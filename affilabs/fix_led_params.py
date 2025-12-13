"""Fix LED calibration function signatures to add delay parameters."""

import re

def fix_led_calibration():
    filepath = 'utils/led_calibration.py'

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix calibrate_led_channel signature
    old_sig = r'''def calibrate_led_channel\(
    usb,
    ctrl: ControllerBase,
    ch: str,
    target_counts: float = None,
    stop_flag=None,
    detector_params: DetectorParams = None,  # Optional: pre-read detector parameters
    wave_min_index: int = None,  # ROI start for saturation checking
    wave_max_index: int = None,  # ROI end for saturation checking
\) -> int:'''

    new_sig = '''def calibrate_led_channel(
    usb,
    ctrl: ControllerBase,
    ch: str,
    target_counts: float = None,
    stop_flag=None,
    detector_params: DetectorParams = None,  # Optional: pre-read detector parameters
    wave_min_index: int = None,  # ROI start for saturation checking
    wave_max_index: int = None,  # ROI end for saturation checking
    pre_led_delay_ms: float = 45.0,  # PRE LED delay (default 45ms)
    post_led_delay_ms: float = 5.0,  # POST LED delay (default 5ms)
) -> int:'''

    content_new = re.sub(old_sig, new_sig, content)

    if content != content_new:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content_new)
        print("[OK] Fixed calibrate_led_channel signature")
    else:
        print("[WARN]  No changes made - signature already correct or pattern didn't match")

    # Now fix calibrate_p_mode_leds signature
    old_sig2 = r'''def calibrate_p_mode_leds\(
    usb,
    ctrl: ControllerBase,
    ch_list: list\[str\],
    ref_intensity: dict\[str, int\],
    stop_flag=None,
    detector_params: DetectorParams = None,  # Optional: pre-read detector parameters
    headroom_analysis: dict\[str, ChannelHeadroomAnalysis\] = None,  # Optional: pre-computed headroom analysis
\) -> tuple\[dict\[str, int\], dict\[str, dict\]\]:'''

    new_sig2 = '''def calibrate_p_mode_leds(
    usb,
    ctrl: ControllerBase,
    ch_list: list[str],
    ref_intensity: dict[str, int],
    stop_flag=None,
    detector_params: DetectorParams = None,  # Optional: pre-read detector parameters
    headroom_analysis: dict[str, ChannelHeadroomAnalysis] = None,  # Optional: pre-computed headroom analysis
    pre_led_delay_ms: float = 45.0,
    post_led_delay_ms: float = 5.0,
) -> tuple[dict[str, int], dict[str, dict]]:'''

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    content_new = re.sub(old_sig2, new_sig2, content)

    if content != content_new:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content_new)
        print("[OK] Fixed calibrate_p_mode_leds signature")
    else:
        print("[WARN]  calibrate_p_mode_leds signature not changed - check manually")

if __name__ == '__main__':
    fix_led_calibration()
    print("\n[OK] LED calibration signatures fixed!")
