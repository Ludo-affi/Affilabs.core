"""
CalibrationData - Immutable data model for calibration parameters.

Single source of truth for all calibration results.
Used by both QC display and live acquisition.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
import numpy as np
from datetime import datetime


@dataclass(frozen=True)
class CalibrationData:
    """Immutable calibration data container.

    All calibration parameters are stored here as the single source of truth.
    Both QC display and live acquisition reference this data.
    """

    # Core acquisition parameters
    integration_time: float
    p_integration_time: float
    num_scans: int

    # LED intensities
    s_mode_intensities: Dict[str, int]
    p_mode_intensities: Dict[str, int]

    # Wavelength calibration
    wavelengths: np.ndarray
    wave_min_index: int
    wave_max_index: int

    # Reference spectra
    s_pol_ref: Dict[str, np.ndarray]
    p_pol_ref: Dict[str, np.ndarray]

    # QC display data
    dark_noise: np.ndarray
    afterglow_curves: Dict[str, np.ndarray]
    transmission_spectra: Dict[str, np.ndarray]

    # LED timing
    pre_led_delay_ms: float
    post_led_delay_ms: float

    # QC metrics
    spr_fwhm: Dict[str, float] = field(default_factory=dict)
    orientation_validation: Dict[str, dict] = field(default_factory=dict)
    transmission_validation: Dict[str, dict] = field(default_factory=dict)

    # Device metadata
    device_type: str = "Unknown"
    detector_serial: str = "N/A"
    firmware_version: str = "N/A"
    calibration_timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    calibration_method: str = "full_6step"

    # Diagnostic data
    ch_error_list: list = field(default_factory=list)
    weakest_channel: Optional[str] = None

    @classmethod
    def from_calibration_result(cls, cal_result, device_info: dict = None) -> 'CalibrationData':
        """Create CalibrationData from calibration_6step result.

        Args:
            cal_result: Result object from run_full_6step_calibration()
            device_info: Optional dict with device metadata
                {
                    'device_type': str,
                    'detector_serial': str,
                    'firmware_version': str,
                    'pre_led_delay_ms': float,
                    'post_led_delay_ms': float
                }

        Returns:
            Immutable CalibrationData instance
        """
        device_info = device_info or {}

        return cls(
            # Core parameters
            integration_time=cal_result.s_integration_time,
            p_integration_time=cal_result.p_integration_time,
            num_scans=cal_result.num_scans,

            # LED intensities
            s_mode_intensities=dict(cal_result.ref_intensity),
            p_mode_intensities=dict(cal_result.p_mode_intensity),

            # Wavelength calibration
            wavelengths=cal_result.wave_data.copy(),
            wave_min_index=getattr(cal_result, 'wave_min_index', 0),
            wave_max_index=getattr(cal_result, 'wave_max_index', len(cal_result.wave_data)),

            # Reference spectra
            s_pol_ref={ch: spec.copy() for ch, spec in cal_result.s_ref_sig.items()},
            p_pol_ref={ch: spec.copy() for ch, spec in cal_result.p_ref_sig.items()},

            # QC display data
            dark_noise=cal_result.dark_noise.copy(),
            afterglow_curves={ch: curve.copy() for ch, curve in getattr(cal_result, 'afterglow_curves', {}).items()},
            transmission_spectra={ch: trans.copy() for ch, trans in getattr(cal_result, 'transmission', {}).items()},

            # LED timing
            pre_led_delay_ms=device_info.get('pre_led_delay_ms', 45.0),
            post_led_delay_ms=device_info.get('post_led_delay_ms', 5.0),

            # QC metrics
            spr_fwhm=dict(getattr(cal_result, 'spr_fwhm', {})),
            orientation_validation=dict(getattr(cal_result, 'orientation_validation', {})),
            transmission_validation=dict(getattr(cal_result, 'transmission_validation', {})),

            # Device metadata
            device_type=device_info.get('device_type', 'Unknown'),
            detector_serial=device_info.get('detector_serial', 'N/A'),
            firmware_version=device_info.get('firmware_version', 'N/A'),
            calibration_timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            calibration_method=getattr(cal_result, 'calibration_method', 'full_6step'),

            # Diagnostic data
            ch_error_list=list(cal_result.ch_error_list),
            weakest_channel=getattr(cal_result, 'weakest_channel', None)
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization or QC display.

        Returns:
            Dictionary with all calibration data
        """
        return {
            's_pol_spectra': self.s_pol_ref,
            'p_pol_spectra': self.p_pol_ref,
            'dark_scan': {ch: self.dark_noise for ch in self.s_pol_ref.keys()},
            'afterglow_curves': self.afterglow_curves,
            'transmission_spectra': self.transmission_spectra,
            'wavelengths': self.wavelengths,
            'integration_time': self.integration_time,
            'p_integration_time': self.p_integration_time,
            'led_intensities': self.p_mode_intensities,
            'spr_fwhm': self.spr_fwhm,
            'orientation_validation': self.orientation_validation,
            'transmission_validation': self.transmission_validation,
            'num_scans': self.num_scans,
            'timestamp': self.calibration_timestamp,
            'device_type': self.device_type,
            'detector_serial': self.detector_serial,
            'firmware_version': self.firmware_version,
            'detector_number': 'N/A',  # For backward compatibility
        }

    def validate(self) -> bool:
        """Validate that all required calibration data is present.

        Returns:
            True if calibration data is complete and valid
        """
        if not self.integration_time or self.integration_time <= 0:
            return False

        if not self.s_mode_intensities or not self.p_mode_intensities:
            return False

        if not self.s_pol_ref or not self.p_pol_ref:
            return False

        if self.wavelengths is None or len(self.wavelengths) == 0:
            return False

        if self.dark_noise is None or len(self.dark_noise) == 0:
            return False

        return True

    def get_channels(self) -> list:
        """Get list of calibrated channels.

        Returns:
            List of channel identifiers ['a', 'b', 'c', 'd']
        """
        return sorted(self.s_pol_ref.keys())

    # Property aliases for clearer semantics
    @property
    def s_mode_integration_time(self) -> float:
        """Alias for integration_time (S-mode)."""
        return self.integration_time

    @property
    def wavelength_min(self) -> float:
        """Get minimum wavelength in SPR range."""
        if len(self.wavelengths) > self.wave_min_index:
            return self.wavelengths[self.wave_min_index]
        return self.wavelengths[0] if len(self.wavelengths) > 0 else 0.0

    @property
    def wavelength_max(self) -> float:
        """Get maximum wavelength in SPR range."""
        if len(self.wavelengths) > self.wave_max_index:
            return self.wavelengths[self.wave_max_index]
        return self.wavelengths[-1] if len(self.wavelengths) > 0 else 0.0
