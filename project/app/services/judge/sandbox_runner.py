"""
文件名: sandbox_runner.py
功能描述: 受限子进程执行沙箱模块，负责在独立隔离目录中编译 C++ 源码，并在超时强杀等资源约束下安全执行编译产物。
遵循规范: 编译与运行目录统一收敛在 storage/temp_judge/{uuid} 下；超时/内存阈值全部外部化到 config 配置。
"""

import os
import signal
import shutil
import uuid
import subprocess
import threading
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

    def run_executable(
        self,
        executable_path: Path,
        input_data: str,
        work_dir: Path,
        time_limit_ms: Optional[int] = None,
        memory_limit_mb: Optional[int] = None,
    ) -> dict:
        """
        在受限子进程中执行编译产物并喂入测试输入

        参数:
            executable_path (Path): 编译生成的可执行文件绝对路径
            input_data (str): 喂入标准输入 (stdin) 的测试用例数据
            work_dir (Path): 隔离工作目录 (作为可执行程序的运行工作目录)
            time_limit_ms (Optional[int]): 题目级时间限制毫秒数，为空时回退全局默认配置
            memory_limit_mb (Optional[int]): 题目级内存限制MB数，为空时回退全局默认配置

        返回:
            dict: 包含运行状态、标准输出、耗时毫秒数及错误信息的结果字典
                  {
                      "status": "Accepted" | "Time Limit Exceeded" | "Runtime Error",
                      "stdout": str,
                      "time_ms": int,
                      "error_msg": str
                  }
        """
        # 题目级限制优先，缺省时回退全局默认阈值
        time_limit_ms = (
            time_limit_ms if time_limit_ms and time_limit_ms > 0 else settings.DEFAULT_TIME_LIMIT_MS
        )
        memory_limit_mb = (
            memory_limit_mb if memory_limit_mb and memory_limit_mb > 0 else settings.DEFAULT_MEMORY_LIMIT_MB
        )

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

        # 启动内存上限监控线程: 持续轮询常驻内存，超限立即强杀进程树
        memory_monitor = _MemoryMonitor(proc, memory_limit_mb, self._kill_process_tree)
        memory_monitor.start()

        start_time = _monotonic_ms()
        timed_out = False
        try:
            stdout, stderr = proc.communicate(input=input_data, timeout=hard_timeout_ms / 1000.0)
        except subprocess.TimeoutExpired:
            # 运行超时: 强杀进程树后收集已输出内容
            timed_out = True
            self._kill_process_tree(proc)
            try:
                stdout, stderr = proc.communicate()
            except Exception:
                stdout, stderr = "", str(stderr) if stderr else ""
        finally:
            # 无论正常结束还是异常，都必须停止监控线程，避免线程泄漏
            memory_monitor.stop()

        elapsed_ms = int(_monotonic_ms() - start_time)

        # 内存超限优先级最高: 进程是被监控器主动强杀的
        if memory_monitor.exceeded:
            return {
                "status": "Runtime Error",
                "stdout": (stdout or "").strip(),
                "time_ms": elapsed_ms,
                "error_msg": "内存超限 (限制 %d MB)，已强制终止进程" % memory_limit_mb,
            }

        if timed_out:
            return {
                "status": "Time Limit Exceeded",
                "stdout": (stdout or "").strip(),
                "time_ms": elapsed_ms,
                "error_msg": "运行超时，已强制终止进程",
            }

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


class _MemoryMonitor:
    """
    子进程内存上限监控器

    在独立守护线程中以固定间隔轮询目标进程的常驻内存 (RSS)，一旦超过阈值立即回调
    强杀进程树，并记录超限标记供调用方归类为运行错误。
    """

    def __init__(self, proc: subprocess.Popen, limit_mb: int, kill_callback, interval_seconds: float = 0.02):
        """
        参数:
            proc (subprocess.Popen): 被监控的子进程对象
            limit_mb (int): 允许的最大常驻内存 MB 数
            kill_callback: 内存超限时执行强杀的回调函数
            interval_seconds (float): 轮询间隔秒数 (默认 20ms)
        """
        self._proc = proc
        self._limit_mb = limit_mb
        self._kill_callback = kill_callback
        self._interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._exceeded = False
        self._thread = threading.Thread(target=self._watch, daemon=True)

    @property
    def exceeded(self) -> bool:
        """返回监控期间是否发生过内存超限"""
        return self._exceeded

    def start(self) -> None:
        """启动后台监控线程"""
        self._thread.start()

    def stop(self) -> None:
        """通知监控线程退出并等待其结束，避免线程泄漏"""
        self._stop_event.set()
        self._thread.join(timeout=1.0)

    def _watch(self) -> None:
        """监控循环: 定期读取进程 RSS，超限时强杀并退出"""
        try:
            import psutil
            process = psutil.Process(self._proc.pid)
        except Exception:
            # 进程已退出或 psutil 不可用: 放弃监控，交由主流程按返回码判定
            return

        while not self._stop_event.is_set():
            # 进程已自然退出则无需继续监控
            if self._proc.poll() is not None:
                return
            try:
                rss_mb = process.memory_info().rss / (1024 * 1024)
            except Exception:
                # 进程已退出或无法读取内存信息
                return
            if rss_mb > self._limit_mb:
                self._exceeded = True
                self._kill_callback(self._proc)
                return
            self._stop_event.wait(self._interval_seconds)


def _monotonic_ms() -> float:
    """获取单调递增时钟的毫秒计数 (用于精确耗时测算，不受系统时间调整影响)"""
    import time
    return time.monotonic() * 1000.0