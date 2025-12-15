"""Modern Sidebar - Modular tab-based design with lazy loading and event bus integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QScrollArea, QTabWidget, QVBoxLayout, QWidget

from widgets.tabs import (
    DeviceStatusTab,
    ExportTab,
    FlowTab,
    GraphicControlTab,
    SettingsTab,
    StaticTab,
)

if TYPE_CHECKING:
    from core.event_bus import EventBus


class ModernSidebar(QWidget):
    """Modern sidebar with vertical tabs and scrollable content areas.

    Features:
    - Modular tab architecture with dedicated tab classes
    - Lazy loading for performance
    - Event bus integration
    - Backwards compatible with legacy API
    """

    # Signals
    tab_changed = Signal(int, str)  # index, tab_name

    def __init__(
        self,
        event_bus: EventBus | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.event_bus = event_bus

        # Tab instances
        self.device_status_tab: DeviceStatusTab | None = None
        self.graphic_control_tab: GraphicControlTab | None = None
        self.static_tab: StaticTab | None = None
        self.flow_tab: FlowTab | None = None
        self.export_tab: ExportTab | None = None
        self.settings_tab: SettingsTab | None = None

        # Legacy properties
        self.device_widget = None
        self.kinetic_widget = None

        self._setup_ui()

    def _setup_ui(self):
        """Setup the modern sidebar UI with tab classes."""
        self.setStyleSheet("background: #F5F5F7;")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Tab widget with West position (vertical tabs on left)
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.West)
        self.tab_widget.setDocumentMode(False)

        # Modern tab styling
        self.tab_widget.setStyleSheet(
            "QTabWidget::pane {"
            "  border: none;"
            "  background: #FFFFFF;"
            "}"
            "QTabWidget::tab-bar {"
            "  alignment: left;"
            "}"
            "QTabBar::tab {"
            "  background: #F5F5F7;"
            "  color: #86868B;"
            "  padding: 12px 16px;"
            "  border: none;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "  min-width: 120px;"
            "  text-align: left;"
            "}"
            "QTabBar::tab:selected {"
            "  background: #FFFFFF;"
            "  color: #1D1D1F;"
            "  font-weight: 600;"
            "}"
            "QTabBar::tab:hover:!selected {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  color: #1D1D1F;"
            "}",
        )

        # Create tabs using dedicated tab classes
        self._create_tabs()

        # Connect tab change signal
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        main_layout.addWidget(self.tab_widget)

    def _create_tabs(self):
        """Create all tab instances with scroll areas."""
        # Device Status - Always loaded (critical info)
        self.device_status_tab = DeviceStatusTab(event_bus=self.event_bus)
        self._add_tab_with_scroll(
            self.device_status_tab,
            "Device Status",
            "Hardware connection and device information",
        )
        self._connect_tab_to_event_bus(self.device_status_tab, "Device Status")

        # Legacy property
        self.device_widget = self.device_status_tab.device_status_widget

        # Graphic Control - Lazy loaded (heavy plotting)
        self.graphic_control_tab = GraphicControlTab(event_bus=self.event_bus)
        self._add_tab_with_scroll(
            self.graphic_control_tab,
            "Graphic Control",
            "Real-time visualization controls",
        )
        self._connect_tab_to_event_bus(self.graphic_control_tab, "Graphic Control")

        # Static - Lazy loaded
        self.static_tab = StaticTab(event_bus=self.event_bus)
        self._add_tab_with_scroll(
            self.static_tab,
            "Static",
            "Static measurement controls",
        )
        self._connect_tab_to_event_bus(self.static_tab, "Static")

        # Flow - Lazy loaded
        self.flow_tab = FlowTab(event_bus=self.event_bus)
        self._add_tab_with_scroll(
            self.flow_tab,
            "Flow",
            "Flow measurement and kinetic controls",
        )
        self._connect_tab_to_event_bus(self.flow_tab, "Flow")

        # Export - Lazy loaded
        self.export_tab = ExportTab(event_bus=self.event_bus)
        self._add_tab_with_scroll(
            self.export_tab,
            "Export",
            "Data export and file management",
        )
        self._connect_tab_to_event_bus(self.export_tab, "Export")

        # Settings - Lazy loaded
        self.settings_tab = SettingsTab(event_bus=self.event_bus)
        self._add_tab_with_scroll(
            self.settings_tab,
            "Settings",
            "Application configuration",
        )
        self._connect_tab_to_event_bus(self.settings_tab, "Settings")

    def _connect_tab_to_event_bus(self, tab, tab_name: str):
        """Connect tab lifecycle signals to event bus."""
        if self.event_bus is None:
            return

        # Connect tab signals to event bus
        tab.content_loaded.connect(
            lambda: self.event_bus.tab_content_loaded.emit(tab_name),
        )
        tab.content_shown.connect(lambda: self.event_bus.tab_shown.emit(tab_name))
        tab.content_hidden.connect(lambda: self.event_bus.tab_hidden.emit(tab_name))

    def _add_tab_with_scroll(self, tab_widget: QWidget, label: str, tooltip: str):
        """Add a tab with scroll area wrapper."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet(
            "QScrollArea {"
            "  background: #FFFFFF;"
            "  border: none;"
            "}"
            "QScrollBar:vertical {"
            "  background: #F5F5F7;"
            "  width: 10px;"
            "  border-radius: 5px;"
            "}"
            "QScrollBar::handle:vertical {"
            "  background: rgba(0, 0, 0, 0.2);"
            "  border-radius: 5px;"
            "  min-height: 20px;"
            "}"
            "QScrollBar::handle:vertical:hover {"
            "  background: rgba(0, 0, 0, 0.3);"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            "  height: 0px;"
            "}",
        )

        scroll_area.setWidget(tab_widget)
        tab_index = self.tab_widget.addTab(scroll_area, label)
        self.tab_widget.setTabToolTip(tab_index, tooltip)

    def _on_tab_changed(self, index: int):
        """Handle tab change event."""
        tab_name = self.tab_widget.tabText(index)
        self.tab_changed.emit(index, tab_name)

        # Route to event bus
        if self.event_bus is not None:
            self.event_bus.tab_changed.emit(index, tab_name)

    # ===== Backwards Compatibility API =====

    def set_widgets(
        self,
        cycle_controls_widget=None,
        static_cycle_controls=None,
        flow_cycle_controls=None,
    ):
        """Legacy method - set up widgets for backwards compatibility."""
        # Install cycle controls if provided
        if cycle_controls_widget is not None:
            self.install_sensorgram_controls(cycle_controls_widget)

        if static_cycle_controls is not None:
            self.static_tab.install_controls(static_cycle_controls)

        if flow_cycle_controls is not None:
            self.flow_tab.install_controls(flow_cycle_controls)

    def install_sensorgram_controls(self, controls_widget: QWidget) -> None:
        """Legacy method - embed controls into the Graphic Control tab."""
        if self.graphic_control_tab:
            self.graphic_control_tab.install_controls(controls_widget)

    def install_spectroscopy_panel(self, panel_widget: QWidget) -> None:
        """Legacy method - install the spectroscopy preview widget."""
        if self.graphic_control_tab:
            self.graphic_control_tab.install_controls(panel_widget)

    def get_settings_tab(self) -> QWidget | None:
        """Get the Settings tab widget."""
        return self.settings_tab

    def get_export_tab(self) -> QWidget | None:
        """Get the Export tab widget."""
        return self.export_tab


# Legacy class alias for backwards compatibility
class Sidebar(ModernSidebar):
    """Legacy class name - redirects to ModernSidebar."""
