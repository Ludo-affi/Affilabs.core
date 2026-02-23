"""Calibration QC Dialog - Displays 4 comprehensive graphs for quality control.

Shows:
1. S-pol final spectra (all 4 channels)
2. P-pol final spectra (all 4 channels)
3. Final dark scan (all 4 channels)
4. Transmission spectra (all 4 channels)
"""

from __future__ import annotations

import matplotlib
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from affilabs.utils.logger import logger

matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


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
        self.setModal(False)  # Non-modal so it doesn't block and can be moved easily

        # Ensure dialog stays within screen bounds with better constraints
        from PySide6.QtGui import QGuiApplication

        screen = QGuiApplication.primaryScreen().availableGeometry()
        # Use 80% of screen size with narrower width for 2x2 layout
        dialog_width = min(int(screen.width() * 0.8), 1300)
        dialog_height = min(int(screen.height() * 0.85), 850)

        # Set size constraints to prevent dialog from becoming unusable
        self.setMinimumSize(1000, 650)
        self.setMaximumSize(screen.width(), screen.height() - 50)  # Leave room for taskbar
        self.resize(dialog_width, dialog_height)

        # Center dialog on screen initially
        self.move(
            (screen.width() - dialog_width) // 2,
            (screen.height() - dialog_height) // 2,
        )
        # Apply modern styling matching the software design system
        self.setStyleSheet("""
            QDialog {
                background: #FFFFFF;
            }
            QLabel {
                color: #1D1D1F;
                font-size: 13px;
                font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton {
                background: #007AFF;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
                min-width: 110px;
                min-height: 36px;
                font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton:hover {
                background: #0051D5;
            }
            QPushButton:pressed {
                background: #004FC4;
            }
            QPushButton:disabled {
                background: #E5E5EA;
                color: #86868B;
            }
        """)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI layout with tabs for graphs and QC parameters."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(8)

        # ── Compact single-row header ─────────────────────────────────────
        from datetime import datetime
        from version import __version__

        timestamp = self.calibration_data.get(
            "timestamp",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        # Build inline stats string (S-POL / P-POL / DARK)
        _stats_html = self._build_header_stats_html()

        # Username
        try:
            from affilabs.services.user_profile_manager import UserProfileManager
            _upm = UserProfileManager()
            _username = _upm.current_user or ""
        except Exception:
            _username = ""
        _user_html = (
            f"&nbsp;&nbsp;•&nbsp;&nbsp;<span style='color:#1D1D1F; font-weight:600;'>{_username}</span>"
            if _username else ""
        )

        header_label = QLabel(
            f"<span style='font-size:14px; font-weight:700; color:#1D1D1F;'>Calibration QC Report</span>"
            f"&nbsp;&nbsp;&nbsp;"
            f"<span style='font-size:11px; color:#86868B;'>📅 {timestamp}&nbsp;&nbsp;{__version__}</span>"
            f"{_user_html}"
            f"&nbsp;&nbsp;&nbsp;&nbsp;"
            f"{_stats_html}"
        )
        header_label.setTextFormat(Qt.TextFormat.RichText)
        header_label.setStyleSheet("padding: 4px 0px;")
        layout.addWidget(header_label)

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

        # Tab 1: QC graphs and table (single tab - second tab removed as it was empty)
        tab1 = self._create_graphs_content()
        tabs.addTab(tab1, "QC Spectra & Validation")

        layout.addWidget(tabs)

        # Button layout with export options
        button_layout = QHBoxLayout()

        # Export PDF button
        export_pdf_btn = QPushButton(" Export PDF")
        try:
            from affilabs.utils.resource_path import get_affilabs_resource
            _pdf_icon_path = get_affilabs_resource("ui/img/export_pdf.svg")
            if _pdf_icon_path.exists():
                export_pdf_btn.setIcon(QIcon(str(_pdf_icon_path)))
                export_pdf_btn.setIconSize(QSize(16, 16))
        except Exception:
            pass
        export_pdf_btn.setFixedSize(148, 36)
        export_pdf_btn.setStyleSheet("""
            QPushButton {
                background: #34C759;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #2DA84C;
            }
            QPushButton:pressed {
                background: #248A3D;
            }
        """)
        export_pdf_btn.clicked.connect(self._export_to_pdf)
        button_layout.addWidget(export_pdf_btn)

        button_layout.addStretch()

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setFixedSize(100, 36)
        close_btn.setStyleSheet("""
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
            QPushButton:pressed {
                background: #004FC4;
            }
        """)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _create_graphs_content(self) -> QWidget:
        """Create the graphs section with 2x2 quadrant layout and table."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 2x2 Grid layout for quadrant display
        from PySide6.QtWidgets import QGridLayout
        
        grid_container = QWidget()
        grid_layout = QGridLayout(grid_container)
        grid_layout.setSpacing(8)
        grid_layout.setContentsMargins(0, 0, 0, 0)

        # Create graphs and table
        s_pol_graph = self._create_graph("S-Pol", "s_pol")
        p_pol_graph = self._create_graph("P-Pol", "p_pol")
        transmission_graph = self._create_graph("Transmission", "transmission")
        combined_qc_table = self._create_combined_qc_table()

        # Quadrant layout:
        # Top left: S-Pol
        # Top right: P-Pol
        # Bottom left: Transmission
        # Bottom right: Table
        grid_layout.addWidget(s_pol_graph, 0, 0)
        grid_layout.addWidget(p_pol_graph, 0, 1)
        grid_layout.addWidget(transmission_graph, 1, 0)
        grid_layout.addWidget(combined_qc_table, 1, 1)

        layout.addWidget(grid_container)

        return widget

    def _create_metadata_section(self) -> QFrame:
        """Create compact metadata section with timestamp only."""
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
        layout.setSpacing(4)

        # Timestamp row only
        from datetime import datetime

        timestamp = self.calibration_data.get(
            "timestamp",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        device_type = self.calibration_data.get("device_type", "USB4000")

        metadata_text = f"""
        <table style='width: 100%; border-collapse: collapse;'>
            <tr>
                <td style='padding: 3px; width: 15%; font-weight: 600; color: #1D1D1F; font-size: 11px;'>Timestamp:</td>
                <td style='padding: 3px; color: #3A3A3C; font-size: 11px;'>{timestamp}</td>
                <td style='padding: 3px; width: 15%; font-weight: 600; color: #1D1D1F; font-size: 11px;'>Device:</td>
                <td style='padding: 3px; color: #3A3A3C; font-size: 11px;'>{device_type}</td>
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

    def _create_convergence_summary(self) -> QWidget | None:
        """Create convergence summary section showing LED calibration results.

        Returns:
            QWidget with title and convergence data, or None if no convergence data available

        """
        convergence_summary = self.calibration_data.get("convergence_summary")
        if not convergence_summary or not isinstance(convergence_summary, dict):
            return None

        # Container for frame + title at bottom
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)

        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            "QFrame { background: white; border: 1px solid #D1D1D6; border-radius: 8px; }",
        )

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Extract convergence data
        strategy = convergence_summary.get("strategy", "intensity")
        shared_integration = convergence_summary.get("shared_integration_ms", 0)
        ok = convergence_summary.get("ok", False)
        channels = convergence_summary.get("channels", {})

        # Summary line
        status_color = "#34C759" if ok else "#FF3B30"
        status_text = "PASS" if ok else "FAIL"
        summary_html = f"""
        <span style='color:#86868B; font-size:10px; font-weight:600;'>STRATEGY</span>
        <span style='color:#1D1D1F; font-weight:500;'>{strategy.title()}</span>
        &nbsp;&nbsp;•&nbsp;&nbsp;
        <span style='color:#86868B; font-size:10px; font-weight:600;'>INTEGRATION TIME</span>
        <span style='color:#1D1D1F; font-weight:600;'>{shared_integration:.1f}ms</span>
        &nbsp;&nbsp;•&nbsp;&nbsp;
        <span style='color:#86868B; font-size:10px; font-weight:600;'>STATUS</span>
        <span style='color:{status_color}; font-weight:700;'>{status_text}</span>
        """

        summary_label = QLabel(summary_html)
        summary_label.setTextFormat(Qt.TextFormat.RichText)
        summary_label.setStyleSheet("""
            background: transparent;
            padding: 4px 0px;
            font-size: 11px;
            color: #1D1D1F;
            border: none;
        """)
        summary_label.setWordWrap(False)
        layout.addWidget(summary_label)

        # Per-channel table
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            ["Channel", "LED Intensity", "Integration (ms)", "Signal (counts)", "Saturation %", "Iterations"],
        )
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

        channels_list = ["a", "b", "c", "d"]
        table.setRowCount(len(channels_list))

        for idx, ch in enumerate(channels_list):
            if ch not in channels:
                continue

            ch_data = channels[ch]

            # Channel name
            ch_item = QTableWidgetItem(ch.upper())
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 0, ch_item)

            # LED intensity
            led = int(ch_data.get("final_led", 0) or 0)
            led_item = QTableWidgetItem(str(led))
            led_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 1, led_item)

            # Integration time
            integration = float(ch_data.get("final_integration_ms", 0) or 0)
            int_item = QTableWidgetItem(f"{integration:.2f}")
            int_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 2, int_item)

            # Signal (top50 counts)
            signal = float(ch_data.get("final_top50_counts", 0) or 0)
            sig_item = QTableWidgetItem(f"{signal:.0f}")
            sig_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 3, sig_item)

            # Saturation percentage
            saturation = float(ch_data.get("final_percentage", 0) or 0)
            sat_item = QTableWidgetItem(f"{saturation:.1f}%")
            sat_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if saturation > 95:
                sat_item.setForeground(QColor("#FF3B30"))  # Red (saturated)
            elif saturation > 85:
                sat_item.setForeground(QColor("#34C759"))  # Green (good)
            else:
                sat_item.setForeground(QColor("#FF9500"))  # Orange (low)
            table.setItem(idx, 4, sat_item)

            # Iteration count
            iterations = int(ch_data.get("iterations", 0) or 0)
            iter_item = QTableWidgetItem(str(iterations))
            iter_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 5, iter_item)

        table.resizeColumnsToContents()
        table.setMaximumHeight(150)
        layout.addWidget(table)

        container_layout.addWidget(frame)

        # Title at bottom without box
        title = QLabel("LED Convergence Results")
        title.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #1D1D1F; padding-top: 4px; background: transparent; border: none;",
        )
        container_layout.addWidget(title)

        return container

    def _create_combined_qc_table(self) -> QWidget:
        """Create unified QC validation table with transmission, P-pol, and convergence data."""
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)

        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            "QFrame { background: white; border: 1px solid #D1D1D6; border-radius: 8px; }",
        )

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Single unified table with all metrics
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            [
                "Ch",
                "Dip Depth %",
                "FWHM (nm)",
                "P-Pol Signal",
                "Conv Iter",
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

        transmission_validation = self.calibration_data.get("transmission_validation", {})
        p_pol_spectra = self.calibration_data.get("p_pol_spectra", {})
        s_iterations = int(self.calibration_data.get("s_iterations", 0) or 0)
        p_iterations = int(self.calibration_data.get("p_iterations", 0) or 0)

        channels = ["a", "b", "c", "d"]
        table.setRowCount(4)

        for idx, ch in enumerate(channels):
            # Channel name
            ch_item = QTableWidgetItem(ch.upper())
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 0, ch_item)

            # Min Transmission % (actually dip_depth from calibration_data.py - higher is better)
            if ch in transmission_validation:
                ch_data = transmission_validation[ch]
                trans_min = ch_data.get("transmission_min")  # This is actually dip_depth %
                if trans_min is not None:
                    trans_item = QTableWidgetItem(f"{trans_min:.1f}")
                    trans_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    # Color code for dip depth: >70% = excellent (green), 50-70% = good (yellow), <50% = poor (red)
                    if trans_min >= 70:
                        trans_item.setForeground(QColor("#34C759"))
                    elif trans_min >= 50:
                        trans_item.setForeground(QColor("#FF9500"))
                    else:
                        trans_item.setForeground(QColor("#FF3B30"))
                    table.setItem(idx, 1, trans_item)
                else:
                    table.setItem(idx, 1, QTableWidgetItem("N/A"))

                # FWHM (nm)
                fwhm = ch_data.get("fwhm")
                if fwhm is not None:
                    fwhm_item = QTableWidgetItem(f"{fwhm:.1f}")
                    fwhm_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if fwhm < 80:
                        fwhm_item.setForeground(QColor("#34C759"))
                    elif fwhm < 100:
                        fwhm_item.setForeground(QColor("#FF9500"))
                    else:
                        fwhm_item.setForeground(QColor("#FF3B30"))
                    table.setItem(idx, 2, fwhm_item)
                else:
                    table.setItem(idx, 2, QTableWidgetItem("N/A"))

                # Status
                status = ch_data.get("status", "INDETERMINATE")
                if "[OK]" in status or "PASS" in status:
                    display_status = "GOOD"
                    status_color = QColor("#34C759")
                elif "[ERROR]" in status or "FAIL" in status:
                    display_status = "BAD"
                    status_color = QColor("#FF3B30")
                else:
                    display_status = "CHECK"
                    status_color = QColor("#FF9500")

                status_item = QTableWidgetItem(display_status)
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                status_item.setForeground(status_color)
                table.setItem(idx, 5, status_item)
            else:
                # No transmission data
                for col in [1, 2, 5]:
                    item = QTableWidgetItem("N/A")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(idx, col, item)

            # P-pol Signal (max brightness)
            if ch in p_pol_spectra and p_pol_spectra[ch] is not None:
                try:
                    p_arr = np.asarray(p_pol_spectra[ch], dtype=float)
                    p_max = float(np.max(p_arr))
                    brightness_item = QTableWidgetItem(f"{p_max:.0f}")
                    brightness_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if p_max > 50000:
                        brightness_item.setForeground(QColor("#34C759"))
                    elif p_max > 30000:
                        brightness_item.setForeground(QColor("#FF9500"))
                    else:
                        brightness_item.setForeground(QColor("#FF3B30"))
                    table.setItem(idx, 3, brightness_item)
                except Exception:
                    table.setItem(idx, 3, QTableWidgetItem("N/A"))
            else:
                table.setItem(idx, 3, QTableWidgetItem("N/A"))

            # Convergence Iterations (S/P format) — plain text, no colour
            if s_iterations > 0 or p_iterations > 0:
                iter_text = f"{s_iterations}/{p_iterations}"
                iter_item = QTableWidgetItem(iter_text)
                iter_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(idx, 4, iter_item)
            else:
                table.setItem(idx, 4, QTableWidgetItem("N/A"))

        # Optimize column widths
        table.setColumnWidth(0, 50)   # Ch
        table.setColumnWidth(1, 100)  # Dip Depth %
        table.setColumnWidth(2, 90)   # FWHM
        table.setColumnWidth(3, 100)  # P-Pol Signal
        table.setColumnWidth(4, 90)   # Conv Iter
        table.horizontalHeader().setSectionResizeMode(
            5,
            table.horizontalHeader().ResizeMode.Stretch,
        )  # Status
        table.setMaximumHeight(155)

        layout.addWidget(table)

        # Calibration notes / reminders
        notes_frame = QFrame()
        notes_frame.setStyleSheet(
            "QFrame {"
            "  background: #F9F9F9;"
            "  border-top: 1px solid #E5E5EA;"
            "  border-radius: 0px;"
            "}"
        )
        notes_layout = QVBoxLayout(notes_frame)
        notes_layout.setContentsMargins(8, 4, 8, 6)
        notes_layout.setSpacing(3)

        notes = [
            ("⚠", "Dry sensor will not produce usable data — ensure buffer is flowing before each run."),
            ("♻", "Reused sensor chips often fail QC — dip depth degrades with each use."),
            ("✗", "Channels not in use will show poor metrics — this is expected, not a fault."),
            ("⊘", "Dip depth < 50% on a new chip? Check fiber connection and flow cell seating."),
            ("~", "QC pass does not guarantee stable data — watch baseline drift in the first 5 min."),
        ]

        for icon, text in notes:
            row = QHBoxLayout()
            row.setSpacing(6)
            row.setContentsMargins(0, 0, 0, 0)

            icon_lbl = QLabel(icon)
            icon_lbl.setFixedWidth(14)
            icon_lbl.setStyleSheet("font-size: 11px; color: #86868B; background: transparent; border: none;")
            row.addWidget(icon_lbl)

            text_lbl = QLabel(text)
            text_lbl.setWordWrap(True)
            text_lbl.setStyleSheet(
                "font-size: 12px; color: #3A3A3C; background: transparent; border: none;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            row.addWidget(text_lbl, 1)

            notes_layout.addLayout(row)

        layout.addWidget(notes_frame)

        container_layout.addWidget(frame)

        return container

    def _create_ppol_brightness_table(self) -> QWidget:
        """Create P-pol brightness and iteration table."""
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(
            [
                "Ch",
                "P-Pol Signal",
                "Conv Iter",
            ],
        )
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

        channels = ["a", "b", "c", "d"]
        table.setRowCount(4)

        # Get P-pol spectra
        p_pol_spectra = self.calibration_data.get("p_pol_spectra", {})

        # Get iteration counts (stored directly in calibration_data now)
        # Ensure they're integers, not strings from JSON
        s_iterations = int(self.calibration_data.get("s_iterations", 0) or 0)
        p_iterations = int(self.calibration_data.get("p_iterations", 0) or 0)

        for idx, ch in enumerate(channels):
            # Channel name
            ch_item = QTableWidgetItem(ch.upper())
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 0, ch_item)

            # P-pol final brightness (max value)
            if ch in p_pol_spectra and p_pol_spectra[ch] is not None:
                try:
                    p_arr = np.asarray(p_pol_spectra[ch], dtype=float)
                    p_max = float(np.max(p_arr))
                    brightness_item = QTableWidgetItem(f"{p_max:.0f}")
                    brightness_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                    # Color code based on brightness level
                    if p_max > 50000:
                        brightness_item.setForeground(QColor("#34C759"))  # Green (good signal)
                    elif p_max > 30000:
                        brightness_item.setForeground(QColor("#FF9500"))  # Orange (moderate)
                    else:
                        brightness_item.setForeground(QColor("#FF3B30"))  # Red (low signal)

                    table.setItem(idx, 1, brightness_item)
                except Exception:
                    na_item = QTableWidgetItem("N/A")
                    na_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(idx, 1, na_item)
            else:
                na_item = QTableWidgetItem("N/A")
                na_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(idx, 1, na_item)

            # Convergence iterations (show S/P combined)
            if s_iterations > 0 or p_iterations > 0:
                iter_text = f"{s_iterations}/{p_iterations}" if p_iterations > 0 else str(s_iterations)
                iter_item = QTableWidgetItem(iter_text)
                iter_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                # Color code based on S-pol iteration count (primary convergence)
                if s_iterations <= 5:
                    iter_item.setForeground(QColor("#34C759"))  # Green (fast convergence)
                elif s_iterations <= 10:
                    iter_item.setForeground(QColor("#FF9500"))  # Orange (moderate)
                else:
                    iter_item.setForeground(QColor("#FF3B30"))  # Red (slow convergence)

                table.setItem(idx, 2, iter_item)
            else:
                na_item = QTableWidgetItem("N/A")
                na_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(idx, 2, na_item)

        # Optimize column widths
        table.setColumnWidth(0, 60)  # Ch
        table.setColumnWidth(1, 110)  # P-Pol Signal
        table.horizontalHeader().setSectionResizeMode(
            2,
            table.horizontalHeader().ResizeMode.Stretch,
        )  # Conv Iter
        table.setMaximumHeight(160)

        return table

    def _create_model_validation_table(self) -> QFrame:
        """Create model validation table showing predicted vs measured LED values."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            "QFrame { background: white; border: 1px solid #D1D1D6; border-radius: 8px; }",
        )

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("📊 Model Validation (Predicted vs Measured)")
        title.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #1D1D1F; padding-bottom: 3px;",
        )
        layout.addWidget(title)

        # Get model validation data from QC results
        qc_results = self.calibration_data.get("qc_results", {})
        model_val_s = qc_results.get("model_validation_s")
        model_val_p = qc_results.get("model_validation_p")

        if not model_val_s and not model_val_p:
            no_data_label = QLabel("No model validation data available")
            no_data_label.setStyleSheet(
                "color: #8E8E93; font-style: italic; padding: 20px;",
            )
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_data_label)
            return frame

        # Create table for S-mode and P-mode validation
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            [
                "Ch",
                "Mode",
                "Predicted",
                "Measured",
                "Error",
                "Error %",
            ],
        )
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

        channels = ["A", "B", "C", "D"]
        rows = []

        # Add S-mode rows
        if model_val_s:
            for ch in channels:
                if ch in model_val_s.get("predicted_leds", {}):
                    rows.append((ch, "S", model_val_s, ch))

        # Add P-mode rows
        if model_val_p:
            for ch in channels:
                if ch in model_val_p.get("predicted_leds", {}):
                    rows.append((ch, "P", model_val_p, ch))

        table.setRowCount(len(rows))

        for idx, (ch, mode, validation, ch_key) in enumerate(rows):
            # Channel
            ch_item = QTableWidgetItem(ch)
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 0, ch_item)

            # Mode
            mode_item = QTableWidgetItem(mode)
            mode_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 1, mode_item)

            # Predicted
            pred = validation["predicted_leds"][ch_key]
            pred_item = QTableWidgetItem(f"{pred}")
            pred_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 2, pred_item)

            # Measured
            meas = validation["measured_leds"][ch_key]
            meas_item = QTableWidgetItem(f"{meas}")
            meas_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 3, meas_item)

            # Error (Δ)
            dev = validation["deviations"][ch_key]
            dev_item = QTableWidgetItem(f"{dev:+d}")
            dev_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if abs(dev) <= 5:
                dev_item.setForeground(QColor("#34C759"))  # Green - excellent
            elif abs(dev) <= 15:
                dev_item.setForeground(QColor("#FF9500"))  # Orange - acceptable
            else:
                dev_item.setForeground(QColor("#FF3B30"))  # Red - poor
            table.setItem(idx, 4, dev_item)

            # Error %
            pct = validation["percent_errors"][ch_key]
            pct_item = QTableWidgetItem(f"{pct:+.1f}%")
            pct_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if abs(pct) <= 5:
                pct_item.setForeground(QColor("#34C759"))
            elif abs(pct) <= 15:
                pct_item.setForeground(QColor("#FF9500"))
            else:
                pct_item.setForeground(QColor("#FF3B30"))
            table.setItem(idx, 5, pct_item)

        # Optimize column widths
        table.resizeColumnsToContents()
        table.setColumnWidth(0, 50)  # Ch
        table.setColumnWidth(1, 60)  # Mode
        table.setColumnWidth(2, 80)  # Predicted
        table.setColumnWidth(3, 80)  # Measured
        table.setColumnWidth(4, 60)  # Error
        table.setColumnWidth(5, 80)  # Error %
        table.setMaximumHeight(240)
        layout.addWidget(table)

        # Summary statistics
        if model_val_s:
            avg_err_s = model_val_s.get("average_error_percent", 0)
            max_err_s = model_val_s.get("max_error_percent", 0)
            status_s = model_val_s.get("validation_status", "UNKNOWN").upper()

            summary_s = QLabel(
                f"S-mode: Avg={avg_err_s:.1f}%, Max={max_err_s:.1f}% ({status_s})",
            )
            summary_s.setStyleSheet("font-size: 10px; color: #1D1D1F; padding: 2px;")
            layout.addWidget(summary_s)

        if model_val_p:
            avg_err_p = model_val_p.get("average_error_percent", 0)
            max_err_p = model_val_p.get("max_error_percent", 0)
            status_p = model_val_p.get("validation_status", "UNKNOWN").upper()

            summary_p = QLabel(
                f"P-mode: Avg={avg_err_p:.1f}%, Max={max_err_p:.1f}% ({status_p})",
            )
            summary_p.setStyleSheet("font-size: 10px; color: #1D1D1F; padding: 2px;")
            layout.addWidget(summary_p)

        return frame

    def _create_orientation_table(self) -> QFrame:
        """Create polarizer orientation validation table."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            "QFrame { background: white; border: 1px solid #D1D1D6; border-radius: 8px; }",
        )

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        title = QLabel("🔄 Polarizer Orientation Validation")
        title.setStyleSheet(
            "font-size: 14px; font-weight: 600; color: #1D1D1F; padding-bottom: 5px;",
        )
        layout.addWidget(title)

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(
            ["Channel", "Orientation", "Diagnostic Reason", "Status"],
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
            logger.warning("[WARN] No orientation_validation data in QC report")
        else:
            logger.info(
                f"[OK] Orientation validation data for channels: {list(orientation_data.keys())}",
            )

        table.setRowCount(4)
        global_pass = False  # If any channel is correct, polarizer is OK

        for idx, ch in enumerate(["a", "b", "c", "d"]):
            # Channel name
            ch_item = QTableWidgetItem(f"Channel {ch.upper()}")
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 0, ch_item)

            if ch in orientation_data:
                # Handle both old format (dict) and new format (float FWHM)
                if isinstance(orientation_data[ch], dict):
                    # Old format: {'passed': bool, 'reason': str}
                    passed = orientation_data[ch].get("passed", None)
                    reason = orientation_data[ch].get("reason", "Unknown")
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
                    orient_text = "[OK] CORRECT"
                    global_pass = True
                elif passed is False:
                    orient_text = "[ERROR] INVERTED"
                else:
                    orient_text = "[WARN] INDETERMINATE"

                orient_item = QTableWidgetItem(orient_text)
                orient_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(idx, 1, orient_item)

                # Reason (replaces "confidence" column with actual diagnostic reason)
                reason_item = QTableWidgetItem(reason)
                reason_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(idx, 2, reason_item)

                # Status
                if passed is True:
                    status_text = "[OK] PASS"
                    status_color = "#34C759"
                elif passed is False:
                    status_text = "[ERROR] FAIL"
                    status_color = "#FF3B30"
                else:
                    status_text = "[WARN] INDETERMINATE"
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
            result_text = "[OK] GLOBAL POLARIZER ORIENTATION: CORRECT (at least one channel validates polarizer position)"
            result_color = "#34C759"
        else:
            result_text = "[WARN] GLOBAL POLARIZER ORIENTATION: CANNOT VALIDATE (check all channels)"
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
        frame.setStyleSheet(
            "QFrame { background: white; border: 1px solid #D1D1D6; border-radius: 8px; }",
        )

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        title = QLabel("🔬 Transmission Validation (SPR Dip Detection)")
        title.setStyleSheet(
            "font-size: 14px; font-weight: 600; color: #1D1D1F; padding-bottom: 5px;",
        )
        layout.addWidget(title)

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(
            [
                "Channel",
                "Dip Depth %",
                "FWHM (nm)",
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
            logger.warning("[WARN] No transmission_validation data in QC report")
        else:
            logger.info(
                f"[OK] Transmission validation keys: {list(transmission_validation.keys())}",
            )
            for ch, data in transmission_validation.items():
                logger.info(f"   Ch {ch}: {data}")

        # Display per-channel transmission results
        channels = ["a", "b", "c", "d"]
        table.setRowCount(len(channels))

        for idx, ch in enumerate(channels):
            # Channel name
            ch_item = QTableWidgetItem(f"Channel {ch.upper()}")
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 0, ch_item)

            if ch in transmission_validation:
                ch_data = transmission_validation[ch]

                # Min Transmission % (actually dip_depth from calibration_data.py - higher is better)
                trans_min = ch_data.get("transmission_min")  # This is actually dip_depth %
                if trans_min is not None:
                    trans_item = QTableWidgetItem(f"{trans_min:.1f}%")
                    trans_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    # Color code for dip depth: >70% = excellent (green), 50-70% = good (yellow), <50% = poor (red)
                    if trans_min >= 70:
                        trans_item.setForeground(QColor("#34C759"))
                    elif trans_min >= 50:
                        trans_item.setForeground(QColor("#FF9500"))
                    else:
                        trans_item.setForeground(QColor("#FF3B30"))
                    table.setItem(idx, 1, trans_item)
                else:
                    table.setItem(idx, 1, QTableWidgetItem("N/A"))

                # FWHM (moved to column 2)
                fwhm = ch_data.get("fwhm")
                if fwhm is not None:
                    fwhm_item = QTableWidgetItem(f"{fwhm:.1f}")
                    fwhm_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    # Color code FWHM quality: green < 80nm, yellow 80-100nm, red > 100nm
                    if fwhm < 80:
                        fwhm_item.setForeground(QColor("#34C759"))
                    elif fwhm < 100:
                        fwhm_item.setForeground(QColor("#FF9500"))
                    else:
                        fwhm_item.setForeground(QColor("#FF3B30"))
                    table.setItem(idx, 2, fwhm_item)
                else:
                    table.setItem(idx, 2, QTableWidgetItem("N/A"))

                # Status (now column 3)
                status = ch_data.get("status", "INDETERMINATE")
                # Convert status to user-friendly display
                if "[OK] PASS" in status or "PASS" in status:
                    display_status = "GOOD"
                    status_color = QColor("#34C759")
                elif "[ERROR] FAIL" in status or "FAIL" in status:
                    display_status = "BAD"
                    status_color = QColor("#FF3B30")
                else:
                    display_status = "CHECK"
                    status_color = QColor("#FF9500")

                status_item = QTableWidgetItem(display_status)
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                status_item.setForeground(status_color)
                table.setItem(idx, 3, status_item)
            else:
                # No data for this channel
                for col in range(1, 4):
                    item = QTableWidgetItem("N/A")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(idx, col, item)

        # Optimize column widths
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(False)
        table.setColumnWidth(0, 100)  # Channel
        table.setColumnWidth(1, 110)  # Dip Depth %
        table.setColumnWidth(2, 100)  # FWHM
        table.horizontalHeader().setSectionResizeMode(
            3,
            table.horizontalHeader().ResizeMode.Stretch,
        )  # Status
        table.setMinimumHeight(180)
        table.setMaximumHeight(220)

        # Create horizontal layout for tables (transmission table + calibration metrics table)
        tables_layout = QHBoxLayout()
        tables_layout.setSpacing(12)
        tables_layout.addWidget(table, stretch=1)

        # Add calibration metrics table next to transmission table
        metrics_table = self._create_calibration_metrics_table()
        if metrics_table:
            tables_layout.addWidget(metrics_table, stretch=1)

        layout.addLayout(tables_layout)

        # Overall result - check if all channels passed
        passed_channels = [
            ch
            for ch, data in transmission_validation.items()
            if "[OK] PASS" in data.get("status", "")
        ]
        failed_channels = [
            ch
            for ch, data in transmission_validation.items()
            if "[ERROR] FAIL" in data.get("status", "")
        ]

        if len(passed_channels) == len(channels) and len(failed_channels) == 0:
            result_text = "✓ SENSOR QUALITY: EXCELLENT - All channels calibrated successfully"
            result_color = "#34C759"
        elif len(failed_channels) > 0:
            result_text = f"⚠ SENSOR QUALITY: POOR - {len(failed_channels)} channel(s) need attention (check hydration)"
            result_color = "#FF3B30"
        else:
            result_text = (
                "[WARN] TRANSMISSION VALIDATION: INDETERMINATE (check calibration data)"
            )
            result_color = "#FF9500"

        result_label = QLabel(result_text)
        result_label.setWordWrap(True)
        result_label.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        result_label.setStyleSheet(f"""
            QLabel {{
                color: {result_color};
                font-weight: 600;
                padding: 12px;
                background: #F5F5F7;
                border-radius: 6px;
                border: 2px solid {result_color};
                font-size: 12px;
            }}
        """)
        result_label.setMinimumHeight(120)
        layout.addWidget(result_label)

        return frame

    def _build_header_stats_html(self) -> str:
        """Return inline HTML snippet: S-POL MAX / P-POL MAX / DARK AVG."""
        data = self.calibration_data
        s_pol_spectra = data.get("s_pol_spectra", {})
        p_pol_spectra = data.get("p_pol_spectra", {})
        dark_s_scans = data.get("dark_s_scans", {})
        dark_p_scans = data.get("dark_p_scans", {})
        sp_swap_applied = data.get("sp_swap_applied", False)

        s_parts, p_parts, dark_values = [], [], []
        for ch in ["a", "b", "c", "d"]:
            try:
                if ch in s_pol_spectra and s_pol_spectra[ch] is not None:
                    s_parts.append(f"{ch.upper()}:{np.max(np.asarray(s_pol_spectra[ch], dtype=float)):.0f}")
            except Exception:
                pass
            try:
                if ch in p_pol_spectra and p_pol_spectra[ch] is not None:
                    p_parts.append(f"{ch.upper()}:{np.max(np.asarray(p_pol_spectra[ch], dtype=float)):.0f}")
            except Exception:
                pass
            try:
                src = dark_s_scans.get(ch) or dark_p_scans.get(ch)
                if src is not None:
                    dark_values.append(float(np.mean(np.asarray(src, dtype=float))))
            except Exception:
                pass

        s_str = ", ".join(s_parts) or "N/A"
        p_str = ", ".join(p_parts) or "N/A"
        dark_str = f"{np.mean(dark_values):.0f}" if dark_values else "N/A"

        lbl = "<span style='font-size:10px; font-weight:600; color:#86868B;'>"
        val_s = "<span style='font-weight:600; color:#34C759;'>"
        val_p = "<span style='font-weight:600; color:#007AFF;'>"
        val_d = "<span style='font-weight:600; color:#8E8E93;'>"
        end = "</span>"
        sep = "&nbsp;&nbsp;•&nbsp;&nbsp;"

        swap = (
            "&nbsp;<span style='background:#FFF3CD; color:#856404; padding:1px 5px;"
            " border-radius:3px; font-weight:600; font-size:10px;'>⚠ S/P SWAPPED</span>"
            if sp_swap_applied else ""
        )

        return (
            f"{lbl}S-POL MAX{end} {val_s}{s_str}{end}"
            f"{sep}{lbl}P-POL MAX{end} {val_p}{p_str}{end}"
            f"{sep}{lbl}DARK AVG{end} {val_d}{dark_str}{end}"
            f"{swap}"
        )

    def _create_calibration_metrics_table(self) -> QTableWidget | None:
        """Create a table showing LED intensities and iteration counts per channel.

        Returns:
            QTableWidget with calibration metrics, or None if no data available
        """
        data = self.calibration_data
        led_intensities = data.get("led_intensities", {})
        convergence_summary = data.get("convergence_summary", {})

        if not led_intensities and not convergence_summary:
            return None

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Channel", "LED Intensity", "Iterations"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setStyleSheet("""
            QTableWidget {
                background: white;
                border: 1px solid #E5E5EA;
                border-radius: 4px;
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
            QTableWidget::item {
                padding: 4px;
            }
        """)

        channels_list = ["a", "b", "c", "d"]
        table.setRowCount(len(channels_list))

        # Extract iteration counts from convergence_summary if available
        channels_data = convergence_summary.get("channels", {}) if convergence_summary else {}

        for idx, ch in enumerate(channels_list):
            # Channel name
            ch_item = QTableWidgetItem(ch.upper())
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 0, ch_item)

            # LED intensity
            led = led_intensities.get(ch, 0)
            led_item = QTableWidgetItem(str(led))
            led_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 1, led_item)

            # Iterations (from convergence_summary if available)
            iterations = "N/A"
            if ch in channels_data and isinstance(channels_data[ch], dict):
                ch_iterations = channels_data[ch].get("iterations", None)
                if ch_iterations is not None:
                    iterations = str(ch_iterations)

            iter_item = QTableWidgetItem(iterations)
            iter_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(idx, 2, iter_item)

        # Resize columns to content
        table.resizeColumnsToContents()
        table.setMaximumHeight(160)

        return table

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

        # Create plot widget with fixed height for consistent layout
        plot_widget = pg.PlotWidget()
        plot_widget.setBackground("w")
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        plot_widget.setMinimumHeight(200)
        plot_widget.setMaximumHeight(280)

        # Configure axes
        plot_widget.setLabel("bottom", "λ", units="nm")

        if data_type == "transmission":
            plot_widget.setLabel("left", "Transmission", units="%")
            # Enable auto-range for transmission - don't constrain the Y-axis
            plot_widget.enableAutoRange(axis="y")
        else:
            plot_widget.setLabel("left", "Intensity", units="counts")

        # Set X-axis range to start at 570 nm for all plots
        wavelengths = self.calibration_data.get("wavelengths", None)
        if wavelengths is not None and len(wavelengths) > 0:
            # Ensure wavelengths are numeric (convert from string if needed)
            try:
                wavelengths_numeric = [float(w) for w in wavelengths]
                max_wl = max(wavelengths_numeric)
                plot_widget.setXRange(570, max_wl, padding=0)
            except (ValueError, TypeError):
                # Fallback if conversion fails
                plot_widget.setXRange(570, 720, padding=0)
        else:
            # Default range if no wavelengths available
            plot_widget.setXRange(570, 720, padding=0)

        # Plot data
        self._plot_data(plot_widget, data_type)

        # Set Y-axis range AFTER plotting to override auto-range
        if data_type == "s_pol":
            detector_serial = self.calibration_data.get("detector_serial", "")
            if detector_serial.startswith("ST"):
                # PhasePhotonics detector: lower count range (~2000-3000)
                plot_widget.setYRange(0, 5000, padding=0)
                plot_widget.disableAutoRange(axis="y")
            else:
                # USB4000: higher count range (~35000-50000)
                plot_widget.setYRange(0, 70000, padding=0)
                plot_widget.disableAutoRange(axis="y")
        elif data_type == "p_pol":
            # Also set appropriate range for P-pol
            detector_serial = self.calibration_data.get("detector_serial", "")
            if detector_serial.startswith("ST"):
                plot_widget.setYRange(0, 3000, padding=0)
                plot_widget.disableAutoRange(axis="y")
            else:
                plot_widget.setYRange(0, 50000, padding=0)
                plot_widget.disableAutoRange(axis="y")

        layout.addWidget(plot_widget)

        return container

    def _plot_data(self, plot_widget: pg.PlotWidget, data_type: str):
        """Plot data on the graph widget.

        Args:
            plot_widget: PyQtGraph PlotWidget
            data_type: Type of data to plot

        """
        try:
            data = self.calibration_data

            logger.debug(f"Plotting {data_type}")

            wavelengths = data.get("wavelengths", None)

            # Default wavelength array
            default_wavelengths = np.linspace(560, 720, 3648)

            if wavelengths is None:
                wavelengths = default_wavelengths
                logger.warning("No wavelengths in QC data, using default range")
            else:
                # Convert to numeric numpy array (wavelengths may be stored as strings in JSON)
                try:
                    # If wavelengths is a string representation of a list, parse it first
                    if isinstance(wavelengths, str):
                        import json
                        import ast
                        # Try JSON first
                        try:
                            parsed = json.loads(wavelengths)
                        except:
                            # Try ast.literal_eval as fallback
                            try:
                                parsed = ast.literal_eval(wavelengths)
                            except:
                                # Give up, use default
                                logger.warning("Failed to parse wavelengths string, using default")
                                wavelengths = default_wavelengths
                                parsed = None
                    else:
                        parsed = wavelengths

                    if parsed is not None:
                        wavelengths = parsed

                    # Now convert to numpy array (only if not already set to default)
                    if not isinstance(wavelengths, np.ndarray):
                        wavelengths = np.array([float(w) for w in wavelengths], dtype=float)

                except Exception as e:
                    logger.warning(f"Failed to convert wavelengths to numeric array: {e}")
                    wavelengths = default_wavelengths

            # Final safety check - ensure wavelengths is a valid numpy array
            if not isinstance(wavelengths, np.ndarray) or len(wavelengths) == 0:
                logger.warning(f"Wavelengths invalid (type: {type(wavelengths)}, len: {len(wavelengths) if hasattr(wavelengths, '__len__') else 'N/A'}), using default")
                wavelengths = default_wavelengths

            # Channel colors (matching existing UI)
            colors = {
            "a": (0, 0, 0, 200),  # Black
            "b": (255, 0, 81, 200),  # Red
            "c": (0, 174, 255, 200),  # Blue
            "d": (0, 150, 80, 200),  # Green (matches main UI)
            }

            # Get data based on type
            data_dict = {}
            if data_type == "s_pol":
                data_dict = data.get("s_pol_spectra", {})
            elif data_type == "p_pol":
                data_dict = data.get("p_pol_spectra", {})
            elif data_type == "dark":
                # NEW: Support per-channel darks for both S-pol and P-pol
                dark_s_scans = data.get("dark_s_scans", {})
                dark_p_scans = data.get("dark_p_scans", {})

                # If we have per-channel darks, plot all 8 (4 channels × 2 polarizations)
                if dark_s_scans or dark_p_scans:
                    # Plot S-pol darks with solid lines
                    from affilabs.utils.detector_config import filter_valid_wavelength_data
                    detector_serial = self.calibration_data.get("detector_serial", None)

                    for channel in ["a", "b", "c", "d"]:
                        if channel in dark_s_scans:
                            spectrum = dark_s_scans[channel]
                            if spectrum is not None and len(spectrum) > 0:
                                wavelengths_plot = (
                                    wavelengths
                                    if len(wavelengths) == len(spectrum)
                                    else np.linspace(
                                        wavelengths[0],
                                        wavelengths[-1],
                                        len(spectrum),
                                    )
                                )
                                # Filter for Phase Photonics (noisy data below 570nm)
                                wavelengths_plot, spectrum = filter_valid_wavelength_data(
                                    wavelengths_plot,
                                    spectrum,
                                    detector_serial=detector_serial,
                                )
                                pen = pg.mkPen(
                                    color=colors.get(channel, (128, 128, 128, 200)),
                                    width=2,
                                    style=Qt.PenStyle.SolidLine,
                                )
                                plot_widget.plot(
                                    wavelengths_plot,
                                    spectrum,
                                    pen=pen,
                                    name=f"{channel.upper()}-S (S-pol dark)",
                                )
                    # Plot P-pol darks with dashed lines
                    for channel in ["a", "b", "c", "d"]:
                        if channel in dark_p_scans:
                            spectrum = dark_p_scans[channel]
                            if spectrum is not None and len(spectrum) > 0:
                                wavelengths_plot = (
                                    wavelengths
                                    if len(wavelengths) == len(spectrum)
                                    else np.linspace(
                                        wavelengths[0],
                                        wavelengths[-1],
                                        len(spectrum),
                                    )
                                )
                                # Filter for Phase Photonics (noisy data below 570nm)
                                wavelengths_plot, spectrum = filter_valid_wavelength_data(
                                    wavelengths_plot,
                                    spectrum,
                                    detector_serial=detector_serial,
                                )
                                pen = pg.mkPen(
                                    color=colors.get(channel, (128, 128, 128, 200)),
                                    width=2,
                                    style=Qt.PenStyle.DashLine,
                                )
                                plot_widget.plot(
                                    wavelengths_plot,
                                    spectrum,
                                    pen=pen,
                                    name=f"{channel.upper()}-P (P-pol dark)",
                                )
                    # Add legend
                    plot_widget.addLegend(offset=(10, 10))
                    return  # Skip normal plotting below
                # Fallback to legacy single dark per channel
                data_dict = data.get("dark_scan", {})
            elif data_type == "transmission":
                data_dict = data.get("transmission_spectra", {})

            # Log if no data found
            if not data_dict:
                logger.warning(f"No {data_type} data found in calibration_data!")
                # Show "No Data" message on plot
                plot_widget.clear()
                text_item = pg.TextItem(
                    text=f"No {data_type} data available",
                    anchor=(0.5, 0.5),
                    color=(128, 128, 128)
                )
                plot_widget.addItem(text_item)
                text_item.setPos(640, 2000)  # Center position
                return

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

                            # CRITICAL: Filter wavelengths for Phase Photonics detector
                        # Phase Photonics has noisy data below 570nm
                        from affilabs.utils.detector_config import filter_valid_wavelength_data
                        detector_serial = self.calibration_data.get("detector_serial", None)
                        wavelengths_plot, spectrum = filter_valid_wavelength_data(
                            wavelengths_plot,
                            spectrum,
                            detector_serial=detector_serial,
                        )

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

            # Add pass region overlay for S-Pol
            if data_type == "s_pol":
                from pyqtgraph import LinearRegionItem

                # Adapt pass region based on detector type
                detector_serial = self.calibration_data.get("detector_serial", "")
                if detector_serial.startswith("ST"):
                    # PhasePhotonics detector: 75%-95% of typical max (~2000)
                    pass_min, pass_max = 1500, 1900
                else:
                    # USB4000: 35,000-50,000 counts
                    pass_min, pass_max = 35000, 50000

                pass_region = LinearRegionItem(
                    values=[pass_min, pass_max],
                    orientation='horizontal',
                    brush=(0, 255, 0, 30),  # Green with transparency
                    movable=False
                )
                plot_widget.addItem(pass_region)

                # Add legend
                plot_widget.addLegend(offset=(10, 10))

        except Exception as e:
            logger.error(f"Error plotting {data_type} data: {e}", exc_info=True)
            # Show error text on plot
            plot_widget.clear()
            text_item = pg.TextItem(
                text=f"Error displaying data:\n{str(e)[:200]}",
                anchor=(0.5, 0.5),
                color=(255, 0, 0)
            )
            plot_widget.addItem(text_item)
            text_item.setPos(640, 2000)  # Center-ish position

    def _create_analysis_visualization(self) -> QWidget:
        """Create calibration analysis visualization tab with matplotlib charts."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Get QC results
        qc_results = self.calibration_data.get("qc_results", {})

        # Check if this is a failed calibration with limited data
        has_channel_data = any(ch in qc_results for ch in ["a", "b", "c", "d"])

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
        fig = Figure(figsize=(14, 8), facecolor="white")
        canvas = FigureCanvasQTAgg(fig)

        channels = ["a", "b", "c", "d"]
        channel_labels = ["A", "B", "C", "D"]
        colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A"]

        # Check if polarizer is inverted
        ps_ratios = []
        all_inverted = True
        for ch in channels:
            if ch in qc_results:
                ratio = qc_results[ch].get("p_s_ratio", 0)
                ps_ratios.append(ratio)
                if ratio < 1.15:  # Threshold for warning
                    all_inverted = False
            else:
                ps_ratios.append(0)
                all_inverted = False

        # Title with warning if inverted
        title_text = "Calibration Analysis"
        title_color = "black"
        if all_inverted and any(r > 1.15 for r in ps_ratios):
            title_text = "Calibration Analysis - WARNING: Polarizer May Be Inverted"
            title_color = "red"

        fig.suptitle(title_text, fontsize=14, fontweight="bold", color=title_color)

        # Plot 1: S-pol max counts
        ax1 = fig.add_subplot(2, 3, 1)
        s_max = [qc_results.get(ch, {}).get("s_max_counts", 0) for ch in channels]
        bars1 = ax1.bar(
            channel_labels,
            s_max,
            color=colors,
            alpha=0.7,
            edgecolor="black",
            linewidth=2,
        )
        ax1.set_ylabel("Max Counts", fontsize=11, fontweight="bold")
        ax1.set_title(
            "S-Polarization Peak\n(Should be HIGHER than P)",
            fontsize=10,
            fontweight="bold",
        )
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim(0, max(s_max) * 1.2 if s_max else 70000)
        for bar, val in zip(bars1, s_max, strict=False):
            if val > 0:
                ax1.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(s_max) * 0.02,
                    f"{val:.0f}",
                    ha="center",
                    va="bottom",
                    fontweight="bold",
                    fontsize=9,
                )

        # Plot 2: P-pol max counts
        ax2 = fig.add_subplot(2, 3, 2)
        p_max = [qc_results.get(ch, {}).get("p_max_counts", 0) for ch in channels]
        bars2 = ax2.bar(
            channel_labels,
            p_max,
            color=colors,
            alpha=0.7,
            edgecolor="black",
            linewidth=2,
        )
        ax2.set_ylabel("Max Counts", fontsize=11, fontweight="bold")
        ax2.set_title(
            "P-Polarization Peak\n(Should be LOWER than S)",
            fontsize=10,
            fontweight="bold",
        )
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(0, max(p_max) * 1.2 if p_max else 70000)
        for bar, val in zip(bars2, p_max, strict=False):
            if val > 0:
                ax2.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(p_max) * 0.02,
                    f"{val:.0f}",
                    ha="center",
                    va="bottom",
                    fontweight="bold",
                    fontsize=9,
                )

        # Plot 3: P/S Ratio
        ax3 = fig.add_subplot(2, 3, 3)
        bar_colors = ["red" if r > 1.15 else "green" for r in ps_ratios]
        bars3 = ax3.bar(
            channel_labels,
            ps_ratios,
            color=bar_colors,
            alpha=0.7,
            edgecolor="black",
            linewidth=2,
        )
        ax3.axhline(
            y=1.0,
            color="green",
            linestyle="--",
            linewidth=2,
            label="Expected: P/S < 1.0",
        )
        ax3.axhline(
            y=1.15,
            color="orange",
            linestyle="--",
            linewidth=2,
            label="Warning: 1.15",
        )
        ax3.set_ylabel("P/S Ratio", fontsize=11, fontweight="bold")
        title_suffix = (
            "\n(INVERTED!)"
            if all_inverted and any(r > 1.15 for r in ps_ratios)
            else "\n(Expected < 1.0)"
        )
        ax3.set_title(
            "P/S Ratio" + title_suffix,
            fontsize=10,
            fontweight="bold",
            color="red" if all_inverted else "black",
        )
        ax3.grid(True, alpha=0.3)
        ax3.legend(loc="upper right", fontsize=8)
        max_ratio = max(ps_ratios) if ps_ratios else 8
        ax3.set_ylim(0, max(max_ratio * 1.2, 8))
        for bar, val in zip(bars3, ps_ratios, strict=False):
            if val > 0:
                ax3.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max_ratio * 0.02,
                    f"{val:.2f}x",
                    ha="center",
                    va="bottom",
                    fontweight="bold",
                    fontsize=9,
                    color="red" if val > 1.15 else "black",
                )

        # Plot 4: LED Intensities
        ax4 = fig.add_subplot(2, 3, 4)
        led_intensities = self.calibration_data.get("s_mode_intensity", {})
        led_vals = [led_intensities.get(ch, 0) for ch in channels]
        bars4 = ax4.bar(
            channel_labels,
            led_vals,
            color=colors,
            alpha=0.7,
            edgecolor="black",
            linewidth=2,
        )
        ax4.set_ylabel("LED Intensity (0-255)", fontsize=11, fontweight="bold")
        ax4.set_title("LED Intensities (Calibrated)", fontsize=10, fontweight="bold")
        ax4.set_ylim(0, 280)
        ax4.grid(True, alpha=0.3)
        for bar, val in zip(bars4, led_vals, strict=False):
            if val > 0:
                ax4.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 5,
                    f"{val}",
                    ha="center",
                    va="bottom",
                    fontweight="bold",
                    fontsize=9,
                )

        # Plot 5: SPR Wavelengths
        ax5 = fig.add_subplot(2, 3, 5)
        spr_wl = [qc_results.get(ch, {}).get("dip_wavelength", 0) for ch in channels]
        bars5 = ax5.bar(
            channel_labels,
            spr_wl,
            color=colors,
            alpha=0.7,
            edgecolor="black",
            linewidth=2,
        )
        ax5.set_ylabel("Wavelength (nm)", fontsize=11, fontweight="bold")
        ax5.set_title("SPR Peak Wavelengths", fontsize=10, fontweight="bold")
        min_wl = (
            min([w for w in spr_wl if w > 0]) if any(w > 0 for w in spr_wl) else 620
        )
        max_wl = max(spr_wl) if spr_wl else 680
        ax5.set_ylim(min_wl - 20, max_wl + 20)
        ax5.grid(True, alpha=0.3)
        for bar, val in zip(bars5, spr_wl, strict=False):
            if val > 0:
                ax5.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 1,
                    f"{val:.1f}nm",
                    ha="center",
                    va="bottom",
                    fontweight="bold",
                    fontsize=9,
                )

        # Plot 6: QC Summary
        ax6 = fig.add_subplot(2, 3, 6)
        ax6.axis("off")

        # Build summary text
        s_integration = self.calibration_data.get("s_integration_time", 0)
        p_integration = self.calibration_data.get("p_integration_time", 0)
        polarizer_s = self.calibration_data.get("polarizer_s_position", "N/A")
        polarizer_p = self.calibration_data.get("polarizer_p_position", "N/A")

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
        fwhm_vals = [qc_results.get(ch, {}).get("fwhm", 0) for ch in channels]
        avg_fwhm = (
            sum(fwhm_vals) / len([f for f in fwhm_vals if f > 0])
            if any(f > 0 for f in fwhm_vals)
            else 0
        )
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

        ax6.text(
            0.05,
            0.95,
            summary_text,
            transform=ax6.transAxes,
            fontsize=9,
            verticalalignment="top",
            fontfamily="monospace",
            bbox=dict(
                boxstyle="round",
                facecolor="wheat" if all_inverted else "lightblue",
                alpha=0.5,
            ),
        )

        fig.tight_layout(rect=[0, 0, 1, 0.97])
        layout.addWidget(canvas)

        return widget

    def _create_failure_diagnostic(
        self,
        layout: QVBoxLayout,
        qc_results: dict,
    ) -> QWidget:
        """Create diagnostic view for failed calibration."""
        widget = QWidget()
        diag_layout = QVBoxLayout(widget)
        diag_layout.setContentsMargins(20, 20, 20, 20)
        diag_layout.setSpacing(15)

        # Title
        title = QLabel("[ERROR] Calibration Failed - Diagnostic Information")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #D32F2F;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        diag_layout.addWidget(title)

        # Get error info
        old_s = qc_results.get("old_s_pos", "N/A")
        old_p = qc_results.get("old_p_pos", "N/A")

        # Create matplotlib figure for diagnostic plots
        fig = Figure(figsize=(12, 6), facecolor="white")
        canvas = FigureCanvasQTAgg(fig)

        # Plot 1: Servo position comparison
        ax1 = fig.add_subplot(1, 2, 1)
        positions = [
            "Old S-pos",
            "Old P-pos",
            "New S-pos\n(expected)",
            "New P-pos\n(expected)",
        ]
        values = [
            old_s if isinstance(old_s, (int, float)) else 0,
            old_p if isinstance(old_p, (int, float)) else 0,
            89,
            179,
        ]
        colors = ["red", "red", "green", "green"]
        bars = ax1.bar(
            positions,
            values,
            color=colors,
            alpha=0.7,
            edgecolor="black",
            linewidth=2,
        )
        ax1.set_ylabel("Servo Angle (degrees)", fontsize=11, fontweight="bold")
        ax1.set_title("Servo Position Issue", fontsize=12, fontweight="bold")
        ax1.grid(True, alpha=0.3, axis="y")
        ax1.set_ylim(0, 200)

        for bar, val in zip(bars, values, strict=False):
            if val > 0:
                ax1.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 5,
                    f"{val}°",
                    ha="center",
                    va="bottom",
                    fontweight="bold",
                    fontsize=10,
                )

        # Plot 2: Expected behavior diagram
        ax2 = fig.add_subplot(1, 2, 2)
        ax2.axis("off")

        diagnostic_text = f"""
FAILURE DIAGNOSIS:

[ERROR] Old Servo Positions Detected:
   • S-position: {old_s}° (should be 89°)
   • P-position: {old_p}° (should be 179°)

[WARN]  Problem Detected:
   • Controller did not confirm movement
   • Possible causes:
     - Old EEPROM values still loaded
     - Communication error
     - Servo hardware issue

[OK] Fixes Applied:
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

        ax2.text(
            0.05,
            0.95,
            diagnostic_text,
            transform=ax2.transAxes,
            fontsize=9,
            verticalalignment="top",
            family="monospace",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )

        plt.tight_layout()

    def _export_to_pdf(self):
        """Export QC report to PDF file with graphs and ALL tables - comprehensive report."""
        try:
            from pathlib import Path

            from PySide6.QtWidgets import QFileDialog
            from matplotlib.backends.backend_pdf import PdfPages
            import matplotlib.pyplot as plt
            from datetime import datetime
            import numpy as np

            device_serial = self.calibration_data.get("detector_serial", "Unknown")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"QC_Report_{device_serial}_{timestamp}.pdf"

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export QC Report to PDF",
                str(Path.home() / "Documents" / default_filename),
                "PDF Files (*.pdf)",
            )

            if file_path:
                # Create COMPREHENSIVE PDF with all data
                with PdfPages(file_path) as pdf:
                    # PAGE 1: Graphs and Summary Tables
                    fig = plt.figure(figsize=(17, 11))  # Landscape A3-like

                    # Use GridSpec for precise layout control
                    import matplotlib.gridspec as gridspec
                    gs = gridspec.GridSpec(4, 3, figure=fig, height_ratios=[0.6, 5, 1.8, 1.8],
                                          hspace=0.4, wspace=0.3,
                                          left=0.06, right=0.97, top=0.96, bottom=0.05)

                    # === HEADER SECTION ===
                    header_ax = fig.add_subplot(gs[0, :])
                    header_ax.axis('off')

                    # Title
                    header_ax.text(0.01, 0.7, f"📊 Calibration QC Report - {device_serial}",
                                  fontsize=18, fontweight='bold', va='center')

                    # Metadata (right side)
                    from version import __version__
                    cal_timestamp = self.calibration_data.get('timestamp', 'N/A')
                    device_type = self.calibration_data.get('device_type', 'N/A')
                    fw_version = self.calibration_data.get('firmware_version', 'N/A')
                    integration = self.calibration_data.get('integration_time_ms', 'N/A')

                    metadata = f"📅 {cal_timestamp}  |  Device: {device_type}  |  FW: {fw_version}  |  Integration: {integration} ms  |  v{__version__}"
                    header_ax.text(0.01, 0.1, metadata, fontsize=10, color='#666666', va='center')

                    # === THREE GRAPHS IN ONE ROW ===
                    wavelengths = self.calibration_data.get('wavelengths', [])
                    channels = ['a', 'b', 'c', 'd']
                    colors = ['black', 'red', 'blue', 'green']

                    # S-Pol graph
                    ax1 = fig.add_subplot(gs[1, 0])
                    s_pol_data = self.calibration_data.get('s_pol_spectra', {})

                    # Calculate max values for auto-scaling
                    s_max_values = []
                    for ch, color in zip(channels, colors):
                        if ch in s_pol_data:
                            spectrum = s_pol_data[ch]
                            ax1.plot(wavelengths, spectrum, color=color, label=f'Ch {ch.upper()}', linewidth=1.5)
                            if len(spectrum) > 0:
                                s_max_values.append(max(spectrum))

                    # Auto-scale y-axis based on detector type
                    detector_serial_str = str(device_serial)
                    if detector_serial_str.startswith("ST"):
                        detector_max = 8192
                        target_min, target_max = 4000, 7000
                    else:
                        detector_max = 65535
                        target_min, target_max = 35000, 50000

                    if s_max_values:
                        y_max = max(s_max_values) * 1.2
                        ax1.set_ylim(0, min(y_max, detector_max * 1.1))
                    else:
                        ax1.set_ylim(0, detector_max)

                    ax1.axhspan(target_min, target_max, alpha=0.2, color='green', zorder=1,
                               label=f'Target ({target_min/1000:.1f}k-{target_max/1000:.1f}k)')

                    ax1.set_title('S-Pol Spectra', fontsize=12, fontweight='bold', pad=8)
                    ax1.set_xlabel('λ (nm)', fontsize=11, fontweight='bold')
                    ax1.set_ylabel('Counts', fontsize=11, fontweight='bold')
                    ax1.set_xlim(570, max(wavelengths) if len(wavelengths) > 0 else 720)
                    ax1.legend(fontsize=9, loc='best')
                    ax1.grid(True, alpha=0.3)

                    # P-Pol graph
                    ax2 = fig.add_subplot(gs[1, 1])
                    p_pol_data = self.calibration_data.get('p_pol_spectra', {})
                    p_max_values = []
                    for ch, color in zip(channels, colors):
                        if ch in p_pol_data:
                            spectrum = p_pol_data[ch]
                            ax2.plot(wavelengths, spectrum, color=color, label=f'Ch {ch.upper()}', linewidth=1.5)
                            if len(spectrum) > 0:
                                p_max_values.append(max(spectrum))

                    if p_max_values:
                        y_max = max(p_max_values) * 1.2
                        ax2.set_ylim(0, y_max)
                    else:
                        ax2.set_ylim(0, 8192 if detector_serial_str.startswith("ST") else 70000)

                    ax2.set_title('P-Pol Spectra', fontsize=12, fontweight='bold', pad=8)
                    ax2.set_xlabel('λ (nm)', fontsize=11, fontweight='bold')
                    ax2.set_ylabel('Counts', fontsize=11, fontweight='bold')
                    ax2.set_xlim(570, max(wavelengths) if len(wavelengths) > 0 else 720)
                    ax2.legend(fontsize=9, loc='best')
                    ax2.grid(True, alpha=0.3)

                    # Transmission graph
                    ax3 = fig.add_subplot(gs[1, 2])
                    trans_data = self.calibration_data.get('transmission_spectra', {})
                    for ch, color in zip(channels, colors):
                        if ch in trans_data:
                            ax3.plot(wavelengths, trans_data[ch], color=color, label=f'Ch {ch.upper()}', linewidth=1.5)
                    ax3.set_title('Transmission Spectra', fontsize=12, fontweight='bold', pad=8)
                    ax3.set_xlabel('λ (nm)', fontsize=11, fontweight='bold')
                    ax3.set_ylabel('Transmission %', fontsize=11, fontweight='bold')
                    ax3.set_xlim(570, max(wavelengths) if len(wavelengths) > 0 else 720)
                    ax3.legend(fontsize=9, loc='best')
                    ax3.grid(True, alpha=0.3)

                    # === LED CONVERGENCE TABLE (Row 2) ===
                    conv_ax = fig.add_subplot(gs[2, :])
                    conv_ax.axis('off')

                    convergence_summary = self.calibration_data.get('convergence_summary', {})
                    if convergence_summary:
                        conv_ax.text(0.01, 0.95, '📋 LED Convergence Results',
                                    fontsize=12, fontweight='bold', va='top')

                        channels_data = convergence_summary.get('channels', {})

                        # Create table data
                        table_data = []
                        headers = ['Ch', 'LED', 'Integration (ms)', 'Signal', 'Saturation %', 'Iterations']

                        for ch in ['a', 'b', 'c', 'd']:
                            if ch in channels_data:
                                ch_data = channels_data[ch]
                                led = int(ch_data.get('final_led', 0) or 0)
                                integ = float(ch_data.get('final_integration_ms', 0) or 0)
                                signal = float(ch_data.get('final_top50_counts', 0) or 0)
                                sat = float(ch_data.get('final_percentage', 0) or 0)
                                iters = int(ch_data.get('iterations', 0) or 0)

                                table_data.append([
                                    ch.upper(),
                                    f'{led}',
                                    f'{integ:.2f}',
                                    f'{signal:.0f}',
                                    f'{sat:.1f}%',
                                    f'{iters}'
                                ])

                        if table_data:
                            # Draw table
                            table = conv_ax.table(cellText=table_data, colLabels=headers,
                                                cellLoc='center', loc='center',
                                                bbox=[0.05, 0.0, 0.9, 0.8])
                            table.auto_set_font_size(False)
                            table.set_fontsize(10)
                            table.scale(1, 1.8)

                            # Style headers
                            for i in range(len(headers)):
                                table[(0, i)].set_facecolor('#F5F5F7')
                                table[(0, i)].set_text_props(weight='bold')

                    # === QC VALIDATION TABLES (Row 3) - Split into two columns ===
                    qc_left_ax = fig.add_subplot(gs[3, :2])
                    qc_left_ax.axis('off')

                    # Left: Transmission & FWHM Data
                    qc_left_ax.text(0.01, 0.95, '✅ Transmission & Spectral Quality',
                                   fontsize=12, fontweight='bold', va='top')

                    transmission_validation = self.calibration_data.get('transmission_validation', {})
                    if transmission_validation:
                        trans_data = []
                        trans_headers = ['Ch', 'Min Trans %', 'FWHM (nm)', 'Status']

                        for ch in ['a', 'b', 'c', 'd']:
                            if ch in transmission_validation:
                                ch_data = transmission_validation[ch]
                                trans_min = ch_data.get('transmission_min')
                                fwhm = ch_data.get('fwhm')
                                status = ch_data.get('status', 'UNKNOWN')

                                # Simplify status
                                if '[OK]' in status or 'PASS' in status:
                                    status_text = 'GOOD'
                                elif '[ERROR]' in status or 'FAIL' in status:
                                    status_text = 'BAD'
                                else:
                                    status_text = 'CHECK'

                                trans_data.append([
                                    ch.upper(),
                                    f'{trans_min:.1f}' if trans_min is not None else 'N/A',
                                    f'{fwhm:.1f}' if fwhm is not None else 'N/A',
                                    status_text
                                ])

                        if trans_data:
                            trans_table = qc_left_ax.table(cellText=trans_data, colLabels=trans_headers,
                                                          cellLoc='center', loc='center',
                                                          bbox=[0.05, 0.0, 0.9, 0.8])
                            trans_table.auto_set_font_size(False)
                            trans_table.set_fontsize(10)
                            trans_table.scale(1, 1.8)

                            for i in range(len(trans_headers)):
                                trans_table[(0, i)].set_facecolor('#F5F5F7')
                                trans_table[(0, i)].set_text_props(weight='bold')

                    # Right: P-Pol Brightness & Convergence
                    qc_right_ax = fig.add_subplot(gs[3, 2])
                    qc_right_ax.axis('off')

                    qc_right_ax.text(0.01, 0.95, '💡 P-Pol Signal & Convergence',
                                    fontsize=12, fontweight='bold', va='top')

                    p_pol_spectra = self.calibration_data.get('p_pol_spectra', {})
                    s_iterations = int(self.calibration_data.get('s_iterations', 0) or 0)
                    p_iterations = int(self.calibration_data.get('p_iterations', 0) or 0)

                    if p_pol_spectra:
                        ppol_data = []
                        ppol_headers = ['Ch', 'P-Pol Max', 'Conv Iter']

                        for ch in ['a', 'b', 'c', 'd']:
                            if ch in p_pol_spectra and p_pol_spectra[ch] is not None:
                                try:
                                    p_arr = np.asarray(p_pol_spectra[ch], dtype=float)
                                    p_max = float(np.max(p_arr))
                                    iter_text = f"{s_iterations}/{p_iterations}" if p_iterations > 0 else str(s_iterations)

                                    ppol_data.append([
                                        ch.upper(),
                                        f'{p_max:.0f}',
                                        iter_text
                                    ])
                                except:
                                    ppol_data.append([ch.upper(), 'N/A', 'N/A'])
                            else:
                                ppol_data.append([ch.upper(), 'N/A', 'N/A'])

                        if ppol_data:
                            ppol_table = qc_right_ax.table(cellText=ppol_data, colLabels=ppol_headers,
                                                          cellLoc='center', loc='center',
                                                          bbox=[0.05, 0.0, 0.9, 0.8])
                            ppol_table.auto_set_font_size(False)
                            ppol_table.set_fontsize(10)
                            ppol_table.scale(1, 1.8)

                            for i in range(len(ppol_headers)):
                                ppol_table[(0, i)].set_facecolor('#F5F5F7')
                                ppol_table[(0, i)].set_text_props(weight='bold')

                    pdf.savefig(fig, dpi=150)
                    plt.close()

                from affilabs.widgets.message import show_message
                show_message(
                    f"PDF exported successfully to:\n{file_path}",
                    msg_type="Information",
                    title="PDF Export",
                )
                logger.info(f"✅ PDF report exported: {file_path}")

        except Exception as e:
            logger.error(f"Failed to export PDF: {e}")
            import traceback
            traceback.print_exc()
            from affilabs.widgets.message import show_message
            show_message(
                f"Failed to export PDF:\n{str(e)}",
                msg_type="Critical",
                title="Export Error",
            )
            from affilabs.widgets.message import show_message
            show_message(f"Failed to export PDF:\n{e!s}", "Export Error", "Error")

    def _export_to_html(self):
        """Export QC report to HTML file."""
        try:
            from pathlib import Path

            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtWidgets import QFileDialog

            device_serial = self.calibration_data.get("detector_serial", "Unknown")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"QC_Report_{device_serial}_{timestamp}.html"

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export QC Report to HTML",
                str(Path.home() / "Documents" / default_filename),
                "HTML Files (*.html)",
            )

            if file_path:
                from affilabs.managers.qc_report_manager import QCReportManager

                qc_manager = QCReportManager()

                # Find the latest report
                reports_dir = qc_manager._get_reports_dir(device_serial)
                latest_json = reports_dir / "qc_report_latest.json"

                if latest_json.exists():
                    # Export to user-selected location
                    html_path = qc_manager.export_to_html(latest_json, Path(file_path))

                    from affilabs.widgets.message import show_message

                    result = show_message(
                        f"HTML report exported successfully!\n\n{html_path}\n\nOpen in browser?",
                        "Export Complete",
                        "Information",
                    )

                    # Open in default browser
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(html_path)))
                    logger.info(f"HTML report exported and opened: {html_path}")
                else:
                    from affilabs.widgets.message import show_message

                    show_message(
                        "No saved QC report found.\nReport must be saved first.",
                        "Export Error",
                        "Warning",
                    )

        except Exception as e:
            logger.error(f"Failed to export HTML: {e}")
            from affilabs.widgets.message import show_message

            show_message(f"Failed to export HTML:\n{e!s}", "Export Error", "Error")

    @staticmethod
    def show_qc_report(parent=None, calibration_data: dict = None):
        """Static method to show QC report dialog (modal, blocking).

        Args:
            parent: Parent widget
            calibration_data: Calibration data dictionary

        Returns:
            The dialog instance (returns after the dialog is closed)

        """
        dialog = CalibrationQCDialog(parent=parent, calibration_data=calibration_data)

        # Ensure modal behavior (blocks until user closes)
        dialog.setModal(True)
        dialog.setWindowModality(Qt.ApplicationModal)

        # Execute dialog modally
        dialog.exec()

        return dialog
