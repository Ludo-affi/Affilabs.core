"""Intelligence Bar Widget

A status bar widget that shows real-time system intelligence and guidance.
Can be used across different tabs with customizable colors and messages.

Author: Affilabs
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from affilabs.core.system_intelligence import (
    SystemState,
    get_system_intelligence,
)


class IntelligenceBar(QFrame):
    """Compact status bar showing system intelligence and guidance.

    Features:
    - Color-coded status indicator
    - Dynamic status messages
    - Auto-updates from System Intelligence
    - Customizable gradient colors per tab
    """

    def __init__(
        self,
        context: str = "general",
        gradient_start: str = "#2E5CFF",
        gradient_end: str = "#4A90FF",
        message_callback=None,
        parent=None,
    ):
        """Initialize intelligence bar.

        Args:
            context: Context identifier ('method', 'flow', 'settings')
            gradient_start: Starting color for gradient background
            gradient_end: Ending color for gradient background
            message_callback: Optional function that returns (message, color) tuple for custom status
            parent: Parent widget
        """
        super().__init__(parent)
        self.context = context
        self.message_callback = message_callback
        self.system_intelligence = get_system_intelligence()

        self._setup_ui(gradient_start, gradient_end)
        self._setup_timer()

        # Initial update
        self.update_status()

    def _setup_ui(self, gradient_start: str, gradient_end: str):
        """Set up the UI components."""
        self.setObjectName(f"intelligence_bar_{self.context}")
        self.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
                padding: 0px;
            }
        """)
        self.setFixedHeight(24)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        # Status indicator dot
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("font-size: 12px; color: #007AFF;")
        layout.addWidget(self.status_dot)

        # Status message
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            "font-size: 12px; "
            "color: #007AFF; "
            "background: transparent; "
            "font-weight: 600; "
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        layout.addWidget(self.status_label)

        layout.addStretch()

    def _setup_timer(self):
        """Set up auto-update timer (every 5 seconds)."""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(5000)  # 5 seconds

    def update_status(self):
        """Update status based on System Intelligence or custom callback."""
        # If custom callback provided, use it
        if self.message_callback:
            try:
                result = self.message_callback()
                if isinstance(result, tuple) and len(result) == 2:
                    message, color = result
                    self.status_label.setText(message)
                    self.status_dot.setStyleSheet(f"color: {color}; font-size: 16px;")
                    return
            except Exception:
                pass  # Fall back to default behavior

        # Default: use System Intelligence
        state, issues = self.system_intelligence.diagnose_system()

        # Update status dot color
        status_colors = {
            SystemState.HEALTHY: "#007AFF",
            SystemState.DEGRADED: "#FF9500",
            SystemState.WARNING: "#FF9500",
            SystemState.ERROR: "#FF3B30",
            SystemState.UNKNOWN: "#8E8E93",
        }
        color = status_colors.get(state, "#8E8E93")
        self.status_dot.setStyleSheet(f"font-size: 12px; color: {color};")

        # Update text color to match
        self.status_label.setStyleSheet(
            f"font-size: 12px; "
            f"color: {color}; "
            f"background: transparent; "
            f"font-weight: 600; "
            f"font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )

        # Update status message based on context and state
        message = self._get_context_message(state, issues)
        self.status_label.setText(message)

    def _get_context_message(self, state: SystemState, issues: list) -> str:
        """Get context-appropriate status message.

        Args:
            state: Current system state
            issues: List of active issues

        Returns:
            Status message string
        """
        # If there are critical issues, show first one
        if issues:
            critical = [i for i in issues if i.severity.value == "critical"]
            if critical:
                return f"⚠ {critical[0].title}"
            return f"⚡ {issues[0].title}"

        # Default messages by context
        context_messages = {
            "method": {
                SystemState.HEALTHY: "Ready • Configure cycles and build methods",
                SystemState.DEGRADED: "Caution • System operational with degraded performance",
                SystemState.WARNING: "Warning • Check system status",
                SystemState.ERROR: "Error • System check required",
                SystemState.UNKNOWN: "Unknown • Initializing...",
            },
            "flow": {
                SystemState.HEALTHY: "Idle • Configure flow rates and pumps",
                SystemState.DEGRADED: "Caution • Fluidics operational with warnings",
                SystemState.WARNING: "Warning • Check pump/valve status",
                SystemState.ERROR: "Error • Fluidics check required",
                SystemState.UNKNOWN: "Unknown • Initializing...",
            },
            "settings": {
                SystemState.HEALTHY: "Ready • Configure hardware and calibration",
                SystemState.DEGRADED: "Caution • Hardware operational with warnings",
                SystemState.WARNING: "Warning • Check calibration quality",
                SystemState.ERROR: "Error • Calibration required",
                SystemState.UNKNOWN: "Unknown • Initializing...",
            },
        }

        messages = context_messages.get(self.context, context_messages["method"])
        return messages.get(state, "Ready")

    def set_custom_message(self, message: str, color: str = "#007AFF"):
        """Set a custom status message (overrides auto-update until next timer).

        Args:
            message: Custom message to display
            color: Color for status dot and text (CSS color name or hex)
        """
        self.status_label.setText(message)
        self.status_dot.setStyleSheet(f"font-size: 12px; color: {color};")
        self.status_label.setStyleSheet(
            f"font-size: 12px; "
            f"color: {color}; "
            f"background: transparent; "
            f"font-weight: 600; "
            f"font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )

    def cleanup(self):
        """Stop timer and cleanup resources."""
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
