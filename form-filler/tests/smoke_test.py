# -*- coding: utf-8 -*-
"""离屏冒烟测试：全流程 + 界面截图"""
import sys, os, json, shutil, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import fitz
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

app = QApplication(sys.argv)
from app.ui.theme import APP_STYLESHEET
from PySide6.QtGui import QFont, QFontDatabase
if not any("YaHei" in f for f in QFontDatabase.families()):
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
print("YaHei available:", any("YaHei" in f for f in QFontDatabase.families()))
app.setFont(QFont("Microsoft YaHei", 10))
app.setStyle("Fusion")
app.setStyleSheet(APP_STYLESHEET)

# 临时数据目录 + 标记引导已完成（避免弹窗阻塞测试）
data_dir = tempfile.mkdtemp(prefix="fftest_")
os.makedirs(data_dir, exist_ok=True)
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

# 打印机接口探针（不弹对话框）
from PySide6.QtPrintSupport import QPrinter
_pr = QPrinter(QPrinter.PrinterMode.HighResolution)
_pr_page = _pr.pageRect(QPrinter.Unit.DevicePixel)
print("printer pageRect OK:", _pr_page.width(), _pr_page.height())

from app.ui.main_window import MainWindow
w = MainWindow(data_dir)
w.resize(1280, 800)
w.show()
app.processEvents()

def shot(name):
    pm = w.grab()
    pm.save(os.path.join(data_dir, name + ".png"), "PNG")
    print("shot:", name, pm.width(), "x", pm.height())

# 新手引导截图（仅展示，不执行 exec）
from app.ui.onboarding import OnboardingDialog
ob = OnboardingDialog(w)
ob.show()
app.processEvents()
ob.grab().save(os.path.join(data_dir, "00_onboarding.png"), "PNG")
ob.close()
print("shot: 00_onboarding")

shot("01_home_empty")

# 建模板
t = w.template_manager.create("报销单样例", pdf_path)
print("template:", t.id, t.page_count, "pages")
w._enter_design_mode(t)
app.processEvents()
assert not w.field_design_panel._props_group.isEnabled(), "props should be disabled when nothing selected"
shot("02_design_blank")

# 画两个字段（一个文本、一个勾选）
from app.core.field_model import FieldDefinition
f1 = FieldDefinition(name="姓名", field_type="text", page=0, rect=(80, 140, 250, 165), tab_order=0, required=True)
f2 = FieldDefinition(name="已确认", field_type="checkbox", page=0, rect=(320, 140, 340, 160), tab_order=1)
f3 = FieldDefinition(name="备注", field_type="text", page=1, rect=(80, 200, 300, 240), tab_order=2, multiline=True)
for f in (f1, f2, f3):
    w.design_mode.canvas.add_field(f)
    w.design_mode.canvas.field_created.emit(f)
w.field_design_panel.load_fields(t)
w.field_design_panel.select_field(f1.id)
assert w.field_design_panel._props_group.isEnabled(), "props should be enabled after selection"
app.processEvents()
shot("03_design_fields")

# 撤销/重做
w.design_mode.canvas.undo()
assert len(w.design_mode.canvas._fields) == 2, "undo failed"
w.design_mode.canvas.redo()
assert len(w.design_mode.canvas._fields) == 3, "redo failed"
print("undo/redo OK")

# 页面旋转设置 + 坐标换算往返
w.design_mode.canvas.set_page_rotation(0, 3.0)
rot_f = w.design_mode.canvas._field_to_display(f1)
back_f = w.design_mode.canvas._field_to_pdf(rot_f)
assert abs(back_f.rect[0] - f1.rect[0]) < 0.01 and abs(back_f.rotation - f1.rotation) < 0.01, "rotation roundtrip failed"
print("rotation roundtrip OK")
w.design_mode.canvas.set_page_rotation(0, 0.0)

# 去填写
w._on_design_to_fill()
app.processEvents()
shot("04_fill_mode")

# 填写值
w._on_field_value_changed(f1.id, "张三")
w._on_field_value_changed(f2.id, "true")
w._on_field_value_changed(f3.id, "下午开会\n需要发票")
w._on_save_record()
print("record saved, values:", w._current_record.values)

# 跨页 Tab 跳转
w.fill_mode.canvas.select_field(f1.id)
w.fill_mode.focus_next_field()
assert w.fill_mode.canvas._selected_field_item.field.id == f2.id, "tab next failed"
w.fill_mode.focus_next_field()
assert w.fill_mode.canvas.current_page == 1, "cross-page tab failed"
print("cross-page tab OK")

# 导出并校验烧录内容
out_pdf = os.path.join(data_dir, "filled.pdf")
from app.core.pdf_engine import burn_text
burn_text(pdf_path, t.fields, w._current_record.values, t.page_settings, out_pdf)
chk = fitz.open(out_pdf)
text_all = "".join(p.get_text() for p in chk)
chk.close()
assert "张三" in text_all and "√" in text_all, "burn missing text: " + repr(text_all[:200])
print("burn OK, text length:", len(text_all))

# 预览弹窗截图
from app.ui.preview_dialog import PreviewDialog
pv = PreviewDialog(w._current_template, w._current_record, w.template_manager, w)
pv.show()
app.processEvents()
pv.grab().save(os.path.join(data_dir, "06_preview.png"), "PNG")
print("shot: 06_preview", pv.width(), "x", pv.height())
pv.close()
app.processEvents()

# 多记录（直接走数据层 API，避免弹窗阻塞）

r2 = w.record_manager.create(t.id, "李四的报销单")
w.record_manager.save(r2)
records = w.record_manager.list_for_template(t.id)
assert len(records) == 2, "record list failed"
w.record_manager.rename(t.id, r2.id, "李四-差旅")
assert w.record_manager.get(t.id, r2.id).name == "李四-差旅"
print("records OK:", [r.name for r in records])

# 必填校验：走界面路径清空姓名
w._on_field_value_changed(f1.id, "")
missing = w._missing_required()
assert missing and missing[0].id == f1.id, "required check failed"
print("required check OK:", [m.name for m in missing])

# 返回首页
w._show_home()
app.processEvents()
shot("05_home_with_card")

print("ALL SMOKE TESTS PASSED")
print("DATADIR:", data_dir)