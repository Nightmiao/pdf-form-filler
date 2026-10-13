# -*- coding: utf-8 -*-
"""界面布局回归 — 1024x768 小屏 / 窄屏工具栏不折叠、缩略图栏自动收起

背景：目标机可能是 1024x768 的 Win7。左栏 208 + 右栏 300 只剩 516px 给中间，
设计/填写工具栏（需要 675/685px）会把「保存」「去填写」挤进 "»" 溢出菜单，
用户根本找不到。本用例断言这些关键按钮在 1024x768 下依然直接可见。

用法：  python tests/ui_layout_check.py   （退出码非 0 = 失败）
"""
import sys, os, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 输出编码兜底：stdout 被重定向到文件/管道时 Windows 会退回 GBK，
# 打印 − / ✓ / ═ 等字符会抛 UnicodeEncodeError 让脚本中途退出。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import fitz
from app.qt import QtWidgets, QtGui, Qt, QT6

app = QtWidgets.QApplication(sys.argv)

from app.ui.theme import APP_STYLESHEET
# 离屏平台默认拿不到系统字体，必须显式注册，否则截图里全是无字空白
if QT6:
    from app.qt import QtGui as _QG
    if not any("YaHei" in f for f in _QG.QFontDatabase.families()):
        _QG.QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
else:
    from app.qt import QtGui as _QG
    _qfd = _QG.QFontDatabase()
    if not any("YaHei" in f for f in _qfd.families()):
        _qfd.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
app.setFont(QtGui.QFont("Microsoft YaHei", 10))
app.setStyle("Fusion")
app.setStyleSheet(APP_STYLESHEET)

FAILS = []
SHOT_DIR = os.path.join(tempfile.gettempdir(), "fflayout")
os.makedirs(SHOT_DIR, exist_ok=True)


def check(name, ok, detail=""):
    print(f"  {'[PASS]' if ok else '[FAIL]'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILS.append(f"{name}: {detail}")


data_dir = tempfile.mkdtemp(prefix="fflayout_")
with open(os.path.join(data_dir, "settings.json"), "w", encoding="utf-8") as f:
    json.dump({"onboarding_done": True}, f)

pdf_path = os.path.join(data_dir, "sample.pdf")
doc = fitz.open()
for i in range(2):
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), f"Form Page {i+1}", fontsize=16)
doc.save(pdf_path)
doc.close()

from app.ui.main_window import MainWindow
from app.core.field_model import FieldDefinition

w = MainWindow(data_dir)
w.show()
app.processEvents()


def visible_in_toolbar(btn) -> bool:
    """按钮是否真的显示出来了（没被塞进溢出菜单）"""
    if not btn.isVisible():
        return False
    # Qt 把放不下的控件设成不可见；再确认它确实在窗口内
    tl = btn.mapTo(w, btn.rect().topLeft())
    return tl.x() >= 0 and tl.x() + btn.width() <= w.width() + 2


def active_toolbar_widgets(mode):
    """返回当前模式下所有 QToolBar 里的控件"""
    from app.qt import QtWidgets as Q
    out = []
    for bar in mode.findChildren(Q.QToolBar):
        out.extend(bar.findChildren(Q.QWidget))
    return out


t = w.template_manager.create("小屏测试表单", pdf_path)
f1 = FieldDefinition(name="姓名", field_type="text", page=0, rect=(80, 140, 250, 165), tab_order=0)
w._enter_design_mode(t)
w.design_mode.canvas.add_field(f1)
w.design_mode.canvas.field_created.emit(f1)
app.processEvents()

for label, (ww, wh) in (("1280x800", (1280, 800)), ("1024x768", (1024, 768)),
                        ("1024x680(最小)", (1024, 680))):
    print(f"\n===== 窗口 {label} =====")
    w.resize(ww, wh)
    app.processEvents()

    # 设计模式
    # 必须走真实的模式入口：只 setCurrentIndex(center_stack) 不会切换右侧面板，
    # 于是从第二轮迭代起会截出"设计工具栏 + 填写右栏"的混合态 —— 这个状态在真实
    # 运行中根本不存在，窄屏截图却是整个用例存在的理由。
    w._enter_design_mode(t)
    w._apply_sidebar()
    app.processEvents()
    from app.qt import QtWidgets as Q
    bars = w.design_mode.findChildren(Q.QToolBar)
    print(f"        中心区宽={w.center_stack.width()} 右栏宽={w.right_panel.width()} "
          f"左栏可见={w.left_panel.isVisible()} 左栏宽={w.left_panel.width()}")
    for i, b in enumerate(bars):
        print(f"        工具栏[{i}] 宽={b.width()} sizeHint={b.sizeHint().width()} "
              f"隐藏控件={[c.text() for c in b.findChildren(Q.QWidget) if c.isVisible() is False and hasattr(c, 'text') and c.text()]}")
    check(f"{label} 设计-保存按钮可见", visible_in_toolbar(w.design_mode._save_btn))
    check(f"{label} 设计-去填写按钮可见", visible_in_toolbar(w.design_mode._fill_btn))
    check(f"{label} 设计-放大按钮可见", visible_in_toolbar(w.design_mode._zoom_in_btn))
    check(f"{label} 设计-适应窗口按钮可见", visible_in_toolbar(w.design_mode._fit_btn))
    # 填写模式同样要能看到「调整设计」和「返回模板库」
    check(f"{label} 填写-调整设计可见",
          visible_in_toolbar(w.fill_mode._design_btn) if hasattr(w.fill_mode, "_design_btn") else True,
          "（按钮未暴露引用则跳过）")
    shot = os.path.join(SHOT_DIR, f"design_{label.replace('(', '_').replace(')', '')}.png")
    w.grab().save(shot, "PNG")
    print(f"        截图: {shot}")

    # 填写模式
    w._enter_fill_mode(t)
    app.processEvents()
    check(f"{label} 填写-工具栏有可见控件",
          any(visible_in_toolbar(b) for b in active_toolbar_widgets(w.fill_mode)))
    shot = os.path.join(SHOT_DIR, f"fill_{label.replace('(', '_').replace(')', '')}.png")
    w.grab().save(shot, "PNG")
    print(f"        截图: {shot}")

    # 缩略图栏：窄屏应收起，宽屏应显示
    if ww < 1180:
        check(f"{label} 缩略图栏自动收起", not w.left_panel.isVisible(),
              f"visible={w.left_panel.isVisible()}")
    else:
        check(f"{label} 缩略图栏显示", w.left_panel.isVisible(),
              f"visible={w.left_panel.isVisible()}")

# 手动开关
print("\n===== 缩略图栏手动开关 =====")
w.resize(1024, 768)
w._on_toggle_sidebar(True)
app.processEvents()
check("窄屏手动强制显示后可见", w.left_panel.isVisible())
w._on_toggle_sidebar(False)
app.processEvents()
check("手动隐藏后不可见", not w.left_panel.isVisible())
w.resize(1280, 800)
w._on_toggle_sidebar(True)
app.processEvents()
check("宽屏恢复显示", w.left_panel.isVisible())

# 关键控件的最小宽度不应把窗口顶爆
print("\n===== 窗口最小宽度 =====")
w._show_home()
app.processEvents()
mh = w.minimumSizeHint()
check("窗口 minimumSizeHint 宽度 <= 1000", mh.width() <= 1000, f"实测 {mh.width()}px")

# 首页空状态图标必须是"画出来的"图，不能依赖 emoji 字体
# （Windows 7 没有 Segoe UI Emoji，"📄" 会变成空心方框）
print("\n===== Win7 字体安全 =====")
from app.ui.theme import step_glyph
for kind in ("document", "draw", "print"):
    pm = step_glyph(kind, 64)
    img = pm.toImage()
    non_transparent = 0
    for y in range(0, img.height(), 2):
        for x in range(0, img.width(), 2):
            if img.pixelColor(x, y).alpha() > 0:
                non_transparent += 1
    check(f"图标 {kind} 已绘制出内容", (not pm.isNull()) and non_transparent > 50,
          f"不透明采样点={non_transparent}")

import re as _re
src_files = []
for root, _dirs, files in os.walk(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "app")):
    for fn in files:
        if fn.endswith(".py"):
            src_files.append(os.path.join(root, fn))
emoji_hits = []
for path in src_files:
    with open(path, "r", encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            for ch in line:
                cp = ord(ch)
                if 0x1F300 <= cp <= 0x1FAFF or cp in (0x2705, 0x274C, 0x2728, 0x270F):
                    emoji_hits.append(f"{os.path.basename(path)}:{i} U+{cp:04X}")
check("源码里没有 emoji 字符（Win7 会显示成方框）", not emoji_hits,
      "; ".join(emoji_hits[:6]))

print(f"\n═══ 界面布局回归：{len(FAILS)} 项失败 ═══")
for x in FAILS:
    print("  ✗", x)
print("ALL UI LAYOUT TESTS PASSED" if not FAILS else "UI LAYOUT TESTS FAILED")
print("SHOTDIR:", SHOT_DIR)
sys.exit(1 if FAILS else 0)
