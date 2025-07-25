# annotation_tools.py
  
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPen, QColor, QPainterPath, QBrush
from PyQt5.QtWidgets import QGraphicsPathItem, QGraphicsItemGroup

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
        self.selected_arrow = None
        self.current_mode = "select"

    def add_point(self, pos):
        if not self.arrow_curved:
            if len(self.arrow_points) < 2:
                self.arrow_points.append(pos)
        else:
            self.arrow_points.append(pos)

    def set_mode(self, mode):
        self.arrow_curved = (mode == "curve")
        self.arrow_points = []
        self.remove_arrow_preview()
        self.clear_selection()
        self.current_mode = mode

    def set_color(self, color):
        if self.selected_arrow:
            if hasattr(self.selected_arrow, 'childItems'):
                for item in self.selected_arrow.childItems():
                    if hasattr(item, 'pen'):
                        pen = item.pen()
                        pen.setColor(QColor(color))
                        item.setPen(pen)
                    if hasattr(item, 'brush'):
                        brush = item.brush()
                        brush.setColor(QColor(color))
                        item.setBrush(brush)
            else:
                pen = self.selected_arrow.pen()
                pen.setColor(QColor(color))
                self.selected_arrow.setPen(pen)
        else:
            self.arrow_color = color

    def set_width(self, width):
        if self.selected_arrow:
            if hasattr(self.selected_arrow, 'childItems'):
                for item in self.selected_arrow.childItems():
                    if hasattr(item, 'pen') and not hasattr(item, 'brush'):
                        pen = item.pen()
                        pen.setWidth(width * 0.3)
                        item.setPen(pen)
            else:
                pen = self.selected_arrow.pen()
                pen.setWidth(width * 0.3)
                self.selected_arrow.setPen(pen)
        else:
            self.arrow_width = width

    def set_style(self, style):
        if self.selected_arrow:
            if hasattr(self.selected_arrow, 'childItems'):
                for item in self.selected_arrow.childItems():
                    if hasattr(item, 'pen') and not hasattr(item, 'brush'):
                        pen = item.pen()
                        pen.setStyle(Qt.SolidLine if style == "solid" else Qt.DashLine)
                        item.setPen(pen)
            else:
                pen = self.selected_arrow.pen()
                pen.setStyle(Qt.SolidLine if style == "solid" else Qt.DashLine)
                self.selected_arrow.setPen(pen)
        else:
            self.arrow_style = style

    def remove_arrow_preview(self):
        if self.arrow_preview:
            try:
                self.scene.removeItem(self.arrow_preview)
            except RuntimeError:
                pass
            self.arrow_preview = None

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
        arrow_item.setFlag(QGraphicsItemGroup.ItemIsSelectable, True)
        arrow_item.setFlag(QGraphicsItemGroup.ItemIsFocusable, True)
        arrow_item.setAcceptHoverEvents(True)
        arrow_item.setZValue(999)
        arrow_item.mousePressEvent = self.arrow_mouse_press_event(arrow_item)
        self.arrows.append(arrow_item)
        self.arrow_points = []
        self.remove_arrow_preview()

    def try_finish_arrow(self):
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
        for arrow in list(self.arrows):
            try:
                arrow.setSelected(False)
            except RuntimeError:
                self.arrows.remove(arrow)
        self.selected_arrow = None

    def cancel_arrow(self):
        self.arrow_points = []
        self.remove_arrow_preview()

    def create_zigzag_path(self, pts, is_curved=False):
        if len(pts) < 2:
            return QPainterPath()
        
        path = QPainterPath()
        
        if is_curved and len(pts) > 2:
            # Mode zigzag courbé : suit les points de la courbe
            path.moveTo(pts[0])
            
            # Créer la courbe de base
            total_length = 0
            segments = []
            for i in range(len(pts) - 1):
                dx = pts[i+1].x() - pts[i].x()
                dy = pts[i+1].y() - pts[i].y()
                seg_length = math.sqrt(dx*dx + dy*dy)
                segments.append((pts[i], pts[i+1], seg_length))
                total_length += seg_length
            
            # Créer des points le long de la courbe avec oscillation
            num_points = max(int(total_length / 2), 30)
            zigzag_points = [pts[0]]
            
            for i in range(1, num_points):
                t = i / num_points
                # Position sur la courbe originale
                curve_pos = self.get_point_on_curve(pts, t)
                
                # Oscillation perpendiculaire
                if i < num_points - 5:  # Arrêter l'oscillation avant la fin
                    direction = self.get_curve_direction(pts, t)
                    perp_x = -direction.y()
                    perp_y = direction.x()
                    oscillation = 1.2 * math.sin(t * 12 * math.pi)
                    curve_pos = QPointF(
                        curve_pos.x() + oscillation * perp_x,
                        curve_pos.y() + oscillation * perp_y
                    )
                
                zigzag_points.append(curve_pos)
            
            # Terminer en ligne droite
            zigzag_points.append(pts[-1])
            
            # Dessiner avec des courbes lisses
            for i in range(1, len(zigzag_points)):
                if i < len(zigzag_points) - 5:
                    mid = QPointF(
                        (zigzag_points[i].x() + zigzag_points[i+1].x()) / 2,
                        (zigzag_points[i].y() + zigzag_points[i+1].y()) / 2
                    ) if i < len(zigzag_points) - 1 else zigzag_points[i]
                    path.quadTo(zigzag_points[i], mid)
                else:
                    path.lineTo(zigzag_points[i])
                    
        else:
            # Mode zigzag droit
            start, end = pts[0], pts[-1]
            
            dx = end.x() - start.x()
            dy = end.y() - start.y()
            length = math.sqrt(dx*dx + dy*dy)
            
            if length == 0:
                path.moveTo(start)
                return path
            
            ux = dx / length
            uy = dy / length
            px = -uy
            py = ux
            
            path.moveTo(start)
            
            num_segments = max(int(length / 1), 30)
            control_points = []
            
            for i in range(1, num_segments + 1):
                t = i / num_segments
                base_x = start.x() + t * dx
                base_y = start.y() + t * dy
                
                # Arrêter l'oscillation avant la fin pour finir droit
                if t < 0.85:  # Arrêter l'oscillation à 85% du chemin
                    oscillation = 1.2 * math.sin(t * 12 * math.pi)
                    final_x = base_x + oscillation * px
                    final_y = base_y + oscillation * py
                else:
                    # Ligne droite pour la fin
                    final_x = base_x
                    final_y = base_y
                
                control_points.append(QPointF(final_x, final_y))
            
            if len(control_points) >= 2:
                # Dessiner avec des courbes jusqu'à la zone droite
                smooth_until = int(len(control_points) * 0.85)
                
                if smooth_until > 1:
                    path.quadTo(control_points[0], 
                               QPointF((control_points[0].x() + control_points[1].x()) / 2,
                                      (control_points[0].y() + control_points[1].y()) / 2))
                    
                    for i in range(1, min(smooth_until, len(control_points) - 1)):
                        mid_point = QPointF((control_points[i].x() + control_points[i+1].x()) / 2,
                                           (control_points[i].y() + control_points[i+1].y()) / 2)
                        path.quadTo(control_points[i], mid_point)
                
                # Finir en ligne droite
                for i in range(smooth_until, len(control_points)):
                    path.lineTo(control_points[i])
            else:
                path.lineTo(end)
        
        return path

    def get_point_on_curve(self, pts, t):
        """Obtient un point sur la courbe à la position t (0 à 1)"""
        if len(pts) == 2:
            # Ligne droite
            return QPointF(
                pts[0].x() + t * (pts[1].x() - pts[0].x()),
                pts[0].y() + t * (pts[1].y() - pts[0].y())
            )
        else:
            # Courbe multi-points (approximation)
            total_segments = len(pts) - 1
            segment_t = t * total_segments
            segment_idx = int(segment_t)
            local_t = segment_t - segment_idx
            
            if segment_idx >= total_segments:
                return pts[-1]
            
            return QPointF(
                pts[segment_idx].x() + local_t * (pts[segment_idx + 1].x() - pts[segment_idx].x()),
                pts[segment_idx].y() + local_t * (pts[segment_idx + 1].y() - pts[segment_idx].y())
            )

    def get_curve_direction(self, pts, t):
        """Obtient la direction de la courbe à la position t"""
        if len(pts) == 2:
            dx = pts[1].x() - pts[0].x()
            dy = pts[1].y() - pts[0].y()
            length = math.sqrt(dx*dx + dy*dy)
            if length > 0:
                return QPointF(dx/length, dy/length)
            return QPointF(1, 0)
        else:
            # Pour une courbe multi-points, approximer la direction
            p1 = self.get_point_on_curve(pts, max(0, t - 0.01))
            p2 = self.get_point_on_curve(pts, min(1, t + 0.01))
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            length = math.sqrt(dx*dx + dy*dy)
            if length > 0:
                return QPointF(dx/length, dy/length)
            return QPointF(1, 0)

    def draw_arrow_head_triangle(self, start, end, width_scale=1.0):
        dx, dy = end.x() - start.x(), end.y() - start.y()
        angle = math.atan2(dy, dx)
        
        # Taille directement proportionnelle à width_scale
        length = ANNOTATION_ARROW_HEAD_LENGTH * width_scale
        
        angle_rad = math.radians(ANNOTATION_ARROW_HEAD_ANGLE)
        angle1 = angle + angle_rad
        angle2 = angle - angle_rad
        
        p1 = QPointF(
            end.x() - length * math.cos(angle1),
            end.y() - length * math.sin(angle1)
        )
        p2 = QPointF(
            end.x() - length * math.cos(angle2),
            end.y() - length * math.sin(angle2)
        )
        
        # Triangle sans contour pour éviter le trait à la base
        path = QPainterPath()
        path.moveTo(end)
        path.lineTo(p1)
        path.lineTo(p2)
        path.closeSubpath()
        return path

    def draw_arrow(self, pts, preview=False):
        if len(pts) < 2:
            return None
        
        group = QGraphicsItemGroup()
        
        color = QColor(self.arrow_color)
        if preview:
            color.setAlphaF(0.5)
        else:
            color.setAlphaF(1.0)
        
        # Calculer la longueur de la tête pour raccourcir le corps
        width_scale = max(0.8, self.arrow_width * 0.2)
        head_length = ANNOTATION_ARROW_HEAD_LENGTH * width_scale
        
        # Corps de la flèche (raccourci)
        body_path = QPainterPath()
        
        if self.arrow_style == "zigzag":
            # Zigzag avec gestion des courbes - TOUJOURS en premier
            if self.arrow_curved:
                # Pour les courbes zigzag, utiliser tous les points
                body_path = self.create_zigzag_path(pts, self.arrow_curved)
            else:
                # Pour zigzag droit, raccourcir comme avant
                zigzag_pts = [pts[0]]
                start, end = pts[-2], pts[-1]
                dx, dy = end.x() - start.x(), end.y() - start.y()
                length = math.sqrt(dx*dx + dy*dy)
                if length > 0:
                    ratio = max(0, (length - head_length * 0.7) / length)
                    new_end = QPointF(start.x() + dx * ratio, start.y() + dy * ratio)
                    zigzag_pts.append(new_end)
                else:
                    zigzag_pts.append(end)
                body_path = self.create_zigzag_path(zigzag_pts, self.arrow_curved)
        elif self.arrow_curved and len(pts) > 2:
            # Mode courbe normale (pas zigzag)
            body_path.moveTo(pts[0])
            for i in range(1, len(pts)-1):
                mid = (pts[i] + pts[i+1]) * 0.5
                body_path.quadTo(pts[i], mid)
            # Raccourcir la fin
            start, end = pts[-2], pts[-1]
            dx, dy = end.x() - start.x(), end.y() - start.y()
            length = math.sqrt(dx*dx + dy*dy)
            if length > 0:
                ratio = max(0, (length - head_length * 0.7) / length)
                new_end = QPointF(start.x() + dx * ratio, start.y() + dy * ratio)
                body_path.lineTo(new_end)
            else:
                body_path.lineTo(end)
        else:
            # Mode normal (ligne droite)
            body_path.moveTo(pts[0])
            for i, p in enumerate(pts[1:], 1):
                if i == len(pts) - 1:  # Dernier point
                    start = pts[i-1]
                    dx, dy = p.x() - start.x(), p.y() - start.y()
                    length = math.sqrt(dx*dx + dy*dy)
                    if length > 0:
                        ratio = max(0, (length - head_length * 0.7) / length)
                        new_end = QPointF(start.x() + dx * ratio, start.y() + dy * ratio)
                        body_path.lineTo(new_end)
                    else:
                        body_path.lineTo(p)
                else:
                    body_path.lineTo(p)
        
        body_item = QGraphicsPathItem(body_path)
        pen = QPen(color, self.arrow_width * 0.3)
        
        if self.arrow_style == "dotted":
            pen.setStyle(Qt.DashLine)
        else:
            pen.setStyle(Qt.SolidLine)
        
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        body_item.setPen(pen)
        body_item.setBrush(QBrush(Qt.NoBrush))
        group.addToGroup(body_item)
        
        # Tête de flèche
        if len(pts) >= 2:
            start, end = pts[-2], pts[-1]
            head_path = self.draw_arrow_head_triangle(start, end, width_scale)
            
            head_item = QGraphicsPathItem(head_path)
            # Pas de contour pour avoir des bords nets
            head_item.setPen(QPen(Qt.NoPen))
            head_item.setBrush(QBrush(color))
            group.addToGroup(head_item)
        
        group.setZValue(999 if not preview else 998)
        group.arrow_points = list(pts)
        self.scene.addItem(group)
        
        return group

    def delete_last_arrow(self):
        if self.arrows:
            arrow_item = self.arrows.pop()
            try:
                self.scene.removeItem(arrow_item)
            except RuntimeError:
                pass
        self.clear_selection()