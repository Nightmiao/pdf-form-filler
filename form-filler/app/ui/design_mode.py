"""设计模式 — PDF 画布 + 工具栏"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QToolBar, QSlider, QLabel,
    QPushButton, QSpinBox, QCheckBox,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QAction, QIcon

from app.ui.pdf_canvas import PdfCanvas
from app.core.field_model import TemplateMeta, FieldDefinition


class DesignMode(QWidget):
    """设计模式容器 — 画布 + 工具栏"""

    field_selected = Signal(str)  # field_id → 右侧面板
    field_created = Signal(object)  # FieldDefinition → 主窗口
    back_to_home = Signal()  # 返回首页
    switch_to_fill = Signal()  # 切换到填写模式
    save_requested = Signal()  # 保存模板

    def __init__(self, parent=None):
        super().__init__(parent)
        self._template: TemplateMeta | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏
        self._toolbar = self._create_toolbar()
        layout.addWidget(self._toolbar)

        # PDF 画布
        self._canvas = PdfCanvas()
        self._canvas.set_mode(PdfCanvas.MODE_DESIGN)
        self._canvas.field_created.connect(self._on_field_created)
        self._canvas.field_modified.connect(self._on_field_modified)
        self._canvas.field_deleted.connect(self._on_field_deleted)
        self._canvas.field_selected_sig.connect(self._on_field_selected)
        self._canvas.current_page_changed.connect(self._on_page_changed)
        self._canvas.zoom_changed.connect(self._on_canvas_zoom_changed)
        layout.addWidget(self._canvas)

        # 工具栏开关接入画布（此时 _canvas 已创建）
        self._snap_check.toggled.connect(self._canvas.set_snap_enabled)
        self._align_check.toggled.connect(self._canvas.set_alignment_enabled)
        self._zoom_slider.valueChanged.connect(self._on_zoom_slider_changed)
        # 应用初始开关状态
        self._canvas.set_snap_enabled(self._snap_check.isChecked())
        self._canvas.set_alignment_enabled(self._align_check.isChecked())

    def _create_toolbar(self) -> QToolBar:
        """创建设计模式工具栏"""
        toolbar = QToolBar()
        toolbar.setMovable(False)

        # 返回按钮
        back_btn = QPushButton("🏠 返回首页")
        back_btn.setFixedHeight(28)
        back_btn.clicked.connect(self.back_to_home)
        toolbar.addWidget(back_btn)

        save_btn = QPushButton("💾 保存模板 (Ctrl+S)")
        save_btn.setFixedHeight(28)
        save_btn.setStyleSheet("background-color: #27ae60; color: white; border: none; border-radius: 3px; padding: 0 10px; font-weight: bold;")
        save_btn.clicked.connect(self.save_requested)
        toolbar.addWidget(save_btn)

        fill_btn = QPushButton("✏️ 填写模式")
        fill_btn.setFixedHeight(28)
        fill_btn.setStyleSheet("background-color: #4a90d9; color: white; border: none; border-radius: 3px; padding: 0 10px;")
        fill_btn.clicked.connect(self.switch_to_fill)
        toolbar.addWidget(fill_btn)

        toolbar.addSeparator()

        # 页码导航
        toolbar.addWidget(QLabel(" 页码: "))
        self._page_spin = QSpinBox()
        self._page_spin.setMinimum(1)
        self._page_spin.setValue(1)
        self._page_spin.setFixedWidth(50)
        self._page_spin.valueChanged.connect(self._on_page_spin_changed)
        toolbar.addWidget(self._page_spin)

        toolbar.addSeparator()

        # 页面旋转滑块
        toolbar.addWidget(QLabel(" 页面旋转: "))
        self._rotation_slider = QSlider(Qt.Orientation.Horizontal)
        self._rotation_slider.setRange(-50, 50)  # -5.0° ~ +5.0°
        self._rotation_slider.setValue(0)
        self._rotation_slider.setFixedWidth(120)
        self._rotation_slider.valueChanged.connect(self._on_page_rotation_changed)
        toolbar.addWidget(self._rotation_slider)

        self._rotation_value_label = QLabel("0.0°")
        self._rotation_value_label.setFixedWidth(40)
        toolbar.addWidget(self._rotation_value_label)

        toolbar.addSeparator()

        # 网格吸附开关
        self._snap_check = QCheckBox("网格吸附")
        self._snap_check.setChecked(True)
        toolbar.addWidget(self._snap_check)

        self._align_check = QCheckBox("对齐线")
        self._align_check.setChecked(True)
        toolbar.addWidget(self._align_check)

        toolbar.addSeparator()

        # 缩放
        toolbar.addWidget(QLabel(" 缩放: "))
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self._zoom_slider.setRange(50, 300)
        self._zoom_slider.setValue(100)
        self._zoom_slider.setFixedWidth(100)
        toolbar.addWidget(self._zoom_slider)

        zoom_label = QLabel("100%")
        self._zoom_label = zoom_label
        toolbar.addWidget(zoom_label)

        return toolbar

    # ── 公共方法 ──────────────────────────────────

    def load_template(self, template: TemplateMeta, pdf_path: str):
        """加载模板进入设计模式"""
        self._template = template
        self._canvas.load_pdf(pdf_path, template.page_settings)
        self._canvas.load_fields(template.fields)
        self._canvas.show_page(0)

        self._page_spin.setMaximum(template.page_count)
        self._page_spin.setValue(1)

        # 加载页面旋转
        if template.page_settings:
            rot = template.page_settings[0].rotation
            self._rotation_slider.blockSignals(True)
            self._rotation_slider.setValue(int(rot * 10))
            self._rotation_slider.blockSignals(False)
            self._rotation_value_label.setText(f"{rot:.1f}°")

    def set_current_page(self, page_num: int):
        """切换页面"""
        self._canvas.set_current_page(page_num)
        self._page_spin.setValue(page_num + 1)

        # 更新旋转滑块
        if self._template and page_num < len(self._template.page_settings):
            rot = self._template.page_settings[page_num].rotation
            self._rotation_slider.blockSignals(True)
            self._rotation_slider.setValue(int(rot * 10))
            self._rotation_slider.blockSignals(False)
            self._rotation_value_label.setText(f"{rot:.1f}°")

    def update_field(self, field: FieldDefinition):
        """更新字段"""
        self._canvas.update_field(field)

    def remove_field(self, field_id: str):
        """移除字段"""
        self._canvas.remove_field(field_id)

    def select_field(self, field_id: str):
        """选中字段"""
        self._canvas.select_field(field_id)

    def undo(self):
        self._canvas.undo()

    def redo(self):
        self._canvas.redo()

    # ── 信号处理 ──────────────────────────────────

    def _on_field_created(self, field: FieldDefinition):
        """画布上创建了新字段"""
        if self._template:
            self._template.fields.append(field)

    def _on_field_modified(self, field: FieldDefinition):
        """画布上字段被修改"""
        if self._template:
            for i, f in enumerate(self._template.fields):
                if f.id == field.id:
                    self._template.fields[i] = field
                    break

    def _on_field_deleted(self, field_id: str):
        """画布上字段被删除"""
        if self._template:
            self._template.fields = [
                f for f in self._template.fields if f.id != field_id
            ]

    def _on_field_selected(self, field_id: str):
        """画布上字段被选中"""
        self.field_selected.emit(field_id)

    def _on_page_changed(self, page_num: int):
        """页面切换"""
        self._page_spin.blockSignals(True)
        self._page_spin.setValue(page_num + 1)
        self._page_spin.blockSignals(False)

    def _on_page_spin_changed(self, value: int):
        """页码输入框改变"""
        page = value - 1
        if page != self._canvas.current_page:
            self.set_current_page(page)

    def _on_page_rotation_changed(self, value: int):
        """页面旋转滑块改变"""
        rotation = value / 10.0
        self._rotation_value_label.setText(f"{rotation:.1f}°")

        if self._template:
            page = self._canvas.current_page
            if page < len(self._template.page_settings):
                self._template.page_settings[page].rotation = rotation
            self._canvas.set_page_rotation(page, rotation)

    def _on_zoom_slider_changed(self, value: int):
        """缩放滑块改变 → 设置画布缩放"""
        self._zoom_label.setText(f"{value}%")
        self._canvas.set_zoom_percent(value)

    def _on_canvas_zoom_changed(self, percent: int):
        """画布缩放变化（如滚轮/快捷键）→ 回写滑块。
        百分比可能超出滑块范围（如 Ctrl+1 实际比例），滑块按范围 clamp，
        标签显示真实百分比。"""
        self._zoom_slider.blockSignals(True)
        self._zoom_slider.setValue(percent)  # QSlider 自动 clamp 到 [50,300]
        self._zoom_slider.blockSignals(False)
        self._zoom_label.setText(f"{percent}%")
