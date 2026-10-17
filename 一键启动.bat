@echo off
chcp 65001 >nul
:: CourseJudge 根目录快捷启动引导脚本
cd /d "%~dp0project"
call start.bat
