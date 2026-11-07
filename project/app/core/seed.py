"""
文件名: seed.py
功能描述: 首次启动演示账号初始化。当 users 表为空时创建教师/学生演示账号，
          便于课设答辩与团队成员开箱即用；已有任何用户时不做任何修改。
遵循规范: 账号与密码全部来自 config 配置，代码中不硬编码业务凭据。
"""

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import User


def seed_demo_accounts() -> None:
    """
    在用户表为空时创建演示账号

    该函数是幂等的：只要数据库中已存在任意用户，就直接返回，不会覆盖真实数据。
    """
    if not settings.SEED_DEMO_ACCOUNTS:
        return

    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return

        db.add(User(
            username=settings.DEMO_TEACHER_USERNAME,
            real_name="演示教师",
            password=settings.DEMO_TEACHER_PASSWORD,
            role="teacher",
        ))
        db.add(User(
            username=settings.DEMO_STUDENT_USERNAME,
            real_name="演示学生",
            password=settings.DEMO_STUDENT_PASSWORD,
            role="student",
        ))
        db.commit()
    finally:
        db.close()