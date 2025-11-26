"""Settings tab - hardware configuration and calibration controls."""

from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget, QLabel
from widgets.tabs.base_tab import BaseSidebarTab

if TYPE_CHECKING:
    from core.event_bus import EventBus


class SettingsTab(BaseSidebarTab):
    """
    Settings tab.

    Provides:
    - Hardware configuration (polarizer, LED intensities)
    - Calibration controls (Simple, Full, OEM)
    - Advanced settings
    """

    def __init__(self, event_bus: "EventBus | None" = None, parent: "QWidget | None" = None):
        super().__init__(
            title="Settings",
            subtitle="Hardware configuration and calibration",
            lazy_load=True,
            event_bus=event_bus,
            parent=parent
        )

        self._controls_widget: "QWidget | None" = None

    def _build_content(self) -> "QWidget | None":
        """Build settings content."""
        if self._controls_widget is not None:
            return self._controls_widget

        # Default placeholder
        placeholder = QLabel("Settings controls will be added here")
        placeholder.setStyleSheet(
            "font-size: 13px; "
            "color: #86868B; "
            "background: transparent; "
            "font-style: italic; "
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        return placeholder

    def install_controls(self, controls_widget: QWidget):
        """Install settings controls."""
        self._controls_widget = controls_widget
        if self._content_built:
            self.replace_content(controls_widget)
