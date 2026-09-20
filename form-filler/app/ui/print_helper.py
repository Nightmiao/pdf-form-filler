"""打印辅助 — 把填好的 PDF 发送到打印机（自动适应纸张大小）

坐标与分辨率要点（每一行都对应一次实测，改动前请先看 tests/print_accuracy.py）：

1) **QPainter 的原点 = 可打印区左上角，不是纸张左上角。**
   实测（PySide2/Qt5，Qt 内置 PDF 引擎与 Windows 打印引擎一致）：
   在画笔坐标 (0,0) 画满 device 矩形，落到纸上的位置正好是 pageRect（含页边距偏移）。
   因此 `printer.pageRect().x()/y()` **不能**再当作偏移量叠加，
   否则整页内容会向右下平移一个页边距（A4 实测 3.5mm，真实打印机 4~6mm），
   右下角还会被裁掉。正确做法是使用画笔自己的逻辑页面矩形
   （`painter.window()`：逻辑坐标下的整块可打印区，原点恒为 0,0）。

2) 渲染分辨率封顶 300 DPI：打印机的 600/1200 DPI 会让位图达到近万像素、
   数百 MB，QImage 加载失败或显存/内存不足导致整页空白。按 300 DPI 渲染后
   由打印机驱动放大，表单打印质量足够且稳定。

3) 打印是耗时操作（每页 300 DPI 渲染 + 位图传输）。必须在页间
   `processEvents()`，否则老机器上界面长时间无响应，用户会以为"打印坏了"。

4) 任何异常都要变成可见的提示框：EXE 是无控制台的 windowed 程序，
   异常直接抛到 Qt 槽里 = 屏幕上什么都不发生，这本身就是"无法打印"。
"""

from __future__ import annotations

import os
import tempfile
import traceback

from app.qt import (
    QtPrintSupport, QtGui, QtCore, QtWidgets, Qt,
    dialog_exec, dialog_accepted,
    printer_high_resolution, printer_device_pixel,
)

QPrinter = QtPrintSupport.QPrinter
QPrintDialog = QtPrintSupport.QPrintDialog
QPainter = QtGui.QPainter
QImage = QtGui.QImage
QMessageBox = QtWidgets.QMessageBox
QApplication = QtWidgets.QApplication

CAP_DPI = 300          # 打印渲染分辨率上限
MIN_DPI = 150          # 渲染失败时的降级分辨率


def _burn_to_tmp(template, record, template_manager):
    from app.core.pdf_engine import burn_text
    pdf_path = template_manager.pdf_path(template.id) if hasattr(
        template_manager, "pdf_path") else template_manager.get_pdf_path(template.id)
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
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    img = QImage()
    img.loadFromData(pix.tobytes("png"), "PNG")
    if img.isNull():
        pix2 = page.get_pixmap(matrix=fitz.Matrix(MIN_DPI / 72.0, MIN_DPI / 72.0), alpha=False)
        img = QImage()
        img.loadFromData(pix2.tobytes("png"), "PNG")
    return img


def _painter_page_rect(painter, printer) -> QtCore.QRectF:
    """画笔逻辑坐标系下的整页可打印矩形。

    实测：QPainter 在 QPrinter 上以"可打印区左上角"为原点，
    `painter.window()` 就是这个逻辑页面的矩形（原点 0,0），
    而 `printer.pageRect()` 带页边距偏移，不能当偏移量用。
    """
    try:
        w = painter.window()
        if not w.isEmpty() and w.width() > 0 and w.height() > 0:
            return QtCore.QRectF(w)
    except Exception:
        pass
    # 兜底：QPaintDevice 尺寸（对打印机即"可打印区像素尺寸"）
    try:
        dev_w, dev_h = int(painter.device().width()), int(painter.device().height())
    except Exception:
        dev_w = dev_h = 0
    if dev_w > 0 and dev_h > 0:
        return QtCore.QRectF(0, 0, dev_w, dev_h)
    try:
        pr = printer.pageRect(printer_device_pixel())
    except (TypeError, AttributeError):
        pr = printer.pageRect()
    if pr.width() > 0 and pr.height() > 0:
        return QtCore.QRectF(0, 0, pr.width(), pr.height())
    return QtCore.QRectF()


def _describe_printer(printer) -> str:
    bits = []
    try:
        bits.append(f"打印机：{printer.printerName() or '(未指定)'}")
    except Exception:
        pass
    try:
        bits.append(f"分辨率：{printer.resolution()} dpi")
    except Exception:
        pass
    try:
        pr = printer.pageRect(printer_device_pixel())
        bits.append(f"可打印区：{pr.width():.0f}x{pr.height():.0f} 设备像素")
    except Exception:
        pass
    return "；".join(bits)


def print_filled_pdf(template, record, template_manager, parent=None) -> bool:
    """打印填好的 PDF — 先烧录到临时文件，再逐页按纸张比例打印。

    返回 True 表示确实把作业送进了打印队列；False 表示用户取消或失败
    （失败时一定会弹提示框，不会静默）。
    """
    try:
        return _print_filled_pdf(template, record, template_manager, parent)
    except Exception as e:
        # 无控制台的 EXE 里，异常抛到 Qt 槽 = 点了打印毫无反应
        traceback.print_exc()
        QMessageBox.critical(
            parent, "打印失败",
            f"打印过程中出错，作业未发送。\n\n{type(e).__name__}: {e}\n\n"
            "可以先用「导出 PDF」确认填写内容正常，再检查打印机驱动。",
        )
        return False


def _print_filled_pdf(template, record, template_manager, parent=None) -> bool:
    output_path = None
    try:
        output_path = _burn_to_tmp(template, record, template_manager)

        # 烧录自检：有内容却写不进 PDF 时，先给用户明确提示
        if _burned_text_missing(output_path, record):
            QMessageBox.warning(
                parent, "打印提醒",
                "填写的内容未能写入打印文件，打印出来会是空白表单。\n"
                "请先点「导出 PDF」检查填写内容是否正常。",
            )

        printer = QPrinter(printer_high_resolution())
        try:
            printer.setDocName(template.name or "狸猫猫表单")
        except Exception:
            pass

        if not printer.isValid():
            QMessageBox.critical(
                parent, "无法打印",
                "系统里没有可用的打印机。\n\n"
                "请先在 Windows 里安装打印机（或添加「Microsoft Print to PDF」"
                "虚拟打印机）并设为默认，然后重试。",
            )
            return False

        dialog = QPrintDialog(printer, parent)
        if dialog_exec(dialog) != dialog_accepted():
            return False

        painter = QPainter(printer)
        if not painter.isActive():
            painter.end()
            QMessageBox.critical(
                parent, "无法打印",
                "无法连接打印机。请检查打印机驱动与默认打印机设置后重试。\n"
                f"（{_describe_printer(printer)}）",
            )
            return False

        doc = None
        old_cursor = False
        try:
            import fitz
            doc = fitz.open(output_path)
            if doc.page_count <= 0:
                QMessageBox.warning(parent, "打印提醒", "这个 PDF 没有任何页面，无法打印。")
                return False

            dpi_limit = min(int(printer.logicalDpiX() or CAP_DPI), CAP_DPI)
            if dpi_limit < MIN_DPI:
                dpi_limit = MIN_DPI

            # 逻辑页面矩形只取一次：painter.window() 恒为设备默认矩形，
            # 与后面 translate/scale 无关（那两个改的是世界变换）。
            device_rect = _painter_page_rect(painter, printer)

            try:
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                old_cursor = True
            except Exception:
                old_cursor = False

            blank_pages = []
            for page_num in range(doc.page_count):
                if page_num > 0:
                    if not printer.newPage():
                        # 驱动拒绝新页：继续画只会把内容叠在上一页，必须报出来
                        blank_pages.append(page_num + 1)
                        continue
                    QApplication.processEvents()   # 老机器上避免"假死"

                page = doc[page_num]
                img = _render_page_image(page, dpi_limit)
                if img.isNull() or img.width() <= 0 or img.height() <= 0:
                    blank_pages.append(page_num + 1)
                    continue

                if device_rect.width() <= 0 or device_rect.height() <= 0:
                    blank_pages.append(page_num + 1)
                    continue

                # 等比缩放，居中铺满可打印区。
                # 关键：画笔原点已经是可打印区左上角，这里不再叠加 pageRect 的
                # 页边距偏移，否则整页会右下平移一个页边距并被裁边。
                scale = min(
                    device_rect.width() / img.width(),
                    device_rect.height() / img.height(),
                )
                painter.resetTransform()
                painter.scale(scale, scale)
                painter.translate(
                    device_rect.x() / scale + (device_rect.width() / scale - img.width()) / 2.0,
                    device_rect.y() / scale + (device_rect.height() / scale - img.height()) / 2.0,
                )
                painter.drawImage(QtCore.QPointF(0, 0), img)

            painter.end()
            if old_cursor:
                QApplication.restoreOverrideCursor()
                old_cursor = False

            if blank_pages:
                pages = "、".join(str(p) for p in blank_pages[:10])
                QMessageBox.warning(
                    parent, "部分页面未打印",
                    f"第 {pages} 页没能送出到打印机（渲染失败或驱动拒绝新页）。\n"
                    "可以改用「导出 PDF」，再用系统自带的阅读器打印。",
                )
            return True
        finally:
            if old_cursor:
                try:
                    QApplication.restoreOverrideCursor()
                except Exception:
                    pass
            try:
                painter.end()
            except Exception:
                pass
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass
    finally:
        if output_path:
            try:
                os.unlink(output_path)
            except OSError:
                pass
