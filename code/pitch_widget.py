# pitch_widget.py
 
import numpy as np
import math
from PyQt5.QtWidgets import (
    QWidget, QGraphicsScene, QGraphicsView, QVBoxLayout, QGraphicsEllipseItem, QGraphicsPathItem, 
    QGraphicsTextItem, QGraphicsRectItem, QGraphicsItemGroup
)
from PyQt5.QtGui import QPen, QBrush, QColor, QFont, QPainterPath, QTransform
from PyQt5.QtCore import Qt

from config import *

class PitchWidget(QWidget):
    def __init__(self, X_MIN, X_MAX, Y_MIN, Y_MAX, parent=None):
        super().__init__(parent)
        self.X_MIN = X_MIN
        self.X_MAX = X_MAX
        self.Y_MIN = Y_MIN
        self.Y_MAX = Y_MAX
        self.PITCH_LENGTH = X_MAX - X_MIN
        self.PITCH_WIDTH = Y_MAX - Y_MIN

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(self.view.renderHints() | self.view.renderHints())
        self.view.scale(1, -1)
        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        self.setLayout(layout)
        self.draw_pitch()

    def draw_pitch(self):
        self.scene.clear()
        # Herbe autour du terrain
        X_MIN = self.X_MIN
        X_MAX = self.X_MAX
        Y_MIN = self.Y_MIN
        Y_MAX = self.Y_MAX
        PITCH_LENGTH = self.PITCH_LENGTH
        PITCH_WIDTH = self.PITCH_WIDTH
        grass = QGraphicsRectItem(
            X_MIN - SCENE_EXTRA_GRASS, Y_MIN - SCENE_EXTRA_GRASS,
            PITCH_LENGTH + 2*SCENE_EXTRA_GRASS, PITCH_WIDTH + 2*SCENE_EXTRA_GRASS
        )
        grass.setBrush(QBrush(QColor("#1b5e20")))
        grass.setPen(QPen(Qt.NoPen))
        self.scene.addItem(grass)

        # Terrain principal
        field = self.scene.addRect(
            X_MIN, Y_MIN, PITCH_LENGTH, PITCH_WIDTH,
            QPen(Qt.white, LINE_WIDTH), QBrush(QColor("#08711a"))
        )
        field.setZValue(-10)

        # Lignes principales
        self.scene.addLine(X_MIN, Y_MIN, X_MIN, Y_MAX, QPen(Qt.white, LINE_WIDTH))
        self.scene.addLine(X_MAX, Y_MIN, X_MAX, Y_MAX, QPen(Qt.white, LINE_WIDTH))
        self.scene.addLine(X_MIN, Y_MIN, X_MAX, Y_MIN, QPen(Qt.white, LINE_WIDTH))
        self.scene.addLine(X_MIN, Y_MAX, X_MAX, Y_MAX, QPen(Qt.white, LINE_WIDTH))
        self.scene.addLine(X_MIN + PITCH_LENGTH/2, Y_MIN, X_MIN + PITCH_LENGTH/2, Y_MAX, QPen(Qt.white, LINE_WIDTH))
        self.scene.addEllipse(
            (X_MIN + PITCH_LENGTH/2) - CENTER_CIRCLE_RADIUS, (Y_MIN + PITCH_WIDTH/2) - CENTER_CIRCLE_RADIUS,
            CENTER_CIRCLE_RADIUS*2, CENTER_CIRCLE_RADIUS*2, QPen(Qt.white, LINE_WIDTH)
        )
        # Point central
        self.scene.addEllipse(
            (X_MIN + PITCH_LENGTH/2) - POINT_RADIUS,
            (Y_MIN + PITCH_WIDTH/2) - POINT_RADIUS,
            POINT_RADIUS*2, POINT_RADIUS*2,
            QPen(Qt.NoPen), QBrush(Qt.white)
        )
        # Points de penalty
        self.scene.addEllipse(X_MIN+PENALTY_SPOT_DIST-POINT_RADIUS, Y_MIN+PITCH_WIDTH/2-POINT_RADIUS, POINT_RADIUS*2, POINT_RADIUS*2, QPen(Qt.NoPen), QBrush(Qt.white))
        self.scene.addEllipse(X_MAX-PENALTY_SPOT_DIST-POINT_RADIUS, Y_MIN+PITCH_WIDTH/2-POINT_RADIUS, POINT_RADIUS*2, POINT_RADIUS*2, QPen(Qt.NoPen), QBrush(Qt.white))
        # Surfaces
        self.scene.addRect(X_MIN, Y_MIN + (PITCH_WIDTH-PENALTY_AREA_WIDTH)/2, PENALTY_AREA_LENGTH, PENALTY_AREA_WIDTH, QPen(Qt.white, LINE_WIDTH))
        self.scene.addRect(X_MAX-PENALTY_AREA_LENGTH, Y_MIN + (PITCH_WIDTH-PENALTY_AREA_WIDTH)/2, PENALTY_AREA_LENGTH, PENALTY_AREA_WIDTH, QPen(Qt.white, LINE_WIDTH))
        self.scene.addRect(X_MIN, Y_MIN + (PITCH_WIDTH-GOAL_AREA_WIDTH)/2, GOAL_AREA_LENGTH, GOAL_AREA_WIDTH, QPen(Qt.white, LINE_WIDTH))
        self.scene.addRect(X_MAX-GOAL_AREA_LENGTH, Y_MIN + (PITCH_WIDTH-GOAL_AREA_WIDTH)/2, GOAL_AREA_LENGTH, GOAL_AREA_WIDTH, QPen(Qt.white, LINE_WIDTH))
        # Buts
        self.scene.addRect(X_MIN - GOAL_DEPTH, Y_MIN + (PITCH_WIDTH-GOAL_WIDTH)/2, GOAL_DEPTH, GOAL_WIDTH, QPen(Qt.white, LINE_WIDTH))
        self.scene.addRect(X_MAX, Y_MIN + (PITCH_WIDTH-GOAL_WIDTH)/2, GOAL_DEPTH, GOAL_WIDTH, QPen(Qt.white, LINE_WIDTH))
        # Arcs de penalty
        arc_radius = 9.15
        # Gauche
        arc_center_left = (X_MIN + PENALTY_SPOT_DIST, Y_MIN + PITCH_WIDTH / 2)
        left_arc = QGraphicsPathItem()
        path_left = QPainterPath()
        path_left.arcMoveTo(
            arc_center_left[0] - arc_radius, arc_center_left[1] - arc_radius,
            2 * arc_radius, 2 * arc_radius, 308
        )
        path_left.arcTo(
            arc_center_left[0] - arc_radius, arc_center_left[1] - arc_radius,
            2 * arc_radius, 2 * arc_radius, 308, 104
        )
        left_arc.setPath(path_left)
        left_arc.setPen(QPen(Qt.white, LINE_WIDTH))
        self.scene.addItem(left_arc)
        # Droite
        arc_center_right = (X_MAX - PENALTY_SPOT_DIST, Y_MIN + PITCH_WIDTH / 2)
        right_arc = QGraphicsPathItem()
        path_right = QPainterPath()
        path_right.arcMoveTo(
            arc_center_right[0] - arc_radius, arc_center_right[1] - arc_radius,
            2 * arc_radius, 2 * arc_radius, 128
        )
        path_right.arcTo(
            arc_center_right[0] - arc_radius, arc_center_right[1] - arc_radius,
            2 * arc_radius, 2 * arc_radius, 128, 104
        )
        right_arc.setPath(path_right)
        right_arc.setPen(QPen(Qt.white, LINE_WIDTH))
        self.scene.addItem(right_arc)


    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def draw_player(self, x, y, main_color, sec_color, num_color, number, angle=0, velocity=0, display_orientation=False, z_offset=10):
        # Dessin d’un joueur avec orientation
        if display_orientation and angle is not None and velocity is not None:
            arrow_length = velocity * VELOCITY_ARROW_SCALE
            arrow_x_start = x + PLAYER_OUTER_RADIUS * math.cos(angle)
            arrow_y_start = y + PLAYER_OUTER_RADIUS * math.sin(angle)
            arrow_x_end = x + (PLAYER_OUTER_RADIUS + arrow_length) * math.cos(angle)
            arrow_y_end = y + (PLAYER_OUTER_RADIUS + arrow_length) * math.sin(angle)
            arrow = self.scene.addLine(
                arrow_x_start, arrow_y_start, arrow_x_end, arrow_y_end, QPen(QColor("black"), PLAYER_ARROW_THICKNESS)
            )
            arrow.setZValue(z_offset - 2)
            chevron_size = PLAYER_CHEVRON_SIZE
            left_chevron_angle = angle + math.radians(PLAYER_CHEVRON_ANGLE_DEG)
            right_chevron_angle = angle - math.radians(PLAYER_CHEVRON_ANGLE_DEG)
            left_x = arrow_x_end + chevron_size * math.cos(left_chevron_angle)
            left_y = arrow_y_end + chevron_size * math.sin(left_chevron_angle)
            right_x = arrow_x_end + chevron_size * math.cos(right_chevron_angle)
            right_y = arrow_y_end + chevron_size * math.sin(right_chevron_angle)
            left_line = self.scene.addLine(arrow_x_end, arrow_y_end, left_x, left_y, QPen(QColor("black"), PLAYER_ARROW_THICKNESS))
            right_line = self.scene.addLine(arrow_x_end, arrow_y_end, right_x, right_y, QPen(QColor("black"), PLAYER_ARROW_THICKNESS))
            left_line.setZValue(z_offset - 2)
            right_line.setZValue(z_offset - 2)
        # Groupe du joueur
        group = QGraphicsItemGroup()
        path_bottom = QPainterPath()
        cx, cy, r = 0, 0, PLAYER_OUTER_RADIUS
        path_bottom.moveTo(cx, cy)
        path_bottom.arcMoveTo(cx - r, cy - r, 2*r, 2*r, 0)
        path_bottom.arcTo(cx - r, cy - r, 2*r, 2*r, 0, 180)
        path_bottom.lineTo(cx, cy)
        path_bottom.closeSubpath()
        bottom_half = QGraphicsPathItem(path_bottom)
        bottom_half.setPen(QPen(Qt.transparent, 0))
        bottom_half.setBrush(QBrush(QColor(sec_color)))
        bottom_half.setZValue(z_offset + 1)
        group.addToGroup(bottom_half)
        path_top = QPainterPath()
        path_top.moveTo(cx, cy)
        path_top.arcMoveTo(cx - r, cy - r, 2*r, 2*r, 180)
        path_top.arcTo(cx - r, cy - r, 2*r, 2*r, 180, 180)
        path_top.lineTo(cx, cy)
        path_top.closeSubpath()
        top_half = QGraphicsPathItem(path_top)
        top_half.setPen(QPen(Qt.transparent, 0))
        top_half.setBrush(QBrush(QColor(main_color)))
        top_half.setZValue(z_offset + 2)
        group.addToGroup(top_half)
        inner = QGraphicsEllipseItem(-PLAYER_INNER_RADIUS, -PLAYER_INNER_RADIUS, PLAYER_INNER_RADIUS*2, PLAYER_INNER_RADIUS*2)
        inner.setPen(QPen(Qt.transparent, 0))
        inner.setBrush(QBrush(QColor(main_color)))
        inner.setZValue(z_offset + 3)
        group.addToGroup(inner)
        font = QFont("Arial")
        font.setBold(True)
        font.setPointSize(int(PLAYER_INNER_RADIUS*1.8))
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

    def draw_ball(self, x, y):
        ball = self.scene.addEllipse(
            x - BALL_RADIUS, y - BALL_RADIUS,
            BALL_RADIUS * 2, BALL_RADIUS * 2,
            QPen(Qt.darkYellow, 0.3), QBrush(QColor("orange"))
        )
        ball.setZValue(100)
        return ball

    def draw_offside_line(self, x_offside, color="#FF40FF", style="dotted", visible=True):
        if visible and x_offside is not None:
            pen = QPen(QColor(color), OFFSIDE_LINE_WIDTH)
            pen.setStyle(Qt.DotLine if style == "dotted" else Qt.SolidLine)
            line = self.scene.addLine(x_offside, self.Y_MIN, x_offside, self.Y_MAX+1, pen)
            line.setZValue(199)
            return line
