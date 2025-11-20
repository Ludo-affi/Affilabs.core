"""Settings Panel for Sidebar - Contains graph display settings."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QPushButton,
    QLabel, QSpacerItem, QSizePolicy
)


class SettingsPanel(QWidget):
    """Settings panel widget for the sidebar Settings tab."""

    adjust_margins_requested = Signal()  # Emitted when user wants to adjust margins
    advanced_settings_requested = Signal()  # Emitted when user wants to open advanced settings

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def get_adjust_margins_button(self):
        """Return the adjust margins button for external access."""
        return self.adjust_margins_btn
    
    def get_advanced_settings_button(self):
        """Return the advanced settings button for external access."""
        return self.advanced_settings_btn

    def _setup_ui(self):
        """Set up the settings panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Graph Display Settings Group
        graph_group = QGroupBox("Graph Display Settings")
        graph_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid rgb(200, 200, 200);
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        graph_layout = QVBoxLayout(graph_group)
        graph_layout.setSpacing(10)

        # Description label
        desc_label = QLabel("Adjust the white background margins around the graphs:")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-weight: normal; color: rgb(80, 80, 80);")
        graph_layout.addWidget(desc_label)

        # Adjust Margins Button
        self.adjust_margins_btn = QPushButton("Adjust Graph Margins")
        self.adjust_margins_btn.setMinimumHeight(35)
        self.adjust_margins_btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(240, 240, 240);
                border: 1px solid rgb(171, 171, 171);
                border-radius: 3px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgb(253, 253, 253);
                border: 1px solid rgb(46, 48, 227);
            }
            QPushButton:pressed {
                background-color: rgb(230, 230, 230);
            }
        """)
        self.adjust_margins_btn.clicked.connect(self.adjust_margins_requested.emit)
        graph_layout.addWidget(self.adjust_margins_btn)

        layout.addWidget(graph_group)

        # Advanced Settings Group
        adv_group = QGroupBox("Advanced Settings")
        adv_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid rgb(200, 200, 200);
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        adv_layout = QVBoxLayout(adv_group)
        adv_layout.setSpacing(10)

        # Description label
        adv_desc_label = QLabel("Configure device calibration settings, LED intensities, and integration time:")
        adv_desc_label.setWordWrap(True)
        adv_desc_label.setStyleSheet("font-weight: normal; color: rgb(80, 80, 80);")
        adv_layout.addWidget(adv_desc_label)

        # Advanced Settings Button
        self.advanced_settings_btn = QPushButton("⚙️ Advanced Settings")
        self.advanced_settings_btn.setEnabled(False)  # Disabled until device connected
        self.advanced_settings_btn.setMinimumHeight(35)
        self.advanced_settings_btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(240, 240, 240);
                border: 1px solid rgb(171, 171, 171);
                border-radius: 3px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover:enabled {
                background-color: rgb(253, 253, 253);
                border: 1px solid rgb(46, 48, 227);
            }
            QPushButton:pressed:enabled {
                background-color: rgb(230, 230, 230);
            }
            QPushButton:disabled {
                background-color: rgb(220, 220, 220);
                color: rgb(150, 150, 150);
            }
        """)
        self.advanced_settings_btn.clicked.connect(self.advanced_settings_requested.emit)
        adv_layout.addWidget(self.advanced_settings_btn)

        layout.addWidget(adv_group)

        # UI Developer Tools Group
        dev_group = QGroupBox("Developer Tools")
        dev_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid rgb(200, 200, 200);
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        dev_layout = QVBoxLayout(dev_group)
        dev_layout.setSpacing(10)

        # Description
        dev_desc = QLabel("Open interactive console to inspect and adjust UI elements in real-time (Ctrl+Shift+I):")
        dev_desc.setWordWrap(True)
        dev_desc.setStyleSheet("font-weight: normal; color: rgb(80, 80, 80);")
        dev_layout.addWidget(dev_desc)

        # UI Inspector Button
        self.ui_inspector_btn = QPushButton("🔧 Open UI Inspector Console")
        self.ui_inspector_btn.setMinimumHeight(35)
        self.ui_inspector_btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(46, 48, 227);
                color: white;
                border: none;
                border-radius: 3px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgb(66, 68, 247);
            }
            QPushButton:pressed {
                background-color: rgb(26, 28, 207);
            }
        """)
        dev_layout.addWidget(self.ui_inspector_btn)

        # Tip label
        tip_label = QLabel("💡 Tip: Use 'Device' quick button in console for easy inspect!")
        tip_label.setWordWrap(True)
        tip_label.setStyleSheet("font-weight: normal; color: rgb(46, 227, 111); font-size: 9pt; padding: 5px;")
        dev_layout.addWidget(tip_label)

        layout.addWidget(dev_group)

        # Add spacer to push everything to the top
        spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        layout.addItem(spacer)

        # Store references for external access
        self.graph_group = graph_group
        self.main_layout = layout

    def get_graph_display_group(self):
        """Return the graph display settings group box for external layout manipulation."""
        return self.graph_group

    def remove_graph_display_group(self):
        """Remove the graph display group from this panel's layout."""
        if self.graph_group and self.main_layout:
            self.main_layout.removeWidget(self.graph_group)
            self.graph_group.setParent(None)
            return self.graph_group
        return None
