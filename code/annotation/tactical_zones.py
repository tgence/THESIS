"""
Tactical zones management for football analysis.

Supports creation, manipulation, and visualization of rectangular and elliptical
tactical zones on the pitch for spatial analysis.
"""
# tactical_zones.py

from PyQt5.QtCore import Qt, QPointF, QRectF, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPen, QColor, QBrush, QPainterPath, QPainter, QTransform
from PyQt5.QtWidgets import QGraphicsItemGroup, QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsPathItem

import math
from config import *

DEFAULT_ZONE_COLOR = "#FF0000"
DEFAULT_ZONE_WIDTH = 2
DEFAULT_ZONE_ALPHA = 50  # transparency for fill


class TacticalZoneManager:
    """Manage creation, selection, and storage of tactical zone items."""
    
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
        self.zone_type = "rectangle"  # "rectangle" or "ellipse"
        
    def set_mode(self, mode, zone_type="rectangle"):
        """Set the current mode and zone type."""
        self.current_mode = mode
        self.zone_type = zone_type
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
        if self.zone_type == "rectangle":
            if len(self.zone_points) < 2:
                self.zone_points.append(pos)
        else:  # ellipse
            if len(self.zone_points) < 2:
                self.zone_points.append(pos)
                
    def update_preview(self, pos):
        """Update the zone preview during creation."""
        if not self.zone_points:
            return
            
        self.remove_zone_preview()
        
        if self.zone_type == "rectangle":
            if len(self.zone_points) >= 1:
                start = self.zone_points[0]
                rect = QRectF(start, pos).normalized()
                self.zone_preview = TacticalZoneItem("rectangle", rect, self.zone_color, 
                                                   self.zone_width, self.zone_style, 
                                                   self.zone_fill_alpha, preview=True)
                self.scene.addItem(self.zone_preview)
        else:  # ellipse
            if len(self.zone_points) >= 1:
                center = self.zone_points[0]
                radius_x = abs(pos.x() - center.x())
                radius_y = abs(pos.y() - center.y())
                rect = QRectF(center.x() - radius_x, center.y() - radius_y, 
                             radius_x * 2, radius_y * 2)
                self.zone_preview = TacticalZoneItem("ellipse", rect, self.zone_color,
                                                   self.zone_width, self.zone_style,
                                                   self.zone_fill_alpha, preview=True)
                self.scene.addItem(self.zone_preview)
                
    def finish_zone(self):
        """Finish creating the current zone."""
        if len(self.zone_points) < 2:
            return False
            
        self.remove_zone_preview()
        
        if self.zone_type == "rectangle":
            rect = QRectF(self.zone_points[0], self.zone_points[1]).normalized()
            zone = TacticalZoneItem("rectangle", rect, self.zone_color, 
                                  self.zone_width, self.zone_style, 
                                  self.zone_fill_alpha)
        else:  # ellipse
            center = self.zone_points[0]
            end = self.zone_points[1]
            radius_x = abs(end.x() - center.x())
            radius_y = abs(end.y() - center.y())
            rect = QRectF(center.x() - radius_x, center.y() - radius_y,
                         radius_x * 2, radius_y * 2)
            zone = TacticalZoneItem("ellipse", rect, self.zone_color,
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


class TacticalZoneItem(QGraphicsItemGroup):
    """Graphical item representing a tactical zone (rectangle or ellipse)."""
    
    def __init__(self, zone_type, rect, color, width, style, fill_alpha, preview=False, parent=None):
        super().__init__(parent)
        
        self.zone_type = zone_type  # "rectangle" or "ellipse"
        self.rect = rect
        self.zone_color = color
        self.zone_width = width
        self.zone_style = style
        self.zone_fill_alpha = fill_alpha
        self.rotation_angle = 0
        self.is_preview = preview
        
        # Create the main zone item
        self._create_zone_item()
        
        # Create selection rectangle (hidden by default)
        self._create_selection_rect()
        
        # Set flags for interaction
        self.setFlag(QGraphicsItemGroup.ItemIsSelectable, True)
        self.setFlag(QGraphicsItemGroup.ItemIsMovable, True)
        self.setFlag(QGraphicsItemGroup.ItemSendsGeometryChanges, True)
        
    def _create_zone_item(self):
        """Create the main zone shape."""
        if self.zone_type == "rectangle":
            self.zone_item = QGraphicsRectItem(self.rect)
        else:  # ellipse
            self.zone_item = QGraphicsEllipseItem(self.rect)
            
        # Set pen
        pen = QPen(QColor(self.zone_color), self.zone_width)
        if self.zone_style == "dotted":
            pen.setStyle(Qt.DashLine)
        elif self.zone_style == "zigzag":
            pen.setStyle(Qt.DashDotLine)
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
        """Create selection rectangle with handles."""
        self._selection_rect = QGraphicsRectItem()
        self._selection_rect.setPen(QPen(QColor("#0066FF"), 1, Qt.DashLine))
        self._selection_rect.setBrush(QBrush(Qt.NoBrush))
        self._selection_rect.setVisible(False)
        self.addToGroup(self._selection_rect)
        
        # Create rotation handle
        self._rotation_handle = QGraphicsPathItem()
        rotation_path = QPainterPath()
        # Create a curved arrow for rotation
        rotation_path.moveTo(0, -5)
        rotation_path.arcTo(-5, -10, 10, 10, 0, 180)
        rotation_path.lineTo(0, -5)
        self._rotation_handle.setPath(rotation_path)
        self._rotation_handle.setPen(QPen(QColor("#0066FF"), 2))
        self._rotation_handle.setBrush(QBrush(QColor("#0066FF")))
        self._rotation_handle.setVisible(False)
        self.addToGroup(self._rotation_handle)
        
    def setSelected(self, selected):
        """Handle selection state."""
        super().setSelected(selected)
        if selected:
            self._update_selection_rect()
            self._selection_rect.setVisible(True)
            self._rotation_handle.setVisible(True)
        else:
            self._selection_rect.setVisible(False)
            self._rotation_handle.setVisible(False)
            
    def _update_selection_rect(self):
        """Update selection rectangle to match zone bounds."""
        if self.zone_type == "rectangle":
            bounds = self.zone_item.rect()
        else:  # ellipse
            bounds = self.zone_item.rect()
            
        # Apply rotation if needed
        if self.rotation_angle != 0:
            transform = QTransform()
            transform.rotate(self.rotation_angle)
            bounds = transform.mapRect(bounds)
            
        # Add some padding
        padding = 5
        bounds.adjust(-padding, -padding, padding, padding)
        self._selection_rect.setRect(bounds)
        
        # Position rotation handle
        handle_pos = QPointF(bounds.right(), bounds.top() - 20)
        self._rotation_handle.setPos(handle_pos)
        
    def set_color(self, color):
        """Change zone color."""
        self.zone_color = color
        pen = self.zone_item.pen()
        pen.setColor(QColor(color))
        self.zone_item.setPen(pen)
        
        brush_color = QColor(color)
        brush_color.setAlpha(self.zone_fill_alpha)
        self.zone_item.setBrush(QBrush(brush_color))
        
    def set_width(self, width):
        """Change zone border width."""
        self.zone_width = width
        pen = self.zone_item.pen()
        pen.setWidth(width)
        self.zone_item.setPen(pen)
        
    def set_fill_alpha(self, alpha):
        """Change zone fill transparency."""
        self.zone_fill_alpha = alpha
        brush_color = QColor(self.zone_color)
        brush_color.setAlpha(alpha)
        self.zone_item.setBrush(QBrush(brush_color))
        
    def set_rotation(self, angle):
        """Set zone rotation angle."""
        self.rotation_angle = angle
        transform = QTransform()
        transform.rotate(angle)
        self.zone_item.setTransform(transform)
        if self.isSelected():
            self._update_selection_rect()
            
    def get_rotation(self):
        """Get current rotation angle."""
        return self.rotation_angle
        
    def get_zone_data(self):
        """Get zone data for saving/loading."""
        return {
            'type': self.zone_type,
            'rect': (self.rect.x(), self.rect.y(), self.rect.width(), self.rect.height()),
            'color': self.zone_color,
            'width': self.zone_width,
            'style': self.zone_style,
            'fill_alpha': self.zone_fill_alpha,
            'rotation': self.rotation_angle,
            'position': (self.pos().x(), self.pos().y())
        }
        
    def set_zone_data(self, data):
        """Set zone data from saved data."""
        self.zone_type = data['type']
        self.rect = QRectF(*data['rect'])
        self.zone_color = data['color']
        self.zone_width = data['width']
        self.zone_style = data['style']
        self.zone_fill_alpha = data['fill_alpha']
        self.rotation_angle = data['rotation']
        self.setPos(*data['position'])
        
        # Recreate the zone item with new data
        self.removeFromGroup(self.zone_item)
        self.scene().removeItem(self.zone_item)
        self._create_zone_item()
