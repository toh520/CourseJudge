# -*- coding: utf-8 -*-
"""
文件名: test_phase4.py
功能描述: Phase 4 业务逻辑 RESTful API 全链路阶段自动化验收测试脚本。
测试范围:
    1. 登录鉴权与当前用户 (Step 4.2 auth)
    2. 教师建班 / 学生邀请码加入 / 班级名册 (Step 4.3 classes)
    3. 作业发布(练习/考试) 与题目读取 (Step 4.4 assignments)
    4. 自测运行 与 正式提交判定(练习多次/考试单次锁定) (Step 4.5 judge)
    5. 专属强化训练题列表/详情/提交 (Step 4.6 training)
    6. 作业学情与薄弱知识点大屏聚合 (Step 4.7 dashboard)
    7. LLM 路由未配置 API Key 时统一返回 503 (Step 4.8 llm)
遵循规范: 与 test_phase1.py 一致，采用"临时独立数据库 + 脚本流" 执行方式，不使用 pytest。
"""
import io
import sys
import json
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

# 在 Windows 终端下统一标准输出为 UTF-8，防止 GBK 编码异常
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# 将 project 目录加入 Python 搜索路径，确保可直接导入 app 包
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 使用临时独立测试数据库，避免污染真实环境；每次运行前清理保证可重复执行
TEST_DB_FILE = PROJECT_ROOT / "test_phase4.db"
if TEST_DB_FILE.exists():
    try:
        TEST_DB_FILE.unlink()
    except Exception:
        pass
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    User,
    Class,
    Assignment,
    Problem,
    TestCase,
    TrainingProblem,
)

client = TestClient(app)

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


def _auth_headers(token: str) -> dict:
    """构造 Bearer 鉴权请求头"""
    return {"Authorization": f"Bearer {token}"}


def _ac_code() -> str:
    """一个输出 OK 的正确 C++ 程序（用于 AC 判定）"""
    return (
        "#include <iostream>\n"
        "using namespace std;\n"
        "int main(){ cout << \"OK\"; return 0; }"
    )


def _seed_users() -> None:
    """预置教师与两名学生测试账号"""
    db = SessionLocal()
    try:
        db.add(User(username="teacher1", real_name="王老师", password="123456", role="teacher"))
        db.add(User(username="student1", real_name="小明", password="123456", role="student"))
        db.add(User(username="student2", real_name="小红", password="123456", role="student"))
        db.commit()
    finally:
        db.close()


def _add_problem(assignment_id: int, tag: str, case_output: str = "OK", weight: int = 100) -> int:
    """直接向数据库写入一道题与其测试用例，返回题目 ID"""
    db = SessionLocal()
    try:
        problem = Problem(
            assignment_id=assignment_id,
            title=f"输出{case_output}",
            description="读入任意内容并输出固定串",
            input_format="",
            output_format=case_output,
            sample_input="1",
            sample_output=case_output,
            time_limit_ms=1000,
            memory_limit_mb=256,
            knowledge_tag=tag,
            is_ai_generated=False,
        )
        db.add(problem)
        db.flush()
        db.add(TestCase(
            problem_id=problem.id,
            input_data="x",
            output_data=case_output,
            score_weight=weight,
        ))
        db.commit()
        return problem.id
    finally:
        db.close()


def _add_training(user_id: int, source_assignment_id: int, tag: str) -> int:
    """直接写入一道专属强化训练题并返回其 ID"""
    db = SessionLocal()
    try:
        cases = [{"input_data": "x", "output_data": "OK", "score_weight": 100}]
        training = TrainingProblem(
            student_id=user_id,
            source_assignment_id=source_assignment_id,
            knowledge_tag=tag,
            title="强化-输出OK",
            description="针对薄弱点输出OK的强化题",
            sample_input="1",
            sample_output="OK",
            test_cases_json=json.dumps(cases, ensure_ascii=False),
            best_status="Unsolved",
        )
        db.add(training)
        db.commit()
        return training.id
    finally:
        db.close()


def run_phase4_verification() -> None:
    """执行 Phase 4 阶段自动化验收测试流程"""
    print("\n" + "=" * 70)
    print(">>> 开始执行 Phase 4: 业务逻辑 RESTful API 与控制层 自动化验收测试 <<<")
    print("=" * 70)

    # ---------------------------------------------------------------------
    # 0. 预置用户
    # ---------------------------------------------------------------------
    _seed_users()

    # ---------------------------------------------------------------------
    # 1. 登录鉴权与当前用户 (Step 4.2)
    # ---------------------------------------------------------------------
    print("\n[测试项 1/9] 登录鉴权与当前用户 ...")
    r = client.post("/api/v1/auth/login", json={"username": "teacher1", "password": "123456"})
    check("教师登录成功返回 200", r.status_code == 200, f"status={r.status_code}")
    token_t = r.json().get("access_token", "")
    check("登录应答携带 access_token 与 user.role=teacher",
          bool(token_t) and r.json().get("user", {}).get("role") == "teacher")

    r = client.post("/api/v1/auth/login", json={"username": "student1", "password": "123456"})
    token_s1 = r.json().get("access_token", "")
    check("学生1登录成功", r.status_code == 200 and bool(token_s1))

    r = client.post("/api/v1/auth/login", json={"username": "student2", "password": "123456"})
    token_s2 = r.json().get("access_token", "")
    check("学生2登录成功", r.status_code == 200 and bool(token_s2))

    r = client.post("/api/v1/auth/login", json={"username": "teacher1", "password": "wrong"})
    check("错误密码登录被拒 401", r.status_code == 401)

    r = client.get("/api/v1/auth/me", headers=_auth_headers(token_t))
    check("auth/me 返回当前教师真实姓名",
          r.status_code == 200 and r.json().get("real_name") == "王老师")

    r = client.get("/api/v1/auth/me")
    check("无 token 访问受保护接口返回 401", r.status_code == 401)

    # ---------------------------------------------------------------------
    # 2. 班级创建/加入/名册 (Step 4.3)
    # ---------------------------------------------------------------------
    print("\n[测试项 2/9] 班级管理 ...")
    r = client.post("/api/v1/classes", json={"name": "2024计科1班"}, headers=_auth_headers(token_t))
    check("教师建班成功 200/201", r.status_code in (200, 201), f"status={r.status_code}")
    class_id = r.json().get("id")
    invite_code = r.json().get("invite_code")
    check("建班返回 6 位邀请码", bool(invite_code) and len(invite_code) == 6)

    r = client.post("/api/v1/classes", json={"name": "越权班"}, headers=_auth_headers(token_s1))
    check("普通学生建班被拒 403", r.status_code == 403)

    r = client.post("/api/v1/classes/join", json={"invite_code": invite_code}, headers=_auth_headers(token_s1))
    check("学生1用邀请码加入成功", r.status_code == 200, f"status={r.status_code}")

    r = client.post("/api/v1/classes/join", json={"invite_code": invite_code}, headers=_auth_headers(token_s1))
    check("重复加入返回 409", r.status_code == 409)

    r = client.post("/api/v1/classes/join", json={"invite_code": "XXXXXX"}, headers=_auth_headers(token_s2))
    check("无效邀请码加入返回 404", r.status_code == 404)

    r = client.post("/api/v1/classes/join", json={"invite_code": invite_code}, headers=_auth_headers(token_s2))
    check("学生2正常加入成功", r.status_code == 200)

    r = client.get(f"/api/v1/classes/{class_id}/students", headers=_auth_headers(token_t))
    check("教师查看名册返回 2 名学生",
          r.status_code == 200 and r.json().get("student_count") == 2)

    # ---------------------------------------------------------------------
    # 3. 作业/考试发布与题目读取 (Step 4.4)
    # ---------------------------------------------------------------------
    print("\n[测试项 3/9] 作业与考试发布 ...")
    now = datetime.now(timezone.utc)
    r = client.post("/api/v1/assignments", json={
        "class_id": class_id,
        "title": "第三周练习",
        "type": "practice",
        "start_time": now.isoformat(),
        "end_time": (now + timedelta(days=7)).isoformat(),
    }, headers=_auth_headers(token_t))
    check("教师发布练习作业成功 200/201", r.status_code in (200, 201), f"status={r.status_code}")
    practice_id = r.json().get("id")
    check("练习作业类型为 practice", r.json().get("type") == "practice")

    r = client.post("/api/v1/assignments", json={
        "class_id": class_id,
        "title": "期中考试",
        "type": "exam",
    }, headers=_auth_headers(token_t))
    check("教师发布考试成功 200/201", r.status_code in (200, 201), f"status={r.status_code}")
    exam_id = r.json().get("id")
    check("考试类型为 exam", r.json().get("type") == "exam")

    r = client.post("/api/v1/assignments", json={
        "class_id": class_id,
        "title": "非法类型",
        "type": "homework",
    }, headers=_auth_headers(token_t))
    check("非法作业类型被拒 400", r.status_code == 400)

    r = client.post("/api/v1/assignments", json={
        "class_id": class_id,
        "title": "学生越权发作业",
        "type": "practice",
    }, headers=_auth_headers(token_s1))
    check("学生发布作业被拒 403", r.status_code == 403)

    problem_p = _add_problem(practice_id, "基础输入输出")
    problem_e = _add_problem(exam_id, "指针基础", case_output="OK")

    r = client.get(f"/api/v1/assignments/{practice_id}", headers=_auth_headers(token_s1))
    check("练习作业详情 problem_count>=1", r.status_code == 200 and r.json().get("problem_count") >= 1)

    r = client.get(f"/api/v1/assignments/{practice_id}/problems", headers=_auth_headers(token_t))
    check("练习作业题目列表包含 1 题",
          r.status_code == 200 and r.json().get("problem_count") == 1)

    # ---------------------------------------------------------------------
    # 4. 自测运行与正式提交 (Step 4.5)
    # ---------------------------------------------------------------------
    print("\n[测试项 4/9] 自测运行与正式提交判定 ...")
    r = client.post("/api/v1/judge/run-test", json={
        "problem_id": problem_p,
        "code": _ac_code(),
        "input_data": "x",
    }, headers=_auth_headers(token_s1))
    check("合法自测运行返回 200 且 AC",
          r.status_code == 200 and r.json().get("execution_status") == "AC",
          f"status={r.status_code} exec={r.json().get('execution_status') if r.status_code==200 else ''}")

    r = client.post("/api/v1/judge/run-test", json={
        "problem_id": 9999,
        "code": _ac_code(),
    }, headers=_auth_headers(token_s1))
    check("未知题目自测返回 404", r.status_code == 404)

    r = client.post("/api/v1/judge/submit", json={
        "problem_id": problem_p,
        "code": _ac_code(),
    }, headers=_auth_headers(token_s1))
    check("练习作业首次提交 AC 且不锁定",
          r.status_code == 200 and r.json().get("status") == "AC"
          and r.json().get("score") == 100 and r.json().get("is_final") is False,
          f"status={r.status_code} body={r.json() if r.status_code==200 else ''}")

    r = client.post("/api/v1/judge/submit", json={
        "problem_id": problem_p,
        "code": _ac_code(),
    }, headers=_auth_headers(token_s1))
    check("练习作业允许重复提交 200", r.status_code == 200)

    r = client.post("/api/v1/judge/submit", json={
        "problem_id": problem_e,
        "code": _ac_code(),
    }, headers=_auth_headers(token_s1))
    check("考试首次提交 AC 并锁定 is_final",
          r.status_code == 200 and r.json().get("status") == "AC"
          and r.json().get("is_final") is True,
          f"status={r.status_code} body={r.json() if r.status_code==200 else ''}")

    r = client.post("/api/v1/judge/submit", json={
        "problem_id": problem_e,
        "code": _ac_code(),
    }, headers=_auth_headers(token_s1))
    check("考试重复提交被拒 409", r.status_code == 409)

    # ---------------------------------------------------------------------
    # 5. 专属强化训练题 (Step 4.6)
    # ---------------------------------------------------------------------
    print("\n[测试项 5/9] 专属强化训练题 ...")
    r = client.get("/api/v1/training", headers=_auth_headers(token_s1))
    check("初始训练题列表为空", r.status_code == 200 and r.json().get("training_count") == 0)

    training_id = _add_training(_get_user_id("student1"), practice_id, "基础输入输出")
    r = client.get("/api/v1/training", headers=_auth_headers(token_s1))
    check("写入训练题后列表返回 1 条", r.status_code == 200 and r.json().get("training_count") == 1)

    r = client.get(f"/api/v1/training/{training_id}", headers=_auth_headers(token_s1))
    check("训练题详情可读且含知识点",
          r.status_code == 200 and r.json().get("knowledge_tag") == "基础输入输出")

    r = client.post(f"/api/v1/training/{training_id}/submit", json={"code": _ac_code()},
                    headers=_auth_headers(token_s1))
    check("训练题提交 AC 并回写 best_status",
          r.status_code == 200 and r.json().get("best_status") == "AC",
          f"status={r.status_code} body={r.json() if r.status_code==200 else ''}")

    r = client.get(f"/api/v1/training/{training_id}", headers=_auth_headers(token_s2))
    check("他人训练题越权访问被拒 403", r.status_code == 403)

    # ---------------------------------------------------------------------
    # 6. 学情与薄弱知识点大屏聚合 (Step 4.7)
    # ---------------------------------------------------------------------
    print("\n[测试项 6/9] 作业学情与薄弱知识点大屏 ...")
    r = client.get(f"/api/v1/assignments/{practice_id}/dashboard", headers=_auth_headers(token_t))
    check("教师查看练习学情大屏 200", r.status_code == 200, f"status={r.status_code}")
    dash = r.json() if r.status_code == 200 else {}
    check("及格率按满分提交计 100%", dash.get("pass_rate") == 100.0)
    check("分数段聚合命中 80-100", any(b.get("band") == "80-100" and b.get("count") >= 1
                                          for b in dash.get("score_bands", [])))
    check("各题通过率聚合含 AC", all(ps.get("ac_rate") == 100.0
                                       for ps in dash.get("problem_stats", []) if ps.get("submissions") > 0))

    r = client.get(f"/api/v1/assignments/{practice_id}/dashboard", headers=_auth_headers(token_s1))
    check("学生越权查看学情大屏被拒 403", r.status_code == 403)

    # ---------------------------------------------------------------------
    # 7. LLM 路由未配置 Key 统一返回 503 (Step 4.8)
    # ---------------------------------------------------------------------
    print("\n[测试项 7/9] LLM 路由未配置 Key 守卫 ...")
    r = client.post("/api/v1/llm/generate-problem", json={"intent": "求两数和"}, headers=_auth_headers(token_t))
    check("generate-problem 未配 key 返回 503", r.status_code == 503, f"status={r.status_code}")

    r = client.post("/api/v1/llm/generate-test-inputs", json={"problem_id": problem_p}, headers=_auth_headers(token_t))
    check("generate-test-inputs 未配 key 返回 503", r.status_code == 503)

    r = client.post("/api/v1/llm/diagnose", json={"assignment_id": practice_id}, headers=_auth_headers(token_t))
    check("diagnose 未配 key 返回 503", r.status_code == 503)

    r = client.post("/api/v1/llm/training", json={"weak_point": "指针"}, headers=_auth_headers(token_s1))
    check("llm/training 未配 key 返回 503", r.status_code == 503)

    r = client.post("/api/v1/llm/chat", json={"message": "解释递归"}, headers=_auth_headers(token_t))
    check("llm/chat 未配 key 返回 503", r.status_code == 503)

    # ---------------------------------------------------------------------
    # 8. 权限与路由健壮性
    # ---------------------------------------------------------------------
    print("\n[测试项 8/9] 权限与路由健壮性 ...")
    r = client.get("/api/v1/system/status")
    check("系统状态接口免登录可访问 200", r.status_code == 200)

    r = client.get("/")
    check("根路径返回服务信息", r.status_code == 200 and r.json().get("status") == "ok")

    r = client.get("/api/v1/assignments/999999", headers=_auth_headers(token_t))
    check("未知作业详情返回 404", r.status_code == 404)

    # ---------------------------------------------------------------------
    # 9. 汇总
    # ---------------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f">>> Phase 4 验收测试完成: 通过 {PASSED} 项, 失败 {FAILED} 项 <<<")
    print("=" * 70)
    if FAILED > 0:
        sys.exit(1)
    print("\n✅ 所有验收项全部通过，Phase 4 业务逻辑 RESTful API 开发达标！")


def _get_user_id(username: str) -> int:
    """按用户名取用户 ID（供训练题归属使用）"""
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == username).first()
        return u.id if u else 0
    finally:
        db.close()


if __name__ == "__main__":
    run_phase4_verification()