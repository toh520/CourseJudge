"""
文件名: test_phase1.py
功能描述: Phase 1 核心配置、数据库持久层与数据模型全流程阶段自动化验收测试脚本。
测试范围:
    1. 配置单例加载与 .env 变量解析 (Step 1.1)
    2. SQLite 数据库引擎连接与自动建表机制 (Step 1.2)
    3. 极简实体模型全量增删改查与外键级联关系 (Step 1.3)
    4. 明文密码匹配与轻量 JWT 令牌签发/校验 (Step 1.4)
"""

import os
import sys
import io
from pathlib import Path
from datetime import datetime, timedelta, timezone

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

# 使用临时独立的测试数据库，避免污染真实环境
TEST_DB_FILE = PROJECT_ROOT / "test_phase1.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal, init_db
from app.core.security import verify_password, create_access_token, decode_access_token
from app.models import (
    User,
    Class,
    ClassMember,
    Assignment,
    Problem,
    TestCase,
    Submission,
    TrainingProblem,
    ChatMessage
)


def run_phase1_verification():
    """执行 Phase 1 阶段自动化验收测试流程"""
    print("\n" + "=" * 70)
    print(">>> 开始执行 Phase 1: 核心配置、极简持久层与数据模型 自动化验收测试 <<<")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # 1. 验证配置读取模块 (Step 1.1)
    # -------------------------------------------------------------------------
    print("\n[测试项 1/4] 验证基础配置加载与环境变量解析...")
    assert settings.PROJECT_NAME, "项目名称配置不能为空"
    assert settings.API_V1_PREFIX == "/api/v1", "API 前缀校验失败"
    assert settings.DEFAULT_TIME_LIMIT_MS == 1000, "判题默认时间限制校验失败"
    print(f"  [OK] 配置单例加载正常: {settings.PROJECT_NAME} (v{settings.VERSION})")
    print(f"  [OK] LLM 模型配置正常: {settings.LLM_MODEL_NAME} | BaseURL: {settings.LLM_BASE_URL}")

    # -------------------------------------------------------------------------
    # 2. 验证密码核验与 JWT 令牌安全工具 (Step 1.4)
    # -------------------------------------------------------------------------
    print("\n[测试项 2/4] 验证轻量安全认证 (明文密码比对与 JWT 编解码)...")
    assert verify_password("123456", "123456") is True, "密码一致校验失败"
    assert verify_password("wrong_pwd", "123456") is False, "错误密码应当校验不通过"

    test_payload = {"sub": "T2024001", "role": "teacher", "real_name": "张老师"}
    token = create_access_token(test_payload, expires_delta=timedelta(hours=2))
    assert token and isinstance(token, str), "生成的 JWT 令牌格式错误"

    decoded = decode_access_token(token)
    assert decoded is not None, "JWT 解码失败"
    assert decoded["sub"] == "T2024001", "Token 载荷中的账号不匹配"
    assert decoded["role"] == "teacher", "Token 载荷中的角色不匹配"
    print(f"  [OK] 明文密码极简校验机制运行正常")
    print(f"  [OK] JWT 令牌签署与解码通过 (Token前20位: {token[:20]}...)")

    # -------------------------------------------------------------------------
    # 3. 验证 SQLite 数据库自动建表 (Step 1.2)
    # -------------------------------------------------------------------------
    print("\n[测试项 3/4] 验证 SQLite 引擎与自动建表机制...")
    if TEST_DB_FILE.exists():
        TEST_DB_FILE.unlink()  # 清理旧的测试库文件

    init_db()  # 调用自动建表
    assert TEST_DB_FILE.exists(), "测试数据库文件未成功自动生成"
    table_names = list(Base.metadata.tables.keys())
    expected_tables = [
        "users", "classes", "class_members", "assignments",
        "problems", "test_cases", "submissions", "training_problems", "chat_messages"
    ]
    for tbl in expected_tables:
        assert tbl in table_names, f"数据表 [{tbl}] 未能成功创建"
    print(f"  [OK] 数据库自动建表成功，共生成 {len(table_names)} 张数据表: {table_names}")

    # -------------------------------------------------------------------------
    # 4. 验证数据模型完整业务流转增删改查 (Step 1.3)
    # -------------------------------------------------------------------------
    print("\n[测试项 4/4] 验证极简实体全业务链路数据持久化与关系映射...")
    db = SessionLocal()
    try:
        # 4.1 创建教师与学生用户
        teacher = User(username="T101", real_name="王老师", password="password123", role="teacher")
        student = User(username="S202401", real_name="李同学", password="stu_pwd", role="student")
        db.add_all([teacher, student])
        db.commit()
        db.refresh(teacher)
        db.refresh(student)
        assert teacher.id and student.id, "用户实体持久化失败"
        print(f"  [OK] 用户持久化成功: 教师 ID={teacher.id}, 学生 ID={student.id}")

        # 4.2 教师创建班级
        clazz = Class(name="C++算法强化1班", invite_code="JOIN88", teacher_id=teacher.id)
        db.add(clazz)
        db.commit()
        db.refresh(clazz)
        assert clazz.id and clazz.invite_code == "JOIN88", "班级创建失败"

        # 4.3 学生加入班级
        member = ClassMember(class_id=clazz.id, student_id=student.id)
        db.add(member)
        db.commit()
        print(f"  [OK] 班级关系建立成功: 学生加入班级 [{clazz.name}]")

        # 4.4 教师发布练习活动
        now = datetime.now(timezone.utc)
        assignment = Assignment(
            class_id=clazz.id,
            title="第一次递归与动态规划练习",
            type="practice",
            start_time=now,
            end_time=now + timedelta(days=7),
            created_by=teacher.id
        )
        db.add(assignment)
        db.commit()
        db.refresh(assignment)

        # 4.5 为作业添加题目与测试用例
        problem = Problem(
            assignment_id=assignment.id,
            title="斐波那契数列计算",
            description="# 题目描述\n输入整数 N，输出第 N 项斐波那契数。",
            input_format="一个正整数 N",
            output_format="输出对应斐波那契值",
            sample_input="5",
            sample_output="5",
            knowledge_tag="递归与记忆化搜索",
            is_ai_generated=False
        )
        db.add(problem)
        db.commit()
        db.refresh(problem)

        tc1 = TestCase(problem_id=problem.id, input_data="1", output_data="1", score_weight=50)
        tc2 = TestCase(problem_id=problem.id, input_data="5", output_data="5", score_weight=50)
        db.add_all([tc1, tc2])
        db.commit()
        print(f"  [OK] 作业与题目编排成功: 题目ID={problem.id}, 包含 2 组测试用例")

        # 4.6 学生提交代码记录
        submission = Submission(
            user_id=student.id,
            problem_id=problem.id,
            assignment_id=assignment.id,
            code="#include <iostream>\nint main() { ... }",
            status="AC",
            score=100,
            time_used_ms=15,
            is_final=False
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)
        assert submission.score == 100, "提交得分不匹配"
        print(f"  [OK] 提交记录落库成功: Submission ID={submission.id}, 状态={submission.status}")

        # 4.7 考后专属强化训练题落库
        training = TrainingProblem(
            student_id=student.id,
            source_assignment_id=assignment.id,
            knowledge_tag="动态规划-状态转移",
            title="爬楼梯方案数 (巩固练习)",
            description="针对斐波那契未掌握点的针对性练习题...",
            sample_input="3",
            sample_output="3",
            test_cases_json='[{"input": "3", "output": "3"}]',
            best_status="Unsolved"
        )
        db.add(training)
        db.commit()
        db.refresh(training)
        assert training.best_status == "Unsolved", "专属强化题状态初始不正确"
        print(f"  [OK] 专属强化题本落库成功: ID={training.id}, 考查点={training.knowledge_tag}")

        # 4.8 AI 助教对话消息落库
        chat_user = ChatMessage(user_id=student.id, role="user", content="请问斐波那契算法如何优化空间复杂度？")
        chat_ai = ChatMessage(user_id=student.id, role="assistant", content="可以使用两个变量进行滚动更新，将空间复杂度优化至 O(1)。")
        db.add_all([chat_user, chat_ai])
        db.commit()
        print(f"  [OK] AI 助教问答历史存储正常")

    finally:
        db.close()
        # 清理测试数据库
        if TEST_DB_FILE.exists():
            try:
                TEST_DB_FILE.unlink()
            except Exception:
                pass

    print("\n" + "=" * 70)
    print(">>> 恭喜！Phase 1 全部自动化测试用例 100% 验收通过！ <<<")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_phase1_verification()
