# data_processing.py
 
import os
import pandas as pd
import xml.etree.ElementTree as ET
from floodlight.io.dfl import read_position_data_xml, read_event_data_xml
from utils import compute_orientations, compute_velocities

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


def extract_dsam_from_xml(file_pos, player_ids, teamid_map):
    """
    Extrait D, S, A, M, N pour chaque joueur et chaque période (firstHalf, secondHalf...).
    Retourne :
    {
      'Home': {person_id: {'firstHalf': {...}, 'secondHalf': {...}, ...}},
      'Away': {...}
    }
    """
    import xml.etree.ElementTree as ET
    tree_pos = ET.parse(file_pos)
    root_pos = tree_pos.getroot()
    dsam = {'Home': {}, 'Away': {}}

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
        data = {k: [] for k in ['D', 'S', 'A', 'M']}
        for fr in frames:
            data['D'].append(float(fr.get('D', 'nan')))
            s_kmh = float(fr.get('S', 'nan'))
            data['S'].append(s_kmh / 3.6)   # km/h -> m/s
            data['A'].append(float(fr.get('A', 'nan')))
            data['M'].append(float(fr.get('M', 'nan')))
        # Construction multi-segment
        if person_id not in dsam[side]:
            dsam[side][person_id] = {}
        dsam[side][person_id][segment] = data
    return dsam




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
    # 5. Extraction D/S/A/M/N
    dsam = extract_dsam_from_xml(
        os.path.join(path, file_pos), player_ids, teamid_map
    )
    # 6. Autres traitements
    orientations = compute_orientations(xy, player_ids)
    #velocities = compute_velocities(xy, player_ids)
    home_colors = get_player_color_dict(home_df)
    away_colors = get_player_color_dict(away_df)
    id2num = dict(zip(teams_df.PersonId, teams_df['ShirtNumber']))
    n1 = xy['firstHalf']['Home'].xy.shape[0]
    n2 = xy['secondHalf']['Home'].xy.shape[0]
    ntot = n1 + n2
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