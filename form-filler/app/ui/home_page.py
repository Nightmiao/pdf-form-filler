"""首页 — 模板列表、搜索、新建、导入"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QLabel, QMessageBox,
    QMenu, QAbstractItemView,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QIcon, QAction

from app.core.field_model import TemplateMeta


class TemplateCard(QWidget):
    """模板列表项卡片"""

    clicked = Signal(TemplateMeta, str)  # template, action ("design" | "fill")

    def __init__(self, template: TemplateMeta, thumb_path: str, parent=None):
        super().__init__(parent)
        self.template = template
        self.thumb_path = thumb_path
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 名称
        name_label = QLabel(self.template.name)
        name_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        name_label.setWordWrap(True)
        layout.addWidget(name_label)

        # 信息
        info_label = QLabel(f"{self.template.page_count} 页 · {len(self.template.fields)} 个字段")
        info_label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(info_label)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        design_btn = QPushButton("设计")
        design_btn.setFixedHeight(28)
        design_btn.clicked.connect(lambda: self.clicked.emit(self.template, "design"))
        btn_layout.addWidget(design_btn)

        fill_btn = QPushButton("填写")
        fill_btn.setFixedHeight(28)
        fill_btn.setStyleSheet("background-color: #4a90d9; color: white; border: none; border-radius: 3px; padding: 0 12px;")
        fill_btn.clicked.connect(lambda: self.clicked.emit(self.template, "fill"))
        btn_layout.addWidget(fill_btn)

        layout.addLayout(btn_layout)

    def mouseDoubleClickEvent(self, event):
        """双击进入填写模式"""
        self.clicked.emit(self.template, "fill")


class HomePage(QWidget):
    """首页 — 模板管理主页"""

    template_selected = Signal(TemplateMeta, str)  # template, action
    template_deleted = Signal(str)  # template_id

    def __init__(self, template_manager, parent=None):
        super().__init__(parent)
        self.template_manager = template_manager
        self._templates: list[TemplateMeta] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题
        title = QLabel("📋 模板列表")
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px 0;")
        layout.addWidget(title)

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索模板...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search)
        layout.addWidget(self.search_input)

        # 最近使用
        recent_label = QLabel("最近使用")
        recent_label.setStyleSheet("color: #888; font-size: 10px; padding: 4px 0;")
        layout.addWidget(recent_label)

        # 模板卡片列表
        self.card_widget = QWidget()
        self.card_layout = QVBoxLayout(self.card_widget)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(4)
        self.card_layout.addStretch()

        scroll = QVBoxLayout()
        scroll.addWidget(self.card_widget)
        scroll.addStretch()
        layout.addLayout(scroll)

        # 按钮区
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)

        new_btn = QPushButton("📄 新建模板")
        new_btn.setFixedHeight(36)
        new_btn.clicked.connect(self._on_new_template)
        btn_layout.addWidget(new_btn)

        import_btn = QPushButton("📥 导入模板 (.lmt)")
        import_btn.setFixedHeight(36)
        import_btn.clicked.connect(self._on_import_template)
        btn_layout.addWidget(import_btn)

        back_btn = QPushButton("🏠 回到首页")
        back_btn.setFixedHeight(36)
        back_btn.clicked.connect(self._on_back_home)
        btn_layout.addWidget(back_btn)

        layout.addLayout(btn_layout)

    def refresh(self):
        """刷新模板列表"""
        keyword = self.search_input.text()
        if keyword:
            self._templates = self.template_manager.search(keyword)
        else:
            self._templates = self.template_manager.list_all()
        self._render_cards()

    def _render_cards(self):
        """渲染模板卡片"""
        # 清除旧卡片
        while self.card_layout.count() > 1:  # 保留最后的 stretch
            item = self.card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 添加新卡片
        for tmpl in self._templates[:20]:  # 限制 20 个
            thumb_path = self.template_manager.get_thumbnail_path(tmpl.id)
            card = TemplateCard(tmpl, thumb_path)
            card.clicked.connect(self._on_card_clicked)

            # 右键菜单
            card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            card.customContextMenuRequested.connect(
                lambda pos, t=tmpl: self._show_context_menu(pos, t)
            )

            self.card_layout.insertWidget(self.card_layout.count() - 1, card)

    def _on_card_clicked(self, template: TemplateMeta, action: str):
        """模板卡片被点击"""
        self.template_selected.emit(template, action)

    def _show_context_menu(self, pos, template: TemplateMeta):
        """显示右键菜单"""
        menu = QMenu(self)
        rename_action = menu.addAction("重命名")
        delete_action = menu.addAction("删除")
        export_action = menu.addAction("导出 (.lmt)")

        action = menu.exec_(self.mapToGlobal(pos))
        if action == rename_action:
            self._rename_template(template)
        elif action == delete_action:
            self._delete_template(template)
        elif action == export_action:
            self._export_template(template)

    def _rename_template(self, template: TemplateMeta):
        """重命名模板"""
        from PySide6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(
            self, "重命名模板", "新名称：", text=template.name
        )
        if ok and new_name.strip():
            self.template_manager.rename(template.id, new_name.strip())
            template.name = new_name.strip()
            self.refresh()

    def _delete_template(self, template: TemplateMeta):
        """删除模板"""
        reply = QMessageBox.warning(
            self,
            "确认删除",
            f"确定删除模板「{template.name}」吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.template_manager.delete(template.id)
            self.template_deleted.emit(template.id)
            self.refresh()

    def _export_template(self, template: TemplateMeta):
        """导出模板为 .lmt 文件"""
        from app.core.export_import import export_template
        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出模板", f"{template.name}.lmt", "狸猫猫模板文件 (*.lmt)"
        )
        if filepath:
            try:
                export_template(template, self.template_manager, filepath)
                QMessageBox.information(self, "导出成功", f"模板已导出到：\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", str(e))

    def _on_search(self, text: str):
        """搜索文本变化"""
        self.refresh()

    def _on_new_template(self):
        """新建模板 — 选择 PDF 文件"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择 PDF 表单文件", "", "PDF 文件 (*.pdf);;所有文件 (*)"
        )
        if filepath:
            name = os.path.splitext(os.path.basename(filepath))[0]
            try:
                template = self.template_manager.create(name, filepath)
                self.refresh()
                self.template_selected.emit(template, "design")
            except Exception as e:
                QMessageBox.critical(self, "创建失败", f"无法加载 PDF 文件：\n{e}")

    def _on_import_template(self):
        """导入 .lmt 模板"""
        from app.core.export_import import import_template
        filepath, _ = QFileDialog.getOpenFileName(
            self, "导入模板", "", "狸猫猫模板文件 (*.lmt);;所有文件 (*)"
        )
        if filepath:
            try:
                template = import_template(filepath, self.template_manager)
                self.refresh()
                self.template_selected.emit(template, "design")
            except Exception as e:
                QMessageBox.critical(self, "导入失败", str(e))

    def _on_back_home(self):
        """回到首页"""
        # 重新触发首页显示
        self.refresh()
