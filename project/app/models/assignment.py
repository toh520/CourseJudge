"""
文件名: assignment.py
功能描述: 作业与考试活动数据模型实体。
遵循规范: 支持练习模式 (practice) 与考试模式 (exam) 两类不同评测规则的教学活动。
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Assignment(Base):
    """
    作业与考试活动实体类
    对应数据库表: assignments
    """
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="作业/考试主键ID")
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True, comment="归属班级ID")
    title = Column(String(100), nullable=False, comment="作业/考试名称 (例如: 第三周动态规划专项练习)")
    type = Column(String(20), nullable=False, default="practice", comment="模式: practice (练习模式，多次提交看结果) / exam (考试模式，单次交卷)")
    start_time = Column(DateTime, nullable=False, comment="开始允许作答时间")
    end_time = Column(DateTime, nullable=False, comment="截止交卷时间")
    created_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="发布该作业的教师用户ID")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, comment="作业创建时间")

    # 关联关系
    clazz = relationship("Class", back_populates="assignments")
    creator = relationship("User", foreign_keys=[created_by])
    problems = relationship("Problem", back_populates="assignment", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="assignment", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Assignment(id={self.id}, title='{self.title}', type='{self.type}')>"
