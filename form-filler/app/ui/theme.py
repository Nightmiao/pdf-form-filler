"""全局视觉主题 — 浅色清爽风格的配色与样式表，以及按钮角色工具函数"""

from PySide6.QtWidgets import QPushButton, QStyle

# ── 调色板 ──────────────────────────────────────────
COLORS = {
    "bg": "#F4F6F9",
    "surface": "#FFFFFF",
    "border": "#E3E7EC",
    "border_strong": "#D5DAE1",
    "text": "#1F2329",
    "text_secondary": "#6B7280",
    "text_faint": "#9AA3AF",
    "primary": "#3B82F6",
    "primary_hover": "#2F6FD6",
    "primary_pressed": "#2A62BE",
    "primary_light": "#E8F1FD",
    "success": "#16A34A",
    "danger": "#DC2626",
    "warn_bg": "#FEF3C7",
    "warn_text": "#92400E",
}

APP_STYLESHEET = """
QWidget {
    background: #F4F6F9;
    color: #1F2329;
    font-family: "Microsoft YaHei";
    font-size: 13px;
}
QMainWindow, QDialog { background: #F4F6F9; }

QToolBar {
    background: #FFFFFF;
    border: none;
    border-bottom: 1px solid #E3E7EC;
    padding: 5px 8px;
    spacing: 6px;
}
QToolBar::separator { background: #E3E7EC; width: 1px; margin: 4px 6px; }
QStatusBar { background: #FFFFFF; border-top: 1px solid #E3E7EC; color: #6B7280; }

QPushButton {
    background: #FFFFFF;
    color: #1F2329;
    border: 1px solid #D5DAE1;
    border-radius: 6px;
    padding: 5px 12px;
    min-height: 18px;
}
QPushButton:hover { background: #F0F4F9; border-color: #B9C4D2; }
QPushButton:pressed { background: #E4EAF2; }
QPushButton:disabled { color: #A6ADB8; background: #F2F4F7; border-color: #E3E7EC; }

QPushButton[role="primary"] {
    background: #3B82F6; color: #FFFFFF; border: none; font-weight: 600;
}
QPushButton[role="primary"]:hover { background: #2F6FD6; }
QPushButton[role="primary"]:pressed { background: #2A62BE; }
QPushButton[role="primary"]:disabled { background: #A9C7F5; color: #F2F6FD; }

QPushButton[role="ghost"] {
    background: transparent; border: none; color: #4B5563; padding: 5px 8px;
}
QPushButton[role="ghost"]:hover { background: #EDF1F6; }
QPushButton[role="ghost"]:disabled { color: #A6ADB8; }

QPushButton[role="danger"] {
    background: #FFFFFF; color: #DC2626; border: 1px solid #F1B8B8;
}
QPushButton[role="danger"]:hover { background: #FEF2F2; }
QPushButton[role="toolbar"] {
    background: transparent; border: none; padding: 4px 6px;
}
QPushButton[role="toolbar"]:hover { background: #EDF1F6; border-radius: 6px; }

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTextEdit, QPlainTextEdit {
    background: #FFFFFF;
    border: 1px solid #D5DAE1;
    border-radius: 6px;
    padding: 4px 8px;
    selection-background-color: #3B82F6;
    selection-color: #FFFFFF;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QDateEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #3B82F6;
}
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: #FFFFFF; border: 1px solid #E3E7EC; border-radius: 6px;
    selection-background-color: #E8F1FD; selection-color: #1D4ED8;
}

QGroupBox {
    background: #FFFFFF;
    border: 1px solid #E3E7EC;
    border-radius: 8px;
    margin-top: 10px;
    padding: 10px 8px 8px 8px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #374151;
}
QListWidget {
    background: #FFFFFF;
    border: 1px solid #E3E7EC;
    border-radius: 8px;
    padding: 4px;
}
QListWidget::item { padding: 6px 8px; border-radius: 4px; color: #1F2329; }
QListWidget::item:selected { background: #E8F1FD; color: #1D4ED8; }
QListWidget::item:hover { background: #F2F6FB; }
QScrollArea { border: none; background: transparent; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #C9D1DC; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #AEB9C8; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #C9D1DC; border-radius: 5px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #AEB9C8; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QProgressBar {
    background: #E8EDF3; border: none; border-radius: 5px;
    text-align: center; color: #374151; height: 10px;
}
QProgressBar::chunk { background: #3B82F6; border-radius: 5px; }
QMenu {
    background: #FFFFFF; border: 1px solid #E3E7EC; border-radius: 8px; padding: 4px;
}
QMenu::item { padding: 6px 24px 6px 12px; border-radius: 4px; }
QMenu::item:selected { background: #E8F1FD; color: #1D4ED8; }
QMenu::separator { height: 1px; background: #E3E7EC; margin: 4px 8px; }
QToolTip { background: #1F2329; color: #FFFFFF; border: none; padding: 4px 8px; }

QLabel#pageTitle { font-size: 18px; font-weight: 700; background: transparent; }
QLabel[role="sectionTitle"] { font-size: 14px; font-weight: 700; color: #1F2329; background: transparent; }
QLabel[role="hint"] { color: #8A93A1; font-size: 12px; background: transparent; }
QLabel[role="error"] { color: #DC2626; background: transparent; }
QLabel[role="meta"] { color: #6B7280; font-size: 12px; background: transparent; }
QLabel[role="badge"] {
    background: #E8F1FD; color: #1D4ED8; border-radius: 8px;
    padding: 1px 8px; font-size: 11px;
}

QCheckBox, QRadioButton { spacing: 6px; background: transparent; }
QSlider::groove:horizontal { background: #E3E7EC; height: 4px; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #FFFFFF; border: 1px solid #C9D1DC;
    width: 14px; height: 14px; margin: -6px 0; border-radius: 7px;
}
QSlider::handle:horizontal:hover { border-color: #3B82F6; }
QSlider::sub-page:horizontal { background: #3B82F6; border-radius: 2px; }

QFrame#card { background: #FFFFFF; border: 1px solid #E3E7EC; border-radius: 10px; }
QFrame#card:hover { border-color: #B9C9E8; background: #FCFDFF; }
QFrame#cardSelected { background: #FFFFFF; border: 2px solid #3B82F6; border-radius: 10px; }
QFrame#sidebar { background: #FFFFFF; border-right: 1px solid #E3E7EC; }
QFrame#hintBar { background: #F0F6FF; border: 1px solid #D3E3FB; border-radius: 8px; }
QLabel#hintText { color: #3B6BC0; background: transparent; }
QFrame#emptyState { background: transparent; }
QLabel#emptyIcon { background: transparent; font-size: 44px; }
QLabel#emptyTitle { background: transparent; font-size: 16px; font-weight: 700; color: #374151; }
QLabel#emptyDesc { background: transparent; color: #8A93A1; }
QTabWidget::pane { border: 1px solid #E3E7EC; border-radius: 8px; background: #FFFFFF; }
QTabBar::tab {
    background: transparent; padding: 7px 16px; color: #6B7280;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected { color: #1D4ED8; border-bottom: 2px solid #3B82F6; font-weight: 600; }
"""


def apply_role(btn: QPushButton, role: str):
    """给按钮设置视觉角色：primary / ghost / danger / toolbar"""
    btn.setProperty("role", role)
    btn.style().unpolish(btn)
    btn.style().polish(btn)


def icon_of(widget, standard_pixmap):
    """从 Qt 内置图标库取一个标准图标"""
    return widget.style().standardIcon(standard_pixmap)