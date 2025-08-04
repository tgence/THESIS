# frame_utils.py

import numpy as np
from config import FPS


class FrameManager:
    """Gère la conversion et navigation entre frames"""
    
    def __init__(self, n_frames_firstHalf, n_frames_secondHalf, n_frames_total):
        self.n_frames_firstHalf = n_frames_firstHalf
        self.n_frames_secondHalf = n_frames_secondHalf
        self.n_frames_total = n_frames_total
        
    def get_frame_data(self, frame_number):
        """Retourne (half, frame_idx, half_label) pour un frame donné"""
        if frame_number < self.n_frames_firstHalf:
            return "firstHalf", frame_number, "1st Half"
        else:
            return "secondHalf", frame_number - self.n_frames_firstHalf, "2nd Half"
    
    def time_to_frame(self, minutes, seconds, half="firstHalf"):
        """Convertit un temps en frame"""
        total_seconds = minutes * 60 + seconds
        frame = int(total_seconds * FPS)
        
        if half == "secondHalf":
            frame += self.n_frames_firstHalf
            
        return min(frame, self.n_frames_total - 1)
    
    def frame_to_time(self, frame_number):
        """Convertit un frame en temps (minutes, seconds, half)"""
        half, idx, _ = self.get_frame_data(frame_number)
        
        total_seconds = idx / FPS
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        
        return minutes, seconds, half
    
    def get_interval_frames(self, center_frame, interval_seconds):
        """Calcule les frames de début et fin pour un intervalle"""
        interval_frames = int(interval_seconds * FPS)
        start = max(0, center_frame - interval_frames // 2)
        end = min(self.n_frames_total - 1, center_frame + interval_frames // 2)
        return start, end
    
    def jump_to_next_action(self, current_frame, actions, direction=1):
        """Trouve l'action suivante/précédente"""
        actions_sorted = sorted(actions, key=lambda x: x['frame'])
        
        if direction > 0:  # Next
            next_actions = [a for a in actions_sorted if a['frame'] > current_frame]
            return next_actions[0]['frame'] if next_actions else None
        else:  # Previous
            prev_actions = [a for a in actions_sorted if a['frame'] < current_frame]
            return prev_actions[-1]['frame'] if prev_actions else None


class PossessionTracker:
    """Gère la possession du ballon"""
    
    @staticmethod
    def get_possession_for_frame(possession, half, frame_idx):
        """Retourne l'équipe en possession (Home/Away/None)"""
        poss_val = possession[half].code[frame_idx]
        return {1: "Home", 2: "Away"}.get(poss_val, None)
    
    @staticmethod
    def get_possession_stats(possession, half):
        """Calcule les statistiques de possession pour une mi-temps"""
        codes = possession[half].code
        home_frames = np.sum(codes == 1)
        away_frames = np.sum(codes == 2)
        total = len(codes)
        
        return {
            "Home": (home_frames / total * 100) if total > 0 else 0,
            "Away": (away_frames / total * 100) if total > 0 else 0
        }