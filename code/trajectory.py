# trajectory.py - Version améliorée avec trajectoires simulées

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
        self.simulated_trajectories = {}  # Trajectoires tactiques
        
    def clear_trails(self):
        """Efface toutes les trajectoires"""
        self.player_trails.clear()
        self.future_trajectories.clear()
        self.simulated_trajectories.clear()
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
                               loop_start=None, loop_end=None, interval_seconds=10.0, ball_color=BALL_COLOR):
        """Dessine les trajectoires futures avec effacement progressif pendant la loop"""
        
        # Calculer les frames de fade basé sur l'intervalle choisi
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
                            
                            # Logique d'opacité inversée
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
                            pen = QPen(color, CONFIG.TRAJECTORY_PLAYER_LINE_WIDTH)
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
                    
                    # Même logique inversée pour la balle
                    color = QColor(ball_color)
                    
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
                    
                    pen = QPen(color, CONFIG.TRAJECTORY_BALL_LINE_WIDTH)
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
                        final_radius = CONFIG.BALL_RADIUS * 1.2  # 20% plus gros que la balle normale
                        pen_color = QColor(ball_color)
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

    def draw_simulated_trajectories(self, simulated_data, current_frame, loop_start, loop_end, ball_color=BALL_COLOR):
        """Dessine les trajectoires simulées par-dessus les vraies trajectoires"""
        if not simulated_data:
            return
        
        # Dessiner les trajectoires des joueurs simulés
        players_data = simulated_data.get('players', {})
        for player_id, positions in players_data.items():
            if len(positions) > 1:
                # Déterminer l'équipe pour la couleur
                side = "Home" if player_id in self.home_colors else "Away"
                base_color = self.home_colors.get(player_id, ["#FF0000"])[0] if side == "Home" else self.away_colors.get(player_id, ["#0000FF"])[0]
                
                # Dessiner les segments de trajectoire avec effacement progressif
                for i in range(len(positions) - 1):
                    x1, y1, frame1 = positions[i]
                    x2, y2, frame2 = positions[i + 1]
                    
                    # Ne dessiner que les segments futurs
                    if current_frame is not None and current_frame > frame1:
                        continue
                    
                    # Calculer l'opacité selon la distance temporelle
                    color = QColor(base_color)
                    if current_frame is not None:
                        frames_until_segment = frame1 - current_frame
                        total_frames = loop_end - loop_start
                        
                        if total_frames > 0:
                            distance_factor = frames_until_segment / total_frames
                            # Plus proche = plus opaque
                            final_alpha = max(0.4, 1.0 - distance_factor * 0.6)
                        else:
                            final_alpha = 0.9
                    else:
                        final_alpha = 0.9
                    
                    color.setAlphaF(final_alpha)
                    
                    # Ligne plus épaisse et continue pour la simulation
                    pen = QPen(color, CONFIG.TRAJECTORY_PLAYER_LINE_WIDTH * 2)
                    pen.setStyle(Qt.SolidLine)
                    pen.setCapStyle(Qt.RoundCap)
                    
                    line = self.pitch_widget.scene.addLine(x1, y1, x2, y2, pen)
                    line.setZValue(15)  # Au-dessus des trajectoires réelles
                    self.pitch_widget.dynamic_items.append(line)
        
        # Dessiner la trajectoire de la balle simulée
        ball_positions = simulated_data.get('ball', [])
        if len(ball_positions) > 1:
            for i in range(len(ball_positions) - 1):
                x1, y1, frame1 = ball_positions[i]
                x2, y2, frame2 = ball_positions[i + 1]
                
                # Ne dessiner que les segments futurs
                if current_frame is not None and current_frame > frame1:
                    continue
                
                # Calculer l'opacité pour la balle
                color = QColor(BALL_COLOR)
                if current_frame is not None:
                    frames_until_segment = frame1 - current_frame
                    total_frames = loop_end - loop_start
                    
                    if total_frames > 0:
                        distance_factor = frames_until_segment / total_frames
                        # Plus proche = plus opaque
                        final_alpha = max(0.5, 1.0 - distance_factor * 0.5)
                    else:
                        final_alpha = 1.0
                else:
                    final_alpha = 1.0
                
                color.setAlphaF(final_alpha)
                
                # Ligne plus épaisse pour la balle simulée
                pen = QPen(color, CONFIG.TRAJECTORY_BALL_LINE_WIDTH * 2)
                pen.setStyle(Qt.SolidLine)
                pen.setCapStyle(Qt.RoundCap)
                
                line = self.pitch_widget.scene.addLine(x1, y1, x2, y2, pen)
                line.setZValue(98)  # Au-dessus des trajectoires réelles de balle
                self.pitch_widget.dynamic_items.append(line)
            
            # Position finale de la balle simulée
            if ball_positions:
                final_x, final_y, final_frame = ball_positions[-1]
                
                if current_frame is None or current_frame < final_frame:
                    final_radius = CONFIG.BALL_RADIUS * 1.3
                    pen_color = QColor(ball_color)
                    pen_color.setAlphaF(1.0)
                    
                    # Cercle de destination final
                    final_ball = self.pitch_widget.scene.addEllipse(
                        final_x - final_radius, final_y - final_radius,
                        final_radius * 2, final_radius * 2,
                        QPen(pen_color, 0.6, Qt.SolidLine),
                        QBrush(Qt.NoBrush)
                    )
                    final_ball.setZValue(99)
                    self.pitch_widget.dynamic_items.append(final_ball)

    def draw_non_associated_arrows(self, arrows):
        """Dessine les flèches non associées de façon distincte"""
        for arrow in arrows:
            if hasattr(arrow, 'childItems'):
                for item in arrow.childItems():
                    if hasattr(item, 'pen'):
                        # Rendre les flèches non associées plus transparentes
                        pen = item.pen()
                        color = pen.color()
                        color.setAlphaF(0.5)
                        pen.setColor(color)
                        item.setPen(pen)
                    if hasattr(item, 'brush'):
                        brush = item.brush()
                        color = brush.color()
                        color.setAlphaF(0.5)
                        brush.setColor(color)
                        item.setBrush(brush)

    def highlight_associated_arrows(self, tactical_arrows):
        """Met en évidence les flèches associées selon leur type"""
        for tactical_arrow in tactical_arrows:
            arrow = tactical_arrow['arrow']
            action_type = tactical_arrow['action_type']
            
            # Couleurs selon le type d'action
            highlight_colors = {
                'pass': '#00FF00',    # Vert pour les passes
                'run': '#FFD700',     # Jaune pour les courses
                'dribble': '#FF8C00'  # Orange pour les dribbles
            }
            
            highlight_color = QColor(highlight_colors.get(action_type, '#FFFFFF'))
            
            if hasattr(arrow, 'childItems'):
                for item in arrow.childItems():
                    if hasattr(item, 'pen'):
                        pen = item.pen()
                        pen.setColor(highlight_color)
                        pen.setWidth(pen.width() * 1.5)  # Légèrement plus épais
                        item.setPen(pen)
                    if hasattr(item, 'brush'):
                        brush = item.brush()
                        brush.setColor(highlight_color)
                        item.setBrush(brush)