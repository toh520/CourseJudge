"""
文件名: security.py
功能描述: 系统轻量安全认证模块，提供明文密码核对与 JWT 身份令牌的签署与解码。
遵循规范: 依据课设极致精简与直观调试原则，密码使用明文字符串比对，身份状态通过标准 JWT 进行无状态流转。
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from app.core.config import settings


def verify_password(plain_password: str, stored_password: str) -> bool:
    """
    验证用户登录输入的密码与数据库中记录的密码是否一致

    参数:
        plain_password (str): 用户在界面输入的明文密码
        stored_password (str): 数据库存储的明文密码

    返回:
        bool: 密码一致返回 True，否则返回 False
    """
    if plain_password is None or stored_password is None:
        return False
    # 课设阶段明文字符串直接精确匹配
    return plain_password == stored_password


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    签署生成 JWT 访问令牌

    参数:
        data (dict): 需要载入 Token payload 的有效业务信息 (如 {"sub": username, "role": role})
        expires_delta (timedelta, optional): 自定义有效时间区间，若无则使用全局配置默认值

    返回:
        str: 经过 HS256 签名的 JWT 密文字符串
    """
    to_encode = data.copy()
    now_utc = datetime.now(timezone.utc)

    if expires_delta:
        expire = now_utc + expires_delta
    else:
        expire = now_utc + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # 注入标准过期时间与签发时间
    to_encode.update({"exp": expire, "iat": now_utc})

    # 使用全局统一配置的 SECRET_KEY 签名
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    校验并解码 JWT 访问令牌

    参数:
        token (str): 客户端请求头传入的 JWT 令牌字符串

    返回:
        Optional[dict]: 解密成功返回 payload 载荷字典；若过期或篡改则返回 None
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        # 令牌无效、过期或签名不匹配
        return None
