"""
LicenseActivationDialog — one-time key entry dialog.

Shown:
  (a) At first launch when no valid license.json is found
  (b) When the user clicks "Enter License Key" in the demo banner
  (c) When the user clicks the power button in demo mode

Visual style mirrors startup_calib_dialog.py:
  frameless, blue border, drop shadow, Apple-style button colours.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from affilabs.services.license_service import LicenseService


class LicenseActivationDialog(QDialog):
    """Frameless modal dialog for one-time license key activation."""

    license_activated = Signal()  # emitted after successful activation

    def __init__(
        self,
        license_service: LicenseService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._svc = license_service

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        self.setFixedWidth(480)
        self.setStyleSheet(
            "QDialog {"
            "  background: #FFFFFF;"
            "  border: 2px solid #007AFF;"
            "  border-radius: 12px;"
            "}"
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        self.setGraphicsEffect(shadow)

        self._build_ui()
        self._connect()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        # Title
        title = QLabel("Activate Affilabs.core")
        title.setStyleSheet(
            "font-size: 17px; font-weight: 700; color: #1D1D1F;"
            " border: none; background: transparent;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Subtitle
        sub = QLabel(
            "Enter the license key from your purchase confirmation.\n"
            "Format: AFFI-XXXX-XXXX-XXXX"
        )
        sub.setStyleSheet(
            "font-size: 12px; color: #86868B; border: none; background: transparent;"
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        layout.addWidget(sub)

        layout.addSpacing(4)

        # Key entry field
        self._key_field = QLineEdit()
        self._key_field.setPlaceholderText("AFFI-XXXX-XXXX-XXXX")
        self._key_field.setMaxLength(19)  # AFFI-1234-5678-ABCD
        self._key_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._key_field.setStyleSheet(
            "QLineEdit {"
            "  font-size: 16px; font-weight: 600; letter-spacing: 2px;"
            "  padding: 10px 14px;"
            "  border: 2px solid #D1D1D6; border-radius: 10px;"
            "  color: #1D1D1F; background: #F5F5F7;"
            "}"
            "QLineEdit:focus { border-color: #007AFF; background: #FFFFFF; }"
        )
        layout.addWidget(self._key_field)

        # Error label — hidden until validation fails
        self._error_label = QLabel("")
        self._error_label.setStyleSheet(
            "font-size: 12px; color: #FF3B30; border: none; background: transparent;"
        )
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        layout.addSpacing(4)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._demo_btn = QPushButton("Continue in Demo")
        self._demo_btn.setFixedHeight(36)
        self._demo_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent; color: #636366;"
            "  border: 1.5px solid #D1D1D6; border-radius: 10px;"
            "  font-size: 13px; font-weight: 500;"
            "}"
            "QPushButton:hover { background: #F5F5F7; }"
        )
        btn_row.addWidget(self._demo_btn, 1)

        self._activate_btn = QPushButton("Activate")
        self._activate_btn.setFixedHeight(36)
        self._activate_btn.setEnabled(False)
        self._activate_btn.setDefault(True)
        self._activate_btn.setStyleSheet(
            "QPushButton {"
            "  background: #007AFF; color: white;"
            "  border: none; border-radius: 10px;"
            "  font-size: 13px; font-weight: 600;"
            "}"
            "QPushButton:hover { background: #0062CC; }"
            "QPushButton:disabled { background: #E5E5EA; color: #AEAEB2; }"
        )
        btn_row.addWidget(self._activate_btn, 1)

        layout.addLayout(btn_row)

        # Footer note
        note = QLabel(
            "Demo mode: hardware connection disabled, demo dataset pre-loaded."
        )
        note.setStyleSheet(
            "font-size: 11px; color: #AEAEB2; border: none; background: transparent;"
        )
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setWordWrap(True)
        layout.addWidget(note)

    def _connect(self) -> None:
        self._key_field.textChanged.connect(self._on_text_changed)
        self._activate_btn.clicked.connect(self._on_activate)
        self._demo_btn.clicked.connect(self.reject)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_text_changed(self, text: str) -> None:
        """Auto-format input as AFFI-XXXX-XXXX-XXXX while typing."""
        # Strip everything except alphanumerics, uppercase
        clean = "".join(c for c in text.upper() if c.isalnum())
        # Drop the AFFI prefix if the user typed it (we always prepend it)
        if clean.startswith("AFFI"):
            clean = clean[4:]
        clean = clean[:12]

        # Rebuild with dashes
        parts = [clean[i : i + 4] for i in range(0, len(clean), 4)]
        formatted = "AFFI-" + "-".join(p for p in parts if p) if clean else ""

        self._key_field.blockSignals(True)
        cursor = self._key_field.cursorPosition()
        self._key_field.setText(formatted)
        self._key_field.setCursorPosition(min(cursor, len(formatted)))
        self._key_field.blockSignals(False)

        # Reset error state on any edit
        self._error_label.setVisible(False)
        self._key_field.setStyleSheet(
            self._key_field.styleSheet().replace("#FF3B30", "#D1D1D6")
        )

        self._activate_btn.setEnabled(len(clean) == 12)

    def _on_activate(self) -> None:
        key = self._key_field.text().strip()
        ok, error = self._svc.activate(key)
        if ok:
            self.license_activated.emit()
            self.accept()
        else:
            self._error_label.setText(error)
            self._error_label.setVisible(True)
            # Highlight field border red
            self._key_field.setStyleSheet(
                self._key_field.styleSheet().replace("#D1D1D6", "#FF3B30")
            )
