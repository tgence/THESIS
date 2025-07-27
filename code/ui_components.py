# ui_components.py

from PyQt5.QtWidgets import (
    QPushButton, QHBoxLayout, QVBoxLayout, QLabel, 
    QDialog, QListWidget, QListWidgetItem, QCheckBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont

class ActionFilterBar:
    """Barre de filtrage des actions au-dessus de la timeline"""
    
    def __init__(self, actions_data, update_callback):
        self.actions_data = actions_data
        self.update_callback = update_callback
        self.action_buttons = {}
        self.layout = QHBoxLayout()
        
        self._create_buttons()
        
    def _create_buttons(self):
        self.layout.addWidget(QLabel("Actions:"))
        
        # Grouper par type
        action_types = {}
        for act in self.actions_data:
            label = act['label']
            if label not in action_types:
                action_types[label] = []
            action_types[label].append(act)
        
        # Créer boutons
        for action_type, actions in action_types.items():
            emoji = actions[0]['emoji']
            btn = QPushButton(f"{emoji} {action_type} ({len(actions)})")
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.clicked.connect(self.update_callback)
            self.action_buttons[action_type] = btn
            self.layout.addWidget(btn)
        
        self.layout.addStretch()
        
        # Toggle all
        toggle_all = QPushButton("All")
        toggle_all.clicked.connect(self.toggle_all)
        self.layout.addWidget(toggle_all)
    
    def toggle_all(self):
        all_checked = all(btn.isChecked() for btn in self.action_buttons.values())
        for btn in self.action_buttons.values():
            btn.setChecked(not all_checked)
        self.update_callback()
    
    def get_active_types(self):
        return [t for t, btn in self.action_buttons.items() if btn.isChecked()]
    
    def get_filtered_actions(self):
        active_types = self.get_active_types()
        return [a for a in self.actions_data if a['label'] in active_types]


class MatchActionsDialog(QDialog):
    """Dialog amélioré pour afficher les actions du match"""
    
    def __init__(self, parent, actions, home_team_name, goto_callback):
        super().__init__(parent)
        self.actions = actions
        self.home_team_name = home_team_name
        self.goto_callback = goto_callback
        
        self.setWindowTitle("Match Actions")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Liste des actions
        self.list_widget = QListWidget()
        self.populate_list()
        
        # Checkbox auto-timeline
        self.auto_timeline = QCheckBox("Activate Timeline mode on selection")
        self.auto_timeline.setChecked(True)
        
        layout.addWidget(self.list_widget)
        layout.addWidget(self.auto_timeline)
        
        # Connecter signal
        self.list_widget.itemClicked.connect(self._on_item_clicked)
    
    def populate_list(self):
        for act in self.actions:
            display_text = f"{act['emoji']} {act['label']} - {act['display_time']} ({act['team']})"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, act['frame'])
            item.setData(Qt.UserRole + 1, act)        
            self.list_widget.addItem(item)
    
    def _on_item_clicked(self, item):
        frame = item.data(Qt.UserRole)
        activate_timeline = self.auto_timeline.isChecked()
        self.goto_callback(frame, activate_timeline)


def create_nav_button(label, width, height, frames, tooltip, callback):
    """Crée un bouton de navigation standardisé"""
    btn = QPushButton(label)
    btn.setFixedWidth(width)
    btn.setFixedHeight(height)
    btn.setToolTip(tooltip)
    btn.clicked.connect(lambda: callback(frames))
    btn.setStyleSheet(f"font-size: {width//3}pt; font-family: Arial; padding: 1px 1px;")
    return btn