"""Test script for live data acquisition loop in isolation.

Usage:
    python test_live_acquisition_loop.py

Tests:
- Loads latest calibration data
- Connects to hardware
- Runs acquisition loop for N cycles
- Logs timing and results
- Validates transmission calculations
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from affilabs.core.hardware_manager import HardwareManager
from affilabs.utils.logger import logger


def load_latest_calibration():
    """Load the most recent calibration data."""
    # Find qc_report_latest.json
    qc_file = Path("OpticalSystem_QC/FLMT09116/validation_reports/qc_report_latest.json")

    if not qc_file.exists():
        raise FileNotFoundError(f"No calibration found at {qc_file}")

    logger.info(f"Loading calibration from {qc_file}")
    with open(qc_file, 'r') as f:
        data = json.load(f)

    # Extract key parameters - they're in raw_calibration_data section
    raw_cal = data.get("raw_calibration_data", {})

    cal_data = {
        "p_integration_time": raw_cal.get("integration_time_p"),
        "s_integration_time": raw_cal.get("integration_time_s"),
        "p_mode_intensities": raw_cal.get("p_mode_intensities", raw_cal.get("led_intensities", {})),
        "s_mode_intensities": raw_cal.get("s_mode_intensities", {}),
        "num_scans": raw_cal.get("num_scans", 3),
        "wavelengths": raw_cal.get("wavelengths"),
        "s_pol_ref": raw_cal.get("s_raw_roi", raw_cal.get("s_pol_ref", {})),
        "dark_p": raw_cal.get("dark_p", {}),
        "dark_noise": raw_cal.get("dark_noise"),
        "channel_integration_times": raw_cal.get("channel_integration_times", {}),
    }

    logger.info("Calibration loaded:")

    p_int = cal_data.get('p_integration_time')
    s_int = cal_data.get('s_integration_time')

    if p_int is None:
        raise ValueError("P-pol integration time not found in calibration")

    logger.info(f"  P-pol integration: {p_int:.1f}ms")
    logger.info(f"  S-pol integration: {s_int:.1f}ms" if s_int else "  S-pol integration: N/A")
    logger.info(f"  Num scans: {cal_data['num_scans']}")
    logger.info(f"  LED intensities (P): {cal_data['p_mode_intensities']}")
    logger.info(f"  Per-channel times: {cal_data['channel_integration_times']}")

    return cal_data


def test_acquisition_loop(num_cycles=5):
    """Test the live acquisition loop for N cycles.

    Args:
        num_cycles: Number of 4-channel cycles to acquire
    """
    logger.info("=" * 80)
    logger.info("TESTING LIVE ACQUISITION LOOP")
    logger.info("=" * 80)

    # Load calibration
    cal_data = load_latest_calibration()

    # Connect to hardware
    logger.info("\nConnecting to hardware...")
    hw_mgr = HardwareManager()

    # Scan and connect
    logger.info("Scanning for devices...")
    connection_result = hw_mgr.scan_and_connect(auto_connect=True)
    logger.info(f"Connection result: {connection_result}")

    # Wait for connections to complete (hardware init runs in background)
    logger.info("Waiting for hardware initialization...")
    max_wait = 10  # seconds
    start_time = time.time()

    while (time.time() - start_time) < max_wait:
        if hw_mgr.usb and hw_mgr.ctrl:
            break
        time.sleep(0.5)

    if not hw_mgr.usb or not hw_mgr.ctrl:
        raise RuntimeError(f"Hardware not connected after {max_wait}s (usb={hw_mgr.usb is not None}, ctrl={hw_mgr.ctrl is not None})")

    logger.info(f"✓ Detector: {hw_mgr.usb.serial_number}")
    ctrl_name = getattr(hw_mgr.ctrl, 'device_type', getattr(hw_mgr.ctrl, 'device', type(hw_mgr.ctrl).__name__))
    logger.info(f"✓ Controller: {ctrl_name}")

    # Extract parameters
    channels = ["a", "b", "c", "d"]
    p_int_time = cal_data["p_integration_time"]
    num_scans = cal_data["num_scans"]
    led_intensities = cal_data["p_mode_intensities"]
    s_pol_ref = cal_data["s_pol_ref"]
    dark_p = cal_data.get("dark_p", {})
    wavelengths = cal_data["wavelengths"]

    # Check for per-channel integration times
    per_ch_times = cal_data.get("channel_integration_times", {})
    has_per_ch = bool(per_ch_times)

    logger.info("\n" + "=" * 80)
    logger.info("ACQUISITION PARAMETERS")
    logger.info("=" * 80)
    logger.info(f"Integration time: {p_int_time:.1f}ms")
    logger.info(f"Num scans: {num_scans}")
    logger.info(f"Per-channel times: {has_per_ch}")
    if has_per_ch:
        logger.info(f"  Channel times: {per_ch_times}")
    logger.info(f"LED intensities: {led_intensities}")

    # Pre-arm integration time (optimization)
    logger.info("\n" + "=" * 80)
    logger.info("PRE-ARM OPTIMIZATION")
    logger.info("=" * 80)

    if has_per_ch:
        logger.info("[PRE-ARM] Disabled - using per-channel integration times")
        pre_armed = False
    else:
        logger.info(f"[PRE-ARM] Setting integration time: {p_int_time:.1f}ms")
        result = hw_mgr.usb.set_integration(p_int_time)

        # Verify integration time was actually set
        actual_int = hw_mgr.usb.get_integration_ms()
        logger.info(f"[PRE-ARM] Requested: {p_int_time:.1f}ms, Actual: {actual_int:.1f}ms")

        if result and abs(actual_int - p_int_time) < 1.0:
            logger.info("[PRE-ARM] ✓ Integration time pre-armed and verified")
            logger.info("[PRE-ARM] Will skip set_integration() in loop")
            pre_armed = True
        else:
            logger.warning(f"[PRE-ARM] ✗ Failed to pre-arm (requested={p_int_time:.1f}, actual={actual_int:.1f})")
            pre_armed = False

    # Switch to P-mode
    logger.info("\nSwitching polarizer to P-mode...")
    hw_mgr.ctrl.set_mode("p")
    time.sleep(0.4)  # Settle time
    logger.info("✓ Polarizer in P-mode")

    # Run acquisition cycles
    logger.info("\n" + "=" * 80)
    logger.info(f"RUNNING {num_cycles} ACQUISITION CYCLES")
    logger.info("=" * 80)

    cycle_times = []

    # Helper to send ACK (newline) back to controller firmware
    def send_ack(ctrl):
        try:
            # Common explicit methods
            if hasattr(ctrl, 'ack'):
                ctrl.ack(); return True
            if hasattr(ctrl, 'write'):
                ctrl.write(b"\n"); return True
            # Try private serial handle
            ser = getattr(ctrl, '_ser', None)
            if ser:
                ser.write(b"\n"); return True
        except Exception:
            pass
        return False

    for cycle in range(1, num_cycles + 1):
        logger.info(f"\n--- Cycle {cycle}/{num_cycles} ---")
        cycle_start = time.perf_counter()

        cycle_data = {}

        # Preset per-LED intensities, then run firmware rank sequence
        # 1) Set intensities for all LEDs (A,B,C,D)
        for ch in channels:
            led_int = led_intensities.get(ch)
            if led_int is None:
                logger.warning(f"  {ch.upper()}: No LED intensity - skipping preset")
                continue
            hw_mgr.ctrl.set_intensity(ch, led_int)
            time.sleep(0.010)

        # 2) Proceed to rank sequence (firmware manages on/off per LED)

        # 3) Run rank sequence; acquire during READ for each channel
        settling_ms_global = p_int_time
        dark_ms = 10
        # If per-channel integration times exist, we will set per channel just-in-time before READ
        for ch, signal in hw_mgr.ctrl.led_rank_sequence(255, settling_ms_global, dark_ms):
            # Send ACKs for firmware prompts to advance sequence
            sig = (signal or '').upper()
            if sig in ('READY', 'DONE', 'END'):
                send_ack(hw_mgr.ctrl)

            # When firmware signals READ for channel ch, set integration (if needed) and read spectrum
            int_time = per_ch_times.get(ch, p_int_time) if has_per_ch else p_int_time
            if not pre_armed:
                hw_mgr.usb.set_integration(int_time)
                time.sleep(0.005)

            ch_start = time.perf_counter()
            raw_spectrum = hw_mgr.usb.read_intensity()
            ch_time = (time.perf_counter() - ch_start) * 1000

            if raw_spectrum is None or len(raw_spectrum) == 0:
                logger.warning(f"  {ch.upper()}: Failed to acquire spectrum")
                continue

            # Calculate raw peak counts BEFORE dark correction
            import numpy as np
            raw_peak = np.max(raw_spectrum)
            raw_min = np.min(raw_spectrum)
            raw_mean = np.mean(raw_spectrum)

            # Diagnostic: Show if spectrum looks saturated
            if raw_peak >= 65535:
                logger.warning(f"  {ch.upper()}: DETECTOR SATURATED! Min={raw_min:.0f}, Mean={raw_mean:.0f}, Max={raw_peak:.0f}")
            elif raw_peak == raw_min:
                logger.warning(f"  {ch.upper()}: FLAT SPECTRUM! All pixels = {raw_peak:.0f}")
            elif cycle == 1 and ch == 'a':
                # Log first measurement for reference
                logger.info(f"  {ch.upper()}: First spectrum Min={raw_min:.0f}, Mean={raw_mean:.0f}, Max={raw_peak:.0f}")

            # Dark correction
            dark_ref = dark_p.get(ch, cal_data.get("dark_noise"))
            dark_peak = 0
            if dark_ref is not None and len(dark_ref) == len(raw_spectrum):
                dark_peak = np.max(dark_ref)
                dark_corrected = [max(0, r - d) for r, d in zip(raw_spectrum, dark_ref)]
            else:
                dark_corrected = raw_spectrum
                logger.warning(f"  {ch.upper()}: No dark reference - using raw spectrum")

            # Calculate transmission (P-pol / S-pol)
            s_ref = s_pol_ref.get(ch)
            if s_ref is not None and len(s_ref) == len(dark_corrected):
                transmission = [p / s if s > 0 else 0 for p, s in zip(dark_corrected, s_ref)]
            else:
                logger.warning(f"  {ch.upper()}: S-ref mismatch - cannot calculate transmission")
                transmission = None

            # Calculate ROI signal (example: 650-750nm)
            try:
                wl = np.array(wavelengths)
                trans_arr = np.array(transmission) if transmission else np.array(dark_corrected)

                # Find ROI indices
                roi_mask = (wl >= 650) & (wl <= 750)
                if np.any(roi_mask):
                    roi_signal = np.mean(trans_arr[roi_mask])
                else:
                    roi_signal = np.mean(trans_arr)

                peak_counts = np.max(dark_corrected)
            except Exception:
                roi_signal = 0
                peak_counts = 0

            # Check if LED is actually on (3X above dark)
            snr_ratio = raw_peak / dark_peak if dark_peak > 0 else 0
            led_status = "✓ LED ON" if snr_ratio >= 3.0 else f"✗ LED WEAK ({snr_ratio:.1f}X)"

            led_int = led_intensities.get(ch, 0)
            logger.info(f"  {ch.upper()}: LED={led_int:3d}, Int={int_time:.1f}ms, "
                       f"Raw={raw_peak:.0f}, Dark={dark_peak:.0f}, Peak={peak_counts:.0f}, "
                       f"SNR={snr_ratio:.1f}X {led_status}, Time={ch_time:.1f}ms")

            cycle_data[ch] = {
                "led_intensity": led_int,
                "integration_time": int_time,
                "peak_counts": peak_counts,
                "roi_signal": roi_signal,
                "transmission": transmission,
                "timing_ms": ch_time,
            }

        cycle_elapsed = (time.perf_counter() - cycle_start) * 1000
        cycle_times.append(cycle_elapsed)

        logger.info(f"Cycle {cycle} complete: {cycle_elapsed:.1f}ms")

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Cycles completed: {num_cycles}")

    if cycle_times:
        import numpy as np
        logger.info(f"Cycle times: {np.mean(cycle_times):.1f}ms ± {np.std(cycle_times):.1f}ms")
        logger.info(f"  Min: {np.min(cycle_times):.1f}ms")
        logger.info(f"  Max: {np.max(cycle_times):.1f}ms")

        # Expected vs actual
        expected_time = 250 * 4  # 250ms per channel
        logger.info(f"Expected cycle time: {expected_time}ms")
        logger.info(f"Measured cycle time: {np.mean(cycle_times):.1f}ms")

        if pre_armed:
            time_saved = 7 * 4  # ~7ms saved per channel
            logger.info(f"Pre-arm time savings: ~{time_saved}ms per cycle")

    logger.info("\n✓ Test complete")


if __name__ == "__main__":
    import sys

    # Parse command line args
    num_cycles = 5
    if len(sys.argv) > 1:
        try:
            num_cycles = int(sys.argv[1])
        except ValueError:
            logger.error(f"Invalid cycle count: {sys.argv[1]}")
            sys.exit(1)

    try:
        test_acquisition_loop(num_cycles)
    except KeyboardInterrupt:
        logger.info("\n\nTest interrupted by user")
    except Exception as e:
        logger.error(f"\n\nTest failed: {e}", exc_info=True)
        sys.exit(1)
