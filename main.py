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
        except Exception:
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
    # Log the import error for debugging
    import logging
    logging.warning(f"Coordinator import failed: {e}")

# --- Phase 1 Architecture Components ---
# ViewModels (Phase 1.3 - UI presentation logic)
from affilabs.app_config import (
    DEFAULT_FILTER_ENABLED,
    DEFAULT_FILTER_STRENGTH,
    LEAK_DETECTION_WINDOW,
    LEAK_THRESHOLD_RATIO,
)

# Domain Models (Phase 1.1 - Data structures)
from affilabs.domain import ProcessedSpectrumData, RawSpectrumData

# Business Services (Phase 1.2 - Core logic)
from affilabs.services import BaselineCorrector, TransmissionCalculator

# Configuration
from affilabs.settings import PROFILING_ENABLED, PROFILING_REPORT_INTERVAL, SW_VERSION

# --- Utilities and Configuration ---
from affilabs.utils.logger import logger
from affilabs.utils.performance_profiler import get_profiler
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
# SECTION 7: Helper Functions
# ============================================================================


def _safe_get_global(name: str, default: str = "") -> str:
    """Safely retrieve a global variable value, returning default if not found.

    Args:
        name: Global variable name to retrieve
        default: Default value if variable doesn't exist

    Returns:
        Variable value as string, or default if not found

    """
    return str(globals().get(name, default))


# ============================================================================
# SECTION 8: Application Class
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
            2,
            "Validation",
            self._validate_critical_imports,
            critical=True,
        )

        # ============================================================
        # PHASE 3: Infrastructure Setup (no business logic)
        # ============================================================
        self._run_init_phase(3, "Infrastructure", self._setup_infrastructure)

        # ============================================================
        # PHASE 4: State Initialization (all instance variables)
        # ============================================================
        self._run_init_phase(
            4,
            "State Variables",
            self._init_state_variables,
            critical=True,
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
            8,
            "Signal Wiring",
            self._connect_all_signals,
            critical=True,
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
            logger.info(f"[{phase}] {name}")
            func()
            logger.debug(f"[{phase}] ✓ {name}")
        except Exception as e:
            logger.error(f"[{phase}] ✗ {name}: {e}", exc_info=True)
            if critical:
                logger.critical(f"Critical initialization failed")
                raise SystemExit(1)
            logger.warning(f"[{phase}] Non-critical error, continuing")

    def _validate_critical_imports(self):
        """Fail fast if critical modules are missing or broken.

        This prevents silent fallback to stub classes that cause
        hard-to-debug issues like "controller not found".

        Raises:
            SystemExit: If any critical import fails

        """
        logger.debug("Validating imports...")

        failures = []

        # Validate controller classes (ArduinoController deleted - obsolete)
        try:
            from affilabs.utils.controller import (
                PicoEZSPR,
                PicoP4SPR,
            )

            # Verify classes are actually callable (not None/stub)
            if not all(
                callable(cls) for cls in [PicoP4SPR, PicoEZSPR]
            ):
                raise ImportError("Controller classes are not callable")
            logger.debug("✓ Controllers")
        except (ImportError, AttributeError) as e:
            failures.append(f"Controllers: {e}")

        # Validate settings
        try:
            from settings import ARDUINO_VID, PICO_VID

            # Verify settings are valid integers
            if not all(isinstance(vid, int) for vid in [PICO_VID, ARDUINO_VID]):
                raise ValueError("VID values must be integers")
            logger.debug("✓ Settings")
        except (ImportError, AttributeError, ValueError) as e:
            failures.append(f"Settings: {e}")

        # Report HAL availability
        hal_status = "✓ HAL" if HAL_AVAILABLE else "⚠ HAL unavailable"
        logger.debug(hal_status)

        # Report Coordinators availability
        if COORDINATORS_AVAILABLE:
            logger.debug("✓ UI Coordinators")
        else:
            error_msg = _safe_get_global("_coordinators_import_error", "unknown error")
            logger.warning(f"⚠ UI Coordinators not available: {error_msg}")

        # Fail fast if critical imports missing
        if failures:
            logger.critical("=" * 80)
            logger.critical("CRITICAL STARTUP FAILURES DETECTED")
            logger.critical("=" * 80)
            for failure in failures:
                logger.critical(f"  {failure}")
            logger.critical("=" * 80)
            raise SystemExit(1)

        logger.debug("✓ All critical imports validated")

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
        self._intentional_disconnect = False  # Track user-initiated disconnect

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

        # [Timeframe Mode state variables removed - feature permanently disabled]

        # LED monitoring - now handled by HardwareEventCoordinator

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

        # Peak finding results (updated by pipeline)
        self._latest_peaks = {"a": None, "b": None, "c": None, "d": None}

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
        logger.debug("✓ Pipelines")

        # Hardware manager (does NOT auto-connect)
        self.hardware_mgr = HardwareManager()
        if self.hardware_mgr is None:
            raise RuntimeError("HardwareManager initialization failed")

        # HAL device manager (optional)
        if HAL_AVAILABLE:
            try:
                self.device_manager = DeviceManager()
                logger.debug("✓ DeviceManager (HAL)")
            except Exception as e:
                logger.warning(f"⚠ DeviceManager unavailable: {e}")
                self.device_manager = None
        else:
            self.device_manager = None
            logger.debug("Using legacy HardwareManager")

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
        logger.debug("Segment queue initialized (TEST MODE)")

        logger.debug("✓ Managers")

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
            "✓ Business services",
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

        logger.debug("All services initialized successfully")

        logger.debug("✓ Services")

    def _create_main_window(self):
        """Create main window (UI layer entry point)."""
        logger.debug("Creating main window...")

        # Create main window
        self.main_window = AffilabsMainWindow()

        # Pass hardware manager reference for settings application
        # This allows Settings tab to apply LED intensities without signal routing
        self.main_window.hardware_manager = self.hardware_mgr

        # Wire up elapsed time getter for pause markers
        def get_elapsed_time():
            if self.experiment_start_time is None:
                return None
            return monotonic() - self.experiment_start_time

        self.main_window._get_elapsed_time = get_elapsed_time

        # NOTE: Not storing app reference in UI (violates separation of concerns)
        # UI should only emit signals, not call app methods directly
        # All UIΓåÆApp communication happens through Qt signals

        # Verify spectroscopy plots availability
        if not hasattr(self.main_window, "transmission_curves"):
            logger.warning("⚠ Spectroscopy plots unavailable")

        # Debug controller (requires main_window)
        from affilabs.utils.debug_controller import DebugController

        self.debug = DebugController(self)

        logger.debug("✓ Main window")

    def _init_coordinators(self):
        """Initialize UI coordinators (require main window)."""
        logger.debug("Initializing coordinators...")

        # Hardware event coordinator
        from affilabs.coordinators.hardware_event_coordinator import (
            HardwareEventCoordinator,
        )

        self.hardware_events = HardwareEventCoordinator(
            self.hardware_mgr,
            self.main_window,
            self,
        )

        # Acquisition event coordinator
        from affilabs.coordinators.acquisition_event_coordinator import (
            AcquisitionEventCoordinator,
        )

        self.acquisition_events = AcquisitionEventCoordinator(
            self.data_mgr,
            self.hardware_mgr,
            self.main_window,
            self,
        )

        # UI control event coordinator
        from affilabs.coordinators.ui_control_event_coordinator import (
            UIControlEventCoordinator,
        )

        self.ui_control_events = UIControlEventCoordinator(self)

        # Peripheral event coordinator
        from affilabs.coordinators.peripheral_event_coordinator import (
            PeripheralEventCoordinator,
        )

        self.peripheral_events = PeripheralEventCoordinator(self)

        # Recording event coordinator
        from affilabs.coordinators.recording_event_coordinator import (
            RecordingEventCoordinator,
        )

        self.recording_events = RecordingEventCoordinator(self)

        # UI update coordinator and dialog manager
        if COORDINATORS_AVAILABLE:
            self.ui_updates = AL_UIUpdateCoordinator(self, self.main_window)
            self.dialog_manager = DialogManager(self.main_window)
            self.spectroscopy_presenter = None  # Managed by coordinator
            logger.debug("✓ Coordinators (6 loaded)")
        else:
            self.ui_updates = None
            self.dialog_manager = None
            # Create spectroscopy presenter directly when coordinator isn't available
            try:
                from affilabs.presenters import SpectroscopyPresenter
                self.spectroscopy_presenter = SpectroscopyPresenter(self.main_window)
                logger.debug("✓ SpectroscopyPresenter (fallback)")
            except Exception as e:
                logger.warning(f"  Failed to initialize SpectroscopyPresenter: {e}")
                self.spectroscopy_presenter = None
            logger.debug("✓ Coordinators (5 loaded)")
            logger.warning("  Running without UI coordinators (compatibility mode)")

    def _init_viewmodels(self):
        """Initialize ViewModels (UI-aware, require coordinators and services)."""
        logger.debug("Initializing viewmodels...")

        # Device status view model
        self.device_status_vm = DeviceStatusViewModel(
            device_manager=self.device_manager if HAL_AVAILABLE else None,
        )
        if HAL_AVAILABLE and self.device_manager:
            logger.debug("✓ DeviceStatusViewModel (HAL)")
        else:
            logger.debug("✓ DeviceStatusViewModel (legacy)")

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
                    self.transmission_calc,
                    self.baseline_corrector,
                    spectrum_processor,
                )

            logger.debug("✓ SpectrumViewModel (4 channels)")
        except (ImportError, AttributeError) as e:
            logger.warning(f"  Failed to initialize SpectrumViewModel: {e}")
            self.spectrum_viewmodels = None
        except Exception as e:
            logger.error(
                f"  Unexpected error initializing SpectrumViewModel: {e}",
                exc_info=True,
            )
            self.spectrum_viewmodels = None

        # CalibrationViewModel
        try:
            from services import CalibrationValidator

            self.calibration_viewmodel = CalibrationViewModel()
            calibration_validator = CalibrationValidator()
            self.calibration_viewmodel.set_validator(calibration_validator)
            logger.debug("✓ CalibrationViewModel")
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
        logger.debug("Connecting signals...")

        # Connect hardware manager signals to UI
        self._connect_signals()

        # Connect signals organized by subsystem (Phase 4 refactoring)
        self._connect_viewmodel_signals()
        self._connect_manager_signals()
        self._connect_ui_event_signals()

        logger.debug("✓ All signals connected")

    def _finalize_and_show(self):
        """Finalize initialization and show main window."""
        logger.debug("Finalizing application...")

        # Start processing thread (acquisition ΓåÆ processing separation)
        self._start_processing_thread()

        # UI update throttling - prevent excessive graph redraws (2 Hz = 500ms interval)

        self._ui_update_timer = QTimer()
        self._ui_update_timer.timeout.connect(self._process_pending_ui_updates)
        self._ui_update_timer.setInterval(500)  # Match ui_update_coordinator rate (2 Hz)
        self._ui_update_timer.start()

        # Performance profiling timer (if enabled)
        if PROFILING_ENABLED and PROFILING_REPORT_INTERVAL > 0:
            self._profiling_timer = QTimer()
            self._profiling_timer.timeout.connect(self._print_profiling_stats)
            self._profiling_timer.setInterval(PROFILING_REPORT_INTERVAL * 1000)
            self._profiling_timer.start()
            logger.info(
                f"  Profiling enabled - stats every {PROFILING_REPORT_INTERVAL}s",
            )

        # Show window FIRST (before loading heavy widgets)
        logger.debug("Showing main window...")
        if hasattr(self, "update_splash_message"):
            self.update_splash_message("Building interface...")

        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
        QApplication.processEvents()  # Force immediate render
        logger.debug(f"Window visible: {self.main_window.isVisible()}")

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
            logger.debug("Loading deferred UI components...")
            # Update splash message
            if hasattr(self, "update_splash_message"):
                self.update_splash_message("Loading graphs...")

            # Load heavy graph widgets (PyQtGraph plots)
            if hasattr(self.main_window, "load_deferred_graphs"):
                self.main_window.load_deferred_graphs()
                logger.debug("✓ Graph widgets")

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
                logger.debug("✓ Timeline cursors")

            # Connect cursor auto-follow signal (thread-safe)
            self.cursor_update_signal.connect(self._update_stop_cursor_position)
            logger.debug("✓ Cursor auto-follow")

            # [Timeframe Mode removed - using legacy cursor system]

            # Update cached attribute checks now that graphs are loaded
            self._has_stop_cursor = (
                hasattr(self.main_window, "full_timeline_graph")
                and hasattr(self.main_window.full_timeline_graph, "stop_cursor")
                and self.main_window.full_timeline_graph.stop_cursor is not None
            )
            logger.debug(
                f"\u2713 Stop cursor available: {self._has_stop_cursor}",
            )

            # Connect polarizer toggle button to servo control
            if hasattr(self.main_window, "polarizer_toggle_btn"):
                self.main_window.polarizer_toggle_btn.clicked.connect(
                    self._on_polarizer_toggle_clicked,
                )
                logger.debug("✓ Polarizer toggle")

            # Connect mouse events for channel selection and flagging
            if hasattr(self.main_window, "cycle_of_interest_graph"):
                self.main_window.cycle_of_interest_graph.scene().sigMouseClicked.connect(
                    self._on_graph_clicked,
                )
                logger.debug("✓ Graph click events")

            # Mark deferred loading as complete
            self._deferred_connections_pending = False

            # Now connect UI button/control signals (after graphs are loaded)
            self._connect_ui_signals()
            logger.debug("✓ UI control signals")

            logger.debug("✓ Deferred UI components loaded")

        except Exception as e:
            logger.error(f"[X] Error loading deferred widgets: {e}", exc_info=True)
            # Non-fatal - app can continue with reduced functionality

    def _apply_theme(self):
        """Apply modern UI theme."""
        try:
            # Prefer centralized affilabs theme manager
            from affilabs.utils.ui_styles import UIStyleManager

            UIStyleManager.apply_app_theme(self)
        except Exception:
            # Theme not available or failed; continue with default styling
            pass

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
        # NOTE: _on_calibration_complete_status_update handles BOTH status updates AND QC dialog
        logger.debug(
            "✓ calibration.calibration_complete signal",
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
        """Handler for calibration completion - updates status AND shows QC dialog."""
        from affilabs.utils.settings_helpers import SettingsHelpers

        SettingsHelpers.on_calibration_complete(self, calibration_data)

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
        logger.debug(
            "✓ power_on_requested signal",
        )

        self.main_window.power_off_requested.connect(self._on_power_off_requested)
        self.main_window.recording_start_requested.connect(
            self._on_recording_start_requested,
        )
        self.main_window.recording_stop_requested.connect(
            self._on_recording_stop_requested,
        )
        # NOTE: These signals not yet implemented in main window
        # self.main_window.clear_graphs_requested.connect(self._on_clear_graphs_requested)
        # self.main_window.clear_flags_requested.connect(self._on_clear_flags_requested)
        # self.main_window.pipeline_changed.connect(self._on_pipeline_changed)
        logger.debug("Connected: main_window UI action signals")

        # === DEBUG SHORTCUTS ===
        from PySide6.QtGui import QKeySequence, QShortcut

        logger.debug("Registering debug shortcuts...")

        # Ctrl+Shift+C: Bypass calibration - DISABLED (missing debug_helpers module)
        # bypass_calibration_shortcut = QShortcut(QKeySequence("Ctrl+Shift+C"), self.main_window)
        # bypass_calibration_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        # bypass_calibration_shortcut.activated.connect(self.debug.bypass_calibration)
        # logger.info(f"[OK] Ctrl+Shift+C registered: {bypass_calibration_shortcut}")

        # Ctrl+Shift+S: Start simulation mode (inject fake spectra)
        simulation_shortcut = QShortcut(QKeySequence("Ctrl+Shift+S"), self.main_window)
        simulation_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        simulation_shortcut.activated.connect(self.debug.start_simulation)
        logger.debug(f"[DEBUG] Ctrl+Shift+S: {simulation_shortcut}")
        logger.debug(f"   Context: {simulation_shortcut.context()}")
        logger.debug(f"   Key: {simulation_shortcut.key().toString()}")

        # Ctrl+Shift+1: Single data point test (minimal test)
        single_point_shortcut = QShortcut(
            QKeySequence("Ctrl+Shift+1"),
            self.main_window,
        )
        single_point_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        single_point_shortcut.activated.connect(self.debug.send_single_data_point)
        logger.debug(f"[DEBUG] Ctrl+Shift+1: {single_point_shortcut}")
        logger.debug(f"   Context: {single_point_shortcut.context()}")
        logger.debug(f"   Key: {single_point_shortcut.key().toString()}")

        logger.debug("Ctrl+Shift+S: spectrum simulation")

        self.main_window.acquisition_pause_requested.connect(
            self._on_acquisition_pause_requested,
        )
        self.main_window.export_requested.connect(self._on_export_requested)

        # === TIMEFRAME MODE SIGNALS (Phase 2 - Cursor Replacement) ===
        logger.debug("[Timeframe Mode removed]")

        # === UI CONTROL SIGNALS (direct connections - not through event bus) ===
        self._connect_ui_control_signals()

        logger.debug("[DEBUG] All shortcuts registered")

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
            logger.debug("[OK] Connected Polarizer Calibration button to handler")

        # OEM Calibration button (direct connection)
        ui.oem_led_calibration_btn.clicked.connect(self._on_oem_led_calibration)

        # Baseline Capture button (REBUILT - direct connection, no lambda)
        if hasattr(ui, "baseline_capture_btn"):
            ui.baseline_capture_btn.clicked.connect(self._on_record_baseline_clicked)
            logger.debug("[OK] Connected Baseline Capture button to handler")
        else:
            logger.warning("[WARN] baseline_capture_btn NOT found in UI")

        # Advanced Settings dialog - connect optical calibration signal
        if hasattr(ui, "advanced_menu") and ui.advanced_menu is not None:
            if hasattr(ui.advanced_menu, "measure_afterglow_sig"):
                ui.advanced_menu.measure_afterglow_sig.connect(
                    self._on_oem_led_calibration,
                )
                logger.info(
                    "[OK] Connected Advanced Settings optical calibration signal",
                )

        # Start Cycle button: App layer needs to start data acquisition
        # (UI's start_cycle() handles experiment queue - different purpose)
        ui.sidebar.start_cycle_btn.clicked.connect(self._on_start_button_clicked)
        logger.debug(
            "✓ start_cycle_btn connected",
        )

        # NOTE: Detector wait time and pipeline selector are in Advanced Settings dialog
        # Values are applied when dialog is accepted

        # Add to Queue button (TEST MODE - segment queue)
        if hasattr(ui.sidebar, "add_to_queue_btn"):
            ui.sidebar.add_to_queue_btn.clicked.connect(self._on_add_to_queue)
            logger.debug(
                "✓ add_to_queue_btn connected (TEST MODE)",
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
            self._on_vm_device_disconnected,
        )
        self.device_status_vm.device_error.connect(self._on_vm_device_error)
        self.device_status_vm.overall_status_changed.connect(self._on_vm_status_changed)
        logger.debug("✓ DeviceStatusViewModel signals")

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
                vm.peak_updated.connect(
                    lambda ch, peak, meta, channel=channel: self._on_peak_updated(
                        channel,
                        peak,
                        meta,
                    ),
                )
            logger.debug("✓ SpectrumViewModel signals (4 channels)")

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
            logger.debug("✓ CalibrationViewModel signals")

    def _connect_manager_signals(self):
        """Connect manager/service signals to handlers (Phase 4 refactoring).

        Groups all manager signal connections including hardware, acquisition,
        calibration, recording, and kinetic managers.
        """
        # === CALIBRATION SERVICE ===
        # NOTE: Already connected in _connect_signals() at line 598 to _on_calibration_complete_status_update
        # (merged with _on_calibration_complete to avoid duplicate QC dialogs)
        logger.info(
            "[OK] CalibrationService signals already connected in _connect_signals()",
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
            self.main_window.sidebar,
            "tabs",
        ):
            self.main_window.sidebar.tabs.currentChanged.connect(self._on_tab_changing)
        if hasattr(self.main_window, "content_stack"):
            self.main_window.content_stack.currentChanged.connect(self._on_page_changed)

        # === EMA DISPLAY FILTER CONTROLS ===
        ui = self.main_window.sidebar
        if hasattr(ui, "filter_none_radio"):
            ui.filter_none_radio.toggled.connect(
                lambda checked: self._set_display_filter(0) if checked else None,
            )
        if hasattr(ui, "filter_light_radio"):
            ui.filter_light_radio.toggled.connect(
                lambda checked: self._set_display_filter(1) if checked else None,
            )
        if hasattr(ui, "filter_smooth_radio"):
            ui.filter_smooth_radio.toggled.connect(
                lambda checked: self._set_display_filter(2) if checked else None,
            )

        # Initialize filter to default (None - raw data)
        self._set_display_filter(0)
        logger.debug("✓ Display filter: None (raw data)")

        logger.debug("✓ UI event signals (tabs/pages/filters)")

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

            logger.info(f"Display filter: {config['label']}")
            logger.debug(
                f"   Method: {self._display_filter_method}, Alpha: {self._display_filter_alpha}",
            )

    # === DEBUG / TEST HELPERS ===
    # Debug methods moved to utils/debug_controller.py for separation of concerns.
    # Access via self.debug.method_name():
    #   - self.debug.bypass_calibration() - Ctrl+Shift+C
    #   - self.debug.start_simulation() - Ctrl+Shift+S
    #   - self.debug.send_single_data_point() - Ctrl+Shift+1
    #   - self.debug.test_acquisition_thread() - Ctrl+Shift+T
    #   - self.debug.simulate_calibration_success()

    def _on_detector_wait_changed(self, value: int):
        """Update detector wait time for live acquisition."""
        self.acquisition_events.on_detector_wait_changed(value)

    def _on_start_button_clicked(self):
        """User clicked Start button - begin live data acquisition."""
        self.acquisition_events.on_start_button_clicked()

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
                logger.debug(
                    f"Parsed concentrations: {segment['concentrations']} {units}",
                )

            # Add to queue
            self.segment_queue.append(segment)

            # Log success
            logger.info(f"✓ Added cycle {len(self.segment_queue)}: {cycle_type}, {length_minutes}min")
            logger.debug(f"   Name: {segment['name']}")
            logger.debug(f"   Note: {segment['note'][:100]}...") if len(
                segment["note"],
            ) > 100 else logger.debug(f"   Note: {segment['note']}")

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

            # Update summary table
            self._update_summary_table()

            # Validate queue structure
            self._validate_segment_queue()

        except Exception as e:
            logger.exception(f"[ERROR] Failed to add cycle to queue: {e}")
            if hasattr(self.main_window.sidebar, "intel_message_label"):
                self.main_window.sidebar.intel_message_label.setText(
                    f"✗ Failed to add: {e}",
                )
                self.main_window.sidebar.intel_message_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #FF3B30;"  # Red for error
                    "background: transparent;"
                    "font-weight: 600;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
                )

    def _update_summary_table(self):
        """Update summary table with last 5 cycles from segment queue.

        Displays cycle state, type (with color coding), start time, and notes.
        Color codes cycle types for easy visual distinction.
        """
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QTableWidgetItem
        from datetime import datetime

        # Define color scheme for cycle types
        type_colors = {
            "Auto-read": QColor(242, 242, 247),  # Light gray
            "Baseline": QColor(217, 234, 250),  # Light blue
            "Immobilization": QColor(232, 245, 233),  # Light green
            "Concentration": QColor(255, 243, 224),  # Light orange
        }

        # Get last 5 segments (most recent first)
        recent_segments = self.segment_queue[-5:] if len(self.segment_queue) > 0 else []
        recent_segments.reverse()  # Show newest at top

        # Clear table and populate with segments
        for row in range(5):
            if row < len(recent_segments):
                segment = recent_segments[row]

                # State column with color coding
                status = segment.get("status", "pending")
                if status == "pending":
                    state_text = "⏳ Queued"
                    state_color = QColor(255, 249, 196)  # Light yellow
                elif status == "active":
                    state_text = "▶ Running"
                    state_color = QColor(217, 234, 250)  # Light blue
                elif status == "completed":
                    state_text = "✓ Done"
                    state_color = QColor(232, 245, 233)  # Light green
                else:
                    state_text = "•"
                    state_color = QColor(242, 242, 247)  # Gray

                state_item = QTableWidgetItem(state_text)
                state_item.setBackground(state_color)
                self.main_window.sidebar.summary_table.setItem(row, 0, state_item)

                # Type column with type-specific color
                cycle_type = segment.get("type", "")
                type_item = QTableWidgetItem(cycle_type)
                type_color = type_colors.get(cycle_type, QColor(242, 242, 247))
                type_item.setBackground(type_color)
                self.main_window.sidebar.summary_table.setItem(row, 1, type_item)

                # Start time column
                timestamp = segment.get("timestamp", 0)
                if timestamp > 0:
                    start_time = datetime.fromtimestamp(timestamp).strftime("%H:%M")
                else:
                    start_time = "--:--"
                start_item = QTableWidgetItem(start_time)
                start_item.setBackground(state_color)
                self.main_window.sidebar.summary_table.setItem(row, 2, start_item)

                # Notes column (truncated)
                note = segment.get("note", "")
                note_display = note[:40] + "..." if len(note) > 40 else note
                note_item = QTableWidgetItem(note_display)
                note_item.setBackground(state_color)
                self.main_window.sidebar.summary_table.setItem(row, 3, note_item)

            else:
                # Empty row
                for col in range(4):
                    empty_item = QTableWidgetItem("")
                    empty_item.setBackground(QColor(255, 255, 255))  # White
                    self.main_window.sidebar.summary_table.setItem(row, col, empty_item)

        logger.debug(f"✓ Summary table updated ({len(recent_segments)} cycles)")

    def _validate_segment_queue(self):
        """Validate segment queue structure (TEST MODE).

        Logs queue contents and validates data structure.
        This helps verify the architecture is sound.
        """
        logger.debug("=" * 80)
        logger.debug("🧪 SEGMENT QUEUE VALIDATION TEST")
        logger.debug("=" * 80)
        logger.debug(f"Queue size: {len(self.segment_queue)} segments")
        logger.debug("")

        for i, seg in enumerate(self.segment_queue):
            logger.debug(f"[{i + 1}] {seg['name']}")
            logger.debug(f"    Type: {seg['type']}")
            logger.debug(f"    Length: {seg['length_minutes']} minutes")
            logger.debug(f"    Status: {seg['status']}")

            if "concentrations" in seg:
                logger.debug(
                    f"    Concentrations: {seg['concentrations']} {seg['units']}",
                )

            if seg["note"]:
                logger.debug(f"    Note: {seg['note'][:80]}...") if len(
                    seg["note"],
                ) > 80 else logger.debug(f"    Note: {seg['note']}")

            logger.debug("")

        logger.debug("=" * 80)
        logger.debug("[OK] Queue validation complete")
        logger.debug("=" * 80)

    def _on_scan_requested(self):
        """User clicked Scan button in UI."""
        self.hardware_events.on_scan_requested()

    def _on_hardware_connected(self, status: dict):
        """Hardware connection completed and update Device Status UI."""
        self.hardware_events.on_hardware_connected(status)

    def _on_hardware_disconnected(self):
        """Hardware disconnected."""
        # Check if this was an intentional disconnect (user clicked power off)
        was_intentional = self._intentional_disconnect
        if was_intentional:
            logger.info("Hardware disconnected (user-initiated)")
            self._intentional_disconnect = False  # Reset flag
        else:
            # Unexpected disconnect - show critical error
            logger.error(
                "ΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉ",
            )
            logger.error("CRITICAL: HARDWARE DISCONNECTED")
            logger.error(
                "ΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉ",
            )

        # Check if acquisition was running
        acquisition_was_running = (
            self.data_mgr._acquiring if hasattr(self.data_mgr, "_acquiring") else False
        )

        # Stop acquisition if running
        if acquisition_was_running:
            logger.info("Stopping acquisition (hardware disconnected gracefully)...")
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

        # Show critical error dialog only if NOT user-initiated
        if acquisition_was_running and not was_intentional:
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
        self.hardware_events.start_led_status_monitoring()

    def _stop_led_status_monitoring(self):
        """Stop LED status monitoring timer."""
        self.hardware_events.stop_led_status_monitoring()

    # Note: _update_led_status_display is now handled by HardwareEventCoordinator

    def _on_connection_progress(self, message: str):
        """Hardware connection progress update."""
        self.hardware_events.on_connection_progress(message)

    def _on_hardware_error(self, error: str):
        """Hardware error occurred."""
        self.hardware_events.on_hardware_error(error)
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
        logger.debug("Starting processing thread...")
        self._processing_active = True
        self._processing_thread = threading.Thread(
            target=self._processing_worker,
            name="SpectrumProcessing",
            daemon=True,
        )
        self._processing_thread.start()
        logger.debug(
            f"✓ Processing thread started: {self._processing_thread.name}",
        )

    def _stop_processing_thread(self):
        """Stop processing thread gracefully."""
        if self._processing_thread and self._processing_active:
            self._processing_active = False
            # Send sentinel to wake up thread
            try:
                self._spectrum_queue.put(None, timeout=0.1)
            except Exception:
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
                    self._queue_stats["max_size"],
                    current_size,
                )

            except queue.Empty:
                # Timeout - check if we should continue
                continue
            except Exception as e:
                logger.error(f"[X] Processing worker error: {e}", exc_info=True)

        # Log final statistics
        logger.info(
            f"Γëí╞Æ├╢Γöñ Processing worker stopped - Stats: {self._queue_stats['processed']} processed, "
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
            if not self._safe_queue_put(data):
                # Queue operation failed - log and drop to prevent blocking
                self._queue_stats["dropped"] += 1
                if self._queue_stats["dropped"] % 10 == 1:  # Log every 10th drop
                    logger.warning(
                        f"[WARN] Spectrum queue full - {self._queue_stats['dropped']} frames dropped",
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
        """Process spectrum data in dedicated worker thread."""
        try:
            from affilabs.utils.spectrum_helpers import SpectrumHelpers
            logger.info(f"[MAIN] About to process spectrum for channel {data.get('channel', 'UNKNOWN')}")
            SpectrumHelpers.process_spectrum_data(self, data)
        except Exception as e:
            logger.error(f"[MAIN] Failed to process spectrum: {e}", exc_info=True)

    def _handle_intensity_monitoring(self, channel: str, data: dict, timestamp: float):
        """Handle intensity monitoring and leak detection (extracted for clarity).

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            data: Spectrum data dictionary
            timestamp: Acquisition timestamp

        """
        # numpy imported at module scope as np

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
                        f"Possible optical leak detected in channel {channel.upper()}: "
                        f"avg intensity {avg_intensity:.0f} < threshold {dark_threshold:.0f}",
                    )

    def _queue_transmission_update(self, channel: str, data: dict):
        """Queue transmission spectrum update for batch processing."""
        from affilabs.utils.spectrum_helpers import SpectrumHelpers

        SpectrumHelpers.queue_transmission_update(self, channel, data)

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

        Skip expensive transmission calculations if preconditions aren't met.
        """
        # Note: UI update enable/disable is controlled by AL_UIUpdateCoordinator flags
        # (_transmission_updates_enabled, _raw_spectrum_updates_enabled)

        # Unified calibration source-of-truth
        cd = getattr(self.data_mgr, "calibration_data", None)
        if not cd or not getattr(cd, "s_pol_ref", None):
            return False
        if getattr(cd, "wavelengths", None) is None:
            return False
        return True

    def _on_page_changed(self, page_index: int):
        """Handle page changes - show/hide live data dialog for Live Data page (index 0)."""
        if hasattr(self, 'ui_control_events') and self.ui_control_events:
            self.ui_control_events.on_page_changed(page_index)

    def _on_tab_changing(self, index):
        """Temporarily pause graph updates during tab transition.

        Tab switching can trigger widget repaints that block the UI thread
        when combined with graph updates. Brief pause prevents freezing.
        """
        self._skip_graph_updates = True

        # Resume updates after 200ms (enough time for tab transition to complete)
        QTimer.singleShot(200, lambda: setattr(self, "_skip_graph_updates", False))

    def _process_pending_ui_updates(self):
        """Process queued graph updates at throttled rate (1 Hz)."""
        from affilabs.utils.ui_update_helpers import UIUpdateHelpers

        UIUpdateHelpers.process_pending_ui_updates(self)

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
        """Update the cycle of interest graph based on cursor positions."""
        from affilabs.utils.ui_update_helpers import UIUpdateHelpers

        UIUpdateHelpers.update_cycle_of_interest_graph(self)

    def _update_delta_display(self):
        """Update the Δ SPR display label with values at Stop cursor position."""
        if self.main_window.cycle_of_interest_graph.delta_display is None:
            return

        # numpy imported at module scope as np

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

        # Update label with bold text for better visibility
        self.main_window.cycle_of_interest_graph.delta_display.setText(
            f"<b>SPR: Ch A: {delta_values['a']:.1f} RU  |  Ch B: {delta_values['b']:.1f} RU  |  "
            f"Ch C: {delta_values['c']:.1f} RU  |  Ch D: {delta_values['d']:.1f} RU</b>",
        )

    def _on_acquisition_error(self, error: str):
        """Data acquisition error."""
        self.acquisition_events.on_acquisition_error(error)

    def _on_polarizer_toggle_clicked(self):
        """Handle polarizer toggle button click - switch servo between S and P positions."""
        self.ui_control_events.on_polarizer_toggle_clicked()

    # === Recording Callbacks ===

    def _on_recording_started(self, filename: str):
        """Recording started."""
        self.recording_events.on_recording_started(filename)

    def _on_recording_stopped(self):
        """Recording stopped."""
        self.recording_events.on_recording_stopped()

    def _on_recording_error(self, error: str):
        """Recording error occurred."""
        self.recording_events.on_recording_error(error)

    def _on_event_logged(self, event: str):
        """Event logged to recording."""
        logger.info(f"Event: {event}")

    def _on_acquisition_pause_requested(self, pause: bool):
        """Handle acquisition pause/resume request from UI."""
        if pause:
            logger.info("Pausing live acquisition...")
            self.data_mgr.pause_acquisition()
        else:
            logger.info("Resuming live acquisition...")
            self.data_mgr.resume_acquisition()

    def _on_acquisition_started(self):
        """Live data acquisition has started - enable record and pause buttons."""
        self.acquisition_events.on_acquisition_started()

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
        logger.debug("Reset experiment_start_time for new acquisition")

        # Clear data buffers for fresh start
        self.buffer_mgr.clear_all()
        logger.debug("Cleared all data buffers")

        # Clear any pause/resume markers from previous runs (with thread safety)
        try:
            if hasattr(self.main_window, "pause_markers") and hasattr(
                self.main_window,
                "full_timeline_graph",
            ):
                # Schedule marker removal in main thread (Qt objects must be accessed from main thread)

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
        self.acquisition_events.on_acquisition_stopped()
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
            logger.info("Stopping recording due to acquisition stop...")
            self.recording_mgr.stop_recording()

    # === Kinetic Operations Callbacks ===

    def _on_pump_initialized(self):
        """Pump initialized successfully."""
        logger.debug("✓ Pump initialized")
        # TODO: Enable pump controls in UI

    def _on_pump_error(self, error: str):
        """Pump error occurred."""
        logger.error(f"Pump error: {error}")
        from affilabs.widgets.message import show_message

        show_message(error, "Pump Error")

    def _on_pump_state_changed(self, state: dict):
        """Pump state changed."""
        self.peripheral_events.on_pump_state_changed(state)

    def _on_valve_switched(self, valve_info: dict):
        """Valve position changed."""
        self.peripheral_events.on_valve_switched(valve_info)

    def _cleanup_resources(self, emergency: bool = False):
        """Consolidated cleanup logic for all shutdown paths."""
        from affilabs.utils.resource_helpers import ResourceHelpers

        ResourceHelpers.cleanup_resources(self, emergency)

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

        # Don't trigger for intentional disconnects
        if hasattr(self, "_intentional_disconnect") and self._intentional_disconnect:
            return  # Intentional disconnect, not an emergency

        logger.warning(
            "Emergency cleanup triggered - forcing resource release",
        )

        # Force close all hardware connections without waiting
        self._cleanup_resources(emergency=True)

    def __del__(self):
        """Destructor to ensure resources are cleaned up."""
        try:
            if not hasattr(self, "closing") or not self.closing:
                logger.warning(
                    "__del__ called without proper close - forcing cleanup",
                )
                self._cleanup_resources(emergency=True)
        except Exception:
            pass  # Destructor should never raise

    # === PHASE 1.4 HAL HELPER METHODS ===

    def get_hal_controller(self) -> IController | None:
        """Get HAL controller interface if available.

        Returns:
            IController instance or None if HAL not available

        """
        if HAL_AVAILABLE and self.device_manager:
            return self.device_manager.get_controller()
        return None

    def get_hal_spectrometer(self) -> ISpectrometer | None:
        """Get HAL spectrometer interface if available.

        Returns:
            ISpectrometer instance or None if HAL not available

        """
        if HAL_AVAILABLE and self.device_manager:
            return self.device_manager.get_spectrometer()
        return None

    def get_hal_servo(self) -> IServo | None:
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
                "HAL not available, cannot connect via DeviceManager",
            )
            return False

        try:
            logger.info("Connecting devices via HAL DeviceManager...")
            success = self.device_manager.connect_all(
                require_controller=require_controller,
                require_spectrometer=require_spectrometer,
                require_servo=require_servo,
            )

            if success:
                logger.debug("✓ HAL devices connected")
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
            logger.info("Disconnecting HAL devices...")
            # Stop auto-reconnect
            self.device_status_vm.stop_auto_reconnect()
            # Disconnect all
            self.device_manager.disconnect_all()
            logger.debug("✓ HAL devices disconnected")
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
            # Register controller if available (already a HAL)
            if (
                hasattr(self, "hardware_mgr")
                and self.hardware_mgr
                and self.hardware_mgr.ctrl
            ):
                # hardware_mgr.ctrl is already a HAL created by create_controller_hal()
                self.device_manager.register_controller(self.hardware_mgr.ctrl)
                logger.debug("✓ Controller HAL registered")

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
                logger.debug("✓ Legacy spectrometer registered")

            # Note: Servo is managed separately, could add servo adapter here

        except Exception as e:
            logger.warning(
                f"Could not register legacy devices with HAL: {e}",
            )

    # === END PHASE 1.4 HAL METHODS ===

    # === Graphic Control Callbacks ===

    def _on_grid_toggled(self, checked: bool):
        """Grid checkbox toggled."""
        logger.info(f"Grid toggled: {checked}")
        self.main_window.cycle_of_interest_graph.showGrid(x=checked, y=checked)

    def _on_autoscale_toggled(self, checked: bool):
        """Autoscale radio button toggled."""
        pass  # graph_events removed

    def _on_manual_scale_toggled(self, checked: bool):
        """Manual radio button toggled."""
        pass  # graph_events removed

    def _on_manual_range_changed(self):
        """Manual range input values changed."""
        pass  # graph_events removed

    def _on_axis_selected(self, checked: bool):
        """Axis selector button toggled."""
        pass  # graph_events removed

    def _on_filter_toggled(self, checked: bool):
        """Data filtering checkbox toggled."""
        pass  # graph_events removed

    def _on_filter_strength_changed(self, value: int):
        """Filter strength slider changed."""
        self.ui_control_events.on_filter_strength_changed(value)

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
        """Apply incremental median filtering for real-time display."""
        from affilabs.utils.data_processing_helpers import DataProcessingHelpers

        return DataProcessingHelpers.apply_online_smoothing(self, data, strength, channel)

    def _redraw_timeline_graph(self):
        """Redraw the full timeline graph with current filter settings."""
        from affilabs.utils.data_processing_helpers import DataProcessingHelpers

        DataProcessingHelpers.redraw_timeline_graph(self)

    def _on_reference_changed(self, text: str):
        """Reference channel selection changed."""
        self.ui_control_events.on_reference_changed(text)

    def _apply_reference_subtraction(self):
        """Apply reference channel subtraction to all other channels."""
        from affilabs.utils.graph_helpers import GraphHelpers

        GraphHelpers.apply_reference_subtraction(self)

    def _reset_channel_style(self, ch_idx: int):
        """Reset channel curve to standard or colorblind style."""
        from affilabs.utils.graph_helpers import GraphHelpers

        GraphHelpers.reset_channel_style(self, ch_idx)

    def _on_graph_clicked(self, event):
        """Handle mouse clicks on cycle_of_interest_graph.

        Left click: Select channel closest to cursor
        Right click: Add flag/annotation at cursor position for selected channel
        """
        pass  # graph_events removed

    def _select_nearest_channel(self, click_time: float, click_value: float):
        """Select the channel whose curve is nearest to the click position."""
        pass  # graph_events removed

    def _add_flag(self, channel: int, time: float, annotation: str):
        """Add a flag marker to the graph and save to table."""
        pass  # graph_events removed

    def _update_cycle_data_table(self):
        """Update the Flags column in cycle data table with flag information."""
        self.graph_events.update_cycle_data_table()

    def _on_polarizer_toggle(self):
        """Toggle between S and P polarizer positions."""
        if self.hardware_mgr and self.hardware_mgr.ctrl:
            # Determine current position and toggle
            current_pos = getattr(self.hardware_mgr, "_current_polarizer", "s")
            new_pos = "p" if current_pos == "s" else "s"

            logger.info(
                f"Toggling polarizer from {current_pos.upper()} to {new_pos.upper()}",
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
                            f"[OK] Position validation: {new_pos.upper()}-mode target={target_pos} (from device_config)",
                        )
                    else:
                        logger.warning(
                            "Cannot validate positions - not found in device_config",
                        )
                else:
                    logger.warning(
                        "Cannot validate positions - device_config not available",
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

            # LED timing now built into hardware commands - no explicit delays needed

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

                # Polarizer positions are IMMUTABLE - set at controller initialization
                # DO NOT apply servo_set() - positions come from device_config at startup
                logger.info(
                    f"   Polarizer positions locked (from device_config at init): S={s_pos}, P={p_pos}",
                )

                # Set LED intensities (applies immediately to hardware)
                self.hardware_mgr.ctrl.set_intensity("a", led_a)
                self.hardware_mgr.ctrl.set_intensity("b", led_b)
                self.hardware_mgr.ctrl.set_intensity("c", led_c)
                self.hardware_mgr.ctrl.set_intensity("d", led_d)

                # LED timing now built into hardware commands - no explicit delays needed

                # Save servo positions and LED intensities to device config file
                # The device config file is provided by OEM with factory positions
                if self.main_window.device_config:
                    logger.info("Γëí╞Æ├åΓò¢ Saving settings to device config file...")
                    self.main_window.device_config.set_servo_positions(s_pos, p_pos)
                    self.main_window.device_config.set_led_intensities(
                        led_a,
                        led_b,
                        led_c,
                        led_d,
                    )
                    self.main_window.device_config.save()
                    logger.info(
                        "[OK] Settings saved to device config file",
                    )
                else:
                    logger.warning(
                        "Device config not available - settings not saved",
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
        self.ui_control_events.on_unit_changed(checked)

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
        self.recording_events.on_record_baseline_clicked()

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
            "≡ƒôè Baseline recording started - button updated to 'Stop Recording'",
        )

    def _on_recording_progress(self, progress: dict):
        """Handle baseline recording progress update.

        Args:
            progress: Dict with 'elapsed', 'remaining', 'count', 'percent' keys

        """
        self.recording_events.on_baseline_recording_progress(progress)

    def _on_recording_complete(self, filepath: str):
        """Handle baseline recording complete signal.

        Args:
            filepath: Path to saved recording file

        """
        self.recording_events.on_baseline_recording_complete(filepath)

    def _on_recording_error(self, error_msg: str):
        """Handle baseline recording error signal.

        Args:
            error_msg: Error description

        """
        self.recording_events.on_baseline_recording_error(error_msg)

    def _on_power_on_requested(self):
        """User requested to power on (connect hardware)."""
        try:
            logger.info("Power ON: Scanning for hardware...")

            # Set to searching state
            logger.debug("Setting power button to 'searching' state...")
            self.main_window.set_power_state("searching")
            logger.debug("Power button state updated")

            # Start hardware scan and connection
            logger.debug("Calling hardware_mgr.scan_and_connect()...")
            self.hardware_mgr.scan_and_connect()
            logger.debug(
                "scan_and_connect() call completed (scanning in background thread)",
            )
        except Exception as e:
            logger.exception(f"ERROR in _on_power_on_requested: {e}")
            from affilabs.widgets.message import show_message

            show_message(
                f"Failed to start hardware scan: {e}",
                "Error",
                parent=self.main_window,
            )
            # Reset power button to disconnected state
            try:
                self.main_window.set_power_state("disconnected")
            except Exception:
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
                self._intentional_disconnect = (
                    True  # Mark as intentional before disconnect
                )
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
            from affilabs.widgets.message import show_message

            show_message(f"Power off completed with errors: {e}", "Warning")

    def _on_recording_start_requested(self):
        """User requested to start recording."""
        logger.info(
            "[RECORD-HANDLER] Recording start requested by user (button clicked)",
        )

        # Show file dialog to select recording location
        # Get default filename with timestamp

        from PySide6.QtWidgets import QFileDialog

        from affilabs.utils.time_utils import for_filename

        timestamp = for_filename().replace(".", "_")
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
                f"📋 [RECORD-HANDLER] Export fields populated: {filename} in {directory}",
            )
        else:
            # User cancelled - revert button state
            logger.info(
                "[RECORD-HANDLER] User cancelled file dialog - reverting button state",
            )
            self.main_window.record_btn.setChecked(False)

    def _on_recording_stop_requested(self):
        """User requested to stop recording."""
        logger.info("Recording stop requested...")

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
        self.peripheral_events.on_pipeline_changed(pipeline_id)

    # ==================== End Timeframe Mode Handlers ====================

    def _update_device_status_ui(self, status: dict):
        """Update Device Status UI with hardware information.

        Args:
            status: Hardware status dict from HardwareManager

        """
        logger.debug("Updating Device Status UI via ViewModel...")

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
        spec = "✓" if status.get("spectrometer") else "✗"
        knx = status.get("knx_type", "None")
        pump = "✓" if status.get("pump_connected") else "✗"
        sensor = "✓" if status.get("sensor_ready") else "✗"
        optics = "✓" if status.get("optics_ready") else "✗"
        fluids = "✓" if status.get("fluidics_ready") else "✗"
        logger.debug(
            f"Hardware: {ctrl} | Spec:{spec} KNX:{knx} Pump:{pump} | Sensor:{sensor} Optics:{optics} Fluids:{fluids}",
        )

    # === VIEWMODEL SIGNAL HANDLERS (Phase 1.3+1.4 Integration) ===

    def _on_vm_device_connected(self, device_type: str, serial_number: str):
        """Handle device_connected signal from DeviceStatusViewModel.

        Args:
            device_type: Type of device ('controller', 'spectrometer', etc.)
            serial_number: Device serial number

        """
        logger.info(
            f"[ViewModel] Device connected: {device_type} (S/N: {serial_number})",
        )
        # UI updates are handled by the main window's direct connection to hardware_mgr
        # This is here for future enhancements (e.g., notifications, logging)

    def _on_vm_device_disconnected(self, device_type: str):
        """Handle device_disconnected signal from DeviceStatusViewModel.

        Args:
            device_type: Type of device that disconnected

        """
        logger.info(f"[ViewModel] Device disconnected: {device_type}")
        # Future: Could show notification or update status indicators

    def _on_vm_device_error(self, device_type: str, error_message: str):
        """Handle device_error signal from DeviceStatusViewModel.

        Args:
            device_type: Type of device with error
            error_message: Error description

        """
        logger.warning(
            f"[ViewModel] Device error - {device_type}: {error_message}",
        )
        # Future: Could show error notification or update error indicators

    def _on_vm_status_changed(self, all_connected: bool, all_healthy: bool):
        """Handle overall_status_changed signal from DeviceStatusViewModel.

        Args:
            all_connected: True if all required devices are connected
            all_healthy: True if all devices are healthy (no errors)

        """
        if hasattr(self, 'peripheral_events') and self.peripheral_events:
            self.peripheral_events.on_vm_status_changed(all_connected, all_healthy)

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
        # Update via UI coordinator if available
        if hasattr(self, 'ui_updates') and self.ui_updates is not None:
            self.ui_updates.queue_transmission_update(
                channel,
                wavelengths,
                transmission,
                None,
            )
        # Fallback: Update spectroscopy presenter directly
        elif hasattr(self, 'spectroscopy_presenter') and self.spectroscopy_presenter is not None:
            try:
                self.spectroscopy_presenter.update_transmission_spectrum(
                    channel,
                    wavelengths,
                    transmission,
                )
            except Exception as e:
                logger.error(f"Failed to update transmission spectrum: {e}")
        
        logger.debug(f"[ViewModel] Spectrum updated for channel {channel}")

    def _on_peak_updated(
        self,
        channel: str,
        peak_wavelength: float,
        metadata: dict,
    ):
        """Handle peak_updated signal from SpectrumViewModel.

        Updates the most recent spectrum data dict with the pipeline-calculated
        resonance wavelength so it flows to the sensorgram.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            peak_wavelength: Resonance wavelength in nm (from pipeline)
            metadata: Pipeline metadata (name, timing, etc.)

        """
        # Store peak for next buffer append
        if not hasattr(self, '_latest_peaks'):
            self._latest_peaks = {}
        self._latest_peaks[channel] = peak_wavelength

        logger.debug(
            f"[Peak] Channel {channel}: {peak_wavelength:.2f} nm "
            f"(pipeline: {metadata.get('pipeline_id', 'unknown')})"
        )

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
        # DIRECT UPDATE - don't queue, update immediately
        # Timer-based updates weren't firing during heavy acquisition load
        try:
            if hasattr(self, 'ui_updates') and self.ui_updates is not None:
                if self.ui_updates.spectroscopy_presenter and self.ui_updates._raw_spectrum_updates_enabled:
                    self.ui_updates.spectroscopy_presenter.update_raw_spectrum(
                        channel,
                        wavelengths,
                        raw_spectrum,
                    )
            # Fallback: Update spectroscopy presenter directly
            elif hasattr(self, 'spectroscopy_presenter') and self.spectroscopy_presenter is not None:
                self.spectroscopy_presenter.update_raw_spectrum(
                    channel,
                    wavelengths,
                    raw_spectrum,
                )
        except Exception as e:
            logger.exception(f"Error updating raw spectrum for {channel}: {e}")

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
                timestamp=data.get("timestamp", monotonic()),
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
        logger.info("[CalibrationViewModel] Calibration started")
        # Future: Update UI to show calibration in progress

    def _on_cal_vm_progress(self, percent: int, message: str):
        """Handle calibration_progress signal from CalibrationViewModel.

        Args:
            percent: Progress percentage (0-100)
            message: Status message

        """
        logger.info(
            f"[CalibrationViewModel] Progress: {percent}% - {message}",
        )
        # Future: Update progress bar in UI

    def _on_cal_vm_complete(self, calibration_data: dict):
        """Handle calibration_complete signal from CalibrationViewModel.

        Args:
            calibration_data: Calibration data dictionary

        """
        logger.info("[CalibrationViewModel] Calibration complete")
        # Future: Display success message, enable acquisition

    def _on_cal_vm_failed(self, error_message: str):
        """Handle calibration_failed signal from CalibrationViewModel.

        Args:
            error_message: Error description

        """
        logger.error(
            f"[CalibrationViewModel] Calibration failed: {error_message}",
        )
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
            f"[CalibrationViewModel] Validation: {'PASSED' if passed else 'FAILED'} "
            f"({errors} errors, {warnings} warnings)",
        )
        # Future: Display validation report in UI

    def _load_device_settings(self):
        """Load servo positions from device config file and populate UI."""
        from affilabs.utils.settings_helpers import SettingsHelpers

        SettingsHelpers.load_device_settings(self)

    def _run_servo_auto_calibration(self):
        """Delegate to calibration service."""
        self.calibration.start_calibration()

    def _update_led_intensities_for_integration_time(
        self,
        integration_time_ms: float,
        polarization: str = "P",
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
                "Dynamic LED intensity update not implemented (using static config values)",
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
                f"LED intensities updated in UI: A={led_a}, B={led_b}, C={led_c}, D={led_d}",
            )

        except Exception as e:
            logger.error(f"Failed to update LED intensities in UI: {e}")

    def _on_quick_export_csv(self):
        """Quick export cycle of interest data to CSV file."""
        from affilabs.utils.export_helpers import ExportHelpers

        ExportHelpers.quick_export_csv(self)

    def _do_deferred_autosave(self):
        """Execute pending autosave operation after delay to avoid USB conflicts."""
        if hasattr(self, "_pending_autosave") and self._pending_autosave is not None:
            start_time, stop_time = self._pending_autosave
            self._pending_autosave = None
            self._autosave_cycle_data(start_time, stop_time)

    def _autosave_cycle_data(self, start_time: float, stop_time: float):
        """Automatically save cycle data to session folder."""
        from affilabs.utils.export_helpers import ExportHelpers

        ExportHelpers.autosave_cycle_data(self, start_time, stop_time)

    def _on_export_requested(self, config: dict):
        """Handle comprehensive export request from Export tab."""
        from affilabs.utils.export_helpers import ExportHelpers

        ExportHelpers.export_requested(self, config)

    def _on_quick_export_image(self):
        """Quick export cycle of interest graph as image with metadata."""
        from affilabs.utils.export_helpers import ExportHelpers

        ExportHelpers.quick_export_image(self)

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
        # Handle KeyboardInterrupt (Ctrl+C) gracefully - this is normal shutdown
        if exc_type is KeyboardInterrupt:
            logger.info("=" * 80)
            logger.info("🛑 Application shutdown requested (Ctrl+C)")
            logger.info("=" * 80)
            # Exit gracefully without stack trace
            sys.exit(0)
            return

        # For actual crashes, log detailed information
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
    logger.info("="*70)
    logger.info(f"AffiLabs.core {SW_VERSION.split()[1]} | {dtnow.strftime('%Y-%m-%d %H:%M')}")
    logger.info("="*70)

    # Install emergency cleanup on exit
    def emergency_silence():
        """Silence all output during final cleanup to prevent I/O errors."""
        try:
            null = NullWriter()
            sys.stderr = null
            sys.stdout = null
        except Exception:
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

    logger.info("Ready | Starting application")
    exit_code = app.exec()

    # Restore original stderr
    sys.stderr = original_stderr
    sys.stdout = original_stdout

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
