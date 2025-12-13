"""Device Configuration Management System.

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
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from affilabs.utils.logger import logger


def _get_setting(name: str, default):
    """Fetch a timing setting from affilabs.settings or fallback.

    Tries `affilabs.settings` first, then top-level `settings`, else returns default.
    This avoids ImportError when package-relative settings are used.
    """
    try:
        from affilabs.settings import __dict__ as affi_settings

        if name in affi_settings:
            return affi_settings[name]
    except Exception:
        pass
    try:
        from settings import __dict__ as root_settings

        if name in root_settings:
            return root_settings[name]
    except Exception:
        pass
    return default


class DeviceConfiguration:
    """Manages device-specific configuration and calibration data.

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
    VALID_LED_PCB_MODELS = ["luminus_cool_white", "osram_warm_white"]
    VALID_LED_TYPE_CODES = ["LCW", "OWW"]  # Short codes for LED types
    VALID_FIBER_DIAMETERS = [100, 200]  # micrometers
    VALID_LED_MODES = [4]  # number of LEDs (all devices use 4 LEDs)
    VALID_POLARIZER_TYPES = [
        "barrel",
        "round",
    ]  # barrel (2 fixed windows) or round (continuous rotation)
    VALID_SERVO_MODELS = ["HS-55MG", "Alternate"]  # Default is HS-55MG

    # LED type mapping (short code to full name)
    LED_TYPE_MAP = {
        "LCW": "luminus_cool_white",
        "OWW": "osram_warm_white",
    }
    LED_TYPE_REVERSE_MAP = {
        "luminus_cool_white": "LCW",
        "osram_warm_white": "OWW",
    }

    # Default values
    DEFAULT_CONFIG = {
        "device_info": {
            "config_version": "1.0",
            "created_date": None,
            "last_modified": None,
            "device_id": None,  # User-defined identifier
        },
        "hardware": {
            "led_pcb_model": "luminus_cool_white",  # or 'osram_warm_white'
            "led_type_code": "LCW",  # Short code: LCW or OWW
            "led_pcb_serial": None,
            "spectrometer_model": "Flame-T",
            "spectrometer_serial": None,
            "controller_model": "Raspberry Pi Pico P4SPR",
            "controller_serial": None,
            "optical_fiber_diameter_um": 200,  # 200 µm or 100 µm
            "polarizer_type": "barrel",  # 'barrel' (2 fixed windows) or 'round' (continuous rotation)
            # Hardware rule: Arduino and PicoP4SPR ALWAYS use 'round'
            "servo_model": "HS-55MG",  # Servo motor model: 'HS-55MG' (default) or 'Alternate'
            "servo_s_position": 10,  # S-mode polarizer position (0-255, ~1°/step, covers ~250°)
            "servo_p_position": 100,  # P-mode polarizer position (0-255, ~1°/step, covers ~250°)
        },
        "timing_parameters": {
            # Legacy timing (deprecated - for backward compatibility)
            "pre_led_delay_ms": 35.0,  # DEPRECATED: Maps to detector_wait_before_ms
            "post_led_delay_ms": 5.0,  # DEPRECATED: Maps to led_off_period_ms
            # New timing tracks (separated LED and detector timing)
            "led_off_period_ms": 5.0,  # LED transition time between channels
            "detector_wait_before_ms": 35.0,  # Wait for LED stabilization
            "detector_window_ms": 210.0,  # Spectrum acquisition window
            "detector_wait_after_ms": 5.0,  # Gap after detection completes
            # Per-channel LED delays (future use for fine-tuning)
            "led_a_delay_ms": 0,
            "led_b_delay_ms": 0,
            "led_c_delay_ms": 0,
            "led_d_delay_ms": 0,
            # Hardware limits
            "min_integration_time_ms": 50,  # Minimum safe integration time per LED
            "led_rise_fall_time_ms": 5,  # Time for LED to stabilize
        },
        "frequency_limits": {
            "4_led_target_hz": 1.0,  # Target frequency for 4-LED mode
        },
        "calibration": {
            "dark_calibration_date": None,
            "s_mode_calibration_date": None,
            "p_mode_calibration_date": None,
            "polarizer_calibration_date": None,  # Last polarizer servo calibration date
            "polarizer_extinction_ratio_percent": None,  # (S-P)/S in best bucket, sensor-specific reference
            "factory_calibrated": False,
            "user_calibrated": False,
            "preferred_calibration_mode": "global",  # 'global' or 'per_channel'
            "integration_time_ms": None,  # Calibrated integration time
            "num_scans": None,  # Calibrated number of scans
            "led_intensity_a": 0,  # Calibrated LED A intensity (0-255)
            "led_intensity_b": 0,  # Calibrated LED B intensity (0-255)
            "led_intensity_c": 0,  # Calibrated LED C intensity (0-255)
            "led_intensity_d": 0,  # Calibrated LED D intensity (0-255)
            "spr_model_path": None,  # Path to SPR bilinear model file (OpticalSystem_QC/<SERIAL>/spr_calibration/...)
            "spr_model_calibration_date": None,  # Last SPR model calibration date
        },
        "maintenance": {
            "last_maintenance_date": None,
            "total_measurement_cycles": 0,
            "led_on_hours": 0.0,
            "next_maintenance_due": None,
        },
    }

    def __init__(
        self,
        config_path: str | None = None,
        device_serial: str | None = None,
        controller=None,
        silent_load: bool = False,
    ) -> None:
        """Initialize device configuration.

        Args:
            config_path: Path to configuration file. If None, uses default location.
            device_serial: Device serial number for device-specific config. If provided,
                          creates config in devices/<serial>/device_config.json
            controller: Controller instance for EEPROM fallback (optional)
            silent_load: If True, suppress verbose logging during initialization (default: False)

        """
        self.silent_load = silent_load  # Store for use in logging methods

        if config_path is None:
            if device_serial:
                # Device-specific location: config/devices/<serial>/device_config.json
                config_dir = (
                    Path(__file__).parent.parent / "config" / "devices" / device_serial
                )
                config_dir.mkdir(parents=True, exist_ok=True)
                self.config_path = config_dir / "device_config.json"
                if not silent_load:
                    logger.info(
                        f"Using device-specific configuration for S/N: {device_serial}",
                    )
            else:
                # Default location: config/device_config.json (fallback for unknown devices)
                config_dir = Path(__file__).parent.parent / "config"
                config_dir.mkdir(exist_ok=True)
                self.config_path = config_dir / "device_config.json"
                if not silent_load:
                    logger.warning(
                        "No device serial provided - using default configuration",
                    )
        else:
            self.config_path = Path(config_path)

        self.device_serial = device_serial
        self.controller = controller
        self.loaded_from_eeprom = False
        self.created_from_scratch = False  # True if config created with known info (user needs to fill missing fields)
        self.config = self._load_or_create_config()

        # Auto-save EEPROM config to JSON if loaded from EEPROM
        if self.loaded_from_eeprom:
            self.save()
            if not silent_load:
                logger.info(f"✓ Saved EEPROM config to JSON: {self.config_path}")

        if not silent_load:
            logger.info(f"Device configuration loaded from: {self.config_path}")
            self._log_config_summary()

    def _load_or_create_config(self) -> dict[str, Any]:
        """Load configuration from file or create new with defaults.

        Load priority:
        1. JSON file (if exists)
        2. EEPROM (if JSON missing and controller connected)
        3. Create with known info (device serial, controller type) - UI will prompt for missing fields

        Returns:
            Configuration dictionary

        """
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    config = json.load(f)
                if not self.silent_load:
                    logger.info(
                        f"✓ Loaded existing configuration from {self.config_path}",
                    )

                # Validate and merge with defaults (in case new fields added)
                config = self._merge_with_defaults(config)
                self.loaded_from_eeprom = False
                self.created_from_scratch = False  # Loaded from file, not created
                return config
            except Exception as e:
                if not self.silent_load:
                    logger.error(f"Failed to load configuration: {e}")
                    logger.warning("Attempting EEPROM fallback...")
                return self._try_load_from_eeprom_or_default()
        else:
            if not self.silent_load:
                logger.info("No JSON configuration found. Checking EEPROM...")
            return self._try_load_from_eeprom_or_default()

    def _try_load_from_eeprom_or_default(self) -> dict[str, Any]:
        """Try to load config from EEPROM, or create partial config with known info if that fails."""
        if self.controller is not None:
            try:
                if self.controller.is_config_valid_in_eeprom():
                    logger.info("✓ Valid configuration found in EEPROM")
                    eeprom_config = self.controller.read_config_from_eeprom()

                    if eeprom_config:
                        # Convert EEPROM config to full config structure
                        config = self._create_config_from_eeprom(eeprom_config)
                        self.loaded_from_eeprom = True
                        self.created_from_scratch = False

                        # Note: Don't call self.save() here - config not yet assigned to self.config
                        # It will be saved after __init__ assigns it

                        return config
                else:
                    logger.info("No valid configuration in EEPROM")
            except Exception as e:
                logger.warning(f"EEPROM read failed: {e}")

        # Fallback: create partial config with known information
        # UI will prompt user for missing fields (LED model, fiber diameter, polarizer type)
        logger.info(
            "Creating new configuration with known information (device serial, controller type)",
        )
        logger.info(
            "UI will prompt for missing fields: LED model, fiber diameter, polarizer type",
        )
        self.loaded_from_eeprom = False
        self.created_from_scratch = True  # Flag to trigger UI popup
        return self._create_partial_config_with_known_info()

    def _create_config_from_eeprom(self, eeprom_config: dict) -> dict[str, Any]:
        """Create full configuration structure from EEPROM data.

        Args:
            eeprom_config: Dict from controller.read_config_from_eeprom()

        Returns:
            Full configuration with defaults for missing fields

        """
        import copy

        config = copy.deepcopy(self.DEFAULT_CONFIG)

        # Set timestamps
        now = datetime.now().isoformat()
        config["device_info"]["created_date"] = now
        config["device_info"]["last_modified"] = now

        # Map EEPROM data to config structure
        config["hardware"]["led_pcb_model"] = eeprom_config.get(
            "led_pcb_model", "luminus_cool_white",
        )
        config["hardware"]["optical_fiber_diameter_um"] = eeprom_config.get(
            "fiber_diameter_um", 200,
        )
        config["hardware"]["polarizer_type"] = eeprom_config.get(
            "polarizer_type", "round",
        )
        config["hardware"]["servo_s_position"] = eeprom_config.get(
            "servo_s_position", 10,
        )
        config["hardware"]["servo_p_position"] = eeprom_config.get(
            "servo_p_position", 100,
        )

        config["calibration"]["led_intensity_a"] = eeprom_config.get(
            "led_intensity_a", 0,
        )
        config["calibration"]["led_intensity_b"] = eeprom_config.get(
            "led_intensity_b", 0,
        )
        config["calibration"]["led_intensity_c"] = eeprom_config.get(
            "led_intensity_c", 0,
        )
        config["calibration"]["led_intensity_d"] = eeprom_config.get(
            "led_intensity_d", 0,
        )
        config["calibration"]["integration_time_ms"] = eeprom_config.get(
            "integration_time_ms", 100,
        )
        config["calibration"]["num_scans"] = eeprom_config.get("num_scans", 3)

        # Mark as factory calibrated if LED intensities are non-zero
        if any(
            eeprom_config.get(f"led_intensity_{ch}", 0) > 0
            for ch in ["a", "b", "c", "d"]
        ):
            config["calibration"]["factory_calibrated"] = True

        return config

    def _create_default_config(self) -> dict[str, Any]:
        """Create new configuration with default values."""
        import copy

        config = copy.deepcopy(self.DEFAULT_CONFIG)

        # Set timestamps
        now = datetime.now().isoformat()
        config["device_info"]["created_date"] = now
        config["device_info"]["last_modified"] = now

        # Set next maintenance to November of next year (one year from now)
        current_date = datetime.now()
        current_year = current_date.year
        current_month = current_date.month

        # If we're past November, schedule for next year's November
        if current_month >= 11:
            next_maintenance_year = current_year + 1
        else:
            # If we're before November, schedule for this year's November
            next_maintenance_year = current_year

        config["maintenance"]["next_maintenance_due"] = f"{next_maintenance_year}-11-01"

        return config

    def _create_partial_config_with_known_info(self) -> dict[str, Any]:
        """Create partial configuration with known information.

        Populates fields we know from hardware detection:
        - Device serial number (spectrometer)
        - Controller type (detected from hardware)

        Leaves these fields for user input:
        - LED model (LCW or OWW)
        - Fiber diameter (100 or 200 µm)
        - Polarizer type (barrel or circle)

        Servo positions and LED intensities will be populated after calibration.

        Returns:
            Partial configuration with known info

        """
        import copy

        config = copy.deepcopy(self.DEFAULT_CONFIG)

        # Set timestamps
        now = datetime.now().isoformat()
        config["device_info"]["created_date"] = now
        config["device_info"]["last_modified"] = now

        # Set next maintenance to November of next year (one year from now)
        current_date = datetime.now()
        current_year = current_date.year
        current_month = current_date.month

        # If we're past November, schedule for next year's November
        if current_month >= 11:
            next_maintenance_year = current_year + 1
        else:
            # If we're before November, schedule for this year's November
            next_maintenance_year = current_year

        config["maintenance"]["next_maintenance_due"] = f"{next_maintenance_year}-11-01"

        # Populate known information
        if self.device_serial:
            config["hardware"]["spectrometer_serial"] = self.device_serial
            config["device_info"]["device_id"] = self.device_serial
            logger.info(f"  ✓ Device Serial: {self.device_serial}")

        # Try to detect controller type from hardware
        if self.controller is not None:
            try:
                ctrl_name = getattr(self.controller, "device_name", "").lower()
                if "arduino" in ctrl_name or ctrl_name == "p4spr":
                    config["hardware"]["controller_type"] = "Arduino"
                    config["hardware"]["controller_model"] = "Arduino P4SPR"
                    config["hardware"]["polarizer_type"] = (
                        "round"  # Hardware rule: Arduino always uses round
                    )
                    logger.info(
                        "  ✓ Controller: Arduino (auto-set polarizer to 'round')",
                    )
                elif "pico_p4spr" in ctrl_name or "picop4spr" in ctrl_name:
                    config["hardware"]["controller_type"] = "PicoP4SPR"
                    config["hardware"]["controller_model"] = "Raspberry Pi Pico P4SPR"
                    config["hardware"]["polarizer_type"] = (
                        "round"  # Hardware rule: PicoP4SPR always uses round
                    )
                    logger.info(
                        "  ✓ Controller: PicoP4SPR (auto-set polarizer to 'round')",
                    )
                elif "pico_ezspr" in ctrl_name or "picoezspr" in ctrl_name:
                    config["hardware"]["controller_type"] = "PicoEZSPR"
                    config["hardware"]["controller_model"] = "Raspberry Pi Pico EZSPR"
                    config["hardware"]["polarizer_type"] = (
                        "barrel"  # Hardware rule: PicoEZSPR typically uses barrel
                    )
                    logger.info(
                        "  ✓ Controller: PicoEZSPR (auto-set polarizer to 'barrel')",
                    )
            except Exception as e:
                logger.debug(f"Could not auto-detect controller type: {e}")

        logger.info("  [WARN] User input required: LED model, fiber diameter")
        return config

    def _merge_with_defaults(self, config: dict[str, Any]) -> dict[str, Any]:
        """Merge loaded config with defaults to handle new fields.

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

    def save(self, auto_sync_eeprom: bool = False) -> None:
        """Save configuration to file.

        Args:
            auto_sync_eeprom: If True and controller is available, automatically sync to EEPROM

        """
        try:
            # Update last modified timestamp
            self.config["device_info"]["last_modified"] = datetime.now().isoformat()

            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Save with nice formatting
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=2)

            logger.info(f"Configuration saved to {self.config_path}")

            # Auto-sync to EEPROM if requested and controller available
            if auto_sync_eeprom and self.controller is not None:
                logger.info("Auto-syncing configuration to EEPROM...")
                success = self.sync_to_eeprom(self.controller)
                if success:
                    logger.info("✓ Configuration auto-synced to EEPROM")
                else:
                    logger.warning("✗ EEPROM auto-sync failed")

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise

    def to_dict(self) -> dict[str, Any]:
        """Return configuration as dictionary.

        Returns:
            Configuration dictionary

        """
        return self.config.copy()

    def validate(self) -> tuple[bool, list[str]]:
        """Validate configuration for consistency and valid values.

        Returns:
            Tuple of (is_valid, list_of_errors)

        """
        errors = []

        # Validate LED PCB model
        led_model = self.config["hardware"]["led_pcb_model"]
        if led_model not in self.VALID_LED_PCB_MODELS:
            errors.append(
                f"Invalid LED PCB model '{led_model}'. "
                f"Valid options: {self.VALID_LED_PCB_MODELS}",
            )

        # Validate optical fiber diameter
        fiber_diameter = self.config["hardware"]["optical_fiber_diameter_um"]
        if fiber_diameter not in self.VALID_FIBER_DIAMETERS:
            errors.append(
                f"Invalid optical fiber diameter {fiber_diameter} µm. "
                f"Valid options: {self.VALID_FIBER_DIAMETERS} µm",
            )

        # Validate polarizer type
        polarizer_type = self.config["hardware"].get(
            "polarizer_type", "barrel",
        )  # Default for backward compatibility
        if polarizer_type not in self.VALID_POLARIZER_TYPES:
            errors.append(
                f"Invalid polarizer type '{polarizer_type}'. "
                f"Valid options: {self.VALID_POLARIZER_TYPES}",
            )

        # Validate timing parameters
        min_integration = self.config["timing_parameters"]["min_integration_time_ms"]
        if min_integration < 1 or min_integration > 1000:
            errors.append(
                f"Invalid min_integration_time_ms: {min_integration}. "
                f"Must be between 1-1000 ms",
            )

        # Validate frequency limits
        freq_4led = self.config["frequency_limits"]["4_led_max_hz"]

        if freq_4led <= 0 or freq_4led > 10:
            errors.append(f"Invalid 4-LED max frequency: {freq_4led} Hz")

        is_valid = len(errors) == 0
        return is_valid, errors

    def _log_config_summary(self) -> None:
        """Log summary of current configuration."""
        hw = self.config["hardware"]
        logger.info("=" * 60)
        logger.info("DEVICE CONFIGURATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"  LED PCB Model: {hw['led_pcb_model']}")
        logger.info(f"  Optical Fiber: {hw['optical_fiber_diameter_um']} µm")
        logger.info(
            f"  Polarizer Type: {hw.get('polarizer_type', 'barrel')} ({'2 fixed windows' if hw.get('polarizer_type', 'barrel') == 'barrel' else 'continuous rotation'})",
        )
        logger.info(
            f"  Spectrometer: {hw['spectrometer_model']} (S/N: {hw['spectrometer_serial'] or 'N/A'})",
        )
        logger.info(f"  Controller: {hw['controller_model']}")

        cal = self.config["calibration"]
        logger.info(
            f"  Factory Calibrated: {'Yes' if cal['factory_calibrated'] else 'No'}",
        )
        logger.info(f"  User Calibrated: {'Yes' if cal['user_calibrated'] else 'No'}")

        if cal["dark_calibration_date"]:
            logger.info(f"  Last Dark Calibration: {cal['dark_calibration_date']}")

        logger.info("=" * 60)

    # ========================================================================
    # Getter/Setter Methods
    # ========================================================================

    def get_led_pcb_model(self) -> str:
        """Get LED PCB model."""
        return self.config["hardware"]["led_pcb_model"]

    def set_led_pcb_model(self, model: str) -> None:
        """Set LED PCB model.

        Args:
            model: 'luminus_cool_white' or 'osram_warm_white'

        """
        if model not in self.VALID_LED_PCB_MODELS:
            msg = (
                f"Invalid LED PCB model '{model}'. "
                f"Valid options: {self.VALID_LED_PCB_MODELS}"
            )
            raise ValueError(
                msg,
            )
        self.config["hardware"]["led_pcb_model"] = model
        logger.info(f"LED PCB model set to: {model}")

    def get_optical_fiber_diameter(self) -> int:
        """Get optical fiber diameter in micrometers."""
        return self.config["hardware"]["optical_fiber_diameter_um"]

    def set_optical_fiber_diameter(self, diameter_um: int) -> None:
        """Set optical fiber diameter.

        Args:
            diameter_um: Fiber diameter in micrometers (100 or 200)

        """
        if diameter_um not in self.VALID_FIBER_DIAMETERS:
            msg = (
                f"Invalid fiber diameter {diameter_um} µm. "
                f"Valid options: {self.VALID_FIBER_DIAMETERS} µm"
            )
            raise ValueError(
                msg,
            )
        self.config["hardware"]["optical_fiber_diameter_um"] = diameter_um
        logger.info(f"Optical fiber diameter set to: {diameter_um} µm")

    def get_polarizer_type(self) -> str:
        """Get polarizer type ('barrel' or 'round')."""
        return self.config["hardware"].get(
            "polarizer_type", "barrel",
        )  # Default to barrel for backward compatibility

    def set_polarizer_type(self, polarizer_type: str) -> None:
        """Set polarizer type.

        Args:
            polarizer_type: 'barrel' (2 fixed perpendicular windows) or 'round' (continuous rotation)

        """
        if polarizer_type not in self.VALID_POLARIZER_TYPES:
            msg = (
                f"Invalid polarizer type '{polarizer_type}'. "
                f"Valid options: {self.VALID_POLARIZER_TYPES}"
            )
            raise ValueError(
                msg,
            )
        self.config["hardware"]["polarizer_type"] = polarizer_type
        logger.info(f"Polarizer type set to: {polarizer_type}")

    def get_spectrometer_serial(self) -> str | None:
        """Get spectrometer serial number."""
        return self.config["hardware"]["spectrometer_serial"]

    def set_spectrometer_serial(self, serial: str) -> None:
        """Set spectrometer serial number."""
        self.config["hardware"]["spectrometer_serial"] = serial
        logger.info(f"Spectrometer serial set to: {serial}")

    def get_min_integration_time(self) -> float:
        """Get minimum integration time in milliseconds."""
        return self.config["timing_parameters"]["min_integration_time_ms"]

    def set_min_integration_time(self, time_ms: float) -> None:
        """Set minimum integration time in milliseconds."""
        if time_ms < 1 or time_ms > 1000:
            msg = "Integration time must be between 1-1000 ms"
            raise ValueError(msg)
        self.config["timing_parameters"]["min_integration_time_ms"] = time_ms
        logger.info(f"Min integration time set to: {time_ms} ms")

    def get_led_delays(self) -> dict[str, float]:
        """Get LED delay times for all channels."""
        tp = self.config["timing_parameters"]
        return {
            "a": tp["led_a_delay_ms"],
            "b": tp["led_b_delay_ms"],
            "c": tp["led_c_delay_ms"],
            "d": tp["led_d_delay_ms"],
        }

    def set_led_delays(self, delays: dict[str, float]) -> None:
        """Set LED delay times.

        Args:
            delays: Dict with keys 'a', 'b', 'c', 'd' and delay values in ms

        """
        tp = self.config["timing_parameters"]
        for channel, delay in delays.items():
            if channel in ["a", "b", "c", "d"]:
                tp[f"led_{channel}_delay_ms"] = delay
        logger.info(f"LED delays updated: {delays}")

    def get_pre_led_delay_ms(self) -> float:
        """Get PRE LED delay (DEPRECATED: use get_detector_wait_before_ms instead).

        This method is kept for backward compatibility. New code should use
        timing track methods (get_detector_wait_before_ms, get_led_off_period_ms).
        """
        DETECTOR_WAIT_BEFORE_MS = _get_setting("DETECTOR_WAIT_BEFORE_MS", 35.0)
        # Try new timing track parameter first, fallback to legacy
        detector_wait = self.config["timing_parameters"].get("detector_wait_before_ms")
        if detector_wait is not None:
            return detector_wait
        return self.config["timing_parameters"].get(
            "pre_led_delay_ms", DETECTOR_WAIT_BEFORE_MS,
        )

    def get_post_led_delay_ms(self) -> float:
        """Get POST LED delay (DEPRECATED: use get_led_off_period_ms instead).

        This method is kept for backward compatibility. New code should use
        timing track methods (get_detector_wait_before_ms, get_led_off_period_ms).
        """
        LED_OFF_PERIOD_MS = _get_setting("LED_OFF_PERIOD_MS", 5.0)
        # Try new timing track parameter first, fallback to legacy
        led_off = self.config["timing_parameters"].get("led_off_period_ms")
        if led_off is not None:
            return led_off
        return self.config["timing_parameters"].get(
            "post_led_delay_ms", LED_OFF_PERIOD_MS,
        )

    def set_pre_post_led_delays(self, pre_ms: float, post_ms: float) -> None:
        """Set PRE/POST LED delays (DEPRECATED: use set_timing_tracks instead).

        This method is kept for backward compatibility. It maps legacy parameters
        to the new timing track architecture:
        - pre_ms → detector_wait_before_ms
        - post_ms → led_off_period_ms

        Args:
            pre_ms: PRE LED delay in milliseconds (maps to detector_wait_before)
            post_ms: POST LED delay in milliseconds (maps to led_off_period)

        """
        # Store both legacy and new format for compatibility
        self.config["timing_parameters"]["pre_led_delay_ms"] = pre_ms
        self.config["timing_parameters"]["post_led_delay_ms"] = post_ms
        self.config["timing_parameters"]["detector_wait_before_ms"] = pre_ms
        self.config["timing_parameters"]["led_off_period_ms"] = post_ms
        self.save()
        logger.info(
            f"LED timing delays saved (legacy format): PRE={pre_ms}ms, POST={post_ms}ms",
        )
        logger.info(
            f"  Mapped to timing tracks: DETECTOR_WAIT={pre_ms}ms, LED_OFF={post_ms}ms",
        )

    # NEW: Timing track methods (separated LED and detector timing)
    def get_timing_tracks(self) -> dict[str, float]:
        """Get all timing track parameters.

        Returns dict with:
        - led_off_period_ms: LED transition time between channels
        - detector_wait_before_ms: Wait for LED stabilization
        - detector_window_ms: Spectrum acquisition window
        - detector_wait_after_ms: Gap after detection
        """
        LED_OFF_PERIOD_MS = _get_setting("LED_OFF_PERIOD_MS", 5.0)
        DETECTOR_WAIT_BEFORE_MS = _get_setting("DETECTOR_WAIT_BEFORE_MS", 35.0)
        DETECTOR_WINDOW_MS = _get_setting("DETECTOR_WINDOW_MS", 210.0)
        DETECTOR_WAIT_AFTER_MS = _get_setting("DETECTOR_WAIT_AFTER_MS", 5.0)
        tp = self.config["timing_parameters"]
        return {
            "led_off_period_ms": tp.get("led_off_period_ms", LED_OFF_PERIOD_MS),
            "detector_wait_before_ms": tp.get(
                "detector_wait_before_ms", DETECTOR_WAIT_BEFORE_MS,
            ),
            "detector_window_ms": tp.get("detector_window_ms", DETECTOR_WINDOW_MS),
            "detector_wait_after_ms": tp.get(
                "detector_wait_after_ms", DETECTOR_WAIT_AFTER_MS,
            ),
        }

    def set_timing_tracks(
        self,
        led_off: float,
        detector_wait: float,
        detector_window: float,
        detector_after: float,
    ) -> None:
        """Set timing track parameters (new architecture).

        Args:
            led_off: LED transition time between channels (ms)
            detector_wait: Wait for LED stabilization (ms)
            detector_window: Spectrum acquisition window (ms)
            detector_after: Gap after detection (ms)

        """
        tp = self.config["timing_parameters"]
        tp["led_off_period_ms"] = led_off
        tp["detector_wait_before_ms"] = detector_wait
        tp["detector_window_ms"] = detector_window
        tp["detector_wait_after_ms"] = detector_after

        # Also update legacy params for backward compatibility
        tp["pre_led_delay_ms"] = detector_wait
        tp["post_led_delay_ms"] = led_off

        self.save()
        cycle_time = led_off + detector_wait + detector_window + detector_after
        logger.info("Timing tracks saved:")
        logger.info(f"  LED OFF: {led_off}ms (transition between channels)")
        logger.info(f"  DETECTOR WAIT: {detector_wait}ms (LED stabilization)")
        logger.info(f"  DETECTOR WINDOW: {detector_window}ms (acquisition)")
        logger.info(f"  DETECTOR AFTER: {detector_after}ms (gap)")
        logger.info(f"  TOTAL CYCLE: {cycle_time}ms per channel")

    def get_led_off_period_ms(self) -> float:
        """Get LED transition time between channels (ms)."""
        LED_OFF_PERIOD_MS = _get_setting("LED_OFF_PERIOD_MS", 5.0)
        return self.config["timing_parameters"].get(
            "led_off_period_ms", LED_OFF_PERIOD_MS,
        )

    def get_detector_wait_before_ms(self) -> float:
        """Get detector wait time for LED stabilization (ms)."""
        DETECTOR_WAIT_BEFORE_MS = _get_setting("DETECTOR_WAIT_BEFORE_MS", 35.0)
        return self.config["timing_parameters"].get(
            "detector_wait_before_ms", DETECTOR_WAIT_BEFORE_MS,
        )

    def get_detector_window_ms(self) -> float:
        """Get detector acquisition window (ms)."""
        DETECTOR_WINDOW_MS = _get_setting("DETECTOR_WINDOW_MS", 210.0)
        return self.config["timing_parameters"].get(
            "detector_window_ms", DETECTOR_WINDOW_MS,
        )

    def get_detector_wait_after_ms(self) -> float:
        """Get detector wait time after acquisition (ms)."""
        DETECTOR_WAIT_AFTER_MS = _get_setting("DETECTOR_WAIT_AFTER_MS", 5.0)
        return self.config["timing_parameters"].get(
            "detector_wait_after_ms", DETECTOR_WAIT_AFTER_MS,
        )

    def get_frequency_limits(self, num_leds: int) -> dict[str, float]:
        """Get frequency limits for specified LED mode.

        Args:
            num_leds: Number of LEDs (must be 4)

        Returns:
            Dict with 'max_hz' and 'recommended_hz'

        """
        if num_leds not in self.VALID_LED_MODES:
            msg = f"Invalid LED mode: {num_leds}. Must be 4."
            raise ValueError(msg)

        freq = self.config["frequency_limits"]
        return {
            "max_hz": freq[f"{num_leds}_led_max_hz"],
            "recommended_hz": freq[f"{num_leds}_led_recommended_hz"],
        }

    def get_calibration_mode(self) -> str:
        """Get preferred calibration mode.

        Returns:
            'global' (traditional LED calibration with global integration time)
            or 'per_channel' (fixed LED=255, per-channel integration times)

        """
        return self.config["calibration"].get("preferred_calibration_mode", "global")

    def set_calibration_mode(self, mode: str) -> None:
        """Set preferred calibration mode.

        Args:
            mode: 'global' or 'per_channel'

        Raises:
            ValueError: If mode is not valid

        """
        if mode not in ["global", "per_channel"]:
            msg = f"Invalid calibration mode: {mode}. Must be 'global' or 'per_channel'"
            raise ValueError(msg)

        self.config["calibration"]["preferred_calibration_mode"] = mode
        self.save()
        logger.info(f"Calibration mode set to: {mode}")

    def is_factory_calibrated(self) -> bool:
        """Check if device has factory calibration."""
        return self.config["calibration"]["factory_calibrated"]

    def is_user_calibrated(self) -> bool:
        """Check if device has user calibration."""
        return self.config["calibration"]["user_calibrated"]

    def mark_calibrated(self, calibration_type: str) -> None:
        """Mark device as calibrated.

        Args:
            calibration_type: 'factory', 'dark', 's_mode', or 'p_mode'

        """
        now = datetime.now().isoformat()
        cal = self.config["calibration"]

        if calibration_type == "factory":
            cal["factory_calibrated"] = True
        elif calibration_type == "dark":
            cal["dark_calibration_date"] = now
        elif calibration_type == "s_mode":
            cal["s_mode_calibration_date"] = now
            cal["user_calibrated"] = True
        elif calibration_type == "p_mode":
            cal["p_mode_calibration_date"] = now
            cal["user_calibrated"] = True
        else:
            msg = f"Invalid calibration type: {calibration_type}"
            raise ValueError(msg)

    def get_servo_positions(self) -> dict[str, int]:
        """Get polarizer servo positions for S and P modes.

        Returns:
            Dict with keys 's' and 'p' containing servo positions (0-180)

        """
        hw = self.config["hardware"]
        return {
            "s": hw["servo_s_position"],
            "p": hw["servo_p_position"],
        }

    def get_servo_s_position(self) -> int:
        """Get polarizer servo position for S-mode.

        Returns:
            Servo position for S-mode (0-180)

        """
        return self.config["hardware"]["servo_s_position"]

    def get_servo_p_position(self) -> int:
        """Get polarizer servo position for P-mode.

        Returns:
            Servo position for P-mode (0-180)

        """
        return self.config["hardware"]["servo_p_position"]

    def set_servo_positions(self, s_pos: int, p_pos: int) -> None:
        """Set polarizer servo positions for S and P modes.

        Args:
            s_pos: Servo position for S-mode (0-180)
            p_pos: Servo position for P-mode (0-180)

        Raises:
            ValueError: If positions are out of valid range

        """
        if not (0 <= s_pos <= 180):
            msg = f"S position {s_pos} out of range (0-180)"
            raise ValueError(msg)
        if not (0 <= p_pos <= 180):
            msg = f"P position {p_pos} out of range (0-180)"
            raise ValueError(msg)

        hw = self.config["hardware"]
        hw["servo_s_position"] = s_pos
        hw["servo_p_position"] = p_pos
        self.config["device_info"]["last_modified"] = datetime.now().isoformat()
        logger.info(f"Servo positions updated: S={s_pos}, P={p_pos}")

    def set_extinction_ratio(self, extinction_ratio: float) -> None:
        """Set polarizer extinction ratio from calibration.

        The extinction ratio is (S-P)/S expressed as percentage, measured in the best
        ROI bucket during servo calibration. This is a sensor-specific reference value
        for tracking calibration quality over time (not an absolute metric).

        Args:
            extinction_ratio: Extinction ratio as percentage (0-100)

        """
        if not (0.0 <= extinction_ratio <= 100.0):
            logger.warning(
                f"Extinction ratio {extinction_ratio:.2f}% outside expected range (0-100%)",
            )

        cal = self.config["calibration"]
        cal["polarizer_extinction_ratio_percent"] = round(extinction_ratio, 2)
        cal["polarizer_calibration_date"] = datetime.now().isoformat()
        self.config["device_info"]["last_modified"] = datetime.now().isoformat()
        logger.info(f"Polarizer extinction ratio updated: {extinction_ratio:.2f}%")

    def set_spr_model_path(self, model_path: str) -> None:
        """Set path to SPR bilinear model calibration file.

        Args:
            model_path: Path to led_calibration_spr_processed_latest.json file
                       (typically in OpticalSystem_QC/<SERIAL>/spr_calibration/)

        """
        cal = self.config["calibration"]
        cal["spr_model_path"] = str(model_path)
        cal["spr_model_calibration_date"] = datetime.now().isoformat()
        self.config["device_info"]["last_modified"] = datetime.now().isoformat()
        logger.info(f"SPR model path updated: {model_path}")

    def get_spr_model_path(self) -> str | None:
        """Get path to SPR bilinear model calibration file.

        Returns:
            Path to SPR model file, or None if not set

        """
        return self.config["calibration"].get("spr_model_path")

    def set_integration_time(self, integration_time_ms: float) -> None:
        """Set calibrated integration time.

        Args:
            integration_time_ms: Integration time in milliseconds

        """
        cal = self.config["calibration"]
        cal["integration_time_ms"] = integration_time_ms
        self.config["device_info"]["last_modified"] = datetime.now().isoformat()
        logger.info(f"Integration time updated: {integration_time_ms} ms")

    def get_integration_time(self) -> float | None:
        """Get calibrated integration time.

        Returns:
            Integration time in milliseconds, or None if not set

        """
        return self.config["calibration"].get("integration_time_ms")

    def set_num_scans(self, num_scans: int) -> None:
        """Set calibrated number of scans.

        Args:
            num_scans: Number of scans to average

        """
        cal = self.config["calibration"]
        cal["num_scans"] = num_scans
        self.config["device_info"]["last_modified"] = datetime.now().isoformat()
        logger.info(f"Number of scans updated: {num_scans}")

    def get_num_scans(self) -> int | None:
        """Get calibrated number of scans.

        Returns:
            Number of scans, or None if not set

        """
        return self.config["calibration"].get("num_scans")

    def get_extinction_ratio(self) -> float | None:
        """Get polarizer extinction ratio from last calibration.

        Returns:
            Extinction ratio as percentage, or None if not calibrated

        """
        return self.config.get("calibration", {}).get(
            "polarizer_extinction_ratio_percent",
        )

    def get_calibration_summary(self) -> dict[str, Any]:
        """Get complete calibration summary from device config.

        Returns:
            Dictionary containing all calibration parameters

        """
        hw = self.config["hardware"]
        cal = self.config["calibration"]

        return {
            "servo_positions": {
                "s": hw["servo_s_position"],
                "p": hw["servo_p_position"],
                "calibration_date": cal.get("polarizer_calibration_date"),
                "extinction_ratio": cal.get("polarizer_extinction_ratio_percent"),
            },
            "led_intensities": {
                "a": cal["led_intensity_a"],
                "b": cal["led_intensity_b"],
                "c": cal["led_intensity_c"],
                "d": cal["led_intensity_d"],
            },
            "integration_settings": {
                "integration_time_ms": cal.get("integration_time_ms"),
                "num_scans": cal.get("num_scans"),
            },
            "spr_model": {
                "path": cal.get("spr_model_path"),
                "calibration_date": cal.get("spr_model_calibration_date"),
            },
            "calibration_status": {
                "factory_calibrated": cal["factory_calibrated"],
                "user_calibrated": cal["user_calibrated"],
                "s_mode_date": cal.get("s_mode_calibration_date"),
                "p_mode_date": cal.get("p_mode_calibration_date"),
            },
        }

    def log_calibration_summary(self) -> None:
        """Log comprehensive calibration summary showing single source of truth."""
        summary = self.get_calibration_summary()

        logger.info("=" * 80)
        logger.info("📋 DEVICE CALIBRATION STATUS - Single Source of Truth")
        logger.info("=" * 80)
        logger.info(f"   Config File: {self.config_path}")
        logger.info(f"   Device Serial: {self.device_serial or 'N/A'}")
        logger.info("")

        # Servo positions
        servo = summary["servo_positions"]
        logger.info("   SERVO POSITIONS:")
        logger.info(f"     S-mode: {servo['s']}°")
        logger.info(f"     P-mode: {servo['p']}°")
        if servo["calibration_date"]:
            logger.info(f"     Last calibrated: {servo['calibration_date']}")
            if servo["extinction_ratio"]:
                logger.info(f"     Extinction ratio: {servo['extinction_ratio']:.2f}%")
        else:
            logger.info("     Status: ⚠️ Not calibrated (using defaults)")
        logger.info("")

        # LED intensities
        leds = summary["led_intensities"]
        logger.info("   LED INTENSITIES:")
        logger.info(f"     Channel A: {leds['a']}")
        logger.info(f"     Channel B: {leds['b']}")
        logger.info(f"     Channel C: {leds['c']}")
        logger.info(f"     Channel D: {leds['d']}")
        if any([leds["a"], leds["b"], leds["c"], leds["d"]]):
            logger.info("     Status: ✅ Calibrated")
        else:
            logger.info("     Status: ⚠️ Not calibrated (all zero)")
        logger.info("")

        # Integration settings
        integration = summary["integration_settings"]
        logger.info("   INTEGRATION SETTINGS:")
        if integration["integration_time_ms"]:
            logger.info(
                f"     Integration time: {integration['integration_time_ms']} ms",
            )
        else:
            logger.info("     Integration time: ⚠️ Not set")
        if integration["num_scans"]:
            logger.info(f"     Number of scans: {integration['num_scans']}")
        else:
            logger.info("     Number of scans: ⚠️ Not set")
        logger.info("")

        # SPR model
        spr = summary["spr_model"]
        logger.info("   SPR BILINEAR MODEL:")
        if spr["path"]:
            logger.info(f"     Path: {spr['path']}")
            if spr["calibration_date"]:
                logger.info(f"     Generated: {spr['calibration_date']}")
            logger.info("     Status: ✅ Available")
        else:
            logger.info("     Status: ⚠️ Not generated - run OEM calibration")
        logger.info("")

        # Overall status
        status = summary["calibration_status"]
        logger.info("   OVERALL STATUS:")
        if status["factory_calibrated"]:
            logger.info("     Factory calibrated: ✅ Yes")
        else:
            logger.info("     Factory calibrated: ⚠️ No")
        if status["user_calibrated"]:
            logger.info("     User calibrated: ✅ Yes")
        logger.info("=" * 80)

    def swap_servo_positions(self) -> tuple[int, int, str]:
        """Swap S and P polarizer servo positions.

        Used for auto-correction when polarizer orientation is detected as inverted
        (e.g., when 3+ channels show inverted SPR dips).

        Returns:
            Tuple of (new_s_pos, new_p_pos, polarizer_type) after swap

        """
        hw = self.config["hardware"]
        s_pos = hw.get("servo_s_position", 10)
        p_pos = hw.get("servo_p_position", 100)
        polarizer_type = hw.get("polarizer_type", "barrel")

        # Swap positions
        hw["servo_s_position"] = p_pos
        hw["servo_p_position"] = s_pos
        self.config["device_info"]["last_modified"] = datetime.now().isoformat()

        logger.info(
            f"Servo positions swapped: S={s_pos}→{p_pos}, P={p_pos}→{s_pos} (polarizer_type={polarizer_type})",
        )
        return p_pos, s_pos, polarizer_type

    def get_led_intensities(self) -> dict[str, int]:
        """Get calibrated LED intensities for all channels.

        Returns:
            Dict with keys 'a', 'b', 'c', 'd' containing LED intensities (0-255)

        """
        cal = self.config["calibration"]
        return {
            "a": cal["led_intensity_a"],
            "b": cal["led_intensity_b"],
            "c": cal["led_intensity_c"],
            "d": cal["led_intensity_d"],
        }

    def set_led_intensities(
        self, led_a: int, led_b: int, led_c: int, led_d: int,
    ) -> None:
        """Set calibrated LED intensities for all channels.

        Args:
            led_a: LED A intensity (0-255)
            led_b: LED B intensity (0-255)
            led_c: LED C intensity (0-255)
            led_d: LED D intensity (0-255)

        Raises:
            ValueError: If intensities are out of valid range

        """
        for name, val in [("A", led_a), ("B", led_b), ("C", led_c), ("D", led_d)]:
            if not (0 <= val <= 255):
                msg = f"LED {name} intensity {val} out of range (0-255)"
                raise ValueError(msg)

        cal = self.config["calibration"]
        cal["led_intensity_a"] = led_a
        cal["led_intensity_b"] = led_b
        cal["led_intensity_c"] = led_c
        cal["led_intensity_d"] = led_d
        self.config["device_info"]["last_modified"] = datetime.now().isoformat()
        logger.info(
            f"LED intensities updated: A={led_a}, B={led_b}, C={led_c}, D={led_d}",
        )

    def get_calibration_settings(self) -> dict[str, int | None]:
        """Get calibration settings (integration time and number of scans).

        Returns:
            Dict with keys 'integration_time_ms' and 'num_scans'

        """
        cal = self.config["calibration"]
        return {
            "integration_time_ms": cal["integration_time_ms"],
            "num_scans": cal["num_scans"],
        }

    def set_calibration_settings(
        self, integration_time_ms: int | None, num_scans: int | None,
    ) -> None:
        """Set calibration settings (integration time and number of scans).

        Args:
            integration_time_ms: Integration time in milliseconds
            num_scans: Number of scans to average

        """
        cal = self.config["calibration"]
        cal["integration_time_ms"] = integration_time_ms
        cal["num_scans"] = num_scans
        self.config["device_info"]["last_modified"] = datetime.now().isoformat()

    def save_sp_validation(self, sp_results: dict[str, dict]) -> None:
        """Save S/P orientation validation results to device config.

        Args:
            sp_results: Dict with channel keys, each containing:
                - orientation_correct: bool
                - confidence: float
                - peak_wl: float
                - peak_value: float
                - timestamp: str (ISO format)
                - is_flat: bool

        """
        cal = self.config["calibration"]

        # Add sp_orientation section if not exists
        if "sp_orientation" not in cal:
            cal["sp_orientation"] = {}

        # Store validation results
        cal["sp_orientation"]["validated"] = True
        cal["sp_orientation"]["validation_date"] = datetime.now().isoformat()
        cal["sp_orientation"]["channels"] = {}

        for ch, result in sp_results.items():
            cal["sp_orientation"]["channels"][ch] = {
                "orientation_correct": result.get("orientation_correct"),
                "confidence": result.get("confidence"),
                "peak_wavelength_nm": result.get("peak_wl"),
                "peak_transmission_percent": result.get("peak_value"),
                "is_flat": result.get("is_flat", False),
            }

        self.config["device_info"]["last_modified"] = datetime.now().isoformat()
        logger.info(f"S/P orientation validation saved for {len(sp_results)} channels")
        self.config["device_info"]["last_modified"] = datetime.now().isoformat()
        logger.info(
            f"Calibration settings updated: Integration={integration_time_ms}ms, Scans={num_scans}",
        )

    def increment_measurement_cycles(self, count: int = 1) -> None:
        """Increment total measurement cycle counter."""
        self.config["maintenance"]["total_measurement_cycles"] += count

    def add_led_on_time(self, hours: float) -> None:
        """Add to LED on-time counter."""
        self.config["maintenance"]["led_on_hours"] += hours

    def export_config(self, export_path: str) -> None:
        """Export configuration to specified path (for backup).

        Args:
            export_path: Path to save exported configuration

        """
        try:
            with open(export_path, "w") as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Configuration exported to: {export_path}")
        except Exception as e:
            logger.error(f"Failed to export configuration: {e}")
            raise

    def import_config(self, import_path: str) -> None:
        """Import configuration from specified path.

        Args:
            import_path: Path to configuration file to import

        """
        try:
            with open(import_path) as f:
                imported_config = json.load(f)

            # Validate imported config
            self.config = self._merge_with_defaults(imported_config)
            is_valid, errors = self.validate()

            if not is_valid:
                logger.error("Imported configuration is invalid:")
                for error in errors:
                    logger.error(f"  - {error}")
                msg = "Invalid configuration"
                raise ValueError(msg)

            logger.info(f"Configuration imported from: {import_path}")
            self._log_config_summary()

        except Exception as e:
            logger.error(f"Failed to import configuration: {e}")
            raise

    def sync_to_eeprom(self, controller) -> bool:
        """Synchronize current configuration to controller EEPROM.

        This creates a portable backup of device settings that travels with the hardware.
        Called automatically on major config changes or manually via UI.

        Args:
            controller: Controller instance with write_config_to_eeprom() method

        Returns:
            True if successful, False otherwise

        """
        if controller is None:
            logger.warning("Cannot sync to EEPROM: No controller connected")
            return False

        try:
            # Extract config data for EEPROM
            hw = self.config["hardware"]
            cal = self.config["calibration"]

            eeprom_config = {
                "led_pcb_model": hw.get("led_pcb_model", "luminus_cool_white"),
                "controller_type": self._get_controller_type_name(controller),
                "fiber_diameter_um": hw.get("optical_fiber_diameter_um", 200),
                "polarizer_type": hw.get("polarizer_type", "round"),
                "servo_s_position": hw.get("servo_s_position", 10),
                "servo_p_position": hw.get("servo_p_position", 100),
                "led_intensity_a": cal.get("led_intensity_a", 0),
                "led_intensity_b": cal.get("led_intensity_b", 0),
                "led_intensity_c": cal.get("led_intensity_c", 0),
                "led_intensity_d": cal.get("led_intensity_d", 0),
                "integration_time_ms": cal.get("integration_time_ms", 100),
                "num_scans": cal.get("num_scans", 3),
            }

            success = controller.write_config_to_eeprom(eeprom_config)

            if success:
                logger.info("✓ Configuration synchronized to EEPROM")
            else:
                logger.warning("✗ Failed to sync configuration to EEPROM")

            return success

        except Exception as e:
            logger.error(f"Exception while syncing to EEPROM: {e}")
            return False

    def _get_controller_type_name(self, controller) -> str:
        """Determine controller type from controller instance."""
        controller_str = str(controller).lower()
        if "arduino" in controller_str:
            return "arduino"
        if "pico mini" in controller_str or "picop4spr" in controller_str:
            return "pico_p4spr"
        if "pico ez" in controller_str or "picoezspr" in controller_str:
            return "pico_ezspr"
        return "arduino"  # default fallback

    def reset_to_defaults(self) -> None:
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
            if "led_calibration" not in self.config:
                self.config["led_calibration"] = {}

            dark_min = float(np.min(dark_spectrum))
            dark_max = float(np.max(dark_spectrum))
            now = datetime.now().isoformat()

            # Persist snapshot and stats
            self.config["led_calibration"]["pre_qc_dark_snapshot"] = (
                dark_spectrum.tolist()
            )
            self.config["led_calibration"]["pre_qc_dark_date"] = now
            self.config["led_calibration"]["pre_qc_dark_min"] = dark_min
            self.config["led_calibration"]["pre_qc_dark_max"] = dark_max

            # Update top-level calibration date for dark
            if "calibration" not in self.config:
                self.config["calibration"] = {}
            self.config["calibration"]["dark_calibration_date"] = now

            # Persist to disk
            self.save()

            # Log and flag if any negatives
            if dark_min < 0:
                logger.error(
                    f"[WARN] Dark snapshot contains negative values (min={dark_min:.2f}). "
                    f"This indicates possible offset or subtraction error.",
                )
            logger.info(
                f"💾 Pre-QC dark snapshot saved: len={len(dark_spectrum)}, "
                f"min={dark_min:.1f}, max={dark_max:.1f}",
            )

        except Exception as e:
            logger.error(f"Failed to save dark snapshot: {e}")
            raise

    def save_led_calibration(
        self,
        calibration_data: dict[str, Any] | None = None,
        integration_time_ms: int | None = None,
        s_mode_intensities: dict[str, int] | None = None,
        p_mode_intensities: dict[str, int] | None = None,
        s_ref_spectra: dict[str, np.ndarray] | None = None,
        p_ref_spectra: dict[str, np.ndarray] | None = None,
        s_ref_wavelengths: np.ndarray | None = None,
        live_boost_integration_ms: int | None = None,
        live_boost_led_intensities: dict[str, int] | None = None,
        live_boost_factor: float | None = None,
        calibration_method: str = "standard",
        per_channel_integration_times: dict[str, int] | None = None,
        weakest_channel: str | None = None,
    ) -> None:
        """Save LED calibration baseline to device_config.json (single source of truth).

        Can be called with either:
        1. A dictionary containing all calibration data (preferred for new code)
        2. Individual keyword arguments (legacy support)

        This stores calibrated LED intensities, integration time, and S/P-mode reference
        spectra for quick QC validation. Replaces any existing calibration data.

        OPTICAL SYSTEM MODE HANDLING:
        ==============================
        STANDARD Mode (Global Integration Time):
          - integration_time_ms: Single value used by ALL channels (e.g., 93 ms)
          - s_mode_intensities: VARIABLE per channel (e.g., {'a': 187, 'b': 203, 'c': 195, 'd': 178})
          - p_mode_intensities: VARIABLE per channel (e.g., {'a': 238, 'b': 255, 'c': 245, 'd': 229})
          - per_channel_integration_times: None (not used)
          - Interpretation: All channels share SAME integration time, but DIFFERENT LED intensities

        ALTERNATIVE Mode (Global LED Intensity):
          - integration_time_ms: MAX integration time across all channels (e.g., 120 ms)
          - s_mode_intensities: FIXED at 255 for all channels ({'a': 255, 'b': 255, 'c': 255, 'd': 255})
          - p_mode_intensities: FIXED at 255 for all channels ({'a': 255, 'b': 255, 'c': 255, 'd': 255})
          - per_channel_integration_times: Dict per channel (e.g., {'a': 85, 'b': 95, 'c': 120, 'd': 110})
          - Interpretation: All channels use SAME LED intensity (255), but DIFFERENT integration times

        CRITICAL FOR QC VALIDATION:
        The S-ref spectra saved here are captured AFTER live mode boost optimization.
        This ensures QC validation compares against the actual live running parameters,
        not the calibration baseline.

        Args:
            integration_time_ms: Calibrated integration time in milliseconds
                                 STANDARD mode: global value for all channels
                                 ALTERNATIVE mode: maximum integration time across channels
            s_mode_intensities: S-mode LED intensities per channel {'a': 128, ...}
                                STANDARD mode: variable per channel
                                ALTERNATIVE mode: all set to 255
            p_mode_intensities: P-mode LED intensities per channel {'a': 172, ...}
                                STANDARD mode: variable per channel
                                ALTERNATIVE mode: all set to 255
            s_ref_spectra: S-mode reference spectra per channel (AFTER boost if provided)
            s_ref_wavelengths: Optional wavelength array (stored separately if provided)
            live_boost_integration_ms: Optional boosted integration time for live mode (P-mode)
            live_boost_led_intensities: Optional boosted LED intensities for live mode
            live_boost_factor: Optional boost factor applied (e.g., 1.5× for 50% → 75%)
            calibration_method: 'standard' or 'alternative' - indicates which calibration mode was used
            per_channel_integration_times: Optional dict of integration times per channel (ALTERNATIVE mode only)
                                           e.g., {'a': 85, 'b': 95, 'c': 120, 'd': 110}

        """
        try:
            logger.info(
                "💾 Saving LED calibration to device_config.json (single source of truth)",
            )

            # Handle dict input (new format) vs individual parameters (legacy format)
            if calibration_data is not None:
                # Extract values from dict
                integration_time_ms = calibration_data.get(
                    "integration_time_ms", integration_time_ms,
                )
                s_mode_intensities = calibration_data.get(
                    "s_mode_intensities", s_mode_intensities,
                )
                p_mode_intensities = calibration_data.get(
                    "p_mode_intensities", p_mode_intensities,
                )
                s_ref_spectra = calibration_data.get(
                    "s_ref_signals", s_ref_spectra,
                )  # Note: dict uses 's_ref_signals'
                p_ref_spectra = calibration_data.get("p_ref_signals", p_ref_spectra)
                s_ref_wavelengths = calibration_data.get(
                    "wavelengths", s_ref_wavelengths,
                )
                calibration_method = calibration_data.get(
                    "calibration_method", calibration_method,
                )
                per_channel_integration_times = calibration_data.get(
                    "per_channel_integration_times", per_channel_integration_times,
                )
                weakest_channel = calibration_data.get(
                    "weakest_channel", weakest_channel,
                )
                # Note: live_boost parameters not in calibration_data dict

            # Determine weakest channel (use provided value or calculate from S-mode intensities)
            if weakest_channel is None and s_mode_intensities:
                weakest_channel = min(s_mode_intensities, key=s_mode_intensities.get)

            # Create/update led_calibration section
            self.config["led_calibration"] = {
                "calibration_date": datetime.now().isoformat(),
                "calibration_method": calibration_method,  # 'standard' or 'alternative'
                "integration_time_ms": int(integration_time_ms),
                "s_mode_intensities": {
                    ch: int(val) for ch, val in s_mode_intensities.items()
                },
                "p_mode_intensities": {
                    ch: int(val) for ch, val in p_mode_intensities.items()
                },
                "weakest_channel": weakest_channel,  # Hardware fingerprint (stored from calibration)
                "s_ref_baseline": {
                    ch: spec.tolist() if isinstance(spec, np.ndarray) else spec
                    for ch, spec in s_ref_spectra.items()
                },
                "s_ref_max_intensity": {
                    ch: float(np.max(np.array(spec)))
                    for ch, spec in s_ref_spectra.items()
                },
            }

            # Save P-mode reference spectra if provided
            if p_ref_spectra:
                self.config["led_calibration"]["p_ref_baseline"] = {
                    ch: spec.tolist() if isinstance(spec, np.ndarray) else spec
                    for ch, spec in p_ref_spectra.items()
                }
                self.config["led_calibration"]["p_ref_max_intensity"] = {
                    ch: float(np.max(np.array(spec)))
                    for ch, spec in p_ref_spectra.items()
                }
                logger.info(
                    f"   P-ref baseline: {len(p_ref_spectra)} channels × {len(next(iter(p_ref_spectra.values())))} pixels",
                )

            # Save per-channel integration times for ALTERNATIVE mode
            if calibration_method == "alternative" and per_channel_integration_times:
                self.config["led_calibration"]["per_channel_integration_times"] = {
                    ch: int(val) for ch, val in per_channel_integration_times.items()
                }
                logger.info(
                    f"   Per-channel integration times: {per_channel_integration_times}",
                )

            # Store live mode boost parameters (for QC validation)
            if live_boost_integration_ms is not None:
                self.config["led_calibration"]["live_boost_integration_ms"] = int(
                    live_boost_integration_ms,
                )
                logger.info(
                    f"   Live boost integration: {live_boost_integration_ms} ms",
                )

            if live_boost_led_intensities is not None:
                self.config["led_calibration"]["live_boost_led_intensities"] = {
                    ch: int(val) for ch, val in live_boost_led_intensities.items()
                }
                logger.info(f"   Live boost LEDs: {live_boost_led_intensities}")

            if live_boost_factor is not None:
                self.config["led_calibration"]["live_boost_factor"] = float(
                    live_boost_factor,
                )
                logger.info(f"   Live boost factor: {live_boost_factor:.2f}×")

            # Store wavelengths if provided (for reference)
            if s_ref_wavelengths is not None:
                # Ensure it's a numpy array before calling tolist()
                if isinstance(s_ref_wavelengths, np.ndarray):
                    self.config["led_calibration"]["s_ref_wavelengths"] = (
                        s_ref_wavelengths.tolist()
                    )
                elif isinstance(s_ref_wavelengths, list):
                    self.config["led_calibration"]["s_ref_wavelengths"] = (
                        s_ref_wavelengths
                    )
                else:
                    # Try to convert to numpy array first
                    self.config["led_calibration"]["s_ref_wavelengths"] = np.array(
                        s_ref_wavelengths,
                    ).tolist()

            # Update calibration status
            self.config["calibration"]["s_mode_calibration_date"] = (
                datetime.now().isoformat()
            )
            self.config["calibration"]["user_calibrated"] = True

            # Save to disk
            self.save()

            logger.info("[OK] LED calibration saved successfully")
            logger.info(f"   Calibration method: {calibration_method.upper()}")
            logger.info("   Calibration baseline:")
            if calibration_method == "standard":
                logger.info(
                    f"      Integration time: {integration_time_ms} ms (global)",
                )
            else:
                logger.info(
                    f"      Integration time: {integration_time_ms} ms (max across channels)",
                )
            logger.info(f"      S-mode LEDs: {s_mode_intensities}")
            logger.info(f"      P-mode LEDs: {p_mode_intensities}")
            if live_boost_integration_ms:
                logger.info("   Live mode boost:")
                logger.info(
                    f"      Integration time: {live_boost_integration_ms} ms ({live_boost_factor:.2f}× boost)",
                )
                logger.info(f"      Adjusted LEDs: {live_boost_led_intensities}")
            logger.info(
                f"   S-ref baseline: {len(s_ref_spectra)} channels × {len(next(iter(s_ref_spectra.values())))} pixels",
            )

        except Exception as e:
            logger.error(f"Failed to save LED calibration: {e}")
            raise

    def load_led_calibration(self) -> dict[str, Any] | None:
        """Load LED calibration baseline from device_config.json.

        Returns:
            Dictionary containing calibration data:
            - calibration_date: ISO timestamp
            - calibration_method: 'standard' or 'alternative'
            - integration_time_ms: int (global for standard, max for alternative)
            - s_mode_intensities: dict (variable for standard, all 255 for alternative)
            - p_mode_intensities: dict (variable for standard, all 255 for alternative)
            - per_channel_integration_times: dict (only for alternative mode)
            - s_ref_baseline: dict of numpy arrays
            - s_ref_max_intensity: dict of float
            - s_ref_wavelengths: numpy array (if available)

            Returns None if no calibration stored.

        """
        if "led_calibration" not in self.config:
            logger.debug("No LED calibration found in device_config.json")
            return None

        try:
            cal = self.config["led_calibration"].copy()

            # Convert lists back to numpy arrays
            if "s_ref_baseline" in cal:
                cal["s_ref_baseline"] = {
                    ch: np.array(spec) for ch, spec in cal["s_ref_baseline"].items()
                }

            # Convert P-ref baseline if present
            if "p_ref_baseline" in cal:
                cal["p_ref_baseline"] = {
                    ch: np.array(spec) for ch, spec in cal["p_ref_baseline"].items()
                }
                logger.debug(
                    f"   Loaded P-ref baseline: {len(cal['p_ref_baseline'])} channels",
                )

            if "s_ref_wavelengths" in cal:
                cal["s_ref_wavelengths"] = np.array(cal["s_ref_wavelengths"])

            # Optional: pre-QC dark snapshot
            if "pre_qc_dark_snapshot" in cal and isinstance(
                cal["pre_qc_dark_snapshot"], list,
            ):
                try:
                    cal["pre_qc_dark_snapshot"] = np.array(cal["pre_qc_dark_snapshot"])
                except Exception:
                    # Leave as-is if conversion fails
                    pass

            logger.debug(f"Loaded LED calibration from {cal['calibration_date']}")
            return cal

        except Exception as e:
            logger.error(f"Failed to load LED calibration: {e}")
            return None

    def get_calibration_age_days(self) -> float | None:
        """Get age of stored calibration in days.

        Returns:
            Age in days, or None if no calibration stored

        """
        cal = self.load_led_calibration()
        if cal is None:
            return None

        try:
            cal_date = datetime.fromisoformat(cal["calibration_date"])
            return (datetime.now() - cal_date).total_seconds() / 86400.0
        except Exception:
            return None

    def clear_led_calibration(self) -> None:
        """Clear stored LED calibration data."""
        if "led_calibration" in self.config:
            del self.config["led_calibration"]
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
        mean_counts: dict[str, float] | None = None,
        saturated_on_first_pass: list[str] | None = None,
        test_led_intensity: int | None = None,
        test_region_nm: tuple[float, float] | None = None,
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
            if "diagnostics" not in self.config:
                self.config["diagnostics"] = {}

            # Build a compact ranked order list
            ranked_order = [ch for ch, _ in ranked_channels]

            self.config["diagnostics"]["led_ranking"] = {
                "date": now,
                "weakest_channel": weakest_channel,
                "ranked_order": ranked_order,
                "percent_of_weakest": {
                    k: float(v) for k, v in percent_of_weakest.items()
                },
            }

            if mean_counts is not None:
                self.config["diagnostics"]["led_ranking"]["mean_counts"] = {
                    k: float(v) for k, v in mean_counts.items()
                }

            if saturated_on_first_pass is not None:
                self.config["diagnostics"]["led_ranking"]["saturated_on_first_pass"] = (
                    list(saturated_on_first_pass)
                )

            if test_led_intensity is not None:
                self.config["diagnostics"]["led_ranking"]["test_led_intensity"] = int(
                    test_led_intensity,
                )

            if test_region_nm is not None:
                self.config["diagnostics"]["led_ranking"]["test_region_nm"] = [
                    float(test_region_nm[0]),
                    float(test_region_nm[1]),
                ]

            # Persist to disk
            self.save()
            logger.info(
                "[OK] Saved LED ranking diagnostics to device_config.json → diagnostics.led_ranking",
            )

        except Exception as e:
            logger.error(f"Failed to save LED ranking diagnostics: {e}")
            # Don't raise to avoid breaking calibration; diagnostics are optional


def get_device_config(config_path: str | None = None) -> DeviceConfiguration:
    """Get device configuration instance (convenience function).

    Args:
        config_path: Optional path to configuration file

    Returns:
        DeviceConfiguration instance

    """
    return DeviceConfiguration(config_path)


if __name__ == "__main__":
    # Example usage and testing

    # Create configuration
    config = DeviceConfiguration()

    # Set some values
    config.set_optical_fiber_diameter(200)
    config.set_led_pcb_model("luminus_cool_white")
    config.set_spectrometer_serial("FLMT09788")

    # Get values

    # Validate
    is_valid, errors = config.validate()
    if is_valid:
        pass
    else:
        for _error in errors:
            pass

    # Save
    config.save()

    # Test fiber diameter validation
    try:
        config.set_optical_fiber_diameter(150)  # Invalid
    except ValueError:
        pass

    # Test frequency limits
    num_leds = 4
    limits = config.get_frequency_limits(num_leds)
