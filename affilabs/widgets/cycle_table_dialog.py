"""Cycle Data Table Dialog - Popup window for managing cycle data."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsEllipseItem,
    QGraphicsScene,
    QTableWidgetItem,
)

from affilabs.ui.ui_cycle_table_dialog import Ui_CycleTableDialog
from affilabs.widgets.delegates import CycleTypeDelegate, TextInputDelegate
from affilabs.widgets.table_manager import CycleTableManager


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
            toggle_indicators=self.circles,
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

    def load_cycles(self, cycles: list):
        """Load cycle data into the table.

        Shows queued cycles with their current data. Matches Excel export format
        from Cycle.to_export_dict() for consistency.

        Args:
            cycles: List of Cycle objects from the queue
        """
        self.clear_table()

        # Set column count and headers to match Excel export
        self.ui.data_table.setColumnCount(11)
        self.ui.data_table.setHorizontalHeaderLabels([
            "#",                    # Column 0: Cycle number
            "Type",                 # Column 1: Cycle type
            "Duration (min)",       # Column 2: Length in minutes
            "Start (s)",            # Column 3: Start time in sensorgram
            "Conc.",                # Column 4: Concentration value
            "Units",                # Column 5: Concentration units
            "ΔSP R",                # Column 6: Delta SPR (if calculated)
            "Flags",                # Column 7: Flags (injection, wash, spike)
            "Status",               # Column 8: pending/running/completed
            "Note",                 # Column 9: User notes
            "ID"                    # Column 10: Cycle ID
        ])

        if not cycles:
            return

        # Set row count
        self.ui.data_table.setRowCount(len(cycles))

        # Populate rows
        for row, cycle in enumerate(cycles):
            # Column 0: Cycle number (position in queue)
            self.ui.data_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))

            # Column 1: Type
            self.ui.data_table.setItem(row, 1, QTableWidgetItem(cycle.type))

            # Column 2: Duration (minutes) - matches duration_minutes in export
            self.ui.data_table.setItem(row, 2, QTableWidgetItem(f"{cycle.length_minutes:.1f}"))

            # Column 3: Start Time - matches start_time_sensorgram in export
            start_text = f"{cycle.sensorgram_time:.1f}" if cycle.sensorgram_time else "—"
            self.ui.data_table.setItem(row, 3, QTableWidgetItem(start_text))

            # Column 4: Concentration value - matches concentration_value in export
            if cycle.concentrations:
                # Multi-channel concentrations - format as "A:100, B:50"
                conc_parts = [f"{ch}:{val}" for ch, val in sorted(cycle.concentrations.items())]
                conc_text = ', '.join(conc_parts)
            elif cycle.concentration_value is not None:
                conc_text = f"{cycle.concentration_value:.2f}"
            else:
                conc_text = "—"
            self.ui.data_table.setItem(row, 4, QTableWidgetItem(conc_text))

            # Column 5: Units - matches concentration_units/units in export
            units_text = cycle.concentration_units if cycle.concentration_units else cycle.units
            self.ui.data_table.setItem(row, 5, QTableWidgetItem(units_text))

            # Column 6: Delta SPR - matches delta_spr in export
            delta_text = f"{cycle.delta_spr:.1f}" if cycle.delta_spr is not None else "—"
            self.ui.data_table.setItem(row, 6, QTableWidgetItem(delta_text))

            # Column 7: Flags - matches flags in export (capitalised for display)
            flags_text = ", ".join(f.capitalize() for f in cycle.flags) if cycle.flags else "—"
            self.ui.data_table.setItem(row, 7, QTableWidgetItem(flags_text))

            # Column 8: Status (pending/running/completed)
            status_icon = {"pending": "⏳", "running": "▶️", "completed": "✅", "cancelled": "❌"}
            status_display = f"{status_icon.get(cycle.status, '')} {cycle.status}"
            self.ui.data_table.setItem(row, 8, QTableWidgetItem(status_display))

            # Column 9: Note - matches note in export
            self.ui.data_table.setItem(row, 9, QTableWidgetItem(cycle.note))

            # Column 10: Cycle ID - matches cycle_id in export
            self.ui.data_table.setItem(row, 10, QTableWidgetItem(str(cycle.cycle_id)))

        # Resize columns to content
        self.ui.data_table.resizeColumnsToContents()
