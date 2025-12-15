"""AffiLabs.core Production Sidebar

PRODUCTION CODE - Used by affilabs_core_ui.AffilabsMainWindow

This is the main sidebar for the AffiLabs.core application.
Contains 6 tabs with controls for device management, experiments, and settings.

NOT TO BE CONFUSED WITH:
- widgets/sidebar.py (old/unused modular version)
- LL_UI_v1_0.py SidebarPrototype (actual prototype, not production)

Author: AffiLabs Team
Last Updated: November 23, 2025
"""

from cycle_table_dialog import CycleTableDialog
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# Tab builders
from sidebar_tabs.device_status_builder import DeviceStatusTabBuilder
from sidebar_tabs.export_builder import ExportTabBuilder
from sidebar_tabs.flow_builder import FlowTabBuilder
from sidebar_tabs.graphic_control_builder import GraphicControlTabBuilder
from sidebar_tabs.settings_builder import SettingsTabBuilder
from sidebar_tabs.static_builder import StaticTabBuilder
from ui_styles import (
    Colors,
    Fonts,
    label_style,
    scrollbar_style,
    title_style,
)

# Colorblind-safe palette (Tol bright scheme)
COLORBLIND_PALETTE = ["#4477AA", "#EE6677", "#228833", "#CCBB44"]


class AffilabsSidebar(QWidget):
    """Production sidebar for AffiLabs.core application.

    Used by: affilabs_core_ui.AffilabsMainWindow

    Architecture:
    - 6 tabs: Device Status, Graphic Control, Static, Flow, Export, Settings
    - Each tab built by dedicated builder method (~550 lines average)
    - EventBus integration for centralized signal routing
    """

    def __init__(self, parent=None, event_bus=None):
        super().__init__(parent)
        self._ui_setup_done = False
        self.event_bus = event_bus  # EventBus for centralized signal routing
        self.cycle_table_dialog = None  # Will be created on first open
        self._setup_ui()

    def _setup_ui(self):
        if getattr(self, "_ui_setup_done", False):
            return
        self._ui_setup_done = True
        self.setStyleSheet(f"background: {Colors.BACKGROUND_LIGHT};")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setUpdatesEnabled(False)

        container = QWidget()
        container.setStyleSheet(f"background: {Colors.BACKGROUND_WHITE};")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.West)
        self.tab_widget.setDocumentMode(False)

        # Style the tab widget with compact vertical tabs (original design)
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background: {Colors.BACKGROUND_WHITE};
            }}
            QTabBar::tab {{
                background: transparent;
                color: {Colors.SECONDARY_TEXT};
                padding: 12px 20px;
                margin: 2px 0;
                border: none;
                font-size: 13px;
                font-weight: 500;
                min-height: 50px;
                border-radius: 6px;
            }}
            QTabBar::tab:selected {{
                background: {Colors.BACKGROUND_WHITE};
                color: {Colors.PRIMARY_TEXT};
                font-weight: 600;
            }}
            QTabBar::tab:hover:!selected {{
                background: {Colors.OVERLAY_LIGHT_6};
            }}
            QTabBar::tab:disabled {{
                background: transparent;
                color: {Colors.OVERLAY_LIGHT_20};
            }}
            QTabBar::tab:selected:!disabled {{
                border-left: 3px solid {Colors.PRIMARY_TEXT};
                padding-left: 17px;
            }}
        """)

        # Tab definitions with builder method mapping and subtitles
        tab_definitions = [
            (
                "Device Status",
                "Device Status",
                "Hardware readiness check",
                self._build_device_status_tab,
            ),
            (
                "Graphic Control",
                "Display Setup",
                "Configure cycle of interest graph",
                self._build_graphic_control_tab,
            ),
            (
                "Static",
                "Cycle Control",
                "Start and manage experiments",
                self._build_static_tab,
            ),
            ("Flow", "Flow Control", "Fluidics experiments", self._build_flow_tab),
            (
                "Export",
                "Export Data",
                "Save and export experiment results",
                self._build_export_tab,
            ),
            (
                "Settings",
                "Settings & Diagnostics",
                "Calibration and maintenance",
                self._build_settings_tab,
            ),
        ]

        # Store tab references for dynamic control
        self.tab_indices = {}
        tab_index = 0

        for label, title_text, subtitle_text, builder_method in tab_definitions:
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            scroll_area.setStyleSheet(scrollbar_style())

            tab_content = QWidget()
            tab_content.setStyleSheet(f"background: {Colors.BACKGROUND_WHITE};")
            tab_layout = QVBoxLayout(tab_content)
            tab_layout.setContentsMargins(20, 20, 20, 20)
            tab_layout.setSpacing(12)

            # Title with subtitle
            title = QLabel(title_text)
            title.setFixedHeight(27)
            title.setStyleSheet(title_style())
            tab_layout.addWidget(title)

            tab_layout.addSpacing(4)

            # Subtitle helper text
            subtitle = QLabel(subtitle_text)
            subtitle.setWordWrap(True)
            subtitle.setFixedHeight(20)
            subtitle.setStyleSheet(
                f"font-size: 11px;"
                f"color: {Colors.SECONDARY_TEXT};"
                f"background: transparent;"
                f"font-style: italic;"
                f"font-family: {Fonts.SYSTEM};",
            )
            tab_layout.addWidget(subtitle)

            tab_layout.addSpacing(12)

            # Call specific builder method for tab content
            builder_method(tab_layout)

            self.tab_widget.addTab(scroll_area, label)
            scroll_area.setWidget(tab_content)

            # Store tab index for later reference
            self.tab_indices[label] = tab_index
            tab_index += 1

        container_layout.addWidget(self.tab_widget)
        # Compatibility alias expected by main code
        self.tabs = self.tab_widget
        main_layout.addWidget(container)
        self.setUpdatesEnabled(True)

    def set_operation_mode(self, mode: str):
        """Set the active operation mode (static or flow) and update tab states."""
        if mode.lower() == "static":
            # Enable Static, disable Flow
            self.tab_widget.setTabEnabled(self.tab_indices["Static"], True)
            self.tab_widget.setTabEnabled(self.tab_indices["Flow"], False)
            self.tab_widget.setTabToolTip(
                self.tab_indices["Flow"],
                "Flow mode unavailable - requires pump hardware",
            )
        elif mode.lower() == "flow":
            # Enable Flow, disable Static
            self.tab_widget.setTabEnabled(self.tab_indices["Flow"], True)
            self.tab_widget.setTabEnabled(self.tab_indices["Static"], False)
            self.tab_widget.setTabToolTip(
                self.tab_indices["Static"],
                "Static mode unavailable - flow mode active",
            )
        else:
            # Enable both (default fallback)
            self.tab_widget.setTabEnabled(self.tab_indices["Static"], True)
            self.tab_widget.setTabEnabled(self.tab_indices["Flow"], True)

    def _build_device_status_tab(self, tab_layout: QVBoxLayout):
        """Build Device Status tab with hardware and subunit indicators using builder."""
        builder = DeviceStatusTabBuilder(self)
        builder.build(tab_layout)

    def _build_graphic_control_tab(self, tab_layout: QVBoxLayout):
        """Build Graphic Control tab with plots, axes, filters, and accessibility using builder."""
        builder = GraphicControlTabBuilder(self)
        builder.build(tab_layout)

    def _build_static_tab(self, tab_layout: QVBoxLayout):
        """Build Static tab with cycle management using builder."""
        builder = StaticTabBuilder(self)
        builder.build(tab_layout)

    def _build_flow_tab(self, tab_layout: QVBoxLayout):
        """Build Flow tab with pump controls and cycle management using builder."""
        builder = FlowTabBuilder(self)
        builder.build(tab_layout)

    def _open_cycle_table_dialog(self):
        """Open the full cycle table dialog (shared by Static and Flow tabs)."""
        if self.cycle_table_dialog is None:
            self.cycle_table_dialog = CycleTableDialog(self)

            # Load sample/demo data matching SegmentDataFrame structure
            # TODO: Connect to actual data source
            sample_data = [
                {
                    "seg_id": 0,
                    "name": "1",
                    "start": 0.0,
                    "end": 300.0,
                    "ref_ch": None,
                    "unit": "RU",
                    "shift_a": 0.0,
                    "shift_b": 0.0,
                    "shift_c": 0.0,
                    "shift_d": 0.0,
                    "cycle_type": "Baseline",
                    "cycle_time": 5,
                    "note": "Initial baseline",
                    "flags": None,
                    "error": None,
                },
                {
                    "seg_id": 1,
                    "name": "2",
                    "start": 300.0,
                    "end": 600.0,
                    "ref_ch": "a",
                    "unit": "nM",
                    "shift_a": 0.125,
                    "shift_b": 0.143,
                    "shift_c": 0.098,
                    "shift_d": 0.112,
                    "cycle_type": "Concentration",
                    "cycle_time": 5,
                    "note": "[A:50] Binding test",
                    "flags": "ChA: 2",
                    "error": None,
                },
            ]
            self.cycle_table_dialog.load_cycles(sample_data)

        self.cycle_table_dialog.show()
        self.cycle_table_dialog.raise_()
        self.cycle_table_dialog.activateWindow()

    def _build_export_tab(self, tab_layout: QVBoxLayout):
        """Build Export tab with data export options using builder."""
        builder = ExportTabBuilder(self)
        builder.build(tab_layout)

    def _toggle_all_channels(self):
        """Toggle all channel checkboxes."""
        all_checked = all(cb.isChecked() for cb in self.export_channel_checkboxes)
        for cb in self.export_channel_checkboxes:
            cb.setChecked(not all_checked)

    def _browse_export_destination(self):
        """Open directory picker for export destination."""
        from PySide6.QtWidgets import QFileDialog

        directory = QFileDialog.getExistingDirectory(self, "Select Export Destination")
        if directory:
            self.export_dest_input.setText(directory)

    def update_export_filesize_estimate(self, num_data_points: int, num_channels: int):
        """Update the file size estimation label based on data size.

        Args:
            num_data_points: Total number of data points across all time series
            num_channels: Number of channels selected for export

        """
        if num_data_points == 0:
            self.export_filesize_label.setText("Estimated file size: No data")
            return

        # Rough estimates per format (bytes per data point)
        bytes_per_point = {
            "csv": 20,  # Text-based, ~20 bytes per number
            "excel": 16,  # Binary, more efficient
            "json": 30,  # Text with structure overhead
            "hdf5": 12,  # Most efficient binary format
        }

        # Determine selected format
        format_type = "excel"  # Default
        if hasattr(self, "csv_radio") and self.csv_radio.isChecked():
            format_type = "csv"
        elif hasattr(self, "json_radio") and self.json_radio.isChecked():
            format_type = "json"
        elif hasattr(self, "hdf5_radio") and self.hdf5_radio.isChecked():
            format_type = "hdf5"

        # Calculate estimate
        bytes_estimate = (
            num_data_points * num_channels * bytes_per_point.get(format_type, 16)
        )

        # Add metadata overhead if enabled
        if hasattr(self, "metadata_check") and self.metadata_check.isChecked():
            bytes_estimate += 10 * 1024  # ~10 KB for metadata

        # Format size string
        if bytes_estimate < 1024:
            size_str = f"{bytes_estimate} B"
        elif bytes_estimate < 1024 * 1024:
            size_str = f"{bytes_estimate / 1024:.1f} KB"
        elif bytes_estimate < 1024 * 1024 * 1024:
            size_str = f"{bytes_estimate / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{bytes_estimate / (1024 * 1024 * 1024):.2f} GB"

        self.export_filesize_label.setText(f"Estimated file size: ~{size_str}")

    def _build_settings_tab(self, tab_layout: QVBoxLayout):
        """Build Settings tab with diagnostics, hardware, and calibration using builder."""
        builder = SettingsTabBuilder(self)
        builder.build(tab_layout)

    def toggle_polarizer_position(self):
        """Toggle polarizer between S and P positions and update button text.

        Note: This only updates the UI. The actual hardware movement is handled
        by main_simplified.py via the clicked signal connection.
        """
        if self.current_polarizer_position == "S":
            self.current_polarizer_position = "P"
            self.polarizer_toggle_btn.setText("Position: P")
        else:
            self.current_polarizer_position = "S"
            self.polarizer_toggle_btn.setText("Position: S")

        # This method can be called from main window to actually move the polarizer
        # and will return the new position
        return self.current_polarizer_position

    def set_polarizer_position(self, position: str):
        """Set polarizer position (S or P) and update button text.

        Args:
            position: 'S' or 'P'

        """
        position = position.upper()
        if position not in ["S", "P"]:
            return

        self.current_polarizer_position = position
        self.polarizer_toggle_btn.setText(f"Position: {position}")

    def update_spectroscopy_status(self, status: str, color: str = "#34C759"):
        """Update spectroscopy status indicator.

        Args:
            status: Status text (e.g., "Ready", "Acquiring", "Error")
            color: Color code for status indicator (default: green)

        """
        if hasattr(self, "transmission_status_indicator"):
            self.transmission_status_indicator.setText(f"● {status}")
            self.transmission_status_indicator.setStyleSheet(
                f"font-size: 11px;"
                f"color: {color};"
                f"background: transparent;"
                f"font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
            )

        if hasattr(self, "raw_data_status_indicator"):
            self.raw_data_status_indicator.setText(f"● {status}")
            self.raw_data_status_indicator.setStyleSheet(
                f"font-size: 11px;"
                f"color: {color};"
                f"background: transparent;"
                f"font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
            )

    def load_hardware_settings(
        self,
        s_pos: int = None,
        p_pos: int = None,
        led_a: int = None,
        led_b: int = None,
        led_c: int = None,
        led_d: int = None,
    ):
        """Load hardware settings into the input fields.

        Args:
            s_pos: S-mode servo position (0-180)
            p_pos: P-mode servo position (0-180)
            led_a: Channel A LED intensity (0-255)
            led_b: Channel B LED intensity (0-255)
            led_c: Channel C LED intensity (0-255)
            led_d: Channel D LED intensity (0-255)

        """
        if s_pos is not None and hasattr(self, "s_position_input"):
            self.s_position_input.setText(str(s_pos))

        if p_pos is not None and hasattr(self, "p_position_input"):
            self.p_position_input.setText(str(p_pos))

        if led_a is not None and hasattr(self, "channel_a_input"):
            self.channel_a_input.setText(str(led_a))

        if led_b is not None and hasattr(self, "channel_b_input"):
            self.channel_b_input.setText(str(led_b))

        if led_c is not None and hasattr(self, "channel_c_input"):
            self.channel_c_input.setText(str(led_c))

        if led_d is not None and hasattr(self, "channel_d_input"):
            self.channel_d_input.setText(str(led_d))

    def update_queue_status(self, count: int):
        """Update queue status display and button visibility.

        Args:
            count: Number of cycles currently in queue (0-5)

        """
        if hasattr(self, "queue_status_label"):
            if count == 0:
                self.queue_status_label.setText(
                    "Queue: 0 cycles | Click 'Add to Queue' to plan batch runs",
                )
            else:
                self.queue_status_label.setText(
                    f"Queue: {count} cycle{'s' if count > 1 else ''} ready",
                )

        if hasattr(self, "clear_queue_btn"):
            self.clear_queue_btn.setVisible(count > 0)

        if hasattr(self, "start_run_btn"):
            self.start_run_btn.setVisible(count > 0)

    def update_operation_hours(self, hours: int):
        """Update the operation hours display."""
        if hasattr(self, "hours_value"):
            self.hours_value.setText(f"{hours:,} hrs")

    def update_last_operation(self, date_str: str):
        """Update the last operation date display."""
        if hasattr(self, "last_op_value"):
            self.last_op_value.setText(date_str)

    def update_next_maintenance(self, date_str: str, is_overdue: bool = False):
        """Update the next maintenance date display.

        Args:
            date_str: Date string to display
            is_overdue: If True, display in red warning color

        """
        if hasattr(self, "next_maintenance_value"):
            color = "#FF3B30" if is_overdue else "#FF9500"
            self.next_maintenance_value.setText(date_str)
            self.next_maintenance_value.setStyleSheet(
                label_style(13, color) + "font-weight: 600; margin-top: 6px;",
            )

    def show_settings_applied_feedback(self):
        """Provide visual feedback when settings are successfully applied."""
        if hasattr(self, "apply_settings_btn"):
            # Store original style
            original_style = self.apply_settings_btn.styleSheet()

            # Change to success style temporarily
            self.apply_settings_btn.setText("✓ Applied")
            self.apply_settings_btn.setStyleSheet(
                "QPushButton {"
                "  background: #34C759;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 6px;"
                "  padding: 6px 16px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}",
            )

            # Reset after 2 seconds
            from PySide6.QtCore import QTimer

            QTimer.singleShot(2000, lambda: self._reset_apply_button(original_style))

    def _reset_apply_button(self, original_style: str):
        """Reset the apply button to its original state."""
        if hasattr(self, "apply_settings_btn"):
            self.apply_settings_btn.setText("Apply Settings")
            self.apply_settings_btn.setStyleSheet(original_style)

    def update_transmission_plot(self, channel: str, wavelength, transmission_spectrum):
        """Update transmission plot with live data.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            wavelength: Wavelength array in nm
            transmission_spectrum: Transmission percentage array

        """
        if not hasattr(self, "transmission_curves"):
            return

        # Map channel to curve index
        channel_map = {"a": 0, "b": 1, "c": 2, "d": 3}
        idx = channel_map.get(channel.lower())

        if idx is not None and idx < len(self.transmission_curves):
            try:
                self.transmission_curves[idx].setData(wavelength, transmission_spectrum)
                # Update status to show we're receiving data
                self.update_spectroscopy_status("Acquiring", "#007AFF")
            except Exception:
                pass  # Silently ignore plotting errors

    def update_raw_data_plot(self, channel: str, wavelength, raw_spectrum):
        """Update raw data plot with live intensity data.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            wavelength: Wavelength array in nm
            raw_spectrum: Raw intensity array (counts)

        """
        if not hasattr(self, "raw_data_curves"):
            return

        # Map channel to curve index
        channel_map = {"a": 0, "b": 1, "c": 2, "d": 3}
        idx = channel_map.get(channel.lower())

        if idx is not None and idx < len(self.raw_data_curves):
            try:
                self.raw_data_curves[idx].setData(wavelength, raw_spectrum)
                # Update status to show we're receiving data
                self.update_spectroscopy_status("Acquiring", "#007AFF")
            except Exception:
                pass  # Silently ignore plotting errors
