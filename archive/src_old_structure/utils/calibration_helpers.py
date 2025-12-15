from dataclasses import dataclass


@dataclass
class DetectorParams:
    """Detector parameters with STANDARD units.

    INTEGRATION TIME STANDARD: All integration times use MILLISECONDS.
    This matches usb.set_integration(time_ms) API throughout the codebase.
    """

    max_counts: int
    saturation_threshold: int
    min_integration_time: int  # MILLISECONDS (not seconds, not microseconds)
    max_integration_time: int  # MILLISECONDS (not seconds, not microseconds)
    saturation_level: int
    target_counts: int  # Target signal level for calibration (typically 90% of max)


def get_detector_params(usb) -> DetectorParams:
    # Minimal detector parameters; adjust with usb if available
    # Fallback values typical for Ocean Optics-style detectors
    max_counts = getattr(usb, "max_counts", 65535)
    saturation_threshold = int(0.95 * max_counts)
    target_counts = int(0.90 * max_counts)  # Target 90% of max for optimal SNR
    # If usb exposes min/max integration in seconds, convert to ms
    min_int_ms = int(getattr(usb, "min_integration_ms", 5))
    max_int_ms = int(getattr(usb, "max_integration_ms", 1000))
    return DetectorParams(
        max_counts=max_counts,
        saturation_threshold=saturation_threshold,
        min_integration_time=min_int_ms,
        max_integration_time=max_int_ms,
        saturation_level=saturation_threshold,
        target_counts=target_counts,
    )


def determine_channel_list(
    device_type: str,
    single_mode: bool,
    single_ch: str,
) -> list[str]:
    if single_mode:
        return [single_ch.lower()]
    return ["a", "b", "c", "d"]


def switch_mode_safely(ctrl, mode: str, turn_off_leds: bool = True) -> None:
    # Expect ctrl to have set_polarizer_mode and turn_off_channels
    if mode.lower() == "s":
        if hasattr(ctrl, "set_polarizer_mode"):
            ctrl.set_polarizer_mode("s")
    elif mode.lower() == "p":
        if hasattr(ctrl, "set_polarizer_mode"):
            ctrl.set_polarizer_mode("p")
    if turn_off_leds and hasattr(ctrl, "turn_off_channels"):
        ctrl.turn_off_channels()
