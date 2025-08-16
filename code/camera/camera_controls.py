"""
Compact camera control widget for the tools panel.

Lets users switch camera presets and control zoom; emits signals to the
`CameraManager` held by the main window.
"""
# camera_controls.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QGroupBox, QFrame, QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

class CameraControlWidget(QWidget):
    """Compact camera control widget with mode buttons and zoom controls.

    Parameters
    ----------
    camera_manager : CameraManager object
        Instance managing camera modes and zoom on the main pitch view.
    parent : QWidget, optional
        Parent widget.
    """
    
    # Signals
    modeChanged = pyqtSignal(str)
    zoomInRequested = pyqtSignal()
    zoomOutRequested = pyqtSignal()
    resetZoomRequested = pyqtSignal()
    
    def __init__(self, camera_manager, parent=None):
        super().__init__(parent)
        self.camera_manager = camera_manager
        self.current_mode = "full"
        self.mode_buttons = {}
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Configure a compact user interface (buttons and labels)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        
        # === Group: Camera View ===
        camera_group = QGroupBox("Camera View")
        camera_group.setMaximumHeight(250)  # slightly more space than before
        camera_layout = QVBoxLayout(camera_group)
        camera_layout.setSpacing(6)
        
        # === Zoom controls ===
        zoom_layout = QHBoxLayout()
        zoom_layout.setSpacing(3)
        
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.setMaximumWidth(25)
        self.zoom_out_btn.setMaximumHeight(25)
        self.zoom_out_btn.setToolTip("Zoom Out")
        zoom_layout.addWidget(self.zoom_out_btn)
        
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setMaximumWidth(25)
        self.zoom_in_btn.setMaximumHeight(25)
        self.zoom_in_btn.setToolTip("Zoom In")
        zoom_layout.addWidget(self.zoom_in_btn)
        
        self.reset_zoom_btn = QPushButton("Reset")
        self.reset_zoom_btn.setMaximumWidth(40)  # compact reset button
        self.reset_zoom_btn.setMaximumHeight(25)
        self.reset_zoom_btn.setToolTip("Reset to Full View")
        self.reset_zoom_btn.setStyleSheet("font-size: 8px; padding: 2px;")  # Smaller font
        zoom_layout.addWidget(self.reset_zoom_btn)
        
        zoom_layout.addStretch()
        camera_layout.addLayout(zoom_layout)
        
        # === Mode buttons (grid to save space) ===
        modes_layout = QGridLayout()
        modes_layout.setSpacing(2)
        
        # Define buttons and their positions in the grid (no Full button)
        button_config = [
            ("ball", "Ball", 0, 0),
            ("top_left_corner", "TLC", 0, 1),
            ("top_right_corner", "TRC", 1, 0),
            ("bottom_left_corner", "BLC", 1, 1),
            ("bottom_right_corner", "BRC", 2, 0),
            ("penalty_left", "LP", 2, 1),
            ("penalty_right", "RP", 3, 0),
        ]
        
        for mode_key, display_name, row, col in button_config:
            btn = QPushButton(display_name)
            btn.setMaximumWidth(55)
            btn.setMaximumHeight(30)
            btn.setCheckable(True)
            btn.setContentsMargins(0, 0, 0, 0)  # No margins at all
            btn.setStyleSheet("""
                QPushButton {
                    padding: 0px 1px; 
                    font-size: 9px;  
                    margin: 0px;
                    border: 1px solid #555;
                }
            """)
            btn.clicked.connect(lambda checked, mode=mode_key: self.set_mode(mode))
            
            # Tooltips with full names
            tooltip_names = {
                "ball": "Follow Ball",
                "left_half": "Left Half",
                "right_half": "Right Half",
                "top_left_corner": "Top Left Corner",     # Now correct
                "top_right_corner": "Top Right Corner",   # Now correct
                "bottom_left_corner": "Bottom Left Corner",     # Now correct
                "bottom_right_corner": "Bottom Right Corner",   # Now correct
                "penalty_left": "Left Penalty",
                "penalty_right": "Right Penalty"
            }
            btn.setToolTip(tooltip_names.get(mode_key, display_name))
            
            self.mode_buttons[mode_key] = btn
            modes_layout.addWidget(btn, row, col)
        
        camera_layout.addLayout(modes_layout)
        
        # === Compact info ===
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #888; font-size: 9px;")
        self.info_label.setWordWrap(True)
        self.info_label.setMinimumHeight(40)  # fixed to avoid layout jumps
        self.info_label.setMaximumHeight(40)
        camera_layout.addWidget(self.info_label)
        
        layout.addWidget(camera_group)
        
        # Start with default mode (no button selected)
        self.current_mode = "full"
        self._update_info()
    
    def _connect_signals(self):
        """Connect internal button signals to external signals."""
        self.zoom_in_btn.clicked.connect(self.zoomInRequested.emit)
        self.zoom_out_btn.clicked.connect(self.zoomOutRequested.emit)
        self.reset_zoom_btn.clicked.connect(self.resetZoomRequested.emit)
    
    def set_mode(self, mode_key):
        """Change camera mode and update button visuals.

        Parameters
        ----------
        mode_key : str
            One of the available keys exposed by the camera manager.
        """
        if mode_key == "full":
            # Full mode: no button checked
            self.current_mode = "full"
            for btn in self.mode_buttons.values():
                btn.setChecked(False)
                btn.setStyleSheet("padding: 1px 2px; font-size: 10px;")
        else:
            if mode_key not in self.mode_buttons:
                return
                
            self.current_mode = mode_key
            
            # Update button states (single selection)
            for key, btn in self.mode_buttons.items():
                btn.setChecked(key == mode_key)
                
                # Special style for the active button
                if key == mode_key:
                    if key == "ball":
                        btn.setStyleSheet("""
                            QPushButton:checked {
                                background-color: #2196F3; 
                                color: white; 
                                font-weight: bold;
                                padding: 1px 2px; 
                                font-size: 10px;
                            }
                        """)
                    else:
                        btn.setStyleSheet("""
                            QPushButton:checked {
                                background-color: #4CAF50; 
                                color: white; 
                                font-weight: bold;
                                padding: 1px 2px; 
                                font-size: 10px;
                            }
                        """)
                else:
                    btn.setStyleSheet("padding: 1px 2px; font-size: 10px;")
        
        # Update info label
        self._update_info()
        
        # Emit modeChanged signal
        self.modeChanged.emit(mode_key)
    
    def _update_info(self):
        """Update the small info label to reflect the active mode."""
        mode_names = {
            "full": "Full Pitch",
            "ball": "Following Ball",
            "left_half": "Left Half",
            "right_half": "Right Half", 
            "top_left_corner": "Top Left Corner",     # Now correct
            "top_right_corner": "Top Right Corner",   # Now correct
            "bottom_left_corner": "Bottom Left Corner",     # Now correct
            "bottom_right_corner": "Bottom Right Corner",   # Now correct
            "penalty_left": "Left Penalty",
            "penalty_right": "Right Penalty"
        }
        
        mode_name = mode_names.get(self.current_mode, "Unknown")
        self.info_label.setText(f"Active: {mode_name}")
    
    def update_ball_status(self, is_following):
        """Update the tooltip to reflect whether the ball is being followed.

        Parameters
        ----------
        is_following : bool
            True if camera is in ball-follow mode.
        """
        ball_btn = self.mode_buttons.get("ball")
        if ball_btn:
            # Keep text as "BALL"; only tooltip reflects follow state
            ball_btn.setText("BALL")
            if is_following:
                ball_btn.setToolTip("Currently following ball")
            else:
                ball_btn.setToolTip("Click to follow ball")
    
    def get_current_mode(self):
        """Return the current camera mode key.

        Returns
        -------
        str
            Current mode key (e.g., 'full', 'ball', corner, penalty).
        """
        return self.current_mode

