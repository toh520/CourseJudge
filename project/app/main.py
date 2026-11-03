"""
文件名: main.py
功能描述: CourseJudge FastAPI 应用入口。汇聚 API 层全部路由模块，统一挂载到
          /api/v1 前缀，并暴露 Swagger(/docs) 与健康检查。
遵循规范: 复用 config.API_V1_PREFIX；服务启动时初始化数据库表并注册各业务路由。
"""

from fastapi import FastAPI

from app.core.config import settings
from app.core.database import init_db
from app.api import auth, classes, assignments, judge, training, dashboard, llm, system

# 服务启动时创建缺失的数据表（幂等）
init_db()

# 创建 FastAPI 应用实例
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="CourseJudge 智能代码判题与教学辅助系统 - RESTful API",
)


# 注册全部业务路由
app.include_router(system.router, prefix=settings.API_V1_PREFIX, tags=["系统状态"])
app.include_router(auth.router, prefix=settings.API_V1_PREFIX, tags=["认证"])
app.include_router(classes.router, prefix=settings.API_V1_PREFIX, tags=["班级管理"])
app.include_router(assignments.router, prefix=settings.API_V1_PREFIX, tags=["作业编排"])
app.include_router(judge.router, prefix=settings.API_V1_PREFIX, tags=["判题提交"])
app.include_router(training.router, prefix=settings.API_V1_PREFIX, tags=["专属训练"])
app.include_router(dashboard.router, prefix=settings.API_V1_PREFIX, tags=["学情大屏"])
app.include_router(llm.router, prefix=settings.API_V1_PREFIX, tags=["AI 能力"])


@app.get("/", summary="服务根路径")
def root() -> dict:
    """根路径提示，引导访问 /docs 文档"""
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "status": "ok",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)