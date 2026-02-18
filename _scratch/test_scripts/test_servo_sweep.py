"""Quick servo sweep test - find transparent windows in barrel polarizer.

This test:
1. Turns ON LEDs at fixed intensity
2. Sweeps servo across full range (5-175°)
3. Measures signal at each position
4. Reports positions with highest signal (= transparent windows)

Use this BEFORE polarizer calibration to verify servo movement and find transparent regions.
"""

import time
import logging
from affilabs.core.hardware_manager import HardwareManager

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def test_servo_sweep():
    """Sweep servo across full range while LEDs are ON to find transparent windows."""

    logger.info("="*80)
    logger.info("SERVO SWEEP TEST - Find Transparent Windows")
    logger.info("="*80)

    hm = HardwareManager()

    try:
        ctrl = hm.ctrl
        det = hm.usb

        # 1. Turn ON LEDs at 20% intensity
        logger.info("\n1. Turning ON LEDs at 20% (51/255)...")
        led_value = 51
        for ch in ['a', 'b', 'c', 'd']:
            try:
                result = ctrl.set_intensity(ch=ch, raw_val=led_value)
                logger.info(f"   Channel {ch}: {'OK' if result else 'FAILED'}")
                time.sleep(0.05)
            except Exception as e:
                logger.error(f"   Channel {ch}: FAILED - {e}")

        # Set integration time
        det.set_integration_time(200)
        time.sleep(0.2)

        # 2. Sweep servo from 5° to 175° in 10° steps
        logger.info("\n2. Sweeping servo from 5° to 175° (step 10°)...")
        logger.info(f"{'Angle':>6} | {'PWM':>3} | {'Signal':>8} | {'Transparent?':>15}")
        logger.info("-" * 50)

        results = []
        for angle in range(5, 180, 10):
            # Move servo
            pwm = int((angle - 5) * 255 / 170)  # Convert angle to PWM
            cmd = f"servo:{angle},500"
            ctrl.send_command(cmd)
            time.sleep(0.7)  # Wait for servo movement

            # Measure signal
            spectrum = det.get_detector_counts()
            signal = float(spectrum.mean())

            results.append((angle, pwm, signal))

            # Mark transparent if signal > 2x dark baseline (940 * 2 = 1880)
            is_transparent = signal > 1880
            marker = " *** TRANSPARENT ***" if is_transparent else ""

            logger.info(f"{angle:>6}deg | {pwm:>3} | {signal:>8.1f}{marker}")

        # 3. Report summary
        logger.info("\n" + "="*80)
        logger.info("SUMMARY")
        logger.info("="*80)

        # Find positions with signal > 2x baseline
        transparent = [(angle, pwm, signal) for angle, pwm, signal in results if signal > 1880]

        if transparent:
            logger.info(f"\nFound {len(transparent)} transparent positions:")
            for angle, pwm, signal in transparent:
                logger.info(f"   {angle:>3}deg (PWM {pwm:>3}): {signal:>8.1f} counts")

            # Find peaks (P and S positions)
            sorted_by_signal = sorted(transparent, key=lambda x: x[2], reverse=True)
            if len(sorted_by_signal) >= 2:
                p_angle, p_pwm, p_signal = sorted_by_signal[0]
                s_angle, s_pwm, s_signal = sorted_by_signal[1]

                logger.info("\nSuggested positions:")
                logger.info(f"   P position: {p_angle}deg (PWM {p_pwm}) - {p_signal:.1f} counts")
                logger.info(f"   S position: {s_angle}deg (PWM {s_pwm}) - {s_signal:.1f} counts")
        else:
            logger.error("\n*** NO TRANSPARENT POSITIONS FOUND ***")
            logger.error("All measurements at dark baseline (~940)")
            logger.error("\nPossible causes:")
            logger.error("  1. LEDs not actually turning ON (check wiring)")
            logger.error("  2. Detector not seeing light (check fiber optic connection)")
            logger.error("  3. Barrel polarizer completely opaque (check hardware)")

    except Exception as e:
        logger.error(f"\n*** ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Turn off LEDs
        try:
            logger.info("\nTurning OFF LEDs...")
            ctrl.turn_off_channels()
        except:
            pass

if __name__ == "__main__":
    test_servo_sweep()
