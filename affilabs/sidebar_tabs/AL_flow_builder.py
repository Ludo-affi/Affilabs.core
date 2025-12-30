"""Flow Tab Builder

Handles building the Flow tab UI with pump controls and cycle management.
Similar to Static tab but includes fluidics-specific controls (polarizer, pump operations).

Author: Affilabs
"""

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
)

from affilabs.sections import CollapsibleSection

# Import styles from central location
from affilabs.ui_styles import card_style, section_header_style


class FlowChannelTagHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for channel concentration tags in flow notes."""

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


class FlowTabBuilder:
    """Builder for constructing the Flow tab UI with pump controls and cycle management."""

    def __init__(self, sidebar):
        """Initialize builder with reference to parent sidebar.

        Args:
            sidebar: Parent AffilabsSidebar instance to attach widgets to

        """
        self.sidebar = sidebar

    def build(self, tab_layout: QVBoxLayout):
        """Build the complete Flow tab UI.

        Args:
            tab_layout: QVBoxLayout to add flow tab widgets to

        """
        self._build_intelligence_bar(tab_layout)
        self._build_cycle_settings(tab_layout)
        self._build_cycle_history_queue(tab_layout)

    def _build_intelligence_bar(self, tab_layout: QVBoxLayout):
        """Build intelligence bar section."""
        # TEMPORARY: Hidden for v1.0 release - will be re-enabled with AI diagnostics
        return

        intel_section = QLabel("INTELLIGENCE BAR")
        intel_section.setStyleSheet(section_header_style())
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
        self.sidebar.flow_intel_status_label = QLabel("✓ Good")
        self.sidebar.flow_intel_status_label.setStyleSheet(
            "font-size: 12px;"
            "color: #34C759;"
            "background: transparent;"
            "font-weight: 700;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        intel_bar_layout.addWidget(self.sidebar.flow_intel_status_label)

        # Separator bullet
        self.sidebar.flow_intel_separator = QLabel("•")
        self.sidebar.flow_intel_separator.setStyleSheet(
            "font-size: 12px;color: #86868B;background: transparent;",
        )
        intel_bar_layout.addWidget(self.sidebar.flow_intel_separator)

        self.sidebar.flow_intel_message_label = QLabel("→ Ready for injection")
        self.sidebar.flow_intel_message_label.setStyleSheet(
            "font-size: 12px;"
            "color: #007AFF;"
            "background: transparent;"
            "font-weight: 600;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        intel_bar_layout.addWidget(self.sidebar.flow_intel_message_label)

        intel_bar_layout.addStretch()

        tab_layout.addWidget(intel_bar)
        tab_layout.addSpacing(8)

    def _build_cycle_settings(self, tab_layout: QVBoxLayout):
        """Build cycle configuration section with type, length, notes, pump controls."""
        # Collapsible section
        flow_cycle_settings_section = CollapsibleSection(
            "⚙ Configure Next Cycle",
            is_expanded=True,
        )

        # Card container
        flow_cycle_settings_card = QFrame()
        flow_cycle_settings_card.setStyleSheet(card_style())
        flow_cycle_settings_card_layout = QVBoxLayout(flow_cycle_settings_card)
        flow_cycle_settings_card_layout.setContentsMargins(10, 8, 10, 8)
        flow_cycle_settings_card_layout.setSpacing(8)

        # Type row
        self._build_type_row(flow_cycle_settings_card_layout)

        # Length row
        self._build_length_row(flow_cycle_settings_card_layout)

        # Note input with syntax highlighting
        self._build_note_input(flow_cycle_settings_card_layout)

        # Units row
        self._build_units_row(flow_cycle_settings_card_layout)

        # Separator before pump controls
        execution_separator = QFrame()
        execution_separator.setFixedHeight(1)
        execution_separator.setStyleSheet(
            "background: rgba(0, 0, 0, 0.06);"
            "border: none;"
            "margin: 12px 0px 8px 0px;",
        )
        flow_cycle_settings_card_layout.addWidget(execution_separator)

        # FLOW-SPECIFIC: Pump Controls
        self._build_pump_controls(flow_cycle_settings_card_layout)

        # Another separator before execution buttons
        execution_separator2 = QFrame()
        execution_separator2.setFixedHeight(1)
        execution_separator2.setStyleSheet(
            "background: rgba(0, 0, 0, 0.06);"
            "border: none;"
            "margin: 12px 0px 8px 0px;",
        )
        flow_cycle_settings_card_layout.addWidget(execution_separator2)

        # Execution section (Start Cycle / Add to Queue buttons)
        self._build_execution_section(flow_cycle_settings_card_layout)

        flow_cycle_settings_section.add_content_widget(flow_cycle_settings_card)
        tab_layout.addWidget(flow_cycle_settings_section)
        tab_layout.addSpacing(8)

    def _build_type_row(self, layout: QVBoxLayout):
        """Build cycle type selector row."""
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

        self.sidebar.flow_cycle_type_combo = QComboBox()
        self.sidebar.flow_cycle_type_combo.addItems(
            ["Auto-read", "Baseline", "Immobilization", "Concentration"],
        )
        self.sidebar.flow_cycle_type_combo.setCurrentIndex(0)
        self.sidebar.flow_cycle_type_combo.setToolTip(
            "Select experiment type: Auto-read (automatic), Baseline (reference), Immobilization (binding), or Concentration (dose-response)",
        )
        self.sidebar.flow_cycle_type_combo.setFixedWidth(140)
        self.sidebar.flow_cycle_type_combo.setStyleSheet(self._combo_style())
        type_row.addWidget(self.sidebar.flow_cycle_type_combo)

        type_row.addStretch()
        layout.addLayout(type_row)

    def _build_length_row(self, layout: QVBoxLayout):
        """Build cycle length selector row."""
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

        self.sidebar.flow_cycle_length_combo = QComboBox()
        self.sidebar.flow_cycle_length_combo.addItems(
            ["2 min", "5 min", "15 min", "30 min", "60 min"],
        )
        self.sidebar.flow_cycle_length_combo.setCurrentIndex(1)
        self.sidebar.flow_cycle_length_combo.setToolTip(
            "Duration of the experiment cycle",
        )
        self.sidebar.flow_cycle_length_combo.setFixedWidth(100)
        self.sidebar.flow_cycle_length_combo.setStyleSheet(self._combo_style())
        length_row.addWidget(self.sidebar.flow_cycle_length_combo)

        length_row.addStretch()
        layout.addLayout(length_row)

    def _build_note_input(self, layout: QVBoxLayout):
        """Build note input with syntax highlighting for channel tags."""
        note_label = QLabel("Note:")
        note_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        layout.addWidget(note_label)

        self.sidebar.flow_note_input = QTextEdit()
        self.sidebar.flow_note_input.setPlaceholderText(
            "Use tags: [A] [B] [C] [D] [ALL] or with concentration [A:10] [ALL:50]  (max 250 chars)",
        )
        self.sidebar.flow_note_input.setMaximumHeight(60)
        self.sidebar.flow_note_input.setStyleSheet(
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
        self.sidebar.flow_note_highlighter = FlowChannelTagHighlighter(
            self.sidebar.flow_note_input.document(),
        )

        # Character counter
        self.sidebar.flow_char_count_label = QLabel("0/250 characters")
        self.sidebar.flow_char_count_label.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )

        def update_flow_note_counter():
            text = self.sidebar.flow_note_input.toPlainText()
            if len(text) > 250:
                self.sidebar.flow_note_input.setPlainText(text[:250])
                self.sidebar.flow_note_input.moveCursor(
                    self.sidebar.flow_note_input.textCursor().End,
                )
            self.sidebar.flow_char_count_label.setText(
                f"{len(self.sidebar.flow_note_input.toPlainText())}/250 characters",
            )

        self.sidebar.flow_note_input.textChanged.connect(update_flow_note_counter)
        layout.addWidget(self.sidebar.flow_note_input)

        # Character count and tag help
        note_info_row = QHBoxLayout()
        note_info_row.setSpacing(10)
        note_info_row.addWidget(self.sidebar.flow_char_count_label)
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
        layout.addLayout(note_info_row)

    def _build_units_row(self, layout: QVBoxLayout):
        """Build concentration units selector row."""
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

        self.sidebar.flow_units_combo = QComboBox()
        self.sidebar.flow_units_combo.addItems(
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
        self.sidebar.flow_units_combo.setCurrentIndex(3)  # Default to nM
        self.sidebar.flow_units_combo.setToolTip(
            "Concentration units for tagged channels (applies to [A:10] style tags)",
        )
        self.sidebar.flow_units_combo.setFixedWidth(140)
        self.sidebar.flow_units_combo.setStyleSheet(self._combo_style())
        units_row.addWidget(self.sidebar.flow_units_combo)

        units_row.addStretch()
        layout.addLayout(units_row)

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
        layout.addWidget(units_info)

    def _build_pump_controls(self, layout: QVBoxLayout):
        """Build pump controls section (FLOW-SPECIFIC)."""
        pump_header = QLabel("💧 Pump Controls")
        pump_header.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 600;"
            "margin-bottom: 4px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        layout.addWidget(pump_header)

        # Toggle Polarizer button
        self.sidebar.polarizer_toggle_btn = QPushButton("Toggle Polarizer")
        self.sidebar.polarizer_toggle_btn.setFixedHeight(32)
        self.sidebar.polarizer_toggle_btn.setToolTip(
            "Switch polarizer between S and P positions",
        )
        self.sidebar.polarizer_toggle_btn.setStyleSheet(
            "QPushButton {"
            "  background: #636366;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 6px 12px;"
            "  font-size: 12px;"
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
        layout.addWidget(self.sidebar.polarizer_toggle_btn)

    def _build_execution_section(self, layout: QVBoxLayout):
        """Build execution section with Start Cycle and Add to Queue buttons."""
        execution_header = QLabel("🚀 Execution")
        execution_header.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 600;"
            "margin-bottom: 4px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        layout.addWidget(execution_header)

        # Action Buttons
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)

        # Start Cycle Button
        self.sidebar.flow_start_cycle_btn = QPushButton("▶ Start Cycle")
        self.sidebar.flow_start_cycle_btn.setFixedSize(120, 36)
        self.sidebar.flow_start_cycle_btn.setToolTip(
            "Begin experiment immediately with current settings",
        )
        self.sidebar.flow_start_cycle_btn.setStyleSheet(
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
        buttons_row.addWidget(self.sidebar.flow_start_cycle_btn)

        # Add to Queue Button
        self.sidebar.flow_add_to_queue_btn = QPushButton("+ Add to Queue")
        self.sidebar.flow_add_to_queue_btn.setFixedSize(140, 36)
        self.sidebar.flow_add_to_queue_btn.setToolTip(
            "Add cycle to queue for batch execution (max 5 cycles)",
        )
        self.sidebar.flow_add_to_queue_btn.setStyleSheet(
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
        buttons_row.addWidget(self.sidebar.flow_add_to_queue_btn)
        buttons_row.addStretch()

        layout.addLayout(buttons_row)

        # Help text with workflow explanation
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
        layout.addWidget(help_text)

    def _build_cycle_history_queue(self, tab_layout: QVBoxLayout):
        """Build cycle history and queue management section."""
        flow_summary_section = CollapsibleSection(
            "Cycle History & Queue",
            is_expanded=True,
        )

        # Start Run Button (hidden by default)
        self.sidebar.flow_start_run_btn = QPushButton("▶ Start Queued Run")
        self.sidebar.flow_start_run_btn.setFixedHeight(36)
        self.sidebar.flow_start_run_btn.setToolTip(
            "Execute all cycles in queue sequentially",
        )
        self.sidebar.flow_start_run_btn.setStyleSheet(
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
        self.sidebar.flow_start_run_btn.setVisible(
            False,
        )  # Hidden until queue has items
        flow_summary_section.content_layout.addWidget(self.sidebar.flow_start_run_btn)

        # Queue status label
        self.sidebar.flow_queue_status_label = QLabel("No cycles queued")
        self.sidebar.flow_queue_status_label.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "margin: 4px 0px 8px 0px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        flow_summary_section.content_layout.addWidget(
            self.sidebar.flow_queue_status_label,
        )

        # Cycle summary table card
        self._build_summary_table(flow_summary_section)

        tab_layout.addWidget(flow_summary_section)

    def _build_summary_table(self, parent_section):
        """Build cycle summary table with 3 recent cycles."""
        flow_summary_card = QFrame()
        flow_summary_card.setStyleSheet(
            "QFrame {  background: rgba(0, 0, 0, 0.03);  border-radius: 8px;}",
        )
        flow_summary_card_layout = QVBoxLayout(flow_summary_card)
        flow_summary_card_layout.setContentsMargins(10, 8, 10, 8)
        flow_summary_card_layout.setSpacing(6)

        # Table with 3 recent cycles
        self.sidebar.flow_cycle_mini_table = QTableWidget(3, 4)
        self.sidebar.flow_cycle_mini_table.setHorizontalHeaderLabels(
            ["#", "Type", "Time", "Note"],
        )
        self.sidebar.flow_cycle_mini_table.horizontalHeader().setStretchLastSection(
            True,
        )
        self.sidebar.flow_cycle_mini_table.verticalHeader().setVisible(False)
        self.sidebar.flow_cycle_mini_table.setMaximumHeight(120)
        self.sidebar.flow_cycle_mini_table.setStyleSheet(
            "QTableWidget {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 4px;"
            "  font-size: 11px;"
            "  gridline-color: rgba(0, 0, 0, 0.06);"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QTableWidget::item {"
            "  padding: 4px;"
            "}"
            "QHeaderView::section {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  padding: 4px;"
            "  border: none;"
            "  border-bottom: 1px solid rgba(0, 0, 0, 0.1);"
            "  font-weight: 600;"
            "  font-size: 10px;"
            "  color: #86868B;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}",
        )
        flow_summary_card_layout.addWidget(self.sidebar.flow_cycle_mini_table)

        # Table footer with legend and View All button
        table_footer_row = QHBoxLayout()
        table_footer_row.setSpacing(8)

        info_legend = QLabel("📊 Showing last 3 cycles")
        info_legend.setStyleSheet(
            "font-size: 10px;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        table_footer_row.addWidget(info_legend)
        table_footer_row.addStretch()

        # View All Cycles Button (shares cycle table dialog with Static tab)
        self.sidebar.flow_open_table_btn = QPushButton("📊 View All Cycles")
        self.sidebar.flow_open_table_btn.setFixedHeight(28)
        self.sidebar.flow_open_table_btn.setToolTip(
            "Open full cycle table dialog with complete history",
        )
        self.sidebar.flow_open_table_btn.setStyleSheet(
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
        table_footer_row.addWidget(self.sidebar.flow_open_table_btn)

        flow_summary_card_layout.addLayout(table_footer_row)

        parent_section.add_content_widget(flow_summary_card)

        # Connect button signal to shared dialog handler in sidebar
        self.sidebar.flow_open_table_btn.clicked.connect(
            self.sidebar._open_cycle_table_dialog,
        )

    def _combo_style(self) -> str:
        """Return consistent combo box stylesheet."""
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
