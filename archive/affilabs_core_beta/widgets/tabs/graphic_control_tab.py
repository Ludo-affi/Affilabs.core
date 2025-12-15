"""Graphic Control tab - sensorgram and spectroscopy visualization controls."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QWidget

from widgets.tabs.base_tab import BaseSidebarTab

if TYPE_CHECKING:
    from core.event_bus import EventBus


class GraphicControlTab(BaseSidebarTab):
    """Graphic Control tab.

    Hosts:
    - Sensorgram controls (cycle controls widget)
    - Spectroscopy preview panel
    - Live plotting controls

    Supports lazy loading for performance.
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(
            title="Graphic Control",
            subtitle="Real-time visualization controls",
            lazy_load=True,  # Lazy load - heavy plotting widgets
            event_bus=event_bus,
            parent=parent,
        )

        # Control widget reference (set via install methods)
        self._controls_widget: QWidget | None = None

    def _build_content(self) -> QWidget | None:
        """Build graphic control content."""
        if self._controls_widget is not None:
            return self._controls_widget

        # Default placeholder if no controls installed
        placeholder = QLabel("Awaiting sensorgram controls...")
        placeholder.setStyleSheet(
            "font-size: 13px; "
            "color: #86868B; "
            "background: transparent; "
            "font-style: italic; "
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        return placeholder

    def install_controls(self, controls_widget: QWidget):
        """Install sensorgram/spectroscopy controls.

        Args:
            controls_widget: The control widget to display

        """
        self._controls_widget = controls_widget

        # If content already built, replace it
        if self._content_built:
            self.replace_content(controls_widget)
        # Otherwise it will be built on first show (lazy loading)

    # Backwards compatibility aliases
    def install_sensorgram_controls(self, controls_widget: QWidget):
        """Legacy method name."""
        self.install_controls(controls_widget)

    def install_spectroscopy_panel(self, panel_widget: QWidget):
        """Legacy method name."""
        self.install_controls(panel_widget)

    def on_show(self):
        """Called when tab becomes visible."""
        # Could start/resume plotting updates here

    def on_hide(self):
        """Called when tab is hidden."""
        # Could pause plotting updates to save resources
