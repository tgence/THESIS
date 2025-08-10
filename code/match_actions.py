"""
UI components for selecting and filtering match actions.

Provides:
- `ActionFilterBar`: top-of-timeline filter and selection of action types
- `ActionSelectionDialog`: modal dialog to choose up to N action types
- `MatchActionsDialog`: list of actions with click-to-jump behavior
- `create_nav_button`: helper for standardized navigation buttons
"""
# match_actions.py

from PyQt5.QtWidgets import (
    QPushButton, QHBoxLayout, QVBoxLayout, QLabel, 
    QDialog, QListWidget, QListWidgetItem, QCheckBox,
    QComboBox, QScrollArea, QFrame, QMessageBox, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont

class ActionFilterBar:
    """Filter bar to pick action types and toggle their visibility on timeline."""
    
    def __init__(self, actions_data, update_callback):
        self.actions_data = actions_data
        self.update_callback = update_callback
        self.action_buttons = {}
        self.layout = QHBoxLayout()
        self.available_types = {}
        self.selected_action_types = []  # None selected by default
        self.active_button_states = {}  # Remember button states
        
        self._analyze_actions()
        self._create_ui()
        
    def _analyze_actions(self):
        """Scan actions and build the set of available types with counts."""
        for act in self.actions_data:
            label = act['label']
            if label not in self.available_types:
                self.available_types[label] = {
                    'emoji': act['emoji'],
                    'count': 0
                }
            self.available_types[label]['count'] += 1
    
    def _create_ui(self):
        self.layout.addWidget(QLabel("Actions:"))
        
        # Button to open action type selection
        self.select_button = QPushButton("Select Action Types")
        self.select_button.clicked.connect(self.open_selection_dialog)
        self.layout.addWidget(self.select_button)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        self.layout.addWidget(separator)
        
        # Placeholder to insert action buttons after the separator
        self.buttons_start_index = self.layout.count()
        
        self.layout.addStretch()
        
        # "All" button – present but disabled until some types are selected
        self.all_button = QPushButton("All")
        self.all_button.setCheckable(True)
        self.all_button.setChecked(False)
        self.all_button.setEnabled(False)  # Disabled until some types are selected
        self.all_button.clicked.connect(self.toggle_all)
        self.layout.addWidget(self.all_button)
    
    def open_selection_dialog(self):
        dialog = ActionSelectionDialog(self.select_button.parent(), self.available_types)
        
        # Pre-select current types
        dialog.set_selected_types(self.selected_action_types)
        
        if dialog.exec_() == QDialog.Accepted:
            new_selection = dialog.get_selected_types()
            
            # Save current active button states before we rebuild
            current_active_states = {}
            for action_type, btn in self.action_buttons.items():
                current_active_states[action_type] = btn.isChecked()
            
            # Update the list of selected types
            self.selected_action_types = new_selection
            
            # Update remembered states
            for action_type in new_selection:
                if action_type not in self.active_button_states:
                    # New type: off by default
                    self.active_button_states[action_type] = False
                elif action_type in current_active_states:
                    # Existing type: keep current on/off
                    self.active_button_states[action_type] = current_active_states[action_type]
            
            # Drop states for types that are no longer selected
            self.active_button_states = {
                k: v for k, v in self.active_button_states.items() 
                if k in new_selection
            }
            
            self._update_filter_buttons()
            
            # Enable "All" if some types are selected
            self.all_button.setEnabled(len(self.selected_action_types) > 0)
            
            self.update_callback()
    
    def _update_filter_buttons(self):
        """Rebuild filter buttons according to the current selection."""
        # Supprimer les anciens boutons
        for btn in self.action_buttons.values():
            btn.deleteLater()
        self.action_buttons.clear()
        
        # Create the new buttons for selected types
        for i, action_type in enumerate(self.selected_action_types):
            if action_type in self.available_types:
                emoji = self.available_types[action_type]['emoji']
                count = self.available_types[action_type]['count']
                btn = QPushButton(f"{emoji} {action_type} ({count})")
                btn.setCheckable(True)
                
                # Use remembered state (off by default for new types)
                is_checked = self.active_button_states.get(action_type, False)
                btn.setChecked(is_checked)
                
                btn.clicked.connect(self._on_action_button_clicked)
                self.action_buttons[action_type] = btn
                
                # Insert from the left (after the separator)
                insert_position = self.buttons_start_index + i
                self.layout.insertWidget(insert_position, btn)
    
    def _on_action_button_clicked(self):
        """Toggle a single action type and sync the 'All' button state."""
        # Update remembered states
        for action_type, btn in self.action_buttons.items():
            self.active_button_states[action_type] = btn.isChecked()
        
        # Toggle the "All" button depending on individual states
        if self.action_buttons:  # ensure there are buttons
            all_checked = all(btn.isChecked() for btn in self.action_buttons.values())
            self.all_button.setChecked(all_checked)
        
        self.update_callback()
    
    def toggle_all(self):
        """Enable/disable all selected action types at once."""
        if not self.selected_action_types:
            # If no types are selected, keep "All" disabled
            self.all_button.setChecked(False)
            return
        
        is_all_checked = self.all_button.isChecked()
        
        for action_type, btn in self.action_buttons.items():
            btn.setChecked(is_all_checked)
            self.active_button_states[action_type] = is_all_checked
        
        self.update_callback()
    
    def get_active_types(self):
        """Return currently active (checked) action types."""
        return [t for t, btn in self.action_buttons.items() if btn.isChecked()]
    
    def get_filtered_actions(self):
        """Return actions matching the active types."""
        active_types = self.get_active_types()
        return [a for a in self.actions_data if a['label'] in active_types]

class ActionSelectionDialog(QDialog):
    """Dialog to select up to a maximum number of action types."""
    
    def __init__(self, parent, all_action_types):
        super().__init__(parent)
        self.all_action_types = all_action_types
        self.selected_types = []
        self.MAX_SELECTIONS = 6
        
        self.setWindowTitle("Select Action Types")
        self.setMinimumWidth(300)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout(self)
        
        # Instructions
        info_label = QLabel(f"Select up to {self.MAX_SELECTIONS} action types :")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Scrollable selection area
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        self.checkboxes = {}
        for action_type, data in all_action_types.items():
            cb = QCheckBox(f"{data['emoji']} {action_type} ({data['count']})")
            cb.stateChanged.connect(self.on_checkbox_changed)
            self.checkboxes[action_type] = cb
            scroll_layout.addWidget(cb)
        
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        # Counter
        self.counter_label = QLabel("0/6 selected")
        layout.addWidget(self.counter_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(select_all_btn)
        
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.clear_all)
        button_layout.addWidget(clear_btn)
        
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def on_checkbox_changed(self):
        selected_count = sum(1 for cb in self.checkboxes.values() if cb.isChecked())
        self.counter_label.setText(f"{selected_count}/{self.MAX_SELECTIONS} selected")
        
        if selected_count > self.MAX_SELECTIONS:
            # Find the last checked one and uncheck it
            sender = self.sender()
            if sender and sender.isChecked():
                sender.setChecked(False)
                QMessageBox.warning(self, "Limit Reached", 
                                  f"You can only select up to {self.MAX_SELECTIONS} action types.")
                return
        
                    # Disable other checkboxes if limit reached
        for cb in self.checkboxes.values():
            if not cb.isChecked():
                cb.setEnabled(selected_count < self.MAX_SELECTIONS)
    
    def select_all(self):
        count = 0
        for cb in self.checkboxes.values():
            if count < self.MAX_SELECTIONS:
                cb.setChecked(True)
                count += 1
            else:
                cb.setChecked(False)
    
    def clear_all(self):
        for cb in self.checkboxes.values():
            cb.setChecked(False)
            cb.setEnabled(True)
    
    def get_selected_types(self):
        return [action_type for action_type, cb in self.checkboxes.items() if cb.isChecked()]
    
    def set_selected_types(self, types):
        """Pré-sélectionne les types donnés"""
        for action_type, cb in self.checkboxes.items():
            cb.setChecked(action_type in types)
        self.on_checkbox_changed()

        # Keep other classes unchanged
class MatchActionsDialog(QDialog):
    """Dialog to display actions and jump to selected ones on click."""
    
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
    """Create a standardized navigation button bound to a frame jump."""
    btn = QPushButton(label)
    btn.setFixedWidth(width)
    btn.setFixedHeight(height)
    btn.setToolTip(tooltip)
    btn.clicked.connect(lambda: callback(frames))
    btn.setStyleSheet(f"font-size: {width//3}pt; font-family: Arial; padding: 1px 1px;")
    return btn