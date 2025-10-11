"""Detector Configuration Manager - Auto-detects and loads detector profiles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

from utils.logger import logger


@dataclass
class DetectorProfile:
    """Detector configuration profile."""

    # Detector info
    manufacturer: str
    model: str
    serial_number: str
    description: str

    # Hardware specs
    pixel_count: int
    wavelength_min_nm: float
    wavelength_max_nm: float
    detector_type: str

    # Acquisition limits
    max_intensity_counts: int
    saturation_counts: int
    min_integration_time_ms: float
    max_integration_time_ms: float
    recommended_integration_time_ms: float
    integration_step_ms: float  # Step size for integration time adjustments during calibration

    # Calibration targets
    target_signal_counts: int
    signal_tolerance_counts: int
    dark_noise_scans: int
    led_characterization_points: list[int]
    max_calibration_iterations: int

    # SPR settings
    spr_wavelength_min_nm: int
    spr_wavelength_max_nm: int
    expected_filtered_pixels: int
    spr_peak_min_nm: int
    spr_peak_max_nm: int

    # Performance
    typical_snr: int
    dark_noise_mean_counts: float
    dark_noise_std_counts: float
    read_time_ms: float

    # Communication
    interface: str
    driver: str
    auto_detect_string: str
    vendor_id: str
    product_id: str

    # Original profile path
    profile_path: Optional[Path] = None


class DetectorManager:
    """Manages detector profiles and auto-detection."""

    PROFILES_DIR = Path(__file__).parent.parent / "detector_profiles"

    def __init__(self):
        """Initialize detector manager."""
        self.profiles: Dict[str, DetectorProfile] = {}
        self.current_profile: Optional[DetectorProfile] = None
        self._load_all_profiles()

    def _load_all_profiles(self) -> None:
        """Load all detector profiles from JSON files."""
        if not self.PROFILES_DIR.exists():
            logger.warning(f"Detector profiles directory not found: {self.PROFILES_DIR}")
            self.PROFILES_DIR.mkdir(parents=True, exist_ok=True)
            return

        for profile_file in self.PROFILES_DIR.glob("*.json"):
            try:
                profile = self._load_profile(profile_file)
                profile_key = f"{profile.manufacturer}_{profile.model}".lower().replace(" ", "_")
                self.profiles[profile_key] = profile
                logger.info(f"✅ Loaded detector profile: {profile.manufacturer} {profile.model}")
            except Exception as e:
                logger.error(f"❌ Failed to load profile {profile_file.name}: {e}")

    def _load_profile(self, profile_path: Path) -> DetectorProfile:
        """Load a single detector profile from JSON."""
        with open(profile_path, 'r') as f:
            data = json.load(f)

        # Extract nested values
        detector_info = data['detector_info']
        hardware_specs = data['hardware_specs']
        acquisition_limits = data['acquisition_limits']
        calibration_targets = data['calibration_targets']
        spr_settings = data['spr_settings']
        performance = data['performance']
        communication = data['communication']

        return DetectorProfile(
            # Detector info
            manufacturer=detector_info['manufacturer'],
            model=detector_info['model'],
            serial_number=detector_info['serial_number'],
            description=detector_info['description'],

            # Hardware specs
            pixel_count=hardware_specs['pixel_count'],
            wavelength_min_nm=hardware_specs['wavelength_range']['min_nm'],
            wavelength_max_nm=hardware_specs['wavelength_range']['max_nm'],
            detector_type=hardware_specs['detector_type'],

            # Acquisition limits
            max_intensity_counts=acquisition_limits['max_intensity_counts'],
            saturation_counts=acquisition_limits['saturation_counts'],
            min_integration_time_ms=acquisition_limits['min_integration_time_ms'],
            max_integration_time_ms=acquisition_limits['max_integration_time_ms'],
            recommended_integration_time_ms=acquisition_limits['recommended_integration_time_ms'],
            integration_step_ms=acquisition_limits.get('integration_step_ms', 1.0),  # Default 1.0ms if not specified

            # Calibration targets
            target_signal_counts=calibration_targets['target_signal_counts'],
            signal_tolerance_counts=calibration_targets['signal_tolerance_counts'],
            dark_noise_scans=calibration_targets['dark_noise_scans'],
            led_characterization_points=calibration_targets['led_characterization_points'],
            max_calibration_iterations=calibration_targets['max_calibration_iterations'],

            # SPR settings
            spr_wavelength_min_nm=spr_settings['wavelength_range_nm']['min'],
            spr_wavelength_max_nm=spr_settings['wavelength_range_nm']['max'],
            expected_filtered_pixels=spr_settings['expected_filtered_pixels'],
            spr_peak_min_nm=spr_settings['typical_spr_peak_range_nm']['min'],
            spr_peak_max_nm=spr_settings['typical_spr_peak_range_nm']['max'],

            # Performance
            typical_snr=performance['typical_snr'],
            dark_noise_mean_counts=performance['dark_noise_mean_counts'],
            dark_noise_std_counts=performance['dark_noise_std_counts'],
            read_time_ms=performance['read_time_ms'],

            # Communication
            interface=communication['interface'],
            driver=communication['driver'],
            auto_detect_string=communication['auto_detect_string'],
            vendor_id=communication['vendor_id'],
            product_id=communication['product_id'],

            # Store path
            profile_path=profile_path
        )

    def auto_detect(self, usb_device: Any) -> Optional[DetectorProfile]:
        """
        Auto-detect detector profile based on connected device.

        Detection priority:
        1. Serial number (e.g., FLMT for Flame-T)
        2. Model string (fallback)

        Args:
            usb_device: Connected USB spectrometer device

        Returns:
            DetectorProfile if detected, None otherwise
        """
        try:
            # Try to get serial number first (most reliable for Flame-T)
            serial_number = None
            try:
                if hasattr(usb_device, 'get_device_info'):
                    device_info = usb_device.get_device_info()
                    serial_number = device_info.get('serial_number', None)
                elif hasattr(usb_device, 'get_serial_number'):
                    serial_number = usb_device.get_serial_number()
            except Exception as e:
                logger.debug(f"Could not get serial number: {e}")

            # Try to get model string (fallback)
            device_model = None
            if hasattr(usb_device, 'get_model'):
                device_model = usb_device.get_model()
            elif hasattr(usb_device, 'DEVICE_MODEL'):
                device_model = usb_device.DEVICE_MODEL
            elif hasattr(usb_device, '_device') and hasattr(usb_device._device, 'model'):
                device_model = usb_device._device.model

            logger.info(f"🔍 Detecting profile:")
            if serial_number:
                logger.info(f"   Serial Number: {serial_number}")
            if device_model:
                logger.info(f"   Device Model: {device_model}")

            # Match against profiles (serial number takes priority)
            for profile_key, profile in self.profiles.items():
                # Check serial number first (e.g., FLMT for Flame-T)
                if serial_number and profile.auto_detect_string.upper() in serial_number.upper():
                    logger.info(f"✅ Matched by serial number: {profile.manufacturer} {profile.model}")
                    logger.info(f"   Serial starts with: {serial_number[:4]}")
                    self.current_profile = profile
                    return profile

                # Fallback to model string
                if device_model and profile.auto_detect_string.lower() in device_model.lower():
                    logger.info(f"✅ Matched by model string: {profile.manufacturer} {profile.model}")
                    self.current_profile = profile
                    return profile

            # No match found
            logger.warning(f"⚠️ No profile matched")
            if serial_number:
                logger.warning(f"   Serial: {serial_number}")
            if device_model:
                logger.warning(f"   Model: {device_model}")
            return self._get_default_profile()

        except Exception as e:
            logger.error(f"❌ Auto-detection failed: {e}")
            return self._get_default_profile()

    def _get_default_profile(self) -> Optional[DetectorProfile]:
        """Get default detector profile (Flame-T or first available)."""
        # Try Flame-T first
        default_key = "ocean_optics_flame-t"
        if default_key in self.profiles:
            logger.info(f"Using default profile: {self.profiles[default_key].model}")
            self.current_profile = self.profiles[default_key]
            return self.profiles[default_key]

        # Try USB4000 as fallback
        usb4000_key = "ocean_optics_usb4000"
        if usb4000_key in self.profiles:
            logger.info(f"Using fallback profile: {self.profiles[usb4000_key].model}")
            self.current_profile = self.profiles[usb4000_key]
            return self.profiles[usb4000_key]

        # Use any available profile
        if self.profiles:
            first_profile = next(iter(self.profiles.values()))
            logger.warning(f"Using first available profile: {first_profile.model}")
            self.current_profile = first_profile
            return first_profile

        logger.error("❌ No detector profiles available!")
        return None

    def get_profile(self, manufacturer: str, model: str) -> Optional[DetectorProfile]:
        """Get specific detector profile by manufacturer and model."""
        profile_key = f"{manufacturer}_{model}".lower().replace(" ", "_")
        return self.profiles.get(profile_key)

    def get_current_profile(self) -> Optional[DetectorProfile]:
        """Get currently active detector profile."""
        return self.current_profile

    def list_available_profiles(self) -> list[str]:
        """List all available detector profiles."""
        return [f"{p.manufacturer} {p.model}" for p in self.profiles.values()]


# Global detector manager instance
_detector_manager: Optional[DetectorManager] = None


def get_detector_manager() -> DetectorManager:
    """Get global detector manager instance (singleton)."""
    global _detector_manager
    if _detector_manager is None:
        _detector_manager = DetectorManager()
    return _detector_manager


def get_current_detector_profile() -> Optional[DetectorProfile]:
    """Get currently active detector profile."""
    manager = get_detector_manager()
    return manager.get_current_profile()
