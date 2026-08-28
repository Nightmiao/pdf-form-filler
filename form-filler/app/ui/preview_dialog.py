"""预览对话框 — 弹窗显示填好的 PDF 效果，可直接导出或打印"""

import tempfile
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QScrollArea, QWidget,
    QHBoxLayout, QPushButton, QFileDialog, QMessageBox, QStyle, QApplication,
)
from PySide6.QtCore import Qt

from app.ui.theme import apply_role, icon_of
from app.core.pdf_engine import burn_text, pdf_to_images


class PreviewDialog(QDialog):
    """填好的 PDF 预览对话框"""

    def __init__(self, template, record, template_manager, parent=None):
        super().__init__(parent)
        self._template = template
        self._record = record
        self._template_manager = template_manager
        self._output_path = ""
        self._setup_ui()
        self._build_preview()

    def _setup_ui(self):
        self.setWindowTitle(f"预览 - {self._template.name}")
        screen = QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
        if screen:
            self.resize(
                min(900, screen.width() - 160),
                min(1000, screen.height() - 160),
            )
        else:
            self.resize(820, 940)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        head = QHBoxLayout()
        info = QLabel(
            f"{self._template.name} · 共 {self._template.page_count} 页 · "
            f"填写内容将烧录进 PDF（原始文件不受影响）"
        )
        info.setProperty("role", "hint")
        head.addWidget(info)
        head.addStretch()
        layout.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setSpacing(10)
        scroll.setWidget(self._content)
        layout.addWidget(scroll, stretch=1)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        btns.addStretch()
        export_btn = QPushButton("导出 PDF")
        apply_role(export_btn, "primary")
        export_btn.setIcon(icon_of(self, QStyle.StandardPixmap.SP_DialogSaveButton))
        export_btn.clicked.connect(self._export)
        btns.addWidget(export_btn)
        print_btn = QPushButton("打印")
        print_btn.setIcon(icon_of(self, QStyle.StandardPixmap.SP_ComputerIcon))
        print_btn.clicked.connect(self._print)
        btns.addWidget(print_btn)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btns.addWidget(close_btn)
        layout.addLayout(btns)

        self.finished.connect(self._cleanup)

    def _build_preview(self):
        pdf_path = self._template_manager.get_pdf_path(self._template.id)
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.close()
        self._output_path = burn_text(
            pdf_path,
            self._template.fields,
            self._record.values,
            self._template.page_settings,
            tmp.name,
        )

        images = pdf_to_images(self._output_path, dpi=140)
        for i, img in enumerate(images):
            page_label = QLabel(f"第 {i + 1} 页")
            page_label.setProperty("role", "meta")
            self._content_layout.addWidget(page_label)
            lbl = QLabel()
            lbl.setPixmap(img)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._content_layout.addWidget(lbl)

    def _export(self):
        default_name = f"{self._template.name}_已填写.pdf"
        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出填好的 PDF", default_name, "PDF 文件 (*.pdf)"
        )
        if not filepath:
            return
        try:
            import shutil
            shutil.copy2(self._output_path, filepath)
            QMessageBox.information(self, "导出成功", f"PDF 已保存到：\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _print(self):
        from app.ui.print_helper import print_filled_pdf
        print_filled_pdf(
            self._template, self._record, self._template_manager, self
        )

    def _cleanup(self):
        if self._output_path and os.path.exists(self._output_path):
            try:
                os.unlink(self._output_path)
            except OSError:
                pass
