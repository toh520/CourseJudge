"""
文件名: __init__.py
功能描述: 数据库实体模型统一聚合导出入口。
"""

from app.models.user import User
from app.models.clazz import Class, ClassMember
from app.models.assignment import Assignment
from app.models.problem import Problem, TestCase
from app.models.submission import Submission
from app.models.training import TrainingProblem
from app.models.chat import ChatMessage

__all__ = [
    "User",
    "Class",
    "ClassMember",
    "Assignment",
    "Problem",
    "TestCase",
    "Submission",
    "TrainingProblem",
    "ChatMessage",
]
