"""Cycle Intelligence Footer Widget - Status and metadata display below Active Cycle graph.

Displays cycle information and system intelligence in a compact footer bar placed
below the cycle of interest graph. Users' eyes naturally rest on this area during
data acquisition, making it the ideal location for status and quick actions.

LAYOUT:
- Left: Auto-scrolling cycle metadata (marquee effect if too long)
- Right: Status indicators (build status, detection state, flag count, injection readiness)

FEATURES:
- Real-time updates as cycle properties change
- Apple HIG design matching existing UI
- Compact, non-intrusive footer bar
- Auto-scrolling marquee for long metadata
- Color-coded status indicators
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from affilabs.utils.logger import logger


class CycleIntelligenceFooter(QFrame):
    """Footer widget displaying cycle info and system intelligence below Active Cycle graph.

    Shows cycle metadata in auto-scrolling marquee and status indicators on right.
    Updates in real-time as cycle data changes.

    Attributes:
        cycle_data: Current cycle dictionary or None
        status_data: Current status dictionary {'build': str, 'detection': str, 'flags': int, 'injection': str}
    """

    def __init__(self, parent: QWidget | None = None):
        """Initialize cycle intelligence footer.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.cycle_data: dict[str, Any] | None = None
        self.status_data: dict[str, str | int] = {
            'build': '⚪ Not built',
            'detection': '⚪ Idle',
            'flags': 0,
            'injection': '⚪ Ready',
        }

        self.setMinimumHeight(48)
        self.setMaximumHeight(56)
        self.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border-top: 1px solid #E5E5EA;
                border-radius: 0px;
            }
        """)

        # Auto-scroll state
        self._scroll_offset = 0
        self._scroll_timer = QTimer(self)
        self._scroll_timer.timeout.connect(self._auto_scroll_step)
        self._full_metadata_text = ""

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build footer UI with left metadata panel and right status indicators."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 6, 12, 6)
        main_layout.setSpacing(16)

        # Left: Auto-scrolling metadata label (marquee effect)
        self._metadata_label = QLabel()
        self._metadata_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #1D1D1F;
                font-family: -apple-system, 'SF Pro Text', sans-serif;
            }
        """)
        self._metadata_label.setTextFormat(Qt.TextFormat.PlainText)
        # Create a container to clip overflow
        metadata_container = QFrame()
        metadata_container.setStyleSheet("QFrame { background: transparent; border: none; }")
        metadata_layout = QHBoxLayout(metadata_container)
        metadata_layout.setContentsMargins(0, 0, 0, 0)
        metadata_layout.addWidget(self._metadata_label)
        metadata_layout.addStretch()
        main_layout.addWidget(metadata_container, 1)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setStyleSheet("color: #E5E5EA;")
        main_layout.addWidget(divider)

        # Right: Status indicators
        status_layout = QHBoxLayout()
        status_layout.setSpacing(16)
        status_layout.setContentsMargins(0, 0, 0, 0)

        self._status_labels = {}

        for key in ['build', 'detection', 'flags', 'injection']:
            label = QLabel('⚪ —')
            label.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    font-weight: 500;
                    color: #666666;
                    font-family: -apple-system, 'SF Pro Text', sans-serif;
                }
            """)
            label.setToolTip(self._get_tooltip(key))
            self._status_labels[key] = label
            status_layout.addWidget(label)

        main_layout.addLayout(status_layout)

    def update_cycle_info(self, cycle_data: dict[str, Any] | None) -> None:
        """Update cycle metadata display.

        Args:
            cycle_data: Cycle dictionary with keys:
                - name: Cycle name (str)
                - type: Cycle type e.g. 'Baseline', 'Association' (str)
                - duration_minutes: Duration in minutes (float)
                - sample_id: Sample identifier (str, optional)
                - concentration: Concentration value (float, optional)
                - units: Concentration units (str, default 'nM')
                - note: User notes (str, optional)
                - channels: Target channels (str, optional)
        """
        self.cycle_data = cycle_data
        self._update_metadata_display()

    def update_status(self, status_data: dict[str, Any]) -> None:
        """Update status indicators.

        Args:
            status_data: Status dictionary with keys:
                - build: Build status message (str) e.g. '✅ Built'
                - detection: Detection status (str) e.g. '🟡 Monitoring'
                - flags: Flag count (int)
                - injection: Injection readiness (str) e.g. '✅ Ready'
        """
        self.status_data.update(status_data)
        self._update_status_display()

    def _update_metadata_display(self) -> None:
        """Update metadata text with auto-scroll if content is too long."""
        # Stop existing auto-scroll
        self._scroll_timer.stop()
        self._scroll_offset = 0

        if not self.cycle_data:
            self._metadata_label.setText('No cycle loaded')
            self._full_metadata_text = ''
            return

        # Build metadata text as compact string with separators
        items = []

        # Cycle name and type
        name = self.cycle_data.get('name', 'Unknown')
        cycle_type = self.cycle_data.get('type', '')
        if cycle_type:
            items.append(f"📊 {name} ({cycle_type})")
        else:
            items.append(f"📊 {name}")

        # Duration
        duration = self.cycle_data.get('duration_minutes', 0)
        if duration:
            items.append(f"⏱ {duration:.1f}min")

        # Sample info
        sample_id = self.cycle_data.get('sample_id')
        if sample_id:
            items.append(f"🧪 {sample_id}")

        # Concentration
        conc = self.cycle_data.get('concentration')
        if conc is not None:
            units = self.cycle_data.get('units', 'nM')
            items.append(f"🔬 {conc} {units}")

        # Channels
        channels = self.cycle_data.get('channels')
        if channels:
            items.append(f"📡 Ch: {channels}")

        # Notes
        note = self.cycle_data.get('note')
        if note:
            items.append(f"📝 {note}")

        # Join all items with separators
        self._full_metadata_text = "  •  ".join(items)

        # Set initial text
        self._metadata_label.setText(self._full_metadata_text)

        # Start auto-scroll after 1 second if text is wider than container
        QTimer.singleShot(1000, self._check_and_start_autoscroll)

    def _check_and_start_autoscroll(self) -> None:
        """Check if text is too long and start auto-scroll if needed."""
        if not self._full_metadata_text:
            return

        # Check if label width exceeds available space
        label_width = self._metadata_label.sizeHint().width()
        container_width = self._metadata_label.parent().width() if self._metadata_label.parent() else 0

        if label_width > container_width and container_width > 0:
            # Text is too long - start marquee scroll
            self._scroll_timer.start(50)  # Update every 50ms for smooth scroll

    def _auto_scroll_step(self) -> None:
        """Advance the auto-scroll animation one step."""
        if not self._full_metadata_text:
            self._scroll_timer.stop()
            return

        # Increment scroll offset
        self._scroll_offset += 1

        # Calculate character position based on offset
        text_len = len(self._full_metadata_text)

        # Create scrolling text by rotating characters
        # When we reach the end, loop back with a spacer
        spacer = "     •     "  # Visual separator between loops
        full_loop = self._full_metadata_text + spacer
        loop_len = len(full_loop)

        # Reset offset when we've scrolled through entire loop
        if self._scroll_offset >= loop_len:
            self._scroll_offset = 0

        # Extract visible portion (rotate the text)
        visible_text = (full_loop + full_loop)[self._scroll_offset:self._scroll_offset + text_len]
        self._metadata_label.setText(visible_text)

    def _update_status_display(self) -> None:
        """Update status indicator labels."""
        if 'build' in self._status_labels:
            build_status = self.status_data.get('build', '⚪ Not built')
            self._status_labels['build'].setText(build_status)
            self._status_labels['build'].setToolTip('Method build status')

        if 'detection' in self._status_labels:
            detection_status = self.status_data.get('detection', '⚪ Idle')
            self._status_labels['detection'].setText(detection_status)
            self._status_labels['detection'].setToolTip('Injection detection status')

        if 'flags' in self._status_labels:
            flag_count = self.status_data.get('flags', 0)
            flags_text = f"🚩 {flag_count}" if flag_count > 0 else "🚩 —"
            self._status_labels['flags'].setText(flags_text)
            self._status_labels['flags'].setToolTip(f'Flags placed: {flag_count}')

        if 'injection' in self._status_labels:
            injection_status = self.status_data.get('injection', '⚪ Ready')
            self._status_labels['injection'].setText(injection_status)
            self._status_labels['injection'].setToolTip('Manual injection readiness')

    def _get_tooltip(self, key: str) -> str:
        """Get tooltip text for status indicator."""
        tooltips = {
            'build': 'Method build status',
            'detection': 'Injection peak detection status',
            'flags': 'Number of flags placed on current cycle',
            'injection': 'Manual injection readiness',
        }
        return tooltips.get(key, '')
