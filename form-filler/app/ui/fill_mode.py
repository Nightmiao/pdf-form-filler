"""填写模式 — PDF 预览 + 字段高亮 + 提示条"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QToolBar, QStyle, QSizePolicy,
)
from PySide6.QtCore import Signal

from app.ui.pdf_canvas import PdfCanvas
from app.ui.theme import apply_role, icon_of
from app.core.field_model import TemplateMeta, FillRecord


class FillMode(QWidget):
    """填写模式容器"""

    back_to_home = Signal()
    switch_to_design = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._template: TemplateMeta | None = None
        self._record: FillRecord | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QToolBar()
        toolbar.setMovable(False)

        back_btn = QPushButton("返回模板库")
        back_btn.setIcon(icon_of(self, QStyle.StandardPixmap.SP_ArrowBack))
        apply_role(back_btn, "ghost")
        back_btn.setToolTip("返回模板库（自动保存草稿）")
        back_btn.clicked.connect(self.back_to_home)
        toolbar.addWidget(back_btn)

        toolbar.addSeparator()

        self._title_label = QLabel("未命名模板")
        self._title_label.setStyleSheet("font-weight: 700; font-size: 14px; color: #1F2329;")
        toolbar.addWidget(self._title_label)

        stretch = QWidget()
        stretch.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(stretch)

        hint = QLabel("点击 PDF 上的蓝色框定位输入项，或按 Tab 依次填写")
        hint.setProperty("role", "hint")
        toolbar.addWidget(hint)

        toolbar.addSeparator()

        design_btn = QPushButton("调整字段设计")
        design_btn.setIcon(icon_of(self, QStyle.StandardPixmap.SP_FileDialogDetailedView))
        design_btn.setToolTip("回到设计模式修改字段（自动保存草稿）")
        design_btn.clicked.connect(self.switch_to_design)
        toolbar.addWidget(design_btn)

        layout.addWidget(toolbar)

        self._canvas = PdfCanvas()
        self._canvas.set_mode(PdfCanvas.MODE_FILL)
        layout.addWidget(self._canvas, stretch=1)

    # ── 公共方法 ──────────────────────────────────

    def load_template(self, template: TemplateMeta, pdf_path: str, record: FillRecord):
        self._template = template
        self._record = record
        self._title_label.setText(template.name)
        self._canvas.load_pdf(pdf_path, template.page_settings)
        self._canvas.load_fields(template.fields)
        self._canvas.show_page(0)
        self._sync_canvas_values()
        # 自动定位第一个字段
        ordered = sorted(template.fields, key=lambda f: (f.page, f.tab_order))
        if ordered:
            self._canvas.select_field_on_page(ordered[0].id)

    def set_record(self, record: FillRecord):
        """切换填写记录"""
        self._record = record
        self._sync_canvas_values()

    def set_current_page(self, page_num: int):
        self._canvas.set_current_page(page_num)
        self._sync_canvas_values()

    def focus_next_field(self):
        self._canvas.focus_next_field()

    def focus_prev_field(self):
        self._canvas.focus_prev_field()

    def select_field(self, field_id: str):
        self._canvas.select_field_on_page(field_id)

    def update_field_value(self, field_id: str, value: str):
        self._canvas.set_field_value(field_id, value)

    def _sync_canvas_values(self):
        if self._record:
            self._canvas.apply_fill_values(self._record.values)

    @property
    def canvas(self) -> PdfCanvas:
        return self._canvas