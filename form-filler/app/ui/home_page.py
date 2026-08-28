"""首页 — 模板库：缩略图卡片墙、搜索（防抖）、新建/导入、空状态引导"""

from __future__ import annotations


import os
from datetime import datetime

from app.qt import (
    QtWidgets, QtCore, QtGui, Qt,
    std_button, menu_exec, orientation,
)

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QLineEdit = QtWidgets.QLineEdit
QPushButton = QtWidgets.QPushButton
QFileDialog = QtWidgets.QFileDialog
QLabel = QtWidgets.QLabel
QMessageBox = QtWidgets.QMessageBox
QMenu = QtWidgets.QMenu
QFrame = QtWidgets.QFrame
QScrollArea = QtWidgets.QScrollArea
QLayout = QtWidgets.QLayout
QLayoutItem = QtWidgets.QLayoutItem
QStyle = QtWidgets.QStyle
Signal = QtCore.Signal
QRect = QtCore.QRect
QSize = QtCore.QSize
QPoint = QtCore.QPoint
QTimer = QtCore.QTimer
QPixmap = QtGui.QPixmap

from app.ui.theme import apply_role, icon_of
from app.core.field_model import TemplateMeta
from app.core.pdf_engine import render_thumbnail


def format_time(iso: str) -> str:
    """把 ISO 时间格式化成 '今天 14:30' / '昨天' / '2024-06-01'"""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso[:10]
    today = datetime.now().date()
    if dt.date() == today:
        return f"今天 {dt.strftime('%H:%M')}"
    if (today - dt.date()).days == 1:
        return f"昨天 {dt.strftime('%H:%M')}"
    if dt.year == today.year:
        return dt.strftime("%m月%d日")
    return dt.strftime("%Y年%m月%d日")


class FlowLayout(QLayout):
    """自动换行的流式布局，用于模板卡片墙"""

    def __init__(self, parent=None, margin=0, h_spacing=12, v_spacing=12):
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item: QLayoutItem):
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem:
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y = effective.x(), effective.y()
        line_height = 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._h_spacing
            if next_x - self._h_spacing > effective.right() and line_height > 0:
                x = effective.x()
                y += line_height + self._v_spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._h_spacing
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + m.bottom()


class TemplateCard(QFrame):
    """模板卡片：缩略图 + 名称 + 信息 + 填写/设计按钮"""

    clicked = Signal(TemplateMeta, str)  # template, action ("design" | "fill")

    def __init__(self, template: TemplateMeta, thumb_path: str, parent=None):
        super().__init__(parent)
        self.template = template
        self.setObjectName("card")
        self.setFixedWidth(236)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._thumb_label = None
        self._name_label = None
        self._info_label = None
        self._setup_ui(thumb_path)

    def _setup_ui(self, thumb_path: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self._thumb_label = QLabel()
        self._thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._set_thumb(thumb_path)
        self._thumb_label.setFixedHeight(150)
        layout.addWidget(self._thumb_label)

        self._name_label = QLabel(self.template.name)
        self._name_label.setStyleSheet("font-weight: 700; font-size: 13px; color: #1F2329; background: transparent;")
        self._name_label.setWordWrap(True)
        self._name_label.setMaximumHeight(38)
        self._name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self._name_label)

        self._info_label = QLabel()
        self._info_label.setProperty("role", "meta")
        self._info_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self._info_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        fill_btn = QPushButton("填写")
        fill_btn.setIcon(icon_of(self, "SP_DialogApplyButton"))
        apply_role(fill_btn, "primary")
        fill_btn.clicked.connect(lambda: self.clicked.emit(self.template, "fill"))
        btn_row.addWidget(fill_btn, stretch=1)
        design_btn = QPushButton("设计")
        design_btn.setToolTip("修改字段框")
        design_btn.clicked.connect(lambda: self.clicked.emit(self.template, "design"))
        btn_row.addWidget(design_btn)
        layout.addLayout(btn_row)

    def _set_thumb(self, thumb_path: str):
        pixmap = QPixmap()
        if thumb_path and os.path.exists(thumb_path):
            pixmap = QPixmap(thumb_path)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(
                216, 150, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self._thumb_label.setPixmap(pixmap)

    def refresh(self, template: TemplateMeta, thumb_path: str):
        """复用卡片时刷新显示内容"""
        self.template = template
        self._name_label.setText(template.name)
        self._info_label.setText(
            f"{template.page_count} 页 · {len(template.fields)} 个字段 · "
            f"{format_time(template.updated_at)}"
        )
        self._set_thumb(thumb_path)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.template, "fill")
            return
        super().mousePressEvent(event)


class HomePage(QWidget):
    """首页 — 模板管理主页"""

    template_selected = Signal(TemplateMeta, str)  # template, action
    template_deleted = Signal(str)
    help_requested = Signal()

    SEARCH_DEBOUNCE_MS = 300

    def __init__(self, template_manager, parent=None):
        super().__init__(parent)
        self.template_manager = template_manager
        self._templates: list[TemplateMeta] = []
        self._cards: dict[str, TemplateCard] = {}  # 卡片复用缓存
        self._thumb_cache: dict[str, QPixmap] = {}  # 缩略图 pixmap 缓存
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(self.SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self.refresh)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(10)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("我的模板")
        title.setObjectName("pageTitle")
        subtitle = QLabel("为 PDF 表单画好填写框，之后反复快速填写、导出、打印")
        subtitle.setProperty("role", "hint")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        top.addLayout(title_box)

        top.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索模板…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedWidth(220)
        self.search_input.textChanged.connect(self._on_search)
        top.addWidget(self.search_input)

        help_btn = QPushButton("使用说明")
        help_btn.setIcon(icon_of(self, "SP_MessageBoxInformation"))
        help_btn.clicked.connect(self.help_requested)
        top.addWidget(help_btn)

        import_btn = QPushButton("导入模板")
        import_btn.setIcon(icon_of(self, "SP_DialogOpenButton"))
        import_btn.setToolTip("导入 .lmt 模板文件")
        import_btn.clicked.connect(self._on_import_template)
        top.addWidget(import_btn)

        new_btn = QPushButton("新建模板")
        apply_role(new_btn, "primary")
        new_btn.setIcon(icon_of(self, "SP_FileDialogNewFolder"))
        new_btn.setToolTip("选择一张 PDF 表单开始")
        new_btn.clicked.connect(self._on_new_template)
        top.addWidget(new_btn)

        layout.addLayout(top)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self._cards_host = QWidget()
        self._flow = FlowLayout(self._cards_host, margin=4)
        self.scroll.setWidget(self._cards_host)
        layout.addWidget(self.scroll, stretch=1)

        self._empty_state = self._build_state(
            "还没有模板",
            "上传一张 PDF 表单开始吧：画好填写框之后，就能反复快速填写、导出和打印。",
            show_buttons=True,
        )
        layout.addWidget(self._empty_state, stretch=1)
        self._empty_state.hide()

        self._no_result_state = self._build_state(
            "没有找到相关模板",
            "换个关键词试试，或新建一个模板。",
            show_buttons=False,
        )
        layout.addWidget(self._no_result_state, stretch=1)
        self._no_result_state.hide()

        self._result_count = QLabel("")
        self._result_count.setProperty("role", "hint")
        layout.addWidget(self._result_count)

    def _build_state(self, title_text: str, desc: str, show_buttons: bool) -> QFrame:
        frame = QFrame()
        frame.setObjectName("emptyState")
        v = QVBoxLayout(frame)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.setSpacing(10)

        icon = QLabel("📄")
        icon.setObjectName("emptyIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(icon)

        t = QLabel(title_text)
        t.setObjectName("emptyTitle")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(t)

        d = QLabel(desc)
        d.setObjectName("emptyDesc")
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        d.setWordWrap(True)
        v.addWidget(d)

        if show_buttons:
            row = QHBoxLayout()
            row.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.setSpacing(10)
            b1 = QPushButton("新建模板")
            apply_role(b1, "primary")
            b1.clicked.connect(self._on_new_template)
            row.addWidget(b1)
            b2 = QPushButton("导入模板")
            b2.clicked.connect(self._on_import_template)
            row.addWidget(b2)
            v.addLayout(row)
        return frame

    # ── 刷新 ──────────────────────────────────────

    def refresh(self):
        keyword = self.search_input.text().strip() if hasattr(self, "search_input") else ""
        if keyword:
            self._templates = self.template_manager.search(keyword)
        else:
            self._templates = self.template_manager.list_all()
        self._render_cards()

    def _render_cards(self):
        seen: set[str] = set()
        for tmpl in self._templates:
            seen.add(tmpl.id)
            thumb_path = self.template_manager.get_thumbnail_path(tmpl.id)
            if not thumb_path:
                thumb_path = self._ensure_thumb(tmpl)
            card = self._cards.get(tmpl.id)
            if card is None:
                card = TemplateCard(tmpl, thumb_path)
                card.clicked.connect(self._on_card_clicked)
                card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                card.customContextMenuRequested.connect(
                    lambda pos, t=tmpl: self._show_context_menu(pos, t)
                )
                self._cards[tmpl.id] = card
                self._flow.addWidget(card)
            else:
                card.refresh(tmpl, thumb_path)

        # 移除不在当前结果里的卡片
        stale = [tid for tid in self._cards if tid not in seen]
        for tid in stale:
            card = self._cards.pop(tid)
            self._flow.removeWidget(card)
            card.deleteLater()

        has_templates = bool(self._templates)
        self.scroll.setVisible(has_templates)
        self._empty_state.setVisible(not has_templates and not self._searching())
        self._no_result_state.setVisible(not has_templates and self._searching())
        if has_templates and self._searching():
            self._result_count.setText(f"找到 {len(self._templates)} 个模板")
        else:
            self._result_count.setText("")

    def _searching(self) -> bool:
        return bool(self.search_input.text().strip()) if hasattr(self, "search_input") else False

    def _ensure_thumb(self, tmpl: TemplateMeta) -> str:
        """老数据没有缩略图时补渲染一张"""
        try:
            pdf_path = self.template_manager.pdf_path(tmpl.id)
            if os.path.exists(pdf_path):
                pixmap = render_thumbnail(pdf_path, 0, 96)
                path = self.template_manager.thumb_path(tmpl.id)
                pixmap.save(path, "PNG")
                return path
        except Exception:
            pass
        return ""

    # ── 事件 ──────────────────────────────────────

    def _on_card_clicked(self, template: TemplateMeta, action: str):
        self.template_selected.emit(template, action)

    def _show_context_menu(self, pos, template: TemplateMeta):
        menu = QMenu(self)
        rename_action = menu.addAction("重命名")
        export_action = menu.addAction("导出模板 (.lmt)")
        menu.addSeparator()
        delete_action = menu.addAction("删除模板")

        sender_card = self.sender()
        global_pos = (
            sender_card.mapToGlobal(pos) if sender_card else self.mapToGlobal(pos)
        )
        chosen = menu_exec(menu, global_pos)
        if chosen == rename_action:
            self._rename_template(template)
        elif chosen == export_action:
            self._export_template(template)
        elif chosen == delete_action:
            self._delete_template(template)

    def _rename_template(self, template: TemplateMeta):
        from app.qt import QtWidgets
        QInputDialog = QtWidgets.QInputDialog
        new_name, ok = QInputDialog.getText(
            self, "重命名模板", "模板名称：", text=template.name
        )
        if ok and new_name.strip():
            self.template_manager.rename(template.id, new_name.strip())
            template.name = new_name.strip()
            self.refresh()

    def _delete_template(self, template: TemplateMeta):
        reply = QMessageBox.warning(
            self,
            "确认删除",
            f"确定删除模板「{template.name}」吗？\n模板和它的所有填写记录都会被删除，且无法恢复。",
            std_button("Yes") | std_button("No"),
        )
        if reply == std_button("Yes"):
            self.template_manager.delete(template.id)
            self._cards.pop(template.id, None)
            self.template_deleted.emit(template.id)
            self.refresh()

    def _export_template(self, template: TemplateMeta):
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
        # 300ms 防抖：停止输入后才真正刷新卡片墙
        self._search_timer.start()

    def _on_new_template(self):
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