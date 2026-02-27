"""Hotkey Cheat Sheet — lightweight popup showing all keyboard shortcuts.

Opened from the ⌨ label in the status bar (bottom-right corner).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


_HOTKEYS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Navigation", [
        ("Ctrl+1", "Sensorgram tab"),
        ("Ctrl+2", "Edits tab"),
        ("Ctrl+3", "Notes tab"),
    ]),
    ("Device", [
        ("Ctrl+P", "Power on / off device"),
        ("Ctrl+Q", "Toggle Run Queue panel"),
    ]),
    ("Channels", [
        ("Alt+A", "Toggle channel A"),
        ("Alt+B", "Toggle channel B"),
        ("Alt+C", "Toggle channel C"),
        ("Alt+D", "Toggle channel D"),
        ("Ctrl+Click", "Set / clear reference channel"),
    ]),
    ("Method Builder", [
        ("Ctrl+Z", "Undo"),
        ("Ctrl+Shift+Z", "Redo"),
        ("↑ / ↓", "Sparq bar history"),
        ("Ctrl+Enter", "Add cycle from text mode"),
    ]),
    ("Advanced / OEM", [
        ("Ctrl+Shift+I", "OEM Issue Tracker"),
        ("Ctrl+Shift+M", "Signal metrics strip"),
        ("Ctrl+Shift+S", "Start simulation"),
        ("Ctrl+Shift+D", "Load demo data"),
        ("F9", "Load demo data"),
    ]),
]


class HotkeyCheatsheetDialog(QDialog):
    """Modal-ish, frameless cheat sheet — click anywhere outside to dismiss."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Popup
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build_ui()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QWidget()
        card.setObjectName("hk_card")
        card.setStyleSheet(
            "#hk_card {"
            "  background: #FFFFFF;"
            "  border: 1px solid #D5D5D7;"
            "  border-radius: 12px;"
            "}"
        )
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(20, 16, 20, 16)
        card_lay.setSpacing(12)

        # Title
        title = QLabel("⌨  Keyboard Shortcuts")
        title.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: #1D1D1F;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        card_lay.addWidget(title)

        # Sections
        for section_name, keys in _HOTKEYS:
            sec_label = QLabel(section_name)
            sec_label.setStyleSheet(
                "font-size: 11px; font-weight: 600; color: #86868B; text-transform: uppercase; "
                "letter-spacing: 0.5px; margin-top: 4px;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            card_lay.addWidget(sec_label)

            for shortcut, description in keys:
                row = QHBoxLayout()
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(12)

                key_label = QLabel(shortcut)
                key_label.setFixedWidth(130)
                key_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                key_label.setStyleSheet(
                    "font-size: 12px; font-weight: 600; color: #1D1D1F;"
                    "font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;"
                    "background: #F2F2F7; border: 1px solid #E5E5EA; border-radius: 4px;"
                    "padding: 2px 8px;"
                )

                desc_label = QLabel(description)
                desc_label.setStyleSheet(
                    "font-size: 12px; color: #3A3A3C;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )

                row.addWidget(key_label)
                row.addWidget(desc_label, 1)

                row_w = QWidget()
                row_w.setLayout(row)
                card_lay.addWidget(row_w)

        # Dismiss hint
        hint = QLabel("Click anywhere to close")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(
            "font-size: 10px; color: #AEAEB2; margin-top: 8px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        card_lay.addWidget(hint)

        outer.addWidget(card)

    # ── Show anchored above a widget ──────────────────────────────────────────

    def show_above(self, anchor: QWidget) -> None:
        """Position the popup above *anchor* (the ⌨ label) and show."""
        self.adjustSize()
        # Map anchor top-right to global, then position popup's bottom-right there
        global_pos = anchor.mapToGlobal(anchor.rect().topRight())
        x = global_pos.x() - self.width()
        y = global_pos.y() - self.height() - 6
        # Clamp to screen
        if x < 0:
            x = 4
        if y < 0:
            y = global_pos.y() + anchor.height() + 6
        self.move(x, y)
        self.show()
