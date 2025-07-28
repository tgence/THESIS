# trajectory_manager.py

from PyQt5.QtGui import QPen, QColor, QBrush
from PyQt5.QtCore import Qt
from collections import deque
import numpy as np
from config import *
class TrajectoryManager:
    """Gère tous les types de trajectoires (passées et futures)"""

    def __init__(self, pitch_widget, home_colors, away_colors):
        self.pitch_widget = pitch_widget
        self.player_trails = {}
        self.future_trajectories = {}
        self.cached_frame = None  # Cache pour éviter de recalculer
        self.cached_interval = None
        self.home_colors = home_colors
        self.away_colors = away_colors
        
    def clear_trails(self):
        """Efface toutes les trajectoires"""
        self.player_trails.clear()
        self.future_trajectories.clear()
        self.cached_frame = None
        self.cached_interval = None
        
    def calculate_future_trajectories(self, current_frame, interval_seconds, xy_objects, 
                                    home_ids, away_ids, n_frames, get_frame_data_func):
        """Calcule les trajectoires futures pour la simulation (avec cache)"""
        # OPTIMISATION: Cache pour éviter de recalculer si même frame/interval
        if (self.cached_frame == current_frame and 
            self.cached_interval == interval_seconds and 
            self.future_trajectories):
            return
        
        future_frames = int(interval_seconds * FPS)
        end_frame = min(current_frame + future_frames, n_frames - 1)
        
        self.future_trajectories = {
            'players': {'Home': {}, 'Away': {}},
            'ball': []
        }
        
        # OPTIMISATION: Échantillonnage pour réduire le nombre de points
        sample_step = TRAJECTORY_SAMPLE_RATE
        
        for frame in range(current_frame, end_frame + 1, sample_step):
            half, idx, _ = get_frame_data_func(frame)
            progress = (frame - current_frame) / max(1, future_frames)
            
            # Joueurs
            for side, ids in [("Home", home_ids), ("Away", away_ids)]:
                try:
                    xy = xy_objects[half][side].xy[idx]
                    for i, pid in enumerate(ids):
                        if 2*i+1 < len(xy):  # Vérification des limites
                            x, y = xy[2*i], xy[2*i+1]
                            if not np.isnan(x) and not np.isnan(y):
                                if pid not in self.future_trajectories['players'][side]:
                                    self.future_trajectories['players'][side][pid] = []
                                # Stocker aussi le frame pour pouvoir comparer avec current_frame
                                self.future_trajectories['players'][side][pid].append((x, y, progress, frame))
                except (IndexError, KeyError):
                    continue
            
            # Balle
            try:
                ball_xy = xy_objects[half]["Ball"].xy[idx]
                if len(ball_xy) >= 2 and not np.isnan(ball_xy[0]):
                    # Stocker aussi le frame pour la balle
                    self.future_trajectories['ball'].append((ball_xy[0], ball_xy[1], progress, frame))
            except (IndexError, KeyError):
                continue
        
        # Mettre à jour le cache
        self.cached_frame = current_frame
        self.cached_interval = interval_seconds
    
    def draw_future_trajectories(self, show_players=True, show_ball=True, current_frame=None, 
                               loop_start=None, loop_end=None, interval_seconds=10.0):
        """Dessine les trajectoires futures avec effacement progressif pendant la loop"""
        
        # NOUVEAU: Calculer les frames de fade basé sur l'intervalle choisi
        fade_frames_players = int(interval_seconds * FPS)  # Utilise l'intervalle complet
        fade_frames_ball = int(interval_seconds * FPS)     # Même chose pour la balle
        
        if show_players:
            for side, players in self.future_trajectories.get('players', {}).items():
                for pid, positions in players.items():
                    base_color = self.home_colors[pid][0] if side == "Home" else self.away_colors[pid][0]
                    if len(positions) > 1:
                        sampled_positions = positions[::2]
                        
                        for i in range(len(sampled_positions) - 1):
                            x1, y1, p1, frame1 = sampled_positions[i]
                            x2, y2, p2, frame2 = sampled_positions[i+1]
                            
                            # Ne dessiner que si le segment n'a pas encore été "traversé"
                            if current_frame is not None and current_frame > frame1:
                                continue
                            
                            # NOUVEAU: Logique d'opacité inversée
                            color = QColor(base_color)
                            
                            if current_frame is not None:
                                frames_until_segment = frame1 - current_frame
                                
                                # Plus on est proche du segment, plus il est opaque (proche de 1.0)
                                # Plus on est loin du segment, plus il est transparent (proche de 0.2)
                                distance_factor = frames_until_segment / fade_frames_players
                                # Inverser : proche = opaque (1.0), loin = transparent (0.2)
                                final_alpha = max(0.2, 1.0 - distance_factor * 0.8)
                            else:
                                final_alpha = 0.8
                            
                            color.setAlphaF(final_alpha)
                            
                            # Ligne très fine et pointillée
                            pen = QPen(color, TRAJECTORY_PLAYER_LINE_WIDTH)
                            pen.setStyle(Qt.CustomDashLine)
                            pen.setDashPattern([1, 4])
                            pen.setCapStyle(Qt.RoundCap)
                            
                            line = self.pitch_widget.scene.addLine(x1, y1, x2, y2, pen)
                            line.setZValue(8)
                            self.pitch_widget.dynamic_items.append(line)
        
        if show_ball:
            ball_positions = self.future_trajectories.get('ball', [])
            if len(ball_positions) > 1:
                sampled_ball_positions = ball_positions[::2]
                
                for i in range(len(sampled_ball_positions) - 1):
                    x1, y1, p1, frame1 = sampled_ball_positions[i]
                    x2, y2, p2, frame2 = sampled_ball_positions[i+1]
                    
                    # Même logique pour la balle - ne dessiner que les segments futurs
                    if current_frame is not None and current_frame > frame1:
                        continue
                    
                    # NOUVEAU: Même logique inversée pour la balle
                    color = QColor(BALL_COLOR)
                    
                    if current_frame is not None:
                        frames_until_segment = frame1 - current_frame
                        
                        # Plus on est proche du segment, plus il est opaque (proche de 1.0)
                        # Plus on est loin du segment, plus il est transparent (proche de 0.3)
                        distance_factor = frames_until_segment / fade_frames_ball
                        # Inverser : proche = opaque (1.0), loin = transparent (0.3)
                        final_alpha = max(0.3, 1.0 - distance_factor * 0.7)
                    else:
                        final_alpha = 0.9
                    
                    color.setAlphaF(final_alpha)
                    
                    pen = QPen(color, TRAJECTORY_BALL_LINE_WIDTH)
                    pen.setStyle(TRAJECTORY_STYLE)
                    pen.setCapStyle(Qt.RoundCap)
                    
                    line = self.pitch_widget.scene.addLine(x1, y1, x2, y2, pen)
                    line.setZValue(95)
                    self.pitch_widget.dynamic_items.append(line)
                
                # Position finale - toujours opaque à 1.0 et visible tant qu'elle n'est pas atteinte
                if ball_positions:
                    final_x, final_y, final_progress, final_frame = ball_positions[-1]
                    
                    # Afficher tant que la position finale n'est pas atteinte
                    if current_frame is None or current_frame < final_frame:
                        # Rayon légèrement plus gros et cercle complet
                        final_radius = BALL_RADIUS * 1.2  # 20% plus gros que la balle normale
                        pen_color = QColor(BALL_COLOR)
                        pen_color.setAlphaF(1.0)  # TOUJOURS opaque à 1.0
                        
                        # Cercle complet (pas de pointillés) avec contour fin
                        final_ball = self.pitch_widget.scene.addEllipse(
                            final_x - final_radius, final_y - final_radius,
                            final_radius * 2, final_radius * 2,
                            QPen(pen_color, 0.4, Qt.SolidLine),  # Ligne solide
                            QBrush(Qt.NoBrush)
                        )
                        final_ball.setZValue(96)
                        self.pitch_widget.dynamic_items.append(final_ball)