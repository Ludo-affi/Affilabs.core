"""Binding Schedule Dialog — Pre-injection countdown for manual mode.

Shows injection schedule with 20s countdown. User clicks Ready or waits.
When complete, closes and triggers ManualInjectionDialog for actual detection.

USAGE:
    dialog = ConcentrationScheduleDialog(cycle, parent=main_window)
    dialog.set_injection_hooks(
        execute_callback=lambda: self._execute_injection(cycle),
        injection_coordinator=self.injection_coordinator,
    )
    result = dialog.exec()
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from affilabs.coordinators.injection_coordinator import InjectionCoordinator
    from affilabs.domain.cycle import Cycle

logger = logging.getLogger(__name__)


class ConcentrationScheduleDialog(QDialog):
    """Pre-injection countdown dialog for multi-injection experiments.

    Attributes:
        cycle: Cycle with planned_concentrations / concentrations / channels
    """

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def __init__(self, cycle: "Cycle", parent=None):
        super().__init__(parent)
        self.cycle = cycle
        self.setWindowTitle("Injection Schedule")
        self.setModal(True)
        self.setFixedWidth(400)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )

        # Countdown state
        self._countdown = 20
        self._countdown_timer: Optional[QTimer] = None
        self._phase1_done = False

        # Injection callback (set via set_injection_hooks)
        self._execute_callback: Optional[Callable] = None
        self._coordinator: Optional["InjectionCoordinator"] = None

        # Persistent UI refs
        self._title_label: Optional[QLabel] = None
        self._hint_label: Optional[QLabel] = None
        self._begin_btn: Optional[QPushButton] = None
        self._cancel_btn: Optional[QPushButton] = None
        self._schedule_widgets: list[QWidget] = []

        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_injection_hooks(
        self,
        execute_callback: Callable,
        injection_coordinator: "InjectionCoordinator",
    ):
        """Wire up injection execution callback.

        Args:
            execute_callback: Function to call when user clicks Ready
            injection_coordinator: Coordinator reference (stored but not used in countdown-only mode)
        """
        self._execute_callback = execute_callback
        self._coordinator = injection_coordinator

    # ------------------------------------------------------------------
    # UI Setup (Phase 1 visible, Phase 2 hidden)
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Title
        self._title_label = QLabel("📋 Get Ready")
        self._title_label.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: #1D1D1F; "
            "font-family: -apple-system, 'SF Pro Display', sans-serif;"
        )
        layout.addWidget(self._title_label)

        # Hint
        self._hint_label = QLabel(
            "Prepare your sample — injection starts when countdown ends."
        )
        self._hint_label.setStyleSheet("font-size: 12px; color: #6E6E73;")
        layout.addWidget(self._hint_label)

        # Schedule items (Phase 1 only — hidden in Phase 2)
        self._build_schedule_items(layout)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setFixedHeight(32)
        self._cancel_btn.setStyleSheet(
            "QPushButton { background: #F5F5F7; border: none; border-radius: 6px; "
            "padding: 0 16px; font-size: 13px; font-weight: 500; }"
            "QPushButton:hover { background: #E5E5EA; }"
        )
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)

        btn_row.addStretch()

        self._begin_btn = QPushButton(f"Ready ({self._countdown}s)")
        self._begin_btn.setFixedHeight(32)
        self._begin_btn.setStyleSheet(
            "QPushButton { background: #007AFF; border: none; border-radius: 6px; "
            "padding: 0 20px; font-size: 13px; font-weight: 600; color: white; }"
            "QPushButton:hover { background: #0051D5; }"
        )
        self._begin_btn.clicked.connect(self._on_ready)
        self._begin_btn.setDefault(True)
        btn_row.addWidget(self._begin_btn)

        layout.addLayout(btn_row)

    def _build_schedule_items(self, parent_layout):
        """Add schedule items (shown during Phase 1)."""
        units = self.cycle.units or "nM"
        contact_time_str = (
            f"{int(self.cycle.contact_time)}s" if self.cycle.contact_time else "—"
        )

        def _add_item(text: str):
            item = QLabel(text)
            item.setStyleSheet(
                "font-size: 13px; color: #1D1D1F; "
                "background: #EDF4FE; border-radius: 6px; padding: 6px 10px;"
            )
            parent_layout.addWidget(item)
            self._schedule_widgets.append(item)

        if self.cycle.concentrations:
            from collections import defaultdict

            conc_to_channels: dict = defaultdict(list)
            for channel, conc_value in self.cycle.concentrations.items():
                conc_to_channels[conc_value].append(channel)

            if len(conc_to_channels) == 1:
                channels_str = ", ".join(sorted(self.cycle.concentrations.keys()))
                conc_value = list(conc_to_channels.keys())[0]
                _add_item(
                    f"  💉  Ch {channels_str}  •  {conc_value}{units}  •  {contact_time_str}"
                )
            else:
                for conc_value, channels in sorted(conc_to_channels.items()):
                    channels_str = ", ".join(sorted(channels))
                    _add_item(
                        f"  💉  Ch {channels_str}  •  {conc_value}{units}  •  {contact_time_str}"
                    )
        elif self.cycle.planned_concentrations:
            for conc in self.cycle.planned_concentrations:
                _add_item(f"  💉  {conc}  •  {contact_time_str}")
        else:
            empty = QLabel("  (No concentrations defined)")
            empty.setStyleSheet("font-size: 12px; color: #999; font-style: italic;")
            parent_layout.addWidget(empty)
            self._schedule_widgets.append(empty)

    # ------------------------------------------------------------------
    # Phase 1: Countdown
    # ------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        self._countdown = 20
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._tick)
        self._countdown_timer.start(1000)

    def _tick(self):
        self._countdown -= 1
        if self._countdown <= 0:
            self._countdown_timer.stop()
            self._on_ready()
        elif self._begin_btn:
            self._begin_btn.setText(f"Ready ({self._countdown}s)")

    # ------------------------------------------------------------------
    # Ready handler
    # ------------------------------------------------------------------

    def _on_ready(self):
        """User clicked Ready (or countdown expired) — close dialog and trigger injection."""
        if self._phase1_done:
            return
        self._phase1_done = True

        if self._countdown_timer:
            self._countdown_timer.stop()

        # Execute injection callback and close dialog
        # ManualInjectionDialog will handle the actual "Inject Now" detection phase
        logger.info("Schedule dialog: User ready — triggering injection")
        if self._execute_callback:
            self._execute_callback()
        
        # Accept and close (ManualInjectionDialog will show next)
        self.accept()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self._countdown_timer:
            self._countdown_timer.stop()
        super().closeEvent(event)
