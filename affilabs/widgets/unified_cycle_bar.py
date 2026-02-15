"""Unified Cycle Bar - Single widget replacing intelligence bar + injection dialog + contact timer.

This compact bar lives at the bottom of the main window and transitions through
cycle phases, providing a consistent information stream:

    IDLE → RUNNING → INJECT → CONTACT → WASH_DUE → (back to RUNNING or IDLE)

Each state shows contextually appropriate information and controls:
- IDLE: System status messages (hardware state, acquisition status)
- RUNNING: Cycle countdown with type, progress, and time remaining
- INJECT: Manual injection prompt with auto-detection countdown and action buttons
- CONTACT: Contact time countdown (clickable to open large popout timer)
- WASH_DUE: Urgent wash/regeneration alert with dismiss button

REPLACES:
- bottom_intel_message_label (operation_status_bar intelligence messages)
- ManualInjectionDialog (modal blocking injection prompt)
- Contact timer auto-start in popout window
- Intelligence bar cycle countdown from _update_cycle_display()

ARCHITECTURE:
- State machine driven: set_idle / set_running / set_inject / set_contact / set_wash_due
- Non-blocking: injection detection runs in InjectionCoordinator, bar is just display
- Signals relay user actions (done, cancel, dismiss) back to coordinator
- Click during CONTACT state opens PopOutTimerWindow as detached large view

USAGE:
    from affilabs.widgets.unified_cycle_bar import UnifiedCycleBar

    bar = UnifiedCycleBar(parent=main_window)
    bar.set_idle("Connected to P4SPR")
    bar.set_running("Association", 1, 5, 150.0, 300.0)
    bar.set_inject(sample_info, injection_num=1, total_injections=3)
    bar.set_contact("Contact Time — 50 nM (2/5)", 180)
    bar.set_wash_due()
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from affilabs.ui_styles import Colors, Fonts


class CycleBarState(Enum):
    """States for the unified cycle bar."""

    IDLE = "idle"
    RUNNING = "running"
    INJECT = "inject"
    CONTACT = "contact"
    WASH_DUE = "wash_due"


class UnifiedCycleBar(QFrame):
    """Compact status bar that transitions through cycle phases.

    Replaces the intelligence bar, manual injection dialog, and contact timer
    with a single unified widget showing contextual information and controls.

    Signals:
        user_done_injecting: User clicked "Done Injecting" during INJECT state
        user_cancel_injection: User clicked "Cancel" during INJECT state
        wash_acknowledged: User clicked "Dismiss" during WASH_DUE state
        popout_requested: User clicked bar during CONTACT state (open large timer)
    """

    user_done_injecting = Signal()
    user_cancel_injection = Signal()
    wash_acknowledged = Signal()
    popout_requested = Signal()

    def __init__(self, parent=None):
        """Initialize unified cycle bar.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._state = CycleBarState.IDLE
        self._contact_remaining = 0
        self._inject_remaining = 60
        self._setup_ui()

    def _setup_ui(self):
        """Build bar UI with all elements (visibility toggled per state)."""
        self.setFixedHeight(50)
        self.setStyleSheet(self._idle_style())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(12)

        # ── State icon ──
        self.icon_label = QLabel("●")
        self.icon_label.setStyleSheet(
            f"font-size: 14px; color: {Colors.SECONDARY_TEXT}; "
            f"font-weight: {Fonts.WEIGHT_BOLD}; background: transparent;"
        )
        layout.addWidget(self.icon_label)

        # ── Main message (primary text) ──
        self.message_label = QLabel("Initializing...")
        self.message_label.setStyleSheet(
            f"font-size: 13px; color: {Colors.SECONDARY_TEXT}; "
            f"font-weight: {Fonts.WEIGHT_SEMIBOLD}; font-family: {Fonts.SYSTEM}; "
            f"background: transparent;"
        )
        layout.addWidget(self.message_label)

        layout.addStretch()

        # ── Right-side info (countdown, notes) ──
        self.info_label = QLabel("")
        self.info_label.setStyleSheet(
            f"font-size: 13px; color: {Colors.SECONDARY_TEXT}; "
            f"font-weight: {Fonts.WEIGHT_NORMAL}; font-family: {Fonts.MONOSPACE}; "
            f"background: transparent;"
        )
        self.info_label.hide()
        layout.addWidget(self.info_label)

        # ── Cancel button (INJECT state) ──
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(28)
        self.cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.8);
                padding: 0px 16px;
                font-size: 12px;
                font-weight: 500;
                color: #1D1D1F;
                border-radius: 6px;
                border: 1px solid #D1D1D6;
            }
            QPushButton:hover { background: #E5E5EA; }
            QPushButton:pressed { background: #D1D1D6; }
        """)
        self.cancel_btn.clicked.connect(self.user_cancel_injection)
        self.cancel_btn.hide()
        layout.addWidget(self.cancel_btn)

        # ── Done button (INJECT state) ──
        self.done_btn = QPushButton("✓ Done Injecting")
        self.done_btn.setFixedHeight(28)
        self.done_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.done_btn.setStyleSheet(self._done_btn_style())
        self.done_btn.clicked.connect(self.user_done_injecting)
        self.done_btn.hide()
        layout.addWidget(self.done_btn)

        # ── Dismiss button (WASH_DUE state) ──
        self.dismiss_btn = QPushButton("Dismiss")
        self.dismiss_btn.setFixedHeight(28)
        self.dismiss_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.dismiss_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.9);
                padding: 0px 16px;
                font-size: 12px;
                font-weight: 600;
                color: #FF3B30;
                border-radius: 6px;
                border: 1px solid rgba(255, 59, 48, 0.3);
            }
            QPushButton:hover { background: rgba(255, 255, 255, 1.0); }
            QPushButton:pressed { background: #FFE5E3; }
        """)
        self.dismiss_btn.clicked.connect(self._on_dismiss)
        self.dismiss_btn.hide()
        layout.addWidget(self.dismiss_btn)

    # ──────────────────────────────────────────────────────────────────
    # State transition methods
    # ──────────────────────────────────────────────────────────────────

    @property
    def state(self) -> CycleBarState:
        """Current bar state."""
        return self._state

    def set_idle(self, message: str = "", color: str = "") -> None:
        """Set IDLE state with system status message.

        Called by _refresh_intelligence_bar() when no cycle is running.

        Args:
            message: Status message (e.g., "Connected to P4SPR", "⚡ Acquiring")
            color: Message color (hex). Default: secondary text color.
        """
        self._state = CycleBarState.IDLE
        self._hide_all_buttons()
        self.info_label.hide()

        color = color or Colors.SECONDARY_TEXT
        self.icon_label.setText("●")
        self.icon_label.setStyleSheet(
            f"font-size: 14px; color: {color}; font-weight: {Fonts.WEIGHT_BOLD}; "
            f"background: transparent;"
        )
        self.message_label.setText(message or "Ready")
        self.message_label.setStyleSheet(
            f"font-size: 13px; color: {color}; "
            f"font-weight: {Fonts.WEIGHT_SEMIBOLD}; font-family: {Fonts.SYSTEM}; "
            f"background: transparent;"
        )
        self.setStyleSheet(self._idle_style())
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.setToolTip("")

    def set_running(
        self,
        cycle_type: str,
        cycle_num: int,
        total_cycles: int,
        elapsed_sec: float,
        total_sec: float,
        next_warning: str = "",
        color: str = "",
    ) -> None:
        """Set RUNNING state with cycle countdown.

        Called by _update_cycle_display() every 1 second during cycle execution.

        Args:
            cycle_type: Cycle type (e.g., "Association", "Baseline")
            cycle_num: Current cycle number (1-indexed)
            total_cycles: Total number of cycles
            elapsed_sec: Elapsed seconds in current cycle
            total_sec: Total cycle duration in seconds
            next_warning: Optional warning text (e.g., "→ Next: Conc. 50nM in 8s")
            color: Message color override (hex)
        """
        self._state = CycleBarState.RUNNING
        self._hide_all_buttons()

        # Format countdown
        if total_sec >= 6000:
            # Hours:minutes for very long cycles (>= 100 min)
            e_h, e_m = int(elapsed_sec // 3600), int((elapsed_sec % 3600) // 60)
            t_h, t_m = int(total_sec // 3600), int((total_sec % 3600) // 60)
            time_str = f"{e_h:02d}:{e_m:02d}/{t_h:02d}:{t_m:02d}"
        else:
            # Minutes:seconds
            e_m, e_s = int(elapsed_sec // 60), int(elapsed_sec % 60)
            t_m, t_s = int(total_sec // 60), int(total_sec % 60)
            time_str = f"{e_m:02d}:{e_s:02d}/{t_m:02d}:{t_s:02d}"

        display_color = color or Colors.INFO
        if next_warning:
            display_color = Colors.WARNING

        self.icon_label.setText("⏱")
        self.icon_label.setStyleSheet(
            f"font-size: 14px; color: {display_color}; background: transparent;"
        )

        message = f"{cycle_type} (Cycle {cycle_num}/{total_cycles}) — {time_str}"
        self.message_label.setText(message)
        self.message_label.setStyleSheet(
            f"font-size: 13px; color: {display_color}; "
            f"font-weight: {Fonts.WEIGHT_SEMIBOLD}; font-family: {Fonts.SYSTEM}; "
            f"background: transparent;"
        )

        if next_warning:
            self.info_label.setText(next_warning)
            self.info_label.setStyleSheet(
                f"font-size: 12px; color: {Colors.WARNING}; "
                f"font-weight: {Fonts.WEIGHT_SEMIBOLD}; font-family: {Fonts.SYSTEM}; "
                f"background: transparent;"
            )
            self.info_label.show()
        else:
            self.info_label.hide()

        self.setStyleSheet(self._idle_style())
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.setToolTip("")

    def set_inject(
        self,
        sample_info: dict[str, Any],
        injection_num: Optional[int] = None,
        total_injections: Optional[int] = None,
    ) -> None:
        """Set INJECT state — manual injection prompt with detection countdown.

        Shows sample info, a 60-second countdown, and Cancel/Done buttons.
        Detection runs in InjectionCoordinator; this is pure display.

        Args:
            sample_info: Sample information dict with keys:
                sample_id, concentration, units, display_name
            injection_num: Current injection number (for concentration cycles)
            total_injections: Total injections planned
        """
        self._state = CycleBarState.INJECT
        self._inject_remaining = 60

        # Build injection description
        sample_id = sample_info.get("sample_id", "Sample")
        conc = sample_info.get("concentration")
        units = sample_info.get("units", "nM")

        if injection_num and total_injections:
            prefix = f"Injection {injection_num}/{total_injections}"
        else:
            prefix = "Manual Injection"

        if conc is not None:
            desc = f"{prefix}  •  {sample_id} ({conc} {units})"
        else:
            desc = f"{prefix}  •  {sample_id}"

        self.icon_label.setText("💉")
        self.icon_label.setStyleSheet(
            "font-size: 15px; background: transparent;"
        )

        self.message_label.setText(desc)
        self.message_label.setStyleSheet(
            f"font-size: 13px; color: #1D1D1F; "
            f"font-weight: {Fonts.WEIGHT_SEMIBOLD}; font-family: {Fonts.SYSTEM}; "
            f"background: transparent;"
        )

        # Show countdown
        self.info_label.setText("60s")
        self.info_label.setStyleSheet(
            f"font-size: 14px; color: #FF9500; "
            f"font-weight: {Fonts.WEIGHT_BOLD}; font-family: {Fonts.MONOSPACE}; "
            f"background: transparent;"
        )
        self.info_label.show()

        # Show action buttons
        self._hide_all_buttons()
        self.cancel_btn.show()
        self.done_btn.show()
        self.done_btn.setEnabled(True)
        self.done_btn.setText("✓ Done Injecting")
        self.done_btn.setStyleSheet(self._done_btn_style())

        # Warm background to draw attention
        self.setStyleSheet(self._inject_style())
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.setToolTip("Inject your sample now. Click Done when finished.")

    def update_inject_countdown(self, remaining_seconds: int) -> None:
        """Update injection countdown display during INJECT state.

        Called by InjectionCoordinator every second during the 60-second window.

        Args:
            remaining_seconds: Seconds remaining in detection window
        """
        if self._state != CycleBarState.INJECT:
            return
        self._inject_remaining = remaining_seconds
        self.info_label.setText(f"{remaining_seconds}s")

        # Intensify color as time runs low
        if remaining_seconds <= 10:
            color = "#FF3B30"  # Red
        elif remaining_seconds <= 30:
            color = "#FF9500"  # Orange
        else:
            color = "#FF9500"  # Standard orange
        self.info_label.setStyleSheet(
            f"font-size: 14px; color: {color}; "
            f"font-weight: {Fonts.WEIGHT_BOLD}; font-family: {Fonts.MONOSPACE}; "
            f"background: transparent;"
        )

    def set_inject_done_phase(self) -> None:
        """Switch INJECT state to 'finalizing' after user clicks Done.

        Disables Done button and shows finalizing message while
        detection continues for ~10 seconds.
        """
        if self._state != CycleBarState.INJECT:
            return
        self.done_btn.setEnabled(False)
        self.done_btn.setText("✓ Finalizing...")
        self.message_label.setStyleSheet(
            f"font-size: 13px; color: {Colors.SUCCESS}; "
            f"font-weight: {Fonts.WEIGHT_SEMIBOLD}; font-family: {Fonts.SYSTEM}; "
            f"background: transparent;"
        )

    def set_inject_detected(self, channel: str, confidence: float) -> None:
        """Briefly show detection success before transitioning to next state.

        Displayed for ~1 second before the bar transitions to CONTACT or RUNNING.

        Args:
            channel: Channel where injection was detected (e.g., "a")
            confidence: Detection confidence (0–1)
        """
        if self._state != CycleBarState.INJECT:
            return
        self.icon_label.setText("✓")
        self.icon_label.setStyleSheet(
            f"font-size: 15px; color: {Colors.SUCCESS}; background: transparent;"
        )
        self.message_label.setText(
            f"Injection detected on channel {channel.upper()} ({confidence:.0%})"
        )
        self.message_label.setStyleSheet(
            f"font-size: 13px; color: {Colors.SUCCESS}; "
            f"font-weight: {Fonts.WEIGHT_SEMIBOLD}; font-family: {Fonts.SYSTEM}; "
            f"background: transparent;"
        )
        self.info_label.hide()
        self._hide_all_buttons()

    def set_contact(self, label: str, remaining_seconds: int) -> None:
        """Set CONTACT state with countdown timer.

        Clickable – user can click the bar to open PopOutTimerWindow.

        Args:
            label: Timer label (e.g., "Contact Time — 50 nM (2/5)")
            remaining_seconds: Starting countdown in seconds
        """
        self._state = CycleBarState.CONTACT
        self._contact_remaining = remaining_seconds
        self._hide_all_buttons()

        minutes = remaining_seconds // 60
        seconds = remaining_seconds % 60

        self.icon_label.setText("⏳")
        self.icon_label.setStyleSheet(
            f"font-size: 14px; color: {Colors.INFO}; background: transparent;"
        )

        self.message_label.setText(label)
        self.message_label.setStyleSheet(
            f"font-size: 13px; color: {Colors.INFO}; "
            f"font-weight: {Fonts.WEIGHT_SEMIBOLD}; font-family: {Fonts.SYSTEM}; "
            f"background: transparent;"
        )

        self.info_label.setText(f"{minutes:02d}:{seconds:02d}")
        self.info_label.setStyleSheet(
            f"font-size: 15px; color: {Colors.INFO}; "
            f"font-weight: {Fonts.WEIGHT_BOLD}; font-family: {Fonts.MONOSPACE}; "
            f"background: transparent;"
        )
        self.info_label.show()

        self.setStyleSheet(self._contact_style())
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setToolTip("Click to open large timer")

    def update_contact_countdown(self, remaining_seconds: int) -> None:
        """Update contact timer countdown display.

        Called every second by the manual timer tick in affilabs_core_ui.

        Args:
            remaining_seconds: Seconds remaining
        """
        if self._state != CycleBarState.CONTACT:
            return
        self._contact_remaining = remaining_seconds
        minutes = remaining_seconds // 60
        seconds = remaining_seconds % 60
        self.info_label.setText(f"{minutes:02d}:{seconds:02d}")

    def set_wash_due(self, label: str = "") -> None:
        """Set WASH_DUE state — urgent alert with red background.

        Triggered when contact timer expires. Shows prominent visual alert
        and plays alarm sound (handled by affilabs_core_ui timer infrastructure).

        Args:
            label: Optional label text override
        """
        self._state = CycleBarState.WASH_DUE
        self._hide_all_buttons()

        self.icon_label.setText("🧪")
        self.icon_label.setStyleSheet("font-size: 16px; background: transparent;")

        self.message_label.setText(label or "WASH NOW — Contact time expired")
        self.message_label.setStyleSheet(
            f"font-size: 14px; color: #FFFFFF; "
            f"font-weight: {Fonts.WEIGHT_BOLD}; font-family: {Fonts.SYSTEM}; "
            f"background: transparent;"
        )

        self.info_label.hide()
        self.dismiss_btn.show()

        self.setStyleSheet(self._wash_due_style())
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.setToolTip("Wash/regeneration needed. Click Dismiss to acknowledge.")

    # ──────────────────────────────────────────────────────────────────
    # Mouse handling
    # ──────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        """Handle click — open popout timer in CONTACT state."""
        if self._state == CycleBarState.CONTACT:
            self.popout_requested.emit()
        super().mousePressEvent(event)

    # ──────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────

    def _hide_all_buttons(self):
        """Hide all action buttons."""
        self.cancel_btn.hide()
        self.done_btn.hide()
        self.dismiss_btn.hide()

    def _on_dismiss(self):
        """Handle dismiss button click in WASH_DUE state."""
        self.wash_acknowledged.emit()

    # ──────────────────────────────────────────────────────────────────
    # Style sheets per state
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _idle_style() -> str:
        """Neutral background matching the existing operation_status_bar."""
        return f"""
            QFrame {{
                background: {Colors.BACKGROUND_WHITE};
            }}
        """

    @staticmethod
    def _inject_style() -> str:
        """Warm yellow-orange gradient to draw attention during injection."""
        return """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FFF8E1, stop:1 #FFF3E0);
                border-top: 2px solid #FF9500;
            }
        """

    @staticmethod
    def _contact_style() -> str:
        """Cool blue tint for contact/incubation countdown."""
        return """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #E3F2FD, stop:1 #E8EAF6);
                border-top: 2px solid #007AFF;
            }
        """

    @staticmethod
    def _wash_due_style() -> str:
        """Red/orange gradient for urgent wash alert."""
        return """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FF3B30, stop:1 #FF6B35);
                border-top: 2px solid #CC2F27;
            }
        """

    @staticmethod
    def _done_btn_style() -> str:
        """Green Done Injecting button style."""
        return """
            QPushButton {
                background: #34C759;
                padding: 0px 18px;
                font-size: 12px;
                font-weight: 600;
                color: white;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background: #2DA84C; }
            QPushButton:pressed { background: #248A3D; }
            QPushButton:disabled { background: #E5E5EA; color: #86868B; }
        """
