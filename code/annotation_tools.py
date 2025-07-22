from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPen, QColor, QPainterPath
from PyQt5.QtWidgets import QGraphicsPathItem
import math

class ArrowAnnotationManager:
    def __init__(self, scene):
        self.scene = scene
        self.arrows = []
        self.arrow_points = []
        self.arrow_color = "#2D5AC7"
        self.arrow_width = 3
        self.arrow_style = "solid"  # 'solid', 'dotted', 'zigzag'
        self.arrow_curved = False
        self.arrow_preview = None
        self.active = False

    def set_active(self, val: bool):
        self.active = val
        self.arrow_points = []
        self.remove_arrow_preview()

    def set_color(self, color):
        self.arrow_color = color

    def set_width(self, width):
        self.arrow_width = width

    def set_style(self, style):
        self.arrow_style = style

    def set_curved(self, curved):
        self.arrow_curved = curved

    def remove_arrow_preview(self):
        if self.arrow_preview:
            self.scene.removeItem(self.arrow_preview)
            self.arrow_preview = None

    def start_arrow(self, pos):
        self.arrow_points = [pos]

    def add_point(self, pos):
        self.arrow_points.append(pos)

    def update_preview(self, pos):
        if not self.arrow_points:
            return
        pts = self.arrow_points + [pos]
        self.remove_arrow_preview()
        self.arrow_preview = self.draw_arrow(pts, preview=True)

    def finish_arrow(self):
        if len(self.arrow_points) < 2:
            self.arrow_points = []
            self.remove_arrow_preview()
            return
        arrow_item = self.draw_arrow(self.arrow_points, preview=False)
        self.arrows.append(arrow_item)
        self.arrow_points = []
        self.remove_arrow_preview()

    def cancel_arrow(self):
        self.arrow_points = []
        self.remove_arrow_preview()

    def draw_arrow(self, pts, preview=False):
        path = QPainterPath()
        if self.arrow_curved and len(pts) > 2:
            # courbe de Bézier en passant par chaque point (approx)
            path.moveTo(pts[0])
            for i in range(1, len(pts)-1):
                mid = (pts[i] + pts[i+1]) * 0.5
                path.quadTo(pts[i], mid)
            path.lineTo(pts[-1])
        elif self.arrow_style == "zigzag" and len(pts) > 2:
            path.moveTo(pts[0])
            for i, p in enumerate(pts[1:], 1):
                if i % 2 == 0:
                    dz = QPointF(0, 8)  # zig
                else:
                    dz = QPointF(0, -8) # zag
                mid = (p + pts[i-1]) * 0.5 + dz
                path.lineTo(mid)
                path.lineTo(p)
        else:
            path.moveTo(pts[0])
            for p in pts[1:]:
                path.lineTo(p)

        # Tête de flèche
        if len(pts) >= 2:
            start, end = pts[-2], pts[-1]
            dx, dy = end.x() - start.x(), end.y() - start.y()
            angle = math.atan2(dy, dx)
            head_len = 10
            head_angle = math.radians(28)
            for da in [-head_angle, +head_angle]:
                x2 = end.x() - head_len * math.cos(angle + da)
                y2 = end.y() - head_len * math.sin(angle + da)
                path.moveTo(end)
                path.lineTo(QPointF(x2, y2))

        pen = QPen(QColor(self.arrow_color), self.arrow_width if not preview else 1.5)
        if self.arrow_style == "dotted":
            pen.setStyle(Qt.DotLine)
        elif self.arrow_style == "zigzag":
            pen.setStyle(Qt.SolidLine)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        if preview:
            pen.setColor(QColor(self.arrow_color).lighter(160))
        item = QGraphicsPathItem(path)
        item.setPen(pen)
        item.setZValue(999 if not preview else 998)
        self.scene.addItem(item)
        return item

    def delete_last_arrow(self):
        if self.arrows:
            arrow_item = self.arrows.pop()
            self.scene.removeItem(arrow_item)
