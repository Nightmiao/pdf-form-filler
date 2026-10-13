"""PDF 画布 — 基于 QGraphicsView 的 PDF 显示与交互组件

职责：
- 渲染 PDF 页面并显示页面旋转矫正（显示层旋转，不改变原始 PDF）；
- 在"设计模式"支持拖拽画框、移动/缩放/旋转字段、复制粘贴、对齐吸附；
- 在"填写模式"支持点击选中字段、Tab 跨页跳转；
- 维护撤销/重做栈（快照式）。

坐标系约定：
- 对外（信号、模板数据）一律使用"原始 PDF 点坐标"；
- 图元内部使用"显示坐标"（= PDF 坐标，页面旋转已折算进 rect/rotation），
  由 _field_to_display / _field_to_pdf 负责双向换算。
"""

from __future__ import annotations


import copy
import threading
import uuid
from collections import OrderedDict

from app.qt import (
    QtWidgets, QtCore, QtGui, Qt,
    ANCHOR_UNDER_MOUSE, NO_DRAG, FULL_VIEWPORT_UPDATE, SHAPE_NO_FRAME,
    KEEP_ASPECT, RENDER_ANTIALIASING, RENDER_SMOOTH_PIXMAP, menu_exec,
)

QGraphicsView = QtWidgets.QGraphicsView
QGraphicsScene = QtWidgets.QGraphicsScene
QGraphicsRectItem = QtWidgets.QGraphicsRectItem
QGraphicsPixmapItem = QtWidgets.QGraphicsPixmapItem
QGraphicsLineItem = QtWidgets.QGraphicsLineItem
QMenu = QtWidgets.QMenu
Signal = QtCore.Signal
QRectF = QtCore.QRectF
QPointF = QtCore.QPointF
QSizeF = QtCore.QSizeF
QTimer = QtCore.QTimer
QPixmap = QtGui.QPixmap
QPainter = QtGui.QPainter
QPen = QtGui.QPen
QColor = QtGui.QColor
QBrush = QtGui.QBrush
QTransform = QtGui.QTransform
QKeyEvent = QtGui.QKeyEvent
QMouseEvent = QtGui.QMouseEvent

from app.core.pdf_engine import (
    PdfSource, bytes_to_pixmap, rotate_point_cw, rotate_point_ccw,
    rotate_rect_about_center, rotate_rect_cw, rotate_rect_ccw, normalize_angle,
)
from app.core.field_model import FieldDefinition, PageSettings
from app.ui.field_item import FieldItem
from app.ui.alignment_overlay import AlignmentOverlay

# 渲染 DPI
DPI = 150
SCALE = DPI / 72.0  # PDF point → pixel

MAX_UNDO = 50
MAX_CACHED_PIXMAPS = 6  # 页面像素缓存上限（LRU）
ZOOM_MIN = 0.1          # 统一缩放限幅（原先四处不一致）
ZOOM_MAX = 6.0


class PdfCanvas(QGraphicsView):
    """PDF 画布 — 支持设计模式和填写模式"""

    field_created = Signal(FieldDefinition)
    field_selected_sig = Signal(str)
    field_modified = Signal(FieldDefinition)
    field_deleted = Signal(str)
    current_page_changed = Signal(int)
    zoom_changed = Signal(int)              # 缩放百分比（如 100）
    fields_restored = Signal(object)        # 撤销/重做后：完整字段列表
    undo_available = Signal(bool)
    redo_available = Signal(bool)

    MODE_DESIGN = "design"
    MODE_FILL = "fill"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = self.MODE_DESIGN
        self._scene = QGraphicsScene()
        self.setScene(self._scene)

        self._pdf_path: str = ""
        self._source: PdfSource | None = None
        self._page_count: int = 1
        self._current_page: int = 0
        self._page_pixmaps: "OrderedDict[int, QPixmap]" = OrderedDict()
        self._page_size_pdf: dict[int, tuple[float, float]] = {}
        self._failed_pages: set[int] = set()      # 渲染失败的页（保留重试机会）
        self._page_settings: list[PageSettings] = []
        self._render_jobs: dict[int, dict] = {}  # 后台渲染任务
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(60)
        self._render_timer.timeout.connect(self._collect_render_jobs)
        self._render_timer.start()
        self._pixmap_item: QGraphicsPixmapItem | None = None   # 当前页位图图元

        self._fields: list[FieldDefinition] = []
        self._field_items: dict[str, FieldItem] = {}

        # 拖拽创建新字段
        self._drawing: bool = False
        self._draw_start: QPointF | None = None
        self._draw_rect: QGraphicsRectItem | None = None

        # 平移状态
        self._panning: bool = False
        self._pan_start: QPointF | None = None
        self._space_held: bool = False

        # 右键状态（区分拖动平移 vs 单击菜单）
        self._rmb_pressed: bool = False
        self._rmb_moved: bool = False
        self._rmb_press_pos: QPointF | None = None
        self._rmb_drag_threshold: int = 4

        self._selected_field_item: FieldItem | None = None

        # 对齐辅助
        self._overlay = AlignmentOverlay()
        self._guide_items: list[QGraphicsLineItem] = []

        # 字段剪贴板
        self._clipboard_field: FieldDefinition | None = None
        self._paste_count: int = 0

        # 缩放
        self._fit_scale: float = 1.0
        self._zoom: float = 1.0

        # 撤销/重做
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._interaction_baseline: dict | None = None  # 拖拽开始时的快照
        self._nudge_baseline: dict | None = None        # 方向键手势开始时的快照
        self._prop_baseline_id: str | None = None       # 属性连续编辑合并

        self.setRenderHint(RENDER_ANTIALIASING)
        self.setRenderHint(RENDER_SMOOTH_PIXMAP)
        self.setDragMode(NO_DRAG)
        self.setTransformationAnchor(ANCHOR_UNDER_MOUSE)
        self.setResizeAnchor(ANCHOR_UNDER_MOUSE)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setViewportUpdateMode(FULL_VIEWPORT_UPDATE)
        self.setBackgroundBrush(QBrush(QColor(244, 246, 249)))
        self.setFrameShape(SHAPE_NO_FRAME)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ── 模式 ──────────────────────────────────────

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str):
        self._mode = mode
        cursors = {
            self.MODE_DESIGN: Qt.CursorShape.CrossCursor,
            self.MODE_FILL: Qt.CursorShape.ArrowCursor,
        }
        self.setCursor(cursors.get(mode, Qt.CursorShape.ArrowCursor))

    # ── 加载 ──────────────────────────────────────

    def load_pdf(self, pdf_path: str, page_settings: list[PageSettings] = None):
        if self._source is not None:
            self._source.close()
        self._pdf_path = pdf_path
        self._source = PdfSource(pdf_path)
        self._page_count = self._source.page_count
        self._page_settings = page_settings or [
            PageSettings() for _ in range(self._page_count)
        ]
        self._page_pixmaps.clear()
        self._page_size_pdf.clear()
        self._failed_pages.clear()
        self._render_jobs.clear()
        self._scene.clear()
        self._reset_scene_refs()
        self._field_items.clear()
        self._fields = []
        self._selected_field_item = None
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._emit_undo_state()
        self._ensure_page_pixmap(0)  # 首页同步渲染（仅一次）
        self._current_page = 0

    # ── 页面渲染与缓存 ─────────────────────────────

    def _cache_pixmap(self, page_num: int, pixmap: QPixmap):
        """写入缓存并做 LRU 淘汰"""
        self._page_pixmaps[page_num] = pixmap
        self._page_pixmaps.move_to_end(page_num)
        while len(self._page_pixmaps) > MAX_CACHED_PIXMAPS:
            oldest = next(iter(self._page_pixmaps))
            if oldest == self._current_page and len(self._page_pixmaps) > 1:
                # 优先保留当前页，淘汰第二旧的
                keys = list(self._page_pixmaps.keys())
                oldest = keys[1]
            self._page_pixmaps.pop(oldest, None)
        # _page_size_pdf 不随像素缓存淘汰：它是页面几何的权威值，与像素无关
        # 且数据极小，丢掉只会让坐标换算退化成 (0,0) 这种静默腐蚀型默认值。

    def _page_size_pdf_of(self, page_num: int) -> tuple[float, float]:
        """页面尺寸（PDF 点），**以 PDF 自身为准**，不从渲染位图反推。

        历史缺陷：页面尺寸曾由渲染出的位图反推（pixmap.width()/SCALE），
        而渲染失败时会伪造一张 100×140 的空白图，于是页面尺寸被写成
        48×67.2pt（A4 实为 595×842），所有绕页中心的换算（页面旋转、
        画框落点）全部算错，且因为进了缓存永不重试。
        """
        size = self._page_size_pdf.get(page_num)
        if size is None:
            size = (0.0, 0.0)
            if self._source is not None:
                try:
                    s = self._source.page_size(page_num)
                    size = (float(s.width()), float(s.height()))
                except Exception:
                    size = (0.0, 0.0)
            self._page_size_pdf[page_num] = size
        return size

    def _placeholder_pixmap(self, page_num: int) -> QPixmap:
        """渲染失败时的占位图：尺寸按**真实页面尺寸**造，保证坐标基准不被污染"""
        w, h = self._page_size_pdf_of(page_num)
        if w <= 0 or h <= 0:
            w, h = 595.0, 842.0
        pm = QPixmap(max(1, int(round(w * SCALE))), max(1, int(round(h * SCALE))))
        pm.fill(QColor(255, 255, 255))
        return pm

    def _ensure_page_pixmap(self, page_num: int):
        """确保"要显示的这一页"的像素已经在缓存里（同步渲染）。

        历史缺陷：这里曾经在"目标页既不在缓存、也不在 _render_jobs 中"时
        走后台预取分支并直接返回，而 show_page 紧接着无条件执行
        `self._page_pixmaps[page_num]` → KeyError。触发条件非常普通：
        多页表单上点一个隔了 2 页以上的缩略图（相邻页永远在预取里，所以
        2 页表单永远看不出来）。崩溃时 _scene 已被清空、_current_page 已经
        改号，画布会永久空白，且因为 set_current_page 的去重判断，重试无效。

        现在：要显示的页一律同步渲染；后台预取只服务于相邻页（见 show_page）。
        """
        if page_num in self._page_pixmaps and page_num not in self._failed_pages:
            return
        self._render_page_sync(page_num)

    def _render_page_sync(self, page_num: int):
        """同步渲染一页；失败时用真实尺寸的空白占位图，并记录以便下次重试"""
        if self._source is None:
            return
        pixmap = QPixmap()
        try:
            pixmap = bytes_to_pixmap(self._source.render_page_bytes(page_num, DPI))
        except Exception:
            pixmap = QPixmap()
        if pixmap.isNull():
            self._failed_pages.add(page_num)
            pixmap = self._placeholder_pixmap(page_num)
        else:
            self._failed_pages.discard(page_num)
        self._cache_pixmap(page_num, pixmap)
        self._page_size_pdf_of(page_num)   # 填充权威页面尺寸

    def _request_render(self, page_num: int):
        """后台渲染一页（用于相邻页预取）"""
        if self._source is None or page_num in self._page_pixmaps:
            return
        if page_num in self._render_jobs:
            return
        if not (0 <= page_num < self._page_count):
            return
        job = {"done": False, "bytes": None}
        self._render_jobs[page_num] = job
        source = self._source

        def worker():
            try:
                job["bytes"] = source.render_page_bytes(page_num, DPI)
            except Exception:
                job["bytes"] = b""
            job["done"] = True

        threading.Thread(target=worker, daemon=True).start()

    def _collect_render_jobs(self):
        """把后台渲染结果收进缓存（GUI 线程）"""
        finished = [p for p, j in self._render_jobs.items() if j["done"]]
        for page_num in finished:
            job = self._render_jobs.pop(page_num)
            pixmap = bytes_to_pixmap(job["bytes"] or b"")
            if pixmap.isNull():
                # 渲染失败：标记该页，让它下次显示时有机会重新渲染；
                # 绝不写入假像素，也不改页面尺寸。
                self._failed_pages.add(page_num)
                continue
            self._failed_pages.discard(page_num)
            self._cache_pixmap(page_num, pixmap)
            self._page_size_pdf_of(page_num)
            if page_num == self._current_page:
                self._update_page_display()

    def _reset_scene_refs(self):
        """_scene.clear() 之后必须清掉所有指向"已被销毁的 C++ 图元"的引用。

        历史缺陷：show_page / load_pdf / release_pdf 都调用 _scene.clear()，
        但没有清 _pixmap_item / _guide_items / _draw_rect。clear() 会销毁底层
        C++ 对象，而 Python 包装器仍被属性持有 —— 之后任何一次
        `self._pixmap_item.setXxx()` 都会抛
        RuntimeError: Internal C++ object already deleted
        （hasattr 判不出来，因为它判断的是 Python 属性是否存在）。
        """
        self._pixmap_item = None
        self._guide_items = []
        self._draw_rect = None
        self._draw_start = None
        self._drawing = False

    def release_pdf(self):
        """释放 PDF 资源（返回首页时调用，释放内存与渲染任务）"""
        self._render_jobs.clear()
        self._page_pixmaps.clear()
        self._page_size_pdf.clear()
        self._failed_pages.clear()
        self._scene.clear()
        self._reset_scene_refs()
        self._field_items.clear()
        self._selected_field_item = None
        if self._source is not None:
            self._source.close()
            self._source = None
        # 重置页面状态，防止散落调用 show_page 访问已释放的 source
        self._page_count = 0
        self._current_page = 0
        self._page_settings = []

    def closeEvent(self, event):
        self.release_pdf()
        super().closeEvent(event)

    def _current_page_rotation(self) -> float:
        if self._current_page < len(self._page_settings):
            return self._page_settings[self._current_page].rotation
        return 0.0

    def _page_center_pdf(self) -> tuple[float, float]:
        w, h = self._page_size_pdf_of(self._current_page)
        return (w / 2, h / 2)

    def show_page(self, page_num: int):
        if page_num < 0 or page_num >= self._page_count:
            return
        self._ensure_page_pixmap(page_num)
        pixmap = self._page_pixmaps.get(page_num)
        if pixmap is None or pixmap.isNull():
            # 兜底：无论如何都不能在这里让整页崩掉（历史上这里 KeyError）
            pixmap = self._placeholder_pixmap(page_num)
            self._cache_pixmap(page_num, pixmap)
        self._scene.clear()
        self._reset_scene_refs()
        self._field_items.clear()
        self._selected_field_item = None
        self._current_page = page_num

        self._pixmap_item = QGraphicsPixmapItem(pixmap)
        self._pixmap_item.setZValue(-10)
        self._scene.addItem(self._pixmap_item)
        self._update_page_display()

        for field in self._fields:
            if field.page == page_num:
                self._add_field_item(field)

        self.current_page_changed.emit(page_num)
        self.fitInView(self._scene.sceneRect(), KEEP_ASPECT)
        self._fit_scale = self.transform().m11()
        if self._zoom != 1.0:
            self._apply_zoom()

        # 后台预取相邻页
        self._request_render(page_num - 1)
        self._request_render(page_num + 1)

    def _update_page_display(self):
        """应用页面旋转：旋转图片图元并放大场景范围，避免旋转后被裁掉"""
        if self._pixmap_item is None:
            return
        rot = self._current_page_rotation()
        pixmap = self._page_pixmaps.get(self._current_page)
        if pixmap is None or pixmap.isNull():
            return
        self._pixmap_item.setTransformOriginPoint(pixmap.width() / 2, pixmap.height() / 2)
        self._pixmap_item.setRotation(rot)

        # 场景范围 = 旋转后页面外接矩形（场景坐标 = 像素坐标）
        w, h = pixmap.width(), pixmap.height()
        corners = [(0, 0), (w, 0), (w, h), (0, h)]
        rotated = [rotate_point_cw(x, y, w / 2, h / 2, rot) for x, y in corners]
        xs = [p[0] for p in rotated]
        ys = [p[1] for p in rotated]
        self._scene.setSceneRect(QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)))

    def _add_field_item(self, field: FieldDefinition):
        display_field = self._field_to_display(field)
        item = FieldItem(display_field, SCALE, self.mode)
        item.field_changed.connect(self._on_field_item_changed)
        item.field_deleted.connect(self._on_field_item_deleted)
        item.field_selected.connect(self._on_field_item_selected)
        item.interaction_started.connect(self._on_interaction_started)
        item.interaction_ended.connect(self._on_interaction_ended)
        item.set_canvas(self)
        self._scene.addItem(item)
        self._field_items[field.id] = item

    # ── 显示坐标 ↔ PDF 坐标 ───────────────────────

    def _field_to_display(self, field: FieldDefinition) -> FieldDefinition:
        """PDF 坐标字段 → 显示坐标字段。

        契约：页面矫正角只影响显示 —— 字段绕页面中心旋转 rot，**形状（宽高）
        保持不变**，字段自身角度 += rot。因此必须用 rotate_rect_about_center，
        不能用 rotate_rect_cw（后者会把宽高换成旋转后对角线的投影，见 pdf_engine
        中该函数的说明）。
        """
        rot = self._current_page_rotation()
        if rot == 0:
            return copy.deepcopy(field)
        d = copy.deepcopy(field)
        pcx, pcy = self._page_center_pdf()
        d.rect = rotate_rect_about_center(field.rect, pcx, pcy, rot)
        d.rotation = normalize_angle(field.rotation + rot)
        return d

    def _field_to_pdf(self, field: FieldDefinition) -> FieldDefinition:
        """显示坐标字段 → PDF 坐标字段（rotate_rect_about_center 的精确逆运算）"""
        rot = self._current_page_rotation()
        if rot == 0:
            return copy.deepcopy(field)
        d = copy.deepcopy(field)
        pcx, pcy = self._page_center_pdf()
        d.rect = rotate_rect_about_center(field.rect, pcx, pcy, -rot)
        d.rotation = normalize_angle(field.rotation - rot)
        return d

    def _new_field_rotation_for_page(self) -> float:
        """在矫正过的页面上新画一个"看起来水平"的框时，该字段应有的自身角度。

        显示角 = 字段自身角度 + 页面矫正角，要让屏幕上是水平的（显示角 0），
        字段自身角度就得是 -页面矫正角。这也正是 audit_verify C2 断言的语义。
        """
        return normalize_angle(-self._current_page_rotation())

    def _screen_rect_to_pdf(self, screen_rect: QRectF) -> tuple:
        """场景像素矩形 → PDF 坐标矩形（宽高不变，只把中心绕页中心回转）"""
        pdf_rect = (
            screen_rect.left() / SCALE,
            screen_rect.top() / SCALE,
            screen_rect.right() / SCALE,
            screen_rect.bottom() / SCALE,
        )
        rot = self._current_page_rotation()
        if rot != 0:
            pcx, pcy = self._page_center_pdf()
            pdf_rect = rotate_rect_about_center(pdf_rect, pcx, pcy, -rot)
        return pdf_rect

    # ── 吸附与对齐线 ──────────────────────────────

    def set_snap_enabled(self, enabled: bool):
        self._overlay.snap_enabled = enabled

    def set_alignment_enabled(self, enabled: bool):
        self._overlay.alignment_enabled = enabled
        if not enabled:
            self._clear_guides()

    def snap_pdf_rect(self, field_id: str, pdf_rect: tuple) -> tuple:
        """对拖拽中的字段做吸附并显示对齐线（显示坐标系内计算）"""
        px_rect = QRectF(
            QPointF(pdf_rect[0] * SCALE, pdf_rect[1] * SCALE),
            QPointF(pdf_rect[2] * SCALE, pdf_rect[3] * SCALE),
        ).normalized()

        other_rects = []
        for fid, item in self._field_items.items():
            if fid == field_id:
                continue
            f = item.field
            other_rects.append(QRectF(
                QPointF(f.rect[0] * SCALE, f.rect[1] * SCALE),
                QPointF(f.rect[2] * SCALE, f.rect[3] * SCALE),
            ).normalized())

        snapped = self._snap_to_others(px_rect, other_rects)

        if self._overlay.snap_enabled:
            w, h = snapped.width(), snapped.height()
            tl = self._overlay.snap_to_grid(snapped.topLeft())
            snapped = QRectF(tl, QSizeF(w, h))

        if self._overlay.alignment_enabled:
            self._show_guides(self._overlay.compute_alignment_lines(snapped, other_rects))
        else:
            self._clear_guides()

        return (
            snapped.left() / SCALE, snapped.top() / SCALE,
            snapped.right() / SCALE, snapped.bottom() / SCALE,
        )

    def snap_resize_pdf_rect(self, field_id: str, pdf_rect: tuple) -> tuple:
        """缩放时的吸附：四角分别吸附到网格，并显示对齐线"""
        other_rects = []
        for fid, item in self._field_items.items():
            if fid == field_id:
                continue
            f = item.field
            other_rects.append(QRectF(
                QPointF(f.rect[0] * SCALE, f.rect[1] * SCALE),
                QPointF(f.rect[2] * SCALE, f.rect[3] * SCALE),
            ).normalized())

        x0, y0, x1, y1 = pdf_rect
        if self._overlay.snap_enabled:
            g = self._overlay.GRID_SIZE / SCALE
            x0 = round(x0 / g) * g
            y0 = round(y0 / g) * g
            x1 = round(x1 / g) * g
            y1 = round(y1 / g) * g

        px_rect = QRectF(
            QPointF(x0 * SCALE, y0 * SCALE), QPointF(x1 * SCALE, y1 * SCALE)
        ).normalized()
        if self._overlay.alignment_enabled:
            self._show_guides(self._overlay.compute_alignment_lines(px_rect, other_rects))
        return (x0, y0, x1, y1)

    def _snap_to_others(self, rect: QRectF, other_rects: list) -> QRectF:
        if not self._overlay.alignment_enabled:
            return rect
        th = self._overlay.SNAP_THRESHOLD
        w, h = rect.width(), rect.height()
        x0, y0 = rect.left(), rect.top()
        best_dx = best_dy = None
        for other in other_rects:
            for m, o in (
                (x0, other.left()), (x0 + w, other.right()),
                (x0 + w / 2, other.center().x()),
            ):
                d = o - m
                if abs(d) < th and (best_dx is None or abs(d) < abs(best_dx)):
                    best_dx = d
            for m, o in (
                (y0, other.top()), (y0 + h, other.bottom()),
                (y0 + h / 2, other.center().y()),
            ):
                d = o - m
                if abs(d) < th and (best_dy is None or abs(d) < abs(best_dy)):
                    best_dy = d
        if best_dx:
            x0 += best_dx
        if best_dy:
            y0 += best_dy
        return QRectF(QPointF(x0, y0), QSizeF(w, h))

    def _show_guides(self, lines: list):
        self._clear_guides()
        pen = AlignmentOverlay.guide_line_pen()
        for line in lines:
            item = self._scene.addLine(line, pen)
            item.setZValue(150)
            self._guide_items.append(item)

    def _clear_guides(self):
        # _scene.clear() 会销毁图元，_reset_scene_refs 已把列表清空；
        # 这里再对残留项做一次安全移除（防止调用方绕过统一清理路径）。
        for item in list(self._guide_items):
            try:
                self._scene.removeItem(item)
            except RuntimeError:
                pass
        self._guide_items.clear()

    # ── 导航 ──────────────────────────────────────

    def set_current_page(self, page_num: int):
        if page_num != self._current_page:
            self.show_page(page_num)

    @property
    def current_page(self) -> int:
        return self._current_page

    @property
    def page_count(self) -> int:
        return self._page_count

    # ── 缩放 ──────────────────────────────────────

    def _apply_zoom(self):
        target = self._fit_scale * self._zoom
        t = QTransform()
        t.scale(target, target)
        self.setTransform(t)

    def _clamp_zoom(self, value: float) -> float:
        """统一的缩放限幅：四处各自为政（1.15 步进、3.0、0.5、0.1、无上限）
        曾导致"+ 键反而缩小""0.5 时按 − 无反应"这类死区。
        """
        return max(ZOOM_MIN, min(ZOOM_MAX, value))

    def _refit(self):
        """按当前视口重算"适应窗口"的基准比例 _fit_scale。

        zoom_fit / zoom_actual 都以 _fit_scale 为基准，而它只在 show_page 和
        （原先仅当 _zoom==1 时的）resizeEvent 里更新；窗口改变后再点"适应窗口"
        会用过期基准，页面不再适配。
        """
        rect = self._scene.sceneRect()
        if rect.isEmpty():
            return
        self.fitInView(rect, KEEP_ASPECT)
        fit = self.transform().m11()
        if fit > 0:
            self._fit_scale = fit

    def set_zoom_percent(self, percent: int):
        self._zoom = self._clamp_zoom(percent / 100.0)
        self._apply_zoom()
        self.zoom_changed.emit(self.zoom_percent)

    @property
    def zoom_percent(self) -> int:
        return int(round(self._zoom * 100))

    def zoom_in(self):
        self._zoom = self._clamp_zoom(self._zoom * 1.15)
        self._apply_zoom()
        self.zoom_changed.emit(self.zoom_percent)

    def zoom_out(self):
        self._zoom = self._clamp_zoom(self._zoom / 1.15)
        self._apply_zoom()
        self.zoom_changed.emit(self.zoom_percent)

    def zoom_fit(self):
        self._refit()          # 先按当前视口刷新基准，再回到 100% 基准
        self._zoom = 1.0
        self._apply_zoom()
        self.zoom_changed.emit(self.zoom_percent)

    def zoom_actual(self):
        self._refit()
        if self._fit_scale > 0:
            self._zoom = self._clamp_zoom(1.0 / self._fit_scale)
            self._apply_zoom()
            self.zoom_changed.emit(self.zoom_percent)

    # ── 撤销 / 重做 ───────────────────────────────

    def _snapshot(self) -> dict:
        return {
            "fields": copy.deepcopy(self._fields),
            "selected": (
                self._selected_field_item.field.id
                if self._selected_field_item is not None
                else ""
            ),
        }

    def _fields_equal(self, a: dict, b: dict) -> bool:
        fa = {f.id: (f.rect, f.rotation) for f in a["fields"]}
        fb = {f.id: (f.rect, f.rotation) for f in b["fields"]}
        return fa == fb

    def push_undo(self):
        self._undo_stack.append(self._snapshot())
        if len(self._undo_stack) > MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._emit_undo_state()

    def _emit_undo_state(self):
        self.undo_available.emit(bool(self._undo_stack))
        self.redo_available.emit(bool(self._redo_stack))

    def _reset_prop_baseline(self):
        self._prop_baseline_id = None

    def _apply_snapshot(self, snap: dict):
        self._fields = copy.deepcopy(snap["fields"])
        # 重建当前页图元
        for item in list(self._field_items.values()):
            self._scene.removeItem(item)
        self._field_items.clear()
        self._selected_field_item = None
        for field in self._fields:
            if field.page == self._current_page:
                self._add_field_item(field)
        sel = snap.get("selected", "")
        if sel in self._field_items:
            self.select_field(sel)
        self._reset_prop_baseline()
        self.fields_restored.emit(copy.deepcopy(self._fields))

    def undo(self):
        if not self._undo_stack:
            return
        current = self._snapshot()
        target = self._undo_stack.pop()
        self._redo_stack.append(current)
        self._apply_snapshot(target)
        self._emit_undo_state()

    def redo(self):
        if not self._redo_stack:
            return
        current = self._snapshot()
        target = self._redo_stack.pop()
        self._undo_stack.append(current)
        self._apply_snapshot(target)
        self._emit_undo_state()

    def _on_interaction_started(self, field_id: str):
        self._interaction_baseline = self._snapshot()

    def _on_interaction_ended(self, field_id: str):
        if self._interaction_baseline is not None:
            if not self._fields_equal(self._interaction_baseline, self._snapshot()):
                self._undo_stack.append(self._interaction_baseline)
                if len(self._undo_stack) > MAX_UNDO:
                    self._undo_stack.pop(0)
                self._redo_stack.clear()
                self._emit_undo_state()
        self._interaction_baseline = None

    # ── 字段操作 ──────────────────────────────────

    def load_fields(self, fields: list[FieldDefinition]):
        """重载字段列表（重排 Tab 顺序等），保持当前选中"""
        selected_id = (
            self._selected_field_item.field.id
            if self._selected_field_item is not None
            else ""
        )
        self._fields = copy.deepcopy(fields)
        self._field_items.clear()
        self._selected_field_item = None
        if self._current_page < self._page_count:
            self.show_page(self._current_page)
        if selected_id in self._field_items:
            self.select_field(selected_id)
        self._reset_prop_baseline()

    def add_field(self, field: FieldDefinition):
        self.push_undo()
        self._fields.append(copy.deepcopy(field))
        if field.page == self._current_page:
            self._add_field_item(field)

    def update_field(self, field: FieldDefinition):
        """右侧面板属性更新（PDF 坐标）"""
        for i, f in enumerate(self._fields):
            if f.id == field.id:
                if self._prop_baseline_id != field.id:
                    self.push_undo()
                    self._prop_baseline_id = field.id
                self._fields[i] = copy.deepcopy(field)
                break
        if field.id in self._field_items:
            self._field_items[field.id].update_from_field(self._field_to_display(field))

    def remove_field(self, field_id: str):
        self.push_undo()
        self._fields = [f for f in self._fields if f.id != field_id]
        if field_id in self._field_items:
            item = self._field_items.pop(field_id)
            self._scene.removeItem(item)
        if self._selected_field_item is not None and self._selected_field_item.field.id == field_id:
            self._selected_field_item = None

    def select_field(self, field_id: str, center: bool = True):
        """选中字段。

        center=True（面板/跨页定位等主动跳转）会把字段滚动到视口中央；
        鼠标按下路径必须传 center=False —— 否则 centerOn 会先滚动视图，
        紧接着 QGraphicsView 用**新的**变换把这次 press 映射到别处，
        FieldItem 收不到按下事件，表现为"点一下没反应、要再点一次"，
        填写模式下还会出现"每点一次页面就跳一下"。
        """
        for item in self._field_items.values():
            item.set_selected(False)
        self._selected_field_item = None
        if field_id and field_id in self._field_items:
            item = self._field_items[field_id]
            item.set_selected(True)
            self._selected_field_item = item
            if center:
                self.centerOn(item)
        elif not field_id:
            self.field_selected_sig.emit("")
        self._reset_prop_baseline()

    def select_field_on_page(self, field_id: str):
        """跨页选中字段：必要时先翻页。

        注意：这里**不能**补发 field_selected_sig。
        select_field 只在"清空选择"时发信号，非空选中不发射是刻意的：
        面板点选 → 本方法 → 若再发 field_selected_sig 会回到
        MainWindow._on_field_selected_in_design → 面板 _on_field_selected_in_list
        → field_focus_requested → 本方法，形成无限递归（实测直接栈溢出崩溃）。
        右面板高亮由 MainWindow._on_field_focus_requested 自己负责同步。
        """
        for f in self._fields:
            if f.id == field_id:
                if f.page != self._current_page:
                    self.show_page(f.page)
                self.select_field(field_id)
                return

    def _ordered_fields(self) -> list[FieldDefinition]:
        return sorted(self._fields, key=lambda f: (f.page, f.tab_order, f.name))

    def focus_next_field(self):
        """跳到下一个字段（跨页循环）"""
        ordered = self._ordered_fields()
        if not ordered:
            return
        if self._selected_field_item is None:
            target = ordered[0]
        else:
            cur_id = self._selected_field_item.field.id
            idx = next((i for i, f in enumerate(ordered) if f.id == cur_id), 0)
            target = ordered[(idx + 1) % len(ordered)]
        self.select_field_on_page(target.id)
        self.field_selected_sig.emit(target.id)

    def focus_prev_field(self):
        ordered = self._ordered_fields()
        if not ordered:
            return
        if self._selected_field_item is None:
            target = ordered[-1]
        else:
            cur_id = self._selected_field_item.field.id
            idx = next((i for i, f in enumerate(ordered) if f.id == cur_id), 0)
            target = ordered[(idx - 1) % len(ordered)]
        self.select_field_on_page(target.id)
        self.field_selected_sig.emit(target.id)

    def apply_fill_values(self, values: dict[str, str]):
        """把填写值同步到当前页所有字段图元的显示"""
        for field_id, item in self._field_items.items():
            item.set_fill_value(values.get(field_id, ""))

    def set_field_value(self, field_id: str, value: str):
        """设置单个字段图元的显示值（字段不在当前页时无操作）"""
        if field_id in self._field_items:
            self._field_items[field_id].set_fill_value(value)

    def _delete_selected_field(self):
        if self._selected_field_item and self._mode == self.MODE_DESIGN:
            fid = self._selected_field_item.field.id
            self._on_field_item_deleted(fid)

    # ── 复制 / 粘贴 ───────────────────────────────

    def copy_selected_field(self):
        if self._mode != self.MODE_DESIGN or self._selected_field_item is None:
            return
        item = self._selected_field_item
        self._clipboard_field = self._field_to_pdf(item.field)
        self._paste_count = 0

    def paste_field(self):
        if self._mode != self.MODE_DESIGN or self._clipboard_field is None:
            return
        new_field = copy.deepcopy(self._clipboard_field)
        new_field.id = uuid.uuid4().hex[:12]
        self._paste_count += 1
        offset = 10.0 * self._paste_count
        x0, y0, x1, y1 = new_field.rect
        new_field.rect = (x0 + offset, y0 + offset, x1 + offset, y1 + offset)
        new_field.page = self._current_page
        new_field.name = f"{new_field.name} 副本"
        new_field.tab_order = len(self._fields)
        self.add_field(new_field)
        self.field_created.emit(new_field)
        self.select_field(new_field.id)
        self.field_selected_sig.emit(new_field.id)

    def duplicate_selected_field(self):
        if self._mode != self.MODE_DESIGN or self._selected_field_item is None:
            return
        self.copy_selected_field()
        self.paste_field()

    def nudge_selected_field(self, dx: float, dy: float):
        """方向键微移。

        历史缺陷：每按一次都 push_undo()，而 Qt 的自动重复会以约 30 次/秒
        触发，一次长按就能把 MAX_UNDO(50) 条真实历史挤掉并清空 redo。
        现在改为"手势基线"模型：整个按下-松开过程只产生一条撤销记录，
        与拖拽/旋转的既有手势模型一致。
        """
        if self._mode != self.MODE_DESIGN or self._selected_field_item is None:
            return
        if self._nudge_baseline is None:
            self._nudge_baseline = self._snapshot()
        self._nudge_without_undo(dx, dy)

    def _nudge_without_undo(self, dx: float, dy: float):
        if self._selected_field_item is None:
            return
        item = self._selected_field_item
        x0, y0, x1, y1 = item.field.rect
        item.field.rect = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        item.update_from_field(item.field)
        self._sync_from_item(item)

    def _end_nudge(self):
        """方向键松开：把手势基线补进撤销栈（无实际位移则不入栈）"""
        if self._nudge_baseline is None:
            return
        if not self._fields_equal(self._nudge_baseline, self._snapshot()):
            self._undo_stack.append(self._nudge_baseline)
            if len(self._undo_stack) > MAX_UNDO:
                self._undo_stack.pop(0)
            self._redo_stack.clear()
            self._emit_undo_state()
        self._nudge_baseline = None

    # ── 鼠标事件 ──────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.RightButton:
            self._rmb_pressed = True
            self._rmb_moved = False
            self._pan_start = event.pos()
            self._rmb_press_pos = event.pos()
            return

        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            items = self._scene.items(scene_pos)
            field_items = [it for it in items if isinstance(it, FieldItem)]

            if self._mode == self.MODE_DESIGN:
                if self._space_held:
                    self._panning = True
                    self._pan_start = event.pos()
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                    return

                if field_items:
                    self.select_field(field_items[0].field.id, center=False)
                    self.field_selected_sig.emit(field_items[0].field.id)
                    super().mousePressEvent(event)
                    return

                self._drawing = True
                self._draw_start = scene_pos
                from app.ui.theme import COLORS
                self._draw_rect = QGraphicsRectItem(QRectF(scene_pos, QSizeF(0, 0)))
                self._draw_rect.setPen(QPen(QColor(COLORS["primary"]), 2, Qt.PenStyle.DashLine))
                self._draw_rect.setBrush(QBrush(QColor(59, 130, 246, 30)))
                self._draw_rect.setZValue(100)
                self._scene.addItem(self._draw_rect)
                return

            elif self._mode == self.MODE_FILL:
                if field_items:
                    self.setFocus(Qt.FocusReason.MouseFocusReason)
                    self.select_field(field_items[0].field.id, center=False)
                    self.field_selected_sig.emit(field_items[0].field.id)
                else:
                    self._panning = True
                    self._pan_start = event.pos()
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drawing and self._draw_rect:
            scene_pos = self.mapToScene(event.pos())
            rect = QRectF(self._draw_start, scene_pos).normalized()
            self._draw_rect.setRect(rect)
            return

        if self._rmb_pressed and self._pan_start:
            if not self._rmb_moved:
                moved = (event.pos() - self._rmb_press_pos).manhattanLength()
                if moved > self._rmb_drag_threshold:
                    self._rmb_moved = True
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
            if self._rmb_moved:
                delta = event.pos() - self._pan_start
                self._pan_start = event.pos()
                self.horizontalScrollBar().setValue(
                    self.horizontalScrollBar().value() - delta.x()
                )
                self.verticalScrollBar().setValue(
                    self.verticalScrollBar().value() - delta.y()
                )
            return

        if self._panning and self._pan_start:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.RightButton and self._rmb_pressed:
            was_drag = self._rmb_moved
            self._rmb_pressed = False
            self._rmb_moved = False
            self.setCursor(
                Qt.CursorShape.CrossCursor if self._mode == self.MODE_DESIGN
                else Qt.CursorShape.ArrowCursor
            )
            if not was_drag and self._mode == self.MODE_DESIGN:
                scene_pos = self.mapToScene(event.pos())
                items = self._scene.items(scene_pos)
                field_items = [it for it in items if isinstance(it, FieldItem)]
                if field_items:
                    self.select_field(field_items[0].field.id)
                    self._show_context_menu(event.pos(), field_items[0].field.id)
            self._pan_start = None
            return

        if self._drawing and self._draw_rect:
            self._drawing = False
            rect = self._draw_rect.rect()
            self._scene.removeItem(self._draw_rect)
            self._draw_rect = None
            if rect.width() >= 10 and rect.height() >= 10:
                pdf_rect = self._screen_rect_to_pdf(rect)
                field = FieldDefinition(
                    name=f"字段{len(self._fields) + 1}",
                    page=self._current_page,
                    rect=pdf_rect,
                    # 在矫正过的页面上新画的框，屏幕上必须是水平的：
                    # 显示角 = 自身角度 + 页面矫正角，故自身角度取 -矫正角。
                    rotation=self._new_field_rotation_for_page(),
                    tab_order=len(self._fields),
                )
                self.add_field(field)
                self.field_created.emit(field)
                self.select_field(field.id)
                self.field_selected_sig.emit(field.id)
            return

        if self._panning:
            self._panning = False
            self._pan_start = None
            self.setCursor(
                Qt.CursorShape.CrossCursor if self._mode == self.MODE_DESIGN
                else Qt.CursorShape.ArrowCursor
            )
            return

        super().mouseReleaseEvent(event)

    def _show_context_menu(self, viewport_pos, field_id: str):
        menu = QMenu(self)
        copy_action = menu.addAction("复制字段")
        delete_action = menu.addAction("删除字段")
        chosen = menu_exec(menu, self.mapToGlobal(viewport_pos))
        if chosen == copy_action:
            self.select_field(field_id)
            self.copy_selected_field()
        elif chosen == delete_action:
            self._on_field_item_deleted(field_id)

    # ── 键盘事件 ──────────────────────────────────

    def focusNextPrevChild(self, next_child: bool) -> bool:
        """接管 Tab / Shift+Tab。

        Qt 在 QWidget::event() 里对 Tab 会先调用本方法（窗口级焦点切换），
        返回 True 后就不会再走 keyPressEvent。填写模式下必须在这里切换
        表单字段，否则焦点会在整个窗口的控件之间乱跳。
        """
        if self._mode == self.MODE_FILL:
            if next_child:
                self.focus_next_field()
            else:
                self.focus_prev_field()
            return True
        return super().focusNextPrevChild(next_child)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        mods = event.modifiers()
        ctrl = mods & Qt.KeyboardModifier.ControlModifier
        shift = mods & Qt.KeyboardModifier.ShiftModifier

        if ctrl:
            if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self.zoom_in()
                event.accept()
                return
            if key == Qt.Key.Key_Minus:
                self.zoom_out()
                event.accept()
                return
            if key == Qt.Key.Key_0:
                self.zoom_fit()
                event.accept()
                return
            if key == Qt.Key.Key_1:
                self.zoom_actual()
                event.accept()
                return

        if key == Qt.Key.Key_PageUp:
            if self._current_page > 0:
                self.set_current_page(self._current_page - 1)
            event.accept()
            return
        if key == Qt.Key.Key_PageDown:
            if self._current_page < self._page_count - 1:
                self.set_current_page(self._current_page + 1)
            event.accept()
            return

        if self._mode == self.MODE_DESIGN:
            if ctrl and key == Qt.Key.Key_C:
                self.copy_selected_field()
                event.accept()
                return
            if ctrl and key == Qt.Key.Key_V:
                self.paste_field()
                event.accept()
                return
            if ctrl and key == Qt.Key.Key_D:
                self.duplicate_selected_field()
                event.accept()
                return

            arrow_map = {
                Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0),
                Qt.Key.Key_Up: (0, -1), Qt.Key.Key_Down: (0, 1),
            }
            if key in arrow_map and self._selected_field_item is not None:
                # 连按（含自动重复）只移动；整个"按下-松开"手势在松手时
                # 才由 _end_nudge 补一条撤销记录，避免 1 秒长按塞进 30 条。
                step = 10.0 if shift else 1.0
                ux, uy = arrow_map[key]
                self.nudge_selected_field(ux * step, uy * step)
                event.accept()
                return

        if self._mode == self.MODE_FILL:
            if key == Qt.Key.Key_Tab:
                if shift:
                    self.focus_prev_field()
                else:
                    self.focus_next_field()
                event.accept()
                return

        if key == Qt.Key.Key_Escape:
            if self._drawing and self._draw_rect:
                self._scene.removeItem(self._draw_rect)
                self._draw_rect = None
                self._drawing = False
            elif self._selected_field_item is not None:
                self.select_field("")
            event.accept()
            return

        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._mode == self.MODE_DESIGN:
                self._delete_selected_field()
            event.accept()
            return

        if key == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = True
            if self._mode == self.MODE_DESIGN:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = False
            if self._mode == self.MODE_DESIGN:
                self.setCursor(Qt.CursorShape.CrossCursor)
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right,
                           Qt.Key.Key_Up, Qt.Key.Key_Down):
            self._end_nudge()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def focusOutEvent(self, event):
        """失焦时把所有"按住类"状态复位。

        历史缺陷：按住空格进入平移态后 Alt+Tab / 弹出对话框，画布收不到
        keyRelease，_space_held 永久为真 —— 此后设计模式里所有左键拖拽都变成
        平移，再也画不出新字段框，而且光标卡在"手形"。_panning/_rmb_pressed
        同理。
        """
        self._space_held = False
        self._panning = False
        self._pan_start = None
        self._rmb_pressed = False
        self._rmb_moved = False
        self._rmb_press_pos = None
        self._end_nudge()
        if self._mode == self.MODE_DESIGN:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().focusOutEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 窗口尺寸变了就重算基准比例，并保持用户当前的缩放档位。
        # （原先只在 _zoom==1.0 时重算，导致"放大后改窗口→点适应窗口"用过期基准）
        if self._fit_scale > 0 and not self._scene.sceneRect().isEmpty():
            self._refit()
            self._apply_zoom()

    # ── 滚轮 ──────────────────────────────────────

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        mods = event.modifiers()
        # Shift+滚轮 → 翻页
        if mods == Qt.KeyboardModifier.ShiftModifier:
            if delta > 0 and self._current_page > 0:
                self.set_current_page(self._current_page - 1)
            elif delta < 0 and self._current_page < self._page_count - 1:
                self.set_current_page(self._current_page + 1)
            return
        # Ctrl+滚轮 → 缩放
        if mods == Qt.KeyboardModifier.ControlModifier:
            self._zoom_by_wheel(delta)
            return
        # 普通滚轮：页面放大超出视口时滚动（符合 PDF 阅读器习惯），否则缩放
        vbar = self.verticalScrollBar()
        hbar = self.horizontalScrollBar()
        if vbar.maximum() > 0:
            vbar.setValue(vbar.value() - delta)
        elif hbar.maximum() > 0:
            hbar.setValue(hbar.value() - delta)
        else:
            self._zoom_by_wheel(delta)

    def _zoom_by_wheel(self, delta: int):
        factor = 1.15 if delta > 0 else 1 / 1.15
        self._zoom = self._clamp_zoom(self._zoom * factor)
        self._apply_zoom()
        self.zoom_changed.emit(self.zoom_percent)

    # ── 回调 ──────────────────────────────────────

    def _sync_from_item(self, item: FieldItem):
        """把图元的显示坐标字段换算回 PDF 坐标，更新内部列表并对外发射"""
        pdf_field = self._field_to_pdf(item.field)
        for i, f in enumerate(self._fields):
            if f.id == pdf_field.id:
                self._fields[i] = pdf_field
                break
        self.field_modified.emit(pdf_field)

    def _on_field_item_changed(self, field: FieldDefinition):
        if field.id in self._field_items:
            self._sync_from_item(self._field_items[field.id])

    def _on_field_item_deleted(self, field_id: str):
        self.remove_field(field_id)
        self.field_deleted.emit(field_id)

    def _on_field_item_selected(self, field_id: str):
        for fid, item in self._field_items.items():
            item.set_selected(fid == field_id)
        if field_id in self._field_items:
            self._selected_field_item = self._field_items[field_id]
        self.field_selected_sig.emit(field_id)

    # ── 页面旋转 ──────────────────────────────────

    def get_page_rotation(self, page_num: int) -> float:
        if page_num < len(self._page_settings):
            return self._page_settings[page_num].rotation
        return 0.0

    def set_page_rotation(self, page_num: int, rotation: float):
        if page_num < len(self._page_settings):
            self._page_settings[page_num].rotation = rotation
            if page_num == self._current_page:
                self.show_page(page_num)