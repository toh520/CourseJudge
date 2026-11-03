"""
文件名: deps.py
功能描述: API 层公共依赖注入。封装 JWT 身份解析与当前用户获取，
          供所有受保护路由复用；未携带有效令牌时统一返回 401。
遵循规范: 无状态 JWT 流转，一切数据仅来源于请求头与数据库。
"""

from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import User


def get_current_user(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> User:
    """
    从 Authorization: Bearer <token> 头部解析并返回当前登录用户

    参数:
        authorization (str): 请求头 Authorization 原文
        db (Session): 数据库会话

    返回:
        User: 命中的用户实体

    异常:
        HTTPException 401: 缺少令牌、令牌无效、过期或用户不存在
    """
    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证令牌，请在 Authorization 头携带 Bearer token",
        )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效或已过期",
        )

    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌载荷缺少用户标识",
        )

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌对应用户不存在",
        )
    return user


def _extract_bearer_token(authorization: str) -> Optional[str]:
    """
    从授权头字符串中截取 Bearer token

    参数:
        authorization (str): 授权头原文

    返回:
        Optional[str]: 提取到的 token，格式不符时返回 None
    """
    if not authorization:
        return None
    parts = authorization.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None