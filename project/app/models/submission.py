"""
文件名: submission.py
功能描述: 学生代码提交与判题记录数据模型实体。
遵循规范: 完整保存学生提交的 C++ 源码、得分、运行耗时、状态码与编译报错信息。
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Submission(Base):
    """
    提交记录实体类
    对应数据库表: submissions
    """
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="提交记录主键ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="提交学生用户ID")
    problem_id = Column(Integer, ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True, comment="对应题目ID")
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True, comment="所属作业ID")
    code = Column(Text, nullable=False, comment="提交的 C++ 源代码")
    status = Column(String(30), nullable=False, default="Pending", comment="评测最终状态: AC (通过) / WA (答案错误) / TLE (超时) / RE (运行崩溃) / CE (编译错误)")
    score = Column(Integer, default=0, nullable=False, comment="本次提交判题得分 (0~100)")
    time_used_ms = Column(Integer, default=0, nullable=False, comment="所有测试用例中的最大运行耗时 (毫秒)")
    compiler_output = Column(Text, nullable=True, comment="g++ 编译器标准错误输出 (主要用于 CE 时回显语法报错日志)")
    is_final = Column(Boolean, default=False, nullable=False, comment="考试模式下是否为最终交卷判分记录")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, comment="代码提交时间")

    # 关联关系
    student = relationship("User", foreign_keys=[user_id])
    problem = relationship("Problem", back_populates="submissions")
    assignment = relationship("Assignment", back_populates="submissions")

    def __repr__(self) -> str:
        return f"<Submission(id={self.id}, user_id={self.user_id}, status='{self.status}', score={self.score})>"
