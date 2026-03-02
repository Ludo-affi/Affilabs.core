"""Experiment Browser Dialog — search and load past recording sessions.

Entry point: history_btn in UIBuildersMixin._create_table_panel()
Reads:       ExperimentIndex → ~/Documents/Affilabs Data/experiment_index.json
Emits:       file_selected(Path) — caller connects to _load_data_from_path()

See docs/features/EXPERIMENT_BROWSER_FRS.md for full spec.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPalette
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from affilabs.ui_styles import Colors, Fonts


# ── Constants ─────────────────────────────────────────────────────────────────

_BLUE_HOVER = "rgba(0, 122, 255, 0.06)"
_BLUE_SELECT = "rgba(0, 122, 255, 0.12)"
_ACCENT_BLUE = "#007AFF"
_PILL_ACTIVE_BG = "#007AFF"
_PILL_ACTIVE_FG = "#FFFFFF"
_PILL_INACTIVE_BG = "#E5E5EA"
_PILL_INACTIVE_FG = "#1D1D1F"


# ── ExperimentRowWidget ────────────────────────────────────────────────────────

class ExperimentRowWidget(QFrame):
    """Single row representing one experiment. Supports hover, selected, and stale states."""

    clicked = Signal(object)   # emits self
    open_clicked = Signal(Path)  # emits abs_path for QDesktopServices

    def __init__(self, entry: dict[str, Any], abs_path: Path, stale: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry = entry
        self._abs_path = abs_path
        self._stale = stale
        self._selected = False
        self._hovered = False

        self.setFixedHeight(56)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        # File icon
        icon_lbl = QLabel("📄")
        icon_lbl.setFixedWidth(20)
        icon_lbl.setStyleSheet(f"font-size: 16px; color: {Colors.SECONDARY_TEXT};")
        layout.addWidget(icon_lbl)

        # Left block: filename + metadata
        text_block = QVBoxLayout()
        text_block.setSpacing(2)
        text_block.setContentsMargins(0, 0, 0, 0)

        filename = Path(self._entry.get("file", "")).name or "unknown.xlsx"
        if len(filename) > 42:
            filename = filename[:39] + "…"

        name_color = Colors.SECONDARY_TEXT if self._stale else Colors.PRIMARY_TEXT
        name_lbl = QLabel(filename)
        name_font = f"font-size: 13px; font-weight: 600; color: {name_color}; font-family: {Fonts.SYSTEM};"
        if self._stale:
            name_font += " text-decoration: line-through;"
        name_lbl.setStyleSheet(name_font)
        text_block.addWidget(name_lbl)

        meta_parts = [
            self._entry.get("user") or "—",
            self._entry.get("chip_serial") or "—",
            self._format_duration(self._entry.get("duration_min")),
            self._format_cycles(self._entry.get("cycle_count")),
        ]
        meta_lbl = QLabel("  ·  ".join(meta_parts))
        meta_lbl.setStyleSheet(
            f"font-size: 11px; color: {Colors.SECONDARY_TEXT}; font-family: {Fonts.SYSTEM};"
        )
        text_block.addWidget(meta_lbl)
        layout.addLayout(text_block)

        layout.addStretch()

        # "Open ↗" button
        open_btn = QPushButton("Open ↗")
        open_btn.setFixedSize(60, 24)
        open_btn.setStyleSheet(
            f"QPushButton {{ background: {Colors.BACKGROUND_LIGHT}; color: {_ACCENT_BLUE}; "
            f"border: none; border-radius: 6px; font-size: 11px; font-weight: 500; "
            f"font-family: {Fonts.SYSTEM}; }}"
            f"QPushButton:hover {{ background: rgba(0,122,255,0.10); }}"
            f"QPushButton:disabled {{ color: {Colors.SECONDARY_TEXT}; }}"
        )
        if self._stale:
            open_btn.setEnabled(False)
            open_btn.setToolTip(f"File not found: {self._abs_path}")
        else:
            open_btn.clicked.connect(self._on_open_clicked)
        layout.addWidget(open_btn)

    def _format_duration(self, minutes: Any) -> str:
        try:
            return f"{int(minutes)} min"
        except (TypeError, ValueError):
            return "—"

    def _format_cycles(self, n: Any) -> str:
        try:
            n = int(n)
            return f"{n} cycle{'s' if n != 1 else ''}"
        except (TypeError, ValueError):
            return "— cycles"

    def _on_open_clicked(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._abs_path)))

    # ── Selection / hover state ────────────────────────────────────────────────

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._apply_style()

    @property
    def is_selected(self) -> bool:
        return self._selected

    @property
    def entry(self) -> dict[str, Any]:
        return self._entry

    @property
    def abs_path(self) -> Path:
        return self._abs_path

    @property
    def is_stale(self) -> bool:
        return self._stale

    def _apply_style(self) -> None:
        if self._selected:
            bg = _BLUE_SELECT
            border_left = f"border-left: 3px solid {_ACCENT_BLUE};"
        elif self._hovered:
            bg = _BLUE_HOVER
            border_left = "border-left: 3px solid transparent;"
        else:
            bg = Colors.BACKGROUND_WHITE
            border_left = "border-left: 3px solid transparent;"

        self.setStyleSheet(
            f"ExperimentRowWidget {{ background: {bg}; {border_left} "
            f"border-bottom: 1px solid {Colors.OVERLAY_LIGHT_10}; }}"
        )

    def enterEvent(self, event) -> None:
        self._hovered = True
        if not self._selected:
            self._apply_style()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        if not self._selected:
            self._apply_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and not self._stale:
            self.clicked.emit(self)
            # Parent dialog handles double-click → load
            parent = self.parent()
            while parent and not isinstance(parent, ExperimentBrowserDialog):
                parent = parent.parent()
            if parent:
                parent._on_load_selected()
        super().mouseDoubleClickEvent(event)


# ── Section header ─────────────────────────────────────────────────────────────

def _make_section_header(title: str) -> QLabel:
    lbl = QLabel(title.upper())
    lbl.setFixedHeight(28)
    lbl.setStyleSheet(
        f"QLabel {{ font-size: 11px; color: {Colors.SECONDARY_TEXT}; font-weight: 500; "
        f"font-family: {Fonts.SYSTEM}; background: {Colors.BACKGROUND_LIGHT}; "
        f"padding-left: 15px; padding-top: 8px; }}"
    )
    return lbl


# ── Main dialog ────────────────────────────────────────────────────────────────

class ExperimentBrowserDialog(QDialog):
    """Searchable, time-grouped list of past recording sessions."""

    file_selected = Signal(Path)

    def __init__(self, parent: QWidget | None = None, user_manager=None) -> None:
        super().__init__(parent)
        self._user_manager = user_manager
        self._all_rows: list[ExperimentRowWidget] = []
        self._selected_row: ExperimentRowWidget | None = None
        self._active_pill: str = "All"   # "All" | "Mine" | "7d" | "30d"
        self._pill_btns: dict[str, QPushButton] = {}

        self.setWindowTitle("Experiment History")
        self.setMinimumSize(680, 540)
        self.resize(700, 560)
        self.setStyleSheet(f"QDialog {{ background: {Colors.BACKGROUND_LIGHT}; }}")

        self._build_ui()
        self._load_entries()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_filter_bar())
        root.addWidget(self._build_scroll_area(), stretch=1)
        root.addWidget(self._build_footer())

    def _build_header(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {Colors.BACKGROUND_WHITE}; "
            f"border-bottom: 1px solid {Colors.OVERLAY_LIGHT_10}; }}"
        )
        frame.setFixedHeight(48)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 0, 12, 0)

        title = QLabel("Experiment History")
        title.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {Colors.PRIMARY_TEXT}; "
            f"font-family: {Fonts.SYSTEM}; background: transparent; border: none;"
        )
        layout.addWidget(title)
        layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {Colors.SECONDARY_TEXT}; "
            f"font-size: 14px; border-radius: 14px; }}"
            f"QPushButton:hover {{ background: {Colors.OVERLAY_LIGHT_10}; }}"
        )
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)
        return frame

    def _build_filter_bar(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {Colors.BACKGROUND_WHITE}; "
            f"border-bottom: 1px solid {Colors.OVERLAY_LIGHT_10}; }}"
        )
        frame.setFixedHeight(46)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search user, chip, notes…")
        self._search_box.setFixedHeight(30)
        self._search_box.setStyleSheet(
            f"QLineEdit {{ background: {Colors.BACKGROUND_LIGHT}; border: 1px solid {Colors.OVERLAY_LIGHT_20}; "
            f"border-radius: 6px; font-size: 12px; padding: 4px 10px; font-family: {Fonts.SYSTEM}; "
            f"color: {Colors.PRIMARY_TEXT}; }}"
            f"QLineEdit:focus {{ border: 1px solid {_ACCENT_BLUE}; }}"
        )
        self._search_box.textChanged.connect(self._apply_filter)
        layout.addWidget(self._search_box, stretch=1)

        pill_style_active = (
            f"QPushButton {{ background: {_PILL_ACTIVE_BG}; color: {_PILL_ACTIVE_FG}; "
            f"border: none; border-radius: 13px; font-size: 11px; font-weight: 500; "
            f"font-family: {Fonts.SYSTEM}; padding: 0 12px; }}"
        )
        pill_style_inactive = (
            f"QPushButton {{ background: {_PILL_INACTIVE_BG}; color: {_PILL_INACTIVE_FG}; "
            f"border: none; border-radius: 13px; font-size: 11px; font-weight: 400; "
            f"font-family: {Fonts.SYSTEM}; padding: 0 12px; }}"
            f"QPushButton:hover {{ background: #D1D1D6; }}"
        )

        for label in ("All", "Mine", "7d", "30d"):
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.setCheckable(False)
            style = pill_style_active if label == "All" else pill_style_inactive
            btn.setStyleSheet(style)
            btn.clicked.connect(lambda checked, lbl=label: self._on_pill_clicked(lbl))
            self._pill_btns[label] = btn
            layout.addWidget(btn)

        return frame

    def _build_scroll_area(self) -> QScrollArea:
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background: {Colors.BACKGROUND_LIGHT}; border: none; }}"
            f"QScrollBar:vertical {{ width: 6px; background: transparent; }}"
            f"QScrollBar::handle:vertical {{ background: {Colors.OVERLAY_LIGHT_20}; border-radius: 3px; }}"
        )

        self._entries_widget = QWidget()
        self._entries_widget.setStyleSheet(f"background: {Colors.BACKGROUND_LIGHT};")
        self._entries_layout = QVBoxLayout(self._entries_widget)
        self._entries_layout.setContentsMargins(0, 4, 0, 8)
        self._entries_layout.setSpacing(0)
        self._entries_layout.addStretch()

        self._scroll.setWidget(self._entries_widget)
        return self._scroll

    def _build_footer(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {Colors.BACKGROUND_WHITE}; "
            f"border-top: 1px solid {Colors.OVERLAY_LIGHT_10}; }}"
        )
        frame.setFixedHeight(48)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 0, 12, 0)

        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(
            f"font-size: 11px; color: {Colors.SECONDARY_TEXT}; font-family: {Fonts.SYSTEM}; "
            f"background: transparent; border: none;"
        )
        layout.addWidget(self._count_lbl)
        layout.addStretch()

        self._load_btn = QPushButton("Load Selected")
        self._load_btn.setFixedHeight(32)
        self._load_btn.setEnabled(False)
        self._load_btn.setStyleSheet(
            f"QPushButton {{ background: {_ACCENT_BLUE}; color: white; border: none; "
            f"border-radius: 7px; font-size: 12px; font-weight: 600; "
            f"font-family: {Fonts.SYSTEM}; padding: 0 16px; }}"
            f"QPushButton:hover {{ background: #0066CC; }}"
            f"QPushButton:disabled {{ background: {Colors.OVERLAY_LIGHT_20}; color: {Colors.SECONDARY_TEXT}; }}"
        )
        self._load_btn.clicked.connect(self._on_load_selected)
        layout.addWidget(self._load_btn)
        return frame

    # ── Data loading ───────────────────────────────────────────────────────────

    def _load_entries(self) -> None:
        from affilabs.services.experiment_index import ExperimentIndex
        index = ExperimentIndex()
        entries = index.all_entries()

        from affilabs.utils.resource_path import get_writable_data_path
        base = get_writable_data_path("data")
        rows: list[ExperimentRowWidget] = []

        for entry in entries:
            file_val = entry.get("file", "")
            if not file_val:
                continue
            file_path = Path(file_val)
            # Resolve: if relative, anchor to base; if absolute, use as-is
            abs_path = file_path if file_path.is_absolute() else base / file_path
            stale = not abs_path.exists()
            row = ExperimentRowWidget(entry, abs_path, stale)
            row.clicked.connect(self._on_row_clicked)
            rows.append(row)

        self._all_rows = rows
        self._apply_filter()

    # ── Filtering / rebuilding list ────────────────────────────────────────────

    def _apply_filter(self) -> None:
        keyword = self._search_box.text().strip().lower()
        today = date.today()

        # Determine pill date boundary
        pill = self._active_pill
        date_cutoff: date | None = None
        user_filter: str | None = None

        if pill == "Mine":
            if self._user_manager:
                user_filter = self._user_manager.get_current_user() or None
        elif pill == "7d":
            date_cutoff = today - timedelta(days=7)
        elif pill == "30d":
            date_cutoff = today - timedelta(days=30)

        visible: list[ExperimentRowWidget] = []
        for row in self._all_rows:
            e = row.entry

            # User filter
            if user_filter and (e.get("user", "") or "").lower() != user_filter.lower():
                continue

            # Date cutoff
            if date_cutoff:
                try:
                    entry_date = date.fromisoformat(e.get("date", ""))
                    if entry_date < date_cutoff:
                        continue
                except ValueError:
                    pass

            # Keyword
            if keyword:
                haystack = " ".join([
                    str(e.get("user", "")),
                    str(e.get("chip_serial", "")),
                    Path(e.get("file", "")).name,
                    str(e.get("notes", "")),
                ]).lower()
                if keyword not in haystack:
                    continue

            visible.append(row)

        self._rebuild_list(visible, today)

    def _rebuild_list(self, rows: list[ExperimentRowWidget], today: date) -> None:
        # Remove all widgets from layout (except the trailing stretch)
        while self._entries_layout.count() > 1:
            item = self._entries_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        if not rows:
            self._show_empty_state()
            self._count_lbl.setText("")
            return

        # Bucket rows by recency
        buckets: dict[str, list[ExperimentRowWidget]] = {
            "Today": [],
            "This week": [],
            "This month": [],
            "Earlier": [],
        }
        for row in rows:
            try:
                entry_date = date.fromisoformat(row.entry.get("date", ""))
            except ValueError:
                entry_date = date.min

            delta = (today - entry_date).days
            if delta == 0:
                buckets["Today"].append(row)
            elif delta <= 7:
                buckets["This week"].append(row)
            elif delta <= 30:
                buckets["This month"].append(row)
            else:
                buckets["Earlier"].append(row)

        insert_pos = 0
        for bucket_name, bucket_rows in buckets.items():
            if not bucket_rows:
                continue
            header = _make_section_header(bucket_name)
            self._entries_layout.insertWidget(insert_pos, header)
            insert_pos += 1
            for row in bucket_rows:
                self._entries_layout.insertWidget(insert_pos, row)
                row.show()
                insert_pos += 1

        total = len(rows)
        self._count_lbl.setText(f"{total} experiment{'s' if total != 1 else ''}")

        # Restore selection if previously selected entry is still visible
        if self._selected_row and self._selected_row in rows:
            self._selected_row.set_selected(True)
        else:
            self._selected_row = None
            self._update_load_btn()

    def _show_empty_state(self) -> None:
        container = QWidget()
        container.setStyleSheet(f"background: {Colors.BACKGROUND_LIGHT}; border: none;")
        vbox = QVBoxLayout(container)
        vbox.setAlignment(Qt.AlignCenter)
        vbox.setSpacing(6)

        # Determine which empty state to show
        from affilabs.services.experiment_index import ExperimentIndex
        has_any = bool(ExperimentIndex().all_entries())

        if has_any:
            icon_lbl = QLabel("🔬")
            icon_lbl.setStyleSheet("font-size: 36px; background: transparent; border: none;")
            icon_lbl.setAlignment(Qt.AlignCenter)
            vbox.addWidget(icon_lbl)

            title_lbl = QLabel("No matching experiments")
            title_lbl.setStyleSheet(
                f"font-size: 14px; font-weight: 600; color: {Colors.PRIMARY_TEXT}; "
                f"font-family: {Fonts.SYSTEM}; background: transparent; border: none;"
            )
            title_lbl.setAlignment(Qt.AlignCenter)
            vbox.addWidget(title_lbl)

            sub_lbl = QLabel("Try a different search or time range.")
            sub_lbl.setStyleSheet(
                f"font-size: 12px; color: {Colors.SECONDARY_TEXT}; "
                f"font-family: {Fonts.SYSTEM}; background: transparent; border: none;"
            )
            sub_lbl.setAlignment(Qt.AlignCenter)
            vbox.addWidget(sub_lbl)
        else:
            icon_lbl = QLabel("📋")
            icon_lbl.setStyleSheet("font-size: 36px; background: transparent; border: none;")
            icon_lbl.setAlignment(Qt.AlignCenter)
            vbox.addWidget(icon_lbl)

            title_lbl = QLabel("No experiments recorded yet")
            title_lbl.setStyleSheet(
                f"font-size: 14px; font-weight: 600; color: {Colors.PRIMARY_TEXT}; "
                f"font-family: {Fonts.SYSTEM}; background: transparent; border: none;"
            )
            title_lbl.setAlignment(Qt.AlignCenter)
            vbox.addWidget(title_lbl)

            sub_lbl = QLabel("Your experiments will appear here after your first recording.")
            sub_lbl.setStyleSheet(
                f"font-size: 12px; color: {Colors.SECONDARY_TEXT}; "
                f"font-family: {Fonts.SYSTEM}; background: transparent; border: none;"
            )
            sub_lbl.setAlignment(Qt.AlignCenter)
            vbox.addWidget(sub_lbl)

        self._entries_layout.insertWidget(0, container)

    # ── Interaction ────────────────────────────────────────────────────────────

    def _on_pill_clicked(self, label: str) -> None:
        self._active_pill = label
        pill_style_active = (
            f"QPushButton {{ background: {_PILL_ACTIVE_BG}; color: {_PILL_ACTIVE_FG}; "
            f"border: none; border-radius: 13px; font-size: 11px; font-weight: 500; "
            f"font-family: {Fonts.SYSTEM}; padding: 0 12px; }}"
        )
        pill_style_inactive = (
            f"QPushButton {{ background: {_PILL_INACTIVE_BG}; color: {_PILL_INACTIVE_FG}; "
            f"border: none; border-radius: 13px; font-size: 11px; font-weight: 400; "
            f"font-family: {Fonts.SYSTEM}; padding: 0 12px; }}"
            f"QPushButton:hover {{ background: #D1D1D6; }}"
        )
        for lbl, btn in self._pill_btns.items():
            btn.setStyleSheet(pill_style_active if lbl == label else pill_style_inactive)
        self._apply_filter()

    def _on_row_clicked(self, row: ExperimentRowWidget) -> None:
        if self._selected_row and self._selected_row is not row:
            self._selected_row.set_selected(False)
        self._selected_row = row
        row.set_selected(True)
        self._update_load_btn()

    def _update_load_btn(self) -> None:
        row = self._selected_row
        if row and not row.is_stale:
            name = row.abs_path.name
            if len(name) > 28:
                name = name[:25] + "…"
            self._load_btn.setText(f"Load  {name}")
            self._load_btn.setEnabled(True)
        else:
            self._load_btn.setText("Load Selected")
            self._load_btn.setEnabled(False)

    def _on_load_selected(self) -> None:
        if self._selected_row and not self._selected_row.is_stale:
            self.file_selected.emit(self._selected_row.abs_path)
            self.accept()

    # ── Keyboard navigation ────────────────────────────────────────────────────

    def keyPressEvent(self, event) -> None:
        key = event.key()

        if key == Qt.Key_Escape:
            self.reject()
            return

        if key == Qt.Key_Return or key == Qt.Key_Enter:
            self._on_load_selected()
            return

        if key == Qt.Key_F and event.modifiers() == Qt.ControlModifier:
            self._search_box.setFocus()
            return

        # Arrow key navigation
        visible_rows = self._visible_rows()
        if not visible_rows:
            super().keyPressEvent(event)
            return

        if key in (Qt.Key_Up, Qt.Key_Down):
            current_idx = -1
            if self._selected_row in visible_rows:
                current_idx = visible_rows.index(self._selected_row)

            if key == Qt.Key_Up:
                new_idx = max(0, current_idx - 1)
            else:
                new_idx = min(len(visible_rows) - 1, current_idx + 1)

            if 0 <= new_idx < len(visible_rows):
                self._on_row_clicked(visible_rows[new_idx])
                # Scroll to keep selection visible
                self._scroll.ensureWidgetVisible(visible_rows[new_idx])
            return

        super().keyPressEvent(event)

    def _visible_rows(self) -> list[ExperimentRowWidget]:
        """Return all ExperimentRowWidget instances currently in the layout."""
        rows = []
        for i in range(self._entries_layout.count()):
            item = self._entries_layout.itemAt(i)
            if item and isinstance(item.widget(), ExperimentRowWidget):
                rows.append(item.widget())
        return rows
