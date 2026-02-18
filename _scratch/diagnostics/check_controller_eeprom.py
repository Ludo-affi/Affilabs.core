"""Read servo positions from controller EEPROM (PicoP4SPR)."""

from affilabs.utils.controller import PicoP4SPR
from affilabs.utils.logger import logger


def main():
    ctrl = PicoP4SPR()
    if not ctrl.open():
        logger.error("Failed to open PicoP4SPR controller")
        return

    try:
        logger.info("=" * 70)
        logger.info("Reading PicoP4SPR EEPROM configuration")
        logger.info("=" * 70)

        # Check if config is valid in EEPROM
        valid = ctrl.is_config_valid_in_eeprom()
        logger.info(f"EEPROM has valid config: {valid}")

        cfg = ctrl.read_config_from_eeprom()
        if not cfg:
            logger.error("EEPROM read failed or checksum mismatch")
            return

        s_pos = cfg.get("servo_s_position")
        p_pos = cfg.get("servo_p_position")
        led_a = cfg.get("led_intensity_a")
        led_b = cfg.get("led_intensity_b")
        led_c = cfg.get("led_intensity_c")
        led_d = cfg.get("led_intensity_d")
        integ = cfg.get("integration_time_ms")
        scans = cfg.get("num_scans")

        logger.info("\nController EEPROM Values:")
        logger.info(f"  Servo S position: {s_pos} degrees")
        logger.info(f"  Servo P position: {p_pos} degrees")
        logger.info(f"  LED intensities (A,B,C,D): {led_a}, {led_b}, {led_c}, {led_d}")
        logger.info(f"  Integration time: {integ} ms")
        logger.info(f"  Num scans: {scans}")

    finally:
        ctrl.close()
        logger.info("\nController disconnected")


if __name__ == "__main__":
    main()
