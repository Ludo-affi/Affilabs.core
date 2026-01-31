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
from pathlib import Path

from PySide6.QtCore import (
    QEvent,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QTabWidget,
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
from affilabs.inspector import ElementInspector
from affilabs.plot_helpers import add_channel_curves, create_time_plot
from affilabs.tabs.edits_tab import EditsTab  # Extracted tab content
from affilabs.ui_styles import (
    Colors,
    Fonts,
    Dimensions,
    create_card_shadow,
    segmented_button_style,
    spinbox_style,
    label_style,
    title_style,
    divider_style,
    group_box_style,
)
from affilabs.utils.logger import logger


class StartupCalibProgressDialog(QDialog):
    """Non-modal progress dialog for calibration with Start button integration."""

    start_clicked = Signal()  # Signal emitted when Start button is clicked
    retry_clicked = Signal()  # Signal emitted when Retry button is clicked
    continue_anyway_clicked = Signal()  # Signal emitted when Continue Anyway is clicked

    # Internal signals for thread-safe UI updates
    _update_title_signal = Signal(str)
    _update_status_signal = Signal(str)
    _set_progress_signal = Signal(int, int)  # (value, maximum)
    _hide_progress_signal = Signal()
    _enable_start_signal = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        title: str = "Processing",
        message: str = "Please wait...",
        show_start_button: bool = False,
    ) -> None:
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
            "QDialog { background: {Colors.BACKGROUND_WHITE}; border: 2px solid #007AFF; border-radius: {Dimensions.BORDER_RADIUS_LG}; }"
            "QLabel { font-family: {Fonts.SYSTEM}; color: {Colors.PRIMARY_TEXT}; }",
        )

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(20)

        # Title
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            "font-size: 18px;font-weight: {Fonts.WEIGHT_BOLD};color: {Colors.PRIMARY_TEXT};",
        )
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.title_label)

        # Progress bar (can be indeterminate or real progress)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)  # Start in indeterminate mode
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(Dimensions.HEIGHT_BUTTON_SM)
        self.progress_bar.setVisible(False)  # Hidden initially for checklist
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setStyleSheet(
            "QProgressBar {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  border-radius: 4px;"
            "  border: 1px solid #D1D1D6;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  font-size: 12px;"
            "  font-weight: {Fonts.WEIGHT_BOLD};"
            "  text-align: center;"
            "}"
            "QProgressBar::chunk {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007AFF, stop:1 #00C7BE);"
            "  border-radius: 4px;"
            "}",
        )
        main_layout.addWidget(self.progress_bar)

        # Status message
        self.status_label = QLabel(message)
        self.status_label.setStyleSheet(
            "font-size: 14px;color: {Colors.SECONDARY_TEXT};padding: 0px;",
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
                "  color: {Colors.SECONDARY_TEXT};"
                "}",
            )
            self.start_button.clicked.connect(self._on_start_clicked)
            self.button_layout.addWidget(self.start_button)

        self.button_layout.addStretch()
        main_layout.addWidget(self.button_container)

        # Connect internal signals for thread-safe UI updates
        self._update_title_signal.connect(self._do_update_title)
        self._update_status_signal.connect(self._do_update_status)
        self._set_progress_signal.connect(self._do_set_progress)
        self._hide_progress_signal.connect(self._do_hide_progress)
        self._enable_start_signal.connect(self._do_enable_start)

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
                    from affilabs.utils.logger import logger

                    logger.info(
                        "📋 Dialog Start button clicked (post-calibration) - emitting signal",
                    )
                    self.start_clicked.emit()
                    logger.info(
                        "📋 Signal emitted, dialog will close after acquisition starts",
                    )
                    # Don't close immediately - let coordinator close it after acquisition starts
                    # self._is_closing = True
                    # self.close()
                else:
                    # Pre-calibration: Emit signal but keep dialog open for progress updates
                    self.start_clicked.emit()
                    # Dialog stays open to show calibration progress
        except Exception as e:
            from affilabs.utils.logger import logger

            logger.error(f"❌ Error in _on_start_clicked: {e}", exc_info=True)
            import traceback

            try:
                print(traceback.format_exc())
            except:
                pass

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
        """Update the status message (thread-safe via signal)."""
        self._update_status_signal.emit(message)

    def _do_update_status(self, message: str) -> None:
        """Actually update status label (runs in main thread)."""
        if not self._is_closing and self.isVisible():
            try:
                self.status_label.setText(message)
            except RuntimeError as e:
                logger.error(f"RuntimeError in _do_update_status: {e}")
            except Exception as e:
                logger.error(f"Exception in _do_update_status: {e}")
                import traceback

                try:
                    print(traceback.format_exc())
                except:
                    pass

    def update_title(self, title: str):
        """Update the title (thread-safe via signal)."""
        self._update_title_signal.emit(title)

    def _do_update_title(self, title: str) -> None:
        """Actually update title (runs in main thread)."""
        if not self._is_closing and self.isVisible():
            try:
                self.title_label.setText(title)
                self.setWindowTitle(title)
            except RuntimeError as e:
                logger.error(f"RuntimeError in _do_update_title: {e}")
            except Exception as e:
                logger.error(f"Exception in _do_update_title: {e}")
                import traceback

                try:
                    print(traceback.format_exc())
                except:
                    pass

    def set_progress(self, value: int, maximum: int = 100):
        """Set progress bar to show actual progress (thread-safe).

        Args:
            value: Current progress value
            maximum: Maximum progress value (default 100)

        """
        self._set_progress_signal.emit(value, maximum)

    def _do_set_progress(self, value: int, maximum: int) -> None:
        """Actually set progress (runs in main thread).

        Args:
            value: Current progress value
            maximum: Maximum progress value

        """
        if not self._is_closing and self.isVisible():
            try:
                # Always ensure progress bar is in determinate mode with correct maximum
                if self.progress_bar.maximum() != maximum:
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
        """Hide progress bar (thread-safe via signal)."""
        self._hide_progress_signal.emit()

    def _do_hide_progress(self) -> None:
        """Actually hide progress bar (runs in main thread)."""
        if not self._is_closing and self.isVisible():
            try:
                self.progress_bar.hide()
            except RuntimeError as e:
                logger.error(f"RuntimeError in _do_hide_progress: {e}")
            except Exception as e:
                logger.error(f"Exception in _do_hide_progress: {e}")
                import traceback

                try:
                    print(traceback.format_exc())
                except:
                    pass

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
        from affilabs.utils.logger import logger

        logger.debug(
            f"🔧 enable_start_button_pre_calib() called: _is_complete={self._is_complete}",
        )
        if not self._is_closing and self.isVisible() and self.start_button:
            try:
                self._is_error_state = False
                self.start_button.setEnabled(True)
                logger.debug(
                    f"   ✅ Button enabled, _is_complete={self._is_complete} (should be False)",
                )
            except RuntimeError:
                pass  # Widget deleted

    def enable_start_button(self) -> None:
        """Enable the Start button when calibration is complete (thread-safe via signal)."""
        self._enable_start_signal.emit()

    def _do_enable_start(self) -> None:
        """Actually enable start button (runs in main thread)."""
        if not self._is_closing and self.isVisible() and self.start_button:
            try:
                self._is_complete = True
                self._is_error_state = False
                self.start_button.setEnabled(True)
            except RuntimeError as e:
                logger.error(f"RuntimeError in _do_enable_start: {e}")
            except Exception as e:
                logger.error(f"Exception in _do_enable_start: {e}")
                import traceback

                try:
                    print(traceback.format_exc())
                except:
                    pass

    def show_error_state(
        self,
        error_message: str,
        retry_count: int,
        max_retries: int,
    ) -> None:
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
                "font-weight: {Fonts.WEIGHT_BOLD};"
                "color: #FF3B30;",  # Red color for error
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
                    "}",
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
                    "}",
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
            self.status_label.setText(
                f"{error_message}\n\nMaximum retry attempts reached.\nPlease contact technical support.",
            )

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
                    "}",
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
                "font-size: 18px;font-weight: {Fonts.WEIGHT_BOLD};color: {Colors.PRIMARY_TEXT};",
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

    def __init__(
        self,
        parent: QWidget | None = None,
        device_serial: str | None = None,
        controller_type: str = "",
        controller=None,
        device_config=None,
    ) -> None:
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
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border: 2px solid #007AFF;"
            "  border-radius: {Dimensions.BORDER_RADIUS_LG};"
            "}"
            "QLabel {"
            "  color: {Colors.PRIMARY_TEXT};"
            "  font-size: 13px;"
            "}",
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Title
        title = QLabel("⚙️ Device Configuration")
        title.setStyleSheet(
            "font-size: 20px;font-weight: 600;color: {Colors.PRIMARY_TEXT};",
        )
        layout.addWidget(title)

        # Description
        desc = QLabel(
            f"Please provide the following information for device:\n<b>{device_serial or 'Unknown'}</b>",
        )
        desc.setTextFormat(Qt.TextFormat.RichText)  # Enable HTML formatting
        desc.setStyleSheet(
            "font-size: 13px;color: {Colors.SECONDARY_TEXT};",
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Config source indicator (EEPROM vs JSON)
        self.config_source_label = QLabel()
        self.config_source_label.setStyleSheet(
            "font-size: 12px;"
            "color: {Colors.SECONDARY_TEXT};"
            "padding: 8px 12px;"
            "background: #F5F5F7;"
            "border-radius: 6px;",
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
            "  background: {Colors.BACKGROUND_WHITE};"
            "  font-size: 13px;"
            "  color: {Colors.PRIMARY_TEXT};"
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
            "  color: {Colors.SECONDARY_TEXT};"
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
            "  background: {Colors.BACKGROUND_WHITE};"
            "  selection-background-color: #007AFF;"
            "  selection-color: #FFFFFF;"
            "  padding: 4px;"
            "  outline: none;"
            "}"
            "QComboBox QAbstractItemView::item {"
            "  padding: 8px 12px;"
            "  border-radius: 4px;"
            "  color: {Colors.PRIMARY_TEXT};"
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
            "  background: {Colors.BACKGROUND_WHITE};"
            "  font-size: 13px;"
            "}"
            "QLineEdit:focus {"
            "  border: 2px solid #007AFF;"
            "}"
        )

        # LED Model (LCW or OWW)
        self.led_model_combo = QComboBox()
        self.led_model_combo.addItems(["LCW", "OWW"])
        self.led_model_combo.setStyleSheet(combo_style)
        form.addRow("LED Model:", self.led_model_combo)

        # Controller Options (hardware types excluding pumps)
        self.controller_combo = QComboBox()
        self.controller_combo.addItems(["Arduino", "PicoP4SPR", "PicoEZSPR"])
        self.controller_combo.setStyleSheet(combo_style)

        # Pre-select based on detected controller type
        if self.controller_type in ["Arduino", "PicoP4SPR", "PicoEZSPR"]:
            index = self.controller_combo.findText(self.controller_type)
            if index >= 0:
                self.controller_combo.setCurrentIndex(index)

        # Connect change to update polarizer
        self.controller_combo.currentTextChanged.connect(self._on_controller_changed)
        form.addRow("Controller:", self.controller_combo)

        # Fiber Diameter (A=100, B=200)
        self.fiber_diameter_combo = QComboBox()
        self.fiber_diameter_combo.addItems(["A (100 µm)", "B (200 µm)"])
        self.fiber_diameter_combo.setStyleSheet(combo_style)
        form.addRow("Fiber Diameter:", self.fiber_diameter_combo)

        # Polarizer Type (barrel or circle, default circle for Arduino/PicoP4SPR)
        self.polarizer_type_combo = QComboBox()
        self.polarizer_type_combo.addItems(["circle", "barrel"])
        self.polarizer_type_combo.setStyleSheet(combo_style)

        # Set default based on controller
        self._update_polarizer_default()

        form.addRow("Polarizer:", self.polarizer_type_combo)

        # Device ID (detector serial number)
        self.device_id_input = QLineEdit()
        self.device_id_input.setPlaceholderText("Enter detector serial number")
        self.device_id_input.setText(
            device_serial or "",
        )  # Pre-fill with detected serial
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
            "  color: {Colors.PRIMARY_TEXT};"
            "}"
            "QPushButton:hover {"
            "  background: #E5E5E7;"
            "}",
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
                "  color: {Colors.SECONDARY_TEXT};"
                "}",
            )
            eeprom_btn.setToolTip(
                "Save configuration to device EEPROM for portable backup",
            )
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
            "}",
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
        if self.controller_type in ["Arduino", "PicoP4SPR"]:
            self.polarizer_type_combo.setCurrentText("circle")
        elif self.controller_type == "PicoEZSPR":
            self.polarizer_type_combo.setCurrentText("barrel")

    def _update_config_source_indicator(self):
        """Update the config source indicator label."""
        if self.device_config is None:
            self.config_source_label.setText("ℹ️ New configuration")
            return

        if (
            hasattr(self.device_config, "loaded_from_eeprom")
            and self.device_config.loaded_from_eeprom
        ):
            self.config_source_label.setText("📦 Configuration loaded from EEPROM")
            self.config_source_label.setStyleSheet(
                "font-size: 12px;"
                "color: #FF9500;"
                "padding: 8px 12px;"
                "background: #FFF3E0;"
                "border-radius: 6px;",
            )
        else:
            self.config_source_label.setText("💾 Configuration loaded from JSON file")
            self.config_source_label.setStyleSheet(
                "font-size: 12px;"
                "color: #34C759;"
                "padding: 8px 12px;"
                "background: #E8F5E9;"
                "border-radius: 6px;",
            )

    def _on_push_to_eeprom(self):
        """Push current form configuration to EEPROM."""
        if self.controller is None:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                "No Controller",
                "Cannot push to EEPROM: No controller connected.",
            )
            return

        # Update device_config with current form values (if it exists)
        if self.device_config is not None:
            config_data = self.get_config_data()
            self.device_config.set_hardware_config(
                led_pcb_model=config_data["led_pcb_model"],
                optical_fiber_diameter_um=config_data["optical_fiber_diameter_um"],
                polarizer_type=config_data["polarizer_type"],
            )

        # Sync to EEPROM
        from affilabs.utils.logger import logger

        logger.info("Pushing configuration to EEPROM...")

        if self.device_config is not None:
            success = self.device_config.sync_to_eeprom(self.controller)
        else:
            # No device_config yet - create temporary EEPROM config from form
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                "Save First",
                "Please save the configuration to JSON first, then push to EEPROM.",
            )
            return

        # Show result
        from PySide6.QtWidgets import QMessageBox

        if success:
            QMessageBox.information(
                self,
                "EEPROM Sync Complete",
                "✓ Configuration successfully pushed to device EEPROM.\n\n"
                "The device can now be used on other computers without reconfiguration.",
            )
            logger.info("✓ EEPROM sync successful")
        else:
            QMessageBox.warning(
                self,
                "EEPROM Sync Failed",
                "Failed to push configuration to EEPROM.\n\n"
                "Check the logs for details.",
            )
            logger.error("✗ EEPROM sync failed")

    def get_config_data(self):
        """Get the configuration data from the form."""
        # Map LED model abbreviations to full names
        led_model_map = {
            "LCW": "luminus_cool_white",
            "OWW": "osram_warm_white",
        }

        # Extract fiber diameter from selection (e.g., "A (100 µm)" -> 100)
        fiber_text = self.fiber_diameter_combo.currentText()
        if "A" in fiber_text:
            fiber_diameter = 100
        elif "B" in fiber_text:
            fiber_diameter = 200
        else:
            fiber_diameter = 200  # Default

        # Get controller type
        controller_type = self.controller_combo.currentText()

        # Determine controller model name from type
        controller_model = "Raspberry Pi Pico P4SPR"  # Default
        if controller_type == "Arduino":
            controller_model = "Arduino P4SPR"
        elif controller_type == "PicoP4SPR":
            controller_model = "Raspberry Pi Pico P4SPR"
        elif controller_type == "PicoEZSPR":
            controller_model = "Raspberry Pi Pico EZSPR"

        return {
            "led_pcb_model": led_model_map.get(
                self.led_model_combo.currentText(),
                "luminus_cool_white",
            ),
            "optical_fiber_diameter_um": fiber_diameter,
            "polarizer_type": self.polarizer_type_combo.currentText(),
            "device_id": self.device_id_input.text().strip() or None,
            "controller_model": controller_model,
            "controller_type": controller_type,
        }


class AffilabsMainWindow(QMainWindow):
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
        # Set window icon using relative path from affilabs module
        from pathlib import Path

        icon_path = Path(__file__).parent / "ui" / "img" / "affinite2.ico"
        if icon_path.exists():
            icon = QIcon(str(icon_path))
            if not icon.isNull():
                self.setWindowIcon(icon)
                logger.debug(f"Window icon loaded successfully: {icon_path}")
            else:
                logger.warning(f"Failed to create icon from file: {icon_path}")
        else:
            logger.warning(f"Icon file not found: {icon_path}")
        self.setGeometry(100, 100, 1400, 900)
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
        self.sidebar.setMinimumWidth(55)  # Allow window to resize very small
        self.sidebar.setMaximumWidth(900)  # Maximum width for sidebar
        # Give sidebar reference to device_config for S/P position syncing
        self.sidebar.device_config = self.device_config
        # Give sidebar reference to app for accessing _completed_cycles
        # Note: Will be set by Application.__init__ after main_window creation
        self.sidebar.app = None
        self.splitter.addWidget(self.sidebar)
        self.splitter.setCollapsible(0, False)  # Prevent sidebar from collapsing

        # Forward sidebar control references to main window for easy access
        # Graphic display controls hidden per user request:
        # self.grid_check = self.sidebar.grid_check
        # self.autoscale_check = self.sidebar.autoscale_check
        # self.min_input = self.sidebar.min_input
        # self.max_input = self.sidebar.max_input
        # self.x_axis_btn = self.sidebar.x_axis_btn
        # self.y_axis_btn = self.sidebar.y_axis_btn
        self.colorblind_check = self.sidebar.colorblind_check
        self.ref_combo = self.sidebar.ref_combo
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

        # Connect colorblind mode signal to update button colors
        if hasattr(self.sidebar, 'colorblind_mode_signal'):
            self.sidebar.colorblind_mode_signal.connect(self._on_colorblind_mode_changed)

        # Forward spectroscopy plots (if they exist)
        logger.debug("Checking for transmission_plot in sidebar...")

        if hasattr(self.sidebar, "transmission_plot"):
            self.transmission_plot = self.sidebar.transmission_plot
            self.transmission_curves = self.sidebar.transmission_curves
            logger.debug(
                f"✓ Forwarded transmission plot ({len(self.transmission_curves)} curves)",
            )
        else:
            logger.warning(
                "⚠️ transmission_plot NOT found in sidebar - plots will not work",
            )

        if hasattr(self.sidebar, "raw_data_plot"):
            self.raw_data_plot = self.sidebar.raw_data_plot
            self.raw_data_curves = self.sidebar.raw_data_curves
            logger.debug(
                f"✓ Forwarded raw plot ({len(self.raw_data_curves)} curves)",
            )
        else:
            logger.warning("⚠️ raw_data_plot NOT found in sidebar - plots will not work")

        # Forward calibration buttons
        self.simple_led_calibration_btn = self.sidebar.simple_led_calibration_btn
        self.full_calibration_btn = self.sidebar.full_calibration_btn
        self.polarizer_calibration_btn = self.sidebar.polarizer_calibration_btn
        self.oem_led_calibration_btn = self.sidebar.oem_led_calibration_btn
        self.led_model_training_btn = self.sidebar.led_model_training_btn

        # Forward baseline capture button (REBUILT)
        if hasattr(self.sidebar, "baseline_capture_btn"):
            self.baseline_capture_btn = self.sidebar.baseline_capture_btn
            logger.debug("✓ Forwarded baseline capture button")
        else:
            logger.warning("⚠️ baseline_capture_btn NOT found in sidebar")

        right_widget = QWidget()
        right_widget.setMinimumWidth(
            300,
        )  # Allow main content to compress so sidebar can expand more
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        nav_bar = self.navigation_presenter.create_navigation_bar()
        right_layout.addWidget(nav_bar)

        # Stacked widget to hold different content pages
        from PySide6.QtWidgets import QStackedWidget

        self.content_stack = QStackedWidget()

        # Create placeholder for sensorgram (will be replaced with real graphs after window shows)
        self._sensorgram_placeholder = self._create_sensorgram_placeholder()
        self.content_stack.addWidget(self._sensorgram_placeholder)  # Index 0
        self.content_stack.addWidget(self._create_blank_content("Edits"))  # Index 1
        self.content_stack.addWidget(self._create_blank_content("Analyze"))  # Index 2
        self.content_stack.addWidget(self._create_blank_content("Report"))  # Index 3

        right_layout.addWidget(self.content_stack, 1)
        self.splitter.addWidget(right_widget)

        # Set initial sizes: 520px for sidebar (more space due to wide Static section), rest for main content
        self.splitter.setSizes([520, 880])

        main_layout.addWidget(self.splitter)

        # Ensure Sensorgram page (index 0) is shown by default
        self.content_stack.setCurrentIndex(0)

    def _create_sensorgram_content(self):
        """Create the Sensorgram tab content with dual-graph layout (master-detail pattern)."""
        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame {  background: #F8F9FA;  border: none;}",
        )

        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        content_layout.setSpacing(Dimensions.SPACING_SM)

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
            show_delta_spr=False,
        )

        # Bottom graph (Detail/Cycle of Interest) - 70%
        self.cycle_of_interest_graph, bottom_graph = self._create_graph_container(
            "Active Cycle",
            height=400,
            show_delta_spr=True,
        )

        # Initialize Channel A as selected for flagging (default)
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
            "}",
        )

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
                    self.connecting_label.setText("Connecting to hardware...")

                    # Position as centered overlay
                    self.connecting_label.setParent(self)
                    self.connecting_label.raise_()  # Bring to front

                    # Center the label
                    label_width = 300
                    label_height = 60
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
                # Stop animation and hide label
                self._connecting_anim_timer.stop()
                self.connecting_label.setVisible(False)

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
        """Tick the 'Connecting to hardware...' animated ellipsis."""
        try:
            if not hasattr(self, "connecting_label") or not self.connecting_label.isVisible():
                return
            frames = [
                "Connecting to hardware",
                "Connecting to hardware.",
                "Connecting to hardware..",
                "Connecting to hardware..."
            ]
            self.connecting_label.setText(frames[self._connecting_anim_step % len(frames)])
            self._connecting_anim_step += 1
        except Exception:
            pass

    def _create_sensorgram_placeholder(self):
        """Create lightweight placeholder for sensorgram page during initial load.

        This placeholder mimics the actual UI layout with skeleton states
        so the transition is seamless when real graphs load.
        """
        placeholder = QFrame()
        placeholder.setStyleSheet("QFrame { background: {Colors.BACKGROUND_WHITE}; border: none; }")

        layout = QVBoxLayout(placeholder)
        layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        layout.setSpacing(Dimensions.SPACING_LG)

        # Timeline section skeleton
        timeline_card = QFrame()
        timeline_card.setStyleSheet(f"""
            QFrame {{
                background: {Colors.BACKGROUND_WHITE};
                border: 1px solid {Colors.OVERLAY_LIGHT_10};
                border-radius: {Dimensions.BORDER_RADIUS_LG};
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
                border: 1px dashed {Colors.OVERLAY_LIGHT_20};
                border-radius: 8px;
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
                border: 1px solid {Colors.OVERLAY_LIGHT_10};
                border-radius: {Dimensions.BORDER_RADIUS_LG};
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
                border: 1px dashed {Colors.OVERLAY_LIGHT_20};
                border-radius: 8px;
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

    def _create_graph_header(self):
        """Create header with channel toggle controls and cursor range inputs in two rows."""
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        # ===== First Row: Channel toggles, Live Data, Clear Graph =====
        first_row = QWidget()
        first_row.setFixedHeight(Dimensions.HEIGHT_BUTTON_XL)
        first_row_layout = QHBoxLayout(first_row)
        first_row_layout.setContentsMargins(0, 0, 0, 0)
        first_row_layout.setSpacing(8)

        # Channel selection label
        from affilabs.utils.ui_styles import UIStyleManager

        channels_label = QLabel("Display Channels:")
        channels_label.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  padding-right: 4px;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        channels_label.setToolTip("Toggle channel visibility on graphs")
        first_row_layout.addWidget(channels_label)

        # Channel toggles - show/hide channels on graphs
        self.channel_toggles = {}
        channel_names = {
            "A": ("#1D1D1F", "Channel A (Black) - Toggle visibility"),
            "B": ("#FF3B30", "Channel B (Red) - Toggle visibility"),
            "C": ("#007AFF", "Channel C (Blue) - Toggle visibility"),
            "D": ("#34C759", "Channel D (Green) - Toggle visibility"),
        }
        for ch, (color, tooltip) in channel_names.items():
            ch_btn = QPushButton(ch)
            ch_btn.setCheckable(True)
            ch_btn.setChecked(True)  # All visible by default
            ch_btn.setFixedSize(36, 32)
            ch_btn.setToolTip(tooltip)
            ch_btn.setStyleSheet(UIStyleManager.get_channel_button_style(color))

            # Store reference and connect to visibility toggle
            self.channel_toggles[ch] = ch_btn
            ch_btn.toggled.connect(
                lambda checked, channel=ch: self.sensogram_presenter.toggle_channel_visibility(
                    channel,
                    checked,
                ),
            )

            first_row_layout.addWidget(ch_btn)

        first_row_layout.addStretch()

        # Live Data checkbox
        self.live_data_checkbox = QCheckBox("Live Data")
        self.live_data_checkbox.setChecked(True)
        self.live_data_checkbox.setToolTip(
            "Enable/disable live cursor auto-follow\n"
            "• Checked: Stop cursor follows latest data point\n"
            "• Unchecked: Stop cursor freezes, data keeps recording\n"
            "• Cycle of Interest graph always updates between cursors",
        )
        self.live_data_checkbox.setStyleSheet(UIStyleManager.get_live_checkbox_style())
        self.live_data_checkbox.toggled.connect(
            self.sensogram_presenter.set_live_data_enabled,
        )
        first_row_layout.addWidget(self.live_data_checkbox)

        # Add spacing
        first_row_layout.addSpacing(16)

        # Clear Graph button
        self.clear_graph_btn = QPushButton("Clear Graph")
        self.clear_graph_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_STD)
        self.clear_graph_btn.setToolTip(
            "Clear all timeline data and reset graphs\n"
            "• Clears all channel data (A, B, C, D)\n"
            "• Resets baseline wavelengths\n"
            "• Does not stop acquisition",
        )
        self.clear_graph_btn.setStyleSheet(
            UIStyleManager.get_clear_button_style("neutral"),
        )
        # Connect to DataWindow's reset_graphs() method (triggers proper clear chain)
        self.clear_graph_btn.clicked.connect(self._on_clear_graph_clicked)
        first_row_layout.addWidget(self.clear_graph_btn)

        header_layout.addWidget(first_row)

        return header

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
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 8px;"
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
                "  border: 1px solid rgba(0, 0, 0, 0.1);"
                "  border-radius: 6px;"
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
        export_btn = QPushButton("📤 Export Range")
        export_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_MD)
        export_btn.setToolTip("Export data from selected cursor range to CSV")
        export_btn.setStyleSheet(
            "QPushButton {"
            "  background: #007AFF;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
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

            # Get cursor position
            cursor_time = cursor.value()

            # Find nearest timestamp from any channel with data
            nearest_time = cursor_time
            min_distance = float("inf")

            for ch in ["a", "b", "c", "d"]:
                time_data = self.app.buffer_mgr.timeline_data[ch].time
                if len(time_data) > 0:
                    timestamps = np.array(time_data)
                    idx = np.argmin(np.abs(timestamps - cursor_time))
                    if idx < len(timestamps):
                        candidate = timestamps[idx]
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

    def _clear_cycle_markers(self):
        """Clear all flags from the Active Cycle graph and markers from Full Sensorgram timeline."""
        try:
            logger.info("🗑️ Clear Flags button clicked")

            # Clear flags from Active Cycle (bottom) graph via flag manager
            if hasattr(self.app, 'flag_mgr') and self.app.flag_mgr:
                self.app.flag_mgr.clear_all_flags()
                logger.info("✅ Cleared all flags from Active Cycle graph")

            # Also clear cycle markers from Full Sensorgram (top) graph
            if not hasattr(self, "full_timeline_graph"):
                logger.warning("❌ Full timeline graph not found")
                return

            if not hasattr(self, "app") or not self.app:
                logger.warning("❌ App reference not found - cannot clear markers")
                return

            # Get reference to app's cycle markers
            if not hasattr(self.app, "_cycle_markers"):
                logger.warning("⚠️ No _cycle_markers attribute on app")
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
            print(f"✅ Cleared all flags and cycle markers")

            # Update flag counter
            self._update_flag_counter()

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

            # Clear injection reference if it exists in flag manager
            if hasattr(self.app, 'flag_mgr') and self.app.flag_mgr:
                self.app.flag_mgr._injection_reference_time = None
                self.app.flag_mgr._injection_reference_channel = None

                # Remove injection alignment line from graph
                if hasattr(self.app.flag_mgr, '_injection_alignment_line') and self.app.flag_mgr._injection_alignment_line:
                    if hasattr(self, 'cycle_of_interest_graph'):
                        try:
                            self.cycle_of_interest_graph.removeItem(self.app.flag_mgr._injection_alignment_line)
                        except:
                            pass
                    self.app.flag_mgr._injection_alignment_line = None

                logger.info("✅ Cleared injection alignment reference")

            # Refresh the Active Cycle display to show updated timing
            if hasattr(self.app, '_refresh_active_cycle_display'):
                self.app._refresh_active_cycle_display()

            print("✅ Channel timing reset to default")
            logger.info("✅ Channel timing reset complete")

        except Exception as e:
            logger.error(f"❌ Error resetting channel timing: {e}")
            print(f"❌ Error resetting timing: {e}")

    def _update_flag_counter(self):
        """Update the flag counter label with current number of flags."""
        try:
            if not hasattr(self, 'flag_counter_label'):
                return

            # Count flags from full_timeline_graph
            flag_count = 0
            if hasattr(self, 'full_timeline_graph') and hasattr(self.full_timeline_graph, 'flag_markers'):
                flag_count = len(self.full_timeline_graph.flag_markers)

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
        """Update button colors when colorblind mode is toggled."""
        from affilabs.utils.ui_styles import UIStyleManager
        from affilabs.plot_helpers import CHANNEL_COLORS, CHANNEL_COLORS_COLORBLIND

        # Select color palette based on mode
        colors = CHANNEL_COLORS_COLORBLIND if enabled else CHANNEL_COLORS

        # Update channel visibility toggle buttons
        if hasattr(self, 'channel_toggles'):
            for i, (ch, btn) in enumerate(self.channel_toggles.items()):
                btn.setStyleSheet(UIStyleManager.get_channel_button_style(colors[i]))

        # Update flag selection buttons
        if hasattr(self, 'channel_selection_buttons'):
            for i, (ch, btn) in enumerate(self.channel_selection_buttons.items()):
                btn.setStyleSheet(UIStyleManager.get_channel_button_style(colors[i]))

    def _create_graph_container(
        self,
        title: str,
        height: int,
        show_delta_spr: bool = False,
    ) -> QFrame:
        """Create a graph container with title and controls."""
        import pyqtgraph as pg
        from affilabs.utils.ui_styles import UIStyleManager

        container = QFrame()
        container.setMinimumHeight(height)
        container.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border: none;"
            "  border-radius: {Dimensions.BORDER_RADIUS_LG};"
            "}",
        )
        # Add shadow
        container.setGraphicsEffect(create_card_shadow())

        layout = QVBoxLayout(container)
        layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        layout.setSpacing(Dimensions.SPACING_MD)

        # Title row with controls
        title_row = QHBoxLayout()
        title_row.setSpacing(12)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        title_row.addWidget(title_label)

        title_row.addStretch()

        # Delta SPR signal display (only for Cycle of Interest graph)
        delta_display = None
        if show_delta_spr:
            delta_display = QLabel(
                "Δ SPR: Ch A: 0.0 RU  |  Ch B: 0.0 RU  |  Ch C: 0.0 RU  |  Ch D: 0.0 RU",
            )
            delta_display.setStyleSheet(
                "QLabel {"
                "  background: rgba(0, 0, 0, 0.08);"
                "  border: none;"
                "  border-radius: 6px;"
                "  padding: 8px 14px;"
                "  font-size: 12px;"
                "  color: {Colors.PRIMARY_TEXT};"
                f"  font-family: {Fonts.MONOSPACE};"
                "  font-weight: 600;"
                "}",
            )
            delta_display.setToolTip(
                "Real-time change in Surface Plasmon Resonance signal (relative to cycle start)",
            )
            title_row.addWidget(delta_display)

        layout.addLayout(title_row)

        # Add Flag controls row (only for Active Cycle graph)
        if show_delta_spr:
            flag_row = QHBoxLayout()
            flag_row.setSpacing(8)

            # Flagging channel selection label
            flag_label = QLabel("Flag Controls:")
            flag_label.setStyleSheet(
                "QLabel {"
                "  font-size: 12px;"
                "  font-weight: 600;"
                "  color: #1D1D1F;"
                "  padding-right: 4px;"
                "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
                "}"
            )
            flag_label.setToolTip("Flag marker controls - Select channel and manage flags")
            flag_row.addWidget(flag_label)

            # Flagging channel selection buttons (radio-style)
            self.channel_selection_buttons = {}

            flag_channel_names = ["A", "B", "C", "D"]
            flag_tooltips = [
                "Select Channel A for flagging",
                "Select Channel B for flagging",
                "Select Channel C for flagging",
                "Select Channel D for flagging",
            ]

            # Monochrome style for flag selection buttons (different from display toggles)
            flag_button_style = (
                "QPushButton {"
                "  background: #D1D1D6;"
                "  color: #1D1D1F;"
                "  border: none;"
                "  border-radius: 4px;"
                "  font-size: 11px;"
                "  font-weight: 700;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:!checked {"
                "  background: rgba(0, 0, 0, 0.05);"
                "  color: #86868B;"
                "  border: 1px solid rgba(0, 0, 0, 0.08);"
                "}"
                "QPushButton:hover:!checked {"
                "  background: rgba(0, 0, 0, 0.08);"
                "  border: 1px solid rgba(0, 0, 0, 0.12);"
                "}"
            )

            for i, ch in enumerate(flag_channel_names):
                tooltip = flag_tooltips[i]
                ch_btn = QPushButton(ch)
                ch_btn.setCheckable(True)
                ch_btn.setChecked(ch == "A")  # Channel A selected by default
                ch_btn.setFixedSize(36, 32)
                ch_btn.setToolTip(tooltip)
                ch_btn.setStyleSheet(flag_button_style)
                ch_btn.setCursor(Qt.CursorShape.PointingHandCursor)

                # Store reference and connect to channel selection for flagging
                self.channel_selection_buttons[ch] = ch_btn
                channel_letter_lower = ch.lower()  # 'A'→'a', 'B'→'b', etc.
                ch_btn.clicked.connect(
                    lambda _, channel=channel_letter_lower: self._on_flag_channel_selected(channel)
                )

                flag_row.addWidget(ch_btn)

            # Spacing between channel buttons and controls
            flag_row.addSpacing(12)

            # Flag counter display
            self.flag_counter_label = QLabel("Flags: 0")
            self.flag_counter_label.setStyleSheet(
                "QLabel { "
                "  font-size: 11px; "
                "  color: #86868B; "
                "  padding: 4px 8px; "
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif; "
                "}"
            )
            self.flag_counter_label.setToolTip("Number of flags on Live Sensorgram")
            flag_row.addWidget(self.flag_counter_label)

            # Spacing before action buttons
            flag_row.addSpacing(8)

            # Clear Flags button
            self.clear_flags_btn = QPushButton("C")
            self.clear_flags_btn.setFixedHeight(32)
            self.clear_flags_btn.setFixedWidth(32)
            self.clear_flags_btn.setToolTip(
                "Clear All Flags\n"
                "Remove all flags from Live Sensorgram\n"
                "• Clears all flag markers\n"
                "• Does not affect recorded data",
            )
            self.clear_flags_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: #8E8E93;"
                "  border: 1px solid rgba(0, 0, 0, 0.08);"
                "  border-radius: 4px;"
                "  font-size: 11px;"
                "  font-weight: 500;"
                "  padding: 0px 12px;"
                "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(255, 59, 48, 0.15);"
                "  color: #FF3B30;"
                "  border: 1px solid rgba(255, 59, 48, 0.2);"
                "}"
                "QPushButton:pressed {"
                "  background: rgba(255, 59, 48, 0.25);"
                "}"
            )
            self.clear_flags_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.clear_flags_btn.clicked.connect(self._clear_cycle_markers)
            flag_row.addWidget(self.clear_flags_btn)

            # Reset Timing button
            self.reset_timing_btn = QPushButton("R")
            self.reset_timing_btn.setFixedHeight(32)
            self.reset_timing_btn.setFixedWidth(32)
            self.reset_timing_btn.setToolTip(
                "Reset Timing\n"
                "Reset all channel time shifts to default\n"
                "• Removes injection alignment offsets\n"
                "• Restores original timing"
            )
            self.reset_timing_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: #8E8E93;"
                "  border: 1px solid rgba(0, 0, 0, 0.08);"
                "  border-radius: 4px;"
                "  font-size: 11px;"
                "  font-weight: 500;"
                "  padding: 0px 12px;"
                "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(255, 149, 0, 0.15);"
                "  color: #FF9500;"
                "  border: 1px solid rgba(255, 149, 0, 0.2);"
                "}"
                "QPushButton:pressed {"
                "  background: rgba(255, 149, 0, 0.25);"
                "}"
            )
            self.reset_timing_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.reset_timing_btn.clicked.connect(self._reset_channel_timing)
            flag_row.addWidget(self.reset_timing_btn)

            flag_row.addStretch()

            layout.addLayout(flag_row)

        # Create standardized time-series plot
        left_label = "Δ SPR (RU)" if show_delta_spr else "λ (nm)"
        plot_widget = create_time_plot(left_label)

        # Create plot curves for 4 channels with distinct colors
        # Ch A: Black, Ch B: Red, Ch C: Blue, Ch D: Green
        curves = add_channel_curves(plot_widget, clickable=False, width=2)

        # Add Start/Stop cursors for Full Experiment Timeline (top graph)
        # Navigation concept: Live Sensorgram is the navigation space, cursors define cycle of interest region
        start_cursor = None
        stop_cursor = None

        # Enable curve clicking for channel selection (ONLY on Active Cycle graph)
        if show_delta_spr:  # Active Cycle (bottom graph)
            for i, curve in enumerate(curves):
                try:
                    # Make curve clickable with larger tolerance (18px)
                    curve.setCurveClickable(True, width=18)
                    # Connect to channel selection for flagging
                    channel_letter = chr(ord('a') + i)  # 0→'a', 1→'b', 2→'c', 3→'d'
                    curve.sigClicked.connect(
                        lambda *args, ch=channel_letter: self._on_flag_channel_selected(ch)
                    )
                    logger.debug(f"[ACTIVE CYCLE] Connected click handler for channel {channel_letter.upper()}")
                except AttributeError as e:
                    logger.warning(f"[ACTIVE CYCLE] Could not make curve {i} clickable: {e}")
                except Exception as e:
                    logger.warning(f"[ACTIVE CYCLE] Error connecting curve {i} click: {e}")

        if not show_delta_spr:  # Only for Live Sensorgram (top graph)
            # Start cursor - thicker line (3px) for easier interaction
            start_cursor = pg.InfiniteLine(
                pos=0,
                angle=90,
                pen=pg.mkPen(color="#1D1D1F", width=3),  # 3px for easier click target
                movable=True,
                label="Start: {value:.1f}s",
                labelOpts={
                    "position": 0.5,  # Center of graph
                    "color": "#1D1D1F",
                    "fill": "#FFFFFF",
                    "movable": False,
                    "rotateAxis": (1, 0),  # Rotate 180 degrees total (horizontal)
                },
            )
            # Thicker hover effect (5px) for clear visual feedback
            start_cursor.setHoverPen(pg.mkPen(color="#666666", width=5))
            plot_widget.addItem(start_cursor)

            # Stop cursor - thicker line (3px) for easier interaction
            stop_cursor = pg.InfiniteLine(
                pos=0,  # Start at 0, will auto-follow as data comes in
                angle=90,
                pen=pg.mkPen(color="#1D1D1F", width=3),  # 3px for easier click target
                movable=True,
                label="Stop: {value:.1f}s",
                labelOpts={
                    "position": 0.5,  # Center of graph
                    "color": "#1D1D1F",
                    "fill": "#FFFFFF",
                    "movable": False,
                    "rotateAxis": (1, 0),  # Rotate 180 degrees total (horizontal)
                },
            )
            # Thicker hover effect (5px) for clear visual feedback
            stop_cursor.setHoverPen(pg.mkPen(color="#666666", width=5))
            plot_widget.addItem(stop_cursor)

        # Store references to curves and cursors on the plot widget
        plot_widget.curves = curves
        plot_widget.delta_display = delta_display
        plot_widget.start_cursor = start_cursor
        plot_widget.stop_cursor = stop_cursor
        plot_widget.flag_markers = []  # Store flag marker items
        plot_widget.channel_flags = {
            0: [],
            1: [],
            2: [],
            3: [],
        }  # Store flags per channel (index: list of (x, y, note))

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

        layout.addWidget(plot_widget, 1)

        return plot_widget, container

    def _on_flag_channel_selected(self, channel: str):
        """Handle channel selection for flag placement in Active Cycle graph.

        Clicking a curve in Active Cycle graph:
        - Selects the channel for flagging
        - Highlights the curve
        - Enables flagging mode

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
        """
        if not hasattr(self, "cycle_of_interest_graph"):
            return

        # Store selected channel for flagging operations
        channel_idx = ord(channel) - ord('a')  # 'a'→0, 'b'→1, 'c'→2, 'd'→3
        channel_letter = channel.upper()

        self.selected_channel_for_flagging = channel_idx
        self.selected_channel_letter = channel_letter

        # Update button states (radio button behavior - only one checked)
        if hasattr(self, "channel_selection_buttons"):
            for ch, btn in self.channel_selection_buttons.items():
                btn.setChecked(ch == channel_letter)

        # Store selected channel in main app (will be used by flag placement logic)
        if hasattr(self, "app"):
            self.app._selected_flag_channel = channel

        # Update curve highlighting (make selected curve thicker)
        import pyqtgraph as pg

        # Get channel colors (same as defined in add_channel_curves)
        channel_colors = [
            (0, 0, 0),        # A: Black
            (255, 0, 0),      # B: Red
            (0, 0, 255),      # C: Blue
            (0, 170, 0),      # D: Green
        ]

        for i, curve in enumerate(self.cycle_of_interest_graph.curves):
            if i == channel_idx:
                # Selected curve: thicker line (width 4)
                curve.setPen(pg.mkPen(color=channel_colors[i], width=4))
            else:
                # Unselected curves: normal width (width 2)
                curve.setPen(pg.mkPen(color=channel_colors[i], width=2))

        logger.debug(f"Channel {channel.upper()} selected for flagging (curve highlighted)")

        # Enable flagging mode for Active Cycle graph
        self._enable_flagging_mode(channel_idx, channel_letter, graph_name="Active Cycle")

    def _enable_flagging_mode(self, channel_idx, channel_letter, graph_name="Active Cycle"):
        """Enable flagging mode for the selected channel.

        Args:
            channel_idx: Index of the channel (0-3)
            channel_letter: Letter of the channel (A-D)
            graph_name: Name of the graph where flagging is enabled ("Active Cycle" or "Live Sensorgram")
        """
        if not hasattr(self, "full_timeline_graph"):
            return

        # Store current flagging mode state
        if not hasattr(self, "flagging_enabled"):
            self.flagging_enabled = False

        # Only show messages for Active Cycle graph (when selecting channel for flagging)
        if graph_name == "Active Cycle":
            print(f"Flagging mode ready for Channel {channel_letter}")
            print(f"Right-click on the LIVE SENSORGRAM graph (top) to add a flag at absolute time")
            print("Ctrl+Right-click to remove a flag near that position")

    def _on_plot_clicked(self, event, plot_widget):
        """Handle clicks on the Live Sensorgram (top graph) for adding/removing flags.
        Bottom graph (Cycle of Interest) does not have this handler - uses default PyQtGraph interactions.

        Right-click: Add flag at position on selected channel
        Ctrl+Right-click: Remove flag near position on selected channel
        """
        # Only process right-clicks for flagging
        if event.button() != 2:  # 2 = right mouse button
            return

        # Check if a channel is selected for flagging
        if not hasattr(self, "selected_channel_for_flagging"):
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
        if not hasattr(self, "full_timeline_graph"):
            return

        import pyqtgraph as pg

        # Get channel letter
        channel_letter = chr(65 + channel_idx)

        # Channel colors matching the cycle curves
        channel_colors = [
            (0, 0, 0),        # A: Black
            (255, 0, 0),      # B: Red
            (0, 0, 255),      # C: Blue
            (0, 170, 0),      # D: Green
        ]
        color = channel_colors[channel_idx] if channel_idx < len(channel_colors) else (255, 0, 0)

        # Create flag marker (vertical line with text)
        flag_line = pg.InfiniteLine(
            pos=x_pos,
            angle=90,
            pen=pg.mkPen(
                color=color,
                width=2,
                style=pg.QtCore.Qt.PenStyle.DashLine,
            ),
            movable=False,
        )

        # Add text label at the top
        flag_text = pg.TextItem(
            text=f"🚩 Ch{channel_letter}",
            color=color,
            anchor=(0.5, 1),  # Center, bottom
        )
        # Position text fixed to timeline (data coordinates), not window
        # Get the y-axis data range and position at top of range
        y_range = self.full_timeline_graph.viewRange()[1]  # [ymin, ymax]
        y_pos_fixed = y_range[1] * 0.95  # Position at 95% of max to keep it visible
        flag_text.setPos(x_pos, y_pos_fixed)

        # Add to Live Sensorgram (top graph)
        self.full_timeline_graph.addItem(flag_line)
        self.full_timeline_graph.addItem(flag_text)

        # Store references
        flag_marker = {
            "channel": channel_idx,
            "x": x_pos,
            "y": y_pos,
            "note": note,
            "line": flag_line,
            "text": flag_text,
        }

        self.full_timeline_graph.flag_markers.append(flag_marker)
        self.full_timeline_graph.channel_flags[channel_idx].append((x_pos, y_pos, note))

        # Update the table Flags column
        self._update_flags_table()

        # Update flag counter
        self._update_flag_counter()

        print(f"Flag added to Channel {channel_letter} at x={x_pos:.2f}, y={y_pos:.2f}")

    def _remove_flag_at_position(self, channel_idx, x_pos, tolerance=5.0):
        """Remove a flag marker near the specified x position on the selected channel."""
        if not hasattr(self, "full_timeline_graph"):
            return

        # Find and remove flags within tolerance
        removed_count = 0
        markers_to_remove = []

        for marker in self.full_timeline_graph.flag_markers:
            if (
                marker["channel"] == channel_idx
                and abs(marker["x"] - x_pos) <= tolerance
            ):
                # Remove visual elements
                self.full_timeline_graph.removeItem(marker["line"])
                self.full_timeline_graph.removeItem(marker["text"])
                markers_to_remove.append(marker)
                removed_count += 1

        # Remove from list
        for marker in markers_to_remove:
            self.full_timeline_graph.flag_markers.remove(marker)

        # Update channel flags
        self.full_timeline_graph.channel_flags[channel_idx] = [
            (x, y, note)
            for x, y, note in self.full_timeline_graph.channel_flags[channel_idx]
            if abs(x - x_pos) > tolerance
        ]

        # Update table
        self._update_flags_table()

        # Update flag counter
        self._update_flag_counter()

        if removed_count > 0:
            channel_letter = chr(65 + channel_idx)
            print(
                f"Removed {removed_count} flag(s) from Channel {channel_letter} near x={x_pos:.2f}",
            )

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
        """Update the Flags column in the cycle data table with current flags."""
        if not hasattr(self, "cycle_data_table") or not hasattr(
            self,
            "full_timeline_graph",
        ):
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
            flag_summary = ", ".join(
                [f"Ch{ch}: {count}" for ch, count in flag_counts.items()],
            )
            print(f"Flags summary: {flag_summary}")
            # In full implementation: update specific table cell in Flags column

    def _on_cursor_dragged(self):
        """Handle cursor dragging - update label format dynamically."""
        if not hasattr(self, "full_timeline_graph"):
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
            start_cursor.label.setFormat(f"Start: {start_pos:.1f}s")
            stop_cursor.label.setFormat(f"Stop: {stop_pos:.1f}s")

    def _on_cursor_moved(self):
        """Handle cursor movement finished - update selected region."""
        if not hasattr(self, "full_timeline_graph"):
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
        if tab_name == "Analyze":
            return self._create_analyze_content()
        if tab_name == "Report":
            return self._create_report_content()

        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame {  background: #F8F9FA;  border: none;}",
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
        self.edits_tab = EditsTab(self)
        return self.edits_tab.create_content()

    # Edits tab helper methods - delegate to EditsTab instance
    def _update_edits_selection_view(self):
        """Update edits selection view (delegates to EditsTab)."""
        if hasattr(self, 'edits_tab'):
            self.edits_tab._update_selection_view()

    def _toggle_edits_channel(self, ch_idx, visible):
        """Toggle edits channel visibility (delegates to EditsTab)."""
        if hasattr(self, 'edits_tab'):
            self.edits_tab._toggle_channel(ch_idx, visible)

    def _export_edits_selection(self):
        """Export edits selection (delegates to EditsTab)."""
        if hasattr(self, 'edits_tab'):
            self.edits_tab._export_selection()

    def _load_data_from_excel(self):
        """Alias for _load_previous_data for the new Edits tab."""
        self._load_previous_data()

    # Dead code removed (lines 2848-3223):
    # - Stub _create_segment_from_selection (real implementation at line ~6451)
    # - Duplicate _create_edits_right_panel (367 lines)
    # - Duplicate _create_analyze_left_panel
    # Active definitions are below

    def _create_edits_right_panel(self):
        """Create right panel with primary graph and thumbnail selectors."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {  background: {Colors.TRANSPARENT};  border: none;}",
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Primary Graph Container
        primary_graph = QFrame()
        primary_graph.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border: none;"
            "  border-radius: {Dimensions.BORDER_RADIUS_LG};"
            "}",
        )
        primary_graph.setGraphicsEffect(create_card_shadow())

        primary_layout = QVBoxLayout(primary_graph)
        primary_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        primary_layout.setSpacing(Dimensions.SPACING_MD)

        # Graph header
        graph_header = QHBoxLayout()
        graph_title = QLabel("Primary Cycle View")
        graph_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        graph_header.addWidget(graph_title)
        graph_header.addStretch()

        # Channel toggles (compact)
        for ch, color in [
            ("A", "#000000"),  # Black
            ("B", "#FF0000"),  # Red
            ("C", "#0000FF"),  # Blue
            ("D", "#00AA00"),  # Green (0, 170, 0)
        ]:
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
                "  font-family: {Fonts.SYSTEM};"
                "}"
                "QPushButton:!checked {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: {Colors.SECONDARY_TEXT};"
                "}",
            )
            graph_header.addWidget(ch_btn)

        primary_layout.addLayout(graph_header)

        # Create actual PyQtGraph widget for cycle display
        import pyqtgraph as pg
        self.edits_primary_graph = pg.PlotWidget()
        self.edits_primary_graph.setBackground('w')
        self.edits_primary_graph.showGrid(x=True, y=True, alpha=0.3)
        self.edits_primary_graph.setLabel('left', 'Response (RU)')
        self.edits_primary_graph.setLabel('bottom', 'Time (s)')
        self.edits_primary_graph.setMinimumHeight(400)

        # Enable right-click menu for adding flags
        self.edits_primary_graph.scene().sigMouseClicked.connect(self._on_edits_graph_clicked)

        # Install keyboard event filter for flag movement
        from PySide6.QtCore import QObject, QEvent, Qt

        class EditsKeyboardFilter(QObject):
            def __init__(self, main_window):
                super().__init__()
                self.main_window = main_window

            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.KeyPress:
                    key = event.key()

                    # Check if we have a selected flag
                    if not hasattr(self.main_window, 'edits_tab'):
                        return False

                    selected_idx = self.main_window.edits_tab._selected_flag_idx
                    if selected_idx is None or selected_idx >= len(self.main_window.edits_tab._edits_flags):
                        return False

                    flag = self.main_window.edits_tab._edits_flags[selected_idx]

                    # Move flag left/right with arrow keys
                    if key == Qt.Key.Key_Left:
                        flag.time -= 1.0  # Move 1 second left
                        flag.marker.setData([flag.time], [flag.spr])
                        return True
                    elif key == Qt.Key.Key_Right:
                        flag.time += 1.0  # Move 1 second right
                        flag.marker.setData([flag.time], [flag.spr])
                        return True
                    elif key == Qt.Key.Key_Escape:
                        # Deselect flag
                        flag.marker.setPen(pg.mkPen('w', width=2))
                        self.main_window.edits_tab._selected_flag_idx = None
                        return True
                    elif key == Qt.Key.Key_Delete:
                        # Delete flag
                        self.main_window.edits_primary_graph.removeItem(flag.marker)
                        self.main_window.edits_tab._edits_flags.pop(selected_idx)
                        self.main_window.edits_tab._selected_flag_idx = None
                        return True

                return False

        self._edits_keyboard_filter = EditsKeyboardFilter(self)
        self.edits_primary_graph.installEventFilter(self._edits_keyboard_filter)

        # Create curves for each channel (matching main window colors)
        self.edits_graph_curves = [
            self.edits_primary_graph.plot(pen=pg.mkPen(color=(0, 0, 0), width=2)),       # Channel A: Black
            self.edits_primary_graph.plot(pen=pg.mkPen(color=(255, 0, 0), width=2)),     # Channel B: Red
            self.edits_primary_graph.plot(pen=pg.mkPen(color=(0, 0, 255), width=2)),     # Channel C: Blue
            self.edits_primary_graph.plot(pen=pg.mkPen(color=(0, 170, 0), width=2)),     # Channel D: Green
        ]

        primary_layout.addWidget(self.edits_primary_graph)

        panel_layout.addWidget(primary_graph, 4)

        # Reference Graphs Container (Phase 3)
        references_container = QFrame()
        references_container.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border: none;"
            "  border-radius: {Dimensions.BORDER_RADIUS_LG};"
            "}",
        )
        references_container.setGraphicsEffect(create_card_shadow())

        references_layout = QVBoxLayout(references_container)
        references_layout.setContentsMargins(Dimensions.MARGIN_SM, Dimensions.MARGIN_SM, Dimensions.MARGIN_SM, Dimensions.MARGIN_SM)
        references_layout.setSpacing(Dimensions.SPACING_SM)

        # References label
        ref_header = QHBoxLayout()
        ref_label = QLabel("Reference Graphs")
        ref_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        ref_header.addWidget(ref_label)

        # Clear all button
        clear_refs_btn = QPushButton("Clear All")
        clear_refs_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_SM)
        clear_refs_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  color: {Colors.PRIMARY_TEXT};"
            "  border: none;"
            "  border-radius: 4px;"
            "  font-size: 11px;"
            "  font-weight: 500;"
            "  padding: 0px 8px;"
            "  font-family: {Fonts.SYSTEM};"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.08);"
            "}",
        )
        clear_refs_btn.clicked.connect(self._clear_reference_graphs)
        ref_header.addWidget(clear_refs_btn)
        references_layout.addLayout(ref_header)

        # Three reference graph widgets
        ref_graphs_layout = QHBoxLayout()
        ref_graphs_layout.setSpacing(8)

        import pyqtgraph as pg
        self.edits_reference_graphs = []
        self.edits_reference_curves = []
        self.edits_reference_cycle_data = [None, None, None]  # Store which cycle is loaded

        for i in range(3):
            # Create container for each reference
            ref_frame = QFrame()
            ref_frame.setStyleSheet(
                "QFrame {"
                "  background: rgba(0, 0, 0, 0.02);"
                "  border: 1px dashed rgba(0, 0, 0, 0.15);"
                "  border-radius: 6px;"
                "}",
            )
            ref_frame.setAcceptDrops(True)

            ref_layout = QVBoxLayout(ref_frame)
            ref_layout.setContentsMargins(4, 4, 4, 4)
            ref_layout.setSpacing(2)

            # Label
            ref_name_label = QLabel(f"Drag cycle here")
            ref_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ref_name_label.setStyleSheet(
                "QLabel {"
                "  font-size: 10px;"
                "  color: {Colors.SECONDARY_TEXT};"
                "  background: {Colors.TRANSPARENT};"
                "  font-family: {Fonts.SYSTEM};"
                "}",
            )
            ref_layout.addWidget(ref_name_label)

            # Mini graph
            ref_graph = pg.PlotWidget()
            ref_graph.setBackground('w')
            ref_graph.setFixedHeight(120)
            ref_graph.hideAxis('left')
            ref_graph.hideAxis('bottom')
            ref_graph.setMouseEnabled(x=False, y=False)

            # Create curves for 4 channels (matching main window colors)
            ref_curves = [
                ref_graph.plot(pen=pg.mkPen(color=(0, 0, 0), width=1)),       # Channel A: Black
                ref_graph.plot(pen=pg.mkPen(color=(255, 0, 0), width=1)),     # Channel B: Red
                ref_graph.plot(pen=pg.mkPen(color=(0, 0, 255), width=1)),     # Channel C: Blue
                ref_graph.plot(pen=pg.mkPen(color=(0, 170, 0), width=1)),     # Channel D: Green
            ]

            ref_layout.addWidget(ref_graph)

            # Store references
            self.edits_reference_graphs.append(ref_graph)
            self.edits_reference_curves.append(ref_curves)

            # Add to layout
            ref_graphs_layout.addWidget(ref_frame)

            # Store frame and label for later updates
            if not hasattr(self, 'edits_reference_frames'):
                self.edits_reference_frames = []
                self.edits_reference_labels = []
            self.edits_reference_frames.append(ref_frame)
            self.edits_reference_labels.append(ref_name_label)

        references_layout.addLayout(ref_graphs_layout)

        panel_layout.addWidget(references_container, 2)

        return panel

    def _create_analyze_content(self):
        """Create the Analyze tab content with processed data graph, statistics, and kinetic analysis."""
        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame {  background: #F8F9FA;  border: none;}",
        )

        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        content_layout.setSpacing(Dimensions.SPACING_MD)

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
            "QFrame {  background: {Colors.TRANSPARENT};  border: none;}",
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Main Processed Data Graph
        main_graph = QFrame()
        main_graph.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border: none;"
            "  border-radius: {Dimensions.BORDER_RADIUS_LG};"
            "}",
        )
        main_graph.setGraphicsEffect(create_card_shadow())

        main_graph_layout = QVBoxLayout(main_graph)
        main_graph_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        main_graph_layout.setSpacing(Dimensions.SPACING_MD)

        # Header
        graph_header = QHBoxLayout()
        graph_title = QLabel("Processed Data")
        graph_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        graph_header.addWidget(graph_title)
        graph_header.addStretch()

        # View options
        view_btns = ["Fitted", "Residuals", "Overlay"]
        for i, btn_text in enumerate(view_btns):
            view_btn = QPushButton(btn_text)
            view_btn.setCheckable(True)
            view_btn.setChecked(i == 0)
            view_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_MD)
            view_btn.setMinimumWidth(72)
            view_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: {Colors.SECONDARY_TEXT};"
                "  border: none;"
                "  border-radius: 6px;"
                "  font-size: 12px;"
                "  font-weight: 500;"
                "  font-family: {Fonts.SYSTEM};"
                "}"
                "QPushButton:checked {"
                "  background: #1D1D1F;"
                "  color: white;"
                "  font-weight: 600;"
                "}"
                "QPushButton:hover:!checked {"
                "  background: rgba(0, 0, 0, 0.1);"
                "}",
            )
            graph_header.addWidget(view_btn)

        main_graph_layout.addLayout(graph_header)

        # Graph canvas
        graph_canvas = QFrame()
        graph_canvas.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "}",
        )
        canvas_layout = QVBoxLayout(graph_canvas)
        canvas_placeholder = QLabel(
            "[Processed Data Graph]\n\n"
            "Fitted curves with model overlay\n"
            "Interactive zoom and pan enabled",
        )
        canvas_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        canvas_placeholder.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: #C7C7CC;"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        canvas_layout.addWidget(canvas_placeholder)
        main_graph_layout.addWidget(graph_canvas, 1)

        panel_layout.addWidget(main_graph, 3)

        # Statistics / Goodness of Fit Graph
        stats_graph = QFrame()
        stats_graph.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border: none;"
            "  border-radius: {Dimensions.BORDER_RADIUS_LG};"
            "}",
        )
        stats_graph.setGraphicsEffect(create_card_shadow())

        stats_layout = QVBoxLayout(stats_graph)
        stats_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        stats_layout.setSpacing(Dimensions.SPACING_MD)

        # Header
        stats_header = QHBoxLayout()
        stats_title = QLabel("Goodness of Fit Analysis")
        stats_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
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
            "}",
        )
        stats_header.addWidget(r_squared)

        stats_layout.addLayout(stats_header)

        # Stats canvas
        stats_canvas = QFrame()
        stats_canvas.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "}",
        )
        stats_canvas_layout = QVBoxLayout(stats_canvas)
        stats_placeholder = QLabel(
            "[Residuals / Chi-Square Plot]\n\n"
            "Statistical analysis visualization\n"
            "Chi² = 1.23e-4, RMSE = 0.012",
        )
        stats_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats_placeholder.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: #C7C7CC;"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        stats_canvas_layout.addWidget(stats_placeholder)
        stats_layout.addWidget(stats_canvas, 1)

        panel_layout.addWidget(stats_graph, 2)

        return panel

    def _create_analyze_right_panel(self):
        """Create right panel with model selection, data table, and export options."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {  background: {Colors.TRANSPARENT};  border: none;}",
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Mathematical Model Selection
        model_container = QFrame()
        model_container.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border: none;"
            "  border-radius: {Dimensions.BORDER_RADIUS_LG};"
            "}",
        )
        model_container.setGraphicsEffect(create_card_shadow())

        model_layout = QVBoxLayout(model_container)
        model_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        model_layout.setSpacing(Dimensions.SPACING_MD)

        # Header
        model_title = QLabel("Mathematical Model")
        model_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        model_layout.addWidget(model_title)

        # Model selection dropdown
        from PySide6.QtWidgets import QComboBox

        model_dropdown = QComboBox()
        model_dropdown.addItems(
            [
                "Langmuir 1:1",
                "Two-State Binding",
                "Bivalent Analyte",
                "Mass Transport Limited",
                "Heterogeneous Ligand",
                "Custom Model",
            ],
        )
        model_dropdown.setFixedHeight(Dimensions.HEIGHT_BUTTON_LG)
        model_dropdown.setStyleSheet(
            "QComboBox {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  color: {Colors.PRIMARY_TEXT};"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 8px 12px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  font-family: {Fonts.SYSTEM};"
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
            "}",
        )
        model_layout.addWidget(model_dropdown)

        # Fit button
        fit_btn = QPushButton("Run Fitting Analysis")
        fit_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_LG)
        fit_btn.setStyleSheet(
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  font-family: {Fonts.SYSTEM};"
            "}"
            "QPushButton:hover {"
            "  background: #3A3A3C;"
            "}"
            "QPushButton:pressed {"
            "  background: #48484A;"
            "}",
        )
        model_layout.addWidget(fit_btn)

        # Model parameters info
        params_label = QLabel("Model Parameters")
        params_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  margin-top: 8px;"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        model_layout.addWidget(params_label)

        params_info = QLabel(
            "ka: Association rate constant\n"
            "kd: Dissociation rate constant\n"
            "KD: Equilibrium constant\n"
            "Rmax: Maximum response",
        )
        params_info.setStyleSheet(
            "QLabel {"
            "  font-size: 11px;"
            "  color: {Colors.SECONDARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  line-height: 1.6;"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        model_layout.addWidget(params_info)

        panel_layout.addWidget(model_container)

        # Kinetic Data Table
        data_container = QFrame()
        data_container.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border: none;"
            "  border-radius: {Dimensions.BORDER_RADIUS_LG};"
            "}",
        )
        data_container.setGraphicsEffect(create_card_shadow())

        data_layout = QVBoxLayout(data_container)
        data_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        data_layout.setSpacing(Dimensions.SPACING_MD)

        # Header
        data_header = QHBoxLayout()
        data_title = QLabel("Kinetic Results")
        data_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        data_header.addWidget(data_title)
        data_header.addStretch()

        copy_btn = QPushButton("📋 Copy")
        copy_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_MD)
        copy_btn.setMinimumWidth(72)
        copy_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  color: {Colors.PRIMARY_TEXT};"
            "  border: none;"
            "  border-radius: 6px;"
            "  font-size: 12px;"
            "  font-weight: 500;"
            "  font-family: {Fonts.SYSTEM};"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.1);"
            "}",
        )
        data_header.addWidget(copy_btn)

        data_layout.addLayout(data_header)

        # Data table
        from PySide6.QtWidgets import QHeaderView, QTableWidget

        data_table = QTableWidget(4, 2)
        data_table.setHorizontalHeaderLabels(["Parameter", "Value"])
        data_table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        data_table.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        data_table.setStyleSheet(
            "QTableWidget {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "  gridline-color: rgba(0, 0, 0, 0.06);"
            "  font-size: 12px;"
            "  font-family: {Fonts.SYSTEM};"
            "}"
            "QTableWidget::item {"
            "  padding: 8px;"
            "  color: {Colors.PRIMARY_TEXT};"
            "}"
            "QHeaderView::section {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  color: {Colors.SECONDARY_TEXT};"
            "  padding: 8px;"
            "  border: none;"
            "  border-bottom: 1px solid rgba(0, 0, 0, 0.08);"
            "  font-weight: 600;"
            "  font-size: 11px;"
            "}",
        )

        # Sample data
        from PySide6.QtWidgets import QTableWidgetItem

        results = [
            ("ka (M⁻¹s⁻¹)", "1.23e5 ± 0.04e5"),
            ("kd (s⁻¹)", "3.45e-4 ± 0.12e-4"),
            ("KD (M)", "2.80e-9 ± 0.15e-9"),
            ("Δ SPR (nm)", "0.45 ± 0.02"),
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
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border: none;"
            "  border-radius: {Dimensions.BORDER_RADIUS_LG};"
            "}",
        )
        export_container.setGraphicsEffect(create_card_shadow())

        export_layout = QVBoxLayout(export_container)
        export_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        export_layout.setSpacing(Dimensions.SPACING_MD)

        export_title = QLabel("Export Data")
        export_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        export_layout.addWidget(export_title)

        # Export buttons
        export_btns = QHBoxLayout()
        export_btns.setSpacing(8)

        csv_btn = QPushButton("Save CSV")
        csv_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_LG)
        csv_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  color: {Colors.PRIMARY_TEXT};"
            "  border: none;"
            "  border-radius: 8px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  font-family: {Fonts.SYSTEM};"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.08);"
            "}",
        )
        export_btns.addWidget(csv_btn)

        json_btn = QPushButton("Save JSON")
        json_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_LG)
        json_btn.setStyleSheet(csv_btn.styleSheet())
        export_btns.addWidget(json_btn)

        export_layout.addLayout(export_btns)

        # Export graph image button (full width)
        image_btn = QPushButton("📸 Export Active Cycle Image")
        image_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_LG)
        image_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 122, 255, 0.1);"
            "  color: #007AFF;"
            "  border: none;"
            "  border-radius: 8px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  font-family: {Fonts.SYSTEM};"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 122, 255, 0.2);"
            "}",
        )
        image_btn.setToolTip("Export the active cycle graph as a high-resolution PNG image")
        self.export_image_btn = image_btn
        export_layout.addWidget(image_btn)

        export_layout.addLayout(export_btns)

        panel_layout.addWidget(export_container)

        panel_layout.addStretch()

        return panel

    def _create_report_content(self):
        """Create the Report tab content for generating PDF reports with graphs, tables, and notes."""
        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame {  background: #F8F9FA;  border: none;}",
        )

        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        content_layout.setSpacing(Dimensions.SPACING_MD)

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
            "QFrame {  background: {Colors.TRANSPARENT};  border: none;}",
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
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "}",
        )
        header.addWidget(report_title)
        header.addStretch()

        # Generate PDF button
        pdf_btn = QPushButton("📄 Generate PDF")
        pdf_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_XL)
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
            "  font-family: {Fonts.SYSTEM};"
            "}"
            "QPushButton:hover {"
            "  background: #E6342A;"
            "}"
            "QPushButton:pressed {"
            "  background: #CC2E25;"
            "}",
        )
        header.addWidget(pdf_btn)

        panel_layout.addLayout(header)

        # Report canvas/preview area
        canvas = QFrame()
        canvas.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border: none;"
            "  border-radius: {Dimensions.BORDER_RADIUS_LG};"
            "}",
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
            "QScrollArea {  border: none;  background: {Colors.TRANSPARENT};}",
        )

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        scroll_layout.setSpacing(20)

        # Sample report elements
        # Title
        title_edit = QLabel("Kinetic Analysis Report")
        title_edit.setStyleSheet(
            "QLabel {"
            "  font-size: 24px;"
            "  font-weight: {Fonts.WEIGHT_BOLD};"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  padding: 8px;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "}",
        )
        scroll_layout.addWidget(title_edit)

        # Date/Info
        info_label = QLabel("Date: November 20, 2025\nExperiment ID: EXP-2025-001")
        info_label.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: {Colors.SECONDARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  padding: 4px 8px;"
            "  line-height: 1.6;"
            "  font-family: {Fonts.SYSTEM};"
            "}",
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
            "}",
        )
        graph_label = QLabel("[Graph Element]\n\nClick to insert graph")
        graph_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        graph_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  border: none;"
            "  font-family: {Fonts.SYSTEM};"
            "}",
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
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  padding: 8px;"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        scroll_layout.addWidget(notes_label)

        notes_edit = QTextEdit()
        notes_edit.setPlaceholderText(
            "Add experiment notes, observations, or conclusions...",
        )
        notes_edit.setFixedHeight(120)
        notes_edit.setStyleSheet(
            "QTextEdit {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "  padding: 12px;"
            "  font-size: 13px;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
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
            "}",
        )
        table_label = QLabel("[Table Element]\n\nClick to insert data table")
        table_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  color: #34C759;"
            "  background: {Colors.TRANSPARENT};"
            "  border: none;"
            "  font-family: {Fonts.SYSTEM};"
            "}",
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
            "QFrame {  background: {Colors.TRANSPARENT};  border: none;}",
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Insert Elements Section
        elements_container = QFrame()
        elements_container.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border: none;"
            "  border-radius: {Dimensions.BORDER_RADIUS_LG};"
            "}",
        )
        elements_container.setGraphicsEffect(create_card_shadow())

        elements_layout = QVBoxLayout(elements_container)
        elements_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        elements_layout.setSpacing(Dimensions.SPACING_MD)

        elements_title = QLabel("Insert Elements")
        elements_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
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
            elem_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_LG)
            elem_btn.setToolTip(tooltip)
            elem_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.04);"
                "  color: {Colors.PRIMARY_TEXT};"
                "  border: none;"
                "  border-radius: 8px;"
                "  font-size: 13px;"
                "  font-weight: 500;"
                "  text-align: left;"
                "  padding-left: 12px;"
                "  font-family: {Fonts.SYSTEM};"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.08);"
                "}"
                "QPushButton:pressed {"
                "  background: rgba(0, 0, 0, 0.12);"
                "}",
            )
            elements_layout.addWidget(elem_btn)

        panel_layout.addWidget(elements_container)

        # Chart Builder Tool
        chart_container = QFrame()
        chart_container.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border: none;"
            "  border-radius: {Dimensions.BORDER_RADIUS_LG};"
            "}",
        )
        chart_container.setGraphicsEffect(create_card_shadow())

        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        chart_layout.setSpacing(Dimensions.SPACING_MD)

        chart_title = QLabel("Chart Builder")
        chart_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        chart_layout.addWidget(chart_title)

        # Chart type selector
        chart_types = QHBoxLayout()
        chart_types.setSpacing(6)

        for chart_type in ["Bar", "Line", "Scatter"]:
            type_btn = QPushButton(chart_type)
            type_btn.setCheckable(True)
            type_btn.setChecked(chart_type == "Bar")
            type_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_STD)
            type_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: {Colors.SECONDARY_TEXT};"
                "  border: none;"
                "  border-radius: 6px;"
                "  font-size: 12px;"
                "  font-weight: 500;"
                "  font-family: {Fonts.SYSTEM};"
                "}"
                "QPushButton:checked {"
                "  background: #1D1D1F;"
                "  color: white;"
                "  font-weight: 600;"
                "}",
            )
            chart_types.addWidget(type_btn)

        chart_layout.addLayout(chart_types)

        # Data source
        source_label = QLabel("Data Source:")
        source_label.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: {Colors.SECONDARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        chart_layout.addWidget(source_label)

        from PySide6.QtWidgets import QComboBox

        source_dropdown = QComboBox()
        source_dropdown.addItems(
            [
                "Kinetic Results",
                "Cycle Statistics",
                "Custom Data",
            ],
        )
        source_dropdown.setFixedHeight(Dimensions.HEIGHT_BUTTON_STD)
        source_dropdown.setStyleSheet(
            "QComboBox {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  color: {Colors.PRIMARY_TEXT};"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 6px 10px;"
            "  font-size: 12px;"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        chart_layout.addWidget(source_dropdown)

        # Create chart button
        create_chart_btn = QPushButton("Create Chart")
        create_chart_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_LG)
        create_chart_btn.setStyleSheet(
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  font-family: {Fonts.SYSTEM};"
            "}"
            "QPushButton:hover {"
            "  background: #3A3A3C;"
            "}",
        )
        chart_layout.addWidget(create_chart_btn)

        panel_layout.addWidget(chart_container)

        # Saved Content Library
        library_container = QFrame()
        library_container.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border: none;"
            "  border-radius: {Dimensions.BORDER_RADIUS_LG};"
            "}",
        )
        library_container.setGraphicsEffect(create_card_shadow())

        library_layout = QVBoxLayout(library_container)
        library_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        library_layout.setSpacing(Dimensions.SPACING_MD)

        library_title = QLabel("Content Library")
        library_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
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
            item_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_STD)
            item_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.03);"
                "  color: {Colors.PRIMARY_TEXT};"
                "  border: none;"
                "  border-radius: 6px;"
                "  font-size: 12px;"
                "  font-weight: 400;"
                "  text-align: left;"
                "  padding-left: 12px;"
                "  font-family: {Fonts.SYSTEM};"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.06);"
                "}",
            )
            library_layout.addWidget(item_btn)

        panel_layout.addWidget(library_container, 1)

        panel_layout.addStretch()

        return panel

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
                "}",
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
                "}",
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
                "}",
            )
            self.power_btn.setToolTip(
                "Power Off Device (Ctrl+P)\nGreen = Device Connected\nClick to power off",
            )

    def _handle_power_click(self):
        """Handle power button click - connects/disconnects hardware.

        Button behavior:
        - DISCONNECTED (gray): Click to start connection → SEARCHING (yellow)
        - SEARCHING (yellow): Click to cancel search → DISCONNECTED (gray)
        - CONNECTED (green): Click to disconnect → DISCONNECTED (gray)
        """
        current_state = self.power_btn.property("powerState")
        logger.info(f"Power button clicked: current_state={current_state}")

        if current_state == "disconnected":
            # Start hardware connection
            logger.debug("Starting hardware connection...")

            # Update UI state to searching IMMEDIATELY
            self.power_btn.setProperty("powerState", "searching")
            self._update_power_button_style()

            # Show connecting indicator
            self.show_connecting_indicator(True)

            # FORCE immediate visual update (process all pending events)
            from PySide6.QtCore import QCoreApplication

            self.power_btn.repaint()  # Force immediate repaint
            QCoreApplication.processEvents()  # Process all pending UI events

            logger.debug(
                "Power button state: searching",
            )

            # Emit signal to Application layer (clean architecture)
            logger.debug("Emitting power_on_requested signal...")
            self.power_on_requested.emit()
            logger.debug("Signal emitted")

        elif current_state == "searching":
            # Button is inactive while searching - ignore clicks
            logger.debug(
                "Button clicked during search - ignoring",
            )
            return  # Do nothing while hardware search is active

        elif current_state == "connected":
            # Power OFF: Show warning dialog
            from PySide6.QtWidgets import QMessageBox

            warning = QMessageBox(self)
            warning.setWindowTitle("Power Off Device")
            warning.setIcon(QMessageBox.Icon.Warning)
            warning.setText("Are you sure you want to disconnect the device?")
            warning.setInformativeText("All hardware connections will be closed.")
            warning.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            warning.setDefaultButton(QMessageBox.StandardButton.Cancel)

            # Style the warning dialog
            warning.setStyleSheet(
                "QMessageBox {"
                "  background: {Colors.BACKGROUND_WHITE};"
                "  font-family: {Fonts.SYSTEM};"
                "}"
                "QLabel {"
                "  color: {Colors.PRIMARY_TEXT};"
                "  font-size: 13px;"
                "}"
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: {Colors.PRIMARY_TEXT};"
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
                "}",
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
                if hasattr(self, "power_off_requested"):
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

        # Show/hide connecting indicator based on state
        self.show_connecting_indicator(state == "searching")

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
            self.pause_btn.setToolTip(
                "Pause Live Acquisition\n(Click to temporarily stop data flow)",
            )
        except Exception as e:
            # Suppress Qt threading warnings that are false positives
            if "QTextDocument" not in str(e) and "different thread" not in str(e):
                raise

    def _reset_subunit_status(self) -> None:
        """Reset all subunit status indicators to 'Not Ready' state."""
        for subunit_name in ["Sensor", "Optics", "Fluidics"]:
            if subunit_name in self.sidebar.subunit_status:
                indicator = self.sidebar.subunit_status[subunit_name]["indicator"]
                status_label = self.sidebar.subunit_status[subunit_name]["status_label"]

                # Gray indicator and "Not Ready" text
                indicator.setStyleSheet(
                    "font-size: 14px;"
                    "color: {Colors.SECONDARY_TEXT};"  # Gray
                    "background: {Colors.TRANSPARENT};"
                    "font-family: {Fonts.SYSTEM};",
                )
                status_label.setText("Not Ready")
                status_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: {Colors.SECONDARY_TEXT};"  # Gray
                    "background: {Colors.TRANSPARENT};"
                    "font-family: {Fonts.SYSTEM};",
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
        self.sidebar.set_scan_state(True)  # Use encapsulated method

        # Emit signal to trigger actual hardware scan in Application
        # The Application class will handle the actual hardware manager scan
        if hasattr(self, "app") and self.app:
            self.app.hardware_mgr.scan_and_connect()
        else:
            logger.warning("No application reference - cannot trigger hardware scan")
            # Reset button state after 1 second
            QTimer.singleShot(1000, lambda: self.sidebar.set_scan_state(False))

    def _on_hardware_scan_complete(self) -> None:
        """Called when hardware scan completes - reset scan button."""
        self.sidebar.set_scan_state(False)  # Use encapsulated method
        logger.debug("Hardware scan complete - button reset")

    def _handle_add_hardware(self) -> None:
        """Handle Add Hardware button click - scan for peripheral devices only."""
        logger.info("🔌 User requested peripheral device scan (Affipump)...")

        # Check if application and kinetic manager are available
        if hasattr(self, "app") and self.app:
            if hasattr(self.app, "kinetic_mgr") and self.app.kinetic_mgr:
                try:
                    # Scan for Affipump
                    self.app.kinetic_mgr.scan_for_pump()
                    logger.info("✓ Peripheral scan initiated")
                except Exception as e:
                    logger.error(f"Failed to scan for peripherals: {e}")
                    from affilabs.ui.ui_message import error as ui_error
                    ui_error(
                        self,
                        "Peripheral Scan Error",
                        f"Failed to scan for peripheral devices:\\n\\n{e}",
                    )
            else:
                logger.warning("Kinetic manager not available - peripheral scan unavailable")
                from affilabs.ui.ui_message import warning as ui_warning
                ui_warning(
                    self,
                    "Feature Unavailable",
                    "Peripheral device scanning is not available.\\n\\n"
                    "Kinetic manager is not initialized.",
                )
        else:
            logger.warning("No application reference - cannot scan for peripherals")

    def update_hardware_status(self, status: dict[str, Any]) -> None:
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

        ctrl_type = status.get("ctrl_type")

        # Map internal names to display names
        # Valid hardware: P4SPR, P4PRO, P4PROPLUS, ezSPR, KNX, AffiPump
        # Common pairings: P4SPR+KNX, P4PRO+AffiPump, P4PROPLUS (internal pumps)
        CONTROLLER_DISPLAY_NAMES = {
            "PicoP4SPR": "P4SPR",
            "P4SPR": "P4SPR",
            "PicoP4PRO": "P4PRO",
            "P4PRO": "P4PRO",
            "P4PROPLUS": "P4PRO+",
            "PicoP4PROPLUS": "P4PRO+",
            "PicoEZSPR": "P4PRO",  # PicoEZSPR hardware = P4PRO product
            "EZSPR": "ezSPR",
            "ezSPR": "ezSPR",
        }

        KNX_DISPLAY_NAMES = {
            "KNX": "KNX",
            "KNX2": "KNX",
            "PicoKNX2": "KNX",
        }

        # Controller (P4SPR, P4PRO, ezSPR)
        if ctrl_type:
            display_name = CONTROLLER_DISPLAY_NAMES.get(ctrl_type)
            if display_name:
                devices.append(display_name)
            else:
                # Unknown controller - log warning but don't display
                logger.warning(
                    f"⚠️ Unknown controller type '{ctrl_type}' - not displayed in Hardware Connected",
                )

        # Kinetic Controller (KNX)
        knx_type = status.get("knx_type")
        if knx_type:
            display_name = KNX_DISPLAY_NAMES.get(knx_type)
            if display_name:
                devices.append(display_name)
            else:
                # Unknown kinetic type - log warning but don't display
                logger.warning(
                    f"⚠️ Unknown kinetic type '{knx_type}' - not displayed in Hardware Connected",
                )

        # Pump (AffiPump) - only show if external pump actually connected
        # Don't show "AffiPump" for P4PROPLUS internal pumps
        if status.get("pump_connected"):
            # Check if this is external AffiPump or P4PROPLUS internal pumps
            # P4PROPLUS sets pump_connected=True but shouldn't display as "AffiPump"
            is_p4proplus_internal = ctrl_type in ["P4PROPLUS", "PicoP4PROPLUS"]
            if not is_p4proplus_internal:
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

        # Show "Add Hardware" button only when core module is connected (ctrl_type exists)
        # This allows adding peripherals like Affipump after core connection
        self.sidebar.add_hardware_btn.setVisible(bool(ctrl_type))

        # Update subunit readiness based on actual verification
        self._update_subunit_readiness_from_status(status)

        # Update operation mode availability based on hardware
        logger.debug(f"📥 update_hardware_status received: flow_calibrated={status.get('flow_calibrated', 'NOT SET')}")
        self._update_operation_modes(status)

    def _update_subunit_readiness_from_status(self, status: dict[str, Any]) -> None:
        """Update subunit readiness based on hardware verification results."""
        # Sensor readiness
        if "sensor_ready" in status:
            logger.info(f"[UI] Setting Sensor readiness: {status['sensor_ready']}")
            self._set_subunit_status("Sensor", status["sensor_ready"])

        # Optics readiness
        if "optics_ready" in status:
            optics_ready = status["optics_ready"]
            logger.info(f"[UI] Setting Optics readiness: {optics_ready}")
            optics_details = {
                "failed_channels": status.get("optics_failed_channels", []),
                "maintenance_channels": status.get("optics_maintenance_channels", []),
            }
            self._set_subunit_status("Optics", optics_ready, details=optics_details)

        # Fluidics readiness - only show for flow-capable controllers
        if "fluidics_ready" in status:
            fluidics_ready = status["fluidics_ready"]
            logger.info(f"[UI] Setting Fluidics readiness: {fluidics_ready}")
            logger.info(f"[UI] Full status dict keys: {list(status.keys())}")
            logger.info(f"[UI] pump_connected={status.get('pump_connected')}, flow_calibrated={status.get('flow_calibrated')}")
            self._set_subunit_status("Fluidics", fluidics_ready)
            # Show the fluidics row
            self._set_subunit_visibility("Fluidics", True)
        else:
            # Hide the fluidics row for static-only controllers (P4SPR)
            self._set_subunit_visibility("Fluidics", False)

    def _set_subunit_visibility(self, subunit_name: str, visible: bool) -> None:
        """Show or hide a subunit status row.

        Args:
            subunit_name: Name of subunit (Sensor, Optics, Fluidics)
            visible: True to show, False to hide
        """
        if subunit_name in self.sidebar.subunit_status:
            # Get the container widget for the entire row
            container = self.sidebar.subunit_status[subunit_name].get("container")
            if container:
                container.setVisible(visible)

    def _set_subunit_status(
        self,
        subunit_name: str,
        is_ready: bool,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Set the status of a specific subunit.

        Args:
            subunit_name: Name of subunit (Sensor, Optics, Fluidics)
            is_ready: True if ready, False otherwise
            details: Optional dict with 'failed_channels' and 'maintenance_channels' for Optics

        """
        if subunit_name in self.sidebar.subunit_status:
            indicator = self.sidebar.subunit_status[subunit_name]["indicator"]
            status_label = self.sidebar.subunit_status[subunit_name]["status_label"]

            if is_ready:
                # Green indicator and "Ready" text
                indicator.setStyleSheet(
                    "font-size: 14px;"
                    "color: #34C759;"  # Green
                    "background: {Colors.TRANSPARENT};"
                    "font-family: {Fonts.SYSTEM};",
                )
                status_label.setText("Ready")
                status_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #34C759;"  # Green
                    "background: {Colors.TRANSPARENT};"
                    "font-family: {Fonts.SYSTEM};",
                )
                # Clear optics warning if it was active
                if subunit_name == "Optics" and hasattr(self, "_optics_warning_active"):
                    self._clear_optics_warning()
            else:
                # Red indicator for Not Ready (all subunits use red for consistency)
                color = "#FF3B30"
                indicator.setStyleSheet(
                    "font-size: 14px;"
                    f"color: {color};"
                    "background: {Colors.TRANSPARENT};"
                    "font-family: {Fonts.SYSTEM};",
                )
                status_label.setText("Not Ready")
                status_label.setStyleSheet(
                    "font-size: 12px;"
                    f"color: {color};"
                    "background: {Colors.TRANSPARENT};"
                    "font-family: {Fonts.SYSTEM};",
                )
                # Store optics status details for warning message
                if subunit_name == "Optics" and details:
                    self._optics_status_details = details

            from affilabs.utils.logger import logger

            logger.info(f"{subunit_name}: {'Ready' if is_ready else 'Not Ready'}")

    def _set_optics_warning(self) -> None:
        """Apply light red background to live sensorgram when proceeding with unready optics."""
        # Only set warning if we actually have optics issues (not just unverified)
        if (
            not hasattr(self, "_optics_status_details")
            or not self._optics_status_details
        ):
            from affilabs.utils.logger import logger

            logger.debug(
                "_set_optics_warning called but no optics issues detected - skipping red background",
            )
            return

        if hasattr(self, "full_timeline_graph") and self.full_timeline_graph:
            self.full_timeline_graph.setBackground("#FFE5E5")  # Light red
            self._optics_warning_active = True

            # Log warning with details
            if self._optics_status_details:
                failed = self._optics_status_details.get("failed_channels", [])
                maintenance = self._optics_status_details.get(
                    "maintenance_channels",
                    [],
                )

                if failed or maintenance:  # Only warn if there are actual problems
                    failed_str = (
                        ", ".join([ch.upper() for ch in failed]) if failed else "none"
                    )
                    maint_str = (
                        ", ".join([ch.upper() for ch in maintenance])
                        if maintenance
                        else "none"
                    )

                    from affilabs.utils.logger import logger

                    logger.warning(
                        f"⚠️ Optics NOT ready: calibration failed for channels [{failed_str}], maintenance required for channels [{maint_str}]",
                    )
                    logger.warning(
                        "   Live sensorgram background set to light red - please resolve optics issues",
                    )

    def _clear_optics_warning(self) -> None:
        """Clear light red background from live sensorgram when optics become ready."""
        if (
            hasattr(self, "full_timeline_graph")
            and self.full_timeline_graph
            and self._optics_warning_active
        ):
            self.full_timeline_graph.setBackground("#FFFFFF")  # White
            self._optics_warning_active = False
            self._optics_status_details = None

            from affilabs.utils.logger import logger

            logger.info("✅ Optics ready - sensorgram background restored to normal")

    def _update_operation_modes(self, status: dict[str, Any]) -> None:
        """Update available operation modes based on hardware type."""
        ctrl_type = status.get("ctrl_type", "")
        has_pump = status.get("pump_connected", False)
        detector_ready = status.get("sensor_ready", False)
        pcb_ready = status.get("optics_ready", False)

        from affilabs.utils.logger import logger

        # Determine if static mode should be available
        # Static mode is available if we have detector AND PCB (regardless of pump)
        static_available = detector_ready and pcb_ready

        # Flow mode requires calibration to be completed (not just pump detection)
        # During initial connection, flow indicators stay grey until calibration completes
        # After calibration, flow_available will be set based on pump presence
        # For P4PROPLUS (internal pumps) and other flow controllers, still needs calibration
        flow_available = status.get("flow_calibrated", False)  # Enabled after calibration completes

        logger.info(f"🔄 Operation modes update:")
        logger.info(f"   ctrl_type={ctrl_type}")
        logger.info(f"   pump_connected={has_pump}")
        logger.info(f"   flow_calibrated={status.get('flow_calibrated', 'NOT IN STATUS DICT')}")
        logger.info(f"   flow_available={flow_available} (THIS CONTROLS GREEN/GRAY)")
        logger.info(f"   static_available={static_available}")

        # P4SPR static device - only Static mode
        if ctrl_type in ["P4SPR", "PicoP4SPR"]:
            logger.info(f"P4SPR device detected - Static mode: {'✅ Available' if static_available else '❌ Disabled'}")
            if has_pump:
                logger.info("Pump detected - Flow mode also available")
            else:
                logger.info("No pump - Flow mode disabled")

        # EZSPR or other devices
        elif ctrl_type in ["EZSPR", "PicoEZSPR"]:
            logger.info(f"EZSPR device detected - Static mode: {'✅ Available' if static_available else '❌ Disabled'}, Flow mode: {'✅ Available' if flow_available else '❌ Disabled'}")

        # Update UI indicators
        if hasattr(self.sidebar, "set_operation_mode_availability"):
            self.sidebar.set_operation_mode_availability(static_available, flow_available)
            logger.debug(f"✓ Called set_operation_mode_availability(static={static_available}, flow={flow_available})")

    def _update_scan_button_style(self) -> None:
        """Update scan button style based on scanning state.

        DEPRECATED: State management moved to sidebar.set_scan_state().
        Kept for backward compatibility only.
        """
        is_scanning = self.sidebar.scan_btn.property("scanning")
        self.sidebar.set_scan_state(is_scanning)

    def _handle_debug_log_download(self) -> None:
        """Handle debug log download button click."""
        import datetime

        from PySide6.QtWidgets import QFileDialog, QMessageBox

        # Generate filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"AffiLabs_debug_log_{timestamp}.txt"

        # Open file save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Debug Log",
            default_filename,
            "Log Files (*.txt *.log);;All Files (*.*)",
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
                with open(file_path, "w", encoding="utf-8") as f:
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
                    "  background: {Colors.BACKGROUND_WHITE};"
                    "  font-family: {Fonts.SYSTEM};"
                    "}"
                    "QLabel {"
                    "  color: {Colors.PRIMARY_TEXT};"
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
                    "}",
                )
                msg.exec()

                logger.info(f"Debug log saved to: {file_path}")

            except Exception as e:
                # Show error message
                error_msg = QMessageBox(self)
                error_msg.setWindowTitle("Error")
                error_msg.setIcon(QMessageBox.Icon.Critical)
                error_msg.setText("Failed to save debug log")
                error_msg.setInformativeText(f"Error: {e!s}")
                error_msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                error_msg.setStyleSheet(
                    "QMessageBox {"
                    "  background: {Colors.BACKGROUND_WHITE};"
                    "}"
                    "QPushButton {"
                    "  background: #FF3B30;"
                    "  color: white;"
                    "  border: none;"
                    "  border-radius: 6px;"
                    "  padding: 6px 16px;"
                    "}",
                )
                error_msg.exec()

                logger.error(f"Error saving debug log: {e}")

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

        if is_recording:
            # Update button tooltip
            display_name = Path(filename).name if filename else "data.csv"
            self.record_btn.setToolTip(
                f"Stop Recording\n(Recording to: {display_name})",
            )

            # Recording indicator - update if it exists
            if hasattr(self, 'rec_status_dot'):
                self.rec_status_dot.setStyleSheet(
                    "QLabel {"
                    "  color: #FF3B30;"
                    "  font-size: 16px;"
                    "  background: {Colors.TRANSPARENT};"
                    "}",
                )

            if hasattr(self, 'rec_status_text'):
                display_name = Path(filename).name if filename else "data.csv"
                self.rec_status_text.setText(f"Recording to: {display_name}")
                self.rec_status_text.setStyleSheet(
                    "QLabel {"
                    "  font-size: 12px;"
                    "  color: #FF3B30;"
                    "  background: {Colors.TRANSPARENT};"
                    "  font-family: {Fonts.SYSTEM};"
                    "  font-weight: 600;"
                    "}",
                )

            if hasattr(self, 'recording_indicator'):
                self.recording_indicator.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(255, 59, 48, 0.1);"
                    "  border: 1px solid rgba(255, 59, 48, 0.3);"
                    "  border-radius: 6px;"
                    "}",
                )
        else:
            # Update button tooltip back to viewing mode
            self.record_btn.setToolTip(
                "Start Recording\n(Currently viewing - not saved)",
            )

            # Update recording indicator back to viewing mode (if exists)
            if hasattr(self, 'rec_status_dot'):
                self.rec_status_dot.setStyleSheet(
                    "QLabel {"
                    "  color: {Colors.SECONDARY_TEXT};"
                    "  font-size: 16px;"
                    "  background: {Colors.TRANSPARENT};"
                    "}",
                )

            if hasattr(self, 'recording_indicator'):
                self.recording_indicator.setStyleSheet(
                    "QFrame {"
                "  background: rgba(0, 0, 0, 0.04);"
                "  border-radius: 6px;"
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
        if self.device_config is None:
            return

        # Check if maintenance widgets exist yet (UI might not be fully initialized)
        if not hasattr(self, "hours_value"):
            return

        try:
            import datetime

            # Update operation hours
            led_hours = self.device_config.config["maintenance"]["led_on_hours"]
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
                    "background: {Colors.TRANSPARENT};"
                    "font-weight: {Fonts.WEIGHT_BOLD};"
                    "margin-top: 6px;"
                    "font-family: {Fonts.SYSTEM};",
                )
            else:
                self.next_maintenance_value.setStyleSheet(
                    "font-size: 13px;"
                    "color: #FF9500;"  # Orange for scheduled
                    "background: {Colors.TRANSPARENT};"
                    "font-weight: 600;"
                    "margin-top: 6px;"
                    "font-family: {Fonts.SYSTEM};",
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

        logger.info(
            f"Device powered on at {self.last_powered_on.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        self._update_maintenance_display()

    def _on_start_queued_run(self):
        """Start executing queued cycles."""
        if not self.cycle_queue:
            logger.warning("No cycles in queue to start")
            return

        # Execute first cycle from queue
        cycle_data = self.cycle_queue[0]  # Don't pop yet, wait for completion
        cycle_data["state"] = "running"

        logger.info(
            f"🚀 Starting queued cycle: {cycle_data['type']} - {cycle_data['notes']}",
        )

        # Update display to show running state
        self._update_queue_display()

        # Hide start run button while cycle is running
        self.sidebar.start_run_btn.setVisible(False)

        # Trigger the actual acquisition start through the app
        if hasattr(self, "app") and self.app:
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
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.cycle_queue.clear()
            logger.info("Queue cleared")

            # Update UI
            self._update_queue_display()
            self.sidebar.update_queue_status(0)

    def _on_expand_queue(self):
        """Expand queue capacity by 5 cycles and resize the table."""
        # Increase max queue size
        self.max_queue_size += 5

        # Resize the summary table
        current_rows = self.sidebar.summary_table.rowCount()
        new_rows = current_rows + 5
        self.sidebar.summary_table.setRowCount(new_rows)

        # Initialize new rows with empty items
        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtGui import QColor

        for row in range(current_rows, new_rows):
            for col in range(5):  # 5 columns: State, Type, Duration, Start, Notes
                empty_item = QTableWidgetItem("")
                empty_item.setBackground(QColor(255, 255, 255))
                self.sidebar.summary_table.setItem(row, col, empty_item)

        # Update table height (40px per row approximately)
        new_height = min(new_rows * 40 + 40, 600)  # Cap at 600px
        self.sidebar.summary_table.setMaximumHeight(new_height)

        # Update footer label
        if hasattr(self.sidebar, 'queue_size_label'):
            self.sidebar.queue_size_label.setText(f"Showing last {new_rows} cycles")

        logger.info(f"✓ Queue expanded: capacity now {self.max_queue_size}, table shows {new_rows} rows")

        # Re-enable Add to Queue button if it was disabled
        if hasattr(self, 'add_to_queue_btn'):
            self.add_to_queue_btn.setEnabled(True)

    def open_full_cycle_table(self):
        """Open the full cycle data table in the Edits tab."""
        # Find the Edits tab and switch to it
        for i in range(self.sidebar.tabs.count()):
            if self.sidebar.tabs.tabText(i) == "Edits":
                self.sidebar.tabs.setCurrentIndex(i)
                break

    def add_cycle_to_queue(self):
        """Add current cycle form values to the queue."""
        # DISABLED: Queue size limit removed - no longer needed
        # if len(self.cycle_queue) >= self.max_queue_size:
        #     QMessageBox.warning(
        #         self,
        #         "Queue Full",
        #         f"Maximum queue size ({self.max_queue_size}) reached. Start a cycle to free up space.",
        #     )
        #     return

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
            "length_minutes": cycle_minutes,
        }

        self.cycle_queue.append(cycle_data)
        self._update_queue_display()

        # Disable Add to Queue if at capacity
        if len(self.cycle_queue) >= self.max_queue_size:
            if hasattr(self, 'add_to_queue_btn'):
                self.add_to_queue_btn.setEnabled(False)

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
            # No queue items - use current form values
            # TODO: Extract form values and create cycle
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

        if hasattr(self.sidebar, "countdown_label"):
            self.sidebar.countdown_label.setText(f"{minutes:02d}:{seconds:02d}")

        # Stop timer when countdown reaches zero
        if remaining <= 0:
            self.cycle_countdown_timer.stop()
            self.cycle_start_time = None

    def _on_export_data(self):
        """Handle export data button click - emit signal with export configuration."""
        export_config = self._get_export_config()
        self.export_requested.emit(export_config)

    def _on_send_to_edits_clicked(self):
        """Transfer live recording data to Edits tab for review and modification."""
        from PySide6.QtWidgets import QMessageBox

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

    def _refresh_intelligence_bar(self):
        """Refresh the Intelligence Bar display with current system diagnostics."""
        try:
            # Get system intelligence instance and run diagnosis
            intelligence = get_system_intelligence()
            system_state, active_issues = intelligence.diagnose_system()

            # Determine operational context for more useful messaging
            is_acquiring = hasattr(self, 'app') and hasattr(self.app, 'data_mgr') and getattr(self.app.data_mgr, '_acquiring', False)
            is_calibrated = hasattr(self, 'app') and hasattr(self.app, 'data_mgr') and getattr(self.app.data_mgr, 'calibrated', False)
            queue_count = len(self.segment_queue) if hasattr(self, 'segment_queue') else 0

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
                    message_text = "⚠ Cal needed"
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

            # Update the UI labels
            self.sidebar.intel_status_label.setText(status_text)
            self.sidebar.intel_status_label.setStyleSheet(
                f"font-size: 12px;"
                f"color: {status_color};"
                f"background: {Colors.TRANSPARENT};"
                f"font-weight: {Fonts.WEIGHT_BOLD};"
                f"font-family: {Fonts.SYSTEM};",
            )

            self.sidebar.intel_message_label.setText(message_text)
            self.sidebar.intel_message_label.setStyleSheet(
                f"font-size: 12px;"
                f"color: {message_color};"
                f"background: {Colors.TRANSPARENT};"
                f"font-weight: 600;"
                f"font-family: {Fonts.SYSTEM};",
            )

        except Exception as e:
            logger.error(f"Error refreshing intelligence bar: {e}")

    def _update_queue_display(self):
        """Update the summary table to reflect current queue state."""
        if not hasattr(self.sidebar, 'summary_table'):
            return

        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QTableWidgetItem

        # Get current table size (may have been expanded)
        max_rows = self.sidebar.summary_table.rowCount()

        # Clear table
        for row in range(max_rows):
            for col in range(4):
                self.sidebar.summary_table.setItem(row, col, QTableWidgetItem(""))
                self.sidebar.summary_table.item(row, col).setBackground(QColor(255, 255, 255))

        # Populate with queue data (up to table capacity)
        display_count = min(len(self.cycle_queue), max_rows)
        for row, cycle in enumerate(self.cycle_queue[:display_count]):
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
            elif state == "running":
                state_text = "🏃 Running"
                state_color = QColor(255, 243, 205)  # Light yellow/amber
            elif state == "completed":
                state_text = "✓ Done"
                state_color = QColor(232, 245, 233)  # Light green

            # Set cell values
            state_item = QTableWidgetItem(state_text)
            state_item.setBackground(state_color)
            self.sidebar.summary_table.setItem(row, 0, state_item)

            self.sidebar.summary_table.setItem(row, 1, QTableWidgetItem(cycle["type"]))
            self.sidebar.summary_table.setItem(row, 2, QTableWidgetItem(cycle["start"]))
            self.sidebar.summary_table.setItem(row, 3, QTableWidgetItem(cycle["notes"]))

            # Apply background color to entire row
            for col in range(1, 4):
                self.sidebar.summary_table.item(row, col).setBackground(state_color)

    def _on_unit_changed(self, checked: bool):
        """Toggle between RU and nm units."""
        # This will be connected to main_simplified handler
        if checked and self.ru_btn.isChecked():
            logger.info("Unit changed to RU")
        elif checked and self.nm_btn.isChecked():
            logger.info("Unit changed to nm")

    def _load_current_settings(self, show_warnings: bool = True):
        """Load current hardware settings into Hardware Configuration.

        Loads:
        - Servo positions (S/P) from device_config (immutable, set at init)
        - LED brightness (A/B/C/D) preferring calibrated P-mode final brightness,
          falling back to current hardware state or device config

        Args:
            show_warnings: If True, show warning dialogs when config unavailable.
                          Set to False during UI init to avoid spurious warnings.
        """
        try:
            if not self.device_config:
                # Silent return during init; only warn if explicitly requested
                if show_warnings:
                    logger.warning(
                        "Device config not available - cannot load current settings",
                    )
                    QMessageBox.warning(
                        self,
                        "Settings Not Available",
                        "Device configuration is not available. Please connect to hardware first.",
                    )
                return

            # Load servo positions from device_config (set at hardware init)
            servo_positions = self.device_config.get_servo_positions()
            s_pos = servo_positions.get("s", 0)
            p_pos = servo_positions.get("p", 0)

            # Prefer calibrated P-mode final intensities when available
            led_intensities = {"a": 0, "b": 0, "c": 0, "d": 0}
            source = ""
            try:
                if hasattr(self, "app") and self.app and hasattr(self.app, "data_mgr") and self.app.data_mgr:
                    cd = getattr(self.app.data_mgr, "calibration_data", None)
                    if cd and hasattr(cd, "p_mode_intensities") and cd.p_mode_intensities:
                        led_intensities = dict(cd.p_mode_intensities)
                        source = "calibration"
            except Exception as e:
                logger.warning(f"Failed to read calibrated P-mode brightness: {e}")

            # Fallback to current hardware or device config
            if not source:
                if self.hardware_mgr and self.hardware_mgr.ctrl:
                    try:
                        led_intensities = self.hardware_mgr.ctrl.get_all_led_intensities()
                        source = "hardware"
                    except Exception as e:
                        logger.warning(
                            f"Failed to query LED brightness from hardware: {e} - using config values",
                        )
                        led_intensities = self.device_config.get_led_intensities()
                        source = "config"
                else:
                    logger.info("Hardware not connected - loading LED brightness from config")
                    led_intensities = self.device_config.get_led_intensities()
                    source = "config"

            # Populate UI fields
            self.sidebar.load_hardware_settings(
                s_pos=s_pos,
                p_pos=p_pos,
                led_a=led_intensities.get("a", 0),
                led_b=led_intensities.get("b", 0),
                led_c=led_intensities.get("c", 0),
                led_d=led_intensities.get("d", 0),
            )

            logger.info(
                f"✓ Loaded current settings: S={s_pos}°, P={p_pos}°, LEDs={led_intensities} (source={source})",
            )

            # Initialize pipeline selector to current configuration
            self._init_pipeline_selector()

        except Exception as e:
            logger.error(f"Error loading current settings: {e}")
            QMessageBox.critical(
                self,
                "Error Loading Settings",
                f"Failed to load current settings: {e!s}",
            )

    def eventFilter(self, obj, event):
        """Event filter to detect Control+10-click on advanced settings button."""
        if (
            obj == self.sidebar.advanced_settings_btn
            and event.type() == QEvent.Type.MouseButtonPress
        ):
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
        os.environ["AFFILABS_DEV"] = "1"

        # Show confirmation message
        QMessageBox.information(
            self,
            "Advanced Parameters Unlocked",
            "Advanced parameters tab and developer mode are now enabled for 60 minutes.",
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
        if "AFFILABS_DEV" in os.environ:
            del os.environ["AFFILABS_DEV"]

        logger.info("Advanced parameters and dev mode locked after timeout")

    def open_advanced_settings(self):
        """Open the advanced settings dialog."""
        try:
            dialog = AdvancedSettingsDialog(
                self,
                unlocked=getattr(self, "advanced_params_unlocked", False),
            )
        except Exception as e:
            logger.error(f"Failed to create AdvancedSettingsDialog: {e}")
            return

        # Load current settings
        if hasattr(dialog, "ru_btn"):
            dialog.ru_btn.setChecked(
                self.ru_btn.isChecked() if hasattr(self, "ru_btn") else True,
            )
        if hasattr(dialog, "nm_btn"):
            dialog.nm_btn.setChecked(
                self.nm_btn.isChecked() if hasattr(self, "nm_btn") else False,
            )

        # Load calibration parameters if available
        if hasattr(self, "app") and self.app and hasattr(self.app, "data_mgr") and self.app.data_mgr:
            calibration_data = getattr(self.app.data_mgr, "calibration_data", None)
            if calibration_data:
                dialog.load_calibration_params(calibration_data)
                logger.info("✓ Loaded calibration parameters into Advanced Settings")

        # Load device info if available
        if self.device_config:
            device_serial = self.device_config.get_serial_number() if hasattr(self.device_config, "get_serial_number") else "Not detected"
            dialog.load_device_info(serial=device_serial)

        # Load pump corrections if available
        if hasattr(self, "app") and self.app and hasattr(self.app, "hardware_mgr"):
            if hasattr(dialog, "load_pump_corrections"):
                dialog.load_pump_corrections(self.app.hardware_mgr)

        # Show dialog
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Apply settings
            if hasattr(self, "ru_btn"):
                self.ru_btn.setChecked(dialog.ru_btn.isChecked())
                self.nm_btn.setChecked(dialog.nm_btn.isChecked())

            logger.info("Advanced settings applied")

    def _toggle_polarizer_mode(self):
        """Toggle polarizer between S and P modes."""
        try:
            if not hasattr(self, "app") or not self.app:
                logger.warning("Application not connected")
                return

            if not self.app.hardware_mgr or not self.app.hardware_mgr.ctrl:
                logger.warning("Controller not connected")
                return

            ctrl = self.app.hardware_mgr.ctrl

            # Get current mode from button text
            current_text = self.polarizer_toggle_btn.text()

            if "S" in current_text:
                # Currently in S, switch to P
                ctrl.set_mode("p")
                self.polarizer_toggle_btn.setText("Position: P")
                logger.info("✅ Switched to P-mode")
            else:
                # Currently in P, switch to S
                ctrl.set_mode("s")
                self.polarizer_toggle_btn.setText("Position: S")
                logger.info("✅ Switched to S-mode")

        except Exception as e:
            logger.error(f"Failed to toggle polarizer: {e}")
            QMessageBox.warning(self, "Error", f"Failed to toggle polarizer: {e}")

    def _apply_settings(self):
        """Apply polarizer and LED settings from the Settings tab.

        ARCHITECTURE: Signal-based communication (UI → Application)
        UI validates input and emits signal with settings dict.
        Application layer handles business logic (hardware access, config save).
        """
        try:
            logger.info("🔧 UI: Parsing settings...")

            # Get polarizer positions
            s_pos_text = self.s_position_input.text()
            p_pos_text = self.p_position_input.text()

            # Get LED intensities
            led_a_text = self.channel_a_input.text()
            led_b_text = self.channel_b_input.text()
            led_c_text = self.channel_c_input.text()
            led_d_text = self.channel_d_input.text()

            # Parse and validate
            try:
                s_pos = int(s_pos_text) if s_pos_text else None
                p_pos = int(p_pos_text) if p_pos_text else None
                led_a = int(led_a_text) if led_a_text else None
                led_b = int(led_b_text) if led_b_text else None
                led_c = int(led_c_text) if led_c_text else None
                led_d = int(led_d_text) if led_d_text else None
            except ValueError as e:
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    f"Please enter valid integers: {e}",
                )
                return

            # Validate ranges
            if s_pos is not None and not (0 <= s_pos <= 255):
                QMessageBox.warning(self, "Invalid Range", "S position must be 0-255")
                return
            if p_pos is not None and not (0 <= p_pos <= 255):
                QMessageBox.warning(self, "Invalid Range", "P position must be 0-255")
                return

            for led_val, name in [
                (led_a, "A"),
                (led_b, "B"),
                (led_c, "C"),
                (led_d, "D"),
            ]:
                if led_val is not None and not (0 <= led_val <= 255):
                    QMessageBox.warning(
                        self,
                        "Invalid Range",
                        f"LED {name} must be 0-255",
                    )
                    return

            # Build settings dict (UI layer responsibility: parse and validate)
            settings = {
                "s_pos": s_pos,
                "p_pos": p_pos,
                "led_a": led_a,
                "led_b": led_b,
                "led_c": led_c,
                "led_d": led_d,
            }

            # Emit signal - Application layer handles business logic
            # This respects HAL architecture: UI → Application → Hardware
            logger.info("🔧 UI: Emitting apply_led_settings_requested signal")
            self.apply_led_settings_requested.emit(settings)
            logger.info("✅ Settings saved to device config")

            # Note: Message boxes removed - visual feedback now via button style change only
            # LED brightness updates are now live (no need for confirmation dialogs)

        except Exception as e:
            logger.error(f"❌ Failed to apply settings: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Failed to apply settings: {e}")

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
            self.baseline_capture_btn.setText("🔴 Record 5-Min Baseline Data")
            self.baseline_capture_btn.setStyleSheet(
                "QPushButton {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF3B30, stop:1 #E02020);"
                "  color: white;"
                "  border: none;"
                "  border-radius: 8px;"
                "  padding: 8px 16px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  font-family: {Fonts.SYSTEM};"
                "}"
                "QPushButton:hover {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF4D42, stop:1 #F03030);"
                "}"
                "QPushButton:pressed {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E02020, stop:1 #C01818);"
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

        # Connect keyboard shortcuts
        from PySide6.QtGui import QKeySequence, QShortcut

        power_shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        power_shortcut.activated.connect(self._handle_power_click)

        # Demo data loader (Ctrl+Shift+D) for promotional screenshots
        demo_data_shortcut = QShortcut(QKeySequence("Ctrl+Shift+D"), self)
        demo_data_shortcut.activated.connect(self._load_demo_data)

        # Channel selection shortcuts (Alt+A, Alt+B, Alt+C, Alt+D)
        for ch_idx, ch_letter in enumerate(['A', 'B', 'C', 'D']):
            shortcut = QShortcut(QKeySequence(f"Alt+{ch_letter}"), self)
            shortcut.activated.connect(
                lambda idx=ch_idx: self._on_curve_clicked(idx)
            )

        # Connect cycle management buttons
        # NOTE: start_cycle_btn also connected in main-simplified.py for acquisition start
        # This handler manages experiment cycle queue (different responsibility)
        self.sidebar.start_cycle_btn.clicked.connect(self.start_cycle)
        self.sidebar.add_to_queue_btn.clicked.connect(self.add_cycle_to_queue)
        self.sidebar.start_run_btn.clicked.connect(self._on_start_queued_run)
        self.sidebar.clear_queue_btn.clicked.connect(self._on_clear_queue)
        self.sidebar.expand_queue_btn.clicked.connect(self._on_expand_queue)
        self.sidebar.open_table_btn.clicked.connect(self.open_full_cycle_table)

        # Connect export buttons
        self.sidebar.export_data_btn.clicked.connect(self._on_export_data)
        self.sidebar.send_to_edits_btn.clicked.connect(self._on_send_to_edits_clicked)

        # Connect settings tab controls
        self.sidebar.advanced_settings_btn.clicked.connect(self.open_advanced_settings)
        self.sidebar.apply_settings_btn.clicked.connect(self._apply_settings)
        self.sidebar.polarizer_toggle_btn.clicked.connect(self._toggle_polarizer_mode)

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

            # CRITICAL: Always call application cleanup to ensure:
            # 1. LEDs are turned off
            # 2. Valves are powered off (prevent overheating)
            # 3. Pumps are stopped
            # NO EXIT PATH bypasses this graceful shutdown
            if app_instance and hasattr(app_instance, 'close'):
                logger.info("🔒 Triggering graceful hardware shutdown...")
                app_instance.close()
                logger.info("✓ Hardware shutdown complete")

            devices_to_unplug = []
            if app_instance and hasattr(app_instance, 'hardware_mgr') and app_instance.hardware_mgr:
                hw_mgr = app_instance.hardware_mgr
                if hasattr(hw_mgr, 'controller') and hw_mgr.controller is not None:
                    controller_name = getattr(hw_mgr.controller, 'name', 'Controller')
                    devices_to_unplug.append(controller_name)
                if hasattr(hw_mgr, 'pump') and hw_mgr.pump is not None:
                    devices_to_unplug.append('AffiPump')
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

    def add_cycle_to_table(self, cycle_data: dict):
        """Add a single completed cycle to the cycle data table during live acquisition.
        
        CRITICAL: This method should ONLY be called when a cycle COMPLETES,
        NOT when cycles are added to the queue. The Cycle Data Table shows
        COMPLETED cycles only, not queued/pending cycles.
        
        Args:
            cycle_data: Dictionary containing cycle information from Cycle.to_export_dict()
        """
        from PySide6.QtWidgets import QTableWidgetItem, QComboBox, QDoubleSpinBox
        from affilabs.utils.logger import logger
        
        logger.info(f"📝 Adding COMPLETED cycle to table: {cycle_data.get('type', 'Unknown')}")
        
        try:
            # Verify edits_tab exists
            if not hasattr(self, 'edits_tab'):
                logger.error("❌ CRITICAL: edits_tab does NOT exist on main_window! Cannot add cycle to table.")
                logger.error(f"   main_window attributes: {dir(self)}")
                return
            
            # Verify cycle_data_table exists
            if not hasattr(self.edits_tab, 'cycle_data_table'):
                logger.error("❌ CRITICAL: cycle_data_table does NOT exist on edits_tab! Cannot add cycle.")
                logger.error(f"   edits_tab attributes: {dir(self.edits_tab)}")
                return
            
            cycle_table = self.edits_tab.cycle_data_table
            
            logger.debug(f"✓ Cycle table found, current rows: {cycle_table.rowCount()}")
                
            # Initialize type counter if it doesn't exist
            if not hasattr(self, '_cycle_type_counts'):
                self._cycle_type_counts = {}
                
            # Get current row count (where we'll add the new row)
            row_idx = cycle_table.rowCount()
            cycle_table.insertRow(row_idx)
            
            # Get cycle type and format with numbering
            cycle_type = cycle_data.get('type', 'Unknown')
            
            # Abbreviate "Concentration" to "Conc."
            if cycle_type.lower() in ('concentration', 'conc', 'conc.'):
                cycle_type = 'Conc.'
                
            # Count this type occurrence
            if cycle_type not in self._cycle_type_counts:
                self._cycle_type_counts[cycle_type] = 0
            self._cycle_type_counts[cycle_type] += 1
            
            # Format type with number
            type_with_number = f"{cycle_type} {self._cycle_type_counts[cycle_type]}"
            
            # Column 0: Type
            cycle_table.setItem(row_idx, 0, QTableWidgetItem(type_with_number))
            
            # Column 1: Duration (minutes)
            duration = cycle_data.get('duration_minutes', cycle_data.get('length_minutes', ''))
            if isinstance(duration, (int, float)):
                duration = f"{duration:.2f}"
            cycle_table.setItem(row_idx, 1, QTableWidgetItem(str(duration)))
            
            # Column 2: Start time (seconds)
            start_time = cycle_data.get('start_time_sensorgram', cycle_data.get('sensorgram_time', ''))
            if isinstance(start_time, (int, float)):
                start_time = f"{start_time:.2f}"
            cycle_table.setItem(row_idx, 2, QTableWidgetItem(str(start_time)))
            
            # Column 3: Concentration value
            # Handle both single concentration_value and multi-channel concentrations dict
            if cycle_data.get('concentrations'):
                # Multi-channel concentrations - format as "A:100, B:50"
                conc_dict = cycle_data['concentrations']
                if isinstance(conc_dict, dict):
                    conc_parts = [f"{ch}:{val}" for ch, val in sorted(conc_dict.items())]
                    conc_value = ', '.join(conc_parts)
                else:
                    conc_value = str(conc_dict)
            else:
                # Single concentration value
                conc_value = cycle_data.get('concentration_value', '')
                if isinstance(conc_value, (int, float)):
                    conc_value = f"{conc_value:.2f}"
            cycle_table.setItem(row_idx, 3, QTableWidgetItem(str(conc_value)))
            
            # Column 4: Concentration units (use 'units' field if available, fallback to 'concentration_units')
            conc_units = cycle_data.get('units', cycle_data.get('concentration_units', ''))
            cycle_table.setItem(row_idx, 4, QTableWidgetItem(str(conc_units)))
            
            # Column 5: Notes (include cycle_id for tracking)
            notes = cycle_data.get('note', cycle_data.get('notes', ''))
            cycle_id = cycle_data.get('cycle_id', '')
            if cycle_id:
                notes_display = f"[ID:{cycle_id}] {notes}" if notes else f"[ID:{cycle_id}]"
            else:
                notes_display = notes
            cycle_table.setItem(row_idx, 5, QTableWidgetItem(str(notes_display)))
            
            # Column 6: Delta SPR
            delta_spr = cycle_data.get('delta_spr', '')
            if isinstance(delta_spr, (int, float)):
                delta_spr_text = f"{delta_spr:.1f}"
            else:
                delta_spr_text = str(delta_spr) if delta_spr else ''
            cycle_table.setItem(row_idx, 6, QTableWidgetItem(delta_spr_text))
            
            # Column 7: Injection flag indicator
            flags_list = cycle_data.get('flags', [])
            has_injection = '✓' if 'injection' in flags_list else ''
            cycle_table.setItem(row_idx, 7, QTableWidgetItem(has_injection))
            
            # Column 8: Other flags (wash, spike)
            other_flags = [f for f in flags_list if f != 'injection']
            flags_text = ', '.join(other_flags) if other_flags else ''
            cycle_table.setItem(row_idx, 8, QTableWidgetItem(flags_text))
            
            # Column 9: Channel selector
            channel_combo = QComboBox()
            channel_combo.addItems(["All", "A", "B", "C", "D"])
            channel_combo.setCurrentText("All")
            channel_combo.setStyleSheet("""
                QComboBox {
                    background: white;
                    border: 1px solid #D1D1D6;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 12px;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox:hover {
                    border: 1px solid #007AFF;
                }
            """)
            channel_combo.setProperty('cycle_index', row_idx)
            channel_combo.currentTextChanged.connect(self._on_cycle_channel_changed)
            cycle_table.setCellWidget(row_idx, 9, channel_combo)
            
            # Column 10: Time shift
            shift_spinbox = QDoubleSpinBox()
            shift_spinbox.setRange(-1000.0, 1000.0)
            shift_spinbox.setValue(0.0)
            shift_spinbox.setSuffix(" s")
            shift_spinbox.setDecimals(2)
            shift_spinbox.setSingleStep(0.1)
            shift_spinbox.setStyleSheet("""
                QDoubleSpinBox {
                    background: white;
                    border: 1px solid #D1D1D6;
                    border-radius: 4px;
                    padding: 2px 4px;
                    font-size: 12px;
                }
                QDoubleSpinBox:hover {
                    border: 1px solid #007AFF;
                }
            """)
            shift_spinbox.setProperty('cycle_index', row_idx)
            shift_spinbox.valueChanged.connect(self._on_cycle_shift_changed)
            cycle_table.setCellWidget(row_idx, 10, shift_spinbox)
            
            # Initialize alignment settings for this cycle
            if not hasattr(self, '_cycle_alignment'):
                self._cycle_alignment = {}
            self._cycle_alignment[row_idx] = {'channel': 'All', 'shift': 0.0}
            
            # Update loaded cycles data list
            if not hasattr(self, '_loaded_cycles_data'):
                self._loaded_cycles_data = []
            self._loaded_cycles_data.append(cycle_data)
            
            logger.info(f"✓ Added cycle to table: {type_with_number} at row {row_idx}")
            
        except Exception as e:
            logger.exception(f"Error adding cycle to table: {e}")

    def _populate_cycle_table_from_loaded_data(self, cycles_data: list):
        """Populate the cycle data table with loaded cycle information.

        Args:
            cycles_data: List of cycle dictionaries from loaded Excel data
        """
        from PySide6.QtWidgets import QTableWidgetItem
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self, 'cycle_data_table'):
                logger.warning("Cycle data table not found - cannot populate")
                return

            # Clear existing table data and reset type counter
            self.cycle_data_table.setRowCount(0)
            self._cycle_type_counts = {}  # Reset numbering for loaded data

            if not cycles_data:
                logger.info("No cycles to display in table")
                return

            # Set row count to match number of cycles
            self.cycle_data_table.setRowCount(len(cycles_data))

            # Count occurrences of each type for numbering
            type_counts = {}

            # Populate each row with cycle data
            for row_idx, cycle in enumerate(cycles_data):
                # Get cycle type and format with numbering
                cycle_type = cycle.get('type', 'Unknown')

                # Abbreviate "Concentration" to "Conc."
                if cycle_type.lower() in ('concentration', 'conc', 'conc.'):
                    cycle_type = 'Conc.'

                # Count this type occurrence
                if cycle_type not in type_counts:
                    type_counts[cycle_type] = 0
                type_counts[cycle_type] += 1

                # Format type with number (e.g., "Baseline 1", "Conc. 2")
                type_with_number = f"{cycle_type} {type_counts[cycle_type]}"

                # Column 0: Type (with automatic numbering)
                self.cycle_data_table.setItem(row_idx, 0, QTableWidgetItem(type_with_number))

                # Column 1: Duration (minutes)
                duration = cycle.get('duration_minutes', cycle.get('length_minutes', ''))
                if isinstance(duration, (int, float)):
                    duration = f"{duration:.2f}"
                self.cycle_data_table.setItem(row_idx, 1, QTableWidgetItem(str(duration)))

                # Column 2: Start time (seconds)
                start_time = cycle.get('start_time_sensorgram', cycle.get('sensorgram_time', ''))
                if isinstance(start_time, (int, float)):
                    start_time = f"{start_time:.2f}"
                self.cycle_data_table.setItem(row_idx, 2, QTableWidgetItem(str(start_time)))

                # Column 3: Concentration value
                # Handle both single concentration_value and multi-channel concentrations dict
                if cycle.get('concentrations'):
                    # Multi-channel concentrations - format as "A:100, B:50"
                    conc_dict = cycle['concentrations']
                    if isinstance(conc_dict, dict):
                        conc_parts = [f"{ch}:{val}" for ch, val in sorted(conc_dict.items())]
                        conc_value = ', '.join(conc_parts)
                    else:
                        conc_value = str(conc_dict)
                else:
                    # Single concentration value
                    conc_value = cycle.get('concentration_value', '')
                    if isinstance(conc_value, (int, float)):
                        conc_value = f"{conc_value:.2f}"
                self.cycle_data_table.setItem(row_idx, 3, QTableWidgetItem(str(conc_value)))

                # Column 4: Concentration units (use 'units' field if available)
                conc_units = cycle.get('units', cycle.get('concentration_units', ''))
                self.cycle_data_table.setItem(row_idx, 4, QTableWidgetItem(str(conc_units)))

                # Column 5: Notes (include cycle_id for tracking)
                notes = cycle.get('note', cycle.get('notes', ''))
                cycle_id = cycle.get('cycle_id', '')
                if cycle_id:
                    notes_display = f"[ID:{cycle_id}] {notes}" if notes else f"[ID:{cycle_id}]"
                else:
                    notes_display = notes
                self.cycle_data_table.setItem(row_idx, 5, QTableWidgetItem(str(notes_display)))

                # Column 6: Delta SPR
                delta_spr = cycle.get('delta_spr', '')
                if isinstance(delta_spr, (int, float)):
                    delta_spr_text = f"{delta_spr:.1f}"
                else:
                    delta_spr_text = str(delta_spr) if delta_spr else ''
                self.cycle_data_table.setItem(row_idx, 6, QTableWidgetItem(delta_spr_text))
                
                # Column 7: Injection flag indicator
                flags_list = cycle.get('flags', [])
                has_injection = '✓' if 'injection' in flags_list else ''
                self.cycle_data_table.setItem(row_idx, 7, QTableWidgetItem(has_injection))
                
                # Column 8: Other flags (wash, spike)
                other_flags = [f for f in flags_list if f != 'injection']
                flags_text = ', '.join(other_flags) if other_flags else ''
                self.cycle_data_table.setItem(row_idx, 8, QTableWidgetItem(flags_text))

                # Column 9: Channel selector (dropdown)
                from PySide6.QtWidgets import QComboBox
                channel_combo = QComboBox()
                channel_combo.addItems(["All", "A", "B", "C", "D"])
                channel_combo.setCurrentText("All")
                channel_combo.setStyleSheet("""
                    QComboBox {
                        background: white;
                        border: 1px solid #D1D1D6;
                        border-radius: 4px;
                        padding: 2px 8px;
                        font-size: 12px;
                    }
                    QComboBox::drop-down {
                        border: none;
                    }
                    QComboBox:hover {
                        border: 1px solid #007AFF;
                    }
                """)
                # Store cycle index in widget
                channel_combo.setProperty('cycle_index', row_idx)
                channel_combo.currentTextChanged.connect(self._on_cycle_channel_changed)
                self.cycle_data_table.setCellWidget(row_idx, 9, channel_combo)

                # Column 10: Time shift (spinbox in seconds)
                from PySide6.QtWidgets import QDoubleSpinBox
                shift_spinbox = QDoubleSpinBox()
                shift_spinbox.setRange(-1000.0, 1000.0)
                shift_spinbox.setValue(0.0)
                shift_spinbox.setSuffix(" s")
                shift_spinbox.setDecimals(2)
                shift_spinbox.setSingleStep(0.1)
                shift_spinbox.setStyleSheet("""
                    QDoubleSpinBox {
                        background: white;
                        border: 1px solid #D1D1D6;
                        border-radius: 4px;
                        padding: 2px 4px;
                        font-size: 12px;
                    }
                    QDoubleSpinBox:hover {
                        border: 1px solid #007AFF;
                    }
                """)
                # Store cycle index in widget
                shift_spinbox.setProperty('cycle_index', row_idx)
                shift_spinbox.valueChanged.connect(self._on_cycle_shift_changed)
                self.cycle_data_table.setCellWidget(row_idx, 10, shift_spinbox)

            # Store cycles data for graph loading
            self._loaded_cycles_data = cycles_data

            # Initialize cycle alignment settings (channel and shift per cycle)
            if not hasattr(self, '_cycle_alignment'):
                self._cycle_alignment = {}
            for idx in range(len(cycles_data)):
                self._cycle_alignment[idx] = {'channel': 'All', 'shift': 0.0}

            logger.info(f"✓ Populated cycle table with {len(cycles_data)} cycles")

        except Exception as e:
            logger.exception(f"Error populating cycle table: {e}")

    def _populate_edits_timeline_from_loaded_data(self, raw_data: list):
        """Populate the timeline navigator graph with loaded raw data.

        Args:
            raw_data: List of raw data dictionaries with 'time', 'channel', 'value'
        """
        import numpy as np
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self, 'edits_timeline_graph'):
                logger.warning("Timeline graph not found - cannot populate")
                return

            if not raw_data:
                logger.info("No raw data to display in timeline")
                return

            # Separate data by channel
            channel_data = {'a': [], 'b': [], 'c': [], 'd': []}

            for row in raw_data:
                channel = row.get('channel', '')
                time = row.get('time')
                value = row.get('value')

                if channel in channel_data and time is not None and value is not None:
                    channel_data[channel].append((time, value))

            # Plot each channel
            for ch_idx, ch in enumerate(['a', 'b', 'c', 'd']):
                if channel_data[ch]:
                    # Sort by time
                    channel_data[ch].sort(key=lambda x: x[0])
                    times = np.array([t for t, v in channel_data[ch]])
                    values = np.array([v for t, v in channel_data[ch]])

                    # Plot on timeline graph
                    self.edits_timeline_curves[ch_idx].setData(times, values)
                    logger.debug(f"  Timeline: Plotted {len(times)} points for channel {ch}")
                else:
                    self.edits_timeline_curves[ch_idx].setData([], [])

            # Set cursor range to span the data
            if any(channel_data.values()):
                all_times = []
                for ch_data in channel_data.values():
                    all_times.extend([t for t, v in ch_data])

                if all_times:
                    min_time = min(all_times)
                    max_time = max(all_times)

                    # Set cursor positions to span data
                    self.edits_timeline_cursors['left'].setValue(min_time)
                    self.edits_timeline_cursors['right'].setValue(max_time)

                    # Trigger selection view update
                    self._update_edits_selection_view()

            logger.info(f"✓ Populated timeline graph with data from {len(raw_data)} rows")

        except Exception as e:
            logger.exception(f"Error populating timeline graph: {e}")

    def _on_edits_graph_clicked(self, event):
        """Handle mouse clicks on Edits graph for flag management."""
        from PySide6.QtCore import Qt
        from affilabs.utils.logger import logger
        import pyqtgraph as pg

        # Get click position in data coordinates
        view_box = self.edits_primary_graph.plotItem.vb
        mouse_point = view_box.mapSceneToView(event.scenePos())
        time_val = mouse_point.x()
        spr_val = mouse_point.y()

        # Handle left-click for flag selection
        if event.button() == Qt.MouseButton.LeftButton:
            if not hasattr(self, 'edits_tab'):
                return

            # Check if we clicked near a flag (within 10 pixels)
            min_dist = float('inf')
            closest_idx = None

            for idx, flag in enumerate(self.edits_tab._edits_flags):
                # Calculate distance in pixel space
                flag_pos = view_box.mapViewToScene(pg.Point(flag.time, flag.spr))
                click_pos = event.scenePos()
                dist = ((flag_pos.x() - click_pos.x())**2 + (flag_pos.y() - click_pos.y())**2)**0.5

                if dist < min_dist:
                    min_dist = dist
                    closest_idx = idx

            # If clicked within 15 pixels of a flag, select it
            if closest_idx is not None and min_dist < 15:
                # Deselect previous flag
                if self.edits_tab._selected_flag_idx is not None:
                    prev_flag = self.edits_tab._edits_flags[self.edits_tab._selected_flag_idx]
                    prev_flag.marker.setPen(pg.mkPen('w', width=2))

                # Select new flag
                self.edits_tab._selected_flag_idx = closest_idx
                flag = self.edits_tab._edits_flags[closest_idx]
                flag.marker.setPen(pg.mkPen('cyan', width=3))  # Highlight selected
                logger.debug(f"Selected {flag.flag_type} flag at t={flag.time:.2f}s")
                return
            else:
                # Clicked empty space - deselect
                if self.edits_tab._selected_flag_idx is not None:
                    prev_flag = self.edits_tab._edits_flags[self.edits_tab._selected_flag_idx]
                    prev_flag.marker.setPen(pg.mkPen('w', width=2))
                    self.edits_tab._selected_flag_idx = None
                return

        # Handle right-click (context menu)
        if event.button() != Qt.MouseButton.RightButton:
            return

        # Check if we have cycle data loaded
        if not hasattr(self, '_loaded_cycles_data') or not self._loaded_cycles_data:
            logger.warning("No cycle data loaded - cannot add flags")
            return

        # Determine which channel to assign (use first visible channel or A)
        channel = 'A'

        # Show flag type menu
        from affilabs.domain import create_flag
        from PySide6.QtWidgets import QMenu, QAction
        from PySide6.QtGui import QCursor

        menu = QMenu()

        # Create flag type actions
        injection_action = QAction("▲ Injection", menu)
        injection_action.triggered.connect(
            lambda: self._add_edits_flag(channel, time_val, spr_val, "injection")
        )

        wash_action = QAction("■ Wash", menu)
        wash_action.triggered.connect(
            lambda: self._add_edits_flag(channel, time_val, spr_val, "wash")
        )

        spike_action = QAction("★ Spike", menu)
        spike_action.triggered.connect(
            lambda: self._add_edits_flag(channel, time_val, spr_val, "spike")
        )

        menu.addAction(injection_action)
        menu.addAction(wash_action)
        menu.addAction(spike_action)

        # Show menu at cursor position
        menu.exec(QCursor.pos())

    def _add_edits_flag(self, channel: str, time_val: float, spr_val: float, flag_type: str):
        """Add a flag to the Edits graph."""
        from affilabs.domain import create_flag
        from affilabs.utils.logger import logger
        import pyqtgraph as pg

        try:
            # Create Flag instance
            flag = create_flag(
                flag_type=flag_type,
                channel=channel.upper(),
                time=time_val,
                spr=spr_val,
            )

            # Create visual marker
            marker = pg.ScatterPlotItem(
                [flag.time],
                [flag.spr],
                symbol=flag.marker_symbol,
                size=flag.marker_size,
                brush=pg.mkBrush(flag.marker_color),
                pen=pg.mkPen('w', width=2),
            )
            marker.setZValue(100)  # Draw on top

            # Add to graph
            self.edits_primary_graph.addItem(marker)
            flag.marker = marker

            # Store flag
            if hasattr(self, 'edits_tab'):
                self.edits_tab._edits_flags.append(flag)

            logger.info(f"🚩 Added {flag_type} flag in Edits at t={time_val:.2f}s")

        except Exception as e:
            logger.error(f"Failed to add flag in Edits: {e}")

    def _on_cycle_selected_in_table(self):
        """Handle cycle selection in table - load cycle data on graph.

        Supports multi-cycle selection for blending:
        - Single selection: Shows one cycle with baseline cursors
        - Multi-selection: Overlays all selected cycles
        - No selection: Clears the graph
        """
        from affilabs.utils.logger import logger

        try:
            # Get all selected rows
            selected_rows = sorted(set(item.row() for item in self.cycle_data_table.selectedItems()))

            if not selected_rows:
                # Clear graph when nothing is selected
                logger.info("[GRAPH] No cycles selected - clearing graph")
                for i in range(4):
                    self.edits_graph_curves[i].setData([], [])
                # Hide alignment panel when nothing selected
                if hasattr(self, 'edits_tab'):
                    self.edits_tab.alignment_panel.hide()
                return

            # Show alignment panel for single selection
            if len(selected_rows) == 1 and hasattr(self, 'edits_tab'):
                row_idx = selected_rows[0]
                self.edits_tab.alignment_panel.show()

                # Update title with cycle number
                cycle_num = row_idx + 1  # 1-indexed for display
                self.edits_tab.alignment_title.setText(f"Cycle {cycle_num} Alignment")

                # Populate alignment controls from stored data
                alignment_data = self.edits_tab._cycle_alignment.get(row_idx, {'channel': 'All', 'shift': 0.0})
                self.edits_tab.alignment_channel_combo.blockSignals(True)
                self.edits_tab.alignment_shift_spinbox.blockSignals(True)
                self.edits_tab.alignment_channel_combo.setCurrentText(alignment_data['channel'])
                self.edits_tab.alignment_shift_spinbox.setValue(alignment_data['shift'])
                self.edits_tab.alignment_channel_combo.blockSignals(False)
                self.edits_tab.alignment_shift_spinbox.blockSignals(False)

                # Populate cycle boundary controls
                if row_idx < len(self._loaded_cycles_data):
                    cycle = self._loaded_cycles_data[row_idx]
                    start_time = cycle.get('start_time_sensorgram', 0)
                    end_time = cycle.get('end_time_sensorgram', start_time + 300)
                    self.edits_tab.cycle_start_spinbox.blockSignals(True)
                    self.edits_tab.cycle_end_spinbox.blockSignals(True)
                    self.edits_tab.cycle_start_spinbox.setValue(start_time)
                    self.edits_tab.cycle_end_spinbox.setValue(end_time)
                    self.edits_tab.cycle_start_spinbox.blockSignals(False)
                    self.edits_tab.cycle_end_spinbox.blockSignals(False)
            elif hasattr(self, 'edits_tab'):
                # Hide for multi-selection (no alignment controls for multiple cycles)
                self.edits_tab.alignment_panel.hide()

            # Get cycle data
            if not hasattr(self, '_loaded_cycles_data') or not self._loaded_cycles_data:
                logger.warning("No loaded cycle data available")
                return

            # Update channel source combos with selected cycle numbers
            self._update_channel_source_combos(selected_rows)

            # Collect all data from selected cycles
            all_cycle_data = {
                'a': {'time': [], 'wavelength': []},
                'b': {'time': [], 'wavelength': []},
                'c': {'time': [], 'wavelength': []},
                'd': {'time': [], 'wavelength': []},
            }

            valid_cycles_loaded = 0

            for row in selected_rows:
                if row >= len(self._loaded_cycles_data):
                    continue

                cycle = self._loaded_cycles_data[row]

                # Get time range for this cycle
                start_time = cycle.get('start_time_sensorgram', cycle.get('sensorgram_time'))
                end_time = cycle.get('end_time_sensorgram')

                # Handle NaN values from pandas (convert to None)
                import math
                try:
                    if start_time is not None and isinstance(start_time, float) and math.isnan(start_time):
                        start_time = None
                    if end_time is not None and isinstance(end_time, float) and math.isnan(end_time):
                        end_time = None
                except (TypeError, ValueError):
                    pass  # Not a number, keep as is

                if start_time is None:
                    logger.warning(f"Cycle {row} has no start time - skipping")
                    continue

                logger.info(f"[GRAPH] Loading cycle {row}: start={start_time}s, end={end_time}s")

                # If no end time, use start time + duration
                if end_time is None:
                    duration_min = cycle.get('duration_minutes', cycle.get('length_minutes', 5))
                    if duration_min is not None:
                        end_time = start_time + (duration_min * 60)
                    else:
                        logger.warning(f"Cycle {row} has no duration - using 5 min default")
                        end_time = start_time + 300  # 5 minutes

                # Load raw data from loaded Excel
                if not hasattr(self.app, 'recording_mgr') or self.app.recording_mgr is None:
                    logger.warning("Recording manager not available")
                    continue

                # Get raw data from data collector
                raw_data = self.app.recording_mgr.data_collector.raw_data_rows

                if not raw_data:
                    logger.warning("No raw data available to display")
                    continue

                logger.info(f"[GRAPH] Filtering {len(raw_data)} raw data rows for time range {start_time}-{end_time}")

                # Get alignment settings for this cycle
                cycle_channel = 'All'
                cycle_shift = 0.0
                if hasattr(self, '_cycle_alignment') and row in self._cycle_alignment:
                    cycle_channel = self._cycle_alignment[row]['channel']
                    cycle_shift = self._cycle_alignment[row]['shift']
                    logger.info(f"[GRAPH] Cycle {row} alignment: channel={cycle_channel}, shift={cycle_shift:.2f}s")

                # Filter data for this cycle's time range and accumulate
                points_found = 0
                for row_data in raw_data:
                    time = row_data.get('elapsed', row_data.get('time', 0))
                    if start_time <= time <= end_time:
                        points_found += 1
                        # Convert to relative time (time since cycle start) + apply shift
                        relative_time = time - start_time + cycle_shift

                        # Handle two data formats:
                        # Format 1 (new): {'time': X, 'channel': 'a', 'value': Y}
                        # Format 2 (legacy): {'time': X, 'channel_a': Y, 'channel_b': Z, ...}

                        if 'channel' in row_data and 'value' in row_data:
                            # Format 1: One row per channel measurement
                            ch = row_data.get('channel')
                            value = row_data.get('value')
                            # Apply channel filter
                            if cycle_channel != 'All' and ch != cycle_channel.lower():
                                continue  # Skip this channel
                            if ch in ['a', 'b', 'c', 'd'] and value is not None:
                                all_cycle_data[ch]['time'].append(relative_time)
                                all_cycle_data[ch]['wavelength'].append(value)
                        else:
                            # Format 2: All channels in one row
                            for ch in ['a', 'b', 'c', 'd']:
                                # Apply channel filter
                                if cycle_channel != 'All' and ch != cycle_channel.lower():
                                    continue  # Skip this channel
                                # Try both naming conventions: channel_X or wavelength_X
                                wavelength = row_data.get(f'channel_{ch}', row_data.get(f'wavelength_{ch}'))
                                if wavelength is not None:
                                    all_cycle_data[ch]['time'].append(relative_time)
                                    all_cycle_data[ch]['wavelength'].append(wavelength)

                logger.info(f"[GRAPH] Found {points_found} data points in time range for cycle {row}")
                valid_cycles_loaded += 1

            # Check if any valid cycles were loaded
            if valid_cycles_loaded == 0:
                logger.warning("No valid cycles could be loaded - all cycles missing start time")
                QMessageBox.warning(
                    self,
                    "No Valid Cycles",
                    "Selected cycles are missing start time information.\n\n"
                    "This usually means the data was not recorded properly."
                )
                return

            # Plot the collected data on the graph
            import numpy as np

            # Conversion factor: 1 nm wavelength shift = 355 RU
            WAVELENGTH_TO_RU = 355.0

            for i, ch in enumerate(['a', 'b', 'c', 'd']):
                time_data = np.array(all_cycle_data[ch]['time'])
                wavelength_data = np.array(all_cycle_data[ch]['wavelength'])

                if len(time_data) > 0:
                    # Sort by time (important for proper line plotting!)
                    sort_indices = np.argsort(time_data)
                    time_data = time_data[sort_indices]
                    wavelength_data = wavelength_data[sort_indices]

                    # Apply baseline correction (subtract first point) and convert to RU
                    baseline = wavelength_data[0]
                    delta_wavelength = wavelength_data - baseline
                    spr_data = delta_wavelength * WAVELENGTH_TO_RU

                    self.edits_graph_curves[i].setData(time_data, spr_data)
                    logger.info(f"[GRAPH] Ch {ch.upper()}: {len(time_data)} pts, time {time_data.min():.1f}-{time_data.max():.1f}s, baseline={baseline:.3f}nm, RU range {spr_data.min():.1f} to {spr_data.max():.1f}")
                else:
                    # Clear curve if no data
                    self.edits_graph_curves[i].setData([], [])
                    logger.info(f"[GRAPH] No data for channel {ch.upper()}")

            # Auto-scale the graph to show all data
            self.edits_primary_graph.autoRange()
            # Update Y-axis label to show RU
            self.edits_primary_graph.setLabel('left', 'Response (RU)')
            logger.info("[GRAPH] Auto-scaled graph to fit data")

            logger.info(f"✓ Loaded {valid_cycles_loaded} cycle(s) to edits graph")

            # Handle baseline cursors (only for single selection)
            if len(selected_rows) == 1:
                row = selected_rows[0]
                cycle = self._loaded_cycles_data[row]
                start_time = cycle.get('start_time_sensorgram', cycle.get('sensorgram_time'))
                end_time = cycle.get('end_time_sensorgram')

                # Skip cursor creation if no valid start time
                if start_time is None:
                    logger.warning(f"Cycle {row} has no start time - skipping cursor creation")
                else:
                    if end_time is None:
                        duration_min = cycle.get('duration_minutes', cycle.get('length_minutes', 5))
                        if duration_min is not None:
                            end_time = start_time + (duration_min * 60)
                        else:
                            end_time = start_time + 300  # 5 minutes default

        except Exception as e:
            logger.exception(f"Error loading cycle data to edits graph: {e}")

    def _on_cycle_channel_changed(self, channel_text):
        """Handle channel selector change for a cycle row.

        Args:
            channel_text: Selected channel ("All", "A", "B", "C", or "D")
        """
        from affilabs.utils.logger import logger

        try:
            # Get the cycle index from the sender widget
            sender = self.sender()
            if not sender:
                return

            cycle_idx = sender.property('cycle_index')
            if cycle_idx is None:
                return

            # Update alignment settings
            if not hasattr(self, '_cycle_alignment'):
                self._cycle_alignment = {}

            if cycle_idx not in self._cycle_alignment:
                self._cycle_alignment[cycle_idx] = {'channel': 'All', 'shift': 0.0}

            self._cycle_alignment[cycle_idx]['channel'] = channel_text
            logger.info(f"[ALIGNMENT] Cycle {cycle_idx} channel set to: {channel_text}")

            # Refresh the graph if this cycle is selected
            self._on_cycle_selected_in_table()

        except Exception as e:
            logger.exception(f"Error handling cycle channel change: {e}")

    def _on_cycle_shift_changed(self, shift_value):
        """Handle time shift change for a cycle row.

        Args:
            shift_value: Time shift in seconds
        """
        from affilabs.utils.logger import logger

        try:
            # Get the cycle index from the sender widget
            sender = self.sender()
            if not sender:
                return

            cycle_idx = sender.property('cycle_index')
            if cycle_idx is None:
                return

            # Update alignment settings
            if not hasattr(self, '_cycle_alignment'):
                self._cycle_alignment = {}

            if cycle_idx not in self._cycle_alignment:
                self._cycle_alignment[cycle_idx] = {'channel': 'All', 'shift': 0.0}

            self._cycle_alignment[cycle_idx]['shift'] = shift_value
            logger.info(f"[ALIGNMENT] Cycle {cycle_idx} shift set to: {shift_value:.2f}s")

            # Refresh the graph if this cycle is selected
            self._on_cycle_selected_in_table()

        except Exception as e:
            logger.exception(f"Error handling cycle shift change: {e}")

    def _update_channel_source_combos(self, selected_rows: list):
        """Update channel source dropdown options based on selected cycles.

        Args:
            selected_rows: List of selected table row indices
        """
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self, 'channel_source_combos'):
                return

            # Clear and repopulate all channel combos
            for ch_idx in range(4):
                combo = self.channel_source_combos[ch_idx]
                combo.clear()
                combo.addItem("Auto")  # Default option

                # Add each selected cycle as an option
                for row in selected_rows:
                    if row < len(self._loaded_cycles_data):
                        cycle = self._loaded_cycles_data[row]
                        cycle_type = cycle.get('type', 'Unknown')
                        combo.addItem(f"Cycle {row + 1} ({cycle_type})", row)

            logger.debug(f"Updated channel source combos with {len(selected_rows)} cycles")

        except Exception as e:
            logger.exception(f"Error updating channel source combos: {e}")

    def _create_segment_from_selection(self):
        """Create an EditableSegment from currently selected cycles.

        Uses channel source combos to determine which cycle contributes to each channel.
        """
        from PySide6.QtWidgets import QMessageBox, QInputDialog
        from affilabs.utils.logger import logger
        from affilabs.domain import Cycle

        try:
            # Get selected cycles
            selected_rows = sorted(set(item.row() for item in self.cycle_data_table.selectedItems()))

            if not selected_rows:
                QMessageBox.warning(
                    self,
                    "No Selection",
                    "Please select one or more cycles to create a segment."
                )
                return

            if not hasattr(self, '_loaded_cycles_data') or not self._loaded_cycles_data:
                QMessageBox.warning(
                    self,
                    "No Data",
                    "No cycle data loaded."
                )
                return

            # Get cycle data (keep as dictionaries)
            source_cycles = []
            for row in selected_rows:
                if row < len(self._loaded_cycles_data):
                    cycle_dict = self._loaded_cycles_data[row]
                    source_cycles.append(cycle_dict)

            if not source_cycles:
                QMessageBox.warning(
                    self,
                    "Invalid Selection",
                    "Selected cycles could not be loaded."
                )
                return

            # Get channel sources from combos
            channel_sources = {}
            for ch_idx in range(4):
                combo = self.channel_source_combos[ch_idx]
                selected_index = combo.currentIndex()

                if selected_index == 0:  # "Auto"
                    # Use first selected cycle for this channel
                    channel_sources[ch_idx] = selected_rows[0]
                else:
                    # Use the cycle selected in combo
                    cycle_row = combo.currentData()
                    if cycle_row is not None:
                        channel_sources[ch_idx] = cycle_row
                    else:
                        channel_sources[ch_idx] = selected_rows[0]

            # Ask user for segment name
            segment_name, ok = QInputDialog.getText(
                self,
                "Create Segment",
                "Enter segment name:",
                text=f"Segment_{len(source_cycles)}_cycles"
            )

            if not ok or not segment_name:
                return

            # Create segment using SegmentManager
            if not hasattr(self.app, 'segment_mgr'):
                QMessageBox.warning(
                    self,
                    "Not Ready",
                    "Segment manager not initialized."
                )
                return

            # Determine time range (union of all selected cycles)
            min_start = min(c.get('start_time_sensorgram', c.get('sensorgram_time', 0)) for c in source_cycles)
            max_end = max(c.get('end_time_sensorgram', min_start + 300) for c in source_cycles)
            time_range = (min_start, max_end)

            # Create segment
            segment = self.app.segment_mgr.create_segment(
                name=segment_name,
                source_cycles=source_cycles,
                time_range=time_range,
                channel_sources=channel_sources
            )

            # Refresh segment list
            self._refresh_segment_list()

            QMessageBox.information(
                self,
                "Segment Created",
                f"Created segment '{segment_name}' from {len(source_cycles)} cycle(s).\n\n"
                f"Time range: {min_start:.1f}s - {max_end:.1f}s"
            )

            logger.info(f"✓ Created segment '{segment_name}' from {len(source_cycles)} cycles")

        except Exception as e:
            logger.exception(f"Error creating segment: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to create segment: {str(e)}"
            )

    def _clear_reference_graphs(self):
        """Clear all reference graphs."""
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self, 'edits_reference_curves'):
                return

            for i in range(3):
                # Clear all curves
                for curve in self.edits_reference_curves[i]:
                    curve.setData([], [])

                # Reset label
                self.edits_reference_labels[i].setText("Drag cycle here")
                self.edits_reference_labels[i].setStyleSheet(
                    "QLabel {"
                    "  font-size: 10px;"
                    "  color: {Colors.SECONDARY_TEXT};"
                    "  background: {Colors.TRANSPARENT};"
                    "  font-family: {Fonts.SYSTEM};"
                    "}",
                )

                # Reset stored data
                self.edits_reference_cycle_data[i] = None

            logger.info("✓ Cleared all reference graphs")

        except Exception as e:
            logger.exception(f"Error clearing reference graphs: {e}")

    def _load_cycle_to_reference(self, cycle_row: int, ref_index: int):
        """Load a cycle to a specific reference graph.

        Args:
            cycle_row: Row index of cycle in table
            ref_index: Index of reference graph (0-2)
        """
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self, '_loaded_cycles_data') or not self._loaded_cycles_data:
                logger.warning("No loaded cycle data available")
                return

            if cycle_row >= len(self._loaded_cycles_data):
                return

            if ref_index < 0 or ref_index >= 3:
                logger.warning(f"Invalid reference index: {ref_index}")
                return

            cycle = self._loaded_cycles_data[cycle_row]

            # Get time range for this cycle
            start_time = cycle.get('start_time_sensorgram', cycle.get('sensorgram_time'))
            end_time = cycle.get('end_time_sensorgram')

            if start_time is None:
                logger.warning(f"Cycle {cycle_row} has no start time - cannot load to reference")
                QMessageBox.warning(
                    self,
                    "Invalid Cycle",
                    f"Cycle {cycle_row + 1} is missing start time information and cannot be displayed."
                )
                return

            # If no end time, use start time + duration
            if end_time is None:
                duration_min = cycle.get('duration_minutes', cycle.get('length_minutes', 5))
                if duration_min is not None:
                    end_time = start_time + (duration_min * 60)
                else:
                    end_time = start_time + 300  # 5 minutes default

            # Load raw data from loaded Excel
            if not hasattr(self, '_loaded_raw_data') or not self._loaded_raw_data:
                logger.warning("No loaded data available")
                return

            # Get raw data (list of dicts with 'time', 'channel', 'value')
            raw_data = self._loaded_raw_data

            # Filter data for this cycle's time range
            cycle_data = {
                'a': {'time': [], 'wavelength': []},
                'b': {'time': [], 'wavelength': []},
                'c': {'time': [], 'wavelength': []},
                'd': {'time': [], 'wavelength': []},
            }

            for row_data in raw_data:
                time = row_data.get('time', 0)
                if start_time <= time <= end_time:
                    ch = row_data.get('channel', '')
                    if ch in ['a', 'b', 'c', 'd']:
                        value = row_data.get('value')
                        if value is not None:
                            cycle_data[ch]['time'].append(time)
                            cycle_data[ch]['wavelength'].append(value)

            # Update reference graph
            for ch_idx, ch in enumerate(['a', 'b', 'c', 'd']):
                if cycle_data[ch]['time']:
                    self.edits_reference_curves[ref_index][ch_idx].setData(
                        cycle_data[ch]['time'],
                        cycle_data[ch]['wavelength']
                    )
                else:
                    self.edits_reference_curves[ref_index][ch_idx].setData([], [])

            # Update label
            cycle_type = cycle.get('type', 'Unknown')
            self.edits_reference_labels[ref_index].setText(f"{cycle_type} {cycle_row + 1}")
            self.edits_reference_labels[ref_index].setStyleSheet(
                "QLabel {"
                "  font-size: 10px;"
                "  color: {Colors.PRIMARY_TEXT};"
                "  font-weight: 600;"
                "  background: {Colors.TRANSPARENT};"
                "  font-family: {Fonts.SYSTEM};"
                "}",
            )

            # Store cycle data
            self.edits_reference_cycle_data[ref_index] = cycle_row

            logger.info(f"✓ Loaded {cycle_type} cycle {cycle_row + 1} to reference {ref_index + 1}")

        except Exception as e:
            logger.exception(f"Error loading cycle to reference: {e}")

    def _export_segment_to_tracedrawer(self, segment_name: str):
        """Export a segment to TraceDrawer CSV format.

        Args:
            segment_name: Name of segment to export
        """
        from PySide6.QtWidgets import QFileDialog
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self.app, 'segment_mgr'):
                QMessageBox.warning(
                    self,
                    "Not Ready",
                    "Segment manager not initialized."
                )
                return

            # Get segment
            segment = self.app.segment_mgr.get_segment(segment_name)
            if segment is None:
                QMessageBox.warning(
                    self,
                    "Not Found",
                    f"Segment '{segment_name}' not found."
                )
                return

            # Ask for save location
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export to TraceDrawer CSV",
                f"{segment_name}.csv",
                "CSV Files (*.csv)"
            )

            if not file_path:
                return

            # Export using segment's method
            segment.export_to_tracedrawer_csv(file_path)

            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported segment '{segment_name}' to:\n{file_path}"
            )

            logger.info(f"✓ Exported segment '{segment_name}' to TraceDrawer CSV")

        except Exception as e:
            logger.exception(f"Error exporting segment: {e}")
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export segment: {str(e)}"
            )

    def _export_segment_to_json(self, segment_name: str):
        """Export a segment to JSON format for re-import.

        Args:
            segment_name: Name of segment to export
        """
        from PySide6.QtWidgets import QFileDialog
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self.app, 'segment_mgr'):
                QMessageBox.warning(
                    self,
                    "Not Ready",
                    "Segment manager not initialized."
                )
                return

            # Ask for save location
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Segment to JSON",
                f"{segment_name}.json",
                "JSON Files (*.json)"
            )

            if not file_path:
                return

            # Export using manager's method
            self.app.segment_mgr.export_segment(segment_name, file_path)

            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported segment '{segment_name}' to:\n{file_path}"
            )

            logger.info(f"✓ Exported segment '{segment_name}' to JSON")

        except Exception as e:
            logger.exception(f"Error exporting segment to JSON: {e}")
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export segment: {str(e)}"
            )

    def _export_selected_segment_csv(self):
        """Export currently selected segment to TraceDrawer CSV format."""
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self, 'segment_list_combo'):
                return

            segment_name = self.segment_list_combo.currentText()

            if segment_name == "(no segments yet)" or not segment_name:
                QMessageBox.warning(
                    self,
                    "No Selection",
                    "Please select a segment to export."
                )
                return

            self._export_segment_to_tracedrawer(segment_name)

        except Exception as e:
            logger.exception(f"Error exporting selected segment to CSV: {e}")

    def _export_selected_segment_json(self):
        """Export currently selected segment to JSON format."""
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self, 'segment_list_combo'):
                return

            segment_name = self.segment_list_combo.currentText()

            if segment_name == "(no segments yet)" or not segment_name:
                QMessageBox.warning(
                    self,
                    "No Selection",
                    "Please select a segment to export."
                )
                return

            self._export_segment_to_json(segment_name)

        except Exception as e:
            logger.exception(f"Error exporting selected segment to JSON: {e}")

    def _delete_selected_segment(self):
        """Delete currently selected segment."""
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self, 'segment_list_combo'):
                return

            segment_name = self.segment_list_combo.currentText()

            if segment_name == "(no segments yet)" or not segment_name:
                QMessageBox.warning(
                    self,
                    "No Selection",
                    "Please select a segment to delete."
                )
                return

            # Confirm deletion
            reply = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Are you sure you want to delete segment '{segment_name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            # Delete segment
            if hasattr(self.app, 'segment_mgr'):
                self.app.segment_mgr.delete_segment(segment_name)

                # Update segment list
                self._refresh_segment_list()

                QMessageBox.information(
                    self,
                    "Segment Deleted",
                    f"Deleted segment '{segment_name}'."
                )

                logger.info(f"✓ Deleted segment '{segment_name}'")

        except Exception as e:
            logger.exception(f"Error deleting segment: {e}")
            QMessageBox.critical(
                self,
                "Delete Error",
                f"Failed to delete segment: {str(e)}"
            )

    def _refresh_segment_list(self):
        """Refresh the segment list dropdown with current segments."""
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self, 'segment_list_combo'):
                return

            if not hasattr(self.app, 'segment_mgr'):
                return

            # Clear current list
            self.segment_list_combo.clear()

            # Get all segments
            segments = self.app.segment_mgr.list_segments()

            if segments:
                for segment_name in segments:
                    self.segment_list_combo.addItem(segment_name)
            else:
                self.segment_list_combo.addItem("(no segments yet)")

            logger.debug(f"Refreshed segment list: {len(segments)} segments")

        except Exception as e:
            logger.exception(f"Error refreshing segment list: {e}")

    def _find_nearest_index(self, time_list: list, target_time: float) -> int | None:
        """Find index of time value nearest to target time.

        Args:
            time_list: List of time values
            target_time: Target time to find

        Returns:
            Index of nearest time value, or None if list is empty
        """
        if not time_list:
            return None

        min_diff = float('inf')
        nearest_idx = 0

        for idx, time_val in enumerate(time_list):
            diff = abs(time_val - target_time)
            if diff < min_diff:
                min_diff = diff
                nearest_idx = idx

        return nearest_idx

    def _load_demo_data(self):
        """Load demo SPR kinetics data for promotional screenshots.

        Keyboard shortcut: Ctrl+Shift+D
        Generates realistic binding curves with association/dissociation phases.
        """
        try:
            from affilabs.utils.demo_data_generator import generate_demo_cycle_data

            # Generate 3 cycles of demo data with increasing responses
            time_array, channel_data, cycle_boundaries = generate_demo_cycle_data(
                num_cycles=3,
                cycle_duration=600,
                sampling_rate=2.0,
                responses=[20, 40, 65],  # Progressive concentration series
                seed=42,
            )

            # Check if app instance is available (it should be set by main_simplified)
            if not hasattr(self, "app") or self.app is None:
                print("⚠️  Demo data: No app instance available")
                print(
                    "   Demo data can only be loaded when running through main_simplified.py",
                )
                from PySide6.QtWidgets import QMessageBox

                QMessageBox.warning(
                    self,
                    "Demo Data Unavailable",
                    "Demo data can only be loaded when the application is fully initialized.\n\n"
                    "Please ensure you're running through main_simplified.py",
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
                data_mgr.wavelength_buffer_a.append(channel_data["a"][i])
                data_mgr.wavelength_buffer_b.append(channel_data["b"][i])
                data_mgr.wavelength_buffer_c.append(channel_data["c"][i])
                data_mgr.wavelength_buffer_d.append(channel_data["d"][i])

            # Now update the timeline data in buffer manager
            import numpy as np

            for ch in ["a", "b", "c", "d"]:
                if hasattr(self.app, "buffer_mgr") and hasattr(
                    self.app.buffer_mgr,
                    "timeline_data",
                ):
                    self.app.buffer_mgr.timeline_data[ch].time = np.array(time_array)
                    self.app.buffer_mgr.timeline_data[ch].wavelength = np.array(
                        channel_data[ch],
                    )

            # Trigger graph updates for both full timeline and cycle of interest
            # Update full timeline graph
            if hasattr(self, "full_timeline_graph"):
                for ch_idx, ch in enumerate(["a", "b", "c", "d"]):
                    if ch_idx < len(self.full_timeline_graph.curves):
                        curve = self.full_timeline_graph.curves[ch_idx]
                        curve.setData(time_array, channel_data[ch])

            # Update cycle of interest graph
            if hasattr(self.app, "_update_cycle_of_interest_graph"):
                self.app._update_cycle_of_interest_graph()

            print(
                f"✅ Demo data loaded: {len(time_array)} points, {len(cycle_boundaries)} cycles",
            )
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
                "Tip: Navigate to different views to capture various screenshots.",
            )

        except ImportError as e:
            print(f"❌ Error importing demo data generator: {e}")
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self,
                "Import Error",
                f"Could not import demo data generator:\n{e}",
            )
        except Exception as e:
            print(f"❌ Error loading demo data: {e}")
            import traceback

            try:
                print(traceback.format_exc())
            except:
                pass
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self,
                "Error Loading Demo Data",
                f"An error occurred while loading demo data:\n\n{e!s}\n\n"
                "Please check the console for details.",
            )


# Main entry point
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindowPrototype()
    window.show()
    sys.exit(app.exec())
