"""Queue Toolbar - Action buttons for queue management.

ARCHITECTURE LAYER: UI Widget (Phase 4)

This toolbar provides buttons for queue operations:
- Undo/Redo with keyboard shortcuts (Ctrl+Z, Ctrl+Shift+Z)
- Delete Selected
- Clear All Queue
- Visual state updates (enabled/disabled based on availability)

FEATURES:
- Keyboard shortcuts automatically registered
- Dynamic button states (enabled when operation available)
- Tooltips with operation descriptions
- Icon support (optional)

USAGE:
    # Create toolbar
    toolbar = QueueToolbar()

    # Connect to presenter
    toolbar.undo_requested.connect(presenter.undo)
    toolbar.redo_requested.connect(presenter.redo)
    toolbar.delete_selected_requested.connect(lambda: presenter.delete_cycles(table.get_selected_indices()))
    toolbar.clear_all_requested.connect(presenter.clear_queue)

    # Update button states from presenter
    presenter.can_undo_changed.connect(toolbar.set_undo_enabled)
    presenter.can_redo_changed.connect(toolbar.set_redo_enabled)
    presenter.undo_description_changed.connect(toolbar.set_undo_tooltip)
"""

from PySide6.QtWidgets import QToolBar, QWidget, QPushButton, QLabel, QSizePolicy
from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtGui import QKeySequence, QShortcut

from affilabs.utils.logger import logger


class QueueToolbar(QToolBar):
    """Toolbar for queue operations with undo/redo support.

    Provides action buttons for:
    - Undo (Ctrl+Z)
    - Redo (Ctrl+Shift+Z)
    - Delete Selected
    - Clear All

    Signals:
        undo_requested: User clicked Undo or pressed Ctrl+Z
        redo_requested: User clicked Redo or pressed Ctrl+Shift+Z
        delete_selected_requested: User clicked Delete Selected
        clear_all_requested: User clicked Clear All
    """

    # Signals
    undo_requested = Signal()
    redo_requested = Signal()
    delete_selected_requested = Signal()
    clear_all_requested = Signal()

    def __init__(self, parent: QWidget = None):
        """Initialize queue toolbar.

        Args:
            parent: Parent widget
        """
        super().__init__("Queue Operations", parent)

        self._undo_button: QPushButton = None
        self._redo_button: QPushButton = None
        self._delete_button: QPushButton = None
        self._clear_button: QPushButton = None

        self._setup_ui()
        self._setup_shortcuts(parent)

        logger.debug("QueueToolbar initialized")

    def _setup_ui(self):
        """Create toolbar buttons."""
        # Undo button
        self._undo_button = QPushButton("↶ Undo")
        self._undo_button.setToolTip("Undo last operation (Ctrl+Z)")
        self._undo_button.setEnabled(False)
        self._undo_button.clicked.connect(self.undo_requested.emit)
        self.addWidget(self._undo_button)

        # Redo button
        self._redo_button = QPushButton("↷ Redo")
        self._redo_button.setToolTip("Redo last undone operation (Ctrl+Shift+Z)")
        self._redo_button.setEnabled(False)
        self._redo_button.clicked.connect(self.redo_requested.emit)
        self.addWidget(self._redo_button)

        # Separator
        self.addSeparator()

        # Delete selected button
        self._delete_button = QPushButton("🗑 Delete Selected")
        self._delete_button.setToolTip("Delete selected cycles from queue")
        self._delete_button.setEnabled(False)  # Enabled when selection exists
        self._delete_button.clicked.connect(self.delete_selected_requested.emit)
        self.addWidget(self._delete_button)

        # Clear all button
        self._clear_button = QPushButton("🧹 Clear All")
        self._clear_button.setToolTip("Remove all cycles from queue")
        self._clear_button.clicked.connect(self._on_clear_all_clicked)
        self.addWidget(self._clear_button)

        # Spacer to push subsequent items to the right
        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred
        )
        self.addWidget(spacer)

        # Queue info label (optional)
        self._info_label = QLabel("")
        self.addWidget(self._info_label)

    def _setup_shortcuts(self, parent: QWidget):
        """Register keyboard shortcuts.

        Args:
            parent: Parent widget for shortcut scope
        """
        if not parent:
            return

        # Ctrl+Z for Undo
        undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, parent)
        undo_shortcut.activated.connect(self._on_undo_shortcut)

        # Ctrl+Shift+Z for Redo
        redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, parent)
        redo_shortcut.activated.connect(self._on_redo_shortcut)

        logger.debug("Keyboard shortcuts registered (Ctrl+Z, Ctrl+Shift+Z)")

    # ========================================================================
    # PUBLIC API - Button State Control
    # ========================================================================

    @Slot(bool)
    def set_undo_enabled(self, enabled: bool):
        """Enable/disable undo button.

        Args:
            enabled: True to enable undo
        """
        self._undo_button.setEnabled(enabled)

    @Slot(bool)
    def set_redo_enabled(self, enabled: bool):
        """Enable/disable redo button.

        Args:
            enabled: True to enable redo
        """
        self._redo_button.setEnabled(enabled)

    @Slot(bool)
    def set_delete_enabled(self, enabled: bool):
        """Enable/disable delete button.

        Args:
            enabled: True to enable delete (when selection exists)
        """
        self._delete_button.setEnabled(enabled)

    @Slot(bool)
    def set_clear_enabled(self, enabled: bool):
        """Enable/disable clear button.

        Args:
            enabled: True to enable clear (when queue not empty)
        """
        self._clear_button.setEnabled(enabled)

    @Slot(str)
    def set_undo_tooltip(self, description: str):
        """Update undo button tooltip with operation description.

        Args:
            description: Undo operation description (e.g., "Undo: Add Baseline cycle")
        """
        tooltip = f"Undo: {description} (Ctrl+Z)" if description else "Undo (Ctrl+Z)"
        self._undo_button.setToolTip(tooltip)

    @Slot(str)
    def set_redo_tooltip(self, description: str):
        """Update redo button tooltip with operation description.

        Args:
            description: Redo operation description
        """
        tooltip = f"Redo: {description} (Ctrl+Shift+Z)" if description else "Redo (Ctrl+Shift+Z)"
        self._redo_button.setToolTip(tooltip)

    @Slot(str)
    def set_info_text(self, text: str):
        """Update info label text.

        Args:
            text: Info text to display (e.g., "3 cycles, 6.0 min total")
        """
        self._info_label.setText(text)

    # ========================================================================
    # PRIVATE - Event Handlers
    # ========================================================================

    def _on_undo_shortcut(self):
        """Handle Ctrl+Z shortcut."""
        if self._undo_button.isEnabled():
            self.undo_requested.emit()
            logger.debug("Undo triggered via Ctrl+Z")

    def _on_redo_shortcut(self):
        """Handle Ctrl+Shift+Z shortcut."""
        if self._redo_button.isEnabled():
            self.redo_requested.emit()
            logger.debug("Redo triggered via Ctrl+Shift+Z")

    def _on_clear_all_clicked(self):
        """Handle clear all button click with confirmation."""
        # TODO: Add confirmation dialog in actual integration
        # For now, just emit signal
        self.clear_all_requested.emit()

    # ========================================================================
    # CONVENIENCE METHODS
    # ========================================================================

    def update_from_presenter_stats(self, stats: dict):
        """Update toolbar state from presenter statistics.

        Args:
            stats: Stats dict from presenter.get_stats()
        """
        # Update info label
        queue_size = stats.get('queue_size', 0)
        total_duration = stats.get('total_duration_min', 0.0)
        self.set_info_text(f"{queue_size} cycles, {total_duration:.1f} min total")

        # Update button states
        self.set_undo_enabled(stats.get('can_undo', False))
        self.set_redo_enabled(stats.get('can_redo', False))
        self.set_clear_enabled(queue_size > 0)
