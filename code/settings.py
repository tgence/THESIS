# settings.py
"""
Visual settings management and dialog.

Provides:
- `SettingsManager`: central, signal-emitting store for visual preferences
- `ColorButton`: small helper widget to pick/show a color
- `SettingsDialog`: non-modal dialog to adjust player scale and colors
"""
# settings.py

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider, 
    QPushButton, QColorDialog, QGroupBox, QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QColor
from config import BALL_COLOR, CONFIG


class SettingsManager(QObject):
    """Central store for visual settings with Qt signals.

    Notes
    -----
    Emits granular and aggregate signals when settings change. Updating
    ``player_scale`` updates the global ``CONFIG.scale`` for size-dependent values.
    """
    
    # Signals emitted when settings change
    playerScaleChanged = pyqtSignal(float)
    ballColorChanged = pyqtSignal(str)
    offsideColorChanged = pyqtSignal(str)
    arrowColorChanged = pyqtSignal(str)
    settingsChanged = pyqtSignal()  # general signal for any change
    
    def __init__(self):
        super().__init__()
        
        # Defaults
        self._player_scale = 1.0
        self._ball_color = BALL_COLOR
        self._offside_color = "#FF40FF"  # default magenta
        self._arrow_color = "#000000"    # default black
        self._custom_arrow_color = False
        self._custom_offside_color = False
        
        # Bounds
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
            CONFIG.scale = value  # update global dynamic config
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
        # Set without re-emitting settingsChanged (avoid double update)
        self._ball_color = BALL_COLOR
        self._arrow_color = theme.get("arrow", "#000000")
        self._offside_color = theme.get("offside", "#FF40FF")
        self.settingsChanged.emit()
    
    def get_all_settings(self):
        """Return dictionary with all settings.

        Returns
        -------
        dict
            Current values for player scale and overlay colors.
        """
        return {
            'player_scale': self._player_scale,
            'ball_color': self._ball_color,
            'offside_color': self._offside_color,
            'arrow_color': self._arrow_color
        }


class ColorButton(QPushButton):
    """Push button that displays and lets users pick a color.

    Parameters
    ----------
    color : str, default '#FFFFFF'
        Initial color.
    parent : QWidget, optional
        Parent widget.
    """
    
    colorChanged = pyqtSignal(str)
    
    def __init__(self, color="#FFFFFF", parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(60, 30)
        self.update_color(color)
        self.clicked.connect(self._on_clicked)
        
    def _on_clicked(self):
        """Open a color selection dialog and emit ``colorChanged`` if accepted."""
        initial = QColor(self._color)
        color = QColorDialog.getColor(initial, self, "Choose color")
        if color.isValid():
            self.update_color(color.name())
            self.colorChanged.emit(color.name())
    
    def update_color(self, color):
        """Update button color and style sheet.

        Parameters
        ----------
        color : str
            Hex color string.
        """
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
        """Return current color string."""
        return self._color


class SettingsDialog(QDialog):
    """Non-modal dialog to adjust player size and overlay colors.

    Parameters
    ----------
    settings_manager : SettingsManager
        Settings manager instance used to get/set values.
    parent : QWidget, optional
        Parent window.
    """
    
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle("Visual Settings")
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setModal(False)  # non-modal to see live changes
        self.setFixedSize(350, 400)
        
        self._current_theme = getattr(parent, 'current_theme', None)
        self._setup_ui()
        self._load_current_settings()
        self._connect_signals()
        
    def _setup_ui(self):
        """Configure the dialog layout and widgets."""
        layout = QVBoxLayout(self)
        
        # === Player size group ===
        size_group = QGroupBox("Global Scale")
        size_layout = QVBoxLayout()
        
        # Slider with labels
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
        
        # Preset buttons (optional)
        preset_layout = QHBoxLayout()
        size_layout.addLayout(preset_layout)
        
        size_group.setLayout(size_layout)
        layout.addWidget(size_group)
        
        # === Colors group ===
        colors_group = QGroupBox("Colors")
        colors_layout = QGridLayout()
        
        # Ball color
        colors_layout.addWidget(QLabel("Ball :"), 0, 0)
        self.ball_color_btn = ColorButton()
        colors_layout.addWidget(self.ball_color_btn, 0, 1)
        
        # Offside line color
        colors_layout.addWidget(QLabel("Offside Line :"), 1, 0)
        self.offside_color_btn = ColorButton()
        colors_layout.addWidget(self.offside_color_btn, 1, 1)
        
        # Orientation arrows color
        colors_layout.addWidget(QLabel("Orientation Arrows :"), 2, 0)
        self.arrow_color_btn = ColorButton()
        colors_layout.addWidget(self.arrow_color_btn, 2, 1)
        
        colors_layout.setColumnStretch(0, 1)
        colors_layout.setColumnStretch(1, 0)
        colors_group.setLayout(colors_layout)
        layout.addWidget(colors_group)
        
        # === Control buttons ===
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
        """Load current settings into the widgets."""
        settings = self.settings_manager.get_all_settings()
        
        # Player size
        scale_value = int(settings['player_scale'] * 100)
        self.size_slider.setValue(scale_value)
        self._update_size_label(scale_value)
        
        # Colors
        self.ball_color_btn.update_color(settings['ball_color'])
        self.offside_color_btn.update_color(settings['offside_color'])
        self.arrow_color_btn.update_color(settings['arrow_color'])
    
    def _connect_signals(self):
        """Wire widget signals to handlers."""
        # Slider
        self.size_slider.valueChanged.connect(self._on_size_changed)
        
        # Color buttons
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
        """Handle player size slider change and propagate to settings manager."""
        scale = value / 100.0
        self._update_size_label(value)
        self.settings_manager.player_scale = scale
    
    def _update_size_label(self, value):
        """Update the size label text."""
        scale = value / 100.0
        self.size_label.setText(f"{scale:.1f}x")
    
    def _on_reset(self):
        """Reset everything to current theme values and scale 1."""
        # reset colors (current theme)
        if self._current_theme is not None:
            self.settings_manager.reset_theme_colors(self._current_theme)
        # reset player size
        self.settings_manager.player_scale = 1.0
        # reload widgets
        self._load_current_settings()