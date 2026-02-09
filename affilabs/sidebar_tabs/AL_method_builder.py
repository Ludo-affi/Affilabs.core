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

from PySide6.QtCore import Qt, QRegularExpression
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
)

from affilabs.sections import CollapsibleSection
from affilabs.ui_styles import card_style, section_header_style, Colors, Fonts
from affilabs.widgets.queue_summary_widget import QueueSummaryWidget
from affilabs.widgets.ui_constants import CycleTypeStyle
from affilabs.services.user_profile_manager import UserProfileManager


class ResizableTableWidget(QTableWidget):
    """Table widget with resize handle at bottom for expanding/collapsing."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._min_height = 200
        self._max_height = 600
        self._is_resizing = False
        self._resize_start_pos = None
        self._resize_start_height = None

    def mousePressEvent(self, event):
        """Handle mouse press to start resize if near bottom edge."""
        # Only intercept left-clicks near bottom edge for resizing
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if click is near bottom edge (within 10 pixels)
            if abs(event.pos().y() - self.height()) <= 10:
                self._is_resizing = True
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_height = self.height()
                self.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))
                event.accept()
                return

        # Pass all other events (including right-clicks) to parent
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for resizing or cursor change."""
        if self._is_resizing:
            # Calculate new height
            delta = event.globalPosition().toPoint().y() - self._resize_start_pos.y()
            new_height = max(self._min_height, min(self._max_height, self._resize_start_height + delta))
            self.setMaximumHeight(new_height)
            self.setMinimumHeight(new_height)
            event.accept()
            return
        else:
            # Change cursor when hovering near bottom edge
            if abs(event.pos().y() - self.height()) <= 10:
                self.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))
            else:
                self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release to stop resizing."""
        if self._is_resizing:
            self._is_resizing = False
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ChannelTagHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for channel concentration tags and cycle type keywords."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tag_format = QTextCharFormat()
        self.tag_format.setForeground(QColor("#1D1D1F"))
        self.tag_format.setFontWeight(700)

        self.conc_format = QTextCharFormat()
        self.conc_format.setForeground(QColor("#34C759"))
        self.conc_format.setFontWeight(700)

        # Build cycle type formats from the shared constant
        self._type_formats: dict[str, QTextCharFormat] = {}
        for type_name, (_, color) in CycleTypeStyle.MAP.items():
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            fmt.setFontWeight(700)
            self._type_formats[type_name.lower()] = fmt

    def highlightBlock(self, text):
        # Highlight cycle type keywords at the start of lines (e.g. "Baseline 5min")
        for type_name, fmt in self._type_formats.items():
            pattern = QRegularExpression(
                rf"(?i)\b{type_name}\b"
            )
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)

        # Highlight [A:10], [B:50], [ALL:20] concentration tags (green)
        conc_pattern = QRegularExpression(r"\[(A|B|C|D|ALL):(\d+\.?\d*)\]")
        iterator = conc_pattern.globalMatch(text)
        while iterator.hasNext():
            match = iterator.next()
            self.setFormat(
                match.capturedStart(),
                match.capturedLength(),
                self.conc_format,
            )

        # Highlight [A], [B], [C], [D], [ALL] tags without concentration (dark)
        tag_pattern = QRegularExpression(r"\[(A|B|C|D|ALL)\]")
        iterator = tag_pattern.globalMatch(text)
        while iterator.hasNext():
            match = iterator.next()
            # Only highlight if not already highlighted as concentration
            start = match.capturedStart()
            if self.format(start).foreground().color() != QColor("#34C759"):
                self.setFormat(start, match.capturedLength(), self.tag_format)


class MethodTabBuilder:
    """Builds the Method (Assay Builder) tab content."""

    def __init__(self, sidebar):
        """Initialize builder.

        Args:
            sidebar: Reference to parent AffilabsSidebar instance

        """
        self.sidebar = sidebar
        self.user_manager = UserProfileManager()
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
        tab_layout.addWidget(self.sidebar.build_method_btn)
        tab_layout.addSpacing(12)

    def _build_note_input(self, parent_layout: QVBoxLayout):
        """Deprecated - note input now in Method Builder dialog."""
        pass

    def _build_units_row(self, parent_layout: QVBoxLayout):
        """Deprecated - units selector now in Method Builder dialog."""
        pass

    def _build_execution_section(self, parent_layout: QVBoxLayout):
        """Deprecated - execution buttons now in Method Builder dialog."""
        pass

    def _build_cycle_history_queue(self, tab_layout: QVBoxLayout):
        """Build cycle queue management section."""

        # Hidden widgets for compatibility (method name & operator now in popup)
        self.sidebar.method_name_label = QLabel("Untitled Method")
        self.sidebar.method_name_label.setVisible(False)
        self.sidebar.user_combo = QComboBox()
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
            "  border: 1px solid rgba(142, 142, 147, 0.18);"
            "  border-radius: 8px;"
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

        self.sidebar.queue_status_label = QLabel(
            "Queue: 0 cycles | Click 'Build Method' to plan batch runs",
        )
        self.sidebar.queue_status_label.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
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

        # Queue control buttons (Start, Pause, Next)
        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        self.sidebar.start_queue_btn = QPushButton("▶ Start Run")
        self.sidebar.start_queue_btn.setFixedHeight(32)
        self.sidebar.start_queue_btn.setToolTip("Start executing the queued cycles")
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
            # Get UserProfileManager instance
            from affilabs.services.user_profile_manager import UserProfileManager
            profile_manager = UserProfileManager()
            profile_manager.set_current_user(user_name)
