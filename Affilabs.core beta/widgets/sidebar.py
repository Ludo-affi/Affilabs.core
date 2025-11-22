"""Modern Sidebar - Prototype-based design with clean tabs and content areas."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QTabWidget, QVBoxLayout, QWidget, QScrollArea, QFrame
)

from widgets.device_status import DeviceStatusWidget


class ModernSidebar(QWidget):
    """Modern sidebar with vertical tabs and scrollable content areas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.device_widget = None
        self.kinetic_widget = None
        self._tab_pages: dict[str, QWidget] = {}
        self._setup_ui()

    def _setup_ui(self):
        """Setup the modern sidebar UI matching prototype."""
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
            "}"
        )

        # Add tabs with prototype structure
        tab_definitions = [
            ("Device Status", "Device Status"),
            ("Graphic Control", "Graphic Control"),
            ("Static", "Static"),
            ("Flow", "Flow"),
            ("Export", "Export"),
            ("Settings", "Settings"),
        ]

        for label, tooltip in tab_definitions:
            # Create scroll area for tab content
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
                "}"
            )

            tab_content = QWidget()
            tab_content.setStyleSheet("background: #FFFFFF;")
            tab_layout = QVBoxLayout(tab_content)
            tab_layout.setContentsMargins(20, 20, 20, 20)
            tab_layout.setSpacing(12)

            # Title
            title = QLabel(f"{tooltip}")
            title.setStyleSheet(
                "font-size: 20px;"
                "font-weight: 600;"
                "color: #1D1D1F;"
                "background: transparent;"
                "line-height: 1.2;"
                "letter-spacing: -0.3px;"
                "font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            )
            tab_layout.addWidget(title)

            # Special handling for Device Status tab
            if label == "Device Status":
                tab_layout.addSpacing(12)
                # Add DeviceStatusWidget with modern design
                self.device_status_widget = DeviceStatusWidget()
                tab_layout.addWidget(self.device_status_widget)
                tab_layout.addStretch()
            else:
                # Placeholder for other tabs
                tab_layout.addSpacing(12)
                placeholder = QLabel(f"{label} content will be added here")
                placeholder.setStyleSheet(
                    "font-size: 13px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-style: italic;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(placeholder)
                tab_layout.addStretch()

            scroll_area.setWidget(tab_content)
            tab_index = self.tab_widget.addTab(scroll_area, label)
            self.tab_widget.setTabToolTip(tab_index, tooltip)
            self._tab_pages[label] = tab_content

        main_layout.addWidget(self.tab_widget)

    def set_widgets(self, cycle_controls_widget=None, static_cycle_controls=None, flow_cycle_controls=None):
        """Set up legacy widgets for backwards compatibility."""
        # Device widget is now handled by DeviceStatusWidget in Device Status tab
        # Keep reference for backwards compatibility
        if hasattr(self, 'device_status_widget'):
            self.device_widget = self.device_status_widget

        # Install cycle controls if provided
        if cycle_controls_widget is not None:
            self.install_sensorgram_controls(cycle_controls_widget)

        if static_cycle_controls is not None:
            self._replace_tab_content("Static", static_cycle_controls)

        if flow_cycle_controls is not None:
            self._replace_tab_content("Flow", flow_cycle_controls)

    def install_sensorgram_controls(self, controls_widget: QWidget) -> None:
        """Embed controls into the Graphic Control tab."""
        self._replace_tab_content("Graphic Control", controls_widget)

    def install_spectroscopy_panel(self, panel_widget: QWidget) -> None:
        """Install the spectroscopy preview widget (deprecated - use Graphic Control)."""
        self._replace_tab_content("Graphic Control", panel_widget)

    def get_settings_tab(self) -> QWidget | None:
        """Get the Settings tab container widget."""
        return self._tab_pages.get("Settings")

    def get_export_tab(self) -> QWidget | None:
        """Get the Export tab container widget."""
        return self._tab_pages.get("Export")

    def _replace_tab_content(self, title: str, widget: QWidget) -> None:
        """Replace the content of a specific tab with a custom widget."""
        page = self._tab_pages.get(title)
        if page is None:
            return

        layout = page.layout()
        if layout is None:
            return

        # Clear existing content (keep title, remove placeholder and add new widget)
        items_to_remove = []
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget():
                widget_item = item.widget()
                # Keep the title (first QLabel with specific styling)
                if isinstance(widget_item, QLabel) and "20px" in widget_item.styleSheet():
                    continue
                items_to_remove.append(widget_item)

        for item_widget in items_to_remove:
            layout.removeWidget(item_widget)
            item_widget.setParent(None)
            item_widget.deleteLater()

        # Add new widget
        widget.setParent(page)
        widget.show()
        layout.addWidget(widget)
        layout.addStretch()


# Legacy class alias for backwards compatibility
class Sidebar(ModernSidebar):
    """Legacy class name - redirects to ModernSidebar."""
    pass
