# main.py
 
import os
import sys
import numpy as np
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSlider, QPushButton, QLabel, QComboBox, QCheckBox, QColorDialog, QSpinBox, QButtonGroup, QRadioButton, QGroupBox, QListWidget, QListWidgetItem, QDialog
)
from PyQt5.QtCore import Qt, QTimer, QEvent
from PyQt5.QtGui import QColor
from pitch_widget import PitchWidget
from annotation_tools import ArrowAnnotationManager
from data_processing import load_data, build_player_out_frames, extract_match_actions_from_events
from visualization import format_match_time
from config import *

# --- CONFIGURATION: Always use relative paths ---
CODE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CODE_DIR)
DATA_PATH = os.path.join(PROJECT_ROOT, "data/")

MATCH_ID = "J03WN1"
FILE_NAME_POS = f"DFL_04_03_positions_raw_observed_DFL-COM-000001_DFL-MAT-{MATCH_ID}.xml"
FILE_NAME_INFOS = f"DFL_02_01_matchinformation_DFL-COM-000001_DFL-MAT-{MATCH_ID}.xml"
FILE_NAME_EVENTS = f"DFL_03_02_events_raw_DFL-COM-000001_DFL-MAT-{MATCH_ID}.xml"

# ======= CHARGEMENT CENTRALISÉ =======
data = load_data(
    DATA_PATH,
    FILE_NAME_POS,
    FILE_NAME_INFOS,
    FILE_NAME_EVENTS,
)

xy_objects         = data['xy_objects']
possession         = data['possession']
events             = data['events']
pitch_info         = data['pitch_info']
teams_df           = data['teams_df']
home_team_name     = data['home_name']
away_team_name     = data['away_name']
home_ids           = data['home_ids']
away_ids           = data['away_ids']
player_ids         = data['player_ids']
player_orientations= data['orientations']
dsam               = data['dsam']
home_colors        = data['home_colors']
away_colors        = data['away_colors']
id2num             = data['id2num']
n_frames_firstHalf = data['n1']
n_frames_secondHalf= data['n2']
n_frames           = data['ntot']
last_positions     = {'Home': {pid: (np.nan, np.nan) for pid in home_ids}, 'Away': {pid: (np.nan, np.nan) for pid in away_ids}, 'Ball': (np.nan, np.nan)}
player_out_frames  = build_player_out_frames(events, FPS, n_frames_firstHalf)

# Dans ton main.py ou data_processing.py après load_data()
"""for segment in events:
    for team in events[segment]:
        df = events[segment][team].events
        print(f"== {segment} | {team} ==")
        print(df['eID'].value_counts())
        print(df[['eID','minute','second','outcome']].head(10))"""


X_MIN, X_MAX = pitch_info.xlim
Y_MIN, Y_MAX = pitch_info.ylim



def get_frame_data(frame_number):
    if frame_number < n_frames_firstHalf:
        return "firstHalf", frame_number, "1st Half"
    else:
        return "secondHalf", frame_number - n_frames_firstHalf, "2nd Half"

def get_possession_for_frame(possession, half, frame_idx):
    poss_val = possession[half].code[frame_idx]
    if poss_val == 1:
        return "Home"
    elif poss_val == 2:
        return "Away"
    else:
        return None
    
def get_offside_line_x(xy_objects, half, frame_idx, possession_team, home_ids, away_ids, teams_df, last_positions):
    defending_team = "Home" if possession_team == "Away" else "Away"
    player_ids_team = home_ids if defending_team == "Home" else away_ids
    team_name = teams_df[teams_df['PersonId'] == player_ids_team[0]]['team'].iloc[0]

    gk_ids = set(
        teams_df[
            (teams_df['team'] == team_name)
            & (teams_df['PlayingPosition'].str.lower().str.contains('tw', na=False))
        ]['PersonId']
    )

    xy = xy_objects[half][defending_team].xy[frame_idx]
    x_coords = []

    for i, pid in enumerate(player_ids_team):
        if pid in gk_ids:
            continue
        x = xy[2*i]
        if np.isnan(x):
            x = last_positions[defending_team].get(pid, (np.nan, np.nan))[0]
        if not np.isnan(x):
            x_coords.append(x)

    if not x_coords:
        return None

    return max(x_coords) if defending_team == "Home" else min(x_coords)



class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tactikz")
        self.resize(1700, 1000)

        main_layout = QHBoxLayout(self)
        left_panel = QVBoxLayout()
        self.pitch_widget = PitchWidget(X_MIN, X_MAX, Y_MIN, Y_MAX)
        left_panel.addWidget(self.pitch_widget)
        self.actions_list_widget = None


        # Annotation manager avec flèche noire par défaut
        self.annotation_manager = ArrowAnnotationManager(self.pitch_widget.scene)
        self.current_tool = "select"

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

        self.offside_checkbox = QCheckBox("Offside")
        self.offside_checkbox.setChecked(True)
        control_layout.addWidget(self.offside_checkbox)

        self.frame_slider.valueChanged.connect(self.update_scene)
        self.play_button.clicked.connect(self.toggle_play_pause)

        # ----------- OUTILS ANNOTATION -----------
        tools_panel = QVBoxLayout()
        tools_panel.addWidget(QLabel("Annotation"))

        self.match_actions_button = QPushButton("Match Actions")
        self.match_actions_button.clicked.connect(self.show_match_actions)
        tools_panel.addWidget(self.match_actions_button)


        self.select_button = QPushButton("Selection")
        self.select_button.setCheckable(True)
        self.select_button.setChecked(True)
        self.select_button.clicked.connect(lambda: self.set_tool_mode("select"))
        tools_panel.addWidget(self.select_button)

        self.arrow_button = QPushButton("Arrow")
        self.arrow_button.setCheckable(True)
        self.arrow_button.setChecked(False)
        self.arrow_button.clicked.connect(lambda: self.set_tool_mode("arrow"))
        tools_panel.addWidget(self.arrow_button)

        self.curve_button = QPushButton("Curved Arrow")
        self.curve_button.setCheckable(True)
        self.curve_button.setChecked(False)
        self.curve_button.clicked.connect(lambda: self.set_tool_mode("curve"))
        tools_panel.addWidget(self.curve_button)

        self.color_button = QPushButton("Arrow Color")
        self.color_button.clicked.connect(self.choose_arrow_color)
        tools_panel.addWidget(self.color_button)

        self.delete_button = QPushButton("Delete Last Arrow")
        self.delete_button.clicked.connect(self.delete_last_arrow)
        tools_panel.addWidget(self.delete_button)

        tools_panel.addStretch(1)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(ANNOTATION_ARROW_SCALE_RANGE[0], ANNOTATION_ARROW_SCALE_RANGE[1])
        self.width_spin.setValue(ANNOTATION_ARROW_BASE_WIDTH_VALUE) 

        self.width_spin.valueChanged.connect(self.set_arrow_width)
        tools_panel.addWidget(QLabel("Arrow Width"))
        tools_panel.addWidget(self.width_spin)

        style_group = QGroupBox("Line Style")
        style_layout = QVBoxLayout()
        self.style_buttons = QButtonGroup()
        solid_rb = QRadioButton("Solid")
        dotted_rb = QRadioButton("Dotted")
        zigzag_rb = QRadioButton("Zigzag")
        self.style_buttons.addButton(solid_rb, 0)
        self.style_buttons.addButton(dotted_rb, 1)
        self.style_buttons.addButton(zigzag_rb, 2)
        solid_rb.setChecked(True)
        style_layout.addWidget(solid_rb)
        style_layout.addWidget(dotted_rb)
        style_layout.addWidget(zigzag_rb)
        style_group.setLayout(style_layout)
        tools_panel.addWidget(style_group)
        self.style_buttons.buttonClicked.connect(self.change_line_style)

        main_layout.addLayout(left_panel, stretch=8)
        main_layout.addLayout(tools_panel, stretch=2)

        self.setLayout(main_layout)
        self.update_scene(0)
        self.installEventFilter(self)  # Ajoute ceci, pour attraper tous les keypress au niveau fenêtre
        self.pitch_widget.view.viewport().installEventFilter(self)
        self.pitch_widget.view.viewport().setFocusPolicy(Qt.StrongFocus)
        self.pitch_widget.view.viewport().setFocus()


        # Etat initial : sélection
        self.set_tool_mode("select")


    def show_match_actions(self):
        actions = extract_match_actions_from_events(events, FPS)
        actions_list_widget = QListWidget()
        for act in actions:
            item = QListWidgetItem(f"{act['emoji']} {act['label']} - {act['minute']}:{act['second']:02d} ({act['team']})")
            item.setData(Qt.UserRole, act['frame'])
            actions_list_widget.addItem(item)
        actions_list_widget.itemClicked.connect(self.goto_action_frame)
        dlg = QDialog(self)
        layout = QVBoxLayout(dlg)
        layout.addWidget(actions_list_widget)
        dlg.setWindowTitle("Match Actions")
        dlg.setMinimumWidth(320)
        dlg.exec_()

    def goto_action_frame(self, item):
        frame = item.data(Qt.UserRole)
        self.frame_slider.setValue(frame)

    def set_tool_mode(self, mode):
        self.current_tool = mode
        self.select_button.setChecked(mode == "select")
        self.arrow_button.setChecked(mode == "arrow")
        self.curve_button.setChecked(mode == "curve")
        self.pitch_widget.view.setCursor(Qt.ArrowCursor if mode == "select" else Qt.CrossCursor)
        if mode == "select":
            self.annotation_manager.try_finish_arrow()
        if mode in ("arrow", "curve"):
            self._pause_match()
        self.annotation_manager.set_mode(mode)
        # Toujours redonner le focus clavier après changement de mode
        self.pitch_widget.view.viewport().setFocus()





    def _pause_match(self):
        if self.is_playing:
            self.toggle_play_pause()

    def set_arrow_width(self, value):
        self.annotation_manager.set_width(value)

    def change_line_style(self, button):
        txt = button.text()
        if txt == "Normale":
            self.annotation_manager.set_style("solid")
        elif txt == "Pointillé":
            self.annotation_manager.set_style("dotted")
        elif txt == "Serpentin":
            self.annotation_manager.set_style("zigzag")

    def choose_arrow_color(self):
        color = QColorDialog.getColor(QColor(self.annotation_manager.arrow_color))
        if color.isValid():
            self.annotation_manager.set_color(color.name())


    def delete_last_arrow(self):
        self.annotation_manager.delete_last_arrow()


    def keyPressEvent(self, event):
        if self.current_tool != "select":
            self.annotation_manager.try_finish_arrow()
            self.set_tool_mode("select")
            # Event handled
            return
        # Sinon, laisse Qt gérer
        super().keyPressEvent(event)


    def eventFilter(self, obj, event):
        if obj != self.pitch_widget.view.viewport():
            return False
        # Si on est en mode sélection : Qt gère normalement
        if self.current_tool == "select":
            return False
        # GESTION CLIC SOURIS
        if event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                scene_pos = self.pitch_widget.view.mapToScene(event.pos())
                self.annotation_manager.add_point(scene_pos)
                # Mode flèche droite/zigzag/dotted : 2 clics → finish direct et retour en select
                if not self.annotation_manager.arrow_curved and len(self.annotation_manager.arrow_points) == 2:
                    self.annotation_manager.finish_arrow()
                    self.set_tool_mode("select")
            elif event.button() == Qt.RightButton:
                if len(self.annotation_manager.arrow_points) < 2:
                    self.annotation_manager.cancel_arrow()
                    self.set_tool_mode("select")
            return True  # Empêche propagation Qt
        elif event.type() == QEvent.MouseMove and self.annotation_manager.arrow_points:
            scene_pos = self.pitch_widget.view.mapToScene(event.pos())
            self.annotation_manager.update_preview(scene_pos)
            return True
        return False

    
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
        self.pitch_widget.clear_dynamic() 
        self.pitch_widget.draw_pitch()
        half, idx, halftime = get_frame_data(frame_number)

        TMP_COUNTER = 0
        for side, ids, colors in [("Home", home_ids, home_colors), ("Away", away_ids, away_colors)]:
            xy = xy_objects[half][side].xy[idx]
            for i, pid in enumerate(ids):
                try:
                    x, y = xy[2*i], xy[2*i+1]
                    main, sec, numc = colors[pid]
                    num = id2num.get(pid, "")
                    if not np.isnan(x) and not np.isnan(y):
                        TMP_COUNTER += 1
                        self.pitch_widget.draw_player(
                            x=x, y=y, main_color=main, sec_color=sec, num_color=numc, number=num,
                            angle=player_orientations[pid][frame_number], velocity=dsam[side][pid][half]['S'][idx],
                            display_orientation=self.orientation_checkbox.isChecked(),
                            z_offset=(10 if side == "Home" else 50) + i,
                        )
                except IndexError:
                    continue


        # Ball
        ball_xy = xy_objects[half]["Ball"].xy[idx]
        x, y = ball_xy[0], ball_xy[1]
        self.pitch_widget.draw_ball(x=x, y=y)

        # Offside line
        possession_team = get_possession_for_frame(possession, half, idx)
        offside_x = get_offside_line_x(xy_objects, half, idx, possession_team, home_ids, away_ids, teams_df, last_positions)
        self.pitch_widget.draw_offside_line(offside_x, visible=self.offside_checkbox.isChecked())

        match_time = format_match_time(
            frame_number, n_frames_firstHalf, n_frames_secondHalf, 0, 0, fps=FPS
        )
        self.info_label.setText(f"{halftime} {match_time}   |   Frame {frame_number}")



if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
