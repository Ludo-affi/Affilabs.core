"""Concentration Schedule Dialog - Shows planned injections for concentration cycles.

This dialog appears at the start of a concentration cycle in manual injection mode.
It shows the user all planned injections upfront, so they know what to expect
as the cycle progresses.

ARCHITECTURE:
- Modal dialog (blocks execution via .exec())
- Shows list of planned concentrations
- Explains the workflow (watch → place flag → inject → place wash flag → repeat)
- User clicks "I'm ready to begin" to proceed with cycle

USAGE:
    from affilabs.dialogs.concentration_schedule_dialog import ConcentrationScheduleDialog
    from affilabs.domain.cycle import Cycle

    cycle = Cycle(
        type="Concentration",
        name="Concentration series",
        planned_concentrations=["100 nM", "50 nM", "10 nM"],
        length_minutes=15.0
    )

    dialog = ConcentrationScheduleDialog(cycle, parent=main_window)
    result = dialog.exec()  # Blocks here until user responds
    if result == ConcentrationScheduleDialog.DialogCode.Accepted:
        # User is ready - proceed with cycle
        continue_cycle()
    else:
        # User cancelled
        stop_cycle()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from affilabs.domain.cycle import Cycle

class ConcentrationScheduleDialog(QDialog):
    """Modal dialog showing planned injections for concentration cycle.

    Blocks cycle execution until user clicks "I'm ready to begin" or "Cancel".
    Displays all planned concentrations so user knows what to expect.

    Attributes:
        cycle: Cycle with planned_concentrations list
    """

    def __init__(self, cycle: "Cycle", parent=None):
        """Initialize concentration schedule dialog.

        Args:
            cycle: Cycle object with planned_concentrations list
            parent: Parent widget for positioning
        """
        super().__init__(parent)
        self.cycle = cycle
        self.setWindowTitle("Concentration Cycle — Injection Schedule")
        self.setModal(True)  # Block execution
        self.setMinimumWidth(520)
        self.setMinimumHeight(380)

        # Remove close button (force user to click Begin/Cancel)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )

        self._setup_ui()

    def _setup_ui(self):
        """Build dialog UI with Apple HIG design."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("📋 Concentration Cycle — Injection Schedule")
        title.setStyleSheet("""
            font-size: 20px;
            font-weight: 700;
            color: #1D1D1F;
            font-family: -apple-system, 'SF Pro Display', sans-serif;
        """)
        layout.addWidget(title)

        # Instruction card
        instruction_frame = QFrame()
        instruction_frame.setStyleSheet("""
            QFrame {
                background: #F5F5F7;

                padding: 16px;
            }
        """)
        instruction_layout = QVBoxLayout(instruction_frame)

        instruction = QLabel(
            "You will perform multiple manual injections during this cycle.\n\n"
            "For each injection:\n"
            "1. Watch the sensorgram for baseline plateau\n"
            "2. Place an INJECTION flag when ready\n"
            "3. System will prompt you to inject\n"
            "4. Manually inject the sample via syringe\n"
            "5. Click 'Injection Complete'\n"
            "6. Watch for response, then place a WASH flag"
        )
        instruction.setStyleSheet("font-size: 13px; color: #1D1D1F; line-height: 1.5;")
        instruction.setWordWrap(True)
        instruction_layout.addWidget(instruction)
        layout.addWidget(instruction_frame)

        # Schedule card
        schedule_frame = QFrame()
        schedule_frame.setStyleSheet("""
            QFrame {
                background: #E3F2FD;

                padding: 16px;
            }
        """)
        schedule_layout = QVBoxLayout(schedule_frame)

        # Schedule title
        schedule_title = QLabel("<b>Planned Injections:</b>")
        schedule_title.setStyleSheet("font-size: 14px; color: #1D1D1F;")
        schedule_layout.addWidget(schedule_title)

        # List of concentrations
        if self.cycle.planned_concentrations:
            for idx, conc in enumerate(self.cycle.planned_concentrations, 1):
                item_label = QLabel(f"  {idx}. {conc}")
                item_label.setStyleSheet("font-size: 13px; color: #424242; margin-left: 8px;")
                schedule_layout.addWidget(item_label)
        else:
            no_conc = QLabel("  (No specific concentrations defined)")
            no_conc.setStyleSheet("font-size: 13px; color: #999999; font-style: italic;")
            schedule_layout.addWidget(no_conc)

        layout.addWidget(schedule_frame)

        # Spacer
        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        cancel_btn = QPushButton("Cancel Cycle")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #F5F5F7;

                padding: 10px 20px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover { background: #E5E5EA; }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        button_layout.addStretch()

        begin_btn = QPushButton("✓ I'm ready to begin")
        begin_btn.setStyleSheet("""
            QPushButton {
                background: #007AFF;

                padding: 10px 24px;
                font-size: 14px;
                font-weight: 600;
                color: white;
            }
            QPushButton:hover { background: #0051D5; }
        """)
        begin_btn.clicked.connect(self.accept)
        begin_btn.setDefault(True)
        button_layout.addWidget(begin_btn)

        layout.addLayout(button_layout)
