"""
文件名: assignments.py
功能描述: 作业与考试编排路由。支持教师向班级发布作业/考试（练习/考试双模式）、
          查看&获取作业题目列表，并在报错时给出明确提示。
遵循规范: 权限隔离——发布仅限本班教师；题目列表对班级内学生与教师开放；
          时间窗在业务层不强制（当前阶段由前端控制），后续可扩展。
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Assignment, Class, ClassMember, Problem, TestCase, User
from app.api.deps import get_current_user

router = APIRouter()

# 支持的作业类型
VALID_ASSIGNMENT_TYPES = {"practice", "exam"}


class AssignmentCreateRequest(BaseModel):
    """教师发布作业/考试请求载荷"""

    class_id: int = Field(..., description="归属班级 ID")
    title: str = Field(..., min_length=1, max_length=100, description="作业/考试名称")
    type: str = Field("practice", description="practice(练习) / exam(考试)")
    start_time: Optional[datetime] = Field(None, description="允许作答开始时间")
    end_time: Optional[datetime] = Field(None, description="截止交卷时间")


def _problem_to_dict(problem: Problem) -> dict:
    """将题目实体序列化为对外 JSON 字典，附带公开样例与用例数量"""
    return {
        "id": problem.id,
        "title": problem.title,
        "description": problem.description,
        "input_format": problem.input_format,
        "output_format": problem.output_format,
        "sample_input": problem.sample_input,
        "sample_output": problem.sample_output,
        "time_limit_ms": problem.time_limit_ms,
        "memory_limit_mb": problem.memory_limit_mb,
        "knowledge_tag": problem.knowledge_tag,
        "is_ai_generated": problem.is_ai_generated,
        "test_case_count": len(problem.test_cases),
    }


@router.post("/assignments", summary="教师发布作业/考试（练习/考试双模式）")
def create_assignment(
    payload: AssignmentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    教师在指定班级发布作业或考试

    参数:
        payload (AssignmentCreateRequest): 作业创建信息
        current_user (User): 当前登录用户
        db (Session): 数据库会话

    返回:
        dict: 新建作业信息

    异常:
        HTTPException 403: 非本班教师
        HTTPException 404: 班级不存在
        HTTPException 400: 非法作业类型
    """
    if payload.type not in VALID_ASSIGNMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="作业类型仅支持 practice(练习) 或 exam(考试)",
        )

    clazz = db.query(Class).filter(Class.id == payload.class_id).first()
    if not clazz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="班级不存在",
        )
    if clazz.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有本班教师可发布作业",
        )

    assignment = Assignment(
        class_id=payload.class_id,
        title=payload.title.strip(),
        type=payload.type,
        start_time=payload.start_time or datetime.utcnow(),
        end_time=payload.end_time or datetime.utcnow(),
        created_by=current_user.id,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return {
        "id": assignment.id,
        "class_id": assignment.class_id,
        "title": assignment.title,
        "type": assignment.type,
        "start_time": assignment.start_time.isoformat() if assignment.start_time else None,
        "end_time": assignment.end_time.isoformat() if assignment.end_time else None,
    }


@router.get("/assignments/{assignment_id}/problems", summary="获取作业题目列表")
def list_assignment_problems(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    获取某次作业/考试的题目列表

    参数:
        assignment_id (int): 作业 ID
        current_user (User): 当前登录用户
        db (Session): 数据库会话

    返回:
        dict: 作业信息与该作业全部题目

    异常:
        HTTPException 403: 非本班成员
        HTTPException 404: 作业不存在
    """
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="作业不存在",
        )
    _ensure_access(assignment, current_user, db)

    problems = (
        db.query(Problem)
        .filter(Problem.assignment_id == assignment_id)
        .order_by(Problem.id)
        .all()
    )

    return {
        "assignment_id": assignment.id,
        "assignment_title": assignment.title,
        "assignment_type": assignment.type,
        "problem_count": len(problems),
        "problems": [_problem_to_dict(p) for p in problems],
    }


@router.get("/assignments/{assignment_id}", summary="获取作业详情")
def get_assignment_detail(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    获取作业详情（含题目数量与提交统计）

    参数:
        assignment_id (int): 作业 ID
        current_user (User): 当前登录用户
        db (Session): 数据库会话

    返回:
        dict: 作业详细信息

    异常:
        HTTPException 403: 非本班成员
        HTTPException 404: 作业不存在
    """
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="作业不存在",
        )
    _ensure_access(assignment, current_user, db)

    return {
        "id": assignment.id,
        "class_id": assignment.class_id,
        "title": assignment.title,
        "type": assignment.type,
        "start_time": assignment.start_time.isoformat() if assignment.start_time else None,
        "end_time": assignment.end_time.isoformat() if assignment.end_time else None,
        "problem_count": len(assignment.problems),
        "submission_count": len(assignment.submissions),
    }


def _ensure_access(assignment: Assignment, user: User, db: Session) -> None:
    """
    校验当前用户是否可访问该作业（本班教师或本班学生）

    参数:
        assignment (Assignment): 作业实体
        user (User): 当前用户
        db (Session): 数据库会话

    异常:
        HTTPException 403: 非本班成员
    """
    clazz = db.query(Class).filter(Class.id == assignment.class_id).first()
    if clazz and clazz.teacher_id == user.id:
        return

    is_member = (
        db.query(ClassMember)
        .filter(
            ClassMember.class_id == assignment.class_id,
            ClassMember.student_id == user.id,
        )
        .first()
    )
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该作业（非本班成员）",
        )