"""
文件名: judge_service.py
功能描述: 判题调度与自测运行服务模块，负责协调编译器探针、沙箱运行器与输出比对器，完成单点自测与全套用例评测。
遵循规范: 自测运行不记录得分；正式评测遍历全部隐藏用例，依据通过权重计算百分比得分并回传最终状态。
"""

from pathlib import Path
from typing import List, Optional, Union

from app.core.config import settings
from app.services.judge.compiler_probe import CompilerProbe
from app.services.judge.sandbox_runner import SandboxRunner
from app.services.judge.output_comparator import OutputComparator


class JudgeService:
    """
    C++ 代码判题调度服务类
    对外暴露两个核心能力:
        - run_custom_test():  学生自测运行 (不记录分数，仅返回单点运行与比对结果);
        - judge_submission(): 正式提交评测 (遍历全部隐藏用例，计算百分比得分与最终状态)。
    """

    # 判题结果状态码 (与 Submission 模型 status 字段取值保持一致)
    STATUS_AC = "AC"
    STATUS_WA = "WA"
    STATUS_TLE = "TLE"
    STATUS_CE = "CE"
    STATUS_RE = "RE"

    def __init__(self) -> None:
        """初始化判题核心三组件: 探针、沙箱、比对器（单一实例复用）"""
        self.probe = CompilerProbe()
        self.sandbox = SandboxRunner()
        self.comparator = OutputComparator()

    def compile_code(self, source_code: str):
        """
        编译用户提交的 C++ 源码（供 self-test 与正式评测复用的底层步骤）

        参数:
            source_code (str): 用户提交的 C++ 源代码文本

        返回:
            tuple: (compile_ok, compiler_output, work_dir, executable_path)
        """
        work_dir = self.sandbox.create_work_dir()
        compile_ok, compiler_output, executable_path = self.sandbox.compile_source(source_code, work_dir)
        return compile_ok, compiler_output, work_dir, executable_path

    def run_custom_test(self, source_code: str, input_data: str, expected_output: str = "") -> dict:
        """
        执行单点自测运行逻辑 (不记录任何分数)

        参数:
            source_code (str): 用户提交的 C++ 源代码
            input_data (str): 本次自测喂入的标准输入数据
            expected_output (str): 本次自测期望的标准输出 (可为空，用于可选比对)

        返回:
            dict: 自测结果字典，包含编译状态、执行状态、输出、耗时与比对结论
        """
        result = {
            "compile_ok": False,
            "compiler_output": "",
            "execution_status": "",
            "stdout": "",
            "expected_output": expected_output,
            "time_ms": 0,
            "error_msg": "",
            "is_accepted": None,   # 无期望输出时不做 AC 判定
        }

        compile_ok, compiler_output, work_dir, executable_path = self.compile_code(source_code)
        result["compile_ok"] = compile_ok
        result["compiler_output"] = compiler_output

        if not compile_ok:
            # 编译失败定位为 CE，回传编译器错误日志
            result["execution_status"] = self.STATUS_CE
            result["error_msg"] = compiler_output
            return result

        try:
            run_result = self.sandbox.run_executable(executable_path, input_data, work_dir)
            result["execution_status"] = run_result["status"]
            result["stdout"] = run_result["stdout"]
            result["time_ms"] = run_result["time_ms"]
            result["error_msg"] = run_result["error_msg"]

            # 若提供了期望输出，则进行文本智能比对
            if expected_output is not None and expected_output != "":
                accepted, message = self.comparator.compare(result["stdout"], expected_output)
                result["is_accepted"] = accepted
                if not accepted:
                    result["execution_status"] = self.STATUS_WA
        finally:
            # 自测结束务必清理隔离目录，避免磁盘残留
            self.sandbox.cleanup(work_dir)

        return result

    def judge_submission(self, source_code: str, test_cases: List) -> dict:
        """
        遍历题目全部隐藏评测用例，计算通过百分比与得分

        参数:
            source_code (str): 学生提交的 C++ 源码
            test_cases (List): 测试用例集合 (TestCase ORM 对象或含 input_data/output_data/score_weight 属性的对象)

        返回:
            dict: 判题结果字典，包含最终状态、得分、通过数、最大耗时及每个用例的明细
        """
        result = {
            "status": self.STATUS_CE,
            "score": 0,
            "passed_cases": 0,
            "total_cases": len(test_cases),
            "max_time_ms": 0,
            "compiler_output": "",
            "case_results": [],
        }

        compile_ok, compiler_output, work_dir, executable_path = self.compile_code(source_code)
        result["compiler_output"] = compiler_output

        if not compile_ok:
            # 编译失败直接整体 CE
            result["status"] = self.STATUS_CE
            result["error_msg"] = compiler_output
            return result

        try:
            total_weight = 0     # 全部用例总权重
            gained_weight = 0    # 通过用例的权重之和
            final_status = self.STATUS_AC  # 默认乐观为 AC
            error_flag = False

            for case in test_cases:
                # 支持 TestCase ORM 对象或普通对象，统一提取字段
                input_data = getattr(case, "input_data", "")
                expected_output = getattr(case, "output_data", "")
                weight = int(getattr(case, "score_weight", 10) or 0)
                total_weight += weight

                run_result = self.sandbox.run_executable(executable_path, input_data, work_dir)
                time_used = run_result["time_ms"]
                result["max_time_ms"] = max(result["max_time_ms"], time_used)

                # 依据沙箱运行状态 + 文本比对判定单个用例结果
                if run_result["status"] == "Time Limit Exceeded":
                    case_status = self.STATUS_TLE
                    final_status = self.STATUS_TLE
                    error_flag = True
                elif run_result["status"] == "Runtime Error":
                    case_status = self.STATUS_RE
                    final_status = self.STATUS_RE
                    error_flag = True
                else:
                    accepted, _ = self.comparator.compare(run_result["stdout"], expected_output)
                    if accepted:
                        case_status = self.STATUS_AC
                        gained_weight += weight
                        result["passed_cases"] += 1
                    else:
                        # 出现答案错误，最终状态降级为 WA (保留首个错误权重)
                        if not error_flag:
                            final_status = self.STATUS_WA
                        case_status = self.STATUS_WA

                result["case_results"].append({
                    "case_status": case_status,
                    "stdout": run_result["stdout"],
                    "expected": expected_output,
                    "time_ms": time_used,
                    "weight": weight,
                })

            # 计算最终百分比得分 (权重加权)
            if total_weight > 0:
                result["score"] = int(round(gained_weight / total_weight * 100))
            else:
                result["score"] = 100 if final_status == self.STATUS_AC and result["total_cases"] == 0 else result["score"]

            # 全部通过且无任何错误时保持 AC
            result["status"] = final_status if (result["passed_cases"] < result["total_cases"] or error_flag) else self.STATUS_AC
        finally:
            # 评测结束清理隔离目录
            self.sandbox.cleanup(work_dir)

        return result