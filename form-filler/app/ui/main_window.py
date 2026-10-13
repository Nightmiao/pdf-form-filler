"""主窗口 — 全局布局、模式切换、记录管理、必填校验与快捷键"""

from __future__ import annotations


import os

from app.qt import (
    QtWidgets, QtCore, QtGui, Qt,
    QAction, std_button, standard_key, dialog_exec, msg_icon, msg_button_role,
    event_key_press,
)

QMainWindow = QtWidgets.QMainWindow
QWidget = QtWidgets.QWidget
QHBoxLayout = QtWidgets.QHBoxLayout
QStackedWidget = QtWidgets.QStackedWidget
QStatusBar = QtWidgets.QStatusBar
QLabel = QtWidgets.QLabel
QPushButton = QtWidgets.QPushButton
QMessageBox = QtWidgets.QMessageBox
QFileDialog = QtWidgets.QFileDialog
QInputDialog = QtWidgets.QInputDialog
QTimer = QtCore.QTimer
QKeySequence = QtGui.QKeySequence

from app.ui.home_page import HomePage
from app.ui.design_mode import DesignMode
from app.ui.fill_mode import FillMode
from app.ui.thumbnail_bar import ThumbnailBar
from app.ui.field_panel import FieldDesignPanel, FieldFillPanel
from app.ui.onboarding import OnboardingDialog
from app.ui.theme import apply_role
from app.core.template_manager import TemplateManager
from app.core.record_manager import RecordManager
from app.core.settings import load_settings, save_settings
from app.core.field_model import TemplateMeta, FillRecord


class MainWindow(QMainWindow):
    """应用程序主窗口"""

    MODE_HOME = 0
    MODE_DESIGN = 1
    MODE_FILL = 2

    def __init__(self, data_dir: str):
        super().__init__()
        self.data_dir = data_dir
        self.template_manager = TemplateManager(data_dir)
        self.record_manager = RecordManager(data_dir)
        self._settings = load_settings(data_dir)

        self._current_template: TemplateMeta | None = None
        self._current_record: FillRecord | None = None
        self._onboarding_shown = False

        self._setup_ui()
        self._setup_shortcuts()
        self._show_home()

    # ── UI 搭建 ────────────────────────────────────

    def _setup_ui(self):
        self.setWindowTitle("狸猫猫表单")
        # 最小尺寸按 1024x768 机器留出余量（含任务栏与窗口边框）；
        # 太小会造成内容不可用，太大则在小屏上够不到右边的面板
        self.setMinimumSize(940, 600)

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧：编辑模式下的缩略图导航（首页时隐藏）
        self.left_panel = QStackedWidget()
        self.left_panel.setFixedWidth(208)
        self.thumbnail_bar = ThumbnailBar()
        self.thumbnail_bar.page_clicked.connect(self._on_thumbnail_page_clicked)
        self.left_panel.addWidget(self.thumbnail_bar)
        main_layout.addWidget(self.left_panel)

        # 窄屏（1024x768 这类机器）自动收起缩略图栏：
        # 208 + 300 两个侧栏会只剩 516px 给中间，工具栏按钮会被挤进
        # "»" 溢出菜单，用户就找不到「保存」「去填写」了。
        self._sidebar_force = None          # None=自动；True/False=用户强制
        self._narrow_threshold = 1180

        # 中央：模式区（0=首页 1=设计 2=填写）
        self.center_stack = QStackedWidget()

        self.home_page = HomePage(self.template_manager)
        self.home_page.template_selected.connect(self._on_template_selected)
        self.home_page.template_deleted.connect(self._on_template_deleted)
        self.home_page.help_requested.connect(self._show_onboarding)
        self.home_page.diagnose_requested.connect(self._run_diagnose)
        self.center_stack.addWidget(self.home_page)

        self.design_mode = DesignMode()
        self.design_mode.field_selected.connect(self._on_field_selected_in_design)
        self.design_mode.back_to_home.connect(self._show_home)
        self.design_mode.switch_to_fill.connect(self._on_design_to_fill)
        self.design_mode.save_requested.connect(self._save_template)
        self.design_mode.fields_restored.connect(self._on_fields_restored)
        self.design_mode.page_rotation_changed.connect(self._on_page_rotation_changed)
        canvas_d = self.design_mode.canvas
        canvas_d.field_created.connect(self._on_field_created_in_canvas)
        canvas_d.field_modified.connect(self._on_field_modified_in_canvas)
        canvas_d.field_deleted.connect(self._on_field_deleted_in_canvas)
        canvas_d.current_page_changed.connect(self._on_canvas_page_changed)
        self.center_stack.addWidget(self.design_mode)

        self.fill_mode = FillMode()
        self.fill_mode.back_to_home.connect(self._show_home)
        self.fill_mode.switch_to_design.connect(self._on_fill_to_design)
        canvas_f = self.fill_mode.canvas
        canvas_f.field_selected_sig.connect(self._on_field_selected_in_fill)
        canvas_f.current_page_changed.connect(self._on_canvas_page_changed)
        self.center_stack.addWidget(self.fill_mode)
        main_layout.addWidget(self.center_stack, stretch=2)

        # 右侧面板
        self.right_panel = QStackedWidget()
        self.right_panel.setMinimumWidth(300)
        self.right_panel.setMaximumWidth(340)

        self.field_design_panel = FieldDesignPanel()
        self.field_design_panel.field_updated.connect(self._on_field_updated)
        self.field_design_panel.field_focus_requested.connect(self._on_field_focus_requested)
        self.field_design_panel.field_delete_requested.connect(self._on_field_delete_requested)
        self.field_design_panel.field_duplicate_requested.connect(self._on_field_duplicate_requested)
        self.field_design_panel.tab_order_changed.connect(self._on_tab_order_changed)
        self.right_panel.addWidget(self.field_design_panel)

        self.field_fill_panel = FieldFillPanel()
        self.field_fill_panel.field_value_changed.connect(self._on_field_value_changed)
        self.field_fill_panel.tab_next_requested.connect(self._on_tab_next)
        self.field_fill_panel.tab_prev_requested.connect(self._on_tab_prev)
        self.field_fill_panel.save_requested.connect(self._on_save_record)
        self.field_fill_panel.preview_requested.connect(self._on_preview)
        self.field_fill_panel.export_requested.connect(self._on_export_pdf)
        self.field_fill_panel.print_requested.connect(self._on_print)
        self.field_fill_panel.record_selected.connect(self._on_record_selected)
        self.field_fill_panel.record_new_requested.connect(self._on_record_new)
        self.field_fill_panel.record_rename_requested.connect(self._on_record_rename)
        self.field_fill_panel.record_delete_requested.connect(self._on_record_delete)
        self.right_panel.addWidget(self.field_fill_panel)
        main_layout.addWidget(self.right_panel)

        # 应用级事件过滤器：填写模式下把 Tab/Shift+Tab 一律交给"下一个/上一个字段"，
        # 不论当前焦点落在输入框、下拉框、按钮还是画布上。
        QtWidgets.QApplication.instance().installEventFilter(self)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._status_label = QLabel("就绪")
        self.status_bar.addWidget(self._status_label)

        # 缩略图栏开关（窄屏会自动收起，这里给用户一个随时可点的入口）
        self._sidebar_btn = QPushButton("缩略图")
        self._sidebar_btn.setCheckable(True)
        self._sidebar_btn.setChecked(True)
        self._sidebar_btn.setText("隐藏缩略图")
        apply_role(self._sidebar_btn, "toolbar")
        self._sidebar_btn.setToolTip("显示 / 隐藏左侧缩略图栏 (Ctrl+B)")
        self._sidebar_btn.clicked.connect(self._on_toggle_sidebar)
        self.status_bar.addPermanentWidget(self._sidebar_btn)

    def _on_toggle_sidebar(self, checked: bool = None):
        """用户手动开关缩略图栏（手动设置优先于自动收起/展开）"""
        want = self._sidebar_btn.isChecked() if checked is None else bool(checked)
        self._sidebar_force = want
        self._sync_sidebar_btn_text(want)
        self._apply_sidebar()

    def _sync_sidebar_btn_text(self, visible: bool):
        if self._sidebar_btn is None:
            return
        self._sidebar_btn.blockSignals(True)
        self._sidebar_btn.setChecked(visible)
        self._sidebar_btn.setText("隐藏缩略图" if visible else "显示缩略图")
        self._sidebar_btn.blockSignals(False)

    def _sidebar_should_show(self) -> bool:
        if self._sidebar_force is not None:
            return self._sidebar_force
        return self.width() >= self._narrow_threshold

    def _apply_sidebar(self):
        """编辑模式下按窗口宽度决定是否显示缩略图栏"""
        if self.center_stack.currentIndex() == self.MODE_HOME:
            self.left_panel.hide()
            return
        show = self._sidebar_should_show()
        self.left_panel.setVisible(show)
        self._sync_sidebar_btn_text(show)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_sidebar()

    def _setup_shortcuts(self):
        save_action = QAction("保存", self)
        save_action.setShortcut(standard_key("Save"))
        save_action.triggered.connect(self._on_save_shortcut)
        self.addAction(save_action)

        undo_action = QAction("撤销", self)
        undo_action.setShortcut(standard_key("Undo"))
        undo_action.triggered.connect(self._on_undo)
        self.addAction(undo_action)

        redo_action = QAction("重做", self)
        redo_action.setShortcut(standard_key("Redo"))
        redo_action.triggered.connect(self._on_redo)
        self.addAction(redo_action)

        print_action = QAction("打印", self)
        print_action.setShortcut(standard_key("Print"))
        print_action.triggered.connect(self._on_print)
        self.addAction(print_action)

        sidebar_action = QAction("显示/隐藏缩略图栏", self)
        sidebar_action.setShortcut(QKeySequence("Ctrl+B"))
        sidebar_action.triggered.connect(
            lambda: self._on_toggle_sidebar(not self._sidebar_should_show())
        )
        self.addAction(sidebar_action)

    # ── 全局事件过滤（填写模式的 Tab 导航）──────────

    def eventFilter(self, obj, event):
        if (
            self.center_stack.currentIndex() == self.MODE_FILL
            and event.type() == event_key_press()
        ):
            key = event.key()
            if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                # 模态对话框（预览 / 打印 / 新建记录等）里保持系统默认行为
                if QtWidgets.QApplication.activeModalWidget() is None:
                    try:
                        same_window = obj.window() is self
                    except AttributeError:
                        same_window = False
                    if same_window:
                        # Ctrl+Tab 放行：多行文本框里用于插入制表符
                        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                            return False
                        backwards = (key == Qt.Key.Key_Backtab) or bool(
                            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                        )
                        if backwards:
                            self.fill_mode.focus_prev_field()
                        else:
                            self.fill_mode.focus_next_field()
                        return True
        return super().eventFilter(obj, event)

    # ── 新手引导 ──────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if not self._onboarding_shown and not self._settings.get("onboarding_done"):
            self._onboarding_shown = True
            QTimer.singleShot(150, self._show_onboarding)

    def _show_onboarding(self):
        dialog = OnboardingDialog(self)
        dialog_exec(dialog)
        self._settings["onboarding_done"] = True
        save_settings(self.data_dir, self._settings)

    def _run_diagnose(self):
        """首页「运行自检」：生成诊断报告（打印落点 + 环境 + 打印机）"""
        try:
            from app.core.diagnostics import show_report_dialog
            path = show_report_dialog(self)
            self._set_status(f"自检报告已保存 - {path}")
        except Exception as e:
            QMessageBox.critical(self, "自检失败", f"无法生成自检报告：\n{e}")

    # ── 模式切换 ──────────────────────────────────

    def _show_home(self):
        if self.center_stack.currentIndex() == self.MODE_DESIGN and self._current_template:
            self._save_template()
        if self.center_stack.currentIndex() == self.MODE_FILL:
            self._save_current_record()

        self._current_template = None
        self._current_record = None
        # 释放两个画布的 PDF 资源（内存打开，退出编辑即释放）
        self.design_mode.canvas.release_pdf()
        self.fill_mode.canvas.release_pdf()
        self.center_stack.setCurrentIndex(self.MODE_HOME)
        self._apply_sidebar()
        self.right_panel.hide()
        self.home_page.refresh()
        self.setWindowTitle("狸猫猫表单")
        self._set_status("选择模板开始，或点击「新建模板」上传 PDF 表单")

    def _enter_design_mode(self, template: TemplateMeta):
        self._current_template = template
        pdf_path = self.template_manager.get_pdf_path(template.id)
        self.design_mode.load_template(template, pdf_path)
        self.center_stack.setCurrentIndex(self.MODE_DESIGN)
        self._apply_sidebar()
        self.left_panel.setCurrentIndex(0)
        self.thumbnail_bar.load_pages(template, pdf_path)
        self.thumbnail_bar.set_current_page(0)
        self.right_panel.show()
        self.right_panel.setCurrentIndex(0)
        self.field_design_panel.load_fields(template)
        self.setWindowTitle(f"设计字段 - {template.name} - 狸猫猫表单")
        self._set_status("按住鼠标左键在表格上拖拽画框；拖动可移动，拖四角圆点可调整大小")

    def _enter_fill_mode(self, template: TemplateMeta, record: FillRecord | None = None):
        self._current_template = template
        if record is None:
            records = self.record_manager.list_for_template(template.id)
            if records:
                record = records[0]
            else:
                record = self.record_manager.create(
                    template.id, self.record_manager.next_name(template.id)
                )
                self.record_manager.save(record)  # 立即落盘，下拉列表与退出恢复都有数据
        self._current_record = record
        self._reload_fill()

    def _reload_fill(self):
        """（重新）加载填写模式：画布 + 面板 + 记录下拉"""
        template = self._current_template
        record = self._current_record
        pdf_path = self.template_manager.get_pdf_path(template.id)
        self.fill_mode.load_template(template, pdf_path, record)
        self.center_stack.setCurrentIndex(self.MODE_FILL)
        self._apply_sidebar()
        self.left_panel.setCurrentIndex(0)
        self.thumbnail_bar.load_pages(template, pdf_path)
        self.right_panel.show()
        self.right_panel.setCurrentIndex(1)
        self.field_fill_panel.load_fields(template, record)
        self._refresh_records()
        self.setWindowTitle(f"填写表单 - {template.name} - 狸猫猫表单")
        self._set_status("点击 PDF 上的蓝色框或按 Tab 依次填写；Ctrl+S 保存草稿")

    def _refresh_records(self):
        if not self._current_template:
            return
        records = self.record_manager.list_for_template(self._current_template.id)
        self.field_fill_panel.set_records(records, self._current_record.id)

    # ── 首页信号 ──────────────────────────────────

    def _on_template_selected(self, template: TemplateMeta, action: str):
        fresh = self.template_manager.get(template.id)
        if fresh is None:
            self._set_status("模板不存在，请刷新")
            return
        if action == "design":
            self._enter_design_mode(fresh)
        elif action == "fill":
            self._enter_fill_mode(fresh)

    def _on_template_deleted(self, template_id: str):
        self._show_home()

    def _on_thumbnail_page_clicked(self, page_num: int):
        if self._current_template is None:
            return
        if self.center_stack.currentIndex() == self.MODE_DESIGN:
            self.design_mode.set_current_page(page_num)
        elif self.center_stack.currentIndex() == self.MODE_FILL:
            self.fill_mode.set_current_page(page_num)
        self.thumbnail_bar.set_current_page(page_num)

    def _on_canvas_page_changed(self, page_num: int):
        self.thumbnail_bar.set_current_page(page_num)

    # ── 设计模式信号 ──────────────────────────────

    def _on_field_selected_in_design(self, field_id: str):
        self.field_design_panel.select_field(field_id)

    def _on_field_created_in_canvas(self, field):
        """画布新建字段：MainWindow 是模板数据的唯一写入方"""
        if self._current_template:
            if not any(f.id == field.id for f in self._current_template.fields):
                self._current_template.fields.append(field)
            self.field_design_panel.load_fields(self._current_template)
            self.field_design_panel.select_field(field.id)
            self._mark_modified()

    def _on_field_modified_in_canvas(self, field):
        if self._current_template:
            for i, f in enumerate(self._current_template.fields):
                if f.id == field.id:
                    self._current_template.fields[i] = field
                    break
            # 同步面板缓存：否则面板旧对象回写会把画布改过的 rotation 等属性归零
            self.field_design_panel.sync_field_object(field)
            self._mark_modified()

    def _on_field_deleted_in_canvas(self, field_id: str):
        if self._current_template:
            self._current_template.fields = [
                f for f in self._current_template.fields if f.id != field_id
            ]
            self.field_design_panel.load_fields(self._current_template)
            self._mark_modified()

    def _on_fields_restored(self, fields: list):
        """撤销/重做后同步模板与面板"""
        if self._current_template:
            self._current_template.fields = fields
            self.field_design_panel.load_fields(self._current_template)
            self._mark_modified()
            self._set_status("已撤销/重做操作")

    def _on_field_updated(self, panel_field):
        """右侧属性面板更新字段。

        面板持有的是字段副本；画布上的对象才带最新几何（rect）。
        因此这里只合并面板可编辑的属性，几何信息以画布为准，
        避免"改个名字，位置弹回原位"的问题。
        """
        if self._current_template is None:
            return
        target = next(
            (f for f in self._current_template.fields if f.id == panel_field.id), None
        )
        if target is None:
            return
        target.name = panel_field.name
        target.field_type = panel_field.field_type
        target.font_size = panel_field.font_size
        target.alignment = panel_field.alignment
        target.required = panel_field.required
        target.default_value = panel_field.default_value
        target.max_length = panel_field.max_length
        target.multiline = panel_field.multiline
        target.select_options = list(panel_field.select_options)
        target.rotation = panel_field.rotation
        target.checked_by_default = panel_field.checked_by_default
        self.design_mode.update_field(target)
        self._mark_modified()

    def _on_field_focus_requested(self, field_id: str):
        if self._current_template:
            self.design_mode.select_field(field_id)

    def _on_field_delete_requested(self, field_id: str):
        self.design_mode.canvas.remove_field(field_id)
        # canvas 会发射 field_deleted → _on_field_deleted_in_canvas 完成清理

    def _on_field_duplicate_requested(self, field_id: str):
        self.design_mode.canvas.select_field_on_page(field_id)
        self.design_mode.canvas.duplicate_selected_field()

    def _on_tab_order_changed(self, fields: list):
        """字段列表拖拽排序 → 同步画布 Tab 顺序"""
        if self._current_template:
            self._current_template.fields = fields
            self.design_mode.canvas.load_fields(fields)
            self._mark_modified()

    def _on_page_rotation_changed(self, page_num: int, rotation: float):
        """页面旋转矫正变化 → 写入模板数据"""
        if self._current_template and page_num < len(self._current_template.page_settings):
            self._current_template.page_settings[page_num].rotation = rotation
            self._mark_modified()

    # ── 填写模式信号 ──────────────────────────────

    def _on_field_selected_in_fill(self, field_id: str):
        self.field_fill_panel.set_current_field(field_id)

    def _on_field_value_changed(self, field_id: str, value: str):
        if self._current_record:
            self._current_record.values[field_id] = value
            self.field_fill_panel.sync_value(field_id, value)
            self.fill_mode.update_field_value(field_id, value)
            self._mark_modified()

    def _on_tab_next(self):
        self.fill_mode.focus_next_field()

    def _on_tab_prev(self):
        self.fill_mode.focus_prev_field()

    def _flush_record(self):
        """把面板当前值收进记录对象"""
        if self._current_record:
            self._current_record.values.update(self.field_fill_panel.get_current_values())

    def _save_current_record(self):
        """收面板值 + 落盘保存当前记录（切换/新建/删除/返回/关闭统一走这里）"""
        if not self._current_record:
            return
        self._flush_record()
        self.record_manager.save(self._current_record)
        self._clear_modified()

    # ── 记录管理 ──────────────────────────────────

    def _on_record_selected(self, record_id: str):
        if not self._current_template:
            return
        self._save_current_record()  # 先把当前记录的修改落盘
        record = self.record_manager.get(self._current_template.id, record_id)
        if record is None:
            return
        self._current_record = record
        self.fill_mode.set_record(record)
        self.field_fill_panel.load_fields(self._current_template, record)
        self._refresh_records()
        self._set_status(f"已切换到「{record.name or '未命名记录'}」")

    def _on_record_new(self):
        if not self._current_template:
            return
        self._save_current_record()  # 先把当前记录的修改落盘
        default = self.record_manager.next_name(self._current_template.id)
        name, ok = QInputDialog.getText(
            self, "新建填写记录",
            "这份记录的用途？（例如：张三的报销单）",
            text=default,
        )
        if not ok:
            return
        record = self.record_manager.create(
            self._current_template.id, name.strip() or default
        )
        self.record_manager.save(record)
        self._current_record = record
        self.fill_mode.set_record(record)
        self.field_fill_panel.load_fields(self._current_template, record)
        self._refresh_records()
        self._set_status(f"已新建记录「{record.name}」，开始填写吧")

    def _on_record_rename(self, record_id: str):
        if not self._current_template:
            return
        record = self.record_manager.get(self._current_template.id, record_id)
        if record is None:
            return
        name, ok = QInputDialog.getText(
            self, "重命名记录", "记录名称：", text=record.name
        )
        if ok and name.strip():
            new_name = name.strip()
            self.record_manager.rename(self._current_template.id, record_id, new_name)
            # 内存里的当前记录必须一起改名：否则之后任何一次自动保存
            # （_save_current_record 整份覆写 JSON）都会把名字改回旧的。
            if self._current_record and self._current_record.id == record_id:
                self._current_record.name = new_name
            self._refresh_records()

    def _on_record_delete(self, record_id: str):
        if not self._current_template:
            return
        records = self.record_manager.list_for_template(self._current_template.id)
        target = next((r for r in records if r.id == record_id), None)
        if target is None:
            return
        # 删除的不是当前记录时，先把当前记录的修改落盘
        if self._current_record and self._current_record.id != record_id:
            self._save_current_record()
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定删除记录「{target.name or '未命名记录'}」吗？\n此操作无法恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.record_manager.delete(self._current_template.id, record_id)
        if self._current_record and self._current_record.id == record_id:
            remaining = self.record_manager.list_for_template(self._current_template.id)
            if remaining:
                self._current_record = remaining[0]
            else:
                # 删的是最后一条记录：必须立刻落盘，否则 _refresh_records 从磁盘
                # 读到 0 条，下拉框被清空并禁用，而创建出来的这条记录没有任何路径
                # 会再触发 _refresh_records（保存/导出都不会），重命名/删除按钮
                # 因 currentData() 为空而静默无反应。
                self._current_record = self.record_manager.create(
                    self._current_template.id,
                    self.record_manager.next_name(self._current_template.id),
                )
                self.record_manager.save(self._current_record)
            self.fill_mode.set_record(self._current_record)
            self.field_fill_panel.load_fields(self._current_template, self._current_record)
        self._refresh_records()

    # ── 保存 / 模式互切 ───────────────────────────

    def _save_template(self):
        if self._current_template:
            self.template_manager.update(self._current_template)
            self._clear_modified()
            self._set_status(f"模板已保存 - {self._current_template.name}")

    def _on_design_to_fill(self):
        if self._current_template:
            self._save_template()
            fresh = self.template_manager.get(self._current_template.id)
            self._enter_fill_mode(fresh or self._current_template)

    def _on_fill_to_design(self):
        if self._current_template:
            self._save_current_record()
            fresh = self.template_manager.get(self._current_template.id)
            self._enter_design_mode(fresh or self._current_template)

    def _on_save_record(self):
        if self._current_record and self._current_template:
            self._save_current_record()
            self._set_status(f"草稿已保存 - {self._current_template.name}")

    def _on_save_shortcut(self):
        if self.center_stack.currentIndex() == self.MODE_DESIGN:
            self._save_template()
        elif self.center_stack.currentIndex() == self.MODE_FILL:
            self._on_save_record()

    # ── 必填校验 ──────────────────────────────────

    def _missing_required(self) -> list:
        self._flush_record()
        values = self._current_record.values if self._current_record else {}
        missing = []
        if self._current_template:
            for f in self._current_template.fields:
                if not f.required:
                    continue
                v = values.get(f.id, f.default_value or "")
                if f.field_type == "checkbox":
                    filled = v.lower() in ("true", "1", "yes", "√", "✓", "是")
                else:
                    filled = bool(v and str(v).strip())
                if not filled:
                    missing.append(f)
        return missing

    def _confirm_required(self) -> bool:
        """导出/打印前检查必填项；返回 True 表示可以继续"""
        missing = self._missing_required()
        if not missing:
            return True
        names = "、".join(f.name for f in missing[:6])
        more = f"…（共 {len(missing)} 项）" if len(missing) > 6 else ""
        box = QMessageBox(self)
        box.setIcon(msg_icon("Warning"))
        box.setWindowTitle("还有必填项未完成")
        box.setText(f"以下必填项还没有填写：\n{names}{more}")
        box.setInformativeText("可以先去补齐，也可以不填直接导出。")
        go_btn = box.addButton("去填写", msg_button_role("ActionRole"))
        export_btn = box.addButton("仍然导出", msg_button_role("AcceptRole"))
        box.addButton("取消", msg_button_role("RejectRole"))
        box.setDefaultButton(go_btn)
        dialog_exec(box)
        clicked = box.clickedButton()
        if clicked is export_btn:
            return True
        if clicked is go_btn:
            # 跳到第一个未填项
            self.fill_mode.canvas.select_field_on_page(missing[0].id)
            self.field_fill_panel.set_current_field(missing[0].id)
        return False

    # ── 预览 / 打印 / 导出 ────────────────────────

    def _on_preview(self):
        if not self._current_template or not self._current_record:
            return
        self._flush_record()
        from app.ui.preview_dialog import PreviewDialog
        dialog = PreviewDialog(
            self._current_template, self._current_record, self.template_manager, self,
            # 预览窗里的"导出/打印"必须走同一套必填校验，否则读 README 的
            # "导出/打印前提示漏填"就有了旁路。
            before_export=self._confirm_required,
        )
        dialog_exec(dialog)

    def _on_print(self):
        if not self._current_template or not self._current_record:
            return
        if not self._confirm_required():
            return
        self._flush_record()
        from app.ui.print_helper import print_filled_pdf
        print_filled_pdf(
            self._current_template, self._current_record, self.template_manager, self
        )

    def _choose_export_path(self) -> str:
        """选择导出路径；不允许覆盖模板原始 PDF；记住上次导出目录"""
        if self._current_template is None:
            return ""
        original = os.path.normcase(os.path.abspath(
            self.template_manager.pdf_path(self._current_template.id)
        ))
        last_dir = self._settings.get("last_export_dir", "")
        default_name = f"{self._current_template.name}_已填写.pdf"
        if last_dir and os.path.isdir(last_dir):
            default_name = os.path.join(last_dir, default_name)
        for attempt in range(2):
            filepath, _ = QFileDialog.getSaveFileName(
                self, "导出填好的 PDF",
                default_name,
                "PDF 文件 (*.pdf)",
            )
            if not filepath:
                return ""
            chosen = os.path.normcase(os.path.abspath(filepath))
            if chosen == original:
                QMessageBox.warning(
                    self, "不能覆盖原文件",
                    "导出的 PDF 不能与模板原始文件保存在同一路径，\n"
                    "请换个文件名或位置（例如文件名后加「_已填写」）。",
                )
                continue
            return filepath
        return ""

    def _on_export_pdf(self):
        if not self._current_template or not self._current_record:
            return
        if not self._confirm_required():
            return
        self._flush_record()
        filepath = self._choose_export_path()
        if filepath:
            from app.core.pdf_engine import burn_text
            pdf_path = self.template_manager.get_pdf_path(self._current_template.id)
            try:
                burn_text(
                    pdf_path,
                    self._current_template.fields,
                    self._current_record.values,
                    self._current_template.page_settings,
                    filepath,
                )
                self._set_status(f"PDF 已导出 - {filepath}")
                self._settings["last_export_dir"] = os.path.dirname(filepath)
                save_settings(self.data_dir, self._settings)
                self._notify_export_done(filepath)
            except Exception as e:
                QMessageBox.critical(self, "导出失败", str(e))

    def _notify_export_done(self, filepath: str):
        """导出成功反馈：弹窗 + 可选打开所在文件夹"""
        box = QMessageBox(self)
        box.setIcon(msg_icon("Information"))
        box.setWindowTitle("导出成功")
        box.setText(f"PDF 已导出：\n{filepath}")
        open_btn = box.addButton("打开所在文件夹", msg_button_role("ActionRole"))
        box.addButton("完成", msg_button_role("AcceptRole"))
        dialog_exec(box)
        if box.clickedButton() is open_btn:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(os.path.dirname(filepath)))

    # ── 撤销 / 重做 ───────────────────────────────

    def _on_undo(self):
        if self.center_stack.currentIndex() == self.MODE_DESIGN:
            self.design_mode.undo()

    def _on_redo(self):
        if self.center_stack.currentIndex() == self.MODE_DESIGN:
            self.design_mode.redo()

    # ── 辅助 ──────────────────────────────────────

    def _mark_modified(self):
        title = self.windowTitle()
        if not title.startswith("* "):
            self.setWindowTitle("* " + title)

    def _clear_modified(self):
        title = self.windowTitle()
        if title.startswith("* "):
            self.setWindowTitle(title[2:])

    def _set_status(self, message: str):
        self._status_label.setText(message)

    def closeEvent(self, event):
        # 退出前自动保存，避免丢数据
        try:
            if self.center_stack.currentIndex() == self.MODE_DESIGN and self._current_template:
                self._save_template()
            if self.center_stack.currentIndex() == self.MODE_FILL:
                self._save_current_record()
        except Exception:
            pass
        event.accept()