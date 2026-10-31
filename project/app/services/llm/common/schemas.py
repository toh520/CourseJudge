"""
文件名: schemas.py
功能描述: LLM 结构化输出与测试用例验证结果的 Pydantic 数据模型。
遵循规范: 所有模型字段均对应明确的业务语义，禁止模型输出中的多余字段污染业务数据。
"""

from typing import Any, List
from pydantic import BaseModel, Field, field_validator

from app.services.llm.common.parsers import strip_code_fence


class GeneratedProblem(BaseModel):
    """AI 生成题目的结构化结果"""

    title: str = Field(..., min_length=1, max_length=100, description="题目标题")
    description: str = Field(..., min_length=1, description="Markdown 题面描述")
    input_format: str = Field(default="", description="输入格式说明")
    output_format: str = Field(default="", description="输出格式说明")
    sample_input: str = Field(default="", description="公开样例输入")
    sample_output: str = Field(default="", description="公开样例输出")
    time_limit_ms: int = Field(default=1000, ge=100, le=10000, description="时间限制毫秒数")
    memory_limit_mb: int = Field(default=256, ge=16, le=1024, description="内存限制MB数")
    knowledge_tag: str = Field(default="", max_length=50, description="核心知识点标签")
    standard_code: str = Field(..., min_length=1, description="标准 C++17 解答源码")

    @field_validator("input_format", "output_format", "sample_input", "sample_output", "knowledge_tag", mode="before")
    @classmethod
    def _none_to_empty_string(cls, value: Any) -> str:
        """将模型可能返回的 null 统一转换为空字符串"""
        return "" if value is None else str(value)

    @field_validator("standard_code")
    @classmethod
    def _strip_code_fence(cls, value: str) -> str:
        """剥离标准代码外层的 Markdown 代码围栏"""
        return strip_code_fence(value)


class GeneratedTestInputs(BaseModel):
    """AI 生成的测试输入集合 (期望输出由后端运行标准代码回填)"""

    test_inputs: List[str] = Field(..., min_length=1, description="测试输入文本列表")

    @field_validator("test_inputs", mode="before")
    @classmethod
    def _normalize_inputs(cls, value: Any) -> Any:
        """兼容模型返回单个字符串或非字符串数组的情况"""
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return ["" if item is None else str(item) for item in value]
        return value


class GeneratedTrainingProblem(GeneratedProblem):
    """AI 生成的专属强化训练题 (附带测试输入)"""

    test_inputs: List[str] = Field(..., min_length=1, description="测试输入文本列表")

    @field_validator("test_inputs", mode="before")
    @classmethod
    def _normalize_inputs(cls, value: Any) -> Any:
        """兼容模型返回单个字符串或非字符串数组的情况"""
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return ["" if item is None else str(item) for item in value]
        return value


class VerifiedTestCase(BaseModel):
    """经标准代码真实运行验证后的测试用例"""

    input_data: str = Field(..., description="喂入标准输入的数据")
    output_data: str = Field(..., description="标准代码运行产生的期望输出")
    score_weight: int = Field(default=0, ge=0, description="用例分值权重")


class WeakPoint(BaseModel):
    """学生单项薄弱知识点诊断"""

    tag: str = Field(..., min_length=1, max_length=50, description="薄弱知识点标签")
    evidence: str = Field(default="", description="代码或评测结果中的具体证据")
    suggestion: str = Field(default="", description="针对性的改进建议")


class DiagnosisReport(BaseModel):
    """考后短板诊断报告"""

    summary: str = Field(default="", description="整体诊断摘要")
    weak_points: List[WeakPoint] = Field(default_factory=list, description="薄弱知识点列表")
    learning_guidance: str = Field(default="", description="后续学习与复习指导")

    @field_validator("summary", "learning_guidance", mode="before")
    @classmethod
    def _none_to_empty_string(cls, value: Any) -> str:
        """将模型可能返回的 null 统一转换为空字符串"""
        return "" if value is None else str(value)