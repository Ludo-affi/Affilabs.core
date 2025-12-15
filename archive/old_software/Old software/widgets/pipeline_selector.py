"""Pipeline Selection Widget

Provides UI controls for switching between processing pipelines
and viewing their parameters.
"""

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.logger import logger
from utils.processing_pipeline import get_pipeline_registry


class PipelineSelector(QWidget):
    """Widget for selecting and configuring processing pipelines"""

    # Signal emitted when pipeline changes
    pipeline_changed = Signal(str)  # pipeline_id

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.registry = get_pipeline_registry()
        self._setup_ui()
        self._populate_pipelines()

    def _setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)

        # Pipeline selection group
        selection_group = QGroupBox("Processing Pipeline")
        selection_layout = QVBoxLayout()

        # Combo box for pipeline selection
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Active Pipeline:"))

        self.pipeline_combo = QComboBox()
        self.pipeline_combo.currentTextChanged.connect(self._on_pipeline_selected)
        selector_layout.addWidget(self.pipeline_combo, 1)

        selection_layout.addLayout(selector_layout)

        # Pipeline description
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet(
            "QLabel { padding: 5px; background-color: #f0f0f0; }",
        )
        selection_layout.addWidget(self.description_label)

        selection_group.setLayout(selection_layout)
        layout.addWidget(selection_group)

        # Pipeline details group
        details_group = QGroupBox("Pipeline Details")
        details_layout = QVBoxLayout()

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        details_layout.addWidget(self.details_text)

        details_group.setLayout(details_layout)
        layout.addWidget(details_group)

        # Action buttons
        button_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("Refresh Pipelines")
        self.refresh_btn.clicked.connect(self._populate_pipelines)
        button_layout.addWidget(self.refresh_btn)

        button_layout.addStretch()

        layout.addLayout(button_layout)

        # Add stretch at bottom
        layout.addStretch()

    def _populate_pipelines(self):
        """Populate combo box with available pipelines"""
        self.pipeline_combo.blockSignals(True)
        self.pipeline_combo.clear()

        # Get all registered pipelines
        pipelines = self.registry.list_pipelines()

        for metadata in pipelines:
            self.pipeline_combo.addItem(metadata.name, metadata)

        # Set current selection to active pipeline
        active_id = self.registry.active_pipeline_id
        if active_id:
            try:
                active_pipeline = self.registry.get_active_pipeline()
                active_metadata = active_pipeline.get_metadata()
                index = self.pipeline_combo.findText(active_metadata.name)
                if index >= 0:
                    self.pipeline_combo.setCurrentIndex(index)
            except Exception as e:
                logger.error(f"Error setting active pipeline in UI: {e}")

        self.pipeline_combo.blockSignals(False)

        # Update display for current selection
        self._update_display()

    @Slot(str)
    def _on_pipeline_selected(self, pipeline_name: str):
        """Handle pipeline selection change"""
        try:
            # Find pipeline ID by name
            index = self.pipeline_combo.currentIndex()
            metadata = self.pipeline_combo.itemData(index)

            if metadata:
                # Find pipeline ID (we need to search registry)
                for pid, pclass in self.registry._pipelines.items():
                    temp_pipeline = pclass()
                    if temp_pipeline.get_metadata().name == metadata.name:
                        # Set as active
                        self.registry.set_active_pipeline(pid)
                        self._update_display()
                        self.pipeline_changed.emit(pid)
                        logger.info(f"Switched to pipeline: {pid}")
                        break
        except Exception as e:
            logger.error(f"Error changing pipeline: {e}")

    def _update_display(self):
        """Update description and details display"""
        try:
            index = self.pipeline_combo.currentIndex()
            metadata = self.pipeline_combo.itemData(index)

            if metadata:
                # Update description
                self.description_label.setText(
                    f"<b>{metadata.name}</b> (v{metadata.version})<br/>"
                    f"{metadata.description}",
                )

                # Update details
                details = f"<b>Author:</b> {metadata.author}<br/><br/>"
                details += "<b>Parameters:</b><br/>"

                for key, value in metadata.parameters.items():
                    details += f"  • {key}: {value}<br/>"

                self.details_text.setHtml(details)
        except Exception as e:
            logger.error(f"Error updating display: {e}")

    def get_active_pipeline_id(self) -> str | None:
        """Get the currently selected pipeline ID"""
        return self.registry.active_pipeline_id


if __name__ == "__main__":
    """Test the pipeline selector widget"""
    import sys

    from PySide6.QtWidgets import QApplication

    # Initialize pipelines
    from utils.pipelines import initialize_pipelines

    initialize_pipelines()

    app = QApplication(sys.argv)

    widget = PipelineSelector()
    widget.setWindowTitle("Pipeline Selector Test")
    widget.resize(500, 400)
    widget.show()

    sys.exit(app.exec())
