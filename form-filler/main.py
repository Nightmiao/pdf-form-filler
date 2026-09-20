"""狸猫猫表单 — 程序入口

Windows 7 目标机适配要点：
- 目标机常见 1024x768 + 125% 缩放。若不声明 DPI 感知，系统会把整个界面
  虚拟化放大，逻辑分辨率变成约 819x614，比窗口最小尺寸还小，
  右侧属性面板会永久跑到屏幕外。所以必须在建 QApplication **之前**
  打开 DPI 感知（Qt5 用 AA_EnableHighDpiScaling，Qt6 默认已开）。
- 窗口尺寸从屏幕可用区域推导，不再硬编码 1280x800。
- `--diagnose` 生成自检报告（也可从首页「运行自检」按钮触发）。
"""

from __future__ import annotations


import sys
import os

from app.qt import QtWidgets, QtGui, QtCore, QT6

from app.ui.theme import APP_STYLESHEET
from app.ui.main_window import MainWindow


def enable_dpi_awareness():
    """在 QApplication 构造之前设置 DPI 策略（必须在最早时机调用）"""
    # 1) Windows 原生：让进程声明为 DPI 感知
    #    （Win7 不声明的话，125% 缩放下界面会被系统拉伸模糊，
    #     而且逻辑分辨率被虚拟化得比窗口最小尺寸还小）
    if sys.platform == "win32":
        try:
            import ctypes
            try:
                # PROCESS_PER_MONITOR_DPI_AWARE（Win8.1+）
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                # Win7 走老 API
                ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    # 2) Qt5 的自动缩放开关（Qt6 默认开启且该属性已废弃）
    if not QT6:
        try:
            QtWidgets.QApplication.setAttribute(
                QtCore.Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True
            )
            QtWidgets.QApplication.setAttribute(
                QtCore.Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True
            )
        except Exception:
            pass
    try:
        QtGui.QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception:
        pass


def get_data_dir() -> str:
    """获取用户数据目录"""
    home = os.path.expanduser("~")
    data_dir = os.path.join(home, ".form-filler", "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def preferred_window_size(app, min_w: int = 940, min_h: int = 600):
    """按屏幕可用区域决定初始窗口大小（1024x768 上不再开到屏幕外）"""
    try:
        screen = app.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            w = max(min_w, min(1280, avail.width() - 40))
            h = max(min_h, min(800, avail.height() - 60))
            return w, h
    except Exception:
        pass
    return 1280, 800


def run_diagnose() -> str:
    """生成自检报告并返回路径（--diagnose 用）"""
    from app.core.diagnostics import save_report
    path, print_ok = save_report()
    try:
        print(open(path, "r", encoding="utf-8").read())
    except Exception:
        pass
    try:
        box = QtWidgets.QMessageBox()
        box.setIcon(QtWidgets.QMessageBox.Icon.Information if print_ok
                    else QtWidgets.QMessageBox.Icon.Warning)
        box.setWindowTitle("自检完成")
        box.setText("打印落点自检：" + ("正常，可以放心打印。" if print_ok
                                    else "异常！请把报告发给开发者。"))
        box.setInformativeText(f"完整报告已保存到：\n{path}")
        box.exec() if hasattr(box, "exec") else box.exec_()
    except Exception:
        pass
    return path


def main():
    if "--diagnose" in sys.argv:
        enable_dpi_awareness()
        QtWidgets.QApplication(sys.argv)
        run_diagnose()
        return 0

    enable_dpi_awareness()

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("pdf-form-filler")
    app.setApplicationDisplayName("狸猫猫表单")
    app.setOrganizationName("FormFiller")
    app.setStyle("Fusion")
    app.setFont(QtGui.QFont("Microsoft YaHei", 10))
    app.setStyleSheet(APP_STYLESHEET)

    data_dir = get_data_dir()
    window = MainWindow(data_dir)
    w, h = preferred_window_size(app)
    window.resize(w, h)
    # 居中显示
    try:
        screen = app.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            window.move(
                avail.x() + max(0, (avail.width() - w) // 2),
                avail.y() + max(0, (avail.height() - h) // 2),
            )
    except Exception:
        pass
    window.show()

    # PySide6 用 exec()；PySide2(Qt5) 若没有 exec 则退回 exec_
    sys.exit(app.exec() if hasattr(app, "exec") else app.exec_())


if __name__ == "__main__":
    main()
