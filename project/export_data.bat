@echo off
chcp 65001 >nul
title CourseJudge 团队数据快照导出工具

echo ==============================================================================
echo           CourseJudge 智能代码判题系统 - 团队数据快照导出
echo ==============================================================================
echo.
echo 正在将您本地的班级、作业、题目及测试用例导出为共享快照...
echo 导出目标: storage\data_snapshot.json
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未检测到 .venv 虚拟环境，请先运行 sync.bat 初始化环境。
    pause
    exit /b 1
)

.venv\Scripts\python -m app.core.seed --export

if %errorlevel% equ 0 (
    echo.
    echo ==============================================================================
    echo [成功] 数据快照导出成功！
    echo 请执行 git add storage\data_snapshot.json 并提交推送，即可与团队队友共享！
    echo ==============================================================================
) else (
    echo [错误] 导出失败，请查看上方日志。
)
echo.
pause
