"""Shared LED Model Training Helpers.

Utility functions for measuring LED response and fitting linear models.
Used by both:
- affilabs.core.oem_model_training (runtime automatic training)
- led_calibration_official/1_create_model.py (manual OEM calibration)

Author: ezControl-AI System
Date: December 17, 2025
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from affilabs.utils.controller import PicoP4SPR
    from affilabs.utils.usb4000_wrapper import USB4000


def measure_led_response(
    controller: PicoP4SPR,
    spectrometer: USB4000,
    led_char: str,
    intensity: int,
    integration_time_ms: float,
    dark_counts: float,
    detector_wait_ms: int = 50,
) -> dict[str, float | int | bool]:
    """Measure single LED at given intensity and integration time.

    Args:
        controller: PicoP4SPR controller instance
        spectrometer: USB4000 spectrometer instance
        led_char: LED character ('a', 'b', 'c', or 'd')
        intensity: LED intensity (0-255)
        integration_time_ms: Integration time in milliseconds
        dark_counts: Dark counts to subtract
        detector_wait_ms: Wait time after LED stabilization (default: 50ms)

    Returns:
        Dictionary with measurement results:
            - raw_counts: Top 10 pixels average
            - corrected_counts: raw_counts - dark_counts
            - saturated_wavelengths: Number of saturated pixels (>=65535)
            - near_saturation_pixels: Number of pixels near saturation (>=60000)
            - is_saturated: True if any saturation detected

    Note:
        This function uses DIRECT hardware commands (NOT HAL).
        This is acceptable for OEM calibration since:
        1. It's a one-time factory calibration process
        2. Creates the model that HAL will use for runtime
        3. Uses fixed detector_wait_ms (not settings-driven)

    """
    # Set integration time
    spectrometer.set_integration(integration_time_ms)
    time.sleep(0.05)

    # Enable LEDs first (P4SPR requires lm:ABCD, P4PRO uses enable_multi_led)
    raw_ctrl = controller._ctrl if hasattr(controller, '_ctrl') else controller
    controller_class = raw_ctrl.__class__.__name__

    if 'P4SPR' in controller_class:
        # P4SPR: Use direct serial lm:ABCD command
        try:
            if hasattr(raw_ctrl, '_ser') and raw_ctrl._ser is not None:
                raw_ctrl._ser.write(b"lm:ABCD\n")
                time.sleep(0.05)
                raw_ctrl._ser.read(10)  # Read response
        except Exception:
            pass  # Ignore errors during LED enable
    elif 'P4PRO' in controller_class:
        # P4PRO: Use enable_multi_led() if available
        if hasattr(controller, 'enable_multi_led'):
            try:
                controller.enable_multi_led(a=True, b=True, c=True, d=True)
            except Exception:
                pass

    # Turn on this LED only (others off)
    intensities = {"a": 0, "b": 0, "c": 0, "d": 0}
    intensities[led_char] = intensity
    controller.set_batch_intensities(**intensities)
    time.sleep(0.3)  # LED settle time
    time.sleep(detector_wait_ms / 1000.0)  # Detector wait time

    # Measure (average of 3 scans, then average top 10 pixels)
    # Use HAL-compatible method
    scans = []
    for _ in range(3):
        scans.append(spectrometer.read_intensity())
        time.sleep(0.05)
    spectrum = np.mean(scans, axis=0)
    top_10_indices = np.argpartition(spectrum, -10)[-10:]
    top_10_avg = float(spectrum[top_10_indices].mean())
    corrected = top_10_avg - dark_counts

    # Detector-agnostic saturation check (USB4000: 65535, PhasePhotonics: 4095)
    detector_max = getattr(spectrometer, 'max_counts', 65535)
    near_saturation_threshold = int(0.92 * detector_max)  # 92% of max

    saturated_pixels = int((spectrum >= detector_max).sum())
    near_saturation = int((spectrum >= near_saturation_threshold).sum())

    return {
        "raw_counts": top_10_avg,
        "corrected_counts": corrected,
        "saturated_wavelengths": saturated_pixels,
        "near_saturation_pixels": near_saturation,
        "is_saturated": saturated_pixels > 0 or top_10_avg >= near_saturation_threshold,
    }


def fit_linear_model(data_points: list[tuple[int, float]]) -> float | None:
    """Fit linear model: counts = slope × intensity.

    Args:
        data_points: List of (intensity, corrected_counts) tuples

    Returns:
        Slope (counts per intensity unit) or None if insufficient data

    """
    if len(data_points) < 2:
        return None

    # Linear fit through origin: counts = k × intensity
    sum_i_c = sum(i * c for i, c in data_points)
    sum_i_i = sum(i * i for i, _ in data_points)

    if sum_i_i == 0:
        return None

    slope = sum_i_c / sum_i_i
    return slope
