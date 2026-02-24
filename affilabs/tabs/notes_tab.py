"""Notes Tab — Electronic Lab Notebook embedded in the main app.

Third tab in the main nav bar (Live · Edits · Notes).
Phase 2b: interactive star rating, editable notes + auto-save, tag pill editor,
          sensorgram preview (pyqtgraph).

See docs/features/NOTES_TAB_FRS.md §18 for full implementation roadmap.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QRunnable, QThreadPool
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCompleter,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from affilabs.ui_styles import Colors, Fonts

try:
    import pyqtgraph as pg
    _HAS_PG = True
except ImportError:
    _HAS_PG = False


# ── Constants ──────────────────────────────────────────────────────────────────

_ACCENT = "#007AFF"
_SECTION_FG = "#86868B"
_NAV_BG = "#F5F5F7"
_PREVIEW_BG = "#FAFAFA"
_FILTER_ACTIVE_BG = "rgba(0, 122, 255, 0.08)"
_FILTER_ACTIVE_BORDER = _ACCENT
_ROW_HOVER = "rgba(0, 122, 255, 0.05)"
_ROW_SELECTED_BG = "rgba(0, 122, 255, 0.10)"
_ROW_SELECTED_BORDER = _ACCENT


# ── Star rating widget ─────────────────────────────────────────────────────────

class _StarRatingWidget(QWidget):
    """Interactive 1–5 star rating. Clicking the current star clears it (→ 0)."""

    rating_changed = Signal(int)  # 0–5

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rating: int = 0
        self._btns: list[QPushButton] = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        for i in range(1, 6):
            btn = QPushButton("☆")
            btn.setFixedSize(26, 26)
            btn.setFlat(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ font-size: 17px; background: transparent; border: none; "
                f"color: {_SECTION_FG}; padding: 0; }}"
                f"QPushButton:hover {{ color: #FFD700; }}"
            )
            btn.clicked.connect(lambda checked, n=i: self._on_clicked(n))
            layout.addWidget(btn)
            self._btns.append(btn)
        layout.addStretch()

    def _on_clicked(self, n: int) -> None:
        new_rating = 0 if self._rating == n else n  # click same star → clear
        self.set_rating(new_rating)
        self.rating_changed.emit(new_rating)

    def set_rating(self, rating: int) -> None:
        self._rating = max(0, min(5, rating))
        for i, btn in enumerate(self._btns):
            if i < self._rating:
                btn.setText("★")
                btn.setStyleSheet(
                    f"QPushButton {{ font-size: 17px; background: transparent; border: none; "
                    f"color: #FFD700; padding: 0; }}"
                    f"QPushButton:hover {{ color: #FFB800; }}"
                )
            else:
                btn.setText("☆")
                btn.setStyleSheet(
                    f"QPushButton {{ font-size: 17px; background: transparent; border: none; "
                    f"color: {_SECTION_FG}; padding: 0; }}"
                    f"QPushButton:hover {{ color: #FFD700; }}"
                )

    @property
    def rating(self) -> int:
        return self._rating


# ── Preview worker ─────────────────────────────────────────────────────────────

class _PreviewSignals(QObject):
    ready = Signal(str, object)   # entry_id, dict | None
    error = Signal(str, str)      # entry_id, message


class PreviewWorker(QRunnable):
    """Load sensorgram wavelength data from the Excel file in a background thread."""

    def __init__(self, entry_id: str, path: "Path") -> None:
        super().__init__()
        self.entry_id = entry_id
        self.path = path
        self.signals = _PreviewSignals()
        self.setAutoDelete(True)

    def run(self) -> None:  # noqa: C901
        try:
            import pandas as pd

            xl = pd.ExcelFile(self.path)
            # Find the sensorgram sheet
            sheet: str | None = None
            for name in xl.sheet_names:
                nl = name.lower()
                if any(k in nl for k in ("sensogram", "sensorgram", "wavelength", "spr")):
                    sheet = name
                    break
            if sheet is None and xl.sheet_names:
                sheet = xl.sheet_names[0]
            if sheet is None:
                self.signals.ready.emit(self.entry_id, None)
                return

            df = pd.read_excel(self.path, sheet_name=sheet, nrows=5000)
            if df.empty or len(df.columns) < 2:
                self.signals.ready.emit(self.entry_id, None)
                return

            # Locate time column and channel columns
            time_col: Any = None
            channel_cols: dict[str, Any] = {}
            for col in df.columns:
                cs = str(col).lower().replace(" ", "_")
                if time_col is None and ("time" in cs or cs in ("t", "time_s", "time_(s)")):
                    time_col = col
                for ch in ("a", "b", "c", "d"):
                    if ch not in channel_cols and (
                        cs in (f"ch_{ch}", f"channel_{ch}", f"ch{ch}", ch) or
                        cs.startswith(f"ch_{ch}_") or cs.endswith(f"_{ch}")
                    ):
                        channel_cols[ch] = col

            # Fallback: use column positions
            if time_col is None:
                time_col = df.columns[0]
            if not channel_cols:
                for i, col in enumerate(df.columns[1:5]):
                    channel_cols[chr(ord("a") + i)] = col

            times = df[time_col].to_numpy(dtype=float, na_value=float("nan"))
            channels: dict[str, Any] = {}
            for ch, col in channel_cols.items():
                try:
                    channels[ch] = df[col].to_numpy(dtype=float, na_value=float("nan"))
                except Exception:
                    pass

            self.signals.ready.emit(self.entry_id, {"times": times, "channels": channels})
        except Exception as exc:
            self.signals.error.emit(self.entry_id, str(exc))


# ── Row widget ─────────────────────────────────────────────────────────────────

class _ExperimentListRow(QFrame):
    """48px row representing one past recording."""

    def __init__(self, entry: dict[str, Any], abs_path: Path, stale: bool,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry = entry
        self._abs_path = abs_path
        self._stale = stale
        self._selected = False
        self._hovered = False

        self.setFixedHeight(48)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        # Date column (compact)
        entry_date = self._entry.get("date", "")
        date_str = self._format_date(entry_date)
        date_lbl = QLabel(date_str)
        date_lbl.setFixedWidth(46)
        date_lbl.setStyleSheet(
            f"font-size: 11px; color: {_SECTION_FG}; font-family: {Fonts.SYSTEM}; "
            f"background: transparent;"
        )
        layout.addWidget(date_lbl)

        # Centre block: filename + metadata line
        centre = QVBoxLayout()
        centre.setSpacing(1)
        centre.setContentsMargins(0, 0, 0, 0)

        filename = Path(self._entry.get("file", "")).stem or "unknown"
        if len(filename) > 40:
            filename = filename[:37] + "…"

        name_color = _SECTION_FG if self._stale else Colors.PRIMARY_TEXT
        name_style = (
            f"font-size: 12px; font-weight: 600; color: {name_color}; "
            f"font-family: {Fonts.SYSTEM}; background: transparent;"
        )
        if self._stale:
            name_style += " text-decoration: line-through;"
        name_lbl = QLabel(filename)
        name_lbl.setStyleSheet(name_style)
        centre.addWidget(name_lbl)

        chip = self._entry.get("chip_serial") or "—"
        cycles = self._format_cycles(self._entry.get("cycle_count"))
        meta_lbl = QLabel(f"{chip}  ·  {cycles}")
        meta_lbl.setStyleSheet(
            f"font-size: 10px; color: {_SECTION_FG}; font-family: {Fonts.SYSTEM}; "
            f"background: transparent;"
        )
        centre.addWidget(meta_lbl)

        layout.addLayout(centre)
        layout.addStretch()

        # Status badge
        badge = QLabel("Done")
        badge.setFixedHeight(18)
        badge.setStyleSheet(
            f"font-size: 10px; color: {_SECTION_FG}; background: #E5E5EA; "
            f"border-radius: 9px; padding: 0 7px; font-family: {Fonts.SYSTEM};"
        )
        if self._stale:
            badge.setText("Missing")
            badge.setStyleSheet(
                f"font-size: 10px; color: #FF3B30; background: rgba(255,59,48,0.10); "
                f"border-radius: 9px; padding: 0 7px; font-family: {Fonts.SYSTEM};"
            )
        layout.addWidget(badge)

    @staticmethod
    def _format_date(date_str: str) -> str:
        try:
            d = date.fromisoformat(date_str)
            return d.strftime("%b %d")
        except (ValueError, AttributeError):
            return "—"

    @staticmethod
    def _format_cycles(n: Any) -> str:
        try:
            n = int(n)
            return f"{n} cycle{'s' if n != 1 else ''}"
        except (TypeError, ValueError):
            return "0 cycles"

    # ── Selection / hover ─────────────────────────────────────────────────────

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
            self.setStyleSheet(
                f"_ExperimentListRow {{ background: {_ROW_SELECTED_BG}; "
                f"border-left: 3px solid {_ROW_SELECTED_BORDER}; "
                f"border-bottom: 1px solid {Colors.OVERLAY_LIGHT_10}; }}"
            )
        elif self._hovered:
            self.setStyleSheet(
                f"_ExperimentListRow {{ background: {_ROW_HOVER}; "
                f"border-left: 3px solid transparent; "
                f"border-bottom: 1px solid {Colors.OVERLAY_LIGHT_10}; }}"
            )
        else:
            self.setStyleSheet(
                f"_ExperimentListRow {{ background: {Colors.BACKGROUND_WHITE}; "
                f"border-left: 3px solid transparent; "
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
            # Walk up to find NotesTab and notify selection
            parent = self.parent()
            while parent and not isinstance(parent, NotesTab):
                parent = parent.parent()
            if parent:
                parent._on_row_clicked(self)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and not self._stale:
            parent = self.parent()
            while parent and not isinstance(parent, NotesTab):
                parent = parent.parent()
            if parent:
                parent._on_row_clicked(self)
                parent._load_in_edits(self._abs_path)
        super().mouseDoubleClickEvent(event)


# ── Kanban card ────────────────────────────────────────────────────────────────

class _KanbanCard(QFrame):
    """A card in the Kanban board representing one experiment."""

    def __init__(self, entry: dict, abs_path: "Path", stale: bool,
                 parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self._entry = entry
        self._abs_path = abs_path
        self._stale = stale
        self._selected = False
        self._drag_start_pos = None

        self.setFixedWidth(180)
        self.setCursor(Qt.PointingHandCursor)
        self.setAcceptDrops(False)
        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Filename
        filename = Path(self._entry.get("file", "")).stem or "unknown"
        if len(filename) > 22:
            filename = filename[:19] + "…"
        name_color = _SECTION_FG if self._stale else Colors.PRIMARY_TEXT
        name_lbl = QLabel(filename)
        name_lbl.setWordWrap(False)
        name_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {name_color}; "
            f"font-family: {Fonts.SYSTEM}; background: transparent;"
        )
        if self._stale:
            name_lbl.setStyleSheet(name_lbl.styleSheet() + " text-decoration: line-through;")
        layout.addWidget(name_lbl)

        # Date + chip
        date_str = _KanbanCard._fmt_date(self._entry.get("date", ""))
        chip = self._entry.get("chip_serial") or "—"
        sub_lbl = QLabel(f"{date_str}  ·  {chip}")
        sub_lbl.setStyleSheet(
            f"font-size: 10px; color: {_SECTION_FG}; font-family: {Fonts.SYSTEM}; "
            f"background: transparent;"
        )
        layout.addWidget(sub_lbl)

        # Stars
        rating = int(self._entry.get("rating") or 0)
        if rating:
            stars = "★" * rating + "☆" * (5 - rating)
            star_lbl = QLabel(stars)
            star_lbl.setStyleSheet(
                f"font-size: 11px; color: #FFD700; background: transparent; "
                f"font-family: {Fonts.SYSTEM};"
            )
            layout.addWidget(star_lbl)

        # Tag pills (up to 2)
        tags = self._entry.get("tags") or []
        if tags:
            tag_row = QHBoxLayout()
            tag_row.setContentsMargins(0, 0, 0, 0)
            tag_row.setSpacing(4)
            for tag in tags[:2]:
                pill = QLabel(f"#{tag}")
                pill.setStyleSheet(
                    f"font-size: 9px; color: {_ACCENT}; background: rgba(0,122,255,0.10); "
                    f"border-radius: 8px; padding: 1px 5px; font-family: {Fonts.SYSTEM};"
                )
                tag_row.addWidget(pill)
            if len(tags) > 2:
                more = QLabel(f"+{len(tags)-2}")
                more.setStyleSheet(
                    f"font-size: 9px; color: {_SECTION_FG}; background: transparent; "
                    f"font-family: {Fonts.SYSTEM};"
                )
                tag_row.addWidget(more)
            tag_row.addStretch()
            layout.addLayout(tag_row)

    @staticmethod
    def _fmt_date(date_str: str) -> str:
        try:
            from datetime import date as _date
            d = _date.fromisoformat(date_str)
            return d.strftime("%b %d")
        except (ValueError, AttributeError):
            return "—"

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._apply_style()

    def _apply_style(self) -> None:
        if self._selected:
            self.setStyleSheet(
                f"_KanbanCard {{ background: {Colors.BACKGROUND_WHITE}; "
                f"border: 2px solid {_ACCENT}; border-radius: 8px; }}"
            )
        else:
            self.setStyleSheet(
                f"_KanbanCard {{ background: {Colors.BACKGROUND_WHITE}; "
                f"border: 1px solid {Colors.OVERLAY_LIGHT_20}; border-radius: 8px; }}"
                f"_KanbanCard:hover {{ border: 1px solid {_ACCENT}; }}"
            )

    @property
    def entry(self) -> dict:
        return self._entry

    @property
    def abs_path(self) -> "Path":
        return self._abs_path

    @property
    def is_stale(self) -> bool:
        return self._stale

    # ── Mouse events ──────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.position().toPoint()
            notes_tab = self._find_notes_tab()
            if notes_tab:
                notes_tab._on_card_clicked(self)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and not self._stale:
            notes_tab = self._find_notes_tab()
            if notes_tab:
                notes_tab._on_card_clicked(self)
                notes_tab._load_in_edits(self._abs_path)
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
        if self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return
        dist = (event.position().toPoint() - self._drag_start_pos).manhattanLength()
        if dist < 8:
            super().mouseMoveEvent(event)
            return
        # Start drag
        from PySide6.QtGui import QDrag
        from PySide6.QtCore import QMimeData
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self._entry.get("id", ""))
        drag.setMimeData(mime)
        # Render card as drag pixmap
        from PySide6.QtGui import QPixmap, QPainter
        px = QPixmap(self.size())
        px.fill(Qt.transparent)
        painter = QPainter(px)
        painter.setOpacity(0.8)
        self.render(painter)
        painter.end()
        drag.setPixmap(px)
        drag.setHotSpot(event.position().toPoint())
        drag.exec(Qt.MoveAction)

    def _find_notes_tab(self) -> "NotesTab | None":
        p = self.parent()
        while p:
            if isinstance(p, NotesTab):
                return p
            p = p.parent()
        return None


# ── Kanban column ───────────────────────────────────────────────────────────────

_COLUMN_DEFS = [
    ("to_repeat", "TO REPEAT", "#FF3B30"),
    ("done",      "DONE",      "#34C759"),
    ("archived",  "ARCHIVED",  _SECTION_FG),
]


class _KanbanColumn(QFrame):
    """A scrollable column in the Kanban board."""

    def __init__(self, status: str, label: str, color: str,
                 parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self.status = status
        self._color = color
        self._cards: list[_KanbanCard] = []
        self._highlighted = False

        self.setMinimumWidth(200)
        self.setAcceptDrops(True)
        self._build_ui(label)

    def _build_ui(self, label: str) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Column header
        header = QFrame()
        header.setFixedHeight(40)
        header.setStyleSheet(
            f"QFrame {{ background: {_NAV_BG}; "
            f"border-bottom: 2px solid {self._color}; }}"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 0, 12, 0)

        self._header_lbl = QLabel(label)
        self._header_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {self._color}; "
            f"font-family: {Fonts.SYSTEM}; background: transparent; letter-spacing: 0.5px;"
        )
        h_layout.addWidget(self._header_lbl)
        h_layout.addStretch()

        self._count_lbl = QLabel("0")
        self._count_lbl.setStyleSheet(
            f"font-size: 10px; color: {_SECTION_FG}; background: {Colors.OVERLAY_LIGHT_10}; "
            f"border-radius: 8px; padding: 1px 6px; font-family: {Fonts.SYSTEM};"
        )
        h_layout.addWidget(self._count_lbl)
        outer.addWidget(header)

        # Scrollable card area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {_NAV_BG}; border: none; }}"
            f"QScrollBar:vertical {{ width: 4px; background: transparent; }}"
            f"QScrollBar::handle:vertical {{ background: {Colors.OVERLAY_LIGHT_20}; border-radius: 2px; }}"
        )

        self._cards_widget = QWidget()
        self._cards_widget.setStyleSheet(f"background: {_NAV_BG};")
        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setContentsMargins(10, 10, 10, 10)
        self._cards_layout.setSpacing(8)
        self._cards_layout.addStretch()

        scroll.setWidget(self._cards_widget)
        outer.addWidget(scroll, stretch=1)

    def set_cards(self, cards: list[_KanbanCard]) -> None:
        # Remove old cards from layout (keep trailing stretch)
        while self._cards_layout.count() > 1:
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self._cards = cards
        for card in cards:
            card.setParent(self._cards_widget)
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)
            card.show()
        self._count_lbl.setText(str(len(cards)))

    def add_card(self, card: _KanbanCard) -> None:
        card.setParent(self._cards_widget)
        self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)
        card.show()
        if card not in self._cards:
            self._cards.append(card)
        self._count_lbl.setText(str(len(self._cards)))

    def remove_card(self, card: _KanbanCard) -> None:
        if card in self._cards:
            self._cards.remove(card)
        card.setParent(None)
        self._count_lbl.setText(str(len(self._cards)))

    def _set_highlight(self, on: bool) -> None:
        self._highlighted = on
        self.setStyleSheet(
            f"_KanbanColumn {{ background: rgba(0,122,255,0.04); }}" if on else ""
        )

    # ── Drop target ───────────────────────────────────────────────────────────

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasText():
            self._set_highlight(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._set_highlight(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        self._set_highlight(False)
        entry_id = event.mimeData().text()
        if not entry_id:
            event.ignore()
            return
        # Find NotesTab and delegate
        p = self.parent()
        while p:
            if isinstance(p, NotesTab):
                p._on_card_dropped(entry_id, self.status)
                break
            p = p.parent()
        event.acceptProposedAction()


# ── Kanban view ─────────────────────────────────────────────────────────────────

class _KanbanView(QWidget):
    """Horizontal three-column Kanban board."""

    def __init__(self, parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self._columns: dict[str, _KanbanColumn] = {}
        self._all_cards: list[_KanbanCard] = []
        self._selected_card: _KanbanCard | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        for status, label, color in _COLUMN_DEFS:
            col = _KanbanColumn(status, label, color, parent=self)
            self._columns[status] = col
            layout.addWidget(col, stretch=1)

            if status != _COLUMN_DEFS[-1][0]:  # separator between columns
                sep = QFrame()
                sep.setFrameShape(QFrame.VLine)
                sep.setStyleSheet(f"color: {Colors.OVERLAY_LIGHT_10};")
                layout.addWidget(sep)

    def populate(self, rows: "list[_ExperimentListRow]") -> None:
        """Build cards from list rows and sort into columns by kanban_status."""
        self._all_cards = []
        buckets: dict[str, list[_KanbanCard]] = {s: [] for s, *_ in _COLUMN_DEFS}

        for row in rows:
            card = _KanbanCard(row.entry, row.abs_path, row.is_stale, parent=self)
            self._all_cards.append(card)
            status = row.entry.get("kanban_status", "done")
            if status not in buckets:
                status = "done"
            buckets[status].append(card)

        for status, cards in buckets.items():
            self._columns[status].set_cards(cards)

        self._selected_card = None

    def move_card(self, entry_id: str, new_status: str) -> None:
        """Move a card to a different column (after status saved to index)."""
        card = next((c for c in self._all_cards if c.entry.get("id") == entry_id), None)
        if card is None:
            return
        old_status = card.entry.get("kanban_status", "done")
        if old_status in self._columns:
            self._columns[old_status].remove_card(card)
        card.entry["kanban_status"] = new_status
        if new_status in self._columns:
            self._columns[new_status].add_card(card)

    def select_card(self, entry_id: str | None) -> None:
        """Visually select the card with the given id, deselect others."""
        for card in self._all_cards:
            card.set_selected(card.entry.get("id") == entry_id)
        self._selected_card = next(
            (c for c in self._all_cards if c.entry.get("id") == entry_id), None
        )


# ── Section header ─────────────────────────────────────────────────────────────

def _make_section_header(title: str) -> QLabel:
    lbl = QLabel(title.upper())
    lbl.setFixedHeight(26)
    lbl.setStyleSheet(
        f"QLabel {{ font-size: 10px; color: {_SECTION_FG}; font-weight: 500; "
        f"font-family: {Fonts.SYSTEM}; background: {_NAV_BG}; "
        f"padding-left: 12px; padding-top: 6px; }}"
    )
    return lbl


# ── Notes Tab (main widget) ────────────────────────────────────────────────────

class NotesTab(QWidget):
    """Electronic Lab Notebook — Phase 2b: interactive ELN widgets."""

    def __init__(self, main_window: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_window = main_window
        self._all_rows: list[_ExperimentListRow] = []
        self._selected_row: _ExperimentListRow | None = None
        self._active_filter: str = "all"   # "all" | "needs_repeat" | "planned" | "unrated"
        self._current_entry_id: str | None = None  # id of entry shown in right panel
        self._notes_blocking: bool = False          # suppress save while populating

        # Search debounce
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self._apply_filter)

        # Notes auto-save debounce (800 ms)
        self._notes_save_timer = QTimer()
        self._notes_save_timer.setSingleShot(True)
        self._notes_save_timer.setInterval(800)
        self._notes_save_timer.timeout.connect(self._save_notes)

        self._build_ui()
        self._load_entries()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        nav = self._build_nav_panel()
        nav.setFixedWidth(200)
        root.addWidget(nav)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet(f"color: {Colors.OVERLAY_LIGHT_10};")
        root.addWidget(sep)

        root.addWidget(self._build_list_panel(), stretch=1)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet(f"color: {Colors.OVERLAY_LIGHT_10};")
        root.addWidget(sep2)

        preview = self._build_preview_panel()
        preview.setFixedWidth(300)
        root.addWidget(preview)

    # ── Left nav panel ─────────────────────────────────────────────────────────

    def _build_nav_panel(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"QFrame {{ background: {_NAV_BG}; }}")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(2)

        # Section header
        filters_hdr = QLabel("FILTERS")
        filters_hdr.setStyleSheet(
            f"font-size: 10px; color: {_SECTION_FG}; font-weight: 600; "
            f"font-family: {Fonts.SYSTEM}; padding-left: 14px; padding-top: 4px; "
            f"background: transparent;"
        )
        layout.addWidget(filters_hdr)

        self._filter_btns: dict[str, QPushButton] = {}
        filter_defs = [
            ("all",          "All Experiments",   Colors.PRIMARY_TEXT, None),
            ("needs_repeat", "Needs Repeat",       "#FF3B30",          None),
            ("planned",      "Planned",             _ACCENT,            None),
            ("unrated",      "Unrated",             _SECTION_FG,        None),
        ]
        for key, label, color, _ in filter_defs:
            btn = QPushButton()
            btn.setFlat(True)
            btn.setCheckable(False)
            btn.setFixedHeight(32)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setProperty("filter_key", key)
            btn.setProperty("filter_color", color)
            self._update_filter_btn_text(btn, label, 0, color, active=(key == "all"))
            btn.clicked.connect(lambda checked, k=key: self._on_filter_clicked(k))
            layout.addWidget(btn)
            self._filter_btns[key] = btn

        layout.addSpacing(16)

        # Tags placeholder
        tags_hdr = QLabel("TAGS")
        tags_hdr.setStyleSheet(
            f"font-size: 10px; color: {_SECTION_FG}; font-weight: 600; "
            f"font-family: {Fonts.SYSTEM}; padding-left: 14px; padding-top: 4px; "
            f"background: transparent;"
        )
        layout.addWidget(tags_hdr)

        coming_lbl = QLabel("Coming in next update")
        coming_lbl.setStyleSheet(
            f"font-size: 10px; color: {_SECTION_FG}; font-style: italic; "
            f"font-family: {Fonts.SYSTEM}; padding-left: 14px; background: transparent;"
        )
        layout.addWidget(coming_lbl)

        layout.addStretch()
        return frame

    @staticmethod
    def _update_filter_btn_text(btn: QPushButton, label: str, count: int,
                                 color: str, active: bool) -> None:
        btn.setText(f"  {label}  ({count})")
        if active:
            btn.setStyleSheet(
                f"QPushButton {{ text-align: left; font-size: 12px; font-weight: 600; "
                f"color: {_ACCENT}; font-family: {Fonts.SYSTEM}; "
                f"background: {_FILTER_ACTIVE_BG}; border: none; "
                f"border-left: 3px solid {_FILTER_ACTIVE_BORDER}; "
                f"padding-left: 11px; }}"
            )
        else:
            btn.setStyleSheet(
                f"QPushButton {{ text-align: left; font-size: 12px; font-weight: 400; "
                f"color: {color}; font-family: {Fonts.SYSTEM}; "
                f"background: transparent; border: none; border-left: 3px solid transparent; "
                f"padding-left: 14px; }}"
                f"QPushButton:hover {{ background: rgba(0,0,0,0.04); }}"
            )

    # ── Centre list panel ──────────────────────────────────────────────────────

    def _build_list_panel(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"QFrame {{ background: {Colors.BACKGROUND_WHITE}; }}")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Search bar
        search_frame = QFrame()
        search_frame.setStyleSheet(
            f"QFrame {{ background: {Colors.BACKGROUND_WHITE}; "
            f"border-bottom: 1px solid {Colors.OVERLAY_LIGHT_10}; }}"
        )
        search_frame.setFixedHeight(46)
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(12, 8, 12, 8)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search notes, tags, chips…")
        self._search_box.setFixedHeight(30)
        self._search_box.setStyleSheet(
            f"QLineEdit {{ background: {_NAV_BG}; border: 1px solid {Colors.OVERLAY_LIGHT_20}; "
            f"border-radius: 6px; font-size: 12px; padding: 4px 10px; font-family: {Fonts.SYSTEM}; "
            f"color: {Colors.PRIMARY_TEXT}; }}"
            f"QLineEdit:focus {{ border: 1px solid {_ACCENT}; }}"
        )
        self._search_box.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self._search_box)
        layout.addWidget(search_frame)

        # ── View toggle header (List / Kanban) ─────────────────────────────────
        toggle_frame = QFrame()
        toggle_frame.setStyleSheet(
            f"QFrame {{ background: {Colors.BACKGROUND_WHITE}; "
            f"border-bottom: 1px solid {Colors.OVERLAY_LIGHT_10}; }}"
        )
        toggle_frame.setFixedHeight(36)
        toggle_layout = QHBoxLayout(toggle_frame)
        toggle_layout.setContentsMargins(10, 4, 10, 4)
        toggle_layout.setSpacing(4)

        self._list_view_btn = QPushButton("\u2630  List")
        self._kanban_view_btn = QPushButton("\u229e  Kanban")
        for btn in (self._list_view_btn, self._kanban_view_btn):
            btn.setFixedHeight(26)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ font-size: 11px; font-family: {Fonts.SYSTEM}; "
                f"border-radius: 5px; padding: 2px 10px; border: none; "
                f"color: {_SECTION_FG}; background: transparent; }}"
                f"QPushButton:hover {{ background: {Colors.OVERLAY_LIGHT_10}; }}"
            )

        self._list_view_btn.clicked.connect(self._switch_to_list_view)
        self._kanban_view_btn.clicked.connect(self._switch_to_kanban_view)
        toggle_layout.addWidget(self._list_view_btn)
        toggle_layout.addWidget(self._kanban_view_btn)
        toggle_layout.addStretch()
        layout.addWidget(toggle_frame)

        # ── View stack (List = 0, Kanban = 1) ──────────────────────────────────
        self._view_stack = QStackedWidget()

        # Index 0 — List
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background: {_NAV_BG}; border: none; }}"
            f"QScrollBar:vertical {{ width: 6px; background: transparent; }}"
            f"QScrollBar::handle:vertical {{ background: {Colors.OVERLAY_LIGHT_20}; border-radius: 3px; }}"
        )

        self._entries_widget = QWidget()
        self._entries_widget.setStyleSheet(f"background: {_NAV_BG};")
        self._entries_layout = QVBoxLayout(self._entries_widget)
        self._entries_layout.setContentsMargins(0, 4, 0, 8)
        self._entries_layout.setSpacing(0)
        self._entries_layout.addStretch()

        self._scroll.setWidget(self._entries_widget)
        self._view_stack.addWidget(self._scroll)  # index 0

        # Index 1 — Kanban
        self._kanban_view = _KanbanView(parent=self)
        self._view_stack.addWidget(self._kanban_view)  # index 1

        layout.addWidget(self._view_stack, stretch=1)
        self._switch_to_list_view()  # start in list mode

        # Footer count label
        footer = QFrame()
        footer.setStyleSheet(
            f"QFrame {{ background: {Colors.BACKGROUND_WHITE}; "
            f"border-top: 1px solid {Colors.OVERLAY_LIGHT_10}; }}"
        )
        footer.setFixedHeight(32)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(14, 0, 14, 0)
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(
            f"font-size: 11px; color: {_SECTION_FG}; font-family: {Fonts.SYSTEM}; "
            f"background: transparent; border: none;"
        )
        footer_layout.addWidget(self._count_lbl)
        layout.addWidget(footer)

        return frame

    # ── Right preview panel ────────────────────────────────────────────────────

    def _build_preview_panel(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"QFrame {{ background: {_PREVIEW_BG}; }}")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(10)

        # ── Sensorgram preview ────────────────────────────────────────────────
        if _HAS_PG:
            self._preview_plot = pg.PlotWidget()
            self._preview_plot.setFixedHeight(130)
            self._preview_plot.setBackground(_PREVIEW_BG)
            self._preview_plot.getAxis("left").setStyle(showValues=False)
            self._preview_plot.getAxis("bottom").setStyle(showValues=False)
            self._preview_plot.getPlotItem().setContentsMargins(0, 0, 0, 0)
            self._preview_plot.showGrid(x=False, y=False)
            self._preview_plot.setMouseEnabled(x=False, y=False)
            self._preview_plot.setMenuEnabled(False)
            self._preview_plot_placeholder = None
            layout.addWidget(self._preview_plot)
        else:
            self._preview_plot = None
            self._preview_plot_placeholder = QLabel("Install pyqtgraph for preview")
            self._preview_plot_placeholder.setFixedHeight(50)
            self._preview_plot_placeholder.setAlignment(Qt.AlignCenter)
            self._preview_plot_placeholder.setStyleSheet(
                f"font-size: 10px; color: {_SECTION_FG}; font-style: italic; "
                f"background: transparent;"
            )
            layout.addWidget(self._preview_plot_placeholder)
        self._preview_entry_id: str | None = None  # tracks which entry the plot shows

        # ── Title ─────────────────────────────────────────────────────────────
        self._preview_title = QLabel("Select an experiment")
        self._preview_title.setWordWrap(True)
        self._preview_title.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {Colors.PRIMARY_TEXT}; "
            f"font-family: {Fonts.SYSTEM}; background: transparent;"
        )
        layout.addWidget(self._preview_title)

        # ── Metadata grid ─────────────────────────────────────────────────────
        meta_frame = QFrame()
        meta_frame.setStyleSheet("background: transparent;")
        meta_grid = QGridLayout(meta_frame)
        meta_grid.setContentsMargins(0, 0, 0, 0)
        meta_grid.setHorizontalSpacing(10)
        meta_grid.setVerticalSpacing(4)
        meta_grid.setColumnStretch(1, 1)
        meta_grid.setColumnStretch(3, 1)

        self._meta_labels: dict[str, QLabel] = {}
        meta_defs = [
            ("chip",     "Chip",     0, 0),
            ("duration", "Duration", 0, 2),
            ("cycles",   "Cycles",   1, 0),
            ("user",     "User",     1, 2),
            ("date",     "Date",     2, 0),
            ("hardware", "Hardware", 2, 2),
        ]
        lbl_style = (
            f"font-size: 11px; color: {_SECTION_FG}; font-family: {Fonts.SYSTEM}; "
            f"background: transparent;"
        )
        val_style = (
            f"font-size: 11px; color: {Colors.PRIMARY_TEXT}; font-family: {Fonts.SYSTEM}; "
            f"background: transparent; font-weight: 500;"
        )
        for key, label, row, col in meta_defs:
            key_lbl = QLabel(label)
            key_lbl.setStyleSheet(lbl_style)
            meta_grid.addWidget(key_lbl, row, col)
            val_lbl = QLabel("—")
            val_lbl.setStyleSheet(val_style)
            meta_grid.addWidget(val_lbl, row, col + 1)
            self._meta_labels[key] = val_lbl

        layout.addWidget(meta_frame)

        # ── Separator ─────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {Colors.OVERLAY_LIGHT_10};")
        layout.addWidget(sep)

        # ── Notes (editable, auto-saves on focusOut) ──────────────────────────
        notes_hdr = QLabel("NOTES")
        notes_hdr.setStyleSheet(
            f"font-size: 10px; color: {_SECTION_FG}; font-weight: 600; "
            f"font-family: {Fonts.SYSTEM}; background: transparent;"
        )
        layout.addWidget(notes_hdr)

        self._notes_edit = QTextEdit()
        self._notes_edit.setReadOnly(False)
        self._notes_edit.setPlaceholderText("Add notes for this experiment…")
        self._notes_edit.setFixedHeight(72)
        self._notes_edit.setStyleSheet(
            f"QTextEdit {{ background: {Colors.BACKGROUND_WHITE}; border: 1px solid {Colors.OVERLAY_LIGHT_20}; "
            f"border-radius: 6px; font-size: 11px; font-family: {Fonts.SYSTEM}; "
            f"color: {Colors.PRIMARY_TEXT}; padding: 4px; }}"
            f"QTextEdit:focus {{ border: 1px solid {_ACCENT}; }}"
            f"QTextEdit:disabled {{ background: {_NAV_BG}; }}"
        )
        self._notes_edit.setEnabled(False)
        self._notes_edit.textChanged.connect(self._on_notes_changed)
        layout.addWidget(self._notes_edit)

        # ── Rating (interactive _StarRatingWidget) ────────────────────────────
        rating_hdr = QLabel("RATING")
        rating_hdr.setStyleSheet(
            f"font-size: 10px; color: {_SECTION_FG}; font-weight: 600; "
            f"font-family: {Fonts.SYSTEM}; background: transparent;"
        )
        layout.addWidget(rating_hdr)

        self._star_rating = _StarRatingWidget()
        self._star_rating.setEnabled(False)
        self._star_rating.rating_changed.connect(self._on_rating_changed)
        layout.addWidget(self._star_rating)

        # ── Tags ──────────────────────────────────────────────────────────────
        tags_hdr = QLabel("TAGS")
        tags_hdr.setStyleSheet(
            f"font-size: 10px; color: {_SECTION_FG}; font-weight: 600; "
            f"font-family: {Fonts.SYSTEM}; background: transparent;"
        )
        layout.addWidget(tags_hdr)

        # Horizontal scroll area for tag pills
        tags_scroll = QScrollArea()
        tags_scroll.setFixedHeight(36)
        tags_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        tags_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tags_scroll.setWidgetResizable(True)
        tags_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:horizontal { height: 4px; background: transparent; }"
            f"QScrollBar::handle:horizontal {{ background: {Colors.OVERLAY_LIGHT_20}; border-radius: 2px; }}"
        )
        tags_inner = QWidget()
        tags_inner.setStyleSheet("background: transparent;")
        self._tags_layout = QHBoxLayout(tags_inner)
        self._tags_layout.setContentsMargins(0, 2, 0, 2)
        self._tags_layout.setSpacing(6)

        self._add_tag_btn = QPushButton("+ Add tag")
        self._add_tag_btn.setFixedHeight(24)
        self._add_tag_btn.setEnabled(False)
        self._add_tag_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px dashed {Colors.OVERLAY_LIGHT_20}; "
            f"border-radius: 12px; font-size: 10px; color: {_SECTION_FG}; "
            f"font-family: {Fonts.SYSTEM}; padding: 0 8px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; color: {_ACCENT}; }}"
            f"QPushButton:disabled {{ opacity: 0.4; }}"
        )
        self._add_tag_btn.clicked.connect(self._on_add_tag)
        self._tags_layout.addWidget(self._add_tag_btn)
        self._tags_layout.addStretch()
        tags_scroll.setWidget(tags_inner)
        layout.addWidget(tags_scroll)

        layout.addStretch()

        # ── Actions bar ───────────────────────────────────────────────────────
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        self._load_btn = QPushButton("Load in Edits")
        self._load_btn.setFixedHeight(30)
        self._load_btn.setEnabled(False)
        self._load_btn.setStyleSheet(
            f"QPushButton {{ background: {_ACCENT}; color: white; border: none; "
            f"border-radius: 6px; font-size: 11px; font-weight: 600; "
            f"font-family: {Fonts.SYSTEM}; padding: 0 12px; }}"
            f"QPushButton:hover {{ background: #0066CC; }}"
            f"QPushButton:disabled {{ background: {Colors.OVERLAY_LIGHT_20}; color: {_SECTION_FG}; }}"
        )
        self._load_btn.clicked.connect(self._on_load_in_edits_clicked)
        actions_layout.addWidget(self._load_btn)

        self._open_btn = QPushButton("Open Excel")
        self._open_btn.setFixedHeight(30)
        self._open_btn.setEnabled(False)
        self._open_btn.setStyleSheet(
            f"QPushButton {{ background: {_NAV_BG}; color: {_ACCENT}; "
            f"border: 1px solid {Colors.OVERLAY_LIGHT_20}; border-radius: 6px; "
            f"font-size: 11px; font-weight: 500; font-family: {Fonts.SYSTEM}; padding: 0 12px; }}"
            f"QPushButton:hover {{ background: rgba(0,122,255,0.08); }}"
            f"QPushButton:disabled {{ color: {_SECTION_FG}; }}"
        )
        self._open_btn.clicked.connect(self._on_open_excel_clicked)
        actions_layout.addWidget(self._open_btn)

        layout.addLayout(actions_layout)
        return frame

    # ── View toggle ────────────────────────────────────────────────────────────

    def _switch_to_list_view(self) -> None:
        self._view_stack.setCurrentIndex(0)
        self._list_view_btn.setStyleSheet(
            f"QPushButton {{ font-size: 11px; font-family: {Fonts.SYSTEM}; "
            f"border-radius: 5px; padding: 2px 10px; border: none; "
            f"color: white; background: {_ACCENT}; }}"
        )
        self._kanban_view_btn.setStyleSheet(
            f"QPushButton {{ font-size: 11px; font-family: {Fonts.SYSTEM}; "
            f"border-radius: 5px; padding: 2px 10px; border: none; "
            f"color: {_SECTION_FG}; background: transparent; }}"
            f"QPushButton:hover {{ background: {Colors.OVERLAY_LIGHT_10}; }}"
        )

    def _switch_to_kanban_view(self) -> None:
        self._view_stack.setCurrentIndex(1)
        self._kanban_view_btn.setStyleSheet(
            f"QPushButton {{ font-size: 11px; font-family: {Fonts.SYSTEM}; "
            f"border-radius: 5px; padding: 2px 10px; border: none; "
            f"color: white; background: {_ACCENT}; }}"
        )
        self._list_view_btn.setStyleSheet(
            f"QPushButton {{ font-size: 11px; font-family: {Fonts.SYSTEM}; "
            f"border-radius: 5px; padding: 2px 10px; border: none; "
            f"color: {_SECTION_FG}; background: transparent; }}"
            f"QPushButton:hover {{ background: {Colors.OVERLAY_LIGHT_10}; }}"
        )

    # ── Kanban interaction ─────────────────────────────────────────────────────

    def _on_card_clicked(self, card: "_KanbanCard") -> None:
        """Card clicked in Kanban view — select it and populate preview."""
        self._kanban_view.select_card(card.entry.get("id"))
        # Deselect list row
        if self._selected_row:
            self._selected_row.set_selected(False)
            self._selected_row = None
        # Populate right panel via a synthetic _ExperimentListRow-like object
        # reuse _populate_preview by constructing a minimal proxy
        class _CardProxy:
            def __init__(self, c):
                self.entry = c.entry
                self.abs_path = c.abs_path
                self.is_stale = c.is_stale
        self._populate_preview(_CardProxy(card))  # type: ignore[arg-type]
        self._current_entry_id = card.entry.get("id")
        self._notes_blocking = True
        self._notes_edit.setPlainText(card.entry.get("notes") or "")
        self._notes_blocking = False
        self._notes_edit.setEnabled(True)
        self._star_rating.set_rating(int(card.entry.get("rating") or 0))
        self._star_rating.setEnabled(True)
        self._add_tag_btn.setEnabled(True)
        self._refresh_tags_panel(card.entry.get("tags") or [])

    def _on_card_dropped(self, entry_id: str, new_status: str) -> None:
        """Card dropped onto a column — save new status and move card."""
        from affilabs.services.experiment_index import ExperimentIndex
        try:
            ExperimentIndex().set_status(entry_id, new_status)
        except Exception:
            pass
        self._kanban_view.move_card(entry_id, new_status)
        # Update in-memory entry on the matching list row
        for row in self._all_rows:
            if row.entry.get("id") == entry_id:
                row.entry["kanban_status"] = new_status
                break

    # ── Data loading ───────────────────────────────────────────────────────────

    def _load_entries(self) -> None:
        from affilabs.services.experiment_index import ExperimentIndex
        index = ExperimentIndex()
        entries = index.all_entries()

        base = Path.home() / "Documents" / "Affilabs Data"
        rows: list[_ExperimentListRow] = []

        for entry in entries:
            file_val = entry.get("file", "")
            if not file_val:
                continue
            file_path = Path(file_val)
            abs_path = file_path if file_path.is_absolute() else base / file_path
            stale = not abs_path.exists()
            row = _ExperimentListRow(entry, abs_path, stale, parent=self._entries_widget)
            rows.append(row)

        self._all_rows = rows
        self._apply_filter()
        self._update_filter_counts()
        self._kanban_view.populate(rows)

    def _update_filter_counts(self) -> None:
        from affilabs.services.experiment_index import ExperimentIndex
        total = len(self._all_rows)
        self._update_filter_btn_text(
            self._filter_btns["all"], "All Experiments", total,
            Colors.PRIMARY_TEXT, active=(self._active_filter == "all")
        )
        try:
            idx = ExperimentIndex()
            needs_repeat_n = sum(
                1 for r in self._all_rows
                if int(r.entry.get("rating") or 0) in (1, 2)
            )
            planned_n = len(idx.all_planned())
            unrated_n = sum(1 for r in self._all_rows if not r.entry.get("rating"))
        except Exception:
            needs_repeat_n = planned_n = unrated_n = 0
        for key, label, color, count in [
            ("needs_repeat", "Needs Repeat", "#FF3B30",    needs_repeat_n),
            ("planned",      "Planned",       _ACCENT,     planned_n),
            ("unrated",      "Unrated",       _SECTION_FG, unrated_n),
        ]:
            self._update_filter_btn_text(
                self._filter_btns[key], label, count,
                color, active=(self._active_filter == key)
            )

    # ── Filtering ──────────────────────────────────────────────────────────────

    def _on_search_changed(self) -> None:
        self._search_timer.start()

    def _apply_filter(self) -> None:
        keyword = self._search_box.text().strip().lower()

        visible: list[_ExperimentListRow] = []
        for row in self._all_rows:
            e = row.entry

            # Active nav filter
            if self._active_filter == "needs_repeat":
                rating = int(e.get("rating") or 0)
                if rating not in (1, 2):
                    continue
            elif self._active_filter == "unrated":
                if e.get("rating"):
                    continue
            elif self._active_filter == "planned":
                continue  # planned entries not yet in row list

            if keyword:
                haystack = " ".join([
                    str(e.get("user", "")),
                    str(e.get("chip_serial", "")),
                    Path(e.get("file", "")).name,
                    str(e.get("notes", "")),
                    " ".join(e.get("tags") or []),
                ]).lower()
                if keyword not in haystack:
                    continue

            visible.append(row)

        self._rebuild_list(visible)

    def _rebuild_list(self, rows: list[_ExperimentListRow]) -> None:
        # Clear layout (keep trailing stretch)
        while self._entries_layout.count() > 1:
            item = self._entries_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        if not rows:
            self._show_empty_state()
            self._count_lbl.setText("")
            return

        today = date.today()
        buckets: dict[str, list[_ExperimentListRow]] = {
            "Today": [],
            "This week": [],
            "This month": [],
            "Earlier": [],
        }
        for row in rows:
            try:
                entry_date = date.fromisoformat(row.entry.get("date", ""))
            except (ValueError, AttributeError):
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

        # Restore selection if still visible
        if self._selected_row and self._selected_row in rows:
            self._selected_row.set_selected(True)
        else:
            self._selected_row = None
            self._clear_preview()

    def _show_empty_state(self) -> None:
        from affilabs.services.experiment_index import ExperimentIndex
        has_any = bool(self._all_rows)

        container = QWidget()
        container.setStyleSheet(f"background: {_NAV_BG}; border: none;")
        vbox = QVBoxLayout(container)
        vbox.setAlignment(Qt.AlignCenter)
        vbox.setSpacing(6)

        if has_any:
            icon_lbl = QLabel("🔬")
            icon_lbl.setStyleSheet("font-size: 32px; background: transparent; border: none;")
            icon_lbl.setAlignment(Qt.AlignCenter)
            vbox.addWidget(icon_lbl)
            title_lbl = QLabel("No matching experiments")
            title_lbl.setStyleSheet(
                f"font-size: 13px; font-weight: 600; color: {Colors.PRIMARY_TEXT}; "
                f"font-family: {Fonts.SYSTEM}; background: transparent; border: none;"
            )
            title_lbl.setAlignment(Qt.AlignCenter)
            vbox.addWidget(title_lbl)
            sub_lbl = QLabel("Try a different search or filter.")
            sub_lbl.setStyleSheet(
                f"font-size: 11px; color: {_SECTION_FG}; "
                f"font-family: {Fonts.SYSTEM}; background: transparent; border: none;"
            )
            sub_lbl.setAlignment(Qt.AlignCenter)
            vbox.addWidget(sub_lbl)
        else:
            icon_lbl = QLabel("📋")
            icon_lbl.setStyleSheet("font-size: 32px; background: transparent; border: none;")
            icon_lbl.setAlignment(Qt.AlignCenter)
            vbox.addWidget(icon_lbl)
            title_lbl = QLabel("No experiments yet")
            title_lbl.setStyleSheet(
                f"font-size: 13px; font-weight: 600; color: {Colors.PRIMARY_TEXT}; "
                f"font-family: {Fonts.SYSTEM}; background: transparent; border: none;"
            )
            title_lbl.setAlignment(Qt.AlignCenter)
            vbox.addWidget(title_lbl)
            sub_lbl = QLabel("Start recording to build your history.")
            sub_lbl.setStyleSheet(
                f"font-size: 11px; color: {_SECTION_FG}; "
                f"font-family: {Fonts.SYSTEM}; background: transparent; border: none;"
            )
            sub_lbl.setAlignment(Qt.AlignCenter)
            vbox.addWidget(sub_lbl)

        self._entries_layout.insertWidget(0, container)

    # ── Interaction ────────────────────────────────────────────────────────────

    def _on_filter_clicked(self, key: str) -> None:
        self._active_filter = key
        self._update_filter_counts()
        self._apply_filter()

    def _on_row_clicked(self, row: _ExperimentListRow) -> None:
        if self._selected_row and self._selected_row is not row:
            self._selected_row.set_selected(False)
        self._selected_row = row
        row.set_selected(True)
        self._populate_preview(row)
        # Sync kanban selection
        self._kanban_view.select_card(row.entry.get("id"))

    def _populate_preview(self, row: _ExperimentListRow) -> None:
        e = row.entry
        path = row.abs_path

        # Title
        title = path.stem if not row.is_stale else f"{path.stem} (missing)"
        self._preview_title.setText(title)

        # Metadata
        def _fmt_duration(m: Any) -> str:
            try:
                return f"{int(m)} min"
            except (TypeError, ValueError):
                return "—"

        def _fmt_date(d: str) -> str:
            try:
                return datetime.strptime(d, "%Y-%m-%d").strftime("%b %d, %Y")
            except (ValueError, AttributeError):
                return d or "—"

        self._meta_labels["chip"].setText(e.get("chip_serial") or "—")
        self._meta_labels["duration"].setText(_fmt_duration(e.get("duration_min")))
        self._meta_labels["cycles"].setText(str(e.get("cycle_count") or "—"))
        self._meta_labels["user"].setText(e.get("user") or "—")
        self._meta_labels["date"].setText(_fmt_date(e.get("date", "")))
        self._meta_labels["hardware"].setText(e.get("hardware_model") or "—")

        # Notes
        self._notes_edit.setPlainText(e.get("notes") or "")

        # Action buttons
        self._load_btn.setEnabled(not row.is_stale)
        self._open_btn.setEnabled(not row.is_stale)

    def _clear_preview(self) -> None:
        self._preview_title.setText("Select an experiment")
        for lbl in self._meta_labels.values():
            lbl.setText("—")
        self._notes_edit.clear()
        self._load_btn.setEnabled(False)
        self._open_btn.setEnabled(False)

    def _on_load_in_edits_clicked(self) -> None:
        if self._selected_row and not self._selected_row.is_stale:
            self._load_in_edits(self._selected_row.abs_path)

    def _load_in_edits(self, path: Path) -> None:
        """Switch to Edits tab and load the file."""
        mw = self._main_window
        # Switch to Edits page (index 1)
        if hasattr(mw, 'navigation_presenter'):
            mw.navigation_presenter.switch_page(1)
        elif hasattr(mw, 'content_stack'):
            mw.content_stack.setCurrentIndex(1)
        # Load the file
        if hasattr(mw, 'edits_tab') and hasattr(mw.edits_tab, '_load_data_from_path'):
            mw.edits_tab._load_data_from_path(path)
        elif hasattr(mw, '_load_data_from_excel_internal'):
            mw._load_data_from_excel_internal(str(path))

    def _on_open_excel_clicked(self) -> None:
        if self._selected_row and not self._selected_row.is_stale:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._selected_row.abs_path)))

    # ── New 2b ELN methods ─────────────────────────────────────────────────────

    def _on_notes_changed(self) -> None:
        """Debounce notes auto-save. Suppressed while populating."""
        if not self._notes_blocking:
            self._notes_save_timer.start()

    def _save_notes(self) -> None:
        if not self._current_entry_id:
            return
        from affilabs.services.experiment_index import ExperimentIndex
        try:
            ExperimentIndex().update_notes(self._current_entry_id, self._notes_edit.toPlainText())
        except Exception:
            pass

    def _on_rating_changed(self, rating: int) -> None:
        if not self._current_entry_id:
            return
        from affilabs.services.experiment_index import ExperimentIndex
        try:
            ExperimentIndex().set_rating(self._current_entry_id, rating)
        except Exception:
            pass
        # Update filter counts (rating may move entry to/from Needs Repeat)
        self._update_filter_counts()

    def _refresh_tags_panel(self, tags: list[str]) -> None:
        """Rebuild tag pill chips in the right panel."""
        # Remove all existing pill widgets (keep add_tag_btn and stretch)
        while self._tags_layout.count():
            item = self._tags_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for tag in tags:
            pill = self._make_tag_pill(tag)
            self._tags_layout.addWidget(pill)

        self._tags_layout.addWidget(self._add_tag_btn)
        self._tags_layout.addStretch()

    def _make_tag_pill(self, tag: str) -> QFrame:
        pill = QFrame()
        pill.setFixedHeight(24)
        pill.setStyleSheet(
            f"QFrame {{ background: rgba(0,122,255,0.10); border-radius: 12px; }}"
        )
        row = QHBoxLayout(pill)
        row.setContentsMargins(8, 0, 4, 0)
        row.setSpacing(2)
        tag_lbl = QLabel(f"#{tag}")
        tag_lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 500; color: {_ACCENT}; "
            f"font-family: {Fonts.SYSTEM}; background: transparent;"
        )
        row.addWidget(tag_lbl)
        rm_btn = QPushButton("\u00d7")  # ×
        rm_btn.setFixedSize(14, 14)
        rm_btn.setFlat(True)
        rm_btn.setCursor(Qt.PointingHandCursor)
        rm_btn.setStyleSheet(
            f"QPushButton {{ font-size: 11px; color: {_ACCENT}; background: transparent; "
            f"border: none; padding: 0; }}"
            f"QPushButton:hover {{ color: #FF3B30; }}"
        )
        rm_btn.clicked.connect(lambda checked, t=tag: self._on_remove_tag(t))
        row.addWidget(rm_btn)
        return pill

    def _on_add_tag(self) -> None:
        """Show an inline QLineEdit in the tag area for typing a new tag."""
        if not self._current_entry_id:
            return

        # Replace add_tag_btn temporarily with an inline editor
        self._add_tag_btn.hide()
        inp = QLineEdit()
        inp.setFixedHeight(24)
        inp.setFixedWidth(90)
        inp.setPlaceholderText("tag name")
        inp.setStyleSheet(
            f"QLineEdit {{ background: {Colors.BACKGROUND_WHITE}; "
            f"border: 1px solid {_ACCENT}; border-radius: 12px; "
            f"font-size: 10px; font-family: {Fonts.SYSTEM}; padding: 0 6px; }}"
        )
        # Autocomplete from known tags
        try:
            from affilabs.services.experiment_index import ExperimentIndex
            known = list(ExperimentIndex().all_tags().keys())
        except Exception:
            known = []
        completer = QCompleter(known, inp)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        inp.setCompleter(completer)

        # Insert before the stretch at the end
        count = self._tags_layout.count()
        self._tags_layout.insertWidget(count - 1, inp)
        inp.setFocus()

        def _commit():
            text = inp.text().strip().lstrip("#")
            inp.deleteLater()
            self._add_tag_btn.show()
            if text and self._current_entry_id:
                self._on_add_tag_value(text)

        inp.returnPressed.connect(_commit)
        inp.editingFinished.connect(_commit)

    def _on_add_tag_value(self, tag: str) -> None:
        if not self._current_entry_id:
            return
        from affilabs.services.experiment_index import ExperimentIndex
        try:
            ExperimentIndex().add_tag(self._current_entry_id, tag)
        except Exception:
            return
        # Re-read tags from index and refresh panel
        if self._selected_row:
            updated = self._selected_row.entry
            updated.setdefault("tags", [])
            if tag not in updated["tags"]:
                updated["tags"].append(tag)
            self._refresh_tags_panel(updated["tags"])
        self._update_filter_counts()

    def _on_remove_tag(self, tag: str) -> None:
        if not self._current_entry_id:
            return
        from affilabs.services.experiment_index import ExperimentIndex
        try:
            ExperimentIndex().remove_tag(self._current_entry_id, tag)
        except Exception:
            return
        if self._selected_row:
            tags = self._selected_row.entry.get("tags") or []
            if tag in tags:
                tags.remove(tag)
            self._refresh_tags_panel(tags)
        self._update_filter_counts()

    def _on_preview_ready(self, entry_id: str, data: object) -> None:
        """Plot sensorgram data received from PreviewWorker."""
        if not _HAS_PG or self._preview_plot is None:
            return
        if entry_id != self._current_entry_id:
            return  # selection changed before worker finished
        self._preview_plot.clear()
        if data is None:
            return
        ch_colors = {"a": "#007AFF", "b": "#34C759", "c": "#FF9500", "d": "#FF3B30"}
        times = data.get("times")
        for ch, wls in data.get("channels", {}).items():
            color = ch_colors.get(ch, "#888")
            if times is not None and len(times):
                xs = times[:len(wls)]
            else:
                xs = list(range(len(wls)))
            self._preview_plot.plot(xs, wls, pen=pg.mkPen(color, width=1.5))

    def _on_preview_error(self, entry_id: str, msg: str) -> None:
        # Silently ignore — preview is best-effort
        pass

    # ── Public API ─────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload from ExperimentIndex — call after recording stops."""
        prev_id = self._selected_row.entry.get("id") if self._selected_row else None
        self._selected_row = None
        self._load_entries()
        # Restore selection if still present
        if prev_id:
            for row in self._all_rows:
                if row.entry.get("id") == prev_id:
                    self._on_row_clicked(row)
                    break

    def switch_to_entry(self, entry_id: str) -> None:
        """Select the row with the given entry_id (for future wiring)."""
        for row in self._all_rows:
            if row.entry.get("id") == entry_id:
                self._on_row_clicked(row)
                self._scroll.ensureWidgetVisible(row)
                break

    def on_recording_started(self, filename: str) -> None:
        """Called at recording_started signal. Stores in-progress filename."""
        self._active_recording_filename = filename

    def on_recording_stopped(self) -> None:
        """Called at recording_stopped signal. Refreshes list."""
        self._active_recording_filename = None
        self.refresh()
