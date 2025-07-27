# trajectory_manager.py

from PyQt5.QtGui import QPen, QColor, QBrush
from PyQt5.QtCore import Qt
from collections import deque
import numpy as np
from config import BALL_RADIUS, FPS

class TrajectoryManager:
    """Gère tous les types de trajectoires (passées et futures)"""
    
    def __init__(self, pitch_widget):
        self.pitch_widget = pitch_widget
        self.player_trails = {}
        self.future_trajectories = {}
        
    def clear_trails(self):
        """Efface toutes les trajectoires"""
        self.player_trails.clear()
        self.future_trajectories.clear()
        
    def calculate_future_trajectories(self, current_frame, interval_seconds, xy_objects, 
                                    home_ids, away_ids, n_frames, get_frame_data_func):
        """Calcule les trajectoires futures pour la simulation"""
        future_frames = int(interval_seconds * FPS)
        end_frame = min(current_frame + future_frames, n_frames - 1)
        
        self.future_trajectories = {
            'players': {'Home': {}, 'Away': {}},
            'ball': []
        }
        
        for frame in range(current_frame, end_frame + 1):
            half, idx, _ = get_frame_data_func(frame)
            progress = (frame - current_frame) / max(1, future_frames)
            
            # Joueurs
            for side, ids in [("Home", home_ids), ("Away", away_ids)]:
                xy = xy_objects[half][side].xy[idx]
                for i, pid in enumerate(ids):
                    x, y = xy[2*i], xy[2*i+1]
                    if not np.isnan(x) and not np.isnan(y):
                        if pid not in self.future_trajectories['players'][side]:
                            self.future_trajectories['players'][side][pid] = []
                        self.future_trajectories['players'][side][pid].append((x, y, progress))
            
            # Balle
            ball_xy = xy_objects[half]["Ball"].xy[idx]
            if not np.isnan(ball_xy[0]):
                self.future_trajectories['ball'].append((ball_xy[0], ball_xy[1], progress))
    
    def draw_player_trail(self, positions, color_base, is_home=True):
        """Dessine la trajectoire d'un joueur"""
        if len(positions) < 2:
            return
            
        for i in range(len(positions) - 1):
            x1, y1, a1 = positions[i]
            x2, y2, a2 = positions[i+1]
            
            color = QColor(color_base)
            color.setAlphaF(a2 * 0.5)
            pen = QPen(color, 0.3)
            
            line = self.pitch_widget.scene.addLine(x1, y1, x2, y2, pen)
            line.setZValue(5)
            self.pitch_widget.dynamic_items.append(line)
    
    def draw_ball_trail(self, positions, style="dash"):
        """Dessine la trajectoire de la balle"""
        if len(positions) < 2:
            return
            
        for i in range(len(positions) - 1):
            x1, y1 = positions[i][:2]
            x2, y2 = positions[i+1][:2]
            
            pen = QPen(QColor("#FFA500"), 0.5)
            pen.setStyle(Qt.DashLine if style == "dash" else Qt.DotLine)
            
            line = self.pitch_widget.scene.addLine(x1, y1, x2, y2, pen)
            line.setZValue(90)
            self.pitch_widget.dynamic_items.append(line)
    
    def draw_future_trajectories(self, show_players=True, show_ball=True):
        """Dessine les trajectoires futures (mode simulation)"""
        if show_players:
            for side, players in self.future_trajectories.get('players', {}).items():
                base_color = "#0066CC" if side == "Home" else "#CC0000"
                
                for pid, positions in players.items():
                    if len(positions) > 1:
                        for i in range(len(positions) - 1):
                            x1, y1, p1 = positions[i]
                            x2, y2, p2 = positions[i+1]
                            
                            color = QColor(base_color)
                            color.setAlphaF(0.6 * (1 - p2 * 0.7))
                            
                            pen = QPen(color, 0.5)
                            pen.setStyle(Qt.DotLine)
                            
                            line = self.pitch_widget.scene.addLine(x1, y1, x2, y2, pen)
                            line.setZValue(8)
                            self.pitch_widget.dynamic_items.append(line)
        
        if show_ball:
            ball_positions = self.future_trajectories.get('ball', [])
            if len(ball_positions) > 1:
                for i in range(len(ball_positions) - 1):
                    x1, y1, p1 = ball_positions[i]
                    x2, y2, p2 = ball_positions[i+1]
                    
                    color = QColor("#FFA500")
                    color.setAlphaF(0.8 * (1 - p2 * 0.5))
                    
                    pen = QPen(color, 1.0)
                    pen.setStyle(Qt.DashLine)
                    
                    line = self.pitch_widget.scene.addLine(x1, y1, x2, y2, pen)
                    line.setZValue(95)
                    self.pitch_widget.dynamic_items.append(line)
                
                # Position finale
                if ball_positions:
                    x, y, _ = ball_positions[-1]
                    final_ball = self.pitch_widget.scene.addEllipse(
                        x - BALL_RADIUS * 1.2, y - BALL_RADIUS * 1.2,
                        BALL_RADIUS * 2.4, BALL_RADIUS * 2.4,
                        QPen(QColor("#FFA500"), 1.5, Qt.DashLine),
                        QBrush(Qt.NoBrush)
                    )
                    final_ball.setZValue(96)
                    self.pitch_widget.dynamic_items.append(final_ball)
    
    def collect_past_trajectories(self, start_frame, end_frame, xy_objects, home_ids, 
                                 away_ids, get_frame_data_func, max_trail_length=None):
        """Collecte les trajectoires passées"""
        if max_trail_length is None:
            max_trail_length = 5 * FPS
            
        trail_data = {'players': {}, 'ball': []}
        
        for frame in range(start_frame, end_frame + 1):
            half, idx, _ = get_frame_data_func(frame)
            alpha = 0.3 + 0.7 * ((frame - start_frame) / max(1, (end_frame - start_frame)))
            
            # Joueurs
            for side, ids in [("Home", home_ids), ("Away", away_ids)]:
                xy = xy_objects[half][side].xy[idx]
                for i, pid in enumerate(ids):
                    x, y = xy[2*i], xy[2*i+1]
                    if not np.isnan(x) and not np.isnan(y):
                        if pid not in self.player_trails:
                            self.player_trails[pid] = deque(maxlen=max_trail_length)
                        self.player_trails[pid].append((x, y, alpha))
                        
                        if pid not in trail_data['players']:
                            trail_data['players'][pid] = []
                        trail_data['players'][pid].append((x, y, alpha))
            
            # Balle
            ball_xy = xy_objects[half]["Ball"].xy[idx]
            if not np.isnan(ball_xy[0]):
                trail_data['ball'].append((ball_xy[0], ball_xy[1]))
        
        return trail_data
    
    def draw_past_trajectories(self, trail_data, home_ids):
        """Dessine les trajectoires passées"""
        # Joueurs
        for pid, positions in trail_data['players'].items():
            color_base = "#FF0000" if pid in home_ids else "#0000FF"
            self.draw_player_trail(positions, color_base, pid in home_ids)
        
        # Balle
        self.draw_ball_trail(trail_data['ball'])