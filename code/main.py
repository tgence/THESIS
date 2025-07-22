import os
import sys
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSlider, QPushButton, QLabel, QComboBox, QCheckBox, QColorDialog, QSpinBox, QButtonGroup, QRadioButton, QGroupBox
)
from PyQt5.QtCore import Qt, QTimer, QEvent

from pitch_widget import PitchWidget
from annotation_tools import ArrowAnnotationManager
from data_processing import load_data
from config import FPS
from visualization import format_match_time

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
    FPS
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
home_colors        = data['home_colors']
away_colors        = data['away_colors']
id2num             = data['id2num']
n_frames_firstHalf = data['n1']
n_frames_secondHalf= data['n2']
n_frames           = data['ntot']

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

def get_offside_line_x(xy_objects, half, frame_idx, possession_team, home_ids, away_ids, teams_df):
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
        if np.isnan(x): continue
        x_coords.append(x)
    if not x_coords:
        return None
    return max(x_coords) if defending_team == "Home" else min(x_coords)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tactikz")
        self.resize(1700, 1000)

        # --- LAYOUT PRINCIPAL ---
        main_layout = QHBoxLayout(self)

        # --- PANEL GAUCHE (Terrain + contrôles) ---
        left_panel = QVBoxLayout()
        self.pitch_widget = PitchWidget(X_MIN, X_MAX, Y_MIN, Y_MAX)
        left_panel.addWidget(self.pitch_widget)

        # ---- ANNOTATION MANAGER ----
        self.annotation_manager = ArrowAnnotationManager(self.pitch_widget.scene)
        self.arrow_mode = False

        # ---- Contrôles navigation + slider ----
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

        # ---- Autres contrôles (à droite) ----
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

        # --- PANEL DROIT (Outils d'annotation) ---
        tools_panel = QVBoxLayout()
        tools_panel.addWidget(QLabel("Annotation"))
        self.arrow_button = QPushButton("Créer Flèche")
        self.arrow_button.clicked.connect(self.activate_arrow_mode)
        tools_panel.addWidget(self.arrow_button)

        self.color_button = QPushButton("Couleur Flèche")
        self.color_button.clicked.connect(self.choose_arrow_color)
        tools_panel.addWidget(self.color_button)

        self.delete_button = QPushButton("Supprimer dernière flèche")
        self.delete_button.clicked.connect(self.delete_last_arrow)
        tools_panel.addWidget(self.delete_button)

        tools_panel.addStretch(1)

        # Largeur de trait
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 10)
        self.width_spin.setValue(3)
        self.width_spin.valueChanged.connect(self.annotation_manager.set_width)
        tools_panel.addWidget(QLabel("Largeur du trait"))
        tools_panel.addWidget(self.width_spin)

        # Style de trait
        style_group = QGroupBox("Type de ligne")
        style_layout = QVBoxLayout()
        self.style_buttons = QButtonGroup()
        solid_rb = QRadioButton("Normale")
        dotted_rb = QRadioButton("Pointillé")
        zigzag_rb = QRadioButton("Serpentin")
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

        # Courbe
        self.curve_button = QPushButton("Courbé (toggle)")
        self.curve_button.setCheckable(True)
        self.curve_button.clicked.connect(lambda: self.annotation_manager.set_curved(self.curve_button.isChecked()))
        tools_panel.addWidget(self.curve_button)

        # --- ASSEMBLAGE LAYOUT PRINCIPAL ---
        main_layout.addLayout(left_panel, stretch=8)
        main_layout.addLayout(tools_panel, stretch=2)

        self.setLayout(main_layout)
        self.update_scene(0)

        # --- EventFilter sur la zone de terrain ---
        self.pitch_widget.view.viewport().installEventFilter(self)

    def change_line_style(self, button):
        txt = button.text()
        if txt == "Normale":
            self.annotation_manager.set_style("solid")
        elif txt == "Pointillé":
            self.annotation_manager.set_style("dotted")
        elif txt == "Serpentin":
            self.annotation_manager.set_style("zigzag")

    def activate_arrow_mode(self):
        self.arrow_mode = not self.arrow_mode
        self.annotation_manager.set_active(self.arrow_mode)
        self.arrow_button.setText("Créer Flèche (ON)" if self.arrow_mode else "Créer Flèche")
        self.pitch_widget.view.setCursor(Qt.CrossCursor if self.arrow_mode else Qt.ArrowCursor)

    def choose_arrow_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.annotation_manager.set_color(color.name())

    def delete_last_arrow(self):
        self.annotation_manager.delete_last_arrow()

    # === Gestion événements souris pour les flèches ===
    def eventFilter(self, obj, event):
        if not self.arrow_mode or obj != self.pitch_widget.view.viewport():
            return False
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            scene_pos = self.pitch_widget.view.mapToScene(event.pos())
            if not self.annotation_manager.arrow_points:
                self.annotation_manager.start_arrow(scene_pos)
            else:
                self.annotation_manager.add_point(scene_pos)
        elif event.type() == QEvent.MouseMove and self.annotation_manager.arrow_points:
            scene_pos = self.pitch_widget.view.mapToScene(event.pos())
            self.annotation_manager.update_preview(scene_pos)
        elif event.type() == QEvent.MouseButtonPress and event.button() == Qt.RightButton:
            self.annotation_manager.cancel_arrow()
        elif event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.annotation_manager.cancel_arrow()
        elif event.type() == QEvent.KeyPress and event.key() in [Qt.Key_Return, Qt.Key_Enter]:
            self.annotation_manager.finish_arrow()
            self.arrow_mode = False
            self.arrow_button.setChecked(False)
            self.annotation_manager.set_active(False)
            self.pitch_widget.view.setCursor(Qt.ArrowCursor)
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
        # Détermine la possession et la ligne de hors-jeu
        possession_team = get_possession_for_frame(possession, half, idx)
        offside_x = get_offside_line_x(xy_objects, half, idx, possession_team, home_ids, away_ids, teams_df)
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
