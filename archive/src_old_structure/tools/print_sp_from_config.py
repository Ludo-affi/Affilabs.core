import json
from pathlib import Path
import argparse
from datetime import datetime

CONFIG_DEVICES_DIR = Path(__file__).resolve().parents[1] / 'config' / 'devices'

def find_latest_device_config() -> Path | None:
    if not CONFIG_DEVICES_DIR.exists():
        return None
    latest_path = None
    latest_mtime = -1.0
    for d in CONFIG_DEVICES_DIR.iterdir():
        if not d.is_dir():
            continue
        cfg = d / 'device_config.json'
        if cfg.exists():
            mtime = cfg.stat().st_mtime
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_path = cfg
    return latest_path


def get_device_config(serial: str | None) -> tuple[str, dict] | None:
    if serial:
        cfg = CONFIG_DEVICES_DIR / serial / 'device_config.json'
        if not cfg.exists():
            return None
        with open(cfg, 'r') as f:
            return serial, json.load(f)
    else:
        latest = find_latest_device_config()
        if not latest:
            return None
        with open(latest, 'r') as f:
            data = json.load(f)
        return latest.parent.name, data


def main():
    parser = argparse.ArgumentParser(description='Print S/P values from device_config.json')
    parser.add_argument('--serial', '-s', help='Device serial (e.g., FLMT09116)')
    args = parser.parse_args()

    result = get_device_config(args.serial)
    if not result:
        print('No device_config.json found. Expected under src/config/devices/<SERIAL>/')
        return

    serial, cfg = result
    hw = cfg.get('hardware', {})
    cal = cfg.get('calibration', {})
    led_cal = cfg.get('led_calibration', {})

    servo_s = hw.get('servo_s_position')
    servo_p = hw.get('servo_p_position')

    s_leds = led_cal.get('s_mode_intensities')
    p_leds = led_cal.get('p_mode_intensities')
    it_ms = led_cal.get('integration_time_ms')
    s_max = led_cal.get('s_ref_max_intensity')
    p_max = led_cal.get('p_ref_max_intensity')

    created = cfg.get('device_info', {}).get('created_date')
    modified = cfg.get('device_info', {}).get('last_modified')

    print('\n=== Device Config: {} ==='.format(serial))
    if created:
        print('Created:  {}'.format(created))
    if modified:
        print('Updated:  {}'.format(modified))

    print('\n[Servo Positions]')
    print('  S position: {}'.format(servo_s if servo_s is not None else 'N/A'))
    print('  P position: {}'.format(servo_p if servo_p is not None else 'N/A'))

    print('\n[LED Intensities] (from LED calibration)')
    if it_ms is not None:
        print('  Integration time (ms): {}'.format(it_ms))
    print('  S-mode LEDs: {}'.format(s_leds if s_leds else 'N/A'))
    print('  P-mode LEDs: {}'.format(p_leds if p_leds else 'N/A'))

    if s_max or p_max:
        print('\n[Reference Max Intensities]')
        if s_max:
            print('  S-ref max: {}'.format({k: round(v, 1) for k, v in s_max.items()}))
        if p_max:
            print('  P-ref max: {}'.format({k: round(v, 1) for k, v in p_max.items()}))

    print('\nDone.')


if __name__ == '__main__':
    main()
