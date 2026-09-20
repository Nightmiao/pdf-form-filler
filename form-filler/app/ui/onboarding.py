"""新手引导 — 首次使用时的 3 步图文教程"""

from __future__ import annotations


from app.qt import QtWidgets, QtCore, Qt, dialog_exec

QDialog = QtWidgets.QDialog
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QPushButton = QtWidgets.QPushButton
QStackedWidget = QtWidgets.QStackedWidget
QWidget = QtWidgets.QWidget

from app.ui.theme import apply_role, glyph_label, step_glyph

STEPS = [
    {
        "glyph": "document",
        "title": "第 1 步：上传 PDF 表单",
        "text": "点击「新建模板」，选择你要填写的 PDF 表单。\n原始文件会被原样保存，填写和导出都不会改动它。",
    },
    {
        "glyph": "draw",
        "title": "第 2 步：画出填写框",
        "text": "进入设计模式后，按住鼠标左键在表格空白处拖拽，画出填写框。\n"
                "在右侧设置字段名称、类型（文本/数字/日期/下拉/勾选）和必填。\n"
                "拖动框可移动，拖四角小圆点可调整大小。",
    },
    {
        "glyph": "print",
        "title": "第 3 步：填写并导出",
        "text": "点击「去填写」，按 Tab 键依次填写，或直接点 PDF 上的蓝色框。\n"
                "可以保存草稿、为不同的人建立多份记录，\n"
                "最后预览、导出 PDF 或直接打印。",
    },
]


class OnboardingDialog(QDialog):
    """3 步新手引导"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("欢迎使用狸猫猫表单")
        self.setModal(True)
        # 用最小尺寸而非固定尺寸：用户把系统字号/DPI 放大时还能撑开
        self.setMinimumSize(520, 420)
        self.resize(560, 460)
        self._current = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)

        title = QLabel("三步搞定一张 PDF 表单")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #1F2329;")
        layout.addWidget(title)

        # 步骤页
        self._stack = QStackedWidget()
        for step in STEPS:
            page = QWidget()
            v = QVBoxLayout(page)
            v.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.setSpacing(10)

            icon = glyph_label(step["glyph"], 64)
            v.addWidget(icon)

            t = QLabel(step["title"])
            t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            t.setStyleSheet("font-size: 15px; font-weight: 700; color: #1F2329;")
            v.addWidget(t)

            # 注意：Qt 样式表不支持 line-height，行距只能靠段落间距控制。
            # wordWrap 也别开：QLabel 的换行 sizeHint 会算得很窄，
            # 把已经用 \n 排好版的文案再折一次，读起来很碎。
            body = QLabel(step["text"])
            body.setAlignment(Qt.AlignmentFlag.AlignCenter)
            body.setWordWrap(False)
            body.setStyleSheet("color: #4B5563;")
            v.addWidget(body, alignment=Qt.AlignmentFlag.AlignCenter)
            self._stack.addWidget(page)
        layout.addWidget(self._stack, stretch=1)

        # 页码圆点
        dots = QHBoxLayout()
        dots.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dots.setSpacing(6)
        self._dots = []
        for i in range(len(STEPS)):
            dot = QLabel("●")
            dot.setStyleSheet("color: #B0BAC6; font-size: 12px; background: transparent;")
            dots.addWidget(dot)
            self._dots.append(dot)
        layout.addLayout(dots)

        # 按钮
        btns = QHBoxLayout()
        btns.setSpacing(8)
        self._skip_btn = QPushButton("跳过教程")
        apply_role(self._skip_btn, "ghost")
        self._skip_btn.clicked.connect(self.accept)
        btns.addWidget(self._skip_btn)
        btns.addStretch()
        self._prev_btn = QPushButton("上一步")
        self._prev_btn.clicked.connect(self._prev)
        self._prev_btn.setEnabled(False)
        btns.addWidget(self._prev_btn)
        self._next_btn = QPushButton("下一步")
        apply_role(self._next_btn, "primary")
        self._next_btn.clicked.connect(self._next)
        btns.addWidget(self._next_btn)
        layout.addLayout(btns)

        self._update()

    def _update(self):
        self._stack.setCurrentIndex(self._current)
        for i, dot in enumerate(self._dots):
            if i == self._current:
                dot.setStyleSheet("color: #3B82F6; font-size: 12px; background: transparent;")
            else:
                dot.setStyleSheet("color: #B0BAC6; font-size: 12px; background: transparent;")
        self._prev_btn.setEnabled(self._current > 0)
        last = self._current == len(STEPS) - 1
        self._next_btn.setText("开始使用" if last else "下一步")
        self._skip_btn.setVisible(not last)

    def _next(self):
        if self._current < len(STEPS) - 1:
            self._current += 1
            self._update()
        else:
            self.accept()

    def _prev(self):
        if self._current > 0:
            self._current -= 1
            self._update()