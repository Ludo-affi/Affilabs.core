"""Update Available Dialog — Prompt user to install available update."""

import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QProgressBar, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont

from affilabs.services.update_manager import UpdateInfo, UpdateManager

logger = logging.getLogger(__name__)


class UpdateAvailableDialog(QDialog):
    """Dialog showing available update with release notes and options.

    Signals:
        update_applied: Emitted when update is successfully applied.
        update_skipped: Emitted when user skips the update.
    """

    update_applied = Signal()
    update_skipped = Signal()

    def __init__(self, update_info: UpdateInfo, update_mgr: UpdateManager, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.update_mgr = update_mgr
        self.setWindowTitle("Software Update Available")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        """Build the dialog layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header: "Update Available"
        header = QLabel("Software Update Available")
        header.setFont(QFont("SF Pro Display", 16, QFont.Weight.Bold))
        layout.addWidget(header)

        # Current → New version info
        info_text = f"Affilabs.core {self.update_info.version}"
        if self.update_info.release_date:
            info_text += f" — {self.update_info.release_date}"
        info_lbl = QLabel(info_text)
        info_lbl.setFont(QFont("Menlo", 11))
        info_lbl.setStyleSheet("color: #007AFF; background: transparent;")
        layout.addWidget(info_lbl)

        # Release notes / description
        notes_label = QLabel("Release Notes:")
        notes_label.setFont(QFont("SF Pro Text", 12, QFont.Weight.SemiBold))
        layout.addWidget(notes_label)

        notes_box = QTextEdit()
        notes_box.setMarkdown(self.update_info.release_notes[:2000])  # Truncate very long notes
        notes_box.setReadOnly(True)
        notes_box.setMaximumHeight(150)
        layout.addWidget(notes_box)

        # Update type indicator
        update_type = "Full Installer Update (new bundled files)" if self.update_info.is_major_update else "Quick Patch (drop-in exe)"
        type_lbl = QLabel(f"Update Type: {update_type}")
        type_lbl.setStyleSheet(
            "color: #8E8E93; background: transparent; font-size: 11px; font-style: italic;"
        )
        layout.addWidget(type_lbl)

        # Progress bar (hidden initially)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # Indeterminate
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # Status/error label
        self._status_lbl = QLabel()
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet("color: #FF3B30;")
        self._status_lbl.setVisible(False)
        layout.addWidget(self._status_lbl)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        self._skip_btn = QPushButton("Skip")
        self._skip_btn.setFixedWidth(100)
        self._skip_btn.clicked.connect(self.reject)
        button_layout.addWidget(self._skip_btn)

        button_layout.addStretch()

        self._update_btn = QPushButton("Update Now")
        self._update_btn.setFixedWidth(120)
        self._update_btn.setStyleSheet(
            "QPushButton { background: #007AFF; color: white; border: none; border-radius: 6px; font-weight: 600; padding: 8px; }"
            "QPushButton:hover { background: #0051CC; }"
            "QPushButton:pressed { background: #003399; }"
        )
        self._update_btn.clicked.connect(self._on_update_clicked)
        button_layout.addWidget(self._update_btn)

        layout.addLayout(button_layout)

    def _connect_signals(self) -> None:
        """Connect update manager signals."""
        self.update_mgr.update_error.connect(self._on_update_error)
        self.rejected.connect(lambda: self.update_skipped.emit())

    def _on_update_clicked(self) -> None:
        """Handle Update Now button click."""
        self._update_btn.setEnabled(False)
        self._skip_btn.setEnabled(False)
        self._progress.setVisible(True)

        # Download and apply in background
        import threading
        thread = threading.Thread(
            target=self._apply_update_thread, daemon=True
        )
        thread.start()

    def _apply_update_thread(self) -> None:
        """Background thread to download and apply the update."""
        try:
            use_installer = self.update_info.is_major_update
            success = self.update_mgr.download_and_apply_update(
                self.update_info,
                use_installer=use_installer,
            )

            if success:
                logger.info("Update applied successfully")
                self.update_applied.emit()
                self.accept()
            else:
                self._status_lbl.setText("Update failed. Please try again or download manually from GitHub.")
                self._status_lbl.setVisible(True)
                self._update_btn.setEnabled(True)
                self._skip_btn.setEnabled(True)
                self._progress.setVisible(False)

        except Exception as e:
            logger.error(f"Update thread error: {e}")
            self._on_update_error(str(e))

    def _on_update_error(self, error_msg: str) -> None:
        """Handle update error from update manager."""
        self._status_lbl.setText(f"Error: {error_msg}")
        self._status_lbl.setVisible(True)
        self._update_btn.setEnabled(True)
        self._skip_btn.setEnabled(True)
        self._progress.setVisible(False)
