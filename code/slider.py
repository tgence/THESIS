# slider.py
"""
Timeline widgets: slider with hover preview and action markers.

Contains:
- `TimelineSlider`: QSlider with hover frame/time preview
- `ActionMarker`: clickable emoji marker for an action
- `TimelineWidget`: slider + markers + zoomed overlay with action context
- `ZoomedMarkersWidget`: floating strip showing nearby actions
"""

from PyQt6.QtWidgets import QSlider, QToolTip, QWidget, QVBoxLayout, QLabel, QFrame, QApplication, QHBoxLayout
from PyQt6.QtCore import QEvent, pyqtSignal, QRect, QTimer, Qt
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QCursor, QBrush
from data_processing import format_match_time
from config import *
import sys


class TimelineSlider(QSlider):
    """Slider that shows a hover preview line and time tooltip."""
    hoverFrameChanged = pyqtSignal(int, str)  # frame, time_str
    def __init__(self, n_frames_firstHalf, n_frames_secondHalf, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.n_frames_firstHalf = n_frames_firstHalf
        self.n_frames_secondHalf = n_frames_secondHalf
        self.setMouseTracking(True)
        self.hover_pos = None
        self.hover_time_str = ""
        self.hover_frame = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.width() > 0:
            ratio = event.position().x() / self.width()
            frame = int(ratio * self.maximum())
            frame = max(0, min(frame, self.maximum()))
            self.setValue(frame)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if self.width() > 0:
            ratio = event.position().x() / self.width()
            frame = int(ratio * self.maximum())
            frame = max(0, min(frame, self.maximum()))
            if event.buttons() & Qt.MouseButton.LeftButton:
                self.setValue(frame)
            time_str = format_match_time(frame, self.n_frames_firstHalf, self.n_frames_secondHalf, fps=FPS)
            self.hover_pos = int(event.position().x())
            self.hover_time_str = time_str
            self.hover_frame = frame
            self.hoverFrameChanged.emit(frame, time_str)
            self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        QToolTip.hideText()
        self.hover_pos = None
        self.hover_time_str = ""
        self.hover_frame = None
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if self.hover_pos is not None and self.hover_frame is not None:
            current_value = self.value()
            
            # Preview bar between real cursor and hover cursor
            real_pos = (current_value / self.maximum()) * self.width() if self.maximum() > 0 else 0
            hover_pos = self.hover_pos
            
            if abs(hover_pos - real_pos) > 2:
                start_x = min(real_pos, hover_pos)
                end_x = max(real_pos, hover_pos)
                y_center = self.height() // 2
                bar_y = y_center - TIMELINE_GROOVE_HEIGHT // 2
                
                preview_brush = QBrush(QColor(33, 150, 243, 60))
                painter.setBrush(preview_brush)
                painter.setPen(QPen(Qt.PenStyle.NoPen))
                painter.drawRect(int(start_x), bar_y, int(end_x - start_x), TIMELINE_GROOVE_HEIGHT)
            
            # Imaginary cursor line at hover position
            preview_pen = QPen(QColor(33, 150, 243, 120), 1)
            painter.setPen(preview_pen)
            painter.drawLine(self.hover_pos, 0, self.hover_pos, self.height())
            
            # Tooltip at the same height as the time label in the bottom-left
            current_hover_time = format_match_time(self.hover_frame, self.n_frames_firstHalf, self.n_frames_secondHalf, fps=FPS)
            
            font = QFont("Arial", 11)  # same size as the bottom-left time label
            painter.setFont(font)
            fm = painter.fontMetrics()
            text_width = fm.horizontalAdvance(current_hover_time)
            text_height = fm.height()
            
            # Next to the hover cursor, same height as real time label
            tooltip_x = self.hover_pos + 10  # 10px to the right of the cursor
            tooltip_y = 15
            
            # Keep the tooltip inside the widget bounds
            if tooltip_x + text_width > self.width() - 5:
                tooltip_x = self.hover_pos - text_width - 10  # to the left of the cursor
            
            # Tooltip background
            padding = 3
            painter.setBrush(QBrush(QColor(30, 30, 30, 200)))
            painter.setPen(QPen(QColor(33, 150, 243), 1))
            painter.drawRoundedRect(tooltip_x - padding, tooltip_y - text_height - padding + 3, 
                                text_width + 2*padding, text_height + 2*padding, 3, 3)
            
            # Tooltip text
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(tooltip_x, tooltip_y, current_hover_time)

class ActionMarker(QWidget):
    """Small clickable widget that draws an emoji for an action."""
    clicked = pyqtSignal(int)
    def __init__(self, action_data, parent=None):
        super().__init__(parent)
        self.action = action_data
        self.setFixedSize(20, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont("Segoe UI Emoji", 14)
        if not font.exactMatch():
            font = QFont("Arial", 14)
        painter.setFont(font)

        # Highlight if selected
        parent = self.parentWidget()
        selected = False
        if parent is not None and hasattr(parent.parentWidget(), "selected_frame"):
            selected = self.action['frame'] == parent.parentWidget().selected_frame
        if selected:
            size = self.width()  # full-size square highlight
            painter.setBrush(QColor(33, 150, 243, 50))  # semi-transparent blue
            painter.setPen(QPen(QColor(33, 150, 243), 2))  # thin blue outline
            painter.drawRect(0, 0, size, size)
        else:
            painter.setPen(QColor(0, 0, 0, 50))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.action['emoji'])
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.action['frame'])


class TimelineWidget(QWidget):
    """Composite timeline with slider and action markers/zoom overlay."""
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
        self.has_selected_types = False  # NEW: flag to know if types have been selected

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 30, 0, 5)
        layout.setSpacing(0)

        parent_width = self.parent().width() if self.parent() else 900
        margin_buttons = 250
        timeline_width = max(MIN_TIMELINE_WIDTH, min(parent_width - margin_buttons, MAX_TIMELINE_WIDTH))
        self.setFixedWidth(timeline_width)

        # Emoji bar
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
        
        # === Container for the time label (bottom-left, larger) ===
        time_container = QWidget()
        time_container.setFixedHeight(30)
        time_layout = QHBoxLayout(time_container)
        time_layout.setContentsMargins(0, 8, 0, 0)  # extra bottom space
        
        self.time_label = QLabel("00:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.time_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 13px;                 /* larger */
                font-family: Arial;
                font-weight: 500;               /* slightly bolder */
                background: transparent;
                padding: 3px 6px;
            }
        """)
        
        time_layout.addWidget(self.time_label)
        time_layout.addStretch()
        layout.addWidget(time_container)

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

        self.slider.valueChanged.connect(self._update_time_label_on_value)

        self.setMouseTracking(True)


    def _update_time_label_on_value(self, frame):
        """Update ONLY the real cursor time (bottom left)"""
        time_str = format_match_time(
            frame, self.n_frames_firstHalf, self.n_frames_secondHalf, fps=FPS
        )
        self.time_label.setText(time_str)


    def show_zoomed_markers(self, center_frame, max_actions=10):
        # Sort by chronological frame
        all_actions = sorted(self.filtered_actions, key=lambda a: a['frame'])
        idx = next((i for i, a in enumerate(all_actions) if a['frame'] == center_frame), None)
        if idx is None:
            self.hide_zoomed_markers()
            return

        # Take up to 4 before and 5 after (centered, max 10)
        start = max(0, idx - 4)
        end = min(len(all_actions), idx + 6)
        actions_zoom = all_actions[start:end]

        if not actions_zoom:
            self.hide_zoomed_markers()
            return

        # Always clean up previous zoom widget
        self.hide_zoomed_markers()

        self.zoom_widget = ZoomedMarkersWidget(actions_zoom, center_frame, self.n_frames, self)
        self.zoom_widget.setFixedWidth(self.markers_container.width())
        self.zoom_widget.emojiClicked.connect(self.setValue)
        self.zoom_widget.closeRequested.connect(self.hide_zoomed_markers)
        self.zoom_widget.selected_frame = center_frame  # <- for highlighting

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
        # NEW: Update flag to know if types have been selected
        self.has_selected_types = len(action_types) > 0
        self.update_markers()

    def update_markers(self):
        # MODIFIED: Only filter actions if types have been explicitly selected
        if self.has_selected_types:
            # If types are selected, filter according to these types
            self.filtered_actions = [
                a for a in self.actions_data
                if a['label'] in self.filtered_types
            ]
        else:
            # If no type is selected, display nothing
            self.filtered_actions = []

        # Nettoyage
        for marker in self.action_markers:
            marker.deleteLater()
        self.action_markers.clear()
        for child in self.markers_container.children():
            if isinstance(child, QWidget):
                child.deleteLater()

        # MODIFIED: Create markers only if there are filtered actions
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
        self.update_markers()  # to redraw main bar with highlighting

    def value(self):
        return self.slider.value()

    def setValue(self, value):
        self.slider.setValue(value)

    def setMaximum(self, value):
        self.slider.setMaximum(value)


class ZoomedMarkersWidget(QFrame):
    """Floating overlay showing a small set of actions around a selected one."""
    emojiClicked = pyqtSignal(int)
    closeRequested = pyqtSignal()  # new signal for closing
    
    def __init__(self, actions, center_frame, n_frames, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
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
        # Handle focus loss to close automatically
        if event.type() == QEvent.Type.WindowDeactivate:
            # Optional: close automatically when losing focus
            # self.closeRequested.emit()
            pass
        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = self.width()
        
        # --- Drawing the close button ---
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
                painter.drawRect(x_pos-18, 10, 36, 36)

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
        if event.button() == Qt.MouseButton.LeftButton:
            # Click on the close button?
            if hasattr(self, "cross_rect") and self.cross_rect.contains(event.position().toPoint()):
                self.closeRequested.emit()
                return
            x = int(event.position().x())
            for x_min, x_max, frame in self.emoji_hitboxes:
                if x_min <= x <= x_max:
                    self.emojiClicked.emit(frame)
        super().mousePressEvent(event)

    def showEvent(self, event):
        """Ensure window stays within screen bounds"""
        super().showEvent(event)
        # Optional: adjust position if it goes off screen
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            if self.x() + self.width() > sg.width():
                self.move(sg.width() - self.width() - 10, self.y())
            if self.y() + self.height() > sg.height():
                self.move(self.x(), sg.height() - self.height() - 10)