@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo  狸猫猫的表单填写工具 - MSI 构建脚本
echo ============================================
echo.

set "PROJECT_DIR=%~dp0"
set "VENV=%PROJECT_DIR%venv"
set "SPEC_FILE=%PROJECT_DIR%form-filler.spec"
set "ICON_SCRIPT=%PROJECT_DIR%generate_icon.py"
set "INSTALLER_DIR=%PROJECT_DIR%installer"
set "STAGING_DIR=%INSTALLER_DIR%\staging\FormFillerApp"
set "DIST_DIR=%PROJECT_DIR%dist"

echo [1/5] 激活虚拟环境并安装 PyInstaller...
call "%VENV%\Scripts\activate.bat"
pip install pyinstaller -q 2>nul

echo [2/5] 生成应用图标...
python "%ICON_SCRIPT%"

echo [3/5] PyInstaller 打包...
rmdir /s /q "%DIST_DIR%" 2>nul
rmdir /s /q "%PROJECT_DIR%build" 2>nul
pyinstaller --clean "%SPEC_FILE%"

if not exist "%DIST_DIR%\狸猫猫的表单填写工具\狸猫猫的表单填写工具.exe" (
    echo 错误: PyInstaller 构建失败！
    exit /b 1
)

echo [4/5] 准备 WiX 打包目录...
rmdir /s /q "%STAGING_DIR%" 2>nul
mkdir "%STAGING_DIR%" 2>nul
xcopy "%DIST_DIR%\狸猫猫的表单填写工具\*" "%STAGING_DIR%\" /E /Q /Y

echo [5/5] WiX 构建 MSI...
wix build -arch x64 -d "StagingDir=%STAGING_DIR%" -o "%INSTALLER_DIR%\form-filler.msi" "%INSTALLER_DIR%\form-filler.wxs" "%INSTALLER_DIR%\app-components.wxs" -nologo

if %ERRORLEVEL% NEQ 0 (
    echo 错误: WiX 构建失败！
    exit /b 1
)

echo.
echo ============================================
echo  构建成功！
echo  输出: %INSTALLER_DIR%\form-filler.msi
echo ============================================
for %%F in ("%INSTALLER_DIR%\form-filler.msi") do echo  大小: %%~zF 字节
echo.

pause
