"""
文件名: training.py
功能描述: 专属强化训练题路由。支持学生获取个人专属训练题列表、查看单题详情、
          以及针对训练题提交判分并更新历史最佳状态。
遵循规范: 训练题由 Phase 3 的 TrainingProblemGenerator 生成并落库（test_cases_json），
          本路由负责读取与判分；判分结果同步回写 best_status。
"""

import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import TrainingProblem, User
from app.services.judge.judge_service import JudgeService
from app.api.deps import get_current_user

router = APIRouter()

# 判题服务单例
_judge_service = JudgeService()


class TrainingSubmitRequest(BaseModel):
    """训练题提交请求载荷"""

    code: str = Field(..., min_length=1, description="针对训练题提交的 C++ 源码")


def _parse_cases(test_cases_json: str) -> List[Dict[str, Any]]:
    """
    将训练题 JSON 用例串解析为简单用例对象列表

    参数:
        test_cases_json (str): JSON 字符串，元素含 input_data/output_data/score_weight

    返回:
        List[Dict[str, Any]]: 用例字典列表

    异常:
        HTTPException 500: JSON 解析失败
    """
    try:
        data = json.loads(test_cases_json)
        if not isinstance(data, list):
            raise ValueError("用例集合应为数组")
        return data
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"训练题用例解析失败: {exc}",
        ) from exc


class _SimpleCase:
    """判题器所需的简易用例对象（含属性访问）"""

    def __init__(self, item: Dict[str, Any]) -> None:
        self.input_data = item.get("input_data", "")
        self.output_data = item.get("output_data", "")
        self.score_weight = int(item.get("score_weight", 10) or 0)


@router.get("/training", summary="获取个人专属训练题列表")
def list_my_training(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    获取当前学生的全部专属强化训练题

    参数:
        current_user (User): 当前登录用户
        db (Session): 数据库会话

    返回:
        dict: 训练题列表（每项含标题、知识点、最佳状态）
    """
    problems = (
        db.query(TrainingProblem)
        .filter(TrainingProblem.student_id == current_user.id)
        .order_by(TrainingProblem.created_at.desc())
        .all()
    )

    items = [
        {
            "id": p.id,
            "title": p.title,
            "knowledge_tag": p.knowledge_tag,
            "sample_input": p.sample_input,
            "sample_output": p.sample_output,
            "best_status": p.best_status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in problems
    ]

    return {"training_count": len(items), "training_list": items}


@router.get("/training/{training_id}", summary="获取单题详情")
def get_training_detail(
    training_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    获取某道训练题的完整详情（含题面描述，不返回隐藏用例）

    参数:
        training_id (int): 训练题 ID
        current_user (User): 当前登录用户
        db (Session): 数据库会话

    返回:
        dict: 训练题详情

    异常:
        HTTPException 403: 非本人训练题
        HTTPException 404: 训练题不存在
    """
    problem = _get_own_training(training_id, current_user.id, db)
    return {
        "id": problem.id,
        "title": problem.title,
        "knowledge_tag": problem.knowledge_tag,
        "description": problem.description,
        "sample_input": problem.sample_input,
        "sample_output": problem.sample_output,
        "best_status": problem.best_status,
    }


@router.post("/training/{training_id}/submit", summary="针对训练题提交判分")
def submit_training(
    training_id: int,
    payload: TrainingSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    针对某道训练题提交判分，并更新历史最佳状态

    参数:
        training_id (int): 训练题 ID
        payload (TrainingSubmitRequest): 源码
        current_user (User): 当前登录用户
        db (Session): 数据库会话

    返回:
        dict: 判分结果

    异常:
        HTTPException 403: 非本人训练题
        HTTPException 404: 训练题不存在
        HTTPException 500: 判分异常
    """
    problem = _get_own_training(training_id, current_user.id, db)
    cases = [_SimpleCase(item) for item in _parse_cases(problem.test_cases_json)]

    try:
        judge_result = _judge_service.judge_submission(
            source_code=payload.code,
            test_cases=cases,
            time_limit_ms=None,
            memory_limit_mb=None,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"训练题判分异常: {exc}",
        ) from exc

    # 更新历史最佳状态（AC 优先，其次按出现顺序）
    if problem.best_status in (None, "Unsolved") or (
        judge_result["status"] == "AC" and problem.best_status != "AC"
    ):
        problem.best_status = judge_result["status"]
        db.commit()

    return {
        "training_id": problem.id,
        "title": problem.title,
        "status": judge_result["status"],
        "score": judge_result["score"],
        "passed_cases": judge_result["passed_cases"],
        "total_cases": judge_result["total_cases"],
        "max_time_ms": judge_result["max_time_ms"],
        "best_status": problem.best_status,
    }


def _get_own_training(training_id: int, student_id: int, db: Session) -> TrainingProblem:
    """
    查询某学生自己的训练题，越权或不存在时抛错

    参数:
        training_id (int): 训练题 ID
        student_id (int): 当前学生 ID
        db (Session): 数据库会话

    返回:
        TrainingProblem: 训练题实体

    异常:
        HTTPException 403/404
    """
    problem = db.query(TrainingProblem).filter(TrainingProblem.id == training_id).first()
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="训练题不存在",
        )
    if problem.student_id != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问他人训练题",
        )
    return problem