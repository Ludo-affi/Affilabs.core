"""Acquisition service that encapsulates LED control and spectrum acquisition.

This isolates device I/O (LED on/off, read spectra, averaging) from the UI layer.
It preserves current behavior, including channel sequencing and device-specific
normalization, while providing a clean, testable entry point.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np

from utils.logger import logger
from utils.spr_signal_processing import calculate_transmission
from utils.hal.interfaces import LEDController, SpectrometerInfo


class AcquisitionService:
    """Handles channel-wise acquisition with LED sequencing and averaging."""

    def __init__(self, led: LEDController, spec_info: SpectrometerInfo, spectrum_acq):
        """Initialize the service.

        Args:
            ctrl: Controller providing LED/channel methods (turn_on_channel/turn_off_channels)
            usb: Spectrometer wrapper with read_intensity(), serial_number, etc.
            spectrum_acq: SpectrumAcquisition helper for vectorized averaging
        """
        self.led = led
        self.spec_info = spec_info
        self.spectrum_acq = spectrum_acq

    def acquire_channel(
        self,
        ch: str,
        wave_min_index: int,
        wave_max_index: int,
        num_scans: int,
        led_delay: float,
        post_delay: float,
        dark_noise: np.ndarray,
        ref_sig: Dict[str, Optional[np.ndarray]],
        wave_data: Optional[np.ndarray] = None,
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Acquire averaged spectrum for a channel and compute transmission.

        Returns a tuple (int_data, trans_data). On failure, returns (None, None).
        Behavior matches legacy sequence: LED on → delay → read/average → dark subtract →
        optional FLMT09788 chB normalization → transmission (if reference available) → LED off.
        """
        int_data = None
        trans_data = None
        try:
            if self.led is not None:
                self.led.turn_on_channel(ch=ch)

            if led_delay and led_delay > 0:
                import time as _t
                _t.sleep(led_delay)

            if self.spectrum_acq is None:
                logger.error("Spectrum acquisition helper not initialized")
                return None, None

            int_data_sum = self.spectrum_acq.acquire_averaged_spectrum(
                wave_min_index,
                wave_max_index,
                num_scans,
            )

            if int_data_sum is not None:
                int_data = int_data_sum - dark_noise

                # Device-specific normalization: FLMT09788 channel B around 640 nm
                try:
                    serial_number = self.spec_info.serial_number
                    if (
                        serial_number == "FLMT09788"
                        and ch == "b"
                        and wave_data is not None
                        and len(wave_data) > 0
                    ):
                        target_counts = 35000.0
                        wl = wave_data
                        left_idx = int(np.searchsorted(wl, 635, side="left"))
                        right_idx = int(np.searchsorted(wl, 645, side="right"))
                        left_idx = max(0, left_idx)
                        right_idx = min(len(wl), max(left_idx + 1, right_idx))
                        roi = int_data[left_idx:right_idx]
                        if roi.size > 0:
                            roi_mean = float(np.mean(roi))
                            if 0 < roi_mean < target_counts:
                                scale = min(2.0, target_counts / roi_mean)
                                if scale > 1.0:
                                    int_data = np.clip(int_data * scale, 0, 65535.0)
                                    logger.debug(
                                        f"FLMT09788 chB scaling @640nm: mean {roi_mean:.0f} → target {target_counts:.0f} (x{scale:.2f})"
                                    )
                except Exception as _norm_err:
                    logger.debug(f"B-channel 640nm normalization skipped: {_norm_err}")

                # Compute transmission if reference is available
                ref = ref_sig.get(ch) if ref_sig is not None else None
                if ref is not None:
                    try:
                        trans_data = calculate_transmission(int_data, ref)
                    except Exception as e:
                        logger.exception(f"Failed to compute transmission for ch {ch}: {e}")

            return int_data, trans_data

        except Exception as e:
            logger.exception(f"Error during acquisition for channel {ch}: {e}")
            return None, None
        finally:
            # Ensure LEDs are turned off after read attempt
            try:
                if self.led is not None:
                    self.led.turn_off_channels()
            except Exception:
                # Guard against cascading errors
                pass
            # Optional post delay to allow afterglow decay before next channel
            try:
                if post_delay and post_delay > 0:
                    import time as _t
                    _t.sleep(post_delay)
            except Exception:
                pass
