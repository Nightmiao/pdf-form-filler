"""Qt 兼容层 — 同一套代码同时支持两种环境

- 开发机：Python 3.10+ / PySide6 (Qt 6)
- 目标机（Windows 7 离线）：Python 3.9 / PySide2 5.15 (Qt 5)

所有界面代码一律从本模块导入 Qt 类与工具函数，
不要直接 import PySide6 / PySide2。

Windows 7 部署细节见 docs/Windows7-离线部署.md。
"""

from __future__ import annotations


try:
    from PySide6 import QtCore, QtGui, QtWidgets, QtPrintSupport
    QT6 = True
except ImportError:  # PySide2 目标环境
    from PySide2 import QtCore, QtGui, QtWidgets, QtPrintSupport
    QT6 = False

if QT6:
    Qt = QtCore.Qt
    QAction = QtGui.QAction

    def dialog_exec(d):
        return d.exec()

    def menu_exec(menu, pos):
        return menu.exec(pos)

else:
    class _Scoped:
        """把 Qt5 的非作用域枚举伪装成 Qt6 风格的作用域枚举"""

        def __init__(self, base):
            self._base = base

        def __getattr__(self, name):
            return getattr(self._base, name)

    class _QtCompat:
        def __init__(self, base):
            self._base = base
            self.MouseButton = _Scoped(base)
            self.KeyboardModifier = _Scoped(base)
            self.KeyboardModifiers = _Scoped(base)
            self.AlignmentFlag = _Scoped(base)
            self.AspectRatioMode = _Scoped(base)
            self.CursorShape = _Scoped(base)
            self.ItemDataRole = _Scoped(base)
            self.Orientation = _Scoped(base)
            self.PenStyle = _Scoped(base)
            self.ScrollBarPolicy = _Scoped(base)
            self.TransformationMode = _Scoped(base)
            self.WidgetAttribute = _Scoped(base)
            self.ContextMenuPolicy = _Scoped(base)
            self.FocusPolicy = _Scoped(base)
            self.WindowType = _Scoped(base)
            self.MatchFlag = _Scoped(base)
            self.Key = _Scoped(base)  # Qt.Key.Key_PageUp → Qt.Key_PageUp

        def __getattr__(self, name):
            return getattr(self._base, name)

    Qt = _QtCompat(QtCore.Qt)
    QAction = QtWidgets.QAction  # Qt5 里 QAction 在 QtWidgets

    def dialog_exec(d):
        return d.exec_()

    def menu_exec(menu, pos):
        return menu.exec_(pos)


def enum_of(owner, scoped_name, name):
    """owner.ScopedName.name（Qt6）或 owner.name（Qt5）"""
    try:
        return getattr(getattr(owner, scoped_name), name)
    except AttributeError:
        return getattr(owner, name)


# ── 常用枚举/工具（兼容两种 Qt）────────────────────────

def std_button(name):
    return enum_of(QtWidgets.QMessageBox, "StandardButton", name)

def msg_icon(name):
    return enum_of(QtWidgets.QMessageBox, "Icon", name)

def msg_button_role(name):
    return enum_of(QtWidgets.QMessageBox, "ButtonRole", name)

def dialog_accepted():
    return enum_of(QtWidgets.QDialog, "DialogCode", "Accepted")

def printer_high_resolution():
    return enum_of(QtPrintSupport.QPrinter, "PrinterMode", "HighResolution")

def printer_device_pixel():
    return enum_of(QtPrintSupport.QPrinter, "Unit", "DevicePixel")

def event_key_press():
    return enum_of(QtCore.QEvent, "Type", "KeyPress")

def standard_key(name):
    return enum_of(QtGui.QKeySequence, "StandardKey", name)

def size_policy(name):
    return enum_of(QtWidgets.QSizePolicy, "Policy", name)

def orientation(value):
    return QtCore.Qt.Orientation(value)

RENDER_ANTIALIASING = enum_of(QtGui.QPainter, "RenderHint", "Antialiasing")
RENDER_SMOOTH_PIXMAP = enum_of(QtGui.QPainter, "RenderHint", "SmoothPixmapTransform")
KEEP_ASPECT = enum_of(QtCore.Qt, "AspectRatioMode", "KeepAspectRatio")
DRAG_INTERNAL_MOVE = enum_of(QtWidgets.QAbstractItemView, "DragDropMode", "InternalMove")
ITEM_SELECTABLE = enum_of(QtWidgets.QGraphicsItem, "GraphicsItemFlag", "ItemIsSelectable")
ANCHOR_UNDER_MOUSE = enum_of(QtWidgets.QGraphicsView, "ViewportAnchor", "AnchorUnderMouse")
NO_DRAG = enum_of(QtWidgets.QGraphicsView, "DragMode", "NoDrag")
FULL_VIEWPORT_UPDATE = enum_of(QtWidgets.QGraphicsView, "ViewportUpdateMode", "FullViewportUpdate")
SHAPE_NO_FRAME = enum_of(QtWidgets.QFrame, "Shape", "NoFrame")
