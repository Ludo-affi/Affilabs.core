from __future__ import annotations

"""Device-Specific Afterglow Calibration Integration.

This module integrates the DeviceManager with the calibration and data acquisition
workflows to ensure each device (detector) gets its own optical calibration file
and automatic afterglow correction.

Integration Points:
===================

1. HARDWARE CONNECTION (main/main.py or state machine)
   - After spectrometer connects, get serial number
   - Call DeviceManager.set_device(serial_number)
   - DeviceManager creates/loads device-specific config directory

2. CALIBRATION START (utils/spr_calibrator.py)
   - Check if optical calibration exists for device
   - If missing → automatically run optical calibration
   - Save optical calibration to device directory
   - Update device config with calibration path

3. DATA ACQUISITION (utils/spr_data_acquisition.py)
   - Load device-specific optical calibration file
   - Initialize AfterglowCorrection with device calibration
   - Apply afterglow correction during live measurements

4. SETTINGS MENU (widgets/settings or channelmenu)
   - Add "Recalibrate Afterglow" button
   - Triggers optical calibration (overwrites existing)

Directory Structure:
====================
config/
└── devices/
    ├── FLMT09116/
    │   ├── device_config.json
    │   └── optical_calibration.json
    ├── FLMT09788/
    │   ├── device_config.json
    │   └── optical_calibration.json

Key Functions:
==============
"""

from pathlib import Path
from typing import Any

from affilabs.utils.device_manager import get_device_manager
from affilabs.utils.logger import logger


def initialize_device_on_connection(usb_device: Any) -> Path | None:
    """Initialize device-specific configuration when spectrometer connects.

    Call this after successful spectrometer connection to set up device-specific
    directories and load configuration.

    Args:
        usb_device: USB spectrometer object with serial_number attribute

    Returns:
        Path to device directory, or None if initialization failed

    Example:
        # In main.py after spectrometer connection:
        if self.usb is not None:
            device_dir = initialize_device_on_connection(self.usb)
            if device_dir:
                logger.info(f"Device initialized: {device_dir}")

    """
    try:
        # Get detector serial number
        serial_number = getattr(usb_device, "serial_number", None) or getattr(
            usb_device,
            "_serial_number",
            None,
        )

        if not serial_number or serial_number == "Unknown":
            logger.warning(
                "[WARN] Cannot initialize device - serial number not available",
            )
            return None

        # Set up device-specific configuration
        device_manager = get_device_manager()
        device_dir = device_manager.set_device(serial_number)

        logger.debug(f"Device initialized: {serial_number}")
        logger.debug(f"   Config directory: {device_dir}")

        return device_dir

    except Exception as e:
        logger.error(f"[ERROR] Device initialization failed: {e}")
        return None


def check_and_request_optical_calibration() -> bool:
    """Check if current device needs optical calibration.

    Call this before starting measurements to ensure afterglow correction
    is available. If calibration is missing, this returns True to indicate
    that optical calibration should be run.

    Returns:
        True if optical calibration needed, False if already exists

    Example:
        # In calibration workflow:
        if check_and_request_optical_calibration():
            logger.info("🔬 Optical calibration needed - starting automatically")
            run_optical_calibration()

    """
    try:
        device_manager = get_device_manager()

        if device_manager.current_device_serial is None:
            logger.warning("[WARN] No device set - cannot check optical calibration")
            return False

        needs_calibration = device_manager.needs_optical_calibration()

        if needs_calibration:
            logger.warning(
                f"[WARN] Optical calibration missing for device {device_manager.current_device_serial}",
            )
            logger.info(
                "   Afterglow correction will be unavailable until calibration is run",
            )

        return needs_calibration

    except Exception as e:
        logger.error(f"[ERROR] Failed to check optical calibration status: {e}")
        return False


def get_device_optical_calibration_path() -> Path | None:
    """Get path to optical calibration file for current device.

    Returns:
        Path to optical_calibration.json if exists, None otherwise

    Example:
        # In data acquisition initialization:
        optical_cal_path = get_device_optical_calibration_path()
        if optical_cal_path:
            self.afterglow_correction = AfterglowCorrection(optical_cal_path)

    """
    try:
        device_manager = get_device_manager()

        if device_manager.current_device_serial is None:
            logger.warning("[WARN] No device set - cannot get optical calibration path")
            return None

        return device_manager.get_optical_calibration_path()

    except Exception as e:
        logger.error(f"[ERROR] Failed to get optical calibration path: {e}")
        return None


def save_optical_calibration_result(calibration_file_path: Path) -> bool:
    """Update device config after optical calibration completes.

    Call this after optical calibration successfully saves its calibration file
    to update the device configuration.

    Args:
        calibration_file_path: Path to the optical calibration JSON file

    Returns:
        True if device config updated, False otherwise

    Example:
        # In optical calibration tool after saving calibration:
        calibration_path = device_dir / "optical_calibration.json"
        import tempfile

        # Atomic write
        with tempfile.NamedTemporaryFile(
            mode='w',
            encoding='utf-8',
            dir=calibration_path.parent,
            delete=False,
            suffix='.tmp'
        ) as tmp_file:
            json.dump(calibration_data, tmp_file, indent=2)
            tmp_path = Path(tmp_file.name)

        tmp_path.replace(calibration_path)

        save_optical_calibration_result(calibration_path)

    """
    try:
        device_manager = get_device_manager()

        if device_manager.current_device_serial is None:
            logger.error(
                "[ERROR] No device set - cannot save optical calibration result",
            )
            return False

        device_manager.set_optical_calibration_path(calibration_file_path)
        device_manager.update_calibration_status("optical", status=True)

        logger.info("[OK] Device config updated with optical calibration path")
        return True

    except Exception as e:
        logger.error(f"[ERROR] Failed to save optical calibration result: {e}")
        return False


def get_device_config_dict() -> dict[str, Any] | None:
    """Get current device configuration as dictionary.

    Returns:
        Device configuration dictionary, or None if no device set

    Example:
        # In calibrator or data acquisition initialization:
        device_config = get_device_config_dict()
        if device_config:
            # Use device-specific configuration
            pass

    """
    try:
        device_manager = get_device_manager()

        if device_manager.current_device_serial is None:
            logger.warning("[WARN] No device set - cannot get device config")
            return None

        return device_manager.get_device_config()

    except Exception as e:
        logger.error(f"[ERROR] Failed to get device config: {e}")
        return None


def update_firmware_version(firmware_version: str) -> bool:
    """Update firmware version in device config.

    Call this after successful firmware update or when firmware version is detected.

    Args:
        firmware_version: Firmware version string (e.g., "V1.1")

    Returns:
        True if config updated successfully, False otherwise

    Example:
        # In hardware_manager after firmware update:
        from affilabs.utils.device_integration import update_firmware_version

        current_version = controller.get_version()
        update_firmware_version(current_version)

    """
    try:
        device_manager = get_device_manager()

        if device_manager.current_device_serial is None:
            logger.warning("[WARN] No device set - cannot update firmware version")
            return False

        # Update hardware section with firmware version
        if "hardware" not in device_manager.device_config:
            device_manager.device_config["hardware"] = {}

        device_manager.device_config["hardware"]["controller_firmware_version"] = (
            firmware_version
        )

        # Save config
        device_manager._save_device_config()

        logger.info(
            f"[OK] Updated firmware version in device config: {firmware_version}",
        )
        return True

    except Exception as e:
        logger.error(f"[ERROR] Failed to update firmware version: {e}")
        return False


def list_all_devices() -> list[str]:
    """List all devices with configuration files.

    Returns:
        List of device serial numbers

    Example:
        # In settings menu to show available devices:
        devices = list_all_devices()
        for device in devices:
            print(f"Device: {device}")

    """
    try:
        device_manager = get_device_manager()
        return device_manager.list_devices()

    except Exception as e:
        logger.error(f"[ERROR] Failed to list devices: {e}")
        return []


# Integration workflow example:
"""
COMPLETE INTEGRATION WORKFLOW
==============================

1. HARDWARE CONNECTION
   --------------------
   # In main.py or state_machine.py after spectrometer connects:

   from affilabs.utils.device_integration import initialize_device_on_connection

   if self.usb is not None:
       device_dir = initialize_device_on_connection(self.usb)


2. CALIBRATION CHECK
   ------------------
   # In calibration start (after LED calibration completes):

   from affilabs.utils.device_integration import check_and_request_optical_calibration

   if check_and_request_optical_calibration():
       logger.info("🔬 Running automatic optical calibration...")
       # Run optical calibration here
       # (see next step)


3. OPTICAL CALIBRATION EXECUTION
   ------------------------------
   # In utils/afterglow_calibration.py or wherever optical calibration runs:

   from affilabs.utils.device_integration import (
       get_device_manager,
       save_optical_calibration_result
   )

   # Run optical calibration as normal
   calibration_data = perform_optical_calibration(...)

   # Save to device-specific directory
   device_manager = get_device_manager()
   device_dir = device_manager.current_device_dir
   calibration_path = device_dir / "optical_calibration.json"

   with open(calibration_path, 'w') as f:
       json.dump(calibration_data, f, indent=2)

   # Update device config
   save_optical_calibration_result(calibration_path)


4. DATA ACQUISITION INITIALIZATION
   --------------------------------
   # In utils/spr_data_acquisition.py __init__:

   from affilabs.utils.device_integration import get_device_optical_calibration_path

   # Load device-specific optical calibration
   optical_cal_path = get_device_optical_calibration_path()

   if optical_cal_path and optical_cal_path.exists():
       from afterglow_correction import AfterglowCorrection
       self.afterglow_correction = AfterglowCorrection(optical_cal_path)
       self.afterglow_correction_enabled = True
       logger.info(f"[OK] Loaded device-specific afterglow correction")
   else:
       logger.warning("[WARN] No optical calibration - afterglow correction disabled")
       self.afterglow_correction_enabled = False


5. SETTINGS MENU - MANUAL RECALIBRATION
   -------------------------------------
   # In widgets/settings.py or channelmenu.py:

   def on_recalibrate_afterglow_clicked(self):
       '''User requested manual afterglow recalibration.'''
       from affilabs.utils.device_integration import get_device_manager

       device_manager = get_device_manager()
       if device_manager.current_device_serial is None:
           QMessageBox.warning(self, "Error", "No device connected")
           return

       reply = QMessageBox.question(
           self,
           "Recalibrate Afterglow",
           f"This will recalibrate afterglow correction for device "
           f"{device_manager.current_device_serial}.\\n\\n"
           f"This process takes ~5-10 minutes.\\n\\nContinue?",
           QMessageBox.Yes | QMessageBox.No
       )

       if reply == QMessageBox.Yes:
           # Trigger optical calibration
           self.run_optical_calibration()
"""
