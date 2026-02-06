"""Spark AI Help Widget - Clean Simple Q&A Assistant

A lightweight AI assistant for answering questions about Affilabs.core software.
Uses TinyLM AI with pattern matching fallback for intelligent responses.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QScrollArea, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QKeyEvent, QFont
from datetime import datetime
import threading
import subprocess
import wave
import io

# Spark answer engine for hybrid AI + pattern matching (deferred to _setup_knowledge_base)
# from affilabs.services.spark import SparkAnswerEngine

# Text-to-Speech integration - Piper TTS (lightweight ~10MB model)
try:
    import sounddevice as sd
    import numpy as np
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False


class QuestionInput(QTextEdit):
    """Text input that submits on Ctrl+Enter."""

    submit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Type your question... (Ctrl+Enter to send)")
        self.setMaximumHeight(80)
        self.setStyleSheet("""
            QTextEdit {
                background: white;
                border: 2px solid #E5E5EA;
                border-radius: 10px;
                padding: 12px;
                font-size: 14px;
                font-family: -apple-system, 'Segoe UI', sans-serif;
            }
            QTextEdit:focus {
                border: 2px solid #007AFF;
            }
        """)

    def keyPressEvent(self, event: QKeyEvent):
        """Handle Ctrl+Enter to submit."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.submit_requested.emit()
                event.accept()
                return
        super().keyPressEvent(event)


class MessageBubble(QFrame):
    """Chat bubble for questions and answers."""

    feedback_given = Signal(str)  # 'helpful' or 'not_helpful'

    def __init__(self, text: str, is_user: bool = True, is_thinking: bool = False, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self.is_thinking = is_thinking

        # Styling - both aligned left with different colors
        if is_user:
            bg_color = "#E3F2FD"
            text_color = "#1565C0"
        elif is_thinking:
            bg_color = "#FFF9C4"
            text_color = "#F57F17"
        else:
            bg_color = "#F5F5F5"
            text_color = "#212121"

        self.setStyleSheet(f"""
            QFrame {{
                background: {bg_color};
                border-radius: 16px;
                margin: 0px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        # Message text with more height for longer answers
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        label_style = f"""
            color: {text_color};
            font-size: 14px;
            font-family: -apple-system, 'Segoe UI', sans-serif;
            background: transparent;
            line-height: 1.5;
        """

        # Add italic style for thinking
        if is_thinking:
            label_style += "font-style: italic;"

        self.label.setStyleSheet(label_style)
        self.label.setMinimumHeight(40)  # Increased from 20 to allow longer answers
        layout.addWidget(self.label)

        # Bottom row: timestamp and feedback (for AI responses only)
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(12)

        # Timestamp (not shown for thinking bubble)
        if not is_thinking:
            timestamp = datetime.now().strftime("%H:%M")
            time_label = QLabel(timestamp)
            time_label.setStyleSheet(f"""
                color: {text_color};
                font-size: 10px;
                opacity: 0.5;
                background: transparent;
            """)
            bottom_layout.addWidget(time_label)

        # Feedback buttons (only for AI responses)
        if not is_user and not is_thinking:
            bottom_layout.addStretch()

            # Thumbs up button
            self.thumbs_up_btn = QPushButton("👍")
            self.thumbs_up_btn.setFixedSize(28, 28)
            self.thumbs_up_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.thumbs_up_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 1px solid #E0E0E0;
                    border-radius: 14px;
                    font-size: 14px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background: #E8F5E9;
                    border: 1px solid #4CAF50;
                }
                QPushButton:pressed {
                    background: #C8E6C9;
                }
            """)
            self.thumbs_up_btn.clicked.connect(lambda: self._on_feedback("helpful"))
            bottom_layout.addWidget(self.thumbs_up_btn)

            # Thumbs down button
            self.thumbs_down_btn = QPushButton("👎")
            self.thumbs_down_btn.setFixedSize(28, 28)
            self.thumbs_down_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.thumbs_down_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 1px solid #E0E0E0;
                    border-radius: 14px;
                    font-size: 14px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background: #FFEBEE;
                    border: 1px solid #F44336;
                }
                QPushButton:pressed {
                    background: #FFCDD2;
                }
            """)
            self.thumbs_down_btn.clicked.connect(lambda: self._on_feedback("not_helpful"))
            bottom_layout.addWidget(self.thumbs_down_btn)

        layout.addLayout(bottom_layout)

        # Set size policies to allow proper expansion
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        # No fixed width - allow bubbles to expand based on content and container
        self.setMinimumHeight(50)

    def update_text(self, text: str):
        """Update the bubble text (for replacing thinking bubble with answer)."""
        self.label.setText(text)

    def _on_feedback(self, feedback: str):
        """Handle feedback button click."""
        # Disable both buttons after feedback
        if hasattr(self, 'thumbs_up_btn'):
            self.thumbs_up_btn.setEnabled(False)
            self.thumbs_down_btn.setEnabled(False)

        # Emit signal
        self.feedback_given.emit(feedback)


class SparkHelpWidget(QWidget):
    """Main Spark AI assistant widget."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Thinking indicator state
        self._thinking_timer = None
        self._thinking_start_time = None
        self._thinking_dots = 0

        # TTS setup (Piper TTS - lightweight model)
        self.tts_enabled = True  # Start with TTS on
        self.piper_path = None
        self.voice_model = None
        if TTS_AVAILABLE:
            try:
                # Piper will be installed as a standalone executable
                import os
                from pathlib import Path
                # Check if piper is in the same directory
                piper_exe = os.path.join(os.path.dirname(__file__), '..', '..', 'piper', 'piper.exe')
                piper_dir = Path(piper_exe).parent
                voice_file = piper_dir / "selected_voice.txt"

                if os.path.exists(piper_exe):
                    self.piper_path = piper_exe
                    # Load selected voice (or use default)
                    if voice_file.exists():
                        self.voice_model = voice_file.read_text().strip()
                    else:
                        self.voice_model = "en_US-lessac-medium"
                    print(f"Piper TTS found! Voice: {self.voice_model}")
                else:
                    print("Piper TTS not found - voice disabled")
                    self.piper_path = None
            except Exception as e:
                print(f"TTS initialization failed: {e}")
                self.piper_path = None

        self._setup_ui()
        self._setup_knowledge_base()

    def _setup_ui(self):
        """Create the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Header with TTS toggle
        header_container = QFrame()
        header_container.setStyleSheet("""
            QFrame {
                background: white;
                border-bottom: 1px solid #E5E5EA;
            }
        """)
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(16, 16, 16, 16)
        header_layout.setSpacing(12)

        header = QLabel("⚡ Spark AI Assistant")
        header.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: 700;
                color: #1D1D1F;
                background: transparent;
                border: none;
            }
        """)
        header_layout.addWidget(header)
        header_layout.addStretch()

        # TTS toggle button (speaker icon)
        if TTS_AVAILABLE and self.piper_path:
            self.tts_button = QPushButton("🔊")
            self.tts_button.setFixedSize(32, 32)
            self.tts_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.tts_button.setToolTip("Mute Spark voice")
            self.tts_button.setStyleSheet("""
                QPushButton {
                    background: #F5F5F5;
                    border: none;
                    border-radius: 16px;
                    font-size: 16px;
                }
                QPushButton:hover {
                    background: #E5E5EA;
                }
            """)
            self.tts_button.clicked.connect(self._toggle_tts)
            header_layout.addWidget(self.tts_button)

        layout.addWidget(header_container)

        # Chat history scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                background: white;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #D1D1D6;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #A1A1A6;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_layout.setSpacing(12)
        self.chat_layout.setContentsMargins(8, 8, 8, 8)

        # Ensure content stays at top, not centered
        from PySide6.QtWidgets import QSizePolicy
        self.chat_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        scroll.setWidget(self.chat_container)
        layout.addWidget(scroll, 1)

        # Store scroll area reference for scrolling
        self.scroll_area = scroll

        # Input area
        input_container = QFrame()
        input_container.setStyleSheet("""
            QFrame {
                background: #FAFAFA;
                border-radius: 12px;
                border: 1px solid #E5E5EA;
            }
        """)
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(12, 12, 12, 12)
        input_layout.setSpacing(10)

        self.question_input = QuestionInput()
        self.question_input.submit_requested.connect(self._handle_question)
        input_layout.addWidget(self.question_input)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        # Clear chat button
        clear_btn = QPushButton("Clear Chat")
        clear_btn.setFixedSize(100, 36)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #F2F2F7;
                color: #8E8E93;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #E5E5EA;
                color: #636366;
            }
            QPushButton:pressed {
                background: #D1D1D6;
            }
        """)
        clear_btn.clicked.connect(self._clear_chat)
        button_layout.addWidget(clear_btn)

        button_layout.addStretch()

        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedSize(100, 36)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: #007AFF;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #0051D5;
            }
            QPushButton:pressed {
                background: #004DB8;
            }
        """)
        self.send_btn.clicked.connect(self._handle_question)
        button_layout.addWidget(self.send_btn)

        input_layout.addLayout(button_layout)
        layout.addWidget(input_container)

        # Welcome message
        self._add_welcome_message()

    def _setup_knowledge_base(self):
        """Initialize answer engine (replaces embedded patterns)."""
        # SparkAnswerEngine coordinates pattern matching + AI
        from affilabs.services.spark import SparkAnswerEngine
        self.answer_engine = SparkAnswerEngine()

    def _add_welcome_message(self):
        """Add welcome message to chat."""
        welcome = MessageBubble(
            "👋 Hi! I'm Spark, your Affilabs.core assistant. Ask me anything about:\n\n"
            "• Power on and startup procedures\n"
            "• Starting and stopping acquisitions\n"
            "• Recording and exporting data\n"
            "• Detector troubleshooting\n"
            "• Pump and flow control\n"
            "• Creating cycles and methods\n"
            "• Baseline corrections\n\n"
            "What would you like to know?",
            is_user=False
        )
        self.chat_layout.addWidget(welcome, alignment=Qt.AlignmentFlag.AlignLeft)

    def _clear_chat(self):
        """Clear all messages and reset to welcome."""
        # Remove all widgets except welcome
        while self.chat_layout.count() > 0:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add fresh welcome message
        self._add_welcome_message()

    def _handle_question(self):
        """Process user question and generate response."""
        question = self.question_input.toPlainText().strip()

        if not question:
            return

        # Clear input
        self.question_input.clear()

        # Add user question bubble
        user_bubble = MessageBubble(question, is_user=True)
        self.chat_layout.addWidget(user_bubble, alignment=Qt.AlignmentFlag.AlignLeft)

        # Add "thinking" indicator with animated dots
        thinking_bubble = MessageBubble("💭 Thinking...", is_user=False, is_thinking=True)
        self.chat_layout.addWidget(thinking_bubble, alignment=Qt.AlignmentFlag.AlignLeft)
        self._thinking_bubble = thinking_bubble  # Store reference

        # Start thinking animation timer
        import time
        self._thinking_start_time = time.time()
        self._thinking_dots = 0
        self._thinking_timer = QTimer()
        self._thinking_timer.timeout.connect(self._update_thinking_indicator)
        self._thinking_timer.start(500)  # Update every 500ms

        # Scroll to show thinking bubble
        QTimer.singleShot(50, self._scroll_to_bottom)

        # Generate answer after short delay (to show thinking bubble)
        QTimer.singleShot(150, lambda: self._add_answer(question))

    def _add_answer(self, question: str):
        """Find and display answer to question."""
        answer_text = self._find_answer(question)

        # Stop thinking timer
        if self._thinking_timer:
            self._thinking_timer.stop()
            self._thinking_timer = None

        # Remove thinking bubble
        if hasattr(self, '_thinking_bubble') and self._thinking_bubble:
            self.chat_layout.removeWidget(self._thinking_bubble)
            self._thinking_bubble.deleteLater()
            self._thinking_bubble = None

        # Add actual answer
        answer_bubble = MessageBubble(answer_text, is_user=False)
        self.chat_layout.addWidget(answer_bubble, alignment=Qt.AlignmentFlag.AlignLeft)

        # Speak the answer with Zira
        self._speak_text(answer_text)

        self._scroll_to_bottom()

    def _find_answer(self, question: str) -> str:
        """Generate answer using SparkAnswerEngine."""
        # SparkAnswerEngine handles pattern matching + AI fallback
        answer, matched = self.answer_engine.generate_answer(question)
        return answer

    def _toggle_tts(self):
        """Toggle TTS on/off."""
        self.tts_enabled = not self.tts_enabled
        if hasattr(self, 'tts_button'):
            if self.tts_enabled:
                self.tts_button.setText("🔊")
                self.tts_button.setToolTip("Mute Spark voice")
            else:
                self.tts_button.setText("🔇")
                self.tts_button.setToolTip("Unmute Spark voice")

    def _speak_text(self, text: str):
        """Speak text using Piper TTS in background thread."""
        if not self.tts_enabled or not self.piper_path:
            return

        # Remove markdown formatting for cleaner speech
        clean_text = text.replace('**', '').replace('\n\n', '. ').replace('\n', '. ')
        clean_text = clean_text.replace('•', '').replace('→', '')
        clean_text = clean_text.replace('✅', '').replace('❌', '')
        clean_text = clean_text.replace('⚠️', 'Warning:')
        clean_text = clean_text.replace('💡', 'Tip:')
        # Pronounce Affilabs as two words
        clean_text = clean_text.replace('Affilabs', 'uh fee labs')
        clean_text = clean_text.replace('affilabs', 'uh fee labs')

        def speak():
            try:
                # Get model path (should be next to piper.exe)
                import os
                piper_dir = os.path.dirname(self.piper_path)
                model_path = os.path.join(piper_dir, f'{self.voice_model}.onnx')

                # Run piper to generate audio
                result = subprocess.run(
                    [self.piper_path, '--model', model_path, '--output-raw'],
                    input=clean_text.encode('utf-8'),
                    capture_output=True,
                    check=True
                )

                # Parse WAV data and play
                audio_data = np.frombuffer(result.stdout, dtype=np.int16)
                sd.play(audio_data, 22050)  # Piper default sample rate
                sd.wait()

            except Exception as e:
                print(f"TTS error: {e}")

        # Run in background thread to avoid blocking UI
        thread = threading.Thread(target=speak, daemon=True)
        thread.start()

    def _update_thinking_indicator(self):
        """Update thinking bubble with animated dots and elapsed time."""
        if not hasattr(self, '_thinking_bubble') or not self._thinking_bubble:
            if self._thinking_timer:
                self._thinking_timer.stop()
            return

        # Calculate elapsed time
        import time
        elapsed = int(time.time() - self._thinking_start_time)

        # Cycle through dot animations: . .. ...
        self._thinking_dots = (self._thinking_dots + 1) % 4
        dots = '.' * (self._thinking_dots if self._thinking_dots > 0 else 3)

        # Update bubble text with animation and timer
        thinking_text = f"💭 Thinking{dots} ({elapsed}s)"
        self._thinking_bubble.update_text(thinking_text)

    def _scroll_to_bottom(self):
        """Scroll chat to bottom."""
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
