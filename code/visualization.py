# visualization.py

import matplotlib.pyplot as plt
import seaborn as sns
from floodlight.io.dfl import read_position_data_xml, read_event_data_xml
from config import *
import xml.etree.ElementTree as ET

# Constants
COL_FACE = "lightgrey"
plt.style.use("ggplot")

def load_data(path, file_name_pos, file_name_infos, file_name_events):
    xy_objects, possession, ballstatus, teamsheets, pitch = read_position_data_xml(
        f"{path}{file_name_pos}", f"{path}{file_name_infos}"
    )
    print(possession)
    print(teamsheets)
    events, _, _ = read_event_data_xml(f"{path}{file_name_events}", f"{path}{file_name_infos}")


    return xy_objects, possession, events, pitch


# Count Plot for Event IDs
def plot_event_count(all_events):
    fig, ax = plt.subplots(figsize=(16, 9), tight_layout=True)
    sns.countplot(all_events["eID"], order=all_events["eID"].value_counts().index, ax=ax)
    ax.set_xscale("log")
    ax.tick_params(axis="x", labelsize=14)
    ax.tick_params(axis="y", labelsize=14)
    ax.set_xlabel("Event ID", size=14)
    ax.set_ylabel("Count", size=14)
    plt.show()

# KDE Plot
def plot_kde(xy_objects, pitch):
    fig, ax = plt.subplots(2, 2, constrained_layout=True, figsize=(13, 9))
    for a in ax.flat:
        pitch.plot(ax=a)
        a.set_facecolor(COL_FACE)
        a.set_xlim(-55, 55)
        a.set_ylim(-37, 37)
        a.annotate("Attacking Direction", xy=(-51, -25), xytext=(-51, -28), xycoords="data", fontsize=12)
        a.annotate("", xy=(-22, -25), xytext=(-51, -25), xycoords="data",
                    arrowprops=dict(arrowstyle="->", connectionstyle="arc3"), ha="center", va="top")

    ax[0, 0].set_xlabel("TW", size=14)
    ax[0, 1].set_xlabel("STZ", size=14)
    ax[1, 0].set_xlabel("OLM", size=14)
    ax[1, 1].set_xlabel("IVL", size=14)

    sns.kdeplot(x=xy_objects["firstHalf"]["Home"].xy[:, 22], y=xy_objects["firstHalf"]["Home"].xy[:, 23], fill=True, color="red", alpha=0.5, ax=ax[0, 0])
    sns.kdeplot(x=xy_objects["firstHalf"]["Home"].xy[:, 4], y=xy_objects["firstHalf"]["Home"].xy[:, 5], fill=True, color="green", alpha=0.5, ax=ax[0, 1])
    sns.kdeplot(x=xy_objects["firstHalf"]["Home"].xy[:, 30], y=xy_objects["firstHalf"]["Home"].xy[:, 31], fill=True, color="blue", alpha=0.5, ax=ax[1, 0])
    sns.kdeplot(x=xy_objects["firstHalf"]["Home"].xy[:, 8], y=xy_objects["firstHalf"]["Home"].xy[:, 9], fill=True, color="purple", alpha=0.5, ax=ax[1, 1])

    plt.show()

# Goal Positions Plot
def plot_goal_positions(xy_objects, events, pitch):
    framerate = xy_objects["secondHalf"]["Home"].framerate
    events["secondHalf"]["Home"].add_frameclock(framerate)
    goals = events["secondHalf"]["Home"].events.loc[events["secondHalf"]["Home"].events["eID"] == "ShotAtGoal_SuccessfulShot"]
    first_goal = goals.iloc[0]
    frame_first_goal = int(first_goal["gameclock"] * framerate + 1.6 * framerate)  # offset event clock, pos data
    second_before_goal = frame_first_goal - 5 * framerate

    fig, ax = plt.subplots(tight_layout=True, figsize=(16, 10))
    pitch.plot(ax=ax)
    ax.set_facecolor(COL_FACE)

    xy_objects["secondHalf"]["Home"].plot(t=(second_before_goal, frame_first_goal), plot_type="trajectories", color="blue", ax=ax)
    xy_objects["secondHalf"]["Away"].plot(t=(second_before_goal, frame_first_goal), plot_type="trajectories", color="red", ax=ax)
    xy_objects["secondHalf"]["Ball"].plot(t=(second_before_goal, frame_first_goal), plot_type="trajectories", color="black", ax=ax)

    xy_objects["secondHalf"]["Home"].plot(t=frame_first_goal, color="blue", ax=ax)
    xy_objects["secondHalf"]["Away"].plot(t=frame_first_goal, color="red", ax=ax)
    xy_objects["secondHalf"]["Ball"].plot(t=frame_first_goal, color="black", ax=ax)

    plt.show()
    
    
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
