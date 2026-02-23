"""Method Builder Dialog - Popup for building cycle configurations.

Replaces the cramped sidebar form with a spacious popup dialog for better UX.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QFrame, QTextEdit, QScrollArea, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QLineEdit, QComboBox,
    QCheckBox, QTabWidget, QWidget
)
from PySide6.QtCore import Signal, Qt, QTimer, QSize
from PySide6.QtGui import QKeyEvent, QCursor, QColor, QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from affilabs.domain.cycle import Cycle
from affilabs.services.queue_preset_storage import QueuePresetStorage
from affilabs.services.user_profile_manager import UserProfileManager
from affilabs.widgets.ui_constants import CycleTypeStyle
from affilabs.utils.logger import logger
import time
import re
import threading


# ---------------------------------------------------------------------------
# SVG icon helper
# ---------------------------------------------------------------------------

def _create_svg_icon(svg_string: str, size: int = 16) -> QIcon:
    """Create QIcon from inline SVG markup."""
    renderer = QSvgRenderer(svg_string.encode('utf-8'))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


# SVG icon definitions (24×24 viewBox, rendered at requested size)
_SVG_UNDO = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M9 14L4 9l5-5" stroke="#1D1D1F" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M4 9h11a5 5 0 0 1 0 10h-3" stroke="#1D1D1F" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'

_SVG_REDO = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M15 14l5-5-5-5" stroke="#1D1D1F" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M20 9H9a5 5 0 0 0 0 10h3" stroke="#1D1D1F" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'

_SVG_TRASH = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3 6h18" stroke="#FF3B30" stroke-width="2" stroke-linecap="round"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" stroke="#FF3B30" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" stroke="#FF3B30" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M10 11v6M14 11v6" stroke="#FF3B30" stroke-width="2" stroke-linecap="round"/></svg>'

_SVG_CHEVRON_UP = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M18 15l-6-6-6 6" stroke="#1D1D1F" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'

_SVG_CHEVRON_DOWN = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M6 9l6 6 6-6" stroke="#1D1D1F" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'

_SVG_CLEAR = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="9" stroke="#86868B" stroke-width="2"/><path d="M15 9l-6 6M9 9l6 6" stroke="#86868B" stroke-width="2" stroke-linecap="round"/></svg>'

_SVG_PLUS_WHITE = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 5v14M5 12h14" stroke="white" stroke-width="2.5" stroke-linecap="round"/></svg>'

_SVG_CLIPBOARD_WHITE = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" stroke="white" stroke-width="2" stroke-linecap="round"/><rect x="8" y="2" width="8" height="4" rx="1" stroke="white" stroke-width="2"/><path d="M9 12h6M9 16h4" stroke="white" stroke-width="2" stroke-linecap="round"/></svg>'


# ---------------------------------------------------------------------------
#  Draggable method table — supports row drag-and-drop reordering
# ---------------------------------------------------------------------------

class DraggableMethodTable(QTableWidget):
    """QTableWidget with row-level drag-and-drop reordering.

    When the user drags a row to a new position the *on_row_moved* callback is
    invoked with (from_row, to_row) so the caller can update its data model and
    repopulate the table itself.
    """

    def __init__(self, on_row_moved=None):
        super().__init__()
        self._on_row_moved = on_row_moved
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        # Use DragOnly so Qt doesn't physically move rows — we repopulate from the data model
        self.setDragDropMode(QTableWidget.DragDropMode.DragOnly)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setToolTip("Drag rows to reorder cycles")

    def dragEnterEvent(self, event):
        if event.source() is self:
            event.accept()

    def dragMoveEvent(self, event):
        if event.source() is self:
            event.accept()

    def dropEvent(self, event):  # type: ignore[override]
        if event.source() is not self:
            event.ignore()
            return
        src_row = self.currentRow()
        index = self.indexAt(event.position().toPoint())
        if index.isValid():
            dst_row = index.row()
        else:
            # Dropped below all rows — move to last
            dst_row = self.rowCount() - 1
        if src_row >= 0 and src_row != dst_row and self._on_row_moved:
            self._on_row_moved(src_row, dst_row)
        event.accept()


# ---------------------------------------------------------------------------
#  Spark Method Popup — lightweight chat for method-building assistance
# ---------------------------------------------------------------------------

class _SparkBubble(QFrame):
    """Minimal chat bubble for the method-builder Spark popup."""

    def __init__(self, text: str, is_user: bool = True, parent=None):
        super().__init__(parent)
        bg = "#E3F2FD" if is_user else "#F5F5F5"
        fg = "#1565C0" if is_user else "#212121"
        self.setStyleSheet(f"QFrame {{ background: {bg}; border-radius: 12px; }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.label.setStyleSheet(
            f"color: {fg}; font-size: 13px; background: transparent;"
            f" font-family: -apple-system, 'Segoe UI', sans-serif;"
        )
        layout.addWidget(self.label)
        if is_user:
            # Use Preferred + max width so bubble shrinks for short text
            # but expands enough to show all text with word wrap
            self.setMaximumWidth(320)
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)


class SparkMethodPopup(QDialog):
    """Spark AI chat popup specialised for method-building queries.

    Opens from the green ⚡ Spark button in the method builder.
    Provides a conversational interface that can generate method text
    which the user can insert directly into the notes field.
    """

    # Emitted with the text the user wants inserted into the notes field
    insert_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚡ Spark — Method Assistant")
        self.resize(460, 520)
        self.setModal(False)  # Non-blocking
        self._last_ai_text = ""  # Most recent AI answer (for Insert button)
        self._answer_engine = None
        self._setup_ui()
        self._init_engine_background()

    # -- UI ----------------------------------------------------------------

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Header
        hdr = QLabel("⚡ Spark — Method Assistant")
        hdr.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: #1D1D1F;"
            " font-family: -apple-system, 'SF Pro Display', 'Segoe UI', sans-serif;"
        )
        root.addWidget(hdr)

        # Scrollable chat area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #E5E5EA; border-radius: 8px; background: white; }"
        )
        chat_container = QFrame()
        chat_container.setStyleSheet("background: white;")
        self._chat_layout = QVBoxLayout(chat_container)
        self._chat_layout.setContentsMargins(8, 8, 8, 8)
        self._chat_layout.setSpacing(8)
        self._chat_layout.addStretch()  # Pushes bubbles up
        scroll.setWidget(chat_container)
        self._scroll = scroll
        root.addWidget(scroll, 1)

        # Welcome bubble
        self._add_bubble(
            "Hi! I can help you build methods. Try asking:\n\n"
            "• @spark titration — dose-response series\n"
            "• @spark amine coupling — full immobilization workflow\n"
            "• build 5 — generate 5 binding cycles\n"
            "• @spark regeneration / baseline / immobilization\n\n"
            "I'll suggest cycles you can accept, edit, or reject.",
            is_user=False,
        )

        # Input row
        input_row = QHBoxLayout()
        self._input = QTextEdit()
        self._input.setPlaceholderText("Ask Spark about methods…")
        self._input.setMaximumHeight(60)
        self._input.setStyleSheet(
            "QTextEdit { background: white; border: 2px solid #E5E5EA;"
            " border-radius: 8px; padding: 8px; font-size: 13px; }"
            " QTextEdit:focus { border: 2px solid #34C759; }"
        )
        self._input.installEventFilter(self)
        input_row.addWidget(self._input, 1)

        send_btn = QPushButton("Send")
        send_btn.setFixedSize(60, 36)
        send_btn.setStyleSheet(
            "QPushButton { background: #34C759; color: white; border: none;"
            " border-radius: 8px; font-weight: 600; font-size: 13px; }"
            " QPushButton:hover { background: #28A745; }"
        )
        send_btn.clicked.connect(self._on_send)
        input_row.addWidget(send_btn)
        root.addLayout(input_row)

        # Bottom action row
        action_row = QHBoxLayout()

        self._insert_btn = QPushButton("📋 Insert into Method")
        self._insert_btn.setFixedHeight(32)
        self._insert_btn.setEnabled(False)
        self._insert_btn.setToolTip("Paste Spark's last suggestion into the Note field")
        self._insert_btn.setStyleSheet(
            "QPushButton { background: #007AFF; color: white; border: none;"
            " border-radius: 6px; padding: 4px 16px; font-size: 12px; font-weight: 600; }"
            " QPushButton:hover { background: #0051D5; }"
            " QPushButton:disabled { background: #C7C7CC; }"
        )
        self._insert_btn.clicked.connect(self._on_insert)
        action_row.addWidget(self._insert_btn)

        action_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(32)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #86868B; border: 1px solid #E5E5EA;"
            " border-radius: 6px; padding: 4px 16px; font-size: 12px; }"
            " QPushButton:hover { background: #F5F5F7; }"
        )
        close_btn.clicked.connect(self.close)
        action_row.addWidget(close_btn)

        root.addLayout(action_row)

    # -- Engine initialization ---------------------------------------------

    def _init_engine_background(self):
        """Initialize SparkAnswerEngine in background so it's ready on first question."""
        import threading
        def _init():
            try:
                from affilabs.services.spark import SparkAnswerEngine
                engine = SparkAnswerEngine()
                self._answer_engine = engine
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Spark engine init failed: {e}")
        threading.Thread(target=_init, daemon=True).start()

    # -- Event filter for Enter-to-send ------------------------------------

    def eventFilter(self, obj, event):
        if obj is self._input and isinstance(event, QKeyEvent):
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                    self._on_send()
                    return True
        return super().eventFilter(obj, event)

    # -- Chat helpers ------------------------------------------------------

    def _add_bubble(self, text: str, is_user: bool = True):
        bubble = _SparkBubble(text, is_user=is_user, parent=self)
        # Insert before the stretch at the end
        idx = self._chat_layout.count() - 1
        self._chat_layout.insertWidget(idx, bubble,
            alignment=Qt.AlignmentFlag.AlignRight if is_user else Qt.AlignmentFlag.AlignLeft)
        QTimer.singleShot(50, self._scroll_bottom)
        return bubble

    def _scroll_bottom(self):
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    # -- Send / answer -----------------------------------------------------

    def _on_send(self):
        try:
            question = self._input.toPlainText().strip()
            if not question:
                return
            self._input.clear()

            # User bubble
            self._add_bubble(question, is_user=True)

            # Thinking bubble
            thinking = self._add_bubble("💭 Thinking...", is_user=False)

            # Generate answer (slightly delayed so the UI paints the thinking bubble)
            QTimer.singleShot(100, lambda: self._generate_answer(question, thinking))
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Spark method popup _on_send crashed: {e}")

    def _generate_answer(self, question: str, thinking_bubble):
        """Try method-specific patterns first, then fall back to SparkAnswerEngine."""
        try:
            answer = self._try_method_patterns(question)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Spark pattern matching crashed: {e}")
            answer = None

        if answer is None:
            # Fall back to full Spark engine
            if self._answer_engine is None:
                try:
                    from affilabs.services.spark import SparkAnswerEngine
                    self._answer_engine = SparkAnswerEngine()
                except Exception as e:
                    answer = f"Could not load Spark engine: {e}"
            if answer is None:
                try:
                    answer, _ = self._answer_engine.generate_answer(question, context="method_builder")
                except Exception as e:
                    answer = "Sorry, I had trouble generating an answer. Please try again."

        # Replace thinking bubble
        try:
            thinking_bubble.label.setText(answer)
            thinking_bubble.setStyleSheet("QFrame { background: #F5F5F5; border-radius: 12px; }")
            thinking_bubble.label.setStyleSheet(
                "color: #212121; font-size: 13px; background: transparent;"
                " font-family: -apple-system, 'Segoe UI', sans-serif;"
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Spark bubble update crashed: {e}")
            return

        # Track last answer for Insert button
        self._last_ai_text = answer
        try:
            self._insert_btn.setEnabled(True)
        except Exception:
            pass
        QTimer.singleShot(50, self._scroll_bottom)

    # -- Method-specific pattern matching ----------------------------------

    def _try_method_patterns(self, text: str):
        """Return a method suggestion string, or None to fall back to the engine."""
        t = text.lower().strip()

        # "build N" pattern — N binding cycles with regen + baseline
        m = re.search(r'build.*?(\d+)', t)
        if m:
            n = int(m.group(1))
            lines = ["Baseline 5min"]
            for i in range(n):
                lines.append(f"Binding 8.5min [A:100nM] contact 300s  # Binding {i+1}")
                lines.append("Regeneration 30sec [ALL:50mM]")
                lines.append("Baseline 2min")
            return "\n".join(lines)

        if re.search(r'titration|dose.?response|concentration series|serial dilution', t):
            return ("Baseline 5min\n"
                    "Binding 8.5min [A:10nM] contact 300s\n"
                    "Regeneration 30sec [ALL:50mM]\n"
                    "Baseline 2min\n"
                    "Binding 8.5min [A:50nM] contact 300s\n"
                    "Regeneration 30sec [ALL:50mM]\n"
                    "Baseline 2min\n"
                    "Binding 8.5min [A:100nM] contact 300s\n"
                    "Regeneration 30sec [ALL:50mM]\n"
                    "Baseline 2min\n"
                    "Binding 8.5min [A:500nM] contact 300s\n"
                    "Regeneration 30sec [ALL:50mM]\n"
                    "Baseline 2min")

        if re.search(r'full cycle|complete cycle|entire run|whole method', t):
            return ("Baseline 5min\n"
                    "Binding 8.5min [A:100nM] contact 300s\n"
                    "Regeneration 30sec [ALL:50mM]\n"
                    "Baseline 2min")

        if re.search(r'regenerat|regen|clean|strip', t):
            return "Regeneration 30sec [ALL:50mM]"

        if re.search(r'binding|association|inject|sample|analyte', t):
            return ("Baseline 2min\n"
                    "Binding 8.5min [A:100nM] contact 300s\n"
                    "Regeneration 30sec [ALL:50mM]\n"
                    "Baseline 2min")

        if re.search(r'amine coupling|amine|coupling', t):
            n_match = re.search(r'(\d+)', t)
            n = int(n_match.group(1)) if n_match else 3
            lines = [
                "Baseline 5min",
                "Other 4min  # EDC/NHS activation",
                "Wash 30sec",
                "Immobilization 30min  # Ligand attachment",
                "Wash 30sec",
                "Blocking 4min  # Ethanolamine",
                "Wash 30sec",
                "Baseline 15min",
            ]
            for i in range(n):
                lines.append(f"Binding 8.5min [A:100nM] contact 300s  # Binding {i+1}")
                lines.append("Regeneration 30sec [ALL:50mM]")
                lines.append("Baseline 2min")
            return "\n".join(lines)

        if re.search(r'immobiliz|immob|attach|ligand', t):
            return "Immobilization 30min"

        if re.search(r'baseline|start|begin|initial|equilibrat', t):
            return "Baseline 5min"

        return None  # No match — fall back to engine

    # -- Insert into notes -------------------------------------------------

    def _on_insert(self):
        """Insert last AI answer into the method builder notes field."""
        if not self._last_ai_text:
            return
        # Strip lines that start with # (comments) or are purely informational
        lines = self._last_ai_text.strip().split("\n")
        # Keep cycle-like lines and comments, strip pure prose
        self.insert_requested.emit(self._last_ai_text.strip())
        self._insert_btn.setEnabled(False)


# ---------------------------------------------------------------------------


class NotesTextEdit(QPlainTextEdit):
    """Custom text edit with history navigation via Up/Down arrows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_dialog = None  # Will be set by parent

    def keyPressEvent(self, event: QKeyEvent):
        """Handle Up/Down arrow keys for history navigation, ENTER for @spark commands, and [ for auto-complete."""
        if not self._parent_dialog:
            super().keyPressEvent(event)
            return

        # Auto-complete [:]  when user types [
        # Cursor positioned here: [▮:]  for fast concentration tag entry
        if event.text() == '[':
            from PySide6.QtGui import QTextCursor
            cursor = self.textCursor()
            cursor.insertText('[:]')
            # Move cursor back 2 positions to land between [ and :
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, 2)
            self.setTextCursor(cursor)
            event.accept()
            return

        # ENTER key → If @spark command OR waiting for response, trigger processing
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            text_stripped = self.toPlainText().strip()

            # If we're waiting for a response (like answering "5" to "How many binding cycles?")
            if self._parent_dialog._waiting_for_response:
                # Trigger Spark AI processing to process the answer
                self._parent_dialog._detect_and_respond_to_question()
                event.accept()
                return

            # If @spark command, trigger processing immediately
            if text_stripped.lower().startswith('@spark '):
                # Trigger Spark AI processing
                self._parent_dialog._on_add_to_method()
                event.accept()
                return
            # Otherwise allow default behavior (new line for multi-cycle input)

        # Only handle arrows when at first/last line
        cursor = self.textCursor()

        if event.key() == Qt.Key.Key_Up:
            # Check if we're on the first line
            cursor.movePosition(cursor.MoveOperation.Start)
            if self.textCursor().blockNumber() == cursor.blockNumber():
                # Navigate to previous note in history
                if self._parent_dialog._history_index == -1:
                    # First time browsing - save current draft
                    self._parent_dialog._current_draft = self.toPlainText()
                    self._parent_dialog._history_index = len(self._parent_dialog._notes_history)

                if self._parent_dialog._history_index > 0:
                    self._parent_dialog._history_index -= 1
                    self.setPlainText(self._parent_dialog._notes_history[self._parent_dialog._history_index])
                    # Move cursor to start
                    cursor = self.textCursor()
                    cursor.movePosition(cursor.MoveOperation.Start)
                    self.setTextCursor(cursor)
                return  # Don't call super - we handled it

        elif event.key() == Qt.Key.Key_Down:
            # Check if we're on the last line
            cursor.movePosition(cursor.MoveOperation.End)
            if self.textCursor().blockNumber() == cursor.blockNumber():
                # Navigate to next note in history
                if self._parent_dialog._history_index != -1:
                    if self._parent_dialog._history_index < len(self._parent_dialog._notes_history) - 1:
                        self._parent_dialog._history_index += 1
                        self.setPlainText(self._parent_dialog._notes_history[self._parent_dialog._history_index])
                    else:
                        # Reached end - restore draft
                        self.setPlainText(self._parent_dialog._current_draft)
                        self._parent_dialog._history_index = -1
                    # Move cursor to end
                    cursor = self.textCursor()
                    cursor.movePosition(cursor.MoveOperation.End)
                    self.setTextCursor(cursor)
                return  # Don't call super - we handled it

        # For all other keys, reset history browsing
        if event.key() not in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Shift,
                               Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._parent_dialog._history_index = -1

        super().keyPressEvent(event)


class MethodBuilderDialog(QDialog):
    """Dialog for building cycle methods.

    User builds cycles locally in this dialog, then pushes entire method to main queue.

    Signals:
        method_ready: Emitted when user wants to push method (action, method_name, cycles)
            action is either "queue" or "start"
        method_saved: Emitted when user saves method to file (method_name, file_path)
    """

    method_ready = Signal(str, str, list)  # (action, method_name, list of cycles)
    method_saved = Signal(str, str)  # (method_name, file_path)

    def __init__(self, parent=None, user_manager=None, app=None):
        super().__init__(parent)
        self._app_ref = app  # For triggering calibration from New Sensor button
        self.setWindowTitle("Build Method")
        self.setMinimumSize(860, 640)
        self._local_cycles = []  # Cycles built in this dialog
        self._has_affipump = False  # Set by configure_for_hardware(); gates contact_time warnings
        self._notes_history = []  # History of previous notes
        self._history_index = -1  # Current position in history (-1 = not browsing)
        self._current_draft = ""  # Store current text when browsing history
        self._helper_active = False  # Track if helper is responding
        self._preset_storage = QueuePresetStorage()  # For @preset and !save commands
        self._waiting_for_response = False  # Track if we're waiting for user answer
        self._pending_command = None  # Store the command waiting for answer (e.g., "amine_coupling", "build")
        self._answer_engine = None  # Initialized in background thread at startup

        # Use shared user manager if provided, otherwise create fallback
        if user_manager:
            self._user_manager = user_manager
        else:
            from affilabs.services.user_profile_manager import UserProfileManager
            self._user_manager = UserProfileManager()

        self._setup_ui()
        self._init_engine_background()

    def _init_engine_background(self):
        """Initialize SparkAnswerEngine in background so it's ready on first question."""
        import threading
        def _init():
            try:
                from affilabs.services.spark import SparkAnswerEngine
                self._answer_engine = SparkAnswerEngine()
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Spark engine init failed: {e}")
        threading.Thread(target=_init, daemon=True).start()

    def _detect_and_respond_to_question(self):
        """Detect if user is asking a question and provide helpful suggestions.

        Routes through SparkAnswerEngine (single source of truth for patterns).
        Also searches saved presets if text matches a preset name.
        """
        text = self.notes_input.toPlainText().strip()
        text_lower = text.lower()

        if not text:
            # Show message if empty
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Ask Spark",
                "Type a question or keyword. Examples:\n\n"
                "• titration — dose-response concentration series\n"
                "• kinetics — association + dissociation phases\n"
                "• amine coupling — full immobilization workflow\n"
                "• build 5 — create 5 binding cycles\n"
                "• regeneration / baseline / immobilization\n\n"
                "Type your query and press Enter or click ⚡ Send.")
            return

        if self._helper_active:
            return

        # Check if we're waiting for a response to a question
        if self._waiting_for_response:
            self._process_user_answer(text)
            return

        # First, check if text matches a saved preset name
        all_presets = self._preset_storage.get_all_presets()
        preset_names = [preset.name for preset in all_presets]
        for preset_name in preset_names:
            if preset_name.lower() in text_lower or text_lower in preset_name.lower():
                # Found matching preset - load it
                self._load_preset(preset_name)
                self.notes_input.clear()
                return

        # Check for "build" with number (specialized pattern)
        build_match = re.search(r'build.*?(\d+)', text_lower)
        if build_match:
            num_cycles = int(build_match.group(1))
            cycles = []
            for i in range(num_cycles):
                cycles.append(f"Binding 15min [A]  # Binding {i+1}")
                cycles.append("Regeneration 2min [ALL]")
                cycles.append("Baseline 2min [ALL]")
            response = "\n".join(cycles)
            self._show_suggestion(response)
            return

        # If just "build" without number, ask how many binding cycles
        if re.search(r'\bbuild\b', text_lower):
            self._ask_question("How many binding cycles? (e.g., type '5' and press Enter)", "build")
            return

        # If "amine coupling" without a number, ask how many binding cycles
        if re.search(r'amine coupling|amine|coupling', text_lower) and not build_match:
            self._ask_question("How many binding cycles? (e.g., type '5' and press Enter)", "amine_coupling")
            return

        # Route all other questions through SparkAnswerEngine (Layer 1 patterns + KB + AI)
        try:
            if self._answer_engine is None:
                self._answer_engine = SparkAnswerEngine()
            
            answer, matched = self._answer_engine.generate_answer(text, context="method_builder")

            if matched:
                self._show_suggestion(answer)
                return
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"SparkAnswerEngine failed: {e}")

        # No match found - show available options including presets
        from PySide6.QtWidgets import QMessageBox
        preset_list = "\n".join(f"• @{name}" for name in preset_names) if preset_names else ""
        preset_section = f"\n\nSaved Presets:\n{preset_list}" if preset_names else ""

        QMessageBox.information(self, "Spark Says...",
            f"I didn't match a pattern for that query.\n\n"
            f"Try these keywords:\n"
            f"• titration / dose response / serial dilution\n"
            f"• kinetics / dissociation / off-rate\n"
            f"• amine coupling\n"
            f"• build N  (e.g. build 5)\n"
            f"• regeneration / baseline / immobilization\n"
            f"• binding / association / inject\n"
            f"• p4spr channel / concentration / workflow"
            f"{preset_section}")


    def _ask_question(self, question, command):
        """Ask user a question and wait for their answer.

        Args:
            question: The question to show in placeholder
            command: The command this question is for (e.g., "amine_coupling", "build")
        """
        self._waiting_for_response = True
        self._pending_command = command

        # Clear input and show question as placeholder
        self.notes_input.clear()
        self.notes_input.setPlaceholderText(f"⚡ {question}")

        # Show tooltip
        from PySide6.QtWidgets import QToolTip
        from PySide6.QtGui import QCursor
        QToolTip.showText(
            QCursor.pos(),
            f"⚡ Spark is asking: {question}",
            self.notes_input,
            self.notes_input.rect(),
            5000
        )

    def _process_user_answer(self, answer):
        """Process user's answer to a question.

        Args:
            answer: User's text response
        """
        import re

        # Reset state
        self._waiting_for_response = False
        command = self._pending_command
        self._pending_command = None
        self.notes_input.setPlaceholderText("Type your method or ask Spark...")

        # Extract number from answer
        number_match = re.search(r'(\d+)', answer)
        if not number_match:
            # No number found - show error
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Invalid Answer",
                "Please type a number (e.g., '5') and press Enter or click Spark button.")
            self.notes_input.clear()
            return

        num_cycles = int(number_match.group(1))

        # Generate response based on command
        if command == "amine_coupling":
            # Generate amine coupling method with N binding cycles
            cycles = []
            # Immobilization setup
            cycles.append("Baseline 30sec [ALL]")
            cycles.append("Other 4min  # Activation")
            cycles.append("Other 30sec  # Wash")
            cycles.append("Immobilization 4min [A]")
            cycles.append("Other 30sec  # Wash")
            cycles.append("Other 4min  # Blocking")
            cycles.append("Other 30sec  # Wash")
            cycles.append("Baseline 15min [ALL]")
            cycles.append("")
            cycles.append("# Binding series")
            # Add binding cycles
            for i in range(num_cycles):
                cycles.append(f"Binding 15min [A]  # Binding {i+1}")
                cycles.append("Regeneration 2min [ALL]")
                cycles.append("Baseline 2min [ALL]")
            response = "\n".join(cycles)

        elif command == "build":
            # Generate build pattern
            cycles = []
            for i in range(num_cycles):
                cycles.append(f"Binding 15min [A]  # Binding {i+1}")
                cycles.append("Regeneration 2min [ALL]")
                cycles.append("Baseline 2min [ALL]")
            response = "\n".join(cycles)
        else:
            response = "Error: Unknown command"

        self._show_suggestion(response)

    def _show_suggestion(self, text):
        """Show a suggestion by replacing the input text and showing a tooltip.

        Args:
            text: The suggestion text to show
        """
        self._helper_active = True
        # Replace text with suggestion
        self.notes_input.setPlainText(text)
        
        # Show tooltip with preset suggestion if method is substantial (>=3 cycles)
        from PySide6.QtWidgets import QToolTip
        from PySide6.QtGui import QCursor
        
        # Count cycles in suggestion (heuristic: lines with Binding, Regen, Baseline, etc.)
        cycle_count = len([line for line in text.split('\n') if any(
            keyword in line for keyword in ['Baseline', 'Binding', 'Kinetic', 'Regeneration', 'Immobilization', 'Wash']
        )])
        
        if cycle_count >= 3:
            tooltip_text = "⚡ Spark suggestion! Edit as needed.\n💡 Tip: Type !save my_protocol_name to save this as a preset."
        else:
            tooltip_text = "⚡ Spark suggestion! Edit as needed."
        
        QToolTip.showText(
            QCursor.pos(),
            tooltip_text,
            self.notes_input,
            self.notes_input.rect(),
            4000 if cycle_count >= 3 else 3000
        )
        self._helper_active = False

    def _setup_ui(self):
        """Build the redesigned 3-zone dialog UI (Method Builder v2)."""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction, QShortcut, QKeySequence

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # ── Settings widgets (created early so all zones can reference them) ──
        self.mode_combo = QComboBox()
        self.mode_combo.setFixedHeight(24)
        self.mode_combo.addItems(["Manual", "Semi-Automated"])
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.setToolTip(
            "Manual: User injects by syringe\n"
            "Semi-Automated: Pump handles flow, valves switch automatically"
        )
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)

        self.hw_label = QLabel("P4SPR")
        self.hw_label.setToolTip("Detected hardware platform")

        self.detection_combo = QComboBox()
        self.detection_combo.setFixedHeight(24)
        self.detection_combo.addItems(["Auto", "Priority", "Off"])
        self.detection_combo.setCurrentIndex(0)
        self.detection_combo.setToolTip(
            "Auto: Sensitivity adapts to mode\nPriority: Most sensitive\nOff: No auto-detection"
        )

        # ═══════════════════════════════════════════════════════════════════
        # ZONE A — Header (method name · operator · hw badge)
        # ═══════════════════════════════════════════════════════════════════
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        title = QLabel("Build Method")
        title.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #1D1D1F;"
            " font-family: -apple-system, 'SF Pro Display', 'Segoe UI', sans-serif;"
        )
        header_row.addWidget(title)
        header_row.addSpacing(12)

        _lbl = QLabel("📋")
        _lbl.setStyleSheet("font-size: 13px; color: #86868B;")
        header_row.addWidget(_lbl)

        self.method_name_input = QLineEdit("Untitled Method")
        self.method_name_input.setFixedHeight(28)
        self.method_name_input.setMaximumWidth(200)
        self.method_name_input.setStyleSheet(
            "QLineEdit { background: white; border: 1px solid rgba(0,0,0,0.1);"
            " border-radius: 4px; padding: 4px 8px; font-size: 12px; color: #1D1D1F; }"
            " QLineEdit:focus { border-color: #007AFF; }"
        )
        header_row.addWidget(self.method_name_input)

        _op_icon = QLabel("👤")
        _op_icon.setStyleSheet("font-size: 13px; color: #86868B; margin-left: 8px;")
        header_row.addWidget(_op_icon)

        self.operator_combo = QComboBox()
        self.operator_combo.setFixedHeight(28)
        self.operator_combo.setMaximumWidth(140)
        self.operator_combo.addItems(self._user_manager.get_profiles())
        current_user = self._user_manager.get_current_user()
        if current_user:
            idx = self.operator_combo.findText(current_user)
            if idx >= 0:
                self.operator_combo.setCurrentIndex(idx)
        if self.operator_combo.count() <= 1:
            self.operator_combo.hide()
            _op_icon.hide()
        self.operator_combo.setStyleSheet(
            "QComboBox { background: white; border: 1px solid rgba(0,0,0,0.1);"
            " border-radius: 4px; padding: 4px 8px; font-size: 12px; color: #1D1D1F; }"
            " QComboBox:focus { border-color: #007AFF; }"
            " QComboBox::drop-down { border: none; width: 20px; }"
            " QComboBox::down-arrow { image: none; border-left: 4px solid transparent;"
            " border-right: 4px solid transparent; border-top: 5px solid #86868B; margin-right: 8px; }"
        )
        self.operator_combo.currentTextChanged.connect(self._on_operator_changed)
        header_row.addWidget(self.operator_combo)
        header_row.addStretch()

        self.hw_label.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #86868B; background: #F2F2F7;"
            " border-radius: 4px; padding: 2px 8px;"
        )
        header_row.addWidget(self.hw_label)
        layout.addLayout(header_row)

        # Header row 2 — chip/sensor metadata
        chip_row = QHBoxLayout()
        chip_row.setSpacing(8)

        _chip_icon = QLabel("🧬")
        _chip_icon.setStyleSheet("font-size: 13px; color: #86868B;")
        chip_row.addWidget(_chip_icon)

        _chip_lbl = QLabel("Surface")
        _chip_lbl.setStyleSheet("font-size: 12px; color: #86868B;")
        chip_row.addWidget(_chip_lbl)

        self.chip_type_combo = QComboBox()
        self.chip_type_combo.addItems([
            "— select —", "Au bare", "COOH", "Streptavidin", "NTA-His", "Protein A", "Other"
        ])
        self.chip_type_combo.setFixedHeight(28)
        self.chip_type_combo.setMaximumWidth(150)
        self.chip_type_combo.setStyleSheet(
            "QComboBox { background: white; border: 1px solid rgba(0,0,0,0.1);"
            " border-radius: 4px; padding: 4px 8px; font-size: 12px; color: #1D1D1F; }"
            " QComboBox:focus { border-color: #007AFF; }"
            " QComboBox::drop-down { border: none; width: 20px; }"
            " QComboBox::down-arrow { image: none; border-left: 4px solid transparent;"
            " border-right: 4px solid transparent; border-top: 5px solid #86868B; margin-right: 8px; }"
        )
        chip_row.addWidget(self.chip_type_combo)

        _lot_icon = QLabel("📦")
        _lot_icon.setStyleSheet("font-size: 13px; color: #86868B; margin-left: 8px;")
        chip_row.addWidget(_lot_icon)

        self.lot_number_input = QLineEdit()
        self.lot_number_input.setPlaceholderText("Lot # (optional)")
        self.lot_number_input.setFixedHeight(28)
        self.lot_number_input.setMaximumWidth(130)
        self.lot_number_input.setStyleSheet(
            "QLineEdit { background: white; border: 1px solid rgba(0,0,0,0.1);"
            " border-radius: 4px; padding: 4px 8px; font-size: 12px; color: #1D1D1F; }"
            " QLineEdit:focus { border-color: #007AFF; }"
        )
        chip_row.addWidget(self.lot_number_input)

        chip_row.addStretch()

        self.new_sensor_btn = QPushButton("⬡ New Sensor Chip")
        self.new_sensor_btn.setFixedHeight(28)
        self.new_sensor_btn.setAutoDefault(False)  # Prevent Enter-key accidental activation
        self.new_sensor_btn.setDefault(False)
        self.new_sensor_btn.setStyleSheet(
            "QPushButton { background: #F2F2F7; border: 1px solid rgba(0,0,0,0.12);"
            " border-radius: 4px; padding: 4px 12px; font-size: 12px; color: #3C3C43; }"
            " QPushButton:hover { background: #E5E5EA; }"
            " QPushButton:pressed { background: #D1D1D6; }"
        )
        self.new_sensor_btn.clicked.connect(self._on_new_sensor_chip)
        chip_row.addWidget(self.new_sensor_btn)

        layout.addLayout(chip_row)

        # ═══════════════════════════════════════════════════════════════════
        # ZONE B — Template Gallery (collapses once first step is added)
        # ═══════════════════════════════════════════════════════════════════
        self._template_gallery_frame = QFrame()
        self._template_gallery_frame.setObjectName("templateGallery")
        self._template_gallery_frame.setStyleSheet(
            "QFrame#templateGallery { background: #F5F5F7; border-radius: 8px;"
            " border: 1px solid rgba(0,0,0,0.06); }"
        )
        gallery_layout = QVBoxLayout(self._template_gallery_frame)
        gallery_layout.setContentsMargins(14, 10, 14, 10)
        gallery_layout.setSpacing(8)

        self._gallery_toggle_btn = QPushButton("Quick start ▴")
        self._gallery_toggle_btn.setStyleSheet(
            "QPushButton { font-size: 12px; font-weight: 600; color: #86868B;"
            " background: transparent; border: none; text-align: left; padding: 0; }"
            " QPushButton:hover { color: #007AFF; }"
        )
        self._gallery_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._gallery_toggle_btn.clicked.connect(self._toggle_gallery_cards)
        gallery_layout.addWidget(self._gallery_toggle_btn)

        self._gallery_cards_frame = QFrame()
        self._gallery_cards_frame.setStyleSheet("QFrame { background: transparent; border: none; }")
        _cards_vbox = QVBoxLayout(self._gallery_cards_frame)
        _cards_vbox.setContentsMargins(0, 0, 0, 0)
        _cards_vbox.setSpacing(8)
        gallery_layout = _cards_vbox  # redirect remaining adds into cards frame
        gallery_layout.addWidget = _cards_vbox.addWidget  # noqa — already same obj

        _TEMPLATES = [
            # ── P4SPR / Manual injection ──────────────────────────────────────────
            # Regen and baseline are folded into neighboring cycles — user adds them
            # manually if needed. Prep phases collapse into one cycle per logical step.
            # One cycle = one thing to watch on the live sensorgram (~5–30 min).
            ("Binding", "5× Binding", [
                "Binding 8.5min [A:100nM] contact 300s  # Binding 1",
                "Binding 8.5min [A:100nM] contact 300s  # Binding 2",
                "Binding 8.5min [A:100nM] contact 300s  # Binding 3",
                "Binding 8.5min [A:100nM] contact 300s  # Binding 4",
                "Binding 8.5min [A:100nM] contact 300s  # Binding 5",
            ]),
            ("Amine", "Coupling → 5× binding", [
                # All prep steps in one cycle — activation, ligand, blocking
                "Immobilization 30min  # EDC/NHS → ligand → ethanolamine",
                "Binding 8.5min [A:100nM] contact 300s  # Binding 1",
                "Binding 8.5min [A:100nM] contact 300s  # Binding 2",
                "Binding 8.5min [A:100nM] contact 300s  # Binding 3",
                "Binding 8.5min [A:100nM] contact 300s  # Binding 4",
                "Binding 8.5min [A:100nM] contact 300s  # Binding 5",
            ]),
            ("✏ Custom", "Start with a blank step list", []),
            # ── additional templates (shown when "More" is expanded) ──────
            ("NTA", "His-tag capture → 5× binding", [
                "Immobilization 20min  # NiNTA + His-tagged ligand, then rinse",
                "Binding 8.5min [A:100nM] contact 300s  # Binding 1",
                "Binding 8.5min [A:100nM] contact 300s  # Binding 2",
                "Binding 8.5min [A:100nM] contact 300s  # Binding 3",
                "Binding 8.5min [A:100nM] contact 300s  # Binding 4",
                "Binding 8.5min [A:100nM] contact 300s  # Binding 5",
            ]),
            ("Biotin", "Streptavidin capture → 5× binding", [
                "Immobilization 20min  # Biotinylated ligand capture, then rinse",
                "Binding 8.5min [A:100nM] contact 300s  # Binding 1",
                "Binding 8.5min [A:100nM] contact 300s  # Binding 2",
                "Binding 8.5min [A:100nM] contact 300s  # Binding 3",
                "Binding 8.5min [A:100nM] contact 300s  # Binding 4",
                "Binding 8.5min [A:100nM] contact 300s  # Binding 5",
            ]),
            ("Conditions Scouting", "5× binding (screen conditions)", [
                "Binding 8.5min [A:100nM] contact 300s  # Condition 1",
                "Binding 8.5min [A:100nM] contact 300s  # Condition 2",
                "Binding 8.5min [A:100nM] contact 300s  # Condition 3",
                "Binding 8.5min [A:100nM] contact 300s  # Condition 4",
                "Binding 8.5min [A:100nM] contact 300s  # Condition 5",
            ]),
        ]

        _VISIBLE_COUNT = 3  # cards always shown
        _visible_templates = _TEMPLATES[:_VISIBLE_COUNT]
        _extra_templates = _TEMPLATES[_VISIBLE_COUNT:]

        _card_ss = (
            "QPushButton { background: white; border: 1.5px solid rgba(0,0,0,0.09);"
            " border-radius: 8px; padding: 10px 8px; font-size: 11px; color: #1D1D1F;"
            " text-align: left;"
            " font-family: -apple-system, 'SF Pro Text', 'Segoe UI', sans-serif; }"
            " QPushButton:hover { border-color: #007AFF; background: #F0F6FF; }"
            " QPushButton:pressed { background: #E3EDFF; }"
        )

        def _make_card(name, subtitle, lines, parent_row):
            from PySide6.QtWidgets import QLabel, QVBoxLayout
            from PySide6.QtCore import Qt as _Qt
            _name_flat = name.replace("\n", " ")
            _sub_flat  = subtitle.replace("\n", " ")
            _l = list(lines)

            card = QFrame()
            card.setFixedHeight(44)
            card.setMinimumWidth(100)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            card.setToolTip(_sub_flat)
            card.setStyleSheet(
                "QFrame { background: white; border: 1.5px solid rgba(0,0,0,0.09);"
                " border-radius: 8px; }"
                " QFrame:hover { border-color: #007AFF; background: #F0F6FF; }"
            )
            card.setCursor(Qt.CursorShape.PointingHandCursor)

            _inner = QVBoxLayout(card)
            _inner.setContentsMargins(10, 5, 10, 5)
            _inner.setSpacing(1)

            _name_lbl = QLabel(_name_flat)
            _name_lbl.setStyleSheet(
                "font-size: 11px; font-weight: 600; color: #1D1D1F;"
                " background: transparent; border: none;"
            )
            _name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

            _sub_lbl = QLabel(_sub_flat)
            _sub_lbl.setStyleSheet(
                "font-size: 10px; color: #86868B;"
                " background: transparent; border: none;"
            )
            _sub_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

            _inner.addWidget(_name_lbl)
            _inner.addWidget(_sub_lbl)

            def _on_click(event, l=_l, n=_name_flat):
                self._on_template_card_clicked(l, n)

            card.mousePressEvent = _on_click
            parent_row.addWidget(card)

        # ── primary row (always visible) ─────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)
        for name, subtitle, lines in _visible_templates:
            _make_card(name, subtitle, lines, cards_row)

        # "More ▾" toggle button
        _more_btn = QPushButton("More ▾")
        _more_btn.setToolTip("Show more quick-start templates")
        _more_btn.setFixedHeight(44)
        _more_btn.setFixedWidth(72)
        _more_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        _more_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 1.5px dashed rgba(0,0,0,0.15);"
            " border-radius: 8px; padding: 8px; font-size: 11px; color: #86868B; }"
            " QPushButton:hover { border-color: #007AFF; color: #007AFF; }"
            " QPushButton:checked { border-style: solid; border-color: #007AFF; color: #007AFF; }"
        )
        _more_btn.setCheckable(True)
        cards_row.addWidget(_more_btn)
        gallery_layout.addLayout(cards_row)

        # ── extra row (hidden until "More" is clicked) ───────────────────
        _extra_frame = QFrame()
        _extra_frame.setVisible(False)
        _extra_row = QHBoxLayout(_extra_frame)
        _extra_row.setContentsMargins(0, 0, 0, 0)
        _extra_row.setSpacing(8)
        for name, subtitle, lines in _extra_templates:
            _make_card(name, subtitle, lines, _extra_row)

        browse_btn = QPushButton("🔍 Browse saved…")
        browse_btn.setFixedHeight(44)
        browse_btn.setMinimumWidth(80)
        browse_btn.setToolTip("Browse saved cycle templates")
        browse_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        browse_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 1.5px dashed rgba(0,0,0,0.15);"
            " border-radius: 8px; padding: 8px; font-size: 11px; color: #86868B; }"
            " QPushButton:hover { border-color: #007AFF; color: #007AFF; }"
        )
        browse_btn.clicked.connect(self._on_browse_templates)
        _extra_row.addWidget(browse_btn)
        _extra_row.addStretch()
        gallery_layout.addWidget(_extra_frame)

        def _toggle_more(checked, btn=_more_btn, frame=_extra_frame):
            frame.setVisible(checked)
            btn.setText("Less ▴" if checked else "More ▾")

        _more_btn.toggled.connect(_toggle_more)

        # Add cards container to the outer gallery layout
        outer_gallery_layout = self._template_gallery_frame.layout()
        outer_gallery_layout.addWidget(self._gallery_cards_frame)

        layout.addWidget(self._template_gallery_frame)

        # ═══════════════════════════════════════════════════════════════════
        # ZONE C — Step List (the method; replaces dual-tab input + queue)
        # ═══════════════════════════════════════════════════════════════════
        steps_section = QVBoxLayout()
        steps_section.setSpacing(4)

        steps_hdr = QHBoxLayout()
        steps_hdr_lbl = QLabel("Method Steps")
        steps_hdr_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #1D1D1F;")
        steps_hdr.addWidget(steps_hdr_lbl)
        steps_hdr.addStretch()
        self.method_exp_time_value = QLabel("0 min")
        self.method_exp_time_value.setStyleSheet("font-size: 11px; color: #86868B;")
        steps_hdr.addWidget(self.method_exp_time_value)
        steps_section.addLayout(steps_hdr)

        table_style = (
            "QTableWidget { background: white; border: 1px solid rgba(0,0,0,0.08);"
            " border-radius: 6px; font-size: 12px; gridline-color: rgba(0,0,0,0.05); }"
            " QHeaderView::section { background: rgba(0,0,0,0.03); padding: 4px 6px;"
            " border: none; font-size: 11px; font-weight: 600; color: #86868B; }"
            " QTableWidget::item { padding: 4px 6px; }"
            " QTableWidget::item:selected { background: #E3EDFF; color: #1D1D1F; }"
        )
        self.method_table = DraggableMethodTable(on_row_moved=self._on_row_moved)
        self.method_table.setColumnCount(6)
        self.method_table.setHorizontalHeaderLabels(
            ["Type", "Duration", "Channel", "Concentration", "Contact time", "Note"]
        )
        # Header label updated by configure_for_hardware() when hardware is known
        self.method_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.method_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.method_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.method_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.method_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.method_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.method_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.method_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.method_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.method_table.itemChanged.connect(self._on_table_item_edited)
        self.method_table.verticalHeader().setVisible(True)
        self.method_table.setMinimumHeight(160)
        self.method_table.setStyleSheet(table_style)
        steps_section.addWidget(self.method_table)

        # Step footer controls
        step_footer = QHBoxLayout()
        step_footer.setSpacing(6)

        add_step_btn = QPushButton("+ Add step  ▾")
        add_step_btn.setFixedHeight(28)
        add_step_btn.setStyleSheet(
            "QPushButton { background: #007AFF; color: white; border: none; border-radius: 6px;"
            " padding: 4px 12px; font-size: 12px; font-weight: 600; }"
            " QPushButton:hover { background: #0051D5; }"
            " QPushButton:pressed { background: #003D99; }"
            " QPushButton::menu-indicator { width: 0; height: 0; }"
        )
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction
        add_step_menu = QMenu(add_step_btn)
        for _step_type, _default_line in [
            ("Baseline",       "Baseline 5min"),
            ("Binding",        "Binding 8.5min [A:100nM] contact 300s"),
            ("Regeneration",   "Regeneration 30sec [ALL:50mM]"),
            ("Immobilization", "Immobilization 30min"),
            ("Blocking",       "Blocking 4min"),
            ("Wash",           "Wash 30sec"),
            ("Other",          "Other 2min"),
        ]:
            _act = QAction(_step_type, add_step_btn)
            _line_copy = _default_line
            _act.triggered.connect(lambda checked=False, l=_line_copy: self._add_single_step(l))
            add_step_menu.addAction(_act)
        add_step_btn.setMenu(add_step_menu)
        step_footer.addWidget(add_step_btn)

        step_footer.addSpacing(8)

        _SVG_COG = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
                    '<path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" stroke="#86868B" stroke-width="2"/>'
                    '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06'
                    'a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65'
                    ' 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06'
                    'A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65'
                    ' 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65'
                    ' 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0'
                    ' 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65'
                    ' 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"'
                    ' stroke="#86868B" stroke-width="2"/></svg>')

        _btn_ss = (
            "QPushButton { background: white; color: #1D1D1F; border: 1px solid rgba(0,0,0,0.1);"
            " border-radius: 4px; padding: 4px 10px; font-size: 12px; }"
            " QPushButton:hover { background: #F5F5F7; }"
            " QPushButton:disabled { color: #C7C7CC; border-color: rgba(0,0,0,0.05); }"
        )

        self.undo_btn = QPushButton("Undo")
        self.undo_btn.setIcon(_create_svg_icon(_SVG_UNDO, 14))
        self.undo_btn.setIconSize(QSize(14, 14))
        self.undo_btn.setFixedHeight(28)
        self.undo_btn.setEnabled(False)
        self.undo_btn.setToolTip("Undo last action (Ctrl+Z)")
        self.undo_btn.setStyleSheet(_btn_ss)
        step_footer.addWidget(self.undo_btn)

        self.redo_btn = QPushButton("Redo")
        self.redo_btn.setIcon(_create_svg_icon(_SVG_REDO, 14))
        self.redo_btn.setIconSize(QSize(14, 14))
        self.redo_btn.setFixedHeight(28)
        self.redo_btn.setEnabled(False)
        self.redo_btn.setToolTip("Redo last action (Ctrl+Shift+Z)")
        self.redo_btn.setStyleSheet(_btn_ss)
        step_footer.addWidget(self.redo_btn)

        _sep_v = QLabel("|")
        _sep_v.setStyleSheet("color: rgba(0,0,0,0.15); margin: 0 2px;")
        step_footer.addWidget(_sep_v)

        self.delete_cycle_btn = QPushButton("Delete")
        self.delete_cycle_btn.setIcon(_create_svg_icon(_SVG_TRASH, 14))
        self.delete_cycle_btn.setIconSize(QSize(14, 14))
        self.delete_cycle_btn.setFixedHeight(28)
        self.delete_cycle_btn.setEnabled(False)
        self.delete_cycle_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #FF3B30;"
            " border: 1px solid rgba(255,59,48,0.3); border-radius: 4px;"
            " padding: 4px 10px; font-size: 12px; }"
            " QPushButton:hover { background: rgba(255,59,48,0.1); }"
            " QPushButton:disabled { color: #C7C7CC; border-color: rgba(0,0,0,0.1); }"
        )
        self.delete_cycle_btn.clicked.connect(self._on_delete_selected)
        step_footer.addWidget(self.delete_cycle_btn)

        self.move_up_btn = QPushButton()
        self.move_up_btn.setIcon(_create_svg_icon(_SVG_CHEVRON_UP, 16))
        self.move_up_btn.setIconSize(QSize(16, 16))
        self.move_up_btn.setFixedSize(28, 28)
        self.move_up_btn.setEnabled(False)
        self.move_up_btn.setStyleSheet(
            "QPushButton { background: #F2F2F7; border: none; border-radius: 4px; }"
            " QPushButton:hover { background: #E5E5EA; }"
            " QPushButton:disabled { background: #F2F2F7; color: #C7C7CC; }"
        )
        self.move_up_btn.clicked.connect(self._on_move_up)
        step_footer.addWidget(self.move_up_btn)

        self.move_down_btn = QPushButton()
        self.move_down_btn.setIcon(_create_svg_icon(_SVG_CHEVRON_DOWN, 16))
        self.move_down_btn.setIconSize(QSize(16, 16))
        self.move_down_btn.setFixedSize(28, 28)
        self.move_down_btn.setEnabled(False)
        self.move_down_btn.setStyleSheet(
            "QPushButton { background: #F2F2F7; border: none; border-radius: 4px; }"
            " QPushButton:hover { background: #E5E5EA; }"
            " QPushButton:disabled { background: #F2F2F7; color: #C7C7CC; }"
        )
        self.move_down_btn.clicked.connect(self._on_move_down)
        step_footer.addWidget(self.move_down_btn)

        self.clear_method_btn = QPushButton("Clear All")
        self.clear_method_btn.setIcon(_create_svg_icon(_SVG_CLEAR, 14))
        self.clear_method_btn.setIconSize(QSize(14, 14))
        self.clear_method_btn.setFixedHeight(28)
        self.clear_method_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #86868B;"
            " border: 1px solid rgba(0,0,0,0.1); border-radius: 4px;"
            " padding: 4px 10px; font-size: 12px; }"
            " QPushButton:hover { background: rgba(0,0,0,0.05); }"
        )
        self.clear_method_btn.clicked.connect(self._on_clear_method)
        step_footer.addWidget(self.clear_method_btn)

        self.method_count_label = QLabel("0 cycles")
        self.method_count_label.setStyleSheet("font-size: 11px; color: #86868B;")
        step_footer.addWidget(self.method_count_label)
        step_footer.addStretch()

        self._settings_btn = QPushButton()
        self._settings_btn.setIcon(_create_svg_icon(_SVG_COG, 14))
        self._settings_btn.setIconSize(QSize(14, 14))
        self._settings_btn.setFixedSize(24, 24)
        self._settings_btn.setToolTip("Method settings (mode, detection)")
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; }"
            " QPushButton:hover { background: rgba(0,0,0,0.05); border-radius: 4px; }"
        )
        self._settings_btn.setCheckable(True)
        self._settings_btn.toggled.connect(self._toggle_advanced_settings)
        step_footer.addWidget(self._settings_btn)

        steps_section.addLayout(step_footer)
        layout.addLayout(steps_section)

        # Hidden stub for details_table (keeps _refresh_method_table guards working)
        self.details_table = QTableWidget()
        self.details_table.hide()
        self.method_cycle_count_value = QLabel()
        self.method_cycle_count_value.hide()

        # ── Advanced settings (collapsible via ⚙ button) ───────────────────
        _combo_ss = (
            "QComboBox { background: white; border: 1px solid rgba(0,0,0,0.12);"
            " border-radius: 4px; padding: 2px 6px; font-size: 11px; color: #1D1D1F; }"
            " QComboBox:focus { border-color: #007AFF; }"
            " QComboBox::drop-down { border: none; width: 18px; }"
            " QComboBox::down-arrow { image: none; border-left: 3px solid transparent;"
            " border-right: 3px solid transparent; border-top: 4px solid #86868B; margin-right: 6px; }"
        )
        _lbl_ss = "font-size: 11px; color: #86868B; font-weight: 500;"

        self._adv_settings_frame = QFrame()
        self._adv_settings_frame.setObjectName("advSettings")
        self._adv_settings_frame.setVisible(False)
        self._adv_settings_frame.setStyleSheet(
            "QFrame#advSettings { background: #F9F9FB; border: 1px solid rgba(0,0,0,0.08);"
            " border-radius: 6px; }"
        )
        adv_lay = QHBoxLayout(self._adv_settings_frame)
        adv_lay.setContentsMargins(10, 6, 10, 6)
        adv_lay.setSpacing(8)

        _m = QLabel("Mode:")
        _m.setStyleSheet(_lbl_ss)
        adv_lay.addWidget(_m)
        self.mode_combo.setStyleSheet(_combo_ss)
        adv_lay.addWidget(self.mode_combo)

        _sep_adv = QFrame()
        _sep_adv.setFrameShape(QFrame.Shape.VLine)
        _sep_adv.setStyleSheet("color: rgba(0,0,0,0.08);")
        _sep_adv.setFixedHeight(18)
        adv_lay.addWidget(_sep_adv)

        _dev = QLabel("Device:")
        _dev.setStyleSheet(_lbl_ss)
        adv_lay.addWidget(_dev)
        self.hw_label.setStyleSheet("font-size: 11px; color: #1D1D1F; font-weight: 600;")
        adv_lay.addWidget(self.hw_label)
        adv_lay.addStretch()

        _det = QLabel("Detection:")
        _det.setStyleSheet(_lbl_ss)
        adv_lay.addWidget(_det)
        self.detection_combo.setStyleSheet(_combo_ss)
        adv_lay.addWidget(self.detection_combo)
        layout.addWidget(self._adv_settings_frame)

        # ═══════════════════════════════════════════════════════════════════
        # ZONE D — Sparq Bar (single always-visible query input)
        # ═══════════════════════════════════════════════════════════════════
        sparq_frame = QFrame()
        sparq_frame.setObjectName("sparqFrame")
        sparq_frame.setStyleSheet(
            "QFrame#sparqFrame { background: #FFFBF0; border: 1.5px solid #FFD60A;"
            " border-radius: 8px; }"
        )
        sparq_row = QHBoxLayout(sparq_frame)
        sparq_row.setContentsMargins(10, 6, 10, 6)
        sparq_row.setSpacing(8)

        sparq_lbl = QLabel("⚡ Sparq:")
        sparq_lbl.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #B8860B; background: transparent;"
            " font-family: -apple-system, 'SF Pro Text', 'Segoe UI', sans-serif;"
        )
        sparq_row.addWidget(sparq_lbl)

        self._sparq_input = QLineEdit()
        self._sparq_input.setPlaceholderText(
            'e.g. "add 5 kinetic cycles"  ·  "titration"  ·  "amine coupling"  ·  "build 3"'
        )
        self._sparq_input.setStyleSheet(
            "QLineEdit { background: transparent; border: none; font-size: 12px; color: #1D1D1F; }"
        )
        self._sparq_input.returnPressed.connect(self._on_sparq_ask)
        sparq_row.addWidget(self._sparq_input, 1)

        self._sparq_ask_btn = QPushButton("Ask")
        self._sparq_ask_btn.setFixedSize(50, 26)
        self._sparq_ask_btn.setAutoDefault(False)
        self._sparq_ask_btn.setDefault(False)
        self._sparq_ask_btn.setStyleSheet(
            "QPushButton { background: #FFD60A; color: #1D1D1F; border: none;"
            " border-radius: 6px; font-size: 11px; font-weight: 700; }"
            " QPushButton:hover { background: #E6C009; }"
            " QPushButton:pressed { background: #CCB008; }"
        )
        self._sparq_ask_btn.clicked.connect(self._on_sparq_ask)
        sparq_row.addWidget(self._sparq_ask_btn)
        layout.addWidget(sparq_frame)

        # Sparq prose-response area — shown when the answer engine replies with info text
        self._sparq_response_lbl = QLabel("")
        self._sparq_response_lbl.setVisible(False)
        self._sparq_response_lbl.setWordWrap(True)
        self._sparq_response_lbl.setStyleSheet(
            "QLabel { background: #F5F5F7; border: 1px solid #D1D1D6;"
            " border-radius: 6px; padding: 8px 10px; font-size: 11px; color: #1D1D1F; }"
        )
        layout.addWidget(self._sparq_response_lbl)

        # ── Text Mode (hidden, power-user escape hatch) ────────────────────
        self._text_mode_toggle = QPushButton("⋯ Text mode")
        self._text_mode_toggle.setFlat(True)
        self._text_mode_toggle.setCheckable(True)
        self._text_mode_toggle.setStyleSheet(
            "QPushButton { background: transparent; color: #86868B; border: none;"
            " font-size: 11px; text-decoration: underline; padding: 0; }"
            " QPushButton:hover { color: #007AFF; }"
            " QPushButton:checked { color: #007AFF; }"
        )
        self._text_mode_toggle.toggled.connect(self._toggle_text_mode_panel)
        layout.addWidget(self._text_mode_toggle, alignment=Qt.AlignmentFlag.AlignRight)

        self._text_mode_panel = QFrame()
        self._text_mode_panel.setVisible(False)
        text_panel_lay = QVBoxLayout(self._text_mode_panel)
        text_panel_lay.setContentsMargins(0, 0, 0, 0)
        text_panel_lay.setSpacing(4)

        _text_hdr = QHBoxLayout()
        _text_hdr_lbl = QLabel("Power Mode — one cycle per line")
        _text_hdr_lbl.setStyleSheet("font-size: 11px; color: #86868B;")
        _text_hdr.addWidget(_text_hdr_lbl)
        _text_hdr.addStretch()
        _help_btn = QPushButton("?")
        _help_btn.setFixedSize(20, 20)
        _help_btn.setStyleSheet(
            "QPushButton { background: #007AFF; color: white; border: none; border-radius: 10px;"
            " font-size: 11px; font-weight: bold; }"
            " QPushButton:hover { background: #0051D5; }"
        )
        _help_btn.clicked.connect(self._show_notes_help)
        _text_hdr.addWidget(_help_btn)
        text_panel_lay.addLayout(_text_hdr)

        self.notes_input = NotesTextEdit()
        self.notes_input._parent_dialog = self
        self.notes_input.setPlaceholderText(
            "Baseline 5min\n"
            "Binding 8.5min A:100nM contact 300s\n"
            "Regeneration 30sec ALL:50mM\n\n"
            "Ctrl+Enter to add  ·  ↑/↓ history  ·  @preset_name  ·  !save name"
        )
        self.notes_input.setMinimumHeight(90)
        self.notes_input.setStyleSheet(
            "QPlainTextEdit { background: white; border: 1px solid rgba(0,0,0,0.1);"
            " border-radius: 6px; padding: 8px; font-size: 12px;"
            " font-family: 'Consolas', 'Monaco', monospace; }"
            " QPlainTextEdit:focus { border-color: #007AFF; }"
        )
        self.notes_input.textChanged.connect(self._update_char_count)
        text_panel_lay.addWidget(self.notes_input)

        _add_txt_row = QHBoxLayout()
        _add_txt_row.addStretch()
        _add_from_text_btn = QPushButton("→ Add to method")
        _add_from_text_btn.setFixedHeight(28)
        _add_from_text_btn.setStyleSheet(
            "QPushButton { background: #007AFF; color: white; border: none; border-radius: 6px;"
            " padding: 4px 16px; font-size: 12px; font-weight: 600; }"
            " QPushButton:hover { background: #0051D5; }"
        )
        _add_from_text_btn.clicked.connect(self._on_add_to_method)
        _add_txt_row.addWidget(_add_from_text_btn)
        text_panel_lay.addLayout(_add_txt_row)

        _build_sc = QShortcut(QKeySequence("Ctrl+Return"), self.notes_input)
        _build_sc.activated.connect(self._on_add_to_method)
        layout.addWidget(self._text_mode_panel)

        # ── Overnight Mode checkbox ────────────────────────────────────────
        overnight_row = QHBoxLayout()
        overnight_row.setContentsMargins(0, 2, 0, 0)
        self.overnight_mode_check = QCheckBox("🌙 Overnight Mode")
        self.overnight_mode_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.overnight_mode_check.setToolTip("System runs continuously without user interaction")
        try:
            import settings as root_settings
            self.overnight_mode_check.setChecked(getattr(root_settings, "OVERNIGHT_MODE", False))
        except Exception:
            pass
        self.overnight_mode_check.stateChanged.connect(self._on_overnight_mode_changed)
        self.overnight_mode_check.setStyleSheet(
            "QCheckBox { spacing: 4px; font-size: 10px; font-weight: 500; color: #86868B;"
            " font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif; }"
            " QCheckBox::indicator { width: 14px; height: 14px; border-radius: 2px;"
            " border: 1px solid rgba(0,0,0,0.15); background: white; }"
            " QCheckBox::indicator:checked { background: #007AFF; border-color: #007AFF; }"
            " QCheckBox::indicator:hover { border-color: #007AFF; }"
        )
        overnight_row.addWidget(self.overnight_mode_check)
        overnight_row.addStretch()
        layout.addLayout(overnight_row)

        # ── Separator ──────────────────────────────────────────────────────
        _sep_h = QFrame()
        _sep_h.setFrameShape(QFrame.Shape.HLine)
        _sep_h.setStyleSheet("background: rgba(0,0,0,0.08);")
        layout.addWidget(_sep_h)

        # ── Footer buttons ─────────────────────────────────────────────────
        button_row = QHBoxLayout()

        self.close_btn = QPushButton("Cancel")
        self.close_btn.setFixedHeight(40)
        self.close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #86868B;"
            " border: 1px solid rgba(0,0,0,0.1); border-radius: 8px;"
            " padding: 8px 20px; font-size: 13px; font-weight: 600; }"
            " QPushButton:hover { background: rgba(0,0,0,0.05); }"
        )
        self.close_btn.clicked.connect(self.reject)
        button_row.addWidget(self.close_btn)

        self.save_btn = QPushButton("💾 Save")
        self.save_btn.setFixedHeight(40)
        self.save_btn.setToolTip("Save current method to file")
        self.save_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #34C759;"
            " border: 1px solid rgba(52,199,89,0.3); border-radius: 8px;"
            " padding: 8px 14px; font-size: 13px; font-weight: 600; }"
            " QPushButton:hover { background: rgba(52,199,89,0.1); border-color: #34C759; }"
        )
        self.save_btn.clicked.connect(self._on_save_method)
        button_row.addWidget(self.save_btn)

        self.load_btn = QPushButton("📂 Load")
        self.load_btn.setFixedHeight(40)
        self.load_btn.setToolTip("Load method from file")
        self.load_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #007AFF;"
            " border: 1px solid rgba(0,122,255,0.3); border-radius: 8px;"
            " padding: 8px 14px; font-size: 13px; font-weight: 600; }"
            " QPushButton:hover { background: rgba(0,122,255,0.1); border-color: #007AFF; }"
        )
        self.load_btn.clicked.connect(self._on_load_method)
        button_row.addWidget(self.load_btn)

        button_row.addStretch()

        self._copy_schedule_btn = QPushButton("📋 Copy Schedule")
        self._copy_schedule_btn.setFixedHeight(40)
        self._copy_schedule_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_schedule_btn.setToolTip("Copy injection schedule to clipboard")
        self._copy_schedule_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #007AFF;"
            " border: 1px solid rgba(0,122,255,0.3); border-radius: 8px;"
            " padding: 8px 14px; font-size: 13px; font-weight: 600; }"
            " QPushButton:hover { background: rgba(0,122,255,0.08); }"
        )
        self._copy_schedule_btn.clicked.connect(self._copy_schedule_to_clipboard)
        button_row.addWidget(self._copy_schedule_btn)

        self.queue_btn = QPushButton("Add to Queue")
        self.queue_btn.setIcon(_create_svg_icon(_SVG_CLIPBOARD_WHITE, 18))
        self.queue_btn.setIconSize(QSize(18, 18))
        self.queue_btn.setFixedHeight(40)
        self.queue_btn.setStyleSheet(
            "QPushButton { background: #007AFF; color: white; border: none; border-radius: 8px;"
            " padding: 8px 20px; font-size: 14px; font-weight: 600; }"
            " QPushButton:hover { background: #0051D5; }"
            " QPushButton:pressed { background: #003D99; }"
        )
        self.queue_btn.clicked.connect(self._on_push_to_queue)
        button_row.addWidget(self.queue_btn)

        layout.addLayout(button_row)

        # Apply initial settings state
        self._on_mode_changed(self.mode_combo.currentText())
        self._update_gallery_visibility()

    # ── New 3-zone helper methods ──────────────────────────────────────────

    def _on_template_card_clicked(self, lines: list, name: str):
        """Load a built-in template into the step list."""
        if self._local_cycles:
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "Replace Method?",
                f"Load '{name}' template? Current steps will be replaced.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._local_cycles.clear()
        for line in lines:
            if line.strip() and not line.strip().startswith("#"):
                cycle, _ = self._build_cycle_from_text(line.strip())
                self._local_cycles.append(cycle)
        self.method_name_input.setText(name.replace("\n", " "))
        self._refresh_method_table()

    def _add_single_step(self, line: str):
        """Add one pre-configured step from the '+ Add step' dropdown."""
        cycle, _ = self._build_cycle_from_text(line)
        self._local_cycles.append(cycle)
        self._refresh_method_table()
        # Select the newly added row
        self.method_table.selectRow(self.method_table.rowCount() - 1)

    def _sparq_show_response(self, text: str) -> None:
        """Display an info response from the answer engine below the Sparq bar."""
        if not hasattr(self, '_sparq_response_lbl'):
            return
        # Strip markdown bold markers for plain display
        import re as _re
        plain = _re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        self._sparq_response_lbl.setText(plain)
        self._sparq_response_lbl.setVisible(True)
        # Auto-clear after 12 seconds
        QTimer.singleShot(12_000, lambda: (
            self._sparq_response_lbl.setVisible(False)
            if hasattr(self, '_sparq_response_lbl') else None
        ))

    def _on_sparq_ask(self):
        """Handle Sparq bar query — generate cycles (pattern match) or show answer (engine)."""
        # Always ensure button is re-enabled on entry (guards against stuck state)
        self._sparq_ask_btn.setEnabled(True)

        query = self._sparq_input.text().strip()
        if not query:
            # Flash the input border briefly to indicate it needs text
            self._sparq_input.setStyleSheet(
                "QLineEdit { background: transparent; border: none; font-size: 12px; color: #FF3B30; }"
            )
            QTimer.singleShot(600, lambda: self._sparq_input.setStyleSheet(
                "QLineEdit { background: transparent; border: none; font-size: 12px; color: #1D1D1F; }"
            ))
            return

        self._sparq_ask_btn.setText("⏳")
        self._sparq_ask_btn.setEnabled(False)

        try:
            # Layer 1: pattern-based cycle generation (returns cycle-syntax lines)
            cycle_lines = self._try_sparq_patterns(query)
            if cycle_lines:
                lines_added = 0
                for line in cycle_lines.split("\n"):
                    s = line.strip()
                    if s and not s.startswith("#"):
                        cycle, _ = self._build_cycle_from_text(s)
                        self._local_cycles.append(cycle)
                        lines_added += 1
                if lines_added:
                    self._refresh_method_table()
                    self._sparq_input.clear()
                    self._sparq_ask_btn.setText(f"✓ +{lines_added}")
                    self._sparq_ask_btn.setEnabled(True)
                    QTimer.singleShot(1500, lambda: self._sparq_ask_btn.setText("Ask"))
                    return

            # Layer 2: answer engine — returns prose, display it (do NOT parse as cycles)
            if self._answer_engine is not None:
                try:
                    answer, _ = self._answer_engine.generate_answer(query, context="method_builder")
                    if answer:
                        self._sparq_show_response(answer)
                        self._sparq_input.clear()
                        self._sparq_ask_btn.setText("Ask")
                        self._sparq_ask_btn.setEnabled(True)
                        return
                except Exception:
                    pass

            # Nothing matched
            self._sparq_input.setPlaceholderText(
                'Try: "binding", "kinetics", "titration", "amine coupling", "build 5"'
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Sparq bar error: {e}")

        self._sparq_ask_btn.setText("Ask")
        self._sparq_ask_btn.setEnabled(True)

    def _try_sparq_patterns(self, text: str):
        """Method-pattern matching for the Sparq bar.

        P4SPR / Manual philosophy: one cycle = one watchable region (~5–10 min).
        Each binding rep is its own short cycle so the user sees a clear signal
        event per queue step. Alignment and export are done in Edits afterward.
        """
        t = text.lower().strip()
        # "build N" → N binding cycles of 8.5min each (no regen/baseline padding)
        m = re.search(r'build.*?(\d+)', t)
        if m:
            n = int(m.group(1))
            lines = []
            for i in range(n):
                lines.append(f"Binding 8.5min [A:100nM] contact 300s  # Binding {i + 1}")
            return "\n".join(lines)
        if re.search(r'titration|dose.?response|serial dilution|concentration series', t):
            return (
                "Binding 8.5min [A:10nM] contact 300s\n"
                "Binding 8.5min [A:50nM] contact 300s\n"
                "Binding 8.5min [A:100nM] contact 300s\n"
                "Binding 8.5min [A:500nM] contact 300s"
            )
        if re.search(r'amine coupling|amine|coupling', t):
            n_match = re.search(r'(\d+)', t)
            n = int(n_match.group(1)) if n_match else 5
            # All prep in one immobilization cycle; each binding rep is its own cycle
            lines = ["Immobilization 30min  # EDC/NHS → ligand → ethanolamine"]
            for i in range(n):
                lines.append(f"Binding 8.5min [A:100nM] contact 300s  # Binding {i + 1}")
            return "\n".join(lines)
        if re.search(r'baseline|start|equilibrat', t):
            return "Baseline 5min"
        if re.search(r'regenerat|regen|clean|strip', t):
            return "Regeneration 30sec [ALL:50mM]"
        if re.search(r'binding|association|inject|sample', t):
            return "Binding 8.5min [A:100nM] contact 300s"
        if re.search(r'immobiliz|immob|attach|ligand', t):
            return "Immobilization 30min"
        if re.search(r'wash|rinse', t):
            return "Wash 30sec"
        if re.search(r'block', t):
            return "Blocking 5min"
        return None

    def _update_gallery_visibility(self):
        """Collapse template gallery to header-only when steps exist; expand when empty."""
        if not hasattr(self, '_template_gallery_frame') or not hasattr(self, '_gallery_cards_frame'):
            return
        has_cycles = len(self._local_cycles) > 0
        if has_cycles:
            # Auto-collapse cards — header toggle remains visible for recall
            self._gallery_cards_frame.setVisible(False)
            if hasattr(self, '_gallery_toggle_btn'):
                self._gallery_toggle_btn.setText("Quick start ▾")
        else:
            # Empty state — expand so gallery is the first thing users see
            self._gallery_cards_frame.setVisible(True)
            if hasattr(self, '_gallery_toggle_btn'):
                self._gallery_toggle_btn.setText("Quick start ▴")

    def _toggle_gallery_cards(self):
        """Toggle the quick-start card rows open/closed."""
        if not hasattr(self, '_gallery_cards_frame'):
            return
        visible = not self._gallery_cards_frame.isVisible()
        self._gallery_cards_frame.setVisible(visible)
        self._gallery_toggle_btn.setText("Quick start ▴" if visible else "Quick start ▾")

    def _toggle_text_mode_panel(self, checked: bool):
        """Show or hide the power-user text input panel."""
        if hasattr(self, '_text_mode_panel'):
            self._text_mode_panel.setVisible(checked)

    def _on_browse_templates(self):
        """Open the full CycleTemplateDialog for user-saved templates."""
        try:
            from affilabs.widgets.cycle_template_dialog import CycleTemplateDialog
            from affilabs.services.cycle_template_storage import CycleTemplateStorage
            storage = CycleTemplateStorage()
            dlg = CycleTemplateDialog(storage, parent=self)
            if dlg.exec():
                template = dlg.get_selected_template()
                if template:
                    cycle = template.to_cycle()
                    self._local_cycles.append(cycle)
                    self._refresh_method_table()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Browse templates failed: {e}")

    def _update_char_count(self):
        """Enforce 1500 character limit."""
        text = self.notes_input.toPlainText()
        if len(text) > 1500:
            self.notes_input.setPlainText(text[:1500])
            cursor = self.notes_input.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.notes_input.setTextCursor(cursor)

    def _show_notes_help(self):
        """Show help dialog for notes syntax."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton

        help_text = """
<h3>How to Build a Method</h3>

<p>A <b>method</b> is a sequence of timed cycles that automates your SPR experiment.
You build it here, push it to the queue, then press <b>Start Run</b> to execute.
Each cycle runs for its set duration and auto-advances to the next.</p>

<hr/>

<h4>Step-by-Step Workflow</h4>
<ol>
<li>Click <b>+ Build Method</b> in the sidebar</li>
<li>Type one or more cycle lines in the Note field (one per line)</li>
<li>Click <b>➕ Add to Method</b> — cycles appear in the table below</li>
<li>Reorder with <b>↑ / ↓</b>, delete with <b>🗑 Delete</b>, undo/redo as needed</li>
<li>Review the <b>Details</b> tab to inspect injection settings per cycle</li>
<li>Click <b>📋 Push to Queue</b> — cycles move to the main Cycle Queue</li>
<li>Use <b>📋 Copy Schedule</b> (next to Push) to print a trackable injection checklist</li>
<li>Press <b>▶ Start Run</b> in the sidebar — cycles run automatically in order</li>
<li>After the last cycle, the system enters <b>Auto-Read</b> (continuous 2-hour monitoring)</li>
</ol>

<hr/>

<h4>Cycle Syntax</h4>
<p><code>Type Duration [ChannelTags] contact Ns partial injection</code></p>

<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse; font-size:12px;">
<tr style="background:#f0f0f0;"><th>Part</th><th>Required?</th><th>Description</th></tr>
<tr><td><b>Type</b></td><td>Yes</td><td>Baseline, Binding, Kinetic, Regeneration, Immobilization, Blocking, Wash, Other</td></tr>
<tr><td><b>Duration</b></td><td>Yes</td><td>e.g. <code>5min</code>, <code>30sec</code>, <code>2h</code>, <code>overnight</code> (= 8 h). Default 5 min if omitted.</td></tr>
<tr><td><b>[Tags]</b></td><td>No</td><td>Channel + optional concentration: <code>A:100nM</code>  <code>ALL:100nM</code>  <code>B:50µM</code> (brackets optional)</td></tr>
<tr><td><b>contact Ns</b></td><td>No</td><td>Injection contact time: <code>contact 180s</code>, <code>contact 3min</code>, <code>contact 5h</code>, or shorthand <code>ct 180s</code>. ⚠️ Auto-enables Overnight Mode if > 3 hours</td></tr>
<tr><td><b>partial</b></td><td>No</td><td>Use partial injection (30 µL spike) instead of simple (full loop)</td></tr>
<tr><td><b>manual / automated</b></td><td>No</td><td>Override injection mode for this cycle</td></tr>
<tr><td><b>detection priority/off</b></td><td>No</td><td>Override injection-detection sensitivity for this cycle</td></tr>
<tr><td><b>channels AC</b></td><td>No</td><td>Override target channels (e.g. <code>channels BD</code>)</td></tr>
<tr><td><b>fr N</b></td><td>No</td><td>Flow rate in µL/min: <code>fr 50</code> (shorthand for <code>flow</code>)</td></tr>
<tr><td><b>iv N</b></td><td>No</td><td>Injection volume in µL: <code>iv 25</code> (shorthand for <code>injection volume</code>)</td></tr>
</table>

<hr/>

<h4>⚡ Quick Syntax Reference</h4>
<p><b>Cycle Type Abbreviations:</b></p>
<table border="1" cellpadding="3" cellspacing="0" style="border-collapse:collapse; font-size:11px;">
<tr><td><code>BL</code></td><td>Baseline</td></tr>
<tr><td><code>BN</code></td><td>Binding</td></tr>
<tr><td><code>IM</code></td><td>Immobilization</td></tr>
<tr><td><code>BK</code></td><td>Blocking</td></tr>
<tr><td><code>KN</code></td><td>Kinetic</td></tr>
<tr><td><code>CN</code></td><td>Concentration</td></tr>
<tr><td><code>RG</code></td><td>Regeneration</td></tr>
<tr><td><code>AS</code></td><td>Association</td></tr>
<tr><td><code>DS</code></td><td>Dissociation</td></tr>
<tr><td><code>WS</code></td><td>Wash</td></tr>
<tr><td><code>OT</code></td><td>Other</td></tr>
</table>

<p><b>Duration Shortcuts:</b></p>
<ul style="margin-top:4px; margin-bottom:12px;">
<li><code>5s</code>, <code>30sec</code> — Seconds</li>
<li><code>5m</code>, <code>30min</code> — Minutes</li>
<li><code>2h</code>, <code>5hr</code> — Hours (auto-enables Overnight Mode if &gt; 3h)</li>
<li><code>overnight</code> — 8 hours (default for long equilibration)</li>
</ul>

<p><b>Parameter Shorthand:</b></p>
<ul style="margin-top:4px; margin-bottom:12px;">
<li><code>flow 50</code> or <code>fr 50</code> — Flow rate in µL/min</li>
<li><code>iv 25</code> — Injection volume in µL</li>
<li><code>contact 5m</code> or <code>ct 5m</code> — Contact time with auto-conversion (e.g., <code>ct 180s</code>, <code>ct 3min</code>, <code>ct 5h</code>)</li>
</ul>

<p><b>Injection Modifiers:</b></p>
<ul style="margin-top:4px; margin-bottom:12px;">
<li><code>partial</code> — 30 µL spike injection (vs full loop)</li>
<li><code>manual</code> — Manual syringe injection</li>
<li><code>automated</code> — Peristaltic pump injection</li>
<li><code>detection priority</code> — High-sensitivity detection</li>
<li><code>detection off</code> — Disable detection for this cycle</li>
</ul>

<p><b>Channel Selection:</b></p>
<ul style="margin-top:4px; margin-bottom:12px;">
<li><code>channels A</code>, <code>channels BD</code>, <code>channels ALL</code> — Target specific channels</li>
<li><code>A:100nM</code>, <code>B:50µM</code> — Per-channel concentration tags</li>
</ul>

<p><b>Full Example:</b> <code>Binding 5min A:100nM fr 50 iv 25 contact 3m partial</code></p>

<hr/>

<h4>Cycle Types Explained</h4>
<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse; font-size:12px;">
<tr style="background:#f0f0f0;"><th>Type</th><th>Injection</th><th>Default Contact</th><th>Purpose</th></tr>
<tr><td><b>Baseline</b></td><td>None</td><td>—</td><td>Running buffer only — establish stable signal</td></tr>
<tr><td><b>Binding</b></td><td>Simple (or partial)</td><td>300 s (5 min)</td><td>Manual injection — incubate analyte for a set contact time (no dissociation)</td></tr>
<tr><td><b>Kinetic</b></td><td>Simple (or partial)</td><td>300 s (5 min)</td><td>Flow injection — association + dissociation phases (requires flowrate)</td></tr>
<tr><td><b>Regeneration</b></td><td>Simple</td><td>30 s</td><td>Strip bound analyte, restore baseline</td></tr>
<tr><td><b>Immobilization</b></td><td>Simple</td><td>User-specified</td><td>Attach ligand to sensor surface</td></tr>
<tr><td><b>Blocking</b></td><td>Simple</td><td>User-specified</td><td>Block unreacted surface sites</td></tr>
<tr><td><b>Wash</b></td><td>Simple</td><td>User-specified</td><td>Rinse flow path between steps</td></tr>
<tr><td><b>Other</b></td><td>None</td><td>—</td><td>Custom step (activation, equilibration, etc.)</td></tr>
</table>
<p><b>All injections start at 20 s</b> into the cycle (fixed delay for baseline stabilization).<br/>
When <b>contact time expires</b>, a wash flag is automatically placed to mark the transition.</p>

<hr/>

<h4>Concentration &amp; Unit Tags</h4>
<p>Tag format: <code>Channel:ValueUnits</code> or <code>[Channel:ValueUnits]</code> (brackets optional)</p>
<ul>
<li>Channels: <code>A</code>, <code>B</code>, <code>C</code>, <code>D</code>, <code>ALL</code></li>
<li>Units: <code>nM</code>, <code>µM</code>, <code>pM</code>, <code>mM</code>, <code>M</code>, <code>mg/mL</code>, <code>µg/mL</code>, <code>ng/mL</code></li>
<li>Examples: <code>A:100nM</code>  <code>B:50µM</code>  <code>ALL:25pM</code></li>
<li>Multiple tags per line: <code>A:100nM B:50nM</code> — different concentration per channel</li>
</ul>

<hr/>

<h4>In-Place Modifiers — <code>#N</code> Commands</h4>
<p>Edit cycles already in the method table without removing them:</p>
<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse; font-size:12px;">
<tr style="background:#f0f0f0;"><th>Command</th><th>Effect</th></tr>
<tr><td><code>#3 contact 120s</code></td><td>Set contact time on cycle 3 to 120 s</td></tr>
<tr><td><code>#3 channels BD</code></td><td>Restrict cycle 3 to channels B &amp; D</td></tr>
<tr><td><code>#3 detection priority</code></td><td>Set high-sensitivity injection detection</td></tr>
<tr><td><code>#3 injection partial</code></td><td>Switch to partial injection</td></tr>
<tr><td><code>#3 flow 50</code></td><td>Set flow rate to 50 µL/min</td></tr>
<tr><td><code>#3 conc A:100nM B:50nM</code></td><td>Set per-channel concentrations</td></tr>
<tr><td><code>#3 duration 10min</code></td><td>Change cycle duration</td></tr>
<tr><td><code>#all detection off</code></td><td>Disable injection detection on ALL cycles</td></tr>
<tr><td><code>#2-5 channels AC</code></td><td>Apply to cycles 2 through 5</td></tr>
</table>
<p>Multiple modifiers in one line: <code>#3 contact 120s channels BD detection priority</code></p>

<hr/>

<h4>Examples — One Line per Cycle</h4>
<pre style="background:#f5f5f7; padding:8px; border-radius:4px; font-size:12px;">
Baseline 5min
Binding 8.5min A:100nM contact 300s
Binding 8.5min A:500nM contact 300s
Regeneration 30sec ALL:50mM
Baseline 2min
</pre>

<h4>Overnight Stability Test</h4>
<pre style="background:#f5f5f7; padding:8px; border-radius:4px; font-size:12px;">
Baseline overnight   # 8 hours (auto)
Baseline 12h         # 12 hours
Baseline 24hr        # 24 hours
</pre>

<h4>Amine Coupling</h4>
<pre style="background:#f5f5f7; padding:8px; border-radius:4px; font-size:12px;">
Baseline 5min
Other 4min                                 # EDC/NHS activation
Wash 30sec
Immobilization 30min                       # ligand attachment — freestyle window
Wash 30sec
Blocking 4min                              # ethanolamine
Wash 30sec
Baseline 15min
Binding 8.5min A:100nM contact 300s
Regeneration 30sec ALL:50mM
Baseline 2min
</pre>

<h4>Partial Injection Example</h4>
<pre style="background:#f5f5f7; padding:8px; border-radius:4px; font-size:12px;">
Binding 5min A:100nM contact 120s partial
</pre>

<hr/>

<h4>⚡ Spark AI Shortcuts</h4>
<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse; font-size:12px;">
<tr style="background:#f0f0f0;"><th>Command</th><th>What it generates</th></tr>
<tr><td><code>@spark titration</code></td><td>Dose-response series (4 concentrations + regen)</td></tr>
<tr><td><code>@spark amine coupling</code></td><td>Full amine coupling workflow (asks how many binding cycles)</td></tr>
<tr><td><code>build 5</code></td><td>5 × (Binding 8.5 min + Regen + Baseline)</td></tr>
<tr><td><code>build 10</code></td><td>10 × (Binding 8.5 min + Regen + Baseline)</td></tr>
<tr><td><code>@spark binding</code></td><td>Multi-concentration binding template</td></tr>
<tr><td><code>@spark regeneration</code></td><td>Single regeneration cycle</td></tr>
<tr><td><code>@spark immobilization</code></td><td>Single immobilization cycle (30 min freestyle)</td></tr>
<tr><td><code>@spark baseline</code></td><td>Single baseline cycle</td></tr>
<tr><td><code>@spark full cycle</code></td><td>Baseline + Binding + Regen</td></tr>
</table>
<p>Spark suggests cycles in the note field — click <b>✅ Accept</b> to add, <b>✏ Edit</b> to modify, or <b>❌ Reject</b> to discard.</p>

<hr/>

<h4>📦 Presets — Save &amp; Reuse Methods</h4>
<ul>
<li><b>Save:</b> Build your method, then type <code>!save my_method_name</code> and click Add to Method</li>
<li><b>Load:</b> Type <code>@my_method_name</code> and click Add to Method to load a saved preset</li>
<li>Presets are stored in <code>cycle_templates.json</code> in the application directory</li>
</ul>

<hr/>

<h4>Queue Controls</h4>
<ul>
<li><b>↑ / ↓</b> — Reorder cycles in the method table</li>
<li><b>🗑 Delete</b> — Remove selected cycle</li>
<li><b>Clear All</b> — Remove all cycles from the method</li>
<li><b>↶ Undo / ↷ Redo</b> — Undo or redo changes (Ctrl+Z / Ctrl+Shift+Z)</li>
<li><b>↑/↓ arrows</b> in the Note field — Recall previously typed notes</li>
<li><b>📋 Copy Schedule</b> — Copy a print-friendly injection checklist to clipboard</li>
</ul>

<h4>Execution Behavior</h4>
<ul>
<li>Cycles run in order and <b>auto-advance</b> when the timer expires</li>
<li>Press <b>⏭ Next Cycle</b> to skip to the next cycle early (data is preserved)</li>
<li>After the last cycle, the system enters <b>Auto-Read</b> mode (2 hours of continuous monitoring)</li>
<li>The intelligence bar shows a countdown and previews the next cycle in the last 10 seconds</li>
<li><b>Automatic wash flags</b> are placed when a contact timer expires during injection cycles</li>
<li><b>Validation warnings</b> appear when adding cycles with potential timing conflicts</li>
</ul>

<hr/>

<h4>Tips</h4>
<ul>
<li>In <b>manual mode</b> (no pump): use <b>Binding</b> cycles — incubation with a set contact time, no dissociation phase.</li>
<li>In <b>flow mode</b> (with pump): use <b>Kinetic</b> cycles — full association + dissociation phases (requires flowrate).</li>
<li>Binding and Kinetic cycles default to <b>300 s contact time</b> (5 min) if not specified.</li>
<li>Regeneration cycles default to <b>30 s contact time</b>.</li>
<li>Use <b>overnight</b> as a duration keyword for 8-hour baseline runs.</li>
<li>Comments after <code>#</code> are ignored in cycle lines but shown in the method table.</li>
</ul>
        """

        # Create modeless dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Method Builder Help")
        dialog.setModal(False)  # Non-blocking - user can still type in main window
        dialog.resize(560, 700)

        layout = QVBoxLayout(dialog)

        # Text browser for rich text display
        browser = QTextBrowser()
        browser.setHtml(help_text)
        browser.setOpenExternalLinks(True)
        layout.addWidget(browser)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)

        dialog.show()  # Non-blocking show instead of exec()

    def _build_cycle_from_text(self, text: str) -> tuple[Cycle, list[str]]:
        """Build Cycle object from a single line of text.

        Notes (after #) are strictly informational and never parsed.
        Only the command portion before # is used to build cycle parameters.

        Args:
            text: Single line like "Baseline 5min A:100nM  # my note"
            
        Returns:
            tuple: (Cycle object, list of warning strings from parsing)
        """
        import re

        # ── Separate command from user note ────────────────────────────
        # Everything after the first '#' that is NOT a modifier (#3, #all, #1-5)
        # is treated as a free-form, unparsed user note.
        user_note = ""
        command = text
        note_match = re.search(r'(?<!^)\s+#(?!\d|all|\d+-\d+)\s*(.*)', text, re.IGNORECASE)
        if note_match:
            user_note = note_match.group(1).strip()
            command = text[:note_match.start()].strip()
        # If the entire line is just a comment, keep it as note with empty command
        if not command:
            command = text

        # Use 'command' (not 'text') for all parsing below
        text = command

        # Parse type from text (updated cycle types)
        cycle_type = "Baseline"  # default
        type_keywords = [
            ('Baseline', r'\bbl\b|baseline'),
            ('Immobilization', r'\bim\b|immobilization|immobilize|immob'),
            ('Blocking', r'\bbk\b|blocking|block'),
            ('Wash', r'\bws\b|\bwash\b'),  # Match 'wash' as standalone word
            ('Kinetic', r'\bkn\b|kinetic|kinetics'),
            ('Binding', r'\bbn\b|\bcn\b|binding|concentration|conc|association|inject'),
            ('Regeneration', r'\brg\b|regeneration|regen|clean'),
            ('Other', r'\bot\b|other|custom'),
        ]

        for type_name, pattern in type_keywords:
            if re.search(pattern, text, re.IGNORECASE):
                cycle_type = type_name
                break

        # Parse duration from text (e.g., "5min", "30sec", "2h", "overnight")
        duration_minutes = 5.0  # default

        # Special case: "overnight" = 8 hours
        if 'overnight' in text.lower():
            duration_minutes = 8 * 60.0  # 480 minutes
        else:
            # Parse hours, minutes, or seconds (e.g., "24h", "5min", "30sec")
            duration_match = re.search(r'(\d+(?:\.\d+)?)\s*(h|hr|hour|hours|min|m|sec|s)\b', text, re.IGNORECASE)
            if duration_match:
                value = float(duration_match.group(1))
                unit = duration_match.group(2).lower()
                if unit in ['sec', 's']:
                    duration_minutes = value / 60.0
                elif unit in ['h', 'hr', 'hour', 'hours']:
                    duration_minutes = value * 60.0  # Convert hours to minutes
                else:  # min or m
                    duration_minutes = value

        # Parse concentration tags WITH units: A:100nM, B:50µM, [A:100nM], [ALL:25pM], BD:5nM, ABC:10µM, etc.
        # Accepts both formats: simple (A:100nM) and bracketed ([A:100nM])
        # Also accepts lowercase (a, b, c, d) and uppercase (A, B, C, D)
        # Supports multi-channel shorthand: BD:5nM expands to B:5nM D:5nM
        # Supports comma-separated concentrations: ABCD:100,50,25,10 maps A=100, B=50, C=25, D=10
        tags_with_units = re.findall(r"\[?([A-Da-d]+|ALL|all):([\d.,\s]+)([a-zA-Zµ/]+)?\]?", text, re.IGNORECASE)

        # Unit validation whitelist
        VALID_UNITS = {"nM", "µM", "uM", "mM", "M", "pM", "µg/mL", "ug/mL", "ng/mL", "mg/mL", "g/L"}

        # Extract concentrations and detect units
        concentrations = {}
        detected_unit = "nM"  # default
        unit_warnings = []  # Track invalid units for warning

        for ch_group, val_str, unit_str in tags_with_units:
            # Normalize channel group to uppercase
            ch_group_upper = ch_group.upper()
            
            # Handle special case: ALL means all channels
            if ch_group_upper == "ALL":
                channels_to_set = ["A", "B", "C", "D"]
            else:
                # Expand multi-character channel groups (e.g., "BD" -> ["B", "D"])
                channels_to_set = list(ch_group_upper)
                # Validate that all characters are valid channels
                valid_channels = {"A", "B", "C", "D"}
                channels_to_set = [ch for ch in channels_to_set if ch in valid_channels]
            
            # Parse concentration values (single value or comma-separated list)
            if ',' in val_str:
                # Comma-separated concentrations: map in order to channels
                concentration_values = [float(v.strip()) for v in val_str.split(',') if v.strip()]
                
                # Map concentrations to channels in order
                for i, ch in enumerate(channels_to_set):
                    if i < len(concentration_values):
                        concentrations[ch] = concentration_values[i]
                    else:
                        # If we run out of values, use the last value for remaining channels
                        concentrations[ch] = concentration_values[-1] if concentration_values else 0.0
            else:
                # Single value: apply same concentration to all channels in the group
                val = float(val_str.strip())
                for ch in channels_to_set:
                    concentrations[ch] = val
                
            if unit_str:  # If units specified in tag, validate and use it
                # Normalize unit for comparison (handle µ vs u)
                unit_normalized = unit_str.replace('µ', 'µ').replace('μ', 'µ')  # Normalize greek mu
                
                # Check whitelist
                if unit_normalized in VALID_UNITS or unit_str in VALID_UNITS:
                    detected_unit = unit_str
                else:
                    # Invalid unit - add warning but accept the parse (non-blocking)
                    unit_warnings.append(f"⚠️ Invalid unit '{unit_str}' — Valid units: nM, µM, mM, M, pM, µg/mL, ng/mL, mg/mL")
                    detected_unit = unit_str  # Store anyway for user to see/fix

        # Parse contact time (e.g., "contact 180s", "contact180s", "contact 3min", "ct 2min", "ct3m")
        contact_time = None
        # Try full "contact" keyword first (allows both "contact 3m" and "contact3m")
        contact_match = re.search(r'contact[:\s]*(\d+(?:\.\d+)?)\s*(s|sec|m|min|h|hr)?', text, re.IGNORECASE)
        if not contact_match:
            # Try shorthand "ct" keyword (allows both "ct 3m" and "ct3m")
            contact_match = re.search(r'\bct\s*(\d+(?:\.\d+)?)\s*(s|sec|m|min|h|hr)?', text, re.IGNORECASE)

        if contact_match:
            value = float(contact_match.group(1))
            unit = contact_match.group(2).lower() if contact_match.group(2) else 's'
            if unit in ['h', 'hr']:
                contact_time = value * 3600.0  # Convert to seconds
                # Auto-enable overnight mode if > 3 hours
                if value > 3:
                    self.overnight_mode_check.setChecked(True)
            elif unit in ['m', 'min']:
                contact_time = value * 60.0  # Convert to seconds
            else:
                contact_time = value

        # Parse partial injection override (e.g., "partial injection", "partial")
        is_partial = bool(re.search(r'partial\s*(injection)?', text, re.IGNORECASE))

        # Parse manual injection mode override (e.g., "manual injection", "automated")
        manual_injection_mode = None
        if re.search(r'manual\s*(?:injection|mode)?', text, re.IGNORECASE):
            manual_injection_mode = "manual"
        elif re.search(r'automated\s*(?:injection|mode)?', text, re.IGNORECASE):
            manual_injection_mode = "automated"

        # Auto-set injection method and contact time based on cycle type rules
        injection_method = None
        pump_type = None  # Will be auto-detected during execution

        # Injection rules by cycle type (P4SPR / manual injection context)
        if cycle_type == "Binding":
            injection_method = "partial" if is_partial else "simple"
            if contact_time is None:
                contact_time = 300.0  # 5 min default contact time (P4SPR manual injection)
        elif cycle_type == "Kinetic":
            injection_method = "simple"
            if contact_time is None:
                contact_time = 300.0  # 5 min default — association phase
        elif cycle_type == "Regeneration":
            injection_method = "simple"
            if contact_time is None:
                contact_time = 30.0   # 30 s default contact time
        elif cycle_type in ("Baseline", "Immobilization", "Wash", "Blocking", "Other"):
            # No automated injection. Immobilization is a 30-min freestyle window —
            # injection prompts within that window are a future improvement.
            injection_method = None
            contact_time = None

        # Build planned_concentrations list for concentration cycles
        # Format: Individual channel entries for proper injection counting and detection
        # Each channel gets its own entry so injection detection properly recognizes all channels
        planned_concentrations = []
        if cycle_type in ("Binding", "Kinetic") and concentrations:
            # Create individual entries for each channel to ensure proper detection
            for ch in sorted(concentrations.keys()):
                val = concentrations[ch]
                conc_str = f"{val} {detected_unit}".replace(" .", ".")  # Clean up decimals
                planned_concentrations.append(f"Ch {ch}: {conc_str}")

        # Generate name from type + tags or just text
        if concentrations:
            tag_str = " ".join([f"[{ch}:{val}]" for ch, val in concentrations.items()])
            name = f"{cycle_type} {tag_str}"
        else:
            # Use first 30 chars of text as name
            name = text[:30] if text else cycle_type

        # Parse detection priority override (e.g., "detection priority", "detection off")
        detection_priority_override = None
        det_match = re.search(r'detection\s+(priority|off|auto)', text, re.IGNORECASE)
        if det_match:
            detection_priority_override = det_match.group(1).lower()

        # Parse target channels override (e.g., "channels AC", "channels BD")
        target_channels = None
        ch_match = re.search(r'channels?\s+([ABCD]+)', text, re.IGNORECASE)
        if ch_match:
            target_channels = ch_match.group(1).upper()
        # Auto-derive channels from concentrations if not explicitly set
        elif concentrations:
            target_channels = "".join(sorted(concentrations.keys()))

        # Determine mode and detection from dialog selectors
        method_mode = self._get_method_mode()
        detection_priority = detection_priority_override or self._get_detection_priority()

        cycle = Cycle(
            type=cycle_type,
            name=name,
            length_minutes=duration_minutes,
            note=user_note,
            status="pending",
            units=detected_unit,
            concentrations=concentrations,
            timestamp=time.time(),
            # Pump and injection fields
            injection_method=injection_method,
            injection_delay=20.0,  # Always 20s
            contact_time=contact_time,
            pump_type=pump_type,  # Auto-detected during execution
            # Manual injection mode fields
            manual_injection_mode=manual_injection_mode,
            planned_concentrations=planned_concentrations,
            # Mode and detection fields
            method_mode=method_mode,
            detection_priority=detection_priority,
            target_channels=target_channels,
        )
        
        # Return cycle along with any unit warnings from parsing
        return cycle, unit_warnings

    def _on_add_to_method(self):
        """Add cycles to local method queue (supports multiple cycles, one per line)."""

        notes_text = self.notes_input.toPlainText().strip()
        if not notes_text:
            return

        # Check for Spark AI question: @spark question
        if notes_text.lower().startswith('@spark '):
            question = notes_text[7:].strip()  # Remove '@spark ' prefix
            self.notes_input.setPlainText(question)
            self._detect_and_respond_to_question()
            return

        # Check for preset loading command: @preset_name
        if notes_text.startswith('@'):
            preset_name = notes_text[1:].strip()
            self._load_preset(preset_name)
            self.notes_input.clear()
            return

        # Check for save command: !save preset_name
        if notes_text.startswith('!save '):
            preset_name = notes_text[6:].strip()
            self._save_preset(preset_name)
            self.notes_input.clear()
            return

        # Split by newlines to support multiple cycles at once
        lines = [line.strip() for line in notes_text.split('\n') if line.strip()]

        # Separate #N modifier lines from new cycle lines
        modifier_lines = []
        cycle_lines = []
        for line in lines:
            if re.match(r'^#(\d+|all|\d+-\d+)\s', line, re.IGNORECASE):
                modifier_lines.append(line)
            else:
                cycle_lines.append(line)

        # Process #N modifier commands (edit existing cycles in-place)
        if modifier_lines:
            self._apply_modifiers(modifier_lines)

        # Process new cycle lines
        for line in cycle_lines:
            cycle, parse_warnings = self._build_cycle_from_text(line)
            self._local_cycles.append(cycle)
            self._validate_and_warn_cycle(cycle, raw_text=line, parse_warnings=parse_warnings)

        self._refresh_method_table()

        # Save notes to history (if not empty and not duplicate)
        if notes_text and (not self._notes_history or notes_text != self._notes_history[-1]):
            self._notes_history.append(notes_text)

        # Reset history navigation
        self._history_index = -1
        self._current_draft = ""

    # -- #N modifier parser ------------------------------------------------

    def _apply_modifiers(self, lines: list[str]):
        """Apply #N modifier commands to existing cycles in _local_cycles.

        Syntax examples:
            #3 contact 120s          — set contact time on cycle 3
            #3 channels BD           — set target channels on cycle 3
            #3 detection priority    — set detection priority on cycle 3
            #3 injection manual      — set injection mode on cycle 3
            #3 flow 50               — set flow rate on cycle 3
            #3 conc A:100nM B:50nM   — set concentrations on cycle 3
            #all detection off       — apply to ALL cycles
            #2-5 channels AC         — apply to range of cycles
        """
        import re

        for line in lines:
            # Parse the target selector: #N, #all, #N-M
            match = re.match(r'^#(\d+|all|(\d+)-(\d+))\s+(.+)$', line, re.IGNORECASE)
            if not match:
                continue

            selector = match.group(1).lower()
            rest = match.group(4).strip()

            # Determine which cycle indices to modify
            indices = []
            if selector == "all":
                indices = list(range(len(self._local_cycles)))
            elif "-" in selector:
                range_match = re.match(r'(\d+)-(\d+)', selector)
                if range_match:
                    start = int(range_match.group(1)) - 1  # 1-indexed to 0-indexed
                    end = int(range_match.group(2)) - 1
                    indices = [i for i in range(start, end + 1) if 0 <= i < len(self._local_cycles)]
            else:
                idx = int(selector) - 1  # 1-indexed to 0-indexed
                if 0 <= idx < len(self._local_cycles):
                    indices = [idx]

            if not indices:
                continue

            # Parse the field=value pairs from the rest of the line
            for idx in indices:
                cycle = self._local_cycles[idx]
                self._apply_single_modifier(cycle, rest)

    def _apply_single_modifier(self, cycle: Cycle, text: str):
        """Apply a single modifier string to a Cycle object.

        Args:
            cycle: Cycle to modify in-place
            text: Modifier text like 'contact 120s', 'channels BD', etc.
        """
        import re
        text_lower = text.lower().strip()

        # contact Ns / contact Nm / contact Nh / contact Nhr
        contact_match = re.match(r'contact\s+(\d+(?:\.\d+)?)\s*(s|sec|m|min|h|hr)?', text_lower)
        if contact_match:
            # Don't allow contact_time on Baseline or Other cycles (no injection)
            if cycle.type in ("Baseline", "Other"):
                logger.warning(f"⚠️ Cannot set contact_time on {cycle.type} cycle (no injection)")
                return

            value = float(contact_match.group(1))
            unit = contact_match.group(2) or 's'
            if unit in ('h', 'hr'):
                cycle.contact_time = value * 3600.0
                # Auto-enable overnight mode if > 3 hours
                if value > 3:
                    self.overnight_mode_check.setChecked(True)
            elif unit in ('m', 'min'):
                cycle.contact_time = value * 60.0
            else:
                cycle.contact_time = value
            return

        # channels XX
        ch_match = re.match(r'channels?\s+([abcd]+)', text_lower)
        if ch_match:
            cycle.target_channels = ch_match.group(1).upper()
            return

        # detection priority/off/auto
        det_match = re.match(r'detection\s+(priority|off|auto)', text_lower)
        if det_match:
            cycle.detection_priority = det_match.group(1)
            return

        # injection manual/simple/partial/automated
        inj_match = re.match(r'injection\s+(manual|simple|partial|automated)', text_lower)
        if inj_match:
            mode = inj_match.group(1)
            if mode == "manual":
                cycle.manual_injection_mode = "manual"
            elif mode == "automated":
                cycle.manual_injection_mode = "automated"
            else:
                cycle.injection_method = mode
            return

        # flow N (µL/min)
        flow_match = re.match(r'flow\s+(\d+(?:\.\d+)?)', text_lower)
        if flow_match:
            cycle.flow_rate = float(flow_match.group(1))
            return

        # fr N (µL/min) - shorthand for flow rate
        fr_match = re.match(r'fr\s+(\d+(?:\.\d+)?)', text_lower)
        if fr_match:
            cycle.flow_rate = float(fr_match.group(1))
            return

        # iv N (µL) - injection volume
        iv_match = re.match(r'iv\s+(\d+(?:\.\d+)?)', text_lower)
        if iv_match:
            cycle.injection_volume = float(iv_match.group(1))
            return

        # ct Ns / ct Nm / ct Nh / ct Nhr - shorthand for contact time
        ct_match = re.match(r'ct\s+(\d+(?:\.\d+)?)\s*(s|sec|m|min|h|hr)?', text_lower)
        if ct_match:
            # Don't allow contact_time on Baseline or Other cycles (no injection)
            if cycle.type in ("Baseline", "Other"):
                logger.warning(f"⚠️ Cannot set contact_time on {cycle.type} cycle (no injection)")
                return

            value = float(ct_match.group(1))
            unit = ct_match.group(2) or 's'
            if unit in ('h', 'hr'):
                cycle.contact_time = value * 3600.0
                # Auto-enable overnight mode if > 3 hours
                if value > 3:
                    self.overnight_mode_check.setChecked(True)
            elif unit in ('m', 'min'):
                cycle.contact_time = value * 60.0
            else:
                cycle.contact_time = value
            return

        # conc A:100nM B:50nM ...
        conc_match = re.match(r'conc\s+(.+)', text, re.IGNORECASE)
        if conc_match:
            conc_text = conc_match.group(1)
            tags = re.findall(r'([A-D]):(\d+\.?\d*)([a-zA-Zµ/]+)?', conc_text)
            for ch, val, unit_str in tags:
                cycle.concentrations[ch] = float(val)
                if unit_str:
                    cycle.units = unit_str
            return

        # duration Nmin / Ns / Nh
        dur_match = re.match(r'(?:duration|time|length)\s+(\d+(?:\.\d+)?)\s*(s|sec|m|min|h|hr)?', text_lower)
        if dur_match:
            value = float(dur_match.group(1))
            unit = dur_match.group(2) or 'min'
            if unit in ('s', 'sec'):
                cycle.length_minutes = value / 60.0
            elif unit in ('h', 'hr'):
                cycle.length_minutes = value * 60.0
            else:
                cycle.length_minutes = value
            return

        # Compound modifiers: multiple keywords on one line separated by spaces
        # e.g., "#3 contact 120s channels BD detection priority" or "#3 ct 120s channels BD"
        # Try recursive splitting at known keywords
        keywords = ['contact', 'ct', 'channels', 'channel', 'detection', 'injection', 'flow', 'fr', 'iv', 'conc', 'duration', 'time', 'length']
        parts = re.split(r'\s+(?=(?:' + '|'.join(keywords) + r')\s)', text, flags=re.IGNORECASE)
        if len(parts) > 1:
            for part in parts:
                self._apply_single_modifier(cycle, part.strip())

    def _on_clear_method(self):
        """Clear all cycles from local method."""
        self._local_cycles.clear()
        self._refresh_method_table()
        self._update_gallery_visibility()

    def _refresh_method_table(self):
        """Update the 6-column step list and gallery visibility."""
        self._update_chip_suggestion()
        self.method_table.blockSignals(True)
        self.method_table.setRowCount(0)

        for cycle in self._local_cycles:
            row = self.method_table.rowCount()
            self.method_table.insertRow(row)

            # Col 0: Type (colour-coded abbreviation)
            abbr, color = CycleTypeStyle.get(cycle.type)
            type_item = QTableWidgetItem(abbr)
            type_item.setForeground(QColor(color))
            type_item.setToolTip(cycle.type)
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.method_table.setItem(row, 0, type_item)

            # Col 1: Duration (formatted)
            mins = cycle.length_minutes
            if mins >= 60:
                dur_str = f"{int(mins // 60)}h {int(mins % 60)}m" if mins % 60 else f"{int(mins // 60)}h"
            elif mins < 1:
                dur_str = f"{mins * 60:.0f}s"
            else:
                dur_str = f"{mins:.1f} min"
            dur_item = QTableWidgetItem(dur_str)
            dur_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            dur_item.setFlags(dur_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.method_table.setItem(row, 1, dur_item)

            # Col 2: Channel
            if cycle.target_channels:
                ch_text = cycle.target_channels
            elif cycle.concentrations:
                ch_text = "".join(sorted(cycle.concentrations.keys()))
            elif cycle.type in ("Baseline", "Other"):
                ch_text = "—"
            else:
                ch_text = "ALL"
            ch_item = QTableWidgetItem(ch_text)
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            ch_item.setToolTip("Double-click to edit channels (e.g. A, BD, ALL)")
            self.method_table.setItem(row, 2, ch_item)

            # Col 3: Concentration
            if cycle.concentrations:
                conc_parts = [f"{ch}:{v}{cycle.units}" for ch, v in cycle.concentrations.items()]
                conc_text = "  ".join(conc_parts)
            elif getattr(cycle, 'concentration_value', None) is not None:
                conc_text = f"{cycle.concentration_value} {getattr(cycle, 'concentration_units', '')}"
            else:
                conc_text = "—"
            conc_item = QTableWidgetItem(conc_text)
            conc_item.setToolTip("Double-click to edit concentration (e.g. 100nM, A:100nM B:50nM)")
            self.method_table.setItem(row, 3, conc_item)

            # Col 4: Flow rate (AffiPump) or Contact time (P4SPR)
            if self._has_affipump:
                fr = getattr(cycle, 'flow_rate', None)
                col4_text = f"{fr:.0f} µL/min" if fr else "—"
            else:
                if cycle.contact_time is not None:
                    ct = cycle.contact_time
                    if ct >= 3600:
                        col4_text = f"{ct / 3600:.1f}h"
                    elif ct >= 60:
                        col4_text = f"{ct / 60:.0f}m"
                    else:
                        col4_text = f"{ct:.0f}s"
                else:
                    col4_text = "—"
            ct_item = QTableWidgetItem(col4_text)
            ct_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            ct_item.setFlags(ct_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.method_table.setItem(row, 4, ct_item)

            # Col 5: Note (editable)
            note_item = QTableWidgetItem(cycle.note or "")
            self.method_table.setItem(row, 5, note_item)

        # Update labels
        count = len(self._local_cycles)
        self.method_count_label.setText(f"{count} cycle{'s' if count != 1 else ''}")

        total_time = sum(c.length_minutes for c in self._local_cycles)
        if total_time == 0:
            time_str = "0 min total"
        elif total_time >= 60:
            h = int(total_time // 60)
            m = int(total_time % 60)
            time_str = f"Total: {h}h {m}m" if m else f"Total: {h}h"
        else:
            time_str = f"Total: {total_time:.1f} min"
        self.method_exp_time_value.setText(time_str)

        self.method_table.blockSignals(False)
        self._update_gallery_visibility()

    def _on_details_selection_changed(self):
        """Sync selection from details table to overview table."""
        selected_rows = [item.row() for item in self.details_table.selectedItems()]
        if selected_rows:
            self.method_table.selectRow(selected_rows[0])

    def _on_table_item_edited(self, item: QTableWidgetItem):
        """Write channel or concentration edits back to the cycle data model."""
        row = item.row()
        col = item.column()
        if row < 0 or row >= len(self._local_cycles):
            return
        if col not in (2, 3):  # Only channel and concentration are editable
            return
        cycle = self._local_cycles[row]
        text = item.text().strip()

        # Block the signal while we refresh to avoid re-entry
        self.method_table.blockSignals(True)
        try:
            if col == 2:  # Channel
                cleaned = text.upper().replace(" ", "").replace("-", "").replace("—", "")
                if cleaned in ("", "—", "ALL"):
                    cycle.target_channels = ""
                else:
                    # Keep only valid channel letters
                    cleaned = "".join(c for c in cleaned if c in "ABCD")
                    cycle.target_channels = cleaned
            elif col == 3:  # Concentration — re-parse via _build_cycle_from_text
                if text in ("", "—"):
                    cycle.concentrations = {}
                else:
                    # Build a minimal line with the cycle type + new conc tag and re-parse
                    probe_line = f"{cycle.type.lower()} {text}"
                    try:
                        rebuilt, _ = self._build_cycle_from_text(probe_line)
                        if rebuilt.concentrations:
                            cycle.concentrations = rebuilt.concentrations
                            cycle.units = rebuilt.units
                    except Exception:
                        pass  # Leave existing value if parse fails
        finally:
            self.method_table.blockSignals(False)

        # Refresh just this row to reflect normalised values
        self._refresh_method_table()
        self.method_table.selectRow(row)

    def _on_selection_changed(self):
        """Update button states based on selection."""
        selected_rows = [item.row() for item in self.method_table.selectedItems()]
        has_selection = len(selected_rows) > 0
        selected_row = selected_rows[0] if has_selection else -1

        self.delete_cycle_btn.setEnabled(has_selection)
        self.move_up_btn.setEnabled(has_selection and selected_row > 0)
        self.move_down_btn.setEnabled(has_selection and selected_row < len(self._local_cycles) - 1)

    def _on_delete_selected(self):
        """Delete selected cycle from method."""
        selected_rows = [item.row() for item in self.method_table.selectedItems()]
        if not selected_rows:
            return
        row = selected_rows[0]
        if 0 <= row < len(self._local_cycles):
            del self._local_cycles[row]
            self._refresh_method_table()

    def _on_move_up(self):
        """Move selected cycle up."""
        selected_rows = [item.row() for item in self.method_table.selectedItems()]
        if not selected_rows:
            return
        row = selected_rows[0]
        if row > 0:
            self._local_cycles[row], self._local_cycles[row - 1] = self._local_cycles[row - 1], self._local_cycles[row]
            self._refresh_method_table()
            self.method_table.selectRow(row - 1)

    def _on_move_down(self):
        """Move selected cycle down."""
        selected_rows = [item.row() for item in self.method_table.selectedItems()]
        if not selected_rows:
            return
        row = selected_rows[0]
        if row < len(self._local_cycles) - 1:
            self._local_cycles[row], self._local_cycles[row + 1] = self._local_cycles[row + 1], self._local_cycles[row]
            self._refresh_method_table()
            self.method_table.selectRow(row + 1)

    def _on_row_moved(self, from_row: int, to_row: int) -> None:
        """Handle drag-and-drop reorder — move cycle in data model then refresh."""
        n = len(self._local_cycles)
        if 0 <= from_row < n and 0 <= to_row < n and from_row != to_row:
            cycle = self._local_cycles.pop(from_row)
            self._local_cycles.insert(to_row, cycle)
            self._refresh_method_table()
            self.method_table.selectRow(to_row)

    def _on_overnight_mode_changed(self, state):
        """Update settings.OVERNIGHT_MODE when checkbox is toggled."""
        try:
            import settings as root_settings
            root_settings.OVERNIGHT_MODE = (state == Qt.CheckState.Checked.value)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to update OVERNIGHT_MODE setting: {e}")

    def _toggle_advanced_settings(self, checked: bool):
        """Show/hide the advanced settings panel (device type & detection)."""
        self._adv_settings_frame.setVisible(checked)

    # -- Mode / Hardware helpers ------------------------------------------

    def _on_mode_changed(self, mode_text: str):
        """Handle method mode change — keep detection on Auto (factor adapts internally)."""
        # Detection stays 'Auto' — the sensitivity_factor in
        # manual_injection_dialog adapts automatically (2.0 for manual, 0.75 for pump)
        self.detection_combo.setCurrentText("Auto")

        # Easy mode: disable flow-specific fields when injection mode is Manual
        # (no pump → contact time and flow rate don't apply)
        is_manual = mode_text.lower() == "manual"
        for widget in [
            getattr(self, 'easy_contact_value', None),
            getattr(self, 'easy_contact_unit', None),
            getattr(self, 'easy_flow_value', None),
            getattr(self, 'easy_flow_unit', None),
        ]:
            if widget is not None:
                widget.setEnabled(not is_manual)
                widget.setToolTip("Not applicable in Manual injection mode" if is_manual else "")

    def configure_for_hardware(self, hw_name: str, has_affipump: bool = False):
        """Configure mode selector based on detected hardware.

        Called from main window on dialog open. Auto-selects the best mode
        for the connected hardware but leaves the combo enabled so the user
        can override.

        Args:
            hw_name: Hardware identifier — 'P4SPR', 'P4PRO', 'P4PROPLUS'
            has_affipump: True if an AffiPump is connected (external syringe pump)
        """
        hw_upper = hw_name.upper() if hw_name else "P4SPR"
        label = hw_upper

        if hw_upper == "P4SPR" and not has_affipump:
            # Static controller, no pump → manual only
            label = "P4SPR"
            self.mode_combo.clear()
            self.mode_combo.addItems(["Manual"])
            self.mode_combo.setCurrentIndex(0)
            self.mode_combo.setEnabled(False)
        elif hw_upper == "P4SPR" and has_affipump:
            # Static controller + AffiPump → can do semi-automated
            label = "P4SPR + AffiPump"
            self.mode_combo.clear()
            self.mode_combo.addItems(["Manual", "Semi-Automated"])
            self.mode_combo.setCurrentIndex(1)  # Default semi-auto with pump
            self.mode_combo.setEnabled(True)
        elif hw_upper in ("P4PRO", "P4PROPLUS"):
            self.mode_combo.clear()
            self.mode_combo.addItems(["Manual", "Semi-Automated"])
            self.mode_combo.setCurrentIndex(1)  # Default semi-automated for PRO
            self.mode_combo.setEnabled(True)
            if hw_upper == "P4PROPLUS":
                label = "P4PRO+"
            elif has_affipump:
                label = f"{hw_upper} + AffiPump"

        # Store pump presence for validator gating
        self._has_affipump = has_affipump or hw_upper in ("P4PRO", "P4PROPLUS")

        # Col 4 header: "Flow rate" for AffiPump (contact time is loop-derived), "Contact time" for P4SPR
        col4_label = "Flow rate" if self._has_affipump else "Contact time"
        from PySide6.QtWidgets import QTableWidgetItem as _TWI
        self.method_table.setHorizontalHeaderItem(4, _TWI(col4_label))

        # Detection always defaults to Auto — factor adapts internally
        self.detection_combo.setCurrentText("Auto")
        self.hw_label.setText(label)

    def _get_method_mode(self) -> str:
        """Return the current method mode as a lowercase string for Cycle fields."""
        return self.mode_combo.currentText().lower()

    def _get_detection_priority(self) -> str:
        """Return the current detection priority as a lowercase string."""
        return self.detection_combo.currentText().lower()

    def _on_push_to_queue(self):
        """Push all cycles to main queue."""
        if not self._local_cycles:
            return
        method_name = self.method_name_input.text().strip() or "Untitled Method"
        # Attach chip/sensor metadata to every cycle before queuing
        chip_type = self.chip_type_combo.currentText()
        chip_info = {
            "chip_type": chip_type if chip_type != "— select —" else "",
            "lot_number": self.lot_number_input.text().strip(),
        }
        for cycle in self._local_cycles:
            cycle.chip_info = chip_info
        self.method_ready.emit("queue", method_name, self._local_cycles.copy())
        self._local_cycles.clear()
        self._refresh_method_table()
        # Close dialog after pushing to queue
        self.accept()

    def _load_preset(self, preset_name: str):
        """Load a saved preset by name."""
        preset = self._preset_storage.get_preset(preset_name)
        if preset:
            self._local_cycles = preset.copy()
            self._refresh_method_table()
            from PySide6.QtWidgets import QToolTip
            QToolTip.showText(
                QCursor.pos(),
                f"✅ Loaded preset '{preset_name}' with {len(preset)} cycles",
                self,
                self.rect(),
                2000
            )

    def _on_save_method(self):
        """Save current method to a JSON file."""
        if not self._local_cycles:
            QMessageBox.information(self, "No Method", "Add some cycles to the method queue before saving.")
            return

        from PySide6.QtWidgets import QFileDialog
        import json
        from pathlib import Path

        # Default save directory - user profile subfolder
        username = self._user_manager.get_current_user()
        default_dir = Path.home() / "Documents" / "Affilabs Methods" / username
        default_dir.mkdir(parents=True, exist_ok=True)

        # Use the method name input as default filename
        method_name = self.method_name_input.text().strip() or "Untitled Method"
        safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in method_name)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Method",
            str(default_dir / f"{safe_name}.json"),
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        try:
            import time as _time

            # Convert cycles to JSON-serializable format using Cycle.to_dict()
            method_name = self.method_name_input.text().strip() or "Untitled Method"
            cycles_data = []
            for cycle in self._local_cycles:
                if hasattr(cycle, 'to_dict'):
                    cycles_data.append(cycle.to_dict())
                else:
                    cycles_data.append({
                        "type": cycle.type,
                        "length_minutes": cycle.length_minutes,
                        "note": cycle.note or "",
                    })

            method_data = {
                "version": "1.0",
                "name": method_name,
                "author": self.operator_combo.currentText() if hasattr(self, 'operator_combo') else "",
                "description": "",
                "cycle_count": len(cycles_data),
                "created": _time.time(),
                "cycles": cycles_data,
            }

            # Write to file
            with open(file_path, 'w') as f:
                json.dump(method_data, f, indent=2)

            QMessageBox.information(self, "Method Saved", f"Method saved successfully to:\n{file_path}")

            # Emit signal so main app can respond (e.g., expand Run Queue panel)
            self.method_saved.emit(method_name, file_path)

        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save method:\n{e}")

    def _update_chip_suggestion(self) -> None:
        """Auto-suggest surface chemistry based on cycle types in the current method.

        Only updates the combo if the user hasn't made an explicit selection
        (i.e. it's still at the default "— select —").
        """
        if not hasattr(self, 'chip_type_combo'):
            return
        if self.chip_type_combo.currentText() != "— select —":
            return  # User already chose — don't override
        types = {c.type for c in self._local_cycles}
        if "Immobilization" in types and "Blocking" in types:
            self.chip_type_combo.setCurrentText("COOH")
        elif "Immobilization" in types and "Blocking" not in types:
            # NTA or Biotin — immobilization without EDC/NHS blocking step
            self.chip_type_combo.setCurrentText("NTA-His")

    def _on_new_sensor_chip(self) -> None:
        """Trigger Simple LED Calibration for a freshly loaded sensor chip."""
        if self._app_ref and hasattr(self._app_ref, "_on_simple_led_calibration"):
            self._app_ref._on_simple_led_calibration()
        else:
            QMessageBox.warning(
                self,
                "Not Connected",
                "Connect hardware before running sensor calibration.",
            )

    def _on_operator_changed(self, user_name: str):
        """Update current user when operator changes in Build Method dialog.

        This ensures the user_profile_manager stays in sync with the selected
        operator, so the export path and other user-dependent features use the
        correct user folder.
        """
        if user_name and hasattr(self, '_user_manager') and self._user_manager:
            self._user_manager.set_current_user(user_name)
            logger.debug(f"Operator changed in Build Method → current_user set to '{user_name}'")

    def _on_load_method(self):
        """Load method from a JSON file."""
        from PySide6.QtWidgets import QFileDialog
        import json
        from pathlib import Path
        from affilabs.domain.cycle import Cycle

        # Default load directory - user profile subfolder
        username = self._user_manager.get_current_user()
        default_dir = Path.home() / "Documents" / "Affilabs Methods" / username
        default_dir.mkdir(parents=True, exist_ok=True)

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Method",
            str(default_dir),
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        try:
            # Read from file
            with open(file_path, 'r') as f:
                method_data = json.load(f)

            # Validate format
            if "cycles" not in method_data:
                raise ValueError("Invalid method file format")

            # Clear current method if not empty
            if self._local_cycles:
                reply = QMessageBox.question(
                    self,
                    "Replace Method?",
                    "Current method will be replaced. Continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

            # Convert JSON back to Cycle objects using Cycle.from_dict()
            loaded_cycles = []
            for cycle_dict in method_data["cycles"]:
                # Use the Cycle model's built-in deserialization
                cycle = Cycle.from_dict(cycle_dict)
                loaded_cycles.append(cycle)

            # Update method
            self._local_cycles = loaded_cycles

            # Restore method name from file
            if method_data.get("name"):
                self.method_name_input.setText(method_data["name"])

            self._refresh_method_table()

            QMessageBox.information(
                self,
                "Method Loaded",
                f"Loaded {len(loaded_cycles)} cycle{'s' if len(loaded_cycles) != 1 else ''} from:\n{file_path}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load method:\n{e}")

    def _save_preset(self, preset_name: str):
        """Save current local cycles as a preset."""
        if not self._local_cycles:
            QMessageBox.warning(
                self,
                "Nothing to Save",
                "No cycles in the method queue to save."
            )
            return

        if not preset_name:
            QMessageBox.warning(
                self,
                "Invalid Name",
                "Please provide a name for the preset.\n\n"
                "Usage: !save preset_name"
            )
            return

        self._preset_storage.save_preset(preset_name, self._local_cycles)
        from PySide6.QtWidgets import QToolTip
        QToolTip.showText(
            QCursor.pos(),
            f"💾 Saved {len(self._local_cycles)} cycles as '{preset_name}'",
            self,
            self.rect(),
            2000
        )

    # -- Validation & clipboard helpers ------------------------------------

    def _validate_and_warn_cycle(self, cycle: Cycle, raw_text: str = "", parse_warnings: list = None):
        """Show non-blocking warnings for potential cycle issues."""
        warnings = []
        
        # Add any parsing warnings (e.g., invalid units)
        if parse_warnings:
            warnings.extend(parse_warnings)

        # Check 0a: Empty concentrations (all channels filtered out)
        if cycle.injection_method and raw_text and '[' in raw_text:
            # User specified concentration tags but no valid channels parsed
            if not getattr(cycle, 'concentrations', None) or len(cycle.concentrations) == 0:
                warnings.append(
                    "⚠️ Concentration tags found but no valid channels — check for typos\n"
                    "   → Valid channels: A, B, C, D or ALL"
                )

        # Check 0b: Duration limit (> 60 min)
        if cycle.length_minutes > 60:
            warnings.append(
                f"⚠️ Very long cycle ({cycle.length_minutes:.0f} min = {cycle.length_minutes / 60:.1f} hr)\n"
                "   → Long cycles may block queue for hours\n"
                "   → Consider breaking into shorter segments"
            )

        # Check 0c: Mixed units in method (compare with previous cycles)
        if self._local_cycles and hasattr(cycle, 'units'):
            prev_units = {c.units for c in self._local_cycles if hasattr(c, 'units') and c.units}
            if prev_units and cycle.units not in prev_units:
                prev_unit_str = ", ".join(sorted(prev_units))
                warnings.append(
                    f"⚠️ Unit change detected — previous cycles used {prev_unit_str}, this cycle uses {cycle.units}\n"
                    "   → Mixed units make data analysis harder\n"
                    "   → Consider using consistent units throughout method"
                )

        # T6 Check: No contact time on Binding/Kinetic cycles (P4SPR only — AffiPump uses loop volume)
        if not self._has_affipump:
            if cycle.type in ("Binding", "Kinetic") and cycle.injection_method and not cycle.contact_time:
                warnings.append(
                    "⚠️ No contact time set — injection will run for full cycle duration"
                )

            # T6 Check: Contact time < 60s (too short)
            if cycle.type in ("Binding", "Kinetic") and cycle.contact_time and cycle.contact_time < 60:
                warnings.append(
                    f"⚠️ Contact time is very short ({cycle.contact_time:.0f}s) — most analytes need 30+ seconds"
                )

        # T6 Check: Channel mismatch (concentrations only on specific channels but cycle runs ALL)
        if cycle.injection_method and getattr(cycle, 'concentrations', None):
            conc_channels = set(cycle.concentrations.keys())
            cycle_has_all = 'ALL' in raw_text.upper() or 'ALL' in cycle.name.upper() if cycle.name else False
            if cycle_has_all and len(conc_channels) < 4:
                channels_str = ", ".join(sorted(conc_channels))
                warnings.append(
                    f"⚠️ Channel mismatch — concentrations only set for {channels_str} but cycle runs ALL"
                )

        # T6 Check: Missing regeneration after Binding cycles
        # This check is for the overall method, so we'll mark it but note it needs method-level checking
        if cycle.type == "Binding" and cycle.injection_method:
            # Find if next cycle is regen (user will need to add it)
            cycle_idx = self._local_cycles.index(cycle) if cycle in self._local_cycles else -1
            if cycle_idx >= 0 and cycle_idx < len(self._local_cycles) - 1:
                next_cycle = self._local_cycles[cycle_idx + 1]
                if next_cycle.type != "Regeneration":
                    warnings.append(
                        "💡 Tip: Consider adding a **Regeneration** cycle after this binding step to remove bound analyte"
                    )

        # Check 0: Detect unparsed contact time patterns (P4SPR only)
        if not self._has_affipump and raw_text and cycle.injection_method:
            ct_pattern_found = bool(re.search(r'\b(ct|contact)[:\s]*\d', raw_text, re.IGNORECASE))
            if ct_pattern_found and cycle.type in ("Binding", "Kinetic"):
                unit_found = bool(re.search(r'\b(ct|contact)[:\s]*\d+(?:\.\d+)?\s*(s|sec|m|min|h|hr)', raw_text, re.IGNORECASE))
                if not unit_found and cycle.contact_time == 300.0:
                    warnings.append(
                        f"⚠️ Contact time detected but no unit specified, using default 300s\n"
                        f"Add a unit for clarity: 'ct 5m' or 'contact 180s'"
                    )

        # Check 1: Contact time vs cycle duration (P4SPR only — AffiPump ignores contact_time)
        if not self._has_affipump and cycle.injection_method and cycle.contact_time:
            cycle_seconds = cycle.length_minutes * 60
            if cycle.contact_time > cycle_seconds * 0.9:
                warnings.append(
                    f"⚠️ Contact time ({cycle.contact_time:.0f}s) is "
                    f"{cycle.contact_time / cycle_seconds:.0%} of cycle "
                    f"duration ({cycle_seconds:.0f}s)\n"
                    "   → Might not leave enough time for wash/baseline"
                )

        # Check 2: Very short cycles with injection
        if cycle.length_minutes < 2.0 and cycle.injection_method:
            warnings.append(
                f"⚠️ Short cycle ({cycle.length_minutes:.1f} min) may be "
                "rushed\n   → Consider 3-5 min minimum for manual injection"
            )

        # Check 3: Multi-injection binding/kinetic cycles (P4SPR only — AffiPump timing set by loop/flow)
        if not self._has_affipump and cycle.type in ("Binding", "Kinetic") and cycle.planned_concentrations:
            n = len(cycle.planned_concentrations)
            is_parallel = len(getattr(cycle, 'concentrations', {})) > 1

            if is_parallel:
                secs = cycle.length_minutes * 60
                min_needed = (cycle.contact_time or 0) + 60
                if secs < min_needed:
                    warnings.append(
                        f"⚠️ {n} parallel injections in {cycle.length_minutes:.1f} min\n"
                        f"   → With {cycle.contact_time:.0f}s contact, need {min_needed / 60:.1f} min minimum\n"
                        f"   → Consider {min_needed / 60:.1f} min"
                    )
            else:
                secs = cycle.length_minutes * 60
                per = secs / n
                if per < (cycle.contact_time or 0) + 60:
                    warnings.append(
                        f"⚠️ {n} sequential injections in {cycle.length_minutes:.1f} min = "
                        f"{per:.0f}s each\n"
                        f"   → With {cycle.contact_time:.0f}s contact, this is tight\n"
                        f"   → Consider {((cycle.contact_time or 0) + 120) * n / 60:.1f} min"
                    )

        # Check 4: Detection explicitly off (with mode conflict check)
        det = getattr(cycle, 'detection_priority', 'auto')
        manual_mode = getattr(cycle, 'manual_injection_mode', None)
        
        if cycle.injection_method and det == 'off':
            # Detection off - warn if not in manual injection mode
            if manual_mode != 'manual':
                warnings.append(
                    "⚠️ Injection detection is OFF but manual injection mode is not enabled\n"
                    "   → Detection won't auto-flag injections\n"
                    "   → Either enable 'Manual Injection Mode' or set detection to 'Auto'"
                )
            else:
                warnings.append(
                    "⚠️ Injection detection is OFF\n"
                    "   → You must manually place all flags\n"
                    "   → Set to 'Auto' for assisted detection"
                )

        # Check 5: High sensitivity factor
        mode = getattr(cycle, 'method_mode', 'manual')
        if mode == 'manual' and det == 'priority':
            warnings.append(
                "ℹ️ High sensitivity detection (factor = 2.0)\n"
                "   → Conservative — avoids false positives\n"
                "   → May miss weak injections"
            )

        if warnings:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Cycle Validation")
            msg.setText("Potential issues detected:\n\n" + "\n\n".join(warnings))
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.setMinimumWidth(480)
            msg.exec()

    def _copy_schedule_to_clipboard(self):
        """Copy injection schedule to clipboard in a print-friendly tracking format."""
        from PySide6.QtWidgets import QApplication
        from datetime import datetime

        if not self._local_cycles:
            return

        now = datetime.now().strftime("%B %d, %Y")
        method_name = self.method_name_input.text().strip() or "Untitled Method"

        lines = []
        lines.append("=" * 70)
        lines.append(f"  SPR EXPERIMENT SCHEDULE — {method_name}")
        lines.append("=" * 70)
        lines.append(f"  Date: {now}")
        lines.append(f"  Total Cycles: {len(self._local_cycles)}")
        lines.append("")

        # Build schedule with human-friendly formatting
        inj_num = 1
        for i, cycle in enumerate(self._local_cycles, 1):
            duration = f"{cycle.length_minutes:.1f}min" if cycle.length_minutes else "—"

            # Cycle header
            lines.append(f"{'─' * 70}")
            lines.append(f"  Cycle {i}: {cycle.type} • {duration}")
            lines.append("")

            # Show injections if any
            ct = getattr(cycle, 'contact_time', None)
            contact = f" • {ct:.0f}s contact" if ct else ""

            if cycle.planned_concentrations:
                # Injection events for this cycle (parallel channels already grouped)
                for conc in cycle.planned_concentrations:
                    lines.append(f"    ☐  Injection {inj_num}: {conc}{contact}")
                    inj_num += 1
            elif cycle.injection_method:
                # Single injection
                conc_str = ""
                if cycle.concentrations:
                    parts = [f"Channel {ch.upper()} at {v}" for ch, v in cycle.concentrations.items()]
                    conc_str = " • ".join(parts)
                elif cycle.concentration_value is not None:
                    conc_str = f"{cycle.concentration_value} {cycle.concentration_units or 'nM'}"

                if conc_str:
                    lines.append(f"    ☐  Injection {inj_num}: {conc_str}{contact}")
                else:
                    lines.append(f"    ☐  Injection {inj_num}{contact}")
                inj_num += 1
            else:
                # Buffer-only cycle (no injection)
                lines.append(f"       (Buffer only — no injection)")

            lines.append("")

        # Summary footer
        lines.append("=" * 70)
        inj_total = inj_num - 1
        buffer_only = sum(1 for c in self._local_cycles if not c.injection_method)
        total_min = sum(c.length_minutes for c in self._local_cycles)
        hours = total_min // 60
        mins = total_min % 60

        if hours > 0:
            runtime = f"{int(hours)}h {int(mins)}min"
        else:
            runtime = f"{int(mins)}min"

        lines.append("")
        lines.append(f"  SUMMARY:")
        lines.append(f"    • Total manual injections: {inj_total}")
        lines.append(f"    • Buffer-only cycles: {buffer_only}")
        lines.append(f"    • Estimated runtime: {runtime}")
        lines.append("")
        lines.append("  NOTES:")
        lines.append("  " + "_" * 66)
        lines.append("")
        lines.append("  " + "_" * 66)
        lines.append("")
        lines.append("=" * 70)

        QApplication.clipboard().setText("\n".join(lines))

        # Flash confirmation on the button itself
        self._copy_schedule_btn.setText("✓ Copied!")
        self._copy_schedule_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(52,199,89,0.1);"
            "  color: #34C759;"
            "  border: 1px solid rgba(52,199,89,0.4);"
            "  border-radius: 8px;"
            "  padding: 8px 16px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "}"
        )
        QTimer.singleShot(2000, self._reset_copy_schedule_btn)

    def _reset_copy_schedule_btn(self):
        """Restore Copy Schedule button to default state."""
        self._copy_schedule_btn.setText("\U0001F4CB Copy Schedule")
        self._copy_schedule_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent;"
            "  color: #007AFF;"
            "  border: 1px solid rgba(0,122,255,0.3);"
            "  border-radius: 8px;"
            "  padding: 8px 16px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:hover { background: rgba(0,122,255,0.08); }"
        )
