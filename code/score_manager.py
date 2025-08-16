# score_manager.py

"""
Score extraction from events to display running score by frame.
"""

from config import *

class ScoreManager:
    """Compute running score (home/away) at any frame using events.

    Parameters
    ----------
    events : dict
        Floodlight events structure grouped by segment and team.
    home_team_name, away_team_name : str
        Team names used in the event data.
    n_frames_firstHalf : int
        Frames in the first half (for computing second-half offsets).
    fps : int, default config.FPS
        Frames per second for time→frame conversion.
    """
    
    def __init__(self, events, home_team_name, away_team_name, n_frames_firstHalf, fps=FPS):
        self.home_team_name = home_team_name
        self.away_team_name = away_team_name
        self.n_frames_firstHalf = n_frames_firstHalf
        self.fps = fps
        self.goals = []
        
        self._extract_goals(events)
    
    def _extract_goals(self, events):
        """Extract goals from events and store them with computed frame indices."""
        for segment in events:
            # Compute frame offset based on the half
            frame_offset = 0
            if segment.lower() in ["secondhalf", "second_half", "ht2"]:
                frame_offset = self.n_frames_firstHalf
            
            for team_key in events[segment]:  # "Home"/"Away" or actual team name
                df = events[segment][team_key].events
                
                # Detect goals (mirror extract_match_actions_from_events logic)
                for _, row in df.iterrows():
                    eid = row.get('eID', None)
                    eid_str = str(eid) if eid is not None else ""
                    
                    # Check if it's a goal (same logic as in data_processing.py)
                    is_goal = (eid_str == "ShotAtGoal_SuccessfulShot" or 
                              eid_str == "1" or 
                              eid == 1)
                    
                    if is_goal:
                        minute = int(row.get("minute", 0) or 0)
                        second = int(row.get("second", 0) or 0)
                        frame = int((minute * 60 + second) * self.fps) + frame_offset
                        
                        self.goals.append({
                            'frame': frame,
                            'team_key': team_key,
                            'minute': minute,
                            'second': second,
                            'segment': segment,
                            'eid': eid
                        })
        
        # Sort by frame
        self.goals.sort(key=lambda x: x['frame'])
        
    def get_score_at_frame(self, frame):
        """Return (home_score, away_score) at the provided global frame index.

        Parameters
        ----------
        frame : int
            Global frame index.

        Returns
        -------
        tuple[int, int]
            Home and Away scores at or before the given frame.
        """
        home_score = 0
        away_score = 0
        
        for goal in self.goals:
            if goal['frame'] <= frame:
                team_key = goal['team_key']
                
                # Try different matches for team names vs Home/Away keys
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
        """Return all parsed goals (for debugging/inspection).

        Returns
        -------
        list[dict]
            Goal entries with 'frame', 'team_key', and raw fields.
        """
        return self.goals