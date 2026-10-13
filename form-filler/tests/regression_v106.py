# -*- coding: utf-8 -*-
"""v1.0.6 审计修复回归 —— 每一个用例都对应一个"曾经真实存在、且原有用例没覆盖"的缺陷

设计原则（吸取原有用例的教训）：
- 每个用例都要能在这个缺陷**未修复**时失败。凡是想验证"跳页不崩"的，就**不能**
  自己往 _render_jobs 里塞东西来绕过真实分支（audit_verify 的 D1 就是这么漏掉的）。
- 用例里出现的"巧合"要么消除，要么在注释里写明为什么它不影响结论。

用法：  python tests/regression_v106.py     （退出码非 0 = 失败）
"""
import os
import sys
import json
import time
import math
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 输出编码兜底：重定向到文件/管道时 Windows 会退回 GBK 代码页，
# 打印 ═ / ✗ 等字符会抛 UnicodeEncodeError 让脚本中途退出（看起来像用例失败）。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import fitz
from app.qt import QtWidgets, QtCore, QtGui, Qt, QT6

QApplication = QtWidgets.QApplication
app = QApplication(sys.argv)

# 离屏平台拿不到系统字体，必须显式注册，否则截图/文本测量全是空
if QT6:
    if not any("YaHei" in f for f in QtGui.QFontDatabase.families()):
        QtGui.QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
else:
    _qfd = QtGui.QFontDatabase()
    if not any("YaHei" in f for f in _qfd.families()):
        _qfd.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
app.setFont(QtGui.QFont("Microsoft YaHei", 10))
app.setStyle("Fusion")

from app.ui.theme import APP_STYLESHEET
app.setStyleSheet(APP_STYLESHEET)

PASS = []
FAIL = []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(f"  {'[PASS]' if ok else '[FAIL]'} {name}" + (f" — {detail}" if detail else ""))


def pump(ms=250):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def new_data_dir():
    d = tempfile.mkdtemp(prefix="regr106_")
    with open(os.path.join(d, "settings.json"), "w", encoding="utf-8") as f:
        json.dump({"onboarding_done": True}, f)
    return d


# 模态对话框桩：离屏测试里不替换就会永久阻塞（挂死到超时，非常难排查）。
# 注意 main_window / home_page 在 import 时已把 QMessageBox 绑成模块级名字，
# 所以下面替换的是**模块属性**，而不是 QtWidgets.QMessageBox。
_RealMB = QtWidgets.QMessageBox
_YES = _RealMB.StandardButton.Yes


class _AutoYesBox(_RealMB):
    @staticmethod
    def question(*a, **k):
        return _YES

    @staticmethod
    def warning(*a, **k):
        return _YES

    @staticmethod
    def information(*a, **k):
        return _YES

    @staticmethod
    def critical(*a, **k):
        return _YES


def make_pdf(path, pages=5):
    doc = fitz.open()
    for i in range(pages):
        pg = doc.new_page(width=595, height=842)
        pg.insert_text((72, 100), f"Form Page {i + 1}", fontsize=16)
    doc.save(path)
    doc.close()
    return path


from app.ui.main_window import MainWindow
from app.core.field_model import FieldDefinition, FillRecord
from app.core.export_import import export_template
import app.ui.home_page as hp
import app.ui.main_window as mw

print("=" * 68)
print("D1  跳到非相邻页不再崩溃、画布不再永久空白")
print("=" * 68)
data = new_data_dir()
pdf = make_pdf(os.path.join(data, "5p.pdf"), 5)
w = MainWindow(data)
w.resize(1280, 800)
w.show()
t = w.template_manager.create("五页表单", pdf)
w._enter_design_mode(t)
cv = w.design_mode.canvas
pump(1200)   # 等相邻页预取完成、_render_jobs 排空（这正是触发条件）

check("D1 前提：目标页既不在缓存、也不在渲染队列",
      4 not in cv._page_pixmaps and 4 not in cv._render_jobs,
      f"cache={sorted(cv._page_pixmaps)} jobs={sorted(cv._render_jobs)}")
try:
    w._on_thumbnail_page_clicked(4)      # 与用户点缩略图完全同一条路径
    ok = True
    err = ""
except Exception as e:
    ok = False
    err = f"{type(e).__name__}: {e}"
check("D1 点第 5 页缩略图不抛异常", ok, err)
pump(300)
has_pix = cv._pixmap_item is not None
check("D1 画布确实切换到了第 5 页", cv.current_page == 4, f"current_page={cv.current_page}")
check("D1 画布上有页面位图（非空白）", has_pix and len(cv._scene.items()) > 0,
      f"图元数={len(cv._scene.items())}")


print("=" * 68)
print("D7  渲染失败不再伪造 100x140 页面、不再污染坐标基准")
print("=" * 68)
real_render = cv._source.render_page_bytes


def boom(page_num, dpi):
    raise RuntimeError("simulated render failure")


cv._source.render_page_bytes = boom
try:
    cv._failed_pages.discard(2)
    cv._page_pixmaps.pop(2, None)
    cv._render_page_sync(2)
finally:
    cv._source.render_page_bytes = real_render
sx, sy = cv._page_size_pdf_of(2)
check("D7 渲染失败后页面尺寸仍是真实 A4（595x842）",
      abs(sx - 595) < 1.0 and abs(sy - 842) < 1.0, f"实测 {sx:.1f}x{sy:.1f}")
pm = cv._page_pixmaps.get(2)
check("D7 占位图按真实页面尺寸生成（不再 100x140）",
      pm is not None and abs(pm.width() / (150 / 72.0) - 595) < 1.0,
      f"占位图 {pm.width() if pm else 0}x{pm.height() if pm else 0}px")
check("D7 失败的页被标记，下次显示会重试", 2 in cv._failed_pages)


print("=" * 68)
print("D2  页面矫正角只改变位置/角度，不再扭曲字段形状")
print("=" * 68)
cv.set_current_page(0)            # 上一步把画布停在了第 5 页，先回到第 1 页
pump(200)
cv.set_page_rotation(0, 0.0)
f = FieldDefinition(name="几何", page=0, rect=(200.0, 300.0, 300.0, 330.0), tab_order=0)
cv.load_fields([f])
pump(150)
W0, H0 = 100.0, 30.0
worst = 0.0
for theta in (1.0, 3.0, 5.0, 15.0):
    cv.set_page_rotation(0, theta)
    pump(80)
    d = cv._field_to_display(f)
    dw = (d.rect[2] - d.rect[0]) - W0
    dh = (d.rect[3] - d.rect[1]) - H0
    worst = max(worst, abs(dw), abs(dh))
    back = cv._field_to_pdf(d)
    assert all(abs(a - b) < 1e-9 for a, b in zip(back.rect, f.rect)), "往返丢失精度"
check("D2 显示矩形宽高恒定（1°/3°/5°/15°）", worst < 1e-9, f"最大偏差 {worst:.4f}pt")
cv.set_page_rotation(0, 5.0)
pump(80)
pw, ph = cv._field_items[f.id]._pdf_rect_to_pixel()
S = 150 / 72.0
check("D2 画布上图元实际渲染尺寸 = 真实尺寸",
      abs(pw - W0 * S) < 0.01 and abs(ph - H0 * S) < 0.01,
      f"渲染 {pw:.1f}x{ph:.1f}px，应为 {W0 * S:.1f}x{H0 * S:.1f}px（旧实现为 ~{W0 * math.cos(math.radians(5)) - H0 * math.sin(math.radians(5)):.1f}x{(W0 * math.sin(math.radians(5)) + H0 * math.cos(math.radians(5))) * S:.1f}px）")


print("=" * 68)
print("D3  拖动旋转过的字段缩放时方向不再错乱")
print("=" * 68)
cv.set_page_rotation(0, 0.0)
cv.set_snap_enabled(False)        # 关掉网格吸附，否则 5pt 取整会污染测量
f90 = FieldDefinition(name="转了90度", page=0, rect=(200.0, 600.0, 300.0, 630.0),
                      rotation=90.0, tab_order=5)
cv.load_fields([f90])
cv.select_field(f90.id)
pump(150)
item90 = cv._field_items[f90.id]
p0 = item90.mapToScene(QtCore.QPointF(0.0, 0.0))          # 左上角手柄
press = QtWidgets.QGraphicsSceneMouseEvent(QtCore.QEvent.Type.GraphicsSceneMousePress)
press.setButton(Qt.MouseButton.LeftButton)
press.setPos(QtCore.QPointF(0.0, 0.0))
press.setScenePos(p0)
item90.mousePressEvent(press)
move = QtWidgets.QGraphicsSceneMouseEvent(QtCore.QEvent.Type.GraphicsSceneMouseMove)
move.setButtons(Qt.MouseButton.LeftButton)
move.setPos(QtCore.QPointF(60.0, 0.0))
move.setScenePos(p0 + QtCore.QPointF(60.0, 0.0))          # 纯水平拖 60px
item90.mouseMoveEvent(move)
r = item90.field.rect
dw = (r[2] - r[0]) - 100.0
dh = (r[3] - r[1]) - 30.0
# 字段转了 90°，场景水平方向对应图元的"高度"方向：
# 正确实现下宽度不变、高度变大；旧实现（直接用场景差量）会变成宽度变小、高度不变。
check("D3 90°字段水平拖拽只改变高度方向（宽度不变）",
      abs(dw) < 2.0 and dh > 15.0,
      f"宽变化 {dw:+.1f}pt，高变化 {dh:+.1f}pt（旧实现约为 宽 -28.8 / 高 0）")
item90.mouseReleaseEvent(
    QtWidgets.QGraphicsSceneMouseEvent(QtCore.QEvent.Type.GraphicsSceneMouseRelease))
cv.set_snap_enabled(True)


print("=" * 68)
print("D5  失焦后不再卡在'按住空格平移'状态")
print("=" * 68)
cv.set_page_rotation(0, 0.0)
cv._space_held = True
cv._panning = True
cv._rmb_pressed = True
cv.focusOutEvent(QtGui.QFocusEvent(QtCore.QEvent.Type.FocusOut))
check("D5 失焦清空 _space_held", cv._space_held is False)
check("D5 失焦清空 _panning / _rmb_pressed",
      cv._panning is False and cv._rmb_pressed is False)


print("=" * 68)
print("D4  方向键连按不再冲垮撤销栈")
print("=" * 68)
cv.load_fields([f])
cv.select_field(f.id)
pump(80)
before = len(cv._undo_stack)
for _ in range(30):                 # 模拟约 1 秒的自动重复
    cv.nudge_selected_field(1.0, 0.0)
during = len(cv._undo_stack)
check("D4 连按 30 次只产生 1 条撤销记录", during - before <= 1,
      f"撤销栈增长 {during - before} 条（旧实现为 30 条）")
cv._end_nudge()
after = len(cv._undo_stack)
check("D4 松手后恰好补 1 条撤销记录", after - before == 1, f"增长 {after - before} 条")
moved = next(x for x in cv._fields if x.id == f.id)
check("D4 30 次微移累积生效（位移 30pt）", abs(moved.rect[0] - (f.rect[0] + 30.0)) < 1e-6,
      f"x0={moved.rect[0]:.2f}")


print("=" * 68)
print("D10 小手柄判定盒不再吃掉整个字段（否则小字段拖不动）")
print("=" * 68)
small = FieldDefinition(name="小框", page=0, rect=(100.0, 400.0, 118.0, 415.0), tab_order=1)
cv.load_fields([small])
cv.select_field(small.id)
pump(80)
item = cv._field_items[small.id]
w_px, h_px = item._pdf_rect_to_pixel()
center = QtCore.QPointF(w_px / 2, h_px / 2)
check("D10 小字段中心位置不再被判为手柄", item._find_handle_at(center) is None,
      f"字段 {w_px:.1f}x{h_px:.1f}px，中心命中={item._find_handle_at(center)}")
big = FieldDefinition(name="大框", page=0, rect=(100.0, 500.0, 300.0, 540.0), tab_order=2)
cv.load_fields([big])
cv.select_field(big.id)
pump(80)
bitem = cv._field_items[big.id]
bw, bh = bitem._pdf_rect_to_pixel()
check("D10 大字段中心仍是'移动'而非手柄",
      bitem._find_handle_at(QtCore.QPointF(bw / 2, bh / 2)) is None)
check("D10 大字段四角仍可命中手柄",
      bitem._find_handle_at(QtCore.QPointF(0, 0)) == 0,
      f"左上角命中={bitem._find_handle_at(QtCore.QPointF(0, 0))}")


print("=" * 68)
print("D9  改变窗口大小后'适应窗口'使用最新基准")
print("=" * 68)
cv.resize(600, 400)
pump(120)
cv.zoom_in()
cv.zoom_in()
pump(80)
cv.resize(1100, 700)          # 放大后再改窗口（旧实现基准过期）
pump(150)
cv.zoom_fit()
pump(80)
sr = cv._scene.sceneRect()
vis_w = cv.viewport().width()
vis_h = cv.viewport().height()
scale = cv.transform().m11()
fits = scale * sr.width() <= vis_w + 2 and scale * sr.height() <= vis_h + 2
check("D9 改窗口后 Ctrl+0 页面确实放进视口", fits,
      f"缩放后页面 {scale * sr.width():.0f}x{scale * sr.height():.0f}px，视口 {vis_w}x{vis_h}px")


print("=" * 68)
print("P0-1 切换记录不再把上一份记录的值写进新记录")
print("=" * 68)
w.close()
data = new_data_dir()
pdf = make_pdf(os.path.join(data, "s.pdf"), 1)
w = MainWindow(data)
w.resize(1280, 800)
w.show()
t = w.template_manager.create("串值", pdf)
f1 = FieldDefinition(name="姓名", page=0, rect=(80, 140, 250, 165), tab_order=0)
f2 = FieldDefinition(name="备注", page=0, rect=(80, 200, 300, 240), tab_order=1)
t.fields = [f1, f2]
w.template_manager.update(t)
w._enter_design_mode(t)
w._on_design_to_fill()
pump(200)
rec_a = w._current_record
# 关键：把面板停在"非排序第一"的字段上（Tab 两下即可达到）
w.field_fill_panel.focus_field(f2.id)
w._on_field_value_changed(f2.id, "A2")
w._on_field_value_changed(f1.id, "A1")
w.field_fill_panel.focus_field(f2.id)
pump(120)
w._save_current_record()
rec_b = w.record_manager.create(t.id, "记录B")
w.record_manager.save(rec_b)
w._on_record_selected(rec_b.id)      # 切到一份全新的空记录
pump(120)
w._save_current_record()
b = w.record_manager.get(t.id, rec_b.id)
check("P0-1 新记录未继承旧记录的值",
      (b.values.get(f2.id) or "") == "" and (b.values.get(f1.id) or "") == "",
      f"B.姓名={b.values.get(f1.id)!r} B.备注={b.values.get(f2.id)!r}（旧实现 B.备注='A2'）")
a = w.record_manager.get(t.id, rec_a.id)
check("P0-1 旧记录的值完好无损", a.values.get(f2.id) == "A2" and a.values.get(f1.id) == "A1",
      f"A.姓名={a.values.get(f1.id)!r} A.备注={a.values.get(f2.id)!r}")


print("=" * 68)
print("P1-5 跨页 Tab 后画布仍显示已填内容")
print("=" * 68)
w.close()
data = new_data_dir()
pdf = make_pdf(os.path.join(data, "2p.pdf"), 2)
w = MainWindow(data)
w.resize(1280, 800)
w.show()
t = w.template_manager.create("跨页", pdf)
fa = FieldDefinition(name="甲", page=0, rect=(80, 140, 250, 165), tab_order=0)
fb = FieldDefinition(name="乙", page=1, rect=(80, 200, 300, 240), tab_order=1)
t.fields = [fa, fb]
w.template_manager.update(t)
w._enter_design_mode(t)
w._on_design_to_fill()
pump(200)
fa2, fb2 = w._current_template.fields[0], w._current_template.fields[1]
w._on_field_value_changed(fb2.id, "乙页已填")
w._on_field_value_changed(fa2.id, "甲页已填")
w.fill_mode.canvas.select_field(fa2.id)
pump(120)
w.fill_mode.focus_next_field()       # 跨页跳到第 2 页
pump(250)
it = w.fill_mode.canvas._field_items.get(fb2.id)
check("P1-5 跨页后目标字段图元仍带填写值",
      it is not None and getattr(it, "_fill_value", "") == "乙页已填",
      f"_fill_value={getattr(it, '_fill_value', '<无图元>')!r}")


print("=" * 68)
print("P0-4 重命名记录后保存不再回退")
print("=" * 68)
class _FakeInput:
    @staticmethod
    def getText(*a, **k):
        return ("新名字XYZ", True)


real_input = mw.QInputDialog
mw.QInputDialog = _FakeInput
try:
    rid = w._current_record.id
    w._on_record_rename(rid)
    w._save_current_record()
finally:
    mw.QInputDialog = real_input
check("P0-4 重命名后的名字在保存后仍然生效",
      w.record_manager.get(t.id, rid).name == "新名字XYZ",
      f"实测 {w.record_manager.get(t.id, rid).name!r}")


print("=" * 68)
print("P1-6 删除最后一条记录后，新建的记录会落盘且下拉可用")
print("=" * 68)
w.close()
data = new_data_dir()
pdf = make_pdf(os.path.join(data, "1p.pdf"), 1)
w = MainWindow(data)
w.resize(1280, 800)
w.show()
t = w.template_manager.create("记录", pdf)
fld = FieldDefinition(name="字段", page=0, rect=(80, 140, 250, 165), tab_order=0)
t.fields = [fld]
w.template_manager.update(t)
w._enter_design_mode(t)
w._on_design_to_fill()
pump(200)
only = w._current_record
# 注意：main_window / home_page 在 import 时就把 QMessageBox 绑成了模块级名字
# （QMessageBox = QtWidgets.QMessageBox），所以必须替换 **模块属性**，
# 只改 QtWidgets.QMessageBox 是够不着的 —— 漏一个就会模态阻塞到超时。
QtWidgets.QMessageBox = _AutoYesBox
mw.QMessageBox = _AutoYesBox
hp.QMessageBox = _AutoYesBox
try:
    w._on_record_delete(only.id)
finally:
    QtWidgets.QMessageBox = _RealMB
    mw.QMessageBox = _RealMB
    hp.QMessageBox = _RealMB
pump(150)
on_disk = w.record_manager.list_for_template(t.id)
check("P1-6 删完最后一条后磁盘上仍有一条可用记录", len(on_disk) == 1,
      f"磁盘记录数={len(on_disk)}")
combo = w.field_fill_panel._record_combo
check("P1-6 记录下拉框不是空的且可用",
      combo.count() == 1 and combo.isEnabled(), f"count={combo.count()} enabled={combo.isEnabled()}")


print("=" * 68)
print("P1-7 删除模板后卡片从卡片墙上真正移除")
print("=" * 68)
w.close()
data = new_data_dir()
pdf = make_pdf(os.path.join(data, "t.pdf"), 1)
w = MainWindow(data)
w.resize(1280, 800)
w.show()
t1 = w.template_manager.create("模板甲", pdf)
t2 = w.template_manager.create("模板乙", pdf)
w._show_home()
pump(300)
hp_page = w.home_page
check("P1-7 前提：两张卡片都在墙上", len(hp_page._cards) == 2, f"卡片数={len(hp_page._cards)}")
doomed = hp_page._cards[t1.id]
QtWidgets.QMessageBox = _AutoYesBox
mw.QMessageBox = _AutoYesBox
hp.QMessageBox = _AutoYesBox
try:
    hp_page._delete_template(hp_page.template_manager.get(t1.id))
finally:
    QtWidgets.QMessageBox = _RealMB
    mw.QMessageBox = _RealMB
    hp.QMessageBox = _RealMB
pump(300)
still_in_layout = any(
    hp_page._flow.itemAt(i) is not None
    and hp_page._flow.itemAt(i).widget() is doomed
    for i in range(hp_page._flow.count())
)
check("P1-7 被删模板的卡片已从布局移除", not still_in_layout,
      f"布局中仍有该卡片={still_in_layout}（旧实现只 pop 字典、卡片永久残留）")


print("=" * 68)
print("P1-8 画布删除字段后面板不再指向失效字段")
print("=" * 68)
w.close()
data = new_data_dir()
pdf = make_pdf(os.path.join(data, "d.pdf"), 1)
w = MainWindow(data)
w.resize(1280, 800)
w.show()
t = w.template_manager.create("孤儿", pdf)
fx = FieldDefinition(name="会被删", page=0, rect=(80, 140, 250, 165), tab_order=0)
t.fields = [fx]
w.template_manager.update(t)
w._enter_design_mode(t)
pump(200)
panel = w.field_design_panel
dcanvas = w.design_mode.canvas
panel.select_field(fx.id)
pump(120)
check("P1-8 前提：属性区已启用", panel._props_group.isEnabled())
dcanvas.remove_field(fx.id)
w._on_field_deleted_in_canvas(fx.id)
pump(120)
orphan = panel._current_field
check("P1-8 面板不再持有已删除的字段对象", orphan is None,
      f"_current_field={orphan!r}")
check("P1-8 属性区已禁用", not panel._props_group.isEnabled())


print("=" * 68)
print("P1-10 多行输入不再每敲一键就把光标顶到末尾")
print("=" * 68)
w.close()
data = new_data_dir()
pdf = make_pdf(os.path.join(data, "m.pdf"), 1)
w = MainWindow(data)
w.resize(1280, 800)
w.show()
t = w.template_manager.create("多行", pdf)
fm = FieldDefinition(name="备注", page=0, rect=(80, 200, 300, 260), tab_order=0, multiline=True)
t.fields = [fm]
w.template_manager.update(t)
w._enter_design_mode(t)
w._on_design_to_fill()
pump(200)
fid = w._current_template.fields[0].id
w.field_fill_panel.focus_field(fid)
pump(120)
widget = w.field_fill_panel._current_widget
widget.setPlainText("abcdef")
cur = widget.textCursor()
cur.setPosition(2)
widget.setTextCursor(cur)
before_pos = widget.textCursor().position()
w.field_fill_panel.sync_value(fid, "abcdef")      # 正是每次按键都会走的那一步
after_pos = widget.textCursor().position()
check("P1-10 值未变时不再回写控件，光标位置保持", before_pos == after_pos,
      f"光标 {before_pos} → {after_pos}（旧实现会被 setPlainText 顶到 6）")


print("=" * 68)
print("P0-3 首页右键导出 .lmt 使用最新模板（不再丢字段）")
print("=" * 68)
w.close()
data = new_data_dir()
pdf = make_pdf(os.path.join(data, "e.pdf"), 1)
w = MainWindow(data)
w.resize(1280, 800)
w.show()
w._show_home()
pump(200)
# 完全复刻真实顺序：先建模板（此时 0 字段）→ 首页建卡 → 再设计字段
t = w.template_manager.create("报销单", pdf)
w.home_page.refresh()
pump(200)
card = w.home_page._cards[t.id]
w._enter_design_mode(t)
t.fields = [FieldDefinition(name=f"字段{i}", page=0,
                            rect=(80, 140 + i * 40, 250, 165 + i * 40), tab_order=i)
            for i in range(3)]
w._save_template()
w._show_home()
pump(250)
check("P0-3 前提：卡片被复用（不是重建）", w.home_page._cards[t.id] is card)

out_lmt = os.path.join(data, "out.lmt")


class _FakeFD:
    @staticmethod
    def getSaveFileName(*a, **k):
        return (out_lmt, "")


class _FakeMB:
    @staticmethod
    def information(*a, **k):
        return None

    @staticmethod
    def critical(*a, **k):
        print("      导出报错:", a)
        return None


def _fake_menu_exec(menu, pos):
    for act in menu.actions():
        if act.text().startswith("导出模板"):
            return act
    return None


real_fd, real_mb, real_exec = hp.QFileDialog, hp.QMessageBox, hp.menu_exec
hp.QFileDialog, hp.QMessageBox, hp.menu_exec = _FakeFD, _FakeMB, _fake_menu_exec
try:
    card.customContextMenuRequested.emit(QtCore.QPoint(5, 5))
finally:
    hp.QFileDialog, hp.QMessageBox, hp.menu_exec = real_fd, real_mb, real_exec

import zipfile
n_fields = -1
if os.path.exists(out_lmt):
    with zipfile.ZipFile(out_lmt) as zf:
        n_fields = len(json.loads(zf.read("template.json")).get("fields", []))
check("P0-3 导出的 .lmt 含全部 3 个字段", n_fields == 3,
      f"实测 {n_fields} 个（旧实现为 0 个）")

print()
print(f"═══ v1.0.6 修复回归：{len(PASS)} 通过 / {len(FAIL)} 失败 ═══")
for x in FAIL:
    print("  ✗", x)
print("ALL V106 REGRESSION TESTS PASSED" if not FAIL else "V106 REGRESSION TESTS FAILED")
sys.exit(1 if FAIL else 0)
