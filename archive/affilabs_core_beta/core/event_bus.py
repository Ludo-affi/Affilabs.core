"""Centralized Event Bus for Application-wide Signal Management

This event bus centralizes all signal routing between UI, managers, and coordinators,
making the architecture more maintainable and easier to debug.

Architecture Benefits:
- Single source of truth for all application events
- Easy to see all signal flows in one place
- Simplified testing (mock the bus instead of individual connections)
- Automatic logging/debugging of event flow
- Type-safe event definitions

Author: AI Assistant
Date: November 23, 2025
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal

from utils.logger import logger


class EventBus(QObject):
    """Centralized event bus for application-wide signal management.

    This class acts as a mediator between:
    - UI components (user actions)
    - Core managers (hardware, data acquisition, recording, kinetic)
    - Coordinators (calibration, graphs, cycles)

    Architecture Pattern:
        UI → EventBus → Manager
        Manager → EventBus → Coordinator/UI

    Benefits:
    - Decouples components (UI doesn't need to know about managers)
    - Makes signal flow visible in one place
    - Easier to debug (can log all events here)
    - Simpler to mock for testing
    """

    # ========================================================================
    # HARDWARE EVENTS
    # ========================================================================
    hardware_connected = Signal(dict)  # status: dict with device info
    hardware_disconnected = Signal()
    hardware_connection_progress = Signal(str)  # message: progress update
    hardware_error = Signal(str)  # error: error message

    # ========================================================================
    # DATA ACQUISITION EVENTS
    # ========================================================================
    spectrum_acquired = Signal(dict)  # data: spectrum data dict
    acquisition_started = Signal()
    acquisition_stopped = Signal()
    acquisition_error = Signal(str)  # error: error message
    acquisition_pause_requested = Signal(bool)  # pause: True to pause, False to resume

    # ========================================================================
    # CALIBRATION EVENTS
    # ========================================================================
    calibration_started = Signal()
    calibration_complete = Signal(dict)  # calibration_data: results dict
    calibration_failed = Signal(str)  # error: error message
    calibration_progress = Signal(str)  # message: progress update

    # ========================================================================
    # RECORDING EVENTS
    # ========================================================================
    recording_started = Signal(str)  # filename: output file path
    recording_stopped = Signal()
    recording_error = Signal(str)  # error: error message
    event_logged = Signal(str, str)  # event_type, description

    # ========================================================================
    # KINETIC (PUMP/FLOW) EVENTS
    # ========================================================================
    pump_initialized = Signal(dict)  # info: pump configuration
    pump_error = Signal(str)  # error: error message
    pump_state_changed = Signal(str)  # state: pump state string
    valve_switched = Signal(str)  # position: valve position

    # ========================================================================
    # UI CONTROL EVENTS (Graph Controls)
    # ========================================================================
    grid_toggled = Signal(bool)  # enabled: grid visibility
    autoscale_toggled = Signal(bool)  # enabled: auto-scaling mode
    manual_scale_toggled = Signal(bool)  # enabled: manual scaling mode
    manual_range_changed = Signal()  # Triggered when user changes min/max inputs
    axis_selected = Signal(str)  # axis: 'x' or 'y'
    cursor_position_changed = Signal(
        str,
        float,
    )  # cursor_name ('start'/'stop'), position
    graph_clicked = Signal(object)  # event: mouse click event on graph

    # ========================================================================
    # UI TAB EVENTS (Sidebar Tab Management)
    # ========================================================================
    tab_changed = Signal(int, str)  # index, tab_name
    tab_content_loaded = Signal(str)  # tab_name: when tab content finishes loading
    tab_shown = Signal(str)  # tab_name: when tab becomes visible
    tab_hidden = Signal(str)  # tab_name: when tab becomes hidden

    # ========================================================================
    # UI REQUEST EVENTS (User Actions)
    # ========================================================================
    power_on_requested = Signal()  # User clicked power on
    power_off_requested = Signal()  # User clicked power off
    recording_start_requested = Signal()  # User clicked start recording
    recording_stop_requested = Signal()  # User clicked stop recording
    export_requested = Signal(str, str)  # format ('csv'/'image'), target_path
    calibration_requested = Signal(str)  # calibration_type ('simple'/'full'/'oem')

    # ========================================================================
    # FILTERING/PROCESSING EVENTS
    # ========================================================================
    filter_toggled = Signal(bool)  # enabled: data filtering
    filter_strength_changed = Signal(int)  # strength: filter strength value
    reference_channel_changed = Signal(str)  # channel: 'none', 'a', 'b', 'c', 'd'

    def __init__(self, parent: QObject | None = None, debug_mode: bool = False):
        super().__init__(parent)
        self.debug_mode = debug_mode

        if debug_mode:
            logger.info(
                "🚌 EventBus initialized in DEBUG mode - all events will be logged",
            )
            self._connect_debug_logging()

    def _connect_debug_logging(self):
        """Connect debug logging to all signals for troubleshooting."""
        # Hardware events
        self.hardware_connected.connect(
            lambda d: logger.debug(f"[EventBus] hardware_connected: {d}"),
        )
        # self.hardware_disconnected.connect(lambda: logger.debug("[EventBus] hardware_disconnected"))
        # self.hardware_connection_progress.connect(lambda m: logger.debug(f"[EventBus] hardware_connection_progress: {m}"))
        # self.hardware_error.connect(lambda e: logger.debug(f"[EventBus] hardware_error: {e}"))

        # Data acquisition events
        # DISABLED: These lambdas execute in worker thread and cause Qt threading errors
        # self.spectrum_acquired.connect(lambda d: logger.debug(f"[EventBus] spectrum_acquired: {len(d)} keys"))
        # self.acquisition_started.connect(lambda: logger.debug("[EventBus] acquisition_started"))
        # self.acquisition_stopped.connect(lambda: logger.debug("[EventBus] acquisition_stopped"))
        # self.acquisition_error.connect(lambda e: logger.debug(f"[EventBus] acquisition_error: {e}"))

        # Calibration events
        # self.calibration_started.connect(lambda: logger.debug("[EventBus] calibration_started"))
        # self.calibration_complete.connect(lambda d: logger.debug(f"[EventBus] calibration_complete"))
        # self.calibration_failed.connect(lambda e: logger.debug(f"[EventBus] calibration_failed: {e}"))
        # self.calibration_progress.connect(lambda m: logger.debug(f"[EventBus] calibration_progress: {m}"))

        # Recording events
        self.recording_started.connect(
            lambda f: logger.debug(f"[EventBus] recording_started: {f}"),
        )
        self.recording_stopped.connect(
            lambda: logger.debug("[EventBus] recording_stopped"),
        )
        self.recording_error.connect(
            lambda e: logger.debug(f"[EventBus] recording_error: {e}"),
        )

        # UI events
        self.power_on_requested.connect(
            lambda: logger.debug("[EventBus] power_on_requested"),
        )
        self.power_off_requested.connect(
            lambda: logger.debug("[EventBus] power_off_requested"),
        )
        self.recording_start_requested.connect(
            lambda: logger.debug("[EventBus] recording_start_requested"),
        )
        self.recording_stop_requested.connect(
            lambda: logger.debug("[EventBus] recording_stop_requested"),
        )

    def connect_hardware_manager(self, hardware_mgr):
        """Connect hardware manager signals to event bus.

        Args:
            hardware_mgr: HardwareManager instance

        """
        # Use QueuedConnection to ensure slot execution occurs on the GUI thread.
        # HardwareManager emits from a Python threading.Thread; without queued delivery
        # Qt may attempt direct invocation causing QObject warnings when UI elements
        # (e.g., dialogs) are created in that worker context.
        hardware_mgr.hardware_connected.connect(
            self.hardware_connected.emit,
            Qt.QueuedConnection,
        )
        hardware_mgr.hardware_disconnected.connect(
            self.hardware_disconnected.emit,
            Qt.QueuedConnection,
        )
        hardware_mgr.connection_progress.connect(
            self.hardware_connection_progress.emit,
            Qt.QueuedConnection,
        )
        hardware_mgr.error_occurred.connect(
            self.hardware_error.emit,
            Qt.QueuedConnection,
        )
        logger.info(
            "✓ Hardware manager connected to event bus (queued for thread safety)",
        )

    def connect_data_acquisition_manager(self, data_mgr):
        """Connect data acquisition manager signals to event bus.

        NOTE: EventBus is currently UNUSED in the application architecture.
        Signals are connected directly between components:
        - CalibrationManager → CalibrationCoordinator → Application
        - DataAcquisitionManager → Application (direct references)

        This method exists for legacy compatibility but is not actively used.

        Args:
            data_mgr: DataAcquisitionManager instance

        """
        data_mgr.spectrum_acquired.connect(
            self.spectrum_acquired.emit,
            Qt.QueuedConnection,
        )
        data_mgr.acquisition_started.connect(
            self.acquisition_started.emit,
            Qt.QueuedConnection,
        )
        data_mgr.acquisition_stopped.connect(
            self.acquisition_stopped.emit,
            Qt.QueuedConnection,
        )
        data_mgr.acquisition_error.connect(
            self.acquisition_error.emit,
            Qt.QueuedConnection,
        )
        logger.info(
            "✓ Data acquisition manager connected to event bus (UNUSED - direct connections used instead)",
        )

    def connect_recording_manager(self, recording_mgr):
        """Connect recording manager signals to event bus.

        Args:
            recording_mgr: RecordingManager instance

        """
        recording_mgr.recording_started.connect(self.recording_started.emit)
        recording_mgr.recording_stopped.connect(self.recording_stopped.emit)
        recording_mgr.recording_error.connect(self.recording_error.emit)
        recording_mgr.event_logged.connect(self.event_logged.emit)
        logger.info("✓ Recording manager connected to event bus")

    def connect_kinetic_manager(self, kinetic_mgr):
        """Connect kinetic manager signals to event bus.

        Args:
            kinetic_mgr: KineticManager instance

        """
        kinetic_mgr.pump_initialized.connect(self.pump_initialized.emit)
        kinetic_mgr.pump_error.connect(self.pump_error.emit)
        kinetic_mgr.pump_state_changed.connect(self.pump_state_changed.emit)
        kinetic_mgr.valve_switched.connect(self.valve_switched.emit)
        logger.info("✓ Kinetic manager connected to event bus")

    def connect_ui_signals(self, ui):
        """Connect UI request signals to event bus.

        Args:
            ui: UIAdapter instance

        """
        ui.power_on_requested.connect(self.power_on_requested.emit)
        ui.power_off_requested.connect(self.power_off_requested.emit)
        ui.recording_start_requested.connect(self.recording_start_requested.emit)
        ui.recording_stop_requested.connect(self.recording_stop_requested.emit)
        ui.export_requested.connect(self.export_requested.emit)
        ui.acquisition_pause_requested.connect(self.acquisition_pause_requested.emit)
        logger.info("✓ UI signals connected to event bus")
