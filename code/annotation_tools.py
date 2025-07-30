
# annotation_tools.py - Version corrigée avec problème largeur résolu

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
        self.tactical_mode = False

    def set_tactical_mode(self, enabled):
        self.tactical_mode = enabled

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

    def select_arrow(self, arrow):
        """Sélectionne une flèche spécifique"""
        self.clear_selection()
        self.selected_arrow = arrow
        if arrow:
            arrow.setSelected(True)
            # Mettre en évidence visuellement
    
    def set_color(self, color):
        if self.selected_arrow:
            self.selected_arrow.set_color(color)
        else:
            self.arrow_color = color

    def set_width(self, width):
        if self.selected_arrow:
            self.selected_arrow.set_width(width)
        else:
            self.arrow_width = width

    def set_style(self, style):
        if self.selected_arrow:
            self.selected_arrow.set_style(style)
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
        if arrow_item:
            self.arrows.append(arrow_item)
        self.arrow_points = []
        self.remove_arrow_preview()


    def try_finish_arrow(self):
        if len(self.arrow_points) >= 2:
            self.finish_arrow()
        else:
            self.cancel_arrow()

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
            path.moveTo(pts[0])
            
            total_length = 0
            segments = []
            for i in range(len(pts) - 1):
                dx = pts[i+1].x() - pts[i].x()
                dy = pts[i+1].y() - pts[i].y()
                seg_length = math.sqrt(dx*dx + dy*dy)
                segments.append((pts[i], pts[i+1], seg_length))
                total_length += seg_length
            
            num_points = max(int(total_length / 2), 30)
            zigzag_points = [pts[0]]
            
            for i in range(1, num_points):
                t = i / num_points
                curve_pos = self.get_point_on_curve(pts, t)
                
                if i < num_points - 5:
                    direction = self.get_curve_direction(pts, t)
                    perp_x = -direction.y()
                    perp_y = direction.x()
                    oscillation = 1.2 * math.sin(t * 12 * math.pi)
                    curve_pos = QPointF(
                        curve_pos.x() + oscillation * perp_x,
                        curve_pos.y() + oscillation * perp_y
                    )
                
                zigzag_points.append(curve_pos)
            
            zigzag_points.append(pts[-1])
            
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
                
                if t < 0.85:
                    oscillation = 1.2 * math.sin(t * 12 * math.pi)
                    final_x = base_x + oscillation * px
                    final_y = base_y + oscillation * py
                else:
                    final_x = base_x
                    final_y = base_y
                
                control_points.append(QPointF(final_x, final_y))
            
            if len(control_points) >= 2:
                smooth_until = int(len(control_points) * 0.85)
                
                if smooth_until > 1:
                    path.quadTo(control_points[0], 
                               QPointF((control_points[0].x() + control_points[1].x()) / 2,
                                      (control_points[0].y() + control_points[1].y()) / 2))
                    
                    for i in range(1, min(smooth_until, len(control_points) - 1)):
                        mid_point = QPointF((control_points[i].x() + control_points[i+1].x()) / 2,
                                           (control_points[i].y() + control_points[i+1].y()) / 2)
                        path.quadTo(control_points[i], mid_point)
                
                for i in range(smooth_until, len(control_points)):
                    path.lineTo(control_points[i])
            else:
                path.lineTo(end)
        
        return path

    def get_point_on_curve(self, pts, t):
        if len(pts) == 2:
            return QPointF(
                pts[0].x() + t * (pts[1].x() - pts[0].x()),
                pts[0].y() + t * (pts[1].y() - pts[0].y())
            )
        else:
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
        if len(pts) == 2:
            dx = pts[1].x() - pts[0].x()
            dy = pts[1].y() - pts[0].y()
            length = math.sqrt(dx*dx + dy*dy)
            if length > 0:
                return QPointF(dx/length, dy/length)
            return QPointF(1, 0)
        else:
            p1 = self.get_point_on_curve(pts, max(0, t - 0.01))
            p2 = self.get_point_on_curve(pts, min(1, t + 0.01))
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            length = math.sqrt(dx*dx + dy*dy)
            if length > 0:
                return QPointF(dx/length, dy/length)
            return QPointF(1, 0)

    def draw_arrow_head_triangle(self, start, end, width_scale=1.0, color=None):
        """Dessine la tête de flèche triangulaire avec la couleur spécifiée"""
        dx, dy = end.x() - start.x(), end.y() - start.y()
        angle = math.atan2(dy, dx)
        
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
        
        path = QPainterPath()
        path.moveTo(end)
        path.lineTo(p1)
        path.lineTo(p2)
        path.closeSubpath()
        return path

    def draw_arrow(self, pts, preview=False):
        if len(pts) < 2:
            return None
        # Note: preview ne gère ici que la transparence de couleur, le reste est le même
        color = self.arrow_color
        width = self.arrow_width
        style = self.arrow_style
        if preview:
            # On ajoute un alpha pour la preview (ex : transparence 0.5)
            col = QColor(color)
            col.setAlphaF(0.5)
            color = col.name(QColor.HexArgb)  # force alpha
        arrow = CustomArrowItem(
            arrow_points=pts,
            color=color,
            width=width,
            style=style
        )
        arrow.setZValue(999 if not preview else 998)
        self.scene.addItem(arrow)
        return arrow


    def delete_last_arrow(self):
        """Supprime la dernière flèche créée"""
        if self.arrows:
            arrow_item = self.arrows.pop()
            try:
                self.scene.removeItem(arrow_item)
            except RuntimeError:
                pass
        self.clear_selection()




class CustomArrowItem(QGraphicsItemGroup):
    """Flèche graphique avec attributs métier et méthode de rafraîchissement."""
    def __init__(self, arrow_points, color, width, style, parent=None):
        super().__init__(parent)
        self.arrow_points = list(arrow_points)
        self.arrow_color = color
        self.arrow_width = width
        self.arrow_style = style
        self.from_player = None
        self.to_player = None
        self.original_width = width
        self._body_item = None
        self._head_item = None
        self._draw_items()

    def _draw_items(self):
        # Supprimer anciens items du groupe
        for item in [self._body_item, self._head_item]:
            if item is not None:
                try:
                    self.removeFromGroup(item)
                    item.setParentItem(None)
                except Exception:
                    pass

        if len(self.arrow_points) < 2:
            return

        pts = self.arrow_points
        body_path = None

        # ---------- CORPS ----------
        if self.arrow_style == "zigzag":
            body_path = self._create_zigzag_path(pts)
        elif len(pts) > 2 and self.arrow_style == "solid" and self._is_curved():
            body_path = QPainterPath()
            body_path.moveTo(pts[0])
            for i in range(1, len(pts)-1):
                mid = QPointF((pts[i].x() + pts[i+1].x())/2, (pts[i].y() + pts[i+1].y())/2)
                body_path.quadTo(pts[i], mid)
            body_path.lineTo(pts[-1])
        else:
            body_path = QPainterPath()
            body_path.moveTo(pts[0])
            for p in pts[1:]:
                body_path.lineTo(p)

        # Coupe le dernier segment pour laisser la place à la tête
        start, end = pts[-2], pts[-1]
        dx, dy = end.x() - start.x(), end.y() - start.y()
        length = math.hypot(dx, dy)
        head_length = ANNOTATION_ARROW_HEAD_LENGTH * max(0.8, self.arrow_width * 0.2)
        if length > 0:
            ratio = max(0, (length - head_length * 0.7) / length)
            new_end = QPointF(start.x() + dx * ratio, start.y() + dy * ratio)
            # Pour zigzag, on garde le path tel quel car il gère déjà la troncature
            if self.arrow_style != "zigzag":
                body_path = self._truncate_path_end(body_path, new_end)

        self._body_item = QGraphicsPathItem(body_path)
        pen = QPen(QColor(self.arrow_color), self.arrow_width * 0.3)
        if self.arrow_style == "dotted":
            pen.setStyle(Qt.DashLine)
        else:
            pen.setStyle(Qt.SolidLine)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        self._body_item.setPen(pen)
        self._body_item.setBrush(QBrush(Qt.NoBrush))
        self.addToGroup(self._body_item)

        # ---------- HEAD ----------
        head_path = self._draw_arrow_head_triangle(start, end, head_length)
        self._head_item = QGraphicsPathItem(head_path)
        self._head_item.setPen(QPen(Qt.NoPen))
        self._head_item.setBrush(QBrush(QColor(self.arrow_color)))
        self.addToGroup(self._head_item)

    def _is_curved(self):
        """Détecte s'il faut interpréter la flèche comme courbe (au moins 3 pts)"""
        return len(self.arrow_points) > 2

    def _create_zigzag_path(self, pts):
        """Crée un chemin zigzag sinusoïdal segment par segment"""
        if len(pts) < 2:
            return QPainterPath()
        
        path = QPainterPath()
        
        if len(pts) > 2:  # Mode courbe avec plusieurs points
            path.moveTo(pts[0])
            
            # Traiter chaque segment individuellement
            for seg_idx in range(len(pts) - 1):
                start_pt = pts[seg_idx]
                end_pt = pts[seg_idx + 1]
                
                dx = end_pt.x() - start_pt.x()
                dy = end_pt.y() - start_pt.y()
                segment_length = math.sqrt(dx*dx + dy*dy)
                
                if segment_length == 0:
                    continue
                
                # Direction et perpendiculaire du segment (identique au cas pas curved)
                ux = dx / segment_length
                uy = dy / segment_length
                px = -uy  # vecteur perpendiculaire
                py = ux
                
                # Nombre de points pour ce segment (identique au cas pas curved)
                num_segments = max(int(segment_length / 1), 30)
                control_points = []
                
                # Déterminer si c'est le dernier segment
                is_last_segment = (seg_idx == len(pts) - 2)
                
                # EXACTEMENT LA MÊME LOGIQUE que le cas pas curved
                for i in range(1, num_segments + 1):
                    t = i / num_segments
                    base_x = start_pt.x() + t * dx
                    base_y = start_pt.y() + t * dy
                    
                    # Pour le dernier segment : 85% sinusoïde + 15% droit
                    # Pour les autres segments : 100% sinusoïde
                    if is_last_segment and t > 0.85:
                        # 15% finaux du dernier segment : ligne droite
                        final_x = base_x
                        final_y = base_y
                    else:
                        # Sinusoïde (identique au cas pas curved)
                        oscillation = 1.2 * math.sin(t * 12 * math.pi)
                        final_x = base_x + oscillation * px
                        final_y = base_y + oscillation * py
                    
                    control_points.append(QPointF(final_x, final_y))
                
                # EXACTEMENT LE MÊME LISSAGE que le cas pas curved
                if len(control_points) >= 2:
                    if is_last_segment:
                        # Pour le dernier segment : 85% lisse + 15% droit
                        smooth_until = int(len(control_points) * 0.85)
                    else:
                        # Pour les autres segments : 100% lisse
                        smooth_until = len(control_points)
                    
                    if smooth_until > 1:
                        # Premier point du segment
                        if len(control_points) > 1:
                            path.quadTo(control_points[0], 
                                       QPointF((control_points[0].x() + control_points[1].x()) / 2,
                                              (control_points[0].y() + control_points[1].y()) / 2))
                        
                        # Points intermédiaires avec lissage
                        for i in range(1, min(smooth_until, len(control_points) - 1)):
                            mid_point = QPointF((control_points[i].x() + control_points[i+1].x()) / 2,
                                               (control_points[i].y() + control_points[i+1].y()) / 2)
                            path.quadTo(control_points[i], mid_point)
                    
                    # Partie droite finale (seulement pour le dernier segment)
                    for i in range(smooth_until, len(control_points)):
                        path.lineTo(control_points[i])
                else:
                    # Fallback si pas assez de points
                    for point in control_points:
                        path.lineTo(point)
                    
        else:  # Mode segment simple (inchangé)
            start, end = pts[0], pts[-1]
            
            dx = end.x() - start.x()
            dy = end.y() - start.y()
            length = math.sqrt(dx*dx + dy*dy)
            
            if length == 0:
                path.moveTo(start)
                return path
            
            ux = dx / length
            uy = dy / length
            px = -uy  # vecteur perpendiculaire
            py = ux
            
            path.moveTo(start)
            
            num_segments = max(int(length / 1), 30)
            control_points = []
            
            for i in range(1, num_segments + 1):
                t = i / num_segments
                base_x = start.x() + t * dx
                base_y = start.y() + t * dy
                
                # Oscillation sinusoïdale sur 85% du tracé
                if t < 0.85:
                    oscillation = 1.2 * math.sin(t * 12 * math.pi)
                    final_x = base_x + oscillation * px
                    final_y = base_y + oscillation * py
                else:  # 15% finaux : ligne droite
                    final_x = base_x
                    final_y = base_y
                
                control_points.append(QPointF(final_x, final_y))
            
            # Dessiner avec courbes lisses pour la partie sinusoïdale
            if len(control_points) >= 2:
                smooth_until = int(len(control_points) * 0.85)
                
                if smooth_until > 1:
                    path.quadTo(control_points[0], 
                               QPointF((control_points[0].x() + control_points[1].x()) / 2,
                                      (control_points[0].y() + control_points[1].y()) / 2))
                    
                    for i in range(1, min(smooth_until, len(control_points) - 1)):
                        mid_point = QPointF((control_points[i].x() + control_points[i+1].x()) / 2,
                                           (control_points[i].y() + control_points[i+1].y()) / 2)
                        path.quadTo(control_points[i], mid_point)
                
                # Partie droite finale
                for i in range(smooth_until, len(control_points)):
                    path.lineTo(control_points[i])
            else:
                path.lineTo(end)
        
        return path

    def _get_point_on_curve(self, pts, t):
        """Obtient un point sur la courbe multi-segments à la position t (0-1)"""
        if len(pts) == 2:
            return QPointF(
                pts[0].x() + t * (pts[1].x() - pts[0].x()),
                pts[0].y() + t * (pts[1].y() - pts[0].y())
            )
        else:
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

    def _get_curve_direction(self, pts, t):
        """Obtient la direction de la courbe au point t"""
        if len(pts) == 2:
            dx = pts[1].x() - pts[0].x()
            dy = pts[1].y() - pts[0].y()
            length = math.sqrt(dx*dx + dy*dy)
            if length > 0:
                return QPointF(dx/length, dy/length)
            return QPointF(1, 0)
        else:
            p1 = self._get_point_on_curve(pts, max(0, t - 0.01))
            p2 = self._get_point_on_curve(pts, min(1, t + 0.01))
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            length = math.sqrt(dx*dx + dy*dy)
            if length > 0:
                return QPointF(dx/length, dy/length)
            return QPointF(1, 0)

    def _truncate_path_end(self, path, new_end):
        """Remplace le dernier point du path par new_end."""
        if path.isEmpty():
            return path
        polys = path.toSubpathPolygons()
        if not polys or len(polys[0]) < 2:
            return path
        poly = polys[0]
        poly[-1] = new_end
        new_path = QPainterPath()
        new_path.moveTo(poly[0])
        for pt in poly[1:]:
            new_path.lineTo(pt)
        return new_path

    def _draw_arrow_head_triangle(self, start, end, length):
        dx, dy = end.x() - start.x(), end.y() - start.y()
        angle = math.atan2(dy, dx)
        angle_rad = math.radians(ANNOTATION_ARROW_HEAD_ANGLE)
        angle1 = angle + angle_rad
        angle2 = angle - angle_rad
        p1 = QPointF(end.x() - length * math.cos(angle1), end.y() - length * math.sin(angle1))
        p2 = QPointF(end.x() - length * math.cos(angle2), end.y() - length * math.sin(angle2))
        path = QPainterPath()
        path.moveTo(end)
        path.lineTo(p1)
        path.lineTo(p2)
        path.closeSubpath()
        return path

    def set_color(self, color):
        self.arrow_color = color
        self.refresh_visual()

    def set_width(self, width):
        self.arrow_width = width
        self.refresh_visual()

    def set_style(self, style):
        self.arrow_style = style
        self.refresh_visual()

    def set_from_player(self, player_id):
        self.from_player = player_id

    def set_to_player(self, player_id):
        self.to_player = player_id

    def refresh_visual(self):
        self._draw_items()
        self.update()