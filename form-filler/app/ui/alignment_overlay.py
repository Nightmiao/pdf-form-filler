"""对齐辅助 — 网格吸附和对齐线"""

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QPen, QColor


class AlignmentOverlay:
    """对齐辅助计算器 — 提供网格吸附和对齐线检测"""

    GRID_SIZE = 5.0  # 网格间距（像素）
    SNAP_THRESHOLD = 8.0  # 吸附阈值（像素）

    def __init__(self):
        self._snap_enabled: bool = True
        self._alignment_enabled: bool = True
        self._guide_lines: list[QLineF] = []

    @property
    def snap_enabled(self) -> bool:
        return self._snap_enabled

    @snap_enabled.setter
    def snap_enabled(self, value: bool):
        self._snap_enabled = value

    @property
    def alignment_enabled(self) -> bool:
        return self._alignment_enabled

    @alignment_enabled.setter
    def alignment_enabled(self, value: bool):
        self._alignment_enabled = value

    def snap_to_grid(self, pos: QPointF) -> QPointF:
        """将点吸附到最近网格点"""
        if not self._snap_enabled:
            return pos
        x = round(pos.x() / self.GRID_SIZE) * self.GRID_SIZE
        y = round(pos.y() / self.GRID_SIZE) * self.GRID_SIZE
        return QPointF(x, y)

    def snap_rect(self, rect: QRectF) -> QRectF:
        """将矩形吸附到网格"""
        if not self._snap_enabled:
            return rect
        top_left = self.snap_to_grid(rect.topLeft())
        bottom_right = self.snap_to_grid(rect.bottomRight())
        return QRectF(top_left, bottom_right)

    def compute_alignment_lines(
        self, moving_rect: QRectF, other_rects: list[QRectF]
    ) -> list[QLineF]:
        """计算对齐辅助线

        Args:
            moving_rect: 当前移动的矩形
            other_rects: 其他矩形的列表

        Returns:
            对齐线列表（品红色）
        """
        if not self._alignment_enabled:
            return []

        lines = []
        mx0, my0 = moving_rect.left(), moving_rect.top()
        mx1, my1 = moving_rect.right(), moving_rect.bottom()
        mx_c = moving_rect.center().x()
        my_c = moving_rect.center().y()

        for other in other_rects:
            if other == moving_rect:
                continue

            ox0, oy0 = other.left(), other.top()
            ox1, oy1 = other.right(), other.bottom()
            ox_c = other.center().x()
            oy_c = other.center().y()

            # 左对齐
            if abs(mx0 - ox0) < self.SNAP_THRESHOLD:
                lines.append(QLineF(QPointF(ox0, min(my0, oy0)), QPointF(ox0, max(my1, oy1))))
            # 右对齐
            if abs(mx1 - ox1) < self.SNAP_THRESHOLD:
                lines.append(QLineF(QPointF(ox1, min(my0, oy0)), QPointF(ox1, max(my1, oy1))))
            # 顶部对齐
            if abs(my0 - oy0) < self.SNAP_THRESHOLD:
                lines.append(QLineF(QPointF(min(mx0, ox0), oy0), QPointF(max(mx1, ox1), oy0)))
            # 底部对齐
            if abs(my1 - oy1) < self.SNAP_THRESHOLD:
                lines.append(QLineF(QPointF(min(mx0, ox0), oy1), QPointF(max(mx1, ox1), oy1)))
            # 水平中线对齐
            if abs(mx_c - ox_c) < self.SNAP_THRESHOLD:
                lines.append(QLineF(QPointF(ox_c, min(my0, oy0)), QPointF(ox_c, max(my1, oy1))))
            # 垂直中线对齐
            if abs(my_c - oy_c) < self.SNAP_THRESHOLD:
                lines.append(QLineF(QPointF(min(mx0, ox0), oy_c), QPointF(max(mx1, ox1), oy_c)))

        self._guide_lines = lines
        return lines

    @property
    def guide_lines(self) -> list[QLineF]:
        return self._guide_lines

    @staticmethod
    def guide_line_pen() -> QPen:
        """对齐线画笔 — 品红色虚线"""
        pen = QPen(QColor(255, 0, 255), 1)
        pen.setStyle(Qt.PenStyle.DashLine)
        return pen
