"""打印辅助 — 将填好的 PDF 发送到打印机"""

import tempfile
import os
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import Qt


def print_filled_pdf(template, record, template_manager, parent=None):
    """打印填好的 PDF — 先烧录再逐页打印"""
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

    import fitz
    doc = fitz.open(output_path)
    painter = QPainter(printer)

    dpi_x = printer.logicalDpiX()

    for page_num in range(doc.page_count):
        if page_num > 0:
            printer.newPage()

        page = doc[page_num]
        zoom = dpi_x / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        # 通过 PNG 字节流加载，避免 stride 问题
        png_data = pix.tobytes("png")
        pixmap = QPixmap()
        pixmap.loadFromData(png_data)
        painter.drawPixmap(0, 0, pixmap)

    painter.end()
    doc.close()

    try:
        os.unlink(tmp_file.name)
    except OSError:
        pass
