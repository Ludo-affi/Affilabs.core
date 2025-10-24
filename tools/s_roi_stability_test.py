"""
S-ROI Stability Test Runner

Standalone diagnostic to measure S-mode 580–610 nm ROI stability while flashing
LEDs sequentially using device_config LED delays. Saves time series to CSV and
prints per-channel stats and suggested normalization factors.

Usage (PowerShell):
  python tools/s_roi_stability_test.py --duration 120 --led 128

Args:
  --duration:  Test duration in seconds (default 120)
  --led:       Optional fixed LED intensity (0-255). If omitted, uses calibrated
               ref_intensity per channel if available, else S_LED_INT.
  --no-delays: Do not use device_config delays; use default LED_DELAY instead.
  --channels:  Optional comma-separated list of channels (e.g., a,b,c,d). If omitted,
               uses settings.CH_LIST.
"""

from __future__ import annotations

import argparse
import sys
import time

import os
from pathlib import Path
import sys as _sys

# Ensure repository root is on sys.path for `utils` imports
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))

from utils.logger import logger
from utils.device_configuration import DeviceConfiguration
from utils.spr_calibrator import SPRCalibrator
from settings import CH_LIST, ROOT_DIR

# Prefer OceanDirect/SeaBreeze USB4000 and PicoP4SPR controller
try:
    from utils.usb4000_oceandirect import USB4000OceanDirect
except Exception as e:  # pragma: no cover
    logger.error(f"USB4000OceanDirect not available: {e}")
    USB4000OceanDirect = None  # type: ignore

try:
    from utils.controller import PicoP4SPR
except Exception as e:  # pragma: no cover
    logger.error(f"PicoP4SPR controller not available: {e}")
    PicoP4SPR = None  # type: ignore


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="S-ROI (580–610 nm) stability diagnostic runner")
    p.add_argument("--duration", type=float, default=120.0, help="Test duration in seconds (default 120)")
    p.add_argument("--led", type=int, default=None, help="Fixed LED intensity (0-255); default uses calibrated ref_intensity or S_LED_INT")
    p.add_argument("--no-delays", action="store_true", help="Disable device_config LED delays and use default LED_DELAY")
    p.add_argument("--led-delay-ms", type=float, default=None, help="Fixed LED delay in milliseconds for both on/off (overrides device_config and --no-delays)")
    p.add_argument("--led-on-delay-ms", type=float, default=None, help="Delay after LED turn-on before measurement (overrides --led-delay-ms)")
    p.add_argument("--led-off-delay-ms", type=float, default=None, help="Delay after LED turn-off before next channel (overrides --led-delay-ms)")
    p.add_argument("--channels", type=str, default=None, help="Comma-separated channels (e.g., a,b,c,d). Default uses settings.CH_LIST")
    p.add_argument("--integration-ms", type=float, default=None, help="Override integration time in ms for this run")
    p.add_argument("--integration-per-ch", type=str, default=None, help="Per-channel integration times in ms (e.g., a:50,b:120,c:19,d:19)")
    p.add_argument("--preflight-only", action="store_true", help="Run LED/polarizer preflight check and exit")
    p.add_argument("--auto-integration", action="store_true", help="Auto-find optimal integration time (50-75%% of max) before running test")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if USB4000OceanDirect is None or PicoP4SPR is None:
        logger.error("Required hardware classes are not available.")
        return 2

    # Prepare device config
    cfg = DeviceConfiguration()
    device_config_dict = cfg.to_dict()

    # Connect hardware
    ctrl = PicoP4SPR()
    if not ctrl.open():
        logger.error("Failed to open PicoP4SPR controller")
        return 2
    logger.info("✓ Controller connected")

    usb = USB4000OceanDirect()
    if not usb.connect():
        logger.error("Failed to connect to USB4000 spectrometer")
        try:
            ctrl.turn_off_channels()
        except Exception:
            pass
        return 2
    logger.info("✓ Spectrometer connected")

    try:
        # Build calibrator
        calibrator = SPRCalibrator(
            ctrl=ctrl,
            usb=usb,
            device_type="PicoP4SPR",
            device_config=device_config_dict,
        )

        # Load LED calibration from device_config and apply integration/LEDs
        baseline = cfg.load_led_calibration()
        if baseline:
            try:
                integ_ms = int(baseline.get("integration_time_ms", 0))
                if integ_ms > 0:
                    calibrator.state.integration = float(integ_ms) / 1000.0
                    # Apply to spectrometer
                    usb.set_integration_time(calibrator.state.integration)
                    logger.info(f"Using integration from device_config: {integ_ms} ms")
            except Exception as e:
                logger.warning(f"Failed to apply integration from device_config: {e}")

            try:
                s_leds = baseline.get("s_mode_intensities", {})
                if isinstance(s_leds, dict) and s_leds:
                    for ch, val in s_leds.items():
                        try:
                            calibrator.state.ref_intensity[ch] = int(val)
                        except Exception:
                            pass
                    logger.info(f"Using S-mode LED intensities from device_config: {s_leds}")
            except Exception as e:
                logger.warning(f"Failed to apply S-mode LEDs from device_config: {e}")

        # Ensure wavelengths are available
        if not calibrator.step_2_calibrate_wavelength_range():
            logger.error("Step 2 (wavelength calibration) failed - cannot run stability test")
            return 1

        # Channels
        if args.channels:
            ch_list = [ch.strip().lower() for ch in args.channels.split(",") if ch.strip()]
        else:
            ch_list = CH_LIST

        # Auto-find optimal integration time if requested
        if args.auto_integration:
            # Build LED intensity map
            per_led = {}
            if args.led is not None:
                per_led = {ch: int(args.led) for ch in ch_list}
            else:
                for ch in ch_list:
                    val = calibrator.state.ref_intensity.get(ch, 0)
                    per_led[ch] = int(val) if int(val) > 0 else 128

            optimal_int = calibrator.find_optimal_integration_time(
                ch_list=ch_list,
                roi_nm=(580.0, 610.0),
                led_intensities=per_led,
            )
            if optimal_int is not None:
                calibrator.state.integration = float(optimal_int) / 1000.0
                usb.set_integration_time(calibrator.state.integration)
                logger.info(f"Using auto-detected integration time: {optimal_int} ms")
            else:
                logger.warning("Auto-integration failed; using current value")

        # Optional manual integration override (takes precedence over auto)
        if args.integration_ms is not None and args.integration_ms > 0:
            try:
                calibrator.state.integration = float(args.integration_ms) / 1000.0
                usb.set_integration_time(calibrator.state.integration)
                logger.info(f"Overriding integration for this run: {args.integration_ms:.1f} ms")
            except Exception as e:
                logger.warning(f"Failed to override integration: {e}")

        # Sanity log: filtered wavelength range and pixel count
        try:
            w = calibrator.state.wavelengths
            if w is not None and len(w) > 0:
                logger.info(
                    f"Filtered wavelength range: {float(w[0]):.1f}-{float(w[-1]):.1f} nm | pixels={len(w)}"
                )
            else:
                logger.warning("Filtered wavelengths not available; ROI indexing may fail")
        except Exception:
            logger.debug("Could not log filtered wavelength range")

        # Optional quick LED preflight: verify ROI responds per channel
        print("=" * 80)
        print("LED PREFLIGHT CHECK (S-mode verification + per-channel ROI test)")
        print("=" * 80)
        try:
            # Force S-mode and small settle
            print("Step 1: Setting polarizer to S-mode...")
            try:
                ok_mode = bool(calibrator.ctrl.set_mode("s"))
                time.sleep(0.3)
                print(f"  set_mode('s') returned: {ok_mode}")
                if not ok_mode and hasattr(calibrator.ctrl, "servo_set") and hasattr(calibrator, "_get_oem_positions"):
                    s_pos, p_pos, _ = calibrator._get_oem_positions()
                    print(f"  OEM positions available: S={s_pos}, P={p_pos}")
                    if s_pos is not None and p_pos is not None:
                        print("  ⚠️ Polarizer set_mode did not confirm; applying OEM servo positions directly")
                        try:
                            ok_servo = calibrator.ctrl.servo_set(s=int(s_pos), p=int(p_pos))
                            print(f"  servo_set returned: {ok_servo}")
                            time.sleep(0.3)
                        except Exception as e_servo:
                            print(f"  ❌ servo_set failed: {e_servo}")
                else:
                    print("  ✓ S-mode confirmed or OEM positions not available")
            except Exception as e_mode:
                print(f"  ❌ S-mode setup failed: {e_mode}")

            w = calibrator.state.wavelengths
            print(f"Step 2: Wavelength array available: {w is not None and len(w) > 0}")
            if w is not None and len(w) > 0:
                import numpy as _np
                print(f"  Wavelength array: {len(w)} pixels, range {float(w[0]):.1f}-{float(w[-1]):.1f} nm")
                roi_nm = (580.0, 610.0)
                i0 = int(_np.argmin(_np.abs(w - roi_nm[0])))
                i1 = int(_np.argmin(_np.abs(w - roi_nm[1])))
                print(f"  ROI target: {roi_nm[0]}-{roi_nm[1]} nm")
                print(f"  ROI indices: {i0}-{i1} (span={i1-i0} px)")
                print(f"  ROI actual: {float(w[i0]):.1f}-{float(w[i1]):.1f} nm")
                if i1 > i0:
                    # Build per-channel LED map like diagnostic
                    if args.led is not None:
                        per_led = {ch: int(args.led) for ch in ch_list}
                    else:
                        per_led = {}
                        for ch in ch_list:
                            val = calibrator.state.ref_intensity.get(ch, 0)
                            per_led[ch] = int(val) if int(val) > 0 else 128
                    print(f"  LED intensities to test: {per_led}")

                    # Dark baseline - be VERY forceful about LED shutdown
                    print("Step 3: Measuring dark baseline...")
                    print("  🔌 Forcing all LEDs OFF (multiple attempts)...")
                    for _ in range(5):  # Quintuple-force LED shutdown
                        calibrator._all_leds_off_batch()
                        time.sleep(0.5)
                    print("  ⏳ Waiting 5 seconds for full LED decay and detector stabilization...")
                    time.sleep(5.0)  # Extended buffer time

                    # Take a first dark measurement to check LED decay
                    print("  📷 Acquiring initial dark spectrum (LED decay check)...")
                    dark_check = calibrator._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
                    dark_check_f = calibrator._apply_spectral_filter(dark_check) if dark_check is not None else None
                    dark_check_roi = float(_np.max(dark_check_f[i0:i1])) if (dark_check_f is not None and len(dark_check_f) > 0) else 0.0
                    print(f"  ⏱️  Initial dark ROI: {dark_check_roi:.1f} counts")

                    # Wait additional time and measure again
                    print("  ⏳ Waiting another 3 seconds...")
                    time.sleep(3.0)
                    print("  📷 Acquiring final dark spectrum...")
                    dark = calibrator._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
                    dark_f = calibrator._apply_spectral_filter(dark) if dark is not None else None
                    dark_roi = float(_np.max(dark_f[i0:i1])) if (dark_f is not None and len(dark_f) > 0) else 0.0
                    print(f"  ✅ Final dark ROI max: {dark_roi:.1f} counts")

                    # Show decay trend
                    decay = dark_check_roi - dark_roi
                    print(f"  📉 Dark decay: {decay:.1f} counts ({dark_check_roi:.0f} → {dark_roi:.0f})")
                    if dark_roi > 5000:
                        print(f"  ⚠️  WARNING: Dark baseline still high ({dark_roi:.0f} counts) - may need longer settle time")
                    elif abs(decay) < 100:
                        print(f"  ✅ Dark baseline stable (minimal decay)")



                    print("Step 4: Testing LEDs per channel...")
                    low_count_channels = []
                    for ch in ch_list:
                        print(f"  Testing channel {ch.upper()}...", end=" ", flush=True)
                        # Use sequential method to bypass batch command
                        ok = calibrator.ctrl.set_intensity(ch, per_led[ch])
                        print(f"set_intensity_ok={ok}", end=" ")
                        time.sleep(0.12)
                        sig = calibrator._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
                        sig_f = calibrator._apply_spectral_filter(sig) if sig is not None else None
                        sig_roi = float(_np.max(sig_f[i0:i1])) if (sig_f is not None and len(sig_f) > 0) else 0.0
                        delta = sig_roi - dark_roi
                        print(f"ROI={sig_roi:.0f}, dark={dark_roi:.0f}, Δ={delta:.0f} @ LED={per_led[ch]}")
                        calibrator._all_leds_off_batch()
                        time.sleep(0.08)
                        if delta < 500.0:  # Should be MUCH higher with proper LED/integration
                            low_count_channels.append(ch)

                    print()
                    if low_count_channels:
                        print(f"⚠️ Low ROI response detected on channels: {low_count_channels}")
                        print("   Check: 1) LED wiring/power 2) Polarizer in S position 3) Integration time sufficient")
                    else:
                        print("✅ All channels responded with good signal")
                else:
                    print("  ❌ Invalid ROI indices - cannot perform preflight")
            else:
                print("  ❌ No wavelengths available - cannot perform preflight")
        except Exception as _e:
            print(f"❌ LED preflight failed with exception: {_e}")
            import traceback
            print(traceback.format_exc())

        # Exit early if only preflight is requested
        if args.preflight_only:
            return 0

        # Parse per-channel integration times if provided
        integration_time_ms_by_ch = None
        if args.integration_per_ch:
            integration_time_ms_by_ch = {}
            for pair in args.integration_per_ch.split(','):
                ch, ms = pair.split(':')
                integration_time_ms_by_ch[ch.strip().lower()] = float(ms.strip())
            print(f"\n🔧 Using per-channel integration times: {integration_time_ms_by_ch}\n")

        # Run diagnostic
        ok = calibrator.diagnostic_s_roi_stability_test(
            ch_list=ch_list,
            duration_sec=float(args.duration),
            led_value=None if args.led is None else int(args.led),
            use_device_config_delays=not args.no_delays,
            led_delay_ms=args.led_delay_ms,
            led_on_delay_ms=args.led_on_delay_ms,
            led_off_delay_ms=args.led_off_delay_ms,
            integration_time_ms_by_ch=integration_time_ms_by_ch,
        )
        if not ok:
            return 1

        # After the run, try to locate the latest stability CSV and produce a plot
        try:
            from pathlib import Path as _Path
            import glob as _glob
            import csv as _csv
            import math as _math
            from collections import deque as _deque
            try:
                import matplotlib
                matplotlib.use("Agg")  # headless-safe backend
                import matplotlib.pyplot as _plt
            except Exception as e:
                logger.warning(f"Matplotlib not available, skipping plot: {e}")
                return 0

            # Use configured ROOT_DIR (usually 'generated-files') where calibrator saves outputs
            calib_dir = _Path(ROOT_DIR) / "calibration_data"
            pattern = str(calib_dir / "s_roi_stability_*.csv")
            files = sorted(_glob.glob(pattern), key=lambda p: _Path(p).stat().st_mtime, reverse=True)
            if not files:
                print("⚠️ No stability CSV found to plot - diagnostic may have failed to save data")
                logger.error("No stability CSV found in calibration_data/")
                return 1
            csv_path = _Path(files[0])
            print(f"\n📊 Generating plot from: {csv_path.name}")

            # Load time series
            records: list[tuple[float, str, float]] = []
            with open(csv_path, "r", newline="") as f:
                reader = _csv.DictReader(f)
                for row in reader:
                    try:
                        t = float(row["t_seconds"])  # already formatted as string
                        ch = str(row["channel"]).strip().lower()
                        val = float(row["roi_max_counts"])  # may be formatted
                        records.append((t, ch, val))
                    except Exception:
                        continue

            if not records:
                logger.warning("Empty stability CSV; nothing to plot")
                return 0

            # Organize per-channel series
            per_ch_times: dict[str, list[float]] = {ch: [] for ch in ch_list}
            per_ch_vals: dict[str, list[float]] = {ch: [] for ch in ch_list}
            for t, ch, v in records:
                if ch in per_ch_times:
                    per_ch_times[ch].append(t)
                    per_ch_vals[ch].append(v)

            # Rolling std (samples) window size
            window = 10

            def rolling_std(values: list[float], w: int) -> list[float]:
                if not values:
                    return []
                out: list[float] = []
                q = _deque(maxlen=w)
                s = 0.0
                s2 = 0.0
                for v in values:
                    # push
                    if len(q) == q.maxlen:
                        old = q[0]
                        s -= old
                        s2 -= old * old
                    q.append(v)
                    s += v
                    s2 += v * v
                    n = len(q)
                    if n > 1:
                        mean = s / n
                        var = max(0.0, (s2 / n) - (mean * mean))
                        out.append(var ** 0.5)
                    else:
                        out.append(0.0)
                return out

            def rolling_mean(values: list[float], w: int) -> list[float]:
                if not values:
                    return []
                out: list[float] = []
                q = _deque(maxlen=w)
                s = 0.0
                for v in values:
                    if len(q) == q.maxlen:
                        s -= q[0]
                    q.append(v)
                    s += v
                    out.append(s / len(q))
                return out

            def adaptive_detrend(values: list[float], times: list[float]) -> list[float]:
                """Advanced detrending using polynomial fit + rolling correction."""
                if len(values) < 10:
                    return values

                vals_arr = _np.array(values)
                times_arr = _np.array(times)

                # Fit polynomial to capture slow drift (thermal/aging)
                poly_order = min(3, len(values) // 20)  # Adaptive order
                if poly_order >= 1:
                    coeffs = _np.polyfit(times_arr, vals_arr, poly_order)
                    trend = _np.polyval(coeffs, times_arr)
                    detrended = vals_arr - trend
                else:
                    detrended = vals_arr - _np.mean(vals_arr)

                # Remove high-frequency noise with rolling median
                window = min(5, len(values) // 10)
                if window >= 3:
                    smoothed = []
                    for i in range(len(detrended)):
                        start = max(0, i - window // 2)
                        end = min(len(detrended), i + window // 2 + 1)
                        smoothed.append(_np.median(detrended[start:end]))
                    return smoothed

                return detrended.tolist()

            # Plot per-channel rolling std: raw vs multiple correction methods
            n_ch = len(ch_list)
            cols = 2 if n_ch > 2 else n_ch
            rows = int(_math.ceil(n_ch / cols))
            _plt.figure(figsize=(14, 4 * rows))

            correction_summary = {}

            for idx, ch in enumerate(ch_list, start=1):
                ts = per_ch_times[ch]
                vs = per_ch_vals[ch]

                # Method 1: Rolling mean detrending (original)
                rm = rolling_mean(vs, window)
                cs_rolling = [v - m for v, m in zip(vs, rm)]
                rs_raw = rolling_std(vs, window)
                rs_rolling = rolling_std(cs_rolling, window)

                # Method 2: Adaptive polynomial detrending
                cs_adaptive = adaptive_detrend(vs, ts)
                rs_adaptive = rolling_std(cs_adaptive, window)

                # Method 3: Reference normalization (use channel B if available and not current)
                if ch != 'b' and 'b' in per_ch_vals and len(per_ch_vals['b']) == len(vs):
                    # Normalize by channel B's rolling mean
                    ref_rm = rolling_mean(per_ch_vals['b'], window)
                    cs_ref = [float(v / (r / _np.mean(per_ch_vals['b']))) if r > 0 else float(v)
                             for v, r in zip(vs, ref_rm)]
                    rs_ref = rolling_std(cs_ref, window)
                else:
                    rs_ref = rs_raw

                # Calculate improvement metrics
                raw_std = _np.mean(rs_raw[window:]) if len(rs_raw) > window else 0
                rolling_std_val = _np.mean(rs_rolling[window:]) if len(rs_rolling) > window else 0
                adaptive_std_val = _np.mean(rs_adaptive[window:]) if len(rs_adaptive) > window else 0

                improvement_rolling = ((raw_std - rolling_std_val) / raw_std * 100) if raw_std > 0 else 0
                improvement_adaptive = ((raw_std - adaptive_std_val) / raw_std * 100) if raw_std > 0 else 0

                correction_summary[ch] = {
                    'raw_std': raw_std,
                    'rolling_improvement_%': improvement_rolling,
                    'adaptive_improvement_%': improvement_adaptive
                }

                _plt.subplot(rows, cols, idx)
                _plt.plot(ts, rs_raw, label=f"Raw (σ={raw_std:.1f})", alpha=0.7, linewidth=2)
                _plt.plot(ts, rs_rolling, label=f"Rolling Mean ({improvement_rolling:+.1f}%)", alpha=0.8, linewidth=1.5)
                _plt.plot(ts, rs_adaptive, label=f"Adaptive Poly ({improvement_adaptive:+.1f}%)", alpha=0.8, linewidth=1.5)
                if ch != 'b':
                    _plt.plot(ts, rs_ref, '--', label="Ref-normalized", alpha=0.6, linewidth=1)

                _plt.title(f"Channel {ch.upper()} | Rolling Std Comparison (window={window})")
                _plt.xlabel("time (s)")
                _plt.ylabel("rolling std (counts)")
                _plt.grid(True, alpha=0.3)
                _plt.legend(frameon=True, fontsize=8)

            # Print correction summary
            print("\n" + "="*60)
            print("JITTER CORRECTION SUMMARY")
            print("="*60)
            for ch in ch_list:
                s = correction_summary[ch]
                print(f"Channel {ch.upper()}: Raw σ={s['raw_std']:.1f} | "
                      f"Rolling: {s['rolling_improvement_%']:+.1f}% | "
                      f"Adaptive: {s['adaptive_improvement_%']:+.1f}%")
            print("="*60)

            png_path = csv_path.with_suffix(".png")
            _plt.tight_layout()
            _plt.savefig(png_path, dpi=120)
            _plt.close()

            # Now create stacked spectra plot if spectra data exists
            spectra_npz_path = csv_path.parent / (csv_path.stem + "_spectra.npz")
            if spectra_npz_path.exists():
                try:
                    print(f"\n📊 Generating stacked spectra plot...")
                    data = _np.load(spectra_npz_path)
                    wavelengths = data['wavelengths']

                    # Create stacked spectra plot
                    n_ch = len(ch_list)
                    _plt.figure(figsize=(14, 3 * n_ch))

                    for idx, ch in enumerate(ch_list, start=1):
                        spectra_key = f'spectra_{ch}'
                        times_key = f'times_{ch}'

                        if spectra_key in data and times_key in data:
                            spectra = data[spectra_key]
                            times = data[times_key]

                            _plt.subplot(n_ch, 1, idx)
                            # Plot all spectra with color based on time
                            for i, (t, spectrum) in enumerate(zip(times, spectra)):
                                color = _plt.cm.viridis(t / times[-1] if len(times) > 1 else 0.5)
                                _plt.plot(wavelengths, spectrum, color=color, alpha=0.3, linewidth=0.5)

                            # Plot mean spectrum
                            mean_spectrum = _np.mean(spectra, axis=0)
                            _plt.plot(wavelengths, mean_spectrum, 'r-', linewidth=2, label='Mean', zorder=10)

                            _plt.title(f"Channel {ch.upper()} - Stacked S-pol Spectra (n={len(spectra)})")
                            _plt.xlabel("Wavelength (nm)")
                            _plt.ylabel("Counts")
                            _plt.grid(True, alpha=0.3)
                            _plt.legend()

                            # Add colorbar for time
                            if idx == 1:
                                sm = _plt.cm.ScalarMappable(cmap=_plt.cm.viridis,
                                                            norm=_plt.Normalize(vmin=0, vmax=times[-1] if len(times) > 0 else 1))
                                sm.set_array([])
                                cbar = _plt.colorbar(sm, ax=_plt.gca())
                                cbar.set_label('Time (s)')

                    spectra_png_path = csv_path.parent / (csv_path.stem + "_spectra.png")
                    _plt.tight_layout()
                    _plt.savefig(spectra_png_path, dpi=120)
                    _plt.close()
                    print(f"📊 Stacked spectra plot saved: {spectra_png_path}")
                    logger.info(f"📈 Saved stacked spectra plot: {spectra_png_path}")
                except Exception as e:
                    print(f"⚠️  Failed to generate spectra plot: {e}")
                    logger.error(f"Spectra plot generation failed: {e}")

            print(f"\n✅ COMPLETE!")
            print(f"📊 Rolling std plot saved: {png_path}")
            print(f"📁 CSV data: {csv_path}")
            logger.info(f"📈 Saved rolling std plot: {png_path}")
        except Exception as e:
            print(f"\n❌ Failed to generate plot: {e}")
            logger.error(f"Plot generation failed: {e}")
            import traceback
            print(traceback.format_exc())
            return 1
        return 0

    finally:
        # Best-effort cleanup
        try:
            ctrl.turn_off_channels()
        except Exception:
            pass
        try:
            if hasattr(usb, "disconnect"):
                usb.disconnect()
        except Exception:
            pass
        time.sleep(0.1)


if __name__ == "__main__":
    sys.exit(main())
