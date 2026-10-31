"""
文件名: sandbox_runner.py
功能描述: 受限子进程执行沙箱模块，负责在独立隔离目录中编译 C++ 源码，并在超时强杀等资源约束下安全执行编译产物。
遵循规范: 编译与运行目录统一收敛在 storage/temp_judge/{uuid} 下；超时/内存阈值全部外部化到 config 配置。
"""

import os
import sys
import signal
import shutil
import uuid
import subprocess
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.services.judge.compiler_probe import CompilerProbe


class SandboxRunner:
    """
    受限子进程判题沙箱类
    负责 C++ 源码的隔离编译与受限运行。
    核心能力:
        - 在每个独立 UUID 目录中编译，杜绝多用户同时判题的路径冲突;
        - 执行时重定向标准输入/输出，并强制设定 CPU 运行超时阈值，超时即强杀进程树;
        - 捕获运行时非零退出(段错误/除零等)并统一归类为运行错误。
    """

    def __init__(self) -> None:
        """初始化沙箱: 创建探针实例并确保根隔离目录存在"""
        self.probe = CompilerProbe()
        # 从 config 读取隔离目录配置并解析为绝对路径
        self.temp_judge_root = Path(settings.TEMP_JUDGE_DIR).resolve()

    def _ensure_root_ready(self) -> None:
        """确保判题临时根目录存在，不存在则递归创建"""
        self.temp_judge_root.mkdir(parents=True, exist_ok=True)

    def create_work_dir(self) -> Path:
        """
        为一次判题任务创建独立 UUID 工作目录

        返回:
            Path: 新生成的隔离工作目录绝对路径
        """
        self._ensure_root_ready()
        work_dir = self.temp_judge_root / uuid.uuid4().hex
        work_dir.mkdir(parents=True, exist_ok=True)
        return work_dir

    def compile_source(self, source_code: str, work_dir: Path) -> tuple:
        """
        在隔离目录中编译用户提交的 C++ 源代码

        参数:
            source_code (str): 用户提交的完整 C++ 源代码文本
            work_dir (Path): 本次判题的隔离工作目录

        返回:
            tuple: (compile_ok, compiler_output, executable_path)
                - compile_ok (bool): 编译是否成功
                - compiler_output (str): 编译器的完整输出 (含错误信息)
                - executable_path (Optional[Path]): 编译成功后的可执行文件路径，失败为 None
        """
        source_file = work_dir / "main.cpp"
        # 以 UTF-8 写入源码文件，避免中文注释乱码
        source_file.write_text(source_code, encoding="utf-8")

        compiler_path = self.probe.get_compiler()  # 通过双模探针定位 g++
        # 按操作系统约定产生可执行文件名 (Windows 下携带 .exe 后缀)
        executable_path = work_dir / ("main.exe" if os.name == "nt" else "main.out")

        # 组装编译命令: 静态/标准编译，关闭优化以保持行为可预测并提升编译速度
        cmd = [
            compiler_path,
            str(source_file),
            "-o", str(executable_path),
            "-static",  # 静态链接运行时库，规避隔离目录下缺少 libstdc++-6.dll 等导致进程启动失败的 RE 误判
            "-O2",
            "-std=c++17",
            "-DONLINE_JUDGE",
        ]

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=settings.COMPILE_TIMEOUT_SECONDS,
            )
            compiler_output = (proc.stdout or "") + (proc.stderr or "")
            if proc.returncode == 0 and executable_path.exists():
                # 编译成功，清理冗余源码以保持目录干净
                return True, compiler_output.strip(), executable_path
            # 编译失败，回传编译器标准错误供前端回显
            return False, compiler_output.strip(), None
        except subprocess.TimeoutExpired:
            # 编译阶段超时也视作编译失败
            return False, "编译超时 (超过 %.0f 秒)" % settings.COMPILE_TIMEOUT_SECONDS, None

    def run_executable(self, executable_path: Path, input_data: str, work_dir: Path) -> dict:
        """
        在受限子进程中执行编译产物并喂入测试输入

        参数:
            executable_path (Path): 编译生成的可执行文件绝对路径
            input_data (str): 喂入标准输入 (stdin) 的测试用例数据
            work_dir (Path): 隔离工作目录 (作为可执行程序的运行工作目录)

        返回:
            dict: 包含运行状态、标准输出、耗时毫秒数及错误信息的结果字典
                  {
                      "status": "Accepted" | "Time Limit Exceeded" | "Runtime Error",
                      "stdout": str,
                      "time_ms": int,
                      "error_msg": str
                  }
        """
        # 载入默认时间限制阈值 (毫秒)
        time_limit_ms = settings.DEFAULT_TIME_LIMIT_MS
        time_limit_ms = settings.DEFAULT_TIME_LIMIT_MS
        # 崩溃程序会因 Windows 错误报告(WER)后台收集而延迟自然退出(实测约 1.7s 以上)，
        # 追加 WER 缓冲作为"强杀上界"(上界 = 时间限制 + 缓冲)，让已自行退出的崩溃程序携带非零返回码
        # 返回，从而与真正死循环(永不退出)在语义上可区分，避免崩溃被误判为 TLE。
        wer_grace_ms = settings.DEFAULT_EXEC_GRACE_MS
        hard_timeout_ms = time_limit_ms + wer_grace_ms

        # Windows 下抑制子进程崩溃时的错误报告弹窗/延迟收集 (WER)，
        # 否则崩溃程序会因等待用户确认或错误报告而阻塞，被误判为 TLE 而非 RE。
        # SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX = 0x8001
        if os.name == "nt":
            try:
                import ctypes
                ctypes.windll.kernel32.SetErrorMode(0x8001)
            except Exception:
                pass

        # 以子进程启动可执行程序，重定向标准输入/输出/错误流
        proc = subprocess.Popen(
            [str(executable_path)],
            cwd=str(work_dir),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        start_time = _monotonic_ms()
        # 计算本次判定允许的超时轮询边界 (追加少量缓冲应对进程启动开销)

        try:
            stdout, stderr = proc.communicate(input=input_data, timeout=hard_timeout_ms / 1000.0)
        except subprocess.TimeoutExpired:
            # 运行超时: 强杀进程树后收集已输出内容
            self._kill_process_tree(proc)
            try:
                stdout, stderr = proc.communicate()
            except Exception:
                stdout, stderr = "", str(stderr) if stderr else ""
            elapsed_ms = int(_monotonic_ms() - start_time)
            return {
                "status": "Time Limit Exceeded",
                "stdout": (stdout or "").strip(),
                "time_ms": elapsed_ms,
                "error_msg": "运行超时，已强制终止进程",
            }

        elapsed_ms = int(_monotonic_ms() - start_time)
        # 若子进程非零退出 (段错误/除零/非法访问等) 归类为运行错误
        if proc.returncode != 0:
            return {
                "status": "Runtime Error",
                "stdout": (stdout or "").strip(),
                "time_ms": elapsed_ms,
                "error_msg": (stderr or "").strip() or "程序发生运行时错误 (返回码 %s)" % proc.returncode,
            }

        # 返回码为零但实际耗时已超过时间限制: 属程序运行过慢而非崩溃 -> TLE
        if elapsed_ms > time_limit_ms:
            return {
                "status": "Time Limit Exceeded",
                "stdout": (stdout or "").strip(),
                "time_ms": elapsed_ms,
                "error_msg": "程序运行超过时间限制 (%d ms)" % time_limit_ms,
            }

        # 正常运行完成，默认判定为 Accepted (是否真正 AC 交由比对器进一步裁决)
        return {
            "status": "Accepted",
            "stdout": (stdout or "").strip(),
            "time_ms": elapsed_ms,
            "error_msg": (stderr or "").strip(),
        }

    def _kill_process_tree(self, proc: subprocess.Popen) -> None:
        """
        强制终止指定子进程及其全部子进程树 (Windows 与 POSIX 双兼容)

        参数:
            proc (subprocess.Popen): 需要强杀的子进程对象
        """
        try:
            if proc.poll() is None:
                if os.name == "nt":
                    # Windows 下使用系统命令强制结束进程树 (包含孙子进程)
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        capture_output=True,
                        timeout=10,
                    )
                else:
                    # POSIX 下先向整个进程组发送信号
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            # 进程可能已自然退出，忽略强杀异常
            pass

    def cleanup(self, work_dir: Path) -> None:
        """
        评测结束后清理隔离工作目录中的全部临时文件

        参数:
            work_dir (Path): 本次判题的隔离工作目录
        """
        if work_dir and work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)


def _monotonic_ms() -> float:
    """获取单调递增时钟的毫秒计数 (用于精确耗时测算，不受系统时间调整影响)"""
    import time
    return time.monotonic() * 1000.0