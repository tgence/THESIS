#main.py
import os
import sys
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSlider, QPushButton, QLabel, QComboBox, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer

from pitch_widget import PitchWidget
from data_processing import load_team_sheets_for_specific_match, get_player_color_dict
from visualization import load_data, format_match_time
from config import FPS
from utils import compute_orientations

# --- CONFIGURATION: Always use relative paths ---
CODE_DIR = os.path.dirname(os.path.abspath(__file__))    # .../THESIS/code/
PROJECT_ROOT = os.path.dirname(CODE_DIR)                 # .../THESIS/
DATA_PATH = os.path.join(PROJECT_ROOT, "data/")           # .../THESIS/data
#SVG_PATH = os.path.join(PROJECT_ROOT, "visual_language/") # .../THESIS/visual_language

MATCH_ID = "J03WN1"

FILE_NAME_POS = f"DFL_04_03_positions_raw_observed_DFL-COM-000001_DFL-MAT-{MATCH_ID}.xml"
FILE_NAME_INFOS = f"DFL_02_01_matchinformation_DFL-COM-000001_DFL-MAT-{MATCH_ID}.xml"
FILE_NAME_EVENTS = f"DFL_03_02_events_raw_DFL-COM-000001_DFL-MAT-{MATCH_ID}.xml"

xy_objects, events, pitch_info = load_data(
    DATA_PATH,
    file_name_pos=FILE_NAME_POS,
    file_name_infos=FILE_NAME_INFOS,
    file_name_events=FILE_NAME_EVENTS
)
X_MIN, X_MAX = pitch_info.xlim
Y_MIN, Y_MAX = pitch_info.ylim

teams_df, home_team_name, away_team_name = load_team_sheets_for_specific_match(path=DATA_PATH, file_name_infos=FILE_NAME_INFOS)
home_players = teams_df[teams_df.team == home_team_name]
away_players = teams_df[teams_df.team == away_team_name]
home_ids = list(home_players["PersonId"])
away_ids = list(away_players["PersonId"])
player_ids = {'Home': home_ids, 'Away': away_ids}
player_orientations = compute_orientations(xy_objects, player_ids, every_n_frames=FPS)
home_colors = get_player_color_dict(home_players)
away_colors = get_player_color_dict(away_players)
id2num = dict(zip(teams_df.PersonId, teams_df['ShirtNumber']))

n_frames_firstHalf = xy_objects["firstHalf"]["Home"].xy.shape[0]
n_frames_secondHalf = xy_objects["secondHalf"]["Home"].xy.shape[0]
n_frames = n_frames_firstHalf + n_frames_secondHalf

def get_frame_data(frame_number):
    if frame_number < n_frames_firstHalf:
        return "firstHalf", frame_number, "1st Half"
    else:
        return "secondHalf", frame_number - n_frames_firstHalf, "2nd Half"

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tactikz")
        self.resize(1700, 1000)

        # ---- Layout principal: Terrain à gauche, outils à droite ----
        main_layout = QHBoxLayout(self)

        # --- Partie terrain + contrôles (gauche) ---
        left_panel = QVBoxLayout()
        # Passage du dossier SVG au widget terrain
        self.pitch_widget = PitchWidget(X_MIN, X_MAX, Y_MIN, Y_MAX)
        left_panel.addWidget(self.pitch_widget)

        # ---- Contrôles navigation et slider ----
        control_layout = QHBoxLayout()
        jump_layout = QHBoxLayout()
        jump_layout.addWidget(self.create_nav_button("back_1min", self.jump_frames))
        jump_layout.addWidget(self.create_nav_button("back_5s", self.jump_frames))
        self.frame_slider = QSlider(Qt.Horizontal)
        self.frame_slider.setMinimum(0)
        self.frame_slider.setMaximum(n_frames-1)
        self.frame_slider.setValue(0)
        jump_layout.addWidget(self.frame_slider, stretch=1)
        jump_layout.addWidget(self.create_nav_button("fwd_5s", self.jump_frames))
        jump_layout.addWidget(self.create_nav_button("fwd_1min", self.jump_frames))
        control_layout.addLayout(jump_layout)
        left_panel.addLayout(control_layout)

        # ---- Autres contrôles (droite des boutons nav) ----
        self.speed_box = QComboBox()
        for label, _ in [
            ("x0.25", 160), ("x0.5", 80), ("x1", 40), ("x2", 20), ("x4", 10), ("x16", 2), ("x64", 1)
        ]:
            self.speed_box.addItem(label)
        self.speed_box.setCurrentIndex(2)
        control_layout.addWidget(QLabel("Speed"))
        control_layout.addWidget(self.speed_box)
        self.speed_box.currentIndexChanged.connect(self.update_speed)

        self.play_button = QPushButton("▶")
        self.play_button.setFixedWidth(36)
        control_layout.addWidget(self.play_button)
        self.orientation_checkbox = QCheckBox("Display player orientation")
        self.orientation_checkbox.setChecked(True)
        control_layout.addWidget(self.orientation_checkbox)

        self.info_label = QLabel("")
        self.info_label.setMinimumWidth(260)
        self.info_label.setMaximumWidth(340)
        self.info_label.setAlignment(Qt.AlignCenter)
        control_layout.addWidget(self.info_label)

        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.next_frame)
        self.is_playing = False
        self.frame_step = 1

        self.frame_slider.valueChanged.connect(self.update_scene)
        self.play_button.clicked.connect(self.toggle_play_pause)

        main_layout.addLayout(left_panel, stretch=8)  # La zone terrain prend 80%

        # --- Barre d'outils (droite), à remplir plus tard ---
        tools_panel = QVBoxLayout()
        tools_panel.addWidget(QLabel("Outils d’annotation"))
        tools_panel.addStretch(1)
        main_layout.addLayout(tools_panel, stretch=2)

        self.setLayout(main_layout)
        self.update_scene(0)

    def jump_frames(self, n):
        new_frame = np.clip(self.frame_slider.value() + n, 0, self.frame_slider.maximum())
        self.frame_slider.setValue(new_frame)

    def create_nav_button(self, key, callback):
        params = {
            "back_1min": {'label': '< 1m', 'width': 56, 'frames': -60 * FPS, 'tooltip': 'Reculer de 1 minute'},
            "back_5s":   {'label': '< 5s', 'width': 56, 'frames': -5 * FPS, 'tooltip': 'Reculer de 5s'},
            "fwd_5s":    {'label': '5s >', 'width': 56, 'frames': 5 * FPS, 'tooltip': 'Avancer de 5s'},
            "fwd_1min":  {'label': '1m >', 'width': 56, 'frames': 60 * FPS, 'tooltip': 'Avancer de 1 minute'},
        }
        p = params[key]
        btn = QPushButton(p['label'])
        btn.setFixedWidth(p['width'])
        btn.setToolTip(p['tooltip'])
        btn.clicked.connect(lambda: callback(p['frames']))
        return btn

    def toggle_play_pause(self):
        if self.is_playing:
            self.play_button.setText("▶")
            self.timer.stop()
        else:
            self.play_button.setText("⏸")
            self.timer.start()
        self.is_playing = not self.is_playing

    def update_speed(self, idx):
        intervals = [160, 80, 40, 20, 10, 2, 1]
        self.timer.setInterval(intervals[idx])

    def next_frame(self):
        next_frame = min(self.frame_slider.value() + self.frame_step, n_frames-1)
        self.frame_slider.setValue(next_frame)
        if next_frame == n_frames-1:
            self.toggle_play_pause()

    def update_scene(self, frame_number):
        self.pitch_widget.draw_pitch()
        half, idx, halftime = get_frame_data(frame_number)
        # Home
        home_xy = xy_objects[half]["Home"].xy[idx]
        for i, pid in enumerate(home_ids):
            try:
                x, y = home_xy[2*i], home_xy[2*i+1]
                if np.isnan(x) or np.isnan(y): continue
                main, sec, numc = home_colors[pid]
                num = id2num.get(pid, "")
                self.pitch_widget.draw_player(
                    x=x, y=y, main_color=main, sec_color=sec, num_color=numc, number=num,
                    angle=player_orientations[pid][frame_number],
                    display_orientation=self.orientation_checkbox.isChecked(),
                    z_offset=10+i,
                )
            except IndexError: continue
        # Away
        away_xy = xy_objects[half]["Away"].xy[idx]
        for i, pid in enumerate(away_ids):
            try:
                x, y = away_xy[2*i], away_xy[2*i+1]
                if np.isnan(x) or np.isnan(y): continue
                main, sec, numc = away_colors[pid]
                num = id2num.get(pid, "")
                self.pitch_widget.draw_player(
                    x=x, y=y, main_color=main, sec_color=sec, num_color=numc, number=num,
                    angle=player_orientations[pid][frame_number],
                    display_orientation=self.orientation_checkbox.isChecked(),
                    z_offset=50+i,
                )
            except IndexError: continue
        # Ball
        ball_xy = xy_objects[half]["Ball"].xy[idx]
        if ball_xy is not None and not np.any(np.isnan(ball_xy)):
            bx, by = ball_xy[0], ball_xy[1]
            self.pitch_widget.draw_ball(bx, by)
        # Time/info
        match_time = format_match_time(
            frame_number, n_frames_firstHalf, n_frames_secondHalf, 0, 0, fps=FPS
        )
        self.info_label.setText(f"{halftime} {match_time}   |   Frame {frame_number}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
