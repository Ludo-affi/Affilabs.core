"""Spark AI Help Widget - Operational Q&A Assistant

This widget provides a chat-like interface for users to ask questions about
how to use the ezControl software. Questions and answers are tracked in a
database for continuous improvement of responses.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QScrollArea, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from tinydb import TinyDB, Query
from datetime import datetime
import urllib.parse
import webbrowser
import re
import logging

# TinyLM integration (bundled with software)
from .spark_tinylm import SparkTinyLM

logger = logging.getLogger(__name__)


class SparkQuestionInput(QTextEdit):
    """Custom QTextEdit that submits on Enter key."""

    submit_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent):
        """Handle Enter key to submit question."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Submit on Enter
            self.submit_requested.emit()
            event.accept()
            return

        # Otherwise, allow default behavior
        super().keyPressEvent(event)


class SparkQuestionStorage:
    """Storage for tracking Spark AI questions and answers."""

    def __init__(self, db_path="spark_qa_history.json"):
        """Initialize Spark Q&A storage.

        Args:
            db_path: Path to TinyDB database file
        """
        self.db = TinyDB(db_path)
        self.qa_table = self.db.table('questions_answers')

    def log_question(self, question: str, answer: str, matched: bool = True, feedback: str = None):
        """Log a question and answer pair.

        Args:
            question: User's question text
            answer: Spark's answer/response
            matched: Whether a matching response was found
            feedback: Optional user feedback (helpful/not helpful)
            
        Returns:
            int: Database ID of the inserted entry
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'question': question,
            'answer': answer,
            'matched': matched,
            'feedback': feedback,
        }
        doc_id = self.qa_table.insert(entry)
        return doc_id

    def get_all_questions(self):
        """Get all logged questions."""
        return self.qa_table.all()

    def get_unmatched_questions(self):
        """Get questions that didn't have a matching response."""
        Q = Query()
        return self.qa_table.search(Q.matched == False)

    def update_feedback(self, doc_id: int, feedback: str):
        """Update feedback for a Q&A entry.

        Args:
            doc_id: Document ID from TinyDB
            feedback: 'helpful' or 'not_helpful'
        """
        self.qa_table.update({'feedback': feedback}, doc_ids=[doc_id])


class QABubble(QFrame):
    """Chat bubble for displaying question or answer."""

    def __init__(self, text: str, is_question: bool = True, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Role label - minimal
        role_label = QLabel("You" if is_question else "Spark")
        role_label.setStyleSheet(
            "font-size: 12px; "
            "font-weight: 700; "
            "color: #6B6B6B; "
            "background: transparent;"
        )
        layout.addWidget(role_label)

        # Message text - clean, readable
        message = QLabel(text)
        message.setWordWrap(True)
        message.setTextFormat(Qt.TextFormat.PlainText)
        message.setStyleSheet(
            "font-size: 14px; "
            "line-height: 1.5; "
            "color: #000000; "
            "background: transparent;"
        )
        layout.addWidget(message)

        # No background styling - clean ChatGPT style
        self.setStyleSheet(
            "QFrame {"
            "  background: transparent; "
            "}"
        )


class SparkHelpWidget(QWidget):
    """Spark AI Help Widget - Operational assistance tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.qa_storage = SparkQuestionStorage()
        self.last_qa_id = None  # Track most recent Q&A for feedback

        # TinyLM integration (lazy loading - transparent to user)
        self._tinylm = SparkTinyLM()

        # Set size policy to expand vertically
        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the Spark help interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Use standard background color
        self.setStyleSheet(
            "SparkHelpWidget { "
            "  background: #F8F9FA; "
            "}"
        )

        # Conversation area (scrollable) - full width, no borders, takes all space
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet(
            "QScrollArea { "
            "  background: #F8F9FA; "
            "  border: none; "
            "}"
        )

        self.conversation_widget = QWidget()
        self.conversation_layout = QVBoxLayout(self.conversation_widget)
        self.conversation_layout.setContentsMargins(16, 16, 16, 16)
        self.conversation_layout.setSpacing(24)
        self.conversation_layout.addStretch()

        self.scroll_area.setWidget(self.conversation_widget)
        # CRITICAL: Give scroll area maximum stretch to fill all available space
        layout.addWidget(self.scroll_area, stretch=100)

        # Welcome message (no feedback buttons for welcome)
        self._add_spark_message(
            "Hi! I'm Spark ⚡\n\n"
            "I can answer short, simple questions about using ezControl.\n\n"
            "Ask me questions like:\n"
            "• How do I start an acquisition?\n"
            "• How do I export my data?\n"
            "• What's the best way to calibrate the detector?\n"
            "• How do I save a method?",
            add_feedback=False  # Don't add feedback buttons to welcome message
        )

        # Input area - sticky bottom, fixed height, minimal design
        input_container = QFrame()
        input_container.setFrameShape(QFrame.Shape.NoFrame)
        input_container.setFixedHeight(100)  # Fixed height to prevent expansion
        input_container.setStyleSheet(
            "QFrame { "
            "  background: #FFFFFF; "
            "  border-top: 1px solid #E5E5EA; "
            "}"
        )
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(16, 12, 16, 12)
        input_layout.setSpacing(12)

        # Question input - with Enter key handling
        self.question_input = SparkQuestionInput()
        self.question_input.setPlaceholderText("Message Spark...")
        self.question_input.setFixedHeight(76)  # Fixed height instead of maximum
        self.question_input.setStyleSheet(
            "QTextEdit {"
            "  background: #F7F7F8; "
            "  border: 1px solid #E0E0E0; "
            "  border-radius: 20px; "
            "  padding: 12px 16px; "
            "  font-size: 14px; "
            "  color: #000000;"
            "}"
        )
        # Connect Enter key to submit
        self.question_input.submit_requested.connect(self._handle_question)
        input_layout.addWidget(self.question_input)

        # Send button (minimal, icon-style)
        ask_btn = QPushButton("↑")
        ask_btn.setFixedSize(40, 40)
        ask_btn.setStyleSheet(
            "QPushButton {"
            "  background: #34C759; "
            "  color: white; "
            "  border: none; "
            "  border-radius: 20px; "
            "  font-size: 20px; "
            "  font-weight: bold;"
            "}"
            "QPushButton:hover { background: #28A745; }"
            "QPushButton:pressed { background: #1E7B34; }"
        )
        ask_btn.clicked.connect(self._handle_question)
        input_layout.addWidget(ask_btn)

        # Add input container with NO stretch (stretch=0 is default)
        layout.addWidget(input_container, stretch=0)

    def _add_question_bubble(self, question: str):
        """Add a question bubble to conversation."""
        # Remove stretch before adding new item
        self.conversation_layout.takeAt(self.conversation_layout.count() - 1)

        bubble = QABubble(question, is_question=True)
        self.conversation_layout.addWidget(bubble)
        self.conversation_layout.addStretch()

        # Scroll to bottom
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )

    def _add_spark_message(self, answer: str, add_feedback: bool = True):
        """Add a Spark answer bubble to conversation.
        
        Args:
            answer: Answer text to display
            add_feedback: Whether to add feedback buttons (default True)
        """
        # Remove stretch before adding new item
        if self.conversation_layout.count() > 0:
            self.conversation_layout.takeAt(self.conversation_layout.count() - 1)

        bubble = QABubble(answer, is_question=False)
        self.conversation_layout.addWidget(bubble)

        # Add feedback buttons if requested
        if add_feedback and self.last_qa_id is not None:
            self._add_feedback_buttons(self.last_qa_id)

        self.conversation_layout.addStretch()

        # Scroll to bottom
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )

    def _handle_question(self):
        """Handle user question and generate response."""
        question = self.question_input.toPlainText().strip()
        if not question:
            return

        # Add question to conversation
        self._add_question_bubble(question)
        self.question_input.clear()

        # Generate answer
        answer, matched = self._generate_answer(question)

        # Log to database first (to get the ID)
        qa_id = self.qa_storage.log_question(question, answer, matched)
        self.last_qa_id = qa_id  # Store for feedback buttons

        # Add answer to conversation (with feedback buttons)
        self._add_spark_message(answer)

        # If no match, add "Send to Support" button
        if not matched:
            self._add_support_button(question)

    def _generate_answer(self, question: str) -> tuple[str, bool]:
        """Generate answer using hybrid approach: regex first, TinyLM fallback.

        Returns:
            tuple: (answer_text, matched_pattern)
        """
        question_lower = question.lower()

        # === FAST PATH: Pattern matching for common questions ===
        # Start/Run acquisition
        if re.search(r'start|begin|run|acquire', question_lower):
            return (
                "To start an acquisition:\n\n"
                "1. Make sure the device is connected (green Power indicator)\n"
                "2. Run a calibration if needed (Settings → Calibrate)\n"
                "3. Click the Start Recording button in the sidebar\n"
                "4. Data will appear on the Full Sensorgram graph\n\n"
                "You can pause or stop the acquisition using the sidebar controls.",
                True
            )

        # Export/Save data
        elif re.search(r'export|save|download', question_lower):
            return (
                "To export your data:\n\n"
                "1. Click the Export tab in the sidebar\n"
                "2. Choose your export format (CSV, Excel, JSON)\n"
                "3. Select which channels to export (A, B, C, D)\n"
                "4. Click 'Export to File'\n\n"
                "Your data will be saved to the export destination folder.",
                True
            )

        # Calibration
        elif re.search(r'calibrat|baseline|zero', question_lower):
            return (
                "To calibrate the detector:\n\n"
                "1. Go to the Settings tab\n"
                "2. Click 'OEM LED Calibration' for automatic calibration\n"
                "3. Wait for calibration to complete (~30-60 seconds)\n"
                "4. Review the calibration report\n\n"
                "For manual baseline: Use the 'Baseline Capture' button during acquisition.",
                True
            )

        # Method building
        elif re.search(r'method|cycle|inject', question_lower):
            return (
                "To build a method:\n\n"
                "1. Go to the Method tab\n"
                "2. Add cycles to your queue (Baseline, Association, Dissociation, etc.)\n"
                "3. Set duration and concentration for each cycle\n"
                "4. Click 'Add to Queue'\n"
                "5. Click 'Start Run' to execute the method\n\n"
                "💡 Note: For advanced cycle building, you can use @spark commands "
                "in the note field to trigger automated actions (focused on execution, "
                "not general Q&A).\n\n"
                "The progress bar shows the current cycle status.",
                True
            )

        # Flow control
        elif re.search(r'channel|flow|pump', question_lower):
            return (
                "To control channels and flow:\n\n"
                "1. Go to the Flow tab\n"
                "2. Select pump operations (Prime, Cleanup, Buffer)\n"
                "3. Set flow rates for each mode (Setup/Functionalization/Assay)\n"
                "4. Use valve controls to switch between channels A/B/C/D\n\n"
                "The Flow tab shows real-time pump status and valve positions.",
                True
            )

        # Graph configuration
        elif re.search(r'graph|plot|display', question_lower):
            return (
                "To configure the graphs:\n\n"
                "1. Go to the Graphic Display tab\n"
                "2. Toggle grid, autoscale, or colorblind mode\n"
                "3. Use channel selector to choose which channels to display\n"
                "4. Apply filters (None/Light Smoothing) for noise reduction\n\n"
                "The Full Sensorgram shows live data, Active Cycle shows the selected time region.",
                True
            )

        # Troubleshooting
        elif re.search(r'error|problem|issue|troubleshoot', question_lower):
            return (
                "Common troubleshooting steps:\n\n"
                "1. Connection issues: Check USB cable, try Power Off → Power On\n"
                "2. Noisy data: Run calibration, check baseline stability\n"
                "3. No data appearing: Verify detector wait time in Advanced Settings\n"
                "4. Pump not responding: Use Emergency Stop, then Home Pumps\n\n"
                "If issues persist, check the Hardware tab for device status.",
                True
            )

        # General help
        elif re.search(r'help|how|what|guide|tutorial', question_lower):
            return (
                "I can help with:\n\n"
                "• Starting/stopping acquisitions\n"
                "• Building and running methods\n"
                "• Exporting data\n"
                "• Calibration procedures\n"
                "• Channel and flow control\n"
                "• Graph configuration\n"
                "• Saving/loading presets\n"
                "• Troubleshooting\n\n"
                "Just ask me about any of these topics!",
                True
            )

        # === CONVERSATIONAL PATH: TinyLM fallback ===
        # No pattern matched - use conversational AI (transparent to user)
        logger.debug("No pattern match - using conversational AI")
        answer, success = self._tinylm.generate_answer(question)
        return (answer, success)

    def _add_support_button(self, question: str):
        """Add a button to send question to support team."""
        # Remove stretch before adding button
        self.conversation_layout.takeAt(self.conversation_layout.count() - 1)

        # Create button container
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 4, 0, 4)

        support_btn = QPushButton("📧 Send Question to Support")
        support_btn.setFixedHeight(32)
        support_btn.setStyleSheet(
            "QPushButton {"
            "  background: #007AFF; "
            "  color: white; "
            "  border: none; "
            "  border-radius: 6px; "
            "  padding: 6px 16px; "
            "  font-size: 12px; "
            "  font-weight: 600;"
            "}"
            "QPushButton:hover { background: #0051D5; }"
            "QPushButton:pressed { background: #003D99; }"
        )
        support_btn.clicked.connect(lambda: self._send_to_support(question))
        btn_layout.addWidget(support_btn)
        btn_layout.addStretch()

        self.conversation_layout.addWidget(btn_container)
        self.conversation_layout.addStretch()

    def _send_to_support(self, question: str):
        """Send question to support via email."""
        # Email configuration
        support_email = "info@affiniteinstruments.com"
        subject = "Spark AI - Unanswered Question"
        body = (
            f"Hello AffiLabs Support Team,\n\n"
            f"I asked Spark AI the following question, but it couldn't provide an answer:\n\n"
            f"Question: {question}\n\n"
            f"Could you please help me with this?\n\n"
            f"Thank you,\n"
            f"ezControl User\n\n"
            f"---\n"
            f"Timestamp: {datetime.now().isoformat()}\n"
            f"Sent from ezControl Spark AI Assistant"
        )

        # Create mailto URL
        mailto_url = f"mailto:{support_email}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"

        try:
            # Open default email client
            webbrowser.open(mailto_url)

            # Show confirmation (no feedback buttons for system messages)
            self._add_spark_message(
                "✅ Email draft created! Your default email client should open with a pre-filled message. "
                "Just click send when you're ready.",
                add_feedback=False
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Email Error",
                f"Couldn't open email client.\n\n"
                f"Please email your question manually to:\n{support_email}\n\n"
                f"Error: {str(e)}"
            )
    def _add_feedback_buttons(self, qa_id: int):
        """Add thumbs up/down feedback buttons for the last answer.
        
        Args:
            qa_id: Database ID of the Q&A entry to attach feedback to
        """
        # Remove stretch before adding buttons
        self.conversation_layout.takeAt(self.conversation_layout.count() - 1)

        # Create button container
        feedback_container = QWidget()
        feedback_layout = QHBoxLayout(feedback_container)
        feedback_layout.setContentsMargins(0, 4, 0, 8)
        feedback_layout.setSpacing(8)

        # Label
        label = QLabel("Was this helpful?")
        label.setStyleSheet(
            "font-size: 11px; "
            "color: #8E8E93; "
            "background: transparent;"
        )
        feedback_layout.addWidget(label)

        # Thumbs up button
        thumbs_up_btn = QPushButton("👍")
        thumbs_up_btn.setFixedSize(32, 32)
        thumbs_up_btn.setStyleSheet(
            "QPushButton {"
            "  background: #F0F0F0; "
            "  border: 1px solid #D0D0D0; "
            "  border-radius: 16px; "
            "  font-size: 16px; "
            "  padding: 0px;"
            "}"
            "QPushButton:hover { background: #E0E0E0; }"
            "QPushButton:pressed { background: #D0D0D0; }"
        )
        thumbs_up_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        thumbs_up_btn.clicked.connect(lambda: self._handle_feedback(qa_id, "helpful", feedback_container))
        feedback_layout.addWidget(thumbs_up_btn)

        # Thumbs down button
        thumbs_down_btn = QPushButton("👎")
        thumbs_down_btn.setFixedSize(32, 32)
        thumbs_down_btn.setStyleSheet(
            "QPushButton {"
            "  background: #F0F0F0; "
            "  border: 1px solid #D0D0D0; "
            "  border-radius: 16px; "
            "  font-size: 16px; "
            "  padding: 0px;"
            "}"
            "QPushButton:hover { background: #E0E0E0; }"
            "QPushButton:pressed { background: #D0D0D0; }"
        )
        thumbs_down_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        thumbs_down_btn.clicked.connect(lambda: self._handle_feedback(qa_id, "not_helpful", feedback_container))
        feedback_layout.addWidget(thumbs_down_btn)

        feedback_layout.addStretch()

        self.conversation_layout.addWidget(feedback_container)
        self.conversation_layout.addStretch()

    def _handle_feedback(self, qa_id: int, feedback: str, feedback_widget: QWidget):
        """Handle user feedback on an answer.
        
        Args:
            qa_id: Database ID of the Q&A entry
            feedback: 'helpful' or 'not_helpful'
            feedback_widget: Widget to replace with thank you message
        """
        # Update database
        self.qa_storage.update_feedback(qa_id, feedback)

        # Remove feedback buttons
        self.conversation_layout.removeWidget(feedback_widget)
        feedback_widget.deleteLater()

        # Add thank you message
        self.conversation_layout.takeAt(self.conversation_layout.count() - 1)

        thank_you = QLabel("✓ Thanks for your feedback!" if feedback == "helpful" else "✓ Thanks! We'll improve this answer.")
        thank_you.setStyleSheet(
            "font-size: 11px; "
            "color: #34C759; "
            "background: transparent; "
            "padding: 4px 0px;"
        )
        self.conversation_layout.addWidget(thank_you)
        self.conversation_layout.addStretch()

        logger.info(f"Feedback recorded: {feedback} for Q&A ID {qa_id}")
    def _clear_conversation(self):
        """Clear the conversation history."""
        # Remove all bubbles except stretch
        while self.conversation_layout.count() > 1:
            item = self.conversation_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add welcome message back
        self._add_spark_message(
            "Chat cleared! Ask me anything about ezControl."
        )
