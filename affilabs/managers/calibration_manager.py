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
        """Handle Simple LED Calibration button click."""
        logger.info("Simple LED Calibration button clicked")
        # Emit signal to trigger calibration via application
        if hasattr(self.main_window, "app") and self.main_window.app:
            self.main_window.app.calibration.start_calibration()
        else:
            logger.warning("Application not connected - cannot start calibration")

    def handle_full_calibration(self) -> None:
        """Handle Full Calibration button click."""
        logger.info("Full Calibration button clicked")
        # Emit signal to trigger full calibration via application
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

    def handle_oem_led_calibration(self) -> None:
        """Handle OEM LED Calibration button click."""
        logger.info("OEM LED Calibration button clicked")
        # Emit signal to trigger OEM calibration via application
        if hasattr(self.main_window, "app") and self.main_window.app:
            self.main_window.app.calibration.start_calibration()
        else:
            logger.warning("Application not connected - cannot start calibration")
