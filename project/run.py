"""
文件名: run.py
功能描述: CourseJudge 桌面客户端启动总入口。
          启动 FastAPI 后台 ASGI 服务线程，等待 HTTP 就绪后拉起 PyWebView
          原生桌面独立窗口，支持自适应端口探测与 --headless 调试模式。
遵循规范: 严格遵循 AGENTS.md 规范与 Phase 6.1 要求；
          环境变量外部化；完备中文注释；主窗口退出联动停止后端服务。
"""

import argparse
import os
import socket
import sys
import threading
import time
import urllib.request
from typing import Optional

# 确保在 Windows 控制台中文输出正常
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 确保项目根目录在 sys.path 中
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import uvicorn
from app.core.config import settings


def find_available_port(host: str = "127.0.0.1", start_port: int = 8000, max_attempts: int = 30) -> int:
    """
    自动检测可用端口，若首选端口被占用则顺序探测后续空闲端口。

    :param host: 监听地址
    :param start_port: 起始尝试端口
    :param max_attempts: 最大探测次数
    :return: 确认可用的端口号
    """
    for offset in range(max_attempts):
        port = start_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # 尝试直接绑定端口，若已被占用则抛出 OSError 并继续探测
            try:
                sock.bind((host, port))
                return port
            except OSError:
                continue
    # 兜底返回起始端口
    return start_port


class UvicornServerThread(threading.Thread):
    """
    在守护线程中运行 Uvicorn 服务器，
    主窗口关闭或接收到终止信号时优雅退出。
    """

    def __init__(self, host: str, port: int):
        super().__init__(name="UvicornServerThread", daemon=True)
        self.host = host
        self.port = port
        self.config = uvicorn.Config(
            app="app.main:app",
            host=self.host,
            port=self.port,
            log_level="warning",  # 减少桌面端控制台日志刷屏
            access_log=False,
            workers=1,
        )
        self.server = uvicorn.Server(self.config)

    def run(self) -> None:
        """运行 ASGI 服务器"""
        self.server.run()

    def stop(self) -> None:
        """优雅通知服务器退出"""
        self.server.should_exit = True


def wait_for_server(url: str, timeout_seconds: float = 12.0) -> bool:
    """
    轮询等待后端 HTTP 服务就绪，避免 PyWebView 窗口加载时出现白屏或连接被拒。

    :param url: 待检测的后端入口 URL
    :param timeout_seconds: 最长等待超时时间（秒）
    :return: 服务就绪返回 True，超时返回 False
    """
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status in (200, 301, 302, 307, 308):
                    return True
        except Exception:
            time.sleep(0.15)
    return False


def start_webview(target_url: str, title: str) -> None:
    """
    唤起 PyWebView 现代原生桌面独立窗口。

    :param target_url: 目标前端访问 URL
    :param title: 桌面窗口标题
    """
    import webview

    # 创建标准高清视窗 (1280x820)，支持缩放与窗口缩放
    window = webview.create_window(
        title=title,
        url=target_url,
        width=1280,
        height=820,
        min_size=(1024, 680),
        text_select=True,
        zoomable=True,
        confirm_close=False,
    )
    # 启动桌面事件主循环（阻塞当前主线程直到窗口关闭）
    webview.start(debug=False)


def main() -> None:
    """主启动逻辑：参数解析、服务启动、健康检测、拉起原生视窗"""
    parser = argparse.ArgumentParser(
        description="CourseJudge 智能代码判题与教学辅助系统桌面客户端"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=settings.SERVER_HOST,
        help=f"后端监听主机地址（默认: {settings.SERVER_HOST}）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.SERVER_PORT,
        help=f"首选监听端口（默认: {settings.SERVER_PORT}，占用将自动递增探测）",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="以无头纯后端模式运行（不拉起 PyWebView 桌面窗口，方便远程或终端开发）",
    )
    args = parser.parse_args()

    # 1. 端口智能探测
    actual_port = find_available_port(host=args.host, start_port=args.port)
    base_url = f"http://{args.host}:{actual_port}"
    ui_url = f"{base_url}/ui/"

    print("==============================================================================")
    print("           CourseJudge 智能代码判题系统 - 桌面客户端启动程序")
    print("==============================================================================")
    print(f"[1/3] 检测监听服务端口: {actual_port} (目标地址: {base_url})")

    # 2. 启动 Uvicorn 后台服务线程
    server_thread = UvicornServerThread(host=args.host, port=actual_port)
    server_thread.start()
    print("[2/3] 后端服务线程已拉起，正在等待健康检查就绪...")

    # 3. 等待后端 HTTP 连通就绪
    is_ready = wait_for_server(f"{base_url}/ui/", timeout_seconds=15.0)
    if not is_ready:
        print("[警告] 等待后端服务响应超时，将尝试继续加载界面...")
    else:
        print("[2/3] 后端服务健康就绪！")

    # 4. 根据模式决定是否拉起 PyWebView 桌面视窗
    if args.headless:
        print(f"[3/3] 处于 --headless 模式，服务已就绪！")
        print(f"      - 桌面前端访问入口: {ui_url}")
        print(f"      - API 交互文档入口: {base_url}/docs")
        print("      提示: 按 Ctrl + C 即可退出服务。")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\n正在停止服务...")
            server_thread.stop()
            print("服务已平稳停止。")
    else:
        print(f"[3/3] 正在拉起 PyWebView 原生桌面视窗 (加载: {ui_url}) ...")
        print("      提示: 直接关闭桌面窗口即可安全退出应用。")
        try:
            start_webview(
                target_url=ui_url,
                title=f"{settings.PROJECT_NAME} v{settings.VERSION} - 智能代码判题与教学辅助系统",
            )
        except Exception as exc:
            print(f"[提示] 拉起 PyWebView 视窗异常 ({exc})，已自动降级为浏览器引导模式：")
            print(f"       请在浏览器中打开: {ui_url}")
            try:
                import webbrowser
                webbrowser.open(ui_url)
                while True:
                    time.sleep(1.0)
            except KeyboardInterrupt:
                pass
        finally:
            # 窗口关闭后，通知后台线程停止
            print("\n检测到桌面窗口已关闭，正在安全释放资源...")
            server_thread.stop()
            print("CourseJudge 桌面端已安全退出。")


if __name__ == "__main__":
    main()
