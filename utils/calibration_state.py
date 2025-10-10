"""Shared Calibration State - Single Source of Truth.

This module provides a single shared state object that both the calibrator
and data acquisition can reference, eliminating the need for data copying
and synchronization logic.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import numpy as np

from utils.common import CH_LIST


@dataclass
class CalibrationState:
    """Shared calibration state - single source of truth for SPR system.
    
    This object is passed by reference to both SPRCalibrator and SPRDataAcquisition,
    ensuring they always work with the same data without copying or synchronization.
    
    Thread Safety:
        Use the provided lock when accessing data from multiple threads.
    """
    
    # Thread safety
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    
    # Wavelength data (full spectrum from spectrometer)
    wavelengths: Optional[np.ndarray] = None
    wave_data: Optional[np.ndarray] = None  # Alias for backward compatibility
    full_spectrum_wavelengths: Optional[np.ndarray] = None  # Full range before any cropping
    
    # Wavelength range indices
    wave_min_index: int = 0
    wave_max_index: int = 0
    
    # Dark noise (background signal)
    dark_noise: Optional[np.ndarray] = None
    
    # Reference signals per channel (measured during calibration)
    ref_sig: Dict[str, Optional[np.ndarray]] = field(default_factory=lambda: {ch: None for ch in CH_LIST})
    
    # LED calibration intensities per channel
    leds_calibrated: Dict[str, int] = field(default_factory=dict)
    
    # Integration settings
    integration_time: float = 0.0
    num_scans: int = 1
    
    # Additional settings
    ref_intensity: float = 0.0
    led_delay: float = 0.1
    med_filt_win: int = 11
    
    # Device information
    device_type: str = ""
    
    # Calibration status
    is_calibrated: bool = False
    calibration_timestamp: Optional[str] = None
    
    def is_valid(self) -> bool:
        """Check if calibration is complete and valid.
        
        Returns:
            True if all required calibration data is present, False otherwise.
        """
        with self._lock:
            return (
                self.wavelengths is not None and
                len(self.wavelengths) > 0 and
                self.dark_noise is not None and
                len(self.dark_noise) > 0 and
                self.ref_sig is not None and
                any(ref is not None for ref in self.ref_sig.values()) and
                self.leds_calibrated is not None and
                len(self.leds_calibrated) > 0
            )
    
    def get_wavelengths(self) -> Optional[np.ndarray]:
        """Thread-safe getter for wavelengths.
        
        Returns:
            Copy of wavelengths array or None if not available.
        """
        with self._lock:
            return self.wavelengths.copy() if self.wavelengths is not None else None
    
    def get_dark_noise(self) -> Optional[np.ndarray]:
        """Thread-safe getter for dark noise.
        
        Returns:
            Copy of dark noise array or None if not available.
        """
        with self._lock:
            return self.dark_noise.copy() if self.dark_noise is not None else None
    
    def get_ref_sig(self, channel: str) -> Optional[np.ndarray]:
        """Thread-safe getter for reference signal.
        
        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            
        Returns:
            Copy of reference signal array or None if not available.
        """
        with self._lock:
            ref = self.ref_sig.get(channel)
            return ref.copy() if ref is not None else None
    
    def get_led_intensity(self, channel: str) -> Optional[int]:
        """Thread-safe getter for LED intensity.
        
        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            
        Returns:
            LED intensity value or None if not calibrated.
        """
        with self._lock:
            return self.leds_calibrated.get(channel)
    
    def set_wavelengths(self, wavelengths: np.ndarray) -> None:
        """Thread-safe setter for wavelengths.
        
        Args:
            wavelengths: Wavelength array from spectrometer.
        """
        with self._lock:
            self.wavelengths = wavelengths.copy()
            self.wave_data = wavelengths.copy()  # Keep alias in sync
            if self.full_spectrum_wavelengths is None:
                self.full_spectrum_wavelengths = wavelengths.copy()
    
    def set_dark_noise(self, dark_noise: np.ndarray) -> None:
        """Thread-safe setter for dark noise.
        
        Args:
            dark_noise: Dark noise array from measurement.
        """
        with self._lock:
            self.dark_noise = dark_noise.copy()
    
    def set_ref_sig(self, channel: str, ref_signal: np.ndarray) -> None:
        """Thread-safe setter for reference signal.
        
        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            ref_signal: Reference signal array.
        """
        with self._lock:
            self.ref_sig[channel] = ref_signal.copy()
    
    def set_led_intensity(self, channel: str, intensity: int) -> None:
        """Thread-safe setter for LED intensity.
        
        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            intensity: LED intensity value.
        """
        with self._lock:
            self.leds_calibrated[channel] = intensity
    
    def reset(self) -> None:
        """Reset all calibration data to initial state."""
        with self._lock:
            self.wavelengths = None
            self.wave_data = None
            self.full_spectrum_wavelengths = None
            self.wave_min_index = 0
            self.wave_max_index = 0
            self.dark_noise = None
            self.ref_sig = {ch: None for ch in CH_LIST}
            self.leds_calibrated = {}
            self.integration_time = 0.0
            self.num_scans = 1
            self.ref_intensity = 0.0
            self.is_calibrated = False
            self.calibration_timestamp = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert calibration state to dictionary for serialization.
        
        Returns:
            Dictionary containing all calibration data.
        """
        with self._lock:
            return {
                "wavelengths": self.wavelengths.tolist() if self.wavelengths is not None else None,
                "wave_min_index": self.wave_min_index,
                "wave_max_index": self.wave_max_index,
                "dark_noise": self.dark_noise.tolist() if self.dark_noise is not None else None,
                "ref_sig": {
                    ch: ref.tolist() if ref is not None else None 
                    for ch, ref in self.ref_sig.items()
                },
                "leds_calibrated": self.leds_calibrated,
                "integration_time": self.integration_time,
                "num_scans": self.num_scans,
                "ref_intensity": self.ref_intensity,
                "led_delay": self.led_delay,
                "med_filt_win": self.med_filt_win,
                "device_type": self.device_type,
                "is_calibrated": self.is_calibrated,
                "calibration_timestamp": self.calibration_timestamp,
            }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """Load calibration state from dictionary.
        
        Args:
            data: Dictionary containing calibration data.
        """
        with self._lock:
            # Wavelengths
            if data.get("wavelengths"):
                wavelengths = np.array(data["wavelengths"])
                self.wavelengths = wavelengths
                self.wave_data = wavelengths.copy()
                self.full_spectrum_wavelengths = wavelengths.copy()
            
            self.wave_min_index = data.get("wave_min_index", 0)
            self.wave_max_index = data.get("wave_max_index", 0)
            
            # Dark noise
            if data.get("dark_noise"):
                self.dark_noise = np.array(data["dark_noise"])
            
            # Reference signals
            ref_sig_data = data.get("ref_sig", {})
            for ch in CH_LIST:
                if ch in ref_sig_data and ref_sig_data[ch] is not None:
                    self.ref_sig[ch] = np.array(ref_sig_data[ch])
            
            # LED intensities
            self.leds_calibrated = data.get("leds_calibrated", {})
            
            # Settings
            self.integration_time = data.get("integration_time", 0.0)
            self.num_scans = data.get("num_scans", 1)
            self.ref_intensity = data.get("ref_intensity", 0.0)
            self.led_delay = data.get("led_delay", 0.1)
            self.med_filt_win = data.get("med_filt_win", 11)
            
            # Metadata
            self.device_type = data.get("device_type", "")
            self.is_calibrated = data.get("is_calibrated", False)
            self.calibration_timestamp = data.get("calibration_timestamp")
    
    def __repr__(self) -> str:
        """String representation of calibration state."""
        with self._lock:
            wavelength_info = f"{len(self.wavelengths)} points" if self.wavelengths is not None else "None"
            ref_channels = [ch for ch, ref in self.ref_sig.items() if ref is not None]
            led_channels = list(self.leds_calibrated.keys())
            
            return (
                f"CalibrationState("
                f"valid={self.is_valid()}, "
                f"wavelengths={wavelength_info}, "
                f"dark_noise={'present' if self.dark_noise is not None else 'None'}, "
                f"ref_channels={ref_channels}, "
                f"led_channels={led_channels}, "
                f"integration={self.integration_time}ms)"
            )
