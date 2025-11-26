"""Data export and management panel for sidebar."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QPushButton, QLabel


class DataPanel(QWidget):
    """Data export and management controls panel."""

    export_triggered = Signal()
    export_excel_triggered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Set up the data panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # Export group
        export_group = QGroupBox("Export Data")
        export_layout = QVBoxLayout(export_group)
        export_layout.setSpacing(8)

        # Export to CSV button
        self.export_csv_btn = QPushButton("📄 Export to CSV/TXT")
        self.export_csv_btn.setToolTip("Export sensorgram data to CSV or text format")
        self.export_csv_btn.setStyleSheet(
            "QPushButton { "
            "background-color: #1A73E8; color: white; "
            "border-radius: 4px; padding: 10px; font-weight: 500; font-size: 13px; "
            "} "
            "QPushButton:hover { background-color: #1765CC; }"
        )
        self.export_csv_btn.clicked.connect(self.export_triggered.emit)
        export_layout.addWidget(self.export_csv_btn)

        # Export to Excel button
        self.export_excel_btn = QPushButton("📊 Export to Excel")
        self.export_excel_btn.setToolTip("Export data to Excel format (.xlsx) with multiple sheets")
        self.export_excel_btn.setStyleSheet(
            "QPushButton { "
            "background-color: #1E8E3E; color: white; "
            "border-radius: 4px; padding: 10px; font-weight: 500; font-size: 13px; "
            "} "
            "QPushButton:hover { background-color: #188038; }"
        )
        self.export_excel_btn.clicked.connect(self.export_excel_triggered.emit)
        export_layout.addWidget(self.export_excel_btn)

        # Info label
        info_label = QLabel(
            "Export current sensorgram data to various formats. "
            "Excel export includes raw data, filtered data, and statistics."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #5F6368; font-size: 11px; padding: 4px;")
        export_layout.addWidget(info_label)

        layout.addWidget(export_group)

        # Add stretch to push content to top
        layout.addStretch(1)
