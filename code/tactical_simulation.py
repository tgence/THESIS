# tactical_simulation.py

import numpy as np
import math
from PyQt5.QtCore import QPointF
from config import *

class TacticalSimulationManager:
    """Gère la simulation tactique basée sur les flèches dessinées"""
    
    def __init__(self, annotation_manager, pitch_widget, home_ids, away_ids, home_colors, away_colors):
        self.annotation_manager = annotation_manager
        self.pitch_widget = pitch_widget
        self.home_ids = home_ids
        self.away_ids = away_ids
        self.home_colors = home_colors
        self.away_colors = away_colors
        
        # Données tactiques
        self.tactical_arrows = []  # Flèches avec joueurs associés
        self.ball_possession_chain = []  # Chaîne de passes
        self.player_associations = {}  # {arrow_id: player_id}
        self.pass_receivers = {}  # {arrow_id: receiver_player_id} pour les passes
        
        # Trajectoires simulées
        self.simulated_player_positions = {}  # {player_id: [(x, y, frame), ...]}
        self.simulated_ball_positions = []  # [(x, y, frame), ...]
        
    def associate_arrow_with_player(self, arrow, player_id, current_frame, xy_objects):
        """Associe une flèche à un joueur (appelé manuellement)"""
        arrow_id = id(arrow)
        self.player_associations[arrow_id] = player_id
        
        # Créer l'objet tactical_arrow
        tactical_arrow = {
            'arrow': arrow,
            'arrow_id': arrow_id,
            'player_id': player_id,
            'action_type': self.get_action_type(arrow),
            'start_pos': arrow.arrow_points[0],
            'end_pos': arrow.arrow_points[-1],
            'length': self.calculate_arrow_length(arrow.arrow_points),
            'associated_frame': current_frame
        }
        
        self.tactical_arrows.append(tactical_arrow)
        
        # Si c'est une passe (solid), demander le receveur
        if tactical_arrow['action_type'] == 'pass':
            return "waiting_for_receiver"
        
        return "associated"
    
    def set_pass_receiver(self, receiver_player_id):
        """Définit le receveur d'une passe"""
        # Trouver la dernière passe sans receveur
        for tactical_arrow in reversed(self.tactical_arrows):
            if (tactical_arrow['action_type'] == 'pass' and 
                'receiver_id' not in tactical_arrow):
                
                arrow_id = tactical_arrow['arrow_id']
                self.pass_receivers[arrow_id] = receiver_player_id
                tactical_arrow['receiver_id'] = receiver_player_id
                
                # Ajouter à la chaîne de possession
                self.ball_possession_chain.append({
                    'from_player': tactical_arrow['player_id'],
                    'to_player': receiver_player_id,
                    'arrow_id': arrow_id
                })
                
                return True
        return False
    
    def get_action_type(self, arrow):
        """Détermine le type d'action selon le style de flèche"""
        if hasattr(arrow, 'arrow_style'):
            style = arrow.arrow_style
            if style == "dotted":
                return 'run'  # Pointillés = course
            elif style == "zigzag":
                return 'dribble'  # Zigzag = dribble
            else:
                return 'pass'  # Solid = passe
        
        # Fallback: analyser les items graphiques
        if hasattr(arrow, 'childItems') and arrow.childItems():
            for item in arrow.childItems():
                if hasattr(item, 'pen'):
                    pen = item.pen()
                    if pen.style() == Qt.DashLine:
                        return 'run'
                    break
        
        # Par défaut, solid = passe
        return 'pass'
    
    def calculate_arrow_length(self, points):
        """Calcule la longueur totale d'une flèche"""
        if len(points) < 2:
            return 0
        
        total_length = 0
        for i in range(len(points) - 1):
            dx = points[i+1].x() - points[i].x()
            dy = points[i+1].y() - points[i].y()
            total_length += math.sqrt(dx*dx + dy*dy)
        
        return total_length
    
    def calculate_simulated_trajectories(self, interval_seconds, current_frame, xy_objects, n_frames, get_frame_data_func):
        """Calcule les nouvelles positions selon les flèches tactiques"""
        self.simulated_player_positions.clear()
        self.simulated_ball_positions.clear()
        
        if not self.tactical_arrows:
            return
        
        total_frames = int(interval_seconds * FPS)
        ball_current_pos = None
        ball_holder = None
        
        # Obtenir la position initiale de la balle
        half, idx, _ = get_frame_data_func(current_frame)
        try:
            ball_xy = xy_objects[half]["Ball"].xy[idx]
            if len(ball_xy) >= 2 and not np.isnan(ball_xy[0]):
                ball_current_pos = QPointF(ball_xy[0], ball_xy[1])
                # Déterminer qui a le ballon initialement
                ball_holder = self._find_closest_player_to_ball(ball_current_pos, current_frame, xy_objects, get_frame_data_func)
        except (IndexError, KeyError):
            pass
        
        # Trier les actions par ordre et par timing
        passes = [ta for ta in self.tactical_arrows if ta['action_type'] == 'pass']
        other_actions = [ta for ta in self.tactical_arrows if ta['action_type'] in ['run', 'dribble']]
        
        # Calculer les trajectoires pour chaque frame
        for frame_offset in range(total_frames):
            current_sim_frame = current_frame + frame_offset
            progress = frame_offset / max(1, total_frames - 1)
            
            # Traiter les actions des joueurs selon la vitesse calculée
            for tactical_arrow in self.tactical_arrows:
                player_id = tactical_arrow['player_id']
                action_type = tactical_arrow['action_type']
                
                # Calculer la position du joueur selon sa flèche et la vitesse requise
                player_pos = self._calculate_player_position_with_speed(
                    tactical_arrow, progress, interval_seconds, current_frame, xy_objects, get_frame_data_func
                )
                
                if player_id not in self.simulated_player_positions:
                    self.simulated_player_positions[player_id] = []
                
                self.simulated_player_positions[player_id].append((
                    player_pos.x(), player_pos.y(), current_sim_frame
                ))
            
            # Calculer la position de la balle avec vitesse de passe
            if ball_current_pos and ball_holder:
                ball_pos = self._calculate_ball_position_with_speed(
                    ball_current_pos, ball_holder, passes, progress, interval_seconds, 
                    current_frame, xy_objects, get_frame_data_func
                )
                self.simulated_ball_positions.append((
                    ball_pos.x(), ball_pos.y(), current_sim_frame
                ))
    
    def _calculate_player_position_with_speed(self, tactical_arrow, progress, interval_seconds, current_frame, xy_objects, get_frame_data_func):
        """Calcule la position d'un joueur en tenant compte de la vitesse requise"""
        start_pos = tactical_arrow['start_pos']
        end_pos = tactical_arrow['end_pos']
        arrow_length = tactical_arrow['length']
        
        # Calculer la vitesse requise (mètres par seconde)
        required_speed = arrow_length / interval_seconds
        
        # Vitesse maximale réaliste selon le type d'action
        max_speeds = {
            'run': 8.0,      # 8 m/s course rapide
            'dribble': 4.0,  # 4 m/s dribble
            'pass': 0.0      # Les passes n'ont pas de limite de vitesse joueur
        }
        
        action_type = tactical_arrow['action_type']
        
        if action_type in max_speeds and max_speeds[action_type] > 0:
            # Limiter la vitesse si nécessaire
            max_allowed_speed = max_speeds[action_type]
            if required_speed > max_allowed_speed:
                # Le joueur n'atteint pas la fin dans le temps imparti
                # Il parcourt la distance qu'il peut à vitesse max
                distance_covered = max_allowed_speed * interval_seconds * progress
                total_distance = arrow_length
                actual_progress = min(distance_covered / total_distance, 1.0)
            else:
                actual_progress = progress
        else:
            # Pour les passes, utiliser le progress normal
            actual_progress = progress
        
        # Interpolation le long de la flèche
        x = start_pos.x() + actual_progress * (end_pos.x() - start_pos.x())
        y = start_pos.y() + actual_progress * (end_pos.y() - start_pos.y())
        
        return QPointF(x, y)
    
    def _calculate_ball_position_with_speed(self, initial_ball_pos, initial_holder, passes, progress, interval_seconds, current_frame, xy_objects, get_frame_data_func):
        """Calcule la position de la balle avec vitesse de passe réaliste"""
        if not passes:
            # Pas de passe, la balle suit le porteur initial
            if initial_holder in self.simulated_player_positions:
                positions = self.simulated_player_positions[initial_holder]
                if positions:
                    latest_pos = positions[-1]
                    return QPointF(latest_pos[0], latest_pos[1])
            return initial_ball_pos
        
        # Traiter les passes en séquence selon leur timing
        current_pass = None
        pass_start_time = 0.0
        
        # Pour simplicité, traiter la première passe
        # TODO: Implémenter la logique séquentielle pour multiples passes
        first_pass = passes[0]
        
        if 'receiver_id' in first_pass:
            pass_length = first_pass['length']
            
            # Vitesse de passe réaliste (15-25 m/s pour une passe normale)
            pass_speed = min(25.0, max(15.0, pass_length / 2.0))  # Adaptée à la distance
            pass_duration = pass_length / pass_speed
            
            # Convertir en proportion du temps total
            pass_duration_ratio = min(pass_duration / interval_seconds, 0.8)  # Max 80% du temps
            
            if progress <= pass_duration_ratio:
                # Passe en cours - interpoler entre passeur et receveur
                pass_progress = progress / pass_duration_ratio
                
                # Position du passeur
                passer_pos = self._calculate_player_position_with_speed(
                    first_pass, progress, interval_seconds, current_frame, xy_objects, get_frame_data_func
                )
                
                # Position du receveur
                receiver_pos = self._get_player_position_at_progress(
                    first_pass['receiver_id'], progress, interval_seconds, current_frame, xy_objects, get_frame_data_func
                )
                
                # Interpoler la balle avec une trajectoire légèrement courbe
                x = passer_pos.x() + pass_progress * (receiver_pos.x() - passer_pos.x())
                y = passer_pos.y() + pass_progress * (receiver_pos.y() - passer_pos.y())
                
                return QPointF(x, y)
            else:
                # Passe terminée - la balle suit le receveur
                receiver_pos = self._get_player_position_at_progress(
                    first_pass['receiver_id'], progress, interval_seconds, current_frame, xy_objects, get_frame_data_func
                )
                return receiver_pos
        
        return initial_ball_pos
    
    def _get_player_position_at_progress(self, player_id, progress, interval_seconds, current_frame, xy_objects, get_frame_data_func):
        """Obtient la position d'un joueur (simulée ou réelle) à un moment donné"""
        # D'abord vérifier s'il y a une position simulée
        if player_id in self.simulated_player_positions:
            positions = self.simulated_player_positions[player_id]
            if positions:
                # Prendre la position correspondant au progress
                target_index = int(progress * (len(positions) - 1))
                target_index = min(target_index, len(positions) - 1)
                latest_pos = positions[target_index]
                return QPointF(latest_pos[0], latest_pos[1])
        
        # Sinon, utiliser la position réelle
        frame_to_check = current_frame + int(progress * interval_seconds * FPS)
        return self._get_real_player_position(player_id, frame_to_check, xy_objects, get_frame_data_func)
    
    def _get_real_player_position(self, player_id, frame, xy_objects, get_frame_data_func):
        """Obtient la position réelle d'un joueur à une frame donnée"""
        half, idx, _ = get_frame_data_func(frame)
        
        # Déterminer l'équipe du joueur
        side = "Home" if player_id in self.home_ids else "Away"
        ids = self.home_ids if side == "Home" else self.away_ids
        
        try:
            player_index = ids.index(player_id)
            xy = xy_objects[half][side].xy[idx]
            
            if 2*player_index+1 < len(xy):
                x, y = xy[2*player_index], xy[2*player_index+1]
                if not np.isnan(x) and not np.isnan(y):
                    return QPointF(x, y)
        except (ValueError, IndexError, KeyError):
            pass
        
        return QPointF(0, 0)  # Position par défaut
    
    def _find_closest_player_to_ball(self, ball_pos, frame, xy_objects, get_frame_data_func):
        """Trouve le joueur le plus proche de la balle"""
        min_distance = float('inf')
        closest_player = None
        
        for side, ids in [("Home", self.home_ids), ("Away", self.away_ids)]:
            for player_id in ids:
                player_pos = self._get_real_player_position(player_id, frame, xy_objects, get_frame_data_func)
                distance = math.sqrt(
                    (ball_pos.x() - player_pos.x())**2 + 
                    (ball_pos.y() - player_pos.y())**2
                )
                
                if distance < min_distance:
                    min_distance = distance
                    closest_player = player_id
        
        return closest_player
    
    def find_player_at_position(self, click_pos, current_frame, xy_objects, get_frame_data_func, max_distance=PLAYER_OUTER_RADIUS_BASE):
        """Trouve le joueur le plus proche d'une position de clic"""
        min_distance = float('inf')
        closest_player = None
        
        for side, ids in [("Home", self.home_ids), ("Away", self.away_ids)]:
            for player_id in ids:
                player_pos = self._get_real_player_position(player_id, current_frame, xy_objects, get_frame_data_func)
                distance = math.sqrt(
                    (click_pos.x() - player_pos.x())**2 + 
                    (click_pos.y() - player_pos.y())**2
                )
                
                if distance < min_distance and distance <= max_distance:
                    min_distance = distance
                    closest_player = player_id
        
        return closest_player
    
    def clear_tactical_data(self):
        """Efface toutes les données tactiques"""
        self.tactical_arrows.clear()
        self.ball_possession_chain.clear()
        self.player_associations.clear()
        self.pass_receivers.clear()
        self.simulated_player_positions.clear()
        self.simulated_ball_positions.clear()
    
    def get_simulated_trajectories(self):
        """Retourne les trajectoires simulées pour l'affichage"""
        return {
            'players': self.simulated_player_positions,
            'ball': self.simulated_ball_positions
        }
    
    def get_non_associated_arrows(self):
        """Retourne les flèches qui ne sont pas associées à des joueurs"""
        associated_arrow_ids = {ta['arrow_id'] for ta in self.tactical_arrows}
        all_arrows = self.annotation_manager.arrows
        
        non_associated = []
        for arrow in all_arrows:
            if id(arrow) not in associated_arrow_ids:
                non_associated.append(arrow)
        
        return non_associated
    
    def get_associated_arrows(self):
        """Retourne les flèches associées avec leurs informations tactiques"""
        return self.tactical_arrows.copy()
    
    def remove_arrow_association(self, arrow):
        """Supprime l'association d'une flèche avec un joueur"""
        arrow_id = id(arrow)
        
        # Supprimer de tactical_arrows
        self.tactical_arrows = [ta for ta in self.tactical_arrows if ta['arrow_id'] != arrow_id]
        
        # Supprimer des associations
        if arrow_id in self.player_associations:
            del self.player_associations[arrow_id]
        
        # Supprimer des receveurs de passe
        if arrow_id in self.pass_receivers:
            del self.pass_receivers[arrow_id]
        
        # Supprimer de la chaîne de possession
        self.ball_possession_chain = [
            link for link in self.ball_possession_chain 
            if link['arrow_id'] != arrow_id
        ]