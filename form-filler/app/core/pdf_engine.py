"""PDF 引擎 — 基于 PyMuPDF 封装，提供渲染、烧录、缩略图等功能

坐标系约定：
- 字段的 rect 始终以"原始 PDF 点坐标"存储；
- 页面旋转（扫描倾斜矫正）只在显示层处理，烧录时直接使用 PDF 坐标，
  因此显示与导出天然一致。
"""

import os
import math
import fitz  # PyMuPDF
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QSizeF


def get_page_count(pdf_path: str) -> int:
    """获取 PDF 页数"""
    doc = fitz.open(pdf_path)
    count = doc.page_count
    doc.close()
    return count


def get_page_size(pdf_path: str, page_num: int = 0) -> QSizeF:
    """获取指定页的尺寸（PDF 点单位，1 point = 1/72 inch）"""
    doc = fitz.open(pdf_path)
    rect = doc[page_num].rect
    doc.close()
    return QSizeF(rect.width, rect.height)


# ── 旋转几何工具（屏幕坐标系，y 轴向下，正角度=顺时针）────────────

def rotate_point_cw(
    x: float, y: float, cx: float, cy: float, angle_deg: float
) -> tuple[float, float]:
    """把点 (x,y) 绕中心 (cx,cy) 顺时针旋转 angle_deg 度"""
    if angle_deg == 0:
        return x, y
    rad = math.radians(angle_deg)
    dx = x - cx
    dy = y - cy
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    return (cx + dx * cos_a + dy * sin_a, cy - dx * sin_a + dy * cos_a)


def rotate_point_ccw(
    x: float, y: float, cx: float, cy: float, angle_deg: float
) -> tuple[float, float]:
    """把点 (x,y) 绕中心 (cx,cy) 逆时针旋转 angle_deg 度"""
    return rotate_point_cw(x, y, cx, cy, -angle_deg)


def rotate_rect_cw(
    rect: tuple[float, float, float, float],
    cx: float, cy: float, angle_deg: float,
) -> tuple[float, float, float, float]:
    """旋转矩形（旋转两个对角点，再规整顺序）"""
    x0, y0 = rotate_point_cw(rect[0], rect[1], cx, cy, angle_deg)
    x1, y1 = rotate_point_cw(rect[2], rect[3], cx, cy, angle_deg)
    return _order_rect((x0, y0, x1, y1))


def rotate_rect_ccw(
    rect: tuple[float, float, float, float],
    cx: float, cy: float, angle_deg: float,
) -> tuple[float, float, float, float]:
    """逆时针旋转矩形"""
    x0, y0 = rotate_point_ccw(rect[0], rect[1], cx, cy, angle_deg)
    x1, y1 = rotate_point_ccw(rect[2], rect[3], cx, cy, angle_deg)
    return _order_rect((x0, y0, x1, y1))


def _order_rect(rect: tuple) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = rect
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0
    return (x0, y0, x1, y1)


def normalize_angle(angle: float) -> float:
    """把角度归一到 (-180, 180]"""
    a = angle % 360.0
    if a > 180:
        a -= 360.0
    return a


def _round_rotation(angle: float) -> int:
    """将角度规范化为 PyMuPDF insert_textbox 接受的值：0 / 90 / 180 / 270"""
    if angle == 0:
        return 0
    return int(round(angle / 90) * 90) % 360


# ── 渲染 ───────────────────────────────────────────

def render_page(pdf_path: str, page_num: int = 0, dpi: int = 150) -> QPixmap:
    """把指定页渲染为 QPixmap（始终渲染原始朝向，不烘焙旋转）

    页面旋转矫正由画布层用 QGraphicsItem 变换完成。
    通过 PNG 字节流加载，避免直接引用 pix.samples 缓冲区可能悬空的隐患。
    """
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    doc.close()
    pixmap = QPixmap()
    pixmap.loadFromData(pix.tobytes("png"))
    return pixmap


def render_thumbnail(pdf_path: str, page_num: int = 0, dpi: int = 72) -> QPixmap:
    """渲染缩略图（低分辨率）"""
    return render_page(pdf_path, page_num, dpi)


def render_all_page_thumbnails(pdf_path: str, dpi: int = 72) -> list[QPixmap]:
    """渲染所有页的缩略图"""
    count = get_page_count(pdf_path)
    return [render_thumbnail(pdf_path, i, dpi) for i in range(count)]


# ── 烧录 ───────────────────────────────────────────

def burn_text(
    pdf_path: str,
    fields: list,
    values: dict[str, str],
    page_settings: list = None,
    output_path: str = None,
) -> str:
    """把填写内容写进 PDF 并另存为新文件

    fields 的 rect 均为原始 PDF 坐标，页面旋转仅影响显示，
    这里直接按坐标写入即可。
    """
    if output_path is None:
        base, ext = os.path.splitext(pdf_path)
        output_path = f"{base}_filled{ext}"

    doc = fitz.open(pdf_path)

    cjk_font = _find_cjk_font()
    if cjk_font:
        for page_num in range(doc.page_count):
            try:
                doc[page_num].insert_font(fontfile=cjk_font, fontname="CJKFont")
            except Exception:
                pass  # 字体已存在则跳过

    for field in fields:
        field_id = field.id
        value = values.get(field_id, field.default_value)
        if not value:
            continue

        page = doc[field.page]

        if field.field_type == "checkbox":
            checked = value.lower() in ("true", "yes", "✓", "√", "是", "1", "on")
            if not checked:
                continue
            value = "√"

        font_size = field.font_size
        align_map = {"left": 0, "center": 1, "right": 2}
        align = align_map.get(field.alignment, 0)
        font_name = "CJKFont" if cjk_font else "china-ss"
        field_rotation = _round_rotation(field.rotation)

        rect = fitz.Rect(*field.rect)
        _insert_text_fit(
            page, rect, value,
            font_name=font_name,
            font_size=font_size,
            align=align,
            rotation=field_rotation,
        )

    doc.save(output_path)
    doc.close()
    return output_path


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


def pdf_to_images(pdf_path: str, dpi: int = 150) -> list[QPixmap]:
    """将 PDF 所有页渲染为 QPixmap 列表"""
    return [render_page(pdf_path, i, dpi) for i in range(get_page_count(pdf_path))]
