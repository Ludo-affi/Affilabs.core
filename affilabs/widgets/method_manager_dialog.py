"""Method Manager Dialog - Popup for saving/loading cycle queue methods.

Provides UI for managing experimental method files (saved cycle queues).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QTextEdit,
    QInputDialog,
    QMessageBox,
    QSplitter,
    QWidget,
)

from affilabs.services.method_manager import MethodManager
from affilabs.utils.logger import logger


class MethodManagerDialog(QDialog):
    """Dialog for managing saved methods (cycle queues)."""

    def __init__(self, main_window, parent=None):
        """Initialize method manager dialog.
        
        Args:
            main_window: Reference to main window for accessing segment_queue
            parent: Parent widget
        """
        try:
            super().__init__(parent)
            logger.debug(f"MethodManagerDialog.__init__ called with main_window={type(main_window).__name__ if main_window else None}, parent={type(parent).__name__ if parent else None}")
            
            self.main_window = main_window
            
            # Get current user from sidebar if available
            current_user = None
            if hasattr(parent, 'user_combo'):
                current_user = parent.user_combo.currentText()
            elif hasattr(main_window, 'sidebar') and hasattr(main_window.sidebar, 'user_combo'):
                current_user = main_window.sidebar.user_combo.currentText()
            
            logger.debug(f"Current user for method manager: {current_user or 'none'}")
            self.method_manager = MethodManager(current_user=current_user)
            self.selected_method = None
            
            self.setWindowTitle("Method Manager")
            self.setWindowFlags(Qt.WindowType.Window)
            self.setModal(False)  # Allow interaction with main window
            self.resize(800, 500)
            
            logger.debug("Setting up UI...")
            self._setup_ui()
            logger.debug("Refreshing methods list...")
            self._refresh_methods_list()
            logger.debug("MethodManagerDialog initialized successfully")
            
        except Exception as e:
            logger.exception(f"Failed to initialize MethodManagerDialog: {e}")
            raise

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Splitter for list and preview
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background: #D1D1D6;
                width: 1px;
            }
        """)
        
        # Left side: Methods list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        
        list_label = QLabel("Saved Methods")
        list_label.setStyleSheet(
            "font-size: 12px; font-weight: 600; padding-bottom: 2px; "
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        left_layout.addWidget(list_label)
        
        self.methods_list = QListWidget()
        self.methods_list.setStyleSheet("""
            QListWidget {
                background: white;
                border: 1px solid #D1D1D6;
                border-radius: 4px;
                font-size: 12px;
                font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;
            }
            QListWidget::item {
                padding: 8px;
                color: #1D1D1F;
            }
            QListWidget::item:selected {
                background: #007AFF;
                color: white;
            }
            QListWidget::item:hover {
                background: #E5E5EA;
            }
        """)
        self.methods_list.itemClicked.connect(self._on_method_selected)
        self.methods_list.itemDoubleClicked.connect(self._on_load_clicked)
        left_layout.addWidget(self.methods_list)
        
        splitter.addWidget(left_widget)
        
        # Right side: Preview
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)
        
        preview_label = QLabel("Preview")
        preview_label.setStyleSheet(
            "font-size: 12px; font-weight: 600; padding-bottom: 2px; "
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        right_layout.addWidget(preview_label)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("Select a method to preview")
        self.preview_text.setStyleSheet("""
            QTextEdit {
                background: #F9F9F9;
                border: 1px solid #D1D1D6;
                border-radius: 4px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                padding: 8px;
                color: #1D1D1F;
                line-height: 1.4;
            }
        """)
        right_layout.addWidget(self.preview_text)
        
        splitter.addWidget(right_widget)
        
        # Set splitter sizes (35% list, 65% preview)
        splitter.setSizes([280, 520])
        layout.addWidget(splitter, 1)  # Stretch to fill
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(6)
        
        self.load_btn = QPushButton("Load")
        self.load_btn.setEnabled(False)
        self.load_btn.clicked.connect(self._on_load_clicked)
        self.load_btn.setFixedSize(80, 28)
        self.load_btn.setStyleSheet("""
            QPushButton {
                background: #007AFF;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: 600;
                font-size: 12px;
                font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton:hover { background: #0051D5; }
            QPushButton:disabled { background: #E5E5EA; color: #8E8E93; }
        """)
        button_layout.addWidget(self.load_btn)
        
        self.save_btn = QPushButton("Save Queue")
        self.save_btn.clicked.connect(self._on_save_clicked)
        self.save_btn.setFixedSize(90, 28)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: #34C759;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: 600;
                font-size: 12px;
                font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton:hover { background: #30B350; }
        """)
        button_layout.addWidget(self.save_btn)
        
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        self.delete_btn.setFixedSize(70, 28)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background: #FF3B30;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: 600;
                font-size: 12px;
                font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton:hover { background: #E63329; }
            QPushButton:disabled { background: #E5E5EA; color: #8E8E93; }
        """)
        button_layout.addWidget(self.delete_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        close_btn.setFixedSize(70, 28)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #F2F2F7;
                color: #1D1D1F;
                border: 1px solid #D1D1D6;
                border-radius: 4px;
                font-weight: 600;
                font-size: 12px;
                font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton:hover { background: #E5E5EA; }
        """)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)

    def _refresh_methods_list(self):
        """Refresh the list of saved methods."""
        self.methods_list.clear()
        methods = self.method_manager.get_methods_list()
        
        if not methods:
            item = QListWidgetItem("No saved methods")
            item.setFlags(Qt.ItemFlag.NoItemFlags)  # Not selectable
            self.methods_list.addItem(item)
            return
        
        for method in methods:
            # Format display text
            import datetime
            created_str = datetime.datetime.fromtimestamp(method['created']).strftime('%Y-%m-%d %H:%M')
            
            display_text = f"{method['name']} ({method['cycle_count']} cycles)"
            if method.get('author'):
                display_text += f" - by {method['author']}"
            display_text += f"\n  Created: {created_str}"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, method['filename'])
            self.methods_list.addItem(item)

    def _on_method_selected(self, item):
        """Handle method selection from list."""
        if item.flags() & Qt.ItemFlag.NoItemFlags:
            return
        
        filename = item.data(Qt.ItemDataRole.UserRole)
        self.selected_method = filename
        
        # Enable buttons
        self.load_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        
        # Load and display preview
        method_data = self.method_manager.load_method(filename)
        if method_data:
            self._display_preview(method_data)

    def _display_preview(self, method_data):
        """Display method preview in text area."""
        preview = f"Method: {method_data.get('name', 'Unknown')}\n"
        preview += "=" * 50 + "\n\n"
        
        if method_data.get('description'):
            preview += f"Description: {method_data['description']}\n\n"
        
        if method_data.get('author'):
            preview += f"Author: {method_data['author']}\n\n"
        
        preview += f"Cycles: {method_data.get('cycle_count', 0)}\n"
        preview += "-" * 50 + "\n\n"
        
        # List cycles
        for i, cycle in enumerate(method_data.get('cycles', []), 1):
            cycle_type = cycle.get('type', 'Unknown')
            duration = cycle.get('length_minutes', 0)
            note = cycle.get('note', '')
            
            preview += f"{i}. {cycle_type} - {duration} min\n"
            if note:
                preview += f"   Note: {note[:60]}\n"
            preview += "\n"
        
        self.preview_text.setPlainText(preview)

    def _on_load_clicked(self):
        """Load selected method into queue."""
        if not self.selected_method:
            return
        
        method_data = self.method_manager.load_method(self.selected_method)
        if not method_data:
            QMessageBox.warning(self, "Error", "Failed to load method")
            return
        
        # Get segment_queue from Application instance (main_window.app or via sidebar)
        segment_queue = None
        update_summary_fn = None
        
        # Try to get Application instance
        app = None
        if hasattr(self.main_window, 'app'):
            app = self.main_window.app
        elif hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'app'):
            app = self.main_window.sidebar.app
        
        if app:
            segment_queue = app.segment_queue
            update_summary_fn = app._update_summary_table
        else:
            # Fallback: try direct access (shouldn't happen)
            if hasattr(self.main_window, 'segment_queue'):
                segment_queue = self.main_window.segment_queue
                update_summary_fn = getattr(self.main_window, '_update_summary_table', None)
        
        if segment_queue is None:
            QMessageBox.critical(self, "Error", "Cannot access queue. Application reference not found.")
            logger.error("Failed to access segment_queue - no app reference found")
            return
        
        # Confirm if queue is not empty
        if segment_queue:
            reply = QMessageBox.question(
                self,
                "Replace Queue?",
                f"Current queue has {len(segment_queue)} cycles.\n"
                "Do you want to replace it with this method?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Load cycles
        try:
            from affilabs.domain.cycle import Cycle
            
            # Clear current queue
            segment_queue.clear()
            
            # Load cycles from method
            for cycle_dict in method_data.get('cycles', []):
                cycle = Cycle.from_dict(cycle_dict)
                # Reset to pending status
                cycle.status = 'pending'
                segment_queue.append(cycle)
            
            # Refresh UI
            if update_summary_fn:
                update_summary_fn()
            
            QMessageBox.information(
                self,
                "Success",
                f"Loaded method: {method_data['name']}\n"
                f"{len(method_data['cycles'])} cycles added to queue"
            )
            
            logger.info(f"✓ Method loaded to queue: {method_data['name']}")
            self.close()
            
        except Exception as e:
            logger.exception(f"Failed to load method to queue: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load method:\n{e}")

    def _on_save_clicked(self):
        """Save current queue as new method."""
        # Get segment_queue from Application instance
        segment_queue = None
        app = None
        if hasattr(self.main_window, 'app'):
            app = self.main_window.app
        elif hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'app'):
            app = self.main_window.sidebar.app
        
        if app:
            segment_queue = app.segment_queue
        elif hasattr(self.main_window, 'segment_queue'):
            segment_queue = self.main_window.segment_queue
        
        # Check if queue has cycles
        if not segment_queue or len(segment_queue) == 0:
            QMessageBox.warning(self, "Empty Queue", "No cycles in queue to save")
            return
        
        # Get method name
        name, ok = QInputDialog.getText(
            self,
            "Save Method",
            "Method name:",
        )
        if not ok or not name:
            return
        
        # Get description (optional)
        description, ok = QInputDialog.getText(
            self,
            "Save Method",
            "Description (optional):",
        )
        if not ok:
            description = ""
        
        # Get author (from user profile if available)
        author = ""
        if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'user_combo'):
            author = self.main_window.sidebar.user_combo.currentText()
        
        # Save method
        success = self.method_manager.save_method(
            name=name,
            cycles=segment_queue,
            description=description,
            author=author
        )
        
        if success:
            QMessageBox.information(
                self,
                "Success",
                f"Method '{name}' saved with {len(segment_queue)} cycles"
            )
            self._refresh_methods_list()
        else:
            QMessageBox.critical(self, "Error", "Failed to save method")

    def _on_delete_clicked(self):
        """Delete selected method."""
        if not self.selected_method:
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete method '{self.selected_method}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.method_manager.delete_method(self.selected_method):
                QMessageBox.information(self, "Success", "Method deleted")
                self._refresh_methods_list()
                self.preview_text.clear()
                self.load_btn.setEnabled(False)
                self.delete_btn.setEnabled(False)
            else:
                QMessageBox.critical(self, "Error", "Failed to delete method")
