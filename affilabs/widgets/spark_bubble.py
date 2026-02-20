"""SparkBubble — floating Sparq AI overlay panel.

A frameless child widget positioned over the main window bottom-right corner.
Zero layout impact: no splitter space consumed, available on every tab.
Toggle with toggle(). Repositions on parent resize via reposition().
"""

import logging
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsDropShadowEffect,
)
from PySide6.QtGui import QColor

logger = logging.getLogger(__name__)

_BUBBLE_W = 340
_BUBBLE_H = 500
_MARGIN_RIGHT = 16
_MARGIN_BOTTOM = 52   # clears the nav bar pill button row


class SparkBubble(QFrame):
    """Floating Sparq AI chat panel. Parented to main window, stacks above all content.

    Usage:
        bubble = SparkBubble(main_window)
        bubble.toggle()          # open / close
        bubble.reposition()      # call from resizeEvent
        bubble.push_troubleshooting(diagnosis, controller)  # from calibration_service
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SparkBubble")
        self.setFixedSize(_BUBBLE_W, _BUBBLE_H)
        self._spark_widget = None
        self._drag_offset = QPoint()
        try:
            self._setup_ui()
        except Exception as e:
            logger.error(f"SparkBubble setup failed (non-fatal): {e}")
        self.hide()

    # ──────────────────────────────────────────────────────────────────────
    # UI construction
    # ──────────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        self.setStyleSheet("""
            QFrame#SparkBubble {
                background: #FFFFFF;
                border-radius: 16px;
                border: 1px solid #E5E5EA;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 70))
        shadow.setOffset(0, 8)
        self.setGraphicsEffect(shadow)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header / drag handle ──────────────────────────────────────────
        self._header = QFrame()
        self._header.setFixedHeight(44)
        self._header.setStyleSheet("""
            QFrame {
                background: #F5F5F7;
                border-radius: 16px 16px 0px 0px;
                border-bottom: 1px solid #E5E5EA;
            }
        """)
        self._header.setCursor(Qt.CursorShape.SizeAllCursor)

        header_row = QHBoxLayout(self._header)
        header_row.setContentsMargins(14, 0, 10, 0)
        header_row.setSpacing(8)

        title = QLabel("✦ Sparq")
        title.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #1D1D1F;"
            " background: transparent; border: none;"
        )
        header_row.addWidget(title)
        header_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #86868B;
                font-size: 14px;
                font-weight: 500;
                border-radius: 12px;
            }
            QPushButton:hover { background: #E5E5EA; color: #1D1D1F; }
        """)
        close_btn.clicked.connect(self._close_and_uncheck)
        header_row.addWidget(close_btn)

        outer.addWidget(self._header)

        # ── Spark content ─────────────────────────────────────────────────
        content_frame = QFrame()
        content_frame.setStyleSheet(
            "QFrame { background: transparent; border: none; border-radius: 0px 0px 16px 16px; }"
        )
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        try:
            from affilabs.widgets.spark_help_widget import SparkHelpWidget
            self._spark_widget = SparkHelpWidget()
            content_layout.addWidget(self._spark_widget)
        except Exception as e:
            logger.error(f"SparkHelpWidget load failed in bubble (non-fatal): {e}")
            placeholder = QLabel("Sparq unavailable")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("color: #86868B; font-size: 12px; padding: 40px;")
            content_layout.addWidget(placeholder)

        outer.addWidget(content_frame, 1)

        # ── Drag support ──────────────────────────────────────────────────
        self._header.mousePressEvent = self._on_header_press
        self._header.mouseMoveEvent = self._on_header_move

    # ──────────────────────────────────────────────────────────────────────
    # Drag
    # ──────────────────────────────────────────────────────────────────────

    def _on_header_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def _on_header_move(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def toggle(self):
        """Show or hide. On show: repositions, raises to front."""
        if self.isVisible():
            self.hide()
        else:
            self._reposition()
            self.show()
            self.raise_()

    def reposition(self):
        """Call from main window resizeEvent to keep bubble anchored bottom-right."""
        if self.isVisible():
            self._reposition()

    def _reposition(self):
        parent = self.parent()
        if parent is None:
            return
        x = parent.width() - _BUBBLE_W - _MARGIN_RIGHT
        y = parent.height() - _BUBBLE_H - _MARGIN_BOTTOM
        self.move(max(0, x), max(0, y))

    def _close_and_uncheck(self):
        """Hide bubble and uncheck the nav bar toggle button."""
        self.hide()
        # Uncheck the pill button so it stays in sync
        parent = self.parent()
        if parent and hasattr(parent, 'spark_toggle_btn'):
            parent.spark_toggle_btn.setChecked(False)

    def push_troubleshooting(self, diagnosis: dict, controller) -> None:
        """Open bubble and start guided LED troubleshooting flow.

        Same API as SparkSidebar.push_troubleshooting — drop-in replacement
        for calibration_service calls.
        """
        try:
            if not self.isVisible():
                self.toggle()
            if self._spark_widget is not None and hasattr(
                self._spark_widget, 'start_troubleshooting_flow'
            ):
                self._spark_widget.start_troubleshooting_flow(diagnosis, controller)
        except Exception as e:
            logger.error(f"SparkBubble troubleshooting launch failed (non-fatal): {e}")
