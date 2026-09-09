# -*- coding: utf-8 -*-
"""狸猫猫表单 安装器 — 双击即装：解压程序文件 + 创建桌面快捷方式 + 可选启动

运行环境目标：离线 Windows 7（Python 3.8 / 仅标准库 + ctypes）。
打包：pyinstaller --onefile --windowed --add-data <载荷> make_installer.py

测试钩子：设置环境变量 LMM_SILENT=1 跳过全部弹窗与启动；
LMM_TARGET 指定安装目录（默认 %LOCALAPPDATA%\\狸猫猫表单）；
LMM_LNKDIR 指定快捷方式目录（默认桌面）。
"""

import os
import sys
import shutil
import subprocess
import tempfile

APP_EXE = "LiuMaoMao.exe"
README = "readme.txt"
UNINSTALL = "uninstall.bat"
LNK_NAME = "狸猫猫表单.lnk"


def resource(name: str) -> str:
    """取打包进 EXE 的载荷文件路径（PyInstaller onefile 解到 _MEIPASS）"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def msg(text: str, title: str = "狸猫猫表单", style: int = 0) -> int:
    """Win7/Win10/11 通用消息框（ctypes，无第三方依赖）"""
    import ctypes
    return ctypes.windll.user32.MessageBoxW(0, text, title, style)


def make_shortcut(target_exe: str, lnk_dir: str) -> str:
    """用临时 VBS 创建快捷方式（cscript 在 Win7 一定存在，最可靠）"""
    vbs = os.path.join(tempfile.gettempdir(), "lmm_setup_%d.vbs" % os.getpid())
    lnk_path = os.path.join(lnk_dir, LNK_NAME)
    with open(vbs, "w", encoding="gbk") as f:
        f.write(
            'Set ws = CreateObject("WScript.Shell")\n'
            'Set fso = CreateObject("Scripting.FileSystemObject")\n'
            'folder = "%s"\n'
            'If LCase(folder) = "desktop" Then folder = ws.SpecialFolders("Desktop")\n'
            'If Not fso.FolderExists(folder) Then fso.CreateFolder folder\n'
            'Set lnk = ws.CreateShortcut(folder & "\\%s")\n'
            'lnk.TargetPath = "%s"\n'
            'lnk.WorkingDirectory = "%s"\n'
            'lnk.IconLocation = "%s, 0"\n'
            'lnk.Description = "狸猫猫表单 - PDF 表单填写工具"\n'
            'lnk.Save\n'
            % (lnk_dir, LNK_NAME, target_exe, os.path.dirname(target_exe), target_exe)
        )
    try:
        subprocess.run(
            ["cscript", "//nologo", vbs],
            creationflags=0x08000000,  # CREATE_NO_WINDOW
            timeout=30, check=False,
        )
    finally:
        try:
            os.remove(vbs)
        except OSError:
            pass
    return lnk_path


def main():
    silent = os.environ.get("LMM_SILENT") == "1"
    target = os.environ.get("LMM_TARGET") or os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "狸猫猫表单"
    )
    lnk_dir = os.environ.get("LMM_LNKDIR", "desktop")

    src_exe = resource(APP_EXE)
    if not os.path.exists(src_exe):
        if not silent:
            msg("安装文件不完整，请重新下载安装包。", style=0x10)
        sys.exit(1)

    # 已在运行的旧实例会锁文件 —— 提示用户先关闭
    try:
        os.makedirs(target, exist_ok=True)
        dst_exe = os.path.join(target, "狸猫猫表单.exe")
        shutil.copy2(src_exe, dst_exe)
        shutil.copy2(resource(README), os.path.join(target, "使用说明.txt"))
        shutil.copy2(resource(UNINSTALL), os.path.join(target, "卸载.bat"))
    except (OSError, shutil.Error) as e:
        if not silent:
            msg(
                "安装失败，文件被占用或没有写入权限：\n%s\n\n"
                "如果程序正在运行，请先关闭后重试。" % e, style=0x10,
            )
        sys.exit(1)

    lnk_path = make_shortcut(dst_exe, lnk_dir)

    if silent:
        print("installed:", target)
        print("shortcut:", lnk_path, "exists:", os.path.exists(lnk_path))
        return

    # 询问是否立即启动（默认回车=是）
    rc = msg(
        "安装完成！\n\n"
        "程序位置：%s\n桌面快捷方式已创建。\n\n"
        "现在启动「狸猫猫表单」吗？" % target,
        style=0x40 | 0x1,  # 信息图标 + 确定取消
    )
    if rc == 1:
        os.startfile(dst_exe)


if __name__ == "__main__":
    main()
