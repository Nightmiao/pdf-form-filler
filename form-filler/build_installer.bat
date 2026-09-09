@echo off
chcp 936 >nul
setlocal
rem ============================================================
rem  一键构建离线安装包（两步：应用 EXE + 安装器 EXE）
rem  产物: dist-win7\狸猫猫表单.exe（绿色版）
rem        dist-win7\狸猫猫表单离线安装包.exe（双击安装+桌面快捷方式）
rem  前提: 本机装有 Python 3.8/3.9（首次构建先运行 build_win7.bat 装好 venv-win7）
rem ============================================================

call venv-win7\Scripts\activate.bat

echo [1/3] 构建应用单文件 EXE...
pyinstaller --noconfirm --clean --onefile --windowed --name "狸猫猫表单" --icon app\resources\icons\app.ico --distpath dist-win7 --workpath build-win7 main.py
if errorlevel 1 (echo [错误] 应用 EXE 构建失败 & pause & exit /b 1)

echo [2/3] 组装安装器载荷...
copy /y "dist-win7\狸猫猫表单.exe" "installer\sfx-payload\LiuMaoMao.exe" >nul

echo [3/3] 构建离线安装包...
pyinstaller --noconfirm --clean --onefile --windowed --name LMM-Setup --icon app\resources\icons\app.ico --distpath installer --workpath build-installer --add-data "installer\sfx-payload\LiuMaoMao.exe;." --add-data "installer\sfx-payload\readme.txt;." --add-data "installer\sfx-payload\uninstall.bat;." installer\make_installer.py
if errorlevel 1 (echo [错误] 安装包构建失败 & pause & exit /b 1)

copy /y "installer\LMM-Setup.exe" "dist-win7\狸猫猫表单离线安装包.exe" >nul
echo.
echo 构建完成！
echo   绿色版:   dist-win7\狸猫猫表单.exe
echo   安装包:   dist-win7\狸猫猫表单离线安装包.exe
pause
