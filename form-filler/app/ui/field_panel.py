"""字段面板 — 设计模式下编辑字段属性，填写模式下填写内容"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QScrollArea,
    QLabel, QLineEdit, QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox,
    QPushButton, QGroupBox, QTextEdit, QDateEdit, QListWidget,
    QListWidgetItem, QMessageBox, QSlider,
)
from PySide6.QtCore import Signal, Qt, QDate, QEvent
from PySide6.QtGui import QFont, QColor

from app.core.field_model import FieldDefinition, FillRecord


class FieldDesignPanel(QWidget):
    """设计模式右侧面板 — 字段列表 + 属性编辑"""

    field_updated = Signal(FieldDefinition)
    field_deleted = Signal(str)
    field_focus_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_field: FieldDefinition | None = None
        self._fields: list[FieldDefinition] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题
        title = QLabel("📝 字段列表")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        # 字段列表
        self._field_list = QListWidget()
        self._field_list.currentRowChanged.connect(self._on_field_selected_in_list)
        # 支持拖拽排序
        self._field_list.setDragDropMode(self._field_list.DragDropMode.InternalMove)
        self._field_list.model().rowsMoved.connect(self._on_fields_reordered)
        layout.addWidget(self._field_list)

        # 按钮
        btn_row = QHBoxLayout()
        del_btn = QPushButton("删除选中")
        del_btn.clicked.connect(self._on_delete_field)
        btn_row.addWidget(del_btn)
        layout.addLayout(btn_row)

        # 字段属性编辑区
        props_group = QGroupBox("字段属性")
        props_layout = QVBoxLayout(props_group)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        self._props_form = QFormLayout(scroll_widget)
        self._props_form.setContentsMargins(4, 4, 4, 4)
        self._props_form.setSpacing(6)

        # 名称
        self._name_edit = QLineEdit()
        self._name_edit.textChanged.connect(self._on_prop_changed)
        self._props_form.addRow("名称:", self._name_edit)

        # 类型
        self._type_combo = QComboBox()
        self._type_combo.addItems(["文本", "数字", "日期", "下拉选择", "勾选框"])
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        self._props_form.addRow("类型:", self._type_combo)

        # 字号
        self._font_size_spin = QDoubleSpinBox()
        self._font_size_spin.setRange(6, 72)
        self._font_size_spin.setValue(12)
        self._font_size_spin.valueChanged.connect(self._on_prop_changed)
        self._props_form.addRow("字号:", self._font_size_spin)

        # 对齐
        self._align_combo = QComboBox()
        self._align_combo.addItems(["左对齐", "居中", "右对齐"])
        self._align_combo.currentIndexChanged.connect(self._on_prop_changed)
        self._props_form.addRow("对齐:", self._align_combo)

        # 必填
        self._required_check = QCheckBox()
        self._required_check.toggled.connect(self._on_prop_changed)
        self._props_form.addRow("必填:", self._required_check)

        # 默认值
        self._default_edit = QLineEdit()
        self._default_edit.textChanged.connect(self._on_prop_changed)
        self._props_form.addRow("默认值:", self._default_edit)

        # 最大长度
        self._max_len_spin = QSpinBox()
        self._max_len_spin.setRange(0, 9999)
        self._max_len_spin.setSpecialValueText("不限制")
        self._max_len_spin.valueChanged.connect(self._on_prop_changed)
        self._props_form.addRow("最大长度:", self._max_len_spin)

        # 多行
        self._multiline_check = QCheckBox()
        self._multiline_check.toggled.connect(self._on_prop_changed)
        self._props_form.addRow("多行文本:", self._multiline_check)

        # 下拉选项（仅 select 类型可见）
        self._options_label = QLabel("下拉选项:")
        self._options_edit = QTextEdit()
        self._options_edit.setPlaceholderText("每行一个选项")
        self._options_edit.setMaximumHeight(80)
        self._options_edit.textChanged.connect(self._on_options_changed)
        self._props_form.addRow(self._options_label, self._options_edit)

        # 字段旋转
        self._field_rotation_spin = QDoubleSpinBox()
        self._field_rotation_spin.setRange(-180, 180)
        self._field_rotation_spin.setValue(0)
        self._field_rotation_spin.setSuffix("°")
        self._field_rotation_spin.valueChanged.connect(self._on_prop_changed)
        self._props_form.addRow("旋转角度:", self._field_rotation_spin)

        scroll.setWidget(scroll_widget)
        props_layout.addWidget(scroll)
        layout.addWidget(props_group)

    # ── 加载 ──────────────────────────────────────

    def load_fields(self, template):
        """加载模板的所有字段到列表"""
        self._fields = template.fields[:]
        self._template = template
        self._refresh_field_list()

    def select_field(self, field_id: str):
        """选中指定字段"""
        for i, f in enumerate(self._fields):
            if f.id == field_id:
                self._field_list.setCurrentRow(i)
                break

    # ── 内部 ──────────────────────────────────────

    def _refresh_field_list(self):
        """刷新字段列表"""
        self._field_list.blockSignals(True)
        self._field_list.clear()
        for f in sorted(self._fields, key=lambda x: x.tab_order):
            item = QListWidgetItem(f"📌 {f.name}  [{f.display_type}]  第{f.page + 1}页")
            item.setData(Qt.ItemDataRole.UserRole, f.id)
            if f.required:
                item.setForeground(QColor(200, 0, 0))
            self._field_list.addItem(item)
        self._field_list.blockSignals(False)

    def _on_field_selected_in_list(self, row: int):
        """列表中的字段被选中"""
        if row < 0 or row >= len(self._fields):
            return
        self._current_field = self._fields[row]
        self._populate_properties(self._current_field)
        self.field_focus_requested.emit(self._current_field.id)

    def _populate_properties(self, field: FieldDefinition):
        """填充属性编辑器"""
        self._block_prop_signals(True)

        self._name_edit.setText(field.name)

        type_map = {"text": 0, "number": 1, "date": 2, "select": 3, "checkbox": 4}
        self._type_combo.setCurrentIndex(type_map.get(field.field_type, 0))

        self._font_size_spin.setValue(field.font_size)

        align_map = {"left": 0, "center": 1, "right": 2}
        self._align_combo.setCurrentIndex(align_map.get(field.alignment, 0))

        self._required_check.setChecked(field.required)
        self._default_edit.setText(field.default_value)
        self._max_len_spin.setValue(field.max_length)
        self._multiline_check.setChecked(field.multiline)

        self._options_edit.setPlainText("\n".join(field.select_options))
        self._field_rotation_spin.setValue(field.rotation)

        # 根据类型显示/隐藏选项
        self._update_options_visibility()

        self._block_prop_signals(False)

    def _block_prop_signals(self, block: bool):
        """阻塞/解除属性控件信号"""
        self._name_edit.blockSignals(block)
        self._type_combo.blockSignals(block)
        self._font_size_spin.blockSignals(block)
        self._align_combo.blockSignals(block)
        self._required_check.blockSignals(block)
        self._default_edit.blockSignals(block)
        self._max_len_spin.blockSignals(block)
        self._multiline_check.blockSignals(block)
        self._options_edit.blockSignals(block)
        self._field_rotation_spin.blockSignals(block)

    def _update_options_visibility(self):
        """根据字段类型显示/隐藏下拉选项编辑器"""
        is_select = self._type_combo.currentIndex() == 3  # select
        self._options_label.setVisible(is_select)
        self._options_edit.setVisible(is_select)

    def _apply_properties(self):
        """将 UI 值应用到当前字段"""
        if self._current_field is None:
            return

        self._current_field.name = self._name_edit.text()

        type_map = {0: "text", 1: "number", 2: "date", 3: "select", 4: "checkbox"}
        self._current_field.field_type = type_map.get(self._type_combo.currentIndex(), "text")

        self._current_field.font_size = self._font_size_spin.value()

        align_map = {0: "left", 1: "center", 2: "right"}
        self._current_field.alignment = align_map.get(self._align_combo.currentIndex(), "left")

        self._current_field.required = self._required_check.isChecked()
        self._current_field.default_value = self._default_edit.text()
        self._current_field.max_length = self._max_len_spin.value()
        self._current_field.multiline = self._multiline_check.isChecked()

        options_text = self._options_edit.toPlainText()
        self._current_field.select_options = [
            line.strip() for line in options_text.split("\n") if line.strip()
        ]
        self._current_field.rotation = self._field_rotation_spin.value()

    # ── 信号处理 ──────────────────────────────────

    def _on_prop_changed(self, *args):
        """属性变更"""
        if self._current_field is None:
            return
        self._apply_properties()
        self._refresh_field_list()
        self.field_updated.emit(self._current_field)

    def _on_type_changed(self, idx: int):
        self._update_options_visibility()
        self._on_prop_changed()

    def _on_options_changed(self):
        self._on_prop_changed()

    def _on_delete_field(self):
        """删除选中的字段"""
        if self._current_field is None:
            return
        reply = QMessageBox.question(
            self, "确认删除", f"确定删除字段「{self._current_field.name}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            fid = self._current_field.id
            self._fields = [f for f in self._fields if f.id != fid]
            self._template.fields = self._fields
            self._current_field = None
            self._refresh_field_list()
            self.field_deleted.emit(fid)

    def _on_fields_reordered(self):
        """字段拖拽排序后的 TAB 顺序更新"""
        new_order = []
        for i in range(self._field_list.count()):
            item = self._field_list.item(i)
            fid = item.data(Qt.ItemDataRole.UserRole)
            for f in self._fields:
                if f.id == fid:
                    f.tab_order = i
                    new_order.append(f)
                    break
        self._fields = new_order
        self._template.fields = self._fields


class FieldFillPanel(QWidget):
    """填写模式右侧面板 — 动态生成填写控件"""

    field_value_changed = Signal(str, str)  # field_id, value
    tab_next_requested = Signal()
    save_requested = Signal()
    print_requested = Signal()
    export_requested = Signal()
    preview_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fields: list[FieldDefinition] = []
        self._record: FillRecord | None = None
        self._tab_order: list[str] = []  # 按 tab_order 排列的 field_id
        self._widgets: dict[str, QWidget] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题
        title = QLabel("✏️ 填写表单")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._fields_widget = QWidget()
        self._fields_layout = QVBoxLayout(self._fields_widget)
        self._fields_layout.setSpacing(8)
        self._fields_layout.addStretch()
        scroll.setWidget(self._fields_widget)
        layout.addWidget(scroll)

        # 按钮区
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(6)

        save_btn = QPushButton("💾 保存草稿 (Ctrl+S)")
        save_btn.clicked.connect(self.save_requested)
        btn_layout.addWidget(save_btn)

        preview_btn = QPushButton("🔍 预览")
        preview_btn.clicked.connect(self.preview_requested)
        btn_layout.addWidget(preview_btn)

        print_btn = QPushButton("🖨️ 打印 (Ctrl+P)")
        print_btn.clicked.connect(self.print_requested)
        btn_layout.addWidget(print_btn)

        export_btn = QPushButton("📄 导出 PDF")
        export_btn.clicked.connect(self.export_requested)
        btn_layout.addWidget(export_btn)

        layout.addLayout(btn_layout)

    def load_fields(self, template, record: FillRecord):
        """加载字段并动态创建填写控件"""
        self._fields = template.fields[:]
        self._record = record
        self._tab_order = sorted(self._fields, key=lambda f: f.tab_order)
        self._rebuild_widgets()

    def _rebuild_widgets(self):
        """重建所有填写控件"""
        # 清除旧控件
        while self._fields_layout.count() > 1:  # 保留 stretch
            item = self._fields_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._widgets.clear()

        # 为每个字段创建控件
        for field in self._tab_order:
            group = QGroupBox(f"{field.name}")
            if field.required:
                group.setTitle(f"{field.name} *")
                group.setStyleSheet("QGroupBox::title { color: #c00; }")

            gl = QVBoxLayout(group)

            value = self._record.values.get(field.id, field.default_value)

            widget = None
            if field.field_type == "select":
                w = QComboBox()
                w.addItems(field.select_options)
                if value in field.select_options:
                    w.setCurrentText(value)
                w.currentTextChanged.connect(
                    lambda v, fid=field.id: self.field_value_changed.emit(fid, v)
                )
                widget = w
            elif field.field_type == "date":
                w = QDateEdit()
                w.setCalendarPopup(True)
                if value:
                    try:
                        w.setDate(QDate.fromString(value, "yyyy-MM-dd"))
                    except:
                        w.setDate(QDate.currentDate())
                else:
                    w.setDate(QDate.currentDate())
                w.dateChanged.connect(
                    lambda d, fid=field.id: self.field_value_changed.emit(
                        fid, d.toString("yyyy-MM-dd")
                    )
                )
                widget = w
            elif field.field_type == "checkbox":
                w = QCheckBox()
                w.setChecked(value.lower() in ("true", "yes", "1", "☑"))
                w.toggled.connect(
                    lambda checked, fid=field.id: self.field_value_changed.emit(
                        fid, "true" if checked else "false"
                    )
                )
                widget = w
            elif field.field_type == "number":
                w = QLineEdit()
                w.setPlaceholderText("输入数字...")
                w.setText(value)
                w.textChanged.connect(
                    lambda v, fid=field.id: self.field_value_changed.emit(fid, v)
                )
                widget = w
            else:  # text
                if field.multiline:
                    w = QTextEdit()
                    w.setMaximumHeight(100)
                    w.setPlainText(value)
                    w.textChanged.connect(
                        lambda fid=field.id, w=w: self.field_value_changed.emit(
                            fid, w.toPlainText()
                        )
                    )
                else:
                    w = QLineEdit()
                    w.setPlaceholderText(f"输入{field.name}...")
                    w.setText(value)
                    if field.max_length > 0:
                        w.setMaxLength(field.max_length)
                    w.textChanged.connect(
                        lambda v, fid=field.id: self.field_value_changed.emit(fid, v)
                    )
                widget = w

            gl.addWidget(widget)
            self._widgets[field.id] = widget
            # 安装事件过滤器以捕获 TAB 键，实现快速跳到下一个字段
            widget.installEventFilter(self)
            self._fields_layout.insertWidget(self._fields_layout.count() - 1, group)

    def eventFilter(self, obj, event):
        """捕获填写控件上的 TAB 键，发射 tab_next_requested 切换到下一个字段。

        多行文本框（QTextEdit）的 TAB 用于输入制表符，不拦截。
        """
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Tab:
            if not isinstance(obj, QTextEdit):
                self.tab_next_requested.emit()
                return True  # 拦截，阻止默认焦点切换
        return super().eventFilter(obj, event)

    def set_field_value(self, field_id: str, value: str):
        """设置字段值（从外部）"""
        if field_id in self._widgets:
            w = self._widgets[field_id]
            if isinstance(w, QLineEdit):
                w.setText(value)
            elif isinstance(w, QTextEdit):
                w.setPlainText(value)
            elif isinstance(w, QComboBox):
                w.setCurrentText(value)
            elif isinstance(w, QDateEdit):
                try:
                    w.setDate(QDate.fromString(value, "yyyy-MM-dd"))
                except:
                    pass
            elif isinstance(w, QCheckBox):
                w.setChecked(value.lower() in ("true", "yes", "1", "☑"))

    def focus_field(self, field_id: str):
        """聚焦指定字段"""
        if field_id in self._widgets:
            w = self._widgets[field_id]
            w.setFocus()
            # 滚动到可见区域
            if hasattr(w.parent(), 'ensureVisible'):
                pass

    def get_current_values(self) -> dict[str, str]:
        """获取所有字段当前值"""
        values = {}
        for field in self._fields:
            fid = field.id
            if fid in self._widgets:
                w = self._widgets[fid]
                if isinstance(w, QLineEdit):
                    values[fid] = w.text()
                elif isinstance(w, QTextEdit):
                    values[fid] = w.toPlainText()
                elif isinstance(w, QComboBox):
                    values[fid] = w.currentText()
                elif isinstance(w, QDateEdit):
                    values[fid] = w.date().toString("yyyy-MM-dd")
                elif isinstance(w, QCheckBox):
                    values[fid] = "true" if w.isChecked() else "false"
        return values
