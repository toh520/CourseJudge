"""
文件名: test_judge.py
功能描述: Phase 2 C++ 判题引擎与编译器智能双模探针全流程阶段自动化验收测试。
测试范围:
    1. 编译器双模探针定位 g++ (Step 2.1)
    2. 受限子进程沙箱编译与执行 (Step 2.2)
    3. 智能文本输出比对器 (Step 2.3)
    4. 判题调度与自测服务 (Step 2.4)
    5. 五种典型判题结果状态 (AC / WA / TLE / CE / RE) 判定准确性
"""

import os
import sys
import io
from pathlib import Path

# 在 Windows 终端下统一标准输出为 UTF-8，防止 GBK 编码异常
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 将 project 目录加入 Python 搜索路径，确保可以直接导入 app 包
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 使用临时独立的测试临时目录，避免污染真实判题环境
os.environ["TEMP_JUDGE_DIR"] = str(PROJECT_ROOT / "storage" / "test_judge")

from app.services.judge.compiler_probe import CompilerProbe
from app.services.judge.output_comparator import OutputComparator
from app.services.judge.judge_service import JudgeService
from app.services.judge.sandbox_runner import SandboxRunner


# ------------------------- 测试样例 C++ 代码 -------------------------

# 正确解法: 读取两个数求和 (正常 AC)
CODE_AC = """
#include <iostream>
using namespace std;
int main() {
    int a, b;
    cin >> a >> b;
    cout << a + b << endl;
    return 0;
}
"""

# 逻辑错误解法: 改为做差，应判定 WA
CODE_WA = """
#include <iostream>
using namespace std;
int main() {
    int a, b;
    cin >> a >> b;
    cout << a - b << endl;
    return 0;
}
"""

# 死循环解法: while(true) 无退出，应判定 TLE
CODE_TLE = """
#include <iostream>
using namespace std;
int main() {
    int a, b;
    cin >> a >> b;
    while (true) { }
    return 0;
}
"""

# 语法错误解法: 缺少分号，应判定 CE
CODE_CE = """
#include <iostream>
using namespace std;
int main() {
    int a, b
    cin >> a >> b;
    cout << a + b << endl;
    return 0;
}
"""

# 运行时崩溃解法: 空指针解引用触发段错误，应快速非零退出并判定 RE
CODE_RE = """
#include <iostream>
using namespace std;
int main() {
    cout << "before crash" << endl;
    volatile int* p = nullptr;  // volatile 防止编译器在优化下移除该非法访问
    *p = 42;                    // 空指针写入 -> Access Violation -> 崩溃返回非零
    cout << "after crash" << endl;
    return 0;
}
"""

# 超高耗时但正常逻辑: 死等 3 秒 (测试 1 秒 TLE 阈值)
CODE_SLOW = """
#include <iostream>
#include <chrono>
#include <thread>
using namespace std;
int main() {
    int a, b;
    cin >> a >> b;
    this_thread::sleep_for(chrono::milliseconds(3000));
    cout << a + b << endl;
    return 0;
}
"""

# 测试用例 (Input, ExpectedOutput, weight)
TEST_CASES_AC = [
    ("1 2", "3", 50),
    ("10 20", "30", 50),
]


def run_phase2_verification():
    """执行 Phase 2 阶段自动化验收测试流程"""
    print("\n" + "=" * 70)
    print(">>> 开始执行 Phase 2: C++ 判题引擎与编译器智能双模探针 自动化验收测试 <<<")
    print("=" * 70)
    passed = 0
    failed = 0

    def check(label, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  [OK] {label}")
        else:
            failed += 1
            print(f"  [FAIL] {label}")

    # -----------------------------------------------------------------
    # 1. 编译器智能双模探针 (Step 2.1)
    # -----------------------------------------------------------------
    print("\n[测试项 1/5] 验证编译器双模探针定位与智能降级...")
    probe = CompilerProbe()
    try:
        compiler_path = probe.get_compiler()
        check("探针成功定位到可用 g++ 编译器", bool(compiler_path) and "g++" in compiler_path)
        status = probe.probe_status()
        print(f"  探针状态: 模式={status['mode']}, 系统g++={status['system_compiler_available']}, "
              f"内置g++={status['builtin_compiler_available']}")
        print(f"  解析到的编译器路径: {compiler_path}")
    except RuntimeError as e:
        check(f"探针未能定位编译器: {e}", False)

    # -----------------------------------------------------------------
    # 2. 智能文本输出比对器 (Step 2.3)
    # -----------------------------------------------------------------
    print("\n[测试项 2/5] 验证文本输出比对器跨平台归一化...")
    comparator = OutputComparator()
    # 带窗口换行符差异与行末空格
    check("忽略 \\r\\n 换行符差异判定 AC",
          comparator.compare("3\r\n", "3\n")[0] is True)
    check("忽略行末空白与末尾空行判定 AC",
          comparator.compare("3  \n\n\n", "3")[0] is True)
    check("不同数值判定 WA",
          comparator.compare("5", "3")[0] is False)
    check("多行内容一致判定 AC",
          comparator.compare("1\n2\n3", "1  \r\n2\r\n3\n\n")[0] is True)

    # -----------------------------------------------------------------
    # 3. 受限子进程沙箱执行 (Step 2.2)
    # -----------------------------------------------------------------
    print("\n[测试项 3/5] 验证沙箱编译与受限执行...")
    sandbox = SandboxRunner()
    work_dir = sandbox.create_work_dir()
    compile_ok, compiler_output, executable = sandbox.compile_source(CODE_AC, work_dir)
    check("正常源码编译成功", compile_ok and executable is not None)
    if compile_ok:
        run_result = sandbox.run_executable(executable, "1 2", work_dir)
        check("受限执行返回 Accepted 语义", run_result["status"] == "Accepted")
        check("执行输出为 3", run_result["stdout"] == "3")
        check("执行耗时在合理区间", 0 <= run_result["time_ms"] < 1000)
    sandbox.cleanup(work_dir)
    check("沙箱隔离目录执行后清理成功", not work_dir.exists())

    # -----------------------------------------------------------------
    # 4. 判题调度与自测服务 (Step 2.4)
    # -----------------------------------------------------------------
    print("\n[测试项 4/5] 验证自测运行服务 (run_custom_test)...")
    judge = JudgeService()
    self_result = judge.run_custom_test(CODE_AC, "1 2", "3")
    check("自测运行编译成功", self_result["compile_ok"] is True)
    check("自测运行输出正确", self_result["stdout"] == "3")
    check("自测比对判定 AC", self_result["is_accepted"] is True)

    # -----------------------------------------------------------------
    # 5. 五种判题结果状态判定 (Step 2.5)
    # -----------------------------------------------------------------
    print("\n[测试项 5/5] 验证五种典型判题状态 (AC/WA/TLE/CE/RE)...")

    # 5.1 AC: 正确代码 + 全通过用例
    print("\n  --- 场景 A: 正确代码应判定 AC ---")
    ac_result = judge.judge_submission(CODE_AC, _to_case_objs(TEST_CASES_AC))
    check("AC 代码最终状态为 AC", ac_result["status"] == "AC")
    check("AC 代码通过全部用例", ac_result["passed_cases"] == 2 and ac_result["total_cases"] == 2)
    check("AC 代码得分 100 分", ac_result["score"] == 100)
    print(f"    实际状态={ac_result['status']}, 通过={ac_result['passed_cases']}/{ac_result['total_cases']}, 得分={ac_result['score']}")

    # 5.2 WA: 逻辑错误代码 (做差而非求和)
    print("\n  --- 场景 B: 逻辑错误代码应判定 WA ---")
    wa_result = judge.judge_submission(CODE_WA, _to_case_objs(TEST_CASES_AC))
    check("WA 代码最终状态为 WA", wa_result["status"] == "WA")
    check("WA 代码未通过用例", wa_result["passed_cases"] == 0)
    check("WA 代码得分 0 分", wa_result["score"] == 0)
    print(f"    实际状态={wa_result['status']}, 通过={wa_result['passed_cases']}/{wa_result['total_cases']}, 得分={wa_result['score']}")

    # 5.3 TLE: 死循环/超时代码
    print("\n  --- 场景 C: 死循环代码应判定 TLE ---")
    tle_result = judge.judge_submission(CODE_TLE, _to_case_objs(TEST_CASES_AC))
    check("TLE 代码最终状态为 TLE", tle_result["status"] == "TLE")
    print(f"    实际状态={tle_result['status']}")
    print("  --- 场景 C-extra: 高耗时代码 (3秒) 应超时判定 ---")
    slow_result = judge.judge_submission(CODE_SLOW, _to_case_objs(TEST_CASES_AC))
    check("高耗时代码判定为 TLE", slow_result["status"] == "TLE")
    check("TLE 状态耗时记录合理", slow_result["max_time_ms"] >= 900)

    # 5.4 CE: 语法错误代码
    print("\n  --- 场景 D: 语法错误代码应判定 CE ---")
    ce_result = judge.judge_submission(CODE_CE, _to_case_objs(TEST_CASES_AC))
    check("CE 代码最终状态为 CE", ce_result["status"] == "CE")
    check("CE 代码回传编译错误日志", len(ce_result["compiler_output"]) > 0)
    print(f"    实际状态={ce_result['status']}")
    print(f"    编译器回显(截断): {ce_result['compiler_output'][:120]}...")

    # 5.5 RE: 运行时崩溃代码
    print("\n  --- 场景 E: 运行时崩溃代码应判定 RE ---")
    re_result = judge.judge_submission(CODE_RE, _to_case_objs(TEST_CASES_AC))
    check("RE 代码最终状态为 RE", re_result["status"] == "RE")
    print(f"    实际状态={re_result['status']}")

    # -----------------------------------------------------------------
    # 汇总
    # -----------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f">>> Phase 2 验收测试完成: 通过 {passed} 项, 失败 {failed} 项 <<<")
    print("=" * 70)
    if failed > 0:
        sys.exit(1)
    print("\n✅ 所有验收项全部通过，Phase 2 判题引擎开发达标！")


def _to_case_objs(cases):
    """将 (input, output, weight) 元组列表转换为带属性的简易用例对象"""
    class _Case:
        def __init__(self, input_data, output_data, score_weight):
            self.input_data = input_data
            self.output_data = output_data
            self.score_weight = score_weight
    return [_Case(i, o, w) for i, o, w in cases]


if __name__ == "__main__":
    run_phase2_verification()