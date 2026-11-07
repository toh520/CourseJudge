"""
文件名: test_phase5.py
功能描述: Phase 5 PyWebView 桌面客户端界面与交互阶段自动化验收测试。
测试范围:
    1. FastAPI 静态资源挂载与关键前端资产可访问性;
    2. 全部前端 JS 模块的 ES Module 语法检查 (Node.js);
    3. 无头 Chrome 真实渲染登录页冒烟 (验证模块加载与首屏 JS 无致命错误);
    4. Phase 5 页面骨架与关键组件文件完整性。
"""

import io
import os
import sys
import json
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 在 Windows 终端下统一标准输出为 UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 静态资源测试与无头浏览器服务使用相互独立的临时数据库
TEST_DB_FILE = PROJECT_ROOT / "test_phase5.db"
SERVER_DB_FILE = PROJECT_ROOT / "test_phase5_server.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
os.environ["SEED_DEMO_ACCOUNTS"] = "true"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.core.database import engine  # noqa: E402

UI_DIR = PROJECT_ROOT / "app" / "ui"
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

PASSED = 0
FAILED = 0


def check(name: str, cond: bool, extra: str = "") -> None:
    """断言并统计验收通过/失败项"""
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  [PASS] {name}")
    else:
        FAILED += 1
        print(f"  [FAIL] {name}  {extra}")


def free_port() -> int:
    """获取一个空闲本地端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def find_chrome() -> str:
    """查找可用的 Chromium 内核浏览器"""
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return shutil.which("chrome") or shutil.which("chromium") or ""


def api_json(base_url: str, method: str, path: str, token: str = "", payload=None):
    """调用测试服务端 API 并解析 JSON，供前端登录态冒烟准备数据"""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{base_url}/api/v1{path}",
        data=data,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else None


def login_token(base_url: str, username: str, password: str) -> str:
    """通过 API 登录并返回 JWT，用于无头浏览器登录态冒烟"""
    data = api_json(base_url, "POST", "/auth/login", payload={"username": username, "password": password})
    return data.get("access_token", "")


def chrome_dump(chrome: str, url: str, profile_dir: Path) -> str:
    """使用无头浏览器渲染并返回最终 DOM"""
    proc = subprocess.run(
        [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
         "--disable-dev-shm-usage", "--virtual-time-budget=8000",
         f"--user-data-dir={profile_dir}",
         "--dump-dom", url],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=90,
    )
    return proc.stdout or ""


def run_phase5_verification() -> None:
    """执行 Phase 5 阶段自动化验收测试流程"""
    print("\n" + "=" * 70)
    print(">>> 开始执行 Phase 5: PyWebView 桌面客户端界面与交互 自动化验收测试 <<<")
    print("=" * 70)

    client = TestClient(app)

    # -----------------------------------------------------------------
    # 1. 静态资源挂载与关键资产
    # -----------------------------------------------------------------
    print("\n[测试项 1/4] 验证前端静态资源挂载 ...")
    r = client.get("/ui/")
    check("前端首页可访问 200", r.status_code == 200, f"status={r.status_code}")
    html = r.text if r.status_code == 200 else ""
    check("首页包含应用标题与模块入口",
          "CourseJudge" in html and "js/app.js" in html)
    check("首页引用本地 Monaco 与 ECharts",
          "libs/monaco/vs/loader.js" in html and "libs/echarts/echarts.min.js" in html)

    for asset in [
        "/ui/css/base.css",
        "/ui/css/layout.css",
        "/ui/css/components.css",
        "/ui/css/views.css",
        "/ui/js/app.js",
        "/ui/js/api/client.js",
        "/ui/js/views/student/workbench.js",
        "/ui/libs/monaco/vs/loader.js",
        "/ui/libs/echarts/echarts.min.js",
    ]:
        rr = client.get(asset)
        check(f"静态资产可访问 {asset}", rr.status_code == 200 and len(rr.content) > 0, f"status={rr.status_code}")

    r = client.get("/app", follow_redirects=False)
    check("/app 重定向到前端首页", r.status_code in (302, 307) and "/ui/" in r.headers.get("location", ""))

    # -----------------------------------------------------------------
    # 2. 前端 JS 全部通过 ES Module 语法检查
    # -----------------------------------------------------------------
    print("\n[测试项 2/4] 验证前端 JS 模块语法 ...")
    node = shutil.which("node")
    if not node:
        print("  [SKIP] 未检测到 Node.js，跳过 JS 语法检查")
    else:
        js_files = sorted((UI_DIR / "js").rglob("*.js"))
        syntax_errors = []
        for js_file in js_files:
            # 写入临时 .mjs 文件再检查，避免 Windows 控制台 GBK 编码影响 Node 标准输入
            with tempfile.NamedTemporaryFile(
                "w", suffix=".mjs", encoding="utf-8", delete=False
            ) as tmp:
                tmp.write(js_file.read_text(encoding="utf-8"))
                tmp_path = tmp.name
            try:
                proc = subprocess.run(
                    [node, "--check", tmp_path],
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    timeout=30,
                )
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            if proc.returncode != 0:
                syntax_errors.append(f"{js_file.relative_to(PROJECT_ROOT)}: {(proc.stderr or '').strip()[:240]}")
        check(f"全部 {len(js_files)} 个前端 JS 模块语法正确",
              not syntax_errors, "\n".join(syntax_errors))

    # -----------------------------------------------------------------
    # 3. 页面骨架与关键组件文件完整性
    # -----------------------------------------------------------------
    print("\n[测试项 3/4] 验证页面骨架与关键组件文件 ...")
    required_files = [
        "js/views/auth/auth.js",
        "js/views/common/classes.js",
        "js/views/teacher/workbench.js",
        "js/views/teacher/dashboard.js",
        "js/views/student/assignments.js",
        "js/views/student/workbench.js",
        "js/views/student/training.js",
        "js/components/assistant/assistant.js",
        "js/components/editor/editor.js",
        "js/components/media/charts.js",
        "js/components/media/markdown.js",
    ]
    missing = [item for item in required_files if not (UI_DIR / item).exists()]
    check("登录、教师、学生、AI 助手等关键视图齐全", not missing, f"missing={missing}")

    index_html = (UI_DIR / "index.html").read_text(encoding="utf-8")
    check("首页包含 toast / overlay / app 挂载点",
          all(token in index_html for token in ("id=\"app\"", "id=\"overlay-root\"", "id=\"toast-root\"")))

    # -----------------------------------------------------------------
    # 4. 无头浏览器真实渲染冒烟
    # -----------------------------------------------------------------
    print("\n[测试项 4/4] 无头浏览器渲染登录页冒烟 ...")
    chrome = find_chrome()
    if not chrome:
        print("  [SKIP] 未检测到 Chrome/Edge，跳过真实渲染冒烟")
    else:
        engine.dispose()
        if SERVER_DB_FILE.exists():
            try:
                SERVER_DB_FILE.unlink()
            except Exception:
                pass

        port = free_port()
        server_env = os.environ.copy()
        server_env["DATABASE_URL"] = f"sqlite:///{SERVER_DB_FILE}"
        server_env["SEED_DEMO_ACCOUNTS"] = "true"
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app",
             "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
            cwd=str(PROJECT_ROOT),
            env=server_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        base_url = f"http://127.0.0.1:{port}"
        ready = False
        try:
            for _ in range(80):
                try:
                    with urllib.request.urlopen(f"{base_url}/api/v1/system/status", timeout=0.5) as resp:
                        if resp.status == 200:
                            ready = True
                            break
                except Exception:
                    time.sleep(0.25)
            check("FastAPI 服务成功启动并响应探针状态", ready)

            if ready:
                chrome_profile = PROJECT_ROOT / "storage" / "chrome_profile"
                shutil.rmtree(chrome_profile, ignore_errors=True)
                chrome_profile.mkdir(parents=True, exist_ok=True)
                harness_files = []
                try:
                    dom = chrome_dump(chrome, f"{base_url}/ui/", chrome_profile)
                    check("无头浏览器完成登录页渲染",
                          "登录工作台" in dom and "CourseJudge" in dom,
                          f"dom_prefix={dom[:220]}")
                    check("登录页未停留在启动加载屏",
                          "正在加载智能判题工作台" not in dom)

                    # 教师登录态：利用临时跳板页写入 token 后进入工作区
                    teacher_token = login_token(base_url, "teacher", "123456")
                    teacher_harness = UI_DIR / "__cj_test_login_teacher.html"
                    teacher_harness.write_text(
                        "<!doctype html><meta charset='utf-8'><script>"
                        f"localStorage.setItem('coursejudge_token', {teacher_token!r});"
                        "location.replace('/ui/#/teacher/classes');</script>",
                        encoding="utf-8",
                    )
                    harness_files.append(teacher_harness)
                    teacher_dom = chrome_dump(chrome, f"{base_url}/ui/{teacher_harness.name}", chrome_profile)
                    check("教师登录态渲染班级大厅与导航",
                          "班级大厅" in teacher_dom and "作业工作台" in teacher_dom,
                          f"dom_prefix={teacher_dom[:220]}")

                    # 学生登录态
                    student_token = login_token(base_url, "student", "123456")
                    student_harness = UI_DIR / "__cj_test_login_student.html"
                    student_harness.write_text(
                        "<!doctype html><meta charset='utf-8'><script>"
                        f"localStorage.setItem('coursejudge_token', {student_token!r});"
                        "location.replace('/ui/#/student/assignments');</script>",
                        encoding="utf-8",
                    )
                    harness_files.append(student_harness)
                    student_dom = chrome_dump(chrome, f"{base_url}/ui/{student_harness.name}", chrome_profile)
                    check("学生登录态渲染我的作业与强化训练导航",
                          "我的作业" in student_dom and "强化训练" in student_dom,
                          f"dom_prefix={student_dom[:220]}")

                    # 学生做题工作台：通过 API 造数据后真实渲染 Monaco 编辑器
                    now = datetime.now(timezone.utc)
                    clazz = api_json(base_url, "POST", "/classes", teacher_token,
                                     {"name": "第五阶段验收班"})
                    assignment = api_json(base_url, "POST", "/assignments", teacher_token, {
                        "class_id": clazz["id"],
                        "title": "第五阶段验收作业",
                        "type": "practice",
                        "start_time": now.isoformat(),
                        "end_time": (now + timedelta(days=1)).isoformat(),
                        "problems": [{
                            "title": "两数之和",
                            "description": "输入两个整数 a 和 b，输出 a + b。",
                            "input_format": "一行两个整数",
                            "output_format": "一个整数",
                            "sample_input": "1 2",
                            "sample_output": "3",
                            "time_limit_ms": 1000,
                            "memory_limit_mb": 256,
                            "knowledge_tag": "基础输入输出",
                            "test_cases": [{
                                "input_data": "1 2",
                                "output_data": "3",
                                "score_weight": 100,
                            }],
                        }],
                    })
                    problems = api_json(base_url, "GET",
                                        f"/assignments/{assignment['id']}/problems", teacher_token)
                    problem_id = problems["problems"][0]["id"]
                    api_json(base_url, "POST", "/classes/join", student_token,
                             {"invite_code": clazz["invite_code"]})

                    workbench_harness = UI_DIR / "__cj_test_workbench.html"
                    workbench_harness.write_text(
                        "<!doctype html><meta charset='utf-8'><script>"
                        f"localStorage.setItem('coursejudge_token', {student_token!r});"
                        f"location.replace('/ui/#/student/workbench/{assignment['id']}/{problem_id}');</script>",
                        encoding="utf-8",
                    )
                    harness_files.append(workbench_harness)
                    workbench_dom = chrome_dump(
                        chrome, f"{base_url}/ui/{workbench_harness.name}", chrome_profile
                    )
                    check("学生做题工作台渲染题目与 Monaco 编辑器",
                          "两数之和" in workbench_dom
                          and ("monaco-editor" in workbench_dom or "code-fallback" in workbench_dom),
                          f"dom_prefix={workbench_dom[:260]}")

                    # 学生通过 API 提交一次 AC，供教师大屏聚合
                    api_json(base_url, "POST", "/judge/submit", student_token, {
                        "problem_id": problem_id,
                        "code": "#include <iostream>\nint main(){int a,b;std::cin>>a>>b;std::cout<<a+b;return 0;}",
                    })

                    # 教师作业工作台渲染
                    teacher_workbench = UI_DIR / "__cj_test_teacher_workbench.html"
                    teacher_workbench.write_text(
                        "<!doctype html><meta charset='utf-8'><script>"
                        f"localStorage.setItem('coursejudge_token', {teacher_token!r});"
                        f"location.replace('/ui/#/teacher/workbench/{clazz['id']}');</script>",
                        encoding="utf-8",
                    )
                    harness_files.append(teacher_workbench)
                    teacher_workbench_dom = chrome_dump(
                        chrome, f"{base_url}/ui/{teacher_workbench.name}", chrome_profile
                    )
                    check("教师作业工作台渲染编排表单与 AI 出题入口",
                          "编排新作业" in teacher_workbench_dom
                          and "AI 出题" in teacher_workbench_dom,
                          f"dom_prefix={teacher_workbench_dom[:260]}")

                    # 教师学情大屏渲染（含 ECharts canvas）
                    teacher_dashboard = UI_DIR / "__cj_test_teacher_dashboard.html"
                    teacher_dashboard.write_text(
                        "<!doctype html><meta charset='utf-8'><script>"
                        f"localStorage.setItem('coursejudge_token', {teacher_token!r});"
                        f"location.replace('/ui/#/teacher/dashboard/{clazz['id']}');</script>",
                        encoding="utf-8",
                    )
                    harness_files.append(teacher_dashboard)
                    teacher_dashboard_dom = chrome_dump(
                        chrome, f"{base_url}/ui/{teacher_dashboard.name}", chrome_profile
                    )
                    check("教师学情大屏渲染统计与 ECharts 图表",
                          "班级学情大屏" in teacher_dashboard_dom
                          and "分数段分布" in teacher_dashboard_dom
                          and "<canvas" in teacher_dashboard_dom,
                          f"dom_prefix={teacher_dashboard_dom[:260]}")
                    check("全局 AI 助手浮窗已挂载",
                          "assistant-fab" in teacher_dashboard_dom)
                except Exception as exc:
                    check(f"无头浏览器渲染失败: {exc}", False)
                finally:
                    for harness in harness_files:
                        try:
                            harness.unlink()
                        except OSError:
                            pass
        finally:
            server.terminate()
            try:
                server.wait(timeout=8)
            except Exception:
                server.kill()
            engine.dispose()
            # Windows 下 SQLite 句柄可能延迟释放，短暂重试确保测试库被清理
            for _ in range(10):
                if not SERVER_DB_FILE.exists():
                    break
                try:
                    SERVER_DB_FILE.unlink()
                    break
                except OSError:
                    time.sleep(0.2)
            shutil.rmtree(PROJECT_ROOT / "storage" / "chrome_profile", ignore_errors=True)

    # -----------------------------------------------------------------
    # 汇总
    # -----------------------------------------------------------------
    engine.dispose()
    if TEST_DB_FILE.exists():
        try:
            TEST_DB_FILE.unlink()
        except Exception:
            pass

    print("\n" + "=" * 70)
    print(f">>> Phase 5 验收测试完成: 通过 {PASSED} 项, 失败 {FAILED} 项 <<<")
    print("=" * 70)
    if FAILED > 0:
        sys.exit(1)
    print("\n✅ 所有验收项全部通过，Phase 5 桌面客户端界面与交互开发达标！")


if __name__ == "__main__":
    run_phase5_verification()