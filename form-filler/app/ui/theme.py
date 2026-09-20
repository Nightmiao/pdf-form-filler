"""全局视觉主题 — 浅色清爽风格的配色与样式表，以及按钮角色工具函数"""

from __future__ import annotations


from app.qt import QtWidgets

QPushButton = QtWidgets.QPushButton
QStyle = QtWidgets.QStyle

# ── 调色板 ──────────────────────────────────────────
COLORS = {
    "bg": "#F4F6F9",
    "surface": "#FFFFFF",
    "border": "#E3E7EC",
    "border_strong": "#D5DAE1",
    "text": "#1F2329",
    "text_secondary": "#5B6472",
    "text_faint": "#6B7280",
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
/* 关键：QWidget 的底色规则会传染给 QLabel，导致白色卡片/工具栏里出现灰块。
   QLabel 一律透明；需要底色的用属性选择器单独指定（更具体，仍然生效）。 */
QLabel { background: transparent; }
QMainWindow, QDialog { background: #F4F6F9; }

QToolBar {
    background: #FFFFFF;
    border: none;
    border-bottom: 1px solid #E3E7EC;
    padding: 5px 8px;
    spacing: 6px;
}
QToolBar::separator { background: #E3E7EC; width: 1px; margin: 4px 6px; }
QToolBar QToolButton {
    background: transparent; border: none; border-radius: 6px;
    padding: 4px 8px; color: #4B5563;
}
QToolBar QToolButton:hover { background: #EDF1F6; }
QToolBar QToolButton:pressed { background: #E4EAF2; }
QToolBar QToolButton:disabled { color: #A6ADB8; }
QToolBar QToolButton::menu-indicator { image: none; }
QStatusBar { background: #FFFFFF; border-top: 1px solid #E3E7EC; color: #5B6472; }
QStatusBar QLabel { color: #5B6472; }

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
    background: #3B82F6; color: #FFFFFF; border: 1px solid #3B82F6; font-weight: 600;
}
QPushButton[role="primary"]:hover { background: #2F6FD6; border-color: #2F6FD6; }
QPushButton[role="primary"]:pressed { background: #2A62BE; border-color: #2A62BE; }
QPushButton[role="primary"]:disabled { background: #CFE0FA; border-color: #CFE0FA; color: #6B7A90; }

QPushButton[role="ghost"] {
    background: transparent; border: none; color: #4B5563; padding: 5px 8px;
}
QPushButton[role="ghost"]:hover { background: #EDF1F6; }
QPushButton[role="ghost"]:disabled { color: #A6ADB8; background: transparent; }

QPushButton[role="danger"] {
    background: #FFFFFF; color: #DC2626; border: 1px solid #F1B8B8;
}
QPushButton[role="danger"]:hover { background: #FEF2F2; border-color: #E89B9B; }
QPushButton[role="danger"]:pressed { background: #FDE8E8; }
QPushButton[role="danger"]:disabled {
    background: #F2F4F7; border-color: #E3E7EC; color: #A6ADB8;
}
QPushButton[role="toolbar"] {
    background: transparent; border: none; padding: 4px 6px; color: #4B5563;
}
QPushButton[role="toolbar"]:hover { background: #EDF1F6; border-radius: 6px; }
QPushButton[role="toolbar"]:pressed { background: #E4EAF2; border-radius: 6px; }
QPushButton[role="toolbar"]:disabled { color: #A6ADB8; background: transparent; }

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTextEdit, QPlainTextEdit {
    background: #FFFFFF;
    border: 1px solid #D5DAE1;
    border-radius: 6px;
    padding: 4px 8px;
    selection-background-color: #3B82F6;
    selection-color: #FFFFFF;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover,
QDateEdit:hover, QTextEdit:hover, QPlainTextEdit:hover { border-color: #B9C4D2; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QDateEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #3B82F6;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QDateEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {
    background: #F2F4F7; color: #A6ADB8; border-color: #E3E7EC;
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
QScrollArea > QWidget > QWidget { background: transparent; }

/* 老机器基本是鼠标操作，滚动条要够粗好抓 */
QScrollBar:vertical { background: transparent; width: 13px; margin: 1px; }
QScrollBar::handle:vertical { background: #C2CBD8; border-radius: 6px; min-height: 36px; }
QScrollBar::handle:vertical:hover { background: #A6B2C2; }
QScrollBar::handle:vertical:pressed { background: #8E9BAD; }
QScrollBar:horizontal { background: transparent; height: 13px; margin: 1px; }
QScrollBar::handle:horizontal { background: #C2CBD8; border-radius: 6px; min-width: 36px; }
QScrollBar::handle:horizontal:hover { background: #A6B2C2; }
QScrollBar::handle:horizontal:pressed { background: #8E9BAD; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QProgressBar {
    background: #E8EDF3; border: none; border-radius: 6px; height: 12px;
}
QProgressBar::chunk { background: #3B82F6; border-radius: 6px; }
QMenu {
    background: #FFFFFF; border: 1px solid #E3E7EC; border-radius: 8px; padding: 4px;
}
QMenu::item { padding: 6px 24px 6px 12px; border-radius: 4px; }
QMenu::item:selected { background: #E8F1FD; color: #1D4ED8; }
QMenu::separator { height: 1px; background: #E3E7EC; margin: 4px 8px; }
QToolTip { background: #1F2329; color: #FFFFFF; border: none; padding: 4px 8px; }

QLabel#pageTitle { font-size: 18px; font-weight: 700; background: transparent; }
QLabel[role="sectionTitle"] { font-size: 14px; font-weight: 700; color: #1F2329; background: transparent; }
QLabel[role="hint"] { color: #667085; font-size: 12px; background: transparent; }
QLabel[role="error"] { color: #C81E1E; background: transparent; }
QLabel[role="meta"] { color: #5B6472; font-size: 12px; background: transparent; }
QLabel[role="badge"] {
    background: #E8F1FD; color: #1D4ED8; border-radius: 8px;
    padding: 1px 8px; font-size: 11px;
}

QCheckBox, QRadioButton { spacing: 6px; background: transparent; }
QCheckBox::indicator, QRadioButton::indicator { width: 15px; height: 15px; }
QCheckBox::indicator:unchecked {
    background: #FFFFFF; border: 1px solid #C2CBD8; border-radius: 3px;
}
QCheckBox::indicator:unchecked:hover { border-color: #3B82F6; }
QCheckBox::indicator:checked {
    background: #3B82F6; border: 1px solid #3B82F6; border-radius: 3px;
    image: url(:/qt-project.org/styles/commonstyle/images/checkbox_checked.png);
}
QRadioButton::indicator:unchecked {
    background: #FFFFFF; border: 1px solid #C2CBD8; border-radius: 8px;
}
QRadioButton::indicator:checked {
    background: #3B82F6; border: 4px solid #FFFFFF; border-radius: 8px;
    outline: 1px solid #3B82F6;
}
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
QFrame#emptyState { background: transparent; }
QLabel#emptyIcon { background: transparent; }
QLabel#emptyTitle { background: transparent; font-size: 16px; font-weight: 700; color: #374151; }
QLabel#emptyDesc { background: transparent; color: #667085; }
"""



def apply_role(btn: QPushButton, role: str):
    """给按钮设置视觉角色：primary / ghost / danger / toolbar"""
    btn.setProperty("role", role)
    btn.style().unpolish(btn)
    btn.style().polish(btn)


def make_elided_label(text: str = "", parent=None, role: str = "",
                      object_name: str = "", max_hint_width: int = 180):
    """宽度不够时自动显示省略号的 QLabel。

    普通 QLabel 的 minimumSizeHint 等于整段文字的宽度，会把整个窗口的
    最小宽度顶起来（实测首页顶栏把窗口最小宽度顶到 1418px，
    在 1024x768 的机器上工具栏按钮会被挤进溢出菜单）。

    这里把"期望宽度"压到 max_hint_width、"最小宽度"放到 24：
    布局够宽时按期望宽度显示（超长自动省略号），不够宽时可以被压缩，
    而不是把窗口/工具栏顶爆。
    """
    from app.qt import QtWidgets, QtCore, enum_of

    elide_right = enum_of(QtCore.Qt, "TextElideMode", "ElideRight")

    class ElidedLabel(QtWidgets.QLabel):
        def __init__(self, text="", parent=None):
            super().__init__(parent)
            self._full = text
            super().setText(text)
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Preferred,
                QtWidgets.QSizePolicy.Policy.Preferred,
            )

        def setText(self, text):
            self._full = text
            self._sync()

        def fullText(self):
            return self._full

        def _sync(self):
            avail = max(0, self.width() - 2)
            shown = self.fontMetrics().elidedText(self._full, elide_right, avail)
            if shown != super().text():
                super().setText(shown)

        def sizeHint(self):
            base = super().sizeHint()
            return QtCore.QSize(min(base.width(), max_hint_width), base.height())

        def minimumSizeHint(self):
            return QtCore.QSize(24, super().minimumSizeHint().height())

        def resizeEvent(self, event):
            super().resizeEvent(event)
            self._sync()

    lbl = ElidedLabel(text, parent)
    if role:
        lbl.setProperty("role", role)
    if object_name:
        lbl.setObjectName(object_name)
    lbl.setToolTip(text)
    return lbl



def icon_of(widget, sp_name: str):
    """从 Qt 内置图标库取一个标准图标（传名称，兼容 Qt5/Qt6 枚举差异）"""
    sp = getattr(QStyle, sp_name, None)
    if sp is None:
        sp = getattr(QStyle.StandardPixmap, sp_name)
    return widget.style().standardIcon(sp)


def document_glyph(size: int = 56, color: str = "#9DB2CE", accent: str = "#3B82F6"):
    """画一个"文档"图标并返回 QPixmap。

    为什么不用 emoji：Windows 7 只有 Segoe UI Symbol，
    没有彩色 emoji 字体（Segoe UI Emoji 从 Win8 才有），
    纸飞机/sd 卡那类字符（U+1F4C4 等）在 Win7 上会渲染成一个空心方框（豆腐块）。
    用 QPainter 自己画，任何 Windows 版本、任何字体环境都一致。
    """
    from app.qt import QtGui, QtCore, Qt

    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pm)
    try:
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        m = size * 0.18                      # 外边距
        w = size - 2 * m
        h = w * 1.28
        if h > size - 2 * m:
            h = size - 2 * m
            w = h / 1.28
        x = (size - w) / 2.0
        y = (size - h) / 2.0
        fold = w * 0.32

        path = QtGui.QPainterPath()
        path.moveTo(x, y)
        path.lineTo(x + w - fold, y)
        path.lineTo(x + w, y + fold)
        path.lineTo(x + w, y + h)
        path.lineTo(x, y + h)
        path.closeSubpath()

        p.setPen(QtGui.QPen(QtGui.QColor(color), max(1.0, size * 0.035)))
        p.setBrush(QtGui.QColor("#FFFFFF"))
        p.drawPath(path)

        # 折角
        p.setBrush(QtGui.QColor(color).lighter(115))
        p.drawPolygon([
            QtCore.QPointF(x + w - fold, y),
            QtCore.QPointF(x + w, y + fold),
            QtCore.QPointF(x + w - fold, y + fold),
        ])

        # 内容行（最后一行用主题蓝，暗示"可填写"）
        p.setPen(QtGui.QPen(QtGui.QColor(color), max(1.0, size * 0.045)))
        line_x0 = x + w * 0.18
        line_x1 = x + w * 0.82
        for i in range(3):
            ly = y + h * (0.50 + i * 0.16)
            if i == 2:
                p.setPen(QtGui.QPen(QtGui.QColor(accent), max(1.0, size * 0.045)))
                p.drawLine(QtCore.QPointF(line_x0, ly), QtCore.QPointF(x + w * 0.58, ly))
            else:
                p.drawLine(QtCore.QPointF(line_x0, ly), QtCore.QPointF(line_x1, ly))
    finally:
        p.end()
    return pm


# 引导页/空状态用的大图标：全部自绘，不依赖 emoji 字体
STEP_GLYPHS = ("document", "draw", "print")


def step_glyph(kind: str, size: int = 60):
    """画引导页的三步图标（挑文件 / 画框 / 填写打印）"""
    from app.qt import QtGui, QtCore, Qt

    if kind == "document":
        return document_glyph(size)

    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pm)
    try:
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        ln = max(1.5, size * 0.055)
        blue = QtGui.QColor("#3B82F6")
        slate = QtGui.QColor("#9DB2CE")
        if kind == "draw":
            # 纸 + 虚线框 + 铅笔
            m = size * 0.16
            p.setPen(QtGui.QPen(slate, ln))
            p.setBrush(QtGui.QColor("#FFFFFF"))
            p.drawRoundedRect(
                QtCore.QRectF(m, m, size - 2 * m, size - 2 * m), size * 0.06, size * 0.06
            )
            p.setPen(QtGui.QPen(blue, ln, QtCore.Qt.PenStyle.DashLine))
            p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            p.drawRect(QtCore.QRectF(size * 0.28, size * 0.30, size * 0.30, size * 0.16))
            p.setPen(QtGui.QPen(blue, ln))
            p.drawLine(
                QtCore.QPointF(size * 0.62, size * 0.72),
                QtCore.QPointF(size * 0.84, size * 0.50),
            )
        else:  # print
            m = size * 0.16
            p.setPen(QtGui.QPen(slate, ln))
            p.setBrush(QtGui.QColor("#FFFFFF"))
            p.drawRoundedRect(
                QtCore.QRectF(m, size * 0.36, size - 2 * m, size * 0.34),
                size * 0.06, size * 0.06,
            )
            p.drawRoundedRect(
                QtCore.QRectF(size * 0.28, m, size * 0.44, size * 0.22),
                size * 0.04, size * 0.04,
            )
            p.setBrush(QtGui.QColor("#E8F1FD"))
            p.drawRoundedRect(
                QtCore.QRectF(size * 0.28, size * 0.62, size * 0.44, size * 0.22),
                size * 0.04, size * 0.04,
            )
            p.setPen(QtGui.QPen(blue, ln))
            p.drawLine(
                QtCore.QPointF(size * 0.38, size * 0.71),
                QtCore.QPointF(size * 0.62, size * 0.71),
            )
            p.drawLine(
                QtCore.QPointF(size * 0.38, size * 0.78),
                QtCore.QPointF(size * 0.54, size * 0.78),
            )
    finally:
        p.end()
    return pm


def glyph_label(kind: str = "document", size: int = 60):
    """返回一个显示自绘图标、且背景透明的 QLabel"""
    from app.qt import QtWidgets, Qt

    lbl = QtWidgets.QLabel()
    lbl.setPixmap(step_glyph(kind, size))
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setFixedHeight(int(size * 1.15))
    return lbl
