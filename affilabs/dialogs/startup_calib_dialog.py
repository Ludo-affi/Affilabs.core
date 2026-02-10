"""Startup Calibration Progress Dialog

Extracted from affilabs_core_ui.py for better modularity.

Non-modal progress dialog for calibration with Start button integration.
Thread-safe UI updates via signals.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal, QTimer, QElapsedTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class StartupCalibProgressDialog(QDialog):
    """Non-modal progress dialog for calibration with Start button integration."""

    start_clicked = Signal()  # Signal emitted when Start button is clicked
    retry_clicked = Signal()  # Signal emitted when Retry button is clicked
    continue_anyway_clicked = Signal()  # Signal emitted when Continue Anyway is clicked

    # Internal signals for thread-safe UI updates
    _update_title_signal = Signal(str)
    _update_status_signal = Signal(str)
    _update_step_description_signal = Signal(str)  # Signal for step description updates
    _set_progress_signal = Signal(int, int)  # (value, maximum)
    _hide_progress_signal = Signal()
    _enable_start_signal = Signal()
    _close_signal = Signal()  # Signal for thread-safe close

    def __init__(
        self,
        parent: QWidget | None = None,
        title: str = "Processing",
        message: str = "Please wait...",
        show_start_button: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(False)  # Non-blocking - allows background processing
        self.setMinimumWidth(460)
        self.setMinimumHeight(200)
        self.setMaximumWidth(520)
        self.setMaximumHeight(400)

        # Track dialog state to prevent race conditions
        self._is_closing = False
        self._is_complete = False
        self._is_error_state = False

        # Elapsed time tracking so users see the process is alive
        self._elapsed_timer = QElapsedTimer()
        self._calibration_running = False

        # Store parent for overlay and position tracking
        self.parent_window = parent
        self.overlay = None

        # Create semi-transparent overlay on parent window
        if self.parent_window:
            self.overlay = QWidget(self.parent_window)
            self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 0.5);")
            self.overlay.setGeometry(self.parent_window.rect())
            self.overlay.show()
            self.overlay.raise_()

            # Install event filter to track parent window movements
            self.parent_window.installEventFilter(self)

        # Remove window close button and make it frameless for modern look
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)

        # Style with border and rounded corners
        self.setStyleSheet(
            "QDialog { background: #FFFFFF; border: 2px solid #007AFF; border-radius: 12px; }"
            "QLabel { font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif; color: #1D1D1F; }",
        )

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(10)

        # Title
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            "font-size: 18px;font-weight: 700;color: #1D1D1F;",
        )
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.title_label)

        # Step description label (shows current calibration step)
        self.step_description_label = QLabel("")
        self.step_description_label.setStyleSheet(
            "font-size: 13px; color: #007AFF; font-weight: 600; padding: 4px;",
        )
        self.step_description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.step_description_label.setWordWrap(True)
        self.step_description_label.setVisible(False)  # Hidden until calibration starts
        self.step_description_label.setMinimumHeight(20)
        main_layout.addWidget(self.step_description_label)

        # Progress bar (can be indeterminate or real progress)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)  # Start in indeterminate mode
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(24)
        self.progress_bar.setVisible(False)  # Hidden initially for checklist
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setStyleSheet(
            "QProgressBar {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  border-radius: 4px;"
            "  border: 1px solid #D1D1D6;"
            "  color: #1D1D1F;"
            "  font-size: 12px;"
            "  font-weight: 700;"
            "  text-align: center;"
            "}"
            "QProgressBar::chunk {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007AFF, stop:1 #00C7BE);"
            "  border-radius: 4px;"
            "}",
        )
        main_layout.addWidget(self.progress_bar)

        # Animated activity indicator with elapsed time
        self.activity_label = QLabel("Working...")
        self.activity_label.setStyleSheet(
            "font-size: 14px; color: #007AFF; font-weight: bold; padding: 8px;",
        )
        self.activity_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.activity_label.setFixedHeight(32)
        self.activity_label.setVisible(True)  # Visible from start
        main_layout.addWidget(self.activity_label)

        self._dot_count = 0
        self._dot_timer = QTimer(self)
        self._dot_timer.timeout.connect(self._animate_dots)
        self._dot_timer.start(1000)  # 1s interval for elapsed time ticking

        # Status message
        self.status_label = QLabel(message)
        self.status_label.setStyleSheet(
            "font-size: 14px;color: #86868B;padding: 0px;",
        )
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(30)
        self.status_label.setMaximumHeight(160)
        main_layout.addWidget(self.status_label)

        # Small spacer before buttons
        main_layout.addSpacing(4)

        # Start button (optional, initially disabled if shown)
        self.start_button = None
        self.retry_button = None
        self.continue_button = None
        self.close_button = None

        # Button container for dynamic button switching
        self.button_container = QWidget()
        self.button_layout = QHBoxLayout(self.button_container)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.addStretch()

        if show_start_button:
            self.start_button = QPushButton("Start")
            self.start_button.setEnabled(False)  # Start disabled
            self.start_button.setFixedSize(140, 36)
            self.start_button.setStyleSheet(
                "QPushButton {"
                "  background: #007AFF;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 6px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  padding: 8px 16px;"
                "}"
                "QPushButton:hover {"
                "  background: #0051D5;"
                "}"
                "QPushButton:pressed {"
                "  background: #004FC4;"
                "}"
                "QPushButton:disabled {"
                "  background: #E5E5EA;"
                "  color: #86868B;"
                "}",
            )
            self.start_button.clicked.connect(self._on_start_clicked)
            self.button_layout.addWidget(self.start_button)

        # Add Cancel/Close button (always available)
        self.close_button = QPushButton("Cancel")
        self.close_button.setFixedSize(100, 36)
        self.close_button.setStyleSheet(
            "QPushButton {"
            "  background: #8E8E93;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:hover {"
            "  background: #636366;"
            "}"
        )
        self.close_button.clicked.connect(self.close)
        self.button_layout.addWidget(self.close_button)

        self.button_layout.addStretch()
        main_layout.addWidget(self.button_container)

        # Connect internal signals for thread-safe UI updates
        self._update_title_signal.connect(self._do_update_title)
        self._update_status_signal.connect(self._do_update_status)
        self._update_step_description_signal.connect(self._do_update_step_description)
        self._set_progress_signal.connect(self._do_set_progress)
        self._hide_progress_signal.connect(self._do_hide_progress)
        self._enable_start_signal.connect(self._do_enable_start)
        self._close_signal.connect(self._do_close)

        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        self.setGraphicsEffect(shadow)

        # Center on parent when dialog is initialized
        if self.parent_window:
            self._center_on_parent()

    def _on_start_clicked(self) -> None:
        """Handle start button click."""
        try:
            if not self._is_closing:
                # Check if this is the initial start (pre-calibration) or final start (post-calibration)
                if self._is_complete:
                    # Post-calibration: Emit signal to start acquisition, dialog will close after
                    from affilabs.utils.logger import logger

                    logger.info(
                        "[DIALOG] Start button clicked (post-calibration) - emitting signal",
                    )
                    self.start_clicked.emit()
                    logger.info(
                        "[DIALOG] Signal emitted, dialog will close after acquisition starts",
                    )
                else:
                    # Pre-calibration: Emit signal but keep dialog open for progress updates
                    self.start_clicked.emit()
                    # Dialog stays open to show calibration progress
        except Exception as e:
            from affilabs.utils.logger import logger

            logger.error(f"[ERROR] Error in _on_start_clicked: {e}", exc_info=True)
            import traceback

            try:
                print(traceback.format_exc())
            except:
                pass

    def closeEvent(self, event: Any) -> None:
        """Clean up overlay when dialog closes."""
        self._is_closing = True
        self._dot_timer.stop()

        # Remove event filter
        if self.parent_window:
            try:
                self.parent_window.removeEventFilter(self)
            except RuntimeError:
                pass

        if self.overlay:
            try:
                self.overlay.hide()
                self.overlay.deleteLater()
            except RuntimeError:
                pass  # Widget already deleted
            self.overlay = None
        super().closeEvent(event)

    def eventFilter(self, obj: Any, event: Any) -> bool:
        """Track parent window movements and reposition dialog."""
        if obj == self.parent_window and not self._is_closing:
            if event.type() == event.Type.Move:
                # Recenter dialog on parent
                self._center_on_parent()
            elif event.type() == event.Type.Resize:
                # Update overlay size
                if self.overlay:
                    self.overlay.setGeometry(self.parent_window.rect())
                # Recenter dialog
                self._center_on_parent()
        return super().eventFilter(obj, event)

    def _center_on_parent(self) -> None:
        """Center the dialog on the parent window."""
        if self.parent_window and not self._is_closing:
            parent_geometry = self.parent_window.geometry()
            dialog_width = self.width()
            dialog_height = self.height()

            x = parent_geometry.x() + (parent_geometry.width() - dialog_width) // 2
            y = parent_geometry.y() + (parent_geometry.height() - dialog_height) // 2

            self.move(x, y)

    def update_status(self, message: str) -> None:
        """Update the status message (thread-safe via signal)."""
        self._update_status_signal.emit(message)

    def _do_update_status(self, message: str) -> None:
        """Actually update status label (runs in main thread)."""
        if not self._is_closing and self.isVisible():
            try:
                self.status_label.setText(message)
            except RuntimeError:
                pass  # Widget deleted

    def update_title(self, title: str):
        """Update the title (thread-safe via signal)."""
        self._update_title_signal.emit(title)

    def _do_update_title(self, title: str) -> None:
        """Actually update title (runs in main thread)."""
        if not self._is_closing and self.isVisible():
            try:
                self.title_label.setText(title)
                self.setWindowTitle(title)
            except RuntimeError:
                pass  # Widget deleted

    def update_step_description(self, description: str) -> None:
        """Update the step description label (thread-safe via signal)."""
        self._update_step_description_signal.emit(description)

    def _do_update_step_description(self, description: str) -> None:
        """Actually update step description label (runs in main thread)."""
        if not self._is_closing and self.isVisible():
            try:
                if description:
                    self.step_description_label.setText(description)
                    self.step_description_label.setVisible(True)
                else:
                    self.step_description_label.setVisible(False)
            except RuntimeError:
                pass  # Widget deleted

    def set_progress(self, value: int, maximum: int = 100):
        """Set progress bar to show actual progress (thread-safe)."""
        self._set_progress_signal.emit(value, maximum)

    def _do_set_progress(self, value: int, maximum: int) -> None:
        """Actually set progress (runs in main thread)."""
        if not self._is_closing and self.isVisible():
            try:
                if self.progress_bar.maximum() != maximum:
                    self.progress_bar.setMaximum(maximum)
                    self.progress_bar.setTextVisible(True)

                self.progress_bar.setValue(value)

                # Update text to show percentage
                if maximum > 0:
                    percentage = int((value / maximum) * 100)
                    self.progress_bar.setFormat(f"{percentage}%")
            except RuntimeError:
                pass  # Widget deleted

    def hide_progress_bar(self) -> None:
        """Hide progress bar (thread-safe via signal)."""
        self._hide_progress_signal.emit()

    def _do_hide_progress(self) -> None:
        """Actually hide progress bar (runs in main thread)."""
        if not self._is_closing and self.isVisible():
            try:
                self.progress_bar.hide()
            except RuntimeError:
                pass  # Widget deleted

    def show_progress_bar(self) -> None:
        """Show progress bar and start activity animation (when calibration starts)."""
        if not self._is_closing and self.isVisible():
            try:
                self.progress_bar.show()
                self.progress_bar.setMaximum(100)
                self.progress_bar.setValue(0)
                self.activity_label.setVisible(True)
                self._calibration_running = True
                self._elapsed_timer.start()
                self._dot_timer.start(1000)
            except RuntimeError:
                pass  # Widget deleted

    def _animate_dots(self) -> None:
        """Cycle dots and show elapsed time so users see the process is alive."""
        self._dot_count = (self._dot_count % 3) + 1
        dots = "." * self._dot_count
        if self._calibration_running:
            elapsed_ms = self._elapsed_timer.elapsed()
            total_secs = elapsed_ms // 1000
            mins = total_secs // 60
            secs = total_secs % 60
            if mins > 0:
                elapsed_str = f"{mins}m {secs:02d}s"
            else:
                elapsed_str = f"{secs}s"
            self.activity_label.setText(f"Calibrating{dots}  ({elapsed_str} elapsed)")
        else:
            self.activity_label.setText(f"Working{dots}")

    def _stop_activity_animation(self) -> None:
        """Stop the dot animation and elapsed time tracking."""
        self._dot_timer.stop()
        self._calibration_running = False
        self.activity_label.setVisible(False)

    def enable_start_button_pre_calib(self) -> None:
        """Enable the Start button for pre-calibration checklist (thread-safe)."""
        from affilabs.utils.logger import logger

        logger.debug(
            f"[DIALOG] enable_start_button_pre_calib() called: _is_complete={self._is_complete}",
        )
        if not self._is_closing and self.isVisible() and self.start_button:
            try:
                self._is_error_state = False
                self.start_button.setEnabled(True)
                logger.debug(
                    f"[DIALOG] Button enabled, _is_complete={self._is_complete} (should be False)",
                )
            except RuntimeError:
                pass  # Widget deleted

    def enable_start_button(self) -> None:
        """Enable the Start button when calibration is complete (thread-safe via signal)."""
        self._enable_start_signal.emit()

    def _do_enable_start(self) -> None:
        """Actually enable start button (runs in main thread)."""
        if not self._is_closing and self.isVisible() and self.start_button:
            try:
                self._is_complete = True
                self._is_error_state = False
                self.start_button.setEnabled(True)
            except RuntimeError:
                pass  # Widget deleted

    def hide_start_button(self) -> None:
        """Hide the Start button (called when calibration starts)."""
        if self.start_button:
            try:
                self.start_button.setVisible(False)
            except RuntimeError:
                pass  # Widget deleted

    def show_error_state(
        self,
        error_message: str,
        retry_count: int,
        max_retries: int,
    ) -> None:
        """Switch dialog to error state with Retry/Continue buttons."""
        if self._is_closing or not self.isVisible():
            return

        try:
            self._is_error_state = True
            self._is_complete = False

            # Update title and status
            self.title_label.setText("[WARN] Calibration Failed")
            self.title_label.setStyleSheet(
                "font-size: 18px;"
                "font-weight: 700;"
                "color: #FF3B30;",  # Red color for error
            )

            retries_left = max_retries - retry_count
            full_message = f"{error_message}\n\nRetries remaining: {retries_left}"
            self.status_label.setText(full_message)

            # Hide Start button if it exists
            if self.start_button:
                self.start_button.hide()

            # Create Retry and Continue buttons if they don't exist
            if not self.retry_button:
                self.retry_button = QPushButton("Retry Calibration")
                self.retry_button.setFixedSize(160, 36)
                self.retry_button.setStyleSheet(
                    "QPushButton {"
                    "  background: #007AFF;"
                    "  color: white;"
                    "  border: none;"
                    "  border-radius: 6px;"
                    "  font-size: 13px;"
                    "  font-weight: 600;"
                    "}"
                    "QPushButton:hover {"
                    "  background: #0051D5;"
                    "}",
                )
                self.retry_button.clicked.connect(self._on_retry_clicked)
                self.button_layout.insertWidget(1, self.retry_button)

            if not self.continue_button:
                self.continue_button = QPushButton("Continue Anyway")
                self.continue_button.setFixedSize(160, 36)
                self.continue_button.setStyleSheet(
                    "QPushButton {"
                    "  background: #FF9500;"
                    "  color: white;"
                    "  border: none;"
                    "  border-radius: 6px;"
                    "  font-size: 13px;"
                    "  font-weight: 600;"
                    "}"
                    "QPushButton:hover {"
                    "  background: #FF8000;"
                    "}",
                )
                self.continue_button.clicked.connect(self._on_continue_clicked)
                self.button_layout.insertWidget(2, self.continue_button)

            self.retry_button.show()
            self.continue_button.show()

        except RuntimeError:
            pass  # Widget deleted

    def show_max_retries_error(self, error_message: str):
        """Show error state when max retries reached - only Continue button."""
        if self._is_closing or not self.isVisible():
            return

        try:
            self._is_error_state = True

            # Update title and status
            self.title_label.setText("[ERROR] Calibration Failed")
            self.status_label.setText(
                f"{error_message}\n\nMaximum retry attempts reached.\nPlease contact technical support.",
            )

            # Hide Start and Retry buttons
            if self.start_button:
                self.start_button.hide()
            if self.retry_button:
                self.retry_button.hide()

            # Show only Continue button
            if not self.continue_button:
                self.continue_button = QPushButton("Continue Anyway")
                self.continue_button.setFixedSize(160, 36)
                self.continue_button.setStyleSheet(
                    "QPushButton {"
                    "  background: #FF9500;"
                    "  color: white;"
                    "  border: none;"
                    "  border-radius: 6px;"
                    "  font-size: 13px;"
                    "  font-weight: 600;"
                    "}"
                    "QPushButton:hover {"
                    "  background: #FF8000;"
                    "}",
                )
                self.continue_button.clicked.connect(self._on_continue_clicked)
                self.button_layout.insertWidget(1, self.continue_button)

            self.continue_button.show()

        except RuntimeError:
            pass  # Widget deleted

    def reset_to_progress_state(self):
        """Reset dialog back to progress state (for retry)."""
        if self._is_closing or not self.isVisible():
            return

        try:
            self._is_error_state = False
            self._is_complete = False

            # Reset title color
            self.title_label.setStyleSheet(
                "font-size: 18px;font-weight: 700;color: #1D1D1F;",
            )

            # Hide error buttons
            if self.retry_button:
                self.retry_button.hide()
            if self.continue_button:
                self.continue_button.hide()

            # Reset progress bar
            self.progress_bar.setValue(0)

        except RuntimeError:
            pass  # Widget deleted

    def _on_retry_clicked(self) -> None:
        """Handle retry button click."""
        if not self._is_closing:
            self.retry_clicked.emit()

    def _on_continue_clicked(self) -> None:
        """Handle continue anyway button click."""
        if not self._is_closing:
            self.continue_anyway_clicked.emit()

    def close_from_thread(self) -> None:
        """Close dialog from background thread (thread-safe via signal)."""
        self._close_signal.emit()

    def _do_close(self) -> None:
        """Actually close dialog (runs in main thread)."""
        if not self._is_closing:
            try:
                self.close()
            except RuntimeError:
                pass  # Widget already deleted
