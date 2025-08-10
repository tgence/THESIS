"""
Properties panel for tactical zones.

Provides UI controls for modifying zone properties including color, width,
transparency, and rotation.
"""
# zone_properties.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, 
    QPushButton, QColorDialog, QSpinBox, QGroupBox, QGridLayout,
    QComboBox, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from annotation.arrow.arrow_properties import ColorButton


class ZoneProperties(QWidget):
    """Properties panel for tactical zones with color, width, transparency, and rotation controls."""
    
    # Signals
    colorChanged = pyqtSignal(str)
    widthChanged = pyqtSignal(int)
    fillAlphaChanged = pyqtSignal(int)
    rotationChanged = pyqtSignal(float)
    deleteRequested = pyqtSignal()
    propertiesConfirmed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_zone = None
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Title
        title = QLabel("Zone Properties")
        title.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # === Color and Style Group ===
        style_group = QGroupBox("Appearance")
        style_layout = QGridLayout()
        
        # Color
        style_layout.addWidget(QLabel("Color:"), 0, 0)
        self.color_btn = ColorButton()
        self.color_btn.colorChanged.connect(self._on_color_changed)
        style_layout.addWidget(self.color_btn, 0, 1)
        
        # Width
        style_layout.addWidget(QLabel("Width:"), 1, 0)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 10)
        self.width_spin.setValue(2)
        self.width_spin.valueChanged.connect(self._on_width_changed)
        style_layout.addWidget(self.width_spin, 1, 1)
        
        # Fill transparency
        style_layout.addWidget(QLabel("Fill Opacity:"), 2, 0)
        self.alpha_slider = QSlider(Qt.Horizontal)
        self.alpha_slider.setRange(0, 255)
        self.alpha_slider.setValue(50)
        self.alpha_slider.valueChanged.connect(self._on_alpha_changed)
        style_layout.addWidget(self.alpha_slider, 2, 1)
        
        self.alpha_label = QLabel("50")
        self.alpha_label.setFixedWidth(30)
        style_layout.addWidget(self.alpha_label, 2, 2)
        
        style_group.setLayout(style_layout)
        layout.addWidget(style_group)
        
        # === Rotation Group ===
        rotation_group = QGroupBox("Rotation")
        rotation_layout = QHBoxLayout()
        
        self.rotation_spin = QDoubleSpinBox()
        self.rotation_spin.setRange(-180, 180)
        self.rotation_spin.setSuffix("°")
        self.rotation_spin.setDecimals(1)
        self.rotation_spin.setValue(0)
        self.rotation_spin.valueChanged.connect(self._on_rotation_changed)
        rotation_layout.addWidget(self.rotation_spin)
        
        # Reset rotation button
        reset_rotation_btn = QPushButton("Reset")
        reset_rotation_btn.clicked.connect(self._on_reset_rotation)
        rotation_layout.addWidget(reset_rotation_btn)
        
        rotation_group.setLayout(rotation_layout)
        layout.addWidget(rotation_group)
        
        # === Control Buttons ===
        button_layout = QHBoxLayout()
        
        delete_btn = QPushButton("Delete Zone")
        delete_btn.setStyleSheet("background-color: #ff4444; color: white;")
        delete_btn.clicked.connect(self.deleteRequested.emit)
        button_layout.addWidget(delete_btn)
        
        button_layout.addStretch()
        
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.propertiesConfirmed.emit)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
        
        # Initial state
        self.setEnabled(False)
        
    def set_zone(self, zone):
        """Set the zone to edit."""
        self.current_zone = zone
        if zone:
            self.setEnabled(True)
            self._load_zone_properties()
        else:
            self.setEnabled(False)
            
    def _load_zone_properties(self):
        """Load properties from the current zone."""
        if not self.current_zone:
            return
            
        # Color
        self.color_btn.update_color(self.current_zone.zone_color)
        
        # Width
        self.width_spin.setValue(self.current_zone.zone_width)
        
        # Fill alpha
        alpha = self.current_zone.zone_fill_alpha
        self.alpha_slider.setValue(alpha)
        self.alpha_label.setText(str(alpha))
        
        # Rotation
        rotation = self.current_zone.get_rotation()
        self.rotation_spin.setValue(rotation)
        
    def _on_color_changed(self, color):
        """Handle color change."""
        if self.current_zone:
            self.current_zone.set_color(color)
        self.colorChanged.emit(color)
        
    def _on_width_changed(self, width):
        """Handle width change."""
        if self.current_zone:
            self.current_zone.set_width(width)
        self.widthChanged.emit(width)
        
    def _on_alpha_changed(self, alpha):
        """Handle fill alpha change."""
        self.alpha_label.setText(str(alpha))
        if self.current_zone:
            self.current_zone.set_fill_alpha(alpha)
        self.fillAlphaChanged.emit(alpha)
        
    def _on_rotation_changed(self, angle):
        """Handle rotation change."""
        if self.current_zone:
            self.current_zone.set_rotation(angle)
        self.rotationChanged.emit(angle)
        
    def _on_reset_rotation(self):
        """Reset rotation to 0."""
        self.rotation_spin.setValue(0)
