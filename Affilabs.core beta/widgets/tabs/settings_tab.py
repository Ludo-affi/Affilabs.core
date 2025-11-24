"""Settings tab - application settings and configuration."""

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
    - Application preferences
    - Hardware configuration
    - UI customization
    - Advanced settings
    """

    def __init__(self, event_bus: "EventBus | None" = None, parent: "QWidget | None" = None):
        super().__init__(
            title="Settings",
            subtitle="Application configuration",
            lazy_load=True,
            event_bus=event_bus,
            parent=parent
        )

    def _build_content(self) -> "QWidget | None":
        """Build settings content."""
        # Placeholder for now
        placeholder = QLabel("Settings will be added here")
        placeholder.setStyleSheet(
            "font-size: 13px; "
            "color: #86868B; "
            "background: transparent; "
            "font-style: italic; "
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif; "
        )
        return placeholder
