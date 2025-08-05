# settings.py

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider, 
    QPushButton, QColorDialog, QGroupBox, QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QColor
from config import BALL_COLOR, CONFIG


class SettingsManager(QObject):
    """Gestionnaire centralisé des paramètres visuels de l'application"""
    
    # Signaux émis quand les paramètres changent
    playerScaleChanged = pyqtSignal(float)
    ballColorChanged = pyqtSignal(str)
    offsideColorChanged = pyqtSignal(str)
    arrowColorChanged = pyqtSignal(str)
    settingsChanged = pyqtSignal()  # Signal général pour tout changement
    
    def __init__(self):
        super().__init__()
        
        # Valeurs par défaut
        self._player_scale = 1.0
        self._ball_color = BALL_COLOR
        self._offside_color = "#FF40FF"  # Magenta par défaut
        self._arrow_color = "#000000"    # Noir par défaut
        self._custom_arrow_color = False
        self._custom_offside_color = False
        
        # Limites
        self.MIN_PLAYER_SCALE = 0.5
        self.MAX_PLAYER_SCALE = 2.0
        
    @property
    def player_scale(self):
        return self._player_scale
    
    @player_scale.setter
    def player_scale(self, value):
        value = max(self.MIN_PLAYER_SCALE, min(self.MAX_PLAYER_SCALE, value))
        if self._player_scale != value:
            self._player_scale = value
            CONFIG.scale = value  # Mettre à jour la config globale
            self.playerScaleChanged.emit(value)
            self.settingsChanged.emit()
    
    @property
    def ball_color(self):
        return self._ball_color
    
    @ball_color.setter
    def ball_color(self, color):
        if self._ball_color != color:
            self._ball_color = color
            self.ballColorChanged.emit(color)
            self.settingsChanged.emit()
    
    @property
    def offside_color(self):
        return self._offside_color
    
    @offside_color.setter
    def offside_color(self, color):
        if self._offside_color != color:
            self._offside_color = color
            self._custom_offside_color = True
            self.offsideColorChanged.emit(color)
            self.settingsChanged.emit()
    
    @property
    def arrow_color(self):
        return self._arrow_color
    
    @arrow_color.setter
    def arrow_color(self, color):
        if self._arrow_color != color:
            self._arrow_color = color
            self._custom_arrow_color = True
            self.arrowColorChanged.emit(color)
            self.settingsChanged.emit()
    
    def reset_theme_colors(self, theme):
        self._custom_arrow_color = False
        self._custom_offside_color = False
        # Set sans réémettre settingsChanged (évite double update), utilise les setters pour cohérence
        self._ball_color = BALL_COLOR
        self._arrow_color = theme.get("arrow", "#000000")
        self._offside_color = theme.get("offside", "#FF40FF")
        self.settingsChanged.emit()
    
    def get_all_settings(self):
        """Retourne un dictionnaire avec tous les paramètres"""
        return {
            'player_scale': self._player_scale,
            'ball_color': self._ball_color,
            'offside_color': self._offside_color,
            'arrow_color': self._arrow_color
        }


class ColorButton(QPushButton):
    """Bouton personnalisé pour sélectionner une couleur"""
    
    colorChanged = pyqtSignal(str)
    
    def __init__(self, color="#FFFFFF", parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(60, 30)
        self.update_color(color)
        self.clicked.connect(self._on_clicked)
        
    def _on_clicked(self):
        """Ouvre le dialog de sélection de couleur"""
        initial = QColor(self._color)
        color = QColorDialog.getColor(initial, self, "Choose color")
        if color.isValid():
            self.update_color(color.name())
            self.colorChanged.emit(color.name())
    
    def update_color(self, color):
        """Met à jour la couleur du bouton"""
        self._color = color
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border: 2px solid #333;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border: 2px solid #666;
            }}
        """)
    
    def get_color(self):
        return self._color


class SettingsDialog(QDialog):
    """Dialog pour modifier les paramètres visuels"""
    
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle("Visual Settings")
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setModal(False)  # Non-modal pour voir les changements en temps réel
        self.setFixedSize(350, 400)
        
        self._current_theme = getattr(parent, 'current_theme', None)
        self._setup_ui()
        self._load_current_settings()
        self._connect_signals()
        
    def _setup_ui(self):
        """Configure l'interface utilisateur"""
        layout = QVBoxLayout(self)
        
        # === Groupe Taille des joueurs ===
        size_group = QGroupBox("Player Size")
        size_layout = QVBoxLayout()
        
        # Slider avec labels
        slider_layout = QHBoxLayout()
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setMinimum(50)   # 0.5x
        self.size_slider.setMaximum(200)  # 2.0x
        self.size_slider.setTickPosition(QSlider.TicksBelow)
        self.size_slider.setTickInterval(25)
        
        self.size_label = QLabel("1.0x")
        self.size_label.setFixedWidth(40)
        self.size_label.setAlignment(Qt.AlignCenter)
        
        slider_layout.addWidget(QLabel("0.5x"))
        slider_layout.addWidget(self.size_slider)
        slider_layout.addWidget(QLabel("2.0x"))
        slider_layout.addWidget(self.size_label)
        
        size_layout.addLayout(slider_layout)
        
        # Boutons preset
        preset_layout = QHBoxLayout()
        size_layout.addLayout(preset_layout)
        
        size_group.setLayout(size_layout)
        layout.addWidget(size_group)
        
        # === Groupe Couleurs ===
        colors_group = QGroupBox("Colors")
        colors_layout = QGridLayout()
        
        # Couleur de la balle
        colors_layout.addWidget(QLabel("Ball :"), 0, 0)
        self.ball_color_btn = ColorButton()
        colors_layout.addWidget(self.ball_color_btn, 0, 1)
        
        # Couleur ligne hors-jeu
        colors_layout.addWidget(QLabel("Offside Line :"), 1, 0)
        self.offside_color_btn = ColorButton()
        colors_layout.addWidget(self.offside_color_btn, 1, 1)
        
        # Couleur flèches orientation
        colors_layout.addWidget(QLabel("Orientation Arrows :"), 2, 0)
        self.arrow_color_btn = ColorButton()
        colors_layout.addWidget(self.arrow_color_btn, 2, 1)
        
        colors_layout.setColumnStretch(0, 1)
        colors_layout.setColumnStretch(1, 0)
        colors_group.setLayout(colors_layout)
        layout.addWidget(colors_group)
        
        # === Boutons de contrôle ===
        layout.addStretch()
        
        button_layout = QHBoxLayout()
        
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._on_reset)
        
        close_btn = QPushButton("Ok")
        close_btn.clicked.connect(self.close)
        close_btn.setDefault(True)
        
        button_layout.addWidget(reset_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _load_current_settings(self):
        """Charge les paramètres actuels"""
        settings = self.settings_manager.get_all_settings()
        
        # Taille des joueurs
        scale_value = int(settings['player_scale'] * 100)
        self.size_slider.setValue(scale_value)
        self._update_size_label(scale_value)
        
        # Couleurs
        self.ball_color_btn.update_color(settings['ball_color'])
        self.offside_color_btn.update_color(settings['offside_color'])
        self.arrow_color_btn.update_color(settings['arrow_color'])
    
    def _connect_signals(self):
        """Connecte les signaux aux slots"""
        # Slider
        self.size_slider.valueChanged.connect(self._on_size_changed)
        
        # Boutons couleur
        self.ball_color_btn.colorChanged.connect(
            lambda c: setattr(self.settings_manager, 'ball_color', c)
        )
        self.offside_color_btn.colorChanged.connect(
            lambda c: setattr(self.settings_manager, 'offside_color', c)
        )
        self.arrow_color_btn.colorChanged.connect(
            lambda c: setattr(self.settings_manager, 'arrow_color', c)
        )
    
    def _on_size_changed(self, value):
        """Callback pour changement de taille"""
        scale = value / 100.0
        self._update_size_label(value)
        self.settings_manager.player_scale = scale
    
    def _update_size_label(self, value):
        """Met à jour le label de taille"""
        scale = value / 100.0
        self.size_label.setText(f"{scale:.1f}x")
    
    def _on_reset(self):
        """Réinitialise TOUT aux valeurs du thème courant + scale 1"""
        # reset couleurs (thème courant)
        if self._current_theme is not None:
            self.settings_manager.reset_theme_colors(self._current_theme)
        # reset taille joueur
        self.settings_manager.player_scale = 1.0
        # recharge les widgets
        self._load_current_settings()