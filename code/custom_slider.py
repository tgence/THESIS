# custom_slider.py

from PyQt5.QtWidgets import QSlider, QToolTip, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor, QFont
from visualization import format_match_time
from config import *

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
        font = QFont("Segoe UI Emoji", 9)
        if not font.exactMatch():
            font = QFont("Arial", 12)
        painter.setFont(font)
        painter.setPen(QColor(0, 0, 0, 50))
        painter.drawText(self.rect().adjusted(1, 1, 1, 1), Qt.AlignCenter, self.action['emoji'])
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(self.rect(), Qt.AlignCenter, self.action['emoji'])

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.action['frame'])

    def enterEvent(self, event):
        self.setFixedSize(30, 30)
        self.update()
        tooltip = f"{self.action['emoji']} {self.action['label']} - {self.action['display_time']}\n{self.action['team']}"
        QToolTip.showText(event.globalPos(), tooltip, self)

    def leaveEvent(self, event):
        self.setFixedSize(20, 20)
        self.update()
        QToolTip.hideText()

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
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 30, 20, 5)
        layout.setSpacing(0)

        parent_width = self.parent().width() if self.parent() else 900
        margin_buttons = 250  # ajuste selon la taille totale de tes boutons à gauche/droite
        timeline_width = max(MIN_TIMELINE_WIDTH, min(parent_width - margin_buttons, MAX_TIMELINE_WIDTH))
        self.setMaximumWidth(timeline_width)



        # Container pour les marqueurs
        self.markers_container = QWidget(self)
        self.markers_container.setMinimumHeight(30)
        layout.addWidget(self.markers_container)

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

    def _update_time_label_on_value(self, frame):
        # Affiche le temps réel du slider (handle)
        time_str = format_match_time(
            frame, self.n_frames_firstHalf, self.n_frames_secondHalf, fps=FPS
        )
        self.time_label.setText(time_str)

    def _update_time_label(self, frame, time_str):
        # Affiche le temps pointé par la souris (hover)
        self.time_label.setText(time_str)


    def set_actions(self, actions_data):
        self.actions_data = actions_data
        self.update_markers()

    def set_filtered_types(self, action_types):
        self.filtered_types = action_types
        self.update_markers()

    def update_markers(self):
        for marker in self.action_markers:
            marker.deleteLater()
        self.action_markers.clear()

        filtered_actions = [
            a for a in self.actions_data
            if not self.filtered_types or a['label'] in self.filtered_types
        ]
        # Nettoyage complet du container
        for child in self.markers_container.children():
            if isinstance(child, QWidget):
                child.deleteLater()

        slider_width = max(1, self.slider.width())
        for action in filtered_actions:
            x_pos = round(action['frame'] * (slider_width - 1) / (self.n_frames - 1))
            marker = ActionMarker(action, parent=self.markers_container)
            marker.move(x_pos, 0)
            marker.clicked.connect(self.slider.setValue)
            marker.show()
            self.action_markers.append(marker)


    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.markers_container.setFixedWidth(self.slider.width())
        self.markers_container.move(0, 0)
        self.slider.setMinimum(0)
        self.slider.setMaximum(self.n_frames - 1)
        self.update_markers()

    def value(self):
        return self.slider.value()

    def setValue(self, value):
        self.slider.setValue(value)

    def setMaximum(self, value):
        self.slider.setMaximum(value)

