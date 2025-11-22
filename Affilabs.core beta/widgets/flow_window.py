"""Widgets related to fluidic controls."""

from math import inf
from typing import Literal, Self

from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class PumpControl(QGroupBox):
    """Parameters related to pumps."""

    main_layout: QVBoxLayout
    channel_1: QRadioButton
    channel_2: QRadioButton
    reference: QCheckBox

    def __init__(
        self: Self,
        number: Literal[1, 2],
        parent: QWidget | None = None,
    ) -> None:
        """Make a pump control group box."""
        super().__init__(f"Pump {number}", parent)

        self.main_layout = QVBoxLayout(self)
        self.reference = QCheckBox("Referene")
        if number == 1:
            self.channel_1 = QRadioButton("Channel A")
            self.channel_2 = QRadioButton("Channel B")
        else:
            self.channel_1 = QRadioButton("Channel C")
            self.channel_2 = QRadioButton("Channel D")

        self.main_layout.addWidget(self.channel_1)
        self.main_layout.addWidget(self.channel_2)
        self.main_layout.addWidget(self.reference)

        self.channel_1.setChecked(True)  # noqa: FBT003


class FlowWindow(QDialog):
    """Flow parameters entry."""

    main_layout: QVBoxLayout
    pumps_layout: QHBoxLayout
    flow_layout: QHBoxLayout
    pump_1: PumpControl
    pump_2: PumpControl
    flow_rate: QLineEdit
    sample_time: QLabel
    ok_button: QPushButton
    reference_buttons: QButtonGroup

    def __init__(
        self: Self,
        parent: QWidget | None = None,
        flags: Qt.WindowType = Qt.WindowType.Dialog,
    ) -> None:
        """Make a flow window."""
        super().__init__(parent, flags)

        self.main_layout = QVBoxLayout(self)
        self.pumps_layout = QHBoxLayout()
        self.flow_layout = QHBoxLayout()
        self.pump_1 = PumpControl(1)
        self.pump_2 = PumpControl(2)
        self.flow_rate = QLineEdit()
        self.sample_time = QLabel("Sample on-time: 0 seconds")
        self.ok_button = QPushButton("Start")
        self.reference_buttons = QButtonGroup(self)

        self.main_layout.addLayout(self.pumps_layout)
        self.main_layout.addWidget(QLabel("Flow rate of running buffer:"))
        self.main_layout.addLayout(self.flow_layout)
        self.main_layout.addWidget(self.sample_time)
        self.main_layout.addWidget(self.ok_button)

        self.pumps_layout.addWidget(self.pump_1)
        self.pumps_layout.addWidget(self.pump_2)

        self.flow_layout.addWidget(self.flow_rate)
        self.flow_layout.addWidget(QLabel("uL/min"))

        self.pump_2.reference.setChecked(True)  # noqa: FBT003

        self.flow_rate.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.flow_rate.setValidator(QDoubleValidator(0, inf, 5))
        self.flow_rate.textChanged.connect(self.update_time)

        self.reference_buttons.addButton(self.pump_1.reference)
        self.reference_buttons.addButton(self.pump_2.reference)


    def update_time(self: Self) -> None:
        """Update the sample on-time based on the current flow rate."""
        if self.flow_rate.hasAcceptableInput():
            flow_rate = float(self.flow_rate.text())
            time = 80 / flow_rate * 60
            self.sample_time.setText(f"Sample on-time: {time} seconds")

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    widget = FlowWindow()
    widget.show()
    app.exec()
