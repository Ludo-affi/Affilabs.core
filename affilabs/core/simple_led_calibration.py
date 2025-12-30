"""Simple LED Calibration - Light touch intensity adjustment.

This is a lightweight calibration designed for scenarios where:
- You already have good LED values from previous calibration
- LED intensities may have drifted slightly or sensor swapped
- Just need to bring intensities back to target range (no saturation)
- Already CLOSE to target, so very quick (~5-10 seconds)

WORKFLOW (LIGHT TOUCH):
1. Turn on LEDs with current saved values
2. Measure spectrum to check current intensity
3. If too bright (>60k counts): scale down LEDs proportionally
4. If too dim (<40k counts): scale up LEDs proportionally
5. Verify with one more measurement
6. Update device config with adjusted LED intensities

This is NOT a full convergence - just a quick proportional adjustment to bring
intensities back into safe operating range (40k-55k counts).

REQUIREMENTS:
- Hardware connected (ctrl + usb)
- LED intensities already configured (from previous calibration)
- Prism installed with water/buffer
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Callable

import numpy as np

from affilabs.utils.logger import logger

if TYPE_CHECKING:
    from affilabs.core.hardware_manager import HardwareManager


def run_simple_led_calibration(
    hardware_mgr: HardwareManager,
    progress_callback: Callable[[str, int], None] | None = None,
) -> bool:
    """Run simple LED intensity adjustment (light touch).

    This function performs a quick proportional adjustment to bring LED intensities
    back into target range (40k-55k counts). It does NOT run full convergence -
    just measures current intensity and scales LEDs proportionally if needed.

    Args:
        hardware_mgr: Hardware manager with ctrl and usb
        progress_callback: Optional callback(message: str, percent: int)

    Returns:
        True if successful, False otherwise

    """
    try:
        ctrl = hardware_mgr.ctrl
        usb = hardware_mgr.usb

        if not ctrl or not usb:
            logger.error("Hardware not connected")
            return False

        # Get detector serial and device type
        detector_serial = getattr(usb, "serial_number", "UNKNOWN")
        device_type = (
            ctrl.get_device_type() if hasattr(ctrl, "get_device_type") else type(ctrl).__name__
        )

        logger.info("=" * 80)
        logger.info("🔧 SIMPLE LED CALIBRATION - Light Touch Adjustment")
        logger.info("=" * 80)
        logger.info(f"Device: {device_type}")
        logger.info(f"Detector: {detector_serial}")
        logger.info("Target range: 40k-55k counts (75% of max)")
        logger.info("=" * 80 + "\n")

        if progress_callback:
            progress_callback("Reading current LED settings...", 5)

        # ====================================================================
        # STEP 1: Load current LED settings from device config
        # ====================================================================
        logger.info("STEP 1: Loading current LED settings...")
        logger.info("-" * 80)

        # Load device config (keep in outer scope for use in later steps)
        device_config = hardware_mgr.get_device_config()
        if not device_config:
            logger.error("No device configuration found")
            return False

        try:
            # Get current LED intensities
            current_leds_s = {
                "a": device_config.led_a_s,
                "b": device_config.led_b_s,
                "c": device_config.led_c_s,
                "d": device_config.led_d_s,
            }

            current_leds_p = {
                "a": device_config.led_a_p,
                "b": device_config.led_b_p,
                "c": device_config.led_c_p,
                "d": device_config.led_d_p,
            }

            current_integration_s = device_config.integration_time_s
            current_integration_p = device_config.integration_time_p

            logger.info(f"[OK] Current S-mode LEDs: {current_leds_s}")
            logger.info(f"     Current P-mode LEDs: {current_leds_p}")
            logger.info(
                f"     Integration times: S={current_integration_s:.2f}ms, P={current_integration_p:.2f}ms"
            )

        except Exception as e:
            logger.error(f"Failed to load device config: {e}")
            return False

        if progress_callback:
            progress_callback("Measuring S-mode intensity...", 15)

        # Initialize adjusted LED values (in case of early failure)
        adjusted_leds_s = current_leds_s.copy()
        adjusted_leds_p = current_leds_p.copy()

        # ====================================================================
        # STEP 2: S-mode measurement and adjustment
        # ====================================================================
        logger.info("\nSTEP 2: S-mode measurement and light touch adjustment...")
        logger.info("-" * 80)

        try:
            # Move servo to S position (if device has servo)
            if hasattr(ctrl, "servo_set"):
                s_pos = (
                    device_config.s_servo_position
                    if hasattr(device_config, "s_servo_position")
                    else 90
                )
                logger.info(f"Moving servo to S position: {s_pos}")
                ctrl.servo_set(s=s_pos, p=s_pos)
                time.sleep(0.3)

            # Set integration time and turn on LEDs with current values
            usb.set_integration(current_integration_s)
            time.sleep(0.05)

            for ch, intensity in current_leds_s.items():
                ctrl.set_intensity(ch, intensity)
            time.sleep(0.1)  # Let LEDs stabilize

            # Measure spectrum
            spectrum = usb.read_intensity()
            max_intensity = float(spectrum.max())

            logger.info(f"[MEASURED] S-mode max intensity: {max_intensity:.0f} counts")

            # Target range: 40k-55k counts (safe operating range, no saturation)
            target_min = 40000
            target_max = 55000
            target_center = 49152  # 75% of 65535

            # Determine if adjustment needed
            if max_intensity < target_min:
                # Too dim - scale up
                scale_factor = target_center / max_intensity
                action = "SCALE UP"
            elif max_intensity > target_max:
                # Too bright - scale down
                scale_factor = target_center / max_intensity
                action = "SCALE DOWN"
            else:
                # In range - no adjustment needed
                scale_factor = 1.0
                action = "NO CHANGE"

            logger.info(f"[ACTION] {action} (scale factor: {scale_factor:.3f})")

            # Apply proportional adjustment
            adjusted_leds_s = {}
            for ch, current_val in current_leds_s.items():
                new_val = int(current_val * scale_factor)
                adjusted_leds_s[ch] = int(np.clip(new_val, 10, 255))

            logger.info(f"[OK] Adjusted S-mode LEDs: {adjusted_leds_s}")

            # Verify adjustment (optional quick check)
            if scale_factor != 1.0:
                for ch, intensity in adjusted_leds_s.items():
                    ctrl.set_intensity(ch, intensity)
                time.sleep(0.1)

                verify_spectrum = usb.read_intensity()
                verify_max = float(verify_spectrum.max())
                logger.info(f"[VERIFY] New S-mode intensity: {verify_max:.0f} counts ✓")

        except Exception as e:
            logger.error(f"S-mode adjustment failed: {e}")
            return False

        if progress_callback:
            progress_callback("Measuring P-mode intensity...", 50)

        # ====================================================================
        # STEP 3: P-mode measurement and adjustment
        # ====================================================================
        logger.info("\nSTEP 3: P-mode measurement and light touch adjustment...")
        logger.info("-" * 80)

        try:
            # Move servo to P position (if device has servo)
            if hasattr(ctrl, "servo_set"):
                p_pos = (
                    device_config.p_servo_position
                    if hasattr(device_config, "p_servo_position")
                    else 0
                )
                logger.info(f"Moving servo to P position: {p_pos}")
                ctrl.servo_set(s=p_pos, p=p_pos)
                time.sleep(0.3)

            # Set integration time and turn on LEDs with current P-mode values
            usb.set_integration(current_integration_p)
            time.sleep(0.05)

            for ch, intensity in current_leds_p.items():
                ctrl.set_intensity(ch, intensity)
            time.sleep(0.1)  # Let LEDs stabilize

            # Measure spectrum
            spectrum = usb.read_intensity()
            max_intensity = float(spectrum.max())

            logger.info(f"[MEASURED] P-mode max intensity: {max_intensity:.0f} counts")

            # Target range: 40k-55k counts (safe operating range, no saturation)
            target_min = 40000
            target_max = 55000
            target_center = 49152  # 75% of 65535

            # Determine if adjustment needed
            if max_intensity < target_min:
                # Too dim - scale up
                scale_factor = target_center / max_intensity
                action = "SCALE UP"
            elif max_intensity > target_max:
                # Too bright - scale down
                scale_factor = target_center / max_intensity
                action = "SCALE DOWN"
            else:
                # In range - no adjustment needed
                scale_factor = 1.0
                action = "NO CHANGE"

            logger.info(f"[ACTION] {action} (scale factor: {scale_factor:.3f})")

            # Apply proportional adjustment
            adjusted_leds_p = {}
            for ch, current_val in current_leds_p.items():
                new_val = int(current_val * scale_factor)
                adjusted_leds_p[ch] = int(np.clip(new_val, 10, 255))

            logger.info(f"[OK] Adjusted P-mode LEDs: {adjusted_leds_p}")

            # Verify adjustment (optional quick check)
            if scale_factor != 1.0:
                for ch, intensity in adjusted_leds_p.items():
                    ctrl.set_intensity(ch, intensity)
                time.sleep(0.1)

                verify_spectrum = usb.read_intensity()
                verify_max = float(verify_spectrum.max())
                logger.info(f"[VERIFY] New P-mode intensity: {verify_max:.0f} counts ✓")

        except Exception as e:
            logger.error(f"P-mode adjustment failed: {e}")
            # P-mode failure is acceptable - use S-mode values
            adjusted_leds_p = adjusted_leds_s
            logger.warning("Using S-mode values for P-mode")

        if progress_callback:
            progress_callback("Saving adjusted LED values...", 90)

        # ====================================================================
        # STEP 4: Save adjusted LED values to device config
        # ====================================================================
        logger.info("\nSTEP 4: Saving adjusted LED configuration...")
        logger.info("-" * 80)

        try:
            device_config = hardware_mgr.get_device_config()
            if device_config:
                # Update LED intensities (keep integration times unchanged)
                device_config.led_a_s = adjusted_leds_s.get("a", 128)
                device_config.led_b_s = adjusted_leds_s.get("b", 128)
                device_config.led_c_s = adjusted_leds_s.get("c", 128)
                device_config.led_d_s = adjusted_leds_s.get("d", 128)

                device_config.led_a_p = adjusted_leds_p.get("a", 128)
                device_config.led_b_p = adjusted_leds_p.get("b", 128)
                device_config.led_c_p = adjusted_leds_p.get("c", 128)
                device_config.led_d_p = adjusted_leds_p.get("d", 128)

                # Save config
                device_config.save()
                logger.info("[OK] Device config updated and saved")
                logger.info(f"     S-mode LEDs: {adjusted_leds_s}")
                logger.info(f"     P-mode LEDs: {adjusted_leds_p}")

        except Exception as e:
            logger.error(f"Failed to update device config: {e}")
            # Non-fatal - calibration still succeeded

        # Turn off LEDs
        try:
            ctrl.turn_off_channels()
        except Exception:
            pass

        if progress_callback:
            progress_callback("✅ Simple calibration complete!", 100)

        logger.info("\n" + "=" * 80)
        logger.info("✅ SIMPLE LED CALIBRATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"S-mode LEDs: {adjusted_leds_s}")
        logger.info(f"P-mode LEDs: {adjusted_leds_p}")
        logger.info("Adjusted LED intensities saved to device config.")
        logger.info("=" * 80 + "\n")

        return True

    except Exception as e:
        logger.error(f"Simple LED calibration failed: {e}")
        import traceback

        traceback.print_exc()
        return False
