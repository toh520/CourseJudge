"""
文件名: trainer.py
功能描述: 学生专属强化训练题生成与落库服务。
遵循规范: 依据薄弱知识点生成 1 道阶梯巩固题，测试输入经标准代码真实验证后，
          以 JSON 形式归档至学生个人专属训练题本。
"""

import json
from typing import Optional

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.training import TrainingProblem
from app.services.judge.judge_service import JudgeService
from app.services.llm.client import LLMClient
from app.services.llm.common.parsers import LLMResponseFormatError, extract_json_object
from app.services.llm.common.schemas import GeneratedTrainingProblem
from app.services.llm.common.verifier import verify_standard_code
from app.services.llm.prompts.training_generation import (
    TRAINING_SYSTEM_PROMPT,
    build_training_prompt,
)


class TrainingProblemGenerator:
    """
    专属强化训练题生成服务

    generate_and_save() 完成“模型生成 -> 标准代码运行验证 -> ORM 落库”的完整闭环。
    """

    # 单道强化题最多保留的测试用例数量
    MAX_TEST_COUNT = 10

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        judge_service: Optional[JudgeService] = None,
    ):
        """
        参数:
            llm_client (Optional[LLMClient]): 可注入的 LLM 客户端
            judge_service (Optional[JudgeService]): 可注入的判题服务
        """
        self.llm = llm_client or LLMClient()
        self.judge = judge_service or JudgeService()

    def generate_and_save(
        self,
        db: Session,
        student_id: int,
        weak_point: str,
        source_assignment_id: Optional[int] = None,
        source_assignment_title: str = "",
        test_count: int = 4,
    ) -> TrainingProblem:
        """
        生成一道针对薄弱点的强化题、验证配套用例并保存到学生专属题本

        参数:
            db (Session): 数据库会话
            student_id (int): 归属学生用户ID
            weak_point (str): 薄弱知识点标签
            source_assignment_id (Optional[int]): 来源作业/考试ID
            source_assignment_title (str): 来源作业/考试名称
            test_count (int): 期望生成的测试输入组数

        返回:
            TrainingProblem: 已持久化的强化训练题实体

        异常:
            ValueError: 薄弱知识点为空
            LLMResponseFormatError: 模型输出结构不符合预期
            TestCaseVerificationError: 标准解答无法编译或运行
        """
        if not weak_point or not weak_point.strip():
            raise ValueError("薄弱知识点不能为空")

        raw_text = self.llm.chat([
            {"role": "system", "content": TRAINING_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_training_prompt(
                    weak_point=weak_point.strip(),
                    source_assignment_title=source_assignment_title,
                    test_count=test_count,
                ),
            },
        ])

        try:
            generated = GeneratedTrainingProblem.model_validate(extract_json_object(raw_text))
        except ValidationError as exc:
            raise LLMResponseFormatError(
                "强化题结构不符合预期: %s" % exc
            ) from exc

        test_inputs = generated.test_inputs[:self.MAX_TEST_COUNT]
        cases = verify_standard_code(
            generated.standard_code,
            test_inputs,
            time_limit_ms=generated.time_limit_ms,
            memory_limit_mb=generated.memory_limit_mb,
            judge_service=self.judge,
        )

        training = TrainingProblem(
            student_id=student_id,
            source_assignment_id=source_assignment_id,
            knowledge_tag=(generated.knowledge_tag or weak_point.strip())[:50],
            title=generated.title[:100],
            description=self._compose_description(generated),
            sample_input=generated.sample_input,
            sample_output=generated.sample_output,
            test_cases_json=json.dumps(
                [case.model_dump() for case in cases],
                ensure_ascii=False,
            ),
            best_status="Unsolved",
        )

        try:
            db.add(training)
            db.commit()
            db.refresh(training)
        except Exception:
            db.rollback()
            raise

        return training

    @staticmethod
    def _compose_description(generated: GeneratedTrainingProblem) -> str:
        """
        将题面与输入输出格式合并为完整 Markdown 描述

        参数:
            generated (GeneratedTrainingProblem): 模型生成的强化题

        返回:
            str: 完整 Markdown 题面
        """
        parts = [generated.description.strip()]
        if generated.input_format.strip():
            parts.append("**输入格式**\n" + generated.input_format.strip())
        if generated.output_format.strip():
            parts.append("**输出格式**\n" + generated.output_format.strip())
        return "\n\n".join(parts)