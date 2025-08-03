# data_processing.py
 
import os
import pandas as pd
import numpy as np
from scipy.special import expit  
import ast
import xml.etree.ElementTree as ET
from floodlight.io.dfl import read_position_data_xml, read_event_data_xml
from scipy.signal import savgol_filter
from config import *
from PyQt5.QtGui import QColor

def safe_color(val, fallback='#aaaaaa'):
    if isinstance(val, str) and (val.startswith('#') or len(val)==6):
        return val if val.startswith('#') else '#'+val
    return fallback

def get_player_color_dict(df):
    d = {}
    for _, r in df.iterrows():
        pid = r['PersonId']
        main = safe_color(r.shirtMainColor)
        sec = safe_color(r.shirtSecondaryColor, fallback=main)
        numc = safe_color(r.shirtNumberColor)
        d[pid] = (main, sec, numc)
    return d




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


def extract_dsam_from_xml(file_pos, player_ids, teamid_map, n_frames_per_half):
    """
    Extrait D, S, A, M pour chaque joueur et chaque période (firstHalf, secondHalf...).
    Pour chaque joueur et chaque période :
      - Si pas de données : [nan]*n_frames
      - Si données incomplètes : nan là où il n'y a pas de data
    Args :
        file_pos: chemin du xml
        player_ids: {'Home': [...], 'Away': [...]}
        teamid_map: {'Home': '...', 'Away': '...'}
        n_frames_per_half: dict {'firstHalf': N1, 'secondHalf': N2, ...}
    """
    import xml.etree.ElementTree as ET
    tree_pos = ET.parse(file_pos)
    root_pos = tree_pos.getroot()
    dsam = {'Home': {}, 'Away': {}}

    # Initialisation de toutes les entrées à des nan
    for side in ['Home', 'Away']:
        for pid in player_ids[side]:
            dsam[side][pid] = {}
            for segment, n_frames in n_frames_per_half.items():
                dsam[side][pid][segment] = {k: [np.nan]*n_frames for k in ['D', 'S', 'A', 'M']}

    # Parcours du XML
    for frameset in root_pos.findall('.//FrameSet'):
        team_id = frameset.get('TeamId')
        person_id = frameset.get('PersonId')
        segment = frameset.get('GameSection', 'unknown')
        # Trouver le side (Home/Away)
        side = None
        for k, tid in teamid_map.items():
            if team_id == tid:
                side = k
                break
        if side is None or person_id not in player_ids[side]:
            continue
        frames = frameset.findall('Frame')
        n_frames = len(frames)
        for idx, fr in enumerate(frames):
            try:
                dsam[side][person_id][segment]['D'][idx] = float(fr.get('D', 'nan'))
            except Exception:
                dsam[side][person_id][segment]['D'][idx] = np.nan
            try:
                s_kmh = float(fr.get('S', 'nan'))
                dsam[side][person_id][segment]['S'][idx] = s_kmh / 3.6
            except Exception:
                dsam[side][person_id][segment]['S'][idx] = np.nan
            try:
                dsam[side][person_id][segment]['A'][idx] = float(fr.get('A', 'nan'))
            except Exception:
                dsam[side][person_id][segment]['A'][idx] = np.nan
            try:
                dsam[side][person_id][segment]['M'][idx] = float(fr.get('M', 'nan'))
            except Exception:
                dsam[side][person_id][segment]['M'][idx] = np.nan

    return dsam


def build_player_out_frames(events_objects, fps, n_frames_firstHalf):
    """
    Retourne un dict {player_id: sortie_frame} pour Substitution Out (eID==19) ou Red Card (eID==6).
    On travaille DIRECTEMENT avec events_objects[segment][team].events (DataFrame).
    """
    out_player_frames = {}
    for segment, team_dict in events_objects.items():
        # Calcule offset de frame selon la mi-temps
        offset = 0
        if segment.lower() in ["ht2", "secondhalf", "second_half", "second"]:
            offset = n_frames_firstHalf

        for team, events_obj in team_dict.items():
            df = events_obj.events
            # Substitution OUT = eID==19, Red Card = eID==6
            mask = (df["eID"] == 19) | (df["eID"] == 6)
            for _, row in df[mask].iterrows():
                pid = str(row["pID"])
                minute = row["minute"]
                second = row["second"]
                frame = int((minute * 60 + second) * fps) + offset
                # On garde la 1ère sortie par joueur (minimum)
                if pid not in out_player_frames or frame < out_player_frames[pid]:
                    out_player_frames[pid] = frame
    return out_player_frames

def extract_match_actions_from_events(events, FPS=25, n_frames_firstHalf=0):
    """
    Extrait les actions importantes avec le bon calcul de frame selon la mi-temps
    """
    ACTIONS = []
    
    for segment in events:
        # Calcul de l'offset selon la mi-temps
        frame_offset = 0
        if segment.lower() in ["secondhalf", "second_half", "ht2"]:
            frame_offset = n_frames_firstHalf
            
        for team in events[segment]:
            df = events[segment][team].events
            
            for _, row in df.iterrows():
                eid = row.get('eID', None)
                eid_str = str(eid) if eid is not None else ""
                minute = int(row.get("minute", 0) or 0)
                second = int(row.get("second", 0) or 0)
                
                # Frame avec offset selon la mi-temps
                frame = int((minute * 60 + second) * FPS) + frame_offset
                
                qualifier = row.get('qualifier', '')
                
                # Mapping des événements
                action_map = {
                    "ShotAtGoal_SuccessfulShot": {"label": "GOAL", "emoji": "⚽"},
                    "GoalKick_Play_Pass": {"label": "Goal Kick", "emoji": "🦶"},
                    "FreeKick_Play_Cross": {"label": "Free Kick", "emoji": "🎯"},
                    "FreeKick_Play_Pass": {"label": "Free Kick", "emoji": "🎯"},
                    "FreeKick_ShotAtGoal_BlockedShot": {"label": "Free Kick", "emoji": "🎯"},
                    "CornerKick_Play_Cross": {"label": "Corner", "emoji": "🚩"},
                    "Penalty_Play_Pass": {"label": "Penalty", "emoji": "⚪"},
                    "Penalty_ShotAtGoal_BlockedShot": {"label": "Penalty", "emoji": "⚪"},
                    "Penalty_ShotAtGoal_SuccessfulShot": {"label": "Penalty", "emoji": "⚪"},
                    "Offside": {"label": "Offside", "emoji": "❌"},
                    "OutSubstitution": {"label": "Substitution", "emoji": "🔄"},
                }
                # je veux verif s il y a pas deja la meme action au meme temps etc il faut faire une comparaison complete
                if eid_str in action_map and not any(str(a['eID']) == eid_str and a['frame'] == frame for a in ACTIONS):
                    action = action_map[eid_str].copy()
                    action.update({
                        "frame": frame,
                        "segment": segment,
                        "team": team,
                        "minute": minute,
                        "second": second,
                        "eID": eid,
                        "display_time": format_display_time(minute, second, segment)
                    })
                    ACTIONS.append(action)
                
                # Cartons (logique spéciale)
                elif eid_str in ["Caution", "6"]:
                    is_red = False
                    qual = None
                    if isinstance(qualifier, dict):
                        qual = qualifier
                    elif isinstance(qualifier, str):
                        try:
                            qual = ast.literal_eval(qualifier)
                        except:
                            qual = {"cardcolor": qualifier}
                    
                    if isinstance(qual, dict):
                        for key in ['cardcolor', 'CardColor', 'CardRating']:
                            cardcolor = str(qual.get(key, '')).lower()
                            if cardcolor:
                                break
                    
                    if 'red' in cardcolor or 'red' in str(qualifier).lower():
                        is_red = True
                    
                    action = {
                        "frame": frame,
                        "segment": segment,
                        "team": team,
                        "minute": minute,
                        "second": second,
                        "eID": eid,
                        "label": "Red Card" if is_red else "Yellow Card",
                        "emoji": "🟥" if is_red else "🟨",
                        "display_time": format_display_time(minute, second, segment)
                    }
                    ACTIONS.append(action)
    
    # Tri par frame
    ACTIONS = sorted(ACTIONS, key=lambda x: x["frame"])
    return ACTIONS

def format_display_time(minute, second, segment):
    """
    Formate le temps d'affichage selon la mi-temps avec gestion du temps additionnel
    """
    # Temps de base selon la mi-temps
    if segment.lower() in ["firsthalf", "first_half", "ht1"]:
        base_minutes = 0
        half_duration = 45
    elif segment.lower() in ["secondhalf", "second_half", "ht2"]:
        base_minutes = 45
        half_duration = 45
    else:
        # Prolongations ou autres
        base_minutes = 90
        half_duration = 15
    
    total_minutes = base_minutes + minute
    
    # Si on dépasse la durée normale de la mi-temps
    if minute >= half_duration:
        extra_time_minutes = minute - half_duration
        return f"{base_minutes + half_duration}:00+{int(extra_time_minutes):02d}:{int(second):02d}"
    else:
        return f"{total_minutes:02d}:{second:02d}"
    


def load_data(path, file_pos, file_info, file_events):

    # 1. Extraction floodlight (positions, etc.)
    xy, possession, ballstatus, teamsheets, pitch = read_position_data_xml(
        os.path.join(path, file_pos),
        os.path.join(path, file_info)
    )
    # 2. Events
    events, _, _ = read_event_data_xml(
        os.path.join(path, file_events),
        os.path.join(path, file_info)
    )

    # 3. Teams/players info
    tree = ET.parse(os.path.join(path, file_info))
    root = tree.getroot()
    general = root.find('.//General')
    home_name, away_name = general.get('HomeTeamName'), general.get('GuestTeamName')
    rows = []
    for team in root.findall('.//Team'):
        team_name = team.get('TeamName')
        tid = team.get('TeamId')
        main, sec, numc = team.get('PlayerShirtMainColor'), team.get('PlayerShirtSecondaryColor'), team.get('PlayerShirtNumberColor')
        side = 'Home' if team_name == home_name else 'Away' if team_name == away_name else 'Unknown'
        for p in team.findall('.//Player'):
            d = p.attrib.copy()
            d.update(team=team_name, side=side, shirtMainColor=main, shirtSecondaryColor=sec, shirtNumberColor=numc, TeamId=tid)
            rows.append(d)
    teams_df = pd.DataFrame(rows)
    # 4. Filter joueurs + mapping IDs
    home_df = teams_df[teams_df.team==home_name]
    away_df = teams_df[teams_df.team==away_name]
    home_ids = home_df.PersonId.tolist()
    away_ids = away_df.PersonId.tolist()
    player_ids = {'Home': home_ids, 'Away': away_ids}
    # Ajout TeamId pour chaque équipe
    teamid_map = {
        'Home': home_df.iloc[0]['TeamId'] if not home_df.empty else None,
        'Away': away_df.iloc[0]['TeamId'] if not away_df.empty else None
    }
    # 5. Extraction D (distance)/S (speed)/A (acceleration)/M (minute) and number of frames per half + total
    n1 = xy['firstHalf']['Home'].xy.shape[0]
    n2 = xy['secondHalf']['Home'].xy.shape[0]
    ntot = n1 + n2
    n_frames_per_half = {'firstHalf': n1, 'secondHalf': n2}
    dsam = extract_dsam_from_xml(
        os.path.join(path, file_pos), player_ids, teamid_map, n_frames_per_half
    )
    # 6. Autres traitements
    orientations = compute_orientations(xy, player_ids)
    home_colors = get_player_color_dict(home_df)
    away_colors = get_player_color_dict(away_df)
    id2num = dict(zip(teams_df.PersonId, teams_df['ShirtNumber']))

    # 7. Ball carrier
    ball_carrier_array = build_ball_carrier_array(home_ids, away_ids, ntot, possession, xy)
    return {
        'xy_objects': xy, 'possession': possession, 'ballstatus': ballstatus,
        'events': events, 'pitch_info': pitch,
        'teams_df': teams_df, 'home_name': home_name, 'away_name': away_name,
        'home_ids': home_ids, 'away_ids': away_ids,
        'player_ids': player_ids, 'orientations': orientations, 'dsam': dsam, 'ball_carrier_array': ball_carrier_array,
        'home_colors': home_colors, 'away_colors': away_colors,
        'id2num': id2num,
        'n1': n1, 'n2': n2, 'ntot': ntot
    }



   
def format_match_time(
    frame_idx,
    n_frames_firstHalf,
    n_frames_secondHalf,
    n_frames_overtime_firstHalf=None,
    n_frames_overtime_secondHalf=None,
    fps=FPS
):
    periods = [
        ("FirstHalf", 0, n_frames_firstHalf, 0, LENGTH_FIRST_HALF),
        ("SecondHalf", n_frames_firstHalf, n_frames_firstHalf + n_frames_secondHalf, LENGTH_FIRST_HALF, LENGTH_FULL_TIME),
    ]
    # Ajout des prolongations si elles existent
    curr_start = n_frames_firstHalf + n_frames_secondHalf
    min_start = LENGTH_FULL_TIME
    if n_frames_overtime_firstHalf:
        periods.append(("OvertimeFirstHalf", curr_start, curr_start + n_frames_overtime_firstHalf, min_start, min_start + LENGTH_OVERTIME_HALF))
        curr_start += n_frames_overtime_firstHalf
        min_start += LENGTH_OVERTIME_HALF
    if n_frames_overtime_secondHalf:
        periods.append(("OvertimeSecondHalf", curr_start, curr_start + n_frames_overtime_secondHalf, min_start, min_start + LENGTH_OVERTIME_HALF))
        curr_start += n_frames_overtime_secondHalf
        min_start += LENGTH_OVERTIME_HALF

    # Trouve la période du frame
    for label, start_f, end_f, min_start, min_end in periods:
        if start_f <= frame_idx < end_f:
            rel_frame = frame_idx - start_f
            tot_sec = rel_frame / fps
            min_ = int(tot_sec // 60) + min_start
            sec_ = int(tot_sec % 60)
            if min_ < min_end:
                return f"{min_:02d}:{sec_:02d}"
            else:
                # temps additionnel pour cette période
                over = tot_sec - ((min_end - min_start) * 60)
                return f"{min_end}:00 + {int(over // 60):02d}:{int(over % 60):02d}"
    # Au-delà des prolongs
    rel_frame = frame_idx - periods[-1][2]
    tot_sec = rel_frame / fps
    min_end = periods[-1][4]
    return f"{min_end}:00 + {int(tot_sec // 60):02d}:{int(tot_sec % 60):02d}"




def build_ball_carrier_array(
    home_ids, away_ids, n_frames, possession, xy_objects, distance_threshold=3.5
):
    """
    Pour chaque frame, renvoie (pid, side) du porteur (joueur de l'équipe en possession le plus proche du ballon, si < seuil).
    Sinon, None.
    Args :
        home_ids, away_ids : listes d'ID joueurs
        n_frames : total frames
        possession : array/list/Code par frame (0=personne, 1=Home, 2=Away)
        xy_objects : floodlight xy (pour positions joueurs et balle)
        distance_threshold : max mètres pour considérer le porteur (sinon None)
    Returns :
        frame_carrier : list of (pid, side) ou None
    """

    # Aplatit possession si nécessaire
    if isinstance(possession, dict):  # floodlight format
        pos1 = possession['firstHalf'].code
        pos2 = possession['secondHalf'].code
        possession_flat = np.concatenate([pos1, pos2])
    elif hasattr(possession, 'code'):
        possession_flat = possession.code
    else:
        possession_flat = np.array(possession)

    # Récupère xy
    player_xy = {}
    for side, ids in [('Home', home_ids), ('Away', away_ids)]:
        arr = np.vstack([
            xy_objects['firstHalf'][side].xy,
            xy_objects['secondHalf'][side].xy
        ])
        for j, pid in enumerate(ids):
            player_xy[pid] = arr[:, 2*j:2*j+2]
    ball_xy = np.vstack([
        xy_objects['firstHalf']['Ball'].xy,
        xy_objects['secondHalf']['Ball'].xy
    ])

    frame_carrier = []
    for i in range(n_frames):
        poss = possession_flat[i]
        if poss == 1:
            ids, side = home_ids, "Home"
        elif poss == 2:
            ids, side = away_ids, "Away"
        else:
            frame_carrier.append((None, None))
            continue

        bx, by = ball_xy[i]
        min_dist = np.inf
        pid_proche = None
        for pid in ids:
            px, py = player_xy[pid][i]
            dist = np.sqrt((bx - px)**2 + (by - py)**2)
            if dist < min_dist:
                min_dist = dist
                pid_proche = pid
        # Si trop loin, pas de porteur
        if pid_proche is not None and min_dist < distance_threshold:
            frame_carrier.append((pid_proche, side))
        else:
            frame_carrier.append((None, None))
    return frame_carrier




def get_pressure_color(pressure):
    """
    Couleur linéaire entre vert (0) et violet (1), sans autres couleurs intermédiaires.
    """
    green = np.array([62, 207, 68])
    yellow = np.array([247, 182, 0])
    red = np.array([224, 58, 37])
    violet = np.array([176, 21, 153])
    p = np.clip(pressure, 0, 1)
    if p < 0.33:
        frac = p / 0.33
        rgb = (1 - frac) * green + frac * yellow
    elif p < 0.66:
        frac = (p - 0.33) / (0.33)
        rgb = (1 - frac) * yellow + frac * red
    else:
        frac = (p - 0.66) / (0.34)
        rgb = (1 - frac) * red + frac * violet
    rgb = rgb.astype(int)
    return QColor(*rgb)



def compute_dynamic_pressing(
    ball_xy,              # tuple (x, y) de la balle à la frame considérée
    carrier_pid,          # id du porteur de balle à la frame considérée
    carrier_side,         # "Home" ou "Away", camp du porteur
    home_ids,           # liste des IDs joueurs de l'équipe Home
    away_ids,           # liste des IDs joueurs de l'équipe Away
    xy_objects,           # structure contenant les positions (xy) des joueurs/balle
    dsam,                 # structure contenant les vitesses (S), etc. des joueurs
    orientations,         # dict donnant l’orientation de chaque joueur à chaque frame
    half,                 # "firstHalf" ou "secondHalf"
    idx,                  # index de la frame courante dans la mi-temps
    t_threshold=1.2,      # seuil temps pour la probabilité de pressing (~temps d’accès max au porteur)
    sigma=0.25,           # largeur de la sigmoïde pour convertir le tti en probabilité
    max_speed=10.0,       # vitesse max supposée d’un défenseur (m/s)
    speed_threshold=1.5   # vitesse minimale pour qu’un défenseur soit “pris en compte” (m/s)
):
    """
    Calcule la pression défensive sur le porteur de balle (carrier_pid) au frame idx.
    """
   # --- Position du porteur
    try:
        defenders_ids = home_ids if carrier_side == "Away" else away_ids
        carrier_team_ids = home_ids if carrier_side == "Home" else away_ids
        xy = xy_objects[half][carrier_side].xy[idx]
        i = carrier_team_ids.index(carrier_pid)
        px, py = xy[2*i], xy[2*i+1]
    except Exception as e:
        px, py = ball_xy

    # Défenseurs
    res = []
    for pid in defenders_ids:
        try:
            side = "Home" if carrier_side == "Away" else "Away"
            xy = xy_objects[half][side].xy[idx]
            ids = xy_objects[half][side].ids if hasattr(xy_objects[half][side], 'ids') else defenders_ids
            i = ids.index(pid)
            x, y = xy[2*i], xy[2*i+1]
            v = dsam[side][pid][half]["S"][idx]
            angle = orientations[pid][idx]
            vx, vy = v * np.cos(angle), v * np.sin(angle)
            dist = np.sqrt((px - x)**2 + (py - y)**2)
            speed = np.linalg.norm([vx, vy])
            if np.isnan(x) or np.isnan(y):
                tti = np.inf
                proba = 0
            elif speed < speed_threshold:
                tti = np.inf
                proba = 0
            else:
                tti = dist / (max_speed + 1e-5)
                proba = expit((t_threshold - tti) / sigma)
            res.append(proba)
        except Exception as e:
            res.append(0)
    # Pression globale
    intensity = 1 - np.prod(1 - np.array(res))
    return float(np.clip(intensity, 0, 1))