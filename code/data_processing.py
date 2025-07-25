# data_processing.py
 
import os
import pandas as pd
import numpy as np
import xml.etree.ElementTree as ET
from floodlight.io.dfl import read_position_data_xml, read_event_data_xml
from utils import compute_orientations, compute_velocities
from config import *


"""EVENT_WHITELIST = {
    "ShotAtGoal_SuccessfulShot": {"emoji": "⚽️", "label": "Goal"},
    "GoalKick_Play_Pass": {"emoji": "🦶", "label": "Goal Kick"},
    "FreeKick_Play_Cross": {"emoji": "🎯", "label": "Free Kick"},
    "FreeKick_Play_Pass": {"emoji": "🎯", "label": "Free Kick"},
    "FreeKick_ShotAtGoal_BlockedShot": {"emoji": "🎯", "label": "Free Kick"},
    "CornerKick_Play_Cross": {"emoji": "🟩", "label": "Corner"},
    "Caution": {"emoji": "🟨", "label": "Yellow Card"},
    # "CautionTeamofficial": {"emoji": "🟨", "label": "Yellow Card (Staff)"}, # Optionnel
    # Pas de balise explicite pour Red Card/Expulsion !
    # Penalty à traiter à part avec qualifier
}"""


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

def extract_match_actions_from_events(events, FPS):
    ACTIONS = []
    for segment in events:
        for team in events[segment]:
            df = events[segment][team].events
            for _, row in df.iterrows():
                eid = str(row.get('eID', ''))
                qualifier = str(row.get('qualifier', '')).lower()
                minute = int(row.get("minute", 0))
                second = int(row.get("second", 0))
                frame = int((minute * 60 + second) * FPS)
                
                # But classique
                if eid == "ShotAtGoal_SuccessfulShot" and "penalt" not in qualifier:
                    ACTIONS.append({"frame": frame, "segment": segment, "team": team, "minute": minute, "second": second, "label": "Goal", "emoji": "⚽️"})
                # Penalty marqué
                elif eid == "ShotAtGoal_SuccessfulShot" and "penalt" in qualifier:
                    ACTIONS.append({"frame": frame, "segment": segment, "team": team, "minute": minute, "second": second, "label": "Penalty Goal", "emoji": "🅿️"})
                # Dégagement 6m
                elif eid == "GoalKick_Play_Pass":
                    ACTIONS.append({"frame": frame, "segment": segment, "team": team, "minute": minute, "second": second, "label": "Goal Kick", "emoji": "🦶"})
                # Coup franc
                elif eid in ("FreeKick_Play_Cross", "FreeKick_Play_Pass", "FreeKick_ShotAtGoal_BlockedShot"):
                    ACTIONS.append({"frame": frame, "segment": segment, "team": team, "minute": minute, "second": second, "label": "Free Kick", "emoji": "🎯"})
                # Corner
                elif eid == "CornerKick_Play_Cross":
                    ACTIONS.append({"frame": frame, "segment": segment, "team": team, "minute": minute, "second": second, "label": "Corner", "emoji": "🟩"})
                # Jaune
                elif eid == "Caution":
                    ACTIONS.append({"frame": frame, "segment": segment, "team": team, "minute": minute, "second": second, "label": "Yellow Card", "emoji": "🟨"})
                # Rouge
                elif ("expuls" in qualifier) or ("red" in qualifier) or eid.lower() == "expulsion":
                    ACTIONS.append({"frame": frame, "segment": segment, "team": team, "minute": minute, "second": second, "label": "Red Card", "emoji": "🟥"})
    ACTIONS = sorted(ACTIONS, key=lambda x: x["frame"])
    return ACTIONS



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

    actions = extract_match_actions_from_events(events, FPS)
    """for act in actions:
        print(f"{act['emoji']} {act['label']} - {act['minute']}:{act['second']:02d} ({act['team']}) eID={act.get('eID', '')}")"""   
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
    #velocities = compute_velocities(xy, player_ids)
    home_colors = get_player_color_dict(home_df)
    away_colors = get_player_color_dict(away_df)
    id2num = dict(zip(teams_df.PersonId, teams_df['ShirtNumber']))

    return {
        'xy_objects': xy, 'possession': possession, 'ballstatus': ballstatus,
        'events': events, 'pitch_info': pitch,
        'teams_df': teams_df, 'home_name': home_name, 'away_name': away_name,
        'home_ids': home_ids, 'away_ids': away_ids,
        'player_ids': player_ids, 'orientations': orientations, 'dsam': dsam,
        'home_colors': home_colors, 'away_colors': away_colors,
        'id2num': id2num,
        'n1': n1, 'n2': n2, 'ntot': ntot
    }