"""Binding Schedule Dialog — Two-phase injection feedback for manual mode.

Phase 1 (COUNTDOWN):
    Shows injection schedule, 20s countdown.  User clicks Ready or waits.

Phase 2 (DETECTION):
    Dialog stays open.  Per-channel LED indicators (one per active channel)
    turn green as injection_auto_detected fires.  Once all channels are green,
    dialog shows success for 3 seconds, then accepts and closes.

The dialog is still used with .exec() — it connects to coordinator signals
inside the event loop spawned by exec(), so callbacks fire normally.

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
    """Two-phase injection dialog: countdown → detection LED feedback.

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

        # Phase-1 state
        self._countdown = 20
        self._countdown_timer: Optional[QTimer] = None
        self._phase1_done = False

        # Phase-2 state (set via set_injection_hooks)
        self._execute_callback: Optional[Callable] = None
        self._coordinator: Optional["InjectionCoordinator"] = None
        self._active_channels: list[str] = []
        self._channel_leds: dict[str, QLabel] = {}
        self._channel_status: dict[str, QLabel] = {}
        self._detected_channels: set[str] = set()

        # Persistent UI refs
        self._title_label: Optional[QLabel] = None
        self._hint_label: Optional[QLabel] = None
        self._begin_btn: Optional[QPushButton] = None
        self._cancel_btn: Optional[QPushButton] = None
        self._schedule_widgets: list[QWidget] = []
        self._detection_container: Optional[QVBoxLayout] = None

        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_injection_hooks(
        self,
        execute_callback: Callable,
        injection_coordinator: "InjectionCoordinator",
    ):
        """Wire up injection execution and coordinator signals.

        Must be called before exec() so Phase 2 works.

        Args:
            execute_callback: Starts the actual injection (e.g. _execute_injection)
            injection_coordinator: Coordinator with injection_auto_detected signal
        """
        self._execute_callback = execute_callback
        self._coordinator = injection_coordinator

        # Determine active channels from cycle.channels ("AC" / "BD" / etc.)
        ch_str = (self.cycle.channels or "ABCD").upper()
        self._active_channels = list(ch_str)

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
        self._hint_label.setStyleSheet("font-size: 11px; color: #86868B;")
        layout.addWidget(self._hint_label)

        # Schedule items (Phase 1 only — hidden in Phase 2)
        self._build_schedule_items(layout)

        # Detection container (empty in Phase 1, populated in Phase 2)
        self._detection_container = QVBoxLayout()
        self._detection_container.setSpacing(6)
        layout.addLayout(self._detection_container)

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
    # Phase 1 → Phase 2 transition
    # ------------------------------------------------------------------

    def _on_ready(self):
        """User clicked Ready (or countdown expired) — start Phase 2."""
        if self._phase1_done:
            return
        self._phase1_done = True

        if self._countdown_timer:
            self._countdown_timer.stop()

        # If no coordinator hooked up, fall back to simple 3s close
        if not self._coordinator or not self._execute_callback:
            self._show_simple_success()
            return

        # --- Switch UI to detection phase ---
        self._title_label.setText("💉 Inject Now")
        self._hint_label.setText(
            "Waiting for injection detection on active channels..."
        )
        self._hint_label.setStyleSheet(
            "font-size: 11px; color: #007AFF; font-weight: 500;"
        )

        # Hide schedule items
        for w in self._schedule_widgets:
            w.hide()

        # Build per-channel LED indicators
        self._build_channel_leds()

        # Button → waiting state
        self._begin_btn.setText("Waiting for injection...")
        self._begin_btn.setEnabled(False)
        self._begin_btn.setStyleSheet(
            "QPushButton { background: #FF9500; border: none; border-radius: 6px; "
            "padding: 0 20px; font-size: 13px; font-weight: 600; color: white; }"
        )

        # Connect coordinator signals (inside exec() event loop, they fire fine)
        self._coordinator.injection_auto_detected.connect(self._on_channel_detected)
        self._coordinator.injection_window_expired.connect(self._on_detection_timeout)

        # Kick off the actual injection (non-blocking for manual mode)
        logger.info("Schedule dialog Phase 2 — calling execute_callback")
        self._execute_callback()

    def _show_simple_success(self):
        """Fallback when no coordinator — green for 3s then accept."""
        if self._begin_btn:
            self._begin_btn.setText("✅ Injecting...")
            self._begin_btn.setEnabled(False)
            self._begin_btn.setStyleSheet(
                "QPushButton { background: #34C759; border: none; border-radius: 6px; "
                "padding: 0 20px; font-size: 13px; font-weight: 600; color: white; }"
            )
        QTimer.singleShot(3000, self.accept)

    # ------------------------------------------------------------------
    # Phase 2: Per-channel detection LEDs
    # ------------------------------------------------------------------

    def _build_channel_leds(self):
        """Create one LED row per active channel."""
        for ch in self._active_channels:
            row = QHBoxLayout()
            row.setSpacing(8)

            led = QLabel("⚪")
            led.setFixedWidth(24)
            led.setStyleSheet("font-size: 16px;")
            row.addWidget(led)

            label = QLabel(f"Channel {ch}")
            label.setStyleSheet("font-size: 13px; font-weight: 600; color: #86868B;")
            row.addWidget(label)

            row.addStretch()

            status = QLabel("Waiting...")
            status.setStyleSheet("font-size: 11px; color: #86868B;")
            row.addWidget(status)

            self._detection_container.addLayout(row)
            self._channel_leds[ch] = led
            self._channel_status[ch] = status

    def _on_channel_detected(
        self, channel: str, injection_time: float, confidence: float
    ):
        """Slot for injection_auto_detected — lights primary channel green.

        After a short delay, also checks cycle.injection_time_by_channel
        (populated by the coordinator's _scan_all_channels_for_injection)
        so remaining channels light up too.
        """
        self._set_channel_green(channel.upper(), injection_time, confidence)

        # Give coordinator ~500ms to finish _scan_all_channels_for_injection
        QTimer.singleShot(500, self._check_all_channel_results)

    def _set_channel_green(
        self, channel: str, injection_time: float, confidence: float
    ):
        """Light a single channel LED green."""
        if channel in self._detected_channels:
            return  # already lit
        self._detected_channels.add(channel)

        if channel in self._channel_leds:
            self._channel_leds[channel].setText("🟢")
        if channel in self._channel_status:
            self._channel_status[channel].setText(
                f"✓ Detected at {injection_time:.1f}s ({confidence:.0%})"
            )
            self._channel_status[channel].setStyleSheet(
                "font-size: 11px; color: #34C759; font-weight: 600;"
            )

        self._maybe_all_detected()

    def _check_all_channel_results(self):
        """Read per-channel scan results stored on cycle by coordinator."""
        times = getattr(self.cycle, "injection_time_by_channel", {}) or {}
        confs = getattr(self.cycle, "injection_confidence_by_channel", {}) or {}

        for ch in self._active_channels:
            if ch in self._detected_channels:
                continue
            ch_lower = ch.lower()
            t = times.get(ch) or times.get(ch_lower)
            c = confs.get(ch, confs.get(ch_lower, 0.0))
            if t is not None:
                self._set_channel_green(ch, t, c)

        self._maybe_all_detected()

    def _maybe_all_detected(self):
        """If every active channel is green → show success for 3s → accept."""
        if not set(self._active_channels).issubset(self._detected_channels):
            return

        logger.info("All active channels detected — showing success for 3s")
        self._title_label.setText("✅ Injection Detected")
        self._hint_label.setText(
            "All channels confirmed — continuing in 3 seconds..."
        )
        self._hint_label.setStyleSheet(
            "font-size: 11px; color: #34C759; font-weight: 600;"
        )
        self._begin_btn.setText("✅ Success!")
        self._begin_btn.setStyleSheet(
            "QPushButton { background: #34C759; border: none; border-radius: 6px; "
            "padding: 0 20px; font-size: 13px; font-weight: 600; color: white; }"
        )
        if self._cancel_btn:
            self._cancel_btn.hide()

        QTimer.singleShot(3000, self.accept)

    # ------------------------------------------------------------------
    # Timeout handling
    # ------------------------------------------------------------------

    def _on_detection_timeout(self):
        """60s detection window expired — mark undetected as yellow, close."""
        for ch in self._active_channels:
            if ch not in self._detected_channels:
                if ch in self._channel_leds:
                    self._channel_leds[ch].setText("🟡")
                if ch in self._channel_status:
                    self._channel_status[ch].setText("Timeout — no detection")
                    self._channel_status[ch].setStyleSheet(
                        "font-size: 11px; color: #FF9500; font-weight: 500;"
                    )

        self._title_label.setText("⚠️ Detection Timeout")
        self._hint_label.setText("Not all channels detected — closing in 3s...")
        self._hint_label.setStyleSheet(
            "font-size: 11px; color: #FF9500; font-weight: 500;"
        )

        self._begin_btn.setText("Continue anyway")
        self._begin_btn.setEnabled(True)
        self._begin_btn.setStyleSheet(
            "QPushButton { background: #FF9500; border: none; border-radius: 6px; "
            "padding: 0 20px; font-size: 13px; font-weight: 600; color: white; }"
            "QPushButton:hover { background: #E08600; }"
        )
        try:
            self._begin_btn.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._begin_btn.clicked.connect(self.accept)

        QTimer.singleShot(3000, self.accept)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self._countdown_timer:
            self._countdown_timer.stop()
        if self._coordinator:
            try:
                self._coordinator.injection_auto_detected.disconnect(
                    self._on_channel_detected
                )
            except (RuntimeError, TypeError):
                pass
            try:
                self._coordinator.injection_window_expired.disconnect(
                    self._on_detection_timeout
                )
            except (RuntimeError, TypeError):
                pass
        super().closeEvent(event)
