"""
文件名: llm.py
功能描述: LLM 业务调度路由。通过 API 层对 Phase 3 的 LLM 四大能力（AI 出题、
          用例生成、考后一键诊断、强化题生成）进行封装，并提供 AI 助教流式问答。
遵循规范: 未配置 LLM_API_KEY 时统一返回 503 与友好提示；流式问答使用 SSE 增量输出；
          诊断与训练题生成参数化委派至底层服务。
"""

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import Assignment, Problem, Submission, TrainingProblem, User
from app.services.llm.client import LLMClient, LLMServiceError
from app.services.llm.diagnostician import Diagnostician
from app.services.llm.generator import ProblemGenerator
from app.services.llm.trainer import TrainingProblemGenerator
from app.services.llm.assistant import AssistantService
from app.api.deps import get_current_user
from app.api.assignments import _ensure_access

router = APIRouter()


class GenerateProblemRequest(BaseModel):
    """AI 出题请求载荷"""

    intent: str = Field(..., min_length=1, max_length=1000, description="教师出题意图")
    knowledge_tag: str = Field("", max_length=50, description="指定知识点标签")
    difficulty: str = Field("中等", max_length=10, description="目标难度")
    test_count: int = Field(5, ge=1, le=10, description="期望测试用例数量")


class GenerateTestInputsRequest(BaseModel):
    """用例生成请求载荷"""

    problem_id: int = Field(..., description="题目 ID")
    count: int = Field(5, ge=1, le=10, description="期望生成用例数量")


class DiagnoseRequest(BaseModel):
    """考后一键诊断请求载荷"""

    assignment_id: int = Field(..., description="作业/考试 ID")


class TrainingRequest(BaseModel):
    """针对弱点生成强化题请求载荷"""

    weak_point: str = Field(..., min_length=1, max_length=100, description="薄弱知识点")
    source_assignment_id: Optional[int] = Field(None, description="来源作业 ID")
    test_count: int = Field(4, ge=1, le=10, description="期望用例数量")


class ChatRequest(BaseModel):
    """AI 助教多轮对话请求载荷"""

    message: str = Field(..., min_length=1, max_length=4000, description="本次提问")
    message_id: Optional[int] = Field(None, description="助教会话消息 ID（可选）")
    history: List[Dict[str, str]] = Field(default_factory=list, description="历史对话")


def _require_llm_key() -> None:
    """未配置 LLM Key 时抛 503，避免向底层抛 LLMServiceError"""
    if not settings.LLM_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="尚未配置 LLM_API_KEY，请在项目 .env 中填写大模型 API Key 以启用 AI 功能",
        )


@router.post("/llm/generate-problem", summary="AI 快速出题并生成已验证用例")
def ai_generate_problem(
    payload: GenerateProblemRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    依据教师意图生成完整题目与已验证测试用例

    参数:
        payload (GenerateProblemRequest): 出题参数
        current_user (User): 当前登录用户

    返回:
        dict: 生成的题目与测试用例

    异常:
        HTTPException 503: 未配置 LLM Key
    """
    _require_llm_key()
    try:
        generator = ProblemGenerator()
        return generator.generate_problem(
            intent=payload.intent,
            knowledge_tag=payload.knowledge_tag,
            difficulty=payload.difficulty,
            test_count=payload.test_count,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI 出题失败: {exc}",
        ) from exc


@router.post("/llm/generate-test-inputs", summary="针对已生成题目补充测试用例")
def ai_generate_test_inputs(
    payload: GenerateTestInputsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    针对数据库中已存在的题目补充测试输入

    参数:
        payload (GenerateTestInputsRequest): 题目 ID 与目标数量
        current_user (User): 当前登录用户
        db (Session): 数据库会话

    返回:
        dict: 生成的测试输入列表

    异常:
        HTTPException 404: 题目不存在
        HTTPException 503: 未配置 LLM Key
    """
    _require_llm_key()
    problem = db.query(Problem).filter(Problem.id == payload.problem_id).first()
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="题目不存在",
        )

    try:
        generator = ProblemGenerator()
        from app.services.llm.common.schemas import GeneratedProblem

        gen_problem = GeneratedProblem(
            title=problem.title,
            description=problem.description,
            input_format=problem.input_format or "",
            output_format=problem.output_format or "",
            sample_input=problem.sample_input or "",
            sample_output=problem.sample_output or "",
            time_limit_ms=problem.time_limit_ms,
            memory_limit_mb=problem.memory_limit_mb,
            knowledge_tag=problem.knowledge_tag or "",
            standard_code="",  # 仅用于生成输入，不参与标准答案回填
        )
        test_inputs = generator.generate_test_inputs(gen_problem, payload.count)
        return {"problem_id": problem.id, "generated_inputs": test_inputs}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"用例生成失败: {exc}",
        ) from exc


@router.post("/llm/diagnose", summary="考后一键短板诊断")
def ai_diagnose(
    payload: DiagnoseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    针对某次作业的全部未满分提交生成短板诊断报告

    参数:
        payload (DiagnoseRequest): 作业 ID
        current_user (User): 当前登录用户
        db (Session): 数据库会话

    返回:
        dict: 诊断报告（summary / weak_points / learning_guidance）

    异常:
        HTTPException 404: 作业不存在
        HTTPException 503: 未配置 LLM Key
    """
    _require_llm_key()
    assignment = db.query(Assignment).filter(Assignment.id == payload.assignment_id).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="作业不存在",
        )
    _ensure_access(assignment, current_user, db)

    # 收集该作业所有未 AC 的提交摘要 (problem_title/知识标签/状态/得分/代码)
    submissions = (
        db.query(Submission)
        .filter(Submission.assignment_id == payload.assignment_id)
        .all()
    )
    problem_map = {p.id: p for p in db.query(Problem).filter(Problem.assignment_id == payload.assignment_id).all()}
    failed_items: List[Dict[str, Any]] = []
    for sub in submissions:
        if sub.status == "AC":
            continue
        problem = problem_map.get(sub.problem_id)
        failed_items.append({
            "problem_title": problem.title if problem else f"题{sub.problem_id}",
            "knowledge_tag": problem.knowledge_tag if problem else "",
            "status": sub.status,
            "score": sub.score,
            "code": sub.code,
            "error_msg": sub.compiler_output or "",
        })

    try:
        diagnostician = Diagnostician()
        return diagnostician.diagnose(assignment.title, failed_items)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"诊断失败: {exc}",
        ) from exc


@router.post("/llm/training", summary="针对弱点生成强化训练题")
def ai_generate_training(
    payload: TrainingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    依据弱点知识标签为学生生成一道强化训练题并落库

    参数:
        payload (TrainingRequest): 弱点参数
        current_user (User): 当前登录用户
        db (Session): 数据库会话

    返回:
        dict: 新生成的训练题信息

    异常:
        HTTPException 503: 未配置 LLM Key
    """
    _require_llm_key()
    try:
        trainer = TrainingProblemGenerator()
        training: TrainingProblem = trainer.generate_and_save(
            db=db,
            student_id=current_user.id,
            weak_point=payload.weak_point,
            source_assignment_id=payload.source_assignment_id,
            test_count=payload.test_count,
        )
        return {
            "id": training.id,
            "title": training.title,
            "knowledge_tag": training.knowledge_tag,
            "sample_input": training.sample_input,
            "sample_output": training.sample_output,
            "best_status": training.best_status,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"训练题生成失败: {exc}",
        ) from exc


@router.post("/llm/chat", summary="AI 助教多轮对话（SSE 流式）")
async def ai_chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    发起 AI 助教对话并返回 SSE 流式增量回答

    参数:
        payload (ChatRequest): 提问与历史
        current_user (User): 当前登录用户

    返回:
        StreamingResponse: text/event-stream 增量输出

    异常:
        HTTPException 503: 未配置 LLM Key
    """
    _require_llm_key()
    assistant = AssistantService()

    async def event_generator():
        try:
            for chunk in assistant.chat_stream(payload.message, payload.history):
                yield f"data: {json.dumps({'delta': chunk}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )