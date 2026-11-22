"""
文件名: seed.py
功能描述: 数据库种子数据管理与团队数据快照导入/导出同步器。
遵循规范: 
  1. 保证团队协作数据同步：通过纯文本 JSON 数据快照 (data_snapshot.json) 解决二进制 .db 无法在 Git 合并的痛点；
  2. 幂等性保障：数据导入时智能去重更新，不覆盖用户本地提交记录，开箱即用。
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.models import (
    User,
    Class,
    ClassMember,
    Assignment,
    Problem,
    TestCase,
    TrainingProblem,
)


def seed_demo_accounts() -> None:
    """
    在用户表为空时创建默认演示账号 (教师/学生)
    该函数是幂等的：只要数据库中已存在任意用户，就直接返回，不会覆盖真实数据。
    """
    if not settings.SEED_DEMO_ACCOUNTS:
        return

    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return

        db.add(User(
            username=settings.DEMO_TEACHER_USERNAME,
            real_name="演示教师",
            password=settings.DEMO_TEACHER_PASSWORD,
            role="teacher",
        ))
        db.add(User(
            username=settings.DEMO_STUDENT_USERNAME,
            real_name="演示学生",
            password=settings.DEMO_STUDENT_PASSWORD,
            role="student",
        ))
        db.commit()
    finally:
        db.close()


def seed_initial_demo_data() -> None:
    """
    初始化内置的演示教学数据 (演示班级、练习作业、示例题目与用例)
    当本地数据库尚无班级数据时自动执行，确保团队拉取后直接能体验做题、出题与大屏。
    """
    # 确保基础账号存在
    seed_demo_accounts()

    db = SessionLocal()
    try:
        # 如果已经有班级，则说明已有业务数据，无需重复灌入默认数据
        if db.query(Class).count() > 0:
            return

        teacher = db.query(User).filter(User.username == settings.DEMO_TEACHER_USERNAME).first()
        student = db.query(User).filter(User.username == settings.DEMO_STUDENT_USERNAME).first()
        if not teacher or not student:
            return

        # 1. 创建演示班级
        demo_class = Class(
            name="2026程序设计与算法强化1班",
            invite_code="CJ2026",
            teacher_id=teacher.id,
        )
        db.add(demo_class)
        db.commit()
        db.refresh(demo_class)

        # 2. 将演示学生加入该班级
        db.add(ClassMember(class_id=demo_class.id, student_id=student.id))

        # 3. 创建演示练习作业
        now = datetime.now(timezone.utc)
        assignment = Assignment(
            class_id=demo_class.id,
            title="第一次递归与动态规划专项练习",
            type="practice",
            start_time=now - timedelta(days=1),
            end_time=now + timedelta(days=30),
            created_by=teacher.id,
        )
        db.add(assignment)
        db.commit()
        db.refresh(assignment)

        # 4. 创建示例题目: 斐波那契数列计算
        problem = Problem(
            assignment_id=assignment.id,
            title="斐波那契数列计算",
            description=(
                "# 斐波那契数列计算\n\n"
                "## 题目描述\n"
                "已知斐波那契数列定义如下：\n"
                "- $F(1) = 1$\n"
                "- $F(2) = 1$\n"
                "- $F(N) = F(N-1) + F(N-2)$ (当 $N \\ge 3$)\n\n"
                "请编写 C++ 程序，输入正整数 $N$ ($1 \\le N \\le 40$)，输出对应的第 $N$ 项斐波那契数。"
            ),
            input_format="输入一个正整数 N。",
            output_format="输出一行一个整数，表示第 N 项斐波那契数的值。",
            sample_input="5",
            sample_output="5",
            time_limit_ms=1000,
            memory_limit_mb=256,
            knowledge_tag="递归与记忆化搜索",
            is_ai_generated=False,
        )
        db.add(problem)
        db.commit()
        db.refresh(problem)

        # 5. 添加测试用例
        tc1 = TestCase(problem_id=problem.id, input_data="1", output_data="1", score_weight=30)
        tc2 = TestCase(problem_id=problem.id, input_data="5", output_data="5", score_weight=30)
        tc3 = TestCase(problem_id=problem.id, input_data="10", output_data="55", score_weight=40)
        db.add_all([tc1, tc2, tc3])

        # 6. 为学生添加 1 道考后专属强化训练题示例
        training = TrainingProblem(
            student_id=student.id,
            source_assignment_id=assignment.id,
            knowledge_tag="动态规划-状态转移",
            title="爬楼梯方案数 (专项巩固)",
            description=(
                "# 爬楼梯方案数\n\n"
                "假设你正在爬楼梯。需要 $n$ 阶你才能到达楼顶。\n"
                "每次你可以爬 1 或 2 个台阶。你有多少种不同的方法可以爬到楼顶呢？"
            ),
            sample_input="3",
            sample_output="3",
            test_cases_json=json.dumps([
                {"input": "2", "output": "2"},
                {"input": "3", "output": "3"},
                {"input": "5", "output": "8"}
            ], ensure_ascii=False),
            best_status="Unsolved",
        )
        db.add(training)
        db.commit()
    finally:
        db.close()


def export_snapshot(output_file: Optional[str] = None) -> Dict[str, Any]:
    """
    将本地数据库的核心业务数据导出为纯文本 JSON 数据快照
    用于团队协作共享：团队成员录题后导出此文件并提交 Git，队友拉取后一键导入。
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    snapshot_path = Path(output_file) if output_file else project_root / settings.DATA_SNAPSHOT_FILE
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        # 导出用户 (保留基础信息与角色)
        users_data = []
        for u in db.query(User).all():
            users_data.append({
                "username": u.username,
                "real_name": u.real_name,
                "password": u.password,
                "role": u.role,
            })

        # 导出班级与成员关系
        classes_data = []
        for c in db.query(Class).all():
            members_usernames = [m.student.username for m in c.members if m.student]
            classes_data.append({
                "name": c.name,
                "invite_code": c.invite_code,
                "teacher_username": c.teacher.username if c.teacher else settings.DEMO_TEACHER_USERNAME,
                "members": members_usernames,
            })

        # 导出作业、题目与用例
        assignments_data = []
        for a in db.query(Assignment).all():
            problems_data = []
            for p in a.problems:
                cases_data = [
                    {
                        "input_data": tc.input_data,
                        "output_data": tc.output_data,
                        "score_weight": tc.score_weight,
                    }
                    for tc in p.test_cases
                ]
                problems_data.append({
                    "title": p.title,
                    "description": p.description,
                    "input_format": p.input_format,
                    "output_format": p.output_format,
                    "sample_input": p.sample_input,
                    "sample_output": p.sample_output,
                    "time_limit_ms": p.time_limit_ms,
                    "memory_limit_mb": p.memory_limit_mb,
                    "knowledge_tag": p.knowledge_tag,
                    "is_ai_generated": p.is_ai_generated,
                    "test_cases": cases_data,
                })

            assignments_data.append({
                "class_invite_code": a.clazz.invite_code if a.clazz else None,
                "title": a.title,
                "type": a.type,
                "start_time": a.start_time.isoformat() if a.start_time else None,
                "end_time": a.end_time.isoformat() if a.end_time else None,
                "creator_username": a.creator.username if a.creator else settings.DEMO_TEACHER_USERNAME,
                "problems": problems_data,
            })

        snapshot_content = {
            "version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "users": users_data,
            "classes": classes_data,
            "assignments": assignments_data,
        }

        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(snapshot_content, f, ensure_ascii=False, indent=2)

        return snapshot_content
    finally:
        db.close()


def import_snapshot(input_file: Optional[str] = None) -> Dict[str, int]:
    """
    读取 JSON 数据快照，幂等合并入本地 SQLite 数据库
    如果记录已存在则平滑跳过或更新，保证团队成员拉取代码后数据无损同步。
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    snapshot_path = Path(input_file) if input_file else project_root / settings.DATA_SNAPSHOT_FILE

    if not snapshot_path.exists():
        # 若快照文件不存在，则降级灌入默认内置种子数据
        seed_initial_demo_data()
        return {"users": 0, "classes": 0, "assignments": 0, "problems": 0}

    with open(snapshot_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    db = SessionLocal()
    stats = {"users": 0, "classes": 0, "assignments": 0, "problems": 0}
    try:
        # 1. 同步用户
        user_cache: Dict[str, User] = {u.username: u for u in db.query(User).all()}
        for u_dict in data.get("users", []):
            username = u_dict["username"]
            if username not in user_cache:
                new_user = User(
                    username=username,
                    real_name=u_dict.get("real_name", username),
                    password=u_dict.get("password", "123456"),
                    role=u_dict.get("role", "student"),
                )
                db.add(new_user)
                db.commit()
                db.refresh(new_user)
                user_cache[username] = new_user
                stats["users"] += 1

        # 2. 同步班级与成员
        class_cache: Dict[str, Class] = {c.invite_code: c for c in db.query(Class).all()}
        for c_dict in data.get("classes", []):
            code = c_dict["invite_code"]
            teacher = user_cache.get(c_dict.get("teacher_username"))
            if not teacher:
                continue

            if code not in class_cache:
                new_class = Class(
                    name=c_dict["name"],
                    invite_code=code,
                    teacher_id=teacher.id,
                )
                db.add(new_class)
                db.commit()
                db.refresh(new_class)
                class_cache[code] = new_class
                stats["classes"] += 1
            else:
                new_class = class_cache[code]

            # 同步班级成员
            existing_members = {m.student_id for m in new_class.members}
            for student_username in c_dict.get("members", []):
                student_user = user_cache.get(student_username)
                if student_user and student_user.id not in existing_members:
                    db.add(ClassMember(class_id=new_class.id, student_id=student_user.id))
                    existing_members.add(student_user.id)
            db.commit()

        # 3. 同步作业、题目与用例
        for a_dict in data.get("assignments", []):
            class_code = a_dict.get("class_invite_code")
            target_class = class_cache.get(class_code)
            if not target_class:
                continue

            creator = user_cache.get(a_dict.get("creator_username")) or target_class.teacher
            title = a_dict["title"]

            # 查找是否已有同名作业
            assignment = (
                db.query(Assignment)
                .filter(Assignment.class_id == target_class.id, Assignment.title == title)
                .first()
            )
            if not assignment:
                start_dt = (
                    datetime.fromisoformat(a_dict["start_time"])
                    if a_dict.get("start_time")
                    else datetime.now(timezone.utc)
                )
                end_dt = (
                    datetime.fromisoformat(a_dict["end_time"])
                    if a_dict.get("end_time")
                    else datetime.now(timezone.utc) + timedelta(days=30)
                )
                assignment = Assignment(
                    class_id=target_class.id,
                    title=title,
                    type=a_dict.get("type", "practice"),
                    start_time=start_dt,
                    end_time=end_dt,
                    created_by=creator.id,
                )
                db.add(assignment)
                db.commit()
                db.refresh(assignment)
                stats["assignments"] += 1

            # 题目同步
            existing_problems = {p.title: p for p in assignment.problems}
            for p_dict in a_dict.get("problems", []):
                p_title = p_dict["title"]
                if p_title not in existing_problems:
                    new_problem = Problem(
                        assignment_id=assignment.id,
                        title=p_title,
                        description=p_dict["description"],
                        input_format=p_dict.get("input_format"),
                        output_format=p_dict.get("output_format"),
                        sample_input=p_dict.get("sample_input"),
                        sample_output=p_dict.get("sample_output"),
                        time_limit_ms=p_dict.get("time_limit_ms", 1000),
                        memory_limit_mb=p_dict.get("memory_limit_mb", 256),
                        knowledge_tag=p_dict.get("knowledge_tag"),
                        is_ai_generated=p_dict.get("is_ai_generated", False),
                    )
                    db.add(new_problem)
                    db.commit()
                    db.refresh(new_problem)
                    stats["problems"] += 1

                    # 添加测试用例
                    for tc_dict in p_dict.get("test_cases", []):
                        db.add(TestCase(
                            problem_id=new_problem.id,
                            input_data=tc_dict["input_data"],
                            output_data=tc_dict["output_data"],
                            score_weight=tc_dict.get("score_weight", 10),
                        ))
                    db.commit()

        return stats
    finally:
        db.close()


def main():
    """CLI 命令行入口，方便批处理脚本直接调度"""
    parser = argparse.ArgumentParser(description="CourseJudge 数据库种子与数据快照同步工具")
    parser.add_argument("--export", action="store_true", help="将当前本地数据库导出为团队共享数据快照 JSON")
    parser.add_argument("--import", dest="import_cmd", action="store_true", help="将共享数据快照导入到本地数据库")
    parser.add_argument("--sync", action="store_true", help="智能同步 (若本地无数据则完整导入，有数据则增量合并)")
    parser.add_argument("--init", action="store_true", help="仅初始化演示账号与初始题面")
    parser.add_argument("--file", type=str, default=None, help="自定义快照文件路径")

    args = parser.parse_args()

    # 先确保表结构存在
    init_db()

    if args.export:
        print("[CourseJudge] 正在导出本地数据快照...")
        res = export_snapshot(args.file)
        print(f"[CourseJudge] 导出成功！包含 {len(res['users'])} 个用户, {len(res['classes'])} 个班级, {len(res['assignments'])} 个作业。")
    elif args.import_cmd or args.sync:
        print("[CourseJudge] 正在从数据快照同步到本地数据库...")
        stats = import_snapshot(args.file)
        print(f"[CourseJudge] 同步完成！新增用户: {stats['users']}, 班级: {stats['classes']}, 作业: {stats['assignments']}, 题目: {stats['problems']}")
    else:
        print("[CourseJudge] 正在初始化默认演示账号与数据...")
        seed_initial_demo_data()
        print("[CourseJudge] 演示数据初始化完成！")


if __name__ == "__main__":
    main()


# 提供 sync_snapshot 语义别名，兼容导入调用
sync_snapshot = import_snapshot
