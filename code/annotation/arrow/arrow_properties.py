"""
Properties popup for a selected arrow.

Allows choosing color/width/style and selecting from/to players, with a small
undo/redo stack for property changes.
"""
# arrow_properties.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSpinBox, QButtonGroup, QRadioButton, QColorDialog, QFrame,
    QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush, QFont, QIcon
from annotation.arrow.arrow_player_selection import ArrowPlayerSelection
from config import *
import os

class PlayerCircleWidget(QWidget):
    clicked = pyqtSignal()

    def __init__(self, number, main_color, sec_color, num_color, parent=None):
        """Small circular widget rendering a player's number and colors."""
        super().__init__(parent)
        self.number = str(number)
        self.main_color = QColor(main_color)
        self.sec_color = QColor(sec_color)
        self.num_color = QColor(num_color)
        self.setFixedSize(40, 40)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.setBrush(QBrush(self.sec_color))
        painter.setPen(Qt.NoPen)
        painter.drawPie(2, 2, 36, 36, 0, 180 * 16)
        painter.setBrush(QBrush(self.main_color))
        painter.drawPie(2, 2, 36, 36, 180 * 16, 180 * 16)
        painter.setBrush(QBrush(self.main_color))
        painter.drawEllipse(8, 8, 24, 24)
        painter.setPen(QPen(self.num_color))
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(self.rect(), Qt.AlignCenter, self.number)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

class ArrowProperties(QWidget):
    fromPlayerSelected = pyqtSignal(str)
    toPlayerSelected = pyqtSignal(str)
    deleteRequested = pyqtSignal()
    propertiesConfirmed = pyqtSignal()

    def __init__(self, parent=None):
        """Create the properties popup with controls and signals wired."""
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.Window)
        self.setWindowTitle("Arrow Properties") 

        # State
        self.current_arrow = None
        self.home_players = {}
        self.away_players = {}
        self.selected_from_player = None
        self.selected_to_player = None
        self.current_color = "#000000"
        self.current_width = 5
        self.history = []
        self.history_index = -1

        self._setup_ui()
        # Connect signals AFTER widgets exist
        self.color_button.clicked.connect(self._on_color_changed)
        self.width_spin.valueChanged.connect(self._on_width_changed)
        self.style_buttons.buttonClicked.connect(self._style_changed)
        self.ok_button.clicked.connect(self._on_ok_clicked)
        self.undo_button.clicked.connect(self._undo_action)
        self.redo_button.clicked.connect(self._redo_action)
        self.delete_button.clicked.connect(lambda: self.deleteRequested.emit())

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # --- From ---
        layout.addWidget(QLabel("From:"))
        self.from_container = QHBoxLayout()
        self.from_button = QPushButton("Select Player")
        self.from_button.clicked.connect(lambda: self._open_player_selection("from"))
        self.from_container.addWidget(self.from_button)
        self.from_player_widget = None
        layout.addLayout(self.from_container)
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.HLine)
        separator1.setStyleSheet("color: #666;")
        layout.addWidget(separator1)
        # --- To ---
        layout.addWidget(QLabel("To:"))
        self.to_container = QHBoxLayout()
        self.to_button = QPushButton("Select Player")
        self.to_button.clicked.connect(lambda: self._open_player_selection("to"))
        self.to_container.addWidget(self.to_button)
        self.to_player_widget = None
        layout.addLayout(self.to_container)
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        separator2.setStyleSheet("color: #666;")
        layout.addWidget(separator2)
        # --- Properties ---
        layout.addWidget(QLabel("Properties:"))

        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Color:"))
        self.color_button = QPushButton()
        self.color_button.setFixedSize(50, 30)
        color_layout.addWidget(self.color_button)
        color_layout.addStretch()
        layout.addLayout(color_layout)

        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel("Width:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 5)
        self.width_spin.setValue(1)
        width_layout.addWidget(self.width_spin)
        width_layout.addStretch()
        layout.addLayout(width_layout)

        layout.addWidget(QLabel("Style:"))
        self.style_buttons = QButtonGroup()
        solid_rb = QRadioButton("Solid (Pass)")
        dotted_rb = QRadioButton("Dotted (Run)")
        zigzag_rb = QRadioButton("Zigzag (Dribble)")
        self.style_buttons.addButton(solid_rb, 0)
        self.style_buttons.addButton(dotted_rb, 1)
        self.style_buttons.addButton(zigzag_rb, 2)
        solid_rb.setChecked(True)
        layout.addWidget(solid_rb)
        layout.addWidget(dotted_rb)
        layout.addWidget(zigzag_rb)
        layout.addStretch()

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, 1)

        buttons_frame = QFrame()
        buttons_frame.setStyleSheet("background-color: #2b2b2b; border-top: 1px solid #555;")
        buttons_layout = QHBoxLayout(buttons_frame)
        buttons_layout.setContentsMargins(12, 8, 12, 8)
        buttons_layout.setSpacing(8)
        # Undo
        self.undo_button = QPushButton()
        self.undo_button.setFixedSize(40, 30)
        self.undo_button.setToolTip("Undo last action")
        undo_icon_path = os.path.join(SVG_DIR, "undo.svg")
        if os.path.exists(undo_icon_path):
            self.undo_button.setIcon(QIcon(undo_icon_path))
        # Redo
        self.redo_button = QPushButton()
        self.redo_button.setFixedSize(40, 30)
        self.redo_button.setToolTip("Redo last action")
        redo_icon_path = os.path.join(SVG_DIR, "redo.svg")
        if os.path.exists(redo_icon_path):
            self.redo_button.setIcon(QIcon(redo_icon_path))
        self.undo_button.setEnabled(False)
        self.redo_button.setEnabled(False)
        buttons_layout.addWidget(self.undo_button)
        buttons_layout.addWidget(self.redo_button)
        buttons_layout.addStretch()
        self.ok_button = QPushButton("OK")
        self.ok_button.setFixedSize(80, 30)
        buttons_layout.addWidget(self.ok_button)
        self.delete_button = QPushButton("Delete")
        self.delete_button.setFixedSize(80, 30)
        self.delete_button.setStyleSheet("background-color: #ff4444; color: white; border: 2px solid #ff4444;")
        buttons_layout.addWidget(self.delete_button)
        main_layout.addWidget(buttons_frame)
        self.setFixedSize(320, 500)

    # --- Undo/Redo ---
    def _save_state(self, action_type, old_value, new_value):
        self.history = self.history[:self.history_index + 1]
        self.history.append({'type': action_type, 'old_value': old_value, 'new_value': new_value})
        self.history_index += 1
        self._update_undo_redo_buttons()

    def _update_undo_redo_buttons(self):
        self.undo_button.setEnabled(self.history_index >= 0)
        self.redo_button.setEnabled(self.history_index < len(self.history) - 1)

    def _undo_action(self):
        if self.history_index >= 0:
            action = self.history[self.history_index]
            self._apply_action(action, True)
            self.history_index -= 1
            self._update_undo_redo_buttons()

    def _redo_action(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            action = self.history[self.history_index]
            self._apply_action(action, False)
            self._update_undo_redo_buttons()

    def _apply_action(self, action, is_undo):
        value = action['old_value'] if is_undo else action['new_value']
        if action['type'] == 'color':
            self.current_color = value
            self._set_color_button(value)
            if self.current_arrow:
                self.current_arrow.set_color(value)
                if hasattr(self.current_arrow, 'refresh_visual'):
                    self.current_arrow.refresh_visual()
        elif action['type'] == 'width':
            self.current_width = value
            self.width_spin.blockSignals(True)
            self.width_spin.setValue(value)
            self.width_spin.blockSignals(False)
            if self.current_arrow:
                self.current_arrow.set_width(value)
                if hasattr(self.current_arrow, 'refresh_visual'):
                    self.current_arrow.refresh_visual()
        elif action['type'] == 'style':
            style_map = {"solid": 0, "dotted": 1, "zigzag": 2}
            if value in style_map:
                self.style_buttons.button(style_map[value]).setChecked(True)
            if self.current_arrow:
                self.current_arrow.set_style(value)
                if hasattr(self.current_arrow, 'refresh_visual'):
                    self.current_arrow.refresh_visual()
        elif action['type'] == 'from_player':
            self.selected_from_player = value
            self._update_player_display("from", value)
            if self.current_arrow:
                self.current_arrow.set_from_player(value)
        elif action['type'] == 'to_player':
            self.selected_to_player = value
            self._update_player_display("to", value)
            if self.current_arrow:
                self.current_arrow.set_to_player(value)


    # --- Property handlers ---
    def _on_color_changed(self):
        color_dialog = QColorDialog(QColor(self.current_color), self)
        if color_dialog.exec_() == QColorDialog.Accepted:
            color = color_dialog.selectedColor()    
            if color.isValid():
                old_color = self.current_color
                self.current_color = color.name()
                self._save_state('color', old_color, color.name())
                self._set_color_button(self.current_color)
                if self.current_arrow:
                    self.current_arrow.set_color(self.current_color)
                    if hasattr(self.current_arrow, 'refresh_visual'):
                        self.current_arrow.refresh_visual()

    def _on_width_changed(self, value):
            old_value = self.current_width
            self.current_width = value
            self._save_state('width', old_value, value)
            if self.current_arrow:
                self.current_arrow.set_width(self.current_width)
                # AJOUTER ICI:
                if hasattr(self.current_arrow, 'refresh_visual'):
                    self.current_arrow.refresh_visual()

        

    def _style_changed(self, button):
        styles = {0: "solid", 1: "dotted", 2: "zigzag"}
        style = styles.get(self.style_buttons.id(button), "solid")
        old_style = "solid"
        if hasattr(self.current_arrow, 'arrow_style'):
            old_style = self.current_arrow.arrow_style
        self._save_state('style', old_style, style)
        if self.current_arrow:
            self.current_arrow.set_style(style)
            # AJOUTER ICI:
            if hasattr(self.current_arrow, 'refresh_visual'):
                self.current_arrow.refresh_visual()



    # --- Player selection ---
    def set_players_data(self, home_players, away_players):
        self.home_players = home_players
        self.away_players = away_players

    def _open_player_selection(self, selection_type):
        title = "From" if selection_type == "from" else "To"
        dialog = ArrowPlayerSelection(self.home_players, self.away_players, title, self)
        result = dialog.exec_()
        if result == dialog.Accepted:
            player_id = dialog.selected_player_id
            player_text = dialog.selected_player_text
            
            if selection_type == "from":
                old_value = self.selected_from_player
                self.selected_from_player = player_id
                if player_text == "No Player":
                    # Restore "Select Player" button and remove player widget
                    if self.from_player_widget:
                        self.from_container.removeWidget(self.from_player_widget)
                        self.from_player_widget.deleteLater()
                        self.from_player_widget = None
                    self.from_button.show()
                    self.selected_from_player = None  # important: reset to None
                else:
                    self._update_player_display("from", player_id)
                self._save_state('from_player', old_value, player_id)
                self.fromPlayerSelected.emit(player_id or "")
            else:
                old_value = self.selected_to_player
                self.selected_to_player = player_id
                if player_text == "No Player":
                    # Restore "Select Player" button and remove player widget
                    if self.to_player_widget:
                        self.to_container.removeWidget(self.to_player_widget)
                        self.to_player_widget.deleteLater()
                        self.to_player_widget = None
                    self.to_button.show()
                    self.selected_to_player = None  # important: reset to None
                else:
                    self._update_player_display("to", player_id)
                self._save_state('to_player', old_value, player_id)
                self.toPlayerSelected.emit(player_id or "")
        
        self.show()
        self.raise_()
        self.activateWindow()

    def _update_player_display(self, selection_type, player_id):
        player_data = self.home_players.get(player_id) or self.away_players.get(player_id)
        if not player_data:
            if selection_type == "from":
                if self.from_player_widget:
                    self.from_container.removeWidget(self.from_player_widget)
                    self.from_player_widget.deleteLater()
                    self.from_player_widget = None
                self.from_button.show()
            else:
                if self.to_player_widget:
                    self.to_container.removeWidget(self.to_player_widget)
                    self.to_player_widget.deleteLater()
                    self.to_player_widget = None
                self.to_button.show()
            return
        number, main_color, sec_color, num_color = player_data
        if selection_type == "from":
            if self.from_player_widget:
                self.from_container.removeWidget(self.from_player_widget)
                self.from_player_widget.deleteLater()
            self.from_button.hide()
            self.from_player_widget = PlayerCircleWidget(number, main_color, sec_color, num_color)
            self.from_player_widget.clicked.connect(lambda: self._open_player_selection("from"))
            self.from_container.addWidget(self.from_player_widget)
        else:
            if self.to_player_widget:
                self.to_container.removeWidget(self.to_player_widget)
                self.to_player_widget.deleteLater()
            self.to_button.hide()
            self.to_player_widget = PlayerCircleWidget(number, main_color, sec_color, num_color)
            self.to_player_widget.clicked.connect(lambda: self._open_player_selection("to"))
            self.to_container.addWidget(self.to_player_widget)

    # --- Show & state reset ---
    def show_for_arrow(self, arrow, pos):
        self.current_arrow = arrow
        self.selected_from_player = None
        self.selected_to_player = None
        self.history.clear()
        self.history_index = -1
        self._update_undo_redo_buttons()
        self._update_from_arrow(arrow)
        self.move(pos)
        self.show()
        self.raise_()
        self.activateWindow()

    def _update_from_arrow(self, arrow):
        # Sync visual properties
        if hasattr(arrow, 'arrow_color'):
            self.current_color = arrow.arrow_color
            self._set_color_button(arrow.arrow_color)
            self.current_width = arrow.arrow_width
            self.width_spin.setValue(arrow.arrow_width)
            style = arrow.arrow_style
            if style == "solid":
                self.style_buttons.button(0).setChecked(True)
            elif style == "dotted":
                self.style_buttons.button(1).setChecked(True)
            elif style == "zigzag":
                self.style_buttons.button(2).setChecked(True)
        
        # Sync current players selection state
        # From Player
        from_player = getattr(arrow, "from_player", None)
        self.selected_from_player = from_player
        if from_player is not None:
            self._update_player_display("from", from_player)
        else:
            # reset display, show "Select Player" button
            if self.from_player_widget:
                self.from_container.removeWidget(self.from_player_widget)
                self.from_player_widget.deleteLater()
                self.from_player_widget = None
            self.from_button.show()
        # To Player
        to_player = getattr(arrow, "to_player", None)
        self.selected_to_player = to_player
        if to_player is not None:
            self._update_player_display("to", to_player)
        else:
            if self.to_player_widget:
                self.to_container.removeWidget(self.to_player_widget)
                self.to_player_widget.deleteLater()
                self.to_player_widget = None
            self.to_button.show()


    def _set_color_button(self, color_hex):
        self.color_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color_hex};
                border: 2px solid #666;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border-color: #888;
            }}
        """)

    def _on_ok_clicked(self):
        arrow = self.current_arrow
        if arrow is not None:
            arrow.set_color(self.current_color)
            arrow.set_width(self.current_width)
            arrow.set_style(self._get_current_style())
            arrow.set_from_player(self.selected_from_player)
            arrow.set_to_player(self.selected_to_player)


        self.propertiesConfirmed.emit()
        self.close()

    def _get_current_style(self):
        for btn, name in zip(self.style_buttons.buttons(), ["solid", "dotted", "zigzag"]):
            if btn.isChecked():
                return name
        return "solid"

    def closeEvent(self, event):
        self.current_arrow = None
        super().closeEvent(event)
