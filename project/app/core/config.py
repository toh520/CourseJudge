"""
文件名: config.py
功能描述: 系统全局配置管理模块，基于 Pydantic Settings 实现强类型环境变量读取。
遵循规范: 严格零硬编码，所有易变参数均由本地 .env 文件注入并提供合理默认值。
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    系统全局配置类
    负责加载环境变量与本地私密 .env 文件中的配置项
    """

    # --- 基础服务信息 ---
    PROJECT_NAME: str = "CourseJudge 智能代码判题与教学辅助系统"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    # --- 数据库持久层配置 (默认采用项目级单文件 SQLite，开箱即用) ---
    DATABASE_URL: str = "sqlite:///./course_judge.db"

    # --- 大语言模型 (LLM) API 配置 (遵循标准 OpenAI 兼容协议) ---
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_MODEL_NAME: str = "deepseek-chat"

    # --- 身份认证与安全参数 (明文密码配合轻量 JWT 令牌) ---
    SECRET_KEY: str = "course_judge_default_secret_key_change_me_in_prod"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # Token 默认有效期 24 小时 (1440分钟)
    ALGORITHM: str = "HS256"

    # --- 编译器智能双模探针参数 ---
    # auto: 优先系统环境变量 g++，兜底项目内置便携绿色版
    # builtin: 强制内置绿色版 | system: 强制系统环境版
    COMPILER_PROBE_MODE: str = "auto"
    BUILTIN_COMPILER_BIN_DIR: str = "compiler/bin"

    # --- 判题沙箱资源约束阈值 ---
    DEFAULT_TIME_LIMIT_MS: int = 1000       # 默认运行超时时间 1000 毫秒
    DEFAULT_MEMORY_LIMIT_MB: int = 256      # 默认运行内存限制 256 MB
    COMPILE_TIMEOUT_SECONDS: int = 10       # 编译阶段最长等待时间 10 秒

    # --- 存储路径 ---
    STORAGE_DIR: str = "storage"
    TEMP_JUDGE_DIR: str = "storage/temp_judge"
    TEST_CASES_DIR: str = "storage/test_cases"

    # Pydantic Settings 配置：指定读取上级或当前目录下的 .env 文件
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"  # 忽略多余的环境变量
    )


# 导出全局单例配置对象，业务模块统一通过 settings.XXX 进行访问
settings = Settings()
