from PySide6.QtCore import QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from widgets.cycle_manager import CycleManager
from widgets.ui_constants import CycleConfig


class CycleControlsWidget(QWidget):
    """Widget for cycle data button and cycle settings controls."""

    def __init__(
        self,
        parent=None,
        show_cycle_data_button=True,
        show_cycle_settings=True,
        sensorgram_graph=None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        self.cycle_manager = None
        self.cycle_type_dropdown = None
        self.cycle_time_dropdown = None
        self.cycle_data_btn = None

        if show_cycle_data_button:
            # Styled container for Cycle Data Table button
            container = QFrame(self)
            container.setObjectName("cycle_data_container")
            container.setStyleSheet(
                "QFrame#cycle_data_container {"
                "    background-color: white;"
                "    border: 1px solid rgb(180, 180, 180);"
                "    border-radius: 8px;"
                "}",
            )
            container.setFrameShape(QFrame.StyledPanel)
            container.setFrameShadow(QFrame.Raised)
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(12, 12, 12, 12)
            container_layout.setSpacing(8)

            self.cycle_data_btn = QPushButton("Cycle Data Table", container)
            self.cycle_data_btn.setMinimumSize(QSize(0, 35))
            self.cycle_data_btn.setObjectName("cycle_data_btn")
            self.cycle_data_btn.setStyleSheet(
                "QPushButton {"
                "    background-color: rgb(46, 48, 227);"
                "    color: white;"
                "    border: 1px solid rgb(46, 48, 227);"
                "    border-radius: 4px;"
                "    font-weight: bold;"
                "    padding: 8px;"
                "}"
                "QPushButton:hover {"
                "    background-color: rgb(66, 68, 247);"
                "}"
                "QPushButton:pressed {"
                "    background-color: rgb(26, 28, 207);"
                "}",
            )
            container_layout.addWidget(self.cycle_data_btn)
            layout.addWidget(container)

        if show_cycle_settings:
            # Styled container matching Cycle Settings section
            group = QFrame(self)
            group.setObjectName("cycle_settings_container")
            group.setStyleSheet(
                "QFrame#cycle_settings_container {"
                "    background-color: white;"
                "    border: 1px solid rgb(180, 180, 180);"
                "    border-radius: 8px;"
                "}",
            )
            group.setFrameShape(QFrame.StyledPanel)
            group.setFrameShadow(QFrame.Raised)
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(12, 12, 12, 12)
            group_layout.setSpacing(8)

            # Add title
            title = QLabel("Cycle Settings", group)
            title_font = QFont()
            title_font.setPointSize(10)
            title_font.setBold(True)
            title.setFont(title_font)
            title.setStyleSheet("color: rgb(80, 80, 80); padding-bottom: 4px;")
            group_layout.addWidget(title)

            # Cycle type dropdown
            self.cycle_type_dropdown = QComboBox(group)
            self.cycle_type_dropdown.addItems(CycleConfig.TYPES)
            group_layout.addWidget(QLabel("Cycle Type:"))
            group_layout.addWidget(self.cycle_type_dropdown)

            # Cycle time dropdown
            self.cycle_time_dropdown = QComboBox(group)
            self.cycle_time_dropdown.addItems(
                [f"{t} min" for t in CycleConfig.TIME_OPTIONS],
            )
            group_layout.addWidget(QLabel("Cycle Time:"))
            group_layout.addWidget(self.cycle_time_dropdown)

            layout.addWidget(group)

            # Optionally connect to a sensorgram graph for shaded region logic
            if sensorgram_graph is not None:
                self.cycle_manager = CycleManager(
                    cycle_type_dropdown=self.cycle_type_dropdown,
                    cycle_time_dropdown=self.cycle_time_dropdown,
                    sensorgram_graph=sensorgram_graph,
                )

    def set_cycle_data_callback(self, callback):
        if self.cycle_data_btn:
            self.cycle_data_btn.clicked.connect(callback)

    def set_cycle_type(self, cycle_type):
        if self.cycle_type_dropdown:
            self.cycle_type_dropdown.setCurrentText(cycle_type)

    def set_cycle_time(self, cycle_time):
        if self.cycle_time_dropdown:
            self.cycle_time_dropdown.setCurrentText(f"{cycle_time} min")
