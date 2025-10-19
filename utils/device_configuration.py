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
    VALID_FIBER_DIAMETERS = [100, 200]  # micrometers
    VALID_LED_MODES = [2, 4]  # number of LEDs
    VALID_POLARIZER_TYPES = ['barrel', 'round']  # barrel (2 fixed windows) or round (continuous rotation)

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
