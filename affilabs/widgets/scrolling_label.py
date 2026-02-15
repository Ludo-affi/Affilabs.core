"""Scrolling Label Widget - Displays text with right-to-left scrolling animation.

A custom QLabel that automatically scrolls text from right to left when the text
is too long to fit in the available width.
"""

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPainter, QFontMetrics
from PySide6.QtWidgets import QWidget


class ScrollingLabel(QWidget):
    """QWidget with automatic right-to-left scrolling for long text.

    When text exceeds the widget width, it automatically scrolls from right to left.
    The scroll speed can be customized.
    """

    def __init__(self, text: str = "", parent=None):
        """Initialize scrolling label.

        Args:
            text: Initial text to display
            parent: Parent widget
        """
        super().__init__(parent)

        # Scrolling state
        self._text = text
        self._scroll_offset = 0
        self._scroll_enabled = False

        # Timer for smooth scrolling
        self._scroll_timer = QTimer(self)
        self._scroll_timer.timeout.connect(self._update_scroll)
        self._scroll_speed = 30  # milliseconds per update
        self._scroll_step = 2  # pixels to move per update

        # Padding between text repetitions (pixels)
        self._text_padding = 50

        # Set minimum height
        self.setMinimumHeight(20)

    def setText(self, text: str):
        """Set the text to display.

        Args:
            text: New text to display
        """
        self._text = text
        self._scroll_offset = 0
        self._check_if_scrolling_needed()
        self.update()  # Trigger repaint

    def text(self) -> str:
        """Get the current text.

        Returns:
            Current text string
        """
        return self._text

    def _check_if_scrolling_needed(self):
        """Check if text exceeds widget width and start/stop scrolling accordingly."""
        if not self._text:
            self._stop_scrolling()
            return

        # Get text width using font metrics
        fm = QFontMetrics(self.font())
        text_width = fm.horizontalAdvance(self._text)
        widget_width = self.width()

        if text_width > widget_width - 20:  # Leave some margin
            self._start_scrolling()
        else:
            self._stop_scrolling()

    def _start_scrolling(self):
        """Start the scrolling animation."""
        if not self._scroll_enabled:
            self._scroll_enabled = True
            self._scroll_offset = self.width()  # Start from right edge
            self._scroll_timer.start(self._scroll_speed)

    def _stop_scrolling(self):
        """Stop the scrolling animation."""
        if self._scroll_enabled:
            self._scroll_enabled = False
            self._scroll_timer.stop()
            self._scroll_offset = 0
            self.update()

    def _update_scroll(self):
        """Update scroll position and repaint."""
        if not self._text:
            return

        # Get the width of the full text
        fm = QFontMetrics(self.font())
        text_width = fm.horizontalAdvance(self._text)

        # Move text left
        self._scroll_offset -= self._scroll_step

        # Reset when text has completely scrolled off the left side
        if self._scroll_offset < -text_width - self._text_padding:
            self._scroll_offset = self.width()

        self.update()  # Trigger repaint

    def paintEvent(self, event):
        """Paint the scrolling text.

        Args:
            event: Paint event
        """
        super().paintEvent(event)

        if not self._text:
            return

        painter = QPainter(self)
        painter.setFont(self.font())

        # Get the stylesheet color (extract from stylesheet if set)
        painter.setPen(self.palette().color(self.foregroundRole()))

        fm = QFontMetrics(self.font())
        text_width = fm.horizontalAdvance(self._text)

        if self._scroll_enabled:
            # Draw the first instance of text
            painter.drawText(
                self._scroll_offset,
                fm.ascent(),
                self._text
            )

            # Draw the second instance for seamless loop (if the first is scrolling off)
            if self._scroll_offset < 0:
                painter.drawText(
                    self._scroll_offset + text_width + self._text_padding,
                    fm.ascent(),
                    self._text
                )
        else:
            # Draw static text (left-aligned)
            painter.drawText(
                0,
                fm.ascent(),
                self._text
            )

    def resizeEvent(self, event):
        """Handle widget resize to check if scrolling is needed.

        Args:
            event: Resize event
        """
        super().resizeEvent(event)
        self._check_if_scrolling_needed()

    def setScrollSpeed(self, milliseconds: int):
        """Set scroll speed in milliseconds per update.

        Args:
            milliseconds: Time between scroll updates (lower = faster)
        """
        self._scroll_speed = max(10, milliseconds)
        if self._scroll_enabled:
            self._scroll_timer.setInterval(self._scroll_speed)

    def setScrollStep(self, pixels: int):
        """Set how many pixels to scroll per update.

        Args:
            pixels: Number of pixels to move per update (higher = faster)
        """
        self._scroll_step = max(1, pixels)

    def setStyleSheet(self, styleSheet: str):
        """Override setStyleSheet to update the widget.

        Args:
            styleSheet: CSS stylesheet string
        """
        super().setStyleSheet(styleSheet)
        self.update()
