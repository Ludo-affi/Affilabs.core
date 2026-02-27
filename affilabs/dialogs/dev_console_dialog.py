"""Dev Console — internal developer tool.

NOT FOR PRODUCTION USE.

Activated via Ctrl+Shift+Alt+D (no UI entry point).
Provides raw command access to pump hardware (Cavro protocol) and the
controller (serial string passthrough) for bench testing without going through
the full injection coordinator flow.

Pump command examples (Cavro ASCII protocol):
  ?        → report status / position
  Q        → poll busy/idle (0=idle)
  W4R      → initialize (home plunger, valve to input)
  IR       → valve → input port
  OR       → valve → output port
  BR       → valve → bypass
  V5P1500R → aspirate 1500 steps at speed code 5
  V5D1500R → dispense 1500 steps at speed code 5
  ZR       → home plunger to 0
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

_DARK_BG   = "#1a1a2e"
_PANEL_BG  = "#16213e"
_INPUT_BG  = "#0f3460"
_ACCENT    = "#e94560"
_GREEN     = "#00d084"
_YELLOW    = "#f6c90e"
_TEXT      = "#e0e0e0"
_DIM_TEXT  = "#888"
_MONO_FONT = "Consolas"


class _LogRelay(QObject):
    """Thread-safe relay for log lines from background send thread."""
    line_ready = Signal(str)


class DevConsoleDialog(QDialog):
    """Floating developer console for raw pump + controller command testing.

    Open via Ctrl+Shift+Alt+D — not exposed anywhere in the UI.
    """

    def __init__(self, app, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self._app = app
        self._relay = _LogRelay()
        self._relay.line_ready.connect(self._append_log)
        self._lock = threading.Lock()

        self.setWindowTitle("⚠  Dev Console — INTERNAL")
        self.setMinimumSize(680, 560)
        self.resize(720, 620)
        self.setStyleSheet(f"""
            QDialog {{ background: {_DARK_BG}; color: {_TEXT}; }}
            QLabel  {{ color: {_TEXT}; }}
        """)

        self._build_ui()

    # ──────────────────────────────────────────────────────────────────────
    # UI construction
    # ──────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # ── Title bar ──────────────────────────────────────────────────────
        title_row = QHBoxLayout()
        warn = QLabel("⚠  DEVELOPER CONSOLE — DO NOT USE IN PRODUCTION")
        warn.setStyleSheet(f"color: {_ACCENT}; font-weight: bold; font-size: 11px;")
        title_row.addWidget(warn)
        title_row.addStretch()

        self._hw_status = QLabel("● checking…")
        self._hw_status.setStyleSheet(f"color: {_YELLOW}; font-size: 10px;")
        title_row.addWidget(self._hw_status)
        root.addLayout(title_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {_ACCENT}; border: 1px solid {_ACCENT};")
        root.addWidget(sep)

        # ── Splitter: controls top, log bottom ────────────────────────────
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background: #333; }")

        # --- Controls panel ---
        ctrl_widget = QWidget()
        ctrl_layout = QVBoxLayout(ctrl_widget)
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        ctrl_layout.setSpacing(8)

        ctrl_layout.addWidget(self._build_pump_section())
        ctrl_widget.setMaximumHeight(260)

        splitter.addWidget(ctrl_widget)

        # --- Log panel ---
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)

        log_header = QHBoxLayout()
        log_label = QLabel("Response Log")
        log_label.setStyleSheet(f"color: {_DIM_TEXT}; font-size: 10px; font-weight: bold;")
        log_header.addWidget(log_label)
        log_header.addStretch()
        clr_btn = QPushButton("Clear")
        clr_btn.setFixedSize(52, 20)
        clr_btn.setStyleSheet(
            f"QPushButton {{ background: #333; color: {_DIM_TEXT}; border: 1px solid #444; "
            f"border-radius: 3px; font-size: 10px; }}"
            f"QPushButton:hover {{ background: #444; }}"
        )
        clr_btn.clicked.connect(self._clear_log)
        log_header.addWidget(clr_btn)
        log_layout.addLayout(log_header)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont(_MONO_FONT, 9))
        self._log.setStyleSheet(
            f"QTextEdit {{ background: {_PANEL_BG}; color: {_GREEN}; border: 1px solid #333; }}"
        )
        log_layout.addWidget(self._log)
        splitter.addWidget(log_widget)

        splitter.setSizes([240, 340])
        root.addWidget(splitter)

        # ── Footer ────────────────────────────────────────────────────────
        footer = QLabel("Ctrl+Shift+Alt+D to close  •  Commands run on GUI thread — keep them fast")
        footer.setStyleSheet(f"color: {_DIM_TEXT}; font-size: 9px;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(footer)

        # Update status label
        QTimer.singleShot(0, self._refresh_status)

    def _build_pump_section(self) -> QWidget:
        box = QFrame()
        box.setStyleSheet(
            f"QFrame {{ background: {_PANEL_BG}; border: 1px solid #333; border-radius: 4px; }}"
        )
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        title = QLabel("Pump — Raw Cavro Command")
        title.setStyleSheet(f"color: {_YELLOW}; font-weight: bold; font-size: 10px; border: none;")
        layout.addWidget(title)

        # Address + command row
        row1 = QHBoxLayout()

        addr_label = QLabel("Addr:")
        addr_label.setStyleSheet(f"color: {_DIM_TEXT}; font-size: 10px; border: none;")
        row1.addWidget(addr_label)

        self._addr_spin = QSpinBox()
        self._addr_spin.setRange(1, 15)
        self._addr_spin.setValue(1)
        self._addr_spin.setFixedWidth(52)
        self._addr_spin.setStyleSheet(
            f"QSpinBox {{ background: {_INPUT_BG}; color: {_TEXT}; border: 1px solid #555; "
            f"border-radius: 3px; padding: 2px; font-family: {_MONO_FONT}; font-size: 10px; }}"
        )
        row1.addWidget(self._addr_spin)

        cmd_label = QLabel("Command:")
        cmd_label.setStyleSheet(f"color: {_DIM_TEXT}; font-size: 10px; border: none;")
        row1.addWidget(cmd_label)

        self._cmd_input = QLineEdit()
        self._cmd_input.setPlaceholderText("e.g.  ?    W4R    V5P1500R    IR")
        self._cmd_input.setFont(QFont(_MONO_FONT, 10))
        self._cmd_input.setStyleSheet(
            f"QLineEdit {{ background: {_INPUT_BG}; color: {_TEXT}; border: 1px solid #555; "
            f"border-radius: 3px; padding: 4px 6px; }}"
        )
        self._cmd_input.returnPressed.connect(self._send_pump_cmd)
        row1.addWidget(self._cmd_input, stretch=1)

        send_btn = QPushButton("Send")
        send_btn.setFixedSize(60, 28)
        send_btn.setStyleSheet(
            f"QPushButton {{ background: {_ACCENT}; color: white; font-weight: bold; "
            f"border: none; border-radius: 3px; }}"
            f"QPushButton:hover {{ background: #c73652; }}"
            f"QPushButton:disabled {{ background: #555; color: #888; }}"
        )
        send_btn.clicked.connect(self._send_pump_cmd)
        row1.addWidget(send_btn)

        layout.addLayout(row1)

        # Preset buttons
        preset_row = QHBoxLayout()
        preset_row.setSpacing(4)

        presets = [
            ("Status ?",  "?"),
            ("Idle Q",    "Q"),
            ("Init W4R",  "W4R"),
            ("Input I",   "IR"),
            ("Output O",  "OR"),
            ("Bypass B",  "BR"),
            ("Home Z",    "ZR"),
        ]

        preset_lbl = QLabel("Quick:")
        preset_lbl.setStyleSheet(f"color: {_DIM_TEXT}; font-size: 10px; border: none;")
        preset_row.addWidget(preset_lbl)

        for label, cmd in presets:
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setStyleSheet(
                f"QPushButton {{ background: {_INPUT_BG}; color: {_TEXT}; border: 1px solid #555; "
                f"border-radius: 3px; font-size: 9px; padding: 0 6px; }}"
                f"QPushButton:hover {{ background: #1a4080; }}"
            )
            btn.clicked.connect(lambda checked=False, c=cmd: self._preset_pump(c))
            preset_row.addWidget(btn)

        preset_row.addStretch()
        layout.addLayout(preset_row)

        return box

    # ──────────────────────────────────────────────────────────────────────
    # Logic
    # ──────────────────────────────────────────────────────────────────────

    def _refresh_status(self) -> None:
        hw = self._get_pump_hw()
        if hw is None:
            self._hw_status.setText("● no pump hardware")
            self._hw_status.setStyleSheet(f"color: {_ACCENT}; font-size: 10px;")
        else:
            pump_type = type(hw).__name__
            self._hw_status.setText(f"● {pump_type} connected")
            self._hw_status.setStyleSheet(f"color: {_GREEN}; font-size: 10px;")

    def _get_pump_hw(self):
        """Return the lowest-level PumpHAL adapter, or None."""
        hw_mgr = getattr(self._app, "hardware_mgr", None)
        if hw_mgr is None:
            return None
        return getattr(hw_mgr, "pump", None)   # AffipumpAdapter | XP3000Adapter | None

    def _preset_pump(self, cmd: str) -> None:
        self._cmd_input.setText(cmd)
        self._send_pump_cmd()

    def _send_pump_cmd(self) -> None:
        cmd = self._cmd_input.text().strip()
        if not cmd:
            return

        hw = self._get_pump_hw()
        if hw is None:
            self._log_line("✘ No pump hardware connected", error=True)
            return

        addr = self._addr_spin.value()
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._log_line(f"[{ts}]  → /{addr}{cmd}", sent=True)

        # Run on a background thread so the GUI doesn't freeze on slow serial
        def _worker():
            try:
                raw = hw.send_command(addr, cmd.encode("ascii"))
                if isinstance(raw, (bytes, bytearray)):
                    resp = raw.decode("ascii", errors="replace").strip()
                else:
                    resp = str(raw).strip()
                reply = repr(resp) if resp else "(empty)"
                self._relay.line_ready.emit(f"          ← {reply}")
            except Exception as exc:
                self._relay.line_ready.emit(f"          ✘ ERROR: {exc}")

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _append_log(self, text: str) -> None:
        """Append a line to the log widget. Called on GUI thread via signal."""
        self._log.append(text)
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _log_line(self, text: str, *, error: bool = False, sent: bool = False) -> None:
        """Append a coloured line to the log."""
        if error:
            color = _ACCENT
        elif sent:
            color = _YELLOW
        else:
            color = _GREEN

        self._log.append(f'<span style="color:{color};">{text}</span>')
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear_log(self) -> None:
        self._log.clear()

    # ──────────────────────────────────────────────────────────────────────
    # Window lifecycle
    # ──────────────────────────────────────────────────────────────────────

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_status()
        self._log_line(
            f"Dev Console opened  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            sent=True,
        )

    def closeEvent(self, event) -> None:
        self._log_line("Dev Console closed.")
        super().closeEvent(event)
