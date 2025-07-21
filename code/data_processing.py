import os
import pandas as pd
from floodlight.io.dfl import read_position_data_xml, read_event_data_xml, read_teamsheets_from_mat_info_xml
import re
import xml.etree.ElementTree as ET




def load_team_sheets_for_specific_match(path, file_name_infos):
    # Parse the XML
    tree = ET.parse(os.path.join(path, file_name_infos))
    root = tree.getroot()

    # 1. Trouver les noms "officiels" home/away dans la balise <General>
    general = root.find('.//General')
    home_team_name = general.attrib.get('HomeTeamName')
    away_team_name = general.attrib.get('GuestTeamName')
    
    teams = []
    for team in root.findall('.//Team'):
        team_name = team.attrib.get('TeamName')
        main_color = team.attrib.get('PlayerShirtMainColor')
        secondary_color = team.attrib.get('PlayerShirtSecondaryColor')
        number_color = team.attrib.get('PlayerShirtNumberColor')
        
        # Déterminer si cette équipe est home ou away
        if team_name == home_team_name:
            side = 'home'
        elif team_name == away_team_name:
            side = 'away'
        else:
            side = 'unknown'
        
        # Loop over players
        for player in team.findall('.//Player'):
            player_dict = player.attrib.copy()
            player_dict['team'] = team_name
            player_dict['side'] = side
            player_dict['shirtMainColor'] = main_color
            player_dict['shirtSecondaryColor'] = secondary_color
            player_dict['shirtNumberColor'] = number_color
            teams.append(player_dict)
    
    # Create a DataFrame for ALL players (Home + Away)
    teams_df = pd.DataFrame(teams)
    return teams_df, home_team_name, away_team_name



# Load Team Sheets
def load_team_sheets(path):
    info_files = [x for x in os.listdir(path) if "matchinformation" in x]
    team_sheets_all = pd.DataFrame()
    for file in info_files:
        team_sheets = read_teamsheets_from_mat_info_xml(os.path.join(path, file))
        team_sheets_combined = pd.concat([team_sheets["Home"].teamsheet, team_sheets["Away"].teamsheet])
        team_sheets_all = pd.concat([team_sheets_all, team_sheets_combined])
    return team_sheets_all

   

# Load Event Data
def load_event_data(path):
    info_files = sorted([x for x in os.listdir(path) if "matchinformation" in x])
    event_files = sorted([x for x in os.listdir(path) if "events_raw" in x])
    all_events = pd.DataFrame()
    for events_file, info_file in zip(event_files, info_files):
        events, _, _ = read_event_data_xml(os.path.join(path, events_file), os.path.join(path, info_file))
        events_fullmatch = pd.DataFrame()
        for half in events:
            for team in events[half]:
                events_fullmatch = pd.concat([events_fullmatch, events[half][team].events])
        all_events = pd.concat([all_events, events_fullmatch])
    return all_events

# Load Position Data
def load_position_data(path):
    info_files = [x for x in os.listdir(path) if "matchinformation" in x]
    position_files = [x for x in os.listdir(path) if "positions_raw" in x]
    n_frames = 0
    for position_file, info_file in zip(position_files, info_files):
        positions, _, _, _, _ = read_position_data_xml(os.path.join(path, position_file), os.path.join(path, info_file))
        n_frames += len(positions["firstHalf"]["Home"]) + len(positions["secondHalf"]["Home"])
    return n_frames

# Display Data Summary
def display_data_summary(path):
    team_sheets_all = load_team_sheets(path)
    all_events = load_event_data(path)
    n_frames = load_position_data(path)

    print("Unique player IDs:", team_sheets_all["pID"].nunique())
    print("Unique teams:", team_sheets_all["team"].nunique())
    print("Total number of events:", len(all_events))
    print("Unique event ID counts:\n", all_events["eID"].value_counts())
    print("Total number of position frames:", n_frames)





def safe_color(val, fallback='#aaaaaa'):
    if isinstance(val, str) and val.startswith('#') and len(val) in [7, 9]:
        return val
    if isinstance(val, str) and len(val) == 6 and not val.startswith('#'):
        return '#' + val
    return fallback



def extract_pitch_limits(pitch_info):
    info_str = str(pitch_info)
    match = re.search(r'x = \(([-\d\.]+), ([-\d\.]+)\) / y = \(([-\d\.]+), ([-\d\.]+)\)', info_str)
    if match:
        x_min, x_max, y_min, y_max = map(float, match.groups())
        pitch_length = x_max - x_min
        pitch_width = y_max - y_min
        return x_min, x_max, y_min, y_max, pitch_length, pitch_width
    else:
        raise ValueError("Impossible to extract pitch limits from pitch_info string.")
    

def get_player_color_dict(players_df):
    d = {}
    for idx, row in players_df.iterrows():
        pid = row['PersonId']
        main = safe_color(row.get('shirtMainColor', None))
        sec = safe_color(row.get('shirtSecondaryColor', None), fallback=main)
        numc = safe_color(row.get('shirtNumberColor', None), fallback='#ffffff')
        d[pid] = (main, sec, numc)
    return d
