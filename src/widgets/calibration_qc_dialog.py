"""Calibration QC Dialog - Displays 5 comprehensive graphs for quality control.

Shows:
1. S-pol final spectra (all 4 channels)
2. P-pol final spectra (all 4 channels)
3. Final dark scan (all 4 channels)
4. Final afterglow simulation curves (all 4 channels)
5. Transmission spectra (all 4 channels)
"""

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGridLayout, QFrame, QTabWidget,
    QTableWidget, QTableWidgetItem, QWidget, QScrollArea
)
import pyqtgraph as pg
from utils.logger import logger


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
                - afterglow_curves: dict of {channel: afterglow_array}
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

        # DEBUG: Log what data is received
        logger.info("🔍 QC Dialog Received Data:")
        logger.info(f"   orientation_validation: {list(self.calibration_data.get('orientation_validation', {}).keys())}")
        logger.info(f"   spr_fwhm: {self.calibration_data.get('spr_fwhm', {})}")
        logger.info(f"   transmission_validation: {list(self.calibration_data.get('transmission_validation', {}).keys())}")

        self.setWindowTitle("Calibration QC Report")
        self.setMinimumSize(1400, 900)
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
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel("📊 Calibration Quality Control Report")
        title.setStyleSheet("""
            font-size: 20px;
            font-weight: 600;
            color: #1D1D1F;
            padding: 10px 0px;
        """)
        layout.addWidget(title)

        # Summary info
        summary = self._create_summary_section()
        layout.addWidget(summary)

        # Create tab widget
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #D1D1D6;
                border-radius: 8px;
                background: white;
            }
            QTabBar::tab {
                background: #F5F5F7;
                color: #1D1D1F;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: #007AFF;
                color: white;
            }
            QTabBar::tab:hover {
                background: #0051D5;
                color: white;
            }
        """)

        # Tab 1: Graphs
        graphs_tab = self._create_graphs_tab()
        tab_widget.addTab(graphs_tab, "📈 Spectra Graphs")

        # Tab 2: QC Parameters
        qc_params_tab = self._create_qc_params_tab()
        tab_widget.addTab(qc_params_tab, "✅ QC Parameters")

        layout.addWidget(tab_widget)

        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _create_graphs_tab(self) -> QWidget:
        """Create the graphs tab with 5 spectral graphs."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Grid of graphs (3x2 layout)
        graphs_container = QFrame()
        graphs_layout = QGridLayout(graphs_container)
        graphs_layout.setSpacing(15)

        # Row 1: S-pol and P-pol
        s_pol_graph = self._create_graph("1. S-Polarization Final Spectra", "s_pol")
        p_pol_graph = self._create_graph("2. P-Polarization Final Spectra", "p_pol")
        graphs_layout.addWidget(s_pol_graph, 0, 0)
        graphs_layout.addWidget(p_pol_graph, 0, 1)

        # Row 2: Dark and Afterglow
        dark_graph = self._create_graph("3. Final Dark Scan", "dark")
        afterglow_graph = self._create_graph("4. Afterglow Simulation Curves", "afterglow")
        graphs_layout.addWidget(dark_graph, 1, 0)
        graphs_layout.addWidget(afterglow_graph, 1, 1)

        # Row 3: Transmission and Metadata (same width as other graphs)
        transmission_graph = self._create_graph("5. Transmission Spectra", "transmission")
        metadata_section = self._create_metadata_section()
        graphs_layout.addWidget(transmission_graph, 2, 0)
        graphs_layout.addWidget(metadata_section, 2, 1)

        layout.addWidget(graphs_container)
        return widget

    def _create_qc_params_tab(self) -> QWidget:
        """Create the QC parameters tab showing pass/fail status."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Info label
        info_label = QLabel("📋 Quality Control Parameters and Results")
        info_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #1D1D1F; padding-bottom: 10px;")
        layout.addWidget(info_label)

        # Create scroll area for the tables
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(20)

        # 1. Polarizer Orientation Table
        orientation_table = self._create_orientation_table()
        scroll_layout.addWidget(orientation_table)

        # 2. Transmission Validation Table (includes FWHM)
        transmission_table = self._create_transmission_validation_table()
        scroll_layout.addWidget(transmission_table)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        return widget

    def _create_metadata_section(self) -> QFrame:
        """Create metadata section with timestamp and device info."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("""
            QFrame {
                background: #F5F5F7;
                border: 1px solid #D1D1D6;
                border-radius: 8px;
                padding: 15px;
            }
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Title
        title = QLabel("📄 Calibration Report Metadata")
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1D1D1F; background: transparent; border: none; padding: 0px;")
        layout.addWidget(title)

        # Metadata grid
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
                <td style='padding: 5px; width: 30%; font-weight: 600; color: #1D1D1F;'>Timestamp:</td>
                <td style='padding: 5px; color: #3A3A3C;'>{timestamp}</td>
                <td style='padding: 5px; width: 30%; font-weight: 600; color: #1D1D1F;'>Device Type:</td>
                <td style='padding: 5px; color: #3A3A3C;'>{device_type}</td>
            </tr>
            <tr>
                <td style='padding: 5px; font-weight: 600; color: #1D1D1F;'>Detector S/N:</td>
                <td style='padding: 5px; color: #3A3A3C;'>{detector_serial}</td>
                <td style='padding: 5px; font-weight: 600; color: #1D1D1F;'>Detector #:</td>
                <td style='padding: 5px; color: #3A3A3C;'>{detector_number}</td>
            </tr>
            <tr>
                <td style='padding: 5px; font-weight: 600; color: #1D1D1F;'>Firmware:</td>
                <td style='padding: 5px; color: #3A3A3C;'>{firmware_version}</td>
                <td style='padding: 5px; font-weight: 600; color: #1D1D1F;'>Integration:</td>
                <td style='padding: 5px; color: #3A3A3C;'>{integration_time:.2f} ms</td>
            </tr>
            <tr>
                <td style='padding: 5px; font-weight: 600; color: #1D1D1F;'>Scan Averaging:</td>
                <td style='padding: 5px; color: #3A3A3C;'>{num_scans} scans</td>
                <td style='padding: 5px; font-weight: 600; color: #1D1D1F;'></td>
                <td style='padding: 5px; color: #3A3A3C;'></td>
            </tr>
        </table>
        """

        metadata_label = QLabel(metadata_text)
        metadata_label.setTextFormat(Qt.TextFormat.RichText)
        metadata_label.setStyleSheet("""
            QLabel {
                background: white;
                padding: 10px;
                border-radius: 6px;
                font-size: 12px;
                border: none;
            }
        """)
        layout.addWidget(metadata_label)

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
        """Create summary information section."""
        data = self.calibration_data

        integration_time = data.get('integration_time', 0)
        led_intensities = data.get('led_intensities', {})

        led_str = ", ".join([f"Ch {ch.upper()}: {led_intensities.get(ch, 0)}" for ch in ['a', 'b', 'c', 'd']])

        # Calculate S-pol and P-pol max counts
        s_pol_spectra = data.get('s_pol_spectra', {})
        p_pol_spectra = data.get('p_pol_spectra', {})
        
        s_max_str_parts = []
        p_max_str_parts = []
        
        for ch in ['a', 'b', 'c', 'd']:
            if ch in s_pol_spectra and s_pol_spectra[ch] is not None:
                s_max = np.max(s_pol_spectra[ch])
                s_max_str_parts.append(f"Ch {ch.upper()}: {s_max:.0f}")
            
            if ch in p_pol_spectra and p_pol_spectra[ch] is not None:
                p_max = np.max(p_pol_spectra[ch])
                p_max_str_parts.append(f"Ch {ch.upper()}: {p_max:.0f}")
        
        s_max_str = ", ".join(s_max_str_parts) if s_max_str_parts else "N/A"
        p_max_str = ", ".join(p_max_str_parts) if p_max_str_parts else "N/A"

        summary_text = (
            f"<b>Integration Time:</b> {integration_time:.2f} ms  |  "
            f"<b>LED Intensities:</b> {led_str}<br>"
            f"<b>S-pol Max (75% target):</b> {s_max_str}<br>"
            f"<b>P-pol Max (81% target):</b> {p_max_str}"
        )

        summary_label = QLabel(summary_text)
        summary_label.setTextFormat(Qt.TextFormat.RichText)
        summary_label.setStyleSheet("""
            background: #F5F5F7;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 12px;
            color: #1D1D1F;
        """)

        return summary_label

    def _create_graph(self, title: str, data_type: str) -> QFrame:
        """Create a single graph widget.

        Args:
            title: Graph title
            data_type: Type of data ('s_pol', 'p_pol', 'dark', 'afterglow', 'transmission')

        Returns:
            QFrame containing the graph
        """
        container = QFrame()
        container.setFrameShape(QFrame.Shape.StyledPanel)
        container.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #D1D1D6;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Title label
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            font-size: 14px;
            font-weight: 600;
            color: #1D1D1F;
            padding: 5px 0px;
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
        elif data_type == 'afterglow':
            plot_widget.setLabel('left', 'Afterglow Correction', units='counts')
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
            'd': (0, 230, 65, 200)      # Green
        }

        # Get data based on type
        data_dict = {}
        if data_type == 's_pol':
            data_dict = data.get('s_pol_spectra', {})
        elif data_type == 'p_pol':
            data_dict = data.get('p_pol_spectra', {})
        elif data_type == 'dark':
            data_dict = data.get('dark_scan', {})
        elif data_type == 'afterglow':
            data_dict = data.get('afterglow_curves', {})
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

    @staticmethod
    def show_qc_report(parent=None, calibration_data: dict = None):
        """Static method to show QC report dialog.

        Args:
            parent: Parent widget
            calibration_data: Calibration data dictionary

        Returns:
            Dialog result (QDialog.Accepted or QDialog.Rejected)
        """
        dialog = CalibrationQCDialog(parent=parent, calibration_data=calibration_data)

        # Ensure dialog is visible and comes to front
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

        return dialog.exec()
