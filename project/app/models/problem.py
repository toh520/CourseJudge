"""
文件名: problem.py
功能描述: 算法题目与测试用例数据模型实体。
遵循规范: 题目直接归属于作业清单，无杂乱公共冗余库；每道题目关联多组结构化测试输入输出用例。
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Problem(Base):
    """
    题目实体类
    对应数据库表: problems
    """
    __tablename__ = "problems"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="题目主键ID")
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True, comment="归属作业/考试ID")
    title = Column(String(100), nullable=False, comment="题目标题")
    description = Column(Text, nullable=False, comment="题面描述 (Markdown格式)")
    input_format = Column(Text, nullable=True, comment="输入格式说明")
    output_format = Column(Text, nullable=True, comment="输出格式说明")
    sample_input = Column(Text, nullable=True, comment="题面公开样例输入")
    sample_output = Column(Text, nullable=True, comment="题面公开样例输出")
    time_limit_ms = Column(Integer, default=1000, nullable=False, comment="时间限制毫秒数 (默认 1000ms)")
    memory_limit_mb = Column(Integer, default=256, nullable=False, comment="内存限制MB数 (默认 256MB)")
    knowledge_tag = Column(String(50), nullable=True, index=True, comment="题目核心考查知识点 (如: 动态规划, 二叉树)")
    is_ai_generated = Column(Boolean, default=False, nullable=False, comment="是否由 AI 辅助生成")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, comment="题目创建时间")

    # 关联关系
    assignment = relationship("Assignment", back_populates="problems")
    test_cases = relationship("TestCase", back_populates="problem", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="problem", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Problem(id={self.id}, title='{self.title}', tag='{self.knowledge_tag}')>"


class TestCase(Base):
    """
    测试用例实体类
    对应数据库表: test_cases
    """
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="测试用例主键ID")
    problem_id = Column(Integer, ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True, comment="归属题目ID")
    input_data = Column(Text, nullable=False, comment="用例输入数据文本 (喂入标准输入 stdin)")
    output_data = Column(Text, nullable=False, comment="期望标准输出文本 (对比标准输出 stdout)")
    score_weight = Column(Integer, default=10, nullable=False, comment="该用例分值权重 (用于汇总百分比得分)")

    # 关联关系
    problem = relationship("Problem", back_populates="test_cases")

    def __repr__(self) -> str:
        return f"<TestCase(id={self.id}, problem_id={self.problem_id}, weight={self.score_weight})>"
