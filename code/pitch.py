# pitch.py
"""
Pitch rendering with PyQt GraphicsScene.

`PitchWidget` draws the static field once and re-renders dynamic items
(players, ball, overlays) every frame. It relies on size constants exposed via
`CONFIG` so that visual scale can be adjusted globally.
"""
# pitch.py
import numpy as np
import math
from PyQt5.QtWidgets import (
    QWidget, QGraphicsScene, QGraphicsView, QVBoxLayout, QGraphicsEllipseItem, QGraphicsPathItem,
    QGraphicsTextItem, QGraphicsRectItem, QGraphicsItemGroup
)
from PyQt5.QtGui import QPen, QBrush, QColor, QFont, QPainterPath, QTransform
from PyQt5.QtCore import Qt, QRectF
from config import CONFIG


from data_processing import get_pressure_color, build_ball_carrier_array
from config import *

class PitchWidget(QWidget):
    """Graphics widget to display a soccer pitch and dynamic overlays.

    Parameters
    ----------
    X_MIN, X_MAX, Y_MIN, Y_MAX : float
        Pitch bounds in scene coordinates.
    parent : QWidget, optional
        Parent widget.
    """
    def __init__(self, X_MIN, X_MAX, Y_MIN, Y_MAX, parent=None):
        super().__init__(parent)
        self.X_MIN = X_MIN
        self.X_MAX = X_MAX
        self.Y_MIN = Y_MIN
        self.Y_MAX = Y_MAX
        self.PITCH_LENGTH = X_MAX - X_MIN
        self.PITCH_WIDTH = Y_MAX - Y_MIN
        self.theme = {}


        self.pitch_items = []         # Static pitch objects
        self.dynamic_items = []       # Dynamic objects (players, ball, lines, etc)
        self.annotation_items = []    # Annotations/arrows, managed elsewhere

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(self.view.renderHints() | self.view.renderHints())
        self.view.scale(1, -1)
        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        self.setLayout(layout)
        self.draw_pitch()
        
    
        

    def clear_pitch(self):
        """Remove static field items from the scene."""
        for item in self.pitch_items:
            self.scene.removeItem(item)
        self.pitch_items.clear()

    def clear_dynamic(self):
        """Remove dynamic items (players, ball, lines, overlays)."""
        for item in self.dynamic_items:
            try:
                scene = item.scene()
                if scene is not None:
                    scene.removeItem(item)
            except Exception:
                pass
        self.dynamic_items.clear()

        
    def draw_pitch(self):
        """Draw the field using current theme colors (grass and lines)."""
        self.clear_pitch()
        # Grab theme colors (fallback if key is missing)
        grass_color = self.theme.get("grass", "#08711a")
        line_color    = self.theme.get("line",    "#FFFFFF")

        brush = QBrush(QColor(grass_color))
        pen   = QPen(QColor(line_color), LINE_WIDTH)

        # Grass + main field rectangle
        grass = QGraphicsRectItem(
            self.X_MIN - 2*SCENE_EXTRA_GRASS,
            self.Y_MIN - SCENE_EXTRA_GRASS,
            self.PITCH_LENGTH + 4*SCENE_EXTRA_GRASS,
            self.PITCH_WIDTH  + 2*SCENE_EXTRA_GRASS
        )
        grass.setBrush(brush)
        grass.setPen(QPen(Qt.NoPen))
        self.scene.addItem(grass)
        self.pitch_items.append(grass)

        field = self.scene.addRect(
            self.X_MIN, self.Y_MIN, self.PITCH_LENGTH, self.PITCH_WIDTH,
            pen, brush
        )
        field.setZValue(-10)
        self.pitch_items.append(field)

        # Outer lines and halfway line
        self.pitch_items.append(self.scene.addLine(self.X_MIN, self.Y_MIN, self.X_MIN, self.Y_MAX, pen))
        self.pitch_items.append(self.scene.addLine(self.X_MAX, self.Y_MIN, self.X_MAX, self.Y_MAX, pen))
        self.pitch_items.append(self.scene.addLine(self.X_MIN, self.Y_MIN, self.X_MAX, self.Y_MIN, pen))
        self.pitch_items.append(self.scene.addLine(self.X_MIN, self.Y_MAX, self.X_MAX, self.Y_MAX, pen))
        self.pitch_items.append(self.scene.addLine(
            self.X_MIN + self.PITCH_LENGTH/2, self.Y_MIN,
            self.X_MIN + self.PITCH_LENGTH/2, self.Y_MAX,
            pen
        ))

        # Center circle
        center_x = self.X_MIN + self.PITCH_LENGTH/2
        center_y = self.Y_MIN + self.PITCH_WIDTH/2
        self.pitch_items.append(self.scene.addEllipse(
            center_x - CENTER_CIRCLE_RADIUS,
            center_y - CENTER_CIRCLE_RADIUS,
            CENTER_CIRCLE_RADIUS*2, CENTER_CIRCLE_RADIUS*2,
            pen
        ))

        # Center spot
        dot = self.scene.addEllipse(
            center_x - POINT_RADIUS,
            center_y - POINT_RADIUS,
            POINT_RADIUS*2, POINT_RADIUS*2,
            QPen(Qt.NoPen), QBrush(QColor(line_color))
        )
        self.pitch_items.append(dot)

        # Penalty spots
        left_spot = self.scene.addEllipse(
            self.X_MIN + PENALTY_SPOT_DIST - POINT_RADIUS,
            center_y - POINT_RADIUS,
            POINT_RADIUS*2, POINT_RADIUS*2,
            QPen(Qt.NoPen), QBrush(QColor(line_color))
        )
        right_spot = self.scene.addEllipse(
            self.X_MAX - PENALTY_SPOT_DIST - POINT_RADIUS,
            center_y - POINT_RADIUS,
            POINT_RADIUS*2, POINT_RADIUS*2,
            QPen(Qt.NoPen), QBrush(QColor(line_color))
        )
        self.pitch_items.extend([left_spot, right_spot])

        # Penalty areas and goal areas
        self.pitch_items.append(self.scene.addRect(
            self.X_MIN,
            self.Y_MIN + (self.PITCH_WIDTH - PENALTY_AREA_WIDTH)/2,
            PENALTY_AREA_LENGTH,
            PENALTY_AREA_WIDTH,
            pen
        ))
        self.pitch_items.append(self.scene.addRect(
            self.X_MAX - PENALTY_AREA_LENGTH,
            self.Y_MIN + (self.PITCH_WIDTH - PENALTY_AREA_WIDTH)/2,
            PENALTY_AREA_LENGTH,
            PENALTY_AREA_WIDTH,
            pen
        ))
        self.pitch_items.append(self.scene.addRect(
            self.X_MIN,
            self.Y_MIN + (self.PITCH_WIDTH - GOAL_AREA_WIDTH)/2,
            GOAL_AREA_LENGTH,
            GOAL_AREA_WIDTH,
            pen
        ))
        self.pitch_items.append(self.scene.addRect(
            self.X_MAX - GOAL_AREA_LENGTH,
            self.Y_MIN + (self.PITCH_WIDTH - GOAL_AREA_WIDTH)/2,
            GOAL_AREA_LENGTH,
            GOAL_AREA_WIDTH,
            pen
        ))

        # Goals (posts area)
        self.pitch_items.append(self.scene.addRect(
            self.X_MIN - GOAL_DEPTH,
            self.Y_MIN + (self.PITCH_WIDTH - GOAL_WIDTH)/2,
            GOAL_DEPTH, GOAL_WIDTH,
            pen
        ))
        self.pitch_items.append(self.scene.addRect(
            self.X_MAX,
            self.Y_MIN + (self.PITCH_WIDTH - GOAL_WIDTH)/2,
            GOAL_DEPTH, GOAL_WIDTH,
            pen
        ))

        # Penalty arcs
        arc_radius = 9.15

        # Left arc
        left_arc = QGraphicsPathItem()
        path_l = QPainterPath()
        path_l.arcMoveTo(
            self.X_MIN + PENALTY_SPOT_DIST - arc_radius,
            center_y           - arc_radius,
            2*arc_radius, 2*arc_radius,
            308
        )
        path_l.arcTo(
            self.X_MIN + PENALTY_SPOT_DIST - arc_radius,
            center_y           - arc_radius,
            2*arc_radius, 2*arc_radius,
            308, 104
        )
        left_arc.setPath(path_l)
        left_arc.setPen(pen)
        self.scene.addItem(left_arc)
        self.pitch_items.append(left_arc)

        # Right arc
        right_arc = QGraphicsPathItem()
        path_r = QPainterPath()
        path_r.arcMoveTo(
            self.X_MAX - PENALTY_SPOT_DIST - arc_radius,
            center_y           - arc_radius,
            2*arc_radius, 2*arc_radius,
            128
        )
        path_r.arcTo(
            self.X_MAX - PENALTY_SPOT_DIST - arc_radius,
            center_y           - arc_radius,
            2*arc_radius, 2*arc_radius,
            128, 104
        )
        right_arc.setPath(path_r)
        right_arc.setPen(pen)
        self.scene.addItem(right_arc)
        self.pitch_items.append(right_arc)

    def resizeEvent(self, event):
            """Fit the entire pitch rect on widget resize (keeps aspect ratio)."""
            super().resizeEvent(event)
            MARGIN = SCENE_EXTRA_GRASS
            rect = QRectF(
                self.X_MIN - 2*MARGIN,
                self.Y_MIN - MARGIN,
                self.PITCH_LENGTH + 4*MARGIN,
                self.PITCH_WIDTH + 2*MARGIN
            )
            self.view.setSceneRect(rect)
            self.view.fitInView(rect, Qt.KeepAspectRatio)

    def draw_player(self, x, y, main_color, sec_color, num_color, number, 
                angle=0, velocity=0, display_orientation=False, z_offset=10, 
                arrow_color=None):
        """Draw a bi-color player disc with optional orientation arrow.

        Parameters
        ----------
        x, y : float
            Player center coordinates.
        main_color, sec_color, num_color : str
            Hex colors for top half, bottom half, and number.
        number : int | str
            Shirt number (displayed on the disc).
        angle : float, default 0
            Orientation angle in radians.
        velocity : float, default 0
            Player speed (m/s), used to scale the orientation arrow.
        display_orientation : bool, default False
            Whether to draw the orientation arrow.
        z_offset : float, default 10
            Z stacking base.
        arrow_color : str | None
            Hex color for orientation arrow (defaults to theme arrow color).
        """
    
        # Use theme color if arrow_color is not provided
        if arrow_color is None:
            arrow_color = self.theme.get("arrow", "#000000")
        
        # Fetch scaled dimensions from CONFIG
        radius = CONFIG.PLAYER_OUTER_RADIUS
        inner_radius = CONFIG.PLAYER_INNER_RADIUS
        arrow_thickness = CONFIG.PLAYER_ARROW_THICKNESS
        chevron_size = CONFIG.PLAYER_CHEVRON_SIZE
        
        # Draw a player with orientation
        min_velocity = 0.01 # m/s to avoid display bugs
        if display_orientation and angle is not None and velocity is not None:
            velocity = max(velocity, min_velocity)
            arrow_length = velocity * VELOCITY_ARROW_SCALE
            arrow_x_start = x + radius * math.cos(angle)
            arrow_y_start = y + radius * math.sin(angle)
            arrow_x_end = x + (radius + arrow_length) * math.cos(angle)
            arrow_y_end = y + (radius + arrow_length) * math.sin(angle)
            arrow = self.scene.addLine(
                arrow_x_start, arrow_y_start, arrow_x_end, arrow_y_end, 
                QPen(QColor(arrow_color), arrow_thickness)
            )
            arrow.setZValue(z_offset - 2)
            self.dynamic_items.append(arrow)
            
            left_chevron_angle = angle + math.radians(PLAYER_CHEVRON_ANGLE_DEG)
            right_chevron_angle = angle - math.radians(PLAYER_CHEVRON_ANGLE_DEG)
            left_x = arrow_x_end + chevron_size * math.cos(left_chevron_angle)
            left_y = arrow_y_end + chevron_size * math.sin(left_chevron_angle)
            right_x = arrow_x_end + chevron_size * math.cos(right_chevron_angle)
            right_y = arrow_y_end + chevron_size * math.sin(right_chevron_angle)
            left_line = self.scene.addLine(arrow_x_end, arrow_y_end, left_x, left_y, 
                                        QPen(QColor(arrow_color), arrow_thickness))
            right_line = self.scene.addLine(arrow_x_end, arrow_y_end, right_x, right_y, 
                                        QPen(QColor(arrow_color), arrow_thickness))
            left_line.setZValue(z_offset - 2)
            right_line.setZValue(z_offset - 2)
            self.dynamic_items.append(left_line)
            self.dynamic_items.append(right_line)

        group = QGraphicsItemGroup()
        path_bottom = QPainterPath()
        cx, cy = 0, 0
        path_bottom.moveTo(cx, cy)
        path_bottom.arcMoveTo(cx - radius, cy - radius, 2*radius, 2*radius, 0)
        path_bottom.arcTo(cx - radius, cy - radius, 2*radius, 2*radius, 0, 180)
        path_bottom.lineTo(cx, cy)
        path_bottom.closeSubpath()
        bottom_half = QGraphicsPathItem(path_bottom)
        bottom_half.setPen(QPen(Qt.transparent, 0))
        bottom_half.setBrush(QBrush(QColor(sec_color)))
        bottom_half.setZValue(z_offset + 1)
        group.addToGroup(bottom_half)
        
        path_top = QPainterPath()
        path_top.moveTo(cx, cy)
        path_top.arcMoveTo(cx - radius, cy - radius, 2*radius, 2*radius, 180)
        path_top.arcTo(cx - radius, cy - radius, 2*radius, 2*radius, 180, 180)
        path_top.lineTo(cx, cy)
        path_top.closeSubpath()
        top_half = QGraphicsPathItem(path_top)
        top_half.setPen(QPen(Qt.transparent, 0))
        top_half.setBrush(QBrush(QColor(main_color)))
        top_half.setZValue(z_offset + 2)
        group.addToGroup(top_half)
        
        inner = QGraphicsEllipseItem(-inner_radius, -inner_radius, inner_radius*2, inner_radius*2)
        inner.setPen(QPen(Qt.transparent, 0))
        inner.setBrush(QBrush(QColor(main_color)))
        inner.setZValue(z_offset + 3)
        group.addToGroup(inner)
        
        # Adjust font size based on scale
        font = QFont("Arial")
        font.setBold(True)
        font.setPointSize(int(inner_radius * 1.8))
        text = QGraphicsTextItem(str(number))
        text.setDefaultTextColor(QColor(num_color))
        text.setFont(font)
        bounding = text.boundingRect()
        text.setZValue(z_offset + 4)
        text.setTransformOriginPoint(bounding.width()/2, bounding.height()/2)
        text.setTransform(QTransform().scale(1, -1), True)
        text_rect = text.boundingRect()
        text.setPos(-text_rect.width()/2, +text_rect.height()/2)
        group.addToGroup(text)
        group.setPos(x, y)
        deg = np.degrees(angle) + PLAYER_ROTATION_OFFSET_DEG if display_orientation else PLAYER_ROTATION_DEFAULT_DEG + PLAYER_ROTATION_OFFSET_DEG
        group.setRotation(deg)
        group.setZValue(z_offset)
        self.scene.addItem(group)
        self.dynamic_items.append(group)


    def draw_ball(self, x, y, color=None):
        """Draw the ball at (x, y).

        Parameters
        ----------
        x, y : float
            Ball center coordinates.
        color : str | None
            Hex color; defaults to theme ball color.

        Returns
        -------
        QGraphicsEllipseItem
            The created ball item.
        """
        if color is None:
            color = BALL_COLOR
        
        ball_radius = CONFIG.BALL_RADIUS
        
        ball = self.scene.addEllipse(
            x - ball_radius, y - ball_radius,
            ball_radius * 2, ball_radius * 2,
            QPen(QColor(color), 0.3), QBrush(QColor(color))
        )
        ball.setZValue(100)
        self.dynamic_items.append(ball)
        return ball


    def draw_offside_line(self, x_offside, visible=True, color=None):
        """Draw vertical offside line at x coordinate if visible and defined.

        Parameters
        ----------
        x_offside : float | None
            X coordinate for offside line; if None, nothing is drawn.
        visible : bool, default True
            Toggle visibility.
        color : str | None
            Hex color; defaults to theme offside color.

        Returns
        -------
        QGraphicsLineItem | None
            The created line or None.
        """
        if not visible:
            return None
        
        if color is None:
            color = self.theme.get("offside", "#FF40FF")
        
        if visible and x_offside is not None:
            pen = QPen(QColor(color), CONFIG.OFFSIDE_LINE_WIDTH)
            pen.setStyle(Qt.DotLine)
            line = self.scene.addLine(x_offside, self.Y_MIN, x_offside, self.Y_MAX+1, pen)
            line.setZValue(199)
            self.dynamic_items.append(line)
            return line


    def draw_pressure(self, x, y, color, opacity=0.5):
        """Draw a translucent circle to represent local pressure.

        Parameters
        ----------
        x, y : float
            Center coordinates.
        color : str | QColor
            Fill color.
        opacity : float, default 0.5
            Opacity in [0, 1].

        Returns
        -------
        QGraphicsEllipseItem
            The created pressure disk.
        """

        ellipse = QGraphicsEllipseItem(
            x - CONFIG.PLAYER_OUTER_RADIUS * 2, y - CONFIG.PLAYER_OUTER_RADIUS * 2, 2*CONFIG.PLAYER_OUTER_RADIUS * 2, 2*CONFIG.PLAYER_OUTER_RADIUS * 2
        )
        ellipse.setBrush(QBrush(QColor(color)))
        ellipse.setOpacity(opacity)
        ellipse.setPen(QPen(Qt.NoPen))
        ellipse.setZValue(110)
        self.scene.addItem(ellipse)
        self.dynamic_items.append(ellipse)
        return ellipse
        

    def draw_pressure_for_ball_carrier(
        self,
        xy_objects,
        home_ids,
        away_ids,
        dsam,
        orientations,
        half,
        idx,
        ball_xy,
        pressure_fn,
        ball_carrier_array,
        ballstatus,  
        frame_number=0,
        visible=True,
    ):
        """Draw pressure zone around the ball carrier if ball is active.

        Parameters
        ----------
        xy_objects : dict
            Positions per half/side and ball.
        home_ids, away_ids : list[str]
            Player IDs.
        dsam : dict
            DSAM metrics per player.
        orientations : dict
            Player orientations (radians).
        half : {'firstHalf','secondHalf'}
            Current half.
        idx : int
            Frame index within the half.
        ball_xy : tuple[float, float]
            Ball position at this frame.
        pressure_fn : callable
            Function computing pressure intensity in [0, 1].
        ball_carrier_array : list[tuple[str|None,str|None]]
            Carrier ID and side per global frame.
        ballstatus : array-like | dict
            Ball activity flags per frame or per-half.
        frame_number : int, default 0
            Global frame index.
        visible : bool, default True
            Toggle to draw or skip.

        Returns
        -------
        float | None
            Pressure intensity if drawn; None otherwise.
        """
        if not visible:
            return None

        # Do not draw anything if the ball is inactive at this frame
        if isinstance(ballstatus, dict):
            # Structure Floodlight standard : ballstatus['firstHalf'].code, etc.
            # Concatenate halves similar to possession
            n_first = xy_objects['firstHalf']['Home'].xy.shape[0]
            if frame_number < n_first:
                ball_active = ballstatus['firstHalf'].code[frame_number] != 0
            else:
                ball_active = ballstatus['secondHalf'].code[frame_number - n_first] != 0
        elif isinstance(ballstatus, np.ndarray) or isinstance(ballstatus, list):
            # ballstatus already flat
            ball_active = ballstatus[frame_number] != 0
        else:
            # Edge case but we don't crash
            ball_active = True

        if not ball_active:
            return None

        carrier = ball_carrier_array[frame_number]
        if carrier is None or carrier[0] is None:
            return None

        carrier_pid, carrier_side = carrier

        pressure = pressure_fn(
            ball_xy=ball_xy,
            carrier_pid=carrier_pid,
            carrier_side=carrier_side,
            home_ids=home_ids,
            away_ids=away_ids,  
            xy_objects=xy_objects,
            dsam=dsam,
            orientations=orientations,
            half=half,
            idx=idx
        )

        color = get_pressure_color(pressure)


        # Center on the carrier (not the ball)
        xy = xy_objects[half][carrier_side].xy[idx]
        i = (home_ids if carrier_side=="Home" else away_ids).index(carrier_pid)
        x, y = xy[2*i], xy[2*i+1]

        self.draw_pressure(x, y, color=color)
        return pressure
