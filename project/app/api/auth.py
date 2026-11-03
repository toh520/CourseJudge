"""
文件名: auth.py
功能描述: 极简认证与登录路由。支持用户名+明文密码登录换取 JWT 令牌，
          以及通过令牌获取当前登录用户信息。
遵循规范: 依据 security.py 明文密码比对 + JWT 无状态流转的极简设计，
          不引入复杂加密方案，便于直观调试与桌面端集成。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models import User
from app.api.deps import get_current_user

router = APIRouter()


class LoginRequest(BaseModel):
    """登录请求载荷"""

    username: str = Field(..., min_length=1, max_length=50, description="学号或工号登录账号")
    password: str = Field(..., min_length=1, max_length=100, description="登录明文密码")


class UserOut(BaseModel):
    """对外暴露的用户信息（永不返回密码）"""

    id: int
    username: str
    real_name: str
    role: str

    @classmethod
    def from_model(cls, user: User) -> "UserOut":
        """将 ORM 用户实体映射为响应模型"""
        return cls(
            id=user.id,
            username=user.username,
            real_name=user.real_name,
            role=user.role,
        )


def _user_to_dict(user: User) -> dict:
    """将用户实体序列化为对外 JSON 字典（屏蔽敏感字段）"""
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "role": user.role,
    }


@router.post("/auth/login", summary="登录并获取 JWT 令牌")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    """
    用户名+明文密码登录

    参数:
        payload (LoginRequest): 登录凭据
        db (Session): 数据库会话

    返回:
        dict: 访问令牌、令牌类型与用户信息

    异常:
        HTTPException 401: 账号不存在或密码错误
    """
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误",
        )

    token = create_access_token({"sub": user.username, "role": user.role})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _user_to_dict(user),
    }


@router.get("/auth/me", summary="获取当前登录用户")
def get_me(current_user: User = Depends(get_current_user)) -> dict:
    """
    通过 Bearer 令牌返回当前登录用户信息

    参数:
        current_user (User): 由认证依赖注入的当前用户

    返回:
        dict: 当前用户信息
    """
    return _user_to_dict(current_user)