# camera_controls.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, 
    QLabel, QSlider, QGroupBox, QButtonGroup, QRadioButton,
    QToolButton, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon
import os
from config import SVG_DIR

class CameraControlWidget(QWidget):
    """Widget de contrôle de la caméra"""
    
    # Signaux
    modeChanged = pyqtSignal(str)  # Émis quand le mode change
    zoomInRequested = pyqtSignal()
    zoomOutRequested = pyqtSignal()
    resetZoomRequested = pyqtSignal()
    
    def __init__(self, camera_manager, parent=None):
        super().__init__(parent)
        self.camera_manager = camera_manager
        self.current_mode = "full"
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Configure l'interface utilisateur"""
        layout = QVBoxLayout(self)
        
        # === Groupe : Modes de Caméra ===
        camera_group = QGroupBox("Camera Mode")
        camera_layout = QVBoxLayout(camera_group)
        
        # Sélecteur de mode principal
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("View:"))
        
        self.mode_combo = QComboBox()
        self.mode_combo.setMinimumWidth(120)
        for mode_key, mode_name in self.camera_manager.get_available_modes().items():
            self.mode_combo.addItem(mode_name, mode_key)
        camera_layout.addLayout(mode_layout)
        mode_layout.addWidget(self.mode_combo)
        
        # Boutons rapides pour les modes les plus utilisés
        quick_modes_layout = QHBoxLayout()
        quick_modes_layout.addWidget(QLabel("Quick:"))
        
        self.quick_full_btn = QPushButton("Full")
        self.quick_full_btn.setMaximumWidth(50)
        self.quick_full_btn.clicked.connect(lambda: self.set_mode("full"))
        quick_modes_layout.addWidget(self.quick_full_btn)
        
        self.quick_ball_btn = QPushButton("Ball")
        self.quick_ball_btn.setMaximumWidth(50)
        self.quick_ball_btn.setCheckable(True)
        self.quick_ball_btn.clicked.connect(lambda: self.set_mode("ball"))
        quick_modes_layout.addWidget(self.quick_ball_btn)
        
        self.quick_left_btn = QPushButton("Left")
        self.quick_left_btn.setMaximumWidth(50)
        self.quick_left_btn.clicked.connect(lambda: self.set_mode("left_half"))
        quick_modes_layout.addWidget(self.quick_left_btn)
        
        self.quick_right_btn = QPushButton("Right")
        self.quick_right_btn.setMaximumWidth(50)
        self.quick_right_btn.clicked.connect(lambda: self.set_mode("right_half"))
        quick_modes_layout.addWidget(self.quick_right_btn)
        
        quick_modes_layout.addStretch()
        camera_layout.addLayout(quick_modes_layout)
        
        layout.addWidget(camera_group)
        
        # === Groupe : Contrôles de Zoom ===
        zoom_group = QGroupBox("Zoom Controls")
        zoom_layout = QVBoxLayout(zoom_group)
        
        # Boutons de zoom
        zoom_buttons_layout = QHBoxLayout()
        
        self.zoom_in_btn = QPushButton("Zoom In")
        self.zoom_in_btn.setMaximumWidth(70)
        zoom_buttons_layout.addWidget(self.zoom_in_btn)
        
        self.zoom_out_btn = QPushButton("Zoom Out") 
        self.zoom_out_btn.setMaximumWidth(70)
        zoom_buttons_layout.addWidget(self.zoom_out_btn)
        
        self.reset_zoom_btn = QPushButton("Reset")
        self.reset_zoom_btn.setMaximumWidth(50)
        zoom_buttons_layout.addWidget(self.reset_zoom_btn)
        
        zoom_buttons_layout.addStretch()
        zoom_layout.addLayout(zoom_buttons_layout)
        
        layout.addWidget(zoom_group)
        
        # === Groupe : Zones Spéciales ===
        special_group = QGroupBox("Special Areas")
        special_layout = QVBoxLayout(special_group)
        
        # Boutons pour les surfaces de réparation
        penalty_layout = QHBoxLayout()
        penalty_layout.addWidget(QLabel("Penalty:"))
        
        self.penalty_left_btn = QPushButton("Left")
        self.penalty_left_btn.setMaximumWidth(60)
        self.penalty_left_btn.clicked.connect(lambda: self.set_mode("penalty_left"))
        penalty_layout.addWidget(self.penalty_left_btn)
        
        self.penalty_right_btn = QPushButton("Right")
        self.penalty_right_btn.setMaximumWidth(60)
        self.penalty_right_btn.clicked.connect(lambda: self.set_mode("penalty_right"))
        penalty_layout.addWidget(self.penalty_right_btn)
        
        penalty_layout.addStretch()
        special_layout.addLayout(penalty_layout)
        
        # Boutons pour les corners
        corner_layout = QHBoxLayout()
        corner_layout.addWidget(QLabel("Corners:"))
        
        self.corner_tl_btn = QPushButton("↖")
        self.corner_tl_btn.setMaximumWidth(30)
        self.corner_tl_btn.setToolTip("Top Left Corner")
        self.corner_tl_btn.clicked.connect(lambda: self.set_mode("top_left_corner"))
        corner_layout.addWidget(self.corner_tl_btn)
        
        self.corner_tr_btn = QPushButton("↗")
        self.corner_tr_btn.setMaximumWidth(30)
        self.corner_tr_btn.setToolTip("Top Right Corner")
        self.corner_tr_btn.clicked.connect(lambda: self.set_mode("top_right_corner"))
        corner_layout.addWidget(self.corner_tr_btn)
        
        self.corner_bl_btn = QPushButton("↙")
        self.corner_bl_btn.setMaximumWidth(30)
        self.corner_bl_btn.setToolTip("Bottom Left Corner")
        self.corner_bl_btn.clicked.connect(lambda: self.set_mode("bottom_left_corner"))
        corner_layout.addWidget(self.corner_bl_btn)
        
        self.corner_br_btn = QPushButton("↘")
        self.corner_br_btn.setMaximumWidth(30)
        self.corner_br_btn.setToolTip("Bottom Right Corner")
        self.corner_br_btn.clicked.connect(lambda: self.set_mode("bottom_right_corner"))
        corner_layout.addWidget(self.corner_br_btn)
        
        corner_layout.addStretch()
        special_layout.addLayout(corner_layout)
        
        layout.addWidget(special_group)
        
        # === Informations ===
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #888; font-size: 10px;")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        
        layout.addStretch()
    
    def _connect_signals(self):
        """Connecte les signaux"""
        self.mode_combo.currentIndexChanged.connect(self._on_mode_combo_changed)
        self.zoom_in_btn.clicked.connect(self.zoomInRequested.emit)
        self.zoom_out_btn.clicked.connect(self.zoomOutRequested.emit)
        self.reset_zoom_btn.clicked.connect(self.resetZoomRequested.emit)
    
    def _on_mode_combo_changed(self, index):
        """Gestionnaire pour le changement de mode via le combo"""
        mode_key = self.mode_combo.itemData(index)
        self.set_mode(mode_key)
    
    def set_mode(self, mode_key):
        """Change le mode de caméra"""
        self.current_mode = mode_key
        
        # Mettre à jour le combo box si nécessaire
        for i in range(self.mode_combo.count()):
            if self.mode_combo.itemData(i) == mode_key:
                if self.mode_combo.currentIndex() != i:
                    self.mode_combo.setCurrentIndex(i)
                break
        
        # Mettre à jour l'état des boutons
        self._update_button_states()
        
        # Mettre à jour les informations
        self._update_info()
        
        # Émettre le signal
        self.modeChanged.emit(mode_key)
    
    def _update_button_states(self):
        """Met à jour l'état visuel des boutons"""
        # Désactiver tous les boutons rapides
        for btn in [self.quick_full_btn, self.quick_ball_btn, self.quick_left_btn, self.quick_right_btn]:
            btn.setChecked(False)
            btn.setStyleSheet("")
        
        # Activer le bouton correspondant au mode actuel
        if self.current_mode == "full":
            self.quick_full_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        elif self.current_mode == "ball":
            self.quick_ball_btn.setChecked(True)
            self.quick_ball_btn.setStyleSheet("background-color: #2196F3; color: white;")
        elif self.current_mode == "left_half":
            self.quick_left_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        elif self.current_mode == "right_half":
            self.quick_right_btn.setStyleSheet("background-color: #4CAF50; color: white;")
    
    def _update_info(self):
        """Met à jour les informations affichées"""
        mode_name = self.camera_manager.get_available_modes().get(self.current_mode, "Unknown")
        
        info_text = f"Active: {mode_name}"
        
        if self.current_mode == "ball":
            info_text += "\n🔄 Following ball movement"
        elif "corner" in self.current_mode:
            info_text += "\n📍 Corner area focus"
        elif "penalty" in self.current_mode:
            info_text += "\n⚽ Penalty area focus"
        elif "half" in self.current_mode:
            info_text += "\n🏟️ Half-field view"
        
        self.info_label.setText(info_text)
    
    def update_ball_following_status(self, is_following):
        """Met à jour le statut de suivi de balle"""
        if is_following:
            self.quick_ball_btn.setText("Ball*")
            self.quick_ball_btn.setToolTip("Currently following ball")
        else:
            self.quick_ball_btn.setText("Ball")
            self.quick_ball_btn.setToolTip("Click to follow ball")
    
    def get_current_mode(self):
        """Retourne le mode actuel"""
        return self.current_mode


class CameraControlBar(QWidget):
    """Barre de contrôle compacte pour la caméra (à intégrer dans la toolbar)"""
    
    modeChanged = pyqtSignal(str)
    zoomInRequested = pyqtSignal()
    zoomOutRequested = pyqtSignal()
    resetZoomRequested = pyqtSignal()
    
    def __init__(self, camera_manager, parent=None):
        super().__init__(parent)
        self.camera_manager = camera_manager
        self._setup_ui()
    
    def _setup_ui(self):
        """Interface compacte pour la barre d'outils"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Séparateur
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep1)
        
        # Label
        layout.addWidget(QLabel("View:"))
        
        # Combo mode
        self.mode_combo = QComboBox()
        self.mode_combo.setMaximumWidth(100)
        for mode_key, mode_name in self.camera_manager.get_available_modes().items():
            # Noms courts pour la barre
            short_names = {
                "full": "Full",
                "ball": "Ball",
                "left_half": "Left",
                "right_half": "Right",
                "top_left_corner": "TL Corner",
                "top_right_corner": "TR Corner",
                "bottom_left_corner": "BL Corner", 
                "bottom_right_corner": "BR Corner",
                "penalty_left": "Left Penalty",
                "penalty_right": "Right Penalty"
            }
            short_name = short_names.get(mode_key, mode_name)
            self.mode_combo.addItem(short_name, mode_key)
        
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(self.mode_combo)
        
        # Boutons zoom
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setMaximumWidth(25)
        self.zoom_in_btn.setToolTip("Zoom In")
        self.zoom_in_btn.clicked.connect(self.zoomInRequested.emit)
        layout.addWidget(self.zoom_in_btn)
        
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.setMaximumWidth(25)
        self.zoom_out_btn.setToolTip("Zoom Out")
        self.zoom_out_btn.clicked.connect(self.zoomOutRequested.emit)
        layout.addWidget(self.zoom_out_btn)
        
        self.reset_btn = QPushButton("⌂")
        self.reset_btn.setMaximumWidth(25)
        self.reset_btn.setToolTip("Reset View")
        self.reset_btn.clicked.connect(self.resetZoomRequested.emit)
        layout.addWidget(self.reset_btn)
        
        # Séparateur final
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep2)
    
    def _on_mode_changed(self, index):
        """Gestionnaire changement de mode"""
        mode_key = self.mode_combo.itemData(index)
        self.modeChanged.emit(mode_key)
    
    def set_mode(self, mode_key):
        """Met à jour le mode sélectionné"""
        for i in range(self.mode_combo.count()):
            if self.mode_combo.itemData(i) == mode_key:
                self.mode_combo.setCurrentIndex(i)
                break