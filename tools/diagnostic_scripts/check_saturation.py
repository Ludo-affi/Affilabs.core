"""Quick diagnostic to check signal levels and detect saturation.

This script helps diagnose saturation issues by testing each channel
at different LED intensities and integration times.
"""

import time

import numpy as np

from utils.controller import PicoP4SPR
from utils.logger import logger
from utils.usb4000_oceandirect import USB4000OceanDirect


def check_signal_levels():
    """Check signal levels at different LED intensities."""
    logger.info("=" * 80)
    logger.info("SATURATION DIAGNOSTIC")
    logger.info("=" * 80)

    # Initialize hardware manually
    logger.info("Connecting to hardware...")

    # Connect to controller
    ctrl = PicoP4SPR()
    if not ctrl.open():
        logger.error("Failed to open PicoP4SPR controller")
        return

    logger.info("✅ Controller connected")

    # Connect to spectrometer
    usb = USB4000OceanDirect()
    if not usb.connect():
        logger.error("Failed to connect to USB4000 spectrometer")
        return

    logger.info("✅ Spectrometer connected")

    try:
        _run_diagnostic(ctrl, usb)
    finally:
        # Cleanup
        logger.info("\nCleaning up hardware...")
        ctrl.turn_off_channels()
        usb.disconnect()
        logger.info("✅ Hardware disconnected")


def _run_diagnostic(ctrl, usb):
    """Run the actual diagnostic with connected hardware."""
    # Get detector max
    detector_max = 65535  # Standard for most detectors

    # Test integration times (ms)
    test_integration_times = [10, 20, 32, 50]

    # Test LED intensities
    test_led_intensities = [32, 64, 128, 192, 255]

    channels = ["a", "b", "c", "d"]

    logger.info("\nTesting signal levels...")
    logger.info(f"Detector max: {detector_max} counts")
    logger.info(f"Saturation threshold: {int(0.95 * detector_max)} counts (95%)")
    logger.info("")

    # Set S-mode for testing
    ctrl.set_mode("s")

    # Test each integration time
    for integration_ms in test_integration_times:
        integration_s = integration_ms / 1000.0
        usb.set_integration_time(integration_s)

        logger.info(f"\n{'='*80}")
        logger.info(f"Integration Time: {integration_ms}ms")
        logger.info(f"{'='*80}")

        # Test each channel at each LED intensity
        for ch in channels:
            logger.info(f"\nChannel {ch.upper()}:")
            logger.info(
                f"  {'LED':<5} {'Max Signal':<12} {'Mean Signal':<12} {'Status':<20}",
            )
            logger.info(f"  {'-'*60}")

            for led in test_led_intensities:
                # Set LED intensity (automatically turns on)
                ctrl.set_intensity(ch, led)
                time.sleep(0.1)  # Brief settle time

                # Read spectrum
                spectrum = usb.acquire_spectrum()

                if spectrum is None:
                    logger.warning(
                        f"  {led:<5} {'ERROR':<12} {'ERROR':<12} {'Failed to read':<20}",
                    )
                    continue

                # Calculate stats
                max_signal = float(np.max(spectrum))
                mean_signal = float(np.mean(spectrum))
                percent = (max_signal / detector_max) * 100

                # Determine status
                if max_signal >= 0.95 * detector_max:
                    status = "❌ SATURATED"
                elif max_signal >= 0.85 * detector_max:
                    status = "⚠️  Near saturation"
                elif max_signal >= 0.50 * detector_max:
                    status = "✅ Good signal"
                else:
                    status = "⚙️  Low signal"

                logger.info(
                    f"  {led:<5} {max_signal:>8.0f} ({percent:>4.1f}%)  {mean_signal:>8.0f}  {status:<20}",
                )

            # Turn off channel after all intensities tested
            ctrl.turn_off_channels()

    logger.info("\n" + "=" * 80)
    logger.info("RECOMMENDATIONS:")
    logger.info("=" * 80)

    # Find lowest integration time that doesn't saturate at low LED
    logger.info("\n1. If saturated at 10ms, 32 LED:")
    logger.info("   → Your optical system is VERY efficient")
    logger.info("   → Use shorter integration time (5-8ms)")
    logger.info("")
    logger.info("2. If saturated at 20ms, 64 LED:")
    logger.info("   → Good optical efficiency")
    logger.info("   → Use 10-15ms integration time")
    logger.info("")
    logger.info("3. If saturated at 32ms, 128 LED:")
    logger.info("   → Normal optical efficiency")
    logger.info("   → Current settings should work")
    logger.info("")
    logger.info("4. If NOT saturating anywhere:")
    logger.info("   → Weak optical coupling")
    logger.info("   → Check fiber alignment and connections")
    logger.info("")

    logger.info("\n✅ Diagnostic complete!")


if __name__ == "__main__":
    try:
        check_signal_levels()
    except KeyboardInterrupt:
        logger.info("\n\n🛑 Diagnostic interrupted by user")
    except Exception as e:
        logger.exception(f"Error during diagnostic: {e}")
