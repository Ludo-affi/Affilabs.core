"""Simplified main launcher for AffiLabs.core with modern UI.

This is a clean rewrite that:
1. Shows the window FIRST
2. Initializes hardware in background threads
3. Uses standard app.exec() instead of asyncio complexity

ARCHITECTURE (4-Layer Clean Separation):
=========================================
Layer 4: UI/Widgets (affilabs_core_ui.py, widgets/) - Display only, no business logic
Layer 3: Coordinators (calibration_service, graph_coordinator, cycle_coordinator) - Orchestration
Layer 2: Core Business Logic (data_acquisition_manager, recording_manager, kinetic_manager) - Processing
Layer 1: Hardware (hardware_manager) - Hardware Abstraction Layer (HAL)

→ Application class (this file) connects layers via signal/slot pattern

6-STEP CALIBRATION FLOW:
========================
1. Hardware Validation & LED Verification - Ensure LEDs off, verify firmware
2. Wavelength Calibration - Read EEPROM, determine ROI (560-720nm)
3. LED Brightness Ranking - Measure at 255, rank weak→strong channels
4. S-Mode Integration Time Optimization - Maximize weakest LED, constrain strongest
5. P-Mode Optimization (Transfer + Boost) - Transfer S-mode + iterative boost
6. S-Mode Reference Signals + QC - Final validation, quality checks

INTEGRATION STATUS: [OK] READY
============================
4-layer architecture enforced:
- Layer 4 (UI): Display only, zero business logic
- Layer 3 (Coordinators): Orchestration via calibration_service, graph_coordinator, cycle_coordinator
- Layer 2 (Core): Business logic in data_acquisition_manager, recording_manager
- Layer 1 (Hardware): HAL abstraction in hardware_manager
All communication via Qt signals/slots (no direct cross-layer calls)

Last Updated: November 22, 2025
"""

import os
import sys

# Add parent directory to path for imports
if __name__ == "__main__":
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

import atexit
import io
import os
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
            # Handle both str and bytes (traceback module can write bytes)
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="replace")
            elif not isinstance(text, str):
                text = str(text)

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

from PySide6.QtCore import Signal

from affilabs.affilabs_core_ui import AffilabsMainWindow
from affilabs.core.calibration_service import CalibrationService
from affilabs.core.cycle_coordinator import CycleCoordinator
from affilabs.core.data_acquisition_manager import DataAcquisitionManager
from affilabs.core.data_buffer_manager import DataBufferManager
from affilabs.core.hardware_manager import HardwareManager
from affilabs.core.kinetic_manager import KineticManager
from affilabs.core.recording_manager import RecordingManager

# Phase 1.4 - Hardware Abstraction Layer
try:
    from affilabs.hardware import (
        DeviceManager,
        IController,
        IServo,
        ISpectrometer,
        SystemState,
        controller_adapter,
        servo_adapter,
        spectrometer_adapter,
    )

    HAL_AVAILABLE = True
except ImportError as e:
    HAL_AVAILABLE = False
    _hal_import_error = str(e)  # Store for later logging
try:
    from affilabs.coordinators.dialog_manager import DialogManager
    from affilabs.coordinators.ui_update_coordinator import AL_UIUpdateCoordinator

    COORDINATORS_AVAILABLE = True
except ImportError as e:
    COORDINATORS_AVAILABLE = False
    _coordinators_import_error = str(e)  # Store for later logging
from affilabs.config import (
    DEFAULT_FILTER_ENABLED,
    DEFAULT_FILTER_STRENGTH,
    LEAK_DETECTION_WINDOW,
    LEAK_THRESHOLD_RATIO,
    SENSORGRAM_DOWNSAMPLE_FACTOR,
    TRANSMISSION_UPDATE_INTERVAL,
    WAVELENGTH_TO_RU_CONVERSION,
)

# Phase 1.1 Domain Models
from affilabs.domain import ProcessedSpectrumData, RawSpectrumData

# Phase 1.2 Business Services
from affilabs.services import BaselineCorrector, TransmissionCalculator
from affilabs.settings import PROFILING_ENABLED, PROFILING_REPORT_INTERVAL, SW_VERSION
from affilabs.utils.logger import logger
from affilabs.utils.performance_profiler import get_profiler, measure
from affilabs.utils.session_quality_monitor import SessionQualityMonitor
from affilabs.viewmodels import (
    CalibrationViewModel,
    DeviceStatusViewModel,
    SpectrumViewModel,
)

# Import TIME_ZONE from settings
try:
    from affilabs.settings import TIME_ZONE
except ImportError:
    # Fallback if TIME_ZONE not available
    import datetime

    try:
        TIME_ZONE = datetime.datetime.now(datetime.UTC).astimezone().tzinfo
    except AttributeError:
        TIME_ZONE = datetime.datetime.now(datetime.UTC).astimezone().tzinfo

import datetime as dt
from typing import Optional

import numpy as np


class Application(QApplication):
    """Main application class that coordinates UI and hardware."""

    # Signal for thread-safe cursor updates (emitted from processing thread)
    cursor_update_signal = Signal(float)  # elapsed_time

    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("AffiLabs.core")
        self.setOrganizationName("Affinite Instruments")

        # Log import status for HAL and Coordinators
        if HAL_AVAILABLE:
            logger.info("[OK] Phase 1.4 HAL available")
        else:
            logger.warning(
                f"[WARN]  Phase 1.4 HAL not available: {_hal_import_error if '_hal_import_error' in globals() else 'unknown error'}",
            )

        if COORDINATORS_AVAILABLE:
            logger.info("[OK] UI Coordinators available")
        else:
            logger.warning(
                f"[WARN]  UI Coordinators not available: {_coordinators_import_error if '_coordinators_import_error' in globals() else 'unknown error'}",
            )

        # Closing flag for cleanup coordination
        self.closing = False

        # Track if device config has been initialized during this session
        self._device_config_initialized = False

        # Apply theme
        self._apply_theme()

        # Create hardware manager (does NOT connect yet)
        self.hardware_mgr = HardwareManager()

        # Phase 1.4 - Initialize Hardware Abstraction Layer alongside legacy manager
        if HAL_AVAILABLE:
            self.device_manager = DeviceManager()
            logger.info("[OK] DeviceManager (HAL) initialized")
        else:
            self.device_manager = None
            logger.info("📌 Using legacy HardwareManager only")

        # Create device status view model (Phase 1.3+1.4 integration)
        # Pass DeviceManager if available for HAL integration
        self.device_status_vm = DeviceStatusViewModel(
            device_manager=self.device_manager if HAL_AVAILABLE else None,
        )
        if HAL_AVAILABLE and self.device_manager:
            logger.info("[OK] DeviceStatusViewModel initialized with HAL DeviceManager")
        else:
            logger.info("[OK] DeviceStatusViewModel initialized (legacy mode)")

        # Create data acquisition manager
        self.data_mgr = DataAcquisitionManager(self.hardware_mgr)

        # Create recording manager
        self.recording_mgr = RecordingManager(self.data_mgr)

        # Create kinetic operations manager
        self.kinetic_mgr = KineticManager(self.hardware_mgr)

        # Create session quality monitor for FWHM tracking
        self.quality_monitor = SessionQualityMonitor(
            device_serial="unknown",  # Will be updated when hardware connects
            session_id=None,  # Auto-generated
        )

        # Create main window (production AffiLabs.core UI)
        self.main_window = AffilabsMainWindow(event_bus=None)

        # Wire up elapsed time getter for pause markers (must use correct experiment time)
        import time

        def get_elapsed_time():
            """Get elapsed time since experiment start for pause markers."""
            if self.experiment_start_time is None:
                return None
            return time.time() - self.experiment_start_time

        self.main_window._get_elapsed_time = get_elapsed_time

        # Ensure calibration runs with visible dialogs in UI launcher
        # Force-disable headless calibration unless explicitly enabled in-app
        try:
            os.environ["CALIBRATION_HEADLESS"] = "0"
        except Exception:
            pass

        # Store reference to app in window for easy access to managers
        self.main_window.app = self

        # Initialize UI update coordinator and dialog manager (Phase 1 Refactoring)
        if COORDINATORS_AVAILABLE:
            self.ui_updates = UIUpdateCoordinator(self, self.main_window)
            self.dialog_manager = DialogManager(self.main_window)
            logger.info(
                "[OK] UI coordinators initialized (UIUpdateCoordinator, DialogManager)",
            )
        else:
            self.ui_updates = None
            self.dialog_manager = None
            logger.warning(
                "[WARN]  Running without UI coordinators (compatibility mode)",
            )

        # Verify spectroscopy plots are available (silent check)
        if not hasattr(self.main_window, "transmission_curves"):
            logger.warning(
                "[WARN] Spectroscopy plots NOT found in main window - graphs will not display",
            )

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

        # QC dialog reference (Layer 1 responsibility)
        self._qc_dialog = None
        self._selected_channel = None
        self._flag_data = []  # List of {channel, time, annotation} dicts

        # LED status monitoring timer (V1.1+ firmware)
        self._led_status_timer = None

        # Calibration state tracking
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

        # Initialize Phase 1.2 business services
        self.transmission_calc = TransmissionCalculator(apply_led_correction=True)
        self.baseline_corrector = BaselineCorrector(method="polynomial", poly_order=1)
        logger.info(
            "[OK] Business services initialized (TransmissionCalculator, BaselineCorrector)",
        )

        # Initialize SpectrumViewModel for each channel (Phase 1.3 integration)
        # These coordinate spectrum processing and display updates
        try:
            from services import SpectrumProcessor

            spectrum_processor = SpectrumProcessor()

            self.spectrum_viewmodels = {
                "a": SpectrumViewModel(),
                "b": SpectrumViewModel(),
                "c": SpectrumViewModel(),
                "d": SpectrumViewModel(),
            }

            # Inject services into each ViewModel
            for channel, vm in self.spectrum_viewmodels.items():
                vm.set_services(
                    self.transmission_calc,
                    self.baseline_corrector,
                    spectrum_processor,
                )

            logger.info("[OK] SpectrumViewModel initialized for all channels")
        except Exception as e:
            logger.warning(f"[WARN]  Failed to initialize SpectrumViewModel: {e}")
            self.spectrum_viewmodels = None

        # Initialize CalibrationViewModel (Phase 1.3 integration)
        # Coordinates calibration workflow and validation
        try:
            from services import CalibrationValidator

            self.calibration_viewmodel = CalibrationViewModel()
            calibration_validator = CalibrationValidator()
            self.calibration_viewmodel.set_validator(calibration_validator)
            logger.info("[OK] CalibrationViewModel initialized with validator")
        except Exception as e:
            logger.warning(f"[WARN]  Failed to initialize CalibrationViewModel: {e}")
            self.calibration_viewmodel = None

        # Initialize debug controller for testing
        from affilabs.utils.debug_controller import DebugController

        self.debug = DebugController(self)

        # Initialize coordinators for better separation of concerns
        # Create coordinators
        self.calibration = CalibrationService(self)
        self.cycles = CycleCoordinator(self)

        # Initialize calibration controller for calibration workflows
        from controllers.calibration_controller import CalibrationController

        self.calibration_ctrl = CalibrationController(self)

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
        # NOTE: Update enable flags moved to AL_UIUpdateCoordinator

        # Performance: Sensorgram downsampling counter
        self._sensorgram_update_counter = 0

        # Pre-cache attribute checks for performance (called frequently)
        # NOTE: Deferred until graphs are loaded (done in _load_deferred_widgets)
        self._has_stop_cursor = False

        # Start processing thread
        self._start_processing_thread()

        # UI update throttling - prevent excessive graph redraws
        from PySide6.QtCore import QTimer

        self._ui_update_timer = QTimer()
        self._ui_update_timer.timeout.connect(self._process_pending_ui_updates)
        self._ui_update_timer.setInterval(
            100,
        )  # 100ms = 10 Hz update rate for smooth live sensorgram
        self._pending_graph_updates = {
            "a": None,
            "b": None,
            "c": None,
            "d": None,
        }  # Store latest data per channel
        # NOTE: _pending_transmission_updates moved to AL_UIUpdateCoordinator
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
                f"⏱ Profiling enabled - stats will print every {PROFILING_REPORT_INTERVAL}s",
            )

        # Connect hardware manager signals to UI
        self._connect_signals()

        # Mark which UI components need deferred loading
        self._deferred_connections_pending = True

        # Show window FIRST (with minimal essential UI)
        logger.info("🪟 Showing main window...")

        # Update splash screen message if available
        if hasattr(self, "update_splash_message"):
            self.update_splash_message("Building interface...")

        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

        # Force immediate UI update - paint window before loading heavy widgets
        QApplication.processEvents()
        logger.info(
            f"[OK] Window visible (minimal UI rendered): {self.main_window.isVisible()}",
        )

        # UI signals are connected by the main UI or after deferred widgets load.
        # Avoid early connections that reference not-yet-built widgets.

        # Connect all signals organized by subsystem (Phase 4 refactoring)
        self._connect_viewmodel_signals()
        self._connect_manager_signals()
        self._connect_ui_event_signals()

        # Connect all signals organized by subsystem (Phase 4 refactoring)
        self._connect_viewmodel_signals()
        self._connect_manager_signals()
        self._connect_ui_event_signals()

        # Load deferred widgets in background (after window is visible)
        QTimer.singleShot(50, self._load_deferred_widgets)

        # DO NOT auto-connect hardware - user must press Power button
        # This allows user to start in offline mode for post-processing
        logger.info(
            "💡 Ready - waiting for user to press Power button to connect hardware...",
        )

    def _load_deferred_widgets(self):
        """Load heavy UI components after window is visible.

        This improves perceived startup time by showing the window immediately,
        then loading expensive components in the background.
        """
        try:
            logger.info("🔄 Loading deferred UI components...")
            # Update splash message
            if hasattr(self, "update_splash_message"):
                self.update_splash_message("Loading graphs...")

            # Load heavy graph widgets (PyQtGraph plots)
            if hasattr(self.main_window, "load_deferred_graphs"):
                self.main_window.load_deferred_graphs()
                logger.info("  [OK] Graph widgets loaded")

            # Process events to ensure graphs are rendered before connecting signals
            QApplication.processEvents()

            # Ensure graphs are fully initialized before connecting signals
            if hasattr(self.main_window, "full_timeline_graph"):
                # Connect cursor movements to update cycle graph
                if hasattr(self.main_window.full_timeline_graph, "start_cursor"):
                    self.main_window.full_timeline_graph.start_cursor.sigPositionChanged.connect(
                        self._update_cycle_of_interest_graph,
                    )
                if hasattr(self.main_window.full_timeline_graph, "stop_cursor"):
                    self.main_window.full_timeline_graph.stop_cursor.sigPositionChanged.connect(
                        self._update_cycle_of_interest_graph,
                    )
                logger.info("  [OK] Timeline graph cursors connected")

            # Connect cursor auto-follow signal (thread-safe)
            self.cursor_update_signal.connect(self._update_stop_cursor_position)
            logger.info("  [OK] Cursor auto-follow connected")

            # Update cached attribute checks now that graphs are loaded
            self._has_stop_cursor = (
                hasattr(self.main_window, "full_timeline_graph")
                and hasattr(self.main_window.full_timeline_graph, "stop_cursor")
                and self.main_window.full_timeline_graph.stop_cursor is not None
            )
            logger.info(f"  [INFO]  Stop cursor available: {self._has_stop_cursor}")

            # Connect polarizer toggle button to servo control
            if hasattr(self.main_window, "polarizer_toggle_btn"):
                self.main_window.polarizer_toggle_btn.clicked.connect(
                    self._on_polarizer_toggle_clicked,
                )
                logger.info("  [OK] Polarizer toggle connected")

            # Connect mouse events for channel selection and flagging
            if hasattr(self.main_window, "cycle_of_interest_graph"):
                self.main_window.cycle_of_interest_graph.scene().sigMouseClicked.connect(
                    self._on_graph_clicked,
                )
                logger.info("  [OK] Graph click events connected")

            # Mark deferred loading as complete
            self._deferred_connections_pending = False

            logger.info("[OK] Deferred UI components loaded successfully")

        except Exception as e:
            logger.error(f"[ERROR] Error loading deferred widgets: {e}", exc_info=True)
            # Non-fatal - app can continue with reduced functionality

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

        # === CALIBRATION MANAGER SIGNALS ===
        # Connect to calibration_complete to update optics_ready status
        self.calibration.calibration_complete.connect(
            self._on_calibration_complete_status_update,
            Qt.QueuedConnection,
        )
        logger.info(
            "Connected: calibration.calibration_complete -> _on_calibration_complete_status_update",
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

    def _on_calibration_complete_status_update(self, calibration_data):
        """Handler for calibration completion - updates optics_ready status.

        Args:
            calibration_data: CalibrationData object (immutable dataclass)

        """
        try:
            # CalibrationData is a dataclass, not a dict - check if channels were calibrated
            optics_ready = (
                len(calibration_data.get_channels()) > 0 if calibration_data else False
            )
            logger.info(
                f"📡 Calibration complete signal received - optics_ready={optics_ready}",
            )

            # Extract channel errors and S-ref QC results
            ch_error_list = []
            s_ref_qc_results = {}
            if calibration_data:
                # Get failed channels from calibration data
                channels = calibration_data.get_channels()
                all_channels = ["a", "b", "c", "d"]
                ch_error_list = [ch for ch in all_channels if ch not in channels]

                # Get S-ref QC results if available
                s_ref_qc_results = getattr(calibration_data, "s_ref_qc_results", {})

            # Update hardware manager calibration status
            # This will set sensor_ready and optics_ready based on calibration results
            self.hardware_mgr.update_calibration_status(
                ch_error_list,
                "full",
                s_ref_qc_results,
            )
            logger.info(
                f"[OK] Hardware manager calibration status updated - ch_errors={ch_error_list}",
            )

            if optics_ready:
                # Update device status UI directly (no hardware scan needed)
                # Calibration has already verified the hardware is working
                status_update = {
                    "sensor_ready": True,
                    "optics_ready": True,
                    "ctrl_type": self.hardware_mgr._get_controller_type(),
                    "spectrometer": self.hardware_mgr.usb.serial_number
                    if self.hardware_mgr.usb
                    else None,
                    "fluidics_ready": self.hardware_mgr.pump is not None,
                }
                self._update_device_status_ui(status_update)
                logger.info(
                    "[OK] Device status updated directly (no hardware scan post-calibration)",
                )

                # Mark calibration as completed (used by power-on workflow)
                self._calibration_completed = True

                logger.info("[OK] Sensor and Optics status updated to READY in UI")
            else:
                # Calibration failed - optics not ready
                logger.warning(
                    "[WARN] Calibration completed but optics not ready (some channels failed)",
                )
                self._update_device_status_ui(
                    {"optics_ready": False, "sensor_ready": True},
                )

        except Exception as e:
            logger.error(
                f"[ERROR] Failed to update optics_ready status: {e}",
                exc_info=True,
            )

    def _on_calibration_complete(self, calibration_data):
        """Handler for calibration_complete signal from CalibrationService.

        This is called when CalibrationService completes calibration and provides
        the immutable CalibrationData model. We apply it to the acquisition manager
        and show the QC dialog (Layer 1 responsibility).

        Args:
            calibration_data: CalibrationData instance with all calibration parameters

        """
        try:
            logger.info("=" * 80)
            logger.info("📊 CALIBRATION COMPLETE - APPLYING TO ACQUISITION MANAGER")
            logger.info("=" * 80)

            # Apply calibration data to acquisition manager (single entry point)
            self.data_mgr.apply_calibration(calibration_data)

            logger.info("[OK] Calibration data applied successfully")
            logger.info("[OK] System ready for live acquisition")
            logger.info("=" * 80)
            logger.info("")

            # Show QC dialog (Layer 1 responsibility - UI operations)
            self._show_qc_dialog(calibration_data)

        except Exception as e:
            logger.error(
                f"[ERROR] Failed to apply calibration data: {e}",
                exc_info=True,
            )
            # Show error dialog to user
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self.main_window,
                "Calibration Error",
                f"Failed to apply calibration data:\n{e}\n\nPlease try calibration again.",
            )

    def _show_qc_dialog(self, calibration_data):
        """Show QC dialog with calibration results (Layer 1 - UI responsibility).

        Args:
            calibration_data: CalibrationData instance

        """
        try:
            from widgets.calibration_qc_dialog import CalibrationQCDialog

            # Convert to dict for QC dialog
            qc_data = calibration_data.to_dict()

            logger.info("📊 Showing QC report dialog (modal)...")

            # Create and show dialog (modal, blocks until closed)
            self._qc_dialog = CalibrationQCDialog.show_qc_report(
                parent=self.main_window,
                calibration_data=qc_data,
            )

            logger.info("[OK] QC report displayed and closed (modal)")
            logger.info(
                "💡 System ready - Click START button to begin live acquisition",
            )

        except Exception as e:
            logger.error(f"[ERROR] Failed to show QC report: {e}", exc_info=True)

    def _connect_ui_signals(self):
        """Connect UI signals after handler method is defined."""
        # === UI SIGNALS (user requests) ===
        self.main_window.power_on_requested.connect(self._on_power_on_requested)
        logger.info(
            "Connected: main_window.power_on_requested -> _on_power_on_requested",
        )

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
        bypass_calibration_shortcut.activated.connect(self.debug.bypass_calibration)
        logger.info(f"[OK] Ctrl+Shift+C registered: {bypass_calibration_shortcut}")
        logger.info(f"   Context: {bypass_calibration_shortcut.context()}")
        logger.info(f"   Key: {bypass_calibration_shortcut.key().toString()}")

        # Ctrl+Shift+S: Start simulation mode (inject fake spectra)
        simulation_shortcut = QShortcut(QKeySequence("Ctrl+Shift+S"), self.main_window)
        simulation_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        simulation_shortcut.activated.connect(self.debug.start_simulation)
        logger.info(f"[OK] Ctrl+Shift+S registered: {simulation_shortcut}")
        logger.info(f"   Context: {simulation_shortcut.context()}")
        logger.info(f"   Key: {simulation_shortcut.key().toString()}")

        # Ctrl+Shift+1: Single data point test (minimal test)
        single_point_shortcut = QShortcut(
            QKeySequence("Ctrl+Shift+1"),
            self.main_window,
        )
        single_point_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        single_point_shortcut.activated.connect(self.debug.send_single_data_point)
        logger.info(f"[OK] Ctrl+Shift+1 registered: {single_point_shortcut}")
        logger.info(f"   Context: {single_point_shortcut.context()}")
        logger.info(f"   Key: {single_point_shortcut.key().toString()}")

        logger.info("=" * 80)
        logger.info("🔧 DEBUG: Ctrl+Shift+S to start spectrum simulation")

        self.main_window.acquisition_pause_requested.connect(
            self._on_acquisition_pause_requested,
        )
        self.main_window.export_requested.connect(self._on_export_requested)

        # === UI CONTROL SIGNALS (direct connections - not through event bus) ===
        self._connect_ui_control_signals()

        logger.info("[OK] All signal connections registered")

    def _check_hardware_ready(self, operation_name: str = "operation") -> bool:
        """Delegate to calibration controller."""
        return self.calibration_ctrl.check_hardware_ready(operation_name)

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

        # NOTE: Polarizer Calibration button is connected in affilabs_core_ui.py
        # If available, connect here to ensure functionality
        if hasattr(ui, "polarizer_calibration_btn"):
            ui.polarizer_calibration_btn.clicked.connect(self._on_polarizer_calibration)
            logger.info("[OK] Connected Polarizer Calibration button to handler")

        # OEM Calibration button (direct connection)
        ui.oem_led_calibration_btn.clicked.connect(self._on_oem_led_calibration)

        # Advanced Settings dialog - connect optical calibration signal
        if hasattr(ui, "advanced_menu") and ui.advanced_menu is not None:
            if hasattr(ui.advanced_menu, "measure_afterglow_sig"):
                ui.advanced_menu.measure_afterglow_sig.connect(
                    self._on_oem_led_calibration,
                )
                logger.info(
                    "[OK] Connected Advanced Settings optical calibration signal",
                )

        # Start button (direct connection)
        ui.sidebar.start_cycle_btn.clicked.connect(self._on_start_button_clicked)

    def _connect_viewmodel_signals(self):
        """Connect ViewModel signals to handlers (Phase 4 refactoring).

        Groups all ViewModel signal connections for better organization.
        """
        # === DEVICE STATUS VIEWMODEL ===
        self.device_status_vm.device_connected.connect(self._on_vm_device_connected)
        self.device_status_vm.device_disconnected.connect(
            self._on_vm_device_disconnected,
        )
        self.device_status_vm.device_error.connect(self._on_vm_device_error)
        self.device_status_vm.overall_status_changed.connect(self._on_vm_status_changed)
        logger.info("[OK] DeviceStatusViewModel signals connected")

        # === SPECTRUM VIEWMODELS ===
        if self.spectrum_viewmodels:
            for channel, vm in self.spectrum_viewmodels.items():
                vm.spectrum_updated.connect(
                    lambda ch, wl, trans, channel=channel: self._on_spectrum_updated(
                        channel,
                        wl,
                        trans,
                    ),
                )
                vm.raw_spectrum_updated.connect(
                    lambda ch, wl, raw, channel=channel: self._on_raw_spectrum_updated(
                        channel,
                        wl,
                        raw,
                    ),
                )
            logger.info("[OK] SpectrumViewModel signals connected for all channels")

        # === CALIBRATION VIEWMODEL ===
        if self.calibration_viewmodel:
            self.calibration_viewmodel.calibration_started.connect(
                self._on_cal_vm_started,
            )
            self.calibration_viewmodel.calibration_progress.connect(
                self._on_cal_vm_progress,
            )
            self.calibration_viewmodel.calibration_complete.connect(
                self._on_cal_vm_complete,
            )
            self.calibration_viewmodel.calibration_failed.connect(
                self._on_cal_vm_failed,
            )
            self.calibration_viewmodel.validation_complete.connect(
                self._on_cal_vm_validation_complete,
            )
            logger.info("[OK] CalibrationViewModel signals connected")

    def _connect_manager_signals(self):
        """Connect manager/service signals to handlers (Phase 4 refactoring).

        Groups all manager signal connections including hardware, acquisition,
        calibration, recording, and kinetic managers.
        """
        # === CALIBRATION SERVICE ===
        self.calibration.calibration_complete.connect(self._on_calibration_complete)
        logger.info("[OK] CalibrationService signals connected")

        # Manager signals are connected in _connect_signals() (called from __init__)
        # This method is reserved for future manager signal organization

    def _connect_ui_event_signals(self):
        """Connect UI event signals (Phase 4 refactoring).

        Groups all UI interaction signals including tab changes, page changes,
        and graph interactions.
        """
        # === TAB/PAGE CHANGE SIGNALS ===
        if hasattr(self.main_window, "tab_widget"):
            self.main_window.tab_widget.currentChanged.connect(self._on_tab_changing)
        if hasattr(self.main_window, "sidebar") and hasattr(
            self.main_window.sidebar,
            "tabs",
        ):
            self.main_window.sidebar.tabs.currentChanged.connect(self._on_tab_changing)
        if hasattr(self.main_window, "content_stack"):
            self.main_window.content_stack.currentChanged.connect(self._on_page_changed)
        logger.info("[OK] UI event signals connected (tabs/pages)")

    # === DEBUG / TEST HELPERS ===
    # Debug methods moved to utils/debug_controller.py for separation of concerns.
    # Access via self.debug.method_name():
    #   - self.debug.bypass_calibration() - Ctrl+Shift+C
    #   - self.debug.start_simulation() - Ctrl+Shift+S
    #   - self.debug.send_single_data_point() - Ctrl+Shift+1
    #   - self.debug.test_acquisition_thread() - Ctrl+Shift+T
    #   - self.debug.simulate_calibration_success()

    def _on_start_button_clicked(self):
        """User clicked Start button - begin live data acquisition."""
        logger.info("🚀 User requested start - beginning acquisition")

        # Check if already acquiring - if so, just open the live data dialog
        if self.data_mgr and self.data_mgr._acquiring:
            logger.info("Acquisition already running - opening live data dialog")
            try:
                from live_data_dialog import LiveDataDialog

                if self._live_data_dialog is None:
                    self._live_data_dialog = LiveDataDialog(parent=self.main_window)

                # Load reference spectra
                cd = getattr(self.data_mgr, "calibration_data", None)
                if (
                    cd
                    and getattr(cd, "s_pol_ref", None)
                    and getattr(cd, "wavelengths", None) is not None
                ):
                    self._live_data_dialog.set_reference_spectra(
                        cd.s_pol_ref,
                        cd.wavelengths,
                    )

                self._live_data_dialog.show()
                self._live_data_dialog.raise_()
                self._live_data_dialog.activateWindow()
                logger.info("[OK] Live data dialog opened")
            except Exception as e:
                logger.exception(f"Failed to open live data dialog: {e}")
            return

        # PHASE 1: Validate hardware connection and calibration
        logger.info("[SEARCH] PHASE 1: Checking hardware status...")
        try:
            if self.hardware_mgr.ctrl:
                logger.info("   [OK] Controller connected")
            else:
                logger.warning("   [WARN] No controller found")

            if self.hardware_mgr.usb:
                logger.info("   [OK] Spectrometer connected")
            else:
                logger.warning("   [WARN] No spectrometer found")

            # Check if calibrated and get settings (from CalibrationData)
            if (
                self.data_mgr
                and self.data_mgr.calibrated
                and getattr(self.data_mgr, "calibration_data", None)
            ):
                logger.info("   [OK] System calibrated")
                cd = self.data_mgr.calibration_data
                # Prefer P-mode integration time, fall back to S-mode, then default
                integration_time = (
                    getattr(cd, "p_integration_time", None)
                    or getattr(cd, "s_mode_integration_time", None)
                    or 40
                )
                # Use calibrated P-mode LED intensities if available
                led_intensities = getattr(cd, "p_mode_intensities", {}) or {}
            else:
                logger.info(
                    "   [INFO] System not calibrated (using bypass mode defaults)",
                )
                integration_time = 40
                led_intensities = {"a": 255, "b": 150, "c": 150, "d": 255}

            logger.info("[OK] Hardware validation complete")
        except Exception as e:
            logger.exception(f"[ERROR] Hardware validation failed: {e}")
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
                logger.info("   [OK] Polarizer configured")
            else:
                logger.warning("   [WARN] Controller not available")
        except Exception as e:
            logger.exception(f"[ERROR] Polarizer configuration failed: {e}")

        # 2B: Integration time
        try:
            usb = self.hardware_mgr.usb
            if usb and hasattr(usb, "set_integration"):
                logger.info(f"   Setting integration time: {integration_time}ms...")
                usb.set_integration(integration_time)
                logger.info("   [OK] Integration time configured")
            else:
                logger.warning("   [WARN] Spectrometer not available")
        except Exception as e:
            logger.exception(f"[ERROR] Integration time configuration failed: {e}")

        # 2C: LED intensities
        try:
            ctrl = self.hardware_mgr.ctrl
            if ctrl and hasattr(ctrl, "set_intensity"):
                logger.info(f"   Setting LED intensities: {led_intensities}...")
                for channel, intensity in led_intensities.items():
                    ctrl.set_intensity(channel, intensity)
                logger.info("   [OK] LED intensities configured")
            else:
                logger.warning("   [WARN] Controller not available")
        except Exception as e:
            logger.exception(f"[ERROR] LED configuration failed: {e}")

        logger.info("[OK] Hardware configuration complete")

        # PHASE 3: Start data acquisition thread
        logger.info("🚀 PHASE 3: Starting data acquisition thread...")
        try:
            # This is the critical step - starting the actual acquisition
            self.data_mgr.start_acquisition()
            logger.info("[OK] Data acquisition thread started successfully")
        except Exception as e:
            logger.exception(f"[ERROR] Failed to start acquisition: {e}")
            from widgets.message import show_message

            show_message(f"Failed to start acquisition:\n{e}", msg_type="Error")
            return

        # PHASE 4: Open live data dialog (NO automatic recording)
        logger.info("📊 Opening live data dialog...")
        try:
            from live_data_dialog import LiveDataDialog

            if self._live_data_dialog is None:
                self._live_data_dialog = LiveDataDialog(parent=self.main_window)

            # Load reference spectra from calibration into the dialog (unified source)
            cd = getattr(self.data_mgr, "calibration_data", None)
            if (
                cd
                and getattr(cd, "s_pol_ref", None)
                and getattr(cd, "wavelengths", None) is not None
            ):
                self._live_data_dialog.set_reference_spectra(
                    cd.s_pol_ref,
                    cd.wavelengths,
                )
                try:
                    logger.info(
                        f"[OK] Loaded S-mode reference spectra: {list(cd.s_pol_ref.keys())}",
                    )
                except Exception:
                    pass

            self._live_data_dialog.show()
            self._live_data_dialog.raise_()
            self._live_data_dialog.activateWindow()
            logger.info("[OK] Live data dialog opened")
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
            logger.info("[OK] UI state updated")
        except Exception as e:
            logger.exception(f"Failed to update UI: {e}")

        logger.info("=" * 80)
        logger.info("[OK] LIVE ACQUISITION STARTED - View data in dialog")
        logger.info("=" * 80)

    def _on_scan_requested(self):
        """User clicked Scan button in UI."""
        logger.info("User requested hardware scan")
        self.hardware_mgr.scan_and_connect()

    def _on_hardware_connected(self, status: dict):
        """Hardware connection completed and update Device Status UI."""
        # Deduplicate rapid-fire signals (prevent double-processing within 500ms)
        import time

        current_time = time.time()
        if hasattr(self, "_last_hw_callback_time"):
            time_since_last = current_time - self._last_hw_callback_time
            if time_since_last < 0.5:  # Less than 500ms since last callback
                logger.debug(
                    f"📊 Skipping duplicate hardware callback ({time_since_last*1000:.0f}ms since last)",
                )
                return
        self._last_hw_callback_time = current_time

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
                f"[OK] Scan SUCCESSFUL - found valid hardware: {', '.join(valid_hardware)}",
            )
            self.main_window.set_power_state("connected")
        else:
            logger.warning("[WARN] Scan FAILED - no valid hardware combinations found")
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
            from affilabs.utils.device_integration import (
                initialize_device_on_connection,
            )

            # Create a mock USB device object with serial number for device initialization
            class MockUSBDevice:
                def __init__(self, serial):
                    self.serial_number = serial

            mock_usb = MockUSBDevice(device_serial)
            device_dir = initialize_device_on_connection(mock_usb)

            if device_dir:
                logger.info(f"[OK] Device initialized: {device_dir}")

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
                    from affilabs.utils.device_special_cases import apply_special_case

                    # Apply special case to the loaded device config
                    self.main_window.device_config = apply_special_case(
                        special_case,
                        self.main_window.device_config,
                    )
                    logger.info("[OK] Special case configuration applied to device")

            # Mark as initialized to prevent redundant reloads
            self._device_config_initialized = True
        elif device_serial and self._device_config_initialized:
            logger.debug(
                "Hardware status update received (not initial connection) - skipping calibration check",
            )
        else:
            # No spectrometer detected - this is a new OEM device that needs provisioning
            logger.warning("[WARN] No spectrometer serial in hardware status")

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
            f"[SEARCH] Calling _update_device_status_ui with optics_ready={status.get('optics_ready')}, sensor_ready={status.get('sensor_ready')}",
        )
        self._update_device_status_ui(status)

        # Start LED status monitoring timer (V1.1+ firmware)
        if not self._device_config_initialized:
            self._start_led_status_monitoring()

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
        calibration_dialog = self.calibration.dialog if self.calibration else None
        if calibration_dialog and not calibration_dialog._is_closing:
            if status.get("ctrl_type") and status.get("spectrometer"):
                # Both hardware components detected
                logger.info("[OK] Calibration dialog updated: Hardware detected")
                calibration_dialog.update_status(
                    f"Hardware detected:\n"
                    f"• Controller: {status.get('ctrl_type')}\n"
                    f"• Spectrometer: Connected\n\n"
                    f"Click Start to begin calibration.",
                )
            elif status.get("spectrometer") and not status.get("ctrl_type"):
                logger.warning("[WARN] Spectrometer found but controller missing")
                calibration_dialog.update_status(
                    "[WARN] Controller not detected\n\n"
                    "Please connect the SPR controller\n"
                    "to continue calibration.",
                )
            elif status.get("ctrl_type") and not status.get("spectrometer"):
                logger.warning("[WARN] Controller found but spectrometer missing")
                calibration_dialog.update_status(
                    "[WARN] Spectrometer not detected\n\n"
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
                logger.info("=" * 80)
                logger.info("🎯 STARTING 6-STEP CALIBRATION FLOW")
                logger.info("=" * 80)
                logger.info("   Hardware Detected:")
                logger.info(f"   • Controller: {status.get('ctrl_type')}")
                logger.info("   • Spectrometer: Connected")
                logger.info("")
                logger.info("   Calibration Steps:")
                logger.info("   1. Hardware Validation & LED Verification")
                logger.info("   2. Wavelength Calibration")
                logger.info("   3. LED Brightness Ranking")
                logger.info("   4. S-Mode Integration Time Optimization")
                logger.info("   5. P-Mode Optimization (Transfer + Boost)")
                logger.info("   6. S-Mode Reference Signals + QC")
                logger.info("=" * 80)

                # OPTIMIZATION: Check for optical calibration file first
                # If missing, run full calibration workflow automatically (LED → afterglow)
                from affilabs.utils.device_integration import (
                    get_device_optical_calibration_path,
                )

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
                    f"[SEARCH] TYPE CHECK: self.calibration = {type(self.calibration)}",
                )
                logger.info(f"[SEARCH] OBJECT: {self.calibration}")
                logger.info("=" * 80)
                self.calibration.start_calibration()
            elif (
                status.get("ctrl_type")
                and status.get("spectrometer")
                and self._calibration_completed
            ):
                logger.info("[OK] Calibration already completed - ready for live data")
            elif status.get("spectrometer") and not status.get("ctrl_type"):
                logger.warning("[WARN] Spectrometer detected but no controller found")
                logger.info("📋 Controller is required for calibration")
                logger.info("📋 Please connect the controller to perform calibration")
            elif status.get("ctrl_type") and not status.get("spectrometer"):
                logger.warning("[WARN] Controller detected but no spectrometer found")
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

        # Stop LED status monitoring
        self._stop_led_status_monitoring()

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

    def _start_led_status_monitoring(self):
        """Start periodic LED status monitoring timer (V1.1+ firmware)."""
        if self._led_status_timer is not None:
            return  # Already running

        # Check if hardware supports LED queries
        if not self.hardware_mgr or not self.hardware_mgr.ctrl:
            return

        if not hasattr(self.hardware_mgr.ctrl, "get_all_led_intensities"):
            logger.debug("LED status monitoring not available (firmware < V1.1)")
            return

        from PyQt5.QtCore import QTimer

        self._led_status_timer = QTimer()
        self._led_status_timer.timeout.connect(self._update_led_status_display)
        self._led_status_timer.start(2000)  # Update every 2 seconds
        logger.info("[OK] LED status monitoring started (2s interval)")

    def _stop_led_status_monitoring(self):
        """Stop LED status monitoring timer."""
        if self._led_status_timer is not None:
            self._led_status_timer.stop()
            self._led_status_timer.deleteLater()
            self._led_status_timer = None
            logger.info("LED status monitoring stopped")

    def _update_led_status_display(self):
        """Query hardware for LED intensities and update UI display."""
        try:
            if not self.hardware_mgr or not self.hardware_mgr.ctrl:
                return

            # Get current LED intensities from hardware
            led_intensities = self.hardware_mgr.ctrl.get_all_led_intensities()

            if led_intensities:
                # Update device status widget
                if hasattr(self.main_window, "sidebar"):
                    if hasattr(self.main_window.sidebar, "device_widget"):
                        if hasattr(
                            self.main_window.sidebar.device_widget,
                            "device_status_widget",
                        ):
                            self.main_window.sidebar.device_widget.device_status_widget.update_led_status(
                                led_intensities,
                            )

        except Exception as e:
            # Silent fail - don't disrupt normal operation
            logger.debug(f"LED status update failed: {e}")

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

    @property
    def transmission_dialog(self):
        """Get transmission dialog via DialogManager."""
        return self.dialog_manager.get_transmission_dialog()

    @property
    def live_data_dialog(self):
        """Get live data dialog via DialogManager."""
        return self.dialog_manager.get_live_data_dialog()

    def show_transmission_dialog(self):
        """Show the transmission spectrum dialog."""
        self.dialog_manager.show_transmission_dialog()

    # === Data Acquisition Callbacks ===

    def _start_processing_thread(self):
        """Start dedicated processing thread for spectrum data (Phase 3 optimization).

        Separates acquisition from processing to prevent jitter in acquisition timing.
        Acquisition thread only queues data, processing thread handles all analysis.
        """
        print("\n🔧 [THREAD-INIT] Starting processing thread...")
        self._processing_active = True
        self._processing_thread = threading.Thread(
            target=self._processing_worker,
            name="SpectrumProcessing",
            daemon=True,
        )
        self._processing_thread.start()
        print(
            f"   [OK] Thread started: alive={self._processing_thread.is_alive()}, name={self._processing_thread.name}",
        )
        logger.info("[OK] Processing thread started (acquisition/processing separated)")

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
            logger.info("[OK] Processing thread stopped")

    def _processing_worker(self):
        """Worker thread for processing spectrum data (Phase 3 optimization).

        Runs in dedicated thread to prevent processing from affecting acquisition timing.
        Processes data from queue and updates buffers/graphs.
        """
        import queue

        print("\n🟢 [WORKER-THREAD] Processing worker entered! Thread is running...")
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
                logger.error(f"[ERROR] Processing worker error: {e}", exc_info=True)

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
                        f"[WARN] Spectrum queue full - {self._queue_stats['dropped']} frames dropped",
                    )

        except Exception as e:
            logger.exception(f"Spectrum acquisition error: {e}")

    def _process_spectrum_data(self, data: dict):
        """Process spectrum data in dedicated worker thread (Phase 3 optimization).

        All the actual processing happens here, not in acquisition callback.
        This includes: intensity monitoring, transmission updates, buffer updates, etc.
        """
        try:
            channel = data["channel"]  # 'a', 'b', 'c', 'd'
            print(
                f"\n🟣 [WORKER-PROCESS] Processing data for channel {channel.upper()}",
            )
            wavelength = data["wavelength"]  # nm
            intensity = data.get("intensity", 0)  # Raw intensity
            timestamp = data["timestamp"]
            elapsed_time = data["elapsed_time"]
            is_preview = data.get(
                "is_preview",
                False,
            )  # Interpolated preview vs real data

            # Append to timeline data buffers (RAW data - unfiltered)
            try:
                self.buffer_mgr.append_timeline_point(
                    channel,
                    elapsed_time,
                    wavelength,
                    timestamp,
                )
            except Exception as e:
                logger.exception(
                    f"[ERROR] Buffer append failed for channel {channel}: {e}",
                )

            # Queue transmission spectrum update (for dialog display) ONLY if we have full spectrum
            # THROTTLED: Only update every N seconds per channel
            has_raw_data = data.get("raw_spectrum") is not None
            has_transmission = data.get("transmission_spectrum") is not None
            time_since_last_update = timestamp - self._last_transmission_update.get(
                channel,
                0,
            )
            should_update_transmission = (
                time_since_last_update >= TRANSMISSION_UPDATE_INTERVAL
            )

            # DEBUG: Log transmission update condition
            print(
                f"\n[SEARCH] [TRANS-COND] Ch {channel.upper()}: has_raw={has_raw_data}, has_trans={has_transmission}, should_update={should_update_transmission} (time={time_since_last_update:.3f}s >= {TRANSMISSION_UPDATE_INTERVAL}s)",
            )

            if has_raw_data and has_transmission and should_update_transmission:
                print(
                    f"   [OK] Calling _queue_transmission_update for channel {channel.upper()}",
                )
                try:
                    self._queue_transmission_update(channel, data)
                    self._last_transmission_update[channel] = timestamp

                    # Update Sensor IQ display if available
                    if "sensor_iq" in data:
                        self._update_sensor_iq_display(channel, data["sensor_iq"])

                except Exception as e:
                    logger.exception(
                        f"[ERROR] Transmission queue error for channel {channel}: {e}",
                    )

            # Cursor auto-follow (thread-safe via signal)
            # Emit signal to update cursor on main thread
            try:
                self.cursor_update_signal.emit(elapsed_time)
            except Exception as e:
                logger.warning(f"Cursor update signal emit failed: {e}")

        except Exception as e:
            # TOP-LEVEL CATCH: Prevent any exception from killing the processing thread
            logger.exception(f"[ERROR] Spectrum processing error: {e}")

        # Queue graph update instead of immediate update (throttled by timer)
        # DOWNSAMPLED: Only queue every Nth update
        self._sensorgram_update_counter += 1
        should_update_graph = (
            self._sensorgram_update_counter % SENSORGRAM_DOWNSAMPLE_FACTOR == 0
        )

        if should_update_graph:
            try:
                # Queue the update (main thread will check if live data is enabled)
                self._pending_graph_updates[channel] = {
                    "elapsed_time": elapsed_time,
                    "channel": channel,
                }
            except Exception as e:
                logger.exception(
                    f"[ERROR] Graph update error for channel {channel}: {e}",
                )

        # Record data point if recording is active
        try:
            if self.recording_mgr.is_recording:
                # Build data point with all channels (use latest value for each)
                data_point = {}
                for ch in self._idx_to_channel:
                    latest_value = self.buffer_mgr.get_latest_value(ch)
                    data_point[f"channel_{ch}"] = (
                        latest_value if latest_value is not None else ""
                    )

                self.recording_mgr.record_data_point(data_point)
        except Exception as e:
            logger.exception(f"[ERROR] Recording error for channel {channel}: {e}")

        # Update cycle of interest graph (bottom graph) - handled by UI refresh timer

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
                        f"[WARN] Possible optical leak detected in channel {channel.upper()}: "
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
        # DEBUG: Log flags that control updates
        print(
            f"\n🎯 [UPDATE-FLAGS] Ch {channel.upper()}: transmission_enabled={self.ui_updates._transmission_updates_enabled}, raw_enabled={self.ui_updates._raw_spectrum_updates_enabled}",
        )

        # Skip if updates are disabled (performance optimization) - check coordinator flags
        if (
            not self.ui_updates._transmission_updates_enabled
            and not self.ui_updates._raw_spectrum_updates_enabled
        ):
            print("   [WARN] BOTH FLAGS DISABLED - SKIPPING UPDATE")
            return

        transmission = data.get("transmission_spectrum")
        # Get raw spectrum using unified field name
        raw_spectrum = data.get("raw_spectrum")

        # Fallback: calculate transmission if not provided
        if transmission is None and raw_spectrum is not None and len(raw_spectrum) > 0:
            if (
                self.data_mgr.calibration_data
                and self.data_mgr.calibration_data.s_pol_ref
            ):
                ref_spectrum = self.data_mgr.calibration_data.s_pol_ref[channel]

                # Get LED intensities for this channel
                p_led = self.data_mgr.calibration_data.p_mode_intensities.get(channel)
                s_led = self.data_mgr.calibration_data.s_mode_intensities.get(channel)

                # Use SpectrumViewModel if available (Phase 1.3 integration)
                if self.spectrum_viewmodels and channel in self.spectrum_viewmodels:
                    # Get wavelengths
                    wavelengths = data.get("wavelengths", self.data_mgr.wave_data)
                    if wavelengths is None and not data.get("simulated", False):
                        logger.error(
                            f"[HARDWARE ERROR] No wavelength data for channel {channel}!",
                        )
                        return

                    # Process through ViewModel (handles services pipeline)
                    # This will emit spectrum_updated signal which we handle below
                    self.spectrum_viewmodels[channel].process_raw_spectrum(
                        channel=channel,
                        wavelengths=wavelengths,
                        p_spectrum=raw_spectrum,
                        s_reference=ref_spectrum,
                        p_led_intensity=p_led,
                        s_led_intensity=s_led,
                    )
                    return  # ViewModel will handle the update via signals
                # Fallback: Direct service calls (if ViewModel not available)
                transmission = self.transmission_calc.calculate(
                    p_spectrum=raw_spectrum,
                    s_reference=ref_spectrum,
                    p_led_intensity=p_led,
                    s_led_intensity=s_led,
                )

                # Apply baseline correction
                if transmission is not None and len(transmission) > 0:
                    try:
                        transmission = self.baseline_corrector.correct(transmission)
                    except Exception as e:
                        logger.warning(
                            f"Baseline correction failed for channel {channel}: {e}",
                        )

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

            # Queue for batch processing via AL_UIUpdateCoordinator
            self.ui_updates.queue_transmission_update(
                channel,
                wavelengths,
                transmission,
                raw_spectrum,
            )
            logger.debug(
                f"[TRANS-UPDATE] Queued ch {channel}: {len(transmission)} points, λ={wavelengths[0]:.1f}-{wavelengths[-1]:.1f}nm",
            )

            # === PHASE 1.1 INTEGRATION: Create domain models for type safety ===
            # Create RawSpectrumData domain model
            raw_spectrum_model = self._dict_to_raw_spectrum(channel, data)
            if raw_spectrum_model:
                logger.debug(
                    f"[Domain] Created RawSpectrumData for channel {channel}: "
                    f"{raw_spectrum_model.num_points} points, "
                    f"integration_time={raw_spectrum_model.integration_time}ms",
                )

            # Create ProcessedSpectrumData domain model
            processed_spectrum_model = self._dict_to_processed_spectrum(
                channel,
                data,
                transmission,
            )
            if processed_spectrum_model:
                logger.debug(
                    f"[Domain] Created ProcessedSpectrumData for channel {channel}: "
                    f"transmission range={processed_spectrum_model.transmission_range}, "
                    f"mean={processed_spectrum_model.mean_transmission:.2f}%",
                )

    def _update_sensor_iq_display(self, channel: str, sensor_iq):
        """Queue Sensor IQ display update - delegated to AL_UIUpdateCoordinator.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            sensor_iq: SensorIQMetrics object from affilabs.utils.sensor_iq

        """
        # Delegate to AL_UIUpdateCoordinator for throttled, batched updates
        if self.ui_updates:
            self.ui_updates.queue_sensor_iq_update(channel, sensor_iq)

    def _should_update_transmission(self):
        """Check if transmission plot updates are needed (lazy evaluation).

        Skip expensive transmission calculations if the feature is disabled
        or preconditions aren't met.
        """
        if not hasattr(self.main_window, "spectroscopy_enabled"):
            return False
        if not self.main_window.spectroscopy_enabled.isChecked():
            return False
        # Unified calibration source-of-truth
        cd = getattr(self.data_mgr, "calibration_data", None)
        if not cd or not getattr(cd, "s_pol_ref", None):
            return False
        if getattr(cd, "wavelengths", None) is None:
            return False
        return True

    def _on_page_changed(self, page_index: int):
        """Handle page changes - show/hide live data dialog for Live Data page (index 0)."""
        # Page 0 is Live Data (sensorgram)
        if page_index == 0:
            # Show live data dialog if acquisition is running
            if (
                self.data_mgr
                and self.data_mgr._acquiring
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
        from PySide6.QtCore import QTimer

        # Resume updates after 200ms (enough time for tab transition to complete)
        QTimer.singleShot(200, lambda: setattr(self, "_skip_graph_updates", False))

    def _process_pending_ui_updates(self):
        """Process queued graph updates at throttled rate (1 Hz).

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

                    # Simple downsampling DISABLED - show all raw data for troubleshooting
                    # MAX_PLOT_POINTS = 2000  # Sufficient for smooth rendering at 1 Hz
                    # if len(raw_time) > MAX_PLOT_POINTS:
                    #     step = len(raw_time) // MAX_PLOT_POINTS
                    #     display_time = raw_time[::step]
                    #     display_wavelength = display_wavelength[::step]
                    # else:
                    #     display_time = raw_time
                    display_time = raw_time
                    display_wavelength = raw_wavelength  # Show all points unfiltered

                    # Update graph
                    with measure("graph_update.setData"):
                        curve.setData(display_time, display_wavelength)

                except Exception:
                    # Silent fail - these are non-critical display errors
                    pass

            # Clear processed updates
            self._pending_graph_updates = {"a": None, "b": None, "c": None, "d": None}

            # === UPDATE CYCLE OF INTEREST GRAPH ===
            # Update at throttled rate (1 Hz) instead of on every data point (40+ FPS)
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
            logger.warning("[WARN] Hardware error detected - stopping acquisition")

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

            # Send command to hardware using servo_move_1_then worker function
            if self.hardware_mgr.ctrl is not None:
                logger.info(
                    f"🔄 Toggling polarizer: {current_position} → {new_position}",
                )

                # Import servo worker function
                from affilabs.utils.calibration_6step import (
                    resolve_device_config_for_detector,
                    servo_move_1_then,
                )

                # Get device config (reads updated UI positions)
                device_config_det = None
                if (
                    hasattr(self.main_window, "device_config")
                    and self.main_window.device_config
                ):
                    device_config_det = self.main_window.device_config.config
                else:
                    # Fallback: try to resolve from USB
                    try:
                        if hasattr(self.hardware_mgr, "usb") and self.hardware_mgr.usb:
                            device_config_det = resolve_device_config_for_detector(
                                self.hardware_mgr.usb,
                            )
                    except Exception:
                        pass

                if device_config_det:
                    # Use servo worker function - it reads positions from device_config
                    # and moves only if current != target
                    success = servo_move_1_then(
                        self.hardware_mgr.ctrl,
                        device_config_det,
                        current_mode=current_position.lower(),
                        target_mode=new_position.lower(),
                    )

                    if success:
                        # Lock the new mode via firmware command
                        mode_success = self.hardware_mgr.ctrl.set_mode(
                            new_position.lower(),
                        )

                        if mode_success:
                            # Update UI to reflect new position
                            self.main_window.sidebar.set_polarizer_position(
                                new_position,
                            )
                            logger.info(
                                f"[OK] Polarizer moved to position {new_position}",
                            )
                        else:
                            logger.warning(
                                f"[WARN] Servo moved but mode lock failed for {new_position}",
                            )
                            # Still update UI since servo physically moved
                            self.main_window.sidebar.set_polarizer_position(
                                new_position,
                            )
                    else:
                        logger.error(
                            f"[ERROR] Failed to move polarizer to position {new_position}",
                        )
                        from widgets.message import show_message

                        show_message(
                            f"Failed to move polarizer to position {new_position}\n\nCheck hardware connection.",
                        )
                else:
                    logger.error(
                        "[ERROR] No device_config available for servo positions",
                    )
                    from widgets.message import show_message

                    show_message(
                        "Cannot move polarizer - device configuration not loaded.",
                    )

            else:
                logger.warning(
                    "[WARN] Controller not connected - cannot move polarizer",
                )
                from widgets.message import show_message

                show_message(
                    "Controller not connected.\n\nPlease connect hardware first.",
                )

        except Exception as e:
            logger.error(f"[ERROR] Error toggling polarizer: {e}")
            import traceback

            traceback.print_exc()
            from widgets.message import show_message

            show_message(f"Error toggling polarizer: {e!s}")

        except Exception as e:
            logger.error(f"[ERROR] Error toggling polarizer: {e}")
            from widgets.message import show_message

            show_message(f"Error toggling polarizer: {e!s}")

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
            if self.data_mgr._acquiring:
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
            logger.info("▶ Resuming live acquisition...")
            self.data_mgr.resume_acquisition()

    def _on_acquisition_started(self):
        """Live data acquisition has started - enable record and pause buttons."""
        logger.info("[OK] Live acquisition started - enabling record/pause buttons")
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
        logger.info("[OK] Pump initialized")
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

    def _cleanup_resources(self, emergency: bool = False):
        """Consolidated cleanup logic for all shutdown paths.

        Args:
            emergency: If True, skip graceful shutdown steps and force-close hardware

        """
        try:
            if not emergency:
                # Print final profiling stats if enabled (graceful shutdown only)
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

            # Disconnect hardware (force close in emergency mode)
            if hasattr(self, "hardware_mgr") and self.hardware_mgr:
                if not emergency:
                    logger.info("Disconnecting hardware...")
                try:
                    # Close controller
                    if (
                        hasattr(self.hardware_mgr, "controller")
                        and self.hardware_mgr.controller
                    ):
                        try:
                            if not emergency:
                                self.hardware_mgr.controller.stop()
                            self.hardware_mgr.controller.close()
                        except Exception as e:
                            if not emergency:
                                logger.error(f"Error closing controller: {e}")

                    # Close spectrometer
                    if (
                        hasattr(self.hardware_mgr, "spectrometer")
                        and self.hardware_mgr.spectrometer
                    ):
                        try:
                            self.hardware_mgr.spectrometer.close()
                        except Exception as e:
                            if not emergency:
                                logger.error(f"Error closing spectrometer: {e}")
                except Exception as e:
                    if not emergency:
                        logger.error(f"Error during hardware disconnect: {e}")

            # Close kinetics controller
            if hasattr(self, "kinetic_mgr") and self.kinetic_mgr:
                if (
                    hasattr(self.kinetic_mgr, "kinetics_controller")
                    and self.kinetic_mgr.kinetics_controller
                ):
                    try:
                        self.kinetic_mgr.kinetics_controller.close()
                    except Exception as e:
                        if not emergency:
                            logger.error(f"Error closing kinetics: {e}")

            if not emergency:
                # Wait for threads to finish (with timeout)
                time.sleep(0.5)
                logger.info("[OK] Application closed successfully")
            else:
                logger.info("[OK] Emergency cleanup completed")

        except Exception as e:
            if not emergency:
                logger.error(f"Error during cleanup: {e}")

    def close(self):
        """Clean up resources on application close."""
        if self.closing:
            return True  # Already closing, prevent double cleanup

        self.closing = True
        logger.info("🔄 Closing application...")

        # Perform graceful cleanup
        self._cleanup_resources(emergency=False)

        return super().close()

    def _emergency_cleanup(self):
        """Emergency cleanup for unexpected exits (called by atexit)."""
        if hasattr(self, "closing") and self.closing:
            return  # Normal close already happened

        logger.warning("[WARN] Emergency cleanup triggered - forcing resource release")

        # Force close all hardware connections without waiting
        self._cleanup_resources(emergency=True)

    def __del__(self):
        """Destructor to ensure resources are cleaned up."""
        try:
            if not hasattr(self, "closing") or not self.closing:
                logger.warning(
                    "[WARN] __del__ called without proper close - forcing cleanup",
                )
                self._cleanup_resources(emergency=True)
        except Exception:
            pass  # Destructor should never raise

    # === PHASE 1.4 HAL HELPER METHODS ===

    def get_hal_controller(self) -> Optional["IController"]:
        """Get HAL controller interface if available.

        Returns:
            IController instance or None if HAL not available

        """
        if HAL_AVAILABLE and self.device_manager:
            return self.device_manager.get_controller()
        return None

    def get_hal_spectrometer(self) -> Optional["ISpectrometer"]:
        """Get HAL spectrometer interface if available.

        Returns:
            ISpectrometer instance or None if HAL not available

        """
        if HAL_AVAILABLE and self.device_manager:
            return self.device_manager.get_spectrometer()
        return None

    def get_hal_servo(self) -> Optional["IServo"]:
        """Get HAL servo interface if available.

        Returns:
            IServo instance or None if HAL not available

        """
        if HAL_AVAILABLE and self.device_manager:
            return self.device_manager.get_servo()
        return None

    def is_hal_ready(self) -> bool:
        """Check if HAL system is ready (controller + spectrometer connected).

        Returns:
            True if HAL is available and system is ready

        """
        if not HAL_AVAILABLE or not self.device_manager:
            return False
        health = self.device_manager.check_health()
        return health.is_ready()

    def connect_hal_devices(
        self,
        require_controller=True,
        require_spectrometer=True,
        require_servo=False,
    ):
        """Connect devices via HAL DeviceManager.

        Args:
            require_controller: Raise error if controller connection fails
            require_spectrometer: Raise error if spectrometer connection fails
            require_servo: Raise error if servo connection fails

        Returns:
            True if all required devices connected successfully

        """
        if not HAL_AVAILABLE or not self.device_manager:
            logger.warning(
                "[WARN]  HAL not available, cannot connect via DeviceManager",
            )
            return False

        try:
            logger.info("🔌 Connecting devices via HAL DeviceManager...")
            success = self.device_manager.connect_all(
                require_controller=require_controller,
                require_spectrometer=require_spectrometer,
                require_servo=require_servo,
            )

            if success:
                logger.info("[OK] HAL devices connected successfully")
                # Start auto-reconnect monitoring
                self.device_status_vm.start_auto_reconnect(interval=5.0)
            else:
                logger.error("[ERROR] HAL device connection failed")

            return success
        except Exception as e:
            logger.error(f"[ERROR] HAL connection error: {e}", exc_info=True)
            return False

    def disconnect_hal_devices(self):
        """Disconnect all devices via HAL DeviceManager."""
        if not HAL_AVAILABLE or not self.device_manager:
            return

        try:
            logger.info("🔌 Disconnecting HAL devices...")
            # Stop auto-reconnect
            self.device_status_vm.stop_auto_reconnect()
            # Disconnect all
            self.device_manager.disconnect_all()
            logger.info("[OK] HAL devices disconnected")
        except Exception as e:
            logger.error(f"[ERROR] HAL disconnect error: {e}", exc_info=True)

    def register_hal_devices_from_legacy(self):
        """Register existing legacy hardware with HAL (bridge pattern).

        This allows gradual migration - wraps legacy hardware_mgr devices
        in HAL adapters and registers them with DeviceManager.
        """
        if not HAL_AVAILABLE or not self.device_manager:
            return

        try:
            # Wrap legacy controller if available
            if (
                hasattr(self, "hardware_mgr")
                and self.hardware_mgr
                and self.hardware_mgr.ctrl
            ):
                controller_adapter = controller_adapter.wrap_existing_controller(
                    self.hardware_mgr.ctrl,
                )
                self.device_manager.register_controller(controller_adapter)
                logger.info("[OK] Legacy controller registered with HAL")

            # Wrap legacy spectrometer if available
            if (
                hasattr(self, "hardware_mgr")
                and self.hardware_mgr
                and self.hardware_mgr.usb
            ):
                spec_adapter = spectrometer_adapter.wrap_existing_spectrometer(
                    self.hardware_mgr.usb,
                )
                self.device_manager.register_spectrometer(spec_adapter)
                logger.info("[OK] Legacy spectrometer registered with HAL")

            # Note: Servo is managed separately, could add servo adapter here

        except Exception as e:
            logger.warning(f"[WARN]  Could not register legacy devices with HAL: {e}")

    # === END PHASE 1.4 HAL METHODS ===

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

        # IMMEDIATE REFRESH: Also update cycle of interest graph
        self._update_cycle_of_interest_graph()
        logger.info(
            "[OK] Filter toggle complete - both timeline and cycle graphs refreshed",
        )

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

        from affilabs.utils.spr_data_processor import KalmanFilter

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
        online_mode: bool = False,
    ):
        """Apply smoothing filter to data (median or Kalman).

        Args:
            data: Input data array
            strength: Smoothing strength (1-10)
            channel: Channel identifier ('a', 'b', 'c', 'd') - required for Kalman
            method: Filter method override ('median' or 'kalman'), uses self._filter_method if None
            online_mode: If True, only filters recent window for large datasets (optimized for real-time display)

        Returns:
            Smoothed data array

        """
        import numpy as np

        if len(data) < 3:
            return data

        # Online mode optimization: For large datasets, only filter recent window
        if online_mode and len(data) > 200:
            ONLINE_FILTER_WINDOW = 200
            split_point = len(data) - ONLINE_FILTER_WINDOW
            overlap = 20
            filter_start = max(0, split_point - overlap)

            result = np.copy(data)
            recent_data = data[filter_start:]
            filtered_recent = self._apply_smoothing(
                recent_data,
                strength,
                channel,
                method,
                online_mode=False,
            )
            result[filter_start:] = filtered_recent
            return result

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
        """Apply incremental median filtering for real-time display (alias for optimized mode).

        This is an alias that calls _apply_smoothing with online_mode=True, which only
        processes recent data window instead of refiltering entire timeline on every update.

        Args:
            data: Full timeline data array
            strength: Smoothing strength (1-10)
            channel: Channel identifier

        Returns:
            Smoothed data array (full length, but efficiently computed)

        """
        return self._apply_smoothing(data, strength, channel, online_mode=True)

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
                # Apply smoothing to timeline data
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

            # 🔒 CRITICAL VALIDATION: Check positions match device_config
            try:
                if (
                    hasattr(self.main_window, "device_config")
                    and self.main_window.device_config
                ):
                    positions = self.main_window.device_config.get_servo_positions()
                    if positions:
                        s_pos = positions.get("s")
                        p_pos = positions.get("p")
                        target_pos = s_pos if new_pos == "s" else p_pos
                        logger.info(
                            f"[OK] Position validation: {new_pos.upper()}-mode target={target_pos}° (from device_config)",
                        )
                    else:
                        logger.warning(
                            "[WARN]  Cannot validate positions - not found in device_config",
                        )
                else:
                    logger.warning(
                        "[WARN]  Cannot validate positions - device_config not available",
                    )
            except Exception as e:
                logger.error(f"[ERROR] Position validation failed: {e}")

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
            pre_led_delay = 12  # Default (optimized for <1Hz acquisition)
            post_led_delay = 40  # Default (optimized for <1Hz acquisition)
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

                # [WARN]  Polarizer positions are IMMUTABLE - set at controller initialization
                # DO NOT apply servo_set() - positions come from device_config at startup
                logger.info(
                    f"   🔒 Polarizer positions locked (from device_config at init): S={s_pos}°, P={p_pos}°",
                )

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

                # Save servo positions, LED intensities, and LED timing delays to device config file
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
                    self.main_window.device_config.set_pre_post_led_delays(
                        pre_led_delay,
                        post_led_delay,
                    )
                    self.main_window.device_config.save()
                    logger.info(
                        "[OK] Settings saved to device config file (including LED timing delays)",
                    )
                else:
                    logger.warning(
                        "[WARN] Device config not available - settings not saved",
                    )

                # Show visual feedback in UI
                self.main_window.show_settings_applied_feedback()

                logger.info("[OK] Settings applied and saved to EEPROM")
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

        logger.info("[OK] Graph colors updated successfully")

    # === CALIBRATION WORKFLOWS ===
    # Calibration methods moved to controllers/calibration_controller.py for separation of concerns.
    # Access via self.calibration_ctrl.method_name()

    def _start_led_calibration(self, calibration_type: str = "LED"):
        """Delegate to calibration controller."""
        self.calibration_ctrl.start_led_calibration(calibration_type)

    def _on_simple_led_calibration(self):
        """Delegate to calibration controller."""
        self.calibration_ctrl.start_simple_led_calibration()

    def _on_full_calibration(self):
        """Delegate to calibration controller."""
        self.calibration_ctrl.start_full_calibration()

    def _on_polarizer_calibration(self):
        """Delegate to calibration controller."""
        self.calibration_ctrl.start_polarizer_calibration()

    def _on_oem_led_calibration(self):
        """Delegate to calibration controller."""
        self.calibration_ctrl.start_oem_led_calibration()

    def _run_led_then_afterglow_calibration(self):
        """Delegate to calibration controller."""
        self.calibration_ctrl.run_led_then_afterglow_calibration()

        # Start LED calibration with progress dialog
        self.calibration.start_calibration()

    def _run_afterglow_calibration(self, led_intensities: dict = None):
        """Delegate to calibration controller."""
        self.calibration_ctrl.run_afterglow_calibration(led_intensities)

    def _on_power_on_requested(self):
        """User requested to power on (connect hardware)."""
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
                logger.info("⏸  Stopping data acquisition...")
                try:
                    self.data_mgr.stop_acquisition()
                    logger.info("[OK] Data acquisition stopped")
                except Exception as e:
                    logger.error(f"Error stopping data acquisition: {e}")

            # Stop recording if active (ensures data is saved)
            if self.recording_mgr and self.recording_mgr.is_recording:
                logger.info("💾 Stopping active recording...")
                try:
                    self.recording_mgr.stop_recording()
                    logger.info("[OK] Recording stopped and saved")
                except Exception as e:
                    logger.error(f"Error stopping recording: {e}")

            # Disconnect all hardware (safe shutdown of devices)
            logger.info("🔌 Disconnecting hardware...")
            try:
                self.hardware_mgr.disconnect_all()
                logger.info("[OK] Hardware disconnected safely")
            except Exception as e:
                logger.error(f"Error disconnecting hardware: {e}")

            # Update UI to disconnected state
            self.main_window.set_power_state("disconnected")

            logger.info(
                "[OK] Graceful shutdown complete - software ready for offline post-processing",
            )

        except Exception as e:
            logger.error(f"Error during power off: {e}")
            # Still update UI even if errors occurred
            self.main_window.set_power_state("disconnected")
            from widgets.message import show_message

            show_message(f"Power off completed with errors: {e}", "Warning")

    def _on_recording_start_requested(self):
        """User requested to start recording."""
        logger.info(
            "📝 [RECORD-HANDLER] Recording start requested by user (button clicked)",
        )

        # Show file dialog to select recording location
        # Get default filename with timestamp
        import datetime as dt
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog

        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"AffiLabs_data_{timestamp}.csv"

        logger.info(
            f"[RECORD-HANDLER] Showing save dialog with default: {default_filename}",
        )

        # Show save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Save Recording As",
            default_filename,
            "CSV Files (*.csv);;All Files (*.*)",
        )

        if file_path:
            # User selected a file - start recording
            logger.info(f"[RECORD-HANDLER] User selected file: {file_path}")
            logger.info(
                "[RECORD-HANDLER] Starting recording via recording_mgr.start_recording()",
            )
            self.recording_mgr.start_recording(file_path)

            # Populate export fields with recording information
            path_obj = Path(file_path)
            filename = path_obj.stem  # Name without extension
            directory = str(path_obj.parent)

            self.main_window.sidebar.export_filename_input.setText(filename)
            self.main_window.sidebar.export_dest_input.setText(directory)
            logger.info(
                f"✓ [RECORD-HANDLER] Export fields populated: {filename} in {directory}",
            )
        else:
            # User cancelled - revert button state
            logger.info(
                "[RECORD-HANDLER] User cancelled file dialog - reverting button state",
            )
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
        logger.info("Updating Device Status UI via ViewModel...")

        # Update ViewModel with hardware status (Phase 1.3+1.4 integration)
        # ViewModel will emit signals that trigger UI updates
        if status.get("ctrl_type"):
            # Controller connected
            serial = status.get("ctrl_serial", "unknown")
            self.device_status_vm.update_device_status(
                "controller",
                "connected",
                is_healthy=True,
                serial_number=serial,
            )

        if status.get("spectrometer"):
            # Spectrometer connected
            serial = status.get("spectrometer_serial", "unknown")
            self.device_status_vm.update_device_status(
                "spectrometer",
                "connected",
                is_healthy=True,
                serial_number=serial,
            )

        if status.get("knx_type"):
            # Kinetic controller connected
            self.device_status_vm.update_device_status(
                "kinetic",
                "connected",
                is_healthy=True,
            )

        if status.get("pump_connected"):
            # Pump connected
            self.device_status_vm.update_device_status(
                "pump",
                "connected",
                is_healthy=True,
            )

        # Also forward to main window for backward compatibility
        # TODO: Remove this once all UI updates are driven by ViewModel signals
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

    # === VIEWMODEL SIGNAL HANDLERS (Phase 1.3+1.4 Integration) ===

    def _on_vm_device_connected(self, device_type: str, serial_number: str):
        """Handle device_connected signal from DeviceStatusViewModel.

        Args:
            device_type: Type of device ('controller', 'spectrometer', etc.)
            serial_number: Device serial number

        """
        logger.info(
            f"📡 [ViewModel] Device connected: {device_type} (S/N: {serial_number})",
        )
        # UI updates are handled by the main window's direct connection to hardware_mgr
        # This is here for future enhancements (e.g., notifications, logging)

    def _on_vm_device_disconnected(self, device_type: str):
        """Handle device_disconnected signal from DeviceStatusViewModel.

        Args:
            device_type: Type of device that disconnected

        """
        logger.info(f"📡 [ViewModel] Device disconnected: {device_type}")
        # Future: Could show notification or update status indicators

    def _on_vm_device_error(self, device_type: str, error_message: str):
        """Handle device_error signal from DeviceStatusViewModel.

        Args:
            device_type: Type of device with error
            error_message: Error description

        """
        logger.warning(f"📡 [ViewModel] Device error - {device_type}: {error_message}")
        # Future: Could show error notification or update error indicators

    def _on_vm_status_changed(self, all_connected: bool, all_healthy: bool):
        """Handle overall_status_changed signal from DeviceStatusViewModel.

        Args:
            all_connected: True if all required devices are connected
            all_healthy: True if all devices are healthy (no errors)

        """
        logger.info(
            f"📡 [ViewModel] Overall status: connected={all_connected}, healthy={all_healthy}",
        )
        # Future: Could enable/disable features based on system health

    # === SPECTRUM VIEWMODEL SIGNAL HANDLERS (Phase 1.3 Integration) ===

    def _on_spectrum_updated(
        self,
        channel: str,
        wavelengths: np.ndarray,
        transmission: np.ndarray,
    ):
        """Handle spectrum_updated signal from SpectrumViewModel.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            wavelengths: Wavelength array
            transmission: Processed transmission spectrum

        """
        # Queue via AL_UIUpdateCoordinator (raw spectrum handled separately in _on_raw_spectrum_updated)
        self.ui_updates.queue_transmission_update(
            channel,
            wavelengths,
            transmission,
            None,
        )
        logger.debug(f"[ViewModel] Spectrum updated for channel {channel}")

    def _on_raw_spectrum_updated(
        self,
        channel: str,
        wavelengths: np.ndarray,
        raw_spectrum: np.ndarray,
    ):
        """Handle raw_spectrum_updated signal from SpectrumViewModel.

        Args:
            channel: Channel identifier
            wavelengths: Wavelength array
            raw_spectrum: Raw intensity data

        """
        # Update pending transmission update with raw spectrum data via coordinator
        if self.ui_updates._pending_transmission_updates.get(channel):
            self.ui_updates._pending_transmission_updates[channel]["raw_spectrum"] = (
                raw_spectrum
            )
        logger.debug(f"[ViewModel] Raw spectrum updated for channel {channel}")

    # === DOMAIN MODEL ADAPTERS (Phase 1.1 Integration) ===

    def _dict_to_raw_spectrum(self, channel: str, data: dict) -> RawSpectrumData | None:
        """Convert dictionary to RawSpectrumData domain model.

        Args:
            channel: Channel identifier
            data: Spectrum data dictionary from acquisition

        Returns:
            RawSpectrumData instance or None if data is invalid

        """
        try:
            # Use unified field name
            raw_spectrum = data.get("raw_spectrum")
            wavelengths = data.get("wavelengths", self.data_mgr.wave_data)

            if raw_spectrum is None or wavelengths is None:
                return None

            # Convert to domain model with validation
            return RawSpectrumData(
                wavelengths=wavelengths,
                intensities=raw_spectrum,
                channel=channel,
                timestamp=data.get("timestamp", time.time()),
                integration_time=data.get("integration_time", 0.0),
                num_scans=data.get("num_scans", 1),
                led_intensity=data.get("led_intensity", 0),
                metadata=data.get("metadata", {}),
            )
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Failed to create RawSpectrumData for channel {channel}: {e}",
            )
            return None

    def _dict_to_processed_spectrum(
        self,
        channel: str,
        data: dict,
        transmission: np.ndarray,
    ) -> ProcessedSpectrumData | None:
        """Convert transmission data to ProcessedSpectrumData domain model.

        Args:
            channel: Channel identifier
            data: Original spectrum data dictionary
            transmission: Calculated transmission spectrum

        Returns:
            ProcessedSpectrumData instance or None if data is invalid

        """
        try:
            wavelengths = data.get("wavelengths", self.data_mgr.wave_data)

            if wavelengths is None:
                return None

            # Get reference spectrum if available
            ref_spectrum = None
            if (
                self.data_mgr.calibration_data
                and self.data_mgr.calibration_data.s_pol_ref
            ):
                ref_spectrum = self.data_mgr.calibration_data.s_pol_ref.get(channel)

            return ProcessedSpectrumData(
                wavelengths=wavelengths,
                intensities=transmission,  # For processed, intensities = transmission
                transmission_percent=transmission,
                channel=channel,
                timestamp=data.get("timestamp", time.time()),
                reference_spectrum=ref_spectrum,
                baseline_corrected=True,  # We apply baseline correction via services
                metadata=data.get("metadata", {}),
            )
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Failed to create ProcessedSpectrumData for channel {channel}: {e}",
            )
            return None

    # === CALIBRATION VIEWMODEL SIGNAL HANDLERS (Phase 1.3 Integration) ===

    def _on_cal_vm_started(self):
        """Handle calibration_started signal from CalibrationViewModel."""
        logger.info("📡 [CalibrationViewModel] Calibration started")
        # Future: Update UI to show calibration in progress

    def _on_cal_vm_progress(self, percent: int, message: str):
        """Handle calibration_progress signal from CalibrationViewModel.

        Args:
            percent: Progress percentage (0-100)
            message: Status message

        """
        logger.info(f"📡 [CalibrationViewModel] Progress: {percent}% - {message}")
        # Future: Update progress bar in UI

    def _on_cal_vm_complete(self, calibration_data: dict):
        """Handle calibration_complete signal from CalibrationViewModel.

        Args:
            calibration_data: Calibration data dictionary

        """
        logger.info("📡 [CalibrationViewModel] Calibration complete")
        # Future: Display success message, enable acquisition

    def _on_cal_vm_failed(self, error_message: str):
        """Handle calibration_failed signal from CalibrationViewModel.

        Args:
            error_message: Error description

        """
        logger.error(f"📡 [CalibrationViewModel] Calibration failed: {error_message}")
        # Future: Display error message, suggest retry

    def _on_cal_vm_validation_complete(self, passed: bool, results: list):
        """Handle validation_complete signal from CalibrationViewModel.

        Args:
            passed: True if validation passed
            results: List of ValidationResult objects

        """
        errors = len([r for r in results if r.severity == "error"])
        warnings = len([r for r in results if r.severity == "warning"])
        logger.info(
            f"📡 [CalibrationViewModel] Validation: {'PASSED' if passed else 'FAILED'} "
            f"({errors} errors, {warnings} warnings)",
        )
        # Future: Display validation report in UI

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
                    logger.warning("[WARN]  SERVO POSITIONS AT DEFAULT VALUES")
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

                # ========================================================================
                # CRITICAL: WRITE DEVICE CONFIG POSITIONS TO CONTROLLER EEPROM
                # ========================================================================
                # Servo positions are IMMUTABLE and come from device_config ONLY
                # We write them to controller EEPROM at startup to ensure single source of truth
                # Controller firmware loads positions from EEPROM at boot
                # ========================================================================
                logger.info("=" * 80)
                logger.info("🔒 CRITICAL: Syncing servo positions to controller EEPROM")
                logger.info("=" * 80)
                logger.info(f"   Device Config: S={s_pos}°, P={p_pos}°")
                logger.info("   Action: Writing to controller EEPROM...")

                try:
                    # Read current EEPROM config
                    eeprom_config = self.hardware_mgr.ctrl.read_config_from_eeprom()

                    if eeprom_config:
                        # Check if EEPROM positions match device_config
                        eeprom_s = eeprom_config.get("servo_s_position")
                        eeprom_p = eeprom_config.get("servo_p_position")

                        logger.info(f"   Current EEPROM: S={eeprom_s}°, P={eeprom_p}°")

                        if eeprom_s != s_pos or eeprom_p != p_pos:
                            logger.warning("[WARN]  EEPROM MISMATCH DETECTED!")
                            logger.warning(f"   Device Config: S={s_pos}°, P={p_pos}°")
                            logger.warning(
                                f"   EEPROM:        S={eeprom_s}°, P={eeprom_p}°",
                            )
                            logger.warning(
                                "   Updating EEPROM to match device_config...",
                            )

                            # Update EEPROM with device_config positions
                            eeprom_config["servo_s_position"] = s_pos
                            eeprom_config["servo_p_position"] = p_pos

                            if self.hardware_mgr.ctrl.write_config_to_eeprom(
                                eeprom_config,
                            ):
                                logger.info("[OK] EEPROM updated successfully")
                                logger.info(
                                    "🔄 Power cycle controller to apply new positions",
                                )
                                logger.warning("")
                                logger.warning("=" * 80)
                                logger.warning(
                                    "[WARN]  CRITICAL: CONTROLLER NEEDS POWER CYCLE",
                                )
                                logger.warning("=" * 80)
                                logger.warning(
                                    "The controller firmware caches EEPROM positions at boot.",
                                )
                                logger.warning(
                                    "New positions have been written but firmware is still using old values.",
                                )
                                logger.warning("")
                                logger.warning("TO FIX:")
                                logger.warning("1. Close this application")
                                logger.warning("2. Unplug the controller USB cable")
                                logger.warning("3. Wait 5 seconds")
                                logger.warning("4. Plug the USB cable back in")
                                logger.warning("5. Restart this application")
                                logger.warning("=" * 80)
                                logger.warning("")
                            else:
                                logger.error("[ERROR] EEPROM write failed!")
                                logger.error(
                                    "   DANGER: Controller may use wrong positions!",
                                )
                        else:
                            logger.info(
                                "[OK] EEPROM matches device_config - no update needed",
                            )
                    else:
                        logger.warning("[WARN]  Could not read EEPROM config")
                        logger.warning("   Cannot verify position sync")

                except Exception as e:
                    logger.error(f"[ERROR] EEPROM sync failed: {e}")
                    logger.error(
                        "   DANGER: Controller positions may not match device_config!",
                    )

                logger.info("=" * 80)
                logger.info(
                    f"  Servo positions: S={s_pos}°, P={p_pos}° (🔒 IMMUTABLE - loaded at init)",
                )
                logger.info("=" * 80)
            else:
                logger.warning(
                    "  [WARN] Device config not available - cannot load servo positions",
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
                        f"  [OK] LED intensities loaded from device config: A={led_a}, B={led_b}, C={led_c}, D={led_d}",
                    )
                else:
                    logger.info(
                        "  [INFO]  No calibrated LED intensities in device config - will calibrate on startup",
                    )

            # Initialize polarizer position to S-mode (default after startup)
            # This keeps UI in sync with hardware state
            if hasattr(self.main_window, "sidebar"):
                self.main_window.sidebar.set_polarizer_position("S")
                logger.info("  [OK] Polarizer position initialized to S-mode (default)")

        except Exception as e:
            logger.error(f"Failed to load device settings: {e}")
            logger.debug("Settings load error details:", exc_info=True)

    def _run_servo_auto_calibration(self):
        """Delegate to calibration controller."""
        self.calibration_ctrl.run_servo_auto_calibration()

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

            logger.info(f"[OK] Cycle data exported to: {file_path}")
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

            # Export using strategy pattern
            exporter = self._get_export_strategy(format_type)
            exporter.export(file_path, export_data, config)

            logger.info(f"[OK] Data exported successfully to: {file_path}")
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

    def _get_export_strategy(self, format_type: str):
        """Factory method to get appropriate export strategy.

        Args:
            format_type: Export format ('excel', 'csv', 'json', 'hdf5')

        Returns:
            ExportStrategy instance for the specified format

        """
        from affilabs.utils.export_strategies import get_export_strategy

        return get_export_strategy(format_type)

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

            logger.info(f"[OK] Graph image exported to: {file_path}")
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
            logger.info("\n⏱ PERIODIC PROFILING SNAPSHOT:")
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
    logger.info("🛡 Global exception hook installed")

    # NullWriter for emergency cleanup
    class NullWriter:
        """Null output that absorbs all writes."""

        def write(self, text):
            pass

        def flush(self):
            pass

        def fileno(self):
            return -1

    # Replace stderr with filtered version (QtWarningFilter already defined at module level)
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

    # Create application instance
    app = Application(sys.argv)

    # Show splash screen for better user experience during startup
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPixmap
    from PySide6.QtWidgets import QSplashScreen

    splash = QSplashScreen()
    splash.setFixedSize(400, 250)

    # Create custom splash with gradient background
    splash_pixmap = QPixmap(400, 250)
    splash_pixmap.fill(Qt.transparent)

    painter = QPainter(splash_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Draw rounded rectangle with gradient
    from PySide6.QtGui import QPainterPath

    gradient = QLinearGradient(0, 0, 0, 250)
    gradient.setColorAt(0, QColor(46, 48, 227))  # Primary blue
    gradient.setColorAt(1, QColor(36, 38, 180))  # Darker blue

    path = QPainterPath()
    path.addRoundedRect(QRect(0, 0, 400, 250), 12, 12)
    painter.fillPath(path, QBrush(gradient))

    # Draw app name
    painter.setPen(QColor(255, 255, 255))
    from PySide6.QtGui import QFont

    font = painter.font()
    font.setPointSize(24)
    font.setWeight(QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(QRect(0, 80, 400, 40), Qt.AlignCenter, "AffiLabs.core")

    # Draw version/status
    font.setPointSize(12)
    font.setWeight(QFont.Weight.Normal)
    painter.setFont(font)
    painter.setPen(QColor(255, 255, 255, 180))
    painter.drawText(QRect(0, 130, 400, 30), Qt.AlignCenter, "Loading components...")

    painter.end()

    splash.setPixmap(splash_pixmap)
    splash.show()
    app.processEvents()

    # Update splash message when main window is ready
    def update_splash_message(message: str):
        """Update splash screen message."""
        if splash.isVisible():
            painter = QPainter(splash_pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Clear message area
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            gradient = QLinearGradient(0, 120, 0, 170)
            gradient.setColorAt(0, QColor(46, 48, 227))
            gradient.setColorAt(1, QColor(36, 38, 180))
            painter.fillRect(QRect(0, 120, 400, 50), QBrush(gradient))

            # Draw new message
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver,
            )
            painter.setPen(QColor(255, 255, 255, 180))
            font = painter.font()
            font.setPointSize(12)
            painter.setFont(font)
            painter.drawText(QRect(0, 130, 400, 30), Qt.AlignCenter, message)
            painter.end()

            splash.setPixmap(splash_pixmap)
            app.processEvents()

    # Store splash reference in app for updates
    app.splash_screen = splash
    app.update_splash_message = update_splash_message

    # Schedule splash close after window is fully loaded
    def close_splash():
        """Close splash screen after deferred loading completes."""
        if hasattr(app, "splash_screen") and app.splash_screen.isVisible():
            app.update_splash_message("Ready!")
            QTimer.singleShot(300, lambda: app.splash_screen.finish(app.main_window))

    # Close splash after deferred widgets load (total ~350ms)
    QTimer.singleShot(350, close_splash)

    logger.info("🚀 Starting event loop...")
    exit_code = app.exec()

    # Restore original stderr
    sys.stderr = original_stderr
    sys.stdout = original_stdout

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
