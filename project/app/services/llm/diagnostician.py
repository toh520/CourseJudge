"""
文件名: diagnostician.py
功能描述: 考后学情短板深度诊断服务。
遵循规范: 汇总学生未满分题目的源码与评测错误点，引导 LLM 输出结构化薄弱知识点与学习指导。
"""

from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from app.core.config import settings
from app.services.llm.client import LLMClient
from app.services.llm.common.parsers import LLMResponseFormatError, extract_json_object
from app.services.llm.common.schemas import DiagnosisReport
from app.services.llm.prompts.diagnosis import (
    DIAGNOSIS_SYSTEM_PROMPT,
    build_diagnosis_prompt,
)


class Diagnostician:
    """
    考后短板诊断服务

    接收学生未拿满分的题目记录，输出结构化诊断报告，供前端卡片式展示与后续强化题生成。
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        参数:
            llm_client (Optional[LLMClient]): 可注入的 LLM 客户端
        """
        self.llm = llm_client or LLMClient()

    def diagnose(
        self,
        assignment_title: str,
        submissions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        针对一次作业/考试的全部失分题目生成短板诊断报告

        参数:
            assignment_title (str): 作业/考试名称
            submissions (List[Dict[str, Any]]): 学生提交记录摘要列表

        返回:
            Dict[str, Any]: 诊断报告字典 (summary / weak_points / learning_guidance)

        异常:
            LLMResponseFormatError: 模型输出结构不符合预期
        """
        prepared = [self._prepare_submission(item) for item in (submissions or [])]
        if not prepared:
            # 全部满分时无需消耗模型调用，直接返回空诊断
            return {
                "summary": "本次作业没有需要诊断的失分题目。",
                "weak_points": [],
                "learning_guidance": "",
            }

        raw_text = self.llm.chat([
            {"role": "system", "content": DIAGNOSIS_SYSTEM_PROMPT},
            {"role": "user", "content": build_diagnosis_prompt(assignment_title, prepared)},
        ])

        try:
            report = DiagnosisReport.model_validate(extract_json_object(raw_text))
        except ValidationError as exc:
            raise LLMResponseFormatError(
                "诊断报告结构不符合预期: %s" % exc
            ) from exc

        return report.model_dump()

    @staticmethod
    def _prepare_submission(item: Dict[str, Any]) -> Dict[str, Any]:
        """
        裁剪单条提交记录，控制提示词长度并保留诊断所需关键信息

        参数:
            item (Dict[str, Any]): 原始提交记录

        返回:
            Dict[str, Any]: 裁剪后的提交摘要
        """
        code = item.get("code") or ""
        max_chars = max(0, int(settings.LLM_MAX_CODE_CHARS))
        if max_chars and len(code) > max_chars:
            code = code[:max_chars] + "\n... (代码过长，已截断)"

        return {
            "problem_title": item.get("problem_title", ""),
            "knowledge_tag": item.get("knowledge_tag", ""),
            "status": item.get("status", ""),
            "score": item.get("score", 0),
            "code": code,
            "error_msg": item.get("error_msg", ""),
        }