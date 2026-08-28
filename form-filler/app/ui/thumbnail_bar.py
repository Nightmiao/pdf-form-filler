"""缩略图导航栏 — 左侧多页缩略图（带页码标签与选中高亮）"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame, QHBoxLayout,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPixmap

from app.core.field_model import TemplateMeta
from app.core.pdf_engine import render_thumbnail

THUMB_WIDTH = 168


class ThumbItem(QFrame):
    """单页缩略图卡片：图片 + 页码"""

    clicked = Signal(int)

    def __init__(self, page_num: int, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.page_num = page_num
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(THUMB_WIDTH + 4)

        v = QVBoxLayout(self)
        v.setContentsMargins(4, 6, 4, 4)
        v.setSpacing(4)

        self._img = QLabel()
        self._img.setPixmap(pixmap)
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        v.addWidget(self._img)

        self._label = QLabel(f"第 {page_num + 1} 页")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setProperty("role", "meta")
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        v.addWidget(self._label)

    def set_current(self, current: bool):
        if current:
            self.setObjectName("cardSelected")
            self._label.setStyleSheet(
                "color: #1D4ED8; font-weight: 700; font-size: 12px; background: transparent;"
            )
        else:
            self.setObjectName("card")
            self._label.setStyleSheet("color: #6B7280; font-size: 12px; background: transparent;")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.page_num)
            return
        super().mousePressEvent(event)


class ThumbnailBar(QWidget):
    """左侧缩略图导航栏"""

    page_clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[ThumbItem] = []
        self._current_page: int = 0
        self._page_count: int = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title_row = QHBoxLayout()
        title = QLabel("页面导航")
        title.setProperty("role", "sectionTitle")
        title_row.addWidget(title)
        title_row.addStretch()
        self._page_label = QLabel("")
        self._page_label.setProperty("role", "meta")
        title_row.addWidget(self._page_label)
        layout.addLayout(title_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._thumb_widget = QWidget()
        self._thumb_layout = QVBoxLayout(self._thumb_widget)
        self._thumb_layout.setContentsMargins(0, 0, 0, 0)
        self._thumb_layout.setSpacing(8)
        self._thumb_layout.addStretch()

        scroll.setWidget(self._thumb_widget)
        layout.addWidget(scroll, stretch=1)

    def load_pages(self, template: TemplateMeta, pdf_path: str):
        self._page_count = template.page_count
        self._current_page = 0
        self._items = []

        while self._thumb_layout.count() > 1:
            item = self._thumb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i in range(self._page_count):
            thumb = render_thumbnail(pdf_path, i, 96)
            scaled = thumb.scaledToWidth(
                THUMB_WIDTH, Qt.TransformationMode.SmoothTransformation
            )
            item = ThumbItem(i, scaled)
            item.clicked.connect(self._on_page_clicked)
            self._items.append(item)
            self._thumb_layout.insertWidget(self._thumb_layout.count() - 1, item)

        self.set_current_page(0)

    def set_current_page(self, page_num: int):
        self._current_page = page_num
        self._page_label.setText(f"{page_num + 1} / {self._page_count}")
        for i, item in enumerate(self._items):
            item.set_current(i == page_num)

    def _on_page_clicked(self, page_num: int):
        self.set_current_page(page_num)
        self.page_clicked.emit(page_num)
