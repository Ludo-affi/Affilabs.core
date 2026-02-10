"""AffiLabs.core Production Sidebar

PRODUCTION CODE - Used by affilabs_core_ui.AffilabsMainWindow

This is the main sidebar for the AffiLabs.core application.
Contains 7 tabs with controls for device management, experiments, AI help, and settings.

File: affilabs_sidebar.py (renamed from sidebar.py for clarity)

NOT TO BE CONFUSED WITH:
- widgets/sidebar.py (ARCHIVED - old/unused modular version)
- LL_UI_v1_0.py SidebarPrototype (ARCHIVED - actual prototype, not production)

Author: AffiLabs Team
Last Updated: December 4, 2025 - Added MVVM refactoring with CycleConfigViewModel
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QTransform

# Tab builders
from affilabs.sidebar_tabs.AL_device_status_builder import DeviceStatusTabBuilder
from affilabs.sidebar_tabs.AL_export_builder import ExportTabBuilder
from affilabs.sidebar_tabs.AL_flow_builder import FlowTabBuilder
from affilabs.sidebar_tabs.AL_graphic_control_builder import GraphicControlTabBuilder
from affilabs.sidebar_tabs.AL_settings_builder import SettingsTabBuilder
from affilabs.sidebar_tabs.AL_method_builder import MethodTabBuilder
from affilabs.ui_styles import (
    Colors,
    Fonts,
    label_style,
    scrollbar_style,
    title_style,
)

# ViewModels - MVVM architecture
from affilabs.viewmodels import CycleConfigViewModel

# Colorblind-safe palette (Tol bright scheme)
COLORBLIND_PALETTE = ["#4477AA", "#EE6677", "#228833", "#CCBB44"]


class AffilabsSidebar(QWidget):
    """Production sidebar for AffiLabs.core application.

    Used by: affilabs_core_ui.AffilabsMainWindow

    Architecture:
    - 7 tabs: Device Status, Method, Flow, Export, Settings, Spark
    - Each tab built by dedicated builder method (~550 lines average)
    - Signal abstraction layer for loose coupling
    """

    # Signal abstraction layer (Change #3) - emit high-level actions instead of exposing buttons
    scan_requested = Signal()
    export_requested = Signal()
    debug_log_requested = Signal()
    polarizer_toggle_requested = Signal()
    settings_apply_requested = Signal()
    led_brightness_changed = Signal(str, str)  # channel, value (live update)
    synced_flowrate_changed = Signal()  # Synced pump flowrate changed (live update)

    # High-level cycle signals (MVVM refactoring)
    cycle_start_requested = Signal(object)  # CycleConfigViewModel
    cycle_queued = Signal(object)  # CycleConfigViewModel
    queue_cleared = Signal()
    queued_run_started = Signal()
    next_cycle_requested = Signal()  # Skip to next cycle

    def __init__(self, parent=None, detector_type="USB4000", app=None):
        super().__init__(parent)
        self._ui_setup_done = False
        self.cycle_table_dialog = None  # Will be created on first open
        self.detector_type = detector_type  # Store detector type for plot configuration
        self.app = app  # Reference to Application instance for accessing _completed_cycles

        # Deferred loading flags (Settings tab plots now loaded immediately)
        self._settings_tab_loaded = False

        # Create baseline button IMMEDIATELY (before any signal connections)
        self._create_baseline_button()

        self._setup_ui()
        self._connect_internal_signals()

    def _create_baseline_button(self):
        """Create baseline capture button immediately for signal connections.

        This button is created in __init__ rather than lazy-loaded so that
        main-simplified.py can connect to it before the Settings tab is opened.
        """
        self.baseline_capture_btn = QPushButton("📊 Capture 5-Min Baseline")
        self.baseline_capture_btn.setObjectName("baseline_capture_btn")
        self.baseline_capture_btn.setFixedHeight(40)
        self.baseline_capture_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.baseline_capture_btn.setStyleSheet(
            "QPushButton#baseline_capture_btn {"
            "  background-color: #FF3B30;"
            "  color: white;"
            "  border: 2px solid #E02020;"
            "  border-radius: 6px;"
            "  padding: 10px 16px;"
            "  font-size: 14px;"
            "  font-weight: bold;"
            "}"
            "QPushButton#baseline_capture_btn:hover {"
            "  background-color: #FF4D42;"
            "  border: 2px solid #FF3B30;"
            "}"
            "QPushButton#baseline_capture_btn:pressed {"
            "  background-color: #C01818;"
            "}"
            "QPushButton#baseline_capture_btn:disabled {"
            "  background-color: #D1D1D6;"
            "  color: #86868B;"
            "  border: 2px solid #C7C7CC;"
            "}",
        )
        self.baseline_capture_btn.setToolTip(
            "Capture 5 minutes of baseline transmission data\n"
            "for noise analysis and optimization.\n\n"
            "Requirements:\n"
            "• Stable baseline (no injections)\n"
            "• Live acquisition running\n"
            "• System calibrated",
        )

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
        container.setStyleSheet(
            f"background: {Colors.BACKGROUND_WHITE};"
        )
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
                border-left: 1px solid rgba(0, 0, 0, 0.08);
                background: {Colors.BACKGROUND_WHITE};
            }}
            QTabBar {{
                alignment: left;
                background: #FAFAFA;
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
                background: rgba(0, 0, 0, 0.08);
                color: {Colors.PRIMARY_TEXT};
                font-weight: 700;
            }}
            QTabBar::tab:hover:!selected {{
                background: {Colors.OVERLAY_LIGHT_6};
            }}
            QTabBar::tab:disabled {{
                background: transparent;
                color: {Colors.OVERLAY_LIGHT_20};
            }}
            QTabBar::tab:selected:!disabled {{
                border-left: 4px solid #1D1D1F;
                padding-left: 16px;
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
            # HIDDEN: Graphic Control tab - content moved to Settings > Display Controls
            # (
            #     "Graphic Control",
            #     "Display Setup",
            #     "Configure cycle of interest graph",
            #     self._build_graphic_control_tab,
            # ),
            (
                "Method",
                "Build and run method",
                "Build and manage assay methods",
                self._build_method_tab,
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
            (
                "⚡",
                "⚡ Spark",
                "Ask questions about using Affilabs.core",
                self._build_spark_tab,
            ),
        ]

        # Store tab references for dynamic control
        self.tab_indices = {}
        tab_index = 0

        for label, title_text, subtitle_text, builder_method in tab_definitions:
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            scroll_area.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            scroll_area.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            scroll_area.setStyleSheet(scrollbar_style())

            tab_content = QWidget()
            tab_content.setStyleSheet(f"background: {Colors.BACKGROUND_WHITE};")
            tab_layout = QVBoxLayout(tab_content)
            tab_layout.setContentsMargins(20, 20, 20, 20)
            tab_layout.setSpacing(12)

            # Title with subtitle (capitalize first letter of each word)
            title = QLabel(title_text.title())
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

            # Add stretch to push all sections to the top (prevents even spacing when collapsed)
            tab_layout.addStretch()

            # For Spark tab, we want to rotate the lightning icon 90 degrees
            # We'll add the tab normally but store the index to customize later
            self.tab_widget.addTab(scroll_area, label)

            scroll_area.setWidget(tab_content)

            # Store tab index for later reference
            self.tab_indices[label] = tab_index

            # Apply rotation to Spark tab icon after it's added
            if label == "⚡":
                # Get the tab bar and apply rotation via stylesheet transform
                # Note: QTabBar doesn't support CSS transforms directly,
                # so we'll rotate the text using a custom approach
                from PySide6.QtGui import QPixmap, QPainter, QFont, QFontMetrics
                from PySide6.QtCore import QSize, QRect

                # Create a rotated pixmap of the lightning symbol
                # Use smaller size to match text height better
                icon_size = 28
                pixmap = QPixmap(icon_size, icon_size)
                pixmap.fill(Qt.GlobalColor.transparent)

                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

                # Set font to match tab text size
                font = QFont()
                font.setPixelSize(20)
                font.setBold(True)
                painter.setFont(font)

                # Get font metrics to properly center the text
                metrics = QFontMetrics(font)
                text_rect = metrics.boundingRect("⚡")

                # Center the coordinate system
                painter.translate(icon_size / 2, icon_size / 2)
                # Rotate 90 degrees clockwise
                painter.rotate(90)

                # Draw centered (offset by half of text bounds)
                painter.drawText(
                    -text_rect.width() / 2,
                    text_rect.height() / 2 - metrics.descent(),
                    "⚡"
                )
                painter.end()

                # Set as tab icon with updated size
                self.tab_widget.setTabIcon(tab_index, pixmap)
                # Set icon size for the tab bar to match text line height
                self.tab_widget.tabBar().setIconSize(QSize(28, 28))
                # Clear the text label since we're using icon
                self.tab_widget.setTabText(tab_index, "")

            tab_index += 1

        # Apply light green background to Spark tab button
        spark_tab_index = self.tab_indices.get("⚡")
        if spark_tab_index is not None:
            # Update stylesheet to include green background for Spark tab
            current_style = self.tab_widget.styleSheet()
            # Add specific styling that matches based on tab text
            enhanced_style = current_style.replace(
                "QTabBar::tab:selected:!disabled {",
                """QTabBar::tab[text="⚡"] {
                background: #E8F5E9 !important;
                color: #1B5E20 !important;
            }
            QTabBar::tab[text="⚡"]:selected {
                background: #C8E6C9 !important;
                color: #1B5E20 !important;
            }
            QTabBar::tab[text="⚡"]:hover:!selected {
                background: #D4EDD6 !important;
            }
            QTabBar::tab:selected:!disabled {"""
            )
            self.tab_widget.setStyleSheet(enhanced_style)

        container_layout.addWidget(self.tab_widget)
        # Compatibility alias expected by main code
        self.tabs = self.tab_widget
        main_layout.addWidget(container)

        # Connect tab change to lazy-load Settings tab plots
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        self.setUpdatesEnabled(True)

    def _connect_internal_signals(self):
        """Connect internal button clicks to outgoing signals (Change #3: Signal abstraction).

        This creates a clean abstraction layer - external code connects to high-level signals
        instead of directly to buttons, allowing internal implementation to change freely.
        """
        # Note: Most buttons are still directly connected in affilabs_core_ui._connect_signals()
        # for backward compatibility. These signals provide an alternative, cleaner interface.
        # Over time, external connections should migrate to these signals.

        # Wait for UI setup to complete before connecting
        if hasattr(self, "scan_btn"):
            self.scan_btn.clicked.connect(self.scan_requested.emit)
        if hasattr(self, "export_data_btn"):
            self.export_data_btn.clicked.connect(self.export_requested.emit)
        if hasattr(self, "debug_log_btn"):
            self.debug_log_btn.clicked.connect(self.debug_log_requested.emit)
        if hasattr(self, "polarizer_toggle_btn"):
            self.polarizer_toggle_btn.clicked.connect(
                self.polarizer_toggle_requested.emit,
            )
        if hasattr(self, "apply_settings_btn"):
            self.apply_settings_btn.clicked.connect(self.settings_apply_requested.emit)

        # High-level cycle signals (MVVM refactoring)
        if hasattr(self, "start_cycle_btn"):
            self.start_cycle_btn.clicked.connect(self._on_start_cycle_clicked)
        if hasattr(self, "add_to_queue_btn"):
            self.add_to_queue_btn.clicked.connect(self._on_add_to_queue_clicked)
        if hasattr(self, "clear_queue_btn"):
            self.clear_queue_btn.clicked.connect(self._on_clear_queue_clicked)
        if hasattr(self, "start_run_btn"):
            self.start_run_btn.clicked.connect(self._on_start_run_clicked)
        if hasattr(self, "start_queue_btn"):
            self.start_queue_btn.clicked.connect(self._on_start_run_clicked)
        if hasattr(self, "next_cycle_btn"):
            self.next_cycle_btn.clicked.connect(self._on_next_cycle_clicked)

    def _on_start_cycle_clicked(self):
        """Handle start cycle button click - emit high-level signal with config."""
        config = self.get_cycle_configuration()
        if config.is_valid():
            self.cycle_start_requested.emit(config)
        else:
            # Could show validation errors here
            from affilabs.utils.logger import logger

            errors = config.validate()
            logger.warning(f"Invalid cycle configuration: {errors}")

    def _on_add_to_queue_clicked(self):
        """Handle add to queue button click - emit high-level signal with config."""
        config = self.get_cycle_configuration()
        if config.is_valid():
            self.cycle_queued.emit(config)
        else:
            from affilabs.utils.logger import logger

            errors = config.validate()
            logger.warning(f"Invalid cycle configuration: {errors}")

    def _on_clear_queue_clicked(self):
        """Handle clear queue button click - emit high-level signal."""
        self.queue_cleared.emit()

    def _on_start_run_clicked(self):
        """Handle start queued run button click - emit high-level signal."""
        self.queued_run_started.emit()

    def _on_next_cycle_clicked(self):
        """Handle next cycle button click - emit high-level signal."""
        self.next_cycle_requested.emit()

    # === State Management Methods (Change #2: Encapsulation) ===

    def set_scan_state(self, scanning: bool):
        """Update scan button state (encapsulates internal implementation).

        Args:
            scanning: True if scan is in progress, False otherwise

        """
        if not hasattr(self, "scan_btn"):
            return

        self.scan_btn.setProperty("scanning", scanning)
        if scanning:
            self.scan_btn.setText("Scanning...")
            self.scan_btn.setEnabled(False)
            self.scan_btn.setStyleSheet(
                "QPushButton { background: #FF9500; color: white; border: none; "
                "border-radius: 8px; padding: 12px 24px; font-size: 14px; font-weight: 600; }",
            )
        else:
            self.scan_btn.setText("Scan for Hardware")
            self.scan_btn.setEnabled(True)
            self.scan_btn.setStyleSheet(
                "QPushButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                "stop:0 #007AFF, stop:1 #0051D5); color: white; border: none; "
                "border-radius: 8px; padding: 12px 24px; font-size: 14px; font-weight: 600; }"
                "QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                "stop:0 #0051D5, stop:1 #003D99); }",
            )

    def set_export_enabled(self, enabled: bool):
        """Enable/disable export button (encapsulates internal implementation).

        Args:
            enabled: True to enable, False to disable

        """
        if hasattr(self, "export_data_btn"):
            self.export_data_btn.setEnabled(enabled)

    def set_polarizer_mode(self, mode: str):
        """Update polarizer toggle button text (encapsulates internal implementation).

        Args:
            mode: Current polarizer mode ('S' or 'P')

        """
        if hasattr(self, "polarizer_toggle_btn"):
            self.polarizer_toggle_btn.setText(f"Current: {mode}-Mode")

    def set_operation_mode(self, mode: str):
        """Set the active operation mode (method or flow) and update tab states."""
        if mode.lower() == "method":
            # Enable Method, disable Flow
            self.tab_widget.setTabEnabled(self.tab_indices["Method"], True)
            self.tab_widget.setTabEnabled(self.tab_indices["Flow"], False)
            self.tab_widget.setTabToolTip(
                self.tab_indices["Flow"],
                "Flow mode unavailable - requires pump hardware",
            )
        elif mode.lower() == "flow":
            # Enable Flow, disable Method
            self.tab_widget.setTabEnabled(self.tab_indices["Flow"], True)
            self.tab_widget.setTabEnabled(self.tab_indices["Method"], False)
            self.tab_widget.setTabToolTip(
                self.tab_indices["Method"],
                "Method mode unavailable - flow mode active",
            )
        else:
            # Enable both (default fallback)
            self.tab_widget.setTabEnabled(self.tab_indices["Method"], True)
            self.tab_widget.setTabEnabled(self.tab_indices["Flow"], True)

    def set_operation_mode_availability(self, static_available: bool, flow_available: bool):
        """Update operation mode indicators in Device Status tab.

        Args:
            static_available: True if static mode is available
            flow_available: True if flow mode is available
        """
        if "static" in self.operation_modes:
            indicator = self.operation_modes["static"]["indicator"]
            status_label = self.operation_modes["static"]["status_label"]
            if static_available:
                indicator.setStyleSheet("color: #34C759; font-size: 16px;")
                status_label.setText("Available")
                status_label.setStyleSheet("font-size: 12px; color: #34C759;")
            else:
                indicator.setStyleSheet("color: #86868B; font-size: 16px;")
                status_label.setText("Disabled")
                status_label.setStyleSheet("font-size: 12px; color: #86868B;")

        if "flow" in self.operation_modes:
            indicator = self.operation_modes["flow"]["indicator"]
            status_label = self.operation_modes["flow"]["status_label"]
            if flow_available:
                indicator.setStyleSheet("color: #34C759; font-size: 16px;")
                status_label.setText("Available")
                status_label.setStyleSheet("font-size: 12px; color: #34C759;")
            else:
                indicator.setStyleSheet("color: #86868B; font-size: 16px;")
                status_label.setText("Disabled")
                status_label.setStyleSheet("font-size: 12px; color: #86868B;")

    def _build_device_status_tab(self, tab_layout: QVBoxLayout):
        """Build Device Status tab with hardware and subunit indicators using builder."""
        builder = DeviceStatusTabBuilder(self)
        builder.build(tab_layout)

    def _build_graphic_control_tab(self, tab_layout: QVBoxLayout):
        """Build Graphic Control tab with plots, axes, filters, and accessibility using builder."""
        builder = GraphicControlTabBuilder(self)
        builder.build(tab_layout)

    def _build_method_tab(self, tab_layout: QVBoxLayout):
        """Build Method tab with cycle management using builder."""
        self.method_tab_builder = MethodTabBuilder(self)
        self.method_tab_builder.build(tab_layout)

    def _build_flow_tab(self, tab_layout: QVBoxLayout):
        """Build Flow tab with pump controls and cycle management using builder."""
        builder = FlowTabBuilder(self)
        builder.build(tab_layout)

    def _open_cycle_table_dialog(self):
        """Open the full cycle table dialog showing completed cycles.

        Displays all completed cycles from _completed_cycles list with
        same column structure as Edits tab cycle_data_table.
        """
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton
        from affilabs.utils.logger import logger

        # DEBUG: Check what data we have
        if hasattr(self, 'app') and self.app and hasattr(self.app, '_completed_cycles'):
            cycles = self.app._completed_cycles
            logger.info(f"📊 Opening Cycle Data Table - Found {len(cycles)} completed cycles")
            for i, cycle in enumerate(cycles):
                logger.debug(f"  Cycle {i+1}: {cycle.cycle_type} - {cycle.notes}")
        else:
            logger.error("❌ Cannot access _completed_cycles - app reference not set!")
            if not hasattr(self, 'app'):
                logger.error("  self.app does not exist")
            elif not self.app:
                logger.error("  self.app is None")
            elif not hasattr(self.app, '_completed_cycles'):
                logger.error("  self.app has no _completed_cycles attribute")

        # Create simple dialog showing cycle data
        dialog = QDialog(self)
        dialog.setWindowTitle("Cycle Data Table - COMPLETED CYCLES ONLY")
        dialog.resize(1000, 600)

        layout = QVBoxLayout()

        # Create table matching Edits tab structure
        table = QTableWidget()
        table.setColumnCount(11)
        table.setHorizontalHeaderLabels([
            "Type", "Duration", "Start", "Conc.", "Units",
            "Notes", "ΔSPR", "Inj.", "Flags", "Channel", "Shift"
        ])

        # Populate table with completed cycles from Application instance
        if hasattr(self, 'app') and self.app and hasattr(self.app, '_completed_cycles'):
            cycles = self.app._completed_cycles
            table.setRowCount(len(cycles))

            for row, cycle in enumerate(cycles):
                # Format concentrations dict as string (e.g., "A:100, B:50")
                if cycle.concentrations:
                    conc_str = ", ".join(
                        f"{ch}:{val}" for ch, val in sorted(cycle.concentrations.items())
                    )
                else:
                    conc_str = ""

                # Format notes with cycle_id prefix
                notes_text = f"[ID:{cycle.cycle_id}] {cycle.notes}" if cycle.notes else f"[ID:{cycle.cycle_id}]"

                # Format injection flag
                injection_text = "Yes" if cycle.injection else "No"

                # Add row data
                table.setItem(row, 0, QTableWidgetItem(cycle.cycle_type))
                table.setItem(row, 1, QTableWidgetItem(str(cycle.duration)))
                table.setItem(row, 2, QTableWidgetItem(cycle.start_time))
                table.setItem(row, 3, QTableWidgetItem(conc_str))
                table.setItem(row, 4, QTableWidgetItem(cycle.units or ""))
                table.setItem(row, 5, QTableWidgetItem(notes_text))
                table.setItem(row, 6, QTableWidgetItem(f"{cycle.delta_spr:.2f}" if cycle.delta_spr is not None else ""))
                table.setItem(row, 7, QTableWidgetItem(injection_text))
                table.setItem(row, 8, QTableWidgetItem(cycle.flags or ""))
                table.setItem(row, 9, QTableWidgetItem(cycle.channel or ""))
                table.setItem(row, 10, QTableWidgetItem(f"{cycle.shift:.2f}" if cycle.shift is not None else ""))

        # Resize columns to content
        table.resizeColumnsToContents()

        layout.addWidget(table)

        # Add close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)

        dialog.setLayout(layout)
        dialog.exec()

    def _build_export_tab(self, tab_layout: QVBoxLayout):
        """Build Export tab with data export options using builder."""
        self.export_tab_builder = ExportTabBuilder(self)
        self.export_tab_builder.build(tab_layout)

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

    def _build_spark_tab(self, tab_layout: QVBoxLayout):
        """Build Spark AI Help tab placeholder — actual widget loads on first visit."""
        # Defer SparkHelpWidget creation until user clicks the Spark tab
        # (importing affilabs.services.spark pulls in torch/transformers/tinydb)
        self._spark_tab_layout = tab_layout
        self._spark_loaded = False
        placeholder = QLabel("Loading Spark AI…")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(
            "color: #86868B; font-size: 13px; font-style: italic; background: transparent;"
        )
        tab_layout.addWidget(placeholder, stretch=1)

    def _on_tab_changed(self, index: int):
        """Handle tab change events — lazy-load Spark tab on first visit."""
        spark_index = self.tab_indices.get("⚡")
        if index == spark_index and not getattr(self, "_spark_loaded", True):
            self._spark_loaded = True
            layout = self._spark_tab_layout
            # Remove placeholder
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            # Build the real Spark widget
            from affilabs.widgets.spark_help_widget import SparkHelpWidget
            self.spark_widget = SparkHelpWidget()
            layout.addWidget(self.spark_widget, stretch=1)

    def _build_deferred_spectroscopy_plots(self):
        """Build spectroscopy plots on-demand when Settings tab is first opened."""
        from plot_helpers import add_channel_curves, create_spectroscopy_plot

        from affilabs.utils.logger import logger

        if (
            not hasattr(self, "_spectroscopy_placeholder")
            or not self._spectroscopy_placeholder
        ):
            return

        # Clear placeholder text
        placeholder_section = self._spectroscopy_placeholder
        content_layout = placeholder_section.content_layout

        # Remove placeholder label
        while content_layout.count():
            item = content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add actual plots
        spectro_help = QLabel(
            "Real-time transmission and raw detector spectrum display",
        )
        spectro_help.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "margin: 4px 0px 8px 0px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        content_layout.addWidget(spectro_help)

        # Card container
        spectro_card = QFrame()
        spectro_card.setStyleSheet(
            "QFrame {  background: rgba(0, 0, 0, 0.03);  border-radius: 8px;}",
        )
        spectro_card_layout = QVBoxLayout(spectro_card)
        spectro_card_layout.setContentsMargins(12, 8, 12, 8)
        spectro_card_layout.setSpacing(8)

        # Transmission Plot
        trans_label = QLabel("Transmission Spectrum (%):")
        trans_label.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        spectro_card_layout.addWidget(trans_label)

        self.transmission_plot = create_spectroscopy_plot(
            left_label="Transmission (norm.)",
            bottom_label="Wavelength (nm)",
            detector_type=self.detector_type,
        )
        self.transmission_plot.setFixedHeight(180)
        self.transmission_plot.setMinimumHeight(180)
        spectro_card_layout.addWidget(self.transmission_plot)

        self.transmission_curves = add_channel_curves(self.transmission_plot)

        # Add Baseline Capture button (created in __init__ for immediate access)
        spectro_card_layout.addWidget(self.baseline_capture_btn)

        spectro_card_layout.addSpacing(12)

        # Raw Data Plot
        raw_label = QLabel("Raw Detector Signal (counts):")
        raw_label.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        spectro_card_layout.addWidget(raw_label)

        self.raw_data_plot = create_spectroscopy_plot(
            left_label="Intensity (counts)",
            bottom_label="Wavelength (nm)",
            detector_type=self.detector_type,
        )
        self.raw_data_plot.setFixedHeight(180)
        self.raw_data_plot.setMinimumHeight(180)
        spectro_card_layout.addWidget(self.raw_data_plot)

        self.raw_data_curves = add_channel_curves(self.raw_data_plot)

        content_layout.addWidget(spectro_card)

        logger.info(
            "[OK] Spectroscopy plots created: transmission=4 curves, raw=4 curves",
        )

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

    def set_detector_type(self, detector_type: str):
        """Update detector type and adjust spectroscopy plot ranges.

        Args:
            detector_type: Detector type ("USB4000", "PhasePhotonics", or serial starting with "ST")
        """
        self.detector_type = detector_type

        # Update x-axis range for both plots
        if hasattr(self, 'transmission_plot'):
            if "Phase" in detector_type or "ST" in detector_type:
                self.transmission_plot.setXRange(570, 720, padding=0)
            else:
                self.transmission_plot.setXRange(560, 720, padding=0)

        if hasattr(self, 'raw_data_plot'):
            if "Phase" in detector_type or "ST" in detector_type:
                self.raw_data_plot.setXRange(570, 720, padding=0)
            else:
                self.raw_data_plot.setXRange(560, 720, padding=0)

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
            s_pos: S-mode servo position (0-255 PWM)
            p_pos: P-mode servo position (0-255 PWM)
            led_a: Channel A LED brightness (0-255)
            led_b: Channel B LED brightness (0-255)
            led_c: Channel C LED brightness (0-255)
            led_d: Channel D LED brightness (0-255)

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

    # ===================================================================
    # FACADE METHODS - Cycle Configuration (Encapsulation Layer)
    # ===================================================================
    # These methods provide a clean interface for getting/setting cycle
    # configuration without exposing internal widget structure.
    # External code should use these instead of accessing widgets directly.

    def get_cycle_configuration(self) -> "CycleConfigViewModel":
        """Get current cycle configuration as view model (ENCAPSULATED).

        This is the preferred way for external code to read cycle settings.
        Returns a data object rather than exposing widget references.

        Returns:
            CycleConfigViewModel with current configuration

        """
        from viewmodels import CycleConfigViewModel

        # Extract cycle type
        cycle_type = "Auto-read"  # default
        if hasattr(self, "cycle_type_combo"):
            cycle_type = self.cycle_type_combo.currentText()

        # Extract cycle length (parse "5 min" -> 5)
        cycle_length_min = 5  # default
        if hasattr(self, "cycle_length_combo"):
            length_text = self.cycle_length_combo.currentText()
            try:
                cycle_length_min = int(length_text.split()[0])
            except (ValueError, IndexError):
                cycle_length_min = 5

        # Extract note
        note = ""
        if hasattr(self, "note_input"):
            note = self.note_input.toPlainText()

        # Extract units (parse "nM (Nanomolar)" -> "nM")
        units = "nM"  # default
        if hasattr(self, "units_combo"):
            units_text = self.units_combo.currentText()
            units = units_text.split()[0]  # Extract prefix before space

        return CycleConfigViewModel(
            cycle_type=cycle_type,
            cycle_length_min=cycle_length_min,
            note=note,
            units=units,
        )

    def set_cycle_configuration(self, config: "CycleConfigViewModel"):
        """Set cycle configuration from view model (ENCAPSULATED).

        This is the preferred way for external code to update cycle settings.
        Accepts a data object rather than requiring widget manipulation.

        Args:
            config: CycleConfigViewModel with desired configuration

        """
        # Set cycle type
        if hasattr(self, "cycle_type_combo"):
            index = self.cycle_type_combo.findText(config.cycle_type)
            if index >= 0:
                self.cycle_type_combo.setCurrentIndex(index)

        # Set cycle length (convert 5 -> "5 min")
        if hasattr(self, "cycle_length_combo"):
            length_text = f"{config.cycle_length_min} min"
            index = self.cycle_length_combo.findText(length_text)
            if index >= 0:
                self.cycle_length_combo.setCurrentIndex(index)

        # Set note
        if hasattr(self, "note_input"):
            self.note_input.setPlainText(config.note)

        # Set units (find matching display name)
        if hasattr(self, "units_combo"):
            display_name = config.get_units_display_name()
            index = self.units_combo.findText(display_name)
            if index >= 0:
                self.units_combo.setCurrentIndex(index)

    def validate_cycle_configuration(self) -> tuple[bool, list[str]]:
        """Validate current cycle configuration.

        Returns:
            Tuple of (is_valid, error_messages)

        """
        config = self.get_cycle_configuration()
        errors = config.validate()
        return (len(errors) == 0, errors)

    def clear_cycle_configuration(self):
        """Reset cycle configuration to defaults."""
        default_config = CycleConfigViewModel()
        self.set_cycle_configuration(default_config)


# ===================================================================
# COMPATIBILITY ALIAS
# ===================================================================
# LL_UI_v1_0.py imports "SidebarPrototype" but we renamed to "AffilabsSidebar"
# This alias maintains backward compatibility without changing all imports
SidebarPrototype = AffilabsSidebar
