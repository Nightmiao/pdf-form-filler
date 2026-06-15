"""预览对话框 — 弹窗显示填好的 PDF 预览"""

import tempfile
import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QScrollArea
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


class PreviewDialog(QDialog):
    """填好的 PDF 预览对话框"""

    def __init__(self, template, record, template_manager, parent=None):
        super().__init__(parent)
        self._template = template
        self._record = record
        self._template_manager = template_manager
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle(f"预览 - {self._template.name}")
        self.resize(800, 1000)

        layout = QVBoxLayout(self)

        # 诊断信息
        field_count = len(self._template.fields)
        value_count = len(self._record.values)
        has_values = any(v for v in self._record.values.values() if v)
        diag_text = f"字段数: {field_count} | 记录值数: {value_count} | 有非空值: {has_values}"
        info = QLabel(diag_text)
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet("background: #fff3cd; color: #856404; padding: 6px; font-size: 12px; border-radius: 3px;")
        layout.addWidget(info)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        # 生成预览
        from app.core.pdf_engine import burn_text, pdf_to_images
        pdf_path = self._template_manager.get_pdf_path(self._template.id)

        tmp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp_file.close()
        output_path = burn_text(
            pdf_path,
            self._template.fields,
            self._record.values,
            self._template.page_settings,
            tmp_file.name,
        )

        # 检查输出的 PDF 是否包含了文字
        import fitz
        check_doc = fitz.open(output_path)
        check_text = ""
        for pn in range(check_doc.page_count):
            check_text += check_doc[pn].get_text()
        check_doc.close()

        has_output = len(check_text.strip()) > 0
        result_text = f"烧录后PDF文本: {'有内容' if has_output else '【空】'} ({len(check_text)} 字符)"
        result = QLabel(result_text)
        result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        color = "#155724" if has_output else "#721c24"
        bg = "#d4edda" if has_output else "#f8d7da"
        result.setStyleSheet(f"background: {bg}; color: {color}; padding: 6px; font-size: 12px; border-radius: 3px;")
        layout.addWidget(result)

        # 渲染为图片（用 150 DPI 保证文字清晰可见）
        images = pdf_to_images(output_path, dpi=150)

        from PySide6.QtWidgets import QWidget
        content = QWidget()
        cl = QVBoxLayout(content)
        for i, img in enumerate(images):
            lbl = QLabel()
            lbl.setPixmap(img)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(lbl)
        scroll.setWidget(content)
        layout.addWidget(scroll)

        self._tmp_file = tmp_file.name
        self.finished.connect(self._cleanup)

    def _cleanup(self):
        if hasattr(self, '_tmp_file') and os.path.exists(self._tmp_file):
            try:
                os.unlink(self._tmp_file)
            except OSError:
                pass
