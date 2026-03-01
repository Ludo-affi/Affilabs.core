"""AccessibilityPanel — inline visual accessibility sidebar opened from the icon rail.

Fixed-width (380 px) panel injected into the main horizontal layout immediately to
the right of the icon rail. Visibility is toggled by the icon rail accessibility button.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (

    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

_FONT = "-apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif"

# ── Colour palettes ────────────────────────────────────────────────────────────
# Each entry: (id, display_name, description, [A, B, C, D] hex colours)
PALETTES: list[tuple[str, str, str, list[str]]] = [
    (
        "default",
        "Default",
        "Standard high-contrast",
        ["#1D1D1F", "#FF3B30", "#007AFF", "#34C759"],
    ),
    (
        "puor",
        "PuOr (CB-safe)",
        "Original colorblind palette — orange & purple divergent",
        ["#E66101", "#FDB863", "#B2ABD2", "#5E3C99"],
    ),
    (
        "wong",
        "Wong (CB-safe)",
        "Optimised for deuteranopia & protanopia",
        ["#E69F00", "#56B4E9", "#009E73", "#CC79A7"],
    ),
    (
        "tol",
        "Tol Bright (CB-safe)",
        "Paul Tol's bright scheme — safe for all types",
        ["#4477AA", "#EE6677", "#228833", "#CCBB44"],
    ),
    (
        "okabe",
        "Okabe-Ito (CB-safe)",
        "Widely recommended for colourblind readers",
        ["#0072B2", "#D55E00", "#F0E442", "#000000"],
    ),
    (
        "ibm",
        "IBM (CB-safe)",
        "IBM Design Language palette",
        ["#648FFF", "#785EF0", "#DC267F", "#FE6100"],
    ),
    (
        "pastel",
        "Pastel",
        "Softer tones for low-glare displays",
        ["#6BAED6", "#FC8D59", "#78C679", "#9E9AC8"],
    ),
]

# ── Line styles ────────────────────────────────────────────────────────────────
LINE_STYLES: list[tuple[str, str, Qt.PenStyle]] = [
    ("solid",  "Solid",  Qt.PenStyle.SolidLine),
    ("dashed", "Dashed", Qt.PenStyle.DashLine),
    ("dotted", "Dotted", Qt.PenStyle.DotLine),
]


def _swatch_pixmap(colors: list[str], size: int = 18, gap: int = 3) -> QPixmap:
    """Render 4 coloured squares in a row as a QPixmap."""
    total_w = size * 4 + gap * 3
    px = QPixmap(total_w, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for i, hex_color in enumerate(colors):
        x = i * (size + gap)
        p.setBrush(QColor(hex_color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(x, 0, size, size, 3, 3)
    p.end()
    return px


def _line_preview_pixmap(style: Qt.PenStyle, color: str = "#1D1D1F",
                         w: int = 72, h: int = 16) -> QPixmap:
    """Render a short line with the given pen style."""
    from PySide6.QtGui import QPen
    px = QPixmap(w, h)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    pen = QPen(QColor(color), 2, style)
    p.setPen(pen)
    p.drawLine(0, h // 2, w, h // 2)
    p.end()
    return px


class AccessibilityPanel(QFrame):
    """Fixed-width sidebar panel for visual accessibility settings."""

    palette_changed = Signal(str, list)   # (palette_id, [hex_A, hex_B, hex_C, hex_D])
    line_style_changed = Signal(str, object)  # (style_id, Qt.PenStyle)
    dark_mode_changed = Signal(bool)       # True = dark active cycle, False = light
    large_text_changed = Signal(bool)      # True = Large Text (120%), False = Normal

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(380)
        self.setObjectName("AccessibilityPanel")
        self.setStyleSheet("""
            QFrame#AccessibilityPanel {
                background: #FFFFFF;
                border-right: 1px solid #E5E5EA;
            }
        """)

        self._sidebar = None
        self._active_palette_id = "default"
        self._active_line_style_id = "solid"
        self._dark_mode = False
        try:
            from affilabs.ui_styles import FontScale
            self._large_text: bool = FontScale.is_large()
        except Exception:
            self._large_text = False
        self._palette_btns: dict[str, QPushButton] = {}
        self._line_btns: dict[str, QPushButton] = {}

        # ── Scroll wrapper ─────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }
            QScrollBar::handle:vertical {
                background: rgba(0,0,0,0.15); border-radius: 3px; min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        content = QWidget()
        content.setStyleSheet("background: #FFFFFF;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # ── Header ─────────────────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        header_title = QLabel("ACCESSIBILITY")
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

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("border: none; background: #E5E5EA; max-height: 1px;")
        layout.addWidget(div)

        # ── Saved-per-user notice ──────────────────────────────────────────────
        self._saved_note = QLabel("💾  Preferences saved to your profile.")
        self._saved_note.setWordWrap(True)
        self._saved_note.setStyleSheet(
            f"font-size: 11px; color: #6E6E73; font-style: italic;"
            f" background: rgba(0,122,255,0.05); border-radius: 7px;"
            f" padding: 7px 10px; font-family: {_FONT};"
        )
        layout.addWidget(self._saved_note)

        # ── Colour Palette section ─────────────────────────────────────────────
        layout.addWidget(self._section_label("Colour Palette"))
        layout.addWidget(self._section_hint(
            "Select a palette for channels A · B · C · D"
        ))

        for palette_id, name, desc, colors in PALETTES:
            btn = self._palette_card(palette_id, name, desc, colors)
            self._palette_btns[palette_id] = btn
            layout.addWidget(btn)

        self._refresh_palette_selection()

        # Divider
        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.HLine)
        div2.setStyleSheet("border: none; background: #E5E5EA; max-height: 1px;")
        layout.addWidget(div2)

        # ── Line Style section ─────────────────────────────────────────────────
        layout.addWidget(self._section_label("Line Style"))
        layout.addWidget(self._section_hint("Applied to all sensorgram curves"))

        line_row = QHBoxLayout()
        line_row.setSpacing(8)
        for style_id, label, pen_style in LINE_STYLES:
            btn = self._line_style_card(style_id, label, pen_style)
            self._line_btns[style_id] = btn
            line_row.addWidget(btn)
        layout.addLayout(line_row)

        self._refresh_line_selection()

        # Divider
        div3 = QFrame()
        div3.setFrameShape(QFrame.Shape.HLine)
        div3.setStyleSheet("border: none; background: #E5E5EA; max-height: 1px;")
        layout.addWidget(div3)

        # ── Active Cycle Dark Mode section ─────────────────────────────────────
        layout.addWidget(self._section_label("Appearance"))

        dark_row = QHBoxLayout()
        dark_row.setSpacing(10)

        dark_label_col = QVBoxLayout()
        dark_label_col.setSpacing(1)
        dark_title = QLabel("Active Cycle Dark Mode")
        dark_title.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: #1D1D1F;"
            f" background: transparent; font-family: {_FONT};"
        )
        dark_desc = QLabel("Black background with neon channel colours")
        dark_desc.setStyleSheet(
            f"font-size: 10px; color: #86868B; background: transparent; font-family: {_FONT};"
        )
        dark_label_col.addWidget(dark_title)
        dark_label_col.addWidget(dark_desc)
        dark_row.addLayout(dark_label_col)
        dark_row.addStretch()

        self._dark_toggle = QPushButton("○")
        self._dark_toggle.setCheckable(True)
        self._dark_toggle.setFixedSize(44, 26)
        self._dark_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dark_toggle.setStyleSheet(self._toggle_style(False))
        self._dark_toggle.clicked.connect(self._on_dark_mode_clicked)
        dark_row.addWidget(self._dark_toggle)

        layout.addLayout(dark_row)

        # ── Large Text section ─────────────────────────────────────────────────
        font_div = QFrame()
        font_div.setFrameShape(QFrame.Shape.HLine)
        font_div.setStyleSheet("border: none; background: #E5E5EA; max-height: 1px;")
        layout.addWidget(font_div)

        font_row = QHBoxLayout()
        font_row.setSpacing(10)

        font_label_col = QVBoxLayout()
        font_label_col.setSpacing(1)
        font_title = QLabel("Large Text")
        font_title.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: #1D1D1F;"
            f" background: transparent; font-family: {_FONT};"
        )
        font_desc = QLabel("120% font size — takes effect on restart")
        font_desc.setStyleSheet(
            f"font-size: 10px; color: #86868B; background: transparent; font-family: {_FONT};"
        )
        font_label_col.addWidget(font_title)
        font_label_col.addWidget(font_desc)
        font_row.addLayout(font_label_col)
        font_row.addStretch()

        self._large_text_toggle = QPushButton("●" if self._large_text else "○")
        self._large_text_toggle.setCheckable(True)
        self._large_text_toggle.setChecked(self._large_text)
        self._large_text_toggle.setFixedSize(44, 26)
        self._large_text_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._large_text_toggle.setStyleSheet(self._toggle_style(self._large_text))
        self._large_text_toggle.clicked.connect(self._on_large_text_clicked)
        font_row.addWidget(self._large_text_toggle)

        layout.addLayout(font_row)

        layout.addStretch()
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        # Legacy compat — settings sidebar used to have this checkbox
        self.colorblind_check = _DummyCheck()

    # ──────────────────────────────────────────────────────────────────────────
    # Widget builders
    # ──────────────────────────────────────────────────────────────────────────

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: #86868B;"
            f" background: transparent; font-family: {_FONT};"
        )
        return lbl

    def _section_hint(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-size: 11px; color: #AEAEB2; font-style: italic;"
            f" background: transparent; font-family: {_FONT};"
        )
        return lbl

    def _palette_card(self, palette_id: str, name: str,
                      desc: str, colors: list[str]) -> QPushButton:
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setFixedHeight(52)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        # Build layout inside button via a child widget overlay
        inner = QWidget(btn)
        inner.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row = QHBoxLayout(inner)
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(10)

        # Colour swatches
        swatch_lbl = QLabel()
        swatch_lbl.setPixmap(_swatch_pixmap(colors, size=16, gap=3))
        swatch_lbl.setFixedSize(16 * 4 + 3 * 3, 16)
        swatch_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row.addWidget(swatch_lbl)

        # Text
        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: #1D1D1F;"
            f" background: transparent; font-family: {_FONT};"
        )
        name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet(
            f"font-size: 10px; color: #86868B; background: transparent; font-family: {_FONT};"
        )
        desc_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text_col.addWidget(name_lbl)
        text_col.addWidget(desc_lbl)
        row.addLayout(text_col)
        row.addStretch()

        inner.setGeometry(0, 0, 340, 52)

        btn.setStyleSheet(self._card_style(active=False))
        btn.clicked.connect(lambda: self._on_palette_selected(palette_id, colors))
        return btn

    def _line_style_card(self, style_id: str, label: str,
                         pen_style: Qt.PenStyle) -> QPushButton:
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setFixedSize(100, 56)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        inner = QWidget(btn)
        inner.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        col = QVBoxLayout(inner)
        col.setContentsMargins(8, 6, 8, 6)
        col.setSpacing(4)
        col.setAlignment(Qt.AlignmentFlag.AlignCenter)

        preview_lbl = QLabel()
        preview_lbl.setPixmap(_line_preview_pixmap(pen_style, "#1D1D1F", 72, 14))
        preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        name_lbl = QLabel(label)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setStyleSheet(
            f"font-size: 11px; color: #1D1D1F; background: transparent; font-family: {_FONT};"
        )
        name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        col.addWidget(preview_lbl)
        col.addWidget(name_lbl)
        inner.setGeometry(0, 0, 100, 56)

        btn.setStyleSheet(self._card_style(active=False))
        btn.clicked.connect(lambda: self._on_line_style_selected(style_id, pen_style))
        return btn

    @staticmethod
    def _card_style(active: bool) -> str:
        if active:
            return (
                "QPushButton { background: rgba(0,122,255,0.08);"
                "  border: 1.5px solid #007AFF; border-radius: 8px; }"
                "QPushButton:hover { background: rgba(0,122,255,0.12); }"
            )
        return (
            "QPushButton { background: #F5F5F7;"
            "  border: 1.5px solid transparent; border-radius: 8px; }"
            "QPushButton:hover { background: #EBEBED; }"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def set_sidebar(self, sidebar) -> None:
        self._sidebar = sidebar

    def _refresh_saved_note(self) -> None:
        """Update the per-user note to show the active username."""
        try:
            mgr = getattr(getattr(self, '_sidebar', None), 'user_profile_manager', None)
            user = mgr.get_current_user() if mgr else None
        except Exception:
            user = None
        if user:
            self._saved_note.setText(f"💾  Saved to {user}'s profile — colour and font size are personal.")
        else:
            self._saved_note.setText("💾  Colour and font size preferences are saved per user profile.")

    def toggle(self) -> bool:
        if self.isVisible():
            self.hide()
            return False
        self._refresh_saved_note()
        self.show()
        return True

    def get_active_palette(self) -> list[str]:
        for pid, _, _, colors in PALETTES:
            if pid == self._active_palette_id:
                return colors
        return PALETTES[0][3]

    def get_active_line_style(self) -> Qt.PenStyle:
        for sid, _, pen_style in LINE_STYLES:
            if sid == self._active_line_style_id:
                return pen_style
        return Qt.PenStyle.SolidLine

    def is_dark_mode(self) -> bool:
        return self._dark_mode

    def is_large_text(self) -> bool:
        return self._large_text

    # ──────────────────────────────────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _toggle_style(active: bool) -> str:
        if active:
            return (
                "QPushButton { background: #007AFF; color: #FFFFFF; border: none;"
                "  border-radius: 13px; font-size: 16px; font-weight: bold; }"
                "QPushButton:hover { background: #0A84FF; }"
            )
        return (
            "QPushButton { background: #E5E5EA; color: #86868B; border: none;"
            "  border-radius: 13px; font-size: 16px; }"
            "QPushButton:hover { background: #D5D5D7; }"
        )

    def _on_dark_mode_clicked(self) -> None:
        self._dark_mode = self._dark_toggle.isChecked()
        self._dark_toggle.setText("●" if self._dark_mode else "○")
        self._dark_toggle.setStyleSheet(self._toggle_style(self._dark_mode))
        self.dark_mode_changed.emit(self._dark_mode)

    def _on_large_text_clicked(self) -> None:
        self._large_text = self._large_text_toggle.isChecked()
        self._large_text_toggle.setText("●" if self._large_text else "○")
        self._large_text_toggle.setStyleSheet(self._toggle_style(self._large_text))
        try:
            from affilabs.ui_styles import FontScale
            FontScale.save(self._large_text)
        except Exception:
            pass
        self.large_text_changed.emit(self._large_text)

    def _on_palette_selected(self, palette_id: str, colors: list[str]) -> None:
        self._active_palette_id = palette_id
        self._refresh_palette_selection()
        self.palette_changed.emit(palette_id, colors)

    def _on_line_style_selected(self, style_id: str, pen_style: Qt.PenStyle) -> None:
        self._active_line_style_id = style_id
        self._refresh_line_selection()
        self.line_style_changed.emit(style_id, pen_style)

    def _refresh_palette_selection(self) -> None:
        for pid, btn in self._palette_btns.items():
            active = (pid == self._active_palette_id)
            btn.setChecked(active)
            btn.setStyleSheet(self._card_style(active))

    def _refresh_line_selection(self) -> None:
        for sid, btn in self._line_btns.items():
            active = (sid == self._active_line_style_id)
            btn.setChecked(active)
            btn.setStyleSheet(self._card_style(active))


class _DummySignal:
    """No-op signal stub for _DummyCheck.toggled."""
    def connect(self, *args) -> None:
        pass
    def disconnect(self, *args) -> None:
        pass
    def emit(self, *args) -> None:
        pass


class _DummyCheck:
    """Backwards-compat shim — replaces sidebar.colorblind_check."""
    def __init__(self):
        self.toggled = _DummySignal()
        self.stateChanged = _DummySignal()
    def isChecked(self) -> bool:
        return False
    def setChecked(self, _: bool) -> None:
        pass
    def blockSignals(self, _: bool) -> None:
        pass
