"""Run afterglow calibration to regenerate optical_calibration.json with all 4 channels.

This script properly initializes hardware and runs the optical calibration procedure.
The afterglow correction requires ALL 4 channels due to cross-channel correction:
- Channel A corrected by D afterglow
- Channel B corrected by A afterglow
- Channel C corrected by B afterglow
- Channel D corrected by C afterglow

Usage:
    cd "Affilabs.core beta"
    python run_afterglow_calibration.py

Duration: ~5-10 minutes
"""

import sys
import time
from pathlib import Path

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent  # Go up to ezControl-AI root
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Now add Affilabs.core beta to path
core_beta_dir = Path(__file__).parent
if str(core_beta_dir) not in sys.path:
    sys.path.insert(0, str(core_beta_dir))

from affilabs.utils.device_manager import get_device_manager
from affilabs.utils.logger import logger
from affilabs.utils.spr_calibrator import SPRCalibrator


def main():
    """Run afterglow calibration programmatically."""
    logger.info("=" * 80)
    logger.info("AFTERGLOW CALIBRATION - REGENERATE ALL 4 CHANNELS")
    logger.info("=" * 80)

    # Get device manager
    device_manager = get_device_manager()

    # Check if device is configured, if not try to auto-detect from spectrometer
    if device_manager.current_device_serial is None:
        logger.warning("[WARN]  No device configured in device_manager")
        logger.info("Will attempt to detect device serial from spectrometer...")

        # Try to detect device first
        from core.hardware_manager import HardwareManager

        temp_hw = HardwareManager()
        temp_hw._connect_spectrometer()

        if temp_hw.usb and hasattr(temp_hw.usb, "serial_number"):
            serial = temp_hw.usb.serial_number
            logger.info(f"[OK] Detected device serial from spectrometer: {serial}")

            # Set device in device manager
            try:
                device_manager.set_device(serial)
                logger.info(f"[OK] Device configured: {serial}")
            except Exception as e:
                logger.error(f"[ERROR] Failed to configure device: {e}")
                return 1
            finally:
                # Close temporary connection
                try:
                    temp_hw.usb.close()
                except:
                    pass
        else:
            logger.error("[ERROR] Could not detect device serial from spectrometer")
            logger.error("   Please ensure device is connected")
            return 1

    serial = device_manager.current_device_serial
    device_dir = device_manager.current_device_dir

    if device_dir is None:
        logger.error("[ERROR] Device directory not available")
        return 1

    logger.info(f"Device: {serial}")
    logger.info(f"Device directory: {device_dir}")

    # Check existing optical calibration
    optical_cal_file = device_dir / "optical_calibration.json"
    if optical_cal_file.exists():
        import json

        logger.warning("[WARN]  Existing optical calibration will be REPLACED:")
        logger.warning(f"   {optical_cal_file}")

        try:
            with open(optical_cal_file) as f:
                data = json.load(f)
                channels = list(data.get("channel_data", {}).keys())
                logger.warning(f"   Current channels: {channels}")

                if len(channels) == 4:
                    logger.info("   (File already has 4 channels, re-running anyway)")
                else:
                    logger.error(
                        f"   [ERROR] File missing channels! Has {len(channels)}/4: {channels}",
                    )
                    missing = [ch for ch in ["a", "b", "c", "d"] if ch not in channels]
                    logger.error(f"   Missing: {missing}")
        except Exception as e:
            logger.warning(f"   Could not parse existing file: {e}")
    else:
        logger.info("No existing optical calibration file")

    logger.info("")
    logger.info("=" * 80)
    logger.info("INITIALIZING HARDWARE")
    logger.info("=" * 80)

    # Initialize hardware manager
    hardware_mgr = HardwareManager()

    # Connect to hardware using internal method
    try:
        logger.info("Scanning for spectrometer...")
        hardware_mgr._connect_spectrometer()

        logger.info("Scanning for SPR controller...")
        hardware_mgr._connect_controller()

        # Get hardware instances
        ctrl = hardware_mgr.ctrl
        usb = hardware_mgr.usb

        if ctrl is None or usb is None:
            logger.error("[ERROR] Hardware not found")
            logger.error(f"   Controller: {ctrl}")
            logger.error(f"   Spectrometer: {usb}")
            logger.error("")
            logger.error("Make sure:")
            logger.error("  • Device is connected via USB")
            logger.error("  • No other application is using the device")
            logger.error("  • Drivers are properly installed")
            return 1

        logger.info(f"[OK] Controller: {type(ctrl).__name__}")
        logger.info(f"[OK] Spectrometer: {type(usb).__name__}")
        if hasattr(usb, "serial_number"):
            logger.info(f"   Serial: {usb.serial_number}")

        # Wait for hardware to stabilize
        logger.info("Waiting for hardware to stabilize...")
        time.sleep(1.0)

        logger.info("")
        logger.info("=" * 80)
        logger.info("INITIALIZING CALIBRATOR")
        logger.info("=" * 80)

        # Load LED intensities from device_config.json
        led_intensities = {"a": 255, "b": 255, "c": 255, "d": 255}
        device_config_dict = None

        try:
            import json

            config_file = device_dir / "device_config.json"
            if config_file.exists():
                with open(config_file) as f:
                    device_config_dict = json.load(f)
                    led_intensities = device_config_dict.get(
                        "led_intensities",
                        led_intensities,
                    )
                    logger.info("Loaded LED intensities from device_config.json:")
                    for ch in ["a", "b", "c", "d"]:
                        logger.info(
                            f"  Channel {ch}: {led_intensities.get(ch, 'NOT SET')}",
                        )
            else:
                logger.warning(
                    "No device_config.json found, using defaults (255 for all)",
                )
        except Exception as e:
            logger.warning(f"Could not load device_config.json: {e}")
            logger.warning("Using default intensities (255 for all channels)")

        # Determine device type from controller
        if hasattr(ctrl, "__class__"):
            ctrl_class_name = ctrl.__class__.__name__
            if "P4" in ctrl_class_name or "PicoP4" in ctrl_class_name:
                device_type = "PicoP4SPR"
            elif "EZ" in ctrl_class_name or "PicoEZ" in ctrl_class_name:
                device_type = "PicoEZSPR"
            else:
                device_type = "PicoP4SPR"  # Default
        else:
            device_type = "PicoP4SPR"

        logger.info(f"Device type: {device_type}")

        # Create calibrator
        calibrator = SPRCalibrator(
            ctrl=ctrl,
            usb=usb,
            device_type=device_type,
            stop_flag=None,
            calib_state=None,
            optical_fiber_diameter=100,  # Default
            led_pcb_model="4LED",  # Default
            device_config=device_config_dict,
        )

        logger.info("[OK] Calibrator initialized")

        logger.info("")
        logger.info("=" * 80)
        logger.info("RUNNING OPTICAL CALIBRATION")
        logger.info("=" * 80)
        logger.info("")
        logger.info("This will:")
        logger.info("  • Test all 4 channels: a, b, c, d")
        logger.info("  • Test 6 integration times: [10, 25, 40, 55, 70, 85] ms")
        logger.info("  • Measure LED afterglow decay for each combination")
        logger.info("  • Fit exponential decay models")
        logger.info("  • Save results to optical_calibration.json")
        logger.info("")
        logger.info("Duration: ~5-10 minutes")
        logger.info("")
        logger.info("Starting in 3 seconds...")
        time.sleep(3)

        # Run optical calibration
        logger.info("")
        logger.info("🔬 STARTING CALIBRATION...")
        logger.info("")

        success = calibrator._run_optical_calibration()

        if success:
            logger.info("")
            logger.info("=" * 80)
            logger.info("[OK] OPTICAL CALIBRATION COMPLETE")
            logger.info("=" * 80)

            # Verify channels
            import json

            try:
                with open(optical_cal_file) as f:
                    data = json.load(f)
                    channels = list(data["channel_data"].keys())

                logger.info(f"[OK] Calibration file saved: {optical_cal_file}")
                logger.info(f"[OK] Channels present: {channels}")

                if len(channels) == 4:
                    logger.info("[OK] SUCCESS: All 4 channels calibrated!")

                    # Show data point counts
                    logger.info("")
                    logger.info("Data points per channel:")
                    for ch in channels:
                        num_points = len(
                            data["channel_data"][ch]["integration_time_data"],
                        )
                        logger.info(f"  Channel {ch}: {num_points} integration times")

                    return 0
                missing = [ch for ch in ["a", "b", "c", "d"] if ch not in channels]
                logger.error(f"[ERROR] FAILURE: Missing channels: {missing}")
                logger.error(f"   Only calibrated: {channels}")
                logger.error("   Check logs above for errors during measurement")
                return 1

            except Exception as e:
                logger.error(f"[ERROR] Failed to verify calibration file: {e}")
                return 1
        else:
            logger.error("")
            logger.error("=" * 80)
            logger.error("[ERROR] OPTICAL CALIBRATION FAILED")
            logger.error("=" * 80)
            logger.error("")
            logger.error("Check logs above for specific errors")
            logger.error("")
            logger.error("Common issues:")
            logger.error("  • Hardware communication failure")
            logger.error("  • Channel LED not functional")
            logger.error("  • Timing/synchronization issues")
            logger.error("  • Insufficient signal levels")
            return 1

    except KeyboardInterrupt:
        logger.warning("")
        logger.warning("[ERROR] Calibration interrupted by user")
        return 1

    except Exception as e:
        logger.exception(f"[ERROR] Calibration failed with exception: {e}")
        return 1

    finally:
        # Cleanup hardware
        logger.info("")
        logger.info("Cleaning up hardware...")
        try:
            if hardware_mgr and hardware_mgr.ctrl:
                hardware_mgr.ctrl.all_off()
                try:
                    hardware_mgr.ctrl.disconnect()
                except:
                    pass
            if hardware_mgr and hardware_mgr.usb:
                try:
                    hardware_mgr.usb.close()
                except:
                    pass
            logger.info("[OK] Hardware disconnected")
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")


if __name__ == "__main__":
    sys.exit(main())
