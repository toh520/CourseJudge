"""
文件名: user.py
功能描述: 用户数据模型实体。
遵循规范: 极致精简克制原则，仅保留完成教学作业所必需的字段，密码采用明文存储便于直观调试。
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from app.core.database import Base


class User(Base):
    """
    用户实体类
    对应数据库表: users
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="用户主键ID")
    username = Column(String(50), unique=True, nullable=False, index=True, comment="学号或工号登录账号")
    real_name = Column(String(50), nullable=False, comment="用户真实姓名")
    password = Column(String(50), nullable=False, comment="登录明文密码 (课设免加密)")
    role = Column(String(20), nullable=False, default="student", comment="用户角色: teacher (教师) / student (学生)")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, comment="账号创建时间")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"
