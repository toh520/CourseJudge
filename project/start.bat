@echo off
chcp 65001 >nul
title CourseJudge 团队开发一键启动与环境初始化工具

echo ==============================================================================
echo           CourseJudge 智能代码判题系统 - 团队协同快速启动
echo ==============================================================================
echo.

:: 1. 检查当前目录下是否存在 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 本机未检测到 Python 运行环境！
    echo 请先安装 Python 3.10 或更高版本，并勾选 "Add Python to PATH"。
    echo.
    pause
    exit /b 1
)

:: 2. 检查或创建虚拟环境 .venv
if not exist ".venv\Scripts\python.exe" (
    echo [1/5] 未检测到虚拟环境，正在自动为团队成员创建 .venv ...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [错误] 虚拟环境创建失败，请检查 Python 安装权限。
        pause
        exit /b 1
    )
    echo [1/5] 虚拟环境创建成功！
) else (
    echo [1/5] 检测到已存在虚拟环境 .venv。
)

:: 3. 自动同步并安装 requirements.txt 依赖 (使用清华镜像加速)
echo [2/5] 正在检查并同步项目依赖包 (使用国内清华镜像源加速)...
.venv\Scripts\pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet
if %errorlevel% neq 0 (
    echo [警告] 依赖自动同步出现警告，正在尝试重试...
    .venv\Scripts\pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)
echo [2/5] 依赖检查与同步完成！

:: 4. 检查 .env 配置文件，若无则自动从模板初始化
echo [3/5] 正在检查环境配置文件...
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo [提示] 检测到首次运行，已自动从 .env.example 生成本地 .env 配置文件！
        echo [提示] 如需体验 AI 智能功能，请用记事本打开 .env 填入你的大模型 API Key。
    )
) else (
    echo [3/5] 本地 .env 配置文件已就绪。
)

:: 5. 确保本地目录结构并同步数据快照
if not exist "storage\temp_judge" mkdir "storage\temp_judge"
echo [4/5] 正在检查团队共享数据快照并执行同步...
if exist "storage\data_snapshot.json" (
    .venv\Scripts\python -m app.core.seed --sync
) else (
    .venv\Scripts\python -m app.core.seed --init
)

:: 6. 启动系统客户端
echo [5/5] 正在启动 CourseJudge...
echo ==============================================================================
if exist "run.py" (
    echo 服务准备就绪，即将打开原生桌面窗口，请稍候...
    echo 提示: 如需停止运行，直接关闭桌面窗口或在当前终端按 Ctrl + C。
    echo ==============================================================================
    echo.
    .venv\Scripts\python run.py
) else (
    echo [提示] 启动成功后请在浏览器访问: http://127.0.0.1:8000/ui/
    echo [提示] 如需停止运行，请在当前终端按 Ctrl + C。
    echo ==============================================================================
    echo.
    .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
)

if %errorlevel% neq 0 (
    echo.
    echo [提示] 应用程序已退出。如果运行中发生异常，请检查上方日志。
    pause
)
