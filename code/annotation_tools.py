# annotation_tools.py
  
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPen, QColor, QPainterPath
from PyQt5.QtWidgets import QGraphicsPathItem

import math

from config import *
DEFAULT_ARROW_COLOR = "#000000"



class ArrowAnnotationManager:
    def __init__(self, scene):
        self.scene = scene
        self.arrows = []
        self.arrow_points = []
        self.arrow_color = DEFAULT_ARROW_COLOR
        self.arrow_width = ANNOTATION_ARROW_BASE_WIDTH_VALUE
        self.arrow_style = "solid"
        self.arrow_curved = False
        self.arrow_preview = None
        self.active = False
        self.selected_arrow = None
        self.current_mode = "select"

    def add_point(self, pos):
        if not self.arrow_curved:
            if len(self.arrow_points) < 2:
                self.arrow_points.append(pos)
        else:
            self.arrow_points.append(pos)
    


    def set_mode(self, mode):
        self.active = (mode in ("arrow", "curve"))
        self.arrow_curved = (mode == "curve")
        self.arrow_points = []
        self.remove_arrow_preview()
        self.clear_selection()
        self.current_mode = mode


    def set_active(self, val: bool):
        self.active = val
        self.arrow_points = []
        self.remove_arrow_preview()
        if val:
            self.clear_selection()

    def set_color(self, color):
        if self.selected_arrow:
            pen = self.selected_arrow.pen()
            pen.setColor(QColor(color))
            self.selected_arrow.setPen(pen)
        else:
            self.arrow_color = color

    def set_width(self, width):
        if self.selected_arrow:
            pen = self.selected_arrow.pen()
            pen.setWidth(width)
            self.selected_arrow.setPen(pen)
        else:
            self.arrow_width = width

    def set_style(self, style):
        if self.selected_arrow:
            pen = self.selected_arrow.pen()
            if style == "solid":
                pen.setStyle(Qt.SolidLine)
            elif style == "dotted":
                pen.setStyle(Qt.DotLine)
            self.selected_arrow.setPen(pen)
        else:
            self.arrow_style = style

    def set_curved(self, curved):
        self.arrow_curved = curved
        # Si édition post, redessiner la flèche sélectionnée
        if self.selected_arrow:
            idx = self.arrows.index(self.selected_arrow)
            pts = self.selected_arrow.arrow_points if hasattr(self.selected_arrow, "arrow_points") else []
            if pts:
                self.scene.removeItem(self.selected_arrow)
                new_arrow = self.draw_arrow(pts, preview=False)
                self.arrows[idx] = new_arrow
                self.selected_arrow = new_arrow

    def remove_arrow_preview(self):
        if self.arrow_preview:
            try:
                self.scene.removeItem(self.arrow_preview)
            except RuntimeError:
                pass
            self.arrow_preview = None

    def start_arrow(self, pos):
        self.arrow_points = [pos]

    def update_preview(self, pos):
        if not self.arrow_points:
            return
        if not self.arrow_curved:
            pts = [self.arrow_points[0], pos]
        else:
            pts = self.arrow_points + [pos]
        self.remove_arrow_preview()
        self.arrow_preview = self.draw_arrow(pts, preview=True)



    def finish_arrow(self):
        if len(self.arrow_points) < 2:
            self.arrow_points = []
            self.remove_arrow_preview()
            return
        arrow_item = self.draw_arrow(self.arrow_points, preview=False)
        arrow_item.arrow_points = list(self.arrow_points)
        arrow_item.setFlag(QGraphicsPathItem.ItemIsSelectable, True)
        arrow_item.setFlag(QGraphicsPathItem.ItemIsFocusable, True)
        arrow_item.setAcceptHoverEvents(True)
        arrow_item.setZValue(999)
        arrow_item.mousePressEvent = self.arrow_mouse_press_event(arrow_item)
        self.arrows.append(arrow_item)
        self.arrow_points = []
        self.remove_arrow_preview()

    def try_finish_arrow(self):
        """
        Termine la flèche en cours si au moins 2 points (pour toute flèche/courbe).
        Sinon, annule l'annotation.
        """
        if len(self.arrow_points) >= 2:
            self.finish_arrow()
        else:
            self.cancel_arrow()

    def arrow_mouse_press_event(self, arrow_item):
        def handler(event):
            if event.button() == Qt.LeftButton:
                self.clear_selection()
                arrow_item.setSelected(True)
                self.selected_arrow = arrow_item
        return handler

    def clear_selection(self):
        # On ne tente de setSelected que si l'item n'a pas été détruit par Qt.
        for arrow in list(self.arrows):
            try:
                arrow.setSelected(False)
            except RuntimeError:
                # Si jamais un arrow a été supprimé par erreur, on l'enlève de la liste
                self.arrows.remove(arrow)
        self.selected_arrow = None

    def cancel_arrow(self):
        self.arrow_points = []
        self.remove_arrow_preview()

    def draw_arrow_head_triangle(self, path, start, end, arrow_head_length=ANNOTATION_ARROW_HEAD_LENGTH, arrow_head_angle_deg=ANNOTATION_ARROW_HEAD_ANGLE):
        """
        Ajoute un triangle de tête de flèche à un QPainterPath.
        - path : QPainterPath déjà construit jusqu'à end
        - start, end : QPointF
        - arrow_width : largeur du trait principal
        - arrow_head_length : longueur du triangle
        - arrow_head_angle_deg : demi-angle à la base du triangle
        """
        dx, dy = end.x() - start.x(), end.y() - start.y()
        angle = math.atan2(dy, dx)
        length = arrow_head_length
        angle1 = angle + math.radians(arrow_head_angle_deg)
        angle2 = angle - math.radians(arrow_head_angle_deg)
        p1 = QPointF(
            end.x() - length * math.cos(angle1),
            end.y() - length * math.sin(angle1)
        )
        p2 = QPointF(
            end.x() - length * math.cos(angle2),
            end.y() - length * math.sin(angle2)
        )
        # Triangle plein
        path.moveTo(end)
        path.lineTo(p1)
        path.lineTo(p2)
        path.closeSubpath()
        return path

    def draw_arrow(self, pts, preview=False):
        path = QPainterPath()
        if self.arrow_curved and len(pts) > 2:
            path.moveTo(pts[0])
            for i in range(1, len(pts)-1):
                mid = (pts[i] + pts[i+1]) * 0.5
                path.quadTo(pts[i], mid)
            path.lineTo(pts[-1])
        elif self.arrow_style == "zigzag" and len(pts) > 2:
            path.moveTo(pts[0])
            for i, p in enumerate(pts[1:], 1):
                dz = QPointF(0, 8) if i % 2 == 0 else QPointF(0, -8)
                mid = (p + pts[i-1]) * 0.5 + dz
                path.lineTo(mid)
                path.lineTo(p)
        else:
            path.moveTo(pts[0])
            for p in pts[1:]:
                path.lineTo(p)
        # Flèche
        if len(pts) >= 2:
            start, end = pts[-2], pts[-1]
            path = self.draw_arrow_head_triangle(path, start, end)

        color = QColor(self.arrow_color)
        if preview:
            color.setAlphaF(0.5)  # Ghost effect
        else: color.setAlphaF(1.0)
        pen = QPen(color, self.arrow_width* 0.1)
        if self.arrow_style == "dotted":
            pen.setStyle(Qt.DotLine)
        elif self.arrow_style == "zigzag":
            pen.setStyle(Qt.SolidLine)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)

        item = QGraphicsPathItem(path)
        item.setPen(pen)
        item.setZValue(999 if not preview else 998)
        item.arrow_points = list(pts)
        
        self.scene.addItem(item)
        return item

    def delete_last_arrow(self):
        if self.arrows:
            arrow_item = self.arrows.pop()
            try:
                self.scene.removeItem(arrow_item)
            except RuntimeError:
                pass
        self.clear_selection()
