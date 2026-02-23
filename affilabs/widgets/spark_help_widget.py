"""Spark AI Help Widget - Clean Simple Q&A Assistant

A lightweight AI assistant for answering questions about Affilabs.core software.
Uses TinyLM AI with pattern matching fallback for intelligent responses.
"""

import logging
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

logger = logging.getLogger(__name__)

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
    """Text input that submits on Ctrl+Enter. Supports drag-and-drop images."""

    submit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Type your question... (Ctrl+Enter to send)")
        self.setMaximumHeight(80)
        self.setAcceptDrops(True)
        self.attached_images = []  # List of image file paths
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

    def dragEnterEvent(self, event):
        """Accept drag events with image files."""
        if event.mimeData().hasUrls():
            # Check if any URLs are image files
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                if path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event):
        """Accept drag move events."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle dropped image files."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                if path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    self.attached_images.append(path)
                    # Show feedback in the text input
                    current_text = self.toPlainText()
                    import os
                    filename = os.path.basename(path)
                    if current_text and not current_text.endswith('\n'):
                        current_text += '\n'
                    self.setPlainText(current_text + f"📎 Attached: {filename}")
            event.acceptProposedAction()
        else:
            event.ignore()

    def clear(self):
        """Clear text and attached images."""
        super().clear()
        self.attached_images = []


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


class InteractiveMessageBubble(QFrame):
    """Chat bubble with clickable option buttons for guided troubleshooting."""

    option_selected = Signal(str)  # Emits the selected option label

    def __init__(self, text: str, options: list[str], parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background: #FFF3E0;
                border-radius: 12px;
                margin: 0px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        # Message text (rich HTML)
        label = QLabel(_format_spark_text(text))
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        label.setStyleSheet("""
            color: #212121;
            font-size: 14px;
            font-family: -apple-system, 'Segoe UI', sans-serif;
            background: transparent;
            line-height: 1.5;
        """)
        label.setMinimumHeight(40)
        layout.addWidget(label)

        # Option buttons row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        self._option_buttons: list[QPushButton] = []

        for option_text in options:
            btn = QPushButton(option_text)
            btn.setMinimumHeight(34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: white;
                    color: #007AFF;
                    border: 2px solid #007AFF;
                    border-radius: 17px;
                    font-size: 13px;
                    font-weight: 600;
                    padding: 6px 16px;
                    font-family: -apple-system, 'Segoe UI', sans-serif;
                }
                QPushButton:hover {
                    background: #007AFF;
                    color: white;
                }
                QPushButton:pressed {
                    background: #005ECB;
                    color: white;
                }
            """)
            btn.clicked.connect(lambda _checked=False, opt=option_text: self._on_option_clicked(opt))
            self._option_buttons.append(btn)
            btn_layout.addWidget(btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Timestamp
        timestamp = datetime.now().strftime("%H:%M")
        time_label = QLabel(timestamp)
        time_label.setStyleSheet("""
            color: #9E9E9E;
            font-size: 10px;
            background: transparent;
        """)
        layout.addWidget(time_label)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.setMaximumWidth(310)
        self.setMinimumHeight(40)

    def _on_option_clicked(self, option: str):
        """Handle option button click — disable all buttons and emit signal."""
        for btn in self._option_buttons:
            btn.setEnabled(False)
            btn.setStyleSheet("""
                QPushButton {
                    background: #F0F0F0;
                    color: #999;
                    border: 2px solid #DDD;
                    border-radius: 17px;
                    font-size: 13px;
                    font-weight: 600;
                    padding: 6px 16px;
                    font-family: -apple-system, 'Segoe UI', sans-serif;
                }
            """)
        self.option_selected.emit(option)


class SparkHelpWidget(QWidget):
    """Main Spark AI assistant widget. All methods guarded — Spark never crashes the UI."""

    # Thread-safe signals — emitted from background threads, connected to UI-thread slots
    _engine_ready_signal = Signal(object)   # carries the SparkAnswerEngine instance
    _answer_ready_signal = Signal(str, str, int)  # answer_text, question, token

    def __init__(self, parent=None, user_manager=None):
        super().__init__(parent)

        # Wire thread-safe signals → UI-thread slots
        self._engine_ready_signal.connect(self._on_engine_ready)
        self._answer_ready_signal.connect(self._on_answer_ready)

        # User context for personalization
        self._user_manager = user_manager

        # Thinking indicator state
        self._thinking_timer = None
        self._thinking_start_time = None
        self._thinking_dots = 0
        self._thinking_bubble = None
        self._query_token = 0          # incremented per query; stale threads compare before writing
        self._timeout_timer = None     # kills thinking bubble if answer never arrives
        self.answer_engine = None
        self._engine_ready = False     # set True once background init completes
        self._awaiting_bug_description = False

        # TTS setup (Piper TTS - lightweight model)
        self.tts_enabled = False  # Start with TTS off by default
        self.piper_path = None
        self.voice_model = None
        try:
            if TTS_AVAILABLE:
                try:
                    from affilabs.utils.resource_path import get_resource_path
                    piper_exe = get_resource_path("piper/piper.exe")
                    piper_dir = piper_exe.parent
                    voice_file = piper_dir / "selected_voice.txt"

                    if piper_exe.exists():
                        self.piper_path = str(piper_exe)
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
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"TTS outer init failed: {e}")

        try:
            self._setup_ui()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Spark UI setup failed (non-fatal): {e}")

        try:
            self._setup_knowledge_base()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Spark knowledge base failed (non-fatal): {e}")

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
        button_layout.setSpacing(6)

        # Report Bug button - small icon-only, left of Clear
        bug_btn = QPushButton("🐛")
        bug_btn.setFixedSize(36, 36)
        bug_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        bug_btn.setToolTip("Report a Bug (screenshot + logs included automatically)")
        bug_btn.setStyleSheet("""
            QPushButton {
                background: #FFF3CD;
                color: #7D5A00;
                border: 1px solid #F0C040;
                border-radius: 6px;
                font-size: 16px;
                font-weight: 600;
                padding: 0px;
            }
            QPushButton:hover {
                background: #FFE699;
                border-color: #D4A000;
            }
            QPushButton:pressed {
                background: #F5D800;
            }
        """)
        bug_btn.clicked.connect(self._on_report_bug_clicked)
        button_layout.addWidget(bug_btn)

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
        """Initialize answer engine in a background thread so it doesn't block the UI."""
        def _init_engine():
            try:
                from affilabs.services.spark import SparkAnswerEngine
                engine = SparkAnswerEngine()
                # Emit signal — automatically queued to UI thread (Qt Signal is thread-safe)
                self._engine_ready_signal.emit(engine)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Spark engine init failed: {e}")

        threading.Thread(target=_init_engine, daemon=True).start()

    def _on_engine_ready(self, engine):
        """Called on UI thread when engine background init completes."""
        self.answer_engine = engine
        self._engine_ready = True

    def _add_welcome_message(self):
        """Add welcome message to chat."""
        # Personalize with user name if available
        user_name = ""
        if self._user_manager:
            try:
                active_user = self._user_manager.get_active_user()
                if active_user:
                    user_name = active_user.strip()
            except Exception:
                pass
        
        if user_name:
            greeting = f"\U0001f44b Hi {user_name}! I'm Spark, your Affilabs assistant."
        else:
            greeting = "\U0001f44b Hi! I'm Spark, your Affilabs assistant."
        
        welcome_text = (
            f"{greeting} "
            "I'm especially expert at **method building** — ask me about cycle syntax, shortcuts, examples, presets, and more!\n\n"
            "I can also help with setup, calibration, pumps, data export, and troubleshooting."
        )
        
        welcome = MessageBubble(welcome_text, is_user=False)
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

    def _set_input_enabled(self, enabled: bool):
        """Enable/disable question input and send button."""
        try:
            self.question_input.setEnabled(enabled)
            self.send_btn.setEnabled(enabled)
        except Exception:
            pass

    def _handle_question_inner(self):
        """Process user question and generate response (never crashes)."""
        try:
            question = self.question_input.toPlainText().strip()
            if not question:
                return

            # Disable input to prevent double-submit while in flight
            self._set_input_enabled(False)
            self.question_input.clear()

            # Bump query token — stale threads will see a mismatch and no-op
            self._query_token += 1
            my_token = self._query_token

            # Add user question bubble
            try:
                user_bubble = MessageBubble(question, is_user=True)
                self.chat_layout.addWidget(user_bubble, alignment=Qt.AlignmentFlag.AlignRight)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Spark user bubble failed: {e}")
                self._set_input_enabled(True)
                return

            # Add thinking bubble
            try:
                thinking_bubble = MessageBubble("💭 Thinking...", is_user=False, is_thinking=True)
                self.chat_layout.addWidget(thinking_bubble, alignment=Qt.AlignmentFlag.AlignLeft)
                self._thinking_bubble = thinking_bubble
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Spark thinking bubble failed: {e}")
                self._set_input_enabled(True)
                return

            # Start animation timer (create fresh each query)
            try:
                import time
                self._thinking_start_time = time.time()
                self._thinking_dots = 0
                if self._thinking_timer is not None:
                    self._thinking_timer.stop()
                    self._thinking_timer = None
                self._thinking_timer = QTimer()
                self._thinking_timer.timeout.connect(self._update_thinking_indicator)
                self._thinking_timer.start(500)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Spark thinking timer failed: {e}")

            # Safety timeout — clears thinking state after 15s regardless
            try:
                if self._timeout_timer is not None:
                    self._timeout_timer.stop()
                self._timeout_timer = QTimer()
                self._timeout_timer.setSingleShot(True)
                self._timeout_timer.timeout.connect(
                    lambda: self._display_answer(
                        "Sorry, I took too long to respond. Please try again.", question, my_token
                    )
                )
                self._timeout_timer.start(15000)
            except Exception:
                pass

            QTimer.singleShot(50, self._scroll_to_bottom)

            # Run answer generation in background
            try:
                self._answer_worker = threading.Thread(
                    target=self._generate_answer_async, args=(question, my_token), daemon=True
                )
                self._answer_worker.start()
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Spark answer thread failed: {e}")
                self._display_answer("Sorry, something went wrong. Please try again.", question, my_token)

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Spark _handle_question_inner crashed: {e}")
            self._set_input_enabled(True)

    def _generate_answer_async(self, question: str, token: int):
        """Run answer generation in background thread, post result to UI thread."""
        try:
            answer_text, matched = self._find_answer(question)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Spark _find_answer crashed: {e}")
            answer_text, matched = "Sorry, something went wrong. Please try again.", False

        # Auto-log misses so we know what questions need new patterns
        if not matched:
            self._log_miss(question)

        # Emit signal — thread-safe, queued to UI thread automatically
        self._answer_ready_signal.emit(answer_text, question, token)

    def _on_answer_ready(self, answer_text: str, question: str, token: int):
        """Slot called on UI thread when background answer generation completes."""
        self._display_answer(answer_text, question, token)

    def _display_answer(self, answer_text: str, question: str = "", token: int = -1):
        """Display answer on UI thread. token guards against stale threads."""
        # Ignore if a newer query already took over
        if token != -1 and token != self._query_token:
            return

        # Cancel the safety timeout
        try:
            if self._timeout_timer is not None:
                self._timeout_timer.stop()
                self._timeout_timer = None
        except Exception:
            pass

        # Stop thinking timer
        try:
            if self._thinking_timer:
                self._thinking_timer.stop()
                self._thinking_timer = None
        except Exception:
            self._thinking_timer = None

        # Remove thinking bubble
        try:
            if self._thinking_bubble:
                self.chat_layout.removeWidget(self._thinking_bubble)
                self._thinking_bubble.deleteLater()
                self._thinking_bubble = None
        except Exception:
            self._thinking_bubble = None

        # Re-enable input
        self._set_input_enabled(True)

        # Add actual answer
        try:
            answer_bubble = MessageBubble(answer_text, is_user=False)
            self.chat_layout.addWidget(answer_bubble, alignment=Qt.AlignmentFlag.AlignLeft)
            # Wire feedback button → write feedback log entry
            if question:
                answer_bubble.feedback_given.connect(
                    lambda rating, q=question, a=answer_text: self._write_feedback(q, a, rating)
                )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Spark bubble creation failed: {e}")
            return

        # Save Q&A to per-user history
        if question:
            try:
                self._save_qa_entry(question, answer_text)
            except Exception:
                pass

        # Speak the answer with Piper TTS
        try:
            self._speak_text(answer_text)
        except Exception:
            pass

        self._scroll_to_bottom()



    def _find_answer(self, question: str) -> tuple:
        """Generate answer using SparkAnswerEngine. Returns (answer, matched)."""
        try:
            if self.answer_engine is None:
                # Engine still loading — brief wait (should be ready within 1-2s)
                import time
                deadline = time.time() + 3.0
                while self.answer_engine is None and time.time() < deadline:
                    time.sleep(0.05)
            if self.answer_engine is None:
                return ("Still starting up — please try again in a moment.", False)
            answer, matched = self.answer_engine.generate_answer(question)
            return (answer, matched)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Sparq answer error: {e}")
            return ("Sorry, I had trouble generating an answer. Please try again.", False)

    def _save_qa_entry(self, question: str, answer: str):
        """Save Q&A entry to per-user JSON history file (non-fatal)."""
        import json
        from pathlib import Path
        from datetime import datetime
        
        try:
            # Determine history file name (per-user or default)
            if self._user_manager:
                try:
                    active_user = self._user_manager.get_active_user()
                    if active_user:
                        user_safe = active_user.replace(" ", "_").lower()
                        filename = f"spark_qa_history_{user_safe}.json"
                    else:
                        filename = "spark_qa_history_default.json"
                except Exception:
                    filename = "spark_qa_history_default.json"
            else:
                filename = "spark_qa_history_default.json"
            
            # Use affilabs/data/ directory for history
            from affilabs.utils.resource_path import get_resource_path
            history_dir = get_resource_path("data/spark")
            history_file = Path(history_dir) / filename
            
            # Load existing history
            history = []
            if history_file.exists():
                try:
                    history = json.loads(history_file.read_text())
                except (json.JSONDecodeError, IOError):
                    history = []
            
            # Append new entry
            history.append({
                "timestamp": datetime.now().isoformat(),
                "question": question.strip(),
                "answer": answer.strip()
            })
            
            # Keep only last 50 entries to prevent bloat
            if len(history) > 50:
                history = history[-50:]
            
            # Save
            history_file.write_text(json.dumps(history, indent=2))
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"Failed to save Q&A history: {e}")
            # Silent fail - never crash on history save

    def _write_feedback(self, question: str, answer: str, rating: str):
        """Append a thumbs up/down feedback entry to spark_feedback.json."""
        import json
        from pathlib import Path
        from datetime import datetime
        try:
            from affilabs.utils.resource_path import get_resource_path
            feedback_file = Path(get_resource_path("data/spark")) / "spark_feedback.json"
            entries = []
            if feedback_file.exists():
                try:
                    entries = json.loads(feedback_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, IOError):
                    entries = []
            entries.append({
                "timestamp": datetime.now().isoformat(),
                "question": question.strip(),
                "answer": answer.strip(),
                "rating": rating  # "helpful" or "not_helpful"
            })
            feedback_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass  # never crash on feedback write

    def _log_miss(self, question: str):
        """Append an unmatched question to spark_misses.json for pattern development."""
        import json
        from pathlib import Path
        from datetime import datetime
        try:
            from affilabs.utils.resource_path import get_resource_path
            miss_file = Path(get_resource_path("data/spark")) / "spark_misses.json"
            entries = []
            if miss_file.exists():
                try:
                    entries = json.loads(miss_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, IOError):
                    entries = []
            entries.append({
                "timestamp": datetime.now().isoformat(),
                "question": question.strip()
            })
            miss_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass  # never crash on miss log write

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
            if self._thinking_timer:
                self._thinking_timer.stop()
                self._thinking_timer = None
        except Exception:
            pass
        try:
            if self._timeout_timer:
                self._timeout_timer.stop()
                self._timeout_timer = None
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

    # ── SPARK Troubleshooting Flow ───────────────────────────────────────

    # ── Bug Report Flow ───────────────────────────────────────────────────────

    def start_bug_report_flow(self):
        """Start a conversational bug report flow in the Spark chat."""
        try:
            self.push_system_message(
                "**Report a Bug**\n\n"
                "Describe what went wrong in as much detail as you can. "
                "You can drag and drop images into the text box. "
                "I'll also attach a screenshot and the recent log automatically.\n\n"
                "What happened?"
            )
            self._awaiting_bug_description = True
            # Re-use the normal input — next submit goes to bug flow
            self.question_input.setPlaceholderText("Describe the bug… (Ctrl+Enter to send)")
            self.question_input.setFocus()
        except Exception as e:
            logger.error(f"Bug report flow start failed: {e}")

    def _on_report_bug_clicked(self):
        """Handle Report Bug button click."""
        self.start_bug_report_flow()

    def _handle_question(self):
        """Process user question — routes to bug report flow if active."""
        # Bug report intercept
        if getattr(self, '_awaiting_bug_description', False):
            self._awaiting_bug_description = False
            description = self.question_input.toPlainText().strip()
            # Capture attached images before clearing
            attached_images = getattr(self.question_input, 'attached_images', []).copy()
            self.question_input.clear()
            self.question_input.setPlaceholderText("Type your question… (Ctrl+Enter to send)")
            if description:
                user_bubble = MessageBubble(description, is_user=True)
                self.chat_layout.addWidget(user_bubble, alignment=Qt.AlignmentFlag.AlignRight)
                self._submit_bug_report(description, attached_images)
            return
        self._handle_question_inner()

    def _submit_bug_report(self, description: str, attached_images: list = None):
        """Generate bug report draft and display for user to copy."""
        self.push_system_message("Generating bug report…")

        def _generate():
            try:
                from affilabs.services.bug_reporter import send_bug_report
                user_name = ""
                if self._user_manager:
                    try:
                        user_name = self._user_manager.get_active_user() or ""
                    except Exception:
                        pass
                ok, draft_text = send_bug_report(
                    description, 
                    user_name=user_name, 
                    additional_images=attached_images or []
                )
            except Exception as e:
                ok, draft_text = False, f"Failed to generate: {e}"
            
            def show_draft():
                if ok:
                    self.push_system_message("✅ Bug report draft ready! Copy the text below and email it to info@affiniteinstruments.com")
                    # Push the draft in a code block so it's easy to select/copy
                    bubble = MessageBubble(f"```\n{draft_text}\n```", is_user=False)
                    self.chat_layout.addWidget(bubble, alignment=Qt.AlignmentFlag.AlignLeft)
                    QTimer.singleShot(50, self._scroll_to_bottom)
                else:
                    self.push_system_message(f"❌ {draft_text}")
            
            QTimer.singleShot(0, show_draft)

        threading.Thread(target=_generate, daemon=True).start()

    def push_system_message(self, text: str):
        """Push a system-initiated message into the SPARK chat (not user-initiated).

        Used by the troubleshooting flow to display diagnostic information
        and guidance steps in the chat.
        """
        bubble = MessageBubble(text, is_user=False)
        self.chat_layout.addWidget(bubble, alignment=Qt.AlignmentFlag.AlignLeft)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def push_interactive_message(self, text: str, options: list[str]) -> InteractiveMessageBubble:
        """Push a message with clickable option buttons into the chat.

        Args:
            text: Message text (supports markdown-like formatting).
            options: List of button labels for user to choose from.

        Returns:
            The InteractiveMessageBubble instance (caller connects to option_selected).
        """
        bubble = InteractiveMessageBubble(text, options)
        self.chat_layout.addWidget(bubble, alignment=Qt.AlignmentFlag.AlignLeft)
        QTimer.singleShot(50, self._scroll_to_bottom)
        return bubble

    def start_troubleshooting_flow(self, diagnosis: dict, controller):
        """Start the guided LED troubleshooting flow. Never crashes the UI.

        Args:
            diagnosis: Output of ``diagnose_weak_channel()`` containing:
                channel, current_signal, current_led, historical_avg, pct_of_historical
            controller: PicoP4SPR controller instance for LED commands.
        """
        try:
            self._ts_controller = controller
            self._ts_diagnosis = diagnosis
            self._ts_state = "START"
            self._advance_troubleshooting()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Spark troubleshooting flow failed (non-fatal): {e}")

    def _advance_troubleshooting(self):
        """State machine for the LED troubleshooting flow. Never crashes."""
        try:
            self.__advance_troubleshooting_inner()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Spark troubleshooting step failed (non-fatal): {e}")

    def __advance_troubleshooting_inner(self):
        """Inner troubleshooting state machine (may raise)."""
        state = self._ts_state
        diag = self._ts_diagnosis
        ctrl = self._ts_controller
        ch = diag["channel"].upper()

        if state == "START":
            track = diag.get('history_track', 'known_good')
            n_success = diag.get('history_successes', 0)

            if track == 'known_good':
                self.push_system_message(
                    f"**Calibration failed — Channel {ch} signal is critically low.**\n\n"
                    f"Channel {ch} at maximum LED brightness is producing only "
                    f"**{diag['current_signal']:,.0f} counts** ({diag['pct_of_historical']:.0f}% of normal). "
                    f"Historically, Channel {ch} produces ~**{diag['historical_avg']:,.0f} counts**.\n\n"
                    f"This device has **{n_success} prior successful calibration{'s' if n_success != 1 else ''} on record** — "
                    f"most likely cause is **water or debris in the optical path**.\n\n"
                    f"I'm turning on LED {ch} at full brightness."
                )
                # Turn on the problematic LED at max brightness
                try:
                    led_args = {c: 0 for c in ("a", "b", "c", "d")}
                    led_args[diag["channel"]] = 255
                    ctrl.set_batch_intensities(**led_args)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Troubleshooting LED control failed: {e}")
                self._ts_state = "CHECK_WATER"
                QTimer.singleShot(1500, self._advance_troubleshooting)

            elif track == 'never_calibrated':
                self.push_system_message(
                    f"**Calibration failed — Channel {ch} signal is critically low.**\n\n"
                    f"This device has **no successful calibration history on record**. "
                    f"This typically points to a setup or hardware issue rather than water in the optical path.\n\n"
                    f"Let's check the basics first."
                )
                self._ts_state = "CHECK_HARDWARE"
                QTimer.singleShot(800, self._advance_troubleshooting)

            else:  # consistently_failing
                self.push_system_message(
                    f"**Calibration failed — Channel {ch} signal is critically low.**\n\n"
                    f"This device has attempted calibration before but has **never succeeded**. "
                    f"This is unlikely to be water — it points to a persistent hardware fault.\n\n"
                    f"I recommend contacting technical support. "
                    f"I can generate a bug report with the full diagnostic details."
                )
                self._ts_state = "CONTACT_SUPPORT"
                QTimer.singleShot(800, self._advance_troubleshooting)

        elif state == "CHECK_WATER":
            bubble = self.push_interactive_message(
                f"Place a piece of paper in the **Channel {ch}** light path.\n\n"
                f"**Is the paper wet?**",
                ["Yes, it's wet", "No, it's dry"],
            )
            bubble.option_selected.connect(self._on_water_check_answer)

        elif state == "CHECK_LED_BRIGHTNESS":
            # Turn on LED A alongside the problematic LED for comparison
            self.push_system_message(
                f"Now I'm turning on **LED A** at full brightness alongside **LED {ch}** "
                f"so you can compare them."
            )
            try:
                led_args = {c: 0 for c in ("a", "b", "c", "d")}
                led_args["a"] = 255
                led_args[diag["channel"]] = 255
                ctrl.set_batch_intensities(**led_args)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Troubleshooting LED control failed: {e}")

            # Short delay then ask the comparison question
            QTimer.singleShot(1500, self._show_led_comparison_question)

        elif state == "CHECK_HARDWARE":
            bubble = self.push_interactive_message(
                f"Check the following for Channel {ch}:\n\n"
                f"• Fiber cable seated firmly at both ends\n"
                f"• LED connector fully attached\n"
                f"• Detector USB connected and powered on\n\n"
                f"**Have you checked all connections?**",
                ["Yes — all connections look good", "Found a loose connection"],
            )
            bubble.option_selected.connect(self._on_hardware_check_answer)

        elif state == "CONTACT_SUPPORT":
            bubble = self.push_interactive_message(
                "Would you like me to generate a support report?\n\n"
                "It will include: device serial, error details, calibration history, "
                "and a recent log excerpt — ready to email to support.",
                ["Yes, generate report", "No thanks"],
            )
            bubble.option_selected.connect(self._on_contact_support_answer)

        elif state == "DONE":
            # Turn off all LEDs
            try:
                ctrl.turn_off_channels()
            except Exception:
                pass
            # Clear controller reference
            self._ts_controller = None
            self._ts_diagnosis = None

    def _show_led_comparison_question(self):
        """Show the LED brightness comparison question (called after delay)."""
        ch = self._ts_diagnosis["channel"].upper()
        bubble = self.push_interactive_message(
            f"Look at both LEDs. **Is LED {ch} noticeably dimmer than LED A?**",
            [f"Yes, {ch} is dimmer", "No, they look similar"],
        )
        bubble.option_selected.connect(self._on_led_brightness_answer)

    def _on_water_check_answer(self, answer: str):
        """Handle user response to the water check question."""
        ch = self._ts_diagnosis["channel"].upper()
        if "wet" in answer.lower():
            self.push_system_message(
                f"**Water in the optical path** is causing the low signal on Channel {ch}.\n\n"
                f"Clean and dry the channel thoroughly, then retry calibration."
            )
            self._ts_state = "DONE"
            self._advance_troubleshooting()
        else:
            self._ts_state = "CHECK_LED_BRIGHTNESS"
            self._advance_troubleshooting()

    def _on_led_brightness_answer(self, answer: str):
        """Handle user response to the LED brightness comparison question."""
        ch = self._ts_diagnosis["channel"].upper()
        if "dimmer" in answer.lower():
            self.push_system_message(
                f"**LED {ch} appears to be failing.** The LED PCB likely needs "
                f"to be replaced.\n\nContact support for a replacement LED PCB."
            )
        else:
            self.push_system_message(
                f"The LEDs look OK and the path is dry. This could be a **fiber alignment "
                f"issue** or an intermittent connection.\n\n"
                f"Try reseating the fiber for Channel {ch} and retry calibration. "
                f"If the problem persists, contact support."
            )
        self._ts_state = "DONE"
        self._advance_troubleshooting()

    def _on_hardware_check_answer(self, answer: str):
        """Handle user response to the hardware connections check (never-calibrated track)."""
        ch = self._ts_diagnosis["channel"].upper()
        if "loose" in answer.lower():
            self.push_system_message(
                f"Re-seat the connection and retry calibration.\n\n"
                f"If Channel {ch} still fails after reconnecting, contact support."
            )
            self._ts_state = "DONE"
            self._advance_troubleshooting()
        else:
            # All connections look fine — fall through to LED brightness comparison
            self._ts_state = "CHECK_LED_BRIGHTNESS"
            self._advance_troubleshooting()

    def _on_contact_support_answer(self, answer: str):
        """Handle user response to the support report offer (consistently-failing track)."""
        if "generate" in answer.lower():
            self._ts_state = "DONE"
            self._advance_troubleshooting()
            self.start_bug_report_flow()
        else:
            self.push_system_message(
                "Contact support at **info@affiniteinstruments.com** with your device serial "
                "number and the error details shown in the calibration dialog."
            )
            self._ts_state = "DONE"
            self._advance_troubleshooting()