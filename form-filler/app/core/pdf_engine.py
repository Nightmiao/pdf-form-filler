"""PDF 引擎 — 基于 PyMuPDF 封装：渲染、烧录、缩略图

坐标与旋转约定：
- 字段 rect 恒以"原始 PDF 点坐标"存储；
- 页面旋转（扫描倾斜矫正）只影响显示；导出时把矫正角一并写入，
  因此"画布上看到什么，导出就是什么"；
- 任意角度的字段旋转用 insert_text 的 morph 矩阵精确写入，
  不再四舍五入到 90°（insert_textbox 只用于 90° 整数倍的快速路径）。
"""

from __future__ import annotations


import os
import math
import threading
import fitz  # PyMuPDF
from app.qt import QtGui, QtCore
from app.core.field_model import is_truthy

QPixmap = QtGui.QPixmap
QSizeF = QtCore.QSizeF


# ── 旋转几何工具（屏幕坐标系，y 轴向下，正角度=顺时针）────────────

def rotate_point_cw(
    x: float, y: float, cx: float, cy: float, angle_deg: float
) -> tuple[float, float]:
    """屏幕坐标系（y 向下）中顺时针旋转；与 QTransform.rotate 方向一致。

    已用 QTransform.rotate(+15) 实测校准：正角度 = 屏幕顺时针。
    """
    if angle_deg == 0:
        return x, y
    rad = math.radians(angle_deg)
    dx = x - cx
    dy = y - cy
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    return (cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a)


def rotate_point_ccw(
    x: float, y: float, cx: float, cy: float, angle_deg: float
) -> tuple[float, float]:
    return rotate_point_cw(x, y, cx, cy, -angle_deg)


def rotate_rect_cw(
    rect: tuple[float, float, float, float],
    cx: float, cy: float, angle_deg: float,
) -> tuple[float, float, float, float]:
    """顺时针旋转矩形（保持精确角点，不做轴对齐外接框）"""
    x0, y0 = rotate_point_cw(rect[0], rect[1], cx, cy, angle_deg)
    x1, y1 = rotate_point_cw(rect[2], rect[3], cx, cy, angle_deg)
    return (x0, y0, x1, y1)


def rotate_rect_ccw(
    rect: tuple[float, float, float, float],
    cx: float, cy: float, angle_deg: float,
) -> tuple[float, float, float, float]:
    """逆时针旋转矩形（保持精确角点，与 cw 互逆）"""
    x0, y0 = rotate_point_ccw(rect[0], rect[1], cx, cy, angle_deg)
    x1, y1 = rotate_point_ccw(rect[2], rect[3], cx, cy, angle_deg)
    return (x0, y0, x1, y1)


def rotate_rect_about_center(
    rect: tuple[float, float, float, float],
    cx: float, cy: float, angle_deg: float,
) -> tuple[float, float, float, float]:
    """把轴对齐矩形绕 (cx, cy) 旋转 angle_deg：**只旋转中心点，宽高保持不变**。

    这是"页面矫正角只影响显示"这一契约的正确实现，也是与
    `rotate_rect_cw` 的关键区别：

    - `rotate_rect_cw` 只把两个对角点分别旋转，得到的两个点**不再是轴对齐
      矩形的对角点**。若调用方再把 (x1-x0, y1-y0) 当作宽高，就会把真实的
      w×h 换成"旋转后对角线"的投影
      (w·cosθ−h·sinθ) × (w·sinθ+h·cosθ) —— 100×30 的框在 5° 下会变成
      97×38.6，高度虚胖 29%。历史上画布与导出都用错在这里。
    - 本函数保持宽高、只把中心点绕 (cx, cy) 旋转，因此配合"字段自身角度 +=
      页面矫正角"就得到唯一正确的显示几何：字段绕页面中心转 θ，形状不变。

    与 `rotate_rect_cw/ccw` 一样，本函数与其逆运算（传 -angle_deg）精确互逆。
    """
    x0, y0, x1, y1 = rect
    if angle_deg == 0:
        return (x0, y0, x1, y1)
    mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    nx, ny = rotate_point_cw(mx, my, cx, cy, angle_deg)
    hw, hh = (x1 - x0) / 2.0, (y1 - y0) / 2.0
    return (nx - hw, ny - hh, nx + hw, ny + hh)


def normalize_angle(angle: float) -> float:
    """把角度归一到 (-180, 180]"""
    a = angle % 360.0
    if a > 180:
        a -= 360.0
    return a


# ── PDF 源（复用同一个已打开的文档，避免每页都重新开文件）─────────

class PdfSource:
    """一个 PDF 文件的句柄：页数/尺寸/渲染都从这里走

    实现说明：
    - 用 fitz.open(stream=文件字节) 从内存打开 —— 不占用磁盘文件句柄，
      Windows 上用户可以随时删除/替换原始 PDF 文件；
    - 渲染方法加 threading.Lock —— MuPDF 的 Document 不是线程安全的，
      GUI 线程同步渲染与后台预取线程共用同一句柄时串行化访问。
    """

    def __init__(self, pdf_path: str):
        self.path = pdf_path
        with open(pdf_path, "rb") as f:
            data = f.read()
        self.doc = fitz.open(stream=data, filetype="pdf")
        self._lock = threading.Lock()

    @property
    def page_count(self) -> int:
        return self.doc.page_count

    def page_size(self, page_num: int) -> QSizeF:
        rect = self.doc[page_num].rect
        return QSizeF(rect.width, rect.height)

    def render_page_bytes(self, page_num: int, dpi: int) -> bytes:
        """渲染一页为 PNG 字节流（可在工作线程调用，内部加锁）"""
        with self._lock:
            zoom = dpi / 72.0
            pix = self.doc[page_num].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            return pix.tobytes("png")

    def render_all_page_bytes(self, dpi: int) -> list[bytes]:
        """一次打开渲染全部页（批量缩略图用，内部加锁）"""
        out = []
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        with self._lock:
            for page_num in range(self.page_count):
                pix = self.doc[page_num].get_pixmap(matrix=mat)
                out.append(pix.tobytes("png"))
        return out

    def close(self):
        with self._lock:
            try:
                self.doc.close()
            except Exception:
                pass


def get_page_count(pdf_path: str) -> int:
    doc = fitz.open(pdf_path)
    try:
        return doc.page_count
    finally:
        doc.close()


# ── 渲染 ───────────────────────────────────────────

def bytes_to_pixmap(png_bytes: bytes) -> QPixmap:
    pixmap = QPixmap()
    pixmap.loadFromData(png_bytes)
    return pixmap


def render_page(pdf_path: str, page_num: int = 0, dpi: int = 150) -> QPixmap:
    """把指定页渲染为 QPixmap（单页便捷接口；批量请用 PdfSource）"""
    source = PdfSource(pdf_path)
    try:
        return bytes_to_pixmap(source.render_page_bytes(page_num, dpi))
    finally:
        source.close()


def render_thumbnail(pdf_path: str, page_num: int = 0, dpi: int = 72) -> QPixmap:
    return render_page(pdf_path, page_num, dpi)


def pdf_to_images(pdf_path: str, dpi: int = 150) -> list[QPixmap]:
    """将 PDF 所有页渲染为 QPixmap 列表（只打开一次文件）"""
    source = PdfSource(pdf_path)
    try:
        return [
            bytes_to_pixmap(b) for b in source.render_all_page_bytes(dpi)
        ]
    finally:
        source.close()


# ── 烧录 ───────────────────────────────────────────

def burn_text(
    pdf_path: str,
    fields: list,
    values: dict[str, str],
    page_settings: list = None,
    output_path: str = None,
) -> str:
    """把填写内容写进 PDF 并另存为新文件

    - 90° 整数倍且页面无矫正角：insert_textbox 快速路径（自动缩字号防溢出）；
    - 其他情况（任意角度字段旋转 / 页面矫正角 ≠ 0）：insert_text + morph
      矩阵精确写入，显示与导出一致。
    - 非法字段（页码越界、rect 损坏）自动跳过，不再抛异常。
    """
    if output_path is None:
        base, ext = os.path.splitext(pdf_path)
        output_path = f"{base}_filled{ext}"

    doc = fitz.open(pdf_path)
    try:
        page_count = doc.page_count
        page_settings = page_settings or []

        cjk_font = _find_cjk_font()
        if cjk_font:
            for page_num in range(page_count):
                try:
                    doc[page_num].insert_font(fontfile=cjk_font, fontname="CJKFont")
                except Exception:
                    pass

        for field in fields:
            try:
                _burn_field(doc, field, values, page_settings, cjk_font)
            except Exception:
                continue  # 单个字段失败不影响其余字段

        doc.save(output_path)
    finally:
        doc.close()
    return output_path


def expected_burned_text(field, values: dict) -> str:
    """该字段"本应被烧录进 PDF"的文字；无内容/不勾选时返回空串。

    与 _burn_field 的取值口径保持一致（含勾选框归一化成 √）。
    """
    field_id = getattr(field, "id", None)
    value = values.get(field_id, getattr(field, "default_value", "")) if field_id else ""
    if not value:
        return ""
    if getattr(field, "field_type", "text") == "checkbox":
        return "√" if is_truthy(value) else ""
    return str(value)


def missing_burned_fields(output_path: str, fields: list, values: dict) -> list:
    """校验导出结果：返回"有内容却没写进 PDF"的字段名列表。

    为什么需要它：打印路径一直有"有值却提取不到文字"的自检，导出路径却**无条件**
    弹"导出成功"；而 burn_text 对于越界页码、退化矩形、字体写入失败等情况是
    `except: continue` 静默跳过的。于是一份缺了字段的表单会以"成功"的面目交到
    用户手里 —— 对一个要拿去报账的工具来说，这是最不该静默的一类失败。
    """
    names = []
    try:
        doc = fitz.open(output_path)
    except Exception:
        return [getattr(f, "name", "?") for f in fields]
    try:
        page_text = {}
        for i in range(doc.page_count):
            try:
                page_text[i] = "".join(doc[i].get_text().split())
            except Exception:
                page_text[i] = ""
        for field in fields:
            want = expected_burned_text(field, values)
            if not want:
                continue
            name = getattr(field, "name", "?")
            page_num = int(getattr(field, "page", 0) or 0)
            if not (0 <= page_num < doc.page_count):
                names.append(name)
                continue
            needle = "".join(want.split())
            if needle and needle not in page_text.get(page_num, ""):
                names.append(name)
    finally:
        doc.close()
    return names


def _burn_field(doc, field, values, page_settings, cjk_font):
    field_id = getattr(field, "id", None)
    value = values.get(field_id, getattr(field, "default_value", "")) if field_id else ""
    if not value:
        return

    page_num = int(getattr(field, "page", 0))
    if not (0 <= page_num < doc.page_count):
        return
    page = doc[page_num]

    rect = getattr(field, "rect", None)
    if not isinstance(rect, (list, tuple)) or len(rect) != 4:
        return
    if not all(math.isfinite(float(v)) for v in rect):
        return
    rect = fitz.Rect(float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3]))
    if rect.is_empty or rect.width < 1 or rect.height < 1:
        return

    if getattr(field, "field_type", "text") == "checkbox":
        checked = is_truthy(value)
        if not checked:
            return
        value = "√"

    font_size = float(getattr(field, "font_size", 12.0) or 12.0)
    align = getattr(field, "alignment", "left")
    rotation = float(getattr(field, "rotation", 0.0) or 0.0)

    page_rot = 0.0
    if 0 <= page_num < len(page_settings):
        page_rot = float(getattr(page_settings[page_num], "rotation", 0.0) or 0.0)

    font_name = "CJKFont" if cjk_font else "china-ss"

    if page_rot == 0 and rotation % 90 == 0:
        # 快速路径：轴对齐 + 90° 倍数
        align_map = {"left": 0, "center": 1, "right": 2}
        _insert_text_fit(
            page, rect, value,
            font_name=font_name,
            font_size=font_size,
            align=align_map.get(align, 0),
            rotation=_round_rotation(-rotation),
        )
    else:
        # 精确路径：先在"显示坐标系"（页面矫正角后的轴对齐矩形）里排版，
        # 再把基准点换算回 PDF 坐标，并用 morph 矩阵写入任意角度。
        page_rect = page.rect
        pcx, pcy = page_rect.width / 2, page_rect.height / 2
        # 显示排版框 = 原矩形绕页中心旋转 page_rot（宽高不变）。
        # 不能用 rotate_rect_cw：那会把宽高换成旋转后对角线的投影，
        # 导致自动缩字号与对齐位置随页面矫正角漂移（与画布显示不一致）。
        disp_rect = fitz.Rect(*rotate_rect_about_center(
            (rect.x0, rect.y0, rect.x1, rect.y1), pcx, pcy, page_rot
        ))
        _insert_text_rotated(
            page, disp_rect, value,
            font_name=font_name,
            font_size=font_size,
            align=align,
            rotation=rotation,
            page_rot=page_rot,
            page_center=(pcx, pcy),
            cjk_font=cjk_font,
        )


def _insert_text_rotated(
    page, disp_rect, value, font_name, font_size, align,
    rotation, page_rot, page_center, cjk_font,
):
    """任意角度写入：显示坐标排版 → 回转 PDF 坐标 → morph 旋转字形。

    - 显示坐标：页面整体旋转 page_rot 后，文字应呈轴对齐；
    - 文字在 PDF 中的角度 = rotation（字段自身旋转角）；
    - morph 以"行基线点"为枢轴，只旋转字形不移动位置。
    """
    lines = str(value).split("\n")
    metrics_font = fitz.Font(fontfile=cjk_font) if cjk_font else fitz.Font("china-ss")

    # 自动缩小字号直到放得下（与 insert_textbox 路径行为一致）
    size = font_size
    line_height = size * 1.25
    total_h = line_height * len(lines)
    max_w = max((metrics_font.text_length(ln, size) for ln in lines), default=0)
    while size >= 4:
        line_height = size * 1.25
        total_h = line_height * len(lines)
        max_w = max((metrics_font.text_length(ln, size) for ln in lines), default=0)
        if max_w <= disp_rect.width + 0.5 and total_h <= disp_rect.height + 0.5:
            break
        size -= 1

    ascent = metrics_font.ascender * size
    top = disp_rect.y0 + max(0.0, (disp_rect.height - total_h) / 2)

    for i, line in enumerate(lines):
        w = metrics_font.text_length(line, size)
        if align == "center":
            x = disp_rect.x0 + (disp_rect.width - w) / 2
        elif align == "right":
            x = disp_rect.x1 - w
        else:
            x = disp_rect.x0
        y = top + ascent + i * line_height

        # 显示坐标 → PDF 坐标（绕页面中心回转矫正角）
        px, py = rotate_point_ccw(x, y, page_center[0], page_center[1], page_rot)
        pivot = fitz.Point(px, py)
        page.insert_text(
            pivot, line,
            fontname=font_name,
            fontsize=size,
            # Qt setRotation(+θ)=视觉顺时针；PyMuPDF morph Matrix(+θ)=视觉逆时针，
            # 取负号让导出与画布显示方向一致
            morph=(pivot, fitz.Matrix(-rotation)),
        )


def _insert_text_fit(page, rect, value, font_name, font_size, align, rotation):
    """把文字写入矩形框，放不下时自动缩小字号，最后兜底强制写入"""
    size = font_size
    while size >= 4:
        rc = page.insert_textbox(
            rect, value,
            fontname=font_name,
            fontsize=size,
            align=align,
            rotate=rotation,
        )
        if rc >= 0:
            return
        size -= 1

    try:
        baseline = fitz.Point(rect.x0 + 1, rect.y0 + min(font_size, rect.height) * 0.85)
        page.insert_text(
            baseline, value,
            fontname=font_name,
            fontsize=min(font_size, max(rect.height - 1, 4)),
            rotate=rotation,
        )
    except Exception:
        pass


def _round_rotation(angle: float) -> int:
    if angle == 0:
        return 0
    return int(round(angle / 90) * 90) % 360


def _find_cjk_font() -> str:
    """查找系统可用的中文字体文件路径"""
    import sys
    candidates = []
    if sys.platform == "win32":
        candidates = [
            "C:/Windows/Fonts/simsun.ttc",
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""