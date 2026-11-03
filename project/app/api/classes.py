"""
文件名: classes.py
功能描述: 班级管理业务与路由。支持教师创建班级（自动生成 6 位唯一邀请码）、
          学生凭邀请码加入班级、以及教师查看班级学生名册。
遵循规范: 权限严格隔离——建班/名册仅限 teacher 角色，加入仅限 student 角色；
          邀请码使用 secret 字符集随机生成并去重校验唯一性。
"""

import secrets
import string
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Class, ClassMember, User
from app.api.deps import get_current_user

router = APIRouter()

# 邀请码字符集（去除易混淆的 0/O、1/I/l）
_INVITE_ALPHABET = string.ascii_uppercase + string.digits
_INVITE_DISALLOW = set("0O1Il")
_INVITE_CHARS = "".join(c for c in _INVITE_ALPHABET if c not in _INVITE_DISALLOW)
_INVITE_LENGTH = 6


class ClassCreateRequest(BaseModel):
    """教师创建班级请求载荷"""

    name: str = Field(..., min_length=1, max_length=100, description="班级全称")


class JoinClassRequest(BaseModel):
    """学生通过邀请码加入班级请求载荷"""

    invite_code: str = Field(..., min_length=6, max_length=10, description="6 位班级邀请码")


def _generate_unique_invite_code(db: Session) -> str:
    """
    生成全局唯一的班级邀请码

    参数:
        db (Session): 数据库会话

    返回:
        str: 未与任何班级冲突的 6 位邀请码
    """
    for _ in range(50):
        code = "".join(secrets.choice(_INVITE_CHARS) for _ in range(_INVITE_LENGTH))
        exists = db.query(Class).filter(Class.invite_code == code).first()
        if not exists:
            return code
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="邀请码生成冲突，请重试",
    )


def _require_role(user: User, expected: str) -> None:
    """校验用户角色，不符时抛 403"""
    if user.role != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"该操作仅限 {expected} 角色",
        )


@router.post("/classes", summary="教师创建班级（自动生成 6 位邀请码）")
def create_class(
    payload: ClassCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    教师创建新班级

    参数:
        payload (ClassCreateRequest): 班级名称
        current_user (User): 当前登录用户
        db (Session): 数据库会话

    返回:
        dict: 班级信息与邀请码

    异常:
        HTTPException 403: 非教师角色
    """
    _require_role(current_user, "teacher")

    clazz = Class(
        name=payload.name.strip(),
        invite_code=_generate_unique_invite_code(db),
        teacher_id=current_user.id,
    )
    db.add(clazz)
    db.commit()
    db.refresh(clazz)

    return {
        "id": clazz.id,
        "name": clazz.name,
        "invite_code": clazz.invite_code,
        "teacher_id": clazz.teacher_id,
    }


@router.post("/classes/join", summary="学生凭邀请码加入班级")
def join_class(
    payload: JoinClassRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    学生通过邀请码加入班级

    参数:
        payload (JoinClassRequest): 邀请码
        current_user (User): 当前登录用户
        db (Session): 数据库会话

    返回:
        dict: 加入结果与班级信息

    异常:
        HTTPException 403: 非学生角色
        HTTPException 404: 邀请码不存在
        HTTPException 409: 已在该班级 / 加入失败
    """
    _require_role(current_user, "student")

    code = payload.invite_code.strip().upper()
    clazz = db.query(Class).filter(Class.invite_code == code).first()
    if not clazz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="邀请码无效或班级不存在",
        )

    exists = (
        db.query(ClassMember)
        .filter(ClassMember.class_id == clazz.id, ClassMember.student_id == current_user.id)
        .first()
    )
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="你已在当前班级中",
        )

    member = ClassMember(class_id=clazz.id, student_id=current_user.id)
    db.add(member)
    db.commit()

    return {
        "class_id": clazz.id,
        "class_name": clazz.name,
        "message": "加入成功",
    }


@router.get("/classes/{class_id}/students", summary="查看班级学生名册")
def list_class_students(
    class_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    教师查看某班级的学生名册

    参数:
        class_id (int): 班级 ID
        current_user (User): 当前登录用户
        db (Session): 数据库会话

    返回:
        dict: 班级信息与学生名单

    异常:
        HTTPException 403: 非本班教师
        HTTPException 404: 班级不存在
    """
    clazz = db.query(Class).filter(Class.id == class_id).first()
    if not clazz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="班级不存在",
        )
    if clazz.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有本班教师可查看名册",
        )

    members = (
        db.query(ClassMember, User)
        .join(User, ClassMember.student_id == User.id)
        .filter(ClassMember.class_id == class_id)
        .order_by(User.username)
        .all()
    )

    students = [
        {
            "student_id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "joined_at": member.joined_at.isoformat() if member.joined_at else None,
        }
        for member, user in members
    ]

    return {
        "class_id": clazz.id,
        "class_name": clazz.name,
        "student_count": len(students),
        "students": students,
    }