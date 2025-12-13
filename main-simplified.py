"""AffiLabs.core - Surface Plasmon Resonance Analysis Platform

ARCHITECTURE (4-Layer Clean Separation):
=========================================
Layer 1: Hardware (hardware_manager) - Hardware Abstraction Layer (HAL)
Layer 2: Core Business Logic (managers) - Processing
Layer 3: Coordinators - Orchestration
Layer 4: UI/Widgets - Display only, no business logic

INITIALIZATION PHASES (9-phase strict ordering):
=================================================
1. Validation - Fail-fast on missing critical imports
2. Infrastructure - Logging, theme, profiling
3. State Initialization - All instance variables
4. Business Layer - Managers and services (no UI dependencies)
5. UI Layer - Main window creation
6. Coordinators & ViewModels - UI-aware components
7. Signal Wiring - Connect all subsystems
8. Finalization - Show window, start threads/timers

Last Updated: December 2, 2025
"""

from __future__ import annotations

# ============================================================================
# SECTION 1: Core Python Setup
# ============================================================================
import os
import sys

# Add parent directory to path for imports
if __name__ == "__main__":
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

import atexit
import threading
import warnings
from pathlib import Path

# ============================================================================
# SECTION 2: Exception and Warning Filters (BEFORE Qt imports)
# ============================================================================
# These filters suppress false-positive Qt threading warnings that occur when
# using queue-based architecture. MUST be installed before importing Qt.


# --- Exception Handler ---
def qt_exception_handler(exctype, value, tb):
    """Global exception hook to suppress harmless Qt threading warnings."""
    if not sys.stderr or not hasattr(sys.stderr, "write"):
        return

    try:
        error_msg = str(value)
        # Suppress known false-positive Qt threading warnings
        if "QTextDocument" in error_msg or "different thread" in error_msg:
            return
        # Forward real exceptions to default handler
        sys.__excepthook__(exctype, value, tb)
    except (ValueError, OSError):
        pass  # stderr closed, fail silently


# --- Warning Filter Classes ---
class QtWarningFilter:
    """Stderr wrapper that suppresses known Qt threading false-positives."""

    SUPPRESSED_PATTERNS = (
        "QObject: Cannot create children",
        "QTextDocument",
        "parent's thread is QThread",
        "parent that is in a different thread",
    )

    def __init__(self, original_stderr):
        self.original = original_stderr
        self._closed = False

    def write(self, text):
        if self._closed or not self.original:
            return
        try:
            # Normalize to string
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="replace")
            elif not isinstance(text, str):
                text = str(text)

            # Drop known false-positive warnings
            if any(pattern in text for pattern in self.SUPPRESSED_PATTERNS):
                return

            self.original.write(text)
        except (ValueError, OSError):
            self._closed = True

    def flush(self):
        if not self._closed and self.original:
            try:
                self.original.flush()
            except (ValueError, OSError):
                self._closed = True

    def fileno(self):
        try:
            return self.original.fileno()
        except:
            return -1


# --- Install Filters ---
# Install exception hook
sys.excepthook = qt_exception_handler

# Install stderr filter (unless verbose mode)
if os.environ.get("AFFILABS_VERBOSE_QT", "0") in ("0", "false", "False"):
    sys.stderr = QtWarningFilter(sys.stderr)

# Note: stdout is NOT wrapped here to preserve sys.stdout.buffer for logger
# The logger's SafeWriter handles stdout filtering when needed

# Suppress Python warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

# ============================================================================
# SECTION 3: Qt Environment Configuration (BEFORE Qt imports)
# ============================================================================
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

# ============================================================================
# SECTION 4: Qt Core Imports
# ============================================================================
from PySide6.QtCore import Qt, QTimer, QtMsgType, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

from affilabs.ui.ui_message import error as ui_error
from affilabs.ui.ui_message import info as ui_info
from affilabs.ui.ui_message import question as ui_question
from affilabs.ui.ui_message import warn as ui_warn
from affilabs.utils.time_utils import monotonic


# --- Qt Message Handler (suppresses threading warnings) ---
def qt_message_handler(msg_type, context, message):
    """Qt message handler that filters false-positive threading warnings."""
    # Suppress known false-positives
    if "QTextDocument" in message or "different thread" in message:
        return

    # Forward legitimate messages to stdout
    level_map = {
        QtMsgType.QtDebugMsg: "Debug",
        QtMsgType.QtWarningMsg: "Warning",
        QtMsgType.QtCriticalMsg: "Critical",
        QtMsgType.QtFatalMsg: "Fatal",
    }
    level = level_map.get(msg_type, "Unknown")
    print(f"Qt {level}: {message}")


qInstallMessageHandler(qt_message_handler)

# ============================================================================
# SECTION 5: Application Imports (Organized by Architecture Layer)
# ============================================================================

# Qt Core
from PySide6.QtCore import Signal

# Layer 4: UI/Widgets
from affilabs.affilabs_core_ui import AffilabsMainWindow

# Layer 3: Coordinators (Orchestration)
from affilabs.core.calibration_service import CalibrationService
from affilabs.core.cycle_coordinator import CycleCoordinator

# Layer 2: Core Business Logic (Managers)
from affilabs.core.data_acquisition_manager import DataAcquisitionManager
from affilabs.core.data_buffer_manager import DataBufferManager

# Layer 1: Hardware (HAL)
from affilabs.core.hardware_manager import HardwareManager
from affilabs.core.kinetic_manager import KineticManager
from affilabs.core.recording_manager import RecordingManager

# --- Optional: Phase 1.4 Hardware Abstraction Layer (HAL) ---
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
    _hal_import_error = str(e)

# --- Optional: Phase 1.3 UI Coordinators ---
try:
    from affilabs.coordinators.dialog_manager import DialogManager
    from affilabs.coordinators.ui_update_coordinator import AL_UIUpdateCoordinator

    COORDINATORS_AVAILABLE = True
except ImportError as e:
    COORDINATORS_AVAILABLE = False
    _coordinators_import_error = str(e)

# --- Phase 1 Architecture Components ---
# ViewModels (Phase 1.3 - UI presentation logic)
from affilabs.app_config import (
    DEFAULT_FILTER_ENABLED,
    DEFAULT_FILTER_STRENGTH,
    LEAK_DETECTION_WINDOW,
    LEAK_THRESHOLD_RATIO,
    SENSORGRAM_DOWNSAMPLE_FACTOR,
    WAVELENGTH_TO_RU_CONVERSION,
)

# Domain Models (Phase 1.1 - Data structures)
from affilabs.domain import ProcessedSpectrumData, RawSpectrumData

# Business Services (Phase 1.2 - Core logic)
from affilabs.services import BaselineCorrector, TransmissionCalculator

# Configuration
from affilabs.settings import PROFILING_ENABLED, PROFILING_REPORT_INTERVAL, SW_VERSION
from affilabs.utils.baseline_data_recorder import BaselineDataRecorder

# --- Utilities and Configuration ---
from affilabs.utils.logger import logger
from affilabs.utils.performance_profiler import get_profiler, measure
from affilabs.utils.session_quality_monitor import SessionQualityMonitor
from affilabs.viewmodels import (
    CalibrationViewModel,
    DeviceStatusViewModel,
    SpectrumViewModel,
)

# TIME_ZONE configuration
try:
    from affilabs.settings import TIME_ZONE
except ImportError:
    import datetime

    TIME_ZONE = datetime.datetime.now(datetime.UTC).astimezone().tzinfo

# Standard library imports for application logic
import datetime as dt
import logging
from typing import Optional

import numpy as np

# ============================================================================
# SECTION 6: Constants and Configuration
# ============================================================================
# Centralized configuration to avoid magic numbers and improve maintainability

# Queue configuration
SPECTRUM_QUEUE_SIZE = 200  # Buffer ~5 seconds at 40 Hz (data output from acquisition)
try:
    from settings import LED_COMMAND_QUEUE_SIZE
except ImportError:
    LED_COMMAND_QUEUE_SIZE = 1440  # LED commands to pre-queue (5 min @ 4 Hz default)

# Performance settings
UI_UPDATE_INTERVAL_MS = 100  # 10 Hz for smooth updates
DEBUG_LOG_EVERY_N_ACQUISITIONS = 10  # Throttle debug logs

# Calibration limits
MAX_CALIBRATION_RETRIES = 3

# Channel configuration
CHANNELS = ["a", "b", "c", "d"]
CHANNEL_INDICES = {"a": 0, "b": 1, "c": 2, "d": 3}
DEFAULT_AXIS = "x"

# Filter defaults
DEFAULT_FILTER_METHOD = "median"  # Options: 'median', 'kalman'

# ============================================================================
# SECTION 7: Logging Configuration
# ============================================================================
# Configures ASCII-only logging to prevent mojibake in PowerShell (cp1252)


class _AsciiLogFilter(logging.Filter):
    """Filter that strips non-ASCII characters from log messages.

    Prevents mojibake/encoding errors in Windows PowerShell terminals.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            # Strip non-ASCII (keep only 0-127)
            clean = "".join(ch for ch in msg if ord(ch) < 128)
            record.msg = clean
        except Exception:
            pass
        return True


# Attach filter to project logger
try:
    if isinstance(logger, logging.Logger):
        logger.addFilter(_AsciiLogFilter())
except Exception:
    pass

# ============================================================================
# SECTION 7: Application Class
# ============================================================================


class Application(QApplication):
    """Main application coordinator for AffiLabs.core SPR analysis platform.

    Architecture:
    -------------
    Follows strict 4-layer separation:
      Layer 1: Hardware (hardware_manager) - Device abstraction
      Layer 2: Business Logic (managers) - Data processing
      Layer 3: Coordinators - Workflow orchestration
      Layer 4: UI (widgets) - Display only

    Initialization:
    ---------------
    9-phase initialization prevents fragile dependency issues:
      1. Validation - Fail-fast on missing imports
      2. Infrastructure - Theme, logging, profiling
      3. State - All instance variables declared
      4. Business Layer - Managers (no UI dependencies)
      5. UI Layer - Main window creation
      6. Coordinators & ViewModels - UI-aware components
      7. Signal Wiring - Connect subsystems
      8. Finalization - Start threads, show window

    Thread Safety:
    --------------
    - Processing thread: Handles spectrum data via queue
    - UI thread: Updates display via throttled signals
    - All cross-thread communication uses Qt signals/slots
    """

    # Signals for thread-safe communication
    cursor_update_signal = Signal(float)  # elapsed_time from processing thread

    def __init__(self, argv):
        """Initialize application with strict phase ordering to prevent fragile dependencies."""
        # ============================================================
        # PHASE 1: Qt Core Setup
        # ============================================================
        super().__init__(argv)
        self.setApplicationName("AffiLabs.core")
        self.setOrganizationName("Affinite Instruments")

        # ============================================================
        # PHASE 2: Validation - Fail Fast on Critical Import Failures
        # ============================================================
        self._run_init_phase(
            2, "Validation", self._validate_critical_imports, critical=True
        )

        # ============================================================
        # PHASE 3: Infrastructure Setup (no business logic)
        # ============================================================
        self._run_init_phase(3, "Infrastructure", self._setup_infrastructure)

        # ============================================================
        # PHASE 4: State Initialization (all instance variables)
        # ============================================================
        self._run_init_phase(
            4, "State Variables", self._init_state_variables, critical=True
        )

        # ============================================================
        # PHASE 5: Business Layer (managers & services, no UI)
        # ============================================================
        self._run_init_phase(5, "Managers", self._init_managers, critical=True)
        self._run_init_phase(5, "Services", self._init_services, critical=True)

        # ============================================================
        # PHASE 6: UI Layer (main window creation)
        # ============================================================
        self._run_init_phase(6, "Main Window", self._create_main_window, critical=True)

        # ============================================================
        # PHASE 7: Coordinators & ViewModels (UI-aware components)
        # ============================================================
        self._run_init_phase(7, "Coordinators", self._init_coordinators)
        self._run_init_phase(7, "ViewModels", self._init_viewmodels)

        # ============================================================
        # PHASE 8: Signal Wiring (connect all subsystems)
        # ============================================================
        self._run_init_phase(
            8, "Signal Wiring", self._connect_all_signals, critical=True
        )

        # ============================================================
        # PHASE 9: Finalization (show window, start threads/timers)
        # ============================================================
        self._run_init_phase(9, "Finalization", self._finalize_and_show, critical=True)

    @staticmethod
    def _run_init_phase(phase: int, name: str, func, critical: bool = False):
        """Execute an initialization phase with consistent logging and error handling.

        Args:
            phase: Phase number (1-9)
            name: Human-readable phase name
            func: Callable to execute
            critical: If True, exit on failure; if False, log and continue

        Raises:
            SystemExit: If critical phase fails

        """
        try:
            logger.info(f"Phase {phase}: {name}...")
            func()
            logger.debug(f"Phase {phase}: {name} complete")
        except Exception as e:
            logger.error(f"Phase {phase}: {name} failed: {e}", exc_info=True)
            if critical:
                logger.critical(f"Critical phase {phase} failed, cannot continue")
                raise SystemExit(1)
            logger.warning(f"Non-critical phase {phase} failed, continuing anyway")

    def _validate_critical_imports(self):
        """Fail fast if critical modules are missing or broken.

        This prevents silent fallback to stub classes that cause
        hard-to-debug issues like "controller not found".

        Raises:
            SystemExit: If any critical import fails

        """
        logger.info("Validating critical imports...")

        failures = []

        # Validate controller classes
        try:
            from affilabs.utils.controller import (
                ArduinoController,
                PicoEZSPR,
                PicoP4SPR,
            )

            # Verify classes are actually callable (not None/stub)
            if not all(
                callable(cls) for cls in [PicoP4SPR, PicoEZSPR, ArduinoController]
            ):
                raise ImportError("Controller classes are not callable")
            logger.debug("  Controller classes OK")
        except (ImportError, AttributeError) as e:
            failures.append(f"Controller classes: {e}")

        # Validate settings
        try:
            from settings import ARDUINO_PID, ARDUINO_VID, PICO_PID, PICO_VID

            # Verify settings are valid integers
            if not all(isinstance(vid, int) for vid in [PICO_VID, ARDUINO_VID]):
                raise ValueError("VID values must be integers")
            logger.debug("  Settings OK")
        except (ImportError, AttributeError, ValueError) as e:
            failures.append(f"Settings: {e}")

        # Report HAL availability
        if HAL_AVAILABLE:
            logger.info("  Phase 1.4 HAL available")
        else:
            error_msg = _safe_get_global("_hal_import_error", "unknown error")
            logger.warning(f"  Phase 1.4 HAL not available: {error_msg}")

        # Report Coordinators availability
        if COORDINATORS_AVAILABLE:
            logger.info("  UI Coordinators available")
        else:
            error_msg = _safe_get_global("_coordinators_import_error", "unknown error")
            logger.warning(f"  UI Coordinators not available: {error_msg}")

        # Fail fast if critical imports missing
        if failures:
            logger.critical("=" * 80)
            logger.critical("CRITICAL STARTUP FAILURES DETECTED")
            logger.critical("=" * 80)
            for failure in failures:
                logger.critical(f"  {failure}")
            logger.critical("=" * 80)
            raise SystemExit(1)

        logger.info("  All critical imports validated")

    def _setup_infrastructure(self):
        """Setup logging, theme, profiling (no business logic).

        Applies UI theme and configures environment variables for
        subprocess behavior. Failures are non-fatal since these are
        optional enhancements.
        """
        # Apply theme (non-fatal if fails)
        try:
            self._apply_theme()
        except Exception as e:
            logger.warning(f"Failed to apply theme: {e}")

        # Ensure calibration runs with visible dialogs in UI launcher
        self._set_env_var("CALIBRATION_HEADLESS", "0", "Calibration dialog visibility")

    @staticmethod
    def _set_env_var(name: str, value: str, description: str) -> bool:
        """Safely set environment variable with logging.

        Args:
            name: Environment variable name
            value: Value to set
            description: Human-readable purpose for logging

        Returns:
            True if successful, False otherwise

        """
        try:
            os.environ[name] = value
            logger.debug(f"Set {name}={value} ({description})")
            return True
        except Exception as e:
            logger.warning(f"Could not set {name}: {e} ({description})")
            return False

    def _init_state_variables(self):
        """Initialize all instance variables in one place for clarity.

        Centralized state initialization prevents scattered declarations
        and makes initialization order explicit.
        """
        # Application lifecycle
        self.closing = False
        self._device_config_initialized = False
        self._initial_connection_done = False
        self._deferred_connections_pending = True

        # Experiment tracking
        self.experiment_start_time = None
        self._last_cycle_bounds = None
        self._session_cycles_dir = None

        # Calibration state
        self._calibration_retry_count = 0
        self._max_calibration_retries = MAX_CALIBRATION_RETRIES
        self._calibration_completed = False
        self._qc_dialog = None

        # Channel/axis selection
        self._selected_axis = DEFAULT_AXIS
        self._selected_channel = None
        self._reference_channel = None
        self._ref_subtraction_enabled = False
        self._ref_channel = None

        # Data filtering
        self._filter_enabled = DEFAULT_FILTER_ENABLED
        self._filter_strength = DEFAULT_FILTER_STRENGTH
        self._filter_method = DEFAULT_FILTER_METHOD
        self._kalman_filters = {}
        self._flag_data = []

        # EMA live display filtering
        self._ema_state = {"a": None, "b": None, "c": None, "d": None}
        self._display_filter_method = "none"  # 'none', 'ema_light', 'ema_smooth'
        self._display_filter_alpha = 0.0  # Will be set based on selection

        # PHASE 1: Live Cycle Timeframe Mode (parallel to cursor system)
        self._live_cycle_timeframe = 5  # minutes (default)
        self._live_cycle_mode = "moving"  # 'moving' or 'fixed'
        self.USE_TIMEFRAME_MODE = False  # Feature flag - DISABLED (using legacy cursor mode)
        self._timeframe_baseline_wavelengths = {
            "a": None,
            "b": None,
            "c": None,
            "d": None,
        }  # Persistent baseline for moving window
        self._last_processed_time = {
            "a": -1.0,
            "b": -1.0,
            "c": -1.0,
            "d": -1.0,
        }  # Track last processed timestamp to avoid re-appending same data
        self._last_timeframe_update = 0  # Timestamp of last update (for throttling)

        # LED monitoring
        self._led_status_timer = None

        # Performance optimization (pre-computed lookups)
        self._channel_to_idx = CHANNEL_INDICES
        self._idx_to_channel = CHANNELS
        self._channel_pairs = [(ch, idx) for ch, idx in CHANNEL_INDICES.items()]

        # Acquisition/processing
        from queue import Queue

        self._spectrum_queue = Queue(maxsize=SPECTRUM_QUEUE_SIZE)
        self._processing_thread = None
        self._processing_active = False
        self._queue_stats = {"dropped": 0, "processed": 0, "max_size": 0}

        # Performance counters
        self._acquisition_counter = 0
        self._last_transmission_update = {"a": 0, "b": 0, "c": 0, "d": 0}
        self._sensorgram_update_counter = 0

        # UI update management
        self._pending_graph_updates = {"a": None, "b": None, "c": None, "d": None}
        self._skip_graph_updates = False
        self._has_stop_cursor = False

        # Baseline data recording
        self._baseline_recorder = None

    def _init_managers(self):
        """Initialize business layer managers (no UI dependencies).

        Creates all business logic managers required for hardware interaction
        and data processing. Managers are instantiated but not connected.

        Raises:
            Exception: If any critical manager fails to initialize

        """
        # Initialize pipeline registry BEFORE DataAcquisitionManager
        from affilabs.utils.pipelines import initialize_pipelines

        initialize_pipelines()
        logger.info("  Processing pipelines initialized")

        # Hardware manager (does NOT auto-connect)
        self.hardware_mgr = HardwareManager()
        if self.hardware_mgr is None:
            raise RuntimeError("HardwareManager initialization failed")

        # HAL device manager (optional)
        if HAL_AVAILABLE:
            try:
                self.device_manager = DeviceManager()
                logger.info("  DeviceManager (HAL) initialized")
            except Exception as e:
                logger.error(f"  DeviceManager failed to initialize: {e}")
                self.device_manager = None
        else:
            self.device_manager = None
            logger.info("  Using legacy HardwareManager only")

        # Data acquisition manager
        self.data_mgr = DataAcquisitionManager(self.hardware_mgr)
        if self.data_mgr is None:
            raise RuntimeError("DataAcquisitionManager initialization failed")

        # Recording manager
        self.recording_mgr = RecordingManager(self.data_mgr)
        if self.recording_mgr is None:
            raise RuntimeError("RecordingManager initialization failed")

        # Kinetic operations manager
        self.kinetic_mgr = KineticManager(self.hardware_mgr)
        if self.kinetic_mgr is None:
            raise RuntimeError("KineticManager initialization failed")

        # Data buffer manager
        self.buffer_mgr = DataBufferManager()
        if self.buffer_mgr is None:
            raise RuntimeError("DataBufferManager initialization failed")

        # Session quality monitor
        self.quality_monitor = SessionQualityMonitor(
            device_serial="unknown",
            session_id=None,
        )
        if self.quality_monitor is None:
            raise RuntimeError("SessionQualityMonitor initialization failed")

        # Segment queue (TEST MODE - minimal implementation)
        self.segment_queue = []  # List of segment definition dicts
        logger.info("  Segment queue initialized (TEST MODE)")

        logger.info("  All managers initialized successfully")

    def _init_services(self):
        """Initialize business services (pure logic, no UI).

        Creates high-level services that orchestrate business logic.
        Services may depend on managers but not on UI components.

        Raises:
            Exception: If any critical service fails to initialize

        """
        # Phase 1.2 business services
        self.transmission_calc = TransmissionCalculator(apply_led_correction=True)
        if self.transmission_calc is None:
            raise RuntimeError("TransmissionCalculator initialization failed")

        self.baseline_corrector = BaselineCorrector(method="polynomial", poly_order=1)
        if self.baseline_corrector is None:
            raise RuntimeError("BaselineCorrector initialization failed")

        logger.info(
            "  Business services initialized (TransmissionCalculator, BaselineCorrector)"
        )

        # Calibration and cycle coordinators
        self.calibration = CalibrationService(self)
        if self.calibration is None:
            raise RuntimeError("CalibrationService initialization failed")

        self.cycles = CycleCoordinator(self)
        if self.cycles is None:
            raise RuntimeError("CycleCoordinator initialization failed")

        # Performance profiler
        self.profiler = get_profiler()
        if self.profiler is None:
            logger.warning("  Profiler not available, performance tracking disabled")

        logger.info("  All services initialized successfully")

        logger.info("  Services initialized")

    def _create_main_window(self):
        """Create main window (UI layer entry point)."""
        logger.info("Creating main window...")

        # Create main window
        self.main_window = AffilabsMainWindow()

        # Pass hardware manager reference for settings application
        # This allows Settings tab to apply LED intensities without signal routing
        self.main_window.hardware_manager = self.hardware_mgr

        # Wire up elapsed time getter for pause markers
        def get_elapsed_time():
            if self.experiment_start_time is None:
                return None
            from affilabs.utils.time_utils import monotonic

            return monotonic() - self.experiment_start_time

        self.main_window._get_elapsed_time = get_elapsed_time

        # NOTE: Not storing app reference in UI (violates separation of concerns)
        # UI should only emit signals, not call app methods directly
        # All UIΓåÆApp communication happens through Qt signals

        # Verify spectroscopy plots availability
        if not hasattr(self.main_window, "transmission_curves"):
            logger.warning(
                "  Spectroscopy plots NOT found in main window - graphs will not display"
            )

        # Debug controller (requires main_window)
        from affilabs.utils.debug_controller import DebugController

        self.debug = DebugController(self)

        logger.info("  Main window created")

    def _init_coordinators(self):
        """Initialize UI coordinators (require main window)."""
        logger.info("Initializing coordinators...")

        # UI update coordinator and dialog manager
        if COORDINATORS_AVAILABLE:
            self.ui_updates = AL_UIUpdateCoordinator(self, self.main_window)
            self.dialog_manager = DialogManager(self.main_window)
            logger.info(
                "  UI coordinators initialized (AL_UIUpdateCoordinator, DialogManager)"
            )
        else:
            self.ui_updates = None
            self.dialog_manager = None
            logger.warning("  Running without UI coordinators (compatibility mode)")

    def _init_viewmodels(self):
        """Initialize ViewModels (UI-aware, require coordinators and services)."""
        logger.info("Initializing viewmodels...")

        # Device status view model
        self.device_status_vm = DeviceStatusViewModel(
            device_manager=self.device_manager if HAL_AVAILABLE else None,
        )
        if HAL_AVAILABLE and self.device_manager:
            logger.info("  DeviceStatusViewModel initialized with HAL DeviceManager")
        else:
            logger.info("  DeviceStatusViewModel initialized (legacy mode)")

        # SpectrumViewModel for each channel
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
                    self.transmission_calc, self.baseline_corrector, spectrum_processor
                )

            logger.info("  SpectrumViewModel initialized for all channels")
        except (ImportError, AttributeError) as e:
            logger.warning(f"  Failed to initialize SpectrumViewModel: {e}")
            self.spectrum_viewmodels = None
        except Exception as e:
            logger.error(
                f"  Unexpected error initializing SpectrumViewModel: {e}", exc_info=True
            )
            self.spectrum_viewmodels = None

        # CalibrationViewModel
        try:
            from services import CalibrationValidator

            self.calibration_viewmodel = CalibrationViewModel()
            calibration_validator = CalibrationValidator()
            self.calibration_viewmodel.set_validator(calibration_validator)
            logger.info("  CalibrationViewModel initialized with validator")
        except (ImportError, AttributeError) as e:
            logger.warning(f"  Failed to initialize CalibrationViewModel: {e}")
            self.calibration_viewmodel = None
        except Exception as e:
            logger.error(
                f"  Unexpected error initializing CalibrationViewModel: {e}",
                exc_info=True,
            )
            self.calibration_viewmodel = None

    def _connect_all_signals(self):
        """Connect all signals (require all subsystems initialized)."""
        logger.info("Connecting signals...")

        # Connect hardware manager signals to UI
        self._connect_signals()

        # Connect signals organized by subsystem (Phase 4 refactoring)
        self._connect_viewmodel_signals()
        self._connect_manager_signals()
        self._connect_ui_event_signals()

        logger.info("  All signals connected")

    def _finalize_and_show(self):
        """Finalize initialization and show main window."""
        logger.info("Finalizing application...")

        # Start processing thread (acquisition ΓåÆ processing separation)
        self._start_processing_thread()

        # UI update throttling - prevent excessive graph redraws (10 Hz = 100ms interval)
        from PySide6.QtCore import QTimer

        self._ui_update_timer = QTimer()
        self._ui_update_timer.timeout.connect(self._process_pending_ui_updates)
        self._ui_update_timer.setInterval(100)
        self._ui_update_timer.start()

        # Performance profiling timer (if enabled)
        if PROFILING_ENABLED and PROFILING_REPORT_INTERVAL > 0:
            self._profiling_timer = QTimer()
            self._profiling_timer.timeout.connect(self._print_profiling_stats)
            self._profiling_timer.setInterval(PROFILING_REPORT_INTERVAL * 1000)
            self._profiling_timer.start()
            logger.info(
                f"  Profiling enabled - stats every {PROFILING_REPORT_INTERVAL}s"
            )

        # Show window FIRST (before loading heavy widgets)
        logger.info("Showing main window...")
        if hasattr(self, "update_splash_message"):
            self.update_splash_message("Building interface...")

        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
        QApplication.processEvents()  # Force immediate render
        logger.info(f"  Window visible: {self.main_window.isVisible()}")

        # Load deferred widgets in background (after window visible)
        QTimer.singleShot(50, self._load_deferred_widgets)

        # DO NOT auto-connect hardware - user must press Power button
        logger.info("Ready - waiting for user to press Power button...")

    def _load_deferred_widgets(self):
        """Load heavy UI components after window is visible.

        This improves perceived startup time by showing the window immediately,
        then loading expensive components in the background.
        """
        try:
            logger.info("Loading deferred UI components...")
            # Update splash message
            if hasattr(self, "update_splash_message"):
                self.update_splash_message("Loading graphs...")

            # Load heavy graph widgets (PyQtGraph plots)
            if hasattr(self.main_window, "load_deferred_graphs"):
                self.main_window.load_deferred_graphs()
                logger.info("  Graph widgets loaded")

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
                logger.info("  Timeline graph cursors connected")

            # Connect cursor auto-follow signal (thread-safe)
            self.cursor_update_signal.connect(self._update_stop_cursor_position)
            logger.info("  Cursor auto-follow connected")

            # === Phase 2: Enable Timeframe Mode UI if flag is set ===
            if self.USE_TIMEFRAME_MODE:
                # NOTE: enable_timeframe_mode method not yet implemented in main window
                # self.main_window.enable_timeframe_mode(True)
                # Ensure we start in moving window mode
                self._on_timeframe_mode_changed("moving")
                logger.info("  ========================================")
                logger.info("  TIMEFRAME MODE ENABLED (Phase 3)")
                logger.info("  ========================================")
                logger.info("  - Cursors should be HIDDEN")
                logger.info("  - Moving Window mode active")
                logger.info(f"  - Duration: {self._live_cycle_timeframe} minutes")
                logger.info("  - Live Cycle shows last N minutes")
                logger.info("  ========================================")
            else:
                logger.info("  Timeframe mode disabled - using legacy cursor system")

            # Update cached attribute checks now that graphs are loaded
            self._has_stop_cursor = (
                hasattr(self.main_window, "full_timeline_graph")
                and hasattr(self.main_window.full_timeline_graph, "stop_cursor")
                and self.main_window.full_timeline_graph.stop_cursor is not None
            )
            logger.info(f"  ╬ô├ñΓòúΓê⌐Γòò├à  Stop cursor available: {self._has_stop_cursor}")

            # Connect polarizer toggle button to servo control
            if hasattr(self.main_window, "polarizer_toggle_btn"):
                self.main_window.polarizer_toggle_btn.clicked.connect(
                    self._on_polarizer_toggle_clicked
                )
                logger.info("  Polarizer toggle connected")

            # Connect mouse events for channel selection and flagging
            if hasattr(self.main_window, "cycle_of_interest_graph"):
                self.main_window.cycle_of_interest_graph.scene().sigMouseClicked.connect(
                    self._on_graph_clicked,
                )
                logger.info("  Graph click events connected")

            # Mark deferred loading as complete
            self._deferred_connections_pending = False

            # Now connect UI button/control signals (after graphs are loaded)
            self._connect_ui_signals()
            logger.info("  UI control signals connected")

            logger.info("Deferred UI components loaded successfully")

        except Exception as e:
            logger.error(f"[X] Error loading deferred widgets: {e}", exc_info=True)
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
            self._on_hardware_connected, Qt.QueuedConnection
        )
        self.hardware_mgr.hardware_disconnected.connect(
            self._on_hardware_disconnected, Qt.QueuedConnection
        )
        self.hardware_mgr.connection_progress.connect(
            self._on_connection_progress, Qt.QueuedConnection
        )
        self.hardware_mgr.error_occurred.connect(
            self._on_hardware_error, Qt.QueuedConnection
        )

        # === DATA ACQUISITION MANAGER SIGNALS ===
        # Queued connections for thread safety (data manager runs in worker thread)
        self.data_mgr.spectrum_acquired.connect(
            self._on_spectrum_acquired, Qt.QueuedConnection
        )
        self.data_mgr.acquisition_started.connect(
            self._on_acquisition_started, Qt.QueuedConnection
        )
        self.data_mgr.acquisition_stopped.connect(
            self._on_acquisition_stopped, Qt.QueuedConnection
        )
        self.data_mgr.acquisition_error.connect(
            self._on_acquisition_error, Qt.QueuedConnection
        )

        # === CALIBRATION MANAGER SIGNALS ===
        # Connect to calibration_complete to update optics_ready status
        self.calibration.calibration_complete.connect(
            self._on_calibration_complete_status_update, Qt.QueuedConnection
        )
        # NOTE: _on_calibration_complete_status_update handles BOTH status updates AND QC dialog
        logger.info(
            "Connected: calibration.calibration_complete -> _on_calibration_complete_status_update"
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
        """Handler for calibration completion - updates status AND shows QC dialog.

        Args:
            calibration_data: CalibrationData object (immutable dataclass)

        """
        try:
            # === PART 1: Apply calibration to acquisition manager ===
            logger.info("=" * 80)
            logger.info("CALIBRATION COMPLETE - APPLYING TO ACQUISITION MANAGER")
            logger.info("=" * 80)

            self.data_mgr.apply_calibration(calibration_data)

            logger.info("Calibration data applied successfully")
            logger.info("System ready for live acquisition")

            # Save SPR model path to device config
            device_serial = (
                self.hardware_mgr.usb.serial_number if self.hardware_mgr.usb else None
            )
            if calibration_data and self.main_window.device_config and device_serial:
                from pathlib import Path

                spr_model_path = Path(
                    f"OpticalSystem_QC/{device_serial}/spr_calibration/led_calibration_spr_processed_latest.json"
                )
                if spr_model_path.exists():
                    self.main_window.device_config.set_spr_model_path(
                        str(spr_model_path)
                    )
                    self.main_window.device_config.save()
                    logger.info(
                        f"Γ£ô SPR model path saved to device_config: {spr_model_path}"
                    )
                else:
                    logger.warning(
                        f"ΓÜá∩╕Å SPR model file not found at expected path: {spr_model_path}"
                    )

            # Save QC report for traceability and ML model
            if calibration_data and device_serial:
                from affilabs.managers.qc_report_manager import QCReportManager

                qc_manager = QCReportManager()

                # Convert calibration data to dict for saving
                qc_data_dict = (
                    calibration_data.to_dict()
                    if hasattr(calibration_data, "to_dict")
                    else calibration_data
                )

                # Get software version
                software_version = getattr(self.main_window, "version", "2.0")

                # Save QC report
                report_path = qc_manager.save_qc_report(
                    calibration_data=qc_data_dict,
                    device_serial=device_serial,
                    software_version=software_version,
                )

                if report_path:
                    logger.info(
                        f"Γ£ô QC report saved for ML/traceability: {report_path.name}"
                    )

                    # Generate HTML export
                    html_path = qc_manager.export_to_html(report_path)
                    if html_path:
                        logger.info(f"≡ƒôä HTML report exported: {html_path.name}")

            logger.info("=" * 80)
            logger.info("")

            # === PART 2: Update hardware manager status ===
            # CalibrationData is a dataclass, not a dict - check if channels were calibrated
            optics_ready = (
                len(calibration_data.get_channels()) > 0 if calibration_data else False
            )
            logger.info(
                f"Calibration complete signal received - optics_ready={optics_ready}"
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
                ch_error_list, "full", s_ref_qc_results
            )
            logger.info(
                f"Hardware manager calibration status updated - ch_errors={ch_error_list}"
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
                    "Device status updated directly (no hardware scan post-calibration)"
                )

                # Mark calibration as completed (used by power-on workflow)
                self._calibration_completed = True

                logger.info("Sensor and Optics status updated to READY in UI")
            else:
                # Calibration failed - optics not ready
                logger.warning(
                    "Calibration completed but optics not ready (some channels failed)"
                )
                self._update_device_status_ui(
                    {"optics_ready": False, "sensor_ready": True}
                )

            # === PART 3: Show QC dialog ===
            self._show_qc_dialog(calibration_data)

        except Exception as e:
            logger.error(
                f"[X] Failed to process calibration completion: {e}", exc_info=True
            )

    def _show_qc_dialog(self, calibration_data):
        """Show QC dialog with calibration results (Layer 1 - UI responsibility).

        Args:
            calibration_data: CalibrationData instance

        """
        try:
            from affilabs.widgets.calibration_qc_dialog import CalibrationQCDialog

            # Convert to dict for QC dialog
            qc_data = calibration_data.to_dict()

            logger.info("Showing QC report dialog (modal)...")

            # Create and show dialog (modal, blocks until closed)
            self._qc_dialog = CalibrationQCDialog(
                parent=self.main_window,
                calibration_data=qc_data,
            )
            self._qc_dialog.exec()

            logger.info("QC report displayed and closed (modal)")
            logger.info("System ready - Click START button to begin live acquisition")

        except Exception as e:
            logger.error(f"[X] Failed to show QC report: {e}", exc_info=True)

    def _connect_ui_signals(self):
        """Connect UI signals after handler method is defined."""
        # === UI SIGNALS (user requests) ===
        self.main_window.power_on_requested.connect(self._on_power_on_requested)
        logger.info(
            "Connected: main_window.power_on_requested -> _on_power_on_requested"
        )

        self.main_window.power_off_requested.connect(self._on_power_off_requested)
        self.main_window.recording_start_requested.connect(
            self._on_recording_start_requested
        )
        self.main_window.recording_stop_requested.connect(
            self._on_recording_stop_requested
        )
        # NOTE: These signals not yet implemented in main window
        # self.main_window.clear_graphs_requested.connect(self._on_clear_graphs_requested)
        # self.main_window.clear_flags_requested.connect(self._on_clear_flags_requested)
        # self.main_window.pipeline_changed.connect(self._on_pipeline_changed)
        logger.info("Connected: main_window UI action signals")

        # === DEBUG SHORTCUTS ===
        from PySide6.QtGui import QKeySequence, QShortcut

        logger.info("=" * 80)
        logger.info("REGISTERING DEBUG SHORTCUTS")
        logger.info("=" * 80)

        # Ctrl+Shift+C: Bypass calibration - DISABLED (missing debug_helpers module)
        # bypass_calibration_shortcut = QShortcut(QKeySequence("Ctrl+Shift+C"), self.main_window)
        # bypass_calibration_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        # bypass_calibration_shortcut.activated.connect(self.debug.bypass_calibration)
        # logger.info(f"[OK] Ctrl+Shift+C registered: {bypass_calibration_shortcut}")

        # Ctrl+Shift+S: Start simulation mode (inject fake spectra)
        simulation_shortcut = QShortcut(QKeySequence("Ctrl+Shift+S"), self.main_window)
        simulation_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        simulation_shortcut.activated.connect(self.debug.start_simulation)
        logger.info(f"[OK] Ctrl+Shift+S registered: {simulation_shortcut}")
        logger.info(f"   Context: {simulation_shortcut.context()}")
        logger.info(f"   Key: {simulation_shortcut.key().toString()}")

        # Ctrl+Shift+1: Single data point test (minimal test)
        single_point_shortcut = QShortcut(
            QKeySequence("Ctrl+Shift+1"), self.main_window
        )
        single_point_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        single_point_shortcut.activated.connect(self.debug.send_single_data_point)
        logger.info(f"[OK] Ctrl+Shift+1 registered: {single_point_shortcut}")
        logger.info(f"   Context: {single_point_shortcut.context()}")
        logger.info(f"   Key: {single_point_shortcut.key().toString()}")

        logger.info("=" * 80)
        logger.info("[DEBUG] Ctrl+Shift+S to start spectrum simulation")

        self.main_window.acquisition_pause_requested.connect(
            self._on_acquisition_pause_requested
        )
        self.main_window.export_requested.connect(self._on_export_requested)

        # === TIMEFRAME MODE SIGNALS (Phase 2 - Cursor Replacement) ===
        if self.USE_TIMEFRAME_MODE:
            # NOTE: These signals not yet implemented in main window
            # self.main_window.timeframe_mode_changed.connect(self._on_timeframe_mode_changed)
            # self.main_window.timeframe_duration_changed.connect(self._on_timeframe_duration_changed)
            logger.info("Timeframe mode enabled (signals pending implementation)")

        # === UI CONTROL SIGNALS (direct connections - not through event bus) ===
        self._connect_ui_control_signals()

        logger.info("[OK] All signal connections registered")

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

        # --- Data Filtering Controls (moved to Graphic Display tab) ---
        # EMA filter controls are in sidebar, connected in _connect_sidebar_signals()

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

        # Baseline Capture button (REBUILT - direct connection, no lambda)
        if hasattr(ui, "baseline_capture_btn"):
            ui.baseline_capture_btn.clicked.connect(self._on_record_baseline_clicked)
            logger.info("[OK] Connected Baseline Capture button to handler")
        else:
            logger.warning("[WARN] baseline_capture_btn NOT found in UI")

        # Advanced Settings dialog - connect optical calibration signal
        if hasattr(ui, "advanced_menu") and ui.advanced_menu is not None:
            if hasattr(ui.advanced_menu, "measure_afterglow_sig"):
                ui.advanced_menu.measure_afterglow_sig.connect(
                    self._on_oem_led_calibration
                )
                logger.info(
                    "[OK] Connected Advanced Settings optical calibration signal"
                )

        # Start Cycle button: App layer needs to start data acquisition
        # (UI's start_cycle() handles experiment queue - different purpose)
        ui.sidebar.start_cycle_btn.clicked.connect(self._on_start_button_clicked)
        logger.info(
            "[OK] Connected start_cycle_btn -> _on_start_button_clicked (acquisition start)"
        )

        # Add to Queue button (TEST MODE - segment queue)
        if hasattr(ui.sidebar, "add_to_queue_btn"):
            ui.sidebar.add_to_queue_btn.clicked.connect(self._on_add_to_queue)
            logger.info(
                "[OK] Connected add_to_queue_btn -> _on_add_to_queue (TEST MODE)"
            )
        else:
            logger.warning("[WARN] add_to_queue_btn NOT found in UI")

    def _connect_viewmodel_signals(self):
        """Connect ViewModel signals to handlers (Phase 4 refactoring).

        Groups all ViewModel signal connections for better organization.
        """
        # === DEVICE STATUS VIEWMODEL ===
        self.device_status_vm.device_connected.connect(self._on_vm_device_connected)
        self.device_status_vm.device_disconnected.connect(
            self._on_vm_device_disconnected
        )
        self.device_status_vm.device_error.connect(self._on_vm_device_error)
        self.device_status_vm.overall_status_changed.connect(self._on_vm_status_changed)
        logger.info("[OK] DeviceStatusViewModel signals connected")

        # === SPECTRUM VIEWMODELS ===
        if self.spectrum_viewmodels:
            for channel, vm in self.spectrum_viewmodels.items():
                vm.spectrum_updated.connect(
                    lambda ch, wl, trans, channel=channel: self._on_spectrum_updated(
                        channel, wl, trans
                    ),
                )
                vm.raw_spectrum_updated.connect(
                    lambda ch, wl, raw, channel=channel: self._on_raw_spectrum_updated(
                        channel, wl, raw
                    ),
                )
            logger.info("[OK] SpectrumViewModel signals connected for all channels")

        # === CALIBRATION VIEWMODEL ===
        if self.calibration_viewmodel:
            self.calibration_viewmodel.calibration_started.connect(
                self._on_cal_vm_started
            )
            self.calibration_viewmodel.calibration_progress.connect(
                self._on_cal_vm_progress
            )
            self.calibration_viewmodel.calibration_complete.connect(
                self._on_cal_vm_complete
            )
            self.calibration_viewmodel.calibration_failed.connect(
                self._on_cal_vm_failed
            )
            self.calibration_viewmodel.validation_complete.connect(
                self._on_cal_vm_validation_complete
            )
            logger.info("[OK] CalibrationViewModel signals connected")

    def _connect_manager_signals(self):
        """Connect manager/service signals to handlers (Phase 4 refactoring).

        Groups all manager signal connections including hardware, acquisition,
        calibration, recording, and kinetic managers.
        """
        # === CALIBRATION SERVICE ===
        # NOTE: Already connected in _connect_signals() at line 598 to _on_calibration_complete_status_update
        # (merged with _on_calibration_complete to avoid duplicate QC dialogs)
        logger.info(
            "[OK] CalibrationService signals already connected in _connect_signals()"
        )

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
            self.main_window.sidebar, "tabs"
        ):
            self.main_window.sidebar.tabs.currentChanged.connect(self._on_tab_changing)
        if hasattr(self.main_window, "content_stack"):
            self.main_window.content_stack.currentChanged.connect(self._on_page_changed)

        # === EMA DISPLAY FILTER CONTROLS ===
        ui = self.main_window.sidebar
        if hasattr(ui, "filter_none_radio"):
            ui.filter_none_radio.toggled.connect(
                lambda checked: self._set_display_filter(0) if checked else None
            )
        if hasattr(ui, "filter_light_radio"):
            ui.filter_light_radio.toggled.connect(
                lambda checked: self._set_display_filter(1) if checked else None
            )
        if hasattr(ui, "filter_smooth_radio"):
            ui.filter_smooth_radio.toggled.connect(
                lambda checked: self._set_display_filter(2) if checked else None
            )

        # Initialize filter to default (None/Raw) - must be outside the if block
        self._set_display_filter(0)
        logger.info("[OK] EMA display filter initialized to None (Raw)")

        logger.info("[OK] UI event signals connected (tabs/pages/filters)")

    def _set_display_filter(self, filter_id: int):
        """Set EMA display filter method based on radio button selection.

        Args:
            filter_id: 0=None (Raw), 1=EMA Light (╬▒=0.33), 2=EMA Smooth (╬▒=0.18)

        """
        filter_configs = [
            {"method": "none", "alpha": 0.0, "label": "None (Raw)"},
            {"method": "ema_light", "alpha": 0.33, "label": "EMA Light (╬▒=0.33)"},
            {"method": "ema_smooth", "alpha": 0.18, "label": "EMA Smooth (╬▒=0.18)"},
        ]

        if 0 <= filter_id < len(filter_configs):
            config = filter_configs[filter_id]
            self._display_filter_method = config["method"]
            self._display_filter_alpha = config["alpha"]

            # Reset EMA state when changing filters
            self._ema_state = {"a": None, "b": None, "c": None, "d": None}

            logger.info(f"≡ƒÄ¢ Display filter changed to: {config['label']}")
            logger.info(
                f"   Method: {self._display_filter_method}, Alpha: {self._display_filter_alpha}"
            )

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
        logger.info("Γëí╞Æ├£├ç User requested start - beginning acquisition")

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
                        cd.s_pol_ref, cd.wavelengths
                    )

                self._live_data_dialog.show()
                self._live_data_dialog.raise_()
                self._live_data_dialog.activateWindow()
                logger.info("[OK] Live data dialog opened")
            except Exception as e:
                logger.exception(f"Failed to open live data dialog: {e}")
            return

        # PHASE 1: Validate hardware connection and calibration
        logger.info("Γëí╞Æ├╢├¼ PHASE 1: Checking hardware status...")
        try:
            if self.hardware_mgr.ctrl:
                logger.info("   [OK] Controller connected")
            else:
                logger.warning("   ╬ô├£├íΓê⌐Γòò├à No controller found")

            if self.hardware_mgr.usb:
                logger.info("   [OK] Spectrometer connected")
            else:
                logger.warning("   ╬ô├£├íΓê⌐Γòò├à No spectrometer found")

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
                # Use LED intensities from calibration data
                led_intensities = {}
                try:
                    if self.main_window.device_config:
                        # TODO: Integrate 3-stage linear LED calibration
                        # from led_calibration_manager import get_led_intensities_for_scan
                        # intensities_dict = get_led_intensities_for_scan(60000, float(integration_time))
                        # led_intensities = {'a': intensities_dict['A'], 'b': intensities_dict['B'],
                        #                   'c': intensities_dict['C'], 'd': intensities_dict['D']}

                        # For now: Use calibrated P-mode intensities from calibration data
                        led_intensities = getattr(cd, "p_mode_intensities", {}) or {}
                        logger.info(
                            f"   [STATIC] Using P-mode intensities: {led_intensities}"
                        )
                except Exception as e:
                    logger.warning(f"   [FALLBACK] Could not load LED intensities: {e}")
                    led_intensities = getattr(cd, "p_mode_intensities", {}) or {}
            else:
                logger.info(
                    "   ╬ô├ñΓòúΓê⌐Γòò├à System not calibrated (using bypass mode defaults)"
                )
                integration_time = 40
                led_intensities = {"a": 255, "b": 150, "c": 150, "d": 255}

            logger.info("[OK] Hardware validation complete")
        except Exception as e:
            logger.exception(f"[X] Hardware validation failed: {e}")
            ui_error(
                self,
                "Hardware Check Failed",
                f"Hardware check failed:\n{e}",
            )
            return

        # PHASE 2: Configure hardware
        logger.info("[PHASE 2] Configuring hardware...")

        # 2A: Polarizer
        try:
            ctrl = self.hardware_mgr.ctrl
            if ctrl and hasattr(ctrl, "set_mode"):
                logger.info("   Setting polarizer to P-mode...")
                ctrl.set_mode("p")
                import time

                try:
                    import settings

                    settle_ms = getattr(settings, "POLARIZER_SETTLE_MS", 400)
                except Exception:
                    settle_ms = 400
                time.sleep(max(0, float(settle_ms)) / 1000.0)
                logger.info("   [OK] Polarizer configured")
            else:
                logger.warning("   ╬ô├£├íΓê⌐Γòò├à Controller not available")
        except Exception as e:
            logger.exception(f"[X] Polarizer configuration failed: {e}")

        # 2B: Integration time
        try:
            usb = self.hardware_mgr.usb
            if usb and hasattr(usb, "set_integration"):
                logger.info(f"   Setting integration time: {integration_time}ms...")
                usb.set_integration(integration_time)
                logger.info("   [OK] Integration time configured")
            else:
                logger.warning("   ╬ô├£├íΓê⌐Γòò├à Spectrometer not available")
        except Exception as e:
            logger.exception(f"[X] Integration time configuration failed: {e}")

        # 2C: LED intensities
        try:
            ctrl = self.hardware_mgr.ctrl
            if ctrl and hasattr(ctrl, "set_intensity"):
                logger.info(f"   Setting LED intensities: {led_intensities}...")
                for channel, intensity in led_intensities.items():
                    ctrl.set_intensity(channel, intensity)
                logger.info("   [OK] LED intensities configured")
            else:
                logger.warning("   ╬ô├£├íΓê⌐Γòò├à Controller not available")
        except Exception as e:
            logger.exception(f"[X] LED configuration failed: {e}")

        logger.info("[OK] Hardware configuration complete")

        # PHASE 3: Start data acquisition thread
        logger.info("Γëí╞Æ├£├ç PHASE 3: Starting data acquisition thread...")
        try:
            # This is the critical step - starting the actual acquisition
            self.data_mgr.start_acquisition()
            logger.info("[OK] Data acquisition thread started successfully")
        except Exception as e:
            logger.exception(f"[X] Failed to start acquisition: {e}")
            from widgets.message import show_message

            show_message(f"Failed to start acquisition:\n{e}", msg_type="Error")
            return

        # PHASE 4: Open live data dialog (NO automatic recording)
        logger.info("Γëí╞Æ├┤├¿ Opening live data dialog...")
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
                        f"[OK] Loaded S-mode reference spectra: {list(cd.s_pol_ref.keys())}"
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
        logger.info("Γëí╞Æ├ä┬í Updating UI state...")
        try:
            self.main_window.enable_controls()
            if hasattr(self.main_window, "sidebar") and hasattr(
                self.main_window.sidebar, "start_cycle_btn"
            ):
                self.main_window.sidebar.start_cycle_btn.setEnabled(True)
            self._on_acquisition_started()
            logger.info("[OK] UI state updated")
        except Exception as e:
            logger.exception(f"Failed to update UI: {e}")

        logger.info("=" * 80)
        logger.info("[OK] LIVE ACQUISITION STARTED - View data in dialog")
        logger.info("=" * 80)

    # =========================================================================
    # SEGMENT QUEUE MANAGEMENT (TEST MODE - Minimal Implementation)
    # =========================================================================

    def _on_add_to_queue(self):
        """Add current cycle configuration to segment queue (TEST MODE).

        This is a minimal test implementation to validate the architecture.
        Creates a segment definition dict without executing it.
        """
        import re
        import time

        logger.info("≡ƒº¬ TEST MODE: Adding cycle to segment queue")

        try:
            # Read form values
            cycle_type = self.main_window.sidebar.cycle_type_combo.currentText()
            length_text = self.main_window.sidebar.cycle_length_combo.currentText()
            length_minutes = int(length_text.split()[0])  # Extract number from "5 min"
            note = self.main_window.sidebar.note_input.toPlainText()
            units = self.main_window.sidebar.units_combo.currentText().split()[
                0
            ]  # Extract unit from "nM (Nanomolar)"

            # Create segment definition
            segment = {
                "name": f"Cycle {len(self.segment_queue) + 1}",
                "type": cycle_type,
                "length_minutes": length_minutes,
                "note": note,
                "units": units,
                "timestamp": time.time(),
                "status": "pending",
            }

            # Parse concentration tags from note
            tags = re.findall(r"\[([A-D]|ALL):(\d+\.?\d*)\]", note)
            if tags:
                segment["concentrations"] = dict(tags)
                logger.info(
                    f"   Parsed concentrations: {segment['concentrations']} {units}"
                )

            # Add to queue
            self.segment_queue.append(segment)

            # Log success
            logger.info(f"[OK] Added to queue: {segment['name']}")
            logger.info(f"   Type: {segment['type']}")
            logger.info(f"   Length: {segment['length_minutes']} minutes")
            logger.info(f"   Note: {segment['note'][:100]}...") if len(
                segment["note"]
            ) > 100 else logger.info(f"   Note: {segment['note']}")
            logger.info(f"   Queue size: {len(self.segment_queue)}")

            # Update intelligence bar
            if hasattr(self.main_window.sidebar, "intel_message_label"):
                self.main_window.sidebar.intel_message_label.setText(
                    f"ΓåÆ Added {segment['name']} to queue ({len(self.segment_queue)} total)",
                )
                self.main_window.sidebar.intel_message_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #34C759;"  # Green for success
                    "background: transparent;"
                    "font-weight: 600;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
                )

            # Validate queue structure
            self._validate_segment_queue()

        except Exception as e:
            logger.exception(f"[ERROR] Failed to add cycle to queue: {e}")
            if hasattr(self.main_window.sidebar, "intel_message_label"):
                self.main_window.sidebar.intel_message_label.setText(
                    f"Γ£ù Failed to add: {e}"
                )
                self.main_window.sidebar.intel_message_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #FF3B30;"  # Red for error
                    "background: transparent;"
                    "font-weight: 600;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
                )

    def _validate_segment_queue(self):
        """Validate segment queue structure (TEST MODE).

        Logs queue contents and validates data structure.
        This helps verify the architecture is sound.
        """
        logger.info("=" * 80)
        logger.info("≡ƒº¬ SEGMENT QUEUE VALIDATION TEST")
        logger.info("=" * 80)
        logger.info(f"Queue size: {len(self.segment_queue)} segments")
        logger.info("")

        for i, seg in enumerate(self.segment_queue):
            logger.info(f"[{i + 1}] {seg['name']}")
            logger.info(f"    Type: {seg['type']}")
            logger.info(f"    Length: {seg['length_minutes']} minutes")
            logger.info(f"    Status: {seg['status']}")

            if "concentrations" in seg:
                logger.info(
                    f"    Concentrations: {seg['concentrations']} {seg['units']}"
                )

            if seg["note"]:
                logger.info(f"    Note: {seg['note'][:80]}...") if len(
                    seg["note"]
                ) > 80 else logger.info(f"    Note: {seg['note']}")

            logger.info("")

        logger.info("=" * 80)
        logger.info("[OK] Queue validation complete")
        logger.info("=" * 80)

    def _on_scan_requested(self):
        """User clicked Scan button in UI."""
        logger.info("User requested hardware scan")
        self.hardware_mgr.scan_and_connect()

    def _on_hardware_connected(self, status: dict):
        """Hardware connection completed and update Device Status UI."""
        # Deduplicate rapid-fire signals (prevent double-processing within 500ms)
        from affilabs.utils.time_utils import monotonic

        current_time = monotonic()
        if hasattr(self, "_last_hw_callback_time"):
            time_since_last = current_time - self._last_hw_callback_time
            if time_since_last < 0.5:  # Less than 500ms since last callback
                logger.debug(
                    f"Γëí╞Æ├┤├¿ Skipping duplicate hardware callback ({time_since_last * 1000:.0f}ms since last)"
                )
                return
        self._last_hw_callback_time = current_time

        logger.info("Γëí╞Æ├╢├« Hardware connection callback received")
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
                f"[OK] Scan SUCCESSFUL - found valid hardware: {', '.join(valid_hardware)}"
            )
            self.main_window.set_power_state("connected")
        else:
            logger.warning("╬ô├£├íΓê⌐Γòò├à Scan FAILED - no valid hardware combinations found")
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
                error_msg = "No devices found.\n\nPlease check:\n╬ô├ç├│ USB connections\n╬ô├ç├│ Device power\n╬ô├ç├│ Driver installation"

            from widgets.message import show_message

            show_message(error_msg, msg_type="Warning", title="Connection Failed")
            return  # Exit early if scan failed

        # Re-initialize device config with actual device serial number (ONLY on initial connection)
        device_serial = status.get("spectrometer_serial")
        if device_serial and not self._device_config_initialized:
            logger.info(
                f"Re-initializing device configuration for S/N: {device_serial}"
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
                logger.info("Γëí╞Æ├┤├» APPLYING SPECIAL CASE CONFIGURATION")
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
                "Hardware status update received (not initial connection) - skipping calibration check"
            )
        else:
            # No spectrometer detected - this is a new OEM device that needs provisioning
            logger.warning("╬ô├£├íΓê⌐Γòò├à No spectrometer serial in hardware status")

            if status.get("ctrl_type"):
                # Controller detected but no spectrometer - trigger OEM device config flow
                logger.info("=" * 80)
                logger.info("Γëí╞Æ├à┬í NEW DEVICE DETECTED - OEM Provisioning Required")
                logger.info("=" * 80)
                logger.info(f"   Controller: {status.get('ctrl_type')}")
                logger.info("   Spectrometer: NOT CONNECTED")
                logger.info("")
                logger.info("Γëí╞Æ├┤├» Starting OEM device configuration workflow:")
                logger.info(
                    "   1. Collect device info (LED model, fiber diameter, etc.)"
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
                ui_info(
                    self,
                    "OEM Device Provisioning",
                    "New Device Detected!\n\n"
                    f"Controller: {status.get('ctrl_type')}\n"
                    f"Spectrometer: NOT CONNECTED\n\n"
                    "Please complete device configuration,\n"
                    "then connect the spectrometer to begin\n"
                    "automatic calibration.",
                )
            else:
                # Fallback to default config
                logger.warning("Using default config")
                self.main_window._init_device_config(device_serial=None)

        # Update last power-on timestamp in maintenance tracking (only on initial connection)
        if self._device_config_initialized:
            logger.debug(
                "Hardware status update received (not initial connection) - skipping timestamp update"
            )
        else:
            self.main_window.update_last_power_on()

        # Update Device Status UI with hardware details (always, even on status updates)
        logger.debug(
            f"Γëí╞Æ├╢├¼ Calling _update_device_status_ui with optics_ready={status.get('optics_ready')}, sensor_ready={status.get('sensor_ready')}"
        )
        self._update_device_status_ui(status)

        # Start LED status monitoring timer (V1.1+ firmware)
        if not self._device_config_initialized:
            self._start_led_status_monitoring()

        # Load servo positions and LED intensities from device config (only on initial connection)
        if self._device_config_initialized:
            logger.debug(
                "Hardware status update received (not initial connection) - skipping device settings reload"
            )
        else:
            self._load_device_settings()

        # === CRITICAL CHECK: Verify bilinear model exists before allowing live view ===
        # If no model exists, redirect to OEM LED Calibration workflow
        if not self._device_config_initialized and device_serial:
            logger.info("=" * 80)
            logger.info("≡ƒöì CHECKING FOR BILINEAR MODEL...")
            logger.info("=" * 80)

            model_exists = False
            try:
                from affilabs.utils.model_loader import (
                    LEDCalibrationModelLoader,
                    ModelNotFoundError,
                )

                model = LEDCalibrationModelLoader()
                model.load_model(device_serial)

                # Verify model has all required parameters
                model_info = model.get_model_info()
                r2_scores = model_info.get("r2_scores", {})

                # Check if all channels have valid R┬▓ scores
                required_channels = ["A", "B", "C", "D"]
                all_channels_valid = all(
                    ch in r2_scores
                    and "S" in r2_scores[ch]
                    and r2_scores[ch]["S"] > 0.5
                    for ch in required_channels
                )

                if all_channels_valid:
                    model_exists = True
                    logger.info(
                        f"Γ£ô Valid bilinear model found for detector {device_serial}"
                    )
                    logger.info(
                        f"  Model timestamp: {model_info.get('timestamp', 'Unknown')}"
                    )
                    logger.info(f"  R┬▓ scores: {r2_scores}")
                else:
                    logger.warning("ΓÜá∩╕Å  Model exists but has invalid/missing parameters")

            except ModelNotFoundError as e:
                logger.warning(f"ΓÜá∩╕Å  No bilinear model found: {e}")
            except Exception as e:
                logger.warning(f"ΓÜá∩╕Å  Model check failed: {e}")

            if not model_exists:
                logger.warning("=" * 80)
                logger.warning("ΓÜá∩╕Å  NO VALID MODEL ΓåÆ REDIRECTING TO OEM CALIBRATION")
                logger.warning("=" * 80)
                logger.warning("")
                logger.warning(
                    "Cannot start live view without a calibrated bilinear model."
                )
                logger.warning(
                    "The system will now launch OEM Calibration workflow (servo + LED)."
                )
                logger.warning("")

                # Show dialog to user
                from widgets.message import show_message

                show_message(
                    "No Calibration Model Found!\n\n"
                    f"Detector: {device_serial}\n\n"
                    "This device requires OEM calibration before use.\n"
                    "The OEM Calibration workflow will now start.\n\n"
                    "This process will:\n"
                    "  1. Calibrate servo positions (S/P polarization)\n"
                    "  2. Measure LED characteristics\n"
                    "  3. Generate bilinear model\n"
                    "  4. Enable live view functionality",
                    title="Calibration Required",
                    msg_type="Warning",
                    parent=self.main_window,
                )

                # Trigger OEM Calibration workflow
                from PySide6.QtCore import QTimer

                QTimer.singleShot(500, self._on_oem_led_calibration)
                return  # Exit early - don't proceed to normal startup

            logger.info("=" * 80)
            logger.info("")

        # Check if OEM calibration workflow should be triggered
        # This happens when: config was just completed + spectrometer now connected
        if self.main_window.oem_config_just_completed and status.get("spectrometer"):
            logger.info("=" * 80)
            logger.info(
                "Γëí╞Æ├à┬í OEM Config Complete + Spectrometer Connected ╬ô├Ñ├å Auto-Starting Calibration"
            )
            logger.info("=" * 80)
            self.main_window.oem_config_just_completed = False  # Reset flag

            # Trigger calibration workflow
            if hasattr(self.main_window, "_start_oem_calibration_workflow"):
                self.main_window._start_oem_calibration_workflow()
            else:
                logger.error(
                    "_start_oem_calibration_workflow method not found in main_window"
                )

        # Update calibration dialog if it exists and is waiting for hardware
        calibration_dialog = self.calibration.dialog if self.calibration else None
        if calibration_dialog and not calibration_dialog._is_closing:
            if status.get("ctrl_type") and status.get("spectrometer"):
                # Both hardware components detected
                logger.info("Calibration dialog updated: Hardware detected")
                calibration_dialog.update_status(
                    "Hardware detected:\n"
                    f"ΓÇó Controller: {status.get('ctrl_type')}\n"
                    "ΓÇó Spectrometer: Connected\n\n"
                    "Click Start to begin calibration.",
                )
            elif status.get("spectrometer") and not status.get("ctrl_type"):
                logger.warning("Spectrometer found but controller missing")
                calibration_dialog.update_status(
                    "Controller not detected\n\n"
                    "Please connect the SPR controller\n"
                    "to continue calibration.",
                )
            elif status.get("ctrl_type") and not status.get("spectrometer"):
                logger.warning("Controller found but spectrometer missing")
                calibration_dialog.update_status(
                    "Spectrometer not detected\n\n"
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
            logger.debug("New hardware connection - calibration flag reset")

            # Start calibration ONLY if BOTH controller and spectrometer are connected
            # Calibration requires both hardware components
            if (
                status.get("ctrl_type")
                and status.get("spectrometer")
                and not self._calibration_completed
            ):
                logger.info("=" * 80)
                logger.info("Γëí╞Æ├ä┬╗ STARTING CALIBRATION WORKFLOW")
                logger.info("=" * 80)
                logger.info("   Hardware Detected:")
                logger.info(f"     Controller: {status.get('ctrl_type')}")
                logger.info("     Spectrometer: Connected")

                # Servo positions will be loaded from device_config.json
                # The bilinear model handles calibration quality validation
                logger.info(
                    "Γä╣∩╕Å Loading servo positions from device_config (single source of truth)..."
                )

                # OPTIMIZATION: Check for optical calibration file first
                # If missing, run full calibration workflow automatically (LED ΓåÆ afterglow)
                from affilabs.utils.device_integration import (
                    get_device_optical_calibration_path,
                )

                # get_device_optical_calibration_path() gets serial from device_manager.current_device_serial
                optical_cal_path = get_device_optical_calibration_path()

                if not optical_cal_path or not optical_cal_path.exists():
                    logger.info(
                        "≡ƒöº Optical calibration file not found - starting LED calibration"
                    )
                    # Run LED calibration (handled by CalibrationService)
                    self.calibration.start_calibration()
                    return
                # Trigger calibration with dialog (LED only, optical cal already exists)
                logger.info("Optical calibration exists - running LED calibration only")
                self.calibration.start_calibration()
            elif (
                status.get("ctrl_type")
                and status.get("spectrometer")
                and self._calibration_completed
            ):
                logger.info("[OK] Calibration already completed - ready for live data")
            elif status.get("spectrometer") and not status.get("ctrl_type"):
                logger.warning("╬ô├£├íΓê⌐Γòò├à Spectrometer detected but no controller found")
                logger.info("Γëí╞Æ├┤├» Controller is required for calibration")
                logger.info("Γëí╞Æ├┤├» Please connect the controller to perform calibration")
            elif status.get("ctrl_type") and not status.get("spectrometer"):
                logger.warning("╬ô├£├íΓê⌐Γòò├à Controller detected but no spectrometer found")
                logger.info("Γëí╞Æ├┤├» Spectrometer is required for calibration")
                logger.info(
                    "Γëí╞Æ├┤├» Please connect the spectrometer to perform calibration"
                )
        else:
            logger.debug(
                "Hardware status update received (not initial connection) - skipping calibration check"
            )

    def _on_hardware_disconnected(self):
        """Hardware disconnected."""
        logger.error("ΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉ")
        logger.error("CRITICAL: HARDWARE DISCONNECTED")
        logger.error("ΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉ")

        # Check if acquisition was running
        acquisition_was_running = (
            self.data_mgr._acquiring if hasattr(self.data_mgr, "_acquiring") else False
        )

        # Stop acquisition if running
        if acquisition_was_running:
            logger.error("Stopping acquisition due to hardware disconnection...")
            try:
                self.data_mgr.stop_acquisition()
            except Exception as e:
                logger.error(f"Error stopping acquisition: {e}")

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

        # Show critical error dialog if acquisition was running
        if acquisition_was_running:
            ui_error(
                self.main_window,
                "Device Disconnected",
                "<b>Hardware has been disconnected during acquisition!</b><br><br>"
                "Acquisition has been stopped.<br><br>"
                "Please check:<br>"
                "ΓÇó USB cable connections<br>"
                "ΓÇó USB port stability<br>"
                "ΓÇó Device power<br><br>"
                "Click 'Scan' to reconnect devices.",
            )

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

        from PySide6.QtCore import QTimer

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
                                led_intensities
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
        ui_error(
            self,
            "Hardware Error",
            error,
        )

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
        logger.info("[THREAD-INIT] Starting processing thread...")
        self._processing_active = True
        self._processing_thread = threading.Thread(
            target=self._processing_worker,
            name="SpectrumProcessing",
            daemon=True,
        )
        self._processing_thread.start()
        logger.info(
            f"Thread started: alive={self._processing_thread.is_alive()}, name={self._processing_thread.name}"
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

        logger.info("[WORKER-THREAD] Processing worker entered; thread is running...")
        logger.info("Γëí╞Æ╞Æ├│ Processing worker started")

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
                    self._queue_stats["max_size"], current_size
                )

            except queue.Empty:
                # Timeout - check if we should continue
                continue
            except Exception as e:
                logger.error(f"[X] Processing worker error: {e}", exc_info=True)

        # Log final statistics
        logger.info(
            f"Γëí╞Æ├╢Γöñ Processing worker stopped - Stats: {self._queue_stats['processed']} processed, "
            f"{self._queue_stats['dropped']} dropped, max queue: {self._queue_stats['max_size']}"
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
            if not self._safe_queue_put(data):
                # Queue operation failed - log and drop to prevent blocking
                self._queue_stats["dropped"] += 1
                if self._queue_stats["dropped"] % 10 == 1:  # Log every 10th drop
                    logger.warning(
                        f"[WARN] Spectrum queue full - {self._queue_stats['dropped']} frames dropped"
                    )

        except Exception as e:
            logger.exception(f"Spectrum acquisition error: {e}")

    def _safe_queue_put(self, data: dict) -> bool:
        """Safely put data in processing queue with error handling.

        Args:
            data: Spectrum data dictionary to queue

        Returns:
            True if data was queued successfully, False otherwise

        """
        try:
            if self._spectrum_queue is None:
                logger.error("Spectrum queue is None, cannot queue data")
                return False

            self._spectrum_queue.put_nowait(data)
            return True

        except AttributeError as e:
            logger.error(f"Queue attribute error: {e}")
            return False
        except Exception:
            # Queue full or other error - this is expected under load
            return False

    def _process_spectrum_data(self, data: dict):
        """Process spectrum data in dedicated worker thread (Phase 3 optimization).

        All the actual processing happens here, not in acquisition callback.
        This includes: intensity monitoring, transmission updates, buffer updates, etc.
        """
        try:
            channel = data["channel"]  # 'a', 'b', 'c', 'd'
            wavelength = data["wavelength"]  # nm
            intensity = data.get("intensity", 0)  # Raw intensity
            timestamp = data["timestamp"]
            elapsed_time = data["elapsed_time"]
            is_preview = data.get(
                "is_preview", False
            )  # Interpolated preview vs real data

            # Apply EMA display filter (if enabled) before storing
            if self._display_filter_method in ["ema_light", "ema_smooth"]:
                if self._ema_state[channel] is None:
                    self._ema_state[channel] = wavelength
                else:
                    alpha = self._display_filter_alpha
                    wavelength = (
                        alpha * wavelength + (1 - alpha) * self._ema_state[channel]
                    )
                    self._ema_state[channel] = wavelength

            # Append to timeline data buffers (with optional EMA filtering applied)
            try:
                self.buffer_mgr.append_timeline_point(
                    channel, elapsed_time, wavelength, timestamp
                )
            except Exception as e:
                logger.exception(f"[X] Buffer append failed for channel {channel}: {e}")

            # Queue transmission spectrum update for sidebar (QC/diagnostic display)
            # ALWAYS UPDATE: Sidebar is a QC tool and should show all available data
            has_raw_data = data.get("raw_spectrum") is not None
            has_transmission = data.get("transmission_spectrum") is not None

            # QC POLICY: Always update sidebar if we have ANY data (raw or transmission)
            # Sidebar is a diagnostic tool and must show data regardless of processing issues
            if has_raw_data or has_transmission:
                try:
                    self._queue_transmission_update(channel, data)

                    # Update Sensor IQ display if available
                    if "sensor_iq" in data:
                        self._update_sensor_iq_display(channel, data["sensor_iq"])

                except Exception as e:
                    logger.exception(
                        f"[X] Transmission queue error for channel {channel}: {e}"
                    )

            # Cursor auto-follow (thread-safe via signal)
            # Emit signal to update cursor on main thread
            try:
                self.cursor_update_signal.emit(elapsed_time)
            except Exception as e:
                logger.warning(f"Cursor update signal emit failed: {e}")

        except Exception as e:
            # TOP-LEVEL CATCH: Prevent any exception from killing the processing thread
            logger.exception(f"[X] Spectrum processing error: {e}")

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
                logger.exception(f"[X] Graph update error for channel {channel}: {e}")

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
            logger.exception(f"[X] Recording error for channel {channel}: {e}")

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
                        f"╬ô├£├íΓê⌐Γòò├à Possible optical leak detected in channel {channel.upper()}: "
                        f"avg intensity {avg_intensity:.0f} < threshold {dark_threshold:.0f}"
                    )

    def _queue_transmission_update(self, channel: str, data: dict):
        """Queue transmission spectrum update for batch processing (Phase 2 optimization).

        Instead of updating plots immediately in acquisition thread, queue the data
        for batch processing in the UI timer. This prevents blocking.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            data: Spectrum data dictionary containing transmission_spectrum and raw_spectrum

        """
        # Skip if updates are disabled (performance optimization) - check coordinator flags
        if (
            not self.ui_updates._transmission_updates_enabled
            and not self.ui_updates._raw_spectrum_updates_enabled
        ):
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
                            f"[HARDWARE ERROR] No wavelength data for channel {channel}!"
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
                            f"Baseline correction failed for channel {channel}: {e}"
                        )

        # Queue for batch update if we have valid data
        if transmission is not None and len(transmission) > 0:
            # Unified wavelength source-of-truth: data_mgr.wave_data (set after calibration)
            wavelengths = self.data_mgr.wave_data
            if wavelengths is None:
                cd = getattr(self.data_mgr, "calibration_data", None)
                wavelengths = (
                    getattr(cd, "wavelengths", None) if cd is not None else None
                )

            if wavelengths is None:
                logger.error(
                    f"[WAVELENGTHS MISSING] channel={channel}: data_mgr.wave_data not set; calibration not loaded. Skipping update."
                )
                return

            # Queue for batch processing via AL_UIUpdateCoordinator
            self.ui_updates.queue_transmission_update(
                channel, wavelengths, transmission, raw_spectrum
            )

            # === PHASE 1.1 INTEGRATION: Create domain models for type safety ===
            # Create domain models (for future use)
            raw_spectrum_model = self._dict_to_raw_spectrum(channel, data)
            processed_spectrum_model = self._dict_to_processed_spectrum(
                channel, data, transmission
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
                        raw_wavelength, np.ndarray
                    ):
                        continue
                    if len(raw_time) == 0 or len(raw_wavelength) == 0:
                        continue
                    if len(raw_time) != len(raw_wavelength):
                        continue

                    # Display buffered data (already has EMA filtering applied if enabled)
                    display_wavelength = raw_wavelength

                    # DISABLED: Online smoothing (for peak tracking validation)
                    # if self._filter_enabled and len(raw_wavelength) > 2:
                    #     with measure('filtering.online_smoothing'):
                    #         display_wavelength = self._apply_online_smoothing(
                    #             raw_wavelength,
                    #             self._filter_strength,
                    #             channel
                    #         )
                    # else:
                    #     display_wavelength = raw_wavelength

                    # Simple downsampling DISABLED - show full-resolution data for troubleshooting
                    # MAX_PLOT_POINTS = 2000  # Sufficient for smooth rendering at 1 Hz
                    # if len(raw_time) > MAX_PLOT_POINTS:
                    #     step = len(raw_time) // MAX_PLOT_POINTS
                    #     display_time = raw_time[::step]
                    #     display_wavelength = display_wavelength[::step]
                    # else:
                    #     display_time = raw_time
                    display_time = raw_time
                    # Keep any filtering applied above; do not overwrite

                    # Update graph
                    with measure("graph_update.setData"):
                        curve.setData(display_time, display_wavelength)

                except Exception as e:
                    # Log display errors for debugging
                    logger.error(f"[PLOT-ERROR] Ch {channel.upper()}: {e}")
                    import traceback

                    logger.error(traceback.format_exc())

            # Clear processed updates
            self._pending_graph_updates = {"a": None, "b": None, "c": None, "d": None}

            # === UPDATE CYCLE OF INTEREST GRAPH ===
            # Update at throttled rate (1 Hz) instead of on every data point (40+ FPS)
            # This prevents crashes from heavy processing (filtering, baseline calc, etc.)
            # Always update cycle of interest graph when data is flowing
            if True:  # Always update (was: self.USE_TIMEFRAME_MODE or len(queued_channels) > 0)
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
                ) as e:
                    # Log cycle update errors for debugging
                    if (
                        self._sensorgram_update_counter <= 5
                        or self._sensorgram_update_counter % 20 == 0
                    ):
                        logger.error(f"[CYCLE-ERROR]: {type(e).__name__}: {e}")

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
        """Update the cycle of interest graph based on cursor positions or timeframe mode.

        Phase 3: Uses timeframe extraction when USE_TIMEFRAME_MODE is enabled.
        Also triggers autosave when cycle region changes significantly.
        """
        # Phase 3: Use timeframe extraction if enabled
        if self.USE_TIMEFRAME_MODE:
            self._update_cycle_graph_from_timeframe()
            return

        # Legacy cursor-based update
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

                if len(cycle_wavelength) == 0:
                    continue

                # Data already has EMA filtering applied (if enabled) from buffer storage
                # Calculate ╬ö SPR (baseline is first point in cycle or calibrated baseline)
                baseline = self.buffer_mgr.baseline_wavelengths[ch_letter]
                if baseline is None and len(cycle_wavelength) > 0:
                    # Use first VALID wavelength (620-680nm range for SPR)
                    for wl in cycle_wavelength:
                        if 620.0 <= wl <= 680.0:
                            baseline = wl
                            break
                    else:
                        # No valid wavelengths - use first point anyway
                        baseline = cycle_wavelength[0]
                elif baseline is None:
                    baseline = 0

                # Convert wavelength shift to RU (Response Units)
                delta_spr = (cycle_wavelength - baseline) * WAVELENGTH_TO_RU_CONVERSION

                # Store in buffer manager (with timestamps)
                self.buffer_mgr.update_cycle_data(
                    ch_letter, cycle_time, cycle_wavelength, delta_spr, cycle_timestamp
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

            # Update ╬ö SPR display with current values
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
        """Update the Γò¼├╢ SPR display label with values at Stop cursor position."""
        if self.main_window.cycle_of_interest_graph.delta_display is None:
            return

        import numpy as np

        # Get Stop cursor position from full timeline graph
        stop_time = self.main_window.full_timeline_graph.stop_cursor.value()

        # Get Γò¼├╢ SPR value at Stop cursor position for each channel
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

        # Update label with bold text for better visibility
        self.main_window.cycle_of_interest_graph.delta_display.setText(
            f"<b>╬ö SPR: Ch A: {delta_values['a']:.1f} RU  |  Ch B: {delta_values['b']:.1f} RU  |  "
            f"Ch C: {delta_values['c']:.1f} RU  |  Ch D: {delta_values['d']:.1f} RU</b>",
        )

    def _on_acquisition_error(self, error: str):
        """Data acquisition error."""
        logger.error(f"Acquisition error: {error}")

        # Check if error is due to device disconnect
        if "disconnected" in error.lower():
            logger.error("Γëí╞Æ├╢├« Spectrometer disconnected during acquisition")

            # Trigger hardware disconnect to clean up and reset UI
            self.hardware_mgr.disconnect()

            # Show user-friendly message
            ui_warn(
                self,
                "Device Disconnected",
                "Spectrometer was disconnected.\n\n"
                "Please check the USB connection and power on again.",
            )
            return

        # If error indicates hardware failure, stop acquisition and show warning
        if (
            "Hardware communication lost" in error
            or "stopping acquisition" in error.lower()
        ):
            logger.warning("╬ô├£├íΓê⌐Γòò├à Hardware error detected - stopping acquisition")

            # Update UI to show disconnected state
            self.main_window.set_power_state("error")

            # Show user-friendly message
            ui_error(
                self,
                "Hardware Error",
                "Hardware communication lost. Please power off and reconnect the device.",
            )

    def _on_polarizer_toggle_clicked(self):
        """Handle polarizer toggle button click - switch servo between S and P positions."""
        try:
            logger.info("Γëí╞Æ├╢├┐ Polarizer toggle button clicked")

            # Get current position from UI
            current_position = self.main_window.sidebar.current_polarizer_position
            logger.info(f"   Current position: {current_position}")

            # Toggle to opposite position
            new_position = "P" if current_position == "S" else "S"

            # Send command to hardware using servo_move_1_then worker function
            if self.hardware_mgr.ctrl is not None:
                logger.info(
                    f"Γëí╞Æ├╢├ñ Toggling polarizer: {current_position} ╬ô├Ñ├å {new_position}"
                )

                # Import servo worker function
                from affilabs.utils.startup_calibration import (
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
                                self.hardware_mgr.usb
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
                            new_position.lower()
                        )

                        if mode_success:
                            # Update UI to reflect new position
                            self.main_window.sidebar.set_polarizer_position(
                                new_position
                            )
                            logger.info(
                                f"[OK] Polarizer moved to position {new_position}"
                            )
                        else:
                            logger.warning(
                                f"╬ô├£├íΓê⌐Γòò├à Servo moved but mode lock failed for {new_position}"
                            )
                            # Still update UI since servo physically moved
                            self.main_window.sidebar.set_polarizer_position(
                                new_position
                            )
                    else:
                        logger.error(
                            f"[X] Failed to move polarizer to position {new_position}"
                        )
                        from widgets.message import show_message

                        show_message(
                            f"Failed to move polarizer to position {new_position}\n\nCheck hardware connection."
                        )
                else:
                    logger.error("[X] No device_config available for servo positions")
                    from widgets.message import show_message

                    show_message(
                        "Cannot move polarizer - device configuration not loaded."
                    )

            else:
                logger.warning(
                    "╬ô├£├íΓê⌐Γòò├à Controller not connected - cannot move polarizer"
                )
                from widgets.message import show_message

                show_message(
                    "Controller not connected.\n\nPlease connect hardware first."
                )

        except Exception as e:
            logger.error(f"[X] Error toggling polarizer: {e}")
            import traceback

            traceback.print_exc()
            from widgets.message import show_message

            show_message(f"Error toggling polarizer: {e!s}")

        except Exception as e:
            logger.error(f"[X] Error toggling polarizer: {e}")
            from widgets.message import show_message

            show_message(f"Error toggling polarizer: {e!s}")

    # === Recording Callbacks ===

    def _on_recording_started(self, filename: str):
        """Recording started."""
        logger.info(f"Γëí╞Æ├┤┬Ñ Recording started: {filename}")

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
        logger.info("Γëí╞Æ├┤┬Ñ Recording stopped")

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
            logger.info("╬ô├àΓòò Pausing live acquisition...")
            self.data_mgr.pause_acquisition()
        else:
            logger.info("╬ô├╗ΓòóΓê⌐Γòò├à Resuming live acquisition...")
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
        logger.debug("Γëí╞Æ├╢├ñ Reset experiment_start_time for new acquisition")

        # Clear data buffers for fresh start
        self.buffer_mgr.clear_all()
        logger.debug("Γëí╞Æ├╢├ñ Cleared all data buffers")

        # Clear any pause/resume markers from previous runs (with thread safety)
        try:
            if hasattr(self.main_window, "pause_markers") and hasattr(
                self.main_window, "full_timeline_graph"
            ):
                # Schedule marker removal in main thread (Qt objects must be accessed from main thread)
                from PySide6.QtCore import QTimer

                def clear_markers():
                    try:
                        for marker in self.main_window.pause_markers:
                            if "line" in marker:
                                try:
                                    self.main_window.full_timeline_graph.removeItem(
                                        marker["line"]
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
        logger.info("╬ô├àΓòú Live acquisition stopped - disabling record/pause buttons")
        self.main_window.record_btn.setEnabled(False)
        self.main_window.pause_btn.setEnabled(False)
        self.main_window.record_btn.setToolTip(
            "Start Recording\n(Enabled after calibration)"
        )
        self.main_window.pause_btn.setToolTip(
            "Pause Live Acquisition\n(Enabled after calibration)"
        )

        # Uncheck buttons if they were active
        if self.main_window.record_btn.isChecked():
            self.main_window.record_btn.setChecked(False)
        if self.main_window.pause_btn.isChecked():
            self.main_window.pause_btn.setChecked(False)

        # Update spectroscopy status to "Stopped"
        if hasattr(self.main_window, "sidebar") and hasattr(
            self.main_window.sidebar, "subunit_status"
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
            logger.info("Γëí╞Æ├┤┬Ñ Stopping recording due to acquisition stop...")
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
            f"Pump {channel}: {'running' if running else 'stopped'} @ {flow_rate} Γò¼Γò¥L/min"
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
                    logger.info("\nΓëí╞Æ├┤├¿ FINAL PROFILING STATISTICS:")
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
                # Avoid arbitrary sleeps; threads joined above.
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
        logger.info("Γëí╞Æ├╢├ñ Closing application...")

        # Perform graceful cleanup
        self._cleanup_resources(emergency=False)

        return super().close()

    def _emergency_cleanup(self):
        """Emergency cleanup for unexpected exits (called by atexit)."""
        if hasattr(self, "closing") and self.closing:
            return  # Normal close already happened

        logger.warning("╬ô├£├íΓê⌐Γòò├à Emergency cleanup triggered - forcing resource release")

        # Force close all hardware connections without waiting
        self._cleanup_resources(emergency=True)

    def __del__(self):
        """Destructor to ensure resources are cleaned up."""
        try:
            if not hasattr(self, "closing") or not self.closing:
                logger.warning(
                    "╬ô├£├íΓê⌐Γòò├à __del__ called without proper close - forcing cleanup"
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
        self, require_controller=True, require_spectrometer=True, require_servo=False
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
                "╬ô├£├íΓê⌐Γòò├à  HAL not available, cannot connect via DeviceManager"
            )
            return False

        try:
            logger.info("Γëí╞Æ├╢├« Connecting devices via HAL DeviceManager...")
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
                logger.error("[X] HAL device connection failed")

            return success
        except Exception as e:
            logger.error(f"[X] HAL connection error: {e}", exc_info=True)
            return False

    def disconnect_hal_devices(self):
        """Disconnect all devices via HAL DeviceManager."""
        if not HAL_AVAILABLE or not self.device_manager:
            return

        try:
            logger.info("Γëí╞Æ├╢├« Disconnecting HAL devices...")
            # Stop auto-reconnect
            self.device_status_vm.stop_auto_reconnect()
            # Disconnect all
            self.device_manager.disconnect_all()
            logger.info("[OK] HAL devices disconnected")
        except Exception as e:
            logger.error(f"[X] HAL disconnect error: {e}", exc_info=True)

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
                    self.hardware_mgr.ctrl
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
                    self.hardware_mgr.usb
                )
                self.device_manager.register_spectrometer(spec_adapter)
                logger.info("[OK] Legacy spectrometer registered with HAL")

            # Note: Servo is managed separately, could add servo adapter here

        except Exception as e:
            logger.warning(f"╬ô├£├íΓê⌐Γòò├à  Could not register legacy devices with HAL: {e}")

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
                f"Setting {self._selected_axis.upper()}-axis range: [{min_val}, {max_val}]"
            )

            # Apply range to selected axis
            if self._selected_axis == "x":
                self.main_window.cycle_of_interest_graph.setXRange(
                    min_val, max_val, padding=0
                )
            else:
                self.main_window.cycle_of_interest_graph.setYRange(
                    min_val, max_val, padding=0
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
            "[OK] Filter toggle complete - both timeline and cycle graphs refreshed"
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
        # Lower strength (1) = heavy filtering: high R, low Q ╬ô├Ñ├å trust model, smooth heavily
        # Higher strength (10) = light filtering: low R, high Q ╬ô├Ñ├å trust data, track closely
        #
        # R (measurement_noise): Variance of sensor noise
        # Q (process_noise): Variance of system dynamics
        # Kalman gain K = P / (P + R), so higher R ╬ô├Ñ├å lower K ╬ô├Ñ├å less weight on measurements
        #
        # Strength 1: R=0.10, Q=0.001 (heavy smoothing for noisy historical data)
        # Strength 5: R=0.02, Q=0.005 (balanced)
        # Strength 10: R=0.005, Q=0.01 (light smoothing for clean live data)
        measurement_noise = (
            0.1 / self._filter_strength
        )  # Lower strength ╬ô├Ñ├å higher R ╬ô├Ñ├å more filtering
        process_noise = (
            0.001 * self._filter_strength
        )  # Lower strength ╬ô├Ñ├å lower Q ╬ô├Ñ├å steadier model

        self._kalman_filters = {}
        for ch in self._idx_to_channel:
            self._kalman_filters[ch] = KalmanFilter(
                process_noise=process_noise,
                measurement_noise=measurement_noise,
            )

        logger.info(
            f"Kalman filters initialized (R={measurement_noise:.4f}, Q={process_noise:.4f})"
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
                recent_data, strength, channel, method, online_mode=False
            )
            result[filter_start:] = filtered_recent
            return result

        # Use instance method if not overridden
        filter_method = method if method is not None else self._filter_method

        if filter_method == "kalman":
            # Kalman filter - optimal for smooth trajectories
            if channel is None:
                logger.warning(
                    "Kalman filter requires channel ID, falling back to median"
                )
                filter_method = "median"
            elif channel not in self._kalman_filters:
                logger.warning(
                    f"No Kalman filter for channel {channel}, initializing..."
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
            # No reference selected - this is normal, user hasn't selected one yet
            return

        import numpy as np

        ref_time = self.buffer_mgr.cycle_data[self._reference_channel].time
        ref_spr = self.buffer_mgr.cycle_data[self._reference_channel].spr

        if len(ref_time) == 0:
            print(f"[REF-DEBUG] Reference channel {self._reference_channel} has no data")
            return

        print(f"[REF-DEBUG] Applying reference subtraction using channel {self._reference_channel}")
        print(f"[REF-DEBUG] Reference SPR range: [{ref_spr.min():.2f}, {ref_spr.max():.2f}] RU")

        # Subtract reference from all other channels
        for ch in self._idx_to_channel:
            if ch == self._reference_channel:
                continue  # Don't subtract reference from itself

            ch_time = self.buffer_mgr.cycle_data[ch].time
            ch_spr = self.buffer_mgr.cycle_data[ch].spr

            if len(ch_time) == 0:
                continue

            print(f"[REF-DEBUG] Ch {ch}: Before subtraction, SPR range=[{ch_spr.min():.2f}, {ch_spr.max():.2f}] RU")

            # Interpolate reference to match channel time points
            if len(ref_time) > 1:
                ref_interp = np.interp(ch_time, ref_time, ref_spr)
                # Update the cycle data with subtracted values
                subtracted_spr = ch_spr - ref_interp
                self.buffer_mgr.cycle_data[ch].spr = subtracted_spr
                print(f"[REF-DEBUG] Ch {ch}: After subtraction, SPR range=[{subtracted_spr.min():.2f}, {subtracted_spr.max():.2f}] RU")

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
                pos
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
                    "No channel selected. Left-click a channel first to select it."
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
        curve = self.main_window.full_timeline_graph.curves[channel]
        color = curve.opts["pen"].color()

        # Create flag marker for Navigation graph (prominent)
        flag_line = pg.InfiniteLine(
            pos=time,
            angle=90,
            pen=pg.mkPen(color=color, width=2, style=pg.QtCore.Qt.PenStyle.DashLine),
            movable=False,
        )

        # Add flag symbol at top
        flag_symbol = pg.ScatterPlotItem(
            [time],
            [self.main_window.full_timeline_graph.getPlotItem().viewRange()[1][1]],
            symbol="t",  # Triangle down (flag shape)
            size=15,
            brush=pg.mkBrush(color),
            pen=pg.mkPen(color=color, width=2),
        )

        # Add to Navigation graph (full_timeline_graph)
        self.main_window.full_timeline_graph.addItem(flag_line)
        self.main_window.full_timeline_graph.addItem(flag_symbol)

        # Store references on Navigation graph
        if not hasattr(self.main_window.full_timeline_graph, "flag_markers"):
            self.main_window.full_timeline_graph.flag_markers = []

        self.main_window.full_timeline_graph.flag_markers.append(
            {
                "line": flag_line,
                "symbol": flag_symbol,
                "data": flag_entry,
            }
        )

        # Update cycle data table
        self._update_cycle_data_table()

        logger.info(
            f"Added flag for Channel {chr(65 + channel)} at {time:.2f}s: '{annotation}'"
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
            ]
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
                f"Toggling polarizer from {current_pos.upper()} to {new_pos.upper()}"
            )

            # Γëí╞Æ├╢├å CRITICAL VALIDATION: Check positions match device_config
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
                            f"[OK] Position validation: {new_pos.upper()}-mode target={target_pos}Γö¼Γûæ (from device_config)"
                        )
                    else:
                        logger.warning(
                            "╬ô├£├íΓê⌐Γòò├à  Cannot validate positions - not found in device_config"
                        )
                else:
                    logger.warning(
                        "╬ô├£├íΓê⌐Γòò├à  Cannot validate positions - device_config not available"
                    )
            except Exception as e:
                logger.error(f"[X] Position validation failed: {e}")

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
                    f"Applying settings: S={s_pos}, P={p_pos}, LEDs=[{led_a},{led_b},{led_c},{led_d}]"
                )

                # ╬ô├£├íΓê⌐Γòò├à  Polarizer positions are IMMUTABLE - set at controller initialization
                # DO NOT apply servo_set() - positions come from device_config at startup
                logger.info(
                    f"   Γëí╞Æ├╢├å Polarizer positions locked (from device_config at init): S={s_pos}Γö¼Γûæ, P={p_pos}Γö¼Γûæ"
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
                        f"Applied LED delays: PRE={pre_led_delay}ms, POST={post_led_delay}ms"
                    )

                # Save servo positions, LED intensities, and LED timing delays to device config file
                # The device config file is provided by OEM with factory positions
                if self.main_window.device_config:
                    logger.info("Γëí╞Æ├åΓò¢ Saving settings to device config file...")
                    self.main_window.device_config.set_servo_positions(s_pos, p_pos)
                    self.main_window.device_config.set_led_intensities(
                        led_a, led_b, led_c, led_d
                    )
                    self.main_window.device_config.set_pre_post_led_delays(
                        pre_led_delay, post_led_delay
                    )
                    self.main_window.device_config.save()
                    logger.info(
                        "[OK] Settings saved to device config file (including LED timing delays)"
                    )
                else:
                    logger.warning(
                        "╬ô├£├íΓê⌐Γòò├à Device config not available - settings not saved"
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
                "left", "Γò¼├╢ SPR (RU)", color="#86868B", size="11pt"
            )
        else:
            self.main_window.cycle_of_interest_graph.setLabel(
                "left", "Γò¼Γòù (nm)", color="#86868B", size="11pt"
            )

        # TODO: Trigger data conversion and redraw
        # The conversion factor is approximately: 1 RU ╬ô├½├¬ 0.1 nm
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

    def _on_polarizer_calibration(self):
        """Servo calibration is now integrated into OEM calibration workflow."""
        logger.info("Polarizer calibration integrated into OEM Calibration workflow")
        ui_info(
            self,
            "Use OEM Calibration",
            "Servo polarizer calibration is now integrated into the\n"
            "OEM Calibration workflow.\n\n"
            "Please use: Calibration ΓåÆ OEM Calibration\n\n"
            "This runs the complete workflow including servo optimization.",
        )

    def _on_oem_led_calibration(self):
        """Run full OEM calibration (servo + LED) via CalibrationService."""
        logger.info("Starting Full LED Calibration via CalibrationService...")
        self.calibration.start_calibration()

    def _on_record_baseline_clicked(self):
        """Handle Record Baseline Data button click."""
        logger.info("=" * 80)
        logger.info("[User Action] Record Baseline Data button clicked")
        logger.info("=" * 80)

        # Debug: Check data manager state
        logger.info(f"Data manager exists: {self.data_mgr is not None}")
        if self.data_mgr:
            logger.info(f"Data manager calibrated: {self.data_mgr.calibrated}")
            logger.info(f"Data manager acquiring: {self.data_mgr._acquiring}")

        # Check if already recording
        if (
            self._baseline_recorder is not None
            and self._baseline_recorder.is_recording()
        ):
            logger.info("Stopping baseline recording...")
            self._baseline_recorder.stop_recording()
            return

        # Create recorder if not exists
        if self._baseline_recorder is None:
            if not self.data_mgr:
                ui_warn(
                    self.main_window,
                    "Not Ready",
                    "Data acquisition system not initialized.",
                )
                return

            self._baseline_recorder = BaselineDataRecorder(
                self.data_mgr, parent=self.main_window
            )

            # Connect signals
            self._baseline_recorder.recording_started.connect(
                self._on_recording_started
            )
            self._baseline_recorder.recording_progress.connect(
                self._on_recording_progress
            )
            self._baseline_recorder.recording_complete.connect(
                self._on_recording_complete
            )
            self._baseline_recorder.recording_error.connect(self._on_recording_error)
            logger.info("[OK] Baseline recorder initialized and signals connected")

        # Confirm with user
        reply_yes = ui_question(
            self.main_window,
            "Record Baseline Data",
            "This will record 5 minutes of transmission data for noise optimization analysis.\n\n"
            "[WARN] Ensure stable baseline (no sample injections) during recording.\n\n"
            "Continue?",
        )
        if reply_yes:
            logger.info("User confirmed - starting 5-minute baseline recording")
            self._baseline_recorder.start_recording(duration_minutes=5.0)

    def _on_recording_started(self):
        """Handle baseline recording started signal."""
        if hasattr(self.main_window, "baseline_capture_btn"):
            self.main_window.baseline_capture_btn.setText("ΓÅ╣ Stop Recording")
            self.main_window.baseline_capture_btn.setStyleSheet(
                "QPushButton {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF9500, stop:1 #E08000);"
                "  color: white;"
                "  border: none;"
                "  border-radius: 8px;"
                "  padding: 8px 16px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFA520, stop:1 #F09000);"
                "}"
                "QPushButton:pressed {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E08000, stop:1 #C07000);"
                "}",
            )
        logger.info(
            "≡ƒôè Baseline recording started - button updated to 'Stop Recording'"
        )

    def _on_recording_progress(self, progress: dict):
        """Handle baseline recording progress update.

        Args:
            progress: Dict with 'elapsed', 'remaining', 'count', 'percent' keys

        """
        if hasattr(self.main_window, "baseline_capture_btn"):
            percent = progress.get("percent", 0)
            remaining = progress.get("remaining", 0)
            self.main_window.baseline_capture_btn.setText(
                f"ΓÅ╣ Recording... {int(percent)}% ({int(remaining)}s)",
            )

    def _on_recording_complete(self, filepath: str):
        """Handle baseline recording complete signal.

        Args:
            filepath: Path to saved recording file

        """
        # Reset button appearance
        if hasattr(self.main_window, "baseline_capture_btn"):
            self.main_window.baseline_capture_btn.setText("≡ƒôè Capture 5-Min Baseline")
            self.main_window.baseline_capture_btn.setStyleSheet(
                "QPushButton {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF3B30, stop:1 #E02020);"
                "  color: white;"
                "  border: none;"
                "  border-radius: 8px;"
                "  padding: 8px 16px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF4D42, stop:1 #F03030);"
                "}"
                "QPushButton:pressed {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E02020, stop:1 #C01818);"
                "}"
                "QPushButton:disabled {"
                "  background: #D1D1D6;"
                "  color: #86868B;"
                "}",
            )

        # Show completion message
        ui_info(
            self.main_window,
            "Recording Complete",
            f"[OK] Baseline data successfully recorded!\n\n"
            f"Saved to: {filepath}\n\n"
            f"You can now send this data for offline noise optimization analysis.",
        )
        logger.info(f"[OK] Baseline recording complete - user notified: {filepath}")

    def _on_recording_error(self, error_msg: str):
        """Handle baseline recording error signal.

        Args:
            error_msg: Error description

        """
        # Reset button appearance
        if hasattr(self.main_window, "baseline_capture_btn"):
            self.main_window.baseline_capture_btn.setText("≡ƒôè Capture 5-Min Baseline")
            self.main_window.baseline_capture_btn.setStyleSheet(
                "QPushButton {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF3B30, stop:1 #E02020);"
                "  color: white;"
                "  border: none;"
                "  border-radius: 8px;"
                "  padding: 8px 16px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF4D42, stop:1 #F03030);"
                "}"
                "QPushButton:pressed {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E02020, stop:1 #C01818);"
                "}"
                "QPushButton:disabled {"
                "  background: #D1D1D6;"
                "  color: #86868B;"
                "}",
            )

        # Show error message
        ui_error(
            self.main_window,
            "Recording Error",
            f"[ERROR] Baseline recording failed:\n\n{error_msg}",
        )
        logger.error(f"[ERROR] Baseline recording error shown to user: {error_msg}")

    def _on_power_on_requested(self):
        """User requested to power on (connect hardware)."""
        try:
            logger.info("Power ON requested - starting hardware connection...")

            # Set to searching state
            logger.info("Setting power button to 'searching' state...")
            self.main_window.set_power_state("searching")
            logger.info("Power button state updated")

            # Start hardware scan and connection
            logger.info("Calling hardware_mgr.scan_and_connect()...")
            print("[APPLICATION] Calling hardware_mgr.scan_and_connect()...")
            self.hardware_mgr.scan_and_connect()
            logger.info(
                "scan_and_connect() call completed (scanning in background thread)"
            )
        except Exception as e:
            logger.exception(f"ERROR in _on_power_on_requested: {e}")
            from widgets.message import show_message

            show_message(
                f"Failed to start hardware scan: {e}", "Error", parent=self.main_window
            )
            # Reset power button to disconnected state
            try:
                self.main_window.set_power_state("disconnected")
            except:
                pass

    def _on_power_off_requested(self):
        """User requested to power off (disconnect hardware)."""
        logger.info("Γëí╞Æ├╢├« Power OFF requested - initiating graceful shutdown...")

        try:
            # Stop data acquisition first (prevents new data from coming in)
            if self.data_mgr:
                logger.info("╬ô├àΓòòΓê⌐Γòò├à  Stopping data acquisition...")
                try:
                    self.data_mgr.stop_acquisition()
                    logger.info("[OK] Data acquisition stopped")
                except Exception as e:
                    logger.error(f"Error stopping data acquisition: {e}")

            # Stop recording if active (ensures data is saved)
            if self.recording_mgr and self.recording_mgr.is_recording:
                logger.info("Γëí╞Æ├åΓò¢ Stopping active recording...")
                try:
                    self.recording_mgr.stop_recording()
                    logger.info("[OK] Recording stopped and saved")
                except Exception as e:
                    logger.error(f"Error stopping recording: {e}")

            # Disconnect all hardware (safe shutdown of devices)
            logger.info("Γëí╞Æ├╢├« Disconnecting hardware...")
            try:
                self.hardware_mgr.disconnect_all()
                logger.info("[OK] Hardware disconnected safely")
            except Exception as e:
                logger.error(f"Error disconnecting hardware: {e}")

            # Update UI to disconnected state
            self.main_window.set_power_state("disconnected")

            logger.info(
                "[OK] Graceful shutdown complete - software ready for offline post-processing"
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
            "Γëí╞Æ├┤┬Ñ [RECORD-HANDLER] Recording start requested by user (button clicked)"
        )

        # Show file dialog to select recording location
        # Get default filename with timestamp

        from PySide6.QtWidgets import QFileDialog

        from affilabs.utils.time_utils import for_filename

        timestamp = for_filename().replace(".", "_")
        default_filename = f"AffiLabs_data_{timestamp}.csv"

        logger.info(
            f"[RECORD-HANDLER] Showing save dialog with default: {default_filename}"
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
                "[RECORD-HANDLER] Starting recording via recording_mgr.start_recording()"
            )
            self.recording_mgr.start_recording(file_path)

            # Populate export fields with recording information
            path_obj = Path(file_path)
            filename = path_obj.stem  # Name without extension
            directory = str(path_obj.parent)

            self.main_window.sidebar.export_filename_input.setText(filename)
            self.main_window.sidebar.export_dest_input.setText(directory)
            logger.info(
                f"╬ô┬ú├┤ [RECORD-HANDLER] Export fields populated: {filename} in {directory}"
            )
        else:
            # User cancelled - revert button state
            logger.info(
                "[RECORD-HANDLER] User cancelled file dialog - reverting button state"
            )
            self.main_window.record_btn.setChecked(False)

    def _on_recording_stop_requested(self):
        """User requested to stop recording."""
        logger.info("Γëí╞Æ├┤┬Ñ Recording stop requested...")

        # Stop the recording
        self.recording_mgr.stop_recording()

    def _on_clear_graphs_requested(self):
        """Handle clear graphs button click - clear all buffer data and reset timeline."""
        logger.info("[UI] Clear graphs requested")
        try:
            # Clear all data buffers
            if hasattr(self, "buffer_mgr") and self.buffer_mgr:
                self.buffer_mgr.clear_all()
                logger.info("[OK] Buffer data cleared successfully")
            else:
                logger.warning("[WARN] Buffer manager not available")

            # Reset experiment start time so timeline starts at zero
            self.experiment_start_time = None
            logger.info("≡ƒöä Timeline reset - next data point will start at t=0")

        except Exception as e:
            logger.error(f"[ERROR] Error clearing buffer data: {e}", exc_info=True)

    def _on_clear_flags_requested(self):
        """Handle clear flags button click - clear all flag data."""
        logger.info("[UI] Clear flags requested")
        try:
            if hasattr(self, "_flag_data"):
                self._flag_data.clear()
                logger.info("[OK] Flag data cleared successfully")
            else:
                logger.warning("[WARN] Flag data not available")
        except Exception as e:
            logger.error(f"[ERROR] Error clearing flag data: {e}", exc_info=True)

    def _on_pipeline_changed(self, pipeline_id: str):
        """Handle peak finding pipeline selection change.

        Args:
            pipeline_id: Pipeline identifier ('fourier', 'hybrid', 'hybrid_original')

        """
        logger.info(f"[UI] Pipeline changed to: {pipeline_id}")
        try:
            # Update data acquisition manager to use new pipeline
            if hasattr(self, "data_mgr") and self.data_mgr:
                self.data_mgr.set_peak_finding_pipeline(pipeline_id)
                logger.info("[OK] Peak finding pipeline updated successfully")
            else:
                logger.warning("[WARN] Data manager not available")
        except Exception as e:
            logger.error(f"[ERROR] Error changing pipeline: {e}", exc_info=True)

    # ==================== Timeframe Mode Handlers (Phase 2) ====================

    def _on_timeframe_mode_changed(self, mode: str):
        """Handle timeframe mode change (moving vs fixed window).

        Args:
            mode: 'moving' or 'fixed'

        """
        self._live_cycle_mode = mode
        logger.info(f"[TIMEFRAME] Mode changed to: {mode}")

        # Reset baselines when changing modes
        if mode == "moving":
            # Clear baselines so they get re-established with first new data
            self._timeframe_baseline_wavelengths = {
                "a": None,
                "b": None,
                "c": None,
                "d": None,
            }
            # Reset last processed time tracker
            self._last_processed_time = {
                "a": -1.0,
                "b": -1.0,
                "c": -1.0,
                "d": -1.0,
            }
            # Clear accumulated cycle data
            for ch in ["a", "b", "c", "d"]:
                self.buffer_mgr.cycle_data[ch].time = np.array([])
                self.buffer_mgr.cycle_data[ch].wavelength = np.array([])
                self.buffer_mgr.cycle_data[ch].spr = np.array([])
            logger.info(
                f"[TIMEFRAME] Moving window enabled - showing last {self._live_cycle_timeframe} minutes"
            )
            logger.info("[TIMEFRAME] Cleared cycle data and baselines for fresh start")
        else:
            logger.info("[TIMEFRAME] Fixed window enabled - showing cursor range")

    def _on_timeframe_duration_changed(self, minutes: int):
        """Handle timeframe duration change.

        Args:
            minutes: Duration in minutes (1-60)

        """
        self._live_cycle_timeframe = minutes
        logger.info(f"[TIMEFRAME] Duration changed to: {minutes} minutes")

        # Trigger immediate update of Cycle of Interest graph
        if self._live_cycle_mode == "moving":
            self._update_cycle_graph_from_timeframe()

    def _extract_cycle_timeframe(self):
        """Extract cycle data based on timeframe mode settings.

        Returns:
            dict: Extracted data for each channel with keys:
                - time: List of timestamps
                - wavelength: List of resonance wavelengths
                - ru: List of RU values

        """
        logger.info(
            f"[EXTRACT] Called - mode={self._live_cycle_mode}, USE_TIMEFRAME_MODE={self.USE_TIMEFRAME_MODE}"
        )

        if not self.USE_TIMEFRAME_MODE:
            # Fall back to cursor-based extraction
            return self._extract_cycle_from_cursors()

        if self._live_cycle_mode == "moving":
            # Moving window: Extract last N minutes
            result = self._extract_moving_window()
            result_counts = {
                ch: len(result.get(ch, {}).get("time", []))
                for ch in ["a", "b", "c", "d"]
            }
            logger.info(f"[EXTRACT] Moving window returned: {result_counts}")
            return result
        # Fixed window: Use cursor positions
        result = self._extract_cycle_from_cursors()
        result_counts = {
            ch: len(result.get(ch, {}).get("time", [])) for ch in ["a", "b", "c", "d"]
        }
        logger.info(f"[EXTRACT] Cursor mode returned: {result_counts}")
        return result

    def _extract_moving_window(self):
        """Extract data for moving window mode (last N minutes).

        Returns:
            dict: Channel data for the moving window timeframe

        """
        import numpy as np

        # Calculate time window
        # Get current time from the latest data point in any channel
        current_time = 0
        for ch in ["a", "b", "c", "d"]:
            if ch in self.buffer_mgr.timeline_data:
                time_data = self.buffer_mgr.timeline_data[ch].time
                if len(time_data) > 0:
                    ch_time = time_data[-1]  # Last time point
                    current_time = max(current_time, ch_time)

        window_seconds = self._live_cycle_timeframe * 60  # Convert to seconds
        start_time = max(0, current_time - window_seconds)

        # Debug logging removed to reduce log spam

        # Extract data for each channel
        extracted = {"a": {}, "b": {}, "c": {}, "d": {}}

        for ch in ["a", "b", "c", "d"]:
            if ch not in self.buffer_mgr.timeline_data:
                extracted[ch] = {"time": [], "wavelength": [], "spr": []}
                continue

            # Get all timeline data for channel
            time_data = self.buffer_mgr.timeline_data[ch].time
            wavelength_data = self.buffer_mgr.timeline_data[ch].wavelength

            if len(time_data) == 0:
                extracted[ch] = {"time": [], "wavelength": [], "spr": []}
                continue

            # Extract only the LAST N minutes (moving window optimization)
            # This prevents copying ALL data every 250ms, which kills performance on long recordings
            try:
                import numpy as np

                # Convert to numpy arrays for fast slicing
                time_array = np.array(time_data)
                wavelength_array = np.array(wavelength_data)

                # Get current time (most recent data point)
                current_time = time_array[-1]

                # Calculate window start time (e.g., current - 5 minutes)
                window_duration_seconds = self._live_cycle_timeframe * 60.0
                window_start_time = current_time - window_duration_seconds

                # Find index where time >= window_start_time (binary search for speed)
                start_idx = np.searchsorted(time_array, window_start_time, side="left")

                # Extract only the window (not ALL 40 minutes!)
                extracted[ch] = {
                    "time": list(time_array[start_idx:]),
                    "wavelength": list(wavelength_array[start_idx:]),
                    "spr": [],  # Will be calculated later from wavelength
                }

                # Debug logging removed to reduce log spam - working as expected
            except Exception as e:
                logger.warning(f"[MOVING-WINDOW] Error extracting ch {ch}: {e}")
                extracted[ch] = {"time": [], "wavelength": [], "spr": []}

        return extracted

    def _extract_cycle_from_cursors(self):
        """Extract data between cursor positions (legacy/fixed window mode).

        Returns:
            dict: Channel data between cursors

        """
        import numpy as np

        # Get cursor positions
        if not hasattr(self.main_window, "full_timeline_graph"):
            return {"a": {}, "b": {}, "c": {}, "d": {}}

        start_time = self.main_window.full_timeline_graph.start_cursor.value()
        stop_time = self.main_window.full_timeline_graph.stop_cursor.value()

        logger.debug(
            f"[CURSOR-EXTRACT] Extracting from {start_time:.1f}s to {stop_time:.1f}s"
        )

        # Extract data for each channel
        extracted = {"a": {}, "b": {}, "c": {}, "d": {}}

        for ch in ["a", "b", "c", "d"]:
            if ch not in self.buffer_mgr.timeline_data:
                extracted[ch] = {"time": [], "wavelength": [], "spr": []}
                continue

            # Get all timeline data for channel (convert to numpy arrays immediately to prevent race conditions)
            time_data = self.buffer_mgr.timeline_data[ch].time
            wavelength_data = self.buffer_mgr.timeline_data[ch].wavelength
            spr_data = self.buffer_mgr.timeline_data[ch].spr

            if len(time_data) == 0:
                extracted[ch] = {"time": [], "wavelength": [], "spr": []}
                continue

            # Convert to numpy arrays atomically
            try:
                time_array = np.array(time_data)
                wavelength_array = np.array(wavelength_data)
                spr_array = np.array(spr_data)

                # Ensure all arrays have the same length (handle race conditions)
                min_len = min(len(time_array), len(wavelength_array), len(spr_array))
                if min_len == 0:
                    extracted[ch] = {"time": [], "wavelength": [], "spr": []}
                    continue

                time_array = time_array[:min_len]
                wavelength_array = wavelength_array[:min_len]
                spr_array = spr_array[:min_len]

                # Double-check arrays are not empty after truncation
                if len(time_array) == 0:
                    extracted[ch] = {"time": [], "wavelength": [], "spr": []}
                    continue

                # Filter to cursor range
                mask = (time_array >= start_time) & (time_array <= stop_time)

                # Ensure mask has correct size
                if len(mask) != len(time_array):
                    logger.warning(
                        f"[CURSOR-EXTRACT] Ch {ch}: mask size mismatch ({len(mask)} vs {len(time_array)})"
                    )
                    extracted[ch] = {"time": [], "wavelength": [], "spr": []}
                    continue

                extracted[ch] = {
                    "time": list(time_array[mask]),
                    "wavelength": list(wavelength_array[mask]),
                    "spr": list(spr_array[mask]),
                }

                if len(extracted[ch]["time"]) > 0:
                    logger.debug(
                        f"[CURSOR-EXTRACT] Ch {ch}: {len(extracted[ch]['time'])} points"
                    )
            except Exception as e:
                logger.warning(f"[CURSOR-EXTRACT] Error extracting ch {ch}: {e}")
                extracted[ch] = {"time": [], "wavelength": [], "spr": []}

        return extracted

    def _update_cycle_graph_from_timeframe(self):
        """Update the Cycle of Interest graph based on timeframe extraction.

        Phase 3: Full implementation with RU calculation and baseline correction.
        Throttled to update maximum once every 250ms to prevent excessive plotting.
        """
        import time

        if not self.USE_TIMEFRAME_MODE:
            logger.debug("[TIMEFRAME] Skipped - USE_TIMEFRAME_MODE is False")
            return

        # Throttle updates to prevent excessive extraction/plotting
        current_time = time.time()
        if current_time - self._last_timeframe_update < 0.25:  # 250ms throttle
            return
        self._last_timeframe_update = current_time

        # Guard: Don't update if no data exists yet
        if not hasattr(self, "buffer_mgr") or not self.buffer_mgr:
            logger.debug("[TIMEFRAME] Skipped - no buffer_mgr")
            return

        # Check if any channel has data
        has_data = False
        data_counts = {}
        for ch in ["a", "b", "c", "d"]:
            if ch in self.buffer_mgr.timeline_data:
                count = len(self.buffer_mgr.timeline_data[ch].time)
                data_counts[ch] = count
                if count > 0:
                    has_data = True

        if not has_data:
            # Only log once when we first notice no data (avoid spam)
            if (
                not hasattr(self, "_timeframe_no_data_logged")
                or not self._timeframe_no_data_logged
            ):
                logger.debug("[TIMEFRAME] Waiting for data...")
                self._timeframe_no_data_logged = True
            return  # No data to display yet
        # Reset flag when we have data
        self._timeframe_no_data_logged = False

        # Only log occasionally (every 20th update)
        if not hasattr(self, "_timeframe_process_counter"):
            self._timeframe_process_counter = 0
        self._timeframe_process_counter += 1
        if self._timeframe_process_counter % 20 == 1:
            logger.info(
                f"[TIMEFRAME] Processing data - mode={self._live_cycle_mode}, duration={self._live_cycle_timeframe}min, counts={data_counts}"
            )

        try:
            import numpy as np

            # Extract data based on current timeframe settings
            cycle_data = self._extract_cycle_timeframe()

            # DEBUG: Log extraction results
            extraction_summary = {
                ch: len(cycle_data.get(ch, {}).get("time", []))
                for ch in ["a", "b", "c", "d"]
            }
            if self._timeframe_process_counter % 20 == 1:
                logger.info(f"[TIMEFRAME] Extracted points: {extraction_summary}")

            # Process each channel
            for ch_letter, ch_idx in self._channel_pairs:
                if ch_letter not in cycle_data:
                    continue

                times = cycle_data[ch_letter].get("time", [])
                wavelengths = cycle_data[ch_letter].get("wavelength", [])

                if len(times) == 0 or len(wavelengths) == 0:
                    logger.debug(
                        f"[TIMEFRAME] Ch {ch_letter}: skipping - no data (times={len(times)}, wavelengths={len(wavelengths)})"
                    )
                    continue

                # Filter out already-processed data (only append NEW points)
                last_processed = self._last_processed_time[ch_letter]
                if last_processed >= 0:
                    # Keep only points with time > last_processed
                    new_indices = [i for i, t in enumerate(times) if t > last_processed]
                    if len(new_indices) == 0:
                        logger.debug(
                            f"[TIMEFRAME] Ch {ch_letter}: skipping - no new data since {last_processed:.1f}s"
                        )
                        continue
                    times = [times[i] for i in new_indices]
                    wavelengths = [wavelengths[i] for i in new_indices]

                logger.info(
                    f"[TIMEFRAME] Ch {ch_letter}: processing {len(times)} NEW points (last_processed={last_processed:.1f}s)"
                )

                # Calculate ╬ö SPR baseline
                # For moving window: Use persistent baseline (first point ever, or calibrated)
                # For fixed window: Use first point in the cursor range
                if self._live_cycle_mode == "moving":
                    # Check if we have a persistent baseline for this channel
                    baseline = self._timeframe_baseline_wavelengths[ch_letter]
                    if baseline is None:
                        # First time: establish baseline from calibrated or first point
                        baseline = self.buffer_mgr.baseline_wavelengths[ch_letter]
                        if baseline is None and len(wavelengths) > 0:
                            # Use first VALID wavelength (620-680nm range for SPR)
                            for wl in wavelengths:
                                if 620.0 <= wl <= 680.0:
                                    baseline = wl
                                    break
                            else:
                                # No valid wavelengths - use first point anyway
                                baseline = wavelengths[0]
                        self._timeframe_baseline_wavelengths[ch_letter] = baseline
                        logger.info(
                            f"[TIMEFRAME] Ch {ch_letter}: established baseline={baseline:.4f}nm (persistent for moving window)"
                        )
                else:
                    # Fixed window: use calibrated baseline or first VALID point in range
                    baseline = self.buffer_mgr.baseline_wavelengths[ch_letter]
                    if baseline is None and len(wavelengths) > 0:
                        # Use first VALID wavelength (620-680nm range for SPR)
                        for wl in wavelengths:
                            if 620.0 <= wl <= 680.0:
                                baseline = wl
                                break
                        else:
                            # No valid wavelengths - use first point anyway
                            baseline = wavelengths[0]
                        logger.info(
                            f"[TIMEFRAME] Ch {ch_letter}: using first valid point as baseline={baseline:.4f}nm"
                        )

                # Convert wavelength shift to RU
                wavelengths_array = np.array(wavelengths)
                delta_spr = (wavelengths_array - baseline) * WAVELENGTH_TO_RU_CONVERSION

                logger.info(
                    f"[TIMEFRAME] Ch {ch_letter}: delta_spr range=[{delta_spr.min():.2f}, {delta_spr.max():.2f}] RU"
                )

                # For moving window mode: APPEND data (accumulate over time)
                # For fixed window mode: would use update_cycle_data (replace)
                if self._live_cycle_mode == "moving":
                    window_seconds = self._live_cycle_timeframe * 60
                    self.buffer_mgr.append_cycle_data(
                        ch_letter,
                        times,
                        wavelengths,
                        delta_spr.tolist(),
                        times,  # Use times as timestamps
                        max_window_seconds=window_seconds,
                    )
                    # Update last processed time to prevent re-appending same data
                    if len(times) > 0:
                        self._last_processed_time[ch_letter] = times[-1]
                    logger.debug(
                        f"[TIMEFRAME] Ch {ch_letter}: appended {len(times)} points, buffer now has {len(self.buffer_mgr.cycle_data[ch_letter].time)} total"
                    )
                else:
                    # Fixed window mode: replace entire buffer
                    self.buffer_mgr.update_cycle_data(
                        ch_letter,
                        times,
                        wavelengths,
                        delta_spr.tolist(),
                        times,
                    )

            # Apply reference subtraction if enabled
            self._apply_reference_subtraction()

            # Update graph curves with potentially subtracted data
            points_plotted = {}
            for ch_letter, ch_idx in self._channel_pairs:
                cycle_time = self.buffer_mgr.cycle_data[ch_letter].time
                delta_spr = self.buffer_mgr.cycle_data[ch_letter].spr

                if len(cycle_time) == 0:
                    logger.debug(
                        f"[TIMEFRAME] Ch {ch_letter}: no cycle data after ref subtraction"
                    )
                    continue

                # Update cycle of interest graph
                try:
                    curve = self.main_window.cycle_of_interest_graph.curves[ch_idx]
                    curve.setData(cycle_time, delta_spr)
                    points_plotted[ch_letter] = len(cycle_time)
                except Exception as e:
                    logger.error(f"[PLOT] Ch {ch_letter}: failed to plot - {e}")

            # Update ╬ö SPR display
            self._update_delta_display()

            # Log only every 20th update (reduce spam)
            if len(points_plotted) > 0:
                if not hasattr(self, "_plot_update_count"):
                    self._plot_update_count = 0
                self._plot_update_count += 1
                if self._plot_update_count % 20 == 0:
                    logger.info(
                        f"[LIVE CYCLE] Updated #{self._plot_update_count} - mode={self._live_cycle_mode}, plotted={points_plotted}"
                    )
            else:
                logger.warning(
                    "[LIVE CYCLE] No data plotted - check reference subtraction or baseline"
                )

        except Exception as e:
            logger.error(f"[TIMEFRAME] Error updating cycle graph: {e}", exc_info=True)

    # ==================== End Timeframe Mode Handlers ====================

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

        # Log concise hardware summary
        ctrl = status.get("ctrl_type", "None")
        spec = "Γ£ô" if status.get("spectrometer") else "Γ£ù"
        knx = status.get("knx_type", "None")
        pump = "Γ£ô" if status.get("pump_connected") else "Γ£ù"
        sensor = "Γ£ô" if status.get("sensor_ready") else "Γ£ù"
        optics = "Γ£ô" if status.get("optics_ready") else "Γ£ù"
        fluids = "Γ£ô" if status.get("fluidics_ready") else "Γ£ù"
        logger.info(
            f"Hardware: {ctrl} | Spec:{spec} KNX:{knx} Pump:{pump} | Sensor:{sensor} Optics:{optics} Fluids:{fluids}"
        )

    # === VIEWMODEL SIGNAL HANDLERS (Phase 1.3+1.4 Integration) ===

    def _on_vm_device_connected(self, device_type: str, serial_number: str):
        """Handle device_connected signal from DeviceStatusViewModel.

        Args:
            device_type: Type of device ('controller', 'spectrometer', etc.)
            serial_number: Device serial number

        """
        logger.info(
            f"Γëí╞Æ├┤├¡ [ViewModel] Device connected: {device_type} (S/N: {serial_number})"
        )
        # UI updates are handled by the main window's direct connection to hardware_mgr
        # This is here for future enhancements (e.g., notifications, logging)

    def _on_vm_device_disconnected(self, device_type: str):
        """Handle device_disconnected signal from DeviceStatusViewModel.

        Args:
            device_type: Type of device that disconnected

        """
        logger.info(f"Γëí╞Æ├┤├¡ [ViewModel] Device disconnected: {device_type}")
        # Future: Could show notification or update status indicators

    def _on_vm_device_error(self, device_type: str, error_message: str):
        """Handle device_error signal from DeviceStatusViewModel.

        Args:
            device_type: Type of device with error
            error_message: Error description

        """
        logger.warning(
            f"Γëí╞Æ├┤├¡ [ViewModel] Device error - {device_type}: {error_message}"
        )
        # Future: Could show error notification or update error indicators

    def _on_vm_status_changed(self, all_connected: bool, all_healthy: bool):
        """Handle overall_status_changed signal from DeviceStatusViewModel.

        Args:
            all_connected: True if all required devices are connected
            all_healthy: True if all devices are healthy (no errors)

        """
        # Status already logged in _update_device_status_ui
        # Future: Could enable/disable features based on system health

    # === SPECTRUM VIEWMODEL SIGNAL HANDLERS (Phase 1.3 Integration) ===

    def _on_spectrum_updated(
        self, channel: str, wavelengths: np.ndarray, transmission: np.ndarray
    ):
        """Handle spectrum_updated signal from SpectrumViewModel.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            wavelengths: Wavelength array
            transmission: Processed transmission spectrum

        """
        # Queue via AL_UIUpdateCoordinator (raw spectrum handled separately in _on_raw_spectrum_updated)
        self.ui_updates.queue_transmission_update(
            channel, wavelengths, transmission, None
        )
        logger.debug(f"[ViewModel] Spectrum updated for channel {channel}")

    def _on_raw_spectrum_updated(
        self, channel: str, wavelengths: np.ndarray, raw_spectrum: np.ndarray
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
                timestamp=data.get("timestamp", monotonic()),
                integration_time=data.get("integration_time", 0.0),
                num_scans=data.get("num_scans", 1),
                led_intensity=data.get("led_intensity", 0),
                metadata=data.get("metadata", {}),
            )
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Failed to create RawSpectrumData for channel {channel}: {e}"
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
                timestamp=data.get("timestamp", monotonic()),
                reference_spectrum=ref_spectrum,
                baseline_corrected=True,  # We apply baseline correction via services
                metadata=data.get("metadata", {}),
            )
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Failed to create ProcessedSpectrumData for channel {channel}: {e}"
            )
            return None

    # === CALIBRATION VIEWMODEL SIGNAL HANDLERS (Phase 1.3 Integration) ===

    def _on_cal_vm_started(self):
        """Handle calibration_started signal from CalibrationViewModel."""
        logger.info("Γëí╞Æ├┤├¡ [CalibrationViewModel] Calibration started")
        # Future: Update UI to show calibration in progress

    def _on_cal_vm_progress(self, percent: int, message: str):
        """Handle calibration_progress signal from CalibrationViewModel.

        Args:
            percent: Progress percentage (0-100)
            message: Status message

        """
        logger.info(f"Γëí╞Æ├┤├¡ [CalibrationViewModel] Progress: {percent}% - {message}")
        # Future: Update progress bar in UI

    def _on_cal_vm_complete(self, calibration_data: dict):
        """Handle calibration_complete signal from CalibrationViewModel.

        Args:
            calibration_data: Calibration data dictionary

        """
        logger.info("Γëí╞Æ├┤├¡ [CalibrationViewModel] Calibration complete")
        # Future: Display success message, enable acquisition

    def _on_cal_vm_failed(self, error_message: str):
        """Handle calibration_failed signal from CalibrationViewModel.

        Args:
            error_message: Error description

        """
        logger.error(f"Γëí╞Æ├┤├¡ [CalibrationViewModel] Calibration failed: {error_message}")
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
            f"Γëí╞Æ├┤├¡ [CalibrationViewModel] Validation: {'PASSED' if passed else 'FAILED'} "
            f"({errors} errors, {warnings} warnings)"
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
            logger.info("Γëí╞Æ├┤├╗ Loading servo positions from device config file...")

            # Load servo positions from device config file (not EEPROM)
            if self.main_window.device_config:
                servo_positions = self.main_window.device_config.get_servo_positions()
                s_pos = servo_positions["s"]
                p_pos = servo_positions["p"]

                # Check if positions are absent or still at default values
                # Default values (10/100) indicate servo calibration hasn't been run
                if s_pos == 10 and p_pos == 100:
                    logger.warning("=" * 80)
                    logger.warning("╬ô├£├íΓê⌐Γòò├à  SERVO POSITIONS AT DEFAULT VALUES")
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
                logger.info(
                    "Γëí╞Æ├╢├å CRITICAL: Syncing servo positions to controller EEPROM"
                )
                logger.info("=" * 80)
                logger.info(f"   Device Config: S={s_pos}Γö¼Γûæ, P={p_pos}Γö¼Γûæ")
                logger.info("   Action: Writing to controller EEPROM...")

                try:
                    # Read current EEPROM config
                    eeprom_config = self.hardware_mgr.ctrl.read_config_from_eeprom()

                    if eeprom_config:
                        # Check if EEPROM positions match device_config
                        eeprom_s = eeprom_config.get("servo_s_position")
                        eeprom_p = eeprom_config.get("servo_p_position")

                        logger.info(
                            f"   Current EEPROM: S={eeprom_s}Γö¼Γûæ, P={eeprom_p}Γö¼Γûæ"
                        )

                        if eeprom_s != s_pos or eeprom_p != p_pos:
                            logger.warning("╬ô├£├íΓê⌐Γòò├à  EEPROM MISMATCH DETECTED!")
                            logger.warning(
                                f"   Device Config: S={s_pos}Γö¼Γûæ, P={p_pos}Γö¼Γûæ"
                            )
                            logger.warning(
                                f"   EEPROM:        S={eeprom_s}Γö¼Γûæ, P={eeprom_p}Γö¼Γûæ"
                            )
                            logger.warning(
                                "   Updating EEPROM to match device_config..."
                            )

                            # Update EEPROM with device_config positions
                            eeprom_config["servo_s_position"] = s_pos
                            eeprom_config["servo_p_position"] = p_pos

                            if self.hardware_mgr.ctrl.write_config_to_eeprom(
                                eeprom_config
                            ):
                                logger.info("[OK] EEPROM updated successfully")
                                logger.info(
                                    "Γëí╞Æ├╢├ñ Power cycle controller to apply new positions"
                                )
                                logger.warning("")
                                logger.warning("=" * 80)
                                logger.warning(
                                    "╬ô├£├íΓê⌐Γòò├à  CRITICAL: CONTROLLER NEEDS POWER CYCLE"
                                )
                                logger.warning("=" * 80)
                                logger.warning(
                                    "The controller firmware caches EEPROM positions at boot."
                                )
                                logger.warning(
                                    "New positions have been written but firmware is still using old values."
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
                                logger.error("[X] EEPROM write failed!")
                                logger.error(
                                    "   DANGER: Controller may use wrong positions!"
                                )
                        else:
                            logger.info(
                                "[OK] EEPROM matches device_config - no update needed"
                            )
                    else:
                        logger.warning("╬ô├£├íΓê⌐Γòò├à  Could not read EEPROM config")
                        logger.warning("   Cannot verify position sync")

                except Exception as e:
                    logger.error(f"[X] EEPROM sync failed: {e}")
                    logger.error(
                        "   DANGER: Controller positions may not match device_config!"
                    )

                logger.info("=" * 80)
                logger.info(
                    f"  Servo positions: S={s_pos}Γö¼Γûæ, P={p_pos}Γö¼Γûæ (Γëí╞Æ├╢├å IMMUTABLE - loaded at init)"
                )
                logger.info("=" * 80)
            else:
                logger.warning(
                    "  ╬ô├£├íΓê⌐Γòò├à Device config not available - cannot load servo positions"
                )

            # Load LED intensities from device config (for fast startup)
            if self.main_window.device_config:
                # Load LED intensities from config
                try:
                    # Get integration time from calibration data or use default
                    integration_time_ms = 40.0  # Default
                    if (
                        self.data_mgr
                        and self.data_mgr.calibrated
                        and hasattr(self.data_mgr, "calibration_data")
                    ):
                        cd = self.data_mgr.calibration_data
                        int_time_s = (
                            getattr(cd, "p_integration_time", None)
                            or getattr(cd, "s_mode_integration_time", None)
                            or 0.040
                        )
                        integration_time_ms = int_time_s * 1000.0  # Convert to ms

                    # TODO: Integrate 3-stage linear LED calibration model here
                    # from led_calibration_manager import get_led_intensities_for_scan
                    # target_counts = 60000
                    # intensities = get_led_intensities_for_scan(target_counts, integration_time_ms)
                    # led_a, led_b, led_c, led_d = intensities['A'], intensities['B'], intensities['C'], intensities['D']

                    # For now: Use static values from config
                    logger.info(
                        "  [STATIC] Using static LED intensities from device config"
                    )
                    led_intensities = (
                        self.main_window.device_config.get_led_intensities()
                    )
                    led_a = led_intensities["a"]
                    led_b = led_intensities["b"]
                    led_c = led_intensities["c"]
                    led_d = led_intensities["d"]
                    logger.info(
                        f"  [STATIC] Intensities: A={led_a}, B={led_b}, C={led_c}, D={led_d}"
                    )

                except Exception as e:
                    # Fallback to static values on error
                    logger.warning(f"  [FALLBACK] Could not load LED intensities: {e}")
                    logger.warning("  [FALLBACK] Using static values from config")
                    led_intensities = (
                        self.main_window.device_config.get_led_intensities()
                    )
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
                        f"  [OK] LED intensities applied to hardware: A={led_a}, B={led_b}, C={led_c}, D={led_d}"
                    )
                else:
                    logger.info(
                        "  ╬ô├ñΓòúΓê⌐Γòò├à  No calibrated LED intensities - will calibrate on startup"
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
        """Delegate to calibration service."""
        self.calibration.start_calibration()

    def _update_led_intensities_for_integration_time(
        self, integration_time_ms: float, polarization: str = "P"
    ):
        """Calculate and update LED intensities based on integration time.

        TODO: Integrate 3-stage linear LED calibration model.
        For now, this method does nothing (uses static values from config).

        Args:
            integration_time_ms: Integration time in milliseconds
            polarization: 'S' or 'P' polarization mode (not used with current static config)

        """
        if not self.main_window.device_config:
            logger.debug("No device config available for LED intensity calculation")
            return

        try:
            # TODO: Integrate 3-stage linear calibration
            # from led_calibration_manager import get_led_intensities_for_scan
            # target_counts = 60000
            # intensities = get_led_intensities_for_scan(target_counts, integration_time_ms)
            # led_a, led_b, led_c, led_d = intensities['A'], intensities['B'], intensities['C'], intensities['D']
            #
            # # Update UI
            # self.main_window.channel_a_input.setText(str(led_a))
            # self.main_window.channel_b_input.setText(str(led_b))
            # self.main_window.channel_c_input.setText(str(led_c))
            # self.main_window.channel_d_input.setText(str(led_d))
            #
            # # Apply to hardware
            # if self.hardware_mgr and hasattr(self.hardware_mgr, 'ctrl') and self.hardware_mgr.ctrl:
            #     self.hardware_mgr.ctrl.set_intensity('a', led_a)
            #     self.hardware_mgr.ctrl.set_intensity('b', led_b)
            #     self.hardware_mgr.ctrl.set_intensity('c', led_c)
            #     self.hardware_mgr.ctrl.set_intensity('d', led_d)

            logger.debug(
                "Dynamic LED intensity update not implemented (using static config values)"
            )

        except Exception as e:
            logger.warning(f"Could not update LED intensities dynamically: {e}")
            logger.debug("LED intensity update error:", exc_info=True)

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
                f"Γëí╞Æ├┤┬Ñ LED intensities updated in UI: A={led_a}, B={led_b}, C={led_c}, D={led_d}"
            )

        except Exception as e:
            logger.error(f"Failed to update LED intensities in UI: {e}")

    def _on_quick_export_csv(self):
        """Quick export cycle of interest data to CSV file."""
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
            from affilabs.utils.time_utils import for_filename

            timestamp = for_filename().replace(".", "_")
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
                from affilabs.utils.time_utils import now_utc_iso

                f.write(f"# Export Date,{now_utc_iso()}\n")
                f.write(f"# Start Time (s),{start_time:.2f}\n")
                f.write(f"# Stop Time (s),{stop_time:.2f}\n")
                f.write(f"# Duration (s),{stop_time - start_time:.2f}\n")
                f.write("\n")

                # Write DataFrame (vectorized, much faster than manual loops)
                df.to_csv(f, index=False, float_format="%.4f")

            logger.info(f"[OK] Cycle data exported to: {file_path}")
            from widgets.message import show_message

            show_message(
                f"Cycle exported successfully!\n{Path(file_path).name}", "Information"
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
                    from affilabs.utils.time_utils import now_utc

                    session_dir = Path("data") / "cycles" / now_utc().strftime("%Y%m%d")
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
                    time_array, (0, max_len - len(time_array)), constant_values=np.nan
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
                        spr_array, (0, max_len - len(spr_array)), constant_values=np.nan
                    )

                df_data[f"Ch {ch.upper()} Wavelength (nm)"] = wave_array
                df_data[f"Ch {ch.upper()} SPR (RU)"] = spr_array

            df = pd.DataFrame(df_data)

            # Write to CSV with metadata
            with open(filepath, "w", newline="") as f:
                # Write metadata
                f.write("# AffiLabs Cycle Autosave\n")
                from affilabs.utils.time_utils import now_utc_iso

                f.write(f"# Timestamp,{now_utc_iso()}\n")
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
                f"Γëí╞Æ├åΓò¢ Cycle autosaved to {filename} ({len(active_channels)} channels, {len(df)} points)"
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
        from pathlib import Path

        import pandas as pd
        from PySide6.QtWidgets import QFileDialog

        try:
            logger.info(
                f"Γëí╞Æ├┤├▒ Export requested with config: {config.get('preset', 'custom')}"
            )

            # Check if there's data to export
            has_data = False
            for ch in self._idx_to_channel:
                if len(self.buffer_mgr.cycle_data[ch].time) > 0:
                    has_data = True
                    break

            if not has_data:
                from affilabs.widgets.message import show_message

                show_message(
                    "No cycle data available to export. Start acquisition and record some data first.",
                    msg_type="Warning",
                    title="No Data",
                )
                return

            # Determine filename and path
            filename = config.get("filename", "")
            if not filename:
                from affilabs.utils.time_utils import for_filename

                timestamp = for_filename().replace(".", "_")
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
                            }
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
            from affilabs.widgets.message import show_message

            show_message(
                f"Data exported successfully to:\n{file_path}",
                msg_type="Information",
                title="Export Complete",
            )

        except Exception as e:
            logger.exception(f"Export failed: {e}")
            from affilabs.widgets.message import show_message

            show_message(
                f"Failed to export data:\n{e!s}",
                msg_type="Critical",
                title="Export Error",
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
                painter, target=QRectF(0, 0, total_width, graph_rect.height())
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
                f"Graph exported successfully!\n{Path(file_path).name}", "Information"
            )

        except Exception as e:
            logger.exception(f"Failed to export graph image: {e}")
            from widgets.message import show_message

            show_message(f"Export failed: {e}", "Error")

    def _print_profiling_stats(self):
        """Print profiling statistics (called periodically by timer)."""
        if PROFILING_ENABLED:
            logger.info("\n╬ô├àΓûÆΓê⌐Γòò├à PERIODIC PROFILING SNAPSHOT:")
            self.profiler.print_stats(sort_by="total", min_calls=10)
            logger.info("")


def _install_ascii_safe_print():
    """Install a global ASCII-safe print wrapper to prevent mojibake.

    Forces non-ASCII characters to be replaced when writing to stdout/stderr,
    so legacy direct prints from worker threads don't emit garbled glyphs.
    """
    try:
        import builtins

        original_print = builtins.print

        def ascii_print(*args, **kwargs):
            sep = kwargs.get("sep", " ")
            end = kwargs.get("end", "\n")
            file = kwargs.get("file", sys.stdout)
            flush = kwargs.get("flush", False)

            try:
                text = sep.join(str(a) for a in args)
            except Exception:
                # Fallback: ensure representation safely
                text = sep.join(repr(a) for a in args)

            # Encode to ASCII with replacement to strip/replace non-ASCII
            safe = text.encode("ascii", errors="replace").decode("ascii")
            try:
                file.write(safe + end)
            except Exception:
                # Last-resort fallback to original print
                original_print(safe, sep=sep, end=end, file=file)

            if flush:
                try:
                    file.flush()
                except Exception:
                    pass

        builtins.print = ascii_print
    except Exception:
        # If anything goes wrong, keep default print
        pass


def main():
    # Install ASCII-safe print early to sanitize any stray prints
    _install_ascii_safe_print()
    """Launch the application with modern UI."""
    import atexit

    # Install global exception hook to catch crashes
    def exception_hook(exc_type, exc_value, exc_traceback):
        """Catch all unhandled exceptions before they crash the app."""
        logger.critical("=" * 80)
        logger.critical("Γëí╞Æ├å├æ UNHANDLED EXCEPTION - APPLICATION CRASH")
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
    logger.info("Γëí╞Æ┬ó├¡Γê⌐Γòò├à Global exception hook installed")

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
                QPainter.CompositionMode.CompositionMode_SourceOver
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

    logger.info("Γëí╞Æ├£├ç Starting event loop...")
    exit_code = app.exec()

    # Restore original stderr
    sys.stderr = original_stderr
    sys.stdout = original_stdout

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
