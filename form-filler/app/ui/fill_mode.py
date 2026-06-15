"""填写模式 — PDF 预览 + 字段高亮"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QToolBar
from PySide6.QtCore import Signal, Qt

from app.ui.pdf_canvas import PdfCanvas
from app.core.field_model import TemplateMeta, FillRecord


class FillMode(QWidget):
    """填写模式容器"""

    fill_data_changed = Signal(dict)  # {field_id: value}
    back_to_home = Signal()  # 返回首页
    switch_to_design = Signal()  # 切换到设计模式

    def __init__(self, parent=None):
        super().__init__(parent)
        self._template: TemplateMeta | None = None
        self._record: FillRecord | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏
        toolbar = QToolBar()
        toolbar.setMovable(False)

        back_btn = QPushButton("🏠 返回首页")
        back_btn.setFixedHeight(28)
        back_btn.clicked.connect(self.back_to_home)
        toolbar.addWidget(back_btn)

        design_btn = QPushButton("🔧 设计模式")
        design_btn.setFixedHeight(28)
        design_btn.setStyleSheet("background-color: #4a90d9; color: white; border: none; border-radius: 3px; padding: 0 10px;")
        design_btn.clicked.connect(self.switch_to_design)
        toolbar.addWidget(design_btn)

        layout.addWidget(toolbar)

        # PDF 画布（填写模式）
        self._canvas = PdfCanvas()
        self._canvas.set_mode(PdfCanvas.MODE_FILL)
        self._canvas.field_selected_sig.connect(self._on_field_selected)
        layout.addWidget(self._canvas)

    def load_template(self, template: TemplateMeta, pdf_path: str, record: FillRecord):
        """加载模板和填写记录"""
        self._template = template
        self._record = record

        self._canvas.load_pdf(pdf_path, template.page_settings)
        self._canvas.load_fields(template.fields)
        self._canvas.show_page(0)

        # 将已有填写值显示在画布上
        self._sync_canvas_values()

        # 自动聚焦第一个字段
        tab_ordered = sorted(template.fields, key=lambda f: f.tab_order)
        if tab_ordered:
            self._canvas.select_field(tab_ordered[0].id)

    def set_current_page(self, page_num: int):
        """切换页面"""
        self._canvas.set_current_page(page_num)
        # 翻页后画布会重建当前页的字段图元，需要重新把已填写的值同步上去，
        # 否则其他页之前填的内容不会显示。
        self._sync_canvas_values()

    def focus_next_field(self):
        """聚焦下一个字段"""
        self._canvas.focus_next_field()

    def update_field_value(self, field_id: str, value: str):
        """更新画布上字段的显示值"""
        if field_id in self._canvas._field_items:
            self._canvas._field_items[field_id].set_fill_value(value)

    def _sync_canvas_values(self):
        """将记录中的值同步到画布"""
        if self._record:
            for field_id, item in self._canvas._field_items.items():
                value = self._record.values.get(field_id, "")
                item.set_fill_value(value)

    def _on_field_selected(self, field_id: str):
        """字段被选中"""
        pass  # 由右侧填写面板处理
