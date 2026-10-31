"""
文件名: verifier.py
功能描述: 测试用例 100% 正向验证器。
遵循规范: LLM 只负责生成测试输入，期望输出一律由后端真实编译运行标准 C++ 解答后回填，
          从根本上杜绝“用例期望答案与标准解答不一致”的问题。
"""

from typing import List, Optional

from app.services.judge.judge_service import JudgeService
from app.services.llm.common.schemas import VerifiedTestCase


class TestCaseVerificationError(RuntimeError):
    """标准代码无法编译或运行失败，导致测试用例无法完成正向回填时抛出"""


def verify_standard_code(
    standard_code: str,
    test_inputs: List[str],
    time_limit_ms: Optional[int] = None,
    memory_limit_mb: Optional[int] = None,
    judge_service: Optional[JudgeService] = None,
) -> List[VerifiedTestCase]:
    """
    使用标准 C++ 解答真实运行每一组测试输入，抓取标准输出作为期望结果

    参数:
        standard_code (str): LLM 生成的标准 C++17 解答源码
        test_inputs (List[str]): LLM 生成的测试输入集合
        time_limit_ms (Optional[int]): 题目级时间限制毫秒数
        memory_limit_mb (Optional[int]): 题目级内存限制MB数
        judge_service (Optional[JudgeService]): 可注入的判题服务 (便于测试与复用)

    返回:
        List[VerifiedTestCase]: 输入与标准输出严格配对的已验证用例

    异常:
        TestCaseVerificationError: 标准代码编译失败或任一用例运行失败
    """
    inputs = ["" if item is None else str(item) for item in (test_inputs or [])]
    if not inputs:
        raise TestCaseVerificationError("没有可用于验证的测试输入")

    judge = judge_service or JudgeService()
    compile_ok, compiler_output, work_dir, executable_path = judge.compile_code(standard_code)

    if not compile_ok:
        # 编译失败也要清理隔离目录，避免临时文件残留
        judge.sandbox.cleanup(work_dir)
        raise TestCaseVerificationError(
            "标准解答编译失败: " + (compiler_output or "未知编译错误")[:500]
        )

    try:
        cases: List[VerifiedTestCase] = []
        for index, input_data in enumerate(inputs, start=1):
            run_result = judge.sandbox.run_executable(
                executable_path,
                input_data,
                work_dir,
                time_limit_ms=time_limit_ms,
                memory_limit_mb=memory_limit_mb,
            )
            if run_result["status"] != "Accepted":
                raise TestCaseVerificationError(
                    "第 %d 组用例运行失败: %s %s"
                    % (index, run_result["status"], run_result.get("error_msg", ""))
                )
            cases.append(VerifiedTestCase(
                input_data=input_data,
                output_data=run_result["stdout"],
                score_weight=0,
            ))

        _assign_weights(cases)
        return cases
    finally:
        # 无论验证成功与否，都必须清理本次编译运行的隔离目录
        judge.sandbox.cleanup(work_dir)


def _assign_weights(cases: List[VerifiedTestCase]) -> None:
    """
    将 100 分权重均匀分配给全部用例，余数补给前若干组

    参数:
        cases (List[VerifiedTestCase]): 待分配权重的用例列表
    """
    count = len(cases)
    base, remainder = divmod(100, count)
    for index, case in enumerate(cases):
        case.score_weight = base + (1 if index < remainder else 0)