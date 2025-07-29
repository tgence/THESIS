# arrow_context_menu.py - Version finale corrigée avec tous les problèmes résolus

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QSpinBox, QButtonGroup, QRadioButton, QColorDialog, QFrame,
    QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPalette, QPainter, QIcon, QPen, QBrush, QFont
from player_selection_dialog import PlayerSelectionDialog
from config import *
import os

class PlayerCircleWidget(QWidget):
    """Widget qui affiche un joueur comme un cercle avec son numéro - CLIQUABLE"""
    
    clicked = pyqtSignal()
    
    def __init__(self, number, main_color, sec_color, num_color, parent=None):
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
        
        # Design identique à pitch_widget
        # Demi-cercle du bas (couleur secondaire)
        painter.setBrush(QBrush(self.sec_color))
        painter.setPen(Qt.NoPen)
        painter.drawPie(2, 2, 36, 36, 0, 180 * 16)  # 180 degrés en 1/16e de degrés
        
        # Demi-cercle du haut (couleur principale)
        painter.setBrush(QBrush(self.main_color))
        painter.drawPie(2, 2, 36, 36, 180 * 16, 180 * 16)
        
        # Cercle intérieur (couleur principale)
        painter.setBrush(QBrush(self.main_color))
        painter.drawEllipse(8, 8, 24, 24)
        
        # Numéro
        painter.setPen(QPen(self.num_color))
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(self.rect(), Qt.AlignCenter, self.number)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

class ArrowContextMenu(QWidget):
    """Menu contextuel pour éditer les propriétés des flèches"""
    
    # Signaux
    fromPlayerSelected = pyqtSignal(str)  # player_id
    toPlayerSelected = pyqtSignal(str)    # player_id
    colorChanged = pyqtSignal(str)        # hex color
    widthChanged = pyqtSignal(int)        # width value
    styleChanged = pyqtSignal(str)        # style name
    deleteRequested = pyqtSignal()
    propertiesConfirmed = pyqtSignal()    # Signal pour confirmer les changements
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        
        # Variables
        self.current_arrow = None
        self.home_players = {}
        self.away_players = {}
        
        # État des sélections
        self.selected_from_player = None
        self.selected_to_player = None
        self.current_color = "#000000"
        self.current_width = 5
        
        # Historique pour undo/redo
        self.history = []
        self.history_index = -1
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Configure l'interface du menu avec scroll"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Style du widget principal
        self.setStyleSheet("""
            ArrowContextMenu {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 8px;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #404040;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #666;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #777;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
            QLabel {
                color: white;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton {
                background-color: #404040;
                color: white;
                border: 1px solid #666;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #505050;
                border-color: #888;
            }
            QPushButton:pressed {
                background-color: #353535;
            }
            QSpinBox {
                background-color: #404040;
                color: white;
                border: 1px solid #666;
                border-radius: 4px;
                padding: 4px;
                font-size: 11px;
                min-height: 20px;
            }
            QRadioButton {
                color: white;
                font-size: 11px;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
            }
        """)
        
        # Zone de scroll
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Widget de contenu scrollable
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Section From
        from_label = QLabel("From:")
        layout.addWidget(from_label)
        
        # Container pour le bouton from avec le cercle joueur
        self.from_container = QHBoxLayout()
        self.from_button = QPushButton("Select Player")
        self.from_button.clicked.connect(lambda: self._open_player_selection("from"))
        self.from_container.addWidget(self.from_button)
        self.from_player_widget = None
        layout.addLayout(self.from_container)
        
        # Séparateur
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.HLine)
        separator1.setStyleSheet("color: #666;")
        layout.addWidget(separator1)
        
        # Section To
        to_label = QLabel("To:")
        layout.addWidget(to_label)
        
        # Container pour le bouton to avec le cercle joueur
        self.to_container = QHBoxLayout()
        self.to_button = QPushButton("Select Player")
        self.to_button.clicked.connect(lambda: self._open_player_selection("to"))
        self.to_container.addWidget(self.to_button)
        self.to_player_widget = None
        layout.addLayout(self.to_container)
        
        # Séparateur
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        separator2.setStyleSheet("color: #666;")
        layout.addWidget(separator2)
        
        # Section Properties
        props_label = QLabel("Properties:")
        layout.addWidget(props_label)
        
        # Couleur
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Color:"))
        self.color_button = QPushButton()
        self.color_button.setFixedSize(50, 30)
        self.color_button.clicked.connect(self._choose_color)
        color_layout.addWidget(self.color_button)
        color_layout.addStretch()
        layout.addLayout(color_layout)
        
        # Largeur
        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel("Width:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 10)
        self.width_spin.setValue(3)
        self.width_spin.valueChanged.connect(self._on_width_changed)
        width_layout.addWidget(self.width_spin)
        width_layout.addStretch()
        layout.addLayout(width_layout)
        
        # Style
        style_label = QLabel("Style:")
        layout.addWidget(style_label)
        
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
        
        self.style_buttons.buttonClicked.connect(self._style_changed)
        
        # Ajouter stretch pour pousser les boutons vers le bas
        layout.addStretch()
        
        # Assigner le widget de contenu à la zone de scroll
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, 1)
        
        # Section des boutons (non-scrollable)
        buttons_frame = QFrame()
        buttons_frame.setStyleSheet("background-color: #2b2b2b; border-top: 1px solid #555;")
        buttons_layout = QHBoxLayout(buttons_frame)
        buttons_layout.setContentsMargins(12, 8, 12, 8)
        buttons_layout.setSpacing(8)
        
        # Bouton Undo (undo) - À GAUCHE
        self.undo_button = QPushButton()
        self.undo_button.setFixedSize(40, 30)
        self.undo_button.setToolTip("Undo last action")
        

        undo_icon_path = os.path.join(SVG_DIR, "undo.svg")
        if os.path.exists(undo_icon_path):
            self.undo_button.setIcon(QIcon(undo_icon_path))
  
        self.undo_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                opacity: 1.0;
            }
            QPushButton:hover {
                background-color: #9E9E9E;
            }
            QPushButton:pressed {
                background-color: #616161;
            }
            QPushButton:disabled {
                background-color: #444;
                color: #666;
            }
        """)

        self.undo_button.clicked.connect(self._undo_action)
        self.undo_button.setEnabled(False)
        buttons_layout.addWidget(self.undo_button)
        
        # Bouton Redo (redo)
        self.redo_button = QPushButton()
        self.redo_button.setFixedSize(40, 30)
        self.redo_button.setToolTip("Redo last action")
        
        redo_icon_path = os.path.join(SVG_DIR, "redo.svg")
        if os.path.exists(redo_icon_path):
            self.redo_button.setIcon(QIcon(redo_icon_path))
 
        self.redo_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                opacity: 1.0;
            }
            QPushButton:hover {
                background-color: #9E9E9E;
            }
            QPushButton:pressed {
                background-color: #616161;
            }
            QPushButton:disabled {
                background-color: #444;
                color: #666;
            }
        """)
        self.redo_button.clicked.connect(self._redo_action)
        self.redo_button.setEnabled(False)
        buttons_layout.addWidget(self.redo_button)
        
        buttons_layout.addStretch()  # Espace entre les boutons
        
        # Bouton OK - À DROITE
        self.ok_button = QPushButton("OK")
        self.ok_button.setFixedSize(80, 30)
        self.ok_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #66BB6A;
            }
            QPushButton:pressed {
                background-color: #388E3C;
            }
        """)
        self.ok_button.clicked.connect(self._on_ok_clicked)
        buttons_layout.addWidget(self.ok_button)
        
        # Bouton Delete
        self.delete_button = QPushButton("Delete")
        self.delete_button.setFixedSize(80, 30)
        self.delete_button.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: white;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #f44336;
            }
            QPushButton:pressed {
                background-color: #b71c1c;
            }
        """)
        self.delete_button.clicked.connect(lambda: self.deleteRequested.emit())
        buttons_layout.addWidget(self.delete_button)
        
        main_layout.addWidget(buttons_frame)
        
        # Taille du menu ajustée
        self.setFixedSize(320, 500)
    
    def _save_state(self, action_type, old_value, new_value):
        """Sauvegarde l'état pour l'historique undo/redo"""
        # Supprimer les états après l'index actuel si on fait une nouvelle action
        self.history = self.history[:self.history_index + 1]
        
        # Ajouter la nouvelle action
        self.history.append({
            'type': action_type,
            'old_value': old_value,
            'new_value': new_value
        })
        
        self.history_index += 1
        self._update_undo_redo_buttons()
    
    def _update_undo_redo_buttons(self):
        """Met à jour l'état des boutons undo/redo"""
        self.undo_button.setEnabled(self.history_index >= 0)
        self.redo_button.setEnabled(self.history_index < len(self.history) - 1)
    
    def _undo_action(self):
        """Annule la dernière action"""
        if self.history_index >= 0:
            action = self.history[self.history_index]
            self._apply_action(action, True)  # True = undo
            self.history_index -= 1
            self._update_undo_redo_buttons()
    
    def _redo_action(self):
        """Refait la dernière action annulée"""
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            action = self.history[self.history_index]
            self._apply_action(action, False)  # False = redo
            self._update_undo_redo_buttons()
    
    def _apply_action(self, action, is_undo):
        """Applique une action (undo ou redo)"""
        value = action['old_value'] if is_undo else action['new_value']
        
        if action['type'] == 'color':
            self.current_color = value
            self._set_color_button(value)
            self.colorChanged.emit(value)
        elif action['type'] == 'width':
            self.current_width = value
            self.width_spin.setValue(value)
            self.widthChanged.emit(value)
        elif action['type'] == 'style':
            style_map = {"solid": 0, "dotted": 1, "zigzag": 2}
            if value in style_map:
                self.style_buttons.button(style_map[value]).setChecked(True)
                self.styleChanged.emit(value)
    
    def _on_ok_clicked(self):
        """Gère le clic sur OK"""
        self.propertiesConfirmed.emit()
        self.close()
    
    def _on_width_changed(self, value):
        """Gère le changement de largeur"""
        old_value = self.current_width
        self.current_width = value
        self._save_state('width', old_value, value)
        self.widthChanged.emit(value)
    
    def set_players_data(self, home_players, away_players):
        """Configure les données des joueurs"""
        self.home_players = home_players
        self.away_players = away_players
    
    def _open_player_selection(self, selection_type):
        """Ouvre le dialogue de sélection de joueur"""
        title = "From" if selection_type == "from" else "To"
        
        dialog = PlayerSelectionDialog(
            self.home_players, 
            self.away_players, 
            title, 
            self
        )
        
        result = dialog.exec_()
        if result == dialog.Accepted:
            player_id = dialog.selected_player_id
            
            if selection_type == "from":
                self.selected_from_player = player_id
                self._update_player_display("from", player_id)
                self.fromPlayerSelected.emit(player_id)
            else:
                self.selected_to_player = player_id
                self._update_player_display("to", player_id)
                self.toPlayerSelected.emit(player_id)
        
        # Le menu reste ouvert après fermeture du dialogue
        self.show()
        self.raise_()
        self.activateWindow()
    
    def _update_player_display(self, selection_type, player_id):
        """Met à jour l'affichage du joueur sélectionné"""
        # Trouver les données du joueur
        player_data = None
        if player_id in self.home_players:
            player_data = self.home_players[player_id]
        elif player_id in self.away_players:
            player_data = self.away_players[player_id]
        
        if not player_data:
            return
        
        number, main_color, sec_color, num_color = player_data
        
        if selection_type == "from":
            # Supprimer l'ancien widget s'il existe
            if self.from_player_widget:
                self.from_container.removeWidget(self.from_player_widget)
                self.from_player_widget.deleteLater()
            
            # Cacher le bouton de sélection
            self.from_button.hide()
            
            # Créer le nouveau widget cercle cliquable
            self.from_player_widget = PlayerCircleWidget(number, main_color, sec_color, num_color)
            self.from_player_widget.clicked.connect(lambda: self._open_player_selection("from"))
            self.from_container.addWidget(self.from_player_widget)
            
        else:
            # Supprimer l'ancien widget s'il existe
            if self.to_player_widget:
                self.to_container.removeWidget(self.to_player_widget)
                self.to_player_widget.deleteLater()
            
            # Cacher le bouton de sélection
            self.to_button.hide()
            
            # Créer le nouveau widget cercle cliquable
            self.to_player_widget = PlayerCircleWidget(number, main_color, sec_color, num_color)
            self.to_player_widget.clicked.connect(lambda: self._open_player_selection("to"))
            self.to_container.addWidget(self.to_player_widget)
    
    def show_for_arrow(self, arrow, pos):
        """Affiche le menu pour une flèche donnée"""
        self.current_arrow = arrow
        
        # Réinitialiser l'historique
        self.history.clear()
        self.history_index = -1
        self._update_undo_redo_buttons()
        
        # Mettre à jour les propriétés actuelles
        self._update_from_arrow(arrow)
        
        # Positionner et afficher
        self.move(pos)
        self.show()
        self.raise_()
        self.activateWindow()
    
    def _update_from_arrow(self, arrow):
        """Met à jour le menu avec les propriétés de la flèche"""
        # Couleur
        if hasattr(arrow, 'childItems'):
            for item in arrow.childItems():
                if hasattr(item, 'pen'):
                    color = item.pen().color()
                    self.current_color = color.name()
                    self._set_color_button(color.name())
                    break
        
        # Largeur
        if hasattr(arrow, 'childItems'):
            for item in arrow.childItems():
                if hasattr(item, 'pen') and not hasattr(item, 'brush'):
                    width = int(item.pen().width() / 0.3)
                    self.current_width = width
                    self.width_spin.setValue(width)
                    break
        
        # Style
        if hasattr(arrow, 'arrow_style'):
            style = arrow.arrow_style
            if style == "solid":
                self.style_buttons.button(0).setChecked(True)
            elif style == "dotted":
                self.style_buttons.button(1).setChecked(True)
            elif style == "zigzag":
                self.style_buttons.button(2).setChecked(True)
    
    def _set_color_button(self, color_hex):
        """Met à jour la couleur du bouton couleur"""
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
    
    def _choose_color(self):
        """Ouvre le sélecteur de couleur centré"""
        current_color = QColor(self.current_color)
        
        # Créer le dialogue de couleur
        color_dialog = QColorDialog(current_color, self)
        color_dialog.setModal(True)
        
        # Centrer le dialogue sur l'écran principal
        screen = self.parent().screen() if self.parent() else None
        if screen:
            screen_geometry = screen.geometry()
            dialog_size = color_dialog.sizeHint()
            x = screen_geometry.center().x() - dialog_size.width() // 2
            y = screen_geometry.center().y() - dialog_size.height() // 2
            color_dialog.move(x, y)
        
        # Exécuter le dialogue
        if color_dialog.exec_() == QColorDialog.Accepted:
            color = color_dialog.selectedColor()
            if color.isValid():
                old_color = self.current_color
                self.current_color = color.name()
                self._save_state('color', old_color, color.name())
                self._set_color_button(color.name())
                self.colorChanged.emit(color.name())
        
        # S'assurer que le menu reste ouvert et au premier plan
        self.show()
        self.raise_()
        self.activateWindow()
    
    def _style_changed(self, button):
        """Gère le changement de style"""
        styles = {0: "solid", 1: "dotted", 2: "zigzag"}
        button_id = self.style_buttons.id(button)
        style = styles.get(button_id, "solid")
        
        # Sauvegarder l'ancien style (par défaut "solid")
        old_style = "solid"
        if hasattr(self.current_arrow, 'arrow_style'):
            old_style = self.current_arrow.arrow_style
        
        self._save_state('style', old_style, style)
        self.styleChanged.emit(style)
    
    def closeEvent(self, event):
        """Ferme le menu"""
        self.current_arrow = None
        super().closeEvent(event)