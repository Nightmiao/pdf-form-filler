"""设计模式 — PDF 画布 + 两级工具栏（主操作 / 辅助工具）+ 提示条"""

from __future__ import annotations


from app.qt import QtWidgets, QtCore, Qt, size_policy

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QToolBar = QtWidgets.QToolBar
QSlider = QtWidgets.QSlider
QLabel = QtWidgets.QLabel
QPushButton = QtWidgets.QPushButton
QSpinBox = QtWidgets.QSpinBox
QCheckBox = QtWidgets.QCheckBox
Signal = QtCore.Signal

from app.ui.pdf_canvas import PdfCanvas
from app.ui.theme import apply_role, icon_of, COLORS
from app.core.field_model import TemplateMeta, FieldDefinition


class DesignMode(QWidget):
    """设计模式容器 — 画布 + 工具栏"""

    field_selected = Signal(str)        # field_id → 右侧面板
    back_to_home = Signal()
    switch_to_fill = Signal()
    save_requested = Signal()
    fields_restored = Signal(object)    # 撤销/重做后完整字段列表
    page_rotation_changed = Signal(int, float)  # page_num, rotation

    def __init__(self, parent=None):
        super().__init__(parent)
        self._template: TemplateMeta | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 第一行：主操作栏 ──
        main_bar = QToolBar()
        main_bar.setMovable(False)

        back_btn = QPushButton("返回模板库")
        back_btn.setIcon(icon_of(self, "SP_ArrowBack"))
        apply_role(back_btn, "ghost")
        back_btn.setToolTip("返回模板库（自动保存）")
        back_btn.clicked.connect(self.back_to_home)
        main_bar.addWidget(back_btn)

        main_bar.addSeparator()

        self._title_label = QLabel("未命名模板")
        self._title_label.setStyleSheet(f"font-weight: 700; font-size: 14px; color: {COLORS['text']};")
        main_bar.addWidget(self._title_label)

        # 弹性空间
        from app.qt import QtWidgets
        stretch = QtWidgets.QWidget()
        stretch.setSizePolicy(size_policy("Expanding"), size_policy("Preferred"))
        main_bar.addWidget(stretch)

        # 撤销 / 重做
        self._undo_btn = QPushButton("撤销")
        self._undo_btn.setIcon(icon_of(self, "SP_ArrowBack"))
        apply_role(self._undo_btn, "toolbar")
        self._undo_btn.setToolTip("撤销 (Ctrl+Z)")
        self._undo_btn.clicked.connect(self.undo)
        self._undo_btn.setEnabled(False)
        main_bar.addWidget(self._undo_btn)

        self._redo_btn = QPushButton("重做")
        self._redo_btn.setIcon(icon_of(self, "SP_ArrowForward"))
        apply_role(self._redo_btn, "toolbar")
        self._redo_btn.setToolTip("重做 (Ctrl+Y)")
        self._redo_btn.clicked.connect(self.redo)
        self._redo_btn.setEnabled(False)
        main_bar.addWidget(self._redo_btn)

        main_bar.addSeparator()

        # 页码
        main_bar.addWidget(QLabel("页码"))
        self._page_spin = QSpinBox()
        self._page_spin.setMinimum(1)
        self._page_spin.setValue(1)
        self._page_spin.setFixedWidth(56)
        self._page_spin.setToolTip("当前页")
        self._page_spin.valueChanged.connect(self._on_page_spin_changed)
        main_bar.addWidget(self._page_spin)

        self._page_count_label = QLabel("/ 1")
        self._page_count_label.setProperty("role", "meta")
        main_bar.addWidget(self._page_count_label)

        main_bar.addSeparator()

        self._save_btn = QPushButton("保存")
        self._save_btn.setIcon(icon_of(self, "SP_DialogSaveButton"))
        self._save_btn.setToolTip("保存模板 (Ctrl+S)")
        self._save_btn.clicked.connect(self.save_requested)
        main_bar.addWidget(self._save_btn)

        self._fill_btn = QPushButton("去填写")
        self._fill_btn.setIcon(icon_of(self, "SP_DialogApplyButton"))
        apply_role(self._fill_btn, "primary")
        self._fill_btn.setToolTip("保存并进入填写模式")
        self._fill_btn.clicked.connect(self.switch_to_fill)
        main_bar.addWidget(self._fill_btn)

        layout.addWidget(main_bar)

        # ── 第二行：画布辅助工具 ──
        tools_bar = QToolBar()
        tools_bar.setMovable(False)
        tools_bar.setStyleSheet("QToolBar { background: #FAFBFC; }")  # 次级工具栏稍浅底

        snap_btn = QCheckBox("网格吸附")
        snap_btn.setChecked(True)
        snap_btn.setToolTip("拖动字段时自动对齐网格")
        tools_bar.addWidget(snap_btn)

        align_btn = QCheckBox("对齐线")
        align_btn.setChecked(True)
        align_btn.setToolTip("拖动字段时显示与其他字段的对齐辅助线")
        tools_bar.addWidget(align_btn)

        tools_bar.addSeparator()

        tools_bar.addWidget(QLabel("页面旋转矫正"))
        self._rotation_slider = QSlider(Qt.Orientation.Horizontal)
        self._rotation_slider.setRange(-50, 50)
        self._rotation_slider.setValue(0)
        self._rotation_slider.setFixedWidth(110)
        self._rotation_slider.setToolTip("给扫描歪斜的表格掰正（-5° ~ +5°）")
        self._rotation_slider.valueChanged.connect(self._on_page_rotation_changed)
        tools_bar.addWidget(self._rotation_slider)

        self._rotation_value_label = QLabel("0.0°")
        self._rotation_value_label.setFixedWidth(42)
        self._rotation_value_label.setStyleSheet(f"color:{COLORS['text_secondary']}; font-weight:600;")
        tools_bar.addWidget(self._rotation_value_label)

        self._rotation_reset_btn = QPushButton("重置")
        apply_role(self._rotation_reset_btn, "toolbar")
        self._rotation_reset_btn.setToolTip("恢复 0°")
        self._rotation_reset_btn.clicked.connect(self._on_rotation_reset)
        tools_bar.addWidget(self._rotation_reset_btn)

        tools_bar.addSeparator()

        # 缩放（放在第二行，主栏只保留核心操作，默认窗口下不再溢出折叠）
        self._zoom_out_btn = QPushButton("−")
        apply_role(self._zoom_out_btn, "toolbar")
        self._zoom_out_btn.setFixedWidth(30)
        self._zoom_out_btn.setToolTip("缩小 (Ctrl+-)")
        self._zoom_out_btn.clicked.connect(self._on_zoom_out)
        tools_bar.addWidget(self._zoom_out_btn)

        self._zoom_label = QLabel("100%")
        self._zoom_label.setFixedWidth(46)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zoom_label.setStyleSheet(f"color:{COLORS['text_secondary']}; font-weight:600;")
        tools_bar.addWidget(self._zoom_label)

        self._zoom_in_btn = QPushButton("＋")
        apply_role(self._zoom_in_btn, "toolbar")
        self._zoom_in_btn.setFixedWidth(30)
        self._zoom_in_btn.setToolTip("放大 (Ctrl++)")
        self._zoom_in_btn.clicked.connect(self._on_zoom_in)
        tools_bar.addWidget(self._zoom_in_btn)

        self._fit_btn = QPushButton("适应窗口")
        apply_role(self._fit_btn, "toolbar")
        self._fit_btn.setToolTip("适应窗口 (Ctrl+0)")
        self._fit_btn.clicked.connect(self._on_zoom_fit)
        tools_bar.addWidget(self._fit_btn)

        from app.qt import QtWidgets
        stretch2 = QtWidgets.QWidget()
        stretch2.setSizePolicy(size_policy("Expanding"), size_policy("Preferred"))
        tools_bar.addWidget(stretch2)

        layout.addWidget(tools_bar)

        # ── 画布 ──
        self._canvas = PdfCanvas()
        self._canvas.set_mode(PdfCanvas.MODE_DESIGN)
        self._canvas.field_selected_sig.connect(self._on_field_selected)
        self._canvas.current_page_changed.connect(self._on_page_changed)
        self._canvas.zoom_changed.connect(self._on_canvas_zoom_changed)
        self._canvas.undo_available.connect(self._undo_btn.setEnabled)
        self._canvas.redo_available.connect(self._redo_btn.setEnabled)
        self._canvas.fields_restored.connect(self.fields_restored)
        layout.addWidget(self._canvas, stretch=1)

        snap_btn.toggled.connect(self._canvas.set_snap_enabled)
        align_btn.toggled.connect(self._canvas.set_alignment_enabled)
        self._canvas.set_snap_enabled(snap_btn.isChecked())
        self._canvas.set_alignment_enabled(align_btn.isChecked())

    # ── 公共方法 ──────────────────────────────────

    def load_template(self, template: TemplateMeta, pdf_path: str):
        self._template = template
        self._title_label.setText(template.name)
        self._canvas.load_pdf(pdf_path, template.page_settings)
        self._canvas.load_fields(template.fields)
        self._canvas.show_page(0)

        self._page_spin.blockSignals(True)
        self._page_spin.setMaximum(template.page_count)
        self._page_spin.setValue(1)
        self._page_spin.blockSignals(False)
        self._page_count_label.setText(f"/ {template.page_count}")
        self._sync_rotation_slider()

    def set_current_page(self, page_num: int):
        self._canvas.set_current_page(page_num)
        self._page_spin.setValue(page_num + 1)
        self._sync_rotation_slider()

    def update_field(self, field: FieldDefinition):
        self._canvas.update_field(field)

    def remove_field(self, field_id: str):
        self._canvas.remove_field(field_id)

    def select_field(self, field_id: str):
        self._canvas.select_field_on_page(field_id)

    def undo(self):
        self._canvas.undo()

    def redo(self):
        self._canvas.redo()

    @property
    def canvas(self) -> PdfCanvas:
        return self._canvas

    # ── 内部 ──────────────────────────────────────

    def _sync_rotation_slider(self):
        if not self._template:
            return
        page = self._canvas.current_page
        rot = 0.0
        if page < len(self._template.page_settings):
            rot = self._template.page_settings[page].rotation
        self._rotation_slider.blockSignals(True)
        self._rotation_slider.setValue(int(round(rot * 10)))
        self._rotation_slider.blockSignals(False)
        self._rotation_value_label.setText(f"{rot:.1f}°")

    # ── 信号处理 ──────────────────────────────────

    def _on_field_selected(self, field_id: str):
        self.field_selected.emit(field_id)

    def _on_page_changed(self, page_num: int):
        self._page_spin.blockSignals(True)
        self._page_spin.setValue(page_num + 1)
        self._page_spin.blockSignals(False)
        self._sync_rotation_slider()

    def _on_page_spin_changed(self, value: int):
        page = value - 1
        if page != self._canvas.current_page:
            self.set_current_page(page)

    def _on_page_rotation_changed(self, value: int):
        rotation = value / 10.0
        self._rotation_value_label.setText(f"{rotation:.1f}°")
        page = self._canvas.current_page
        self._canvas.set_page_rotation(page, rotation)
        self.page_rotation_changed.emit(page, rotation)

    def _on_rotation_reset(self):
        self._rotation_slider.setValue(0)

    def _on_zoom_out(self):
        self._canvas.zoom_out()

    def _on_zoom_in(self):
        self._canvas.zoom_in()

    def _on_zoom_fit(self):
        self._canvas.zoom_fit()

    def _on_canvas_zoom_changed(self, percent: int):
        self._zoom_label.setText(f"{percent}%")