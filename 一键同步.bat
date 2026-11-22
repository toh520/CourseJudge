@echo off
chcp 65001 >nul
:: CourseJudge 根目录快捷一键同步引导脚本
cd /d "%~dp0project"
call sync.bat
