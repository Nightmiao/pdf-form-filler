"""打印辅助 — 把填好的 PDF 发送到打印机（自动适应纸张大小）

实现要点：
- 渲染分辨率封顶 300 DPI（打印机的 600/1200 DPI 会让位图达到近万像素、
  数百 MB，QPixmap 加载失败导致整页空白/除零崩溃——按 300 DPI 渲染后
  由打印机驱动放大，表单打印质量足够且稳定）；
- 用 QImage 而非 QPixmap（无纹理尺寸限制）；
- 烧录结果自检：有填写内容但输出 PDF 提取不到文字时明确提示用户；
- 打印机不可用时给出错误提示而不是默默失败。
"""

from __future__ import annotations

import tempfile
import os
from app.qt import (
    QtPrintSupport, QtGui, QtCore, QtWidgets,
    dialog_exec, dialog_accepted,
    printer_high_resolution, printer_device_pixel,
)

QPrinter = QtPrintSupport.QPrinter
QPrintDialog = QtPrintSupport.QPrintDialog
QPainter = QtGui.QPainter
QImage = QtGui.QImage
QMessageBox = QtWidgets.QMessageBox

CAP_DPI = 300  # 打印渲染分辨率上限


def _burn_to_tmp(template, record, template_manager):
    from app.core.pdf_engine import burn_text
    pdf_path = template_manager.get_pdf_path(template.id)
    tmp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_file.close()
    output_path = burn_text(
        pdf_path, template.fields, record.values,
        template.page_settings, tmp_file.name,
    )
    return output_path


def _burned_text_missing(output_path: str, record) -> bool:
    """有填写内容，但烧录结果里提取不到任何文字 → True"""
    values = record.values or {}
    has_values = any(str(v).strip() for v in values.values())
    if not has_values:
        return False
    try:
        import fitz
        doc = fitz.open(output_path)
        text = "".join(p.get_text() for p in doc).strip()
        doc.close()
        return not text
    except Exception:
        return False


def _render_page_image(page, dpi_limit: int) -> QImage:
    """把一页渲染成 QImage（失败自动降级到 150 DPI 重试）"""
    import fitz
    zoom = max(72.0, float(dpi_limit)) / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img = QImage()
    if not img.loadFromData(pix.tobytes("png"), "PNG"):
        pix2 = page.get_pixmap(matrix=fitz.Matrix(150.0 / 72.0, 150.0 / 72.0))
        img.loadFromData(pix2.tobytes("png"), "PNG")
    return img


def print_filled_pdf(template, record, template_manager, parent=None):
    """打印填好的 PDF — 先烧录到临时文件，再逐页按纸张比例打印"""
    output_path = _burn_to_tmp(template, record, template_manager)

    try:
        # 烧录自检：有内容却写不进 PDF 时，先给用户明确提示
        if _burned_text_missing(output_path, record):
            QMessageBox.warning(
                parent, "打印提醒",
                "填写的内容未能写入打印文件，打印出来会是空白表单。\n"
                "请先点「导出 PDF」检查填写内容是否正常。",
            )

        printer = QPrinter(printer_high_resolution())
        printer.setDocName(template.name)

        dialog = QPrintDialog(printer, parent)
        if dialog_exec(dialog) != dialog_accepted():
            return

        painter = QPainter(printer)
        if not painter.isActive():
            painter.end()
            QMessageBox.critical(
                parent, "无法打印",
                "无法连接打印机。请检查打印机驱动与默认打印机设置后重试。",
            )
            return

        try:
            import fitz
            doc = fitz.open(output_path)
            dpi_limit = min(int(printer.logicalDpiX() or CAP_DPI), CAP_DPI)

            for page_num in range(doc.page_count):
                if page_num > 0:
                    printer.newPage()

                page = doc[page_num]
                img = _render_page_image(page, dpi_limit)
                if img.isNull():
                    continue

                try:
                    paper = printer.pageRect(printer_device_pixel())
                except (TypeError, AttributeError):
                    paper = printer.pageRect()  # Qt5 旧签名：无参数版
                if paper.width() <= 0 or paper.height() <= 0:
                    paper = QtCore.QRectF(0, 0, img.width(), img.height())

                # 关键：QPrinter 的画笔坐标系是"设备像素"，直接 drawImage
                # 到设备像素矩形会被裁剪得几乎空白（实测）。正确做法是
                # painter.scale 到设备像素比例后在图像坐标系里绘制。
                scale = min(
                    paper.width() / img.width(),
                    paper.height() / img.height(),
                )
                painter.resetTransform()
                painter.scale(scale, scale)
                painter.translate(
                    paper.x() / scale + (paper.width() / scale - img.width()) / 2,
                    paper.y() / scale + (paper.height() / scale - img.height()) / 2,
                )
                painter.drawImage(QtCore.QPoint(0, 0), img)

            painter.end()
            doc.close()
        finally:
            try:
                painter.end()
            except Exception:
                pass
    finally:
        try:
            os.unlink(output_path)
        except OSError:
            pass