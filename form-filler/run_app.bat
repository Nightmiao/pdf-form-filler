@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

REM ============================================================
REM  狸猫猫表单 — 一键启动（自动使用项目自带的虚拟环境 venv）
REM ============================================================

if /i "%~1"=="check" (
    echo [检查] 当前目录: %CD%
    if exist "venv\Scripts\pythonw.exe" (echo [检查] 找到虚拟环境 venv) else (echo [检查] 未找到虚拟环境)
    goto :eof
)

if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" main.py
    exit /b 0
)

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" main.py
    exit /b %errorlevel%
)

echo.
echo 未找到虚拟环境 venv，改用系统 Python 启动...
echo 若提示 ModuleNotFoundError: PySide6，请按 README 创建虚拟环境并安装依赖。
echo.
python main.py
if errorlevel 1 (
    echo.
    echo 启动失败。也可以直接运行打包好的 EXE：dist 目录下的程序。
    pause
)
