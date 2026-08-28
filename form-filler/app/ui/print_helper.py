"""打印辅助 — 把填好的 PDF 发送到打印机（自动适应纸张大小）"""

import tempfile
import os
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import Qt


def print_filled_pdf(template, record, template_manager, parent=None):
    """打印填好的 PDF — 先烧录到临时文件，再逐页按纸张比例打印"""
    from app.core.pdf_engine import burn_text

    pdf_path = template_manager.get_pdf_path(template.id)

    tmp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_file.close()
    output_path = burn_text(
        pdf_path, template.fields, record.values,
        template.page_settings, tmp_file.name,
    )

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setDocName(template.name)

    dialog = QPrintDialog(printer, parent)
    if dialog.exec() != QPrintDialog.DialogCode.Accepted:
        try:
            os.unlink(tmp_file.name)
        except OSError:
            pass
        return

    try:
        import fitz
        doc = fitz.open(output_path)
        painter = QPainter(printer)
        dpi = printer.logicalDpiX()

        for page_num in range(doc.page_count):
            if page_num > 0:
                printer.newPage()

            page = doc[page_num]
            zoom = dpi / 72.0
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            pixmap = QPixmap()
            pixmap.loadFromData(pix.tobytes("png"))

            # 按纸张可打印区域等比缩放并居中
            paper = printer.pageRect(QPrinter.Unit.DevicePixel)
            scale = min(
                paper.width() / pixmap.width(),
                paper.height() / pixmap.height(),
            )
            w = int(pixmap.width() * scale)
            h = int(pixmap.height() * scale)
            x = paper.x() + (paper.width() - w) // 2
            y = paper.y() + (paper.height() - h) // 2
            painter.drawPixmap(x, y, w, h, pixmap)

        painter.end()
        doc.close()
    finally:
        try:
            os.unlink(tmp_file.name)
        except OSError:
            pass
