"""
文件名: system.py
功能描述: 系统级状态与健康检查路由。返回当前编译器智能双模探针的命中模式
          与判题服务就绪状态，供前端启动自检与运维诊断使用。
遵循规范: 复用 CompilerProbe.probe_status()（永不抛异常），保证未装编译器时
          接口仍返回 200 并携带 ready=False 快照。
"""

from fastapi import APIRouter

from app.services.judge.compiler_probe import CompilerProbe

router = APIRouter()

# 编译器探针单例（探测结果带懒加载缓存，跨请求复用避免重复检测）
_compiler_probe = CompilerProbe()


@router.get("/system/status", summary="系统与编译器就绪状态")
def get_system_status() -> dict:
    """
    获取系统当前就绪状态

    返回:
        dict: 含服务版本、编译器探针模式、系统/内置编译器可用性、解析路径与就绪标记
    """
    status_payload = _compiler_probe.probe_status()
    return {
        "service": "course-judge",
        "status": "ok",
        "compiler_probe": status_payload,
    }