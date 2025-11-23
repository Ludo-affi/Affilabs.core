"""Simplified main launcher for AffiLabs.core with modern UI by Dr. Live.

This is a clean rewrite that:
1. Shows the window FIRST
2. Initializes hardware in background threads
3. Uses standard app.exec() instead of asyncio complexity
"""

import sys
import atexit
from pathlib import Path
import threading

# Add Old software to path
old_software = Path(__file__).parent
sys.path.insert(0, str(old_software))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from LL_UI_v1_0 import MainWindowPrototype
from core.hardware_manager import HardwareManager
from core.data_acquisition_manager import DataAcquisitionManager
from core.recording_manager import RecordingManager
from core.kinetic_manager import KineticManager
from core.data_buffer_manager import DataBufferManager
from utils.logger import logger
from utils.session_quality_monitor import SessionQualityMonitor
from utils.spr_signal_processing import calculate_transmission
from settings import SW_VERSION
from config import (
    LEAK_DETECTION_WINDOW, LEAK_THRESHOLD_RATIO, WAVELENGTH_TO_RU_CONVERSION,
    DEFAULT_FILTER_ENABLED, DEFAULT_FILTER_STRENGTH, DEFAULT_FILTER_METHOD,
    KALMAN_MEASUREMENT_NOISE, KALMAN_PROCESS_NOISE,
    OPTICS_LEAK_DETECTION_TIME, OPTICS_LEAK_THRESHOLD,
    OPTICS_MAX_DETECTOR_COUNTS, OPTICS_MAINTENANCE_INTENSITY_THRESHOLD
)

# Import TIME_ZONE from settings
try:
    from settings import TIME_ZONE
except ImportError:
    # Fallback if TIME_ZONE not available
    import datetime
    try:
        TIME_ZONE = datetime.datetime.now(datetime.UTC).astimezone().tzinfo
    except AttributeError:
        from datetime import timezone
        TIME_ZONE = datetime.datetime.now(timezone.utc).astimezone().tzinfo

import datetime as dt
import numpy as np


class Application(QApplication):
    """Main application class that coordinates UI and hardware."""

    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("AffiLabs.core")
        self.setOrganizationName("Affinite Instruments")

        # Closing flag for cleanup coordination
        self.closing = False

        # Apply theme
        self._apply_theme()

        # Create hardware manager (does NOT connect yet)
        logger.info("Creating hardware manager...")
        self.hardware_mgr = HardwareManager()

        # Create data acquisition manager
        logger.info("Creating data acquisition manager...")
        self.data_mgr = DataAcquisitionManager(self.hardware_mgr)

        # Create recording manager
        logger.info("Creating recording manager...")
        self.recording_mgr = RecordingManager(self.data_mgr)

        # Create kinetic operations manager
        logger.info("Creating kinetic operations manager...")
        self.kinetic_mgr = KineticManager(self.hardware_mgr)

        # Create session quality monitor for FWHM tracking
        logger.info("Creating session quality monitor...")
        self.quality_monitor = SessionQualityMonitor(
            device_serial="unknown",  # Will be updated when hardware connects
            session_id=None  # Auto-generated
        )

        # Create main window (using prototype UI)
        logger.info("Creating main window...")
        self.main_window = MainWindowPrototype()

        # Store reference to app in window for easy access to managers
        self.main_window.app = self

        # Track selected axis for manual/auto scaling (default X)
        self._selected_axis = 'x'

        # Track reference channel for subtraction (None, 'a', 'b', 'c', 'd')
        self._reference_channel = None

        # Track data filtering settings (use config defaults)
        self._filter_enabled = DEFAULT_FILTER_ENABLED
        self._filter_strength = DEFAULT_FILTER_STRENGTH
        self._filter_method = DEFAULT_FILTER_METHOD
        self._kalman_filters = {}  # Store Kalman filter instances per channel

        # Track selected channel for flagging (None, 0-3 for A-D)
        self._selected_channel = None
        self._flag_data = []  # List of {channel, time, annotation} dicts

        # Calibration progress dialog
        self._calibration_dialog = None

        # Initialize data buffer manager
        self.buffer_mgr = DataBufferManager()

        # Experiment start time
        self.experiment_start_time = None

        # Connect hardware manager signals to UI
        self._connect_signals()

        # Show window FIRST
        logger.info("🪟 Showing main window...")
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
        logger.info(f"✅ Window visible: {self.main_window.isVisible()}")

        # DO NOT auto-connect hardware - user must press Power button
        # This allows user to start in offline mode for post-processing
        logger.info("💡 Ready - waiting for user to press Power button to connect hardware...")

        # Connect cursor movements to update cycle graph
        self.main_window.full_timeline_graph.start_cursor.sigPositionChanged.connect(
            self._update_cycle_of_interest_graph
        )
        self.main_window.full_timeline_graph.stop_cursor.sigPositionChanged.connect(
            self._update_cycle_of_interest_graph
        )

        # Connect mouse events for channel selection and flagging
        self.main_window.cycle_of_interest_graph.scene().sigMouseClicked.connect(
            self._on_graph_clicked
        )

    def _apply_theme(self):
        """Apply modern UI theme."""
        try:
            from widgets.modern_theme import apply_modern_theme
            apply_modern_theme(self)
        except ImportError:
            pass  # Theme not available, use default styling

        # Register emergency cleanup handler for unexpected exits
        atexit.register(self._emergency_cleanup)

    def _connect_signals(self):
        """Connect hardware manager signals to UI updates."""
        # Hardware connection updates
        self.hardware_mgr.hardware_connected.connect(self._on_hardware_connected)
        self.hardware_mgr.hardware_disconnected.connect(self._on_hardware_disconnected)
        self.hardware_mgr.connection_progress.connect(self._on_connection_progress)
        self.hardware_mgr.error_occurred.connect(self._on_hardware_error)

        # Data acquisition signals
        self.data_mgr.spectrum_acquired.connect(self._on_spectrum_acquired)
        self.data_mgr.calibration_started.connect(self._on_calibration_started)
        self.data_mgr.calibration_complete.connect(self._on_calibration_complete)
        self.data_mgr.calibration_failed.connect(self._on_calibration_failed)
        self.data_mgr.calibration_progress.connect(self._on_calibration_progress)
        self.data_mgr.acquisition_error.connect(self._on_acquisition_error)

        # Recording signals
        self.recording_mgr.recording_started.connect(self._on_recording_started)
        self.recording_mgr.recording_stopped.connect(self._on_recording_stopped)
        self.recording_mgr.recording_error.connect(self._on_recording_error)
        self.recording_mgr.event_logged.connect(self._on_event_logged)

        # Kinetic operations signals
        self.kinetic_mgr.pump_initialized.connect(self._on_pump_initialized)
        self.kinetic_mgr.pump_error.connect(self._on_pump_error)
        self.kinetic_mgr.pump_state_changed.connect(self._on_pump_state_changed)
        self.kinetic_mgr.valve_switched.connect(self._on_valve_switched)

        # Graphic Control UI → Cycle of Interest Graph connections
        self.main_window.grid_check.toggled.connect(self._on_grid_toggled)
        self.main_window.auto_radio.toggled.connect(self._on_autoscale_toggled)
        self.main_window.manual_radio.toggled.connect(self._on_manual_scale_toggled)
        self.main_window.min_input.editingFinished.connect(self._on_manual_range_changed)
        self.main_window.max_input.editingFinished.connect(self._on_manual_range_changed)
        self.main_window.x_axis_btn.toggled.connect(self._on_axis_selected)
        self.main_window.y_axis_btn.toggled.connect(self._on_axis_selected)

        # Visual Accessibility UI → Color palette connection
        self.main_window.colorblind_check.toggled.connect(self._on_colorblind_toggled)

        # Reference channel selection
        self.main_window.ref_combo.currentTextChanged.connect(self._on_reference_changed)

        # Data filtering controls
        self.main_window.filter_enable.toggled.connect(self._on_filter_toggled)
        self.main_window.filter_slider.valueChanged.connect(self._on_filter_strength_changed)
        self.main_window.median_filter_radio.toggled.connect(self._on_filter_method_changed)
        self.main_window.kalman_filter_radio.toggled.connect(self._on_filter_method_changed)
        self.main_window.sg_filter_radio.toggled.connect(self._on_filter_method_changed)

        # Settings controls
        self.main_window.polarizer_toggle_btn.clicked.connect(self._on_polarizer_toggle)
        self.main_window.apply_settings_btn.clicked.connect(self._on_apply_settings)
        self.main_window.ru_btn.toggled.connect(self._on_unit_changed)
        self.main_window.nm_btn.toggled.connect(self._on_unit_changed)

        # Calibration buttons
        self.main_window.simple_led_calibration_btn.clicked.connect(self._on_simple_led_calibration)
        self.main_window.full_calibration_btn.clicked.connect(self._on_full_calibration)
        self.main_window.oem_led_calibration_btn.clicked.connect(self._on_oem_led_calibration)

        # Power button
        self.main_window.power_on_requested.connect(self._on_power_on_requested)
        self.main_window.power_off_requested.connect(self._on_power_off_requested)

        # Recording button
        self.main_window.recording_start_requested.connect(self._on_recording_start_requested)
        self.main_window.recording_stop_requested.connect(self._on_recording_stop_requested)

        # UI → Manager connections (prototype UI has different structure)
        # TODO: Wire up prototype UI controls to managers
        # Example: self.main_window.sidebar.some_button.clicked.connect(self._on_scan_requested)

    def _on_scan_requested(self):
        """User clicked Scan button in UI."""
        logger.info("User requested hardware scan")
        self.hardware_mgr.scan_and_connect()

    def _on_hardware_connected(self, status: dict):
        """Hardware connection completed and update Device Status UI."""
        logger.info(f"Hardware connected: {status}")

        # Reset scan button state in UI
        self.main_window._on_hardware_scan_complete()

        # Update power button to connected state
        self.main_window.set_power_state("connected")

        # Update last power-on timestamp in maintenance tracking
        self.main_window.update_last_power_on()

        # Update Device Status UI with hardware details
        self._update_device_status_ui(status)

        # Start calibration if controller and spectrometer are connected
        if status.get('ctrl_type') and status.get('spectrometer'):
            logger.info("🎯 Starting automatic calibration...")
            # Trigger calibration through data acquisition manager
            self.data_mgr.start_calibration()
        elif status.get('spectrometer'):
            logger.info("✅ Spectrometer detected - starting data acquisition without calibration...")
            self.data_mgr.start_acquisition()
        else:
            logger.warning("⚠️ No spectrometer detected - data acquisition not started")

    def _on_hardware_disconnected(self):
        """Hardware disconnected."""
        logger.info("Hardware disconnected")

        # Update power button to disconnected state
        self.main_window.set_power_state("disconnected")

    def _on_connection_progress(self, message: str):
        """Hardware connection progress update."""
        logger.info(f"Connection: {message}")

    def _on_hardware_error(self, error: str):
        """Hardware error occurred."""
        logger.error(f"Hardware error: {error}")
        from widgets.message import show_message
        show_message(error, "Hardware Error")

        # If error occurs during connection, reset power button
        if self.main_window.power_btn.property("powerState") == "searching":
            logger.info("Resetting power button state after connection error")
            self.main_window.set_power_state("disconnected")

    # === Data Acquisition Callbacks ===

    def _on_spectrum_acquired(self, data: dict):
        """New spectrum data acquired and update graphs."""
        import numpy as np

        channel = data['channel']  # 'a', 'b', 'c', 'd'
        wavelength = data['wavelength']  # nm
        intensity = data.get('intensity', 0)  # Raw intensity
        timestamp = data['timestamp']

        # Initialize experiment start time on first data point
        if self.experiment_start_time is None:
            self.experiment_start_time = timestamp

        # Calculate elapsed time
        elapsed_time = timestamp - self.experiment_start_time

        # === INTENSITY MONITORING FOR LEAK DETECTION ===
        # Buffer intensity data for sliding window
        self.buffer_mgr.append_intensity_point(channel, timestamp, intensity)

        # Feed intensity to hardware manager for optics leak detection
        # Only monitor if calibration has been performed
        if self.hardware_mgr._calibration_passed:
            self.hardware_mgr.update_led_intensity(channel, intensity, timestamp)

        # Remove data older than window
        cutoff_time = timestamp - LEAK_DETECTION_WINDOW
        self.buffer_mgr.trim_intensity_buffer(channel, cutoff_time)

        # Check for intensity leak
        time_span = self.buffer_mgr.get_intensity_timespan(channel)
        if time_span and time_span >= LEAK_DETECTION_WINDOW:
            # Get dark noise from data acquisition manager
            dark_noise = getattr(self.data_mgr, 'dark_noise', None)
            if dark_noise is not None:
                # Calculate average intensity over window
                avg_intensity = self.buffer_mgr.get_intensity_average(channel)

                # Check if intensity is too low (near dark noise)
                dark_threshold = np.mean(dark_noise) * LEAK_THRESHOLD_RATIO
                if avg_intensity < dark_threshold:
                    logger.warning(f"⚠️ Possible optical leak detected in channel {channel.upper()}: "
                                 f"avg intensity {avg_intensity:.0f} < threshold {dark_threshold:.0f}")

        # === TRANSMISSION SPECTRUM AND FWHM TRACKING ===
        # Calculate transmission if we have reference spectrum and full spectrum data
        if (hasattr(self.data_mgr, 'ref_spectrum') and self.data_mgr.ref_spectrum is not None and
            hasattr(self.data_mgr, 'wave_data') and self.data_mgr.wave_data is not None):
            try:
                # Get full spectrum data from acquisition
                spectrum_intensity = data.get('full_spectrum', None)

                if spectrum_intensity is not None and len(spectrum_intensity) > 0:
                    # Calculate transmission spectrum (in %)
                    transmission = calculate_transmission(spectrum_intensity, self.data_mgr.ref_spectrum)

                    # Update transmission plot
                    if self.main_window.live_data_enabled and hasattr(self.main_window, 'transmission_curves'):
                        channel_idx = {'a': 0, 'b': 1, 'c': 2, 'd': 3}[channel]
                        wavelengths = self.data_mgr.wave_data

                        # Update transmission curve for this channel
                        self.main_window.transmission_curves[channel_idx].setData(
                            wavelengths,
                            transmission
                        )

                        # Also update raw data plot
                        if hasattr(self.main_window, 'raw_data_curves'):
                            self.main_window.raw_data_curves[channel_idx].setData(
                                wavelengths,
                                spectrum_intensity
                            )

                    # Update quality monitor with transmission data for FWHM tracking
                    self.quality_monitor.update_channel_metrics(
                        channel,
                        transmission,
                        self.data_mgr.wave_data,
                        wavelength  # Peak wavelength from peak finding
                    )

                    # Get FWHM from quality monitor
                    metrics = self.quality_monitor.channel_data[channel]
                    if metrics.current_fwhm is not None:
                        # Update hardware manager with FWHM
                        self.hardware_mgr.update_fwhm_status(channel, metrics.current_fwhm)
            except Exception as e:
                logger.debug(f"Transmission/FWHM calculation error for channel {channel}: {e}")

        # Append to timeline data buffers
        self.buffer_mgr.append_timeline_point(channel, elapsed_time, wavelength)

        # Update full timeline graph (top graph) - only if live data is enabled
        if self.main_window.live_data_enabled:
            channel_idx = {'a': 0, 'b': 1, 'c': 2, 'd': 3}[channel]
            curve = self.main_window.full_timeline_graph.curves[channel_idx]

            # Apply smoothing if enabled
            display_wavelength = self.buffer_mgr.timeline_data[channel].wavelength
            if self._filter_enabled and len(display_wavelength) > 2:
                display_wavelength = self._apply_smoothing(
                    display_wavelength,
                    self._filter_strength,
                    self._filter_method
                )

            curve.setData(
                self.buffer_mgr.timeline_data[channel].time,
                display_wavelength
            )

            # Auto-follow latest data with stop cursor (like old software)
            # Only move cursor if not currently being dragged by user
            if (hasattr(self.main_window.full_timeline_graph, 'stop_cursor') and
                self.main_window.full_timeline_graph.stop_cursor is not None):
                stop_cursor = self.main_window.full_timeline_graph.stop_cursor

                # Check moving attribute exists (defensive against initialization timing)
                is_moving = getattr(stop_cursor, 'moving', False)

                if not is_moving:
                    # Move stop cursor to follow latest time point
                    stop_cursor.setValue(elapsed_time)
                    # Update label if it exists
                    if hasattr(stop_cursor, 'label') and stop_cursor.label:
                        stop_cursor.label.setFormat(f'Stop: {elapsed_time:.1f}s')

        # Record data point if recording is active
        if self.recording_mgr.is_recording:
            # Build data point with all channels (use latest value for each)
            data_point = {}
            for ch in ['a', 'b', 'c', 'd']:
                latest_value = self.buffer_mgr.get_latest_value(ch)
                data_point[f'channel_{ch}'] = latest_value if latest_value is not None else ''

            self.recording_mgr.record_data_point(data_point)

        # Update cycle of interest graph (bottom graph)
        self._update_cycle_of_interest_graph()

    def _update_cycle_of_interest_graph(self):
        """Update the cycle of interest graph based on cursor positions."""
        import numpy as np

        # Get cursor positions from full timeline graph
        start_time = self.main_window.full_timeline_graph.start_cursor.value()
        stop_time = self.main_window.full_timeline_graph.stop_cursor.value()

        # Extract data within cursor range for each channel
        for ch_letter, ch_idx in [('a', 0), ('b', 1), ('c', 2), ('d', 3)]:
            cycle_time, cycle_wavelength = self.buffer_mgr.extract_cycle_region(
                ch_letter, start_time, stop_time
            )

            if len(cycle_time) == 0:
                continue

            # Calculate Δ SPR (baseline is first point in cycle or calibrated baseline)
            baseline = self.buffer_mgr.baseline_wavelengths[ch_letter]
            if baseline is None:
                # Use first point in cycle as baseline
                baseline = cycle_wavelength[0] if len(cycle_wavelength) > 0 else 0

            # Convert wavelength shift to RU (Response Units)
            delta_spr = (cycle_wavelength - baseline) * WAVELENGTH_TO_RU_CONVERSION

            # Store in buffer manager
            self.buffer_mgr.update_cycle_data(ch_letter, cycle_time, cycle_wavelength, delta_spr)

        # Apply reference subtraction if enabled
        self._apply_reference_subtraction()

        # Update graph curves with potentially subtracted data
        for ch_letter, ch_idx in [('a', 0), ('b', 1), ('c', 2), ('d', 3)]:
            cycle_time = self.buffer_mgr.cycle_data[ch_letter].time
            delta_spr = self.buffer_mgr.cycle_data[ch_letter].spr

            if len(cycle_time) == 0:
                continue

            # Update cycle of interest graph
            curve = self.main_window.cycle_of_interest_graph.curves[ch_idx]
            curve.setData(cycle_time, delta_spr)

        # Update Δ SPR display with current values
        self._update_delta_display()

    def _update_delta_display(self):
        """Update the Δ SPR display label with values at Stop cursor position."""
        if self.main_window.cycle_of_interest_graph.delta_display is None:
            return

        import numpy as np

        # Get Stop cursor position from full timeline graph
        stop_time = self.main_window.full_timeline_graph.stop_cursor.value()

        # Get Δ SPR value at Stop cursor position for each channel
        delta_values = {}
        for ch in ['a', 'b', 'c', 'd']:
            time_data = self.buffer_mgr.cycle_data[ch].time
            spr_data = self.buffer_mgr.cycle_data[ch].spr

            if len(time_data) > 0 and len(spr_data) > 0:
                # Find the index closest to stop_time
                idx = np.argmin(np.abs(time_data - stop_time))
                delta_values[ch] = spr_data[idx]
            else:
                delta_values[ch] = 0.0

        # Update label
        self.main_window.cycle_of_interest_graph.delta_display.setText(
            f"Δ SPR: Ch A: {delta_values['a']:.1f} RU  |  Ch B: {delta_values['b']:.1f} RU  |  "
            f"Ch C: {delta_values['c']:.1f} RU  |  Ch D: {delta_values['d']:.1f} RU"
        )

    def _on_calibration_started(self):
        """Calibration routine started."""
        logger.info("Calibration started...")

        # Show calibration progress dialog
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar
        from PySide6.QtCore import Qt

        self._calibration_dialog = QDialog(self.main_window)
        self._calibration_dialog.setWindowTitle("Calibration in Progress")
        self._calibration_dialog.setModal(True)
        self._calibration_dialog.setMinimumWidth(400)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title label
        title_label = QLabel("Calibrating SPR System")
        title_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Status label
        self._calibration_status_label = QLabel("Initializing calibration...")
        self._calibration_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._calibration_status_label.setStyleSheet("font-size: 10pt; color: #86868B;")
        layout.addWidget(self._calibration_status_label)

        # Progress bar (indeterminate mode)
        self._calibration_progress_bar = QProgressBar()
        self._calibration_progress_bar.setMinimum(0)
        self._calibration_progress_bar.setMaximum(0)  # Indeterminate mode
        self._calibration_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #86868B;
                border-radius: 5px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #007AFF;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self._calibration_progress_bar)

        # Info label
        info_label = QLabel("Please wait while the system calibrates LEDs and measures dark noise.\nThis may take 30-60 seconds.")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("font-size: 9pt; color: #86868B;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self._calibration_dialog.setLayout(layout)
        self._calibration_dialog.show()

        logger.info("📊 Calibration progress dialog displayed")

    def _on_calibration_complete(self, calibration_data: dict):
        """Calibration completed successfully."""
        ch_error_list = calibration_data.get('ch_error_list', [])
        calibration_type = calibration_data.get('calibration_type', 'full')  # 'full', 'afterglow', 'led'

        logger.info(f"✅ Calibration complete ({calibration_type}): {calibration_data}")

        # Check if afterglow correction was loaded
        if hasattr(self.data_mgr, 'afterglow_enabled') and self.data_mgr.afterglow_enabled:
            logger.info("✅ Afterglow correction is ACTIVE")

        # Update hardware manager with calibration results for optics verification
        self.hardware_mgr.update_calibration_status(ch_error_list, calibration_type)

        # Check if maintenance is required (weak LED intensity)
        if len(ch_error_list) > 0:
            logger.warning(f"⚠️ Calibration completed with errors in channels: {ch_error_list}")

            # Check if this is due to weak intensity (maintenance required)
            maintenance_required = []
            for ch in ch_error_list:
                # If channel failed due to weak intensity, it needs LED PCB replacement
                # This is indicated by the hardware manager's maintenance tracking
                if ch in self.hardware_mgr._maintenance_required:
                    maintenance_required.append(ch)

            # Close calibration dialog FIRST before showing message
            self._close_calibration_dialog()

            # Show appropriate message to user
            from widgets.message import show_message
            ch_str = ", ".join([ch.upper() for ch in ch_error_list])

            if len(maintenance_required) > 0:
                maint_str = ", ".join([ch.upper() for ch in maintenance_required])
                show_message(
                    f"Calibration failed for channels: {ch_str}\n\n"
                    f"Channels {maint_str} show weak LED intensity and may require LED PCB replacement.\n"
                    f"This is a maintenance issue. Please contact technical support.",
                    "Maintenance Required"
                )
            else:
                show_message(
                    f"Calibration completed but the following channels failed: {ch_str}\n\n"
                    "The optics may require cleaning or adjustment. Some channels may not be functional.",
                    "Calibration Warning"
                )
        else:
            logger.info("✅ All channels calibrated successfully - optics ready")

            # Update dialog to show success message instead of closing immediately
            if self._calibration_dialog and hasattr(self, '_calibration_status_label'):
                # Update title and status
                self._calibration_dialog.setWindowTitle("✅ Calibration Complete")
                self._calibration_status_label.setText(
                    "All channels are ready!\n\n"
                    "The dialog will close automatically in 3 seconds."
                )
                
                # Stop the indeterminate progress bar
                if hasattr(self, '_calibration_progress_bar'):
                    self._calibration_progress_bar.setMaximum(100)
                    self._calibration_progress_bar.setValue(100)

                # Auto-close dialog after 3 seconds
                from PySide6.QtCore import QTimer
                QTimer.singleShot(3000, self._close_calibration_dialog)
                logger.info("📋 Calibration dialog will auto-close in 3 seconds")
            else:
                # Fallback if dialog doesn't exist
                self._close_calibration_dialog()

        # Auto-start data acquisition after successful calibration
        logger.info("🚀 Starting data acquisition after calibration...")
        self.data_mgr.start_acquisition()
    
    def _close_calibration_dialog(self):
        """Helper to close calibration dialog and clean up properly."""
        if self._calibration_dialog:
            try:
                self._calibration_dialog.close()
                self._calibration_dialog.deleteLater()
            except Exception as e:
                logger.debug(f"Error closing calibration dialog: {e}")
            finally:
                self._calibration_dialog = None
            logger.debug("Calibration dialog closed and cleaned up")

    def _on_calibration_failed(self, error: str):
        """Calibration failed."""
        logger.error(f"Calibration failed: {error}")

        # Close calibration dialog
        if self._calibration_dialog:
            self._calibration_dialog.reject()
            self._calibration_dialog = None

        from widgets.message import show_message
        show_message(error, "Calibration Error")

    def _on_calibration_progress(self, message: str):
        """Calibration progress update."""
        logger.info(f"Calibration: {message}")

        # Update calibration dialog status if it exists
        if self._calibration_dialog and hasattr(self, '_calibration_status_label'):
            self._calibration_status_label.setText(message)

    def _on_acquisition_error(self, error: str):
        """Data acquisition error."""
        logger.error(f"Acquisition error: {error}")

        # If error indicates hardware failure, stop acquisition and show warning
        if "Hardware communication lost" in error or "stopping acquisition" in error.lower():
            logger.warning("⚠️ Hardware error detected - stopping acquisition")

            # Update UI to show disconnected state
            self.main_window.set_power_state("error")

            # Show user-friendly message
            from widgets.message import show_message
            show_message(
                "Hardware communication lost. Please power off and reconnect the device.",
                "Hardware Error"
            )

    # === Recording Callbacks ===

    def _on_recording_started(self, filename: str):
        """Recording started."""
        logger.info(f"📝 Recording started: {filename}")

        # Start tracking LED operation hours
        self.main_window.start_led_operation_tracking()

        # Update UI recording indicator
        self.main_window.set_recording_state(True, filename)

    def _on_recording_stopped(self):
        """Recording stopped."""
        logger.info("📝 Recording stopped")

        # Stop tracking LED operation hours and save to config
        self.main_window.stop_led_operation_tracking()

        # Update UI recording indicator
        self.main_window.set_recording_state(False)

    def _on_recording_error(self, error: str):
        """Recording error occurred."""
        logger.error(f"Recording error: {error}")
        from widgets.message import show_message
        show_message(error, "Recording Error")

    def _on_event_logged(self, event: str):
        """Event logged to recording."""
        logger.info(f"Event: {event}")

    # === Kinetic Operations Callbacks ===

    def _on_pump_initialized(self):
        """Pump initialized successfully."""
        logger.info("✅ Pump initialized")
        # TODO: Enable pump controls in UI

    def _on_pump_error(self, error: str):
        """Pump error occurred."""
        logger.error(f"Pump error: {error}")
        from widgets.message import show_message
        show_message(error, "Pump Error")

    def _on_pump_state_changed(self, state: dict):
        """Pump state changed."""
        channel = state.get('channel')
        running = state.get('running')
        flow_rate = state.get('flow_rate')
        logger.info(f"Pump {channel}: {'running' if running else 'stopped'} @ {flow_rate} μL/min")
        # TODO: Update UI pump status

    def _on_valve_switched(self, valve_info: dict):
        """Valve position changed."""
        channel = valve_info.get('channel')
        position = valve_info.get('position')
        logger.info(f"Valve {channel} switched to {position}")
        # TODO: Update UI valve status

    def close(self):
        """Clean up resources on application close."""
        if self.closing:
            return True  # Already closing, prevent double cleanup

        self.closing = True
        logger.info("🔄 Closing application...")

        try:
            # Stop data acquisition
            if self.data_mgr:
                logger.info("Stopping data acquisition...")
                try:
                    self.data_mgr.stop_acquisition()
                except Exception as e:
                    logger.error(f"Error stopping data acquisition: {e}")

            # Stop recording
            if self.recording_mgr and self.recording_mgr.is_recording:
                logger.info("Stopping recording...")
                try:
                    self.recording_mgr.stop_recording()
                except Exception as e:
                    logger.error(f"Error stopping recording: {e}")

            # Stop all pumps
            if self.kinetic_mgr:
                logger.info("Stopping pumps...")
                try:
                    self.kinetic_mgr.stop_all_pumps()
                except Exception as e:
                    logger.error(f"Error stopping pumps: {e}")

            # Disconnect hardware gracefully
            if self.hardware_mgr:
                logger.info("Disconnecting hardware...")
                try:
                    # Close controller
                    if hasattr(self.hardware_mgr, 'controller') and self.hardware_mgr.controller:
                        try:
                            self.hardware_mgr.controller.stop()
                            self.hardware_mgr.controller.close()
                        except Exception as e:
                            logger.error(f"Error closing controller: {e}")

                    # Close spectrometer
                    if hasattr(self.hardware_mgr, 'spectrometer') and self.hardware_mgr.spectrometer:
                        try:
                            self.hardware_mgr.spectrometer.close()
                        except Exception as e:
                            logger.error(f"Error closing spectrometer: {e}")

                    # Close kinetics controller
                    if hasattr(self.kinetic_mgr, 'kinetics_controller') and self.kinetic_mgr.kinetics_controller:
                        try:
                            self.kinetic_mgr.kinetics_controller.close()
                        except Exception as e:
                            logger.error(f"Error closing kinetics: {e}")
                except Exception as e:
                    logger.error(f"Error during hardware disconnect: {e}")

            # Wait for threads to finish (with timeout)
            time.sleep(0.5)

            logger.info("✅ Application closed successfully")

        except Exception as e:
            logger.error(f"Error during application close: {e}")

        return super().close()

    def _emergency_cleanup(self):
        """Emergency cleanup for unexpected exits (called by atexit)."""
        if hasattr(self, 'closing') and self.closing:
            return  # Normal close already happened

        logger.warning("⚠️ Emergency cleanup triggered - forcing resource release")

        # Force close all hardware connections without waiting
        try:
            if hasattr(self, 'hardware_mgr') and self.hardware_mgr:
                # Close controller
                try:
                    if hasattr(self.hardware_mgr, 'controller') and self.hardware_mgr.controller:
                        self.hardware_mgr.controller.close()
                except Exception as e:
                    logger.error(f"Emergency cleanup - controller close failed: {e}")

                # Close spectrometer
                try:
                    if hasattr(self.hardware_mgr, 'spectrometer') and self.hardware_mgr.spectrometer:
                        self.hardware_mgr.spectrometer.close()
                except Exception as e:
                    logger.error(f"Emergency cleanup - spectrometer close failed: {e}")
        except Exception as e:
            logger.error(f"Emergency cleanup - hardware_mgr access failed: {e}")

        # Close kinetics
        try:
            if hasattr(self, 'kinetic_mgr') and self.kinetic_mgr:
                if hasattr(self.kinetic_mgr, 'kinetics_controller') and self.kinetic_mgr.kinetics_controller:
                    self.kinetic_mgr.kinetics_controller.close()
        except Exception as e:
            logger.error(f"Emergency cleanup - kinetics close failed: {e}")

        logger.info("✅ Emergency cleanup completed")

    def __del__(self):
        """Destructor to ensure resources are cleaned up."""
        try:
            if not hasattr(self, 'closing') or not self.closing:
                logger.warning("⚠️ __del__ called without proper close - forcing cleanup")
                self._emergency_cleanup()
        except Exception:
            pass  # Destructor should never raise

    # === Graphic Control Callbacks ===

    def _on_grid_toggled(self, checked: bool):
        """Grid checkbox toggled."""
        logger.info(f"Grid toggled: {checked}")
        self.main_window.cycle_of_interest_graph.showGrid(x=checked, y=checked)

    def _on_autoscale_toggled(self, checked: bool):
        """Autoscale radio button toggled."""
        if not checked:  # Radio button was unchecked (manual selected)
            return

        logger.info(f"Autoscale enabled for {self._selected_axis.upper()}-axis")

        # Enable autoscale for selected axis
        if self._selected_axis == 'x':
            self.main_window.cycle_of_interest_graph.enableAutoRange(axis='x')
        else:
            self.main_window.cycle_of_interest_graph.enableAutoRange(axis='y')

    def _on_manual_scale_toggled(self, checked: bool):
        """Manual radio button toggled."""
        if not checked:  # Radio button was unchecked (auto selected)
            return

        logger.info(f"Manual scale enabled for {self._selected_axis.upper()}-axis")

        # Disable autoscale and enable manual inputs
        self.main_window.min_input.setEnabled(True)
        self.main_window.max_input.setEnabled(True)

        # Apply current manual range values if any
        self._on_manual_range_changed()

    def _on_manual_range_changed(self):
        """Manual range input values changed."""
        # Only apply if manual mode is selected
        if not self.main_window.manual_radio.isChecked():
            return

        try:
            min_text = self.main_window.min_input.text()
            max_text = self.main_window.max_input.text()

            # Parse values
            if not min_text or not max_text:
                return  # Need both values

            min_val = float(min_text)
            max_val = float(max_text)

            if min_val >= max_val:
                logger.warning(f"Invalid range: min ({min_val}) >= max ({max_val})")
                return

            logger.info(f"Setting {self._selected_axis.upper()}-axis range: [{min_val}, {max_val}]")

            # Apply range to selected axis
            if self._selected_axis == 'x':
                self.main_window.cycle_of_interest_graph.setXRange(min_val, max_val, padding=0)
            else:
                self.main_window.cycle_of_interest_graph.setYRange(min_val, max_val, padding=0)

        except ValueError as e:
            logger.warning(f"Invalid manual range input: {e}")

    def _on_axis_selected(self, checked: bool):
        """Axis selector button toggled."""
        if not checked:  # Button was unchecked
            return

        # Determine which axis is now selected
        if self.main_window.x_axis_btn.isChecked():
            self._selected_axis = 'x'
            logger.info("X-axis selected for scaling controls")
        else:
            self._selected_axis = 'y'
            logger.info("Y-axis selected for scaling controls")

        # Re-apply current mode to new axis
        if self.main_window.auto_radio.isChecked():
            self._on_autoscale_toggled(True)
        else:
            self._on_manual_range_changed()

    def _on_filter_toggled(self, checked: bool):
        """Data filtering checkbox toggled."""
        self._filter_enabled = checked
        logger.info(f"Data filtering: {'enabled' if checked else 'disabled'}")

        # Redraw full timeline graph with/without filtering
        self._redraw_timeline_graph()

    def _on_filter_strength_changed(self, value: int):
        """Filter strength slider changed."""
        self._filter_strength = value
        logger.info(f"Filter strength set to: {value}")

        # Redraw if filtering is enabled
        if self._filter_enabled:
            self._redraw_timeline_graph()

    def _on_filter_method_changed(self, checked: bool):
        """Filter method radio button toggled."""
        if not checked:
            return

        if self.main_window.median_filter_radio.isChecked():
            self._filter_method = 'median'
            logger.info("Filter method: Filter 1 (Median)")
        elif self.main_window.kalman_filter_radio.isChecked():
            self._filter_method = 'kalman'
            logger.info("Filter method: Filter 2 (Kalman)")
            # Initialize Kalman filters for each channel
            self._init_kalman_filters()
        else:
            self._filter_method = 'savgol'
            logger.info("Filter method: Filter 3 (Savitzky-Golay)")

        # Redraw if filtering is enabled
        if self._filter_enabled:
            self._redraw_timeline_graph()

    def _init_kalman_filters(self):
        """Initialize Kalman filter instances for each channel."""
        import sys
        import os

        # Add utils to path
        utils_path = os.path.join(os.path.dirname(__file__), '..')
        if utils_path not in sys.path:
            sys.path.insert(0, utils_path)

        from utils.spr_data_processor import KalmanFilter

        # Map strength to Kalman noise parameters
        # Lower strength = more filtering (higher measurement noise, lower process noise)
        # Higher strength = less filtering (lower measurement noise, higher process noise)
        # Strength 1: R=0.5, Q=0.01 (heavy filtering)
        # Strength 5: R=0.1, Q=0.05 (moderate)
        # Strength 10: R=0.01, Q=0.1 (light filtering)
        measurement_noise = 0.5 / self._filter_strength  # Higher strength = trust data more
        process_noise = 0.01 * self._filter_strength  # Higher strength = allow more change

        self._kalman_filters = {}
        for ch in ['a', 'b', 'c', 'd']:
            self._kalman_filters[ch] = KalmanFilter(
                process_noise=process_noise,
                measurement_noise=measurement_noise
            )

        logger.info(f"Kalman filters initialized (R={measurement_noise:.3f}, Q={process_noise:.3f})")

    def _apply_smoothing(self, data, strength: int, method: str = 'median'):
        """Apply smoothing filter to data.

        Args:
            data: Input data array
            strength: Smoothing strength (1-10), maps to window size for median/SG or noise params for Kalman
            method: Filter method ('median', 'kalman', or 'savgol')

        Returns:
            Smoothed data array
        """
        import numpy as np

        if len(data) < 3:
            return data

        if method == 'kalman':
            # Use Kalman filter from backend
            import sys
            import os
            utils_path = os.path.join(os.path.dirname(__file__), '..')
            if utils_path not in sys.path:
                sys.path.insert(0, utils_path)

            from utils.spr_data_processor import KalmanFilter

            # Map strength to noise parameters (inverse relationship)
            measurement_noise = 0.5 / strength  # Higher strength = trust data more
            process_noise = 0.01 * strength  # Higher strength = allow more change

            kalman = KalmanFilter(
                process_noise=process_noise,
                measurement_noise=measurement_noise
            )
            return kalman.filter_array(data)

        elif method == 'savgol':
            # Use Savitzky-Golay filter
            from scipy.signal import savgol_filter

            # Map strength (1-10) to window size (5-25) - must be odd
            # SG filter requires window >= polyorder + 2
            window_size = 2 * strength + 3  # Creates odd window: 5, 7, 9, ..., 23
            window_size = min(window_size, len(data))  # Don't exceed data length

            # Ensure window is odd
            if window_size % 2 == 0:
                window_size -= 1

            # Minimum window for polyorder 2
            if window_size < 5:
                return data

            # Use polyorder 2 (quadratic) - good balance of smoothing and feature preservation
            polyorder = min(2, window_size - 1)

            try:
                smoothed = savgol_filter(data, window_size, polyorder, mode='nearest')
                return smoothed
            except Exception as e:
                logger.warning(f"Savitzky-Golay filter failed: {e}, using original data")
                return data

        else:  # median filter
            # Map strength (1-10) to window size (3-21)
            # Strength 1 = minimal smoothing (window 3) - matches old software MED_FILT_WIN = 3
            # Strength 10 = maximum smoothing (window 21)
            window_size = 2 * strength + 1  # Creates odd window: 3, 5, 7, ..., 21
            window_size = min(window_size, len(data))  # Don't exceed data length

            # Ensure window is odd
            if window_size % 2 == 0:
                window_size -= 1

            if window_size < 3:
                return data

            # Apply median filter (matches old software's update_filtered_lambda method)
            # This is the same vectorized approach used in main.py line 2128-2134
            half_win = window_size // 2
            smoothed = np.empty(len(data))

            for i in range(len(data)):
                start_idx = max(0, i - half_win)
                end_idx = min(len(data), i + half_win + 1)
                smoothed[i] = np.nanmedian(data[start_idx:end_idx])

            return smoothed

    def _redraw_timeline_graph(self):
        """Redraw the full timeline graph with current filter settings."""
        for ch_letter, ch_idx in [('a', 0), ('b', 1), ('c', 2), ('d', 3)]:
            time_data = self.buffer_mgr.timeline_data[ch_letter].time
            wavelength_data = self.buffer_mgr.timeline_data[ch_letter].wavelength

            if len(time_data) == 0:
                continue

            # Apply smoothing if enabled
            display_data = wavelength_data
            if self._filter_enabled:
                display_data = self._apply_smoothing(wavelength_data, self._filter_strength)

            # Update curve
            curve = self.main_window.full_timeline_graph.curves[ch_idx]
            curve.setData(time_data, display_data)

    def _on_reference_changed(self, text: str):
        """Reference channel selection changed."""
        import pyqtgraph as pg

        # Map selection to channel letter
        channel_map = {
            "None": None,
            "Channel A": 'a',
            "Channel B": 'b',
            "Channel C": 'c',
            "Channel D": 'd'
        }

        old_ref = self._reference_channel
        self._reference_channel = channel_map.get(text, None)

        if self._reference_channel:
            logger.info(f"Reference channel set to: {self._reference_channel.upper()}")
        else:
            logger.info("Reference channel disabled")

        # Reset old reference channel styling
        if old_ref is not None:
            ch_idx = {'a': 0, 'b': 1, 'c': 2, 'd': 3}[old_ref]
            self._reset_channel_style(ch_idx)

        # Apply new reference channel styling
        if self._reference_channel is not None:
            ch_idx = {'a': 0, 'b': 1, 'c': 2, 'd': 3}[self._reference_channel]
            # Purple color with transparency and dashed line
            self.main_window.cycle_of_interest_graph.curves[ch_idx].setPen(
                pg.mkPen(color=(153, 102, 255, 150), width=2, style=pg.QtCore.Qt.PenStyle.DashLine)
            )

        # Recompute cycle data with new reference
        self._update_cycle_of_interest_graph()

    def _apply_reference_subtraction(self):
        """Apply reference channel subtraction to all other channels."""
        if self._reference_channel is None:
            return

        import numpy as np

        ref_time = self.buffer_mgr.cycle_data[self._reference_channel].time
        ref_spr = self.buffer_mgr.cycle_data[self._reference_channel].spr

        if len(ref_time) == 0:
            return

        # Subtract reference from all other channels
        for ch in ['a', 'b', 'c', 'd']:
            if ch == self._reference_channel:
                continue  # Don't subtract reference from itself

            ch_time = self.buffer_mgr.cycle_data[ch].time
            ch_spr = self.buffer_mgr.cycle_data[ch].spr

            if len(ch_time) == 0:
                continue

            # Interpolate reference to match channel time points
            if len(ref_time) > 1:
                ref_interp = np.interp(ch_time, ref_time, ref_spr)
                # Update the cycle data with subtracted values
                subtracted_spr = ch_spr - ref_interp
                self.buffer_mgr.cycle_data[ch].spr = subtracted_spr

    def _reset_channel_style(self, ch_idx: int):
        """Reset channel curve to standard or colorblind style."""
        import pyqtgraph as pg
        import sys
        import os

        # Add settings to path if not already there
        settings_path = os.path.join(os.path.dirname(__file__), '..')
        if settings_path not in sys.path:
            sys.path.insert(0, settings_path)

        from settings import settings

        # Determine if colorblind mode is active
        if self.main_window.colorblind_check.isChecked():
            colors = settings.GRAPH_COLORS_COLORBLIND
            ch_letter = ['a', 'b', 'c', 'd'][ch_idx]
            rgb = colors[ch_letter]
            color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        else:
            # Standard colors
            color_list = ['#1D1D1F', '#FF3B30', '#007AFF', '#34C759']
            color = color_list[ch_idx]

        # Reset to solid line with full opacity
        self.main_window.cycle_of_interest_graph.curves[ch_idx].setPen(
            pg.mkPen(color=color, width=2)
        )

    def _on_graph_clicked(self, event):
        """Handle mouse clicks on cycle_of_interest_graph.

        Left click: Select channel closest to cursor
        Right click: Add flag/annotation at cursor position for selected channel
        """
        import pyqtgraph as pg
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QInputDialog

        # Get click position in data coordinates
        pos = event.scenePos()
        mouse_point = self.main_window.cycle_of_interest_graph.getPlotItem().vb.mapSceneToView(pos)
        click_time = mouse_point.x()
        click_value = mouse_point.y()

        if event.button() == Qt.MouseButton.LeftButton:
            # Left click: Select nearest channel
            self._select_nearest_channel(click_time, click_value)

        elif event.button() == Qt.MouseButton.RightButton:
            # Right click: Add flag for selected channel
            if self._selected_channel is None:
                logger.warning("No channel selected. Left-click a channel first to select it.")
                return

            # Prompt user for flag type
            flag_type, ok = QInputDialog.getItem(
                self.main_window,
                "Add Flag",
                f"Select flag type for Channel {chr(65 + self._selected_channel)} at {click_time:.2f}s:",
                ["Inject", "Wash", "Spike"],
                0,
                False
            )

            if ok:
                self._add_flag(self._selected_channel, click_time, flag_type)

    def _select_nearest_channel(self, click_time: float, click_value: float):
        """Select the channel whose curve is nearest to the click position."""
        import numpy as np

        # Find nearest channel by checking distance to each curve
        min_distance = float('inf')
        nearest_channel = None

        for ch_idx in range(4):
            curve = self.main_window.cycle_of_interest_graph.curves[ch_idx]
            if not curve.isVisible():
                continue

            x_data, y_data = curve.getData()
            if x_data is None or len(x_data) == 0:
                continue

            # Find point on curve closest to click_time
            idx = np.argmin(np.abs(x_data - click_time))
            curve_value = y_data[idx]

            # Calculate distance (normalized by axis ranges for fair comparison)
            distance = abs(curve_value - click_value)

            if distance < min_distance:
                min_distance = distance
                nearest_channel = ch_idx

        if nearest_channel is not None:
            # Update selection
            old_channel = self._selected_channel
            self._selected_channel = nearest_channel

            # Update visual feedback (make selected channel thicker)
            if old_channel is not None:
                old_curve = self.main_window.cycle_of_interest_graph.curves[old_channel]
                old_pen = old_curve.opts['pen']
                old_pen.setWidth(2)  # Normal width
                old_curve.setPen(old_pen)

            new_curve = self.main_window.cycle_of_interest_graph.curves[nearest_channel]
            new_pen = new_curve.opts['pen']
            new_pen.setWidth(4)  # Thicker for selected
            new_curve.setPen(new_pen)

            logger.info(f"Selected Channel {chr(65 + nearest_channel)}")

    def _add_flag(self, channel: int, time: float, annotation: str):
        """Add a flag marker to the graph and save to table."""
        import pyqtgraph as pg
        from PySide6.QtWidgets import QTableWidgetItem

        # Store flag data
        flag_entry = {
            'channel': channel,
            'time': time,
            'annotation': annotation
        }
        self._flag_data.append(flag_entry)

        # Get channel color
        curve = self.main_window.cycle_of_interest_graph.curves[channel]
        color = curve.opts['pen'].color()

        # Create flag marker (vertical line with symbol)
        flag_line = pg.InfiniteLine(
            pos=time,
            angle=90,
            pen=pg.mkPen(color=color, width=2, style=pg.QtCore.Qt.PenStyle.DashLine),
            movable=False
        )

        # Add flag symbol at top
        flag_symbol = pg.ScatterPlotItem(
            [time], [self.main_window.cycle_of_interest_graph.getPlotItem().viewRange()[1][1]],
            symbol='t',  # Triangle down (flag shape)
            size=15,
            brush=pg.mkBrush(color),
            pen=pg.mkPen(color=color, width=2)
        )

        # Add to graph
        self.main_window.cycle_of_interest_graph.addItem(flag_line)
        self.main_window.cycle_of_interest_graph.addItem(flag_symbol)

        # Store references
        self.main_window.cycle_of_interest_graph.flag_markers.append({
            'line': flag_line,
            'symbol': flag_symbol,
            'data': flag_entry
        })

        # Update cycle data table
        self._update_cycle_data_table()

        logger.info(f"Added flag for Channel {chr(65 + channel)} at {time:.2f}s: '{annotation}'")

    def _update_cycle_data_table(self):
        """Update the Flags column in cycle data table with flag information."""
        from PySide6.QtWidgets import QTableWidgetItem

        # Build flag summary string for each row (currently just showing all flags)
        # In a real implementation, this would map flags to specific cycles
        flag_summary = "\n".join([
            f"Ch {chr(65 + f['channel'])} @ {f['time']:.1f}s: {f['annotation']}"
            for f in self._flag_data
        ])

        # Update first row's Flags column with all flags
        # (In production, you'd map each flag to its corresponding cycle row)
        if self.main_window.cycle_data_table.rowCount() > 0:
            flags_item = QTableWidgetItem(flag_summary)
            self.main_window.cycle_data_table.setItem(0, 4, flags_item)

    def _on_polarizer_toggle(self):
        """Toggle between S and P polarizer positions."""
        if self.hardware_mgr and self.hardware_mgr.ctrl:
            # Determine current position and toggle
            current_pos = getattr(self.hardware_mgr, '_current_polarizer', 's')
            new_pos = 'p' if current_pos == 's' else 's'

            logger.info(f"Toggling polarizer from {current_pos.upper()} to {new_pos.upper()}")

            # Set polarizer position
            self.hardware_mgr.ctrl.set_mode(mode=new_pos)
            self.hardware_mgr._current_polarizer = new_pos

            logger.info(f"Polarizer set to {new_pos.upper()}")
        else:
            logger.warning("Hardware not connected - cannot toggle polarizer")

    def _on_apply_settings(self):
        """Apply polarizer positions and LED intensities, then flash to EEPROM."""
        try:
            # Get values from inputs
            s_pos = int(self.main_window.s_position_input.text() or "0")
            p_pos = int(self.main_window.p_position_input.text() or "0")
            led_a = int(self.main_window.channel_a_input.text() or "0")
            led_b = int(self.main_window.channel_b_input.text() or "0")
            led_c = int(self.main_window.channel_c_input.text() or "0")
            led_d = int(self.main_window.channel_d_input.text() or "0")

            # Validate ranges (0-255)
            if not all(0 <= val <= 255 for val in [s_pos, p_pos, led_a, led_b, led_c, led_d]):
                logger.error("All values must be between 0-255")
                return

            if self.hardware_mgr and self.hardware_mgr.ctrl:
                logger.info(f"Applying settings: S={s_pos}, P={p_pos}, LEDs=[{led_a},{led_b},{led_c},{led_d}]")

                # Set polarizer positions (using servo_set method)
                self.hardware_mgr.ctrl.servo_set(s=s_pos, p=p_pos)

                # Set LED intensities
                self.hardware_mgr.ctrl.set_intensity('a', led_a)
                self.hardware_mgr.ctrl.set_intensity('b', led_b)
                self.hardware_mgr.ctrl.set_intensity('c', led_c)
                self.hardware_mgr.ctrl.set_intensity('d', led_d)

                # Flash to EEPROM
                logger.info("💾 Flashing settings to EEPROM...")
                self.hardware_mgr.ctrl.flash()

                logger.info("✅ Settings applied and saved to EEPROM")
            else:
                logger.warning("Hardware not connected - cannot apply settings")

        except ValueError as e:
            logger.error(f"Invalid input values: {e}")
        except Exception as e:
            logger.error(f"Error applying settings: {e}")

    def _on_unit_changed(self, checked: bool):
        """Toggle between RU and nm units for display."""
        if not checked:
            return

        if self.main_window.ru_btn.isChecked():
            unit = 'RU'
        else:
            unit = 'nm'

        logger.info(f"Display unit changed to: {unit}")

        # Update graph labels
        if unit == 'RU':
            self.main_window.cycle_of_interest_graph.setLabel('left', 'Δ SPR (RU)', color='#86868B', size='11pt')
        else:
            self.main_window.cycle_of_interest_graph.setLabel('left', 'λ (nm)', color='#86868B', size='11pt')

        # TODO: Trigger data conversion and redraw
        # The conversion factor is approximately: 1 RU ≈ 0.1 nm
        # This should be implemented in the data processing pipeline

    def _on_colorblind_toggled(self, checked: bool):
        """Colorblind-friendly palette toggled."""
        import sys
        import os

        # Add settings to path if not already there
        settings_path = os.path.join(os.path.dirname(__file__), '..')
        if settings_path not in sys.path:
            sys.path.insert(0, settings_path)

        from settings import settings

        if checked:
            logger.info("Switching to colorblind-friendly palette (Okabe-Ito)")
            colors = settings.GRAPH_COLORS_COLORBLIND
            # Convert RGB tuples to hex colors
            color_list = [
                f"#{colors['a'][0]:02x}{colors['a'][1]:02x}{colors['a'][2]:02x}",  # Blue
                f"#{colors['b'][0]:02x}{colors['b'][1]:02x}{colors['b'][2]:02x}",  # Orange
                f"#{colors['c'][0]:02x}{colors['c'][1]:02x}{colors['c'][2]:02x}",  # Green
                f"#{colors['d'][0]:02x}{colors['d'][1]:02x}{colors['d'][2]:02x}",  # Magenta
            ]
        else:
            logger.info("Switching to standard palette")
            # Standard colors: Black, Red, Blue, Green
            color_list = ['#1D1D1F', '#FF3B30', '#007AFF', '#34C759']

        # Update all graph curves on both timeline and cycle graphs
        for i, color in enumerate(color_list):
            import pyqtgraph as pg
            # Update full timeline graph
            if i < len(self.main_window.full_timeline_graph.curves):
                self.main_window.full_timeline_graph.curves[i].setPen(
                    pg.mkPen(color=color, width=2)
                )
            # Update cycle of interest graph
            if i < len(self.main_window.cycle_of_interest_graph.curves):
                self.main_window.cycle_of_interest_graph.curves[i].setPen(
                    pg.mkPen(color=color, width=2)
                )

        logger.info("✅ Graph colors updated successfully")

    def _on_simple_led_calibration(self):
        """Start simple LED intensity calibration (no auto-align)."""
        logger.info("🔧 Starting Simple LED Calibration...")
        # This is the basic calibrate() function
        if hasattr(self.hardware_mgr, 'main_app') and self.hardware_mgr.main_app:
            # Disable auto-polarization for simple calibration
            self.hardware_mgr.main_app.auto_polarize = False
            self.hardware_mgr.main_app._c_stop.clear()
            self.hardware_mgr.main_app.calibration_thread = threading.Thread(
                target=self.hardware_mgr.main_app.calibrate
            )
            self.hardware_mgr.main_app.calibration_thread.start()
        else:
            logger.warning("Hardware not ready for calibration")

    def _on_full_calibration(self):
        """Start full calibration with auto-align and polarizer calibration."""
        logger.info("🔧 Starting Full Calibration (with auto-align)...")
        # This is calibrate() with auto_polarize enabled
        if hasattr(self.hardware_mgr, 'main_app') and self.hardware_mgr.main_app:
            # Enable auto-polarization for full calibration
            self.hardware_mgr.main_app.auto_polarize = True
            self.hardware_mgr.main_app._c_stop.clear()
            self.hardware_mgr.main_app.calibration_thread = threading.Thread(
                target=self.hardware_mgr.main_app.calibrate
            )
            self.hardware_mgr.main_app.calibration_thread.start()
        else:
            logger.warning("Hardware not ready for calibration")

    def _on_oem_led_calibration(self):
        """Start OEM LED calibration with full afterglow measurement."""
        logger.info("🔧 Starting OEM LED Calibration (with afterglow)...")
        # This runs full calibration + afterglow measurement
        if hasattr(self.hardware_mgr, 'main_app') and self.hardware_mgr.main_app:
            # Enable auto-polarization
            self.hardware_mgr.main_app.auto_polarize = True
            self.hardware_mgr.main_app._c_stop.clear()

            # Start calibration thread
            self.hardware_mgr.main_app.calibration_thread = threading.Thread(
                target=self.hardware_mgr.main_app.calibrate
            )
            self.hardware_mgr.main_app.calibration_thread.start()

            # After calibration completes, trigger afterglow measurement
            # The calibration already auto-triggers afterglow if needed,
            # but we can force it here for OEM calibration
            def wait_and_measure_afterglow():
                # Wait for calibration to complete
                self.hardware_mgr.main_app.calibration_thread.join()
                if self.hardware_mgr.main_app.calibrated:
                    logger.info("🔄 Starting afterglow measurement...")
                    self.hardware_mgr.main_app.measure_afterglow()

            threading.Thread(target=wait_and_measure_afterglow, daemon=True).start()
        else:
            logger.warning("Hardware not ready for calibration")

    def _on_power_on_requested(self):
        """User requested to power on (connect hardware)."""
        logger.info("🔌 Power ON requested - starting hardware connection...")

        # Set to searching state
        self.main_window.set_power_state("searching")

        # Start hardware scan and connection
        self.hardware_mgr.scan_and_connect()

    def _on_power_off_requested(self):
        """User requested to power off (disconnect hardware)."""
        logger.info("🔌 Power OFF requested - initiating graceful shutdown...")

        try:
            # Stop data acquisition first (prevents new data from coming in)
            if self.data_mgr:
                logger.info("⏸️  Stopping data acquisition...")
                try:
                    self.data_mgr.stop_acquisition()
                    logger.info("✅ Data acquisition stopped")
                except Exception as e:
                    logger.error(f"Error stopping data acquisition: {e}")

            # Stop recording if active (ensures data is saved)
            if self.recording_mgr and self.recording_mgr.is_recording:
                logger.info("💾 Stopping active recording...")
                try:
                    self.recording_mgr.stop_recording()
                    logger.info("✅ Recording stopped and saved")
                except Exception as e:
                    logger.error(f"Error stopping recording: {e}")

            # Disconnect all hardware (safe shutdown of devices)
            logger.info("🔌 Disconnecting hardware...")
            try:
                self.hardware_mgr.disconnect_all()
                logger.info("✅ Hardware disconnected safely")
            except Exception as e:
                logger.error(f"Error disconnecting hardware: {e}")

            # Update UI to disconnected state
            self.main_window.set_power_state("disconnected")

            logger.info("✅ Graceful shutdown complete - software ready for offline post-processing")

        except Exception as e:
            logger.error(f"Error during power off: {e}")
            # Still update UI even if errors occurred
            self.main_window.set_power_state("disconnected")
            from widgets.message import show_message
            show_message(f"Power off completed with errors: {e}", "Warning")

    def _on_recording_start_requested(self):
        """User requested to start recording."""
        logger.info("📝 Recording start requested...")

        # Show file dialog to select recording location
        from PySide6.QtWidgets import QFileDialog
        from pathlib import Path

        # Get default filename with timestamp
        import datetime as dt
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"AffiLabs_data_{timestamp}.csv"

        # Show save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Save Recording As",
            default_filename,
            "CSV Files (*.csv);;All Files (*.*)"
        )

        if file_path:
            # User selected a file - start recording
            logger.info(f"Starting recording to: {file_path}")
            self.recording_mgr.start_recording(file_path)

            # Populate export fields with recording information
            path_obj = Path(file_path)
            filename = path_obj.stem  # Name without extension
            directory = str(path_obj.parent)

            self.main_window.sidebar.export_filename_input.setText(filename)
            self.main_window.sidebar.export_dest_input.setText(directory)
            logger.info(f"✓ Export fields populated: {filename} in {directory}")
        else:
            # User cancelled - revert button state
            logger.info("Recording cancelled by user")
            self.main_window.record_btn.setChecked(False)

    def _on_recording_stop_requested(self):
        """User requested to stop recording."""
        logger.info("📝 Recording stop requested...")

        # Stop the recording
        self.recording_mgr.stop_recording()

    def _update_device_status_ui(self, status: dict):
        """Update Device Status UI with hardware information.

        Args:
            status: Hardware status dict from HardwareManager
        """
        logger.info("Updating Device Status UI...")

        # Forward status to main window for UI update
        self.main_window.update_hardware_status(status)

        # Log hardware summary
        logger.info(f"  Controller: {status.get('ctrl_type', 'None')}")
        logger.info(f"  Spectrometer: {'Connected' if status.get('spectrometer') else 'Not connected'}")
        logger.info(f"  Kinetic: {status.get('knx_type', 'None')}")
        logger.info(f"  Pump: {'Connected' if status.get('pump_connected') else 'Not connected'}")
        logger.info(f"  Sensor: {'Ready' if status.get('sensor_ready') else 'Not ready'}")
        logger.info(f"  Optics: {'Ready' if status.get('optics_ready') else 'Not ready'}")
        logger.info(f"  Fluidics: {'Ready' if status.get('fluidics_ready') else 'Not ready'}")


def main():
    """Launch the application with modern UI."""
    dtnow = dt.datetime.now(TIME_ZONE)
    logger.info("="*70)
    logger.info("AffiLabs.core - Surface Plasmon Resonance Analysis")
    logger.info(f"{SW_VERSION} | {dtnow.strftime('%Y-%m-%d %H:%M')}")
    logger.info("="*70)

    # Create and run application
    app = Application(sys.argv)

    logger.info("🚀 Starting event loop...")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
