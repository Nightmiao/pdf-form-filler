"""PDF 引擎 — 基于 PyMuPDF 封装，提供渲染、烧录、缩略图等功能"""

import os
import math
import fitz  # PyMuPDF
from PySide6.QtGui import QPixmap, QImage, QTransform, QFont
from PySide6.QtCore import Qt, QSizeF


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


def _rotate_point(
    x: float, y: float, cx: float, cy: float, angle_deg: float
) -> tuple[float, float]:
    """围绕中心点旋转坐标"""
    if angle_deg == 0:
        return x, y
    rad = math.radians(-angle_deg)  # 逆旋转
    dx = x - cx
    dy = y - cy
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    rx = dx * cos_a - dy * sin_a + cx
    ry = dx * sin_a + dy * cos_a + cy
    return rx, ry


def _rotate_rect(
    rect: tuple[float, float, float, float],
    cx: float, cy: float, angle_deg: float,
) -> tuple[float, float, float, float]:
    """旋转矩形（通过旋转两个对角点）"""
    x0, y0 = _rotate_point(rect[0], rect[1], cx, cy, angle_deg)
    x1, y1 = _rotate_point(rect[2], rect[3], cx, cy, angle_deg)
    # 保持正确的顺序
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0
    return (x0, y0, x1, y1)


def _round_rotation(angle: float) -> int:
    """将角度规范化为 PyMuPDF insert_textbox 接受的值：0 / 90 / 180 / 270。

    insert_textbox 的 rotate 参数只接受这四个非负整数，
    负角度或 360 等会抛 ValueError，因此先取模再四舍五入到最近 90° 倍。
    """
    if angle == 0:
        return 0
    return int(round(angle / 90) * 90) % 360


def render_page(
    pdf_path: str, page_num: int = 0, dpi: int = 150, rotation: float = 0.0
) -> QPixmap:
    """渲染指定页为 QPixmap

    Args:
        pdf_path: PDF 文件路径
        page_num: 页码（0-based）
        dpi: 渲染分辨率
        rotation: 额外旋转角度（用于修正扫描倾斜），单位度
    """
    doc = fitz.open(pdf_path)
    page = doc[page_num]

    # 计算缩放矩阵
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    pix = page.get_pixmap(matrix=mat)
    doc.close()

    # 转换为 QPixmap
    img = QImage(
        pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888
    )
    pixmap = QPixmap.fromImage(img)

    # 应用旋转（围绕中心）
    if rotation != 0:
        transform = QTransform().rotate(rotation)
        pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

    return pixmap


def render_thumbnail(pdf_path: str, page_num: int = 0) -> QPixmap:
    """渲染缩略图（低分辨率）"""
    return render_page(pdf_path, page_num, dpi=36)


def render_all_page_thumbnails(pdf_path: str) -> list[QPixmap]:
    """渲染所有页的缩略图"""
    count = get_page_count(pdf_path)
    thumbnails = []
    for i in range(count):
        thumbnails.append(render_thumbnail(pdf_path, i))
    return thumbnails


def burn_text(
    pdf_path: str,
    fields: list,
    values: dict[str, str],
    page_settings: list = None,
    output_path: str = None,
) -> str:
    """将填写内容烧录到 PDF 上，生成新文件

    处理旋转逻辑：
    - 页面旋转（扫描倾斜修正）：调整字段坐标逆向旋转，确保文字位置正确
    - 字段旋转：四舍五入到最近 90° 整数倍（PyMuPDF 限制）

    Args:
        pdf_path: 原始 PDF 路径
        fields: 字段定义列表（FieldDefinition）
        values: {field_id: 填写的值}
        page_settings: 页面设置列表（PageSettings），用于页面旋转
        output_path: 输出路径，默认在原文件名后加 _filled

    Returns:
        输出文件路径
    """
    if output_path is None:
        base, ext = os.path.splitext(pdf_path)
        output_path = f"{base}_filled{ext}"

    doc = fitz.open(pdf_path)
    page_settings = page_settings or []

    # 查找可用的中文字体并嵌入到每页
    cjk_font = _find_cjk_font()
    if cjk_font:
        for page_num in range(doc.page_count):
            try:
                doc[page_num].insert_font(fontfile=cjk_font, fontname="CJKFont")
            except Exception:
                pass  # 字体已存在则跳过

    # 缓存每页的中心点
    page_centers = {}
    for page_num in range(doc.page_count):
        rect = doc[page_num].rect
        page_centers[page_num] = (rect.width / 2, rect.height / 2)

    for field in fields:
        field_id = field.id
        value = values.get(field_id, field.default_value)
        if not value:
            continue

        page = doc[field.page]
        page_center = page_centers.get(field.page, (0, 0))

        # 处理页面旋转：调整字段坐标
        page_rot = 0.0
        if field.page < len(page_settings):
            page_rot = page_settings[field.page].rotation

        field_rect = field.rect
        if page_rot != 0:
            field_rect = _rotate_rect(
                field_rect, page_center[0], page_center[1], page_rot
            )

        rect = fitz.Rect(*field_rect)
        field_rotation = _round_rotation(field.rotation)

        # 根据字段类型处理显示值
        if field.field_type == "checkbox":
            # 注意：☑/☐（U+2611/U+2610）在 simsun 等常见中文字体里没有字形，
            # 会被渲染成空白方块，导致"勾了却看不见"。改用根号 √（U+221A，
            # 中文字体普遍包含）表示勾选，未勾选则留空不打印。
            checked = value.lower() in ("true", "yes", "✓", "√", "是", "1", "on")
            if not checked:
                continue
            value = "√"

        font_size = field.font_size
        align_map = {"left": 0, "center": 1, "right": 2}
        align = align_map.get(field.alignment, 0)

        # 选择字体：优先用系统 CJK 字体，其次用 pyMuPDF 内置 china-ss
        font_name = "CJKFont" if cjk_font else "china-ss"
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
    """将文字写入矩形框，自动适配字号避免溢出导致写不进去。

    insert_textbox 的陷阱：当文字（含行高）放不下矩形时会直接放弃写入并返回负值，
    不抛异常——这会导致表单看起来是"白板"。因此这里：
    1. 先按设计字号写；
    2. 写不下就逐步缩小字号重试（最小到 4pt）；
    3. 仍写不下则用 insert_text 在框内强制写入作为兜底，保证内容可见。
    """
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
            return  # 成功写入
        size -= 1

    # 兜底：insert_text 不受框高限制，按基线坐标强制写入
    try:
        # 基线大致放在框内靠上位置，留出一点字体上沿空间
        baseline = fitz.Point(rect.x0 + 1, rect.y0 + min(font_size, rect.height) * 0.85)
        page.insert_text(
            baseline, value,
            fontname=font_name,
            fontsize=min(font_size, max(rect.height - 1, 4)),
            rotate=rotation,
        )
    except Exception:
        pass  # 极端情况下放弃该字段，不影响其余字段


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
    count = get_page_count(pdf_path)
    return [render_page_png(pdf_path, i, dpi) for i in range(count)]


def render_page_png(pdf_path: str, page_num: int = 0, dpi: int = 150) -> QPixmap:
    """通过 PNG 字节流渲染页面，避免 QImage stride 兼容问题"""
    import io
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    doc.close()
    # 转为 PNG 字节流再加载
    png_bytes = pix.tobytes("png")
    pixmap = QPixmap()
    pixmap.loadFromData(png_bytes)
    return pixmap


def page_point_to_screen(
    pdf_point: tuple[float, float], dpi: int = 150
) -> tuple[float, float]:
    """PDF 点坐标 → 屏幕像素坐标"""
    scale = dpi / 72.0
    return (pdf_point[0] * scale, pdf_point[1] * scale)


def screen_to_page_point(
    screen_point: tuple[float, float], dpi: int = 150
) -> tuple[float, float]:
    """屏幕像素坐标 → PDF 点坐标"""
    scale = 72.0 / dpi
    return (screen_point[0] * scale, screen_point[1] * scale)
