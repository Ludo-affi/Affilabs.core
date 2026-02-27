"""AffiLabs.core Production UI - Main Window

PRODUCTION CODE - Used by main_simplified.py

This module contains the production main window (AffilabsMainWindow) for AffiLabs.core application.

NOT TO BE CONFUSED WITH:
========================
- widgets/mainwindow.py (old/unused version)
- LL_UI_v1_0.py (actual prototype UI, not production)

MODULAR DESIGN:
===============
- AffilabsMainWindow: Main application window with navigation, tabs, and graphs
- StartupCalibProgressDialog: Non-modal calibration progress dialog
- ElementInspector: Developer tool for inspecting UI elements
- Components imported from: sidebar.py (AffilabsSidebar), sections.py, plot_helpers.py

UI ARCHITECTURE:
================
- Clean separation from business logic (managed by main_simplified.py)
- Direct signal connections (no EventBus layer)
- Signal-based communication with Application layer
- Independently updatable without touching core logic
- Scalable: new features added here don't affect hardware/data managers

INTEGRATION REFERENCE:
======================

1. SIGNALS (UI → Application):
   - power_on_requested / power_off_requested: User pressed power button
   - recording_start_requested / recording_stop_requested: User pressed record button
   - acquisition_pause_requested(bool): User paused/resumed acquisition

2. KEY UI ELEMENTS (for external access):
   Navigation & Control:
   - self.power_btn: Power button (checkable, has "powerState" property)
   - self.record_btn: Record button (checkable)
   - self.pause_btn: Pause button (checkable)
   - self.navigation_presenter: NavigationPresenter managing navigation bar and page switching

   Main Graphs:
   - self.full_timeline_graph: Top graph showing full experiment timeline
   - self.cycle_of_interest_graph: Bottom graph showing zoomed region

   Sidebar Controls (forwarded from AffilabsSidebar):
   - self.grid_check: Show/hide grid checkbox
   - self.auto_radio / self.manual_radio: Y-axis scaling mode
   - self.min_input / self.max_input: Manual Y-axis range inputs
   - self.x_axis_btn / self.y_axis_btn: Axis selection for scaling
   - self.filter_enable: Data filtering checkbox
   - self.filter_slider: Filter strength slider
   - self.ref_combo: Reference channel dropdown
   - self.channel_a/b/c/d_input: LED intensity inputs
   - self.s_position_input / self.p_position_input: Polarizer position inputs
   - self.polarizer_toggle_btn: Toggle S/P polarizer position
   - self.simple_led_calibration_btn: Quick LED calibration
   - self.full_calibration_btn: Full system calibration
   - self.transmission_plot / self.raw_data_plot: Spectroscopy diagnostic plots

   Device Status (in sidebar):
   - self.sidebar.subunit_status_labels: Dict of status indicators per subunit

3. METHODS FOR APPLICATION TO CALL:
   State Updates:
   - update_recording_state(is_recording: bool): Update record button state
   - enable_controls(): Enable record/pause buttons after calibration
   - _set_power_button_state(state: str): Set power button ('disconnected', 'searching', 'connected')
   - _update_power_button_style(): Refresh power button styling

   Status Updates:
   - _set_subunit_status(subunit: str, ready: bool, details: dict): Update device status

   Data Display:
   - Graph updates via curve.setData() on self.full_timeline_graph.curves[idx]
   - Transmission plot via self.transmission_curves[idx].setData()

4. NAMING CONVENTIONS:
   - Buttons: {purpose}_btn (e.g., record_btn, pause_btn, power_btn)
   - Graphs/Plots: {name}_graph or {name}_plot
   - Inputs: {purpose}_input (e.g., channel_a_input, min_input)
   - Checkboxes: {purpose}_check (e.g., grid_check, filter_enable)
   - Radios: {purpose}_radio (e.g., auto_radio, manual_radio)
   - Sliders: {purpose}_slider (e.g., filter_slider)
   - Combos: {purpose}_combo (e.g., ref_combo)

5. INTEGRATION EXAMPLE (from main_simplified.py):
   ```python
   # In Application.__init__():
   self.main_window = MainWindowPrototype()
   self.main_window.app = self  # Store reference to app

   # Connect signals:
   self.main_window.power_on_requested.connect(self._on_power_on)
   self.main_window.recording_start_requested.connect(self._start_recording)

   # Update UI from app:
   self.main_window.update_recording_state(True)
   self.main_window._set_power_button_state('connected')
   ```

USAGE:
======
This UI is integrated with main_simplified.py via:
    from affilabs_core_ui import MainWindowPrototype

Last Updated: November 22, 2025
"""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import (
    QEvent,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QIcon, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QSplitterHandle,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Add Old software to path for imports
old_software = Path(__file__).parent
sys.path.insert(0, str(old_software))

from typing import Any

from affilabs.affilabs_sidebar import AffilabsSidebar
from affilabs.core.system_intelligence import SystemState, get_system_intelligence
from affilabs.dialogs.advanced_settings_dialog import AdvancedSettingsDialog
from affilabs.plot_helpers import add_channel_curves, create_time_plot
from affilabs.widgets.cycle_intelligence_footer import CycleIntelligenceFooter
from affilabs.widgets.spark_sidebar import SparkSidebar
from affilabs.widgets.spark_bubble import SparkBubble
# EditsTab lazy loaded when needed to speed up startup
from affilabs.ui_styles import (
    Colors,
    Fonts,
    Dimensions,
    create_card_shadow,
    label_style,
)
from affilabs.utils.logger import logger
from affilabs.ui_mixins import (
    PanelBuilderMixin,
    DeviceStatusMixin,
    TimerMixin,
    EditsCycleMixin,
    SettingsMixin,
)

# Dialog classes moved to affilabs/dialogs/ for modularity:
# - StartupCalibProgressDialog -> affilabs/dialogs/startup_calib_dialog.py
# - DeviceConfigDialog -> affilabs/dialogs/device_config_dialog.py
# Import from affilabs.dialogs if needed


class _GripHandle(QSplitterHandle):
    """Splitter handle that paints a visible 5-dot grip indicator."""

    _CLR_DEFAULT = QColor(110, 110, 120)
    _CLR_HOVER   = QColor(60,  60,  70)
    _CLR_PRESS   = QColor(29,  29,  31)
    _BG_DEFAULT  = QColor(0, 0, 0, 10)
    _BG_HOVER    = QColor(0, 122, 255, 18)
    _BG_PRESS    = QColor(0, 122, 255, 35)

    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self._hovered = False
        self._pressed = False
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setToolTip("Drag to resize graphs")

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._pressed = True
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background strip
        bg = self._BG_PRESS if self._pressed else (self._BG_HOVER if self._hovered else self._BG_DEFAULT)
        p.fillRect(self.rect(), bg)

        # 3 grip dots centred in the handle with vertical padding
        dot_color = self._CLR_PRESS if self._pressed else (self._CLR_HOVER if self._hovered else self._CLR_DEFAULT)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(dot_color)
        n, dot_r, spacing = 3, 2.0, 8
        total_w = (n - 1) * spacing
        start_x = (w - total_w) / 2
        pad = 2
        cy = max(dot_r + pad, min(h - dot_r - pad, h / 2))
        for i in range(n):
            cx = start_x + i * spacing
            p.drawEllipse(int(cx - dot_r), int(cy - dot_r), int(dot_r * 2), int(dot_r * 2))
        p.end()


class _GripSplitter(QSplitter):
    """QSplitter that uses _GripHandle for all split handles."""

    def createHandle(self) -> QSplitterHandle:  # noqa: N802
        return _GripHandle(self.orientation(), self)


class AffilabsMainWindow(
    PanelBuilderMixin,
    DeviceStatusMixin,
    TimerMixin,
    EditsCycleMixin,
    SettingsMixin,
    QMainWindow,
):
    """Production main window for AffiLabs.core application.

    QUICK REFERENCE FOR INTEGRATION:
    ================================
    Signals (UI → App):
        - power_on_requested / power_off_requested
        - recording_start_requested / recording_stop_requested
        - acquisition_pause_requested(bool)
        - apply_led_settings_requested(dict)  # LED settings from Settings tab

    Key Control Elements:
        - power_btn, record_btn, pause_btn
        - full_timeline_graph, cycle_of_interest_graph
        - sidebar controls: filter_enable, ref_combo, channel inputs, etc.

    Methods to Call from App:
        - update_recording_state(bool)
        - enable_controls()
        - _set_power_button_state(str)
        - _set_subunit_status(str, bool, dict)

    See module docstring for complete integration reference.
    """

    # Signal emitted when user applies LED settings (signal-based communication)
    apply_led_settings_requested = Signal(dict)

    # Signals for power button
    power_on_requested = Signal()
    power_off_requested = Signal()

    # Signals for recording
    recording_start_requested = Signal()
    recording_stop_requested = Signal()

    # Signal for pause/resume
    acquisition_pause_requested = Signal(bool)  # True=pause, False=resume

    # Signal for export operations
    export_requested = Signal(dict)  # Export configuration dict
    send_to_edits_requested = Signal()  # Transfer live data to Edits tab

    def __init__(self):
        super().__init__()
        # Import version information
        from version import __version__
        self.setWindowTitle(f"AffiLabs.core v{__version__}")
        # Set window icon using resource path helper (works in both dev and frozen exe)
        from affilabs.utils.resource_path import get_affilabs_resource

        icon_path = get_affilabs_resource("ui/img/affinite2.ico")
        if icon_path.exists():
            icon = QIcon(str(icon_path))
            if not icon.isNull():
                self.setWindowIcon(icon)
                logger.debug(f"Window icon loaded successfully: {icon_path}")
            else:
                logger.warning(f"Failed to create icon from file: {icon_path}")
        else:
            logger.warning(f"Icon file not found: {icon_path}")
        self.setGeometry(50, 50, 1400, 800)
        self.is_recording = False
        self.recording_indicator = None
        self.record_button = None

        # Device configuration and maintenance tracking
        self.device_config = None
        self.led_start_time = None
        self.last_powered_on = None

        # OEM provisioning flag - set to True when device config dialog completes
        # Used to trigger calibration when spectrometer is connected after config
        self.oem_config_just_completed = False

        # Live data flag (default enabled)
        self.live_data_enabled = True

        # Cursor input update guard flag
        self._updating_cursor_inputs = False

        # Advanced parameters unlock tracking
        self.advanced_params_click_count = 0
        self.advanced_params_unlocked = False
        self.advanced_params_timer = None
        self.click_reset_timer = QTimer()
        self.click_reset_timer.setSingleShot(True)
        # Use lambda to defer method lookup until timer fires
        self.click_reset_timer.timeout.connect(lambda: self._reset_click_count())

        # Cycle queue management
        self.cycle_queue = []
        self.max_queue_size = 10
        self._current_running_cycle = None  # Track currently running cycle

        # Countdown timer for cycle tracking
        self.cycle_countdown_timer = QTimer()
        self.cycle_countdown_timer.timeout.connect(self._update_countdown)
        self.cycle_start_time = None
        self.cycle_duration_seconds = 0

        # Initialize intelligence bar refresh timer (update every 5 seconds)
        self.intelligence_refresh_timer = QTimer()
        self.intelligence_refresh_timer.timeout.connect(self._refresh_intelligence_bar)
        self.intelligence_refresh_timer.start(5000)  # 5 seconds

        # Track deferred UI loading state
        self._deferred_ui_loaded = False
        self._graph_placeholders_created = False

        # Initialize managers for domain logic (Manager Pattern) - BEFORE _setup_ui()
        from affilabs.managers import CalibrationManager, DeviceConfigManager
        from affilabs.presenters import (
            BaselineRecordingPresenter,
            NavigationPresenter,
            SensogramPresenter,
        )

        self.device_config_manager = DeviceConfigManager(self)
        self.calibration_manager = CalibrationManager(self)
        self.baseline_recording_presenter = BaselineRecordingPresenter(self)
        self.navigation_presenter = NavigationPresenter(self)
        self.sensogram_presenter = SensogramPresenter(self)

        self._setup_ui()
        self._connect_signals()

        # Device configuration will be initialized when hardware connects with actual serial number
        # See device_config_manager.initialize_device_config() called from main_simplified._on_hardware_connected()
        self.device_config = None

        # Optics warning state tracking
        self._optics_warning_active = False
        self._optics_status_details = None

        # Connecting indicator animation state
        self._connecting_anim_timer = QTimer()
        self._connecting_anim_timer.setInterval(300)
        self._connecting_anim_timer.setSingleShot(False)
        self._connecting_anim_step = 0
        self._connecting_anim_timer.timeout.connect(self._update_connecting_animation)

        # Semi-transparent backdrop for connecting overlay
        self._connecting_backdrop = QFrame(self)
        self._connecting_backdrop.setStyleSheet(
            "QFrame { background: rgba(0, 0, 0, 0.35); }"
        )
        self._connecting_backdrop.setVisible(False)

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create splitter for resizable sidebar
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(6)
        self.splitter.setStyleSheet(
            "QSplitter::handle {"
            "  background: rgba(0, 0, 0, 0.06);"
            "}"
            "QSplitter::handle:hover {"
            "  background: rgba(0, 0, 0, 0.1);"
            "}"
            "QSplitter::handle:pressed {"
            "  background: rgba(0, 0, 0, 0.15);"
            "}",
        )

        self.sidebar = AffilabsSidebar()
        self.sidebar.setMinimumWidth(50)   # ~tab bar width — always keeps icon strip visible
        self.sidebar.setMaximumWidth(380)  # Fixed panel width — matches UserSidebarPanel
        # Give sidebar reference to device_config for S/P position syncing
        self.sidebar.device_config = self.device_config
        # Give sidebar reference to app for accessing _completed_cycles
        # Note: Will be set by Application.__init__ after main_window creation
        self.sidebar.app = None

        # Forward sidebar control references to main window for easy access
        # colorblind_check now lives on accessibility_panel (wired after panel creation below)
        self.colorblind_check = None
        self.ref_combo = getattr(self.sidebar, 'ref_combo', None)
        self.export_data_btn = getattr(self.sidebar, 'export_data_btn', None)

        # Initialize unit buttons (will be set from advanced settings)
        self.ru_btn = QPushButton("RU")
        self.ru_btn.setCheckable(True)
        self.ru_btn.setChecked(True)
        self.nm_btn = QPushButton("nm")
        self.nm_btn.setCheckable(True)
        self.nm_btn.setChecked(False)

        # Connect unit toggle
        self.ru_btn.toggled.connect(self._on_unit_changed)
        self.nm_btn.toggled.connect(self._on_unit_changed)

        # Forward settings controls
        self.s_position_input = self.sidebar.s_position_input
        self.p_position_input = self.sidebar.p_position_input
        self.polarizer_toggle_btn = self.sidebar.polarizer_toggle_btn
        self.channel_a_input = self.sidebar.channel_a_input
        self.channel_b_input = self.sidebar.channel_b_input
        self.channel_c_input = self.sidebar.channel_c_input
        self.channel_d_input = self.sidebar.channel_d_input
        self.apply_settings_btn = self.sidebar.apply_settings_btn

        # Connect colorblind mode signal to update button colors
        if hasattr(self.sidebar, 'colorblind_mode_signal'):
            self.sidebar.colorblind_mode_signal.connect(self._on_colorblind_mode_changed)

        # Spectroscopy plots live in SpectrumBubble (floating overlay, dark-themed popup).
        # Attributes are aliased after SpectrumBubble is created in the floating-widgets block below.
        self.live_context_panel = None  # removed — replaced by SpectrumBubble
        self.transmission_plot = None
        self.transmission_curves: list = []
        self.raw_data_plot = None
        self.raw_data_curves: list = []
        self.baseline_capture_btn = None

        # Forward calibration buttons
        self.simple_led_calibration_btn = self.sidebar.simple_led_calibration_btn
        self.full_calibration_btn = self.sidebar.full_calibration_btn
        self.polarizer_calibration_btn = self.sidebar.polarizer_calibration_btn
        self.oem_led_calibration_btn = self.sidebar.oem_led_calibration_btn
        self.led_model_training_btn = self.sidebar.led_model_training_btn

        # baseline_capture_btn is aliased from SpectrumBubble (created in floating-widgets block below)
        # sidebar no longer has spectroscopy plots

        right_widget = QWidget()
        right_widget.setMinimumWidth(
            300,
        )  # Allow main content to compress so sidebar can expand more
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        # TransportBar replaces the old nav_bar (44px, includes all control buttons)
        from affilabs.widgets.transport_bar import TransportBar
        self.transport_bar = TransportBar(self)
        right_layout.addWidget(self.transport_bar)

        # Demo mode banner — shown when no valid license is present (hidden by default)
        self._demo_banner = self._build_demo_banner()
        right_layout.addWidget(self._demo_banner)
        self._demo_banner.setVisible(False)

        # Stage progress bar — kept as object so advance_to() calls don't crash, but hidden from layout
        from affilabs.widgets.stage_progress_bar import StageProgressBar
        self.stage_bar = StageProgressBar(self)
        self.stage_bar.hide()  # Not shown — progress communicated via the StepChip in transport bar

        # Forward stage_bar.advance_to() / reset() → TransportBar.step_chip so existing call sites
        # (in main.py, mixins, presenters) automatically update the chip without being changed.
        _orig_advance = self.stage_bar.advance_to
        _orig_reset   = self.stage_bar.reset
        _tb_ref       = self.transport_bar  # captured here; already constructed above

        def _advance_and_chip(stage: str, _fn=_orig_advance, _tb=_tb_ref) -> None:
            _fn(stage)
            try:
                _tb.step_chip.advance_to(stage)
            except Exception:
                pass

        def _reset_and_chip(_fn=_orig_reset, _tb=_tb_ref) -> None:
            _fn()
            try:
                _tb.step_chip.reset()
            except Exception:
                pass

        self.stage_bar.advance_to = _advance_and_chip  # type: ignore[method-assign]
        self.stage_bar.reset      = _reset_and_chip    # type: ignore[method-assign]

        # Wire build_method_btn on transport bar → actual sidebar button (main.py uses sidebar ref)
        self.build_method_btn = self.transport_bar.build_method_btn
        self.transport_bar.build_method_btn.clicked.connect(
            lambda: self.sidebar.build_method_btn.click()
        )

        # Stacked widget to hold different content pages
        from PySide6.QtWidgets import QStackedWidget
        # Note: Analysis and Report tabs disabled in this version

        self.content_stack = QStackedWidget()

        # Create placeholder for sensorgram (will be replaced with real graphs after window shows)
        self._sensorgram_placeholder = self._create_sensorgram_placeholder()
        self.content_stack.addWidget(self._sensorgram_placeholder)  # Index 0

        # Edits tab with cycle data table and timeline editing
        self.content_stack.addWidget(self._create_edits_content())  # Index 1

        # Notes tab — ELN, experiment history, search
        from affilabs.tabs.notes_tab import NotesTab
        self.notes_tab = NotesTab(self)
        self.content_stack.addWidget(self.notes_tab)  # Index 2

        # Analysis and Report tabs disabled - not used in this software version

        # Phase 2: Live Right Panel — shown/hidden by acquisition start/stop
        # live_right_panel removed — the splitter's right pane is now the Run Queue panel.
        self.live_right_panel = None
        right_layout.addWidget(self.content_stack, 1)

        # SparkSidebar kept alive (off-screen) — SparkBubble is the active floating Spark UI
        try:
            self.spark_sidebar = SparkSidebar()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"SparkSidebar creation failed (non-fatal): {e}")
            self.spark_sidebar = QWidget()
        self.spark_sidebar.hide()

        # Build collapsible right Run Queue panel (populated with sidebar.queue_panel below)
        self._queue_right_panel = self._build_queue_right_panel()
        # Populate it with the queue widget now — sidebar is fully built at this point
        if hasattr(self.sidebar, 'queue_panel') and hasattr(self, '_queue_content_layout'):
            # Queue table first (stretch=1 so it fills available space)
            self._queue_content_layout.addWidget(self.sidebar.queue_panel, 1)

            # Wire the in-table expand footer to the toggle handler
            tbl = getattr(self.sidebar, 'summary_table', None)
            if tbl is not None and hasattr(tbl, 'set_expand_callback'):
                tbl.set_expand_callback(self._on_toggle_queue_table_collapse)

            # Divider between queue table and Manual Injection Assistant
            from PySide6.QtWidgets import QFrame as _QFrame2
            _div = _QFrame2()
            _div.setFixedHeight(1)
            _div.setStyleSheet("QFrame { background: #E0E0E5; border: none; }")
            self._queue_content_layout.addWidget(_div, 0)
            # Manual Injection Assistant — below the queue table
            if hasattr(self.sidebar, 'injection_action_bar'):
                bar = self.sidebar.injection_action_bar
                bar.setParent(self._queue_right_panel)
                from PySide6.QtWidgets import QSizePolicy
                bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
                bar.setMaximumHeight(280)
                bar.show()
                self._queue_content_layout.addWidget(bar, 0)

        # Splitter: Sidebar (left) | TransportBar+Content (center) | Run Queue (right)
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(right_widget)
        self.splitter.addWidget(self._queue_right_panel)
        self.splitter.setCollapsible(0, True)   # Sidebar can collapse
        self.splitter.setCollapsible(1, False)  # Content panel never collapses
        self.splitter.setCollapsible(2, True)   # Run Queue panel can collapse

        # Sidebar collapsed by default (0px); run queue starts collapsed until a run begins
        self.splitter.setSizes([0, 1500, 0])

        # Add splitter directly to main layout
        # IconRail sits at far left (48px fixed), controls sidebar tab selection
        from affilabs.widgets.icon_rail import IconRail
        self.icon_rail = IconRail(parent=self)
        self.icon_rail.set_sidebar(self.sidebar)
        self.sidebar._icon_rail = self.icon_rail  # direct ref so show_flow_tab() works
        main_layout.addWidget(self.icon_rail)

        # User sidebar panel — hidden by default, toggled by icon rail user button
        from affilabs.widgets.user_panel_popup import UserSidebarPanel
        self.user_sidebar_panel = UserSidebarPanel(parent=self)
        self.user_sidebar_panel.setVisible(False)
        main_layout.addWidget(self.user_sidebar_panel)
        self.icon_rail._user_sidebar = self.user_sidebar_panel

        # Accessibility sidebar panel — hidden by default, toggled by icon rail accessibility button
        from affilabs.widgets.accessibility_panel import AccessibilityPanel
        self.accessibility_panel = AccessibilityPanel(parent=self)
        self.accessibility_panel.setVisible(False)
        main_layout.addWidget(self.accessibility_panel)
        self.icon_rail._accessibility_sidebar = self.accessibility_panel
        # Forward colorblind_check reference to main window
        self.colorblind_check = self.accessibility_panel.colorblind_check
        # Wire accessibility signals
        self.accessibility_panel.palette_changed.connect(self._on_palette_changed)
        self.accessibility_panel.line_style_changed.connect(self._on_line_style_changed)
        self.accessibility_panel.dark_mode_changed.connect(self._on_dark_mode_toggled)

        main_layout.addWidget(self.splitter)

        # Floating Sparq bubble — child widget, zero layout impact
        try:
            self.spark_bubble = SparkBubble(self)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"SparkBubble creation failed (non-fatal): {e}")
            self.spark_bubble = None

        # Floating Spectrum bubble — dark-themed popup, bottom-left corner
        try:
            from affilabs.widgets.spectrum_bubble import SpectrumBubble
            self.spectrum_bubble = SpectrumBubble(self)
            self.transmission_plot = self.spectrum_bubble.transmission_plot
            self.transmission_curves = self.spectrum_bubble.transmission_curves
            self.raw_data_plot = self.spectrum_bubble.raw_data_plot
            self.raw_data_curves = self.spectrum_bubble.raw_data_curves
            self.baseline_capture_btn = self.spectrum_bubble.baseline_capture_btn
            logger.debug(
                f"✓ SpectrumBubble: {len(self.transmission_curves)} transmission, "
                f"{len(self.raw_data_curves)} raw curves"
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"SpectrumBubble creation failed (non-fatal): {e}")
            self.spectrum_bubble = None

        # Ensure Sensorgram page (index 0) is shown by default
        self.content_stack.setCurrentIndex(0)

        # Phase 1: Status bar subunit dots
        self._setup_status_bar()

    def _setup_status_bar(self) -> None:
        """Phase 1: Create status bar with Sensor and Optics dot indicators."""
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        sb.setStyleSheet(
            "QStatusBar {"
            "  background: #F5F5F7;"
            "  border-top: 1px solid #D5D5D7;"
            "  font-size: 11px;"
            "}"
            "QStatusBar::item { border: none; }"
        )

        # Sensor/Optics dots — kept as attributes for device_status_mixin but not shown in UI
        self.subunit_sensor_dot = QLabel("● Sensor")
        self.subunit_sensor_dot.hide()
        self.subunit_optics_dot = QLabel("● Optics")
        self.subunit_optics_dot.hide()


        # Acquiring pulse dot — shown + blinks while DAQ is running (left side)
        self._acq_dot = QLabel("● ACQ")
        self._acq_dot.setStyleSheet(
            "color: #007AFF; font-size: 12px; font-weight: 700; margin: 0 8px; "
            "font-family: -apple-system, 'Segoe UI', system-ui, sans-serif;"
        )
        self._acq_dot.hide()
        sb.addWidget(self._acq_dot)

        # Recording badge — shown while file recording is active (left side)
        self._rec_badge_status = QLabel("● REC")
        self._rec_badge_status.setStyleSheet(
            "color: #FF3B30; font-size: 12px; font-weight: 700; margin: 0 4px 0 0; "
            "font-family: -apple-system, 'Segoe UI', system-ui, sans-serif;"
        )
        self._rec_badge_status.hide()
        sb.addWidget(self._rec_badge_status)

        # Recording path label — sits immediately right of the REC badge, no overlap with showMessage
        self._rec_path_label = QLabel()
        self._rec_path_label.setStyleSheet(
            "color: #FF3B30; font-size: 12px; margin: 0 8px 0 0; "
            "font-family: -apple-system, 'Segoe UI', system-ui, sans-serif;"
        )
        self._rec_path_label.hide()
        sb.addWidget(self._rec_path_label)

        # 800 ms blink timer for the acquiring dot
        self._acq_pulse_timer = QTimer(self)
        self._acq_pulse_timer.setInterval(800)
        self._acq_pulse_visible = True
        self._acq_pulse_timer.timeout.connect(self._tick_acq_pulse)

    def _create_sensorgram_content(self):
        """Create the Sensorgram tab content with dual-graph layout (master-detail pattern)."""
        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame {  background: #F8F9FA;  }",
        )

        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        content_layout.setSpacing(Dimensions.SPACING_SM)

        # Create QSplitter for resizable graph panels (30/70 split)
        splitter = _GripSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(10)
        splitter.setChildrenCollapsible(False)

        # Top graph (Navigation/Overview) - 30% - with integrated controls
        self.full_timeline_graph, top_graph = self._create_graph_container(
            "Live Sensorgram",
            height=200,
            show_delta_spr=False,
        )

        # Bottom graph (Detail/Cycle of Interest) - 70%
        self.cycle_of_interest_graph, bottom_graph = self._create_graph_container(
            "Active Cycle",
            height=400,
            show_delta_spr=True,
        )

        # Initialize Channel A as selected for timing adjustment (default)
        # Make Channel A curve thicker to show it's selected
        import pyqtgraph as pg
        channel_colors = [
            (0, 0, 0),        # A: Black
            (255, 0, 0),      # B: Red
            (0, 0, 255),      # C: Blue
            (0, 170, 0),      # D: Green
        ]
        for i, curve in enumerate(self.cycle_of_interest_graph.curves):
            if i == 0:  # Channel A is selected by default
                curve.setPen(pg.mkPen(color=channel_colors[i], width=4))
            else:
                curve.setPen(pg.mkPen(color=channel_colors[i], width=2))

        # Connect cursor signals for region selection
        if (
            self.full_timeline_graph.start_cursor
            and self.full_timeline_graph.stop_cursor
        ):
            self.full_timeline_graph.start_cursor.sigDragged.connect(
                self._on_cursor_dragged,
            )
            self.full_timeline_graph.stop_cursor.sigDragged.connect(
                self._on_cursor_dragged,
            )
            self.full_timeline_graph.start_cursor.sigPositionChangeFinished.connect(
                self._on_cursor_moved,
            )
            self.full_timeline_graph.stop_cursor.sigPositionChangeFinished.connect(
                self._on_cursor_moved,
            )

        splitter.addWidget(top_graph)
        splitter.addWidget(bottom_graph)

        # Set initial sizes (30% / 70%)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 7)

        # Handle appearance is owned by _GripHandle.paintEvent — no CSS needed here
        splitter.setStyleSheet("QSplitter { background-color: transparent; }")

        content_layout.addWidget(splitter, 1)

        return content_widget

    def show_connecting_indicator(self, active: bool) -> None:
        """Show or hide centered overlay 'Connecting to hardware...' indicator.

        When active, shows a centered overlay with animated text and busy cursor.
        When inactive, hides overlay and restores cursor.
        """
        try:
            if not hasattr(self, "connecting_label") or self.connecting_label is None:
                return

            from PySide6.QtWidgets import QApplication
            from affilabs.utils.logger import logger

            if active:
                # Only set cursor if not already set to avoid stacking
                if not hasattr(self, "_busy_cursor_active") or not self._busy_cursor_active:
                    self._connecting_anim_step = 0
                    import time as _time
                    self._connecting_start_time = _time.monotonic()
                    self.connecting_label.setText("Searching for instrument...")

                    # Show dimming backdrop over entire window
                    self._connecting_backdrop.setParent(self)
                    self._connecting_backdrop.setGeometry(0, 0, self.width(), self.height())
                    self._connecting_backdrop.setVisible(True)
                    self._connecting_backdrop.raise_()

                    # Position label as centered overlay on top of backdrop
                    self.connecting_label.setParent(self)
                    self.connecting_label.raise_()

                    # Center the label
                    label_width = 380
                    label_height = 80
                    x = (self.width() - label_width) // 2
                    y = (self.height() - label_height) // 2
                    self.connecting_label.setGeometry(x, y, label_width, label_height)

                    self.connecting_label.setVisible(True)

                    # Start animation and set busy cursor
                    self._connecting_anim_timer.start()
                    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                    self._busy_cursor_active = True
                    logger.debug("Connecting indicator: busy cursor set")
            else:
                # Stop animation and hide label + backdrop
                self._connecting_anim_timer.stop()
                self.connecting_label.setVisible(False)
                self._connecting_backdrop.setVisible(False)

                # Restore cursor with fallback safety
                if hasattr(self, "_busy_cursor_active") and self._busy_cursor_active:
                    try:
                        # Restore once for the cursor we set
                        QApplication.restoreOverrideCursor()
                        logger.debug("Connecting indicator: cursor restored")
                    except Exception as e:
                        logger.warning(f"Failed to restore cursor: {e}")
                    finally:
                        self._busy_cursor_active = False

                        # Safety: clear any remaining override cursors
                        # Qt can stack cursors, so restore until we're back to default
                        max_attempts = 5
                        attempts = 0
                        while QApplication.overrideCursor() is not None and attempts < max_attempts:
                            try:
                                QApplication.restoreOverrideCursor()
                                attempts += 1
                                logger.debug(f"Cleared stacked cursor (attempt {attempts})")
                            except Exception:
                                break
        except Exception as e:
            # Defensive: log but do not raise UI errors from optional indicator
            from affilabs.utils.logger import logger
            logger.error(f"Error in show_connecting_indicator: {e}")

    def _update_connecting_animation(self) -> None:
        """Tick the 'Connecting to hardware...' animated ellipsis with elapsed time."""
        try:
            if not hasattr(self, "connecting_label") or not self.connecting_label.isVisible():
                return
            import time as _time
            elapsed = int(_time.monotonic() - self._connecting_start_time) if hasattr(self, '_connecting_start_time') else 0
            dots = "." * (self._connecting_anim_step % 4)
            self.connecting_label.setText(f"Searching for instrument{dots}  {elapsed}s")
            self._connecting_anim_step += 1
        except Exception:
            pass

    def _build_demo_banner(self):
        """Build the amber demo-mode banner inserted below the transport bar."""
        from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

        banner = QFrame(self)
        banner.setObjectName("DemoBanner")
        banner.setFixedHeight(30)
        banner.setStyleSheet(
            "#DemoBanner {"
            "  background: #FFFBEC;"
            "  border-bottom: 1px solid #F0C840;"
            "}"
        )

        inner = QHBoxLayout(banner)
        inner.setContentsMargins(16, 0, 16, 0)
        inner.setSpacing(8)

        icon = QLabel("Demo Mode")
        icon.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #8B6914;"
            " background: transparent; border: none;"
        )
        inner.addWidget(icon)

        msg = QLabel("— hardware connection disabled.")
        msg.setStyleSheet(
            "font-size: 11px; color: #8B6914; background: transparent; border: none;"
        )
        inner.addWidget(msg, 1)

        activate_link = QPushButton("Enter License Key")
        activate_link.setObjectName("demo_activate_link")
        activate_link.setFlat(True)
        activate_link.setCursor(Qt.CursorShape.PointingHandCursor)
        activate_link.setStyleSheet(
            "QPushButton {"
            "  font-size: 11px; font-weight: 600; color: #007AFF;"
            "  background: transparent; border: none; text-decoration: underline;"
            "  padding: 0;"
            "}"
            "QPushButton:hover { color: #0051D5; }"
        )
        inner.addWidget(activate_link)

        return banner

    def _create_sensorgram_placeholder(self):
        """Create lightweight placeholder for sensorgram page during initial load.

        This placeholder mimics the actual UI layout with skeleton states
        so the transition is seamless when real graphs load.
        """
        placeholder = QFrame()
        placeholder.setStyleSheet(f"QFrame {{ background: {Colors.BACKGROUND_WHITE};  }}")

        layout = QVBoxLayout(placeholder)
        layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        layout.setSpacing(Dimensions.SPACING_LG)

        # Timeline section skeleton
        timeline_card = QFrame()
        timeline_card.setStyleSheet(f"""
            QFrame {{
                background: {Colors.BACKGROUND_WHITE};


            }}
        """)
        timeline_layout = QVBoxLayout(timeline_card)
        timeline_layout.setContentsMargins(16, 12, 16, 16)
        timeline_layout.setSpacing(8)

        timeline_title = QLabel("Full Timeline")
        timeline_title.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                font-weight: 600;
                color: {Colors.PRIMARY_TEXT};
                background: {Colors.TRANSPARENT};
            }}
        """)
        timeline_layout.addWidget(timeline_title)

        # Graph skeleton (light gray box)
        timeline_skeleton = QFrame()
        timeline_skeleton.setFixedHeight(200)
        timeline_skeleton.setStyleSheet(f"""
            QFrame {{
                background: {Colors.BACKGROUND_LIGHT};


            }}
        """)
        skeleton_layout = QVBoxLayout(timeline_skeleton)
        skeleton_label = QLabel("Loading graph...")
        skeleton_label.setStyleSheet(
            f"color: {Colors.SECONDARY_TEXT}; font-size: 12px; background: {Colors.TRANSPARENT};",
        )
        skeleton_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        skeleton_layout.addWidget(skeleton_label)
        timeline_layout.addWidget(timeline_skeleton)

        layout.addWidget(timeline_card)

        # Cycle section skeleton
        cycle_card = QFrame()
        cycle_card.setStyleSheet(f"""
            QFrame {{
                background: {Colors.BACKGROUND_WHITE};


            }}
        """)
        cycle_layout = QVBoxLayout(cycle_card)
        cycle_layout.setContentsMargins(16, 12, 16, 16)
        cycle_layout.setSpacing(8)

        cycle_title = QLabel("Cycle of Interest")
        cycle_title.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                font-weight: 600;
                color: {Colors.PRIMARY_TEXT};
                background: {Colors.TRANSPARENT};
            }}
        """)
        cycle_layout.addWidget(cycle_title)

        cycle_skeleton = QFrame()
        cycle_skeleton.setFixedHeight(250)
        cycle_skeleton.setStyleSheet(f"""
            QFrame {{
                background: {Colors.BACKGROUND_LIGHT};


            }}
        """)
        cycle_skeleton_layout = QVBoxLayout(cycle_skeleton)
        cycle_skeleton_label = QLabel("Loading graph...")
        cycle_skeleton_label.setStyleSheet(
            f"color: {Colors.SECONDARY_TEXT}; font-size: 12px; background: {Colors.TRANSPARENT};",
        )
        cycle_skeleton_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cycle_skeleton_layout.addWidget(cycle_skeleton_label)
        cycle_layout.addWidget(cycle_skeleton)

        layout.addWidget(cycle_card)

        return placeholder

    def load_deferred_graphs(self):
        """Load heavy graph widgets after window is visible.

        Called by main_simplified.py after window.show() to improve startup time.
        Replaces placeholder with real sensorgram graphs.
        """
        if self._deferred_ui_loaded:
            logger.debug("Deferred graphs already loaded, skipping")
            return  # Already loaded

        try:
            logger.info("📊 Loading sensorgram graphs...")

            # Create real sensorgram content
            sensorgram_widget = self._create_sensorgram_content()

            # Replace placeholder with real content
            self.content_stack.removeWidget(self._sensorgram_placeholder)
            self._sensorgram_placeholder.deleteLater()
            self.content_stack.insertWidget(0, sensorgram_widget)

            # Force display of Sensorgram page (index 0)
            self.navigation_presenter.switch_page(0)

            self._deferred_ui_loaded = True
            logger.info("✓ Sensorgram graphs loaded successfully")

        except Exception as e:
            logger.error(f"❌ Failed to load deferred graphs: {e}", exc_info=True)
            # Update placeholder with error message
            if hasattr(self, "_loading_label"):
                self._loading_label.setText(f"Error loading graphs: {e}")
                self._loading_label.setStyleSheet(
                    "QLabel { color: #FF3B30; font-size: 14px; }",
                )

    def _create_signal_quality_bar(self) -> QWidget:
        """Slim quality indicator row — one pill per channel showing live signal quality.

        Green = Good/Excellent  |  Yellow = Questionable  |  Red = Poor/Critical
        Updated by ui_update_coordinator via self.signal_quality_pills[ch].
        """
        bar = QWidget()
        bar.setFixedHeight(22)
        bar.setStyleSheet("QWidget { background: transparent; }")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        quality_label = QLabel("Signal:")
        quality_label.setStyleSheet(
            "QLabel {"
            "  font-size: 10px;"
            "  font-weight: 600;"
            "  color: #86868B;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        layout.addWidget(quality_label)

        self.signal_quality_pills = {}
        _PILL_LABELS = {
            "A": "#1D1D1F",
            "B": "#FF3B30",
            "C": "#007AFF",
            "D": "#34C759",
        }
        for ch, ch_color in _PILL_LABELS.items():
            pill = QLabel(f"<b style='color:{ch_color};'>{ch}</b> —")
            pill.setTextFormat(Qt.TextFormat.RichText)
            pill.setFixedHeight(18)
            pill.setMinimumWidth(52)
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pill.setStyleSheet(
                "QLabel {"
                "  background: #F2F2F7;"
                "  border-radius: 5px;"
                "  border: 1px solid #E5E5EA;"
                "  padding: 0px 6px;"
                "  font-size: 10px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
            )
            pill.setToolTip(f"Channel {ch}: signal quality — no data yet")
            layout.addWidget(pill)
            self.signal_quality_pills[ch] = pill

        layout.addStretch()
        return bar

    def _show_transmission_spectrum(self):
        """Show the transmission spectrum dialog."""
        if hasattr(self, "app") and self.app:
            self.app.show_transmission_dialog()

    def _on_pipeline_changed(self, index: int):
        """DISABLED - Pipeline selector removed, only Fourier method used."""

    def _update_pipeline_description(self, index: int):
        """DISABLED - Pipeline selector removed."""
        descriptions = {
            "fourier": "Fourier Transform: Uses DST/IDCT for derivative zero-crossing detection. Established method for SPR.",
            "batch_savgol": "Batch Savitzky-Golay (GOLD STANDARD): Hardware averaging + batch processing + SG filtering. Achieves 0.008nm baseline.",
            "direct": "Direct ArgMin: Simplest method, finds minimum in SPR range. Fastest execution, optimal for clean signals.",
            "adaptive": "Adaptive Multi-Feature: Combines multiple detection methods with adaptive weighting. Best for challenging signals.",
            "consensus": "Consensus: Combines 3 methods (centroid, parabolic, fourier) for robust multi-method validation.",
        }

        description = descriptions.get(pipeline_id, "Unknown pipeline selected.")
        self.sidebar.pipeline_description.setText(description)

    def _init_pipeline_selector(self):
        """DISABLED - Pipeline selector removed, only Fourier method used."""

    def _create_cursor_controls(self):
        """Create simplified cursor control panel with Quick Select presets only."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border-radius: 10px;"
            "  padding: 6px;"
            "}",
        )

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(12)

        # Quick Select presets
        presets_label = QLabel("Quick Select:")
        presets_label.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: {Colors.SECONDARY_TEXT};"
            "  font-weight: 500;"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        presets_label.setToolTip("Quickly select common time ranges")
        layout.addWidget(presets_label)

        # Preset buttons
        preset_buttons = [
            ("Last 30s", -30, "Select last 30 seconds"),
            ("Last 1min", -60, "Select last 1 minute"),
            ("Last 5min", -300, "Select last 5 minutes"),
            ("All Data", None, "Select entire timeline"),
        ]

        for label, seconds, tooltip in preset_buttons:
            btn = QPushButton(label)
            btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_MD)
            btn.setToolTip(tooltip)
            btn.setStyleSheet(
                "QPushButton {"
                "  background: #F8F9FA;"
                "  color: {Colors.PRIMARY_TEXT};"
                "  border: none;"
                "  border-radius: 14px;"
                "  font-size: 11px;"
                "  font-weight: 500;"
                "  font-family: {Fonts.SYSTEM};"
                "  padding: 0px 12px;"
                "}"
                "QPushButton:hover {"
                "  background: #E8E9EA;"
                "  border-color: rgba(0, 0, 0, 0.2);"
                "}"
                "QPushButton:pressed {"
                "  background: #D8D9DA;"
                "}",
            )
            if seconds is not None:
                btn.clicked.connect(
                    lambda checked=False, s=seconds: self._select_time_range(s),
                )
            else:
                btn.clicked.connect(self._select_all_data)
            layout.addWidget(btn)

        layout.addStretch()

        # Export selected range button
        export_btn = QPushButton("?? Export Range")
        export_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_MD)
        export_btn.setToolTip("Export data from selected cursor range to CSV")
        export_btn.setStyleSheet(
            "QPushButton {"
            "  background: #007AFF;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 14px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  font-family: {Fonts.SYSTEM};"
            "  padding: 0px 16px;"
            "}"
            "QPushButton:hover {"
            "  background: #0051D5;"
            "}"
            "QPushButton:pressed {"
            "  background: #004BB5;"
            "}",
        )
        export_btn.clicked.connect(self._export_cursor_range)
        layout.addWidget(export_btn)

        return panel

    def _create_separator(self):
        """Create a vertical separator line."""
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Plain)
        separator.setStyleSheet("background: rgba(0, 0, 0, 0.1); max-width: 1px;")
        return separator

    def _select_time_range(self, seconds_from_end):
        """Select time range relative to current end time."""
        if not hasattr(self, "full_timeline_graph"):
            return
        if not hasattr(self.full_timeline_graph, "stop_cursor"):
            return

        try:
            # Get current stop position (latest data)
            stop_time = self.full_timeline_graph.stop_cursor.value()

            # Calculate start time (negative seconds means go back from stop)
            start_time = max(0, stop_time + seconds_from_end)

            # Update cursors
            self.full_timeline_graph.start_cursor.setValue(start_time)
            self.full_timeline_graph.stop_cursor.setValue(stop_time)

            # Update spinboxes
            self._update_cursor_inputs()

            print(
                f"Selected range: {start_time:.1f}s to {stop_time:.1f}s ({abs(seconds_from_end)}s duration)",
            )
        except Exception as e:
            logger.error(f"Error selecting time range: {e}")

    def _select_all_data(self):
        """Select entire timeline from 0 to latest data."""
        if not hasattr(self, "full_timeline_graph"):
            return
        if not hasattr(self.full_timeline_graph, "stop_cursor"):
            return

        try:
            # Set start to 0
            self.full_timeline_graph.start_cursor.setValue(0)

            # Stop stays at current position (latest data)
            stop_time = self.full_timeline_graph.stop_cursor.value()

            # Update spinboxes
            self._update_cursor_inputs()

            logger.debug(f"Selected all data: 0s to {stop_time:.1f}s")
        except Exception as e:
            logger.error(f"Error selecting all data: {e}")

    def _on_start_input_changed(self, value):
        """Update start cursor when spinbox changes."""
        if not hasattr(self, "full_timeline_graph"):
            return
        if not hasattr(self.full_timeline_graph, "start_cursor"):
            return

        # Prevent circular updates
        if hasattr(self, "_updating_cursor_inputs") and self._updating_cursor_inputs:
            return

        try:
            self.full_timeline_graph.start_cursor.setValue(value)
            self._update_duration_label()
        except Exception as e:
            logger.error(f"Error updating start cursor: {e}")

    def _on_stop_input_changed(self, value):
        """Update stop cursor when spinbox changes."""
        if not hasattr(self, "full_timeline_graph"):
            return
        if not hasattr(self.full_timeline_graph, "stop_cursor"):
            return

        # Prevent circular updates
        if hasattr(self, "_updating_cursor_inputs") and self._updating_cursor_inputs:
            return

        try:
            self.full_timeline_graph.stop_cursor.setValue(value)
            self._update_duration_label()
        except Exception as e:
            logger.error(f"Error updating stop cursor: {e}")

    def _update_cursor_inputs(self):
        """Update spinboxes to match cursor positions."""
        if not hasattr(self, "start_time_input") or not hasattr(
            self,
            "stop_time_input",
        ):
            return
        if not hasattr(self, "full_timeline_graph"):
            return

        try:
            self._updating_cursor_inputs = True

            start_val = self.full_timeline_graph.start_cursor.value()
            stop_val = self.full_timeline_graph.stop_cursor.value()

            self.start_time_input.setValue(start_val)
            self.stop_time_input.setValue(stop_val)

            self._update_duration_label()
        except Exception as e:
            logger.error(f"Error updating cursor inputs: {e}")
        finally:
            self._updating_cursor_inputs = False

    def _update_duration_label(self):
        """Update duration label based on cursor positions."""
        if not hasattr(self, "duration_label"):
            return
        if not hasattr(self, "full_timeline_graph"):
            return

        try:
            start = self.full_timeline_graph.start_cursor.value()
            stop = self.full_timeline_graph.stop_cursor.value()
            duration = abs(stop - start)
            self.duration_label.setText(f"({duration:.1f}s)")
        except Exception:
            pass

    def _export_cursor_range(self):
        """Export data from selected cursor range to CSV."""
        if not hasattr(self, "app") or not self.app:
            logger.warning("Application not initialized")
            return

        try:
            start_time = self.full_timeline_graph.start_cursor.value()
            stop_time = self.full_timeline_graph.stop_cursor.value()

            # Forward to application's export cycle method
            if hasattr(self.app, "export_cycle_data"):
                self.app.export_cycle_data()
                logger.debug(f"Exporting range: {start_time:.1f}s to {stop_time:.1f}s")
            else:
                logger.warning("Export function not available")
        except Exception as e:
            logger.error(f"Error exporting cursor range: {e}")

    def _on_cursor_dragged(self, evt):
        """Handle cursor being dragged - update inputs in real-time."""
        self._update_cursor_inputs()

    def _on_cursor_moved(self, evt):
        """Handle cursor movement finished - update inputs and apply snap if enabled."""
        # Apply snap to data if enabled
        if hasattr(self, "snap_checkbox") and self.snap_checkbox.isChecked():
            self._apply_snap_to_data(evt)

        self._update_cursor_inputs()

    def _apply_snap_to_data(self, cursor):
        """Snap cursor to nearest data point timestamp."""
        if not hasattr(self, "app") or not self.app:
            return
        if not hasattr(self.app, "buffer_mgr"):
            return

        try:
            import numpy as np

            # Get cursor position (in DISPLAY coordinates)
            cursor_time = cursor.value()

            # Find nearest timestamp from any channel with data
            nearest_time = cursor_time
            min_distance = float("inf")

            for ch in ["a", "b", "c", "d"]:
                time_data = self.app.buffer_mgr.timeline_data[ch].time  # RAW_ELAPSED coordinates
                if len(time_data) > 0:
                    timestamps = np.array(time_data)
                    # Convert RAW_ELAPSED to DISPLAY coordinates for proper comparison
                    timestamps_display = timestamps - self.app.clock.display_offset
                    idx = np.argmin(np.abs(timestamps_display - cursor_time))
                    if idx < len(timestamps_display):
                        candidate = timestamps_display[idx]
                        distance = abs(candidate - cursor_time)
                        if distance < min_distance:
                            min_distance = distance
                            nearest_time = candidate

            # Snap to nearest (only if within 10% of viewport)
            if min_distance < float("inf"):
                cursor.setValue(float(nearest_time))
        except Exception as e:
            logger.error(f"Error applying snap: {e}")

    def _toggle_live_data(self, enabled: bool) -> None:
        """Toggle live data updates for graphs."""
        # Delegate to presenter for consistent behavior
        if hasattr(self, "sensogram_presenter"):
            self.sensogram_presenter.set_live_data_enabled(enabled)
        else:
            self.live_data_enabled = enabled
            if enabled:
                logger.debug("Live data updates enabled")
            else:
                logger.debug("Live data updates disabled - graph frozen")

    def _position_active_cycle_legend(self, plot_widget):
        """Position the interactive SPR legend inside the Active Cycle plot_widget."""
        legend = getattr(plot_widget, 'interactive_spr_legend', None)
        if legend is None:
            return
        legend.adjustSize()
        # Left axis ≈ 55px wide; sit just inside the data area at top-left
        legend.move(62, 10)
        legend.raise_()

    def _position_cycle_status_overlay(self, plot_widget):
        """Position the cycle status overlay inside the Active Cycle plot_widget (top-right)."""
        overlay = getattr(plot_widget, 'cycle_status_overlay', None)
        if overlay is None:
            return
        overlay.adjustSize()
        # Right edge: widget width minus overlay width minus ~10px right margin
        x = max(62, plot_widget.width() - overlay.width() - 10)
        overlay.move(x, 10)
        overlay.raise_()

    def _toggle_channel_visibility(self, channel, visible):
        """Toggle visibility of a channel on both graphs."""
        if hasattr(self, "sensogram_presenter"):
            self.sensogram_presenter.toggle_channel_visibility(channel, visible)
            return
        # Fallback (should not be used once presenter is available)
        channel_idx = {"A": 0, "B": 1, "C": 2, "D": 3}.get(channel)
        if channel_idx is None:
            return
        if hasattr(self, "full_timeline_graph") and channel_idx < len(
            self.full_timeline_graph.curves,
        ):
            (
                self.full_timeline_graph.curves[channel_idx].show()
                if visible
                else self.full_timeline_graph.curves[channel_idx].hide()
            )
        if hasattr(self, "cycle_of_interest_graph") and channel_idx < len(
            self.cycle_of_interest_graph.curves,
        ):
            (
                self.cycle_of_interest_graph.curves[channel_idx].show()
                if visible
                else self.cycle_of_interest_graph.curves[channel_idx].hide()
            )

    def _on_clear_graph_clicked(self):
        """Handle Clear Graph button click - call app's clear handler directly."""
        if hasattr(self, "app") and self.app:
            # Call the main clear handler directly (same as DataWindow signal does)
            if hasattr(self.app, '_on_clear_graphs_requested'):
                self.app._on_clear_graphs_requested()

    def _hex_to_rgb(self, hex_color: str) -> tuple:
        """Convert hex color string to RGB tuple.

        Args:
            hex_color: Hex color string (e.g., "#FF0000")

        Returns:
            tuple: RGB values (0-255) as (r, g, b)
        """
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def _get_delta_spr_display_text(self, delta_values: dict = None) -> str:
        """Generate color-coded delta SPR display text (stacked vertically for better visibility).

        Args:
            delta_values: Dict with keys 'a', 'b', 'c', 'd' containing RU values
                         If None, uses 0.0 for all channels

        Returns:
            HTML-formatted string with color-coded channel labels (no units in values)
        """
        from affilabs.plot_helpers import CHANNEL_COLORS, CHANNEL_COLORS_COLORBLIND

        # Use default values if not provided
        if delta_values is None:
            delta_values = {'a': 0.0, 'b': 0.0, 'c': 0.0, 'd': 0.0}

        # Get colors based on colorblind mode
        colorblind_enabled = False
        if hasattr(self, 'colorblind_check') and self.colorblind_check:
            colorblind_enabled = self.colorblind_check.isChecked()

        colors = CHANNEL_COLORS_COLORBLIND if colorblind_enabled else CHANNEL_COLORS

        # Build channel displays (vertical stack for better visibility)
        channel_parts = []
        for i, ch in enumerate(['a', 'b', 'c', 'd']):
            ch_upper = ch.upper()
            channel_parts.append(
                f"<div style='margin: 3px 0; padding: 2px 0;'>"
                f"<b style='color: {colors[i]}; font-size: 13px;'>{ch_upper}:</b> "
                f"<span style='color: {colors[i]}; font-size: 16px; font-weight: 700;'>{delta_values[ch]:.1f}</span>"
                f"</div>"
            )

        return f"<b style='font-size: 12px;'>Δ SPR (RU)</b><br>{''.join(channel_parts)}"

    def _clear_cycle_markers(self):
        """Clear all flags from the Active Cycle graph and markers from Full Sensorgram timeline."""
        try:
            logger.info("🧹 Clear Flags button clicked")

            # Clear flags from Active Cycle (bottom) graph via flag manager
            if hasattr(self.app, 'flag_mgr') and self.app.flag_mgr:
                self.app.flag_mgr.clear_all_flags()
                logger.info("✅ Cleared all flags from Active Cycle graph")

            # Also clear cycle markers from Full Sensorgram (top) graph
            if not hasattr(self, "full_timeline_graph"):
                logger.warning("? Full timeline graph not found")
                return

            if not hasattr(self, "app") or not self.app:
                logger.warning("? App reference not found - cannot clear markers")
                return

            # Get reference to app's cycle markers
            if not hasattr(self.app, "_cycle_markers"):
                logger.warning("?? No _cycle_markers attribute on app")
                return

            if not self.app._cycle_markers:
                logger.info("ℹ️ No cycle markers to clear (dictionary is empty)")
                return

            timeline = self.full_timeline_graph
            markers_cleared = 0

            logger.debug(f"Found {len(self.app._cycle_markers)} cycle markers to remove")

            # Remove all cycle markers from timeline
            for cycle_id, marker_data in list(self.app._cycle_markers.items()):
                try:
                    # Remove vertical line
                    if 'line' in marker_data and marker_data['line'] is not None:
                        timeline.removeItem(marker_data['line'])
                        markers_cleared += 1

                    # Remove text label
                    if 'label' in marker_data and marker_data['label'] is not None:
                        timeline.removeItem(marker_data['label'])
                except Exception as e:
                    logger.debug(f"Error removing marker {cycle_id}: {e}")

            # Clear the markers dictionary
            self.app._cycle_markers.clear()

            logger.info(f"✅ Cleared {markers_cleared} cycle markers from Full Sensorgram timeline")
            print("✅ Cleared all flags and cycle markers")

            # Update flag counter
            self._update_flag_counter()

            # Refresh the Active Cycle display to show updated timing (removes alignment line)
            if hasattr(self.app, '_refresh_active_cycle_display'):
                self.app._refresh_active_cycle_display()

        except Exception as e:
            logger.error(f"❌ Error clearing flags/markers: {e}")
            print(f"❌ Error clearing flags/markers: {e}")

    def _reset_channel_timing(self):
        """Reset all channel time shifts to default (remove injection alignment)."""
        try:
            logger.info("🔄 Reset Timing button clicked")

            if not hasattr(self, "app") or not self.app:
                logger.warning("❌ App reference not found")
                return

            # Clear channel time shifts
            if hasattr(self.app, '_channel_time_shifts'):
                self.app._channel_time_shifts = {'a': 0.0, 'b': 0.0, 'c': 0.0, 'd': 0.0}
                logger.info("✅ Reset all channel time shifts to 0.0")

            # Hide shift indicator label
            if hasattr(self, 'channel_shift_label'):
                self.channel_shift_label.setVisible(False)

            # Refresh the Active Cycle display to show updated timing
            if hasattr(self.app, '_update_cycle_of_interest_graph'):
                self.app._update_cycle_of_interest_graph()
            elif hasattr(self.app, '_refresh_active_cycle_display'):
                self.app._refresh_active_cycle_display()

            print("✅ Channel timing reset to default")
            logger.info("✅ Channel timing reset complete")

        except Exception as e:
            logger.error(f"❌ Error resetting channel timing: {e}")
            print(f"❌ Error resetting timing: {e}")

    # -- Cycle Notes Popup ----------------------------------------------

    def _open_cycle_notes_popup(self):
        """Open a floating popup to add/edit notes for the currently running cycle."""
        # Close existing popup if open
        if hasattr(self, '_notes_popup') and self._notes_popup is not None:
            self._notes_popup.close()
            self._notes_popup = None
            return

        # Get current note text from the running cycle
        current_note = ""
        if hasattr(self, 'app') and self.app:
            cycle = getattr(self.app, '_current_cycle', None)
            if cycle is not None:
                current_note = getattr(cycle, 'note', "") or ""
            elif hasattr(self.app, '_current_running_cycle') and self.app._current_running_cycle:
                current_note = self.app._current_running_cycle.get("notes", "") or ""

        # Build popup frame
        popup = QFrame(self, Qt.WindowType.Popup)
        popup.setFixedWidth(320)
        popup.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: 1px solid #D1D1D6;"
            "  border-radius: 10px;"
            "}"
        )
        popup.setGraphicsEffect(create_card_shadow())

        layout = QVBoxLayout(popup)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Header row
        header_row = QHBoxLayout()
        title = QLabel("Cycle Notes")
        title.setStyleSheet(
            f"font-size: 13px; font-weight: {Fonts.WEIGHT_SEMIBOLD}; "
            f"color: {Colors.PRIMARY_TEXT}; background: transparent; border: none;"
        )
        header_row.addWidget(title)
        header_row.addStretch()

        close_btn = QPushButton("?")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; font-size: 13px; "
            f"color: {Colors.SECONDARY_TEXT}; border-radius: 4px; }}"
            "QPushButton:hover { background: rgba(0,0,0,0.06); }"
        )
        close_btn.clicked.connect(popup.close)
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        # Text input
        from PySide6.QtWidgets import QPlainTextEdit
        text_edit = QPlainTextEdit()
        text_edit.setPlainText(current_note)
        text_edit.setPlaceholderText("e.g. Bubble on Ch A, sample looked cloudy...")
        text_edit.setMaximumHeight(80)
        text_edit.setStyleSheet(
            "QPlainTextEdit {"
            "  background: #F9F9F9;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "  padding: 6px 8px;"
            "  font-size: 12px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            "}"
            "QPlainTextEdit:focus {"
            "  border: 1.5px solid #007AFF;"
            "}"
        )
        layout.addWidget(text_edit)

        # Bottom row: char counter + save button
        bottom_row = QHBoxLayout()
        char_label = QLabel(f"{len(current_note)}/250")
        char_label.setStyleSheet(
            f"font-size: 12px; color: {Colors.SECONDARY_TEXT}; "
            f"background: transparent; border: none;"
        )
        bottom_row.addWidget(char_label)
        bottom_row.addStretch()

        save_btn = QPushButton("Save")
        save_btn.setFixedHeight(26)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(
            "QPushButton {"
            "  background: #007AFF; color: white; border: none; border-radius: 6px;"
            "  padding: 0px 16px; font-size: 12px; font-weight: 600;"
            "}"
            "QPushButton:hover { background: #0066DD; }"
            "QPushButton:pressed { background: #0055BB; }"
        )
        bottom_row.addWidget(save_btn)
        layout.addLayout(bottom_row)

        # Wire up char counter with 250 limit
        def _on_text_changed():
            text = text_edit.toPlainText()
            if len(text) > 250:
                text_edit.setPlainText(text[:250])
                cursor = text_edit.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                text_edit.setTextCursor(cursor)
            char_label.setText(f"{len(text_edit.toPlainText())}/250")

        text_edit.textChanged.connect(_on_text_changed)

        # Wire save
        def _save_note():
            note_text = text_edit.toPlainText().strip()
            self._save_cycle_note(note_text)
            popup.close()

        save_btn.clicked.connect(_save_note)

        # Position popup above the note button
        btn_pos = self.cycle_note_btn.mapToGlobal(self.cycle_note_btn.rect().topLeft())
        popup.adjustSize()
        popup.move(btn_pos.x(), btn_pos.y() - popup.height() - 6)

        # Track and show
        self._notes_popup = popup
        popup.destroyed.connect(lambda: setattr(self, '_notes_popup', None))
        popup.show()
        text_edit.setFocus()

    def _save_cycle_note(self, note_text: str):
        """Save note text to the currently running cycle and update UI.

        Args:
            note_text: The note content to save
        """
        if not hasattr(self, 'app') or not self.app:
            return

        saved = False

        # Save to Cycle domain object if available
        cycle = getattr(self.app, '_current_cycle', None)
        if cycle is not None and hasattr(cycle, 'note'):
            cycle.note = note_text
            saved = True
            logger.info(f"Saved cycle note to domain object: {note_text[:50]}...")

        # Save to running cycle dict (legacy path)
        if hasattr(self.app, '_current_running_cycle') and self.app._current_running_cycle:
            self.app._current_running_cycle["notes"] = note_text
            saved = True

        if saved:
            # Update button appearance
            self._update_cycle_note_button(bool(note_text))

            # Refresh queue summary widget if it shows notes
            if hasattr(self.app, 'main_window') and hasattr(self.app.main_window, 'queue_summary'):
                try:
                    self.app.main_window.queue_summary._refresh_display()
                except Exception:
                    pass
            elif hasattr(self, 'queue_summary'):
                try:
                    self.queue_summary._refresh_display()
                except Exception:
                    pass

            logger.info(f"Cycle note saved: '{note_text[:60]}{'...' if len(note_text) > 60 else ''}'")
        else:
            logger.warning("No active cycle to save note to")

    def _update_cycle_note_button(self, has_note: bool, visible: bool = True):
        """Update the Note button appearance and visibility.

        Args:
            has_note: True if the current cycle has a non-empty note
            visible: True to show the button (cycle running), False to hide (no active cycle)
        """
        if not hasattr(self, 'cycle_note_btn'):
            return

        self.cycle_note_btn.setVisible(visible)
        self._cycle_note_has_content = has_note

        if has_note:
            # Blue tint when note exists
            self.cycle_note_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0,122,255,0.15);"
                "  border: none;"
                "  border-radius: 6px;"
                "  padding: 0px;"
                "}"
                "QPushButton:hover { background: rgba(0,122,255,0.25); }"
                "QPushButton:pressed { background: rgba(0,122,255,0.35); }"
            )
        else:
            self.cycle_note_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0,0,0,0.05);"
                "  border: none;"
                "  border-radius: 6px;"
                "  padding: 0px;"
                "}"
                "QPushButton:hover { background: rgba(0,0,0,0.10); }"
                "QPushButton:pressed { background: rgba(0,0,0,0.18); }"
            )

    def _close_cycle_notes_popup(self):
        """Close the notes popup if open."""
        if hasattr(self, '_notes_popup') and self._notes_popup is not None:
            self._notes_popup.close()
            self._notes_popup = None

    def _update_flag_counter(self):
        """Update the flag counter label with current number of flags from FlagManager."""
        try:
            if not hasattr(self, 'flag_counter_label'):
                return

            # Count live flags from FlagManager (unified source of truth)
            flag_count = 0
            if hasattr(self, 'app') and hasattr(self.app, 'flag_mgr') and self.app.flag_mgr:
                flag_count = len(self.app.flag_mgr.get_live_flags())

            # Update label text
            self.flag_counter_label.setText(f"Flags: {flag_count}")

            # Change color based on flag count
            if flag_count == 0:
                color = "#86868B"  # Gray when no flags
            else:
                color = "#007AFF"  # Blue when flags exist

            self.flag_counter_label.setStyleSheet(
                f"QLabel {{ "
                f"  font-size: 11px; "
                f"  color: {color}; "
                f"  padding: 4px 8px; "
                f"  font-weight: {600 if flag_count > 0 else 400}; "
                f"  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif; "
                f"}}"
            )

        except Exception as e:
            logger.debug(f"Error updating flag counter: {e}")

    def _on_colorblind_mode_changed(self, enabled: bool):
        """Update button colors and curve colors when colorblind mode is toggled."""
        from affilabs.ui_styles import get_channel_button_style
        from affilabs.plot_helpers import CHANNEL_COLORS, CHANNEL_COLORS_COLORBLIND
        from affilabs.settings import settings as _settings

        # Select color palette based on mode
        colors = CHANNEL_COLORS_COLORBLIND if enabled else CHANNEL_COLORS

        # Keep settings.ACTIVE_GRAPH_COLORS in sync so update_colors() reads correct palette
        _ch_keys = ['a', 'b', 'c', 'd']
        for i, ch in enumerate(_ch_keys):
            _settings.ACTIVE_GRAPH_COLORS[ch] = colors[i]

        # Refresh legend value label colors to match new palette
        if hasattr(self, 'cycle_of_interest_graph'):
            legend = getattr(self.cycle_of_interest_graph, 'interactive_spr_legend', None)
            if legend is not None:
                legend.update_colors()

        # Update channel visibility toggle buttons
        if hasattr(self, 'channel_toggles'):
            for i, (ch, btn) in enumerate(self.channel_toggles.items()):
                btn.setStyleSheet(get_channel_button_style(colors[i]))
                btn.setProperty("channel_color", colors[i])

        # Redraw curves via update_colors() — reads ACTIVE_GRAPH_COLORS set above
        if hasattr(self, 'full_timeline_graph') and hasattr(self.full_timeline_graph, 'update_colors'):
            self.full_timeline_graph.update_colors()
        if hasattr(self, 'cycle_of_interest_graph') and hasattr(self.cycle_of_interest_graph, 'update_colors'):
            self.cycle_of_interest_graph.update_colors()

        # Update Edits tab bar chart colors
        if hasattr(self, 'edits_tab') and hasattr(self.edits_tab, 'update_barchart_colors'):
            self.edits_tab.update_barchart_colors(hex_colors=colors)

        # Propagate to DataWindow graphs and buttons
        self._propagate_to_datawindow_graphs()

        # Refresh interactive SPR legend colors
        if hasattr(self, 'cycle_of_interest_graph'):
            legend = getattr(self.cycle_of_interest_graph, 'interactive_spr_legend', None)
            if legend is not None and legend.isVisible():
                legend.update_colors()

    def _propagate_to_datawindow_graphs(self) -> None:
        """Call update_colors() on all live DataWindow SegmentGraphs and header buttons."""
        try:
            from affilabs.widgets.datawindow import DataWindow
            from affilabs.ui_styles import get_channel_button_style, get_channel_button_ref_style
            from affilabs.settings import settings as _settings
            _ch_keys = ['A', 'B', 'C', 'D']
            for dw in self.findChildren(DataWindow):
                soi = getattr(dw, 'SOI_view', None)
                if soi and hasattr(soi, 'update_colors'):
                    soi.update_colors()
                sg = getattr(dw, 'sensorgram_graph', None)
                if sg and hasattr(sg, 'update_colors'):
                    sg.update_colors()
                # Update soi_frame header channel toggle button colours
                soi_frame = getattr(dw, 'soi_frame', None)
                if soi_frame and soi_frame.channel_toggles:
                    ref_id = soi_frame.reference_channel_id
                    for i, ch in enumerate(_ch_keys):
                        btn = soi_frame.channel_toggles.get(ch)
                        if btn is None:
                            continue
                        color = _settings.ACTIVE_GRAPH_COLORS.get(ch.lower(), '#1D1D1F')
                        btn.setProperty("channel_color", color)
                        if ref_id and ch.lower() == ref_id:
                            btn.setStyleSheet(get_channel_button_ref_style(color))
                        else:
                            btn.setStyleSheet(get_channel_button_style(color))
        except Exception:
            pass

    def _propagate_line_style_to_datawindow_graphs(self, pen_style) -> None:
        """Call update_line_style() on all live DataWindow graphs."""
        try:
            from affilabs.widgets.datawindow import DataWindow
            for dw in self.findChildren(DataWindow):
                soi = getattr(dw, 'SOI_view', None)
                if soi and hasattr(soi, 'update_line_style'):
                    soi.update_line_style(pen_style)
                sg = getattr(dw, 'sensorgram_graph', None)
                if sg and hasattr(sg, 'update_line_style'):
                    sg.update_line_style(pen_style)
        except Exception:
            pass

    def _propagate_to_analysis_tab(self, hex_colors: list | None = None,
                                   pen_style=None) -> None:
        """Update analysis_tab overlay curves with current palette / line style."""
        try:
            from PySide6.QtCore import Qt
            import pyqtgraph as pg
            # Find any AnalysisTab instance
            from affilabs.tabs.analysis_tab import AnalysisTab
            for tab in self.findChildren(AnalysisTab):
                curves = getattr(tab, 'overlay_graph_curves', [])
                _ch_keys = ['a', 'b', 'c', 'd']
                from affilabs.settings import settings as _settings
                for i, curve in enumerate(curves):
                    color = hex_colors[i] if hex_colors else _settings.ACTIVE_GRAPH_COLORS.get(
                        _ch_keys[i], "#1D1D1F")
                    if isinstance(color, str) and color.startswith('#'):
                        color = self._hex_to_rgb(color)
                    style = pen_style if pen_style is not None else Qt.PenStyle(
                        _settings.ACTIVE_LINE_STYLE)
                    curve.setPen(pg.mkPen(color=color, width=2, style=style))
        except Exception:
            pass

    def _on_palette_changed(self, palette_id: str, hex_colors: list) -> None:
        """Apply a new colour palette from the Accessibility panel to all sensorgram curves."""
        from affilabs.ui_styles import get_channel_button_style
        from affilabs.settings import settings as _settings
        from PySide6.QtCore import Qt
        import pyqtgraph as pg

        _ch_keys = ['a', 'b', 'c', 'd']
        pen_style = Qt.PenStyle(_settings.ACTIVE_LINE_STYLE)

        # Update ACTIVE_GRAPH_COLORS so all future renders pick up new colours
        for i, ch in enumerate(_ch_keys):
            _settings.ACTIVE_GRAPH_COLORS[ch] = hex_colors[i]

        channel_colors_rgb = [self._hex_to_rgb(c) for c in hex_colors]

        # Update channel toggle button borders
        if hasattr(self, 'channel_toggles'):
            for i, (ch, btn) in enumerate(self.channel_toggles.items()):
                btn.setStyleSheet(get_channel_button_style(hex_colors[i]))
                btn.setProperty("channel_color", hex_colors[i])

        # Update Full Timeline (Live Sensorgram) curves
        if hasattr(self, 'full_timeline_graph') and hasattr(self.full_timeline_graph, 'curves'):
            for i, curve in enumerate(self.full_timeline_graph.curves):
                curve.setPen(pg.mkPen(color=channel_colors_rgb[i], width=2, style=pen_style))

        # Update Active Cycle graph curves (skip if dark mode active — neon takes precedence)
        _dark_on = getattr(self, 'accessibility_panel', None) and self.accessibility_panel.is_dark_mode()
        if not _dark_on and hasattr(self, 'cycle_of_interest_graph') and hasattr(self.cycle_of_interest_graph, 'curves'):
            selected_channel = getattr(self, 'selected_channel_for_timing', None)
            for i, curve in enumerate(self.cycle_of_interest_graph.curves):
                width = 4 if selected_channel == i else 2
                curve.setPen(pg.mkPen(color=channel_colors_rgb[i], width=width, style=pen_style))

        # Refresh legend
        if hasattr(self, 'cycle_of_interest_graph'):
            legend = getattr(self.cycle_of_interest_graph, 'interactive_spr_legend', None)
            if legend is not None and legend.isVisible():
                legend.update_colors()

        # Update Edits tab first — fast setPen calls, should paint before findChildren walks
        if hasattr(self, 'edits_tab') and hasattr(self.edits_tab, 'update_barchart_colors'):
            self.edits_tab.update_barchart_colors(hex_colors=hex_colors)

        # Propagate to DataWindow graphs and analysis tab (slower — findChildren walk)
        self._propagate_to_datawindow_graphs()
        self._propagate_to_analysis_tab(hex_colors=hex_colors)

    def _on_line_style_changed(self, style_id: str, pen_style) -> None:
        """Apply a new line style from the Accessibility panel to all sensorgram curves."""
        import pyqtgraph as pg
        from affilabs.settings import settings as _settings

        # Persist so graphs initialised later pick up the style
        _settings.ACTIVE_LINE_STYLE = pen_style.value if hasattr(pen_style, 'value') else int(pen_style)

        _ch_keys = ['a', 'b', 'c', 'd']

        def _color_for(i):
            ch = _ch_keys[i]
            c = _settings.ACTIVE_GRAPH_COLORS.get(ch, "#1D1D1F")
            if isinstance(c, str) and c.startswith('#'):
                return self._hex_to_rgb(c)
            return c

        # Update Full Timeline curves
        if hasattr(self, 'full_timeline_graph') and hasattr(self.full_timeline_graph, 'curves'):
            for i, curve in enumerate(self.full_timeline_graph.curves):
                curve.setPen(pg.mkPen(color=_color_for(i), width=2, style=pen_style))

        # Update Active Cycle curves (use neon colours if dark mode active)
        if hasattr(self, 'cycle_of_interest_graph') and hasattr(self.cycle_of_interest_graph, 'curves'):
            _dark_on = getattr(self, 'accessibility_panel', None) and self.accessibility_panel.is_dark_mode()
            selected_channel = getattr(self, 'selected_channel_for_timing', None)
            for i, curve in enumerate(self.cycle_of_interest_graph.curves):
                width = 4 if selected_channel == i else 2
                color = self._NEON_COLORS[i] if _dark_on else _color_for(i)
                curve.setPen(pg.mkPen(color=color, width=width, style=pen_style))

        # Propagate to DataWindow graphs and analysis tab
        self._propagate_line_style_to_datawindow_graphs(pen_style)
        self._propagate_to_analysis_tab(pen_style=pen_style)

    # Neon palette for Active Cycle dark mode
    _NEON_COLORS = [
        "#00FF41",  # A: matrix green
        "#FF3B30",  # B: neon red
        "#00C8FF",  # C: electric cyan
        "#FFD60A",  # D: neon yellow
    ]

    def _on_dark_mode_toggled(self, enabled: bool) -> None:
        """Toggle Active Cycle graph between dark (black bg, neon lines) and light."""
        import pyqtgraph as pg
        from PySide6.QtGui import QColor
        from affilabs.settings import settings as _settings
        from PySide6.QtCore import Qt

        graph = getattr(self, 'cycle_of_interest_graph', None)
        if graph is None:
            return

        pen_style = Qt.PenStyle(_settings.ACTIVE_LINE_STYLE)

        if enabled:
            graph.setBackground(QColor("#0D0D0D"))
            # Neon axis/grid colours
            graph.getPlotItem().getAxis('left').setPen(pg.mkPen('#444444'))
            graph.getPlotItem().getAxis('bottom').setPen(pg.mkPen('#444444'))
            graph.getPlotItem().getAxis('left').setTextPen(pg.mkPen('#888888'))
            graph.getPlotItem().getAxis('bottom').setTextPen(pg.mkPen('#888888'))
            # Neon curves
            selected = getattr(self, 'selected_channel_for_timing', None)
            for i, curve in enumerate(graph.curves):
                width = 4 if selected == i else 2
                curve.setPen(pg.mkPen(color=self._NEON_COLORS[i], width=width,
                                      style=pen_style))
        else:
            graph.setBackground(QColor("#FFFFFF"))
            graph.getPlotItem().getAxis('left').setPen(pg.mkPen('#000000'))
            graph.getPlotItem().getAxis('bottom').setPen(pg.mkPen('#000000'))
            graph.getPlotItem().getAxis('left').setTextPen(pg.mkPen('#000000'))
            graph.getPlotItem().getAxis('bottom').setTextPen(pg.mkPen('#000000'))
            # Restore palette colours
            selected = getattr(self, 'selected_channel_for_timing', None)
            _ch_keys = ['a', 'b', 'c', 'd']
            for i, curve in enumerate(graph.curves):
                c = _settings.ACTIVE_GRAPH_COLORS.get(_ch_keys[i], "#1D1D1F")
                if isinstance(c, str) and c.startswith('#'):
                    c = self._hex_to_rgb(c)
                width = 4 if selected == i else 2
                curve.setPen(pg.mkPen(color=c, width=width, style=pen_style))

    def _toggle_sidebar_collapse(self, collapsed: bool):
        """Collapse left sidebar to icon strip only, or restore to full width."""
        sizes = self.splitter.sizes()
        _ICON_STRIP = 50  # width that shows just the tab bar icons
        if collapsed:
            self._sidebar_saved_width = sizes[0] if sizes[0] > _ICON_STRIP else 380
            self.splitter.setSizes([_ICON_STRIP, sizes[0] + sizes[1] - _ICON_STRIP, sizes[2]])
        else:
            w = getattr(self, '_sidebar_saved_width', 380)
            total = sizes[0] + sizes[1] + sizes[2]
            self.splitter.setSizes([w, total - w - sizes[2], sizes[2]])

    def _build_queue_right_panel(self) -> "QFrame":
        """Build the collapsible right Run Queue panel.

        The panel is a QFrame styled to match the app surface. Its content
        area is stored as self._queue_content_layout so the queue widget can
        be inserted after the sidebar finishes building.
        """
        from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

        panel = QFrame()
        panel.setObjectName("rightQueuePanel")
        panel.setMinimumWidth(0)
        panel.setMaximumWidth(560)
        panel.setStyleSheet(
            "QFrame#rightQueuePanel {"
            "  background: #F5F5F7;"
            "  border-left: 1px solid #E5E5EA;"
            "}"
        )
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── header strip ────────────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(52)
        header.setStyleSheet(
            "QFrame { background: #FFFFFF; border-bottom: 2px solid #E0E0E5; }"
        )
        hdr_row = QHBoxLayout(header)
        hdr_row.setContentsMargins(16, 0, 14, 0)
        title_lbl = QLabel("Run Experiment")
        title_lbl.setStyleSheet(
            "font-size: 16px; font-weight: 700; color: #1D1D1F; background: transparent;"
            "font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "letter-spacing: -0.4px;"
        )
        hdr_row.addWidget(title_lbl)
        hdr_row.addStretch()

        # Clear Queue button in header
        self._clear_queue_hdr_btn = QPushButton("Clear")
        self._clear_queue_hdr_btn.setFixedHeight(24)
        self._clear_queue_hdr_btn.setToolTip("Remove all cycles from the queue")
        self._clear_queue_hdr_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #FF3B30;"
            " border: 1px solid rgba(255,59,48,0.35); border-radius: 5px;"
            " padding: 0 8px; font-size: 11px; font-weight: 600; }"
            " QPushButton:hover { background: rgba(255,59,48,0.08); }"
            " QPushButton:pressed { background: rgba(255,59,48,0.16); }"
        )
        self._clear_queue_hdr_btn.clicked.connect(self._on_clear_queue)
        hdr_row.addWidget(self._clear_queue_hdr_btn)

        outer.addWidget(header)

        # ── queue section subtitle ───────────────────────────────────────
        queue_section = QFrame()
        queue_section.setStyleSheet(
            "QFrame { background: transparent; border: none;"
            " border-bottom: 1px solid #E5E5EA; }"
        )
        queue_section_row = QHBoxLayout(queue_section)
        queue_section_row.setContentsMargins(16, 8, 14, 8)
        self._queue_section_lbl = QLabel("Cycle Queue")
        self._queue_section_lbl.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #8E8E93;"
            " font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            " background: transparent; border: none; letter-spacing: 0px;"
        )
        queue_section_row.addWidget(self._queue_section_lbl)
        queue_section_row.addStretch()

        # Collapse/expand toggle state — starts expanded
        self._queue_table_collapsed = False

        outer.addWidget(queue_section)

        # ── content area (queue widget inserted here after sidebar builds) ──
        self._queue_content_layout = outer
        return panel

    def _on_toggle_queue_table_collapse(self) -> None:
        """Toggle the cycle queue table between full view and single-row (running only)."""
        self._queue_table_collapsed = not self._queue_table_collapsed
        try:
            self.sidebar.summary_table.set_collapsed(self._queue_table_collapsed)
        except Exception:
            pass

    def _on_toggle_queue_panel(self, checked: bool) -> None:
        """Handle queue toggle pill in transport bar — show or hide run queue panel."""
        if checked:
            self.expand_queue_panel()
        else:
            self.collapse_queue_panel()

    def _sync_queue_toggle_btn(self, checked: bool) -> None:
        """Sync the Live Sensorgram queue toggle button without re-triggering the signal."""
        try:
            btn = self._live_queue_btn
            btn.blockSignals(True)
            btn.setChecked(checked)
            btn.blockSignals(False)
        except Exception:
            pass

    def expand_queue_panel(self, width: int = 320) -> None:
        """Expand the right run-queue panel (called when acquisition starts)."""
        try:
            sizes = self.splitter.sizes()
            total = sum(sizes)
            left = sizes[0]
            center = max(400, total - left - width)
            self.splitter.setSizes([left, center, width])
            self._sync_queue_toggle_btn(True)
        except Exception as e:
            logger.debug(f"expand_queue_panel: {e}")

    def collapse_queue_panel(self) -> None:
        """Collapse the right run-queue panel (called when acquisition stops)."""
        try:
            sizes = self.splitter.sizes()
            total = sum(sizes)
            left = sizes[0]
            self.splitter.setSizes([left, total - left, 0])
            self._sync_queue_toggle_btn(False)
        except Exception as e:
            logger.debug(f"collapse_queue_panel: {e}")

    def expand_sidebar(self, width: int = 380) -> None:
        """Expand the left sidebar (called when icon rail tab is clicked)."""
        try:
            sizes = self.splitter.sizes()
            if sizes[0] >= width:
                return  # Already expanded
            total = sum(sizes)
            right = sizes[2]
            center = max(400, total - width - right)
            self.splitter.setSizes([width, center, right])
        except Exception as e:
            logger.debug(f"expand_sidebar: {e}")

    def collapse_sidebar(self) -> None:
        """Collapse the left sidebar to 0px (called when icon rail tab is clicked again)."""
        try:
            sizes = self.splitter.sizes()
            if sizes[0] == 0:
                return  # Already collapsed
            total = sum(sizes)
            right = sizes[2]
            self.splitter.setSizes([0, total - right, right])
        except Exception as e:
            logger.debug(f"collapse_sidebar: {e}")

    def is_sidebar_collapsed(self) -> bool:
        """Check if sidebar is currently collapsed."""
        try:
            return self.splitter.sizes()[0] == 0
        except Exception:
            return True

    def eventFilter(self, obj, event) -> bool:
        """Intercept Ctrl+click on channel toggle buttons to set/clear reference."""
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
            and obj.property("channel_letter") is not None
        ):
            self._on_channel_ref_ctrl_click(obj)
            return True  # Consume — don't toggle the button's checked state
        return super().eventFilter(obj, event)

    def _on_channel_ref_ctrl_click(self, btn: "QPushButton") -> None:
        """Ctrl+click on a channel button — toggle it as the reference channel."""
        ch_letter = btn.property("channel_letter")
        current_ref = getattr(self.app, "_reference_channel", None)

        # Toggle: Ctrl+click the current ref clears it; any other channel sets it
        new_ref = None if ch_letter == current_ref else ch_letter

        # Apply visual immediately — don't wait for coordinator round-trip
        self.app._reference_channel = new_ref
        self._update_channel_btn_ref_styles(new_ref)

        # Sync the combo box in Settings / Graphic Control sidebars
        combo_text = {None: "None", "a": "Channel A", "b": "Channel B", "c": "Channel C", "d": "Channel D"}
        for combo_attr in ("ref_combo",):
            combo = getattr(getattr(self, "sidebar", None), combo_attr, None)
            if combo is not None:
                combo.blockSignals(True)
                combo.setCurrentText(combo_text.get(new_ref, "None"))
                combo.blockSignals(False)

        # Notify coordinator for graph update (wrapped so a missing graph doesn't abort)
        coordinator = getattr(self.app, "ui_control_coordinator", None)
        if coordinator is not None:
            try:
                coordinator.set_reference_channel(new_ref)
            except Exception:
                pass

    def _update_channel_btn_ref_styles(self, ref_letter: "str | None") -> None:
        """Apply dashed border to the reference channel button; restore others."""
        from affilabs.ui_styles import get_channel_button_style, get_channel_button_ref_style
        _colors = {"A": "#1D1D1F", "B": "#FF3B30", "C": "#007AFF", "D": "#34C759"}
        for ch, btn in getattr(self, "channel_toggles", {}).items():
            color = btn.property("channel_color") or _colors.get(ch, "#1D1D1F")
            if ref_letter and ch.lower() == ref_letter:
                btn.setStyleSheet(get_channel_button_ref_style(color))
            else:
                btn.setStyleSheet(get_channel_button_style(color))

    def _on_spark_toggle(self, checked: bool):
        """Handle Spark toggle button — opens/closes the floating Sparq bubble. Never crashes."""
        try:
            bubble = getattr(self, 'spark_bubble', None)
            if bubble is None:
                return
            # Drive bubble from button state directly rather than toggle(), so they stay in sync
            if checked:
                if not bubble.isVisible():
                    bubble._reposition()
                    bubble.show()
                    bubble.raise_()
            else:
                bubble.hide()
        except Exception as e:
            logger.error(f"Spark toggle failed (non-fatal): {e}")

    def _on_spectrum_toggle(self, checked: bool):
        """Handle Spectrum toggle button — opens/closes the floating SpectrumBubble. Never crashes."""
        try:
            spec = getattr(self, 'spectrum_bubble', None)
            if spec is None:
                return
            if checked:
                if not spec.isVisible():
                    spec.reposition()
                    spec.show()
                    spec.raise_()
            else:
                spec.hide()
        except Exception as e:
            logger.error(f"Spectrum toggle failed (non-fatal): {e}")

    def resizeEvent(self, event):
        """Reposition floating bubbles (Sparq + Spectrum) anchored to window corners on resize."""
        super().resizeEvent(event)
        try:
            bubble = getattr(self, 'spark_bubble', None)
            if bubble is not None:
                bubble.reposition()
        except Exception:
            pass
        try:
            spec = getattr(self, 'spectrum_bubble', None)
            if spec is not None:
                spec.reposition()
        except Exception:
            pass

    def _create_graph_container(
        self,
        title: str,
        height: int,
        show_delta_spr: bool = False,
    ) -> QFrame:
        """Create a graph container with title and controls."""
        import pyqtgraph as pg

        container = QFrame()
        container.setMinimumHeight(height)
        if show_delta_spr:
            container.setObjectName("ActiveCycleCard")
            # Active Cycle: elevated white card — more prominent shadow + subtle border
            container.setStyleSheet(
                "QFrame#ActiveCycleCard {"
                "  background: #FFFFFF;"
                "  border-radius: 12px;"
                "  border: 1px solid rgba(0, 0, 0, 0.07);"
                "}",
            )
            elevated_shadow = QGraphicsDropShadowEffect()
            elevated_shadow.setBlurRadius(24)
            elevated_shadow.setColor(QColor(0, 0, 0, 45))
            elevated_shadow.setOffset(0, 4)
            container.setGraphicsEffect(elevated_shadow)
        else:
            container.setObjectName("LiveSensogramCard")
            # Live Sensorgram: standard white card with light shadow
            container.setStyleSheet(
                "QFrame#LiveSensogramCard {"
                "  background: #FFFFFF;"
                "  border-radius: 12px;"
                "}",
            )
            container.setGraphicsEffect(create_card_shadow())

        layout = QVBoxLayout(container)
        if show_delta_spr:
            # Active Cycle: zero side/bottom so the plot bleeds to card edges;
            # title and controls row get their own 16px side indent via setContentsMargins below.
            layout.setContentsMargins(0, 20, 0, 0)
        else:
            layout.setContentsMargins(Dimensions.MARGIN_MD, 14, Dimensions.MARGIN_MD, 12)
        layout.setSpacing(6)

        # Title row with controls
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        if show_delta_spr:
            # Indent title to match the top-graph 16px left margin
            title_row.setContentsMargins(Dimensions.MARGIN_MD, 0, Dimensions.MARGIN_MD, 0)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            "QLabel {"
            "  font-size: 14px;"
            "  font-weight: 700;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "  letter-spacing: -0.2px;"
            "}",
        )
        title_row.addWidget(title_label)
        title_row.addStretch()

        # Action buttons — icon-only 28×28, right-aligned in title row (Active Cycle only)
        if show_delta_spr:
            import os as _os2
            from PySide6.QtGui import QIcon as _QIcon3
            from PySide6.QtCore import QSize as _QSize3
            from affilabs.utils.resource_path import get_affilabs_resource as _get_res2

            _ICON_BTN_STYLE = (
                "QPushButton {"
                "  background: rgba(0,0,0,0.05);"
                "  border: none;"
                "  border-radius: 6px;"
                "  padding: 0px;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0,0,0,0.10);"
                "}"
                "QPushButton:pressed {"
                "  background: rgba(0,0,0,0.18);"
                "}"
            )
            _LIVE_BTN_STYLE = (
                "QPushButton {"
                "  background: rgba(0,0,0,0.05);"
                "  border: none;"
                "  border-radius: 6px;"
                "  padding: 0px;"
                "}"
                "QPushButton:checked {"
                "  background: rgba(0,122,255,0.15);"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0,0,0,0.10);"
                "}"
                "QPushButton:hover:checked {"
                "  background: rgba(0,122,255,0.22);"
                "}"
                "QPushButton:pressed {"
                "  background: rgba(0,122,255,0.30);"
                "}"
            )

            def _make_icon_btn(svg_name, tooltip, style=_ICON_BTN_STYLE):
                btn = QPushButton()
                btn.setFixedSize(28, 28)
                btn.setToolTip(tooltip)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(style)
                _path = str(_get_res2(f"ui/img/{svg_name}"))
                if _os2.path.exists(_path):
                    btn.setIcon(_QIcon3(_path))
                    btn.setIconSize(_QSize3(16, 16))
                return btn

            pass  # action buttons are added to timing_row below

        layout.addLayout(title_row)

        # Initialize delta_display as None (only created if show_delta_spr is True)
        delta_display = None

        # Add controls row (only for Active Cycle graph) — display toggles + action buttons
        if show_delta_spr:
            timing_row = QHBoxLayout()
            timing_row.setSpacing(8)
            timing_row.setContentsMargins(Dimensions.MARGIN_MD, 0, Dimensions.MARGIN_MD, 4)

            # Display label
            from affilabs.ui_styles import get_channel_button_style, get_channel_button_ref_style
            display_label = QLabel("Display:")
            display_label.setStyleSheet(
                "QLabel {"
                "  font-size: 12px;"
                "  font-weight: 600;"
                "  color: #1D1D1F;"
                "  padding-right: 4px;"
                "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
                "}"
            )
            display_label.setToolTip("Toggle channel visibility on both graphs")
            timing_row.addWidget(display_label)

            # Channel visibility toggle buttons (moved from Live Sensorgram header)
            self.channel_toggles = {}
            _toggle_colors = {
                "A": ("#1D1D1F", "Toggle Channel A"),
                "B": ("#FF3B30", "Toggle Channel B"),
                "C": ("#007AFF", "Toggle Channel C"),
                "D": ("#34C759", "Toggle Channel D"),
            }
            _BTN_W, _BTN_H = 32, 28
            for ch, (color, tooltip) in _toggle_colors.items():
                ch_container = QWidget()
                ch_container.setFixedSize(_BTN_W, _BTN_H)
                ch_btn = QPushButton(ch, ch_container)
                ch_btn.setCheckable(True)
                ch_btn.setChecked(True)
                ch_btn.setGeometry(0, 0, _BTN_W, _BTN_H)
                ch_btn.setToolTip(f"{tooltip}\nCtrl+click to set/clear as reference channel")
                ch_btn.setProperty("channel_color", color)
                ch_btn.setProperty("channel_letter", ch.lower())
                ch_btn.setStyleSheet(get_channel_button_style(color))
                ch_btn.installEventFilter(self)
                self.channel_toggles[ch] = ch_btn
                ch_btn.toggled.connect(
                    lambda checked, channel=ch: self.sensogram_presenter.toggle_channel_visibility(channel, checked)
                )
                timing_row.addWidget(ch_container)

            timing_row.addStretch()

            # Channel time-shift bubble (hidden until a shift is applied)
            self.channel_shift_label = QLabel("")
            self.channel_shift_label.setVisible(False)
            self.channel_shift_label.setStyleSheet(
                "QLabel {"
                "  background: rgba(0, 122, 255, 0.08);"
                "  border: 1px solid rgba(0, 122, 255, 0.25);"
                "  border-radius: 4px;"
                "  padding: 2px 8px;"
                "  font-size: 11px;"
                "  color: #007AFF;"
                f"  font-family: {Fonts.MONOSPACE};"
                "  font-weight: 600;"
                "}"
            )
            self.channel_shift_label.setToolTip(
                "Channel time shift (visual only)\n"
                "← / → Arrow keys: shift ±0.1s\n"
                "Shift + Arrow: shift ±1.0s"
            )
            timing_row.addWidget(self.channel_shift_label)

            timing_row.addSpacing(4)

            # Cycle Note button
            self.cycle_note_btn = _make_icon_btn("pen_icon.svg", "Add or edit notes for the current cycle")
            self.cycle_note_btn.setVisible(True)
            self._cycle_note_has_content = False
            self.cycle_note_btn.clicked.connect(self._open_cycle_notes_popup)
            timing_row.addWidget(self.cycle_note_btn)

            timing_row.addSpacing(4)

            # Live Data toggle
            self.live_data_btn = _make_icon_btn("live_icon.svg", "Live Data — cursor follows latest data", _LIVE_BTN_STYLE)
            self.live_data_btn.setCheckable(True)
            self.live_data_btn.setChecked(True)
            self.live_data_btn.toggled.connect(self.sensogram_presenter.set_live_data_enabled)
            timing_row.addWidget(self.live_data_btn)

            # Reset Timing
            self.reset_timing_btn = _make_icon_btn(
                "reset_icon.svg",
                "Reset Timing\nReset all channel time shifts to default"
            )
            self.reset_timing_btn.clicked.connect(self._reset_channel_timing)
            timing_row.addWidget(self.reset_timing_btn)

            # Clear Flags
            self.clear_flags_btn = _make_icon_btn(
                "clear_icon.svg",
                "Clear All Flags\nRemove all flags and reset channel timing"
            )
            self.clear_flags_btn.clicked.connect(self._clear_cycle_markers)
            timing_row.addWidget(self.clear_flags_btn)

            # Clear Graph (trash)
            self.clear_graph_btn = _make_icon_btn(
                "trash_icon.svg",
                "Clear all graph data"
            )
            self.clear_graph_btn.clicked.connect(self._on_clear_graph_clicked)
            timing_row.addWidget(self.clear_graph_btn)

            layout.addLayout(timing_row)

        # ── Section divider (title area → plot) ────────────────────────────
        _div = QFrame()
        _div.setFrameShape(QFrame.Shape.HLine)
        _div.setFixedHeight(1)
        _div.setStyleSheet("background: #E5E5EA; border: none;")
        layout.addWidget(_div)

        # Create standardized time-series plot
        left_label = "Δ SPR (RU)" if show_delta_spr else "λ (nm)"
        # Use larger fonts for Active Cycle graph
        axis_size = "14pt" if show_delta_spr else "11pt"
        plot_widget = create_time_plot(
            left_label, size=axis_size, transparent=not show_delta_spr,
            use_minutes=not show_delta_spr,
        )

        # User-zoom tracking: gate auto-adjust in ui_update_helpers
        if show_delta_spr:
            plot_widget._user_zoomed = False
            plot_widget.getPlotItem().getViewBox().sigRangeChangedManually.connect(
                lambda: setattr(plot_widget, '_user_zoomed', True)
            )

        # Create plot curves for 4 channels with distinct colors
        # Ch A: Black, Ch B: Red, Ch C: Blue, Ch D: Green
        curves = add_channel_curves(plot_widget, clickable=False, width=3)

        # Add Start/Stop cursors for Full Experiment Timeline (top graph)
        # Navigation concept: Live Sensorgram is the navigation space, cursors define cycle of interest region
        start_cursor = None
        stop_cursor = None

        # Curve clicking for channel selection DISABLED
        # Users can select channels from the sidebar instead
        # if show_delta_spr:  # Active Cycle (bottom graph)
        #     for i, curve in enumerate(curves):
        #         try:
        #             # Make curve clickable with larger tolerance (18px)
        #             curve.setCurveClickable(True, width=18)
        #             # Connect to channel selection for timing adjustment
        #             channel_letter = chr(ord('a') + i)  # 0→'a', 1→'b', 2→'c', 3→'d'
        #             curve.sigClicked.connect(
        #                 lambda *args, ch=channel_letter: self._on_timing_channel_selected(ch)
        #             )
        #             logger.debug(f"[ACTIVE CYCLE] Connected click handler for channel {channel_letter.upper()}")
        #         except AttributeError as e:
        #             logger.warning(f"[ACTIVE CYCLE] Could not make curve {i} clickable: {e}")
        #         except Exception as e:
        #             logger.warning(f"[ACTIVE CYCLE] Error connecting curve {i} click: {e}")

        if not show_delta_spr:  # Only for Live Sensorgram (top graph)
            # Start cursor - thicker line (3px) for easier interaction
            start_cursor = pg.InfiniteLine(
                pos=0,
                angle=90,
                pen=pg.mkPen(color="#1D1D1F", width=3),  # 3px for easier click target
                movable=True,
                label="Start: {value:.0f} s",
                labelOpts={
                    "position": 0.5,  # Center of graph
                    "color": "#1D1D1F",
                    "fill": "#FFFFFF",
                    "movable": False,
                    "rotateAxis": (1, 0),  # Rotate 180 degrees total (horizontal)
                },
            )
            # Hide label by default (show only on 3s hover)
            start_cursor.label.setVisible(False)
            # Thicker hover effect (5px) for clear visual feedback
            start_cursor.setHoverPen(pg.mkPen(color="#666666", width=5))
            plot_widget.addItem(start_cursor)

            # Stop cursor - thicker line (3px) for easier interaction
            stop_cursor = pg.InfiniteLine(
                pos=0,  # Start at 0, will auto-follow as data comes in
                angle=90,
                pen=pg.mkPen(color="#1D1D1F", width=3),  # 3px for easier click target
                movable=True,
                label="Stop: {value:.0f} s",
                labelOpts={
                    "position": 0.5,  # Center of graph
                    "color": "#1D1D1F",
                    "fill": "#FFFFFF",
                    "movable": False,
                    "rotateAxis": (1, 0),  # Rotate 180 degrees total (horizontal)
                },
            )
            # Hide label by default (show only on 3s hover)
            stop_cursor.label.setVisible(False)
            # Thicker hover effect (5px) for clear visual feedback
            stop_cursor.setHoverPen(pg.mkPen(color="#666666", width=5))
            plot_widget.addItem(stop_cursor)

            # Setup hover timers for delayed label display (3 seconds)
            from PySide6.QtCore import QTimer
            start_cursor._hover_timer = QTimer()
            start_cursor._hover_timer.setSingleShot(True)
            start_cursor._hover_timer.timeout.connect(lambda: start_cursor.label.setVisible(True))

            stop_cursor._hover_timer = QTimer()
            stop_cursor._hover_timer.setSingleShot(True)
            stop_cursor._hover_timer.timeout.connect(lambda: stop_cursor.label.setVisible(True))

            # Override hoverEvent to handle label visibility
            def make_hover_handler(cursor):
                original_hover = cursor.hoverEvent
                def hover_event(ev):
                    original_hover(ev)
                    if ev.isExit():
                        # Mouse left - cancel timer and hide label
                        cursor._hover_timer.stop()
                        cursor.label.setVisible(False)
                    else:
                        # Mouse entered - start 3 second timer
                        cursor._hover_timer.start(3000)
                return hover_event

            start_cursor.hoverEvent = make_hover_handler(start_cursor)
            stop_cursor.hoverEvent = make_hover_handler(stop_cursor)

        # Store references to curves and cursors on the plot widget
        plot_widget.curves = curves
        plot_widget.delta_display = None  # Removed — replaced by interactive_spr_legend overlay
        plot_widget.start_cursor = start_cursor
        plot_widget.stop_cursor = stop_cursor
        # DEPRECATED: Legacy flag attrs kept for backward compat only.
        # All flag logic now routes through FlagManager (unified flag system).
        plot_widget.flag_markers = []
        plot_widget.channel_flags = {0: [], 1: [], 2: [], 3: []}

        # Connect plot click event for flagging (ONLY for Live Sensorgram - top graph)
        # Bottom graph (Cycle of Interest) has default PyQtGraph interactions
        if not show_delta_spr:  # Live Sensorgram
            plot_widget.scene().sigMouseClicked.connect(
                lambda event: self._on_plot_clicked(event, plot_widget),
            )

        # Mouse interaction mode: Rectangle zoom (default for both graphs)
        # Top graph: Rectangle zoom + flagging via right-click
        # Bottom graph: Rectangle zoom only (default PyQtGraph behavior)
        plot_widget.getPlotItem().getViewBox().setMouseMode(pg.ViewBox.RectMode)

        # Active Cycle graph: kill pyqtgraph's default 10% auto-range padding
        if show_delta_spr:
            plot_widget.getPlotItem().getViewBox().setDefaultPadding(0)

        layout.addWidget(plot_widget, 1)

        # Embed interactive SPR legend inside the Active Cycle graph
        if show_delta_spr:
            from affilabs.widgets.interactive_spr_legend import InteractiveSPRLegend
            spr_legend = InteractiveSPRLegend(parent=plot_widget, title="Δ")
            spr_legend.setVisible(True)  # Visible on startup
            spr_legend.channel_timing_selected.connect(
                lambda ch: self._on_timing_channel_selected(ch)
            )
            plot_widget.interactive_spr_legend = spr_legend
            # Position after layout settles
            from PySide6.QtCore import QTimer as _QTimer
            _QTimer.singleShot(200, lambda w=plot_widget: self._position_active_cycle_legend(w))

            # Cycle status overlay — top-right of Active Cycle graph
            from affilabs.widgets.cycle_status_overlay import CycleStatusOverlay
            cycle_overlay = CycleStatusOverlay(parent=plot_widget)
            plot_widget.cycle_status_overlay = cycle_overlay
            _QTimer.singleShot(200, lambda w=plot_widget: self._position_cycle_status_overlay(w))
        else:
            plot_widget.interactive_spr_legend = None
            plot_widget.cycle_status_overlay = None

        # Add Cycle Intelligence Footer to bottom graph (Active Cycle)
        if show_delta_spr:
            footer = CycleIntelligenceFooter()
            footer.update_cycle_info(None)
            footer.update_status({
                'build': '⚪ Not built',
                'detection': '⚪ Idle',
                'flags': 0,
                'injection': '⚪ Ready',
            })
            # Signal metrics drop-down — sits between graph and footer, hidden by default
            layout.addWidget(footer._sig_panel)
            layout.addWidget(footer)
            plot_widget.intelligence_footer = footer
            self._cycle_intelligence_footer = footer  # ref for hotkey toggle

            # Wire live clocks — use a deferred getter so main.py can register
            # _get_elapsed_time and _get_recording_elapsed after construction.
            def _make_clock_getter(mw):
                def _getter():
                    exp_fn = getattr(mw, '_get_elapsed_time', None)
                    rec_fn = getattr(mw, '_get_recording_elapsed', None)
                    exp = exp_fn() if callable(exp_fn) else None
                    rec = rec_fn() if callable(rec_fn) else None
                    return (exp if exp is not None else 0.0, rec)
                return _getter

            footer.set_clock_getter(_make_clock_getter(self))

            # Wire recording state changes to show/hide rec clock
            if hasattr(self, 'recording_start_requested'):
                self.recording_start_requested.connect(
                    lambda: footer.set_recording_active(True)
                )
            if hasattr(self, 'recording_stop_requested'):
                self.recording_stop_requested.connect(
                    lambda: footer.set_recording_active(False)
                )

            # Wire footer → status bar badge so REC timer shows at the bottom
            def _update_rec_badge(text: str) -> None:
                if hasattr(self, '_rec_badge_status'):
                    self._rec_badge_status.setText(text)
            footer.set_rec_badge_updater(_update_rec_badge)

        # No minimum Y-range enforcement — let the data drive the scale tightly.

        return plot_widget, container

    def _on_timing_channel_selected(self, channel: str):
        """Handle channel selection for timing adjustment in Active Cycle graph.

        Selecting a channel from the sidebar:
        - Selects the channel for timing adjustment
        - Highlights the curve
        - Enables timing adjustment mode

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
        """
        if not hasattr(self, "cycle_of_interest_graph"):
            return

        # Store selected channel for timing adjustment
        channel_idx = ord(channel) - ord('a')  # 'a'→0, 'b'→1, 'c'→2, 'd'→3
        channel_letter = channel.upper()

        self.selected_channel_for_timing = channel_idx
        self.selected_channel_letter = channel_letter

        # Sync legend selection highlight (legend is now the channel selector)
        if hasattr(self, "cycle_of_interest_graph") and hasattr(self.cycle_of_interest_graph, "interactive_spr_legend"):
            legend = self.cycle_of_interest_graph.interactive_spr_legend
            if legend is not None:
                legend.selected_channel = channel
                for ch_key in ['a', 'b', 'c', 'd']:
                    legend._update_channel_appearance(ch_key, ch_key == channel)

        # Store selected channel in main app (will be used by flag placement logic)
        if hasattr(self, "app"):
            self.app._selected_flag_channel = channel

        # Update curve highlighting (make selected curve thicker)
        import pyqtgraph as pg
        from affilabs.plot_helpers import CHANNEL_COLORS, CHANNEL_COLORS_COLORBLIND

        # Get channel colors based on colorblind mode setting
        colorblind_enabled = self.colorblind_check.isChecked() if getattr(self, 'colorblind_check', None) is not None else False
        color_palette = CHANNEL_COLORS_COLORBLIND if colorblind_enabled else CHANNEL_COLORS

        # Convert hex colors to RGB tuples for pyqtgraph
        channel_colors = [self._hex_to_rgb(c) for c in color_palette]

        for i, curve in enumerate(self.cycle_of_interest_graph.curves):
            if i == channel_idx:
                # Selected curve: thicker line (width 4)
                curve.setPen(pg.mkPen(color=channel_colors[i], width=4))
            else:
                # Unselected curves: normal width (width 2)
                curve.setPen(pg.mkPen(color=channel_colors[i], width=2))

        logger.debug(f"Channel {channel.upper()} selected for timing adjustment (curve highlighted)")

        # Enable timing adjustment mode for Active Cycle graph
        self._enable_timing_mode(channel_idx, channel_letter, graph_name="Active Cycle")

    def _enable_timing_mode(self, channel_idx, channel_letter, graph_name="Active Cycle"):
        """Enable timing adjustment mode for the selected channel.

        NOTE: In the unified flag system, live flags are software-placed only.
        This method now just stores the selected channel for the FlagManager.

        Args:
            channel_idx: Index of the channel (0-3)
            channel_letter: Letter of the channel (A-D)
            graph_name: Name of the graph where timing adjustment is enabled
        """
        # Store selected channel for software-driven flag placement
        if not hasattr(self, "timing_mode_enabled"):
            self.timing_mode_enabled = False

        if graph_name == "Active Cycle":
            print(f"Channel {channel_letter} selected for timing adjustment")

    def _on_plot_clicked(self, event, plot_widget):
        """Handle clicks on the Live Sensorgram (top graph).

        UNIFIED FLAG SYSTEM: Manual flag placement on the live sensorgram is
        disabled. Flags during acquisition are placed by the software only
        (injection detection, wash events). Users can adjust flags in the
        Edits tab after acquisition.
        """
        # No-op: live sensorgram flag placement removed in unified flag system
        pass

    def _add_flag_to_point(self, channel_idx, x_pos, y_pos, note=""):
        """Legacy stub — live sensorgram flag placement removed in unified flag system.

        Flags during acquisition are now placed by software only via FlagManager.
        Users can add/edit flags in the Edits tab.
        """
        logger.debug("_add_flag_to_point is deprecated — flags are software-placed during acquisition")

    def _remove_flag_at_position(self, channel_idx, x_pos, tolerance=5.0):
        """Legacy stub — live sensorgram flag removal removed in unified flag system."""
        logger.debug("_remove_flag_at_position is deprecated — use Edits tab for flag management")

    def add_event_marker(self, time_pos: float, event_name: str, color: str = "#00C853"):
        """Add a visual event marker to the full timeline graph.

        Args:
            time_pos: Time position in seconds where the event occurred
            event_name: Name/description of the event
            color: Hex color code for the marker (default green)
        """
        if not hasattr(self, "full_timeline_graph"):
            return

        import pyqtgraph as pg

        # Create vertical line marker
        event_line = pg.InfiniteLine(
            pos=time_pos,
            angle=90,
            pen=pg.mkPen(color=color, width=2, style=pg.QtCore.Qt.PenStyle.DashDotLine),
            movable=False,
        )

        # Create text label
        # Truncate event name if too long
        display_text = event_name if len(event_name) <= 30 else event_name[:27] + "..."
        event_text = pg.TextItem(
            text=f"📍 {display_text}",
            color=color,
            anchor=(0.5, 1),  # Center, bottom - anchor at bottom so text hangs from top of graph
        )

        # Get y-axis range to position text at top of graph
        view_range = self.full_timeline_graph.getPlotItem().getViewBox().viewRange()
        y_max = view_range[1][1]  # Top of y-axis
        event_text.setPos(time_pos, y_max)

        # Add to graph
        self.full_timeline_graph.addItem(event_line)
        self.full_timeline_graph.addItem(event_text)

        # Store reference (in flag_markers list for now, could create separate event_markers list)
        event_marker = {
            "type": "event",
            "time": time_pos,
            "event": event_name,
            "line": event_line,
            "text": event_text,
            "color": color,
        }

        # Initialize event_markers list if it doesn't exist
        if not hasattr(self.full_timeline_graph, 'event_markers'):
            self.full_timeline_graph.event_markers = []

        self.full_timeline_graph.event_markers.append(event_marker)

        logger.info(f"Event marker added at t={time_pos:.2f}s: {event_name}")

    def _update_flags_table(self):
        """Update the Flags column in the cycle data table with current flags from FlagManager."""
        if not hasattr(self, "cycle_data_table"):
            return

        # Count live flags per channel from FlagManager
        flag_counts = {}
        if hasattr(self, 'app') and hasattr(self.app, 'flag_mgr') and self.app.flag_mgr:
            for flag in self.app.flag_mgr.get_live_flags():
                ch = flag.channel.upper()
                flag_counts[ch] = flag_counts.get(ch, 0) + 1

        if flag_counts:
            flag_summary = ", ".join(
                [f"Ch{ch}: {count}" for ch, count in flag_counts.items()],
            )
            print(f"Flags summary: {flag_summary}")

    def _create_blank_content(self, tab_name):
        """Create a blank page for tabs that don't have content yet."""
        # Special handling for different tabs
        if tab_name == "Edits":
            return self._create_edits_content()
        if tab_name == "Analyze":
            return self._create_analyze_content()
        if tab_name == "Report":
            return self._create_report_content()

        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame {  background: #F8F9FA;  }",
        )

        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Empty state message
        empty_icon = QLabel("📑")
        empty_icon.setStyleSheet(
            "QLabel {  font-size: 64px;  background: {Colors.TRANSPARENT};}",
        )
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(empty_icon)

        empty_title = QLabel(f"{tab_name} Page")
        empty_title.setStyleSheet(
            "QLabel {"
            "  font-size: 24px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  margin-top: 16px;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "}",
        )
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(empty_title)

        empty_desc = QLabel(f"Content for the {tab_name} tab will appear here.")
        empty_desc.setStyleSheet(
            "QLabel {"
            "  font-size: 14px;"
            "  color: {Colors.SECONDARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  margin-top: 8px;"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        empty_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(empty_desc)

        return content_widget

    def _create_edits_content(self):
        """Create the Edits tab content (delegated to EditsTab class)."""
        # Lazy import EditsTab to speed up startup
        from affilabs.tabs.edits_tab import EditsTab

        self.edits_tab = EditsTab(self)
        return self.edits_tab.create_content()

    # Edits tab helper methods - delegate to EditsTab instance
    # Dead code removed (lines 2848-3223):
    # - Stub _create_segment_from_selection (real implementation at line ~6451)
    # - Duplicate _create_edits_right_panel (367 lines)
    # - Duplicate _create_analyze_left_panel
    # Active definitions are below

    def _toggle_signal_metrics_panel(self) -> None:
        """Ctrl+Shift+M — toggle the λ/FWHM/p2p/slope metrics strip in the cycle footer.

        Intended for internal/dev use: hide it for customer demos, show it when
        diagnosing signal quality.  State is not persisted across restarts.
        """
        footer = getattr(self, '_cycle_intelligence_footer', None)
        if footer is not None:
            footer.toggle_signal_panel()

    def update_cycle_intelligence_footer(self, cycle_data: dict | None = None, status_data: dict | None = None) -> None:
        """Update the Cycle Intelligence Footer beneath Active Cycle graph.

        Args:
            cycle_data: Current cycle dictionary with keys:
                - name, type, duration_minutes, sample_id, concentration, units, note, channels
            status_data: Status dictionary with keys:
                - build: Build status message (str)
                - detection: Detection status (str)
                - flags: Flag count (int)
                - injection: Injection readiness (str)
        """
        try:
            if not hasattr(self, 'cycle_of_interest_graph'):
                return

            footer = getattr(self.cycle_of_interest_graph, 'intelligence_footer', None)
            if not footer:
                return

            if cycle_data is not None:
                footer.update_cycle_info(cycle_data)

            if status_data is not None:
                footer.update_status(status_data)

        except Exception as e:
            logger.debug(f"Could not update cycle intelligence footer: {e}")

    def _toggle_recording(self):
        """Toggle recording state - emit signal for Application to handle."""
        logger.info(
            f"[RECORD-BTN] _toggle_recording called, is_recording={self.is_recording}",
        )

        # Emit signal based on current recording state
        if not self.is_recording:
            # Request to start recording - emit signal
            if hasattr(self, "recording_start_requested"):
                logger.info("[RECORD-BTN] Emitting recording_start_requested signal")
                self.recording_start_requested.emit()
            else:
                logger.error(
                    "[RECORD-BTN] ERROR: recording_start_requested signal not found!",
                )
        # Request to stop recording - emit signal
        elif hasattr(self, "recording_stop_requested"):
            logger.info("[RECORD-BTN] Emitting recording_stop_requested signal")
            self.recording_stop_requested.emit()
        else:
            logger.error(
                "[RECORD-BTN] ERROR: recording_stop_requested signal not found!",
            )

    def _toggle_pause(self):
        """Toggle pause state for live acquisition."""
        is_paused = self.pause_btn.isChecked()

        if is_paused:
            # Pause acquisition
            self.pause_btn.setToolTip("Resume Live Acquisition")
            logger.info("⏸ Live acquisition paused")
            # Emit signal to pause acquisition
            if hasattr(self, "acquisition_pause_requested"):
                self.acquisition_pause_requested.emit(True)
        else:
            # Resume acquisition
            self.pause_btn.setToolTip("Pause Live Acquisition")
            logger.info("▶️ Live acquisition resumed")
            # Emit signal to resume acquisition
            if hasattr(self, "acquisition_pause_requested"):
                self.acquisition_pause_requested.emit(False)

    def set_recording_state(self, is_recording: bool, filename: str = ""):
        """Update recording UI state from external controller.

        Args:
            is_recording: True if recording is active
            filename: Name of the recording file (if recording)

        """
        self.is_recording = is_recording
        self.record_btn.setChecked(is_recording)

        # Sync the combined Start & Record button in the sidebar
        try:
            sb = getattr(self, 'sidebar', None)
            srb = getattr(sb, 'start_record_btn', None)
            if srb is not None:
                srb.setChecked(is_recording)
                if is_recording:
                    srb.setText("Stop")
                    srb.setProperty("mode", "stop")
                else:
                    srb.setText("▶ Start & Record")
                    srb.setProperty("mode", "start")
                srb.style().unpolish(srb)
                srb.style().polish(srb)
        except Exception:
            pass

        # Status bar recording badge + path label
        if hasattr(self, '_rec_badge_status'):
            if is_recording:
                self._rec_badge_status.show()
            else:
                self._rec_badge_status.hide()

        if hasattr(self, '_rec_path_label'):
            if is_recording and filename:
                self._rec_path_label.setText(Path(filename).name)
                self._rec_path_label.setStyleSheet(
                    "color: #FF3B30; font-size: 12px; margin: 0 8px 0 0; "
                    "font-family: -apple-system, 'Segoe UI', system-ui, sans-serif;"
                )
                self._rec_path_label.show()
            else:
                self._rec_path_label.hide()

        if is_recording:
            display_name = Path(filename).name if filename else "data.csv"

            # Update button tooltip
            self.record_btn.setToolTip(
                f"Stop Recording\n(Recording to: {display_name})",
            )

            # Recording dot — start pulsing via timer
            if hasattr(self, 'rec_status_dot'):
                if not hasattr(self, '_rec_pulse_timer'):
                    self._rec_pulse_timer = QTimer(self)
                    self._rec_pulse_timer.setInterval(800)
                    self._rec_pulse_timer_state = False
                    def _pulse():
                        self._rec_pulse_timer_state = not self._rec_pulse_timer_state
                        if hasattr(self, 'rec_status_dot'):
                            color = "#FF3B30" if self._rec_pulse_timer_state else "rgba(255,59,48,0.25)"
                            self.rec_status_dot.setStyleSheet(
                                f"QLabel {{ color: {color}; font-size: 16px; background: transparent; }}"
                            )
                    self._rec_pulse_timer.timeout.connect(_pulse)
                self._rec_pulse_timer_state = True
                self.rec_status_dot.setStyleSheet(
                    "QLabel { color: #FF3B30; font-size: 16px; background: transparent; }"
                )
                self._rec_pulse_timer.start()

            # Status text — show filename
            if hasattr(self, 'rec_status_text'):
                self.rec_status_text.setText(f"\u23fa  Saving to: {display_name}")
                self.rec_status_text.setStyleSheet(
                    "QLabel {"
                    "  font-size: 12px;"
                    "  color: #FF3B30;"
                    "  background: transparent;"
                    "  font-weight: 600;"
                    "}"
                )

            if hasattr(self, 'recording_indicator'):
                self.recording_indicator.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(255, 59, 48, 0.1);"
                    "  border-radius: 16px;"
                    "}",
                )
        else:
            # Stop pulse timer
            if hasattr(self, '_rec_pulse_timer') and self._rec_pulse_timer.isActive():
                self._rec_pulse_timer.stop()

            # Update button tooltip back to viewing mode
            self.record_btn.setToolTip(
                "Start Recording\n(Currently viewing - not saved)",
            )

            # Reset dot
            if hasattr(self, 'rec_status_dot'):
                self.rec_status_dot.setStyleSheet(
                    "QLabel { color: #86868B; font-size: 16px; background: transparent; }"
                )

            # Clear status text
            if hasattr(self, 'rec_status_text'):
                self.rec_status_text.setText("Not Recording")
                self.rec_status_text.setStyleSheet(
                    "QLabel { font-size: 12px; color: #86868B; background: transparent; }"
                )

            if hasattr(self, 'recording_indicator'):
                self.recording_indicator.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.04);"
                    "  border-radius: 16px;"
                    "}",
                )

    def _init_device_config(self, device_serial: str | None = None):
        """Initialize device configuration (delegates to DeviceConfigManager).

        Args:
            device_serial: Spectrometer serial number for device-specific configuration.

        """
        self.device_config_manager.initialize_device_config(device_serial)

    def _check_missing_config_fields(self):
        """Check for missing critical configuration fields (delegates to DeviceConfigManager).

        Returns:
            List of missing field names, empty if all fields are present

        """
        return self.device_config_manager.check_missing_config_fields()

    def _get_controller_type_from_hardware(self) -> str:
        """Get controller type from connected hardware (delegates to DeviceConfigManager).

        Returns:
            Controller type string: 'Arduino', 'PicoP4SPR', 'PicoEZSPR', or ''

        """
        return self.device_config_manager.get_controller_type_from_hardware()

    def _get_polarizer_type_for_controller(self, controller_type: str) -> str:
        """Determine polarizer type based on controller (delegates to DeviceConfigManager).

        Args:
            controller_type: Type of controller ('Arduino', 'PicoP4SPR', 'PicoEZSPR')

        Returns:
            'round' or 'barrel'

        """
        return self.device_config_manager.get_polarizer_type_for_controller(
            controller_type,
        )

    def _prompt_device_config(self, device_serial: str):
        """Show dialog to collect missing device configuration (delegates to DeviceConfigManager).

        Args:
            device_serial: Device serial number

        """
        self.device_config_manager.prompt_device_config(device_serial)

    def _start_oem_calibration_workflow(self):
        """Start OEM calibration workflow (delegates to DeviceConfigManager).

        Workflow:
        1. Run servo calibration to find optimal S/P positions
        2. Pull S/P positions and update device_config
        3. Run LED calibration to find optimal intensities
        4. Pull LED intensities and update device_config
        5. Push complete config to EEPROM
        """
        self.device_config_manager.start_oem_calibration_workflow()

    def _update_maintenance_display(self):
        """Update the maintenance section with current values from device config."""
        # Update user count (doesn't depend on device config)
        try:
            sidebar = getattr(self, 'sidebar', None)
            user_mgr = getattr(sidebar, 'user_profile_manager', None) if sidebar else None
            if user_mgr and hasattr(sidebar, 'users_count_value'):
                user_count = len(user_mgr.get_profiles())
                sidebar.users_count_value.setText(f"👥 {user_count}")
        except Exception as e:
            logger.debug(f"Could not update user count: {e}")

        if self.device_config is None:
            return

        # Check if maintenance widgets exist yet (UI might not be fully initialized)
        sidebar = getattr(self, 'sidebar', None)
        if sidebar is None or not hasattr(sidebar, 'hours_value'):
            return

        try:
            import datetime

            # Update operation hours
            led_hours = self.device_config.config["maintenance"]["led_on_hours"]
            sidebar.hours_value.setText(f"⏱️ {led_hours:,.1f} hrs")

            # Update experiment count (total measurement cycles)
            total_cycles = self.device_config.config["maintenance"].get("total_measurement_cycles", 0)
            sidebar.experiments_value.setText(f"📊 {total_cycles:,}")

            # Update last operation date
            if self.last_powered_on:
                last_op_str = self.last_powered_on.strftime("%b %d, %Y")
                sidebar.last_op_value.setText(f"📅 {last_op_str}")
            else:
                sidebar.last_op_value.setText("📅 Never")

            # Calculate next maintenance based on actual usage
            # Service recommended every 500 LED hours or 12 months, whichever first
            SERVICE_INTERVAL_HOURS = 500.0
            now = datetime.datetime.now()

            # Try reading last maintenance date from config
            last_maint_str = self.device_config.config["maintenance"].get("last_maintenance_date")
            next_due_str = self.device_config.config["maintenance"].get("next_maintenance_due")

            maintenance_overdue = False
            if next_due_str:
                # Use the stored date (set after each service)
                try:
                    next_due = datetime.datetime.fromisoformat(next_due_str[:10])
                    days_left = (next_due - now).days
                    if days_left < 0:
                        sidebar.next_maintenance_value.setText(f"🔧 OVERDUE ({-days_left}d)")
                        maintenance_overdue = True
                    elif days_left < 30:
                        sidebar.next_maintenance_value.setText(f"🔧 {next_due.strftime('%b %d, %Y')}")
                        maintenance_overdue = True
                    else:
                        sidebar.next_maintenance_value.setText(f"🔧 {next_due.strftime('%b %Y')}")
                except (ValueError, TypeError):
                    sidebar.next_maintenance_value.setText("🔧 —")
            elif led_hours >= SERVICE_INTERVAL_HOURS:
                # No due date set, but hours exceeded threshold
                sidebar.next_maintenance_value.setText(f"🔧 {led_hours:,.0f}/{SERVICE_INTERVAL_HOURS:,.0f} hrs")
                maintenance_overdue = True
            else:
                # No due date, show hours remaining until service
                hrs_remaining = SERVICE_INTERVAL_HOURS - led_hours
                sidebar.next_maintenance_value.setText(f"🔧 in {hrs_remaining:,.0f} hrs")

            # Highlight based on urgency
            if maintenance_overdue:
                sidebar.next_maintenance_value.setStyleSheet(
                    f"font-size: 13px;"
                    f"color: #FF3B30;"
                    f"background: transparent;"
                    f"font-weight: 700;"
                    f"font-family: {Fonts.SYSTEM};",
                )
            else:
                sidebar.next_maintenance_value.setStyleSheet(
                    f"font-size: 13px;"
                    f"color: #FF9500;"
                    f"background: transparent;"
                    f"font-weight: 600;"
                    f"font-family: {Fonts.SYSTEM};",
                )
        except Exception as e:
            logger.error(f"Failed to update maintenance display: {e}")

    def start_led_operation_tracking(self):
        """Start tracking LED operation time (call when acquisition starts)."""
        if self.device_config is None:
            return

        import datetime

        self.led_start_time = datetime.datetime.now()
        self.last_powered_on = self.led_start_time

        logger.info("LED operation tracking started")
        self._update_maintenance_display()

    def stop_led_operation_tracking(self):
        """Stop tracking LED operation time and add elapsed time to total (call when acquisition stops)."""
        if self.device_config is None or self.led_start_time is None:
            return

        try:
            import datetime

            # Calculate elapsed time in hours
            elapsed = datetime.datetime.now() - self.led_start_time
            elapsed_hours = elapsed.total_seconds() / 3600.0

            # Add to device configuration
            self.device_config.add_led_on_time(elapsed_hours)
            self.device_config.save()

            logger.info(
                f"LED operation stopped. Added {elapsed_hours:.2f} hours to total",
            )

            # Reset start time
            self.led_start_time = None

            # Update display
            self._update_maintenance_display()
        except Exception as e:
            logger.error(f"Failed to stop LED operation tracking: {e}")

    def update_last_power_on(self):
        """Update the last power-on timestamp (call when device powers on)."""
        if self.device_config is None:
            return

        import datetime

        self.last_powered_on = datetime.datetime.now()

        logger.debug(
            f"Device powered on at {self.last_powered_on.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        self._update_maintenance_display()

    def _on_start_queued_run(self):
        """Start executing queued cycles."""
        if not self.cycle_queue:
            logger.warning("No cycles in queue to start")
            return

        # Set queue running flag so it auto-advances through cycles
        self._queue_running = True

        # Execute FIRST cycle from queue (index 0)
        cycle_data = self.cycle_queue[0]  # Don't pop yet, wait for completion
        cycle_data["state"] = "running"

        logger.info(
            f"🚀 Starting queued run at FIRST cycle (1/{len(self.cycle_queue)}): {cycle_data['type']} - {cycle_data['notes']}",
        )

        # Update display to show running state
        self._update_queue_display()

        # Hide start run button while cycle is running
        self.sidebar.start_run_btn.setVisible(False)

        # Trigger the actual acquisition start through the app
        if hasattr(self, "app") and self.app:
            self.app._on_start_button_clicked()

    def _on_clear_queue(self):
        """Clear all cycles from the queue (uses queue_presenter)."""
        # Use the app's queue_presenter (new system)
        qp = getattr(getattr(self, 'app', None), 'queue_presenter', None)
        queue_size = qp.get_queue_size() if qp else len(getattr(self, 'cycle_queue', []))
        if queue_size == 0:
            return

        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Clear Queue",
            f"Remove all {queue_size} cycle(s) from the queue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if qp:
            qp.clear_queue()
        else:
            self.cycle_queue.clear()
            self._update_queue_display()
            self.sidebar.update_queue_status(0)
        logger.info("Queue cleared via Clear button")

    def _on_expand_queue(self):
        """Legacy stub — queue expansion is now handled by QueuePresenter."""
        return

        # Re-enable Add to Queue button if it was disabled
        if hasattr(self, 'add_to_queue_btn'):
            self.add_to_queue_btn.setEnabled(True)

    def open_full_cycle_table(self):
        """Switch to Edits tab to show cycle data."""
        if hasattr(self, 'navigation_presenter'):
            self.navigation_presenter.switch_page(1)
        elif hasattr(self, 'content_stack'):
            self.content_stack.setCurrentIndex(1)

    def start_cycle(self):
        """Start next cycle from queue or use current form values."""
        if self.cycle_queue:
            # Get first queued item (don't pop yet - wait for completion)
            cycle_data = self.cycle_queue[0]
            cycle_data["state"] = "running"  # Mark as running, not completed
            self._current_running_cycle = cycle_data  # Track current cycle

            # Start countdown timer with cycle duration
            if 'length_minutes' in cycle_data:
                self.start_cycle_countdown(cycle_data['length_minutes'])

            # Log cycle start event for graph marker
            if hasattr(self, 'app') and hasattr(self.app, 'recording_mgr'):
                event_name = f"Cycle Start: {cycle_data['type']}"
                if cycle_data.get('notes') and cycle_data['notes'] != 'No notes':
                    event_name += f" - {cycle_data['notes']}"
                self.app.recording_mgr.log_event(event_name)

            # Update queue display to show running state
            self._update_queue_display()

            logger.info(f"🏃 Cycle started: {cycle_data['type']} ({cycle_data.get('length_minutes', 0)} min) - {cycle_data.get('notes', 'No notes')}")
        else:
            # No queue items - quick start mode (form-based cycle creation not yet implemented)
            logger.debug("Starting immediate cycle from form values")

    def complete_cycle(self):
        """Complete the currently running cycle."""
        if self._current_running_cycle is not None:
            # Stop countdown timer
            if hasattr(self, 'cycle_countdown_timer'):
                self.cycle_countdown_timer.stop()
            self.cycle_start_time = None

            # Mark as completed and remove from queue
            self._current_running_cycle["state"] = "completed"
            if self.cycle_queue and self.cycle_queue[0] == self._current_running_cycle:
                self.cycle_queue.pop(0)

            logger.info(f"✅ Cycle completed: {self._current_running_cycle['type']}")
            self._current_running_cycle = None

            # Update display
            self._update_queue_display()

            # Re-enable Add to Queue button
            if len(self.cycle_queue) < self.max_queue_size:
                if hasattr(self, 'add_to_queue_btn'):
                    self.add_to_queue_btn.setEnabled(True)

            # Start next cycle if queue is running and has cycles
            if self.cycle_queue and hasattr(self, '_queue_running') and self._queue_running:
                logger.info(f"🔄 Auto-starting next cycle in queue ({len(self.cycle_queue)} remaining)")
                # Use QTimer to start next cycle after a short delay
                from PySide6.QtCore import QTimer
                QTimer.singleShot(500, self._start_next_queued_cycle)

    def cancel_cycle(self):
        """Cancel the currently running cycle (stopped before completion)."""
        if self._current_running_cycle is not None:
            # Stop countdown timer
            if hasattr(self, 'cycle_countdown_timer'):
                self.cycle_countdown_timer.stop()
            self.cycle_start_time = None

            # Remove from queue without marking as completed
            if self.cycle_queue and self.cycle_queue[0] == self._current_running_cycle:
                self.cycle_queue.pop(0)

            logger.info(f"❌ Cycle cancelled: {self._current_running_cycle['type']}")
            self._current_running_cycle = None

            # Update display to remove cancelled cycle
            self._update_queue_display()

            # Re-enable Add to Queue button
            if len(self.cycle_queue) < self.max_queue_size:
                if hasattr(self, 'add_to_queue_btn'):
                    self.add_to_queue_btn.setEnabled(True)

    def _start_next_queued_cycle(self):
        """Start the next cycle in the queue automatically."""
        if self.cycle_queue and not self._current_running_cycle:
            logger.info(f"🚀 Auto-starting next queued cycle")
            self.start_cycle()
        else:
            if not self.cycle_queue:
                logger.info(f"✓ Queue completed - no more cycles")
                if hasattr(self, '_queue_running'):
                    self._queue_running = False
                self._show_run_complete_dialog()
            elif self._current_running_cycle:
                logger.warning(f"⚠️ Cannot start next cycle - current cycle still running")

    def _show_run_complete_dialog(self):
        """Show completion dialog prompting user to review data and export."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        from PySide6.QtCore import Qt

        dialog = QDialog(self)
        dialog.setWindowTitle("Run Complete")
        dialog.setFixedWidth(420)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        dialog.setStyleSheet(
            "QDialog {"
            "  background: #FFFFFF;"
            "  border-radius: 12px;"
            "}"
        )

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(12)

        # Icon + title
        title = QLabel("\u2705  All cycles complete")
        title.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #1D1D1F;"
            "font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Body text
        body = QLabel(
            "Your experiment run has finished and Auto-Read is now active.\n\n"
            "Review your data in the Edits tab and export the raw data before closing."
        )
        body.setWordWrap(True)
        body.setStyleSheet(
            "font-size: 13px; color: #86868B; line-height: 1.5;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(body)

        layout.addSpacing(8)

        # Buttons row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        dismiss_btn = QPushButton("Dismiss")
        dismiss_btn.setFixedHeight(36)
        dismiss_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss_btn.setStyleSheet(
            "QPushButton {"
            "  background: #F5F5F7; color: #1D1D1F; border: none;"
            "  border-radius: 8px; padding: 8px 20px;"
            "  font-size: 13px; font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover { background: #E8E8ED; }"
        )
        dismiss_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(dismiss_btn)

        export_btn = QPushButton("\U0001F4E5  Export Data")
        export_btn.setFixedHeight(36)
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setStyleSheet(
            "QPushButton {"
            "  background: #007AFF; color: white; border: none;"
            "  border-radius: 8px; padding: 8px 20px;"
            "  font-size: 13px; font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover { background: #0066D6; }"
        )

        def _on_export():
            dialog.accept()
            # Switch to Edits tab
            self.content_stack.setCurrentIndex(1)
            # Trigger raw data export
            if hasattr(self, 'edits_tab'):
                self.edits_tab._export_raw_data()

        export_btn.clicked.connect(_on_export)
        btn_layout.addWidget(export_btn)

        layout.addLayout(btn_layout)
        dialog.exec()

    def start_cycle_countdown(self, duration_minutes: int):
        """Start countdown timer for cycle duration.

        Args:
            duration_minutes: Cycle duration in minutes

        """
        import time

        self.cycle_duration_seconds = duration_minutes * 60
        self.cycle_start_time = time.time()
        self.cycle_countdown_timer.start(1000)  # Update every second
        logger.debug(f"Started countdown timer for {duration_minutes} min cycle")

    def _update_countdown(self):
        """Update countdown timer display based on cycle progress.

        NOTE: This method is currently unused - cycle countdown is now displayed
        in the intelligence bar via set_intel_message() called from main.py.
        Kept for potential future use.
        """
        if self.cycle_start_time is None:
            return

        import time

        elapsed = time.time() - self.cycle_start_time
        remaining = max(0, self.cycle_duration_seconds - elapsed)

        # Stop timer when countdown reaches zero
        if remaining <= 0:
            self.cycle_countdown_timer.stop()
            self.cycle_start_time = None

    def _on_export_data(self):
        """Handle export data button click - emit signal with export configuration."""
        export_config = self._get_export_config()
        self.export_requested.emit(export_config)

    def _on_export_animl(self):
        """Handle AnIML export button click - check license then export."""
        from PySide6.QtWidgets import QMessageBox

        # Check if feature is available (this will show upgrade prompt if locked)
        if hasattr(self, 'app') and self.app:
            if not self.app.check_feature_access("AnIML Export", "pro"):
                return  # Feature locked, upgrade prompt shown

        # Feature is available - proceed with AnIML export
        # For now, show a message (Phase 2 will implement actual AnIML export)
        QMessageBox.information(
            self,
            "AnIML Export",
            "AnIML export functionality will be implemented in Phase 2.\n\n"
            "This is a Pro/Enterprise feature that exports data in AnIML XML format\n"
            "for regulatory compliance and LIMS integration."
        )

        logger.info("📋 AnIML export requested (Pro feature)")

    def _on_send_to_edits_clicked(self):
        """Transfer live recording data to Edits tab for review and modification."""

        # Emit signal to application layer to handle data transfer
        # The app has access to both recording manager and edits tab
        self.send_to_edits_requested.emit()

        logger.info("📤 Send to Edits requested - signal emitted")

    def _on_quick_csv_preset(self):
        """Quick CSV export preset - all data, all channels, CSV format."""
        config = self._get_export_config()
        config["preset"] = "quick_csv"
        config["format"] = "csv"
        config["include_metadata"] = False
        config["include_events"] = False
        self.export_requested.emit(config)

    def _on_analysis_preset(self):
        """Analysis-ready preset - processed data, summary table, Excel format."""
        config = self._get_export_config()
        config["preset"] = "analysis"
        config["format"] = "excel"
        config["data_types"] = {
            "processed": True,
            "summary": True,
            "raw": False,
            "cycles": False,
        }
        config["include_metadata"] = True
        config["include_events"] = True
        self.export_requested.emit(config)

    def _on_publication_preset(self):
        """Publication preset - high precision, metadata, Excel format."""
        config = self._get_export_config()
        config["preset"] = "publication"
        config["format"] = "excel"
        config["precision"] = 5
        config["include_metadata"] = True
        config["include_events"] = True
        self.export_requested.emit(config)

    def _get_export_config(self) -> dict:
        """Extract export configuration from UI controls.

        Returns:
            Dictionary with export settings

        """
        # Get selected data types
        data_types = {
            "raw": getattr(self.sidebar, "raw_data_check", None)
            and self.sidebar.raw_data_check.isChecked()
            if hasattr(self.sidebar, "raw_data_check")
            else True,
            "processed": getattr(self.sidebar, "processed_data_check", None)
            and self.sidebar.processed_data_check.isChecked()
            if hasattr(self.sidebar, "processed_data_check")
            else True,
            "cycles": getattr(self.sidebar, "cycle_segments_check", None)
            and self.sidebar.cycle_segments_check.isChecked()
            if hasattr(self.sidebar, "cycle_segments_check")
            else True,
            "summary": getattr(self.sidebar, "summary_table_check", None)
            and self.sidebar.summary_table_check.isChecked()
            if hasattr(self.sidebar, "summary_table_check")
            else True,
        }

        # Get selected channels
        channels = []
        if hasattr(self.sidebar, "export_channel_checkboxes"):
            channel_names = ["a", "b", "c", "d"]
            for i, cb in enumerate(self.sidebar.export_channel_checkboxes):
                if cb.isChecked():
                    channels.append(channel_names[i])
        else:
            channels = ["a", "b", "c", "d"]  # Default all channels

        # Get format from dropdown
        format_type = "excel"  # Default
        if hasattr(self.sidebar, "format_combo"):
            format_text = self.sidebar.format_combo.currentText()
            if "Excel" in format_text:
                format_type = "excel"
            elif "CSV" in format_text:
                format_type = "csv"
            elif "JSON" in format_text:
                format_type = "json"

        # Get options
        include_metadata = (
            getattr(self.sidebar, "metadata_check", None)
            and self.sidebar.metadata_check.isChecked()
            if hasattr(self.sidebar, "metadata_check")
            else True
        )
        include_events = (
            getattr(self.sidebar, "events_check", None)
            and self.sidebar.events_check.isChecked()
            if hasattr(self.sidebar, "events_check")
            else False
        )

        # Get precision
        precision = 4  # Default
        if hasattr(self.sidebar, "precision_combo"):
            precision = int(self.sidebar.precision_combo.currentText())

        # Get timestamp format
        timestamp_format = "relative"  # Default
        if hasattr(self.sidebar, "timestamp_combo"):
            timestamp_text = self.sidebar.timestamp_combo.currentText()
            if "Absolute" in timestamp_text:
                timestamp_format = "absolute"
            elif "seconds" in timestamp_text:
                timestamp_format = "elapsed"

        # Get filename and destination
        filename = (
            getattr(self.sidebar, "export_filename_input", None)
            and self.sidebar.export_filename_input.text()
            if hasattr(self.sidebar, "export_filename_input")
            else ""
        )
        destination = (
            getattr(self.sidebar, "export_dest_input", None)
            and self.sidebar.export_dest_input.text()
            if hasattr(self.sidebar, "export_dest_input")
            else ""
        )

        return {
            "data_types": data_types,
            "channels": channels,
            "format": format_type,
            "include_metadata": include_metadata,
            "include_events": include_events,
            "precision": precision,
            "timestamp_format": timestamp_format,
            "filename": filename,
            "destination": destination,
            "preset": None,  # Will be set by preset buttons
        }

    def _tick_acq_pulse(self) -> None:
        """Alternate the acquiring dot between full and dim on every timer tick."""
        self._acq_pulse_visible = not self._acq_pulse_visible
        color = "#007AFF" if self._acq_pulse_visible else "rgba(0,122,255,0.25)"
        if hasattr(self, '_acq_dot'):
            self._acq_dot.setStyleSheet(
                f"color: {color}; font-size: 12px; font-weight: 700; margin: 0 8px; "
                "font-family: -apple-system, 'Segoe UI', system-ui, sans-serif;"
            )


    def set_acquiring_pulse(self, active: bool) -> None:
        """Show/hide the status-bar acquiring dot and control its blink timer."""
        if not hasattr(self, '_acq_dot'):
            return
        if active:
            self._acq_dot.show()
            if hasattr(self, '_acq_pulse_timer') and not self._acq_pulse_timer.isActive():
                self._acq_pulse_visible = True
                self._acq_pulse_timer.start()
        else:
            if hasattr(self, '_acq_pulse_timer'):
                self._acq_pulse_timer.stop()
            self._acq_dot.hide()

    def update_status_operation(self, message: str, notes: str = "") -> None:
        """Update the bottom operation status bar.

        Args:
            message: Status message to display (e.g., "Running: Binding (01:52)", "Idle")
            notes: Optional cycle notes to display alongside status
        """
        if hasattr(self, 'operation_status_label'):
            # Skip displaying "Running:" messages - they now appear in Timer button above Live Sensorgram
            if "Running" in message or "Acquiring" in message:
                return

            self.operation_status_label.setText(message)
            # Color based on state using design system colors
            if "Idle" in message:
                color = Colors.SECONDARY_TEXT  # Gray for idle
                weight = int(Fonts.WEIGHT_SEMIBOLD)
            elif "Error" in message or "Failed" in message:
                color = Colors.ERROR  # Red for errors
                weight = int(Fonts.WEIGHT_BOLD)
            else:
                color = Colors.INFO  # Blue for other states
                weight = int(Fonts.WEIGHT_SEMIBOLD)

            self.operation_status_label.setStyleSheet(
                label_style(14, color=color, weight=weight)
            )

        # Update cycle notes if available
        if hasattr(self, 'cycle_notes_label'):
            if notes:
                self.cycle_notes_label.setText(f"?? {notes}")
                self.cycle_notes_label.show()
            else:
                self.cycle_notes_label.setText("")
                self.cycle_notes_label.hide()

    # ------------------------------------------------------------------
    #  Pop-out timer window helpers
    # ------------------------------------------------------------------
    def _refresh_intelligence_bar(self):
        """Refresh the Intelligence Bar display with current system diagnostics.

        NOTE: If a cycle is currently running, this method will ONLY update the status
        indicator (?/?/?) but NOT the message, to avoid overriding the cycle countdown
        """
        try:
            # Get system intelligence instance and run diagnosis
            intelligence = get_system_intelligence()
            system_state, active_issues = intelligence.diagnose_system()

            # Determine operational context for more useful messaging
            is_acquiring = hasattr(self, 'app') and hasattr(self.app, 'data_mgr') and getattr(self.app.data_mgr, '_acquiring', False)
            is_calibrated = hasattr(self, 'app') and hasattr(self.app, 'data_mgr') and getattr(self.app.data_mgr, 'calibrated', False)

            # Drive the acquiring pulse dot from the intelligence refresh cycle
            self.set_acquiring_pulse(is_acquiring)
            queue_count = len(self.segment_queue) if hasattr(self, 'segment_queue') else 0

            # Check if a cycle is currently running (don't override cycle countdown)
            is_cycle_running = hasattr(self, 'app') and hasattr(self.app, '_current_cycle') and self.app._current_cycle is not None

            # Update status based on system state
            if system_state == SystemState.HEALTHY:
                status_text = "✓"
                status_color = "#34C759"  # Green

                # Provide contextual messaging based on what's happening - use icons for brevity
                if is_acquiring:
                    message_text = "⚡ Acquiring"
                    message_color = "#007AFF"  # Blue
                elif queue_count > 0:
                    message_text = f"📋 {queue_count} queued"
                    message_color = "#007AFF"
                elif is_calibrated:
                    message_text = "✓ Calibrated"
                    message_color = "#34C759"
                else:
                    message_text = "🔧 Cal needed"
                    message_color = "#FF9500"

            elif system_state == SystemState.DEGRADED:
                status_text = "⚠"
                status_color = "#FF9500"  # Orange
                # Show most critical issue
                if active_issues:
                    message_text = f"{active_issues[0].title}"
                else:
                    message_text = "Performance degraded"
                message_color = "#FF9500"
            elif system_state == SystemState.WARNING:
                status_text = "⚠"
                status_color = "#FF9500"  # Orange
                if active_issues:
                    message_text = f"{active_issues[0].title}"
                else:
                    message_text = "Attention required"
                message_color = "#FF9500"
            elif system_state == SystemState.ERROR:
                status_text = "❌"
                status_color = "#FF3B30"  # Red
                if active_issues:
                    message_text = f"{active_issues[0].title}"
                else:
                    message_text = "System error"
                message_color = "#FF3B30"
            else:  # UNKNOWN
                status_text = "●"
                status_color = "#86868B"  # Gray
                message_text = "Initializing..."
                message_color = "#86868B"

            # Update the sidebar intelligence labels
            # Update the sidebar intelligence status indicator (always)
            self.sidebar.intel_status_label.setText(status_text)
            self.sidebar.intel_status_label.setStyleSheet(
                f"QLabel {{"
                f"  font-size: 12px;"
                f"  color: {status_color};"
                f"  background: {Colors.TRANSPARENT};"
                f"  font-weight: {Fonts.WEIGHT_BOLD};"
                f"  font-family: {Fonts.SYSTEM};"
                f"}}",
            )

            # Update sidebar message ONLY if no cycle is running (to avoid overriding cycle countdown)
            if not is_cycle_running:
                self.sidebar.intel_message_label.setText(message_text)
                self.sidebar.intel_message_label.setStyleSheet(
                    f"QLabel {{"
                    f"  font-size: 14px;"
                    f"  color: {message_color};"
                    f"  background: {Colors.TRANSPARENT};"
                    f"  font-weight: 600;"
                    f"  font-family: {Fonts.SYSTEM};"
                    f"}}",
                )

        except Exception as e:
            logger.error(f"Error refreshing intelligence bar: {e}")

    def set_intel_message(self, message: str, color: str = "#007AFF") -> None:
        """Set a custom message in the sidebar intelligence bar.

        Args:
            message: Message text to display
            color: Hex color code for the message (default: blue #007AFF)
        """
        try:
            # Update sidebar intelligence bar only
            if hasattr(self, 'sidebar') and hasattr(self.sidebar, 'intel_message_label'):
                self.sidebar.intel_message_label.setText(message)
                self.sidebar.intel_message_label.setStyleSheet(
                    f"QLabel {{"
                    f"  font-size: 12px;"
                    f"  color: {color};"
                    f"  background: {Colors.TRANSPARENT};"
                    f"  font-weight: 600;"
                    f"  font-family: {Fonts.SYSTEM};"
                    f"}}",
                )
        except Exception as e:
            logger.error(f"Error setting intel message: {e}")

    def _update_queue_display(self):
        """Legacy stub — queue display is now handled by QueueSummaryWidget.refresh()."""
        return

    def _handle_simple_led_calibration(self) -> None:
        """Handle Simple LED Calibration button click (delegates to CalibrationManager)."""
        self.calibration_manager.handle_simple_led_calibration()

    def _handle_full_calibration(self) -> None:
        """Handle Full Calibration button click (delegates to CalibrationManager)."""
        self.calibration_manager.handle_full_calibration()

    def _handle_polarizer_calibration(self) -> None:
        """Handle Polarizer Calibration button click (delegates to CalibrationManager)."""
        self.calibration_manager.handle_polarizer_calibration()

    # OEM LED Calibration button connected in Application layer (main.py)
    # Connection: ui.oem_led_calibration_btn.clicked.connect(app._on_oem_led_calibration)
    # Do NOT add duplicate handler here

    def _handle_record_baseline(self) -> None:
        """Handle Record Baseline Data button click (delegates to BaselineRecordingPresenter)."""
        self.baseline_recording_presenter.handle_record_baseline()

    def _on_recording_started(self) -> None:
        """Handle recording started signal (delegates to BaselineRecordingPresenter)."""
        self.baseline_recording_presenter.on_recording_started()

    def _on_recording_progress(self, progress: dict) -> None:
        """Handle recording progress update (delegates to BaselineRecordingPresenter)."""
        self.baseline_recording_presenter.on_recording_progress(progress)

    def _on_recording_complete(self, filepath: str) -> None:
        """Handle recording complete signal (delegates to BaselineRecordingPresenter)."""
        self.baseline_recording_presenter.on_recording_complete(filepath)

    def _on_recording_error(self, error_msg: str) -> None:
        """Handle recording error signal."""
        if hasattr(self, "baseline_capture_btn"):
            self.baseline_capture_btn.setText("?? Record 5-Min Baseline Data")
            self.baseline_capture_btn.setStyleSheet(
                "QPushButton {"
                "  background: #FF3B30;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 14px;"
                "  padding: 8px 16px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  font-family: {Fonts.SYSTEM};"
                "}"
                "QPushButton:hover {"
                "  background: #007AFF;"
                "}"
                "QPushButton:pressed {"
                "  background: #007AFF;"
                "}"
                "QPushButton:disabled {"
                "  background: #D1D1D6;"
                "  color: {Colors.SECONDARY_TEXT};"
                "}",
            )

        QMessageBox.critical(self, "Recording Error", f"❌ {error_msg}")
        logger.error(f"❌ Baseline recording error: {error_msg}")

    def _connect_signals(self) -> None:
        """Connect UI signals."""
        self.sidebar.scan_btn.clicked.connect(self._handle_scan_hardware)
        self.sidebar.add_hardware_btn.clicked.connect(self._handle_add_hardware)
        self.sidebar.debug_log_btn.clicked.connect(self._handle_debug_log_download)
        if hasattr(self.sidebar, 'issue_tracker_btn'):
            self.sidebar.issue_tracker_btn.clicked.connect(self._handle_open_issue_tracker)

        # Connect keyboard shortcuts
        from PySide6.QtGui import QKeySequence, QShortcut

        power_shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        power_shortcut.activated.connect(self._handle_power_click)

        # Demo data loader (Ctrl+Shift+D) for promotional screenshots
        demo_data_shortcut = QShortcut(QKeySequence("Ctrl+Shift+D"), self)
        demo_data_shortcut.activated.connect(self._load_demo_data)

        # OEM Issue Tracker (Ctrl+Shift+I)
        issue_shortcut = QShortcut(QKeySequence("Ctrl+Shift+I"), self)
        issue_shortcut.activated.connect(self._handle_open_issue_tracker)

        # Signal metrics panel toggle (Ctrl+Shift+M) — internal/dev use only
        # Hides/shows the λ · FWHM · p2p · slope section of the cycle footer
        sig_metrics_shortcut = QShortcut(QKeySequence("Ctrl+Shift+M"), self)
        sig_metrics_shortcut.activated.connect(self._toggle_signal_metrics_panel)

        # Queue panel toggle (Ctrl+Q)
        queue_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        queue_shortcut.activated.connect(lambda: self._live_queue_btn.toggle())

        # Channel selection shortcuts (Alt+A, Alt+B, Alt+C, Alt+D)
        for ch_idx, ch_letter in enumerate(['A', 'B', 'C', 'D']):
            shortcut = QShortcut(QKeySequence(f"Alt+{ch_letter}"), self)
            shortcut.activated.connect(
                lambda idx=ch_idx: self._on_curve_clicked(idx)
            )

        # Connect cycle management buttons
        # NOTE: start_cycle_btn, add_to_queue_btn, start_run_btn removed - now in Method Builder dialog
        # Queue management buttons are connected in sidebar itself via QueuePresenter
        # self.sidebar.start_cycle_btn.clicked.connect(self.start_cycle)  # DEPRECATED - moved to dialog
        # self.sidebar.start_run_btn.clicked.connect(self._on_start_queued_run)  # DELETED - duplicate button removed

        # Connect remaining queue buttons (if they exist)
        if hasattr(self.sidebar, 'clear_queue_btn'):
            self.sidebar.clear_queue_btn.clicked.connect(self._on_clear_queue)
        if hasattr(self.sidebar, 'open_table_btn'):
            self.sidebar.open_table_btn.clicked.connect(self.open_full_cycle_table)

        # Connect export buttons
        self.sidebar.export_data_btn.clicked.connect(self._on_export_data)
        self.sidebar.export_animl_btn.clicked.connect(self._on_export_animl)

        # Connect settings tab controls
        self.sidebar.advanced_settings_btn.clicked.connect(self.open_advanced_settings)
        self.sidebar.apply_settings_btn.clicked.connect(self._apply_settings)
        self.sidebar.polarizer_toggle_btn.clicked.connect(self._toggle_polarizer_mode)
        if hasattr(self, 'spark_bubble'):
            self.sidebar.spark_help_requested.connect(self.spark_bubble.toggle)
        self.sidebar.collapse_requested.connect(self._toggle_sidebar_collapse)

        # NOTE: ref_combo connection is done in main.py Application class
        # Cannot connect here because self.app is not available during UI init

        # Connect spectrum button if it exists (may be removed)
        if hasattr(self.sidebar, "spectrum_btn"):
            self.sidebar.spectrum_btn.clicked.connect(self._show_transmission_spectrum)

        # Pipeline selector REMOVED - only Fourier method used in production

        # Install event filter for Control+10-click detection on advanced settings button
        self.sidebar.advanced_settings_btn.installEventFilter(self)

        # Connect calibration buttons
        self.simple_led_calibration_btn.clicked.connect(
            self._handle_simple_led_calibration,
        )
        self.full_calibration_btn.clicked.connect(self._handle_full_calibration)
        if hasattr(self, "polarizer_calibration_btn"):
            self.polarizer_calibration_btn.clicked.connect(
                self._handle_polarizer_calibration,
            )

        # NOTE: OEM LED Calibration button connected in Application layer (main.py)
        # NOTE: Baseline Capture button connected in Application layer (main.py)
        # Do NOT connect here - UI builder shouldn't have app logic

        # === Optional: Connect to sidebar's signal abstraction layer (Change #3) ===
        # These provide a cleaner alternative to direct button connections above.
        # Comment out direct connections and use these signals for looser coupling:
        # self.sidebar.scan_requested.connect(self._handle_scan_hardware)
        # self.sidebar.export_requested.connect(self._on_export_data)
        # self.sidebar.debug_log_requested.connect(self._handle_debug_log_download)

        # NOTE: Hardware Configuration settings are loaded AFTER hardware connection
        # in _load_device_settings() called by hardware_event_coordinator, not during UI init

        # self.sidebar.polarizer_toggle_requested.connect(self._toggle_polarizer_mode)
        # self.sidebar.settings_apply_requested.connect(self._apply_settings)

        # Install element inspector for right-click inspection
        # DISABLED: Conflicts with Ctrl+Click flagging system
        # ElementInspector.install_inspector(self)

    def closeEvent(self, event):
        """Handle application close event - shutdown hardware gracefully and show unplug reminder if hardware connected."""
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            app_instance = QApplication.instance()

            # Capture connected device names BEFORE cleanup nulls-out the references
            devices_to_unplug = []
            if app_instance and hasattr(app_instance, 'hardware_mgr') and app_instance.hardware_mgr:
                hw_mgr = app_instance.hardware_mgr
                # HardwareManager stores the HAL-wrapped controller as 'ctrl' (not 'controller')
                if hasattr(hw_mgr, 'ctrl') and hw_mgr.ctrl is not None:
                    controller_name = getattr(hw_mgr.ctrl, 'name', 'Controller')
                    devices_to_unplug.append(controller_name)
                if hasattr(hw_mgr, 'pump') and hw_mgr.pump is not None:
                    devices_to_unplug.append('AffiPump')

            # CRITICAL: Always call application cleanup to ensure:
            # 1. LEDs are turned off (via disconnect_all → turn_off_channels → 'lx' command)
            # 2. Valves are powered off (prevent overheating)
            # 3. Pumps are stopped
            # NO EXIT PATH bypasses this graceful shutdown
            if app_instance and hasattr(app_instance, 'close'):
                logger.debug("Triggering graceful hardware shutdown...")
                app_instance.close()
                logger.debug("Hardware shutdown complete")

            if devices_to_unplug:
                try:
                    QMessageBox.information(
                        self,
                        "Unplug Devices",
                        f"Please unplug: {', '.join(devices_to_unplug)}",
                    )
                except Exception:
                    pass
        except Exception:
            pass
        super().closeEvent(event)

    # REMOVED: add_cycle_to_table() - DEPRECATED 12-column method (365 lines)
    # REMOVED: _populate_cycle_table_from_loaded_data() - DEPRECATED 11-column method
    # Use EditsTab.add_cycle() for live acquisition instead (6-column table)

# Main entry point
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindowPrototype()
    window.show()
    sys.exit(app.exec())

