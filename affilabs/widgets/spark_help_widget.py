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


def _format_spark_text(text: str) -> str:
    """Convert Spark markdown-like answer text to HTML for rich QLabel display."""
    import re as _re
    # Bold: **text** -> <b>text</b>
    text = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Inline code: `text` -> styled <code>
    text = _re.sub(
        r'`([^`]+)`',
        r'<code style="background:#E8E8ED;padding:1px 3px;border-radius:3px;font-size:12px;">\1</code>',
        text,
    )
    # Double newline -> paragraph spacing, single newline -> line break
    text = text.replace('\n\n', '<br><br>')
    text = text.replace('\n', '<br>')
    return text


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
                padding: 10px;
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

        # Styling - user bubbles right-aligned, AI bubbles left-aligned
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
                border-radius: 12px;
                margin: 0px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        # Message text — AI responses rendered as rich HTML for bold, code, etc.
        if not is_user and not is_thinking:
            self.label = QLabel(_format_spark_text(text))
            self.label.setTextFormat(Qt.TextFormat.RichText)
        else:
            self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        if is_user:
            # User bubbles: shrink to content width, still wrap if too long
            self.label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        else:
            # AI bubbles: expand to fill available width
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

            # Thumbs up button with thin-line SVG
            self.thumbs_up_btn = QPushButton()
            self.thumbs_up_btn.setFixedSize(24, 24)
            self.thumbs_up_btn.setCursor(Qt.CursorShape.PointingHandCursor)

            # Create thumbs up SVG icon
            thumbs_up_svg = """
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M7 10v12l8-1V10l-4-6c-1 0-1.5.5-1.5 1.5S8.5 8 7 10Z" stroke="currentColor" stroke-width="1" fill="none"/>
                <path d="M7 10H4a1 1 0 00-1 1v8a1 1 0 001 1h3" stroke="currentColor" stroke-width="1" fill="none"/>
            </svg>
            """
            from PySide6.QtSvg import QSvgRenderer
            from PySide6.QtGui import QPainter, QPixmap, QIcon
            svg_renderer = QSvgRenderer(thumbs_up_svg.encode())
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            svg_renderer.render(painter)
            painter.end()
            self.thumbs_up_btn.setIcon(QIcon(pixmap))

            self.thumbs_up_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 1px solid #E5E5E7;
                    border-radius: 12px;
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

            # Thumbs down button with thin-line SVG
            self.thumbs_down_btn = QPushButton()
            self.thumbs_down_btn.setFixedSize(24, 24)
            self.thumbs_down_btn.setCursor(Qt.CursorShape.PointingHandCursor)

            # Create thumbs down SVG icon
            thumbs_down_svg = """
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M17 14V2l-8 1v11l4 6c1 0 1.5-.5 1.5-1.5S15.5 16 17 14Z" stroke="currentColor" stroke-width="1" fill="none"/>
                <path d="M17 14h3a1 1 0 001-1V5a1 1 0 00-1-1h-3" stroke="currentColor" stroke-width="1" fill="none"/>
            </svg>
            """
            svg_renderer = QSvgRenderer(thumbs_down_svg.encode())
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            svg_renderer.render(painter)
            painter.end()
            self.thumbs_down_btn.setIcon(QIcon(pixmap))

            self.thumbs_down_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 1px solid #E5E5E7;
                    border-radius: 12px;
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

        # Size policies: user bubbles shrink-to-fit with max width, AI bubbles constrained too
        if is_user:
            self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
            self.setMaximumWidth(290)  # Give user bubbles more room to expand before wrapping
        else:
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            self.setMaximumWidth(310)  # Give AI bubbles more breathing room for text
        self.setMinimumHeight(40)

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
                from affilabs.utils.resource_path import get_resource_path
                from pathlib import Path

                # Use resource_path for PyInstaller compatibility
                piper_exe = get_resource_path("piper/piper.exe")
                piper_dir = piper_exe.parent
                voice_file = piper_dir / "selected_voice.txt"

                if piper_exe.exists():
                    self.piper_path = str(piper_exe)
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
        layout.setSpacing(8)

        # Chat history scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
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
        self.chat_container.setStyleSheet("background: transparent;")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_layout.setSpacing(10)
        self.chat_layout.setContentsMargins(4, 8, 4, 8)

        # Ensure content stays at top, not centered
        from PySide6.QtWidgets import QSizePolicy
        self.chat_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        scroll.setWidget(self.chat_container)
        layout.addWidget(scroll, 1)

        # Store scroll area reference for scrolling
        self.scroll_area = scroll

        # Input area - optimized for narrow sidebar
        input_container = QFrame()
        input_container.setStyleSheet("""
            QFrame {
                background: transparent;
                border-radius: 10px;
                border: none;
            }
        """)
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(8, 4, 8, 4)
        input_layout.setSpacing(8)

        self.question_input = QuestionInput()
        self.question_input.submit_requested.connect(self._handle_question)
        input_layout.addWidget(self.question_input)

        # Buttons - responsive for narrow sidebar
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        # Clear chat button - flexible sizing
        clear_btn = QPushButton("Clear")
        clear_btn.setMinimumWidth(70)
        clear_btn.setMinimumHeight(36)
        clear_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #F2F2F7;
                color: #8E8E93;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                padding: 0px;
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

        # Send button (primary action) - flexible sizing
        self.send_btn = QPushButton("Send")
        self.send_btn.setMinimumWidth(70)
        self.send_btn.setMinimumHeight(36)
        self.send_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #4A90D9;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #3A7BC8;
            }
            QPushButton:pressed {
                background-color: #2E6BAF;
            }
        """)
        self.send_btn.clicked.connect(self._handle_question)
        button_layout.addWidget(self.send_btn)

        input_layout.addLayout(button_layout)

        # TTS toggle button (if available) - below buttons
        if TTS_AVAILABLE and self.piper_path:
            tts_row = QHBoxLayout()
            tts_row.setSpacing(6)
            self.tts_button = QPushButton("\U0001f50a Voice On")
            self.tts_button.setMinimumHeight(28)
            self.tts_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.tts_button.setToolTip("Toggle Spark voice")
            self.tts_button.setStyleSheet("""
                QPushButton {
                    background: #EEEEF0;
                    border: none;
                    border-radius: 6px;
                    font-size: 12px;
                    color: #636366;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background: #E0E0E2;
                }
            """)
            self.tts_button.clicked.connect(self._toggle_tts)
            tts_row.addWidget(self.tts_button)
            input_layout.addLayout(tts_row)

        layout.addWidget(input_container)

        # Welcome message
        self._add_welcome_message()

    def _setup_knowledge_base(self):
        """Initialize answer engine (replaces embedded patterns)."""
        # SparkAnswerEngine coordinates pattern matching + AI
        try:
            from affilabs.services.spark import SparkAnswerEngine
            self.answer_engine = SparkAnswerEngine()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Spark engine init failed: {e}")
            self.answer_engine = None

    def _add_welcome_message(self):
        """Add welcome message to chat."""
        welcome = MessageBubble(
            "\U0001f44b Hi! I'm Spark, your Affilabs assistant.\n\n"
            "Ask me about setup, calibration, methods, pumps, data export, or troubleshooting.",
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
        """Process user question and generate response (never crashes)."""
        try:
            question = self.question_input.toPlainText().strip()

            if not question:
                return

            # Clear input
            self.question_input.clear()

            # Add user question bubble (right-aligned like modern chat apps)
            try:
                user_bubble = MessageBubble(question, is_user=True)
                self.chat_layout.addWidget(user_bubble, alignment=Qt.AlignmentFlag.AlignRight)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Spark user bubble failed: {e}")
                return

            # Add "thinking" indicator with animated dots
            try:
                thinking_bubble = MessageBubble("💭 Thinking...", is_user=False, is_thinking=True)
                self.chat_layout.addWidget(thinking_bubble, alignment=Qt.AlignmentFlag.AlignLeft)
                self._thinking_bubble = thinking_bubble  # Store reference
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Spark thinking bubble failed: {e}")
                return

            # Start thinking animation timer (safely)
            try:
                import time
                self._thinking_start_time = time.time()
                self._thinking_dots = 0
                if not hasattr(self, '_thinking_timer') or self._thinking_timer is None:
                    self._thinking_timer = QTimer()
                    self._thinking_timer.timeout.connect(self._update_thinking_indicator)
                self._thinking_timer.start(500)  # Update every 500ms
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Spark thinking timer failed: {e}")

            # Scroll to show thinking bubble
            try:
                QTimer.singleShot(50, self._scroll_to_bottom)
            except Exception:
                pass

            # Generate answer after short delay (to show thinking bubble)
            try:
                QTimer.singleShot(150, lambda: self._add_answer(question))
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Spark answer timer failed: {e}")

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Spark _handle_question crashed: {e}")

    def _add_answer(self, question: str):
        """Find and display answer to question."""
        try:
            answer_text = self._find_answer(question)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Spark _find_answer crashed: {e}")
            answer_text = "Sorry, something went wrong. Please try again."

        # Stop thinking timer
        try:
            if self._thinking_timer:
                self._thinking_timer.stop()
                self._thinking_timer = None
        except Exception:
            self._thinking_timer = None

        # Remove thinking bubble
        try:
            if hasattr(self, '_thinking_bubble') and self._thinking_bubble:
                self.chat_layout.removeWidget(self._thinking_bubble)
                self._thinking_bubble.deleteLater()
                self._thinking_bubble = None
        except Exception:
            self._thinking_bubble = None

        # Add actual answer
        try:
            answer_bubble = MessageBubble(answer_text, is_user=False)
            self.chat_layout.addWidget(answer_bubble, alignment=Qt.AlignmentFlag.AlignLeft)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Spark bubble creation failed: {e}")
            return

        # Speak the answer with Piper TTS
        try:
            self._speak_text(answer_text)
        except Exception:
            pass  # TTS failure should never crash the app

        self._scroll_to_bottom()

    def _find_answer(self, question: str) -> str:
        """Generate answer using SparkAnswerEngine."""
        try:
            if self.answer_engine is None:
                return "Spark engine is not available. Please restart the application."
            answer, matched = self.answer_engine.generate_answer(question)
            return answer
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Spark answer error: {e}")
            return "Sorry, I had trouble generating an answer. Please try again."

    def _toggle_tts(self):
        """Toggle TTS on/off."""
        self.tts_enabled = not self.tts_enabled
        if hasattr(self, 'tts_button'):
            if self.tts_enabled:
                self.tts_button.setText("\U0001f50a Voice On")
                self.tts_button.setToolTip("Mute Spark voice")
            else:
                self.tts_button.setText("\U0001f507 Voice Off")
                self.tts_button.setToolTip("Unmute Spark voice")

    # Maximum characters to send to Piper in one call (prevents buffer overruns)
    _TTS_MAX_CHARS = 400
    _tts_consecutive_failures = 0
    _TTS_MAX_FAILURES = 3  # Disable TTS after this many consecutive crashes

    def _speak_text(self, text: str):
        """Speak text using Piper TTS in background thread."""
        if not self.tts_enabled or not self.piper_path:
            return
        if self._tts_consecutive_failures >= self._TTS_MAX_FAILURES:
            return  # TTS crashed too many times, stay silent

        # Remove markdown formatting for cleaner speech
        clean_text = text.replace('**', '').replace('\n\n', '. ').replace('\n', '. ')
        clean_text = clean_text.replace('•', '').replace('→', '')
        clean_text = clean_text.replace('✅', '').replace('❌', '')
        clean_text = clean_text.replace('⚠️', 'Warning:')
        clean_text = clean_text.replace('💡', 'Tip:')
        # Pronounce Affilabs as two words
        clean_text = clean_text.replace('Affilabs', 'uh fee labs')
        clean_text = clean_text.replace('affilabs', 'uh fee labs')
        # Strip ALL non-ASCII and control chars — Piper only handles plain ASCII safely
        clean_text = ''.join(c for c in clean_text if 32 <= ord(c) < 127 or c == '\n')
        # Collapse multiple spaces/periods from stripping
        import re as _re
        clean_text = _re.sub(r'\.{2,}', '.', clean_text)
        clean_text = _re.sub(r' {2,}', ' ', clean_text)
        clean_text = clean_text.strip()
        # Truncate to safe length to prevent Piper buffer overrun
        if len(clean_text) > self._TTS_MAX_CHARS:
            # Cut at last sentence boundary within limit
            truncated = clean_text[:self._TTS_MAX_CHARS]
            last_period = truncated.rfind('.')
            if last_period > self._TTS_MAX_CHARS // 2:
                clean_text = truncated[:last_period + 1]
            else:
                clean_text = truncated
        # Final safety — skip if too short or empty
        if len(clean_text.strip()) < 3:
            return

        def speak():
            try:
                # Get model path (should be next to piper.exe)
                import os
                piper_dir = os.path.dirname(self.piper_path)
                model_path = os.path.join(piper_dir, f'{self.voice_model}.onnx')

                # Run piper to generate audio with timeout
                result = subprocess.run(
                    [self.piper_path, '--model', model_path, '--output-raw'],
                    input=clean_text.encode('utf-8'),
                    capture_output=True,
                    check=True,
                    timeout=30,
                )

                # Parse WAV data and play
                audio_data = np.frombuffer(result.stdout, dtype=np.int16)
                if len(audio_data) > 0:
                    sd.play(audio_data, 22050)  # Piper default sample rate
                    sd.wait()

                # Reset failure counter on success
                self._tts_consecutive_failures = 0

            except subprocess.TimeoutExpired:
                print("TTS warning: Piper timed out, skipping")
                self._tts_consecutive_failures += 1
            except subprocess.CalledProcessError as e:
                self._tts_consecutive_failures += 1
                if self._tts_consecutive_failures >= self._TTS_MAX_FAILURES:
                    print(f"TTS disabled: Piper crashed {self._TTS_MAX_FAILURES} times "
                          f"(last exit code: {e.returncode:#x})")
                else:
                    print(f"TTS warning: Piper exit code {e.returncode:#x} "
                          f"(failure {self._tts_consecutive_failures}/{self._TTS_MAX_FAILURES})")
            except Exception as e:
                print(f"TTS error: {e}")

        # Run in background thread to avoid blocking UI
        thread = threading.Thread(target=speak, daemon=True)
        thread.start()

    def _update_thinking_indicator(self):
        """Update thinking bubble with animated dots and elapsed time (safe)."""
        try:
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
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"Thinking indicator update error: {e}")
            # Don't propagate - never crash on animation update
            return

    def _scroll_to_bottom(self):
        """Scroll chat to bottom."""
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    def closeEvent(self, event):
        """Clean up resources on widget close (never crash on shutdown)."""
        try:
            # Stop thinking timer
            if hasattr(self, '_thinking_timer') and self._thinking_timer:
                self._thinking_timer.stop()
                self._thinking_timer = None
        except Exception:
            pass

        super().closeEvent(event)

    def destroyEvent(self):
        """Clean up resources on widget destruction."""
        try:
            # Stop thinking timer
            if hasattr(self, '_thinking_timer') and self._thinking_timer:
                self._thinking_timer.stop()
                self._thinking_timer = None
        except Exception:
            pass