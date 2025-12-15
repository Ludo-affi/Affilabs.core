"""UI Update Coordinator

Manages all UI update operations with throttling and batching.
Separates UI update logic from Application class.

Responsibilities:
- Queue UI updates from acquisition/processing threads
- Batch updates at controlled rate (10 Hz)
- Update transmission spectrum curves
- Update Sensor IQ diagnostic displays
- Prevent UI blocking from excessive updates
"""

import logging

import numpy as np
from PySide6.QtCore import QObject, QTimer

logger = logging.getLogger(__name__)


class UIUpdateCoordinator(QObject):
    """Coordinates throttled UI updates for live data display."""

    def __init__(self, app, main_window):
        """Initialize UI update coordinator.

        Args:
            app: Application instance
            main_window: Main window instance with UI widgets

        """
        super().__init__()
        self.app = app
        self.main_window = main_window

        # Pending transmission updates (queued from acquisition thread)
        self._pending_transmission_updates = {
            "a": None,
            "b": None,
            "c": None,
            "d": None,
        }

        # Pending sensor IQ updates
        self._pending_sensor_iq_updates = {}

        # Channel index mapping for array access
        self._channel_to_idx = {"a": 0, "b": 1, "c": 2, "d": 3}

        # Setup throttled update timer (10 Hz = 100ms)
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self.process_pending_updates)
        self._update_timer.start(100)  # 10 FPS

        # Update flags
        self._transmission_updates_enabled = True
        self._raw_spectrum_updates_enabled = True

        logger.info("✅ UIUpdateCoordinator initialized (10 Hz update rate)")

    def queue_transmission_update(
        self,
        channel: str,
        wavelengths: np.ndarray,
        transmission: np.ndarray,
        raw_spectrum: np.ndarray | None = None,
    ):
        """Queue transmission curve update for batch processing.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            wavelengths: Wavelength array (nm)
            transmission: Transmission spectrum (%)
            raw_spectrum: Optional raw intensity data

        """
        self._pending_transmission_updates[channel] = {
            "wavelengths": wavelengths,
            "transmission": transmission,
            "raw_spectrum": raw_spectrum,
        }

    def queue_sensor_iq_update(self, channel: str, sensor_iq):
        """Queue Sensor IQ diagnostic display update.

        Args:
            channel: Channel identifier
            sensor_iq: SensorIQMetrics object

        """
        self._pending_sensor_iq_updates[channel] = sensor_iq

    def process_pending_updates(self):
        """Process all queued UI updates in batch (called by timer)."""
        try:
            # Process transmission curve updates
            if self._transmission_updates_enabled:
                self._update_transmission_curves()

            # Process Sensor IQ diagnostic updates
            self._update_sensor_iq_displays()

        except Exception as e:
            logger.exception(f"Error in UI update coordinator: {e}")

    def _update_transmission_curves(self):
        """Update transmission spectrum curves from pending queue."""
        for channel, update_data in self._pending_transmission_updates.items():
            if update_data is None:
                continue

            try:
                channel_idx = self._channel_to_idx[channel]
                wavelengths = update_data["wavelengths"]
                transmission = update_data["transmission"]
                raw_spectrum = update_data.get("raw_spectrum")

                # Update transmission curve
                if self._transmission_updates_enabled and hasattr(
                    self.main_window,
                    "transmission_curves",
                ):
                    try:
                        self.main_window.transmission_curves[channel_idx].setData(
                            wavelengths,
                            transmission,
                        )
                    except Exception as e:
                        logger.debug(
                            f"Transmission curve update failed for {channel}: {e}",
                        )

                # Update raw spectrum curve
                if (
                    self._raw_spectrum_updates_enabled
                    and raw_spectrum is not None
                    and hasattr(self.main_window, "raw_data_curves")
                ):
                    try:
                        self.main_window.raw_data_curves[channel_idx].setData(
                            wavelengths,
                            raw_spectrum,
                        )
                    except Exception as e:
                        logger.debug(
                            f"Raw spectrum curve update failed for {channel}: {e}",
                        )

            except Exception as e:
                logger.warning(f"Failed to update curves for channel {channel}: {e}")

        # Clear processed updates
        self._pending_transmission_updates = {
            "a": None,
            "b": None,
            "c": None,
            "d": None,
        }

    def _update_sensor_iq_displays(self):
        """Update Sensor IQ diagnostic displays from pending queue."""
        if not self._pending_sensor_iq_updates:
            return

        try:
            from utils.sensor_iq import (
                FWHM_THRESHOLDS_DISPLAY,
                SENSOR_IQ_COLORS,
                SENSOR_IQ_ICONS,
                ZONE_BOUNDARIES_DISPLAY,
            )

            for channel, sensor_iq in self._pending_sensor_iq_updates.items():
                # Get the appropriate label widget
                label_attr = f"sensor_iq_{channel}_diag"
                if not hasattr(self.main_window, label_attr):
                    continue

                label = getattr(self.main_window, label_attr)

                # Get icon and color
                iq_level_key = sensor_iq.iq_level.value
                icon = SENSOR_IQ_ICONS.get(iq_level_key, "❓")
                color = SENSOR_IQ_COLORS.get(iq_level_key, "#86868B")

                # Build display text
                fwhm_text = f"{sensor_iq.fwhm:.1f}nm" if sensor_iq.fwhm else "N/A"
                display_text = (
                    f"{icon} {sensor_iq.iq_level.value.upper()} | "
                    f"λ={sensor_iq.wavelength:.1f}nm, "
                    f"FWHM={fwhm_text}, "
                    f"Score={sensor_iq.quality_score:.2f}"
                )

                # Update label
                label.setText(display_text)
                label.setStyleSheet(
                    f"font-size: 12px; color: {color}; font-weight: bold; "
                    f"font-family: 'Consolas', 'Courier New', monospace;",
                )

                # Update static info labels (only once, not per channel)
                if channel == "a":
                    if hasattr(self.main_window, "sensor_iq_zones_diag"):
                        self.main_window.sensor_iq_zones_diag.setText(
                            ZONE_BOUNDARIES_DISPLAY,
                        )
                    if hasattr(self.main_window, "sensor_iq_fwhm_diag"):
                        self.main_window.sensor_iq_fwhm_diag.setText(
                            FWHM_THRESHOLDS_DISPLAY,
                        )

        except Exception as e:
            logger.debug(f"Sensor IQ display update failed: {e}")

        # Clear processed updates
        self._pending_sensor_iq_updates.clear()

    def set_transmission_updates_enabled(self, enabled: bool):
        """Enable/disable transmission curve updates."""
        self._transmission_updates_enabled = enabled
        logger.info(f"Transmission updates: {'enabled' if enabled else 'disabled'}")

    def set_raw_spectrum_updates_enabled(self, enabled: bool):
        """Enable/disable raw spectrum curve updates."""
        self._raw_spectrum_updates_enabled = enabled
        logger.info(f"Raw spectrum updates: {'enabled' if enabled else 'disabled'}")

    def cleanup(self):
        """Stop timer and cleanup resources."""
        if self._update_timer:
            self._update_timer.stop()
        logger.info("UIUpdateCoordinator cleaned up")
