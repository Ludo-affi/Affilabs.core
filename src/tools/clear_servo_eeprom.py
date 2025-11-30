from utils.controller import ArduinoController
from utils.logger import logger


def main():
    ctrl = ArduinoController()
    if not ctrl.open():
        logger.error("Controller not found or failed to open.")
        return 1
    try:
        ok = ctrl.clear_servo_positions_in_eeprom()
        if ok:
            logger.info("✓ Cleared servo positions in EEPROM (set to 0/0)")
            return 0
        else:
            logger.error("Failed to clear servo positions in EEPROM.")
            return 2
    finally:
        ctrl.close()


if __name__ == "__main__":
    import sys
    sys.exit(main())
