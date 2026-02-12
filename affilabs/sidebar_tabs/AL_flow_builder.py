"""Flow Tab Builder

Handles building the Flow Control tab UI with fluidics experiments configuration.

Author: Affilabs
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
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
from affilabs.utils.logger import logger


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
            self._colored_button_style("#1D1D1F", "#3A3A3C", "#48484A")
        )
        self.prime_btn.setToolTip("Run prime pump sequence (6 cycles)")
        ops_layout.addWidget(self.prime_btn)

        # Clean Pump button
        self.cleanup_btn = QPushButton("🧹 Clean Pump")
        self.cleanup_btn.setFixedHeight(36)
        self.cleanup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cleanup_btn.setStyleSheet(
            self._colored_button_style("#1D1D1F", "#3A3A3C", "#48484A")
        )
        self.cleanup_btn.setToolTip("Run cleanup sequence (9-phase complete cleaning)")
        ops_layout.addWidget(self.cleanup_btn)

        layout.addWidget(ops_card)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _colored_button_style(self, background: str, hover: str, pressed: str):
        """Generate a colored button style with consistent typography.

        Args:
            background: Default background color
            hover: Hover background color
            pressed: Pressed background color

        Returns:
            CSS stylesheet string
        """
        return (
            "QPushButton {"
            f"  background: {background};"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 0px 16px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            f"  background: {hover};"
            "}"
            "QPushButton:pressed {"
            f"  background: {pressed};"
            "}"
        )


class FlowTabBuilder:
    """Builder for constructing the Flow Control tab UI."""

    # UI Style Constants
    FONT_FAMILY_SYSTEM = "-apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif"
    FONT_FAMILY_MONO = "-apple-system, 'SF Mono', 'Menlo', 'Consolas', monospace"

    # Constants for flow control
    FLOWRATE_TO_CONTACT_TIME = {
        0: 240,  # 25 µL/min → 240s contact time
        1: 120,  # 15 µL/min → 120s contact time
        2: 60,   # 10 µL/min → 60s contact time
        3: 30,   # 5 µL/min → 30s contact time
        4: 10,   # Custom → 10s contact time
    }

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

    def _on_synced_flowrate_changed(self):
        """Update contact time based on flowrate preset unless manual mode is active."""
        try:
            manual_check = getattr(self.sidebar, 'synced_manual_time_check', None)
            flowrate_combo = getattr(self.sidebar, 'synced_flowrate_combo', None)
            contact_spin = getattr(self.sidebar, 'synced_contact_time_spin', None)
            if manual_check is None or flowrate_combo is None or contact_spin is None:
                return

            if not manual_check.isChecked():
                flowrate_idx = flowrate_combo.currentIndex()
                contact_time_sec = self.FLOWRATE_TO_CONTACT_TIME.get(flowrate_idx, 60)
                contact_spin.setValue(contact_time_sec)
        finally:
            # Emit signal to update status if pumps are running
            if hasattr(self.sidebar, 'synced_flowrate_changed'):
                self.sidebar.synced_flowrate_changed.emit()

    def _build_intelligence_bar(self, tab_layout: QVBoxLayout):
        """Build intelligence bar section."""
        intel_bar = QFrame()
        intel_bar.setStyleSheet(
            "QFrame {  background: transparent;  border: none;}",
        )
        intel_bar_layout = QHBoxLayout(intel_bar)
        intel_bar_layout.setContentsMargins(8, 4, 8, 4)
        intel_bar_layout.setSpacing(8)

        # Cycle status message (will show running cycles and queued cycles)
        self.sidebar.flow_intel_message_label = QLabel("No cycles running")
        self.sidebar.flow_intel_message_label.setFixedHeight(22)
        self.sidebar.flow_intel_message_label.setStyleSheet(
            "font-size: 14px;"
            "color: #86868B;"
            "background: transparent;"
            "font-weight: 600;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        intel_bar_layout.addWidget(self.sidebar.flow_intel_message_label)

        intel_bar_layout.addStretch()

        tab_layout.addWidget(intel_bar)
        tab_layout.addSpacing(4)

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
            f"font-family: {self.FONT_FAMILY_SYSTEM};"
        )
        plunger_row.addWidget(plunger_title)
        plunger_row.addStretch()

        plunger_value = QLabel("0")
        plunger_value.setStyleSheet(
            "font-size: 15px;"
            "font-weight: 600;"
            "color: #1D1D1F;"
            "background: transparent;"
            f"font-family: {self.FONT_FAMILY_MONO};"
        )
        plunger_row.addWidget(plunger_value)
        self.sidebar.flow_plunger_position = plunger_value

        plunger_unit = QLabel("µL")
        plunger_unit.setStyleSheet(
            "font-size: 11px; color: #86868B; background: transparent; padding-top: 2px;"
            f"font-family: {self.FONT_FAMILY_SYSTEM};"
        )
        plunger_row.addWidget(plunger_unit)

        right_container.addLayout(plunger_row)

        # Contact Time
        contact_row = QHBoxLayout()
        contact_row.setSpacing(4)

        contact_title = QLabel("Contact")
        contact_title.setStyleSheet(
            "font-size: 10px; color: #86868B; background: transparent;"
            f"font-family: {self.FONT_FAMILY_SYSTEM};"
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

        # Card container
        affipump_card = QFrame()
        affipump_card.setStyleSheet(self._card_container_style())
        affipump_card_layout = QVBoxLayout(affipump_card)
        affipump_card_layout.setContentsMargins(12, 8, 12, 8)
        affipump_card_layout.setSpacing(6)

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

        # Maintenance buttons row (Home, Stop, Flush - above flowrate)
        maintenance_layout = QHBoxLayout()
        maintenance_layout.setSpacing(8)

        # Home Pumps button
        home_btn = QPushButton("🏠 Home")
        home_btn.setFixedHeight(34)
        home_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        home_btn.setStyleSheet(
            self._colored_button_style("#007AFF", "#0051D5", "#004BB5")
        )
        home_btn.setToolTip("Home both pumps to zero position")
        maintenance_layout.addWidget(home_btn)
        self.sidebar.pump_home_btn = home_btn

        # Emergency Stop button
        emergency_stop_btn = QPushButton("🛑 STOP")
        emergency_stop_btn.setFixedHeight(28)
        emergency_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        emergency_stop_btn.setStyleSheet(
            self._uniform_button_style("#FF3B30", "#FF4D42", "#C01818")
        )
        emergency_stop_btn.setToolTip("Emergency stop - immediately terminate all pump operations")
        maintenance_layout.addWidget(emergency_stop_btn)
        self.sidebar.pump_emergency_stop_btn = emergency_stop_btn

        # Flush Loop button
        flush_btn = QPushButton("🔄 Flush")
        flush_btn.setFixedHeight(34)
        flush_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        flush_btn.setStyleSheet(
            self._colored_button_style("#007AFF", "#0051D5", "#004BB5")
        )
        flush_btn.setToolTip("Flush sample loop with buffer")
        maintenance_layout.addWidget(flush_btn)
        self.sidebar.flush_btn = flush_btn

        affipump_card_layout.addLayout(maintenance_layout)

        # Flowrate control for Baseline/Injection
        flowrate_row = QHBoxLayout()
        flowrate_row.setSpacing(8)
        flowrate_row.setContentsMargins(0, 0, 0, 0)

        flowrate_label = QLabel("Flow Rate:")
        flowrate_label.setStyleSheet(
            "font-size: 12px; color: #86868B; font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        flowrate_row.addWidget(flowrate_label)

        self.sidebar.injection_flowrate_spin = QSpinBox()
        self.sidebar.injection_flowrate_spin.setRange(1, 30000)
        self.sidebar.injection_flowrate_spin.setValue(15)
        self.sidebar.injection_flowrate_spin.setFixedWidth(80)
        self.sidebar.injection_flowrate_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.sidebar.injection_flowrate_spin.setStyleSheet(
            "QSpinBox { background: white; border: 1px solid rgba(0,0,0,0.1); border-radius: 6px; "
            "padding: 6px 8px; font-size: 13px; font-family: -apple-system, 'SF Mono', 'Menlo', monospace; } "
            "QSpinBox:focus { border: 2px solid #1D1D1F; padding: 5px 7px; }"
        )
        flowrate_row.addWidget(self.sidebar.injection_flowrate_spin)

        flowrate_unit = QLabel("µL/min")
        flowrate_unit.setStyleSheet(
            "font-size: 12px; color: #86868B; font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        flowrate_row.addWidget(flowrate_unit)
        flowrate_row.addStretch()

        affipump_card_layout.addLayout(flowrate_row)

        # Start Buffer row (below flowrate)
        start_flush_layout = QHBoxLayout()
        start_flush_layout.setSpacing(8)

        # Start Buffer button
        start_buffer_btn = QPushButton("▶ Start Buffer")
        start_buffer_btn.setFixedHeight(34)
        start_buffer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_buffer_btn.setStyleSheet(
            self._colored_button_style("#007AFF", "#0051D5", "#004BB5")
        )
        start_buffer_btn.setToolTip("Start continuous buffer flow")
        start_flush_layout.addWidget(start_buffer_btn)
        self.sidebar.start_buffer_btn = start_buffer_btn

        affipump_card_layout.addLayout(start_flush_layout)

        # Injection & Baseline buttons row (below flowrate)
        inject_layout = QHBoxLayout()
        inject_layout.setSpacing(8)

        # Baseline button
        baseline_btn = QPushButton("📊 Baseline")
        baseline_btn.setFixedHeight(34)
        baseline_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        baseline_btn.setStyleSheet(
            self._colored_button_style("#007AFF", "#0051D5", "#004BB5")
        )
        baseline_btn.setToolTip("Run baseline acquisition")
        inject_layout.addWidget(baseline_btn)
        self.sidebar.baseline_btn = baseline_btn

        # Simple Inject button
        inject_simple_btn = QPushButton("💉 Inject (Simple)")
        inject_simple_btn.setFixedHeight(34)
        inject_simple_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        inject_simple_btn.setStyleSheet(
            self._colored_button_style("#007AFF", "#0051D5", "#004BB5")
        )
        inject_simple_btn.setToolTip("Run simple injection (full syringe dispense with contact time)")
        inject_layout.addWidget(inject_simple_btn)
        self.sidebar.inject_simple_btn = inject_simple_btn

        # Advanced Inject button
        inject_advanced_btn = QPushButton("💉 Inject (Advanced)")
        inject_advanced_btn.setFixedHeight(34)
        inject_advanced_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        inject_advanced_btn.setStyleSheet(
            self._colored_button_style("#007AFF", "#0051D5", "#004BB5")
        )
        inject_advanced_btn.setToolTip("Run advanced injection (14-step protocol with spike)")
        inject_layout.addWidget(inject_advanced_btn)
        self.sidebar.inject_partial_btn = inject_advanced_btn

        affipump_card_layout.addLayout(inject_layout)

        # Advanced Settings button row
        advanced_layout = QHBoxLayout()
        advanced_layout.addStretch()

        advanced_btn = QPushButton("⚙️")
        advanced_btn.setFixedSize(32, 32)
        advanced_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        advanced_btn.setStyleSheet(
            "QPushButton {"
            "  background: white;"
            "  color: #1D1D1F;"
            "  border: 1px solid rgba(0, 0, 0, 0.15);"
            "  border-radius: 6px;"
            "  font-size: 16px;"
            "  font-weight: 500;"
            "  padding: 0px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(29, 29, 31, 0.08);"
            "  color: #1D1D1F;"
            "  border: 1px solid #1D1D1F;"
            "}"
            "QPushButton:pressed {"
            "  background: rgba(29, 29, 31, 0.15);"
            "}"
        )
        advanced_btn.setToolTip("Advanced flow rate settings")
        advanced_btn.clicked.connect(self._show_advanced_settings)
        advanced_layout.addWidget(advanced_btn)
        self.sidebar.pump_advanced_btn = advanced_btn

        affipump_card_layout.addLayout(advanced_layout)

        affipump_section.add_content_widget(affipump_card)
        tab_layout.addWidget(affipump_section)
        tab_layout.addSpacing(12)

    def _build_internal_pump_control(self, tab_layout: QVBoxLayout):
        """Build Internal Pump Control section for P4PROPLUS."""
        internal_pump_section = CollapsibleSection(
            "Internal Pump Control (P4PRO+)",
            is_expanded=True,
        )

        # Card container
        internal_pump_card = QFrame()
        internal_pump_card.setStyleSheet(self._white_card_style())
        internal_pump_card_layout = QVBoxLayout(internal_pump_card)
        internal_pump_card_layout.setContentsMargins(16, 12, 16, 12)
        internal_pump_card_layout.setSpacing(8)

        # Status Display
        status_layout = QHBoxLayout()
        status_icon = QLabel("●")
        status_icon.setStyleSheet(
            "color: #86868B;"
            "font-size: 14px;"
            "background: transparent;"
        )
        status_layout.addWidget(status_icon)
        self.sidebar.internal_pump_status_icon = status_icon

        status_label = QLabel("Idle")
        status_label.setStyleSheet(
            "font-size: 12px;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        status_layout.addWidget(status_label)
        self.sidebar.internal_pump_status_label = status_label
        status_layout.addStretch()
        internal_pump_card_layout.addLayout(status_layout)
        self._add_separator(internal_pump_card_layout)

        # Sync Mode Toggle
        sync_layout = QHBoxLayout()
        sync_layout.addStretch()

        sync_pump_btn = QCheckBox("Sync")
        sync_pump_btn.setChecked(True)
        sync_pump_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sync_pump_btn.setStyleSheet(
            "QCheckBox {"
            "  spacing: 6px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QCheckBox::indicator {"
            "  width: 16px;"
            "  height: 16px;"
            "  border-radius: 3px;"
            "  border: 1px solid rgba(0, 0, 0, 0.2);"
            "  background: white;"
            "}"
            "QCheckBox::indicator:checked {"
            "  background: #007AFF;"
            "  border-color: #007AFF;"
            "  image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEgNEw0LjUgNy41TDExIDEiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+PC9zdmc+);"
            "}"
            "QCheckBox::indicator:hover {"
            "  border-color: #007AFF;"
            "}"
        )
        sync_pump_btn.setToolTip("Toggle pump synchronization")
        sync_pump_btn.toggled.connect(self._toggle_pump_sync)
        sync_layout.addWidget(sync_pump_btn)
        self.sidebar.internal_pump_sync_btn = sync_pump_btn

        internal_pump_card_layout.addLayout(sync_layout)
        self._add_separator(internal_pump_card_layout)

        # === SYNCED PUMP CONTROLS (shown when sync is ON) ===
        synced_pump_container = QWidget()
        synced_pump_layout = QVBoxLayout(synced_pump_container)
        synced_pump_layout.setContentsMargins(0, 0, 0, 0)
        synced_pump_layout.setSpacing(8)

        synced_label = QLabel("Both Pumps (Synced)")
        synced_label.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 600;"
            "margin-top: 4px;"
            "font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;",
        )
        synced_pump_layout.addWidget(synced_label)

        # Synced controls - Flowrate Preset, Contact Time, and Toggle Button
        synced_control_layout = QHBoxLayout()
        synced_control_layout.setSpacing(8)

        # Flowrate preset combo (replaces spinbox)
        synced_flowrate_combo = QComboBox()
        synced_flowrate_combo.addItems(["25 µL/min", "50 µL/min", "100 µL/min", "200 µL/min", "Flush (220)"])
        synced_flowrate_combo.setCurrentIndex(1)  # Default to 50 µL/min
        synced_flowrate_combo.setFixedHeight(36)
        synced_flowrate_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        synced_flowrate_combo.setStyleSheet(
            "QComboBox {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.12);"
            "  border-radius: 7px;"
            "  padding: 6px 10px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  color: #1D1D1F;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QComboBox:focus {"
            "  border: 2px solid #FF9500;"
            "  padding: 5px 9px;"
            "}"
            "QComboBox::drop-down {"
            "  border: none;"
            "  width: 20px;"
            "}"
            "QComboBox::down-arrow {"
            "  image: none;"
            "  border-left: 4px solid transparent;"
            "  border-right: 4px solid transparent;"
            "  border-top: 5px solid #1D1D1F;"
            "  margin-right: 8px;"
            "}"
            "QComboBox QAbstractItemView {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.12);"
            "  border-radius: 7px;"
            "  padding: 4px;"
            "  selection-background-color: #FF9500;"
            "  selection-color: white;"
            "}"
        )
        synced_flowrate_combo.setToolTip("Select flowrate preset")
        synced_control_layout.addWidget(synced_flowrate_combo, 1)
        self.sidebar.synced_flowrate_combo = synced_flowrate_combo

        # Contact time spinbox
        synced_contact_time_spin = QSpinBox()
        synced_contact_time_spin.setRange(10, 600)
        synced_contact_time_spin.setValue(60)  # Default to 100 µL/min preset time
        synced_contact_time_spin.setSuffix(" s")
        synced_contact_time_spin.setFixedHeight(36)
        synced_contact_time_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        synced_contact_time_spin.setStyleSheet(
            "QSpinBox {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.12);"
            "  border-radius: 7px;"
            "  padding: 6px 10px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  color: #1D1D1F;"
            f"  font-family: {self.FONT_FAMILY_MONO};"
            "}"
            "QSpinBox:focus {"
            "  border: 2px solid #FF9500;"
            "  padding: 5px 9px;"
            "}"
            "QSpinBox::up-button, QSpinBox::down-button {"
            "  width: 18px;"
            "  border-radius: 4px;"
            "}"
            "QSpinBox::up-button:hover, QSpinBox::down-button:hover {"
            "  background: rgba(0, 0, 0, 0.06);"
            "}"
        )
        synced_contact_time_spin.setToolTip("Valve contact time - auto-calculated unless Manual is checked")
        synced_control_layout.addWidget(synced_contact_time_spin, 1)
        self.sidebar.synced_contact_time_spin = synced_contact_time_spin

        # Manual mode checkbox to disable auto-calculation
        synced_manual_time_check = QCheckBox("Manual")
        synced_manual_time_check.setFixedHeight(36)
        synced_manual_time_check.setCursor(Qt.CursorShape.PointingHandCursor)
        synced_manual_time_check.setStyleSheet(
            "QCheckBox {"
            "  spacing: 6px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QCheckBox::indicator {"
            "  width: 18px;"
            "  height: 18px;"
            "  border: 2px solid rgba(0, 0, 0, 0.2);"
            "  border-radius: 4px;"
            "  background: white;"
            "}"
            "QCheckBox::indicator:checked {"
            "  background: #007AFF;"
            "  border-color: #007AFF;"
            "  image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEgNEw0LjUgNy41TDExIDEiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+PC9zdmc+);"
            "}"
            "QCheckBox::indicator:hover {"
            "  border-color: #007AFF;"
            "}"
        )
        synced_manual_time_check.setToolTip("Check to manually set contact time (disables auto-calculation)")
        synced_control_layout.addWidget(synced_manual_time_check)
        self.sidebar.synced_manual_time_check = synced_manual_time_check

        # Auto-update contact time when flowrate changes (unless manual mode)
        synced_flowrate_combo.currentIndexChanged.connect(self._on_synced_flowrate_changed)

        # Initialize with default contact time
        self._on_synced_flowrate_changed()

        # Start/Stop toggle button for synced pumps
        synced_toggle_btn = QPushButton("▶ Start")
        synced_toggle_btn.setCheckable(True)
        synced_toggle_btn.setFixedHeight(36)
        synced_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        synced_toggle_btn.setStyleSheet(
            self._toggle_button_style(radius=7, padding="0px 18px", font_size=13)
        )
        synced_toggle_btn.setToolTip("Start/Stop both pumps")
        synced_control_layout.addWidget(synced_toggle_btn)
        self.sidebar.synced_toggle_btn = synced_toggle_btn

        synced_pump_layout.addLayout(synced_control_layout)
        internal_pump_card_layout.addWidget(synced_pump_container)
        self.sidebar.synced_pump_container = synced_pump_container

        # === INDIVIDUAL PUMP CONTROLS (shown when sync is OFF) ===
        individual_pumps_container = QWidget()
        individual_pumps_layout = QVBoxLayout(individual_pumps_container)
        individual_pumps_layout.setContentsMargins(0, 0, 0, 0)
        individual_pumps_layout.setSpacing(8)

        # Pump 1 Controls
        pump1_label = QLabel("Pump 1")
        pump1_label.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 600;"
            "margin-top: 4px;"
            "font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;",
        )
        individual_pumps_layout.addWidget(pump1_label)

        # Pump 1 - Flow Rate, Correction, and Toggle Button on same line
        pump1_control_layout = QHBoxLayout()
        pump1_control_layout.setSpacing(8)

        # RPM spinbox
        pump1_rpm_spin = QSpinBox()
        pump1_rpm_spin.setRange(5, 220)
        pump1_rpm_spin.setValue(50)
        pump1_rpm_spin.setSuffix(" RPM")
        pump1_rpm_spin.setFixedHeight(36)
        pump1_rpm_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        pump1_rpm_spin.setStyleSheet(
            "QSpinBox {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.12);"
            "  border-radius: 7px;"
            "  padding: 6px 10px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  color: #1D1D1F;"
            f"  font-family: {self.FONT_FAMILY_MONO};"
            "}"
            "QSpinBox:focus {"
            "  border: 2px solid #FF9500;"
            "  padding: 5px 9px;"
            "}"
            "QSpinBox::up-button, QSpinBox::down-button {"
            "  width: 18px;"
            "  border-radius: 4px;"
            "}"
            "QSpinBox::up-button:hover, QSpinBox::down-button:hover {"
            "  background: rgba(0, 0, 0, 0.06);"
            "}"
        )
        pump1_rpm_spin.setToolTip("Pump 1 flow rate (5-220 µL/min)")
        pump1_control_layout.addWidget(pump1_rpm_spin, 1)
        self.sidebar.pump1_rpm_spin = pump1_rpm_spin

        # Correction factor spinbox
        pump1_corr_spin = QDoubleSpinBox()
        pump1_corr_spin.setRange(0.5, 2.0)
        pump1_corr_spin.setValue(1.0)
        pump1_corr_spin.setSingleStep(0.01)
        pump1_corr_spin.setDecimals(3)
        pump1_corr_spin.setPrefix("×")
        pump1_corr_spin.setFixedHeight(36)
        pump1_corr_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        pump1_corr_spin.setStyleSheet(
            "QDoubleSpinBox {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.12);"
            "  border-radius: 7px;"
            "  padding: 6px 10px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  color: #1D1D1F;"
            f"  font-family: {self.FONT_FAMILY_MONO};"
            "}"
            "QDoubleSpinBox:focus {"
            "  border: 2px solid #FF9500;"
            "  padding: 5px 9px;"
            "}"
            "QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {"
            "  width: 18px;"
            "  border-radius: 4px;"
            "}"
            "QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {"
            "  background: rgba(0, 0, 0, 0.06);"
            "}"
        )
        pump1_corr_spin.setToolTip("Correction factor (from calibration)")
        pump1_control_layout.addWidget(pump1_corr_spin, 1)
        self.sidebar.pump1_correction_spin = pump1_corr_spin
        # Hide Pump 1 correction spinbox in internal pump UI
        try:
            self.sidebar.pump1_correction_spin.hide()
        except Exception:
            pass

        # Start/Stop toggle button for Pump 1
        pump1_toggle_btn = QPushButton("▶ Start")
        pump1_toggle_btn.setCheckable(True)
        pump1_toggle_btn.setFixedHeight(36)
        pump1_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pump1_toggle_btn.setStyleSheet(
            self._toggle_button_style(radius=7, padding="0px 18px", font_size=13)
        )
        pump1_toggle_btn.setToolTip("Start/Stop Pump 1")
        pump1_control_layout.addWidget(pump1_toggle_btn)
        self.sidebar.pump1_toggle_btn = pump1_toggle_btn

        individual_pumps_layout.addLayout(pump1_control_layout)

        internal_pump_card_layout.addWidget(individual_pumps_container)
        self.sidebar.individual_pumps_container = individual_pumps_container
        individual_pumps_container.hide()  # Hidden by default, shown when sync is OFF

        self._add_separator(internal_pump_card_layout)

        # Inject button with channel selection
        inject_container = QWidget()
        inject_layout = QVBoxLayout(inject_container)
        inject_layout.setContentsMargins(0, 0, 0, 0)
        inject_layout.setSpacing(6)

        # Inject button (uses contact time from spinbox)
        inject_30s_btn = QPushButton("💉 Inject")
        inject_30s_btn.setFixedHeight(42)
        inject_30s_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        inject_30s_btn.setProperty("injection_state", "ready")  # States: ready, busy, manual
        inject_30s_btn.setStyleSheet(
            "QPushButton[injection_state='ready'] {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 0px 20px;"
            "  font-size: 14px;"
            "  font-weight: 700;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "  letter-spacing: 0.3px;"
            "}"
            "QPushButton[injection_state='ready']:hover {"
            "  background: #3A3A3C;"
            "}"
            "QPushButton[injection_state='ready']:pressed {"
            "  background: #48484A;"
            "}"
            "QPushButton[injection_state='busy'] {"
            "  background: #48484A;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 0px 20px;"
            "  font-size: 14px;"
            "  font-weight: 700;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "  letter-spacing: 0.3px;"
            "}"
            "QPushButton[injection_state='manual'] {"
            "  background: #2C2C2E;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 0px 20px;"
            "  font-size: 14px;"
            "  font-weight: 700;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "  letter-spacing: 0.3px;"
            "}"
            "QPushButton[injection_state='manual']:hover {"
            "  background: #3A3A3C;"
            "}"
            "QPushButton:disabled {"
            "  background: #D1D1D6;"
            "  color: #86868B;"
            "}"
        )
        inject_30s_btn.setToolTip("✅ Ready to inject")
        inject_layout.addWidget(inject_30s_btn)
        self.sidebar.internal_pump_inject_30s_btn = inject_30s_btn

        internal_pump_card_layout.addWidget(inject_container)

        internal_pump_section.content_layout.addWidget(internal_pump_card)
        tab_layout.addWidget(internal_pump_section)

        # Store reference to section for show/hide control
        self.sidebar.internal_pump_section = internal_pump_section

        # Load saved pump corrections from device config (if available)
        self._load_saved_pump_corrections()

        # Initially hide the section (will be shown when P4PROPLUS detected)
        internal_pump_section.hide()

    def _toggle_pump_sync(self, checked):
        """Toggle synchronized pump mode - shows/hides appropriate controls.

        Args:
            checked: True if sync button is checked (sync ON), False otherwise
        """
        # Show synced controls when checked, individual controls when unchecked
        if hasattr(self.sidebar, 'synced_pump_container'):
            self.sidebar.synced_pump_container.setVisible(checked)
        if hasattr(self.sidebar, 'individual_pumps_container'):
            self.sidebar.individual_pumps_container.setVisible(not checked)

        # When toggling to sync mode, copy pump1 values to synced controls
        if checked:
            if hasattr(self.sidebar, 'pump1_rpm_spin') and hasattr(self.sidebar, 'synced_rpm_spin'):
                self.sidebar.synced_rpm_spin.setValue(self.sidebar.pump1_rpm_spin.value())
            if hasattr(self.sidebar, 'pump1_correction_spin') and hasattr(self.sidebar, 'synced_correction_spin'):
                self.sidebar.synced_correction_spin.setValue(self.sidebar.pump1_correction_spin.value())
            if hasattr(self.sidebar, 'pump1_correction_spin') and hasattr(self.sidebar, 'pump2_correction_spin'):
                self.sidebar.pump2_correction_spin.setValue(self.sidebar.pump1_correction_spin.value())

    def _load_saved_pump_corrections(self):
        """Load saved pump correction factors from EEPROM or device config.

        Loading priority:
        1. Controller EEPROM (if supported - travels with hardware when shipped)
        2. Device config JSON (local calibration data)
        3. Default values (1.0)
        """
        try:
            # Get device_config from hardware manager if available
            if not hasattr(self.sidebar, 'hardware_mgr'):
                return

            hardware_mgr = self.sidebar.hardware_mgr
            if not hardware_mgr:
                return

            pump1_corr = 1.0
            pump2_corr = 1.0
            source = "default"

            # Try to load from controller EEPROM first (highest priority - travels with device)
            ctrl = hardware_mgr._ctrl_raw
            if ctrl and hasattr(ctrl, 'get_pump_corrections'):
                try:
                    eeprom_corrections = ctrl.get_pump_corrections()
                    if eeprom_corrections and isinstance(eeprom_corrections, dict):
                        eeprom_pump1 = eeprom_corrections.get(1, 1.0)
                        eeprom_pump2 = eeprom_corrections.get(2, 1.0)

                        # Only use EEPROM values if they're not default (1.0)
                        if eeprom_pump1 != 1.0 or eeprom_pump2 != 1.0:
                            pump1_corr = eeprom_pump1
                            pump2_corr = eeprom_pump2
                            source = "EEPROM"
                            logger.info("📥 Loaded pump corrections from controller EEPROM")
                except Exception as e:
                    logger.debug(f"Could not read pump corrections from EEPROM: {e}")

            # Fallback to device config if EEPROM didn't have values
            if source == "default" and hasattr(hardware_mgr, 'device_config'):
                device_config = hardware_mgr.device_config
                if device_config:
                    corrections = device_config.get_pump_corrections()
                    config_pump1 = corrections.get("pump_1", 1.0)
                    config_pump2 = corrections.get("pump_2", 1.0)

                    if config_pump1 != 1.0 or config_pump2 != 1.0:
                        pump1_corr = config_pump1
                        pump2_corr = config_pump2
                        source = "device config"
                        logger.info("📥 Loaded pump corrections from device config")

            # Apply to individual pump spinboxes
            if hasattr(self.sidebar, 'pump1_correction_spin'):
                self.sidebar.pump1_correction_spin.setValue(pump1_corr)
            if hasattr(self.sidebar, 'pump2_correction_spin'):
                self.sidebar.pump2_correction_spin.setValue(pump2_corr)

            # Apply to synced pump spinbox (use pump1 value)
            if hasattr(self.sidebar, 'synced_correction_spin'):
                self.sidebar.synced_correction_spin.setValue(pump1_corr)

            if pump1_corr != 1.0 or pump2_corr != 1.0:
                logger.info(f"✓ Pump corrections loaded from {source}: Pump 1={pump1_corr:.3f}, Pump 2={pump2_corr:.3f}")

        except Exception as e:
            logger.warning(f"Could not load saved pump corrections: {e}")

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

        sync_valve_btn = QCheckBox("Sync")
        sync_valve_btn.setChecked(True)
        sync_valve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sync_valve_btn.setStyleSheet(
            "QCheckBox {"
            "  spacing: 6px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QCheckBox::indicator {"
            "  width: 16px;"
            "  height: 16px;"
            "  border-radius: 3px;"
            "  border: 1px solid rgba(0, 0, 0, 0.2);"
            "  background: white;"
            "}"
            "QCheckBox::indicator:checked {"
            "  background: #34C759;"
            "  border-color: #34C759;"
            "  image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEgNEw0LjUgNy41TDExIDEiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+PC9zdmc+);"
            "}"
            "QCheckBox::indicator:hover {"
            "  border-color: #34C759;"
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
        kc1_btn_load.setStyleSheet(self._segmented_button_style(left=True, font_size=10))

        kc1_btn_sensor = QPushButton("Sensor")
        kc1_btn_sensor.setCheckable(True)
        kc1_btn_sensor.setCursor(Qt.CursorShape.PointingHandCursor)
        kc1_btn_sensor.setStyleSheet(self._segmented_button_style(right=True, font_size=10))

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
        kc2_btn_load.setStyleSheet(self._segmented_button_style(left=True, font_size=10))

        kc2_btn_sensor = QPushButton("Sensor")
        kc2_btn_sensor.setCheckable(True)
        kc2_btn_sensor.setCursor(Qt.CursorShape.PointingHandCursor)
        kc2_btn_sensor.setStyleSheet(self._segmented_button_style(right=True, font_size=10))

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
        kc1_btn_a.setStyleSheet(self._segmented_button_style(left=True, font_size=11))

        kc1_btn_b = QPushButton("B")
        kc1_btn_b.setCheckable(True)
        kc1_btn_b.setCursor(Qt.CursorShape.PointingHandCursor)
        kc1_btn_b.setStyleSheet(self._segmented_button_style(right=True, font_size=11))

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
        kc2_btn_c.setStyleSheet(self._segmented_button_style(left=True, font_size=11))

        kc2_btn_d = QPushButton("D")
        kc2_btn_d.setCheckable(True)
        kc2_btn_d.setCursor(Qt.CursorShape.PointingHandCursor)
        kc2_btn_d.setStyleSheet(self._segmented_button_style(right=True, font_size=11))

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
            "QLabel {"
            "  font-size: 12px;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QToolTip {"
            "  background: white;"
            "  color: #1D1D1F;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-size: 12px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}",
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
            "  background: #007AFF;"
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

    def _card_container_style(self, background="rgba(0, 0, 0, 0.03)"):
        """Return consistent card container stylesheet.

        Args:
            background: Background color (default: light gray)

        Returns:
            CSS stylesheet string
        """
        return f"QFrame {{ background: {background}; border-radius: 8px; }}"

    def _white_card_style(self):
        """Return white card container with border."""
        return (
            "QFrame {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "}"
        )

    def _help_text_style(self):
        """Return consistent help text stylesheet."""
        return (
            f"font-size: 11px;"
            f"color: #86868B;"
            f"background: transparent;"
            f"font-style: italic;"
            f"margin: 4px 0px 8px 0px;"
            f"font-family: {self.FONT_FAMILY_SYSTEM};"
        )

    def _colored_button_style(self, background: str, hover: str, pressed: str):
        """Generate a colored button style with consistent typography.

        Args:
            background: Default background color
            hover: Hover background color
            pressed: Pressed background color

        Returns:
            CSS stylesheet string
        """
        return (
            "QPushButton {"
            f"  background: {background};"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 0px 16px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            f"  font-family: {self.FONT_FAMILY_SYSTEM};"
            "}"
            "QPushButton:hover {"
            f"  background: {hover};"
            "}"
            "QPushButton:pressed {"
            f"  background: {pressed};"
            "}"
        )

    def _mono_button_style(self):
        """Generate monochrome dark button style."""
        return (
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 0px 14px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            f"  font-family: {self.FONT_FAMILY_SYSTEM};"
            "}"
            "QPushButton:hover {"
            "  background: #3A3A3C;"
            "}"
            "QPushButton:pressed {"
            "  background: #48484A;"
            "}"
            "QPushButton:disabled {"
            "  background: #D1D1D6;"
            "  color: #86868B;"
            "}"
        )

    def _uniform_button_style(self, background: str, hover: str, pressed: str):
        """Generate uniform button style for AffiPump control section.

        Args:
            background: Default background color
            hover: Hover background color
            pressed: Pressed background color

        Returns:
            CSS stylesheet string with consistent styling
        """
        return (
            "QPushButton {"
            f"  background: {background};"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 0px 14px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            f"  font-family: {self.FONT_FAMILY_SYSTEM};"
            "}"
            "QPushButton:hover {"
            f"  background: {hover};"
            "}"
            "QPushButton:pressed {"
            f"  background: {pressed};"
            "}"
            "QPushButton:disabled {"
            "  background: #D1D1D6;"
            "  color: #86868B;"
            "}"
        )

    def _toggle_button_style(
        self,
        base_bg: str = "#007AFF",
        hover_bg: str = "#0051D5",
        pressed_bg: str = "#004BB5",
        checked_bg: str = "#FF3B30",
        checked_hover: str = "#D32F2F",
        checked_pressed: str = "#B71C1C",
        radius: int = 7,
        padding: str = "0px 18px",
        font_size: int = 13,
        bold: bool = False,
    ) -> str:
        """Generate a Start/Stop toggle button style.

        Returns CSS for a checkable button with distinct unchecked/checked states.
        """
        weight = "700" if bold else "600"
        return (
            "QPushButton {"
            f"  background: {base_bg};"
            "  color: white;"
            "  border: none;"
            f"  border-radius: {radius}px;"
            f"  padding: {padding};"
            f"  font-size: {font_size}px;"
            f"  font-weight: {weight};"
            f"  font-family: {self.FONT_FAMILY_SYSTEM};"
            "}"
            "QPushButton:hover {"
            f"  background: {hover_bg};"
            "}"
            "QPushButton:pressed {"
            f"  background: {pressed_bg};"
            "}"
            "QPushButton:checked {"
            f"  background: {checked_bg};"
            "  color: white;"
            "}"
            "QPushButton:checked:hover {"
            f"  background: {checked_hover};"
            "}"
            "QPushButton:checked:pressed {"
            f"  background: {checked_pressed};"
            "}"
        )

    def _segmented_button_style(self, left: bool = False, right: bool = False, font_size: int = 10) -> str:
        """Generate segmented toggle style for valve controls.

        Left/right determine border radii for paired buttons.
        Checked state is green; unchecked is gray.
        """
        if left:
            radius = "14px 0px 0px 14px"
        elif right:
            radius = "0px 14px 14px 0px"
        else:
            radius = "14px"

        return (
            "QPushButton {"
            "  background: #34C759;"
            "  color: white;"
            "  border: none;"
            f"  border-radius: {radius};"
            f"  font-size: {font_size}px;"
            "  font-weight: 600;"
            f"  font-family: {self.FONT_FAMILY_SYSTEM};"
            "}"
            "QPushButton:!checked {"
            "  background: #E5E5EA;"
            "  color: #86868B;"
            "}"
        )

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
