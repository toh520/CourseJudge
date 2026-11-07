"""
文件名: dashboard.py
功能描述: 教师端班级学情与弱点大屏聚合路由。针对某次作业/考试，聚合计算
          应交/实交人数、平均分、及格率、四段分数分布、各题通过率与薄弱知识点 Top。
遵循规范: 仅本班教师可查看；成绩按“每生每题最佳得分”计算，避免多题作业下
          用单题最高分误当整份作业成绩。
"""

from collections import defaultdict
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Assignment, Class, ClassMember, Problem, Submission, User
from app.api.deps import get_current_user

router = APIRouter()

# 及格线 (百分制)
_PASS_THRESHOLD = 60

# 四段分数分布标签 (与需求规格说明书保持一致)
_SCORE_BAND_LABELS = ("90-100", "80-89", "60-79", "0-59")


def _score_band(score: float) -> str:
    """
    将百分制成绩映射到四段分布标签

    参数:
        score (float): 学生作业总评成绩 (0~100)

    返回:
        str: 分数段标签
    """
    if score >= 90:
        return "90-100"
    if score >= 80:
        return "80-89"
    if score >= 60:
        return "60-79"
    return "0-59"


@router.get("/assignments/{assignment_id}/dashboard", summary="作业学情与薄弱点大屏")
def get_assignment_dashboard(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    聚合计算某次作业的整体学情与薄弱知识点

    参数:
        assignment_id (int): 作业 ID
        current_user (User): 当前登录用户
        db (Session): 数据库会话

    返回:
        dict: 应交/实交人数、平均分、及格率、四段分布、各题通过率、薄弱知识点 Top

    异常:
        HTTPException 403: 非本班教师
        HTTPException 404: 作业不存在
    """
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="作业不存在",
        )

    clazz = db.query(Class).filter(Class.id == assignment.class_id).first()
    if not clazz or clazz.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有本班教师可查看学情大屏",
        )

    submissions = (
        db.query(Submission)
        .filter(Submission.assignment_id == assignment_id)
        .all()
    )

    # ------------------------------------------------------------------
    # 1. 应交人数（班级名册成员）与题目清单
    # ------------------------------------------------------------------
    member_rows = (
        db.query(ClassMember)
        .filter(ClassMember.class_id == assignment.class_id)
        .all()
    )
    member_ids = {row.student_id for row in member_rows}
    expected_student_count = len(member_ids)

    problems = (
        db.query(Problem)
        .filter(Problem.assignment_id == assignment_id)
        .order_by(Problem.id)
        .all()
    )
    problem_ids = [problem.id for problem in problems]
    problem_count = len(problem_ids)

    # ------------------------------------------------------------------
    # 2. 每生每题最佳得分 -> 每生作业总评（各题最佳得分平均分）
    # ------------------------------------------------------------------
    best_by_student_problem: Dict[tuple, int] = {}
    for submission in submissions:
        if submission.user_id not in member_ids or submission.problem_id not in problem_ids:
            continue
        key = (submission.user_id, submission.problem_id)
        best_by_student_problem[key] = max(
            best_by_student_problem.get(key, 0), submission.score or 0
        )

    student_scores: Dict[int, float] = {}
    for user_id in {s.user_id for s in submissions if s.user_id in member_ids}:
        total = sum(best_by_student_problem.get((user_id, pid), 0) for pid in problem_ids)
        student_scores[user_id] = round(total / problem_count, 1) if problem_count else 0.0

    submitted_student_count = len(student_scores)
    pass_count = sum(1 for score in student_scores.values() if score >= _PASS_THRESHOLD)
    pass_rate = (
        round(pass_count / submitted_student_count * 100, 1)
        if submitted_student_count else 0.0
    )
    average_score = (
        round(sum(student_scores.values()) / submitted_student_count, 1)
        if submitted_student_count else 0.0
    )

    # ------------------------------------------------------------------
    # 3. 四段分数分布
    # ------------------------------------------------------------------
    band_counts = {label: 0 for label in _SCORE_BAND_LABELS}
    for score in student_scores.values():
        band_counts[_score_band(score)] += 1

    # ------------------------------------------------------------------
    # 4. 各题通过率（按学生去重，避免同一学生多次提交放大样本）
    # ------------------------------------------------------------------
    problem_stats: List[Dict] = []
    for problem in problems:
        problem_subs = [
            s for s in submissions
            if s.problem_id == problem.id and s.user_id in member_ids
        ]
        student_ids = {s.user_id for s in problem_subs}
        ac_ids = {s.user_id for s in problem_subs if s.status == "AC"}
        problem_stats.append({
            "problem_id": problem.id,
            "problem_title": problem.title,
            "knowledge_tag": problem.knowledge_tag,
            "submissions": len(problem_subs),
            "students": len(student_ids),
            "ac_count": len(ac_ids),
            "ac_rate": (
                round(len(ac_ids) / len(student_ids) * 100, 1)
                if student_ids else 0.0
            ),
        })

    # ------------------------------------------------------------------
    # 5. 全班薄弱知识点 Top（按学生去重统计失分率）
    # ------------------------------------------------------------------
    tag_students = defaultdict(set)
    tag_failed = defaultdict(set)
    problem_tag_map = {p.id: (p.knowledge_tag or "未标注") for p in problems}
    for submission in submissions:
        if submission.user_id not in member_ids:
            continue
        tag = problem_tag_map.get(submission.problem_id, "未标注")
        tag_students[tag].add(submission.user_id)
        if submission.status != "AC":
            tag_failed[tag].add(submission.user_id)

    weak_tags = []
    for tag, students in tag_students.items():
        failed = tag_failed.get(tag, set())
        weak_tags.append({
            "tag": tag,
            "total_students": len(students),
            "failed_students": len(failed),
            "fail_rate": (
                round(len(failed) / len(students) * 100, 1)
                if students else 0.0
            ),
        })
    weak_tags.sort(
        key=lambda item: (item["fail_rate"], item["failed_students"]),
        reverse=True,
    )
    weak_tags = weak_tags[:5]

    return {
        "assignment_id": assignment.id,
        "assignment_title": assignment.title,
        "assignment_type": assignment.type,
        "expected_student_count": expected_student_count,
        "submitted_student_count": submitted_student_count,
        # 兼容旧前端字段：student_count 仍表示实交人数
        "student_count": submitted_student_count,
        "average_score": average_score,
        "pass_rate": pass_rate,
        "pass_threshold": _PASS_THRESHOLD,
        "score_bands": [
            {"band": label, "count": band_counts[label]}
            for label in _SCORE_BAND_LABELS
        ],
        "problem_stats": problem_stats,
        "weak_knowledge_top": weak_tags,
    }