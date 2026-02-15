"""Animated Timer Display - Basketball scoreboard style rolling numbers.

This module provides animated digit displays for countdown timers with smooth
rolling/flipping animations when numbers change.

FEATURES:
- Smooth vertical rolling animation (like basketball scoreboards)
- Configurable animation speed and easing
- Support for minutes:seconds format (MM:SS)
- Automatic handling of digit changes
- Efficient - only animates digits that actually change

USAGE:
    from affilabs.widgets.animated_timer_display import AnimatedTimerDisplay

    timer = AnimatedTimerDisplay(parent=widget)
    timer.set_time(5, 30)  # 5 minutes, 30 seconds
    timer.update_time(5, 29)  # Smoothly animates to new time
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
    Qt,
    Property,
)
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget


class AnimatedDigit(QWidget):
    """Single animated digit that rolls vertically when value changes.

    Like a mechanical split-flap display or basketball scoreboard digit.
    """

    def __init__(self, parent=None, font_size: int = 16):
        """Initialize animated digit.

        Args:
            parent: Parent widget
            font_size: Font size for digit display
        """
        super().__init__(parent)

        self._current_value = 0
        self._next_value = 0
        self._animation_progress = 0.0  # 0.0 = showing current, 1.0 = showing next

        self.font_size = font_size
        self.setMinimumSize(int(font_size * 0.8), int(font_size * 1.4))

        # Animation
        self._animation = QPropertyAnimation(self, b"animation_progress")
        self._animation.setDuration(400)  # 400ms for smooth roll
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_animation_progress(self) -> float:
        """Get current animation progress (0.0 to 1.0)."""
        return self._animation_progress

    def set_animation_progress(self, value: float):
        """Set animation progress and trigger repaint.

        Args:
            value: Progress from 0.0 (current) to 1.0 (next)
        """
        self._animation_progress = value
        self.update()  # Trigger repaint

    # Qt Property for animation system
    animation_progress = Property(float, get_animation_progress, set_animation_progress)

    def set_value(self, value: int, animate: bool = True):
        """Set digit value with optional animation.

        Args:
            value: New digit value (0-9)
            animate: Whether to animate the transition
        """
        value = max(0, min(9, value))  # Clamp 0-9

        if value == self._current_value:
            return  # No change needed

        self._next_value = value

        if animate and self._animation:
            # Animate from current to next
            self._animation.stop()
            self._animation.setStartValue(0.0)
            self._animation.setEndValue(1.0)
            self._animation.finished.connect(self._on_animation_finished)
            self._animation.start()
        else:
            # Jump immediately
            self._current_value = value
            self._next_value = value
            self._animation_progress = 0.0
            self.update()

    def _on_animation_finished(self):
        """Called when animation completes - swap current/next values."""
        self._current_value = self._next_value
        self._animation_progress = 0.0
        self.update()

    def paintEvent(self, event):
        """Paint the digit with rolling animation effect."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Setup font
        font = QFont("Consolas", self.font_size, QFont.Weight.Bold)
        painter.setFont(font)

        rect = self.rect()
        digit_height = rect.height()

        # Calculate vertical offset based on animation progress
        # Progress 0.0 = current digit centered, 1.0 = next digit centered
        y_offset = -self._animation_progress * digit_height

        # Draw current digit (rolling up and out)
        if self._animation_progress < 1.0:
            current_opacity = max(0, 1.0 - self._animation_progress * 2.0)
            color = QColor(29, 29, 31, int(255 * current_opacity))
            painter.setPen(color)

            current_rect = QRect(0, int(y_offset), rect.width(), digit_height)
            painter.drawText(
                current_rect,
                Qt.AlignmentFlag.AlignCenter,
                str(self._current_value)
            )

        # Draw next digit (rolling up from below)
        if self._animation_progress > 0.0:
            next_opacity = min(1.0, self._animation_progress * 2.0)
            color = QColor(29, 29, 31, int(255 * next_opacity))
            painter.setPen(color)

            next_rect = QRect(
                0,
                int(y_offset + digit_height),
                rect.width(),
                digit_height
            )
            painter.drawText(
                next_rect,
                Qt.AlignmentFlag.AlignCenter,
                str(self._next_value)
            )


class AnimatedTimerDisplay(QWidget):
    """Animated timer display showing MM:SS with rolling digit animations."""

    def __init__(self, parent=None, font_size: int = 16, compact: bool = False):
        """Initialize animated timer display.

        Args:
            parent: Parent widget
            font_size: Font size for digits
            compact: If True, show compact MM:SS, else show full format
        """
        super().__init__(parent)

        self.font_size = font_size
        self.compact = compact

        # Create 4 digit widgets (MM:SS)
        self.minute_tens = AnimatedDigit(self, font_size)
        self.minute_ones = AnimatedDigit(self, font_size)
        self.second_tens = AnimatedDigit(self, font_size)
        self.second_ones = AnimatedDigit(self, font_size)

        self._setup_layout()

    def _setup_layout(self):
        """Setup widget layout with digits and colon separator."""
        from PySide6.QtWidgets import QHBoxLayout, QLabel

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Minutes
        layout.addWidget(self.minute_tens)
        layout.addWidget(self.minute_ones)

        # Colon separator
        colon = QLabel(":")
        colon.setStyleSheet(f"""
            QLabel {{
                font-size: {self.font_size}px;
                font-weight: bold;
                color: #1D1D1F;
                font-family: 'Consolas';
                padding: 0px 2px;
            }}
        """)
        layout.addWidget(colon)

        # Seconds
        layout.addWidget(self.second_tens)
        layout.addWidget(self.second_ones)

    def set_time(self, minutes: int, seconds: int, animate: bool = True):
        """Update timer display with optional animation.

        Args:
            minutes: Minutes value (0-999)
            seconds: Seconds value (0-59)
            animate: Whether to animate digit changes
        """
        # Clamp values
        minutes = max(0, min(999, minutes))
        seconds = max(0, min(59, seconds))

        # Extract individual digits
        min_tens = (minutes // 10) % 10
        min_ones = minutes % 10
        sec_tens = seconds // 10
        sec_ones = seconds % 10

        # Update each digit (only animates if value changed)
        self.minute_tens.set_value(min_tens, animate)
        self.minute_ones.set_value(min_ones, animate)
        self.second_tens.set_value(sec_tens, animate)
        self.second_ones.set_value(sec_ones, animate)

    def update_time(self, minutes: int, seconds: int):
        """Update time with animation (convenience method).

        Args:
            minutes: Minutes value
            seconds: Seconds value
        """
        self.set_time(minutes, seconds, animate=True)

    def sizeHint(self):
        """Recommended size for the widget."""
        from PySide6.QtCore import QSize
        digit_width = int(self.font_size * 0.8)
        digit_height = int(self.font_size * 1.4)
        total_width = digit_width * 4 + 20  # 4 digits + colon + spacing
        return QSize(total_width, digit_height)
