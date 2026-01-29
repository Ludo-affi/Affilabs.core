"""Detector Configuration and Characteristics

Provides detector-specific wavelength ranges and parameters based on detector serial number.
Makes the processing pipeline detector-agnostic by automatically detecting the right characteristics.
"""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class DetectorCharacteristics:
    """Detector specifications with valid wavelength ranges"""

    name: str
    serial_prefix: str  # Serial number prefix for identification
    wavelength_min: float  # nm - Valid data start
    wavelength_max: float  # nm - Valid data end
    spr_wavelength_min: float  # nm - SPR region start (for peak finding)
    spr_wavelength_max: float  # nm - SPR region end (for peak finding)
    max_counts: int  # Maximum ADC counts
    pixels: int  # Number of detector pixels


# Detector Database - Add new detectors here
DETECTOR_DATABASE = {
    "PhasePhotonics": DetectorCharacteristics(
        name="Phase Photonics ST Series",
        serial_prefix="ST",
        wavelength_min=570.0,  # Valid data starts at 570nm
        wavelength_max=720.0,
        spr_wavelength_min=570.0,  # SPR search starts at 570nm
        spr_wavelength_max=720.0,
        max_counts=4095,  # 12-bit ADC
        pixels=1848,
    ),
    "USB4000": DetectorCharacteristics(
        name="Ocean Optics USB4000",
        serial_prefix="USB4",
        wavelength_min=560.0,  # Valid data starts at 560nm
        wavelength_max=720.0,
        spr_wavelength_min=560.0,  # SPR search starts at 560nm
        spr_wavelength_max=720.0,
        max_counts=65535,  # 16-bit ADC
        pixels=3648,
    ),
    "FlameT": DetectorCharacteristics(
        name="Ocean Optics Flame-T",
        serial_prefix="FLMT",
        wavelength_min=560.0,
        wavelength_max=720.0,
        spr_wavelength_min=560.0,
        spr_wavelength_max=720.0,
        max_counts=65535,  # 16-bit ADC
        pixels=2048,
    ),
}


def get_detector_characteristics(
    serial_number: Optional[str] = None,
    detector_type: Optional[str] = None,
) -> DetectorCharacteristics:
    """Get detector characteristics from serial number or type.

    Args:
        serial_number: Detector serial number (e.g., "ST00012", "USB4H14526")
        detector_type: Detector type string (e.g., "PhasePhotonics", "USB4000")

    Returns:
        DetectorCharacteristics for the identified detector

    Examples:
        >>> get_detector_characteristics(serial_number="ST00012")
        DetectorCharacteristics(name="Phase Photonics ST Series", wavelength_min=570.0, ...)

        >>> get_detector_characteristics(detector_type="USB4000")
        DetectorCharacteristics(name="Ocean Optics USB4000", wavelength_min=560.0, ...)
    """
    # Try to identify by serial number first
    if serial_number:
        for detector_key, characteristics in DETECTOR_DATABASE.items():
            if serial_number.startswith(characteristics.serial_prefix):
                return characteristics

    # Try to identify by detector type string
    if detector_type:
        # Handle common variations
        detector_type_upper = detector_type.upper()
        if "PHASE" in detector_type_upper or detector_type_upper.startswith("ST"):
            return DETECTOR_DATABASE["PhasePhotonics"]
        elif "USB4" in detector_type_upper:
            return DETECTOR_DATABASE["USB4000"]
        elif "FLAME" in detector_type_upper or "FLMT" in detector_type_upper:
            return DETECTOR_DATABASE["FlameT"]

    # Try to auto-detect from calibration file
    try:
        import json
        import os

        calibration_path = os.path.join(os.path.dirname(__file__), "..", "..", "calibration.json")
        if os.path.exists(calibration_path):
            with open(calibration_path, 'r') as f:
                cal_data = json.load(f)
                if 'detector_serial' in cal_data:
                    # Recursive call with detector serial from calibration
                    return get_detector_characteristics(serial_number=cal_data['detector_serial'])
    except Exception:
        pass  # Fail silently, use default

    # Default to PhasePhotonics (most common in current deployment)
    return DETECTOR_DATABASE["PhasePhotonics"]


def get_spr_wavelength_range(
    serial_number: Optional[str] = None,
    detector_type: Optional[str] = None,
) -> Tuple[float, float]:
    """Get SPR wavelength range for peak finding.

    Args:
        serial_number: Detector serial number
        detector_type: Detector type string

    Returns:
        (min_wavelength, max_wavelength) tuple in nm

    Examples:
        >>> get_spr_wavelength_range(serial_number="ST00012")
        (570.0, 720.0)

        >>> get_spr_wavelength_range(detector_type="USB4000")
        (560.0, 720.0)
    """
    characteristics = get_detector_characteristics(serial_number, detector_type)
    return (characteristics.spr_wavelength_min, characteristics.spr_wavelength_max)


def filter_valid_wavelength_data(
    wavelengths: "np.ndarray",
    data: "np.ndarray",
    detector_serial: Optional[str] = None,
    detector_type: Optional[str] = None,
) -> Tuple["np.ndarray", "np.ndarray"]:
    """Filter wavelength data to only include valid detector range.

    Critical for Phase Photonics detector which has noisy data below 570nm.
    This prevents artifacts in analysis and display.

    Args:
        wavelengths: Wavelength array (nm)
        data: Corresponding data array (same length as wavelengths)
        detector_serial: Detector serial number
        detector_type: Detector type string

    Returns:
        (filtered_wavelengths, filtered_data) tuple

    Examples:
        >>> wl = np.array([560, 565, 570, 575, 580])
        >>> data = np.array([100, 110, 120, 130, 140])
        >>> filtered_wl, filtered_data = filter_valid_wavelength_data(wl, data, "ST00012")
        >>> # Returns wavelengths >= 570nm only for Phase Photonics
    """
    import numpy as np

    characteristics = get_detector_characteristics(detector_serial, detector_type)
    valid_min = characteristics.wavelength_min

    # Create mask for valid wavelength range
    valid_mask = wavelengths >= valid_min

    return wavelengths[valid_mask], data[valid_mask]
