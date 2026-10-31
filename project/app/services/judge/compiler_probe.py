"""
文件名: compiler_probe.py
功能描述: 编译器智能双模自适应探针模块，负责探测并定位可用的 g++ 编译器的绝对路径。
遵循规范: 全部路径与模式均外部化到 config 配置；优先探测系统 PATH 中的 g++，未配置时平滑降级到项目内置便携编译器。
"""

import shutil
from pathlib import Path
from typing import Optional

from app.core.config import settings


class CompilerProbe:
    """
    编译器双模自适应探针类
    负责根据全局配置的工作模式，定位 C++ 编译器 g++ 的可执行文件绝对路径。
    支持三种模式:
        - auto:    优先探测系统环境变量 g++，未找到则降级使用项目内置便携版 (默认)
        - system:  强制仅使用操作系统环境已安装的 g++
        - builtin: 强制仅使用项目内置便携绿色版
    """

    def __init__(self) -> None:
        """初始化探针，惰性缓存探测结果以避免重复损耗"""
        self._system_gxx: Optional[str] = None      # 缓存系统环境 g++ 路径
        self._builtin_gxx: Optional[str] = None     # 缓存项目内置 g++ 路径

    def find_system_compiler(self) -> Optional[str]:
        """
        探测操作系统环境变量中的 g++ 编译命令

        返回:
            Optional[str]: 若系统环境存在 g++ 则返回其绝对路径，否则返回 None
        """
        if self._system_gxx is None:
            # 通过 shutil.which 沿系统 PATH 查找 g++ 可执行文件
            self._system_gxx = shutil.which("g++")
        return self._system_gxx

    def find_builtin_compiler(self) -> Optional[str]:
        """
        探测项目内置便携绿色编译器的绝对路径 (project/compiler/bin/ 目录)

        返回:
            Optional[str]: 若内置编译器存在则返回其绝对路径，否则返回 None
        """
        if self._builtin_gxx is None:
            gxx_name = "g++.exe" if shutil.os.name == "nt" else "g++"
            # 若显式配置了纯 ASCII 路径的编译器目录(规避中文路径下 GNU ld 编码缺陷)，则优先使用
            ascii_dir = (settings.BUILTIN_COMPILER_ASCII_DIR or "").strip()
            if ascii_dir:
                ascii_bin = Path(ascii_dir) / gxx_name
                if ascii_bin.exists():
                    self._builtin_gxx = str(ascii_bin)
                    return self._builtin_gxx
            # 从当前文件逐级上溯到 project 根目录，再拼接配置的内置编译器二进制子目录
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            builtin_dir = project_root / settings.BUILTIN_COMPILER_BIN_DIR
            if settings.BUILTIN_COMPILER_BIN_DIR and builtin_dir.exists():
                builtin_bin = builtin_dir / gxx_name
                self._builtin_gxx = str(builtin_bin) if builtin_bin.exists() else None
        return self._builtin_gxx

    def resolve_compiler(self) -> str:
        """
        依据全局配置的 COMPILER_PROBE_MODE 决策并返回最终可用的编译器路径

        返回:
            str: 可用的 g++ 编译器绝对路径
        """
        mode = (settings.COMPILER_PROBE_MODE or "auto").strip().lower()

        # 强制系统模式: 只允许系统环境 g++
        if mode == "system":
            system_path = self.find_system_compiler()
            if system_path:
                return system_path
            builtin_path = self.find_builtin_compiler()
            if builtin_path:
                return builtin_path
            # 双模式均缺失时抛出明确异常供上层捕获
            raise RuntimeError("未检测到可用的 C++ 编译器 (系统模式)，请先安装 g++ 或配置内置编译器")

        # 强制内置模式: 只允许项目内置便携版
        if mode == "builtin":
            builtin_path = self.find_builtin_compiler()
            if builtin_path:
                return builtin_path
            system_path = self.find_system_compiler()
            if system_path:
                return system_path
            raise RuntimeError("未检测到可用的内置编译器 (builtin 模式)，请先放置项目内置 g++")

        # 默认 auto 模式: 优先系统 g++，缺失时平滑降级到内置便携版
        system_path = self.find_system_compiler()
        if system_path:
            return system_path

        builtin_path = self.find_builtin_compiler()
        if builtin_path:
            return builtin_path

        raise RuntimeError("未检测到可用的 C++ 编译器 (auto 模式)，系统 g++ 与内置编译器均不存在")

    def get_compiler(self) -> str:
        """
        对外统一入口: 获取当前可用的 C++ 编译器绝对路径

        返回:
            str: 可用的 g++ 编译器路径
        """
        return self.resolve_compiler()

    def probe_status(self) -> dict:
        """
        返回编译器探针的可用状态概览 (供诊断接口使用)

        返回:
            dict: 包含工作模式与系统/内置编译器是否存在的信息字典
        """
        return {
            "mode": settings.COMPILER_PROBE_MODE or "auto",
            "system_compiler_available": self.find_system_compiler() is not None,
            "builtin_compiler_available": self.find_builtin_compiler() is not None,
            "resolved_compiler": self.resolve_compiler(),
        }