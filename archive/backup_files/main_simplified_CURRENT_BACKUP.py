"""Simplified main launcher for AffiLabs.core with modern UI by Dr. Live.

This is a clean rewrite that:
1. Shows the window FIRST
2. Initializes hardware in background threads
3. Uses standard app.exec() instead of asyncio complexity
"""

import atexit
import sys
import threading
from pathlib import Path

from core.data_acquisition_manager import DataAcquisitionManager
from core.data_buffer_manager import DataBufferManager
from core.hardware_manager import HardwareManager
from core.kinetic_manager import KineticManager
from core.recording_manager import RecordingManager
from LL_UI_v1_0 import MainWindowPrototype
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from config import (
    DEFAULT_FILTER_ENABLED,
    DEFAULT_FILTER_STRENGTH,
    LEAK_DETECTION_WINDOW,
    LEAK_THRESHOLD_RATIO,
    WAVELENGTH_TO_RU_CONVERSION,
)
from settings import PROFILING_ENABLED, PROFILING_REPORT_INTERVAL, SW_VERSION
from utils.logger import logger
from utils.performance_profiler import get_profiler, measure
from utils.session_quality_monitor import SessionQualityMonitor
from utils.spr_signal_processing import calculate_transmission

# Import TIME_ZONE from settings
try:
    from settings import TIME_ZONE
except ImportError:
    # Fallback if TIME_ZONE not available
    import datetime

    try:
        TIME_ZONE = datetime.datetime.now(datetime.UTC).astimezone().tzinfo
    except AttributeError:
        TIME_ZONE = datetime.datetime.now(datetime.UTC).astimezone().tzinfo

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
            session_id=None,  # Auto-generated
        )

        # Create main window (using prototype UI)
        logger.info("Creating main window...")
        self.main_window = MainWindowPrototype()

        # Store reference to app in window for easy access to managers
        self.main_window.app = self

        # Track selected axis for manual/auto scaling (default X)
        self._selected_axis = "x"

        # Track reference channel for subtraction (None, 'a', 'b', 'c', 'd')
        self._reference_channel = None

        # Track data filtering settings (use config defaults)
        self._filter_enabled = DEFAULT_FILTER_ENABLED
        self._filter_strength = DEFAULT_FILTER_STRENGTH
        # Uses adaptive online filtering automatically (no method selection needed)

        # Track selected channel for flagging (None, 0-3 for A-D)
        self._selected_channel = None
        self._flag_data = []  # List of {channel, time, annotation} dicts

        # Calibration progress dialog
        self._calibration_dialog = None
        self._calibration_retry_count = 0
        self._max_calibration_retries = 3
        self._calibration_completed = (
            False  # Track if calibration has completed to prevent re-triggering
        )
        self._initial_connection_done = (
            False  # Track if initial hardware connection completed
        )

        # Initialize data buffer manager
        self.buffer_mgr = DataBufferManager()

        # Experiment start time
        self.experiment_start_time = None

        # Cycle tracking for autosave
        self._last_cycle_bounds = None  # (start_time, stop_time)
        self._session_cycles_dir = None  # Set when recording starts

        # Pre-computed channel mappings (performance optimization)
        self._channel_to_idx = {"a": 0, "b": 1, "c": 2, "d": 3}
        self._idx_to_channel = ["a", "b", "c", "d"]
        self._channel_pairs = [("a", 0), ("b", 1), ("c", 2), ("d", 3)]

        # === PHASE 3: ACQUISITION/PROCESSING THREAD SEPARATION ===
        # Lock-free queue for spectrum data (acquisition → processing)
        from queue import Queue

        self._spectrum_queue = Queue(maxsize=200)  # Buffer ~5 seconds at 40 Hz
        self._processing_thread = None
        self._processing_active = False
        self._queue_stats = {
            "dropped": 0,
            "processed": 0,
            "max_size": 0,
        }  # Performance monitoring

        # Pre-cache attribute checks for performance (called frequently)
        self._has_stop_cursor = (
            hasattr(self.main_window.full_timeline_graph, "stop_cursor")
            and self.main_window.full_timeline_graph.stop_cursor is not None
        )

        # Start processing thread
        self._start_processing_thread()

        # UI update throttling - prevent excessive graph redraws
        self._ui_update_timer = QTimer()
        self._ui_update_timer.timeout.connect(self._process_pending_ui_updates)
        self._ui_update_timer.setInterval(
            100,
        )  # 100ms = 10 FPS (smooth but not excessive)
        self._pending_graph_updates = {
            "a": None,
            "b": None,
            "c": None,
            "d": None,
        }  # Store latest data per channel
        self._pending_transmission_updates = {
            "a": None,
            "b": None,
            "c": None,
            "d": None,
        }  # Batch transmission updates
        self._skip_graph_updates = (
            False  # Skip updates during tab transitions to prevent freezing
        )
        self._ui_update_timer.start()

        # Performance profiling setup
        self.profiler = get_profiler()
        if PROFILING_ENABLED and PROFILING_REPORT_INTERVAL > 0:
            self._profiling_timer = QTimer()
            self._profiling_timer.timeout.connect(self._print_profiling_stats)
            self._profiling_timer.setInterval(
                PROFILING_REPORT_INTERVAL * 1000,
            )  # Convert to ms
            self._profiling_timer.start()
            logger.info(
                f"⏱️ Profiling enabled - stats will print every {PROFILING_REPORT_INTERVAL}s",
            )

        # Connect hardware manager signals to UI
        self._connect_signals()

        # Connect tab change signals to prevent UI freezing during transitions
        if hasattr(self.main_window, "tab_widget"):
            self.main_window.tab_widget.currentChanged.connect(self._on_tab_changing)
        if hasattr(self.main_window, "sidebar") and hasattr(
            self.main_window.sidebar,
            "tabs",
        ):
            self.main_window.sidebar.tabs.currentChanged.connect(self._on_tab_changing)

        # Show window FIRST
        logger.info("🪟 Showing main window...")
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
        logger.info(f"✅ Window visible: {self.main_window.isVisible()}")

        # DO NOT auto-connect hardware - user must press Power button
        # This allows user to start in offline mode for post-processing
        logger.info(
            "💡 Ready - waiting for user to press Power button to connect hardware...",
        )

        # Connect cursor movements to update cycle graph
        self.main_window.full_timeline_graph.start_cursor.sigPositionChanged.connect(
            self._update_cycle_of_interest_graph,
        )
        self.main_window.full_timeline_graph.stop_cursor.sigPositionChanged.connect(
            self._update_cycle_of_interest_graph,
        )

        # Connect mouse events for channel selection and flagging
        self.main_window.cycle_of_interest_graph.scene().sigMouseClicked.connect(
            self._on_graph_clicked,
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
        self.data_mgr.acquisition_started.connect(self._on_acquisition_started)
        self.data_mgr.acquisition_stopped.connect(self._on_acquisition_stopped)

        # Recording signals
        self.recording_mgr.recording_started.connect(self._on_recording_started)
        self.recording_mgr.recording_stopped.connect(self._on_recording_stopped)
        self.recording_mgr.recording_error.connect(self._on_recording_error)
        self.recording_mgr.event_logged.connect(self._on_event_logged)

        # Acquisition pause/resume signal
        self.main_window.acquisition_pause_requested.connect(
            self._on_acquisition_pause_requested,
        )

        # Kinetic operations signals
        self.kinetic_mgr.pump_initialized.connect(self._on_pump_initialized)
        self.kinetic_mgr.pump_error.connect(self._on_pump_error)
        self.kinetic_mgr.pump_state_changed.connect(self._on_pump_state_changed)
        self.kinetic_mgr.valve_switched.connect(self._on_valve_switched)

        # Graphic Control UI → Cycle of Interest Graph connections
        self.main_window.grid_check.toggled.connect(self._on_grid_toggled)
        self.main_window.auto_radio.toggled.connect(self._on_autoscale_toggled)
        self.main_window.manual_radio.toggled.connect(self._on_manual_scale_toggled)
        self.main_window.min_input.editingFinished.connect(
            self._on_manual_range_changed,
        )
        self.main_window.max_input.editingFinished.connect(
            self._on_manual_range_changed,
        )
        self.main_window.x_axis_btn.toggled.connect(self._on_axis_selected)
        self.main_window.y_axis_btn.toggled.connect(self._on_axis_selected)

        # Visual Accessibility UI → Color palette connection
        self.main_window.colorblind_check.toggled.connect(self._on_colorblind_toggled)

        # Quick Export buttons in Graphic Control
        self.main_window.quick_export_csv_btn.clicked.connect(self._on_quick_export_csv)
        self.main_window.quick_export_image_btn.clicked.connect(
            self._on_quick_export_image,
        )

        # Reference channel selection
        self.main_window.ref_combo.currentTextChanged.connect(
            self._on_reference_changed,
        )

        # Data filtering controls
        self.main_window.filter_enable.toggled.connect(self._on_filter_toggled)
        self.main_window.filter_slider.valueChanged.connect(
            self._on_filter_strength_changed,
        )
        # Filter method selection removed - uses adaptive online filtering automatically

        # Settings controls
        self.main_window.polarizer_toggle_btn.clicked.connect(self._on_polarizer_toggle)
        self.main_window.apply_settings_btn.clicked.connect(self._on_apply_settings)
        self.main_window.ru_btn.toggled.connect(self._on_unit_changed)
        self.main_window.nm_btn.toggled.connect(self._on_unit_changed)

        # Calibration buttons
        self.main_window.simple_led_calibration_btn.clicked.connect(
            self._on_simple_led_calibration,
        )
        self.main_window.full_calibration_btn.clicked.connect(self._on_full_calibration)
        self.main_window.oem_led_calibration_btn.clicked.connect(
            self._on_oem_led_calibration,
        )

        # Power button
        self.main_window.power_on_requested.connect(self._on_power_on_requested)
        self.main_window.power_off_requested.connect(self._on_power_off_requested)

        # Recording button
        self.main_window.recording_start_requested.connect(
            self._on_recording_start_requested,
        )
        self.main_window.recording_stop_requested.connect(
            self._on_recording_stop_requested,
        )

        # Start button (data acquisition)
        self.main_window.sidebar.start_cycle_btn.clicked.connect(
            self._on_start_button_clicked,
        )

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

        # Check if any hardware was actually detected
        hardware_detected = any(
            [
                status.get("ctrl_type"),
                status.get("knx_type"),
                status.get("pump_connected"),
                status.get("spectrometer"),
            ],
        )

        # Update power button based on whether hardware was found
        if hardware_detected:
            self.main_window.set_power_state("connected")
        else:
            logger.info(
                "No hardware detected - resetting power button to disconnected state",
            )
            self.main_window.set_power_state("disconnected")
            from widgets.message import show_message

            show_message(
                "No devices found. Please check connections and try again.",
                "Connection Failed",
                parent=self.main_window,
            )
            return  # Exit early if no hardware detected

        # Re-initialize device config with actual device serial number
        device_serial = status.get("spectrometer_serial")
        if device_serial:
            logger.info(
                f"Re-initializing device configuration for S/N: {device_serial}",
            )
            self.main_window._init_device_config(device_serial=device_serial)
        else:
            logger.warning(
                "No spectrometer serial in hardware status - using default config",
            )

        # Update last power-on timestamp in maintenance tracking
        self.main_window.update_last_power_on()

        # Update Device Status UI with hardware details (always, even on status updates)
        logger.debug(
            f"🔍 Calling _update_device_status_ui with optics_ready={status.get('optics_ready')}, sensor_ready={status.get('sensor_ready')}",
        )
        self._update_device_status_ui(status)

        # Load servo positions and LED intensities from device EEPROM
        self._load_device_settings()

        # Start calibration ONLY on initial connection, not on status updates
        # This prevents calibration from restarting when optics_ready changes
        if not self._initial_connection_done:
            self._initial_connection_done = True

            # Start calibration ONLY if BOTH controller and spectrometer are connected
            # Calibration requires both hardware components
            if (
                status.get("ctrl_type")
                and status.get("spectrometer")
                and not self._calibration_completed
            ):
                logger.info("🎯 Starting automatic calibration...")
                logger.info(f"   Controller: {status.get('ctrl_type')}")
                logger.info("   Spectrometer: Connected")
                # Trigger calibration through data acquisition manager
                self.data_mgr.start_calibration()
            elif (
                status.get("ctrl_type")
                and status.get("spectrometer")
                and self._calibration_completed
            ):
                logger.info(
                    "✅ Calibration already completed - waiting for user to press Start button",
                )
            elif status.get("spectrometer") and not status.get("ctrl_type"):
                logger.warning("⚠️ Spectrometer detected but no controller found")
                logger.info("📋 Controller is required for calibration")
                logger.info("📋 Please connect the controller to perform calibration")
            elif status.get("ctrl_type") and not status.get("spectrometer"):
                logger.warning("⚠️ Controller detected but no spectrometer found")
                logger.info("📋 Spectrometer is required for calibration")
                logger.info("📋 Please connect the spectrometer to perform calibration")
        else:
            logger.debug(
                "Hardware status update received (not initial connection) - skipping calibration check",
            )

    def _on_hardware_disconnected(self):
        """Hardware disconnected."""
        logger.info("Hardware disconnected")

        # Reset calibration completed flag
        self._calibration_completed = False
        self._initial_connection_done = False  # Reset for next connection

        # Update power button to disconnected state
        self.main_window.set_power_state("disconnected")

        # Clear hardware status UI to show no devices
        empty_status = {
            "ctrl_type": None,
            "knx_type": None,
            "pump_connected": False,
            "spectrometer": False,
            "sensor_ready": False,
            "optics_ready": False,
            "fluidics_ready": False,
        }
        self.main_window.update_hardware_status(empty_status)

    def _on_connection_progress(self, message: str):
        """Hardware connection progress update."""
        logger.info(f"Connection: {message}")

    def _on_hardware_error(self, error: str):
        """Hardware error occurred."""
        logger.error(f"Hardware error: {error}")
        from widgets.message import show_message

        show_message(error, "Hardware Error", parent=self.main_window)

        # If error occurs during connection, reset power button
        if self.main_window.power_btn.property("powerState") == "searching":
            logger.info("Resetting power button state after connection error")
            self.main_window.set_power_state("disconnected")

    # === Data Acquisition Callbacks ===

    def _start_processing_thread(self):
        """Start dedicated processing thread for spectrum data (Phase 3 optimization).

        Separates acquisition from processing to prevent jitter in acquisition timing.
        Acquisition thread only queues data, processing thread handles all analysis.
        """
        import threading

        self._processing_active = True
        self._processing_thread = threading.Thread(
            target=self._processing_worker,
            name="SpectrumProcessing",
            daemon=True,
        )
        self._processing_thread.start()
        logger.info("✅ Processing thread started (acquisition/processing separated)")

    def _stop_processing_thread(self):
        """Stop processing thread gracefully."""
        if self._processing_thread and self._processing_active:
            self._processing_active = False
            # Send sentinel to wake up thread
            try:
                self._spectrum_queue.put(None, timeout=0.1)
            except:
                pass
            self._processing_thread.join(timeout=2.0)
            logger.info("✅ Processing thread stopped")

    def _processing_worker(self):
        """Worker thread for processing spectrum data (Phase 3 optimization).

        Runs in dedicated thread to prevent processing from affecting acquisition timing.
        Processes data from queue and updates buffers/graphs.
        """
        import queue

        logger.info("🟢 Processing worker started")

        while self._processing_active:
            try:
                # Get next spectrum from queue (blocks until available)
                data = self._spectrum_queue.get(timeout=0.5)

                # Check for sentinel (shutdown signal)
                if data is None:
                    break

                # Process spectrum data
                self._process_spectrum_data(data)
                self._queue_stats["processed"] += 1

                # Track max queue size for monitoring
                current_size = self._spectrum_queue.qsize()
                self._queue_stats["max_size"] = max(
                    current_size,
                    self._queue_stats["max_size"],
                )

            except queue.Empty:
                # Timeout - check if we should continue
                continue
            except Exception as e:
                logger.error(f"❌ Processing worker error: {e}", exc_info=True)

        # Log final statistics
        logger.info(
            f"🔴 Processing worker stopped - Stats: {self._queue_stats['processed']} processed, "
            f"{self._queue_stats['dropped']} dropped, max queue: {self._queue_stats['max_size']}",
        )

    def _on_spectrum_acquired(self, data: dict):
        """Acquisition callback - minimal processing, queue for worker thread (Phase 3).

        This runs in the acquisition thread/callback and must be FAST.
        Only does timestamp calculation and queuing - all processing in worker thread.
        """
        # Initialize experiment start time on first data point
        if self.experiment_start_time is None:
            self.experiment_start_time = data["timestamp"]

        # Calculate elapsed time (minimal work in acquisition thread)
        data["elapsed_time"] = data["timestamp"] - self.experiment_start_time

        # Queue for processing thread (non-blocking)
        try:
            self._spectrum_queue.put_nowait(data)
        except:
            # Queue full - log and drop (prevents blocking acquisition)
            self._queue_stats["dropped"] += 1
            if self._queue_stats["dropped"] % 10 == 1:  # Log every 10th drop
                logger.warning(
                    f"⚠️ Spectrum queue full - {self._queue_stats['dropped']} frames dropped",
                )

    def _process_spectrum_data(self, data: dict):
        """Process spectrum data in dedicated worker thread (Phase 3 optimization).

        All the actual processing happens here, not in acquisition callback.
        This includes: intensity monitoring, transmission updates, buffer updates, etc.
        """
        with measure("spectrum_processing.total"):
            channel = data["channel"]  # 'a', 'b', 'c', 'd'
            wavelength = data["wavelength"]  # nm
            intensity = data.get("intensity", 0)  # Raw intensity
            timestamp = data["timestamp"]
            elapsed_time = data["elapsed_time"]
            is_preview = data.get(
                "is_preview",
                False,
            )  # Interpolated preview vs real data

            # === INTENSITY MONITORING FOR LEAK DETECTION ===
            # Only perform full processing on real data (not preview interpolations)
            if not is_preview:
                with measure("intensity_monitoring"):
                    self._handle_intensity_monitoring(channel, data, timestamp)

            # === TRANSMISSION SPECTRUM QUEUING (PHASE 2 OPTIMIZATION) ===
            # Queue transmission updates instead of immediate rendering to prevent blocking
            if (
                not is_preview
                and self._should_update_transmission()
                and channel in self.data_mgr.ref_sig
            ):
                with measure("transmission_queueing"):
                    self._queue_transmission_update(channel, data)

            # Append to timeline data buffers (RAW data - unfiltered)
            with measure("buffer_append"):
                self.buffer_mgr.append_timeline_point(channel, elapsed_time, wavelength)

            # Queue graph update instead of immediate update (throttled by timer)
            # This prevents UI freezing from excessive redraws (40+ per second)
            if self.main_window.live_data_enabled:
                self._pending_graph_updates[channel] = {
                    "elapsed_time": elapsed_time,
                    "channel": channel,
                }

            # Auto-follow latest data with stop cursor (like old software)
            # Only move cursor if not currently being dragged by user
            if (
                hasattr(self.main_window.full_timeline_graph, "stop_cursor")
                and self.main_window.full_timeline_graph.stop_cursor is not None
            ):
                stop_cursor = self.main_window.full_timeline_graph.stop_cursor

                # Check moving attribute exists (defensive against initialization timing)
                is_moving = getattr(stop_cursor, "moving", False)

                if not is_moving:
                    # Move stop cursor to follow latest time point
                    stop_cursor.setValue(elapsed_time)
                    # Update label if it exists
                    if hasattr(stop_cursor, "label") and stop_cursor.label:
                        stop_cursor.label.setFormat(f"Stop: {elapsed_time:.1f}s")

        # Record data point if recording is active
        if self.recording_mgr.is_recording:
            # Build data point with all channels (use latest value for each)
            data_point = {}
            for ch in self._idx_to_channel:
                latest_value = self.buffer_mgr.get_latest_value(ch)
                data_point[f"channel_{ch}"] = (
                    latest_value if latest_value is not None else ""
                )

            self.recording_mgr.record_data_point(data_point)

        # Update cycle of interest graph (bottom graph)
        self._update_cycle_of_interest_graph()

    def _handle_intensity_monitoring(self, channel: str, data: dict, timestamp: float):
        """Handle intensity monitoring and leak detection (extracted for clarity).

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            data: Spectrum data dictionary
            timestamp: Acquisition timestamp

        """
        import numpy as np

        intensity = data.get("intensity", 0)

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
            dark_noise = getattr(self.data_mgr, "dark_noise", None)
            if dark_noise is not None:
                # Calculate average intensity over window
                avg_intensity = self.buffer_mgr.get_intensity_average(channel)

                # Check if intensity is too low (near dark noise)
                dark_threshold = np.mean(dark_noise) * LEAK_THRESHOLD_RATIO
                if avg_intensity < dark_threshold:
                    logger.warning(
                        f"⚠️ Possible optical leak detected in channel {channel.upper()}: "
                        f"avg intensity {avg_intensity:.0f} < threshold {dark_threshold:.0f}",
                    )

    def _queue_transmission_update(self, channel: str, data: dict):
        """Queue transmission spectrum update for batch processing (Phase 2 optimization).

        Instead of updating plots immediately in acquisition thread, queue the data
        for batch processing in the UI timer. This prevents blocking.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            data: Spectrum data dictionary containing transmission_spectrum and raw_spectrum

        """
        transmission = data.get("transmission_spectrum")
        raw_spectrum = data.get("raw_spectrum")

        # Fallback: calculate transmission if not provided
        if transmission is None and raw_spectrum is not None and len(raw_spectrum) > 0:
            ref_spectrum = self.data_mgr.ref_sig[channel]
            transmission = calculate_transmission(raw_spectrum, ref_spectrum)

        # Queue for batch update if we have valid data
        if transmission is not None and len(transmission) > 0:
            self._pending_transmission_updates[channel] = {
                "transmission": transmission,
                "raw_spectrum": raw_spectrum,
                "wavelengths": self.data_mgr.wave_data,
            }

    def _should_update_transmission(self):
        """Check if transmission plot updates are needed (lazy evaluation).

        Skip expensive transmission calculations if the feature is disabled
        or preconditions aren't met.
        """
        if not hasattr(self.main_window, "spectroscopy_enabled"):
            return False
        if not self.main_window.spectroscopy_enabled.isChecked():
            return False
        if not hasattr(self.data_mgr, "ref_sig") or not self.data_mgr.ref_sig:
            return False
        if not hasattr(self.data_mgr, "wave_data") or self.data_mgr.wave_data is None:
            return False
        return True

    def _on_tab_changing(self, index):
        """Temporarily pause graph updates during tab transition.

        Tab switching can trigger widget repaints that block the UI thread
        when combined with graph updates. Brief pause prevents freezing.
        """
        self._skip_graph_updates = True
        # Resume updates after 200ms (enough time for tab transition to complete)
        QTimer.singleShot(200, lambda: setattr(self, "_skip_graph_updates", False))

    def _process_pending_ui_updates(self):
        """Process queued graph updates at throttled rate (10 FPS).

        This prevents UI freezing from excessive redraws when data arrives
        at 40+ spectra per second across 4 channels.

        During LIVE acquisition: Shows all data with simple downsampling for performance.
        During POST-RUN: Full resolution available for detailed analysis.
        """
        with measure("ui_update_timer"):
            if not self.main_window.live_data_enabled:
                return

            # Skip updates during tab transitions to prevent UI freezing
            if self._skip_graph_updates:
                return

            # Process all pending channel updates in one batch
            for channel, update_data in self._pending_graph_updates.items():
                if update_data is None:
                    continue

                try:
                    channel_idx = self._channel_to_idx[channel]
                    curve = self.main_window.full_timeline_graph.curves[channel_idx]

                    # Get raw timeline data
                    raw_time = self.buffer_mgr.timeline_data[channel].time
                    raw_wavelength = self.buffer_mgr.timeline_data[channel].wavelength

                    # Validation checks
                    if not isinstance(raw_time, np.ndarray) or not isinstance(
                        raw_wavelength,
                        np.ndarray,
                    ):
                        continue
                    if len(raw_time) == 0 or len(raw_wavelength) == 0:
                        continue
                    if len(raw_time) != len(raw_wavelength):
                        continue

                    # Apply filtering if enabled
                    if self._filter_enabled and len(raw_wavelength) > 2:
                        with measure("filtering.online_smoothing"):
                            display_wavelength = self._apply_online_smoothing(
                                raw_wavelength,
                                self._filter_strength,
                                channel,
                            )
                    else:
                        display_wavelength = raw_wavelength

                    # Simple downsampling for performance during live acquisition
                    # Keep graph responsive by limiting total points displayed
                    MAX_PLOT_POINTS = 2000  # Sufficient for smooth rendering at 10 FPS
                    if len(raw_time) > MAX_PLOT_POINTS:
                        step = len(raw_time) // MAX_PLOT_POINTS
                        display_time = raw_time[::step]
                        display_wavelength = display_wavelength[::step]
                    else:
                        display_time = raw_time

                    # Update graph
                    with measure("graph_update.setData"):
                        curve.setData(display_time, display_wavelength)

                except Exception:
                    # Silent fail - these are non-critical display errors
                    pass

            # Clear processed updates
            self._pending_graph_updates = {"a": None, "b": None, "c": None, "d": None}

            # === PROCESS PENDING TRANSMISSION UPDATES (PHASE 2 OPTIMIZATION) ===
            # Batch process transmission spectrum updates to prevent blocking acquisition thread
            with measure("transmission_batch_process"):
                self._process_transmission_updates()

    def _process_transmission_updates(self):
        """Process queued transmission spectrum updates in batch (Phase 2 optimization).

        This runs in the UI timer (10 FPS) instead of the acquisition thread,
        preventing blocking calls to setData() from delaying spectrum acquisition.
        """
        if not hasattr(self.main_window, "transmission_curves"):
            return

        for channel, update_data in self._pending_transmission_updates.items():
            if update_data is None:
                continue

            try:
                channel_idx = self._channel_to_idx[channel]
                transmission = update_data["transmission"]
                raw_spectrum = update_data.get("raw_spectrum")
                wavelengths = update_data.get("wavelengths")

                if wavelengths is None or len(wavelengths) != len(transmission):
                    continue

                # Update transmission curve
                self.main_window.transmission_curves[channel_idx].setData(
                    wavelengths,
                    transmission,
                )

                # Log successful update (only first time per channel) - simplified logging
                if not hasattr(self, "_transmission_update_logged"):
                    self._transmission_update_logged = set()
                if channel not in self._transmission_update_logged:
                    logger.info(
                        f"✅ Ch {channel.upper()}: Transmission plot updated ({len(wavelengths)} points)",
                    )
                    self._transmission_update_logged.add(channel)
                    # Force autoscale on first update
                    self.main_window.transmission_plot.enableAutoRange()

                # Update raw data plot
                if (
                    hasattr(self.main_window, "raw_data_curves")
                    and raw_spectrum is not None
                ):
                    self.main_window.raw_data_curves[channel_idx].setData(
                        wavelengths,
                        raw_spectrum,
                    )

                    # Log successful update (only first time per channel)
                    if not hasattr(self, "_raw_update_logged"):
                        self._raw_update_logged = set()
                    if channel not in self._raw_update_logged:
                        logger.info(f"✅ Ch {channel.upper()}: Raw data plot updated")
                        self._raw_update_logged.add(channel)
                        self.main_window.raw_data_plot.enableAutoRange()

            except Exception:
                # Silent fail - non-critical display error
                pass  # Clear processed updates
        self._pending_transmission_updates = {
            "a": None,
            "b": None,
            "c": None,
            "d": None,
        }

    def _update_cycle_of_interest_graph(self):
        """Update the cycle of interest graph based on cursor positions.

        Also triggers autosave when cycle region changes significantly.
        """
        with measure("cycle_graph_update.total"):
            # Get cursor positions from full timeline graph
            start_time = self.main_window.full_timeline_graph.start_cursor.value()
            stop_time = self.main_window.full_timeline_graph.stop_cursor.value()

        # Check if this is a new cycle region (for autosave)
        cycle_changed = False
        if not hasattr(self, "_last_cycle_bounds") or self._last_cycle_bounds is None:
            self._last_cycle_bounds = (start_time, stop_time)
            cycle_changed = True
        else:
            last_start, last_stop = self._last_cycle_bounds
            # Consider it a new cycle if boundaries moved significantly (>5% of duration)
            duration = stop_time - start_time
            if (
                abs(start_time - last_start) > duration * 0.05
                or abs(stop_time - last_stop) > duration * 0.05
            ):
                cycle_changed = True
                self._last_cycle_bounds = (start_time, stop_time)

        # Extract data within cursor range for each channel
        for ch_letter, ch_idx in self._channel_pairs:
            cycle_time, cycle_wavelength = self.buffer_mgr.extract_cycle_region(
                ch_letter,
                start_time,
                stop_time,
            )

            if len(cycle_time) == 0:
                continue

            # Apply filtering to CYCLE OF INTEREST (subset) - batch filtering for accuracy
            # This is where we want high-quality filtering since it's used for analysis
            if self._filter_enabled and len(cycle_wavelength) > 2:
                cycle_wavelength = self._apply_smoothing(
                    cycle_wavelength,
                    self._filter_strength,
                )

            # Calculate Δ SPR (baseline is first point in cycle or calibrated baseline)
            baseline = self.buffer_mgr.baseline_wavelengths[ch_letter]
            if baseline is None:
                # Use first point in cycle as baseline
                baseline = cycle_wavelength[0] if len(cycle_wavelength) > 0 else 0

            # Convert wavelength shift to RU (Response Units)
            delta_spr = (cycle_wavelength - baseline) * WAVELENGTH_TO_RU_CONVERSION

            # Store in buffer manager
            self.buffer_mgr.update_cycle_data(
                ch_letter,
                cycle_time,
                cycle_wavelength,
                delta_spr,
            )

        # Apply reference subtraction if enabled
        self._apply_reference_subtraction()

        # Update graph curves with potentially subtracted data
        for ch_letter, ch_idx in self._channel_pairs:
            cycle_time = self.buffer_mgr.cycle_data[ch_letter].time
            delta_spr = self.buffer_mgr.cycle_data[ch_letter].spr

            if len(cycle_time) == 0:
                continue

            # Update cycle of interest graph
            curve = self.main_window.cycle_of_interest_graph.curves[ch_idx]
            curve.setData(cycle_time, delta_spr)

        # Autosave cycle data when boundaries change significantly
        if cycle_changed and len(self.buffer_mgr.cycle_data["a"].time) > 10:
            self._autosave_cycle_data(start_time, stop_time)

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
        for ch in self._idx_to_channel:
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
            f"Ch C: {delta_values['c']:.1f} RU  |  Ch D: {delta_values['d']:.1f} RU",
        )

    def _on_calibration_started(self):
        """Calibration routine started."""
        logger.info("Calibration started...")

        # Show calibration progress dialog using new generic dialog with Start button
        from LL_UI_v1_0 import StartupCalibProgressDialog

        self._calibration_dialog = StartupCalibProgressDialog(
            parent=self.main_window,
            title="Calibrating SPR System",
            message="Initializing calibration...\nThis may take 30-60 seconds.",
            show_start_button=True,  # Show Start button (initially disabled)
        )

        # Connect Start button signal to start acquisition
        self._calibration_dialog.start_clicked.connect(self._on_start_button_clicked)

        # Connect error state buttons
        self._calibration_dialog.retry_clicked.connect(self._on_calibration_retry)
        self._calibration_dialog.continue_anyway_clicked.connect(
            self._on_calibration_continue_anyway,
        )

        # Initialize progress tracking
        self._calibration_steps_total = (
            7  # wavelength, integration, S-LED, dark, S-ref, P-LED, verify
        )
        self._calibration_steps_completed = 0

        # Set progress bar to determinate mode and start at 0%
        self._calibration_dialog.set_progress(0, 100)

        self._calibration_dialog.show()

        logger.info("📊 Calibration progress dialog displayed")

    def _on_calibration_complete(self, calibration_data: dict):
        """Calibration completed successfully."""
        ch_error_list = calibration_data.get("ch_error_list", [])
        calibration_type = calibration_data.get(
            "calibration_type",
            "full",
        )  # 'full', 'afterglow', 'led'
        s_ref_qc_results = calibration_data.get("s_ref_qc_results", {})

        # Log summary instead of full data dictionary
        logger.info(f"✅ Calibration complete ({calibration_type})")
        logger.info(
            f"📊 Integration time: {calibration_data.get('integration_time', 'unknown')}ms, Num scans: {calibration_data.get('num_scans', 'unknown')}",
        )

        # Log LED intensities in a clean format
        leds = calibration_data.get("leds_calibrated", {})
        if leds:
            led_str = ", ".join(
                [
                    f"Ch {ch.upper()}: {intensity}"
                    for ch, intensity in sorted(leds.items())
                ],
            )
            logger.info(f"💡 LED Intensities: {led_str}")

        # Check if afterglow correction was loaded
        if (
            hasattr(self.data_mgr, "afterglow_enabled")
            and self.data_mgr.afterglow_enabled
        ):
            logger.info("✅ Afterglow correction is ACTIVE")

        # Update hardware manager with calibration results for optics verification
        # Now includes S-ref optical QC results
        self.hardware_mgr.update_calibration_status(
            ch_error_list,
            calibration_type,
            s_ref_qc_results,
        )

        # Check if calibration failed for any channels
        if len(ch_error_list) > 0:
            logger.warning(
                f"⚠️ Calibration completed with errors in channels: {ch_error_list}",
            )

            # Increment retry count
            self._calibration_retry_count += 1

            # Check if this is due to weak intensity (maintenance required)
            maintenance_required = []
            for ch in ch_error_list:
                if ch in self.hardware_mgr._maintenance_required:
                    maintenance_required.append(ch)

            # Build error message
            ch_str = ", ".join([ch.upper() for ch in ch_error_list])

            if self._calibration_retry_count >= self._max_calibration_retries:
                # Max retries reached - show inline error with Continue option only
                if len(maintenance_required) > 0:
                    maint_str = ", ".join([ch.upper() for ch in maintenance_required])
                    error_msg = (
                        f"Channels {ch_str} failed.\n"
                        f"Channels {maint_str} show weak LED intensity\n"
                        f"and may require LED PCB replacement."
                    )
                else:
                    error_msg = (
                        f"Channels {ch_str} failed.\n"
                        f"The optics may require cleaning or adjustment."
                    )

                # Update dialog to show max retries error
                if (
                    self._calibration_dialog
                    and not self._calibration_dialog._is_closing
                ):
                    try:
                        self._calibration_dialog.show_max_retries_error(error_msg)
                        logger.info("📋 Max retries reached - showing Continue option")
                    except Exception as e:
                        logger.error(
                            f"Failed to update dialog with max retries error: {e}",
                        )

                # Don't auto-continue - wait for user to click Continue button
                return
            # Show inline error with Retry/Continue buttons
            if len(maintenance_required) > 0:
                maint_str = ", ".join([ch.upper() for ch in maintenance_required])
                error_msg = (
                    f"Channels {ch_str} failed.\n"
                    f"Channels {maint_str} show weak LED intensity\n"
                    f"and may require maintenance."
                )
            else:
                error_msg = (
                    f"Channels {ch_str} failed.\n"
                    f"The optics may require cleaning or adjustment."
                )

            # Update dialog to show error state
            if self._calibration_dialog and not self._calibration_dialog._is_closing:
                try:
                    self._calibration_dialog.show_error_state(
                        error_msg,
                        self._calibration_retry_count,
                        self._max_calibration_retries,
                    )
                    logger.info(
                        "📋 Calibration failed - showing Retry/Continue options",
                    )
                except Exception as e:
                    logger.error(f"Failed to update dialog with error state: {e}")

            # Don't save settings or proceed - wait for user action
            return
        # Calibration successful - update dialog to show success
        logger.info("✅ All channels calibrated successfully - optics ready")
        self._calibration_retry_count = 0  # Reset retry count
        self._calibration_completed = (
            True  # Mark calibration as completed to prevent loop
        )

        # Update existing dialog to show success and enable Start button (with state checking)
        # Use QTimer to ensure UI update happens on main thread
        if self._calibration_dialog and not self._calibration_dialog._is_closing:
            from PySide6.QtCore import QTimer

            def update_dialog_success():
                """Update dialog on main thread."""
                if (
                    self._calibration_dialog
                    and not self._calibration_dialog._is_closing
                ):
                    try:
                        self._calibration_dialog.update_title("✅ Calibration Complete")
                        self._calibration_dialog.update_status(
                            "All channels are ready!\n\nPress Start to begin data acquisition.",
                        )

                        # Set progress to 100%
                        self._calibration_dialog.set_progress(100, 100)

                        # Enable Start button
                        self._calibration_dialog.enable_start_button()

                        # Hide overlay so user can see UI is ready (but keep dialog on top)
                        if (
                            hasattr(self._calibration_dialog, "overlay")
                            and self._calibration_dialog.overlay
                        ):
                            self._calibration_dialog.overlay.hide()

                        logger.info("📋 Calibration complete - Start button enabled")
                    except (RuntimeError, AttributeError) as e:
                        logger.warning(f"Dialog state error during success update: {e}")
                        # Dialog was closed/deleted - recreate a simple success message
                        from widgets.message import show_message

                        show_message(
                            "Calibration completed successfully!\n\nPress the Start button to begin acquisition.",
                            "Calibration Complete",
                            parent=self.main_window,
                        )

            # Schedule UI update on main thread
            QTimer.singleShot(0, update_dialog_success)

        # Save calibrated LED intensities and settings to device config
        if self.main_window.device_config:
            try:
                led_intensities = calibration_data.get("leds_calibrated", {})
                if led_intensities:
                    self.main_window.device_config.set_led_intensities(
                        led_intensities.get("a", 0),
                        led_intensities.get("b", 0),
                        led_intensities.get("c", 0),
                        led_intensities.get("d", 0),
                    )

                # Save integration time and num scans
                integration_time = calibration_data.get("integration_time")
                num_scans = calibration_data.get("num_scans")
                if integration_time and num_scans:
                    self.main_window.device_config.set_calibration_settings(
                        integration_time,
                        num_scans,
                    )

                self.main_window.device_config.save()
                logger.info("💾 Calibration settings saved to device config file")
            except Exception as e:
                logger.warning(f"Failed to save calibration to device config: {e}")

        # Update UI with calibrated LED intensities
        self._update_led_intensities_in_ui()

        # Ensure calibration dialog is closed for all completion paths
        # (Success path keeps dialog open with Start button enabled)
        if self._calibration_dialog and len(ch_error_list) > 0:
            # Only close immediately if there were errors and user chose to continue
            # Success path keeps dialog open with Start button
            self._close_calibration_dialog()

        # DO NOT auto-start acquisition - wait for user to press Start button in dialog
        logger.info("📋 Calibration complete - waiting for user to press Start button")

    def _on_calibration_retry(self):
        """User clicked Retry button in calibration dialog."""
        logger.info(
            f"🔄 User chose to retry calibration (attempt {self._calibration_retry_count + 1}/{self._max_calibration_retries})",
        )

        # Reset flag to allow retry
        self._calibration_completed = False

        # Reset dialog to progress state
        if self._calibration_dialog and not self._calibration_dialog._is_closing:
            try:
                self._calibration_dialog.reset_to_progress_state()
                self._calibration_dialog.update_title("Retrying Calibration")
                self._calibration_dialog.update_status(
                    "Restarting calibration process...",
                )
                self._calibration_dialog.set_progress(0, 100)

                # Reset step tracking
                self._calibration_steps_completed = 0
            except Exception as e:
                logger.error(f"Failed to reset dialog: {e}")

        # Start new calibration attempt
        self.data_mgr.start_calibration()

    def _on_calibration_continue_anyway(self):
        """User clicked Continue Anyway button in calibration dialog."""
        logger.info("✅ User chose to continue despite calibration failures")

        # Reset retry count
        self._calibration_retry_count = 0

        # Mark as completed to prevent re-triggering
        self._calibration_completed = True

        # Update dialog to success state with Start button
        if self._calibration_dialog and not self._calibration_dialog._is_closing:
            try:
                self._calibration_dialog.reset_to_progress_state()
                self._calibration_dialog.update_title("⚠️ Ready (Partial Calibration)")
                self._calibration_dialog.update_status(
                    "Some channels failed calibration.\n\n"
                    "You can proceed with available channels.\n"
                    "Press Start to begin data acquisition.",
                )
                self._calibration_dialog.set_progress(100, 100)

                # Ensure Start button exists and is shown for partial calibration
                if not self._calibration_dialog.start_button:
                    # Create Start button if it doesn't exist
                    self._calibration_dialog.start_button = QPushButton("Start")
                    self._calibration_dialog.start_button.setFixedSize(140, 36)
                    self._calibration_dialog.start_button.setStyleSheet(
                        "QPushButton {"
                        "  background: #007AFF;"
                        "  color: white;"
                        "  border: none;"
                        "  border-radius: 6px;"
                        "  font-size: 13px;"
                        "  font-weight: 600;"
                        "  padding: 8px 16px;"
                        "}"
                        "QPushButton:hover {"
                        "  background: #0051D5;"
                        "}"
                        "QPushButton:pressed {"
                        "  background: #004FC4;"
                        "}"
                        "QPushButton:disabled {"
                        "  background: #E5E5EA;"
                        "  color: #86868B;"
                        "}",
                    )
                    self._calibration_dialog.start_button.clicked.connect(
                        self._calibration_dialog._on_start_clicked,
                    )
                    self._calibration_dialog.button_layout.insertWidget(
                        1,
                        self._calibration_dialog.start_button,
                    )

                # Show and enable Start button
                self._calibration_dialog.start_button.show()
                self._calibration_dialog.enable_start_button()

                # Hide overlay so user can see UI
                if (
                    hasattr(self._calibration_dialog, "overlay")
                    and self._calibration_dialog.overlay
                ):
                    self._calibration_dialog.overlay.hide()

            except Exception as e:
                logger.error(f"Failed to update dialog: {e}")

        # Save calibration data (even partial) - this was skipped by the early return
        if self.main_window.device_config:
            try:
                # Get the last calibration data from data_mgr
                if hasattr(self.data_mgr, "leds_calibrated"):
                    self.main_window.device_config.set_led_intensities(
                        self.data_mgr.leds_calibrated.get("a", 0),
                        self.data_mgr.leds_calibrated.get("b", 0),
                        self.data_mgr.leds_calibrated.get("c", 0),
                        self.data_mgr.leds_calibrated.get("d", 0),
                    )

                if hasattr(self.data_mgr, "integration_time") and hasattr(
                    self.data_mgr,
                    "num_scans",
                ):
                    self.main_window.device_config.set_calibration_settings(
                        self.data_mgr.integration_time,
                        self.data_mgr.num_scans,
                    )

                self.main_window.device_config.save()
                logger.info("💾 Partial calibration settings saved to device config")
            except Exception as e:
                logger.warning(f"Failed to save partial calibration: {e}")

        # Update UI with calibrated LED intensities
        self._update_led_intensities_in_ui()

    def _on_start_button_clicked(self):
        """User clicked Start button - begin data acquisition."""
        logger.info("🎬 Start button clicked - initiating data acquisition")

        # Check if calibration is still in progress
        if hasattr(self.data_mgr, "_calibrating") and self.data_mgr._calibrating:
            logger.warning(
                "⚠️ Calibration still in progress - please wait for completion",
            )
            from widgets.message import show_message

            show_message(
                "Calibration is still in progress.\n\n"
                "Please wait for calibration to complete before starting acquisition.",
                "Calibration In Progress",
                parent=self.main_window,
            )
            return

        # Check if system is calibrated
        if not self.data_mgr.calibrated:
            from widgets.message import show_message

            show_message(
                "Please calibrate the system first.\n\n"
                "Use 'Simple LED Calibration' from the Advanced Settings menu.",
                "Calibration Required",
                parent=self.main_window,
            )
            return

        # Check if already acquiring
        if self.data_mgr._acquiring:
            logger.warning("Data acquisition already running")
            return

        # Dialog will close itself via _on_start_clicked
        # Just clear the reference here
        if self._calibration_dialog:
            logger.debug("Clearing calibration dialog reference")
            self._calibration_dialog = None

        # Check optics status - if not ready, apply visual warning
        if (
            hasattr(self.hardware_mgr, "_optics_verified")
            and not self.hardware_mgr._optics_verified
        ):
            logger.warning(
                "⚠️ Starting acquisition with optics NOT ready - applying visual warning",
            )
            self.main_window._set_optics_warning()

        # Start data acquisition
        try:
            self.data_mgr.start_acquisition()
            logger.info("✅ Data acquisition started successfully")

            # Update UI state (button should become Stop button)
            # TODO: Update button text/icon to indicate running state

        except Exception as e:
            logger.error(f"Failed to start data acquisition: {e}")
            from widgets.message import show_message

            show_message(
                f"Failed to start acquisition:\n{e}",
                "Acquisition Error",
                parent=self.main_window,
            )

    def _close_calibration_dialog(self):
        """Helper to close calibration dialog and clean up."""
        logger.debug("_close_calibration_dialog() called")
        if self._calibration_dialog:
            try:
                logger.debug("Attempting to close and delete calibration dialog")
                self._calibration_dialog.close()
                self._calibration_dialog.deleteLater()
                logger.info("✅ Calibration dialog closed and cleaned up")
            except Exception as e:
                logger.warning(f"Error closing calibration dialog: {e}")
            finally:
                self._calibration_dialog = None
        else:
            logger.debug("No calibration dialog to close (already None)")

    def _on_calibration_failed(self, error: str):
        """Calibration failed."""
        logger.error(f"Calibration failed: {error}")

        # Update dialog to show error
        if self._calibration_dialog:
            self._calibration_dialog.update_title("❌ Calibration Failed")
            self._calibration_dialog.update_status(
                f"Error: {error}\n\nDialog will close automatically.",
            )

            # Auto-close after 4 seconds
            from PySide6.QtCore import QTimer

            QTimer.singleShot(4000, lambda: self._close_calibration_dialog())
        else:
            # Fallback if dialog doesn't exist
            from widgets.message import show_message

            show_message(error, "Calibration Error", parent=self.main_window)

    def _on_calibration_progress(self, message: str):
        """Calibration progress update with real-time step tracking."""
        logger.debug(f"Calibration progress: {message}")

        # Update calibration dialog with progress tracking (thread-safe)
        if self._calibration_dialog and not self._calibration_dialog._is_closing:
            try:
                message_lower = message.lower()

                # Define calibration steps with generic user-facing messages
                step_mapping = {
                    # Step 1: Wavelength calibration
                    ("wavelength", "calibration"): {
                        "step": 1,
                        "user_msg": "Initializing...",
                        "detail": "Please wait",
                    },
                    # Step 2: Integration time optimization
                    ("integration", "time"): {
                        "step": 2,
                        "user_msg": "Configuring...",
                        "detail": "Please wait",
                    },
                    ("optimizing", "integration"): {
                        "step": 2,
                        "user_msg": "Configuring...",
                        "detail": "Please wait",
                    },
                    # Step 3: S-mode LED calibration
                    ("s-mode", "led"): {
                        "step": 3,
                        "user_msg": "Calibrating optics...",
                        "detail": "Please wait",
                    },
                    ("s-led", "calibrat"): {
                        "step": 3,
                        "user_msg": "Calibrating optics...",
                        "detail": "Please wait",
                    },
                    # Step 4: Dark noise measurement
                    ("dark", "noise"): {
                        "step": 4,
                        "user_msg": "Measuring baseline...",
                        "detail": "Please wait",
                    },
                    ("measuring", "dark"): {
                        "step": 4,
                        "user_msg": "Measuring baseline...",
                        "detail": "Please wait",
                    },
                    # Step 5: S-mode reference capture
                    ("s-ref", "capture"): {
                        "step": 5,
                        "user_msg": "Capturing reference...",
                        "detail": "Please wait",
                    },
                    ("capturing", "s-ref"): {
                        "step": 5,
                        "user_msg": "Capturing reference...",
                        "detail": "Please wait",
                    },
                    ("reference", "s-mode"): {
                        "step": 5,
                        "user_msg": "Capturing reference...",
                        "detail": "Please wait",
                    },
                    # Step 6: P-mode LED calibration
                    ("p-mode", "led"): {
                        "step": 6,
                        "user_msg": "Optimizing channels...",
                        "detail": "Please wait",
                    },
                    ("p-led", "calibrat"): {
                        "step": 6,
                        "user_msg": "Optimizing channels...",
                        "detail": "Please wait",
                    },
                    # Step 7: Verification
                    ("verif", ""): {
                        "step": 7,
                        "user_msg": "Finalizing...",
                        "detail": "Please wait",
                    },
                    ("finaliz", ""): {
                        "step": 7,
                        "user_msg": "Finalizing...",
                        "detail": "Please wait",
                    },
                }

                # Find matching step
                current_step = None
                user_message = None
                detail_message = None

                for (keyword1, keyword2), step_info in step_mapping.items():
                    if keyword1 in message_lower and (
                        not keyword2 or keyword2 in message_lower
                    ):
                        current_step = step_info["step"]
                        user_message = step_info["user_msg"]
                        detail_message = step_info["detail"]
                        break

                if current_step:
                    # Update step counter
                    self._calibration_steps_completed = max(
                        current_step,
                        self._calibration_steps_completed,
                    )

                    # Calculate progress percentage
                    progress_percent = int(
                        (current_step / self._calibration_steps_total) * 100,
                    )

                    # Update dialog with user-friendly message
                    display_msg = f"{user_message}\n\n{detail_message}"
                    self._calibration_dialog.update_status(display_msg)
                    self._calibration_dialog.set_progress(progress_percent, 100)

                    logger.debug(
                        f"Progress: Step {current_step}/{self._calibration_steps_total} ({progress_percent}%)",
                    )
                else:
                    # Fallback for unmapped messages - show as generic progress
                    self._calibration_dialog.update_status(
                        f"⚙️ Calibrating...\n\n{message}",
                    )

            except (RuntimeError, AttributeError) as e:
                logger.debug(f"Dialog already closed or deleted: {e}")

    def _on_acquisition_error(self, error: str):
        """Data acquisition error."""
        logger.error(f"Acquisition error: {error}")

        # Check if error is due to device disconnect
        if "disconnected" in error.lower():
            logger.error("🔌 Spectrometer disconnected during acquisition")

            # Trigger hardware disconnect to clean up and reset UI
            self.hardware_mgr.disconnect()

            # Show user-friendly message
            from widgets.message import show_message

            show_message(
                "Spectrometer was disconnected.\n\n"
                "Please check the USB connection and power on again.",
                "Device Disconnected",
                parent=self.main_window,
            )
            return

        # If error indicates hardware failure, stop acquisition and show warning
        if (
            "Hardware communication lost" in error
            or "stopping acquisition" in error.lower()
        ):
            logger.warning("⚠️ Hardware error detected - stopping acquisition")

            # Update UI to show disconnected state
            self.main_window.set_power_state("error")

            # Show user-friendly message
            from widgets.message import show_message

            show_message(
                "Hardware communication lost. Please power off and reconnect the device.",
                "Hardware Error",
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

        show_message(error, "Recording Error", parent=self.main_window)

    def _on_event_logged(self, event: str):
        """Event logged to recording."""
        logger.info(f"Event: {event}")

    def _on_acquisition_pause_requested(self, pause: bool):
        """Handle acquisition pause/resume request from UI."""
        if pause:
            logger.info("⏸ Pausing live acquisition...")
            self.data_mgr.pause_acquisition()
        else:
            logger.info("▶️ Resuming live acquisition...")
            self.data_mgr.resume_acquisition()

    def _on_acquisition_started(self):
        """Live data acquisition has started - enable record and pause buttons."""
        logger.info("✅ Live acquisition started - enabling record/pause buttons")
        self.main_window.record_btn.setEnabled(True)
        self.main_window.pause_btn.setEnabled(True)
        self.main_window.record_btn.setToolTip(
            "Start Recording\n(Currently viewing - not saved)",
        )
        self.main_window.pause_btn.setToolTip("Pause Live Acquisition")

    def _on_acquisition_stopped(self):
        """Live data acquisition has stopped - disable record and pause buttons."""
        logger.info("⏹ Live acquisition stopped - disabling record/pause buttons")
        self.main_window.record_btn.setEnabled(False)
        self.main_window.pause_btn.setEnabled(False)
        self.main_window.record_btn.setToolTip(
            "Start Recording\n(Enabled after calibration)",
        )
        self.main_window.pause_btn.setToolTip(
            "Pause Live Acquisition\n(Enabled after calibration)",
        )

        # Uncheck buttons if they were active
        if self.main_window.record_btn.isChecked():
            self.main_window.record_btn.setChecked(False)
        if self.main_window.pause_btn.isChecked():
            self.main_window.pause_btn.setChecked(False)

    # === Kinetic Operations Callbacks ===

    def _on_pump_initialized(self):
        """Pump initialized successfully."""
        logger.info("✅ Pump initialized")
        # TODO: Enable pump controls in UI

    def _on_pump_error(self, error: str):
        """Pump error occurred."""
        logger.error(f"Pump error: {error}")
        from widgets.message import show_message

        show_message(error, "Pump Error", parent=self.main_window)

    def _on_pump_state_changed(self, state: dict):
        """Pump state changed."""
        channel = state.get("channel")
        running = state.get("running")
        flow_rate = state.get("flow_rate")
        logger.info(
            f"Pump {channel}: {'running' if running else 'stopped'} @ {flow_rate} μL/min",
        )
        # TODO: Update UI pump status

    def _on_valve_switched(self, valve_info: dict):
        """Valve position changed."""
        channel = valve_info.get("channel")
        position = valve_info.get("position")
        logger.info(f"Valve {channel} switched to {position}")
        # TODO: Update UI valve status

    def close(self):
        """Clean up resources on application close."""
        if self.closing:
            return True  # Already closing, prevent double cleanup

        self.closing = True
        logger.info("🔄 Closing application...")

        try:
            # Print final profiling stats if enabled
            if PROFILING_ENABLED:
                logger.info("\n📊 FINAL PROFILING STATISTICS:")
                self.profiler.print_stats(sort_by="total", min_calls=1)
                self.profiler.print_hotspots(top_n=10)

            # Stop processing thread first (Phase 3)
            logger.info("Stopping processing thread...")
            self._stop_processing_thread()

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
                    if (
                        hasattr(self.hardware_mgr, "controller")
                        and self.hardware_mgr.controller
                    ):
                        try:
                            self.hardware_mgr.controller.stop()
                            self.hardware_mgr.controller.close()
                        except Exception as e:
                            logger.error(f"Error closing controller: {e}")

                    # Close spectrometer
                    if (
                        hasattr(self.hardware_mgr, "spectrometer")
                        and self.hardware_mgr.spectrometer
                    ):
                        try:
                            self.hardware_mgr.spectrometer.close()
                        except Exception as e:
                            logger.error(f"Error closing spectrometer: {e}")

                    # Close kinetics controller
                    if (
                        hasattr(self.kinetic_mgr, "kinetics_controller")
                        and self.kinetic_mgr.kinetics_controller
                    ):
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
        if hasattr(self, "closing") and self.closing:
            return  # Normal close already happened

        logger.warning("⚠️ Emergency cleanup triggered - forcing resource release")

        # Force close all hardware connections without waiting
        try:
            if hasattr(self, "hardware_mgr") and self.hardware_mgr:
                # Close controller
                try:
                    if (
                        hasattr(self.hardware_mgr, "controller")
                        and self.hardware_mgr.controller
                    ):
                        self.hardware_mgr.controller.close()
                except Exception as e:
                    logger.error(f"Emergency cleanup - controller close failed: {e}")

                # Close spectrometer
                try:
                    if (
                        hasattr(self.hardware_mgr, "spectrometer")
                        and self.hardware_mgr.spectrometer
                    ):
                        self.hardware_mgr.spectrometer.close()
                except Exception as e:
                    logger.error(f"Emergency cleanup - spectrometer close failed: {e}")
        except Exception as e:
            logger.error(f"Emergency cleanup - hardware_mgr access failed: {e}")

        # Close kinetics
        try:
            if hasattr(self, "kinetic_mgr") and self.kinetic_mgr:
                if (
                    hasattr(self.kinetic_mgr, "kinetics_controller")
                    and self.kinetic_mgr.kinetics_controller
                ):
                    self.kinetic_mgr.kinetics_controller.close()
        except Exception as e:
            logger.error(f"Emergency cleanup - kinetics close failed: {e}")

        logger.info("✅ Emergency cleanup completed")

    def __del__(self):
        """Destructor to ensure resources are cleaned up."""
        try:
            if not hasattr(self, "closing") or not self.closing:
                logger.warning(
                    "⚠️ __del__ called without proper close - forcing cleanup",
                )
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
        if self._selected_axis == "x":
            self.main_window.cycle_of_interest_graph.enableAutoRange(axis="x")
        else:
            self.main_window.cycle_of_interest_graph.enableAutoRange(axis="y")

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

            logger.info(
                f"Setting {self._selected_axis.upper()}-axis range: [{min_val}, {max_val}]",
            )

            # Apply range to selected axis
            if self._selected_axis == "x":
                self.main_window.cycle_of_interest_graph.setXRange(
                    min_val,
                    max_val,
                    padding=0,
                )
            else:
                self.main_window.cycle_of_interest_graph.setYRange(
                    min_val,
                    max_val,
                    padding=0,
                )

        except ValueError as e:
            logger.warning(f"Invalid manual range input: {e}")

    def _on_axis_selected(self, checked: bool):
        """Axis selector button toggled."""
        if not checked:  # Button was unchecked
            return

        # Determine which axis is now selected
        if self.main_window.x_axis_btn.isChecked():
            self._selected_axis = "x"
            logger.info("X-axis selected for scaling controls")
        else:
            self._selected_axis = "y"
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

    def _init_kalman_filters(self):
        """Initialize Kalman filter instances for each channel."""
        import os
        import sys

        # Add utils to path
        utils_path = os.path.join(os.path.dirname(__file__), "..")
        if utils_path not in sys.path:
            sys.path.insert(0, utils_path)

        from utils.spr_data_processor import KalmanFilter

        # Map strength to Kalman noise parameters
        # Lower strength = more filtering (higher measurement noise, lower process noise)
        # Higher strength = less filtering (lower measurement noise, higher process noise)
        # Strength 1: R=0.5, Q=0.01 (heavy filtering)
        # Strength 5: R=0.1, Q=0.05 (moderate)
        # Strength 10: R=0.01, Q=0.1 (light filtering)
        measurement_noise = (
            0.5 / self._filter_strength
        )  # Higher strength = trust data more
        process_noise = (
            0.01 * self._filter_strength
        )  # Higher strength = allow more change

        self._kalman_filters = {}
        for ch in self._idx_to_channel:
            self._kalman_filters[ch] = KalmanFilter(
                process_noise=process_noise,
                measurement_noise=measurement_noise,
            )

    def _apply_smoothing(self, data, strength: int):
        """Apply median smoothing filter to data (optimized for SPR).

        Uses median filtering which is robust to outliers and preserves
        sharp features (binding events) better than alternatives.

        Args:
            data: Input data array
            strength: Smoothing strength (1-10)
                     Strength 1 = minimal smoothing (window 3)
                     Strength 10 = maximum smoothing (window 21)

        Returns:
            Smoothed data array

        """
        import numpy as np

        if len(data) < 3:
            return data

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

        # Vectorized median filter for 5-10x speedup over manual loop
        try:
            from scipy.ndimage import median_filter

            # mode='nearest' handles edges by replicating boundary values
            # Preserves NaN handling and matches original behavior
            smoothed = median_filter(data, size=window_size, mode="nearest")
            return smoothed
        except ImportError:
            # Fallback to numpy stride tricks if scipy unavailable
            try:
                from numpy.lib.stride_tricks import sliding_window_view

                # Pad data to handle edges (NumPy 1.20+)
                pad_width = window_size // 2
                padded = np.pad(data, pad_width, mode="edge")
                windows = sliding_window_view(padded, window_size)
                smoothed = np.nanmedian(windows, axis=1)
                return smoothed
            except (ImportError, AttributeError):
                # Final fallback: original loop-based implementation
                half_win = window_size // 2
                smoothed = np.empty(len(data))
                for i in range(len(data)):
                    start_idx = max(0, i - half_win)
                    end_idx = min(len(data), i + half_win + 1)
                    smoothed[i] = np.nanmedian(data[start_idx:end_idx])
                return smoothed

    def _apply_online_smoothing(
        self,
        data: np.ndarray,
        strength: int,
        channel: str,
    ) -> np.ndarray:
        """Apply incremental median filtering for real-time display (optimized for speed).

        Uses online/incremental filtering that only processes recent data window
        instead of refiltering entire timeline on every update.

        Strategy: Filter only recent window (last 200 points) for responsiveness

        Args:
            data: Full timeline data array
            strength: Smoothing strength (1-10)
            channel: Channel identifier (for future stateful optimization)

        Returns:
            Smoothed data array (full length, but efficiently computed)

        """
        import numpy as np

        if len(data) < 3:
            return data

        # Use windowed approach for large datasets
        # Only filter recent portion to maintain responsiveness
        ONLINE_FILTER_WINDOW = 200  # Process last 200 points

        if len(data) <= ONLINE_FILTER_WINDOW:
            # Small dataset, filter everything normally
            return self._apply_smoothing(data, strength)
        # Large dataset: filter only recent window
        # Keep most of timeline unfiltered for speed (preview quality)
        split_point = len(data) - ONLINE_FILTER_WINDOW

        # Create output array
        result = np.copy(data)

        # Filter only the recent window (with small overlap for continuity)
        overlap = 20
        filter_start = max(0, split_point - overlap)
        recent_data = data[filter_start:]
        filtered_recent = self._apply_smoothing(recent_data, strength)

        # Replace recent portion with filtered version
        result[filter_start:] = filtered_recent

        return result

    def _redraw_timeline_graph(self):
        """Redraw the full timeline graph with current filter settings."""
        for ch_letter, ch_idx in self._channel_pairs:
            time_data = self.buffer_mgr.timeline_data[ch_letter].time
            wavelength_data = self.buffer_mgr.timeline_data[ch_letter].wavelength

            if len(time_data) == 0:
                continue

            # Apply smoothing if enabled
            display_data = wavelength_data
            if self._filter_enabled:
                display_data = self._apply_smoothing(
                    wavelength_data,
                    self._filter_strength,
                )

            # Update curve
            curve = self.main_window.full_timeline_graph.curves[ch_idx]
            curve.setData(time_data, display_data)

    def _on_reference_changed(self, text: str):
        """Reference channel selection changed."""
        import pyqtgraph as pg

        # Map selection to channel letter
        channel_map = {
            "None": None,
            "Channel A": "a",
            "Channel B": "b",
            "Channel C": "c",
            "Channel D": "d",
        }

        old_ref = self._reference_channel
        self._reference_channel = channel_map.get(text)

        if self._reference_channel:
            logger.info(f"Reference channel set to: {self._reference_channel.upper()}")
        else:
            logger.info("Reference channel disabled")

        # Reset old reference channel styling
        if old_ref is not None:
            ch_idx = {"a": 0, "b": 1, "c": 2, "d": 3}[old_ref]
            self._reset_channel_style(ch_idx)

        # Apply new reference channel styling
        if self._reference_channel is not None:
            ch_idx = {"a": 0, "b": 1, "c": 2, "d": 3}[self._reference_channel]
            # Purple color with transparency and dashed line
            self.main_window.cycle_of_interest_graph.curves[ch_idx].setPen(
                pg.mkPen(
                    color=(153, 102, 255, 150),
                    width=2,
                    style=pg.QtCore.Qt.PenStyle.DashLine,
                ),
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
        for ch in self._idx_to_channel:
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
        import os
        import sys

        import pyqtgraph as pg

        # Add settings to path if not already there
        settings_path = os.path.join(os.path.dirname(__file__), "..")
        if settings_path not in sys.path:
            sys.path.insert(0, settings_path)

        from settings import settings

        # Determine if colorblind mode is active
        if self.main_window.colorblind_check.isChecked():
            colors = settings.GRAPH_COLORS_COLORBLIND
            ch_letter = ["a", "b", "c", "d"][ch_idx]
            rgb = colors[ch_letter]
            color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        else:
            # Standard colors
            color_list = ["#1D1D1F", "#FF3B30", "#007AFF", "#34C759"]
            color = color_list[ch_idx]

        # Reset to solid line with full opacity
        self.main_window.cycle_of_interest_graph.curves[ch_idx].setPen(
            pg.mkPen(color=color, width=2),
        )

    def _on_graph_clicked(self, event):
        """Handle mouse clicks on cycle_of_interest_graph.

        Left click: Select channel closest to cursor
        Right click: Add flag/annotation at cursor position for selected channel
        """
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QInputDialog

        # Get click position in data coordinates
        pos = event.scenePos()
        mouse_point = (
            self.main_window.cycle_of_interest_graph.getPlotItem().vb.mapSceneToView(
                pos,
            )
        )
        click_time = mouse_point.x()
        click_value = mouse_point.y()

        if event.button() == Qt.MouseButton.LeftButton:
            # Left click: Select nearest channel
            self._select_nearest_channel(click_time, click_value)

        elif event.button() == Qt.MouseButton.RightButton:
            # Right click: Add flag for selected channel
            if self._selected_channel is None:
                logger.warning(
                    "No channel selected. Left-click a channel first to select it.",
                )
                return

            # Prompt user for flag type
            flag_type, ok = QInputDialog.getItem(
                self.main_window,
                "Add Flag",
                f"Select flag type for Channel {chr(65 + self._selected_channel)} at {click_time:.2f}s:",
                ["Inject", "Wash", "Spike"],
                0,
                False,
            )

            if ok:
                self._add_flag(self._selected_channel, click_time, flag_type)

    def _select_nearest_channel(self, click_time: float, click_value: float):
        """Select the channel whose curve is nearest to the click position."""
        import numpy as np

        # Find nearest channel by checking distance to each curve
        min_distance = float("inf")
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
                old_pen = old_curve.opts["pen"]
                old_pen.setWidth(2)  # Normal width
                old_curve.setPen(old_pen)

            new_curve = self.main_window.cycle_of_interest_graph.curves[nearest_channel]
            new_pen = new_curve.opts["pen"]
            new_pen.setWidth(4)  # Thicker for selected
            new_curve.setPen(new_pen)

            logger.info(f"Selected Channel {chr(65 + nearest_channel)}")

    def _add_flag(self, channel: int, time: float, annotation: str):
        """Add a flag marker to the graph and save to table."""
        import pyqtgraph as pg

        # Store flag data
        flag_entry = {
            "channel": channel,
            "time": time,
            "annotation": annotation,
        }
        self._flag_data.append(flag_entry)

        # Get channel color
        curve = self.main_window.cycle_of_interest_graph.curves[channel]
        color = curve.opts["pen"].color()

        # Create flag marker (vertical line with symbol)
        flag_line = pg.InfiniteLine(
            pos=time,
            angle=90,
            pen=pg.mkPen(color=color, width=2, style=pg.QtCore.Qt.PenStyle.DashLine),
            movable=False,
        )

        # Add flag symbol at top
        flag_symbol = pg.ScatterPlotItem(
            [time],
            [self.main_window.cycle_of_interest_graph.getPlotItem().viewRange()[1][1]],
            symbol="t",  # Triangle down (flag shape)
            size=15,
            brush=pg.mkBrush(color),
            pen=pg.mkPen(color=color, width=2),
        )

        # Add to graph
        self.main_window.cycle_of_interest_graph.addItem(flag_line)
        self.main_window.cycle_of_interest_graph.addItem(flag_symbol)

        # Store references
        self.main_window.cycle_of_interest_graph.flag_markers.append(
            {
                "line": flag_line,
                "symbol": flag_symbol,
                "data": flag_entry,
            },
        )

        # Update cycle data table
        self._update_cycle_data_table()

        logger.info(
            f"Added flag for Channel {chr(65 + channel)} at {time:.2f}s: '{annotation}'",
        )

    def _update_cycle_data_table(self):
        """Update the Flags column in cycle data table with flag information."""
        from PySide6.QtWidgets import QTableWidgetItem

        # Build flag summary string for each row (currently just showing all flags)
        # In a real implementation, this would map flags to specific cycles
        flag_summary = "\n".join(
            [
                f"Ch {chr(65 + f['channel'])} @ {f['time']:.1f}s: {f['annotation']}"
                for f in self._flag_data
            ],
        )

        # Update first row's Flags column with all flags
        # (In production, you'd map each flag to its corresponding cycle row)
        if self.main_window.cycle_data_table.rowCount() > 0:
            flags_item = QTableWidgetItem(flag_summary)
            self.main_window.cycle_data_table.setItem(0, 4, flags_item)

    def _on_polarizer_toggle(self):
        """Toggle between S and P polarizer positions."""
        if self.hardware_mgr and self.hardware_mgr.ctrl:
            # Determine current position and toggle
            current_pos = getattr(self.hardware_mgr, "_current_polarizer", "s")
            new_pos = "p" if current_pos == "s" else "s"

            logger.info(
                f"Toggling polarizer from {current_pos.upper()} to {new_pos.upper()}",
            )

            # Set polarizer position
            self.hardware_mgr.ctrl.set_mode(mode=new_pos)
            self.hardware_mgr._current_polarizer = new_pos

            logger.info(f"Polarizer set to {new_pos.upper()}")
        else:
            logger.warning("Hardware not connected - cannot toggle polarizer")

    def _on_apply_settings(self):
        """Apply polarizer positions and LED intensities to hardware.

        Note: Servo positions are saved to device config file (not EEPROM).
        The OEM provides the device config file with factory servo positions,
        which can be updated here as needed.
        """
        try:
            # Get values from inputs
            s_pos = int(self.main_window.s_position_input.text() or "0")
            p_pos = int(self.main_window.p_position_input.text() or "0")
            led_a = int(self.main_window.channel_a_input.text() or "0")
            led_b = int(self.main_window.channel_b_input.text() or "0")
            led_c = int(self.main_window.channel_c_input.text() or "0")
            led_d = int(self.main_window.channel_d_input.text() or "0")

            # Validate ranges
            if not (0 <= s_pos <= 180 and 0 <= p_pos <= 180):
                logger.error("Servo positions must be between 0-180")
                return

            if not all(0 <= val <= 255 for val in [led_a, led_b, led_c, led_d]):
                logger.error("LED intensities must be between 0-255")
                return

            if self.hardware_mgr and self.hardware_mgr.ctrl:
                logger.info(
                    f"Applying settings: S={s_pos}, P={p_pos}, LEDs=[{led_a},{led_b},{led_c},{led_d}]",
                )

                # Set polarizer positions (applies immediately to hardware)
                self.hardware_mgr.ctrl.servo_set(s=s_pos, p=p_pos)

                # Set LED intensities (applies immediately to hardware)
                self.hardware_mgr.ctrl.set_intensity("a", led_a)
                self.hardware_mgr.ctrl.set_intensity("b", led_b)
                self.hardware_mgr.ctrl.set_intensity("c", led_c)
                self.hardware_mgr.ctrl.set_intensity("d", led_d)

                # Save servo positions and LED intensities to device config file
                # The device config file is provided by OEM with factory positions
                if self.main_window.device_config:
                    logger.info("💾 Saving settings to device config file...")
                    self.main_window.device_config.set_servo_positions(s_pos, p_pos)
                    self.main_window.device_config.set_led_intensities(
                        led_a,
                        led_b,
                        led_c,
                        led_d,
                    )
                    self.main_window.device_config.save()
                    logger.info("✅ Settings saved to device config file")
                else:
                    logger.warning("⚠️ Device config not available - settings not saved")

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
            unit = "RU"
        else:
            unit = "nm"

        logger.info(f"Display unit changed to: {unit}")

        # Update graph labels
        if unit == "RU":
            self.main_window.cycle_of_interest_graph.setLabel(
                "left",
                "Δ SPR (RU)",
                color="#86868B",
                size="11pt",
            )
        else:
            self.main_window.cycle_of_interest_graph.setLabel(
                "left",
                "λ (nm)",
                color="#86868B",
                size="11pt",
            )

        # TODO: Trigger data conversion and redraw
        # The conversion factor is approximately: 1 RU ≈ 0.1 nm
        # This should be implemented in the data processing pipeline

    def _on_colorblind_toggled(self, checked: bool):
        """Colorblind-friendly palette toggled."""
        import os
        import sys

        # Add settings to path if not already there
        settings_path = os.path.join(os.path.dirname(__file__), "..")
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
            color_list = ["#1D1D1F", "#FF3B30", "#007AFF", "#34C759"]

        # Update all graph curves on both timeline and cycle graphs
        for i, color in enumerate(color_list):
            import pyqtgraph as pg

            # Update full timeline graph
            if i < len(self.main_window.full_timeline_graph.curves):
                self.main_window.full_timeline_graph.curves[i].setPen(
                    pg.mkPen(color=color, width=2),
                )
            # Update cycle of interest graph
            if i < len(self.main_window.cycle_of_interest_graph.curves):
                self.main_window.cycle_of_interest_graph.curves[i].setPen(
                    pg.mkPen(color=color, width=2),
                )

            # Update channel toggle buttons in graph header
            channel_letters = ["A", "B", "C", "D"]
            if i < len(channel_letters):
                ch = channel_letters[i]
                if ch in self.main_window.channel_toggles:
                    btn = self.main_window.channel_toggles[ch]
                    btn.setStyleSheet(
                        f"QPushButton {{"
                        f"  background: {color};"
                        "  color: white;"
                        "  border: none;"
                        "  border-radius: 6px;"
                        "  font-size: 12px;"
                        "  font-weight: 600;"
                        "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                        "}"
                        "QPushButton:!checked {"
                        "  background: rgba(0, 0, 0, 0.06);"
                        "  color: #86868B;"
                        "}"
                        "QPushButton:hover:!checked {"
                        "  background: rgba(0, 0, 0, 0.1);"
                        "}",
                    )

        logger.info("✅ Graph colors updated successfully")

    def _on_simple_led_calibration(self):
        """Start simple LED intensity calibration (no auto-align)."""
        logger.info("🔧 Starting Simple LED Calibration...")
        # This is the basic calibrate() function
        if hasattr(self.hardware_mgr, "main_app") and self.hardware_mgr.main_app:
            # Disable auto-polarization for simple calibration
            self.hardware_mgr.main_app.auto_polarize = False
            self.hardware_mgr.main_app._c_stop.clear()
            self.hardware_mgr.main_app.calibration_thread = threading.Thread(
                target=self.hardware_mgr.main_app.calibrate,
            )
            self.hardware_mgr.main_app.calibration_thread.start()
        else:
            logger.warning("Hardware not ready for calibration")

    def _on_full_calibration(self):
        """Start full calibration with auto-align and polarizer calibration."""
        logger.info("🔧 Starting Full Calibration (with auto-align)...")
        # This is calibrate() with auto_polarize enabled
        if hasattr(self.hardware_mgr, "main_app") and self.hardware_mgr.main_app:
            # Enable auto-polarization for full calibration
            self.hardware_mgr.main_app.auto_polarize = True
            self.hardware_mgr.main_app._c_stop.clear()
            self.hardware_mgr.main_app.calibration_thread = threading.Thread(
                target=self.hardware_mgr.main_app.calibrate,
            )
            self.hardware_mgr.main_app.calibration_thread.start()
        else:
            logger.warning("Hardware not ready for calibration")

    def _on_oem_led_calibration(self):
        """Start OEM LED calibration with full afterglow measurement."""
        logger.info("🔧 Starting OEM LED Calibration (with afterglow)...")
        # This runs full calibration + afterglow measurement
        if hasattr(self.hardware_mgr, "main_app") and self.hardware_mgr.main_app:
            # Enable auto-polarization
            self.hardware_mgr.main_app.auto_polarize = True
            self.hardware_mgr.main_app._c_stop.clear()

            # Start calibration thread
            self.hardware_mgr.main_app.calibration_thread = threading.Thread(
                target=self.hardware_mgr.main_app.calibrate,
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

            logger.info(
                "✅ Graceful shutdown complete - software ready for offline post-processing",
            )

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
        # Get default filename with timestamp
        import datetime as dt

        from PySide6.QtWidgets import QFileDialog

        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"AffiLabs_data_{timestamp}.csv"

        # Show save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Save Recording As",
            default_filename,
            "CSV Files (*.csv);;All Files (*.*)",
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
        logger.info(
            f"  Spectrometer: {'Connected' if status.get('spectrometer') else 'Not connected'}",
        )
        logger.info(f"  Kinetic: {status.get('knx_type', 'None')}")
        logger.info(
            f"  Pump: {'Connected' if status.get('pump_connected') else 'Not connected'}",
        )
        logger.info(
            f"  Sensor: {'Ready' if status.get('sensor_ready') else 'Not ready'}",
        )
        logger.info(
            f"  Optics: {'Ready' if status.get('optics_ready') else 'Not ready'}",
        )
        logger.info(
            f"  Fluidics: {'Ready' if status.get('fluidics_ready') else 'Not ready'}",
        )

    def _load_device_settings(self):
        """Load servo positions from device config file and populate UI.

        The device config file is provided by OEM with factory-calibrated servo positions.
        This replaces reading from EEPROM since the config file is the source of truth.
        """
        if not self.hardware_mgr or not self.hardware_mgr.ctrl:
            logger.warning("Cannot load settings - hardware not connected")
            return

        try:
            logger.info("📖 Loading servo positions from device config file...")

            # Load servo positions from device config file (not EEPROM)
            if self.main_window.device_config:
                servo_positions = self.main_window.device_config.get_servo_positions()
                s_pos = servo_positions["s"]
                p_pos = servo_positions["p"]

                # Update UI inputs with loaded values
                self.main_window.s_position_input.setText(str(s_pos))
                self.main_window.p_position_input.setText(str(p_pos))

                # Apply servo positions to hardware
                self.hardware_mgr.ctrl.servo_set(s=s_pos, p=p_pos)

                logger.info(
                    f"  ✅ Servo positions loaded from device config: S={s_pos}, P={p_pos}",
                )
            else:
                logger.warning(
                    "  ⚠️ Device config not available - cannot load servo positions",
                )

            # Load LED intensities from device config (for fast startup)
            if self.main_window.device_config:
                led_intensities = self.main_window.device_config.get_led_intensities()
                led_a = led_intensities["a"]
                led_b = led_intensities["b"]
                led_c = led_intensities["c"]
                led_d = led_intensities["d"]

                # Update UI inputs
                self.main_window.channel_a_input.setText(str(led_a))
                self.main_window.channel_b_input.setText(str(led_b))
                self.main_window.channel_c_input.setText(str(led_c))
                self.main_window.channel_d_input.setText(str(led_d))

                # Apply to hardware for fast startup
                if led_a > 0 or led_b > 0 or led_c > 0 or led_d > 0:
                    self.hardware_mgr.ctrl.set_intensity("a", led_a)
                    self.hardware_mgr.ctrl.set_intensity("b", led_b)
                    self.hardware_mgr.ctrl.set_intensity("c", led_c)
                    self.hardware_mgr.ctrl.set_intensity("d", led_d)
                    logger.info(
                        f"  ✅ LED intensities loaded from device config: A={led_a}, B={led_b}, C={led_c}, D={led_d}",
                    )
                else:
                    logger.info(
                        "  ℹ️  No calibrated LED intensities in device config - will calibrate on startup",
                    )

        except Exception as e:
            logger.error(f"Failed to load device settings: {e}")
            logger.debug("Settings load error details:", exc_info=True)

    def _update_led_intensities_in_ui(self):
        """Update UI with calibrated LED intensities after calibration completes."""
        if (
            not hasattr(self.data_mgr, "leds_calibrated")
            or not self.data_mgr.leds_calibrated
        ):
            logger.debug("No calibrated LED intensities available to update UI")
            return

        try:
            led_a = self.data_mgr.leds_calibrated.get("a", 0)
            led_b = self.data_mgr.leds_calibrated.get("b", 0)
            led_c = self.data_mgr.leds_calibrated.get("c", 0)
            led_d = self.data_mgr.leds_calibrated.get("d", 0)

            self.main_window.channel_a_input.setText(str(led_a))
            self.main_window.channel_b_input.setText(str(led_b))
            self.main_window.channel_c_input.setText(str(led_c))
            self.main_window.channel_d_input.setText(str(led_d))

            logger.info(
                f"📝 LED intensities updated in UI: A={led_a}, B={led_b}, C={led_c}, D={led_d}",
            )

        except Exception as e:
            logger.error(f"Failed to update LED intensities in UI: {e}")

    def _on_quick_export_csv(self):
        """Quick export cycle of interest data to CSV file."""
        import datetime as dt

        from PySide6.QtWidgets import QFileDialog

        try:
            # Get cursor positions
            start_time = self.main_window.full_timeline_graph.start_cursor.value()
            stop_time = self.main_window.full_timeline_graph.stop_cursor.value()

            # Check if there's data to export
            has_data = False
            for ch in self._idx_to_channel:
                if len(self.buffer_mgr.cycle_data[ch].time) > 0:
                    has_data = True
                    break

            if not has_data:
                from widgets.message import show_message

                show_message("No cycle data to export", "Warning")
                return

            # Generate default filename
            timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"Cycle_Export_{timestamp}.csv"

            # Show save dialog
            file_path, _ = QFileDialog.getSaveFileName(
                self.main_window,
                "Export Cycle Data",
                default_filename,
                "CSV Files (*.csv);;All Files (*.*)",
            )

            if not file_path:
                return  # User cancelled

            # Collect cycle data for all channels
            export_data = {}
            for ch in self._idx_to_channel:
                cycle_time = self.buffer_mgr.cycle_data[ch].time
                delta_spr = self.buffer_mgr.cycle_data[ch].spr

                if len(cycle_time) > 0:
                    export_data[ch] = {
                        "time": cycle_time.copy(),
                        "spr": delta_spr.copy(),
                    }

            # Vectorized export using pandas DataFrame for better performance
            import pandas as pd

            # Build DataFrame with time column from first available channel
            first_ch = list(export_data.keys())[0]
            df_data = {"Time (s)": export_data[first_ch]["time"]}

            # Add SPR columns for all channels
            for ch in self._idx_to_channel:
                if ch in export_data:
                    # Align all channels to same length (pandas handles this automatically)
                    df_data[f"Channel_{ch.upper()}_SPR (RU)"] = export_data[ch]["spr"]

            df = pd.DataFrame(df_data)

            # Write to CSV with metadata header
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                # Write metadata
                f.write("# AffiLabs Cycle Export\n")
                f.write(
                    f'# Export Date,{dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n',
                )
                f.write(f"# Start Time (s),{start_time:.2f}\n")
                f.write(f"# Stop Time (s),{stop_time:.2f}\n")
                f.write(f"# Duration (s),{stop_time - start_time:.2f}\n")
                f.write("\n")

                # Write DataFrame (vectorized, much faster than manual loops)
                df.to_csv(f, index=False, float_format="%.4f")

            logger.info(f"✅ Cycle data exported to: {file_path}")
            from widgets.message import show_message

            show_message(
                f"Cycle exported successfully!\n{Path(file_path).name}",
                "Information",
            )

        except Exception as e:
            logger.exception(f"Failed to export cycle CSV: {e}")
            from widgets.message import show_message

            show_message(f"Export failed: {e}", "Error")

    def _autosave_cycle_data(self, start_time: float, stop_time: float):
        """Automatically save cycle data to session folder.

        Creates timestamped cycle exports for later analysis.
        Users can review these without cluttering the live view.
        """
        from datetime import datetime

        try:
            # Create cycles subfolder in session directory
            if (
                not hasattr(self, "_session_cycles_dir")
                or self._session_cycles_dir is None
            ):
                if (
                    self.recording_mgr
                    and hasattr(self.recording_mgr, "current_session_dir")
                    and self.recording_mgr.current_session_dir is not None
                ):
                    session_dir = Path(self.recording_mgr.current_session_dir)
                    self._session_cycles_dir = session_dir / "cycles"
                else:
                    # Use data folder if no active session
                    session_dir = (
                        Path("data") / "cycles" / datetime.now().strftime("%Y%m%d")
                    )
                    self._session_cycles_dir = session_dir

                self._session_cycles_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp and cycle bounds
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"cycle_{timestamp}_t{start_time:.1f}-{stop_time:.1f}s.csv"
            filepath = self._session_cycles_dir / filename

            # Determine which channels have data
            active_channels = []
            for ch in self._idx_to_channel:
                if len(self.buffer_mgr.cycle_data[ch].time) > 0:
                    active_channels.append(ch)

            if not active_channels:
                return

            # Vectorized export using pandas DataFrame
            import pandas as pd

            # Build DataFrame with time and wavelength/SPR for each channel
            first_ch = active_channels[0]
            df_data = {"Time (s)": self.buffer_mgr.cycle_data[first_ch].time}

            for ch in active_channels:
                df_data[f"Ch {ch.upper()} Wavelength (nm)"] = (
                    self.buffer_mgr.cycle_data[ch].wavelength
                )
                df_data[f"Ch {ch.upper()} SPR (RU)"] = self.buffer_mgr.cycle_data[
                    ch
                ].spr

            df = pd.DataFrame(df_data)

            # Write to CSV with metadata
            with open(filepath, "w", newline="") as f:
                # Write metadata
                f.write("# AffiLabs Cycle Autosave\n")
                f.write(f"# Timestamp,{datetime.now().isoformat()}\n")
                f.write(f"# Cycle Start,{start_time:.3f} s\n")
                f.write(f"# Cycle Stop,{stop_time:.3f} s\n")
                f.write(f"# Duration,{stop_time - start_time:.3f} s\n")
                f.write(f"# Filter Enabled,{self._filter_enabled!s}\n")
                if self._filter_enabled:
                    f.write(f"# Filter Strength,{self._filter_strength!s}\n")
                f.write(f"# Reference Subtraction,{self._ref_subtraction_enabled!s}\n")
                if self._ref_subtraction_enabled:
                    f.write(f"# Reference Channel,{self._ref_channel}\n")
                f.write("\n")

                # Write DataFrame (vectorized)
                df.to_csv(f, index=False, float_format="%.4f")

            logger.info(
                f"💾 Cycle autosaved: {filename} ({len(active_channels)} channels, {len(df)} points)",
            )

        except Exception as e:
            logger.debug(f"Cycle autosave failed: {e}")

    def _on_quick_export_image(self):
        """Quick export cycle of interest graph as image with metadata."""
        import datetime as dt

        from PySide6.QtCore import QRectF, Qt
        from PySide6.QtGui import QFont, QImage, QPainter, QPen
        from PySide6.QtWidgets import QFileDialog

        try:
            # Check if there's data to export
            has_data = False
            for ch in self._idx_to_channel:
                if len(self.buffer_mgr.cycle_data[ch].time) > 0:
                    has_data = True
                    break

            if not has_data:
                from widgets.message import show_message

                show_message("No cycle data to export", "Warning")
                return

            # Generate default filename
            timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"Cycle_Graph_{timestamp}.png"

            # Show save dialog
            file_path, _ = QFileDialog.getSaveFileName(
                self.main_window,
                "Export Graph Image",
                default_filename,
                "PNG Images (*.png);;JPEG Images (*.jpg);;All Files (*.*)",
            )

            if not file_path:
                return  # User cancelled

            # Get graph widget
            graph_widget = self.main_window.cycle_of_interest_graph

            # Export graph to image
            exporter = graph_widget.getPlotItem().scene().views()[0]

            # Get cursor positions for metadata
            start_time = self.main_window.full_timeline_graph.start_cursor.value()
            stop_time = self.main_window.full_timeline_graph.stop_cursor.value()

            # Create image with extra space for metadata
            graph_rect = exporter.viewport().rect()
            metadata_height = 100
            total_width = graph_rect.width()
            total_height = graph_rect.height() + metadata_height

            image = QImage(total_width, total_height, QImage.Format_ARGB32)
            image.fill(Qt.white)

            # Render graph to image
            painter = QPainter(image)
            exporter.render(
                painter,
                target=QRectF(0, 0, total_width, graph_rect.height()),
            )

            # Add metadata text below graph
            painter.setFont(QFont("Arial", 9))
            painter.setPen(QPen(Qt.black))

            y_offset = graph_rect.height() + 15
            line_height = 15

            # Metadata lines
            metadata_lines = [
                f"AffiLabs Cycle of Interest - Exported: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Time Range: {start_time:.2f}s - {stop_time:.2f}s  |  Duration: {stop_time - start_time:.2f}s",
                "Channels: A (Red), B (Green), C (Blue), D (Purple)  |  Unit: Response Units (RU)",
            ]

            for i, line in enumerate(metadata_lines):
                painter.drawText(10, y_offset + (i * line_height), line)

            painter.end()

            # Save image
            image.save(file_path)

            logger.info(f"✅ Graph image exported to: {file_path}")
            from widgets.message import show_message

            show_message(
                f"Graph exported successfully!\n{Path(file_path).name}",
                "Information",
            )

        except Exception as e:
            logger.exception(f"Failed to export graph image: {e}")
            from widgets.message import show_message

            show_message(f"Export failed: {e}", "Error")

    def _print_profiling_stats(self):
        """Print profiling statistics (called periodically by timer)."""
        if PROFILING_ENABLED:
            logger.info("\n⏱️ PERIODIC PROFILING SNAPSHOT:")
            self.profiler.print_stats(sort_by="total", min_calls=10)
            logger.info("")


def main():
    """Launch the application with modern UI."""
    dtnow = dt.datetime.now(TIME_ZONE)
    logger.info("=" * 70)
    logger.info("AffiLabs.core - Surface Plasmon Resonance Analysis")
    logger.info(f"{SW_VERSION} | {dtnow.strftime('%Y-%m-%d %H:%M')}")
    logger.info("=" * 70)

    # Create and run application
    app = Application(sys.argv)

    logger.info("🚀 Starting event loop...")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
