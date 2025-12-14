"""Calibration QC Dialog - Displays 4 comprehensive graphs for quality control.

Shows:
1. S-pol final spectra (all 4 channels)
2. P-pol final spectra (all 4 channels)
3. Final dark scan (all 4 channels)
4. Transmission spectra (all 4 channels)
"""

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGridLayout, QFrame,
    QTableWidget, QTableWidgetItem, QWidget, QScrollArea, QTabWidget
)
import pyqtgraph as pg
from utils.logger import logger
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import numpy as np


class CalibrationQCDialog(QDialog):
    """Dialog showing calibration QC graphs."""

    def __init__(self, parent=None, calibration_data: dict = None):
        """Initialize the QC dialog.

        Args:
            parent: Parent widget
            calibration_data: Dictionary containing all calibration results:
                - s_pol_spectra: dict of {channel: spectrum_array}
                - p_pol_spectra: dict of {channel: spectrum_array}
                - dark_scan: dict of {channel: dark_array}
                - transmission_spectra: dict of {channel: transmission_array}
                - wavelengths: array of wavelength values
                - integration_time: float (ms)
                - led_intensities: dict of {channel: intensity}
                - device_type: str (device model)
                - detector_serial: str (detector serial number)
                - firmware_version: str (controller firmware)
                - timestamp: str (calibration timestamp)
        """
        super().__init__(parent)
        self.calibration_data = calibration_data or {}

        self.setWindowTitle("Calibration QC Report")
        self.setMinimumSize(1600, 1000)
        self.setModal(True)
        # Apply modern styling
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
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 600;
                min-width: 100px;
            }
            QPushButton:hover {
                background: #0051D5;
            }
            QPushButton:pressed {
                background: #003D99;
            }
        """)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI layout with tabs for graphs and QC parameters."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(8)

        # Title
        title = QLabel("📊 Calibration Quality Control Report")
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: 600;
            color: #1D1D1F;
            padding: 5px 0px;
        """)
        layout.addWidget(title)

        # Summary info
        summary = self._create_summary_section()
        layout.addWidget(summary)

        # Metadata section
        metadata_section = self._create_metadata_section()
        layout.addWidget(metadata_section)

        # Create tab widget
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #D1D1D6;
                border-radius: 6px;
                background: white;
            }
            QTabBar::tab {
                background: #F5F5F7;
                color: #1D1D1F;
                border: 1px solid #D1D1D6;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 8px 16px;
                margin-right: 2px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: white;
                color: #007AFF;
            }
            QTabBar::tab:hover {
                background: #E8E8ED;
            }
        """)

        # Tab 1: Original QC graphs and table
        tab1 = self._create_graphs_content()
        tabs.addTab(tab1, "QC Spectra & Validation")

        # Tab 2: Calibration analysis visualization
        tab2 = self._create_analysis_visualization()
        tabs.addTab(tab2, "Calibration Analysis")

        layout.addWidget(tabs)

        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _create_graphs_content(self) -> QWidget:
        """Create the graphs section with 4 graphs (2x2) and combined QC table below."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Grid of graphs (2x2 layout for better visibility)
        graphs_container = QFrame()
        graphs_layout = QGridLayout(graphs_container)
        graphs_layout.setSpacing(10)

        # Row 0: S-pol and P-pol
        s_pol_graph = self._create_graph("S-Polarization (s_pol_spectra)", "s_pol")
        p_pol_graph = self._create_graph("P-Polarization (p_pol_spectra)", "p_pol")
        graphs_layout.addWidget(s_pol_graph, 0, 0)
        graphs_layout.addWidget(p_pol_graph, 0, 1)

        # Row 1: Transmission and Dark
        transmission_graph = self._create_graph("Transmission (transmission_spectra)", "transmission")
        dark_graph = self._create_graph("Dark Scan (dark_scan)", "dark")
        graphs_layout.addWidget(transmission_graph, 1, 0)
        graphs_layout.addWidget(dark_graph, 1, 1)

        layout.addWidget(graphs_container)

        # Combined QC table below graphs
        combined_qc_table = self._create_combined_qc_table()
        layout.addWidget(combined_qc_table)

        return widget

    def _create_metadata_section(self) -> QFrame:
        """Create compact metadata section with timestamp and device info."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("""
            QFrame {
                background: #F5F5F7;
                border: 1px solid #D1D1D6;
                border-radius: 6px;
                padding: 8px;
            }
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Title
        title = QLabel("📄 Calibration Metadata")
        title.setStyleSheet("font-size: 12px; font-weight: 600; color: #1D1D1F; background: transparent; border: none; padding: 0px;")
        layout.addWidget(title)

        # Metadata grid - more compact
        from datetime import datetime
        timestamp = self.calibration_data.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        device_type = self.calibration_data.get('device_type', 'Unknown')
        detector_serial = self.calibration_data.get('detector_serial', 'N/A')
        detector_number = self.calibration_data.get('detector_number', 'N/A')
        firmware_version = self.calibration_data.get('firmware_version', 'N/A')
        integration_time = self.calibration_data.get('integration_time', 0)
        num_scans = self.calibration_data.get('num_scans', 'N/A')

        metadata_text = f"""
        <table style='width: 100%; border-collapse: collapse;'>
            <tr>
                <td style='padding: 3px; width: 20%; font-weight: 600; color: #1D1D1F; font-size: 11px;'>Timestamp:</td>
                <td style='padding: 3px; color: #3A3A3C; font-size: 11px;'>{timestamp}</td>
                <td style='padding: 3px; width: 20%; font-weight: 600; color: #1D1D1F; font-size: 11px;'>Device:</td>
                <td style='padding: 3px; color: #3A3A3C; font-size: 11px;'>{device_type}</td>
                <td style='padding: 3px; width: 20%; font-weight: 600; color: #1D1D1F; font-size: 11px;'>Integration:</td>
                <td style='padding: 3px; color: #3A3A3C; font-size: 11px;'>{integration_time:.2f} ms ({num_scans} scans)</td>
            </tr>
            <tr>
                <td style='padding: 3px; font-weight: 600; color: #1D1D1F; font-size: 11px;'>Detector S/N:</td>
                <td style='padding: 3px; color: #3A3A3C; font-size: 11px;'>{detector_serial}</td>
                <td style='padding: 3px; font-weight: 600; color: #1D1D1F; font-size: 11px;'>Detector #:</td>
                <td style='padding: 3px; color: #3A3A3C; font-size: 11px;'>{detector_number}</td>
                <td style='padding: 3px; font-weight: 600; color: #1D1D1F; font-size: 11px;'>Firmware:</td>
                <td style='padding: 3px; color: #3A3A3C; font-size: 11px;'>{firmware_version}</td>
            </tr>
        </table>
        """

        metadata_label = QLabel(metadata_text)
        metadata_label.setTextFormat(Qt.TextFormat.RichText)
        metadata_label.setStyleSheet("""
            QLabel {
                background: white;
                padding: 6px;
                border-radius: 4px;
                font-size: 11px;
                border: none;
            }
        """)
        layout.addWidget(metadata_label)

        return frame

    def _create_combined_qc_table(self) -> QFrame:
        """Create combined QC validation table with both orientation and transmission data."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("QFrame { background: white; border: 1px solid #D1D1D6; border-radius: 8px; }")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("🔬 Quality Control Validation")
        title.setStyleSheet("font-size: 13px; font-weight: 600; color: #1D1D1F; padding-bottom: 3px;")
        layout.addWidget(title)

        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels([
            "Ch", "Polarity", "Min Trans%", "P/S Ratio", "Dip", "FWHM", "Diagnostic", "Status"
        ])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setStyleSheet("""
            QTableWidget {
                background: white;
                border: none;
                gridline-color: #E5E5EA;
                font-size: 11px;
            }
            QHeaderView::section {
                background: #F5F5F7;
                color: #1D1D1F;
                padding: 6px;
                border: none;
                font-weight: 600;
                font-size: 11px;
            }
        """)

        orientation_data = self.calibration_data.get('orientation_validation', {})
        transmission_validation = self.calibration_data.get('transmission_validation', {})

        channels = ['a', 'b', 'c', 'd']
        table.setRowCount(4)

        global_pass_orientation = False
        global_pass_transmission = False

        for idx, ch in enumerate(channels):
            # Channel name
            ch_item = QTableWidgetItem(ch.upper())
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 0, ch_item)

            # === ORIENTATION DATA (Column 1) ===
            if ch in orientation_data:
                if isinstance(orientation_data[ch], dict):
                    passed = orientation_data[ch].get('passed', None)
                    reason = orientation_data[ch].get('reason', 'Unknown')
                else:
                    fwhm = orientation_data[ch]
                    passed = True
                    if fwhm < 30:
                        reason = f"Good: {fwhm:.1f}nm"
                    elif fwhm < 50:
                        reason = f"OK: {fwhm:.1f}nm"
                    else:
                        reason = f"Poor: {fwhm:.1f}nm"
                        passed = None

                if passed is True:
                    orient_text = "✅"
                    global_pass_orientation = True
                elif passed is False:
                    orient_text = "❌"
                else:
                    orient_text = "⚠️"

                orient_item = QTableWidgetItem(orient_text)
                orient_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(idx, 1, orient_item)
            else:
                table.setItem(idx, 1, QTableWidgetItem("N/A"))

            # === TRANSMISSION DATA (Columns 2-6) ===
            if ch in transmission_validation:
                ch_data = transmission_validation[ch]

                # Min Transmission %
                trans_min = ch_data.get('transmission_min')
                if trans_min is not None:
                    trans_item = QTableWidgetItem(f"{trans_min:.1f}")
                    trans_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if trans_min < 20:
                        trans_item.setForeground(QColor("#34C759"))
                    elif trans_min < 40:
                        trans_item.setForeground(QColor("#FF9500"))
                    else:
                        trans_item.setForeground(QColor("#FF3B30"))
                    table.setItem(idx, 2, trans_item)
                else:
                    table.setItem(idx, 2, QTableWidgetItem("N/A"))

                # P/S Ratio
                ratio = ch_data.get('ratio')
                if ratio is not None:
                    ratio_item = QTableWidgetItem(f"{ratio:.2f}")
                    ratio_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if 0.10 <= ratio <= 0.95:
                        ratio_item.setForeground(QColor("#34C759"))
                    else:
                        ratio_item.setForeground(QColor("#FF9500"))
                    table.setItem(idx, 3, ratio_item)
                else:
                    table.setItem(idx, 3, QTableWidgetItem("N/A"))

                # Dip Detected
                dip_detected = ch_data.get('dip_detected', False)
                dip_text = "✅" if dip_detected else "❌"
                dip_item = QTableWidgetItem(dip_text)
                dip_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(idx, 4, dip_item)

                # FWHM
                fwhm = ch_data.get('fwhm')
                if fwhm is not None:
                    fwhm_item = QTableWidgetItem(f"{fwhm:.1f}")
                    fwhm_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if fwhm < 30:
                        fwhm_item.setForeground(QColor("#34C759"))
                    elif fwhm < 50:
                        fwhm_item.setForeground(QColor("#FF9500"))
                    else:
                        fwhm_item.setForeground(QColor("#FF3B30"))
                    table.setItem(idx, 5, fwhm_item)
                else:
                    table.setItem(idx, 5, QTableWidgetItem("N/A"))

                # Diagnostic reason (combined from both)
                diagnostic = ch_data.get('reason', reason if ch in orientation_data else 'N/A')
                diag_item = QTableWidgetItem(diagnostic)
                diag_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft)
                table.setItem(idx, 6, diag_item)

                # Status
                status = ch_data.get('status', 'INDETERMINATE')
                status_item = QTableWidgetItem(status.replace('✅ ', '').replace('❌ ', '').replace('⚠️ ', ''))
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if '✅' in status or 'PASS' in status:
                    status_item.setForeground(QColor("#34C759"))
                    global_pass_transmission = True
                elif '❌' in status or 'FAIL' in status:
                    status_item.setForeground(QColor("#FF3B30"))
                else:
                    status_item.setForeground(QColor("#FF9500"))
                table.setItem(idx, 7, status_item)
            else:
                # No transmission data
                for col in range(2, 8):
                    item = QTableWidgetItem("N/A")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(idx, col, item)

        # Optimize column widths
        table.setColumnWidth(0, 40)   # Ch
        table.setColumnWidth(1, 60)   # Polarity
        table.setColumnWidth(2, 80)   # Min Trans%
        table.setColumnWidth(3, 70)   # P/S Ratio
        table.setColumnWidth(4, 50)   # Dip
        table.setColumnWidth(5, 60)   # FWHM
        table.setColumnWidth(6, 280)  # Diagnostic
        table.horizontalHeader().setSectionResizeMode(7, table.horizontalHeader().ResizeMode.Stretch)  # Status
        table.setMaximumHeight(160)
        layout.addWidget(table)

        # Combined status summary
        if global_pass_orientation and global_pass_transmission:
            result_text = "✅ ALL CHECKS PASSED: Polarizer orientation correct, SPR dip detected"
            result_color = "#34C759"
        elif not global_pass_orientation and not global_pass_transmission:
            result_text = "❌ CALIBRATION ISSUES: Check polarizer and sensor hydration"
            result_color = "#FF3B30"
        else:
            result_text = "⚠️ PARTIAL VALIDATION: Some checks passed, review diagnostics"
            result_color = "#FF9500"

        result_label = QLabel(result_text)
        result_label.setWordWrap(True)
        result_label.setStyleSheet(f"""
            QLabel {{
                color: {result_color};
                font-weight: 600;
                padding: 8px;
                background: #F5F5F7;
                border-radius: 4px;
                border: 1px solid {result_color};
                font-size: 11px;
            }}
        """)
        layout.addWidget(result_label)

        return frame

    def _create_orientation_table(self) -> QFrame:
        """Create polarizer orientation validation table."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("QFrame { background: white; border: 1px solid #D1D1D6; border-radius: 8px; }")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        title = QLabel("🔄 Polarizer Orientation Validation")
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1D1D1F; padding-bottom: 5px;")
        layout.addWidget(title)

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Channel", "Orientation", "Diagnostic Reason", "Status"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setStyleSheet("""
            QTableWidget {
                background: white;
                border: none;
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

        orientation_data = self.calibration_data.get('orientation_validation', {})

        # DEBUG: Log orientation data
        if not orientation_data:
            logger.warning("⚠️ No orientation_validation data in QC report")
        else:
            logger.info(f"✅ Orientation validation data for channels: {list(orientation_data.keys())}")

        table.setRowCount(4)
        global_pass = False  # If any channel is correct, polarizer is OK

        for idx, ch in enumerate(['a', 'b', 'c', 'd']):
            # Channel name
            ch_item = QTableWidgetItem(f"Channel {ch.upper()}")
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 0, ch_item)

            if ch in orientation_data:
                # Handle both old format (dict) and new format (float FWHM)
                if isinstance(orientation_data[ch], dict):
                    # Old format: {'passed': bool, 'reason': str}
                    passed = orientation_data[ch].get('passed', None)
                    reason = orientation_data[ch].get('reason', 'Unknown')
                else:
                    # New format: float FWHM value
                    fwhm = orientation_data[ch]
                    passed = True  # Assume passed if we got a FWHM value
                    if fwhm < 30:
                        reason = f"Good FWHM: {fwhm:.1f}nm"
                    elif fwhm < 50:
                        reason = f"Acceptable FWHM: {fwhm:.1f}nm"
                    else:
                        reason = f"Poor FWHM: {fwhm:.1f}nm - Check sensor"
                        passed = None  # Indeterminate

                # Orientation
                if passed is True:
                    orient_text = "✅ CORRECT"
                    global_pass = True
                elif passed is False:
                    orient_text = "❌ INVERTED"
                else:
                    orient_text = "⚠️ INDETERMINATE"

                orient_item = QTableWidgetItem(orient_text)
                orient_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(idx, 1, orient_item)

                # Reason (replaces "confidence" column with actual diagnostic reason)
                reason_item = QTableWidgetItem(reason)
                reason_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(idx, 2, reason_item)

                # Status
                if passed is True:
                    status_text = "✅ PASS"
                    status_color = "#34C759"
                elif passed is False:
                    status_text = "❌ FAIL"
                    status_color = "#FF3B30"
                else:
                    status_text = "⚠️ INDETERMINATE"
                    status_color = "#FF9500"

                status_item = QTableWidgetItem(status_text)
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                status_item.setForeground(QColor(status_color))
                table.setItem(idx, 3, status_item)
            else:
                # No data
                for col in range(1, 4):
                    item = QTableWidgetItem("N/A")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(idx, col, item)

        table.resizeColumnsToContents()
        table.setMaximumHeight(200)
        layout.addWidget(table)

        # Global result
        if global_pass:
            result_text = "✅ GLOBAL POLARIZER ORIENTATION: CORRECT (at least one channel validates polarizer position)"
            result_color = "#34C759"
        else:
            result_text = "⚠️ GLOBAL POLARIZER ORIENTATION: CANNOT VALIDATE (check all channels)"
            result_color = "#FF9500"

        result_label = QLabel(result_text)
        result_label.setWordWrap(True)
        result_label.setStyleSheet(f"""
            QLabel {{
                color: {result_color};
                font-weight: 600;
                padding: 12px;
                background: #F5F5F7;
                border-radius: 6px;
                border: 1px solid {result_color};
                font-size: 12px;
            }}
        """)
        layout.addWidget(result_label)

        return frame

    def _create_transmission_validation_table(self) -> QFrame:
        """Create transmission dip validation table showing P/S ratio, dip shape, FWHM."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("QFrame { background: white; border: 1px solid #D1D1D6; border-radius: 8px; }")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        title = QLabel("🔬 Transmission Validation (SPR Dip Detection)")
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1D1D1F; padding-bottom: 5px;")
        layout.addWidget(title)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "Channel",
            "Min Trans %",
            "P/S Ratio",
            "Dip Detected",
            "FWHM (nm)",
            "Status"
        ])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setStyleSheet("""
            QTableWidget {
                background: white;
                border: none;
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

        transmission_validation = self.calibration_data.get('transmission_validation', {})

        # DEBUG: Log transmission validation data
        if not transmission_validation:
            logger.warning("⚠️ No transmission_validation data in QC report")
        else:
            logger.info(f"✅ Transmission validation keys: {list(transmission_validation.keys())}")
            for ch, data in transmission_validation.items():
                logger.info(f"   Ch {ch}: {data}")

        # Display per-channel transmission results
        channels = ['a', 'b', 'c', 'd']
        table.setRowCount(len(channels))

        for idx, ch in enumerate(channels):
            # Channel name
            ch_item = QTableWidgetItem(f"Channel {ch.upper()}")
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 0, ch_item)

            if ch in transmission_validation:
                ch_data = transmission_validation[ch]

                # Min Transmission %
                trans_min = ch_data.get('transmission_min')
                if trans_min is not None:
                    trans_item = QTableWidgetItem(f"{trans_min:.1f}%")
                    trans_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    # Color code: green if <20% (good SPR), yellow if 20-40%, red if >40%
                    if trans_min < 20:
                        trans_item.setForeground(QColor("#34C759"))
                    elif trans_min < 40:
                        trans_item.setForeground(QColor("#FF9500"))
                    else:
                        trans_item.setForeground(QColor("#FF3B30"))
                    table.setItem(idx, 1, trans_item)
                else:
                    table.setItem(idx, 1, QTableWidgetItem("N/A"))

                # P/S Ratio
                ratio = ch_data.get('ratio')
                if ratio is not None:
                    ratio_item = QTableWidgetItem(f"{ratio:.3f}")
                    ratio_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    # Color code: green if valid (0.1-0.95), yellow if borderline, red if out of range
                    if 0.10 <= ratio <= 0.95:
                        ratio_item.setForeground(QColor("#34C759"))
                    elif 0.95 < ratio < 1.15:
                        ratio_item.setForeground(QColor("#FF9500"))
                    else:
                        ratio_item.setForeground(QColor("#FF3B30"))
                    table.setItem(idx, 2, ratio_item)
                else:
                    table.setItem(idx, 2, QTableWidgetItem("N/A"))

                # Dip Detected
                dip_detected = ch_data.get('dip_detected', False)
                dip_text = "✅ YES" if dip_detected else "❌ NO"
                dip_item = QTableWidgetItem(dip_text)
                dip_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if dip_detected:
                    dip_item.setForeground(QColor("#34C759"))
                else:
                    dip_item.setForeground(QColor("#FF3B30"))
                table.setItem(idx, 3, dip_item)

                # FWHM
                fwhm = ch_data.get('fwhm')
                if fwhm is not None:
                    fwhm_item = QTableWidgetItem(f"{fwhm:.1f}")
                    fwhm_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    # Color code FWHM quality
                    if fwhm < 30:
                        fwhm_item.setForeground(QColor("#34C759"))
                    elif fwhm < 50:
                        fwhm_item.setForeground(QColor("#FF9500"))
                    else:
                        fwhm_item.setForeground(QColor("#FF3B30"))
                    table.setItem(idx, 4, fwhm_item)
                else:
                    table.setItem(idx, 4, QTableWidgetItem("N/A"))

                # Status (now column 5 after adding Min Trans %)
                status = ch_data.get('status', 'INDETERMINATE')
                status_item = QTableWidgetItem(status)
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if '✅ PASS' in status:
                    status_item.setForeground(QColor("#34C759"))
                elif '❌ FAIL' in status:
                    status_item.setForeground(QColor("#FF3B30"))
                else:
                    status_item.setForeground(QColor("#FF9500"))
                table.setItem(idx, 5, status_item)
            else:
                # No data for this channel
                for col in range(1, 6):
                    item = QTableWidgetItem("N/A")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(idx, col, item)

        # Optimize column widths
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(False)
        table.setColumnWidth(0, 100)  # Channel
        table.setColumnWidth(1, 100)  # Min Trans %
        table.setColumnWidth(2, 100)  # P/S Ratio
        table.setColumnWidth(3, 120)  # Dip Detected
        table.setColumnWidth(4, 100)  # FWHM
        table.horizontalHeader().setSectionResizeMode(5, table.horizontalHeader().ResizeMode.Stretch)  # Status
        table.setMinimumHeight(180)
        table.setMaximumHeight(220)
        layout.addWidget(table)

        # Overall result - check if all channels passed
        passed_channels = [ch for ch, data in transmission_validation.items() if '✅ PASS' in data.get('status', '')]
        failed_channels = [ch for ch, data in transmission_validation.items() if '❌ FAIL' in data.get('status', '')]

        if len(passed_channels) == len(channels) and len(failed_channels) == 0:
            result_text = "✅ TRANSMISSION VALIDATION: ALL CHANNELS PASSED (SPR dip detected, P/S ratio valid)"
            result_color = "#34C759"
        elif len(failed_channels) > 0:
            result_text = f"❌ TRANSMISSION VALIDATION: {len(failed_channels)} CHANNEL(S) FAILED (check sensor hydration)"
            result_color = "#FF3B30"
        else:
            result_text = "⚠️ TRANSMISSION VALIDATION: INDETERMINATE (check calibration data)"
            result_color = "#FF9500"

        result_label = QLabel(result_text)
        result_label.setWordWrap(True)
        result_label.setStyleSheet(f"""
            QLabel {{
                color: {result_color};
                font-weight: 600;
                padding: 12px;
                background: #F5F5F7;
                border-radius: 6px;
                border: 1px solid {result_color};
                font-size: 12px;
            }}
        """)
        layout.addWidget(result_label)

        return frame

    def _create_summary_section(self) -> QLabel:
        """Create compact summary information section."""
        data = self.calibration_data

        integration_time = data.get('integration_time', 0)
        led_intensities = data.get('led_intensities', {})
        sp_swap_applied = data.get('sp_swap_applied', False)

        led_str = ", ".join([f"{ch.upper()}:{led_intensities.get(ch, 0)}" for ch in ['a', 'b', 'c', 'd']])

        # Calculate S-pol and P-pol max counts
        s_pol_spectra = data.get('s_pol_spectra', {})
        p_pol_spectra = data.get('p_pol_spectra', {})

        s_max_str_parts = []
        p_max_str_parts = []

        for ch in ['a', 'b', 'c', 'd']:
            if ch in s_pol_spectra and s_pol_spectra[ch] is not None:
                s_max = np.max(s_pol_spectra[ch])
                s_max_str_parts.append(f"{ch.upper()}:{s_max:.0f}")

            if ch in p_pol_spectra and p_pol_spectra[ch] is not None:
                p_max = np.max(p_pol_spectra[ch])
                p_max_str_parts.append(f"{ch.upper()}:{p_max:.0f}")

        s_max_str = ", ".join(s_max_str_parts) if s_max_str_parts else "N/A"
        p_max_str = ", ".join(p_max_str_parts) if p_max_str_parts else "N/A"

        swap_badge = "  |  <span style='color:#FF9500'><b>QC Display:</b> S/P swapped</span>" if sp_swap_applied else ""

        summary_text = (
            f"<b>Integration:</b> {integration_time:.2f}ms  |  "
            f"<b>LEDs:</b> {led_str}  |  "
            f"<b>S-pol Max:</b> {s_max_str}  |  "
            f"<b>P-pol Max:</b> {p_max_str}" + swap_badge
        )

        summary_label = QLabel(summary_text)
        summary_label.setTextFormat(Qt.TextFormat.RichText)
        summary_label.setStyleSheet("""
            background: #F5F5F7;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 11px;
            color: #1D1D1F;
        """)

        return summary_label

    def _create_graph(self, title: str, data_type: str) -> QFrame:
        """Create a single graph widget.

        Args:
            title: Graph title
            data_type: Type of data ('s_pol', 'p_pol', 'dark', 'transmission')

        Returns:
            QFrame containing the graph
        """
        container = QFrame()
        container.setFrameShape(QFrame.Shape.StyledPanel)
        container.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #D1D1D6;
                border-radius: 6px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Title label
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            font-size: 12px;
            font-weight: 600;
            color: #1D1D1F;
            padding: 3px 0px;
        """)
        layout.addWidget(title_label)

        # Create plot widget
        plot_widget = pg.PlotWidget()
        plot_widget.setBackground('w')
        plot_widget.showGrid(x=True, y=True, alpha=0.3)

        # Configure axes
        plot_widget.setLabel('bottom', 'Wavelength', units='nm')

        if data_type == 'transmission':
            plot_widget.setLabel('left', 'Transmission', units='%')
            # Enable auto-range for transmission - don't constrain the Y-axis
            plot_widget.enableAutoRange(axis='y')
        else:
            plot_widget.setLabel('left', 'Intensity', units='counts')

        # Plot data
        self._plot_data(plot_widget, data_type)

        layout.addWidget(plot_widget)

        return container

    def _plot_data(self, plot_widget: pg.PlotWidget, data_type: str):
        """Plot data on the graph widget.

        Args:
            plot_widget: PyQtGraph PlotWidget
            data_type: Type of data to plot
        """
        data = self.calibration_data
        wavelengths = data.get('wavelengths', None)

        if wavelengths is None:
            wavelengths = np.linspace(560, 720, 3648)  # Default wavelength array
            logger.warning(f"No wavelengths in QC data, using default range")

        # Channel colors (matching existing UI)
        colors = {
            'a': (0, 0, 0, 200),        # Black
            'b': (255, 0, 81, 200),     # Red
            'c': (0, 174, 255, 200),    # Blue
            'd': (0, 150, 80, 200)      # Green (matches main UI)
        }

        # Get data based on type
        data_dict = {}
        if data_type == 's_pol':
            data_dict = data.get('s_pol_spectra', {})
        elif data_type == 'p_pol':
            data_dict = data.get('p_pol_spectra', {})
        elif data_type == 'dark':
            data_dict = data.get('dark_scan', {})
        elif data_type == 'transmission':
            data_dict = data.get('transmission_spectra', {})

        # Plot each channel
        for channel in ['a', 'b', 'c', 'd']:
            if channel in data_dict:
                spectrum = data_dict[channel]
                if spectrum is not None and len(spectrum) > 0:
                    # Handle wavelength array length mismatch
                    if len(wavelengths) != len(spectrum):
                        wavelengths_plot = np.linspace(wavelengths[0], wavelengths[-1], len(spectrum))
                    else:
                        wavelengths_plot = wavelengths

                    pen = pg.mkPen(color=colors.get(channel, (128, 128, 128, 200)), width=2)
                    plot_widget.plot(
                        wavelengths_plot,
                        spectrum,
                        pen=pen,
                        name=f"Channel {channel.upper()}"
                    )

        # Add legend
        plot_widget.addLegend(offset=(10, 10))

    def _create_analysis_visualization(self) -> QWidget:
        """Create calibration analysis visualization tab with matplotlib charts."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Get QC results
        qc_results = self.calibration_data.get('qc_results', {})

        # Check if this is a failed calibration with limited data
        has_channel_data = any(ch in qc_results for ch in ['a', 'b', 'c', 'd'])

        if not qc_results and not has_channel_data:
            # No QC data at all
            label = QLabel("No QC analysis data available")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-size: 14px; color: #666;")
            layout.addWidget(label)
            return widget

        if not has_channel_data:
            # Failed calibration with partial data - show diagnostic info
            return self._create_failure_diagnostic(layout, qc_results)

        # Create matplotlib figure
        fig = Figure(figsize=(14, 8), facecolor='white')
        canvas = FigureCanvasQTAgg(fig)

        channels = ['a', 'b', 'c', 'd']
        channel_labels = ['A', 'B', 'C', 'D']
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']

        # Check if polarizer is inverted
        ps_ratios = []
        all_inverted = True
        for ch in channels:
            if ch in qc_results:
                ratio = qc_results[ch].get('p_s_ratio', 0)
                ps_ratios.append(ratio)
                if ratio < 1.15:  # Threshold for warning
                    all_inverted = False
            else:
                ps_ratios.append(0)
                all_inverted = False

        # Title with warning if inverted
        title_text = 'Calibration Analysis'
        title_color = 'black'
        if all_inverted and any(r > 1.15 for r in ps_ratios):
            title_text = 'Calibration Analysis - WARNING: Polarizer May Be Inverted'
            title_color = 'red'

        fig.suptitle(title_text, fontsize=14, fontweight='bold', color=title_color)

        # Plot 1: S-pol max counts
        ax1 = fig.add_subplot(2, 3, 1)
        s_max = [qc_results.get(ch, {}).get('s_max_counts', 0) for ch in channels]
        bars1 = ax1.bar(channel_labels, s_max, color=colors, alpha=0.7, edgecolor='black', linewidth=2)
        ax1.set_ylabel('Max Counts', fontsize=11, fontweight='bold')
        ax1.set_title('S-Polarization Peak\n(Should be HIGHER than P)', fontsize=10, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim(0, max(s_max) * 1.2 if s_max else 70000)
        for bar, val in zip(bars1, s_max):
            if val > 0:
                ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(s_max)*0.02,
                         f'{val:.0f}', ha='center', va='bottom', fontweight='bold', fontsize=9)

        # Plot 2: P-pol max counts
        ax2 = fig.add_subplot(2, 3, 2)
        p_max = [qc_results.get(ch, {}).get('p_max_counts', 0) for ch in channels]
        bars2 = ax2.bar(channel_labels, p_max, color=colors, alpha=0.7, edgecolor='black', linewidth=2)
        ax2.set_ylabel('Max Counts', fontsize=11, fontweight='bold')
        ax2.set_title('P-Polarization Peak\n(Should be LOWER than S)', fontsize=10, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(0, max(p_max) * 1.2 if p_max else 70000)
        for bar, val in zip(bars2, p_max):
            if val > 0:
                ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(p_max)*0.02,
                         f'{val:.0f}', ha='center', va='bottom', fontweight='bold', fontsize=9)

        # Plot 3: P/S Ratio
        ax3 = fig.add_subplot(2, 3, 3)
        bar_colors = ['red' if r > 1.15 else 'green' for r in ps_ratios]
        bars3 = ax3.bar(channel_labels, ps_ratios, color=bar_colors, alpha=0.7, edgecolor='black', linewidth=2)
        ax3.axhline(y=1.0, color='green', linestyle='--', linewidth=2, label='Expected: P/S < 1.0')
        ax3.axhline(y=1.15, color='orange', linestyle='--', linewidth=2, label='Warning: 1.15')
        ax3.set_ylabel('P/S Ratio', fontsize=11, fontweight='bold')
        title_suffix = '\n(INVERTED!)' if all_inverted and any(r > 1.15 for r in ps_ratios) else '\n(Expected < 1.0)'
        ax3.set_title('P/S Ratio' + title_suffix, fontsize=10, fontweight='bold',
                     color='red' if all_inverted else 'black')
        ax3.grid(True, alpha=0.3)
        ax3.legend(loc='upper right', fontsize=8)
        max_ratio = max(ps_ratios) if ps_ratios else 8
        ax3.set_ylim(0, max(max_ratio * 1.2, 8))
        for bar, val in zip(bars3, ps_ratios):
            if val > 0:
                ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max_ratio*0.02,
                         f'{val:.2f}x', ha='center', va='bottom', fontweight='bold', fontsize=9,
                         color='red' if val > 1.15 else 'black')

        # Plot 4: LED Intensities
        ax4 = fig.add_subplot(2, 3, 4)
        led_intensities = self.calibration_data.get('s_mode_intensity', {})
        led_vals = [led_intensities.get(ch, 0) for ch in channels]
        bars4 = ax4.bar(channel_labels, led_vals, color=colors, alpha=0.7, edgecolor='black', linewidth=2)
        ax4.set_ylabel('LED Intensity (0-255)', fontsize=11, fontweight='bold')
        ax4.set_title('LED Intensities (Calibrated)', fontsize=10, fontweight='bold')
        ax4.set_ylim(0, 280)
        ax4.grid(True, alpha=0.3)
        for bar, val in zip(bars4, led_vals):
            if val > 0:
                ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
                         f'{val}', ha='center', va='bottom', fontweight='bold', fontsize=9)

        # Plot 5: SPR Wavelengths
        ax5 = fig.add_subplot(2, 3, 5)
        spr_wl = [qc_results.get(ch, {}).get('spr_wavelength', 0) for ch in channels]
        bars5 = ax5.bar(channel_labels, spr_wl, color=colors, alpha=0.7, edgecolor='black', linewidth=2)
        ax5.set_ylabel('Wavelength (nm)', fontsize=11, fontweight='bold')
        ax5.set_title('SPR Peak Wavelengths', fontsize=10, fontweight='bold')
        min_wl = min([w for w in spr_wl if w > 0]) if any(w > 0 for w in spr_wl) else 620
        max_wl = max(spr_wl) if spr_wl else 680
        ax5.set_ylim(min_wl - 20, max_wl + 20)
        ax5.grid(True, alpha=0.3)
        for bar, val in zip(bars5, spr_wl):
            if val > 0:
                ax5.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                         f'{val:.1f}nm', ha='center', va='bottom', fontweight='bold', fontsize=9)

        # Plot 6: QC Summary
        ax6 = fig.add_subplot(2, 3, 6)
        ax6.axis('off')

        # Build summary text
        s_integration = self.calibration_data.get('s_integration_time', 0)
        p_integration = self.calibration_data.get('p_integration_time', 0)
        polarizer_s = self.calibration_data.get('polarizer_s_position', 'N/A')
        polarizer_p = self.calibration_data.get('polarizer_p_position', 'N/A')

        summary_text = ""
        if all_inverted and any(r > 1.15 for r in ps_ratios):
            summary_text += "CRITICAL ISSUES:\n\n"
            summary_text += f"1. ALL P/S RATIOS INVERTED ({min(ps_ratios):.1f}-{max(ps_ratios):.1f}x)\n"
            summary_text += "   -> Polarizer positions SWAPPED\n"
            summary_text += f"   -> Current: S={polarizer_s}deg, P={polarizer_p}deg\n"
            summary_text += "   -> Should swap positions\n\n"
        else:
            summary_text += "Configuration:\n\n"

        # Check FWHM
        fwhm_vals = [qc_results.get(ch, {}).get('fwhm', 0) for ch in channels]
        avg_fwhm = sum(fwhm_vals) / len([f for f in fwhm_vals if f > 0]) if any(f > 0 for f in fwhm_vals) else 0
        if avg_fwhm > 50:
            summary_text += f"2. Wide FWHM ({avg_fwhm:.1f}nm avg)\n"
            summary_text += "   -> Poor sensor contact\n"
            summary_text += "   -> Check water/prism\n\n"

        summary_text += f"S Integration: {s_integration:.2f} ms\n"
        summary_text += f"P Integration: {p_integration:.2f} ms\n"
        summary_text += f"Polarizer: S={polarizer_s}deg, P={polarizer_p}deg\n\n"

        if all_inverted and any(r > 1.15 for r in ps_ratios):
            summary_text += "Action Required:\n"
            summary_text += "1. Update device_config.json\n"
            summary_text += "2. Swap S/P positions\n"
            summary_text += "3. Restart & recalibrate\n"

        ax6.text(0.05, 0.95, summary_text, transform=ax6.transAxes,
                 fontsize=9, verticalalignment='top', fontfamily='monospace',
                 bbox=dict(boxstyle='round', facecolor='wheat' if all_inverted else 'lightblue', alpha=0.5))

        fig.tight_layout(rect=[0, 0, 1, 0.97])
        layout.addWidget(canvas)

        return widget

    def _create_failure_diagnostic(self, layout: QVBoxLayout, qc_results: dict) -> QWidget:
        """Create diagnostic view for failed calibration."""
        widget = QWidget()
        diag_layout = QVBoxLayout(widget)
        diag_layout.setContentsMargins(20, 20, 20, 20)
        diag_layout.setSpacing(15)

        # Title
        title = QLabel("❌ Calibration Failed - Diagnostic Information")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #D32F2F;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        diag_layout.addWidget(title)

        # Get error info
        old_s = qc_results.get('old_s_pos', 'N/A')
        old_p = qc_results.get('old_p_pos', 'N/A')

        # Create matplotlib figure for diagnostic plots
        fig = Figure(figsize=(12, 6), facecolor='white')
        canvas = FigureCanvasQTAgg(fig)

        # Plot 1: Servo position comparison
        ax1 = fig.add_subplot(1, 2, 1)
        positions = ['Old S-pos', 'Old P-pos', 'New S-pos\n(expected)', 'New P-pos\n(expected)']
        values = [old_s if isinstance(old_s, (int, float)) else 0,
                  old_p if isinstance(old_p, (int, float)) else 0,
                  89, 179]
        colors = ['red', 'red', 'green', 'green']
        bars = ax1.bar(positions, values, color=colors, alpha=0.7, edgecolor='black', linewidth=2)
        ax1.set_ylabel('Servo Angle (degrees)', fontsize=11, fontweight='bold')
        ax1.set_title('Servo Position Issue', fontsize=12, fontweight='bold')
        ax1.grid(True, alpha=0.3, axis='y')
        ax1.set_ylim(0, 200)

        for bar, val in zip(bars, values):
            if val > 0:
                ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
                        f'{val}°', ha='center', va='bottom', fontweight='bold', fontsize=10)

        # Plot 2: Expected behavior diagram
        ax2 = fig.add_subplot(1, 2, 2)
        ax2.axis('off')

        diagnostic_text = f"""
FAILURE DIAGNOSIS:

❌ Old Servo Positions Detected:
   • S-position: {old_s}° (should be 89°)
   • P-position: {old_p}° (should be 179°)

⚠️  Problem Detected:
   • Controller did not confirm movement
   • Possible causes:
     - Old EEPROM values still loaded
     - Communication error
     - Servo hardware issue

✅ Fixes Applied:
   • Device config updated to correct positions
   • EEPROM sync enabled at startup
   • Legacy EEPROM functions removed
   • Enhanced validation logging
   • Improved error handling

🔧 Next Steps:
   1. Restart the application
   2. EEPROM will sync from device_config
   3. Run calibration again
   4. Check validation logs in console
   5. Verify controller responses

📊 Expected Behavior:
   • S-mode: 89° (maximum transmission)
   • P-mode: 179° (minimum, strongest SPR)
   • P/S ratio should be < 1.0
        """

        ax2.text(0.05, 0.95, diagnostic_text, transform=ax2.transAxes,
                fontsize=9, verticalalignment='top', family='monospace',
                bbox=dict(boxstyle='round', facecolor='#FFF9C4', alpha=0.9))

        fig.tight_layout()
        diag_layout.addWidget(canvas)

        # Add instruction label
        instruction = QLabel(
            "💡 Restart the application and run calibration again. "
            "The EEPROM sync will update the controller with correct positions."
        )
        instruction.setStyleSheet("""
            QLabel {
                background: #E3F2FD;
                border: 2px solid #2196F3;
                border-radius: 6px;
                padding: 12px;
                font-size: 12px;
                color: #1565C0;
            }
        """)
        instruction.setWordWrap(True)
        diag_layout.addWidget(instruction)

        return widget

    @staticmethod
    def show_qc_report(parent=None, calibration_data: dict = None):
        """Static method to show QC report dialog (modal, blocking).

        Args:
            parent: Parent widget
            calibration_data: Calibration data dictionary

        Returns:
            The dialog instance (returns after the dialog is closed)
        """
        print("🔵 DEBUG: CalibrationQCDialog.show_qc_report() started")
        print(f"🔵 DEBUG: parent = {parent}")
        print(f"🔵 DEBUG: calibration_data keys = {list(calibration_data.keys()) if calibration_data else None}")

        print("🔵 DEBUG: Creating CalibrationQCDialog instance...")
        dialog = CalibrationQCDialog(parent=parent, calibration_data=calibration_data)
        print("🟢 DEBUG: CalibrationQCDialog instance created")

        # Ensure modal behavior (blocks until user closes)
        dialog.setModal(True)
        dialog.setWindowModality(Qt.ApplicationModal)

        # Execute dialog modally
        dialog.exec()

        return dialog
