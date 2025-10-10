"""Smart Processing Module - Automated SPR Time Series Analysis
============================================================

A standalone GUI for intelligent processing of SPR time series data with:
- Automatic cycle detection
- Smart concentration assignment
- One-click processing pipeline
- Direct export to kinetic analysis

Author: AI Assistant
Date: October 2025
"""

import csv
import os
from copy import deepcopy

import numpy as np
from pyqtgraph import LinearRegionItem, PlotWidget, mkPen
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from scipy.signal import find_peaks, savgol_filter

# Import existing utilities if available
try:
    from settings import CH_LIST, GRAPH_COLORS
    from utils.logger import logger
    from widgets.ka_kd_wizard import KAKDWizardDialog
    from widgets.message import show_message
except ImportError:
    # Fallback definitions for standalone operation
    CH_LIST = ["a", "b", "c", "d"]
    GRAPH_COLORS = {"a": "red", "b": "blue", "c": "green", "d": "orange"}

    class Logger:
        @staticmethod
        def debug(msg):
            print(f"DEBUG: {msg}")

        @staticmethod
        def info(msg):
            print(f"INFO: {msg}")

        @staticmethod
        def warning(msg):
            print(f"WARNING: {msg}")

        @staticmethod
        def error(msg):
            print(f"ERROR: {msg}")

    logger = Logger()

    def show_message(msg, msg_type="Info", yes_no=False):
        if yes_no:
            reply = QMessageBox.question(
                None, msg_type, msg, QMessageBox.Yes | QMessageBox.No
            )
            return reply == QMessageBox.Yes
        QMessageBox.information(None, msg_type, msg)


class CycleDetectionWorker(QThread):
    """Background worker for cycle detection processing."""

    progress_updated = Signal(int)
    cycle_detected = Signal(dict)
    error_occurred = Signal(str)
    finished = Signal()

    def __init__(self, time_data, signal_data, detection_params):
        super().__init__()
        self.time_data = time_data
        self.signal_data = signal_data
        self.detection_params = detection_params

    def run(self):
        """Run cycle detection in background thread."""
        try:
            print("DEBUG: CycleDetectionWorker started")
            self.progress_updated.emit(10)

            # Step 1: Preprocessing
            print("DEBUG: Starting preprocessing...")
            smoothed_data = self._preprocess_signal()
            print("DEBUG: Preprocessing completed")
            self.progress_updated.emit(30)

            # Step 2: Detect injection events
            print("DEBUG: Starting injection detection...")
            injection_points = self._detect_injections(smoothed_data)
            print(f"DEBUG: Injection detection completed: {injection_points}")
            self.progress_updated.emit(50)

            # Step 3: Segment cycles
            print("DEBUG: Starting cycle segmentation...")
            cycles = self._segment_cycles(injection_points)
            print("DEBUG: Cycle segmentation completed")
            self.progress_updated.emit(70)

            # Step 4: Classify phases
            print("DEBUG: Starting phase classification...")
            classified_cycles = self._classify_phases(cycles)
            print("DEBUG: Phase classification completed")
            self.progress_updated.emit(90)

            # Step 5: Assign concentrations
            print("DEBUG: Starting concentration assignment...")
            final_cycles = self._assign_concentrations(classified_cycles)
            print("DEBUG: Concentration assignment completed")
            self.progress_updated.emit(100)

            print("DEBUG: Emitting cycle_detected signal")
            self.cycle_detected.emit(final_cycles)
            self.finished.emit()

        except Exception as e:
            print(f"DEBUG: CycleDetectionWorker error: {e}")
            import traceback

            traceback.print_exc()
            self.error_occurred.emit(str(e))

    def _preprocess_signal(self):
        """Preprocess signal data for cycle detection."""
        smoothed = {}
        for ch in CH_LIST:
            if len(self.signal_data[ch]) > 0:
                # Apply Savitzky-Golay filter for smoothing
                window_length = min(51, len(self.signal_data[ch]) // 10)
                if window_length % 2 == 0:
                    window_length += 1
                if window_length >= 5:
                    smoothed[ch] = savgol_filter(self.signal_data[ch], window_length, 3)
                else:
                    smoothed[ch] = self.signal_data[ch]
            else:
                smoothed[ch] = np.array([])
        return smoothed

    def _detect_injections(self, smoothed_data):
        """Detect injection start points using derivative analysis."""
        injection_points = {}

        for ch in CH_LIST:
            if len(smoothed_data[ch]) == 0:
                injection_points[ch] = []
                continue

            # Calculate derivative
            derivative = np.gradient(smoothed_data[ch])

            # Find significant positive changes (injections)
            threshold = self.detection_params.get(
                "injection_threshold", np.std(derivative) * 2
            )

            # Find peaks in derivative
            peaks, properties = find_peaks(
                derivative,
                height=threshold,
                distance=self.detection_params.get("min_cycle_distance", 100),
            )

            injection_points[ch] = peaks.tolist()

        return injection_points

    def _segment_cycles(self, injection_points):
        """Segment data into individual cycles."""
        cycles = {}

        for ch in CH_LIST:
            cycles[ch] = []
            if len(injection_points[ch]) == 0:
                continue

            injections = injection_points[ch]

            for i, start_idx in enumerate(injections):
                # Determine cycle end
                if i + 1 < len(injections):
                    end_idx = injections[i + 1]
                else:
                    end_idx = len(self.time_data[ch]) - 1

                # Extract cycle data
                cycle_time = self.time_data[ch][start_idx:end_idx]
                cycle_signal = self.signal_data[ch][start_idx:end_idx]

                cycle = {
                    "start_idx": start_idx,
                    "end_idx": end_idx,
                    "time": cycle_time - cycle_time[0],  # Normalize to start at 0
                    "signal": cycle_signal - cycle_signal[0],  # Baseline correction
                    "raw_time": cycle_time,
                    "raw_signal": cycle_signal,
                }

                cycles[ch].append(cycle)

        return cycles

    def _classify_phases(self, cycles):
        """Classify association and dissociation phases within cycles."""
        classified_cycles = deepcopy(cycles)

        for ch in CH_LIST:
            for cycle in classified_cycles[ch]:
                if len(cycle["signal"]) == 0:
                    continue

                # Find association end (signal plateau)
                signal_data = cycle["signal"]
                derivative = np.gradient(signal_data)

                # Find where derivative becomes small (plateau region)
                plateau_threshold = np.std(derivative) * 0.5
                plateau_candidates = np.where(np.abs(derivative) < plateau_threshold)[0]

                if len(plateau_candidates) > 0:
                    # Association ends where plateau begins
                    assoc_end_idx = plateau_candidates[0]

                    # Look for dissociation start (negative derivative)
                    dissoc_candidates = np.where(derivative < -plateau_threshold)[0]
                    if len(dissoc_candidates) > 0:
                        dissoc_start_idx = dissoc_candidates[0]
                    else:
                        dissoc_start_idx = min(assoc_end_idx + 50, len(signal_data) - 1)
                else:
                    # Fallback: use time-based estimation
                    total_time = len(signal_data)
                    assoc_end_idx = int(total_time * 0.4)  # 40% for association
                    dissoc_start_idx = int(
                        total_time * 0.6
                    )  # 60% for dissociation start

                # Store phase information
                cycle["assoc_start"] = 0
                cycle["assoc_end"] = assoc_end_idx
                cycle["dissoc_start"] = dissoc_start_idx
                cycle["dissoc_end"] = len(signal_data) - 1

                # Extract phase data
                cycle["assoc_time"] = cycle["time"][:assoc_end_idx]
                cycle["assoc_signal"] = cycle["signal"][:assoc_end_idx]
                cycle["dissoc_time"] = (
                    cycle["time"][dissoc_start_idx:] - cycle["time"][dissoc_start_idx]
                )
                cycle["dissoc_signal"] = cycle["signal"][dissoc_start_idx:]

                # Calculate response shifts
                if len(cycle["assoc_signal"]) > 0:
                    cycle["assoc_shift"] = (
                        cycle["assoc_signal"][-1] - cycle["assoc_signal"][0]
                    )
                else:
                    cycle["assoc_shift"] = 0

                if len(cycle["dissoc_signal"]) > 0:
                    cycle["dissoc_shift"] = (
                        cycle["dissoc_signal"][-1] - cycle["dissoc_signal"][0]
                    )
                else:
                    cycle["dissoc_shift"] = 0

        return classified_cycles

    def _assign_concentrations(self, classified_cycles):
        """Automatically assign concentrations based on response patterns."""
        final_cycles = deepcopy(classified_cycles)

        # Analyze response magnitudes to infer concentration series
        for ch in CH_LIST:
            cycles = final_cycles[ch]
            if len(cycles) == 0:
                continue

            # Extract response magnitudes
            responses = [cycle["assoc_shift"] for cycle in cycles]

            if len(responses) == 0:
                continue

            # Detect concentration pattern
            pattern_type = self._detect_concentration_pattern(responses)

            # Assign concentrations based on pattern
            concentrations = self._generate_concentration_series(
                pattern_type, len(responses)
            )

            for i, cycle in enumerate(cycles):
                cycle["concentration"] = (
                    concentrations[i] if i < len(concentrations) else 0
                )
                cycle["concentration_nM"] = (
                    concentrations[i] if i < len(concentrations) else 0
                )

        return final_cycles

    def _detect_concentration_pattern(self, responses):
        """Detect the type of concentration series from response pattern."""
        if len(responses) <= 1:
            return "single"

        # Analyze response trend
        responses = np.array(responses)

        # Check for increasing pattern (common in concentration series)
        if np.corrcoef(range(len(responses)), responses)[0, 1] > 0.7:
            return "increasing"
        # Check for decreasing pattern
        if np.corrcoef(range(len(responses)), responses)[0, 1] < -0.7:
            return "decreasing"
        # Check for duplicate injections (same concentration)
        if len(set(np.round(responses, 1))) == 1:
            return "replicate"
        return "mixed"

    def _generate_concentration_series(self, pattern_type, num_cycles):
        """Generate concentration values based on detected pattern."""
        if pattern_type == "single" or num_cycles == 1:
            return [100.0]  # Default 100 nM
        if pattern_type == "increasing":
            # Common concentration series: 12.5, 25, 50, 100, 200 nM
            base_series = [12.5, 25, 50, 100, 200, 400, 800]
            return base_series[:num_cycles]
        if pattern_type == "decreasing":
            base_series = [800, 400, 200, 100, 50, 25, 12.5]
            return base_series[:num_cycles]
        if pattern_type == "replicate":
            return [100.0] * num_cycles  # Same concentration for all
        # mixed
        # Generate logarithmic series
        return [25 * (2**i) for i in range(num_cycles)]


class SmartProcessingDialog(QDialog):
    """Main Smart Processing GUI Dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Smart Processing - Automated SPR Analysis")
        self.setMinimumSize(1200, 800)

        # Data storage
        self.raw_data = {
            ch: {"time": np.array([]), "signal": np.array([])} for ch in CH_LIST
        }
        self.processed_cycles = {}
        self.detection_worker = None

        # Setup UI
        self._setup_ui()
        self._connect_signals()

        # Initialize detection parameters
        self.detection_params = {
            "injection_threshold": 2.0,
            "min_cycle_distance": 100,
            "baseline_window": 50,
            "smoothing_window": 51,
        }

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Title and description
        title = QLabel("Smart Processing - Automated SPR Time Series Analysis")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        description = QLabel(
            "Import SPR time series data and automatically detect cycles, "
            "assign concentrations, and prepare for kinetic analysis.",
        )
        description.setAlignment(Qt.AlignCenter)
        description.setWordWrap(True)
        layout.addWidget(description)

        # Main content area
        main_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(main_splitter)

        # Left panel - Controls
        left_panel = self._create_control_panel()
        main_splitter.addWidget(left_panel)

        # Right panel - Visualization
        right_panel = self._create_visualization_panel()
        main_splitter.addWidget(right_panel)

        # Set splitter proportions
        main_splitter.setSizes([400, 800])

        # Status bar
        self._create_status_bar(layout)

    def _create_control_panel(self):
        """Create the left control panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # File Import Section
        import_group = QGroupBox("1. Import Data")
        import_layout = QVBoxLayout(import_group)

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Select SPR time series file...")
        import_layout.addWidget(self.file_path_edit)

        file_buttons_layout = QHBoxLayout()
        self.browse_btn = QPushButton("Browse...")
        self.import_btn = QPushButton("Import Data")
        self.import_btn.setEnabled(False)
        file_buttons_layout.addWidget(self.browse_btn)
        file_buttons_layout.addWidget(self.import_btn)
        import_layout.addLayout(file_buttons_layout)

        # File format info
        format_info = QLabel(
            "Supported formats:\n"
            "• Tab-delimited (.txt, .csv)\n"
            "• Multi-channel: Time_A, Channel_A, Time_B, Channel_B...\n"
            "• Wavelength format: Ch A Time, Ch A Wavelength...\n"
            "• Single channel: Time, Response columns\n"
            "• Any SPR time series with 4 channels (A, B, C, D)",
        )
        format_info.setStyleSheet("color: gray; font-size: 10px;")
        import_layout.addWidget(format_info)

        layout.addWidget(import_group)

        # Detection Parameters Section
        params_group = QGroupBox("2. Detection Parameters")
        params_layout = QGridLayout(params_group)

        # Injection threshold
        params_layout.addWidget(QLabel("Injection Sensitivity:"), 0, 0)
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.1, 10.0)
        self.threshold_spin.setValue(2.0)
        self.threshold_spin.setDecimals(1)
        params_layout.addWidget(self.threshold_spin, 0, 1)

        # Minimum cycle distance
        params_layout.addWidget(QLabel("Min Cycle Distance:"), 1, 0)
        self.distance_spin = QSpinBox()
        self.distance_spin.setRange(10, 1000)
        self.distance_spin.setValue(100)
        params_layout.addWidget(self.distance_spin, 1, 1)

        # Smoothing window
        params_layout.addWidget(QLabel("Smoothing Window:"), 2, 0)
        self.smoothing_spin = QSpinBox()
        self.smoothing_spin.setRange(5, 201)
        self.smoothing_spin.setValue(51)
        self.smoothing_spin.setSingleStep(2)  # Keep odd numbers
        params_layout.addWidget(self.smoothing_spin, 2, 1)

        layout.addWidget(params_group)

        # Channel Selection Section
        channel_group = QGroupBox("3. Channel Display")
        channel_layout = QVBoxLayout(channel_group)

        # Channel visibility checkboxes
        channels_row = QHBoxLayout()
        self.channel_checkboxes = {}
        for ch in CH_LIST:
            checkbox = QCheckBox(f"Channel {ch.upper()}")
            checkbox.setChecked(True)
            checkbox.setStyleSheet(f"color: {GRAPH_COLORS[ch]};")
            checkbox.stateChanged.connect(self._update_channel_visibility)
            self.channel_checkboxes[ch] = checkbox
            channels_row.addWidget(checkbox)
        channel_layout.addLayout(channels_row)

        # Show/hide segments toggle
        segments_row = QHBoxLayout()
        self.show_segments_cb = QCheckBox("Show detected segments")
        self.show_segments_cb.setChecked(True)
        self.show_segments_cb.stateChanged.connect(self._update_segment_visibility)
        segments_row.addWidget(self.show_segments_cb)

        # Channel selection buttons
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all_channels)
        clear_all_btn = QPushButton("Clear All")
        clear_all_btn.clicked.connect(self._clear_all_channels)
        segments_row.addWidget(select_all_btn)
        segments_row.addWidget(clear_all_btn)

        channel_layout.addLayout(segments_row)
        layout.addWidget(channel_group)

        # Processing Section
        process_group = QGroupBox("4. Auto-Processing")
        process_layout = QVBoxLayout(process_group)

        self.process_btn = QPushButton("🚀 Start Smart Processing")
        self.process_btn.setEnabled(False)
        self.process_btn.setMinimumHeight(40)
        process_layout.addWidget(self.process_btn)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        process_layout.addWidget(self.progress_bar)

        # Processing options
        options_layout = QVBoxLayout()

        self.auto_concentration_cb = QCheckBox("Auto-assign concentrations")
        self.auto_concentration_cb.setChecked(True)
        options_layout.addWidget(self.auto_concentration_cb)

        self.baseline_correction_cb = QCheckBox("Apply baseline correction")
        self.baseline_correction_cb.setChecked(True)
        options_layout.addWidget(self.baseline_correction_cb)

        self.outlier_removal_cb = QCheckBox("Remove outlier cycles")
        self.outlier_removal_cb.setChecked(False)
        options_layout.addWidget(self.outlier_removal_cb)

        process_layout.addLayout(options_layout)
        layout.addWidget(process_group)

        # Results Section
        results_group = QGroupBox("5. Results & Export")
        results_layout = QVBoxLayout(results_group)

        self.results_label = QLabel("No cycles detected yet")
        self.results_label.setStyleSheet("font-weight: bold;")
        results_layout.addWidget(self.results_label)

        export_layout = QHBoxLayout()
        self.export_csv_btn = QPushButton("Export CSV")
        self.export_csv_btn.setEnabled(False)
        self.launch_kinetics_btn = QPushButton("Launch Kinetics")
        self.launch_kinetics_btn.setEnabled(False)
        export_layout.addWidget(self.export_csv_btn)
        export_layout.addWidget(self.launch_kinetics_btn)
        results_layout.addLayout(export_layout)

        layout.addWidget(results_group)

        # Add stretch to push everything to top
        layout.addStretch()

        return widget

    def _create_visualization_panel(self):
        """Create the right visualization panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Tab widget for different views
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Raw Data Tab
        self.raw_plot = PlotWidget(title="Raw Time Series Data")
        self.raw_plot.setLabel("left", "Response (RU)")
        self.raw_plot.setLabel("bottom", "Time (s)")
        self.raw_plot.showGrid(x=True, y=True)
        self.raw_plot.setBackground("white")
        self.tab_widget.addTab(self.raw_plot, "Raw Data")

        # Detected Cycles Tab
        self.cycles_plot = PlotWidget(title="Detected Cycles")
        self.cycles_plot.setLabel("left", "Response (RU)")
        self.cycles_plot.setLabel("bottom", "Time (s)")
        self.cycles_plot.showGrid(x=True, y=True)
        self.cycles_plot.setBackground("white")
        self.tab_widget.addTab(self.cycles_plot, "Detected Cycles")

        # Cycle Table Tab
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)

        self.cycle_table = QTableWidget()
        self.cycle_table.setColumnCount(7)
        self.cycle_table.setHorizontalHeaderLabels(
            [
                "Channel",
                "Cycle #",
                "Concentration (nM)",
                "Assoc. Shift",
                "Dissoc. Shift",
                "Duration (s)",
                "Quality",
            ]
        )
        self.cycle_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table_layout.addWidget(self.cycle_table)

        self.tab_widget.addTab(table_widget, "Cycle Table")

        return widget

    def _create_status_bar(self, layout):
        """Create status bar at bottom."""
        self.status_label = QLabel(
            "Ready - Import SPR data (supports wavelength/time format)"
        )
        self.status_label.setStyleSheet("border: 1px solid gray; padding: 5px;")
        layout.addWidget(self.status_label)

    def _connect_signals(self):
        """Connect all signal handlers."""
        self.browse_btn.clicked.connect(self._browse_file)
        self.import_btn.clicked.connect(self._import_data)
        self.process_btn.clicked.connect(self._start_processing)
        self.export_csv_btn.clicked.connect(self._export_csv)
        self.launch_kinetics_btn.clicked.connect(self._launch_kinetics)

        # Parameter changes
        self.threshold_spin.valueChanged.connect(self._update_detection_params)
        self.distance_spin.valueChanged.connect(self._update_detection_params)
        self.smoothing_spin.valueChanged.connect(self._update_detection_params)

    def _select_all_channels(self):
        """Select all channels for display."""
        for checkbox in self.channel_checkboxes.values():
            checkbox.setChecked(True)

    def _clear_all_channels(self):
        """Clear all channel selections."""
        for checkbox in self.channel_checkboxes.values():
            checkbox.setChecked(False)

    def _update_channel_visibility(self):
        """Update channel visibility based on checkboxes."""
        self._plot_raw_data()
        if hasattr(self, "detected_cycles") and self.detected_cycles:
            self._plot_cycles()

    def _update_segment_visibility(self):
        """Update segment visibility based on checkbox."""
        if hasattr(self, "detected_cycles") and self.detected_cycles:
            self._plot_cycles()

    def _browse_file(self):
        """Browse for input file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select SPR Time Series File",
            "",
            "Data Files (*.txt *.csv);;All Files (*)",
        )

        if file_path:
            self.file_path_edit.setText(file_path)
            self.import_btn.setEnabled(True)
            self._update_status("File selected - Click 'Import Data' to load")

    def _import_data(self):
        """Import and parse the selected data file."""
        file_path = self.file_path_edit.text()
        if not file_path or not os.path.exists(file_path):
            show_message("Please select a valid file", "Error")
            return

        try:
            self._update_status("Importing data...")
            print(f"DEBUG: Importing file: {file_path}")

            # Try different parsing methods
            success = False

            # Method 1: Standard multi-channel format
            print("DEBUG: Trying multi-channel parsing...")
            if self._try_parse_multichannel(file_path):
                print("DEBUG: Multi-channel parsing successful")
                success = True
            # Method 2: Single channel format
            elif self._try_parse_single_channel(file_path):
                print("DEBUG: Single-channel parsing successful")
                success = True
            else:
                print("DEBUG: All parsing methods failed")

            if success:
                print("DEBUG: Calling _plot_raw_data()")
                self._plot_raw_data()
                self.process_btn.setEnabled(True)
                self._update_status(
                    f"Data imported successfully - {self._get_data_summary()}"
                )

                # Auto-start processing after successful import
                print("DEBUG: Auto-starting Smart Processing...")
                self._start_processing()
            else:
                show_message("Could not parse file format", "Error")
                self._update_status("Import failed - Check file format")

        except Exception as e:
            print(f"DEBUG: Import exception: {e}")
            show_message(f"Import error: {e!s}", "Error")
            self._update_status("Import failed")

    def _try_parse_multichannel(self, file_path):
        """Try to parse multi-channel format using existing datawindow logic."""
        try:
            with open(file_path, encoding="utf-8") as file:
                # Try to detect delimiter
                sample = file.read(1024)
                file.seek(0)

                delimiter = "\t" if "\t" in sample else ","

                # Check for "All_Graph" format first
                if "All_Graph" in file_path:
                    return self._parse_all_graph_format(file, delimiter)

                # Try standard multi-channel format (Time_A, Channel_A, etc.)
                columns = [
                    "Time_A",
                    "Channel_A",
                    "Time_B",
                    "Channel_B",
                    "Time_C",
                    "Channel_C",
                    "Time_D",
                    "Channel_D",
                ]

                reader = csv.DictReader(file, dialect="excel-tab", fieldnames=columns)

                # Check if this format works by testing first few rows
                test_rows = []
                for i, row in enumerate(reader):
                    if i >= 3:  # Test first 3 rows
                        break
                    try:
                        # Try to parse as numbers
                        for col in columns:
                            if row[col]:  # If not empty
                                float(row[col])
                        test_rows.append(row)
                    except (ValueError, KeyError):
                        # This format doesn't work, try alternative
                        break

                if len(test_rows) >= 2:  # Successfully parsed test rows
                    # Reset file and parse full data
                    file.seek(0)
                    reader = csv.DictReader(
                        file, dialect="excel-tab", fieldnames=columns
                    )

                    temp_data = {col: [] for col in columns}

                    for row in reader:
                        for col in columns:
                            try:
                                value = float(row[col]) if row[col] else 0.0
                                temp_data[col].append(value)
                            except (ValueError, KeyError):
                                temp_data[col].append(0.0)

                    # Convert to expected format
                    channel_map = {"a": "A", "b": "B", "c": "C", "d": "D"}
                    for ch in CH_LIST:
                        ch_upper = channel_map[ch]
                        self.raw_data[ch]["time"] = np.array(
                            temp_data[f"Time_{ch_upper}"]
                        )
                        self.raw_data[ch]["signal"] = np.array(
                            temp_data[f"Channel_{ch_upper}"]
                        )

                    return True

                # If standard format failed, try header-based detection
                file.seek(0)
                return self._try_header_based_parsing(file, delimiter)

        except Exception as e:
            logger.error(f"Multi-channel parse error: {e}")
            return False

    def _parse_all_graph_format(self, file, delimiter):
        """Parse All_Graph format (interleaved channels)."""
        try:
            columns = ["GraphAll_x", "GraphAll_y"]
            reader = csv.DictReader(file, dialect="excel-tab", fieldnames=columns)

            temp_data_all = {
                "Time": {ch: [] for ch in CH_LIST},
                "Intensity": {ch: [] for ch in CH_LIST},
            }

            count = 0
            ch_list = ["d", "a", "b", "c"]  # Original order from datawindow
            skip_first = True

            for row in reader:
                if skip_first:
                    skip_first = False
                    continue

                try:
                    count += 1
                    ch = ch_list[(count - 1) % 4]

                    time_val = float(row["GraphAll_x"])
                    intensity_val = float(row["GraphAll_y"])

                    temp_data_all["Time"][ch].append(time_val)
                    temp_data_all["Intensity"][ch].append(intensity_val)

                except (ValueError, KeyError):
                    continue

            # Convert to numpy arrays
            for ch in CH_LIST:
                self.raw_data[ch]["time"] = np.array(temp_data_all["Time"][ch])
                self.raw_data[ch]["signal"] = np.array(temp_data_all["Intensity"][ch])

            return True

        except Exception as e:
            logger.error(f"All_Graph parse error: {e}")
            return False

    def _try_header_based_parsing(self, file, delimiter):
        """Try parsing based on actual column headers."""
        try:
            # Read header line
            first_line = file.readline().strip()
            if not first_line:
                return False

            # Split by delimiter to get potential headers
            headers = first_line.split("\t" if delimiter == "\t" else ",")
            headers = [h.strip() for h in headers]

            # Map headers to channels
            channel_mapping = {}

            # Look for various header patterns
            for i, header in enumerate(headers):
                header_lower = header.lower()

                # Time columns
                if "time" in header_lower:
                    for ch in CH_LIST:
                        ch_patterns = [
                            f"time_{ch}",
                            f"time {ch}",
                            f"{ch}_time",
                            f"{ch} time",
                            f"time_{ch.upper()}",
                            f"time {ch.upper()}",
                            f"{ch.upper()}_time",
                            f"{ch.upper()} time",
                        ]
                        if any(pattern in header_lower for pattern in ch_patterns):
                            if ch not in channel_mapping:
                                channel_mapping[ch] = {}
                            channel_mapping[ch]["time_idx"] = i
                            break

                # Signal/Wavelength columns
                signal_keywords = [
                    "channel",
                    "wavelength",
                    "lambda",
                    "signal",
                    "response",
                ]
                if any(keyword in header_lower for keyword in signal_keywords):
                    for ch in CH_LIST:
                        ch_patterns = [
                            f"channel_{ch}",
                            f"channel {ch}",
                            f"{ch}_channel",
                            f"{ch} channel",
                            f"wavelength_{ch}",
                            f"wavelength {ch}",
                            f"{ch}_wavelength",
                            f"{ch} wavelength",
                            f"ch {ch}",
                            f"ch{ch}",
                            f"{ch}",
                            f"channel_{ch.upper()}",
                            f"channel {ch.upper()}",
                            f"{ch.upper()}_channel",
                            f"{ch.upper()} channel",
                            f"wavelength_{ch.upper()}",
                            f"wavelength {ch.upper()}",
                            f"{ch.upper()}_wavelength",
                            f"{ch.upper()} wavelength",
                            f"ch {ch.upper()}",
                            f"ch{ch.upper()}",
                            f"{ch.upper()}",
                        ]
                        if any(pattern in header_lower for pattern in ch_patterns):
                            if ch not in channel_mapping:
                                channel_mapping[ch] = {}
                            channel_mapping[ch]["signal_idx"] = i
                            break

            # Verify we have at least some channel mappings
            valid_channels = [
                ch
                for ch in channel_mapping
                if "time_idx" in channel_mapping[ch]
                and "signal_idx" in channel_mapping[ch]
            ]

            if not valid_channels:
                return False

            # Parse data using the mapping
            file.seek(0)
            reader = csv.reader(file, delimiter=delimiter)
            next(reader)  # Skip header

            for ch in CH_LIST:
                self.raw_data[ch]["time"] = []
                self.raw_data[ch]["signal"] = []

            for row in reader:
                if len(row) < max(
                    max(mapping.values()) for mapping in channel_mapping.values()
                ):
                    continue

                for ch in valid_channels:
                    try:
                        time_val = float(row[channel_mapping[ch]["time_idx"]])
                        signal_val = float(row[channel_mapping[ch]["signal_idx"]])

                        self.raw_data[ch]["time"].append(time_val)
                        self.raw_data[ch]["signal"].append(signal_val)
                    except (ValueError, IndexError):
                        continue

            # Convert to numpy arrays
            for ch in valid_channels:
                self.raw_data[ch]["time"] = np.array(self.raw_data[ch]["time"])
                self.raw_data[ch]["signal"] = np.array(self.raw_data[ch]["signal"])

            return len(valid_channels) > 0

        except Exception as e:
            logger.error(f"Header-based parse error: {e}")
            return False

    def _try_parse_single_channel(self, file_path):
        """Try to parse single channel or multi-column wavelength format."""
        try:
            with open(file_path, encoding="utf-8") as file:
                lines = file.readlines()

            print(f"DEBUG: File has {len(lines)} lines")

            # Skip header if present and find data start
            data_lines = []
            header_line = None

            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue

                # Check if this looks like a header
                if (
                    line.startswith("#")
                    or "Time" in line
                    or "Channel" in line
                    or "Wavelength" in line
                ):
                    header_line = line
                    print(f"DEBUG: Found header: {header_line}")
                    continue

                # Try to parse as data
                try:
                    parts = line.replace(",", "\t").split("\t")
                    if len(parts) >= 2:
                        # Test if first few columns are numeric
                        for j in range(min(5, len(parts))):  # Test up to 5 columns
                            float(parts[j])
                        data_lines.append(parts)

                        # Show first few lines for debugging
                        if len(data_lines) <= 3:
                            print(
                                f"DEBUG: Data line {len(data_lines)}: {len(parts)} columns, first 5: {parts[:5]}"
                            )

                except ValueError:
                    continue

            if len(data_lines) < 10:  # Need minimum data
                print("DEBUG: Not enough valid data lines found")
                return False

            # Analyze column structure
            num_cols = len(data_lines[0])
            print(f"DEBUG: Data has {num_cols} columns")

            # Reset all channel data
            for ch in CH_LIST:
                self.raw_data[ch]["time"] = np.array([])
                self.raw_data[ch]["signal"] = np.array([])

            if num_cols >= 8:  # Interleaved time-value pairs format
                # Format: ChA_Time, ChA_Value, ChB_Time, ChB_Value, ChC_Time, ChC_Value, ChD_Time, ChD_Value
                print("DEBUG: Parsing as interleaved time-value pairs format")

                channels_data = {ch: {"time": [], "signal": []} for ch in CH_LIST}

                for parts in data_lines:
                    try:
                        # Parse each channel's time-value pair
                        for i, ch in enumerate(CH_LIST):
                            time_col = i * 2  # Column index for time (0, 2, 4, 6)
                            value_col = i * 2 + 1  # Column index for value (1, 3, 5, 7)

                            if time_col < len(parts) and value_col < len(parts):
                                time_val = float(parts[time_col])
                                signal_val = float(parts[value_col])

                                channels_data[ch]["time"].append(time_val)
                                channels_data[ch]["signal"].append(signal_val)

                    except (ValueError, IndexError):
                        continue

                # Store parsed data
                for ch in CH_LIST:
                    if len(channels_data[ch]["time"]) > 0:
                        self.raw_data[ch]["time"] = np.array(channels_data[ch]["time"])
                        self.raw_data[ch]["signal"] = np.array(
                            channels_data[ch]["signal"]
                        )
                        print(
                            f"DEBUG: Channel {ch}: {len(self.raw_data[ch]['time'])} points"
                        )

            elif num_cols >= 5:  # Simple multi-column format (fallback)
                # Assume format: Time, Ch_A_Wavelength, Ch_B_Wavelength, Ch_C_Wavelength, Ch_D_Wavelength
                print("DEBUG: Parsing as simple multi-channel wavelength format")

                times = []
                channels_data = {ch: [] for ch in CH_LIST}

                for parts in data_lines:
                    try:
                        time_val = float(parts[0])
                        times.append(time_val)

                        # Parse wavelength data for each channel (columns 1-4)
                        for i, ch in enumerate(CH_LIST):
                            if i + 1 < len(parts):
                                wavelength_val = float(parts[i + 1])
                                channels_data[ch].append(wavelength_val)
                            else:
                                channels_data[ch].append(0.0)  # Fill missing data

                    except (ValueError, IndexError):
                        continue

                # Store parsed data
                for ch in CH_LIST:
                    if len(channels_data[ch]) > 0:
                        self.raw_data[ch]["time"] = np.array(times)
                        self.raw_data[ch]["signal"] = np.array(channels_data[ch])
                        print(
                            f"DEBUG: Channel {ch}: {len(self.raw_data[ch]['time'])} points"
                        )

            else:  # Standard 2-column format
                print("DEBUG: Parsing as standard 2-column format")
                times = []
                signals = []

                for parts in data_lines:
                    times.append(float(parts[0]))
                    signals.append(float(parts[1]))

                # Store in channel A by default
                self.raw_data["a"]["time"] = np.array(times)
                self.raw_data["a"]["signal"] = np.array(signals)

            return True

        except Exception as e:
            print(f"DEBUG: Single-channel parse error: {e}")
            logger.error(f"Single-channel parse error: {e}")
            return False

    def _plot_raw_data(self):
        """Plot the imported raw data."""
        self.raw_plot.clear()

        # Debug: Check what data we have
        print("DEBUG: Plotting raw data...")
        for ch in CH_LIST:
            time_len = len(self.raw_data[ch]["time"])
            signal_len = len(self.raw_data[ch]["signal"])
            print(f"Channel {ch}: {time_len} time points, {signal_len} signal points")

            # Only plot if channel is selected and has data
            if (
                time_len > 0
                and signal_len > 0
                and hasattr(self, "channel_checkboxes")
                and self.channel_checkboxes[ch].isChecked()
            ):
                pen = mkPen(GRAPH_COLORS[ch], width=2)
                self.raw_plot.plot(
                    self.raw_data[ch]["time"],
                    self.raw_data[ch]["signal"],
                    pen=pen,
                    name=f"Channel {ch.upper()}",
                )

        # Force plot refresh
        self.raw_plot.autoRange()
        self.raw_plot.repaint()

    def _get_data_summary(self):
        """Get summary of imported data."""
        channels_with_data = [
            ch for ch in CH_LIST if len(self.raw_data[ch]["time"]) > 0
        ]
        total_points = sum(len(self.raw_data[ch]["time"]) for ch in channels_with_data)

        return f"{len(channels_with_data)} channels, {total_points} data points"

    def _update_detection_params(self):
        """Update detection parameters from UI."""
        self.detection_params = {
            "injection_threshold": self.threshold_spin.value(),
            "min_cycle_distance": self.distance_spin.value(),
            "baseline_window": 50,
            "smoothing_window": self.smoothing_spin.value(),
        }

    def _start_processing(self):
        """Start the automated processing."""
        if not any(len(self.raw_data[ch]["time"]) > 0 for ch in CH_LIST):
            show_message("No data to process", "Error")
            return

        self._update_status("Processing... Please wait")
        self.process_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Prepare data for worker
        time_data = {ch: self.raw_data[ch]["time"] for ch in CH_LIST}
        signal_data = {ch: self.raw_data[ch]["signal"] for ch in CH_LIST}

        # Start background processing
        self.detection_worker = CycleDetectionWorker(
            time_data, signal_data, self.detection_params
        )

        self.detection_worker.progress_updated.connect(self.progress_bar.setValue)
        self.detection_worker.cycle_detected.connect(self._on_cycles_detected)
        self.detection_worker.error_occurred.connect(self._on_processing_error)
        self.detection_worker.finished.connect(self._on_processing_finished)

        self.detection_worker.start()

    def _on_cycles_detected(self, cycles):
        """Handle successful cycle detection."""
        print(f"DEBUG: _on_cycles_detected called with {len(cycles)} channels")
        for ch, ch_cycles in cycles.items():
            print(f"DEBUG: Channel {ch}: {len(ch_cycles)} cycles detected")

        self.detected_cycles = cycles
        self._plot_cycles()
        self._populate_cycle_table()
        self._update_results_summary()

    def _on_processing_error(self, error_msg):
        """Handle processing error."""
        show_message(f"Processing error: {error_msg}", "Error")
        self._update_status("Processing failed")

    def _on_processing_finished(self):
        """Handle processing completion."""
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)

        if hasattr(self, "detected_cycles") and self.detected_cycles:
            self.export_csv_btn.setEnabled(True)
            self.launch_kinetics_btn.setEnabled(True)
            self._update_status("Processing completed successfully")
        else:
            self._update_status("No cycles detected - try adjusting parameters")

    def _plot_cycles(self):
        """Plot the detected cycles with optional segment overlay."""
        print("DEBUG: _plot_cycles called")
        self.cycles_plot.clear()

        # Plot raw data for selected channels
        for ch in CH_LIST:
            if (
                len(self.raw_data[ch]["time"]) > 0
                and hasattr(self, "channel_checkboxes")
                and self.channel_checkboxes[ch].isChecked()
            ):
                print(f"DEBUG: Plotting channel {ch} on cycles tab")
                pen = mkPen(
                    GRAPH_COLORS[ch], width=1, style=Qt.PenStyle.DashLine
                )  # Thinner, dashed for background
                self.cycles_plot.plot(
                    self.raw_data[ch]["time"],
                    self.raw_data[ch]["signal"],
                    pen=pen,
                    name=f"Channel {ch.upper()}",
                )

        # Overlay detected segments if enabled
        if (
            hasattr(self, "show_segments_cb")
            and self.show_segments_cb.isChecked()
            and hasattr(self, "detected_cycles")
            and self.detected_cycles
        ):
            print("DEBUG: Adding segment overlays")
            self._plot_segment_overlays()

        print("DEBUG: _plot_cycles completed")
        self.cycles_plot.autoRange()

    def _plot_segment_overlays(self):
        """Plot colored overlays for detected cycle segments."""
        if not hasattr(self, "detected_cycles") or not self.detected_cycles:
            print("DEBUG: No detected cycles to plot")
            return

        print("DEBUG: Starting segment overlay plotting...")

        # Define colors for different phases (more visible)
        phase_colors = {
            "association": (255, 100, 100, 80),  # Red with transparency
            "dissociation": (100, 100, 255, 80),  # Blue with transparency
            "baseline": (128, 128, 128, 80),  # Gray with transparency
        }

        overlay_count = 0

        for ch in CH_LIST:
            if ch not in self.detected_cycles:
                continue

            # Only show segments for visible channels
            if (
                hasattr(self, "channel_checkboxes")
                and not self.channel_checkboxes[ch].isChecked()
            ):
                continue

            print(f"DEBUG: Processing segments for channel {ch}")
            channel_cycles = self.detected_cycles[ch]
            print(f"DEBUG: Channel {ch} has {len(channel_cycles)} cycles")

            for cycle_idx, cycle in enumerate(channel_cycles):
                print(f"DEBUG: Processing cycle {cycle_idx + 1}")

                # For now, create simple time-based segments
                # Since we don't have phase data yet, create mock segments based on injection points
                if "raw_time" in cycle and len(cycle["raw_time"]) > 0:
                    start_time = cycle["raw_time"][0]
                    end_time = cycle["raw_time"][-1]
                    duration = end_time - start_time

                    # Create association phase (first 1/3)
                    assoc_start = start_time
                    assoc_end = start_time + duration * 0.33

                    # Create dissociation phase (last 2/3)
                    dissoc_start = assoc_end
                    dissoc_end = end_time

                    # Get signal range for this channel
                    signal_min = np.min(self.raw_data[ch]["signal"])
                    signal_max = np.max(self.raw_data[ch]["signal"])

                    # Association phase - red filled area using LinearRegionItem
                    try:
                        # Create association region
                        assoc_region = LinearRegionItem(
                            values=[assoc_start, assoc_end],
                            brush=phase_colors["association"],
                            pen=None,
                            movable=False,
                        )
                        self.cycles_plot.addItem(assoc_region)

                        # Create dissociation region
                        dissoc_region = LinearRegionItem(
                            values=[dissoc_start, dissoc_end],
                            brush=phase_colors["dissociation"],
                            pen=None,
                            movable=False,
                        )
                        self.cycles_plot.addItem(dissoc_region)

                        overlay_count += 2

                    except (ImportError, TypeError):
                        # Fallback to vertical lines if FillBetweenItem not available
                        pen_red = mkPen(color=(255, 0, 0), width=3)
                        pen_blue = mkPen(color=(0, 0, 255), width=3)

                        self.cycles_plot.plot(
                            [assoc_start, assoc_start],
                            [signal_min, signal_max],
                            pen=pen_red,
                            name=f"assoc_start_{cycle_idx}",
                        )
                        self.cycles_plot.plot(
                            [assoc_end, assoc_end],
                            [signal_min, signal_max],
                            pen=pen_red,
                            name=f"assoc_end_{cycle_idx}",
                        )

                        self.cycles_plot.plot(
                            [dissoc_start, dissoc_start],
                            [signal_min, signal_max],
                            pen=pen_blue,
                            name=f"dissoc_start_{cycle_idx}",
                        )
                        self.cycles_plot.plot(
                            [dissoc_end, dissoc_end],
                            [signal_min, signal_max],
                            pen=pen_blue,
                            name=f"dissoc_end_{cycle_idx}",
                        )

                        overlay_count += 4

                    # Add cycle label
                    mid_time = (start_time + end_time) / 2
                    label_y = signal_max - (signal_max - signal_min) * 0.1

                    # Use TextItem instead of addText
                    from pyqtgraph import TextItem

                    text_item = TextItem(
                        text=f"C{cycle_idx + 1}",
                        color=(0, 0, 0),
                        anchor=(0.5, 0.5),
                    )
                    text_item.setPos(mid_time, label_y)
                    self.cycles_plot.addItem(text_item)

        print(f"DEBUG: Segment overlay completed - added {overlay_count} markers")

        # Plot the cycles themselves with different colors
        colors = ["red", "blue", "green", "orange", "purple", "brown"]

        for ch in CH_LIST:
            if ch not in self.detected_cycles:
                continue

            cycles = self.detected_cycles[ch]
            for i, cycle in enumerate(cycles):
                if "raw_time" not in cycle or len(cycle["raw_time"]) == 0:
                    continue

                color = colors[i % len(colors)]
                pen = mkPen(color, width=2)

                # Plot full cycle
                self.cycles_plot.plot(
                    cycle["raw_time"],
                    cycle["raw_signal"],
                    pen=pen,
                    name=f"Ch {ch.upper()} - Cycle {i + 1} ({cycle.get('concentration', 0):.1f} nM)",
                )

    def _populate_cycle_table(self):
        """Populate the cycle results table."""
        print("DEBUG: _populate_cycle_table called")

        if not hasattr(self, "detected_cycles") or not self.detected_cycles:
            print("DEBUG: No detected cycles to populate table")
            return

        total_cycles = sum(len(self.detected_cycles.get(ch, [])) for ch in CH_LIST)
        print(f"DEBUG: Setting table row count to {total_cycles}")
        self.cycle_table.setRowCount(total_cycles)

        row = 0
        for ch in CH_LIST:
            if ch not in self.detected_cycles:
                continue

            cycles = self.detected_cycles[ch]
            print(f"DEBUG: Processing {len(cycles)} cycles for channel {ch}")

            for i, cycle in enumerate(cycles):
                print(f"DEBUG: Adding cycle {i + 1} to table row {row}")

                # Channel
                self.cycle_table.setItem(row, 0, QTableWidgetItem(ch.upper()))

                # Cycle number
                self.cycle_table.setItem(row, 1, QTableWidgetItem(str(i + 1)))

                # Concentration
                conc = cycle.get("concentration", 0)
                self.cycle_table.setItem(row, 2, QTableWidgetItem(f"{conc:.1f}"))

                # Association shift
                assoc_shift = cycle.get("assoc_shift", 0)
                self.cycle_table.setItem(row, 3, QTableWidgetItem(f"{assoc_shift:.2f}"))

                # Dissociation shift
                dissoc_shift = cycle.get("dissoc_shift", 0)
                self.cycle_table.setItem(
                    row, 4, QTableWidgetItem(f"{dissoc_shift:.2f}")
                )

                # Duration
                if "time" in cycle and len(cycle["time"]) > 0:
                    duration = cycle["time"][-1]
                else:
                    duration = 0
                self.cycle_table.setItem(row, 5, QTableWidgetItem(f"{duration:.1f}"))

                # Quality score (based on signal/noise ratio)
                quality = self._calculate_cycle_quality(cycle)
                self.cycle_table.setItem(row, 6, QTableWidgetItem(f"{quality:.2f}"))

                row += 1

        print(f"DEBUG: Table populated with {row} rows")

    def _calculate_cycle_quality(self, cycle):
        """Calculate a quality score for the cycle."""
        if len(cycle["signal"]) == 0:
            return 0.0

        # Simple quality metric based on signal-to-noise ratio
        signal_range = np.max(cycle["signal"]) - np.min(cycle["signal"])
        noise_estimate = (
            np.std(cycle["signal"][:10]) if len(cycle["signal"]) > 10 else 1.0
        )

        quality = signal_range / max(noise_estimate, 0.1)
        return min(quality / 10.0, 1.0)  # Normalize to 0-1

    def _update_results_summary(self):
        """Update the results summary label."""
        total_cycles = sum(len(self.processed_cycles.get(ch, [])) for ch in CH_LIST)
        channels_with_cycles = sum(
            1 for ch in CH_LIST if len(self.processed_cycles.get(ch, [])) > 0
        )

        self.results_label.setText(
            f"✅ Detected {total_cycles} cycles across {channels_with_cycles} channels",
        )

    def _export_csv(self):
        """Export detected cycles to CSV."""
        if not self.processed_cycles:
            show_message("No cycles to export", "Error")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Cycles Data",
            "detected_cycles.csv",
            "CSV Files (*.csv);;All Files (*)",
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)

                # Write header
                writer.writerow(
                    [
                        "Channel",
                        "Cycle",
                        "Concentration_nM",
                        "Start_Time",
                        "End_Time",
                        "Assoc_Shift",
                        "Dissoc_Shift",
                        "Duration",
                        "Quality",
                    ]
                )

                # Write data
                for ch in CH_LIST:
                    if ch not in self.processed_cycles:
                        continue

                    cycles = self.processed_cycles[ch]
                    for i, cycle in enumerate(cycles):
                        start_time = (
                            cycle["raw_time"][0] if len(cycle["raw_time"]) > 0 else 0
                        )
                        end_time = (
                            cycle["raw_time"][-1] if len(cycle["raw_time"]) > 0 else 0
                        )
                        duration = end_time - start_time

                        writer.writerow(
                            [
                                ch.upper(),
                                i + 1,
                                cycle.get("concentration", 0),
                                start_time,
                                end_time,
                                cycle.get("assoc_shift", 0),
                                cycle.get("dissoc_shift", 0),
                                duration,
                                self._calculate_cycle_quality(cycle),
                            ]
                        )

            show_message(f"Cycles exported to {file_path}")
            self._update_status(f"Exported to {os.path.basename(file_path)}")

        except Exception as e:
            show_message(f"Export error: {e!s}", "Error")

    def _launch_kinetics(self):
        """Launch kinetic analysis with detected cycles."""
        if not self.processed_cycles:
            show_message("No cycles to analyze", "Error")
            return

        try:
            # Convert processed cycles to format expected by KA/KD wizard
            segments = self._convert_cycles_to_segments()

            if len(segments) == 0:
                show_message("No valid segments for kinetic analysis", "Error")
                return

            # Try to launch the KA/KD wizard
            try:
                wizard = KAKDWizardDialog(self, segments, "RU")
                wizard.exec()
            except NameError:
                # Fallback if KA/KD wizard not available
                show_message(
                    "KA/KD Wizard not available in standalone mode.\n"
                    "Export data and import into main application for kinetic analysis.",
                    "Info",
                )

        except Exception as e:
            show_message(f"Error launching kinetics: {e!s}", "Error")

    def _convert_cycles_to_segments(self):
        """Convert detected cycles to segment format for kinetic analysis."""
        segments = []

        for ch in CH_LIST:
            if ch not in self.processed_cycles:
                continue

            cycles = self.processed_cycles[ch]
            for i, cycle in enumerate(cycles):
                if len(cycle["time"]) == 0:
                    continue

                # Create mock segment object
                class MockSegment:
                    def __init__(self, cycle_data, channel, cycle_num):
                        self.name = f"Cycle_{cycle_num}"
                        self.conc = {
                            ch: cycle_data.get("concentration", 0) for ch in CH_LIST
                        }
                        self.conc[channel] = cycle_data.get("concentration", 0)

                        # Initialize all channels
                        self.seg_x = {ch: np.array([]) for ch in CH_LIST}
                        self.seg_y = {ch: np.array([]) for ch in CH_LIST}
                        self.d_seg_x = {ch: np.array([]) for ch in CH_LIST}
                        self.d_seg_y = {ch: np.array([]) for ch in CH_LIST}
                        self.assoc_shift = dict.fromkeys(CH_LIST, 0)
                        self.dissoc_shift = dict.fromkeys(CH_LIST, 0)

                        # Set data for this channel
                        self.seg_x[channel] = cycle_data["assoc_time"]
                        self.seg_y[channel] = cycle_data["assoc_signal"]
                        self.d_seg_x[channel] = cycle_data["dissoc_time"]
                        self.d_seg_y[channel] = cycle_data["dissoc_signal"]
                        self.assoc_shift[channel] = cycle_data.get("assoc_shift", 0)
                        self.dissoc_shift[channel] = cycle_data.get("dissoc_shift", 0)

                segment = MockSegment(cycle, ch, i + 1)
                segments.append(segment)

        return segments

    def _update_status(self, message):
        """Update status bar message."""
        self.status_label.setText(message)


def main():
    """Main function to run Smart Processing as standalone application."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    # Set application properties
    app.setApplicationName("Smart Processing")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("SPR Analysis Tools")

    # Create and show dialog
    dialog = SmartProcessingDialog()
    dialog.show()

    return app.exec()


if __name__ == "__main__":
    main()
