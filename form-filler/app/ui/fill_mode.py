"""填写模式 — PDF 预览 + 字段高亮 + 提示条"""

from __future__ import annotations


from app.qt import QtWidgets, QtCore, Qt, size_policy

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QLabel = QtWidgets.QLabel
QPushButton = QtWidgets.QPushButton
QToolBar = QtWidgets.QToolBar
Signal = QtCore.Signal

from app.ui.pdf_canvas import PdfCanvas
from app.ui.theme import apply_role, icon_of, COLORS, make_elided_label
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
        back_btn.setIcon(icon_of(self, "SP_ArrowBack"))
        apply_role(back_btn, "ghost")
        back_btn.setToolTip("返回模板库（自动保存草稿）")
        back_btn.clicked.connect(self.back_to_home)
        toolbar.addWidget(back_btn)

        toolbar.addSeparator()

        self._title_label = make_elided_label("未命名模板")
        self._title_label.setStyleSheet(f"font-weight: 700; font-size: 14px; color: {COLORS['text']};")
        self._title_label.setMinimumWidth(80)
        self._title_label.setMaximumWidth(200)
        toolbar.addWidget(self._title_label)

        from app.qt import QtWidgets
        stretch = QtWidgets.QWidget()
        stretch.setSizePolicy(size_policy("Expanding"), size_policy("Preferred"))
        toolbar.addWidget(stretch)

        hint = make_elided_label("点击蓝框或按 Tab 填写", role="hint")
        hint.setMaximumWidth(150)
        toolbar.addWidget(hint)

        toolbar.addSeparator()

        # 主操作放最左：Qt 工具栏溢出从右往左丢控件，这样它们不会被丢掉
        design_btn = QPushButton("调整设计")
        design_btn.setIcon(icon_of(self, "SP_FileDialogDetailedView"))
        design_btn.setToolTip("回到设计模式修改字段（自动保存草稿）")
        design_btn.clicked.connect(self.switch_to_design)
        toolbar.addWidget(design_btn)

        toolbar.addSeparator()

        # 缩放
        self._zoom_out_btn = QPushButton("-")
        apply_role(self._zoom_out_btn, "toolbar")
        self._zoom_out_btn.setFixedWidth(28)
        self._zoom_out_btn.setToolTip("缩小 (Ctrl+-)")
        self._zoom_out_btn.clicked.connect(lambda: self._canvas.zoom_out())
        toolbar.addWidget(self._zoom_out_btn)

        self._zoom_label = QLabel("100%")
        self._zoom_label.setFixedWidth(42)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zoom_label.setStyleSheet(f"color:{COLORS['text_secondary']}; font-weight:600;")
        toolbar.addWidget(self._zoom_label)

        self._zoom_in_btn = QPushButton("+")
        apply_role(self._zoom_in_btn, "toolbar")
        self._zoom_in_btn.setFixedWidth(28)
        self._zoom_in_btn.setToolTip("放大 (Ctrl++)")
        self._zoom_in_btn.clicked.connect(lambda: self._canvas.zoom_in())
        toolbar.addWidget(self._zoom_in_btn)

        fit_btn = QPushButton("适应窗口")
        apply_role(fit_btn, "toolbar")
        fit_btn.setToolTip("适应窗口 (Ctrl+0)")
        fit_btn.clicked.connect(lambda: self._canvas.zoom_fit())
        toolbar.addWidget(fit_btn)

        layout.addWidget(toolbar)

        self._canvas = PdfCanvas()
        self._canvas.set_mode(PdfCanvas.MODE_FILL)
        self._canvas.zoom_changed.connect(self._on_canvas_zoom_changed)
        # 翻页后必须重放填写值（见 _on_canvas_page_changed 说明）
        self._canvas.current_page_changed.connect(self._on_canvas_page_changed)
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

    def _on_canvas_zoom_changed(self, percent: int):
        self._zoom_label.setText(f"{percent}%")

    def _on_canvas_page_changed(self, page_num: int):
        """翻页后重放填写值。

        历史缺陷：show_page 会 _scene.clear() 并按字段重建图元，而新建的
        FieldItem._fill_value 恒为空字符串；值只在 load_template / set_record /
        set_current_page 三处补过。于是按 Tab 跨页、或用"必填跳转"翻页后，
        目标页已填的内容在画布蓝框里显示为空白（数据其实一直在记录里），
        用户会以为没保存。挂到 current_page_changed 上一次覆盖所有翻页入口。
        """
        self._sync_canvas_values()

    def _sync_canvas_values(self):
        if self._record:
            self._canvas.apply_fill_values(self._record.values)

    @property
    def canvas(self) -> PdfCanvas:
        return self._canvas