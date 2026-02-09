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
import time
import warnings
from pathlib import Path

# ============================================================================
# SECTION 2: Exception and Warning Filters (BEFORE Qt imports)
# ============================================================================
# These filters suppress false-positive Qt threading warnings that occur when
# using queue-based architecture. MUST be installed before importing Qt.

# Centralized helpers for environment flags and Qt message suppression
def _env_flag(name: str, default: bool = False) -> bool:
    """Parse boolean-like environment variables safely.

    Accepts 1/0, true/false, yes/no, on/off (case-insensitive).
    """
    val = os.environ.get(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


QT_SUPPRESSED_SUBSTRINGS = (
    # General Qt threading false-positives
    "QTextDocument",
    "different thread",
    "parent's thread is QThread",
    "parent that is in a different thread",
    # Object creation warnings that are benign in our architecture
    "QObject: Cannot create children",
    # Font warnings from auto-generated UI files (Qt Designer quirk)
    "QFont::setPointSize: Point size <= 0",
    "QLayout::addChildLayout: layout",
)


def _is_suppressed_qt_text(text: str) -> bool:
    try:
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="replace")
        else:
            text = str(text)
    except Exception:
        return False
    return any(sub in text for sub in QT_SUPPRESSED_SUBSTRINGS)


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

    SUPPRESSED_PATTERNS = QT_SUPPRESSED_SUBSTRINGS

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
            if _is_suppressed_qt_text(text):
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
if not _env_flag("AFFILABS_VERBOSE_QT", default=False):
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
from PySide6.QtCore import Qt, QTimer, QtMsgType, Signal, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

from affilabs.ui.ui_message import error as ui_error
from affilabs.ui.ui_message import info as ui_info
from affilabs.ui_styles import Colors
from affilabs.utils.time_utils import monotonic


# --- Qt Message Handler (suppresses threading warnings) ---
def qt_message_handler(msg_type, context, message):
    """Qt message handler that filters false-positive threading warnings."""
    # Suppress known false-positives
    if _is_suppressed_qt_text(message):
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


# ============================================================================
# SECTION 5: Application Imports (Organized by Architecture Layer)
# ============================================================================

# Layer 4: UI/Widgets
from affilabs.affilabs_core_ui import AffilabsMainWindow

# Layer 3: Coordinators (Orchestration)
from affilabs.core.calibration_service import CalibrationService
from affilabs.core.cycle_coordinator import CycleCoordinator

# Domain Models
from affilabs.domain.cycle import Cycle

# Layer 2: Core Business Logic (Managers)
from affilabs.core.data_acquisition_manager import DataAcquisitionManager
from affilabs.core.data_buffer_manager import DataBufferManager
from affilabs.managers.flag_manager import FlagManager
from affilabs.managers.segment_manager import SegmentManager

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
from affilabs.services import TransmissionCalculator

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

        # Set application icon for taskbar
        from PySide6.QtGui import QIcon
        icon_path = Path(__file__).parent / "affilabs" / "ui" / "img" / "affinite2.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Install Qt message handler to suppress harmless warnings
        qInstallMessageHandler(qt_message_handler)

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
                logger.critical("Critical initialization failed")
                raise SystemExit(1)
            logger.warning(f"[{phase}] Non-critical error, continuing")

    def _sidebar_widget(self, name: str):
        """Get a sidebar widget by name, or None if it doesn't exist."""
        return getattr(self.main_window.sidebar, name, None)

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
        self._display_time_offset = 0.0  # Offset between real time and displayed time (graph skips first point)
        self._last_cycle_bounds = None
        self._session_cycles_dir = None
        self._session_epoch = 0  # Increments on clear to invalidate old data
        self.current_experiment_folder = None  # Path to active experiment folder (GLP/GMP structure)

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
        self._selected_flag_channel = 'a'  # Default channel for flag placement (used by UI)

        # Flag system - legacy storage (for backward compatibility)
        # NOTE: Flag logic now delegated to FlagManager

        # Channel time shifts for injection alignment (Phase 2)
        self._channel_time_shifts = {'a': 0.0, 'b': 0.0, 'c': 0.0, 'd': 0.0}

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

        # Baseline data recording
        self._baseline_recorder = None

        # Analysis window (created on demand)
        self.analysis_window = None

        # Next cycle warning line for active cycle graph
        self._next_cycle_warning_line = None

        # Internal pump state tracking (P4PROPLUS)
        self._pump1_running = False
        self._pump2_running = False
        self._synced_pumps_running = False

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

        # Data buffer manager (must be before RecordingManager)
        self.buffer_mgr = DataBufferManager()
        if self.buffer_mgr is None:
            raise RuntimeError("DataBufferManager initialization failed")

        # Recording manager
        self.recording_mgr = RecordingManager(self.data_mgr, self.buffer_mgr)
        if self.recording_mgr is None:
            raise RuntimeError("RecordingManager initialization failed")

        # Flag manager (must be after main_window is created)
        # Will be initialized in _init_coordinators() phase

        # Kinetic operations manager
        self.kinetic_mgr = KineticManager(self.hardware_mgr)
        if self.kinetic_mgr is None:
            raise RuntimeError("KineticManager initialization failed")

        # Pump operations manager
        from affilabs.managers import PumpManager
        from affilabs.managers.pump_manager import PumpOperation

        self.pump_mgr = PumpManager(self.hardware_mgr)
        self.PumpOperation = PumpOperation  # Store for handler access
        if self.pump_mgr is None:
            raise RuntimeError("PumpManager initialization failed")

        # Session quality monitor
        self.quality_monitor = SessionQualityMonitor(
            device_serial="unknown",
            session_id=None,
        )
        if self.quality_monitor is None:
            raise RuntimeError("SessionQualityMonitor initialization failed")

        # ====================================================================
        # QUEUE ARCHITECTURE (New - Refactored)
        # ====================================================================
        # Initialize new queue presenter (MVP pattern with undo/redo)
        from affilabs.presenters.queue_presenter import QueuePresenter
        self.queue_presenter = QueuePresenter(max_history=50)
        logger.debug("✓ QueuePresenter initialized (with undo/redo support)")

        # Initialize cycle template storage
        from affilabs.services.cycle_template_storage import CycleTemplateStorage
        self.template_storage = CycleTemplateStorage()
        logger.debug("✓ CycleTemplateStorage initialized")

        from affilabs.services.queue_preset_storage import QueuePresetStorage
        self.preset_storage = QueuePresetStorage()
        logger.debug("✓ QueuePresetStorage initialized")

        # Backward compatibility: Keep segment_queue attribute
        # (populated from presenter's queue snapshot)
        self.segment_queue = []  # Will be synced with presenter
        logger.debug("Segment queue initialized (TEST MODE)")

        logger.debug("✓ Managers")

    def _init_services(self):
        """Initialize business services (pure logic, no UI).

        Creates high-level services that orchestrate business logic.
        Services may depend on managers but not on UI components.

        Raises:
            Exception: If any critical service fails to initialize

        """
        # License and feature flags system
        from affilabs.config.license_manager import LicenseManager

        self.license_mgr = LicenseManager()
        self.features = self.license_mgr.load_license()

        license_info = self.license_mgr.get_license_info()
        logger.info(f"✓ License: {license_info['tier_name']} tier")
        if not license_info['is_valid'] and license_info.get('errors'):
            logger.warning(f"License validation issues: {', '.join(license_info['errors'])}")

        # Experiment folder manager for GLP/GMP-compliant file organization
        from affilabs.utils.experiment_folder_manager import ExperimentFolderManager
        self.experiment_folder_mgr = ExperimentFolderManager()
        logger.debug("✓ ExperimentFolderManager")

        # Phase 1.2 business services
        self.transmission_calc = TransmissionCalculator()
        if self.transmission_calc is None:
            raise RuntimeError("TransmissionCalculator initialization failed")

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

        # Give sidebar access to app for _completed_cycles
        if hasattr(self.main_window, 'sidebar'):
            self.main_window.sidebar.app = self

        # Wire up elapsed time getter for pause markers
        def get_elapsed_time():
            if self.experiment_start_time is None:
                return None
            return monotonic() - self.experiment_start_time

        self.main_window._get_elapsed_time = get_elapsed_time

        # Store app reference for CalibrationManager to access calibration methods
        self.main_window.app = self
        # All UI→App communication happens through Qt signals

        # Set default export path in sidebar
        if hasattr(self.main_window, 'sidebar') and (w := self._sidebar_widget('export_dest_input')):
            default_path = str(self.recording_mgr.output_directory)
            w.setText(default_path)
            w.setPlaceholderText(default_path)
            logger.debug(f"✓ Export path initialized: {default_path}")

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

        # Initialize Flag Manager (requires main_window to exist)
        self.flag_mgr = FlagManager(self)
        logger.debug("✓ FlagManager")

        # Initialize Segment Manager for multi-cycle analysis
        self.segment_mgr = SegmentManager(self)
        logger.debug("✓ SegmentManager")

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

        # Cycle management system (simple, safe implementation)
        self._current_cycle: Cycle | None = None  # Currently running cycle (Cycle dataclass)
        self._cycle_end_time = None  # Exact time when cycle should end
        self._completed_cycles: list[Cycle] = []  # List of completed Cycle instances
        self._cycle_markers = {}  # Track cycle markers on Full Sensorgram timeline
        self._cycle_timer = QTimer()
        self._cycle_timer.timeout.connect(self._update_cycle_display)
        self._cycle_end_timer = QTimer()  # Fires once when cycle duration expires
        self._cycle_end_timer.setSingleShot(True)
        self._cycle_end_timer.timeout.connect(self._on_cycle_completed)
        self._cycle_counter = 0  # Global counter for permanent cycle IDs (never decreases)
        logger.debug("✓ Cycle management initialized")

        # Auto-read after queue setting
        self._auto_read_after_queue = True  # Default: auto-start monitoring when queue finishes

        # Plunger position polling timer (5 second interval)
        self._plunger_poll_timer = QTimer()
        self._plunger_poll_timer.timeout.connect(self._poll_plunger_position)
        self._plunger_poll_timer.setInterval(5000)  # 5 seconds
        # Timer will start when pump is detected
        logger.debug("✓ Plunger polling timer initialized")

        # Valve position polling timer (3 second interval)
        self._valve_poll_timer = QTimer()
        self._valve_poll_timer.timeout.connect(self._poll_valve_positions)
        self._valve_poll_timer.setInterval(3000)  # 3 seconds
        # Timer will start when controller is detected
        logger.debug("✓ Valve polling timer initialized")

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
            logger.debug("✓ Cursor update signal connected")

            # Connect polarizer toggle button to servo control
            if hasattr(self.main_window, "polarizer_toggle_btn"):
                self.main_window.polarizer_toggle_btn.clicked.connect(
                    self._on_polarizer_toggle_clicked,
                )
                logger.debug("✓ Polarizer toggle")

            # Connect mouse events for channel selection and flagging
            if hasattr(self.main_window, "cycle_of_interest_graph"):
                # Disable default PyQtGraph context menu (conflicts with flag system)
                self.main_window.cycle_of_interest_graph.setMenuEnabled(False)

                self.main_window.cycle_of_interest_graph.scene().sigMouseClicked.connect(
                    self._on_graph_clicked,
                )
                logger.debug("✓ Graph click events")

            # Mark deferred loading as complete
            self._deferred_connections_pending = False

            # Now connect UI button/control signals (after graphs are loaded)
            self._connect_ui_signals()
            logger.debug("✓ UI control signals")

            # Connect new queue widgets to presenter (Phase 6)
            self._connect_queue_widgets()
            logger.debug("✓ Queue widgets connected to presenter")

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
        self.hardware_mgr.servo_calibration_needed.connect(
            self._on_servo_calibration_needed,
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

        # Resume live spectrum updates after calibration
        if hasattr(self, 'ui_updates') and self.ui_updates is not None:
            logger.info("Resuming live spectrum updates after calibration...")
            self.ui_updates.set_transmission_updates_enabled(True)
            self.ui_updates.set_raw_spectrum_updates_enabled(True)

        SettingsHelpers.on_calibration_complete(self, calibration_data)

        # Set LED intensities once after calibration (fixed for entire run)
        if hasattr(self, 'hardware_mgr') and self.hardware_mgr and hasattr(self.hardware_mgr, 'ctrl'):
            try:
                intensities = calibration_data.p_mode_intensities
                logger.info(f"Setting LED intensities (fixed for run): A={intensities.get('a', 0)}, B={intensities.get('b', 0)}, C={intensities.get('c', 0)}, D={intensities.get('d', 0)}")
                self.hardware_mgr.ctrl.set_batch_intensities(
                    a=int(intensities.get('a', 0)),
                    b=int(intensities.get('b', 0)),
                    c=int(intensities.get('c', 0)),
                    d=int(intensities.get('d', 0))
                )
                logger.info("✓ LED intensities configured - will not change during run")
            except Exception as e:
                logger.warning(f"Could not set LED intensities: {e}")

        # Show QC dialog with calibration results
        self._show_qc_dialog(calibration_data)

        # Automatically log calibration to database for ML training
        self._log_calibration_to_database(calibration_data)

        # Populate LED brightness in Hardware Configuration section
        logger.info("📋 Populating calibration settings in UI...")
        try:
            if hasattr(self.main_window, '_load_current_settings'):
                self.main_window._load_current_settings(show_warnings=False)
                logger.info("   ✓ LED brightness populated in Hardware Configuration")
            else:
                logger.warning("   _load_current_settings method not found on main_window")
        except Exception as e:
            logger.warning(f"   Could not populate settings: {e}")

        # Clear graph and resume live data after OEM calibration
        logger.info("📊 Clearing graph and resuming live data after calibration...")

        # Clear the graph
        if hasattr(self, 'graph') and self.graph:
            self.graph.clear_plot()
            logger.info("   Graph cleared")

        # Resume live acquisition if hardware is ready
        if hasattr(self, 'hardware_mgr') and self.hardware_mgr:
            try:
                # Use data_mgr to start live data
                if hasattr(self, 'data_mgr') and self.data_mgr:
                    self.data_mgr.start_acquisition()
                    logger.info("   Live acquisition started")
                else:
                    logger.warning("   Data acquisition manager not available")
            except Exception as e:
                logger.warning(f"   Could not start live acquisition: {e}")

        logger.info("✓ Post-calibration cleanup complete")

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

            # Use static method to show QC dialog (ensures proper modal behavior and pre-export)
            self._qc_dialog = CalibrationQCDialog.show_qc_report(
                parent=self.main_window,
                calibration_data=qc_data,
            )

            logger.info("QC report displayed and closed (modal)")

            # Turn off all LEDs after QC report
            if hasattr(self, 'hardware_mgr') and self.hardware_mgr and hasattr(self.hardware_mgr, 'ctrl'):
                try:
                    self.hardware_mgr.ctrl.turn_off_channels()
                    logger.info("✓ All LEDs turned off after calibration QC report")
                except Exception as led_error:
                    logger.warning(f"Failed to turn off LEDs: {led_error}")

            logger.info("System ready - Click START button to begin live acquisition")

        except Exception as e:
            logger.error(f"[X] Failed to show QC report: {e}", exc_info=True)

    def open_analysis_window(self):
        """Open the data analysis window for post-processing."""
        try:
            from affilabs.widgets.analysis import AnalysisWindow

            # Create window if it doesn't exist
            if self.analysis_window is None:
                self.analysis_window = AnalysisWindow(recording_mgr=self.recording_mgr)
                self.analysis_window.setWindowTitle("AffiLabs Data Analysis")
                logger.info("✓ Analysis window created")

            # Show the window
            self.analysis_window.show()
            self.analysis_window.raise_()
            self.analysis_window.activateWindow()
            logger.info("Analysis window opened")

        except Exception as e:
            logger.error(f"Failed to open analysis window: {e}", exc_info=True)

    def _connect_queue_widgets(self):
        """Connect new queue widgets (QueueSummaryWidget and QueueToolbar) to presenter."""
        if not hasattr(self.main_window, 'sidebar'):
            logger.warning("No sidebar found - skipping queue widget connections")
            return

        sidebar = self.main_window.sidebar

        # Connect QueueSummaryWidget to presenter
        if hasattr(sidebar, 'summary_table'):
            sidebar.summary_table.set_presenter(self.queue_presenter)
            logger.info("✓ QueueSummaryWidget connected to presenter")

            # Connect widget signals for operations
            sidebar.summary_table.cycle_reordered.connect(
                lambda from_idx, to_idx: self.queue_presenter.reorder_cycle(from_idx, to_idx)
            )
            sidebar.summary_table.cycles_deleted.connect(
                lambda indices: self.queue_presenter.delete_cycles(indices) if indices else None
            )
            logger.debug("✓ QueueSummaryWidget drag-drop and delete signals connected")

        # Timeline widget is now in popup dialog (not in sidebar)
        # Connection handled in _open_timeline_dialog when dialog is opened

        # Connect presenter signals for auto-refresh (replaces manual _update_summary_table calls)
        self.queue_presenter.queue_changed.connect(self._on_queue_changed)
        logger.info("✓ Queue auto-refresh enabled (presenter.queue_changed signal)")

        # Connect Start Queued Run button
        if hasattr(sidebar, 'queued_run_started'):
            sidebar.queued_run_started.connect(self._on_start_queued_run)
            logger.info("✓ Start Queued Run button connected")

        # Connect Next Cycle button
        if hasattr(sidebar, 'next_cycle_requested'):
            sidebar.next_cycle_requested.connect(self._on_next_cycle)
            logger.info("✓ Next Cycle button connected")

        # Connect Clear Queue button (sidebar signal path)
        if hasattr(sidebar, 'queue_cleared'):
            sidebar.queue_cleared.connect(self._confirm_clear_queue)
            logger.info("✓ Clear Queue button connected")

    def _delete_selected_cycles(self):
        """Delete selected cycles from queue (called by toolbar Delete button)."""
        if not (tbl := self._sidebar_widget('summary_table')):
            return

        selected_indices = tbl.get_selected_indices()
        if not selected_indices:
            logger.info("No cycles selected for deletion")
            return

        from PySide6.QtWidgets import QMessageBox
        count = len(selected_indices)
        reply = QMessageBox.question(
            self.main_window,
            "Delete Cycles",
            f"Delete {count} selected {'cycle' if count == 1 else 'cycles'}?\n\nYou can undo this with Ctrl+Z.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            success = self.queue_presenter.delete_cycles(selected_indices)
            if success:
                self.segment_queue = self.queue_presenter.get_queue_snapshot()
                logger.info(f"🗑️ Deleted {count} cycles from queue")

    def _confirm_clear_queue(self):
        """Clear entire queue with confirmation (called by toolbar Clear All button)."""
        if self.queue_presenter.get_queue_size() == 0:
            logger.info("Queue is already empty")
            return

        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self.main_window,
            "Clear Queue",
            f"Clear all {self.queue_presenter.get_queue_size()} cycles from queue?\n\nYou can undo this with Ctrl+Z.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.queue_presenter.clear_queue()
            self.segment_queue = self.queue_presenter.get_queue_snapshot()
            logger.info("🗑️ Queue cleared")

            # Reset method name to default
            if method_label := self._sidebar_widget('method_name_label'):
                method_label.setText("Untitled Method")

    def _on_queue_changed(self):
        """Handle queue changes - update UI elements that don't auto-refresh.

        Summary table auto-refreshes via presenter.queue_changed signal.
        This handler updates:
        - Progress bar
        - Queue status label
        - Button visibility (Start Run, Clear Queue)
        """
        queue_size = self.queue_presenter.get_queue_size()

        # Update progress bar with current queue state
        if bar := self._sidebar_widget('queue_progress_bar'):
            try:
                cycles = self.queue_presenter.get_queue_snapshot()
                completed_cycles = self.queue_presenter.get_completed_cycles()
                bar.set_cycles(cycles, completed_cycles)
                if hasattr(self, '_current_cycle') and self._current_cycle:
                    current_index = 0
                else:
                    current_index = -1
                bar.set_current_index(current_index)
            except Exception as e:
                logger.debug(f"Could not update progress bar: {e}")

        # Update queue status label
        if lbl := self._sidebar_widget('queue_status_label'):
            if queue_size == 0:
                lbl.setText("Queue: 0 cycles | Click 'Add to Queue' to plan batch runs")
            elif queue_size == 1:
                lbl.setText("Queue: 1 cycle ready")
            else:
                lbl.setText(f"Queue: {queue_size} cycles ready")

        # Show/hide Start Run button based on queue size
        if btn := self._sidebar_widget('start_run_btn'):
            btn.setVisible(queue_size > 0)

        # Show/hide Clear Queue button based on queue size
        if btn := self._sidebar_widget('clear_queue_btn'):
            btn.setVisible(queue_size > 0)

        # Update queue size label in table footer
        if lbl := self._sidebar_widget('queue_size_label'):
            if queue_size == 0:
                lbl.setText("No cycles queued")
            elif queue_size == 1:
                lbl.setText("1 cycle queued")
            else:
                lbl.setText(f"{queue_size} cycles queued")

        # Update status bar queue status
        if hasattr(self.main_window, 'update_status_queue'):
            self.main_window.update_status_queue(queue_size)

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

        # Connect Clear Graph signal from sensorgram graphs
        # This signal is emitted when user clicks Clear Graph button
        if hasattr(self.main_window, 'full_timeline_graph'):
            # full_timeline_graph is actually a DataWindow instance that has the signal
            from affilabs.widgets.datawindow import DataWindow
            # Find the DataWindow widget (the graphs are wrapped in it)
            for widget in self.main_window.findChildren(DataWindow):
                if hasattr(widget, 'reset_graphs_sig'):
                    widget.reset_graphs_sig.connect(self._on_clear_graphs_requested)
                    logger.debug("✓ Connected: DataWindow.reset_graphs_sig -> _on_clear_graphs_requested")
                    break

        # NOTE: These signals not yet implemented in main window
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

        # --- Graph Controls (hidden per user request) ---
        # ui.grid_check.toggled.connect(self._on_grid_toggled)
        # ui.autoscale_check.toggled.connect(self._on_autoscale_toggled)
        # ui.min_input.editingFinished.connect(self._on_manual_range_changed)
        # ui.max_input.editingFinished.connect(self._on_manual_range_changed)
        # ui.x_axis_btn.toggled.connect(self._on_axis_selected)
        # ui.y_axis_btn.toggled.connect(self._on_axis_selected)
        ui.colorblind_check.toggled.connect(self._on_colorblind_toggled)

        # --- Channel and Marker Controls ---
        if hasattr(ui.sidebar, 'channel_combo'):
            ui.sidebar.channel_combo.currentTextChanged.connect(self._on_channel_filter_changed)
        if hasattr(ui.sidebar, 'marker_combo'):
            ui.sidebar.marker_combo.currentTextChanged.connect(self._on_marker_style_changed)

        # --- Reference Channel Selection ---
        if hasattr(ui.sidebar, 'ref_combo'):
            ui.sidebar.ref_combo.currentTextChanged.connect(self._on_reference_changed)

        # --- Export Controls ---
        if hasattr(ui, 'export_image_btn'):
            ui.export_image_btn.clicked.connect(self._on_quick_export_image)
        if hasattr(ui.sidebar, 'copy_graph_btn'):
            ui.sidebar.copy_graph_btn.clicked.connect(self._on_copy_graph_to_clipboard)

        # --- Settings Tab Controls ---
        if hasattr(ui.sidebar, 'apply_settings_btn'):
            ui.sidebar.apply_settings_btn.clicked.connect(self._on_apply_settings)

        # --- LED Brightness Live Updates ---
        if hasattr(ui.sidebar, 'led_brightness_changed'):
            ui.sidebar.led_brightness_changed.connect(self._on_led_brightness_changed)

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

        # NOTE: Polarizer Calibration button is already connected in affilabs_core_ui.py
        # to _handle_polarizer_calibration which calls app._on_polarizer_calibration
        # Do NOT connect again here to avoid double-triggering
        # if hasattr(ui, "polarizer_calibration_btn"):
        #     ui.polarizer_calibration_btn.clicked.connect(self._on_polarizer_calibration)
        #     logger.debug("[OK] Connected Polarizer Calibration button to handler")

        # OEM Calibration button (direct connection)
        ui.oem_led_calibration_btn.clicked.connect(self._on_oem_led_calibration)

        # LED Model Training button (direct connection)
        ui.led_model_training_btn.clicked.connect(self._on_led_model_training)

        # Baseline Capture button (REBUILT - direct connection, no lambda)
        if hasattr(ui, "baseline_capture_btn"):
            logger.debug(f"[DEBUG] Found baseline_capture_btn: {ui.baseline_capture_btn}")
            logger.debug(f"[DEBUG] Button object name: {ui.baseline_capture_btn.objectName()}")
            logger.debug(f"[DEBUG] Button is enabled: {ui.baseline_capture_btn.isEnabled()}")
            logger.debug(f"[DEBUG] Button is visible: {ui.baseline_capture_btn.isVisible()}")

            # Disconnect any existing connections first
            try:
                ui.baseline_capture_btn.clicked.disconnect()
                logger.debug("[DEBUG] Disconnected existing button connections")
            except:
                logger.debug("[DEBUG] No existing connections to disconnect")

            # Connect to handler
            ui.baseline_capture_btn.clicked.connect(self._on_record_baseline_clicked)
            logger.info("[OK] ✓ Connected Baseline Capture button to handler")

            # Test connection
            logger.debug(f"[DEBUG] Button has {ui.baseline_capture_btn.receivers('clicked()')} receivers")
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

        # Start Cycle button: DEPRECATED - now in Method Builder dialog
        # ui.sidebar.start_cycle_btn.clicked.connect(self._on_start_button_clicked)
        # logger.debug("✓ start_cycle_btn connected")

        # Next Cycle button: DEPRECATED - now in Method Builder dialog
        # if hasattr(ui.sidebar, 'next_cycle_btn'):
        #     ui.sidebar.next_cycle_btn.clicked.connect(self._on_next_cycle)
        #     logger.debug("✓ next_cycle_btn connected")

        # --- Flow Tab Controls ---
        # Pump operations buttons
        if hasattr(ui.sidebar, 'pump_prime_btn'):
            ui.sidebar.pump_prime_btn.clicked.connect(self._on_pump_prime_clicked)
            logger.debug("✓ pump_prime_btn connected")
        if hasattr(ui.sidebar, 'pump_cleanup_btn'):
            ui.sidebar.pump_cleanup_btn.clicked.connect(self._on_pump_cleanup_clicked)
            logger.debug("✓ pump_cleanup_btn connected")

        # Inject operation buttons
        if hasattr(ui.sidebar, 'inject_simple_btn'):
            ui.sidebar.inject_simple_btn.clicked.connect(self._on_inject_simple_clicked)
            logger.debug("✓ inject_simple_btn connected")
        if hasattr(ui.sidebar, 'inject_partial_btn'):
            ui.sidebar.inject_partial_btn.clicked.connect(self._on_inject_partial_clicked)
            logger.debug("✓ inject_partial_btn connected")

        # Buffer and Flush operations
        if hasattr(ui.sidebar, 'start_buffer_btn'):
            ui.sidebar.start_buffer_btn.clicked.connect(self._on_start_buffer_clicked)
            logger.debug("✓ start_buffer_btn connected")
        if hasattr(ui.sidebar, 'flush_btn'):
            ui.sidebar.flush_btn.clicked.connect(self._on_flush_loop_clicked)
            logger.debug("✓ flush_btn connected")

        # Maintenance operations (Home and Emergency Stop)
        if hasattr(ui.sidebar, 'pump_home_btn'):
            ui.sidebar.pump_home_btn.clicked.connect(self._on_home_pumps_clicked)
            logger.debug("✓ pump_home_btn connected")
        if hasattr(ui.sidebar, 'pump_emergency_stop_btn'):
            ui.sidebar.pump_emergency_stop_btn.clicked.connect(self._on_emergency_stop_clicked)
            logger.debug("✓ pump_emergency_stop_btn connected")

        # Flow rate spinboxes - on-the-fly rate change when pump is running
        if hasattr(ui.sidebar, 'pump_setup_spin'):
            ui.sidebar.pump_setup_spin.valueChanged.connect(
                lambda value: self._on_flow_rate_changed("Setup", value)
            )
            logger.debug("✓ pump_setup_spin connected")
        if hasattr(ui.sidebar, 'pump_functionalization_spin'):
            ui.sidebar.pump_functionalization_spin.valueChanged.connect(
                lambda value: self._on_flow_rate_changed("Functionalization", value)
            )
            logger.debug("✓ pump_functionalization_spin connected")
        if hasattr(ui.sidebar, 'pump_assay_spin'):
            ui.sidebar.pump_assay_spin.valueChanged.connect(
                lambda value: self._on_flow_rate_changed("Assay", value)
            )
            logger.debug("✓ pump_assay_spin connected")

        # Valve sync button
        if hasattr(ui.sidebar, 'sync_valve_btn'):
            ui.sidebar.sync_valve_btn.clicked.connect(
                lambda checked: self._on_valve_sync_toggled(checked)
            )
            logger.debug("✓ sync_valve_btn connected")

        # Internal pump controls (P4PROPLUS)
        if hasattr(ui.sidebar, 'synced_toggle_btn'):
            ui.sidebar.synced_toggle_btn.toggled.connect(lambda checked: self._on_synced_pump_toggle(checked))
            # Connect flowrate change to update status display live
            if hasattr(ui.sidebar, 'synced_flowrate_changed'):
                ui.sidebar.synced_flowrate_changed.connect(self._on_synced_flowrate_changed)
            logger.debug("✓ synced_toggle_btn connected")
        if hasattr(ui.sidebar, 'pump1_toggle_btn'):
            ui.sidebar.pump1_toggle_btn.toggled.connect(lambda checked: self._on_internal_pump1_toggle(checked))
            logger.debug("✓ pump1_toggle_btn connected")
        if hasattr(ui.sidebar, 'internal_pump_inject_30s_btn'):
            ui.sidebar.internal_pump_inject_30s_btn.clicked.connect(self._on_internal_pump_inject_30s)
            logger.debug("✓ internal_pump_inject_30s_btn connected")

        # Internal pump RPM changes (for sync mode)
        if hasattr(ui.sidebar, 'synced_flowrate_combo'):
            ui.sidebar.synced_flowrate_combo.currentIndexChanged.connect(lambda: self._on_synced_flowrate_changed())
            logger.debug("✓ synced_flowrate_combo connected")
        if hasattr(ui.sidebar, 'synced_correction_spin'):
            ui.sidebar.synced_correction_spin.valueChanged.connect(lambda: self._on_synced_rpm_changed())
            logger.debug("✓ synced_correction_spin connected")

        # Individual pump RPM changes (for independent mode)
        if hasattr(ui.sidebar, 'pump1_rpm_spin'):
            ui.sidebar.pump1_rpm_spin.valueChanged.connect(lambda: self._on_pump1_rpm_changed())
            logger.debug("✓ pump1_rpm_spin connected")
        if hasattr(ui.sidebar, 'pump1_correction_spin'):
            ui.sidebar.pump1_correction_spin.valueChanged.connect(lambda: self._on_pump1_rpm_changed())
            logger.debug("✓ pump1_correction_spin connected")

        # Valve controls (Loop valves - 6-port)
        # KC1 Loop valve - segmented control (Load = state 0, Sensor = state 1)
        if hasattr(ui.sidebar, 'kc1_loop_btn_load'):
            ui.sidebar.kc1_loop_btn_load.clicked.connect(
                lambda: self._on_loop_valve_switched(1, 'Load')
            )
            logger.debug("✓ kc1_loop_btn_load connected")
        if hasattr(ui.sidebar, 'kc1_loop_btn_sensor'):
            ui.sidebar.kc1_loop_btn_sensor.clicked.connect(
                lambda: self._on_loop_valve_switched(1, 'Sensor')
            )
            logger.debug("✓ kc1_loop_btn_sensor connected")

        # KC2 Loop valve - segmented control (Load = state 0, Sensor = state 1)
        if hasattr(ui.sidebar, 'kc2_loop_btn_load'):
            ui.sidebar.kc2_loop_btn_load.clicked.connect(
                lambda: self._on_loop_valve_switched(2, 'Load')
            )
            logger.debug("✓ kc2_loop_btn_load connected")
        if hasattr(ui.sidebar, 'kc2_loop_btn_sensor'):
            ui.sidebar.kc2_loop_btn_sensor.clicked.connect(
                lambda: self._on_loop_valve_switched(2, 'Sensor')
            )
            logger.debug("✓ kc2_loop_btn_sensor connected")

        # Valve controls (Channel valves - 3-way)
        if hasattr(ui.sidebar, 'kc1_channel_btn_a'):
            ui.sidebar.kc1_channel_btn_a.clicked.connect(
                lambda: self._on_channel_valve_switched(1, 'A')
            )
            logger.debug("✓ kc1_channel_btn_a connected")
        if hasattr(ui.sidebar, 'kc1_channel_btn_b'):
            ui.sidebar.kc1_channel_btn_b.clicked.connect(
                lambda: self._on_channel_valve_switched(1, 'B')
            )
            logger.debug("✓ kc1_channel_btn_b connected")
        if hasattr(ui.sidebar, 'kc2_channel_btn_c'):
            ui.sidebar.kc2_channel_btn_c.clicked.connect(
                lambda: self._on_channel_valve_switched(2, 'C')
            )
            logger.debug("✓ kc2_channel_btn_c connected")
        if hasattr(ui.sidebar, 'kc2_channel_btn_d'):
            ui.sidebar.kc2_channel_btn_d.clicked.connect(
                lambda: self._on_channel_valve_switched(2, 'D')
            )
            logger.debug("✓ kc2_channel_btn_d connected")

        # Internal Pump controls (RPi peristaltic pumps - separate from AffiPump)
        if hasattr(ui.sidebar, 'internal_pump_sync_btn'):
            ui.sidebar.internal_pump_sync_btn.clicked.connect(
                lambda checked: self._on_internal_pump_sync_toggled(checked)
            )
            logger.debug("✓ internal_pump_sync_btn connected")

        if hasattr(ui.sidebar, 'internal_pump_calibrate_btn'):
            ui.sidebar.internal_pump_calibrate_btn.clicked.connect(
                self._on_internal_pump_calibrate_clicked
            )
            logger.debug("✓ internal_pump_calibrate_btn connected")

        # Calibration timing button removed - use flag-based delta calculation instead

        # Internal pump flowrate changes
        if hasattr(ui.sidebar, 'internal_pump_flowrate_combo'):
            ui.sidebar.internal_pump_flowrate_combo.currentTextChanged.connect(
                self._on_internal_pump_flowrate_changed
            )
            logger.debug("✓ internal_pump_flowrate_combo connected")

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

        # Build Method button - opens popup dialog
        if hasattr(ui.sidebar, "build_method_btn"):
            ui.sidebar.build_method_btn.clicked.connect(self._on_build_method)
            logger.debug("✓ build_method_btn connected")
        else:
            logger.warning("[WARN] build_method_btn NOT found in UI")

        # Preset menu actions (Save/Load - handles single cycles or full sequences)
        if hasattr(ui.sidebar, "save_preset_action"):
            ui.sidebar.save_preset_action.triggered.connect(self._on_save_preset)
            logger.debug("✓ save_preset_action connected")

        if hasattr(ui.sidebar, "load_preset_action"):
            ui.sidebar.load_preset_action.triggered.connect(self._on_load_preset)
            logger.debug("✓ load_preset_action connected")

        # Pause/Resume queue button
        if hasattr(ui.sidebar, "pause_queue_btn"):
            ui.sidebar.pause_queue_btn.clicked.connect(self._on_toggle_pause_queue)
            logger.debug("✓ pause_queue_btn connected")

        # Summary table context menu (right-click to delete cycles)
        if hasattr(ui.sidebar, "summary_table"):
            ui.sidebar.summary_table.customContextMenuRequested.connect(
                self._on_queue_table_context_menu
            )
            logger.debug("✓ summary_table context menu connected")

        # Set app reference for Method tab builder (for accessing segment_queue in View All Cycles dialog)
        if hasattr(ui, "sidebar"):
            if hasattr(ui.sidebar, "method_tab_builder"):
                ui.sidebar.method_tab_builder.set_app_reference(self)
                logger.debug("✓ method_tab_builder app reference set for View All Cycles")
            else:
                logger.error("✗ method_tab_builder NOT found in sidebar - View All Cycles won't work!")
        else:
            logger.error("✗ sidebar NOT found in main_window - View All Cycles won't work!")

        # Verify cycle table connections with comprehensive diagnostic
        self._verify_cycle_table_connections()

    def _verify_cycle_table_connections(self):
        """Verify all cycle table connections are properly set up."""
        logger.info("=" * 80)
        logger.info("🔍 CYCLE TABLE CONNECTION VERIFICATION")
        logger.info("=" * 80)

        # Check 1: Main window has edits_tab
        if hasattr(self.main_window, 'edits_tab'):
            logger.info("✓ main_window.edits_tab EXISTS")

            # Check 2: edits_tab has cycle_data_table
            if hasattr(self.main_window.edits_tab, 'cycle_data_table'):
                table = self.main_window.edits_tab.cycle_data_table
                logger.info(f"✓ edits_tab.cycle_data_table EXISTS (type: {type(table).__name__})")
                logger.info(f"   - Current rows: {table.rowCount()}")
                logger.info(f"   - Current columns: {table.columnCount()}")
            else:
                logger.error("✗ edits_tab.cycle_data_table DOES NOT EXIST!")
        else:
            logger.error("✗ main_window.edits_tab DOES NOT EXIST!")

        # Check 3: Main window has add_cycle_to_table method
        if hasattr(self.main_window, 'add_cycle_to_table'):
            logger.info("✓ main_window.add_cycle_to_table METHOD EXISTS")
        else:
            logger.error("✗ main_window.add_cycle_to_table METHOD DOES NOT EXIST!")

        # Check 4: Sidebar has method_tab_builder
        if hasattr(self.main_window, 'sidebar'):
            if builder := self._sidebar_widget('method_tab_builder'):
                logger.info("✓ sidebar.method_tab_builder EXISTS")

                # Check 5: method_tab_builder has app reference
                if hasattr(builder, '_app_reference') and builder._app_reference is not None:
                    logger.info("✓ method_tab_builder._app_reference IS SET")
                    logger.info(f"   - Points to: {type(builder._app_reference).__name__}")
                else:
                    logger.error("✗ method_tab_builder._app_reference IS NOT SET!")
            else:
                logger.error("✗ sidebar.method_tab_builder DOES NOT EXIST!")
        else:
            logger.error("✗ main_window.sidebar DOES NOT EXIST!")

        # Check 6: Segment queue exists
        if hasattr(self, 'segment_queue'):
            logger.info(f"✓ app.segment_queue EXISTS (current size: {len(self.segment_queue)})")
        else:
            logger.error("✗ app.segment_queue DOES NOT EXIST!")

        logger.info("=" * 80)
        logger.info("END VERIFICATION")
        logger.info("=" * 80)

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

        # Install keyboard event filter for flag movement
        self._setup_keyboard_event_filter()

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

        # === PUMP MANAGER STATUS SIGNALS ===
        if self.pump_mgr:
            self.pump_mgr.operation_started.connect(self._on_pump_operation_started)
            self.pump_mgr.operation_progress.connect(self._on_pump_operation_progress)
            self.pump_mgr.operation_completed.connect(self._on_pump_operation_completed)
            self.pump_mgr.status_updated.connect(self._on_pump_status_updated)
            logger.debug("✓ PumpManager signals connected")

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

        # Initialize filter to default (None - raw data)
        self._set_display_filter(0)
        logger.debug("✓ Display filter: None (raw data)")

        logger.debug("✓ UI event signals (tabs/pages/filters)")

    def _set_display_filter(self, filter_id: int):
        """Set EMA display filter method based on radio button selection.

        Args:
            filter_id: 0=None (Raw), 1=Light Smoothing

        """
        filter_configs = [
            {"method": "none", "alpha": 0.0, "label": "None (Raw)"},
            {"method": "ema_light", "alpha": 0.50, "label": "Light Smoothing"},
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

    def _cancel_active_cycle(self):
        """Cancel the currently-running cycle without starting the next one.

        Stops both cycle timers, clears cycle state, unlocks the queue,
        and restores the intelligence refresh timer.  Unlike
        ``_on_cycle_completed`` this does **not** auto-start the next
        queued cycle, so the run truly stops.
        """
        # Stop both timers (display-update + end-of-cycle)
        if hasattr(self, '_cycle_timer') and self._cycle_timer.isActive():
            self._cycle_timer.stop()
        if hasattr(self, '_cycle_end_timer') and self._cycle_end_timer.isActive():
            self._cycle_end_timer.stop()

        # Resume the 5 s intelligence refresh timer
        if hasattr(self.main_window, 'intelligence_refresh_timer'):
            self.main_window.intelligence_refresh_timer.start(5000)

        # Clear cycle state
        had_cycle = self._current_cycle is not None
        self._current_cycle = None
        self._cycle_end_time = None

        # Hide "Now Running" banner
        if had_cycle:
            self._update_now_running_banner("", 0.0, show=False)

        # Unlock queue so user can edit it again
        try:
            self.queue_presenter.unlock_queue()
        except Exception:
            pass

        # Remove next-cycle warning line from graph
        if hasattr(self, '_next_cycle_warning_line') and self._next_cycle_warning_line is not None:
            try:
                if hasattr(self.main_window, 'cycle_of_interest_graph'):
                    self.main_window.cycle_of_interest_graph.removeItem(self._next_cycle_warning_line)
            except Exception:
                pass
            self._next_cycle_warning_line = None

        # Re-enable Start Run button
        if btn := self._sidebar_widget('start_queue_btn'):
            btn.setEnabled(True)
        if btn := self._sidebar_widget('next_cycle_btn'):
            btn.setEnabled(False)

        if had_cycle:
            logger.info("🛑 Active cycle cancelled – timers stopped, queue unlocked")

    def _on_start_button_clicked(self):
        """Start the next cycle from queue or auto-read mode."""
        import time

        logger.info("▶ Start Cycle button clicked")

        # If no cycles in queue, start auto-read mode
        if self.queue_presenter.get_queue_size() == 0:
            logger.info("No cycles in queue - starting auto-read mode")
            if not self.data_mgr._acquiring:
                self.acquisition_events.on_start_button_clicked()
            return

        # ── Check if recording is active before running queued cycles ─────
        if not self.recording_mgr.is_recording:
            from PySide6.QtWidgets import QMessageBox

            reply = QMessageBox.question(
                self.main_window,
                "Recording Not Active",
                "Data recording is not enabled.\n\n"
                "Would you like to start recording before\n"
                "running the cycle queue?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Cancel:
                logger.info("Cycle start cancelled by user")
                return
            if reply == QMessageBox.Yes:
                logger.info("User chose to start recording before cycle queue")
                self._on_recording_start_requested()
                # If user cancelled the recording dialog, don't start cycles
                if not self.recording_mgr.is_recording:
                    logger.info("Recording was not started — aborting cycle start")
                    return

        # Lock queue during execution (prevents edits)
        self.queue_presenter.lock_queue()

        # Pop first cycle from queue via presenter
        cycle = self.queue_presenter.pop_next_cycle()

        if cycle is None:
            logger.error("❌ Failed to pop cycle from queue")
            self.queue_presenter.unlock_queue()
            return

        # Sync backward compatibility list
        self.segment_queue = self.queue_presenter.get_queue_snapshot()

        cycle_type = cycle.type
        duration_min = cycle.length_minutes

        # Calculate cycle numbers
        cycle_num = len(self._completed_cycles) + 1
        total_cycles = cycle_num + self.queue_presenter.get_queue_size()

        logger.info(f"Starting Cycle {cycle_num}/{total_cycles}: {cycle_type}, {duration_min} min")

        # Start acquisition if not already running
        if not self.data_mgr._acquiring:
            logger.info("Starting data acquisition...")
            self.acquisition_events.on_start_button_clicked()

        # Initialize cycle tracking using Cycle.start() method
        self._current_cycle = cycle
        self._current_cycle.start(
            cycle_num=cycle_num,
            total_cycles=total_cycles,
            sensorgram_time=0.0  # Will be updated when first data arrives
        )
        self._cycle_end_time = time.time() + (duration_min * 60)
        logger.info(f"✓ Cycle initialized: {cycle_type}, end_time set to {self._cycle_end_time}")
        logger.debug(f"   cycle_num={cycle_num}, total={total_cycles}, duration={duration_min}min")

        # Show "Now Running" banner in sidebar
        self._update_now_running_banner(cycle_type, duration_min, show=True)

        # Update status bar operation status
        if hasattr(self.main_window, 'update_status_operation'):
            duration_str = f"{int(duration_min):02d}:{int((duration_min % 1) * 60):02d}"
            self.main_window.update_status_operation(f"Running: {cycle_type} ({duration_str})")

        # Schedule auto-completion when cycle duration expires
        duration_ms = int(duration_min * 60 * 1000)
        self._cycle_end_timer.start(duration_ms)
        logger.info(f"✓ Cycle end timer scheduled: {duration_min} min ({duration_ms} ms)")

        # Pause the 5s intelligence refresh timer to avoid overwriting cycle countdown
        if hasattr(self.main_window, 'intelligence_refresh_timer'):
            self.main_window.intelligence_refresh_timer.stop()

        # Start the 1-second update timer for intelligence bar and overlay
        if hasattr(self, '_cycle_timer'):
            self._cycle_timer.start(1000)  # Update every 1 second
            logger.info("✓ Cycle display timer started (updates every 1 second)")
            logger.debug(f"   _cycle_timer isActive: {self._cycle_timer.isActive()}, interval: {self._cycle_timer.interval()}ms")
        else:
            logger.error("❌ _cycle_timer does not exist - cycle display will not update!")

        # === PUMP ORCHESTRATION FOR THIS CYCLE ===
        has_pump = self.pump_mgr.is_available if hasattr(self, 'pump_mgr') else False
        has_internal = (self.hardware_mgr.ctrl and
                       hasattr(self.hardware_mgr.ctrl, 'has_internal_pumps') and
                       self.hardware_mgr.ctrl.has_internal_pumps())

        if has_pump:
            # Stop any running pump operation before starting new cycle
            if not self.pump_mgr.is_idle:
                logger.info(f"⏹ Stopping pump for new cycle: {cycle_type}")
                self._stop_pump_for_cycle_transition()

            # If cycle has a flow_rate, start buffer at that rate
            if cycle.flow_rate is not None and cycle.flow_rate > 0:
                logger.info(f"▶ Starting buffer flow for {cycle_type} @ {cycle.flow_rate} µL/min")
                self._start_buffer_for_cycle(cycle.flow_rate)

        # Schedule injection if cycle requires it AND pump is available
        if cycle.injection_method is not None:
            if has_pump or has_internal:
                self._schedule_injection(cycle)
            else:
                logger.warning(f"⚠️ Cycle requires {cycle.injection_method} injection but no pump connected — skipping injection")

        # Update progress bar to show current cycle
        if bar := self._sidebar_widget('queue_progress_bar'):
            try:
                cycles = self.queue_presenter.get_queue_snapshot()
                completed_cycles = self.queue_presenter.get_completed_cycles()
                bar.set_cycles(cycles, completed_cycles)
                bar.set_current_index(0)  # First in queue is current
                logger.debug(f"✓ Progress bar updated: {len(completed_cycles)} completed, 1 current, {len(cycles)-1} upcoming")
            except Exception as e:
                logger.warning(f"Could not update progress bar: {e}")

        # Disable Start Run button during cycle execution
        if btn := self._sidebar_widget('start_queue_btn'):
            btn.setEnabled(False)

        # Enable Next Cycle button during cycle execution
        if btn := self._sidebar_widget('next_cycle_btn'):
            btn.setEnabled(True)

        # Reset channel time shifts to default (live sensorgram timing)
        # Each cycle should start with fresh timing, not inherit adjustments from previous cycle
        if hasattr(self, '_channel_time_shifts'):
            self._channel_time_shifts = {'a': 0.0, 'b': 0.0, 'c': 0.0, 'd': 0.0}

        # Reset Active Cycle view: move start cursor to end cursor position (start fresh at t=0)
        try:
            if hasattr(self.main_window, 'full_timeline_graph'):
                timeline = self.main_window.full_timeline_graph
                if hasattr(timeline, 'start_cursor') and hasattr(timeline, 'stop_cursor'):
                    # Get current end cursor position
                    end_pos = timeline.stop_cursor.value()
                    # Move start cursor to end position (Active Cycle will show this as t=0)
                    timeline.start_cursor.setValue(end_pos)

                    # CRITICAL: Update the active segment's start time AND clear old data
                    if hasattr(timeline, 'active_segment') and timeline.active_segment is not None:
                        timeline.active_segment.start = end_pos
                        # Clear any existing data so Active Cycle starts fresh at 0,0
                        import numpy as np
                        for ch in ['a', 'b', 'c', 'd']:
                            timeline.active_segment.seg_x[ch] = np.array([])
                            timeline.active_segment.seg_y[ch] = np.array([])
                            timeline.active_segment.start_index[ch] = 0
                            timeline.active_segment.end_index[ch] = 0
                        logger.debug(f"Updated active segment start to {end_pos:.1f}s and cleared data")

                    logger.info(f"✓ Active Cycle reset: start cursor at t={end_pos:.1f}s (displays as 0,0)")
        except Exception as e:
            logger.debug(f"Could not reset cursors: {e}")

        # Add blue vertical marker to Full Sensorgram timeline
        self._add_cycle_marker()

    def _stop_pump_for_cycle_transition(self):
        """Stop any running pump operation for cycle transition (runs in background)."""
        def run_stop():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.stop_and_wait_for_idle(timeout=15.0))
            finally:
                loop.close()

        thread = threading.Thread(target=run_stop, daemon=True, name="StopPumpForCycle")
        thread.start()
        # Give it a moment to send terminate commands
        import time
        time.sleep(0.5)

    def _start_buffer_for_cycle(self, flow_rate: float):
        """Start buffer flow for a cycle at the specified rate.

        Args:
            flow_rate: Flow rate in µL/min from the cycle definition
        """
        def run_buffer():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Wait for pump to be fully idle before starting buffer
                loop.run_until_complete(self.pump_mgr.stop_and_wait_for_idle(timeout=15.0))
                loop.run_until_complete(self.pump_mgr.run_buffer(
                    cycles=0,  # Continuous until stopped
                    duration_min=0,
                    volume_ul=1000.0,
                    flow_rate=flow_rate
                ))
            finally:
                loop.close()

        thread = threading.Thread(target=run_buffer, daemon=True, name="CycleBuffer")
        thread.start()

        # Update button text to show buffer is running
        if btn := self._sidebar_widget('start_buffer_btn'):
            btn.setText("⏸ Stop Buffer")

    def _on_start_queued_run(self):
        """Start executing all cycles in queue sequentially."""
        logger.info("▶ Start Queued Run button clicked")

        # Check if there are cycles in queue
        queue_size = self.queue_presenter.get_queue_size()
        if queue_size == 0:
            logger.warning("No cycles in queue to run")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self.main_window,
                "No Cycles in Queue",
                "Add cycles to the queue using the Method Builder before starting a run."
            )
            return

        # Check if acquisition is running
        if not self.data_mgr._acquiring:
            logger.info("Starting data acquisition for queued run...")
            self.acquisition_events.on_start_button_clicked()

        # Start first cycle (subsequent cycles will auto-start when previous completes)
        logger.info(f"Starting queued run with {queue_size} cycles")
        self._on_start_button_clicked()
        logger.info("✓ Queued run started successfully")

    def _schedule_injection(self, cycle):
        """Schedule injection to trigger after delay.

        Args:
            cycle: Cycle object with injection_method and injection_delay
        """
        from PySide6.QtCore import QTimer

        delay_ms = int(cycle.injection_delay * 1000)  # Convert to milliseconds

        logger.info(f"⏲ Injection scheduled in {cycle.injection_delay}s ({cycle.injection_method})")

        # Use QTimer.singleShot to trigger injection after delay
        QTimer.singleShot(delay_ms, lambda: self._execute_injection(cycle))

    def _execute_injection(self, cycle):
        """Execute injection method for cycle.

        Stops any running pump operation (e.g. buffer) first, waits for idle,
        then triggers the injection. The method queue drives what happens next.

        Args:
            cycle: Cycle object with injection parameters
        """
        # Validate pump available
        has_affipump = self.pump_mgr.is_available
        has_internal = (self.hardware_mgr.ctrl and
                       hasattr(self.hardware_mgr.ctrl, 'has_internal_pumps') and
                       self.hardware_mgr.ctrl.has_internal_pumps())

        if not has_affipump and not has_internal:
            logger.error("❌ Injection failed - no pump available")
            self.main_window.set_intel_message("❌ Injection failed - no pump", "#FF3B30")
            return

        # Get assay rate: cycle.flow_rate (from method) takes priority over UI spin
        if cycle.flow_rate is not None and cycle.flow_rate > 0:
            assay_rate = cycle.flow_rate
            logger.info(f"Using cycle flow_rate: {assay_rate} µL/min (from method definition)")
        else:
            assay_rate = 100.0
            if spin := self._sidebar_widget('pump_assay_spin'):
                assay_rate = float(spin.value())
            logger.info(f"Using UI assay rate: {assay_rate} µL/min (no cycle flow_rate set)")

        # Stop pump and inject in background thread (stop_and_wait_for_idle is async)
        def run_stop_then_inject():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Step 1: Stop any running pump operation and wait for idle
                if not self.pump_mgr.is_idle:
                    logger.info("⏹ Stopping pump before injection...")
                    idle_ok = loop.run_until_complete(self.pump_mgr.stop_and_wait_for_idle(timeout=30.0))
                    if not idle_ok:
                        logger.error("❌ Could not stop pump for injection")
                        self.pump_mgr.error_occurred.emit("inject", "Could not stop pump for injection")
                        return

                # Step 2: Execute the injection
                if cycle.injection_method == "simple":
                    logger.info(f"💉 AUTO-INJECT: Simple injection @ {assay_rate} µL/min")
                    loop.run_until_complete(self.pump_mgr.inject_simple(assay_rate))
                elif cycle.injection_method == "partial":
                    logger.info(f"💉 AUTO-INJECT: Partial injection @ {assay_rate} µL/min")
                    loop.run_until_complete(self.pump_mgr.inject_partial_loop(assay_rate))
            except Exception as e:
                logger.exception(f"Injection thread error: {e}")
            finally:
                loop.close()

        thread = threading.Thread(target=run_stop_then_inject, daemon=True, name="CycleInjection")
        thread.start()

        # Log event to sensorgram
        if hasattr(self, 'recording_mgr'):
            event_name = f"Auto-Injection ({cycle.injection_method})"
            if cycle.contact_time:
                event_name += f" - {cycle.contact_time}s contact"
            self.recording_mgr.log_event(event_name)

    def _trigger_simple_injection(self, assay_rate: float):
        """Trigger simple injection (reuse existing code).

        Args:
            assay_rate: Flow rate in µL/min
        """
        def run_inject():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.inject_simple(assay_rate))
            finally:
                loop.close()

        thread = threading.Thread(target=run_inject, daemon=True, name="AutoInjectSimple")
        thread.start()

    def _trigger_partial_injection(self, assay_rate: float):
        """Trigger partial injection (reuse existing code).

        Args:
            assay_rate: Flow rate in µL/min
        """
        def run_inject():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.inject_partial_loop(assay_rate))
            finally:
                loop.close()

        thread = threading.Thread(target=run_inject, daemon=True, name="AutoInjectPartial")
        thread.start()

    def _update_cycle_display(self):
        """Update Active Cycle overlay with cycle progress."""
        import time

        # DEBUG: Log to verify this is being called
        logger.debug(f"_update_cycle_display called - current_cycle={self._current_cycle is not None}, end_time={self._cycle_end_time is not None}")

        if not self._current_cycle or not self._cycle_end_time:
            logger.warning(f"Cannot update cycle display - current_cycle: {self._current_cycle is not None}, end_time: {self._cycle_end_time is not None}")
            return

        # Calculate elapsed and total time
        now = time.time()
        total_sec = self._current_cycle.get_duration_seconds()
        elapsed_sec = total_sec - max(0, self._cycle_end_time - now)
        remaining_sec = max(0, self._cycle_end_time - now)

        cycle_type = self._current_cycle.type
        cycle_num = self._current_cycle.cycle_num
        total_cycles = self._current_cycle.total_cycles

        # Format time for display
        # For cycles > 99 minutes, show hours:minutes instead of minutes:seconds
        if total_sec >= 6000:  # >= 100 minutes
            # Display as hours:minutes
            elapsed_hours = int(elapsed_sec // 3600)
            elapsed_min_rem = int((elapsed_sec % 3600) // 60)
            total_hours = int(total_sec // 3600)
            total_min_rem = int((total_sec % 3600) // 60)
            time_format = f"{elapsed_hours:02d}:{elapsed_min_rem:02d}/{total_hours:02d}:{total_min_rem:02d}"
        else:
            # Display as minutes:seconds
            elapsed_min = int(elapsed_sec // 60)
            elapsed_sec_rem = int(elapsed_sec % 60)
            total_min = int(total_sec // 60)
            total_sec_rem = int(total_sec % 60)
            time_format = f"{elapsed_min:02d}:{elapsed_sec_rem:02d}/{total_min:02d}:{total_sec_rem:02d}"

        # Check if there's a next cycle and we're within 10 seconds
        next_cycle_warning = ""
        if remaining_sec <= 10 and remaining_sec > 0 and self.segment_queue:
            next_cycle = self.segment_queue[0]
            next_type = next_cycle.type
            # Shorten "Concentration" to "Conc."
            if next_type == "Concentration":
                next_type = "Conc."

            # Add concentration if available - use proper field
            if next_cycle.concentrations and 'ALL' in next_cycle.concentrations:
                conc_value = next_cycle.concentrations['ALL']
                units = next_cycle.units
                next_type = f"{next_type} {conc_value}{units}"

            next_cycle_warning = f" → Next: {next_type} in {int(remaining_sec)}s"

        # Update intelligence bar with countdown and next cycle warning
        message_text = f"⏱ {cycle_type} (Cycle {cycle_num}/{total_cycles}) - {time_format}{next_cycle_warning}"
        color = Colors.WARNING if next_cycle_warning else Colors.INFO
        logger.debug(f"Setting intelligence message: {message_text}")
        self.main_window.set_intel_message(message_text, color)

        # Update status bar operation with remaining time
        if hasattr(self.main_window, 'update_status_operation'):
            remaining_min = int(remaining_sec // 60)
            remaining_sec_rem = int(remaining_sec % 60)
            self.main_window.update_status_operation(
                f"Running: {cycle_type} ({remaining_min:02d}:{remaining_sec_rem:02d} remaining)"
            )

        # Show/hide warning line on active cycle graph when <10s to next cycle
        self._update_next_cycle_warning_visual(remaining_sec, total_sec)

        # Update overlay using graph's update method
        try:
            if hasattr(self.main_window, 'cycle_of_interest_graph'):
                graph = self.main_window.cycle_of_interest_graph
                logger.debug(f"Found cycle_of_interest_graph, has update_delta_overlay: {hasattr(graph, 'update_delta_overlay')}")
                if hasattr(graph, 'update_delta_overlay'):
                    # Add next cycle info to overlay if within 10 seconds
                    overlay_type = f"{cycle_type} (Cycle {cycle_num}/{total_cycles})"
                    if next_cycle_warning:
                        overlay_type += next_cycle_warning

                    graph.update_delta_overlay(
                        cycle_type=overlay_type,
                        elapsed_sec=elapsed_sec,
                        total_sec=total_sec
                    )
                    # Log first update only
                    if elapsed_sec < 2:
                        logger.info(f"✓ Overlay updated: {cycle_type} {elapsed_min:02d}:{elapsed_sec_rem:02d}/{total_min:02d}:{total_sec_rem:02d}")
                        logger.debug(f"   Overlay params: type={overlay_type}, elapsed={elapsed_sec:.1f}s, total={total_sec:.1f}s")
                else:
                    if elapsed_sec < 2:
                        logger.error("❌ cycle_of_interest_graph does NOT have update_delta_overlay method!")
            else:
                if elapsed_sec < 2:
                    logger.error("❌ main_window does NOT have cycle_of_interest_graph attribute!")
        except Exception as e:
            logger.error(f"❌ Error updating cycle overlay: {e}", exc_info=True)

        # Running banner removed - info now static in method builder tab

    def _update_now_running_banner(self, cycle_type: str, duration_min: float, show: bool):
        """Show or hide the "Now Running" banner in the sidebar.
        
        DEPRECATED: Banner removed - running status shown in intelligence bar instead.
        Completed cycles info is now static in method builder tab.

        Args:
            cycle_type: Type of cycle running (e.g. "Baseline", "Wash")
            duration_min: Duration of cycle in minutes
            show: True to show the banner, False to hide it
        """
        # Method kept for compatibility but does nothing
        pass

    def _update_next_cycle_warning_visual(self, remaining_sec: float, total_sec: float):
        """Show/hide orange warning line on active cycle graph when <10s to next cycle.

        Args:
            remaining_sec: Seconds remaining in current cycle
            total_sec: Total cycle duration in seconds
        """
        try:
            if not hasattr(self.main_window, 'cycle_of_interest_graph'):
                return

            # Validate inputs to avoid overflow
            if not isinstance(remaining_sec, (int, float)) or not isinstance(total_sec, (int, float)):
                return
            if remaining_sec < 0 or total_sec <= 0:
                return
            if remaining_sec > 1e6 or total_sec > 1e6:  # Sanity check for huge values
                return

            graph = self.main_window.cycle_of_interest_graph

            # Calculate time position for warning (total - 10 seconds)
            warning_time = total_sec - 10.0
            if warning_time < 0:
                warning_time = 0

            # Show warning line when we're within 10s of cycle end AND there's a next cycle
            show_warning = remaining_sec <= 10 and remaining_sec > 0 and self.segment_queue

            if show_warning:
                # Create warning line if it doesn't exist
                if self._next_cycle_warning_line is None:
                    import pyqtgraph as pg
                    from PySide6.QtGui import QFont
                    self._next_cycle_warning_line = pg.InfiniteLine(
                        pos=warning_time,
                        angle=90,  # Vertical line
                        pen=pg.mkPen(color='#FF1493', width=3, style=pg.QtCore.Qt.DashLine),  # Hot pink, thicker
                        movable=False,
                        label=f'Next: {int(remaining_sec)}s',
                        labelOpts={
                            'position': 0.95,
                            'color': (255, 20, 147),  # Hot pink
                            'fill': (255, 20, 147, 80),  # More opaque background
                            'movable': False,
                            'anchors': [(0, 0), (0, 0)]
                        }
                    )
                    # Make label font bold and larger
                    if hasattr(self._next_cycle_warning_line, 'label') and hasattr(self._next_cycle_warning_line.label, 'setFont'):
                        font = QFont()
                        font.setPointSize(11)
                        font.setBold(True)
                        self._next_cycle_warning_line.label.setFont(font)
                    graph.addItem(self._next_cycle_warning_line)

                # Update position and label text
                self._next_cycle_warning_line.setPos(warning_time)
                if hasattr(self._next_cycle_warning_line, 'label'):
                    self._next_cycle_warning_line.label.setText(f'Next: {int(remaining_sec)}s')
                self._next_cycle_warning_line.show()
            else:
                # Hide warning line when not needed
                if self._next_cycle_warning_line is not None:
                    self._next_cycle_warning_line.hide()

        except Exception as e:
            logger.error(f"Error updating next cycle warning visual: {e}", exc_info=True)

    def _on_cycle_completed(self):
        """Handle cycle completion - auto-start next or switch to auto-read."""
        if not self._current_cycle:
            return

        cycle_type = self._current_cycle.type
        cycle_num = self._current_cycle.cycle_num

        logger.info(f"✓ Cycle {cycle_num} completed: {cycle_type}")

        # Stop cycle timers
        self._cycle_timer.stop()
        self._cycle_end_timer.stop()

        # Resume the 5s intelligence refresh timer
        if hasattr(self.main_window, 'intelligence_refresh_timer'):
            self.main_window.intelligence_refresh_timer.start(5000)

        # Clear all flags for clean start of next cycle
        self.flag_mgr.clear_flags_for_new_cycle()

        # Calculate end time in sensorgram time (not Unix timestamp!)
        end_sensorgram_time = None
        if hasattr(self.main_window, 'full_timeline_graph'):
            timeline = self.main_window.full_timeline_graph
            if hasattr(timeline, 'stop_cursor'):
                # End time is current stop cursor position (sensorgram seconds)
                end_sensorgram_time = timeline.stop_cursor.value()

        # Mark cycle as completed using presenter
        self.queue_presenter.mark_cycle_completed(self._current_cycle)

        # Unlock queue now that cycle is complete
        self.queue_presenter.unlock_queue()
        logger.debug("🔓 Queue unlocked after cycle completion")

        # Get completed cycles from presenter (includes this one)
        self._completed_cycles = self.queue_presenter.get_completed_cycles()

        # Sync backward compatibility list
        self.segment_queue = self.queue_presenter.get_queue_snapshot()

        # Get cycle export data for table and recording
        cycle_export_data = self._current_cycle.to_export_dict()

        # Always add cycle to the live cycle data table (regardless of recording state)
        logger.debug(f"🔄 Adding cycle to table: {cycle_export_data.get('type', 'Unknown')}")
        if hasattr(self.main_window, 'add_cycle_to_table'):
            logger.debug("   ✓ add_cycle_to_table method exists on main_window")
            self.main_window.add_cycle_to_table(cycle_export_data)
            logger.debug("   ✓ add_cycle_to_table() called successfully")
        else:
            logger.error("   ✗ add_cycle_to_table method NOT FOUND on main_window!")

        # Export cycle to recording manager only if recording
        if self.recording_mgr.is_recording:
            self.recording_mgr.add_cycle(cycle_export_data)

        # Clear current cycle
        self._current_cycle = None
        self._cycle_end_time = None

        # Hide "Now Running" banner
        self._update_now_running_banner("", 0.0, show=False)

        # Update status bar operation status
        if hasattr(self.main_window, 'update_status_operation'):
            self.main_window.update_status_operation("Idle")

        # Save backup after completion to preserve completed cycles
        self._save_queue_backup()

        # Note: Summary table auto-refreshes via presenter.queue_changed signal

        # Update progress bar to show completion
        if bar := self._sidebar_widget('queue_progress_bar'):
            try:
                cycles = self.queue_presenter.get_queue_snapshot()
                completed_cycles = self.queue_presenter.get_completed_cycles()
                bar.set_cycles(cycles, completed_cycles)
                # No cycle running now, set index to -1 (will update when next starts)
                bar.set_current_index(-1)
                logger.debug(f"✓ Progress bar updated: {len(completed_cycles)} completed, next cycle pending")
            except Exception as e:
                logger.warning(f"Could not update progress bar: {e}")

        # Disable Next Cycle button
        if btn := self._sidebar_widget('next_cycle_btn'):
            btn.setEnabled(False)

        # Auto-start next cycle or switch to auto-read
        if self.segment_queue:
            next_cycle = self.segment_queue[0]
            logger.info(f"Auto-starting next cycle: {next_cycle.type}")
            QTimer.singleShot(1000, self._on_start_button_clicked)
        else:
            # No more cycles in queue
            logger.info("✓ Queue completed - all cycles finished")

            # Re-enable Start Run button
            if btn := self._sidebar_widget('start_queue_btn'):
                btn.setEnabled(True)

            # Unlock queue when all cycles complete
            self.queue_presenter.unlock_queue()
            logger.debug("🔓 Queue unlocked after completion")

            # Create and start an auto-read cycle if enabled
            if not self._auto_read_after_queue:
                logger.info("Queue complete - auto-read disabled, stopping")
                return

            logger.info("All cycles complete - starting auto-read cycle")

            import time

            # Assign permanent ID
            self._cycle_counter += 1

            # Create an auto-read cycle (continuous monitoring, 2 hours)
            autoread_cycle = Cycle(
                type="Auto-read",
                length_minutes=120,  # 2 hours
                name="Auto-read",
                note="Automatic continuous monitoring after cycle queue completion",
                status="pending",
                units="RU",
                cycle_id=self._cycle_counter,
                timestamp=time.time(),
            )

            # Add to queue and start (use presenter for signal-driven updates)
            self.queue_presenter.add_cycle(autoread_cycle)
            logger.info("✓ Auto-read cycle created and queued")

            # Start the auto-read cycle after 1 second
            QTimer.singleShot(1000, self._on_start_button_clicked)

    def _calculate_cycle_analysis(self, cycle):
        """Calculate delta SPR and detect flags for a completed cycle.

        Args:
            cycle: Cycle object to analyze
        """
        try:
            # Calculate delta SPR (change in SPR during cycle) for all channels
            if cycle.sensorgram_time is not None and cycle.end_time_sensorgram is not None:
                # Get data from data collector
                if hasattr(self, 'data_collector') and self.data_collector:
                    start_time = cycle.sensorgram_time
                    end_time = cycle.end_time_sensorgram

                    # Get time data
                    time_data = self.data_collector.time_data

                    if len(time_data) > 0:
                        import numpy as np

                        # Find closest indices to start and end times
                        start_idx = np.argmin(np.abs(np.array(time_data) - start_time))
                        end_idx = np.argmin(np.abs(np.array(time_data) - end_time))

                        # Calculate delta SPR for all 4 channels
                        cycle.delta_spr_by_channel = {}
                        for ch in ['A', 'B', 'C', 'D']:
                            spr_data = self.data_collector.get_channel_data(ch)
                            if len(spr_data) > max(start_idx, end_idx):
                                start_spr = spr_data[start_idx]
                                end_spr = spr_data[end_idx]
                                cycle.delta_spr_by_channel[ch] = end_spr - start_spr

                        # Set legacy delta_spr to channel A for backward compatibility
                        if 'A' in cycle.delta_spr_by_channel:
                            cycle.delta_spr = cycle.delta_spr_by_channel['A']

            # Detect flags within cycle time range
            # CRITICAL: Flags use REBASED time (starting at 0 for Active Cycle)
            # We need to convert flag times to ABSOLUTE sensorgram time by adding cycle start time
            if cycle.sensorgram_time is not None and cycle.end_time_sensorgram is not None:
                if hasattr(self, 'flag_mgr') and self.flag_mgr:
                    cycle_flags = []
                    cycle_flag_data = []
                    cycle_duration = cycle.end_time_sensorgram - cycle.sensorgram_time

                    # Check all flags to see if they fall within this cycle's duration
                    # FlagManager stores flags in _flag_markers attribute
                    if hasattr(self.flag_mgr, '_flag_markers'):
                        for flag in self.flag_mgr._flag_markers:
                            # Flag time is rebased (0-based), so just check if it's within cycle duration
                            if 0 <= flag.time <= cycle_duration:
                                cycle_flags.append(flag.flag_type)
                                cycle_flag_data.append(flag.to_export_dict())
                                logger.debug(f"   Found {flag.flag_type} flag at t={flag.time:.2f}s ch={flag.channel} (within cycle)")

                        # Remove duplicates from type list and sort
                        cycle.flags = sorted(list(set(cycle_flags)))
                        # Save full flag data (preserves times, channels, SPR values)
                        cycle.flag_data = cycle_flag_data
                        if cycle.flags:
                            logger.info(f"✓ Cycle flags detected: {cycle.flags} ({len(cycle_flag_data)} flag markers saved)")

        except Exception as e:
            logger.warning(f"Failed to calculate cycle analysis: {e}")
            # Set defaults on error
            if cycle.delta_spr is None:
                cycle.delta_spr = 0.0
            if cycle.flags is None:
                cycle.flags = []

    def _on_next_cycle(self):
        """Complete the current cycle early and move to the next cycle in queue.

        This keeps the data from the current cycle (even if incomplete/bad) and
        continues the acquisition sequence without breaking anything.
        """
        if self._current_cycle is None:
            logger.warning("No cycle is currently running")
            return

        # Check if there are any cycles left in the queue
        if not self.segment_queue or len(self.segment_queue) == 0:
            logger.warning("No cycles in queue - Next Cycle disabled")
            if btn := self._sidebar_widget('next_cycle_btn'):
                btn.setEnabled(False)
            self.main_window.set_intel_message("⚠ No more cycles in queue", Colors.ERROR)
            return

        try:
            logger.info(f"⏭ Skipping to next cycle - completing {self._current_cycle.name} early")

            # Stop cycle timers
            if hasattr(self, '_cycle_timer') and self._cycle_timer.isActive():
                self._cycle_timer.stop()
            if hasattr(self, '_cycle_end_timer') and self._cycle_end_timer.isActive():
                self._cycle_end_timer.stop()
                logger.debug("✓ Cycle timers stopped")

            # Resume the 5s intelligence refresh timer
            if hasattr(self.main_window, 'intelligence_refresh_timer'):
                self.main_window.intelligence_refresh_timer.start(5000)

            # Get current end time for this cycle
            end_sensorgram_time = None
            if hasattr(self.main_window, 'full_timeline_graph'):
                timeline = self.main_window.full_timeline_graph
                if hasattr(timeline, 'stop_cursor'):
                    end_sensorgram_time = timeline.stop_cursor.value()

            # Mark cycle as completed via presenter (even though it's early)
            self.queue_presenter.mark_cycle_completed(self._current_cycle)

            # Unlock queue now that cycle is complete
            self.queue_presenter.unlock_queue()
            logger.debug("🔓 Queue unlocked after early cycle completion")

            # Get completed cycles from presenter (includes this one)
            self._completed_cycles = self.queue_presenter.get_completed_cycles()

            # Sync backward compatibility list
            self.segment_queue = self.queue_presenter.get_queue_snapshot()

            # Get cycle export data for table and recording
            cycle_export_data = self._current_cycle.to_export_dict()

            # Always add cycle to the live cycle data table (regardless of recording state)
            if hasattr(self.main_window, 'add_cycle_to_table'):
                self.main_window.add_cycle_to_table(cycle_export_data)

            # Export cycle to recording manager only if recording
            if self.recording_mgr.is_recording:
                self.recording_mgr.add_cycle(cycle_export_data)

            # Clear current cycle reference
            self._current_cycle = None
            self._cycle_end_time = None

            # Save backup after completion to preserve completed cycles
            self._save_queue_backup()

            # Remove next cycle warning line if present
            if hasattr(self, '_next_cycle_warning_line') and self._next_cycle_warning_line is not None:
                try:
                    if hasattr(self.main_window, 'cycle_of_interest_graph'):
                        self.main_window.cycle_of_interest_graph.removeItem(self._next_cycle_warning_line)
                except:
                    pass
                self._next_cycle_warning_line = None

            # Update intelligence bar
            remaining = len(self.segment_queue)
            if remaining > 0:
                self.main_window.set_intel_message(f"⏭ Moved to next cycle ({remaining} remaining in queue)", Colors.WARNING)
            else:
                self.main_window.set_intel_message("⏭ Cycle completed early - queue finished", Colors.WARNING)

            # Disable Next Cycle button
            if btn := self._sidebar_widget('next_cycle_btn'):
                btn.setEnabled(False)

            # Note: Summary table auto-refreshes via presenter.queue_changed signal

            # Auto-start next cycle if available
            if self.segment_queue:
                next_cycle = self.segment_queue[0]
                logger.info(f"Auto-starting next cycle: {next_cycle.type}")
                from PySide6.QtCore import QTimer
                QTimer.singleShot(500, self._on_start_button_clicked)  # Brief delay for UI update
            else:
                # No more cycles - start auto-read
                logger.info("All cycles complete - starting auto-read cycle")
                from affilabs.domain.cycle import Cycle

                autoread_cycle = Cycle(
                    type="Auto-read",
                    length_minutes=120,  # 2 hours
                    name="Auto-read",
                    note="Continuous monitoring after experiment completion",
                )

                # Use presenter to add cycle (triggers signal-driven updates)
                self.queue_presenter.add_cycle(autoread_cycle)
                from PySide6.QtCore import QTimer
                QTimer.singleShot(500, self._on_start_button_clicked)

            logger.info("✓ Moved to next cycle - data preserved, acquisition continues")

        except Exception as e:
            logger.exception(f"Error moving to next cycle: {e}")
            # On error, still try to clean up and continue
            self._current_cycle = None
            self._cycle_end_time = None
            if hasattr(self, '_cycle_timer'):
                self._cycle_timer.stop()
            if hasattr(self, '_cycle_end_timer'):
                self._cycle_end_timer.stop()
            # Resume the 5s intelligence refresh timer
            if hasattr(self.main_window, 'intelligence_refresh_timer'):
                self.main_window.intelligence_refresh_timer.start(5000)

    # ==================== FLAG METHODS - MOVED TO FlagManager ====================
    # _clear_flags_for_new_cycle() → flag_mgr.clear_flags_for_new_cycle()
    # _show_flag_type_menu() → flag_mgr.show_flag_type_menu()
    # _add_flag_marker() → flag_mgr.add_flag_marker()
    # _remove_flag_near_click() → flag_mgr.remove_flag_near_click()
    # _try_select_flag_for_movement() → flag_mgr.try_select_flag_for_movement()
    # _highlight_selected_flag() → flag_mgr._highlight_selected_flag()
    # _move_selected_flag() → flag_mgr.move_selected_flag()
    # _deselect_flag() → flag_mgr.deselect_flag()
    # All flag methods extracted to affilabs/managers/flag_manager.py
    # ================================================================================

    def _add_cycle_marker(self):
        """Add vertical marker on Full Sensorgram timeline at cycle start.

        Creates a single marker with label showing cycle type and concentration if available.
        """
        try:
            from pyqtgraph import InfiniteLine, TextItem

            if not hasattr(self.main_window, 'full_timeline_graph'):
                return

            timeline = self.main_window.full_timeline_graph

            # Get current time from stop cursor position (where we just moved start cursor to)
            if hasattr(timeline, 'stop_cursor'):
                current_time = timeline.stop_cursor.value()
            else:
                # Fallback to latest data point
                if not self.data_mgr.cycle_time:
                    return
                current_time = self.data_mgr.cycle_time[-1]

            # Get cycle type and abbreviate using centralized method
            cycle_type = self._abbreviate_cycle_type(self._current_cycle.type)

            # Build label text with concentration if available
            label_text = cycle_type

            # Check for concentration data (stored as temp attribute from _on_add_to_queue)
            if hasattr(self._current_cycle, '_concentrations') and self._current_cycle._concentrations:
                concentrations = self._current_cycle._concentrations
                # Get units if available
                units = getattr(self._current_cycle, '_units', 'nM')

                # If ALL channels have the same concentration, show that value
                if 'ALL' in concentrations:
                    conc_value = concentrations['ALL']
                    label_text = f"{cycle_type} {conc_value}{units}"
                else:
                    # Otherwise, show all individual channel concentrations
                    conc_list = []
                    for ch in ['A', 'B', 'C', 'D']:
                        if ch in concentrations:
                            conc_list.append(f"{ch}:{concentrations[ch]}")
                    if conc_list:
                        label_text = f"{cycle_type} {','.join(conc_list)}{units}"

            # Store sensorgram time in cycle data for table display
            self._current_cycle.sensorgram_time = current_time

            # Create vertical line marker (blue, solid)
            marker = InfiniteLine(
                pos=current_time,
                angle=90,
                pen={'color': '#007AFF', 'width': 2},
                movable=False
            )

            # Create text label to the right of marker with cycle type and concentration
            # Anchor to left-bottom so text appears to right and below top of line
            label = TextItem(
                text=label_text,
                color=(0, 122, 255),
                anchor=(0, 1.0)  # Left-bottom anchor
            )

            # Position label to the right of the marker line, near top
            try:
                y_range = timeline.viewRange()[1]
                x_range = timeline.viewRange()[0]
                # Offset label to the right by 2% of visible range
                x_offset = (x_range[1] - x_range[0]) * 0.01
                label.setPos(current_time + x_offset, y_range[1] * 0.95)
            except:
                label.setPos(current_time + 5, 100)  # Fallback position with offset

            # Add to timeline
            timeline.addItem(marker)
            timeline.addItem(label)

            # Store reference
            cycle_num = self._current_cycle.cycle_num if self._current_cycle.cycle_num > 0 else len(self._cycle_markers) + 1
            cycle_id = f"cycle_{cycle_num}"
            self._cycle_markers[cycle_id] = {'line': marker, 'label': label, 'time': current_time}

            logger.info(f"✓ Cycle marker added at t={current_time:.1f}s: {label_text}")

        except Exception as e:
            logger.debug(f"Could not add cycle marker: {e}")

    # =========================================================================
    # SEGMENT QUEUE MANAGEMENT (TEST MODE - Minimal Implementation)
    # =========================================================================

    def _on_build_method(self):
        """Open Method Builder dialog to create cycles."""
        from affilabs.widgets.method_builder_dialog import MethodBuilderDialog

        # Reuse existing dialog or create new one
        if not hasattr(self, '_method_builder_dialog') or not self._method_builder_dialog:
            self._method_builder_dialog = MethodBuilderDialog(self.main_window)
            self._method_builder_dialog.method_ready.connect(self._on_method_ready)

        self._method_builder_dialog.show()  # Non-modal - stays open
        self._method_builder_dialog.raise_()  # Bring to front
        self._method_builder_dialog.activateWindow()

    def _on_method_ready(self, action: str, cycles: list):
        """Handle method push from Method Builder dialog.

        Args:
            action: "queue" (only action now - start is in sidebar)
            cycles: List of Cycle objects
        """
        if not cycles:
            return

        logger.info(f"🔵 Method ready: {len(cycles)} cycles")

        # Add all cycles to queue
        for cycle in cycles:
            self.queue_presenter.add_cycle(cycle)
            logger.info(f"   ✓ Added '{cycle.name}' ({cycle.type}, {cycle.length_minutes} min)")

        logger.info(f"✓ Method pushed to queue - {len(cycles)} cycles added")
        logger.info(f"   Queue now has {self.queue_presenter.get_queue_size()} cycles")

        # Update method name in sidebar
        if method_label := self._sidebar_widget('method_name_label'):
            method_label.setText(f"Method ({len(cycles)} cycles)")

        # Force refresh the summary table
        if tbl := self._sidebar_widget('summary_table'):
            tbl.refresh()

    def _on_add_to_queue(self):
        """Add current cycle configuration to segment queue (TEST MODE).

        This is a minimal test implementation to validate the architecture.
        Creates a segment definition dict without executing it.
        """
        import re
        import time

        # Check queue lock (use presenter's lock state)
        if self.queue_presenter.is_queue_locked():
            logger.warning("⚠️ Queue is locked during cycle operation - cannot add")
            self.main_window.set_intel_message("⚠️ Cannot modify queue while cycle is running", Colors.WARNING)
            return

        logger.info("🔵 TEST MODE: Adding cycle to segment queue")
        logger.debug(f"   Current queue size: {self.queue_presenter.get_queue_size()} cycles")

        try:
            # Read form values
            cycle_type = self.main_window.sidebar.cycle_type_combo.currentText()
            length_text = self.main_window.sidebar.cycle_length_combo.currentText()

            # Parse duration - handle both "30 sec" and "5 min" formats
            if not length_text or not length_text.strip():
                raise ValueError("Cycle length cannot be empty")

            parts = length_text.split()
            if len(parts) == 0:
                raise ValueError("Invalid cycle length format")

            duration_value = int(parts[0])
            duration_unit = parts[1] if len(parts) > 1 else "min"

            # Convert to minutes
            if duration_unit == "sec":
                length_minutes = duration_value / 60.0  # Convert seconds to minutes
            else:
                length_minutes = duration_value  # Already in minutes

            note = self.main_window.sidebar.note_input.toPlainText()
            units = self.main_window.sidebar.units_combo.currentText().split()[
                0
            ]  # Extract unit from "nM (Nanomolar)"

            # Parse concentration tags from note
            tags = re.findall(r"\[([A-D]|ALL):(\d+\.?\d*)\]", note)
            concentrations_dict = {ch: float(val) for ch, val in tags} if tags else {}

            # Create cycle using domain model (ID assigned by presenter)
            cycle = Cycle(
                type=cycle_type,
                length_minutes=length_minutes,
                note=note,
                status="pending",
                units=units,
                concentrations=concentrations_dict,
                timestamp=time.time(),
            )

            if concentrations_dict:
                logger.debug(
                    f"Parsed concentrations: {concentrations_dict} {units}",
                )

            # Add to queue via presenter (handles ID, numbering, undo/redo)
            success = self.queue_presenter.add_cycle(cycle)

            if not success:
                raise RuntimeError("Failed to add cycle to queue (queue may be locked)")

            # Sync backward compatibility list
            self.segment_queue = self.queue_presenter.get_queue_snapshot()

            logger.info(f"✓ Added cycle {self.queue_presenter.get_queue_size()}: {cycle_type}, {length_minutes}min")
            logger.debug(f"   Queue now has {self.queue_presenter.get_queue_size()} cycles")

            if len(cycle.note) > 100:
                logger.debug(f"   Note: {cycle.note[:100]}...")
            else:
                logger.debug(f"   Note: {cycle.note}")

            # Note: Summary table auto-refreshes via presenter.queue_changed signal

            # Auto-save queue for crash recovery
            self._save_queue_backup()

        except Exception as e:
            logger.exception(f"[ERROR] Failed to add cycle to queue: {e}")
            self.main_window.set_intel_message(f"✗ Failed to add: {e}", Colors.ERROR)

    # Template methods removed - Presets now handle both single cycles and full sequences
    # def _on_save_template(self): ...
    # def _on_load_template(self): ...

    def _on_save_preset(self):
        """Handle save preset button click - save current queue as reusable preset."""
        from PySide6.QtWidgets import QInputDialog, QMessageBox

        try:
            # Check if queue has cycles
            if not self.segment_queue:
                QMessageBox.information(
                    self.main_window,
                    "Empty Queue",
                    "Queue is empty. Add cycles before saving a preset."
                )
                return

            # Prompt for preset name and description
            name, ok = QInputDialog.getText(
                self.main_window,
                "Save Queue Preset",
                "Enter name for this queue preset:",
                text=f"Queue with {len(self.segment_queue)} cycles"
            )

            if ok and name:
                description, ok2 = QInputDialog.getText(
                    self.main_window,
                    "Save Queue Preset",
                    "Enter description (optional):",
                    text=""
                )

                if ok2:  # User didn't cancel
                    # Save to storage
                    preset_id = self.preset_storage.save_preset(
                        name=name,
                        cycles=self.segment_queue.copy(),
                        description=description,
                    )

                    total_duration = sum(c.length_minutes for c in self.segment_queue)
                    logger.info(f"✓ Saved queue preset '{name}' (ID: {preset_id})")

                    # Show success message
                    QMessageBox.information(
                        self.main_window,
                        "Preset Saved",
                        f"Queue preset '{name}' saved successfully!\n\n"
                        f"Cycles: {len(self.segment_queue)}\n"
                        f"Total Duration: {total_duration:.1f} minutes"
                    )

        except Exception as e:
            logger.exception(f"[ERROR] Failed to save queue preset: {e}")
            QMessageBox.warning(
                self.main_window,
                "Save Failed",
                f"Failed to save queue preset:\n{e}"
            )

    def _on_load_preset(self):
        """Handle load preset button click - show preset browser and load queue."""
        from affilabs.widgets.queue_preset_dialog import QueuePresetDialog
        from PySide6.QtWidgets import QMessageBox

        try:
            # Warn if queue is not empty
            if self.segment_queue:
                reply = QMessageBox.question(
                    self.main_window,
                    "Replace Queue?",
                    f"Current queue has {len(self.segment_queue)} cycles.\n\n"
                    f"Loading a preset will replace the current queue.\n"
                    f"Continue?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )

                if reply != QMessageBox.Yes:
                    return

            # Create and show preset dialog
            dialog = QueuePresetDialog(self.preset_storage, self.main_window)

            # Connect preset selection to queue loading
            def load_queue(preset):
                """Load preset cycles into queue."""
                try:
                    # Clear current queue via presenter (with undo support)
                    if self.segment_queue:
                        self.queue_presenter.clear_queue()

                    # Add all preset cycles to queue
                    for cycle in preset.cycles:
                        # Create new cycle (without ID to let presenter assign)
                        new_cycle = Cycle(
                            type=cycle.type,
                            length_minutes=cycle.length_minutes,
                            note=cycle.note,
                            status="pending",
                            units=cycle.units,
                            concentrations=cycle.concentrations,
                            timestamp=time.time(),
                        )
                        self.queue_presenter.add_cycle(new_cycle)

                    # Sync backward compatibility list
                    self.segment_queue = self.queue_presenter.get_queue_snapshot()

                    # Update UI - widget auto-refreshes via presenter.queue_changed signal
                    self._save_queue_backup()

                    logger.info(f"✓ Loaded queue preset '{preset.name}' ({preset.cycle_count} cycles)")

                    QMessageBox.information(
                        self.main_window,
                        "Preset Loaded",
                        f"Queue preset '{preset.name}' loaded successfully!\n\n"
                        f"Cycles: {preset.cycle_count}\n"
                        f"Total Duration: {preset.total_duration_minutes:.1f} minutes"
                    )

                except Exception as e:
                    logger.exception(f"[ERROR] Failed to load preset queue: {e}")
                    QMessageBox.warning(
                        self.main_window,
                        "Load Failed",
                        f"Failed to load preset queue:\n{e}"
                    )

            dialog.preset_selected.connect(load_queue)

            # Show dialog
            dialog.exec()

        except Exception as e:
            logger.exception(f"[ERROR] Failed to open preset browser: {e}")
            QMessageBox.warning(
                self.main_window,
                "Load Failed",
                f"Failed to open preset browser:\n{e}"
            )

    def _on_toggle_pause_queue(self):
        """Handle pause/resume queue button click."""
        if not (btn := self._sidebar_widget('pause_queue_btn')):
            return

        try:
            if self.queue_presenter.is_paused():
                # Resume queue
                self.queue_presenter.resume_queue()
                btn.setText("⏸ Pause Queue")
                btn.setToolTip("Pause queue after current cycle completes")
                logger.info("✓ Queue resumed")

                # Update queue status label
                if lbl := self._sidebar_widget('queue_status_label'):
                    size = self.queue_presenter.get_queue_size()
                    duration = self.queue_presenter.get_total_duration()
                    lbl.setText(
                        f"Queue: {size} cycles | {duration:.1f} min total | Running"
                    )
            else:
                # Pause queue
                self.queue_presenter.pause_queue()
                btn.setText("▶ Resume Queue")
                btn.setToolTip("Resume queue execution")
                logger.info("⏸ Queue paused (will stop after current cycle)")

                # Update queue status label
                if lbl := self._sidebar_widget('queue_status_label'):
                    size = self.queue_presenter.get_queue_size()
                    remaining = size  # TODO: Track actual remaining cycles
                    lbl.setText(
                        f"Queue: Paused | {remaining} cycles remaining"
                    )
                    lbl.setStyleSheet(
                        "font-size: 11px; color: #FF9500; background: transparent; "
                        "font-weight: 600; font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    )

        except Exception as e:
            logger.exception(f"[ERROR] Failed to toggle pause/resume: {e}")

    # Note: Old _renumber_cycles() and _update_summary_table() methods removed
    # Queue widget now auto-refreshes via presenter.queue_changed signal

    def _abbreviate_cycle_type(self, cycle_type: str) -> str:
        """Centralized cycle type abbreviation logic.

        Args:
            cycle_type: Full cycle type name

        Returns:
            Abbreviated cycle type for display
        """
        if cycle_type.lower() in ('concentration', 'conc', 'conc.'):
            return 'Conc.'
        # Add more abbreviations as needed
        return cycle_type

    def _save_queue_backup(self):
        """Save current cycle queue to JSON for crash recovery."""
        try:
            import json
            from pathlib import Path

            backup_file = Path("cycle_queue_backup.json")

            # Get state from presenter (includes queue + completed cycles + counter)
            state = self.queue_presenter.get_state()

            with open(backup_file, 'w') as f:
                json.dump({
                    **state,  # Includes queue, completed_cycles, cycle_counter
                    'timestamp': time.time()
                }, f, indent=2)

            logger.debug(f"✓ Queue backup saved: {len(state['queue'])} cycles, {len(state['completed_cycles'])} completed")
        except Exception as e:
            logger.debug(f"Could not save queue backup: {e}")

    def _load_queue_backup(self):
        """Load cycle queue from backup file if it exists.

        Returns:
            bool: True if backup was loaded, False otherwise
        """
        try:
            import json
            from pathlib import Path

            backup_file = Path("cycle_queue_backup.json")
            if not backup_file.exists():
                return False

            with open(backup_file, 'r') as f:
                data = json.load(f)

            # Restore state via presenter
            success = self.queue_presenter.restore_state(data)

            if not success:
                logger.error("❌ Failed to restore queue state from backup")
                return False

            # Sync backward compatibility list
            self.segment_queue = self.queue_presenter.get_queue_snapshot()
            self._completed_cycles = self.queue_presenter.get_completed_cycles()
            self._cycle_counter = data.get('cycle_counter', 0)

            backup_time = data.get('timestamp', 0)
            age_minutes = (time.time() - backup_time) / 60

            logger.info(f"✅ Loaded queue backup: {len(self.segment_queue)} cycles, {len(self._completed_cycles)} completed (backup age: {age_minutes:.1f} min)")

            # Note: UI auto-refreshes via presenter.queue_changed signal

            return True
        except Exception as e:
            logger.debug(f"Could not load queue backup: {e}")
            return False

    def _on_queue_note_edited(self, item):
        """Handle when user edits a note in the queue table.

        Args:
            item: QTableWidgetItem that was edited
        """
        # Only handle notes column (column 4: State, Type, Duration, Start, Notes)
        if item.column() != 4:
            return

        row = item.row()

        # Verify row is valid and has a cycle
        if row < 0 or row >= len(self.segment_queue):
            logger.debug(f"Note edited in empty row {row}, ignoring")
            return

        # Get new note text from item
        new_note = item.text()

        # Remove "..." suffix if present (from truncation)
        if new_note.endswith("..."):
            new_note = new_note[:-3]

        # Update the cycle's note
        cycle = self.segment_queue[row]
        old_note = cycle.note
        cycle.note = new_note

        # Update tooltip to show full note
        item.setToolTip(new_note if new_note else "Click to edit note")

        logger.info(f"📝 Updated note for {cycle.name}: '{new_note[:50]}{'...' if len(new_note) > 50 else ''}'")

        # Auto-save queue backup after note edit
        self._save_queue_backup()

    def _on_queue_table_context_menu(self, position):
        """Show context menu for queue table (right-click to delete cycles)."""
        from PySide6.QtWidgets import QMenu, QMessageBox
        from PySide6.QtGui import QAction

        # Get the row that was clicked
        table = self.main_window.sidebar.summary_table
        row = table.rowAt(position.y())

        logger.debug(f"Right-click at position {position}, row: {row}, segment_queue length: {len(self.segment_queue)}")

        # Check if row is valid
        if row < 0 or row >= table.rowCount():
            logger.debug(f"Invalid row clicked: {row}")
            return

        # Check if this row actually has a cycle (row must be < queue length)
        if row >= len(self.segment_queue):
            logger.debug(f"Empty row clicked (row {row}, segment_queue length {len(self.segment_queue)})")
            logger.debug(f"  segment_queue contents: {[c.name for c in self.segment_queue]}")
            QMessageBox.information(
                self.main_window,
                "No Cycle",
                f"This row is empty. No cycle to delete.\n\nRow: {row}\nQueue has {len(self.segment_queue)} cycles"
            )
            return

        # Verify the row contains data by checking the cell content
        state_item = table.item(row, 0)
        if not state_item or not state_item.text() or state_item.text() == "":
            logger.debug(f"Row {row} has no data in cells")
            QMessageBox.information(
                self.main_window,
                "No Cycle",
                "This row is empty. No cycle to delete."
            )
            return

        logger.debug(f"✓ Showing right-click menu for row {row} (queue has {len(self.segment_queue)} cycles)")

        # Create context menu
        menu = QMenu(table)

        # Delete action
        cycle = self.segment_queue[row]
        delete_action = QAction(f"🗑️ Delete '{cycle.name}'", table)
        delete_action.triggered.connect(lambda: self._delete_cycle_from_queue(row))
        menu.addAction(delete_action)

        # Show menu at cursor position
        menu.exec(table.viewport().mapToGlobal(position))

    def _delete_cycle_from_queue(self, row_index: int):
        """Delete a cycle from the queue.

        Args:
            row_index: Index of the row in the summary table (0-4)
        """
        from PySide6.QtWidgets import QMessageBox

        # Check queue lock (use presenter's lock state)
        if self.queue_presenter.is_queue_locked():
            QMessageBox.warning(
                self.main_window,
                "Queue Locked",
                "Cannot delete cycles while a cycle is running.\nPlease wait for the current cycle to complete."
            )
            return

        # Validate queue exists and has cycles
        if self.queue_presenter.get_queue_size() == 0:
            logger.warning("❌ Cannot delete - queue is empty")
            return

        if row_index < 0 or row_index >= len(self.segment_queue):
            logger.warning(f"❌ Invalid row index: {row_index} (queue has {len(self.segment_queue)} cycles)")
            return

        # Get cycle info before deleting
        queue_snapshot = self.queue_presenter.get_queue_snapshot()
        cycle = queue_snapshot[row_index]
        cycle_name = cycle.name
        cycle_type = cycle.type

        # Confirm deletion with user (undo is available now)
        reply = QMessageBox.question(
            self.main_window,
            "Delete Cycle",
            f"Delete '{cycle_name}' ({cycle_type}) from queue?\n\nYou can undo this with Ctrl+Z.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            logger.info("Deletion cancelled by user")
            return

        # Delete via presenter (handles undo/redo)
        success = self.queue_presenter.delete_cycle(row_index)

        if not success:
            logger.error(f"❌ Failed to delete cycle at index {row_index}")
            return

        # Sync backward compatibility list
        self.segment_queue = self.queue_presenter.get_queue_snapshot()

        remaining = self.queue_presenter.get_queue_size()
        logger.info(f"🗑️ Deleted cycle from queue: {cycle_name} ({cycle_type}), {remaining} cycles remaining")

        # Update UI intelligence bar
        self.main_window.set_intel_message(
            f"🗑️ Deleted {cycle_name} ({remaining} {'cycle' if remaining == 1 else 'cycles'} remaining) - Press Ctrl+Z to undo",
            Colors.WARNING,
        )

        # Update queue status label with fresh count
        if lbl := self._sidebar_widget("queue_status_label"):
            if remaining == 0:
                status_text = "Queue: 0 cycles | Click 'Add to Queue' to plan batch runs"
            else:
                status_text = f"Queue: {remaining} {'cycle' if remaining == 1 else 'cycles'} | Right-click to delete"
            lbl.setText(status_text)

        # Note: Table display auto-refreshes via presenter.queue_changed signal

        logger.debug(f"✓ Queue now has {remaining} cycles after deletion")

        # Log remaining cycles for verification
        logger.info("📋 Remaining queue after deletion:")
        for i, cycle in enumerate(self.segment_queue):
            logger.info(f"  [{i}] {cycle.name} ({cycle.type}, {cycle.length_minutes} min)")

        logger.info(f"✓ Queue updated - {len(self.segment_queue)} cycles remaining")

    def _on_scan_requested(self):
        """User clicked Scan button in UI."""
        self.hardware_events.on_scan_requested()

    def _on_hardware_connected(self, status: dict):
        """Hardware connection completed and update Device Status UI."""
        self.hardware_events.on_hardware_connected(status)

        # Update internal pump section visibility based on P4PROPLUS detection
        self._update_internal_pump_visibility()

        # Update detector info in spectrum processor for detector-agnostic processing
        try:
            if hasattr(self, 'hardware_mgr') and self.hardware_mgr:
                if hasattr(self.hardware_mgr, 'usb') and self.hardware_mgr.usb:
                    # Unwrap detector if it's in an adapter
                    detector = self.hardware_mgr.usb
                    if hasattr(detector, '_usb'):
                        detector = detector._usb

                    detector_serial = getattr(detector, 'serial_number', None)
                    if detector_serial:
                        # Update spectrum processor with detector info
                        if hasattr(self, 'spectrum_viewmodels') and self.spectrum_viewmodels:
                            for vm in self.spectrum_viewmodels.values():
                                # _peak_processor is the utils.SpectrumProcessor with set_detector_info
                                if hasattr(vm, '_peak_processor') and vm._peak_processor:
                                    vm._peak_processor.set_detector_info(detector_serial=detector_serial)
                                    logger.info(f"Spectrum processor updated with detector: {detector_serial}")

                        # Update spectroscopy presenter with detector info for plot filtering
                        if hasattr(self, 'spectroscopy_presenter') and self.spectroscopy_presenter:
                            self.spectroscopy_presenter.set_detector_info(detector_serial)
                            logger.info(f"Spectroscopy presenter updated with detector: {detector_serial}")

                        # Update sidebar detector type for plot ranges
                        if hasattr(self.main_window, 'sidebar'):
                            # Determine detector type from serial
                            if detector_serial.startswith('ST'):
                                detector_type = "PhasePhotonics"
                            elif 'USB4' in detector_serial or 'FLMT' in detector_serial:
                                detector_type = "USB4000"
                            else:
                                detector_type = "USB4000"  # Default

                            if fn := self._sidebar_widget('set_detector_type'):
                                fn(detector_type)
                                logger.info(f"Sidebar updated with detector type: {detector_type}")
        except Exception as e:
            logger.error(f"Error updating detector info: {e}")

        # Update status bar connection status
        if hasattr(self.main_window, 'update_status_connection'):
            self.main_window.update_status_connection(True)

    def _update_internal_pump_visibility(self):
        """Show/hide internal pump control section based on P4PROPLUS detection."""
        try:
            # Check if we have internal pumps - use hardware manager's raw controller
            has_internal = False

            # Try hardware manager's raw controller first (most reliable)
            if hasattr(self, 'hardware_mgr') and self.hardware_mgr:
                if hasattr(self.hardware_mgr, '_ctrl_raw') and self.hardware_mgr._ctrl_raw:
                    raw_ctrl = self.hardware_mgr._ctrl_raw
                    if hasattr(raw_ctrl, 'firmware_id'):
                        has_internal = 'p4proplus' in raw_ctrl.firmware_id.lower()
                    elif hasattr(raw_ctrl, 'has_internal_pumps'):
                        has_internal = raw_ctrl.has_internal_pumps()

            # Fallback to self.ctrl (HAL adapter)
            if not has_internal and hasattr(self, 'ctrl') and self.ctrl:
                if hasattr(self.ctrl, 'has_internal_pumps'):
                    has_internal = self.ctrl.has_internal_pumps()

            # Show/hide section
            if section := self._sidebar_widget('internal_pump_section'):
                if has_internal:
                    section.show()
                    logger.info("P4PROPLUS detected - Internal Pump Control visible")
                else:
                    section.hide()
        except Exception as e:
            logger.error(f"Error updating internal pump visibility: {e}")

    def _on_hardware_disconnected(self):
        """Hardware disconnected."""
        # Check if this was an intentional disconnect (user clicked power off)
        was_intentional = self._intentional_disconnect
        if was_intentional:
            logger.info("Hardware disconnected (user-initiated)")
            self._intentional_disconnect = False  # Reset flag
        else:
            # Unexpected disconnect - show critical error
            logger.error("=" * 60)
            logger.error("CRITICAL: HARDWARE DISCONNECTED")
            logger.error("=" * 60)

        # Hide internal pump section when disconnected
        self._update_internal_pump_visibility()

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

        # Stop plunger polling timer
        if hasattr(self, '_plunger_poll_timer'):
            self._plunger_poll_timer.stop()
            logger.debug("✓ Stopped plunger polling")

        # Stop valve polling timer
        if hasattr(self, '_valve_poll_timer'):
            self._valve_poll_timer.stop()
            logger.debug("✓ Stopped valve polling")

        # Reset pump running states and sync button UI
        self._pump1_running = False
        self._pump2_running = False
        self._synced_pumps_running = False
        self._sync_pump_button_states()
        self._update_internal_pump_status("Idle", running=False)

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

        # Update status bar connection status
        if hasattr(self.main_window, 'update_status_connection'):
            self.main_window.update_status_connection(False)

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

    def _on_servo_calibration_needed(self):
        """Servo positions not found - trigger auto-calibration."""
        logger.info("🔧 Servo calibration needed signal received")
        logger.info("   Starting automatic servo calibration...")

        # Use QTimer to delay calibration start (allow connection to complete)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1000, self._run_servo_auto_calibration)

    def _log_calibration_to_database(self, calibration_data):
        """Automatically log calibration results to SQL database for ML training.

        NOTE: This feature requires proper calibration log files to be saved first.
        Currently disabled until log file saving is implemented.

        Args:
            calibration_data: CalibrationData instance with results
        """
        # Skip database logging - requires timestamped debug log files
        # The record_calibration_to_database() function expects:
        #   - debug_log_path: Path to timestamped debug log (e.g., debug_20251220_143022.log)
        #   - calibration_json_path: Optional path to calibration results JSON
        #
        # This integration will be enabled once calibration orchestrator
        # saves these files automatically during calibration runs.
        logger.debug("📊 Database logging skipped - awaiting log file integration")
        return

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
            # Subtract total paused time to prevent time jumps when resuming
            wall_clock_time = data["timestamp"] - self.experiment_start_time
            total_paused = getattr(self.data_mgr, '_total_paused_time', 0.0)
            data["elapsed_time"] = wall_clock_time - total_paused

            # Tag with current session epoch for invalidation on clear
            data["_epoch"] = self._session_epoch

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
        """Update stop cursor position (thread-safe).

        Called from processing thread via signal. Only updates if:
        - Live Data checkbox is enabled
        - User is not currently dragging the cursor

        Args:
            elapsed_time: Time value to set cursor to
        """
        try:
            # Quick check: Live Data enabled?
            if not getattr(self.main_window, "live_data_enabled", False):
                return

            # Get cursor
            stop_cursor = self.main_window.full_timeline_graph.stop_cursor

            # Don't interrupt user drag
            if getattr(stop_cursor, "moving", False):
                return

            # Update position
            stop_cursor.setValue(elapsed_time)

            # Update label in real-time
            if hasattr(stop_cursor, "label") and stop_cursor.label:
                stop_cursor.label.setFormat(f"Stop: {elapsed_time:.1f}s")

        except (AttributeError, RuntimeError):
            pass  # Cursor not ready, skip silently

    def _update_cycle_of_interest_graph(self):
        """Update the cycle of interest graph based on cursor positions."""
        from affilabs.utils.ui_update_helpers import UIUpdateHelpers

        UIUpdateHelpers.update_cycle_of_interest_graph(self)

    def _update_delta_display(self):
        """Update the Δ SPR display label with delta values BETWEEN start and stop cursors.

        Uses average of 5 points around each cursor position for more stable measurements.
        """
        if self.main_window.cycle_of_interest_graph.delta_display is None:
            return

        # numpy imported at module scope as np

        # Get Start and Stop cursor positions from full timeline graph
        start_time = self.main_window.full_timeline_graph.start_cursor.value()
        stop_time = self.main_window.full_timeline_graph.stop_cursor.value()

        # Calculate Δ SPR between start and stop cursors for each channel
        delta_values = {}
        for ch in self._idx_to_channel:
            time_data = self.buffer_mgr.cycle_data[ch].time
            spr_data = self.buffer_mgr.cycle_data[ch].spr

            if len(time_data) > 0 and len(spr_data) > 0:
                # Find indices closest to start and stop times
                start_idx = np.argmin(np.abs(time_data - start_time))
                stop_idx = np.argmin(np.abs(time_data - stop_time))

                # Average 5 points around each cursor (2 before, center, 2 after)
                # This reduces noise and provides more stable delta measurements
                def get_averaged_value(center_idx, data):
                    """Get average of 5 points centered at index."""
                    start = max(0, center_idx - 2)
                    end = min(len(data), center_idx + 3)
                    return np.mean(data[start:end])

                start_value = get_averaged_value(start_idx, spr_data)
                stop_value = get_averaged_value(stop_idx, spr_data)

                # Calculate delta: stop_value - start_value
                delta_values[ch] = stop_value - start_value
            else:
                delta_values[ch] = 0.0

        # Update label with bold text for better visibility
        self.main_window.cycle_of_interest_graph.delta_display.setText(
            f"<b>Δ SPR: Ch A: {delta_values['a']:.1f} RU  |  Ch B: {delta_values['b']:.1f} RU  |  "
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
        """Recording started - export current experiment state to metadata."""
        self.recording_events.on_recording_started(filename)

        # Log recording start event for graph marker
        self.recording_mgr.log_event("Recording Started")

        # Export initial metadata
        if self.recording_mgr.is_recording:
            # Add user profile information
            try:
                if combo := self._sidebar_widget('user_combo'):
                    current_user = combo.currentText()
                    if current_user:
                        self.recording_mgr.update_metadata('User', current_user)
                        logger.info(f"👤 Recording user: {current_user}")
            except Exception as e:
                logger.debug(f"Could not add user metadata: {e}")

            # Add device information
            device_id = getattr(self.hardware_mgr, 'device_id', 'Unknown')
            self.recording_mgr.update_metadata('device_id', device_id)

            # Save sensorgram offset (critical for cycle reconstruction)
            # This is the sensorgram time when recording started
            if hasattr(self.main_window, 'full_timeline_graph'):
                timeline = self.main_window.full_timeline_graph
                if hasattr(timeline, 'stop_cursor'):
                    sensorgram_offset = timeline.stop_cursor.value()
                    self.recording_mgr.update_metadata('sensorgram_offset_seconds', sensorgram_offset)
                    logger.info(f"📊 Recording offset: sensorgram t={sensorgram_offset:.1f}s")

            # Add channel time shifts
            for ch in ['a', 'b', 'c', 'd']:
                shift = self._channel_time_shifts.get(ch, 0.0)
                self.recording_mgr.update_metadata(f'channel_{ch}_time_shift', shift)

            # Export any existing completed cycles
            for cycle in self._completed_cycles:
                cycle_export_data = cycle.to_export_dict()
                # Note: Cycle.to_export_dict() uses 'start_time_sensorgram', but this code expects 'start_time'
                # Creating compatible format for legacy code
                legacy_export_data = {
                    'cycle_num': cycle.cycle_num,
                    'type': cycle.type,
                    'name': cycle.name,
                    'start_time': cycle.sensorgram_time or '',
                    'end_time': cycle.end_time_sensorgram or '',
                    'duration_minutes': cycle.length_minutes,
                    'status': cycle.status,
                    'note': cycle.note,
                }
                self.recording_mgr.add_cycle(legacy_export_data)

            # Export any existing flags
            if hasattr(self, '_flag_markers'):
                for flag in self._flag_markers:
                    flag_export_data = {
                        'type': flag.get('type', ''),
                        'channel': flag.get('channel', ''),
                        'time': flag.get('time', ''),
                        'spr': flag.get('spr', ''),
                        'timestamp': time.time(),
                    }
                    self.recording_mgr.add_flag(flag_export_data)

            logger.info("✓ Initial experiment state exported to recording")

    def _on_recording_stopped(self):
        """Recording stopped."""
        self.recording_events.on_recording_stopped()

    def _on_recording_error(self, error: str):
        """Recording error occurred."""
        self.recording_events.on_recording_error(error)

    def _on_event_logged(self, event: str, timestamp: float):
        """Event logged to recording."""
        logger.info(f"Event: {event}")

        # Add visual marker to timeline graph
        if hasattr(self, 'main_window') and hasattr(self.main_window, 'full_timeline_graph'):
            try:
                # Calculate elapsed time from acquisition start
                elapsed_time = None
                if hasattr(self, 'get_elapsed_time'):
                    elapsed_time = self.get_elapsed_time()

                # Only add marker if we have a valid elapsed time
                if elapsed_time is None:
                    logger.warning(f"Skipping event marker - acquisition not started yet: {event}")
                    return

                # Determine marker color based on event type
                if "Recording Started" in event:
                    color = "#00C853"  # Green for recording start
                elif "Cycle Start" in event:
                    color = "#2979FF"  # Blue for cycle start
                else:
                    color = "#FF9800"  # Orange for other events

                # Add marker to graph
                self.main_window.add_event_marker(elapsed_time, event, color)
            except Exception as e:
                logger.error(f"Failed to add event marker to graph: {e}")

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
            and (w := self._sidebar_widget("subunit_status"))
            and "Spectroscopy" in w
        ):
            indicator = w["Spectroscopy"][
                "indicator"
            ]
            status_label = w["Spectroscopy"][
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

        # Cancel active cycle if running – do NOT call _on_cycle_completed
        # because that auto-starts the next queued cycle.
        self._cancel_active_cycle()
        logger.info("🛑 Active cycle cancelled due to acquisition stop")

    # === Kinetic Operations Callbacks ===

    def _on_pump_initialized(self):
        """Pump initialized successfully."""
        logger.debug("✓ Pump initialized")
        # TODO: Enable pump controls in UI

    def _on_pump_error(self, error: str):
        """Pump error occurred - show message and update intelligence bar."""
        logger.error(f"Pump error: {error}")

        # Update intelligence bar with error
        self.main_window.set_intel_message(f"❌ Pump: {error}", "#FF3B30")

        from affilabs.widgets.message import show_message

        show_message(error, "Pump Error")

    def _on_pump_state_changed(self, state: dict):
        """Pump state changed."""
        self.peripheral_events.on_pump_state_changed(state)

    def _on_valve_switched(self, valve_info: dict):
        """Valve position changed."""
        self.peripheral_events.on_valve_switched(valve_info)

    # === PUMP MANAGER STATUS HANDLERS ===

    def _on_pump_operation_started(self, operation: str):
        """Handle pump operation started - update status board + intelligence bar."""
        logger.info(f"🔧 Pump operation started: {operation}")
        display_name = operation.replace('_', ' ').title()

        # Update intelligence bar
        self.main_window.set_intel_message(f"⚡ Pump: {display_name}", "#007AFF")

        ui = self.main_window.sidebar
        if hasattr(ui, 'flow_pump_status_label'):
            ui.flow_pump_status_label.setText(display_name)
        if hasattr(ui, 'flow_pump_status_icon'):
            ui.flow_pump_status_icon.setStyleSheet(
                "font-size: 12px; color: #34C759; background: transparent;"
            )

    def _on_pump_operation_progress(self, operation: str, progress: int, message: str):
        """Handle pump operation progress - update status board + intelligence bar."""
        display_name = operation.replace('_', ' ').title()

        # Update intelligence bar with progress
        self.main_window.set_intel_message(f"⚡ Pump: {display_name} ({progress}%)", "#007AFF")

        ui = self.main_window.sidebar
        if hasattr(ui, 'flow_pump_status_label'):
            ui.flow_pump_status_label.setText(f"{display_name} ({progress}%)")

    def _on_pump_operation_completed(self, operation: str, success: bool):
        """Handle pump operation completed - reset status board + intelligence bar."""
        status_icon = "✓" if success else "✗"
        display_name = operation.replace('_', ' ').title()
        logger.info(f"🔧 Pump operation completed: {operation} {status_icon}")

        # Update intelligence bar with result
        if success:
            self.main_window.set_intel_message(f"✓ Pump: {display_name} complete", "#34C759")
        else:
            self.main_window.set_intel_message(f"✗ Pump: {display_name} failed", "#FF3B30")

        ui = self.main_window.sidebar
        if hasattr(ui, 'flow_pump_status_label'):
            ui.flow_pump_status_label.setText("Idle")
        if hasattr(ui, 'flow_pump_status_icon'):
            ui.flow_pump_status_icon.setStyleSheet(
                "font-size: 12px; color: #86868B; background: transparent;"
            )
        if hasattr(ui, 'flow_current_rate'):
            ui.flow_current_rate.setText("0")

        # Always reset buffer button text when any pump operation completes
        # (buffer may have been stopped by cycle transition or injection)
        if btn := self._sidebar_widget('start_buffer_btn'):
            btn.setText("▶ Start Buffer")

    def _on_pump_status_updated(self, status: str, flow_rate: float, plunger_pos: float, contact_time_current: float, contact_time_expected: float):
        """Handle real-time pump status update - update all status board values."""
        ui = self.main_window.sidebar
        if hasattr(ui, 'flow_pump_status_label'):
            ui.flow_pump_status_label.setText(status)
        if hasattr(ui, 'flow_pump_status_icon'):
            color = Colors.SUCCESS if status != "Idle" else Colors.SECONDARY_TEXT
            ui.flow_pump_status_icon.setStyleSheet(
                f"font-size: 12px; color: {color}; background: transparent;"
            )
        if hasattr(ui, 'flow_current_rate'):
            ui.flow_current_rate.setText(f"{flow_rate:.0f}")
        if hasattr(ui, 'flow_plunger_position'):
            ui.flow_plunger_position.setText(f"{plunger_pos:.0f}")
        if hasattr(ui, 'flow_contact_time'):
            # Display as "current / expected" format (e.g., "22 / 120")
            if contact_time_expected > 0:
                ui.flow_contact_time.setText(f"{contact_time_current:.0f} / {contact_time_expected:.0f}")
            else:
                ui.flow_contact_time.setText(f"{contact_time_current:.1f}")

    def _poll_plunger_position(self):
        """Poll plunger position every 5 seconds and update flow status board."""
        if not self.pump_mgr or not self.pump_mgr.is_available:
            return

        # Only poll when pump is actively running
        if self.pump_mgr.is_idle:
            return

        try:
            pump = self.hardware_mgr.pump
            if pump and hasattr(pump, '_pump') and pump._pump and hasattr(pump._pump, 'pump'):
                # Get plunger positions from both pumps
                p1_pos = pump._pump.pump.get_plunger_position(1) or 0.0
                p2_pos = pump._pump.pump.get_plunger_position(2) or 0.0

                # Update UI with average position
                avg_pos = (p1_pos + p2_pos) / 2.0
                ui = self.main_window.sidebar
                if hasattr(ui, 'flow_plunger_position'):
                    ui.flow_plunger_position.setText(f"{avg_pos:.0f}")

                # Log positions during active operation
                logger.debug(f"P1: {p1_pos:.1f} uL | P2: {p2_pos:.1f} uL")
        except Exception as e:
            logger.debug(f"Plunger position error: {e}")

    def _poll_valve_positions(self):
        """Poll valve positions every 3 seconds and sync UI to hardware state."""
        ctrl = self.hardware_mgr._ctrl_raw
        if not ctrl:
            return

        try:
            # Only poll valves if controller supports them (P4PRO has 6-port valves, P4SPR doesn't)
            if not hasattr(ctrl, 'knx_six_state'):
                return

            # Valve state is tracked by controller based on last command sent
            # We update UI when commands are sent, so polling just ensures consistency
            kc1_loop = ctrl.knx_six_state(1)
            kc2_loop = ctrl.knx_six_state(2)
            kc1_channel = ctrl.knx_three_state(1)
            kc2_channel = ctrl.knx_three_state(2)

            ui = self.main_window.sidebar

            # Update UI only if we have a cached state
            if kc1_loop is not None and hasattr(ui, 'kc1_loop_btn_load'):
                ui.kc1_loop_btn_load.blockSignals(True)
                ui.kc1_loop_btn_sensor.blockSignals(True)
                # Uncheck both first to prevent overlap, then set correct state
                ui.kc1_loop_btn_load.setChecked(False)
                ui.kc1_loop_btn_sensor.setChecked(False)
                if kc1_loop == 0:
                    ui.kc1_loop_btn_load.setChecked(True)
                else:
                    ui.kc1_loop_btn_sensor.setChecked(True)
                ui.kc1_loop_btn_load.blockSignals(False)
                ui.kc1_loop_btn_sensor.blockSignals(False)

            if kc2_loop is not None and hasattr(ui, 'kc2_loop_btn_load'):
                ui.kc2_loop_btn_load.blockSignals(True)
                ui.kc2_loop_btn_sensor.blockSignals(True)
                # Uncheck both first to prevent overlap, then set correct state
                ui.kc2_loop_btn_load.setChecked(False)
                ui.kc2_loop_btn_sensor.setChecked(False)
                if kc2_loop == 0:
                    ui.kc2_loop_btn_load.setChecked(True)
                else:
                    ui.kc2_loop_btn_sensor.setChecked(True)
                ui.kc2_loop_btn_load.blockSignals(False)
                ui.kc2_loop_btn_sensor.blockSignals(False)

            # Update KC1 Channel (A/B)
            # state=0: A active, state=1: B active
            if kc1_channel is not None and hasattr(ui, 'kc1_channel_btn_a'):
                ui.kc1_channel_btn_a.blockSignals(True)
                ui.kc1_channel_btn_b.blockSignals(True)
                # Uncheck both first to prevent overlap, then set correct state
                ui.kc1_channel_btn_a.setChecked(False)
                ui.kc1_channel_btn_b.setChecked(False)
                if kc1_channel == 0:
                    ui.kc1_channel_btn_a.setChecked(True)
                else:
                    ui.kc1_channel_btn_b.setChecked(True)
                ui.kc1_channel_btn_a.blockSignals(False)
                ui.kc1_channel_btn_b.blockSignals(False)

            # Update KC2 Channel (C/D)
            # state=0: C active, state=1: D active
            if kc2_channel is not None and hasattr(ui, 'kc2_channel_btn_c'):
                ui.kc2_channel_btn_c.blockSignals(True)
                ui.kc2_channel_btn_d.blockSignals(True)
                # Uncheck both first to prevent overlap, then set correct state
                ui.kc2_channel_btn_c.setChecked(False)
                ui.kc2_channel_btn_d.setChecked(False)
                if kc2_channel == 0:
                    ui.kc2_channel_btn_c.setChecked(True)
                else:
                    ui.kc2_channel_btn_d.setChecked(True)
                ui.kc2_channel_btn_c.blockSignals(False)
                ui.kc2_channel_btn_d.blockSignals(False)

        except Exception as e:
            logger.debug(f"Valve poll error: {e}")

    # === FLOW TAB HANDLERS ===

    def _on_pump_prime_clicked(self):
        """User clicked Prime Pump button - run prime sequence via PumpManager."""
        logger.info("🔧 Prime Pump requested")

        if not self.pump_mgr.is_available:
            from affilabs.widgets.message import show_message
            show_message("AffiPump not connected. Connect pump to use this feature.", "Warning")
            return

        if not self.pump_mgr.is_idle:
            from affilabs.widgets.message import show_message
            show_message(f"Pump is currently {self.pump_mgr.current_operation.name}. Wait for completion.", "Warning")
            return

        # Read prime speed from UI spinbox if available
        prime_speed = 24000.0  # default µL/min
        ui = self.main_window.sidebar
        if hasattr(ui, 'prime_spin'):
            prime_speed = ui.prime_spin.value()
            logger.info(f"Using prime speed from UI: {prime_speed} µL/min")

        # Run prime pump in background
        def run_prime():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.prime_pump(
                    aspirate_speed=prime_speed,
                    dispense_speed=min(prime_speed, 5000.0),
                ))
            finally:
                loop.close()

        thread = threading.Thread(target=run_prime, daemon=True, name="PrimePump")
        thread.start()

    def _on_pump_cleanup_clicked(self):
        """User clicked Clean Pump button - run cleanup sequence via PumpManager."""
        logger.info("🧹 Pump Cleanup requested")

        if not self.pump_mgr.is_available:
            from affilabs.widgets.message import show_message
            show_message("AffiPump not connected. Connect pump to use this feature.", "Warning")
            return

        if not self.pump_mgr.is_idle:
            from affilabs.widgets.message import show_message
            show_message(f"Pump is currently {self.pump_mgr.current_operation.name}. Wait for completion.", "Warning")
            return

        # Run cleanup in background
        def run_cleanup():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.cleanup_pump())
            finally:
                loop.close()

        thread = threading.Thread(target=run_cleanup, daemon=True, name="CleanupPump")
        thread.start()

    def _on_inject_simple_clicked(self):
        """User clicked Simple Inject button - run simple injection via PumpManager."""
        logger.info("💉 Simple Injection requested")

        # Check for EITHER AffiPump OR P4PROPLUS internal pumps
        has_affipump = self.pump_mgr.is_available
        has_internal = (self.hardware_mgr.ctrl and
                       hasattr(self.hardware_mgr.ctrl, 'has_internal_pumps') and
                       self.hardware_mgr.ctrl.has_internal_pumps())

        if not has_affipump and not has_internal:
            from affilabs.widgets.message import show_message
            show_message("No pump available. Connect AffiPump or use P4PROPLUS with internal pumps.", "Warning")
            return

        # If using AffiPump, check if it's idle
        if has_affipump and not self.pump_mgr.is_idle:
            from affilabs.widgets.message import show_message
            show_message(f"Pump is currently {self.pump_mgr.current_operation.name}. Wait for completion.", "Warning")
            return

        # Get assay rate from UI (default 100 µL/min if not available)
        assay_rate = 100.0
        if spin := self._sidebar_widget('pump_assay_spin'):
            assay_rate = float(spin.value())

        logger.info(f"  Using assay rate: {assay_rate} uL/min")

        # Run simple inject in background
        def run_inject():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.inject_simple(assay_rate))
            finally:
                loop.close()

        thread = threading.Thread(target=run_inject, daemon=True, name="InjectSimple")
        thread.start()

    def _on_inject_partial_clicked(self):
        """User clicked Partial Loop Inject button - run partial loop injection via PumpManager."""
        logger.info("💉 Partial Loop Injection requested")

        # Check for EITHER AffiPump OR P4PROPLUS internal pumps
        has_affipump = self.pump_mgr.is_available
        has_internal = (self.hardware_mgr.ctrl and
                       hasattr(self.hardware_mgr.ctrl, 'has_internal_pumps') and
                       self.hardware_mgr.ctrl.has_internal_pumps())

        if not has_affipump and not has_internal:
            from affilabs.widgets.message import show_message
            show_message("No pump available. Connect AffiPump or use P4PROPLUS with internal pumps.", "Warning")
            return

        if not self.pump_mgr.is_idle:
            from affilabs.widgets.message import show_message
            show_message(f"Pump is currently {self.pump_mgr.current_operation.name}. Wait for completion.", "Warning")
            return

        # Get assay rate from UI (default 100 µL/min if not available)
        assay_rate = 100.0
        if spin := self._sidebar_widget('pump_assay_spin'):
            assay_rate = float(spin.value())

        logger.info(f"  Using assay rate: {assay_rate} uL/min")

        # Run partial loop inject in background
        def run_inject_partial():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.inject_partial_loop(assay_rate))
            finally:
                loop.close()

        thread = threading.Thread(target=run_inject_partial, daemon=True, name="InjectPartialLoop")
        thread.start()

    def _on_start_buffer_clicked(self):
        """User clicked Start Buffer button - toggle continuous buffer flow.

        If buffer is running, stop it. If idle, start continuous buffer flow.
        """
        if not self.pump_mgr.is_available:
            from affilabs.widgets.message import show_message
            show_message("AffiPump not connected. Connect pump to use this feature.", "Warning")
            return

        # If buffer is currently running, stop it
        if self.pump_mgr.current_operation == self.PumpOperation.RUNNING_BUFFER:
            logger.info("⏸️ Stopping buffer flow...")

            # Request stop
            self.pump_mgr.cancel_operation()

            # Update button text back to Start
            if btn := self._sidebar_widget('start_buffer_btn'):
                btn.setText("▶ Start Buffer")

            # Update status immediately to show stopping state
            ui = self.main_window.sidebar
            if hasattr(ui, 'flow_pump_status_label'):
                ui.flow_pump_status_label.setText("Stopping...")
            if hasattr(ui, 'flow_pump_status_icon'):
                ui.flow_pump_status_icon.setStyleSheet(
                    "font-size: 12px; color: #FF9500; background: transparent;"
                )
            return

        # Otherwise, start buffer flow
        logger.info("▶️ Start Buffer requested")

        if not self.pump_mgr.is_idle:
            from affilabs.widgets.message import show_message
            show_message(f"Pump is currently {self.pump_mgr.current_operation.name}. Wait for completion.", "Warning")
            return

        # Get setup flow rate from UI (default 25 µL/min if not available)
        flow_rate = 25.0
        if spin := self._sidebar_widget('pump_setup_spin'):
            flow_rate = float(spin.value())

        logger.info(f"  Using flow rate: {flow_rate} uL/min")

        # Update button text to Stop
        if btn := self._sidebar_widget('start_buffer_btn'):
            btn.setText("⏸ Stop Buffer")

        # Run continuous buffer flow in background (0 cycles = run until stopped)
        def run_buffer_flow():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.run_buffer(
                    cycles=0,  # Continuous until stopped
                    duration_min=0,  # No time limit
                    volume_ul=1000.0,
                    flow_rate=flow_rate
                ))
            finally:
                loop.close()

        thread = threading.Thread(target=run_buffer_flow, daemon=True, name="BufferFlow")
        thread.start()

    def _on_flush_loop_clicked(self):
        """User clicked Flush Loop button - flush sample loop with buffer."""
        logger.info("🔄 Flush Loop requested")

        if not self.pump_mgr.is_available:
            from affilabs.widgets.message import show_message
            show_message("AffiPump not connected. Connect pump to use this feature.", "Warning")
            return

        if not self.pump_mgr.is_idle:
            from affilabs.widgets.message import show_message
            show_message(f"Pump is currently {self.pump_mgr.current_operation.name}. Wait for completion.", "Warning")
            return

        # Get flush rate from advanced settings or use default (5000 µL/min)
        flush_rate = 5000.0
        if w := self._sidebar_widget('pump_flush_rate'):
            flush_rate = float(w)

        logger.info(f"  Using flush rate: {flush_rate} uL/min")

        # Run buffer for 3 cycles to flush the loop
        def run_flush():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.run_buffer(
                    cycles=3,  # 3 cycles to flush loop
                    duration_min=0,
                    volume_ul=1000.0,
                    flow_rate=flush_rate
                ))
            finally:
                loop.close()

        thread = threading.Thread(target=run_flush, daemon=True, name="FlushLoop")
        thread.start()

    def _on_home_pumps_clicked(self):
        """User clicked Home Pumps button - home both pumps to zero position."""
        logger.info("🏠 Home Pumps requested")

        if not self.pump_mgr.is_available:
            from affilabs.widgets.message import show_message
            show_message("AffiPump not connected. Connect pump to use this feature.", "Warning")
            return

        if not self.pump_mgr.is_idle:
            from affilabs.widgets.message import show_message
            show_message(f"Pump is currently {self.pump_mgr.current_operation.name}. Wait for completion or use STOP button.", "Warning")
            return

        # Home both pumps
        def run_home():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.home_pumps())
            finally:
                loop.close()

        thread = threading.Thread(target=run_home, daemon=True, name="HomePumps")
        thread.start()

    def _on_emergency_stop_clicked(self):
        """User clicked Emergency Stop button - immediately terminate all operations."""
        logger.warning("🛑 EMERGENCY STOP requested by user")

        if not self.pump_mgr.is_available:
            from affilabs.widgets.message import show_message
            show_message("AffiPump not connected.", "Warning")
            return

        # Execute emergency stop (no idle check - always allow)
        def run_emergency_stop():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.emergency_stop())
            finally:
                loop.close()

        thread = threading.Thread(target=run_emergency_stop, daemon=True, name="EmergencyStop")
        thread.start()

    def _on_flow_rate_changed(self, rate_name: str, value: float):
        """User changed a flow rate spinbox - apply on-the-fly if pump is running.

        Args:
            rate_name: Name of the rate that changed (Setup, Functionalization, Assay)
            value: New flow rate value in µL/min
        """
        if not self.pump_mgr.is_available:
            return

        # If pump is currently running, apply on-the-fly change
        if not self.pump_mgr.is_idle:
            logger.info(f"💧 {rate_name} flow rate changed to {value} uL/min (pump running - applying on-the-fly)")
            self.pump_mgr.change_flow_rate_on_the_fly(value)
        else:
            logger.debug(f"{rate_name} flow rate set to {value} uL/min (pump idle - will use on next operation)")

    # =========================================================================
    # Internal Pump Background Task Classes (Reusable)
    # =========================================================================

    class _PumpStartTask:
        """Background task for starting internal pumps without UI blocking."""
        def __init__(self, ctrl, flow_rate, channel, callback):
            self._runnable = self._create_runnable(ctrl, flow_rate, channel, callback)

        @staticmethod
        def _create_runnable(ctrl, flow_rate, channel, callback):
            from PySide6.QtCore import QRunnable

            class _Runnable(QRunnable):
                def __init__(self):
                    super().__init__()
                    self.ctrl = ctrl
                    self.flow_rate = flow_rate
                    self.channel = channel
                    self.callback = callback

                def run(self):
                    try:
                        success = self.ctrl.pump_start(rate_ul_min=self.flow_rate, ch=self.channel)
                    except Exception as e:
                        # Ensure pump errors never crash the UI thread
                        try:
                            logger.error(f"Error starting internal pump {self.channel}: {e}")
                        except Exception:
                            pass
                        success = False

                    try:
                        self.callback(success)
                    except Exception:
                        # Callback errors should not crash the thread pool
                        pass

            return _Runnable()

        def start(self):
            from PySide6.QtCore import QThreadPool
            QThreadPool.globalInstance().start(self._runnable)

    class _PumpStopTask:
        """Background task for stopping internal pumps without UI blocking."""
        def __init__(self, ctrl, channel, callback):
            self._runnable = self._create_runnable(ctrl, channel, callback)

        @staticmethod
        def _create_runnable(ctrl, channel, callback):
            from PySide6.QtCore import QRunnable

            class _Runnable(QRunnable):
                def __init__(self):
                    super().__init__()
                    self.ctrl = ctrl
                    self.channel = channel
                    self.callback = callback

                def run(self):
                    try:
                        success = self.ctrl.pump_stop(ch=self.channel)
                    except Exception as e:
                        # Ensure pump errors never crash the UI thread
                        try:
                            logger.error(f"Error stopping internal pump {self.channel}: {e}")
                        except Exception:
                            pass
                        success = False

                    try:
                        self.callback(success)
                    except Exception:
                        # Callback errors should not crash the thread pool
                        pass

            return _Runnable()

        def start(self):
            from PySide6.QtCore import QThreadPool
            QThreadPool.globalInstance().start(self._runnable)

    # =========================================================================
    # Internal Pump Toggle Handlers
    # =========================================================================

    def _on_internal_pump1_toggle(self, checked: bool):
        """Toggle internal pump 1 on/off.

        Args:
            checked: True = start pump, False = stop pump
        """
        if not (spin := self._sidebar_widget('pump1_rpm_spin')):
            logger.error("Pump 1 RPM spinbox not found")
            return

        if checked:
            # Start pump
            rpm = spin.value()
            correction = getattr(self.main_window.sidebar.pump1_correction_spin, 'value', lambda: 1.0)()
            rpm_corrected = rpm * correction
            logger.debug(f"[PUMP CMD] Pump 1 Start - Spinbox: {rpm} uL/min, Correction: {correction:.3f}, Sending: {rpm_corrected:.1f} uL/min")

            ctrl = self.hardware_mgr._ctrl_raw
            if not ctrl:
                from affilabs.widgets.message import show_message
                show_message("Controller not connected", "Warning")
                btn = self.main_window.sidebar.pump1_toggle_btn
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
                return

            if hasattr(ctrl, 'has_internal_pumps') and ctrl.has_internal_pumps():
                rpm_corrected = rpm * correction

                logger.info(f"▶ Starting internal pump 1: {rpm_corrected:.1f} RPM (correction: {correction})")

                # Update UI immediately to prevent lag
                btn = self.main_window.sidebar.pump1_toggle_btn
                btn.setText("■ Stop")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                self._update_internal_pump_status(f"Pump 1: {rpm_corrected:.0f} RPM", running=True)

                # Run hardware command in background thread to prevent UI blocking
                def on_start_complete(success):
                    if success:
                        logger.info(f"✓ Started pump 1 at {rpm_corrected:.1f} RPM")
                        self._pump1_running = True  # Track state
                    else:
                        logger.error("✗ Failed to start internal pump")
                        self._pump1_running = False
                        # Revert button state on failure (block signals to prevent toggle loop)
                        btn.blockSignals(True)
                        btn.setChecked(False)
                        btn.blockSignals(False)
                        btn.setText("▶ Start")
                        btn.style().unpolish(btn)
                        btn.style().polish(btn)
                        self._update_internal_pump_status("Idle", running=False)

                # ALWAYS channel 1 for pump1 (not affected by sync mode)
                task = self._PumpStartTask(ctrl, rpm_corrected, 1, on_start_complete)
                task.start()
            else:
                from affilabs.widgets.message import show_message
                show_message("Internal pumps not available. P4PRO+ V2.3+ required.", "Warning")
                btn = self.main_window.sidebar.pump1_toggle_btn
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
        else:
            # Stop pump
            ctrl = self.hardware_mgr._ctrl_raw
            if ctrl and hasattr(ctrl, 'has_internal_pumps') and ctrl.has_internal_pumps():
                logger.info("■ Stopping internal pump 1")

                # Update UI immediately to prevent lag
                btn = self.main_window.sidebar.pump1_toggle_btn
                btn.setText("▶ Start")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                self._update_internal_pump_status("Idle", running=False)

                # Run hardware command in background thread
                def on_stop_complete(success):
                    if success:
                        logger.info("✓ Stopped pump 1")
                        self._pump1_running = False  # Track state
                    else:
                        logger.error("✗ Failed to stop pump 1")
                        # Keep state as running if stop failed
                        logger.warning("Pump 1 may still be running!")

                task = self._PumpStopTask(ctrl, 1, on_stop_complete)
                task.start()

    def _on_synced_flowrate_changed(self):
        """Update status display when synced flowrate combo changes while pumps are running."""
        # Only update if pumps are currently running
        if not hasattr(self, '_synced_pumps_running') or not self._synced_pumps_running:
            return

        if not (combo := self._sidebar_widget('synced_flowrate_combo')):
            return

        # Get current flowrate setting
        flowrate_map = {0: 25, 1: 50, 2: 100, 3: 200, 4: 220}
        idx = combo.currentIndex()
        flow_rate = flowrate_map.get(idx, 50)

        # Get pump corrections
        correction_p1 = 1.0
        correction_p2 = 1.0
        ctrl = self.hardware_mgr._ctrl_raw
        if ctrl and hasattr(ctrl, 'get_pump_corrections'):
            try:
                corrections = ctrl.get_pump_corrections()
                if corrections and isinstance(corrections, dict):
                    correction_p1 = corrections.get(1, 1.0)
                    correction_p2 = corrections.get(2, 1.0)
                elif corrections and isinstance(corrections, tuple) and len(corrections) == 2:
                    correction_p1, correction_p2 = corrections
            except Exception:
                pass

        rpm_p1 = flow_rate * correction_p1
        rpm_p2 = flow_rate * correction_p2

        # Update status display with new flowrate
        self._update_internal_pump_status(f"Both Pumps: P1={rpm_p1:.0f} P2={rpm_p2:.0f} µL/min", running=True)
        logger.debug(f"Status updated: flowrate changed to {flow_rate} µL/min (P1={rpm_p1:.0f}, P2={rpm_p2:.0f})")

    def _on_synced_pump_toggle(self, checked: bool):
        """Toggle synced pumps (both pumps) on/off.

        Args:
            checked: True = start both pumps, False = stop both pumps
        """
        if not (combo := self._sidebar_widget('synced_flowrate_combo')):
            logger.error("Synced flowrate combo not found")
            return

        if checked:
            # Start both pumps
            # Get flowrate from combo box
            flowrate_map = {0: 25, 1: 50, 2: 100, 3: 200, 4: 220}
            idx = combo.currentIndex()
            flow_rate = flowrate_map.get(idx, 50)

            # Get pump corrections from controller EEPROM
            correction_p1 = 1.0
            correction_p2 = 1.0

            ctrl = self.hardware_mgr._ctrl_raw
            if ctrl and hasattr(ctrl, 'get_pump_corrections'):
                try:
                    corrections = ctrl.get_pump_corrections()
                    if corrections and isinstance(corrections, dict):
                        correction_p1 = corrections.get(1, 1.0)
                        correction_p2 = corrections.get(2, 1.0)
                        logger.debug(f"✓ Loaded pump corrections from EEPROM: P1={correction_p1:.3f}, P2={correction_p2:.3f}")
                    elif corrections and isinstance(corrections, tuple) and len(corrections) == 2:
                        correction_p1, correction_p2 = corrections
                        logger.debug(f"✓ Loaded pump corrections from EEPROM: P1={correction_p1:.3f}, P2={correction_p2:.3f}")
                except Exception as e:
                    logger.debug(f"Could not read pump corrections from EEPROM, using defaults: {e}")

            logger.debug(f"[PUMP CMD] Synced flowrate: {flow_rate} uL/min, P1 correction: {correction_p1:.3f}, P2 correction: {correction_p2:.3f}")

            ctrl = self.hardware_mgr._ctrl_raw
            if not ctrl:
                from affilabs.widgets.message import show_message
                show_message("Controller not connected", "Warning")
                btn = self.main_window.sidebar.synced_toggle_btn
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
                return

            if hasattr(ctrl, 'has_internal_pumps') and ctrl.has_internal_pumps():
                # Apply individual corrections
                rpm_p1 = flow_rate * correction_p1
                rpm_p2 = flow_rate * correction_p2

                logger.info(f"▶ Starting both pumps: P1={rpm_p1:.1f} µL/min (×{correction_p1:.3f}), P2={rpm_p2:.1f} µL/min (×{correction_p2:.3f})")

                # Update UI immediately to prevent lag
                btn = self.main_window.sidebar.synced_toggle_btn
                btn.setText("■ Stop")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                self._update_internal_pump_status(f"Both Pumps: P1={rpm_p1:.0f} P2={rpm_p2:.0f} µL/min", running=True)

                # Start both pumps with individual corrections
                success_p1 = ctrl.pump_start(rate_ul_min=rpm_p1, ch=1)
                success_p2 = ctrl.pump_start(rate_ul_min=rpm_p2, ch=2)
                success = success_p1 and success_p2

                if success:
                    logger.info(f"✓ Started both pumps: P1={rpm_p1:.1f} µL/min, P2={rpm_p2:.1f} µL/min")
                    self._synced_pumps_running = True
                    self._pump1_running = True
                    self._pump2_running = True
                else:
                    logger.error(f"✗ Failed to start synced pumps (P1={success_p1}, P2={success_p2})")
                    self._synced_pumps_running = False
                    # Revert button state on failure
                    btn.blockSignals(True)
                    btn.setChecked(False)
                    btn.blockSignals(False)
                    btn.setText("▶ Start")
                    btn.style().unpolish(btn)
                    btn.style().polish(btn)
                    self._update_internal_pump_status("Idle", running=False)
            else:
                from affilabs.widgets.message import show_message
                show_message("Internal pumps not available. P4PRO+ V2.3+ required.", "Warning")
                btn = self.main_window.sidebar.synced_toggle_btn
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
        else:
            # Stop both pumps
            ctrl = self.hardware_mgr._ctrl_raw
            if ctrl and hasattr(ctrl, 'has_internal_pumps') and ctrl.has_internal_pumps():
                logger.info("■ Stopping both internal pumps")

                # Update UI immediately to prevent lag
                btn = self.main_window.sidebar.synced_toggle_btn
                btn.setText("▶ Start")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                self._update_internal_pump_status("Idle", running=False)

                # Run hardware command in background thread
                def on_stop_complete(success):
                    if success:
                        logger.info("✓ Stopped both pumps")
                        self._synced_pumps_running = False  # Track state
                        self._pump1_running = False
                        self._pump2_running = False
                    else:
                        logger.error("✗ Failed to stop both pumps")
                        logger.warning("Pumps may still be running!")

                task = self._PumpStopTask(ctrl, 3, on_stop_complete)
                task.start()

    def _on_internal_pump_inject_30s(self):
        """Run inject sequence using internal pumps with user-selected contact time.

        In Manual mode: Toggle valve open/close without automatic timer
        In Auto mode: Use contact time with automatic valve close
        """

        # Check if Manual mode is enabled
        manual_mode = False
        if chk := self._sidebar_widget('synced_manual_time_check'):
            manual_mode = chk.isChecked()

        # MANUAL MODE: Toggle valve open/close
        if manual_mode:
            # Check if valve is currently open
            valve_open = getattr(self, '_manual_valve_open', False)

            ctrl = self.hardware_mgr._ctrl_raw
            if not ctrl or not hasattr(ctrl, 'has_internal_pumps') or not ctrl.has_internal_pumps():
                from affilabs.widgets.message import show_message
                show_message("Controller not connected or internal pumps unavailable", "Warning")
                return

            # Check if valve sync is enabled
            valve_sync_enabled = False
            if btn := self._sidebar_widget('sync_valve_btn'):
                valve_sync_enabled = btn.isChecked()

            channel_text = "KC1 & KC2" if valve_sync_enabled else "KC1"

            if not valve_open:
                # Open valves
                try:
                    if valve_sync_enabled:
                        valve_success = ctrl.knx_six_both(state=1, timeout_seconds=None)
                    else:
                        valve_success = ctrl.knx_six(state=1, ch=1, timeout_seconds=None)

                    if valve_success:
                        self._manual_valve_open = True
                        self._update_internal_pump_status(f"VALVE OPEN ({channel_text}) - MANUAL", running=True)
                        logger.info(f"✓ Manual mode: {channel_text} valve(s) OPENED")

                        # Update button to manual open state
                        if btn := self._sidebar_widget('internal_pump_inject_30s_btn'):
                            btn.setText("⬇ Close Valve")
                            btn.setProperty("injection_state", "manual")
                            btn.setToolTip("🔄 Click to close valve")
                            btn.style().unpolish(btn)
                            btn.style().polish(btn)
                    else:
                        logger.warning(f"Failed to open {channel_text} valve(s)")
                except Exception as e:
                    logger.error(f"Error opening valves: {e}")
            else:
                # Close valves
                try:
                    if valve_sync_enabled:
                        valve_success = ctrl.knx_six_both(state=0, timeout_seconds=None)
                    else:
                        valve_success = ctrl.knx_six(state=0, ch=1, timeout_seconds=None)

                    if valve_success:
                        self._manual_valve_open = False
                        self._update_internal_pump_status("Idle", running=False)
                        logger.info(f"✓ Manual mode: {channel_text} valve(s) CLOSED")

                        # Update button back to ready state
                        if btn := self._sidebar_widget('internal_pump_inject_30s_btn'):
                            btn.setText("💉 Inject")
                            btn.setProperty("injection_state", "ready")
                            btn.setToolTip("✅ Ready to inject")
                            btn.style().unpolish(btn)
                            btn.style().polish(btn)
                    else:
                        logger.warning(f"Failed to close {channel_text} valve(s)")
                except Exception as e:
                    logger.error(f"Error closing valves: {e}")

            return  # Exit early in manual mode

        # AUTO MODE: Original behavior with contact time
        # Get contact time from spinbox (preset modes only)
        contact_time_s = 60  # Default fallback
        if spin := self._sidebar_widget('synced_contact_time_spin'):
            contact_time_s = spin.value()
        elif spin := self._sidebar_widget('pump2_contact_time_spin'):
            contact_time_s = spin.value()

        logger.info(f"💉 Starting inject sequence ({contact_time_s}s contact time, internal pumps)")

        # Get flowrate from combo box
        flowrate_map = {0: 25, 1: 50, 2: 100, 3: 200, 4: 220}
        idx = 1  # Default to 50
        if combo := self._sidebar_widget('synced_flowrate_combo'):
            idx = combo.currentIndex()
        rpm = flowrate_map.get(idx, 50)

        # Rule: For P4PRO+ internal pump, when flowrate is 25 µL/min,
        # set contact time to 180 seconds automatically.
        try:
            ctrl = self.hardware_mgr._ctrl_raw
        except Exception:
            ctrl = None
        if ctrl and hasattr(ctrl, 'has_internal_pumps') and ctrl.has_internal_pumps():
            if float(rpm) == 25.0:
                contact_time_s = 180
                logger.info("⏱ Contact time overridden to 180s for 25 µL/min (P4PRO+ internal pump)")

        ctrl = self.hardware_mgr._ctrl_raw
        if not ctrl:
            from affilabs.widgets.message import show_message
            show_message("Controller not connected", "Warning")
            return

        if hasattr(ctrl, 'has_internal_pumps') and ctrl.has_internal_pumps():
            # FLUSH PULSE: Start both pumps at 220 µL/min for first 6 seconds,
            # then reduce both to the selected target flowrate.
            # Apply individual pump corrections from controller EEPROM
            flush_rate = 220.0
            target_rate = float(rpm)

            # Get pump corrections from controller EEPROM
            correction_p1 = 1.0
            correction_p2 = 1.0

            if ctrl and hasattr(ctrl, 'get_pump_corrections'):
                try:
                    corrections = ctrl.get_pump_corrections()
                    if corrections and isinstance(corrections, dict):
                        correction_p1 = corrections.get(1, 1.0)
                        correction_p2 = corrections.get(2, 1.0)
                    elif corrections and isinstance(corrections, tuple) and len(corrections) == 2:
                        correction_p1, correction_p2 = corrections
                except Exception as e:
                    logger.debug(f"Could not read pump corrections from EEPROM, using defaults: {e}")

            flush_p1 = flush_rate * correction_p1
            flush_p2 = flush_rate * correction_p2

            logger.info(
                f"💉 Inject (synced): FLUSH P1={flush_p1:.1f} P2={flush_p2:.1f} µL/min (6s) → target {target_rate:.1f} µL/min "
                f"with {contact_time_s}s valve contact time"
            )

            # Start BOTH pumps at FLUSH rate first (channels 1 and 2) with corrections
            success_p1 = ctrl.pump_start(rate_ul_min=flush_p1, ch=1)
            success_p2 = ctrl.pump_start(rate_ul_min=flush_p2, ch=2)
            success = bool(success_p1 and success_p2)

            if success:
                logger.info(f"✓ Pumps started at FLUSH rate {flush_rate:.1f} µL/min")

                # Update internal state flags - pumps are now running
                self._pump1_running = True
                self._pump2_running = True
                self._synced_pumps_running = True

                # Update status bar immediately to show pumps starting
                self._update_internal_pump_status(f"FLUSH: P1={flush_p1:.0f} P2={flush_p2:.0f} µL/min (6s)", running=True)

                # Update inject button to busy state during injection
                if btn := self._sidebar_widget('internal_pump_inject_30s_btn'):
                    btn.setEnabled(False)
                    btn.setProperty("injection_state", "busy")
                    btn.setText("⏳ Injecting...")
                    btn.setToolTip("⏳ Injection in progress - please wait")
                    btn.style().unpolish(btn)
                    btn.style().polish(btn)

                # Update pump toggle buttons to reflect running state
                if btn := self._sidebar_widget('pump1_toggle_btn'):
                    btn.blockSignals(True)
                    btn.setChecked(True)
                    btn.setText("■ Stop")
                    btn.setEnabled(False)  # Disable during injection
                    btn.style().unpolish(btn)
                    btn.style().polish(btn)
                    btn.blockSignals(False)

                if btn := self._sidebar_widget('pump2_toggle_btn'):
                    btn.blockSignals(True)
                    btn.setChecked(True)
                    btn.setText("■ Stop")
                    btn.setEnabled(False)  # Disable during injection
                    btn.style().unpolish(btn)
                    btn.style().polish(btn)
                    btn.blockSignals(False)

                if btn := self._sidebar_widget('synced_toggle_btn'):
                    btn.blockSignals(True)
                    btn.setChecked(True)
                    btn.setText("■ Stop")
                    btn.setEnabled(False)  # Disable during injection
                    btn.style().unpolish(btn)
                    btn.style().polish(btn)
                    btn.blockSignals(False)

                # Check if valve sync is enabled
                valve_sync_enabled = False
                if btn := self._sidebar_widget('sync_valve_btn'):
                    valve_sync_enabled = btn.isChecked()

                # Determine channel text for status display
                channel_text = "KC1 & KC2" if valve_sync_enabled else "KC1"
                # Remember which valve(s) are open so the countdown text can
                # include the correct channels (matches the status style the
                # user sees in the UI).
                self._injection_channel_text = channel_text

                # Turn on 6-port valve(s) for contact time
                # Use both valves if sync enabled, otherwise just KC1
                try:
                    import time
                    if valve_sync_enabled:
                        # Control both valves simultaneously: state=1 (inject position)
                        valve_success = ctrl.knx_six_both(state=1, timeout_seconds=None)
                        if valve_success:
                            # Record valve open timestamp for delta calculation
                            self._injection_valve_open_time = self.main_window._get_elapsed_time() if hasattr(self.main_window, '_get_elapsed_time') else 0
                            self._injection_start_time = time.time()
                            self._injection_total_time = contact_time_s
                            # Update status to show valve OPEN with channel and countdown
                            self._update_internal_pump_status(f"VALVE OPEN ({channel_text}) - FLUSH - {contact_time_s}.0s", running=True)
                            self._start_injection_countdown()
                            logger.info(f"✓ Both 6-port valves → INJECT - {contact_time_s}s contact time started (t={self._injection_valve_open_time:.2f}s)")
                        else:
                            logger.warning("Failed to activate both 6-port valves")
                            self._update_internal_pump_status(f"Injecting: {flush_rate:.0f} µL/min", running=True)
                    else:
                        # Control KC1 only: state=1 (inject position), channel=1
                        valve_success = ctrl.knx_six(state=1, ch=1, timeout_seconds=None)
                        if valve_success:
                            # Record valve open timestamp for delta calculation
                            self._injection_valve_open_time = self.main_window._get_elapsed_time() if hasattr(self.main_window, '_get_elapsed_time') else 0
                            self._injection_start_time = time.time()
                            self._injection_total_time = contact_time_s
                            # Update status to show valve OPEN with channel and countdown
                            self._update_internal_pump_status(f"VALVE OPEN ({channel_text}) - FLUSH - {contact_time_s}.0s", running=True)
                            self._start_injection_countdown()
                            logger.info(f"✓ KC1 6-port valve → INJECT - {contact_time_s}s contact time started (t={self._injection_valve_open_time:.2f}s)")
                        else:
                            logger.warning("Failed to activate KC1 6-port valve")
                            self._update_internal_pump_status(f"Injecting: {flush_rate:.0f} µL/min", running=True)
                    time.sleep(0.1)  # Brief settle time

                except Exception as e:
                    logger.warning(f"Could not activate 6-port valve: {e}")
                    self._update_internal_pump_status(f"Injecting: {flush_rate:.0f} µL/min", running=True)

                # After 6 seconds, reduce BOTH pumps to target flowrate with corrections
                # This runs REGARDLESS of valve success to ensure pumps don't stay at flush rate
                from PySide6.QtCore import QTimer
                def reduce_to_target_flow():
                    target_p1 = target_rate * correction_p1
                    target_p2 = target_rate * correction_p2
                    success_reduce_p1 = ctrl.pump_start(rate_ul_min=target_p1, ch=1)
                    success_reduce_p2 = ctrl.pump_start(rate_ul_min=target_p2, ch=2)
                    if success_reduce_p1 and success_reduce_p2:
                        logger.info(f"✓ Reduced both pumps to target: P1={target_p1:.1f} P2={target_p2:.1f} µL/min")
                        # Update status to show target flowrate (countdown timer will overwrite with valve info)
                        self._update_internal_pump_status(f"TARGET: P1={target_p1:.0f} P2={target_p2:.0f} µL/min", running=True)
                    else:
                        logger.warning("✗ Failed to reduce both pumps to target flowrate")

                QTimer.singleShot(6000, reduce_to_target_flow)  # Reduce after 6 seconds

                # Schedule valve close after contact time
                # NOTE: Pumps continue running after valve closes - user must stop manually
                from PySide6.QtCore import QTimer
                QTimer.singleShot(contact_time_s * 1000, lambda: self._close_inject_valve())
            else:
                logger.error("✗ Failed to start inject sequence")
        else:
            from affilabs.widgets.message import show_message
            show_message("Internal pumps not available. P4PRO+ V2.3+ required.", "Warning")

    def _close_inject_valve(self):
        """Close 6-port valve after 30-second contact time ends.

        NOTE: Pumps continue running - this only closes the valve.
        User must manually stop pumps using toggle buttons.
        """
        ctrl = self.hardware_mgr._ctrl_raw
        if ctrl and hasattr(ctrl, 'has_internal_pumps') and ctrl.has_internal_pumps():
            # Check if valve sync is enabled
            valve_sync_enabled = False
            if btn := self._sidebar_widget('sync_valve_btn'):
                valve_sync_enabled = btn.isChecked()

            # Turn off 6-port valve(s) (end of 30s contact time)
            try:
                if valve_sync_enabled:
                    # Return both valves to LOAD position (state=0)
                    valve_success = ctrl.knx_six_both(state=0, timeout_seconds=None)
                    if valve_success:
                        # Record valve close timestamp for wash delta calculation
                        self._wash_valve_close_time = self._get_elapsed_time()
                        self._stop_injection_countdown()
                        logger.info(f"✓ Both 6-port valves → LOAD - contact time complete (t={self._wash_valve_close_time:.2f}s, pumps still running)")
                    else:
                        logger.warning("Failed to return both 6-port valves to LOAD")
                else:
                    # Return KC1 to LOAD position (state=0, channel=1)
                    valve_success = ctrl.knx_six(state=0, ch=1, timeout_seconds=None)
                    if valve_success:
                        # Record valve close timestamp for wash delta calculation
                        self._wash_valve_close_time = self._get_elapsed_time()
                        self._stop_injection_countdown()
                        logger.info(f"✓ KC1 6-port valve → LOAD - contact time complete (t={self._wash_valve_close_time:.2f}s, pumps still running)")
                    else:
                        logger.warning("Failed to return KC1 6-port valve to LOAD")
            except Exception as e:
                logger.warning(f"Could not close 6-port valve: {e}")

            # Update status to show pumps are still running but contact time is over
            self._update_internal_pump_status("Pumps running (contact complete)", running=True)

            # Re-enable inject button and restore ready state
            if btn := self._sidebar_widget('internal_pump_inject_30s_btn'):
                btn.setEnabled(True)
                btn.setProperty("injection_state", "ready")
                btn.setText("💉 Inject")
                btn.setToolTip("✅ Ready to inject")
                btn.style().unpolish(btn)
                btn.style().polish(btn)

            # Re-enable pump toggle buttons (pumps still running, user can stop them)
            if btn := self._sidebar_widget('pump1_toggle_btn'):
                btn.setEnabled(True)
            if btn := self._sidebar_widget('pump2_toggle_btn'):
                btn.setEnabled(True)
            if btn := self._sidebar_widget('synced_toggle_btn'):
                btn.setEnabled(True)

            # Sync button states with current running flags
            self._sync_pump_button_states()

    def _start_injection_countdown(self):
        """Start countdown timer for valve injection status."""
        from PySide6.QtCore import QTimer

        logger.info(f"🔄 Starting injection countdown timer (total={getattr(self, '_injection_total_time', 'NOT SET')}s)")

        # Stop any existing timer
        if hasattr(self, '_injection_countdown_timer') and self._injection_countdown_timer:
            logger.debug("Stopping existing countdown timer")
            self._injection_countdown_timer.stop()

        # Create new timer that updates every 100ms. Attach it to the main
        # window (GUI thread) so the timeout signal always fires even if this
        # method is triggered from a worker context.
        parent = getattr(self, 'main_window', None)
        logger.debug(f"Creating QTimer with parent={parent}")
        self._injection_countdown_timer = QTimer(parent)
        self._injection_countdown_timer.timeout.connect(self._update_injection_countdown)
        self._injection_countdown_timer.start(100)  # Update 10 times per second
        logger.info("✓ Countdown timer started (interval=100ms)")

        # Initial status update
        self._update_injection_countdown()

    def _stop_injection_countdown(self):
        """Stop countdown timer and reset valve status."""
        if hasattr(self, '_injection_countdown_timer') and self._injection_countdown_timer:
            self._injection_countdown_timer.stop()
            self._injection_countdown_timer = None

        if hasattr(self, '_injection_start_time'):
            self._injection_start_time = None
        if hasattr(self, '_injection_total_time'):
            self._injection_total_time = 0

        # Reset status to show valve closed
        self._update_internal_pump_status("Valve Closed", running=False)

    def _update_injection_countdown(self):
        """Update status bar and inject button with remaining injection time."""
        import time

        if not hasattr(self, '_injection_start_time') or not self._injection_start_time:
            logger.debug("Countdown update skipped: _injection_start_time not set")
            return
        if not hasattr(self, '_injection_total_time') or self._injection_total_time <= 0:
            logger.debug("Countdown update skipped: _injection_total_time not set")
            return

        elapsed = time.time() - self._injection_start_time
        remaining = max(0, self._injection_total_time - elapsed)

        if remaining <= 0:
            # Timer expired
            logger.debug("Countdown complete - stopping timer")
            if hasattr(self, '_injection_countdown_timer') and self._injection_countdown_timer:
                self._injection_countdown_timer.stop()
            return

        # Determine which valve(s) are open for the status text
        channel_text = getattr(self, '_injection_channel_text', 'KC1')
        # Update status with countdown in the same style as the initial label
        logger.debug(f"Countdown update: {remaining:.1f}s remaining")
        self._update_internal_pump_status(
            f"VALVE OPEN ({channel_text}) - {remaining:.1f}s",
            running=True,
        )

        # Update inject button with countdown
        if btn := self._sidebar_widget('internal_pump_inject_30s_btn'):
            btn.setText(f"⏳ Contact: {remaining:.0f}s")
            btn.setToolTip(f"⏳ Injection in progress - {remaining:.0f}s remaining")

    def _save_pump_corrections(self):
        """Save current pump correction factors to device config and controller EEPROM."""
        try:
            if not hasattr(self, 'hardware_mgr') or not self.hardware_mgr:
                return

            if not hasattr(self.hardware_mgr, 'device_config') or not self.hardware_mgr.device_config:
                return

            device_config = self.hardware_mgr.device_config

            # Get current correction values from spinboxes
            pump1_corr = 1.0
            pump2_corr = 1.0

            if spin := self._sidebar_widget('pump1_correction_spin'):
                pump1_corr = spin.value()
            if spin := self._sidebar_widget('pump2_correction_spin'):
                pump2_corr = spin.value()

            # Get currently saved values
            saved_corrections = device_config.get_pump_corrections()
            saved_pump1 = saved_corrections.get("pump_1", 1.0)
            saved_pump2 = saved_corrections.get("pump_2", 1.0)

            # Only save if values have changed
            if abs(pump1_corr - saved_pump1) > 0.001 or abs(pump2_corr - saved_pump2) > 0.001:
                # Save to device config JSON
                device_config.set_pump_corrections(pump1_corr, pump2_corr)
                device_config.save()
                logger.info(f"💾 Pump corrections saved to device config: Pump 1={pump1_corr:.3f}, Pump 2={pump2_corr:.3f}")

                # Also save to controller EEPROM (if supported by firmware)
                ctrl = self.hardware_mgr._ctrl_raw
                if ctrl and hasattr(ctrl, 'set_pump_corrections'):
                    try:
                        success = ctrl.set_pump_corrections(pump1_corr, pump2_corr)
                        if success:
                            logger.info("✓ Pump corrections written to controller EEPROM")
                        else:
                            logger.warning("⚠ Controller EEPROM write failed (firmware may not support this feature)")
                    except Exception as e:
                        logger.warning(f"Could not write pump corrections to EEPROM: {e}")
        except Exception as e:
            logger.warning(f"Could not save pump corrections: {e}")

    def _update_internal_pump_status(self, text: str, running: bool = False):
        """Update internal pump status display.

        Args:
            text: Status text to display
            running: True if pumps are running (green), False if idle (grey)
        """
        if lbl := self._sidebar_widget('internal_pump_status_label'):
            lbl.setText(text)
        if icon := self._sidebar_widget('internal_pump_status_icon'):
            color = Colors.SUCCESS if running else Colors.SECONDARY_TEXT
            icon.setStyleSheet(
                f"color: {color}; font-size: 14px; background: transparent;"
            )

    def _sync_pump_button_states(self):
        """Sync pump button UI states with tracked running state.

        Called after hardware reconnection or when UI needs to reflect actual pump state.
        """
        # Pump 1 button
        if btn := self._sidebar_widget('pump1_toggle_btn'):
            btn.blockSignals(True)
            btn.setChecked(self._pump1_running)
            btn.setText("■ Stop" if self._pump1_running else "▶ Start")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.blockSignals(False)

        # Pump 2 button
        if btn := self._sidebar_widget('pump2_toggle_btn'):
            btn.blockSignals(True)
            btn.setChecked(self._pump2_running)
            btn.setText("■ Stop" if self._pump2_running else "▶ Start")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.blockSignals(False)

        # Synced pumps button
        if btn := self._sidebar_widget('synced_toggle_btn'):
            btn.blockSignals(True)
            btn.setChecked(self._synced_pumps_running)
            btn.setText("■ Stop" if self._synced_pumps_running else "▶ Start")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.blockSignals(False)

    def _on_synced_flowrate_changed(self):
        """Handle flowrate change in synced controls - update running pumps in real-time.

        Uses 300ms debouncing to prevent rapid command flooding that could
        violate the firmware's 150ms command spacing requirement.
        """
        # Cancel any pending update timer
        if hasattr(self, '_synced_rpm_timer') and self._synced_rpm_timer is not None:
            self._synced_rpm_timer.stop()
            self._synced_rpm_timer = None

        # Schedule update after 300ms of no changes (debouncing)
        from PySide6.QtCore import QTimer
        self._synced_rpm_timer = QTimer()
        self._synced_rpm_timer.setSingleShot(True)
        self._synced_rpm_timer.timeout.connect(self._update_synced_rpm)
        self._synced_rpm_timer.start(300)

    def _update_synced_rpm(self):
        """Actually update synced pump RPM (called after debounce delay)."""
        # Only update if pumps are currently running
        if not (btn := self._sidebar_widget('synced_toggle_btn')):
            return

        is_running = btn.isChecked()
        if not is_running:
            return  # Pump not running, no need to update

        # Get new flowrate value from combo
        if not (combo := self._sidebar_widget('synced_flowrate_combo')):
            return

        flowrate_map = {0: 25, 1: 50, 2: 100, 3: 200, 4: 220}
        idx = combo.currentIndex()
        rpm = flowrate_map.get(idx, 50)
        correction = 1.0  # No correction for synced mode
        rpm_corrected = rpm * correction

        logger.debug(f"[PUMP CMD] Synced Speed Update - Flowrate: {rpm} uL/min, Correction: {correction:.3f}, Sending: {rpm_corrected:.1f} uL/min")

        # Save correction factor to device config if changed
        self._save_pump_corrections()

        # Update running pumps with new RPM
        ctrl = self.hardware_mgr._ctrl_raw
        if not ctrl or not hasattr(ctrl, 'has_internal_pumps') or not ctrl.has_internal_pumps():
            return

        logger.info(f"🔄 Updating synced pump speed: {rpm_corrected:.1f} uL/min")

        # P4PROPLUS allows changing speed while running - just send new start command
        success = ctrl.pump_start(rate_ul_min=rpm_corrected, ch=3)
        if success:
            logger.info(f"✓ Synced pumps speed updated to {rpm_corrected:.1f} uL/min")
            self._update_internal_pump_status(f"Both Pumps: {rpm_corrected:.0f} µL/min", running=True)
        else:
            logger.error("✗ Failed to update synced pump speed")

    def _on_pump1_rpm_changed(self):
        """Handle RPM change for pump 1 - update if currently running.

        Uses 300ms debouncing to prevent rapid command flooding that could
        violate the firmware's 150ms command spacing requirement.
        """
        # Cancel any pending update timer
        if hasattr(self, '_pump1_rpm_timer') and self._pump1_rpm_timer is not None:
            self._pump1_rpm_timer.stop()
            self._pump1_rpm_timer = None

        # Schedule update after 300ms of no changes (debouncing)
        from PySide6.QtCore import QTimer
        self._pump1_rpm_timer = QTimer()
        self._pump1_rpm_timer.setSingleShot(True)
        self._pump1_rpm_timer.timeout.connect(self._update_pump1_rpm)
        self._pump1_rpm_timer.start(300)

    def _update_pump1_rpm(self):
        """Actually update pump 1 RPM (called after debounce delay)."""
        if not (btn := self._sidebar_widget('pump1_toggle_btn')):
            logger.debug("pump1_rpm_changed: toggle_btn not found")
            return

        is_running = btn.isChecked()
        logger.debug(f"pump1_rpm_changed: is_running={is_running}")
        if not is_running:
            return  # Pump not running, no need to update

        if not (spin := self._sidebar_widget('pump1_rpm_spin')):
            logger.debug("pump1_rpm_changed: rpm_spin not found")
            return

        rpm = spin.value()
        correction = getattr(self.main_window.sidebar.pump1_correction_spin, 'value', lambda: 1.0)()
        rpm_corrected = rpm * correction

        logger.debug(f"[PUMP CMD] Pump 1 Speed Update - Spinbox: {rpm} uL/min, Correction: {correction:.3f}, Sending: {rpm_corrected:.1f} uL/min")

        # Save correction factor to device config if changed
        self._save_pump_corrections()

        ctrl = self.hardware_mgr._ctrl_raw
        if not ctrl or not hasattr(ctrl, 'has_internal_pumps') or not ctrl.has_internal_pumps():
            logger.debug("pump1_rpm_changed: no internal pumps available")
            return

        logger.info(f"🔄 Updating pump 1 speed: {rpm_corrected:.1f} uL/min (from spinbox value {rpm})")

        success = ctrl.pump_start(rate_ul_min=rpm_corrected, ch=1)
        if success:
            logger.info(f"✓ Pump 1 speed updated to {rpm_corrected:.1f} uL/min")
            self._update_internal_pump_status(f"Pump 1: {rpm_corrected:.0f} µL/min", running=True)
        else:
            logger.error("✗ Failed to update pump 1 speed")

    def _on_valve_sync_toggled(self, checked: bool):
        """User toggled valve synchronization.

        When enabled, KC1 and KC2 valve switches mirror each other.

        Args:
            checked: True = sync enabled, False = independent control
        """
        mode = "SYNCHRONIZED" if checked else "INDEPENDENT"
        logger.info(f"🔄 Valve control mode → {mode}")

        # If sync is enabled, mirror current KC1 state to KC2
        if checked:
            if (sw1 := self._sidebar_widget('kc1_loop_switch')) and (sw2 := self._sidebar_widget('kc2_loop_switch')):
                kc1_state = sw1.isChecked()
                sw2.setChecked(kc1_state)
                logger.info(f"✓ Synced KC2 loop valve to match KC1 ({kc1_state})")

    def _on_loop_valve_switched(self, channel: int, position: str):
        """User clicked loop valve button - simple ON/OFF control.

        The valve has ONE command: power ON (1) or OFF (0)
        - state=0 (OFF): Load position (de-energized, normal state)
        - state=1 (ON): Sensor position (energized)

        Injection sequence:
        - During filling: Valves in LOAD (state=0) - loop fills from sample
        - During injection: Valves switch to INJECT/Sensor (state=1) - loop content to sensor
        - After contact time: Valves return to LOAD (state=0)

        Args:
            channel: 1 for KC1, 2 for KC2
            position: 'Load' or 'Sensor'
        """
        # Simple: Sensor/INJECT=OPEN(1), Load=CLOSED(0)
        state = 1 if position == 'Sensor' else 0

        ctrl = self.hardware_mgr._ctrl_raw
        if not ctrl:
            logger.warning("Controller not connected")
            return

        ui = self.main_window.sidebar
        sync_enabled = hasattr(ui, 'sync_valve_btn') and ui.sync_valve_btn.isChecked()

        try:
            # Check if sync mode is enabled - use broadcast command for both valves
            if sync_enabled:
                # Use broadcast command v631/v630 to control both valves simultaneously
                success = ctrl.knx_six_both(state)

                if success:
                    # Update both KC1 and KC2 UI buttons
                    ui.kc1_loop_btn_load.blockSignals(True)
                    ui.kc1_loop_btn_sensor.blockSignals(True)
                    ui.kc1_loop_btn_load.setChecked(state == 0)
                    ui.kc1_loop_btn_sensor.setChecked(state == 1)
                    ui.kc1_loop_btn_load.blockSignals(False)
                    ui.kc1_loop_btn_sensor.blockSignals(False)

                    ui.kc2_loop_btn_load.blockSignals(True)
                    ui.kc2_loop_btn_sensor.blockSignals(True)
                    ui.kc2_loop_btn_load.setChecked(state == 0)
                    ui.kc2_loop_btn_sensor.setChecked(state == 1)
                    ui.kc2_loop_btn_load.blockSignals(False)
                    ui.kc2_loop_btn_sensor.blockSignals(False)

                    logger.info(f"✓ BOTH Loop valves (SYNC): {position} (state={state})")
                else:
                    logger.error("BOTH Loop valves command failed (SYNC mode)")
            else:
                # Independent mode - control only the clicked channel
                success = ctrl.knx_six(state, channel)

                if success:
                    # Update only the clicked channel's UI
                    if channel == 1:
                        ui.kc1_loop_btn_load.blockSignals(True)
                        ui.kc1_loop_btn_sensor.blockSignals(True)
                        ui.kc1_loop_btn_load.setChecked(state == 0)
                        ui.kc1_loop_btn_sensor.setChecked(state == 1)
                        ui.kc1_loop_btn_load.blockSignals(False)
                        ui.kc1_loop_btn_sensor.blockSignals(False)
                    else:
                        ui.kc2_loop_btn_load.blockSignals(True)
                        ui.kc2_loop_btn_sensor.blockSignals(True)
                        ui.kc2_loop_btn_load.setChecked(state == 0)
                        ui.kc2_loop_btn_sensor.setChecked(state == 1)
                        ui.kc2_loop_btn_load.blockSignals(False)
                        ui.kc2_loop_btn_sensor.blockSignals(False)

                    logger.info(f"✓ KC{channel} Loop valve: {position} (state={state})")
                else:
                    logger.error(f"KC{channel} Loop valve command failed")
        except Exception as e:
            logger.error(f"Loop valve error: {e}")

    def _on_channel_valve_switched(self, channel: int, selected_channel: str):
        """User clicked channel valve button - simple OPEN/CLOSED control.

        3-way valve states (NO WASTE):
        - state=0 (CLOSED): KC1→A, KC2→C (de-energized)
        - state=1 (OPEN): KC1→B, KC2→D (energized)

        Args:
            channel: 1 for KC1, 2 for KC2
            selected_channel: 'A', 'B', 'C', or 'D'
        """
        # B/D=OPEN(1), A/C=CLOSED(0)
        state = 1 if selected_channel in ['B', 'D'] else 0

        ctrl = self.hardware_mgr._ctrl_raw
        if not ctrl:
            logger.warning("Controller not connected")
            return

        ui = self.main_window.sidebar
        sync_enabled = hasattr(ui, 'sync_valve_btn') and ui.sync_valve_btn.isChecked()

        try:
            # Check if sync mode is enabled - use broadcast command for both valves
            if sync_enabled:
                # Use broadcast command v3B1/v3B0 to control both valves simultaneously
                success = ctrl.knx_three_both(state)

                if success:
                    # Update both KC1 and KC2 UI buttons
                    # state=0: A/C active, state=1: B/D active
                    ui.kc1_channel_btn_a.blockSignals(True)
                    ui.kc1_channel_btn_b.blockSignals(True)
                    ui.kc1_channel_btn_a.setChecked(state == 0)
                    ui.kc1_channel_btn_b.setChecked(state == 1)
                    ui.kc1_channel_btn_a.blockSignals(False)
                    ui.kc1_channel_btn_b.blockSignals(False)

                    ui.kc2_channel_btn_c.blockSignals(True)
                    ui.kc2_channel_btn_d.blockSignals(True)
                    ui.kc2_channel_btn_c.setChecked(state == 0)
                    ui.kc2_channel_btn_d.setChecked(state == 1)
                    ui.kc2_channel_btn_c.blockSignals(False)
                    ui.kc2_channel_btn_d.blockSignals(False)

                    logger.info(f"✓ BOTH Channel valves (SYNC): {selected_channel} (state={state})")
                else:
                    logger.error("BOTH Channel valves command failed (SYNC mode)")
            else:
                # Independent mode - control only the clicked channel
                success = ctrl.knx_three(state, channel)

                if success:
                    # Update only the clicked channel's UI
                    # state=0: A/C active, state=1: B/D active
                    if channel == 1:
                        ui.kc1_channel_btn_a.blockSignals(True)
                        ui.kc1_channel_btn_b.blockSignals(True)
                        ui.kc1_channel_btn_a.setChecked(state == 0)
                        ui.kc1_channel_btn_b.setChecked(state == 1)
                        ui.kc1_channel_btn_a.blockSignals(False)
                        ui.kc1_channel_btn_b.blockSignals(False)
                    else:
                        ui.kc2_channel_btn_c.blockSignals(True)
                        ui.kc2_channel_btn_d.blockSignals(True)
                        ui.kc2_channel_btn_c.setChecked(state == 0)
                        ui.kc2_channel_btn_d.setChecked(state == 1)
                        ui.kc2_channel_btn_c.blockSignals(False)
                        ui.kc2_channel_btn_d.blockSignals(False)

                    logger.info(f"✓ KC{channel} Channel valve: {selected_channel} (state={state})")
                else:
                    logger.error(f"KC{channel} Channel valve command failed")
        except Exception as e:
            logger.error(f"KC{channel} Channel valve error: {e}")
            show_message(f"Failed to switch valve: {e}", "Error")

    # === INTERNAL PUMP HANDLERS (RPi Peristaltic Pumps - Separate from AffiPump) ===

    def _on_internal_pump_sync_toggled(self, checked: bool):
        """User toggled internal pump synchronization.

        When enabled, both KC1 and KC2 pumps run together at same flow rate.

        Args:
            checked: True = sync enabled (both pumps), False = single channel control
        """
        mode = "SYNCHRONIZED (Both KC1 & KC2)" if checked else "INDEPENDENT (Single Channel)"
        logger.info(f"🔄 Internal pump mode → {mode}")

        # Apply current flow rate to both pumps if sync enabled
        if checked:
            if combo := self._sidebar_widget('internal_pump_flowrate_combo'):
                flowrate_text = combo.currentText()
                logger.info(f"✓ Sync enabled - applying flow rate '{flowrate_text}' to both pumps")
                # Trigger flow rate change which will handle synced operation
                self._on_internal_pump_flowrate_changed(flowrate_text)

    def _calculate_and_display_flag_deltas(self):
        """Calculate pump calibration metrics from flagged segments.

        Two objectives for pump calibration:
        1. TRAVEL TIME MATCHING: Injection arrival time from valve open should match between channels
           - Solution: Add pump start delay to slower channel
        2. CONTACT TIME MATCHING: Time from injection→wash should match between channels
           - Solution: Adjust RPM correction factor

        Shows in status bar:
        - Travel times (valve open → injection flag)
        - Contact times (injection flag → wash flag)
        - Suggested corrections (delay and RPM factor)
        """
        if not hasattr(self, '_flag_markers') or not self._flag_markers:
            return

        # Group flags by type and channel
        injection_flags = {f['channel']: f for f in self._flag_markers if f['type'] == 'injection'}
        wash_flags = {f['channel']: f for f in self._flag_markers if f['type'] == 'wash'}

        delta_messages = []
        travel_times = {}
        contact_times = {}

        # Calculate travel times (valve open → injection arrival)
        if injection_flags and hasattr(self, '_injection_valve_open_time'):
            valve_open_time = self._injection_valve_open_time
            for ch, flag in injection_flags.items():
                travel_time = flag['time'] - valve_open_time
                travel_times[ch] = travel_time
                delta_messages.append(f"💉 Ch{ch.upper()} Travel: {travel_time:.2f}s")

        # Calculate contact times (injection → wash)
        for ch in injection_flags:
            if ch in wash_flags:
                contact_time = wash_flags[ch]['time'] - injection_flags[ch]['time']
                contact_times[ch] = contact_time
                delta_messages.append(f"⏱ Ch{ch.upper()} Contact: {contact_time:.2f}s")

        # === OBJECTIVE 1: TRAVEL TIME MATCHING ===
        if len(travel_times) >= 2:
            channels = sorted(travel_times.keys())
            ch1, ch2 = channels[0], channels[1]
            t1, t2 = travel_times[ch1], travel_times[ch2]
            travel_delta = abs(t2 - t1)

            # Determine which pump needs delay
            if t1 < t2:
                # Ch1 is faster, delay ch1 pump start
                slower_ch = ch2
                delay_needed = travel_delta
                delta_messages.append(f"🔧 Delay Ch{ch1.upper()} pump: +{delay_needed:.2f}s")
            elif t2 < t1:
                # Ch2 is faster, delay ch2 pump start
                slower_ch = ch1
                delay_needed = travel_delta
                delta_messages.append(f"🔧 Delay Ch{ch2.upper()} pump: +{delay_needed:.2f}s")
            else:
                delta_messages.append("✓ Travel times matched!")

        # === OBJECTIVE 2: CONTACT TIME MATCHING (RPM Correction) ===
        if len(contact_times) >= 2:
            channels = sorted(contact_times.keys())
            ch1, ch2 = channels[0], channels[1]
            ct1, ct2 = contact_times[ch1], contact_times[ch2]

            # Use the faster contact time as target (means higher flow rate)
            target_contact = min(ct1, ct2)

            # Calculate RPM correction factors needed
            if ct1 > target_contact:
                # Ch1 is slower, needs higher RPM
                correction_factor = ct1 / target_contact
                delta_messages.append(f"⚙️ Ch{ch1.upper()} RPM correction: ×{correction_factor:.3f}")
            if ct2 > target_contact:
                # Ch2 is slower, needs higher RPM
                correction_factor = ct2 / target_contact
                delta_messages.append(f"⚙️ Ch{ch2.upper()} RPM correction: ×{correction_factor:.3f}")

            contact_delta = abs(ct2 - ct1)
            if contact_delta < 0.5:
                delta_messages.append("✓ Contact times matched!")

        # Display in status bar
        if delta_messages:
            status_text = " | ".join(delta_messages)
            self.main_window.statusBar().showMessage(status_text, 20000)  # Show for 20 seconds
            logger.info(f"📊 Pump Calibration Analysis: {status_text}")

    def _on_internal_pump_flowrate_changed(self, flowrate_text: str):
        """User changed internal pump flow rate.

        Args:
            flowrate_text: Selected flow rate ('50', '100', '200', or 'Flush')
        """
        ctrl = self.hardware_mgr.controller
        if not ctrl:
            return

        # Parse flow rate
        if flowrate_text == "Flush":
            rate = 500  # Flush rate
        else:
            try:
                rate = int(flowrate_text)
            except ValueError:
                logger.warning(f"Invalid flow rate: {flowrate_text}")
                return

        # Get selected channel (1 or 2) or both if sync is on
        sync_enabled = False
        if btn := self._sidebar_widget('internal_pump_sync_btn'):
            sync_enabled = btn.isChecked()

        if sync_enabled:
            # Control both channels together
            logger.info(f"🔄 Internal pumps (both KC1 & KC2) → {rate} µL/min (synced)")
            try:
                ctrl.knx_start(rate, 1)  # KC1
                ctrl.knx_start(rate, 2)  # KC2
                logger.info(f"✓ Both internal pumps started at {rate} µL/min")
            except Exception as e:
                logger.error(f"Failed to start synced pumps: {e}")
                from affilabs.widgets.message import show_message
                show_message(f"Failed to start pumps: {e}", "Error")
        else:
            # Control only selected channel
            channel = 1
            if btn := self._sidebar_widget('internal_pump_channel_btn_2'):
                if btn.isChecked():
                    channel = 2

            logger.info(f"🔄 Internal pump KC{channel} → {rate} µL/min")
            try:
                ctrl.knx_start(rate, channel)
                logger.info(f"✓ Internal pump KC{channel} started at {rate} µL/min")
            except Exception as e:
                logger.error(f"Failed to start pump KC{channel}: {e}")
                from affilabs.widgets.message import show_message
                show_message(f"Failed to start pump: {e}", "Error")

    def _cleanup_resources(self, emergency: bool = False):
        """Consolidated cleanup logic for all shutdown paths."""
        from affilabs.utils.resource_helpers import ResourceHelpers

        # Turn off all LEDs gracefully
        try:
            if hasattr(self, 'hardware_mgr') and self.hardware_mgr:
                ctrl = getattr(self.hardware_mgr, 'ctrl', None)
                if ctrl and hasattr(ctrl, 'turn_off_channels'):
                    logger.info("💡 Turning off all LEDs gracefully...")
                    ctrl.turn_off_channels()
                    logger.info("✓ All LEDs turned off")
        except Exception as e:
            logger.debug(f"Could not turn off LEDs during cleanup: {e}")

        # Power off all valves gracefully (CRITICAL SAFETY)
        try:
            if hasattr(self, 'hardware_mgr') and self.hardware_mgr:
                ctrl = getattr(self.hardware_mgr, '_ctrl_raw', None)
                if ctrl and hasattr(ctrl, 'stop_kinetic'):
                    logger.info("🔌 Powering off all valves gracefully...")
                    ctrl.stop_kinetic()  # Turns off 3-way and 6-port valves
                    logger.info("✓ All valves powered off")
        except Exception as e:
            logger.debug(f"Could not power off valves during cleanup: {e}")

        # Gracefully stop internal pumps if running
        try:
            if hasattr(self, 'hardware_mgr') and self.hardware_mgr:
                ctrl = getattr(self.hardware_mgr, '_ctrl_raw', None)
                if ctrl and hasattr(ctrl, 'has_internal_pumps') and ctrl.has_internal_pumps():
                    logger.info("⏹️ Stopping internal pumps gracefully...")
                    ctrl.pump_stop(ch=3)  # Stop all pumps (channel 3 = both)
                    logger.info("✓ Internal pumps stopped")
        except Exception as e:
            logger.debug(f"Could not stop internal pumps during cleanup: {e}")

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
        """Grid checkbox toggled - applies to Active Cycle graph only."""
        from affilabs.plot_helpers import GRID_ALPHA
        logger.info(f"Grid toggled: {checked} (Active Cycle graph)")
        # Only apply to Active Cycle graph (bottom graph), not timeline
        try:
            self.main_window.cycle_of_interest_graph.showGrid(x=checked, y=checked, alpha=GRID_ALPHA)
            logger.info(f"✓ Grid {'shown' if checked else 'hidden'} on Active Cycle graph")
        except Exception as e:
            logger.error(f"Failed to toggle grid: {e}")
            import traceback
            traceback.print_exc()

    def _on_autoscale_toggled(self, checked: bool):
        """Autoscale checkbox toggled."""
        if checked:
            logger.info(f"Autoscale enabled for {self._selected_axis.upper()}-axis")
            # Enable autoscale for selected axis
            if self._selected_axis == "x":
                self.main_window.cycle_of_interest_graph.enableAutoRange(axis="x")
            else:
                self.main_window.cycle_of_interest_graph.enableAutoRange(axis="y")
        else:
            logger.info(f"Manual scale enabled for {self._selected_axis.upper()}-axis")
            # Disable autoscale for selected axis
            if self._selected_axis == "x":
                self.main_window.cycle_of_interest_graph.disableAutoRange(axis="x")
            else:
                self.main_window.cycle_of_interest_graph.disableAutoRange(axis="y")
            # Apply current manual range values if any
            self._on_manual_range_changed()

    def _on_manual_range_changed(self):
        """Manual range input values changed."""
        # Check if controls exist (may be hidden)
        if not hasattr(self.main_window, 'autoscale_check'):
            return

        # Only apply if autoscale is disabled (manual mode)
        if self.main_window.autoscale_check.isChecked():
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
        # Check if controls exist (may be hidden)
        if not hasattr(self.main_window, 'x_axis_btn'):
            return

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
        if self.main_window.autoscale_check.isChecked():
            self._on_autoscale_toggled(True)
        else:
            self._on_manual_range_changed()

    def _on_channel_filter_changed(self, channel: str):
        """Channel combo selection changed - filter which channels are displayed."""
        logger.info(f"Channel filter changed to: {channel}")

        # Show/hide channels on cycle of interest graph
        graph = self.main_window.cycle_of_interest_graph
        if not hasattr(graph, 'curves') or not graph.curves:
            return

        channel_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}

        if channel == "All":
            # Show all channels
            for curve in graph.curves:
                curve.setVisible(True)
            logger.info("All channels visible")
        else:
            # Hide all except selected channel
            selected_idx = channel_map.get(channel)
            for idx, curve in enumerate(graph.curves):
                curve.setVisible(idx == selected_idx)
            logger.info(f"Only Channel {channel} visible")

    def _on_marker_style_changed(self, marker: str):
        """Marker combo selection changed - update data point symbols."""
        logger.info(f"Marker style changed to: {marker}")

        # Map marker name to pyqtgraph symbol
        marker_map = {
            'Circle': 'o',
            'Triangle': 't',
            'Square': 's',
            'Star': 'star'
        }
        symbol = marker_map.get(marker, 'o')

        # Update all curve symbols on cycle of interest graph
        graph = self.main_window.cycle_of_interest_graph
        if hasattr(graph, 'curves') and graph.curves:
            import pyqtgraph as pg
            for curve in graph.curves:
                # Get current pen style and update symbol
                current_pen = curve.opts.get('pen')
                current_brush = curve.opts.get('symbolBrush')
                curve.setSymbol(symbol)
                curve.setSymbolSize(6)
                if current_brush:
                    curve.setSymbolBrush(current_brush)
                curve.setSymbolPen(pg.mkPen('w', width=1))  # White outline
            logger.info(f"Updated markers to {marker} ({symbol})")

    def _on_filter_toggled(self, checked: bool):
        """Data filtering checkbox toggled."""
        pass  # graph_events removed

    def _on_filter_strength_changed(self, value: int):
        """Filter strength slider changed."""
        self.ui_control_events.on_filter_strength_changed(value)

    def on_settings_changed(self):
        """Called when Advanced Settings are applied - update UI to reflect new settings.

        This method is called by AdvancedSettingsDialog.accept() after settings are saved.
        It updates the Active Cycle graph Y-axis label to reflect the current unit (RU/nm).
        """
        try:
            import settings

            # Update Active Cycle graph Y-axis label to match new unit
            if hasattr(self, 'main_window') and hasattr(self.main_window, 'cycle_of_interest_graph'):
                graph = self.main_window.cycle_of_interest_graph
                if hasattr(graph, 'reset_segment_graph'):
                    unit = getattr(settings, 'DEFAULT_UNIT', 'RU')
                    graph.reset_segment_graph(unit)
                    logger.info(f"✓ Updated Active Cycle Y-axis label to: Δ SPR ({unit})")

            # Update unit display labels in the UI if available
            if hasattr(self, 'main_window') and hasattr(self.main_window, 'ui'):
                ui = self.main_window.ui
                unit = getattr(settings, 'DEFAULT_UNIT', 'RU')
                # Update unit labels for shift display (Processing tab)
                from settings import CH_LIST
                for ch in CH_LIST:
                    unit_label = getattr(ui, f"unit_{ch}", None)
                    if unit_label:
                        unit_label.setText(unit)
                logger.info(f"✓ Updated unit labels to: {unit}")

        except Exception as e:
            logger.error(f"Error in on_settings_changed: {e}")
            import traceback
            traceback.print_exc()

    def _init_kalman_filters(self):
        """Initialize Kalman filter instances for each channel."""

        # Path already added at module initialization - no need to re-add
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

        Double-Click: Select nearest channel (highlights curve)
        Ctrl+Click: Show flag type menu to add marker
        Right-Click: Remove flag marker near cursor
        """
        from PySide6.QtCore import Qt

        # Get click position in scene coordinates
        pos = event.scenePos()

        # Map scene position to data coordinates
        view_box = self.main_window.cycle_of_interest_graph.plotItem.vb
        mouse_point = view_box.mapSceneToView(pos)
        time_clicked = mouse_point.x()
        spr_clicked = mouse_point.y()

        # Check if double-click (select nearest channel)
        if event.double():
            logger.debug(f"Double-click detected at t={time_clicked:.2f}, SPR={spr_clicked:.2f}")
            nearest_channel = self._find_nearest_channel_at_click(time_clicked, spr_clicked)
            if nearest_channel:
                self._select_flag_channel_visual(nearest_channel)
                logger.info(f"Selected Channel {nearest_channel.upper()} for flag placement (double-click)")
            else:
                logger.warning("Double-click: No channel found near click position")
            return

        # Check if Ctrl key is pressed (add flag)
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Check if it's Ctrl+Right-click (remove flag)
            if event.button() == Qt.MouseButton.RightButton:
                self.flag_mgr.remove_flag_near_click(time_clicked, spr_clicked)
                # Accept event to prevent default PyQtGraph context menu from appearing
                event.accept()
                return

            # Ctrl+Left-click (add flag)
            # Use the selected flag channel instead of auto-detecting
            # Default to 'a' if not yet initialized (defensive)
            selected_channel = getattr(self, '_selected_flag_channel', 'a')

            # CRITICAL: Get DISPLAY data (time rebased to 0, skipping first point)
            # The cycle_of_interest_graph shows rebased time: cycle_time[1:] - cycle_time[1]
            # So we need to work with the displayed/rebased data to match what's shown
            cycle_time_raw = self.buffer_mgr.cycle_data[selected_channel].time
            cycle_spr_raw = self.buffer_mgr.cycle_data[selected_channel].spr

            if len(cycle_time_raw) < 2 or len(cycle_spr_raw) < 2:
                logger.warning(f"Not enough data for Channel {selected_channel.upper()} (need at least 2 points)")
                return

            # Match ui_update_helpers.py logic: skip first point and rebase
            first_time = cycle_time_raw[1]
            cycle_time_display = cycle_time_raw[1:] - first_time  # Rebased to 0
            cycle_spr_display = cycle_spr_raw[1:]

            # Find NEAREST DATA POINT in DISPLAY coordinates
            time_idx = np.argmin(np.abs(cycle_time_display - time_clicked))
            time_at_point = cycle_time_display[time_idx]  # Display time (rebased)
            spr_at_time = cycle_spr_display[time_idx]

            # Show flag type selection menu (use display time for alignment)
            self.flag_mgr.show_flag_type_menu(event, selected_channel, time_at_point, spr_at_time)

            # Accept event to prevent default PyQtGraph context menu from appearing
            event.accept()

        # Check if right-click WITHOUT Ctrl (just ignore, let default menu show)
        elif event.button() == Qt.MouseButton.RightButton:
            # Don't handle plain right-click here to allow PyQtGraph default menu
            pass

        # Check if left-click near a flag (select for keyboard movement)
        elif event.button() == Qt.MouseButton.LeftButton:
            self.flag_mgr.try_select_flag_for_movement(time_clicked, spr_clicked)

    def _show_flag_type_menu(self, event, channel: str, time_val: float, spr_val: float):
        """Show dropdown menu to select flag type.

        Args:
            event: Mouse event
            channel: Channel identifier
            time_val: Time position for flag
            spr_val: SPR value at flag position
        """
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction, QCursor

        menu = QMenu()

        # Create flag type actions
        injection_action = QAction("▲ Injection", menu)
        injection_action.triggered.connect(
            lambda: self._add_flag_marker(channel, time_val, spr_val, 'injection')
        )

        wash_action = QAction("■ Wash", menu)
        wash_action.triggered.connect(
            lambda: self._add_flag_marker(channel, time_val, spr_val, 'wash')
        )

        spike_action = QAction("★ Spike", menu)
        spike_action.triggered.connect(
            lambda: self._add_flag_marker(channel, time_val, spr_val, 'spike')
        )

        menu.addAction(injection_action)
        menu.addAction(wash_action)
        menu.addAction(spike_action)

        # Show menu at cursor position
        menu.exec(QCursor.pos())

    def _find_nearest_channel_at_click(self, time_clicked: float, spr_clicked: float) -> str | None:
        """Find which channel curve is closest to the click position.

        CRITICAL: Works with DISPLAY coordinates (time rebased to 0, first point skipped)
        to match what's actually shown on the cycle_of_interest_graph.

        Uses normalized distance calculation to handle different time/SPR scales.
        Has a tolerance threshold - won't select if click is too far from any curve.

        Args:
            time_clicked: Time coordinate of click (in display/rebased time)
            spr_clicked: SPR coordinate of click

        Returns:
            Channel identifier ('a', 'b', 'c', 'd') or None if no data or too far
        """
        min_distance = float('inf')
        nearest_channel = None

        # Get current view ranges for normalization
        try:
            view_box = self.main_window.cycle_of_interest_graph.plotItem.vb
            view_ranges = view_box.viewRange()
            time_range = view_ranges[0][1] - view_ranges[0][0]  # x-axis range
            spr_range = view_ranges[1][1] - view_ranges[1][0]   # y-axis range

            # Avoid division by zero
            if time_range <= 0:
                time_range = 1.0
            if spr_range <= 0:
                spr_range = 1.0
        except:
            # Fallback to default normalization
            time_range = 100.0
            spr_range = 100.0

        # Check all 4 channels
        for ch in ['a', 'b', 'c', 'd']:
            # Get RAW cycle data
            cycle_time_raw = self.buffer_mgr.cycle_data[ch].time
            cycle_spr_raw = self.buffer_mgr.cycle_data[ch].spr

            if len(cycle_time_raw) < 2 or len(cycle_spr_raw) < 2:
                logger.debug(f"Channel {ch.upper()}: Insufficient data (need at least 2 points)")
                continue

            # Match ui_update_helpers.py: skip first point and rebase to 0
            first_time = cycle_time_raw[1]
            cycle_time_display = cycle_time_raw[1:] - first_time
            cycle_spr_display = cycle_spr_raw[1:]

            # Find the data point closest to clicked time IN DISPLAY COORDINATES
            time_idx = np.argmin(np.abs(cycle_time_display - time_clicked))

            if time_idx < len(cycle_spr_display):
                # Calculate NORMALIZED distance from click to this channel's curve
                spr_at_time = cycle_spr_display[time_idx]

                # Normalize by view range to make distance scale-independent
                time_diff_normalized = 0.0  # Already at exact time point
                spr_diff_normalized = abs(spr_at_time - spr_clicked) / spr_range

                # Euclidean distance in normalized space
                distance = np.sqrt(time_diff_normalized**2 + spr_diff_normalized**2)

                logger.debug(f"Channel {ch.upper()}: SPR at t={time_clicked:.2f} is {spr_at_time:.2f}, normalized distance={distance:.4f}")

                if distance < min_distance:
                    min_distance = distance
                    nearest_channel = ch

        # Only return channel if it's reasonably close (within 15% of view range)
        # This prevents selecting curves that are very far from the click
        TOLERANCE = 0.15  # 15% of vertical view range

        if nearest_channel and min_distance < TOLERANCE:
            logger.debug(f"✓ Nearest channel: {nearest_channel.upper()} (normalized distance={min_distance:.4f})")
            return nearest_channel
        else:
            if nearest_channel:
                logger.debug(f"✗ Click too far from curves (distance={min_distance:.4f} > tolerance={TOLERANCE})")
            else:
                logger.debug("✗ No nearest channel found (all channels have insufficient data)")
            return None

    def _select_flag_channel_visual(self, channel: str):
        """Select a channel for flagging and update visual highlighting.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
        """
        # Store the selected channel
        self._selected_flag_channel = channel

        # Update visual highlighting through UI
        self.main_window._on_flag_channel_selected(channel)

    def _add_flag_marker(self, channel: str, time_val: float, spr_val: float, flag_type: str):
        """Add a visual flag marker to the cycle graph.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            time_val: Time position for flag
            spr_val: SPR value at flag position
            flag_type: Type of flag ('injection', 'wash', 'spike')
        """
        import pyqtgraph as pg

        # Initialize flag storage if needed
        if not hasattr(self, '_flag_markers'):
            self._flag_markers = []

        # Injection alignment (Phase 2)
        if not hasattr(self, '_injection_reference_time'):
            self._injection_reference_time = None
            self._injection_reference_channel = None
            self._injection_alignment_line = None
            self._injection_snap_tolerance = 10.0  # Seconds

        # Define flag appearance based on type (Phase 2)
        flag_styles = {
            'injection': {'symbol': 't', 'size': 15, 'color': (255, 50, 50, 230)},    # Red triangle
            'wash': {'symbol': 's', 'size': 18, 'color': (50, 150, 255, 255)},        # Blue square - larger, fully opaque
            'spike': {'symbol': 'star', 'size': 24, 'color': (255, 200, 0, 255)}      # Yellow star - larger, fully opaque
        }

        style = flag_styles.get(flag_type, flag_styles['injection'])

        # INJECTION ALIGNMENT LOGIC (Phase 2)
        if flag_type == 'injection':
            if self._injection_reference_time is None:
                # First injection - set as reference
                self._injection_reference_time = time_val
                self._injection_reference_channel = channel
                self._create_injection_alignment_line(time_val)
                logger.info(f"✓ Injection reference set at t={time_val:.2f}s (Channel {channel.upper()})")
            else:
                # Subsequent injection - ALWAYS align channel data to reference
                time_diff = time_val - self._injection_reference_time

                # Shift this channel's data to align with reference
                shift_amount = -time_diff  # Negative because we shift left to align
                self._channel_time_shifts[channel] = shift_amount

                logger.info(f"→ Aligning Channel {channel.upper()}: shifting {shift_amount:+.2f}s to match reference (diff was {time_diff:.2f}s)")

                # Export time shift to recording metadata
                if self.recording_mgr.is_recording:
                    self.recording_mgr.update_metadata(f'channel_{channel}_time_shift', shift_amount)

                # Trigger graph update to show shifted data
                self._update_cycle_of_interest_graph()

                # Snap flag marker to reference position
                time_val = self._injection_reference_time

        # Create flag marker with type-specific appearance
        marker = pg.ScatterPlotItem(
            [time_val],
            [spr_val],
            symbol=style['symbol'],
            size=style['size'],
            brush=pg.mkBrush(*style['color']),
            pen=pg.mkPen('w', width=2)  # White border
        )

        # Add marker to graph
        self.main_window.cycle_of_interest_graph.addItem(marker)

        # Store marker reference
        self._flag_markers.append({
            'channel': channel,
            'time': time_val,
            'spr': spr_val,
            'marker': marker,
            'type': flag_type
        })

        # Export flag to recording manager
        if self.recording_mgr.is_recording:
            flag_export_data = {
                'type': flag_type,
                'channel': channel,
                'time': time_val,
                'spr': spr_val,
                'timestamp': time.time(),
            }
            self.recording_mgr.add_flag(flag_export_data)

        logger.info(f"🚩 {flag_type.capitalize()} flag added: Channel {channel.upper()} at t={time_val:.2f}s")

        # Calculate and display time deltas between flagged segments
        self._calculate_and_display_flag_deltas()

    def _create_injection_alignment_line(self, time_val: float):
        """Create vertical line at injection reference time for alignment."""
        import pyqtgraph as pg
        from PySide6.QtCore import Qt

        # Create vertical line spanning the graph
        self._injection_alignment_line = pg.InfiniteLine(
            pos=time_val,
            angle=90,  # Vertical
            pen=pg.mkPen(color=(255, 50, 50, 100), width=2, style=Qt.PenStyle.DashLine),
            movable=False,
            label='Injection Reference'
        )
        self.main_window.cycle_of_interest_graph.addItem(self._injection_alignment_line)

    def _remove_flag_near_click(self, time_clicked: float, spr_clicked: float, tolerance: float = 2.0):
        """Remove flag marker near the click position using 2D distance.

        Args:
            time_clicked: Time coordinate of click
            spr_clicked: SPR coordinate of click
            tolerance: Not used (kept for compatibility)
        """
        if not hasattr(self, '_flag_markers') or not self._flag_markers:
            return

        # Find flag closest to click position using 2D distance
        min_distance = float('inf')
        closest_flag_idx = None

        # Get view range for normalization
        view_range = self.main_window.cycle_of_interest_graph.viewRange()
        time_range = view_range[0][1] - view_range[0][0]
        spr_range = view_range[1][1] - view_range[1][0]

        for idx, flag in enumerate(self._flag_markers):
            # Calculate normalized 2D distance
            time_dist = abs(flag['time'] - time_clicked) / time_range
            spr_dist = abs(flag['spr'] - spr_clicked) / spr_range
            distance = np.sqrt(time_dist**2 + spr_dist**2)

            if distance < min_distance:
                min_distance = distance
                closest_flag_idx = idx

        # Remove the closest flag if within tolerance (2% of screen diagonal)
        if closest_flag_idx is not None and min_distance < 0.02:
            flag = self._flag_markers[closest_flag_idx]

            # Remove from graph - clear the marker data first to ensure complete cleanup
            try:
                flag['marker'].clear()  # Clear any internal data/points
            except Exception:
                pass

            self.main_window.cycle_of_interest_graph.removeItem(flag['marker'])

            # Remove from storage
            self._flag_markers.pop(closest_flag_idx)

            # If we removed an injection flag, check if we need to clear alignment
            if flag['type'] == 'injection':
                # Count remaining injection flags
                remaining_injections = [f for f in self._flag_markers if f['type'] == 'injection']
                if len(remaining_injections) == 0:
                    # No more injections - clear alignment line and time shifts
                    if self._injection_alignment_line is not None:
                        self.main_window.cycle_of_interest_graph.removeItem(self._injection_alignment_line)
                        self._injection_alignment_line = None
                    self._injection_reference_time = None
                    self._injection_reference_channel = None

                    # CRITICAL: Reset all channel time shifts
                    self._channel_time_shifts = {'a': 0.0, 'b': 0.0, 'c': 0.0, 'd': 0.0}

                    # Refresh graph to show unshifted data
                    self._update_cycle_of_interest_graph()

                    logger.info("✓ Injection alignment and time shifts cleared")

            logger.info(f"🚩 {flag['type'].capitalize()} flag removed: Channel {flag['channel'].upper()} at t={flag['time']:.2f}s")

            # Recalculate and display time deltas with remaining flags
            self._calculate_and_display_flag_deltas()

    def _try_select_flag_for_movement(self, time_clicked: float, spr_clicked: float):
        """Check if click is near a flag and select it for keyboard movement."""
        if not hasattr(self, '_flag_markers') or not self._flag_markers:
            return

        # Find flag closest to click
        min_distance = float('inf')
        closest_flag_idx = None

        # Get view range for normalization
        view_range = self.main_window.cycle_of_interest_graph.viewRange()
        time_range = view_range[0][1] - view_range[0][0]
        spr_range = view_range[1][1] - view_range[1][0]

        for idx, flag in enumerate(self._flag_markers):
            # Calculate normalized 2D distance
            time_dist = abs(flag['time'] - time_clicked) / time_range
            spr_dist = abs(flag['spr'] - spr_clicked) / spr_range
            distance = np.sqrt(time_dist**2 + spr_dist**2)

            if distance < min_distance:
                min_distance = distance
                closest_flag_idx = idx

        # Select flag if within tolerance (3% of screen diagonal)
        if closest_flag_idx is not None and min_distance < 0.03:
            self._selected_flag_idx = closest_flag_idx
            flag = self._flag_markers[closest_flag_idx]

            # Visual feedback: highlight selected flag
            self._highlight_selected_flag(closest_flag_idx)

            logger.info(f"🎯 Selected {flag['type']} flag at t={flag['time']:.2f}s (use arrow keys ← → to move, ESC to deselect)")

    def _highlight_selected_flag(self, flag_idx: int):
        """Highlight the selected flag with a yellow ring."""
        # Remove previous highlight if any
        if self._flag_highlight_ring is not None:
            self.main_window.cycle_of_interest_graph.removeItem(self._flag_highlight_ring)

        import pyqtgraph as pg

        flag = self._flag_markers[flag_idx]

        # Create a ring around the selected flag
        self._flag_highlight_ring = pg.ScatterPlotItem(
            [flag['time']],
            [flag['spr']],
            symbol='o',
            size=25,
            pen=pg.mkPen('y', width=3),  # Yellow ring
            brush=None
        )
        self.main_window.cycle_of_interest_graph.addItem(self._flag_highlight_ring)

    def _setup_keyboard_event_filter(self):
        """Install event filter on main window to capture keyboard events for flag movement."""
        from PySide6.QtCore import QObject, QEvent, Qt

        class KeyboardEventFilter(QObject):
            def __init__(self, app_instance):
                super().__init__()
                self.app = app_instance

            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.KeyPress:
                    # Check if a flag is selected
                    if hasattr(self.app, '_selected_flag_idx') and self.app._selected_flag_idx is not None:
                        key = event.key()

                        # Arrow keys move flag
                        if key == Qt.Key.Key_Left:
                            self.app._move_selected_flag(-1)  # Move left by 1 data point
                            return True
                        elif key == Qt.Key.Key_Right:
                            self.app._move_selected_flag(1)  # Move right by 1 data point
                            return True
                        elif key == Qt.Key.Key_Escape:
                            self.app._deselect_flag()  # Deselect flag
                            return True

                return super().eventFilter(obj, event)

        self._keyboard_filter = KeyboardEventFilter(self)
        self.main_window.installEventFilter(self._keyboard_filter)
        logger.debug("✓ Keyboard event filter installed for flag movement")

    def _move_selected_flag(self, direction: int):
        """Move the selected flag left (-1) or right (+1) by one data point.

        Args:
            direction: -1 for left, +1 for right
        """
        if self._selected_flag_idx is None or self._selected_flag_idx >= len(self._flag_markers):
            return

        flag = self._flag_markers[self._selected_flag_idx]
        channel = flag['channel']

        # Get DISPLAY data (rebased time)
        cycle_time_raw = self.buffer_mgr.cycle_data[channel].time
        cycle_spr_raw = self.buffer_mgr.cycle_data[channel].spr

        if len(cycle_time_raw) < 2:
            return

        # Match display logic: skip first point and rebase
        first_time = cycle_time_raw[1]
        cycle_time_display = cycle_time_raw[1:] - first_time
        cycle_spr_display = cycle_spr_raw[1:]

        # Find current flag position in data array
        current_idx = np.argmin(np.abs(cycle_time_display - flag['time']))

        # Move to adjacent data point
        new_idx = current_idx + direction
        new_idx = max(0, min(len(cycle_time_display) - 1, new_idx))  # Clamp to valid range

        # Update flag position
        new_time = cycle_time_display[new_idx]
        new_spr = cycle_spr_display[new_idx]

        # Remove old marker
        self.main_window.cycle_of_interest_graph.removeItem(flag['marker'])

        # Create new marker at new position
        import pyqtgraph as pg
        flag_styles = {
            'injection': {'symbol': 't', 'size': 15, 'color': (255, 50, 50, 230)},
            'wash': {'symbol': 's', 'size': 12, 'color': (50, 150, 255, 230)},
            'spike': {'symbol': 'star', 'size': 18, 'color': (255, 200, 0, 230)}
        }
        style = flag_styles.get(flag['type'], flag_styles['injection'])

        new_marker = pg.ScatterPlotItem(
            [new_time],
            [new_spr],
            symbol=style['symbol'],
            size=style['size'],
            brush=pg.mkBrush(*style['color']),
            pen=pg.mkPen('w', width=2)
        )
        self.main_window.cycle_of_interest_graph.addItem(new_marker)

        # Update flag data
        flag['time'] = new_time
        flag['spr'] = new_spr
        flag['marker'] = new_marker

        # Update highlight ring position
        self._highlight_selected_flag(self._selected_flag_idx)

        # If this is an injection flag and NOT the reference, recalculate alignment
        if flag['type'] == 'injection' and self._injection_reference_time is not None:
            if flag['channel'] != self._injection_reference_channel:
                time_diff = new_time - self._injection_reference_time
                shift_amount = -time_diff
                self._channel_time_shifts[channel] = shift_amount

                # Export updated time shift to recording metadata
                if self.recording_mgr.is_recording:
                    self.recording_mgr.update_metadata(f'channel_{channel}_time_shift', shift_amount)

                self._update_cycle_of_interest_graph()
                logger.info(f"→ Moved & realigned Channel {channel.upper()}: shift={shift_amount:+.2f}s")
            else:
                # Moving the reference flag - update reference time
                old_ref = self._injection_reference_time
                self._injection_reference_time = new_time

                # Update alignment line
                if self._injection_alignment_line is not None:
                    self._injection_alignment_line.setPos(new_time)

                logger.info(f"→ Moved reference flag: {old_ref:.2f}s → {new_time:.2f}s")
        else:
            logger.debug(f"Flag moved: t={new_time:.2f}s, SPR={new_spr:.2f} RU")

    def _deselect_flag(self):
        """Deselect currently selected flag."""
        if self._flag_highlight_ring is not None:
            self.main_window.cycle_of_interest_graph.removeItem(self._flag_highlight_ring)
            self._flag_highlight_ring = None

        self._selected_flag_idx = None
        logger.debug("Flag deselected")

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

    def _on_led_brightness_changed(self, channel: str, value: str):
        """Handle live LED brightness changes from Settings tab inputs.

        Args:
            channel: LED channel letter ('a', 'b', 'c', 'd')
            value: Brightness value as string (0-255)
        """
        try:
            # Validate and parse brightness value
            if not value or value.strip() == "":
                return  # Empty input, do nothing

            brightness = int(value)

            # Validate range
            if not (0 <= brightness <= 255):
                logger.debug(f"LED {channel.upper()}: value {brightness} out of range (0-255)")
                return

            # Apply to hardware immediately
            if self.hardware_mgr and self.hardware_mgr.ctrl:
                self.hardware_mgr.ctrl.set_intensity(channel, brightness)
                logger.debug(f"LED {channel.upper()} set to {brightness} (live update)")

                # Save to device config
                if self.main_window.device_config:
                    # Get current LED values
                    led_a = int(self.main_window.channel_a_input.text() or "0")
                    led_b = int(self.main_window.channel_b_input.text() or "0")
                    led_c = int(self.main_window.channel_c_input.text() or "0")
                    led_d = int(self.main_window.channel_d_input.text() or "0")

                    # Save all values to config
                    self.main_window.device_config.set_led_intensities(
                        led_a, led_b, led_c, led_d
                    )
                    self.main_window.device_config.save()
            else:
                logger.debug(f"LED {channel.upper()}: hardware not connected")

        except ValueError:
            # Invalid integer, ignore
            logger.debug(f"LED {channel.upper()}: invalid value '{value}'")
        except Exception as e:
            logger.error(f"Error updating LED {channel.upper()}: {e}")

    def _on_unit_changed(self, checked: bool):
        """Toggle between RU and nm units for display."""
        self.ui_control_events.on_unit_changed(checked)

    def _on_colorblind_toggled(self, checked: bool):
        """Colorblind-friendly palette toggled."""

        # Add settings to path if not already there
        # Path already added at module initialization - no need to re-add
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

        # Update edits tab graphs (primary and timeline)
        if hasattr(self.main_window, 'edits_tab'):
            # Update primary graph curves
            if hasattr(self.main_window.edits_tab, 'edits_graph_curves'):
                for i, color in enumerate(color_list):
                    if i < len(self.main_window.edits_tab.edits_graph_curves):
                        self.main_window.edits_tab.edits_graph_curves[i].setPen(
                            pg.mkPen(color=color, width=2),
                        )

            # Update timeline graph curves
            if hasattr(self.main_window.edits_tab, 'edits_timeline_curves'):
                for i, color in enumerate(color_list):
                    if i < len(self.main_window.edits_tab.edits_timeline_curves):
                        self.main_window.edits_tab.edits_timeline_curves[i].setPen(
                            pg.mkPen(color=color, width=2),
                        )

            # Update Edits tab channel buttons (ABCD)
            if hasattr(self.main_window.edits_tab, 'edits_channel_buttons'):
                channel_letters = ["A", "B", "C", "D"]
                for i, ch in enumerate(channel_letters):
                    if ch in self.main_window.edits_tab.edits_channel_buttons and i < len(color_list):
                        btn = self.main_window.edits_tab.edits_channel_buttons[ch]
                        color = color_list[i]
                        btn.setStyleSheet(
                            f"QPushButton {{ background: {color}; color: white; border: none; "
                            f"border-radius: 4px; font-size: 11px; font-weight: 600; }}"
                            "QPushButton:!checked { background: rgba(0, 0, 0, 0.06); color: #86868B; }"
                        )

        logger.info("[OK] Graph colors updated successfully")

    # === CALIBRATION WORKFLOWS ===

    def _restart_acquisition_after_calibration(self):
        """Helper method to restart acquisition from main thread after calibration."""
        # Resume live spectrum updates after calibration
        if hasattr(self, 'ui_updates') and self.ui_updates is not None:
            logger.info("Resuming live spectrum updates after calibration...")
            self.ui_updates.set_transmission_updates_enabled(True)
            self.ui_updates.set_raw_spectrum_updates_enabled(True)

        if hasattr(self, 'data_mgr') and self.data_mgr:
            logger.info("🔄 Restarting live data acquisition...")
            try:
                self.data_mgr.start_acquisition()
                logger.info("✅ Live data acquisition restarted")
            except Exception as e:
                logger.error(f"Failed to restart live data: {e}")

    def _on_simple_led_calibration(self):
        """Run simple LED intensity adjustment (quick, for sensor swaps)."""
        logger.info("Starting Simple LED Calibration...")

        # Check if hardware is connected
        if not self.hardware_mgr.ctrl or not self.hardware_mgr.usb:
            ui_error(
                self,
                "Hardware Not Connected",
                "Please connect hardware before running LED calibration.\n\n"
                "Use the power button to connect to the device.",
            )
            return

        # Stop live data if running
        if hasattr(self, 'data_mgr') and self.data_mgr and self.data_mgr._acquiring:
            logger.info("🛑 Stopping live data acquisition before calibration...")
            self.data_mgr.stop_acquisition()
            import time
            time.sleep(0.1)
            logger.info("[OK] Live data stopped")

        # Pause live spectrum updates during calibration
        if hasattr(self, 'ui_updates') and self.ui_updates is not None:
            logger.info("Pausing live spectrum updates during calibration...")
            self.ui_updates.set_transmission_updates_enabled(False)
            self.ui_updates.set_raw_spectrum_updates_enabled(False)

        # Import simple calibration function
        try:
            from affilabs.core.simple_led_calibration import run_simple_led_calibration
        except ImportError as e:
            logger.error(f"Failed to import simple calibration module: {e}")
            ui_error(
                self,
                "Import Error",
                f"Could not load simple calibration module.\n\n{e}",
            )
            return

        # Show progress dialog
        from affilabs.dialogs.startup_calib_dialog import StartupCalibProgressDialog

        message = (
            "Simple LED Calibration - Quick Intensity Adjustment\n\n"
            "This calibration quickly adjusts LED intensities for sensor swaps:\n\n"
            "  • Uses existing LED calibration model\n"
            "  • Quick S-mode convergence (3-5 iterations)\n"
            "  • Quick P-mode convergence (3-5 iterations)\n"
            "  • Updates device config\n\n"
            "Duration: ~10-20 seconds\n\n"
            "Requirements:\n"
            "  ✓ LED model already exists (run OEM calibration first if needed)\n"
            "  ✓ Prism installed with water/buffer\n"
            "  ✓ No air bubbles"
        )

        dialog = StartupCalibProgressDialog(
            parent=self.main_window,
            title="Simple LED Calibration",
            message=message,
            show_start_button=False,  # Auto-start (quick operation, ~10-20 seconds)
        )
        dialog.show()

        # Run calibration in thread
        import threading

        def progress_callback(msg, percent):
            """Update progress dialog."""
            dialog.update_status(msg)
            dialog.set_progress(percent, 100)

        def run_calibration():
            """Thread worker for simple calibration."""
            try:
                success = run_simple_led_calibration(
                    self.hardware_mgr,
                    progress_callback=progress_callback,
                )

                if success:
                    dialog.update_status("✅ Simple calibration complete!")
                    dialog.set_progress(100, 100)
                    logger.info("✅ Simple LED calibration completed successfully")

                    # Clear graphs and restart sensorgram at t=0 (must be on main thread)
                    # Use QTimer.singleShot to call from main thread
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(0, self._on_clear_graphs_requested)
                    logger.info("✓ Scheduled sensorgram reset on main thread")

                    # Restart live data acquisition (also from main thread)
                    QTimer.singleShot(100, self._restart_acquisition_after_calibration)
                else:
                    dialog.update_status("❌ Simple calibration failed")
                    dialog.set_progress(100, 100)
                    logger.error("❌ Simple LED calibration failed")

                # Auto-close after 2 seconds
                import time
                time.sleep(2)
                dialog.close_from_thread()

            except Exception as e:
                logger.error(f"Simple calibration error: {e}")
                import traceback
                traceback.print_exc()
                dialog.update_status(f"❌ Error: {e}")
                dialog.set_progress(100, 100)
                import time
                time.sleep(3)
                dialog.close_from_thread()

        # Show progress bar and start thread
        dialog.show_progress_bar()
        thread = threading.Thread(target=run_calibration, daemon=True, name="SimpleCalibration")
        thread.start()

    def _on_polarizer_calibration(self):
        """Run servo polarizer calibration using existing hardware connection."""
        logger.info("Starting Polarizer Calibration...")

        # Check if hardware is connected
        if not self.hardware_mgr or not self.hardware_mgr.ctrl or not self.hardware_mgr.usb:
            from affilabs.ui.ui_message import error as ui_error
            ui_error(
                self.main_window,
                "Hardware Not Connected",
                "Polarizer calibration requires connected hardware.\n"
                "Please ensure the controller and detector are connected."
            )
            logger.error("Cannot run polarizer calibration - hardware not connected")
            return

        # Stop live data if running
        if hasattr(self, 'data_mgr') and self.data_mgr and self.data_mgr._acquiring:
            logger.info("🛑 Stopping live data acquisition before polarizer calibration...")
            self.data_mgr.stop_acquisition()
            import time
            time.sleep(0.2)
            logger.info("[OK] Live data stopped")

        # Pause live spectrum updates during calibration
        if hasattr(self, 'ui_updates') and self.ui_updates is not None:
            logger.info("Pausing live spectrum updates during calibration...")
            self.ui_updates.set_transmission_updates_enabled(False)
            self.ui_updates.set_raw_spectrum_updates_enabled(False)

        # Create progress dialog
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import Qt

        progress = QProgressDialog(
            "Initializing polarizer calibration...",
            "Cancel",
            0,
            100,
            self.main_window
        )
        progress.setWindowTitle("Polarizer Calibration")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()

        # Progress callback to update dialog
        def update_progress(message, value):
            if progress.wasCanceled():
                return
            progress.setLabelText(message)
            progress.setValue(int(value))
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()

        # Import and run the servo calibration with existing hardware
        try:
            from servo_polarizer_calibration.calibrate_polarizer import run_calibration_with_hardware

            # Run calibration using existing hardware manager
            logger.info("Running polarizer calibration with connected hardware...")
            update_progress("Running polarizer calibration...", 10)

            success = run_calibration_with_hardware(self.hardware_mgr, progress_callback=update_progress)

            progress.close()

            if success:
                # Sync calibrated positions into the live system:
                # 1. Read from disk JSON (where calibrate_polarizer wrote them)
                # 2. Update in-memory DeviceConfiguration (prevents save() from clobbering)
                # 3. Load into controller RAM (so set_mode works immediately)
                try:
                    import json

                    serial_number = None
                    if hasattr(self, 'hardware_mgr') and self.hardware_mgr:
                        if hasattr(self.hardware_mgr, 'detector') and self.hardware_mgr.detector:
                            serial_number = getattr(self.hardware_mgr.detector, 'serial_number', None)

                    if serial_number:
                        config_path = Path(__file__).parent / "affilabs" / "config" / "devices" / serial_number / "device_config.json"
                    else:
                        config_path = Path(__file__).parent / "affilabs" / "config" / "device_config.json"

                    with open(config_path) as f:
                        config = json.load(f)

                    s_position = config.get("hardware", {}).get("servo_s_position")
                    p_position = config.get("hardware", {}).get("servo_p_position")

                    if s_position is not None and p_position is not None:
                        logger.info(f"Syncing calibrated servo positions: S={s_position}, P={p_position}")

                        # Update in-memory DeviceConfiguration so save() won't clobber
                        if self.main_window.device_config:
                            self.main_window.device_config.set_servo_positions(s_position, p_position)
                            logger.info("  -> In-memory DeviceConfiguration updated")

                        # Load into controller RAM so set_mode() works now
                        if self.hardware_mgr and self.hardware_mgr.ctrl:
                            self.hardware_mgr.ctrl.set_servo_positions(s=s_position, p=p_position)
                            logger.info("  -> Controller RAM updated")

                        # Update UI inputs
                        if hasattr(self.main_window, 's_position_input'):
                            self.main_window.s_position_input.setText(str(s_position))
                        if hasattr(self.main_window, 'p_position_input'):
                            self.main_window.p_position_input.setText(str(p_position))
                    else:
                        logger.warning("Servo positions not found in device_config.json after calibration")
                except Exception as e:
                    logger.error(f"Failed to sync servo positions after calibration: {e}")

                # Clear graphs and restart sensorgram at t=0
                logger.info("📊 Clearing graph and restarting sensorgram...")
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self._on_clear_graphs_requested)

                # Restart live data acquisition
                logger.info("🔄 Restarting live data acquisition...")
                QTimer.singleShot(100, self._restart_acquisition_after_calibration)

                # Give UI time to update before showing completion dialog
                from PySide6.QtWidgets import QApplication
                import time
                QApplication.processEvents()
                time.sleep(0.3)
                QApplication.processEvents()

                ui_info(
                    self.main_window,
                    "Calibration Complete",
                    "Polarizer calibration completed successfully!\n"
                    "Servo moved to P position and live data resumed."
                )
            else:
                from affilabs.ui.ui_message import warn as ui_warn
                ui_warn(
                    self.main_window,
                    "Calibration Issue",
                    "Polarizer calibration completed with warnings.\n"
                    "Please check the logs for details."
                )

        except Exception as e:
            progress.close()
            logger.error(f"Polarizer calibration failed: {e}")
            logger.exception("Servo calibration error")
            from affilabs.ui.ui_message import error as ui_error
            ui_error(
                self.main_window,
                "Calibration Failed",
                f"Polarizer calibration encountered an error:\n{str(e)}"
            )

    def _on_oem_led_calibration(self):
        """Run full OEM calibration (servo + LED) via CalibrationService.

        This ALWAYS rebuilds the optical model, regardless of whether one exists.
        Shows dialog with "Start" button BEFORE beginning calibration.
        """
        from affilabs.dialogs.startup_calib_dialog import StartupCalibProgressDialog

        # Show pre-calibration dialog with Start button
        dialog = StartupCalibProgressDialog(
            parent=self.main_window,
            title="OEM Calibration",
            message=(
                "OEM Calibration Process:\n\n"
                "  STEP 1: Servo Polarizer Calibration\n"
                "    • Finds optimal S and P positions\n"
                "    • Takes ~2-5 minutes\n\n"
                "  STEP 2: LED Model Training\n"
                "    • Measures LED response at 10-60ms\n"
                "    • Creates 3-stage linear model\n"
                "    • Takes ~2 minutes\n\n"
                "  STEP 3: Full 6-Step Calibration\n"
                "    • LED convergence for S and P modes\n"
                "    • Reference spectrum capture\n"
                "    • Takes ~3-5 minutes\n\n"
                "Total time: ~10-15 minutes\n\n"
                "Click Start to begin."
            ),
            show_start_button=True,
        )

        def on_start():
            """Called when user clicks Start button."""
            logger.info("=" * 80)
            logger.info("Starting OEM Calibration (will rebuild optical model)...")
            logger.info("=" * 80)
            dialog.hide_start_button()
            dialog.show_progress_bar()

            # Pause live spectrum updates during calibration
            if hasattr(self, 'ui_updates') and self.ui_updates is not None:
                logger.info("Pausing live spectrum updates during calibration...")
                self.ui_updates.set_transmission_updates_enabled(False)
                self.ui_updates.set_raw_spectrum_updates_enabled(False)

            # CRITICAL: Pass the dialog to calibration service to avoid creating a second dialog
            # Set the existing dialog as the calibration dialog before starting
            self.calibration._calibration_dialog = dialog
            self.calibration._force_oem_retrain = True

            # Connect calibration service signals to THIS dialog
            self.calibration.calibration_progress.connect(lambda msg, prog: dialog.update_status(msg))
            self.calibration.calibration_progress.connect(lambda msg, prog: dialog.set_progress(prog, 100))

            # Start calibration WITHOUT creating a new dialog (headless mode)
            self.calibration._running = True
            import threading
            self.calibration._thread = threading.Thread(
                target=self.calibration._run_calibration,
                daemon=True,
                name="CalibrationService",
            )
            self.calibration._thread.start()
            self.calibration.calibration_started.emit()
            logger.info("[OK] Calibration thread started (using existing dialog)")

        dialog.start_clicked.connect(on_start)
        dialog.show()
        dialog.enable_start_button_pre_calib()  # Enable the Start button after dialog is visible

    def _on_led_model_training(self):
        """Run LED model training only (no full calibration).

        Directly trains the 3-stage linear LED model without running the full
        6-step calibration. Useful for quickly rebuilding the optical model.
        """
        logger.info("=" * 80)
        logger.info("Starting LED Model Training (optical model only)...")
        logger.info("=" * 80)

        # Import required modules
        from affilabs.core.oem_model_training import run_oem_model_training_workflow
        from affilabs.dialogs.startup_calib_dialog import StartupCalibProgressDialog
        import threading

        # Check hardware
        if not self.hardware_mgr or not self.hardware_mgr.ctrl or not self.hardware_mgr.usb:
            from affilabs.ui.ui_message import error as ui_error
            ui_error(
                self.main_window,
                "Hardware Not Ready",
                "Please connect hardware before training the LED model."
            )
            return

        # Stop live data if running
        if hasattr(self, 'data_mgr') and self.data_mgr and self.data_mgr._acquiring:
            logger.info("🛑 Stopping live data acquisition before LED model training...")
            self.data_mgr.stop_acquisition()
            import time
            time.sleep(0.1)
            logger.info("[OK] Live data stopped")

        # Pause live spectrum updates during calibration
        if hasattr(self, 'ui_updates') and self.ui_updates is not None:
            logger.info("Pausing live spectrum updates during LED model training...")
            self.ui_updates.set_transmission_updates_enabled(False)
            self.ui_updates.set_raw_spectrum_updates_enabled(False)

        # Show progress dialog
        dialog = StartupCalibProgressDialog(
            parent=self.main_window,
            title="Training LED Model",
            message=(
                "LED Model Training Process:\n\n"
                "  1. Servo Polarizer Calibration (if P4SPR)\n"
                "  2. LED Response Measurement (10-60ms)\n"
                "  3. 3-Stage Linear Model Fitting\n"
                "  4. Model File Creation\n\n"
                "This will take approximately 2-5 minutes.\n\n"
                "Click Start to begin."
            ),
            show_start_button=True,
        )

        def progress_callback(message: str, percent: int):
            """Update progress dialog."""
            dialog.update_status(message)
            dialog.set_progress(percent, 100)
            if not dialog.progress_bar.isVisible():
                dialog.show_progress_bar()

        def run_training():
            """Run training in background thread."""
            try:
                logger.info("🔬 LED Model Training thread started...")

                # Run OEM model training workflow
                success = run_oem_model_training_workflow(
                    hardware_mgr=self.hardware_mgr,
                    progress_callback=progress_callback,
                )

                if success:
                    logger.info("[OK] LED model training completed successfully")
                    dialog.update_title("LED Model Training Complete")
                    dialog.update_status("✓ Model created successfully!")
                    dialog.hide_progress_bar()

                    # Clear graphs and restart sensorgram at t=0 (use QTimer for thread safety)
                    from PySide6.QtCore import QTimer

                    logger.info("📊 Clearing graph and restarting sensorgram...")
                    QTimer.singleShot(0, self._on_clear_graphs_requested)

                    # Restart live data acquisition (also from main thread)
                    QTimer.singleShot(100, self._restart_acquisition_after_calibration)

                    # Show success dialog (also from main thread for safety)
                    from PySide6.QtCore import QMetaObject, Qt as QtCore
                    import time
                    time.sleep(0.5)  # Brief delay before showing dialog

                    QMetaObject.invokeMethod(
                        dialog,
                        "close",
                        QtCore.ConnectionType.QueuedConnection
                    )

                    ui_info(
                        self.main_window,
                        "Training Complete",
                        "LED calibration model created successfully!\n\n"
                        "The new model is now active and will be used for all calibrations."
                    )
                else:
                    logger.error("[ERROR] LED model training failed")
                    dialog.update_title("Training Failed")
                    dialog.update_status("❌ Model training encountered errors")
                    dialog.hide_progress_bar()

                    from affilabs.ui.ui_message import error as ui_error
                    from PySide6.QtCore import QMetaObject, Qt as QtCore
                    import time

                    time.sleep(0.5)  # Brief delay before showing error

                    QMetaObject.invokeMethod(
                        dialog,
                        "close",
                        QtCore.ConnectionType.QueuedConnection
                    )

                    ui_error(
                        self.main_window,
                        "Training Failed",
                        "LED model training failed.\n\nPlease check the logs for details."
                    )

            except Exception as e:
                logger.error(f"LED model training error: {e}", exc_info=True)
                dialog.update_title("Training Error")
                dialog.update_status(f"Error: {str(e)}")
                dialog.hide_progress_bar()

        def on_start_clicked():
            """Handle Start button click."""
            dialog.start_button.setEnabled(False)
            dialog.show_progress_bar()
            dialog.update_status("Initializing LED model training...")

            # Start training thread
            thread = threading.Thread(target=run_training, daemon=True, name="LEDModelTraining")
            thread.start()

        # Connect start button
        dialog.start_clicked.connect(on_start_clicked)
        dialog.show()
        dialog.enable_start_button_pre_calib()  # Enable the Start button after dialog is visible

    def _on_record_baseline_clicked(self):
        """Handle Record Baseline Data button click."""
        logger.info("="*80)
        logger.info("[HANDLER] _on_record_baseline_clicked CALLED")
        logger.info("="*80)
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
            # Cancel any running cycle first (stops timers, unlocks queue)
            self._cancel_active_cycle()

            # Stop data acquisition (prevents new data from coming in)
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

            # Reset application state (fresh state for next power on)
            logger.info("🧹 Resetting application state...")
            try:
                # Reset connection and calibration flags
                self._device_config_initialized = False
                self._initial_connection_done = False
                self._calibration_completed = False

                # Clear data buffers
                if hasattr(self, 'buffer_mgr') and self.buffer_mgr:
                    self.buffer_mgr.clear_all()
                    logger.debug("  ✓ Data buffers cleared")

                # Reset data manager calibration state
                if self.data_mgr:
                    self.data_mgr.calibrated = False
                    logger.debug("  ✓ Data manager calibration flag reset")

                # Reset experiment timing
                self.experiment_start_time = None
                logger.debug("  ✓ Experiment timing reset")

                logger.info("[OK] Application state reset complete")
            except Exception as e:
                logger.error(f"Error resetting application state: {e}")

            # Update UI to disconnected state
            self.main_window.set_power_state("disconnected")

            logger.info(
                "[OK] Graceful shutdown complete - software ready for next power cycle",
            )

        except Exception as e:
            logger.error(f"Error during power off: {e}")
            # Still update UI even if errors occurred
            self.main_window.set_power_state("disconnected")
            from affilabs.widgets.message import show_message

            show_message(f"Power off completed with errors: {e}", "Warning")

    def _on_recording_start_requested(self):
        """User requested to start recording - show confirmation popup first."""
        from PySide6.QtWidgets import QMessageBox
        from affilabs.utils.time_utils import for_filename

        logger.info("[RECORD-HANDLER] Recording start requested - showing confirmation")

        # Log current queue state for debugging
        logger.info(f"📋 Current queue state: {len(self.segment_queue)} cycles")
        for i, cycle in enumerate(self.segment_queue):
            logger.info(f"  [{i}] {cycle.name} ({cycle.type}, {cycle.length_minutes} min)")

        # Reset cycle type counter for new recording session
        if hasattr(self.main_window, '_cycle_type_counts'):
            self.main_window._cycle_type_counts = {}

        # Prepare filename and destination
        timestamp = for_filename().replace(".", "_")
        default_filename = f"AffiLabs_data_{timestamp}"
        default_directory = self.recording_mgr.output_directory

        # Get current export settings
        filename = self.main_window.sidebar.export_filename_input.text() or default_filename
        destination = self.main_window.sidebar.export_dest_input.text() or str(default_directory)

        # Get current user and create user-specific directory structure
        current_user = None
        if combo := self._sidebar_widget('user_combo'):
            current_user = combo.currentText()

        if current_user:
            # Create: output/Username/SPR_data/
            destination_path = Path(destination) / current_user / "SPR_data"
            destination_path.mkdir(parents=True, exist_ok=True)
            destination = str(destination_path)
            logger.info(f"Using user-specific directory: {destination}")

        # Use Excel format (format selector was removed for consistency)
        extension = ".xlsx"

        # Ensure filename has extension
        if not any(filename.endswith(ext) for ext in ['.xlsx', '.csv', '.json', '.h5']):
            filename = filename + extension

        full_path = Path(destination) / filename

        # Show confirmation dialog
        msg = QMessageBox(self.main_window)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Start Recording")

        # Format message with prominent path styling
        message_html = (
            "<p style='font-size: 13px;'>Data will be recorded as:</p>"
            f"<p style='font-size: 14px; font-weight: bold; color: #1D1D1F; background: #F5F5F7; padding: 8px; border-radius: 4px;'>"
            f"{filename}</p>"
            "<p style='font-size: 13px; margin-top: 12px;'>In folder:</p>"
            f"<p style='font-size: 13px; font-weight: 600; color: #007AFF; background: #F0F6FF; padding: 8px; border-radius: 4px; font-family: monospace;'>"
            f"{destination}</p>"
        )

        msg.setText(message_html)
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setInformativeText("Change settings in Export tab if needed, or start live recording now.")

        start_btn = msg.addButton("▶️ Start Recording", QMessageBox.AcceptRole)
        cancel_btn = msg.addButton("Cancel", QMessageBox.RejectRole)
        msg.setDefaultButton(start_btn)

        msg.exec()

        if msg.clickedButton() == cancel_btn:
            logger.info("Recording cancelled by user")
            # Reset button state since recording didn't start
            self.main_window.set_recording_state(is_recording=False)
            return

        # User confirmed - start recording with file
        logger.info(f"Starting recording to file: {full_path}")

        # Store current elapsed time as recording start marker
        # This allows us to: (1) draw vertical line on graph, (2) save data with t=0 at recording start
        current_time = time.time()
        if self.experiment_start_time is not None:
            recording_start_elapsed = current_time - self.experiment_start_time
        else:
            recording_start_elapsed = 0.0

        # Start recording and pass the elapsed time offset
        self.recording_mgr.start_recording(filename=str(full_path), time_offset=recording_start_elapsed)

        # Add visual marker on Live Sensorgram showing recording started
        if hasattr(self.main_window, 'full_timeline_graph'):
            try:
                import pyqtgraph as pg
                from PySide6.QtGui import QColor

                # CRITICAL: Adjust marker position to account for display offset
                # The graph skips the first point and rebases time to start at 0
                # So we need to subtract the display offset to align with what's shown
                marker_position = recording_start_elapsed - self._display_time_offset

                logger.info(f"Recording marker: raw_time={recording_start_elapsed:.3f}s, offset={self._display_time_offset:.3f}s, display_pos={marker_position:.3f}s")

                # Create vertical green dashed line at recording start time
                marker = pg.InfiniteLine(
                    pos=marker_position,
                    angle=90,  # Vertical
                    pen=pg.mkPen(color=QColor(34, 139, 34), width=2, style=Qt.DashLine),
                    movable=False,
                    label='REC',
                    labelOpts={
                        'position': 0.95,
                        'color': (34, 139, 34),
                        'fill': (255, 255, 255, 200),
                        'movable': False
                    }
                )

                # Store marker reference for cleanup
                if not hasattr(self, '_recording_markers'):
                    self._recording_markers = []
                self._recording_markers.append(marker)

                # Add to plot
                self.main_window.full_timeline_graph.addItem(marker)
                logger.info(f"✓ Recording marker added at display position t={marker_position:.1f}s")
            except Exception as e:
                logger.warning(f"Could not add recording marker: {e}")

        # Update UI state
        self.main_window.set_recording_state(is_recording=True, filename=filename)

    def _on_recording_stop_requested(self):
        """User requested to stop recording."""
        logger.info("Recording stop requested...")

        # Stop the recording
        self.recording_mgr.stop_recording()

        # Cancel any running cycle so the queue doesn't keep executing
        self._cancel_active_cycle()

        # Update UI state to reflect recording stopped
        self.main_window.set_recording_state(is_recording=False)

    def _on_clear_graphs_requested(self):
        """Handle clear graphs button click - clear all buffer data and reset timeline."""
        logger.info("[UI] Clear graphs requested")
        try:
            # Increment session epoch - invalidates all old data in one atomic operation
            self._session_epoch += 1

            # Reset experiment start time and display offset
            self.experiment_start_time = None
            self._display_time_offset = 0.0

            # Clear processing queue to remove old data with old timestamps
            if hasattr(self, "_spectrum_queue") and self._spectrum_queue:
                # Drain the queue
                cleared_count = 0
                try:
                    while not self._spectrum_queue.empty():
                        self._spectrum_queue.get_nowait()
                        cleared_count += 1
                except:
                    pass
                if cleared_count > 0:
                    logger.info(f"[OK] Cleared {cleared_count} items from processing queue")

            # Clear all data buffers
            if hasattr(self, "buffer_mgr") and self.buffer_mgr:
                self.buffer_mgr.clear_all()
                logger.info("[OK] Buffer data cleared successfully")
            else:
                logger.warning("[WARN] Buffer manager not available")

            # Clear visual graph data
            if hasattr(self, "sensogram_presenter") and self.sensogram_presenter:
                self.sensogram_presenter.clear_all_graphs()
                logger.info("[OK] Graph visual data cleared")

            # Clear recording markers from Live Sensorgram
            if hasattr(self, '_recording_markers') and hasattr(self.main_window, 'full_timeline_graph'):
                marker_count = len(self._recording_markers)
                for marker in self._recording_markers:
                    try:
                        self.main_window.full_timeline_graph.removeItem(marker)
                    except Exception as e:
                        logger.debug(f"Could not remove recording marker: {e}")
                self._recording_markers.clear()
                logger.info(f"[OK] Cleared {marker_count} recording markers")

            # Reset cursors to position 0 AFTER clearing graphs
            if hasattr(self.main_window, 'full_timeline_graph'):
                timeline = self.main_window.full_timeline_graph
                if hasattr(timeline, 'start_cursor') and timeline.start_cursor:
                    logger.info(f"[CLEAR] Start cursor before reset: {timeline.start_cursor.value()}")
                    timeline.start_cursor.setValue(0)
                    timeline.start_cursor.setPos(0)  # Force position update
                    logger.info(f"[CLEAR] Start cursor after reset: {timeline.start_cursor.value()}")
                if hasattr(timeline, 'stop_cursor') and timeline.stop_cursor:
                    logger.info(f"[CLEAR] Stop cursor before reset: {timeline.stop_cursor.value()}")
                    timeline.stop_cursor.setValue(0)
                    timeline.stop_cursor.setPos(0)  # Force position update
                    logger.info(f"[CLEAR] Stop cursor after reset: {timeline.stop_cursor.value()}")
                logger.info("✓ Cursors reset to t=0")

            logger.info("🔄 Timeline reset complete - next data point will start at t=0")

        except Exception as e:
            logger.error(f"[ERROR] Error clearing buffer data: {e}", exc_info=True)

    def _on_clear_flags_requested(self):
        """Handle clear flags button click - clear all flag data."""
        logger.info("[UI] Clear flags requested")
        try:
            # Delegate to FlagManager
            self.flag_mgr.clear_all_flags()

            # Also clear legacy _flag_data for backward compatibility
            if hasattr(self, "_flag_data"):
                self._flag_data.clear()
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

        # Treat P4PROPLUS internal pumps as a flow-capable pump for UI purposes
        try:
            has_internal_pumps = False

            # Prefer raw controller from HardwareManager (has firmware_id/has_internal_pumps)
            if hasattr(self, "hardware_mgr") and self.hardware_mgr:
                raw_ctrl = getattr(self.hardware_mgr, "_ctrl_raw", None)
                if raw_ctrl is not None:
                    if hasattr(raw_ctrl, "firmware_id") and raw_ctrl.firmware_id:
                        try:
                            fw_id = str(raw_ctrl.firmware_id).lower()
                            if "p4proplus" in fw_id:
                                has_internal_pumps = True
                        except Exception:
                            pass
                    if (not has_internal_pumps and
                            hasattr(raw_ctrl, "has_internal_pumps")):
                        try:
                            has_internal_pumps = bool(raw_ctrl.has_internal_pumps())
                        except Exception:
                            pass

            # Fallback to HAL controller adapter if present
            if (not has_internal_pumps and
                    hasattr(self, "ctrl") and self.ctrl and
                    hasattr(self.ctrl, "has_internal_pumps")):
                try:
                    has_internal_pumps = bool(self.ctrl.has_internal_pumps())
                except Exception:
                    pass

            # If we have internal pumps but no external AffiPump flag, mark pump_connected
            if has_internal_pumps and not status.get("pump_connected"):
                status["pump_connected"] = True
                logger.info(
                    "[UI] P4PROPLUS internal pumps detected - treating as flow-capable pump (pump_connected=True)",
                )

            # NOTE: fluidics_ready should NOT be set here - it should be set AFTER calibration
            # by the hardware_manager when flow_calibrated becomes True
            # Premature fluidics_ready causes flow button to turn green before calibration
        except Exception as e:
            # Never let UI status updates crash the app
            logger.debug(f"Error while inferring internal pump capability: {e}")

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
            # Start plunger polling timer
            if hasattr(self, '_plunger_poll_timer') and not self._plunger_poll_timer.isActive():
                self._plunger_poll_timer.start()
                logger.debug("✓ Started plunger position polling (5s interval)")

        # Start valve polling when controller is connected
        if status.get("knx_type") != "None":
            if hasattr(self, '_valve_poll_timer') and not self._valve_poll_timer.isActive():
                self._valve_poll_timer.start()
                logger.debug("✓ Started valve position polling (3s interval)")

        # Forward to main window for hardware list and subunit readiness updates
        logger.debug(f"📤 Forwarding status to main_window.update_hardware_status: flow_calibrated={status.get('flow_calibrated', 'NOT SET')}")
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
                self.spectroscopy_presenter.update_transmission(
                    channel,
                    wavelengths,
                    transmission,
                )
            except Exception as e:
                logger.error(f"Failed to update transmission spectrum: {e}")

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
        """Run servo polarizer calibration automatically."""
        logger.info("🔧 Auto-triggering servo polarizer calibration...")
        self._on_polarizer_calibration()

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

    def _on_copy_graph_to_clipboard(self):
        """Copy active cycle graph to clipboard."""
        from PySide6.QtWidgets import QApplication

        try:
            # Check if there's data to copy
            has_data = False
            for ch in self._idx_to_channel:
                if len(self.buffer_mgr.cycle_data[ch].time) > 0:
                    has_data = True
                    break

            if not has_data:
                from affilabs.widgets.message import show_message
                show_message("No cycle data to copy", "Warning")
                return

            # Get graph widget
            graph_widget = self.main_window.cycle_of_interest_graph

            # Export graph to image
            exporter = graph_widget.grab()

            # Copy to clipboard
            clipboard = QApplication.clipboard()
            clipboard.setPixmap(exporter)

            logger.info("✓ Active cycle graph copied to clipboard")
            from affilabs.widgets.message import show_message
            show_message("Graph copied to clipboard!\nYou can now paste it into documents.", "Information")

        except Exception as e:
            logger.error(f"Failed to copy graph to clipboard: {e}")
            from affilabs.widgets.message import show_message
            show_message(f"Failed to copy graph:\n{e}", "Error")

    def _on_load_current_settings(self):
        """Load current hardware settings from device_config into UI inputs."""
        try:
            if not self.main_window.device_config:
                from affilabs.widgets.message import show_message
                show_message("No device configuration loaded", "Warning")
                return

            # Get servo positions
            positions = self.main_window.device_config.get_servo_positions()
            if positions:
                s_pos, p_pos = positions
                self.main_window.sidebar.s_position_input.setText(str(s_pos))
                self.main_window.sidebar.p_position_input.setText(str(p_pos))

            # Get LED intensities
            intensities = self.main_window.device_config.get_led_intensities()
            if intensities:
                self.main_window.channel_a_input.setText(str(intensities.get('a', 0)))
                self.main_window.channel_b_input.setText(str(intensities.get('b', 0)))
                self.main_window.channel_c_input.setText(str(intensities.get('c', 0)))
                self.main_window.channel_d_input.setText(str(intensities.get('d', 0)))

            logger.info("✓ Current settings loaded into UI")
            from affilabs.widgets.message import show_message
            show_message("Settings loaded successfully", "Information")

        except Exception as e:
            logger.error(f"Failed to load current settings: {e}")
            from affilabs.widgets.message import show_message
            show_message(f"Failed to load settings:\n{e}", "Error")

    def _on_apply_settings(self):
        """Apply settings from UI inputs to device_config and hardware."""
        try:
            if not self.main_window.device_config:
                from affilabs.widgets.message import show_message
                show_message("No device configuration loaded", "Warning")
                return

            # Get values from UI
            try:
                s_pos = int(self.main_window.sidebar.s_position_input.text())
                p_pos = int(self.main_window.sidebar.p_position_input.text())
                led_a = int(self.main_window.channel_a_input.text())
                led_b = int(self.main_window.channel_b_input.text())
                led_c = int(self.main_window.channel_c_input.text())
                led_d = int(self.main_window.channel_d_input.text())
            except ValueError:
                from affilabs.widgets.message import show_message
                show_message("Invalid input values. Please enter numbers only.", "Error")
                return

            # Validate ranges (PWM 0-255, not degrees)
            if not (0 <= s_pos <= 255) or not (0 <= p_pos <= 255):
                from affilabs.widgets.message import show_message
                show_message("Polarizer positions must be between 0-255 PWM", "Error")
                return

            if not all(0 <= val <= 255 for val in [led_a, led_b, led_c, led_d]):
                from affilabs.widgets.message import show_message
                show_message("LED intensities must be between 0-255", "Error")
                return

            # Save to device config
            self.main_window.device_config.set_servo_positions(s_pos, p_pos)
            self.main_window.device_config.set_led_intensities(led_a, led_b, led_c, led_d)
            self.main_window.device_config.save()

            logger.info(f"✓ Settings saved: S={s_pos}, P={p_pos}, LEDs=[{led_a}, {led_b}, {led_c}, {led_d}]")
            from affilabs.widgets.message import show_message
            show_message("Settings saved to device configuration", "Information")

        except Exception as e:
            logger.error(f"Failed to apply settings: {e}")
            from affilabs.widgets.message import show_message
            show_message(f"Failed to apply settings:\n{e}", "Error")

    # ========================================================================
    # LICENSE & FEATURE MANAGEMENT
    # ========================================================================

    def show_license_dialog(self):
        """Open license management dialog."""
        from affilabs.widgets.license_dialog import LicenseDialog

        dialog = LicenseDialog(self.license_mgr, self.main_window)
        if dialog.exec():
            # License may have changed - reload
            self.features = self.license_mgr.load_license()
            logger.info(f"License reloaded: {self.features.tier_name} tier")

    def check_feature_access(self, feature_name: str, required_tier: str = None) -> bool:
        """
        Check if a feature is accessible with current license.
        Shows upgrade prompt if locked.

        Args:
            feature_name: Human-readable feature name
            required_tier: Required tier (pro/enterprise)

        Returns:
            bool: True if feature is accessible
        """
        # Determine required tier if not specified
        if required_tier is None:
            # Map feature names to tiers
            pro_features = ['animl_export', 'audit_trail', 'advanced_analytics']
            enterprise_features = ['sila_integration', 'lims_integration',
                                  'electronic_signatures', 'cfr_part11_compliance']

            feature_attr = feature_name.lower().replace(' ', '_').replace('-', '_')
            if feature_attr in pro_features:
                required_tier = 'pro'
            elif feature_attr in enterprise_features:
                required_tier = 'enterprise'
            else:
                return True  # Free feature

        # Check if feature is available
        feature_attr = feature_name.lower().replace(' ', '_').replace('-', '_')
        if hasattr(self.features, feature_attr):
            is_available = getattr(self.features, feature_attr)

            if not is_available:
                # Show upgrade prompt
                from affilabs.widgets.license_dialog import UpgradePromptDialog
                dialog = UpgradePromptDialog(feature_name, required_tier, self.main_window)
                dialog.exec()
                return False

            return True

        # Unknown feature - allow by default
        return True

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
    from affilabs.utils.splash_screen import create_splash_screen

    splash, splash_pixmap, update_splash_fn = create_splash_screen()
    splash.show()
    app.processEvents()

    # Store splash reference in app for updates
    app.splash_screen = splash
    app.update_splash_message = lambda msg: update_splash_fn(msg, app)

    # Schedule splash close after window is fully loaded
    def close_splash():
        """Close splash screen after deferred loading completes."""
        if hasattr(app, "splash_screen") and app.splash_screen.isVisible():
            app.update_splash_message("Ready!")
            QTimer.singleShot(300, lambda: app.splash_screen.finish(app.main_window))

    # Close splash after at least 3 seconds for branding visibility
    QTimer.singleShot(3000, close_splash)

    logger.info("Ready | Starting application")
    exit_code = app.exec()

    # Restore original stderr
    sys.stderr = original_stderr
    sys.stdout = original_stdout

    sys.exit(exit_code)


if __name__ == "__main__":
    main()

