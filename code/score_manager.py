# score_manager.py

from config import *

class ScoreManager:
    """Gère le calcul et l'affichage du score en temps réel"""
    
    def __init__(self, events, home_team_name, away_team_name, n_frames_firstHalf, fps=FPS):
        self.home_team_name = home_team_name
        self.away_team_name = away_team_name
        self.n_frames_firstHalf = n_frames_firstHalf
        self.fps = fps
        self.goals = []
        
        self._extract_goals(events)
    
    def _extract_goals(self, events):
        """Extrait tous les goals avec leur frame et équipe depuis les événements"""
        for segment in events:
            # Calcul de l'offset selon la mi-temps
            frame_offset = 0
            if segment.lower() in ["secondhalf", "second_half", "ht2"]:
                frame_offset = self.n_frames_firstHalf
            
            for team_key in events[segment]:  # team_key peut être "Home" ou "Away" ou nom d'équipe
                df = events[segment][team_key].events
                
                # Filtrer les goals - utilise la même logique que extract_match_actions_from_events
                for _, row in df.iterrows():
                    eid = row.get('eID', None)
                    eid_str = str(eid) if eid is not None else ""
                    
                    # Vérifier si c'est un goal (même logique que data_processing.py)
                    is_goal = (eid_str == "ShotAtGoal_SuccessfulShot" or 
                              eid_str == "1" or 
                              eid == 1)
                    
                    if is_goal:
                        minute = int(row.get("minute", 0) or 0)
                        second = int(row.get("second", 0) or 0)
                        frame = int((minute * 60 + second) * self.fps) + frame_offset
                        
                        self.goals.append({
                            'frame': frame,
                            'team_key': team_key,  # "Home" ou "Away" ou nom d'équipe
                            'minute': minute,
                            'second': second,
                            'segment': segment,
                            'eid': eid
                        })
        
        # Trier par frame
        self.goals.sort(key=lambda x: x['frame'])
        
    def get_score_at_frame(self, frame):
        """Retourne le score (home, away) à une frame donnée"""
        home_score = 0
        away_score = 0
        
        for goal in self.goals:
            if goal['frame'] <= frame:
                team_key = goal['team_key']
                
                # Essayer différentes correspondances
                is_home_goal = (
                    team_key == "Home" or 
                    team_key == self.home_team_name
                )
                
                is_away_goal = (
                    team_key == "Away" or 
                    team_key == self.away_team_name
                )
                
                if is_home_goal:
                    home_score += 1
                elif is_away_goal:
                    away_score += 1
        
        return home_score, away_score
    
    def get_all_goals(self):
        """Retourne tous les goals pour debugging"""
        return self.goals