"""Method Tab Builder for AffiLabs.core Sidebar

Builds the Method (Assay Builder) tab with:
- Intelligence Bar (real-time system status)
- Cycle Configuration (type, length, notes with syntax highlighting, units)
- Execution controls (Start Cycle, Add to Queue)
- Cycle History & Queue table
- Full cycle table dialog

The Method sidebar is the main interface for building and managing SPR assays.
Extracted from sidebar.py to improve modularity.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from affilabs.sections import CollapsibleSection
from affilabs.ui_styles import card_style, section_header_style, Colors, Fonts
from affilabs.widgets.queue_summary_widget import QueueSummaryWidget
from affilabs.widgets.scrolling_label import ScrollingLabel
from affilabs.widgets.ui_constants import CycleTypeStyle
from affilabs.services.user_profile_manager import UserProfileManager


class MethodTabBuilder:
    """Builds the Method (Assay Builder) tab content."""

    def __init__(self, sidebar):
        """Initialize builder.

        Args:
            sidebar: Reference to parent AffilabsSidebar instance

        """
        self.sidebar = sidebar
        # Use shared instance from sidebar (will be set by main app)
        self.user_manager = None
        self._app_reference = None

    def set_app_reference(self, app):
        """Set reference to main application for accessing segment_queue.

        Args:
            app: Main application instance
        """
        self._app_reference = app

    def build(self, tab_layout: QVBoxLayout):
        """Build Method tab with cycle management and queue.

        Args:
            tab_layout: QVBoxLayout to add widgets to

        """
        self._build_intelligence_bar(tab_layout)
        self._build_cycle_settings(tab_layout)
        self._build_cycle_history_queue(tab_layout)

    def _build_intelligence_bar(self, tab_layout: QVBoxLayout):
        """Build intelligence bar section."""
        intel_section = QLabel("INTELLIGENCE BAR")
        intel_section.setStyleSheet(section_header_style())
        intel_section.setFixedHeight(20)
        intel_section.setToolTip(
            "Real-time system status and guidance powered by AI diagnostics",
        )
        tab_layout.addWidget(intel_section)
        tab_layout.addSpacing(8)

        intel_bar = QFrame()
        intel_bar.setStyleSheet(
            "QFrame {  background: transparent;  border: none;}",
        )
        intel_bar_layout = QHBoxLayout(intel_bar)
        intel_bar_layout.setContentsMargins(16, 12, 16, 8)
        intel_bar_layout.setSpacing(12)

        # Status indicators
        self.sidebar.intel_status_label = QLabel("✓ Good")
        self.sidebar.intel_status_label.setStyleSheet(
            "font-size: 12px;"
            "color: #34C759;"
            "background: transparent;"
            "font-weight: 700;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        intel_bar_layout.addWidget(self.sidebar.intel_status_label)

        # Separator bullet
        self.sidebar.intel_separator = QLabel("•")
        self.sidebar.intel_separator.setStyleSheet(
            "font-size: 12px;color: #86868B;background: transparent;",
        )
        intel_bar_layout.addWidget(self.sidebar.intel_separator)

        self.sidebar.intel_message_label = QLabel("→ Ready for injection")
        self.sidebar.intel_message_label.setStyleSheet(
            "font-size: 12px;"
            "color: #007AFF;"
            "background: transparent;"
            "font-weight: 600;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        intel_bar_layout.addWidget(self.sidebar.intel_message_label)

        intel_bar_layout.addStretch()

        tab_layout.addWidget(intel_bar)

        # Queue progress bar removed - was visually unappealing
        # tab_layout.addSpacing(8)

    def _build_cycle_settings(self, tab_layout: QVBoxLayout):
        """Build method builder section (replaced with button to open popup)."""
        # Container for Build Method section
        from PySide6.QtWidgets import QFrame

        method_container = QFrame()
        method_container.setStyleSheet(
            "QFrame {"
            "  background: transparent;"
            "  border: none;"
            "  padding: 0px;"
            "}"
        )
        method_layout = QVBoxLayout(method_container)
        method_layout.setContentsMargins(0, 0, 0, 0)
        method_layout.setSpacing(0)

        # Build Method button
        self.sidebar.build_method_btn = QPushButton("➕ Build Method")
        self.sidebar.build_method_btn.setFixedHeight(32)
        self.sidebar.build_method_btn.setStyleSheet(
            "QPushButton {"
            "  background: #007AFF;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 6px 12px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #0051D5;"
            "}"
            "QPushButton:pressed {"
            "  background: #003D99;"
            "}"
        )
        self.sidebar.build_method_btn.setToolTip("Open method builder to create and queue cycles")
        method_layout.addWidget(self.sidebar.build_method_btn)

        # Add container to main layout
        tab_layout.addWidget(method_container)
        tab_layout.addSpacing(12)

    def _build_cycle_history_queue(self, tab_layout: QVBoxLayout):
        """Build cycle queue management section."""

        # Hidden widgets for compatibility (method name & operator now in popup)
        self.sidebar.method_name_label = QLabel("Untitled Method")
        self.sidebar.method_name_label.setVisible(False)
        self.sidebar.user_combo = QComboBox()

        # Get shared user manager from sidebar (set by main app)
        if hasattr(self.sidebar, 'user_profile_manager') and self.sidebar.user_profile_manager:
            self.user_manager = self.sidebar.user_profile_manager

        if self.user_manager:
            self.sidebar.user_combo.addItems(self.user_manager.get_profiles())
            current_user = self.user_manager.get_current_user()
            if current_user:
                index = self.sidebar.user_combo.findText(current_user)
                if index >= 0:
                    self.sidebar.user_combo.setCurrentIndex(index)
        self.sidebar.user_combo.currentTextChanged.connect(self._on_user_changed)
        self.sidebar.user_combo.setVisible(False)

        # Info banner about completed cycles
        self.sidebar.completed_cycles_info = QFrame()
        self.sidebar.completed_cycles_info.setStyleSheet(
            "QFrame {"
            "  background: rgba(142, 142, 147, 0.08);"
            "  border: none;"
            "  border-radius: 0px;"
            "}"
        )
        info_layout = QHBoxLayout(self.sidebar.completed_cycles_info)
        info_layout.setContentsMargins(10, 6, 10, 6)
        info_layout.setSpacing(8)

        info_icon = QLabel("ℹ️")
        info_icon.setStyleSheet("background: transparent; font-size: 12px;")
        info_layout.addWidget(info_icon)

        info_label = QLabel("Completed cycles appear in the Edit tab")
        info_label.setStyleSheet(
            "font-size: 11px;"
            "font-weight: 500;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        info_layout.addWidget(info_label)
        info_layout.addStretch()

        tab_layout.addWidget(self.sidebar.completed_cycles_info)
        tab_layout.addSpacing(4)

        # Queue status row
        queue_status_row = QHBoxLayout()
        queue_status_row.setSpacing(12)

        self.sidebar.queue_status_label = ScrollingLabel(
            "Queue: 0 cycles | Click 'Build Method' to plan batch runs",
        )
        self.sidebar.queue_status_label.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        # Configure scroll speed (adjust these values to make it faster/slower)
        self.sidebar.queue_status_label.setScrollSpeed(30)  # milliseconds between updates
        self.sidebar.queue_status_label.setScrollStep(2)  # pixels per update
        queue_status_row.addWidget(self.sidebar.queue_status_label)

        # Clear Queue button
        self.sidebar.clear_queue_btn = QPushButton("🗑 Clear Queue")
        self.sidebar.clear_queue_btn.setFixedHeight(24)
        self.sidebar.clear_queue_btn.setVisible(False)
        self.sidebar.clear_queue_btn.setToolTip("Remove all cycles from queue")
        self.sidebar.clear_queue_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent;"
            "  color: #FF3B30;"
            "  border: 1px solid rgba(255, 59, 48, 0.3);"
            "  border-radius: 4px;"
            "  padding: 2px 8px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(255, 59, 48, 0.1);"
            "  border-color: #FF3B30;"
            "}"
            "QPushButton:pressed {"
            "  background: rgba(255, 59, 48, 0.2);"
            "}",
        )
        queue_status_row.addWidget(self.sidebar.clear_queue_btn)

        # Pause/Resume Queue button
        self.sidebar.pause_queue_btn = QPushButton("⏸ Pause Queue")
        self.sidebar.pause_queue_btn.setFixedHeight(24)
        self.sidebar.pause_queue_btn.setVisible(False)  # Hidden until queue is running
        self.sidebar.pause_queue_btn.setToolTip("Pause queue after current cycle completes")
        self.sidebar.pause_queue_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent;"
            "  color: #FF9500;"
            "  border: 1px solid rgba(255, 149, 0, 0.3);"
            "  border-radius: 4px;"
            "  padding: 2px 8px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(255, 149, 0, 0.1);"
            "  border-color: #FF9500;"
            "}"
            "QPushButton:pressed {"
            "  background: rgba(255, 149, 0, 0.2);"
            "}",
        )
        queue_status_row.addWidget(self.sidebar.pause_queue_btn)

        queue_status_row.addStretch()

        tab_layout.addLayout(queue_status_row)
        tab_layout.addSpacing(8)

        # Experiment Method section header
        experiment_label = QLabel("EXPERIMENT METHOD")
        experiment_label.setStyleSheet(
            f"color: {Colors.PRIMARY_TEXT}; font-size: 12px; font-weight: 700;"
            f"letter-spacing: 0.5px; background: transparent;"
            f"font-family: {Fonts.SYSTEM};"
        )
        tab_layout.addWidget(experiment_label)
        tab_layout.addSpacing(8)

        # Summary table card (directly on sidebar)
        self._build_summary_table(tab_layout)

    def _build_summary_table(self, parent_layout: QVBoxLayout):
        """Build summary table with cycle history using new QueueSummaryWidget."""
        summary_card = QFrame()
        summary_card.setStyleSheet(card_style())
        summary_card_layout = QVBoxLayout(summary_card)
        summary_card_layout.setContentsMargins(12, 8, 12, 8)
        summary_card_layout.setSpacing(8)

        # NEW: Queue Summary Widget with drag-drop support - styled to match original
        self.sidebar.summary_table = QueueSummaryWidget()
        self.sidebar.summary_table.setMaximumHeight(400)  # Expanded for 10 visible rows
        self.sidebar.summary_table.setMinimumHeight(400)
        self.sidebar.summary_table.setStyleSheet(
            "QTableWidget {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 6px;"
            "  gridline-color: rgba(0, 0, 0, 0.06);"
            "  font-size: 12px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QTableWidget::item {"
            "  padding: 8px 6px;"
            "  color: #1D1D1F;"
            "  border: none;"
            "}"
            "QTableWidget::item:selected {"
            "  background: rgba(0, 122, 255, 0.12);"
            "  color: #1D1D1F;"
            "}"
            "QTableWidget::item:hover {"
            "  background: rgba(0, 0, 0, 0.03);"
            "}"
            "QHeaderView::section {"
            "  background: #F5F5F7;"
            "  color: #86868B;"
            "  padding: 8px 6px;"
            "  border: none;"
            "  border-bottom: 1px solid rgba(0, 0, 0, 0.1);"
            "  font-weight: 700;"
            "  font-size: 11px;"
            "  text-transform: uppercase;"
            "  letter-spacing: 0.5px;"
            "}"
            "QScrollBar:vertical {"
            "  background: transparent;"
            "  width: 6px;"
            "  border-radius: 3px;"
            "  margin: 2px 0px;"
            "}"
            "QScrollBar::handle:vertical {"
            "  background: rgba(0, 0, 0, 0.15);"
            "  border-radius: 3px;"
            "  min-height: 20px;"
            "}"
            "QScrollBar::handle:vertical:hover {"
            "  background: rgba(0, 0, 0, 0.25);"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            "  height: 0px;"
            "}"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {"
            "  background: transparent;"
            "}"
        )

        summary_card_layout.addWidget(self.sidebar.summary_table)

        # Queue control buttons (Start, Pause, Next, Duplicate)
        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        self.sidebar.start_queue_btn = QPushButton("▶ Start Run")
        self.sidebar.start_queue_btn.setFixedHeight(32)
        self.sidebar.start_queue_btn.setToolTip("Start executing the queued cycles")
        self.sidebar.start_queue_btn.setProperty("mode", "start")  # Initialize in start mode
        self.sidebar.start_queue_btn.setStyleSheet(
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
        controls_row.addWidget(self.sidebar.start_queue_btn)

        self.sidebar.duplicate_last_btn = QPushButton("+ Duplicate")
        self.sidebar.duplicate_last_btn.setFixedHeight(32)
        self.sidebar.duplicate_last_btn.setToolTip("Quickly duplicate the last cycle (useful for repetitive testing)")
        self.sidebar.duplicate_last_btn.setStyleSheet(
            "QPushButton {"
            "  background: #FF9500;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 6px 16px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover { background: #E68A00; }"
            "QPushButton:pressed { background: #CC7700; }"
            "QPushButton:disabled { background: #C7C7CC; }"
        )
        # Connect to the main window's duplicate_last_cycle method
        self.sidebar.duplicate_last_btn.clicked.connect(self._on_duplicate_last)
        controls_row.addWidget(self.sidebar.duplicate_last_btn)

        self.sidebar.next_cycle_btn = QPushButton("⏭ Next Cycle")
        self.sidebar.next_cycle_btn.setFixedHeight(32)
        self.sidebar.next_cycle_btn.setEnabled(False)
        self.sidebar.next_cycle_btn.setToolTip("Skip to the next cycle")
        self.sidebar.next_cycle_btn.setStyleSheet(
            "QPushButton {"
            "  background: #007AFF;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 6px 16px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover { background: #0051D5; }"
            "QPushButton:pressed { background: #003D99; }"
            "QPushButton:disabled { background: #C7C7CC; }"
        )
        controls_row.addWidget(self.sidebar.next_cycle_btn)

        summary_card_layout.addLayout(controls_row)
        summary_card_layout.addSpacing(8)

        # Table footer
        table_footer_row = QHBoxLayout()
        table_footer_row.setSpacing(10)

        self.sidebar.queue_size_label = QLabel("0 cycles queued")
        self.sidebar.queue_size_label.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        table_footer_row.addWidget(self.sidebar.queue_size_label)
        table_footer_row.addStretch()

        # View All Cycles Button
        self.sidebar.open_table_btn = QPushButton("📊 View All")
        self.sidebar.open_table_btn.setFixedHeight(28)
        self.sidebar.open_table_btn.setToolTip("View all completed/recorded cycles")
        self.sidebar.open_table_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent;"
            "  color: #636366;"
            "  border: 1px solid rgba(99, 99, 102, 0.3);"
            "  border-radius: 6px;"
            "  padding: 4px 12px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(99, 99, 102, 0.08);"
            "  border-color: #636366;"
            "}"
            "QPushButton:pressed {"
            "  background: rgba(99, 99, 102, 0.15);"
            "}",
        )
        table_footer_row.addWidget(self.sidebar.open_table_btn)

        summary_card_layout.addLayout(table_footer_row)

        parent_layout.addWidget(summary_card)

        # Connect button signal
        self.sidebar.open_table_btn.clicked.connect(self._open_cycle_table_dialog)

    def _open_cycle_table_dialog(self):
        """Open the full cycle table dialog for reviewing completed/recorded cycles.

        Shows all cycles that have been completed and recorded (not the queue).
        This is the same as the Cycle Data Table accessible from the main window.
        """
        from affilabs.utils.logger import logger

        # Get access to main window from app reference
        if not hasattr(self, '_app_reference'):
            logger.warning("Cannot open cycle table - no app reference")
            return

        app = self._app_reference
        if not hasattr(app, 'main_window'):
            logger.warning("Cannot open cycle table - no main_window")
            return

        # Switch to Edits tab to show cycle data table
        # This shows completed/recorded cycles, not the queue
        # Edits tab is always at index 1 in content_stack (Sensorgram=0, Edits=1, Analyze=2, Report=3)
        if hasattr(app.main_window, 'navigation_presenter'):
            app.main_window.navigation_presenter.switch_page(1)  # Edits tab - this also highlights the nav button
            logger.info("📊 Switched to Edits tab (Cycle Data Table)")
        elif hasattr(app.main_window, 'content_stack'):
            app.main_window.content_stack.setCurrentIndex(1)  # Fallback if no navigation presenter
            logger.info("📊 Switched to Edits tab (Cycle Data Table)")
        else:
            logger.warning("Cannot open cycle table - main_window missing content_stack")

    def _on_duplicate_last(self):
        """Duplicate the last cycle in the queue via queue_presenter."""
        from affilabs.utils.logger import logger
        import time as _time

        if not hasattr(self, '_app_reference') or self._app_reference is None:
            logger.warning("Cannot duplicate cycle - no app reference")
            return

        app = self._app_reference
        if not hasattr(app, 'queue_presenter'):
            logger.warning("Cannot duplicate cycle - no queue_presenter")
            return

        # Get current queue snapshot
        queue = app.queue_presenter.get_queue_snapshot()
        if not queue:
            logger.warning("No cycles in queue to duplicate")
            return

        last_cycle = queue[-1]

        # Create a fresh Cycle with the same config fields, reset runtime state
        from affilabs.domain.cycle import Cycle
        new_cycle = Cycle(
            type=last_cycle.type,
            length_minutes=last_cycle.length_minutes,
            name=last_cycle.name,
            note=last_cycle.note,
            concentration_value=last_cycle.concentration_value,
            concentration_units=last_cycle.concentration_units,
            units=last_cycle.units,
            concentrations=dict(last_cycle.concentrations) if last_cycle.concentrations else {},
            flow_rate=last_cycle.flow_rate,
            pump_type=last_cycle.pump_type,
            channels=last_cycle.channels,
            injection_method=last_cycle.injection_method,
            injection_delay=last_cycle.injection_delay,
            contact_time=last_cycle.contact_time,
            manual_injection_mode=last_cycle.manual_injection_mode,
            planned_concentrations=list(last_cycle.planned_concentrations),
            status="pending",
            timestamp=_time.time(),
        )

        success = app.queue_presenter.add_cycle(new_cycle)
        if success:
            # Sync backward compatibility list
            app.segment_queue = app.queue_presenter.get_queue_snapshot()
            logger.info(f"✓ Duplicated last cycle: {new_cycle.type} ({new_cycle.length_minutes} min)")
        else:
            logger.warning("Failed to duplicate cycle (queue may be locked)")

    def _combo_style(self):
        """Return consistent combobox style."""
        return (
            "QComboBox {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-size: 12px;"
            "  color: #1D1D1F;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QComboBox:focus {"
            "  border: 2px solid #1D1D1F;"
            "}"
            "QComboBox::drop-down {"
            "  border: none;"
            "  width: 20px;"
            "}"
            "QComboBox QAbstractItemView {"
            "  background-color: white;"
            "  color: #1D1D1F;"
            "  selection-background-color: rgba(0, 0, 0, 0.1);"
            "  selection-color: #1D1D1F;"
            "  outline: none;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "}"
        )

    def _on_user_changed(self, user_name: str):
        """Handle user selection change.

        Args:
            user_name: Selected user name

        """
        if user_name and user_name != "Select User...":
            # Use shared instance instead of creating new one
            if self.user_manager:
                self.user_manager.set_current_user(user_name)

            # Update export destination to user-specific folder
            from pathlib import Path
            if hasattr(self.sidebar, 'export_dest_input'):
                user_path = str(Path.home() / "Documents" / "Affilabs Data" / user_name / "SPR_data")
                Path(user_path).mkdir(parents=True, exist_ok=True)
                self.sidebar.export_dest_input.setText(user_path)
