"""Compact queue progress bar for real-time monitoring during runs.

Shows 3 cycles at a time: Previous (done) → Current (in progress) → Next (upcoming)
Designed to be embedded in sidebar for at-a-glance status.
"""

from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QFont, QPen
from typing import List, Optional


class QueueProgressBar(QWidget):
    """Compact horizontal progress bar showing 3-cycle context.

    Features:
    - Shows ONLY 3 cycles: Previous → Current → Next
    - Previous: Green checkmark (completed)
    - Current: Blue with progress/status
    - Next: Gray outline (upcoming)
    - Clean, focused design
    """

    cycle_clicked = Signal(int)  # Emits cycle index when clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cycles = []  # List of cycle data
        self.current_index = -1  # Index of currently running cycle
        self.completed_cycles = []  # List of completed cycle objects
        self.setMinimumHeight(65)
        self.setMaximumHeight(65)
        self.setStyleSheet(
            "QWidget { background: transparent; }"
        )

    def set_cycles(self, cycles: List[dict], completed_cycles: List = None):
        """Update the cycles to display.

        Args:
            cycles: List of pending cycle objects (queue)
            completed_cycles: List of completed cycle objects
        """
        self.cycles = cycles
        self.completed_cycles = completed_cycles or []
        self.update()

    def set_current_index(self, index: int):
        """Set which cycle is currently running.

        Args:
            index: Index of current cycle in overall sequence (-1 if none running)
        """
        self.current_index = index
        self.update()

    def paintEvent(self, event):
        """Draw the 3-cycle progress bar: Previous → Current → Next"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # Calculate 3 equal sections
        section_width = (width - 40) // 3
        block_height = 45
        y = (height - block_height) // 2

        # Get the 3 cycles to display
        previous_cycle = self.completed_cycles[-1] if self.completed_cycles else None
        current_cycle = None
        next_cycle = self.cycles[0] if self.cycles else None

        # If we're running a cycle, it's not in the queue anymore
        # So we need to track it separately (passed via set_current_index)
        # For now, assume first in queue is "current" if current_index == 0

        # Position for each section
        prev_x = 10
        curr_x = prev_x + section_width + 10
        next_x = curr_x + section_width + 10

        # === PREVIOUS CYCLE (Completed) ===
        if previous_cycle:
            self._draw_completed_cycle(painter, prev_x, y, section_width, block_height, previous_cycle)
        else:
            self._draw_empty_slot(painter, prev_x, y, section_width, block_height, "Previous")

        # === CURRENT CYCLE (In Progress) ===
        if next_cycle and self.current_index == 0:
            # Currently running the first cycle in queue
            current_cycle = next_cycle
            next_cycle = self.cycles[1] if len(self.cycles) > 1 else None

        if current_cycle:
            self._draw_current_cycle(painter, curr_x, y, section_width, block_height, current_cycle)
        else:
            self._draw_empty_slot(painter, curr_x, y, section_width, block_height, "Current")

        # === NEXT CYCLE (Upcoming) ===
        if next_cycle:
            self._draw_next_cycle(painter, next_x, y, section_width, block_height, next_cycle)
        else:
            self._draw_empty_slot(painter, next_x, y, section_width, block_height, "Next")

        painter.end()

    def _draw_completed_cycle(self, painter, x, y, width, height, cycle):
        """Draw a completed cycle with green checkmark."""
        # Green filled background
        painter.setPen(QPen(QColor(52, 199, 89), 2))
        painter.setBrush(QColor(52, 199, 89, 40))
        painter.drawRoundedRect(x, y, width, height, 8, 8)

        # Checkmark icon
        painter.setPen(QPen(QColor(52, 199, 89), 3))
        check_x = x + 10
        check_y = y + height // 2
        painter.drawLine(check_x, check_y, check_x + 6, check_y + 8)
        painter.drawLine(check_x + 6, check_y + 8, check_x + 16, check_y - 8)

        # Cycle name
        painter.setPen(QColor(52, 199, 89))
        font = QFont("SF Pro Text", 11, QFont.Weight.DemiBold)
        painter.setFont(font)
        name = cycle.name if hasattr(cycle, 'name') and cycle.name else cycle.type
        painter.drawText(x + 30, y, width - 30, height, Qt.AlignmentFlag.AlignVCenter, name[:12])

    def _draw_current_cycle(self, painter, x, y, width, height, cycle):
        """Draw current cycle with blue highlight and status."""
        # Blue filled background
        painter.setPen(QPen(QColor(0, 122, 255), 2))
        painter.setBrush(QColor(0, 122, 255, 60))
        painter.drawRoundedRect(x, y, width, height, 8, 8)

        # Cycle name (bold)
        painter.setPen(QColor(0, 122, 255))
        font = QFont("SF Pro Text", 12, QFont.Weight.Bold)
        painter.setFont(font)
        name = cycle.name if hasattr(cycle, 'name') and cycle.name else cycle.type
        painter.drawText(x + 10, y + 5, width - 20, 20, Qt.AlignmentFlag.AlignCenter, name[:15])

        # Status (smaller text below)
        painter.setPen(QColor(0, 122, 255, 200))
        font = QFont("SF Pro Text", 9)
        painter.setFont(font)
        painter.drawText(x + 10, y + 25, width - 20, 15, Qt.AlignmentFlag.AlignCenter, "In Progress...")

    def _draw_next_cycle(self, painter, x, y, width, height, cycle):
        """Draw next upcoming cycle with gray outline."""
        # Gray outlined background
        painter.setPen(QPen(QColor(134, 134, 139), 2))
        painter.setBrush(QColor(255, 255, 255, 0))
        painter.drawRoundedRect(x, y, width, height, 8, 8)

        # Cycle name
        painter.setPen(QColor(99, 99, 102))
        font = QFont("SF Pro Text", 11)
        painter.setFont(font)
        name = cycle.name if hasattr(cycle, 'name') and cycle.name else cycle.type
        painter.drawText(x + 10, y, width - 20, height, Qt.AlignmentFlag.AlignCenter, name[:15])

    def _draw_empty_slot(self, painter, x, y, width, height, label):
        """Draw an empty placeholder slot."""
        # Light gray dashed border
        painter.setPen(QPen(QColor(200, 200, 200), 1, Qt.PenStyle.DashLine))
        painter.setBrush(QColor(250, 250, 250))
        painter.drawRoundedRect(x, y, width, height, 8, 8)

        # Label
        painter.setPen(QColor(174, 174, 178))
        font = QFont("SF Pro Text", 10)
        painter.setFont(font)
        painter.drawText(x + 10, y, width - 20, height, Qt.AlignmentFlag.AlignCenter, label)
