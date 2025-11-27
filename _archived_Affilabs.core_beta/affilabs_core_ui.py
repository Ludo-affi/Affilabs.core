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
- EventBus integration for centralized signal routing
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
   - self.nav_buttons: List of main navigation buttons (Sensorgram, Edits, Analyze, Report)

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
   - update_afterglow_status(afterglow_sec: float): Update afterglow display

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

import sys
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, QParallelAnimationGroup, Signal, QEvent
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTabWidget, QLabel, QFrame, QToolButton, QScrollArea, QGraphicsDropShadowEffect,
    QSlider, QSpinBox, QSplitter, QMenu, QMessageBox, QCheckBox, QDialog, QLineEdit, QComboBox,
    QRadioButton, QButtonGroup, QFormLayout, QDialogButtonBox, QTextEdit, QGroupBox, QGridLayout, QProgressBar
)
from PySide6.QtGui import QIcon, QColor, QFont, QAction, QPainter, QPen, QPixmap

# Add Old software to path for imports
old_software = Path(__file__).parent
sys.path.insert(0, str(old_software))

from utils.logger import logger
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any, Union
from core.system_intelligence import get_system_intelligence, SystemState, IssueSeverity
from ui_styles import (
    Colors, Fonts, Dimensions,
    label_style, section_header_style, title_style, card_style,
    primary_button_style, secondary_button_style, segmented_button_style,
    checkbox_style, radio_button_style,
    slider_style, scrollbar_style, separator_style, divider_style,
    status_indicator_style, collapsible_header_style,
    line_edit_style, combo_box_style, group_box_style, text_edit_log_style, spinbox_style
)
from diagnostics_dialog import DiagnosticsDialog
from sections import CollapsibleSection
from sidebar import AffilabsSidebar
from plot_helpers import create_time_plot, add_channel_curves, create_spectroscopy_plot
from diagnostics_dialog import DiagnosticsDialog
from inspector import ElementInspector



class StartupCalibProgressDialog(QDialog):
    """Non-modal progress dialog for calibration with Start button integration."""

    start_clicked = Signal()  # Signal emitted when Start button is clicked
    retry_clicked = Signal()  # Signal emitted when Retry button is clicked
    continue_anyway_clicked = Signal()  # Signal emitted when Continue Anyway is clicked

    def __init__(self, parent: Optional[QWidget] = None, title: str = "Processing",
                 message: str = "Please wait...", show_start_button: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(False)  # Non-blocking - allows background processing
        self.setMinimumWidth(500)
        self.setMinimumHeight(200)
        self.setMaximumWidth(600)

        # Track dialog state to prevent race conditions
        self._is_closing = False
        self._is_complete = False
        self._is_error_state = False

        # Store parent for overlay and position tracking
        self.parent_window = parent
        self.overlay = None

        # Create semi-transparent overlay on parent window
        if self.parent_window:
            self.overlay = QWidget(self.parent_window)
            self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 0.5);")
            self.overlay.setGeometry(self.parent_window.rect())
            self.overlay.show()
            self.overlay.raise_()

            # Install event filter to track parent window movements
            self.parent_window.installEventFilter(self)

        # Remove window close button and make it frameless for modern look
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)

        # Style with border and rounded corners
        self.setStyleSheet(
            "QDialog { background: #FFFFFF; border: 2px solid #007AFF; border-radius: 12px; }"
            "QLabel { font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif; color: #1D1D1F; }"
        )

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(20)

        # Title
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            "font-size: 18px;"
            "font-weight: 700;"
            "color: #1D1D1F;"
        )
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.title_label)

        # Progress bar (can be indeterminate or real progress)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)  # Start in indeterminate mode
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(24)
        self.progress_bar.setVisible(False)  # Hidden initially for checklist
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setStyleSheet(
            "QProgressBar {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  border-radius: 4px;"
            "  border: 1px solid #D1D1D6;"
            "  color: #1D1D1F;"
            "  font-size: 12px;"
            "  font-weight: 700;"
            "  text-align: center;"
            "}"
            "QProgressBar::chunk {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007AFF, stop:1 #00C7BE);"
            "  border-radius: 4px;"
            "}"
        )
        main_layout.addWidget(self.progress_bar)

        # Status message
        self.status_label = QLabel(message)
        self.status_label.setStyleSheet(
            "font-size: 14px;"
            "color: #86868B;"
            "padding: 0px;"
        )
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(50)
        self.status_label.setMaximumHeight(150)
        main_layout.addWidget(self.status_label)

        # Add spacer for better vertical distribution
        main_layout.addSpacing(10)

        # Start button (optional, initially disabled if shown)
        self.start_button = None
        self.retry_button = None
        self.continue_button = None

        # Button container for dynamic button switching
        self.button_container = QWidget()
        self.button_layout = QHBoxLayout(self.button_container)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.addStretch()

        if show_start_button:
            self.start_button = QPushButton("Start")
            self.start_button.setEnabled(False)  # Start disabled
            self.start_button.setFixedSize(140, 36)
            self.start_button.setStyleSheet(
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
                "}"
            )
            self.start_button.clicked.connect(self._on_start_clicked)
            self.button_layout.addWidget(self.start_button)

        self.button_layout.addStretch()
        main_layout.addWidget(self.button_container)

        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        self.setGraphicsEffect(shadow)

        # Center on parent when dialog is initialized
        if self.parent_window:
            self._center_on_parent()

    def _on_start_clicked(self) -> None:
        """Handle start button click."""
        try:
            if not self._is_closing:
                # Check if this is the initial start (pre-calibration) or final start (post-calibration)
                if self._is_complete:
                    # Post-calibration: Emit signal to start acquisition, dialog will close after
                    from utils.logger import logger
                    logger.info("📋 Dialog Start button clicked (post-calibration) - emitting signal")
                    self.start_clicked.emit()
                    logger.info("📋 Signal emitted, dialog will close after acquisition starts")
                    # Don't close immediately - let coordinator close it after acquisition starts
                    # self._is_closing = True
                    # self.close()
                else:
                    # Pre-calibration: Emit signal but keep dialog open for progress updates
                    self.start_clicked.emit()
                    # Dialog stays open to show calibration progress
        except Exception as e:
            from utils.logger import logger
            logger.error(f"❌ Error in _on_start_clicked: {e}", exc_info=True)
            import traceback
            traceback.print_exc()

    def closeEvent(self, event: Any) -> None:
        """Clean up overlay when dialog closes."""
        self._is_closing = True

        # Remove event filter
        if self.parent_window:
            try:
                self.parent_window.removeEventFilter(self)
            except RuntimeError:
                pass

        if self.overlay:
            try:
                self.overlay.hide()
                self.overlay.deleteLater()
            except RuntimeError:
                pass  # Widget already deleted
            self.overlay = None
        super().closeEvent(event)

    def eventFilter(self, obj: Any, event: Any) -> bool:
        """Track parent window movements and reposition dialog."""
        if obj == self.parent_window and not self._is_closing:
            if event.type() == event.Type.Move:
                # Recenter dialog on parent
                self._center_on_parent()
            elif event.type() == event.Type.Resize:
                # Update overlay size
                if self.overlay:
                    self.overlay.setGeometry(self.parent_window.rect())
                # Recenter dialog
                self._center_on_parent()
        return super().eventFilter(obj, event)

    def _center_on_parent(self) -> None:
        """Center the dialog on the parent window."""
        if self.parent_window and not self._is_closing:
            parent_geometry = self.parent_window.geometry()
            dialog_width = self.width()
            dialog_height = self.height()

            x = parent_geometry.x() + (parent_geometry.width() - dialog_width) // 2
            y = parent_geometry.y() + (parent_geometry.height() - dialog_height) // 2

            self.move(x, y)

    def update_status(self, message: str) -> None:
        """Update the status message (thread-safe)."""
        if not self._is_closing and self.isVisible():
            try:
                self.status_label.setText(message)
            except RuntimeError:
                pass  # Widget deleted

    def update_title(self, title: str):
        """Update the title (thread-safe)."""
        if not self._is_closing and self.isVisible():
            try:
                self.title_label.setText(title)
                self.setWindowTitle(title)
            except RuntimeError:
                pass  # Widget deleted

    def set_progress(self, value: int, maximum: int = 100):
        """Set progress bar to show actual progress (thread-safe).

        Args:
            value: Current progress value
            maximum: Maximum progress value (default 100)
        """
        if not self._is_closing and self.isVisible():
            try:
                if self.progress_bar.maximum() == 0:  # Currently indeterminate
                    self.progress_bar.setMaximum(maximum)
                    self.progress_bar.setTextVisible(True)
                self.progress_bar.setValue(value)
                # Update text to show percentage
                if maximum > 0:
                    percentage = int((value / maximum) * 100)
                    self.progress_bar.setFormat(f"{percentage}%")
            except RuntimeError:
                pass  # Widget deleted

    def hide_progress_bar(self) -> None:
        """Hide progress bar (for checklist/pre-calibration state)."""
        if not self._is_closing and self.isVisible():
            try:
                self.progress_bar.hide()
            except RuntimeError:
                pass  # Widget deleted

    def show_progress_bar(self) -> None:
        """Show progress bar (when calibration starts)."""
        if not self._is_closing and self.isVisible():
            try:
                self.progress_bar.show()
                self.progress_bar.setMaximum(100)
                self.progress_bar.setValue(0)
            except RuntimeError:
                pass  # Widget deleted

    def enable_start_button_pre_calib(self) -> None:
        """Enable the Start button for pre-calibration checklist (thread-safe).

        Does NOT set _is_complete flag - dialog will stay open during calibration.
        """
        from utils.logger import logger
        logger.debug(f"🔧 enable_start_button_pre_calib() called: _is_complete={self._is_complete}")
        if not self._is_closing and self.isVisible() and self.start_button:
            try:
                self._is_error_state = False
                self.start_button.setEnabled(True)
                logger.debug(f"   ✅ Button enabled, _is_complete={self._is_complete} (should be False)")
            except RuntimeError:
                pass  # Widget deleted

    def enable_start_button(self) -> None:
        """Enable the Start button when calibration is complete (thread-safe)."""
        if not self._is_closing and self.isVisible() and self.start_button:
            try:
                self._is_complete = True
                self._is_error_state = False
                self.start_button.setEnabled(True)
            except RuntimeError:
                pass  # Widget deleted

    def show_error_state(self, error_message: str, retry_count: int, max_retries: int) -> None:
        """Switch dialog to error state with Retry/Continue buttons.

        Args:
            error_message: Error description to show
            retry_count: Current retry attempt
            max_retries: Maximum retry attempts allowed
        """
        if self._is_closing or not self.isVisible():
            return

        try:
            self._is_error_state = True
            self._is_complete = False

            # Update title and status
            self.title_label.setText("⚠️ Calibration Failed")
            self.title_label.setStyleSheet(
                "font-size: 18px;"
                "font-weight: 700;"
                "color: #FF3B30;"  # Red color for error
            )

            retries_left = max_retries - retry_count
            full_message = f"{error_message}\n\nRetries remaining: {retries_left}"
            self.status_label.setText(full_message)

            # Hide Start button if it exists
            if self.start_button:
                self.start_button.hide()

            # Create Retry and Continue buttons if they don't exist
            if not self.retry_button:
                self.retry_button = QPushButton("Retry Calibration")
                self.retry_button.setFixedSize(160, 36)
                self.retry_button.setStyleSheet(
                    "QPushButton {"
                    "  background: #007AFF;"
                    "  color: white;"
                    "  border: none;"
                    "  border-radius: 6px;"
                    "  font-size: 13px;"
                    "  font-weight: 600;"
                    "}"
                    "QPushButton:hover {"
                    "  background: #0051D5;"
                    "}"
                )
                self.retry_button.clicked.connect(self._on_retry_clicked)
                self.button_layout.insertWidget(1, self.retry_button)

            if not self.continue_button:
                self.continue_button = QPushButton("Continue Anyway")
                self.continue_button.setFixedSize(160, 36)
                self.continue_button.setStyleSheet(
                    "QPushButton {"
                    "  background: #FF9500;"
                    "  color: white;"
                    "  border: none;"
                    "  border-radius: 6px;"
                    "  font-size: 13px;"
                    "  font-weight: 600;"
                    "}"
                    "QPushButton:hover {"
                    "  background: #FF8000;"
                    "}"
                )
                self.continue_button.clicked.connect(self._on_continue_clicked)
                self.button_layout.insertWidget(2, self.continue_button)

            self.retry_button.show()
            self.continue_button.show()

        except RuntimeError:
            pass  # Widget deleted

    def show_max_retries_error(self, error_message: str):
        """Show error state when max retries reached - only Continue button.

        Args:
            error_message: Error description to show
        """
        if self._is_closing or not self.isVisible():
            return

        try:
            self._is_error_state = True

            # Update title and status
            self.title_label.setText("🛑 Calibration Failed")
            self.status_label.setText(f"{error_message}\n\nMaximum retry attempts reached.\nPlease contact technical support.")

            # Hide Start and Retry buttons
            if self.start_button:
                self.start_button.hide()
            if self.retry_button:
                self.retry_button.hide()

            # Show only Continue button
            if not self.continue_button:
                self.continue_button = QPushButton("Continue Anyway")
                self.continue_button.setFixedSize(160, 36)
                self.continue_button.setStyleSheet(
                    "QPushButton {"
                    "  background: #FF9500;"
                    "  color: white;"
                    "  border: none;"
                    "  border-radius: 6px;"
                    "  font-size: 13px;"
                    "  font-weight: 600;"
                    "}"
                    "QPushButton:hover {"
                    "  background: #FF8000;"
                    "}"
                )
                self.continue_button.clicked.connect(self._on_continue_clicked)
                self.button_layout.insertWidget(1, self.continue_button)

            self.continue_button.show()

        except RuntimeError:
            pass  # Widget deleted

    def reset_to_progress_state(self):
        """Reset dialog back to progress state (for retry)."""
        if self._is_closing or not self.isVisible():
            return

        try:
            self._is_error_state = False
            self._is_complete = False

            # Reset title color
            self.title_label.setStyleSheet(
                "font-size: 18px;"
                "font-weight: 700;"
                "color: #1D1D1F;"
            )

            # Hide error buttons
            if self.retry_button:
                self.retry_button.hide()
            if self.continue_button:
                self.continue_button.hide()

            # Reset progress bar
            self.progress_bar.setValue(0)

        except RuntimeError:
            pass  # Widget deleted

    def _on_retry_clicked(self) -> None:
        """Handle retry button click."""
        if not self._is_closing:
            self.retry_clicked.emit()

    def _on_continue_clicked(self) -> None:
        """Handle continue anyway button click."""
        if not self._is_closing:
            self.continue_anyway_clicked.emit()


class DeviceConfigDialog(QDialog):
    """Dialog to collect missing device configuration information."""

    def __init__(self, parent: Optional[QWidget] = None, device_serial: Optional[str] = None, controller_type: str = '', controller=None, device_config=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Device Configuration Required")
        self.setFixedWidth(500)
        self.setModal(True)
        self.controller_type = controller_type
        self.controller = controller  # For EEPROM sync
        self.device_config = device_config  # DeviceConfiguration instance

        # Apply modern styling
        self.setStyleSheet(
            "QDialog {"
            "  background: #FFFFFF;"
            "  border: 2px solid #007AFF;"
            "  border-radius: 12px;"
            "}"
            "QLabel {"
            "  color: #1D1D1F;"
            "  font-size: 13px;"
            "}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Title
        title = QLabel("⚙️ Device Configuration")
        title.setStyleSheet(
            "font-size: 20px;"
            "font-weight: 600;"
            "color: #1D1D1F;"
        )
        layout.addWidget(title)

        # Description
        desc = QLabel(f"Please provide the following information for device:\n<b>{device_serial or 'Unknown'}</b>")
        desc.setTextFormat(Qt.TextFormat.RichText)  # Enable HTML formatting
        desc.setStyleSheet(
            "font-size: 13px;"
            "color: #86868B;"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Config source indicator (EEPROM vs JSON)
        self.config_source_label = QLabel()
        self.config_source_label.setStyleSheet(
            "font-size: 12px;"
            "color: #86868B;"
            "padding: 8px 12px;"
            "background: #F5F5F7;"
            "border-radius: 6px;"
        )
        self._update_config_source_indicator()
        layout.addWidget(self.config_source_label)

        # Form layout
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Shared combo box styling
        combo_style = (
            "QComboBox {"
            "  padding: 8px 12px;"
            "  border: 1px solid #D1D1D6;"
            "  border-radius: 6px;"
            "  background: #FFFFFF;"
            "  font-size: 13px;"
            "  color: #1D1D1F;"
            "  min-height: 20px;"
            "}"
            "QComboBox:hover {"
            "  border: 1px solid #007AFF;"
            "}"
            "QComboBox:focus {"
            "  border: 2px solid #007AFF;"
            "}"
            "QComboBox:disabled {"
            "  background: #F5F5F7;"
            "  color: #86868B;"
            "}"
            "QComboBox::drop-down {"
            "  border: none;"
            "  width: 30px;"
            "  subcontrol-origin: padding;"
            "  subcontrol-position: center right;"
            "}"
            "QComboBox::down-arrow {"
            "  image: none;"
            "  border-left: 5px solid transparent;"
            "  border-right: 5px solid transparent;"
            "  border-top: 6px solid #86868B;"
            "  width: 0;"
            "  height: 0;"
            "}"
            "QComboBox QAbstractItemView {"
            "  border: 1px solid #D1D1D6;"
            "  border-radius: 6px;"
            "  background: #FFFFFF;"
            "  selection-background-color: #007AFF;"
            "  selection-color: #FFFFFF;"
            "  padding: 4px;"
            "  outline: none;"
            "}"
            "QComboBox QAbstractItemView::item {"
            "  padding: 8px 12px;"
            "  border-radius: 4px;"
            "  color: #1D1D1F;"
            "  min-height: 24px;"
            "}"
            "QComboBox QAbstractItemView::item:hover {"
            "  background: #F5F5F7;"
            "}"
            "QComboBox QAbstractItemView::item:selected {"
            "  background: #007AFF;"
            "  color: #FFFFFF;"
            "}"
        )

        # Shared input styling
        input_style = (
            "QLineEdit {"
            "  padding: 6px 12px;"
            "  border: 1px solid #D1D1D6;"
            "  border-radius: 6px;"
            "  background: #FFFFFF;"
            "  font-size: 13px;"
            "}"
            "QLineEdit:focus {"
            "  border: 2px solid #007AFF;"
            "}"
        )

        # LED Model (LCW or OWW)
        self.led_model_combo = QComboBox()
        self.led_model_combo.addItems(['LCW', 'OWW'])
        self.led_model_combo.setStyleSheet(combo_style)
        form.addRow("LED Model:", self.led_model_combo)

        # Controller Options (hardware types excluding pumps)
        self.controller_combo = QComboBox()
        self.controller_combo.addItems(['Arduino', 'PicoP4SPR', 'PicoEZSPR'])
        self.controller_combo.setStyleSheet(combo_style)

        # Pre-select based on detected controller type
        if self.controller_type in ['Arduino', 'PicoP4SPR', 'PicoEZSPR']:
            index = self.controller_combo.findText(self.controller_type)
            if index >= 0:
                self.controller_combo.setCurrentIndex(index)

        # Connect change to update polarizer
        self.controller_combo.currentTextChanged.connect(self._on_controller_changed)
        form.addRow("Controller:", self.controller_combo)

        # Fiber Diameter (A=100, B=200)
        self.fiber_diameter_combo = QComboBox()
        self.fiber_diameter_combo.addItems(['A (100 µm)', 'B (200 µm)'])
        self.fiber_diameter_combo.setStyleSheet(combo_style)
        form.addRow("Fiber Diameter:", self.fiber_diameter_combo)

        # Polarizer Type (barrel or circle, default circle for Arduino/PicoP4SPR)
        self.polarizer_type_combo = QComboBox()
        self.polarizer_type_combo.addItems(['circle', 'barrel'])
        self.polarizer_type_combo.setStyleSheet(combo_style)

        # Set default based on controller
        self._update_polarizer_default()

        form.addRow("Polarizer:", self.polarizer_type_combo)

        # Device ID (detector serial number)
        self.device_id_input = QLineEdit()
        self.device_id_input.setPlaceholderText("Enter detector serial number")
        self.device_id_input.setText(device_serial or "")  # Pre-fill with detected serial
        self.device_id_input.setStyleSheet(input_style)
        form.addRow("Device ID:", self.device_id_input)

        layout.addLayout(form)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            "QPushButton {"
            "  padding: 8px 20px;"
            "  background: #F5F5F7;"
            "  border: none;"
            "  border-radius: 6px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  color: #1D1D1F;"
            "}"
            "QPushButton:hover {"
            "  background: #E5E5E7;"
            "}"
        )
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        # Push to EEPROM button (only show if controller connected)
        if self.controller is not None:
            eeprom_btn = QPushButton("Push to EEPROM")
            eeprom_btn.setStyleSheet(
                "QPushButton {"
                "  padding: 8px 20px;"
                "  background: #FF9500;"
                "  border: none;"
                "  border-radius: 6px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  color: #FFFFFF;"
                "}"
                "QPushButton:hover {"
                "  background: #FF8000;"
                "}"
                "QPushButton:disabled {"
                "  background: #E5E5E7;"
                "  color: #86868B;"
                "}"
            )
            eeprom_btn.setToolTip("Save configuration to device EEPROM for portable backup")
            eeprom_btn.clicked.connect(self._on_push_to_eeprom)
            button_layout.addWidget(eeprom_btn)

        save_btn = QPushButton("Save Configuration")
        save_btn.setStyleSheet(
            "QPushButton {"
            "  padding: 8px 20px;"
            "  background: #007AFF;"
            "  border: none;"
            "  border-radius: 6px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  color: #FFFFFF;"
            "}"
            "QPushButton:hover {"
            "  background: #0051D5;"
            "}"
        )
        save_btn.clicked.connect(self.accept)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        self.setGraphicsEffect(shadow)

    def _on_controller_changed(self, controller_text):
        """Update polarizer default when controller changes."""
        self.controller_type = controller_text
        self._update_polarizer_default()

    def _update_polarizer_default(self):
        """Set polarizer default based on controller type."""
        if self.controller_type in ['Arduino', 'PicoP4SPR']:
            self.polarizer_type_combo.setCurrentText('circle')
        elif self.controller_type == 'PicoEZSPR':
            self.polarizer_type_combo.setCurrentText('barrel')

    def _update_config_source_indicator(self):
        """Update the config source indicator label."""
        if self.device_config is None:
            self.config_source_label.setText("ℹ️ New configuration")
            return

        if hasattr(self.device_config, 'loaded_from_eeprom') and self.device_config.loaded_from_eeprom:
            self.config_source_label.setText("📦 Configuration loaded from EEPROM")
            self.config_source_label.setStyleSheet(
                "font-size: 12px;"
                "color: #FF9500;"
                "padding: 8px 12px;"
                "background: #FFF3E0;"
                "border-radius: 6px;"
            )
        else:
            self.config_source_label.setText("💾 Configuration loaded from JSON file")
            self.config_source_label.setStyleSheet(
                "font-size: 12px;"
                "color: #34C759;"
                "padding: 8px 12px;"
                "background: #E8F5E9;"
                "border-radius: 6px;"
            )

    def _on_push_to_eeprom(self):
        """Push current form configuration to EEPROM."""
        if self.controller is None:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "No Controller",
                "Cannot push to EEPROM: No controller connected."
            )
            return

        # Update device_config with current form values (if it exists)
        if self.device_config is not None:
            config_data = self.get_config_data()
            self.device_config.set_hardware_config(
                led_pcb_model=config_data['led_pcb_model'],
                optical_fiber_diameter_um=config_data['optical_fiber_diameter_um'],
                polarizer_type=config_data['polarizer_type']
            )

        # Sync to EEPROM
        from utils.logger import logger
        logger.info("Pushing configuration to EEPROM...")

        if self.device_config is not None:
            success = self.device_config.sync_to_eeprom(self.controller)
        else:
            # No device_config yet - create temporary EEPROM config from form
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "Save First",
                "Please save the configuration to JSON first, then push to EEPROM."
            )
            return

        # Show result
        from PySide6.QtWidgets import QMessageBox
        if success:
            QMessageBox.information(
                self,
                "EEPROM Sync Complete",
                "✓ Configuration successfully pushed to device EEPROM.\n\n"
                "The device can now be used on other computers without reconfiguration."
            )
            logger.info("✓ EEPROM sync successful")
        else:
            QMessageBox.warning(
                self,
                "EEPROM Sync Failed",
                "Failed to push configuration to EEPROM.\n\n"
                "Check the logs for details."
            )
            logger.error("✗ EEPROM sync failed")

    def get_config_data(self):
        """Get the configuration data from the form."""
        # Map LED model abbreviations to full names
        led_model_map = {
            'LCW': 'luminus_cool_white',
            'OWW': 'osram_warm_white'
        }

        # Extract fiber diameter from selection (e.g., "A (100 µm)" -> 100)
        fiber_text = self.fiber_diameter_combo.currentText()
        if 'A' in fiber_text:
            fiber_diameter = 100
        elif 'B' in fiber_text:
            fiber_diameter = 200
        else:
            fiber_diameter = 200  # Default

        # Get controller type
        controller_type = self.controller_combo.currentText()

        # Determine controller model name from type
        controller_model = 'Raspberry Pi Pico P4SPR'  # Default
        if controller_type == 'Arduino':
            controller_model = 'Arduino P4SPR'
        elif controller_type == 'PicoP4SPR':
            controller_model = 'Raspberry Pi Pico P4SPR'
        elif controller_type == 'PicoEZSPR':
            controller_model = 'Raspberry Pi Pico EZSPR'

        return {
            'led_pcb_model': led_model_map.get(self.led_model_combo.currentText(), 'luminus_cool_white'),
            'optical_fiber_diameter_um': fiber_diameter,
            'polarizer_type': self.polarizer_type_combo.currentText(),
            'device_id': self.device_id_input.text().strip() or None,
            'controller_model': controller_model,
            'controller_type': controller_type,
        }


class AdvancedSettingsDialog(QDialog):
    """Advanced Settings Dialog for power users."""

    def __init__(self, parent=None, unlocked=False):
        super().__init__(parent)
        self.setWindowTitle("Advanced Settings")
        self.setModal(True)
        self.setMinimumWidth(550)
        self.advanced_params_unlocked = unlocked

        # Style
        self.setStyleSheet(
            "QDialog {"
            "  background: #FFFFFF;"
            "}"
            "QLabel {"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "  color: #1D1D1F;"
            "}"
        )

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        # Title
        title = QLabel("Advanced Settings")
        title.setStyleSheet(title_style(20) + "margin-bottom: 8px;")
        main_layout.addWidget(title)

        # Tab widget for Settings and Diagnostics (if DEV mode)
        self.tabs = QTabWidget()
        tab_widget_style = (
            "QTabWidget::pane { border: none; }"
            "QTabBar::tab { padding: 8px 20px; margin-right: 4px; "
            f"background: {Colors.BACKGROUND_LIGHT}; border-top-left-radius: 6px; "
            "border-top-right-radius: 6px; font-size: 13px; font-weight: 500; }"
            f"QTabBar::tab:selected {{ background: white; color: {Colors.PRIMARY_TEXT}; }}"
            f"QTabBar::tab:!selected {{ color: {Colors.SECONDARY_TEXT}; }}"
        )
        self.tabs.setStyleSheet(tab_widget_style)

        # Settings tab (main content)
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(0, 16, 0, 0)

        # Form layout for settings
        form = QFormLayout()
        form.setSpacing(16)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Unit Selection (moved from Settings tab)
        unit_label = QLabel("Unit:")
        unit_label.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 600))

        unit_container = QWidget()
        unit_layout = QHBoxLayout(unit_container)
        unit_layout.setContentsMargins(0, 0, 0, 0)
        unit_layout.setSpacing(0)

        self.unit_button_group = QButtonGroup()
        self.unit_button_group.setExclusive(True)

        self.ru_btn = QPushButton("RU")
        self.ru_btn.setCheckable(True)
        self.ru_btn.setChecked(True)
        self.ru_btn.setFixedHeight(28)
        self.ru_btn.setStyleSheet(segmented_button_style("left"))
        self.unit_button_group.addButton(self.ru_btn, 0)
        unit_layout.addWidget(self.ru_btn)

        self.nm_btn = QPushButton("nm")
        self.nm_btn.setCheckable(True)
        self.nm_btn.setFixedHeight(28)
        self.nm_btn.setStyleSheet(segmented_button_style("right"))
        self.unit_button_group.addButton(self.nm_btn, 1)
        unit_layout.addWidget(self.nm_btn)
        unit_layout.addStretch()

        form.addRow(unit_label, unit_container)

        # PRE LED Delay (ms) - Pre-LED delay before measurement
        led_delay_label = QLabel("PRE LED Delay:")
        led_delay_label.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 600))
        self.led_delay_input = QSpinBox()
        self.led_delay_input.setRange(0, 200)
        self.led_delay_input.setValue(45)  # Default from PRE_LED_DELAY_MS
        self.led_delay_input.setSuffix(" ms")
        self.led_delay_input.setFixedWidth(120)
        self.led_delay_input.setStyleSheet(spinbox_style())
        form.addRow(led_delay_label, self.led_delay_input)

        # POST LED Delay (ms) - Post-LED delay after turn-off
        post_led_delay_label = QLabel("POST LED Delay:")
        post_led_delay_label.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 600))
        self.post_led_delay_input = QSpinBox()
        self.post_led_delay_input.setRange(0, 100)
        self.post_led_delay_input.setValue(5)  # Default from POST_LED_DELAY_MS
        self.post_led_delay_input.setSuffix(" ms")
        self.post_led_delay_input.setFixedWidth(120)
        self.post_led_delay_input.setStyleSheet(spinbox_style())
        form.addRow(post_led_delay_label, self.post_led_delay_input)

        # Pipeline Selection
        pipeline_label = QLabel("Data Pipeline:")
        pipeline_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.pipeline_combo = QComboBox()
        self.pipeline_combo.addItems([
            "Pipeline 1 (Fourier Weighted)",
            "Pipeline 2 (Adaptive Multi-Feature)"
        ])
        self.pipeline_combo.setFixedWidth(300)
        self.pipeline_combo.setStyleSheet(
            "QComboBox {"
            "  padding: 6px 8px;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "  background: white;"
            "  font-size: 13px;"
            "}"
            "QComboBox::drop-down {"
            "  border: none;"
            "  width: 30px;"
            "}"
            "QComboBox::down-arrow {"
            "  image: none;"
            "  border-left: 4px solid transparent;"
            "  border-right: 4px solid transparent;"
            "  border-top: 5px solid #86868B;"
            "  margin-right: 8px;"
            "}"
        )
        form.addRow(pipeline_label, self.pipeline_combo)

        # Data Filtering Options (moved from Graphic Control tab)
        filter_label = QLabel("Data Filtering:")
        filter_label.setStyleSheet("font-weight: 600; font-size: 13px;")

        filter_container = QWidget()
        filter_layout = QHBoxLayout(filter_container)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(12)

        self.filter_method_group = QButtonGroup()

        self.filter1_radio = QRadioButton("Filter 1")
        self.filter1_radio.setChecked(True)
        self.filter1_radio.setStyleSheet(
            "QRadioButton {"
            "  font-size: 12px;"
            "  spacing: 4px;"
            "}"
            "QRadioButton::indicator {"
            "  width: 14px;"
            "  height: 14px;"
            "  border: 1px solid rgba(0, 0, 0, 0.2);"
            "  border-radius: 7px;"
            "  background: white;"
            "}"
            "QRadioButton::indicator:checked {"
            "  background: #1D1D1F;"
            "  border: 3px solid white;"
            "  outline: 1px solid #1D1D1F;"
            "}"
        )
        self.filter_method_group.addButton(self.filter1_radio, 0)
        filter_layout.addWidget(self.filter1_radio)

        self.filter2_radio = QRadioButton("Filter 2")
        self.filter2_radio.setStyleSheet(self.filter1_radio.styleSheet())
        self.filter_method_group.addButton(self.filter2_radio, 1)
        filter_layout.addWidget(self.filter2_radio)

        self.filter3_radio = QRadioButton("Filter 3")
        self.filter3_radio.setStyleSheet(self.filter1_radio.styleSheet())
        self.filter_method_group.addButton(self.filter3_radio, 2)
        filter_layout.addWidget(self.filter3_radio)

        filter_layout.addStretch()

        form.addRow(filter_label, filter_container)

        main_layout.addLayout(form)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(divider_style())
        main_layout.addWidget(separator)

        # Device Information Section
        info_section = QLabel("Device Information")
        info_section.setStyleSheet(title_style(15) + "margin-top: 4px;")
        main_layout.addWidget(info_section)

        # Device info layout
        device_info = QFormLayout()
        device_info.setSpacing(12)
        device_info.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Serial Number
        serial_label = QLabel("Serial Number:")
        serial_label.setStyleSheet(label_style(13, Colors.SECONDARY_TEXT))
        self.serial_value = QLabel("Not detected")
        self.serial_value.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 500))
        device_info.addRow(serial_label, self.serial_value)

        # Afterglow Calibration Status
        afterglow_label = QLabel("Afterglow Calibration:")
        afterglow_label.setStyleSheet(label_style(13, Colors.SECONDARY_TEXT))
        self.afterglow_value = QLabel("Not calibrated")
        self.afterglow_value.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 500))
        device_info.addRow(afterglow_label, self.afterglow_value)

        # Calibration Date
        cal_date_label = QLabel("Calibration Date:")
        cal_date_label.setStyleSheet(label_style(13, Colors.SECONDARY_TEXT))
        self.cal_date_value = QLabel("N/A")
        self.cal_date_value.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 500))
        device_info.addRow(cal_date_label, self.cal_date_value)

        main_layout.addLayout(device_info)

        main_layout.addStretch()

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        dialog_button_style = (
            "QPushButton { padding: 8px 20px; border-radius: 6px; font-size: 13px; font-weight: 600; min-width: 80px; }"
            f"QPushButton[text='OK'] {{ background: {Colors.PRIMARY_TEXT}; color: white; border: none; }}"
            "QPushButton[text='OK']:hover { background: #3A3A3C; }"
            f"QPushButton[text='Cancel'] {{ background: white; color: {Colors.PRIMARY_TEXT}; border: 1px solid {Colors.OVERLAY_LIGHT_10}; }}"
            f"QPushButton[text='Cancel']:hover {{ background: {Colors.OVERLAY_LIGHT_6}; }}"
        )
        button_box.setStyleSheet(dialog_button_style)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        # === Add Diagnostics Tab (hidden unless DEV mode) ===
        self._setup_diagnostics_tab()

    def _setup_diagnostics_tab(self):
        """Setup diagnostics tab that shows all QC details and calibration data.

        This tab is hidden in user mode and only visible in dev/support mode or when unlocked.
        """
        try:
            # Check if DEV mode is enabled
            from settings import DEV
            dev_mode = DEV
        except ImportError:
            dev_mode = False

        # Show diagnostics if DEV mode is enabled OR if unlocked via Control+10-click
        if not dev_mode and not self.advanced_params_unlocked:
            return  # Don't create diagnostics tab in user mode

        # Replace the main layout with a tab widget
        # Save the current main layout content
        current_widget = self.layout().takeAt(0)

        # Create tab widget
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet(
            "QTabWidget::pane {"
            "  border: none;"
            "  background: white;"
            "}"
            "QTabBar::tab {"
            "  padding: 10px 24px;"
            "  margin-right: 4px;"
            "  background: #F5F5F7;"
            "  border-top-left-radius: 8px;"
            "  border-top-right-radius: 8px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "}"
            "QTabBar::tab:selected {"
            "  background: white;"
            "  color: #1D1D1F;"
            "}"
            "QTabBar::tab:!selected {"
            "  color: #86868B;"
            "}"
            "QTabBar::tab:hover:!selected {"
            "  background: #E8E8EA;"
            "}"
        )

        # Move existing content to "Settings" tab
        settings_container = QWidget()
        settings_layout = QVBoxLayout(settings_container)
        settings_layout.setContentsMargins(0, 0, 0, 0)

        # Rebuild the settings content in the container
        # (The existing main_layout widgets are already created)
        # We'll just wrap them in the tab

        # Create "Diagnostics" tab
        diagnostics_widget = QWidget()
        diag_layout = QVBoxLayout(diagnostics_widget)
        diag_layout.setContentsMargins(20, 20, 20, 20)
        diag_layout.setSpacing(16)

        # Diagnostics title
        diag_title = QLabel("🔧 System Diagnostics & Quality Control")
        diag_title.setStyleSheet(
            "font-size: 18px;"
            "font-weight: 700;"
            "color: #1D1D1F;"
            "margin-bottom: 12px;"
        )
        diag_layout.addWidget(diag_title)

        # Scroll area for diagnostics content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: white; border: none; }")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(20)

        # === Calibration Data Section ===
        cal_group = QGroupBox("📊 Calibration Data")
        cal_group.setStyleSheet(group_box_style())
        cal_layout = QGridLayout()
        cal_layout.setSpacing(12)
        cal_layout.setColumnStretch(1, 1)

        # Calibration fields
        cal_fields = [
            ("Integration Time:", "integration_time_diag"),
            ("Number of Scans:", "num_scans_diag"),
            ("LED Intensity A:", "led_a_diag"),
            ("LED Intensity B:", "led_b_diag"),
            ("LED Intensity C:", "led_c_diag"),
            ("LED Intensity D:", "led_d_diag"),
            ("S-mode Position:", "s_pos_diag"),
            ("P-mode Position:", "p_pos_diag"),
        ]

        for row, (label_text, attr_name) in enumerate(cal_fields):
            label = QLabel(label_text)
            label.setStyleSheet("font-size: 12px; color: #86868B;")
            value = QLabel("N/A")
            value.setStyleSheet("font-size: 12px; color: #1D1D1F; font-family: 'Consolas', 'Courier New', monospace;")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            setattr(self, attr_name, value)
            cal_layout.addWidget(label, row, 0, Qt.AlignmentFlag.AlignRight)
            cal_layout.addWidget(value, row, 1)

        cal_group.setLayout(cal_layout)
        scroll_layout.addWidget(cal_group)

        # === S-ref Quality Metrics ===
        sref_group = QGroupBox("📈 S-ref Signal Quality")
        sref_group.setStyleSheet(cal_group.styleSheet())
        sref_layout = QGridLayout()
        sref_layout.setSpacing(12)
        sref_layout.setColumnStretch(1, 1)

        sref_fields = [
            ("Channel A Signal:", "sref_a_diag"),
            ("Channel B Signal:", "sref_b_diag"),
            ("Channel C Signal:", "sref_c_diag"),
            ("Channel D Signal:", "sref_d_diag"),
            ("Target Counts:", "sref_target_diag"),
            ("Detector Max:", "detector_max_diag"),
        ]

        for row, (label_text, attr_name) in enumerate(sref_fields):
            label = QLabel(label_text)
            label.setStyleSheet("font-size: 12px; color: #86868B;")
            value = QLabel("N/A")
            value.setStyleSheet("font-size: 12px; color: #1D1D1F; font-family: 'Consolas', 'Courier New', monospace;")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            setattr(self, attr_name, value)
            sref_layout.addWidget(label, row, 0, Qt.AlignmentFlag.AlignRight)
            sref_layout.addWidget(value, row, 1)

        sref_group.setLayout(sref_layout)
        scroll_layout.addWidget(sref_group)

        # === SENSOR IQ & DATA QUALITY ===
        sensor_iq_group = QGroupBox("🎯 Sensor IQ - Data Quality Assessment")
        sensor_iq_group.setStyleSheet(cal_group.styleSheet())
        sensor_iq_layout = QGridLayout()
        sensor_iq_layout.setSpacing(12)
        sensor_iq_layout.setColumnStretch(1, 1)

        sensor_iq_fields = [
            ("Channel A IQ:", "sensor_iq_a_diag"),
            ("Channel B IQ:", "sensor_iq_b_diag"),
            ("Channel C IQ:", "sensor_iq_c_diag"),
            ("Channel D IQ:", "sensor_iq_d_diag"),
            ("Quality Zones:", "sensor_iq_zones_diag"),
            ("FWHM Thresholds:", "sensor_iq_fwhm_diag"),
        ]

        for row, (label_text, attr_name) in enumerate(sensor_iq_fields):
            label = QLabel(label_text)
            label.setStyleSheet("font-size: 12px; color: #86868B;")
            value = QLabel("N/A")
            value.setStyleSheet("font-size: 12px; color: #1D1D1F; font-family: 'Consolas', 'Courier New', monospace;")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            setattr(self, attr_name, value)
            sensor_iq_layout.addWidget(label, row, 0, Qt.AlignmentFlag.AlignRight)
            sensor_iq_layout.addWidget(value, row, 1)

        sensor_iq_group.setLayout(sensor_iq_layout)
        scroll_layout.addWidget(sensor_iq_group)

        # === System Status ===
        status_group = QGroupBox("⚙️ System Status")
        status_group.setStyleSheet(cal_group.styleSheet())
        status_layout = QGridLayout()
        status_layout.setSpacing(12)
        status_layout.setColumnStretch(1, 1)

        status_fields = [
            ("Detector Type:", "detector_type_diag"),
            ("Detector Serial:", "detector_serial_diag"),
            ("Num Pixels:", "num_pixels_diag"),
            ("Wavelength Range:", "wavelength_range_diag"),
            ("QC Mode:", "qc_mode_diag"),
            ("Afterglow Model:", "afterglow_model_diag"),
        ]

        for row, (label_text, attr_name) in enumerate(status_fields):
            label = QLabel(label_text)
            label.setStyleSheet("font-size: 12px; color: #86868B;")
            value = QLabel("N/A")
            value.setStyleSheet("font-size: 12px; color: #1D1D1F; font-family: 'Consolas', 'Courier New', monospace;")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            setattr(self, attr_name, value)
            status_layout.addWidget(label, row, 0, Qt.AlignmentFlag.AlignRight)
            status_layout.addWidget(value, row, 1)

        status_group.setLayout(status_layout)
        scroll_layout.addWidget(status_group)

        # === Raw Log Output ===
        log_group = QGroupBox("📝 Debug Log (Last 50 lines)")
        log_group.setStyleSheet(cal_group.styleSheet())
        log_layout = QVBoxLayout()

        self.diag_log_output = QTextEdit()
        self.diag_log_output.setReadOnly(True)
        self.diag_log_output.setStyleSheet(
            "QTextEdit {"
            "  background: #F5F5F7;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "  padding: 12px;"
            "  font-family: 'Consolas', 'Courier New', monospace;"
            "  font-size: 11px;"
            "  color: #1D1D1F;"
            "}"
        )
        self.diag_log_output.setMaximumHeight(300)
        self.diag_log_output.setPlainText("Log output will appear here when available...")

        log_layout.addWidget(self.diag_log_output)
        log_group.setLayout(log_layout)
        scroll_layout.addWidget(log_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        diag_layout.addWidget(scroll)

        # Note: We can't easily restructure the existing dialog to use tabs
        # without major refactoring, so we'll add a "Show Diagnostics" button instead
        # This is simpler and less invasive

        # Remove tab widget idea, just add a button to show diagnostics window
        self._setup_diagnostics_button()

    def _setup_diagnostics_button(self):
        """Add a diagnostics button to show the diagnostics window."""
        # Find the button box and add our button before it
        button_box = self.findChild(QDialogButtonBox)
        if button_box:
            # Add diagnostics button to the left side
            diag_btn = QPushButton("🔧 Diagnostics")
            diag_btn.setStyleSheet(
                "QPushButton {"
                "  background: #F5F5F7;"
                "  color: #1D1D1F;"
                "  border: 1px solid rgba(0, 0, 0, 0.1);"
                "  border-radius: 6px;"
                "  padding: 8px 20px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  min-width: 120px;"
                "}"
                "QPushButton:hover {"
                "  background: #E8E8EA;"
                "}"
            )
            diag_btn.clicked.connect(self._show_diagnostics)
            button_box.addButton(diag_btn, QDialogButtonBox.ButtonRole.ActionRole)

    def _show_diagnostics(self):
        """Show diagnostics window with all QC data."""
        diag_dialog = DiagnosticsDialog(self)
        diag_dialog.load_diagnostics_data(self.parent())
        diag_dialog.exec()

    def load_device_info(self, serial="Not detected", afterglow_cal=False, cal_date=None):
        """Load device information into the dialog."""
        self.serial_value.setText(serial if serial else "Not detected")

        if afterglow_cal:
            self.afterglow_value.setText("✓ Calibrated")
            self.afterglow_value.setStyleSheet("font-size: 13px; color: #34C759; font-weight: 600;")
        else:
            self.afterglow_value.setText("Not calibrated")
            self.afterglow_value.setStyleSheet("font-size: 13px; color: #FF9500; font-weight: 600;")

        if cal_date:
            if isinstance(cal_date, str):
                self.cal_date_value.setText(cal_date)
            else:
                self.cal_date_value.setText(cal_date.strftime("%Y-%m-%d %H:%M"))
        else:
            self.cal_date_value.setText("N/A")




class AffilabsMainWindow(QMainWindow):
    """Production main window for AffiLabs.core application.

    QUICK REFERENCE FOR INTEGRATION:
    ================================
    Signals (UI → App):
        - power_on_requested / power_off_requested
        - recording_start_requested / recording_stop_requested
        - acquisition_pause_requested(bool)

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

    def __init__(self, event_bus=None):
        super().__init__()
        self.setWindowTitle("AI - AffiLabs.core")
        self.setWindowIcon(QIcon("ui/img/affinite2.ico"))
        self.setGeometry(100, 100, 1400, 900)
        self.nav_buttons = []
        self.is_recording = False
        self.recording_indicator = None
        self.record_button = None

        # Store event bus reference
        self.event_bus = event_bus

        # Device configuration and maintenance tracking
        self.device_config = None
        self.led_start_time = None
        self.last_powered_on = None

        # OEM provisioning flag - set to True when device config dialog completes
        # Used to trigger calibration when spectrometer is connected after config
        self.oem_config_just_completed = False

        # Live data flag (default enabled)
        self.live_data_enabled = True

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
        self.max_queue_size = 5

        # Countdown timer for cycle tracking
        self.cycle_countdown_timer = QTimer()
        self.cycle_countdown_timer.timeout.connect(self._update_countdown)
        self.cycle_start_time = None
        self.cycle_duration_seconds = 0

        # Initialize intelligence bar refresh timer (update every 5 seconds)
        self.intelligence_refresh_timer = QTimer()
        self.intelligence_refresh_timer.timeout.connect(self._refresh_intelligence_bar)
        self.intelligence_refresh_timer.start(5000)  # 5 seconds

        self._setup_ui()
        self._connect_signals()

        # Device configuration will be initialized when hardware connects with actual serial number
        # See _init_device_config() called from main_simplified._on_hardware_connected()
        self.device_config = None

        # Optics warning state tracking
        self._optics_warning_active = False
        self._optics_status_details = None

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
            "}"
        )

        self.sidebar = AffilabsSidebar(event_bus=self.event_bus)
        self.sidebar.setMinimumWidth(55)  # Allow window to resize very small
        self.sidebar.setMaximumWidth(900)  # Maximum width for sidebar
        self.splitter.addWidget(self.sidebar)
        self.splitter.setCollapsible(0, False)  # Prevent sidebar from collapsing

        # Forward sidebar control references to main window for easy access
        self.grid_check = self.sidebar.grid_check
        self.auto_radio = self.sidebar.auto_radio
        self.manual_radio = self.sidebar.manual_radio
        self.min_input = self.sidebar.min_input
        self.max_input = self.sidebar.max_input
        self.x_axis_btn = self.sidebar.x_axis_btn
        self.y_axis_btn = self.sidebar.y_axis_btn
        self.colorblind_check = self.sidebar.colorblind_check
        self.ref_combo = self.sidebar.ref_combo
        self.filter_enable = self.sidebar.filter_enable
        self.filter_slider = self.sidebar.filter_slider
        self.filter_value_label = self.sidebar.filter_value_label
        self.export_data_btn = self.sidebar.export_data_btn

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

        # Forward calibration buttons
        self.simple_led_calibration_btn = self.sidebar.simple_led_calibration_btn
        self.full_calibration_btn = self.sidebar.full_calibration_btn
        self.oem_led_calibration_btn = self.sidebar.oem_led_calibration_btn

        right_widget = QWidget()
        right_widget.setMinimumWidth(300)  # Allow main content to compress so sidebar can expand more
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        nav_bar = self._create_navigation_bar()
        right_layout.addWidget(nav_bar)

        # Stacked widget to hold different content pages
        from PySide6.QtWidgets import QStackedWidget
        self.content_stack = QStackedWidget()

        # Create content for each tab
        self.content_stack.addWidget(self._create_sensorgram_content())  # Index 0
        self.content_stack.addWidget(self._create_blank_content("Edits"))  # Index 1
        self.content_stack.addWidget(self._create_blank_content("Analyze"))  # Index 2
        self.content_stack.addWidget(self._create_blank_content("Report"))  # Index 3

        right_layout.addWidget(self.content_stack, 1)
        self.splitter.addWidget(right_widget)

        # Set initial sizes: 520px for sidebar (more space due to wide Static section), rest for main content
        self.splitter.setSizes([520, 880])

        main_layout.addWidget(self.splitter)

    def _create_navigation_bar(self):
        """Create the pill-shaped navigation bar."""
        nav_widget = QWidget()
        nav_widget.setStyleSheet("background: #FFFFFF;")
        nav_widget.setFixedHeight(60)

        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(20, 10, 20, 10)
        nav_layout.setSpacing(12)

        # Navigation buttons
        nav_button_configs = [
            ("Sensorgram", 0, "Real-time data visualization and cycle monitoring"),
            ("Edits", 1, "Edit and annotate experiment data"),
            ("Analyze", 2, "Analyze results and generate reports"),
            ("Report", 3, "Export and share experiment reports"),
        ]

        for i, (label, page_index, tooltip) in enumerate(nav_button_configs):
            btn = QPushButton(label)
            btn.setFixedHeight(40)
            btn.setMinimumWidth(120)
            btn.setCheckable(True)
            btn.setChecked(i == 0)  # First button selected by default
            btn.setToolTip(tooltip)

            # Store button reference
            self.nav_buttons.append(btn)

            # Update style based on checked state
            btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(46, 48, 227, 0.1);"
                "  color: rgb(46, 48, 227);"
                "  border: none;"
                "  border-radius: 20px;"
                "  padding: 8px 24px;"
                "  font-size: 13px;"
                "  font-weight: 500;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(46, 48, 227, 0.2);"
                "}"
                "QPushButton:checked {"
                "  background: rgba(46, 48, 227, 1.0);"
                "  color: white;"
                "  font-weight: 600;"
                "}"
            )

            # Connect to switch page
            btn.clicked.connect(lambda checked, idx=page_index: self._switch_page(idx))

            nav_layout.addWidget(btn)

        nav_layout.addStretch()

        # Recording timer (hidden by default, shows when recording)
        timer_label = QLabel("00:00:00")
        timer_label.setStyleSheet(
            label_style(12, color=Colors.ERROR, weight=600, font_family=Fonts.MONOSPACE)
            + "background: rgba(255, 59, 48, 0.1);border:none;border-radius:4px;padding:4px 8px;"
        )
        timer_label.setVisible(False)  # Hidden until recording starts
        nav_layout.addWidget(timer_label)

        # Add 16px separation before control buttons
        nav_layout.addSpacing(16)

        # Recording status indicator (next to record button)
        self.recording_indicator = QFrame()
        self.recording_indicator.setFixedSize(200, 32)
        indicator_layout = QHBoxLayout(self.recording_indicator)
        indicator_layout.setContentsMargins(10, 6, 10, 6)
        indicator_layout.setSpacing(8)

        self.rec_status_dot = QLabel("●")
        self.rec_status_dot.setStyleSheet(
            "QLabel {"
            "  color: #86868B;"
            "  font-size: 16px;"
            "  background: transparent;"
            "}"
        )
        indicator_layout.addWidget(self.rec_status_dot)

        # Removed static status text - now shown as tooltip on record button
        indicator_layout.addStretch()

        self.recording_indicator.setStyleSheet(
            "QFrame {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  border-radius: 6px;"
            "}"
        )
        # Hide recording indicator box (keep for internal use but don't display)
        self.recording_indicator.setVisible(False)

        nav_layout.addSpacing(8)

        # Pause button with custom drawn lines (matching record button style)
        self.pause_btn = QPushButton()
        self.pause_btn.setCheckable(True)
        self.pause_btn.setFixedSize(40, 40)
        self.pause_btn.setEnabled(False)  # Disabled until acquisition starts
        self.pause_btn.setToolTip("Pause Live Acquisition\n(Enabled after calibration)")
        self.pause_btn.setStyleSheet(
            "QPushButton {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F5F5F7);"
            "  border: 1px solid rgba(46, 48, 227, 0.3);"
            "  border-radius: 8px;"
            "}"
            "QPushButton:hover:!checked {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(46, 48, 227, 0.1), stop:1 rgba(46, 48, 227, 0.15));"
            "  border: 1px solid rgba(46, 48, 227, 0.4);"
            "}"
            "QPushButton:checked {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF9500, stop:1 #E68500);"
            "  border: 1px solid rgba(255, 149, 0, 0.3);"
            "}"
            "QPushButton:hover:checked {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E68500, stop:1 #CC7700);"
            "  border: 1px solid rgba(230, 133, 0, 0.3);"
            "}"
            "QPushButton:disabled {"
            "  background: rgba(46, 48, 227, 0.1);"
            "  border: 1px solid rgba(46, 48, 227, 0.1);"
            "}"
        )

        # Override paintEvent to draw custom pause lines
        def paint_pause_lines(event):
            """Draw two vertical lines for pause button."""
            from PySide6.QtGui import QPainter, QColor
            from PySide6.QtCore import QRect

            # Call default painting first
            QPushButton.paintEvent(self.pause_btn, event)

            painter = QPainter(self.pause_btn)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Determine color based on state
            if not self.pause_btn.isEnabled():
                color = QColor(46, 48, 227, 77)  # 30% opacity (0.3 * 255 = 77)
            elif self.pause_btn.isChecked():
                color = QColor(255, 255, 255)  # White when checked (orange background)
            else:
                color = QColor(46, 48, 227)  # Blue when unchecked

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)

            # Draw two vertical rectangles (pause lines)
            line_width = 3
            line_height = 14
            gap = 4  # Gap between lines
            center_x = self.pause_btn.width() // 2
            center_y = self.pause_btn.height() // 2

            # Left line
            left_x = center_x - line_width - gap // 2
            painter.drawRoundedRect(
                left_x, center_y - line_height // 2,
                line_width, line_height,
                1.5, 1.5
            )

            # Right line
            right_x = center_x + gap // 2
            painter.drawRoundedRect(
                right_x, center_y - line_height // 2,
                line_width, line_height,
                1.5, 1.5
            )

            painter.end()

        self.pause_btn.paintEvent = paint_pause_lines
        self.pause_btn.clicked.connect(self._toggle_pause)
        nav_layout.addWidget(self.pause_btn)

        nav_layout.addSpacing(4)

        # Record button (matching main tab color with 3D effect)
        self.record_btn = QPushButton("●")
        self.record_btn.setCheckable(True)
        self.record_btn.setFixedSize(40, 40)
        self.record_btn.setEnabled(False)  # Disabled until acquisition starts
        self.record_btn.setToolTip("Start Recording\n(Enabled after calibration)")
        self.record_btn.setStyleSheet(
            "QPushButton {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F5F5F7);"
            "  color: rgb(46, 48, 227);"
            "  border: 1px solid rgba(46, 48, 227, 0.3);"
            "  border-radius: 8px;"
            "  font-size: 20px;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover:!checked {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(46, 48, 227, 0.1), stop:1 rgba(46, 48, 227, 0.15));"
            "  border: 1px solid rgba(46, 48, 227, 0.4);"
            "}"
            "QPushButton:checked {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF3B30, stop:1 #E6342A);"
            "  color: white;"
            "  border: 1px solid rgba(255, 59, 48, 0.3);"
            "}"
            "QPushButton:hover:checked {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E6342A, stop:1 #D02E24);"
            "  border: 1px solid rgba(230, 52, 42, 0.3);"
            "}"
            "QPushButton:disabled {"
            "  background: rgba(46, 48, 227, 0.1);"
            "  color: rgba(46, 48, 227, 0.3);"
            "  border: 1px solid rgba(46, 48, 227, 0.1);"
            "}"
        )
        self.record_btn.clicked.connect(self._toggle_recording)
        nav_layout.addWidget(self.record_btn)

        nav_layout.addSpacing(40)  # Larger gap before power button

        # Power button (indicates power AND connection status)
        self.power_btn = QPushButton("⏻")
        self.power_btn.setFixedSize(40, 40)
        self.power_btn.setProperty("powerState", "disconnected")  # Track state: disconnected, searching, connected
        self._update_power_button_style()
        self.power_btn.setToolTip("Power On Device (Ctrl+P)\nGray = Disconnected | Yellow = Searching | Green = Connected")
        self.power_btn.clicked.connect(self._handle_power_click)  # Use clicked like main branch
        nav_layout.addWidget(self.power_btn)

        nav_layout.addSpacing(16)  # Space between power button and logo

        # Company logo (full horizontal logo)
        logo_label = QLabel()
        logo_pixmap = QPixmap("ui/img/affinite-no-background.png")
        if not logo_pixmap.isNull():
            # Scale logo to larger size while maintaining aspect ratio
            scaled_logo = logo_pixmap.scaledToHeight(40, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_logo)
        logo_label.setStyleSheet("background: transparent;")
        logo_label.setToolTip("Affinité Instruments")
        nav_layout.addWidget(logo_label)

        return nav_widget

    def _create_sensorgram_content(self):
        """Create the Sensorgram tab content with dual-graph layout (master-detail pattern)."""
        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame {"
            "  background: #F8F9FA;"
            "  border: none;"
            "}"
        )

        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(8)

        # Graph header with controls
        header = self._create_graph_header()
        content_layout.addWidget(header)

        # Create QSplitter for resizable graph panels (30/70 split)
        from PySide6.QtWidgets import QSplitter
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(8)
        splitter.setChildrenCollapsible(False)

        # Top graph (Navigation/Overview) - 30%
        self.full_timeline_graph, top_graph = self._create_graph_container(
            "Live Sensorgram",
            height=200,
            show_delta_spr=False
        )

        # Bottom graph (Detail/Cycle of Interest) - 70%
        self.cycle_of_interest_graph, bottom_graph = self._create_graph_container(
            "Cycle of Interest",
            height=400,
            show_delta_spr=True
        )

        # Connect cursor signals for region selection
        if self.full_timeline_graph.start_cursor and self.full_timeline_graph.stop_cursor:
            self.full_timeline_graph.start_cursor.sigDragged.connect(self._on_cursor_dragged)
            self.full_timeline_graph.stop_cursor.sigDragged.connect(self._on_cursor_dragged)
            self.full_timeline_graph.start_cursor.sigPositionChangeFinished.connect(self._on_cursor_moved)
            self.full_timeline_graph.stop_cursor.sigPositionChangeFinished.connect(self._on_cursor_moved)

        splitter.addWidget(top_graph)
        splitter.addWidget(bottom_graph)

        # Set initial sizes (30% / 70%)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 7)

        # Style the splitter handle
        splitter.setStyleSheet(
            "QSplitter {"
            "  background-color: transparent;"
            "  spacing: 8px;"
            "}"
            "QSplitter::handle {"
            "  background: rgba(0, 0, 0, 0.1);"
            "  border: none;"
            "  border-radius: 4px;"
            "  margin: 0px 16px;"
            "}"
            "QSplitter::handle:hover {"
            "  background: rgba(0, 0, 0, 0.15);"
            "}"
            "QSplitter::handle:pressed {"
            "  background: #1D1D1F;"
            "}"
        )

        content_layout.addWidget(splitter, 1)
        return content_widget

    def _create_graph_header(self):
        """Create header with channel toggle controls and live data checkbox."""
        header = QWidget()
        header.setFixedHeight(48)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        # Channel selection label
        channels_label = QLabel("Channels:")
        channels_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "  font-weight: 500;"
            "}"
        )
        channels_label.setToolTip("Toggle channel visibility on graphs")
        header_layout.addWidget(channels_label)

        # Channel toggles - consistent colors (Black, Red, Blue, Green)
        self.channel_toggles = {}
        channel_names = {
            "A": ("#1D1D1F", "Channel A (Black) - Toggle visibility"),
            "B": ("#FF3B30", "Channel B (Red) - Toggle visibility"),
            "C": ("#007AFF", "Channel C (Blue) - Toggle visibility"),
            "D": ("#34C759", "Channel D (Green) - Toggle visibility")
        }
        for ch, (color, tooltip) in channel_names.items():
            ch_btn = QPushButton(f"Ch {ch}")
            ch_btn.setCheckable(True)
            ch_btn.setChecked(True)
            ch_btn.setFixedSize(56, 32)
            ch_btn.setToolTip(tooltip)
            ch_btn.setStyleSheet(
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
                "}"
            )

            # Store reference and connect to visibility toggle
            self.channel_toggles[ch] = ch_btn
            ch_btn.toggled.connect(lambda checked, channel=ch: self._toggle_channel_visibility(channel, checked))

            header_layout.addWidget(ch_btn)

        header_layout.addStretch()

        # Live Data checkbox
        self.live_data_checkbox = QCheckBox("Live Data")
        self.live_data_checkbox.setChecked(True)
        self.live_data_checkbox.setToolTip(
            "Enable/disable live cursor auto-follow\n"
            "• Checked: Stop cursor follows latest data point\n"
            "• Unchecked: Stop cursor freezes, data keeps recording\n"
            "• Cycle of Interest graph always updates between cursors"
        )
        self.live_data_checkbox.setStyleSheet(
            "QCheckBox {"
            "  font-size: 13px;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "  font-weight: 500;"
            "  spacing: 6px;"
            "}"
            "QCheckBox::indicator {"
            "  width: 18px;"
            "  height: 18px;"
            "  border: 2px solid #86868B;"
            "  border-radius: 4px;"
            "  background: white;"
            "}"
            "QCheckBox::indicator:checked {"
            "  background: #007AFF;"
            "  border-color: #007AFF;"
            "  image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEwLjUgMS41TDQgOEwxLjUgNS41IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPjwvc3ZnPg==);"
            "}"
            "QCheckBox::indicator:hover {"
            "  border-color: #007AFF;"
            "}"
        )
        self.live_data_checkbox.toggled.connect(self._toggle_live_data)
        header_layout.addWidget(self.live_data_checkbox)

        return header

    def _show_transmission_spectrum(self):
        """Show the transmission spectrum dialog."""
        if hasattr(self, 'app') and self.app:
            self.app.show_transmission_dialog()

    def _on_pipeline_changed(self, index: int):
        """Handle data processing pipeline selection change."""
        if not hasattr(self.sidebar, 'pipeline_selector'):
            return

        pipeline_id = self.sidebar.pipeline_selector.itemData(index)

        # Update active pipeline in registry
        try:
            from utils.processing_pipeline import get_pipeline_registry

            registry = get_pipeline_registry()
            registry.set_active_pipeline(pipeline_id)

            print(f"Data processing pipeline changed to: {pipeline_id}")

        except Exception as e:
            print(f"Error updating pipeline configuration: {e}")

    def _update_pipeline_description(self, index: int):
        """Update the pipeline description label based on selection."""
        if not hasattr(self.sidebar, 'pipeline_selector') or not hasattr(self.sidebar, 'pipeline_description'):
            return

        pipeline_id = self.sidebar.pipeline_selector.itemData(index)

        descriptions = {
            "fourier": "Fourier Transform: Uses DST/IDCT for derivative zero-crossing detection. Established method for SPR.",
            "centroid": "Centroid Detection: Center-of-mass calculation of inverted transmission dip. Simple and robust for symmetric peaks.",
            "polynomial": "Polynomial Fit: Fits polynomial to dip region and finds minimum. Good for smooth, well-defined peaks.",
            "adaptive": "Adaptive Multi-Feature: Combines multiple detection methods with adaptive weighting. Best for challenging signals.",
            "consensus": "Consensus: Combines 3 methods (centroid, parabolic, fourier) for robust multi-method validation."
        }

        description = descriptions.get(pipeline_id, "Unknown pipeline selected.")
        self.sidebar.pipeline_description.setText(description)

    def _init_pipeline_selector(self):
        """Initialize the pipeline selector to match current active pipeline."""
        if not hasattr(self.sidebar, 'pipeline_selector'):
            return

        try:
            from utils.processing_pipeline import get_pipeline_registry

            registry = get_pipeline_registry()
            active_pipeline_id = registry.active_pipeline_id

            # Find index of active pipeline
            pipeline_map = {
                'fourier': 0,
                'centroid': 1,
                'polynomial': 2,
                'adaptive': 3,
                'consensus': 4
            }

            index = pipeline_map.get(active_pipeline_id, 0)  # Default to Fourier

            # Block signals while setting to avoid recursive calls
            self.sidebar.pipeline_selector.blockSignals(True)
            self.sidebar.pipeline_selector.setCurrentIndex(index)
            self.sidebar.pipeline_selector.blockSignals(False)

            # Update description
            self._update_pipeline_description(index)

            print(f"Pipeline selector initialized to: {active_pipeline_id} (index {index})")

        except Exception as e:
            print(f"Error initializing pipeline selector: {e}")

    def _toggle_live_data(self, enabled: bool) -> None:
        """Toggle live data updates for graphs."""
        self.live_data_enabled = enabled
        if enabled:
            print("Live data updates enabled")
        else:
            print("Live data updates disabled - graph frozen")

    def _toggle_channel_visibility(self, channel, visible):
        """Toggle visibility of a channel on both graphs."""
        channel_idx = {'A': 0, 'B': 1, 'C': 2, 'D': 3}[channel]

        # Update full timeline graph
        if hasattr(self, 'full_timeline_graph'):
            curve = self.full_timeline_graph.curves[channel_idx]
            if visible:
                curve.show()
            else:
                curve.hide()

        # Update cycle of interest graph
        if hasattr(self, 'cycle_of_interest_graph'):
            curve = self.cycle_of_interest_graph.curves[channel_idx]
            if visible:
                curve.show()
            else:
                curve.hide()

    def _create_graph_container(self, title: str, height: int, show_delta_spr: bool = False) -> QFrame:
        """Create a graph container with title and controls."""
        import pyqtgraph as pg

        container = QFrame()
        container.setMinimumHeight(height)
        container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        # Add shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title row with controls
        title_row = QHBoxLayout()
        title_row.setSpacing(12)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        title_row.addWidget(title_label)

        title_row.addStretch()

        # Delta SPR signal display (only for Cycle of Interest graph)
        delta_display = None
        if show_delta_spr:
            delta_display = QLabel("Δ SPR: Ch A: 0.0 nm  |  Ch B: 0.0 nm  |  Ch C: 0.0 nm  |  Ch D: 0.0 nm")
            delta_display.setStyleSheet(
                "QLabel {"
                "  background: rgba(0, 0, 0, 0.04);"
                "  border: none;"
                "  border-radius: 6px;"
                "  padding: 6px 12px;"
                "  font-size: 11px;"
                f"  color: {Colors.PRIMARY_TEXT};"
                f"  font-family: {Fonts.MONOSPACE};"
                "  font-weight: 500;"
                "}"
            )
            delta_display.setToolTip("Real-time change in Surface Plasmon Resonance signal (relative to cycle start)")
            title_row.addWidget(delta_display)

        layout.addLayout(title_row)

        # Create standardized time-series plot
        left_label = 'Δ SPR (RU)' if show_delta_spr else 'λ (nm)'
        plot_widget = create_time_plot(left_label)

        # Create plot curves for 4 channels with distinct colors
        # Ch A: Black, Ch B: Red, Ch C: Blue, Ch D: Green
        # Standard colors (will be updated if colorblind mode enabled)
        # Clickable only for Live Sensorgram (top graph) for channel selection/flagging
        curves = add_channel_curves(plot_widget, clickable=not show_delta_spr, width=2)
        if not show_delta_spr:  # Live Sensorgram - enable curve click to select channel
            for i, curve in enumerate(curves):
                try:
                    curve.sigClicked.connect(lambda _, ch=i: self._on_curve_clicked(ch))
                except Exception:
                    pass

        # Add Start/Stop cursors for Full Experiment Timeline (top graph)
        start_cursor = None
        stop_cursor = None
        if not show_delta_spr:  # Only for FET graph
            # Start cursor (black with horizontal label centered on line)
            start_cursor = pg.InfiniteLine(
                pos=0,
                angle=90,
                pen=pg.mkPen(color='#1D1D1F', width=2),
                movable=True,
                label='Start: {value:.1f}s',
                labelOpts={
                    'position': 0.5,  # Center of graph
                    'color': '#1D1D1F',
                    'fill': '#FFFFFF',
                    'movable': False,
                    'rotateAxis': (1, 0)  # Rotate 180 degrees total (horizontal)
                }
            )
            plot_widget.addItem(start_cursor)

            # Stop cursor (black with horizontal label centered on line)
            stop_cursor = pg.InfiniteLine(
                pos=100,
                angle=90,
                pen=pg.mkPen(color='#1D1D1F', width=2),
                movable=True,
                label='Stop: {value:.1f}s',
                labelOpts={
                    'position': 0.5,  # Center of graph
                    'color': '#1D1D1F',
                    'fill': '#FFFFFF',
                    'movable': False,
                    'rotateAxis': (1, 0)  # Rotate 180 degrees total (horizontal)
                }
            )
            plot_widget.addItem(stop_cursor)

        # Store references to curves and cursors on the plot widget
        plot_widget.curves = curves
        plot_widget.delta_display = delta_display
        plot_widget.start_cursor = start_cursor
        plot_widget.stop_cursor = stop_cursor
        plot_widget.flag_markers = []  # Store flag marker items
        plot_widget.channel_flags = {0: [], 1: [], 2: [], 3: []}  # Store flags per channel (index: list of (x, y, note))

        # Connect plot click event for flagging (ONLY for Live Sensorgram - top graph)
        # Bottom graph (Cycle of Interest) has default PyQtGraph interactions
        if not show_delta_spr:  # Live Sensorgram
            plot_widget.scene().sigMouseClicked.connect(lambda event: self._on_plot_clicked(event, plot_widget))

        # Mouse interaction mode: Rectangle zoom (default for both graphs)
        # Top graph: Rectangle zoom + flagging via right-click
        # Bottom graph: Rectangle zoom only (default PyQtGraph behavior)
        plot_widget.getPlotItem().getViewBox().setMouseMode(pg.ViewBox.RectMode)

        layout.addWidget(plot_widget, 1)

        return plot_widget, container

    def _on_curve_clicked(self, channel_idx):
        """Handle click on a channel curve in Live Sensorgram to select it for flagging."""
        if not hasattr(self, 'full_timeline_graph'):
            return

        # Get channel letter for toggle button
        channel_letter = chr(65 + channel_idx)  # 0→A, 1→B, 2→C, 3→D

        # Store the selected channel for flagging operations
        self.selected_channel_for_flagging = channel_idx
        self.selected_channel_letter = channel_letter

        # Update all curves: highlight selected, reset others
        for i, curve in enumerate(self.full_timeline_graph.curves):
            if i == channel_idx:
                # Highlight selected curve with thicker line
                curve.setPen(curve.selected_pen)
            else:
                # Reset other curves to normal width
                curve.setPen(curve.original_pen)

        # Update channel toggle button to show selection (but don't change visibility)
        if hasattr(self, 'channel_toggles') and channel_letter in self.channel_toggles:
            # Visual feedback: briefly flash the button or update its appearance
            # For now, just ensure it's checked (visible)
            btn = self.channel_toggles[channel_letter]
            if not btn.isChecked():
                btn.setChecked(True)  # Turn on if it was off

        # Enable flagging mode for the selected channel
        self._enable_flagging_mode(channel_idx, channel_letter)

        print(f"Channel {channel_letter} selected for flagging")

    def _enable_flagging_mode(self, channel_idx, channel_letter):
        """Enable flagging mode for the selected channel."""
        if not hasattr(self, 'full_timeline_graph'):
            return

        # Store current flagging mode state
        if not hasattr(self, 'flagging_enabled'):
            self.flagging_enabled = False

        # Inform user that they can now click on points to flag them
        print(f"Flagging mode ready for Channel {channel_letter}")
        print("Right-click on the Live Sensorgram to add a flag at that position")
        print("Ctrl+Right-click to remove a flag near that position")

    def _on_plot_clicked(self, event, plot_widget):
        """
        Handle clicks on the Live Sensorgram (top graph) for adding/removing flags.
        Bottom graph (Cycle of Interest) does not have this handler - uses default PyQtGraph interactions.

        Right-click: Add flag at position on selected channel
        Ctrl+Right-click: Remove flag near position on selected channel
        """
        # Only process right-clicks for flagging
        if event.button() != 2:  # 2 = right mouse button
            return

        # Check if a channel is selected for flagging
        if not hasattr(self, 'selected_channel_for_flagging'):
            print("Please select a channel first by clicking on its curve")
            return

        # Get click position in data coordinates
        pos = event.scenePos()
        mouse_point = plot_widget.getPlotItem().vb.mapSceneToView(pos)
        x_pos = mouse_point.x()
        y_pos = mouse_point.y()

        # Check for Ctrl modifier to remove flags
        from PySide6.QtCore import Qt
        modifiers = event.modifiers()

        if modifiers == Qt.KeyboardModifier.ControlModifier:
            # Remove flag near this position
            self._remove_flag_at_position(self.selected_channel_for_flagging, x_pos)
        else:
            # Add flag at this position
            self._add_flag_to_point(self.selected_channel_for_flagging, x_pos, y_pos)

        event.accept()

    def _add_flag_to_point(self, channel_idx, x_pos, y_pos, note=""):
        """Add a flag marker at the specified position on the selected channel."""
        if not hasattr(self, 'full_timeline_graph'):
            return

        import pyqtgraph as pg

        # Get channel letter
        channel_letter = chr(65 + channel_idx)

        # Create flag marker (vertical line with text)
        flag_line = pg.InfiniteLine(
            pos=x_pos,
            angle=90,
            pen=pg.mkPen(color='#FF3B30', width=2, style=pg.QtCore.Qt.PenStyle.DashLine),
            movable=False
        )

        # Add text label at the top
        flag_text = pg.TextItem(
            text=f"🚩 Ch{channel_letter}",
            color='#FF3B30',
            anchor=(0.5, 1)  # Center, bottom
        )
        flag_text.setPos(x_pos, y_pos)

        # Add to Live Sensorgram (top graph)
        self.full_timeline_graph.addItem(flag_line)
        self.full_timeline_graph.addItem(flag_text)

        # Store references
        flag_marker = {
            'channel': channel_idx,
            'x': x_pos,
            'y': y_pos,
            'note': note,
            'line': flag_line,
            'text': flag_text
        }

        self.full_timeline_graph.flag_markers.append(flag_marker)
        self.full_timeline_graph.channel_flags[channel_idx].append((x_pos, y_pos, note))

        # Update the table Flags column
        self._update_flags_table()

        print(f"Flag added to Channel {channel_letter} at x={x_pos:.2f}, y={y_pos:.2f}")

    def _remove_flag_at_position(self, channel_idx, x_pos, tolerance=5.0):
        """Remove a flag marker near the specified x position on the selected channel."""
        if not hasattr(self, 'full_timeline_graph'):
            return

        # Find and remove flags within tolerance
        removed_count = 0
        markers_to_remove = []

        for marker in self.full_timeline_graph.flag_markers:
            if marker['channel'] == channel_idx and abs(marker['x'] - x_pos) <= tolerance:
                # Remove visual elements
                self.full_timeline_graph.removeItem(marker['line'])
                self.full_timeline_graph.removeItem(marker['text'])
                markers_to_remove.append(marker)
                removed_count += 1

        # Remove from list
        for marker in markers_to_remove:
            self.full_timeline_graph.flag_markers.remove(marker)

        # Update channel flags
        self.full_timeline_graph.channel_flags[channel_idx] = [
            (x, y, note) for x, y, note in self.full_timeline_graph.channel_flags[channel_idx]
            if abs(x - x_pos) > tolerance
        ]

        # Update table
        self._update_flags_table()

        if removed_count > 0:
            channel_letter = chr(65 + channel_idx)
            print(f"Removed {removed_count} flag(s) from Channel {channel_letter} near x={x_pos:.2f}")

    def _update_flags_table(self):
        """Update the Flags column in the cycle data table with current flags."""
        if not hasattr(self, 'cycle_data_table') or not hasattr(self, 'full_timeline_graph'):
            return

        # Count flags per channel
        flag_counts = {}
        for ch_idx in range(4):
            channel_letter = chr(65 + ch_idx)
            count = len(self.full_timeline_graph.channel_flags.get(ch_idx, []))
            if count > 0:
                flag_counts[channel_letter] = count

        # Update table - show flag summary
        # Note: This is a simplified version. In a full implementation, you'd have
        # one row per data segment/cycle and show flags for that specific segment
        if flag_counts:
            flag_summary = ", ".join([f"Ch{ch}: {count}" for ch, count in flag_counts.items()])
            print(f"Flags summary: {flag_summary}")
            # In full implementation: update specific table cell in Flags column

    def _clear_all_flags(self, channel_idx=None):
        """Clear all flags, optionally for a specific channel only."""
        if not hasattr(self, 'full_timeline_graph'):
            return

        markers_to_remove = []

        if channel_idx is None:
            # Clear all flags
            markers_to_remove = self.full_timeline_graph.flag_markers.copy()
        else:
            # Clear flags for specific channel
            markers_to_remove = [m for m in self.full_timeline_graph.flag_markers if m['channel'] == channel_idx]

        # Remove visual elements
        for marker in markers_to_remove:
            self.full_timeline_graph.removeItem(marker['line'])
            self.full_timeline_graph.removeItem(marker['text'])
            self.full_timeline_graph.flag_markers.remove(marker)

        # Clear channel_flags
        if channel_idx is None:
            for ch_idx in range(4):
                self.full_timeline_graph.channel_flags[ch_idx] = []
        else:
            self.full_timeline_graph.channel_flags[channel_idx] = []

        # Update table
        self._update_flags_table()

        if channel_idx is None:
            print("All flags cleared")
        else:
            channel_letter = chr(65 + channel_idx)
            print(f"All flags cleared for Channel {channel_letter}")

    def _on_cursor_dragged(self):
        """Handle cursor dragging - update label format dynamically."""
        if not hasattr(self, 'full_timeline_graph'):
            return

        start_cursor = self.full_timeline_graph.start_cursor
        stop_cursor = self.full_timeline_graph.stop_cursor

        if start_cursor and stop_cursor:
            # Update labels with current positions
            start_pos = start_cursor.value()
            stop_pos = stop_cursor.value()

            # Ensure start is always less than stop
            if start_pos > stop_pos:
                start_pos, stop_pos = stop_pos, start_pos

            # Update label text dynamically
            start_cursor.label.setFormat(f'Start: {start_pos:.1f}s')
            stop_cursor.label.setFormat(f'Stop: {stop_pos:.1f}s')

    def _on_cursor_moved(self):
        """Handle cursor movement finished - update selected region."""
        if not hasattr(self, 'full_timeline_graph'):
            return

        start_cursor = self.full_timeline_graph.start_cursor
        stop_cursor = self.full_timeline_graph.stop_cursor

        if start_cursor and stop_cursor:
            start_time = start_cursor.value()
            stop_time = stop_cursor.value()

            # Ensure start is always before stop
            if start_time > stop_time:
                start_time, stop_time = stop_time, start_time
                # Swap cursor positions
                start_cursor.setValue(start_time)
                stop_cursor.setValue(stop_time)

            print(f"Cursor region selected: {start_time:.2f}s to {stop_time:.2f}s")
            # TODO: Update cycle of interest graph to show selected region

    def _create_blank_content(self, tab_name):
        """Create a blank page for tabs that don't have content yet."""
        # Special handling for different tabs
        if tab_name == "Edits":
            return self._create_edits_content()
        elif tab_name == "Analyze":
            return self._create_analyze_content()
        elif tab_name == "Report":
            return self._create_report_content()

        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame {"
            "  background: #F8F9FA;"
            "  border: none;"
            "}"
        )

        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Empty state message
        empty_icon = QLabel("📑")
        empty_icon.setStyleSheet(
            "QLabel {"
            "  font-size: 64px;"
            "  background: transparent;"
            "}"
        )
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(empty_icon)

        empty_title = QLabel(f"{tab_name} Page")
        empty_title.setStyleSheet(
            "QLabel {"
            "  font-size: 24px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  margin-top: 16px;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(empty_title)

        empty_desc = QLabel(f"Content for the {tab_name} tab will appear here.")
        empty_desc.setStyleSheet(
            "QLabel {"
            "  font-size: 14px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  margin-top: 8px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        empty_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(empty_desc)

        return content_widget

    def _create_edits_content(self):
        """Create the Edits tab content with cycle data table and graph editing tools."""
        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame {"
            "  background: #F8F9FA;"
            "  border: none;"
            "}"
        )

        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)

        # Left side: Cycle Data Table + Tools
        left_panel = self._create_edits_left_panel()
        content_layout.addWidget(left_panel, 2)

        # Right side: Primary Graph + Thumbnail Selector
        right_panel = self._create_edits_right_panel()
        content_layout.addWidget(right_panel, 3)

        return content_widget

    def _create_edits_left_panel(self):
        """Create left panel with cycle data table and editing tools."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {"
            "  background: transparent;"
            "  border: none;"
            "}"
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Cycle Data Table
        table_container = QFrame()
        table_container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        table_container.setGraphicsEffect(shadow)

        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(16, 16, 16, 16)
        table_layout.setSpacing(12)

        # Table header
        table_header = QHBoxLayout()
        table_title = QLabel("Cycle Data")
        table_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        table_header.addWidget(table_title)
        table_header.addStretch()

        # Search/Filter button
        filter_btn = QPushButton("🔍 Filter")
        filter_btn.setFixedHeight(28)
        filter_btn.setMinimumWidth(80)
        filter_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  color: #1D1D1F;"
            "  border: none;"
            "  border-radius: 6px;"
            "  font-size: 12px;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.1);"
            "}"
        )
        table_header.addWidget(filter_btn)

        table_layout.addLayout(table_header)

        # Master-Detail Pattern: Top table (Master) + Bottom detail panel
        # Temporarily simplified for debugging
        from PySide6.QtWidgets import QTableWidget, QHeaderView

        self.cycle_data_table = QTableWidget(10, 6)
        self.cycle_data_table.setHorizontalHeaderLabels(["Type", "Start", "End", "Units", "Notes", "Flags"])
        self.cycle_data_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cycle_data_table.setColumnWidth(3, 80)  # Fixed width for Units column
        self.cycle_data_table.verticalHeader().setVisible(True)  # Show row numbers as ID
        self.cycle_data_table.setStyleSheet(
            "QTableWidget {"
            "  background: #FFFFFF;"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "  font-size: 12px;"
            "}"
        )

        table_layout.addWidget(self.cycle_data_table, 1)

        panel_layout.addWidget(table_container, 3)

        # Editing Tools Box
        tools_container = QFrame()
        tools_container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        tools_container.setGraphicsEffect(shadow)

        tools_layout = QVBoxLayout(tools_container)
        tools_layout.setContentsMargins(16, 16, 16, 16)
        tools_layout.setSpacing(12)

        # Tools header
        tools_title = QLabel("Editing Tools")
        tools_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        tools_layout.addWidget(tools_title)

        # Tool buttons grid
        tools_grid = QHBoxLayout()
        tools_grid.setSpacing(8)

        tool_buttons = [
            ("Cut Spikes", "✂️"),
            ("Align", "⇄"),
            ("Redefine Segment", "⬚"),
            ("Smooth", "〰"),
        ]

        for tool_name, icon in tool_buttons:
            tool_btn = QPushButton(f"{icon} {tool_name}")
            tool_btn.setFixedHeight(36)
            tool_btn.setMinimumWidth(100)
            tool_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.04);"
                "  color: #1D1D1F;"
                "  border: none;"
                "  border-radius: 8px;"
                "  font-size: 12px;"
                "  font-weight: 500;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.08);"
                "}"
                "QPushButton:pressed {"
                "  background: rgba(0, 0, 0, 0.12);"
                "}"
            )
            tools_grid.addWidget(tool_btn)

        tools_layout.addLayout(tools_grid)

        # Action buttons
        action_buttons = QHBoxLayout()
        action_buttons.setSpacing(8)

        apply_btn = QPushButton("Apply Changes")
        apply_btn.setFixedHeight(36)
        apply_btn.setStyleSheet(
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  padding: 0px 16px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #3A3A3C;"
            "}"
            "QPushButton:pressed {"
            "  background: #48484A;"
            "}"
        )
        action_buttons.addWidget(apply_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.setFixedHeight(36)
        reset_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  color: #1D1D1F;"
            "  border: none;"
            "  border-radius: 8px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  padding: 0px 16px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.08);"
            "}"
        )
        action_buttons.addWidget(reset_btn)

        tools_layout.addLayout(action_buttons)

        panel_layout.addWidget(tools_container, 1)

        return panel

    def _create_edits_right_panel(self):
        """Create right panel with primary graph and thumbnail selectors."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {"
            "  background: transparent;"
            "  border: none;"
            "}"
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Primary Graph Container
        primary_graph = QFrame()
        primary_graph.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        primary_graph.setGraphicsEffect(shadow)

        primary_layout = QVBoxLayout(primary_graph)
        primary_layout.setContentsMargins(16, 16, 16, 16)
        primary_layout.setSpacing(12)

        # Graph header
        graph_header = QHBoxLayout()
        graph_title = QLabel("Primary Cycle View")
        graph_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        graph_header.addWidget(graph_title)
        graph_header.addStretch()

        # Channel toggles (compact)
        for ch, color in [("A", "#1D1D1F"), ("B", "#FF3B30"), ("C", "#1D1D1F"), ("D", "#34C759")]:
            ch_btn = QPushButton(f"Ch {ch}")
            ch_btn.setCheckable(True)
            ch_btn.setChecked(True)
            ch_btn.setFixedSize(40, 24)
            ch_btn.setStyleSheet(
                f"QPushButton {{"
                f"  background: {color};"
                "  color: white;"
                "  border: none;"
                "  border-radius: 4px;"
                "  font-size: 11px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:!checked {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: #86868B;"
                "}"
            )
            graph_header.addWidget(ch_btn)

        primary_layout.addLayout(graph_header)

        # Graph canvas placeholder
        graph_canvas = QFrame()
        graph_canvas.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "}"
        )
        graph_canvas_layout = QVBoxLayout(graph_canvas)
        graph_placeholder = QLabel(
            "[Primary Graph Canvas]\n\n"
            "Selected cycle data displayed here\n"
            "Interactive editing enabled"
        )
        graph_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        graph_placeholder.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: #C7C7CC;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        graph_canvas_layout.addWidget(graph_placeholder)

        primary_layout.addWidget(graph_canvas, 1)

        panel_layout.addWidget(primary_graph, 4)

        # Thumbnail Graph Selector
        thumbnails_container = QFrame()
        thumbnails_container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        thumbnails_container.setGraphicsEffect(shadow)

        thumbnails_layout = QVBoxLayout(thumbnails_container)
        thumbnails_layout.setContentsMargins(12, 12, 12, 12)
        thumbnails_layout.setSpacing(8)

        # Thumbnails label
        thumb_label = QLabel("Quick View")
        thumb_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        thumbnails_layout.addWidget(thumb_label)

        # Three thumbnail placeholders
        thumb_grid = QHBoxLayout()
        thumb_grid.setSpacing(8)

        for i in range(3):
            thumb = QPushButton(f"Cycle {i + 2}")
            thumb.setFixedHeight(80)
            thumb.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.03);"
                "  color: #86868B;"
                "  border: 1px solid rgba(0, 0, 0, 0.08);"
                "  border-radius: 8px;"
                "  font-size: 11px;"
                "  font-weight: 500;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  border-color: #1D1D1F;"
                "  color: #1D1D1F;"
                "}"
                "QPushButton:pressed {"
                "  background: rgba(0, 122, 255, 0.2);"
                "}"
            )
            thumb_grid.addWidget(thumb)

        thumbnails_layout.addLayout(thumb_grid)

        panel_layout.addWidget(thumbnails_container, 1)

        return panel

    def _create_analyze_content(self):
        """Create the Analyze tab content with processed data graph, statistics, and kinetic analysis."""
        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame {"
            "  background: #F8F9FA;"
            "  border: none;"
            "}"
        )

        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)

        # Left side: Graphs (Processed Data + Statistics)
        left_panel = self._create_analyze_left_panel()
        content_layout.addWidget(left_panel, 3)

        # Right side: Model Selection + Data Table + Export
        right_panel = self._create_analyze_right_panel()
        content_layout.addWidget(right_panel, 2)

        return content_widget

    def _create_analyze_left_panel(self):
        """Create left panel with processed data and statistics graphs."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {"
            "  background: transparent;"
            "  border: none;"
            "}"
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Main Processed Data Graph
        main_graph = QFrame()
        main_graph.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        main_graph.setGraphicsEffect(shadow)

        main_graph_layout = QVBoxLayout(main_graph)
        main_graph_layout.setContentsMargins(16, 16, 16, 16)
        main_graph_layout.setSpacing(12)

        # Header
        graph_header = QHBoxLayout()
        graph_title = QLabel("Processed Data")
        graph_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        graph_header.addWidget(graph_title)
        graph_header.addStretch()

        # View options
        view_btns = ["Fitted", "Residuals", "Overlay"]
        for i, btn_text in enumerate(view_btns):
            view_btn = QPushButton(btn_text)
            view_btn.setCheckable(True)
            view_btn.setChecked(i == 0)
            view_btn.setFixedHeight(28)
            view_btn.setMinimumWidth(72)
            view_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: #86868B;"
                "  border: none;"
                "  border-radius: 6px;"
                "  font-size: 12px;"
                "  font-weight: 500;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:checked {"
                "  background: #1D1D1F;"
                "  color: white;"
                "  font-weight: 600;"
                "}"
                "QPushButton:hover:!checked {"
                "  background: rgba(0, 0, 0, 0.1);"
                "}"
            )
            graph_header.addWidget(view_btn)

        main_graph_layout.addLayout(graph_header)

        # Graph canvas
        graph_canvas = QFrame()
        graph_canvas.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "}"
        )
        canvas_layout = QVBoxLayout(graph_canvas)
        canvas_placeholder = QLabel(
            "[Processed Data Graph]\n\n"
            "Fitted curves with model overlay\n"
            "Interactive zoom and pan enabled"
        )
        canvas_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        canvas_placeholder.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: #C7C7CC;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        canvas_layout.addWidget(canvas_placeholder)
        main_graph_layout.addWidget(graph_canvas, 1)

        panel_layout.addWidget(main_graph, 3)

        # Statistics / Goodness of Fit Graph
        stats_graph = QFrame()
        stats_graph.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        stats_graph.setGraphicsEffect(shadow)

        stats_layout = QVBoxLayout(stats_graph)
        stats_layout.setContentsMargins(16, 16, 16, 16)
        stats_layout.setSpacing(12)

        # Header
        stats_header = QHBoxLayout()
        stats_title = QLabel("Goodness of Fit Analysis")
        stats_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        stats_header.addWidget(stats_title)
        stats_header.addStretch()

        # R² display
        r_squared = QLabel("R² = 0.9987")
        r_squared.setStyleSheet(
            "QLabel {"
            "  background: rgba(52, 199, 89, 0.1);"
            "  color: #34C759;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 6px 12px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            f"  font-family: {Fonts.MONOSPACE};"
            "}"
        )
        stats_header.addWidget(r_squared)

        stats_layout.addLayout(stats_header)

        # Stats canvas
        stats_canvas = QFrame()
        stats_canvas.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "}"
        )
        stats_canvas_layout = QVBoxLayout(stats_canvas)
        stats_placeholder = QLabel(
            "[Residuals / Chi-Square Plot]\n\n"
            "Statistical analysis visualization\n"
            "Chi² = 1.23e-4, RMSE = 0.012"
        )
        stats_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats_placeholder.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: #C7C7CC;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        stats_canvas_layout.addWidget(stats_placeholder)
        stats_layout.addWidget(stats_canvas, 1)

        panel_layout.addWidget(stats_graph, 2)

        return panel

    def _create_analyze_right_panel(self):
        """Create right panel with model selection, data table, and export options."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {"
            "  background: transparent;"
            "  border: none;"
            "}"
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Mathematical Model Selection
        model_container = QFrame()
        model_container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        model_container.setGraphicsEffect(shadow)

        model_layout = QVBoxLayout(model_container)
        model_layout.setContentsMargins(16, 16, 16, 16)
        model_layout.setSpacing(12)

        # Header
        model_title = QLabel("Mathematical Model")
        model_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        model_layout.addWidget(model_title)

        # Model selection dropdown
        from PySide6.QtWidgets import QComboBox
        model_dropdown = QComboBox()
        model_dropdown.addItems([
            "Langmuir 1:1",
            "Two-State Binding",
            "Bivalent Analyte",
            "Mass Transport Limited",
            "Heterogeneous Ligand",
            "Custom Model"
        ])
        model_dropdown.setFixedHeight(36)
        model_dropdown.setStyleSheet(
            "QComboBox {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  color: #1D1D1F;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 8px 12px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QComboBox:hover {"
            "  background: rgba(0, 0, 0, 0.08);"
            "}"
            "QComboBox::drop-down {"
            "  border: none;"
            "  width: 20px;"
            "}"
            "QComboBox::down-arrow {"
            "  image: none;"
            "  border: none;"
            "}"
        )
        model_layout.addWidget(model_dropdown)

        # Fit button
        fit_btn = QPushButton("Run Fitting Analysis")
        fit_btn.setFixedHeight(36)
        fit_btn.setStyleSheet(
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #3A3A3C;"
            "}"
            "QPushButton:pressed {"
            "  background: #48484A;"
            "}"
        )
        model_layout.addWidget(fit_btn)

        # Model parameters info
        params_label = QLabel("Model Parameters")
        params_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  margin-top: 8px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        model_layout.addWidget(params_label)

        params_info = QLabel(
            "ka: Association rate constant\n"
            "kd: Dissociation rate constant\n"
            "KD: Equilibrium constant\n"
            "Rmax: Maximum response"
        )
        params_info.setStyleSheet(
            "QLabel {"
            "  font-size: 11px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  line-height: 1.6;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        model_layout.addWidget(params_info)

        panel_layout.addWidget(model_container)

        # Kinetic Data Table
        data_container = QFrame()
        data_container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        data_container.setGraphicsEffect(shadow)

        data_layout = QVBoxLayout(data_container)
        data_layout.setContentsMargins(16, 16, 16, 16)
        data_layout.setSpacing(12)

        # Header
        data_header = QHBoxLayout()
        data_title = QLabel("Kinetic Results")
        data_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        data_header.addWidget(data_title)
        data_header.addStretch()

        copy_btn = QPushButton("📋 Copy")
        copy_btn.setFixedHeight(28)
        copy_btn.setMinimumWidth(72)
        copy_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  color: #1D1D1F;"
            "  border: none;"
            "  border-radius: 6px;"
            "  font-size: 12px;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.1);"
            "}"
        )
        data_header.addWidget(copy_btn)

        data_layout.addLayout(data_header)

        # Data table
        from PySide6.QtWidgets import QTableWidget, QHeaderView
        data_table = QTableWidget(4, 2)
        data_table.setHorizontalHeaderLabels(["Parameter", "Value"])
        data_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        data_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        data_table.setStyleSheet(
            "QTableWidget {"
            "  background: #FFFFFF;"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "  gridline-color: rgba(0, 0, 0, 0.06);"
            "  font-size: 12px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QTableWidget::item {"
            "  padding: 8px;"
            "  color: #1D1D1F;"
            "}"
            "QHeaderView::section {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  color: #86868B;"
            "  padding: 8px;"
            "  border: none;"
            "  border-bottom: 1px solid rgba(0, 0, 0, 0.08);"
            "  font-weight: 600;"
            "  font-size: 11px;"
            "}"
        )

        # Sample data
        from PySide6.QtWidgets import QTableWidgetItem
        results = [
            ("ka (M⁻¹s⁻¹)", "1.23e5 ± 0.04e5"),
            ("kd (s⁻¹)", "3.45e-4 ± 0.12e-4"),
            ("KD (M)", "2.80e-9 ± 0.15e-9"),
            ("Δ SPR (nm)", "0.45 ± 0.02")
        ]

        for row, (param, value) in enumerate(results):
            data_table.setItem(row, 0, QTableWidgetItem(param))
            data_table.setItem(row, 1, QTableWidgetItem(value))

        data_layout.addWidget(data_table, 1)

        panel_layout.addWidget(data_container, 1)

        # Export/Save Section
        export_container = QFrame()
        export_container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        export_container.setGraphicsEffect(shadow)

        export_layout = QVBoxLayout(export_container)
        export_layout.setContentsMargins(16, 16, 16, 16)
        export_layout.setSpacing(12)

        export_title = QLabel("Export Data")
        export_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        export_layout.addWidget(export_title)

        # Export buttons
        export_btns = QHBoxLayout()
        export_btns.setSpacing(8)

        csv_btn = QPushButton("Save CSV")
        csv_btn.setFixedHeight(36)
        csv_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  color: #1D1D1F;"
            "  border: none;"
            "  border-radius: 8px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.08);"
            "}"
        )
        export_btns.addWidget(csv_btn)

        json_btn = QPushButton("Save JSON")
        json_btn.setFixedHeight(36)
        json_btn.setStyleSheet(csv_btn.styleSheet())
        export_btns.addWidget(json_btn)

        export_layout.addLayout(export_btns)

        panel_layout.addWidget(export_container)

        panel_layout.addStretch()

        return panel

    def _create_report_content(self):
        """Create the Report tab content for generating PDF reports with graphs, tables, and notes."""
        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame {"
            "  background: #F8F9FA;"
            "  border: none;"
            "}"
        )

        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)

        # Left side: Report Canvas/Preview
        left_panel = self._create_report_left_panel()
        content_layout.addWidget(left_panel, 3)

        # Right side: Tools and Content Library
        right_panel = self._create_report_right_panel()
        content_layout.addWidget(right_panel, 2)

        return content_widget

    def _create_report_left_panel(self):
        """Create left panel with report preview canvas."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {"
            "  background: transparent;"
            "  border: none;"
            "}"
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Report header with export
        header = QHBoxLayout()

        report_title = QLabel("Report Preview")
        report_title.setStyleSheet(
            "QLabel {"
            "  font-size: 17px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        header.addWidget(report_title)
        header.addStretch()

        # Generate PDF button
        pdf_btn = QPushButton("📄 Generate PDF")
        pdf_btn.setFixedHeight(40)
        pdf_btn.setMinimumWidth(140)
        pdf_btn.setStyleSheet(
            "QPushButton {"
            "  background: #FF3B30;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 10px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  padding: 0px 20px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #E6342A;"
            "}"
            "QPushButton:pressed {"
            "  background: #CC2E25;"
            "}"
        )
        header.addWidget(pdf_btn)

        panel_layout.addLayout(header)

        # Report canvas/preview area
        canvas = QFrame()
        canvas.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 25))
        shadow.setOffset(0, 4)
        canvas.setGraphicsEffect(shadow)

        canvas_layout = QVBoxLayout(canvas)
        canvas_layout.setContentsMargins(24, 24, 24, 24)
        canvas_layout.setSpacing(16)

        # Report content area with scroll
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            "QScrollArea {"
            "  border: none;"
            "  background: transparent;"
            "}"
        )

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(16, 16, 16, 16)
        scroll_layout.setSpacing(20)

        # Sample report elements
        # Title
        title_edit = QLabel("Kinetic Analysis Report")
        title_edit.setStyleSheet(
            "QLabel {"
            "  font-size: 24px;"
            "  font-weight: 700;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  padding: 8px;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        scroll_layout.addWidget(title_edit)

        # Date/Info
        info_label = QLabel("Date: November 20, 2025\nExperiment ID: EXP-2025-001")
        info_label.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  padding: 4px 8px;"
            "  line-height: 1.6;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        scroll_layout.addWidget(info_label)

        # Placeholder for graph
        graph_placeholder = QFrame()
        graph_placeholder.setFixedHeight(250)
        graph_placeholder.setStyleSheet(
            "QFrame {"
            "  background: rgba(0, 122, 255, 0.05);"
            "  border: 2px dashed rgba(0, 0, 0, 0.1);"
            "  border-radius: 8px;"
            "}"
        )
        graph_label = QLabel("[Graph Element]\n\nClick to insert graph")
        graph_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        graph_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  border: none;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        graph_layout = QVBoxLayout(graph_placeholder)
        graph_layout.addWidget(graph_label)
        scroll_layout.addWidget(graph_placeholder)

        # Notes section
        notes_label = QLabel("Notes:")
        notes_label.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  padding: 8px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        scroll_layout.addWidget(notes_label)

        from PySide6.QtWidgets import QTextEdit
        notes_edit = QTextEdit()
        notes_edit.setPlaceholderText("Add experiment notes, observations, or conclusions...")
        notes_edit.setFixedHeight(120)
        notes_edit.setStyleSheet(
            "QTextEdit {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "  padding: 12px;"
            "  font-size: 13px;"
            "  color: #1D1D1F;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        scroll_layout.addWidget(notes_edit)

        # Table placeholder
        table_placeholder = QFrame()
        table_placeholder.setFixedHeight(180)
        table_placeholder.setStyleSheet(
            "QFrame {"
            "  background: rgba(52, 199, 89, 0.05);"
            "  border: 2px dashed rgba(52, 199, 89, 0.3);"
            "  border-radius: 8px;"
            "}"
        )
        table_label = QLabel("[Table Element]\n\nClick to insert data table")
        table_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  color: #34C759;"
            "  background: transparent;"
            "  border: none;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        table_layout = QVBoxLayout(table_placeholder)
        table_layout.addWidget(table_label)
        scroll_layout.addWidget(table_placeholder)

        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_content)
        canvas_layout.addWidget(scroll_area, 1)

        panel_layout.addWidget(canvas, 1)

        return panel

    def _create_report_right_panel(self):
        """Create right panel with report tools and content library."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {"
            "  background: transparent;"
            "  border: none;"
            "}"
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Insert Elements Section
        elements_container = QFrame()
        elements_container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        elements_container.setGraphicsEffect(shadow)

        elements_layout = QVBoxLayout(elements_container)
        elements_layout.setContentsMargins(16, 16, 16, 16)
        elements_layout.setSpacing(12)

        elements_title = QLabel("Insert Elements")
        elements_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        elements_layout.addWidget(elements_title)

        # Element buttons
        element_btns = [
            ("📊 Graph", "Insert saved graph"),
            ("📈 Bar Chart", "Create bar chart"),
            ("📋 Table", "Insert data table"),
            ("📝 Text Box", "Add text section"),
            ("🖼️ Image", "Insert image"),
        ]

        for icon_text, tooltip in element_btns:
            elem_btn = QPushButton(icon_text)
            elem_btn.setFixedHeight(36)
            elem_btn.setToolTip(tooltip)
            elem_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.04);"
                "  color: #1D1D1F;"
                "  border: none;"
                "  border-radius: 8px;"
                "  font-size: 13px;"
                "  font-weight: 500;"
                "  text-align: left;"
                "  padding-left: 12px;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.08);"
                "}"
                "QPushButton:pressed {"
                "  background: rgba(0, 0, 0, 0.12);"
                "}"
            )
            elements_layout.addWidget(elem_btn)

        panel_layout.addWidget(elements_container)

        # Chart Builder Tool
        chart_container = QFrame()
        chart_container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        chart_container.setGraphicsEffect(shadow)

        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(16, 16, 16, 16)
        chart_layout.setSpacing(12)

        chart_title = QLabel("Chart Builder")
        chart_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        chart_layout.addWidget(chart_title)

        # Chart type selector
        chart_types = QHBoxLayout()
        chart_types.setSpacing(6)

        for chart_type in ["Bar", "Line", "Scatter"]:
            type_btn = QPushButton(chart_type)
            type_btn.setCheckable(True)
            type_btn.setChecked(chart_type == "Bar")
            type_btn.setFixedHeight(32)
            type_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: #86868B;"
                "  border: none;"
                "  border-radius: 6px;"
                "  font-size: 12px;"
                "  font-weight: 500;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:checked {"
                "  background: #1D1D1F;"
                "  color: white;"
                "  font-weight: 600;"
                "}"
            )
            chart_types.addWidget(type_btn)

        chart_layout.addLayout(chart_types)

        # Data source
        source_label = QLabel("Data Source:")
        source_label.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        chart_layout.addWidget(source_label)

        from PySide6.QtWidgets import QComboBox
        source_dropdown = QComboBox()
        source_dropdown.addItems([
            "Kinetic Results",
            "Cycle Statistics",
            "Custom Data"
        ])
        source_dropdown.setFixedHeight(32)
        source_dropdown.setStyleSheet(
            "QComboBox {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  color: #1D1D1F;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 6px 10px;"
            "  font-size: 12px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        chart_layout.addWidget(source_dropdown)

        # Create chart button
        create_chart_btn = QPushButton("Create Chart")
        create_chart_btn.setFixedHeight(36)
        create_chart_btn.setStyleSheet(
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #3A3A3C;"
            "}"
        )
        chart_layout.addWidget(create_chart_btn)

        panel_layout.addWidget(chart_container)

        # Saved Content Library
        library_container = QFrame()
        library_container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        library_container.setGraphicsEffect(shadow)

        library_layout = QVBoxLayout(library_container)
        library_layout.setContentsMargins(16, 16, 16, 16)
        library_layout.setSpacing(12)

        library_title = QLabel("Content Library")
        library_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        library_layout.addWidget(library_title)

        # Saved items list
        saved_items = [
            "📊 Sensorgram_ChA",
            "📈 Kinetic_Fit_Plot",
            "📋 Results_Table_1",
        ]

        for item in saved_items:
            item_btn = QPushButton(item)
            item_btn.setFixedHeight(32)
            item_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.03);"
                "  color: #1D1D1F;"
                "  border: none;"
                "  border-radius: 6px;"
                "  font-size: 12px;"
                "  font-weight: 400;"
                "  text-align: left;"
                "  padding-left: 12px;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.06);"
                "}"
            )
            library_layout.addWidget(item_btn)

        panel_layout.addWidget(library_container, 1)

        panel_layout.addStretch()

        return panel

    def _switch_page(self, page_index):
        """Switch to the selected page and update button states."""
        self.content_stack.setCurrentIndex(page_index)

        # Update button checked states (radio button behavior)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == page_index)

    def _update_power_button_style(self):
        """Update power button appearance based on current state with 3D effect."""
        state = self.power_btn.property("powerState")

        if state == "disconnected":
            # Gray - No device connected
            self.power_btn.setStyleSheet(
                "QPushButton {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(46, 48, 227, 0.4), stop:1 rgba(46, 48, 227, 0.5));"
                "  color: white;"
                "  border: 1px solid rgba(46, 48, 227, 0.2);"
                "  border-radius: 8px;"
                "  font-size: 18px;"
                "  font-weight: 400;"
                "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(46, 48, 227, 0.5), stop:1 rgba(46, 48, 227, 0.6));"
                "  border: 1px solid rgba(46, 48, 227, 0.3);"
                "}"
            )
            self.power_btn.setToolTip("Power On Device (Ctrl+P)\nGray = Disconnected")
        elif state == "searching":
            # Yellow - Searching for device
            self.power_btn.setStyleSheet(
                "QPushButton {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFCC00, stop:1 #E6B800);"
                "  color: white;"
                "  border: 1px solid rgba(255, 204, 0, 0.3);"
                "  border-radius: 8px;"
                "  font-size: 18px;"
                "  font-weight: 400;"
                "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E6B800, stop:1 #CCA300);"
                "  border: 1px solid rgba(230, 184, 0, 0.3);"
                "}"
            )
            self.power_btn.setToolTip("Searching for Device...\nClick to CANCEL search")
        elif state == "connected":
            # Green - Device powered and connected
            self.power_btn.setStyleSheet(
                "QPushButton {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #34C759, stop:1 #2EAF4F);"
                "  color: white;"
                "  border: 1px solid rgba(52, 199, 89, 0.3);"
                "  border-radius: 8px;"
                "  font-size: 18px;"
                "  font-weight: 400;"
                "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2EAF4F, stop:1 #289845);"
                "  border: 1px solid rgba(46, 175, 79, 0.3);"
                "}"
            )
            self.power_btn.setToolTip("Power Off Device (Ctrl+P)\nGreen = Device Connected\nClick to power off")

    def _handle_power_click(self):
        """Handle power button click - connects/disconnects hardware.

        Button behavior:
        - DISCONNECTED (gray): Click to start connection → SEARCHING (yellow)
        - SEARCHING (yellow): Click to cancel search → DISCONNECTED (gray)
        - CONNECTED (green): Click to disconnect → DISCONNECTED (gray)
        """
        current_state = self.power_btn.property("powerState")
        logger.info(f"Power button clicked: current_state={current_state}")
        print(f"\n{'='*80}")
        print(f"[UI] Power button clicked! Current state: {current_state}")
        print(f"{'='*80}\n")

        if current_state == "disconnected":
            # Start hardware connection
            logger.info("[UI] Power ON: Starting hardware connection...")
            print("[UI] Power ON: Starting hardware connection...")

            # Emit signal to trigger hardware connection (handled by Application class)
            logger.info(f"[UI] Checking for power_on_requested signal: {hasattr(self, 'power_on_requested')}")
            print(f"[UI] Has signal 'power_on_requested': {hasattr(self, 'power_on_requested')}")

            if hasattr(self, 'power_on_requested'):
                logger.info("[UI] Emitting power_on_requested signal...")
                print("[UI] Emitting power_on_requested signal...")
                self.power_on_requested.emit()
                logger.info("[UI] Signal power_on_requested.emit() completed!")
                print("[UI] Signal emitted successfully!")
            else:
                logger.error("[UI] ERROR: power_on_requested signal not defined!")
                print("[UI] ERROR: power_on_requested signal not defined!")

            # Update UI state to searching
            self.power_btn.setProperty("powerState", "searching")
            self._update_power_button_style()
            logger.info("[UI] Power button state updated to 'searching'")

        elif current_state == "searching":
            # Cancel hardware connection in progress
            print("[UI] CANCEL: User cancelled hardware search")

            # Return to disconnected state
            self.power_btn.setProperty("powerState", "disconnected")
            self._update_power_button_style()
            self._reset_subunit_status()  # Reset subunit status to gray

            # Emit signal to cancel connection (if backend supports it)
            # Backend will handle stopping the connection thread
            if hasattr(self, 'power_off_requested'):
                self.power_off_requested.emit()

        elif current_state == "connected":
            # Power OFF: Show warning dialog
            from PySide6.QtWidgets import QMessageBox

            warning = QMessageBox(self)
            warning.setWindowTitle("Power Off Device")
            warning.setIcon(QMessageBox.Icon.Warning)
            warning.setText("Are you sure you want to disconnect the device?")
            warning.setInformativeText("All hardware connections will be closed.")
            warning.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
            warning.setDefaultButton(QMessageBox.StandardButton.Cancel)

            # Style the warning dialog
            warning.setStyleSheet(
                "QMessageBox {"
                "  background: #FFFFFF;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QLabel {"
                "  color: #1D1D1F;"
                "  font-size: 13px;"
                "}"
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: #1D1D1F;"
                "  border: none;"
                "  border-radius: 6px;"
                "  padding: 6px 16px;"
                "  font-size: 13px;"
                "  min-width: 60px;"
                "  min-height: 28px;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.1);"
                "}"
                "QPushButton:default {"
                "  background: #FF3B30;"
                "  color: white;"
                "  font-weight: 600;"
                "}"
                "QPushButton:default:hover {"
                "  background: #E6342A;"
                "}"
            )

            result = warning.exec()

            if result == QMessageBox.StandardButton.Yes:
                # User confirmed power off
                print("[UI] Power OFF: Disconnecting hardware...")
                self.power_btn.setProperty("powerState", "disconnected")
                self._update_power_button_style()
                self.power_btn.setChecked(False)

                # Reset all subunit status to "Not Ready"
                self._reset_subunit_status()

                # Emit signal to disconnect hardware
                if hasattr(self, 'power_off_requested'):
                    self.power_off_requested.emit()
            else:
                # User cancelled, revert button state
                self.power_btn.setChecked(True)
                print("[UI] Power OFF cancelled by user")

    def set_power_state(self, state: str):
        """Set power button state from external controller.

        Args:
            state: 'disconnected', 'searching', or 'connected'
        """
        self.power_btn.setProperty("powerState", state)
        self._update_power_button_style()

        # Reset subunit status whenever power state is not "connected"
        if state in ["disconnected", "searching"]:
            self._reset_subunit_status()

    def _set_power_button_state(self, state: str):
        """Alias for set_power_state for backward compatibility."""
        self.set_power_state(state)

    def enable_controls(self) -> None:
        """Enable record and pause buttons after calibration completes."""
        try:
            logger.info("🎮 Enabling recording controls (calibration complete)")
            self.record_btn.setEnabled(True)
            self.pause_btn.setEnabled(True)
            self.record_btn.setToolTip("Start Recording\n(Click to begin saving data)")
            self.pause_btn.setToolTip("Pause Live Acquisition\n(Click to temporarily stop data flow)")
        except Exception as e:
            # Suppress Qt threading warnings that are false positives
            if 'QTextDocument' not in str(e) and 'different thread' not in str(e):
                raise

    def _reset_subunit_status(self) -> None:
        """Reset all subunit status indicators to 'Not Ready' state."""
        for subunit_name in ["Sensor", "Optics", "Fluidics"]:
            if subunit_name in self.sidebar.subunit_status:
                indicator = self.sidebar.subunit_status[subunit_name]['indicator']
                status_label = self.sidebar.subunit_status[subunit_name]['status_label']

                # Gray indicator and "Not Ready" text
                indicator.setStyleSheet(
                    "font-size: 10px;"
                    "color: #86868B;"  # Gray
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                status_label.setText("Not Ready")
                status_label.setStyleSheet(
                    "font-size: 13px;"
                    "color: #86868B;"  # Gray
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )

        # Also disable all operation modes when disconnecting
        # Use empty status dict to indicate no hardware connected
        self._update_operation_modes({})

    def _handle_scan_hardware(self) -> None:
        """Handle hardware scan button click - trigger real hardware scan."""
        # Don't scan if already scanning
        if self.sidebar.scan_btn.property("scanning"):
            return

        logger.info("[SCAN] User requested hardware scan...")
        self.sidebar.scan_btn.setProperty("scanning", True)
        self._update_scan_button_style()

        # Emit signal to trigger actual hardware scan in Application
        # The Application class will handle the actual hardware manager scan
        if hasattr(self, 'app') and self.app:
            self.app.hardware_mgr.scan_and_connect()
        else:
            logger.warning("No application reference - cannot trigger hardware scan")
            # Reset button state after 1 second
            QTimer.singleShot(1000, lambda: (
                self.sidebar.scan_btn.setProperty("scanning", False),
                self._update_scan_button_style()
            ))

    def _on_hardware_scan_complete(self) -> None:
        """Called when hardware scan completes - reset scan button."""
        self.sidebar.scan_btn.setProperty("scanning", False)
        self._update_scan_button_style()
        logger.info("[SCAN] Hardware scan complete - button reset")

    def update_hardware_status(self, status: Dict[str, Any]) -> None:
        """Update hardware status display with real hardware information.

        Args:
            status: Dict with keys:
                - ctrl_type: Controller type (P4SPR, PicoP4SPR, etc.)
                - knx_type: Kinetic controller type (KNX2, etc.)
                - pump_connected: Boolean
                - spectrometer: Boolean
                - sensor_ready: Boolean
                - optics_ready: Boolean
                - fluidics_ready: Boolean
        """
        # Build list of connected devices
        # ONLY show the 5 valid hardware types: P4SPR, P4PRO, ezSPR, KNX, AffiPump
        devices = []

        ctrl_type = status.get('ctrl_type')

        # Map internal names to display names
        # Valid hardware: P4SPR, P4PRO, ezSPR, KNX, AffiPump
        # Common pairings: P4SPR+KNX, P4PRO+AffiPump
        CONTROLLER_DISPLAY_NAMES = {
            'PicoP4SPR': 'P4SPR',
            'P4SPR': 'P4SPR',
            'PicoP4PRO': 'P4PRO',
            'P4PRO': 'P4PRO',
            'PicoEZSPR': 'P4PRO',  # PicoEZSPR hardware = P4PRO product
            'EZSPR': 'ezSPR',
            'ezSPR': 'ezSPR'
        }

        KNX_DISPLAY_NAMES = {
            'KNX': 'KNX',
            'KNX2': 'KNX',
            'PicoKNX2': 'KNX'
        }

        # Controller (P4SPR, P4PRO, ezSPR)
        if ctrl_type:
            display_name = CONTROLLER_DISPLAY_NAMES.get(ctrl_type, None)
            if display_name:
                devices.append(display_name)
            else:
                # Unknown controller - log warning but don't display
                from utils.logger import logger
                logger.warning(f"⚠️ Unknown controller type '{ctrl_type}' - not displayed in Hardware Connected")

        # Kinetic Controller (KNX)
        knx_type = status.get('knx_type')
        if knx_type:
            display_name = KNX_DISPLAY_NAMES.get(knx_type, None)
            if display_name:
                devices.append(display_name)
            else:
                # Unknown kinetic type - log warning but don't display
                from utils.logger import logger
                logger.warning(f"⚠️ Unknown kinetic type '{knx_type}' - not displayed in Hardware Connected")

        # Pump (AffiPump)
        if status.get('pump_connected'):
            devices.append("AffiPump")

        # Update device labels
        for i, label in enumerate(self.sidebar.hw_device_labels):
            if i < len(devices):
                label.setText(f"• {devices[i]}")
                label.setVisible(True)
            else:
                label.setVisible(False)

        # Show/hide "no devices" message
        self.sidebar.hw_no_devices.setVisible(len(devices) == 0)

        # Update subunit readiness based on actual verification
        self._update_subunit_readiness_from_status(status)

        # Update operation mode availability based on hardware
        self._update_operation_modes(status)

    def _update_subunit_readiness_from_status(self, status: Dict[str, Any]) -> None:
        """Update subunit readiness based on hardware verification results."""
        logger.debug(f"🔍 _update_subunit_readiness_from_status called with: sensor_ready={status.get('sensor_ready')}, optics_ready={status.get('optics_ready')}, fluidics_ready={status.get('fluidics_ready')}")

        # Sensor readiness
        if 'sensor_ready' in status:
            self._set_subunit_status('Sensor', status['sensor_ready'])

        # Optics readiness
        if 'optics_ready' in status:
            optics_ready = status['optics_ready']
            optics_details = {
                'failed_channels': status.get('optics_failed_channels', []),
                'maintenance_channels': status.get('optics_maintenance_channels', [])
            }
            self._set_subunit_status('Optics', optics_ready, details=optics_details)

        # Fluidics readiness
        if 'fluidics_ready' in status:
            self._set_subunit_status('Fluidics', status['fluidics_ready'])

    def _set_subunit_status(self, subunit_name: str, is_ready: bool, details: Optional[Dict[str, Any]] = None) -> None:
        """Set the status of a specific subunit.

        Args:
            subunit_name: Name of subunit (Sensor, Optics, Fluidics)
            is_ready: True if ready, False otherwise
            details: Optional dict with 'failed_channels' and 'maintenance_channels' for Optics
        """
        if subunit_name in self.sidebar.subunit_status:
            indicator = self.sidebar.subunit_status[subunit_name]['indicator']
            status_label = self.sidebar.subunit_status[subunit_name]['status_label']

            if is_ready:
                # Green indicator and "Ready" text
                indicator.setStyleSheet(
                    "font-size: 14px;"
                    "color: #34C759;"  # Green
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                status_label.setText("Ready")
                status_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #34C759;"  # Green
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                # Clear optics warning if it was active
                if subunit_name == 'Optics' and hasattr(self, '_optics_warning_active'):
                    self._clear_optics_warning()
            else:
                # Red indicator for Optics and Sensor, Gray for Fluidics
                color = '#FF3B30' if subunit_name in ['Optics', 'Sensor'] else '#86868B'
                indicator.setStyleSheet(
                    "font-size: 14px;"
                    f"color: {color};"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                status_label.setText("Not Ready")
                status_label.setStyleSheet(
                    "font-size: 12px;"
                    f"color: {color};"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                # Store optics status details for warning message
                if subunit_name == 'Optics' and details:
                    self._optics_status_details = details

            from utils.logger import logger
            logger.info(f"{subunit_name}: {'Ready' if is_ready else 'Not Ready'}")

    def _set_optics_warning(self) -> None:
        """Apply light red background to live sensorgram when proceeding with unready optics."""
        # Only set warning if we actually have optics issues (not just unverified)
        if not hasattr(self, '_optics_status_details') or not self._optics_status_details:
            from utils.logger import logger
            logger.debug("_set_optics_warning called but no optics issues detected - skipping red background")
            return

        if hasattr(self, 'full_timeline_graph') and self.full_timeline_graph:
            self.full_timeline_graph.setBackground('#FFE5E5')  # Light red
            self._optics_warning_active = True

            # Log warning with details
            if self._optics_status_details:
                failed = self._optics_status_details.get('failed_channels', [])
                maintenance = self._optics_status_details.get('maintenance_channels', [])

                if failed or maintenance:  # Only warn if there are actual problems
                    failed_str = ', '.join([ch.upper() for ch in failed]) if failed else 'none'
                    maint_str = ', '.join([ch.upper() for ch in maintenance]) if maintenance else 'none'

                    from utils.logger import logger
                    logger.warning(f"⚠️ Optics NOT ready: calibration failed for channels [{failed_str}], maintenance required for channels [{maint_str}]")
                    logger.warning("   Live sensorgram background set to light red - please resolve optics issues")

    def _clear_optics_warning(self) -> None:
        """Clear light red background from live sensorgram when optics become ready."""
        if hasattr(self, 'full_timeline_graph') and self.full_timeline_graph and self._optics_warning_active:
            self.full_timeline_graph.setBackground('#FFFFFF')  # White
            self._optics_warning_active = False
            self._optics_status_details = None

            from utils.logger import logger
            logger.info("✅ Optics ready - sensorgram background restored to normal")

    def _update_operation_modes(self, status: Dict[str, Any]) -> None:
        """Update available operation modes based on hardware type."""
        ctrl_type = status.get('ctrl_type', '')
        has_pump = status.get('pump_connected', False)

        from utils.logger import logger

        # P4SPR static device - only Static mode
        if ctrl_type in ['P4SPR', 'PicoP4SPR']:
            logger.info("P4SPR device detected - Static mode available")
            # Static mode always available for P4SPR
            # Flow mode only if pump is connected
            if has_pump:
                logger.info("Pump detected - Flow mode also available")
            else:
                logger.info("No pump - Flow mode disabled")

        # EZSPR or other devices
        elif ctrl_type in ['EZSPR', 'PicoEZSPR']:
            logger.info("EZSPR device detected - Static and Flow modes available")

    def _update_scan_button_style(self) -> None:
        """Update scan button style based on scanning state."""
        is_scanning = self.sidebar.scan_btn.property("scanning")

        if is_scanning:
            # Scanning state (yellow/disabled)
            self.sidebar.scan_btn.setText("Scanning...")
            self.sidebar.scan_btn.setEnabled(False)
            self.sidebar.scan_btn.setStyleSheet(
                "QPushButton {"
                "  background: #FFCC00;"
                "  color: #1D1D1F;"
                "  border: none;"
                "  border-radius: 6px;"
                "  padding: 8px 12px;"
                "  font-size: 13px;"
                "  text-align: center;"
                "  margin-left: 12px;"
                "  margin-top: 8px;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
            )
        else:
            # Normal state (blue/clickable)
            self.sidebar.scan_btn.setText("Scan for Hardware")
            self.sidebar.scan_btn.setEnabled(True)
            self.sidebar.scan_btn.setStyleSheet(
                "QPushButton {"
                "  background: #1D1D1F;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 6px;"
                "  padding: 8px 12px;"
                "  font-size: 13px;"
                "  text-align: center;"
                "  margin-left: 12px;"
                "  margin-top: 8px;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: #3A3A3C;"
                "}"
                "QPushButton:pressed {"
                "  background: #48484A;"
                "}"
            )

    def _handle_debug_log_download(self) -> None:
        """Handle debug log download button click."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import datetime

        # Generate filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"AffiLabs_debug_log_{timestamp}.txt"

        # Open file save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Debug Log",
            default_filename,
            "Log Files (*.txt *.log);;All Files (*.*)"
        )

        if file_path:
            try:
                # In real app, this would collect actual debug log data
                # For prototype, create a sample debug log
                debug_content = f"""ezControl Debug Log
Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
================================================

SYSTEM INFORMATION
------------------
Software Version: 4.0.0
Python Version: 3.12.0
Qt Version: 6.10.0
Operating System: Windows 11

HARDWARE STATUS
------------------
Connected Devices: 1
  - Device Type: SPR Sensor
  - Serial Number: SPR-2025-001
  - Firmware Version: 2.3.1
  - Connection: USB 3.0

SUBUNIT STATUS
------------------
Sensor: Ready
Optics: Ready
Fluidics: Not Ready

OPERATIONAL LOG
------------------
[2025-11-20 14:23:15] Device powered on
[2025-11-20 14:23:16] Hardware scan initiated
[2025-11-20 14:23:17] Device SPR-2025-001 detected
[2025-11-20 14:23:18] Subunit readiness check completed
[2025-11-20 14:23:20] Calibration loaded
[2025-11-20 14:24:00] Recording started - Cycle 1
[2025-11-20 14:29:00] Recording stopped

PERFORMANCE METRICS
------------------
Total Operation Hours: 1,247 hrs
Last Operation: Nov 19, 2025
Average Session Duration: 3.2 hrs
Total Cycles Recorded: 8,432

ERROR LOG
------------------
[2025-11-19 10:15:23] WARNING: Temperature drift detected (23.2°C -> 23.8°C)
[2025-11-18 15:42:10] INFO: Fluidics pump recalibrated
[2025-11-17 08:30:05] WARNING: LED intensity below threshold, auto-adjusted

MAINTENANCE REMINDERS
------------------
• Clean optics - Due at 1,500 hrs (253 hrs remaining)
• Replace flow cell - Due at 2,000 hrs (753 hrs remaining)
• Calibration check - Due every 250 hrs (Next: 3 hrs)

================================================
End of Debug Log
"""

                # Write to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(debug_content)

                # Show success message
                msg = QMessageBox(self)
                msg.setWindowTitle("Debug Log Saved")
                msg.setIcon(QMessageBox.Icon.Information)
                msg.setText("Debug log saved successfully")
                msg.setInformativeText(f"File saved to:\n{file_path}")
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg.setStyleSheet(
                    "QMessageBox {"
                    "  background: #FFFFFF;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QLabel {"
                    "  color: #1D1D1F;"
                    "  font-size: 13px;"
                    "}"
                    "QPushButton {"
                    "  background: #1D1D1F;"
                    "  color: white;"
                    "  border: none;"
                    "  border-radius: 6px;"
                    "  padding: 6px 16px;"
                    "  font-size: 13px;"
                    "  font-weight: 600;"
                    "  min-width: 60px;"
                    "  min-height: 28px;"
                    "}"
                    "QPushButton:hover {"
                    "  background: #3A3A3C;"
                    "}"
                )
                msg.exec()

                logger.info(f"Debug log saved to: {file_path}")

            except Exception as e:
                # Show error message
                error_msg = QMessageBox(self)
                error_msg.setWindowTitle("Error")
                error_msg.setIcon(QMessageBox.Icon.Critical)
                error_msg.setText("Failed to save debug log")
                error_msg.setInformativeText(f"Error: {str(e)}")
                error_msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                error_msg.setStyleSheet(
                    "QMessageBox {"
                    "  background: #FFFFFF;"
                    "}"
                    "QPushButton {"
                    "  background: #FF3B30;"
                    "  color: white;"
                    "  border: none;"
                    "  border-radius: 6px;"
                    "  padding: 6px 16px;"
                    "}"
                )
                error_msg.exec()

                logger.error(f"Error saving debug log: {e}")

    def _toggle_recording(self):
        """Toggle recording state - emit signal for Application to handle."""
        # Emit signal based on current recording state
        if not self.is_recording:
            # Request to start recording - emit signal
            if hasattr(self, 'recording_start_requested'):
                self.recording_start_requested.emit()
        else:
            # Request to stop recording - emit signal
            if hasattr(self, 'recording_stop_requested'):
                self.recording_stop_requested.emit()

    def _toggle_pause(self):
        """Toggle pause state for live acquisition."""
        is_paused = self.pause_btn.isChecked()

        if is_paused:
            # Pause acquisition
            self.pause_btn.setToolTip("Resume Live Acquisition")
            logger.info("⏸ Live acquisition paused")
            # Emit signal to pause acquisition
            if hasattr(self, 'acquisition_pause_requested'):
                self.acquisition_pause_requested.emit(True)

            # Add pause marker to live sensorgram (system-level flag, not channel-specific)
            if hasattr(self, 'full_timeline_graph'):
                import pyqtgraph as pg
                from PySide6.QtCore import QTime
                pause_time = QTime.currentTime().msecsSinceStartOfDay() / 1000.0

                pause_line = pg.InfiniteLine(
                    pos=pause_time,
                    angle=90,
                    pen=pg.mkPen(color='#FF9500', width=2, style=pg.QtCore.Qt.PenStyle.DashLine),
                    movable=False,
                    label='⏸ Paused',
                    labelOpts={'position': 0.95, 'color': '#FF9500'}
                )
                self.full_timeline_graph.addItem(pause_line)

                # Store reference to pause marker
                if not hasattr(self, 'pause_markers'):
                    self.pause_markers = []
                self.pause_markers.append({'time': pause_time, 'line': pause_line, 'type': 'pause'})
        else:
            # Resume acquisition
            self.pause_btn.setToolTip("Pause Live Acquisition")
            logger.info("▶️ Live acquisition resumed")
            # Emit signal to resume acquisition
            if hasattr(self, 'acquisition_pause_requested'):
                self.acquisition_pause_requested.emit(False)

            # Add resume marker to live sensorgram
            if hasattr(self, 'full_timeline_graph'):
                import pyqtgraph as pg
                from PySide6.QtCore import QTime
                resume_time = QTime.currentTime().msecsSinceStartOfDay() / 1000.0

                resume_line = pg.InfiniteLine(
                    pos=resume_time,
                    angle=90,
                    pen=pg.mkPen(color='#34C759', width=2, style=pg.QtCore.Qt.PenStyle.DashLine),
                    movable=False,
                    label='▶️ Resumed',
                    labelOpts={'position': 0.95, 'color': '#34C759'}
                )
                self.full_timeline_graph.addItem(resume_line)

                # Store reference to resume marker
                if not hasattr(self, 'pause_markers'):
                    self.pause_markers = []
                self.pause_markers.append({'time': resume_time, 'line': resume_line, 'type': 'resume'})

    def set_recording_state(self, is_recording: bool, filename: str = ""):
        """Update recording UI state from external controller.

        Args:
            is_recording: True if recording is active
            filename: Name of the recording file (if recording)
        """
        self.is_recording = is_recording
        self.record_btn.setChecked(is_recording)

        if is_recording:
            # Update button tooltip
            display_name = Path(filename).name if filename else "data.csv"
            self.record_btn.setToolTip(f"Stop Recording\n(Recording to: {display_name})")

            # Recording indicator still hidden, but update internally for compatibility
            self.rec_status_dot.setStyleSheet(
                "QLabel {"
                "  color: #FF3B30;"
                "  font-size: 16px;"
                "  background: transparent;"
                "}"
            )
            display_name = Path(filename).name if filename else "data.csv"
            self.rec_status_text.setText(f"Recording to: {display_name}")
            self.rec_status_text.setStyleSheet(
                "QLabel {"
                "  font-size: 12px;"
                "  color: #FF3B30;"
                "  background: transparent;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "  font-weight: 600;"
                "}"
            )
            self.recording_indicator.setStyleSheet(
                "QFrame {"
                "  background: rgba(255, 59, 48, 0.1);"
                "  border: 1px solid rgba(255, 59, 48, 0.3);"
                "  border-radius: 6px;"
                "}"
            )
        else:
            # Update button tooltip back to viewing mode
            self.record_btn.setToolTip("Start Recording\n(Currently viewing - not saved)")

            # Update recording indicator back to viewing mode (hidden but kept for compatibility)
            self.rec_status_dot.setStyleSheet(
                "QLabel {"
                "  color: #86868B;"
                "  font-size: 16px;"
                "  background: transparent;"
                "}"
            )
            self.recording_indicator.setStyleSheet(
                "QFrame {"
                "  background: rgba(0, 0, 0, 0.04);"
                "  border-radius: 6px;"
                "}"
            )

    def _init_device_config(self, device_serial: Optional[str] = None):
        """Initialize device configuration for maintenance tracking.

        Args:
            device_serial: Spectrometer serial number for device-specific configuration.
                          If None, uses default config (not device-specific).
        """
        try:
            import os
            from utils.device_configuration import DeviceConfiguration

            # Get controller reference for EEPROM operations and hardware detection
            controller = None
            if hasattr(self, 'app') and self.app and hasattr(self.app, 'hardware_mgr'):
                controller = self.app.hardware_mgr.ctrl if self.app.hardware_mgr else None

            self.device_config = DeviceConfiguration(device_serial=device_serial, controller=controller)

            # Initialize tracking variables
            self.led_start_time = None
            self.last_powered_on = None

            # Check if config was created from scratch (not loaded from JSON or EEPROM)
            # If so, prompt user to complete missing fields
            if self.device_config.created_from_scratch:
                logger.info("=" * 80)
                logger.info("📋 NEW DEVICE CONFIGURATION - User Input Required")
                logger.info("=" * 80)
                logger.info(f"   Device Serial: {device_serial or 'Unknown'}")
                logger.info(f"   Config created with known info (serial, controller)")
                logger.info(f"   Missing fields: LED model, fiber diameter")
                logger.info("")
                logger.info("Workflow:")
                logger.info("   1. User fills device config dialog")
                logger.info("   2. Trigger servo calibration (auto-detect S/P positions)")
                logger.info("   3. Trigger LED calibration (calculate optimal intensities)")
                logger.info("   4. Save complete config to JSON and EEPROM")
                logger.info("=" * 80)

                # Show popup to collect missing device configuration
                self._prompt_device_config(device_serial)
            else:
                logger.info(f"✓ Device configuration loaded successfully")
                if self.device_config.loaded_from_eeprom:
                    logger.info(f"  Source: EEPROM → JSON (auto-saved)")
                else:
                    logger.info(f"  Source: JSON file")

            # Update UI with current values
            self._update_maintenance_display()

            # Auto-load hardware settings into Settings sidebar
            if self.device_config:
                try:
                    s_pos, p_pos = self.device_config.get_servo_positions()
                    led_intensities = self.device_config.get_led_intensities()
                    self.sidebar.load_hardware_settings(
                        s_pos=s_pos,
                        p_pos=p_pos,
                        led_a=led_intensities.get('a', 0),
                        led_b=led_intensities.get('b', 0),
                        led_c=led_intensities.get('c', 0),
                        led_d=led_intensities.get('d', 0)
                    )
                    logger.info(f"Auto-loaded hardware settings to sidebar: S={s_pos}, P={p_pos}")
                except Exception as e:
                    logger.warning(f"Could not auto-load hardware settings: {e}")

            if device_serial:
                logger.info(f"Device configuration initialized for S/N: {device_serial}")
            else:
                logger.info("Device configuration initialized with default config")
        except Exception as e:
            logger.error(f"Failed to initialize device configuration: {e}")
            self.device_config = None

    def _check_missing_config_fields(self):
        """Check for missing critical configuration fields.

        Returns:
            List of missing field names, empty if all fields are present
        """
        if not self.device_config:
            return []

        missing = []
        hw = self.device_config.config.get('hardware', {})

        # Check essential fields only (LED model, controller type, fiber diameter, polarizer)
        if not hw.get('led_pcb_model'):
            missing.append('LED Model')

        if not hw.get('controller_type') and not hw.get('controller_model'):
            missing.append('Controller')

        if not hw.get('optical_fiber_diameter_um'):
            missing.append('Fiber Diameter')

        if not hw.get('polarizer_type'):
            missing.append('Polarizer')

        # Device ID is optional - don't require it
        return missing

    def _get_controller_type_from_hardware(self) -> str:
        """Get controller type from connected hardware.

        Returns:
            Controller type string: 'Arduino', 'PicoP4SPR', 'PicoEZSPR', or ''
        """
        # Import here to avoid issues if hardware not initialized
        try:
            from core.hardware_manager import HardwareManager
            # Try to get from main_window's hardware manager if available
            if hasattr(self, 'hardware_mgr') and self.hardware_mgr and self.hardware_mgr.ctrl:
                ctrl_name = getattr(self.hardware_mgr.ctrl, 'device_name', '').lower()
                if 'arduino' in ctrl_name or ctrl_name == 'p4spr':
                    return 'Arduino'
                elif 'pico_p4spr' in ctrl_name or 'picop4spr' in ctrl_name:
                    return 'PicoP4SPR'
                elif 'pico_ezspr' in ctrl_name or 'picoezspr' in ctrl_name:
                    return 'PicoEZSPR'
        except Exception as e:
            logger.debug(f"Could not determine controller type: {e}")
        return ''

    def _get_polarizer_type_for_controller(self, controller_type: str) -> str:
        """Determine polarizer type based on controller hardware rules.

        Hardware Rules:
        - Arduino P4SPR: Always 'round' (circular polarizer)
        - PicoP4SPR: Always 'round' (circular polarizer)
        - PicoEZSPR: Typically 'barrel' (2 fixed windows)

        Args:
            controller_type: Type of controller ('Arduino', 'PicoP4SPR', 'PicoEZSPR')

        Returns:
            'round' or 'barrel'
        """
        if controller_type in ['Arduino', 'PicoP4SPR']:
            return 'round'  # Circular polarizer
        elif controller_type == 'PicoEZSPR':
            return 'barrel'  # 2 fixed windows (S and P)
        return 'barrel'  # Default fallback

    def _prompt_device_config(self, device_serial: str):
        """Show dialog to collect missing device configuration.

        Args:
            device_serial: Device serial number
        """
        try:
            # Detect controller type from hardware
            controller_type = self._get_controller_type_from_hardware()

            # Get controller reference for EEPROM operations
            controller = None
            if hasattr(self, 'hardware_mgr') and self.hardware_mgr:
                controller = self.hardware_mgr.ctrl

            # Create dialog with controller and device_config for EEPROM support
            dialog = DeviceConfigDialog(
                self,
                device_serial,
                controller_type,
                controller=controller,
                device_config=self.device_config
            )

            # Pre-fill with existing values from config if available
            if self.device_config:
                hw = self.device_config.config.get('hardware', {})
                device_info = self.device_config.config.get('device_info', {})

                # Set LED model (map from full name to abbreviation)
                led_model = hw.get('led_pcb_model', 'luminus_cool_white')
                if led_model == 'luminus_cool_white':
                    dialog.led_model_combo.setCurrentText('LCW')
                elif led_model == 'osram_warm_white':
                    dialog.led_model_combo.setCurrentText('OWW')

                # Set controller type
                ctrl_type = hw.get('controller_type', controller_type)
                if ctrl_type:
                    index = dialog.controller_combo.findText(ctrl_type)
                    if index >= 0:
                        dialog.controller_combo.setCurrentIndex(index)

                # Set fiber diameter (map from number to A/B option)
                fiber_diameter = hw.get('optical_fiber_diameter_um', 200)
                if fiber_diameter == 100:
                    dialog.fiber_diameter_combo.setCurrentText('A (100 µm)')
                else:
                    dialog.fiber_diameter_combo.setCurrentText('B (200 µm)')

                # Set polarizer type
                polarizer_type = hw.get('polarizer_type', 'circle')
                index = dialog.polarizer_type_combo.findText(polarizer_type)
                if index >= 0:
                    dialog.polarizer_type_combo.setCurrentIndex(index)

                # Set device ID (pre-fill with detector serial if not set)
                device_id = device_info.get('device_id', device_serial)
                if device_id:
                    dialog.device_id_input.setText(device_id)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Get configuration data
                config_data = dialog.get_config_data()

                # Update device configuration
                hw = self.device_config.config['hardware']
                hw['led_pcb_model'] = config_data['led_pcb_model']
                hw['optical_fiber_diameter_um'] = config_data['optical_fiber_diameter_um']
                hw['polarizer_type'] = config_data['polarizer_type']
                hw['controller_model'] = config_data.get('controller_model', 'Raspberry Pi Pico P4SPR')
                hw['controller_type'] = config_data['controller_type']

                if config_data['device_id']:
                    self.device_config.config['device_info']['device_id'] = config_data['device_id']

                # Update LED type code based on model
                led_model = config_data['led_pcb_model']
                if led_model == 'luminus_cool_white':
                    hw['led_type_code'] = 'LCW'
                elif led_model == 'osram_warm_white':
                    hw['led_type_code'] = 'OWW'

                # Save configuration
                self.device_config.save()

                # Log what was saved for verification
                logger.info("✅ Device configuration updated and saved")
                logger.info(f"  LED Model: {hw.get('led_pcb_model')}")
                logger.info(f"  Controller: {hw.get('controller_type')} ({hw.get('controller_model')})")
                logger.info(f"  Fiber Diameter: {hw.get('optical_fiber_diameter_um')} µm")
                logger.info(f"  Polarizer: {hw.get('polarizer_type')}")
                logger.info(f"  Device ID: {self.device_config.config['device_info'].get('device_id', 'Not set')}")
                logger.info(f"  Config file: {self.device_config.config_path}")

                # Verify it was actually saved by re-checking
                missing_after_save = self._check_missing_config_fields()
                if missing_after_save:
                    logger.warning(f"⚠️ After saving, still missing fields: {missing_after_save}")
                    from widgets.message import show_message
                    show_message(
                        f"Configuration saved but some fields are still missing: {', '.join(missing_after_save)}",
                        "Configuration Warning"
                    )
                else:
                    logger.info("✅ All required fields are now present in config")

                    # Save configuration first (before calibrations)
                    logger.info("💾 Saving device configuration to JSON...")

                    # Notify application that device config is complete
                    # This will trigger OEM calibration workflow
                    logger.info("=" * 80)
                    logger.info("🏭 Device Configuration Complete - Starting Calibration Workflow")
                    logger.info("=" * 80)
                    logger.info(f"LED Model: {hw.get('led_pcb_model', 'N/A')}")
                    logger.info(f"Controller: {hw.get('controller_type', 'N/A')}")
                    logger.info(f"Fiber: {hw.get('optical_fiber_diameter_um', 'N/A')} µm")
                    logger.info(f"Polarizer: {hw.get('polarizer_type', 'N/A')}")
                    logger.info("")
                    logger.info("Next Steps:")
                    logger.info("  1. Run servo calibration to find S/P positions")
                    logger.info("  2. Run LED calibration to find optimal intensities")
                    logger.info("  3. Push complete config to EEPROM")
                    logger.info("=" * 80)

                    # Set flag for application to check
                    self.oem_config_just_completed = True

                    # Trigger calibration workflow (has its own progress messages)
                    self._start_oem_calibration_workflow()
            else:
                logger.warning("Device configuration dialog cancelled")
        except Exception as e:
            logger.error(f"Failed to prompt for device configuration: {e}")

    def _start_oem_calibration_workflow(self):
        """Start OEM calibration workflow after device config is complete.

        Workflow:
        1. Run servo calibration to find optimal S/P positions
        2. Pull S/P positions from calibration result and update device_config
        3. Run LED calibration to find optimal intensities
        4. Pull LED intensities from data_mgr and update device_config
        5. Push complete config to EEPROM
        """
        logger.info("🏭 Starting OEM calibration workflow...")

        # Check if hardware is ready
        if not hasattr(self, 'app') or not self.app:
            logger.error("Application not initialized")
            from widgets.message import show_message
            show_message(
                "Cannot start calibration: Application not initialized",
                msg_type="Error",
                title="Calibration Error"
            )
            return

        hardware_mgr = self.app.hardware_mgr
        data_mgr = self.app.data_mgr

        # Check for controller (always required)
        if not hardware_mgr or not hardware_mgr.ctrl:
            logger.error("Controller not connected")
            from widgets.message import show_message
            show_message(
                "Cannot start calibration:\\n"
                "Controller must be connected.\\n\\n"
                "Please connect controller and try again.",
                msg_type="Warning",
                title="Hardware Not Ready"
            )
            return

        # Check for spectrometer (required for calibrations)
        if not hardware_mgr.detector:
            logger.warning("Spectrometer not connected - waiting for connection")
            from widgets.message import show_message
            show_message(
                "Device configuration saved!\\n\\n"
                "Please connect the spectrometer to begin\\n"
                "automatic calibration.\\n\\n"
                "Calibration will start automatically\\n"
                "when the spectrometer is detected.",
                msg_type="Information",
                title="Connect Spectrometer"
            )
            return

        # Step 1: Run servo calibration
        logger.info("Step 1/5: Running servo calibration...")
        from widgets.message import show_message
        show_message(
            "Starting servo calibration...\\n\\n"
            "This will automatically find optimal\\n"
            "S and P polarizer positions.\\n\\n"
            "Please ensure water is on the sensor.\\n"
            "This takes about 1-2 minutes.",
            msg_type="Information",
            title="Servo Calibration"
        )

        # Trigger servo calibration in main app
        if hasattr(self.app, '_run_servo_auto_calibration'):
            # Run entire calibration workflow in a thread to avoid blocking UI
            import threading
            def oem_calibration_workflow():
                try:
                    # Step 1: Run servo calibration (this saves to device_config automatically if user accepts)
                    logger.info("Running servo auto-calibration...")
                    self.app._run_servo_auto_calibration()

                    # Step 2: Verify servo positions were saved
                    s_pos = self.device_config.config['hardware']['servo_s_position']
                    p_pos = self.device_config.config['hardware']['servo_p_position']

                    if s_pos == 10 and p_pos == 100:
                        logger.warning("Servo positions not updated - using defaults")
                        logger.warning("User may have declined servo calibration results")
                    else:
                        logger.info(f"✓ Servo positions confirmed: S={s_pos}, P={p_pos}")

                    # Step 3: Run LED calibration
                    logger.info("Step 2/5: Running LED calibration...")
                    from widgets.message import show_message
                    show_message(
                        "Servo calibration complete!\\n\\n"
                        "Now starting LED intensity calibration...\\n"
                        "This takes about 30-60 seconds.",
                        msg_type="Information",
                        title="LED Calibration"
                    )

                    # Trigger simple LED calibration
                    self.app._on_simple_led_calibration()

                    # Wait for LED calibration to complete
                    if hasattr(hardware_mgr, 'main_app') and hardware_mgr.main_app:
                        if hasattr(hardware_mgr.main_app, 'calibration_thread'):
                            hardware_mgr.main_app.calibration_thread.join()
                            logger.info("LED calibration thread completed")

                    # Step 4: Pull LED intensities from data_mgr and update config
                    logger.info("Step 3/5: Updating LED intensities in device config...")
                    import time
                    time.sleep(2)  # Brief delay to ensure data_mgr is updated

                    if data_mgr and hasattr(data_mgr, 'leds_calibrated') and data_mgr.leds_calibrated:
                        led_a = data_mgr.leds_calibrated.get('a', 0)
                        led_b = data_mgr.leds_calibrated.get('b', 0)
                        led_c = data_mgr.leds_calibrated.get('c', 0)
                        led_d = data_mgr.leds_calibrated.get('d', 0)

                        if any([led_a, led_b, led_c, led_d]):
                            self.device_config.config['calibration']['led_intensity_a'] = led_a
                            self.device_config.config['calibration']['led_intensity_b'] = led_b
                            self.device_config.config['calibration']['led_intensity_c'] = led_c
                            self.device_config.config['calibration']['led_intensity_d'] = led_d
                            self.device_config.config['calibration']['factory_calibrated'] = True
                            self.device_config.save()
                            logger.info(f"✓ LED intensities updated: A={led_a}, B={led_b}, C={led_c}, D={led_d}")
                        else:
                            logger.warning("LED intensities are all zero - calibration may have failed")
                    else:
                        logger.warning("Failed to read LED intensities from data_mgr")

                    # Step 5: Push complete config to EEPROM
                    logger.info("Step 4/5: Pushing complete config to EEPROM...")
                    if self.device_config.sync_to_eeprom(hardware_mgr.ctrl):
                        logger.info("=" * 80)
                        logger.info("✅ OEM CALIBRATION WORKFLOW COMPLETE!")
                        logger.info("=" * 80)
                        logger.info(f"   Servo Positions:")
                        logger.info(f"   • S position: {s_pos}°")
                        logger.info(f"   • P position: {p_pos}°")
                        logger.info(f"   LED Intensities:")
                        logger.info(f"   • Channel A: {self.device_config.config['calibration']['led_intensity_a']}")
                        logger.info(f"   • Channel B: {self.device_config.config['calibration']['led_intensity_b']}")
                        logger.info(f"   • Channel C: {self.device_config.config['calibration']['led_intensity_c']}")
                        logger.info(f"   • Channel D: {self.device_config.config['calibration']['led_intensity_d']}")
                        logger.info(f"   Configuration saved to:")
                        logger.info(f"   • JSON: {self.device_config.config_path}")
                        logger.info(f"   • EEPROM: Controller memory")
                        logger.info("=" * 80)

                        # Show success message
                        from widgets.message import show_message
                        show_message(
                            "✅ OEM Calibration Complete!\\n\\n"
                            "All calibrations finished successfully:\\n"
                            f"• Servo S: {s_pos}°\\n"
                            f"• Servo P: {p_pos}°\\n"
                            f"• LED A: {self.device_config.config['calibration']['led_intensity_a']}\\n"
                            f"• LED B: {self.device_config.config['calibration']['led_intensity_b']}\\n"
                            f"• LED C: {self.device_config.config['calibration']['led_intensity_c']}\\n"
                            f"• LED D: {self.device_config.config['calibration']['led_intensity_d']}\\n\\n"
                            "Configuration saved to JSON and EEPROM.\\n"
                            "Device is ready for use!",
                            msg_type="Information",
                            title="Calibration Success"
                        )
                    else:
                        logger.error("Failed to push config to EEPROM")
                        from widgets.message import show_message
                        show_message(
                            "Calibration completed but EEPROM sync failed.\\n\\n"
                            "Configuration is saved to JSON file only.",
                            msg_type="Warning",
                            title="EEPROM Sync Failed"
                        )
                except Exception as e:
                    logger.error(f"OEM calibration workflow failed: {e}")
                    logger.exception("Full traceback:")
                    from widgets.message import show_message
                    show_message(
                        f"Calibration workflow failed:\\n{str(e)}",
                        msg_type="Error",
                        title="Calibration Error"
                    )

            # Start workflow in background thread
            workflow_thread = threading.Thread(target=oem_calibration_workflow, daemon=True)
            workflow_thread.start()
        else:
            logger.error("Servo calibration method not found in application")

    def _update_maintenance_display(self):
        """Update the maintenance section with current values from device config."""
        if self.device_config is None:
            return

        # Check if maintenance widgets exist yet (UI might not be fully initialized)
        if not hasattr(self, 'hours_value'):
            return

        try:
            import datetime

            # Update operation hours
            led_hours = self.device_config.config['maintenance']['led_on_hours']
            self.hours_value.setText(f"{led_hours:,.1f} hrs")

            # Update last operation date
            if self.last_powered_on:
                last_op_str = self.last_powered_on.strftime("%b %d, %Y")
                self.last_op_value.setText(last_op_str)
            else:
                self.last_op_value.setText("Never")

            # Calculate next maintenance (November of current or next year)
            now = datetime.datetime.now()
            current_year = now.year
            current_month = now.month

            # If we're past November, schedule for next year
            if current_month >= 11:
                next_maintenance_year = current_year + 1
            else:
                next_maintenance_year = current_year

            self.next_maintenance_value.setText(f"November {next_maintenance_year}")

            # Highlight if maintenance is due this month
            if current_month == 11:
                self.next_maintenance_value.setStyleSheet(
                    "font-size: 13px;"
                    "color: #FF3B30;"  # Red for urgent
                    "background: transparent;"
                    "font-weight: 700;"
                    "margin-top: 6px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
            else:
                self.next_maintenance_value.setStyleSheet(
                    "font-size: 13px;"
                    "color: #FF9500;"  # Orange for scheduled
                    "background: transparent;"
                    "font-weight: 600;"
                    "margin-top: 6px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
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

            logger.info(f"LED operation stopped. Added {elapsed_hours:.2f} hours to total")

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

        logger.info(f"Device powered on at {self.last_powered_on.strftime('%Y-%m-%d %H:%M:%S')}")
        self._update_maintenance_display()

    def _on_start_queued_run(self):
        """Start executing queued cycles."""
        if not self.cycle_queue:
            logger.warning("No cycles in queue to start")
            return

        # Execute first cycle from queue
        cycle_data = self.cycle_queue[0]  # Don't pop yet, wait for completion
        cycle_data["state"] = "running"

        logger.info(f"🚀 Starting queued cycle: {cycle_data['type']} - {cycle_data['notes']}")

        # Update display to show running state
        self._update_queue_display()

        # Hide start run button while cycle is running
        self.sidebar.start_run_btn.setVisible(False)

        # Trigger the actual acquisition start through the app
        if hasattr(self, 'app') and self.app:
            self.app._on_start_button_clicked()

    def _on_clear_queue(self):
        """Clear all cycles from the queue."""
        if not self.cycle_queue:
            return

        # Confirm with user
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Clear Queue",
            f"Are you sure you want to clear {len(self.cycle_queue)} cycle(s) from the queue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.cycle_queue.clear()
            logger.info("Queue cleared")

            # Update UI
            self._update_queue_display()
            self.sidebar.update_queue_status(0)

    def open_full_cycle_table(self):
        """Open the full cycle data table in the Edits tab."""
        # Find the Edits tab and switch to it
        for i in range(self.sidebar.tabs.count()):
            if self.sidebar.tabs.tabText(i) == "Edits":
                self.sidebar.tabs.setCurrentIndex(i)
                break

    def add_cycle_to_queue(self):
        """Add current cycle form values to the queue."""
        if len(self.cycle_queue) >= self.max_queue_size:
            QMessageBox.warning(self, "Queue Full",
                              f"Maximum queue size ({self.max_queue_size}) reached. Start a cycle to free up space.")
            return

        # Extract values from cycle settings form widgets
        cycle_type = self.sidebar.cycle_type_combo.currentText()
        cycle_length_text = self.sidebar.cycle_length_combo.currentText()
        cycle_notes = self.sidebar.note_input.toPlainText()

        # Parse cycle length (e.g., "5 min" -> 5)
        cycle_minutes = int(cycle_length_text.split()[0])

        cycle_data = {
            "type": cycle_type,
            "start": "00:00:00",  # Will be set when cycle actually starts
            "end": f"00:{cycle_minutes:02d}:00",
            "notes": cycle_notes if cycle_notes else "No notes",
            "state": "queued",
            "length_minutes": cycle_minutes
        }

        self.cycle_queue.append(cycle_data)
        self._update_queue_display()

        # Disable Add to Queue if at capacity
        if len(self.cycle_queue) >= self.max_queue_size:
            self.add_to_queue_btn.setEnabled(False)

    def start_cycle(self):
        """Start next cycle from queue or use current form values."""
        if self.cycle_queue:
            # Consume first queued item
            cycle_data = self.cycle_queue.pop(0)
            cycle_data["state"] = "completed"

            # TODO: Create actual cycle/segment object here
            # For now, just update display
            print(f"Starting cycle: {cycle_data}")

            # Update queue display to show next item as ready
            self._update_queue_display()

            # Re-enable Add to Queue button
            if len(self.cycle_queue) < self.max_queue_size:
                self.add_to_queue_btn.setEnabled(True)
        else:
            # No queue items - use current form values
            # TODO: Extract form values and create cycle
            print("Starting immediate cycle from form values")

    def start_cycle_countdown(self, duration_minutes: int):
        """Start countdown timer for cycle duration.

        Args:
            duration_minutes: Cycle duration in minutes
        """
        import time
        self.cycle_duration_seconds = duration_minutes * 60
        self.cycle_start_time = time.time()
        self.cycle_countdown_timer.start(1000)  # Update every second
        logger.info(f"⏱️ Started countdown timer for {duration_minutes} min cycle")

    def _update_countdown(self):
        """Update countdown timer display based on cycle progress."""
        if self.cycle_start_time is None:
            return

        import time
        elapsed = time.time() - self.cycle_start_time
        remaining = max(0, self.cycle_duration_seconds - elapsed)

        minutes = int(remaining // 60)
        seconds = int(remaining % 60)

        if hasattr(self.sidebar, 'countdown_label'):
            self.sidebar.countdown_label.setText(f"{minutes:02d}:{seconds:02d}")

        # Stop timer when countdown reaches zero
        if remaining <= 0:
            self.cycle_countdown_timer.stop()
            self.cycle_start_time = None

    def start_cycle_countdown(self, duration_minutes: int):
        """Start countdown timer for cycle duration.

        Args:
            duration_minutes: Cycle duration in minutes
        """
        import time
        self.cycle_duration_seconds = duration_minutes * 60
        self.cycle_start_time = time.time()
        self.cycle_countdown_timer.start(1000)  # Update every second
        logger.info(f"⏱️ Started countdown timer for {duration_minutes} min cycle")

    def _update_countdown(self):
        """Update countdown timer display based on cycle progress."""
        if self.cycle_start_time is None:
            return

        import time
        elapsed = time.time() - self.cycle_start_time
        remaining = max(0, self.cycle_duration_seconds - elapsed)

        minutes = int(remaining // 60)
        seconds = int(remaining % 60)

        if hasattr(self.sidebar, 'countdown_label'):
            self.sidebar.countdown_label.setText(f"{minutes:02d}:{seconds:02d}")

        # Stop timer when countdown reaches zero
        if remaining <= 0:
            self.cycle_countdown_timer.stop()
            self.cycle_start_time = None

    def start_cycle_countdown(self, duration_minutes: int):
        """Start countdown timer for cycle duration.

        Args:
            duration_minutes: Cycle duration in minutes
        """
        import time
        self.cycle_duration_seconds = duration_minutes * 60
        self.cycle_start_time = time.time()
        self.cycle_countdown_timer.start(1000)  # Update every second
        logger.info(f"⏱️ Started countdown timer for {duration_minutes} min cycle")

    def _on_export_data(self):
        """Handle export data button click - emit signal with export configuration."""
        export_config = self._get_export_config()
        self.export_requested.emit(export_config)

    def _on_quick_csv_preset(self):
        """Quick CSV export preset - all data, all channels, CSV format."""
        config = self._get_export_config()
        config['preset'] = 'quick_csv'
        config['format'] = 'csv'
        config['include_metadata'] = False
        config['include_events'] = False
        self.export_requested.emit(config)

    def _on_analysis_preset(self):
        """Analysis-ready preset - processed data, summary table, Excel format."""
        config = self._get_export_config()
        config['preset'] = 'analysis'
        config['format'] = 'excel'
        config['data_types'] = {'processed': True, 'summary': True, 'raw': False, 'cycles': False}
        config['include_metadata'] = True
        config['include_events'] = True
        self.export_requested.emit(config)

    def _on_publication_preset(self):
        """Publication preset - high precision, metadata, Excel format."""
        config = self._get_export_config()
        config['preset'] = 'publication'
        config['format'] = 'excel'
        config['precision'] = 5
        config['include_metadata'] = True
        config['include_events'] = True
        self.export_requested.emit(config)

    def _get_export_config(self) -> dict:
        """Extract export configuration from UI controls.

        Returns:
            Dictionary with export settings
        """
        # Get selected data types
        data_types = {
            'raw': getattr(self.sidebar, 'raw_data_check', None) and self.sidebar.raw_data_check.isChecked() if hasattr(self.sidebar, 'raw_data_check') else True,
            'processed': getattr(self.sidebar, 'processed_data_check', None) and self.sidebar.processed_data_check.isChecked() if hasattr(self.sidebar, 'processed_data_check') else True,
            'cycles': getattr(self.sidebar, 'cycle_segments_check', None) and self.sidebar.cycle_segments_check.isChecked() if hasattr(self.sidebar, 'cycle_segments_check') else True,
            'summary': getattr(self.sidebar, 'summary_table_check', None) and self.sidebar.summary_table_check.isChecked() if hasattr(self.sidebar, 'summary_table_check') else True,
        }

        # Get selected channels
        channels = []
        if hasattr(self.sidebar, 'export_channel_checkboxes'):
            channel_names = ['a', 'b', 'c', 'd']
            for i, cb in enumerate(self.sidebar.export_channel_checkboxes):
                if cb.isChecked():
                    channels.append(channel_names[i])
        else:
            channels = ['a', 'b', 'c', 'd']  # Default all channels

        # Get format
        format_type = 'excel'  # Default
        if hasattr(self.sidebar, 'excel_radio') and self.sidebar.excel_radio.isChecked():
            format_type = 'excel'
        elif hasattr(self.sidebar, 'csv_radio') and self.sidebar.csv_radio.isChecked():
            format_type = 'csv'
        elif hasattr(self.sidebar, 'json_radio') and self.sidebar.json_radio.isChecked():
            format_type = 'json'
        elif hasattr(self.sidebar, 'hdf5_radio') and self.sidebar.hdf5_radio.isChecked():
            format_type = 'hdf5'

        # Get options
        include_metadata = getattr(self.sidebar, 'metadata_check', None) and self.sidebar.metadata_check.isChecked() if hasattr(self.sidebar, 'metadata_check') else True
        include_events = getattr(self.sidebar, 'events_check', None) and self.sidebar.events_check.isChecked() if hasattr(self.sidebar, 'events_check') else False

        # Get precision
        precision = 4  # Default
        if hasattr(self.sidebar, 'precision_combo'):
            precision = int(self.sidebar.precision_combo.currentText())

        # Get timestamp format
        timestamp_format = 'relative'  # Default
        if hasattr(self.sidebar, 'timestamp_combo'):
            timestamp_text = self.sidebar.timestamp_combo.currentText()
            if 'Absolute' in timestamp_text:
                timestamp_format = 'absolute'
            elif 'seconds' in timestamp_text:
                timestamp_format = 'elapsed'

        # Get filename and destination
        filename = getattr(self.sidebar, 'export_filename_input', None) and self.sidebar.export_filename_input.text() if hasattr(self.sidebar, 'export_filename_input') else ''
        destination = getattr(self.sidebar, 'export_dest_input', None) and self.sidebar.export_dest_input.text() if hasattr(self.sidebar, 'export_dest_input') else ''

        return {
            'data_types': data_types,
            'channels': channels,
            'format': format_type,
            'include_metadata': include_metadata,
            'include_events': include_events,
            'precision': precision,
            'timestamp_format': timestamp_format,
            'filename': filename,
            'destination': destination,
            'preset': None  # Will be set by preset buttons
        }

    def _refresh_intelligence_bar(self):
        """Refresh the Intelligence Bar display with current system diagnostics."""
        try:
            # Get system intelligence instance and run diagnosis
            intelligence = get_system_intelligence()
            system_state, active_issues = intelligence.diagnose_system()

            # Update status based on system state
            if system_state == SystemState.HEALTHY:
                status_text = "✓ Good"
                status_color = "#34C759"  # Green
                message_text = "→ System Ready"
                message_color = "#007AFF"  # Blue
            elif system_state == SystemState.DEGRADED:
                status_text = "⚠ Degraded"
                status_color = "#FF9500"  # Orange
                # Show most critical issue
                if active_issues:
                    message_text = f"→ {active_issues[0].title}"
                else:
                    message_text = "→ Performance degraded"
                message_color = "#FF9500"
            elif system_state == SystemState.WARNING:
                status_text = "⚠ Warning"
                status_color = "#FF9500"  # Orange
                if active_issues:
                    message_text = f"→ {active_issues[0].title}"
                else:
                    message_text = "→ Attention required"
                message_color = "#FF9500"
            elif system_state == SystemState.ERROR:
                status_text = "❌ Error"
                status_color = "#FF3B30"  # Red
                if active_issues:
                    message_text = f"→ {active_issues[0].title}"
                else:
                    message_text = "→ System error detected"
                message_color = "#FF3B30"
            else:  # UNKNOWN
                status_text = "? Unknown"
                status_color = "#86868B"  # Gray
                message_text = "→ Initializing..."
                message_color = "#86868B"

            # Update the UI labels
            self.sidebar.intel_status_label.setText(status_text)
            self.sidebar.intel_status_label.setStyleSheet(
                f"font-size: 12px;"
                f"color: {status_color};"
                f"background: transparent;"
                f"font-weight: 700;"
                f"font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )

            self.sidebar.intel_message_label.setText(message_text)
            self.sidebar.intel_message_label.setStyleSheet(
                f"font-size: 12px;"
                f"color: {message_color};"
                f"background: transparent;"
                f"font-weight: 600;"
                f"font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )

        except Exception as e:
            logger.error(f"Error refreshing intelligence bar: {e}")

    def _update_queue_display(self):
        """Update the summary table to reflect current queue state."""
        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtGui import QColor

        # Clear table
        for row in range(5):
            for col in range(4):
                self.summary_table.setItem(row, col, QTableWidgetItem(""))
                self.summary_table.item(row, col).setBackground(QColor(255, 255, 255))

        # Populate with queue data
        for row, cycle in enumerate(self.cycle_queue[:5]):
            state = cycle["state"]

            # State indicator with emoji
            state_text = ""
            state_color = QColor(255, 255, 255)

            if state == "queued":
                if row == 0:
                    # First item is ready to start
                    state_text = "▶️ Ready"
                    state_color = QColor(227, 242, 253)  # Light blue
                else:
                    state_text = "🟡 Queued"
                    state_color = QColor(245, 245, 245)  # Light gray
            elif state == "completed":
                state_text = "✓ Done"
                state_color = QColor(232, 245, 233)  # Light green

            # Set cell values
            state_item = QTableWidgetItem(state_text)
            state_item.setBackground(state_color)
            self.summary_table.setItem(row, 0, state_item)

            self.summary_table.setItem(row, 1, QTableWidgetItem(cycle["type"]))
            self.summary_table.setItem(row, 2, QTableWidgetItem(cycle["start"]))
            self.summary_table.setItem(row, 3, QTableWidgetItem(cycle["notes"]))

            # Apply background color to entire row
            for col in range(1, 4):
                self.summary_table.item(row, col).setBackground(state_color)

    def _on_unit_changed(self, checked: bool):
        """Toggle between RU and nm units."""
        # This will be connected to main_simplified handler
        if checked and self.ru_btn.isChecked():
            logger.info("Unit changed to RU")
        elif checked and self.nm_btn.isChecked():
            logger.info("Unit changed to nm")

    def _load_current_settings(self):
        """Load current hardware settings from device config into UI."""
        try:
            if self.device_config:
                # Load servo positions
                s_pos, p_pos = self.device_config.get_servo_positions()

                # Load LED intensities
                led_intensities = self.device_config.get_led_intensities()

                # Populate UI fields
                self.sidebar.load_hardware_settings(
                    s_pos=s_pos,
                    p_pos=p_pos,
                    led_a=led_intensities.get('a', 0),
                    led_b=led_intensities.get('b', 0),
                    led_c=led_intensities.get('c', 0),
                    led_d=led_intensities.get('d', 0)
                )

                logger.info(f"Loaded current settings: S={s_pos}, P={p_pos}, LEDs={led_intensities}")

                # Initialize pipeline selector to current configuration
                self._init_pipeline_selector()
            else:
                logger.warning("Device config not available - cannot load current settings")
                QMessageBox.warning(
                    self,
                    "Settings Not Available",
                    "Device configuration is not available. Please connect to hardware first."
                )
        except Exception as e:
            logger.error(f"Error loading current settings: {e}")
            QMessageBox.critical(
                self,
                "Error Loading Settings",
                f"Failed to load current settings: {str(e)}"
            )

    def eventFilter(self, obj, event):
        """Event filter to detect Control+10-click on advanced settings button."""
        if obj == self.sidebar.advanced_settings_btn and event.type() == QEvent.Type.MouseButtonPress:
            # Check if Control key is held
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.advanced_params_click_count += 1

                # Reset click count after 2 seconds of inactivity
                self.click_reset_timer.start(2000)

                if self.advanced_params_click_count >= 10:
                    self._unlock_advanced_params()
                    self.advanced_params_click_count = 0
                    return True  # Consume the event

        return super().eventFilter(obj, event)

    def _reset_click_count(self):
        """Reset the click counter after inactivity."""
        self.advanced_params_click_count = 0

    def _unlock_advanced_params(self):
        """Unlock advanced parameters and enable dev mode for 60 minutes."""
        import os

        self.advanced_params_unlocked = True

        # Enable dev mode environment variable
        os.environ['AFFILABS_DEV'] = '1'

        # Show confirmation message
        QMessageBox.information(
            self,
            "Advanced Parameters Unlocked",
            "Advanced parameters tab and developer mode are now enabled for 60 minutes."
        )

        # Set timer to lock after 60 minutes
        if self.advanced_params_timer is None:
            self.advanced_params_timer = QTimer()
            self.advanced_params_timer.setSingleShot(True)
            self.advanced_params_timer.timeout.connect(self._lock_advanced_params)

        self.advanced_params_timer.start(60 * 60 * 1000)  # 60 minutes in milliseconds

        logger.info("Advanced parameters and dev mode unlocked for 60 minutes")

    def _lock_advanced_params(self):
        """Lock advanced parameters and disable dev mode after timeout."""
        import os

        self.advanced_params_unlocked = False

        # Disable dev mode environment variable
        if 'AFFILABS_DEV' in os.environ:
            del os.environ['AFFILABS_DEV']

        logger.info("Advanced parameters and dev mode locked after timeout")

    def open_advanced_settings(self):
        """Open the advanced settings dialog."""
        try:
            dialog = AdvancedSettingsDialog(self, unlocked=getattr(self, 'advanced_params_unlocked', False))
        except Exception as e:
            logger.error(f"Failed to create AdvancedSettingsDialog: {e}")
            return

        # Load current settings
        if hasattr(dialog, 'ru_btn'):
            dialog.ru_btn.setChecked(self.ru_btn.isChecked() if hasattr(self, 'ru_btn') else True)
        if hasattr(dialog, 'nm_btn'):
            dialog.nm_btn.setChecked(self.nm_btn.isChecked() if hasattr(self, 'nm_btn') else False)

        # Load LED delays from settings
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from settings import settings
            pre_led_delay = settings.PRE_LED_DELAY_MS
            post_led_delay = settings.POST_LED_DELAY_MS
            if hasattr(dialog, 'led_delay_input'):
                dialog.led_delay_input.setValue(int(pre_led_delay))
            if hasattr(dialog, 'post_led_delay_input'):
                dialog.post_led_delay_input.setValue(int(post_led_delay))
        except Exception as e:
            logger.warning(f"Could not load LED delays, using defaults: {e}")
            if hasattr(dialog, 'led_delay_input'):
                dialog.led_delay_input.setValue(45)  # Default PRE LED
            if hasattr(dialog, 'post_led_delay_input'):
                dialog.post_led_delay_input.setValue(5)  # Default POST LED

        # Show dialog
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Apply settings
            if hasattr(self, 'ru_btn'):
                self.ru_btn.setChecked(dialog.ru_btn.isChecked())
                self.nm_btn.setChecked(dialog.nm_btn.isChecked())

            logger.info("Advanced settings applied")

    def _apply_settings(self):
        """Apply polarizer and LED settings from the Settings tab."""
        try:
            # Get polarizer positions
            s_pos = self.s_position_input.text()
            p_pos = self.p_position_input.text()

            # Get LED intensities
            led_a = self.channel_a_input.text()
            led_b = self.channel_b_input.text()
            led_c = self.channel_c_input.text()
            led_d = self.channel_d_input.text()

            # Validate inputs
            values = []
            for val in [s_pos, p_pos, led_a, led_b, led_c, led_d]:
                if val:
                    try:
                        num = int(val)
                        if not (0 <= num <= 255):
                            raise ValueError("Value must be between 0 and 255")
                        values.append(num)
                    except ValueError as e:
                        QMessageBox.warning(self, "Invalid Input",
                                          f"Please enter valid numbers (0-255): {e}")
                        return

            # TODO: Actually apply these settings to hardware
            logger.info(f"Applying settings - S:{s_pos}, P:{p_pos}, LEDs:[{led_a},{led_b},{led_c},{led_d}]")
            QMessageBox.information(self, "Settings Applied",
                                   "Settings have been applied successfully.")

        except Exception as e:
            logger.error(f"Failed to apply settings: {e}")
            QMessageBox.warning(self, "Error", f"Failed to apply settings: {e}")

    def _handle_simple_led_calibration(self) -> None:
        """Handle Simple LED Calibration button click."""
        logger.info("Simple LED Calibration button clicked")
        # Emit signal to trigger calibration via application
        if hasattr(self, 'app') and self.app:
            self.app.calibration.start_calibration()
        else:
            logger.warning("Application not connected - cannot start calibration")

    def _handle_full_calibration(self) -> None:
        """Handle Full Calibration button click."""
        logger.info("Full Calibration button clicked")
        # Emit signal to trigger full calibration via application
        if hasattr(self, 'app') and self.app:
            self.app.calibration.start_calibration()
        else:
            logger.warning("Application not connected - cannot start calibration")

    def _handle_oem_led_calibration(self) -> None:
        """Handle OEM LED Calibration button click."""
        logger.info("OEM LED Calibration button clicked")
        # Emit signal to trigger OEM calibration via application
        if hasattr(self, 'app') and self.app:
            self.app.calibration.start_calibration(mode='oem')
        else:
            logger.warning("Application not connected - cannot start calibration")

    def _connect_signals(self) -> None:
        """Connect UI signals."""
        self.sidebar.scan_btn.clicked.connect(self._handle_scan_hardware)
        self.sidebar.debug_log_btn.clicked.connect(self._handle_debug_log_download)

        # Connect keyboard shortcuts
        from PySide6.QtGui import QShortcut, QKeySequence
        power_shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        power_shortcut.activated.connect(self._handle_power_click)

        # Demo data loader (Ctrl+Shift+D) for promotional screenshots
        demo_data_shortcut = QShortcut(QKeySequence("Ctrl+Shift+D"), self)
        demo_data_shortcut.activated.connect(self._load_demo_data)

        # Connect cycle management buttons
        self.sidebar.start_cycle_btn.clicked.connect(self.start_cycle)
        self.sidebar.add_to_queue_btn.clicked.connect(self.add_cycle_to_queue)
        self.sidebar.start_run_btn.clicked.connect(self._on_start_queued_run)
        self.sidebar.clear_queue_btn.clicked.connect(self._on_clear_queue)
        self.sidebar.open_table_btn.clicked.connect(self.open_full_cycle_table)

        # Connect export buttons
        self.sidebar.export_data_btn.clicked.connect(self._on_export_data)
        self.sidebar.quick_csv_btn.clicked.connect(self._on_quick_csv_preset)
        self.sidebar.analysis_btn.clicked.connect(self._on_analysis_preset)
        self.sidebar.publication_btn.clicked.connect(self._on_publication_preset)

        # Connect settings tab controls
        self.sidebar.advanced_settings_btn.clicked.connect(self.open_advanced_settings)
        self.sidebar.load_current_settings_btn.clicked.connect(self._load_current_settings)
        self.sidebar.apply_settings_btn.clicked.connect(self._apply_settings)
        self.sidebar.spectrum_btn.clicked.connect(self._show_transmission_spectrum)

        # Connect pipeline selector
        if hasattr(self.sidebar, 'pipeline_selector'):
            self.sidebar.pipeline_selector.currentIndexChanged.connect(self._on_pipeline_changed)
            # Update description on change
            self.sidebar.pipeline_selector.currentIndexChanged.connect(self._update_pipeline_description)
            # Initialize to current configuration
            self._init_pipeline_selector()

        # Install event filter for Control+10-click detection on advanced settings button
        self.sidebar.advanced_settings_btn.installEventFilter(self)

        # Connect calibration buttons
        self.simple_led_calibration_btn.clicked.connect(self._handle_simple_led_calibration)
        self.full_calibration_btn.clicked.connect(self._handle_full_calibration)
        self.oem_led_calibration_btn.clicked.connect(self._handle_oem_led_calibration)

        # Install element inspector for right-click inspection
        ElementInspector.install_inspector(self)

    def _load_demo_data(self):
        """Load demo SPR kinetics data for promotional screenshots.

        Keyboard shortcut: Ctrl+Shift+D
        Generates realistic binding curves with association/dissociation phases.
        """
        try:
            from utils.demo_data_generator import generate_demo_cycle_data

            # Generate 3 cycles of demo data with increasing responses
            time_array, channel_data, cycle_boundaries = generate_demo_cycle_data(
                num_cycles=3,
                cycle_duration=600,
                sampling_rate=2.0,
                responses=[20, 40, 65],  # Progressive concentration series
                seed=42,
            )

            # Check if app instance is available (it should be set by main_simplified)
            if not hasattr(self, 'app') or self.app is None:
                print("⚠️  Demo data: No app instance available")
                print("   Demo data can only be loaded when running through main_simplified.py")
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self,
                    "Demo Data Unavailable",
                    "Demo data can only be loaded when the application is fully initialized.\n\n"
                    "Please ensure you're running through main_simplified.py"
                )
                return

            # Access the data manager through the app instance
            data_mgr = self.app.data_mgr

            # Load demo data into buffers using the proper buffer update mechanism
            # The data manager will handle converting to the right format
            for i, time_point in enumerate(time_array):
                # Update time buffer
                if i == 0:
                    # Initialize
                    data_mgr.time_buffer = []
                    data_mgr.wavelength_buffer_a = []
                    data_mgr.wavelength_buffer_b = []
                    data_mgr.wavelength_buffer_c = []
                    data_mgr.wavelength_buffer_d = []

                data_mgr.time_buffer.append(time_point)
                data_mgr.wavelength_buffer_a.append(channel_data['a'][i])
                data_mgr.wavelength_buffer_b.append(channel_data['b'][i])
                data_mgr.wavelength_buffer_c.append(channel_data['c'][i])
                data_mgr.wavelength_buffer_d.append(channel_data['d'][i])

            # Now update the timeline data in buffer manager
            import numpy as np
            for ch in ['a', 'b', 'c', 'd']:
                if hasattr(self.app, 'buffer_mgr') and hasattr(self.app.buffer_mgr, 'timeline_data'):
                    self.app.buffer_mgr.timeline_data[ch].time = np.array(time_array)
                    self.app.buffer_mgr.timeline_data[ch].wavelength = np.array(channel_data[ch])

            # Trigger graph updates for both full timeline and cycle of interest
            # Update full timeline graph
            if hasattr(self, 'full_timeline_graph'):
                for ch_idx, ch in enumerate(['a', 'b', 'c', 'd']):
                    if ch_idx < len(self.full_timeline_graph.curves):
                        curve = self.full_timeline_graph.curves[ch_idx]
                        curve.setData(time_array, channel_data[ch])

            # Update cycle of interest graph
            if hasattr(self.app, '_update_cycle_of_interest_graph'):
                self.app._update_cycle_of_interest_graph()

            print(f"✅ Demo data loaded: {len(time_array)} points, {len(cycle_boundaries)} cycles")
            print("   Use this view for promotional screenshots")

            # Show confirmation message
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "Demo Data Loaded",
                f"Loaded {len(cycle_boundaries)} cycles of demo SPR kinetics data.\n\n"
                "The sensorgram now shows realistic binding curves for promotional use.\n"
                f"Total duration: {time_array[-1]:.0f} seconds\n"
                f"Data points: {len(time_array)}\n\n"
                "Tip: Navigate to different views to capture various screenshots."
            )

        except ImportError as e:
            print(f"❌ Error importing demo data generator: {e}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Import Error",
                f"Could not import demo data generator:\n{e}"
            )
        except Exception as e:
            print(f"❌ Error loading demo data: {e}")
            import traceback
            traceback.print_exc()
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Error Loading Demo Data",
                f"An error occurred while loading demo data:\n\n{str(e)}\n\n"
                "Please check the console for details."
            )


# Main entry point
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindowPrototype()
    window.show()
    sys.exit(app.exec())


