import inspect

from affilabs.utils.led_calibration import (
    calibrate_integration_time,
    calibrate_led_channel,
    calibrate_p_mode_leds,
    measure_dark_noise,
    measure_reference_signals,
)

funcs = {
    "calibrate_led_channel": calibrate_led_channel,
    "calibrate_p_mode_leds": calibrate_p_mode_leds,
    "calibrate_integration_time": calibrate_integration_time,
    "measure_dark_noise": measure_dark_noise,
    "measure_reference_signals": measure_reference_signals,
}

print("Checking all functions have delay parameters:")
for name, func in funcs.items():
    has_pre = "pre_led_delay_ms" in inspect.signature(func).parameters
    has_post = "post_led_delay_ms" in inspect.signature(func).parameters
    status = "[OK]" if (has_pre and has_post) else "[ERROR]"
    print(f"{status} {name}: pre={has_pre}, post={has_post}")
