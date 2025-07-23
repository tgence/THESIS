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

def load_data(path, file_pos, file_info, file_events, fps):
    # 1. Positions, possession, pitch, etc.
    # return: xy_objects, possession (Code), ballstatus (Code), teamsheets, pitch_info
    xy, possession, ballstatus, teamsheets, pitch = read_position_data_xml(
        os.path.join(path, file_pos),
        os.path.join(path, file_info)
    )
    # 2. Events
    events, _, _ = read_event_data_xml(
        os.path.join(path, file_events),
        os.path.join(path, file_info)
    )
    # 3. Teamsheets XML parsing
    tree = ET.parse(os.path.join(path, file_info)); root = tree.getroot()
    general = root.find('.//General')
    home_name, away_name = general.get('HomeTeamName'), general.get('GuestTeamName')
    rows = []
    for team in root.findall('.//Team'):
        team_name = team.get('TeamName')
        main, sec, numc = team.get('PlayerShirtMainColor'), team.get('PlayerShirtSecondaryColor'), team.get('PlayerShirtNumberColor')
        side = 'home' if team_name==home_name else 'away' if team_name==away_name else 'unknown'
        for p in team.findall('.//Player'):
            d = p.attrib.copy()
            d.update(team=team_name, side=side, shirtMainColor=main, shirtSecondaryColor=sec, shirtNumberColor=numc)
            rows.append(d)
    teams_df = pd.DataFrame(rows)
    print(teams_df)
    # 4. Filter joueurs
    home_df = teams_df[teams_df.team==home_name]
    away_df = teams_df[teams_df.team==away_name]
    home_ids = home_df.PersonId.tolist()
    away_ids = away_df.PersonId.tolist()
    player_ids = {'Home': home_ids, 'Away': away_ids}

    # 5. Orienations + couleurs
    orientations = compute_orientations(xy, player_ids, every_n_frames=fps)
    velocities = compute_velocities(xy, player_ids, every_n_frames=fps)
    home_colors = get_player_color_dict(home_df)
    away_colors = get_player_color_dict(away_df)
    id2num = dict(zip(teams_df.PersonId, teams_df['ShirtNumber']))

    # 6. Frame counts
    n1 = xy['firstHalf']['Home'].xy.shape[0]
    n2 = xy['secondHalf']['Home'].xy.shape[0]
    ntot = n1 + n2

    return {
        'xy_objects': xy, 'possession': possession, 'ballstatus': ballstatus,
        'events': events, 'pitch_info': pitch,
        'teams_df': teams_df, 'home_name': home_name, 'away_name': away_name,
        'home_ids': home_ids, 'away_ids': away_ids,
        'player_ids': player_ids, 'orientations': orientations, 'velocities': velocities,
        'home_colors': home_colors, 'away_colors': away_colors,
        'id2num': id2num,
        'n1': n1, 'n2': n2, 'ntot': ntot
    }
