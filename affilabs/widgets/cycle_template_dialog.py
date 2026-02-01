"""Cycle Template Manager Dialog - Browse, load, save, and manage templates.

ARCHITECTURE LAYER: UI Widget

This dialog provides:
- Template library with search/filter
- Preview of template details
- Load template into cycle builder
- Save current cycle as template
- Edit/delete existing templates
- Import/export templates

USAGE:
    # Open template manager
    dialog = CycleTemplateDialog(template_storage, parent)

    # User selects template
    if dialog.exec() == QDialog.DialogCode.Accepted:
        template = dialog.get_selected_template()
        if template:
            cycle = template.to_cycle()
"""

from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QTextEdit, QLineEdit,
    QMessageBox, QFileDialog, QGroupBox
)
from PySide6.QtCore import Qt, Signal

from affilabs.services.cycle_template_storage import CycleTemplateStorage, CycleTemplate
from affilabs.utils.logger import logger


class CycleTemplateDialog(QDialog):
    """Dialog for managing cycle templates.

    Signals:
        template_selected: User selected a template to load
    """

    template_selected = Signal(CycleTemplate)

    def __init__(self, storage: CycleTemplateStorage, parent=None):
        """Initialize template manager dialog.

        Args:
            storage: CycleTemplateStorage instance
            parent: Parent widget
        """
        super().__init__(parent)

        self.storage = storage
        self.selected_template: Optional[CycleTemplate] = None

        self._setup_ui()
        self._load_templates()

        logger.debug("CycleTemplateDialog initialized")

    def _setup_ui(self):
        """Create dialog UI."""
        self.setWindowTitle("Cycle Templates")
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Search bar
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name or type...")
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_input)

        layout.addLayout(search_layout)

        # Main content area
        content_layout = QHBoxLayout()

        # Left side: Template list
        list_group = QGroupBox("Templates")
        list_layout = QVBoxLayout(list_group)

        self.template_list = QListWidget()
        self.template_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.template_list.itemDoubleClicked.connect(self._on_load_clicked)
        list_layout.addWidget(self.template_list)

        content_layout.addWidget(list_group, stretch=1)

        # Right side: Template preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(200)
        preview_layout.addWidget(self.preview_text)

        content_layout.addWidget(preview_group, stretch=1)

        layout.addLayout(content_layout)

        # Action buttons
        button_layout = QHBoxLayout()

        # Import/Export buttons
        self.import_btn = QPushButton("📥 Import")
        self.import_btn.clicked.connect(self._on_import_clicked)
        button_layout.addWidget(self.import_btn)

        self.export_btn = QPushButton("📤 Export")
        self.export_btn.clicked.connect(self._on_export_clicked)
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)

        button_layout.addStretch()

        # Delete button
        self.delete_btn = QPushButton("🗑 Delete")
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        self.delete_btn.setEnabled(False)
        button_layout.addWidget(self.delete_btn)

        # Load button
        self.load_btn = QPushButton("✓ Load Template")
        self.load_btn.clicked.connect(self._on_load_clicked)
        self.load_btn.setEnabled(False)
        self.load_btn.setDefault(True)
        button_layout.addWidget(self.load_btn)

        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # Apply styling
        self.setStyleSheet("""
            QDialog {
                background: white;
            }
            QGroupBox {
                font-weight: 600;
                font-size: 13px;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QListWidget {
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 6px;
                background: white;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid rgba(0, 0, 0, 0.05);
            }
            QListWidget::item:selected {
                background: rgba(0, 122, 255, 0.1);
                color: #1D1D1F;
            }
            QTextEdit {
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 6px;
                background: #F5F5F7;
                font-size: 11px;
                font-family: 'Consolas', 'Monaco', monospace;
                padding: 8px;
            }
            QPushButton {
                background: white;
                color: #1D1D1F;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #F5F5F7;
                border-color: rgba(0, 0, 0, 0.15);
            }
            QPushButton:pressed {
                background: #E8E8ED;
            }
            QPushButton:disabled {
                background: #F5F5F7;
                color: #86868B;
                border-color: rgba(0, 0, 0, 0.05);
            }
            QPushButton:default {
                background: #007AFF;
                color: white;
                border-color: #007AFF;
            }
            QPushButton:default:hover {
                background: #0051D5;
                border-color: #0051D5;
            }
        """)

    def _load_templates(self):
        """Load all templates into list."""
        self.template_list.clear()
        templates = self.storage.get_all_templates()

        for template in templates:
            item = QListWidgetItem(f"{template.name}")
            item.setData(Qt.ItemDataRole.UserRole, template)
            self.template_list.addItem(item)

        if not templates:
            self.preview_text.setPlainText("No templates found.\n\nSave a cycle as a template to get started!")

    def _on_search_changed(self, text: str):
        """Filter templates based on search query."""
        if not text:
            self._load_templates()
            return

        self.template_list.clear()
        templates = self.storage.search_templates(text)

        for template in templates:
            item = QListWidgetItem(f"{template.name}")
            item.setData(Qt.ItemDataRole.UserRole, template)
            self.template_list.addItem(item)

        if not templates:
            self.preview_text.setPlainText(f"No templates match '{text}'")

    def _on_selection_changed(self):
        """Handle template selection."""
        selected_items = self.template_list.selectedItems()

        if not selected_items:
            self.load_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.export_btn.setEnabled(False)
            self.preview_text.clear()
            self.selected_template = None
            return

        # Get selected template
        item = selected_items[0]
        template = item.data(Qt.ItemDataRole.UserRole)
        self.selected_template = template

        # Enable buttons
        self.load_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

        # Show preview
        preview = f"""Template: {template.name}
Type: {template.cycle_type}
Duration: {template.length_minutes} minutes
Units: {template.units}

Concentrations:
{self._format_concentrations(template.concentrations)}

Notes:
{template.note or '(none)'}

Created: {template.created_at[:10]}
Modified: {template.modified_at[:10]}
"""
        self.preview_text.setPlainText(preview)

    def _format_concentrations(self, concentrations: dict) -> str:
        """Format concentrations for preview."""
        if not concentrations:
            return "  (none)"

        lines = []
        for channel, value in sorted(concentrations.items()):
            lines.append(f"  {channel.upper()}: {value}")

        return "\n".join(lines)

    def _on_load_clicked(self):
        """Load selected template."""
        if self.selected_template:
            self.template_selected.emit(self.selected_template)
            self.accept()

    def _on_delete_clicked(self):
        """Delete selected template."""
        if not self.selected_template:
            return

        reply = QMessageBox.question(
            self,
            "Delete Template",
            f"Delete template '{self.selected_template.name}'?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            success = self.storage.delete_template(self.selected_template.template_id)

            if success:
                self._load_templates()
                self.selected_template = None
                logger.info(f"Template deleted: {self.selected_template.name}")

    def _on_import_clicked(self):
        """Import template from file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Template",
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            template_id = self.storage.import_template(file_path)

            if template_id:
                self._load_templates()
                QMessageBox.information(
                    self,
                    "Success",
                    "Template imported successfully!"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    "Failed to import template.\n\nCheck file format and try again."
                )

    def _on_export_clicked(self):
        """Export selected template to file."""
        if not self.selected_template:
            return

        default_name = f"{self.selected_template.name.replace(' ', '_')}.json"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Template",
            default_name,
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            success = self.storage.export_template(
                self.selected_template.template_id,
                file_path
            )

            if success:
                QMessageBox.information(
                    self,
                    "Success",
                    f"Template exported to:\n{file_path}"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    "Failed to export template."
                )

    def get_selected_template(self) -> Optional[CycleTemplate]:
        """Get the selected template.

        Returns:
            Selected CycleTemplate or None
        """
        return self.selected_template
