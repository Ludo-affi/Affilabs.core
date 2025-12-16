"""Spectroscopy Presenter - Manages transmission and raw spectrum plot updates.

Encapsulates the display logic for real-time spectroscopy data visualization.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from affilabs.utils.logger import logger


class SpectroscopyPresenter:
    """Presenter for transmission and raw data spectrum plots.

    Handles updating PyQtGraph curves with spectroscopy data, including
    transmission percentages and raw intensity spectra.
    """

    def __init__(self, main_window):
        """Initialize spectroscopy presenter.

        Args:
            main_window: Main window reference with transmission_curves and raw_data_curves

        """
        self.main_window = main_window
        self._plots_available = False
        self._plots_check_logged = False
        self._first_update_logged = set()

        # Channel index mapping
        self._channel_to_idx = {"a": 0, "b": 1, "c": 2, "d": 3}

    def check_plots_available(self):
        """Check if spectroscopy plots are available in main window.

        Returns:
            bool: True if both transmission and raw data plots exist

        """
        if self._plots_check_logged:
            return self._plots_available

        has_trans = hasattr(self.main_window, "transmission_curves")
        has_raw = hasattr(self.main_window, "raw_data_curves")

        if not self._plots_check_logged:
            # Log plot availability once only
            if has_trans and has_raw:
                logger.info(
                    f"Spectroscopy plots available: "
                    f"transmission={len(self.main_window.transmission_curves)}, "
                    f"raw={len(self.main_window.raw_data_curves)}"
                )

        if has_trans and has_raw:
            logger.info(
                f"[OK] Spectroscopy plots found: transmission={len(self.main_window.transmission_curves)} curves, raw={len(self.main_window.raw_data_curves)} curves",
            )
            self._plots_available = True
        else:
            logger.warning(
                f"[!] Spectroscopy plots NOT found: transmission={has_trans}, raw={has_raw}",
            )
            self._plots_available = False

        self._plots_check_logged = True
        return self._plots_available

    def update_transmission(
        self,
        channel: str,
        wavelengths: np.ndarray,
        transmission: np.ndarray,
    ):
        """Update transmission spectrum for a specific channel.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            wavelengths: Wavelength array in nm
            transmission: Transmission percentage array (0-100)

        """
        if channel not in self._channel_to_idx:
            logger.warning(f"Invalid channel: {channel}")
            return

        try:
            channel_idx = self._channel_to_idx[channel]

            # Log first update per channel for diagnostics (INFO level only)
            if channel not in self._first_update_logged:
                logger.info(
                    f"First transmission update: Ch {channel.upper()} - "
                    f"{len(wavelengths)} pts, {wavelengths[0]:.1f}-{wavelengths[-1]:.1f}nm, "
                    f"range {np.min(transmission):.1f}-{np.max(transmission):.1f}%"
                )
                self._first_update_logged.add(channel)

            # Update curve (try direct access first, fallback to sidebar method)
            if hasattr(self.main_window, "transmission_curves"):
                self.main_window.transmission_curves[channel_idx].setData(
                    wavelengths,
                    transmission,
                )
                if not self._plots_available:
                    logger.info(
                        f"[OK] First transmission update for channel {channel.upper()}",
                    )
                    self._plots_available = True
            elif hasattr(self.main_window, "sidebar") and hasattr(
                self.main_window.sidebar,
                "update_transmission_plot",
            ):
                # Fallback: use sidebar API
                self.main_window.sidebar.update_transmission_plot(
                    channel,
                    wavelengths,
                    transmission,
                )

        except Exception as e:
            logger.warning(f"Transmission curve update failed for {channel}: {e}")

    def update_raw_spectrum(
        self,
        channel: str,
        wavelengths: np.ndarray,
        raw_spectrum: np.ndarray,
    ):
        """Update raw intensity spectrum for a specific channel.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            wavelengths: Wavelength array in nm
            raw_spectrum: Raw intensity array (counts)

        """
        if channel not in self._channel_to_idx:
            logger.warning(f"Invalid channel: {channel}")
            return

        try:
            channel_idx = self._channel_to_idx[channel]

            # Log first update for debugging
            if channel not in self._first_update_logged:
                logger.info(
                    f"First raw spectrum update for channel {channel}: {len(raw_spectrum)} points",
                )
                self._first_update_logged.add(channel)

            # Update curve (try direct access first, fallback to sidebar method)
            if hasattr(self.main_window, "raw_data_curves"):
                # CRITICAL: raw_data_curves is a list indexed 0-3, so channel_idx must match
                if channel_idx < len(self.main_window.raw_data_curves):
                    self.main_window.raw_data_curves[channel_idx].setData(
                        wavelengths,
                        raw_spectrum,
                    )
                else:
                    logger.error(
                        f"Channel index {channel_idx} out of range for raw_data_curves (len={len(self.main_window.raw_data_curves)})",
                    )
            elif hasattr(self.main_window, "sidebar") and hasattr(
                self.main_window.sidebar,
                "update_raw_data_plot",
            ):
                # Fallback: use sidebar API
                self.main_window.sidebar.update_raw_data_plot(
                    channel,
                    wavelengths,
                    raw_spectrum,
                )

        except Exception as e:
            logger.exception(
                f"Error updating raw spectrum for {channel}: {e}",
            )

    def clear_transmission(self, channel: str = None):
        """Clear transmission plot for specific channel or all channels.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd') or None for all

        """
        try:
            if channel is None:
                # Clear all channels
                if hasattr(self.main_window, "transmission_curves"):
                    for curve in self.main_window.transmission_curves:
                        curve.clear()
            # Clear specific channel
            elif channel in self._channel_to_idx and hasattr(
                self.main_window,
                "transmission_curves",
            ):
                channel_idx = self._channel_to_idx[channel]
                self.main_window.transmission_curves[channel_idx].clear()
        except Exception as e:
            logger.warning(f"Failed to clear transmission plot: {e}")

    def clear_raw_spectrum(self, channel: str = None):
        """Clear raw spectrum plot for specific channel or all channels.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd') or None for all

        """
        try:
            if channel is None:
                # Clear all channels
                if hasattr(self.main_window, "raw_data_curves"):
                    for curve in self.main_window.raw_data_curves:
                        curve.clear()
            # Clear specific channel
            elif channel in self._channel_to_idx and hasattr(
                self.main_window,
                "raw_data_curves",
            ):
                channel_idx = self._channel_to_idx[channel]
                self.main_window.raw_data_curves[channel_idx].clear()
        except Exception as e:
            logger.warning(f"Failed to clear raw spectrum plot: {e}")

    def clear_all(self):
        """Clear all spectroscopy plots."""
        self.clear_transmission()
        self.clear_raw_spectrum()
        self._first_update_logged.clear()
