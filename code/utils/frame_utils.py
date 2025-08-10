"""
Frame and possession utilities.

This module provides helpers to:
- Convert between global frame indices and half-relative indices
- Convert between time (minutes/seconds) and frames
- Compute interval bounds around a given frame
- Navigate to the next/previous action by frame
- Inspect ball possession at a given frame or compute simple possession stats

All time-to-frame conversions use the global FPS configured in `config.FPS`.
"""
# frame_utils.py

import numpy as np
from config import FPS


class FrameManager:
    """Manage conversions and navigation between frames.

    Responsibilities:
    - Map a global frame index to (half, index-within-half, label)
    - Convert time (minutes/seconds) to global frame index and vice versa
    - Provide common helpers for interval computations and action navigation

    The instance is initialized with the frame counts per half and the total
    number of frames in the loaded match.
    """
    
    def __init__(self, n_frames_firstHalf, n_frames_secondHalf, n_frames_total):
        self.n_frames_firstHalf = n_frames_firstHalf
        self.n_frames_secondHalf = n_frames_secondHalf
        self.n_frames_total = n_frames_total
        
    def get_frame_data(self, frame_number):
        """Return (half, frame_idx, half_label) for a given global frame.

        Parameters
        - frame_number: int
            Global frame index in [0, n_frames_total).

        Returns
        - tuple[str, int, str]
            Half key ("firstHalf"/"secondHalf"), index within that half, and a
            short human label ("1st Half"/"2nd Half").
        """
        if frame_number < self.n_frames_firstHalf:
            return "firstHalf", frame_number, "1st Half"
        else:
            return "secondHalf", frame_number - self.n_frames_firstHalf, "2nd Half"
    
    def time_to_frame(self, minutes, seconds, half="firstHalf"):
        """Convert a time to a global frame index.

        Parameters
        - minutes: int
        - seconds: int
        - half: str
            Either "firstHalf" or "secondHalf".

        Returns
        - int: Global frame index clamped to [0, n_frames_total-1].
        """
        total_seconds = minutes * 60 + seconds
        frame = int(total_seconds * FPS)
        
        if half == "secondHalf":
            frame += self.n_frames_firstHalf
            
        return min(frame, self.n_frames_total - 1)
    
    def frame_to_time(self, frame_number):
        """Convert a global frame index to (minutes, seconds, half).

        Returns
        - tuple[int, int, str]: (minutes, seconds, half)
        """
        half, idx, _ = self.get_frame_data(frame_number)
        
        total_seconds = idx / FPS
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        
        return minutes, seconds, half
    
    def get_interval_frames(self, center_frame, interval_seconds):
        """Compute [start, end] global frame bounds for a time interval.

        The interval is centered on `center_frame` and spans `interval_seconds`.

        Returns
        - tuple[int, int]: (start_frame, end_frame)
        """
        interval_frames = int(interval_seconds * FPS)
        start = max(0, center_frame - interval_frames // 2)
        end = min(self.n_frames_total - 1, center_frame + interval_frames // 2)
        return start, end
    
    def jump_to_next_action(self, current_frame, actions, direction=1):
        """Find the next/previous action relative to the current frame.

        Parameters
        - current_frame: int
        - actions: list[dict]
            List of actions, each with a 'frame' field.
        - direction: int
            +1 for next action, -1 for previous action.

        Returns
        - int | None: The target action frame or None if not found.
        """
        actions_sorted = sorted(actions, key=lambda x: x['frame'])
        
        if direction > 0:  # Next
            next_actions = [a for a in actions_sorted if a['frame'] > current_frame]
            return next_actions[0]['frame'] if next_actions else None
        else:  # Previous
            prev_actions = [a for a in actions_sorted if a['frame'] < current_frame]
            return prev_actions[-1]['frame'] if prev_actions else None


class PossessionTracker:
    """Helpers to read ball possession data.

    Exposes static methods to query per-frame possession and compute basic
    possession percentages for a given half.
    """
    
    @staticmethod
    def get_possession_for_frame(possession, half, frame_idx):
        """Return possession team at a given frame.

        Parameters
        - possession: dict
            Floodlight-like dict with keys per half and `.code` arrays
            containing 0 (no one), 1 (Home), 2 (Away).
        - half: str
        - frame_idx: int

        Returns
        - str | None: "Home", "Away", or None if no possession.
        """
        poss_val = possession[half].code[frame_idx]
        return {1: "Home", 2: "Away"}.get(poss_val, None)
    
    @staticmethod
    def get_possession_stats(possession, half):
        """Compute simple possession percentages for the given half.

        Returns
        - dict[str, float]: {"Home": pct, "Away": pct}
        """
        codes = possession[half].code
        home_frames = np.sum(codes == 1)
        away_frames = np.sum(codes == 2)
        total = len(codes)
        
        return {
            "Home": (home_frames / total * 100) if total > 0 else 0,
            "Away": (away_frames / total * 100) if total > 0 else 0
        }