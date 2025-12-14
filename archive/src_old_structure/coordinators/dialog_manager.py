"""
Dialog Manager

Manages all application dialog windows with lazy loading.
Centralizes dialog lifecycle management and reduces code duplication.

Responsibilities:
- Lazy-load dialogs on first access
- Track dialog instances
- Provide convenience methods for showing dialogs
- Cleanup all dialogs on shutdown
"""

import logging

logger = logging.getLogger(__name__)


class DialogManager:
    """Manages all dialog windows with lazy loading."""

    def __init__(self, main_window):
        """Initialize dialog manager.

        Args:
            main_window: Main window instance (parent for dialogs)
        """
        self.main_window = main_window
        self._dialogs = {}
        logger.info("✅ DialogManager initialized")

    def get_transmission_dialog(self):
        """Get or create transmission spectrum dialog.

        Returns:
            TransmissionSpectrumDialog instance
        """
        if 'transmission' not in self._dialogs:
            from transmission_spectrum_dialog import TransmissionSpectrumDialog
            self._dialogs['transmission'] = TransmissionSpectrumDialog(self.main_window)
            logger.info("✅ Transmission dialog created (lazy-loaded)")
        return self._dialogs['transmission']

    def get_live_data_dialog(self):
        """Get or create live data dialog.

        Returns:
            LiveDataDialog instance
        """
        if 'live_data' not in self._dialogs:
            from live_data_dialog import LiveDataDialog
            self._dialogs['live_data'] = LiveDataDialog(parent=self.main_window)
            logger.info("✅ Live data dialog created (lazy-loaded)")
        return self._dialogs['live_data']

    def show_transmission_dialog(self):
        """Show the transmission spectrum dialog."""
        dialog = self.get_transmission_dialog()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        logger.debug("Transmission dialog shown")

    def show_live_data_dialog(self):
        """Show the live data dialog."""
        dialog = self.get_live_data_dialog()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        logger.debug("Live data dialog shown")

    def hide_live_data_dialog(self):
        """Hide the live data dialog."""
        if 'live_data' in self._dialogs:
            self._dialogs['live_data'].hide()
            logger.debug("Live data dialog hidden")

    def is_transmission_dialog_visible(self) -> bool:
        """Check if transmission dialog is visible."""
        if 'transmission' not in self._dialogs:
            return False
        return self._dialogs['transmission'].isVisible()

    def is_live_data_dialog_visible(self) -> bool:
        """Check if live data dialog is visible."""
        if 'live_data' not in self._dialogs:
            return False
        return self._dialogs['live_data'].isVisible()

    def cleanup_all(self):
        """Cleanup all dialogs on shutdown."""
        for name, dialog in self._dialogs.items():
            try:
                dialog.close()
                logger.debug(f"Closed {name} dialog")
            except Exception as e:
                logger.warning(f"Failed to close {name} dialog: {e}")

        self._dialogs.clear()
        logger.info("All dialogs cleaned up")
