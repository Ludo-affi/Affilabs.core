"""Compatibility shim for legacy LED calibration APIs.

This module preserves the historical import paths used throughout the codebase
(e.g., `from utils.led_calibration import ...`) while delegating to the
maintained implementations in `_legacy_led_calibration`.

New calibration flows should use `utils.calibration_6step` and
`utils.LEDCONVERGENCE` where applicable.
"""
from __future__ import annotations

import warnings

# Re-export selected legacy APIs expected by callers
from ._legacy_led_calibration import (
    analyze_channel_headroom,
    calibrate_led_channel,
    calibrate_p_mode_leds,
    perform_full_led_calibration,
)

__all__ = [
    "analyze_channel_headroom",
    "calibrate_led_channel",
    "calibrate_p_mode_leds",
    "perform_full_led_calibration",
]

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.warn(
    "utils.led_calibration is a compatibility shim. "
    "Prefer utils.calibration_6step (Step 4/6) and utils.LEDCONVERGENCE for new code.",
    category=RuntimeWarning,
    stacklevel=2,
)
