# camera_manager.py
"""
Camera manager for the pitch view.

Handles zoom, panning, camera presets (full, ball-follow, corners, penalties),
and smooth updates while following the ball.
"""

import numpy as np
from PyQt6.QtCore import QTimer, QRectF, QPointF, Qt
from PyQt6.QtWidgets import QGraphicsView
from PyQt6.QtGui import QTransform
from config import *

class CameraManager:
    """Manage camera modes, zoom, and ball-follow for the pitch view.

    Parameters
    ----------
    pitch_widget : object
        Widget exposing `view` (QGraphicsView) and `scene`, plus pitch bounds
        attributes (`X_MIN`, `X_MAX`, `Y_MIN`, `Y_MAX`, `PITCH_LENGTH`, `PITCH_WIDTH`).
    """
    
    def __init__(self, pitch_widget):
        self.pitch_widget = pitch_widget
        self.view = pitch_widget.view
        self.scene = pitch_widget.scene
        
        # Available camera modes (keys) - excluding "full" which is implicit
        self.CAMERA_MODES = {
            "ball": "Ball", 
            "top_left_corner": "TLC",
            "top_right_corner": "TRC", 
            "bottom_left_corner": "BLC",
            "bottom_right_corner": "BRC",
            "penalty_left": "LP",
            "penalty_right": "RP"
        }
        
        self.current_mode = "full"
        self.follow_ball_active = False
        self.current_ball_pos = None
        
        # Animation scaffolding for future smooth transitions
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._animate_step)
        self.animation_duration = 400  # ms (faster)
        self.animation_steps = 20      # fewer steps
        self.current_animation_step = 0
        self.animation_start_transform = QTransform()
        self.animation_target_transform = QTransform()
        self.animation_start_center = QPointF()
        self.animation_target_center = QPointF()
        
        # Save the full view area
        self.full_view_rect = None
        self._save_full_view()
    
    def _save_full_view(self):
        """Save the full-pitch rectangle used for the 'full' camera mode."""
        # Default full view at startup – fairly close zoom
        margin = SCENE_EXTRA_GRASS
        self.full_view_rect = QRectF(
            self.pitch_widget.X_MIN - margin,
            self.pitch_widget.Y_MIN - margin,
            self.pitch_widget.PITCH_LENGTH + 2*margin,
            self.pitch_widget.PITCH_WIDTH + 2*margin
        )
        
    
    def get_available_modes(self):
        """Return the available camera modes.

        Returns
        -------
        dict[str, str]
            Mapping of mode keys to short labels (e.g., ``{"ball": "Ball", ...}``).
        """
        return self.CAMERA_MODES
    
    def get_current_mode(self):
        """Return the active camera mode key.

        Returns
        -------
        str
            One of ``"full"``, ``"ball"``, corner or penalty presets.
        """
        return self.current_mode
    
    def set_camera_mode(self, mode, animate=True):
        """Change camera mode.

        Parameters
        ----------
        mode : str
            Target mode (``"full"``, ``"ball"``, corner presets, penalty presets).
        animate : bool, default True
            If True, apply a lightweight animation; otherwise set immediately.

        Returns
        -------
        bool
            True if the mode was applied (always True in current implementation).
        """
        if mode == "full" or mode not in self.CAMERA_MODES:
            self.current_mode = "full"
            self.follow_ball_active = False
            
            if animate:
                self._animate_to_mode("full")
            else:
                self._set_view_immediately("full")
            
            return True
            
        self.current_mode = mode
        self.follow_ball_active = (mode == "ball")
        
        if animate:
            self._animate_to_mode(mode)
        else:
            self._set_view_immediately(mode)
        
        return True
    
    def _get_mode_rect(self, mode):
        """Calculate the scene rectangle corresponding to a camera preset.

        Parameters
        ----------
        mode : str
            Camera mode key.

        Returns
        -------
        PyQt5.QtCore.QRectF
            Scene rectangle to fit for the given mode.
        """
        X_MIN = self.pitch_widget.X_MIN
        X_MAX = self.pitch_widget.X_MAX
        Y_MIN = self.pitch_widget.Y_MIN
        Y_MAX = self.pitch_widget.Y_MAX
        PITCH_LENGTH = self.pitch_widget.PITCH_LENGTH
        PITCH_WIDTH = self.pitch_widget.PITCH_WIDTH
        
   
        
        if mode == "full":
            return self.full_view_rect
            
        elif mode == "ball":
            if self.current_ball_pos:
                ball_area_size = 50
                return QRectF(
                    self.current_ball_pos[0] - ball_area_size/2,
                    self.current_ball_pos[1] - ball_area_size/2,
                    ball_area_size,
                    ball_area_size
                )
            else:
                return self.full_view_rect
    

        elif mode == "top_left_corner":
            # TLC (Top Left Corner in pitch coords) appears bottom-left on screen due to Y inversion
            return QRectF(
                X_MIN,                        # behind left goal
                 Y_MIN + (PITCH_WIDTH - PENALTY_AREA_WIDTH) / 2,      # Start at middle of field
                PITCH_LENGTH//2,             # Width to the middle
                PITCH_WIDTH * 0.8       
            )
            
        elif mode == "top_right_corner":
            # TRC appears bottom-right on screen due to Y inversion
            return QRectF(
                X_MIN + (PITCH_LENGTH - 3*PENALTY_AREA_LENGTH),    
                Y_MIN + (PITCH_WIDTH - PENALTY_AREA_WIDTH) / 2,     
                PITCH_LENGTH // 2 ,           
                PITCH_WIDTH * 0.8        
            )
            
        elif mode == "bottom_left_corner":
            # BLC appears top-left on screen due to Y inversion
            return QRectF(
                X_MIN,     
                Y_MIN,                           
                PITCH_LENGTH//2    ,           
                PITCH_WIDTH * 0.8                 
            )
            
        elif mode == "bottom_right_corner":
            # BRC appears top-right on screen due to Y inversion
            return QRectF(
                X_MIN + (PITCH_LENGTH - 3*PENALTY_AREA_LENGTH),    
                Y_MIN,                            
                PITCH_LENGTH//2,           
                PITCH_WIDTH * 0.8               
            )
        


        elif mode == "penalty_left":
            return QRectF(
                X_MIN - PENALTY_SPOT_DIST,
                Y_MIN + (PITCH_WIDTH - PENALTY_AREA_WIDTH)/2 - PENALTY_SPOT_DIST,
                PENALTY_AREA_LENGTH + PENALTY_SPOT_DIST*2,
                PENALTY_AREA_WIDTH + PENALTY_SPOT_DIST*2
            )
            
        elif mode == "penalty_right":
            return QRectF(
                X_MAX - PENALTY_AREA_LENGTH - PENALTY_SPOT_DIST,
                Y_MIN + (PITCH_WIDTH - PENALTY_AREA_WIDTH)/2 - PENALTY_SPOT_DIST,
                PENALTY_AREA_LENGTH + PENALTY_SPOT_DIST*2,
                PENALTY_AREA_WIDTH + PENALTY_SPOT_DIST*2
            )
        
        return self.full_view_rect
        
    def _set_view_immediately(self, mode):
        """Apply the camera preset immediately (keeping the Y inversion).

        Parameters
        ----------
        mode : str
            Camera mode key.
        """
        
        target_rect = self._get_mode_rect(mode)
        
        # Compute transform manually to keep scale(1, -1)
        view_rect = self.view.viewport().rect()
        
        # Calculate zoom factor to fit the target rectangle
        scale_x = view_rect.width() / target_rect.width()
        scale_y = view_rect.height() / target_rect.height()
        scale_factor = min(scale_x, scale_y) * 0.9
        
        # Center on the target rect
        center = target_rect.center()
        
        # Apply the transform without losing the scale(1, -1)
        transform = QTransform()
        transform.scale(scale_factor, scale_factor)
        transform.scale(1, -1)
        
        self.view.setTransform(transform)
        
        # Center on the point of interest
        self.view.centerOn(center)
        
        # Extra zoom factors per mode
        extra_zoom_factors = {
            "full": 2.5,
            "ball": 1.25,
            "penalty_left": 1.5,
            "penalty_right": 1.5,
            "top_left_corner": 1.0,
            "top_right_corner": 1.0,
            "bottom_left_corner": 1.0,
            "bottom_right_corner": 1.0,
        }
        
        if mode in extra_zoom_factors:
            extra_factor = extra_zoom_factors[mode]
            self.view.scale(extra_factor, extra_factor)
            

    
    def _animate_to_mode(self, mode):
        """Simplified animation stub that applies the mode directly.

        Parameters
        ----------
        mode : str
            Camera mode key.
        """
        if self.animation_timer.isActive():
            self.animation_timer.stop()
        
        # For simplicity, apply preset immediately; full animation would adjust transforms gradually
        self._set_view_immediately(mode)
    
    def _animate_step(self):
        """Execute one step of camera animation (currently disabled)."""
        # Animation disabled for now to avoid transform glitches
        pass
    
    def _ease_in_out_cubic(self, t):
        """Easing function for smooth animation.

        Parameters
        ----------
        t : float
            Normalized time in [0, 1].

        Returns
        -------
        float
            Eased value.
        """
        if t < 0.5:
            return 4 * t * t * t
        else:
            return 1 - pow(-2 * t + 2, 3) / 2
    
    def update_ball_position(self, x, y):
        """Update tracked ball position and adjust the view if following.

        Parameters
        ----------
        x, y : float
            Ball coordinates in scene units.
        """
        self.current_ball_pos = (x, y)
        
        if self.follow_ball_active and not np.isnan(x) and not np.isnan(y):
            self._update_ball_follow()
    
    def _update_ball_follow(self):
        """Pan smoothly towards the new ball position (if following)."""
        if not self.current_ball_pos:
            return
            
        # Smoothly move towards the ball's new position
        current_center = self.view.mapToScene(self.view.rect().center())
        target_center = QPointF(self.current_ball_pos[0], self.current_ball_pos[1])
        
        distance = np.sqrt((current_center.x() - target_center.x())**2 + 
                          (current_center.y() - target_center.y())**2)
        
        if distance > 1.5:
            new_center = QPointF(
                current_center.x() + (target_center.x() - current_center.x()) * 0.15,
                current_center.y() + (target_center.y() - current_center.y()) * 0.15
            )
            self.view.centerOn(new_center)
    
    def zoom_in(self, factor=1.2):
        """Zoom in by the given factor.

        Parameters
        ----------
        factor : float, default 1.2
            Scale factor applied to the view.
        """
        self.view.scale(factor, factor)
    
    def zoom_out(self, factor=0.83):
        """Zoom out by the given factor.

        Parameters
        ----------
        factor : float, default 0.83
            Scale factor applied to the view.
        """
        self.view.scale(factor, factor)
    
    def reset_zoom(self):
        """Reset to the full-pitch preset and disable ball-follow."""
        self.current_mode = "full"
        self.follow_ball_active = False
        self._set_view_immediately("full")