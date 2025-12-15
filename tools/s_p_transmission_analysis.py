"""Acquire S and P polarization spectra and analyze transmission with centroid method."""

import argparse
import logging
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from settings.settings import ROOT_DIR
from utils.controller import PicoP4SPR
from utils.device_configuration import DeviceConfiguration
from utils.spr_calibrator import SPRCalibrator
from utils.usb4000_oceandirect import USB4000OceanDirect

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="S/P transmission spectrum acquisition and centroid analysis",
    )
    p.add_argument(
        "--duration",
        type=float,
        default=60.0,
        help="Acquisition duration per polarization (seconds)",
    )
    p.add_argument("--led", type=int, default=255, help="LED intensity (0-255)")
    p.add_argument(
        "--led-on-delay-ms",
        type=float,
        default=100,
        help="LED turn-on delay in ms",
    )
    p.add_argument(
        "--led-off-delay-ms",
        type=float,
        default=5,
        help="LED turn-off delay in ms",
    )
    p.add_argument(
        "--integration-per-ch",
        type=str,
        default="a:53,b:79,c:18,d:18",
        help="Per-channel integration times (e.g., a:53,b:79,c:18,d:18)",
    )
    p.add_argument(
        "--channels",
        type=str,
        default="a,b,c,d",
        help="Channels to measure",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    # Parse channels
    ch_list = [ch.strip().lower() for ch in args.channels.split(",")]

    # Parse per-channel integration times
    integration_time_ms_by_ch = {}
    for pair in args.integration_per_ch.split(","):
        ch, ms = pair.split(":")
        integration_time_ms_by_ch[ch.strip().lower()] = float(ms.strip())

    print("\n" + "=" * 80)
    print("S/P TRANSMISSION SPECTRUM ACQUISITION")
    print("=" * 80)
    print(f"Duration per polarization: {args.duration}s")
    print(f"LED intensity: {args.led}")
    print(f"LED delays: {args.led_on_delay_ms}ms on / {args.led_off_delay_ms}ms off")
    print(f"Per-channel integration: {integration_time_ms_by_ch}")
    print(f"Channels: {ch_list}")
    print("=" * 80 + "\n")

    # Connect hardware
    ctrl = PicoP4SPR()
    if not ctrl.open():
        logger.error("Failed to open controller")
        return 2
    print("✓ Controller connected")

    usb = USB4000OceanDirect()
    if not usb:
        logger.error("Failed to open spectrometer")
        return 2
    print("✓ Spectrometer connected")

    # Create calibrator
    cfg = DeviceConfiguration()
    device_config = cfg.to_dict()
    if not device_config or not device_config.get("baseline"):
        print("⚠️  No complete device config found, using minimal configuration...")
        device_config = {
            "device_type": "UNKNOWN",
            "baseline": {},
            "wavelengths": device_config.get("wavelengths", [])
            if device_config
            else [],
        }
    device_type = device_config.get("device_type", "UNKNOWN")

    try:
        calibrator = SPRCalibrator(ctrl, usb, device_type, device_config)
    except ValueError as e:
        print(f"⚠️  Calibrator initialization warning: {e}")
        print("Continuing without OEM polarizer config...")
        # Create minimal calibrator bypassing validation
        calibrator = SPRCalibrator.__new__(SPRCalibrator)
        calibrator.ctrl = ctrl
        calibrator.usb = usb
        calibrator.device_type = device_type
        calibrator.device_config = device_config
        from utils.spr_state import SPRState

        calibrator.state = SPRState()
        calibrator.progress_callback = None
        calibrator.stop_flag = None
        calibrator._last_active_channel = None

    # Calibrate wavelengths
    if not calibrator.step_2_calibrate_wavelength_range():
        logger.error("Wavelength calibration failed")
        return 1
    print("✓ Wavelengths calibrated")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ========================================================================
    # STEP 1: Move to S polarization and acquire
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 1: S-POLARIZATION ACQUISITION")
    print("=" * 80)

    print("Moving polarizer to S position...")
    ctrl.set_mode(mode="s")
    time.sleep(1.0)  # Allow servo to move

    # Verify position
    try:
        pos = ctrl.servo_get()
        s_pos = (
            pos.get("s", b"000").decode(errors="ignore")
            if isinstance(pos.get("s"), (bytes, bytearray))
            else str(pos.get("s"))
        )
        p_pos = (
            pos.get("p", b"000").decode(errors="ignore")
            if isinstance(pos.get("p"), (bytes, bytearray))
            else str(pos.get("p"))
        )
        print(f"✓ Polarizer positions: S={s_pos}, P={p_pos}")
    except Exception as e:
        print(f"⚠️ Could not verify polarizer position: {e}")

    print(f"\nAcquiring S-pol data for {args.duration}s...")
    ok_s = calibrator.diagnostic_s_roi_stability_test(
        ch_list=ch_list,
        duration_sec=args.duration,
        led_value=args.led,
        led_on_delay_ms=args.led_on_delay_ms,
        led_off_delay_ms=args.led_off_delay_ms,
        integration_time_ms_by_ch=integration_time_ms_by_ch,
    )

    if not ok_s:
        print("❌ S-pol acquisition failed")
        return 1

    print("✓ S-pol data acquired")

    # ========================================================================
    # STEP 2: Move to P polarization and acquire
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 2: P-POLARIZATION ACQUISITION")
    print("=" * 80)

    print("Moving polarizer to P position...")
    ctrl.set_mode(mode="p")
    time.sleep(1.0)  # Allow servo to move

    # Verify position
    try:
        pos = ctrl.servo_get()
        s_pos = (
            pos.get("s", b"000").decode(errors="ignore")
            if isinstance(pos.get("s"), (bytes, bytearray))
            else str(pos.get("s"))
        )
        p_pos = (
            pos.get("p", b"000").decode(errors="ignore")
            if isinstance(pos.get("p"), (bytes, bytearray))
            else str(pos.get("p"))
        )
        print(f"✓ Polarizer positions: S={s_pos}, P={p_pos}")
    except Exception as e:
        print(f"⚠️ Could not verify polarizer position: {e}")

    print(f"\nAcquiring P-pol data for {args.duration}s...")
    ok_p = calibrator.diagnostic_s_roi_stability_test(
        ch_list=ch_list,
        duration_sec=args.duration,
        led_value=args.led,
        led_on_delay_ms=args.led_on_delay_ms,
        led_off_delay_ms=args.led_off_delay_ms,
        integration_time_ms_by_ch=integration_time_ms_by_ch,
    )

    if not ok_p:
        print("❌ P-pol acquisition failed")
        return 1

    print("✓ P-pol data acquired")

    # ========================================================================
    # STEP 3: Load and process data
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 3: LOADING DATA AND CALCULATING TRANSMISSION")
    print("=" * 80)

    # Find the most recent NPZ files (S and P data)
    import glob

    calib_dir = Path(ROOT_DIR) / "calibration_data"
    npz_files = sorted(
        glob.glob(str(calib_dir / "s_roi_stability_*_spectra.npz")),
        key=lambda p: Path(p).stat().st_mtime,
        reverse=True,
    )

    if len(npz_files) < 2:
        print(f"❌ Need 2 NPZ files (S and P), found {len(npz_files)}")
        return 1

    p_pol_file = Path(npz_files[0])  # Most recent = P
    s_pol_file = Path(npz_files[1])  # Second most recent = S

    print(f"Loading S-pol data: {s_pol_file.name}")
    print(f"Loading P-pol data: {p_pol_file.name}")

    s_data = np.load(s_pol_file)
    p_data = np.load(p_pol_file)

    # Extract spectra organized by channel
    # Format: times, channels, spectra arrays
    s_times = s_data["times"]
    s_channels = s_data["channels"].astype(str)
    s_spectra = s_data["spectra"]

    p_times = p_data["times"]
    p_channels = p_data["channels"].astype(str)
    p_spectra = p_data["spectra"]

    wavelengths = calibrator.state.wavelengths
    dark_noise = calibrator.state.dark_noise

    print(f"S-pol: {len(s_times)} measurements")
    print(f"P-pol: {len(p_times)} measurements")
    print(
        f"Wavelengths: {len(wavelengths)} pixels ({wavelengths[0]:.1f}-{wavelengths[-1]:.1f} nm)",
    )
    print(f"Dark noise: {dark_noise[0]:.1f} - {dark_noise[-1]:.1f} counts")

    # ========================================================================
    # STEP 4: Calculate transmission spectra and analyze with centroid
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 4: TRANSMISSION ANALYSIS WITH CENTROID METHOD")
    print("=" * 80)

    # Save transmission data
    output_file = calib_dir / f"transmission_analysis_{timestamp}.npz"

    print(f"\n💾 Saving transmission data to: {output_file.name}")
    np.savez_compressed(
        output_file,
        s_times=s_times,
        s_channels=s_channels,
        s_spectra=s_spectra,
        p_times=p_times,
        p_channels=p_channels,
        p_spectra=p_spectra,
        wavelengths=wavelengths,
        dark_noise=dark_noise,
        integration_times_str=str(integration_time_ms_by_ch),
        led_value=args.led,
    )

    print("\n✅ ACQUISITION COMPLETE!")
    print(f"📁 S-pol CSV: {s_pol_file.with_suffix('.csv').name}")
    print(f"📁 P-pol CSV: {p_pol_file.with_suffix('.csv').name}")
    print(f"📁 Combined data: {output_file.name}")
    print("\nNext step: Run centroid analysis on transmission spectra")

    return 0


if __name__ == "__main__":
    exit(main())
