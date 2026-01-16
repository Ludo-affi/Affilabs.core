"""Flow Tab Builder

Handles building the Flow Control tab UI with fluidics experiments configuration.

Author: Affilabs
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

# Import sections from central location
from affilabs.sections import CollapsibleSection
from affilabs.ui_styles import section_header_style


class AdvancedFlowRatesDialog(QDialog):
    """Dialog for advanced flow rate settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Flow Rate Settings")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title
        title = QLabel("Advanced Flow Rate Settings")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #1D1D1F; font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;")
        layout.addWidget(title)

        # Description
        desc = QLabel("Configure flow rates for specialized operations")
        desc.setStyleSheet("font-size: 12px; color: #86868B; margin-bottom: 8px; font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;")
        layout.addWidget(desc)

        # Flow rate inputs
        settings_card = QFrame()
        settings_card.setStyleSheet("QFrame { background: rgba(0, 0, 0, 0.03); border-radius: 8px; }")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(12, 12, 12, 12)
        settings_layout.setSpacing(12)

        # Flush flow rate
        flush_row = QHBoxLayout()
        flush_row.setSpacing(10)
        flush_label = QLabel("Flush:")
        flush_label.setFixedWidth(100)
        flush_label.setStyleSheet("font-size: 12px; color: #1D1D1F; font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;")
        flush_row.addWidget(flush_label)

        self.flush_spin = QSpinBox()
        self.flush_spin.setRange(1, 30000)
        self.flush_spin.setValue(50)
        self.flush_spin.setFixedWidth(70)
        self.flush_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.flush_spin.setStyleSheet("QSpinBox { background: white; border: 1px solid rgba(0,0,0,0.1); border-radius: 6px; padding: 6px 8px; font-size: 13px; font-family: -apple-system, 'SF Mono', 'Menlo', monospace; } QSpinBox:focus { border: 2px solid #1D1D1F; padding: 5px 7px; }")
        flush_row.addWidget(self.flush_spin)

        flush_unit = QLabel("µL/min")
        flush_unit.setStyleSheet("font-size: 12px; color: #86868B; font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;")
        flush_row.addWidget(flush_unit)
        flush_row.addStretch()
        settings_layout.addLayout(flush_row)

        # Regeneration flow rate
        regen_row = QHBoxLayout()
        regen_row.setSpacing(10)
        regen_label = QLabel("Regeneration:")
        regen_label.setFixedWidth(100)
        regen_label.setStyleSheet("font-size: 12px; color: #1D1D1F; font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;")
        regen_row.addWidget(regen_label)

        self.regeneration_spin = QSpinBox()
        self.regeneration_spin.setRange(1, 30000)
        self.regeneration_spin.setValue(30)
        self.regeneration_spin.setFixedWidth(70)
        self.regeneration_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.regeneration_spin.setStyleSheet("QSpinBox { background: white; border: 1px solid rgba(0,0,0,0.1); border-radius: 6px; padding: 6px 8px; font-size: 13px; font-family: -apple-system, 'SF Mono', 'Menlo', monospace; } QSpinBox:focus { border: 2px solid #1D1D1F; padding: 5px 7px; }")
        regen_row.addWidget(self.regeneration_spin)

        regen_unit = QLabel("µL/min")
        regen_unit.setStyleSheet("font-size: 12px; color: #86868B; font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;")
        regen_row.addWidget(regen_unit)
        regen_row.addStretch()
        settings_layout.addLayout(regen_row)

        # Prime flow rate
        prime_row = QHBoxLayout()
        prime_row.setSpacing(10)
        prime_label = QLabel("Prime:")
        prime_label.setFixedWidth(100)
        prime_label.setStyleSheet("font-size: 12px; color: #1D1D1F; font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;")
        prime_row.addWidget(prime_label)

        self.prime_spin = QSpinBox()
        self.prime_spin.setRange(1, 30000)
        self.prime_spin.setValue(100)
        self.prime_spin.setFixedWidth(70)
        self.prime_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.prime_spin.setStyleSheet("QSpinBox { background: white; border: 1px solid rgba(0,0,0,0.1); border-radius: 6px; padding: 6px 8px; font-size: 13px; font-family: -apple-system, 'SF Mono', 'Menlo', monospace; } QSpinBox:focus { border: 2px solid #1D1D1F; padding: 5px 7px; }")
        prime_row.addWidget(self.prime_spin)

        prime_unit = QLabel("µL/min")
        prime_unit.setStyleSheet("font-size: 12px; color: #86868B; font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;")
        prime_row.addWidget(prime_unit)
        prime_row.addStretch()
        settings_layout.addLayout(prime_row)

        # Injections flow rate
        inject_row = QHBoxLayout()
        inject_row.setSpacing(10)
        inject_label = QLabel("Injections:")
        inject_label.setFixedWidth(100)
        inject_label.setStyleSheet("font-size: 12px; color: #1D1D1F; font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;")
        inject_row.addWidget(inject_label)

        self.injections_spin = QSpinBox()
        self.injections_spin.setRange(1, 30000)
        self.injections_spin.setValue(20)
        self.injections_spin.setFixedWidth(70)
        self.injections_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.injections_spin.setStyleSheet("QSpinBox { background: white; border: 1px solid rgba(0,0,0,0.1); border-radius: 6px; padding: 6px 8px; font-size: 13px; font-family: -apple-system, 'SF Mono', 'Menlo', monospace; } QSpinBox:focus { border: 2px solid #1D1D1F; padding: 5px 7px; }")
        inject_row.addWidget(self.injections_spin)

        inject_unit = QLabel("µL/min")
        inject_unit.setStyleSheet("font-size: 12px; color: #86868B; font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;")
        inject_row.addWidget(inject_unit)
        inject_row.addStretch()
        settings_layout.addLayout(inject_row)

        layout.addWidget(settings_card)

        # Spacer
        layout.addSpacing(16)

        # Operations section
        ops_title = QLabel("Operations")
        ops_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1D1D1F; font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;")
        layout.addWidget(ops_title)

        # Operations buttons card
        ops_card = QFrame()
        ops_card.setStyleSheet("QFrame { background: rgba(0, 0, 0, 0.03); border-radius: 8px; }")
        ops_layout = QVBoxLayout(ops_card)
        ops_layout.setContentsMargins(12, 12, 12, 12)
        ops_layout.setSpacing(8)

        # Prime Pump button
        self.prime_btn = QPushButton("🔧 Prime Pump")
        self.prime_btn.setFixedHeight(36)
        self.prime_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prime_btn.setStyleSheet(
            "QPushButton {"
            "  background: #007AFF;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 0px 16px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #0051D5;"
            "}"
            "QPushButton:pressed {"
            "  background: #004BB5;"
            "}"
        )
        self.prime_btn.setToolTip("Run prime pump sequence (6 cycles)")
        ops_layout.addWidget(self.prime_btn)

        # Clean Pump button
        self.cleanup_btn = QPushButton("🧹 Clean Pump")
        self.cleanup_btn.setFixedHeight(36)
        self.cleanup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cleanup_btn.setStyleSheet(
            "QPushButton {"
            "  background: #34C759;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 0px 16px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #28A745;"
            "}"
            "QPushButton:pressed {"
            "  background: #1E7E34;"
            "}"
        )
        self.cleanup_btn.setToolTip("Run cleanup sequence (9-phase complete cleaning)")
        ops_layout.addWidget(self.cleanup_btn)

        layout.addWidget(ops_card)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)


class FlowTabBuilder:
    """Builder for constructing the Flow Control tab UI."""

    def __init__(self, sidebar):
        """Initialize builder with reference to parent sidebar.

        Args:
            sidebar: Parent AffilabsSidebar instance to attach widgets to

        """
        self.sidebar = sidebar

    def build(self, tab_layout: QVBoxLayout):
        """Build the complete Flow Control tab UI.

        Args:
            tab_layout: QVBoxLayout to add flow tab widgets to

        """
        self._build_intelligence_bar(tab_layout)
        self._build_affipump_control(tab_layout)
        self._build_valve_control(tab_layout)
        self._build_internal_pump_control(tab_layout)

        # Add stretch to push content to top
        tab_layout.addStretch()

    def _build_intelligence_bar(self, tab_layout: QVBoxLayout):
        """Build intelligence bar section."""
        intel_section = QLabel("FLUIDICS EXPERIMENTS")
        intel_section.setFixedHeight(15)
        intel_section.setStyleSheet(section_header_style())
        intel_section.setToolTip(
            "Configure flow rates for Setup, Functionalization, Assay, and advanced operations",
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

        # Cycle status message (will show running cycles and queued cycles)
        self.sidebar.flow_intel_message_label = QLabel("No cycles running")
        self.sidebar.flow_intel_message_label.setFixedHeight(20)
        self.sidebar.flow_intel_message_label.setStyleSheet(
            "font-size: 12px;"
            "color: #86868B;"
            "background: transparent;"
            "font-weight: 600;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        intel_bar_layout.addWidget(self.sidebar.flow_intel_message_label)

        intel_bar_layout.addStretch()

        tab_layout.addWidget(intel_bar)
        tab_layout.addSpacing(8)

        # === FLOW STATUS BOARD ===
        self._build_flow_status_board(tab_layout)

    def _build_flow_status_board(self, tab_layout: QVBoxLayout):
        """Build the real-time flow status display board."""
        status_card = QFrame()
        status_card.setStyleSheet(
            "QFrame {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 122, 255, 0.06), stop:1 rgba(52, 199, 89, 0.06));"
            "  border: none;"
            "  border-radius: 10px;"
            "}"
        )
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(16, 12, 16, 12)
        status_layout.setSpacing(0)

        # Left side: Status indicator
        left_container = QVBoxLayout()
        left_container.setSpacing(2)

        status_row = QHBoxLayout()
        status_row.setSpacing(6)

        pump_status_icon = QLabel("●")
        pump_status_icon.setStyleSheet(
            "font-size: 12px; color: #86868B; background: transparent;"
        )
        status_row.addWidget(pump_status_icon)
        self.sidebar.flow_pump_status_icon = pump_status_icon

        pump_status_label = QLabel("Idle")
        pump_status_label.setStyleSheet(
            "font-size: 14px;"
            "font-weight: 700;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
        )
        status_row.addWidget(pump_status_label)
        self.sidebar.flow_pump_status_label = pump_status_label
        status_row.addStretch()

        left_container.addLayout(status_row)

        # Flow rate under status
        flow_row = QHBoxLayout()
        flow_row.setSpacing(4)

        flow_rate_value = QLabel("0")
        flow_rate_value.setStyleSheet(
            "font-size: 24px;"
            "font-weight: 600;"
            "color: #007AFF;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Mono', 'Menlo', 'Consolas', monospace;"
        )
        flow_row.addWidget(flow_rate_value)
        self.sidebar.flow_current_rate = flow_rate_value

        flow_rate_unit = QLabel("µL/min")
        flow_rate_unit.setStyleSheet(
            "font-size: 11px; color: #86868B; background: transparent; padding-top: 8px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        flow_row.addWidget(flow_rate_unit)
        flow_row.addStretch()

        left_container.addLayout(flow_row)
        status_layout.addLayout(left_container, 1)

        status_layout.addSpacing(16)

        # Right side: Plunger + Contact
        right_container = QVBoxLayout()
        right_container.setSpacing(6)

        # Plunger Position
        plunger_row = QHBoxLayout()
        plunger_row.setSpacing(4)

        plunger_title = QLabel("Plunger")
        plunger_title.setStyleSheet(
            "font-size: 10px; color: #86868B; background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        plunger_row.addWidget(plunger_title)
        plunger_row.addStretch()

        plunger_value = QLabel("0")
        plunger_value.setStyleSheet(
            "font-size: 15px;"
            "font-weight: 600;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Mono', 'Menlo', 'Consolas', monospace;"
        )
        plunger_row.addWidget(plunger_value)
        self.sidebar.flow_plunger_position = plunger_value

        plunger_unit = QLabel("µL")
        plunger_unit.setStyleSheet(
            "font-size: 11px; color: #86868B; background: transparent; padding-top: 2px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        plunger_row.addWidget(plunger_unit)

        right_container.addLayout(plunger_row)

        # Contact Time
        contact_row = QHBoxLayout()
        contact_row.setSpacing(4)

        contact_title = QLabel("Contact")
        contact_title.setStyleSheet(
            "font-size: 10px; color: #86868B; background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        contact_row.addWidget(contact_title)
        contact_row.addStretch()

        contact_value = QLabel("0.0")
        contact_value.setStyleSheet(
            "font-size: 15px;"
            "font-weight: 600;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Mono', 'Menlo', 'Consolas', monospace;"
        )
        contact_row.addWidget(contact_value)
        self.sidebar.flow_contact_time = contact_value

        contact_unit = QLabel("s")
        contact_unit.setStyleSheet(
            "font-size: 11px; color: #86868B; background: transparent; padding-top: 2px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        contact_row.addWidget(contact_unit)

        right_container.addLayout(contact_row)
        status_layout.addLayout(right_container, 1)

        tab_layout.addWidget(status_card)
        tab_layout.addSpacing(12)

    def _build_affipump_control(self, tab_layout: QVBoxLayout):
        """Build AffiPump Control section."""
        affipump_section = CollapsibleSection(
            "AffiPump Control",
            is_expanded=True,
        )

        affipump_help = QLabel(
            "Configure flow rates for Setup, Functionalization, Assay, and advanced operations",
        )
        affipump_help.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "margin: 4px 0px 8px 0px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        affipump_section.content_layout.addWidget(affipump_help)

        # Card container
        affipump_card = QFrame()
        affipump_card.setStyleSheet(
            "QFrame {  background: rgba(0, 0, 0, 0.03);  border-radius: 8px;}",
        )
        affipump_card_layout = QVBoxLayout(affipump_card)
        affipump_card_layout.setContentsMargins(12, 8, 12, 8)
        affipump_card_layout.setSpacing(6)

        # Main Flow Rates
        rates_label = QLabel("Main Flow Rates")
        rates_label.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        affipump_card_layout.addWidget(rates_label)

        # Setup flow rate
        self._add_flow_rate_control(
            affipump_card_layout,
            "Setup:",
            "pump_setup_spin",
            25,
            1,
            30000,
            "Default in autoread cycle",
        )

        # Functionalization flow rate
        self._add_flow_rate_control(
            affipump_card_layout,
            "Functionalization:",
            "pump_functionalization_spin",
            10,
            1,
            30000,
            "Immobilization cycle",
        )

        # Assay flow rate
        self._add_flow_rate_control(
            affipump_card_layout,
            "Assay:",
            "pump_assay_spin",
            15,
            1,
            30000,
            "Concentration cycle",
        )

        # Quick Preset buttons
        preset_row = QHBoxLayout()
        preset_row.setSpacing(4)

        preset_label = QLabel("Quick:")
        preset_label.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        preset_row.addWidget(preset_label)

        for preset_val in [5, 10, 25, 50, 100]:
            preset_btn = QPushButton(str(preset_val))
            preset_btn.setFixedSize(36, 24)
            preset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            preset_btn.setStyleSheet(
                "QPushButton {"
                "  background: #007AFF;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 4px;"
                "  font-size: 11px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Mono', 'Menlo', monospace;"
                "}"
                "QPushButton:hover {"
                "  background: #0051D5;"
                "}"
                "QPushButton:pressed {"
                "  background: #004BB5;"
                "}"
            )
            preset_btn.setToolTip(f"Set all flow rates to {preset_val} µL/min")
            preset_btn.clicked.connect(lambda checked, v=preset_val: self._set_preset_flow_rate(v))
            preset_row.addWidget(preset_btn)

        preset_row.addStretch()
        affipump_card_layout.addLayout(preset_row)
        affipump_card_layout.addSpacing(4)

        self._add_separator(affipump_card_layout)

        # Pump Operations label
        operations_label = QLabel("Pump Operations")
        operations_label.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "margin-top: 4px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        affipump_card_layout.addWidget(operations_label)

        # Start Buffer and Flush row
        start_flush_layout = QHBoxLayout()
        start_flush_layout.setSpacing(8)

        # Start Buffer button
        start_buffer_btn = QPushButton("▶ Start Buffer")
        start_buffer_btn.setFixedHeight(36)
        start_buffer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_buffer_btn.setStyleSheet(
            "QPushButton {"
            "  background: #34C759;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 0px 16px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #28A745;"
            "}"
            "QPushButton:pressed {"
            "  background: #1E7E34;"
            "}"
        )
        start_buffer_btn.setToolTip("Start continuous buffer flow")
        start_flush_layout.addWidget(start_buffer_btn)
        self.sidebar.start_buffer_btn = start_buffer_btn

        # Flush Loop button
        flush_btn = QPushButton("🔄 Flush Loop")
        flush_btn.setFixedHeight(36)
        flush_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        flush_btn.setStyleSheet(
            "QPushButton {"
            "  background: #5AC8FA;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 0px 16px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #32ADE6;"
            "}"
            "QPushButton:pressed {"
            "  background: #209CCA;"
            "}"
        )
        flush_btn.setToolTip("Flush sample loop with buffer")
        start_flush_layout.addWidget(flush_btn)
        self.sidebar.flush_btn = flush_btn

        affipump_card_layout.addLayout(start_flush_layout)

        # Inject buttons row
        inject_layout = QHBoxLayout()
        inject_layout.setSpacing(8)

        # Simple Inject button
        inject_simple_btn = QPushButton("💉 Inject (Simple)")
        inject_simple_btn.setFixedHeight(36)
        inject_simple_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        inject_simple_btn.setStyleSheet(
            "QPushButton {"
            "  background: #FF9500;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 0px 16px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #E08500;"
            "}"
            "QPushButton:pressed {"
            "  background: #C77500;"
            "}"
        )
        inject_simple_btn.setToolTip("Run simple injection (full syringe dispense with contact time)")
        inject_layout.addWidget(inject_simple_btn)
        self.sidebar.inject_simple_btn = inject_simple_btn

        # Partial Loop Inject button
        inject_partial_btn = QPushButton("💉 Inject (Partial Loop)")
        inject_partial_btn.setFixedHeight(36)
        inject_partial_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        inject_partial_btn.setStyleSheet(
            "QPushButton {"
            "  background: #AF52DE;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 0px 16px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #9A3FCC;"
            "}"
            "QPushButton:pressed {"
            "  background: #8230B3;"
            "}"
        )
        inject_partial_btn.setToolTip("Run partial loop injection (14-step protocol with spike)")
        inject_layout.addWidget(inject_partial_btn)
        self.sidebar.inject_partial_btn = inject_partial_btn

        affipump_card_layout.addLayout(inject_layout)

        # Maintenance buttons row (Home and Emergency Stop)
        maintenance_layout = QHBoxLayout()
        maintenance_layout.setSpacing(8)

        # Home Pumps button
        home_btn = QPushButton("🏠 Home Pumps")
        home_btn.setFixedHeight(36)
        home_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        home_btn.setStyleSheet(
            "QPushButton {"
            "  background: #007AFF;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 0px 16px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #0051D5;"
            "}"
            "QPushButton:pressed {"
            "  background: #004BB5;"
            "}"
        )
        home_btn.setToolTip("Home both pumps to zero position")
        maintenance_layout.addWidget(home_btn)
        self.sidebar.pump_home_btn = home_btn

        # Emergency Stop button
        emergency_stop_btn = QPushButton("🛑 STOP")
        emergency_stop_btn.setFixedHeight(36)
        emergency_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        emergency_stop_btn.setStyleSheet(
            "QPushButton {"
            "  background: #FF3B30;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 0px 16px;"
            "  font-size: 12px;"
            "  font-weight: bold;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #D32F2F;"
            "}"
            "QPushButton:pressed {"
            "  background: #B71C1C;"
            "}"
        )
        emergency_stop_btn.setToolTip("Emergency stop - immediately terminate all pump operations")
        maintenance_layout.addWidget(emergency_stop_btn)
        self.sidebar.pump_emergency_stop_btn = emergency_stop_btn

        affipump_card_layout.addLayout(maintenance_layout)

        # Advanced Settings button row
        advanced_layout = QHBoxLayout()
        advanced_layout.addStretch()

        advanced_btn = QPushButton("⚙️")
        advanced_btn.setFixedSize(32, 32)
        advanced_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        advanced_btn.setStyleSheet(
            "QPushButton {"
            "  background: white;"
            "  color: #007AFF;"
            "  border: 1px solid rgba(0, 0, 0, 0.15);"
            "  border-radius: 6px;"
            "  font-size: 16px;"
            "  font-weight: 500;"
            "  padding: 0px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 122, 255, 0.1);"
            "  color: #0051D5;"
            "  border: 1px solid #007AFF;"
            "}"
            "QPushButton:pressed {"
            "  background: rgba(0, 122, 255, 0.2);"
            "}"
        )
        advanced_btn.setToolTip("Advanced flow rate settings")
        advanced_btn.clicked.connect(self._show_advanced_settings)
        advanced_layout.addWidget(advanced_btn)
        self.sidebar.pump_advanced_btn = advanced_btn

        affipump_card_layout.addLayout(advanced_layout)

        affipump_section.add_content_widget(affipump_card)
        tab_layout.addWidget(affipump_section)

    def _set_preset_flow_rate(self, value):
        """Set all main flow rates to the same preset value.

        Args:
            value: Flow rate value in µL/min

        """
        if hasattr(self.sidebar, 'pump_setup_spin'):
            self.sidebar.pump_setup_spin.setValue(value)
        if hasattr(self.sidebar, 'pump_functionalization_spin'):
            self.sidebar.pump_functionalization_spin.setValue(value)
        if hasattr(self.sidebar, 'pump_assay_spin'):
            self.sidebar.pump_assay_spin.setValue(value)

    def _show_advanced_settings(self):
        """Show the advanced flow rate settings dialog."""
        dialog = AdvancedFlowRatesDialog(self.sidebar)

        # Load current values if they exist
        if hasattr(self.sidebar, 'pump_flush_rate'):
            dialog.flush_spin.setValue(self.sidebar.pump_flush_rate)
        if hasattr(self.sidebar, 'pump_regeneration_rate'):
            dialog.regeneration_spin.setValue(self.sidebar.pump_regeneration_rate)
        if hasattr(self.sidebar, 'pump_prime_rate'):
            dialog.prime_spin.setValue(self.sidebar.pump_prime_rate)
        if hasattr(self.sidebar, 'pump_injections_rate'):
            dialog.injections_spin.setValue(self.sidebar.pump_injections_rate)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Save the values
            self.sidebar.pump_flush_rate = dialog.flush_spin.value()
            self.sidebar.pump_regeneration_rate = dialog.regeneration_spin.value()
            self.sidebar.pump_prime_rate = dialog.prime_spin.value()
            self.sidebar.pump_injections_rate = dialog.injections_spin.value()

    def _build_valve_control(self, tab_layout: QVBoxLayout):
        """Build Valve Control section."""
        valve_section = CollapsibleSection(
            "Valve Control",
            is_expanded=True,
        )

        valve_help = QLabel(
            "Control Loop and Channel valve positions for kinetic channels KC1 and KC2",
        )
        valve_help.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "margin: 4px 0px 8px 0px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        valve_section.content_layout.addWidget(valve_help)

        # Card container
        valve_card = QFrame()
        valve_card.setStyleSheet(
            "QFrame {  background: rgba(0, 0, 0, 0.03);  border-radius: 8px;}",
        )
        valve_card_layout = QVBoxLayout(valve_card)
        valve_card_layout.setContentsMargins(12, 8, 12, 8)
        valve_card_layout.setSpacing(6)

        # Sync toggle button
        sync_layout = QHBoxLayout()
        sync_layout.addStretch()

        sync_valve_btn = QPushButton("Sync")
        sync_valve_btn.setCheckable(True)
        sync_valve_btn.setChecked(True)
        sync_valve_btn.setFixedHeight(32)
        sync_valve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sync_valve_btn.setStyleSheet(
            "QPushButton {"
            "  background: white;"
            "  color: #1D1D1F;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "  padding: 6px 16px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:checked {"
            "  background: #1D1D1F;"
            "  color: white;"
            "}"
            "QPushButton:hover:!checked {"
            "  background: rgba(0, 0, 0, 0.06);"
            "}"
        )
        sync_valve_btn.setToolTip("Toggle valve synchronization")
        sync_layout.addWidget(sync_valve_btn)
        self.sidebar.sync_valve_btn = sync_valve_btn

        valve_card_layout.addLayout(sync_layout)
        self._add_separator(valve_card_layout)

        # VALVES header
        valves_header = QLabel("VALVES")
        valves_header.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-weight: 700;"
            "letter-spacing: 0.5px;"
            "text-transform: uppercase;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        valve_card_layout.addWidget(valves_header)
        valve_card_layout.addSpacing(4)

        # Matrix layout: Valve / KC 1 / KC 2
        # Header row
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        # Empty corner cell
        corner = QLabel("")
        corner.setFixedWidth(100)
        header_row.addWidget(corner)

        # KC1 header
        kc1_header = QLabel("KC 1")
        kc1_header.setFixedWidth(80)
        kc1_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        kc1_header.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 600;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        header_row.addWidget(kc1_header)

        # KC2 header
        kc2_header = QLabel("KC 2")
        kc2_header.setFixedWidth(80)
        kc2_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        kc2_header.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 600;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        header_row.addWidget(kc2_header)

        header_row.addStretch()
        valve_card_layout.addLayout(header_row)

        valve_card_layout.addSpacing(4)

        # Loop Valve row
        loop_row = QHBoxLayout()
        loop_row.setSpacing(10)

        loop_label = QLabel("Loop:")
        loop_label.setFixedWidth(100)
        loop_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        loop_row.addWidget(loop_label)

        # KC1 Loop segmented control (Load | Sensor)
        kc1_loop_container = QWidget()
        kc1_loop_container.setFixedSize(110, 28)
        kc1_loop_layout = QHBoxLayout(kc1_loop_container)
        kc1_loop_layout.setContentsMargins(0, 0, 0, 0)
        kc1_loop_layout.setSpacing(0)

        kc1_btn_load = QPushButton("Load")
        kc1_btn_load.setCheckable(True)
        kc1_btn_load.setChecked(True)
        kc1_btn_load.setCursor(Qt.CursorShape.PointingHandCursor)
        kc1_btn_load.setStyleSheet(
            "QPushButton {"
            "  background: #34C759;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 14px 0px 0px 14px;"
            "  font-size: 10px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:!checked {"
            "  background: #E5E5EA;"
            "  color: #86868B;"
            "}"
        )

        kc1_btn_sensor = QPushButton("Sensor")
        kc1_btn_sensor.setCheckable(True)
        kc1_btn_sensor.setCursor(Qt.CursorShape.PointingHandCursor)
        kc1_btn_sensor.setStyleSheet(
            "QPushButton {"
            "  background: #34C759;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 0px 14px 14px 0px;"
            "  font-size: 10px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:!checked {"
            "  background: #E5E5EA;"
            "  color: #86868B;"
            "}"
        )

        # Button state management handled in main.py _on_loop_valve_switched()
        # Local handlers removed to prevent state conflicts

        kc1_loop_layout.addWidget(kc1_btn_load)
        kc1_loop_layout.addWidget(kc1_btn_sensor)

        loop_row.addWidget(kc1_loop_container)
        self.sidebar.kc1_loop_btn_load = kc1_btn_load
        self.sidebar.kc1_loop_btn_sensor = kc1_btn_sensor

        # KC2 Loop segmented control (Load | Sensor)
        kc2_loop_container = QWidget()
        kc2_loop_container.setFixedSize(110, 28)
        kc2_loop_layout = QHBoxLayout(kc2_loop_container)
        kc2_loop_layout.setContentsMargins(0, 0, 0, 0)
        kc2_loop_layout.setSpacing(0)

        kc2_btn_load = QPushButton("Load")
        kc2_btn_load.setCheckable(True)
        kc2_btn_load.setChecked(True)
        kc2_btn_load.setCursor(Qt.CursorShape.PointingHandCursor)
        kc2_btn_load.setStyleSheet(
            "QPushButton {"
            "  background: #34C759;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 14px 0px 0px 14px;"
            "  font-size: 10px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:!checked {"
            "  background: #E5E5EA;"
            "  color: #86868B;"
            "}"
        )

        kc2_btn_sensor = QPushButton("Sensor")
        kc2_btn_sensor.setCheckable(True)
        kc2_btn_sensor.setCursor(Qt.CursorShape.PointingHandCursor)
        kc2_btn_sensor.setStyleSheet(
            "QPushButton {"
            "  background: #34C759;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 0px 14px 14px 0px;"
            "  font-size: 10px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:!checked {"
            "  background: #E5E5EA;"
            "  color: #86868B;"
            "}"
        )

        # Button state management handled in main.py _on_loop_valve_switched()
        # Local handlers removed to prevent state conflicts

        kc2_loop_layout.addWidget(kc2_btn_load)
        kc2_loop_layout.addWidget(kc2_btn_sensor)

        loop_row.addWidget(kc2_loop_container)
        self.sidebar.kc2_loop_btn_load = kc2_btn_load
        self.sidebar.kc2_loop_btn_sensor = kc2_btn_sensor

        loop_row.addStretch()
        valve_card_layout.addLayout(loop_row)

        # Channel Valve row
        channel_row = QHBoxLayout()
        channel_row.setSpacing(10)

        channel_label = QLabel("Channel:")
        channel_label.setFixedWidth(100)
        channel_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        channel_row.addWidget(channel_label)

        # KC1 Channel segmented control (A | B)
        kc1_channel_container = QWidget()
        kc1_channel_container.setFixedSize(80, 28)
        kc1_channel_layout = QHBoxLayout(kc1_channel_container)
        kc1_channel_layout.setContentsMargins(0, 0, 0, 0)
        kc1_channel_layout.setSpacing(0)

        kc1_btn_a = QPushButton("A")
        kc1_btn_a.setCheckable(True)
        kc1_btn_a.setChecked(True)
        kc1_btn_a.setCursor(Qt.CursorShape.PointingHandCursor)
        kc1_btn_a.setStyleSheet(
            "QPushButton {"
            "  background: #34C759;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 14px 0px 0px 14px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:!checked {"
            "  background: #E5E5EA;"
            "  color: #86868B;"
            "}"
        )

        kc1_btn_b = QPushButton("B")
        kc1_btn_b.setCheckable(True)
        kc1_btn_b.setCursor(Qt.CursorShape.PointingHandCursor)
        kc1_btn_b.setStyleSheet(
            "QPushButton {"
            "  background: #34C759;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 0px 14px 14px 0px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:!checked {"
            "  background: #E5E5EA;"
            "  color: #86868B;"
            "}"
        )

        # Button state management handled in main.py _on_channel_valve_switched()
        # Local handlers removed to prevent state conflicts

        kc1_channel_layout.addWidget(kc1_btn_a)
        kc1_channel_layout.addWidget(kc1_btn_b)

        channel_row.addWidget(kc1_channel_container)
        self.sidebar.kc1_channel_btn_a = kc1_btn_a
        self.sidebar.kc1_channel_btn_b = kc1_btn_b

        # KC2 Channel segmented control (C | D)
        kc2_channel_container = QWidget()
        kc2_channel_container.setFixedSize(80, 28)
        kc2_channel_layout = QHBoxLayout(kc2_channel_container)
        kc2_channel_layout.setContentsMargins(0, 0, 0, 0)
        kc2_channel_layout.setSpacing(0)

        kc2_btn_c = QPushButton("C")
        kc2_btn_c.setCheckable(True)
        kc2_btn_c.setChecked(True)
        kc2_btn_c.setCursor(Qt.CursorShape.PointingHandCursor)
        kc2_btn_c.setStyleSheet(
            "QPushButton {"
            "  background: #34C759;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 14px 0px 0px 14px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:!checked {"
            "  background: #E5E5EA;"
            "  color: #86868B;"
            "}"
        )

        kc2_btn_d = QPushButton("D")
        kc2_btn_d.setCheckable(True)
        kc2_btn_d.setCursor(Qt.CursorShape.PointingHandCursor)
        kc2_btn_d.setStyleSheet(
            "QPushButton {"
            "  background: #34C759;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 0px 14px 14px 0px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:!checked {"
            "  background: #E5E5EA;"
            "  color: #86868B;"
            "}"
        )

        # Button state management handled in main.py _on_channel_valve_switched()
        # Local handlers removed to prevent state conflicts

        kc2_channel_layout.addWidget(kc2_btn_c)
        kc2_channel_layout.addWidget(kc2_btn_d)

        channel_row.addWidget(kc2_channel_container)
        self.sidebar.kc2_channel_btn_c = kc2_btn_c
        self.sidebar.kc2_channel_btn_d = kc2_btn_d

        channel_row.addStretch()
        valve_card_layout.addLayout(channel_row)

        valve_section.add_content_widget(valve_card)
        tab_layout.addWidget(valve_section)

    def _build_internal_pump_control(self, tab_layout: QVBoxLayout):
        """Build Internal Pump Control section."""
        pump_section = CollapsibleSection(
            "Internal Pump Control",
            is_expanded=True,
        )

        pump_help = QLabel(
            "Control RPi-driven peristaltic pumps for kinetic channels (synced or independent)",
        )
        pump_help.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "margin: 4px 0px 8px 0px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        pump_section.content_layout.addWidget(pump_help)

        # Card container
        pump_card = QFrame()
        pump_card.setStyleSheet(
            "QFrame {  background: rgba(0, 0, 0, 0.03);  border-radius: 8px;}",
        )
        pump_card_layout = QVBoxLayout(pump_card)
        pump_card_layout.setContentsMargins(12, 8, 12, 8)
        pump_card_layout.setSpacing(6)

        # Sync toggle button
        sync_layout = QHBoxLayout()
        sync_layout.addStretch()

        sync_pump_btn = QPushButton("Sync")
        sync_pump_btn.setCheckable(True)
        sync_pump_btn.setChecked(True)
        sync_pump_btn.setFixedHeight(32)
        sync_pump_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sync_pump_btn.setStyleSheet(
            "QPushButton {"
            "  background: white;"
            "  color: #1D1D1F;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "  padding: 6px 16px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:checked {"
            "  background: #1D1D1F;"
            "  color: white;"
            "}"
            "QPushButton:hover:!checked {"
            "  background: rgba(0, 0, 0, 0.06);"
            "}"
        )
        sync_pump_btn.setToolTip("Toggle pump synchronization")
        sync_layout.addWidget(sync_pump_btn)
        self.sidebar.internal_pump_sync_btn = sync_pump_btn

        pump_card_layout.addLayout(sync_layout)
        self._add_separator(pump_card_layout)

        # Flow rate control
        flowrate_row = QHBoxLayout()
        flowrate_row.setSpacing(10)

        flowrate_label = QLabel("Flowrate:")
        flowrate_label.setFixedWidth(70)
        flowrate_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        flowrate_row.addWidget(flowrate_label)

        flowrate_combo = QComboBox()
        flowrate_combo.addItems(["50", "100", "200", "Flush"])
        flowrate_combo.setCurrentIndex(1)  # Default to 100
        flowrate_combo.setFixedWidth(70)
        flowrate_combo.setStyleSheet(
            "QComboBox {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "  padding: 6px 8px;"
            "  font-size: 13px;"
            "  font-family: -apple-system, 'SF Mono', 'Menlo', monospace;"
            "}"
            "QComboBox:focus {"
            "  border: 2px solid #1D1D1F;"
            "}"
            "QComboBox::drop-down {"
            "  border: none;"
            "  width: 20px;"
            "}"
            "QComboBox QAbstractItemView {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  selection-background-color: rgba(0, 0, 0, 0.1);"
            "  font-family: -apple-system, 'SF Mono', 'Menlo', monospace;"
            "}",
        )
        flowrate_row.addWidget(flowrate_combo)
        self.sidebar.internal_pump_flowrate_combo = flowrate_combo

        # Units label
        flowrate_unit_label = QLabel("µL/min")
        flowrate_unit_label.setStyleSheet(
            "font-size: 12px;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        flowrate_row.addWidget(flowrate_unit_label)

        flowrate_row.addStretch()
        pump_card_layout.addLayout(flowrate_row)

        # Kinetic Channel Pump selection (button group for 1 or 2)
        channel_row = QHBoxLayout()
        channel_row.setSpacing(10)

        channel_label = QLabel("Kinetic Channel Pump:")
        channel_label.setFixedWidth(70)
        channel_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        channel_row.addWidget(channel_label)

        # Button group for channel selection
        channel_btn_layout = QHBoxLayout()
        channel_btn_layout.setSpacing(0)

        btn_1 = QPushButton("1")
        btn_1.setCheckable(True)
        btn_1.setChecked(True)
        btn_1.setFixedSize(50, 28)
        btn_1.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_1.setStyleSheet(
            "QPushButton {"
            "  background: white;"
            "  color: #86868B;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-top-left-radius: 6px;"
            "  border-bottom-left-radius: 6px;"
            "  border-right: none;"
            "  padding: 4px 16px;"
            "  font-size: 12px;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:checked {"
            "  background: #1D1D1F;"
            "  color: white;"
            "}"
            "QPushButton:hover:!checked {"
            "  background: rgba(0, 0, 0, 0.06);"
            "}"
        )
        channel_btn_layout.addWidget(btn_1)
        self.sidebar.internal_pump_channel_btn_1 = btn_1

        btn_2 = QPushButton("2")
        btn_2.setCheckable(True)
        btn_2.setFixedSize(50, 28)
        btn_2.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_2.setStyleSheet(
            "QPushButton {"
            "  background: white;"
            "  color: #86868B;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-top-right-radius: 6px;"
            "  border-bottom-right-radius: 6px;"
            "  padding: 4px 16px;"
            "  font-size: 12px;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:checked {"
            "  background: #1D1D1F;"
            "  color: white;"
            "}"
            "QPushButton:hover:!checked {"
            "  background: rgba(0, 0, 0, 0.06);"
            "}"
        )
        channel_btn_layout.addWidget(btn_2)
        self.sidebar.internal_pump_channel_btn_2 = btn_2

        # Ensure only one button is checked at a time
        def on_btn_1_clicked():
            if btn_1.isChecked():
                btn_2.setChecked(False)
            else:
                btn_1.setChecked(True)

        def on_btn_2_clicked():
            if btn_2.isChecked():
                btn_1.setChecked(False)
            else:
                btn_2.setChecked(True)

        btn_1.clicked.connect(on_btn_1_clicked)
        btn_2.clicked.connect(on_btn_2_clicked)

        channel_row.addLayout(channel_btn_layout)
        channel_row.addStretch()
        pump_card_layout.addLayout(channel_row)

        self._add_separator(pump_card_layout)

        # Calibrate Speed button
        calibrate_btn = QPushButton("Calibrate Speed")
        calibrate_btn.setFixedHeight(36)
        calibrate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        calibrate_btn.setStyleSheet(
            "QPushButton {"
            "  background: white;"
            "  color: #1D1D1F;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 8px;"
            "  padding: 10px 16px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.06);"
            "}"
            "QPushButton:pressed {"
            "  background: rgba(0, 0, 0, 0.1);"
            "}"
        )
        calibrate_btn.setToolTip("Calibrate peristaltic pump speed")
        pump_card_layout.addWidget(calibrate_btn)
        self.sidebar.internal_pump_calibrate_btn = calibrate_btn

        pump_section.add_content_widget(pump_card)
        tab_layout.addWidget(pump_section)

    def _add_flow_rate_control(
        self,
        layout: QVBoxLayout,
        label_text: str,
        spinbox_ref: str,
        default_value: int,
        min_value: int,
        max_value: int,
        tooltip: str = "",
    ):
        """Add a flow rate control with label and spinbox.

        Args:
            layout: Layout to add to
            label_text: Label text for the flow rate
            spinbox_ref: Attribute name on sidebar to store spinbox reference
            default_value: Default flow rate value
            min_value: Minimum flow rate value
            max_value: Maximum flow rate value
            tooltip: Optional tooltip text for the label

        """
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addSpacing(20)

        label = QLabel(label_text)
        label.setFixedWidth(120)
        label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        if tooltip:
            label.setToolTip(tooltip)
        row.addWidget(label)

        spinbox = QSpinBox()
        spinbox.setRange(min_value, max_value)
        spinbox.setValue(default_value)
        spinbox.setFixedWidth(70)
        spinbox.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        spinbox.setStyleSheet(
            "QSpinBox {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "  padding: 6px 8px;"
            "  font-size: 13px;"
            "  font-family: -apple-system, 'SF Mono', 'Menlo', monospace;"
            "}"
            "QSpinBox:focus {"
            "  border: 2px solid #1D1D1F;"
            "  padding: 5px 7px;"
            "}",
        )
        row.addWidget(spinbox)

        # Units label
        unit_label = QLabel("µL/min")
        unit_label.setStyleSheet(
            "font-size: 12px;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        row.addWidget(unit_label)

        row.addStretch()

        # Store spinbox reference
        setattr(self.sidebar, spinbox_ref, spinbox)

        layout.addLayout(row)

    def _add_valve_switch(
        self,
        layout: QVBoxLayout,
        label_text: str,
        switch_ref: str,
    ):
        """Add a valve control with label and on/off switch.

        Args:
            layout: Layout to add to
            label_text: Label text for the valve
            switch_ref: Attribute name on sidebar to store switch reference

        """
        row = QHBoxLayout()
        row.setSpacing(10)

        label = QLabel(label_text)
        label.setFixedWidth(130)
        label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        row.addWidget(label)

        # On/Off toggle switch
        switch = QPushButton("OFF")
        switch.setCheckable(True)
        switch.setFixedSize(60, 28)
        switch.setCursor(Qt.CursorShape.PointingHandCursor)
        switch.setStyleSheet(
            "QPushButton {"
            "  background: #E5E5EA;"
            "  color: #86868B;"
            "  border: none;"
            "  border-radius: 14px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:checked {"
            "  background: #34C759;"
            "  color: white;"
            "}"
        )

        def toggle_text():
            switch.setText("ON" if switch.isChecked() else "OFF")

        switch.clicked.connect(toggle_text)
        row.addWidget(switch)

        row.addStretch()

        # Store switch reference
        setattr(self.sidebar, switch_ref, switch)

        layout.addLayout(row)

    def _button_style(self, primary=False, secondary=False, danger=False):
        """Generate button style CSS.

        Args:
            primary: Use primary (dark) style
            secondary: Use secondary (white) style
            danger: Use danger (red) style

        Returns:
            CSS stylesheet string

        """
        if danger:
            return (
                "QPushButton {"
                "  background: #FF3B30;"
                "  color: white;"
                "  border: 2px solid #E02020;"
                "  border-radius: 6px;"
                "  padding: 10px 16px;"
                "  font-size: 14px;"
                "  font-weight: bold;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: #FF4D42;"
                "  border: 2px solid #FF3B30;"
                "}"
                "QPushButton:pressed {"
                "  background: #C01818;"
                "}"
                "QPushButton:disabled {"
                "  background: #D1D1D6;"
                "  color: #86868B;"
                "  border: 2px solid #C7C7CC;"
                "}"
            )
        elif primary:
            return (
                "QPushButton {"
                "  background: #1D1D1F;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 8px;"
                "  padding: 10px 16px;"
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
                "  background: #86868B;"
                "  color: #D1D1D6;"
                "}"
            )
        else:  # secondary
            return (
                "QPushButton {"
                "  background: white;"
                "  color: #1D1D1F;"
                "  border: 1px solid rgba(0, 0, 0, 0.1);"
                "  border-radius: 8px;"
                "  padding: 10px 16px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.06);"
                "}"
                "QPushButton:pressed {"
                "  background: rgba(0, 0, 0, 0.1);"
                "}"
                "QPushButton:disabled {"
                "  background: #F5F5F7;"
                "  color: #86868B;"
                "}"
            )

    def _add_separator(self, layout: QVBoxLayout):
        """Add a horizontal separator line.

        Args:
            layout: Layout to add separator to

        """
        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet(
            "background: rgba(0, 0, 0, 0.06);border: none;margin: 4px 0px;",
        )
        layout.addWidget(separator)
