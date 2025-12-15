"""Application state management with grouped data classes.

This module defines the centralized state structure for the Affilabs Core application.
Instead of scattering 50+ instance variables across the Application class,
state is organized into logical groups using dataclasses.

Architecture Benefits:
- Clear separation of concerns (lifecycle, experiment, calibration, etc.)
- Type hints for better IDE support and validation
- Easy to serialize/deserialize for state persistence
- Explicit initialization (no scattered self.x = None declarations)
- Testable (can create mock states easily)

Usage:
    app_state = ApplicationState()
    app_state.lifecycle.closing = True
    app_state.experiment.start_time = monotonic()
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from queue import Queue

# Import constants
try:
    from config import (
        DEFAULT_AXIS,
        DEFAULT_FILTER_ENABLED,
        DEFAULT_FILTER_STRENGTH,
        DEFAULT_FILTER_METHOD,
        CHANNEL_INDICES,
        CHANNELS,
        MAX_CALIBRATION_RETRIES,
        SPECTRUM_QUEUE_SIZE,
    )
except ImportError:
    # Fallback defaults if config not available
    DEFAULT_AXIS = "a"
    DEFAULT_FILTER_ENABLED = False
    DEFAULT_FILTER_STRENGTH = 0.5
    DEFAULT_FILTER_METHOD = "kalman"
    CHANNEL_INDICES = {"a": 0, "b": 1, "c": 2, "d": 3}
    CHANNELS = ("a", "b", "c", "d")
    MAX_CALIBRATION_RETRIES = 3
    SPECTRUM_QUEUE_SIZE = 100


@dataclass
class LifecycleState:
    """Application lifecycle state (startup, shutdown, connection status)."""

    closing: bool = False
    device_config_initialized: bool = False
    initial_connection_done: bool = False
    deferred_connections_pending: bool = True
    intentional_disconnect: bool = False  # Track user-initiated disconnect


@dataclass
class ExperimentState:
    """Experiment session state (timing, data directories)."""

    start_time: Optional[float] = None
    last_cycle_bounds: Optional[tuple] = None
    session_cycles_dir: Optional[str] = None


@dataclass
class CalibrationState:
    """Calibration process state (retry count, completion status)."""

    retry_count: int = 0
    max_retries: int = MAX_CALIBRATION_RETRIES
    completed: bool = False
    qc_dialog: Optional[Any] = None  # QC dialog reference


@dataclass
class ChannelState:
    """Channel and axis selection state."""

    selected_axis: str = DEFAULT_AXIS
    selected_channel: Optional[str] = None
    reference_channel: Optional[str] = None
    ref_subtraction_enabled: bool = False
    ref_channel: Optional[str] = None


@dataclass
class FilteringState:
    """Data filtering configuration (Kalman, EMA, etc.)."""

    # Post-acquisition filtering (applied to stored data)
    filter_enabled: bool = DEFAULT_FILTER_ENABLED
    filter_strength: float = DEFAULT_FILTER_STRENGTH
    filter_method: str = DEFAULT_FILTER_METHOD
    kalman_filters: Dict[str, Any] = field(default_factory=dict)
    flag_data: list = field(default_factory=list)

    # Live display filtering (EMA smoothing for visualization only)
    ema_state: Dict[str, Optional[float]] = field(
        default_factory=lambda: {"a": None, "b": None, "c": None, "d": None}
    )
    display_filter_method: str = "none"  # 'none', 'ema_light', 'ema_smooth'
    display_filter_alpha: float = 0.0


@dataclass
class TimeframeModeState:
    """Live cycle timeframe mode state (parallel to cursor system).

    PHASE 1: Timeframe-based windowing as alternative to cursor selection.
    """

    live_cycle_timeframe: int = 5  # minutes (default)
    live_cycle_mode: str = "moving"  # 'moving' or 'fixed'
    enabled: bool = False  # Feature flag (DISABLED by default, uses legacy cursors)

    # Persistent baseline for moving window mode
    baseline_wavelengths: Dict[str, Optional[float]] = field(
        default_factory=lambda: {"a": None, "b": None, "c": None, "d": None}
    )

    # Track last processed timestamp to avoid re-appending same data
    last_processed_time: Dict[str, float] = field(
        default_factory=lambda: {"a": -1.0, "b": -1.0, "c": -1.0, "d": -1.0}
    )

    last_update_timestamp: float = 0  # Throttling timestamp


@dataclass
class LEDMonitoringState:
    """LED status monitoring state."""

    led_status_timer: Optional[Any] = None  # QTimer reference


@dataclass
class PerformanceState:
    """Performance optimization lookups and counters."""

    # Pre-computed lookups (immutable after init)
    channel_to_idx: Dict[str, int] = field(
        default_factory=lambda: dict(CHANNEL_INDICES)
    )
    idx_to_channel: tuple = field(default_factory=lambda: tuple(CHANNELS))
    channel_pairs: list = field(
        default_factory=lambda: [(ch, idx) for ch, idx in CHANNEL_INDICES.items()]
    )

    # Acquisition/processing queue
    spectrum_queue: Queue = field(default_factory=lambda: Queue(maxsize=SPECTRUM_QUEUE_SIZE))
    processing_thread: Optional[Any] = None
    processing_active: bool = False
    queue_stats: Dict[str, int] = field(
        default_factory=lambda: {"dropped": 0, "processed": 0, "max_size": 0}
    )

    # Performance counters
    acquisition_counter: int = 0
    last_transmission_update: Dict[str, int] = field(
        default_factory=lambda: {"a": 0, "b": 0, "c": 0, "d": 0}
    )
    sensorgram_update_counter: int = 0


@dataclass
class UIState:
    """UI update management state."""

    pending_graph_updates: Dict[str, Optional[Any]] = field(
        default_factory=lambda: {"a": None, "b": None, "c": None, "d": None}
    )
    skip_graph_updates: bool = False
    has_stop_cursor: bool = False  # Cached check for cursor availability


@dataclass
class BaselineRecordingState:
    """Baseline data recording state."""

    recorder: Optional[Any] = None  # BaselineRecorder reference


@dataclass
class ApplicationState:
    """Centralized application state container.

    All application state is grouped into logical subsystems for clarity.
    This replaces the scattered instance variables in Application.__init__().
    """

    lifecycle: LifecycleState = field(default_factory=LifecycleState)
    experiment: ExperimentState = field(default_factory=ExperimentState)
    calibration: CalibrationState = field(default_factory=CalibrationState)
    channel: ChannelState = field(default_factory=ChannelState)
    filtering: FilteringState = field(default_factory=FilteringState)
    timeframe_mode: TimeframeModeState = field(default_factory=TimeframeModeState)
    led_monitoring: LEDMonitoringState = field(default_factory=LEDMonitoringState)
    performance: PerformanceState = field(default_factory=PerformanceState)
    ui: UIState = field(default_factory=UIState)
    baseline_recording: BaselineRecordingState = field(
        default_factory=BaselineRecordingState
    )

    def __post_init__(self):
        """Post-initialization validation."""
        # Validate channel axis is valid
        if self.channel.selected_axis not in CHANNELS:
            raise ValueError(
                f"Invalid axis: {self.channel.selected_axis}. Must be one of {CHANNELS}"
            )

        # Validate filter method
        valid_filter_methods = ["none", "kalman", "savgol", "ema"]
        if self.filtering.filter_method not in valid_filter_methods:
            raise ValueError(
                f"Invalid filter method: {self.filtering.filter_method}. "
                f"Must be one of {valid_filter_methods}"
            )


# ============================================================================
# MIGRATION HELPER: Compatibility Properties
# ============================================================================
# These properties allow backward compatibility during migration.
# Instead of rewriting ALL code at once, we can gradually refactor by:
#   1. Replace self.closing → self.state.lifecycle.closing
#   2. Once all references updated, remove compatibility properties
#
# Example usage in Application class:
#
#   @property
#   def closing(self):
#       """Backward compatibility - use self.state.lifecycle.closing instead."""
#       return self.state.lifecycle.closing
#
#   @closing.setter
#   def closing(self, value):
#       self.state.lifecycle.closing = value
#
# ============================================================================
