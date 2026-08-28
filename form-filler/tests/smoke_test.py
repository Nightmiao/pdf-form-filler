# -*- coding: utf-8 -*-
"""离屏自动化冒烟/回归测试 — 覆盖代码审计修复点 + 全流程 + 界面截图"""
import sys, os, json, copy, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import math
import fitz
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest

app = QApplication(sys.argv)
from app.ui.theme import APP_STYLESHEET
if not any("YaHei" in f for f in QFontDatabase.families()):
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
app.setFont(QFont("Microsoft YaHei", 10))
app.setStyle("Fusion")
app.setStyleSheet(APP_STYLESHEET)

# 打印机接口探针
from PySide6.QtPrintSupport import QPrinter
_pr = QPrinter(QPrinter.PrinterMode.HighResolution)
_pr_page = _pr.pageRect(QPrinter.Unit.DevicePixel)
print("printer pageRect OK:", _pr_page.width(), _pr_page.height())

# 临时数据目录（标记引导已完成，避免弹窗阻塞）
data_dir = tempfile.mkdtemp(prefix="fftest_")
with open(os.path.join(data_dir, "settings.json"), "w", encoding="utf-8") as f:
    json.dump({"onboarding_done": True}, f)

# 生成两页测试 PDF
pdf_path = os.path.join(data_dir, "sample.pdf")
doc = fitz.open()
for i in range(2):
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), f"Test Form Page {i+1}", fontsize=16)
    page.draw_rect(fitz.Rect(72, 130, 300, 160), color=(0.5, 0.5, 0.5))
    page.insert_text((80, 146), "Name: ____________", fontsize=11)
doc.save(pdf_path)
doc.close()

from app.ui.main_window import MainWindow
w = MainWindow(data_dir)
w.resize(1280, 800)
w.show()
app.processEvents()

def shot(name):
    pm = w.grab()
    pm.save(os.path.join(data_dir, name + ".png"), "PNG")
    print("shot:", name)

from app.ui.onboarding import OnboardingDialog
ob = OnboardingDialog(w); ob.show(); app.processEvents()
ob.grab().save(os.path.join(data_dir, "00_onboarding.png"), "PNG"); ob.close()

shot("01_home_empty")

t = w.template_manager.create("报销单样例", pdf_path)
w._enter_design_mode(t)
app.processEvents()
assert not w.field_design_panel._props_group.isEnabled(), "props should be disabled when nothing selected"
shot("02_design_blank")

from app.core.field_model import FieldDefinition, TemplateMeta
f1 = FieldDefinition(name="姓名", field_type="text", page=0, rect=(80, 140, 250, 165), tab_order=0, required=True)
f2 = FieldDefinition(name="已确认", field_type="checkbox", page=0, rect=(320, 140, 340, 160), tab_order=1)
f3 = FieldDefinition(name="备注", field_type="text", page=1, rect=(80, 200, 300, 240), tab_order=2, multiline=True)
for f in (f1, f2, f3):
    w.design_mode.canvas.add_field(f)
    w.design_mode.canvas.field_created.emit(f)
w.field_design_panel.load_fields(t)
w.field_design_panel.select_field(f1.id)
assert w.field_design_panel._props_group.isEnabled(), "props should be enabled after selection"
shot("03_design_fields")

# ── 撤销/重做 ──
w.design_mode.canvas.undo()
assert len(w.design_mode.canvas._fields) == 2, "undo failed"
w.design_mode.canvas.redo()
assert len(w.design_mode.canvas._fields) == 3, "redo failed"
print("undo/redo OK")

# ── #7 页面旋转坐标换算：精确往返，无外接框膨胀 ──
w.design_mode.canvas.set_page_rotation(0, 3.0)
d1 = w.design_mode.canvas._field_to_display(f1)
back1 = w.design_mode.canvas._field_to_pdf(d1)
for a, b in zip(back1.rect, f1.rect):
    assert abs(a - b) < 1e-9, f"rotation roundtrip not exact: {back1.rect} vs {f1.rect}"
assert abs(back1.rotation - f1.rotation) < 1e-9
# 在旋转页面上画的轴对齐框 → PDF → 回显，必须精确还原
disp_f = FieldDefinition(name="X", page=0, rect=(100, 100, 300, 130), rotation=0.0)
pdf_f = w.design_mode.canvas._field_to_pdf(disp_f)
disp_back = w.design_mode.canvas._field_to_display(pdf_f)
for a, b in zip(disp_back.rect, disp_f.rect):
    assert abs(a - b) < 1e-9, f"drawn-rect roundtrip not exact: {disp_back.rect} vs {disp_f.rect}"
w.design_mode.canvas.set_page_rotation(0, 0.0)
print("rotation exact roundtrip OK")

# ── 画布拖拽后改属性：几何不回弹（单一 owner + 属性合并）──
moved = copy.deepcopy(f1)
moved.rect = (90, 150, 260, 175)
w._on_field_modified_in_canvas(moved)
w.field_design_panel.select_field(f1.id)
w.field_design_panel._name_edit.setText("姓名-改")
merged = next(f for f in t.fields if f.id == f1.id)
assert merged.rect == moved.rect, "geometry clobbered by property edit"
assert merged.name == "姓名-改", "name not merged"
w.field_design_panel._name_edit.setText("姓名")
print("property-merge keeps geometry OK")

# ── #6 属性编辑不重建列表、选中不丢 ──
row_before = w.field_design_panel._field_list.currentRow()
w.field_design_panel._name_edit.setText("测试改名")
assert w.field_design_panel._field_list.currentRow() == row_before, "selection lost on prop edit"
item = w.field_design_panel._field_list.item(row_before)
assert "测试改名" in item.text(), "row text not updated"
w.field_design_panel._name_edit.setText("姓名")
print("incremental list update OK")

# ── #5 排序同步画布 ──
reordered = [f2, f1, f3]
for i, f in enumerate(reordered):
    f.tab_order = i
w._on_tab_order_changed(reordered)
canvas_order = sorted(w.design_mode.canvas._fields, key=lambda f: (f.page, f.tab_order))
assert [f.id for f in canvas_order] == [f2.id, f1.id, f3.id], "tab order not synced"
print("reorder sync OK")

# ── #12 页面缓存 LRU 上限 ──
for p in range(w.design_mode.canvas.page_count):
    w.design_mode.canvas._render_page_sync(p)
assert len(w.design_mode.canvas._page_pixmaps) <= 6, "pixmap cache not LRU-capped"
print("LRU cache cap OK")

# ── 填写 ──
w._on_design_to_fill()
app.processEvents()
shot("04_fill_mode")
w._on_field_value_changed(f1.id, "张三")
w._on_field_value_changed(f2.id, "true")
w._on_field_value_changed(f3.id, "下午开会\n需要发票")
w._on_save_record()
app.processEvents()
shot("04b_fill_filled")
print("record saved")

# 跨页 Tab（排序后顺序为 f2 → f1 → f3）
w.fill_mode.canvas.select_field(f2.id)
w.fill_mode.focus_next_field()
assert w.fill_mode.canvas._selected_field_item.field.id == f1.id
w.fill_mode.focus_next_field()
assert w.fill_mode.canvas.current_page == 1, "cross-page tab failed"
assert w.fill_mode.canvas._selected_field_item.field.id == f3.id
print("cross-page tab OK")

# ── #1 记录切换/新建/删除前，旧记录修改必须落盘 ──
rec_a_id = w._current_record.id
w._on_field_value_changed(f1.id, "记录A的最终值")
r2 = w.record_manager.create(t.id, "记录 B")
w.record_manager.save(r2)
w._on_record_selected(r2.id)
saved_a = w.record_manager.get(t.id, rec_a_id)
assert saved_a.values.get(f1.id) == "记录A的最终值", "record switch lost unsaved changes"
w._on_field_value_changed(f1.id, "记录B的值")
r3 = w.record_manager.create(t.id, "记录 C")
w.record_manager.save(r3)
w._on_record_selected(r3.id)
assert w.record_manager.get(t.id, r2.id).values.get(f1.id) == "记录B的值", "record switch lost unsaved changes (2)"
print("record switch persistence OK")

# ── 预览弹窗（正常）──
from app.ui.preview_dialog import PreviewDialog
pv = PreviewDialog(w._current_template, w._current_record, w.template_manager, w)
pv.show(); app.processEvents()
pv.grab().save(os.path.join(data_dir, "06_preview.png"), "PNG")
assert not pv._failed
pv.close(); app.processEvents()
print("preview OK")

# ── #2 任意角度旋转导出：morph 精确写入（15°）──
from app.core.pdf_engine import burn_text
rot_field = FieldDefinition(name="旋转", field_type="text", page=0, rect=(350, 300, 460, 330), rotation=15.0, tab_order=99)
fields_for_rot = list(t.fields) + [rot_field]
values_rot = {**w._current_record.values, rot_field.id: "旋转测试"}
out1 = os.path.join(data_dir, "rot.pdf")
burn_text(pdf_path, fields_for_rot, values_rot, t.page_settings, out1)
d1 = fitz.open(out1)
spans = [s for b in d1[0].get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"]]
rot_span = next((s for s in spans if "旋转" in s["text"]), None)
assert rot_span is not None, "rotated text missing"
line = next(l for b in d1[0].get_text("dict")["blocks"] for l in b.get("lines", []) if any("旋转" in s["text"] for s in l["spans"]))
assert abs(line["dir"][0] - math.cos(math.radians(15))) < 0.01, f"15deg dir wrong: {line['dir']}"
assert abs(line["dir"][1] + math.sin(math.radians(15))) < 0.01, f"15deg dir wrong: {line['dir']}"
d1.close()
print("arbitrary rotation export OK (15deg)")

# ── #7/#10 页面矫正角写入导出（-3° 字段）──
page_settings = copy.deepcopy(t.page_settings)
page_settings[0].rotation = 3.0
straight = FieldDefinition(name="矫正", field_type="text", page=0, rect=(350, 400, 460, 430), rotation=-3.0, tab_order=100)
fields2 = list(t.fields) + [straight]
values2 = {**w._current_record.values, straight.id: "矫正测试"}
out2 = os.path.join(data_dir, "page_rot.pdf")
burn_text(pdf_path, fields2, values2, page_settings, out2)
d2 = fitz.open(out2)
line2 = next(l for b in d2[0].get_text("dict")["blocks"] for l in b.get("lines", []) if any("矫正" in s["text"] for s in l["spans"]))
assert abs(line2["dir"][0] - math.cos(math.radians(3))) < 0.01, f"page-rot dir wrong: {line2['dir']}"
assert abs(line2["dir"][1] - math.sin(math.radians(3))) < 0.01, f"page-rot dir wrong: {line2['dir']}"
d2.close()
print("page rotation export OK")

# ── #4 非法字段防御：越界页/坏 rect 自动跳过 ──
bad1 = FieldDefinition(name="坏", page=99, rect=(0, 0, 100, 30))
bad2 = FieldDefinition(name="坏2", page=0, rect=(0, 0, float("nan"), 30))
out3 = os.path.join(data_dir, "bad.pdf")
burn_text(pdf_path, [bad1, bad2], {bad1.id: "x", bad2.id: "y"}, [], out3)
assert os.path.exists(out3), "burn with bad fields should not crash"
meta_json = t.to_dict()
meta_json["fields"].append({"id": "x", "name": "坏", "page": 99, "rect": [0, 0, 100, 30]})
meta_json["fields"].append({"id": "y", "name": "坏", "page": 0, "rect": [0, 0, "a", 30]})
m2 = TemplateMeta.from_dict(meta_json)
assert all(f.id not in ("x", "y") for f in m2.fields), "invalid fields not dropped on load"
print("invalid field guard OK")

# ── #8 导出路径防覆盖 ──
import app.ui.main_window as mwmod
orig_pdf = os.path.normcase(os.path.abspath(w.template_manager.pdf_path(t.id)))
ok_path = os.path.join(data_dir, "ok_export.pdf")
calls = {"n": 0, "warned": 0}
class FakeFD:
    @staticmethod
    def getSaveFileName(*a, **k):
        calls["n"] += 1
        return (orig_pdf if calls["n"] == 1 else ok_path, "")
class FakeMB:
    @staticmethod
    def warning(*a, **k):
        calls["warned"] += 1
        return None
mwmod.QFileDialog = FakeFD
mwmod.QMessageBox = FakeMB
chosen = w._choose_export_path()
assert chosen == ok_path and calls["warned"] == 1, f"export path guard failed: {chosen}"
print("export path guard OK")

# ── #9 预览构造异常保护 ──
pdf_real = w.template_manager.pdf_path(t.id)
with open(pdf_real, "rb") as f:
    real_bytes = f.read()
with open(pdf_real, "wb") as f:
    f.write(b"not a pdf")
try:
    pv_bad = PreviewDialog(w._current_template, w._current_record, w.template_manager, w)
    assert pv_bad._failed, "preview should fail gracefully"
    pv_bad.close()
finally:
    with open(pdf_real, "wb") as f:
        f.write(real_bytes)
print("preview error guard OK")

# ── #11 缩略图异步渲染 ──
from app.ui.thumbnail_bar import ThumbnailBar, _placeholder_pixmap
tb = ThumbnailBar()
tb.load_pages(t, pdf_path)
for _ in range(60):
    QTest.qWait(50)
    if tb._job is None:
        break
assert tb._job is None, "thumbnail job never finished"
ph_color = _placeholder_pixmap().toImage().pixelColor(5, 5)
item_pix = tb._items[0]._img.pixmap()
assert item_pix is not None and not item_pix.isNull()
real_color = item_pix.toImage().pixelColor(5, 5)
assert real_color != ph_color, "thumbnail still showing placeholder"
print("async thumbnails OK")

# ── #14 搜索防抖 ──
w._show_home()
app.processEvents()
w.home_page.search_input.setText("报")
assert w.home_page._search_timer.isActive(), "search not debounced"
QTest.qWait(400)
assert any("报销" in x.name for x in w.home_page._templates), "debounced search refresh failed"
w.home_page.search_input.setText("")
w.home_page.refresh()
shot("05_home_with_card")

print("ALL REGRESSION TESTS PASSED")
print("DATADIR:", data_dir)