@echo off
chcp 936 >nul
REM ============================================================
REM  构建 Windows 7 兼容版（一键绿色 EXE）
REM  前提：本机装有 Python 3.8/3.9（vendor/wheels 内含两版离线依赖）
REM  产物：dist\狸猫猫表单.exe —— 拷到 Win7 机器双击即可运行
REM ============================================================

where py >nul 2>nul || (echo [错误] 未找到 Python 启动器 py.exe，请先安装 python.org 的 Python 3.9.13 & pause & exit /b 1)
py -3.9 -c "import sys; print(sys.version)" 2>nul || py -3.8 -c "import sys; print(sys.version)" 2>nul || (echo [错误] 未找到 Python 3.8/3.9，请先安装 python.org 的对应版本 & pause & exit /b 1)

if not exist venv-win7 (
    echo [1/4] 创建 Python 3.9 虚拟环境...
    py -3.9 -m venv venv-win7 2>nul || py -3.8 -m venv venv-win7
)
call venv-win7\Scripts\activate.bat

echo [2/4] 安装依赖（优先使用离线 wheel）...
if exist vendor\wheels (
    pip install --no-index --find-links vendor\wheels -r requirements-win7.txt pyinstaller==5.13.2
    if errorlevel 1 pip install -r requirements-win7.txt pyinstaller==5.13.2
) else (
    pip install -r requirements-win7.txt pyinstaller==5.13.2
)

echo [3/4] 打包（onefile 单文件 EXE）...
pyinstaller --noconfirm --clean --onefile --windowed --name "狸猫猫表单" --icon app\resources\icons\app.ico main.py

echo [4/4] 完成！
echo.
echo EXE 位于 dist\狸猫猫表单.exe
echo 部署到 Windows 7：详见 docs\Windows7-离线部署.md
pause

