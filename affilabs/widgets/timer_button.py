"""Timer Button Widget - Displays countdown and cycle information above Live Sensorgram.

This widget replaces the bottom status bar countdown with a clean, modern button
positioned above the Live Sensorgram graph. It shows:
- Countdown timer (MM:SS format)
- Cycle type (Association, Dissociation, etc.)
- Click to open manual timer dialog

DESIGN:
- Clean, flat, modern appearance
- Neutral colors (gray background, dark text)
- Easy-to-read monospace timer
- No extra borders or decorations
- Compact size to not obstruct graph

USAGE:
    from affilabs.widgets.timer_button import TimerButton

    timer_btn = TimerButton(parent=main_window)
    timer_btn.update_countdown("Association", 125)  # 2:05 remaining
    timer_btn.clicked.connect(show_timer_dialog)
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QPushButton

from affilabs.ui_styles import Colors, Fonts


class TimerButton(QPushButton):
    """Compact timer button showing cycle countdown and information.

    Displays running cycle information in a clean, modern button format.
    Clicking opens a dialog to set manual timers or view detailed cycle info.

    Attributes:
        current_cycle_type: Currently running cycle type (e.g., "Association")
        remaining_seconds: Seconds remaining in current cycle

    Signals:
        clicked: Emitted when user clicks button (inherited from QPushButton)
        clear_requested: Emitted when user requests to clear manual timer
        restart_requested: Emitted when user requests to restart manual timer
    """

    clear_requested = Signal()
    restart_requested = Signal()

    def __init__(self, parent=None):
        """Initialize timer button with default styling.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self.current_cycle_type: Optional[str] = None
        self.remaining_seconds: int = 0
        self.font_size: str = "normal"  # "normal" or "large"
        self.compact_mode: bool = False  # Compact icon-only mode
        self.is_manual_timer: bool = False  # Track if showing manual vs cycle timer

        # Set button properties
        self.setFixedHeight(32)
        self.setMinimumWidth(200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Apply clean, modern styling with neutral colors
        self._update_styling()

        # Set default text
        self.setText("⏱ Timer")

        # Tooltip
        self.setToolTip("Click to set manual timer or view cycle details")

        # Enable context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _update_styling(self):
        """Update button styling based on font size setting and compact mode."""
        if self.compact_mode:
            # Compact mode - icon only, fixed size
            font_size = "16px"
            self.setStyleSheet(f"""
                QPushButton {{
                    background: #E8E8EA;
                    padding: 0px;
                    font-size: {font_size};
                    font-weight: 600;
                    color: #1D1D1F;
                    font-family: {Fonts.MONOSPACE};
                    text-align: center;
                }}
                QPushButton:hover {{
                    background: #D1D1D6;
                }}
                QPushButton:pressed {{
                    background: #C7C7CC;
                }}
            """)
            # Don't change size in compact mode - let parent set it
        else:
            # Normal mode - full text display
            font_size = "18px" if self.font_size == "large" else "13px"
            height = 40 if self.font_size == "large" else 32

            self.setFixedHeight(height)
            self.setMinimumWidth(200)
            self.setStyleSheet(f"""
                QPushButton {{
                    background: #E8E8EA;
                    padding: 6px 14px;
                    font-size: {font_size};
                    font-weight: 600;
                    color: #1D1D1F;
                    font-family: {Fonts.MONOSPACE};
                    text-align: left;
                }}
                QPushButton:hover {{
                    background: #D1D1D6;
                }}
                QPushButton:pressed {{
                    background: #C7C7CC;
                }}
            """)

    def update_countdown(self, cycle_type: str, remaining_seconds: float, is_manual: bool = False):
        """Update displayed countdown timer and cycle information.

        Args:
            cycle_type: Type of running cycle (e.g., "Association", "Baseline")
            remaining_seconds: Seconds remaining in cycle
            is_manual: True if this is a manual timer, False for cycle timer
        """
        self.current_cycle_type = cycle_type
        self.remaining_seconds = int(remaining_seconds)
        self.is_manual_timer = is_manual

        # Format time as MM:SS
        minutes = self.remaining_seconds // 60
        seconds = self.remaining_seconds % 60
        time_str = f"{minutes:02d}:{seconds:02d}"

        # Update button text - format depends on compact mode
        if self.compact_mode:
            # Compact mode - just show time (no icon when timer is running)
            self.setText(time_str)
            tooltip_text = f"{cycle_type} - {time_str} remaining\nClick to set manual timer"
            if is_manual:
                tooltip_text += "\nRight-click: Restart or Clear timer"
            self.setToolTip(tooltip_text)
        else:
            # Normal mode - full display
            self.setText(f"⏱ {time_str} • {cycle_type}")
            tooltip_text = "Click to set manual timer or view cycle details"
            if is_manual:
                tooltip_text = f"{cycle_type} - {time_str} remaining\nRight-click: Restart or Clear timer"
            self.setToolTip(tooltip_text)

    def set_compact_mode(self, enabled: bool):
        """Enable or disable compact icon-only mode.

        Args:
            enabled: True for compact mode (icon only), False for full display
        """
        self.compact_mode = enabled
        self._update_styling()
        # Update display to match new mode
        if self.current_cycle_type and self.remaining_seconds > 0:
            self.update_countdown(self.current_cycle_type, self.remaining_seconds)
        else:
            self.clear()

    def set_font_size(self, size: str):
        """Set the font size for timer display.

        Args:
            size: "normal" or "large"
        """
        if size in ["normal", "large"]:
            self.font_size = size
            self._update_styling()

    def clear(self):
        """Clear timer display and return to idle state."""
        self.current_cycle_type = None
        self.remaining_seconds = 0
        self.is_manual_timer = False

        # Clear text - format depends on compact mode
        if self.compact_mode:
            self.setText("🕐")
            self.setToolTip("Click to set manual timer")
        else:
            self.setText("⏱ Timer")
            self.setToolTip("Click to set manual timer or view cycle details")

    def _show_context_menu(self, position):
        """Show context menu for manual timer actions.

        Args:
            position: Position where context menu was requested
        """
        # Only show menu for active manual timers
        if not self.is_manual_timer or self.remaining_seconds <= 0:
            return

        menu = QMenu(self)

        # Restart Timer (reset to original duration)
        restart_action = QAction("🔄 Restart Timer", self)
        restart_action.triggered.connect(self.request_restart)
        menu.addAction(restart_action)

        # Separator
        menu.addSeparator()

        # Clear Timer (stop and remove)
        clear_action = QAction("✕ Clear Timer", self)
        clear_action.triggered.connect(self.request_clear)
        menu.addAction(clear_action)

        menu.exec(self.mapToGlobal(position))

    def request_clear(self):
        """Emit signal to request timer clearing."""
        self.clear_requested.emit()

    def request_restart(self):
        """Emit signal to request timer restart."""
        self.restart_requested.emit()
