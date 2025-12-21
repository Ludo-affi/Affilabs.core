from __future__ import annotations

"""Device-Specific Configuration Manager.

Manages per-device configuration files and optical calibration data.
Each device (identified by detector serial number) gets its own directory
with device_config.json and optical_calibration.json files.

Directory Structure:
    config/devices/
    ├── FLMT09116/
    │   ├── device_config.json
    │   └── optical_calibration.json
    ├── FLMT09788/
    │   ├── device_config.json
    │   └── optical_calibration.json

Workflow:
    1. Detect detector serial number on connection
    2. Load device-specific config from config/devices/{serial}/
    3. Check if optical_calibration.json exists
    4. If missing → automatically trigger optical calibration
    5. If exists → load and use it
    6. Manual recalibration available from settings (overwrites)

Author: GitHub Copilot
Date: November 17, 2025
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from affilabs.utils.logger import logger


class DeviceManager:
    """Manage device-specific configurations and optical calibrations."""

    def __init__(self, base_config_dir: str = "config") -> None:
        """Initialize device manager.

        Args:
            base_config_dir: Base configuration directory (default: "config")

        """
        self.base_config_dir = Path(base_config_dir)
        self.devices_dir = self.base_config_dir / "devices"
        self.devices_dir.mkdir(parents=True, exist_ok=True)

        self.current_device_serial: str | None = None
        self.current_device_dir: Path | None = None
        self.device_config: dict[str, Any] | None = None

        logger.debug(f"DeviceManager initialized: {self.devices_dir}")

    def set_device(self, serial_number: str) -> Path:
        """Set current device and create device directory if needed.

        Args:
            serial_number: Detector serial number (e.g., "FLMT09116")

        Returns:
            Path to device-specific directory

        Raises:
            ValueError: If serial number is empty or invalid

        """
        if not serial_number or not serial_number.strip():
            msg = "Device serial number cannot be empty"
            raise ValueError(msg)

        serial_number = serial_number.strip().upper()
        self.current_device_serial = serial_number
        self.current_device_dir = self.devices_dir / serial_number

        # Create device directory if it doesn't exist
        self.current_device_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"📱 Device set: {serial_number}")
        logger.info(f"   Config directory: {self.current_device_dir}")

        # Load device config (create if doesn't exist)
        self._load_or_create_device_config()

        return self.current_device_dir

    def _load_or_create_device_config(self) -> dict[str, Any]:
        """Load device config or create from template if doesn't exist.

        Returns:
            Device configuration dictionary

        """
        if not self.current_device_dir:
            msg = "No device set. Call set_device() first."
            raise RuntimeError(msg)

        config_file = self.current_device_dir / "device_config.json"

        if config_file.exists():
            # Load existing config
            try:
                with open(config_file) as f:
                    self.device_config = json.load(f)
                logger.info(f"[OK] Loaded device config: {config_file.name}")
                return self.device_config
            except json.JSONDecodeError as e:
                logger.error(f"[ERROR] Invalid JSON in device config: {e}")
                logger.info("   Creating new config from template")
                # Fall through to create new config

        # Create new config from global template
        template_file = self.base_config_dir / "device_config.json"

        if template_file.exists():
            # Copy template
            try:
                with open(template_file) as f:
                    self.device_config = json.load(f)

                # Update device-specific fields
                if "device_info" not in self.device_config:
                    self.device_config["device_info"] = {}

                self.device_config["device_info"]["device_id"] = (
                    self.current_device_serial
                )
                self.device_config["device_info"]["created_date"] = (
                    datetime.now().isoformat()
                )
                self.device_config["device_info"]["last_modified"] = (
                    datetime.now().isoformat()
                )

                if "hardware" not in self.device_config:
                    self.device_config["hardware"] = {}

                self.device_config["hardware"]["spectrometer_serial"] = (
                    self.current_device_serial
                )

                # Save device-specific config
                self._save_device_config()

                logger.info(
                    f"[OK] Created device config from template: {config_file.name}",
                )
                return self.device_config

            except Exception as e:
                logger.error(f"[ERROR] Failed to create config from template: {e}")
                raise

        else:
            # No template, create minimal config
            self.device_config = self._create_minimal_config()
            self._save_device_config()
            logger.warning(
                f"[WARN] No template found, created minimal config: {config_file.name}",
            )
            return self.device_config

    def _create_minimal_config(self) -> dict[str, Any]:
        """Create minimal device configuration.

        Returns:
            Minimal configuration dictionary

        """
        return {
            "device_info": {
                "config_version": "1.0",
                "created_date": datetime.now().isoformat(),
                "last_modified": datetime.now().isoformat(),
                "device_id": self.current_device_serial,
            },
            "hardware": {
                "spectrometer_model": "Flame-T",
                "spectrometer_serial": self.current_device_serial,
                "controller_model": "Raspberry Pi Pico P4SPR",
                "led_pcb_model": "luminus_cool_white",
                "optical_fiber_diameter_um": 200,
                "polarizer_type": "circular",
            },
            "calibration": {
                "dark_calibration_date": None,
                "s_mode_calibration_date": None,
                "p_mode_calibration_date": None,
                "factory_calibrated": False,
                "user_calibrated": False,
                "preferred_calibration_mode": "global",
            },
            "optical_calibration": {
                "optical_calibration_file": None,
                "afterglow_correction_enabled": True,
                "calibration_date": None,
            },
        }

    def _save_device_config(self) -> None:
        """Save current device configuration to file.

        Also saves startup_config.json to calibrations/active/{SERIAL}/ for quick access.
        """
        if not self.current_device_dir or not self.device_config:
            msg = "No device config to save"
            raise RuntimeError(msg)

        config_file = self.current_device_dir / "device_config.json"

        # Update last modified timestamp
        if "device_info" not in self.device_config:
            self.device_config["device_info"] = {}
        self.device_config["device_info"]["last_modified"] = datetime.now().isoformat()

        try:
            with open(config_file, "w") as f:
                json.dump(self.device_config, f, indent=2)
            logger.debug(f"Device config saved: {config_file}")

            # ALSO save startup config to active calibrations
            if self.current_device_serial:
                self._save_startup_config_to_active()

        except Exception as e:
            logger.error(f"Failed to save device config: {e}")
            raise

    def _save_startup_config_to_active(self) -> None:
        """Save startup config to calibrations/active/{SERIAL}/startup_config.json."""
        try:
            project_root = Path(__file__).resolve().parents[2]
            active_dir = project_root / "calibrations" / "active" / self.current_device_serial
            active_dir.mkdir(parents=True, exist_ok=True)

            # Extract startup LED settings from device config
            startup_config = {
                "device_serial": self.current_device_serial,
                "last_updated": datetime.now().isoformat(),
                "source": "device_config.json",
                "led_intensities": {
                    "s_mode": {
                        "a": self.device_config.get("led_a_s", 128),
                        "b": self.device_config.get("led_b_s", 128),
                        "c": self.device_config.get("led_c_s", 128),
                        "d": self.device_config.get("led_d_s", 128),
                    },
                    "p_mode": {
                        "a": self.device_config.get("led_a_p", 128),
                        "b": self.device_config.get("led_b_p", 128),
                        "c": self.device_config.get("led_c_p", 128),
                        "d": self.device_config.get("led_d_p", 128),
                    }
                },
                "integration_times": {
                    "s_mode_ms": self.device_config.get("integration_time_s", 30.0),
                    "p_mode_ms": self.device_config.get("integration_time_p", 30.0),
                }
            }

            startup_file = active_dir / "startup_config.json"
            with open(startup_file, "w") as f:
                json.dump(startup_config, f, indent=2)

            logger.debug(f"Startup config saved to active: {startup_file}")
        except Exception as e:
            logger.warning(f"Could not save startup config to active location: {e}")

    def get_optical_calibration_path(self) -> Path | None:
        """Get path to optical calibration file for current device.

        Returns:
            Path to optical_calibration.json if exists, None otherwise

        """
        if not self.current_device_dir:
            msg = "No device set. Call set_device() first."
            raise RuntimeError(msg)

        optical_cal_file = self.current_device_dir / "optical_calibration.json"

        if optical_cal_file.exists():
            return optical_cal_file
        return None

    def has_optical_calibration(self) -> bool:
        """Check if current device has optical calibration file.

        Returns:
            True if optical calibration exists, False otherwise

        """
        return self.get_optical_calibration_path() is not None

    def needs_optical_calibration(self) -> bool:
        """Check if current device needs optical calibration.

        Returns:
            True if calibration is missing, False if exists

        """
        return not self.has_optical_calibration()

    def set_optical_calibration_path(self, calibration_path: Path) -> None:
        """Update device config with optical calibration path.

        This is called after optical calibration is complete to update
        the device config with the calibration file location.

        Args:
            calibration_path: Path to optical calibration file

        """
        if not self.device_config:
            msg = "No device config loaded"
            raise RuntimeError(msg)

        if "optical_calibration" not in self.device_config:
            self.device_config["optical_calibration"] = {}

        # Store relative path from device directory
        relative_path = calibration_path.relative_to(self.current_device_dir)

        self.device_config["optical_calibration"]["optical_calibration_file"] = str(
            relative_path,
        )
        self.device_config["optical_calibration"]["calibration_date"] = (
            datetime.now().isoformat()
        )
        self.device_config["optical_calibration"]["afterglow_correction_enabled"] = True

        self._save_device_config()

        logger.info("[OK] Optical calibration path updated in device config")
        logger.info(f"   File: {relative_path}")

    def get_device_config(self) -> dict[str, Any]:
        """Get current device configuration.

        Returns:
            Device configuration dictionary

        Raises:
            RuntimeError: If no device is set

        """
        if not self.device_config:
            msg = "No device config loaded. Call set_device() first."
            raise RuntimeError(msg)

        return self.device_config

    def update_calibration_status(
        self,
        calibration_type: str,
        status: bool = True,
    ) -> None:
        """Update calibration status in device config.

        Args:
            calibration_type: Type of calibration ('dark', 's_mode', 'p_mode', 'optical')
            status: Calibration status (default: True)

        """
        if not self.device_config:
            msg = "No device config loaded"
            raise RuntimeError(msg)

        if "calibration" not in self.device_config:
            self.device_config["calibration"] = {}

        timestamp = datetime.now().isoformat() if status else None

        if calibration_type == "optical":
            if "optical_calibration" not in self.device_config:
                self.device_config["optical_calibration"] = {}
            self.device_config["optical_calibration"]["calibration_date"] = timestamp
        else:
            cal_key = f"{calibration_type}_calibration_date"
            self.device_config["calibration"][cal_key] = timestamp

        self._save_device_config()
        logger.debug(f"Updated calibration status: {calibration_type} = {status}")

    def list_devices(self) -> list[str]:
        """List all device serial numbers with configurations.

        Returns:
            List of device serial numbers

        """
        devices = []
        if self.devices_dir.exists():
            for device_dir in self.devices_dir.iterdir():
                if device_dir.is_dir():
                    # Check if it has a device_config.json
                    if (device_dir / "device_config.json").exists():
                        devices.append(device_dir.name)

        return sorted(devices)

    def get_device_info(self, serial_number: str) -> dict[str, Any] | None:
        """Get device information summary.

        Args:
            serial_number: Device serial number

        Returns:
            Dictionary with device info, or None if device not found

        """
        device_dir = self.devices_dir / serial_number
        config_file = device_dir / "device_config.json"

        if not config_file.exists():
            return None

        try:
            with open(config_file) as f:
                config = json.load(f)

            optical_cal_file = device_dir / "optical_calibration.json"
            has_optical_cal = optical_cal_file.exists()

            return {
                "serial": serial_number,
                "has_optical_calibration": has_optical_cal,
                "created_date": config.get("device_info", {}).get("created_date"),
                "last_modified": config.get("device_info", {}).get("last_modified"),
                "calibration_status": config.get("calibration", {}),
                "hardware": config.get("hardware", {}),
            }
        except Exception as e:
            logger.error(f"Failed to read device info for {serial_number}: {e}")
            return None


# Global device manager instance
_device_manager: DeviceManager | None = None


def get_device_manager() -> DeviceManager:
    """Get global device manager instance (singleton).

    Returns:
        DeviceManager instance

    """
    global _device_manager
    if _device_manager is None:
        _device_manager = DeviceManager()
    return _device_manager
