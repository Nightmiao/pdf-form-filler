"""字段图元 — 画布上可拖拽、旋转、缩放的矩形框

注意：FieldItem 内部持有的 FieldDefinition.rect 处于"显示坐标系"
（页面旋转时由 PdfCanvas 换算好再传入），其 rotation 也已包含页面旋转角。
画布在对外发射 field_created / field_modified 时会再换算回 PDF 坐标。
"""

from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsObject, QGraphicsEllipseItem,
    QGraphicsSceneMouseEvent, QStyleOptionGraphicsItem,
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QLineF
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont

from app.core.field_model import FieldDefinition
from app.ui.theme import COLORS

HANDLE_SIZE = 8

# 各字段类型在画布上的标签颜色
TYPE_COLORS = {
    "text": "#1D4ED8",
    "number": "#0E7490",
    "date": "#7C3AED",
    "select": "#B45309",
    "checkbox": "#047857",
}


class ResizeHandle(QGraphicsEllipseItem):
    """缩放/旋转手柄 — 独立的图形项用于更好的鼠标交互"""

    TopLeft = 0
    TopRight = 1
    BottomLeft = 2
    BottomRight = 3
    Rotate = 4

    def __init__(self, handle_type: int, parent=None):
        super().__init__(
            -HANDLE_SIZE / 2, -HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE, parent
        )
        self._handle_type = handle_type
        self.setZValue(200)

        if handle_type == self.Rotate:
            self.setPen(QPen(QColor(255, 140, 0), 2))
            self.setBrush(QBrush(QColor(255, 165, 0, 160)))
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setPen(QPen(QColor(0, 120, 255), 1.5))
            self.setBrush(QBrush(QColor(255, 255, 255)))
            cursors = {
                self.TopLeft: Qt.CursorShape.SizeFDiagCursor,
                self.TopRight: Qt.CursorShape.SizeBDiagCursor,
                self.BottomLeft: Qt.CursorShape.SizeBDiagCursor,
                self.BottomRight: Qt.CursorShape.SizeFDiagCursor,
            }
            self.setCursor(cursors.get(handle_type, Qt.CursorShape.SizeAllCursor))
        self.setAcceptHoverEvents(True)

    @property
    def handle_type(self) -> int:
        return self._handle_type


class FieldItem(QGraphicsObject):
    """画布上的可交互字段图元 — 手动处理所有交互"""

    field_changed = Signal(FieldDefinition)
    field_deleted = Signal(str)
    field_selected = Signal(str)
    interaction_started = Signal(str)  # 拖拽/缩放/旋转开始（供撤销快照）
    interaction_ended = Signal(str)    # 交互结束

    def __init__(self, field: FieldDefinition, scale: float, mode: str = "design"):
        super().__init__()
        self._field = field
        self._scale = scale
        self._selected: bool = False
        self._mode: str = mode
        self._fill_value: str = ""
        self._canvas = None

        self._active_handle: int | None = None
        self._handle_start_pos: QPointF | None = None
        self._handle_start_rect: tuple | None = None
        self._rotating: bool = False
        self._rotation_start: QPointF | None = None
        self._rotation_original: float = 0
        self._moving: bool = False
        self._move_start_pos: QPointF | None = None
        self._move_start_rect: tuple | None = None
        self._interacting: bool = False

        self._setup_handles()
        self._update_transform()

        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

    # ── 手柄 ──────────────────────────────────────

    def _setup_handles(self):
        self._handles: dict[int, ResizeHandle] = {}
        for htype in [
            ResizeHandle.TopLeft,
            ResizeHandle.TopRight,
            ResizeHandle.BottomLeft,
            ResizeHandle.BottomRight,
            ResizeHandle.Rotate,
        ]:
            handle = ResizeHandle(htype, self)
            handle.hide()
            self._handles[htype] = handle
        self._update_handle_positions()

    def _update_handle_positions(self):
        w, h = self._pdf_rect_to_pixel()
        positions = {
            ResizeHandle.TopLeft: (0, 0),
            ResizeHandle.TopRight: (w, 0),
            ResizeHandle.BottomLeft: (0, h),
            ResizeHandle.BottomRight: (w, h),
            ResizeHandle.Rotate: (w / 2, -22),
        }
        for htype, (x, y) in positions.items():
            if htype in self._handles:
                self._handles[htype].setPos(x, y)

    # ── 外观 ──────────────────────────────────────

    def boundingRect(self) -> QRectF:
        w, h = self._pdf_rect_to_pixel()
        return QRectF(-14, -36, w + 28, h + 50)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        w, h = self._pdf_rect_to_pixel()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0, 0, w, h)

        primary = QColor(COLORS["primary"])
        if self._mode == "fill":
            # 填写模式：淡蓝底 + 深蓝框，输入内容直接显示在框内
            if self._selected:
                pen = QPen(primary, 2.5)
                brush = QBrush(QColor(primary.red(), primary.green(), primary.blue(), 40))
            else:
                pen = QPen(QColor(primary.red(), primary.green(), primary.blue(), 140), 1.5)
                brush = QBrush(QColor(primary.red(), primary.green(), primary.blue(), 18))
            painter.setPen(pen)
            painter.setBrush(brush)
            painter.drawRect(rect)

            painter.setPen(QPen(QColor(24, 51, 133)))
            # 场景坐标系是 150 DPI（SCALE = 150/72），字号必须按此比例换算，
            # 否则画布预览文字会比导出小约 36%，误导"会不会溢出框"的判断。
            font = QFont("Microsoft YaHei")
            font.setPixelSize(max(9, int(round(self._field.font_size * self._scale))))
            painter.setFont(font)
            align_map = {
                "left": Qt.AlignmentFlag.AlignLeft,
                "center": Qt.AlignmentFlag.AlignCenter,
                "right": Qt.AlignmentFlag.AlignRight,
            }
            align = align_map.get(self._field.alignment, Qt.AlignmentFlag.AlignLeft)
            if self._fill_value:
                painter.drawText(
                    QRectF(3, 2, max(w - 6, 4), max(h - 4, 4)),
                    align | Qt.AlignmentFlag.AlignVCenter,
                    self._fill_value,
                )
        else:
            # 设计模式：白色底 + 蓝框 + 字段名/类型标签
            if self._selected:
                pen = QPen(primary, 2.5)
                brush = QBrush(QColor(primary.red(), primary.green(), primary.blue(), 35))
            else:
                pen = QPen(QColor(primary.red(), primary.green(), primary.blue(), 170), 1.5)
                brush = QBrush(QColor(255, 255, 255, 60))
            painter.setPen(pen)
            painter.setBrush(brush)
            painter.drawRect(rect)

            type_color = TYPE_COLORS.get(self._field.field_type, "#1D4ED8")
            painter.setPen(QPen(QColor(30, 30, 30)))
            font = QFont("Microsoft YaHei", 9)
            painter.setFont(font)
            label = self._field.name
            if self._field.required:
                label += " *"
                painter.setPen(QPen(QColor(200, 0, 0)))
            painter.drawText(
                QRectF(4, 1, max(w - 8, 4), min(h, 18)),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label,
            )
            # 类型小徽标
            if h >= 22 and w >= 46:
                badge = f"[{self._field.display_type}]"
                painter.setPen(QPen(QColor(type_color)))
                fm = font
                fm.setPointSize(8)
                painter.setFont(fm)
                painter.drawText(
                    QRectF(4, min(h, 20) - 2, max(w - 8, 4), max(h - 20, 12)),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                    badge,
                )

        show = self._selected and self._mode == "design"
        for handle in self._handles.values():
            handle.setVisible(show)

    # ── 鼠标交互 ──────────────────────────────────

    def _find_handle_at(self, pos: QPointF) -> int | None:
        for htype, handle in self._handles.items():
            if handle.isVisible():
                hp = handle.pos()
                if (
                    abs(pos.x() - hp.x()) <= HANDLE_SIZE + 2
                    and abs(pos.y() - hp.y()) <= HANDLE_SIZE + 2
                ):
                    return htype
        return None

    def _is_on_rotate_handle(self, pos: QPointF) -> bool:
        h = self._handles.get(ResizeHandle.Rotate)
        if h and h.isVisible():
            hp = h.pos()
            return (
                abs(pos.x() - hp.x()) <= HANDLE_SIZE + 2
                and abs(pos.y() - hp.y()) <= HANDLE_SIZE + 2
            )
        return False

    def _begin_interaction(self):
        if not self._interacting:
            self._interacting = True
            self.interaction_started.emit(self._field.id)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton or self._mode != "design":
            super().mousePressEvent(event)
            return

        pos = event.pos()

        if self._is_on_rotate_handle(pos):
            self._begin_interaction()
            self._rotating = True
            self._rotation_start = event.scenePos()
            self._rotation_original = self._field.rotation
            event.accept()
            return

        handle_type = self._find_handle_at(pos)
        if handle_type is not None and handle_type != ResizeHandle.Rotate:
            self._begin_interaction()
            self._active_handle = handle_type
            self._handle_start_pos = event.scenePos()
            self._handle_start_rect = self._field.rect
            event.accept()
            return

        w, h = self._pdf_rect_to_pixel()
        if QRectF(0, 0, w, h).contains(pos):
            self._begin_interaction()
            self._moving = True
            self._move_start_pos = event.scenePos()
            self._move_start_rect = self._field.rect

        self._selected = True
        self.field_selected.emit(self._field.id)
        self.update()
        event.accept()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._mode != "design":
            super().mouseMoveEvent(event)
            return

        if self._rotating and self._rotation_start:
            w, h = self._pdf_rect_to_pixel()
            center = self.mapToScene(QRectF(0, 0, w, h).center())
            line1 = QLineF(center, self._rotation_start)
            line2 = QLineF(center, event.scenePos())
            angle_delta = line2.angleTo(line1)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                angle_delta = round(angle_delta / 15) * 15
            new_rot = (self._rotation_original + angle_delta) % 360
            if new_rot > 180:
                new_rot -= 360
            self._field.rotation = new_rot
            self._update_transform()
            self._update_handle_positions()
            self.update()
            self.field_changed.emit(self._field)
            event.accept()
            return

        if self._active_handle is not None and self._handle_start_pos:
            delta = event.scenePos() - self._handle_start_pos
            dx = delta.x() / self._scale
            dy = delta.y() / self._scale
            x0, y0, x1, y1 = self._handle_start_rect

            ht = self._active_handle
            if ht == ResizeHandle.TopLeft:
                nx0, ny0, nx1, ny1 = x0 + dx, y0 + dy, x1, y1
            elif ht == ResizeHandle.TopRight:
                nx0, ny0, nx1, ny1 = x0, y0 + dy, x1 + dx, y1
            elif ht == ResizeHandle.BottomLeft:
                nx0, ny0, nx1, ny1 = x0 + dx, y0, x1, y1 + dy
            else:
                nx0, ny0, nx1, ny1 = x0, y0, x1 + dx, y1 + dy

            if nx1 - nx0 >= 5 and ny1 - ny0 >= 5:
                self._field.rect = (nx0, ny0, nx1, ny1)
                if self._canvas is not None:
                    self._field.rect = self._canvas.snap_resize_pdf_rect(
                        self._field.id, self._field.rect
                    )

            self._update_transform()
            self._update_handle_positions()
            self.update()
            self.field_changed.emit(self._field)
            event.accept()
            return

        if self._moving and self._move_start_pos:
            delta = event.scenePos() - self._move_start_pos
            dx = delta.x() / self._scale
            dy = delta.y() / self._scale
            x0, y0, x1, y1 = self._move_start_rect
            self._field.rect = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
            self._apply_snap()
            self._update_transform()
            self._update_handle_positions()
            self.update()
            self.field_changed.emit(self._field)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        was_interacting = self._interacting
        self._active_handle = None
        self._handle_start_pos = None
        self._handle_start_rect = None
        self._rotating = False
        self._rotation_start = None
        self._moving = False
        self._move_start_pos = None
        self._move_start_rect = None
        self._interacting = False
        if self._canvas is not None:
            self._canvas._clear_guides()
        self._update_handle_positions()
        self.update()
        if was_interacting:
            self.interaction_ended.emit(self._field.id)
        super().mouseReleaseEvent(event)

    def hoverMoveEvent(self, event: QGraphicsSceneMouseEvent):
        pos = event.pos()
        if self._mode == "design" and self._selected:
            ht = self._find_handle_at(pos)
            if ht is not None:
                self.setCursor(self._handles[ht].cursor())
            elif self._is_on_rotate_handle(pos):
                self.setCursor(Qt.CursorShape.CrossCursor)
            elif QRectF(0, 0, *self._pdf_rect_to_pixel()).contains(pos):
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(
                Qt.CursorShape.PointingHandCursor
                if self._mode == "fill"
                else Qt.CursorShape.CrossCursor
            )
        super().hoverMoveEvent(event)

    # ── 状态 ──────────────────────────────────────

    def set_selected(self, selected: bool):
        self._selected = selected
        self.update()

    def set_fill_value(self, value: str):
        self._fill_value = value
        self.update()

    def set_canvas(self, canvas):
        self._canvas = canvas

    def _apply_snap(self):
        if self._canvas is not None:
            self._field.rect = self._canvas.snap_pdf_rect(
                self._field.id, self._field.rect
            )

    @property
    def field(self) -> FieldDefinition:
        return self._field

    def update_from_field(self, field: FieldDefinition):
        self._field = field
        self._update_transform()
        self._update_handle_positions()
        self.update()

    # ── 内部 ──────────────────────────────────────

    def _pdf_rect_to_pixel(self) -> tuple[float, float]:
        x0, y0, x1, y1 = self._field.rect
        return ((x1 - x0) * self._scale, (y1 - y0) * self._scale)

    def _update_transform(self):
        x0, y0 = self._field.rect[0], self._field.rect[1]
        self.setPos(x0 * self._scale, y0 * self._scale)
        w, h = self._pdf_rect_to_pixel()
        self.setTransformOriginPoint(w / 2, h / 2)
        self.setRotation(self._field.rotation)