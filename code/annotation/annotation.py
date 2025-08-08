# annotation.py

from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPen, QColor, QPainterPath, QBrush
from PyQt5.QtWidgets import QGraphicsPathItem, QGraphicsItemGroup, QGraphicsRectItem, QStyleOptionGraphicsItem, QStyle

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


    def clear_selection(self):        
        for arrow in list(self.arrows):
            try:
                arrow.setSelected(False)
            except RuntimeError:
                self.arrows.remove(arrow)
        self.selected_arrow = None

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

    def cancel_arrow(self):
        self.arrow_points = []
        self.remove_arrow_preview()


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
    """Flèche graphique avec rectangle de sélection coordonné"""
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
        self._selection_rect = None
        self._selected_state = False

        # Configuration flags
        self.setFlag(QGraphicsItemGroup.ItemIsSelectable, True)
        self.setFlag(QGraphicsItemGroup.ItemIsMovable, True)
        self.setFlag(QGraphicsItemGroup.ItemSendsGeometryChanges, True)
        
        self._draw_items()
        self._create_selection_rect()

    def paint(self, painter, option, widget):
        """Override pour supprimer le carré blanc par défaut"""
        option_modified = QStyleOptionGraphicsItem(option)
        option_modified.state &= ~QStyle.State_Selected
        super().paint(painter, option_modified, widget)

    def _create_selection_rect(self):
        """Crée le rectangle avec contour fin bleu"""
        min_x = min(p.x() for p in self.arrow_points)
        max_x = max(p.x() for p in self.arrow_points)
        min_y = min(p.y() for p in self.arrow_points)
        max_y = max(p.y() for p in self.arrow_points)
        
        rect_x = min_x 
        rect_y = min_y 
        rect_width = (max_x - min_x) 
        rect_height = (max_y - min_y) 
        
        self._selection_rect = QGraphicsRectItem(rect_x, rect_y, rect_width, rect_height)
        
        # CORRECTION 1: Couleur bleue et épaisseur fine
        self._selection_rect.setPen(QPen(QColor(self.arrow_color), 0.1))  # Bleu fin
        self._selection_rect.setBrush(QBrush(Qt.NoBrush))  # Pas de remplissage
        self._selection_rect.setZValue(1000)
        self._selection_rect.setVisible(False)
        
        self.addToGroup(self._selection_rect)

    def setSelected(self, selected):
        """Affiche/cache le rectangle"""
        self._selected_state = selected
        if self._selection_rect:
            self._selection_rect.setVisible(selected)

    def isSelected(self):
        return self._selected_state

    def itemChange(self, change, value):
        """CORRECTION 2: Logique de déplacement simplifiée"""
        if change == QGraphicsItemGroup.ItemPositionChange and self.isSelected():
            
            # Calculer le delta de déplacement
            old_pos = self.pos()
            new_pos = value
            delta = new_pos - old_pos
            
            
            # Mettre à jour tous les points de la flèche
            for i in range(len(self.arrow_points)):
                old_point = self.arrow_points[i]
                self.arrow_points[i] += delta
            
            # Redessiner la flèche avec les nouveaux points
            self._draw_items_without_moving_rect()
            
            
        return super().itemChange(change, value)

    def _draw_items_without_moving_rect(self):
        """CORRECTION 3: Redessine SEULEMENT la flèche, pas le rectangle"""
        # Supprimer SEULEMENT les items de flèche
        for item in [self._body_item, self._head_item]:
            if item is not None:
                try:
                    self.removeFromGroup(item)
                    item.setParentItem(None)
                except Exception:
                    pass

        if len(self.arrow_points) < 2:
            return

        # Redessiner la flèche
        self._draw_arrow_components()

    def _draw_items(self):
        """Dessine la flèche ET met à jour le rectangle"""
        # Supprimer anciens items de flèche
        for item in [self._body_item, self._head_item]:
            if item is not None:
                try:
                    self.removeFromGroup(item)
                    item.setParentItem(None)
                except Exception:
                    pass

        if len(self.arrow_points) < 2:
            return

        # Dessiner la flèche
        self._draw_arrow_components()
        
        # Mettre à jour le rectangle
        if hasattr(self, '_selection_rect') and self._selection_rect:
            self._update_selection_rect()

    def _draw_arrow_components(self):
        """CORRECTION 4: Dessine les composants de la flèche"""
        pts = self.arrow_points

        # Corps de la flèche
        if self.arrow_style == "zigzag":
            body_path = self._create_zigzag_path(pts)
        elif len(pts) > 2 and self._is_curved():
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

        # Tête de flèche
        start, end = pts[-2], pts[-1]
        dx, dy = end.x() - start.x(), end.y() - start.y()
        length = math.hypot(dx, dy)
        head_length = ANNOTATION_ARROW_HEAD_LENGTH * max(0.8, self.arrow_width * 0.25)
        if length > 0:
            ratio = max(0, (length - head_length * 0.7) / length)
            new_end = QPointF(start.x() + dx * ratio, start.y() + dy * ratio)
            if self.arrow_style != "zigzag":
                body_path = self._truncate_path_end(body_path, new_end)

        # Créer le corps
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

        # Créer la tête
        head_path = self._draw_arrow_head_triangle(start, end, head_length)
        self._head_item = QGraphicsPathItem(head_path)
        self._head_item.setPen(QPen(Qt.NoPen))
        self._head_item.setBrush(QBrush(QColor(self.arrow_color)))
        self.addToGroup(self._head_item)

    def _draw_arrow_components_only(self):
        """Redessine SEULEMENT les composants de la flèche, sans toucher au rectangle"""
        # Supprimer SEULEMENT les items de flèche (pas le rectangle)
        for item in [self._body_item, self._head_item]:
            if item is not None:
                try:
                    self.removeFromGroup(item)
                    item.setParentItem(None)
                except Exception:
                    pass

        if len(self.arrow_points) < 2:
            return

        # Redessiner SEULEMENT la flèche (réutilise le code existant)
        self._draw_arrow_components()

    def _update_selection_rect(self):
        """CORRECTION 5: Met à jour la position du rectangle"""
        if not self._selection_rect:
            return
            
        # Recalculer la bounding box basée sur les nouveaux points
        min_x = min(p.x() for p in self.arrow_points)
        max_x = max(p.x() for p in self.arrow_points)
        min_y = min(p.y() for p in self.arrow_points)
        max_y = max(p.y() for p in self.arrow_points)
        
        rect_x = min_x  
        rect_y = min_y 
        rect_width = (max_x - min_x) 
        rect_height = (max_y - min_y)  
        
        self._selection_rect.setPen(QPen(QColor(self.arrow_color), 0.1))
        self._selection_rect.setRect(rect_x, rect_y, rect_width, rect_height)
        
    # CORRECTION 6: Méthodes utilitaires simplifiées
    def _is_curved(self):
        return len(self.arrow_points) > 2

    def _truncate_path_end(self, path, new_end):
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

    def _create_zigzag_path(self, pts):
        """Version simplifiée du zigzag"""
        if len(pts) < 2:
            return QPainterPath()
        path = QPainterPath()
        path.moveTo(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        return path

    # Interface methods
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
        """Met à jour l'affichage après changement de propriétés"""
        # Sauvegarder l'état de sélection
        was_selected = self.isSelected()
        
        # SOLUTION: Ne redessiner que les éléments visuels, pas le rectangle
        self._draw_arrow_components_only()
        
        # Mettre à jour seulement la couleur du rectangle existant
        if self._selection_rect:
            self._selection_rect.setPen(QPen(QColor(self.arrow_color), 0.1))
        
        # Restaurer l'état de sélection
        self.setSelected(was_selected)
        
        # Forcer la mise à jour visuelle
        self.update()