"""Device Status tab - displays hardware connection status and device information."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from widgets.device_status import DeviceStatusWidget
from widgets.tabs.base_tab import BaseSidebarTab

if TYPE_CHECKING:
    from core.event_bus import EventBus


class DeviceStatusTab(BaseSidebarTab):
    """Device Status tab.

    Displays:
    - Hardware connection status
    - Device information
    - Sensor status
    - LED/detector status
    """

    def __init__(self, event_bus: EventBus = None, parent: QWidget = None):
        super().__init__(
            title="Device Status",
            subtitle=None,
            lazy_load=False,  # Always load immediately - critical info
            event_bus=event_bus,
            parent=parent,
        )

        # Keep reference for backwards compatibility
        self.device_status_widget = None

    def _build_content(self) -> QWidget:
        """Build device status content."""
        self.device_status_widget = DeviceStatusWidget()
        return self.device_status_widget

    def on_show(self):
        """Called when tab becomes visible."""
        # Could trigger status refresh here if needed

    def on_hide(self):
        """Called when tab is hidden."""
        # Could pause status updates here to save resources

    # Backwards compatibility property
    @property
    def device_widget(self):
        """Legacy property name."""
        return self.device_status_widget
