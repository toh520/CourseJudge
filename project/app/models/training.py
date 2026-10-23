"""
文件名: training.py
功能描述: 学生专属强化训练题数据模型实体。
遵循规范: 承载根据考后薄弱知识点由 AI 针对性动态生成的强化题目，归档于学生个人专属题本。
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class TrainingProblem(Base):
    """
    专属强化训练题实体类
    对应数据库表: training_problems
    """
    __tablename__ = "training_problems"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="强化题目主键ID")
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="归属学生用户ID")
    source_assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True, comment="来源作业/考试ID")
    knowledge_tag = Column(String(50), nullable=False, index=True, comment="所针对强化的薄弱知识点标签 (如: 动态规划-状态转移)")
    title = Column(String(100), nullable=False, comment="强化题目标题")
    description = Column(Text, nullable=False, comment="题目描述 Markdown")
    sample_input = Column(Text, nullable=True, comment="样例输入")
    sample_output = Column(Text, nullable=True, comment="样例输出")
    test_cases_json = Column(Text, nullable=False, comment="配套的隐藏测试用例集 (JSON 字符串格式存储输入输出)")
    best_status = Column(String(20), default="Unsolved", nullable=False, comment="学生在该题的历史最佳状态: Unsolved / AC / WA / TLE")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, comment="强化题生成时间")

    # 关联关系
    student = relationship("User", foreign_keys=[student_id])
    source_assignment = relationship("Assignment", foreign_keys=[source_assignment_id])

    def __repr__(self) -> str:
        return f"<TrainingProblem(id={self.id}, student_id={self.student_id}, tag='{self.knowledge_tag}')>"
