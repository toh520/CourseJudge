@echo off
chcp 65001 >nul
:: CourseJudge 根目录快捷一键导出数据快照脚本
cd /d "%~dp0project"
call export_data.bat
