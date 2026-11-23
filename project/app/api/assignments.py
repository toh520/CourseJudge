"""
文件名: assignments.py
功能描述: 作业与考试编排路由。支持教师向班级发布作业/考试（练习/考试双模式）、
          查看&获取作业题目列表，并在报错时给出明确提示。
遵循规范: 权限隔离——发布仅限本班教师；题目列表对班级内学生与教师开放；
          考前隐藏题面，时间窗由服务端统一校验。
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Assignment, Class, ClassMember, Problem, Submission, TestCase, User
from app.api.deps import get_current_user

router = APIRouter()

# 支持的作业类型
VALID_ASSIGNMENT_TYPES = {"practice", "exam"}


class TestCaseCreateRequest(BaseModel):
    """发布作业时内联的测试用例"""

    input_data: str = Field("", description="测试输入")
    output_data: str = Field("", description="期望输出")
    score_weight: int = Field(10, ge=0, description="用例分值权重")


class ProblemCreateRequest(BaseModel):
    """发布作业时内联的题目"""

    title: str = Field(..., min_length=1, max_length=100, description="题目标题")
    description: str = Field(..., min_length=1, description="Markdown 题面")
    input_format: str = Field("", description="输入格式")
    output_format: str = Field("", description="输出格式")
    sample_input: str = Field("", description="样例输入")
    sample_output: str = Field("", description="样例输出")
    time_limit_ms: int = Field(1000, ge=100, le=10000, description="时间限制毫秒")
    memory_limit_mb: int = Field(256, ge=16, le=1024, description="内存限制MB")
    knowledge_tag: str = Field("", max_length=50, description="知识点标签")
    is_ai_generated: bool = Field(False, description="是否 AI 生成")
    test_cases: List[TestCaseCreateRequest] = Field(default_factory=list, description="测试用例列表")


class AssignmentCreateRequest(BaseModel):
    """教师发布作业/考试请求载荷"""

    class_id: int = Field(..., description="归属班级 ID")
    title: str = Field(..., min_length=1, max_length=100, description="作业/考试名称")
    type: str = Field("practice", description="practice(练习) / exam(考试)")
    start_time: Optional[datetime] = Field(None, description="允许作答开始时间")
    end_time: Optional[datetime] = Field(None, description="截止交卷时间")
    problems: List[ProblemCreateRequest] = Field(
        default_factory=list, description="随作业一并发布的题目与用例清单"
    )


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

    for problem in payload.problems:
        if not any(case.score_weight > 0 for case in problem.test_cases):
            raise HTTPException(status_code=422, detail="每道题至少需要一组有正分值的测试用例")

    now = datetime.now(timezone.utc)
    start_time = _as_utc(payload.start_time) or now
    end_time = _as_utc(payload.end_time) or (start_time + timedelta(days=7))
    if end_time <= start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="截止时间必须晚于开始时间",
        )

    assignment = Assignment(
        class_id=payload.class_id,
        title=payload.title.strip(),
        type=payload.type,
        start_time=start_time,
        end_time=end_time,
        created_by=current_user.id,
    )

    try:
        db.add(assignment)
        db.flush()  # 先取得作业 ID，供下属题目关联

        # 将随作业一并提交的题目与测试用例持久化，形成完整发布事务
        for problem_payload in payload.problems:
            problem = Problem(
                assignment_id=assignment.id,
                title=problem_payload.title.strip(),
                description=problem_payload.description,
                input_format=problem_payload.input_format,
                output_format=problem_payload.output_format,
                sample_input=problem_payload.sample_input,
                sample_output=problem_payload.sample_output,
                time_limit_ms=problem_payload.time_limit_ms,
                memory_limit_mb=problem_payload.memory_limit_mb,
                knowledge_tag=problem_payload.knowledge_tag.strip(),
                is_ai_generated=problem_payload.is_ai_generated,
            )
            db.add(problem)
            db.flush()

            for case_payload in problem_payload.test_cases:
                db.add(TestCase(
                    problem_id=problem.id,
                    input_data=case_payload.input_data,
                    output_data=case_payload.output_data,
                    score_weight=case_payload.score_weight,
                ))

        db.commit()
        db.refresh(assignment)
    except Exception:
        db.rollback()
        raise

    return {
        "id": assignment.id,
        "class_id": assignment.class_id,
        "title": assignment.title,
        "type": assignment.type,
        "start_time": _as_utc(assignment.start_time).isoformat() if assignment.start_time else None,
        "end_time": _as_utc(assignment.end_time).isoformat() if assignment.end_time else None,
        "problem_count": len(payload.problems),
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

    if assignment.type == "exam" and current_user.role == "student" and _time_status(assignment) == "upcoming":
        raise HTTPException(status_code=403, detail="考试开始后可查看题目")

    problems = (
        db.query(Problem)
        .filter(Problem.assignment_id == assignment_id)
        .order_by(Problem.id)
        .all()
    )

    # 每题返回本人的最后一次提交，换设备也能恢复交卷状态及结果。
    latest = {}
    if current_user.role == "student":
        for submission in db.query(Submission).filter_by(
            assignment_id=assignment.id, user_id=current_user.id
        ).order_by(Submission.id).all():
            latest[submission.problem_id] = {
                "score": submission.score, "status": submission.status,
                "is_final": submission.is_final, "code": submission.code,
            }
    return {
        "assignment_id": assignment.id,
        "assignment_title": assignment.title,
        "assignment_type": assignment.type,
        "problem_count": len(problems),
        "problems": [dict(_problem_to_dict(p), my_submission=latest.get(p.id)) for p in problems],
    }


@router.get("/assignments/class/{class_id}", summary="按班级获取作业列表")
def list_class_assignments(
    class_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    获取某班级下的全部作业/考试，供教师工作台与学生“我的作业”大厅使用

    参数:
        class_id (int): 班级 ID
        current_user (User): 当前登录用户
        db (Session): 数据库会话

    返回:
        dict: 作业列表，含时间状态与学生个人最佳得分

    异常:
        HTTPException 403: 非本班成员
        HTTPException 404: 班级不存在
    """
    clazz = db.query(Class).filter(Class.id == class_id).first()
    if not clazz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="班级不存在",
        )

    is_teacher = clazz.teacher_id == current_user.id
    is_member = (
        db.query(ClassMember)
        .filter(
            ClassMember.class_id == class_id,
            ClassMember.student_id == current_user.id,
        )
        .first()
        is not None
    )
    if not (is_teacher or is_member):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限查看该班级作业（非本班成员）",
        )

    assignments = (
        db.query(Assignment)
        .filter(Assignment.class_id == class_id)
        .order_by(Assignment.start_time.desc(), Assignment.id.desc())
        .all()
    )

    items = []
    for assignment in assignments:
        item = {
            "id": assignment.id,
            "title": assignment.title,
            "type": assignment.type,
            "start_time": _as_utc(assignment.start_time).isoformat() if assignment.start_time else None,
            "end_time": _as_utc(assignment.end_time).isoformat() if assignment.end_time else None,
            "time_status": _time_status(assignment),
            "problem_count": len(assignment.problems),
        }
        if not is_teacher:
            my_submissions = (
                db.query(Submission)
                .filter(
                    Submission.assignment_id == assignment.id,
                    Submission.user_id == current_user.id,
                )
                .all()
            )
            item["my_submission_count"] = len(my_submissions)
            best = {}
            for submission in my_submissions:
                pid = submission.problem_id
                best[pid] = max(best.get(pid, 0), submission.score)
            item["my_submitted_problems"] = len(best)
            item["my_best_score"] = round(sum(best.values()) / item["problem_count"], 1) if item["problem_count"] else 0
        items.append(item)

    return {
        "class_id": clazz.id,
        "class_name": clazz.name,
        "assignment_count": len(items),
        "assignments": items,
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
        "start_time": _as_utc(assignment.start_time).isoformat() if assignment.start_time else None,
        "end_time": _as_utc(assignment.end_time).isoformat() if assignment.end_time else None,
        "problem_count": len(assignment.problems),
        "submission_count": len(assignment.submissions),
        "time_status": _time_status(assignment),
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


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """
    将数据库/请求中的时间统一转换为 UTC 感知时间

    SQLite 会丢失时区信息，因此对 naive datetime 统一按 UTC 处理。

    参数:
        value (Optional[datetime]): 原始时间

    返回:
        Optional[datetime]: UTC 感知时间
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _time_status(assignment: Assignment) -> str:
    """
    计算作业当前的时间状态

    参数:
        assignment (Assignment): 作业实体

    返回:
        str: upcoming(未开始) / ongoing(进行中) / ended(已截止)
    """
    now = datetime.now(timezone.utc)
    start = _as_utc(assignment.start_time)
    end = _as_utc(assignment.end_time)
    if start and now < start:
        return "upcoming"
    if end and now > end:
        return "ended"
    return "ongoing"


def ensure_time_window(assignment: Assignment) -> None:
    """
    校验当前时间是否处于作业允许作答的时间窗内

    参数:
        assignment (Assignment): 作业实体

    异常:
        HTTPException 403: 作业尚未开始或已截止
    """
    now = datetime.now(timezone.utc)
    start = _as_utc(assignment.start_time)
    end = _as_utc(assignment.end_time)
    if start and now < start:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="作业尚未开始，暂不可作答",
        )
    if end and now > end:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="作业已截止，不可继续作答",
        )