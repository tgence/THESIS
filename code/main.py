# main.py
 
import os
import sys
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSlider, QPushButton,
    QLabel, QComboBox, QCheckBox, QColorDialog, QSpinBox, QButtonGroup,
    QRadioButton, QGroupBox, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, QTimer, QEvent, QDir, QSize
from PyQt5.QtGui import QColor, QIcon

# Imports locaux
from pitch_widget import PitchWidget
from annotation_tools import ArrowAnnotationManager
from data_processing import load_data, build_player_out_frames, extract_match_actions_from_events
from visualization import format_match_time
from trajectory_manager import TrajectoryManager
from ui_components import ActionFilterBar, MatchActionsDialog, create_nav_button
from frame_utils import FrameManager, PossessionTracker
from custom_slider import TimelineWidget
from config import *
import qt_material

from qt_material import apply_stylesheet

# --- CONFIGURATION: Always use relative paths ---
CODE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CODE_DIR)
SVG_DIR = os.path.join(PROJECT_ROOT, "svgs/")
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

        # Managers
        self.frame_manager = FrameManager(n_frames_firstHalf, n_frames_secondHalf, n_frames)
        self.trajectory_manager = None  # Initialisé après pitch_widget
        self.annotation_manager = None
        
        # État
        self.simulation_mode = False
        self.is_playing = False
        self.frame_step = 1
        self.current_tool = "select"
        
        # Actions
        self.actions_data = extract_match_actions_from_events(events, FPS, n_frames_firstHalf)
        
        self._setup_ui()
        self._setup_managers()
        self._connect_signals()
        
        self.update_scene(0)
    
    def _setup_ui(self):
        """Configure l'interface utilisateur"""
        main_layout = QHBoxLayout(self)
        
        # Panel gauche
        left_panel = QVBoxLayout()
        
        # Pitch
        self.pitch_widget = PitchWidget(X_MIN, X_MAX, Y_MIN, Y_MAX)
        left_panel.addWidget(self.pitch_widget)
        
        # Barre de filtrage des actions
        self.action_filter = ActionFilterBar(self.actions_data, self._on_filter_update)
        left_panel.addLayout(self.action_filter.layout)
        
        # Timeline et contrôles
        self._create_timeline_controls(left_panel)
        
        # Panel droit (outils)
        tools_panel = self._create_tools_panel()
        
        main_layout.addLayout(left_panel, stretch=8)
        main_layout.addLayout(tools_panel, stretch=2)
    
    def _create_timeline_controls(self, parent_layout):
        """Crée les contrôles de timeline"""
        control_layout = QHBoxLayout()
        # Layout pour les boutons et la timeline
        nav_layout = QHBoxLayout()
        nav_layout.addWidget(create_nav_button("< 1m", NAV_BUTTON_WIDTH, NAV_BUTTON_HEIGHT, -60 * FPS, "Back 1 minute", self.jump_frames))
        nav_layout.addWidget(create_nav_button("< 5s", NAV_BUTTON_WIDTH, NAV_BUTTON_HEIGHT, -5 * FPS, "Back 5 seconds", self.jump_frames))
        self.timeline_widget = TimelineWidget(
        n_frames, 
        n_frames_firstHalf, 
        n_frames_secondHalf
        )
        self.timeline_widget.frameChanged.connect(self.update_scene)
        self.timeline_widget.set_actions(self.actions_data)
        self.timeline_widget.setMaximumWidth(900)
        self.timeline_widget.setMinimumWidth(min(700, self.pitch_widget.width()))
        nav_layout.addWidget(self.timeline_widget)
        nav_layout.addWidget(create_nav_button("5s >", NAV_BUTTON_WIDTH, NAV_BUTTON_HEIGHT, 5 * FPS, "Forward 5 seconds", self.jump_frames))
        nav_layout.addWidget(create_nav_button("1m >", NAV_BUTTON_WIDTH, NAV_BUTTON_HEIGHT, 60 * FPS, "Forward 1 minute", self.jump_frames))

        

        
        control_layout.addLayout(nav_layout)
        

       
        # Speed control
        self.speed_box = QComboBox()
        for label, _ in [("x0.25", 160), ("x0.5", 80), ("x1", 40), ("x2", 20), ("x4", 10), ("x16", 2), ("x64", 1)]:
            self.speed_box.addItem(label)
        
        self.speed_box.setCurrentIndex(2)
        control_layout.addWidget(QLabel("Speed"))
        control_layout.addWidget(self.speed_box)
        
        # Play/pause icons (déclarées ici, c'est bien)
        self.play_icon = QIcon(os.path.join(SVG_DIR, "play.svg"))
        self.pause_icon = QIcon(os.path.join(SVG_DIR, "pause.svg"))
        self.play_button = QPushButton()
        self.play_button.setFixedWidth(36)
        self.play_button.setIcon(self.play_icon)
        self.play_button.setIconSize(QSize(28, 28))  # ajuste au besoin
        self.play_button.setText("")
        control_layout.addWidget(self.play_button)

        # Checkboxes
        self.orientation_checkbox = QCheckBox("Orientation")
        self.orientation_checkbox.setChecked(True)
        control_layout.addWidget(self.orientation_checkbox)
        
        self.offside_checkbox = QCheckBox("Offside")
        self.offside_checkbox.setChecked(True)
        control_layout.addWidget(self.offside_checkbox)
        
        # Info label
        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignCenter)
        control_layout.addWidget(self.info_label)
        
        parent_layout.addLayout(control_layout)
        
        # Timer
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.next_frame)
    
    def _create_tools_panel(self):
        """Crée le panneau d'outils"""
        tools_panel = QVBoxLayout()
        
        
        # Simulation mode
        tools_panel.addWidget(QLabel("Simulation"))
        self.simulation_button = QPushButton("Simulation Mode")
        self.simulation_button.setCheckable(True)
        self.simulation_button.clicked.connect(self.toggle_simulation_mode)
        tools_panel.addWidget(self.simulation_button)
        
        self.sim_interval_spin = QDoubleSpinBox()
        self.sim_interval_spin.setRange(1.0, 10.0)
        self.sim_interval_spin.setValue(3.0)
        self.sim_interval_spin.setSuffix(" sec")
        self.sim_interval_spin.setSingleStep(0.5)
        self.sim_interval_spin.valueChanged.connect(self.update_simulation_interval)
        tools_panel.addWidget(QLabel("Future interval:"))
        tools_panel.addWidget(self.sim_interval_spin)
        
        self.show_trajectories_checkbox = QCheckBox("Show trajectories")
        self.show_trajectories_checkbox.setChecked(True)
        self.show_trajectories_checkbox.stateChanged.connect(lambda: self.update_scene(self.timeline_widget.value()))
        tools_panel.addWidget(self.show_trajectories_checkbox)
        
        # Annotation tools
        tools_panel.addWidget(QLabel("─────────────"))
        tools_panel.addWidget(QLabel("Annotation"))
        
        self.select_button = QPushButton("Selection")
        self.select_button.setCheckable(True)
        self.select_button.setChecked(True)
        self.select_button.clicked.connect(lambda: self.set_tool_mode("select"))
        tools_panel.addWidget(self.select_button)
        
        self.arrow_button = QPushButton("Arrow")
        self.arrow_button.setCheckable(True)
        self.arrow_button.clicked.connect(lambda: self.set_tool_mode("arrow"))
        tools_panel.addWidget(self.arrow_button)
        
        self.curve_button = QPushButton("Curved Arrow")
        self.curve_button.setCheckable(True)
        self.curve_button.clicked.connect(lambda: self.set_tool_mode("curve"))
        tools_panel.addWidget(self.curve_button)
        
        self.color_button = QPushButton("Arrow Color")
        self.color_button.clicked.connect(self.choose_arrow_color)
        tools_panel.addWidget(self.color_button)
        
        self.delete_button = QPushButton("Delete Last Arrow")
        self.delete_button.clicked.connect(self.delete_last_arrow)
        tools_panel.addWidget(self.delete_button)
        
        # Arrow settings
        self.width_spin = QSpinBox()
        self.width_spin.setRange(ANNOTATION_ARROW_SCALE_RANGE[0], ANNOTATION_ARROW_SCALE_RANGE[1])
        self.width_spin.setValue(ANNOTATION_ARROW_BASE_WIDTH_VALUE)
        self.width_spin.valueChanged.connect(self.set_arrow_width)
        tools_panel.addWidget(QLabel("Arrow Width"))
        tools_panel.addWidget(self.width_spin)
        
        # Style group
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
        
        tools_panel.addStretch(1)
        
        return tools_panel
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        pitch_width = self.pitch_widget.width()
        # Optionnel : laisse un peu de marge si besoin (ex: -40)
        self.timeline_widget.setMaximumWidth(pitch_width)


    def _setup_managers(self):
        """Initialise les managers"""
        self.trajectory_manager = TrajectoryManager(self.pitch_widget)
        self.annotation_manager = ArrowAnnotationManager(self.pitch_widget.scene)
        self.set_tool_mode("select")
    
    def _connect_signals(self):
        """Connecte tous les signaux"""
        self.play_button.clicked.connect(self.toggle_play_pause)
        self.speed_box.currentIndexChanged.connect(self.update_speed)
        
        # Event filters
        self.installEventFilter(self)
        self.pitch_widget.view.viewport().installEventFilter(self)
        self.pitch_widget.view.viewport().setFocusPolicy(Qt.StrongFocus)
        self.pitch_widget.view.viewport().setFocus()
    
    def _on_filter_update(self):
        """Callback pour mise à jour des filtres"""
        active_actions = self.action_filter.get_filtered_actions()
        active_types = self.action_filter.get_active_types()
        self.timeline_widget.set_filtered_types(active_types)


    def toggle_simulation_mode(self):
        """Active/désactive le mode simulation"""
        self.simulation_mode = self.simulation_button.isChecked()
        if self.simulation_mode:
            self._pause_match()
            # Calculer trajectoires futures
            self.trajectory_manager.calculate_future_trajectories(
                self.timeline_widget.value(),
                self.sim_interval_spin.value(),
                xy_objects,
                home_ids,
                away_ids,
                n_frames,
                self.frame_manager.get_frame_data
            )
        else:
            self.trajectory_manager.clear_trails()
        self.update_scene(self.timeline_widget.value())
    
    def update_simulation_interval(self, value):
        """Met à jour l'intervalle de simulation"""
        if self.simulation_mode:
            self.toggle_simulation_mode()
    
    def update_scene(self, frame_number):
        """Met à jour la scène"""
        self.pitch_widget.clear_dynamic()
        self.pitch_widget.draw_pitch()
        
        half, idx, halftime = self.frame_manager.get_frame_data(frame_number)
        
        # Mode simulation : trajectoires futures
        if self.simulation_mode and self.show_trajectories_checkbox.isChecked():
            self.trajectory_manager.draw_future_trajectories()
        
        # Dessiner les joueurs
        self._draw_players(half, idx)
        
        # Balle
        ball_xy = xy_objects[half]["Ball"].xy[idx]
        self.pitch_widget.draw_ball(ball_xy[0], ball_xy[1])
        
        # Offside
        possession_team = PossessionTracker.get_possession_for_frame(possession, half, idx)
        offside_x = get_offside_line_x(xy_objects, half, idx, possession_team, 
                                       home_ids, away_ids, teams_df, last_positions)
        self.pitch_widget.draw_offside_line(offside_x, visible=self.offside_checkbox.isChecked())
        
        # Info
        match_time = format_match_time(frame_number, n_frames_firstHalf, 
                                      n_frames_secondHalf, 0, 0, fps=FPS)
        self.info_label.setText(f"{halftime} \n{match_time}  \nFrame {get_frame_data(frame_number)[1]}")

    def _draw_players(self, half, idx):
        """Dessine tous les joueurs"""
        for side, ids, colors in [("Home", home_ids, home_colors), 
                                 ("Away", away_ids, away_colors)]:
            xy = xy_objects[half][side].xy[idx]
            for i, pid in enumerate(ids):
                try:
                    x, y = xy[2*i], xy[2*i+1]
                    if not np.isnan(x) and not np.isnan(y):
                        main, sec, numc = colors[pid]
                        num = id2num.get(pid, "")
                        self.pitch_widget.draw_player(
                            x=x, y=y, 
                            main_color=main, sec_color=sec, num_color=numc, 
                            number=num,
                            angle=player_orientations[pid][self.timeline_widget.value()],
                            velocity=dsam[side][pid][half]['S'][idx],
                            display_orientation=self.orientation_checkbox.isChecked(),
                            z_offset=(10 if side == "Home" else 50) + i
                        )
                except IndexError:
                    continue
    
    # Méthodes pour les contrôles
    def jump_frames(self, n):
        new_frame = np.clip(self.timeline_widget.value() + n, 0, n_frames-1)
        self.timeline_widget.setValue(new_frame)
    
    def toggle_play_pause(self):
        if self.is_playing:
            self.play_button.setIcon(self.play_icon)
            self.timer.stop()
        else:
            self.play_button.setIcon(self.pause_icon)
            self.timer.start()
        self.is_playing = not self.is_playing

    def update_speed(self, idx):
        intervals = [160, 80, 40, 20, 10, 2, 1]
        self.timer.setInterval(intervals[idx])
    
    def next_frame(self):
        next_frame = min(self.timeline_widget.value() + self.frame_step, n_frames-1)
        self.timeline_widget.setValue(next_frame)
        if next_frame == n_frames-1:
            self.toggle_play_pause()
    
    def _pause_match(self):
        if self.is_playing:
            self.toggle_play_pause()
    
    # Méthodes pour les annotations
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
        self.pitch_widget.view.viewport().setFocus()
    
    def set_arrow_width(self, value):
        self.annotation_manager.set_width(value)
    
    def change_line_style(self, button):
        styles = {0: "solid", 1: "dotted", 2: "zigzag"}
        style = styles.get(self.style_buttons.id(button), "solid")
        self.annotation_manager.set_style(style)
    
    def choose_arrow_color(self):
        color = QColorDialog.getColor(QColor(self.annotation_manager.arrow_color))
        if color.isValid():
            self.annotation_manager.set_color(color.name())
    
    def delete_last_arrow(self):
        self.annotation_manager.delete_last_arrow()
    
    # Event handling
    def keyPressEvent(self, event):
        if self.current_tool != "select":
            self.annotation_manager.try_finish_arrow()
            self.set_tool_mode("select")
            return
        super().keyPressEvent(event)
    
    def eventFilter(self, obj, event):
        if obj != self.pitch_widget.view.viewport():
            return False
        
        if self.current_tool == "select":
            return False
        
        if event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                scene_pos = self.pitch_widget.view.mapToScene(event.pos())
                self.annotation_manager.add_point(scene_pos)
                
                if not self.annotation_manager.arrow_curved and len(self.annotation_manager.arrow_points) == 2:
                    self.annotation_manager.finish_arrow()
                    self.set_tool_mode("select")
            elif event.button() == Qt.RightButton:
                if len(self.annotation_manager.arrow_points) < 2:
                    self.annotation_manager.cancel_arrow()
                    self.set_tool_mode("select")
            return True
        
        elif event.type() == QEvent.MouseMove and self.annotation_manager.arrow_points:
            scene_pos = self.pitch_widget.view.mapToScene(event.pos())
            self.annotation_manager.update_preview(scene_pos)
            return True
        
        return False


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Thème sombre moderne (plusieurs thèmes possibles)
    apply_stylesheet(app, theme='dark_blue.xml', invert_secondary=False)  # Ou 'light_blue.xml', 'dark_amber.xml', etc.
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())