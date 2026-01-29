"""Spectroscopy Presenter - Manages transmission and raw spectrum plot updates.

Encapsulates the display logic for real-time spectroscopy data visualization.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from affilabs.utils.detector_config import filter_valid_wavelength_data
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

        # Detector info for wavelength filtering (prevents noisy data display)
        self._detector_serial = None
        self._detector_type = None

    def set_detector_info(self, detector_serial=None, detector_type=None):
        """Update detector information for wavelength filtering.

        Critical for Phase Photonics detector which has noisy data below 570nm.

        Args:
            detector_serial: Detector serial number
            detector_type: Detector type string
        """
        self._detector_serial = detector_serial
        self._detector_type = detector_type
        logger.info(f"[FILTER DEBUG] Spectroscopy presenter detector info set: serial={detector_serial}, type={detector_type}")

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
                logger.debug(
                    f"Spectroscopy plots available: "
                    f"transmission={len(self.main_window.transmission_curves)}, "
                    f"raw={len(self.main_window.raw_data_curves)}"
                )

        if has_trans and has_raw:
            logger.debug(
                f"✓ Spectroscopy plots: transmission={len(self.main_window.transmission_curves)}, raw={len(self.main_window.raw_data_curves)}",
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

            # CRITICAL: Filter out invalid wavelength data for Phase Photonics detector
            # Phase Photonics has noisy data below 570nm that causes artifacts
            if channel not in self._first_update_logged:
                logger.info(f"[FILTER DEBUG] Before filter: {len(wavelengths)} pts, {wavelengths[0]:.1f}-{wavelengths[-1]:.1f}nm, detector_serial={self._detector_serial}, detector_type={self._detector_type}")

            filtered_wavelengths, filtered_transmission = filter_valid_wavelength_data(
                wavelengths,
                transmission,
                detector_serial=self._detector_serial,
                detector_type=self._detector_type,
            )

            if channel not in self._first_update_logged:
                logger.info(f"[FILTER DEBUG] After filter: {len(filtered_wavelengths)} pts, {filtered_wavelengths[0]:.1f}-{filtered_wavelengths[-1]:.1f}nm")

            # Update curve (try direct access first, fallback to sidebar method)
            if hasattr(self.main_window, "transmission_curves"):
                self.main_window.transmission_curves[channel_idx].setData(
                    filtered_wavelengths,
                    filtered_transmission,
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
                # Fallback: use sidebar API (already filtered above)
                self.main_window.sidebar.update_transmission_plot(
                    channel,
                    filtered_wavelengths,
                    filtered_transmission,
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

            # Track first update (logging disabled)
            if channel not in self._first_update_logged:
                self._first_update_logged.add(channel)

            # CRITICAL: Filter out invalid wavelength data for Phase Photonics detector
            # Phase Photonics has noisy data below 570nm that causes artifacts
            filtered_wavelengths, filtered_raw = filter_valid_wavelength_data(
                wavelengths,
                raw_spectrum,
                detector_serial=self._detector_serial,
                detector_type=self._detector_type,
            )

            # Update curve (try direct access first, fallback to sidebar method)
            if hasattr(self.main_window, "raw_data_curves"):
                # CRITICAL: raw_data_curves is a list indexed 0-3, so channel_idx must match
                if channel_idx < len(self.main_window.raw_data_curves):
                    self.main_window.raw_data_curves[channel_idx].setData(
                        filtered_wavelengths,
                        filtered_raw,
                    )
                else:
                    logger.error(
                        f"Channel index {channel_idx} out of range for raw_data_curves (len={len(self.main_window.raw_data_curves)})",
                    )
            elif hasattr(self.main_window, "sidebar") and hasattr(
                self.main_window.sidebar,
                "update_raw_data_plot",
            ):
                # Fallback: use sidebar API (already filtered above)
                self.main_window.sidebar.update_raw_data_plot(
                    channel,
                    filtered_wavelengths,
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
