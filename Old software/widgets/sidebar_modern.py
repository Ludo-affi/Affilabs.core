"""New sidebar with modern UI - Direct replacement for old sidebar."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea,
    QLabel, QFrame, QPushButton
)


class CollapsibleSection(QWidget):
    """A collapsible section widget with header and content."""
    
    def __init__(self, title, parent=None, is_expanded=True):
        super().__init__(parent)
        self.is_expanded = is_expanded
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header button
        self.header_btn = QPushButton(f"{'▼' if is_expanded else '▶'} {title}")
        self.header_btn.setCheckable(True)
        self.header_btn.setChecked(is_expanded)
        self.header_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 10px 12px;"
            "  text-align: left;"
            "  font-size: 14px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.08);"
            "}"
            "QPushButton:checked {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  color: #1D1D1F;"
            "}"
        )
        self.header_btn.clicked.connect(self.toggle)
        main_layout.addWidget(self.header_btn)
        
        # Content container
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 8, 0, 0)
        self.content_layout.setSpacing(8)
        
        main_layout.addWidget(self.content_widget)
        
        # Set initial state
        self.content_widget.setVisible(is_expanded)
        
    def toggle(self):
        """Toggle the section expanded/collapsed state."""
        self.is_expanded = not self.is_expanded
        title_text = self.header_btn.text()[2:]
        self.header_btn.setText(f"{'▼' if self.is_expanded else '▶'} {title_text}")
        self.content_widget.setVisible(self.is_expanded)
        
    def add_content_widget(self, widget):
        """Add a widget to the content area."""
        self.content_layout.addWidget(widget)


class ModernSidebar(QWidget):
    """Modern sidebar with vertical tabs - Direct replacement for old sidebar."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.device_widget = None
        self.kinetic_widget = None
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the modern sidebar UI."""
        self.setStyleSheet("background: #F5F5F7;")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Tab widget with West position (vertical tabs)
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.West)
        self.tab_widget.setDocumentMode(False)
        
        # Style the tab widget
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: #FFFFFF;
            }
            QTabBar::tab {
                background: transparent;
                color: #86868B;
                padding: 12px 16px;
                margin: 2px 0px;
                font-size: 13px;
                font-weight: 500;
                border: none;
                text-align: left;
            }
            QTabBar::tab:selected {
                background: rgba(0, 0, 0, 0.06);
                color: #1D1D1F;
                font-weight: 600;
                border-left: 3px solid #1D1D1F;
            }
            QTabBar::tab:hover:!selected {
                background: rgba(0, 0, 0, 0.03);
                color: #1D1D1F;
            }
        """)
        
        # Create tabs with placeholder containers
        self.tabs = {}
        tab_names = ["Device Status", "Graphic Control", "Settings", "Static", "Flow", "Export"]
        
        for tab_name in tab_names:
            scroll_area = self._create_tab_container(tab_name)
            self.tabs[tab_name] = scroll_area.widget()
            self.tab_widget.addTab(scroll_area, tab_name)
        
        main_layout.addWidget(self.tab_widget)
        
    def _create_tab_container(self, title):
        """Create a scrollable container for tab content."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background: #FFFFFF;
                border: none;
            }
            QScrollBar:vertical {
                background: #F5F5F7;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 0, 0, 0.2);
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0, 0, 0, 0.3);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        content = QWidget()
        content.setStyleSheet("background: #FFFFFF;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # Add title
        title_label = QLabel(title)
        title_label.setStyleSheet(
            "font-size: 20px;"
            "font-weight: 600;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
        )
        layout.addWidget(title_label)
        layout.addSpacing(8)
        layout.addStretch()
        
        scroll_area.setWidget(content)
        return scroll_area
        
    def set_widgets(self, cycle_controls_widget=None, static_cycle_controls=None, flow_cycle_controls=None):
        """Set widget content in tabs - Compatible with old sidebar interface."""
        # Import here to avoid circular dependencies
        from widgets.device import Device
        from widgets.kinetics import Kinetic
        
        # Device Status tab
        if self.device_widget is None:
            self.device_widget = Device()
            device_container = self.tabs["Device Status"]
            device_layout = device_container.layout()
            
            # Clear placeholder content
            while device_layout.count() > 2:  # Keep title and spacing
                item = device_layout.takeAt(2)
                if item.widget():
                    item.widget().deleteLater()
            
            # Remove stretch
            if device_layout.count() > 0:
                last_item = device_layout.itemAt(device_layout.count() - 1)
                if last_item.spacerItem():
                    device_layout.removeItem(last_item)
            
            device_layout.addWidget(self.device_widget)
            device_layout.addStretch()
        
        # Graphic Control tab (Kinetic)
        if self.kinetic_widget is None:
            self.kinetic_widget = Kinetic()
            kinetic_container = self.tabs["Graphic Control"]
            kinetic_layout = kinetic_container.layout()
            
            # Clear placeholder content
            while kinetic_layout.count() > 2:
                item = kinetic_layout.takeAt(2)
                if item.widget():
                    item.widget().deleteLater()
            
            # Remove stretch
            if kinetic_layout.count() > 0:
                last_item = kinetic_layout.itemAt(kinetic_layout.count() - 1)
                if last_item.spacerItem():
                    kinetic_layout.removeItem(last_item)
            
            kinetic_layout.addWidget(self.kinetic_widget)
            kinetic_layout.addStretch()
        
        # Install cycle controls in Static tab if provided
        if static_cycle_controls is not None:
            static_container = self.tabs["Static"]
            static_layout = static_container.layout()
            
            # Clear placeholder
            while static_layout.count() > 2:
                item = static_layout.takeAt(2)
                if item.widget():
                    item.widget().deleteLater()
            
            # Remove stretch
            if static_layout.count() > 0:
                last_item = static_layout.itemAt(static_layout.count() - 1)
                if last_item.spacerItem():
                    static_layout.removeItem(last_item)
            
            static_layout.addWidget(static_cycle_controls)
            static_layout.addStretch()
        
        # Install cycle controls in Flow tab if provided
        if flow_cycle_controls is not None:
            flow_container = self.tabs["Flow"]
            flow_layout = flow_container.layout()
            
            # Clear placeholder
            while flow_layout.count() > 2:
                item = flow_layout.takeAt(2)
                if item.widget():
                    item.widget().deleteLater()
            
            # Remove stretch
            if flow_layout.count() > 0:
                last_item = flow_layout.itemAt(flow_layout.count() - 1)
                if last_item.spacerItem():
                    flow_layout.removeItem(last_item)
            
            flow_layout.addWidget(flow_cycle_controls)
            flow_layout.addStretch()
    
    def get_settings_tab(self):
        """Get the Settings tab container widget - API compatibility method."""
        return self.tabs.get("Settings")
    
    def get_data_tab(self):
        """Get the Export/Data tab container widget - API compatibility method."""
        return self.tabs.get("Export")
    
    def install_sensorgram_controls(self, controls_widget):
        """Embed sensorgram controls into the Flow tab - API compatibility method."""
        self._replace_tab_content("Flow", controls_widget)
    
    def install_spectroscopy_panel(self, panel_widget):
        """Install spectroscopy preview widget - API compatibility method."""
        # We don't have a Spectroscopy tab yet, but add it for future compatibility
        pass
    
    def _replace_tab_content(self, title, widget):
        """Replace tab content with a new widget."""
        container = self.tabs.get(title)
        if container is None:
            return
        
        layout = container.layout()
        if layout is None:
            return
        
        # Clear all content except title (first 2 items: title label + spacing)
        while layout.count() > 2:
            item = layout.takeAt(2)
            if item.widget():
                item.widget().deleteLater()
        
        # Remove stretch if present
        if layout.count() > 0:
            last_item = layout.itemAt(layout.count() - 1)
            if last_item.spacerItem():
                layout.removeItem(last_item)
        
        # Add new widget
        widget.setParent(container)
        widget.show()
        layout.addWidget(widget)
        layout.addStretch()
