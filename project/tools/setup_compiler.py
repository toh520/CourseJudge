"""为 Windows x64 首次启动准备经校验的便携 C++ 工具链。"""

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.services.judge.compiler_probe import CompilerProbe

# 地址与摘要必须作为同一份上游发布清单成对更新。
VERSION = "2.11.0"
ARCHIVE_URL = f"https://github.com/skeeto/w64devkit/releases/download/v{VERSION}/w64devkit-x64-{VERSION}.7z.exe"
SHA256 = "54c2bb9962e8a30c8270e34c5efc3d5fee579f53087fa7d435b95fbba2af7b2b"


def prepare_compiler() -> None:
    """按当前探针配置准备工具链；已有环境直接返回，失败保留原目录。"""
    if CompilerProbe().probe_status()["ready"]:
        return
    if (os.name != "nt" or platform.machine().lower() not in {"amd64", "x86_64"}
            or settings.COMPILER_PROBE_MODE not in {"auto", "builtin"}
            or Path(settings.BUILTIN_COMPILER_BIN_DIR) != Path("compiler/bin")):
        raise RuntimeError("请按当前平台与配置准备 g++。")

    destination = PROJECT_ROOT / "compiler"
    if destination.exists():
        raise RuntimeError("compiler 目录已存在，请检查其中的 bin/g++.exe。")
    print("首次准备 C++ 编译器，下载约 66 MiB。", flush=True)
    with tempfile.TemporaryDirectory(prefix=".cj-toolchain-", dir=PROJECT_ROOT) as staging:
        work = Path(staging)
        download = work / "distribution.sfx"
        with urlopen(ARCHIVE_URL, timeout=30) as response, download.open("wb") as target:
            shutil.copyfileobj(response, target)
        digest = hashlib.sha256()
        with download.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != SHA256:
            raise RuntimeError("编译器下载校验失败，请重试。")

        # 仅解包已校验的 7z 内容，不运行自解压程序。
        with download.open("rb") as source, (work / "kit.7z").open("wb") as archive:
            offset = source.read(1024 * 1024).find(bytes.fromhex("377abcaf271c"))
            if offset < 0:
                raise RuntimeError("编译器压缩包格式不符。")
            source.seek(offset)
            shutil.copyfileobj(source, archive)
        subprocess.run(["tar.exe", "-xf", str(work / "kit.7z")], cwd=work, check=True)
        kit = work / "w64devkit"
        if not (kit / "bin" / "g++.exe").is_file():
            raise RuntimeError("压缩包中缺少 g++。")
        # 实时防护短暂持有新解压的 exe 时，Windows 可能拒绝目录重命名。
        for attempt in range(16):
            try:
                kit.rename(destination)
                break
            except PermissionError:
                if attempt == 15:
                    raise
                time.sleep(0.5)
        print("便携编译器已就绪。")


if __name__ == "__main__":
    try:
        prepare_compiler()
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"编译器准备失败：{exc}。可继续使用班级功能，之后重新启动重试。", file=sys.stderr)
        sys.exit(1)
