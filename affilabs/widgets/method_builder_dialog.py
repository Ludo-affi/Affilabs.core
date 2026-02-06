"""Method Builder Dialog - Popup for building cycle configurations.

Replaces the cramped sidebar form with a spacious popup dialog for better UX.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QKeyEvent, QCursor
from affilabs.domain.cycle import Cycle
from affilabs.services.queue_preset_storage import QueuePresetStorage
import time


class NotesTextEdit(QPlainTextEdit):
    """Custom text edit with history navigation via Up/Down arrows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_dialog = None  # Will be set by parent

    def keyPressEvent(self, event: QKeyEvent):
        """Handle Up/Down arrow keys for history navigation and ENTER for @spark commands."""
        if not self._parent_dialog:
            super().keyPressEvent(event)
            return

        # ENTER key → If @spark command OR waiting for response, trigger processing
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            text_stripped = self.toPlainText().strip()

            # If we're waiting for a response (like answering "5" to "How many concentrations?")
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
        method_ready: Emitted when user wants to push method (action, cycles)
            action is either "queue" or "start"
    """

    method_ready = Signal(str, list)  # (action, list of cycles)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Build Method")
        self.setMinimumSize(700, 650)
        self._local_cycles = []  # Cycles built in this dialog
        self._notes_history = []  # History of previous notes
        self._history_index = -1  # Current position in history (-1 = not browsing)
        self._current_draft = ""  # Store current text when browsing history
        self._helper_active = False  # Track if helper is responding
        self._preset_storage = QueuePresetStorage()  # For @preset and !save commands
        self._waiting_for_response = False  # Track if we're waiting for user answer
        self._pending_command = None  # Store the command waiting for answer (e.g., "amine_coupling", "build")
        self._setup_ui()

    def _detect_and_respond_to_question(self):
        """Detect if user is asking a question and provide helpful suggestions.

        Also searches saved presets if text matches a preset name.
        Handles multi-turn conversations (ask question → get answer → generate result).
        """
        text = self.notes_input.toPlainText().strip()
        text_lower = text.lower()

        print("\n=== DEBUG: _detect_and_respond_to_question ===")
        print(f"Input text: '{text}'")
        print(f"Input text_lower: '{text_lower}'")
        print(f"_waiting_for_response: {self._waiting_for_response}")
        print(f"_pending_command: {self._pending_command}")

        if not text:
            # Show message if empty
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Ask Spark",
                "Type a question like:\n\n"
                "• @spark how do I run a titration?\n"
                "• @spark show me kinetics\n"
                "• @spark what's a full cycle?\n"
                "• @spark how do I regenerate?\n\n"
                "Or just type the question and click Spark button!")
            return

        if self._helper_active:
            print("DEBUG: Helper is active, returning early")
            return

        # Check if we're waiting for a response to a question
        if self._waiting_for_response:
            print("DEBUG: Waiting for response - calling _process_user_answer")
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

        # Question patterns and responses
        import re
        matched = False

        # Check for "build" with number extraction
        build_match = re.search(r'build.*?(\d+)', text_lower)
        if build_match:
            # Extract number of concentrations
            num_concentrations = int(build_match.group(1))
            # Generate the pattern: concentration 15min, regeneration 2min, baseline 2min (repeated)
            cycles = []
            for i in range(num_concentrations):
                cycles.append(f"Concentration 15min [A]  # Concentration {i+1}")
                cycles.append("Regeneration 2min [ALL]")
                cycles.append("Baseline 2min [ALL]")
            response = "\n".join(cycles)
            matched = True

        # If just "build" without number, ask for concentrations
        elif re.search(r'\bbuild\b', text_lower):
            self._ask_question("How many concentrations? (e.g., type '5' and press Enter)", "build")
            return

        # Check each pattern
        elif re.search(r'titration|dose.?response|concentration series|serial dilution', text_lower):
            response = ("Baseline 5min [ALL]\n"
                       "Concentration 2min [A:10nM] contact 120s\n"
                       "Concentration 2min [A:50nM] contact 120s\n"
                       "Concentration 2min [A:100nM] contact 120s\n"
                       "Concentration 2min [A:500nM] contact 120s\n"
                       "Regeneration 30sec [ALL:50mM]")
            matched = True

        elif re.search(r'kinetics|kinetic|dissociation|off.?rate', text_lower):
            response = ("Baseline 2min [ALL]\n"
                       "Concentration 2min [A:100nM] contact 120s\n"
                       "Baseline 10min [ALL]  # Dissociation phase\n"
                       "Regeneration 30sec [ALL:50mM]")
            matched = True

        elif re.search(r'full cycle|complete cycle|entire run|whole method', text_lower):
            response = ("Baseline 5min [ALL]\n"
                       "Concentration 2min [A:100nM] contact 120s\n"
                       "Regeneration 30sec [ALL:50mM]")
            matched = True

        elif re.search(r'regeneration|regen|clean|wash|remove', text_lower):
            response = "Regeneration 30sec [ALL:50mM]"
            matched = True

        elif re.search(r'binding|association|inject|sample|analyte', text_lower):
            response = ("Concentration 2min [A:100nM] contact 120s [B:50nM] contact 120s\n"
                       "Concentration 5min [A:200nM] contact 180s\n"
                       "Concentration 10min [A:500nM] contact 300s")
            matched = True

        # IMPORTANT: Amine coupling BEFORE immobilization to catch "coupling" before "couple"
        elif re.search(r'amine coupling|amine|coupling|build.*coupling|main coupling', text_lower):
            # Ask how many concentrations
            self._ask_question("How many concentrations? (e.g., type '5' and press Enter)", "amine_coupling")
            return

        elif re.search(r'immobilization|immobilize|immob|attach', text_lower):
            response = "Immobilization 10min [A:50µg/mL] contact 180s"
            matched = True

        elif re.search(r'baseline|start|begin|initial', text_lower):
            response = "Baseline 5min [ALL]"
            matched = True

        if matched:
            self._show_suggestion(response)
        else:
            # No match found - show available options including presets
            from PySide6.QtWidgets import QMessageBox
            preset_list = "\n".join(f"• @{name}" for name in preset_names) if preset_names else ""
            preset_section = f"\n\nSaved Presets:\n{preset_list}" if preset_names else ""

            QMessageBox.information(self, "Spark Says...",
                f"I didn't understand that question.\n\n"
                f"Try asking Spark:\n"
                f"• @spark how do I run a titration?\n"
                f"• @spark show me kinetics\n"
                f"• @spark what's a full cycle?\n"
                f"• @spark how do I regenerate?"
                f"{preset_section}")

    def _ask_question(self, question, command):
        """Ask user a question and wait for their answer.

        Args:
            question: The question to show in placeholder
            command: The command this question is for (e.g., "amine_coupling", "build")
        """
        print(f"DEBUG: _ask_question called with question='{question}', command='{command}'")
        self._waiting_for_response = True
        self._pending_command = command

        # Clear input and show question as placeholder
        self.notes_input.clear()
        self.notes_input.setPlaceholderText(f"⚡ {question}")
        print(f"DEBUG: Placeholder set to: '⚡ {question}'")
        print(f"DEBUG: _waiting_for_response = {self._waiting_for_response}")
        print(f"DEBUG: _pending_command = {self._pending_command}")

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

        print(f"DEBUG: _process_user_answer called with: '{answer}'")
        print(f"DEBUG: _pending_command = '{self._pending_command}'")

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

        num_concentrations = int(number_match.group(1))
        print(f"DEBUG: Extracted number: {num_concentrations}")

        # Generate response based on command
        if command == "amine_coupling":
            # Generate amine coupling method with N concentrations
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
            cycles.append("# Concentration series")
            # Add concentration cycles
            for i in range(num_concentrations):
                cycles.append(f"Concentration 15min [A]  # Concentration {i+1}")
                cycles.append("Regeneration 2min [ALL]")
                cycles.append("Baseline 2min [ALL]")
            response = "\n".join(cycles)

        elif command == "build":
            # Generate build pattern
            cycles = []
            for i in range(num_concentrations):
                cycles.append(f"Concentration 15min [A]  # Concentration {i+1}")
                cycles.append("Regeneration 2min [ALL]")
                cycles.append("Baseline 2min [ALL]")
            response = "\n".join(cycles)
            print(f"DEBUG: Build command generated {len(cycles)} lines for {num_concentrations} concentrations")
            print(f"DEBUG: Response preview: {response[:100]}...")
        else:
            response = "Error: Unknown command"
            print(f"DEBUG: Unknown command '{command}'")

        print(f"DEBUG: Calling _show_suggestion with {len(response)} characters")
        self._show_suggestion(response)

    def _show_suggestion(self, text):
        """Show a suggestion by replacing the input text and showing a tooltip.

        Args:
            text: The suggestion text to show
        """
        self._helper_active = True
        # Replace text with suggestion
        self.notes_input.setPlainText(text)
        # Show tooltip
        from PySide6.QtWidgets import QToolTip
        from PySide6.QtGui import QCursor
        QToolTip.showText(
            QCursor.pos(),
            "⚡ Spark suggestion! Edit as needed.",
            self.notes_input,
            self.notes_input.rect(),
            3000
        )
        self._helper_active = False

    def _setup_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header with title and preset button
        header_row = QHBoxLayout()
        title = QLabel("Build Cycle Method")
        title.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #1D1D1F; "
            "font-family: -apple-system, 'SF Pro Display', 'Segoe UI', sans-serif;"
        )
        header_row.addWidget(title)
        header_row.addStretch()
        layout.addLayout(header_row)
        layout.addSpacing(12)

        # Notes field with header and help button
        notes_header = QHBoxLayout()
        notes_label = QLabel("Note:")
        notes_header.addWidget(notes_label)

        # Spark AI button
        ask_btn = QPushButton("⚡ Spark")
        ask_btn.setFixedSize(60, 24)
        ask_btn.setStyleSheet(
            "QPushButton {"
            "  background: #34C759;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 10px;"
            "  font-size: 11px;"
            "  font-weight: bold;"
            "  padding: 2px 4px;"
            "}"
            "QPushButton:hover { background: #28A745; }"
        )
        ask_btn.setToolTip("Spark AI: Type @spark question or click to activate")
        ask_btn.clicked.connect(self._detect_and_respond_to_question)
        notes_header.addWidget(ask_btn)

        # Help button
        help_btn = QPushButton("?")
        help_btn.setFixedSize(20, 20)
        help_btn.setStyleSheet(
            "QPushButton {"
            "  background: #007AFF;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 10px;"
            "  font-size: 11px;"
            "  font-weight: bold;"
            "}"
            "QPushButton:hover { background: #0051D5; }"
        )
        help_btn.setToolTip("Show notes syntax help")
        help_btn.clicked.connect(self._show_notes_help)
        notes_header.addWidget(help_btn)
        notes_header.addStretch()
        layout.addLayout(notes_header)

        # Notes input with history navigation
        self.notes_input = NotesTextEdit()
        self.notes_input._parent_dialog = self  # Set reference for history navigation
        self.notes_input.setPlaceholderText(
            "Ask Spark or write cycles directly:\n\n"
            "⚡ Ask Spark: @spark how do I run a titration?\n\n"
            "Or write directly (one per line):\n"
            "Baseline 5min [ALL]\n"
            "Concentration 2min [A:100nM] [B:50µM]\n\n"
            "📦 Load preset: @preset_name\n"
            "💾 Save method: !save preset_name\n"
            "↑/↓ arrows to recall previous notes"
        )
        self.notes_input.setMinimumHeight(100)
        layout.addWidget(self.notes_input)

        # Character counter
        self.char_count_label = QLabel("0/1500 characters")
        self.char_count_label.setStyleSheet(
            "font-size: 11px; color: #86868B;"
        )
        self.notes_input.textChanged.connect(self._update_char_count)
        layout.addWidget(self.char_count_label)
        layout.addSpacing(12)

        # Method Queue section
        queue_header = QHBoxLayout()
        queue_label = QLabel("Method Queue:")
        queue_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #1D1D1F;")
        queue_header.addWidget(queue_label)
        queue_header.addStretch()

        # Compact Add to Method button
        self.add_to_method_btn = QPushButton("➕ Add to Method")
        self.add_to_method_btn.setFixedHeight(28)
        self.add_to_method_btn.setStyleSheet(
            "QPushButton {"
            "  background: #007AFF;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 4px 16px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:hover { background: #0051D5; }"
            "QPushButton:pressed { background: #003D99; }"
        )
        self.add_to_method_btn.clicked.connect(self._on_add_to_method)
        queue_header.addWidget(self.add_to_method_btn)
        layout.addLayout(queue_header)

        # Local queue table
        self.method_table = QTableWidget()
        self.method_table.setColumnCount(3)
        self.method_table.setHorizontalHeaderLabels(["Type", "Duration (min)", "Notes"])
        self.method_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.method_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.method_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.method_table.setMaximumHeight(300)  # Increased from 180px to show more cycles
        self.method_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.method_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.method_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.method_table.verticalHeader().setVisible(True)  # Show row numbers
        self.method_table.setStyleSheet(
            "QTableWidget {"
            "  background: white;"
            "  border: 1px solid rgba(0,0,0,0.1);"
            "  border-radius: 4px;"
            "  font-size: 12px;"
            "}"
            "QHeaderView::section {"
            "  background: rgba(0,0,0,0.03);"
            "  padding: 4px;"
            "  border: none;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "}"
        )
        layout.addWidget(self.method_table)

        # Queue control buttons
        queue_btn_row = QHBoxLayout()

        self.undo_btn = QPushButton("↶ Undo")
        self.undo_btn.setFixedHeight(28)
        self.undo_btn.setEnabled(False)
        self.undo_btn.setToolTip("Undo last action (Ctrl+Z)")
        self.undo_btn.setStyleSheet(
            "QPushButton {"
            "  background: white;"
            "  color: #1D1D1F;"
            "  border: 1px solid rgba(0,0,0,0.1);"
            "  border-radius: 4px;"
            "  padding: 4px 12px;"
            "  font-size: 12px;"
            "}"
            "QPushButton:hover { background: #F5F5F7; }"
            "QPushButton:disabled { color: #C7C7CC; border-color: rgba(0,0,0,0.05); }"
        )
        queue_btn_row.addWidget(self.undo_btn)

        self.redo_btn = QPushButton("↷ Redo")
        self.redo_btn.setFixedHeight(28)
        self.redo_btn.setEnabled(False)
        self.redo_btn.setToolTip("Redo last action (Ctrl+Shift+Z)")
        self.redo_btn.setStyleSheet(
            "QPushButton {"
            "  background: white;"
            "  color: #1D1D1F;"
            "  border: 1px solid rgba(0,0,0,0.1);"
            "  border-radius: 4px;"
            "  padding: 4px 12px;"
            "  font-size: 12px;"
            "}"
            "QPushButton:hover { background: #F5F5F7; }"
            "QPushButton:disabled { color: #C7C7CC; border-color: rgba(0,0,0,0.05); }"
        )
        queue_btn_row.addWidget(self.redo_btn)

        # Separator
        separator = QLabel("|")
        separator.setStyleSheet("color: rgba(0,0,0,0.1); font-size: 14px; margin: 0 4px;")
        queue_btn_row.addWidget(separator)

        self.delete_cycle_btn = QPushButton("🗑 Delete")
        self.delete_cycle_btn.setFixedHeight(28)
        self.delete_cycle_btn.setEnabled(False)
        self.delete_cycle_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent;"
            "  color: #FF3B30;"
            "  border: 1px solid rgba(255,59,48,0.3);"
            "  border-radius: 4px;"
            "  padding: 4px 12px;"
            "  font-size: 12px;"
            "}"
            "QPushButton:hover { background: rgba(255,59,48,0.1); }"
            "QPushButton:disabled { color: #C7C7CC; border-color: rgba(0,0,0,0.1); }"
        )
        self.delete_cycle_btn.clicked.connect(self._on_delete_selected)
        queue_btn_row.addWidget(self.delete_cycle_btn)

        self.move_up_btn = QPushButton("↑")
        self.move_up_btn.setFixedSize(28, 28)
        self.move_up_btn.setEnabled(False)
        self.move_up_btn.setStyleSheet(
            "QPushButton { background: #F2F2F7; border: none; border-radius: 4px; font-size: 14px; }"
            "QPushButton:hover { background: #E5E5EA; }"
            "QPushButton:disabled { background: #F2F2F7; color: #C7C7CC; }"
        )
        self.move_up_btn.clicked.connect(self._on_move_up)
        queue_btn_row.addWidget(self.move_up_btn)

        self.move_down_btn = QPushButton("↓")
        self.move_down_btn.setFixedSize(28, 28)
        self.move_down_btn.setEnabled(False)
        self.move_down_btn.setStyleSheet(
            "QPushButton { background: #F2F2F7; border: none; border-radius: 4px; font-size: 14px; }"
            "QPushButton:hover { background: #E5E5EA; }"
            "QPushButton:disabled { background: #F2F2F7; color: #C7C7CC; }"
        )
        self.move_down_btn.clicked.connect(self._on_move_down)
        queue_btn_row.addWidget(self.move_down_btn)

        self.clear_method_btn = QPushButton("Clear All")
        self.clear_method_btn.setFixedHeight(28)
        self.clear_method_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent;"
            "  color: #86868B;"
            "  border: 1px solid rgba(0,0,0,0.1);"
            "  border-radius: 4px;"
            "  padding: 4px 12px;"
            "  font-size: 12px;"
            "}"
            "QPushButton:hover { background: rgba(0,0,0,0.05); }"
        )
        self.clear_method_btn.clicked.connect(self._on_clear_method)
        queue_btn_row.addWidget(self.clear_method_btn)

        self.method_count_label = QLabel("0 cycles")
        self.method_count_label.setStyleSheet("font-size: 11px; color: #86868B;")
        queue_btn_row.addWidget(self.method_count_label)
        queue_btn_row.addStretch()
        layout.addLayout(queue_btn_row)

        layout.addStretch()

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background: rgba(0,0,0,0.1);")
        layout.addWidget(separator)

        # Action buttons
        button_row = QHBoxLayout()

        # Close button (left side)
        self.close_btn = QPushButton("Close")
        self.close_btn.setFixedHeight(40)
        self.close_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent;"
            "  color: #86868B;"
            "  border: 1px solid rgba(0,0,0,0.1);"
            "  border-radius: 8px;"
            "  padding: 8px 24px;"
            "  font-size: 14px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:hover { background: rgba(0,0,0,0.05); }"
            "QPushButton:pressed { background: rgba(0,0,0,0.1); }"
        )
        self.close_btn.clicked.connect(self.reject)
        button_row.addWidget(self.close_btn)
        button_row.addStretch()

        # Push to Queue button
        self.queue_btn = QPushButton("📋 Push to Queue")
        self.queue_btn.setFixedHeight(40)
        self.queue_btn.setStyleSheet(
            "QPushButton {"
            "  background: #007AFF;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 8px 24px;"
            "  font-size: 14px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:hover { background: #0051D5; }"
            "QPushButton:pressed { background: #003D99; }"
        )
        self.queue_btn.clicked.connect(self._on_push_to_queue)
        button_row.addWidget(self.queue_btn)

        layout.addLayout(button_row)

    def _update_char_count(self):
        """Update character counter and enforce 1500 char limit."""
        text = self.notes_input.toPlainText()
        if len(text) > 1500:
            self.notes_input.setPlainText(text[:1500])
            cursor = self.notes_input.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.notes_input.setTextCursor(cursor)
        self.char_count_label.setText(f"{len(self.notes_input.toPlainText())}/1500 characters")

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
<li>Click <b>📋 Push to Queue</b> — cycles move to the main Cycle Queue</li>
<li>Press <b>▶ Start Run</b> in the sidebar — cycles run automatically in order</li>
<li>After the last cycle, the system enters <b>Auto-Read</b> (continuous 2-hour monitoring)</li>
</ol>

<hr/>

<h4>Cycle Syntax</h4>
<p><code>Type Duration [ChannelTags] contact Ns partial injection</code></p>

<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse; font-size:12px;">
<tr style="background:#f0f0f0;"><th>Part</th><th>Required?</th><th>Description</th></tr>
<tr><td><b>Type</b></td><td>Yes</td><td>One of: Baseline, Concentration, Regeneration, Immobilization, Wash, Other</td></tr>
<tr><td><b>Duration</b></td><td>Yes</td><td>e.g. <code>5min</code>, <code>30sec</code>, <code>2m</code>, <code>30s</code>. Default is 5 min if omitted.</td></tr>
<tr><td><b>[Tags]</b></td><td>No</td><td>Channel + optional concentration: <code>[A]</code> <code>[ALL:100nM]</code> <code>[B:50µM]</code></td></tr>
<tr><td><b>contact Ns</b></td><td>No</td><td>Injection contact time: <code>contact 180s</code> or <code>contact 3min</code></td></tr>
<tr><td><b>partial injection</b></td><td>No</td><td>Use partial (30µL spike) instead of simple injection</td></tr>
</table>

<hr/>

<h4>Cycle Types Explained</h4>
<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse; font-size:12px;">
<tr style="background:#f0f0f0;"><th>Type</th><th>Injection</th><th>Contact Time</th><th>Purpose</th></tr>
<tr><td><b>Baseline</b></td><td>None</td><td>—</td><td>Running buffer flow, establish stable baseline signal</td></tr>
<tr><td><b>Concentration</b></td><td>Simple (or partial)</td><td>User-specified</td><td>Inject analyte sample, measure binding (association)</td></tr>
<tr><td><b>Regeneration</b></td><td>Simple</td><td>30s (auto-set)</td><td>Strip bound analyte from surface, restore baseline</td></tr>
<tr><td><b>Immobilization</b></td><td>Simple</td><td>User-specified</td><td>Attach ligand to sensor surface (e.g. protein, antibody)</td></tr>
<tr><td><b>Wash</b></td><td>Simple</td><td>User-specified</td><td>Rinse flow path between steps (activation, blocking, etc.)</td></tr>
<tr><td><b>Other</b></td><td>None</td><td>—</td><td>Custom step (activation, blocking, equilibration, etc.)</td></tr>
</table>
<p><b>All injections start at 20 seconds</b> into the cycle (fixed delay for baseline stabilization).</p>

<hr/>

<h4>Concentration &amp; Unit Tags</h4>
<p>Tag format: <code>[Channel:ValueUnits]</code></p>
<ul>
<li>Channels: <code>A</code>, <code>B</code>, <code>C</code>, <code>D</code>, <code>ALL</code></li>
<li>Units: <code>nM</code>, <code>µM</code>, <code>pM</code>, <code>mM</code>, <code>M</code>, <code>mg/mL</code>, <code>µg/mL</code>, <code>ng/mL</code></li>
<li>Examples: <code>[A:100nM]</code>  <code>[B:50µM]</code>  <code>[ALL:25pM]</code></li>
<li>Multiple tags per line: <code>[A:100nM] [B:50nM]</code></li>
</ul>

<hr/>

<h4>Examples — One Line per Cycle</h4>
<pre style="background:#f5f5f7; padding:8px; border-radius:4px; font-size:12px;">
Baseline 5min
Concentration 5min [A:100nM] contact 180s
Concentration 5min [A:500nM] contact 180s
Regeneration 30sec [ALL:50mM]
Baseline 2min
</pre>

<h4>Kinetics Example (Association + Dissociation)</h4>
<pre style="background:#f5f5f7; padding:8px; border-radius:4px; font-size:12px;">
Baseline 2min
Concentration 5min [A:100nM] contact 120s
Baseline 10min
Regeneration 30sec [ALL:50mM]
</pre>

<h4>Amine Coupling + Titration</h4>
<pre style="background:#f5f5f7; padding:8px; border-radius:4px; font-size:12px;">
Baseline 30sec
Other 4min
Wash 30sec contact 30s
Immobilization 4min [A:50µg/mL] contact 180s
Wash 30sec contact 30s
Other 4min
Wash 30sec contact 30s
Baseline 15min
Concentration 15min [A:10nM] contact 180s
Regeneration 2min [ALL:50mM]
Baseline 2min
Concentration 15min [A:50nM] contact 180s
Regeneration 2min [ALL:50mM]
Baseline 2min
</pre>

<hr/>

<h4>⚡ Spark AI Shortcuts</h4>
<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse; font-size:12px;">
<tr style="background:#f0f0f0;"><th>Command</th><th>What it does</th></tr>
<tr><td><code>@spark titration</code></td><td>Generate a dose-response titration template</td></tr>
<tr><td><code>@spark kinetics</code></td><td>Generate an association/dissociation template</td></tr>
<tr><td><code>@spark amine coupling</code></td><td>Full amine coupling method (asks how many concentrations)</td></tr>
<tr><td><code>build 5</code></td><td>Generate 5 concentration cycles (15min + regen + baseline each)</td></tr>
<tr><td><code>build 10</code></td><td>Generate 10 concentration cycles</td></tr>
<tr><td><code>@spark regeneration</code></td><td>Regeneration cycle template</td></tr>
<tr><td><code>@spark baseline</code></td><td>Baseline cycle template</td></tr>
</table>

<hr/>

<h4>📦 Presets — Save &amp; Reuse Methods</h4>
<ul>
<li><b>Save:</b> Build your method, then type <code>!save my_method_name</code> and click Add to Method</li>
<li><b>Load:</b> Type <code>@my_method_name</code> and click Spark to load a saved preset</li>
</ul>

<hr/>

<h4>Queue Controls</h4>
<ul>
<li><b>↑ / ↓</b> — Reorder cycles in the method table</li>
<li><b>🗑 Delete</b> — Remove selected cycle</li>
<li><b>Clear All</b> — Remove all cycles from the method</li>
<li><b>↶ Undo / ↷ Redo</b> — Undo or redo changes (Ctrl+Z / Ctrl+Shift+Z)</li>
<li><b>↑/↓ arrows</b> in the Note field — Recall previously typed notes</li>
</ul>

<h4>Execution Behavior</h4>
<ul>
<li>Cycles run in order and <b>auto-advance</b> when the timer expires</li>
<li>Press <b>⏭ Next Cycle</b> to skip to the next cycle early (data is preserved)</li>
<li>After the last cycle, the system enters <b>Auto-Read</b> mode (2 hours of continuous monitoring)</li>
<li>The intelligence bar shows a countdown and previews the next cycle in the last 10 seconds</li>
</ul>
        """

        # Create modeless dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Notes Syntax Help")
        dialog.setModal(False)  # Non-blocking - user can still type in main window
        dialog.resize(500, 600)

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

    def _build_cycle_from_text(self, text: str) -> Cycle:
        """Build Cycle object from a single line of text.

        Args:
            text: Single line like "Baseline 5min [A:100nM] [B:50µM]"
        """
        import re

        # Parse type from text (updated cycle types)
        cycle_type = "Baseline"  # default
        type_keywords = [
            ('Baseline', r'baseline'),
            ('Immobilization', r'immobilization|immobilize|immob'),
            ('Wash', r'\bwash\b'),  # Match 'wash' as standalone word
            ('Concentration', r'concentration|conc|association|binding|inject'),
            ('Regeneration', r'regeneration|regen|clean'),
            ('Other', r'other|custom'),
        ]

        for type_name, pattern in type_keywords:
            if re.search(pattern, text, re.IGNORECASE):
                cycle_type = type_name
                break

        # Parse duration from text (e.g., "5min", "30sec", "2min")
        duration_minutes = 5.0  # default
        duration_match = re.search(r'(\d+(?:\.\d+)?)(min|sec|m|s)', text, re.IGNORECASE)
        if duration_match:
            value = float(duration_match.group(1))
            unit = duration_match.group(2).lower()
            if unit in ['sec', 's']:
                duration_minutes = value / 60.0
            else:  # min or m
                duration_minutes = value

        # Parse concentration tags WITH units: [A:100nM], [B:50µM], [ALL:25pM], etc.
        tags_with_units = re.findall(r"\[([A-D]|ALL):(\d+\.?\d*)([a-zA-Zµ/]+)?\]", text)

        # Extract concentrations and detect units
        concentrations = {}
        detected_unit = "nM"  # default

        for ch, val, unit_str in tags_with_units:
            concentrations[ch] = float(val)
            if unit_str:  # If units specified in tag, use it
                detected_unit = unit_str

        # Parse contact time (e.g., "contact 180s", "contact 3min")
        contact_time = None
        contact_match = re.search(r'contact[:\s]+(\d+(?:\.\d+)?)(s|sec|m|min)?', text, re.IGNORECASE)
        if contact_match:
            value = float(contact_match.group(1))
            unit = contact_match.group(2).lower() if contact_match.group(2) else 's'
            if unit in ['m', 'min']:
                contact_time = value * 60.0  # Convert to seconds
            else:
                contact_time = value

        # Parse partial injection override (e.g., "partial injection", "partial")
        is_partial = bool(re.search(r'partial\s*(injection)?', text, re.IGNORECASE))

        # Auto-set injection method and contact time based on cycle type rules
        injection_method = None
        pump_type = None  # Will be auto-detected during execution

        # Injection rules by cycle type
        if cycle_type == "Immobilization":
            injection_method = "simple"
            # contact_time from parsing (required by user)
        elif cycle_type == "Wash":
            injection_method = "simple"
            # contact_time from parsing (required by user)
        elif cycle_type == "Concentration":
            injection_method = "partial" if is_partial else "simple"  # Allow override
            # contact_time from parsing (required by user)
        elif cycle_type == "Regeneration":
            injection_method = "simple"
            if contact_time is None:
                contact_time = 30.0  # Fixed 30s default for Regeneration
        # Baseline and Other get no injection (None)

        # Generate name from type + tags or just text
        if concentrations:
            tag_str = " ".join([f"[{ch}:{val}]" for ch, val in concentrations.items()])
            name = f"{cycle_type} {tag_str}"
        else:
            # Use first 30 chars of text as name
            name = text[:30] if text else cycle_type

        return Cycle(
            type=cycle_type,
            name=name,
            length_minutes=duration_minutes,
            note=text,
            status="pending",
            units=detected_unit,
            concentrations=concentrations,
            timestamp=time.time(),
            # Pump and injection fields
            injection_method=injection_method,
            injection_delay=20.0,  # Always 20s
            contact_time=contact_time,
            pump_type=pump_type,  # Auto-detected during execution
        )

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

        for line in lines:
            cycle = self._build_cycle_from_text(line)
            self._local_cycles.append(cycle)

        self._refresh_method_table()

        # Save notes to history (if not empty and not duplicate)
        if notes_text and (not self._notes_history or notes_text != self._notes_history[-1]):
            self._notes_history.append(notes_text)

        # Reset history navigation
        self._history_index = -1
        self._current_draft = ""

    def _on_clear_method(self):
        """Clear all cycles from local method."""
        self._local_cycles.clear()
        self._refresh_method_table()

    def _refresh_method_table(self):
        """Update the method table display."""
        self.method_table.setRowCount(0)

        for i, cycle in enumerate(self._local_cycles):
            row = self.method_table.rowCount()
            self.method_table.insertRow(row)

            # Column 0: Type
            type_item = QTableWidgetItem(cycle.type)
            self.method_table.setItem(row, 0, type_item)

            # Column 1: Duration
            dur_item = QTableWidgetItem(f"{cycle.length_minutes:.1f}")
            dur_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.method_table.setItem(row, 1, dur_item)

            # Column 2: Notes
            notes_item = QTableWidgetItem(cycle.note or "")
            self.method_table.setItem(row, 2, notes_item)

        # Update count label
        count = len(self._local_cycles)
        self.method_count_label.setText(f"{count} cycle{'s' if count != 1 else ''}")

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

    def _on_push_to_queue(self):
        """Push all cycles to main queue."""
        if not self._local_cycles:
            return
        self.method_ready.emit("queue", self._local_cycles.copy())
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
        else:
            QMessageBox.warning(
                self,
                "Preset Not Found",
                f"No preset named '{preset_name}' exists.\n\n"
                f"Available presets:\n" + "\n".join(f"  • {name}" for name in self._preset_storage.list_presets())
                if self._preset_storage.list_presets()
                else f"No preset named '{preset_name}' exists."
            )

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
