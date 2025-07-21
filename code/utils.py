import numpy as np
from config import FPS


def compute_orientations(xy_data, player_ids, every_n_frames=FPS):
    """
    Calcule l'orientation des joueurs toutes les every_n_frames (ex : 12 = toutes les 0.5s à 25fps),
    puis réplique cette orientation sur les frames intermédiaires pour lisser.
    """
    orientations = {pid: [] for pid in player_ids['Home'] + player_ids['Away']}
    for half in ["firstHalf", "secondHalf"]:
        for team in ["Home", "Away"]:
            xy = xy_data[half][team].xy  # shape (frames, n_players*2)
            n_frames = xy.shape[0]
            ids = player_ids[team]
            for j, pid in enumerate(ids):
                traj = xy[:, 2*j:2*j+2]
                angles = np.zeros(n_frames)
                for i in range(0, n_frames, every_n_frames):
                    next_i = min(i + every_n_frames, n_frames-1)
                    dx = traj[next_i, 0] - traj[i, 0]
                    dy = traj[next_i, 1] - traj[i, 1]
                    angle = np.arctan2(dy, dx)
                    # Copie cette orientation pour les frames du bloc
                    angles[i:next_i+1] = angle
                orientations[pid] += list(angles)
    return orientations
