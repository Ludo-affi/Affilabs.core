"""Minimal test of the actual app structure."""
import sys
from pathlib import Path

# Add Old software to path
old_software = Path(__file__).parent / "Old software"
sys.path.insert(0, str(old_software))

from PySide6.QtWidgets import QApplication, QMainWindow, QLabel
from PySide6.QtCore import QObject

class MinimalApp(QObject):
    def __init__(self):
        super().__init__()
        self.main_window = QMainWindow()
        self.main_window.setWindowTitle("Minimal Test")
        self.main_window.setGeometry(100, 100, 800, 600)
        self.main_window.setCentralWidget(QLabel("Minimal app working!"))

app = QApplication(sys.argv)
minimal = MinimalApp()
minimal.main_window.show()
print("Window shown!")
sys.exit(app.exec())
