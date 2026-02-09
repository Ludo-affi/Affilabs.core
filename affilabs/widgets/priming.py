"""Widgets and function dealing with priming the system."""

from __future__ import annotations

from asyncio import Task, create_task, sleep
try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

try:
    from AffiPump.affipump_controller import AffipumpController as _PumpRef
    PumpException = Exception  # AffipumpController raises generic Exception
except ImportError:
    PumpException = Exception
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from affilabs.utils.common import logger
from affilabs.utils.controller import KineticController, PicoEZSPR
from affilabs.utils.hal.pump_hal import PumpHAL


class PrimingWindow(QDialog):
    """Modal dialogue for priming the system."""

    pump: PumpHAL

    knx: KineticController | PicoEZSPR

    vertical_layout: QVBoxLayout

    horizontal_layout: QHBoxLayout

    progress_bar: QProgressBar

    start_button: QPushButton

    cancel_button: QPushButton

    label: QLabel

    timer: QTimer

    priming: bool

    background_tasks: set[Task]

    def __init__(
        self: Self,
        pump: PumpHAL,
        knx: KineticController | PicoEZSPR,
        parent: QWidget | None = None,
    ) -> None:
        """Create the window prompting the user for confirmation."""
        super().__init__(parent)

        self.setModal(True)
        self.setWindowTitle("Pumps Priming")
        self.setWindowIcon(QIcon(":/img/img/affinite2.ico"))

        self.pump = pump
        self.knx = knx
        self.priming = False
        self.background_tasks = set()
        self.vertical_layout = QVBoxLayout(self)
        self.timer = QTimer(self)
        self.progress_bar = QProgressBar()
        self.label = QLabel(
            "Pump priming will take 3 minutes.\n\n"
            "Make sure there is a sensor in the device and that it is under "
            "compression before starting.\n\n"
            "Are you sure you want to continue with priming?",
        )
        self.horizontal_layout = QHBoxLayout()
        self.start_button = QPushButton("Yes")
        self.cancel_button = QPushButton("No")

        self.vertical_layout.addWidget(self.label)
        self.vertical_layout.addWidget(self.progress_bar)
        self.vertical_layout.addLayout(self.horizontal_layout)

        self.horizontal_layout.addWidget(self.cancel_button)
        self.horizontal_layout.addWidget(self.start_button)

        self.progress_bar.hide()
        self.progress_bar.setMaximum(180)

        self.timer.setInterval(1000)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.update_progress_bar)

        self.start_button.clicked.connect(self.start_priming)

        self.cancel_button.clicked.connect(self.reject)

    @Slot()
    def start_priming(self: Self) -> None:
        """Start priming the system."""
        logger.debug("Priming the pumps.")

        self.start_button.hide()
        self.cancel_button.setText("Stop")

        self.label.hide()
        self.progress_bar.show()

        self.timer.start()

        self.priming = True

        task = create_task(self.prime())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    async def prime(self: Self) -> None:
        """Prime the system."""
        try:
            # Make sure pumps are stopped
            self.pump.send_command(0x41, b"T")

            # Fill syringes and wait for them to fill to syncronise the pumps
            self.pump.send_command(0x41, b"IS12A181490R")
            await sleep(6.6)

            # Flush syringes twice with a pulse (10k uL/min)
            self.pump.send_command(0x41, b"OS15A0IS12A181490G2R")
            await sleep(10)
            self.pump.send_command(0x41, b"V166.667,1R")
            await sleep(0.8)
            self.pump.send_command(0x41, b"V9000R")
            await sleep(42)

            # Flush the injection loop
            self.pump.send_command(0x41, b"OS18A0IS12A181490R")
            self.knx.knx_six(state=1, ch=3)
            await sleep(7.5)
            self.knx.knx_six(state=0, ch=3)
            await sleep(7.5)
            self.knx.knx_six(state=1, ch=3)
            await sleep(7.5)
            self.knx.knx_six(state=0, ch=3)
            await sleep(14.5)

            # Switch to channels B and D to flush those
            self.knx.knx_three(state=1, ch=3)

            # Flush syringes three times with a pulse (10k uL/min)
            self.pump.send_command(0x41, b"OS15A0IS12A181490G3R")
            await sleep(37.2)
            self.pump.send_command(0x41, b"V166.667,1R")
            await sleep(0.8)
            self.pump.send_command(0x41, b"V9000R")
            await sleep(42)

            # Start flow for baseline
            self.knx.knx_three(state=0, ch=3)
            self.pump.send_command(0x41, b"OV0.833,1A0R")

            self.accept()
        except PumpException as e:
            logger.exception(
                f"Error while priming pump: {e}. Cancelling priming sequence...",
            )
            self.reject()

    @Slot()
    def reject(self: Self) -> None:
        """Cancel priming the system."""
        self.timer.stop()
        if self.priming:
            logger.debug("Stopping pump priming")
            for task in self.background_tasks:
                task.cancel()
            self.pump.send_command(0x41, b"T")
            self.knx.knx_three(state=0, ch=3)
        super().reject()

    @Slot()
    def update_progress_bar(self: Self) -> None:
        """Update the progress bar."""
        x = self.progress_bar.value()
        self.progress_bar.setValue(x + 1)


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication

    from AffiPump import CavroPumpManager, PumpController

    from affilabs.utils.hal.pump_hal import create_pump_hal

    app = QApplication([])

    # Connect to pump via HAL
    controller = PumpController.from_first_available()
    pump_manager = CavroPumpManager(controller)
    pump = create_pump_hal(pump_manager)

    # PrimingWindow requires both pump and knx (valve controller)
    # For standalone testing, create a mock knx or pass None
    from affilabs.utils.controller import KineticController
    knx = None  # Replace with actual KineticController for full test
    widget = PrimingWindow(pump, knx)
    widget.open()

    app.exec()
