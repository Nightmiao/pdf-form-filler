"""狸猫猫表单 — 程序入口"""

from __future__ import annotations


import sys
import os
from app.qt import QtWidgets, QtGui

from app.ui.theme import APP_STYLESHEET
from app.ui.main_window import MainWindow


def get_data_dir() -> str:
    """获取用户数据目录"""
    home = os.path.expanduser("~")
    data_dir = os.path.join(home, ".form-filler", "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("pdf-form-filler")
    app.setApplicationDisplayName("狸猫猫表单")
    app.setOrganizationName("FormFiller")
    app.setStyle("Fusion")
    app.setFont(QtGui.QFont("Microsoft YaHei", 10))
    app.setStyleSheet(APP_STYLESHEET)

    data_dir = get_data_dir()
    window = MainWindow(data_dir)
    window.resize(1280, 800)
    window.show()

    # PySide6 用 exec()；PySide2(Qt5) 若没有 exec 则退回 exec_
    sys.exit(app.exec() if hasattr(app, "exec") else app.exec_())


if __name__ == "__main__":
    main()