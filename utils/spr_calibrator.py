"""
SPR Calibration Module

Handles all SPR spectrometer calibration operations:
- Wavelength range calibration
- Integration time optimization
- LED intensity calibration (S-mode and P-mode)
- Dark noise measurement
- Reference signal acquisition
- Calibration validation
- Calibration history logging

Author: Refactored from main.py
Date: October 7, 2025
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import time
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

import numpy as np
import serial

from settings import (
    CH_LIST,
    DARK_NOISE_SCANS,
    DEVICES,
    EZ_CH_LIST,
    LED_DELAY,
    MAX_INTEGRATION,
    MAX_WAVELENGTH,
    MIN_INTEGRATION,
    MIN_WAVELENGTH,
    P_COUNT_THRESHOLD,
    P_LED_MAX,
    P_MAX_INCREASE,
    REF_SCANS,
    ROOT_DIR,
    S_COUNT_MAX,
    S_LED_INT,
    S_LED_MIN,
    TIME_ZONE,
)
from utils.logger import logger
from utils.spr_data_processor import SPRDataProcessor

if TYPE_CHECKING:
    from utils.controller import KineticController, PicoEZSPR, PicoP4SPR
    from utils.usb4000_adapter import USB4000  # HAL-based USB4000 adapter


# Calibration constants
COARSE_ADJUSTMENT = 20  # LED intensity adjustment step for rough calibration
MEDIUM_ADJUSTMENT = 5   # LED intensity adjustment step for medium calibration
FINE_ADJUSTMENT = 1     # LED intensity adjustment step for fine calibration
INTEGRATION_STEP_THRESHOLD = 50  # Threshold for changing dark noise scan count


class CalibrationState:
    """
    Encapsulates calibration state and results.
    Makes calibration data easier to test, serialize, and manage.
    """
    
    def __init__(self):
        """Initialize calibration state with default values."""
        # Wavelength calibration
        self.wave_min_index = 0
        self.wave_max_index = 0
        self.wave_data: np.ndarray = np.array([])
        self.fourier_weights: np.ndarray = np.array([])
        
        # Integration and scanning
        self.integration = MIN_INTEGRATION
        self.num_scans = 1
        
        # LED intensities
        self.ref_intensity: dict[str, int] = {ch: 0 for ch in CH_LIST}
        self.leds_calibrated: dict[str, int] = {ch: 0 for ch in CH_LIST}
        
        # Reference data
        self.dark_noise: np.ndarray = np.array([])
        self.ref_sig: dict[str, np.ndarray | None] = {ch: None for ch in CH_LIST}
        
        # Filter and timing settings
        self.med_filt_win = 11
        self.led_delay = LED_DELAY
        
        # Results
        self.ch_error_list: list[str] = []
        self.is_calibrated = False
        self.calibration_timestamp: float | None = None
    
    def to_dict(self) -> dict:
        """Export calibration state to dictionary for saving."""
        return {
            "wave_min_index": self.wave_min_index,
            "wave_max_index": self.wave_max_index,
            "integration": self.integration,
            "num_scans": self.num_scans,
            "ref_intensity": self.ref_intensity.copy(),
            "leds_calibrated": self.leds_calibrated.copy(),
            "med_filt_win": self.med_filt_win,
            "led_delay": self.led_delay,
            "ch_error_list": self.ch_error_list.copy(),
            "is_calibrated": self.is_calibrated,
            "calibration_timestamp": self.calibration_timestamp,
        }
    
    def from_dict(self, data: dict) -> None:
        """Import calibration state from dictionary."""
        self.wave_min_index = data.get("wave_min_index", 0)
        self.wave_max_index = data.get("wave_max_index", 0)
        self.integration = data.get("integration", MIN_INTEGRATION)
        self.num_scans = data.get("num_scans", 1)
        self.ref_intensity = data.get("ref_intensity", {ch: 0 for ch in CH_LIST})
        self.leds_calibrated = data.get("leds_calibrated", {ch: 0 for ch in CH_LIST})
        self.med_filt_win = data.get("med_filt_win", 11)
        self.led_delay = data.get("led_delay", LED_DELAY)
        self.ch_error_list = data.get("ch_error_list", [])
        self.is_calibrated = data.get("is_calibrated", False)
        self.calibration_timestamp = data.get("calibration_timestamp")
    
    def reset(self) -> None:
        """Reset calibration state to defaults."""
        self.__init__()


class SPRCalibrator:
    """
    Handles all SPR spectrometer calibration operations.
    
    This class encapsulates the calibration logic for the SPR system,
    including wavelength range, integration time, LED intensities,
    dark noise, and reference signals.
    
    Attributes:
        ctrl: LED/polarizer controller
        usb: USB4000 spectrometer
        state: Calibration state storage
        stop_flag: Threading event to signal stop
        device_type: Type of controller device
    """
    
    def __init__(
        self,
        ctrl: PicoP4SPR | PicoEZSPR | None,
        usb: USB4000 | None,
        device_type: str,
        stop_flag: Any = None,
    ):
        """
        Initialize the SPR calibrator.
        
        Args:
            ctrl: LED and polarizer controller
            usb: USB4000 spectrometer
            device_type: Device type string ('PicoP4SPR', 'PicoEZSPR', etc.)
            stop_flag: Optional threading event to signal stop
        """
        self.ctrl = ctrl
        self.usb = usb
        self.device_type = device_type
        self.stop_flag = stop_flag
        self.state = CalibrationState()
        
        # Progress callback (can be set externally)
        self.progress_callback: Optional[Callable[[int, str], None]] = None
    
    def set_progress_callback(self, callback: Callable[[int, str], None]) -> None:
        """Set callback for progress updates."""
        self.progress_callback = callback
    
    def _emit_progress(self, step: int, message: str) -> None:
        """Emit progress update if callback is set."""
        if self.progress_callback is not None:
            self.progress_callback(step, message)
    
    def _is_stopped(self) -> bool:
        """Check if stop has been requested."""
        if self.stop_flag is None:
            return False
        return self.stop_flag.is_set()
    
    # ========================================================================
    # STEP 1: WAVELENGTH RANGE CALIBRATION
    # ========================================================================
    
    def calibrate_wavelength_range(self) -> tuple[bool, float]:
        """
        Calibrate wavelength range and calculate Fourier weights.
        
        Returns:
            Tuple of (success, integration_step)
        """
        try:
            if self.device_type not in DEVICES:
                logger.error(f"Unrecognized controller: {self.device_type}")
                return False, 1.0
            
            if self.usb is None:
                logger.error("USB spectrometer not available")
                return False, 1.0
            
            serial_number = self.usb.serial_number
            logger.debug(f"Spectrometer serial number: {serial_number}")
            
            wave_data = self.usb.read_wavelength()
            if wave_data is None or len(wave_data) == 0:
                logger.error("Failed to read wavelength data")
                return False, 1.0
            
            # Apply serial-specific corrections
            if serial_number == "FLMT06715":
                wave_data = wave_data + 20
            
            integration_step = 2.5 if serial_number == "FLMT09793" else 1.0
            
            # Find wavelength range indices with bounds checking
            if len(wave_data) < 2:
                logger.error("Insufficient wavelength data")
                return False, integration_step
            
            # Find minimum wavelength index
            index = 0
            while index < len(wave_data) and wave_data[index] < MIN_WAVELENGTH:
                index += 1
            
            if index >= len(wave_data):
                logger.error(f"No wavelengths above {MIN_WAVELENGTH}nm found")
                return False, integration_step
            
            self.state.wave_min_index = index
            
            # Find maximum wavelength index
            while index < len(wave_data) - 1 and wave_data[index] < MAX_WAVELENGTH:
                index += 1
            
            self.state.wave_max_index = index
            
            if self.state.wave_min_index >= self.state.wave_max_index:
                logger.error(
                    f"Invalid wavelength range: "
                    f"min={self.state.wave_min_index}, max={self.state.wave_max_index}"
                )
                return False, integration_step
            
            # Extract wavelength range
            self.state.wave_data = wave_data[
                self.state.wave_min_index : self.state.wave_max_index
            ]
            
            logger.debug(
                f"Wavelength range: {self.state.wave_min_index} to {self.state.wave_max_index} "
                f"({len(self.state.wave_data)} points)"
            )
            
            # Calculate Fourier transform weights for smoothing
            alpha = 9e3
            n = len(self.state.wave_data) - 1
            if n <= 0:
                logger.error("Invalid wavelength data length for Fourier weights")
                return False, integration_step
            
            phi = np.pi / n * np.arange(1, n)
            phi2 = phi**2
            self.state.fourier_weights = phi / (1 + alpha * phi2 * (1 + phi2))
            
            logger.debug("Wavelength calibration complete")
            return True, integration_step
            
        except Exception as e:
            logger.exception(f"Error in wavelength calibration: {e}")
            return False, 1.0
    
    # ========================================================================
    # STEP 3: INTEGRATION TIME CALIBRATION
    # ========================================================================
    
    def calibrate_integration_time(
        self,
        ch_list: list[str],
        integration_step: float,
    ) -> bool:
        """
        Calibrate integration time to optimize signal across all channels.
        
        Args:
            ch_list: List of channels to calibrate
            integration_step: Step size for integration time adjustments
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.ctrl is None or self.usb is None:
                return False
            
            # Set initial mode and turn off channels
            self.ctrl.set_mode(mode="s")
            time.sleep(0.5)
            self.ctrl.turn_off_channels()
            
            # Set minimum integration time
            self.state.integration = deepcopy(MIN_INTEGRATION)
            self.usb.set_integration(self.state.integration)
            time.sleep(0.1)
            
            max_int = deepcopy(MAX_INTEGRATION)
            
            # Increase integration time for weak channels
            for ch in ch_list:
                if self._is_stopped():
                    return False
                
                logger.debug(f"Checking integration time for channel {ch}")
                self.ctrl.set_intensity(ch=ch, raw_val=S_LED_INT)
                time.sleep(LED_DELAY)
                
                int_array = self.usb.read_intensity()
                if int_array is None:
                    logger.error(f"Failed to read intensity for channel {ch}")
                    continue
                
                time.sleep(LED_DELAY)
                current_count = int_array[
                    self.state.wave_min_index : self.state.wave_max_index
                ].max()
                
                # Increase integration time if signal is weak
                while current_count < S_COUNT_MAX and self.state.integration < max_int:
                    self.state.integration += integration_step
                    logger.debug(f"Increasing integration time to {self.state.integration}ms")
                    
                    self.usb.set_integration(self.state.integration)
                    time.sleep(0.02)
                    
                    int_array = self.usb.read_intensity()
                    if int_array is None:
                        break
                    
                    current_count = int_array[
                        self.state.wave_min_index : self.state.wave_max_index
                    ].max()
            
            # Check for saturation at low intensity
            for ch in ch_list:
                if self._is_stopped():
                    return False
                
                logger.debug(f"Checking saturation for channel {ch}")
                self.ctrl.set_intensity(ch=ch, raw_val=S_LED_MIN)
                time.sleep(LED_DELAY)
                
                int_array = self.usb.read_intensity()
                if int_array is None:
                    continue
                
                current_count = int_array[
                    self.state.wave_min_index : self.state.wave_max_index
                ].max()
                logger.debug(f"Saturation check: {current_count}, limit: {S_COUNT_MAX}")
                
                # Decrease integration time if saturated
                while (
                    current_count > S_COUNT_MAX
                    and self.state.integration > MIN_INTEGRATION
                ):
                    self.state.integration -= integration_step
                    if self.state.integration < max_int:
                        max_int = deepcopy(self.state.integration)
                    
                    logger.debug(f"Decreasing integration time to {self.state.integration}ms")
                    
                    self.usb.set_integration(self.state.integration)
                    time.sleep(0.02)
                    
                    int_array = self.usb.read_intensity()
                    if int_array is None:
                        break
                    
                    current_count = int_array[
                        self.state.wave_min_index : self.state.wave_max_index
                    ].max()
            
            logger.debug(f"Final integration time: {self.state.integration}ms")
            
            # Calculate number of scans to average (MAX_READ_TIME from settings)
            MAX_READ_TIME = 50  # milliseconds (from settings import may fail)
            self.state.num_scans = int(MAX_READ_TIME / self.state.integration)
            logger.debug(f"Scans to average: {self.state.num_scans}")
            
            return True
            
        except Exception as e:
            logger.exception(f"Error calibrating integration time: {e}")
            return False
    
    # ========================================================================
    # STEP 4: LED INTENSITY CALIBRATION (S-MODE)
    # ========================================================================
    
    def calibrate_led_s_mode(self, ch: str) -> bool:
        """
        Calibrate LED intensity for a single channel in S-polarization mode.
        
        Args:
            ch: Channel identifier ('a', 'b', 'c', or 'd')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.ctrl is None or self.usb is None:
                return False
            
            logger.debug(f"Calibrating LED {ch} in S-mode...")
            
            # Start at maximum intensity for S-polarized light
            intensity = deepcopy(P_LED_MAX)
            self.ctrl.set_intensity(ch=ch, raw_val=intensity)
            time.sleep(LED_DELAY)
            
            calibration_max = self.usb.read_intensity()[
                self.state.wave_min_index : self.state.wave_max_index
            ].max()
            
            logger.debug(f"Initial intensity: {intensity} = {calibration_max} counts")
            
            # Coarse adjustment (step by 20)
            while (
                calibration_max > S_COUNT_MAX 
                and intensity > COARSE_ADJUSTMENT
                and not self._is_stopped()
            ):
                intensity -= COARSE_ADJUSTMENT
                self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                time.sleep(LED_DELAY)
                
                calibration_max = self.usb.read_intensity()[
                    self.state.wave_min_index : self.state.wave_max_index
                ].max()
            
            logger.debug(f"After coarse adjust: {intensity} = {calibration_max} counts")
            
            # Medium adjustment (step by 5)
            while (
                calibration_max < S_COUNT_MAX 
                and intensity < P_LED_MAX
                and not self._is_stopped()
            ):
                intensity += MEDIUM_ADJUSTMENT
                self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                time.sleep(LED_DELAY)
                
                calibration_max = self.usb.read_intensity()[
                    self.state.wave_min_index : self.state.wave_max_index
                ].max()
            
            logger.debug(f"After medium adjust: {intensity} = {calibration_max} counts")
            
            # Fine adjustment (step by 1)
            while (
                calibration_max > S_COUNT_MAX 
                and intensity > FINE_ADJUSTMENT + 1
            ):
                intensity -= FINE_ADJUSTMENT
                self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                time.sleep(LED_DELAY)
                
                calibration_max = self.usb.read_intensity()[
                    self.state.wave_min_index : self.state.wave_max_index
                ].max()
            
            logger.debug(f"After fine adjust: {intensity} = {calibration_max} counts")
            
            # Store calibrated intensity
            self.state.ref_intensity[ch] = deepcopy(intensity)
            return True
            
        except Exception as e:
            logger.exception(f"Error calibrating LED {ch} in S-mode: {e}")
            return False
    
    # ========================================================================
    # STEP 5: DARK NOISE MEASUREMENT
    # ========================================================================
    
    def measure_dark_noise(self) -> bool:
        """
        Measure dark noise with all LEDs off.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.ctrl is None or self.usb is None:
                return False
            
            self.ctrl.turn_off_channels()
            time.sleep(LED_DELAY)
            
            # Adjust scan count based on integration time
            if self.state.integration < INTEGRATION_STEP_THRESHOLD:
                dark_scans = DARK_NOISE_SCANS
            else:
                dark_scans = int(DARK_NOISE_SCANS / 2)
            
            logger.debug(f"Measuring dark noise with {dark_scans} scans")
            
            dark_noise_sum = np.zeros(
                self.state.wave_max_index - self.state.wave_min_index
            )
            
            for _scan in range(dark_scans):
                if self._is_stopped():
                    return False
                
                intensity = self.usb.read_intensity()
                if intensity is None:
                    logger.error("Failed to read intensity for dark noise")
                    return False
                
                dark_noise_single = intensity[
                    self.state.wave_min_index : self.state.wave_max_index
                ]
                dark_noise_sum += dark_noise_single
            
            self.state.dark_noise = dark_noise_sum / dark_scans
            
            logger.debug(
                f"Dark noise measurement complete. Max: {max(self.state.dark_noise):.1f} counts"
            )
            return True
            
        except Exception as e:
            logger.exception(f"Error measuring dark noise: {e}")
            return False
    
    # ========================================================================
    # STEP 6: REFERENCE SIGNAL MEASUREMENT
    # ========================================================================
    
    def measure_reference_signals(self, ch_list: list[str]) -> bool:
        """
        Measure reference signals in S-mode for all channels.
        
        Args:
            ch_list: List of channels to measure
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.ctrl is None or self.usb is None:
                return False
            
            self.ctrl.set_mode(mode="s")
            time.sleep(0.4)
            
            for ch in ch_list:
                if self._is_stopped():
                    return False
                
                logger.debug(f"Measuring reference signal for channel {ch}")
                
                self.ctrl.set_intensity(ch=ch, raw_val=self.state.ref_intensity[ch])
                time.sleep(LED_DELAY)
                
                # Adjust scan count based on integration time
                if self.state.integration < INTEGRATION_STEP_THRESHOLD:
                    ref_scans = REF_SCANS
                else:
                    ref_scans = int(REF_SCANS / 2)
                
                ref_data_sum = np.zeros_like(self.state.dark_noise)
                
                for _scan in range(ref_scans):
                    if self._is_stopped():
                        return False
                    
                    int_val = self.usb.read_intensity()
                    if int_val is None:
                        logger.error(f"Failed to read intensity for channel {ch}")
                        return False
                    
                    ref_data_single = (
                        int_val[self.state.wave_min_index : self.state.wave_max_index] 
                        - self.state.dark_noise
                    )
                    ref_data_sum += ref_data_single
                
                self.state.ref_sig[ch] = deepcopy(ref_data_sum / ref_scans)
                
                logger.debug(
                    f"Channel {ch} reference signal: max={max(self.state.ref_sig[ch]):.1f} counts"
                )
            
            return True
            
        except Exception as e:
            logger.exception(f"Error measuring reference signals: {e}")
            return False
    
    # ========================================================================
    # STEP 8: LED INTENSITY CALIBRATION (P-MODE)
    # ========================================================================
    
    def calibrate_led_p_mode(self, ch_list: list[str]) -> bool:
        """
        Fine-tune LED intensities in P-polarization mode.
        
        Args:
            ch_list: List of channels to calibrate
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.ctrl is None or self.usb is None:
                return False
            
            for ch in ch_list:
                if self._is_stopped():
                    return False
                
                logger.debug(f"Fine-tuning LED {ch} in P-mode...")
                
                p_intensity = deepcopy(self.state.ref_intensity[ch])
                self.ctrl.set_intensity(ch=ch, raw_val=p_intensity)
                time.sleep(LED_DELAY)
                
                calibration_max = self.usb.read_intensity()[
                    self.state.wave_min_index : self.state.wave_max_index
                ].max()
                
                initial_counts = deepcopy(calibration_max)
                logger.debug(f"Initial counts in P-mode: {initial_counts}")
                
                # Coarse adjustment (increase to target)
                target_counts = initial_counts * P_MAX_INCREASE
                while (
                    calibration_max < target_counts
                    and calibration_max < S_COUNT_MAX
                    and p_intensity < (P_LED_MAX - COARSE_ADJUSTMENT)
                ):
                    p_intensity += COARSE_ADJUSTMENT
                    self.ctrl.set_intensity(ch=ch, raw_val=p_intensity)
                    time.sleep(LED_DELAY)
                    
                    calibration_max = self.usb.read_intensity()[
                        self.state.wave_min_index : self.state.wave_max_index
                    ].max()
                
                logger.debug(f"After coarse adjust: {p_intensity} = {calibration_max} counts")
                
                # Medium adjustment (decrease if over target)
                while (
                    calibration_max > target_counts
                    and p_intensity > MEDIUM_ADJUSTMENT
                ):
                    p_intensity -= MEDIUM_ADJUSTMENT
                    self.ctrl.set_intensity(ch=ch, raw_val=p_intensity)
                    time.sleep(LED_DELAY)
                    
                    calibration_max = self.usb.read_intensity()[
                        self.state.wave_min_index : self.state.wave_max_index
                    ].max()
                
                logger.debug(f"After medium adjust: {p_intensity} = {calibration_max} counts")
                
                # Fine adjustment (increase to target)
                while (
                    calibration_max < target_counts
                    and calibration_max < S_COUNT_MAX
                    and p_intensity < P_LED_MAX
                ):
                    p_intensity += FINE_ADJUSTMENT
                    self.ctrl.set_intensity(ch=ch, raw_val=p_intensity)
                    time.sleep(LED_DELAY)
                    
                    calibration_max = self.usb.read_intensity()[
                        self.state.wave_min_index : self.state.wave_max_index
                    ].max()
                
                logger.debug(f"After fine adjust: {p_intensity} = {calibration_max} counts")
                
                # Store calibrated intensity
                self.state.leds_calibrated[ch] = deepcopy(p_intensity)
            
            return True
            
        except Exception as e:
            logger.exception(f"Error calibrating LEDs in P-mode: {e}")
            return False
    
    # ========================================================================
    # STEP 9: VALIDATION
    # ========================================================================
    
    def validate_calibration(self) -> tuple[bool, str]:
        """
        Validate that all channels meet calibration requirements.
        
        Returns:
            Tuple of (success, error_string)
        """
        try:
            if self.ctrl is None or self.usb is None:
                return False, "No devices"
            
            self.state.ch_error_list = []
            
            for ch in CH_LIST:
                if self._is_stopped():
                    break
                
                intensity = self.state.leds_calibrated[ch]
                self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                time.sleep(LED_DELAY)
                
                calibration_max = self.usb.read_intensity()[
                    self.state.wave_min_index : self.state.wave_max_index
                ].max()
                
                if calibration_max < P_COUNT_THRESHOLD:
                    self.state.ch_error_list.append(ch)
                    logger.warning(
                        f"Calibration failed on channel {ch}: "
                        f"intensity={calibration_max:.1f} at LED={intensity} "
                        f"(threshold={P_COUNT_THRESHOLD})"
                    )
            
            # Build error string
            ch_str = ", ".join(self.state.ch_error_list) if self.state.ch_error_list else ""
            calibration_success = len(self.state.ch_error_list) == 0
            
            if calibration_success:
                logger.info("✓ Calibration validation passed for all channels")
                self.state.is_calibrated = True
                self.state.calibration_timestamp = time.time()
            else:
                logger.warning(f"✗ Calibration validation failed for channels: {ch_str}")
            
            return calibration_success, ch_str
            
        except Exception as e:
            logger.exception(f"Error validating calibration: {e}")
            return False, "Validation error"
    
    # ========================================================================
    # FULL CALIBRATION ORCHESTRATION
    # ========================================================================
    
    def run_full_calibration(
        self,
        auto_polarize: bool = False,
        auto_polarize_callback: Optional[Callable[[], None]] = None,
    ) -> tuple[bool, str]:
        """
        Execute the complete 9-step calibration sequence.
        
        Args:
            auto_polarize: Whether to run auto-polarization in step 2
            auto_polarize_callback: Optional callback for auto-polarization
            
        Returns:
            Tuple of (success, error_channels_string)
        """
        try:
            logger.debug("=== Starting full calibration sequence ===")
            
            # Step 1: Wavelength range calibration
            logger.debug("Step 1: Wavelength range calibration")
            self._emit_progress(1, "Calibrating wavelength range...")
            success, integration_step = self.calibrate_wavelength_range()
            if not success or self._is_stopped():
                return False, "Wavelength calibration failed"
            
            # Step 2: Auto-polarize if enabled
            if auto_polarize and not self._is_stopped():
                logger.debug("Step 2: Auto-polarization")
                self._emit_progress(2, "Auto-aligning polarizer...")
                if auto_polarize_callback is not None:
                    auto_polarize_callback()
            
            # Determine which channels to calibrate
            ch_list = CH_LIST
            if self.device_type in ["PicoEZSPR"]:  # EZSPR disabled (obsolete)
                ch_list = EZ_CH_LIST
            
            # Step 3: Integration time calibration
            logger.debug(f"Step 3: Integration time calibration for channels {ch_list}")
            self._emit_progress(3, f"Optimizing integration time ({len(ch_list)} channels)...")
            success = self.calibrate_integration_time(ch_list, integration_step)
            if not success or self._is_stopped():
                return False, "Integration time calibration failed"
            
            # Step 4: LED intensity calibration in S-mode
            logger.debug("Step 4: LED intensity calibration (S-mode)")
            self._emit_progress(4, "Calibrating LED intensities (S-mode)...")
            for ch in ch_list:
                if self._is_stopped():
                    break
                success = self.calibrate_led_s_mode(ch)
                if not success:
                    logger.warning(f"Failed to calibrate LED {ch} in S-mode")
            
            if self._is_stopped():
                return False, "Stopped during S-mode calibration"
            
            logger.debug(f"S-mode LED calibration complete: {self.state.ref_intensity}")
            
            # Step 5: Dark noise measurement
            logger.debug("Step 5: Dark noise measurement")
            self._emit_progress(5, "Measuring dark noise...")
            success = self.measure_dark_noise()
            if not success or self._is_stopped():
                return False, "Dark noise measurement failed"
            
            # Step 6: Reference signal measurement (S-mode)
            logger.debug("Step 6: Reference signal measurement (S-mode)")
            self._emit_progress(6, "Capturing reference signals...")
            success = self.measure_reference_signals(ch_list)
            if not success or self._is_stopped():
                return False, "Reference signal measurement failed"
            
            # Step 7: Switch to P-mode
            logger.debug("Step 7: Switching to P-mode")
            self._emit_progress(7, "Switching to P-polarization mode...")
            if self.ctrl is None:
                return False, "No controller available"
            
            self.ctrl.set_mode(mode="p")
            time.sleep(0.4)
            
            # Step 8: LED intensity calibration (P-mode)
            logger.debug("Step 8: LED intensity calibration (P-mode)")
            self._emit_progress(8, "Fine-tuning LED intensities (P-mode)...")
            success = self.calibrate_led_p_mode(ch_list)
            if not success or self._is_stopped():
                return False, "P-mode LED calibration failed"
            
            logger.debug(f"P-mode LED calibration complete: {self.state.leds_calibrated}")
            
            # Step 9: Validate calibration
            logger.debug("Step 9: Validation")
            self._emit_progress(9, "Validating calibration...")
            calibration_success, ch_error_str = self.validate_calibration()
            
            logger.debug("=== Calibration sequence complete ===")
            return calibration_success, ch_error_str
            
        except Exception as e:
            logger.exception(f"Error during full calibration: {e}")
            return False, f"Exception: {str(e)}"
    
    # ========================================================================
    # CALIBRATION HISTORY LOGGING
    # ========================================================================
    
    def log_calibration_results(
        self,
        success: bool,
        error_channels: str,
        calibrated_channels: list[str],
        device_knx: str = "",
    ) -> None:
        """
        Log calibration results to history files for tracking and analysis.
        
        Args:
            success: Whether calibration was successful
            error_channels: String of channels that failed (comma-separated)
            calibrated_channels: List of channels that were calibrated
            device_knx: KNX device identifier
        """
        try:
            # Create calibration history directory
            history_dir = Path(ROOT_DIR) / "calibration_history"
            history_dir.mkdir(exist_ok=True)
            
            # Prepare log entry
            timestamp = dt.datetime.now(TIME_ZONE)
            log_entry = {
                "timestamp": timestamp.isoformat(),
                "success": success,
                "device_type": self.device_type,
                "device_knx": device_knx,
                "error_channels": error_channels,
                "calibrated_channels": calibrated_channels,
                "integration_time_ms": self.state.integration,
                "num_scans": self.state.num_scans,
                "ref_intensity": self.state.ref_intensity.copy(),
                "leds_calibrated": self.state.leds_calibrated.copy(),
                "wavelength_range": f"{self.state.wave_min_index}-{self.state.wave_max_index}",
            }
            
            # Append to JSON lines file (one JSON object per line)
            history_file = history_dir / "calibration_history.jsonl"
            with history_file.open('a') as f:
                f.write(json.dumps(log_entry) + '\n')
            
            # Also create a dated CSV file for easy viewing
            csv_file = history_dir / f"calibration_log_{timestamp.year}_{timestamp.month:02d}.csv"
            
            # Check if CSV needs header
            needs_header = not csv_file.exists()
            
            with csv_file.open('a', newline='') as f:
                fieldnames = [
                    'Timestamp', 'Success', 'Device', 'Error Channels',
                    'Integration (ms)', 'Num Scans', 'LED A', 'LED B', 'LED C', 'LED D'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                if needs_header:
                    writer.writeheader()
                
                writer.writerow({
                    'Timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'Success': 'Yes' if success else 'No',
                    'Device': self.device_type,
                    'Error Channels': error_channels or 'None',
                    'Integration (ms)': self.state.integration,
                    'Num Scans': self.state.num_scans,
                    'LED A': self.state.leds_calibrated.get('a', 0),
                    'LED B': self.state.leds_calibrated.get('b', 0),
                    'LED C': self.state.leds_calibrated.get('c', 0),
                    'LED D': self.state.leds_calibrated.get('d', 0),
                })
            
            logger.debug(f"Calibration results logged to {history_file}")
            
        except Exception as e:
            logger.exception(f"Error logging calibration results: {e}")
    
    # ========================================================================
    # DATA PROCESSOR CREATION
    # ========================================================================
    
    def create_data_processor(self, med_filt_win: int = 11) -> SPRDataProcessor:
        """
        Create a data processor using calibrated wavelength data.
        
        Args:
            med_filt_win: Median filter window size
            
        Returns:
            Configured SPRDataProcessor instance
        """
        return SPRDataProcessor(
            wave_data=self.state.wave_data,
            fourier_weights=self.state.fourier_weights,
            med_filt_win=med_filt_win,
        )
    
    # ========================================================================
    # CALIBRATION PROFILE MANAGEMENT
    # ========================================================================
    
    def save_profile(
        self, 
        profile_name: str,
        device_type: str
    ) -> bool:
        """
        Save current calibration state to a profile file.
        
        Args:
            profile_name: Name for the profile
            device_type: Device type (e.g., 'picop4spr')
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            profiles_dir = Path(ROOT_DIR) / "calibration_profiles"
            profiles_dir.mkdir(exist_ok=True)
            
            # Build calibration data from state
            calibration_data = {
                "profile_name": profile_name,
                "device_type": device_type,
                "timestamp": time.time(),
                "integration": self.state.integration,
                "num_scans": self.state.num_scans,
                "ref_intensity": self.state.ref_intensity.copy(),
                "leds_calibrated": self.state.leds_calibrated.copy(),
                "wave_min_index": self.state.wave_min_index,
                "wave_max_index": self.state.wave_max_index,
                "led_delay": self.state.led_delay,
                "med_filt_win": self.state.med_filt_win,
            }
            
            # Save to JSON
            profile_path = profiles_dir / f"{profile_name}.json"
            with profile_path.open('w') as f:
                json.dump(calibration_data, f, indent=2)
            
            logger.info(f"Calibration profile saved: {profile_path}")
            return True
            
        except Exception as e:
            logger.exception(f"Error saving calibration profile: {e}")
            return False
    
    def load_profile(
        self, 
        profile_name: str,
        device_type: str | None = None
    ) -> tuple[bool, str]:
        """
        Load calibration state from a profile file.
        
        Args:
            profile_name: Name of profile to load
            device_type: Expected device type (for validation), optional
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            profiles_dir = Path(ROOT_DIR) / "calibration_profiles"
            profile_path = profiles_dir / f"{profile_name}.json"
            
            if not profile_path.exists():
                return False, f"Profile '{profile_name}' not found"
            
            # Load from JSON
            with profile_path.open('r') as f:
                calibration_data = json.load(f)
            
            # Verify device type if provided
            loaded_device = calibration_data.get("device_type")
            if device_type and loaded_device != device_type:
                warning = (f"Profile was created for {loaded_device} "
                          f"but current device is {device_type}")
                logger.warning(warning)
                # Return warning but allow loading
                return True, warning
            
            # Load into state
            self.state.integration = calibration_data.get("integration", MIN_INTEGRATION)
            self.state.num_scans = calibration_data.get("num_scans", 1)
            self.state.ref_intensity = calibration_data.get("ref_intensity", {ch: 0 for ch in CH_LIST})
            self.state.leds_calibrated = calibration_data.get("leds_calibrated", {ch: 0 for ch in CH_LIST})
            self.state.wave_min_index = calibration_data.get("wave_min_index", 0)
            self.state.wave_max_index = calibration_data.get("wave_max_index", 0)
            self.state.led_delay = calibration_data.get("led_delay", LED_DELAY)
            self.state.med_filt_win = calibration_data.get("med_filt_win", 11)
            
            logger.info(f"Calibration profile loaded: {profile_path}")
            return True, "Profile loaded successfully"
            
        except Exception as e:
            logger.exception(f"Error loading calibration profile: {e}")
            return False, f"Failed to load profile: {e}"
    
    def list_profiles(self) -> list[str]:
        """
        Get list of available calibration profile names.
        
        Returns:
            List of profile names (without .json extension)
        """
        profiles_dir = Path(ROOT_DIR) / "calibration_profiles"
        if not profiles_dir.exists():
            return []
        return [p.stem for p in profiles_dir.glob("*.json")]
    
    def apply_profile_to_hardware(
        self,
        ctrl: "PicoP4SPR | PicoEZSPR",
        usb: "USB4000",
        ch_list: list[str] | None = None
    ) -> bool:
        """
        Apply loaded calibration profile to hardware.
        
        Args:
            ctrl: SPR controller instance
            usb: USB4000 spectrometer instance
            ch_list: Channels to apply LED settings to (default: CH_LIST)
            
        Returns:
            True if applied successfully
        """
        try:
            if ch_list is None:
                ch_list = CH_LIST
            
            # Apply integration time
            usb.set_integration(self.state.integration)
            
            # Apply LED intensities
            for ch in ch_list:
                if ch in self.state.leds_calibrated:
                    ctrl.set_intensity(ch=ch, raw_val=self.state.leds_calibrated[ch])
            
            logger.info("Calibration profile applied to hardware")
            return True
            
        except Exception as e:
            logger.exception(f"Error applying profile to hardware: {e}")
            return False
    
    # ========================================================================
    # AUTO-POLARIZATION
    # ========================================================================
    
    def auto_polarize(
        self,
        ctrl: "PicoP4SPR | PicoEZSPR",
        usb: "USB4000"
    ) -> tuple[int, int] | None:
        """
        Automatically find optimal polarizer positions for P and S modes.
        
        Uses peak detection to find the angles where maximum light transmission
        occurs for both polarization modes.
        
        Args:
            ctrl: SPR controller instance
            usb: USB4000 spectrometer instance
            
        Returns:
            Tuple of (s_pos, p_pos) if successful, None if failed
        """
        try:
            from scipy.signal import find_peaks, peak_prominences, peak_widths
            
            # Set initial conditions
            ctrl.set_intensity("a", 255)
            usb.set_integration(max(MIN_INTEGRATION, usb.min_integration))
            
            # Define sweep parameters
            min_angle = 10
            max_angle = 170
            half_range = (max_angle - min_angle) // 2
            angle_step = 5
            steps = half_range // angle_step
            
            # Initialize intensity array
            max_intensities = np.zeros(2 * steps + 1)
            
            # Set starting position
            ctrl.servo_set(half_range + min_angle, max_angle)
            ctrl.set_mode("p")
            ctrl.set_mode("s")
            max_intensities[steps] = usb.read_intensity().max()
            
            # Sweep through angles
            for i in range(steps):
                x = min_angle + angle_step * i
                ctrl.servo_set(s=x, p=x + half_range + angle_step)
                ctrl.set_mode("s")
                max_intensities[i] = usb.read_intensity().max()
                ctrl.set_mode("p")
                max_intensities[i + steps + 1] = usb.read_intensity().max()
            
            # Find peaks and optimal positions
            peaks = find_peaks(max_intensities)[0]
            prominences = peak_prominences(max_intensities, peaks)
            i = prominences[0].argsort()[-2:]
            edges = peak_widths(max_intensities, peaks, 0.05, prominences)[2:4]
            edges = np.array(edges)[:, i]
            
            # Calculate final positions
            p_pos, s_pos = (min_angle + angle_step * edges.mean(0)).astype(int)
            ctrl.servo_set(s_pos, p_pos)
            
            logger.info(f"Auto-polarization complete: s={s_pos}, p={p_pos}")
            return s_pos, p_pos
            
        except Exception as e:
            logger.exception(f"Error during auto-polarization: {e}")
            return None
