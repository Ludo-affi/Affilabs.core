import argparse
import sys
from pathlib import Path

# Ensure we can import from project src/ when running as a script
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.common import update_config_file, get_config
from settings import CONFIG_FILE
from utils.logger import logger


def main():
    parser = argparse.ArgumentParser(description="Update servo S/P positions in device_config (generated-files/config.json)")
    parser.add_argument("--s", dest="s_pos", type=int, required=True, help="S-mode servo position (e.g., 133)")
    parser.add_argument("--p", dest="p_pos", type=int, required=True, help="P-mode servo position (e.g., 43)")
    args = parser.parse_args()

    s = int(args.s_pos)
    p = int(args.p_pos)
    if not (0 <= s <= 255 and 0 <= p <= 255):
        raise SystemExit("Positions must be in range 0-255")

    # Compose update dict at correct path
    update = {"hardware": {"servo_s_position": s, "servo_p_position": p}}

    before = get_config() or {}
    logger.info(f"Config path: {CONFIG_FILE}")
    logger.info(f"Current config keys: {list(before.keys())}")
    logger.info(f"Current hardware: {before.get('hardware', {})}")
    logger.info("Writing servo positions to hardware section...")

    update_config_file(update)

    after = get_config() or {}
    hw = after.get("hardware", {})
    s_written = hw.get("servo_s_position")
    p_written = hw.get("servo_p_position")
    if s_written == s and p_written == p:
        logger.info(f"✅ Updated: S={s_written}°, P={p_written}°")
    else:
        logger.warning(f"⚠️ Verify update: S={s_written}°, P={p_written}° (expected S={s}°, P={p}°)")


if __name__ == "__main__":
    main()
