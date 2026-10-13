# -*- coding: utf-8 -*-
"""独立审计验证脚本 — 覆盖团队冒烟测试未覆盖的风险点

A1. Qt QGraphicsItem.setRotation(+θ) 的视觉方向（画布侧基准）
A2. QLineF.angleTo 的符号（旋转手柄 UX 方向）
B1. fitz insert_text morph Matrix(+θ) 的视觉方向（烧录侧）
B2. fitz insert_textbox rotate=90 的视觉方向（快速路径）
C1. burn_text 任意角度字段：导出方向 vs 画布方向是否一致
C2. 页面矫正角组合：导出文字是否平行于表格线
D1. 快速翻页竞态：后台渲染未完成时 show_page 是否 KeyError
D2. 画布持有 PdfSource 句柄 → 返回首页后删除模板是否失败（Windows 文件锁）
D3. 画布旋转字段后再改属性 → rotation 是否被面板旧值覆盖
D4. 共享 fitz.Document 跨线程渲染压力（线程安全）
"""
import os
import sys
import math
import copy
import json
import shutil
import tempfile

# 输出编码兜底：本文件会打印 ✓/✗/═ 等字符，而 Windows 下 stdout 一旦被重定向
# 到文件或管道就退回 GBK(cp936)，print 会抛 UnicodeEncodeError 并让脚本**中途退出**
# —— A2 之后的用例根本不会执行，表现成"退出码 1 却看不出哪里错"。
# CI 用 PYTHONIOENCODING=utf-8 掩盖了它，本地直接重定向就中招。这里主动切成 UTF-8。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fitz

PASS = []
FAIL = []


def report(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(f"{'[PASS]' if ok else '[FAIL]'} {name}" + (f" — {detail}" if detail else ""))


# ══ A1. Qt setRotation 方向 ═══════════════════════════════
from app.qt import QtWidgets, QtCore

QApplication = QtWidgets.QApplication
QGraphicsScene = QtWidgets.QGraphicsScene
QGraphicsRectItem = QtWidgets.QGraphicsRectItem
QPointF = QtCore.QPointF
QLineF = QtCore.QLineF

app = QApplication(sys.argv)

item = QGraphicsRectItem(0, 0, 100, 40)
item.setRotation(30)  # 未设 origin，默认 (0,0)
p = item.mapToScene(QPointF(100, 0))  # 右上角
qt_cw = p.y() > 0  # 右上角落到 x 轴下方 = 视觉顺时针
report("A1 Qt setRotation(+30) 方向", True,
       f"右上角 mapToScene=({p.x():.1f},{p.y():.1f}) → {'视觉顺时针(CW)' if qt_cw else '视觉逆时针(CCW)'}")

# ══ A2. QLineF.angleTo 符号（旋转手柄）═════════════════════
center = QPointF(0, 0)
start = QPointF(0, -50)      # 手柄在正上方
dragged = QPointF(35.36, -35.36)  # 向右拖 45°（用户预期=顺时针）
line1 = QLineF(center, start)
line2 = QLineF(center, dragged)
delta = line2.angleTo(line1)  # 与 field_item.py 相同的调用方向
# field_item: new_rot = original + angle_delta
# Qt rotation + = 顺时针（A1 已证），所以顺时针拖拽应得到正 delta
report("A2 旋转手柄拖拽方向", 0 < delta <= 180,
       f"顺时针拖 45° → angle_delta={delta:.1f}° → new_rot={delta:.1f}（{'顺时针✓' if 0 < delta <= 180 else '逆时针✗ UX反向'}）")

# ══ B1. fitz morph Matrix(+θ) 方向 ════════════════════════
doc = fitz.open()
page = doc.new_page(width=400, height=400)
pivot = fitz.Point(200, 200)
page.insert_text(pivot, "FFFFFF", fontsize=24, morph=(pivot, fitz.Matrix(30)))
line = next(l for b in page.get_text("dict")["blocks"] for l in b.get("lines", []))
d = line["dir"]
morph_cw = d[1] > 0  # y-down 页面坐标：dir y>0 = 向右下 = 视觉顺时针
report("B1 fitz morph Matrix(+30) 方向", True,
       f"dir=({d[0]:.3f},{d[1]:.3f}) → {'视觉顺时针(CW)' if morph_cw else '视觉逆时针(CCW)'}")
doc.close()

# ══ B2. insert_textbox rotate=90 方向 ═════════════════════
doc = fitz.open()
page = doc.new_page(width=400, height=400)
page.insert_textbox(fitz.Rect(100, 100, 300, 200), "FFFFFF", fontsize=24, rotate=90)
line = next(l for b in page.get_text("dict")["blocks"] for l in b.get("lines", []))
d = line["dir"]
# 画布 rotation=+90（Qt CW）→ 文字应从上往下读 → dir=(0,1)
textbox_cw = d[1] > 0
report("B2 insert_textbox rotate=90 方向", True,
       f"dir=({d[0]:.3f},{d[1]:.3f}) → {'视觉顺时针(CW)' if textbox_cw else '视觉逆时针(CCW)'}")
doc.close()

# ══ C1/C2. 走真实 burn_text ═══════════════════════════════
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.core.pdf_engine import burn_text, rotate_point_ccw  # noqa: E402
from app.core.field_model import FieldDefinition  # noqa: E402

tmp = tempfile.mkdtemp(prefix="audit_")
src = os.path.join(tmp, "src.pdf")
doc = fitz.open()
page = doc.new_page(width=595, height=842)
page.draw_line((50, 100), (545, 100))
doc.save(src)
doc.close()

# C1: 画布上把字段旋转 +30（用户在画布上看到的是视觉顺时针 30°）
f30 = FieldDefinition(name="rot30", page=0, rect=(200, 300, 380, 360),
                      rotation=30.0, font_size=20, tab_order=0)
out1 = os.path.join(tmp, "rot30.pdf")
burn_text(src, [f30], {f30.id: "旋转测试ABC"}, None, out1)
doc = fitz.open(out1)
line = next(l for b in doc[0].get_text("dict")["blocks"] for l in b.get("lines", []))
d = line["dir"]
burn_cw = d[1] > 0
doc.close()
consistent = (burn_cw == qt_cw)
report("C1 字段+30° 画布↔导出方向一致", consistent,
       f"burn dir=({d[0]:.3f},{d[1]:.3f}) → 导出{'CW' if burn_cw else 'CCW'}；画布{'CW' if qt_cw else 'CCW'}"
       + ("" if consistent else " ←【方向镜像，导出与画布相反】"))

# C2: 页面矫正 +3°，画布上水平画的字段 → 存储旋转 -3°
# 期望：导出 PDF 里文字与表格线（视觉 -3°）平行 → dir 应为 (cos3°, -sin3°)
page_settings = type("PS", (), {})()  # 占位
from app.core.field_model import PageSettings  # noqa: E402
ps = [PageSettings(rotation=3.0)]
f3 = FieldDefinition(name="straight", page=0, rect=(150, 400, 460, 436),
                     rotation=-3.0, font_size=20, tab_order=0)
out2 = os.path.join(tmp, "pagerot.pdf")
burn_text(src, [f3], {f3.id: "矫正测试"}, ps, out2)
doc = fitz.open(out2)
line = next(l for b in doc[0].get_text("dict")["blocks"] for l in b.get("lines", []))
d = line["dir"]
expected = (math.cos(math.radians(3)), -math.sin(math.radians(3)))
ok2 = abs(d[0] - expected[0]) < 0.01 and abs(d[1] - expected[1]) < 0.01
report("C2 页面矫正+3° 导出文字平行表格线", ok2,
       f"burn dir=({d[0]:.4f},{d[1]:.4f})；期望≈({expected[0]:.4f},{expected[1]:.4f})"
       + ("" if ok2 else " ←【导出文字与表格线交叉约 6°】"))
doc.close()

# ══ D1. 快速翻页竞态 ══════════════════════════════════════
from app.ui.pdf_canvas import PdfCanvas  # noqa: E402
from app.core.pdf_engine import PdfSource  # noqa: E402

multi = os.path.join(tmp, "multi.pdf")
doc = fitz.open()
for i in range(5):
    pg = doc.new_page(width=595, height=842)
    pg.insert_text((72, 100), f"Page {i+1}", fontsize=20)
doc.save(multi)
doc.close()

canvas = PdfCanvas()
canvas.load_pdf(multi)
canvas._render_timer.stop()  # 冻结结果回收，模拟"后台任务未完成"
canvas._render_jobs[1] = {"done": False, "bytes": None}  # 页1渲染中
try:
    canvas.show_page(1)
    report("D1 翻页竞态（渲染未完成时切页）", True, "未崩溃")
except KeyError as e:
    report("D1 翻页竞态（渲染未完成时切页）", False, f"KeyError: {e} ←【快速翻页崩溃】")
except Exception as e:
    report("D1 翻页竞态（渲染未完成时切页）", False, f"{type(e).__name__}: {e}")

# ══ D2. 画布持有文件句柄 → 删除模板 ═══════════════════════
data_dir = tempfile.mkdtemp(prefix="audit_data_")
with open(os.path.join(data_dir, "settings.json"), "w", encoding="utf-8") as f:
    json.dump({"onboarding_done": True}, f)
from app.core.template_manager import TemplateManager  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402

tm = TemplateManager(data_dir)
meta = tm.create("锁测试", src)
w = MainWindow(data_dir)
w._on_template_selected(meta, "design")   # 进入设计模式 → 画布打开 PdfSource
w._show_home()                            # 返回首页（画布句柄仍持有？）
try:
    tm.delete(meta.id)
    left = os.path.exists(tm.template_dir(meta.id))
    report("D2 删除模板（画布曾打开过该 PDF）", not left,
           "删除成功" if not left else "目录仍存在但未报错")
except PermissionError as e:
    report("D2 删除模板（画布曾打开过该 PDF）", False,
           f"PermissionError: {e} ←【Windows 文件锁，删除失败且无提示】")
except Exception as e:
    report("D2 删除模板（画布曾打开过该 PDF）", False, f"{type(e).__name__}: {e}")
w.close()

# ══ D3. 画布旋转后属性合并丢角度 ══════════════════════════
w2 = MainWindow(tempfile.mkdtemp(prefix="audit_d3_"))
tm2 = w2.template_manager
m2 = tm2.create("旋转合并", src)
w2._on_template_selected(m2, "design")
canvas_d = w2.design_mode.canvas
fid = "d3field"
fd = FieldDefinition(id=fid, name="测试", page=0, rect=(100, 100, 260, 150), tab_order=0)
canvas_d.add_field(fd)
canvas_d.field_created.emit(canvas_d._fields[-1])
app.processEvents()
# 用户在画布上旋转字段到 +30°（模拟 FieldItem 旋转交互落库）
item = canvas_d._field_items[fid]
item.field.rotation = 30.0
canvas_d._sync_from_item(item)
app.processEvents()
rot_after_canvas = next(f for f in w2._current_template.fields if f.id == fid).rotation
# 用户随后在右侧属性面板把名称改为"改名"（不碰角度输入框）
w2.field_design_panel.select_field(fid)
panel_field = w2.field_design_panel._current_field
panel_field.name = "改名后"
w2.field_design_panel._on_prop_changed()
app.processEvents()
rot_after_edit = next(f for f in w2._current_template.fields if f.id == fid).rotation
report("D3 画布旋转+30° 后仅改名称", abs(rot_after_edit - 30) < 0.01,
       f"画布旋转后={rot_after_canvas}°，改名后={rot_after_edit}°"
       + ("" if abs(rot_after_edit - 30) < 0.01 else " ←【旋转角被面板旧值覆盖归零】"))
w2.close()

# ══ D4. 共享 Document 跨线程渲染压力 ═══════════════════════
import threading
import time
canvas4 = PdfCanvas()
# 放大竞态窗口：让每次渲染睡 20ms
orig_render = PdfSource.render_page_bytes
def slow_render(self, page_num, dpi):
    time.sleep(0.02)
    return orig_render(self, page_num, dpi)
PdfSource.render_page_bytes = slow_render
errors = []
canvas4.load_pdf(multi)
canvas4._render_timer.stop()  # 不回收，制造多任务并存
for p in range(1, 5):
    canvas4._request_render(p)  # 每页起一个线程共享同一个 PdfSource
canvas4._render_page_sync(0)     # GUI 线程同时再走同一 Document
time.sleep(1.0)
PdfSource.render_page_bytes = orig_render
done_jobs = sum(1 for j in canvas4._render_jobs.values() if j["done"])
bad = [p for p, j in canvas4._render_jobs.items() if j["done"] and not j["bytes"]]
report("D4 共享 Document 多线程渲染压力", done_jobs == 4 and not bad,
       f"任务完成 {done_jobs}/4，异常空结果 {len(bad)} 个"
       + ("" if done_jobs == 4 and not bad else " ←【存在渲染失败，线程不安全可复现】"))

print()
print(f"═══ 结果：{len(PASS)} 通过 / {len(FAIL)} 失败 ═══")
for f in FAIL:
    print(f"  ✗ {f}")
print("TMP:", tmp)