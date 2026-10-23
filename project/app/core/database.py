"""
文件名: database.py
功能描述: 数据库持久层引擎与会话工厂模块。
遵循规范: 采用 SQLAlchemy 2.0 ORM，屏蔽底层数据库方言差异；默认连接单文件 SQLite，开箱即用。
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings

# 构造数据库引擎连接参数
# SQLite 在多线程访问时需要指定 check_same_thread=False
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

# 创建 SQLAlchemy 引擎单例
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False  # 若调试 SQL 可置为 True
)

# 创建线程安全的会话工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# ORM 实体声明式基类
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI 依赖注入生成器: 获取独立的数据库会话

    产生:
        Session: 当前请求生命周期内的 SQLAlchemy 会话对象
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    数据库初始化函数
    自动扫描所有已注册的 ORM 实体模型，并在目标数据库中创建不存在的数据表。
    """
    # 动态导入所有模型，确保 Base.metadata 能够收集到全部表定义
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
