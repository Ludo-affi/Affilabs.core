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

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from affilabs.ui_styles import card_style
from affilabs.widgets.queue_summary_widget import QueueSummaryWidget
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

    @staticmethod
    def _create_svg_icon(svg_string: str, icon_size: int = 18) -> QIcon:
        """Create QIcon from SVG string.

        Args:
            svg_string: SVG markup as string
            icon_size: Size of the icon in pixels

        Returns:
            QIcon with rendered SVG
        """
        svg_renderer = QSvgRenderer(svg_string.encode('utf-8'))
        pixmap = QPixmap(icon_size, icon_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        svg_renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    @staticmethod
    def _create_play_icon() -> QIcon:
        """Create play/start icon."""
        svg = '''<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
            <path d="M8 5v14l11-7z" fill="white"/>
        </svg>'''
        return MethodTabBuilder._create_svg_icon(svg)

    @staticmethod
    def _create_stop_icon() -> QIcon:
        """Create stop icon."""
        svg = '''<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
            <rect x="6" y="6" width="12" height="12" fill="white" rx="2"/>
        </svg>'''
        return MethodTabBuilder._create_svg_icon(svg)

    @staticmethod
    def _create_duplicate_icon() -> QIcon:
        """Create duplicate/copy icon."""
        svg = '''<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" xmlns="http://www.w3.org/2000/svg">
            <rect x="3" y="3" width="14" height="14" rx="2"/>
            <path d="M21 15a2 2 0 0 1-2 2h-2v-4v-2a2 2 0 0 1 2-2h2v6z"/>
        </svg>'''
        return MethodTabBuilder._create_svg_icon(svg)

    @staticmethod
    def _create_skip_icon() -> QIcon:
        """Create skip/next icon."""
        svg = '''<svg viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg">
            <path d="M6 4v16l8-8-8-8z" fill="white"/>
            <path d="M15 4v16" stroke="white" stroke-width="2" fill="none"/>
        </svg>'''
        return MethodTabBuilder._create_svg_icon(svg)

    @staticmethod
    def _create_add_icon() -> QIcon:
        """Create add/plus icon."""
        svg = '''<svg viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 3v18M3 12h18" stroke="white" stroke-width="2" stroke-linecap="round" fill="none"/>
        </svg>'''
        return MethodTabBuilder._create_svg_icon(svg)

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
        self._build_build_method_cta(tab_layout)
        self._build_active_cycle_card(tab_layout)
        self._build_cycle_history_queue(tab_layout)

    def _build_active_cycle_card(self, tab_layout: QVBoxLayout):
        """Build Active Cycle status card — shown during runs, hidden at idle."""
        # Hidden compat labels (still written to by _update_cycle_display / _refresh_intelligence_bar)
        self.sidebar.intel_status_label = QLabel()
        self.sidebar.intel_status_label.setVisible(False)
        self.sidebar.intel_separator = QLabel()
        self.sidebar.intel_separator.setVisible(False)
        self.sidebar.intel_message_label = QLabel()
        self.sidebar.intel_message_label.setVisible(False)

        # Use pre-built card from sidebar._setup_ui() (Phase 2)
        self.sidebar.active_cycle_card.setVisible(False)
        self.sidebar.active_cycle_card.setStyleSheet(
            "QFrame {"
            "  background: #F0F4FF;"
            "  border: 1.5px solid rgba(46, 48, 227, 0.25);"
            "  border-radius: 10px;"
            "}"
        )
        card_layout = QVBoxLayout(self.sidebar.active_cycle_card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(5)

        # Section label
        running_lbl = QLabel("NOW RUNNING")
        running_lbl.setStyleSheet(
            "QLabel {"
            "  font-size: 9px;"
            "  font-weight: 700;"
            "  color: rgba(46, 48, 227, 0.7);"
            "  letter-spacing: 0.8px;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        card_layout.addWidget(running_lbl)

        # Row 1: cycle type badge + index + countdown
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self.sidebar.active_cycle_type_label = QLabel("Binding")
        self.sidebar.active_cycle_type_label.setStyleSheet(
            "QLabel {"
            "  background: #2E30E3;"
            "  color: white;"
            "  border-radius: 5px;"
            "  padding: 2px 8px;"
            "  font-size: 11px;"
            "  font-weight: 700;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        row1.addWidget(self.sidebar.active_cycle_type_label)

        self.sidebar.active_cycle_index_label = QLabel("Cycle 1/4")
        self.sidebar.active_cycle_index_label.setStyleSheet(
            "QLabel {"
            "  font-size: 11px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        row1.addWidget(self.sidebar.active_cycle_index_label)
        row1.addStretch()

        self.sidebar.active_cycle_countdown_label = QLabel("00:00")
        self.sidebar.active_cycle_countdown_label.setStyleSheet(
            "QLabel {"
            "  font-size: 17px;"
            "  font-weight: 700;"
            "  color: #2E30E3;"
            "  background: transparent;"
            "  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;"
            "}"
        )
        self.sidebar.active_cycle_countdown_label.setToolTip("Time remaining in current cycle")
        row1.addWidget(self.sidebar.active_cycle_countdown_label)

        card_layout.addLayout(row1)

        # Progress bar
        from PySide6.QtWidgets import QProgressBar
        self.sidebar.active_cycle_progress = QProgressBar()
        self.sidebar.active_cycle_progress.setFixedHeight(4)
        self.sidebar.active_cycle_progress.setRange(0, 100)
        self.sidebar.active_cycle_progress.setValue(0)
        self.sidebar.active_cycle_progress.setTextVisible(False)
        self.sidebar.active_cycle_progress.setStyleSheet(
            "QProgressBar {"
            "  background: rgba(46, 48, 227, 0.12);"
            "  border: none;"
            "  border-radius: 2px;"
            "}"
            "QProgressBar::chunk {"
            "  background: #2E30E3;"
            "  border-radius: 2px;"
            "}"
        )
        card_layout.addWidget(self.sidebar.active_cycle_progress)

        # Row 2: next cycle + total experiment time
        row2 = QHBoxLayout()
        row2.setSpacing(0)

        self.sidebar.active_next_cycle_label = QLabel()
        self.sidebar.active_next_cycle_label.setStyleSheet(
            "QLabel {"
            "  font-size: 10px;"
            "  color: #FF9500;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        self.sidebar.active_next_cycle_label.setVisible(False)
        row2.addWidget(self.sidebar.active_next_cycle_label)
        row2.addStretch()

        self.sidebar.active_experiment_time_label = QLabel()
        self.sidebar.active_experiment_time_label.setStyleSheet(
            "QLabel {"
            "  font-size: 10px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        row2.addWidget(self.sidebar.active_experiment_time_label)

        card_layout.addLayout(row2)

        # Card lives in the Method tab sidebar (not in LiveRightPanel)
        tab_layout.addWidget(self.sidebar.active_cycle_card)
        tab_layout.addSpacing(4)

    def _build_build_method_cta(self, tab_layout: QVBoxLayout):
        """Build prominent Build Method CTA at the top of the Method tab."""
        self.sidebar.build_method_btn = QPushButton("  Build Method")
        self.sidebar.build_method_btn.setFixedHeight(48)
        self.sidebar.build_method_btn.setStyleSheet(
            "QPushButton {"
            "  background: #007AFF;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 10px;"
            "  font-size: 15px;"
            "  font-weight: 700;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', sans-serif;"
            "  text-align: left;"
            "  padding-left: 16px;"
            "}"
            "QPushButton:hover { background: #0051D5; }"
            "QPushButton:pressed { background: #003D99; }"
            "QPushButton:disabled { background: #C7C7CC; color: #F2F2F7; }"
        )
        add_icon = self._create_add_icon()
        self.sidebar.build_method_btn.setIcon(add_icon)
        self.sidebar.build_method_btn.setIconSize(QSize(20, 20))
        self.sidebar.build_method_btn.setToolTip("Open method builder to create and queue cycles")
        tab_layout.addWidget(self.sidebar.build_method_btn)
        tab_layout.addSpacing(4)

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

        # Hidden compat label (queue_status_label still written to by external code)
        self.sidebar.queue_status_label = QLabel()
        self.sidebar.queue_status_label.setVisible(False)

        # Hidden compat buttons (still wired in signal connections elsewhere)
        self.sidebar.clear_queue_btn = QPushButton()
        self.sidebar.clear_queue_btn.setVisible(False)
        self.sidebar.clear_queue_btn.setToolTip("Remove all cycles from queue")
        self.sidebar.pause_queue_btn = QPushButton()
        self.sidebar.pause_queue_btn.setVisible(False)
        self.sidebar.pause_queue_btn.setToolTip("Pause queue after current cycle completes")

        # Hidden compat frame (referenced by external code)
        self.sidebar.completed_cycles_info = QFrame()
        self.sidebar.completed_cycles_info.setVisible(False)

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
        self.sidebar.summary_table.setMinimumHeight(200)
        self.sidebar.summary_table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
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

        self.sidebar.start_queue_btn = QPushButton("Start Run")
        self.sidebar.start_queue_btn.setFixedHeight(32)
        self.sidebar.start_queue_btn.setIcon(self._create_play_icon())
        self.sidebar.start_queue_btn.setIconSize(QSize(16, 16))
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

        self.sidebar.duplicate_last_btn = QPushButton("Duplicate")
        self.sidebar.duplicate_last_btn.setFixedHeight(32)
        self.sidebar.duplicate_last_btn.setIcon(self._create_duplicate_icon())
        self.sidebar.duplicate_last_btn.setIconSize(QSize(16, 16))
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

        self.sidebar.next_cycle_btn = QPushButton("Next Cycle")
        self.sidebar.next_cycle_btn.setFixedHeight(32)
        self.sidebar.next_cycle_btn.setIcon(self._create_skip_icon())
        self.sidebar.next_cycle_btn.setIconSize(QSize(16, 16))
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

        # Retrieve Method Button (restore queue after run completion)
        self.sidebar.retrieve_method_btn = QPushButton("↻ Retrieve Method")
        self.sidebar.retrieve_method_btn.setFixedHeight(28)
        self.sidebar.retrieve_method_btn.setVisible(False)  # Only show after run completes
        self.sidebar.retrieve_method_btn.setToolTip("Restore the completed method to queue for re-running")
        self.sidebar.retrieve_method_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent;"
            "  color: #007AFF;"
            "  border: 1px solid rgba(0, 122, 255, 0.3);"
            "  border-radius: 6px;"
            "  padding: 4px 12px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 122, 255, 0.08);"
            "  border-color: #007AFF;"
            "}"
            "QPushButton:pressed {"
            "  background: rgba(0, 122, 255, 0.15);"
            "}",
        )
        self.sidebar.retrieve_method_btn.clicked.connect(self._on_retrieve_method)
        table_footer_row.addWidget(self.sidebar.retrieve_method_btn)

        # Hidden compat reference (open_table_btn still connected in main.py signal wiring)
        self.sidebar.open_table_btn = QPushButton()
        self.sidebar.open_table_btn.setVisible(False)
        self.sidebar.open_table_btn.clicked.connect(self._open_cycle_table_dialog)

        summary_card_layout.addLayout(table_footer_row)

        # Queue panel is NOT added to the sidebar Method tab.
        # It is reparented into the collapsible right splitter pane by affilabs_core_ui.
        self.sidebar.queue_panel = summary_card

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

    def _on_retrieve_method(self):
        """Retrieve (restore) the completed method back to the queue for re-running."""
        from affilabs.utils.logger import logger

        if not hasattr(self, '_app_reference') or self._app_reference is None:
            logger.warning("Cannot retrieve method - no app reference")
            return

        app = self._app_reference
        if not hasattr(app, 'queue_presenter'):
            logger.warning("Cannot retrieve method - no queue_presenter")
            return

        # Check if there's a method snapshot to retrieve
        if not app.queue_presenter.has_method_snapshot():
            logger.warning("No method to retrieve - run a queued method first")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                None,
                "No Method to Retrieve",
                "There is no completed method to retrieve.\n\n"
                "This button appears after a queue run completes, allowing you to re-run the same method."
            )
            return

        # Get the original method from snapshot
        original_method = app.queue_presenter.get_original_method()

        if not original_method:
            logger.warning("Method snapshot is empty")
            return

        # Clear current queue first
        app.queue_presenter.clear_queue()

        # Re-add all cycles from the original method (as fresh copies)
        from affilabs.domain.cycle import Cycle
        import time as _time

        for cycle in original_method:
            # Create a fresh copy with reset state
            new_cycle = Cycle(
                type=cycle.type,
                length_minutes=cycle.length_minutes,
                name=cycle.name,
                note=cycle.note,
                concentration_value=cycle.concentration_value,
                concentration_units=cycle.concentration_units,
                units=cycle.units,
                concentrations=dict(cycle.concentrations) if cycle.concentrations else {},
                flow_rate=cycle.flow_rate,
                pump_type=cycle.pump_type,
                channels=cycle.channels,
                injection_method=cycle.injection_method,
                injection_delay=cycle.injection_delay,
                contact_time=cycle.contact_time,
                manual_injection_mode=cycle.manual_injection_mode,
                planned_concentrations=list(cycle.planned_concentrations),
                status="pending",
                timestamp=_time.time(),
            )
            app.queue_presenter.add_cycle(new_cycle)

        # Clear the snapshot now that it's been retrieved
        app.queue_presenter.clear_method_snapshot()

        # Hide the retrieve button
        self.sidebar.retrieve_method_btn.setVisible(False)

        # Sync backward compatibility list
        app.segment_queue = app.queue_presenter.get_queue_snapshot()

        logger.info(f"✓ Retrieved method: {len(original_method)} cycles restored to queue")

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
