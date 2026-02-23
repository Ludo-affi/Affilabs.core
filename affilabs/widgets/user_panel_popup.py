"""UserSidebarPanel — inline user management sidebar opened from the icon rail.

Appears as a fixed-width (280 px) panel injected into the main horizontal
layout immediately to the right of the icon rail — identical pattern to the
export_sidebar in EditsTab.  Visibility is toggled by the icon rail user button.

Legacy alias ``UserPanelPopup`` is preserved so existing imports keep working.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
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
        self.setFixedWidth(280)
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
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # ── Header ────────────────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        header_icon = QLabel("👥")
        header_icon.setStyleSheet("font-size: 18px; background: transparent;")
        header_row.addWidget(header_icon)

        header_title = QLabel("USERS")
        header_title.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: #1D1D1F;"
            f" letter-spacing: 1px; font-family: {_FONT}; background: transparent;"
        )
        header_row.addWidget(header_title)
        header_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #86868B; border: none;"
            "  font-size: 14px; font-weight: bold; border-radius: 12px; }"
            "QPushButton:hover { background: #F5F5F7; color: #1D1D1F; }"
        )
        close_btn.clicked.connect(self.hide)
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        # Divider
        div0 = QFrame()
        div0.setFrameShape(QFrame.Shape.HLine)
        div0.setStyleSheet("border: none; background: #E5E5EA; max-height: 1px;")
        layout.addWidget(div0)

        # ── Current user banner ───────────────────────────────────────────────
        self._banner = QFrame()
        self._banner.setStyleSheet(
            "QFrame { background: rgba(0,122,255,0.06); border-radius: 8px; }"
        )
        banner_lay = QVBoxLayout(self._banner)
        banner_lay.setContentsMargins(10, 8, 10, 8)
        banner_lay.setSpacing(2)

        self._banner_name = QLabel("")
        self._banner_name.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: #007AFF;"
            f" background: transparent; font-family: {_FONT};"
        )
        banner_lay.addWidget(self._banner_name)

        self._banner_xp = QLabel("")
        self._banner_xp.setStyleSheet(
            f"font-size: 11px; color: #86868B; background: transparent; font-family: {_FONT};"
        )
        banner_lay.addWidget(self._banner_xp)
        layout.addWidget(self._banner)

        # ── User list label ───────────────────────────────────────────────────
        users_lbl = QLabel("Lab Users")
        users_lbl.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: #86868B;"
            f" background: transparent; font-family: {_FONT}; margin-top: 4px;"
        )
        layout.addWidget(users_lbl)

        # ── User list ─────────────────────────────────────────────────────────
        self.user_list = QListWidget()
        self.user_list.setMinimumHeight(100)
        self.user_list.setMaximumHeight(220)
        self.user_list.setStyleSheet(
            f"QListWidget {{ background: #F5F5F7; border: 1px solid rgba(0,0,0,0.08);"
            f"  border-radius: 8px; padding: 4px;"
            f"  font-size: 13px; font-family: {_FONT}; }}"
            "QListWidget::item { padding: 6px 8px; border-radius: 6px; }"
            "QListWidget::item:selected { background: rgba(0,122,255,0.12); }"
            "QListWidget::item:hover { background: rgba(0,0,0,0.04); }"
        )
        self.user_list.itemDoubleClicked.connect(self._on_set_active)
        layout.addWidget(self.user_list)

        hint = QLabel("Double-click to set active")
        hint.setStyleSheet(
            f"font-size: 10px; color: #AEAEB2; font-family: {_FONT}; background: transparent;"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(hint)

        # Divider
        div1 = QFrame()
        div1.setFrameShape(QFrame.Shape.HLine)
        div1.setStyleSheet("border: none; background: #E5E5EA; max-height: 1px;")
        layout.addWidget(div1)

        # ── Action buttons ────────────────────────────────────────────────────
        self._add_btn    = self._action_btn("+ Add User",   "#34C759")
        self._rename_btn = self._action_btn("Rename",       "#007AFF")
        self._active_btn = self._action_btn("Set Active",   "#FF9500")
        self._del_btn    = self._action_btn("Delete",       "#FF3B30")

        self._add_btn.clicked.connect(self._on_add)
        self._rename_btn.clicked.connect(self._on_rename)
        self._active_btn.clicked.connect(self._on_set_active)
        self._del_btn.clicked.connect(self._on_delete)

        for btn in (self._add_btn, self._rename_btn, self._active_btn, self._del_btn):
            layout.addWidget(btn)

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
                self._banner_name.setText(f"👤 {current}  •  {title_str}")
                self._banner_xp.setText(f"{exp_count} experiment(s) logged")
            except Exception:
                self._banner_name.setText(f"👤 {current}")
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
