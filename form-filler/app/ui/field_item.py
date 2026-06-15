"""字段图元 — 画布上可拖拽、旋转、缩放的矩形框"""

from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsObject, QGraphicsRectItem, QGraphicsEllipseItem,
    QGraphicsSceneMouseEvent, QStyleOptionGraphicsItem, QWidget,
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QLineF
from PySide6.QtGui import (
    QPainter, QPen, QColor, QBrush, QFont,
    QCursor,
)

from app.core.field_model import FieldDefinition

HANDLE_SIZE = 8


class ResizeHandle(QGraphicsEllipseItem):
    """缩放/旋转手柄 — 独立的图形项用于更好的鼠标交互"""

    TopLeft = 0
    TopRight = 1
    BottomLeft = 2
    BottomRight = 3
    Rotate = 4

    def __init__(self, handle_type: int, parent=None):
        super().__init__(-HANDLE_SIZE / 2, -HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE, parent)
        self._handle_type = handle_type
        self.setZValue(200)  # 确保在最上层

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
    """画布上的可交互字段图元 — 手动处理所有交互，避免 Qt 内置行为冲突"""

    field_changed = Signal(FieldDefinition)
    field_deleted = Signal(str)
    field_selected = Signal(str)

    def __init__(self, field: FieldDefinition, scale: float, mode: str = "design"):
        super().__init__()
        self._field = field
        self._scale = scale
        self._selected: bool = False
        self._mode: str = mode
        self._highlighted: bool = False
        self._fill_value: str = ""  # 填写模式下显示的值
        self._canvas = None  # 所属画布，用于吸附/对齐线（由 set_canvas 注入）

        # 交互状态
        self._active_handle: int | None = None  # 当前拖拽的手柄类型
        self._handle_start_pos: QPointF | None = None
        self._handle_start_rect: tuple | None = None
        self._rotating: bool = False
        self._rotation_start: QPointF | None = None
        self._rotation_original: float = 0
        self._moving: bool = False
        self._move_start_pos: QPointF | None = None
        self._move_start_rect: tuple | None = None

        self._setup_handles()
        self._update_transform()

        flags = QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        # 注意：不设 ItemIsMovable，手动处理移动
        self.setFlags(flags)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

    # ── 手柄 ──────────────────────────────────────

    def _setup_handles(self):
        self._handles: dict[int, ResizeHandle] = {}
        h = ResizeHandle
        for htype in [h.TopLeft, h.TopRight, h.BottomLeft, h.BottomRight, h.Rotate]:
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
        return QRectF(-12, -34, w + 24, h + 46)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        w, h = self._pdf_rect_to_pixel()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0, 0, w, h)
        if self._selected or self._highlighted:
            pen = QPen(QColor(0, 120, 255), 2.5)
            brush = QBrush(QColor(0, 120, 255, 35))
        else:
            pen = QPen(QColor(0, 120, 255, 170), 1.5)
            brush = QBrush(QColor(255, 255, 255, 50))

        painter.setPen(pen)
        painter.setBrush(brush)
        painter.drawRect(rect)

        # 填写模式下显示填写的值
        if self._mode == "fill" and self._fill_value:
            painter.setPen(QPen(QColor(0, 0, 180)))
            # 字号 = 字段设计字号，QFont 直接使用 pt 单位
            display_font_size = max(9, int(self._field.font_size))
            font = QFont("Microsoft YaHei", display_font_size)
            painter.setFont(font)
            align_map = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignCenter, "right": Qt.AlignmentFlag.AlignRight}
            align = align_map.get(self._field.alignment, Qt.AlignmentFlag.AlignLeft)
            painter.drawText(QRectF(2, 2, w - 4, h - 4), align | Qt.AlignmentFlag.AlignVCenter, self._fill_value)
        else:
            # 设计模式：显示字段名标签
            painter.setPen(QPen(QColor(30, 30, 30)))
            font = QFont("Microsoft YaHei", 9)
            painter.setFont(font)
            label = f"{self._field.name} [{self._field.display_type}]"
            if self._field.required:
                label += " *"
                painter.setPen(QPen(QColor(200, 0, 0)))
            painter.drawText(
                QRectF(3, 1, w - 6, min(h, 20)),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label,
            )

        # 手柄显隐
        show = self._selected and self._mode == "design"
        for handle in self._handles.values():
            handle.setVisible(show)

    # ── 鼠标交互 ──────────────────────────────────

    def _find_handle_at(self, pos: QPointF) -> int | None:
        """检查 pos 是否在手柄上，返回手柄类型或 None"""
        for htype, handle in self._handles.items():
            if handle.isVisible():
                hp = handle.pos()
                if abs(pos.x() - hp.x()) <= HANDLE_SIZE + 2 and abs(pos.y() - hp.y()) <= HANDLE_SIZE + 2:
                    return htype
        return None

    def _is_on_rotate_handle(self, pos: QPointF) -> bool:
        h = self._handles.get(ResizeHandle.Rotate)
        if h and h.isVisible():
            hp = h.pos()
            return abs(pos.x() - hp.x()) <= HANDLE_SIZE + 2 and abs(pos.y() - hp.y()) <= HANDLE_SIZE + 2
        return False

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton or self._mode != "design":
            super().mousePressEvent(event)
            return

        pos = event.pos()

        # 1. 先检查旋转手柄
        if self._is_on_rotate_handle(pos):
            self._rotating = True
            self._rotation_start = event.scenePos()
            self._rotation_original = self._field.rotation
            event.accept()
            return

        # 2. 检查缩放手柄
        handle_type = self._find_handle_at(pos)
        if handle_type is not None and handle_type != ResizeHandle.Rotate:
            self._active_handle = handle_type
            self._handle_start_pos = event.scenePos()
            self._handle_start_rect = self._field.rect
            event.accept()
            return

        # 3. 在字段本体上 → 移动 + 选中
        w, h = self._pdf_rect_to_pixel()
        if QRectF(0, 0, w, h).contains(pos):
            self._moving = True
            self._move_start_pos = event.scenePos()
            self._move_start_rect = self._field.rect

        # 通知选中
        self._selected = True
        self.field_selected.emit(self._field.id)
        self.update()
        event.accept()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._mode != "design":
            super().mouseMoveEvent(event)
            return

        # 旋转
        if self._rotating and self._rotation_start:
            center = self.mapToScene(
                QRectF(0, 0, self._pdf_rect_to_pixel()[0], self._pdf_rect_to_pixel()[1]).center()
            )
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

        # 缩放
        if self._active_handle is not None and self._handle_start_pos:
            delta = event.scenePos() - self._handle_start_pos
            dx = delta.x() / self._scale
            dy = delta.y() / self._scale
            x0, y0, x1, y1 = self._handle_start_rect

            ht = self._active_handle
            if ht == ResizeHandle.TopLeft:
                nx0, ny0 = x0 + dx, y0 + dy
                nx1, ny1 = x1, y1
            elif ht == ResizeHandle.TopRight:
                nx0, ny0 = x0, y0 + dy
                nx1, ny1 = x1 + dx, y1
            elif ht == ResizeHandle.BottomLeft:
                nx0, ny0 = x0 + dx, y0
                nx1, ny1 = x1, y1 + dy
            else:  # BottomRight
                nx0, ny0 = x0, y0
                nx1, ny1 = x1 + dx, y1 + dy

            # 保持最小尺寸
            if nx1 - nx0 >= 5 and ny1 - ny0 >= 5:
                self._field.rect = (nx0, ny0, nx1, ny1)
                # 缩放时的网格吸附 + 对齐线
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

        # 移动
        if self._moving and self._move_start_pos:
            delta = event.scenePos() - self._move_start_pos
            dx = delta.x() / self._scale
            dy = delta.y() / self._scale
            x0, y0, x1, y1 = self._move_start_rect
            self._field.rect = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
            self._apply_snap()  # 网格吸附 + 对齐线
            self._update_transform()
            self._update_handle_positions()
            self.update()
            self.field_changed.emit(self._field)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        # 清除所有交互状态
        self._active_handle = None
        self._handle_start_pos = None
        self._handle_start_rect = None
        self._rotating = False
        self._rotation_start = None
        self._moving = False
        self._move_start_pos = None
        self._move_start_rect = None
        # 拖拽结束 → 清除对齐辅助线
        if self._canvas is not None:
            self._canvas._clear_guides()
        self._update_handle_positions()
        self.update()
        super().mouseReleaseEvent(event)

    def hoverMoveEvent(self, event: QGraphicsSceneMouseEvent):
        # 检查手柄并改变光标
        pos = event.pos()
        if self._mode == "design" and self._selected:
            ht = self._find_handle_at(pos)
            if ht is not None:
                handle = self._handles[ht]
                self.setCursor(handle.cursor())
            elif self._is_on_rotate_handle(pos):
                self.setCursor(Qt.CursorShape.CrossCursor)
            elif QRectF(0, 0, *self._pdf_rect_to_pixel()).contains(pos):
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.PointingHandCursor if self._mode == "fill" else Qt.CursorShape.CrossCursor)
        super().hoverMoveEvent(event)

    # ── 选中 ──────────────────────────────────────

    def set_selected(self, selected: bool):
        self._selected = selected
        self.update()

    def set_fill_value(self, value: str):
        """设置填写模式下显示的值"""
        self._fill_value = value
        self.update()

    def set_canvas(self, canvas):
        """注入所属画布，用于网格吸附与对齐线"""
        self._canvas = canvas

    def _apply_snap(self):
        """把当前 rect 交给画布做吸附（移动时调用，保持尺寸）"""
        if self._canvas is not None:
            self._field.rect = self._canvas.snap_pdf_rect(self._field.id, self._field.rect)

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
