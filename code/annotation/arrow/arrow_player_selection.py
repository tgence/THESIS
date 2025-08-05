# player_selection_dialog.py - Version finale corrigée avec design pitch_widget

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QFrame, QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush, QFont, QPainterPath
from config import *

class PlayerCircleButton(QPushButton):
    """Bouton joueur avec design identique à pitch_widget"""
    def __init__(self, player_id, player_number, main_color, sec_color, num_color, parent=None):
        super().__init__(parent)
        self.player_id = player_id
        self.player_number = str(player_number)
        self.main_color = QColor(main_color)
        self.sec_color = QColor(sec_color)
        self.num_color = QColor(num_color)
        self.is_selected = False
        
        self.setFixedSize(50, 50)
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 25px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
    
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Paramètres du cercle (identiques à pitch_widget)
        center_x, center_y = 25, 25
        outer_radius = 20
        inner_radius = 15
        
        # Demi-cercle du haut (couleur principale)
        painter.setBrush(QBrush(self.main_color))
        painter.setPen(Qt.NoPen)
        painter.drawPie(center_x - outer_radius, center_y - outer_radius, 
                       outer_radius * 2, outer_radius * 2, 0, 180 * 16)
        
        # Demi-cercle du bas (couleur secondaire)
        painter.setBrush(QBrush(self.sec_color))
        painter.drawPie(center_x - outer_radius, center_y - outer_radius,
                       outer_radius * 2, outer_radius * 2, 180 * 16, 180 * 16)
        
        # Cercle intérieur (couleur principale)
        painter.setBrush(QBrush(self.main_color))
        painter.drawEllipse(center_x - inner_radius, center_y - inner_radius,
                          inner_radius * 2, inner_radius * 2)
        
        # Contour de sélection si sélectionné
        if self.is_selected:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor("#39C6FF"), 2))  # bleu clair, épaisseur 2
            painter.drawEllipse(center_x - outer_radius - 2, center_y - outer_radius - 2, 
                            (outer_radius + 2) * 2, (outer_radius + 2) * 2)

        
        # Numéro du joueur
        painter.setPen(QPen(self.num_color))
        font = QFont("Arial", 12, QFont.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, self.player_number)
    
    def set_selected(self, selected):
        """Met à jour l'état de sélection"""
        self.is_selected = selected
        self.update()

class ArrowPlayerSelection(QDialog):
    """Dialogue pour sélectionner un joueur avec design identique pitch_widget"""
    playerSelected = pyqtSignal(str, str)  # player_id, player_text
    
    def __init__(self, home_players, away_players, title="Select Player", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        
        self.home_players = home_players
        self.away_players = away_players
        self.selected_player_id = None
        self.selected_player_text = None
        self.player_buttons = []
        
        # Récupérer les couleurs des équipes pour les labels
        self.home_main_color = "#4CAF50"  # Vert par défaut
        self.away_main_color = "#F44336"  # Rouge par défaut
        
        if home_players:
            first_home_player = next(iter(home_players.values()))
            self.home_main_color = first_home_player[1]  # main_color
        
        if away_players:
            first_away_player = next(iter(away_players.values()))
            self.away_main_color = first_away_player[1]  # main_color
        
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Style du dialogue
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                border: 2px solid #555;
                border-radius: 10px;
            }
            QLabel {
                color: white;
                font-weight: bold;
                font-size: 14px;
                text-align: center;
            }
            QPushButton {
                background-color: #404040;
                color: white;
                border: 1px solid #666;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #505050;
                border-color: #888;
            }
            QPushButton:pressed {
                background-color: #353535;
            }
        """)
        
        # Titre
        title_label = QLabel("Select a Player")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Container pour les équipes
        teams_layout = QHBoxLayout()
        teams_layout.setSpacing(30)
        
        # Équipe Home
        home_frame = QFrame()
        home_layout = QVBoxLayout(home_frame)
        home_layout.setSpacing(10)
        
        home_label = QLabel("Home")
        home_label.setAlignment(Qt.AlignCenter)
        home_label.setStyleSheet(f"color: {self.home_main_color}; font-size: 16px; font-weight: bold;")
        home_layout.addWidget(home_label)
        
        # Grille pour les joueurs Home
        home_grid = QGridLayout()
        home_grid.setSpacing(8)
        
        row, col = 0, 0
        for player_id, (number, main_color, sec_color, num_color) in self.home_players.items():
            btn = PlayerCircleButton(player_id, number, main_color, sec_color, num_color)
            btn.clicked.connect(lambda checked, pid=player_id, num=number: 
                              self._select_player(pid, f"Player {num}"))
            home_grid.addWidget(btn, row, col)
            self.player_buttons.append(btn)
            col += 1
            if col >= 4:  # 4 joueurs par ligne
                col = 0
                row += 1
        
        home_layout.addLayout(home_grid)
        teams_layout.addWidget(home_frame)
        
        # Séparateur vertical
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setStyleSheet("color: #666;")
        teams_layout.addWidget(separator)
        
        # Équipe Away
        away_frame = QFrame()
        away_layout = QVBoxLayout(away_frame)
        away_layout.setSpacing(10)
        
        away_label = QLabel("Away")
        away_label.setAlignment(Qt.AlignCenter)
        away_label.setStyleSheet(f"color: {self.away_main_color}; font-size: 16px; font-weight: bold;")
        away_layout.addWidget(away_label)
        
        # Grille pour les joueurs Away
        away_grid = QGridLayout()
        away_grid.setSpacing(8)
        
        row, col = 0, 0
        for player_id, (number, main_color, sec_color, num_color) in self.away_players.items():
            btn = PlayerCircleButton(player_id, number, main_color, sec_color, num_color)
            btn.clicked.connect(lambda checked, pid=player_id, num=number: 
                              self._select_player(pid, f"Player {num}"))
            away_grid.addWidget(btn, row, col)
            self.player_buttons.append(btn)
            col += 1
            if col >= 4:  # 4 joueurs par ligne
                col = 0
                row += 1
        
        away_layout.addLayout(away_grid)
        teams_layout.addWidget(away_frame)
        
        layout.addLayout(teams_layout)
        
        # Boutons OK/Cancel
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #757575;
            }
            QPushButton:hover {
                background-color: #9E9E9E;
            }
        """)
        
        # Bouton "No Player" pour permettre de ne sélectionner personne
        no_player_button = QPushButton("No Player")
        no_player_button.clicked.connect(self._select_no_player)
        no_player_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FFB74D;
            }
        """)
        
        self.ok_button = QPushButton("OK")
        self.ok_button.setEnabled(False)
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #66BB6A;
            }
            QPushButton:disabled {
                background-color: #666;
                color: #999;
            }
        """)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(cancel_button)
        buttons_layout.addWidget(no_player_button)
        buttons_layout.addWidget(self.ok_button)
        
        layout.addLayout(buttons_layout)
        
        # Taille fixe
        self.setFixedSize(600, 450)
    
    def _select_player(self, player_id, player_text):
        """Sélectionne un joueur"""
        self.selected_player_id = player_id
        self.selected_player_text = player_text
        self.ok_button.setEnabled(True)
        
        # Mettre à jour l'affichage de tous les boutons
        for btn in self.player_buttons:
            btn.set_selected(btn.player_id == player_id)
    
    def _select_no_player(self):
        """Sélectionne aucun joueur"""
        self.selected_player_id = None
        self.selected_player_text = "No Player"
        
        # Désélectionner tous les boutons
        for btn in self.player_buttons:
            btn.set_selected(False)
        
        # Fermer immédiatement
        self.accept()
    
    def accept(self):
        """Accepte la sélection"""
        if self.selected_player_id is not None or self.selected_player_text == "No Player":
            self.playerSelected.emit(self.selected_player_id or "", self.selected_player_text or "")
        super().accept()
    
    @staticmethod
    def select_player(home_players, away_players, title="Select Player", parent=None):
        """Méthode statique pour sélectionner un joueur"""
        dialog = PlayerSelectionDialog(home_players, away_players, title, parent)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.selected_player_id, dialog.selected_player_text
        return None, None