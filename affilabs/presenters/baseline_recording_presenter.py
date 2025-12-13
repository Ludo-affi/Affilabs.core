"""Baseline Recording Presenter

Manages UI state and interactions for baseline data recording.
Extracted from affilabs_core_ui.py for better modularity.
"""

from typing import Dict, Optional
from PySide6.QtWidgets import QMessageBox
from affilabs.utils.logger import logger
from affilabs.utils.baseline_data_recorder import BaselineDataRecorder


class BaselineRecordingPresenter:
    """Presents baseline recording state and handles user interactions."""

    def __init__(self, main_window):
        """Initialize the baseline recording presenter.

        Args:
            main_window: Reference to the main window (AffilabsMainWindow)
        """
        self.main_window = main_window
        self._baseline_recorder: Optional[BaselineDataRecorder] = None

    def handle_record_baseline(self) -> None:
        """Handle Record Baseline Data button click."""
        logger.info("Record Baseline Data button clicked")

        if not hasattr(self.main_window, 'app') or not self.main_window.app:
            logger.warning("Application not connected")
            return

        # Check if already recording
        if self._baseline_recorder and self._baseline_recorder.is_recording():
            logger.info("Stopping baseline recording...")
            self._baseline_recorder.stop_recording()
            return

        # Create recorder if not exists
        if not self._baseline_recorder:
            # Get data manager (try both attribute names for compatibility)
            data_mgr = None
            if hasattr(self.main_window, 'app') and self.main_window.app:
                data_mgr = getattr(self.main_window.app, 'data_mgr', None) or getattr(
                    self.main_window.app, 'data_acquisition', None
                )

            if not data_mgr:
                QMessageBox.warning(
                    self.main_window, "Not Ready", "Data acquisition system not initialized."
                )
                return

            self._baseline_recorder = BaselineDataRecorder(data_mgr, parent=self.main_window)

            # Connect signals
            self._baseline_recorder.recording_started.connect(self.on_recording_started)
            self._baseline_recorder.recording_progress.connect(self.on_recording_progress)
            self._baseline_recorder.recording_complete.connect(self.on_recording_complete)
            self._baseline_recorder.recording_error.connect(self.on_recording_error)

        # Confirm with user
        reply = QMessageBox.question(
            self.main_window,
            "Record Baseline Data",
            "This will record 5 minutes of transmission data for noise optimization analysis.\n\n"
            "⚠️ Ensure stable baseline (no sample injections) during recording.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._baseline_recorder.start_recording(duration_minutes=5.0)

    def on_recording_started(self) -> None:
        """Handle recording started signal - update button to show stop state."""
        if hasattr(self.main_window, 'baseline_capture_btn'):
            self.main_window.baseline_capture_btn.setText("⏹️ Stop Capture")
            self.main_window.baseline_capture_btn.setStyleSheet(
                "QPushButton {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF9500, stop:1 #E08000);"
                "  color: white;"
                "  border: none;"
                "  border-radius: 8px;"
                "  padding: 8px 16px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFA520, stop:1 #F09000);"
                "}"
                "QPushButton:pressed {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E08000, stop:1 #C07000);"
                "}"
            )
        logger.info("📊 Baseline recording started")

    def on_recording_progress(self, progress: Dict) -> None:
        """Handle recording progress update - update button text with progress."""
        elapsed = progress['elapsed']
        remaining = progress['remaining']
        count = progress['count']
        percent = progress['percent']

        if hasattr(self.main_window, 'baseline_capture_btn'):
            self.main_window.baseline_capture_btn.setText(
                f"⏹️ Capturing... {int(percent)}% ({int(remaining)}s)"
            )

    def on_recording_complete(self, filepath: str) -> None:
        """Handle recording complete signal - reset button and show success message."""
        if hasattr(self.main_window, 'baseline_capture_btn'):
            self.main_window.baseline_capture_btn.setText("🔴 Record 5-Min Baseline Data")
            self.main_window.baseline_capture_btn.setStyleSheet(
                "QPushButton {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF3B30, stop:1 #E02020);"
                "  color: white;"
                "  border: none;"
                "  border-radius: 8px;"
                "  padding: 8px 16px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF4D42, stop:1 #F03030);"
                "}"
                "QPushButton:pressed {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E02020, stop:1 #C01818);"
                "}"
                "QPushButton:disabled {"
                "  background: #D1D1D6;"
                "  color: #86868B;"
                "}"
            )

        QMessageBox.information(
            self.main_window,
            "Recording Complete",
            f"✅ Baseline data successfully recorded!\n\n"
            f"Saved to: {filepath}\n\n"
            f"You can now send this data for offline noise optimization analysis.",
        )
        logger.info(f"✅ Baseline recording complete: {filepath}")

    def on_recording_error(self, error_msg: str) -> None:
        """Handle recording error signal - reset button and show error message."""
        if hasattr(self.main_window, 'baseline_capture_btn'):
            self.main_window.baseline_capture_btn.setText("🔴 Record 5-Min Baseline Data")
            self.main_window.baseline_capture_btn.setStyleSheet(
                "QPushButton {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF3B30, stop:1 #E02020);"
                "  color: white;"
                "  border: none;"
                "  border-radius: 8px;"
                "  padding: 8px 16px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF4D42, stop:1 #F03030);"
                "}"
                "QPushButton:pressed {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E02020, stop:1 #C01818);"
                "}"
                "QPushButton:disabled {"
                "  background: #D1D1D6;"
                "  color: #86868B;"
                "}"
            )

        QMessageBox.critical(
            self.main_window, "Recording Error", f"❌ Baseline recording failed:\n\n{error_msg}"
        )
        logger.error(f"❌ Baseline recording error: {error_msg}")
