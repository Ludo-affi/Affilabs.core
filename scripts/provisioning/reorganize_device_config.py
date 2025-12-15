"""Reorganize device_config.json into a clean, well-structured format.
Removes wavelength arrays that don't belong in config, properly organizes sections.
"""

import json
from datetime import datetime
from pathlib import Path


def reorganize_device_config():
    """Load, clean, and reorganize device_config.json"""
    config_path = Path("config/device_config.json")
    backup_path = Path(
        f"config/device_config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
    )

    print(f"📖 Loading {config_path}...")
    with open(config_path) as f:
        old_config = json.load(f)

    print(f"💾 Creating backup at {backup_path}...")
    with open(backup_path, "w") as f:
        json.dump(old_config, f, indent=2)

    # Build new clean structure
    new_config = {
        "device_info": {
            "config_version": old_config.get("device_info", {}).get(
                "config_version",
                "1.0",
            ),
            "created_date": old_config.get("device_info", {}).get("created_date"),
            "last_modified": datetime.now().isoformat(),
            "device_id": old_config.get("device_info", {}).get("device_id"),
        },
        "hardware": {
            "led_pcb_model": old_config.get("hardware", {}).get("led_pcb_model"),
            "led_pcb_serial": old_config.get("hardware", {}).get("led_pcb_serial"),
            "spectrometer_model": old_config.get("hardware", {}).get(
                "spectrometer_model",
            ),
            "spectrometer_serial": old_config.get("hardware", {}).get(
                "spectrometer_serial",
            ),
            "controller_model": old_config.get("hardware", {}).get("controller_model"),
            "controller_serial": old_config.get("hardware", {}).get(
                "controller_serial",
            ),
            "optical_fiber_diameter_um": old_config.get("hardware", {}).get(
                "optical_fiber_diameter_um",
            ),
            "polarizer_type": old_config.get("hardware", {}).get("polarizer_type"),
        },
        "timing_parameters": {
            "led_a_delay_ms": old_config.get("timing_parameters", {}).get(
                "led_a_delay_ms",
                0,
            ),
            "led_b_delay_ms": old_config.get("timing_parameters", {}).get(
                "led_b_delay_ms",
                0,
            ),
            "led_c_delay_ms": old_config.get("timing_parameters", {}).get(
                "led_c_delay_ms",
                0,
            ),
            "led_d_delay_ms": old_config.get("timing_parameters", {}).get(
                "led_d_delay_ms",
                0,
            ),
            "min_integration_time_ms": old_config.get("timing_parameters", {}).get(
                "min_integration_time_ms",
                50,
            ),
            "led_rise_fall_time_ms": old_config.get("timing_parameters", {}).get(
                "led_rise_fall_time_ms",
                5,
            ),
        },
        "frequency_limits": {
            "4_led_max_hz": old_config.get("frequency_limits", {}).get(
                "4_led_max_hz",
                5.0,
            ),
            "4_led_recommended_hz": old_config.get("frequency_limits", {}).get(
                "4_led_recommended_hz",
                2.0,
            ),
            "2_led_max_hz": old_config.get("frequency_limits", {}).get(
                "2_led_max_hz",
                10.0,
            ),
            "2_led_recommended_hz": old_config.get("frequency_limits", {}).get(
                "2_led_recommended_hz",
                5.0,
            ),
        },
        "calibration_status": {
            "dark_calibration_date": old_config.get("calibration", {}).get(
                "dark_calibration_date",
            ),
            "s_mode_calibration_date": old_config.get("calibration", {}).get(
                "s_mode_calibration_date",
            ),
            "p_mode_calibration_date": old_config.get("calibration", {}).get(
                "p_mode_calibration_date",
            ),
            "factory_calibrated": old_config.get("calibration", {}).get(
                "factory_calibrated",
                False,
            ),
            "user_calibrated": old_config.get("calibration", {}).get(
                "user_calibrated",
                False,
            ),
            "preferred_calibration_mode": old_config.get("calibration", {}).get(
                "preferred_calibration_mode",
                "global",
            ),
        },
        "led_calibration": {
            "calibration_date": old_config.get("led_calibration", {}).get(
                "calibration_date",
            ),
            "calibration_mode": old_config.get("calibration", {}).get(
                "preferred_calibration_mode",
                "global",
            ),
            "global_integration_time_ms": old_config.get("led_calibration", {}).get(
                "integration_time_ms",
            ),
            "s_mode_led_intensities": old_config.get("led_calibration", {}).get(
                "s_mode_intensities",
                {},
            ),
            "p_mode_led_intensities": old_config.get("led_calibration", {}).get(
                "p_mode_intensities",
                {},
            ),
        },
        "baseline_data": {
            "s_ref_mean": extract_baseline_means(
                old_config.get("led_calibration", {}).get("s_ref_baseline", {}),
            ),
            "p_ref_mean": extract_baseline_means(
                old_config.get("led_calibration", {}).get("p_ref_baseline", {}),
            ),
            "note": "Full baseline spectra stored in calibration_data/ directory",
        },
        "oem_calibration": {
            "polarizer_s_position": old_config.get("oem_calibration", {}).get(
                "polarizer_s_position",
            ),
            "polarizer_p_position": old_config.get("oem_calibration", {}).get(
                "polarizer_p_position",
            ),
            "polarizer_sp_ratio": old_config.get("oem_calibration", {}).get(
                "polarizer_sp_ratio",
            ),
            "calibration_date": old_config.get("oem_calibration", {}).get(
                "calibration_date",
            ),
            "calibration_method": old_config.get("oem_calibration", {}).get(
                "calibration_method",
            ),
        },
        "baseline_positions": {
            "oem_polarizer_s_position": old_config.get("baseline", {}).get(
                "oem_polarizer_s_position",
            ),
            "oem_polarizer_p_position": old_config.get("baseline", {}).get(
                "oem_polarizer_p_position",
            ),
        },
        "optical_calibration": {
            "optical_calibration_file": old_config.get("optical_calibration", {}).get(
                "optical_calibration_file",
            ),
            "afterglow_correction_enabled": old_config.get(
                "optical_calibration",
                {},
            ).get("afterglow_correction_enabled", True),
            "led_delay_ms": old_config.get("optical_calibration", {}).get(
                "led_delay_ms",
                30.0,
            ),
        },
        "maintenance": {
            "last_maintenance_date": old_config.get("maintenance", {}).get(
                "last_maintenance_date",
            ),
            "total_measurement_cycles": old_config.get("maintenance", {}).get(
                "total_measurement_cycles",
                0,
            ),
            "led_on_hours": old_config.get("maintenance", {}).get("led_on_hours", 0.0),
            "next_maintenance_due": old_config.get("maintenance", {}).get(
                "next_maintenance_due",
            ),
            "led_health_check_last_hours": old_config.get("maintenance", {}).get(
                "led_health_check_last_hours",
                0.0,
            ),
            "led_health_check_last_date": old_config.get("maintenance", {}).get(
                "led_health_check_last_date",
            ),
            "led_health_check_interval_hours": old_config.get("maintenance", {}).get(
                "led_health_check_interval_hours",
                100.0,
            ),
            "led_health_status": old_config.get("maintenance", {}).get(
                "led_health_status",
                {
                    "A": "GOOD",
                    "B": "GOOD",
                    "C": "GOOD",
                    "D": "GOOD",
                },
            ),
        },
        "diagnostics": {
            "led_ranking": old_config.get("diagnostics", {}).get("led_ranking", {}),
            "note": "Diagnostic data from most recent calibration",
        },
    }

    print("✨ Writing reorganized config...")
    with open(config_path, "w") as f:
        json.dump(new_config, f, indent=2)

    # Print summary
    print("\n✅ Device config reorganized successfully!")
    print("\n📊 Structure Summary:")
    print("  • device_info: Device metadata")
    print("  • hardware: Physical components")
    print("  • timing_parameters: LED timing")
    print("  • frequency_limits: Acquisition rates")
    print("  • calibration_status: Calibration dates/flags")
    print("  • led_calibration: LED intensities & integration times")
    print("  • baseline_data: Mean baseline values (full spectra in calibration_data/)")
    print("  • oem_calibration: Polarizer positions")
    print("  • baseline_positions: Legacy baseline positions")
    print("  • optical_calibration: Afterglow correction")
    print("  • maintenance: Device health tracking")
    print("  • diagnostics: Recent calibration diagnostics")

    print(f"\n💾 Backup saved to: {backup_path.name}")
    print(f"📄 Original size: {backup_path.stat().st_size:,} bytes")
    print(f"📄 New size: {config_path.stat().st_size:,} bytes")


def extract_baseline_means(baseline_dict):
    """Extract mean values from baseline spectra (instead of storing full arrays)"""
    if not baseline_dict:
        return {}

    means = {}
    for channel, data in baseline_dict.items():
        if isinstance(data, list) and len(data) > 0:
            import numpy as np

            means[channel] = float(np.mean(data))
        else:
            means[channel] = None

    return means


if __name__ == "__main__":
    reorganize_device_config()
