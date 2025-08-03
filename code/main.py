# main.py - Version corrigée avec données joueurs complètes

import os
import sys
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSlider, QPushButton,
    QLabel, QComboBox, QCheckBox, QColorDialog, QSpinBox, QButtonGroup,
    QRadioButton, QGroupBox, QDoubleSpinBox, QToolButton, QMenu, QAction
)
from PyQt5.QtCore import Qt, QTimer, QEvent, QDir, QSize, QRectF
from PyQt5.QtGui import QColor, QIcon, QFont

# Imports locaux
from pitch_widget import PitchWidget
from annotation_tools import ArrowAnnotationManager
from arrow_context_menu import ArrowContextMenu
from data_processing import load_data, build_player_out_frames, extract_match_actions_from_events, format_match_time, compute_dynamic_pressing
from trajectory_manager import TrajectoryManager
from ui_components import ActionFilterBar, MatchActionsDialog, create_nav_button
from frame_utils import FrameManager, PossessionTracker
from custom_slider import TimelineWidget
from score_manager import ScoreManager
from tactical_simulation import TacticalSimulationManager
from camera.camera_manager import CameraManager  
from camera.camera_controls import CameraControlWidget
from config import *

from qt_material import apply_stylesheet


# ======= CHARGEMENT CENTRALISÉ =======
data = load_data(
    DATA_PATH,
    FILE_NAME_POS,
    FILE_NAME_INFOS,
    FILE_NAME_EVENTS,
)

xy_objects         = data['xy_objects']
possession         = data['possession']
ballstatus         = data['ballstatus']
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
ball_carrier_array = data['ball_carrier_array']
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
        self.tactical_manager = None  # Gestionnaire de simulation tactique
        self.score_manager = ScoreManager(events, home_team_name, away_team_name, n_frames_firstHalf, FPS)
        self.camera_manager = None  # Initialisé après pitch_widget
        
        # Menu contextuel pour flèches
        self.arrow_context_menu = None
        
        # État
        self.simulation_mode = False
        self.is_playing = False
        self.frame_step = 1
        self.current_tool = "select"
        self.simulation_start_frame = 0
        self.simulation_end_frame = 0
        self.simulation_loop_active = False

        # Actions
        self.actions_data = extract_match_actions_from_events(events, FPS, n_frames_firstHalf)
        
        self._setup_ui()
        self._setup_managers()
        self._connect_signals()


        self.update_scene(0)
        QTimer.singleShot(1, lambda: self.camera_manager.set_camera_mode("full", animate=False))



    def _setup_ui(self):
        """Configure l'interface utilisateur"""
        main_layout = QHBoxLayout(self)
        
        # Panel gauche
        left_panel = QVBoxLayout()
        # === NOUVEAU : Container pour la partie gauche avec taille fixe ===
        left_container = QWidget()
        left_container.setFixedWidth(LEFT_PANEL_SIZE)  # ← TAILLE FIXE (ajustez selon vos besoins)
        left_container.setLayout(left_panel)
        # Zone de score en haut
        score_layout = QHBoxLayout()
        
        # Score display
        self.score_label = QLabel()
        self.score_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._update_score_display(0)
        
        score_layout.addWidget(self.score_label)
        score_layout.addStretch()
        
        left_panel.addLayout(score_layout)
        
        # Pitch
        self.pitch_widget = PitchWidget(X_MIN, X_MAX, Y_MIN, Y_MAX)
        left_panel.addWidget(self.pitch_widget)
        
        # Barre de filtrage des actions
        self.action_filter = ActionFilterBar(self.actions_data, self._on_filter_update)
        left_panel.addLayout(self.action_filter.layout)
        
        # Timeline et contrôles
        self._create_timeline_controls(left_panel)
        
        # Panel droit (outils) - SIMPLIFIÉ
        tools_panel = self._create_tools_panel()

        
        main_layout.addWidget(left_container)
        main_layout.addLayout(tools_panel)
    
    def _update_score_display(self, frame):
        """Met à jour l'affichage du score"""
        home_score, away_score = self.score_manager.get_score_at_frame(frame)
        
        # Récupérer les couleurs des équipes
        home_color = "#333333"
        away_color = "#333333"
        
        if home_ids and home_ids[0] in home_colors:
            home_color = home_colors[home_ids[0]][0]
        
        if away_ids and away_ids[0] in away_colors:
            away_color = away_colors[away_ids[0]][0]
        
        # Logique d'adaptation du fond
        def is_light_color(hex_color):
            if not hex_color.startswith('#'):
                hex_color = '#' + hex_color
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16) 
            b = int(hex_color[5:7], 16)
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            return luminance > 0.7
        
        def is_dark_color(hex_color):
            if not hex_color.startswith('#'):
                hex_color = '#' + hex_color
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16) 
            b = int(hex_color[5:7], 16)
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            return luminance < 0.3
        
        home_is_white = is_light_color(home_color)
        away_is_white = is_light_color(away_color)
        home_is_black = is_dark_color(home_color)
        away_is_black = is_dark_color(away_color)
        
        if home_is_white or away_is_white:
            background_color = "#000000"
            score_color = "#ffffff"
        elif home_is_black or away_is_black:
            background_color = "#ffffff" 
            score_color = "#000000"
        else:
            background_color = "#ffffff"
            score_color = "#000000"
        
        score_html = f"""
        <span style="color: {home_color}; font-weight: bold;">{home_team_name}</span>
        <span style="color: {score_color}; font-weight: bold;"> {home_score} - {away_score} </span>
        <span style="color: {away_color}; font-weight: bold;">{away_team_name}</span>
        """
        
        self.score_label.setStyleSheet(f"""
            QLabel {{
                font-size: 20px;
                font-family: Arial;
                font-weight: bold;
                background: {background_color};
                padding: 6px 12px;
                border-radius: 6px;
                margin: 5px;
            }}
        """)
        
        self.score_label.setText(score_html)
    
    def _create_timeline_controls(self, parent_layout):
        """Crée les contrôles de timeline"""
        control_layout = QHBoxLayout()
        nav_layout = QHBoxLayout()
        nav_layout.addWidget(create_nav_button("< 1m", NAV_BUTTON_WIDTH, NAV_BUTTON_HEIGHT, -60 * FPS, "Back 1 minute", self.jump_frames))
        nav_layout.addWidget(create_nav_button("< 5s", NAV_BUTTON_WIDTH, NAV_BUTTON_HEIGHT, -5 * FPS, "Back 5 seconds", self.jump_frames))
        
        self.timeline_widget = TimelineWidget(n_frames, n_frames_firstHalf, n_frames_secondHalf)
        self.timeline_widget.frameChanged.connect(self.update_scene)
        self.timeline_widget.set_actions(self.actions_data)
        nav_layout.addWidget(self.timeline_widget)
        nav_layout.addWidget(create_nav_button("5s >", NAV_BUTTON_WIDTH, NAV_BUTTON_HEIGHT, 5 * FPS, "Forward 5 seconds", self.jump_frames))
        nav_layout.addWidget(create_nav_button("1m >", NAV_BUTTON_WIDTH, NAV_BUTTON_HEIGHT, 60 * FPS, "Forward 1 minute", self.jump_frames))

        control_layout.addLayout(nav_layout)

        # Speed control
        self.speed_box = QComboBox()
        self.speed_box.setMinimumWidth(80)
        self.speed_box.setMaximumWidth(80)
        for label, _ in [("x0.25", 160), ("x0.5", 80), ("x1", 40), ("x2", 20), ("x4", 10), ("x16", 5)]:
            self.speed_box.addItem(label)
        self.speed_box.setCurrentIndex(2)

        speed_widget = QWidget()
        speed_layout = QHBoxLayout(speed_widget)

        label_speed = QLabel("Speed")
        label_speed.setFixedWidth(label_speed.sizeHint().width())

        speed_layout.addWidget(label_speed)
        speed_layout.addWidget(self.speed_box)
        control_layout.addWidget(speed_widget)



        
        # Play/pause button
        self.play_icon = QIcon(os.path.join(SVG_DIR, "play.svg"))
        self.pause_icon = QIcon(os.path.join(SVG_DIR, "pause.svg"))

        self.play_button = QToolButton()
        self.play_button.setFixedWidth(60)
        self.play_button.setFixedHeight(60)
        self.play_button.setIcon(self.play_icon)
        self.play_button.setIconSize(QSize(24, 24))
        self.play_button.setText("")
        self.play_button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        
        self.play_button.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: none;
                font-size: 9px;
                font-weight: bold;
                color: #888;
                padding-top: 10px;
                padding-bottom: 2px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
            QToolButton:pressed {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
        control_layout.addWidget(self.play_button)

        # Checkboxes
        # === Visual overlays button with menu ===
        self.visual_overlays_button = QToolButton()
        self.visual_overlays_button.setText("Visual overlays")
        self.visual_overlays_button.setPopupMode(QToolButton.InstantPopup)
        self.visual_overlays_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.visual_overlays_button.setStyleSheet("""
        QToolButton {
            font-size: 12px;
            padding: 3px 6px;
            border: 1px solid #888;
            border-radius: 4px;
        }
        """)

        # Menu with checkable actions
        overlays_menu = QMenu(self.visual_overlays_button)

        # Orientation
        self.orientation_action = QAction("Orientation", self, checkable=True)
        self.orientation_action.setChecked(True)
        overlays_menu.addAction(self.orientation_action)

        # Offside
        self.offside_action = QAction("Offside", self, checkable=True)
        self.offside_action.setChecked(True)
        overlays_menu.addAction(self.offside_action)

        # Pressure zone
        self.pressure_zone_action = QAction("Pressure zone (Ball Carrier)", self, checkable=True)
        self.pressure_zone_action.setChecked(True)
        overlays_menu.addAction(self.pressure_zone_action)

        self.visual_overlays_button.setMenu(overlays_menu)
        control_layout.addWidget(self.visual_overlays_button)
        
        self.orientation_action.toggled.connect(lambda _: self.update_scene(self.timeline_widget.value()))
        self.offside_action.toggled.connect(lambda _: self.update_scene(self.timeline_widget.value()))
        self.pressure_zone_action.toggled.connect(lambda _: self.update_scene(self.timeline_widget.value()))

        # Info label
        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setFixedWidth(100)
        control_layout.addWidget(self.info_label)
        
        parent_layout.addLayout(control_layout)
        
        # Timer
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.next_frame)
    
    def _create_tools_panel(self):
        """Crée le panneau d'outils SIMPLIFIÉ"""
        tools_panel = QVBoxLayout()
        
        # Simulation mode
        tools_panel.addWidget(QLabel("Simulation"))
        self.simulation_button = QPushButton("Simulation Mode")
        self.simulation_button.setCheckable(True)
        self.simulation_button.clicked.connect(self.toggle_simulation_mode)
        tools_panel.addWidget(self.simulation_button)
        
        self.sim_interval_spin = QDoubleSpinBox()
        self.sim_interval_spin.setRange(1.0, 30.0)
        self.sim_interval_spin.setValue(10.0)
        self.sim_interval_spin.setSuffix(" sec")
        self.sim_interval_spin.setSingleStep(0.5)
        self.sim_interval_spin.valueChanged.connect(self.update_simulation_interval)
        tools_panel.addWidget(QLabel("Future interval:"))
        tools_panel.addWidget(self.sim_interval_spin)
        
        # Affichage des temps de loop
        self.loop_times_label = QLabel("")
        self.loop_times_label.setWordWrap(True)
        self.loop_times_label.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: bold;")
        tools_panel.addWidget(self.loop_times_label)
        
        self.show_trajectories_checkbox = QCheckBox("Show trajectories")
        self.show_trajectories_checkbox.setChecked(True)
        self.show_trajectories_checkbox.stateChanged.connect(lambda: self.update_scene(self.timeline_widget.value()))
        tools_panel.addWidget(self.show_trajectories_checkbox)

        self.simulation_info = QLabel("Click Play to loop the selected interval")
        self.simulation_info.setWordWrap(True)
        self.simulation_info.setStyleSheet("color: #888; font-size: 10px;")
        tools_panel.addWidget(self.simulation_info)
        
        # Annotation tools - SIMPLIFIÉ
        tools_panel.addWidget(QLabel("────────────────"))
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
        
        tools_panel.addStretch(1)
        
        return tools_panel
    
    def resizeEvent(self, event):
        super().resizeEvent(event)





    def _setup_managers(self):
        """Initialise les managers"""
        self.trajectory_manager = TrajectoryManager(self.pitch_widget, home_colors, away_colors)
        self.annotation_manager = ArrowAnnotationManager(self.pitch_widget.scene)
        self.tactical_manager = TacticalSimulationManager(
            self.annotation_manager, self.pitch_widget, 
            home_ids, away_ids, home_colors, away_colors
        )
        self.camera_manager = CameraManager(self.pitch_widget)
        self.camera_control_widget = CameraControlWidget(self.camera_manager, self)
        # Intégrer le widget caméra dans le panneau d'outils
        tools_layout = self.layout().itemAt(1).layout()  # Panel droit
        tools_layout.insertWidget(0, self.camera_control_widget)
        tools_layout.insertWidget(1, QLabel("────────────────"))


        # Menu contextuel pour flèches
        self.arrow_context_menu = ArrowContextMenu(self)
        self._setup_arrow_context_menu()
        
        self.set_tool_mode("select")
    
    def _setup_arrow_context_menu(self):
        """Configure le menu contextuel des flèches"""
        # Préparer les données des joueurs avec TOUTES les couleurs
        home_players = {}
        away_players = {}
        
        for player_id in home_ids:
            number = id2num.get(player_id, "?")
            colors = home_colors.get(player_id, ["#FF0000", "#FFFFFF", "#000000"])
            main_color = colors[0]
            sec_color = colors[1] if len(colors) > 1 else colors[0]
            num_color = colors[2] if len(colors) > 2 else "#000000"
            home_players[player_id] = (number, main_color, sec_color, num_color)
        
        for player_id in away_ids:
            number = id2num.get(player_id, "?")
            colors = away_colors.get(player_id, ["#0000FF", "#FFFFFF", "#000000"])
            main_color = colors[0]
            sec_color = colors[1] if len(colors) > 1 else colors[0]
            num_color = colors[2] if len(colors) > 2 else "#000000"
            away_players[player_id] = (number, main_color, sec_color, num_color)
        
        self.arrow_context_menu.set_players_data(home_players, away_players)
        
        # Connecter les signaux
        self.arrow_context_menu.fromPlayerSelected.connect(self._on_from_player_selected)
        self.arrow_context_menu.toPlayerSelected.connect(self._on_to_player_selected)
        self.arrow_context_menu.deleteRequested.connect(self._on_arrow_delete_requested)
        self.arrow_context_menu.propertiesConfirmed.connect(self._on_arrow_properties_confirmed)
    
    def _connect_signals(self):
        """Connecte tous les signaux"""
        self.play_button.clicked.connect(self.toggle_play_pause)
        self.speed_box.currentIndexChanged.connect(self.update_speed)
        # === NOUVEAUX : Signaux caméra ===
        self.camera_control_widget.modeChanged.connect(self._on_camera_mode_changed)
        self.camera_control_widget.zoomInRequested.connect(self._on_zoom_in)
        self.camera_control_widget.zoomOutRequested.connect(self._on_zoom_out)
        self.camera_control_widget.resetZoomRequested.connect(self._on_reset_zoom)

        
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
            current_frame = self.timeline_widget.value()
            interval_frames = int(self.sim_interval_spin.value() * FPS)
            
            self.simulation_start_frame = current_frame
            self.simulation_end_frame = min(current_frame + interval_frames, n_frames - 1)
            self.simulation_loop_active = False
            
            self.annotation_manager.set_tactical_mode(True)
            self._update_loop_times_display()
            self.play_button.setText("▶ Loop")
        else:
            self.trajectory_manager.clear_trails()
            self.simulation_loop_active = False
            self.play_button.setText("")
            self.loop_times_label.setText("")
            
            self.annotation_manager.set_tactical_mode(False)
            self.tactical_manager.clear_tactical_data()
            
        self.update_scene(self.timeline_widget.value())

    def _update_loop_times_display(self):
        """Met à jour l'affichage des temps de début/fin de loop"""
        start_time = format_match_time(self.simulation_start_frame, n_frames_firstHalf, n_frames_secondHalf, 0, 0, fps=FPS)
        end_time = format_match_time(self.simulation_end_frame, n_frames_firstHalf, n_frames_secondHalf, 0, 0, fps=FPS)
        self.loop_times_label.setText(f"Loop: {start_time} → {end_time}")

    def update_simulation_interval(self, value):
        """Met à jour l'intervalle de simulation et recalcule les limites"""
        if self.simulation_mode:
            current_frame = self.simulation_start_frame
            interval_frames = int(value * FPS)
            self.simulation_end_frame = min(current_frame + interval_frames, n_frames - 1)
            
            self._update_loop_times_display()
            
            if not self.is_playing:
                self.update_scene(self.timeline_widget.value())

    def update_scene(self, frame_number):
        """Met à jour la scène"""
        self._update_score_display(frame_number)
        
        if (self.simulation_mode and 
            not self.is_playing and 
            abs(frame_number - self.simulation_start_frame) > 5):
            
            interval_frames = int(self.sim_interval_spin.value() * FPS)
            self.simulation_start_frame = frame_number
            self.simulation_end_frame = min(frame_number + interval_frames, n_frames - 1)
            self.simulation_loop_active = False
            self._update_loop_times_display()
        
        self.pitch_widget.clear_dynamic()
        self.pitch_widget.draw_pitch()
        
        half, idx, halftime = self.frame_manager.get_frame_data(frame_number)
        
        # Mode simulation : trajectoires futures
        if self.simulation_mode and self.show_trajectories_checkbox.isChecked():
            if self.tactical_manager.tactical_arrows:
                self.tactical_manager.calculate_simulated_trajectories(
                    self.sim_interval_spin.value(),
                    self.simulation_start_frame,
                    xy_objects,
                    n_frames,
                    self.frame_manager.get_frame_data
                )
                
                simulated_data = self.tactical_manager.get_simulated_trajectories()
                self.trajectory_manager.draw_simulated_trajectories(
                    simulated_data, frame_number, self.simulation_start_frame, self.simulation_end_frame
                )
            else:
                self.trajectory_manager.calculate_future_trajectories(
                    self.simulation_start_frame,
                    self.sim_interval_spin.value(),
                    xy_objects,
                    home_ids,
                    away_ids,
                    n_frames,
                    self.frame_manager.get_frame_data
                )
                self.trajectory_manager.draw_future_trajectories(
                    current_frame=frame_number,
                    loop_start=self.simulation_start_frame,
                    loop_end=self.simulation_end_frame
                )
        
        # Dessiner les joueurs
        self._draw_players(half, idx)
        
        # Balle
        ball_xy = xy_objects[half]["Ball"].xy[idx]
        ball_x, ball_y = ball_xy[0], ball_xy[1]
        self.pitch_widget.draw_ball(ball_x, ball_y)
        
        # === NOUVEAU : Mettre à jour la position de la balle dans le gestionnaire de caméra ===
        self.camera_manager.update_ball_position(ball_x, ball_y)
        
        # Offside
        possession_team = PossessionTracker.get_possession_for_frame(possession, half, idx)
        offside_x = get_offside_line_x(xy_objects, half, idx, possession_team, 
                                    home_ids, away_ids, teams_df, last_positions)
        self.pitch_widget.draw_offside_line(offside_x, visible=self.offside_action.isChecked())
        # Pressing zone
        self.pitch_widget.draw_pressure_zone_for_ball_carrier(xy_objects, home_ids,
                                        away_ids, dsam, player_orientations, half, idx, ball_xy,
                                        compute_dynamic_pressing, ball_carrier_array, ballstatus=ballstatus, frame_number=frame_number,
                                        visible=self.pressure_zone_action.isChecked()
        )

    
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
                            display_orientation=self.orientation_action.isChecked(),
                            z_offset=(10 if side == "Home" else 50) + i
                        )
                except IndexError:
                    continue
    
    def jump_frames(self, n):
        """Navigation avec gestion simulation"""
        if self.simulation_mode and self.is_playing:
            return
            
        new_frame = np.clip(self.timeline_widget.value() + n, 0, n_frames-1)
        self.timeline_widget.setValue(new_frame)
        
        if self.simulation_mode:
            interval_frames = int(self.sim_interval_spin.value() * FPS)
            self.simulation_start_frame = new_frame
            self.simulation_end_frame = min(new_frame + interval_frames, n_frames - 1)
            self.simulation_loop_active = False
            self._update_loop_times_display()

    def toggle_play_pause(self):
        """Play/pause avec gestion spéciale pour simulation"""
        if self.is_playing:
            self.play_button.setIcon(self.play_icon)
            if self.simulation_mode:
                self.play_button.setText("▶ Loop")
            else:
                self.play_button.setText("")
            self.timer.stop()
        else:
            self.play_button.setIcon(self.pause_icon)
            if self.simulation_mode:
                self.simulation_loop_active = True
                self.play_button.setText("⏸ Loop")
            else:
                self.play_button.setText("")
            self.timer.start()
        self.is_playing = not self.is_playing

    def update_speed(self, idx):
        intervals = [160, 80, 40, 20, 10, 5]
        self.timer.setInterval(intervals[idx])

    def next_frame(self):
        """Gestion des frames avec système de loop en simulation"""
        current_frame = self.timeline_widget.value()
        
        if self.simulation_mode and self.simulation_loop_active:
            if current_frame >= self.simulation_end_frame:
                self.toggle_play_pause()
                next_frame = self.simulation_start_frame
            else:
                next_frame = min(current_frame + self.frame_step, self.simulation_end_frame)
        else:
            next_frame = min(current_frame + self.frame_step, n_frames - 1)
            
            if next_frame == n_frames - 1:
                self.toggle_play_pause()
        
        self.timeline_widget.setValue(next_frame)

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
    
    # Méthodes pour le menu contextuel des flèches
    def _on_from_player_selected(self, player_id):
        """Joueur FROM sélectionné"""
        if self.arrow_context_menu.current_arrow:
            current_frame = self.timeline_widget.value()
            result = self.tactical_manager.associate_arrow_with_player(
                self.arrow_context_menu.current_arrow, player_id, current_frame, xy_objects
            )
    
    def _on_to_player_selected(self, player_id):
        """Joueur TO sélectionné (receveur)"""
        success = self.tactical_manager.set_pass_receiver(player_id)

    
    def _on_arrow_color_changed(self, color):
        """Couleur de flèche changée"""
        if self.arrow_context_menu.current_arrow:
            self.annotation_manager.selected_arrow = self.arrow_context_menu.current_arrow
            self.annotation_manager.set_color(color)
    
    def _on_arrow_width_changed(self, width):
        """Largeur de flèche changée"""
        if self.arrow_context_menu.current_arrow:
            self.annotation_manager.selected_arrow = self.arrow_context_menu.current_arrow
            self.annotation_manager.set_width(width)
    
    def _on_arrow_style_changed(self, style):
        """Style de flèche changé"""
        if self.arrow_context_menu.current_arrow:
            self.annotation_manager.selected_arrow = self.arrow_context_menu.current_arrow
            self.annotation_manager.set_style(style)
            # Mettre à jour le style stocké dans la nouvelle flèche
            if self.annotation_manager.selected_arrow:
                self.annotation_manager.selected_arrow.arrow_style = style
                # Mettre à jour la référence dans le menu contextuel
                self.arrow_context_menu.current_arrow = self.annotation_manager.selected_arrow
    
    def _on_arrow_delete_requested(self):
        """Suppression de flèche demandée"""
        if self.arrow_context_menu.current_arrow:
            arrow = self.arrow_context_menu.current_arrow
            # Supprimer de la liste des flèches
            if arrow in self.annotation_manager.arrows:
                self.annotation_manager.arrows.remove(arrow)
            # Supprimer de la scène
            try:
                self.pitch_widget.scene.removeItem(arrow)
            except RuntimeError:
                pass
            # Supprimer l'association tactique si elle existe
            self.tactical_manager.remove_arrow_association(arrow)
            # Nettoyer la sélection
            self.annotation_manager.clear_selection()
        self.arrow_context_menu.close()
    
    # === NOUVEAUX : Gestionnaires d'événements caméra ===
    def _on_camera_mode_changed(self, mode):
        """Gestionnaire pour changement de mode caméra"""
        success = self.camera_manager.set_camera_mode(mode, animate=True)
        if success:
            # Mettre à jour le statut de suivi de balle
            is_following = (mode == "ball")
            self.camera_control_widget.update_ball_status(is_following)
    
    def _on_zoom_in(self):
        """Gestionnaire pour zoom avant"""
        self.camera_manager.zoom_in(1.2)
    
    def _on_zoom_out(self):
        """Gestionnaire pour zoom arrière"""
        self.camera_manager.zoom_out(0.83)
    
    def _on_reset_zoom(self):
        """Gestionnaire pour reset du zoom"""
        self.camera_manager.reset_zoom()
        # AJOUTER CETTE LIGNE :
        self.camera_control_widget.set_mode("full")

    
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
            # En mode sélection, gérer les clics sur les flèches pour ouvrir le menu
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                scene_pos = self.pitch_widget.view.mapToScene(event.pos())
                clicked_arrow = self._find_arrow_at_position(scene_pos)
                if clicked_arrow:
                    # Sélectionner la flèche dans le manager
                    self.annotation_manager.select_arrow(clicked_arrow)
                    
                    # Ouvrir le menu contextuel
                    global_pos = self.pitch_widget.view.mapToGlobal(event.pos())
                    # Ajuster la position pour éviter que le menu sorte de l'écran
                    screen_geometry = QApplication.desktop().screenGeometry()
                    if global_pos.x() + 300 > screen_geometry.width():
                        global_pos.setX(global_pos.x() - 300)
                    if global_pos.y() + 500 > screen_geometry.height():
                        global_pos.setY(global_pos.y() - 500)
                    
                    self.arrow_context_menu.show_for_arrow(clicked_arrow, global_pos)
                    return True
                else:
                    # Clic sur une zone vide - désélectionner
                    self.annotation_manager.clear_selection()
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
    
    def _find_arrow_at_position(self, scene_pos):
        """Trouve une flèche à la position donnée"""
        # Rechercher dans les items de la scène avec une zone de tolérance
        tolerance = 5.0  # Pixels de tolérance
        search_rect = QRectF(scene_pos.x() - tolerance, scene_pos.y() - tolerance, 
                           tolerance * 2, tolerance * 2)
        items = self.pitch_widget.scene.items(search_rect)
        
        for item in items:
            # Vérifier si l'item est une flèche ou fait partie d'une flèche
            parent = item
            while parent:
                if parent in self.annotation_manager.arrows:
                    return parent
                parent = parent.parentItem()
        
        return None


    def _on_arrow_properties_confirmed(self):
            """Confirmation des propriétés de flèche"""
            # Le menu se fermera automatiquement
            pass
    



if __name__ == '__main__':
    app = QApplication(sys.argv)
    apply_stylesheet(app, theme='dark_blue.xml', invert_secondary=False)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())