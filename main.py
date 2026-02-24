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

# Suppress seabreeze USBTransportHandle.__del__ noise on Windows.
# libusb_reset() is not supported on Windows with WinUSB/libusb1 — safely ignorable.
def _unraisable_hook(unraisable):
    if unraisable.exc_type is NotImplementedError:
        obj_str = str(unraisable.object)
        if "seabreeze" in obj_str or "USBTransportHandle" in obj_str:
            return  # swallow
    sys.__unraisablehook__(unraisable)
sys.unraisablehook = _unraisable_hook

# Install stderr filter (unless verbose mode)
if not _env_flag("AFFILABS_VERBOSE_QT", default=False):
    sys.stderr = QtWarningFilter(sys.stderr)

# Note: stdout is NOT wrapped here to preserve sys.stdout.buffer for logger
# The logger's SafeWriter handles stdout filtering when needed

# Suppress Python warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", message="seabreeze.use has to be called")  # Suppress seabreeze warning

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
from PySide6.QtCore import Qt, QTimer, QtMsgType, Signal, qInstallMessageHandler, QSize
from PySide6.QtWidgets import QApplication

from affilabs.core.experiment_clock import ExperimentClock, TimeBase
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

    # Don't print remaining Qt messages to console - keep output clean
    # (Messages are still logged via Qt's internal mechanisms if needed)


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

# --- Feature Flag System ---
# Centralized configuration for optional/conditional features
_FEATURES = {
    'HAL': {'available': False, 'error': None},
    'COORDINATORS': {'available': False, 'error': None},
    'SPECTRUM_PROCESSING': {'available': False, 'error': None},
}

# --- Optional: Phase 1.4 Hardware Abstraction Layer (HAL) ---
try:
    from affilabs.hardware import (
        DeviceManager,
        IController,
        IServo,
        ISpectrometer,
        spectrometer_adapter,
    )

    _FEATURES['HAL']['available'] = True
    HAL_AVAILABLE = True
except ImportError as e:
    _FEATURES['HAL']['error'] = str(e)
    HAL_AVAILABLE = False
    _hal_import_error = str(e)

# --- Optional: Phase 1.3 UI Coordinators ---
try:
    from affilabs.coordinators.dialog_manager import DialogManager
    from affilabs.coordinators.ui_update_coordinator import AL_UIUpdateCoordinator

    _FEATURES['COORDINATORS']['available'] = True
    COORDINATORS_AVAILABLE = True
except ImportError as e:
    _FEATURES['COORDINATORS']['error'] = str(e)
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

# --- Mixins ---
from mixins import PumpMixin, FlagMixin, CalibrationMixin, CycleMixin, AcquisitionMixin

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





# ============================================================================
# SECTION 8: Application Class
# ============================================================================


class Application(PumpMixin, FlagMixin, CalibrationMixin, CycleMixin, AcquisitionMixin, QApplication):
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
        from affilabs.utils.resource_path import get_affilabs_resource
        icon_path = get_affilabs_resource("ui/img/affinite2.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Install Qt message handler to suppress harmless warnings
        qInstallMessageHandler(qt_message_handler)

        # Set global tooltip stylesheet (must be done early for all widgets)
        self.setStyleSheet("""
            QToolTip {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 10px 14px;
                font-size: 13px;
                font-weight: 500;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
        """)

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
            # Only log in detail for debug mode, otherwise keep it quiet
            logger.debug(f"[{phase}] {name}")
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

    def _get_current_user(self) -> str:
        """Get the current user name from the profile manager.

        Single source of truth for user identity. The sidebar user_combo
        syncs to the profile manager via signal, so no fallback is needed.

        Returns:
            Current user name, or empty string if unavailable.
        """
        if hasattr(self, 'user_profile_manager') and self.user_profile_manager:
            return self.user_profile_manager.get_current_user() or ""
        return ""

    def _validate_critical_imports(self):
        """Fail fast if critical modules are missing or broken.

        This prevents silent fallback to stub classes that cause
        hard-to-debug issues like "controller not found".

        Raises:
            SystemExit: If any critical import fails

        """
        logger.debug("Validating imports...")

        failures = []

        # Validate controller classes
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
            logger.warning(f"⚠ UI Coordinators not available: {globals().get('_coordinators_import_error', 'unknown error')}")

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

        # Experiment tracking — ExperimentClock is the single source of truth for time
        self.clock = ExperimentClock()
        self._last_cycle_bounds = None
        self._session_cycles_dir = None
        self._session_epoch = 0  # Increments on clear to invalidate old data
        self.current_experiment_folder = None  # Path to active experiment folder (GLP/GMP structure)

        # Calibration state
        self._calibration_retry_count = 0
        self._max_calibration_retries = MAX_CALIBRATION_RETRIES
        self._calibration_completed = False
        self._qc_dialog = None

        # Channel selection
        self._selected_channel = None
        self._reference_channel = None
        self._ref_subtraction_enabled = False
        self._ref_channel = None
        self._selected_flag_channel = 'a'  # Default channel for flag placement (used by UI)

        # Channel time shifts for injection alignment
        self._channel_time_shifts = {'a': 0.0, 'b': 0.0, 'c': 0.0, 'd': 0.0}

        # Data filtering
        self._filter_enabled = DEFAULT_FILTER_ENABLED
        self._filter_strength = DEFAULT_FILTER_STRENGTH
        self._filter_method = DEFAULT_FILTER_METHOD
        self._kalman_filters = {}

        # EMA live display filtering
        self._ema_state = {"a": None, "b": None, "c": None, "d": None}
        self._display_filter_method = "none"  # 'none', 'ema_light', 'ema_smooth'
        self._display_filter_alpha = 0.0  # Will be set based on selection



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

        # Next cycle warning line for active cycle graph
        self._next_cycle_warning_line = None

        # Contact time marker for manual injection cycles
        self._contact_time_marker = None  # Vertical line showing when to wash/regen
        self._injection_completion_time = None  # Sensorgram time when injection completed

        # Live binding stats: keyed by (cycle_num, channel) — populated by _place_injection_flag
        self._injection_stats: dict = {}

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
        # User profile manager (must be before RecordingManager)
        from affilabs.services.user_profile_manager import UserProfileManager
        self.user_profile_manager = UserProfileManager()
        logger.debug("✓ UserProfileManager (centralized)")

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
        self.recording_mgr = RecordingManager(self.data_mgr, self.buffer_mgr, user_manager=self.user_profile_manager)
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

        self.pump_mgr = PumpManager(self.hardware_mgr)
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
        logger.debug(f"✓ License: {license_info['tier_name']} tier")
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

        logger.debug(
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
            # Share centralized user profile manager with sidebar
            self.main_window.sidebar.user_profile_manager = self.user_profile_manager

        # Wire up elapsed time getter for pause markers + footer clocks
        def get_elapsed_time():
            if not self.clock.experiment_started:
                return None
            return self.clock.raw_elapsed_now()

        def get_recording_elapsed():
            """Seconds since recording started (wall-clock), or None if not recording."""
            import time as _time
            wall = getattr(self, '_recording_start_wall', None)
            if wall is None:
                return None
            return max(0.0, _time.time() - wall)

        self.main_window._get_elapsed_time = get_elapsed_time
        self.main_window._get_recording_elapsed = get_recording_elapsed

        # Store app reference for CalibrationManager to access calibration methods
        self.main_window.app = self
        # All UI→App communication happens through Qt signals

        # Set default export path in sidebar (user-specific)
        if hasattr(self.main_window, 'sidebar') and (w := self._sidebar_widget('export_dest_input')):
            # Use user-specific directory: Documents/Affilabs Data/<username>/SPR_data/
            current_user = self._get_current_user()
            if current_user:
                default_path = str(Path.home() / "Documents" / "Affilabs Data" / current_user / "SPR_data")
            else:
                default_path = str(self.recording_mgr.output_directory)
            Path(default_path).mkdir(parents=True, exist_ok=True)
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

        # Injection coordinator (handles manual and automated injections)
        from affilabs.coordinators.injection_coordinator import InjectionCoordinator

        self.injection_coordinator = InjectionCoordinator(
            self.hardware_mgr,
            self.pump_mgr,
            buffer_mgr=self.buffer_mgr,
            parent=self.main_window,
        )
        logger.debug("✓ InjectionCoordinator")

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

        # Guidance coordinator — adaptive hints based on user experience level (Phase 6)
        try:
            from affilabs.coordinators.guidance_coordinator import GuidanceCoordinator
            self.guidance_coordinator = GuidanceCoordinator(self)
            logger.debug("✓ GuidanceCoordinator")
        except Exception as _gc_err:
            logger.warning(f"GuidanceCoordinator not loaded: {_gc_err}")
            self.guidance_coordinator = None

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
            from affilabs.services import SpectrumProcessor

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
            from affilabs.services import CalibrationValidator

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

        # Connect hardware, data, calibration, recording & kinetic manager signals
        self._connect_hardware_and_manager_signals()

        # Connect signals organized by subsystem (Phase 4 refactoring)
        self._connect_viewmodel_signals()
        self._connect_manager_signals()
        self._connect_ui_event_signals()

        logger.debug("✓ All signals connected")

    def _show_user_selector_if_needed(self) -> None:
        """Show a compact user-selector / greeting modal on startup.

        Always shown so the user can confirm who is running the session.
        When only one profile exists the combo is pre-selected and acts
        purely as a greeting; when multiple exist the user picks from the list.
        """
        try:
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import (
                QComboBox,
                QDialog,
                QLabel,
                QPushButton,
                QVBoxLayout,
            )

            um = self.user_profile_manager
            profiles = um.get_profiles()
            current_user = um.get_current_user() or (profiles[0] if profiles else "")

            dlg = QDialog(self.main_window)
            dlg.setWindowTitle("Affilabs.core")
            dlg.setWindowFlags(
                Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
            )
            dlg.setFixedWidth(320)
            dlg.setStyleSheet(
                "QDialog {"
                "  background: #FFFFFF;"
                "  border: 1px solid #D1D1D6;"
                "  border-radius: 12px;"
                "}"
            )

            layout = QVBoxLayout(dlg)
            layout.setContentsMargins(24, 20, 24, 20)
            layout.setSpacing(12)

            # Greeting headline — updates live when combo selection changes
            def _greeting_text(name: str) -> str:
                if name.lower() in ("default", "default user", "", "+ new profile (rename later)"):
                    return "👋 Welcome to Affilabs.core!"
                return f"👋 Hello, {name}!"

            lbl = QLabel(_greeting_text(current_user))
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #1D1D1F;")
            layout.addWidget(lbl)

            sub = QLabel("Who's running today's experiment?")
            sub.setWordWrap(True)
            sub.setStyleSheet("font-size: 12px; color: #8E8E93;")
            layout.addWidget(sub)

            combo = QComboBox()
            combo.addItems(profiles)
            combo.addItem("+ New profile (rename later)")
            current_idx = combo.findText(current_user)
            if current_idx >= 0:
                combo.setCurrentIndex(current_idx)
            combo.setFixedHeight(36)
            combo.setStyleSheet(
                "QComboBox {"
                "  background: #F5F5F7; border: 1px solid #D1D1D6;"
                "  border-radius: 8px; padding: 4px 10px;"
                "  font-size: 13px; color: #1D1D1F;"
                "}"
                "QComboBox::drop-down { border: none; }"
                "QComboBox QAbstractItemView {"
                "  background: #FFFFFF; color: #1D1D1F;"
                "  selection-background-color: #E5E5EA;"
                "}"
            )
            # Update greeting label when selection changes
            combo.currentTextChanged.connect(lambda name: lbl.setText(_greeting_text(name)))
            layout.addWidget(combo)

            hint = QLabel(
                "Press <b>Power</b> when you're ready to connect,\n"
                "or ask <b>Sparq</b> to set up a method first — no hardware needed."
            )
            hint.setWordWrap(True)
            hint.setStyleSheet(
                "font-size: 11px; color: #8E8E93; line-height: 1.4;"
            )
            layout.addWidget(hint)

            btn = QPushButton("Start")
            btn.setFixedHeight(40)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton {"
                "  background: #2E30E3; color: white; border: none;"
                "  border-radius: 8px; font-size: 14px; font-weight: 600;"
                "}"
                "QPushButton:hover { background: #1E20C3; }"
            )
            btn.clicked.connect(dlg.accept)
            layout.addWidget(btn)

            dlg.exec()

            selected = combo.currentText()
            if selected == "+ New profile (rename later)":
                base = "New User"
                candidate = base
                n = 2
                while candidate in profiles:
                    candidate = f"{base} {n}"
                    n += 1
                um.add_user(candidate)
                um.set_current_user(candidate)
            elif selected and selected != um.get_current_user():
                um.set_current_user(selected)
                # GuidanceCoordinator._on_user_changed fires automatically via callback
        except Exception as _sel_err:
            logger.warning(f"User selector skipped: {_sel_err}")

    def _show_user_greeting(self, username: str) -> None:
        """No-op: greeting is now shown inside the user selector dialog."""
        pass

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

        # Defer window visibility until after deferred widgets are loaded
        # This ensures the window is fully loaded before displaying to user
        logger.debug("Preparing main window (deferring visibility)...")
        if hasattr(self, "update_splash_message"):
            self.update_splash_message("Loading interface components...")

        # Load deferred widgets FIRST, then show window
        QTimer.singleShot(0, self._load_deferred_then_show)

        # DO NOT auto-connect hardware - user must press Power button
        logger.info("Ready - waiting for user to press Power button...")

    def _load_deferred_then_show(self):
        """Load deferred widgets, then show the main window when fully ready.

        This ensures the window is only displayed after all components are
        initialized, providing a cleaner startup experience.
        """
        try:
            # Load all deferred widgets first
            self._load_deferred_widgets()

            # Now show the window for the first time (fully loaded)
            logger.debug("Showing fully-loaded main window...")
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()
            QApplication.processEvents()  # Force immediate render
            logger.debug(f"Window visible: {self.main_window.isVisible()}")

        except Exception as e:
            logger.error(f"Error during deferred loading or window show: {e}", exc_info=True)
            # Fallback: show window anyway so app is responsive
            try:
                self.main_window.show()
            except Exception:
                pass

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

        # Note: Tooltip styling is applied at QApplication level during __init__
        logger.debug("✓ Theme applied (tooltip styling applied at app level)")

        # Register emergency cleanup handler for unexpected exits
        atexit.register(self._emergency_cleanup)

    def _connect_hardware_and_manager_signals(self):
        """Connect hardware, data, calibration, recording & kinetic manager signals.

        These are cross-thread connections (QueuedConnection) for thread safety
        since managers run in worker threads.
        """
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
        self.calibration.calibration_failed.connect(
            self._on_calibration_failed,
            Qt.QueuedConnection,
        )
        logger.debug("✓ calibration.calibration_failed signal")

        # === RECORDING MANAGER SIGNALS ===
        self.recording_mgr.recording_started.connect(self._on_recording_started)
        self.recording_mgr.recording_stopped.connect(self._on_recording_stopped)
        self.recording_mgr.recording_error.connect(self._on_recording_error)
        self.recording_mgr.event_logged.connect(self._on_event_logged)
        if hasattr(self, 'notes_tab'):
            self.recording_mgr.recording_started.connect(
                self.notes_tab.on_recording_started, Qt.QueuedConnection
            )
            self.recording_mgr.recording_stopped.connect(
                self.notes_tab.on_recording_stopped, Qt.QueuedConnection
            )

        # === GUIDANCE COORDINATOR SIGNALS (Phase 6) ===
        if getattr(self, 'guidance_coordinator', None):
            _gc = self.guidance_coordinator
            self.hardware_mgr.hardware_connected.connect(
                _gc.on_hardware_connected, Qt.QueuedConnection
            )
            self.calibration.calibration_complete.connect(
                _gc.on_calibration_complete, Qt.QueuedConnection
            )
            self.data_mgr.acquisition_started.connect(
                _gc.on_acquisition_started, Qt.QueuedConnection
            )
            self.recording_mgr.recording_started.connect(
                _gc.on_recording_started, Qt.QueuedConnection
            )
            if hasattr(self, 'injection_coordinator') and self.injection_coordinator:
                self.injection_coordinator.injection_flag_requested.connect(
                    _gc.on_injection_flag, Qt.QueuedConnection
                )
            logger.debug("✓ GuidanceCoordinator signals wired")

        # === KINETIC MANAGER SIGNALS ===
        self.kinetic_mgr.pump_initialized.connect(self._on_pump_initialized)
        self.kinetic_mgr.pump_error.connect(self._on_pump_error)
        self.kinetic_mgr.pump_state_changed.connect(self._on_pump_state_changed)
        self.kinetic_mgr.valve_switched.connect(self._on_valve_switched)





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

        logger.debug("Connected: main_window UI action signals")

        # === TAB SHORTCUTS ===
        from PySide6.QtGui import QKeySequence, QShortcut
        _nav = self.main_window.navigation_presenter
        _sc1 = QShortcut(QKeySequence("Ctrl+1"), self.main_window)
        _sc1.activated.connect(lambda: _nav.switch_page(0))
        _sc2 = QShortcut(QKeySequence("Ctrl+2"), self.main_window)
        _sc2.activated.connect(lambda: _nav.switch_page(1))
        _sc3 = QShortcut(QKeySequence("Ctrl+3"), self.main_window)
        _sc3.activated.connect(lambda: _nav.switch_page(2))

        # === DEBUG SHORTCUTS ===
        # logger.info(f"[OK] Ctrl+Shift+C registered: {bypass_calibration_shortcut}")

        # Ctrl+Shift+S: Start simulation mode (inject fake spectra)
        simulation_shortcut = QShortcut(QKeySequence("Ctrl+Shift+S"), self.main_window)
        simulation_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        simulation_shortcut.activated.connect(self.debug.start_simulation)

        # Ctrl+Shift+1: Single data point test (minimal test)
        single_point_shortcut = QShortcut(
            QKeySequence("Ctrl+Shift+1"),
            self.main_window,
        )
        single_point_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        single_point_shortcut.activated.connect(self.debug.send_single_data_point)

        # Ctrl+Shift+D / F9: Load demo sensorgram data for screenshots
        for _demo_key in ("Ctrl+Shift+D", "F9"):
            _sc = QShortcut(QKeySequence(_demo_key), self.main_window)
            _sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
            _sc.activated.connect(self._load_demo_data)
        logger.info("[Demo] Ctrl+Shift+D / F9 shortcut registered")

        self.main_window.acquisition_pause_requested.connect(
            self._on_acquisition_pause_requested,
        )
        self.main_window.export_requested.connect(self._on_export_requested)

        # === UI CONTROL SIGNALS (direct connections - not through event bus) ===
        self._connect_ui_control_signals()

    def _connect_ui_control_signals(self):
        """Register UI control element signal connections.

        These are direct connections (not routed through event bus) for
        performance-critical UI controls like graph cursors and manual inputs.
        """
        ui = self.main_window

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

        # OEM Calibration button (direct connection)
        ui.oem_led_calibration_btn.clicked.connect(self._on_oem_led_calibration)

        # LED Model Training button (direct connection)
        ui.led_model_training_btn.clicked.connect(self._on_led_model_training)

        # Baseline Capture button (REBUILT - direct connection, no lambda)
        if hasattr(ui, "baseline_capture_btn"):
            # Disconnect any existing connections first
            try:
                ui.baseline_capture_btn.clicked.disconnect()
            except:
                pass

            # Connect to handler
            ui.baseline_capture_btn.clicked.connect(self._on_record_baseline_clicked)
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
        # NOTE: Already connected in _connect_hardware_and_manager_signals()
        # (merged with _on_calibration_complete to avoid duplicate QC dialogs)

        # === PUMP MANAGER STATUS SIGNALS ===
        if self.pump_mgr:
            self.pump_mgr.operation_started.connect(self._on_pump_operation_started)
            self.pump_mgr.operation_progress.connect(self._on_pump_operation_progress)
            self.pump_mgr.operation_completed.connect(self._on_pump_operation_completed)
            self.pump_mgr.status_updated.connect(self._on_pump_status_updated)
            logger.debug("✓ PumpManager signals connected")

        # === INJECTION COORDINATOR SIGNALS ===
        if hasattr(self, 'injection_coordinator') and self.injection_coordinator:
            self.injection_coordinator.injection_completed.connect(self._show_contact_time_marker)
            self.injection_coordinator.injection_flag_requested.connect(self._place_injection_flag)
            self.injection_coordinator.injection_cancelled.connect(self._on_injection_cancelled)

            logger.debug("✓ InjectionCoordinator signals connected")

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

            logger.debug(f"Display filter: {config['label']}")
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


    def _set_start_button_to_stop_mode(self):
        """Change Start Run button to Stop Run mode (red, cancels execution)."""
        if btn := self._sidebar_widget('start_queue_btn'):
            btn.setText("Stop Run")
            btn.setToolTip("Stop the running cycle queue")

            # Set stop icon (SVG)
            try:
                from PySide6.QtGui import QIcon, QPixmap, QPainter
                from PySide6.QtSvg import QSvgRenderer
                svg = '''<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                    <rect x="6" y="6" width="12" height="12" fill="white" rx="2"/>
                </svg>'''
                svg_renderer = QSvgRenderer(svg.encode('utf-8'))
                pixmap = QPixmap(18, 18)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                svg_renderer.render(painter)
                painter.end()
                btn.setIcon(QIcon(pixmap))
                btn.setIconSize(QSize(16, 16))
            except Exception as e:
                logger.warning(f"Failed to set stop icon: {e}")

            btn.setStyleSheet(
                "QPushButton {"
                "  background: #FF3B30;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 6px;"
                "  padding: 6px 16px;"
                "  font-size: 12px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover { background: #E02020; }"
                "QPushButton:pressed { background: #C01010; }"
            )
            # Store state so click handler knows what to do
            btn.setProperty("mode", "stop")
            logger.debug("✓ Start button changed to Stop mode (red)")

    def _set_start_button_to_start_mode(self):
        """Change Stop Run button back to Start Run mode (green, starts execution)."""
        if btn := self._sidebar_widget('start_queue_btn'):
            btn.setText("Start Run")
            btn.setToolTip("Start executing the queued cycles")

            # Set play icon (SVG)
            try:
                from PySide6.QtGui import QIcon, QPixmap, QPainter
                from PySide6.QtSvg import QSvgRenderer
                svg = '''<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                    <path d="M8 5v14l11-7z" fill="white"/>
                </svg>'''
                svg_renderer = QSvgRenderer(svg.encode('utf-8'))
                pixmap = QPixmap(18, 18)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                svg_renderer.render(painter)
                painter.end()
                btn.setIcon(QIcon(pixmap))
                btn.setIconSize(QSize(16, 16))
            except Exception as e:
                logger.warning(f"Failed to set play icon: {e}")

            btn.setStyleSheet(
                "QPushButton {"
                "  background: #34C759;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 6px;"
                "  padding: 6px 16px;"
                "  font-size: 12px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover { background: #30B350; }"
                "QPushButton:pressed { background: #2A9D46; }"
                "QPushButton:disabled { background: #C7C7CC; }"
            )
            btn.setEnabled(True)
            # Store state so click handler knows what to do
            btn.setProperty("mode", "start")
            logger.debug("✓ Stop button changed back to Start mode (green)")

    def _on_start_button_clicked(self):
        """Start the next cycle from queue or auto-read mode."""
        import time

        logger.info("▶ Start Cycle button clicked")

        # Clear any legacy cycle markers from previous runs
        self._clear_all_cycle_markers()

        # If no cycles in queue, start auto-read mode
        if self.queue_presenter.get_queue_size() == 0:
            logger.info("No cycles in queue - starting auto-read mode")
            if not self.data_mgr._acquiring:
                self.acquisition_events.on_start_button_clicked()
            return

        # Snapshot the full method on first cycle start (for progress tracking)
        if self.queue_presenter.get_method_progress() == 0:
            self.queue_presenter.snapshot_method()

        # Lock queue during execution (prevents edits)
        self.queue_presenter.lock_queue()

        # Get the next cycle to run WITHOUT removing it from queue
        # Use method snapshot + progress counter instead of popping
        original_method = self.queue_presenter.get_original_method()
        progress = self.queue_presenter.get_method_progress()
        
        if progress >= len(original_method):
            logger.error("❌ No more cycles to run (progress >= method length)")
            self.queue_presenter.unlock_queue()
            return
            
        cycle = original_method[progress]  # Get cycle at current progress index
        
        if cycle is None:
            logger.error("❌ Failed to get cycle from method snapshot")
            self.queue_presenter.unlock_queue()
            return

        # Sync backward compatibility list
        self.segment_queue = self.queue_presenter.get_remaining_from_method()

        cycle_type = cycle.type
        duration_min = cycle.length_minutes

        # Calculate cycle numbers
        cycle_num = len(self._completed_cycles) + 1
        total_cycles = cycle_num + self.queue_presenter.get_queue_size()

        logger.info(f"Starting Cycle {cycle_num}/{total_cycles}: {cycle_type}, {duration_min} min")

        # Log cycle start event for blue marker on sensorgram
        if self.recording_mgr.is_recording:
            event_name = f"Cycle Start: {cycle_type}"
            if cycle.note and cycle.note != 'No notes':
                event_name += f" - {cycle.note}"
            self.recording_mgr.log_event(event_name)
            logger.debug(f"✓ Logged cycle start event: {event_name}")

        # Start acquisition if not already running
        if not self.data_mgr._acquiring:
            logger.info("Starting data acquisition...")
            self.acquisition_events.on_start_button_clicked()

        # Initialize cycle tracking using Cycle.start() method
        self._current_cycle = cycle
        # Get sensorgram start time from live buffer (RAW_ELAPSED coords).
        # clock.raw_elapsed_now() may return 0 if start_experiment() hasn't fired yet,
        # so read the latest raw timestamp directly from the buffer as a reliable source.
        _cycle_start_raw = self.clock.raw_elapsed_now()
        if _cycle_start_raw == 0.0:
            try:
                for _ch in ['a', 'b', 'c', 'd']:
                    _buf = getattr(self.buffer_mgr, 'timeline_data', {}).get(_ch)
                    if _buf is not None and hasattr(_buf, 'time') and len(_buf.time) > 0:
                        _cycle_start_raw = max(_cycle_start_raw, float(_buf.time[-1]))
            except Exception:
                pass
        self._current_cycle.start(
            cycle_num=cycle_num,
            total_cycles=total_cycles,
            sensorgram_time=_cycle_start_raw  # RAW_ELAPSED
        )
        self._cycle_end_time = time.time() + (duration_min * 60)
        logger.info(f"✓ Cycle initialized: {cycle_type}, end_time set to {self._cycle_end_time}")
        logger.debug(f"   cycle_num={cycle_num}, total={total_cycles}, duration={duration_min}min")

        # Emit CycleMarker START to timeline stream (non-critical)
        if self.recording_mgr.is_recording:
            try:
                from datetime import datetime as _dt_cls
                from affilabs.domain.timeline import CycleMarker, EventContext
                _tl_stream = self.recording_mgr.get_timeline_stream()
                _tl_stream.add_event(CycleMarker(
                    time=_cycle_start_raw,
                    channel='A',
                    context=EventContext.LIVE,
                    created_at=_dt_cls.now(),
                    cycle_id=str(cycle.cycle_id),
                    cycle_type=cycle.type,
                    is_start=True,
                    duration=duration_min * 60.0,
                ))
                logger.debug(f"✓ CycleMarker START emitted: {cycle.type}")
            except Exception as _exc:
                logger.warning(f"Timeline CycleMarker START failed (non-critical): {_exc}")

        # Highlight the running cycle in the queue table
        if tbl := self._sidebar_widget('summary_table'):
            tbl.set_running_cycle(cycle.cycle_id)
            logger.debug(f"✓ Queue table highlighting cycle #{cycle_num} (ID: {cycle.cycle_id})")

        # Update status bar operation status
        if hasattr(self.main_window, 'update_status_operation'):
            duration_str = f"{int(duration_min):02d}:{int((duration_min % 1) * 60):02d}"
            notes = getattr(cycle, 'note', '') or ''
            self.main_window.update_status_operation(f"Running: {cycle_type} ({duration_str})", notes=notes)

        # Sync note button state with the cycle's existing note (if any) and show button
        if hasattr(self.main_window, '_update_cycle_note_button'):
            self.main_window._update_cycle_note_button(bool(getattr(cycle, 'note', '')), visible=True)

        # Schedule auto-completion when cycle duration expires
        duration_ms = int(duration_min * 60 * 1000)
        self._cycle_end_timer.start(duration_ms)
        logger.debug(f"Cycle end timer scheduled: {duration_min} min ({duration_ms} ms)")

        # Pause the 5s intelligence refresh timer to avoid overwriting cycle countdown
        if hasattr(self.main_window, 'intelligence_refresh_timer'):
            self.main_window.intelligence_refresh_timer.stop()

        # Start the 1-second update timer for intelligence bar and overlay
        if hasattr(self, '_cycle_timer'):
            self._cycle_timer.start(1000)  # Update every 1 second
            logger.debug("Cycle display timer started (updates every 1 second)")
            logger.debug(f"   _cycle_timer isActive: {self._cycle_timer.isActive()}, interval: {self._cycle_timer.interval()}ms")
        else:
            logger.error("❌ _cycle_timer does not exist - cycle display will not update!")

        # Start the progress bar to track cycle progress during live data acquisition
        # Directly show and configure progress bar without affecting injection buttons
        try:
            from affilabs.widgets.datawindow import DataWindow
            for widget in self.main_window.findChildren(DataWindow):
                if hasattr(widget, 'ui') and hasattr(widget.ui, 'progress_bar'):
                    # Set maximum to duration in milliseconds (matches increment of 100 every 100ms)
                    widget.ui.progress_bar.setMaximum(duration_ms)
                    widget.ui.progress_bar.setValue(0)
                    widget.ui.progress_bar.show()
                    logger.info(f"✓ Progress bar started for {cycle_type} ({duration_min} min)")
                    break
        except Exception as e:
            logger.warning(f"⚠️ Could not start progress bar: {e}")

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

        # Schedule injection if cycle requires it AND pump is available OR manual mode enabled
        if cycle.injection_method is not None:
            is_manual_mode = self.hardware_mgr.requires_manual_injection
            if has_pump or has_internal or is_manual_mode:
                self._schedule_injection(cycle)
            else:
                logger.warning(f"⚠️ Cycle requires {cycle.injection_method} injection but no pump or manual mode available — skipping injection")

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

        # Change Start Run button to Stop Run during cycle execution
        self._set_start_button_to_stop_mode()

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

        # Add blue vertical marker on Full Sensorgram at cycle start
        try:
            if hasattr(self.main_window, 'full_timeline_graph'):
                import pyqtgraph as pg
                timeline = self.main_window.full_timeline_graph
                marker_pos = timeline.stop_cursor.value() if hasattr(timeline, 'stop_cursor') else self.clock.raw_elapsed_now() - self.clock.display_offset
                cycle_abbr = {
                    "Baseline": "BL", "Binding": "Bind.", "Kinetic": "Kin.",
                    "Concentration": "Bind.", "Immobilization": "Immob.",
                    "Regeneration": "Regen.", "Wash": "Wash",
                }.get(cycle.type, cycle.type[:5])
                line = pg.InfiniteLine(
                    pos=marker_pos, angle=90,
                    pen=pg.mkPen(color='#0A84FF', width=2),
                    movable=False,
                    label=cycle_abbr,
                    labelOpts={'position': 0.92, 'color': '#0A84FF',
                               'fill': (255, 255, 255, 180), 'movable': False}
                )
                timeline.addItem(line)
                self._cycle_markers[cycle.cycle_id] = {'line': line}
                logger.debug(f"✓ Cycle marker added at t={marker_pos:.1f}s ({cycle_abbr})")
        except Exception as e:
            logger.debug(f"Could not add cycle marker: {e}")

    # === Channel Time Shift (Arrow Keys) ===

    def _select_nearest_channel(self, click_time: float, click_value: float):
        """Select the channel whose curve is nearest to the click position."""
        pass  # graph_events removed


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

        # Notify UI coordinator so pill channel-letter colors match active palette
        if hasattr(self, 'ui_updates') and self.ui_updates is not None:
            self.ui_updates.set_colorblind_mode(checked)

        logger.info("[OK] Graph colors updated successfully")


    def _on_power_on_requested(self):
        """User requested to power on (connect hardware)."""
        try:
            logger.debug("Searching for hardware...")

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
        logger.info("Power OFF requested - initiating graceful shutdown...")

        try:
            # Cancel any running cycle first (stops timers, unlocks queue)
            self._cancel_active_cycle()

            # Stop data acquisition (prevents new data from coming in)
            if self.data_mgr:
                logger.debug("Stopping data acquisition...")
                try:
                    self.data_mgr.stop_acquisition()
                    logger.debug("Data acquisition stopped")
                except Exception as e:
                    logger.error(f"Error stopping data acquisition: {e}")

            # Stop recording if active (ensures data is saved)
            if self.recording_mgr and self.recording_mgr.is_recording:
                logger.debug("Stopping active recording...")
                try:
                    self.recording_mgr.stop_recording()
                    logger.debug("Recording stopped and saved")
                except Exception as e:
                    logger.error(f"Error stopping recording: {e}")

            # Disconnect all hardware (safe shutdown of devices)
            logger.debug("Disconnecting hardware...")
            try:
                self._intentional_disconnect = (
                    True  # Mark as intentional before disconnect
                )
                self.hardware_mgr.disconnect_all()
                logger.debug("Hardware disconnected safely")
            except Exception as e:
                logger.error(f"Error disconnecting hardware: {e}")

            # Reset application state (fresh state for next power on)
            logger.debug("Resetting application state...")
            try:
                # Reset connection and calibration flags
                self._device_config_initialized = False
                self._initial_connection_done = False
                self._calibration_completed = False

                # Clear data buffers
                if hasattr(self, 'buffer_mgr') and self.buffer_mgr:
                    self.buffer_mgr.clear_all()
                    logger.debug("Data buffers cleared")

                # Reset data manager calibration state
                if self.data_mgr:
                    self.data_mgr.calibrated = False
                    logger.debug("Data manager calibration flag reset")

                # Reset experiment timing
                self.clock.reset()
                logger.debug("Experiment timing reset")

                logger.debug("Application state reset complete")
            except Exception as e:
                logger.error(f"Error resetting application state: {e}")

            # Update UI to disconnected state
            self.main_window.set_power_state("disconnected")

            logger.debug(
                "Graceful shutdown complete - software ready for next power cycle",
            )

        except Exception as e:
            logger.error(f"Error during power off: {e}")
            # Still update UI even if errors occurred
            self.main_window.set_power_state("disconnected")
            from affilabs.widgets.message import show_message

            show_message(f"Power off completed with errors: {e}", "Warning")




    def _update_device_status_ui(self, status: dict):
        """Update Device Status UI with hardware information.

        Args:
            status: Hardware status dict from HardwareManager

        """


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

    # === HARDWARE MANAGER SIGNAL HANDLERS ===

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
            logger.error("=" * 60)
            logger.error("CRITICAL: HARDWARE DISCONNECTED")
            logger.error("=" * 60)

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
                "• USB cable connections<br>"
                "• USB port stability<br>"
                "• Device power<br><br>"
                "Click 'Scan' to reconnect devices.",
            )

    def _start_led_status_monitoring(self):
        """Start periodic LED status monitoring timer (V1.1+ firmware)."""
        self.hardware_events.start_led_status_monitoring()

    def _stop_led_status_monitoring(self):
        """Stop LED status monitoring timer."""
        self.hardware_events.stop_led_status_monitoring()

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
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1000, self._run_servo_auto_calibration)

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

        # Store pipeline QC metrics (fwhm, dip depth) from adaptive pipeline metadata
        if not hasattr(self, '_latest_iq_metrics'):
            self._latest_iq_metrics = {}
        self._latest_iq_metrics[channel] = {
            'fwhm': metadata.get('fwhm') if metadata else None,
            'dip_depth': metadata.get('depth') if metadata else None,
        }

        # ── Baseline stability rolling buffer ─────────────────────────────────
        # Keep the last 30 peak values per channel (~30 s at ~1 Hz effective).
        # When ALL active channels have p2p < 0.15 nm for their full window,
        # flag as STABLE → show green "Ready to inject ✓" badge.
        _STABILITY_WINDOW = 30   # samples
        _STABLE_P2P_NM   = 0.15  # nm threshold for "flat enough"
        _STABLE_MIN_PTS  = 20    # must have at least this many points before judging

        if not hasattr(self, '_peak_history'):
            self._peak_history = {"a": [], "b": [], "c": [], "d": []}

        buf = self._peak_history[channel]
        buf.append(peak_wavelength)
        if len(buf) > _STABILITY_WINDOW:
            buf.pop(0)

        # Re-evaluate stability across active channels and push badge update
        try:
            active = [
                ch for ch in ("a", "b", "c", "d")
                if hasattr(self, 'main_window')
                and hasattr(self.main_window, 'channel_toggles')
                and self.main_window.channel_toggles.get(ch.upper(), None) is not None
                and self.main_window.channel_toggles[ch.upper()].isChecked()
                and self._latest_peaks.get(ch) is not None
            ]
            if not active:
                stable = False
            else:
                stable = all(
                    len(self._peak_history.get(ch, [])) >= _STABLE_MIN_PTS
                    and (max(self._peak_history[ch]) - min(self._peak_history[ch])) <= _STABLE_P2P_NM
                    for ch in active
                )
            if hasattr(self, 'ui_updates') and self.ui_updates is not None:
                self.ui_updates.queue_stability_update(stable)
        except Exception:
            pass

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
        logger.debug("[CalibrationViewModel] Calibration started")
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
        # Future: Display success message, enable acquisition
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



    def _load_demo_data(self):
        """Ctrl+Shift+D: Generate kinetics_demo.xlsx, load into Edits, fill live graphs."""
        logger.info("[Demo] Ctrl+Shift+D triggered")
        self.main_window._suppress_load_dialog = True
        try:
            from affilabs.utils.demo_data_generator import load_demo_data_into_app
            load_demo_data_into_app(self)
        except Exception as _e:
            logger.error(f"[Demo] load_demo_data_into_app failed: {_e}", exc_info=True)
        finally:
            self.main_window._suppress_load_dialog = False

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

    # === APPLICATION LIFECYCLE / CLEANUP ===

    def _cleanup_resources(self, emergency: bool = False):
        """Consolidated cleanup logic for all shutdown paths."""
        from affilabs.utils.resource_helpers import ResourceHelpers
        ResourceHelpers.cleanup_resources(self, emergency)

    def close(self):
        """Clean up resources on application close."""
        if self.closing:
            return True  # Already closing, prevent double cleanup

        self.closing = True
        logger.info("Closing application...")
        self._cleanup_resources(emergency=False)
        result = super().close()
        # Ensure the Qt event loop exits after all timers are stopped.
        from PySide6.QtWidgets import QApplication
        QApplication.quit()
        return result

    def _emergency_cleanup(self):
        """Emergency cleanup for unexpected exits (called by atexit)."""
        if hasattr(self, "closing") and self.closing:
            return  # Normal close already happened

        if hasattr(self, "_intentional_disconnect") and self._intentional_disconnect:
            return  # Intentional disconnect, not an emergency

        logger.warning("Emergency cleanup triggered - forcing resource release")
        self._cleanup_resources(emergency=True)

    def __del__(self):
        """Destructor to ensure resources are cleaned up."""
        try:
            if not hasattr(self, "closing") or not self.closing:
                logger.warning("__del__ called without proper close - forcing cleanup")
                self._cleanup_resources(emergency=True)
        except Exception:
            pass  # Destructor should never raise


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
    logger.debug("Global exception hook installed")

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
    logger.info(f"AffiLabs.core {SW_VERSION.split()[1]} | {dtnow.strftime('%Y-%m-%d %H:%M')}")
    logger.info("Initializing...")

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
            def _after_splash():
                app.splash_screen.finish(app.main_window)
                # Phase 6: user selector shown immediately after splash dismisses
                app._show_user_selector_if_needed()
            QTimer.singleShot(300, _after_splash)

    # Close splash after at least 3 seconds for branding visibility
    QTimer.singleShot(3000, close_splash)

    logger.info("Ready | Starting application")
    exit_code = app.exec()

    # Restore original stderr
    sys.stderr = original_stderr
    sys.stdout = original_stdout

    # Force process exit — oceandirect/pyserial SDK threads are non-daemon and
    # will keep the process alive indefinitely after app.exec() returns.
    # All hardware cleanup already ran in close() → _cleanup_resources().
    os._exit(exit_code)


if __name__ == "__main__":
    main()

