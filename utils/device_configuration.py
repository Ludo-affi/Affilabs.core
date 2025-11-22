"""
Device Configuration Management System

Manages device-specific calibration data, hardware parameters, and operational settings.
Configuration persists across sessions and includes:
- Hardware identification (LED PCB model, spectrometer serial, etc.)
- Optical parameters (fiber diameter, polarizer type)
- Timing parameters (LED delays, integration times)
- Calibration data (dark spectra, reference spectra)
- Maintenance tracking (last calibration date, cycle counts)

Configuration file location: config/device_config.json

Author: AI Assistant
Date: October 11, 2025
Version: 1.0
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import numpy as np

from utils.logger import logger


class DeviceConfiguration:
    """
    Manages device-specific configuration and calibration data.

    Configuration includes:
    - Hardware identification (LED PCB model, spectrometer serial)
    - Optical fiber diameter (200 µm or 100 µm)
    - Polarizer type (barrel with 2 fixed windows, or round with continuous rotation)
    - Timing parameters (LED delays, integration times)
    - Calibration data (dark, reference, wavelengths)
    - Frequency limits and safety margins
    - Maintenance tracking
    """

    # Valid configuration values
    VALID_LED_PCB_MODELS = ['luminus_cool_white', 'osram_warm_white']
    VALID_LED_TYPE_CODES = ['LCW', 'OWW']  # Short codes for LED types
    VALID_FIBER_DIAMETERS = [100, 200]  # micrometers
    VALID_LED_MODES = [2, 4]  # number of LEDs
    VALID_POLARIZER_TYPES = ['barrel', 'round']  # barrel (2 fixed windows) or round (continuous rotation)

    # LED type mapping (short code to full name)
    LED_TYPE_MAP = {
        'LCW': 'luminus_cool_white',
        'OWW': 'osram_warm_white'
    }
    LED_TYPE_REVERSE_MAP = {
        'luminus_cool_white': 'LCW',
        'osram_warm_white': 'OWW'
    }

    # Default values
    DEFAULT_CONFIG = {
        'device_info': {
            'config_version': '1.0',
            'created_date': None,
            'last_modified': None,
            'device_id': None,  # User-defined identifier
        },
        'hardware': {
            'led_pcb_model': 'luminus_cool_white',  # or 'osram_warm_white'
            'led_type_code': 'LCW',  # Short code: LCW or OWW
            'led_pcb_serial': None,
            'spectrometer_model': 'Flame-T',
            'spectrometer_serial': None,
            'controller_model': 'Raspberry Pi Pico P4SPR',
            'controller_serial': None,
            'optical_fiber_diameter_um': 200,  # 200 µm or 100 µm
            'polarizer_type': 'barrel',  # 'barrel' (2 fixed windows) or 'round' (continuous rotation)
        },
        'timing_parameters': {
            'led_a_delay_ms': 0,
            'led_b_delay_ms': 0,
            'led_c_delay_ms': 0,
            'led_d_delay_ms': 0,
            'min_integration_time_ms': 50,  # Minimum safe integration time per LED
            'led_rise_fall_time_ms': 5,  # Time for LED to stabilize
        },
        'frequency_limits': {
            '4_led_max_hz': 5.0,
            '4_led_recommended_hz': 2.0,
            '2_led_max_hz': 10.0,
            '2_led_recommended_hz': 5.0,
        },
        'calibration': {
            'dark_calibration_date': None,
            's_mode_calibration_date': None,
            'p_mode_calibration_date': None,
            'factory_calibrated': False,
            'user_calibrated': False,
            'preferred_calibration_mode': 'global',  # 'global' or 'per_channel'
        },
        'maintenance': {
            'last_maintenance_date': None,
            'total_measurement_cycles': 0,
            'led_on_hours': 0.0,
            'next_maintenance_due': None,
        },
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize device configuration.

        Args:
            config_path: Path to configuration file. If None, uses default location.
        """
        if config_path is None:
            # Default location: config/device_config.json
            config_dir = Path(__file__).parent.parent / 'config'
            config_dir.mkdir(exist_ok=True)
            self.config_path = config_dir / 'device_config.json'
        else:
            self.config_path = Path(config_path)

        self.config = self._load_or_create_config()
        logger.info(f"Device configuration loaded from: {self.config_path}")
        self._log_config_summary()

    def _load_or_create_config(self) -> Dict[str, Any]:
        """
        Load configuration from file or create new with defaults.

        Returns:
            Configuration dictionary
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                logger.info(f"Loaded existing configuration from {self.config_path}")

                # Validate and merge with defaults (in case new fields added)
                config = self._merge_with_defaults(config)
                return config
            except Exception as e:
                logger.error(f"Failed to load configuration: {e}")
                logger.warning("Creating new configuration with defaults")
                return self._create_default_config()
        else:
            logger.info("No existing configuration found. Creating new configuration.")
            return self._create_default_config()

    def _create_default_config(self) -> Dict[str, Any]:
        """Create new configuration with default values."""
        import copy
        config = copy.deepcopy(self.DEFAULT_CONFIG)

        # Set timestamps
        now = datetime.now().isoformat()
        config['device_info']['created_date'] = now
        config['device_info']['last_modified'] = now

        return config

    def _merge_with_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge loaded config with defaults to handle new fields.

        Args:
            config: Loaded configuration

        Returns:
            Merged configuration
        """
        import copy
        merged = copy.deepcopy(self.DEFAULT_CONFIG)

        # Deep merge - preserve ALL sections from loaded config, not just defaults
        for section, values in config.items():
            if section in merged:
                if isinstance(values, dict):
                    merged[section].update(values)
                else:
                    merged[section] = values
            else:
                # ✨ CRITICAL: Preserve sections not in defaults (e.g., oem_calibration)
                merged[section] = values

        return merged

    def save(self):
        """Save configuration to file."""
        try:
            # Update last modified timestamp
            self.config['device_info']['last_modified'] = datetime.now().isoformat()

            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Save with nice formatting
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)

            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise

    def to_dict(self) -> Dict[str, Any]:
        """
        Return configuration as dictionary.

        Returns:
            Configuration dictionary
        """
        return self.config.copy()

    def validate(self) -> tuple[bool, List[str]]:
        """
        Validate configuration for consistency and valid values.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Validate LED PCB model
        led_model = self.config['hardware']['led_pcb_model']
        if led_model not in self.VALID_LED_PCB_MODELS:
            errors.append(
                f"Invalid LED PCB model '{led_model}'. "
                f"Valid options: {self.VALID_LED_PCB_MODELS}"
            )

        # Validate optical fiber diameter
        fiber_diameter = self.config['hardware']['optical_fiber_diameter_um']
        if fiber_diameter not in self.VALID_FIBER_DIAMETERS:
            errors.append(
                f"Invalid optical fiber diameter {fiber_diameter} µm. "
                f"Valid options: {self.VALID_FIBER_DIAMETERS} µm"
            )

        # Validate polarizer type
        polarizer_type = self.config['hardware'].get('polarizer_type', 'barrel')  # Default for backward compatibility
        if polarizer_type not in self.VALID_POLARIZER_TYPES:
            errors.append(
                f"Invalid polarizer type '{polarizer_type}'. "
                f"Valid options: {self.VALID_POLARIZER_TYPES}"
            )

        # Validate timing parameters
        min_integration = self.config['timing_parameters']['min_integration_time_ms']
        if min_integration < 1 or min_integration > 1000:
            errors.append(
                f"Invalid min_integration_time_ms: {min_integration}. "
                f"Must be between 1-1000 ms"
            )

        # Validate frequency limits
        freq_4led = self.config['frequency_limits']['4_led_max_hz']
        freq_2led = self.config['frequency_limits']['2_led_max_hz']

        if freq_4led <= 0 or freq_4led > 10:
            errors.append(f"Invalid 4-LED max frequency: {freq_4led} Hz")

        if freq_2led <= 0 or freq_2led > 20:
            errors.append(f"Invalid 2-LED max frequency: {freq_2led} Hz")

        # Check frequency consistency
        if freq_2led <= freq_4led:
            errors.append(
                f"2-LED max frequency ({freq_2led} Hz) should be higher than "
                f"4-LED max frequency ({freq_4led} Hz)"
            )

        is_valid = len(errors) == 0
        return is_valid, errors

    def _log_config_summary(self):
        """Log summary of current configuration."""
        hw = self.config['hardware']
        logger.info("=" * 60)
        logger.info("DEVICE CONFIGURATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"  LED PCB Model: {hw['led_pcb_model']}")
        logger.info(f"  Optical Fiber: {hw['optical_fiber_diameter_um']} µm")
        logger.info(f"  Polarizer Type: {hw.get('polarizer_type', 'barrel')} ({'2 fixed windows' if hw.get('polarizer_type', 'barrel') == 'barrel' else 'continuous rotation'})")
        logger.info(f"  Spectrometer: {hw['spectrometer_model']} (S/N: {hw['spectrometer_serial'] or 'N/A'})")
        logger.info(f"  Controller: {hw['controller_model']}")

        cal = self.config['calibration']
        logger.info(f"  Factory Calibrated: {'Yes' if cal['factory_calibrated'] else 'No'}")
        logger.info(f"  User Calibrated: {'Yes' if cal['user_calibrated'] else 'No'}")

        if cal['dark_calibration_date']:
            logger.info(f"  Last Dark Calibration: {cal['dark_calibration_date']}")

        logger.info("=" * 60)

    # ========================================================================
    # Getter/Setter Methods
    # ========================================================================

    def get_led_pcb_model(self) -> str:
        """Get LED PCB model."""
        return self.config['hardware']['led_pcb_model']

    def set_led_pcb_model(self, model: str):
        """
        Set LED PCB model.

        Args:
            model: 'luminus_cool_white' or 'osram_warm_white'
        """
        if model not in self.VALID_LED_PCB_MODELS:
            raise ValueError(
                f"Invalid LED PCB model '{model}'. "
                f"Valid options: {self.VALID_LED_PCB_MODELS}"
            )
        self.config['hardware']['led_pcb_model'] = model
        logger.info(f"LED PCB model set to: {model}")

    def get_optical_fiber_diameter(self) -> int:
        """Get optical fiber diameter in micrometers."""
        return self.config['hardware']['optical_fiber_diameter_um']

    def set_optical_fiber_diameter(self, diameter_um: int):
        """
        Set optical fiber diameter.

        Args:
            diameter_um: Fiber diameter in micrometers (100 or 200)
        """
        if diameter_um not in self.VALID_FIBER_DIAMETERS:
            raise ValueError(
                f"Invalid fiber diameter {diameter_um} µm. "
                f"Valid options: {self.VALID_FIBER_DIAMETERS} µm"
            )
        self.config['hardware']['optical_fiber_diameter_um'] = diameter_um
        logger.info(f"Optical fiber diameter set to: {diameter_um} µm")

    def get_polarizer_type(self) -> str:
        """Get polarizer type ('barrel' or 'round')."""
        return self.config['hardware'].get('polarizer_type', 'barrel')  # Default to barrel for backward compatibility

    def set_polarizer_type(self, polarizer_type: str):
        """
        Set polarizer type.

        Args:
            polarizer_type: 'barrel' (2 fixed perpendicular windows) or 'round' (continuous rotation)
        """
        if polarizer_type not in self.VALID_POLARIZER_TYPES:
            raise ValueError(
                f"Invalid polarizer type '{polarizer_type}'. "
                f"Valid options: {self.VALID_POLARIZER_TYPES}"
            )
        self.config['hardware']['polarizer_type'] = polarizer_type
        logger.info(f"Polarizer type set to: {polarizer_type}")

    def get_spectrometer_serial(self) -> Optional[str]:
        """Get spectrometer serial number."""
        return self.config['hardware']['spectrometer_serial']

    def set_spectrometer_serial(self, serial: str):
        """Set spectrometer serial number."""
        self.config['hardware']['spectrometer_serial'] = serial
        logger.info(f"Spectrometer serial set to: {serial}")

    def get_min_integration_time(self) -> float:
        """Get minimum integration time in milliseconds."""
        return self.config['timing_parameters']['min_integration_time_ms']

    def set_min_integration_time(self, time_ms: float):
        """Set minimum integration time in milliseconds."""
        if time_ms < 1 or time_ms > 1000:
            raise ValueError("Integration time must be between 1-1000 ms")
        self.config['timing_parameters']['min_integration_time_ms'] = time_ms
        logger.info(f"Min integration time set to: {time_ms} ms")

    def get_led_delays(self) -> Dict[str, float]:
        """Get LED delay times for all channels."""
        tp = self.config['timing_parameters']
        return {
            'a': tp['led_a_delay_ms'],
            'b': tp['led_b_delay_ms'],
            'c': tp['led_c_delay_ms'],
            'd': tp['led_d_delay_ms'],
        }

    def set_led_delays(self, delays: Dict[str, float]):
        """
        Set LED delay times.

        Args:
            delays: Dict with keys 'a', 'b', 'c', 'd' and delay values in ms
        """
        tp = self.config['timing_parameters']
        for channel, delay in delays.items():
            if channel in ['a', 'b', 'c', 'd']:
                tp[f'led_{channel}_delay_ms'] = delay
        logger.info(f"LED delays updated: {delays}")

    def get_frequency_limits(self, num_leds: int) -> Dict[str, float]:
        """
        Get frequency limits for specified LED mode.

        Args:
            num_leds: Number of LEDs (2 or 4)

        Returns:
            Dict with 'max_hz' and 'recommended_hz'
        """
        if num_leds not in self.VALID_LED_MODES:
            raise ValueError(f"Invalid LED mode: {num_leds}. Must be 2 or 4.")

        freq = self.config['frequency_limits']
        return {
            'max_hz': freq[f'{num_leds}_led_max_hz'],
            'recommended_hz': freq[f'{num_leds}_led_recommended_hz'],
        }

    def get_calibration_mode(self) -> str:
        """
        Get preferred calibration mode.

        Returns:
            'global' (traditional LED calibration with global integration time)
            or 'per_channel' (fixed LED=255, per-channel integration times)
        """
        return self.config['calibration'].get('preferred_calibration_mode', 'global')

    def set_calibration_mode(self, mode: str):
        """
        Set preferred calibration mode.

        Args:
            mode: 'global' or 'per_channel'

        Raises:
            ValueError: If mode is not valid
        """
        if mode not in ['global', 'per_channel']:
            raise ValueError(f"Invalid calibration mode: {mode}. Must be 'global' or 'per_channel'")

        self.config['calibration']['preferred_calibration_mode'] = mode
        self.save()
        logger.info(f"Calibration mode set to: {mode}")

    def is_factory_calibrated(self) -> bool:
        """Check if device has factory calibration."""
        return self.config['calibration']['factory_calibrated']

    def is_user_calibrated(self) -> bool:
        """Check if device has user calibration."""
        return self.config['calibration']['user_calibrated']

    def mark_calibrated(self, calibration_type: str):
        """
        Mark device as calibrated.

        Args:
            calibration_type: 'factory', 'dark', 's_mode', or 'p_mode'
        """
        now = datetime.now().isoformat()
        cal = self.config['calibration']

        if calibration_type == 'factory':
            cal['factory_calibrated'] = True
        elif calibration_type == 'dark':
            cal['dark_calibration_date'] = now
        elif calibration_type == 's_mode':
            cal['s_mode_calibration_date'] = now
            cal['user_calibrated'] = True
        elif calibration_type == 'p_mode':
            cal['p_mode_calibration_date'] = now
            cal['user_calibrated'] = True
        else:
            raise ValueError(f"Invalid calibration type: {calibration_type}")

        logger.info(f"Device marked as {calibration_type} calibrated at {now}")

    def increment_measurement_cycles(self, count: int = 1):
        """Increment total measurement cycle counter."""
        self.config['maintenance']['total_measurement_cycles'] += count

    def add_led_on_time(self, hours: float):
        """Add to LED on-time counter."""
        self.config['maintenance']['led_on_hours'] += hours

    def export_config(self, export_path: str):
        """
        Export configuration to specified path (for backup).

        Args:
            export_path: Path to save exported configuration
        """
        try:
            with open(export_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Configuration exported to: {export_path}")
        except Exception as e:
            logger.error(f"Failed to export configuration: {e}")
            raise

    def import_config(self, import_path: str):
        """
        Import configuration from specified path.

        Args:
            import_path: Path to configuration file to import
        """
        try:
            with open(import_path, 'r') as f:
                imported_config = json.load(f)

            # Validate imported config
            self.config = self._merge_with_defaults(imported_config)
            is_valid, errors = self.validate()

            if not is_valid:
                logger.error("Imported configuration is invalid:")
                for error in errors:
                    logger.error(f"  - {error}")
                raise ValueError("Invalid configuration")

            logger.info(f"Configuration imported from: {import_path}")
            self._log_config_summary()

        except Exception as e:
            logger.error(f"Failed to import configuration: {e}")
            raise

    def reset_to_defaults(self):
        """Reset configuration to factory defaults."""
        logger.warning("Resetting configuration to defaults...")
        self.config = self._create_default_config()
        logger.info("Configuration reset to defaults")
        self._log_config_summary()

    # ========================================================================
    # LED CALIBRATION STORAGE (SINGLE SOURCE OF TRUTH)
    # ========================================================================

    def save_dark_snapshot(self, dark_spectrum: np.ndarray) -> None:
        """Save a pre-QC dark snapshot to device_config.json.

        Stores a dark spectrum captured prior to QC validation so that QC and
        subsequent sessions can reuse a known-good dark reference.

        Adds the following fields under 'led_calibration':
        - pre_qc_dark_snapshot: list[float]
        - pre_qc_dark_date: ISO timestamp
        - pre_qc_dark_min: float
        - pre_qc_dark_max: float

        Also updates 'calibration.dark_calibration_date'.
        """
        try:
            if dark_spectrum is None or len(dark_spectrum) == 0:
                logger.warning("Attempted to save empty dark snapshot; skipping")
                return

            # Ensure container exists
            if 'led_calibration' not in self.config:
                self.config['led_calibration'] = {}

            dark_min = float(np.min(dark_spectrum))
            dark_max = float(np.max(dark_spectrum))
            now = datetime.now().isoformat()

            # Persist snapshot and stats
            self.config['led_calibration']['pre_qc_dark_snapshot'] = dark_spectrum.tolist()
            self.config['led_calibration']['pre_qc_dark_date'] = now
            self.config['led_calibration']['pre_qc_dark_min'] = dark_min
            self.config['led_calibration']['pre_qc_dark_max'] = dark_max

            # Update top-level calibration date for dark
            if 'calibration' not in self.config:
                self.config['calibration'] = {}
            self.config['calibration']['dark_calibration_date'] = now

            # Persist to disk
            self.save()

            # Log and flag if any negatives
            if dark_min < 0:
                logger.error(
                    f"⚠️ Dark snapshot contains negative values (min={dark_min:.2f}). "
                    f"This indicates possible offset or subtraction error."
                )
            logger.info(
                f"💾 Pre-QC dark snapshot saved: len={len(dark_spectrum)}, "
                f"min={dark_min:.1f}, max={dark_max:.1f}"
            )

        except Exception as e:
            logger.error(f"Failed to save dark snapshot: {e}")
            raise

    def save_led_calibration(
        self,
        integration_time_ms: int,
        s_mode_intensities: Dict[str, int],
        p_mode_intensities: Dict[str, int],
        s_ref_spectra: Dict[str, np.ndarray],
        s_ref_wavelengths: Optional[np.ndarray] = None,
        live_boost_integration_ms: Optional[int] = None,
        live_boost_led_intensities: Optional[Dict[str, int]] = None,
        live_boost_factor: Optional[float] = None
    ) -> None:
        """
        Save LED calibration baseline to device_config.json (single source of truth).

        This stores calibrated LED intensities, integration time, and S-mode reference
        spectra for quick QC validation. Replaces any existing calibration data.

        CRITICAL FOR QC VALIDATION:
        The S-ref spectra saved here are captured AFTER live mode boost optimization.
        This ensures QC validation compares against the actual live running parameters,
        not the calibration baseline.

        Args:
            integration_time_ms: Calibrated integration time in milliseconds (S-mode baseline)
            s_mode_intensities: S-mode LED intensities per channel {'A': 128, ...}
            p_mode_intensities: P-mode LED intensities per channel {'A': 172, ...}
            s_ref_spectra: S-mode reference spectra per channel (AFTER boost if provided)
            s_ref_wavelengths: Optional wavelength array (stored separately if provided)
            live_boost_integration_ms: Optional boosted integration time for live mode (P-mode)
            live_boost_led_intensities: Optional boosted LED intensities for live mode
            live_boost_factor: Optional boost factor applied (e.g., 1.5× for 50% → 75%)
        """
        try:
            logger.info("💾 Saving LED calibration to device_config.json (single source of truth)")

            # Create/update led_calibration section
            self.config['led_calibration'] = {
                'calibration_date': datetime.now().isoformat(),
                'integration_time_ms': int(integration_time_ms),
                's_mode_intensities': {ch: int(val) for ch, val in s_mode_intensities.items()},
                'p_mode_intensities': {ch: int(val) for ch, val in p_mode_intensities.items()},
                's_ref_baseline': {
                    ch: spec.tolist() for ch, spec in s_ref_spectra.items()
                },
                's_ref_max_intensity': {
                    ch: float(np.max(spec)) for ch, spec in s_ref_spectra.items()
                }
            }

            # Store live mode boost parameters (for QC validation)
            if live_boost_integration_ms is not None:
                self.config['led_calibration']['live_boost_integration_ms'] = int(live_boost_integration_ms)
                logger.info(f"   Live boost integration: {live_boost_integration_ms} ms")

            if live_boost_led_intensities is not None:
                self.config['led_calibration']['live_boost_led_intensities'] = {
                    ch: int(val) for ch, val in live_boost_led_intensities.items()
                }
                logger.info(f"   Live boost LEDs: {live_boost_led_intensities}")

            if live_boost_factor is not None:
                self.config['led_calibration']['live_boost_factor'] = float(live_boost_factor)
                logger.info(f"   Live boost factor: {live_boost_factor:.2f}×")

            # Store wavelengths if provided (for reference)
            if s_ref_wavelengths is not None:
                self.config['led_calibration']['s_ref_wavelengths'] = s_ref_wavelengths.tolist()

            # Update calibration status
            self.config['calibration']['s_mode_calibration_date'] = datetime.now().isoformat()
            self.config['calibration']['user_calibrated'] = True

            # Save to disk
            self.save()

            logger.info("✅ LED calibration saved successfully")
            logger.info(f"   Calibration baseline:")
            logger.info(f"      Integration time: {integration_time_ms} ms")
            logger.info(f"      S-mode LEDs: {s_mode_intensities}")
            logger.info(f"      P-mode LEDs: {p_mode_intensities}")
            if live_boost_integration_ms:
                logger.info(f"   Live mode boost:")
                logger.info(f"      Integration time: {live_boost_integration_ms} ms ({live_boost_factor:.2f}× boost)")
                logger.info(f"      Adjusted LEDs: {live_boost_led_intensities}")
            logger.info(f"   S-ref baseline: {len(s_ref_spectra)} channels × {len(next(iter(s_ref_spectra.values())))} pixels")

        except Exception as e:
            logger.error(f"Failed to save LED calibration: {e}")
            raise

    def load_led_calibration(self) -> Optional[Dict[str, Any]]:
        """
        Load LED calibration baseline from device_config.json.

        Returns:
            Dictionary containing calibration data:
            - calibration_date: ISO timestamp
            - integration_time_ms: int
            - s_mode_intensities: dict
            - p_mode_intensities: dict
            - s_ref_baseline: dict of numpy arrays
            - s_ref_max_intensity: dict of float
            - s_ref_wavelengths: numpy array (if available)

            Returns None if no calibration stored.
        """
        if 'led_calibration' not in self.config:
            logger.debug("No LED calibration found in device_config.json")
            return None

        try:
            cal = self.config['led_calibration'].copy()

            # Convert lists back to numpy arrays
            if 's_ref_baseline' in cal:
                cal['s_ref_baseline'] = {
                    ch: np.array(spec) for ch, spec in cal['s_ref_baseline'].items()
                }

            if 's_ref_wavelengths' in cal:
                cal['s_ref_wavelengths'] = np.array(cal['s_ref_wavelengths'])

            # Optional: pre-QC dark snapshot
            if 'pre_qc_dark_snapshot' in cal and isinstance(cal['pre_qc_dark_snapshot'], list):
                try:
                    cal['pre_qc_dark_snapshot'] = np.array(cal['pre_qc_dark_snapshot'])
                except Exception:
                    # Leave as-is if conversion fails
                    pass

            logger.debug(f"Loaded LED calibration from {cal['calibration_date']}")
            return cal

        except Exception as e:
            logger.error(f"Failed to load LED calibration: {e}")
            return None

    def get_calibration_age_days(self) -> Optional[float]:
        """
        Get age of stored calibration in days.

        Returns:
            Age in days, or None if no calibration stored
        """
        cal = self.load_led_calibration()
        if cal is None:
            return None

        try:
            cal_date = datetime.fromisoformat(cal['calibration_date'])
            age = (datetime.now() - cal_date).total_seconds() / 86400.0
            return age
        except Exception:
            return None

    def clear_led_calibration(self) -> None:
        """Clear stored LED calibration data."""
        if 'led_calibration' in self.config:
            del self.config['led_calibration']
            self.save()
            logger.info("Cleared LED calibration from device_config.json")

    # ========================================================================
    # DIAGNOSTICS STORAGE (LED RANKING FROM CALIBRATION STEP)
    # ========================================================================

    def save_led_ranking_diagnostics(
        self,
        weakest_channel: str,
        ranked_channels: list[tuple[str, tuple[float, float, bool]]],
        percent_of_weakest: dict[str, float],
        mean_counts: Optional[dict[str, float]] = None,
        saturated_on_first_pass: Optional[list[str]] = None,
        test_led_intensity: Optional[int] = None,
        test_region_nm: Optional[tuple[float, float]] = None,
    ) -> None:
        """Save LED ranking diagnostics to device_config.json.

        Stores the LED brightness ranking results from calibration as
        percent-of-weakest for maintenance/diagnostics.

        Args:
            weakest_channel: Channel id of weakest (e.g., 'a')
            ranked_channels: List of (channel, (mean, max, was_saturated)) sorted weakest→strongest
            percent_of_weakest: Mapping channel→percent relative to weakest (weakest = 100.0)
            mean_counts: Optional mapping channel→mean counts used to compute percentages
            saturated_on_first_pass: Optional list of channels that saturated at initial test intensity
            test_led_intensity: Optional test LED value used during ranking (e.g., 128)
            test_region_nm: Optional (min_nm, max_nm) region used for ranking
        """
        try:
            now = datetime.now().isoformat()

            # Ensure diagnostics section exists
            if 'diagnostics' not in self.config:
                self.config['diagnostics'] = {}

            # Build a compact ranked order list
            ranked_order = [ch for ch, _ in ranked_channels]

            self.config['diagnostics']['led_ranking'] = {
                'date': now,
                'weakest_channel': weakest_channel,
                'ranked_order': ranked_order,
                'percent_of_weakest': {k: float(v) for k, v in percent_of_weakest.items()},
            }

            if mean_counts is not None:
                self.config['diagnostics']['led_ranking']['mean_counts'] = {
                    k: float(v) for k, v in mean_counts.items()
                }

            if saturated_on_first_pass is not None:
                self.config['diagnostics']['led_ranking']['saturated_on_first_pass'] = list(saturated_on_first_pass)

            if test_led_intensity is not None:
                self.config['diagnostics']['led_ranking']['test_led_intensity'] = int(test_led_intensity)

            if test_region_nm is not None:
                self.config['diagnostics']['led_ranking']['test_region_nm'] = [
                    float(test_region_nm[0]), float(test_region_nm[1])
                ]

            # Persist to disk
            self.save()
            logger.info("✅ Saved LED ranking diagnostics to device_config.json → diagnostics.led_ranking")

        except Exception as e:
            logger.error(f"Failed to save LED ranking diagnostics: {e}")
            # Don't raise to avoid breaking calibration; diagnostics are optional


def get_device_config(config_path: Optional[str] = None) -> DeviceConfiguration:
    """
    Get device configuration instance (convenience function).

    Args:
        config_path: Optional path to configuration file

    Returns:
        DeviceConfiguration instance
    """
    return DeviceConfiguration(config_path)


if __name__ == "__main__":
    # Example usage and testing
    print("\n" + "=" * 70)
    print("DEVICE CONFIGURATION SYSTEM TEST")
    print("=" * 70)

    # Create configuration
    config = DeviceConfiguration()

    # Set some values
    print("\n📝 Setting configuration values...")
    config.set_optical_fiber_diameter(200)
    config.set_led_pcb_model('luminus_cool_white')
    config.set_spectrometer_serial('FLMT09788')

    # Get values
    print("\n📊 Current configuration:")
    print(f"  Fiber diameter: {config.get_optical_fiber_diameter()} µm")
    print(f"  LED PCB model: {config.get_led_pcb_model()}")
    print(f"  Spectrometer: {config.get_spectrometer_serial()}")

    # Validate
    print("\n✅ Validating configuration...")
    is_valid, errors = config.validate()
    if is_valid:
        print("  Configuration is VALID ✅")
    else:
        print("  Configuration has errors:")
        for error in errors:
            print(f"    - {error}")

    # Save
    print("\n💾 Saving configuration...")
    config.save()
    print(f"  Saved to: {config.config_path}")

    # Test fiber diameter validation
    print("\n🧪 Testing fiber diameter validation...")
    try:
        config.set_optical_fiber_diameter(150)  # Invalid
    except ValueError as e:
        print(f"  ✅ Correctly rejected invalid value: {e}")

    # Test frequency limits
    print("\n📈 Frequency limits:")
    for num_leds in [2, 4]:
        limits = config.get_frequency_limits(num_leds)
        print(f"  {num_leds}-LED mode: Max {limits['max_hz']} Hz, Recommended {limits['recommended_hz']} Hz")

    print("\n" + "=" * 70)
    print("TEST COMPLETE ✅")
    print("=" * 70)
