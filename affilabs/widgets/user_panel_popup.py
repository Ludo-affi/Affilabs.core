"""UserSidebarPanel — inline user management sidebar opened from the icon rail.

Appears as a fixed-width (280 px) panel injected into the main horizontal
layout immediately to the right of the icon rail — identical pattern to the
export_sidebar in EditsTab.  Visibility is toggled by the icon rail user button.

Legacy alias ``UserPanelPopup`` is preserved so existing imports keep working.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

_USER_SVG = (
    '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="12" cy="8" r="4" stroke="#007AFF" stroke-width="1.5"/>'
    '<path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" stroke="#007AFF" stroke-width="1.5" stroke-linecap="round"/>'
    '</svg>'
)


def _make_svg_label(svg: str, size: int = 16) -> QLabel:
    renderer = QSvgRenderer(svg.encode("utf-8"))
    px = QPixmap(QSize(size, size))
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    renderer.render(p)
    p.end()
    lbl = QLabel()
    lbl.setPixmap(px)
    lbl.setFixedSize(size, size)
    lbl.setStyleSheet("background: transparent;")
    return lbl

logger = logging.getLogger(__name__)

_FONT = "-apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif"


class UserSidebarPanel(QFrame):
    """Fixed-width sidebar panel for user management.

    Instantiated once by ``AffilabsCoreUI`` and inserted into the main
    horizontal layout right after the icon rail.  The icon rail's user button
    calls ``toggle()`` to show/hide it.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(380)
        self.setObjectName("UserSidebarPanel")
        self.setStyleSheet("""
            QFrame#UserSidebarPanel {
                background: #FFFFFF;
                border-right: 1px solid #E5E5EA;
            }
        """)

        self._user_manager = None

        # ── Scroll wrapper (same pattern as ExportSidebar) ────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: transparent; width: 6px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(0,0,0,0.15); border-radius: 3px; min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        content = QWidget()
        content.setStyleSheet("background: #FFFFFF;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        # ── Header ────────────────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        header_title = QLabel("Lab Users")
        header_title.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: #1D1D1F;"
            f" font-family: {_FONT}; background: transparent;"
        )
        header_row.addWidget(header_title)
        header_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setStyleSheet(
            "QPushButton { background: #F2F2F7; color: #86868B; border: none;"
            "  font-size: 13px; font-weight: bold; border-radius: 13px; }"
            "QPushButton:hover { background: #E5E5EA; color: #1D1D1F; }"
        )
        close_btn.clicked.connect(self.hide)
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        layout.addSpacing(4)

        # ── Current user banner ───────────────────────────────────────────────
        self._banner = QFrame()
        self._banner.setObjectName("userBanner")
        self._banner.setStyleSheet(
            "QFrame#userBanner { background: rgba(0,122,255,0.07); border-radius: 10px; border: 1px solid rgba(0,122,255,0.15); }"
        )
        banner_lay = QVBoxLayout(self._banner)
        banner_lay.setContentsMargins(12, 10, 12, 10)
        banner_lay.setSpacing(3)

        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(6)
        self._banner_icon = _make_svg_label(_USER_SVG, 14)
        name_row.addWidget(self._banner_icon)
        self._banner_name = QLabel("")
        self._banner_name.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: #007AFF;"
            f" background: transparent; font-family: {_FONT};"
        )
        name_row.addWidget(self._banner_name)
        name_row.addStretch()
        banner_lay.addLayout(name_row)

        self._banner_xp = QLabel("")
        self._banner_xp.setStyleSheet(
            f"font-size: 11px; color: #6E6E73; background: transparent; font-family: {_FONT};"
        )
        banner_lay.addWidget(self._banner_xp)
        layout.addWidget(self._banner)

        layout.addSpacing(12)

        # ── User list label ───────────────────────────────────────────────────
        users_lbl = QLabel("Members")
        users_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: #8E8E93; letter-spacing: 0.5px;"
            f" background: transparent; font-family: {_FONT}; text-transform: uppercase;"
        )
        layout.addWidget(users_lbl)

        layout.addSpacing(4)

        # ── User list ─────────────────────────────────────────────────────────
        self.user_list = QListWidget()
        self.user_list.setMinimumHeight(80)
        self.user_list.setMaximumHeight(200)
        self.user_list.setObjectName("membersList")
        self.user_list.setStyleSheet(
            f"QListWidget#membersList {{ background: #F5F5F7; border: 1px solid rgba(0,0,0,0.07);"
            f"  border-radius: 10px; padding: 4px;"
            f"  font-size: 13px; font-family: {_FONT}; outline: none; }}"
            "QListWidget#membersList::item { padding: 7px 10px; border-radius: 7px; border: none; }"
            "QListWidget#membersList::item:selected { background: rgba(0,122,255,0.10); }"
            "QListWidget#membersList::item:hover:!selected { background: rgba(0,0,0,0.04); }"
        )
        self.user_list.itemDoubleClicked.connect(self._on_set_active)
        layout.addWidget(self.user_list)

        hint = QLabel("Double-click to set active")
        hint.setStyleSheet(
            f"font-size: 10px; color: #AEAEB2; font-family: {_FONT}; background: transparent;"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(hint)

        layout.addSpacing(12)

        # ── Add user (primary action) ─────────────────────────────────────────
        self._add_btn = QPushButton("+ Add User")
        self._add_btn.setFixedHeight(36)
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.setStyleSheet(
            f"QPushButton {{ background: #34C759; color: white; border: none;"
            f"  border-radius: 9px; font-size: 13px; font-weight: 600;"
            f"  font-family: {_FONT}; }}"
            "QPushButton:hover { background: #2DB34A; }"
            "QPushButton:pressed { background: #28A044; }"
        )
        self._add_btn.clicked.connect(self._on_add)
        layout.addWidget(self._add_btn)

        layout.addSpacing(6)

        # ── Rename + Set Active (side by side) ───────────────────────────────
        row2 = QHBoxLayout()
        row2.setSpacing(6)

        self._rename_btn = QPushButton("Rename")
        self._rename_btn.setFixedHeight(34)
        self._rename_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rename_btn.setStyleSheet(
            f"QPushButton {{ background: #F2F2F7; color: #007AFF; border: none;"
            f"  border-radius: 9px; font-size: 13px; font-weight: 500;"
            f"  font-family: {_FONT}; }}"
            "QPushButton:hover { background: rgba(0,122,255,0.10); }"
            "QPushButton:pressed { background: rgba(0,122,255,0.18); }"
        )
        self._rename_btn.clicked.connect(self._on_rename)
        row2.addWidget(self._rename_btn)

        self._active_btn = QPushButton("Set Active")
        self._active_btn.setFixedHeight(34)
        self._active_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._active_btn.setStyleSheet(
            f"QPushButton {{ background: #FFF8EE; color: #FF9500; border: none;"
            f"  border-radius: 9px; font-size: 13px; font-weight: 500;"
            f"  font-family: {_FONT}; }}"
            "QPushButton:hover { background: rgba(255,149,0,0.14); }"
            "QPushButton:pressed { background: rgba(255,149,0,0.24); }"
        )
        self._active_btn.clicked.connect(self._on_set_active)
        row2.addWidget(self._active_btn)

        layout.addLayout(row2)

        layout.addSpacing(4)

        # ── Delete (danger zone) ──────────────────────────────────────────────
        self._del_btn = QPushButton("Delete")
        self._del_btn.setFixedHeight(34)
        self._del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._del_btn.setStyleSheet(
            f"QPushButton {{ background: #FFF2F2; color: #FF3B30; border: none;"
            f"  border-radius: 9px; font-size: 13px; font-weight: 500;"
            f"  font-family: {_FONT}; }}"
            "QPushButton:hover { background: rgba(255,59,48,0.12); }"
            "QPushButton:pressed { background: rgba(255,59,48,0.20); }"
        )
        self._del_btn.clicked.connect(self._on_delete)
        layout.addWidget(self._del_btn)

        layout.addSpacing(16)

        # ── Levels guide ──────────────────────────────────────────────────────
        levels_lbl = QLabel("Experience Levels")
        levels_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: #8E8E93; letter-spacing: 0.5px;"
            f" background: transparent; font-family: {_FONT};"
        )
        layout.addWidget(levels_lbl)

        layout.addSpacing(4)

        levels_card = QFrame()
        levels_card.setObjectName("levelsCard")
        levels_card.setStyleSheet(
            "QFrame#levelsCard { background: #F5F5F7; border-radius: 10px; border: 1px solid rgba(0,0,0,0.06); }"
        )
        levels_lay = QVBoxLayout(levels_card)
        levels_lay.setContentsMargins(12, 10, 12, 10)
        levels_lay.setSpacing(6)

        _LEVEL_ROWS = [
            ("🌱", "Novice",     "0 exp",   "#6E6E73", "First steps in SPR"),
            ("🔬", "Operator",   "5 exp",   "#007AFF", "Getting the workflow"),
            ("⚗️", "Specialist", "20 exp",  "#BF5AF2", "SPR is your thing"),
            ("🏆", "Expert",     "50 exp",  "#FF9500", "Advanced practitioner"),
            ("👑", "Master",     "100 exp", "#FF3B30", "SPR legend"),
        ]
        for emoji, title, threshold, color, tagline in _LEVEL_ROWS:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)

            badge = QLabel(emoji)
            badge.setFixedWidth(20)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet("background: transparent; font-size: 13px;")
            row.addWidget(badge)

            name_lbl = QLabel(title)
            name_lbl.setStyleSheet(
                f"font-size: 12px; font-weight: 700; color: {color};"
                f" background: transparent; font-family: {_FONT};"
            )
            row.addWidget(name_lbl)

            thresh_lbl = QLabel(threshold)
            thresh_lbl.setStyleSheet(
                f"font-size: 11px; color: #AEAEB2; background: transparent; font-family: {_FONT};"
            )
            row.addWidget(thresh_lbl)

            row.addStretch()

            tag_lbl = QLabel(tagline)
            tag_lbl.setStyleSheet(
                f"font-size: 11px; color: #8E8E93; background: transparent;"
                f" font-style: italic; font-family: {_FONT};"
            )
            row.addWidget(tag_lbl)

            levels_lay.addLayout(row)

        layout.addWidget(levels_card)

        layout.addStretch()

        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _action_btn(self, label: str, color: str) -> QPushButton:
        """Styled action button matching export sidebar style."""
        btn = QPushButton(f"  {label}")
        btn.setFixedHeight(36)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: white; color: {color};"
            f"  border: 1px solid {color}55;"
            f"  border-radius: 8px; font-size: 13px; font-weight: 600;"
            f"  padding: 8px 16px; text-align: left; font-family: {_FONT};"
            f"}}"
            f"QPushButton:hover {{ background: {color}14; border-color: {color}; }}"
            f"QPushButton:pressed {{ background: {color}22; }}"
        )
        return btn

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def set_user_manager(self, manager) -> None:
        self._user_manager = manager
        self._refresh()

    def toggle(self) -> bool:
        """Toggle visibility. Returns True if now visible."""
        if self.isVisible():
            self.hide()
            return False
        self._refresh()
        self.show()
        return True

    # Legacy call-site compatibility
    def show_and_refresh(self) -> None:
        self._refresh()
        self.show()

    # ──────────────────────────────────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        if not self._user_manager:
            return
        current = self._user_manager.get_current_user()

        # Banner
        if current:
            self._banner.setVisible(True)
            try:
                title, _ = self._user_manager.get_title(current)
                title_str = title.value if hasattr(title, "value") else str(title)
                exp_count = self._user_manager.get_experiment_count(current)
                self._banner_name.setText(f"{current}  •  {title_str}")
                self._banner_xp.setText(f"{exp_count} experiment(s) logged")
            except Exception:
                self._banner_name.setText(current)
                self._banner_xp.setText("")
        else:
            self._banner.setVisible(False)

        # User list
        self.user_list.clear()
        for username in self._user_manager.get_profiles():
            try:
                title, _ = self._user_manager.get_title(username)
                title_str = title.value if hasattr(title, "value") else str(title)
                exp_count = self._user_manager.get_experiment_count(username)
                is_active = username == current
                marker = "★ " if is_active else "   "
                display = f"{marker}{username}  —  {title_str} ({exp_count} exp)"
            except Exception:
                is_active = username == current
                marker = "★ " if is_active else "   "
                display = f"{marker}{username}"

            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, username)
            if is_active:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(Qt.GlobalColor.blue)
            self.user_list.addItem(item)

    def _selected_username(self) -> str | None:
        items = self.user_list.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.ItemDataRole.UserRole)

    def _require_manager(self) -> bool:
        if self._user_manager:
            return True
        QMessageBox.warning(self, "Not Ready", "User manager not available yet.")
        return False

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_add(self) -> None:
        if not self._require_manager():
            return
        name, ok = QInputDialog.getText(self, "Add User", "New user name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        if self._user_manager.add_user(name):
            self._refresh()
        else:
            QMessageBox.warning(self, "User Exists", f"'{name}' already exists.")

    def _on_rename(self) -> None:
        if not self._require_manager():
            return
        old = self._selected_username()
        if not old:
            QMessageBox.information(self, "No Selection", "Select a user to rename.")
            return
        new, ok = QInputDialog.getText(self, "Rename User", f"New name for '{old}':", text=old)
        if not ok or not new.strip():
            return
        new = new.strip()
        try:
            if self._user_manager.rename_user(old, new):
                self._refresh()
            else:
                QMessageBox.warning(self, "Failed", f"Could not rename '{old}'.")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _on_set_active(self) -> None:
        if not self._require_manager():
            return
        name = self._selected_username()
        if not name:
            QMessageBox.information(self, "No Selection", "Select a user to activate.")
            return
        try:
            self._user_manager.set_current_user(name)
            self._refresh()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _on_delete(self) -> None:
        if not self._require_manager():
            return
        name = self._selected_username()
        if not name:
            QMessageBox.information(self, "No Selection", "Select a user to delete.")
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete '{name}' and all their data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self._user_manager.remove_user(name):
                self._refresh()
            else:
                QMessageBox.warning(self, "Cannot Delete", "Must keep at least one user.")


# ── Backward-compat alias so existing ``from affilabs.widgets.user_panel_popup import UserPanelPopup`` keeps working
UserPanelPopup = UserSidebarPanel
