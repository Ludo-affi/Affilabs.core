"""Base class for sidebar tabs - provides consistent structure and lifecycle management."""

from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame

if TYPE_CHECKING:
    from core.event_bus import EventBus


class BaseSidebarTab(QWidget):
    """
    Base class for sidebar tabs.

    Provides:
    - Consistent styling and layout
    - Lazy loading support
    - Event bus integration
    - Performance tracking
    - Lifecycle hooks (on_show, on_hide, on_load)

    Subclasses should override:
    - _build_content(): Create and return tab content widgets
    - on_show(): Called when tab becomes visible
    - on_hide(): Called when tab is hidden
    """

    # Signals
    content_loaded = Signal()  # Emitted when content is fully loaded
    content_shown = Signal()   # Emitted when tab is shown
    content_hidden = Signal()  # Emitted when tab is hidden

    def __init__(
        self,
        title: str,
        subtitle: str = None,
        lazy_load: bool = False,
        event_bus: EventBus = None,
        parent: QWidget = None
    ):
        """
        Initialize sidebar tab.

        Args:
            title: Tab title displayed at top
            subtitle: Optional subtitle/description
            lazy_load: If True, content is built only when first shown
            event_bus: Optional EventBus for signal routing
            parent: Parent widget
        """
        super().__init__(parent)
        self.title = title
        self.subtitle = subtitle
        self.lazy_load = lazy_load
        self.event_bus = event_bus
        self._content_built = False
        self._is_visible = False

        self._setup_ui()

        # Build content immediately if not lazy loading
        if not lazy_load:
            self._ensure_content_built()

    def _setup_ui(self):
        """Setup base tab UI structure."""
        self.setStyleSheet("background: #FFFFFF;")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(12)

        # Title
        self.title_label = QLabel(self.title)
        self.title_label.setStyleSheet(
            "font-size: 20px;"
            "font-weight: 600;"
            "color: #1D1D1F;"
            "background: transparent;"
            "line-height: 1.2;"
            "letter-spacing: -0.3px;"
            "font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
        )
        self.main_layout.addWidget(self.title_label)

        # Optional subtitle
        if self.subtitle:
            self.subtitle_label = QLabel(self.subtitle)
            self.subtitle_label.setStyleSheet(
                "font-size: 13px;"
                "color: #86868B;"
                "background: transparent;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            self.main_layout.addWidget(self.subtitle_label)

        self.main_layout.addSpacing(12)

        # Content container
        self.content_container = QWidget()
        self.content_container.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(12)

        self.main_layout.addWidget(self.content_container)
        self.main_layout.addStretch()

    def _ensure_content_built(self):
        """Build content if not already built (lazy loading support)."""
        if self._content_built:
            return

        # Call subclass content builder
        content = self._build_content()

        if content is not None:
            if isinstance(content, list):
                # Multiple widgets
                for widget in content:
                    self.content_layout.addWidget(widget)
            else:
                # Single widget
                self.content_layout.addWidget(content)

        self._content_built = True
        self.content_loaded.emit()
        self.on_load()

    def _build_content(self) -> QWidget | list[QWidget] | None:
        """
        Build tab content. Override in subclasses.

        Returns:
            Single widget, list of widgets, or None
        """
        # Default: placeholder
        placeholder = QLabel(f"{self.title} content")
        placeholder.setStyleSheet(
            "font-size: 13px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        return placeholder

    def showEvent(self, event):
        """Handle tab becoming visible."""
        super().showEvent(event)

        # Lazy load content if needed
        if self.lazy_load and not self._content_built:
            self._ensure_content_built()

        if not self._is_visible:
            self._is_visible = True
            self.content_shown.emit()
            self.on_show()

    def hideEvent(self, event):
        """Handle tab becoming hidden."""
        super().hideEvent(event)

        if self._is_visible:
            self._is_visible = False
            self.content_hidden.emit()
            self.on_hide()

    # Lifecycle hooks (override in subclasses)

    def on_load(self):
        """Called after content is built (once per tab lifetime)."""
        pass

    def on_show(self):
        """Called when tab becomes visible."""
        pass

    def on_hide(self):
        """Called when tab becomes hidden."""
        pass

    # Content management helpers

    def clear_content(self):
        """Remove all content widgets."""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._content_built = False

    def replace_content(self, new_content: QWidget | list[QWidget]):
        """Replace current content with new widget(s)."""
        self.clear_content()

        if isinstance(new_content, list):
            for widget in new_content:
                self.content_layout.addWidget(widget)
        else:
            self.content_layout.addWidget(new_content)

        self._content_built = True
