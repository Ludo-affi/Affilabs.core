"""Write servo positions and related settings to controller EEPROM from device_config.json.

- Loads `affilabs/config/device_config.json` (or device-specific path if configured)
- Writes S/P servo positions, LED intensities, integration time, and metadata
- Reads back EEPROM to confirm
"""

from affilabs.utils.controller import PicoP4SPR
from affilabs.utils.device_configuration import DeviceConfiguration
from affilabs.utils.logger import logger


def build_eeprom_config(dc: DeviceConfiguration) -> dict:
    cfg = dc.config
    hw = cfg.get("hardware", {})
    cal = cfg.get("calibration", {})

    # Map JSON fields to controller EEPROM schema (flat keys)
    # Coerce and default values to valid integers
    integ = cal.get("integration_time_ms")
    if integ is None:
        integ = 100
    else:
        try:
            integ = int(integ)
        except Exception:
            integ = 100

    scans = cal.get("num_scans")
    if scans is None:
        scans = 3
    else:
        try:
            scans = int(scans)
        except Exception:
            scans = 3

    s_pos = hw.get("servo_s_position")
    p_pos = hw.get("servo_p_position")
    try:
        s_pos = int(s_pos) if s_pos is not None else None
        p_pos = int(p_pos) if p_pos is not None else None
    except Exception:
        # Leave as None to trigger validation failure later
        pass

    eeprom_cfg = {
        "led_pcb_model": hw.get("led_pcb_model", "luminus_cool_white"),
        "controller_type": "pico_p4spr",
        "fiber_diameter_um": hw.get("optical_fiber_diameter_um", 200),
        "polarizer_type": hw.get("polarizer_type", "round"),
        "servo_s_position": s_pos,
        "servo_p_position": p_pos,
        "led_intensity_a": cal.get("led_intensity_a", 0),
        "led_intensity_b": cal.get("led_intensity_b", 0),
        "led_intensity_c": cal.get("led_intensity_c", 0),
        "led_intensity_d": cal.get("led_intensity_d", 0),
        "integration_time_ms": integ,
        "num_scans": scans,
    }
    return eeprom_cfg


def main():
    ctrl = PicoP4SPR()
    if not ctrl.open():
        logger.error("Failed to open PicoP4SPR controller")
        return

    # Load device config (default path)
    dc = DeviceConfiguration(silent_load=True)

    eeprom_cfg = build_eeprom_config(dc)

    # Validate mandatory fields
    s_pos = eeprom_cfg.get("servo_s_position")
    p_pos = eeprom_cfg.get("servo_p_position")
    if s_pos is None or p_pos is None:
        logger.error("❌ Servo positions missing in device_config.json (hardware.servo_s/p_position)")
        logger.info("   Update device_config.json with calibrated S/P positions, then re-run.")
        return

    logger.info("\nWriting to controller EEPROM:")
    logger.info(f"  Servo S: {s_pos}°, Servo P: {p_pos}°")
    logger.info(
        "  LED intensities A,B,C,D: %s, %s, %s, %s"
        % (
            eeprom_cfg.get("led_intensity_a"),
            eeprom_cfg.get("led_intensity_b"),
            eeprom_cfg.get("led_intensity_c"),
            eeprom_cfg.get("led_intensity_d"),
        )
    )
    logger.info(f"  Integration time: {eeprom_cfg.get('integration_time_ms')} ms")
    logger.info(f"  Num scans: {eeprom_cfg.get('num_scans')}")

    ok = ctrl.write_config_to_eeprom(eeprom_cfg)
    if not ok:
        logger.warning("⚠️ EEPROM write did not confirm (firmware may not ACK); attempting readback anyway...")

    # Read back
    readback = ctrl.read_config_from_eeprom()
    if not readback:
        logger.error("❌ EEPROM readback failed. If using V2.4, write may still have applied.")
    else:
        logger.info("\n✅ EEPROM readback:")
        logger.info(f"  Servo S: {readback.get('servo_s_position')}°")
        logger.info(f"  Servo P: {readback.get('servo_p_position')}°")
        logger.info(
            "  LED intensities A,B,C,D: %s, %s, %s, %s"
            % (
                readback.get("led_intensity_a"),
                readback.get("led_intensity_b"),
                readback.get("led_intensity_c"),
                readback.get("led_intensity_d"),
            )
        )
        logger.info(f"  Integration time: {readback.get('integration_time_ms')} ms")
        logger.info(f"  Num scans: {readback.get('num_scans')}")

    ctrl.close()
    logger.info("\nController disconnected")


if __name__ == "__main__":
    main()
