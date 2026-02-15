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

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QPushButton, QWidget

from affilabs.ui_styles import Colors, Fonts
from affilabs.widgets.animated_timer_display import AnimatedTimerDisplay


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
        self.use_rolling_numbers: bool = False  # Basketball scoreboard animation

        # Set button properties
        self.setFixedHeight(32)
        self.setMinimumWidth(200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Create animated timer display (hidden by default)
        self.animated_display_container = QWidget(self)
        self.animated_display_layout = QHBoxLayout(self.animated_display_container)
        self.animated_display_layout.setContentsMargins(14, 0, 0, 0)
        self.animated_display_layout.setSpacing(8)

        # Timer icon label (SVG icon)
        self.timer_icon_label = QLabel()
        import os
        _clock_svg = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ui", "img", "clock_icon.svg")
        if os.path.exists(_clock_svg):
            _pm = QPixmap(_clock_svg).scaled(QSize(20, 20), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.timer_icon_label.setPixmap(_pm)
        else:
            self.timer_icon_label.setText("⏰")
        self.timer_icon_label.setFixedSize(22, 22)
        self.timer_icon_label.setStyleSheet("QLabel { background: transparent; border: none; }")
        self.animated_display_layout.addWidget(self.timer_icon_label)

        # Animated timer
        self.animated_timer = AnimatedTimerDisplay(self.animated_display_container, font_size=13)
        self.animated_display_layout.addWidget(self.animated_timer)

        # Cycle type label
        self.cycle_type_label = QLabel()
        self.cycle_type_label.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                font-weight: 700;
                color: #000000;
                font-family: {Fonts.MONOSPACE};
            }}
        """)
        self.animated_display_layout.addWidget(self.cycle_type_label)
        self.animated_display_layout.addStretch()

        # Position and hide container initially
        self.animated_display_container.hide()
        self.animated_display_container.setGeometry(0, 0, 200, 32)

        # Apply clean, modern styling with neutral colors
        self._update_styling()

        # Set default icon + text
        self._set_icon_text("Timer")

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
                    background: #F5F5F7;
                    border: 1.5px solid #D1D1D6;
                    border-radius: 6px;
                    padding: 0px;
                    font-size: {font_size};
                    font-weight: 600;
                    color: #1D1D1F;
                    font-family: {Fonts.MONOSPACE};
                    text-align: center;
                }}
                QPushButton:hover {{
                    background: #E5E5EA;
                    border: 1.5px solid #B8B8BD;
                }}
                QPushButton:pressed {{
                    background: #D1D1D6;
                    border: 1.5px solid #A0A0A5;
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
                    background: #F5F5F7;
                    border: 1.5px solid #D1D1D6;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-size: {font_size};
                    font-weight: 700;
                    color: #000000;
                    font-family: {Fonts.MONOSPACE};
                    text-align: left;
                }}
                QPushButton:hover {{
                    background: #E5E5EA;
                    border: 1.5px solid #B8B8BD;
                }}
                QPushButton:pressed {{
                    background: #D1D1D6;
                    border: 1.5px solid #A0A0A5;
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

        # Update display based on rolling numbers setting
        if self.use_rolling_numbers and not self.compact_mode:
            # Use animated rolling numbers display
            self.setText("")  # Clear button text
            self.animated_display_container.show()
            self.animated_display_container.setGeometry(0, 0, self.width(), self.height())
            self.animated_timer.update_time(minutes, seconds)
            self.cycle_type_label.setText(f"• {cycle_type}")

            tooltip_text = "Click to set manual timer or view cycle details"
            if is_manual:
                tooltip_text = f"{cycle_type} - {time_str} remaining\nRight-click: Restart or Clear timer"
            self.setToolTip(tooltip_text)
        else:
            # Use standard text display
            self.animated_display_container.hide()

            if self.compact_mode:
                # Compact mode - just show time (no icon when timer is running)
                self.setText(time_str)
                tooltip_text = f"{cycle_type} - {time_str} remaining\nClick to set manual timer"
                if is_manual:
                    tooltip_text += "\nRight-click: Restart or Clear timer"
                self.setToolTip(tooltip_text)
            else:
                # Normal mode - full display
                self._set_icon_text(f"{time_str} • {cycle_type}")
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

            # Update animated display font size
            if self.use_rolling_numbers:
                font_size = 18 if size == "large" else 13
                self.animated_timer.font_size = font_size
                icon_sz = 20 if size == "large" else 16
                self.timer_icon_label.setFixedSize(icon_sz + 2, icon_sz + 2)
                import os
                _clock_svg = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ui", "img", "clock_icon.svg")
                if os.path.exists(_clock_svg):
                    _pm = QPixmap(_clock_svg).scaled(QSize(icon_sz, icon_sz), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.timer_icon_label.setPixmap(_pm)
                self.cycle_type_label.setStyleSheet(f"""
                    QLabel {{
                        font-size: {font_size}px;
                        font-weight: 700;
                        color: #000000;
                        font-family: {Fonts.MONOSPACE};
                    }}
                """)

    def set_rolling_numbers(self, enabled: bool):
        """Enable or disable rolling number animation.

        Args:
            enabled: True to use basketball scoreboard style rolling numbers
        """
        self.use_rolling_numbers = enabled

        # Update display to match new setting
        if self.current_cycle_type and self.remaining_seconds > 0:
            self.update_countdown(self.current_cycle_type, self.remaining_seconds, self.is_manual_timer)
        else:
            self.clear()

    def show_wash_alert(self):
        """Show pulsing WASH NOW alert — click to acknowledge and stop alarm."""
        self.is_manual_timer = True
        self.remaining_seconds = 0
        self.current_cycle_type = "WASH"
        self._wash_alert_active = True

        # Hide animated display
        self.animated_display_container.hide()

        if self.compact_mode:
            self.setText("🔔")
            self.setToolTip("⚠ WASH NOW — click to acknowledge")
        else:
            self.setText("🔔 WASH NOW — click to stop")
            self.setToolTip("Timer expired — click to stop alarm")

        # Orange alert styling
        self.setStyleSheet(f"""
            QPushButton {{
                background: #FF9500;
                border: 2px solid #E08600;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 800;
                color: white;
                font-family: {Fonts.MONOSPACE};
                text-align: center;
            }}
            QPushButton:hover {{
                background: #E08600;
            }}
            QPushButton:pressed {{
                background: #CC7A00;
            }}
        """)

    @property
    def wash_alert_active(self) -> bool:
        """Whether the wash alert is currently shown."""
        return getattr(self, '_wash_alert_active', False)

    def clear(self):
        """Clear timer display and return to idle state."""
        self.current_cycle_type = None
        self.remaining_seconds = 0
        self.is_manual_timer = False
        self._wash_alert_active = False

        # Hide animated display
        self.animated_display_container.hide()

        # Restore normal styling
        self._update_styling()

        # Clear text - format depends on compact mode
        if self.compact_mode:
            self._set_icon_text("")
            self.setToolTip("Click to set manual timer")
        else:
            self._set_icon_text("Timer")
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

    def _set_icon_text(self, text: str):
        """Set button text with clock SVG icon prefix.

        Args:
            text: Text to display after the clock icon (empty string for icon-only)
        """
        import os
        _clock_svg = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ui", "img", "clock_icon.svg")
        if os.path.exists(_clock_svg):
            self.setIcon(QIcon(_clock_svg))
            self.setIconSize(QSize(16, 16))
        self.setText(text)

    def request_clear(self):
        """Emit signal to request timer clearing."""
        self.clear_requested.emit()

    def request_restart(self):
        """Emit signal to request timer restart."""
        self.restart_requested.emit()
