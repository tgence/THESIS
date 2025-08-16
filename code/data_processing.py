# data_processing.py
"""
Data loading and transformation pipeline for Floodlight XML.

Responsibilities:
- Read positions, events, and match info XML files
- Build team/player metadata, IDs, and color dictionaries
- Compute DSAM metrics, player orientations, ball carrier per frame
- Extract a curated list of match actions with frames and display labels
- Provide time formatting helpers used in the UI
"""
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
    """Normalize strings into hex colors, falling back if invalid."""
    if isinstance(val, str) and (val.startswith('#') or len(val)==6):
        return val if val.startswith('#') else '#'+val
    return fallback

def get_player_color_dict(df):
    """Build {playerId: (main, secondary, number)} color mapping from team sheet."""
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
    Compute and smooth player orientation (per frame).
    Returns dict: pid -> list[angle_in_radians] across both halves.
    """
    orientations = {pid: [] for pid in player_ids['Home'] + player_ids['Away']}
    for half in ["firstHalf", "secondHalf"]:
        for team in ["Home", "Away"]:
            xy = xy_data[half][team].xy  # shape (frames, n_players*2)
            n_frames = xy.shape[0]
            ids = player_ids[team]
            for j, pid in enumerate(ids):
                traj = xy[:, 2*j:2*j+2]
                # raw frame-to-frame (nan-safe) differences
                dx = np.diff(traj[:, 0], prepend=traj[0,0])
                dy = np.diff(traj[:, 1], prepend=traj[0,1])
                angles = np.arctan2(dy, dx)
                # convert to cos/sin for smoothing angles across wrap-around
                cos_a = np.cos(angles)
                sin_a = np.sin(angles)
                # If the series is too short, skip smoothing
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
    Extract D, S, A, M per player and per half from the positions XML.
    Missing values are filled with NaN and arrays are sized to the half length.
    """
    import xml.etree.ElementTree as ET
    tree_pos = ET.parse(file_pos)
    root_pos = tree_pos.getroot()
    dsam = {'Home': {}, 'Away': {}}

    # Initialize all entries with NaNs
    for side in ['Home', 'Away']:
        for pid in player_ids[side]:
            dsam[side][pid] = {}
            for segment, n_frames in n_frames_per_half.items():
                dsam[side][pid][segment] = {k: [np.nan]*n_frames for k in ['D', 'S', 'A', 'M']}

    # Walk through the XML
    for frameset in root_pos.findall('.//FrameSet'):
        team_id = frameset.get('TeamId')
        person_id = frameset.get('PersonId')
        segment = frameset.get('GameSection', 'unknown')
        # Determine the side (Home/Away)
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

def extract_match_actions_from_events(events, FPS=25, n_frames_firstHalf=0):
    """
    Extract curated match actions with proper frame offsets per half.
    """
    ACTIONS = []
    
    for segment in events:
        # Compute offset based on the half
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
                
                # Frame with half-dependent offset
                frame = int((minute * 60 + second) * FPS) + frame_offset
                
                qualifier = row.get('qualifier', '')
                
                # Event mapping to curated action labels/emojis
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
                # Deduplicate: avoid adding the same action at the same frame
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
                
                # Cards (special handling)
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
    
    # Sort by frame
    ACTIONS = sorted(ACTIONS, key=lambda x: x["frame"])
    return ACTIONS

def format_display_time(minute, second, segment):
    """
    Format a display time (MM:SS [+ added time]) for a segment and raw time.
    """
    # Base minutes depend on the half
    if segment.lower() in ["firsthalf", "first_half", "ht1"]:
        base_minutes = 0
        half_duration = 45
    elif segment.lower() in ["secondhalf", "second_half", "ht2"]:
        base_minutes = 45
        half_duration = 45
    else:
        # Extra time or other periods
        base_minutes = 90
        half_duration = 15
    
    total_minutes = base_minutes + minute
    
    # If we pass normal half duration, produce added time format
    if minute >= half_duration:
        extra_time_minutes = minute - half_duration
        return f"{base_minutes + half_duration}:00+{int(extra_time_minutes):02d}:{int(second):02d}"
    else:
        return f"{total_minutes:02d}:{second:02d}"
    


def load_data(path, file_pos, file_info, file_events):
    """Load all Floodlight data and compute derived structures used by the app."""

    # 1. Floodlight extraction (positions, etc.)
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
    # 4. Filter players + build ID mappings
    home_df = teams_df[teams_df.team==home_name]
    away_df = teams_df[teams_df.team==away_name]
    home_ids = home_df.PersonId.tolist()
    away_ids = away_df.PersonId.tolist()
    player_ids = {'Home': home_ids, 'Away': away_ids}
    # Add TeamId per team for DSAM extraction
    teamid_map = {
        'Home': home_df.iloc[0]['TeamId'] if not home_df.empty else None,
        'Away': away_df.iloc[0]['TeamId'] if not away_df.empty else None
    }
    # 5. Extract D (distance)/S (speed)/A (acceleration)/M (minute) and compute frame counts per half/total
    n1 = xy['firstHalf']['Home'].xy.shape[0]
    n2 = xy['secondHalf']['Home'].xy.shape[0]
    ntot = n1 + n2
    n_frames_per_half = {'firstHalf': n1, 'secondHalf': n2}
    dsam = extract_dsam_from_xml(
        os.path.join(path, file_pos), player_ids, teamid_map, n_frames_per_half
    )
    # 6. Other transforms
    orientations = compute_orientations(xy, player_ids)
    home_colors = get_player_color_dict(home_df)
    away_colors = get_player_color_dict(away_df)
    id2num = dict(zip(teams_df.PersonId, teams_df['ShirtNumber']))

    # 7. Ball carrier per frame
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
    """Format global frame index into a match time string across periods."""
    periods = [
        ("FirstHalf", 0, n_frames_firstHalf, 0, LENGTH_FIRST_HALF),
        ("SecondHalf", n_frames_firstHalf, n_frames_firstHalf + n_frames_secondHalf, LENGTH_FIRST_HALF, LENGTH_FULL_TIME),
    ]
    # Add overtime periods if present
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

    # Find which period this frame belongs to
    for label, start_f, end_f, min_start, min_end in periods:
        if start_f <= frame_idx < end_f:
            rel_frame = frame_idx - start_f
            tot_sec = rel_frame / fps
            min_ = int(tot_sec // 60) + min_start
            sec_ = int(tot_sec % 60)
            if min_ < min_end:
                return f"{min_:02d}:{sec_:02d}"
            else:
                # Added time for this period
                over = tot_sec - ((min_end - min_start) * 60)
                return f"{min_end}:00 + {int(over // 60):02d}:{int(over % 60):02d}"
    # Beyond extra time
    rel_frame = frame_idx - periods[-1][2]
    tot_sec = rel_frame / fps
    min_end = periods[-1][4]
    return f"{min_end}:00 + {int(tot_sec // 60):02d}:{int(tot_sec % 60):02d}"




def build_ball_carrier_array(
    home_ids, away_ids, n_frames, possession, xy_objects, distance_threshold=3.5
):
    """
    For each frame, return (pid, side) of the carrier (closest in-possession
    player to the ball) if within `distance_threshold`, else (None, None).
    """

    # Flatten possession into a 1D array if needed
    if isinstance(possession, dict):  # floodlight format
        pos1 = possession['firstHalf'].code
        pos2 = possession['secondHalf'].code
        possession_flat = np.concatenate([pos1, pos2])
    elif hasattr(possession, 'code'):
        possession_flat = possession.code
    else:
        possession_flat = np.array(possession)

    # Get XY arrays for all players and the ball
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
        # If too far, there is no ball carrier
        if pid_proche is not None and min_dist < distance_threshold:
            frame_carrier.append((pid_proche, side))
        else:
            frame_carrier.append((None, None))
    return frame_carrier




def get_pressure_color(pressure):
    """
    Map pressure in [0, 1] to a color ramp from green (0) to violet (1).
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



def compute_pressure(
    ball_xy,              # tuple (x, y) of the ball at current frame
    carrier_pid,          # id of the ball carrier at current frame
    carrier_side,         # "Home" or "Away"
    home_ids,             # list of Home player IDs
    away_ids,             # list of Away player IDs
    xy_objects,           # positions for players/ball
    dsam,                 # speeds etc. for players
    orientations,         # player orientation per frame
    half,                 # "firstHalf" or "secondHalf"
    idx,                  # index of current frame within the half
    t_threshold=1.2,      # time threshold for pressing probability (s)
    sigma=0.5,           # sigmoid width for probability mapping
):
    """
    Compute defensive pressure around the ball carrier at the given frame.
    """
   # --- Carrier position
    try:
        defenders_ids = home_ids if carrier_side == "Away" else away_ids
        carrier_team_ids = home_ids if carrier_side == "Home" else away_ids
        xy = xy_objects[half][carrier_side].xy[idx]
        i = carrier_team_ids.index(carrier_pid)
        px, py = xy[2*i], xy[2*i+1]
    except Exception as e:
        px, py = ball_xy

    # Defenders list (opposite team of the carrier)
    res = []
    for pid in defenders_ids:
        try:
            side = "Home" if carrier_side == "Away" else "Away"
            xy = xy_objects[half][side].xy[idx]
            ids = xy_objects[half][side].ids if hasattr(xy_objects[half][side], 'ids') else defenders_ids
            i = ids.index(pid)
            x, y = xy[2*i], xy[2*i+1]

            if np.isnan(x) or np.isnan(y):
                res.append(0)
                continue

            # Distance and unit vector from defender to carrier
            dx, dy = (px - x), (py - y)
            dist = float(np.hypot(dx, dy))
            if dist <= 1e-6: # if the defender is at the same position as the carrier, we want to avoid "zero-division"
                res.append(1.0)
                continue
            ux, uy = dx / dist, dy / dist

            # Kinematics along the line to carrier
            v = float(dsam[side][pid][half]["S"][idx])  # m/s
            a_mag = dsam[side][pid][half]["A"][idx]
            # Skip defender if kinematic inputs are missing
            if np.isnan(v) or np.isnan(a_mag) or np.isnan(orientations[pid][idx]):
                continue
            angle = float(orientations[pid][idx]) if pid in orientations and len(orientations[pid]) > idx else 0.0

            # Defender heading unit vector
            hx, hy = np.cos(angle), np.sin(angle)

            # Project speed and acceleration onto the line to the carrier
            v0 = v * (hx * ux + hy * uy)  # m/s along (def -> carrier)
            a_par = a_mag * (hx * ux + hy * uy)  # assume accel along heading

            # Solve 0.5*a*t^2 + v0*t - dist = 0 (constant acceleration along the line)
            if abs(a_par) < 1e-9:
                v_eff = v0 if v0 > 0 else 1e-6
                tti = dist / v_eff
            else:
                disc = v0*v0 + 2.0 * a_par * dist
                if disc >= 0:
                    tti = (-v0 + np.sqrt(disc)) / a_par
                    if tti <= 0:
                        tti = dist / (v0 if v0 > 0 else 1e-6)
                else:
                    tti = dist / (abs(v0) + 1e-6)

            proba = float(expit((t_threshold - tti) / sigma))
            res.append(proba)
        except Exception:
            res.append(0)
    # Global pressure (complement of joint non-pressures)
    intensity = 1 - np.prod(1 - np.array(res))
    return float(np.clip(intensity, 0, 1))