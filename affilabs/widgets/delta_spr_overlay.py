"""Delta SPR Overlay Widget - Real-time biosensing measurement display.

Displays cycle type, elapsed time, and delta RU values for all channels
as a floating overlay on the Active Cycle graph. Critical for biosensing
applications where ΔRU is the primary measurement of interest.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from affilabs.settings.settings import ACTIVE_GRAPH_COLORS


class DeltaSPROverlay(QWidget):
    """Floating overlay panel showing real-time Delta SPR measurements.

    Features:
    - Cycle type and timer display
    - Delta RU values for all 4 channels (color-coded)
    - Delta time between cursors
    - Semi-transparent background
    - Auto-updates during acquisition

    Positioned in top-right corner of Active Cycle graph.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        """Initialize overlay UI with modern styling."""
        # Make widget semi-transparent and frameless
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Container for styling
        container = QWidget()
        container.setStyleSheet(
            "QWidget {"
            "  background: rgba(30, 30, 30, 230);"  # Dark semi-transparent
            "  border: 1px solid rgba(255, 255, 255, 0.15);"
            "  border-radius: 8px;"
            "}"
        )
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(12, 10, 12, 10)
        container_layout.setSpacing(8)

        # Cycle type and timer row
        self.cycle_label = QLabel("-- (--:--/--:--)")
        self.cycle_label.setStyleSheet(
            "font-size: 13px;"
            "font-weight: 600;"
            "color: #FFFFFF;"
            "background: transparent;"
            "border: none;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        container_layout.addWidget(self.cycle_label)

        # Delta time label
        self.delta_time_label = QLabel("Δt = --s")
        self.delta_time_label.setStyleSheet(
            "font-size: 11px;"
            "font-weight: 500;"
            "color: #A0A0A0;"
            "background: transparent;"
            "border: none;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        container_layout.addWidget(self.delta_time_label)

        # Separator line
        separator = QLabel()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background: rgba(255, 255, 255, 0.1); border: none;")
        container_layout.addWidget(separator)

        # Channel delta grid (2x2 for A/B/C/D)
        delta_grid = QGridLayout()
        delta_grid.setSpacing(6)
        delta_grid.setContentsMargins(0, 4, 0, 0)

        self.channel_labels = {}

        # Create channel labels with color coding
        for i, ch in enumerate(["a", "b", "c", "d"]):
            label = QLabel(f"{ch.upper()}: -- RU")

            # Get color from active palette
            color = ACTIVE_GRAPH_COLORS[ch]
            if isinstance(color, tuple):
                color_str = f"rgb({color[0]}, {color[1]}, {color[2]})"
            else:
                color_str = color

            label.setStyleSheet(
                f"font-size: 12px;"
                f"font-weight: 600;"
                f"color: {color_str};"
                f"background: transparent;"
                f"border: none;"
                f"font-family: 'Consolas', 'Monaco', monospace;"  # Monospace for aligned numbers
            )

            # Add to grid (2x2 layout: A/B top, C/D bottom)
            row = i // 2
            col = i % 2
            delta_grid.addWidget(label, row, col)
            self.channel_labels[ch] = label

        container_layout.addLayout(delta_grid)
        layout.addWidget(container)

        # Set fixed size
        self.setFixedSize(200, 140)

    def update_cycle_info(self, cycle_type: str, elapsed_sec: float, total_sec: float):
        """Update cycle type and timer display.

        Args:
            cycle_type: Type of cycle (Baseline, Association, etc.)
            elapsed_sec: Elapsed time in seconds
            total_sec: Total cycle duration in seconds
        """
        elapsed_min = int(elapsed_sec // 60)
        elapsed_sec_rem = int(elapsed_sec % 60)
        total_min = int(total_sec // 60)
        total_sec_rem = int(total_sec % 60)

        self.cycle_label.setText(
            f"{cycle_type} ({elapsed_min:02d}:{elapsed_sec_rem:02d}/{total_min:02d}:{total_sec_rem:02d})"
        )

    def update_delta_time(self, delta_sec: float):
        """Update delta time between cursors.

        Args:
            delta_sec: Time difference in seconds
        """
        self.delta_time_label.setText(f"Δt = {delta_sec:.1f}s")

    def update_delta_ru(self, delta_values: dict):
        """Update delta RU values for all channels.

        Args:
            delta_values: Dictionary with channel deltas {ch: delta_ru}
                         Example: {"a": 145.2, "b": 167.8, "c": 132.4, "d": 158.9}
        """
        for ch, delta in delta_values.items():
            if ch in self.channel_labels:
                sign = "+" if delta >= 0 else ""
                self.channel_labels[ch].setText(f"{ch.upper()}: {sign}{delta:.1f} RU")

    def reset(self):
        """Reset overlay to default state."""
        self.cycle_label.setText("-- (--:--/--:--)")
        self.delta_time_label.setText("Δt = --s")
        for ch in self.channel_labels:
            self.channel_labels[ch].setText(f"{ch.upper()}: -- RU")
