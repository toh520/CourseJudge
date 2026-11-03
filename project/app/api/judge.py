"""
文件名: judge.py
功能描述: 判题与自测提交路由。提供自测运行（不记录得分）与正式提交判分
          （练习多次 / 考试单次交卷锁定）两类核心能力。
遵循规范: 复用以 JudgeService.run_custom_test / judge_submission 作为底层；
          考试模式首次提交后置 is_final 锁定，后续重复提交返回 409。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Problem, Submission, User
from app.services.judge.judge_service import JudgeService
from app.api.deps import get_current_user

router = APIRouter()

# 判题服务单例（probe/sandbox/comparator 均带缓存与资源复用）
_judge_service = JudgeService()


class RunTestRequest(BaseModel):
    """自测运行请求载荷"""

    problem_id: int = Field(..., description="题目 ID")
    code: str = Field(..., min_length=1, description="待自测的 C++ 源码")
    input_data: str = Field("", description="本次自测输入数据")

    @property
    def expected_output(self) -> str:
        """自测不预设期望输出（可选留空不比对）"""
        return ""


class SubmitRequest(BaseModel):
    """正式提交请求载荷"""

    problem_id: int = Field(..., description="题目 ID")
    code: str = Field(..., min_length=1, description="提交的 C++ 源码")


@router.post("/judge/run-test", summary="自测运行（不记录得分）")
def run_self_test(
    payload: RunTestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    针对题目执行单次自测运行

    参数:
        payload (RunTestRequest): 题目 ID 与源码、输入
        current_user (User): 当前登录用户
        db (Session): 数据库会话

    返回:
        dict: 自测运行结果（编译/执行状态、输出、比对结论）

    异常:
        HTTPException 404: 题目不存在
    """
    problem = _get_problem_or_404(payload.problem_id, db)
    result = _judge_service.run_custom_test(
        source_code=payload.code,
        input_data=payload.input_data,
        expected_output="",
        time_limit_ms=problem.time_limit_ms,
        memory_limit_mb=problem.memory_limit_mb,
    )
    result["problem_id"] = problem.id
    result["problem_title"] = problem.title
    return result


@router.post("/judge/submit", summary="正式提交判分（练习多次/考试单次锁定）")
def submit_solution(
    payload: SubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    针对题目正式提交判分并落库

    参数:
        payload (SubmitRequest): 题目 ID 与源码
        current_user (User): 当前登录用户
        db (Session): 数据库会话

    返回:
        dict: 判分结果、得分、状态与是否最终交卷标记

    异常:
        HTTPException 404: 题目不存在
        HTTPException 409: 考试模式下已交卷被锁定
        HTTPException 500: 判分服务异常
    """
    problem = _get_problem_or_404(payload.problem_id, db)
    assignment = problem.assignment

    # 考试模式：检测是否已锁定最终交卷
    if assignment.type == "exam":
        locked = (
            db.query(Submission)
            .filter(
                Submission.assignment_id == assignment.id,
                Submission.problem_id == problem.id,
                Submission.user_id == current_user.id,
                Submission.is_final.is_(True),
            )
            .first()
        )
        if locked:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="考试模式已交卷锁定，不可重复提交",
            )

    try:
        judge_result = _judge_service.judge_submission(
            source_code=payload.code,
            test_cases=problem.test_cases,
            time_limit_ms=problem.time_limit_ms,
            memory_limit_mb=problem.memory_limit_mb,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"判分服务异常: {exc}",
        ) from exc

    # 落库提交记录
    submission = Submission(
        user_id=current_user.id,
        problem_id=problem.id,
        assignment_id=assignment.id,
        code=payload.code,
        status=judge_result["status"],
        score=judge_result["score"],
        time_used_ms=judge_result["max_time_ms"],
        compiler_output=judge_result.get("compiler_output"),
        is_final=(assignment.type == "exam"),
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    return {
        "submission_id": submission.id,
        "problem_id": problem.id,
        "problem_title": problem.title,
        "assignment_id": assignment.id,
        "assignment_type": assignment.type,
        "status": judge_result["status"],
        "score": judge_result["score"],
        "passed_cases": judge_result["passed_cases"],
        "total_cases": judge_result["total_cases"],
        "max_time_ms": judge_result["max_time_ms"],
        "is_final": submission.is_final,
        "case_results": judge_result["case_results"],
    }


def _get_problem_or_404(problem_id: int, db: Session) -> Problem:
    """
    查询题目，不存在时抛 404

    参数:
        problem_id (int): 题目 ID
        db (Session): 数据库会话

    返回:
        Problem: 题目实体

    异常:
        HTTPException 404: 题目不存在
    """
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="题目不存在",
        )
    return problem