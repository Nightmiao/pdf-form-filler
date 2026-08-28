# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path

# 收集 PyMuPDF 的 C 扩展文件
import pymupdf as _pymupdf
import os as _os
_pymupdf_dir = _os.path.dirname(_pymupdf.__file__)
_pymupdf_binaries = []
for _f in _os.listdir(_pymupdf_dir):
    if _f.endswith(('.pyd', '.dll')):
        _pymupdf_binaries.append((_os.path.join(_pymupdf_dir, _f), 'pymupdf'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_pymupdf_binaries,
    datas=[
        ('app/resources', 'app/resources'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtPrintSupport',
        'fitz',
        'pymupdf',
        'pymupdf._mupdf',
        'pymupdf._extra',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='狸猫猫的表单填写工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    arguments=[],
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app/resources/icons/app.ico',
)

# 收集所有文件到 onedir 输出文件夹
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='狸猫猫的表单填写工具',
)
