"""狸猫猫的表单填写工具 — 程序入口"""

import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from app.ui.main_window import MainWindow


def get_data_dir() -> str:
    """获取用户数据目录"""
    home = os.path.expanduser("~")
    data_dir = os.path.join(home, ".form-filler", "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("狸猫猫的表单填写工具")
    app.setOrganizationName("FormFiller")

    # 设置默认字体
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)

    data_dir = get_data_dir()
    window = MainWindow(data_dir)
    window.resize(1280, 800)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
