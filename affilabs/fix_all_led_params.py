"""Fix ALL LED calibration function signatures to add delay parameters."""

import re

def fix_all_signatures():
    filepath = 'utils/led_calibration.py'

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix measure_dark_noise
    old_dark = r'''def measure_dark_noise\(
    usb,
    ctrl: ControllerBase,
    integration: int,
    wave_min_index: int,
    wave_max_index: int,
    stop_flag=None,
    num_scans: int = None,  # Optional: pre-calculated scan count
\) -> np\.ndarray:'''

    new_dark = '''def measure_dark_noise(
    usb,
    ctrl: ControllerBase,
    integration: int,
    wave_min_index: int,
    wave_max_index: int,
    stop_flag=None,
    num_scans: int = None,  # Optional: pre-calculated scan count
    pre_led_delay_ms: float = 45.0,
    post_led_delay_ms: float = 5.0,
) -> np.ndarray:'''

    content = re.sub(old_dark, new_dark, content)
    print("[OK] Fixed measure_dark_noise signature")

    # Fix measure_reference_signals
    old_ref = r'''def measure_reference_signals\(
    usb,
    ctrl: ControllerBase,
    ch_list: list\[str\],
    ref_intensity: dict\[str, int\],
    dark_noise: np\.ndarray,
    integration: int,
    wave_min_index: int,
    wave_max_index: int,
    stop_flag=None,
    afterglow_correction=None,
    num_scans: int = None,  # Optional: pre-calculated scan count
\) -> dict\[str, np\.ndarray\]:'''

    new_ref = '''def measure_reference_signals(
    usb,
    ctrl: ControllerBase,
    ch_list: list[str],
    ref_intensity: dict[str, int],
    dark_noise: np.ndarray,
    integration: int,
    wave_min_index: int,
    wave_max_index: int,
    stop_flag=None,
    afterglow_correction=None,
    num_scans: int = None,  # Optional: pre-calculated scan count
    pre_led_delay_ms: float = 45.0,
    post_led_delay_ms: float = 5.0,
) -> dict[str, np.ndarray]:'''

    content = re.sub(old_ref, new_ref, content)
    print("[OK] Fixed measure_reference_signals signature")

    # Write back
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print("\n[OK] All missing LED calibration signatures fixed!")

if __name__ == '__main__':
    fix_all_signatures()
