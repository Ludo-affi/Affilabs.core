"""Queue Preset Dialog.

Browse, load, delete, import, and export queue presets (complete cycle sequences).
Provides search functionality and detailed preview of preset contents.

Author: GitHub Copilot
Date: 2026-01-31
"""

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QMessageBox,
)

from affilabs.services.queue_preset_storage import QueuePreset, QueuePresetStorage

logger = logging.getLogger(__name__)


class QueuePresetDialog(QDialog):
    """Queue preset browser dialog.

    Features:
        - Search bar for filtering presets
        - List of available presets (sorted alphabetically)
        - Preview pane showing preset details
        - Load, Delete, Import, Export actions

    Signals:
        preset_selected: Emitted when user loads a preset (passes QueuePreset)
    """

    preset_selected = Signal(QueuePreset)

    def __init__(self, storage: QueuePresetStorage, parent: QWidget = None):
        """Initialize preset dialog.

        Args:
            storage: QueuePresetStorage instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.storage = storage
        self.current_preset = None

        self.setWindowTitle("Queue Presets")
        self.setMinimumSize(700, 500)
        self.setStyleSheet("""
            QDialog {
                background: white;
            }
            QLineEdit, QTextEdit, QListWidget {
                background: white;
                border: 1px solid #D1D1D6;
                border-radius: 6px;
                padding: 6px;
                font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;
                font-size: 13px;
            }
            QLineEdit:focus, QTextEdit:focus, QListWidget:focus {
                border: 1px solid #007AFF;
            }
            QPushButton {
                background: white;
                border: 1px solid #D1D1D6;
                border-radius: 6px;
                padding: 6px 12px;
                font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;
                font-size: 13px;
                min-height: 24px;
            }
            QPushButton:hover {
                background: #F2F2F7;
                border: 1px solid #C7C7CC;
            }
            QPushButton:pressed {
                background: #E5E5EA;
            }
            QPushButton#loadBtn {
                background: #007AFF;
                color: white;
                border: 1px solid #007AFF;
            }
            QPushButton#loadBtn:hover {
                background: #0051D5;
            }
            QPushButton#deleteBtn {
                border: 1px solid #FF3B30;
                color: #FF3B30;
            }
            QPushButton#deleteBtn:hover {
                background: #FFF5F5;
            }
            QLabel {
                font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;
                font-size: 13px;
                color: #1C1C1E;
            }
        """)

        self._build_ui()
        self._load_presets()

    def _build_ui(self):
        """Build dialog UI layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        title_label = QLabel("Queue Presets")
        title_label.setStyleSheet("font-size: 18px; font-weight: 600; margin-bottom: 4px;")
        layout.addWidget(title_label)

        # Search bar
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by name or description...")
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Main content area (list + preview)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)

        # Left: Preset list
        list_container = QVBoxLayout()
        list_label = QLabel("Available Presets")
        list_label.setStyleSheet("font-weight: 600;")
        list_container.addWidget(list_label)

        self.preset_list = QListWidget()
        self.preset_list.setMinimumWidth(250)
        self.preset_list.currentItemChanged.connect(self._on_selection_changed)
        list_container.addWidget(self.preset_list)

        content_layout.addLayout(list_container)

        # Right: Preview pane
        preview_container = QVBoxLayout()
        preview_label = QLabel("Preview")
        preview_label.setStyleSheet("font-weight: 600;")
        preview_container.addWidget(preview_label)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("Select a preset to view details...")
        preview_container.addWidget(self.preview_text)

        content_layout.addLayout(preview_container)

        layout.addLayout(content_layout)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        self.import_btn = QPushButton("📥 Import")
        self.import_btn.setToolTip("Import preset from JSON file")
        self.import_btn.clicked.connect(self._on_import_clicked)

        self.export_btn = QPushButton("📤 Export")
        self.export_btn.setToolTip("Export selected preset to JSON file")
        self.export_btn.clicked.connect(self._on_export_clicked)
        self.export_btn.setEnabled(False)

        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.setObjectName("deleteBtn")
        self.delete_btn.setToolTip("Delete selected preset")
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        self.delete_btn.setEnabled(False)

        button_layout.addWidget(self.import_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.delete_btn)
        button_layout.addStretch()

        self.load_btn = QPushButton("✓ Load Preset")
        self.load_btn.setObjectName("loadBtn")
        self.load_btn.setToolTip("Load selected preset into queue")
        self.load_btn.clicked.connect(self._on_load_clicked)
        self.load_btn.setEnabled(False)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(self.load_btn)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _load_presets(self, filter_query: str = ""):
        """Load presets into list widget.

        Args:
            filter_query: Optional search query to filter presets
        """
        self.preset_list.clear()

        # Get presets (filtered or all)
        if filter_query:
            presets = self.storage.search_presets(filter_query)
        else:
            presets = self.storage.get_all_presets()

        # Add to list
        for preset in presets:
            item = QListWidgetItem(f"{preset.name}")
            item.setData(Qt.UserRole, preset.preset_id)

            # Add tooltip with summary
            tooltip = f"{preset.name}\n{preset.get_summary()}\n{preset.cycle_count} cycles, {preset.total_duration_minutes:.1f} min total"
            item.setToolTip(tooltip)

            self.preset_list.addItem(item)

        logger.debug(f"Loaded {len(presets)} presets into list")

    def _on_search_changed(self, text: str):
        """Handle search text change.

        Args:
            text: Search query
        """
        self._load_presets(filter_query=text)

    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        """Handle preset selection change.

        Args:
            current: Currently selected item
            previous: Previously selected item
        """
        if not current:
            self.preview_text.clear()
            self.current_preset = None
            self.export_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.load_btn.setEnabled(False)
            return

        # Load preset details
        preset_id = current.data(Qt.UserRole)
        preset = self.storage.load_preset(preset_id)

        if preset:
            self.current_preset = preset
            self._update_preview(preset)
            self.export_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
            self.load_btn.setEnabled(True)

    def _update_preview(self, preset: QueuePreset):
        """Update preview pane with preset details.

        Args:
            preset: Preset to preview
        """
        # Build preview text
        preview = f"<b>Name:</b> {preset.name}<br>"

        if preset.description:
            preview += f"<b>Description:</b> {preset.description}<br>"

        preview += f"<b>Cycles:</b> {preset.cycle_count}<br>"
        preview += f"<b>Total Duration:</b> {preset.total_duration_minutes:.1f} minutes<br>"
        preview += f"<b>Summary:</b> {preset.get_summary()}<br><br>"

        # Add cycle details
        preview += "<b>Cycle Sequence:</b><br>"
        for i, cycle in enumerate(preset.cycles, 1):
            concentrations = ", ".join(
                f"{ch}: {val}{cycle.units}"
                for ch, val in sorted(cycle.concentrations.items())
            ) if cycle.concentrations else "None"

            preview += f"  {i}. <b>{cycle.type}</b> - {cycle.length_minutes:.1f}min"
            if concentrations != "None":
                preview += f" ({concentrations})"
            if cycle.note:
                note_short = cycle.note[:50] + "..." if len(cycle.note) > 50 else cycle.note
                preview += f"<br>     <i>{note_short}</i>"
            preview += "<br>"

        preview += f"<br><b>Created:</b> {preset.created_at}<br>"
        preview += f"<b>Modified:</b> {preset.modified_at}"

        self.preview_text.setHtml(preview)

    def _on_load_clicked(self):
        """Handle load button click."""
        if self.current_preset:
            self.preset_selected.emit(self.current_preset)
            self.accept()

    def _on_delete_clicked(self):
        """Handle delete button click."""
        if not self.current_preset:
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete preset '{self.current_preset.name}'?\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            success = self.storage.delete_preset(self.current_preset.preset_id)

            if success:
                logger.info(f"Deleted preset '{self.current_preset.name}'")
                QMessageBox.information(
                    self,
                    "Deleted",
                    f"Preset '{self.current_preset.name}' deleted successfully.",
                )
                # Reload list
                self._load_presets(self.search_input.text())
            else:
                QMessageBox.warning(
                    self,
                    "Delete Failed",
                    f"Failed to delete preset '{self.current_preset.name}'.",
                )

    def _on_import_clicked(self):
        """Handle import button click."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Queue Preset",
            "",
            "JSON Files (*.json);;All Files (*.*)",
        )

        if file_path:
            preset_id = self.storage.import_preset(Path(file_path))

            if preset_id:
                QMessageBox.information(
                    self,
                    "Import Successful",
                    "Preset imported successfully!",
                )
                # Reload list
                self._load_presets(self.search_input.text())
            else:
                QMessageBox.warning(
                    self,
                    "Import Failed",
                    f"Failed to import preset from {file_path}",
                )

    def _on_export_clicked(self):
        """Handle export button click."""
        if not self.current_preset:
            return

        default_filename = f"{self.current_preset.name.replace(' ', '_')}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Queue Preset",
            default_filename,
            "JSON Files (*.json);;All Files (*.*)",
        )

        if file_path:
            success = self.storage.export_preset(
                self.current_preset.preset_id,
                Path(file_path),
            )

            if success:
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Preset exported to:\n{file_path}",
                )
            else:
                QMessageBox.warning(
                    self,
                    "Export Failed",
                    f"Failed to export preset to {file_path}",
                )
