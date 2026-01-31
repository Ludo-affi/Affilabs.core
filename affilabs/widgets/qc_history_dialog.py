"""QC History Dialog - View and compare historical calibration QC reports.

Provides access to all past calibration reports for:
- Performance tracking over time
- Quality control compliance
- Anomaly detection
- ML model input visualization
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from affilabs.utils.logger import logger


class QCHistoryDialog(QDialog):
    """Dialog for viewing historical QC reports."""

    def __init__(self, device_serial: str, parent=None):
        """Initialize QC history dialog.

        Args:
            device_serial: Device serial number
            parent: Parent widget

        """
        super().__init__(parent)
        self.device_serial = device_serial
        self.reports_list = []

        self.setWindowTitle(f"Calibration History - {device_serial}")
        self.setMinimumSize(1000, 600)
        self.setModal(True)

        self.setStyleSheet("""
            QDialog {
                background: #FFFFFF;
            }
            QLabel {
                color: #1D1D1F;
                font-size: 13px;
            }
            QPushButton {
                background: #007AFF;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #0051D5;
            }
            QTableWidget {
                border: 1px solid #D1D1D6;
                border-radius: 6px;
                background: white;
                gridline-color: #E5E5EA;
            }
            QHeaderView::section {
                background: #F5F5F7;
                color: #1D1D1F;
                padding: 8px;
                border: none;
                font-weight: 600;
            }
        """)

        self._setup_ui()
        self._load_reports()

    def _setup_ui(self):
        """Setup UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel(f"📊 Calibration History: {self.device_serial}")
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: 600;
            color: #1D1D1F;
            padding: 5px 0px;
        """)
        layout.addWidget(title)

        # Summary info
        self.summary_label = QLabel("Loading reports...")
        self.summary_label.setStyleSheet("color: #86868B;")
        layout.addWidget(self.summary_label)

        # Reports table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                "Date/Time",
                "Status",
                "Failed Channels",
                "Operator",
                "Actions",
                "File",
            ],
        )

        # Configure table appearance
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(4, 150)

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)

        # Double-click to view report
        self.table.cellDoubleClicked.connect(self._on_report_double_clicked)

        layout.addWidget(self.table)

        # Buttons
        button_layout = QHBoxLayout()

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._load_reports)
        button_layout.addWidget(refresh_btn)

        button_layout.addStretch()

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _load_reports(self):
        """Load and display QC reports."""
        try:
            from affilabs.managers.qc_report_manager import QCReportManager

            qc_manager = QCReportManager()

            self.reports_list = qc_manager.list_qc_reports(self.device_serial)

            # Update summary
            self.summary_label.setText(
                f"Found {len(self.reports_list)} calibration reports",
            )

            # Clear table completely before repopulating
            self.table.clearContents()
            self.table.setRowCount(0)
            
            # Populate table
            self.table.setRowCount(len(self.reports_list))
            
            # Set row height to prevent button overlap
            for r in range(len(self.reports_list)):
                self.table.setRowHeight(r, 40)

            for row, report_info in enumerate(self.reports_list):
                # Date/Time
                timestamp_item = QTableWidgetItem(
                    report_info["timestamp"][:19].replace("T", " "),
                )
                timestamp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 0, timestamp_item)

                # Status
                status = report_info["status"]
                status_item = QTableWidgetItem(status)
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if status == "PASS":
                    status_item.setForeground(Qt.GlobalColor.darkGreen)
                else:
                    status_item.setForeground(Qt.GlobalColor.red)
                self.table.setItem(row, 1, status_item)

                # Failed Channels
                failed = report_info["failed_channels"]
                failed_item = QTableWidgetItem(str(failed) if failed > 0 else "None")
                failed_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 2, failed_item)

                # Operator
                user_item = QTableWidgetItem(report_info["user"])
                self.table.setItem(row, 3, user_item)

                # Actions (View button)
                view_btn = QPushButton("View Report")
                view_btn.setMaximumWidth(120)  # Limit button width
                view_btn.setMinimumHeight(28)  # Set reasonable height
                view_btn.clicked.connect(lambda checked, r=row: self._view_report(r))
                self.table.setCellWidget(row, 4, view_btn)

                # Filename
                file_item = QTableWidgetItem(report_info["filename"])
                file_item.setToolTip(report_info["file_path"])
                self.table.setItem(row, 5, file_item)

            logger.info(f"Loaded {len(self.reports_list)} QC reports for display")

        except Exception as e:
            logger.error(f"Failed to load QC reports: {e}")
            self.summary_label.setText(f"Error loading reports: {e!s}")

    def _on_report_double_clicked(self, row: int, column: int):
        """Handle double-click on report row."""
        self._view_report(row)

    def _view_report(self, row: int):
        """Open full QC dialog for selected report.

        Args:
            row: Table row index

        """
        try:
            if row >= len(self.reports_list):
                return

            report_info = self.reports_list[row]

            from affilabs.managers.qc_report_manager import QCReportManager

            qc_manager = QCReportManager()

            # Extract timestamp from filename
            timestamp = (
                report_info["filename"].replace("qc_report_", "").replace(".json", "")
            )

            # Load full report
            report = qc_manager.load_qc_report(self.device_serial, timestamp)

            if report:
                # Extract calibration data from raw_calibration_data
                calibration_data = report.get("raw_calibration_data", {})

                # Show QC dialog
                from affilabs.widgets.calibration_qc_dialog import CalibrationQCDialog

                qc_dialog = CalibrationQCDialog(
                    parent=self,
                    calibration_data=calibration_data,
                )
                qc_dialog.exec()
            else:
                from affilabs.widgets.message import show_message

                show_message(
                    "Failed to load QC report.",
                    msg_type="Critical",
                    title="Error",
                )

        except Exception as e:
            logger.error(f"Failed to view report: {e}")
            from affilabs.widgets.message import show_message

            show_message(
                f"Failed to view report:\n{e!s}",
                msg_type="Critical",
                title="Error",
            )

    def _view_ml_features(self):
        """View ML features extracted from recent reports."""
        try:
            from affilabs.managers.qc_report_manager import QCReportManager

            qc_manager = QCReportManager()

            # Extract ML features from last 10 reports
            features = qc_manager.get_ml_features(self.device_serial, n_reports=10)

            if features and features.get("timestamps"):
                # Create simple display dialog
                from PySide6.QtWidgets import QDialog, QTextEdit

                ml_dialog = QDialog(self)
                ml_dialog.setWindowTitle("ML Feature Trends")
                ml_dialog.setMinimumSize(800, 600)

                layout = QVBoxLayout(ml_dialog)

                # Format features as text
                text_edit = QTextEdit()
                text_edit.setReadOnly(True)
                text_edit.setStyleSheet("font-family: monospace; font-size: 12px;")

                feature_text = "ML FEATURES FOR PREDICTIVE MAINTENANCE\n"
                feature_text += "=" * 60 + "\n\n"

                feature_text += f"Device Serial: {self.device_serial}\n"
                feature_text += f"Reports Analyzed: {len(features['timestamps'])}\n\n"

                feature_text += "SNR TRENDS (by channel):\n"
                for ch in ["a", "b", "c", "d"]:
                    values = [v for v in features["snr_trends"][ch] if v is not None]
                    if values:
                        feature_text += f"  Channel {ch.upper()}: {values}\n"

                feature_text += "\nPEAK COUNTS TRENDS:\n"
                for ch in ["a", "b", "c", "d"]:
                    values = [
                        v for v in features["peak_counts_trends"][ch] if v is not None
                    ]
                    if values:
                        feature_text += f"  Channel {ch.upper()}: {values}\n"

                feature_text += "\nMODEL ACCURACY:\n"
                feature_text += f"  S-pol: {[v for v in features['model_accuracy_s'] if v is not None]}\n"
                feature_text += f"  P-pol: {[v for v in features['model_accuracy_p'] if v is not None]}\n"

                feature_text += "\nCONVERGENCE ITERATIONS:\n"
                feature_text += f"  {[v for v in features['convergence_iterations'] if v is not None]}\n"

                feature_text += "\nDEVICE USAGE:\n"
                feature_text += f"  Hours: {[v for v in features['device_hours'] if v is not None]}\n"
                feature_text += f"  Failed Channels: {[v for v in features['failed_channels_count'] if v is not None]}\n"

                feature_text += "\n" + "=" * 60 + "\n"
                feature_text += "These features can be used for ML-based predictive maintenance models\n"
                feature_text += (
                    "to forecast calibration drift, LED degradation, and system health."
                )

                text_edit.setText(feature_text)
                layout.addWidget(text_edit)

                close_btn = QPushButton("Close")
                close_btn.clicked.connect(ml_dialog.accept)
                layout.addWidget(close_btn)

                ml_dialog.exec()

                logger.info("ML features displayed")
            else:
                from affilabs.widgets.message import show_message

                show_message(
                    "Not enough calibration history to extract ML features.\n\n"
                    "At least 2 calibrations required.",
                    "Insufficient Data",
                    "Information",
                )

        except Exception as e:
            logger.error(f"Failed to view ML features: {e}")
            from affilabs.widgets.message import show_message

            show_message(f"Failed to view ML features:\n{e!s}", "Error", "Error")
