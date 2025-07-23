# utils.py

import numpy as np
from config import *
import math
from scipy.signal import savgol_filter


def compute_orientations(xy_data, player_ids, window_length=100, polyorder=2):
    """
    Calcule et lisse l'orientation des joueurs, frame par frame.
    Renvoie: dict[pid][frame_idx] = angle (float, en radians)
    """
    orientations = {pid: [] for pid in player_ids['Home'] + player_ids['Away']}
    for half in ["firstHalf", "secondHalf"]:
        for team in ["Home", "Away"]:
            xy = xy_data[half][team].xy  # shape (frames, n_players*2)
            n_frames = xy.shape[0]
            ids = player_ids[team]
            for j, pid in enumerate(ids):
                traj = xy[:, 2*j:2*j+2]
                # calcul brut frame à frame (nan-safe)
                dx = np.diff(traj[:, 0], prepend=traj[0,0])
                dy = np.diff(traj[:, 1], prepend=traj[0,1])
                angles = np.arctan2(dy, dx)
                # conversion périodique pour lissage
                cos_a = np.cos(angles)
                sin_a = np.sin(angles)
                # si trop court, skip smoothing
                if len(cos_a) < window_length:
                    angles_smooth = angles
                else:
                    cos_a = savgol_filter(cos_a, window_length, polyorder, mode='nearest')
                    sin_a = savgol_filter(sin_a, window_length, polyorder, mode='nearest')
                    angles_smooth = np.arctan2(sin_a, cos_a)
                orientations[pid] += list(angles_smooth)
    return orientations

def compute_velocities(xy_data, player_ids, window_length=100, polyorder=2):
    """
    Calcule et lisse la vitesse des joueurs, frame par frame.
    Renvoie: dict[pid][frame_idx] = vitesse (float, en m/s)
    """
    velocities = {pid: [] for pid in player_ids['Home'] + player_ids['Away']}
    for half in ["firstHalf", "secondHalf"]:
        for team in ["Home", "Away"]:
            xy = xy_data[half][team].xy  # shape (frames, n_players*2)
            n_frames = xy.shape[0]
            ids = player_ids[team]
            for j, pid in enumerate(ids):
                traj = xy[:, 2*j:2*j+2]
                dx = np.diff(traj[:, 0], prepend=traj[0,0])
                dy = np.diff(traj[:, 1], prepend=traj[0,1])
                dt = 1.0 / FPS
                vels = np.hypot(dx, dy) / dt
                # lissage Savitzky-Golay
                if len(vels) < window_length:
                    vels_smooth = vels
                else:
                    vels_smooth = savgol_filter(vels, window_length, polyorder, mode='nearest')
                velocities[pid] += list(vels_smooth)
    return velocities
