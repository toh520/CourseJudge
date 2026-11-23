"""
文件名: test_phase6.py
功能描述: CourseJudge Phase 6 系统整装、环境回归与桌面入口交付验收测试脚本。
涵盖范围:
  1. 智能双模编译器在模拟无环境(PATH无g++)下的内置平滑降级与 C++ 评测能力；
  2. 团队数据快照导出与幂等合并导入机制验证；
  3. 桌面主入口 run.py 端口探测、后台服务线程与 HTTP 健康就绪检查；
  4. 团队启动与同步批处理脚本 (一键启动/一键同步/一键导出) 完整性核验。
"""

import json
import os
import shutil
import socket
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import urllib.request
from pathlib import Path

# 保证控制台标准输出编码为 UTF-8
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 将 project 目录加入 sys.path
PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.core.seed import export_snapshot, sync_snapshot, seed_demo_accounts
from app.models.user import User
from app.models.clazz import Class
from app.models.assignment import Assignment
from app.models.problem import Problem, TestCase
from app.services.judge import CompilerProbe, SandboxRunner
from run import find_available_port, wait_for_server, UvicornServerThread


class TestPhase6Integration(unittest.TestCase):
    """Phase 6 系统整装与交付集成验收测试套件"""

    @classmethod
    def setUpClass(cls):
        """初始化测试数据库"""
        init_db()

    @patch.object(CompilerProbe, "find_system_compiler", return_value=None)
    @patch.object(settings, "COMPILER_PROBE_MODE", "auto")
    def test_01_compiler_probe_fallback_and_builtin_judge(self, _system_lookup):
        """
        验证 Step 6.2: 智能双模探针在 PATH 移除 g++ 时的平滑降级机制与 C++ 编译执行
        """
        probe = CompilerProbe()
        status = probe.probe_status()

        # 检查是否成功探测到可用编译器
        self.assertTrue(status.get("ready"), f"系统未检测到任何可用 C++ 编译器！详情: {status}")

        self.assertEqual(status["resolved_compiler"], probe.find_builtin_compiler())

        # 验证沙箱编译与受限执行
        sandbox = SandboxRunner()
        work_dir = sandbox.create_work_dir()
        try:
            cpp_code = (
                '#include <iostream>\n'
                'using namespace std;\n'
                'int main() {\n'
                '    int a, b;\n'
                '    if (cin >> a >> b) cout << (a + b) << endl;\n'
                '    return 0;\n'
                '}\n'
            )
            compile_ok, compile_out, exe_path = sandbox.compile_source(cpp_code, work_dir)
            self.assertTrue(compile_ok, f"C++ 代码编译失败: {compile_out}")
            self.assertIsNotNone(exe_path, "未生成可执行文件")

            # 执行测试
            run_result = sandbox.run_executable(
                executable_path=exe_path,
                input_data="123 456\n",
                work_dir=work_dir,
                time_limit_ms=2000,
                memory_limit_mb=128,
            )
            self.assertIn(run_result.get("status"), ("Accepted", "AC"), f"运行异常: {run_result}")
            self.assertEqual(run_result.get("stdout", "").strip(), "579", "输出结果不符合预期！")
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def test_02_data_snapshot_export_and_idempotent_sync(self):
        """
        验证 Step 6.3: 团队数据快照导出与幂等合并导入机制
        """
        temp_dir = tempfile.mkdtemp(prefix="test_snapshot_")
        snapshot_file = os.path.join(temp_dir, "test_snapshot.json")

        try:
            # 1. 导出当前数据库快照
            export_data = export_snapshot(output_file=snapshot_file)
            self.assertIsInstance(export_data, dict)
            self.assertTrue(os.path.exists(snapshot_file), "快照文件未生成！")

            # 2. 验证快照内容包含核心业务表
            with open(snapshot_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("users", data)
            self.assertIn("classes", data)
            self.assertIn("assignments", data)

            # 3. 验证幂等合并导入 (连续两次导入不会重复生成记录或抛错)
            stats_1 = sync_snapshot(input_file=snapshot_file)
            self.assertIsInstance(stats_1, dict)

            stats_2 = sync_snapshot(input_file=snapshot_file)
            self.assertIsInstance(stats_2, dict)
            # 第二次导入由于所有数据已存在，新增条数应为 0
            total_imported_2 = sum(stats_2.values())
            self.assertEqual(total_imported_2, 0, f"幂等导入异常，产生了重复导入: {stats_2}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_03_run_port_detector_and_server_thread(self):
        """
        验证 Step 6.1: 桌面启动入口 run.py 的端口探测与后台服务线程
        """
        # 1. 测试端口探测逻辑
        available_port = find_available_port(host="127.0.0.1", start_port=8900, max_attempts=10)
        self.assertGreaterEqual(available_port, 8900)

        # 2. 测试占用探测是否自动避让已占用端口
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as mock_occupied:
            mock_occupied.bind(("127.0.0.1", available_port))
            mock_occupied.listen(1)
            next_port = find_available_port(host="127.0.0.1", start_port=available_port, max_attempts=10)
            self.assertNotEqual(next_port, available_port, "端口探测未能避开已占用端口！")

        # 3. 测试后台 UvicornServerThread 与 wait_for_server 健康检查
        server_port = find_available_port(host="127.0.0.1", start_port=8940, max_attempts=20)
        server_thread = UvicornServerThread(host="127.0.0.1", port=server_port)
        server_thread.start()

        try:
            # 等待服务就绪
            is_ready = wait_for_server(f"http://127.0.0.1:{server_port}/ui/", timeout_seconds=8.0)
            self.assertTrue(is_ready, "后台服务线程启动后，在超时时间内未响应 HTTP 请求！")

            # 发送探测请求验证
            req = urllib.request.Request(f"http://127.0.0.1:{server_port}/api/v1/system/status")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                self.assertEqual(resp.status, 200)
        finally:
            server_thread.stop()

    def test_04_startup_scripts_and_assets_integrity(self):
        """
        验证 Step 6.3 & 规范 5: 团队启动、同步脚本与静态资产完整性
        """
        root_dir = PROJECT_DIR.parent

        # 验证根目录批处理脚本存在且编码首行为 chcp 65001
        root_scripts = [
            root_dir / "一键启动.bat",
            root_dir / "一键同步.bat",
            root_dir / "一键导出数据.bat",
        ]
        for script_path in root_scripts:
            self.assertTrue(script_path.exists(), f"脚本缺失: {script_path.name}")
            with open(script_path, "r", encoding="utf-8") as f:
                first_lines = f.read(100)
                self.assertIn("chcp 65001", first_lines, f"{script_path.name} 首行未声明 UTF-8 编码！")

        # 验证 project 目录脚本存在
        proj_scripts = [
            PROJECT_DIR / "start.bat",
            PROJECT_DIR / "sync.bat",
            PROJECT_DIR / "export_data.bat",
            PROJECT_DIR / "run.py",
            PROJECT_DIR / "requirements.txt",
            PROJECT_DIR / ".env.example",
            PROJECT_DIR / "storage" / "data_snapshot.json",
        ]
        for script_path in proj_scripts:
            self.assertTrue(script_path.exists(), f"关键文件缺失: {script_path.name}")

        # 验证前端核心静态资产已落盘
        ui_index = PROJECT_DIR / "app" / "ui" / "index.html"
        self.assertTrue(ui_index.exists(), "前端主入口 app/ui/index.html 缺失！")


if __name__ == "__main__":
    unittest.main()
