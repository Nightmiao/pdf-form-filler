@echo off
setlocal
cd /d "%~dp0"

REM ============================================================
REM  Form Filler - one click launcher
REM  Uses the project venv. ASCII only on purpose:
REM  Chinese/UTF-8 text in .bat breaks cmd.exe parsing on Windows 7.
REM ============================================================

set "LOG=%~dp0run_app.log"
echo [%date% %time%] launcher start, cwd=%CD% > "%LOG%"

if /i "%~1"=="check" (
    echo [check] cwd: %CD%
    if exist "venv\Scripts\pythonw.exe" (echo [check] venv found) else (echo [check] venv NOT found)
    goto :eof
)

if exist "venv\Scripts\pythonw.exe" (
    echo [%date% %time%] launching venv pythonw >> "%LOG%"
    start "" "venv\Scripts\pythonw.exe" main.py
    if errorlevel 1 (
        echo [ERROR] failed to launch venv pythonw >> "%LOG%"
        echo [ERROR] failed to launch venv pythonw & pause & exit /b 1
    )
    exit /b 0
)

if exist "venv\Scripts\python.exe" (
    echo [%date% %time%] launching venv python >> "%LOG%"
    "venv\Scripts\python.exe" main.py
    exit /b %errorlevel%
)

echo [%date% %time%] venv not found, fallback to system python >> "%LOG%"
echo.
echo venv not found. Trying system Python...
echo If you see ModuleNotFoundError: PySide6, create the venv per README first.
echo.
python main.py
if errorlevel 1 (
    echo.
    echo Failed. You can also run the packaged EXE in the dist folder.
    pause
)
