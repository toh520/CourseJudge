"""
文件名: clazz.py
功能描述: 班级与班级成员关联数据模型实体。
遵循规范: 支撑教师建班生成邀请码、学生输入邀请码加入班级的核心教学组织关系。
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


class Class(Base):
    """
    班级实体类
    对应数据库表: classes
    """
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="班级主键ID")
    name = Column(String(100), nullable=False, comment="班级全称 (例如: 2024级计算机1班程序设计)")
    invite_code = Column(String(10), unique=True, nullable=False, index=True, comment="6位随机唯一班级邀请码")
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="创建该班级的教师用户ID")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, comment="班级创建时间")

    # 关联关系
    teacher = relationship("User", foreign_keys=[teacher_id])
    members = relationship("ClassMember", back_populates="clazz", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="clazz", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Class(id={self.id}, name='{self.name}', invite_code='{self.invite_code}')>"


class ClassMember(Base):
    """
    班级成员关联实体类
    对应数据库表: class_members
    """
    __tablename__ = "class_members"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="关联主键ID")
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True, comment="所属班级ID")
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="加入班级的学生用户ID")
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, comment="学生加入班级时间")

    # 关联关系
    clazz = relationship("Class", back_populates="members")
    student = relationship("User", foreign_keys=[student_id])

    # 唯一性约束: 一个学生在一个班级只能有一条加入记录
    __table_args__ = (
        UniqueConstraint("class_id", "student_id", name="uq_class_student"),
    )

    def __repr__(self) -> str:
        return f"<ClassMember(class_id={self.class_id}, student_id={self.student_id})>"
