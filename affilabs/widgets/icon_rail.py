"""IconRail — 48px fixed-width vertical tab strip on the far left.

Replaces the sidebar's built-in East tab bar. Controls which sidebar panel
is visible. Tab bar on AffilabsSidebar.tab_widget is hidden after this is
wired in.

Usage::
    rail = IconRail(parent=main_window)
    rail.set_sidebar(sidebar)          # call after both are created
    main_layout.insertWidget(0, rail)  # add before content

Tab slots (matching sidebar.tab_indices):
    Flow     index 0  — shown only when hardware enables P4PRO/P4PROPLUS
    Export   index 1  — always shown
    Settings index 2  — always shown
    Method removed from sidebar — button moved to transport bar
"""

import logging

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

logger = logging.getLogger(__name__)

# ─── SVG icons (currentColor = filled by _make_icon) ─────────────────────────

_ICONS: dict[str, str] = {
    "Method": (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" stroke-width="1.2"/>'
        '<path d="M3 8h18M3 13h18M3 18h18M9 3v18" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>'
        '</svg>'
    ),
    "Export": (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M12 3v12" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>'
        '<path d="M8 7l4-4 4 4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M4 14v5a2 2 0 002 2h12a2 2 0 002-2v-5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>'
        '</svg>'
    ),
    "Settings": (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.4"/>'
        '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33'
        ' 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1.08-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06'
        'a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09'
        'A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0'
        ' 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33'
        'l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4'
        'h-.09a1.65 1.65 0 0 0-1.51 1z"'
        ' stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    ),
    "Flow": (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="12" cy="12" r="7" stroke="currentColor" stroke-width="1.4"/>'
        '<circle cx="12" cy="12" r="2.5" fill="currentColor"/>'
        '<path d="M3 12H5M19 12h2M19 12l-2-2m2 2l-2 2"'
        ' stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    ),
    "User": (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="12" cy="8" r="4" stroke="currentColor" stroke-width="1.4"/>'
        '<path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" stroke="currentColor" stroke-width="1.4"'
        ' stroke-linecap="round"/>'
        '</svg>'
    ),
    "Timer": (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="12" cy="13" r="7" stroke="currentColor" stroke-width="1.4"/>'
        '<path d="M12 10v3.5l2.5 1.5" stroke="currentColor" stroke-width="1.4"'
        ' stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M9 4h6M12 4v2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>'
        '</svg>'
    ),
    "Spectrum": (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M2 12 C4 6 6 6 8 12 C10 18 12 18 14 12 C16 6 18 6 20 12 L22 12"'
        ' stroke="currentColor" stroke-width="2" stroke-linecap="round"/>'
        '</svg>'
    ),
}

_COLOR_INACTIVE = "#8E8E93"
_COLOR_ACTIVE = "#2E30E3"
_COLOR_SPECTRUM_OFF = "#5AC8FA"
_COLOR_SPECTRUM_ON = "#0A84FF"
_BG = "#F5F5F7"
_ACTIVE_BG = "rgba(46,48,227,0.10)"
_WIDTH = 48


def _make_icon(svg: str, color: str) -> QIcon:
    svg_colored = svg.replace("currentColor", color)
    renderer = QSvgRenderer(svg_colored.encode("utf-8"))
    px = QPixmap(QSize(22, 22))
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    renderer.render(p)
    p.end()
    icon = QIcon()
    icon.addPixmap(px)
    return icon


class IconRail(QWidget):
    """48px vertical strip on the far left. Controls AffilabsSidebar tab selection."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(_WIDTH)
        self.setObjectName("IconRail")
        self.setStyleSheet(
            f"QWidget#IconRail {{ background: {_BG}; border-right: 1px solid #D5D5D7; }}"
        )

        self._sidebar = None
        self._main_ui = None  # Reference to AffilabsCoreUI (set in set_sidebar)
        self._tab_buttons: list[tuple[str, int, QPushButton]] = []  # (name, tab_idx, btn)
        self._selected_name: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ── "A" monogram — fills the transport-bar zone (top-left branding) ──
        logo = QLabel("A")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedHeight(56)  # matches TransportBar._HEIGHT
        logo.setStyleSheet(
            "font-size: 16px; font-weight: 800; color: #2E30E3; background: transparent;"
            "font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
        )
        logo.setToolTip("Affinité Instruments")
        layout.addWidget(logo)

        sep_top = QFrame()
        sep_top.setFrameShape(QFrame.Shape.HLine)
        sep_top.setFixedHeight(1)
        sep_top.setStyleSheet("background: #D5D5D7; margin: 0 8px;")
        layout.addWidget(sep_top)
        layout.addSpacing(4)

        # ── Top tabs ──────────────────────────────────────────────────────────
        # Method removed from rail (moved to transport bar) — Flow is now index 0
        for name, tab_idx in [("Flow", 0), ("Export", 1)]:
            btn = self._tab_btn(name, tab_idx)
            self._tab_buttons.append((name, tab_idx, btn))
            if name == "Flow":
                btn.setVisible(False)
                self._flow_btn = btn
            layout.addWidget(btn)

        # ── User button (popup, not a sidebar tab) ────────────────────────────
        self._user_btn = QPushButton()
        self._user_btn.setFixedSize(_WIDTH - 4, 40)
        self._user_btn.setCheckable(True)
        self._user_btn.setToolTip("Users")
        self._user_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._user_btn.setIcon(_make_icon(_ICONS["User"], _COLOR_INACTIVE))
        self._user_btn.setIconSize(QSize(22, 22))
        self._user_btn.setStyleSheet(self._btn_style(active=False))
        self._user_btn.clicked.connect(self._on_user_click)
        layout.addWidget(self._user_btn)

        # Settings tab
        _settings_btn = self._tab_btn("Settings", 2)
        self._tab_buttons.append(("Settings", 2, _settings_btn))
        layout.addWidget(_settings_btn)

        self._user_popup = None
        self._user_sidebar = None  # Set by AffilabsCoreUI after both widgets exist

        layout.addStretch(1)

        # ── Spectroscopy button (above timer) ────────────────────────────────
        self._spectrum_btn = QPushButton()
        self._spectrum_btn.setFixedSize(_WIDTH - 4, 40)
        self._spectrum_btn.setCheckable(True)
        self._spectrum_btn.setToolTip("Show / hide spectroscopy panel")
        self._spectrum_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._spectrum_btn.setIcon(_make_icon(_ICONS["Spectrum"], _COLOR_SPECTRUM_OFF))
        self._spectrum_btn.setIconSize(QSize(22, 22))
        self._spectrum_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(90,200,250,0.10); border: 1px solid rgba(90,200,250,0.30); border-radius: 8px; margin: 0 2px; }}"
            "QPushButton:hover { background: rgba(90,200,250,0.18); border-color: rgba(90,200,250,0.45); }"
            "QPushButton:checked { background: rgba(10,132,255,0.15); border-color: rgba(10,132,255,0.45); }"
        )
        self._spectrum_btn.toggled.connect(self._on_spectrum_toggle)
        layout.addWidget(self._spectrum_btn)

        # ── Timer button (above divider) ─────────────────────────────────────────────
        self._timer_btn = QPushButton()
        self._timer_btn.setFixedSize(_WIDTH - 4, 40)
        self._timer_btn.setCheckable(True)
        self._timer_btn.setToolTip("Countdown Timer")
        self._timer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._timer_btn.setIcon(_make_icon(_ICONS["Timer"], _COLOR_INACTIVE))
        self._timer_btn.setIconSize(QSize(22, 22))
        self._timer_btn.setStyleSheet(self._btn_style(active=False))
        self._timer_btn.clicked.connect(self._on_timer_click)
        layout.addWidget(self._timer_btn)

        # Timer popup (created lazily on first click)
        self._timer_popup = None
        # Select Export by default (Flow starts hidden, Method moved to transport bar)
        self._select("Export")

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def set_sidebar(self, sidebar) -> None:
        """Wire icon rail to sidebar. Call after both widgets are created."""
        self._sidebar = sidebar
        self._main_ui = self.parent()  # Reference to AffilabsCoreUI for splitter control
        # Hide the sidebar's own tab bar — rail takes over
        try:
            sidebar.tab_widget.tabBar().setVisible(False)
        except Exception as e:
            logger.warning(f"IconRail: could not hide sidebar tab bar: {e}")
        
        # Wire spectrum button to main window
        if hasattr(self._main_ui, '_on_spectrum_toggle'):
            self._main_ui.spectrum_toggle_btn = self._spectrum_btn

    def show_flow_tab(self, visible: bool) -> None:
        """Show or hide the Flow tab icon (call when hardware model is known)."""
        self._flow_btn.setVisible(visible)

    # ──────────────────────────────────────────────────────────────────────────────
    # Timer
    # ──────────────────────────────────────────────────────────────────────────────

    def _on_user_click(self) -> None:
        """Toggle the user sidebar panel (inline, right of icon rail)."""
        # Prefer the inline sidebar panel created by AffilabsCoreUI
        panel = getattr(self, '_user_sidebar', None)
        if panel is not None:
            # Wire user manager if not yet done
            if self._main_ui is not None:
                sidebar = self._sidebar
                if sidebar is not None and hasattr(sidebar, 'user_profile_manager'):
                    panel.set_user_manager(sidebar.user_profile_manager)

            visible = panel.toggle()
            if visible:
                self._user_btn.setChecked(True)
                self._user_btn.setIcon(_make_icon(_ICONS["User"], _COLOR_ACTIVE))
                self._user_btn.setStyleSheet(self._btn_style(active=True))
            else:
                self._user_btn.setChecked(False)
                self._user_btn.setIcon(_make_icon(_ICONS["User"], _COLOR_INACTIVE))
                self._user_btn.setStyleSheet(self._btn_style(active=False))
            return

        # Fallback: legacy floating popup (should not be reached in normal flow)
        if self._user_popup is None:
            try:
                from affilabs.widgets.user_panel_popup import UserPanelPopup
                self._user_popup = UserPanelPopup(parent=None)
                self._user_popup.destroyed.connect(self._on_user_popup_destroyed)
            except Exception as e:
                logger.error(f"IconRail: could not create UserPanelPopup: {e}")
                self._user_btn.setChecked(False)
                return

        # Wire user manager if available
        if self._main_ui is not None:
            sidebar = self._sidebar
            if sidebar is not None and hasattr(sidebar, 'user_profile_manager'):
                self._user_popup.set_user_manager(sidebar.user_profile_manager)

        if self._user_popup.isVisible():
            self._user_popup.hide()
            self._user_btn.setChecked(False)
            self._user_btn.setIcon(_make_icon(_ICONS["User"], _COLOR_INACTIVE))
            self._user_btn.setStyleSheet(self._btn_style(active=False))
        else:
            btn_global = self._user_btn.mapToGlobal(self._user_btn.rect().center())
            popup_x = self.mapToGlobal(self.rect().topRight()).x() + 4
            popup_y = btn_global.y() - self._user_popup.height() // 2
            self._user_popup.move(popup_x, popup_y)
            self._user_popup.show_and_refresh()
            self._user_btn.setChecked(True)
            self._user_btn.setIcon(_make_icon(_ICONS["User"], _COLOR_ACTIVE))
            self._user_btn.setStyleSheet(self._btn_style(active=True))

    def _on_user_popup_destroyed(self) -> None:
        self._user_popup = None
        self._user_btn.setChecked(False)
        self._user_btn.setIcon(_make_icon(_ICONS["User"], _COLOR_INACTIVE))
        self._user_btn.setStyleSheet(self._btn_style(active=False))

    def _on_timer_click(self) -> None:
        """Toggle the floating countdown timer popup."""
        if self._timer_popup is None:
            try:
                from affilabs.widgets.rail_timer_popup import RailTimerPopup
                self._timer_popup = RailTimerPopup(parent=None)  # top-level window
                self._timer_popup.timer_finished.connect(self._on_timer_finished)
                self._timer_popup.destroyed.connect(self._on_popup_destroyed)
            except Exception as e:
                logger.error(f"IconRail: could not create RailTimerPopup: {e}")
                self._timer_btn.setChecked(False)
                return

        # Position popup aligned to this button's global rect
        btn_global = self._timer_btn.mapToGlobal(self._timer_btn.rect().center())
        popup_x = self.mapToGlobal(self.rect().topRight()).x() + 4
        popup_y = btn_global.y() - self._timer_popup.height() // 2
        self._timer_popup.move(QPoint(popup_x, popup_y))

        if self._timer_popup.isVisible():
            self._timer_popup.hide()
            self._timer_btn.setChecked(False)
            self._timer_btn.setIcon(_make_icon(_ICONS["Timer"], _COLOR_INACTIVE))
        else:
            self._timer_popup.show()
            self._timer_popup.raise_()
            self._timer_btn.setChecked(True)
            self._timer_btn.setIcon(_make_icon(_ICONS["Timer"], _COLOR_ACTIVE))

    def _on_timer_finished(self) -> None:
        """Alert state: tint the timer icon orange."""
        self._timer_btn.setIcon(_make_icon(_ICONS["Timer"], "#FF9500"))

    def _on_popup_destroyed(self) -> None:
        self._timer_popup = None
        self._timer_btn.setChecked(False)
        self._timer_btn.setIcon(_make_icon(_ICONS["Timer"], _COLOR_INACTIVE))

    def _on_spectrum_toggle(self, checked: bool) -> None:
        """Handle spectroscopy toggle — delegates to main window."""
        if self._main_ui and hasattr(self._main_ui, '_on_spectrum_toggle'):
            self._main_ui._on_spectrum_toggle(checked)
        # Update icon color
        color = _COLOR_SPECTRUM_ON if checked else _COLOR_SPECTRUM_OFF
        self._spectrum_btn.setIcon(_make_icon(_ICONS["Spectrum"], color))

    # ──────────────────────────────────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────────────────────────────────

    def _tab_btn(self, name: str, tab_idx: int) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(_WIDTH - 4, 40)
        btn.setCheckable(True)
        btn.setChecked(False)
        btn.setToolTip(name)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if name in _ICONS:
            btn.setIcon(_make_icon(_ICONS[name], _COLOR_INACTIVE))
            btn.setIconSize(QSize(22, 22))
        btn.setStyleSheet(self._btn_style(active=False))
        btn.clicked.connect(lambda _: self._on_tab_click(name, tab_idx))
        return btn

    def _on_tab_click(self, name: str, tab_idx: int) -> None:
        if self._sidebar is None or self._main_ui is None:
            return

        # Check if sidebar is currently collapsed
        try:
            is_collapsed = self._main_ui.is_sidebar_collapsed()
        except Exception:
            is_collapsed = True

        # If collapsed, expand and select the clicked tab
        if is_collapsed:
            self._select(name)
            try:
                self._sidebar.tab_widget.setCurrentIndex(tab_idx)
            except Exception as e:
                logger.warning(f"IconRail: tab switch failed: {e}")
            self._main_ui.expand_sidebar()
            return

        # If expanded and same tab clicked, collapse sidebar
        if name == self._selected_name:
            self._main_ui.collapse_sidebar()
            self._select(None)
            return

        # If expanded and different tab clicked, just switch tabs (stay expanded)
        self._select(name)
        try:
            self._sidebar.tab_widget.setCurrentIndex(tab_idx)
        except Exception as e:
            logger.warning(f"IconRail: tab switch failed: {e}")

    def _select(self, name: str | None) -> None:
        self._selected_name = name
        for tab_name, _idx, btn in self._tab_buttons:
            active = (tab_name == name)
            btn.setChecked(active)
            btn.setStyleSheet(self._btn_style(active))
            if tab_name in _ICONS:
                btn.setIcon(_make_icon(
                    _ICONS[tab_name],
                    _COLOR_ACTIVE if active else _COLOR_INACTIVE,
                ))

    @staticmethod
    def _btn_style(active: bool) -> str:
        bg = _ACTIVE_BG if active else "transparent"
        return (
            f"QPushButton {{ background: {bg}; border: none; border-radius: 8px; margin: 0 2px; }}"
            "QPushButton:hover { background: rgba(46,48,227,0.07); }"
        )
