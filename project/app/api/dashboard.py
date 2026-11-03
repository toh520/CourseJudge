"""
文件名: dashboard.py
功能描述: 教师端班级学情与弱点大屏聚合路由。针对某次作业/考试，聚合计算
          及格率、分数段分布、各题通过率、全班薄弱知识点 Top 统计。
遵循规范: 数据聚合基于该作业全部学生的最终/最新提交；仅本班教师可查看，
          提供清晰的分层统计便于前端大屏渲染。
"""

from collections import Counter, defaultdict
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Assignment, Class, Problem, Submission, User
from app.api.deps import get_current_user

router = APIRouter()

# 分数段划分边界（企业课程常见及格线 60 分）
_PASS_THRESHOLD = 60
_SCORE_BANDS = [(0, 59), (60, 79), (80, 100)]


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
        dict: 及格率、分数段分布、各题通过率、薄弱知识点 Top

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
    # 1. 计算每个学生在该作业的最佳（或最终）提交得分
    # ------------------------------------------------------------------
    student_best_score: Dict[int, int] = {}
    for sub in submissions:
        student_best_score[sub.user_id] = max(
            student_best_score.get(sub.user_id, 0), sub.score
        )

    total_students = len(student_best_score)
    pass_count = sum(1 for score in student_best_score.values() if score >= _PASS_THRESHOLD)
    pass_rate = round(pass_count / total_students * 100, 1) if total_students else 0.0

    # 2. 分数段分布
    band_counts = {f"{lo}-{hi}": 0 for lo, hi in _SCORE_BANDS}
    for score in student_best_score.values():
        for lo, hi in _SCORE_BANDS:
            if lo <= score <= hi:
                band_counts[f"{lo}-{hi}"] += 1
                break

    # ------------------------------------------------------------------
    # 3. 各题通过率（submission 中 status == AC）
    # ------------------------------------------------------------------
    problem_stats: List[Dict] = []
    problems = (
        db.query(Problem).filter(Problem.assignment_id == assignment_id).order_by(Problem.id).all()
    )
    for problem in problems:
        problem_subs = [s for s in submissions if s.problem_id == problem.id]
        if not problem_subs:
            problem_stats.append({"problem_id": problem.id, "problem_title": problem.title,
                                  "submissions": 0, "ac_rate": 0.0})
            continue
        ac_count = sum(1 for s in problem_subs if s.status == "AC")
        problem_stats.append({
            "problem_id": problem.id,
            "problem_title": problem.title,
            "knowledge_tag": problem.knowledge_tag,
            "submissions": len(problem_subs),
            "ac_count": ac_count,
            "ac_rate": round(ac_count / len(problem_subs) * 100, 1),
        })

    # ------------------------------------------------------------------
    # 4. 全班薄弱知识点 Top（按非 AC 提交知识点计数, ALL 计数实体）
    # ------------------------------------------------------------------
    tag_correct = defaultdict(int)   # 知识点正确提交数
    tag_total = defaultdict(int)     # 知识点提交总次数
    problem_tag_map = {p.id: (p.knowledge_tag or "未标注") for p in problems}
    for sub in submissions:
        tag = problem_tag_map.get(sub.problem_id, "未标注")
        tag_total[tag] += 1
        if sub.status == "AC":
            tag_correct[tag] += 1

    weak_tags: List[Dict] = []
    for tag in tag_total:
        correct = tag_correct.get(tag, 0)
        total = tag_total[tag]
        fail_rate = round((total - correct) / total * 100, 1) if total else 0.0
        weak_tags.append({
            "tag": tag,
            "total_submissions": total,
            "correct_submissions": correct,
            "fail_rate": fail_rate,
        })
    # 按失分率降序取 Top 5
    weak_tags.sort(key=lambda x: x["fail_rate"], reverse=True)
    weak_tags = weak_tags[:5]

    return {
        "assignment_id": assignment.id,
        "assignment_title": assignment.title,
        "assignment_type": assignment.type,
        "student_count": total_students,
        "pass_rate": pass_rate,
        "pass_threshold": _PASS_THRESHOLD,
        "score_bands": [{"band": band, "count": band_counts[band]} for band in band_counts],
        "problem_stats": problem_stats,
        "weak_knowledge_top": weak_tags,
    }