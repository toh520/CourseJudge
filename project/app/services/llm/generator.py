"""
文件名: generator.py
功能描述: 教师端 AI 快速出题与测试用例生成调度服务。
遵循规范: LLM 负责生成题面、标准解答与测试输入；后端真实编译运行标准解答回填期望输出，
          形成“出题 -> 生成输入 -> 运行标准解 -> 用例验证”的 100% 正向闭环。
"""

from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from app.services.judge.judge_service import JudgeService
from app.services.llm.client import LLMClient
from app.services.llm.common.parsers import LLMResponseFormatError, extract_json_object
from app.services.llm.common.schemas import (
    GeneratedProblem,
    GeneratedTestInputs,
)
from app.services.llm.common.verifier import verify_standard_code
from app.services.llm.prompts.problem_generation import (
    PROBLEM_SYSTEM_PROMPT,
    build_problem_prompt,
)
from app.services.llm.prompts.testcase_generation import (
    TESTCASE_SYSTEM_PROMPT,
    build_testcase_prompt,
)


class ProblemGenerator:
    """
    AI 快速出题调度服务

    对外提供:
        - generate_problem(): 生成完整题目、标准解答与已验证测试用例;
        - generate_test_inputs(): 仅生成测试输入 (供教师单独重新生成用例时复用)。
    """

    # 单次出题允许的测试用例数量范围
    MIN_TEST_COUNT = 1
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

    def generate_problem(
        self,
        intent: str,
        knowledge_tag: str = "",
        difficulty: str = "中等",
        test_count: int = 5,
    ) -> Dict[str, Any]:
        """
        根据教师自然语言意图生成完整题目与已验证测试用例

        参数:
            intent (str): 教师出题意图
            knowledge_tag (str): 指定知识点标签，可为空
            difficulty (str): 目标难度
            test_count (int): 期望生成的测试用例数量

        返回:
            Dict[str, Any]: {"problem": 题目字段字典, "test_cases": 已验证用例列表}

        异常:
            ValueError: 出题意图为空
            LLMResponseFormatError: 模型输出结构不符合预期
            TestCaseVerificationError: 标准解答无法编译或运行
        """
        if not intent or not intent.strip():
            raise ValueError("出题意图不能为空")

        count = min(max(int(test_count), self.MIN_TEST_COUNT), self.MAX_TEST_COUNT)

        raw_problem = self.llm.chat([
            {"role": "system", "content": PROBLEM_SYSTEM_PROMPT},
            {"role": "user", "content": build_problem_prompt(intent, knowledge_tag, difficulty)},
        ])
        problem = self._parse_model(raw_problem, GeneratedProblem)

        test_inputs = self.generate_test_inputs(problem, count)
        cases = verify_standard_code(
            problem.standard_code,
            test_inputs,
            time_limit_ms=problem.time_limit_ms,
            memory_limit_mb=problem.memory_limit_mb,
            judge_service=self.judge,
        )

        problem_payload = problem.model_dump()
        problem_payload["is_ai_generated"] = True
        return {
            "problem": problem_payload,
            "test_cases": [case.model_dump() for case in cases],
        }

    def generate_test_inputs(
        self,
        problem: GeneratedProblem,
        count: int = 5,
    ) -> List[str]:
        """
        针对已生成题目补充测试输入数据

        参数:
            problem (GeneratedProblem): 已校验的题目对象
            count (int): 期望生成的输入组数

        返回:
            List[str]: 测试输入文本列表

        异常:
            LLMResponseFormatError: 模型输出结构不符合预期
        """
        count = min(max(int(count), self.MIN_TEST_COUNT), self.MAX_TEST_COUNT)

        raw_inputs = self.llm.chat([
            {"role": "system", "content": TESTCASE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_testcase_prompt(
                    title=problem.title,
                    description=problem.description,
                    input_format=problem.input_format,
                    output_format=problem.output_format,
                    standard_code=problem.standard_code,
                    count=count,
                ),
            },
        ])
        parsed = self._parse_model(raw_inputs, GeneratedTestInputs)
        return parsed.test_inputs[:count]

    @staticmethod
    def _parse_model(raw_text: str, model_cls):
        """
        将模型文本解析为指定 Pydantic 模型

        参数:
            raw_text (str): 模型原始输出
            model_cls: 目标 Pydantic 模型类

        返回:
            Any: 校验通过的模型实例

        异常:
            LLMResponseFormatError: JSON 无法解析或字段校验失败
        """
        data = extract_json_object(raw_text)
        try:
            return model_cls.model_validate(data)
        except ValidationError as exc:
            raise LLMResponseFormatError(
                "模型返回结构不符合预期: %s" % exc
            ) from exc