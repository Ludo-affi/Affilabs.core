"""Calibration QC Dialog - Displays 5 comprehensive graphs for quality control.

Shows:
1. S-pol final spectra (all 4 channels)
2. P-pol final spectra (all 4 channels)
3. Final dark scan (all 4 channels)
4. Final afterglow simulation curves (all 4 channels)
5. Transmission spectra (all 4 channels)
"""

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

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

        """
        super().__init__(parent)
        self.calibration_data = calibration_data or {}

        # DEBUG: Log what data is received
        logger.info("🔍 QC Dialog Received Data:")
        logger.info(
            f"   orientation_validation: {list(self.calibration_data.get('orientation_validation', {}).keys())}",
        )
        logger.info(f"   spr_fwhm: {self.calibration_data.get('spr_fwhm', {})}")
        logger.info(
            f"   transmission_validation: {list(self.calibration_data.get('transmission_validation', {}).keys())}",
        )

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

        # Grid of graphs (2x3 layout - 5 graphs + 1 empty)
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
        afterglow_graph = self._create_graph(
            "4. Afterglow Simulation Curves",
            "afterglow",
        )
        graphs_layout.addWidget(dark_graph, 1, 0)
        graphs_layout.addWidget(afterglow_graph, 1, 1)

        # Row 3: Transmission (spans both columns)
        transmission_graph = self._create_graph(
            "5. Transmission Spectra",
            "transmission",
        )
        graphs_layout.addWidget(transmission_graph, 2, 0, 1, 2)  # Span 2 columns

        layout.addWidget(graphs_container)
        return widget

    def _create_qc_params_tab(self) -> QWidget:
        """Create the QC parameters tab showing pass/fail status."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Info label
        info_label = QLabel("📋 Quality Control Parameters and Results")
        info_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #1D1D1F;")
        layout.addWidget(info_label)

        # Create scroll area for the tables
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(20)

        # 1. Polarizer Orientation Table
        orientation_table = self._create_orientation_table()
        scroll_layout.addWidget(orientation_table)

        # 2. Transmission Validation Table (NEW)
        transmission_table = self._create_transmission_validation_table()
        scroll_layout.addWidget(transmission_table)

        # 3. SPR Quality Table
        spr_table = self._create_spr_quality_table()
        scroll_layout.addWidget(spr_table)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        return widget

    def _create_orientation_table(self) -> QFrame:
        """Create polarizer orientation validation table."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            "QFrame { background: white; border: 1px solid #D1D1D6; border-radius: 8px; padding: 10px; }",
        )

        layout = QVBoxLayout(frame)

        title = QLabel("🔄 Polarizer Orientation Validation")
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1D1D1F;")
        layout.addWidget(title)

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(
            ["Channel", "Orientation", "Confidence", "Status"],
        )
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

        orientation_data = self.calibration_data.get("orientation_validation", {})

        # DEBUG: Log orientation data
        if not orientation_data:
            logger.warning("⚠️ No orientation_validation data in QC report")
        else:
            logger.info(
                f"✅ Orientation validation data for channels: {list(orientation_data.keys())}",
            )

        table.setRowCount(4)
        global_pass = False  # If any channel is correct, polarizer is OK

        for idx, ch in enumerate(["a", "b", "c", "d"]):
            # Channel name
            ch_item = QTableWidgetItem(f"Channel {ch.upper()}")
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 0, ch_item)

            if ch in orientation_data:
                orientation_correct, confidence = orientation_data[ch]

                # Orientation
                if orientation_correct is True:
                    orient_text = "✅ CORRECT"
                    global_pass = True
                elif orientation_correct is False:
                    orient_text = "❌ INVERTED"
                else:
                    orient_text = "⚠️ INDETERMINATE"

                orient_item = QTableWidgetItem(orient_text)
                orient_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(idx, 1, orient_item)

                # Confidence
                conf_item = QTableWidgetItem(f"{confidence:.2f}")
                conf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(idx, 2, conf_item)

                # Status
                if orientation_correct is True and confidence >= 0.4:
                    status_text = "✅ PASS"
                    status_color = "#34C759"
                elif orientation_correct is False:
                    status_text = "❌ FAIL"
                    status_color = "#FF3B30"
                else:
                    status_text = "⚠️ WARN"
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
            result_text = (
                "⚠️ GLOBAL POLARIZER ORIENTATION: CANNOT VALIDATE (check all channels)"
            )
            result_color = "#FF9500"

        result_label = QLabel(result_text)
        result_label.setStyleSheet(
            f"color: {result_color}; font-weight: 600; padding: 10px; background: #F5F5F7; border-radius: 6px;",
        )
        layout.addWidget(result_label)

        return frame

    def _create_transmission_validation_table(self) -> QFrame:
        """Create transmission dip validation table showing P/S ratio, dip shape, FWHM."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            "QFrame { background: white; border: 1px solid #D1D1D6; border-radius: 8px; padding: 10px; }",
        )

        layout = QVBoxLayout(frame)

        title = QLabel("🔬 Transmission Dip Validation (SPR Range: 580-720nm)")
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1D1D1F;")
        layout.addWidget(title)

        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels(
            [
                "Channel",
                "P/S Ratio",
                "Dip Min (nm)",
                "FWHM (nm)",
                "Left Slope",
                "Right Slope",
                "Status",
            ],
        )
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

        transmission_validation = self.calibration_data.get(
            "transmission_validation",
            {},
        )

        # DEBUG: Log transmission validation data
        if not transmission_validation:
            logger.warning("⚠️ No transmission_validation data in QC report")
        else:
            logger.info(
                f"✅ Transmission validation keys: {list(transmission_validation.keys())}",
            )
            if "global" in transmission_validation:
                logger.info(
                    f"   Global validation data: {transmission_validation['global']}",
                )

        # For now, we show global validation (applies to all channels)
        # In future, this could be per-channel if validation is run per channel
        channels = ["A", "B", "C", "D"]
        table.setRowCount(len(channels))

        global_data = transmission_validation.get("global", {})
        overall_pass = global_data.get("passed", None)

        for idx, ch in enumerate(channels):
            # Channel name
            ch_item = QTableWidgetItem(f"Channel {ch}")
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 0, ch_item)

            if global_data:
                # P/S Ratio
                ratio = global_data.get("ratio")
                if ratio is not None:
                    ratio_item = QTableWidgetItem(f"{ratio:.3f}")
                    ratio_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    # Color code: green if valid (0.1-0.75), yellow if borderline, red if out of range
                    if 0.10 <= ratio <= 0.75:
                        ratio_item.setForeground(QColor("#34C759"))
                    elif 0.01 <= ratio < 0.10 or 0.75 < ratio <= 0.95:
                        ratio_item.setForeground(QColor("#FF9500"))
                    else:
                        ratio_item.setForeground(QColor("#FF3B30"))
                    table.setItem(idx, 1, ratio_item)
                else:
                    table.setItem(idx, 1, QTableWidgetItem("N/A"))

                # Dip minimum wavelength
                min_wl = global_data.get("min_wavelength")
                if min_wl is not None:
                    min_wl_item = QTableWidgetItem(f"{min_wl:.1f}")
                    min_wl_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(idx, 2, min_wl_item)
                else:
                    table.setItem(idx, 2, QTableWidgetItem("N/A"))

                # FWHM
                fwhm = global_data.get("fwhm_nm")
                if fwhm is not None:
                    fwhm_item = QTableWidgetItem(f"{fwhm:.2f}")
                    fwhm_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(idx, 3, fwhm_item)
                else:
                    table.setItem(idx, 3, QTableWidgetItem("N/A"))

                # Left slope
                left_slope = global_data.get("left_slope")
                if left_slope is not None:
                    slope_item = QTableWidgetItem(f"{left_slope:.4f}")
                    slope_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    # Should be negative at minimum
                    if left_slope < 0:
                        slope_item.setForeground(QColor("#34C759"))
                    else:
                        slope_item.setForeground(QColor("#FF3B30"))
                    table.setItem(idx, 4, slope_item)
                else:
                    table.setItem(idx, 4, QTableWidgetItem("N/A"))

                # Right slope
                right_slope = global_data.get("right_slope")
                if right_slope is not None:
                    slope_item = QTableWidgetItem(f"{right_slope:.4f}")
                    slope_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    # Should be positive at minimum
                    if right_slope > 0:
                        slope_item.setForeground(QColor("#34C759"))
                    else:
                        slope_item.setForeground(QColor("#FF3B30"))
                    table.setItem(idx, 5, slope_item)
                else:
                    table.setItem(idx, 5, QTableWidgetItem("N/A"))

                # Status
                if overall_pass is True:
                    status_text = "✅ PASS"
                    status_color = "#34C759"
                elif overall_pass is False:
                    status_text = "❌ FAIL"
                    status_color = "#FF3B30"
                else:
                    status_text = "⚠️ N/A"
                    status_color = "#FF9500"

                status_item = QTableWidgetItem(status_text)
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                status_item.setForeground(QColor(status_color))
                table.setItem(idx, 6, status_item)
            else:
                # No validation data
                for col in range(1, 7):
                    item = QTableWidgetItem("N/A")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(idx, col, item)

        table.resizeColumnsToContents()
        table.setMaximumHeight(220)
        layout.addWidget(table)

        # Global result with explanation
        if overall_pass is True:
            result_text = "✅ TRANSMISSION VALIDATION: PASSED (P/S ratio valid, dip shape correct)"
            result_color = "#34C759"
        elif overall_pass is False:
            failure_reason = global_data.get("failure_reason", "Unknown")
            result_text = f"❌ TRANSMISSION VALIDATION: FAILED ({failure_reason})"
            result_color = "#FF3B30"
        else:
            result_text = "⚠️ TRANSMISSION VALIDATION: NOT PERFORMED"
            result_color = "#FF9500"

        result_label = QLabel(result_text)
        result_label.setStyleSheet(
            f"color: {result_color}; font-weight: 600; padding: 10px; background: #F5F5F7; border-radius: 6px;",
        )
        layout.addWidget(result_label)

        return frame

    def _create_spr_quality_table(self) -> QFrame:
        """Create SPR quality (FWHM) table."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            "QFrame { background: white; border: 1px solid #D1D1D6; border-radius: 8px; padding: 10px; }",
        )

        layout = QVBoxLayout(frame)

        title = QLabel("📊 SPR Sensor Quality (FWHM)")
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1D1D1F;")
        layout.addWidget(title)

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Channel", "FWHM (nm)", "Quality Rating"])
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

        spr_fwhm = self.calibration_data.get("spr_fwhm", {})

        # DEBUG: Log SPR FWHM data
        if not spr_fwhm:
            logger.warning("⚠️ No spr_fwhm data in QC report")
        else:
            logger.info(
                f"✅ SPR FWHM data for channels: {list(spr_fwhm.keys())} - Values: {spr_fwhm}",
            )

        table.setRowCount(4)
        fwhm_values = []

        for idx, ch in enumerate(["a", "b", "c", "d"]):
            # Channel name
            ch_item = QTableWidgetItem(f"Channel {ch.upper()}")
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 0, ch_item)

            if ch in spr_fwhm:
                fwhm = spr_fwhm[ch]
                fwhm_values.append(fwhm)

                # FWHM value
                fwhm_item = QTableWidgetItem(f"{fwhm:.1f}")
                fwhm_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(idx, 1, fwhm_item)

                # Quality rating
                if fwhm < 15:
                    quality_text = "✅ Excellent"
                    quality_color = "#34C759"
                elif fwhm < 30:
                    quality_text = "✅ Good"
                    quality_color = "#34C759"
                elif fwhm < 50:
                    quality_text = "⚠️ Okay"
                    quality_color = "#FF9500"
                else:
                    quality_text = "❌ Poor"
                    quality_color = "#FF3B30"

                quality_item = QTableWidgetItem(quality_text)
                quality_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                quality_item.setForeground(QColor(quality_color))
                table.setItem(idx, 2, quality_item)
            else:
                # No data
                for col in range(1, 3):
                    item = QTableWidgetItem("N/A")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(idx, col, item)

        table.resizeColumnsToContents()
        table.setMaximumHeight(200)
        layout.addWidget(table)

        # Average result
        if fwhm_values:
            avg_fwhm = sum(fwhm_values) / len(fwhm_values)
            if avg_fwhm < 30:
                result_text = (
                    f"✅ Average FWHM: {avg_fwhm:.1f}nm - Sensor ready for measurements"
                )
                result_color = "#34C759"
            elif avg_fwhm < 50:
                result_text = (
                    f"⚠️ Average FWHM: {avg_fwhm:.1f}nm - Acceptable but monitor quality"
                )
                result_color = "#FF9500"
            else:
                result_text = (
                    f"❌ Average FWHM: {avg_fwhm:.1f}nm - Check water/prism contact"
                )
                result_color = "#FF3B30"
        else:
            result_text = "⚠️ No SPR FWHM data available"
            result_color = "#FF9500"

        result_label = QLabel(result_text)
        result_label.setStyleSheet(
            f"color: {result_color}; font-weight: 600; padding: 10px; background: #F5F5F7; border-radius: 6px;",
        )
        layout.addWidget(result_label)

        return frame

    def _create_summary_section(self) -> QLabel:
        """Create summary information section."""
        data = self.calibration_data

        integration_time = data.get("integration_time", 0)
        led_intensities = data.get("led_intensities", {})

        led_str = ", ".join(
            [
                f"Ch {ch.upper()}: {led_intensities.get(ch, 0)}"
                for ch in ["a", "b", "c", "d"]
            ],
        )

        summary_text = (
            f"<b>Integration Time:</b> {integration_time:.2f} ms  |  "
            f"<b>LED Intensities:</b> {led_str}"
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
        plot_widget.setBackground("w")
        plot_widget.showGrid(x=True, y=True, alpha=0.3)

        # Configure axes
        plot_widget.setLabel("bottom", "Wavelength", units="nm")

        if data_type == "transmission":
            plot_widget.setLabel("left", "Transmission", units="%")
        elif data_type == "afterglow":
            plot_widget.setLabel("left", "Afterglow Correction", units="counts")
        else:
            plot_widget.setLabel("left", "Intensity", units="counts")

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
        wavelengths = data.get("wavelengths", None)

        if wavelengths is None:
            wavelengths = np.linspace(560, 720, 3648)  # Default wavelength array
            logger.warning("No wavelengths in QC data, using default range")

        # Channel colors (matching existing UI)
        colors = {
            "a": (0, 0, 0, 200),  # Black
            "b": (255, 0, 81, 200),  # Red
            "c": (0, 174, 255, 200),  # Blue
            "d": (0, 230, 65, 200),  # Green
        }

        # Get data based on type
        data_dict = {}
        if data_type == "s_pol":
            data_dict = data.get("s_pol_spectra", {})
        elif data_type == "p_pol":
            data_dict = data.get("p_pol_spectra", {})
        elif data_type == "dark":
            data_dict = data.get("dark_scan", {})
        elif data_type == "afterglow":
            data_dict = data.get("afterglow_curves", {})
        elif data_type == "transmission":
            data_dict = data.get("transmission_spectra", {})

        # Plot each channel
        for channel in ["a", "b", "c", "d"]:
            if channel in data_dict:
                spectrum = data_dict[channel]
                if spectrum is not None and len(spectrum) > 0:
                    # Handle wavelength array length mismatch
                    if len(wavelengths) != len(spectrum):
                        wavelengths_plot = np.linspace(
                            wavelengths[0],
                            wavelengths[-1],
                            len(spectrum),
                        )
                    else:
                        wavelengths_plot = wavelengths

                    pen = pg.mkPen(
                        color=colors.get(channel, (128, 128, 128, 200)),
                        width=2,
                    )
                    plot_widget.plot(
                        wavelengths_plot,
                        spectrum,
                        pen=pen,
                        name=f"Channel {channel.upper()}",
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
