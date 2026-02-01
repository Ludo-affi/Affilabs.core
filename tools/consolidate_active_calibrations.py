"""Consolidate Active Calibrations - Migration Utility.

This script consolidates calibration data from legacy locations into the new
unified `calibrations/active/{SERIAL}/` structure.

Consolidates:
1. Latest LED model per device (from led_calibration_official/spr_calibration/data/)
2. Latest device profile per device (from calibration_data/)
3. Current startup config per device (from config/devices/{SERIAL}/device_config.json)

Run this after implementing the new calibration structure to migrate existing data.

Author: ezControl OEM System
Date: December 19, 2025
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional


def consolidate_active_calibrations(project_root: Optional[Path] = None) -> None:
    """Consolidate active calibrations into calibrations/active/ structure.
    
    Args:
        project_root: Project root path (if None, auto-detect)
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parents[1]

    print("=" * 80)
    print("CONSOLIDATING ACTIVE CALIBRATIONS")
    print("=" * 80)
    print(f"Project root: {project_root}\n")

    active_dir = project_root / "calibrations" / "active"
    active_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Find all devices
    devices = set()

    # From config/devices/
    config_devices_dir = project_root / "config" / "devices"
    if config_devices_dir.exists():
        for device_dir in config_devices_dir.iterdir():
            if device_dir.is_dir():
                devices.add(device_dir.name)

    # From calibration_data/
    calibration_data_dir = project_root / "calibration_data"
    if calibration_data_dir.exists():
        for f in calibration_data_dir.glob("device_*.json"):
            # Extract serial from filename: device_FLMT09788_20251218.json
            parts = f.stem.split("_")
            if len(parts) >= 2:
                serial = parts[1]
                devices.add(serial)

    print(f"Found {len(devices)} device(s): {sorted(devices)}\n")

    # Step 2: Consolidate each device
    for device_serial in sorted(devices):
        print(f"\n{'=' * 80}")
        print(f"DEVICE: {device_serial}")
        print(f"{'=' * 80}")

        device_active_dir = active_dir / device_serial
        device_active_dir.mkdir(parents=True, exist_ok=True)

        # 2a. LED Model (from led_calibration_official/spr_calibration/data/)
        led_model_source_dir = (
            project_root / "led_calibration_official" / "spr_calibration" / "data"
        )
        if led_model_source_dir.exists():
            # Find latest 3-stage model for this device
            model_files = sorted(
                led_model_source_dir.glob("led_calibration_3stage_*.json"),
                reverse=True
            )

            matched_model = None
            for model_file in model_files:
                try:
                    with open(model_file) as f:
                        data = json.load(f)
                    file_serial = str(data.get("detector_serial", "")).strip().upper()
                    if file_serial == device_serial.upper():
                        matched_model = model_file
                        break
                except Exception as e:
                    print(f"  ⚠️  Could not read {model_file.name}: {e}")

            if matched_model:
                dest = device_active_dir / "led_model.json"
                shutil.copy2(matched_model, dest)
                print(f"  ✅ LED model: {matched_model.name} → led_model.json")
            else:
                print(f"  ⚠️  No LED model found for {device_serial}")

        # 2b. Device Profile (from calibration_data/)
        if calibration_data_dir.exists():
            # Find latest device profile
            profile_files = sorted(
                calibration_data_dir.glob(f"device_{device_serial}_*.json"),
                reverse=True
            )

            if profile_files:
                latest_profile = profile_files[0]
                dest = device_active_dir / "device_profile.json"
                shutil.copy2(latest_profile, dest)
                print(f"  ✅ Device profile: {latest_profile.name} → device_profile.json")
            else:
                print(f"  ⚠️  No device profile found for {device_serial}")

        # 2c. Startup Config (from config/devices/{SERIAL}/device_config.json)
        device_config_file = config_devices_dir / device_serial / "device_config.json"
        if device_config_file.exists():
            try:
                with open(device_config_file) as f:
                    device_config = json.load(f)

                # Extract startup LED settings
                startup_config = {
                    "device_serial": device_serial,
                    "last_updated": datetime.now().isoformat(),
                    "source": "device_config.json",
                    "led_intensities": {
                        "s_mode": {
                            "a": device_config.get("led_a_s", 128),
                            "b": device_config.get("led_b_s", 128),
                            "c": device_config.get("led_c_s", 128),
                            "d": device_config.get("led_d_s", 128),
                        },
                        "p_mode": {
                            "a": device_config.get("led_a_p", 128),
                            "b": device_config.get("led_b_p", 128),
                            "c": device_config.get("led_c_p", 128),
                            "d": device_config.get("led_d_p", 128),
                        }
                    },
                    "integration_times": {
                        "s_mode_ms": device_config.get("integration_time_s", 30.0),
                        "p_mode_ms": device_config.get("integration_time_p", 30.0),
                    }
                }

                dest = device_active_dir / "startup_config.json"
                with open(dest, "w") as f:
                    json.dump(startup_config, f, indent=2)

                print("  ✅ Startup config: device_config.json → startup_config.json")
            except Exception as e:
                print(f"  ⚠️  Could not extract startup config: {e}")
        else:
            print(f"  ⚠️  No device config found for {device_serial}")

        print(f"\n  📁 Consolidated to: calibrations/active/{device_serial}/")

    print("\n" + "=" * 80)
    print("✅ CONSOLIDATION COMPLETE")
    print("=" * 80)
    print(f"Active calibrations location: {active_dir}")
    print("\nAll calibration loaders will now check this location first.")


if __name__ == "__main__":
    consolidate_active_calibrations()
