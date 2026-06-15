"""主窗口 — 管理全局布局和模式切换"""

import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QStatusBar, QLabel, QMessageBox,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QKeySequence

from app.ui.home_page import HomePage
from app.ui.design_mode import DesignMode
from app.ui.fill_mode import FillMode
from app.core.template_manager import TemplateManager
from app.core.record_manager import RecordManager
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

        self._current_template: TemplateMeta | None = None
        self._current_record: FillRecord | None = None

        self._setup_ui()
        self._setup_shortcuts()
        self._show_home()

    # ── UI 搭建 ────────────────────────────────────

    def _setup_ui(self):
        """搭建主界面结构"""
        self.setWindowTitle("狸猫猫的表单填写工具")
        self.setMinimumSize(900, 600)

        # 中央部件
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧边栏（模板列表 / 缩略图）
        self.left_panel = QStackedWidget()
        self.left_panel.setFixedWidth(220)

        self.home_page = HomePage(self.template_manager)
        self.home_page.template_selected.connect(self._on_template_selected)
        self.home_page.template_deleted.connect(self._on_template_deleted)
        self.left_panel.addWidget(self.home_page)

        # 缩略图导航栏（延迟创建）
        from app.ui.thumbnail_bar import ThumbnailBar
        self.thumbnail_bar = ThumbnailBar()
        self.thumbnail_bar.page_clicked.connect(self._on_thumbnail_page_clicked)
        self.left_panel.addWidget(self.thumbnail_bar)

        main_layout.addWidget(self.left_panel)

        # 中央区域（PDF画布）
        self.center_stack = QStackedWidget()

        # 占位页面（首页时显示）
        self.placeholder = QLabel("请从左侧选择模板，或点击「新建模板」上传PDF表单")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet("color: #888; font-size: 14px;")
        self.center_stack.addWidget(self.placeholder)

        self.design_mode = DesignMode()
        self.design_mode.field_selected.connect(self._on_field_selected_in_design)
        self.design_mode.back_to_home.connect(self._show_home)
        self.design_mode.switch_to_fill.connect(self._on_design_to_fill)
        self.design_mode.save_requested.connect(self._save_template)
        # 画布字段变更 → 刷新面板
        self.design_mode._canvas.field_created.connect(self._on_field_created_in_canvas)
        self.center_stack.addWidget(self.design_mode)

        self.fill_mode = FillMode()
        self.fill_mode.fill_data_changed.connect(self._on_fill_data_changed)
        self.fill_mode.back_to_home.connect(self._show_home)
        self.fill_mode.switch_to_design.connect(self._on_fill_to_design)
        self.fill_mode._canvas.field_selected_sig.connect(self._on_field_selected_in_fill)
        self.center_stack.addWidget(self.fill_mode)

        main_layout.addWidget(self.center_stack, stretch=1)

        # 右侧面板（字段属性 / 填写面板）
        self.right_panel = QStackedWidget()
        self.right_panel.setFixedWidth(300)

        from app.ui.field_panel import FieldDesignPanel, FieldFillPanel
        self.field_design_panel = FieldDesignPanel()
        self.field_design_panel.field_updated.connect(self._on_field_updated)
        self.field_design_panel.field_deleted.connect(self._on_field_deleted)
        self.field_design_panel.field_focus_requested.connect(self._on_field_focus_requested)
        self.right_panel.addWidget(self.field_design_panel)

        self.field_fill_panel = FieldFillPanel()
        self.field_fill_panel.field_value_changed.connect(self._on_field_value_changed)
        self.field_fill_panel.tab_next_requested.connect(self._on_tab_next)
        self.field_fill_panel.save_requested.connect(self._on_save_record)
        self.field_fill_panel.print_requested.connect(self._on_print)
        self.field_fill_panel.export_requested.connect(self._on_export_pdf)
        self.field_fill_panel.preview_requested.connect(self._on_preview)
        self.right_panel.addWidget(self.field_fill_panel)

        main_layout.addWidget(self.right_panel)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._status_label = QLabel("就绪")
        self.status_bar.addWidget(self._status_label)

    def _setup_shortcuts(self):
        """设置全局快捷键"""
        # Ctrl+S 保存
        save_action = QAction("保存", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._on_save_shortcut)
        self.addAction(save_action)

        # Ctrl+Z 撤销
        undo_action = QAction("撤销", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(self._on_undo)
        self.addAction(undo_action)

        # Ctrl+Y 重做
        redo_action = QAction("重做", self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.triggered.connect(self._on_redo)
        self.addAction(redo_action)

        # Ctrl+P 打印
        print_action = QAction("打印", self)
        print_action.setShortcut(QKeySequence.StandardKey.Print)
        print_action.triggered.connect(self._on_print)
        self.addAction(print_action)

    # ── 模式切换 ──────────────────────────────────

    def _show_home(self):
        """切换到首页 — 离开前自动保存"""
        # 如果在设计模式，先保存模板
        if self.center_stack.currentIndex() == self.MODE_DESIGN and self._current_template:
            self._save_template()
        # 如果在填写模式，先保存记录
        if self.center_stack.currentIndex() == self.MODE_FILL and self._current_record:
            self._current_record.values.update(
                self.field_fill_panel.get_current_values()
            )
            self.record_manager.save(self._current_record)

        self._current_template = None
        self._current_record = None
        self.center_stack.setCurrentIndex(0)
        self.left_panel.setCurrentIndex(0)
        self.right_panel.hide()
        self.home_page.refresh()
        self.setWindowTitle("狸猫猫的表单填写工具")
        self._set_status("请选择或创建模板")

    def _enter_design_mode(self, template: TemplateMeta):
        """进入设计模式"""
        self._current_template = template

        pdf_path = self.template_manager.get_pdf_path(template.id)
        self.design_mode.load_template(template, pdf_path)

        self.center_stack.setCurrentIndex(1)  # 设计模式
        self.left_panel.setCurrentIndex(1)  # 缩略图
        self.thumbnail_bar.load_pages(template, pdf_path)
        self.thumbnail_bar.set_current_page(0)
        self.right_panel.show()
        self.right_panel.setCurrentIndex(0)  # 设计面板
        self.field_design_panel.load_fields(template)
        self.setWindowTitle(f"设计模式 - {template.name} - 狸猫猫的表单填写工具")
        self._set_status(f"设计模式 | {template.page_count} 页 | {len(template.fields)} 个字段")

    def _enter_fill_mode(self, template: TemplateMeta, record: FillRecord = None):
        """进入填写模式"""
        self._current_template = template
        self._current_record = record or self.record_manager.create(template.id)

        pdf_path = self.template_manager.get_pdf_path(template.id)
        self.fill_mode.load_template(template, pdf_path, self._current_record)

        self.center_stack.setCurrentIndex(2)  # 填写模式
        self.left_panel.setCurrentIndex(1)  # 缩略图
        self.thumbnail_bar.load_pages(template, pdf_path)
        self.right_panel.show()
        self.right_panel.setCurrentIndex(1)  # 填写面板
        self.field_fill_panel.load_fields(template, self._current_record)
        self.setWindowTitle(f"填写模式 - {template.name} - 狸猫猫的表单填写工具")
        self._set_status(f"填写模式 | TAB 切换字段 | Ctrl+S 保存")

    # ── 信号处理 ──────────────────────────────────

    def _on_template_selected(self, template: TemplateMeta, action: str):
        """模板被选中 — 从磁盘重新加载保证数据最新"""
        # 先从磁盘重新加载模板（确保拿到最新数据）
        fresh = self.template_manager.get(template.id)
        if fresh is None:
            self._set_status("模板不存在，请刷新")
            return
        if action == "design":
            self._enter_design_mode(fresh)
        elif action == "fill":
            self._enter_fill_mode(fresh)
        elif action == "fill_continue":
            records = self.record_manager.list_for_template(fresh.id)
            if records:
                self._enter_fill_mode(fresh, records[0])
            else:
                self._enter_fill_mode(fresh)

    def _on_template_deleted(self, template_id: str):
        """模板被删除"""
        self._show_home()

    def _on_thumbnail_page_clicked(self, page_num: int):
        """缩略图点击切换页面"""
        if self._current_template is None:
            return
        if self.center_stack.currentIndex() == self.MODE_DESIGN:
            self.design_mode.set_current_page(page_num)
        elif self.center_stack.currentIndex() == self.MODE_FILL:
            self.fill_mode.set_current_page(page_num)

    def _on_field_selected_in_design(self, field_id: str):
        """设计模式中字段被选中"""
        if self._current_template:
            # 从模板重新加载字段（画布修改后可能变了）
            self.field_design_panel.load_fields(self._current_template)
            self.field_design_panel.select_field(field_id)

    def _on_field_created_in_canvas(self, field):
        """画布上创建了新字段，刷新面板"""
        if self._current_template:
            self.field_design_panel.load_fields(self._current_template)
            self.field_design_panel.select_field(field.id)

    def _on_field_selected_in_fill(self, field_id: str):
        """填写模式中字段被选中，聚焦填写控件"""
        self.field_fill_panel.focus_field(field_id)

    def _on_design_to_fill(self):
        """从设计模式切换到填写模式"""
        if self._current_template:
            self._save_template()
            # 重新从磁盘加载（确保填写模式拿到完整数据）
            fresh = self.template_manager.get(self._current_template.id)
            if fresh:
                self._enter_fill_mode(fresh)
            else:
                self._enter_fill_mode(self._current_template)

    def _on_fill_to_design(self):
        """从填写模式切换到设计模式"""
        if self._current_template:
            # 先保存填写记录
            if self._current_record:
                self._current_record.values.update(
                    self.field_fill_panel.get_current_values()
                )
                self.record_manager.save(self._current_record)
            # 从磁盘加载模板
            fresh = self.template_manager.get(self._current_template.id)
            if fresh:
                self._enter_design_mode(fresh)
            else:
                self._enter_design_mode(self._current_template)

    def _save_template(self):
        """保存当前模板到磁盘"""
        if self._current_template:
            self.template_manager.update(self._current_template)
            self._set_status(f"模板已保存 - {self._current_template.name}")
            self._clear_modified()

    def _on_field_updated(self, field):
        """字段属性更新"""
        if self._current_template:
            # 更新模板中的字段
            for i, f in enumerate(self._current_template.fields):
                if f.id == field.id:
                    self._current_template.fields[i] = field
                    break
            self.design_mode.update_field(field)
            self._mark_modified()

    def _on_field_deleted(self, field_id: str):
        """字段被删除"""
        if self._current_template:
            self._current_template.fields = [
                f for f in self._current_template.fields if f.id != field_id
            ]
            self.design_mode.remove_field(field_id)
            self._mark_modified()

    def _on_field_focus_requested(self, field_id: str):
        """请求聚焦某个字段"""
        if self._current_template:
            for f in self._current_template.fields:
                if f.id == field_id:
                    self.design_mode.set_current_page(f.page)
                    self.design_mode.select_field(field_id)
                    break

    def _on_fill_data_changed(self, values: dict):
        """填写数据变更"""
        if self._current_record:
            self._current_record.values.update(values)
            self._mark_modified()

    def _on_field_value_changed(self, field_id: str, value: str):
        """单个字段值变更"""
        if self._current_record:
            self._current_record.values[field_id] = value
            # 同步到画布预览
            self.fill_mode.update_field_value(field_id, value)

    def _on_tab_next(self):
        """TAB 跳转到下一个字段"""
        self.fill_mode.focus_next_field()

    def _sync_record_from_panel(self):
        """从填写面板收集最新值，同步到 record"""
        if self._current_record:
            panel_values = self.field_fill_panel.get_current_values()
            self._current_record.values.update(panel_values)

    def _on_save_record(self):
        """保存填写记录"""
        if self._current_record and self._current_template:
            self._sync_record_from_panel()  # 先同步面板值
            self.record_manager.save(self._current_record)
            self._set_status(f"已保存 - {self._current_template.name}")
            self._clear_modified()

    def _on_save_shortcut(self):
        """Ctrl+S 保存"""
        if self.center_stack.currentIndex() == self.MODE_DESIGN:
            self._save_template()
        elif self.center_stack.currentIndex() == self.MODE_FILL:
            self._on_save_record()

    def _on_preview(self):
        """预览填好的 PDF"""
        if not self._current_template or not self._current_record:
            return
        self._sync_record_from_panel()  # 确保拿到最新面板值
        from app.ui.preview_dialog import PreviewDialog
        dialog = PreviewDialog(self._current_template, self._current_record, self.template_manager, self)
        dialog.exec()

    def _on_print(self):
        """打印"""
        if not self._current_template or not self._current_record:
            return
        self._sync_record_from_panel()  # 确保拿到最新面板值
        from app.ui.print_helper import print_filled_pdf
        print_filled_pdf(self._current_template, self._current_record, self.template_manager, self)

    def _on_export_pdf(self):
        """导出填好的 PDF"""
        if not self._current_template or not self._current_record:
            return
        self._sync_record_from_panel()  # 确保拿到最新面板值
        from PySide6.QtWidgets import QFileDialog
        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出填好的PDF", f"{self._current_template.name}_已填写.pdf", "PDF文件 (*.pdf)"
        )
        if filepath:
            from app.core.pdf_engine import burn_text
            pdf_path = self.template_manager.get_pdf_path(self._current_template.id)
            burn_text(
                pdf_path,
                self._current_template.fields,
                self._current_record.values,
                self._current_template.page_settings,
                filepath,
            )
            self._set_status(f"PDF 已导出 - {filepath}")

    def _on_undo(self):
        """撤销"""
        if self.center_stack.currentIndex() == self.MODE_DESIGN:
            self.design_mode.undo()

    def _on_redo(self):
        """重做"""
        if self.center_stack.currentIndex() == self.MODE_DESIGN:
            self.design_mode.redo()

    # ── 辅助方法 ──────────────────────────────────

    def _mark_modified(self):
        """标记为已修改（标题栏显示 *）"""
        title = self.windowTitle()
        if not title.startswith("*"):
            self.setWindowTitle(f"* {title}")

    def _clear_modified(self):
        """清除修改标记"""
        title = self.windowTitle()
        if title.startswith("* "):
            self.setWindowTitle(title[2:])

    def _set_status(self, message: str):
        """设置状态栏消息"""
        self._status_label.setText(message)

    def closeEvent(self, event):
        """关闭窗口时检查未保存的修改"""
        if self.windowTitle().startswith("* "):
            reply = QMessageBox.question(
                self,
                "未保存的修改",
                "有未保存的修改，是否保存后退出？",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._on_save_shortcut()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
