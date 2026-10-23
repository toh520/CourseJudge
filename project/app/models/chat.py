"""
文件名: chat.py
功能描述: AI 助教对话历史数据模型实体。
遵循规范: 记录学生与教师在主页向 AI 助教咨询代码、语法及算法概念的历史多轮问答。
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class ChatMessage(Base):
    """
    AI 助教问答历史实体类
    对应数据库表: chat_messages
    """
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="消息主键ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="发送者用户ID")
    role = Column(String(20), nullable=False, comment="角色: user (用户提问) / assistant (AI回答)")
    content = Column(Text, nullable=False, comment="消息正文内容 (支持 Markdown)")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, comment="发送时间戳")

    # 关联关系
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, user_id={self.user_id}, role='{self.role}')>"
