"""Static Tab Builder for AffiLabs.core Sidebar

Builds the Static Control tab with:
- Intelligence Bar (real-time system status)
- Cycle Configuration (type, length, notes with syntax highlighting, units)
- Execution controls (Start Cycle, Add to Queue)
- Cycle History & Queue table
- Full cycle table dialog

Extracted from sidebar.py to improve modularity.
"""

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from affilabs.cycle_table_dialog import CycleTableDialog
from affilabs.sections import CollapsibleSection
from affilabs.ui_styles import card_style, section_header_style


class ChannelTagHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for channel concentration tags."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tag_format = QTextCharFormat()
        self.tag_format.setForeground(QColor("#1D1D1F"))
        self.tag_format.setFontWeight(700)

        self.conc_format = QTextCharFormat()
        self.conc_format.setForeground(QColor("#34C759"))
        self.conc_format.setFontWeight(700)

    def highlightBlock(self, text):
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


class StaticTabBuilder:
    """Builds the Static (Cycle Control) tab content."""

    def __init__(self, sidebar):
        """Initialize builder.

        Args:
            sidebar: Reference to parent AffilabsSidebar instance

        """
        self.sidebar = sidebar

    def build(self, tab_layout: QVBoxLayout):
        """Build Static tab with cycle management and queue.

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
        intel_section.setFixedHeight(20)  # Reduced height from default 27 to 20
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

        # Countdown timer
        self.sidebar.countdown_label = QLabel("00:30")
        self.sidebar.countdown_label.setStyleSheet(
            "font-size: 11px;"
            "color: #1D1D1F;"
            "background: rgba(0, 0, 0, 0.06);"
            "padding: 2px 8px;"
            "border-radius: 4px;"
            "font-weight: 700;"
            "font-family: -apple-system, 'SF Mono', 'Menlo', monospace;",
        )
        intel_bar_layout.addWidget(self.sidebar.countdown_label)

        intel_bar_layout.addStretch()

        tab_layout.addWidget(intel_bar)
        tab_layout.addSpacing(8)

    def _build_cycle_settings(self, tab_layout: QVBoxLayout):
        """Build cycle configuration section."""
        cycle_settings_section = CollapsibleSection(
            "⚙ Configure Next Cycle",
            is_expanded=True,
        )

        cycle_settings_card = QFrame()
        cycle_settings_card.setStyleSheet(card_style(background="transparent"))
        cycle_settings_card_layout = QVBoxLayout(cycle_settings_card)
        cycle_settings_card_layout.setContentsMargins(10, 8, 10, 8)
        cycle_settings_card_layout.setSpacing(8)

        # Type row
        type_row = QHBoxLayout()
        type_row.setSpacing(8)
        type_label = QLabel("Type:")
        type_label.setFixedWidth(70)
        type_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        type_row.addWidget(type_label)

        self.sidebar.cycle_type_combo = QComboBox()
        self.sidebar.cycle_type_combo.addItems(
            ["Auto-read", "Baseline", "Immobilization", "Concentration"],
        )
        self.sidebar.cycle_type_combo.setCurrentIndex(0)
        self.sidebar.cycle_type_combo.setToolTip(
            "Select experiment type: Auto-read (automatic), Baseline (reference), Immobilization (binding), or Concentration (dose-response)",
        )
        self.sidebar.cycle_type_combo.setFixedWidth(140)
        self.sidebar.cycle_type_combo.setStyleSheet(self._combo_style())
        type_row.addWidget(self.sidebar.cycle_type_combo)
        type_row.addStretch()
        cycle_settings_card_layout.addLayout(type_row)

        # Length row
        length_row = QHBoxLayout()
        length_row.setSpacing(8)
        length_label = QLabel("Length:")
        length_label.setFixedWidth(70)
        length_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        length_row.addWidget(length_label)

        self.sidebar.cycle_length_combo = QComboBox()
        self.sidebar.cycle_length_combo.addItems(
            ["2 min", "5 min", "15 min", "30 min", "60 min"],
        )
        self.sidebar.cycle_length_combo.setCurrentIndex(1)
        self.sidebar.cycle_length_combo.setToolTip("Duration of the experiment cycle")
        self.sidebar.cycle_length_combo.setFixedWidth(100)
        self.sidebar.cycle_length_combo.setStyleSheet(self._combo_style())
        length_row.addWidget(self.sidebar.cycle_length_combo)
        length_row.addStretch()
        cycle_settings_card_layout.addLayout(length_row)

        # Note input
        self._build_note_input(cycle_settings_card_layout)

        # Units row
        self._build_units_row(cycle_settings_card_layout)

        # Execution section
        self._build_execution_section(cycle_settings_card_layout)

        cycle_settings_section.add_content_widget(cycle_settings_card)
        tab_layout.addWidget(cycle_settings_section)
        tab_layout.addSpacing(8)

    def _build_note_input(self, parent_layout: QVBoxLayout):
        """Build note input with syntax highlighting."""
        note_label = QLabel("Note:")
        note_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        parent_layout.addWidget(note_label)

        self.sidebar.note_input = QTextEdit()
        self.sidebar.note_input.setPlaceholderText(
            "Use tags: [A] [B] [C] [D] [ALL] or with concentration [A:10] [ALL:50]  (max 250 chars)",
        )
        self.sidebar.note_input.setMaximumHeight(60)
        self.sidebar.note_input.setStyleSheet(
            "QTextEdit {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 4px;"
            "  padding: 6px 8px;"
            "  font-size: 12px;"
            "  color: #1D1D1F;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QTextEdit:focus {"
            "  border: 2px solid #1D1D1F;"
            "}",
        )

        # Apply syntax highlighter
        self.sidebar.note_highlighter = ChannelTagHighlighter(
            self.sidebar.note_input.document(),
        )

        # Character counter
        self.sidebar.char_count_label = QLabel("0/250 characters")
        self.sidebar.char_count_label.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )

        def update_note_counter():
            text = self.sidebar.note_input.toPlainText()
            if len(text) > 250:
                self.sidebar.note_input.setPlainText(text[:250])
                self.sidebar.note_input.moveCursor(
                    self.sidebar.note_input.textCursor().End,
                )
            self.sidebar.char_count_label.setText(
                f"{len(self.sidebar.note_input.toPlainText())}/250 characters",
            )

        self.sidebar.note_input.textChanged.connect(update_note_counter)
        parent_layout.addWidget(self.sidebar.note_input)

        # Character count and tag help
        note_info_row = QHBoxLayout()
        note_info_row.setSpacing(10)
        note_info_row.addWidget(self.sidebar.char_count_label)
        note_info_row.addStretch()

        tag_help_label = QLabel("💡 Tip: Tag channels with concentrations")
        tag_help_label.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        note_info_row.addWidget(tag_help_label)
        parent_layout.addLayout(note_info_row)

    def _build_units_row(self, parent_layout: QVBoxLayout):
        """Build concentration units selector."""
        units_row = QHBoxLayout()
        units_row.setSpacing(8)
        units_label = QLabel("Units:")
        units_label.setFixedWidth(70)
        units_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        units_row.addWidget(units_label)

        self.sidebar.units_combo = QComboBox()
        self.sidebar.units_combo.addItems(
            [
                "M (Molar)",
                "mM (Millimolar)",
                "µM (Micromolar)",
                "nM (Nanomolar)",
                "pM (Picomolar)",
                "mg/mL",
                "µg/mL",
                "ng/mL",
            ],
        )
        self.sidebar.units_combo.setCurrentIndex(3)  # Default to nM
        self.sidebar.units_combo.setToolTip(
            "Concentration units for tagged channels (applies to [A:10] style tags)",
        )
        self.sidebar.units_combo.setFixedWidth(140)
        self.sidebar.units_combo.setStyleSheet(self._combo_style())
        units_row.addWidget(self.sidebar.units_combo)
        units_row.addStretch()

        # Info about units applying to tags
        units_info = QLabel(
            "Units apply to concentrations in tags (e.g., [A:10] = 10 nM)",
        )
        units_info.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        parent_layout.addWidget(units_info)

    def _build_execution_section(self, parent_layout: QVBoxLayout):
        """Build execution controls (Start Cycle, Add to Queue)."""
        # Separator
        execution_separator = QFrame()
        execution_separator.setFixedHeight(1)
        execution_separator.setStyleSheet(
            "background: rgba(0, 0, 0, 0.06);"
            "border: none;"
            "margin: 12px 0px 8px 0px;",
        )
        parent_layout.addWidget(execution_separator)

        # Execution header
        execution_header = QLabel("🚀 Execution")
        execution_header.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 600;"
            "margin-bottom: 4px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        parent_layout.addWidget(execution_header)

        # Action Buttons
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)

        # Start Cycle Button
        self.sidebar.start_cycle_btn = QPushButton("▶ Start Cycle")
        self.sidebar.start_cycle_btn.setFixedSize(120, 36)
        self.sidebar.start_cycle_btn.setToolTip(
            "Begin experiment immediately with current settings",
        )
        self.sidebar.start_cycle_btn.setStyleSheet(
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 6px 12px;"
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
            "QPushButton:disabled {"
            "  background: rgba(0, 0, 0, 0.1);"
            "  color: #86868B;"
            "}",
        )
        buttons_row.addWidget(self.sidebar.start_cycle_btn)

        # Add to Queue Button
        self.sidebar.add_to_queue_btn = QPushButton("+ Add to Queue")
        self.sidebar.add_to_queue_btn.setFixedSize(140, 36)
        self.sidebar.add_to_queue_btn.setToolTip(
            "Add cycle to queue for batch execution (max 5 cycles)",
        )
        self.sidebar.add_to_queue_btn.setStyleSheet(
            "QPushButton {"
            "  background: #636366;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 6px 12px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #7C7C80;"
            "}"
            "QPushButton:pressed {"
            "  background: #8E8E93;"
            "}"
            "QPushButton:disabled {"
            "  background: rgba(0, 0, 0, 0.1);"
            "  color: #86868B;"
            "}",
        )
        buttons_row.addWidget(self.sidebar.add_to_queue_btn)
        buttons_row.addStretch()

        parent_layout.addLayout(buttons_row)

        # Help text
        help_text = QLabel(
            "💡 Start Cycle: Begin immediately  |  Add to Queue: Plan batch runs (max 5 cycles)",
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: rgba(0, 122, 255, 0.06);"
            "border-radius: 4px;"
            "padding: 6px 8px;"
            "margin-top: 6px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        parent_layout.addWidget(help_text)

    def _build_cycle_history_queue(self, tab_layout: QVBoxLayout):
        """Build cycle history and queue management section."""
        summary_section = CollapsibleSection("Cycle History & Queue", is_expanded=True)

        # Start Run Button
        self.sidebar.start_run_btn = QPushButton("▶ Start Queued Run")
        self.sidebar.start_run_btn.setFixedHeight(36)
        self.sidebar.start_run_btn.setToolTip(
            "Execute all cycles in queue sequentially",
        )
        self.sidebar.start_run_btn.setStyleSheet(
            "QPushButton {"
            "  background: #3A3A3C;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 8px 16px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #48484A;"
            "}"
            "QPushButton:pressed {"
            "  background: #636366;"
            "}",
        )
        self.sidebar.start_run_btn.setVisible(False)
        tab_layout.addWidget(self.sidebar.start_run_btn)

        # Queue status row
        queue_status_row = QHBoxLayout()
        queue_status_row.setSpacing(12)

        self.sidebar.queue_status_label = QLabel(
            "Queue: 0 cycles | Click 'Add to Queue' to plan batch runs",
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
        queue_status_row.addStretch()

        tab_layout.addLayout(queue_status_row)
        tab_layout.addSpacing(8)

        # Summary table card
        self._build_summary_table(summary_section)

        tab_layout.addWidget(summary_section)

    def _build_summary_table(self, parent_section: CollapsibleSection):
        """Build summary table with cycle history."""
        summary_card = QFrame()
        summary_card.setStyleSheet(card_style())
        summary_card_layout = QVBoxLayout(summary_card)
        summary_card_layout.setContentsMargins(12, 8, 12, 8)
        summary_card_layout.setSpacing(8)

        # Summary table
        self.sidebar.summary_table = QTableWidget(5, 4)
        self.sidebar.summary_table.setHorizontalHeaderLabels(
            ["State", "Type", "Start", "Notes"],
        )
        self.sidebar.summary_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch,
        )
        self.sidebar.summary_table.setColumnWidth(0, 80)
        self.sidebar.summary_table.setMaximumHeight(200)
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
            "  padding: 6px;"
            "  color: #1D1D1F;"
            "}"
            "QTableWidget::item:selected {"
            "  background: rgba(0, 0, 0, 0.08);"
            "  color: #1D1D1F;"
            "}"
            "QHeaderView::section {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  color: #86868B;"
            "  padding: 6px;"
            "  border: none;"
            "  border-bottom: 1px solid rgba(0, 0, 0, 0.08);"
            "  font-weight: 600;"
            "  font-size: 11px;"
            "}",
        )

        # Populate with empty data
        for row in range(5):
            for col in range(4):
                self.sidebar.summary_table.setItem(row, col, QTableWidgetItem(""))

        summary_card_layout.addWidget(self.sidebar.summary_table)

        # Table footer
        table_footer_row = QHBoxLayout()
        table_footer_row.setSpacing(10)

        info_legend = QLabel("Showing last 5 cycles")
        info_legend.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        table_footer_row.addWidget(info_legend)
        table_footer_row.addStretch()

        # View All Cycles Button
        self.sidebar.open_table_btn = QPushButton("📊 View All Cycles")
        self.sidebar.open_table_btn.setFixedHeight(28)
        self.sidebar.open_table_btn.setStyleSheet(
            "QPushButton {"
            "  background: #636366;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 4px 12px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #7C7C80;"
            "}"
            "QPushButton:pressed {"
            "  background: #8E8E93;"
            "}",
        )
        table_footer_row.addWidget(self.sidebar.open_table_btn)

        summary_card_layout.addLayout(table_footer_row)

        parent_section.add_content_widget(summary_card)

        # Connect button signal
        self.sidebar.open_table_btn.clicked.connect(self._open_cycle_table_dialog)

    def _open_cycle_table_dialog(self):
        """Open the full cycle table dialog for reviewing completed cycles.

        This is the designated location for cycle review/analysis, keeping
        the Live Sensorgram page focused on acquisition and monitoring.
        """
        if self.sidebar.cycle_table_dialog is None:
            self.sidebar.cycle_table_dialog = CycleTableDialog(self.sidebar)

            # Load sample/demo data
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
            self.sidebar.cycle_table_dialog.load_cycles(sample_data)

        self.sidebar.cycle_table_dialog.show()
        self.sidebar.cycle_table_dialog.raise_()
        self.sidebar.cycle_table_dialog.activateWindow()

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
