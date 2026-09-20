# -*- coding: utf-8 -*-
"""打印精度回归 — 用真实打印管线验证"内容落在纸上的位置"是否正确

背景（2026-09 修复的缺陷）：
    print_helper 把 QPrinter.pageRect().x()/y() 当作偏移量叠加到画笔上，
    但 QPainter 在 QPrinter 上的原点**本来就已经是可打印区左上角**，
    于是整页内容向右下平移一个页边距（A4 实测 3.5mm），右下角还被裁掉。
    老回归用例只检查"页面上有没有暗像素"，位移 10pt 也照样通过，所以漏了。

本用例的做法：
    1. 造 A4 测试页，在 (100,100) 与 (555,802) 各画一个黑色基准方块；
    2. 用真实 burn_text 把文字烧进字段，再用真实 print_filled_pdf 打印；
    3. 从被'打桩'的打印对话框里取出真实 QPrinter 对象，按修复后的契约
       算出两个基准方块**应该**落在哪里；
    4. 在打印产物上用像素扫描量出实际落点，断言误差 < 1.2pt（≈0.42mm）。

用法：  python tests/print_accuracy.py    （退出码非 0 = 失败）
"""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from app.qt import QtWidgets, QtGui, QtCore, QtPrintSupport
from app.qt import printer_high_resolution, printer_device_pixel

app = QtWidgets.QApplication(sys.argv)

# 没有安装任何打印机时（某些 CI 容器）本用例无法进行，明确跳过而不是假装通过
_available = [p.printerName() for p in QtPrintSupport.QPrinterInfo.availablePrinters()]
if not _available:
    print("SKIP: 本机没有安装任何打印机，打印精度用例无法运行")
    print("PRINT ACCURACY TESTS SKIPPED")
    sys.exit(0)
print(f"可用打印机: {_available}")

PT = 72.0
MM = 25.4
TOL_PT = 1.2          # 允许误差 ≈0.42mm（栅格化抓边界的量化误差）
TOL_EDGE_PT = 2.0     # 裁边检查容差

SRC_W, SRC_H = 595.0, 842.0
MARKS = [("TL", fitz.Rect(100, 100, 130, 130)),      # 内容左上角
         ("BR", fitz.Rect(555, 802, 585, 832))]      # 内容右下角（紧贴可缩边界）
CONTENT = (100.0, 100.0, 585.0, 832.0)               # 源内容包围盒（pt）

tmpdir = tempfile.mkdtemp(prefix="ffprint_")
src = os.path.join(tmpdir, "form.pdf")

FAILS = []


def check(name, ok, detail):
    print(f"  {'[PASS]' if ok else '[FAIL]'} {name} — {detail}")
    if not ok:
        FAILS.append(f"{name}: {detail}")


# ── 造测试表单 ─────────────────────────────────────────
doc = fitz.open()
page = doc.new_page(width=SRC_W, height=SRC_H)
for _, r in MARKS:
    page.draw_rect(r, color=None, fill=(0, 0, 0), width=0)
page.insert_text((100, 200), "PAINT REFERENCE", fontsize=14)
doc.save(src)
doc.close()

from app.core.field_model import FieldDefinition, FillRecord
from app.core.template_manager import TemplateManager
from app.core.pdf_engine import burn_text

tm = TemplateManager(tmpdir)
meta = tm.create("打印精度测试", src)
f = FieldDefinition(name="姓名", field_type="text", page=0,
                    rect=(100, 220, 300, 250), font_size=12, tab_order=0)
meta.fields.append(f)
tm.update(meta)
rec = FillRecord(template_id=meta.id, name="r1")
rec.values[f.id] = "打印精度ABC"


# ── 像素测量 ───────────────────────────────────────────
def bbox_of_dark(pdf_path, scale=4.0, thresh=120, region=None):
    d = fitz.open(pdf_path)
    pg = d[0]
    clip = fitz.Rect(*region) if region else None
    pm = pg.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csGRAY, clip=clip)
    ox = clip.x0 if clip else 0.0
    oy = clip.y0 if clip else 0.0
    x0 = y0 = 10 ** 9
    x1 = y1 = -1
    for y in range(pm.height):
        base = y * pm.stride
        row = pm.samples[base:base + pm.width]
        if min(row) >= thresh:
            continue
        for x in range(pm.width):
            if row[x] < thresh:
                if x < x0:
                    x0 = x
                if x > x1:
                    x1 = x
        if y < y0:
            y0 = y
        y1 = y
    d.close()
    if x1 < 0:
        return None
    return (ox + x0 / scale, oy + y0 / scale, ox + (x1 + 1) / scale, oy + (y1 + 1) / scale)


def expected_mapping(printer, dpi_limit, img_w, img_h):
    """按修复后的契约算出：源 PDF 的 pt 坐标 → 打印页上的 pt 坐标"""
    res = float(printer.resolution())
    scale_dev = PT / res                                   # 设备像素 → pt
    try:
        pr = printer.pageRect(printer_device_pixel())
    except (TypeError, AttributeError):
        pr = printer.pageRect()
    # 可打印区在"纸张 pt 坐标系"里的位置与大小
    paint_x = pr.x() * scale_dev
    paint_y = pr.y() * scale_dev
    paint_w = pr.width() * scale_dev
    paint_h = pr.height() * scale_dev
    # 画笔逻辑页面 == 可打印区（原点 0,0）；位图等比缩放居中
    s = min(paint_w / img_w, paint_h / img_h) * (dpi_limit / PT)
    off_x = paint_x + (paint_w - s * SRC_W) / 2.0
    off_y = paint_y + (paint_h - s * SRC_H) / 2.0
    return s, off_x, off_y, (paint_x, paint_y, paint_x + paint_w, paint_y + paint_h)


# ── 走真实打印管线 ─────────────────────────────────────
import app.ui.print_helper as ph

real_qprinter = ph.QPrinter
captured = {}


def make_fake(out_path, native):
    def _fake(*a, **k):
        p = real_qprinter(*a, **k)
        if native:
            p.setPrinterName(QtPrintSupport.QPrinterInfo.defaultPrinter().printerName())
        else:
            p.setOutputFormat(QtPrintSupport.QPrinter.PdfFormat)
        p.setOutputFileName(out_path)
        captured["printer"] = p
        captured["mode"] = "native" if native else "pdf-engine"
        return p
    return _fake


class _FakeDialog:
    def __init__(self, printer, parent=None):
        self.printer = printer
    def exec_(self):
        return 1
    def exec(self):
        return 1


ph.QPrintDialog = _FakeDialog

print(f"临时目录: {tmpdir}")
for label, native in (("native", True), ("pdf-engine", False)):
    print(f"\n===== 打印管线: {label} =====")
    out = os.path.join(tmpdir, f"print_{label}.pdf")
    if os.path.exists(out):
        os.unlink(out)
    captured.clear()
    ph.QPrinter = make_fake(out, native)
    try:
        ok = ph.print_filled_pdf(meta, rec, tm, None)
    except Exception as e:
        import traceback
        traceback.print_exc()
        check(f"{label} 打印不抛异常", False, f"{type(e).__name__}: {e}")
        continue
    finally:
        ph.QPrinter = real_qprinter

    check(f"{label} 打印返回成功", ok is True, f"返回值={ok}")
    if not os.path.exists(out) or os.path.getsize(out) < 500:
        check(f"{label} 产生了打印产物", False, "文件缺失或过小")
        continue
    check(f"{label} 产生了打印产物", True, f"{os.path.getsize(out)} 字节")

    printer = captured.get("printer")
    dpi_limit = min(int(printer.logicalDpiX() or 300), 300)
    img_w = SRC_W / PT * dpi_limit
    img_h = SRC_H / PT * dpi_limit
    s, off_x, off_y, paint = expected_mapping(printer, dpi_limit, img_w, img_h)
    print(f"  [info] 打印机={printer.printerName()!r} 分辨率={printer.resolution()}dpi "
          f"可打印区(pt)=({paint[0]:.1f},{paint[1]:.1f})-({paint[2]:.1f},{paint[3]:.1f}) "
          f"缩放={s:.5f} 原点=({off_x:.2f},{off_y:.2f})")

    # 两个基准方块的实际落点
    got = {}
    for name, exp in MARKS:
        region = (exp.x0 - 45, exp.y0 - 45, exp.x1 + 45, exp.y1 + 45)
        bb = bbox_of_dark(out, region=region)
        # 区域里只应有这个方块 → 取其包围盒
        got[name] = bb
        if bb is None:
            check(f"{label} {name} 基准方块存在", False, f"区域 {region} 内没有任何内容（被裁掉？）")
            continue
        exp_x = off_x + s * exp.x0
        exp_y = off_y + s * exp.y0
        dx, dy = bb[0] - exp_x, bb[1] - exp_y
        check(f"{label} {name} 落点正确", abs(dx) <= TOL_PT and abs(dy) <= TOL_PT,
              f"期望({exp_x:.1f},{exp_y:.1f}) 实测({bb[0]:.1f},{bb[1]:.1f}) "
              f"偏差({dx:+.2f},{dy:+.2f})pt = ({dx / PT * MM:+.2f},{dy / PT * MM:+.2f})mm")

    # 整体：内容必须在可打印区内，且没有被裁边
    whole = bbox_of_dark(out)
    if whole is None:
        check(f"{label} 页面上有内容", False, "整页全白 —— 打印结果是空白页")
        continue
    check(f"{label} 页面上有内容", True, f"包围盒=({whole[0]:.1f},{whole[1]:.1f})-({whole[2]:.1f},{whole[3]:.1f})pt")
    exp_x0 = off_x + s * CONTENT[0]
    exp_y0 = off_y + s * CONTENT[1]
    exp_x1 = off_x + s * CONTENT[2]
    exp_y1 = off_y + s * CONTENT[3]
    check(f"{label} 未向右下平移（原缺陷）",
          abs(whole[0] - exp_x0) <= TOL_PT and abs(whole[1] - exp_y0) <= TOL_PT,
          f"左上 期望({exp_x0:.1f},{exp_y0:.1f}) 实测({whole[0]:.1f},{whole[1]:.1f})")
    check(f"{label} 右下角未被裁掉",
          whole[2] >= exp_x1 - TOL_EDGE_PT and whole[3] >= exp_y1 - TOL_EDGE_PT
          and whole[2] <= paint[2] + TOL_EDGE_PT and whole[3] <= paint[3] + TOL_EDGE_PT,
          f"期望右下({exp_x1:.1f},{exp_y1:.1f}) 实测({whole[2]:.1f},{whole[3]:.1f}) "
          f"可打印区右下({paint[2]:.1f},{paint[3]:.1f})")

print(f"\n═══ 打印精度回归：{len(FAILS)} 项失败 ═══")
for x in FAILS:
    print("  ✗", x)
print("ALL PRINT ACCURACY TESTS PASSED" if not FAILS else "PRINT ACCURACY TESTS FAILED")
sys.exit(1 if FAILS else 0)
