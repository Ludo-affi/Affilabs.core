"""Test if a simple window can be shown."""

import sys

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

app = QApplication(sys.argv)

window = QMainWindow()
window.setWindowTitle("Test Window")
window.setGeometry(100, 100, 800, 600)
window.setCentralWidget(QLabel("If you see this, Qt is working!"))
window.show()

print("Window should be visible now!")
sys.exit(app.exec())
