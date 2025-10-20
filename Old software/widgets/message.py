from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QMessageBox
from PySide6.QtGui import QIcon
from ui import ai_rc


class TimerMessageBox(QMessageBox):

    def __init__(self, timeout=None, parent=None, yn=False, q=(False, '', '')):
        super(TimerMessageBox, self).__init__(parent)
        self.setWindowTitle("Affinite Instruments")
        self.setWindowIcon(QIcon(":/img/img/affinite2.ico"))
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        if yn:
            self.y_btn = self.addButton('Yes', QMessageBox.ButtonRole.AcceptRole)
            self.n_btn = self.addButton('No', QMessageBox.ButtonRole.RejectRole)
            self.wait_for_button = True
        elif q[0]:
            self.y_btn = self.addButton(q[1], QMessageBox.ButtonRole.AcceptRole)
            self.n_btn = self.addButton(q[2], QMessageBox.ButtonRole.RejectRole)
            self.wait_for_button = True
        else:
            self.wait_for_button = False

        if timeout is not None:
            self.timer = QTimer(self)
            self.timer.setInterval(timeout * 1000)
            self.timer.timeout.connect(self._on_timeout)
            self.timer.start()

    def _on_timeout(self):
        self.timer.stop()
        self.close()

    def closeEvent(self, event):
        if hasattr(self, 'timer'):
            self.timer.stop()
        event.accept()


def show_message(msg, msg_type='Information', auto_close_time=None, yes_no=False, q=(False, '', '')):
    """
    :param q:
    :param yes_no:
    :param auto_close_time:
    :param msg:
    :param msg_type: Information/Warning/Critical/Question
    :return:
    """
    m = TimerMessageBox(timeout=auto_close_time, yn=yes_no, q=q)
    m.setIcon(getattr(m.Icon, msg_type) if hasattr(m.Icon, msg_type) else m.Icon.NoIcon)
    m.setText(msg)
    m.exec_()
    if m.wait_for_button:
        if m.clickedButton() == m.y_btn:
            return True
        elif m.clickedButton() == m.n_btn:
            return False
