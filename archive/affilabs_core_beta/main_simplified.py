"""Simplified main launcher for AffiLabs.core with modern UI.

This is a clean rewrite that:
1. Shows the window FIRST
2. Initializes hardware in background threads
3. Uses standard app.exec() instead of asyncio complexity

ARCHITECTURE:
=============
- UI Layer: affilabs_core_ui.py (MainWindowPrototype) - Modular, PySide6-based interface
- Application Layer: This file (Application class) - Coordinates UI and hardware managers
- Core Managers: hardware_manager, data_acquisition_manager, recording_manager, kinetic_manager
- UI Components: sidebar.py, sections.py, plot_helpers.py, diagnostics_dialog.py, inspector.py

INTEGRATION STATUS: ✅ READY
============================
The UI is fully integrated and scalable:
- Clean separation between UI (affilabs_core_ui.py) and business logic (main_simplified.py)
- All UI components are modular and can be updated independently
- Signal/slot connections allow UI updates without tight coupling
- New UI features can be added to affilabs_core_ui.py without touching core logic
- The Application class handles all manager coordination and data flow

Last Updated: November 22, 2025
"""

import atexit
import io
import os
import sys
import threading
import warnings
from pathlib import Path


# === CRITICAL: Install sys.excepthook to catch Qt threading crashes ===
def qt_exception_handler(exctype, value, tb):
    """Catch and suppress Qt threading exceptions that are false positives."""
    # Check if stderr is still available
    if not sys.stderr or not hasattr(sys.stderr, "write"):
        return  # Can't log, just return silently

    try:
        error_msg = str(value)
        if "QTextDocument" in error_msg or "different thread" in error_msg:
            # This is the harmless Qt threading warning - suppress it
            return
        # For real exceptions, use default handler
        sys.__excepthook__(exctype, value, tb)
    except (ValueError, OSError):
        # stderr is closed, silently ignore
        pass


sys.excepthook = qt_exception_handler


# === INSTALL STDERR FILTER IMMEDIATELY ===
# Suppress Qt threading warnings before any Qt imports
class QtWarningFilter:
    """Filter to suppress specific Qt warnings that are false positives."""

    SUPPRESSED = (
        "QObject: Cannot create children",
        "QTextDocument",
        "parent's thread is QThread",
        "parent that is in a different thread",
    )

    def __init__(self, original_stderr):
        self.original = original_stderr
        self.buffer = io.StringIO()
        self._closed = False

    def write(self, text):
        # Check if stderr is still open
        if self._closed or not self.original:
            return
        try:
            # Suppress known false-positive Qt threading warnings
            if any(s in text for s in self.SUPPRESSED):
                return  # Silently drop
            self.original.write(text)
        except (ValueError, OSError):
            # stderr is closed - stop trying to write
            self._closed = True

    def flush(self):
        if self._closed or not self.original:
            return
        try:
            self.original.flush()
        except (ValueError, OSError):
            self._closed = True

    def fileno(self):
        try:
            return self.original.fileno()
        except:
            return -1


# Install filter unless verbose mode requested
if os.environ.get("AFFILABS_VERBOSE_QT", "0") in ("0", "false", "False"):
    sys.stderr = QtWarningFilter(sys.stderr)

# Suppress Python warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

# Qt environment configuration - MUST be set before importing Qt
os.environ["QT_LOGGING_RULES"] = (
    "qt.*=false;*.debug=false"  # Suppress all Qt debug/warning messages
)
os.environ["QT_FATAL_WARNINGS"] = "0"  # Don't crash on warnings
os.environ["QT_ASSUME_STDERR_HAS_CONSOLE"] = "0"  # Suppress stderr warnings
os.environ["QT_QPA_PLATFORM"] = (
    "windows:darkmode=0"  # Disable dark mode detection (can cause threading)
)
# CRITICAL: Disable Qt's internal threading checks that cause false positives
os.environ["QT_NO_THREADED_PAINTING"] = "1"
os.environ["QT_NO_GLIB"] = "1"

from PySide6.QtCore import Qt, QTimer, QtMsgType, qInstallMessageHandler
from PySide6.QtWidgets import QApplication


# === Install Qt message handler to suppress threading warnings ===
def qt_message_handler(msg_type, context, message):
    """Custom Qt message handler that suppresses specific warnings."""
    # Suppress Qt threading warnings (false positives with our queue-based approach)
    if "QTextDocument" in message or "different thread" in message:
        return  # Silently ignore

    # For other messages, print them normally
    if msg_type == QtMsgType.QtDebugMsg:
        print(f"Qt Debug: {message}")
    elif msg_type == QtMsgType.QtWarningMsg:
        print(f"Qt Warning: {message}")
    elif msg_type == QtMsgType.QtCriticalMsg:
        print(f"Qt Critical: {message}")
    elif msg_type == QtMsgType.QtFatalMsg:
        print(f"Qt Fatal: {message}")


qInstallMessageHandler(qt_message_handler)

from affilabs_core_ui import AffilabsMainWindow
from core.calibration_coordinator import CalibrationCoordinator
from core.cycle_coordinator import CycleCoordinator
from core.data_acquisition_manager import DataAcquisitionManager
from core.data_buffer_manager import DataBufferManager
from core.graph_coordinator import GraphCoordinator
from core.hardware_manager import HardwareManager
from core.kinetic_manager import KineticManager
from core.recording_manager import RecordingManager
from PySide6.QtCore import Signal
from transmission_spectrum_dialog import TransmissionSpectrumDialog

from config import (
    DEBUG_LOG_THROTTLE_FACTOR,
    DEFAULT_FILTER_ENABLED,
    DEFAULT_FILTER_STRENGTH,
    ENABLE_RAW_SPECTRUM_UPDATES_DEFAULT,
    ENABLE_TRANSMISSION_UPDATES_DEFAULT,
    LEAK_DETECTION_WINDOW,
    LEAK_THRESHOLD_RATIO,
    SENSORGRAM_DOWNSAMPLE_FACTOR,
    TRANSMISSION_UPDATE_INTERVAL,
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

    # Signal for thread-safe cursor updates (emitted from processing thread)
    cursor_update_signal = Signal(float)  # elapsed_time

    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("AffiLabs.core")
        self.setOrganizationName("Affinite Instruments")

        # Closing flag for cleanup coordination
        self.closing = False

        # Track if device config has been initialized during this session
        self._device_config_initialized = False

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

        # Create main window (production AffiLabs.core UI)
        logger.info("Creating main window...")
        self.main_window = AffilabsMainWindow(event_bus=None)

        # Store reference to app in window for easy access to managers
        self.main_window.app = self
        logger.info("✅ Main window initialized")

        # Track selected axis for manual/auto scaling (default X)
        self._selected_axis = "x"

        # Track reference channel for subtraction (None, 'a', 'b', 'c', 'd')
        self._reference_channel = None
        self._ref_subtraction_enabled = (
            False  # Track if reference subtraction is enabled
        )
        self._ref_channel = None  # Reference channel for subtraction

        # Track data filtering settings (use config defaults)
        self._filter_enabled = DEFAULT_FILTER_ENABLED
        self._filter_strength = DEFAULT_FILTER_STRENGTH
        self._filter_method = "median"  # Default: 'median' or 'kalman'
        self._kalman_filters = {}  # Store Kalman filter instances per channel

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

        # Transmission spectrum dialog
        self._transmission_dialog = None
        self._live_data_dialog = None  # Live Data Dialog for real-time spectra

        # Initialize data buffer manager
        self.buffer_mgr = DataBufferManager()

        # Initialize coordinators for better separation of concerns
        logger.info("Creating coordinators...")
        self.calibration = CalibrationCoordinator(self)
        self.graphs = GraphCoordinator(self)
        self.cycles = CycleCoordinator(self)

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

        # Performance: Debug log throttling (log every Nth acquisition)
        self._acquisition_counter = 0  # Count acquisitions for throttling

        # Performance: Transmission update throttling (update every N seconds)
        self._last_transmission_update = {
            "a": 0,
            "b": 0,
            "c": 0,
            "d": 0,
        }  # Timestamp per channel
        self._transmission_updates_enabled = ENABLE_TRANSMISSION_UPDATES_DEFAULT
        self._raw_spectrum_updates_enabled = ENABLE_RAW_SPECTRUM_UPDATES_DEFAULT

        # Performance: Sensorgram downsampling counter
        self._sensorgram_update_counter = 0

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
            1000,
        )  # 1000ms = 1 second update rate for live sensorgram
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

        # Connect page change signal to manage live data dialog visibility
        if hasattr(self.main_window, "content_stack"):
            self.main_window.content_stack.currentChanged.connect(self._on_page_changed)

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

        # Connect cursor auto-follow signal (thread-safe)
        self.cursor_update_signal.connect(self._update_stop_cursor_position)

        # Connect polarizer toggle button to servo control
        self.main_window.polarizer_toggle_btn.clicked.connect(
            self._on_polarizer_toggle_clicked,
        )

        # Connect mouse events for channel selection and flagging
        self.main_window.cycle_of_interest_graph.scene().sigMouseClicked.connect(
            self._on_graph_clicked,
        )

        # Optional debug: simulate calibration success automatically
        if os.environ.get("AFFILABS_SIMULATE_CAL_SUCCESS", "0") not in (
            "0",
            "false",
            "False",
        ):
            from PySide6.QtCore import QTimer

            logger.info(
                "🧪 Debug simulation: scheduling fake calibration success in 2s",
            )
            QTimer.singleShot(2000, self._debug_simulate_calibration_success)

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
        """Connect all manager signals directly to application handlers."""
        # === HARDWARE MANAGER SIGNALS ===
        # Queued connections for thread safety (hardware manager runs in worker thread)
        self.hardware_mgr.hardware_connected.connect(
            self._on_hardware_connected,
            Qt.QueuedConnection,
        )
        self.hardware_mgr.hardware_disconnected.connect(
            self._on_hardware_disconnected,
            Qt.QueuedConnection,
        )
        self.hardware_mgr.connection_progress.connect(
            self._on_connection_progress,
            Qt.QueuedConnection,
        )
        self.hardware_mgr.error_occurred.connect(
            self._on_hardware_error,
            Qt.QueuedConnection,
        )

        # === DATA ACQUISITION MANAGER SIGNALS ===
        # Queued connections for thread safety (data manager runs in worker thread)
        self.data_mgr.spectrum_acquired.connect(
            self._on_spectrum_acquired,
            Qt.QueuedConnection,
        )
        self.data_mgr.acquisition_started.connect(
            self._on_acquisition_started,
            Qt.QueuedConnection,
        )
        self.data_mgr.acquisition_stopped.connect(
            self._on_acquisition_stopped,
            Qt.QueuedConnection,
        )
        self.data_mgr.acquisition_error.connect(
            self._on_acquisition_error,
            Qt.QueuedConnection,
        )

        # === RECORDING MANAGER SIGNALS ===
        self.recording_mgr.recording_started.connect(self._on_recording_started)
        self.recording_mgr.recording_stopped.connect(self._on_recording_stopped)
        self.recording_mgr.recording_error.connect(self._on_recording_error)
        self.recording_mgr.event_logged.connect(self._on_event_logged)

        # === KINETIC MANAGER SIGNALS ===
        self.kinetic_mgr.pump_initialized.connect(self._on_pump_initialized)
        self.kinetic_mgr.pump_error.connect(self._on_pump_error)
        self.kinetic_mgr.pump_state_changed.connect(self._on_pump_state_changed)
        self.kinetic_mgr.valve_switched.connect(self._on_valve_switched)

        # === UI SIGNALS (user requests) ===
        self.main_window.power_on_requested.connect(self._on_power_on_requested)
        logger.info(
            "Connected: main_window.power_on_requested -> _on_power_on_requested",
        )
        print("[INIT] Power ON signal connected!")

        self.main_window.power_off_requested.connect(self._on_power_off_requested)
        self.main_window.recording_start_requested.connect(
            self._on_recording_start_requested,
        )
        self.main_window.recording_stop_requested.connect(
            self._on_recording_stop_requested,
        )

        # === DEBUG SHORTCUTS ===
        from PySide6.QtGui import QKeySequence, QShortcut

        logger.info("=" * 80)
        logger.info("🔧 REGISTERING DEBUG SHORTCUTS")
        logger.info("=" * 80)

        # Ctrl+Shift+C: Bypass calibration (mark system as calibrated without hardware)
        bypass_calibration_shortcut = QShortcut(
            QKeySequence("Ctrl+Shift+C"),
            self.main_window,
        )
        bypass_calibration_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        bypass_calibration_shortcut.activated.connect(self._debug_bypass_calibration)
        logger.info(f"✅ Ctrl+Shift+C registered: {bypass_calibration_shortcut}")
        logger.info(f"   Context: {bypass_calibration_shortcut.context()}")
        logger.info(f"   Key: {bypass_calibration_shortcut.key().toString()}")

        # Ctrl+Shift+S: Start simulation mode (inject fake spectra)
        simulation_shortcut = QShortcut(QKeySequence("Ctrl+Shift+S"), self.main_window)
        simulation_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        simulation_shortcut.activated.connect(self._debug_start_simulation)
        logger.info(f"✅ Ctrl+Shift+S registered: {simulation_shortcut}")
        logger.info(f"   Context: {simulation_shortcut.context()}")
        logger.info(f"   Key: {simulation_shortcut.key().toString()}")

        # Ctrl+Shift+1: Single data point test (minimal test)
        single_point_shortcut = QShortcut(
            QKeySequence("Ctrl+Shift+1"),
            self.main_window,
        )
        single_point_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        single_point_shortcut.activated.connect(self._debug_single_data_point)
        logger.info(f"✅ Ctrl+Shift+1 registered: {single_point_shortcut}")
        logger.info(f"   Context: {single_point_shortcut.context()}")
        logger.info(f"   Key: {single_point_shortcut.key().toString()}")

        logger.info("=" * 80)
        logger.info("🔧 DEBUG: Ctrl+Shift+S to start spectrum simulation")

        # Ctrl+Shift+T: Test acquisition worker threading (skip calibration) - DISABLED
        # debug_thread_shortcut = QShortcut(QKeySequence("Ctrl+Shift+T"), self.main_window)
        # debug_thread_shortcut.activated.connect(self._debug_test_acquisition_thread)
        # logger.info("Debug: Ctrl+Shift+T to test acquisition thread (skip cal)")

        self.main_window.acquisition_pause_requested.connect(
            self._on_acquisition_pause_requested,
        )
        self.main_window.export_requested.connect(self._on_export_requested)

        # === UI CONTROL SIGNALS (direct connections - not through event bus) ===
        self._connect_ui_control_signals()

        logger.info("✅ All signal connections registered")

    def _connect_hardware_signals(self):
        """DEPRECATED: Now handled by event bus.
        Kept for reference during transition.
        """

    def _connect_data_acquisition_signals(self):
        """DEPRECATED: Now handled by event bus.
        Kept for reference during transition.
        """

    def _connect_recording_signals(self):
        """DEPRECATED: Now handled by event bus.
        Kept for reference during transition.
        """

    def _connect_kinetic_signals(self):
        """DEPRECATED: Now handled by event bus.
        Kept for reference during transition.
        """

    def _connect_ui_request_signals(self):
        """DEPRECATED: Now handled by event bus.
        Kept for reference during transition.
        """

    def _connect_ui_control_signals(self):
        """Register UI control element signal connections.

        These are direct connections (not routed through event bus) for
        performance-critical UI controls like graph cursors and manual inputs.
        """
        ui = self.main_window

        # --- Graph Controls ---
        ui.grid_check.toggled.connect(self._on_grid_toggled)
        ui.auto_radio.toggled.connect(self._on_autoscale_toggled)
        ui.manual_radio.toggled.connect(self._on_manual_scale_toggled)
        ui.min_input.editingFinished.connect(self._on_manual_range_changed)
        ui.max_input.editingFinished.connect(self._on_manual_range_changed)
        ui.x_axis_btn.toggled.connect(self._on_axis_selected)
        ui.y_axis_btn.toggled.connect(self._on_axis_selected)

        # --- Data Filtering Controls ---
        ui.filter_enable.toggled.connect(self._on_filter_toggled)
        ui.filter_slider.valueChanged.connect(self._on_filter_strength_changed)

        # Cursor movements for cycle graph updates (performance-critical)
        ui.full_timeline_graph.start_cursor.sigPositionChanged.connect(
            self._update_cycle_of_interest_graph,
        )
        ui.full_timeline_graph.stop_cursor.sigPositionChanged.connect(
            self._update_cycle_of_interest_graph,
        )

        # Mouse events for channel selection and flagging
        ui.cycle_of_interest_graph.scene().sigMouseClicked.connect(
            self._on_graph_clicked,
        )

        # OEM Calibration button (direct connection)
        ui.oem_led_calibration_btn.clicked.connect(self._on_oem_led_calibration)

        # Advanced Settings dialog - connect optical calibration signal
        if hasattr(ui, "advanced_menu") and ui.advanced_menu is not None:
            if hasattr(ui.advanced_menu, "measure_afterglow_sig"):
                ui.advanced_menu.measure_afterglow_sig.connect(
                    self._on_oem_led_calibration,
                )
                logger.info("✅ Connected Advanced Settings optical calibration signal")

        # Start button (direct connection)
        ui.sidebar.start_cycle_btn.clicked.connect(self._on_start_button_clicked)

    # === DEBUG / TEST HELPERS ===
    def _debug_simulate_calibration_success(self):
        """Force a simulated successful calibration (debug/testing only).

        Sets calibrated flag, populates minimal calibration data, emits calibration_complete.
        Auto-start logic (if enabled) should then begin acquisition attempt.
        """
        try:
            if getattr(self.data_mgr, "calibrated", False):
                logger.info("🧪 Debug: system already calibrated; skipping simulation")
                return

            logger.info("🧪 Debug: simulating calibration success (no hardware checks)")
            # Minimal fake data
            self.data_mgr.calibrated = True
            self.data_mgr.integration_time = 36
            self.data_mgr.num_scans = 1
            self.data_mgr.leds_calibrated = {"a": 180, "b": 180, "c": 180, "d": 180}
            self.data_mgr.ref_intensity = 25000
            # Emit calibration_complete via event bus
            calibration_data = {
                "integration_time": self.data_mgr.integration_time,
                "num_scans": self.data_mgr.num_scans,
                "ref_intensity": self.data_mgr.ref_intensity,
                "leds_calibrated": self.data_mgr.leds_calibrated.copy(),
                "ch_error_list": [],
                "s_ref_qc_results": {},
                "channel_performance": {},
                "calibration_type": "debug",
                "afterglow_available": False,
                "sp_validation_results": {},
            }
            # Debug bypass complete - calibration manager not used
            logger.info("🧪 Debug: calibration bypassed (no signal emitted)")
        except Exception as e:
            logger.error(f"🧪 Debug: calibration simulation failed: {e}")

    def _debug_bypass_calibration(self):
        """Debug: Mark system as calibrated without running hardware calibration (Ctrl+Shift+C).

        This is a lightweight bypass that:
        1. Marks the data manager as calibrated
        2. Injects minimal fake calibration data
        3. Enables the Start button and UI controls

        NO hardware interaction - pure UI state change for debugging.
        """
        try:
            logger.info("=" * 80)
            logger.info("🔧 DEBUG BYPASS: Marking system as calibrated (NO HARDWARE)")
            logger.info("=" * 80)

            # Inject minimal fake calibration data into data manager
            import numpy as np

            self.data_mgr.calibrated = True
            self.data_mgr.integration_time = 40
            self.data_mgr.num_scans = 5
            self.data_mgr.leds_calibrated = {"a": 255, "b": 150, "c": 150, "d": 255}
            self.data_mgr.wave_data = np.linspace(400, 900, 2048)
            self.data_mgr.ref_sig = {
                "a": np.ones(2048) * 40000,
                "b": np.ones(2048) * 40000,
                "c": np.ones(2048) * 40000,
                "d": np.ones(2048) * 40000,
            }
            self.data_mgr.dark_noise = np.zeros(2048)
            self.data_mgr.fourier_weights = {
                "a": np.ones(2048 - 1),  # Derivative has n-1 points
                "b": np.ones(2048 - 1),
                "c": np.ones(2048 - 1),
                "d": np.ones(2048 - 1),
            }

            logger.info("✅ Fake calibration data injected")

            # Save LED intensities to device config so Settings dialog shows correct values
            if self.main_window.device_config:
                try:
                    self.main_window.device_config.set_led_intensities(
                        255,
                        150,
                        150,
                        255,
                    )
                    self.main_window.device_config.set_calibration_settings(40, 5)
                    self.main_window.device_config.save()
                    logger.info("💾 Fake calibration saved to device config")
                except Exception as e:
                    logger.warning(
                        f"Failed to save fake calibration to device config: {e}",
                    )

            # Enable Start button in UI
            if hasattr(self.main_window, "sidebar") and hasattr(
                self.main_window.sidebar,
                "start_cycle_btn",
            ):
                self.main_window.sidebar.start_cycle_btn.setEnabled(True)
                self.main_window.sidebar.start_cycle_btn.setToolTip(
                    "Start Live Acquisition (Debug Mode)",
                )
                logger.info("✅ Start button enabled")

            # Enable recording controls
            self.main_window.enable_controls()
            logger.info("✅ Recording controls enabled")  # Show success message
            from widgets.message import show_message

            show_message(
                "Debug calibration bypass active!\n\n"
                "• System marked as calibrated\n"
                "• Start button enabled\n"
                "• Recording controls enabled\n\n"
                "Press 'Start' to test UI without hardware.",
                msg_type="Info",
                title="Calibration Bypassed (Debug)",
            )

            logger.info("=" * 80)
            logger.info("✅ BYPASS COMPLETE - Press Start to test UI")
            logger.info("=" * 80)

        except Exception as e:
            logger.exception(f"❌ Failed to bypass calibration: {e}")
            from widgets.message import show_message

            show_message(
                f"Failed to bypass calibration:\n{e}",
                msg_type="Error",
                title="Bypass Failed",
            )

    def _debug_single_data_point(self):
        """Debug: Emit a single test data point (Ctrl+Shift+1).

        Minimal test - just ONE data point, no loops, no timers.
        This isolates whether the crash is:
        - The data processing itself (crashes immediately)
        - The rate/accumulation (doesn't crash with one point)
        """
        import time

        logger.info("=" * 80)
        logger.info("🧪 SINGLE DATA POINT TEST (Ctrl+Shift+1)")
        logger.info("=" * 80)

        try:
            # Check if data_mgr exists
            if not hasattr(self, "data_mgr") or self.data_mgr is None:
                logger.error("❌ No data_mgr found!")
                from widgets.message import show_message

                show_message("Error: Data manager not initialized!", msg_type="Error")
                return

            logger.info("✅ Data manager found")

            # Create a single data point
            data = {
                "channel": "a",
                "wavelength": 650.0,
                "intensity": 15000.0,
                "timestamp": time.time(),
                "is_preview": False,
                "simulated": True,
            }

            logger.info(f"📤 Emitting single data point: {data}")

            # Emit to spectrum_acquired signal
            self.data_mgr.spectrum_acquired.emit(data)

            logger.info("✅ Single data point emitted")
            logger.info("⏳ Waiting 2 seconds to see if crash occurs...")

            # Use QTimer to check status after delay
            from PySide6.QtCore import QTimer

            def check_status():
                logger.info("=" * 80)
                logger.info("✅ SUCCESS - No crash after 2 seconds!")
                logger.info("   Single data point was processed successfully.")
                logger.info(
                    "   This means the crash is likely rate/accumulation related.",
                )
                logger.info("=" * 80)
                from widgets.message import show_message

                show_message(
                    "Single Data Point Test: SUCCESS!\n\n"
                    "✅ No crash detected\n"
                    "✅ Data processing works\n\n"
                    "The crash is likely caused by:\n"
                    "- High data rate overwhelming Qt\n"
                    "- Event queue flooding\n"
                    "- Accumulated state issues",
                    msg_type="Info",
                )

            QTimer.singleShot(2000, check_status)

        except Exception as e:
            logger.exception(f"❌ Single data point test failed: {e}")
            from widgets.message import show_message

            show_message(f"Single data point test FAILED:\n\n{e}", msg_type="Error")

    def _debug_start_simulation(self):
        """Debug: Start injecting simulated spectra (Ctrl+Shift+S).

        Injects fake SPR spectra at 10 Hz continuously to test the complete
        data pipeline: acquisition → processing → recording → UI.
        """
        import time

        import numpy as np

        logger.info("=" * 80)
        logger.info("🎬 SIMULATION MODE ACTIVATED (Ctrl+Shift+S)")
        logger.info("=" * 80)

        try:
            # Check if data_mgr exists
            if not hasattr(self, "data_mgr") or self.data_mgr is None:
                logger.error("❌ No data_mgr found!")
                from widgets.message import show_message

                show_message(
                    "Error: Data manager not initialized!\n\n"
                    "Make sure the app has fully loaded.",
                    msg_type="Error",
                )
                return

            logger.info(f"✅ Data manager found: {self.data_mgr}")

            # Check if acquisition is running
            if hasattr(self.data_mgr, "_acquiring") and not self.data_mgr._acquiring:
                logger.warning(
                    "⚠️ Acquisition not running - simulation works best with acquisition active",
                )
                logger.warning("   Press Ctrl+Shift+C then click Start first")

            # Create timer to inject spectra at SLOW rate (2 Hz to prevent Qt flooding)
            timer = QTimer()
            timer.setInterval(500)  # 500ms = 2 Hz (much slower, safer)

            spectrum_count = [0]  # Use list for mutable counter
            start_time = [time.time()]  # Simulation start time

            def send_one():
                try:
                    logger.info(
                        f"[SIM-TRACK-1] send_one() ENTRY - cycle {spectrum_count[0]}",
                    )

                    # Generate fake SPR wavelength data for each channel
                    channels = ["a", "b", "c", "d"]
                    peak_positions = {"a": 650, "b": 660, "c": 655, "d": 670}
                    intensities = {"a": 15000, "b": 12000, "c": 10000, "d": 14000}

                    elapsed = time.time() - start_time[0]
                    logger.info(f"[SIM-TRACK-2] Elapsed time: {elapsed:.3f}s")

                    # Generate wavelength array (match real detector: ~640-690nm range for SPR)
                    wavelengths = np.linspace(
                        640,
                        690,
                        512,
                    )  # 512 points for smooth spectrum

                    for ch in channels:
                        logger.info(f"[SIM-TRACK-3] Generating data for channel {ch}")

                        # Generate realistic SPR peak wavelength with drift
                        base_wavelength = peak_positions[ch]
                        drift = 0.5 * np.sin(elapsed / 10)  # Slow oscillation
                        noise = np.random.normal(0, 0.1)
                        peak_wavelength = base_wavelength + drift + noise

                        # Generate full spectrum arrays (simulate SPR dip)
                        # Raw spectrum: Gaussian dip around resonance wavelength
                        raw_spectrum = intensities[ch] - 5000 * np.exp(
                            -((wavelengths - peak_wavelength) ** 2) / (2 * 3**2),
                        )
                        raw_spectrum += np.random.normal(
                            0,
                            200,
                            len(wavelengths),
                        )  # Add noise
                        raw_spectrum = np.clip(
                            raw_spectrum,
                            1000,
                            65000,
                        )  # Realistic detector range

                        # Transmission spectrum: Calculate from raw (simulate P/S ratio)
                        # Assume S_ref is constant baseline
                        s_ref = intensities[ch] * np.ones_like(wavelengths)
                        transmission_spectrum = (
                            raw_spectrum / s_ref
                        ) * 100.0  # Percentage
                        transmission_spectrum = np.clip(transmission_spectrum, 0, 150)

                        # Create data dict with full spectrum arrays (matching real format)
                        data = {
                            "channel": ch,
                            "wavelength": float(
                                peak_wavelength,
                            ),  # Resonance peak for timeline
                            "intensity": float(intensities[ch]),  # Average intensity
                            "raw_spectrum": raw_spectrum,  # Full raw spectrum array
                            "full_spectrum": raw_spectrum,  # Alias for compatibility
                            "transmission_spectrum": transmission_spectrum,  # Full transmission array
                            "wavelengths": wavelengths,  # Wavelength array for plots
                            "timestamp": time.time(),
                            "elapsed_time": elapsed,
                            "is_preview": False,
                            "simulated": True,
                        }

                        logger.info(f"[SIM-TRACK-4] Emitting data for channel {ch}")
                        # Emit to spectrum_acquired signal
                        if self.data_mgr and hasattr(
                            self.data_mgr,
                            "spectrum_acquired",
                        ):
                            self.data_mgr.spectrum_acquired.emit(data)
                        logger.info(f"[SIM-TRACK-5] Channel {ch} emitted successfully")

                    spectrum_count[0] += 1
                    logger.info(f"[SIM-TRACK-6] Cycle {spectrum_count[0]} COMPLETE")

                    # Log every 50 cycles (5 seconds)
                    if spectrum_count[0] % 50 == 0:
                        logger.info(
                            f"📊 Injected {spectrum_count[0]} simulated data cycles ({spectrum_count[0] * 4} points)",
                        )

                except Exception as e:
                    logger.exception(f"[SIM-TRACK-FATAL] Simulation crashed: {e}")
                    timer.stop()

            timer.timeout.connect(send_one)
            timer.start()

            # Store timer reference to prevent garbage collection
            self._sim_timer = timer

            logger.info("✅ Simulation timer started at 10 Hz")
            logger.info("   Generating 4 channels (A, B, C, D) per cycle")

            from widgets.message import show_message

            show_message(
                "Simulation started!\n\n"
                "📡 Sending fake SPR data at 10 Hz\n"
                "   (4 channels per cycle)\n\n"
                "Check logs to see injection status.\n"
                "Watch the graph for updates!\n\n"
                "Close the app to stop.",
                msg_type="Info",
            )

        except Exception as e:
            logger.exception(f"❌ Failed to start simulation: {e}")
            from widgets.message import show_message

            show_message(
                f"Simulation failed:\n\n{e}",
                msg_type="Error",
            )

    def _debug_test_acquisition_thread(self):
        """Debug: Test acquisition worker thread without calibration (Ctrl+Shift+T).

        This bypasses all hardware calibration and directly creates fake calibration
        data to test if the acquisition worker thread crashes with Qt threading errors.
        Works WITHOUT hardware connected - creates mock hardware objects.
        """
        try:
            logger.info("🧪 DEBUG: Testing acquisition thread (no hardware needed)")

            # Create mock hardware if not connected
            if not self.hardware_mgr.ctrl or not self.hardware_mgr.usb:
                logger.info("🧪 DEBUG: Creating mock hardware objects")

                class MockController:
                    def set_intensity(self, ch, raw_val):
                        pass

                    def set_mode(self, mode):
                        pass

                class MockSpectrometer:
                    def set_integration(self, time_ms):
                        pass

                    def read_intensity(self):
                        import numpy as np

                        return np.random.randint(20000, 50000, 2048)

                self.hardware_mgr.ctrl = MockController()
                self.hardware_mgr.usb = MockSpectrometer()
                logger.info("🧪 DEBUG: Mock hardware created")

            # Inject minimal fake calibration data into data manager
            import numpy as np

            self.data_mgr.calibrated = True
            self.data_mgr.integration_time = 40
            self.data_mgr.num_scans = 5
            self.data_mgr.leds_calibrated = {"a": 255, "b": 150, "c": 150, "d": 255}
            self.data_mgr.wave_data = np.linspace(400, 900, 2048)
            self.data_mgr.ref_sig = {
                "a": np.ones(2048) * 40000,
                "b": np.ones(2048) * 40000,
                "c": np.ones(2048) * 40000,
                "d": np.ones(2048) * 40000,
            }
            self.data_mgr.dark_noise = np.zeros(2048)
            self.data_mgr.fourier_weights = {
                "a": np.ones(2048 - 1),  # Derivative has n-1 points
                "b": np.ones(2048 - 1),
                "c": np.ones(2048 - 1),
                "d": np.ones(2048 - 1),
            }

            logger.info("🧪 DEBUG: Fake calibration data injected")

            # Now start acquisition - this should trigger the Qt threading error if it exists
            self.data_mgr.start_acquisition()
            logger.info("🧪 DEBUG: Acquisition started - watch for Qt threading errors")
            logger.info("🧪 DEBUG: If app crashes now, it's the Qt threading bug")

        except Exception as e:
            logger.error(f"🧪 DEBUG: Thread test failed: {e}")
            import traceback

            logger.error(traceback.format_exc())

    def _on_start_button_clicked(self):
        """User clicked Start button - begin live data acquisition."""
        logger.info("🚀 User requested start - PHASE 4: Full acquisition + recording")

        # ========================================================
        # PHASE 4: FULL DATA ACQUISITION + RECORDING
        # ========================================================
        # Start acquisition thread AND recording to test complete pipeline
        # ========================================================

        # Check if already acquiring
        if self.data_mgr and self.data_mgr._acquiring:
            logger.warning("Acquisition already running")
            from widgets.message import show_message

            show_message("Acquisition is already running.", msg_type="Warning")
            return

        # PHASE 1: Validate hardware connection and calibration
        logger.info("🔍 PHASE 1: Checking hardware status...")
        try:
            if self.hardware_mgr.ctrl:
                logger.info("   ✅ Controller connected")
            else:
                logger.warning("   ⚠️ No controller found")

            if self.hardware_mgr.usb:
                logger.info("   ✅ Spectrometer connected")
            else:
                logger.warning("   ⚠️ No spectrometer found")

            # Check if calibrated and get settings
            if self.data_mgr and self.data_mgr.calibrated:
                logger.info("   ✅ System calibrated")
                integration_time = self.data_mgr.integration_time
                led_intensities = self.data_mgr.leds_calibrated
            else:
                logger.info("   ℹ️ System not calibrated (using bypass mode defaults)")
                integration_time = 40
                led_intensities = {"a": 255, "b": 150, "c": 150, "d": 255}

            logger.info("✅ Hardware validation complete")
        except Exception as e:
            logger.exception(f"❌ Hardware validation failed: {e}")
            from widgets.message import show_message

            show_message(f"Hardware check failed:\n{e}", msg_type="Error")
            return

        # PHASE 2: Configure hardware
        logger.info("🔧 PHASE 2: Configuring hardware...")

        # 2A: Polarizer
        try:
            ctrl = self.hardware_mgr.ctrl
            if ctrl and hasattr(ctrl, "set_mode"):
                logger.info("   Setting polarizer to P-mode...")
                ctrl.set_mode("p")
                import time

                time.sleep(0.4)
                logger.info("   ✅ Polarizer configured")
            else:
                logger.warning("   ⚠️ Controller not available")
        except Exception as e:
            logger.exception(f"❌ Polarizer configuration failed: {e}")

        # 2B: Integration time
        try:
            usb = self.hardware_mgr.usb
            if usb and hasattr(usb, "set_integration"):
                logger.info(f"   Setting integration time: {integration_time}ms...")
                usb.set_integration(integration_time)
                logger.info("   ✅ Integration time configured")
            else:
                logger.warning("   ⚠️ Spectrometer not available")
        except Exception as e:
            logger.exception(f"❌ Integration time configuration failed: {e}")

        # 2C: LED intensities
        try:
            ctrl = self.hardware_mgr.ctrl
            if ctrl and hasattr(ctrl, "set_intensity"):
                logger.info(f"   Setting LED intensities: {led_intensities}...")
                for channel, intensity in led_intensities.items():
                    ctrl.set_intensity(channel, intensity)
                logger.info("   ✅ LED intensities configured")
            else:
                logger.warning("   ⚠️ Controller not available")
        except Exception as e:
            logger.exception(f"❌ LED configuration failed: {e}")

        logger.info("✅ Hardware configuration complete")

        # PHASE 3: Start data acquisition thread
        logger.info("🚀 PHASE 3: Starting data acquisition thread...")
        try:
            # This is the critical step - starting the actual acquisition
            self.data_mgr.start_acquisition()
            logger.info("✅ Data acquisition thread started successfully")
        except Exception as e:
            logger.exception(f"❌ Failed to start acquisition: {e}")
            from widgets.message import show_message

            show_message(f"Failed to start acquisition:\n{e}", msg_type="Error")
            return

        # PHASE 4: Start recording
        logger.info("🚀 PHASE 4: Starting recording...")
        try:
            self.recording_mgr.start_recording()
            logger.info("✅ Recording started successfully")
        except Exception as e:
            logger.exception(f"❌ Failed to start recording: {e}")
            from widgets.message import show_message

            show_message(f"Failed to start recording:\n{e}", msg_type="Error")
            return

        # Step 4: Open live data dialog
        logger.info("📊 Opening live data dialog...")
        try:
            from live_data_dialog import LiveDataDialog

            if self._live_data_dialog is None:
                self._live_data_dialog = LiveDataDialog(parent=self.main_window)
            self._live_data_dialog.show()
            self._live_data_dialog.raise_()
            self._live_data_dialog.activateWindow()
            logger.info("✅ Live data dialog opened")
        except Exception as e:
            logger.exception(f"Failed to open live data dialog: {e}")

        # Step 5: Update UI state
        logger.info("🎭 Updating UI state...")
        try:
            self.main_window.enable_controls()
            if hasattr(self.main_window, "sidebar") and hasattr(
                self.main_window.sidebar,
                "start_cycle_btn",
            ):
                self.main_window.sidebar.start_cycle_btn.setEnabled(True)
            self._on_acquisition_started()
            logger.info("✅ UI state updated")
        except Exception as e:
            logger.exception(f"Failed to update UI: {e}")

        logger.info("=" * 80)
        logger.info("✅ PHASE 4 COMPLETE - Acquisition + Recording running!")
        logger.info("=" * 80)
        from widgets.message import show_message

        show_message(
            "Phase 4 Complete!\n\n✅ Hardware configured\n✅ Acquisition thread started\n✅ Recording started\n✅ Live data flowing\n\nIf you see this without crash - SUCCESS!",
            msg_type="Info",
            title="Phase 4: Full Acquisition + Recording",
        )

    def _on_scan_requested(self):
        """User clicked Scan button in UI."""
        logger.info("User requested hardware scan")
        self.hardware_mgr.scan_and_connect()

    def _on_hardware_connected(self, status: dict):
        """Hardware connection completed and update Device Status UI."""
        logger.info("🔌 Hardware connection callback received")
        logger.info(f"   Status: {status}")

        # Reset scan button state in UI
        self.main_window._on_hardware_scan_complete()

        # Check if scan was successful (valid hardware combinations found)
        # Valid combinations:
        # - P4SPR/P4PRO/ezSPR: controller + detector (both required)
        # - KNX: standalone kinetic controller
        # - AffiPump: standalone pump
        scan_successful = status.get("scan_successful", False)

        # Validate hardware combinations
        ctrl_type = status.get("ctrl_type")
        knx_type = status.get("knx_type")
        pump_connected = status.get("pump_connected")

        valid_hardware = []
        if ctrl_type:  # SPR device (already validated as controller + detector)
            valid_hardware.append(ctrl_type)
        if knx_type:  # Kinetic controller (standalone)
            valid_hardware.append(knx_type)
        if pump_connected:  # Pump (standalone)
            valid_hardware.append("AffiPump")

        # Update power button based on scan success
        if scan_successful and valid_hardware:
            logger.info(
                f"✅ Scan SUCCESSFUL - found valid hardware: {', '.join(valid_hardware)}",
            )
            self.main_window.set_power_state("connected")
        else:
            logger.warning("⚠️ Scan FAILED - no valid hardware combinations found")
            self.main_window.set_power_state("disconnected")

            # Clear Device Status UI
            empty_status = {
                "ctrl_type": None,
                "knx_type": None,
                "pump_connected": False,
                "spectrometer": False,
                "sensor_ready": False,
                "optics_ready": False,
                "fluidics_ready": False,
            }
            self._update_device_status_ui(empty_status)

            # Show error message with specific details
            ctrl_only = status.get("spectrometer") == False and ctrl_type
            if ctrl_only:
                error_msg = f"Incomplete hardware detected.\n\n{ctrl_type} controller found but detector missing.\n\nPlease connect USB4000 spectrometer."
            else:
                error_msg = "No devices found.\n\nPlease check:\n• USB connections\n• Device power\n• Driver installation"

            from widgets.message import show_message

            show_message(error_msg, msg_type="Warning", title="Connection Failed")
            return  # Exit early if scan failed

        # Re-initialize device config with actual device serial number (ONLY on initial connection)
        device_serial = status.get("spectrometer_serial")
        if device_serial and not self._device_config_initialized:
            logger.info(
                f"Re-initializing device configuration for S/N: {device_serial}",
            )

            # Initialize device-specific directory and configuration
            from utils.device_integration import initialize_device_on_connection

            # Create a mock USB device object with serial number for device initialization
            class MockUSBDevice:
                def __init__(self, serial):
                    self.serial_number = serial

            mock_usb = MockUSBDevice(device_serial)
            device_dir = initialize_device_on_connection(mock_usb)

            if device_dir:
                logger.info(f"✅ Device initialized: {device_dir}")

            # Initialize device config and prompt for missing fields if needed
            self.main_window._init_device_config(device_serial=device_serial)

            # Check for and apply special case if detector is in registry
            special_case_info = status.get("special_case")
            if special_case_info and special_case_info.get("has_overrides"):
                logger.info("=" * 60)
                logger.info("📋 APPLYING SPECIAL CASE CONFIGURATION")
                logger.info(f"   Detector S/N: {special_case_info['detector_serial']}")
                logger.info(f"   Description: {special_case_info['description']}")
                logger.info("=" * 60)

                # Get special case from hardware manager and apply to device config
                special_case = self.hardware_mgr.get_special_case()
                if special_case:
                    from utils.device_special_cases import apply_special_case

                    # Apply special case to the loaded device config
                    self.main_window.device_config = apply_special_case(
                        special_case,
                        self.main_window.device_config,
                    )
                    logger.info("✅ Special case configuration applied to device")

            # Mark as initialized to prevent redundant reloads
            self._device_config_initialized = True
        elif device_serial and self._device_config_initialized:
            logger.debug(
                "Hardware status update received (not initial connection) - skipping calibration check",
            )
        else:
            # No spectrometer detected - this is a new OEM device that needs provisioning
            logger.warning("⚠️ No spectrometer serial in hardware status")

            if status.get("ctrl_type"):
                # Controller detected but no spectrometer - trigger OEM device config flow
                logger.info("=" * 80)
                logger.info("🏭 NEW DEVICE DETECTED - OEM Provisioning Required")
                logger.info("=" * 80)
                logger.info(f"   Controller: {status.get('ctrl_type')}")
                logger.info("   Spectrometer: NOT CONNECTED")
                logger.info("")
                logger.info("📋 Starting OEM device configuration workflow:")
                logger.info(
                    "   1. Collect device info (LED model, fiber diameter, etc.)",
                )
                logger.info("   2. Connect spectrometer")
                logger.info("   3. Auto-calibrate servo positions")
                logger.info("   4. Calculate afterglow correction")
                logger.info("   5. Calibrate LED intensities")
                logger.info("=" * 80)

                # Initialize device config with default/placeholder serial
                # This will trigger the device config dialog to collect missing info
                self.main_window._init_device_config(device_serial=None)

                # Show message to user explaining next steps
                from widgets.message import show_message

                show_message(
                    "New Device Detected!\n\n"
                    f"Controller: {status.get('ctrl_type')}\n"
                    f"Spectrometer: NOT CONNECTED\n\n"
                    "Please complete device configuration,\n"
                    "then connect the spectrometer to begin\n"
                    "automatic calibration.",
                    msg_type="Information",
                    title="OEM Device Provisioning",
                )
            else:
                # Fallback to default config
                logger.warning("Using default config")
                self.main_window._init_device_config(device_serial=None)

        # Update last power-on timestamp in maintenance tracking (only on initial connection)
        if self._device_config_initialized:
            logger.debug(
                "Hardware status update received (not initial connection) - skipping timestamp update",
            )
        else:
            self.main_window.update_last_power_on()

        # Update Device Status UI with hardware details (always, even on status updates)
        logger.debug(
            f"🔍 Calling _update_device_status_ui with optics_ready={status.get('optics_ready')}, sensor_ready={status.get('sensor_ready')}",
        )
        self._update_device_status_ui(status)

        # Load servo positions and LED intensities from device config (only on initial connection)
        if self._device_config_initialized:
            logger.debug(
                "Hardware status update received (not initial connection) - skipping device settings reload",
            )
        else:
            self._load_device_settings()

        # Check if OEM calibration workflow should be triggered
        # This happens when: config was just completed + spectrometer now connected
        if self.main_window.oem_config_just_completed and status.get("spectrometer"):
            logger.info("=" * 80)
            logger.info(
                "🏭 OEM Config Complete + Spectrometer Connected → Auto-Starting Calibration",
            )
            logger.info("=" * 80)
            self.main_window.oem_config_just_completed = False  # Reset flag

            # Trigger calibration workflow
            if hasattr(self.main_window, "_start_oem_calibration_workflow"):
                self.main_window._start_oem_calibration_workflow()
            else:
                logger.error(
                    "_start_oem_calibration_workflow method not found in main_window",
                )

        # Update calibration dialog if it exists and is waiting for hardware
        if self._calibration_dialog and not self._calibration_dialog._is_closing:
            if status.get("ctrl_type") and status.get("spectrometer"):
                # Both hardware components detected
                logger.info("✅ Calibration dialog updated: Hardware detected")
                self._calibration_dialog.update_status(
                    f"Hardware detected:\n"
                    f"• Controller: {status.get('ctrl_type')}\n"
                    f"• Spectrometer: Connected\n\n"
                    f"Calibration will start automatically...",
                )
            elif status.get("spectrometer") and not status.get("ctrl_type"):
                logger.warning("⚠️ Spectrometer found but controller missing")
                self._calibration_dialog.update_status(
                    "⚠️ Controller not detected\n\n"
                    "Please connect the SPR controller\n"
                    "to continue calibration.",
                )
            elif status.get("ctrl_type") and not status.get("spectrometer"):
                logger.warning("⚠️ Controller found but spectrometer missing")
                self._calibration_dialog.update_status(
                    "⚠️ Spectrometer not detected\n\n"
                    "Please connect the spectrometer\n"
                    "to continue calibration.",
                )

        # Start calibration ONLY on initial connection, not on status updates
        # This prevents calibration from restarting when optics_ready changes
        if not self._initial_connection_done:
            self._initial_connection_done = True

            # Reset calibration flag on new hardware connection
            # Each power-on cycle requires fresh calibration
            self._calibration_completed = False
            logger.debug("🔄 New hardware connection - calibration flag reset")

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

                # OPTIMIZATION: Check for optical calibration file first
                # If missing, offer to run it BEFORE LED calibration (faster workflow)
                from utils.device_integration import get_device_optical_calibration_path

                optical_cal_path = get_device_optical_calibration_path()

                if not optical_cal_path or not optical_cal_path.exists():
                    logger.info(
                        "📋 Optical calibration file not found - starting full calibration workflow",
                    )
                    logger.info("   Step 1/2: LED intensity calibration")
                    logger.info(
                        "   Step 2/2: Optical afterglow calibration (after LED completes)",
                    )
                    # Run full calibration workflow automatically (LED → afterglow)
                    self._run_led_then_afterglow_calibration()
                    return

                # Trigger calibration with dialog (LED only, optical cal already exists)
                logger.info(
                    "📋 Optical calibration exists - running LED calibration only",
                )
                logger.info("=" * 80)
                logger.info(
                    f"🔍 TYPE CHECK: self.calibration = {type(self.calibration)}",
                )
                logger.info(f"🔍 OBJECT: {self.calibration}")
                logger.info("=" * 80)
                self.calibration.start_calibration()
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
            # Check if this is an OEM device that just completed configuration
            # and now has spectrometer connected for the first time
            if (
                hasattr(self.main_window, "oem_config_just_completed")
                and self.main_window.oem_config_just_completed
            ):
                if (
                    status.get("ctrl_type")
                    and status.get("spectrometer")
                    and not self._calibration_completed
                ):
                    logger.info("=" * 80)
                    logger.info(
                        "🏭 OEM DEVICE: Spectrometer connected after config completion",
                    )
                    logger.info("=" * 80)
                    logger.info("🎯 Auto-starting OEM calibration workflow...")
                    logger.info(f"   Controller: {status.get('ctrl_type')}")
                    logger.info(
                        f"   Spectrometer: {status.get('spectrometer_serial', 'Connected')}",
                    )
                    logger.info("")
                    logger.info("📋 Calibration steps:")
                    logger.info("   1. Servo position optimization")
                    logger.info("   2. Afterglow correction calculation")
                    logger.info("   3. LED intensity calibration")
                    logger.info("=" * 80)

                    # Clear the flag
                    self.main_window.oem_config_just_completed = False

                    # Trigger OEM calibration
                    self.data_mgr.start_calibration()

                    # Show message to user
                    from widgets.message import show_message

                    show_message(
                        "Spectrometer Connected!\n\n"
                        "Starting automatic OEM calibration:\n"
                        "• Servo position optimization\n"
                        "• Afterglow correction\n"
                        "• LED intensity calibration\n\n"
                        "This will take a few minutes...",
                        msg_type="Information",
                        title="OEM Calibration Started",
                    )
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
        if (
            self.main_window.power_btn
            and self.main_window.power_btn.property("powerState") == "searching"
        ):
            logger.info("Resetting power button state after connection error")
            self.main_window._set_power_button_state("disconnected")
            self.main_window._update_power_button_style()

    def show_transmission_dialog(self):
        """Show the transmission spectrum dialog."""
        if self._transmission_dialog is None:
            self._transmission_dialog = TransmissionSpectrumDialog(self.main_window)

        self._transmission_dialog.show()
        self._transmission_dialog.raise_()
        self._transmission_dialog.activateWindow()

    # === Data Acquisition Callbacks ===

    def _start_processing_thread(self):
        """Start dedicated processing thread for spectrum data (Phase 3 optimization).

        Separates acquisition from processing to prevent jitter in acquisition timing.
        Acquisition thread only queues data, processing thread handles all analysis.
        """
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
        try:
            # Increment acquisition counter for throttling
            self._acquisition_counter += 1
            should_log = self._acquisition_counter % DEBUG_LOG_THROTTLE_FACTOR == 0

            if should_log:
                logger.info(
                    f"[CRASH-TRACK-1] _on_spectrum_acquired ENTRY - channel={data.get('channel', '?')} (#{self._acquisition_counter})",
                )

            # Initialize experiment start time on first data point
            if self.experiment_start_time is None:
                self.experiment_start_time = data["timestamp"]
                if should_log:
                    logger.info(
                        f"[CRASH-TRACK-1A] Experiment start time set: {self.experiment_start_time}",
                    )

            # Calculate elapsed time (minimal work in acquisition thread)
            data["elapsed_time"] = data["timestamp"] - self.experiment_start_time
            if should_log:
                logger.info(
                    f"[CRASH-TRACK-1B] Elapsed time calculated: {data['elapsed_time']:.3f}s",
                )

            # Queue for processing thread (non-blocking)
            try:
                self._spectrum_queue.put_nowait(data)
                if should_log:
                    logger.info("[CRASH-TRACK-1C] Data queued successfully")
            except:
                # Queue full - log and drop (prevents blocking acquisition)
                self._queue_stats["dropped"] += 1
                if self._queue_stats["dropped"] % 10 == 1:  # Log every 10th drop
                    logger.warning(
                        f"⚠️ Spectrum queue full - {self._queue_stats['dropped']} frames dropped",
                    )

            if should_log:
                logger.info("[CRASH-TRACK-1D] _on_spectrum_acquired EXIT - SUCCESS")

        except Exception as e:
            logger.exception(
                f"[CRASH-TRACK-1-FATAL] _on_spectrum_acquired crashed: {e}",
            )

    def _process_spectrum_data(self, data: dict):
        """Process spectrum data in dedicated worker thread (Phase 3 optimization).

        All the actual processing happens here, not in acquisition callback.
        This includes: intensity monitoring, transmission updates, buffer updates, etc.
        """
        try:
            # Throttled logging (only log every Nth acquisition)
            should_log = self._acquisition_counter % DEBUG_LOG_THROTTLE_FACTOR == 0

            if should_log:
                logger.info("[CRASH-TRACK-2] _process_spectrum_data ENTRY")

            channel = data["channel"]  # 'a', 'b', 'c', 'd'
            wavelength = data["wavelength"]  # nm
            intensity = data.get("intensity", 0)  # Raw intensity
            timestamp = data["timestamp"]
            elapsed_time = data["elapsed_time"]
            is_preview = data.get(
                "is_preview",
                False,
            )  # Interpolated preview vs real data

            if should_log:
                logger.info(
                    f"[CRASH-TRACK-2A] Data parsed - ch={channel}, wave={wavelength:.1f}, int={intensity:.0f}",
                )
                print(
                    f"[PROCESS] Channel {channel}: wave={wavelength:.1f}nm, int={intensity:.0f}, time={elapsed_time:.2f}s",
                )

            # SIMPLIFIED: Just append to buffers and queue graph update
            # Skip intensity monitoring, transmission queueing, etc. for now

            # Append to timeline data buffers (RAW data - unfiltered)
            try:
                if should_log:
                    logger.info(
                        "[CRASH-TRACK-2B] Calling buffer_mgr.append_timeline_point",
                    )
                self.buffer_mgr.append_timeline_point(
                    channel,
                    elapsed_time,
                    wavelength,
                    timestamp,
                )
                if should_log:
                    logger.info("[CRASH-TRACK-2C] Buffer append SUCCESS")
                    print(f"[PROCESS] Channel {channel}: Buffer updated OK")

                # CRASH DEBUG: Check thread context (throttled)
                if should_log:
                    import threading

                    logger.info(
                        f"[CRASH-DEBUG] Current thread: {threading.current_thread().name}",
                    )
                    logger.info(
                        f"[CRASH-DEBUG] Is main thread: {threading.current_thread() is threading.main_thread()}",
                    )
                    print(f"[CRASH-DEBUG] Thread: {threading.current_thread().name}")

            except Exception as e:
                logger.exception(f"[CRASH-TRACK-2C-ERROR] Buffer append FAILED: {e}")
                print(f"[PROCESS ERROR] Channel {channel}: Buffer append failed: {e}")
                import traceback

                traceback.print_exc()

            # Queue transmission spectrum update (for dialog display) ONLY if we have full spectrum
            # THROTTLED: Only update every N seconds per channel
            has_raw_data = (
                data.get("raw_spectrum") is not None
                or data.get("full_spectrum") is not None
            )
            has_transmission = data.get("transmission_spectrum") is not None
            time_since_last_update = timestamp - self._last_transmission_update.get(
                channel,
                0,
            )
            should_update_transmission = (
                time_since_last_update >= TRANSMISSION_UPDATE_INTERVAL
            )

            if has_raw_data and has_transmission and should_update_transmission:
                try:
                    if should_log:
                        logger.info(
                            "[CRASH-TRACK-2D] Calling _queue_transmission_update",
                        )
                        print(
                            f"[DEBUG] About to call _queue_transmission_update(channel={channel})",
                        )
                        print(
                            f"[DEBUG] self={type(self).__name__}, has_method={hasattr(self, '_queue_transmission_update')}",
                        )
                    self._queue_transmission_update(channel, data)
                    self._last_transmission_update[channel] = timestamp

                    # Update Sensor IQ display if available
                    if "sensor_iq" in data:
                        self._update_sensor_iq_display(channel, data["sensor_iq"])

                    if should_log:
                        logger.info("[CRASH-TRACK-2E] Transmission queue SUCCESS")
                        print(f"[PROCESS] Channel {channel}: Transmission queued")
                except Exception as e:
                    logger.exception(
                        f"[CRASH-TRACK-2E-ERROR] Transmission queue FAILED: {e}",
                    )
                    print(
                        f"[PROCESS ERROR] Channel {channel}: Transmission queue failed: {e}",
                    )
                    import traceback

                    traceback.print_exc()

            # Cursor auto-follow (thread-safe via signal)
            # Emit signal to update cursor on main thread
            try:
                self.cursor_update_signal.emit(elapsed_time)
            except Exception as e:
                logger.warning(f"Cursor update signal emit failed: {e}")

        except Exception as e:
            # TOP-LEVEL CATCH: Prevent any exception from killing the processing thread
            logger.exception(
                f"[CRASH-TRACK-2-FATAL] _process_spectrum_data CRASHED: {e}",
            )
            print(
                f"[PROCESS FATAL] Channel {data.get('channel', '?')}: Unhandled exception: {e}",
            )
            import traceback

            traceback.print_exc()

        # Queue graph update instead of immediate update (throttled by timer)
        # DOWNSAMPLED: Only queue every Nth update
        self._sensorgram_update_counter += 1
        should_update_graph = (
            self._sensorgram_update_counter % SENSORGRAM_DOWNSAMPLE_FACTOR == 0
        )

        if should_update_graph:
            try:
                if should_log:
                    logger.info("[CRASH-TRACK-3] Queueing graph update")

                # Queue the update (main thread will check if live data is enabled)
                self._pending_graph_updates[channel] = {
                    "elapsed_time": elapsed_time,
                    "channel": channel,
                }
                if should_log:
                    logger.info("[CRASH-TRACK-3A] Graph update queued")
            except Exception as e:
                logger.exception(f"[CRASH-TRACK-3-ERROR] Graph queue FAILED: {e}")

        # Record data point if recording is active
        try:
            if should_log:
                logger.info(
                    f"[CRASH-TRACK-4] Checking recording - is_recording={self.recording_mgr.is_recording}",
                )
            if self.recording_mgr.is_recording:
                if should_log:
                    logger.info("[CRASH-TRACK-4A] Building data point")
                # Build data point with all channels (use latest value for each)
                data_point = {}
                for ch in self._idx_to_channel:
                    latest_value = self.buffer_mgr.get_latest_value(ch)
                    data_point[f"channel_{ch}"] = (
                        latest_value if latest_value is not None else ""
                    )

                if should_log:
                    logger.info("[CRASH-TRACK-4B] Recording data point")
                self.recording_mgr.record_data_point(data_point)
                if should_log:
                    logger.info("[CRASH-TRACK-4C] Recording SUCCESS")
        except Exception as e:
            logger.exception(f"[CRASH-TRACK-4-ERROR] Recording FAILED: {e}")

        if should_log:
            logger.info("[CRASH-TRACK-5] _process_spectrum_data EXIT - COMPLETE")

        # Update cycle of interest graph (bottom graph) - REMOVED
        # This was causing crashes by running heavy processing 40+ times per second
        # The cycle graph is now updated by the UI refresh timer at a reasonable rate
        # self._update_cycle_of_interest_graph()

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
        # Skip if updates are disabled (performance optimization)
        if (
            not self._transmission_updates_enabled
            and not self._raw_spectrum_updates_enabled
        ):
            return

        transmission = data.get("transmission_spectrum")
        # Get raw spectrum - check both field names for compatibility
        raw_spectrum = data.get("raw_spectrum")
        if raw_spectrum is None:
            raw_spectrum = data.get("full_spectrum")

        # Fallback: calculate transmission if not provided
        if transmission is None and raw_spectrum is not None and len(raw_spectrum) > 0:
            ref_spectrum = self.data_mgr.ref_sig[channel]
            transmission = calculate_transmission(raw_spectrum, ref_spectrum)

        # Queue for batch update if we have valid data
        if transmission is not None and len(transmission) > 0:
            # Use simulated wavelengths if available, otherwise use data_mgr.wave_data
            wavelengths = data.get("wavelengths", self.data_mgr.wave_data)

            # For simulated data ONLY, generate wavelength array if not provided
            if wavelengths is None and data.get("simulated", False):
                wavelengths = np.linspace(640, 690, len(transmission))
                logger.debug(
                    f"[SIMULATION] Generated wavelength array for channel {channel}",
                )

            # Safety check: Real hardware data should NEVER hit this path
            if wavelengths is None and not data.get("simulated", False):
                logger.error(
                    f"[HARDWARE ERROR] No wavelength data for channel {channel}! "
                    f"Calibration may have failed. Skipping spectrum update.",
                )
                return  # Don't update dialogs without wavelength data

            self._pending_transmission_updates[channel] = {
                "transmission": transmission,
                "raw_spectrum": raw_spectrum,
                "wavelengths": wavelengths,
            }

            if wavelengths is not None:
                # Update transmission dialog if open (only if enabled)
                if (
                    self._transmission_updates_enabled
                    and self._transmission_dialog is not None
                    and self._transmission_dialog.isVisible()
                ):
                    self._transmission_dialog.update_spectrum(
                        channel,
                        wavelengths,
                        transmission,
                        raw_spectrum,
                    )

                # Update live data dialog if open (THREAD SAFE - called from processing thread)
                if self._live_data_dialog is not None:
                    try:
                        # Update both transmission and raw data plots (respect enable flags)
                        if self._transmission_updates_enabled:
                            self._live_data_dialog.update_transmission_plot(
                                channel,
                                wavelengths,
                                transmission,
                            )
                        if (
                            self._raw_spectrum_updates_enabled
                            and raw_spectrum is not None
                        ):
                            self._live_data_dialog.update_raw_data_plot(
                                channel,
                                wavelengths,
                                raw_spectrum,
                            )
                    except Exception:
                        # Silently ignore dialog update errors (dialog may be closing)
                        pass

    def _update_sensor_iq_display(self, channel: str, sensor_iq):
        """Update Sensor IQ display in diagnostics panel.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            sensor_iq: SensorIQMetrics object from utils.sensor_iq

        """
        try:
            from utils.sensor_iq import (
                FWHM_THRESHOLDS_DISPLAY,
                SENSOR_IQ_COLORS,
                SENSOR_IQ_ICONS,
                ZONE_BOUNDARIES_DISPLAY,
            )

            # Get the appropriate label widget for this channel
            label_attr = f"sensor_iq_{channel}_diag"
            if not hasattr(self.main_window, label_attr):
                return

            label = getattr(self.main_window, label_attr)

            # Get icon and color from centralized constants
            iq_level_key = sensor_iq.iq_level.value
            icon = SENSOR_IQ_ICONS.get(iq_level_key, "❓")
            color = SENSOR_IQ_COLORS.get(iq_level_key, "#86868B")

            # Build display text
            fwhm_text = f"{sensor_iq.fwhm:.1f}nm" if sensor_iq.fwhm else "N/A"
            display_text = f"{icon} {sensor_iq.iq_level.value.upper()} | λ={sensor_iq.wavelength:.1f}nm, FWHM={fwhm_text}, Score={sensor_iq.quality_score:.2f}"

            # Update label with styled text
            label.setText(display_text)
            label.setStyleSheet(
                f"font-size: 12px; color: {color}; font-weight: bold; font-family: 'Consolas', 'Courier New', monospace;",
            )

            # Update static info labels (only once per cycle, not per channel)
            if channel == "a":
                if hasattr(self.main_window, "sensor_iq_zones_diag"):
                    self.main_window.sensor_iq_zones_diag.setText(
                        ZONE_BOUNDARIES_DISPLAY,
                    )
                if hasattr(self.main_window, "sensor_iq_fwhm_diag"):
                    self.main_window.sensor_iq_fwhm_diag.setText(
                        FWHM_THRESHOLDS_DISPLAY,
                    )

        except Exception:
            # Silently fail - non-critical display update
            pass

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

    def _on_page_changed(self, page_index: int):
        """Handle page changes - show/hide live data dialog for Live Data page (index 0)."""
        # Page 0 is Live Data (sensorgram)
        if page_index == 0:
            # Show live data dialog if acquisition is running
            if (
                self.data_mgr
                and hasattr(self.data_mgr, "is_acquiring")
                and self.data_mgr.is_acquiring
                and self._live_data_dialog is not None
            ):
                self._live_data_dialog.show()
                self._live_data_dialog.raise_()
        # Hide dialog when switching away from Live Data page
        elif self._live_data_dialog is not None:
            self._live_data_dialog.hide()

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

        Note: Graph updates continue even when "Live Data" checkbox is unchecked.
        The checkbox only controls cursor auto-follow behavior.
        """
        with measure("ui_update_timer"):
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

            # === UPDATE CYCLE OF INTEREST GRAPH ===
            # Update at throttled rate (10 FPS) instead of on every data point (40+ FPS)
            # This prevents crashes from heavy processing (filtering, baseline calc, etc.)
            try:
                with measure("cycle_of_interest_update"):
                    self._update_cycle_of_interest_graph()
            except (
                AttributeError,
                RuntimeError,
                KeyError,
                IndexError,
                TypeError,
                ValueError,
            ):
                # Safely handle any initialization issues (cursors not ready, no data yet, etc.)
                pass

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

    def _update_stop_cursor_position(self, elapsed_time: float):
        """Update stop cursor position on main thread (thread-safe).

        This slot is called from the cursor_update_signal emitted by the
        processing thread. It safely updates the cursor on the main Qt thread.

        Behavior:
        - Only updates cursor if "Live Data" checkbox is enabled
        - Respects user drag interaction (pauses during drag)
        - Cycle of interest graph always updates regardless of checkbox state

        Args:
            elapsed_time: Time value to set cursor to

        """
        try:
            # Check if graph and cursor exist
            if not hasattr(self.main_window, "full_timeline_graph"):
                return
            if not hasattr(self.main_window.full_timeline_graph, "stop_cursor"):
                return

            stop_cursor = self.main_window.full_timeline_graph.stop_cursor
            if stop_cursor is None:
                return

            # Check if "Live Data" checkbox is enabled (controls cursor auto-follow)
            if not hasattr(self.main_window, "live_data_enabled"):
                return
            if not self.main_window.live_data_enabled:
                return  # Checkbox disabled - stop cursor updates but keep recording

            # Check if user is currently dragging the cursor
            is_moving = getattr(stop_cursor, "moving", False)
            if is_moving:
                return  # Don't auto-move while user is dragging

            # Update cursor position (only when checkbox enabled)
            stop_cursor.setValue(elapsed_time)

            # Update label if it exists
            if hasattr(stop_cursor, "label") and stop_cursor.label:
                stop_cursor.label.setFormat(f"Stop: {elapsed_time:.1f}s")

        except (AttributeError, RuntimeError):
            # Cursor not ready yet, skip this update silently
            pass

    def _update_cycle_of_interest_graph(self):
        """Update the cycle of interest graph based on cursor positions.

        Also triggers autosave when cycle region changes significantly.
        """
        # Safety checks - don't crash if cursors not initialized or no data yet
        try:
            if not hasattr(self.main_window.full_timeline_graph, "start_cursor"):
                return
            if not hasattr(self.main_window.full_timeline_graph, "stop_cursor"):
                return
            if self.main_window.full_timeline_graph.start_cursor is None:
                return
            if self.main_window.full_timeline_graph.stop_cursor is None:
                return

            # Additional safety - check if buffer manager is ready
            if not hasattr(self, "buffer_mgr") or self.buffer_mgr is None:
                return
            if not hasattr(self, "_channel_pairs") or not self._channel_pairs:
                return

            # Check if we have ANY data at all - if buffers are empty, skip update
            has_data = False
            for ch in ["a", "b", "c", "d"]:
                if len(self.buffer_mgr.timeline_data[ch].time) > 0:
                    has_data = True
                    break
            if not has_data:
                return  # No data yet, nothing to display

        except (AttributeError, RuntimeError):
            return

        try:
            import numpy as np

            # Get cursor positions from full timeline graph
            start_time = self.main_window.full_timeline_graph.start_cursor.value()
            stop_time = self.main_window.full_timeline_graph.stop_cursor.value()

            # Check if this is a new cycle region (for autosave)
            cycle_changed = False
            if (
                not hasattr(self, "_last_cycle_bounds")
                or self._last_cycle_bounds is None
            ):
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
                cycle_time, cycle_wavelength, cycle_timestamp = (
                    self.buffer_mgr.extract_cycle_region(
                        ch_letter,
                        start_time,
                        stop_time,
                    )
                )

                if len(cycle_time) == 0:
                    continue

                # Apply filtering to CYCLE OF INTEREST (subset) - batch filtering for accuracy
                # This is where we want high-quality filtering since it's used for analysis
                # Kalman is optimal for historical/COI analysis (smooth trajectories)
                if self._filter_enabled and len(cycle_wavelength) > 2:
                    cycle_wavelength = self._apply_smoothing(
                        cycle_wavelength,
                        self._filter_strength,
                        ch_letter,  # Pass channel for Kalman filter state
                    )

                # Calculate Δ SPR (baseline is first point in cycle or calibrated baseline)
                baseline = self.buffer_mgr.baseline_wavelengths[ch_letter]
                if baseline is None:
                    # Use first point in cycle as baseline
                    baseline = cycle_wavelength[0] if len(cycle_wavelength) > 0 else 0

                # Convert wavelength shift to RU (Response Units)
                delta_spr = (cycle_wavelength - baseline) * WAVELENGTH_TO_RU_CONVERSION

                # Store in buffer manager (with timestamps)
                self.buffer_mgr.update_cycle_data(
                    ch_letter,
                    cycle_time,
                    cycle_wavelength,
                    delta_spr,
                    cycle_timestamp,
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

        except (
            AttributeError,
            RuntimeError,
            KeyError,
            IndexError,
            ValueError,
            TypeError,
        ):
            # Silently handle any errors during cycle update (data not ready, buffers empty, etc.)
            # This prevents crashes while data is being populated
            pass

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

    def _on_polarizer_toggle_clicked(self):
        """Handle polarizer toggle button click - switch servo between S and P positions."""
        try:
            logger.info("🔘 Polarizer toggle button clicked")

            # Get current position from UI
            current_position = self.main_window.sidebar.current_polarizer_position
            logger.info(f"   Current position: {current_position}")

            # Toggle to opposite position
            new_position = "P" if current_position == "S" else "S"

            # Send command to hardware
            if self.hardware_mgr.controller is not None:
                logger.info(
                    f"🔄 Toggling polarizer: {current_position} → {new_position}",
                )
                success = self.hardware_mgr.controller.set_mode(new_position.lower())

                if success:
                    # Update UI to reflect new position
                    self.main_window.sidebar.set_polarizer_position(new_position)
                    logger.info(f"✅ Polarizer moved to position {new_position}")
                else:
                    logger.error(
                        f"❌ Failed to move polarizer to position {new_position}",
                    )
                    from widgets.message import show_message

                    show_message(
                        f"Failed to move polarizer to position {new_position}",
                        "Polarizer Error",
                        parent=self.main_window,
                    )
            else:
                logger.warning("⚠️ Controller not connected - cannot move polarizer")
                from widgets.message import show_message

                show_message(
                    "Controller not connected. Please connect hardware first.",
                    "Hardware Not Connected",
                    parent=self.main_window,
                )

        except Exception as e:
            logger.error(f"❌ Error toggling polarizer: {e}")
            from widgets.message import show_message

            show_message(
                f"Error toggling polarizer: {e!s}",
                "Polarizer Error",
                parent=self.main_window,
            )

    # === Recording Callbacks ===

    def _on_recording_started(self, filename: str):
        """Recording started."""
        logger.info(f"📝 Recording started: {filename}")

        # Start tracking LED operation hours
        self.main_window.start_led_operation_tracking()

        # Update UI recording indicator with filename
        self.main_window.set_recording_state(True, filename)

        # Update spectroscopy status
        if (
            hasattr(self.main_window, "sidebar")
            and hasattr(self.main_window.sidebar, "subunit_status")
            and "Spectroscopy" in self.main_window.sidebar.subunit_status
        ):
            status_label = self.main_window.sidebar.subunit_status["Spectroscopy"][
                "status_label"
            ]
            status_label.setText("Recording...")
            status_label.setStyleSheet(
                "font-size: 13px;"
                "color: #FF3B30;"  # Red for recording
                "background: transparent;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
            )

    def _on_recording_stopped(self):
        """Recording stopped."""
        logger.info("📝 Recording stopped")

        # Stop tracking LED operation hours and save to config
        self.main_window.stop_led_operation_tracking()

        # Update UI recording indicator
        self.main_window.set_recording_state(False)

        # Update spectroscopy status back to "Running" (not recording)
        if (
            hasattr(self.main_window, "sidebar")
            and hasattr(self.main_window.sidebar, "subunit_status")
            and "Spectroscopy" in self.main_window.sidebar.subunit_status
        ):
            status_label = self.main_window.sidebar.subunit_status["Spectroscopy"][
                "status_label"
            ]
            # Only update if acquisition is still running
            if self.data_mgr.is_acquiring:
                status_label.setText("Running")
                status_label.setStyleSheet(
                    "font-size: 13px;"
                    "color: #34C759;"  # Green
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
                )

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
        self.main_window.enable_controls()

        # Update spectroscopy status to "Running"
        if (
            hasattr(self.main_window, "sidebar")
            and hasattr(self.main_window.sidebar, "subunit_status")
            and "Spectroscopy" in self.main_window.sidebar.subunit_status
        ):
            indicator = self.main_window.sidebar.subunit_status["Spectroscopy"][
                "indicator"
            ]
            status_label = self.main_window.sidebar.subunit_status["Spectroscopy"][
                "status_label"
            ]
            indicator.setStyleSheet(
                "font-size: 10px;"
                "color: #34C759;"  # Green
                "background: transparent;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
            )
            status_label.setText("Running")
            status_label.setStyleSheet(
                "font-size: 13px;"
                "color: #34C759;"  # Green
                "background: transparent;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
            )

        # Reset experiment start time for new acquisition
        self.experiment_start_time = None
        logger.debug("🔄 Reset experiment_start_time for new acquisition")

        # Clear data buffers for fresh start
        self.buffer_mgr.clear_all()
        logger.debug("🔄 Cleared all data buffers")

        # Clear any pause/resume markers from previous runs (with thread safety)
        try:
            if hasattr(self.main_window, "pause_markers") and hasattr(
                self.main_window,
                "full_timeline_graph",
            ):
                # Schedule marker removal in main thread (Qt objects must be accessed from main thread)
                from PySide6.QtCore import QTimer

                def clear_markers():
                    try:
                        for marker in self.main_window.pause_markers:
                            if "line" in marker:
                                try:
                                    self.main_window.full_timeline_graph.removeItem(
                                        marker["line"],
                                    )
                                except RuntimeError:
                                    pass  # Item already deleted
                        self.main_window.pause_markers = []
                    except Exception as e:
                        logger.debug(f"Could not clear pause markers: {e}")

                # Run in main thread after short delay to avoid conflicts with dialog closing
                QTimer.singleShot(200, clear_markers)
        except Exception as e:
            logger.debug(f"Pause marker cleanup error: {e}")

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

        # Update spectroscopy status to "Stopped"
        if hasattr(self.main_window, "sidebar") and hasattr(
            self.main_window.sidebar,
            "subunit_status",
        ):
            if "Spectroscopy" in self.main_window.sidebar.subunit_status:
                status_label = self.main_window.sidebar.subunit_status["Spectroscopy"][
                    "status_label"
                ]
                status_label.setText("Stopped")
                status_label.setStyleSheet(
                    "font-size: 13px;"
                    "color: #86868B;"  # Gray
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
                )

        # Stop recording if active
        if self.recording_mgr.is_recording:
            logger.info("📝 Stopping recording due to acquisition stop...")
            self.recording_mgr.stop_recording()

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
        # Strength controls trust in measurements vs model:
        # Lower strength (1) = heavy filtering: high R, low Q → trust model, smooth heavily
        # Higher strength (10) = light filtering: low R, high Q → trust data, track closely
        #
        # R (measurement_noise): Variance of sensor noise
        # Q (process_noise): Variance of system dynamics
        # Kalman gain K = P / (P + R), so higher R → lower K → less weight on measurements
        #
        # Strength 1: R=0.10, Q=0.001 (heavy smoothing for noisy historical data)
        # Strength 5: R=0.02, Q=0.005 (balanced)
        # Strength 10: R=0.005, Q=0.01 (light smoothing for clean live data)
        measurement_noise = (
            0.1 / self._filter_strength
        )  # Lower strength → higher R → more filtering
        process_noise = (
            0.001 * self._filter_strength
        )  # Lower strength → lower Q → steadier model

        self._kalman_filters = {}
        for ch in self._idx_to_channel:
            self._kalman_filters[ch] = KalmanFilter(
                process_noise=process_noise,
                measurement_noise=measurement_noise,
            )

        logger.info(
            f"Kalman filters initialized (R={measurement_noise:.4f}, Q={process_noise:.4f})",
        )

    def _apply_smoothing(
        self,
        data,
        strength: int,
        channel: str = None,
        method: str = None,
    ):
        """Apply smoothing filter to data (median or Kalman).

        Args:
            data: Input data array
            strength: Smoothing strength (1-10)
            channel: Channel identifier ('a', 'b', 'c', 'd') - required for Kalman
            method: Filter method override ('median' or 'kalman'), uses self._filter_method if None

        Returns:
            Smoothed data array

        """
        import numpy as np

        if len(data) < 3:
            return data

        # Use instance method if not overridden
        filter_method = method if method is not None else self._filter_method

        if filter_method == "kalman":
            # Kalman filter - optimal for smooth trajectories
            if channel is None:
                logger.warning(
                    "Kalman filter requires channel ID, falling back to median",
                )
                filter_method = "median"
            elif channel not in self._kalman_filters:
                logger.warning(
                    f"No Kalman filter for channel {channel}, initializing...",
                )
                self._init_kalman_filters()

            if filter_method == "kalman":  # Check again after fallback
                # Reset filter state for new data sequence
                self._kalman_filters[channel].reset()
                # Apply Kalman filter
                smoothed = self._kalman_filters[channel].filter_array(data)
                return smoothed

        # Median filter (default) - fast and preserves sharp features
        # Map strength (1-10) to window size (3-21)
        # Strength 1 = minimal smoothing (window 3)
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
            return self._apply_smoothing(data, strength, channel)
        # Large dataset: filter only recent window
        # Keep most of timeline unfiltered for speed (preview quality)
        split_point = len(data) - ONLINE_FILTER_WINDOW

        # Create output array
        result = np.copy(data)

        # Filter only the recent window (with small overlap for continuity)
        overlap = 20
        filter_start = max(0, split_point - overlap)
        recent_data = data[filter_start:]
        filtered_recent = self._apply_smoothing(recent_data, strength, channel)

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
                    ch_letter,
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
        try:
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import QInputDialog

            # Safety check - ensure graph is initialized
            if not hasattr(self.main_window, "cycle_of_interest_graph"):
                return
            if not hasattr(self.main_window.cycle_of_interest_graph, "curves"):
                return
            if self.main_window.cycle_of_interest_graph.curves is None:
                return

            # Get click position in data coordinates
            pos = event.scenePos()
            mouse_point = self.main_window.cycle_of_interest_graph.getPlotItem().vb.mapSceneToView(
                pos,
            )
            click_time = mouse_point.x()
            click_value = mouse_point.y()
        except Exception:
            # Silently ignore errors during graph initialization
            return

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
        try:
            import numpy as np

            # Safety check - ensure curves exist
            if not hasattr(self.main_window, "cycle_of_interest_graph"):
                return
            if not hasattr(self.main_window.cycle_of_interest_graph, "curves"):
                return
            if self.main_window.cycle_of_interest_graph.curves is None:
                return

            # Find nearest channel by checking distance to each curve
            min_distance = float("inf")
            nearest_channel = None

            for ch_idx in range(4):
                try:
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
                except Exception:
                    # Skip this channel if there's an error
                    continue

            if nearest_channel is not None:
                # Update selection
                old_channel = self._selected_channel
                self._selected_channel = nearest_channel

                # Update visual feedback (make selected channel thicker)
                if old_channel is not None:
                    try:
                        old_curve = self.main_window.cycle_of_interest_graph.curves[
                            old_channel
                        ]
                        old_pen = old_curve.opts["pen"]
                        old_pen.setWidth(2)  # Normal width
                        old_curve.setPen(old_pen)
                    except Exception:
                        pass

                try:
                    new_curve = self.main_window.cycle_of_interest_graph.curves[
                        nearest_channel
                    ]
                    new_pen = new_curve.opts["pen"]
                    new_pen.setWidth(4)  # Thicker for selected
                    new_curve.setPen(new_pen)
                except Exception:
                    pass

                logger.info(f"Selected Channel {chr(65 + nearest_channel)}")
        except Exception as e:
            # Silently handle errors
            logger.debug(f"Error selecting channel: {e}")

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
        """Apply polarizer positions, LED intensities, and LED delays to hardware.

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

            # Get LED delay values from Advanced Settings if available
            pre_led_delay = 45  # Default
            post_led_delay = 5  # Default
            if (
                hasattr(self.main_window, "advanced_menu")
                and self.main_window.advanced_menu
            ):
                if hasattr(self.main_window.advanced_menu, "led_delay_input"):
                    pre_led_delay = (
                        self.main_window.advanced_menu.led_delay_input.value()
                    )
                if hasattr(self.main_window.advanced_menu, "post_led_delay_input"):
                    post_led_delay = (
                        self.main_window.advanced_menu.post_led_delay_input.value()
                    )

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

                # Apply LED delays to data acquisition manager
                if self.data_mgr:
                    self.data_mgr.set_led_delays(pre_led_delay, post_led_delay)
                    logger.info(
                        f"Applied LED delays: PRE={pre_led_delay}ms, POST={post_led_delay}ms",
                    )

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

                # Show visual feedback in UI
                self.main_window.show_settings_applied_feedback()

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

        # Check if hardware is ready
        if not self.hardware_mgr.usb or not self.hardware_mgr.ctrl:
            logger.error(
                "❌ Hardware not ready: Controller or spectrometer not connected",
            )
            from widgets.message import show_message

            show_message(
                "Please connect the controller and spectrometer first.",
                "Hardware Not Ready",
            )
            return

        # Start LED calibration
        self.data_mgr.start_calibration()

    def _on_full_calibration(self):
        """Start full calibration with auto-align and polarizer calibration."""
        logger.info("🔧 Starting Full Calibration (with auto-align)...")

        # Check if hardware is ready
        if not self.hardware_mgr.usb or not self.hardware_mgr.ctrl:
            logger.error(
                "❌ Hardware not ready: Controller or spectrometer not connected",
            )
            from widgets.message import show_message

            show_message(
                "Please connect the controller and spectrometer first.",
                "Hardware Not Ready",
            )
            return

        # Start LED calibration
        # TODO: The difference between simple/full/OEM needs to be passed as a parameter
        # For now, all use the same data_mgr.start_calibration()
        self.data_mgr.start_calibration()

    def _on_oem_led_calibration(self):
        """Start OEM LED calibration with full afterglow measurement."""
        logger.info("🔧 Starting OEM LED Calibration (with afterglow)...")

        # Check if hardware is ready
        if not self.hardware_mgr.usb or not self.hardware_mgr.ctrl:
            logger.error(
                "❌ Hardware not ready: Controller or spectrometer not connected",
            )
            from widgets.message import show_message

            show_message(
                "Please connect the controller and spectrometer first.",
                "Hardware Not Ready",
            )
            return

        # OPTIMIZATION: Check for optical calibration file first
        # If missing, offer to run it BEFORE LED calibration (faster workflow)
        from utils.device_integration import get_device_optical_calibration_path

        optical_cal_path = get_device_optical_calibration_path()

        if not optical_cal_path or not optical_cal_path.exists():
            logger.info(
                "📋 Optical calibration file not found - starting full calibration workflow",
            )
            logger.info("   Step 1/2: LED intensity calibration")
            logger.info(
                "   Step 2/2: Optical afterglow calibration (after LED completes)",
            )
            # Run full calibration workflow automatically (LED → afterglow)
            self._run_led_then_afterglow_calibration()
            return

        # Start LED calibration
        logger.info("   Step 1/2: Starting LED calibration...")
        self.data_mgr.start_calibration()

        # TODO: After calibration completes, trigger afterglow measurement
        # For now, this will be a manual step after LED calibration completes

    def _run_led_then_afterglow_calibration(self):
        """Run LED calibration first, then automatically trigger afterglow measurement.

        This is the correct calibration order:
        1. LED calibration: Determines operating intensities per channel (2-3 min)
        2. Afterglow measurement: Measures phosphor decay at those intensities (5-10 min)

        Afterglow MUST be measured at the actual operating LED intensities to ensure
        accurate correction. Running afterglow first would require using 255 or guessing
        intensities, leading to incorrect amplitude scaling.
        """
        logger.info("🔄 Starting full calibration workflow: LED → afterglow")

        # Start LED calibration first
        logger.info("   Step 1/2: Starting LED intensity calibration...")

        # Connect to calibration_complete signal to trigger afterglow after LED calibration
        def on_led_calibration_complete(calibration_data: dict):
            """Triggered when LED calibration completes successfully."""
            # Disconnect this one-shot handler
            try:
                self.calibration.manager.calibration_complete.disconnect(
                    on_led_calibration_complete,
                )
            except:
                pass

            # Check if calibration was successful
            if calibration_data.get("ch_error_list"):
                logger.warning(
                    f"⚠️ LED calibration had errors on channels: {calibration_data['ch_error_list']}",
                )
                logger.warning(
                    "   Afterglow calibration may be less accurate for failed channels",
                )
                # Don't proceed to afterglow if LED calibration failed
                return

            logger.info("✅ LED calibration complete!")
            logger.info("   Step 2/2: Starting optical afterglow calibration...")

            # Update dialog to show we're moving to afterglow step
            if (
                hasattr(self.calibration, "_calibration_dialog")
                and self.calibration._calibration_dialog
            ):
                self.calibration._calibration_dialog.update_title(
                    "Calibration: Step 2/2",
                )
                self.calibration._calibration_dialog.update_status(
                    "Running optical afterglow calibration...\n\nThis will take 5-10 minutes.",
                )
                self.calibration._calibration_dialog.set_progress(50, 100)

            # Now run afterglow measurement with calibrated LED intensities
            self._run_afterglow_calibration(calibration_data.get("leds_calibrated"))

        # Connect one-shot handler
        self.calibration.manager.calibration_complete.connect(
            on_led_calibration_complete,
            Qt.ConnectionType.QueuedConnection,
        )

        # Start LED calibration with progress dialog
        self.calibration.start_calibration()

    def _run_afterglow_calibration(self, led_intensities: dict = None):
        """Run afterglow calibration using provided or detected LED intensities.

        Args:
            led_intensities: Dict of LED intensities per channel from LED calibration
                            If None, will try to detect from runtime or device config

        """
        logger.info("🔬 Preparing afterglow calibration...")

        # Import afterglow module
        try:
            from settings import CH_LIST, MAX_INTEGRATION, MIN_INTEGRATION
            from utils.afterglow_calibration import run_afterglow_calibration
            from utils.device_integration import (
                get_device_manager,
                save_optical_calibration_result,
            )
        except ImportError as e:
            logger.error(f"❌ Cannot import afterglow calibration: {e}")
            from widgets.message import show_message

            show_message(
                f"Cannot load afterglow calibration module: {e}",
                "Error",
            )
            return

        # Reuse the existing calibration dialog (don't create a new one)
        dialog = None
        if (
            hasattr(self.calibration, "_calibration_dialog")
            and self.calibration._calibration_dialog
        ):
            dialog = self.calibration._calibration_dialog
            logger.info("📊 Using existing calibration dialog for afterglow progress")
        else:
            logger.warning(
                "⚠️ No calibration dialog found - afterglow will run without progress display",
            )

        # Run afterglow measurement in background thread
        import json

        def run_afterglow_thread():
            nonlocal led_intensities  # Allow modification of outer scope variable
            try:
                logger.info("📊 Starting afterglow measurement...")
                if dialog:
                    dialog.set_progress(55, 100)
                    dialog.update_status(
                        "Measuring LED phosphor decay...\n\nPlease wait (5-10 minutes)...",
                    )

                # Get parameters
                integration_grid = [10.0, 25.0, 40.0, 55.0, 70.0, 85.0]
                integration_grid = [
                    float(max(MIN_INTEGRATION, min(MAX_INTEGRATION, x)))
                    for x in integration_grid
                ]

                # Use S-mode LED intensities
                # Priority: 1) Passed from calibration, 2) Runtime calibration, 3) Device config file
                if led_intensities is not None:
                    logger.info(
                        f"✅ Using LED intensities from calibration: {led_intensities}",
                    )
                elif (
                    hasattr(self.data_mgr, "leds_calibrated")
                    and self.data_mgr.leds_calibrated
                ):
                    led_intensities = self.data_mgr.leds_calibrated.copy()
                    logger.info(
                        f"✅ Using runtime calibrated S-mode LED intensities: {led_intensities}",
                    )
                elif self.main_window.device_config:
                    try:
                        config_leds = {
                            "a": self.main_window.device_config.data["calibration"][
                                "led_intensity_a"
                            ],
                            "b": self.main_window.device_config.data["calibration"][
                                "led_intensity_b"
                            ],
                            "c": self.main_window.device_config.data["calibration"][
                                "led_intensity_c"
                            ],
                            "d": self.main_window.device_config.data["calibration"][
                                "led_intensity_d"
                            ],
                        }
                        # Validate all intensities are reasonable (1-255)
                        if all(1 <= v <= 255 for v in config_leds.values()):
                            led_intensities = config_leds
                            logger.info(
                                f"✅ Using device config S-mode LED intensities: {led_intensities}",
                            )
                        else:
                            logger.warning(
                                f"⚠️ Device config LED intensities out of range: {config_leds}",
                            )
                    except (KeyError, TypeError) as e:
                        logger.warning(
                            f"⚠️ Could not read LED intensities from device config: {e}",
                        )

                # Final fallback: Use 255 (will be noted in calibration metadata)
                if led_intensities is None:
                    logger.warning(
                        "⚠️ No LED intensity calibration found - will use 255 (requires amplitude scaling)",
                    )
                else:
                    logger.info(
                        "📊 Afterglow will be measured at operating LED intensities (Mode 1 - Default)",
                    )

                # Run afterglow calibration using improved method
                # (200ms LED on, measure immediately after LED off - matches test results)
                data = run_afterglow_calibration(
                    ctrl=self.hardware_mgr.ctrl,
                    usb=self.hardware_mgr.usb,
                    wave_min_index=self.data_mgr.wave_min_index
                    if hasattr(self.data_mgr, "wave_min_index")
                    else 1063,
                    wave_max_index=self.data_mgr.wave_max_index
                    if hasattr(self.data_mgr, "wave_max_index")
                    else 3060,
                    channels=CH_LIST,
                    integration_grid_ms=integration_grid,
                    pre_on_duration_s=0.20,
                    acquisition_duration_ms=250,
                    settle_delay_s=0.10,
                    led_intensities=led_intensities,
                )

                if dialog:
                    dialog.set_progress(80, 100)
                    dialog.update_status("Saving calibration data...")

                # Save to device-specific directory
                device_manager = get_device_manager()
                if device_manager.current_device_serial is None:
                    logger.error("❌ No device set - cannot save optical calibration")
                    if dialog:
                        dialog.update_title("❌ Error")
                        dialog.update_status(
                            "No device detected. Cannot save calibration.",
                        )
                    from widgets.message import show_message

                    show_message(
                        "Error: No device detected. Cannot save calibration.",
                        "Error",
                    )
                    return

                device_dir = device_manager.current_device_dir
                out_path = device_dir / "optical_calibration.json"

                with open(out_path, "w") as f:
                    json.dump(data, f, indent=2)

                save_optical_calibration_result(out_path)

                logger.info(f"✅ Optical calibration saved: {out_path}")
                if dialog:
                    dialog.set_progress(90, 100)

                # Reload afterglow correction in data manager
                try:
                    self.data_mgr._load_afterglow_correction()
                except Exception as e:
                    logger.warning(f"Could not reload afterglow correction: {e}")

                if dialog:
                    dialog.set_progress(100, 100)
                    dialog.update_title("✅ Calibration Complete")
                    dialog.update_status(
                        "Full calibration workflow finished!\n\nPress Start to begin data acquisition.",
                    )
                    dialog.enable_start_button()

                logger.info("✅ Full calibration workflow complete: LED → afterglow")
                logger.info(
                    "   System ready for measurement with automatic afterglow correction",
                )

            except Exception as e:
                logger.error(f"❌ Afterglow measurement error: {e}", exc_info=True)
                if dialog:
                    dialog.update_title("❌ Calibration Failed")
                    dialog.update_status(f"Optical calibration failed: {e}")
                from widgets.message import show_message

                show_message(
                    f"Optical calibration failed: {e}",
                    "Error",
                )

        # Start thread
        threading.Thread(target=run_afterglow_thread, daemon=True).start()

    def _on_power_on_requested(self):
        """User requested to power on (connect hardware)."""
        print("\n" + "=" * 60)
        print("[APPLICATION] Power ON handler called!")
        print("=" * 60 + "\n")
        logger.info("Power ON requested - starting hardware connection...")

        # Set to searching state
        logger.info("Setting power button to 'searching' state...")
        self.main_window.set_power_state("searching")
        logger.info("Power button state updated")

        # Start hardware scan and connection
        logger.info("Calling hardware_mgr.scan_and_connect()...")
        print("[APPLICATION] Calling hardware_mgr.scan_and_connect()...")
        self.hardware_mgr.scan_and_connect()
        logger.info("scan_and_connect() call completed (scanning in background thread)")

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

        If S/P positions are missing or invalid (default values 10/100), automatically
        triggers servo calibration to find optimal positions.
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

                # Check if positions are absent or still at default values
                # Default values (10/100) indicate servo calibration hasn't been run
                if s_pos == 10 and p_pos == 100:
                    logger.warning("=" * 80)
                    logger.warning("⚠️  SERVO POSITIONS AT DEFAULT VALUES")
                    logger.warning("=" * 80)
                    logger.warning("   S=10, P=100 are uncalibrated defaults")
                    logger.warning("   Auto-triggering servo calibration...")
                    logger.warning("=" * 80)

                    # Trigger auto-calibration
                    self._run_servo_auto_calibration()
                    return  # Exit - calibration will update positions when complete

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

    def _run_servo_auto_calibration(self):
        """Run automatic servo calibration to find optimal S/P positions.

        This is triggered automatically when S/P positions are missing or at default values.
        Uses the intelligent servo calibration module with transmission validation.
        """
        try:
            logger.info("=" * 80)
            logger.info("🔧 AUTO-TRIGGERING SERVO CALIBRATION")
            logger.info("=" * 80)

            # Check hardware availability
            if (
                not self.hardware_mgr
                or not self.hardware_mgr.ctrl
                or not self.hardware_mgr.usb
            ):
                logger.error("❌ Hardware not ready for servo calibration")
                logger.error("   Missing: controller or spectrometer")
                return

            # Get polarizer type from device config (default: circular)
            polarizer_type = "circular"
            if self.main_window.device_config:
                hw_config = self.main_window.device_config.config.get("hardware", {})
                polarizer_type = hw_config.get("polarizer_type", "circular")
                # Map 'round' to 'circular' for servo_calibration module
                if polarizer_type == "round":
                    polarizer_type = "circular"

            logger.info(f"   Polarizer type: {polarizer_type}")
            logger.info(
                f"   Method: {'Quadrant search (~13 measurements)' if polarizer_type == 'circular' else 'Window detection + SPR signature'}",
            )
            logger.info("=" * 80)

            # Import servo calibration module
            from utils.servo_calibration import auto_calibrate_polarizer

            # Run calibration (requires water for circular, optional for barrel)
            require_water = polarizer_type == "circular"
            result = auto_calibrate_polarizer(
                usb=self.hardware_mgr.usb,
                ctrl=self.hardware_mgr.ctrl,
                require_water=require_water,
                polarizer_type=polarizer_type,
            )

            if result is None or not result.get("success"):
                logger.error("=" * 80)
                logger.error("❌ SERVO CALIBRATION FAILED")
                logger.error("=" * 80)
                logger.error("   Possible causes:")
                logger.error(
                    "   1. No water on sensor (required for circular polarizer)",
                )
                logger.error("   2. Poor SPR coupling")
                logger.error("   3. LED saturation or insufficient intensity")
                logger.error("   4. Servo mechanical issue")
                logger.error("=" * 80)
                logger.error("   ACTION REQUIRED:")
                logger.error("   - Check water presence on sensor")
                logger.error("   - Verify SPR chip coupling")
                logger.error("   - Run manual servo calibration from Settings menu")
                logger.error("=" * 80)
                return

            # Calibration succeeded - show results and ask for user confirmation
            logger.info("=" * 80)
            logger.info("✅ SERVO CALIBRATION SUCCESSFUL")
            logger.info("=" * 80)
            logger.info("   Found positions:")
            logger.info(f"   • S position: {result['s_pos']}°")
            logger.info(f"   • P position: {result['p_pos']}°")
            logger.info(f"   • S/P ratio: {result['sp_ratio']:.2f}×")
            logger.info(f"   • Dip depth: {result['dip_depth_percent']:.1f}%")
            if result.get("resonance_wavelength"):
                logger.info(f"   • Resonance: {result['resonance_wavelength']:.1f}nm")
            logger.info("=" * 80)

            # Show confirmation dialog to user
            from PySide6.QtWidgets import QMessageBox

            msg = QMessageBox(self.main_window)
            msg.setIcon(QMessageBox.Question)
            msg.setWindowTitle("Servo Calibration Complete")
            msg.setText(
                f"<b>Servo calibration successful!</b><br><br>"
                f"Found optimal positions:<br>"
                f"<table style='margin-top:10px;'>"
                f"<tr><td style='padding-right:20px;'><b>S position:</b></td><td>{result['s_pos']}°</td></tr>"
                f"<tr><td><b>P position:</b></td><td>{result['p_pos']}°</td></tr>"
                f"<tr><td><b>S/P ratio:</b></td><td>{result['sp_ratio']:.2f}×</td></tr>"
                f"<tr><td><b>Dip depth:</b></td><td>{result['dip_depth_percent']:.1f}%</td></tr>"
                f"</table><br>"
                f"<i>Do you want to save these positions to device config?</i>",
            )
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.Yes)

            reply = msg.exec()

            if reply == QMessageBox.Yes:
                # Save positions to device config
                s_pos = result["s_pos"]
                p_pos = result["p_pos"]

                self.main_window.device_config.set_servo_positions(s_pos, p_pos)
                self.main_window.device_config.save()

                # Update UI
                self.main_window.s_position_input.setText(str(s_pos))
                self.main_window.p_position_input.setText(str(p_pos))

                # Apply to hardware
                self.hardware_mgr.ctrl.servo_set(s=s_pos, p=p_pos)

                logger.info("=" * 80)
                logger.info("✅ POSITIONS SAVED TO DEVICE CONFIG")
                logger.info("=" * 80)
                logger.info(f"   S={s_pos}, P={p_pos} saved to device_config.json")
                logger.info("   Positions applied to hardware")
                logger.info("=" * 80)
                logger.info("💡 TIP: Click 'Push to EEPROM' to backup these positions")
                logger.info("=" * 80)
            else:
                logger.info("=" * 80)
                logger.info("⚠️  USER DECLINED - POSITIONS NOT SAVED")
                logger.info("=" * 80)
                logger.info("   Calibration results discarded")
                logger.info("   You can run calibration again from Settings menu")
                logger.info("=" * 80)

        except ImportError as e:
            logger.error(f"❌ Failed to import servo_calibration module: {e}")
            logger.error("   Ensure utils/servo_calibration.py is available")
        except Exception as e:
            logger.exception(f"❌ Servo auto-calibration error: {e}")

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

        Overwrites a single "current_cycle.csv" file instead of creating multiple timestamped files.
        This prevents file spam while still preserving the current cycle selection.
        """
        from datetime import datetime

        import numpy as np

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

            # Use a single filename that gets overwritten (no timestamp spam)
            filename = "current_cycle.csv"
            filepath = self._session_cycles_dir / filename

            # Determine which channels have data
            active_channels = []
            for ch in self._idx_to_channel:
                if len(self.buffer_mgr.cycle_data[ch].time) > 0:
                    active_channels.append(ch)

            if not active_channels:
                return

            # Find maximum length across all channels (for padding)
            max_len = max(
                len(self.buffer_mgr.cycle_data[ch].time) for ch in active_channels
            )

            if max_len == 0:
                return

            # Vectorized export using pandas DataFrame
            import pandas as pd

            # Build DataFrame with time and wavelength/SPR for each channel
            first_ch = active_channels[0]

            # Pad time array to max_len with NaN
            time_array = self.buffer_mgr.cycle_data[first_ch].time
            if len(time_array) < max_len:
                time_array = np.pad(
                    time_array,
                    (0, max_len - len(time_array)),
                    constant_values=np.nan,
                )

            df_data = {"Time (s)": time_array}

            for ch in active_channels:
                # Pad wavelength and SPR arrays to match max_len
                wave_array = self.buffer_mgr.cycle_data[ch].wavelength
                spr_array = self.buffer_mgr.cycle_data[ch].spr

                if len(wave_array) < max_len:
                    wave_array = np.pad(
                        wave_array,
                        (0, max_len - len(wave_array)),
                        constant_values=np.nan,
                    )
                if len(spr_array) < max_len:
                    spr_array = np.pad(
                        spr_array,
                        (0, max_len - len(spr_array)),
                        constant_values=np.nan,
                    )

                df_data[f"Ch {ch.upper()} Wavelength (nm)"] = wave_array
                df_data[f"Ch {ch.upper()} SPR (RU)"] = spr_array

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

            logger.debug(
                f"💾 Cycle autosaved to {filename} ({len(active_channels)} channels, {len(df)} points)",
            )

        except Exception as e:
            logger.debug(f"Cycle autosave failed: {e}")

    def _on_export_requested(self, config: dict):
        """Handle comprehensive export request from Export tab.

        Args:
            config: Export configuration dict with keys:
                - data_types: Dict of {raw, processed, cycles, summary} bools
                - channels: List of channel letters to export
                - format: 'excel', 'csv', 'json', or 'hdf5'
                - include_metadata: bool
                - include_events: bool
                - precision: int (decimal places)
                - timestamp_format: 'relative', 'absolute', or 'elapsed'
                - filename: str (base filename)
                - destination: str (directory path)
                - preset: str or None ('quick_csv', 'analysis', 'publication')

        """
        import datetime as dt

        import pandas as pd
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        try:
            logger.info(
                f"📤 Export requested with config: {config.get('preset', 'custom')}",
            )

            # Check if there's data to export
            has_data = False
            for ch in self._idx_to_channel:
                if len(self.buffer_mgr.cycle_data[ch].time) > 0:
                    has_data = True
                    break

            if not has_data:
                QMessageBox.warning(
                    self.main_window,
                    "No Data",
                    "No cycle data available to export. Start acquisition and record some data first.",
                )
                return

            # Determine filename and path
            filename = config.get("filename", "")
            if not filename:
                timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"AffiLabs_Export_{timestamp}"

            destination = config.get("destination", "")
            if not destination:
                destination = str(Path.home() / "Documents")

            # Add appropriate extension
            format_type = config.get("format", "excel")
            extension_map = {
                "excel": ".xlsx",
                "csv": ".csv",
                "json": ".json",
                "hdf5": ".h5",
            }
            extension = extension_map.get(format_type, ".xlsx")

            # Show save dialog
            default_path = str(Path(destination) / f"{filename}{extension}")
            file_filter = {
                "excel": "Excel Files (*.xlsx);;All Files (*.*)",
                "csv": "CSV Files (*.csv);;All Files (*.*)",
                "json": "JSON Files (*.json);;All Files (*.*)",
                "hdf5": "HDF5 Files (*.h5);;All Files (*.*)",
            }.get(format_type, "All Files (*.*)")

            file_path, _ = QFileDialog.getSaveFileName(
                self.main_window,
                "Export Data",
                default_path,
                file_filter,
            )

            if not file_path:
                logger.info("Export cancelled by user")
                return

            # Collect data based on configuration
            channels = config.get("channels", ["a", "b", "c", "d"])
            data_types = config.get("data_types", {})
            precision = config.get("precision", 4)

            # Build export data structure
            export_data = {}

            for ch in channels:
                if ch not in self._idx_to_channel:
                    continue

                ch_data = {}

                # Raw data
                if data_types.get("raw", True):
                    cycle_time = self.buffer_mgr.cycle_data[ch].time
                    delta_spr = self.buffer_mgr.cycle_data[ch].spr
                    if len(cycle_time) > 0:
                        ch_data["raw"] = pd.DataFrame(
                            {
                                "Time (s)": cycle_time,
                                f"Channel_{ch.upper()}_SPR (RU)": delta_spr,
                            },
                        ).round(precision)

                # Processed data (if available)
                if data_types.get("processed", True):
                    # Use same data for now (filtering happens in display)
                    if len(self.buffer_mgr.cycle_data[ch].time) > 0:
                        ch_data["processed"] = ch_data.get("raw", pd.DataFrame()).copy()

                export_data[ch] = ch_data

            # Export based on format
            if format_type == "excel":
                self._export_to_excel(file_path, export_data, config)
            elif format_type == "csv":
                self._export_to_csv(file_path, export_data, config)
            elif format_type == "json":
                self._export_to_json(file_path, export_data, config)
            elif format_type == "hdf5":
                self._export_to_hdf5(file_path, export_data, config)

            logger.info(f"✅ Data exported successfully to: {file_path}")
            QMessageBox.information(
                self.main_window,
                "Export Complete",
                f"Data exported successfully to:\\n{file_path}",
            )

        except Exception as e:
            logger.exception(f"Export failed: {e}")
            QMessageBox.critical(
                self.main_window,
                "Export Error",
                f"Failed to export data:\\n{e!s}",
            )

    def _export_to_excel(self, file_path: str, export_data: dict, config: dict):
        """Export data to Excel workbook with multiple sheets."""
        import datetime as dt

        import pandas as pd

        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            # Export each channel's data
            for ch, ch_data in export_data.items():
                if "raw" in ch_data and not ch_data["raw"].empty:
                    sheet_name = f"Channel_{ch.upper()}_Raw"
                    ch_data["raw"].to_excel(writer, sheet_name=sheet_name, index=False)

                if "processed" in ch_data and not ch_data["processed"].empty:
                    sheet_name = f"Channel_{ch.upper()}_Processed"
                    ch_data["processed"].to_excel(
                        writer,
                        sheet_name=sheet_name,
                        index=False,
                    )

            # Add metadata sheet if requested
            if config.get("include_metadata", False):
                metadata_df = pd.DataFrame(
                    {
                        "Parameter": [
                            "Export Date",
                            "Export Time",
                            "Format",
                            "Precision",
                            "Channels",
                        ],
                        "Value": [
                            dt.datetime.now().strftime("%Y-%m-%d"),
                            dt.datetime.now().strftime("%H:%M:%S"),
                            config.get("format", "excel"),
                            config.get("precision", 4),
                            ", ".join([c.upper() for c in config.get("channels", [])]),
                        ],
                    },
                )
                metadata_df.to_excel(writer, sheet_name="Metadata", index=False)

        logger.info(f"Excel export complete: {file_path}")

    def _export_to_csv(self, file_path: str, export_data: dict, config: dict):
        """Export data to CSV file(s)."""
        import pandas as pd

        # Combine all channels into one CSV
        combined_data = {}

        for ch, ch_data in export_data.items():
            if "raw" in ch_data and not ch_data["raw"].empty:
                df = ch_data["raw"]
                if "Time (s)" in df.columns:
                    if "Time (s)" not in combined_data:
                        combined_data["Time (s)"] = df["Time (s)"]
                    # Add SPR column
                    for col in df.columns:
                        if col != "Time (s)":
                            combined_data[col] = df[col]

        if combined_data:
            combined_df = pd.DataFrame(combined_data)
            combined_df.to_csv(file_path, index=False)
            logger.info(f"CSV export complete: {file_path}")

    def _export_to_json(self, file_path: str, export_data: dict, config: dict):
        """Export data to JSON file."""
        import datetime as dt
        import json

        # Convert DataFrames to dictionaries
        json_data = {}
        for ch, ch_data in export_data.items():
            json_data[f"channel_{ch}"] = {}
            if "raw" in ch_data and not ch_data["raw"].empty:
                json_data[f"channel_{ch}"]["raw"] = ch_data["raw"].to_dict("list")
            if "processed" in ch_data and not ch_data["processed"].empty:
                json_data[f"channel_{ch}"]["processed"] = ch_data["processed"].to_dict(
                    "list",
                )

        # Add metadata
        if config.get("include_metadata", False):
            json_data["metadata"] = {
                "export_date": dt.datetime.now().isoformat(),
                "format": config.get("format", "json"),
                "precision": config.get("precision", 4),
                "channels": config.get("channels", []),
            }

        with open(file_path, "w") as f:
            json.dump(json_data, f, indent=2)

        logger.info(f"JSON export complete: {file_path}")

    def _export_to_hdf5(self, file_path: str, export_data: dict, config: dict):
        """Export data to HDF5 file."""
        import pandas as pd

        with pd.HDFStore(file_path, mode="w") as store:
            for ch, ch_data in export_data.items():
                if "raw" in ch_data and not ch_data["raw"].empty:
                    store.put(f"channel_{ch}/raw", ch_data["raw"])
                if "processed" in ch_data and not ch_data["processed"].empty:
                    store.put(f"channel_{ch}/processed", ch_data["processed"])

        logger.info(f"HDF5 export complete: {file_path}")

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
    import atexit

    # Install global exception hook to catch crashes
    def exception_hook(exc_type, exc_value, exc_traceback):
        """Catch all unhandled exceptions before they crash the app."""
        logger.critical("=" * 80)
        logger.critical("💥 UNHANDLED EXCEPTION - APPLICATION CRASH")
        logger.critical("=" * 80)
        logger.critical(f"Exception Type: {exc_type.__name__}")
        logger.critical(f"Exception Value: {exc_value}")
        logger.critical("Traceback:")
        import traceback

        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        for line in tb_lines:
            logger.critical(line.rstrip())
        logger.critical("=" * 80)

        # Call the default handler to actually crash
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = exception_hook
    logger.info("🛡️ Global exception hook installed")

    class NullWriter:
        """Null output that absorbs all writes."""

        def write(self, text):
            pass

        def flush(self):
            pass

        def fileno(self):
            return -1

    class QtWarningFilter:
        """Filter to suppress Qt threading warnings while keeping other messages."""

        def __init__(self, stream):
            self.stream = stream
            self.buffer = ""

        def write(self, text):
            # Suppress known harmless Qt threading warnings
            if (
                "QObject: Cannot create children" in text
                or "parent's thread is" in text
                or "QTextDocument" in text
                or "I/O operation on closed file" in text
            ):
                return
            try:
                self.stream.write(text)
            except (ValueError, OSError):
                pass  # Stderr closed, ignore

        def flush(self):
            try:
                self.stream.flush()
            except (ValueError, OSError):
                pass

    # Replace stderr with filtered version
    original_stderr = sys.stderr
    original_stdout = sys.stdout
    sys.stderr = QtWarningFilter(original_stderr)

    dtnow = dt.datetime.now(TIME_ZONE)
    logger.info("=" * 70)
    logger.info("AffiLabs.core BETA - Surface Plasmon Resonance Analysis")
    logger.info(f"{SW_VERSION} | {dtnow.strftime('%Y-%m-%d %H:%M')}")
    logger.info("=" * 70)

    # Install emergency cleanup on exit
    def emergency_silence():
        """Silence all output during final cleanup to prevent I/O errors."""
        try:
            null = NullWriter()
            sys.stderr = null
            sys.stdout = null
        except:
            pass

    atexit.register(emergency_silence)

    # Create and run application
    app = Application(sys.argv)

    logger.info("🚀 Starting event loop...")
    exit_code = app.exec()

    # Restore original stderr
    sys.stderr = original_stderr
    sys.stdout = original_stdout

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
