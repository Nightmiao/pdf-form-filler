"""缩略图导航栏 — 左侧多页缩略图"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QPushButton,
    QButtonGroup,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPixmap, QIcon

from app.core.field_model import TemplateMeta
from app.core.pdf_engine import render_thumbnail


class ThumbnailBar(QWidget):
    """左侧缩略图导航栏"""

    page_clicked = Signal(int)  # page_num

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thumbnails: list[QPixmap] = []
        self._current_page: int = 0
        self._page_count: int = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 标题
        title = QLabel("📄 页面导航")
        title.setStyleSheet("font-size: 12px; font-weight: bold;")
        layout.addWidget(title)

        # 页码显示
        self._page_label = QLabel()
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(self._page_label)

        # 缩略图滚动区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._thumb_widget = QWidget()
        self._thumb_layout = QVBoxLayout(self._thumb_widget)
        self._thumb_layout.setContentsMargins(0, 0, 0, 0)
        self._thumb_layout.setSpacing(4)
        self._thumb_layout.addStretch()

        scroll.setWidget(self._thumb_widget)
        layout.addWidget(scroll)

    def load_pages(self, template: TemplateMeta, pdf_path: str):
        """加载所有页面的缩略图"""
        self._page_count = template.page_count
        self._current_page = 0

        # 清除旧缩略图
        while self._thumb_layout.count() > 1:
            item = self._thumb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._thumbnails = []
        for i in range(self._page_count):
            thumb = render_thumbnail(pdf_path, i)

            # 缩放到宽度 180px
            scaled = thumb.scaledToWidth(180, Qt.TransformationMode.SmoothTransformation)
            self._thumbnails.append(scaled)

            # 创建缩略图按钮
            btn = QPushButton()
            btn.setIcon(QIcon(scaled))
            btn.setIconSize(scaled.size())
            btn.setFixedSize(scaled.size().width() + 8, scaled.size().height() + 8)
            btn.setStyleSheet("border: 2px solid transparent; padding: 2px;")
            btn.clicked.connect(lambda checked, p=i: self._on_page_clicked(p))

            # 标签
            label = QLabel(f"第 {i + 1} 页")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("color: #888; font-size: 9px;")

            self._thumb_layout.insertWidget(self._thumb_layout.count() - 1, btn)

        self.set_current_page(0)

    def set_current_page(self, page_num: int):
        """设置当前选中页"""
        self._current_page = page_num
        self._page_label.setText(f"{page_num + 1} / {self._page_count}")

        # 更新缩略图高亮
        for i in range(self._thumb_layout.count() - 1):
            widget = self._thumb_layout.itemAt(i).widget() if i < self._thumb_layout.count() - 1 else None
            if widget and isinstance(widget, QPushButton):
                if i == page_num:
                    widget.setStyleSheet("border: 2px solid #4a90d9; padding: 2px; background: #e8f0fe;")
                else:
                    widget.setStyleSheet("border: 2px solid transparent; padding: 2px;")

    def _on_page_clicked(self, page_num: int):
        """缩略图被点击"""
        self.set_current_page(page_num)
        self.page_clicked.emit(page_num)
