"""Standalone Cycle Table Dialog - Full cycle data table in popup window."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from affilabs.ui_styles import Colors, Fonts


class CycleTableDialog(QDialog):
    """Dialog window displaying full cycle data table with filtering and export."""

    # Signals for data operations
    cycle_selected = Signal(int)  # Emitted when a cycle row is selected
    cycle_deleted = Signal(int)  # Emitted when a cycle is deleted
    cycle_edited = Signal(int, str, object)  # row, column_name, new_value

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cycle Data Table")
        self.setModal(False)  # Allow interaction with main window
        self.resize(1000, 700)
        self.setStyleSheet("""
            QDialog {
                background: #F8F9FA;
            }
        """)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header section
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        # Title
        title_label = QLabel("Cycle Data")
        title_label.setStyleSheet(
            "QLabel {"
            "  font-size: 18px;"
            "  font-weight: 700;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            f"  font-family: {Fonts.SYSTEM};"
            "}",
        )
        header_layout.addWidget(title_label)

        # Info label showing count
        self.count_label = QLabel("0 cycles")
        self.count_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  color: #86868B;"
            "  background: transparent;"
            f"  font-family: {Fonts.SYSTEM};"
            "}",
        )
        header_layout.addWidget(self.count_label)

        header_layout.addStretch()

        # Filter/Search section
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search cycles...")
        self.search_input.setFixedWidth(200)
        self.search_input.setStyleSheet(
            "QLineEdit {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "  padding: 6px 10px;"
            "  font-size: 13px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            "}"
            "QLineEdit:focus {"
            f"  border: 1px solid {Colors.PRIMARY_TEXT};"
            "}",
        )
        header_layout.addWidget(self.search_input)

        # Type filter
        self.type_filter = QComboBox()
        self.type_filter.addItems(
            ["All Types", "Auto-read", "Baseline", "Immobilization", "Concentration"],
        )
        self.type_filter.setFixedWidth(150)
        self.type_filter.setStyleSheet(
            "QComboBox {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "  padding: 6px 10px;"
            "  font-size: 13px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            "}"
            "QComboBox::drop-down {"
            "  border: none;"
            "  width: 20px;"
            "}"
            "QComboBox::down-arrow {"
            "  image: none;"
            "  border-left: 4px solid transparent;"
            "  border-right: 4px solid transparent;"
            "  border-top: 5px solid #86868B;"
            "  margin-right: 8px;"
            "}"
            "QComboBox QAbstractItemView {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  selection-background-color: rgba(0, 0, 0, 0.06);"
            f"  selection-color: {Colors.PRIMARY_TEXT};"
            "  outline: none;"
            "}",
        )
        header_layout.addWidget(self.type_filter)

        main_layout.addLayout(header_layout)

        # Table container with card styling
        table_container = QFrame()
        table_container.setStyleSheet(
            "QFrame {"
            "  background: white;"
            "  border: none;"
            "  border-radius: 12px;"
            "}",
        )
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        # Create table with Cycle-aligned columns (removed Ref Ch, Unit, and ID)
        self.cycle_table = QTableWidget(0, 13)
        self.cycle_table.setHorizontalHeaderLabels(
            [
                "Cycle",
                "Start",
                "End",
                "Shift A",
                "Shift B",
                "Shift C",
                "Shift D",
                "Cycle Type",
                "Cycle Time",
                "Note",
                "Flags",
                "Error",
                "Run",
            ],
        )

        # Configure table
        header = self.cycle_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        # Set column widths (13 columns total)
        self.cycle_table.setColumnWidth(0, 80)   # Cycle
        self.cycle_table.setColumnWidth(1, 100)  # Start
        self.cycle_table.setColumnWidth(2, 100)  # End
        self.cycle_table.setColumnWidth(3, 80)   # Shift A
        self.cycle_table.setColumnWidth(4, 80)   # Shift B
        self.cycle_table.setColumnWidth(5, 80)   # Shift C
        self.cycle_table.setColumnWidth(6, 80)   # Shift D
        self.cycle_table.setColumnWidth(7, 140)  # Cycle Type
        self.cycle_table.setColumnWidth(8, 90)   # Cycle Time
        self.cycle_table.setColumnWidth(9, 250)  # Note
        self.cycle_table.setColumnWidth(10, 120) # Flags
        self.cycle_table.setColumnWidth(11, 100) # Error
        self.cycle_table.setColumnWidth(12, 50)  # Run

        # Make Cycle Type column use fixed resize mode for dropdown
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)

        self.cycle_table.verticalHeader().setVisible(True)
        self.cycle_table.setAlternatingRowColors(True)
        self.cycle_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.cycle_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        self.cycle_table.setStyleSheet(
            "QTableWidget {"
            "  background: white;"
            "  border: none;"
            "  border-radius: 12px;"
            "  font-size: 12px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            "  gridline-color: rgba(0, 0, 0, 0.06);"
            "}"
            "QTableWidget::item {"
            "  padding: 8px;"
            "  border: none;"
            "}"
            "QTableWidget::item:selected {"
            "  background: rgba(0, 122, 255, 0.1);"
            f"  color: {Colors.PRIMARY_TEXT};"
            "}"
            "QTableWidget::item:alternate {"
            "  background: rgba(0, 0, 0, 0.02);"
            "}"
            "QHeaderView::section {"
            "  background: rgba(0, 0, 0, 0.03);"
            f"  color: {Colors.SECONDARY_TEXT};"
            "  padding: 8px;"
            "  border: none;"
            "  border-bottom: 1px solid rgba(0, 0, 0, 0.08);"
            "  font-weight: 600;"
            "  font-size: 11px;"
            f"  font-family: {Fonts.SYSTEM};"
            "}"
            "QHeaderView::section:first {"
            "  border-top-left-radius: 12px;"
            "}"
            "QHeaderView::section:last {"
            "  border-top-right-radius: 12px;"
            "}",
        )

        table_layout.addWidget(self.cycle_table)
        main_layout.addWidget(table_container)

        # Footer with action buttons
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(8)

        # Selection info
        self.selection_label = QLabel("No cycle selected")
        self.selection_label.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            f"  color: {Colors.SECONDARY_TEXT};"
            "  background: transparent;"
            f"  font-family: {Fonts.SYSTEM};"
            "}",
        )
        footer_layout.addWidget(self.selection_label)

        footer_layout.addStretch()

        # Action buttons
        self.delete_btn = QPushButton("🗑 Delete Selected")
        self.delete_btn.setFixedHeight(36)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setStyleSheet(
            "QPushButton {"
            "  background: #FF3B30;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 8px 16px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            f"  font-family: {Fonts.SYSTEM};"
            "}"
            "QPushButton:hover {"
            "  background: #FF2D24;"
            "}"
            "QPushButton:pressed {"
            "  background: #E02020;"
            "}"
            "QPushButton:disabled {"
            "  background: rgba(0, 0, 0, 0.1);"
            f"  color: {Colors.SECONDARY_TEXT};"
            "}",
        )
        footer_layout.addWidget(self.delete_btn)

        self.export_btn = QPushButton("📄 Export CSV")
        self.export_btn.setFixedHeight(36)
        self.export_btn.setStyleSheet(
            "QPushButton {"
            f"  background: {Colors.PRIMARY_TEXT};"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 8px 16px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            f"  font-family: {Fonts.SYSTEM};"
            "}"
            "QPushButton:hover {"
            "  background: #3A3A3C;"
            "}"
            "QPushButton:pressed {"
            "  background: #48484A;"
            "}",
        )
        footer_layout.addWidget(self.export_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.setFixedHeight(36)
        self.close_btn.setStyleSheet(
            "QPushButton {"
            "  background: #636366;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 8px 16px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            f"  font-family: {Fonts.SYSTEM};"
            "}"
            "QPushButton:hover {"
            "  background: #7C7C80;"
            "}"
            "QPushButton:pressed {"
            "  background: #8E8E93;"
            "}",
        )
        footer_layout.addWidget(self.close_btn)

        main_layout.addLayout(footer_layout)

        # Connect signals
        self._connect_signals()

    def _connect_signals(self):
        """Connect UI signals."""
        self.cycle_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.search_input.textChanged.connect(self._on_search_changed)
        self.type_filter.currentTextChanged.connect(self._on_filter_changed)
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        self.export_btn.clicked.connect(self._on_export_clicked)
        self.close_btn.clicked.connect(self.close)

    def _on_selection_changed(self):
        """Handle table selection change."""
        selected_rows = self.cycle_table.selectedItems()
        if selected_rows:
            row = self.cycle_table.currentRow()
            cycle_id = self.cycle_table.item(row, 0).text()
            self.selection_label.setText(f"Cycle #{cycle_id} selected")
            self.delete_btn.setEnabled(True)
            self.cycle_selected.emit(row)
        else:
            self.selection_label.setText("No cycle selected")
            self.delete_btn.setEnabled(False)

    def _on_search_changed(self, text: str):
        """Handle search text change."""
        # Filter table rows based on search text
        for row in range(self.cycle_table.rowCount()):
            match = False
            for col in range(self.cycle_table.columnCount()):
                item = self.cycle_table.item(row, col)
                if item and text.lower() in item.text().lower():
                    match = True
                    break
            self.cycle_table.setRowHidden(row, not match)

    def _on_filter_changed(self, filter_type: str):
        """Handle type filter change."""
        if filter_type == "All Types":
            # Show all rows
            for row in range(self.cycle_table.rowCount()):
                self.cycle_table.setRowHidden(row, False)
        else:
            # Filter by type
            for row in range(self.cycle_table.rowCount()):
                type_item = self.cycle_table.item(row, 1)
                if type_item:
                    self.cycle_table.setRowHidden(row, type_item.text() != filter_type)

    def _on_delete_clicked(self):
        """Handle delete button click."""
        row = self.cycle_table.currentRow()
        if row >= 0:
            cycle_id = self.cycle_table.item(row, 0).text()
            # Emit signal for parent to handle
            self.cycle_deleted.emit(row)
            # Remove from table
            self.cycle_table.removeRow(row)
            self._update_count()

    def _on_export_clicked(self):
        """Handle export button click."""
        # TODO: Implement CSV export
        print("Export CSV clicked")

    def load_cycles(self, cycles_data: list):
        """Load cycle data into the table.

        Args:
            cycles_data: List of dicts or Cycle objects

        """
        self.cycle_table.setRowCount(0)

        for cycle in cycles_data:
            row = self.cycle_table.rowCount()
            self.cycle_table.insertRow(row)

            # Handle both dict and object access
            def get_val(obj, key, default=None):
                if isinstance(obj, dict):
                    val = obj.get(key, default)
                    return val if val is not None else default
                return getattr(obj, key, default)

            # Column 0: Cycle (name or number)
            name = get_val(cycle, "name", f"{row + 1}")
            cycle_item = QTableWidgetItem(str(name))
            cycle_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cycle_table.setItem(row, 0, cycle_item)

            # Column 1: Start Time (sensorgram_time for Cycle objects, start for dicts)
            start_val = get_val(cycle, "sensorgram_time", None)
            if start_val is None:
                start_val = get_val(cycle, "start_time_sensorgram", 0.0)
            if start_val is None:
                start_val = 0.0
            start_item = QTableWidgetItem(f"{float(start_val):.2f}")
            self.cycle_table.setItem(row, 1, start_item)

            # Column 2: End Time (end_time_sensorgram for Cycle objects, end for dicts)
            end_val = get_val(cycle, "end_time_sensorgram", None)
            if end_val is None:
                end_val = get_val(cycle, "end", 0.0)
            if end_val is None:
                end_val = 0.0
            end_item = QTableWidgetItem(f"{float(end_val):.2f}")
            self.cycle_table.setItem(row, 2, end_item)

            # Columns 3-6: Shift A, B, C, D (all in nm)
            # Check if shift is a dict or get individual shift_a, shift_b, etc.
            shift = get_val(cycle, "shift", None)
            if shift and isinstance(shift, dict):
                for i, ch in enumerate(["a", "b", "c", "d"]):
                    shift_val = shift.get(ch, 0.0)
                    shift_item = QTableWidgetItem(f"{float(shift_val):.3f}")
                    shift_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.cycle_table.setItem(row, 3 + i, shift_item)
            else:
                # Try individual columns (SegmentDataFrame format)
                for i, ch in enumerate(["a", "b", "c", "d"]):
                    shift_val = get_val(cycle, f"shift_{ch}", 0.0)
                    shift_item = QTableWidgetItem(f"{float(shift_val):.3f}")
                    shift_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.cycle_table.setItem(row, 3 + i, shift_item)

            # Column 7: Cycle Type (editable with dropdown)
            cycle_type = str(get_val(cycle, "cycle_type", "Auto-read"))
            type_item = QTableWidgetItem(cycle_type)
            self.cycle_table.setItem(row, 7, type_item)

            # Column 8: Cycle Time
            cycle_time = get_val(cycle, "cycle_time", None)
            time_str = str(cycle_time) if cycle_time is not None else ""
            time_item = QTableWidgetItem(time_str)
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cycle_table.setItem(row, 8, time_item)

            # Column 9: Note
            note_item = QTableWidgetItem(str(get_val(cycle, "note", "")))
            self.cycle_table.setItem(row, 9, note_item)

            # Column 10: Flags (summary of channel flags)
            flags = get_val(cycle, "flags", None)
            if flags:
                # Format: "ChA: 2, ChC: 1" or similar
                flags_str = str(flags)
            else:
                flags_str = ""
            flags_item = QTableWidgetItem(flags_str)
            flags_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if flags_str:
                flags_item.setForeground(QColor("#FF9500"))  # Orange for flag indicator
            self.cycle_table.setItem(row, 10, flags_item)

            # Column 11: Error
            error = get_val(cycle, "error", None)
            error_str = str(error) if error else ""
            error_item = QTableWidgetItem(error_str)
            if error:
                error_item.setForeground(QColor("#FF3B30"))  # Red color for errors
            self.cycle_table.setItem(row, 11, error_item)

            # Column 12: Run (placeholder for future run/analysis button)
            run_item = QTableWidgetItem("")
            run_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cycle_table.setItem(row, 12, run_item)

        self._update_count()

    def _update_count(self):
        """Update the cycle count label."""
        count = self.cycle_table.rowCount()
        self.count_label.setText(f"{count} cycle{'s' if count != 1 else ''}")

    def add_cycle(self, cycle_data: dict):
        """Add a single cycle to the table."""
        self.load_cycles([cycle_data])  # Reuse load_cycles logic


# Test/Demo code
if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Create dialog
    dialog = CycleTableDialog()

    # Load sample data matching SegmentDataFrame structure
    sample_data = [
        {
            "seg_id": 0,
            "name": "1",
            "start": 0.0,
            "end": 300.0,
            "ref_ch": None,
            "unit": "RU",
            "shift_a": 0.0,
            "shift_b": 0.0,
            "shift_c": 0.0,
            "shift_d": 0.0,
            "cycle_type": "Baseline",
            "cycle_time": 5,
            "note": "Initial baseline measurement",
            "flags": None,
            "error": None,
        },
        {
            "seg_id": 1,
            "name": "2",
            "start": 300.0,
            "end": 900.0,
            "ref_ch": "a",
            "unit": "RU",
            "shift_a": 0.125,
            "shift_b": 0.143,
            "shift_c": 0.098,
            "shift_d": 0.112,
            "cycle_type": "Immobilization",
            "cycle_time": 10,
            "note": "Ligand immobilization on surface",
            "flags": "ChA: 1, ChB: 2",
            "error": None,
        },
        {
            "seg_id": 2,
            "name": "3",
            "start": 900.0,
            "end": 1200.0,
            "ref_ch": "a",
            "unit": "nM",
            "shift_a": 0.256,
            "shift_b": 0.289,
            "shift_c": 0.234,
            "shift_d": 0.267,
            "cycle_type": "Binding",
            "cycle_time": 5,
            "note": "[A:50] Analyte binding study",
            "flags": None,
            "error": None,
        },
        {
            "seg_id": 3,
            "name": "4",
            "start": 1200.0,
            "end": 1500.0,
            "ref_ch": "b",
            "unit": "RU",
            "shift_a": 0.389,
            "shift_b": 0.412,
            "shift_c": 0.356,
            "shift_d": 0.398,
            "cycle_type": "Auto-read",
            "cycle_time": None,
            "note": "Automated reading cycle",
            "flags": "ChD: 1",
            "error": None,
        },
        {
            "seg_id": 4,
            "name": "5",
            "start": 1500.0,
            "end": 1800.0,
            "ref_ch": "a",
            "unit": "RU",
            "shift_a": 0.0,
            "shift_b": 0.0,
            "shift_c": 0.0,
            "shift_d": 0.0,
            "cycle_type": "Baseline",
            "cycle_time": 5,
            "note": "Final baseline",
            "flags": None,
            "error": "Sensor drift detected",
        },
    ]

    dialog.load_cycles(sample_data)
    dialog.show()

    sys.exit(app.exec())
