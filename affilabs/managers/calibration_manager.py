"""Calibration Manager

Manages calibration workflow delegation to application layer.
Extracted from affilabs_core_ui.py for better modularity.
"""

from affilabs.utils.logger import logger


class CalibrationManager:
    """Manages calibration workflows by delegating to application layer."""

    def __init__(self, main_window):
        """Initialize the calibration manager.

        Args:
            main_window: Reference to the main window (AffilabsMainWindow)

        """
        self.main_window = main_window

    def handle_simple_led_calibration(self) -> None:
        """Handle Simple LED Calibration button click - quick intensity adjustment."""
        logger.info("Simple LED Calibration button clicked")
        # Forward to application's simple calibration handler
        if (
            hasattr(self.main_window, "app")
            and self.main_window.app
            and hasattr(self.main_window.app, "_on_simple_led_calibration")
        ):
            self.main_window.app._on_simple_led_calibration()
        else:
            logger.warning("Application not connected - cannot start calibration")

    def handle_full_calibration(self) -> None:
        """Handle Full Calibration button click - 6-step system calibration with dialog."""
        logger.info("Full Calibration button clicked")
        # Forward to application's calibration service (shows dialog with Start button)
        if hasattr(self.main_window, "app") and self.main_window.app:
            self.main_window.app.calibration.start_calibration()
        else:
            logger.warning("Application not connected - cannot start calibration")

    def handle_polarizer_calibration(self) -> None:
        """Handle Polarizer Calibration button click."""
        logger.info("Polarizer Calibration button clicked")
        # Forward to application's polarizer calibration handler
        if (
            hasattr(self.main_window, "app")
            and self.main_window.app
            and hasattr(self.main_window.app, "_on_polarizer_calibration")
        ):
            self.main_window.app._on_polarizer_calibration()
        else:
            logger.warning(
                "Application not connected or polarizer calibration not available",
            )

    # OEM LED Calibration: Button directly connected to Application._on_oem_led_calibration() in main.py
    # No intermediate manager method needed - direct connection is cleaner
