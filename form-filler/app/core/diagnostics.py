"""运行自检 — 生成一份可发给开发者的诊断报告

目标机是离线 Windows 7，出问题时没法连调试器；这份报告覆盖：
运行环境、屏幕与 DPI、中文字体、打印机列表、可打印区实测值，
以及**一次完整的打印落点自检**（走真实打印管线输出到临时 PDF，
量出基准方块的实际落点误差，不需要真打印机、不弹对话框、不浪费纸）。

入口有两处：
- 命令行 `狸猫猫表单.exe --diagnose`
- 界面首页的「运行自检」按钮
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime

from app.qt import QtWidgets, QtCore, QtGui, QT6, QtPrintSupport

PT = 72.0
MM = 25.4


def _print_roundtrip(lines, add):
    """打印落点自检：渲染 → 坐标换算 → 绘制，全链路走一遍并量误差"""
    tmpdir = tempfile.mkdtemp(prefix="lmm_diag_")
    src = os.path.join(tmpdir, "form.pdf")
    out = os.path.join(tmpdir, "printed.pdf")
    src_w, src_h = 595.0, 842.0
    marks = [(100.0, 100.0), (555.0, 802.0)]      # 两个基准方块左上角
    try:
        import fitz
        from app.core.template_manager import TemplateManager
        from app.core.field_model import FieldDefinition, FillRecord

        doc = fitz.open()
        page = doc.new_page(width=src_w, height=src_h)
        for (mx, my) in marks:
            page.draw_rect(fitz.Rect(mx, my, mx + 30, my + 30),
                           color=None, fill=(0, 0, 0), width=0)
        page.insert_text((100, 200), "DIAG", fontsize=14)
        doc.save(src)
        doc.close()

        tm = TemplateManager(tmpdir)
        meta = tm.create("诊断", src)
        fld = FieldDefinition(name="姓名", field_type="text", page=0,
                              rect=(100, 220, 300, 250), font_size=12, tab_order=0)
        meta.fields.append(fld)
        tm.update(meta)
        rec = FillRecord(template_id=meta.id, name="d")
        rec.values[fld.id] = "打印落点自检"

        import app.ui.print_helper as ph
        captured = {}
        real_qprinter = ph.QPrinter

        def _fake_qprinter(*a, **k):
            p = real_qprinter(*a, **k)
            p.setOutputFormat(QtPrintSupport.QPrinter.PdfFormat)
            p.setOutputFileName(out)
            captured["printer"] = p
            return p

        class _FakeDialog:
            def __init__(self, printer, parent=None):
                self.printer = printer
            def exec_(self):
                return 1
            def exec(self):
                return 1

        class _QuietBox:
            messages = []
            @staticmethod
            def warning(*a, **k):
                _QuietBox.messages.append(str(a[2]) if len(a) > 2 else str(a))
            @staticmethod
            def critical(*a, **k):
                _QuietBox.messages.append(str(a[2]) if len(a) > 2 else str(a))
            @staticmethod
            def information(*a, **k):
                pass

        real_dialog, real_box = ph.QPrintDialog, ph.QMessageBox
        ph.QPrinter, ph.QPrintDialog, ph.QMessageBox = (
            _fake_qprinter, _FakeDialog, _QuietBox)
        try:
            ok = ph.print_filled_pdf(meta, rec, tm, None)
        finally:
            ph.QPrinter, ph.QPrintDialog, ph.QMessageBox = (
                real_qprinter, real_dialog, real_box)
        for m in _QuietBox.messages:
            add("打印过程提示", m.replace("\n", " / ")[:70])

        if not ok or not os.path.exists(out):
            add("打印管线", "失败：没有产生任何输出")
            return False
        add("打印管线", f"成功，输出 {os.path.getsize(out)} 字节")

        printer = captured.get("printer")

        def bbox_of_dark(pdf_path, region, scan=4.0, thresh=120):
            d = fitz.open(pdf_path)
            pg = d[0]
            clip = fitz.Rect(*region)
            pm = pg.get_pixmap(matrix=fitz.Matrix(scan, scan),
                               colorspace=fitz.csGRAY, clip=clip)
            bx0 = by0 = 10 ** 9
            bx1 = by1 = -1
            for yy in range(pm.height):
                base = yy * pm.stride
                row = pm.samples[base:base + pm.width]
                if min(row) >= thresh:
                    continue
                for xx in range(pm.width):
                    if row[xx] < thresh:
                        if xx < bx0:
                            bx0 = xx
                        if xx > bx1:
                            bx1 = xx
                if yy < by0:
                    by0 = yy
                by1 = yy
            d.close()
            if bx1 < 0:
                return None
            return (clip.x0 + bx0 / scan, clip.y0 + by0 / scan,
                    clip.x0 + (bx1 + 1) / scan, clip.y0 + (by1 + 1) / scan)

        try:
            r = printer.pageRect(QtPrintSupport.QPrinter.Unit.DevicePixel)
        except Exception:
            r = None
        if r is None or r.width() <= 0:
            add("落点判定", "无法读取可打印区，跳过")
            return False
        res = float(printer.resolution())
        k = PT / res
        paint = (r.x() * k, r.y() * k, r.width() * k, r.height() * k)
        dpi = min(int(printer.logicalDpiX() or 300), 300)
        img_w = src_w / PT * dpi
        img_h = src_h / PT * dpi
        s = min(paint[2] / img_w, paint[3] / img_h) * (dpi / PT)
        off_x = paint[0] + (paint[2] - s * src_w) / 2.0
        off_y = paint[1] + (paint[3] - s * src_h) / 2.0
        add("可打印区(pt)", f"({paint[0]:.1f},{paint[1]:.1f})-({paint[2]:.1f},{paint[3]:.1f})")
        add("缩放 / 内容原点", f"{s:.4f} / ({off_x:.2f},{off_y:.2f})pt")

        worst = 0.0
        for i, (mx, my) in enumerate(marks):
            got = bbox_of_dark(out, (mx - 45, my - 45, mx + 75, my + 75))
            if got is None:
                add(f"基准方块 {i + 1}", "未找到（可能被裁掉）")
                worst = 99.0
                continue
            ex, ey = off_x + s * mx, off_y + s * my
            dx, dy = got[0] - ex, got[1] - ey
            worst = max(worst, abs(dx), abs(dy))
            add(f"基准方块 {i + 1} 误差",
                f"({dx:+.2f},{dy:+.2f})pt = ({dx / PT * MM:+.2f},{dy / PT * MM:+.2f})mm")
        whole = bbox_of_dark(out, (0, 0, src_w, src_h))
        if whole is None:
            add("落点判定", "整页空白 —— 打印管线有问题")
            return False
        add("内容包围盒",
            f"({whole[0]:.1f},{whole[1]:.1f})-({whole[2]:.1f},{whole[3]:.1f})pt")
        good = worst < 0.5 * PT / MM
        add("落点判定", "正常（误差 < 0.5mm）" if good
            else f"异常：最大误差 {worst / PT / MM * MM:.2f}mm")
        return good
    except Exception as e:
        import traceback
        add("打印管线自检", f"失败: {type(e).__name__}: {e}")
        lines.append(traceback.format_exc())
        return False
    finally:
        try:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


def collect_report() -> tuple:
    """收集自检报告，返回 (报告文本, 打印落点是否正常)"""
    lines = []

    def add(k, v):
        lines.append(f"{k:<28}{v}")

    add("== 狸猫猫表单 运行自检 ==", "")
    add("时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    try:
        from app.version import VERSION_TEXT
        add("程序版本", VERSION_TEXT)
    except Exception:
        pass
    add("Python", sys.version.replace("\n", " "))
    add("可执行文件", sys.executable)
    add("是否打包运行", str(getattr(sys, "frozen", False)))
    try:
        add("Qt 版本", QtCore.qVersion())
        add("Qt 绑定", "PySide6 (Qt6)" if QT6 else "PySide2 (Qt5)")
    except Exception as e:
        add("Qt 版本", f"读取失败: {e}")
    try:
        import fitz
        add("PyMuPDF", (getattr(fitz, "__doc__", "") or "").split("\n")[0] or "已导入")
    except Exception as e:
        add("PyMuPDF", f"导入失败: {e}")

    add("", "")
    add("-- 屏幕 --", "")
    try:
        app_tmp = QtWidgets.QApplication.instance()
        scr = app_tmp.primaryScreen() if app_tmp else None
        if scr:
            add("分辨率", f"{scr.size().width()}x{scr.size().height()}")
            add("可用区域",
                f"{scr.availableGeometry().width()}x{scr.availableGeometry().height()}")
            add("逻辑 DPI", f"{scr.logicalDotsPerInch():.1f}")
            add("设备像素比", f"{scr.devicePixelRatio():.2f}")
    except Exception as e:
        add("屏幕", f"读取失败: {e}")

    add("", "")
    add("-- 字体 --", "")
    for f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simsun.ttc",
              "C:/Windows/Fonts/simhei.ttf"):
        add(os.path.basename(f), "存在" if os.path.exists(f) else "缺失")
    try:
        if QT6:
            fams = QtGui.QFontDatabase.families()
        else:
            fams = QtGui.QFontDatabase().families()
        add("微软雅黑可用", "是" if any("YaHei" in x for x in fams) else "否")
        add("彩色 emoji 字体",
            "有（Win8+）" if any("Emoji" in x for x in fams) else "无（Win7 正常，界面不使用 emoji）")
    except Exception as e:
        add("字体枚举", f"失败: {e}")

    add("", "")
    add("-- 打印机 --", "")
    try:
        printers = [p.printerName()
                    for p in QtPrintSupport.QPrinterInfo.availablePrinters()]
        add("已安装打印机数", str(len(printers)))
        for i, name in enumerate(printers):
            add(f"  [{i}]", name)
        d = QtPrintSupport.QPrinterInfo.defaultPrinter()
        add("默认打印机", d.printerName() if d and not d.isNull() else "(无)")
    except Exception as e:
        add("打印机枚举", f"失败: {e}")

    add("", "")
    add("-- 打印机 / 可打印区实测 --", "")
    try:
        from app.qt import printer_high_resolution, printer_device_pixel
        pr = QtPrintSupport.QPrinter(printer_high_resolution())
        add("isValid()", str(pr.isValid()))
        add("printerName()", repr(pr.printerName()))
        add("resolution()", str(pr.resolution()))
        add("logicalDpiX()", str(pr.logicalDpiX()))
        add("device width/height", f"{pr.width()} x {pr.height()}")
        try:
            r = pr.pageRect(printer_device_pixel())
        except (TypeError, AttributeError):
            r = pr.pageRect()
        add("pageRect(DevicePixel)", f"({r.x():.0f},{r.y():.0f}) {r.width():.0f}x{r.height():.0f}")
        add("pageRect 原点非零",
            "是（内容须按画笔逻辑页面居中，不能叠加该偏移）"
            if (r.x() or r.y()) else "否")
        add("outputFormat()", str(pr.outputFormat()))
    except Exception as e:
        add("打印自检", f"失败: {type(e).__name__}: {e}")

    add("", "")
    add("-- 打印落点自检（不需要真打印机）--", "")
    print_ok = _print_roundtrip(lines, add)

    lines.append("")
    lines.append("提示：把本文件整个发给开发者即可定位问题。")
    return "\n".join(lines), print_ok


def save_report() -> tuple:
    """写报告到桌面（拿不到桌面就写用户目录），返回 (路径, 打印落点是否正常)"""
    text, print_ok = collect_report()
    candidates = []
    try:
        candidates.append(os.path.join(os.path.expanduser("~"), "Desktop"))
    except Exception:
        pass
    candidates.append(os.path.expanduser("~"))
    out_dir = next((d for d in candidates if os.path.isdir(d)), ".")
    out_path = os.path.join(out_dir, "狸猫猫表单-自检报告.txt")
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        out_path = os.path.join(tempfile.gettempdir(), "狸猫猫表单-自检报告.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
    return out_path, print_ok


def show_report_dialog(parent=None) -> str:
    """界面入口：跑自检 + 弹窗告知结果与报告位置"""
    try:
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
    except Exception:
        pass
    try:
        path, print_ok = save_report()
    finally:
        try:
            QtWidgets.QApplication.restoreOverrideCursor()
        except Exception:
            pass
    box = QtWidgets.QMessageBox(parent)
    box.setIcon(QtWidgets.QMessageBox.Icon.Information if print_ok
                else QtWidgets.QMessageBox.Icon.Warning)
    box.setWindowTitle("自检完成")
    box.setText("打印落点自检：" + ("正常，可以放心打印。" if print_ok
                                else "异常！请把报告发给开发者。"))
    box.setInformativeText(f"完整报告已保存到：\n{path}")
    box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
    box.exec_() if not hasattr(box, "exec") else box.exec()
    return path
