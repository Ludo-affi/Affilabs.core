from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget, QScrollArea

from ui.ui_sidebar import Ui_Sidebar
from widgets.device import Device
from widgets.kinetics import Kinetic


class Sidebar(QWidget):
    device_widget = None
    kinetic_widget = None

    def __init__(self):
        super().__init__()
        self.ui = Ui_Sidebar()
        self.ui.setupUi(self)
        self._tab_placeholders: dict[str, QLabel] = {}
        self._tab_pages: dict[str, QWidget] = {}
        self._setup_tab_layout()

    def set_widgets(self, cycle_controls_widget=None, static_cycle_controls=None, flow_cycle_controls=None):
        # display device widget inside Device Status tab
        # Always create fresh widgets to ensure proper initialization
        self.device_widget = Device()

        # Ensure device_frame has a layout
        if self.ui.device_frame.layout() is None:
            from PySide6.QtWidgets import QVBoxLayout
            device_layout = QVBoxLayout(self.ui.device_frame)
            device_layout.setContentsMargins(0, 0, 0, 0)
            device_layout.setSpacing(0)

        # Clear any existing widgets first
        while self.ui.device_frame.layout().count():
            child = self.ui.device_frame.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add device widget to the frame's layout
        self.ui.device_frame.layout().addWidget(self.device_widget)
        self.device_widget.show()
        self._hide_placeholder("Device Status")

        # display kinetic widget inside Graphic Control tab
        # Always create fresh widgets to ensure proper initialization
        self.kinetic_widget = Kinetic()

        # Ensure kinetic_frame has a layout
        if self.ui.kinetic_frame.layout() is None:
            from PySide6.QtWidgets import QVBoxLayout
            kinetic_layout = QVBoxLayout(self.ui.kinetic_frame)
            kinetic_layout.setContentsMargins(0, 0, 0, 0)
            kinetic_layout.setSpacing(0)

        # Clear any existing widgets first
        while self.ui.kinetic_frame.layout().count():
            child = self.ui.kinetic_frame.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add kinetic widget to the frame's layout
        self.ui.kinetic_frame.layout().addWidget(self.kinetic_widget)
        self.kinetic_widget.show()
        self._hide_placeholder("Graphic Control")

        # Install cycle controls in Graph Controls tab if provided
        if cycle_controls_widget is not None:
            self.install_sensorgram_controls(cycle_controls_widget)

        # Install cycle controls in Static tab if provided
        if static_cycle_controls is not None:
            self._replace_tab_content("Static", static_cycle_controls)

        # Install cycle controls in Flow tab if provided
        if flow_cycle_controls is not None:
            self._replace_tab_content("Flow", flow_cycle_controls)

    def _setup_tab_layout(self) -> None:
        """Embed a styled QTabWidget into the sidebar and show empty layout."""
        # Remove legacy labels/frames from the original stacked layout
        for widget in (self.ui.label_2, self.ui.label):
            if widget is None:
                continue
            self.ui.verticalLayout.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()  # Properly delete the widget

        # Recreate frames for use in tabs (without adding them to old layout)
        from PySide6.QtWidgets import QFrame
        if hasattr(self.ui, 'device_frame'):
            self.ui.device_frame.setParent(None)
        if hasattr(self.ui, 'kinetic_frame'):
            self.ui.kinetic_frame.setParent(None)

        self.ui.device_frame = QFrame()
        self.ui.kinetic_frame = QFrame()

        # Prepare the tab widget container
        self.tab_widget = QTabWidget(self)
        self.tab_widget.setObjectName("sidebarTabWidget")
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.West)
        self.tab_widget.setMovable(False)
        self.tab_widget.setDocumentMode(False)

        self.tab_widget.setStyleSheet(
            "QTabWidget::pane {"
            "  border: 1px solid #DADCE0;"
            "  border-radius: 8px;"
            "  background: #FFFFFF;"
            "  margin-left: 10px;"
            "}"
            "QTabWidget::tab-bar {"
            "  left: 8px;"
            "}"
            "QTabBar::tab {"
            "  background: #F0F0F0;"
            "  color: #000000;"
            "  border: 1px solid #CCCCCC;"
            "  padding: 6px 14px;"
            "  margin: 2px;"
            "  font-family: 'Segoe UI';"
            "  font-size: 11px;"
            "  min-width: 60px;"
            "}"
            "QTabBar::tab:selected {"
            "  background: #FFFFFF;"
            "  border-bottom-color: #FFFFFF;"
            "}"
        )

        # Build the requested tab order using existing frames + placeholders
        # Shortened labels for half-width tabs with full tooltips
        tab_definitions = [
            ("Dev", "Device Status", self.ui.device_frame, "Device controls will appear here."),
            ("Ctrl", "Graphic Control", self.ui.kinetic_frame, "Flow/Kinetic controls will appear here."),
            ("Spec", "Spectroscopy", None, "Spectroscopy preview will appear here."),
            ("Flow", "Flow Controls", None, "Live graph controls will appear here."),
            ("Cal", "Static Calibration", None, "Static calibration controls coming soon."),
            ("Data", "Data Management", None, "Data export and management controls."),
            ("Set", "Settings", None, "Graph display settings."),
        ]

        for short_label, full_name, frame, placeholder in tab_definitions:
            if frame is not None:
                self._add_tab_with_frame(short_label, full_name, frame, placeholder)
            else:
                self._add_placeholder_tab(short_label, full_name, placeholder, register_placeholder=True)

        # Move settings widget to Graph Controls tab if available
        try:
            from widgets.settings_menu import Settings
            # Settings widget needs reference channel dialog and advanced menu which aren't available yet
            # Skip for now - will be added when device is connected
            # settings_widget = Settings(...)
            # self._replace_tab_content("Graph Controls", settings_widget)
            pass
        except Exception as e:
            print(f"Could not load settings widget in Graph Controls tab: {e}")

        # Add the tab widget to the sidebar layout
        self.ui.verticalLayout.addWidget(self.tab_widget)
        self.tab_widget.setCurrentIndex(0)

    def _add_tab_with_frame(self, short_label: str, full_name: str, frame: QWidget, placeholder_text: str) -> None:
        """Create a tab that hosts an existing frame with a placeholder label."""
        from PySide6.QtWidgets import QScrollArea

        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 12, 12, 12)  # Increased left margin from 12 to 20
        layout.setSpacing(8)
        frame.setParent(container)
        frame.show()
        layout.addWidget(frame)

        placeholder = QLabel(placeholder_text, container)
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: rgb(120, 120, 120);")
        placeholder.setWordWrap(True)
        layout.addWidget(placeholder)
        layout.addStretch(1)

        scroll.setWidget(container)
        tab_index = self.tab_widget.addTab(scroll, short_label)
        self.tab_widget.setTabToolTip(tab_index, full_name)  # Add tooltip with full name
        self._tab_pages[full_name] = container  # Store with full name for lookups
        self._tab_placeholders[full_name] = placeholder

    def _add_placeholder_tab(self, short_label: str, full_name: str, text: str, *, register_placeholder: bool = False) -> None:
        """Add an empty tab with centered helper text."""
        from PySide6.QtWidgets import QScrollArea

        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 40, 20, 40)  # Increased left margin from 20 to match
        layout.setSpacing(12)
        label = QLabel(text, page)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: rgb(140, 140, 140);")
        label.setWordWrap(True)
        layout.addStretch(1)
        layout.addWidget(label)
        layout.addStretch(2)

        scroll.setWidget(page)
        tab_index = self.tab_widget.addTab(scroll, short_label)
        self.tab_widget.setTabToolTip(tab_index, full_name)  # Add tooltip with full name
        self._tab_pages[full_name] = page  # Store with full name for lookups
        if register_placeholder:
            self._tab_placeholders[full_name] = label

    def _hide_placeholder(self, title: str) -> None:
        placeholder = self._tab_placeholders.get(title)
        if placeholder:
            placeholder.hide()

    def install_sensorgram_controls(self, controls_widget: QWidget) -> None:
        """Embed the legacy sensorgram controls into the Flow tab."""
        self._replace_tab_content("Flow", controls_widget)

    def install_spectroscopy_panel(self, panel_widget: QWidget) -> None:
        """Install the spectroscopy preview widget inside the Spectroscopy tab."""
        self._replace_tab_content("Spectroscopy", panel_widget)

    def get_settings_tab(self) -> QWidget:
        """Get the Settings tab container widget."""
        return self._tab_pages.get("Settings")

    def get_data_tab(self) -> QWidget:
        """Get the Data tab container widget."""
        return self._tab_pages.get("Data")

    def _replace_tab_content(self, title: str, widget: QWidget) -> None:
        page = self._tab_pages.get(title)
        if page is None:
            return

        layout = page.layout()
        if layout is None:
            layout = QVBoxLayout(page)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(8)

        placeholder = self._tab_placeholders.get(title)
        if placeholder is not None:
            placeholder.hide()

        while layout.count():
            item = layout.takeAt(0)
            existing = item.widget()
            if existing is not None:
                existing.setParent(None)

        widget.setParent(page)
        widget.show()
        layout.addWidget(widget)
