"""
Annotation management on the pitch scene.

Supports arrows, rectangles, and ellipses with selection/move and visual property updates.
Used by tactical simulation to associate annotations with players and action types.
"""
# annotation.py

from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QPen, QColor, QPainterPath, QBrush, QTransform
from PyQt5.QtWidgets import QGraphicsPathItem, QGraphicsItemGroup, QGraphicsRectItem, QGraphicsEllipseItem, QStyleOptionGraphicsItem, QStyle

import math

from config import *
DEFAULT_ARROW_COLOR = "#000000"
DEFAULT_ZONE_COLOR = "#000000"
DEFAULT_ZONE_WIDTH = 1
DEFAULT_ZONE_ALPHA = 0  # transparency for fill (0 = transparent)

class ArrowAnnotationManager:
    def __init__(self, scene):
        """Manage creation, preview, selection, and storage of arrow items."""
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
        """Select a specific arrow and unselect others."""
        self.clear_selection()
        self.selected_arrow = arrow
        if arrow:
            arrow.setSelected(True)
            # Visually emphasize selection (rectangle handled by item)
    
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
        """Draw triangular arrowhead with specified color"""
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
        # Note: preview uses reduced alpha; geometry/styling is otherwise identical
        color = self.arrow_color
        width = self.arrow_width
        style = self.arrow_style
        if preview:
            # Add alpha for preview (e.g., 0.5 transparency)
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
        """Delete the most recently created arrow from the scene and memory."""
        if self.arrows:
            arrow_item = self.arrows.pop()
            try:
                self.scene.removeItem(arrow_item)
            except RuntimeError:
                pass
        self.clear_selection()

class CustomArrowItem(QGraphicsItemGroup):
    """Composite arrow item with a thin selection rectangle overlay."""
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
        """Override to remove default white square"""
        option_modified = QStyleOptionGraphicsItem(option)
        option_modified.state &= ~QStyle.State_Selected
        super().paint(painter, option_modified, widget)

    def _create_selection_rect(self):
        """Create rectangle with thin outline"""
        min_x = min(p.x() for p in self.arrow_points)
        max_x = max(p.x() for p in self.arrow_points)
        min_y = min(p.y() for p in self.arrow_points)
        max_y = max(p.y() for p in self.arrow_points)
        
        rect_x = min_x 
        rect_y = min_y 
        rect_width = (max_x - min_x) 
        rect_height = (max_y - min_y) 
        
        self._selection_rect = QGraphicsRectItem(rect_x, rect_y, rect_width, rect_height)
        
        # Thin outline, using arrow color for the selection rectangle
        self._selection_rect.setPen(QPen(QColor(self.arrow_color), 0.1))  
        self._selection_rect.setBrush(QBrush(Qt.NoBrush))  # No fill
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
        """Simplified move logic: update points then redraw without moving rect."""
        if change == QGraphicsItemGroup.ItemPositionChange and self.isSelected():
            
            # Calculate displacement delta
            old_pos = self.pos()
            new_pos = value
            delta = new_pos - old_pos
            
            
            # Update all arrow points
            for i in range(len(self.arrow_points)):
                old_point = self.arrow_points[i]
                self.arrow_points[i] += delta
            
            # Redraw arrow with new points
            self._draw_items_without_moving_rect()
            
            
        return super().itemChange(change, value)

    def _draw_items_without_moving_rect(self):
        """Redraw only the arrow items, not the selection rectangle."""
        # Remove only arrow sub-items (keep selection rectangle)
        for item in [self._body_item, self._head_item]:
            if item is not None:
                try:
                    self.removeFromGroup(item)
                    item.setParentItem(None)
                except Exception:
                    pass

        if len(self.arrow_points) < 2:
            return

        # Redraw the arrow
        self._draw_arrow_components()

    def _draw_items(self):
        """Draw arrow AND update rectangle"""
        # Remove previous arrow sub-items
        for item in [self._body_item, self._head_item]:
            if item is not None:
                try:
                    self.removeFromGroup(item)
                    item.setParentItem(None)
                except Exception:
                    pass

        if len(self.arrow_points) < 2:
            return

        # Draw the arrow
        self._draw_arrow_components()
        
        # Update the selection rectangle
        if hasattr(self, '_selection_rect') and self._selection_rect:
            self._update_selection_rect()

    def _draw_arrow_components(self):
        """Draw the arrow components (body and head)."""
        pts = self.arrow_points

        # Arrow body
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

        # Arrow head
        start, end = pts[-2], pts[-1]
        dx, dy = end.x() - start.x(), end.y() - start.y()
        length = math.hypot(dx, dy)
        head_length = ANNOTATION_ARROW_HEAD_LENGTH * max(0.8, self.arrow_width * 0.25)
        if length > 0:
            ratio = max(0, (length - head_length * 0.7) / length)
            new_end = QPointF(start.x() + dx * ratio, start.y() + dy * ratio)
            if self.arrow_style != "zigzag":
                body_path = self._truncate_path_end(body_path, new_end)

        # Create body item
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

        # Create head item
        head_path = self._draw_arrow_head_triangle(start, end, head_length)
        self._head_item = QGraphicsPathItem(head_path)
        self._head_item.setPen(QPen(Qt.NoPen))
        self._head_item.setBrush(QBrush(QColor(self.arrow_color)))
        self.addToGroup(self._head_item)

    def _draw_arrow_components_only(self):
        """Redraw only the arrow components without touching the selection rect."""
        # Remove only the arrow sub-items (not the rectangle)
        for item in [self._body_item, self._head_item]:
            if item is not None:
                try:
                    self.removeFromGroup(item)
                    item.setParentItem(None)
                except Exception:
                    pass

        if len(self.arrow_points) < 2:
            return

        # Redraw only the arrow (reuse the existing code)
        self._draw_arrow_components()

    def _update_selection_rect(self):
        """Update the selection rectangle position and size."""
        if not self._selection_rect:
            return
            
        # Recompute bounding box based on current points
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
        
    # Utility methods
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
        """Simplified zigzag version"""
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
        """Update display after property changes"""
        # Preserve selection state
        was_selected = self.isSelected()
        
        # Redraw only visual components, not the rectangle
        self._draw_arrow_components_only()
        
        # Update only the selection rectangle color
        if self._selection_rect:
            self._selection_rect.setPen(QPen(QColor(self.arrow_color), 0.1))
        
        # Restore selection state
        self.setSelected(was_selected)
        
        # Force visual update
        self.update()


# ===== ZONE MANAGERS =====

class RectangleZoneManager:
    """Manage creation, selection, and storage of rectangular tactical zones."""
    
    def __init__(self, scene):
        self.scene = scene
        self.zones = []
        self.zone_points = []
        self.zone_color = DEFAULT_ZONE_COLOR
        self.zone_width = DEFAULT_ZONE_WIDTH
        self.zone_style = "solid"
        self.zone_fill_alpha = DEFAULT_ZONE_ALPHA
        self.zone_preview = None
        self.selected_zone = None
        self.current_mode = "select"
        
    def set_mode(self, mode):
        """Set the current mode."""
        self.current_mode = mode
        self.zone_points = []
        self.remove_zone_preview()
        self.clear_selection()
        
    def clear_selection(self):
        """Clear all zone selections."""
        for zone in list(self.zones):
            try:
                zone.setSelected(False)
            except RuntimeError:
                self.zones.remove(zone)
        self.selected_zone = None
        
    def select_zone(self, zone):
        """Select a specific zone and unselect others."""
        self.clear_selection()
        self.selected_zone = zone
        if zone:
            zone.setSelected(True)
            
    def set_color(self, color):
        """Set color for selected zone or default."""
        if self.selected_zone:
            self.selected_zone.set_color(color)
        else:
            self.zone_color = color
            
    def set_width(self, width):
        """Set width for selected zone or default."""
        if self.selected_zone:
            self.selected_zone.set_width(width)
        else:
            self.zone_width = width
            
    def set_style(self, style):
        """Set border style for selected zone or default ('solid'|'dashed')."""
        normalized = "dashed" if str(style).lower() in ("dash", "dashed", "--") else "solid"
        if self.selected_zone:
            self.selected_zone.set_style(normalized)
        else:
            self.zone_style = normalized

    def set_fill_alpha(self, alpha):
        """Set fill transparency for selected zone or default."""
        if self.selected_zone:
            self.selected_zone.set_fill_alpha(alpha)
        else:
            self.zone_fill_alpha = alpha
            
    def remove_zone_preview(self):
        """Remove the current zone preview."""
        if self.zone_preview:
            try:
                self.scene.removeItem(self.zone_preview)
            except RuntimeError:
                pass
            self.zone_preview = None
            
    def add_point(self, pos):
        """Add a point for zone creation."""
        if len(self.zone_points) < 2:
            self.zone_points.append(pos)
                
    def update_preview(self, pos):
        """Update the zone preview during creation."""
        if not self.zone_points:
            return
            
        self.remove_zone_preview()
        
        if len(self.zone_points) >= 1:
            start = self.zone_points[0]
            rect = QRectF(start, pos).normalized()
            self.zone_preview = RectangleZoneItem(rect, self.zone_color, 
                                               self.zone_width, self.zone_style, 
                                               self.zone_fill_alpha, preview=True)
            self.scene.addItem(self.zone_preview)
                
    def finish_zone(self):
        """Finish creating the current zone."""
        if len(self.zone_points) < 2:
            return False
            
        self.remove_zone_preview()
        
        rect = QRectF(self.zone_points[0], self.zone_points[1]).normalized()
        zone = RectangleZoneItem(rect, self.zone_color, 
                              self.zone_width, self.zone_style, 
                              self.zone_fill_alpha)
            
        self.scene.addItem(zone)
        self.zones.append(zone)
        self.zone_points = []
        return True
        
    def cancel_zone(self):
        """Cancel the current zone creation."""
        self.remove_zone_preview()
        self.zone_points = []
        
    def delete_selected_zone(self):
        """Delete the currently selected zone."""
        if self.selected_zone:
            zone = self.selected_zone
            if zone in self.zones:
                self.zones.remove(zone)
            try:
                self.scene.removeItem(zone)
            except RuntimeError:
                pass
            self.clear_selection()


class EllipseZoneManager:
    """Manage creation, selection, and storage of elliptical tactical zones."""
    
    def __init__(self, scene):
        self.scene = scene
        self.zones = []
        self.zone_points = []
        self.zone_color = DEFAULT_ZONE_COLOR
        self.zone_width = DEFAULT_ZONE_WIDTH
        self.zone_style = "solid"
        self.zone_fill_alpha = DEFAULT_ZONE_ALPHA
        self.zone_preview = None
        self.selected_zone = None
        self.current_mode = "select"
        
    def set_mode(self, mode):
        """Set the current mode."""
        self.current_mode = mode
        self.zone_points = []
        self.remove_zone_preview()
        self.clear_selection()
        
    def clear_selection(self):
        """Clear all zone selections."""
        for zone in list(self.zones):
            try:
                zone.setSelected(False)
            except RuntimeError:
                self.zones.remove(zone)
        self.selected_zone = None
        
    def select_zone(self, zone):
        """Select a specific zone and unselect others."""
        self.clear_selection()
        self.selected_zone = zone
        if zone:
            zone.setSelected(True)
            
    def set_color(self, color):
        """Set color for selected zone or default."""
        if self.selected_zone:
            self.selected_zone.set_color(color)
        else:
            self.zone_color = color
            
    def set_width(self, width):
        """Set width for selected zone or default."""
        if self.selected_zone:
            self.selected_zone.set_width(width)
        else:
            self.zone_width = width
            
    def set_style(self, style):
        """Set border style for selected zone or default ('solid'|'dashed')."""
        normalized = "dashed" if str(style).lower() in ("dash", "dashed", "--") else "solid"
        if self.selected_zone:
            self.selected_zone.set_style(normalized)
        else:
            self.zone_style = normalized

    def set_fill_alpha(self, alpha):
        """Set fill transparency for selected zone or default."""
        if self.selected_zone:
            self.selected_zone.set_fill_alpha(alpha)
        else:
            self.zone_fill_alpha = alpha
            
    def remove_zone_preview(self):
        """Remove the current zone preview."""
        if self.zone_preview:
            try:
                self.scene.removeItem(self.zone_preview)
            except RuntimeError:
                pass
            self.zone_preview = None
            
    def add_point(self, pos):
        """Add a point for zone creation."""
        if len(self.zone_points) < 2:
            self.zone_points.append(pos)
                
    def update_preview(self, pos):
        """Update the zone preview during creation."""
        if not self.zone_points:
            return
            
        self.remove_zone_preview()
        
        if len(self.zone_points) >= 1:
            center = self.zone_points[0]
            radius_x = abs(pos.x() - center.x())
            radius_y = abs(pos.y() - center.y())
            rect = QRectF(center.x() - radius_x, center.y() - radius_y, 
                         radius_x * 2, radius_y * 2)
            self.zone_preview = EllipseZoneItem(rect, self.zone_color,
                                              self.zone_width, self.zone_style,
                                              self.zone_fill_alpha, preview=True)
            self.scene.addItem(self.zone_preview)
                
    def finish_zone(self):
        """Finish creating the current zone."""
        if len(self.zone_points) < 2:
            return False
            
        self.remove_zone_preview()
        
        center = self.zone_points[0]
        end = self.zone_points[1]
        radius_x = abs(end.x() - center.x())
        radius_y = abs(end.y() - center.y())
        rect = QRectF(center.x() - radius_x, center.y() - radius_y,
                     radius_x * 2, radius_y * 2)
        zone = EllipseZoneItem(rect, self.zone_color,
                             self.zone_width, self.zone_style,
                             self.zone_fill_alpha)
            
        self.scene.addItem(zone)
        self.zones.append(zone)
        self.zone_points = []
        return True
        
    def cancel_zone(self):
        """Cancel the current zone creation."""
        self.remove_zone_preview()
        self.zone_points = []
        
    def delete_selected_zone(self):
        """Delete the currently selected zone."""
        if self.selected_zone:
            zone = self.selected_zone
            if zone in self.zones:
                self.zones.remove(zone)
            try:
                self.scene.removeItem(zone)
            except RuntimeError:
                pass
            self.clear_selection()


# ===== ZONE ITEMS =====

class RectangleZoneItem(QGraphicsItemGroup):
    """Graphical item representing a rectangular tactical zone."""
    
    def __init__(self, rect, color, width, style, fill_alpha, preview=False, parent=None):
        super().__init__(parent)
        
        self.rect = rect
        self.zone_color = color
        self.zone_width = width
        self.zone_style = style
        self.zone_fill_alpha = fill_alpha
        self.rotation_angle = 0
        self.is_preview = preview
        self._updating_handles = False  # Prevent recursion during handle updates
        
        # Create the main zone item
        self._create_zone_item()
        
        # Create selection rectangle and handles (hidden by default)
        self._create_selection_rect()
        
        # Set flags for interaction
        self.setFlag(QGraphicsItemGroup.ItemIsSelectable, True)
        self.setFlag(QGraphicsItemGroup.ItemIsMovable, True)
        self.setFlag(QGraphicsItemGroup.ItemSendsGeometryChanges, True)
        
    def paint(self, painter, option, widget):
        """Override to remove default white selection rectangle."""
        option_modified = QStyleOptionGraphicsItem(option)
        option_modified.state &= ~QStyle.State_Selected
        super().paint(painter, option_modified, widget)
        
    def _create_zone_item(self):
        """Create the main zone shape."""
        self.zone_item = QGraphicsRectItem(self.rect)
            
        # Set pen with ultra-thin thickness
        pen = QPen(QColor(self.zone_color), 0.1)  # Cosmetic pen (thinnest possible)
        if self.zone_style in ("dashed", "dotted"):
            pen.setStyle(Qt.DashLine)
        else:
            pen.setStyle(Qt.SolidLine)
        self.zone_item.setPen(pen)
        
        # Set brush with transparency
        brush_color = QColor(self.zone_color)
        brush_color.setAlpha(self.zone_fill_alpha)
        self.zone_item.setBrush(QBrush(brush_color))
        
        # Apply rotation
        if self.rotation_angle != 0:
            transform = QTransform()
            transform.rotate(self.rotation_angle)
            self.zone_item.setTransform(transform)
            
        self.addToGroup(self.zone_item)
        
    def _create_selection_rect(self):
        """Create selection rectangle."""
        self._selection_rect = QGraphicsRectItem()
        self._selection_rect.setPen(QPen(QColor(self.zone_color), 0.1))  # Ultra-thin selection
        self._selection_rect.setBrush(QBrush(Qt.NoBrush))
        self._selection_rect.setVisible(False)

        # self._selection_rect.setCursor(Qt.SizeFDiagCursor)
        self.addToGroup(self._selection_rect)
        
    def setSelected(self, selected):
        """Handle selection state."""
        super().setSelected(selected)
        if selected:
            self._update_selection_rect()
            self._selection_rect.setVisible(True)
        else:
            self._selection_rect.setVisible(False)
            
    def _update_selection_rect(self):
        """Update selection rectangle to match zone bounds."""
        # Get the bounding rectangle of the transformed zone
        if self.rotation_angle != 0:
            # For rotated shapes, get the actual bounding box in scene coordinates
            scene_bounds = self.zone_item.sceneBoundingRect()
            # Convert back to item coordinates
            bounds = self.mapRectFromScene(scene_bounds)
        else:
            # For non-rotated shapes, use the original rectangle
            bounds = self.zone_item.rect()
            
        # No padding - exact bounds only
        self._selection_rect.setRect(bounds)
        # Keep selection rectangle pen color in sync
        self._selection_rect.setPen(QPen(QColor(self.zone_color), 0.1))  # Ultra-thin selection
    

        
    def set_color(self, color):
        """Change zone color and sync selection rectangle and handles."""
        self.zone_color = color
        pen = self.zone_item.pen()
        pen.setColor(QColor(color))
        self.zone_item.setPen(pen)
        
        brush_color = QColor(color)
        brush_color.setAlpha(self.zone_fill_alpha)
        self.zone_item.setBrush(QBrush(brush_color))
        
        # Sync selection rectangle color
        if hasattr(self, "_selection_rect") and self._selection_rect is not None:
            self._selection_rect.setPen(QPen(QColor(self.zone_color), 0.1))  # Ultra-thin selection
        
    def set_width(self, width):
        """Change zone border width."""
        self.zone_width = width
        # Scale width slower: divide growth factor by 2
        scaled_width = width * 0.25  # Half the growth rate
        # Create new pen with color and float width
        new_pen = QPen(QColor(self.zone_color), scaled_width)
        new_pen.setStyle(Qt.DashLine if self.zone_style == "dashed" else Qt.SolidLine)
        self.zone_item.setPen(new_pen)
        
    def set_fill_alpha(self, alpha):
        """Change zone fill transparency."""
        self.zone_fill_alpha = alpha
        brush_color = QColor(self.zone_color)
        brush_color.setAlpha(alpha)
        self.zone_item.setBrush(QBrush(brush_color))
        
    def set_style(self, style):
        """Change zone border style ('solid'|'dashed')."""
        self.zone_style = "dashed" if str(style).lower() in ("dash", "dashed", "--") else "solid"
        pen = self.zone_item.pen()
        pen.setStyle(Qt.DashLine if self.zone_style == "dashed" else Qt.SolidLine)
        self.zone_item.setPen(pen)
        
    def set_rotation(self, angle):
        """Set zone rotation angle around the center of the shape."""
        self.rotation_angle = angle
        
        # Get the center of the shape
        rect = self.zone_item.rect()
        center = rect.center()
        
        # Create transform that rotates around the center
        transform = QTransform()
        transform.translate(center.x(), center.y())  # Move to center
        transform.rotate(angle)                       # Rotate
        transform.translate(-center.x(), -center.y()) # Move back
        self.zone_item.setTransform(transform)
        
        if self.isSelected():
            self._update_selection_rect()
            
    def get_rotation(self):
        """Get current rotation angle."""
        return self.rotation_angle


class EllipseZoneItem(QGraphicsItemGroup):
    """Graphical item representing an elliptical tactical zone."""
    
    def __init__(self, rect, color, width, style, fill_alpha, preview=False, parent=None):
        super().__init__(parent)
        
        self.rect = rect
        self.zone_color = color
        self.zone_width = width
        self.zone_style = style
        self.zone_fill_alpha = fill_alpha
        self.rotation_angle = 0
        self.is_preview = preview
        self._updating_handles = False  # Prevent recursion during handle updates
        
        # Create the main zone item
        self._create_zone_item()
        
        # Create selection rectangle (hidden by default)
        self._create_selection_rect()
        
        # Set flags for interaction
        self.setFlag(QGraphicsItemGroup.ItemIsSelectable, True)
        self.setFlag(QGraphicsItemGroup.ItemIsMovable, True)
        self.setFlag(QGraphicsItemGroup.ItemSendsGeometryChanges, True)
        
    def paint(self, painter, option, widget):
        """Override to remove default white selection rectangle."""
        option_modified = QStyleOptionGraphicsItem(option)
        option_modified.state &= ~QStyle.State_Selected
        super().paint(painter, option_modified, widget)
        
    def _create_zone_item(self):
        """Create the main zone shape."""
        self.zone_item = QGraphicsEllipseItem(self.rect)
            
        # Set pen with ultra-thin thickness
        pen = QPen(QColor(self.zone_color), 0.1)  # Cosmetic pen (thinnest possible)
        if self.zone_style in ("dashed", "dotted"):
            pen.setStyle(Qt.DashLine)
        else:
            pen.setStyle(Qt.SolidLine)
        self.zone_item.setPen(pen)
        
        # Set brush with transparency
        brush_color = QColor(self.zone_color)
        brush_color.setAlpha(self.zone_fill_alpha)
        self.zone_item.setBrush(QBrush(brush_color))
        
        # Apply rotation
        if self.rotation_angle != 0:
            transform = QTransform()
            transform.rotate(self.rotation_angle)
            self.zone_item.setTransform(transform)
            
        self.addToGroup(self.zone_item)
        
    def _create_selection_rect(self):
        """Create selection rectangle."""
        self._selection_rect = QGraphicsRectItem()
        self._selection_rect.setPen(QPen(QColor(self.zone_color), 0.1))  # Ultra-thin selection
        self._selection_rect.setBrush(QBrush(Qt.NoBrush))
        self._selection_rect.setVisible(False)

        # self._selection_rect.setCursor(Qt.SizeFDiagCursor)
        self.addToGroup(self._selection_rect)
        
    def setSelected(self, selected):
        """Handle selection state."""
        super().setSelected(selected)
        if selected:
            self._update_selection_rect()
            self._selection_rect.setVisible(True)
        else:
            self._selection_rect.setVisible(False)
            
    def _update_selection_rect(self):
        """Update selection rectangle and resize handles to match zone bounds."""
        bounds = self.zone_item.rect()
            
        # Apply rotation if needed
        if self.rotation_angle != 0:
            transform = QTransform()
            transform.rotate(self.rotation_angle)
            bounds = transform.mapRect(bounds)
            
        # No padding - exact bounds only
        self._selection_rect.setRect(bounds)
        self._selection_rect.setPen(QPen(QColor(self.zone_color), 0.1))  # Ultra-thin selection
        
        # Position resize handles at corners and edges
        if hasattr(self, '_resize_handles'):
            # Corners: top-left, top-right, bottom-left, bottom-right
            # Edges: top, right, bottom, left
            positions = [
                (bounds.left(), bounds.top()),      # 0: top-left
                (bounds.right(), bounds.top()),     # 1: top-right
                (bounds.left(), bounds.bottom()),   # 2: bottom-left
                (bounds.right(), bounds.bottom()),  # 3: bottom-right
                (bounds.center().x(), bounds.top()),    # 4: top edge
                (bounds.right(), bounds.center().y()),  # 5: right edge
                (bounds.center().x(), bounds.bottom()), # 6: bottom edge
                (bounds.left(), bounds.center().y())    # 7: left edge
            ]
            
            for i, handle in enumerate(self._resize_handles):
                if i < len(positions):
                    handle.setPos(positions[i][0], positions[i][1])
    
    def itemChange(self, change, value):
        """Handle item changes."""
        # For now, just handle basic position changes
        if change == QGraphicsItemGroup.ItemPositionChange:
            # Zone moved, update selection rect
            if hasattr(self, '_selection_rect'):
                self._update_selection_rect()
        return super().itemChange(change, value)
    
    def _handle_resize(self, handle_index, new_pos):
        """Resize the ellipse based on handle movement."""
        current_rect = self.zone_item.rect()
        
        # Handle index mapping (same as rectangle):
        # 0: top-left, 1: top-right, 2: bottom-left, 3: bottom-right
        # 4: top edge, 5: right edge, 6: bottom edge, 7: left edge
        
        if handle_index == 0:  # top-left
            current_rect.setTopLeft(new_pos)
        elif handle_index == 1:  # top-right
            current_rect.setTopRight(new_pos)
        elif handle_index == 2:  # bottom-left
            current_rect.setBottomLeft(new_pos)
        elif handle_index == 3:  # bottom-right
            current_rect.setBottomRight(new_pos)
        elif handle_index == 4:  # top edge
            current_rect.setTop(new_pos.y())
        elif handle_index == 5:  # right edge
            current_rect.setRight(new_pos.x())
        elif handle_index == 6:  # bottom edge
            current_rect.setBottom(new_pos.y())
        elif handle_index == 7:  # left edge
            current_rect.setLeft(new_pos.x())
        
        # Update the zone rectangle (ellipse uses same bounding rect)
        self.rect = current_rect
        self.zone_item.setRect(current_rect)
        self._update_selection_rect()
        
    def set_color(self, color):
        """Change zone color."""
        self.zone_color = color
        pen = self.zone_item.pen()
        pen.setColor(QColor(color))
        self.zone_item.setPen(pen)
        
        brush_color = QColor(color)
        brush_color.setAlpha(self.zone_fill_alpha)
        self.zone_item.setBrush(QBrush(brush_color))
        
        # Sync selection rectangle color
        if hasattr(self, "_selection_rect") and self._selection_rect is not None:
            self._selection_rect.setPen(QPen(QColor(self.zone_color), 0.1))  # Ultra-thin selection
        
    def set_width(self, width):
        """Change zone border width."""
        self.zone_width = width
        # Scale width slower: divide growth factor by 2
        scaled_width = width * 0.25
        # Create new pen with color and float width
        new_pen = QPen(QColor(self.zone_color), scaled_width)
        new_pen.setStyle(Qt.DashLine if self.zone_style == "dashed" else Qt.SolidLine)
        self.zone_item.setPen(new_pen)
        
    def set_fill_alpha(self, alpha):
        """Change zone fill transparency."""
        self.zone_fill_alpha = alpha
        brush_color = QColor(self.zone_color)
        brush_color.setAlpha(alpha)
        self.zone_item.setBrush(QBrush(brush_color))
        
    def set_style(self, style):
        """Change zone border style ('solid'|'dashed')."""
        self.zone_style = "dashed" if str(style).lower() in ("dash", "dashed", "--") else "solid"
        pen = self.zone_item.pen()
        pen.setStyle(Qt.DashLine if self.zone_style == "dashed" else Qt.SolidLine)
        self.zone_item.setPen(pen)
        
    def set_rotation(self, angle):
        """Set zone rotation angle around the center of the shape."""
        self.rotation_angle = angle
        
        # Get the center of the shape
        rect = self.zone_item.rect()
        center = rect.center()
        
        # Create transform that rotates around the center
        transform = QTransform()
        transform.translate(center.x(), center.y())  # Move to center
        transform.rotate(angle)                       # Rotate
        transform.translate(-center.x(), -center.y()) # Move back
        self.zone_item.setTransform(transform)
        
        if self.isSelected():
            self._update_selection_rect()
            
    def get_rotation(self):
        """Get current rotation angle."""
        return self.rotation_angle