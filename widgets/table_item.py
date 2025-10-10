from PySide6.QtGui import Qt
from PySide6.QtWidgets import QTableWidgetItem


class CenteredQTableWidgetItem(QTableWidgetItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setTextAlignment(Qt.AlignCenter)
