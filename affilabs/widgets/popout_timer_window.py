"""Pop-Out Timer Window - Standalone floating countdown timer.

A frameless, always-on-top, draggable countdown window that pops out
of the main application. The user can move it anywhere on screen and
resize the font from small to extra-large with a single click.

FEATURES:
- Always on top of other windows
- Draggable by clicking anywhere on the window
- Expandable font (5 sizes: Normal → Large → XL → XXL → XXXL, cycles)
- Shows label + MM:SS countdown
- Double-click time to edit duration (before start or when paused)
- Click title to edit label inline
- Settings button for font size and sound options
- Right-click context menu: Restart, Clear, Close
- Subtle rounded Apple-style design

USAGE:
    from affilabs.widgets.popout_timer_window import PopOutTimerWindow

    win = PopOutTimerWindow(parent=main_window)
    win.set_configurable(minutes=5, seconds=0, label="Incubation", sound_enabled=True)
    win.show()
"""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import Qt, Signal, QPoint, QSize, QTimer
from PySide6.QtGui import QAction, QMouseEvent, QPainter, QColor, QPen, QFont, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from affilabs.ui_styles import Colors, Fonts


# Clickable label classes for timer window
class ClickableLabel(QLabel):
    """QLabel that emits mousePressed signal."""
    mousePressed = Signal(QMouseEvent)

    def mousePressEvent(self, event: QMouseEvent):
        self.mousePressed.emit(event)
        event.accept()


class TimeLabel(QLabel):
    """QLabel for timer display - detects double-click."""
    doubleClicked = Signal()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self.doubleClicked.emit()
        event.accept()


class TitleLabel(QLabel):
    """QLabel for timer title - detects single click."""
    singleClicked = Signal()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.singleClicked.emit()
        event.accept()


# ---------------------------------------------------------------------------
# Font-size presets (label_px, timer_px, window_min_width, window_height)
# ---------------------------------------------------------------------------
_FONT_PRESETS = [
    {"name": "Normal",  "label": 12, "timer": 28, "w": 220, "h": 80},
    {"name": "Large",   "label": 14, "timer": 44, "w": 300, "h": 110},
    {"name": "XL",      "label": 18, "timer": 64, "w": 400, "h": 140},
    {"name": "XXL",     "label": 22, "timer": 96, "w": 540, "h": 190},
    {"name": "XXXL",    "label": 26, "timer": 128, "w": 700, "h": 240},
]


class PopOutTimerWindow(QWidget):
    """Standalone floating countdown timer window.

    Supports inline editing of time and title before timer starts.

    Signals:
        clear_requested: User wants to stop & clear the timer.
        restart_requested: User wants to restart the timer.
        closed: Window was closed by the user.
        timer_ready: Emitted when user confirms settings (time_seconds, label).
        window_shown: Emitted when popup becomes visible
        window_hidden: Emitted when popup is hidden/closed
    """

    clear_requested = Signal()
    restart_requested = Signal()
    pause_requested = Signal()
    resume_requested = Signal()
    closed = Signal()
    timer_ready = Signal(int, str)  # (total_seconds, label)
    alarm_stopped = Signal()  # User stopped the alarm
    time_edited_while_paused = Signal(int)  # (remaining_seconds) - emitted when time is edited while paused
    window_shown = Signal()  # Emitted when window becomes visible
    window_hidden = Signal()  # Emitted when window is hidden/closed

    def __init__(self, parent=None):
        super().__init__(
            None,  # Always independent - no parent
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(180, 60)

        # Set window icon
        try:
            from affilabs.utils.resource_path import get_affilabs_resource
            icon_path = get_affilabs_resource("ui/img/timer_icon.png")
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            pass  # Silent fallback if icon not found

        # Drag state
        self._drag_pos: Optional[QPoint] = None

        # Current font preset index (start at XXL)
        self._size_index: int = 3

        # Timer state
        self._label_text: str = ""
        self._remaining: int = 0
        self._paused: bool = False
        self._alarm_active: bool = False

        # Initial config (saved when START is pressed, used for reset after alarm)
        self._initial_config_minutes: int = 5
        self._initial_config_seconds: int = 0
        self._initial_config_label: str = "Timer"

        # Editable mode (before timer starts)
        self._is_configurable: bool = False
        self._config_minutes: int = 5
        self._config_seconds: int = 0
        self._sound_enabled: bool = True
        self._rolling_numbers: bool = False

        # Flag for next double-click to edit
        self._editing_time: bool = False
        self._editing_title: bool = False

        # Force tooltips to use regular font size regardless of timer size
        self.setStyleSheet("""
            QToolTip {
                font-size: 12px;
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #555555;
                padding: 4px 8px;
                border-radius: 4px;
            }
        """)

        self._build_ui()
        self._apply_size_preset()

    # ------------------------------------------------------------------
    #  UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Container (painted with rounded background)
        self._container = QWidget(self)
        self._container.setObjectName("popout_container")
        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(16, 10, 16, 14)
        container_layout.setSpacing(2)

        # Store first_show flag for positioning
        self._first_show = True

        # --- Title bar row (label + buttons) ---
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(4)

        # Add spacer to account for window icon
        title_row.addSpacing(24)

        # Title label (clickable to edit)
        self._label_lbl = TitleLabel("Timer")
        self._label_lbl.setStyleSheet(
            f"color: {Colors.SECONDARY_TEXT}; font-weight: 600;"
        )
        self._label_lbl.setCursor(Qt.CursorShape.IBeamCursor)
        self._label_lbl.setToolTip("Click to edit title")
        self._label_lbl.singleClicked.connect(self._on_title_label_clicked)
        title_row.addWidget(self._label_lbl, 1)

        # Play/Pause button - square with thin arrow
        self._pause_btn = QPushButton("||")
        self._pause_btn.setMinimumSize(28, 22)
        self._pause_btn.setMaximumSize(32, 26)
        self._pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pause_btn.setToolTip("Pause timer")
        self._pause_btn.clicked.connect(self._toggle_pause)
        self._style_control_btn(self._pause_btn)
        title_row.addWidget(self._pause_btn)

        # Start button (shown only in config mode)
        self._start_btn = QPushButton("▶")
        self._start_btn.setMinimumSize(28, 22)
        self._start_btn.setMaximumSize(32, 26)
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.setToolTip("Start timer")
        self._start_btn.clicked.connect(self._on_start_timer)
        self._style_control_btn(self._start_btn)
        self._start_btn.setVisible(False)
        title_row.addWidget(self._start_btn)

        # Restart button - square with thin arrow
        self._restart_btn = QPushButton("↺")
        self._restart_btn.setMinimumSize(28, 22)
        self._restart_btn.setMaximumSize(32, 26)
        self._restart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._restart_btn.setToolTip("Restart timer")
        self._restart_btn.clicked.connect(self.restart_requested.emit)
        self._style_control_btn(self._restart_btn)
        title_row.addWidget(self._restart_btn)

        # Resize button (cycles font sizes)
        self._resize_btn = QPushButton("Aa")
        self._resize_btn.setMinimumSize(24, 24)
        self._resize_btn.setMaximumSize(28, 28)
        self._resize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._resize_btn.setToolTip("Cycle font size")
        self._resize_btn.clicked.connect(self._cycle_font_size)
        self._style_mini_btn(self._resize_btn)
        title_row.addWidget(self._resize_btn)

        # Close button
        self._close_btn = QPushButton("✕")
        self._close_btn.setMinimumSize(24, 24)
        self._close_btn.setMaximumSize(28, 28)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setToolTip("Close timer window")
        self._close_btn.clicked.connect(self._on_close)
        self._style_mini_btn(self._close_btn)
        title_row.addWidget(self._close_btn)

        container_layout.addLayout(title_row)

        # --- Big countdown label (double-click to edit time) ---
        self._time_lbl = TimeLabel("00:00")
        self._time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._time_lbl.setMinimumHeight(40)
        self._time_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._time_lbl.setStyleSheet(
            f"color: {Colors.PRIMARY_TEXT}; font-family: {Fonts.MONOSPACE}; font-weight: 700;"
        )
        self._time_lbl.setCursor(Qt.CursorShape.IBeamCursor)
        self._time_lbl.setToolTip("Double-click to edit time (works before start or when paused)")
        self._time_lbl.doubleClicked.connect(self._start_time_edit)
        container_layout.addWidget(self._time_lbl)

        # --- Stop Alarm button (hidden by default, shown when alarm is active) ---
        self._stop_alarm_btn = QPushButton("⏹ STOP ALARM")
        self._stop_alarm_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._stop_alarm_btn.setMinimumHeight(60)
        self._stop_alarm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_alarm_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FF3B30, stop:1 #CC0000);
                border: 2px solid #990000;
                border-radius: 12px;
                color: white;
                font-size: 16px;
                font-weight: 700;
                padding: 12px 18px;
                margin: 5px 0px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FF6B60, stop:1 #FF3B30);
            }
            QPushButton:pressed {
                background: #990000;
            }
        """)
        self._stop_alarm_btn.clicked.connect(self._on_stop_alarm)
        self._stop_alarm_btn.setVisible(False)
        container_layout.addWidget(self._stop_alarm_btn)

        root.addWidget(self._container)

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    @staticmethod
    def _style_mini_btn(btn: QPushButton):
        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 12px;
                color: #86868B;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(0,0,0,0.08);
                color: #1D1D1F;
            }
        """)

    @staticmethod
    def _style_control_btn(btn: QPushButton):
        """Style for play/pause/restart buttons."""
        btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 128, 255, 0.1);
                border: 1px solid rgba(0, 128, 255, 0.3);
                border-radius: 4px;
                color: #0080FF;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(0, 128, 255, 0.2);
                border: 1px solid rgba(0, 128, 255, 0.5);
                color: #0066CC;
            }
            QPushButton:pressed {
                background: rgba(0, 128, 255, 0.3);
            }
        """)

    # ------------------------------------------------------------------
    #  Size cycling
    # ------------------------------------------------------------------
    def _cycle_font_size(self):
        self._size_index = (self._size_index + 1) % len(_FONT_PRESETS)
        self._apply_size_preset()

    def _apply_size_preset(self):
        preset = _FONT_PRESETS[self._size_index]
        self._label_lbl.setStyleSheet(
            f"color: {Colors.SECONDARY_TEXT}; font-weight: 600; font-size: {preset['label']}px;"
        )
        # Bright blue color for the timer display
        self._time_lbl.setStyleSheet(
            f"QLabel {{"
            f"  color: #0080FF; font-family: {Fonts.MONOSPACE}; "
            f"  font-weight: 700; font-size: {preset['timer']}px;"
            f"}}"
            f"QToolTip {{"
            f"  font-size: 12px;"
            f"  background-color: #2D2D2D;"
            f"  color: #FFFFFF;"
            f"  border: 1px solid #555555;"
            f"  padding: 4px 8px;"
            f"  border-radius: 4px;"
            f"}}"
        )
        self.setMinimumSize(preset["w"], preset["h"])
        self.resize(preset["w"], preset["h"])

    # ------------------------------------------------------------------
    #  Public API - Configuration mode
    # ------------------------------------------------------------------
    def set_configurable(self, minutes: int = 5, seconds: int = 0, label: str = "Timer",
                        sound_enabled: bool = True, rolling_numbers: bool = False):
        """Put timer in configuration mode (editable before timer starts).

        Args:
            minutes: Initial minutes value
            seconds: Initial seconds value
            label: Initial timer label
            sound_enabled: Whether to play sound on completion
            rolling_numbers: Whether to use rolling number animation
        """
        self._is_configurable = True
        self._config_minutes = minutes
        self._config_seconds = seconds
        self._sound_enabled = sound_enabled
        self._rolling_numbers = rolling_numbers

        self._label_text = label
        self._update_time_display()
        self._label_lbl.setText(label)

        # Show START button, hide pause and restart
        self._pause_btn.setVisible(False)
        self._restart_btn.setVisible(False)
        self._start_btn.setVisible(True)

    def get_config(self) -> Tuple[int, int, str, bool, bool]:
        """Get current configuration (minutes, seconds, label, sound_enabled, rolling_numbers)."""
        return (self._config_minutes, self._config_seconds, self._label_text,
                self._sound_enabled, self._rolling_numbers)

    # ------------------------------------------------------------------
    #  Public API - Runtime
    # ------------------------------------------------------------------
    def update_countdown(self, label: str, remaining_seconds: int):
        """Update the pop-out display.

        Args:
            label: Timer label (e.g. "Incubation")
            remaining_seconds: Seconds left on the clock
        """
        self._is_configurable = False
        self._label_text = label
        self._remaining = remaining_seconds

        self._update_time_display()
        if not self._paused:
            self._label_lbl.setText(label)

    def _update_time_display(self):
        """Update the time label based on current remaining or config."""
        if self._is_configurable:
            minutes = self._config_minutes
            seconds = self._config_seconds
        else:
            minutes = self._remaining // 60
            seconds = self._remaining % 60
        self._time_lbl.setText(f"{minutes:02d}:{seconds:02d}")

        # Reset color to blue if alarm was active (timer had finished)
        if self._alarm_active:
            self._alarm_active = False
            preset = _FONT_PRESETS[self._size_index]
            self._time_lbl.setStyleSheet(
                f"QLabel {{\n"
                f"  color: #0080FF; font-family: {Fonts.MONOSPACE}; "
                f"font-weight: 700; font-size: {preset['timer']}px;\n"
                f"}}\n"
                f"QToolTip {{\n"
                f"  font-size: 12px;\n"
                f"  background-color: #2D2D2D;\n"
                f"  color: #FFFFFF;\n"
                f"  border: 1px solid #555555;\n"
                f"  padding: 4px 8px;\n"
                f"  border-radius: 4px;\n"
                f"}}"
            )

    def set_paused(self, paused: bool):
        """Update the visual paused state (called by main window)."""
        self._paused = paused
        if paused:
            self._pause_btn.setText("▸")
            self._pause_btn.setToolTip("Resume timer")
            self._label_lbl.setText(f"⏸ {self._label_text}")
            # Dim the time label to show paused state (amber/orange)
            preset = _FONT_PRESETS[self._size_index]
            self._time_lbl.setStyleSheet(
                f"QLabel {{\n"
                f"  color: #FF9500; font-family: {Fonts.MONOSPACE}; "
                f"font-weight: 700; font-size: {preset['timer']}px;\n"
                f"}}\n"
                f"QToolTip {{\n"
                f"  font-size: 12px;\n"
                f"  background-color: #2D2D2D;\n"
                f"  color: #FFFFFF;\n"
                f"  border: 1px solid #555555;\n"
                f"  padding: 4px 8px;\n"
                f"  border-radius: 4px;\n"
                f"}}"
            )
        else:
            self._pause_btn.setText("||")
            self._pause_btn.setToolTip("Pause timer")
            self._label_lbl.setText(self._label_text)
            # Restore bright blue color
            preset = _FONT_PRESETS[self._size_index]
            self._time_lbl.setStyleSheet(
                f"QLabel {{\n"
                f"  color: #0080FF; font-family: {Fonts.MONOSPACE}; "
                f"font-weight: 700; font-size: {preset['timer']}px;\n"
                f"}}\n"
                f"QToolTip {{\n"
                f"  font-size: 12px;\n"
                f"  background-color: #2D2D2D;\n"
                f"  color: #FFFFFF;\n"
                f"  border: 1px solid #555555;\n"
                f"  padding: 4px 8px;\n"
                f"  border-radius: 4px;\n"
                f"}}"
            )

    def timer_finished(self, label: str, next_action: str = ""):
        """Show alarm state - display next action or TIME'S UP and show stop button.

        Args:
            label: Timer label (e.g. "Contact Time — 50 nM")
            next_action: If provided, shown instead of "TIME'S UP!"
                         (e.g. "🧪 WASH NOW" for contact time expiry)
        """
        self._alarm_active = True
        self._time_lbl.setText(next_action if next_action else "TIME'S UP!")
        self._label_lbl.setText(f"🔔 {label}")
        self._remaining = 0
        self._paused = False

        # Make time display flash red/orange (use regular font for alarm text, not monospace)
        preset = _FONT_PRESETS[self._size_index]
        # Use smaller font for alarm text to ensure it fits
        alarm_font_size = min(preset['timer'], 48)
        self._time_lbl.setStyleSheet(
            f"QLabel {{"
            f"  color: #FF3B30; font-family: -apple-system, 'SF Pro Display', sans-serif; "
            f"  font-weight: 700; font-size: {alarm_font_size}px;"
            f"  text-align: center; line-height: 1.0; padding: 5px;"
            f"}}"
            f"QToolTip {{"
            f"  font-size: 12px;"
            f"  background-color: #2D2D2D;"
            f"  color: #FFFFFF;"
            f"  border: 1px solid #555555;"
            f"  padding: 4px 8px;"
            f"  border-radius: 4px;"
            f"}}"
        )

        # Adjust window size to accommodate alarm text and stop button
        # Ensure minimum space for both alarm text and button
        min_width = max(preset["w"], 280)
        min_height = max(preset["h"], 160)
        self.setMinimumSize(min_width, min_height)
        self.resize(min_width, min_height)

        # Hide control buttons, show stop alarm button
        self._pause_btn.setVisible(False)
        self._restart_btn.setVisible(False)
        self._start_btn.setVisible(False)
        self._stop_alarm_btn.setVisible(True)

        # Make window flash/pulse to get attention
        self.raise_()
        self.activateWindow()

    def _on_stop_alarm(self):
        """User clicked stop alarm button — stop alarm, reset to initial time, stay idle."""
        self._alarm_active = False
        self._stop_alarm_btn.setVisible(False)

        # Emit signal to stop alarm sound in main UI
        self.alarm_stopped.emit()

        # Reset time label color and font to default blue and monospace
        preset = _FONT_PRESETS[self._size_index]
        self._time_lbl.setStyleSheet(
            f"QLabel {{"
            f"  color: #0080FF; font-family: {Fonts.MONOSPACE}; "
            f"  font-weight: 700; font-size: {preset['timer']}px;"
            f"}}"
            f"QToolTip {{"
            f"  font-size: 12px;"
            f"  background-color: #2D2D2D;"
            f"  color: #FFFFFF;"
            f"  border: 1px solid #555555;"
            f"  padding: 4px 8px;"
            f"  border-radius: 4px;"
            f"}}"
        )

        # Reset to configurable/idle mode with the initial time
        self.set_configurable(
            minutes=self._initial_config_minutes,
            seconds=self._initial_config_seconds,
            label=self._initial_config_label,
            sound_enabled=self._sound_enabled,
            rolling_numbers=self._rolling_numbers,
        )

    # ------------------------------------------------------------------
    #  Inline editing - Time (double-click)
    # ------------------------------------------------------------------
    def _on_start_timer(self):
        """Handle START button click - emit timer_ready with current config."""
        if self._is_configurable:
            total_seconds = self._config_minutes * 60 + self._config_seconds
            if total_seconds > 0:
                # Save initial config so we can reset after alarm
                self._initial_config_minutes = self._config_minutes
                self._initial_config_seconds = self._config_seconds
                self._initial_config_label = self._label_text

                self._is_configurable = False
                # Show pause and restart buttons, hide start button
                self._pause_btn.setVisible(True)
                self._restart_btn.setVisible(True)
                self._start_btn.setVisible(False)
                # Emit signal to start countdown
                self.timer_ready.emit(total_seconds, self._label_text)

    def _start_time_edit(self):
        """Replace time label with editable input.

        Allow editing when:
        - Timer is in configurable mode (before start)
        - Timer is paused (can change remaining time)
        """
        # Only allow editing if configurable or paused
        if not (self._is_configurable or self._paused):
            return

        container = self._container.layout()

        # If paused, we edit the remaining time; if configurable, we edit config time
        is_editing_paused = self._paused and not self._is_configurable

        if is_editing_paused:
            minutes = self._remaining // 60
            seconds = self._remaining % 60
        else:
            minutes = self._config_minutes
            seconds = self._config_seconds

        # Create input field for MM:SS format
        time_input = QLineEdit()
        time_input.setText(f"{minutes:02d}:{seconds:02d}")
        time_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_input.setPlaceholderText("MM:SS")

        # Apply styling to match the time label
        preset = _FONT_PRESETS[self._size_index]

        # Use different color when editing paused timer
        input_color = "#FF9500" if is_editing_paused else "#0080FF"
        border_color = "#FF9500" if is_editing_paused else "#007AFF"

        time_input.setStyleSheet(f"""
            QLineEdit {{
                background: #F8F9FA;
                border: 2px solid {border_color};
                border-radius: 4px;
                padding: 8px;
                font-size: {preset['timer']}px;
                font-weight: 700;
                font-family: {Fonts.MONOSPACE};
                color: {input_color};
                letter-spacing: 4px;
            }}
        """)
        time_input.setMaxLength(6)

        # Replace the time label with input
        container.replaceWidget(self._time_lbl, time_input)

        time_input.selectAll()
        time_input.setFocus()

        def confirm_time_edit():
            """Confirm time edit when user presses Enter."""
            text = time_input.text().strip()
            try:
                if ':' in text:
                    parts = text.split(':')
                    edit_minutes = int(parts[0])
                    edit_seconds = int(parts[1]) if len(parts) > 1 else 0
                else:
                    # If just numbers, assume it's minutes
                    edit_minutes = int(text)
                    edit_seconds = 0

                # Validate ranges
                if 0 <= edit_minutes <= 999 and 0 <= edit_seconds <= 59:
                    if is_editing_paused:
                        # Update remaining time while paused
                        self._remaining = edit_minutes * 60 + edit_seconds
                        # Notify main UI that remaining time was edited
                        self.time_edited_while_paused.emit(self._remaining)
                    else:
                        # Update config time before timer started
                        self._config_minutes = edit_minutes
                        self._config_seconds = edit_seconds
            except (ValueError, IndexError):
                pass

            # Replace input back with label
            self._update_time_display()
            container.replaceWidget(time_input, self._time_lbl)
            time_input.deleteLater()

        time_input.returnPressed.connect(confirm_time_edit)
        time_input.editingFinished.connect(confirm_time_edit)

    # ------------------------------------------------------------------
    #  Inline editing - Title (click)
    # ------------------------------------------------------------------
    def _on_title_label_clicked(self):
        """Handle click on title label - click to edit."""
        if not self._is_configurable:
            return

        self._start_title_edit()

    def _start_title_edit(self):
        """Replace title label with editable input."""
        container = self._container.layout()
        title_row = container.itemAt(0)  # First layout is title row

        if title_row is None or title_row.layout() is None:
            return

        # Create input field for title
        title_input = QLineEdit()
        title_input.setText(self._label_text)
        title_input.setPlaceholderText("Timer label")

        title_input.setStyleSheet(f"""
            QLineEdit {{
                background: #F8F9FA;
                border: 2px solid #007AFF;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 13px;
                font-weight: 600;
                color: #007AFF;
            }}
        """)

        # Replace label in title row
        title_row_layout = title_row.layout()
        title_row_layout.replaceWidget(self._label_lbl, title_input)

        title_input.selectAll()
        title_input.setFocus()

        def confirm_title_edit():
            """Confirm title edit when user presses Enter."""
            text = title_input.text().strip()
            if text:
                self._label_text = text

            # Replace input back with label
            self._label_lbl.setText(self._label_text)
            title_row_layout.replaceWidget(title_input, self._label_lbl)
            title_input.deleteLater()

        title_input.returnPressed.connect(confirm_title_edit)
        title_input.editingFinished.connect(confirm_title_edit)

    # ------------------------------------------------------------------
    #  Painting — rounded rect background
    # ------------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(2, 2, -2, -2)

        # Solid white fill (no transparency - removes the "film" look)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 255))  # Fully opaque white
        painter.drawRoundedRect(rect, 14, 14)

        # Blue outline (thicker for better visibility)
        pen = QPen(QColor(0, 122, 255))  # #007AFF
        pen.setWidth(3)  # Increased from 2 to 3 for crisper outline
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 14, 14)

        painter.end()

    # ------------------------------------------------------------------
    #  Dragging
    # ------------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None

    # ------------------------------------------------------------------
    #  Context menu
    # ------------------------------------------------------------------
    def _show_context_menu(self, pos):
        menu = QMenu(self)

        # Pause / Resume
        if self._paused:
            pause_action = QAction("▶ Resume Timer", self)
            pause_action.triggered.connect(self._toggle_pause)
        else:
            pause_action = QAction("⏸ Pause Timer", self)
            pause_action.triggered.connect(self._toggle_pause)
        menu.addAction(pause_action)

        restart = QAction("🔄 Restart Timer", self)
        restart.triggered.connect(self.restart_requested.emit)
        menu.addAction(restart)

        clear = QAction("✕ Clear Timer", self)
        clear.triggered.connect(self._on_clear)
        menu.addAction(clear)

        menu.addSeparator()

        close = QAction("Close Window", self)
        close.triggered.connect(self._on_close)
        menu.addAction(close)

        menu.exec(self.mapToGlobal(pos))

    # ------------------------------------------------------------------
    #  Pause / resume
    # ------------------------------------------------------------------
    def _toggle_pause(self):
        if self._paused:
            self.resume_requested.emit()
        else:
            self.pause_requested.emit()

    # ------------------------------------------------------------------
    #  Close / clear helpers
    # ------------------------------------------------------------------
    def _on_close(self):
        self.hide()
        self.closed.emit()

    def _on_clear(self):
        self.clear_requested.emit()
        self.hide()

    def showEvent(self, event):
        """Handle show event - position at top-left on first show."""
        if self._first_show:
            # Position at top-left of screen on first show
            self.move(0, 0)
            self._first_show = False
        super().showEvent(event)
        # Emit signal to notify button to highlight
        self.window_shown.emit()

    def hideEvent(self, event):
        """Handle hide event - notify button to remove highlight."""
        super().hideEvent(event)
        self.window_hidden.emit()

    def closeEvent(self, event):
        # Emit signal to notify button to remove highlight
        self.window_hidden.emit()
        self.closed.emit()
        event.accept()
