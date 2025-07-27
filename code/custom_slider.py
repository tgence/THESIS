# custom_slider.py

from PyQt5.QtWidgets import QSlider, QToolTip, QWidget, QVBoxLayout, QLabel, QFrame
from PyQt5.QtCore import Qt, QEvent, pyqtSignal, QRect, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QCursor
from visualization import format_match_time
from config import *
import sys


class TimelineSlider(QSlider):
    hoverFrameChanged = pyqtSignal(int, str)  # frame, time_str
    def __init__(self, n_frames_firstHalf, n_frames_secondHalf, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.n_frames_firstHalf = n_frames_firstHalf
        self.n_frames_secondHalf = n_frames_secondHalf
        self.setMouseTracking(True)
        self.hover_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.width() > 0:
            ratio = event.x() / self.width()
            frame = int(ratio * self.maximum())
            frame = max(0, min(frame, self.maximum()))
            self.setValue(frame)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if self.width() > 0:
            ratio = event.x() / self.width()
            frame = int(ratio * self.maximum())
            frame = max(0, min(frame, self.maximum()))
            if event.buttons() & Qt.LeftButton:
                self.setValue(frame)
            time_str = format_match_time(frame, self.n_frames_firstHalf, self.n_frames_secondHalf, fps=FPS)
            self.hover_pos = event.x()
            self.hoverFrameChanged.emit(frame, time_str)
            self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        QToolTip.hideText()
        self.hover_pos = None
        # ==> Remet le label au temps réel (handle) quand la souris quitte la barre
        if self.parent() and hasattr(self.parent(), '_update_time_label_on_value'):
            self.parent()._update_time_label_on_value(self.value())
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.hover_pos is not None:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(QColor(150, 150, 150, 100), 1)
            painter.setPen(pen)
            painter.drawLine(self.hover_pos, 0, self.hover_pos, self.height())

class ActionMarker(QWidget):
    clicked = pyqtSignal(int)
    def __init__(self, action_data, parent=None):
        super().__init__(parent)
        self.action = action_data
        self.setFixedSize(20, 20)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont("Segoe UI Emoji", 14)
        if not font.exactMatch():
            font = QFont("Arial", 14)
        painter.setFont(font)

        # Surbrillance si sélectionné
        parent = self.parentWidget()
        selected = False
        if parent is not None and hasattr(parent.parentWidget(), "selected_frame"):
            selected = self.action['frame'] == parent.parentWidget().selected_frame
        if selected:
            size = self.width()  # Carré qui occupe tout le widget
            painter.setBrush(QColor(33, 150, 243, 50))  # bleu semi-transparent
            painter.setPen(QPen(QColor(33, 150, 243), 2))  # contour bleu fin
            painter.drawRect(0, 0, size, size)
        else:
            painter.setPen(QColor(0, 0, 0, 50))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(self.rect(), Qt.AlignCenter, self.action['emoji'])
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.action['frame'])


class TimelineWidget(QWidget):
    frameChanged = pyqtSignal(int)
    def __init__(self, n_frames, n_frames_firstHalf, n_frames_secondHalf, parent=None):
        super().__init__(parent)
        self.n_frames = n_frames
        self.n_frames_firstHalf = n_frames_firstHalf
        self.n_frames_secondHalf = n_frames_secondHalf
        self.action_markers = []
        self.actions_data = []
        self.filtered_types = []
        self.filtered_actions = []
        self.zoom_widget = None
        self.selected_frame = None
        self.has_selected_types = False  # NOUVEAU: flag pour savoir si des types ont été sélectionnés

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 30, 20, 5)
        layout.setSpacing(0)

        parent_width = self.parent().width() if self.parent() else 900
        margin_buttons = 250
        timeline_width = max(MIN_TIMELINE_WIDTH, min(parent_width - margin_buttons, MAX_TIMELINE_WIDTH))
        self.setMaximumWidth(timeline_width)

        # Bar d'emojis
        self.markers_container = QWidget(self)
        self.markers_container.setMinimumHeight(50)
        self.markers_container.setMaximumHeight(50)
        layout.addWidget(self.markers_container)
        self.markers_container.setMouseTracking(True)
        self.markers_container.installEventFilter(self)

        # Slider
        self.slider = TimelineSlider(self.n_frames_firstHalf, self.n_frames_secondHalf)
        self.slider.setMinimum(0)
        self.slider.setMaximum(self.n_frames - 1)
        self.slider.setFixedHeight(TIMELINE_SLIDER_HEIGHT)
        self.slider.valueChanged.connect(self.frameChanged.emit)
        layout.addWidget(self.slider)
        self.slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: {TIMELINE_GROOVE_HEIGHT}px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
                margin: 0px;
            }}
            QSlider::handle:horizontal {{
                width: {TIMELINE_HANDLE_WIDTH}px;
                height: {TIMELINE_HANDLE_HEIGHT}px;
                margin: -{(TIMELINE_HANDLE_HEIGHT - TIMELINE_GROOVE_HEIGHT)//2}px 0px;
                background: #2196F3;
                border: 0px solid transparent;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal:hover {{
                background: #42A5F5;
            }}
            QSlider::sub-page:horizontal {{
                background: #2196F3;
                border-radius: 3px;
            }}
        """)

        self.time_label = QLabel("")
        self.time_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(self.time_label)
        self.slider.valueChanged.connect(self._update_time_label_on_value)
        self.slider.hoverFrameChanged.connect(self._update_time_label)

        self.setMouseTracking(True)

    def _update_time_label_on_value(self, frame):
        time_str = format_match_time(
            frame, self.n_frames_firstHalf, self.n_frames_secondHalf, fps=FPS
        )
        self.time_label.setText(time_str)

    def _update_time_label(self, frame, time_str):
        self.time_label.setText(time_str)

    def show_zoomed_markers(self, center_frame, max_actions=10):
        # Trie par ordre d'apparition (frame)
        all_actions = sorted(self.filtered_actions, key=lambda a: a['frame'])
        idx = next((i for i, a in enumerate(all_actions) if a['frame'] == center_frame), None)
        if idx is None:
            self.hide_zoomed_markers()
            return

        # Prend jusqu'à 4 avant, 5 après (centré, 10 max)
        start = max(0, idx - 4)
        end = min(len(all_actions), idx + 6)
        actions_zoom = all_actions[start:end]

        if not actions_zoom:
            self.hide_zoomed_markers()
            return

        # Toujours clean le widget précédent
        self.hide_zoomed_markers()

        self.zoom_widget = ZoomedMarkersWidget(actions_zoom, center_frame, self.n_frames, self)
        self.zoom_widget.setFixedWidth(self.markers_container.width())
        self.zoom_widget.emojiClicked.connect(self.setValue)
        self.zoom_widget.closeRequested.connect(self.hide_zoomed_markers)
        self.zoom_widget.selected_frame = center_frame  # <- pour la surbrillance

        pos = self.markers_container.mapToGlobal(self.markers_container.rect().bottomLeft())
        self.zoom_widget.move(pos)
        self.zoom_widget.show()
        self.zoom_widget.raise_()

    def hide_zoomed_markers(self):
        if self.zoom_widget:
            self.zoom_widget.hide()
            self.zoom_widget.deleteLater()
            self.zoom_widget = None

    def set_actions(self, actions_data):
        self.actions_data = actions_data
        self.update_markers()

    def set_filtered_types(self, action_types):
        self.filtered_types = action_types
        # NOUVEAU: Mettre à jour le flag pour savoir si des types ont été sélectionnés
        self.has_selected_types = len(action_types) > 0
        self.update_markers()

    def update_markers(self):
        # MODIFIÉ: Ne filtrer les actions que si des types ont été explicitement sélectionnés
        if self.has_selected_types:
            # Si des types sont sélectionnés, filtrer selon ces types
            self.filtered_actions = [
                a for a in self.actions_data
                if a['label'] in self.filtered_types
            ]
        else:
            # Si aucun type n'est sélectionné, ne rien afficher
            self.filtered_actions = []

        # Nettoyage
        for marker in self.action_markers:
            marker.deleteLater()
        self.action_markers.clear()
        for child in self.markers_container.children():
            if isinstance(child, QWidget):
                child.deleteLater()

        # MODIFIÉ: Créer les marqueurs seulement s'il y a des actions filtrées
        if self.filtered_actions:
            slider_width = max(1, self.markers_container.width())
            for action in self.filtered_actions:
                x_pos = round(action['frame'] * (slider_width - 1) / (self.n_frames - 1))
                marker = ActionMarker(action, parent=self.markers_container)
                marker.move(x_pos, 0)
                marker.clicked.connect(self.handle_marker_click)
                marker.show()
                self.action_markers.append(marker)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.markers_container.setFixedWidth(self.slider.width())
        self.markers_container.move(0, 0)
        self.slider.setMinimum(0)
        self.slider.setMaximum(self.n_frames - 1)
        self.update_markers()

    def handle_marker_click(self, frame):
        self.selected_frame = frame
        self.show_zoomed_markers(frame, max_actions=10)
        self.update_markers()  # pour redraw la barre principale avec la surbrillance

    def value(self):
        return self.slider.value()

    def setValue(self, value):
        self.slider.setValue(value)

    def setMaximum(self, value):
        self.slider.setMaximum(value)


class ZoomedMarkersWidget(QFrame):
    emojiClicked = pyqtSignal(int)
    closeRequested = pyqtSignal()  # nouveau signal pour fermeture
    
    def __init__(self, actions, center_frame, n_frames, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setMouseTracking(True)
        self.setFixedHeight(48)
        self.setMinimumWidth(220)
        self.setStyleSheet("background: rgba(40,40,40, 0.98); border: 2px solid #2196F3; border-radius: 8px;")
        self.set_actions(actions, center_frame)
        self.installEventFilter(self)
        self.emoji_hitboxes = []
        self.selected_frame = center_frame
        self.n_frames = n_frames

    def set_actions(self, actions, center_frame):
        self.actions = actions
        self.center_frame = center_frame
        self.selected_frame = center_frame
        self.update()

    def eventFilter(self, obj, event):
        # Désactive la fermeture automatique
        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width = self.width()
        # --- Dessin du bouton croix ---
        cross_size = 18
        margin = 7
        cross_rect = QRect(width - cross_size - margin, margin, cross_size, cross_size)
        painter.setPen(QColor(255, 80, 80))
        painter.setBrush(QColor(255, 80, 80, 100))
        painter.drawRect(cross_rect)
        painter.setPen(QColor(255, 255, 255))
        painter.drawLine(
            cross_rect.left() + 4, cross_rect.top() + 4,
            cross_rect.right() - 4, cross_rect.bottom() - 4
        )
        painter.drawLine(
            cross_rect.right() - 4, cross_rect.top() + 4,
            cross_rect.left() + 4, cross_rect.bottom() - 4
        )
        self.cross_rect = cross_rect

        visible_actions = self.actions
        N = len(visible_actions)
        self.emoji_hitboxes = []
        for i, a in enumerate(visible_actions):
            x_pos = int((i+1) * (width / (N+1)))
            emoji = a.get('emoji', '')
            time = a.get('display_time', '')
            team = a.get('team', '')
            font = QFont("Apple Color Emoji" if sys.platform == "darwin" else "Segoe UI Emoji", 24)
            painter.setFont(font)
            # --- Surbrillance ---
            selected = (a['frame'] == self.selected_frame)
            if selected:
                painter.setBrush(QColor(33, 150, 243, 50))
                painter.setPen(QPen(QColor(33, 150, 243), 2))
                painter.drawRect(x_pos-18, 10, 36, 36)  # carré bleu, même taille que l'emoji

            painter.setPen(QColor(255,255,255,255))
            painter.drawText(x_pos-12, 30, emoji)
            mouse = self.mapFromGlobal(QCursor.pos())
            if abs(mouse.x() - x_pos) < 24 and 0 < mouse.y() < self.height():
                QToolTip.showText(self.mapToGlobal(mouse), f"{emoji} {a.get('label','')} - {time}\n{a.get('team','')}", self)
            painter.setFont(QFont("Arial", 9))
            painter.setPen(QColor(200,200,200,200))
            painter.drawText(x_pos-20, 44, f"{time} {team}")
            self.emoji_hitboxes.append((x_pos-20, x_pos+20, a['frame']))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Clique sur la croix ?
            if hasattr(self, "cross_rect") and self.cross_rect.contains(event.pos()):
                self.closeRequested.emit()
                return
            x = event.x()
            for x_min, x_max, frame in self.emoji_hitboxes:
                if x_min <= x <= x_max:
                    self.emojiClicked.emit(frame)
        super().mousePressEvent(event)