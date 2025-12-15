"""Flow tab - flow cycle controls and kinetic measurements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QWidget

from widgets.tabs.base_tab import BaseSidebarTab

if TYPE_CHECKING:
    from core.event_bus import EventBus


class FlowTab(BaseSidebarTab):
    """Flow cycle controls tab.

    Hosts:
    - Flow measurement configuration
    - Kinetic pump controls
    - Valve switching controls
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(
            title="Flow",
            subtitle="Flow measurement and kinetic controls",
            lazy_load=True,
            event_bus=event_bus,
            parent=parent,
        )

        self._controls_widget: QWidget | None = None

    def _build_content(self) -> QWidget | None:
        """Build flow controls content."""
        if self._controls_widget is not None:
            return self._controls_widget

        # Default placeholder
        placeholder = QLabel("Flow controls will be added here")
        placeholder.setStyleSheet(
            "font-size: 13px; "
            "color: #86868B; "
            "background: transparent; "
            "font-style: italic; "
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        return placeholder

    def install_controls(self, controls_widget: QWidget):
        """Install flow cycle controls."""
        self._controls_widget = controls_widget
        if self._content_built:
            self.replace_content(controls_widget)
