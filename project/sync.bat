@echo off
chcp 65001 >nul
title CourseJudge 团队依赖与数据库一键同步工具

echo ==============================================================================
echo           CourseJudge 智能代码判题系统 - 团队环境与数据协同同步
echo ==============================================================================
echo.

:: 1. 检查 Python 运行环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 本机未检测到 Python 运行环境！
    echo 请先安装 Python 3.10 或更高版本，并勾选 "Add Python to PATH"。
    pause
    exit /b 1
)

:: 2. 检查或创建虚拟环境
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] 正在为团队成员自动创建 .venv 虚拟环境...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [错误] 虚拟环境创建失败，请检查安装权限。
        pause
        exit /b 1
    )
    echo [1/3] 虚拟环境创建完成！
) else (
    echo [1/3] 虚拟环境 .venv 已就绪。
)

:: 3. 检查并同步 Python 依赖库 (清华镜像源加速)
echo [2/3] 正在通过国内清华源检查并同步最新依赖包 (requirements.txt)...
.venv\Scripts\pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet
if %errorlevel% neq 0 (
    echo [警告] 依赖静默安装出现波动，正在重试...
    .venv\Scripts\pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)
echo [2/3] 环境依赖同步完成！

:: 4. 检查 .env 配置文件
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo [提示] 检测到本地无 .env，已自动从 .env.example 生成配置文件！
    )
)

:: 5. 同步数据库数据 (从团队共享数据快照 data_snapshot.json 导入)
echo [3/3] 正在将团队共享的题目、班级与测试数据同步到本地 SQLite 数据库...
.venv\Scripts\python -m app.core.seed --sync
if %errorlevel% neq 0 (
    echo [警告] 数据同步出现异常，请检查上方提示。
) else (
    echo [3/3] 本地数据库数据同步成功！
)

echo.
echo ==============================================================================
echo [恭喜] 团队环境依赖与本地数据库已全部同步完成！
echo 默认教师账号: teacher / 密码: 123456
echo 默认学生账号: student / 密码: 123456
echo 现在可以直接双击 "start.bat" 或根目录 "一键启动.bat" 开启系统！
echo ==============================================================================
echo.
pause
