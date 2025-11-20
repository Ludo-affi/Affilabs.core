"""Cycle Table Manager

Handles all cycle table operations including row management, column toggling,
data extraction, and styling. Extracted from datawindow.py to improve modularity.
Works with SegmentDataFrame for efficient pandas-based operations.
"""

from __future__ import annotations
from copy import deepcopy
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from widgets.ui_constants import COLUMNS_TO_TOGGLE
from utils.logger import logger

if TYPE_CHECKING:
    from widgets.datawindow import Segment
    from widgets.segment_dataframe import SegmentDataFrame

# Brush colors for table toggle indicators
ON_BRUSH = QBrush(Qt.GlobalColor.darkGray)
OFF_BRUSH = QBrush(Qt.GlobalColor.transparent)


class CycleTableManager:
    """Manages cycle table operations and styling.

    Responsibilities:
    - Row addition/deletion
    - Column toggle (Tab 1/Tab 2 view)
    - Data extraction from table cells
    - Table styling and indicators
    """

    def __init__(
        self,
        table_widget: QTableWidget,
        toggle_indicators: Optional[list] = None
    ):
        """Initialize table manager.

        Args:
            table_widget: The QTableWidget to manage
            toggle_indicators: Optional list of circle indicators for tab state
        """
        self.table = table_widget
        self.toggle_indicators = toggle_indicators or []
        self.hide_columns = True  # Default to Tab 1 (simplified view)

        # Initialize table style
        self.update_table_style()

    def update_table_style(self) -> None:
        """Update table column visibility based on current toggle state."""
        for column in COLUMNS_TO_TOGGLE:
            self.table.setColumnHidden(column, self.hide_columns)

        # Update toggle indicators if available
        if len(self.toggle_indicators) >= 2:
            if self.hide_columns:
                self.toggle_indicators[0].setBrush(ON_BRUSH)
                self.toggle_indicators[1].setBrush(OFF_BRUSH)
            else:
                self.toggle_indicators[0].setBrush(OFF_BRUSH)
                self.toggle_indicators[1].setBrush(ON_BRUSH)

    def toggle_table_style(self) -> None:
        """Toggle between Tab 1 (simplified) and Tab 2 (detailed) views."""
        self.hide_columns = not self.hide_columns
        self.update_table_style()

    def delete_row(
        self,
        row: Optional[int] = None,
        saved_segments: Optional[SegmentDataFrame] = None,
        first_available: bool = False
    ) -> Optional[Segment]:
        """Delete a row from the table.

        Args:
            row: Row index to delete (if None, uses current row)
            saved_segments: SegmentDataFrame to update
            first_available: If True, delete first row (row 0)

        Returns:
            The deleted segment, or None if no deletion occurred
        """
        if saved_segments is None or len(saved_segments) == 0:
            return None

        if first_available:
            self.table.removeRow(0)
            deleted_segment = saved_segments.pop(0)
            return deleted_segment

        if row is None:
            row = self.table.currentRow()

        if row < 0 or row >= len(saved_segments):
            return None

        deleted_segment = deepcopy(saved_segments[row])
        self.table.removeRow(row)
        del saved_segments[row]

        return deleted_segment

    def get_row_info(self, row: int) -> dict[str, str]:
        """Extract information from a table row.

        Args:
            row: Row index to extract data from

        Returns:
            Dictionary with 'name', 'cycle_type', and 'note' keys
        """
        name = ""
        cycle_type = "Auto-read"
        note = ""

        if self.table.rowCount() > row:
            name_item = self.table.item(row, 0)
            cycle_type_item = self.table.item(row, 8)
            note_item = self.table.item(row, 9)

            if name_item is not None:
                name = name_item.text()
            if cycle_type_item is not None:
                cycle_type = cycle_type_item.text()
            if note_item is not None:
                note = note_item.text()

        return {"name": name, "cycle_type": cycle_type, "note": note}

    def clear_all_rows(self, saved_segments: Optional[SegmentDataFrame] = None) -> None:
        """Clear all rows from the table.

        Args:
            saved_segments: SegmentDataFrame to clear (optional)
        """
        for _i in range(self.table.rowCount()):
            self.table.removeRow(0)

        if saved_segments is not None:
            saved_segments.clear()

    def get_current_row(self) -> int:
        """Get the currently selected row index.

        Returns:
            Current row index, or -1 if no row selected
        """
        return self.table.currentRow()

    def get_row_count(self) -> int:
        """Get the total number of rows in the table.

        Returns:
            Number of rows
        """
        return self.table.rowCount()

    def set_current_row(self, row: int) -> None:
        """Set the currently selected row.

        Args:
            row: Row index to select
        """
        if 0 <= row < self.table.rowCount():
            self.table.setCurrentCell(row, 0)

    def is_tab1_view(self) -> bool:
        """Check if table is in Tab 1 (simplified) view.

        Returns:
            True if in simplified view (columns hidden)
        """
        return self.hide_columns

    def is_tab2_view(self) -> bool:
        """Check if table is in Tab 2 (detailed) view.

        Returns:
            True if in detailed view (columns visible)
        """
        return not self.hide_columns

    def set_item_text(self, row: int, column: int, text: str) -> None:
        """Set text for a table cell.

        Args:
            row: Row index
            column: Column index
            text: Text to set
        """
        item = self.table.item(row, column)
        if item is None:
            item = QTableWidgetItem(text)
            self.table.setItem(row, column, item)
        else:
            item.setText(text)

    def get_item_text(self, row: int, column: int) -> str:
        """Get text from a table cell.

        Args:
            row: Row index
            column: Column index

        Returns:
            Cell text, or empty string if cell is None
        """
        item = self.table.item(row, column)
        return item.text() if item is not None else ""
