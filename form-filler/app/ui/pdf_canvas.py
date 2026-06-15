"""PDF 画布 — 基于 QGraphicsView 的 PDF 显示与交互组件"""

from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsItem,
    QGraphicsPixmapItem, QGraphicsLineItem, QMenu,
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QSizeF
from PySide6.QtGui import (
    QPixmap, QPainter, QPen, QColor, QBrush, QCursor,
    QTransform, QAction, QKeyEvent, QMouseEvent,
)

from app.core.pdf_engine import render_page
from app.core.field_model import FieldDefinition, PageSettings
from app.ui.field_item import FieldItem
from app.ui.alignment_overlay import AlignmentOverlay

# 渲染 DPI
DPI = 150
SCALE = DPI / 72.0  # PDF point → pixel


class PdfCanvas(QGraphicsView):
    """PDF 画布 — 支持设计模式和填写模式"""

    field_created = Signal(FieldDefinition)
    field_selected_sig = Signal(str)
    field_modified = Signal(FieldDefinition)
    field_deleted = Signal(str)
    current_page_changed = Signal(int)
    zoom_changed = Signal(int)  # 缩放百分比（如 100）

    MODE_DESIGN = "design"
    MODE_FILL = "fill"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = self.MODE_DESIGN
        self._scene = QGraphicsScene()
        self.setScene(self._scene)

        self._pdf_path: str = ""
        self._page_count: int = 1
        self._current_page: int = 0
        self._page_pixmaps: dict[int, QPixmap] = {}
        self._page_settings: list[PageSettings] = []

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

        # 右键状态（区分右键拖动平移 vs 右键单击菜单）
        self._rmb_pressed: bool = False
        self._rmb_moved: bool = False
        self._rmb_press_pos: QPointF | None = None
        # 右键拖动判定阈值（像素），小于此距离视为单击
        self._rmb_drag_threshold: int = 4

        # 当前选中的字段
        self._selected_field_item: FieldItem | None = None

        # 对齐辅助（网格吸附 + 对齐线）
        self._overlay = AlignmentOverlay()
        self._guide_items: list[QGraphicsLineItem] = []

        # 字段剪贴板（复制/粘贴）
        self._clipboard_field: FieldDefinition | None = None
        self._paste_count: int = 0

        # 缩放：_fit_scale 为 fitInView 后的基准缩放，_zoom 为用户缩放倍数
        self._fit_scale: float = 1.0
        self._zoom: float = 1.0

        # 视图设置
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setBackgroundBrush(QBrush(QColor(60, 60, 60)))
        self.setFrameShape(self.Shape.NoFrame)

        self.setMouseTracking(True)
        # 允许接收键盘事件
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
        from app.core.pdf_engine import get_page_count
        self._pdf_path = pdf_path
        self._page_count = get_page_count(pdf_path)
        self._page_settings = page_settings or [PageSettings() for _ in range(self._page_count)]
        self._page_pixmaps.clear()
        self._page_items = {}
        self._scene.clear()
        self._field_items.clear()
        self._render_page(0)
        self._current_page = 0

    def _render_page(self, page_num: int):
        if page_num in self._page_pixmaps:
            return
        rotation = 0.0
        if page_num < len(self._page_settings):
            rotation = self._page_settings[page_num].rotation
        pixmap = render_page(self._pdf_path, page_num, DPI, rotation)
        self._page_pixmaps[page_num] = pixmap

    def show_page(self, page_num: int):
        if page_num < 0 or page_num >= self._page_count:
            return
        self._render_page(page_num)
        # scene.clear() 会销毁所有图元的底层 C++ 对象，
        # 因此必须同步清空 _field_items，否则字典中会残留指向已删除对象的引用，
        # 后续 select_field / update_field 等遍历时会触发
        # RuntimeError: Internal C++ object already deleted。
        self._scene.clear()
        self._field_items.clear()
        self._selected_field_item = None
        pixmap = self._page_pixmaps[page_num]
        item = QGraphicsPixmapItem(pixmap)
        item.setZValue(-10)
        self._scene.addItem(item)
        self._page_items = {page_num: item}
        self._scene.setSceneRect(QRectF(0, 0, pixmap.width(), pixmap.height()))
        # 添加当前页字段
        for field in self._fields:
            if field.page == page_num:
                self._add_field_item(field)
        self._current_page = page_num
        self.current_page_changed.emit(page_num)
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        # 记录 fitInView 后的基准缩放，并按当前 zoom 倍数恢复
        self._fit_scale = self.transform().m11()
        if self._zoom != 1.0:
            self._apply_zoom()

    def _add_field_item(self, field: FieldDefinition):
        item = FieldItem(field, SCALE, self.mode)
        item.field_changed.connect(self._on_field_item_changed)
        item.field_deleted.connect(self._on_field_item_deleted)
        item.field_selected.connect(self._on_field_item_selected)
        item.set_canvas(self)
        self._scene.addItem(item)
        self._field_items[field.id] = item

    # ── 吸附与对齐线 ──────────────────────────────

    def set_snap_enabled(self, enabled: bool):
        """开关网格吸附"""
        self._overlay.snap_enabled = enabled

    def set_alignment_enabled(self, enabled: bool):
        """开关对齐线"""
        self._overlay.alignment_enabled = enabled
        if not enabled:
            self._clear_guides()

    def snap_pdf_rect(self, field_id: str, pdf_rect: tuple) -> tuple:
        """对拖拽/缩放中的字段做吸附，并显示对齐线。

        输入/输出都是 PDF 点坐标的 rect (x0,y0,x1,y1)。内部转换到像素坐标
        复用 AlignmentOverlay 的网格/对齐计算（其阈值以像素为单位）。
        """
        # PDF 点 → 像素
        px_rect = QRectF(
            QPointF(pdf_rect[0] * SCALE, pdf_rect[1] * SCALE),
            QPointF(pdf_rect[2] * SCALE, pdf_rect[3] * SCALE),
        ).normalized()

        # 1. 其他字段的像素矩形（同页、排除自己）
        other_rects = []
        for fid, item in self._field_items.items():
            if fid == field_id:
                continue
            f = item.field
            other_rects.append(QRectF(
                QPointF(f.rect[0] * SCALE, f.rect[1] * SCALE),
                QPointF(f.rect[2] * SCALE, f.rect[3] * SCALE),
            ).normalized())

        # 2. 对齐吸附：若某条边接近其他字段的边，则贴合过去（保持尺寸）
        snapped = self._snap_to_others(px_rect, other_rects)

        # 3. 网格吸附（左上角对齐网格，保持宽高）
        if self._overlay.snap_enabled:
            w, h = snapped.width(), snapped.height()
            tl = self._overlay.snap_to_grid(snapped.topLeft())
            snapped = QRectF(tl, QSizeF(w, h))

        # 4. 计算并显示对齐辅助线
        if self._overlay.alignment_enabled:
            lines = self._overlay.compute_alignment_lines(snapped, other_rects)
            self._show_guides(lines)
        else:
            self._clear_guides()

        # 像素 → PDF 点
        return (
            snapped.left() / SCALE, snapped.top() / SCALE,
            snapped.right() / SCALE, snapped.bottom() / SCALE,
        )

    def snap_resize_pdf_rect(self, field_id: str, pdf_rect: tuple) -> tuple:
        """缩放时的吸附：把矩形角分别吸附到网格（不保持尺寸），并显示对齐线。"""
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
            g = self._overlay.GRID_SIZE / SCALE  # 网格大小换算到 PDF 点
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
        """将 rect 的边吸附到邻近字段的对应边（在阈值内），保持原尺寸。"""
        if not self._overlay.alignment_enabled:
            return rect
        th = self._overlay.SNAP_THRESHOLD
        w, h = rect.width(), rect.height()
        x0, y0 = rect.left(), rect.top()
        best_dx = best_dy = None
        for other in other_rects:
            # 水平方向：左边/右边/中线
            for m, o in ((x0, other.left()), (x0 + w, other.right()),
                         (x0 + w / 2, other.center().x())):
                d = o - m
                if abs(d) < th and (best_dx is None or abs(d) < abs(best_dx)):
                    best_dx = d
            # 垂直方向：上边/下边/中线
            for m, o in ((y0, other.top()), (y0 + h, other.bottom()),
                         (y0 + h / 2, other.center().y())):
                d = o - m
                if abs(d) < th and (best_dy is None or abs(d) < abs(best_dy)):
                    best_dy = d
        if best_dx:
            x0 += best_dx
        if best_dy:
            y0 += best_dy
        return QRectF(QPointF(x0, y0), QSizeF(w, h))

    def _show_guides(self, lines: list):
        """绘制对齐辅助线"""
        self._clear_guides()
        pen = AlignmentOverlay.guide_line_pen()
        for line in lines:
            item = self._scene.addLine(line, pen)
            item.setZValue(150)
            self._guide_items.append(item)

    def _clear_guides(self):
        """清除所有对齐辅助线"""
        for item in self._guide_items:
            self._scene.removeItem(item)
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
        """根据 _fit_scale 和 _zoom 设置视图变换"""
        target = self._fit_scale * self._zoom
        t = QTransform()
        t.scale(target, target)
        self.setTransform(t)

    def set_zoom_percent(self, percent: int):
        """设置缩放百分比（50~300），由滑块调用"""
        self._zoom = max(0.1, percent / 100.0)
        self._apply_zoom()

    @property
    def zoom_percent(self) -> int:
        return int(round(self._zoom * 100))

    def zoom_in(self):
        """放大一档（Ctrl++）"""
        self._zoom = min(3.0, self._zoom * 1.15)
        self._apply_zoom()
        self.zoom_changed.emit(self.zoom_percent)

    def zoom_out(self):
        """缩小一档（Ctrl+-）"""
        self._zoom = max(0.5, self._zoom / 1.15)
        self._apply_zoom()
        self.zoom_changed.emit(self.zoom_percent)

    def zoom_fit(self):
        """适应窗口（Ctrl+0）"""
        self._zoom = 1.0  # _fit_scale 即适应窗口的基准
        self._apply_zoom()
        self.zoom_changed.emit(self.zoom_percent)

    def zoom_actual(self):
        """实际比例 100%（Ctrl+1）—— 渲染图按 1:1 像素显示（视图变换=1.0）"""
        if self._fit_scale > 0:
            # 最终变换 = _fit_scale * _zoom，要让它等于 1.0
            self._zoom = 1.0 / self._fit_scale
            self._apply_zoom()
            self.zoom_changed.emit(self.zoom_percent)

    # ── 字段操作 ──────────────────────────────────

    def load_fields(self, fields: list[FieldDefinition]):
        self._fields = fields[:]
        self._field_items.clear()
        if self._current_page < self._page_count:
            self.show_page(self._current_page)

    def add_field(self, field: FieldDefinition):
        self._fields.append(field)
        if field.page == self._current_page:
            self._add_field_item(field)

    def update_field(self, field: FieldDefinition):
        for i, f in enumerate(self._fields):
            if f.id == field.id:
                self._fields[i] = field
                break
        if field.id in self._field_items:
            self._field_items[field.id].update_from_field(field)

    def remove_field(self, field_id: str):
        self._fields = [f for f in self._fields if f.id != field_id]
        if field_id in self._field_items:
            item = self._field_items.pop(field_id)
            self._scene.removeItem(item)

    def select_field(self, field_id: str):
        for item in self._field_items.values():
            item.set_selected(False)
        if field_id in self._field_items:
            item = self._field_items[field_id]
            item.set_selected(True)
            self._selected_field_item = item
            self.centerOn(item)

    def focus_next_field(self):
        if self._mode != self.MODE_FILL:
            return
        current_fields = sorted(
            [f for f in self._fields if f.page == self._current_page],
            key=lambda f: f.tab_order,
        )
        if not current_fields:
            return
        if self._selected_field_item is None:
            fid = current_fields[0].id
        else:
            cur_id = self._selected_field_item.field.id
            indices = [i for i, f in enumerate(current_fields) if f.id == cur_id]
            next_idx = (indices[0] + 1) % len(current_fields) if indices else 0
            fid = current_fields[next_idx].id
        self.select_field(fid)
        self.field_selected_sig.emit(fid)

    def _delete_selected_field(self):
        """删除当前选中的字段"""
        if self._selected_field_item and self._mode == self.MODE_DESIGN:
            fid = self._selected_field_item.field.id
            self._on_field_item_deleted(fid)

    # ── 复制 / 粘贴 ───────────────────────────────

    def copy_selected_field(self):
        """复制当前选中的字段到剪贴板"""
        if self._mode != self.MODE_DESIGN or self._selected_field_item is None:
            return
        import copy
        self._clipboard_field = copy.deepcopy(self._selected_field_item.field)
        self._paste_count = 0

    def paste_field(self):
        """粘贴剪贴板中的字段到当前页（位置略微偏移，避免完全重叠）"""
        if self._mode != self.MODE_DESIGN or self._clipboard_field is None:
            return
        import copy
        import uuid
        new_field = copy.deepcopy(self._clipboard_field)
        # 生成新 id，避免与源字段冲突
        new_field.id = uuid.uuid4().hex[:12]
        # 每次粘贴递增偏移（PDF 点）
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
        """原地复制选中字段（Ctrl+D）—— 复制+粘贴一步完成"""
        if self._mode != self.MODE_DESIGN or self._selected_field_item is None:
            return
        self.copy_selected_field()
        self.paste_field()

    def nudge_selected_field(self, dx: float, dy: float):
        """用方向键微移选中字段（dx/dy 单位为 PDF 点）"""
        if self._mode != self.MODE_DESIGN or self._selected_field_item is None:
            return
        item = self._selected_field_item
        x0, y0, x1, y1 = item.field.rect
        item.field.rect = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        item.update_from_field(item.field)
        self.field_modified.emit(item.field)

    # ── 鼠标事件 ──────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        # 右键 → 可能是平移（拖动）或弹出菜单（单击）。
        # 先记录起点，松手时根据是否移动过来区分。
        if event.button() == Qt.MouseButton.RightButton:
            self._rmb_pressed = True
            self._rmb_moved = False
            self._pan_start = event.pos()
            self._rmb_press_pos = event.pos()
            return

        # 中键 → 平移（保留，兼容习惯）
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            items = self._scene.items(scene_pos)
            # 注意：场景中包含 FieldItem 及其子 Handle，判断时排除 Handle 只找 FieldItem
            field_items = [it for it in items if isinstance(it, FieldItem)]

            if self._mode == self.MODE_DESIGN:
                # 空格+左键 → 平移
                if self._space_held:
                    self._panning = True
                    self._pan_start = event.pos()
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                    return

                if field_items:
                    # 点击字段 → 选中它，然后传给 scene 让 FieldItem 自行处理
                    self.select_field(field_items[0].field.id)
                    self.field_selected_sig.emit(field_items[0].field.id)
                    super().mousePressEvent(event)  # 分发给 scene → FieldItem
                    return

                # 点击空白 → 开始画框
                self._drawing = True
                self._draw_start = scene_pos
                self._draw_rect = QGraphicsRectItem(QRectF(scene_pos, QSizeF(0, 0)))
                self._draw_rect.setPen(QPen(QColor(0, 120, 255), 2, Qt.PenStyle.DashLine))
                self._draw_rect.setBrush(QBrush(QColor(0, 120, 255, 30)))
                self._draw_rect.setZValue(100)
                self._scene.addItem(self._draw_rect)
                return

            elif self._mode == self.MODE_FILL:
                if field_items:
                    self.select_field(field_items[0].field.id)
                    self.field_selected_sig.emit(field_items[0].field.id)
                else:
                    # 填写模式空白区 → 平移
                    self._panning = True
                    self._pan_start = event.pos()
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        # 正在画框 → 自己处理，不发给 scene
        if self._drawing and self._draw_rect:
            scene_pos = self.mapToScene(event.pos())
            rect = QRectF(self._draw_start, scene_pos).normalized()
            self._draw_rect.setRect(rect)
            return

        # 右键按下并移动 → 平移画布
        if self._rmb_pressed and self._pan_start:
            if not self._rmb_moved:
                # 超过阈值才进入平移，避免单击时的轻微抖动被当成拖动
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

        # 正在平移 → 自己处理
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

        # 其他情况（字段拖拽/缩放/旋转）→ 分发给 scene → FieldItem
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        # 右键松开
        if event.button() == Qt.MouseButton.RightButton and self._rmb_pressed:
            was_drag = self._rmb_moved
            self._rmb_pressed = False
            self._rmb_moved = False
            self.setCursor(
                Qt.CursorShape.CrossCursor if self._mode == self.MODE_DESIGN
                else Qt.CursorShape.ArrowCursor
            )
            # 没有拖动 → 视为单击，弹出右键菜单（仅设计模式）
            if not was_drag and self._mode == self.MODE_DESIGN:
                scene_pos = self.mapToScene(event.pos())
                items = self._scene.items(scene_pos)
                field_items = [it for it in items if isinstance(it, FieldItem)]
                if field_items:
                    self.select_field(field_items[0].field.id)
                    self._show_context_menu(event.pos(), field_items[0].field.id)
            self._pan_start = None
            return

        # 结束画框
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
                    tab_order=len(self._fields),
                )
                self.add_field(field)
                self.field_created.emit(field)
                self.select_field(field.id)
                self.field_selected_sig.emit(field.id)
            return

        # 结束平移
        if self._panning:
            self._panning = False
            self._pan_start = None
            self.setCursor(
                Qt.CursorShape.CrossCursor if self._mode == self.MODE_DESIGN
                else Qt.CursorShape.ArrowCursor
            )
            return

        # 其他情况 → 分发给 scene → FieldItem
        super().mouseReleaseEvent(event)

    def _show_context_menu(self, viewport_pos, field_id: str):
        """右键菜单"""
        menu = QMenu(self)
        delete_action = menu.addAction("🗑️ 删除此字段")
        delete_action.triggered.connect(lambda: self._on_field_item_deleted(field_id))
        menu.exec_(self.mapToGlobal(viewport_pos))

    # ── 键盘事件 ──────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        mods = event.modifiers()
        ctrl = mods & Qt.KeyboardModifier.ControlModifier
        shift = mods & Qt.KeyboardModifier.ShiftModifier

        # ── 缩放快捷键（任意模式可用）──
        if ctrl:
            # Ctrl + 加号（主键盘 = / 小键盘 +）放大
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

        # ── 翻页（PageUp/PageDown）──
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

        # ── 设计模式专属 ──
        if self._mode == self.MODE_DESIGN:
            # Ctrl+C / Ctrl+V 复制粘贴字段
            if ctrl and key == Qt.Key.Key_C:
                self.copy_selected_field()
                event.accept()
                return
            if ctrl and key == Qt.Key.Key_V:
                self.paste_field()
                event.accept()
                return
            # Ctrl+D 原地复制
            if ctrl and key == Qt.Key.Key_D:
                self.duplicate_selected_field()
                event.accept()
                return

            # 方向键微移选中字段：1pt，按住 Shift 为 10pt
            arrow_map = {
                Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0),
                Qt.Key.Key_Up: (0, -1), Qt.Key.Key_Down: (0, 1),
            }
            if key in arrow_map and self._selected_field_item is not None:
                step = 10.0 if shift else 1.0
                ux, uy = arrow_map[key]
                self.nudge_selected_field(ux * step, uy * step)
                event.accept()
                return

        # Esc 取消画框 / 取消选中
        if key == Qt.Key.Key_Escape:
            if self._drawing and self._draw_rect:
                # 取消正在进行的画框
                self._scene.removeItem(self._draw_rect)
                self._draw_rect = None
                self._drawing = False
            elif self._selected_field_item is not None:
                self.select_field("")  # 取消所有选中
                self._selected_field_item = None
            event.accept()
            return

        # Delete 键删除
        if key == Qt.Key.Key_Delete or key == Qt.Key.Key_Backspace:
            if self._mode == self.MODE_DESIGN:
                self._delete_selected_field()
            event.accept()
            return

        # 空格键按下 = 准备平移模式
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
        super().keyReleaseEvent(event)

    # ── 滚轮 ──────────────────────────────────────

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        mods = event.modifiers()
        # Shift+滚轮 → 翻页（多页 PDF）
        if mods == Qt.KeyboardModifier.ShiftModifier:
            if delta > 0 and self._current_page > 0:
                self.set_current_page(self._current_page - 1)
            elif delta < 0 and self._current_page < self._page_count - 1:
                self.set_current_page(self._current_page + 1)
            return
        # 普通滚轮 / Ctrl+滚轮 → 缩放
        factor = 1.15 if delta > 0 else 1 / 1.15
        new_zoom = self._zoom * factor
        self._zoom = min(3.0, max(0.5, new_zoom))  # 限制 50%~300%
        self._apply_zoom()
        self.zoom_changed.emit(self.zoom_percent)  # 通知滑块同步

    # ── 回调 ──────────────────────────────────────

    def _on_field_item_changed(self, field: FieldDefinition):
        self.field_modified.emit(field)

    def _on_field_item_deleted(self, field_id: str):
        self.remove_field(field_id)
        self._selected_field_item = None
        self.field_deleted.emit(field_id)

    def _on_field_item_selected(self, field_id: str):
        for fid, item in self._field_items.items():
            item.set_selected(fid == field_id)
        if field_id in self._field_items:
            self._selected_field_item = self._field_items[field_id]
        self.field_selected_sig.emit(field_id)

    # ── 坐标 ──────────────────────────────────────

    def _screen_rect_to_pdf(self, screen_rect: QRectF) -> tuple:
        return (
            screen_rect.left() / SCALE,
            screen_rect.top() / SCALE,
            screen_rect.right() / SCALE,
            screen_rect.bottom() / SCALE,
        )

    def get_page_rotation(self, page_num: int) -> float:
        if page_num < len(self._page_settings):
            return self._page_settings[page_num].rotation
        return 0.0

    def set_page_rotation(self, page_num: int, rotation: float):
        if page_num < len(self._page_settings):
            self._page_settings[page_num].rotation = rotation
            self._page_pixmaps.pop(page_num, None)
            if page_num == self._current_page:
                self.show_page(page_num)

    def undo(self):
        pass

    def redo(self):
        pass
