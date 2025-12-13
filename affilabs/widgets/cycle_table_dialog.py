"""Cycle Data Table Dialog - Popup window for managing cycle data."""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsEllipseItem,
    QGraphicsScene,
    QTableWidgetItem,
)

from settings import CH_LIST
from ui.ui_cycle_table_dialog import Ui_CycleTableDialog
from widgets.delegates import CycleTypeDelegate, TextInputDelegate
from widgets.table_manager import CycleTableManager


class CycleTableDialog(QDialog):
    """Dialog for displaying and editing cycle data table."""

    # Signals for communicating with parent
    row_deleted_sig = Signal()
    row_restored_sig = Signal()
    cell_edited_sig = Signal(int, int)  # row, column
    table_toggled_sig = Signal()

    def __init__(self, parent=None):
        """Initialize the cycle table dialog."""
        super().__init__(parent)
        self.ui = Ui_CycleTableDialog()
        self.ui.setupUi(self)

        # Set dialog properties
        self.setWindowFlags(Qt.WindowType.Window)
        self.setModal(False)  # Allow interaction with main window
        self.resize(900, 600)

        # Connect buttons
        self.ui.delete_row_btn.clicked.connect(self._on_delete_row)
        self.ui.add_row_btn.clicked.connect(self._on_restore_row)
        self.ui.table_toggle.clicked.connect(self._on_table_toggle)

        # Set up delegates
        cycle_type_delegate = CycleTypeDelegate(self.ui.data_table)
        self.ui.data_table.setItemDelegateForColumn(8, cycle_type_delegate)

        text_delegate_name = TextInputDelegate(self.ui.data_table)
        text_delegate_note = TextInputDelegate(self.ui.data_table)
        self.ui.data_table.setItemDelegateForColumn(0, text_delegate_name)
        self.ui.data_table.setItemDelegateForColumn(9, text_delegate_note)

        # Connect table signals
        self.ui.data_table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.ui.data_table.cellClicked.connect(self._on_cell_clicked)

        # Set up page indicator
        self.ui.page_indicator.setScene(QGraphicsScene())
        self.circles = (
            QGraphicsEllipseItem(-4, 0, 5, 5),
            QGraphicsEllipseItem(4, 0, 5, 5),
        )
        for c in self.circles:
            self.ui.page_indicator.scene().addItem(c)

        # Initialize table manager
        self.table_manager = CycleTableManager(
            table_widget=self.ui.data_table,
            toggle_indicators=self.circles
        )

        # Reference to parent's data
        self.saved_segments = None
        self.deleted_segment = None

    def set_segment_data(self, saved_segments, deleted_segment):
        """Set references to parent's segment data."""
        self.saved_segments = saved_segments
        self.deleted_segment = deleted_segment

    def _on_delete_row(self):
        """Handle delete row button click."""
        self.row_deleted_sig.emit()

    def _on_restore_row(self):
        """Handle restore row button click."""
        self.row_restored_sig.emit()

    def _on_table_toggle(self):
        """Handle table toggle button click."""
        self.table_toggled_sig.emit()

    def _on_cell_double_clicked(self, row, column):
        """Handle cell double click."""
        self.cell_edited_sig.emit(row, column)

    def _on_cell_clicked(self, row, column):
        """Handle cell click."""
        # Parent will handle view mode logic
        pass

    def add_table_row(self, row: int, seg, name: str, cycle_type: str, note: str):
        """Add a row to the table."""
        self.ui.data_table.blockSignals(True)
        self.ui.data_table.insertRow(row)

        # Populate the row
        self.ui.data_table.setItem(row, 0, QTableWidgetItem(name))
        self.ui.data_table.setItem(row, 1, QTableWidgetItem(f"{seg.start:.2f}"))
        self.ui.data_table.setItem(row, 2, QTableWidgetItem(f"{seg.end:.2f}"))
        self.ui.data_table.setItem(row, 3, QTableWidgetItem(f"{seg.shift['a']:.3f}"))
        self.ui.data_table.setItem(row, 4, QTableWidgetItem(f"{seg.shift['b']:.3f}"))
        self.ui.data_table.setItem(row, 5, QTableWidgetItem(f"{seg.shift['c']:.3f}"))
        self.ui.data_table.setItem(row, 6, QTableWidgetItem(f"{seg.shift['d']:.3f}"))
        self.ui.data_table.setItem(row, 7, QTableWidgetItem(f"{seg.ref_ch}"))
        self.ui.data_table.setItem(row, 8, QTableWidgetItem(cycle_type))
        self.ui.data_table.setItem(row, 9, QTableWidgetItem(note))

        # Ensure all cells exist
        for col in range(self.ui.data_table.columnCount()):
            if self.ui.data_table.item(row, col) is None:
                self.ui.data_table.setItem(row, col, QTableWidgetItem(""))

        self.ui.data_table.blockSignals(False)

    def update_table_row(self, row: int, seg, name: str, cycle_type: str, note: str):
        """Update an existing row in the table."""
        self.ui.data_table.blockSignals(True)

        self.ui.data_table.setItem(row, 0, QTableWidgetItem(name))
        self.ui.data_table.setItem(row, 1, QTableWidgetItem(f"{seg.start:.2f}"))
        self.ui.data_table.setItem(row, 2, QTableWidgetItem(f"{seg.end:.2f}"))
        self.ui.data_table.setItem(row, 3, QTableWidgetItem(f"{seg.shift['a']:.3f}"))
        self.ui.data_table.setItem(row, 4, QTableWidgetItem(f"{seg.shift['b']:.3f}"))
        self.ui.data_table.setItem(row, 5, QTableWidgetItem(f"{seg.shift['c']:.3f}"))
        self.ui.data_table.setItem(row, 6, QTableWidgetItem(f"{seg.shift['d']:.3f}"))
        self.ui.data_table.setItem(row, 7, QTableWidgetItem(f"{seg.ref_ch}"))
        self.ui.data_table.setItem(row, 8, QTableWidgetItem(cycle_type))
        self.ui.data_table.setItem(row, 9, QTableWidgetItem(note))

        self.ui.data_table.blockSignals(False)

    def clear_table(self):
        """Clear all rows from the table."""
        self.ui.data_table.setRowCount(0)

    def get_current_row(self) -> int:
        """Get the currently selected row."""
        return self.ui.data_table.currentRow()

    def get_row_count(self) -> int:
        """Get the total number of rows."""
        return self.ui.data_table.rowCount()

    def get_cell_text(self, row: int, col: int) -> str:
        """Get text from a specific cell."""
        item = self.ui.data_table.item(row, col)
        return item.text() if item else ""

    def remove_row(self, row: int):
        """Remove a row from the table."""
        self.ui.data_table.removeRow(row)

    def clear_selection(self):
        """Clear table selection."""
        self.ui.data_table.clearSelection()

    def toggle_table_style(self):
        """Toggle table display style using table manager."""
        self.table_manager.toggle_display_mode()
