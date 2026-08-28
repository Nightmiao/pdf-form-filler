"""缩略图导航栏 — 左侧多页缩略图（后台线程渲染，不阻塞界面）"""

from __future__ import annotations


import threading

from app.qt import QtWidgets, QtCore, QtGui, Qt

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QLabel = QtWidgets.QLabel
QScrollArea = QtWidgets.QScrollArea
QFrame = QtWidgets.QFrame
QHBoxLayout = QtWidgets.QHBoxLayout
Signal = QtCore.Signal
QTimer = QtCore.QTimer
QPixmap = QtGui.QPixmap
QPainter = QtGui.QPainter
QColor = QtGui.QColor

from app.core.field_model import TemplateMeta
from app.core.pdf_engine import PdfSource, bytes_to_pixmap

THUMB_WIDTH = 168
THUMB_DPI = 96


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

    def set_pixmap(self, pixmap: QPixmap):
        if not pixmap.isNull():
            self._img.setPixmap(pixmap)

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


def _placeholder_pixmap() -> QPixmap:
    pm = QPixmap(THUMB_WIDTH, int(THUMB_WIDTH * 1.42))
    pm.fill(QColor(238, 241, 245))
    painter = QPainter(pm)
    painter.setPen(QColor(160, 170, 185))
    painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "加载中…")
    painter.end()
    return pm


class ThumbnailBar(QWidget):
    """左侧缩略图导航栏"""

    page_clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[ThumbItem] = []
        self._current_page: int = 0
        self._page_count: int = 0
        self._generation: int = 0
        self._job: dict | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._collect_job)
        self._timer.start()
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
        """先显示占位图，缩略图在后台线程渲染完成后逐页回填"""
        self._generation += 1
        generation = self._generation
        self._job = None
        self._page_count = template.page_count
        self._current_page = 0
        self._items = []

        while self._thumb_layout.count() > 1:
            item = self._thumb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        placeholder = _placeholder_pixmap()
        for i in range(self._page_count):
            item = ThumbItem(i, placeholder)
            item.clicked.connect(self._on_page_clicked)
            self._items.append(item)
            self._thumb_layout.insertWidget(self._thumb_layout.count() - 1, item)

        self.set_current_page(0)

        # 后台一次打开渲染全部页
        job = {"done": False, "bytes": []}
        self._job = job

        def worker():
            try:
                source = PdfSource(pdf_path)
                try:
                    job["bytes"] = source.render_all_page_bytes(THUMB_DPI)
                finally:
                    source.close()
            except Exception:
                job["bytes"] = []
            job["done"] = True

        threading.Thread(target=worker, daemon=True).start()
        self._job_generation = generation

    def _collect_job(self):
        job = self._job
        if job is None or not job.get("done"):
            return
        self._job = None
        # 只回填属于当前加载批次的结果
        gen_ok = getattr(self, "_job_generation", 0) == self._generation
        if not gen_ok or not job.get("bytes"):
            return
        for i, data in enumerate(job["bytes"]):
            if i >= len(self._items):
                break
            pixmap = bytes_to_pixmap(data)
            if not pixmap.isNull():
                scaled = pixmap.scaledToWidth(
                    THUMB_WIDTH, Qt.TransformationMode.SmoothTransformation
                )
                self._items[i].set_pixmap(scaled)

    def set_current_page(self, page_num: int):
        self._current_page = page_num
        self._page_label.setText(f"{page_num + 1} / {self._page_count}")
        for i, item in enumerate(self._items):
            item.set_current(i == page_num)

    def _on_page_clicked(self, page_num: int):
        self.set_current_page(page_num)
        self.page_clicked.emit(page_num)