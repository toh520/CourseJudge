"""
文件名: __init__.py
功能描述: 判题评测引擎子域统一聚合导出入口，对外暴露编译器探针、沙箱运行器、输出比对器与判题调度服务。
遵循规范: services/judge 二级子域，按业务功能单文件职责聚合。
"""

from app.services.judge.compiler_probe import CompilerProbe
from app.services.judge.sandbox_runner import SandboxRunner
from app.services.judge.output_comparator import OutputComparator
from app.services.judge.judge_service import JudgeService

__all__ = [
    "CompilerProbe",
    "SandboxRunner",
    "OutputComparator",
    "JudgeService",
]