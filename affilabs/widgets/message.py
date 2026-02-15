from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMessageBox


class TimerMessageBox(QMessageBox):
    def __init__(
        self,
        timeout=None,
        parent=None,
        yn=False,
        q=(False, "", ""),
        title=None,
    ):
        super(TimerMessageBox, self).__init__(parent)
        self.setWindowTitle(title or "Affinite Instruments")
        self.setWindowIcon(QIcon(":/img/img/affinite2.ico"))
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setMinimumSize(600, 320)
        if yn:
            self.y_btn = self.addButton("Yes", QMessageBox.ButtonRole.AcceptRole)
            self.n_btn = self.addButton("No", QMessageBox.ButtonRole.RejectRole)
            self.wait_for_button = True
        elif q[0]:
            self.y_btn = self.addButton(q[1], QMessageBox.ButtonRole.AcceptRole)
            self.n_btn = self.addButton(q[2], QMessageBox.ButtonRole.RejectRole)
            self.wait_for_button = True
        else:
            self.wait_for_button = False

        if timeout is not None:
            # Coerce timeout (seconds) to an integer millisecond interval; disable timer on invalid types
            msec = None
            try:
                # Allow int, float, or numeric strings
                msec = int(float(timeout) * 1000)
            except Exception:
                msec = None

            if msec is not None and msec > 0:
                self.timer = QTimer(self)
                self.timer.setInterval(msec)
                self.timer.timeout.connect(self._on_timeout)
                self.timer.start()

    def _on_timeout(self):
        self.timer.stop()
        self.close()

    def closeEvent(self, event):
        if hasattr(self, "timer"):
            self.timer.stop()
        event.accept()


def _sanitize_ascii(text: str) -> str:
    """Sanitize text for Windows PowerShell/Qt message boxes by removing mojibake.

    - Replaces common decorative glyphs/emojis with ASCII tags.
    - Strips any remaining non-ASCII characters to avoid cp1252 issues.
    """
    if text is None:
        return ""
    try:
        # Ensure string type
        if not isinstance(text, str):
            text = str(text)

        # Common mappings from prior logs
        replacements = {
            # Decorative bullets/markers
            "ΓÇó": "- ",
            "≡ƒöº": "[INFO] ",
            "≡ƒôè": "[ACTION] ",
            "≡ƒÜÇ": "[START] ",
            "Γ£à": "[OK] ",
            "ΓÜá∩╕Å": "[WARN] ",
            "Γ¥î": "[ERROR] ",
            "Γä╣∩╕Å": "[NOTE] ",
            # Arrows/boxes often seen in logs
            "╞Æ": "",
            "├": "",
            "┬": "",
            "│": "",
            "┤": "",
        }
        for k, v in replacements.items():
            text = text.replace(k, v)

        # Strip remaining non-ASCII
        text = "".join(ch for ch in text if ord(ch) < 128)
        return text
    except Exception:
        # Fallback: naive ASCII strip
        try:
            return "".join(ch for ch in str(text) if ord(ch) < 128)
        except Exception:
            return ""


def show_message(
    msg,
    msg_type="Information",
    auto_close_time=None,
    yes_no=False,
    q=(False, "", ""),
    title=None,
    styled=True,  # Use styled dialog for errors/warnings
):
    """:param q:
    :param yes_no:
    :param auto_close_time:
    :param msg:
    :param msg_type: Information/Warning/Critical/Question
    :param styled: Use styled dialog for errors/warnings (default True)
    :return:
    """
    # Use styled dialog for errors and warnings (hardware connection messages)
    if styled and not yes_no and not q[0] and auto_close_time is None:
        if msg_type in ("Warning", "Critical"):
            from affilabs.widgets.styled_message_dialog import show_styled_warning, show_styled_error

            # Get parent window if available
            from PySide6.QtWidgets import QApplication
            parent = QApplication.activeWindow()

            # Clean up message text
            clean_msg = _sanitize_ascii(msg)

            if msg_type == "Warning":
                show_styled_warning(parent, title or "Warning", clean_msg)
            else:  # Critical
                show_styled_error(parent, title or "Error", clean_msg)
            return

    # Fallback to original TimerMessageBox for other cases
    m = TimerMessageBox(timeout=auto_close_time, yn=yes_no, q=q, title=title)
    m.setIcon(getattr(m.Icon, msg_type) if hasattr(m.Icon, msg_type) else m.Icon.NoIcon)
    m.setText(_sanitize_ascii(msg))
    m.exec_()
    if m.wait_for_button:
        if m.clickedButton() == m.y_btn:
            return True
        if m.clickedButton() == m.n_btn:
            return False
