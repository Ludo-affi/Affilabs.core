"""Test calibration dialog UI without running full app."""

import sys
from PySide6.QtWidgets import QApplication
from affilabs.dialogs.startup_calib_dialog import StartupCalibProgressDialog

app = QApplication(sys.argv)

# Test message (same as actual calibration dialog)
test_message = (
    "Before starting, please verify:\n\n"
    "✓ Prism installed in sensor holder\n"
    "✓ Water or buffer applied to prism\n"
    "✓ No air bubbles visible\n"
    "✓ Temperature stabilized (10 min after power-on)\n\n"
    "Calibration will run 6 steps.\n"
    "Estimated time: ~5 minutes."
)

# Create dialog
dialog = StartupCalibProgressDialog(
    parent=None,
    title="Calibrating SPR System",
    message=test_message,
    show_start_button=True,
)

dialog.show()
sys.exit(app.exec())
