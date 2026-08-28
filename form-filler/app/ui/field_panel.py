"""右侧面板 — 设计模式：字段列表+属性编辑；填写模式：当前项输入+记录管理"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QScrollArea,
    QLabel, QLineEdit, QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox,
    QPushButton, QGroupBox, QTextEdit, QDateEdit, QListWidget,
    QListWidgetItem, QMessageBox, QProgressBar, QStyle,
)
from PySide6.QtCore import Signal, Qt, QDate, QEvent
from PySide6.QtGui import QColor

from app.ui.theme import apply_role, icon_of
from app.core.field_model import FieldDefinition, FillRecord

DATE_MIN = QDate(1900, 1, 1)


class FieldDesignPanel(QWidget):
    """设计模式右侧面板 — 字段列表 + 属性编辑"""

    field_updated = Signal(FieldDefinition)
    field_focus_requested = Signal(str)
    field_delete_requested = Signal(str)
    field_duplicate_requested = Signal(str)
    tab_order_changed = Signal(object)  # 拖拽排序后的完整字段列表

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_field: FieldDefinition | None = None
        self._fields: list[FieldDefinition] = []
        self._template = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("字段设置")
        title.setProperty("role", "sectionTitle")
        layout.addWidget(title)

        # 字段列表
        self._field_list = QListWidget()
        self._field_list.currentRowChanged.connect(self._on_field_selected_in_list)
        self._field_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._field_list.model().rowsMoved.connect(self._on_fields_reordered)
        layout.addWidget(self._field_list, stretch=1)

        self._list_hint = QLabel("还没有字段。在 PDF 上按住鼠标左键拖拽画框")
        self._list_hint.setProperty("role", "hint")
        self._list_hint.setWordWrap(True)
        layout.addWidget(self._list_hint)

        # 字段操作按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        dup_btn = QPushButton("复制")
        dup_btn.setIcon(icon_of(self, QStyle.StandardPixmap.SP_FileDialogNewFolder))
        dup_btn.setToolTip("复制选中字段（Ctrl+D）")
        dup_btn.clicked.connect(self._on_duplicate_field)
        btn_row.addWidget(dup_btn)

        del_btn = QPushButton("删除")
        apply_role(del_btn, "danger")
        del_btn.setIcon(icon_of(self, QStyle.StandardPixmap.SP_TrashIcon))
        del_btn.setToolTip("删除选中字段（Delete）")
        del_btn.clicked.connect(self._on_delete_field)
        btn_row.addWidget(del_btn)
        layout.addLayout(btn_row)

        # 属性编辑区
        props_group = QGroupBox("选中字段的属性")
        self._props_group = props_group
        props_layout = QVBoxLayout(props_group)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        self._props_form = QFormLayout(scroll_widget)
        self._props_form.setContentsMargins(4, 4, 4, 4)
        self._props_form.setSpacing(8)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("如：姓名、电话…")
        self._name_edit.textChanged.connect(self._on_prop_changed)
        self._props_form.addRow("名称", self._name_edit)

        self._type_combo = QComboBox()
        self._type_combo.addItems(["文本", "数字", "日期", "下拉选择", "勾选框"])
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        self._props_form.addRow("类型", self._type_combo)

        self._font_size_spin = QDoubleSpinBox()
        self._font_size_spin.setRange(6, 72)
        self._font_size_spin.setValue(12)
        self._font_size_spin.setSuffix(" pt")
        self._font_size_spin.valueChanged.connect(self._on_prop_changed)
        self._props_form.addRow("字号", self._font_size_spin)

        self._align_combo = QComboBox()
        self._align_combo.addItems(["左对齐", "居中", "右对齐"])
        self._align_combo.currentIndexChanged.connect(self._on_prop_changed)
        self._props_form.addRow("对齐", self._align_combo)

        self._required_check = QCheckBox("此项必须填写")
        self._required_check.toggled.connect(self._on_prop_changed)
        self._props_form.addRow("必填", self._required_check)

        self._default_edit = QLineEdit()
        self._default_edit.setPlaceholderText("留空表示无默认内容")
        self._default_edit.textChanged.connect(self._on_prop_changed)
        self._props_form.addRow("默认值", self._default_edit)

        self._max_len_spin = QSpinBox()
        self._max_len_spin.setRange(0, 9999)
        self._max_len_spin.setSpecialValueText("不限制")
        self._max_len_spin.valueChanged.connect(self._on_prop_changed)
        self._props_form.addRow("最大长度", self._max_len_spin)

        self._multiline_check = QCheckBox("允许输入多行")
        self._multiline_check.toggled.connect(self._on_prop_changed)
        self._props_form.addRow("多行文本", self._multiline_check)

        self._options_label = QLabel("下拉选项")
        self._options_edit = QTextEdit()
        self._options_edit.setPlaceholderText("每行一个选项，例如：\n男\n女")
        self._options_edit.setMaximumHeight(88)
        self._options_edit.textChanged.connect(self._on_options_changed)
        self._props_form.addRow(self._options_label, self._options_edit)

        self._rotation_spin = QDoubleSpinBox()
        self._rotation_spin.setRange(-180, 180)
        self._rotation_spin.setValue(0)
        self._rotation_spin.setSuffix("°")
        self._rotation_spin.valueChanged.connect(self._on_prop_changed)
        self._props_form.addRow("旋转角度", self._rotation_spin)

        self._props_hint = QLabel("在画布上拖动字段、拖四角手柄可改位置和大小")
        self._props_hint.setProperty("role", "hint")
        self._props_hint.setWordWrap(True)
        self._props_form.addRow("", self._props_hint)

        scroll.setWidget(scroll_widget)
        props_layout.addWidget(scroll)
        layout.addWidget(props_group, stretch=1)
        self._props_group.setEnabled(False)

    # ── 加载 ──────────────────────────────────────

    def load_fields(self, template):
        """加载模板的所有字段到列表（保持画布上的选择）"""
        self._fields = template.fields[:]
        self._template = template
        self._refresh_field_list()

    def select_field(self, field_id: str):
        """选中指定字段（按 id 查找，避免顺序错位）"""
        for i in range(self._field_list.count()):
            item = self._field_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == field_id:
                self._field_list.blockSignals(True)
                self._field_list.setCurrentRow(i)
                self._field_list.blockSignals(False)
                self._on_field_selected_in_list(i)
                return
        # 找不到时清空属性区
        self._current_field = None
        self._block_prop_signals(True)
        self._name_edit.clear()
        self._block_prop_signals(False)
        self._props_group.setEnabled(False)
        self._update_list_hint()

    # ── 内部 ──────────────────────────────────────

    def _refresh_field_list(self):
        selected_id = (
            self._current_field.id if self._current_field is not None else ""
        )
        self._field_list.blockSignals(True)
        self._field_list.clear()
        for f in sorted(self._fields, key=lambda x: (x.page, x.tab_order, x.name)):
            item = QListWidgetItem(f"{f.name}　[{f.display_type}]　第{f.page + 1}页")
            item.setData(Qt.ItemDataRole.UserRole, f.id)
            if f.required:
                item.setForeground(QColor(200, 0, 0))
            self._field_list.addItem(item)
        # 恢复选中高亮
        if selected_id:
            for i in range(self._field_list.count()):
                if self._field_list.item(i).data(Qt.ItemDataRole.UserRole) == selected_id:
                    self._field_list.setCurrentRow(i)
                    break
        self._field_list.blockSignals(False)
        self._update_list_hint()

    def _update_current_row_text(self):
        """属性修改时只更新当前行的显示文本，避免整表重建丢选中"""
        if self._current_field is None:
            return
        f = self._current_field
        for i in range(self._field_list.count()):
            item = self._field_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == f.id:
                item.setText(f"{f.name}　[{f.display_type}]　第{f.page + 1}页")
                item.setForeground(QColor(200, 0, 0) if f.required else QColor(31, 35, 41))
                break

    def _update_list_hint(self):
        has = self._field_list.count() > 0
        self._list_hint.setVisible(not has)
        self._field_list.setVisible(has)

    def _on_field_selected_in_list(self, row: int):
        if row < 0:
            return
        item = self._field_list.item(row)
        if item is None:
            return
        fid = item.data(Qt.ItemDataRole.UserRole)
        field = next((f for f in self._fields if f.id == fid), None)
        if field is None:
            return
        self._current_field = field
        self._populate_properties(field)
        self._props_group.setEnabled(True)
        self.field_focus_requested.emit(field.id)

    def _populate_properties(self, field: FieldDefinition):
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
        self._rotation_spin.setValue(field.rotation)
        self._update_options_visibility()
        self._block_prop_signals(False)

    def _block_prop_signals(self, block: bool):
        for w in (
            self._name_edit, self._type_combo, self._font_size_spin,
            self._align_combo, self._required_check, self._default_edit,
            self._max_len_spin, self._multiline_check, self._options_edit,
            self._rotation_spin,
        ):
            w.blockSignals(block)

    def _update_options_visibility(self):
        is_select = self._type_combo.currentIndex() == 3
        self._options_label.setVisible(is_select)
        self._options_edit.setVisible(is_select)

    def _apply_properties(self):
        if self._current_field is None:
            return
        f = self._current_field
        f.name = self._name_edit.text().strip() or "未命名字段"
        type_map = {0: "text", 1: "number", 2: "date", 3: "select", 4: "checkbox"}
        f.field_type = type_map.get(self._type_combo.currentIndex(), "text")
        f.font_size = self._font_size_spin.value()
        align_map = {0: "left", 1: "center", 2: "right"}
        f.alignment = align_map.get(self._align_combo.currentIndex(), "left")
        f.required = self._required_check.isChecked()
        f.default_value = self._default_edit.text()
        f.max_length = self._max_len_spin.value()
        f.multiline = self._multiline_check.isChecked()
        f.select_options = [
            line.strip() for line in self._options_edit.toPlainText().split("\n") if line.strip()
        ]
        f.rotation = self._rotation_spin.value()

    # ── 信号处理 ──────────────────────────────────

    def _on_prop_changed(self, *args):
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
        if self._current_field is None:
            return
        fid = self._current_field.id
        reply = QMessageBox.question(
            self, "确认删除", f"确定删除字段「{self._current_field.name}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._fields = [f for f in self._fields if f.id != fid]
            if self._template is not None:
                self._template.fields = self._fields
            self._current_field = None
            self._props_group.setEnabled(False)
            self._refresh_field_list()
            self.field_delete_requested.emit(fid)

    def _on_duplicate_field(self):
        if self._current_field is not None:
            self.field_duplicate_requested.emit(self._current_field.id)

    def _on_fields_reordered(self):
        """拖拽排序后更新 TAB 顺序，并通知主窗口同步画布"""
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
        if self._template is not None:
            self._template.fields = self._fields
        self.tab_order_changed.emit(self._fields)


class FieldFillPanel(QWidget):
    """填写模式右侧面板 — 当前项输入 + 记录管理 + 操作"""

    field_value_changed = Signal(str, str)
    tab_next_requested = Signal()
    tab_prev_requested = Signal()
    save_requested = Signal()
    preview_requested = Signal()
    export_requested = Signal()
    print_requested = Signal()
    record_selected = Signal(str)
    record_new_requested = Signal()
    record_rename_requested = Signal(str)
    record_delete_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fields: list[FieldDefinition] = []
        self._record: FillRecord | None = None
        self._values: dict[str, str] = {}
        self._current_field_id: str = ""
        self._records: list[FillRecord] = []
        self._current_widget = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ── 记录管理 ──
        record_group = QGroupBox("填写记录")
        rg = QVBoxLayout(record_group)
        self._record_combo = QComboBox()
        self._record_combo.setToolTip("切换这份表单的其他填写记录")
        self._record_combo.currentIndexChanged.connect(self._on_record_combo_changed)
        rg.addWidget(self._record_combo)
        rbtn = QHBoxLayout()
        rbtn.setSpacing(4)
        new_btn = QPushButton("新建")
        new_btn.setIcon(icon_of(self, QStyle.StandardPixmap.SP_FileIcon))
        new_btn.setToolTip("为这张表单新建一份填写记录（如给另一个人填）")
        new_btn.clicked.connect(self.record_new_requested)
        rbtn.addWidget(new_btn)
        rename_btn = QPushButton("重命名")
        rename_btn.setToolTip("给当前记录改个名字")
        rename_btn.clicked.connect(lambda: self._request_rename())
        rbtn.addWidget(rename_btn)
        del_btn = QPushButton("删除")
        apply_role(del_btn, "danger")
        del_btn.setToolTip("删除当前记录")
        del_btn.clicked.connect(lambda: self._request_delete())
        rbtn.addWidget(del_btn)
        rg.addLayout(rbtn)
        layout.addWidget(record_group)

        # ── 进度 ──
        progress_group = QGroupBox("填写进度")
        pg = QVBoxLayout(progress_group)
        self._progress_label = QLabel("共 0 项")
        self._progress_label.setProperty("role", "meta")
        pg.addWidget(self._progress_label)
        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        pg.addWidget(self._progress_bar)
        self._progress_warn = QLabel("")
        self._progress_warn.setProperty("role", "error")
        self._progress_warn.setWordWrap(True)
        pg.addWidget(self._progress_warn)
        layout.addWidget(progress_group)

        # ── 当前项 ──
        field_group = QGroupBox("当前填写项")
        self._field_title = QLabel("请选择一项")
        self._field_title.setStyleSheet("font-weight: 700; font-size: 14px; color: #1F2329;")
        self._field_hint = QLabel("")
        self._field_hint.setProperty("role", "hint")
        self._field_hint.setWordWrap(True)
        self._input_host = QVBoxLayout()
        self._input_host.setSpacing(6)
        fg = QVBoxLayout(field_group)
        fg.addWidget(self._field_title)
        fg.addWidget(self._field_hint)
        fg.addLayout(self._input_host)
        fg.addStretch()
        layout.addWidget(field_group, stretch=1)

        # 上一个 / 下一个
        nav = QHBoxLayout()
        nav.setSpacing(6)
        self._prev_btn = QPushButton("上一个")
        self._prev_btn.setIcon(icon_of(self, QStyle.StandardPixmap.SP_ArrowUp))
        self._prev_btn.clicked.connect(self.tab_prev_requested)
        nav.addWidget(self._prev_btn)
        self._next_btn = QPushButton("下一个 (Tab)")
        apply_role(self._next_btn, "primary")
        self._next_btn.setIcon(icon_of(self, QStyle.StandardPixmap.SP_ArrowDown))
        self._next_btn.clicked.connect(self.tab_next_requested)
        nav.addWidget(self._next_btn)
        layout.addLayout(nav)

        # ── 操作 ──
        actions = QHBoxLayout()
        actions.setSpacing(6)
        save_btn = QPushButton("保存草稿")
        save_btn.setIcon(icon_of(self, QStyle.StandardPixmap.SP_DialogSaveButton))
        save_btn.setToolTip("保存填写进度 (Ctrl+S)")
        save_btn.clicked.connect(self.save_requested)
        actions.addWidget(save_btn)
        preview_btn = QPushButton("预览")
        preview_btn.setIcon(icon_of(self, QStyle.StandardPixmap.SP_FileDialogContentsView))
        preview_btn.setToolTip("预览填写后的效果")
        preview_btn.clicked.connect(self.preview_requested)
        actions.addWidget(preview_btn)
        layout.addLayout(actions)

        actions2 = QHBoxLayout()
        actions2.setSpacing(6)
        export_btn = QPushButton("导出 PDF")
        apply_role(export_btn, "primary")
        export_btn.setIcon(icon_of(self, QStyle.StandardPixmap.SP_DialogSaveButton))
        export_btn.setToolTip("把填写内容烧录进 PDF 并保存为新文件")
        export_btn.clicked.connect(self.export_requested)
        actions2.addWidget(export_btn)
        print_btn = QPushButton("打印")
        print_btn.setIcon(icon_of(self, QStyle.StandardPixmap.SP_ComputerIcon))
        print_btn.setToolTip("直接打印 (Ctrl+P)")
        print_btn.clicked.connect(self.print_requested)
        actions2.addWidget(print_btn)
        layout.addLayout(actions2)

    # ── 加载 ──────────────────────────────────────

    def load_fields(self, template, record: FillRecord):
        """加载字段并定位到当前字段"""
        self._fields = template.fields[:]
        self._record = record
        self._values = dict(record.values)
        for f in self._fields:
            if f.id not in self._values:
                self._values[f.id] = f.default_value or ""
        ordered = sorted(self._fields, key=lambda f: (f.page, f.tab_order, f.name))
        if ordered:
            self.set_current_field(ordered[0].id)
        else:
            self.set_current_field("")
        self._update_progress()

    def set_records(self, records: list[FillRecord], current_id: str):
        self._records = records
        self._record_combo.blockSignals(True)
        self._record_combo.clear()
        for r in records:
            self._record_combo.addItem(r.name or "未命名记录", r.id)
        idx = next((i for i, r in enumerate(records) if r.id == current_id), -1)
        self._record_combo.setCurrentIndex(idx)
        self._record_combo.blockSignals(False)
        self._record_combo.setEnabled(len(records) > 0)

    def set_current_field(self, field_id: str):
        """切换到指定字段的输入控件"""
        if field_id and field_id != self._current_field_id:
            # 先收好旧控件的值
            self._collect_widget_value()
        self._current_field_id = field_id
        self._rebuild_input()

    def focus_field(self, field_id: str):
        self.set_current_field(field_id)
        if self._current_widget is not None:
            self._current_widget.setFocus()

    def get_current_values(self) -> dict[str, str]:
        self._collect_widget_value()
        return dict(self._values)

    def update_field_value(self, field_id: str, value: str):
        """外部更新值（如撤销后）：非当前字段仅同步缓存，当前字段重建控件"""
        self._values[field_id] = value
        if field_id == self._current_field_id:
            self._rebuild_input()
        self._update_progress()

    def sync_value(self, field_id: str, value: str):
        """静默同步值缓存：更新缓存；若该字段控件正显示，也把控件同步成该值"""
        self._values[field_id] = value
        if field_id == self._current_field_id and self._current_widget is not None:
            w = self._current_widget
            w.blockSignals(True)
            try:
                if isinstance(w, QLineEdit):
                    w.setText(value)
                elif isinstance(w, QTextEdit):
                    w.setPlainText(value)
                elif isinstance(w, QComboBox):
                    idx = w.findData(value)
                    w.setCurrentIndex(idx if idx >= 0 else 0)
                elif isinstance(w, QDateEdit):
                    d = QDate.fromString(value, "yyyy-MM-dd")
                    w.setDate(d if d.isValid() else DATE_MIN)
                elif isinstance(w, QCheckBox):
                    w.setChecked(value.lower() in ("true", "1", "yes", "√", "✓", "是"))
            finally:
                w.blockSignals(False)
        self._update_progress()

    # ── 内部 ──────────────────────────────────────

    def _collect_widget_value(self):
        if self._current_widget is None or not self._current_field_id:
            return
        fid = self._current_field_id
        w = self._current_widget
        if isinstance(w, QLineEdit):
            self._values[fid] = w.text()
        elif isinstance(w, QTextEdit):
            self._values[fid] = w.toPlainText()
        elif isinstance(w, QComboBox):
            self._values[fid] = w.currentData() or ""
        elif isinstance(w, QDateEdit):
            self._values[fid] = (
                "" if w.date() == DATE_MIN else w.date().toString("yyyy-MM-dd")
            )
        elif isinstance(w, QCheckBox):
            self._values[fid] = "true" if w.isChecked() else "false"

    def _rebuild_input(self):
        # 清除旧控件
        while self._input_host.count():
            item = self._input_host.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._current_widget = None

        field = next((f for f in self._fields if f.id == self._current_field_id), None)
        if field is None:
            self._field_title.setText("请选择一项")
            self._field_hint.setText("点击左侧 PDF 上的蓝色框，或按 Tab 键依次填写")
            self._update_progress()
            return

        title = field.name
        if field.required:
            title += "　*"
        self._field_title.setText(title)

        value = self._values.get(field.id, field.default_value or "")
        hints = []
        if field.required:
            hints.append("必填")
        if field.max_length > 0 and field.field_type == "text":
            hints.append(f"最多 {field.max_length} 字")
        self._field_hint.setText("　·　".join(hints) if hints else "　")

        widget = None
        if field.field_type == "select":
            w = QComboBox()
            w.addItem("请选择…", "")
            for opt in field.select_options:
                w.addItem(opt, opt)
            if value in field.select_options:
                w.setCurrentIndex(field.select_options.index(value) + 1)
            w.currentTextChanged.connect(
                lambda v, fid=field.id, w=w: self._on_widget_changed(fid)
            )
            widget = w
        elif field.field_type == "date":
            w = QDateEdit()
            w.setCalendarPopup(True)
            w.setMinimumDate(DATE_MIN)
            w.setSpecialValueText("未填写")
            w.setDisplayFormat("yyyy-MM-dd")
            if value:
                d = QDate.fromString(value, "yyyy-MM-dd")
                w.setDate(d if d.isValid() else DATE_MIN)
            else:
                w.setDate(DATE_MIN)
            w.dateChanged.connect(lambda d, fid=field.id: self._on_widget_changed(fid))
            widget = w
        elif field.field_type == "checkbox":
            w = QCheckBox("已勾选此项")
            w.setChecked(value.lower() in ("true", "yes", "1", "√", "✓", "是"))
            w.toggled.connect(lambda checked, fid=field.id: self._on_widget_changed(fid))
            widget = w
        elif field.field_type == "number":
            w = QLineEdit()
            w.setPlaceholderText("输入数字…")
            w.setText(value)
            w.textChanged.connect(lambda v, fid=field.id: self._on_widget_changed(fid))
            widget = w
        elif field.multiline:
            w = QTextEdit()
            w.setPlaceholderText(f"输入{field.name}…")
            w.setPlainText(value)
            w.setMaximumHeight(130)
            w.textChanged.connect(lambda fid=field.id: self._on_widget_changed(fid))
            widget = w
        else:
            w = QLineEdit()
            w.setPlaceholderText(f"输入{field.name}…")
            w.setText(value)
            if field.max_length > 0:
                w.setMaxLength(field.max_length)
            w.textChanged.connect(lambda v, fid=field.id: self._on_widget_changed(fid))
            widget = w

        widget.installEventFilter(self)
        self._input_host.addWidget(widget)
        self._current_widget = widget
        self._update_progress()

    def _on_widget_changed(self, field_id: str):
        if self._current_widget is None:
            return
        self._collect_widget_value()
        self.field_value_changed.emit(field_id, self._values.get(field_id, ""))
        self._update_progress()

    def _update_progress(self):
        total = len(self._fields)
        if total == 0:
            self._progress_label.setText("本模板还没有字段")
            self._progress_bar.setValue(0)
            self._progress_warn.setText("")
            return
        filled = 0
        missing_required = []
        for f in self._fields:
            v = self._values.get(f.id, "")
            if f.field_type == "checkbox":
                is_filled = v.lower() in ("true", "1", "yes", "√", "✓", "是")
            else:
                is_filled = bool(v and str(v).strip())
            if is_filled:
                filled += 1
            if f.required and not is_filled:
                missing_required.append(f.name)
        self._progress_label.setText(f"共 {total} 项 · 已填 {filled} 项")
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(filled)
        if missing_required:
            self._progress_warn.setText(
                "还差必填：" + "、".join(missing_required[:4])
                + ("…" if len(missing_required) > 4 else "")
            )
        else:
            self._progress_warn.setText("")

    def _request_rename(self):
        rid = self._record_combo.currentData()
        if rid:
            self.record_rename_requested.emit(rid)

    def _request_delete(self):
        rid = self._record_combo.currentData()
        if rid:
            self.record_delete_requested.emit(rid)

    def _on_record_combo_changed(self, idx: int):
        if idx < 0:
            return
        rid = self._record_combo.itemData(idx)
        if not rid:
            return
        is_new = self._record is None
        is_different = self._record is not None and rid != self._record.id
        if is_new or is_different:
            self.record_selected.emit(rid)

    # ── TAB 快速填写 ──────────────────────────────

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Tab:
            if not isinstance(obj, QTextEdit):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.tab_prev_requested.emit()
                else:
                    self.tab_next_requested.emit()
                return True
        return super().eventFilter(obj, event)