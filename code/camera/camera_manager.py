# camera_manager.py - SOLUTION FINALE

import numpy as np
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRectF, QPointF
from PyQt5.QtWidgets import QGraphicsView
from PyQt5.QtGui import QTransform
from config import *

class CameraManager:
    """Gestionnaire des modes de caméra et zoom pour le terrain"""
    
    def __init__(self, pitch_widget):
        self.pitch_widget = pitch_widget
        self.view = pitch_widget.view
        self.scene = pitch_widget.scene
        
        # Modes de caméra disponibles (noms simplifiés) - SANS FULL
        self.CAMERA_MODES = {
            "ball": "Ball", 
            "left_half": "LH",
            "right_half": "RH",
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
        
        # Animation pour transitions fluides
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._animate_step)
        self.animation_duration = 400  # ms (plus rapide)
        self.animation_steps = 20      # moins d'étapes
        self.current_animation_step = 0
        self.animation_start_transform = QTransform()
        self.animation_target_transform = QTransform()
        self.animation_start_center = QPointF()
        self.animation_target_center = QPointF()
        
        # Sauvegarde de la vue complète
        self.full_view_rect = None
        self._save_full_view()
    
    def _save_full_view(self):
        """Sauvegarde la vue complète du terrain avec zoom de base"""
        # Vue complète par défaut au démarrage - ZOOM TRÈS PROCHE
        margin = SCENE_EXTRA_GRASS * 0.01
        self.full_view_rect = QRectF(
            self.pitch_widget.X_MIN - margin,
            self.pitch_widget.Y_MIN - margin,
            self.pitch_widget.PITCH_LENGTH + 2*margin,
            self.pitch_widget.PITCH_WIDTH + 2*margin
        )
        
    
    def get_available_modes(self):
        """Retourne la liste des modes disponibles"""
        return self.CAMERA_MODES
    
    def get_current_mode(self):
        """Retourne le mode actuel"""
        return self.current_mode
    
    def set_camera_mode(self, mode, animate=True):
        """Change le mode de caméra"""
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
        """Calculate the rectangle for a given camera mode"""
        X_MIN = self.pitch_widget.X_MIN
        X_MAX = self.pitch_widget.X_MAX
        Y_MIN = self.pitch_widget.Y_MIN
        Y_MAX = self.pitch_widget.Y_MAX
        PITCH_LENGTH = self.pitch_widget.PITCH_LENGTH
        PITCH_WIDTH = self.pitch_widget.PITCH_WIDTH
        
        margin = 5
        corner_size = 35
        penalty_margin = 5
        
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
                
        elif mode == "left_half":
            return QRectF(
                X_MIN - margin,
                Y_MIN - margin,
                PITCH_LENGTH/2 + margin*2,
                PITCH_WIDTH + margin*2
            )
            
        elif mode == "right_half":
            return QRectF(
                X_MIN + PITCH_LENGTH/2 - margin,
                Y_MIN - margin,
                PITCH_LENGTH/2 + margin*2,
                PITCH_WIDTH + margin*2
            )
            
        elif mode == "top_left_corner":
            return QRectF(
                X_MIN - margin,
                Y_MAX - corner_size,
                corner_size,
                corner_size + margin
            )
            
        elif mode == "top_right_corner":
            return QRectF(
                X_MAX - corner_size + margin,
                Y_MAX - corner_size,
                corner_size,
                corner_size + margin
            )
            
        elif mode == "bottom_left_corner":
            return QRectF(
                X_MIN - margin,
                Y_MIN - margin,
                corner_size,
                corner_size + margin
            )
            
        elif mode == "bottom_right_corner":
            return QRectF(
                X_MAX - corner_size + margin,
                Y_MIN - margin,
                corner_size,
                corner_size + margin
            )
            
        elif mode == "penalty_left":
            penalty_area_y = Y_MIN + (PITCH_WIDTH - PENALTY_AREA_WIDTH)/2
            return QRectF(
                X_MIN - penalty_margin,
                penalty_area_y - penalty_margin,
                PENALTY_AREA_LENGTH + penalty_margin*2,
                PENALTY_AREA_WIDTH + penalty_margin*2
            )
            
        elif mode == "penalty_right":
            penalty_area_y = Y_MIN + (PITCH_WIDTH - PENALTY_AREA_WIDTH)/2
            return QRectF(
                X_MAX - PENALTY_AREA_LENGTH - penalty_margin,
                penalty_area_y - penalty_margin,
                PENALTY_AREA_LENGTH + penalty_margin*2,
                PENALTY_AREA_WIDTH + penalty_margin*2
            )
        
        return self.full_view_rect
    
    def _set_view_immediately(self, mode):
        """NOUVELLE MÉTHODE : Zoom manuel sans fitInView"""
        target_rect = self._get_mode_rect(mode)
        
        # Calculer la transformation manuellement pour conserver scale(1, -1)
        view_rect = self.view.viewport().rect()
        
        # Calculer le facteur de zoom pour faire tenir le rectangle cible
        scale_x = view_rect.width() / target_rect.width()
        scale_y = view_rect.height() / target_rect.height()
        scale_factor = min(scale_x, scale_y) * 0.9  # 0.9 pour une petite marge
        
        # Centre du rectangle cible
        center = target_rect.center()
        
        # Appliquer la transformation SANS écraser scale(1, -1)
        transform = QTransform()
        # D'abord le zoom
        transform.scale(scale_factor, scale_factor)
        # Puis l'inversion Y (CRITIQUE pour maintenir le référentiel)
        transform.scale(1, -1)
        
        # Appliquer la transformation
        self.view.setTransform(transform)
        
        # Centrer sur le point d'intérêt
        self.view.centerOn(center)
    
    def _animate_to_mode(self, mode):
        """Animation simplifiée vers le mode"""
        if self.animation_timer.isActive():
            self.animation_timer.stop()
        
        # Pour simplifier, on fait juste un appel direct
        # L'animation complète nécessiterait de recalculer toutes les transformations
        self._set_view_immediately(mode)
    
    def _animate_step(self):
        """Execute one step of camera animation"""
        # Animation désactivée pour éviter les problèmes de transformation
        pass
    
    def _ease_in_out_cubic(self, t):
        """Easing function for smooth animation"""
        if t < 0.5:
            return 4 * t * t * t
        else:
            return 1 - pow(-2 * t + 2, 3) / 2
    
    def update_ball_position(self, x, y):
        """Met à jour la position de la balle pour le suivi"""
        self.current_ball_pos = (x, y)
        
        if self.follow_ball_active and not np.isnan(x) and not np.isnan(y):
            self._update_ball_follow()
    
    def _update_ball_follow(self):
        """Met à jour la vue pour suivre la balle"""
        if not self.current_ball_pos:
            return
            
        # Mouvement fluide vers la nouvelle position de la balle
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
        """Zoom avant"""
        self.view.scale(factor, factor)
    
    def zoom_out(self, factor=0.83):
        """Zoom arrière"""
        self.view.scale(factor, factor)
    
    def reset_zoom(self):
        """Remet le zoom par défaut en mode full"""
        self.current_mode = "full"
        self.follow_ball_active = False
        self._set_view_immediately("full")