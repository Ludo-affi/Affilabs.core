"""Recording Event Coordinator.

Manages all recording-related events including:
- General recording (cycle data recording)
- Baseline data recording (5-minute transmission captures)

This coordinator handles signal routing and UI updates for both recording workflows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main_simplified import Application

from affilabs.utils.logger import logger
from affilabs.widgets.message import show_message


class RecordingEventCoordinator:
    """Coordinates recording-related events and UI updates.

    Handles:
    - General recording lifecycle (start/stop/error)
    - Baseline recording workflow (5-minute captures)
    - LED operation hour tracking
    - Recording state UI updates

    This is a pure coordinator - it routes events and updates UI,
    but does not contain business logic.
    """

    def __init__(self, app: Application):
        """Initialize recording event coordinator.

        Args:
            app: Main application instance for accessing managers and UI

        """
        self.app = app
        self._last_recording_file: str | None = None  # Retained for post-stop prompt

    # =========================================================================
    # GENERAL RECORDING EVENTS (Cycle Data Recording)
    # =========================================================================

    def on_recording_started(self, filename: str):
        """Handle recording started signal.

        Args:
            filename: Path to recording file

        """
        logger.info(f"🎙️ Recording started: {filename}")
        self._last_recording_file = filename  # Retain for post-stop prompt

        # Start tracking LED operation hours
        self.app.main_window.start_led_operation_tracking()

        # Update UI recording indicator with filename
        self.app.main_window.set_recording_state(True, filename)

        # Note: Removed redundant sidebar spectroscopy status update
        # Main recording indicator (rec_status_text) already shows recording state

    def on_recording_stopped(self):
        """Handle recording stopped signal."""
        logger.info("🎙️ Recording stopped")

        # Stop tracking LED operation hours and save to config
        self.app.main_window.stop_led_operation_tracking()

        # Update UI recording indicator
        self.app.main_window.set_recording_state(False)

        # Refresh user progression display so XP count updates immediately
        try:
            sidebar = self.app.main_window.sidebar
            builder = getattr(sidebar, "_settings_builder", None)
            if builder is not None:
                builder._populate_user_list()
                builder._update_progression_display()
        except Exception:
            pass

        # Show inline "Recording saved" toast in the Cycle Intelligence Footer
        self._show_recording_saved_toast()

        # Note: Removed redundant sidebar spectroscopy status update
        # Main recording indicator already handles state display

    def _show_recording_saved_toast(self) -> None:
        """Show inline 'Recording saved' notice in the Cycle Intelligence Footer.

        Replaces the rec-clock area with a clickable green label that navigates
        to the Edits tab. Auto-dismisses after 8 seconds.
        Also shows the full path in the status bar for easy reference.
        """
        import os
        from pathlib import Path
        try:
            saved_file = self._last_recording_file
            display_name = Path(saved_file).name if saved_file else "recording"

            # Show full path in the dedicated rec path label (avoids overlap with REC badge)
            if saved_file and saved_file != "memory":
                try:
                    mw = self.app.main_window
                    lbl = getattr(mw, '_rec_path_label', None)
                    if lbl is not None:
                        lbl.setText(f"Saved: {saved_file}")
                        lbl.setStyleSheet(
                            "color: #34C759; font-size: 12px; margin: 0 8px 0 0; "
                            "font-family: -apple-system, 'Segoe UI', system-ui, sans-serif;"
                        )
                        lbl.show()
                        from PySide6.QtCore import QTimer
                        QTimer.singleShot(30000, lambda: lbl.hide() if not mw.is_recording else None)
                except Exception:
                    pass

            graph = getattr(self.app.main_window, 'cycle_of_interest_graph', None)
            footer = getattr(graph, 'intelligence_footer', None)
            if footer is None:
                return

            def _open_folder():
                try:
                    if saved_file and saved_file != "memory":
                        folder = str(Path(saved_file).parent)
                        os.startfile(folder)
                    else:
                        self.app.main_window.navigation_presenter.switch_page(1)
                except Exception:
                    self.app.main_window.navigation_presenter.switch_page(1)

            footer.show_saved_toast(display_name, on_click=_open_folder)

        except Exception as e:
            logger.warning(f"Could not show post-recording toast: {e}")

    def on_recording_error(self, error: str):
        """Handle recording error signal.

        Args:
            error: Error message

        """
        logger.error(f"Recording error: {error}")
        show_message(error, "Recording Error")

    # =========================================================================
    # BASELINE RECORDING EVENTS (5-Minute Transmission Captures)
    # =========================================================================

    def on_record_baseline_clicked(self):
        """Handle Record Baseline Data button click.

        Manages the baseline recording workflow:
        1. Toggle recording if already active
        2. Initialize BaselineDataRecorder if needed
        3. Confirm with user (5-minute capture)
        4. Start recording
        """
        logger.info("=" * 80)
        logger.info("[User Action] Record Baseline Data button clicked")
        logger.info("=" * 80)

        # Debug: Check data manager state
        logger.info(f"Data manager exists: {self.app.data_mgr is not None}")
        if self.app.data_mgr:
            logger.info(f"Data manager calibrated: {self.app.data_mgr.calibrated}")
            logger.info(f"Data manager acquiring: {self.app.data_mgr._acquiring}")

        # Check if already recording
        if (
            self.app._baseline_recorder is not None
            and self.app._baseline_recorder.is_recording()
        ):
            logger.info("Stopping baseline recording...")
            self.app._baseline_recorder.stop_recording()
            return

        # Create recorder if not exists
        if self.app._baseline_recorder is None:
            if not self.app.data_mgr:
                show_message(
                    "Data acquisition system not initialized.",
                    msg_type="Warning",
                    title="Not Ready",
                )
                return

            from affilabs.utils.baseline_data_recorder import BaselineDataRecorder

            # Pass spectrum_viewmodel to baseline recorder so it can access transmission data
            # The recorder will connect to all 4 channel viewmodels via spectrum_viewmodels dict
            spectrum_viewmodels = getattr(self.app, 'spectrum_viewmodels', None)
            if not spectrum_viewmodels:
                logger.warning("[WARN] spectrum_viewmodels not available - baseline recorder will use fallback mode")

            # Get sidebar reference for export path
            sidebar = getattr(self.app.main_window, 'sidebar', None)

            self.app._baseline_recorder = BaselineDataRecorder(
                self.app.data_mgr,
                spectrum_viewmodels=spectrum_viewmodels,
                sidebar=sidebar,
                parent=self.app.main_window,
            )

            # Connect signals
            self.app._baseline_recorder.recording_started.connect(
                self.on_baseline_recording_started,
            )
            self.app._baseline_recorder.recording_progress.connect(
                self.on_baseline_recording_progress,
            )
            self.app._baseline_recorder.recording_complete.connect(
                self.on_baseline_recording_complete,
            )
            self.app._baseline_recorder.recording_error.connect(
                self.on_baseline_recording_error,
            )
            logger.info("[OK] Baseline recorder initialized and signals connected")

        # Confirm with user
        reply_yes = show_message(
            "This will record 5 minutes of transmission data for noise optimization analysis.\n\n"
            "[WARN] Ensure stable baseline (no sample injections) during recording.\n\n"
            "Continue?",
            msg_type="Question",
            yes_no=True,
            title="Record Baseline Data",
        )
        if reply_yes:
            logger.info("User confirmed - starting 5-minute baseline recording")
            self.app._baseline_recorder.start_recording(duration_minutes=5.0)

    def on_baseline_recording_started(self):
        """Handle baseline recording started signal.

        Updates button appearance to show recording state.
        """
        if hasattr(self.app.main_window, "baseline_capture_btn"):
            self.app.main_window.baseline_capture_btn.setText("Stop Recording")
            self.app.main_window.baseline_capture_btn.setStyleSheet(
                "QPushButton {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF9500, stop:1 #E08000);"
                "  color: white;"
                "  border: none;"
                "  border-radius: 8px;"
                "  padding: 8px 16px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "}"
                "QPushButton:hover {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFA520, stop:1 #F09000);"
                "}"
                "QPushButton:pressed {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E08000, stop:1 #C07000);"
                "}",
            )
        logger.info(
            "🎤 Baseline recording started - button updated to 'Stop Recording'",
        )

    def on_baseline_recording_progress(self, progress: dict):
        """Handle baseline recording progress update.

        Args:
            progress: Dict with 'elapsed', 'remaining', 'count', 'percent' keys

        """
        if hasattr(self.app.main_window, "baseline_capture_btn"):
            percent = progress.get("percent", 0)
            remaining = progress.get("remaining", 0)
            self.app.main_window.baseline_capture_btn.setText(
                f"⏹ Recording... {int(percent)}% ({int(remaining)}s)",
            )

    def on_baseline_recording_complete(self, filepath: str):
        """Handle baseline recording complete signal.

        Args:
            filepath: Path to saved recording file

        """
        # Reset button appearance
        if hasattr(self.app.main_window, "baseline_capture_btn"):
            self.app.main_window.baseline_capture_btn.setText("🎤 Capture 5-Min Baseline")
            self.app.main_window.baseline_capture_btn.setStyleSheet(
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
                "}",
            )

        # Show completion message
        show_message(
            f"[OK] Baseline data successfully recorded!\n\n"
            f"Saved to: {filepath}\n\n"
            f"You can now send this data for offline noise optimization analysis.",
            msg_type="Information",
            title="Recording Complete",
        )
        logger.info(f"[OK] Baseline recording complete - user notified: {filepath}")

    def on_baseline_recording_error(self, error_msg: str):
        """Handle baseline recording error signal.

        Args:
            error_msg: Error description

        """
        # Reset button appearance
        if hasattr(self.app.main_window, "baseline_capture_btn"):
            self.app.main_window.baseline_capture_btn.setText("🎤 Capture 5-Min Baseline")
            self.app.main_window.baseline_capture_btn.setStyleSheet(
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
                "}",
            )

        # Show error message
        show_message(
            f"Failed to record baseline data:\n\n{error_msg}",
            msg_type="Critical",
            title="Recording Error",
        )
        logger.error(f"[X] Baseline recording error - user notified: {error_msg}")

