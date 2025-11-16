"""
Measure acquisition timing for single-channel spectrum and full A→D cycle.

It uses:
- Controller: PicoP4SPR (LED control + S/P mode)
- Spectrometer: USB4000 via SeaBreeze (USB4000OceanDirect)

Reports:
- Spectrometer-only read time (acquire_spectrum)
- Single-channel acquisition time (LED on -> read -> LED off)
- Full cycle time (A→D, sequential channels)

Usage (from repo root or with PYTHONPATH set to project root):
  python tools/diagnostic_scripts/measure_acquisition_timing.py --integration-ms 50 --mode p --repeats 5

Notes:
- Integration time dominates timing; overhead includes USB and controller commands.
- For stable estimates, the script takes multiple repeats and reports mean/median.
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

# Add project root to sys.path (so utils imports resolve when run from tools/...)
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.controller import PicoP4SPR  # type: ignore
from utils.usb4000_oceandirect import USB4000OceanDirect as USB4000  # type: ignore

CHANNELS = ["a", "b", "c", "d"]


def _measure_spectrometer_only(usb: USB4000, repeats: int) -> list[float]:
    times_ms: list[float] = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        sp = usb.acquire_spectrum()
        t1 = time.perf_counter()
        if sp is None:
            raise RuntimeError("Spectrometer failed to acquire spectrum")
        times_ms.append((t1 - t0) * 1000.0)
    return times_ms


def _measure_single_channel(usb: USB4000, ctrl: PicoP4SPR, ch: str, intensity: int, mode: str, settle_s: float) -> float:
    # LED on, set mode, settle, read, LED off
    ctrl.set_intensity(ch=ch, raw_val=intensity)
    if mode.lower() in ("s", "p"):
        ctrl.set_mode(mode.lower())
    time.sleep(settle_s)
    t0 = time.perf_counter()
    sp = usb.acquire_spectrum()
    t1 = time.perf_counter()
    ctrl.turn_off_channels()
    if sp is None:
        raise RuntimeError(f"Spectrometer failed to acquire spectrum (channel {ch})")
    return (t1 - t0) * 1000.0


def _measure_cycle(usb: USB4000, ctrl: PicoP4SPR, intensities: dict[str, int], mode: str, settle_s: float) -> float:
    t0 = time.perf_counter()
    for ch in CHANNELS:
        ctrl.set_intensity(ch=ch, raw_val=int(intensities.get(ch, 255)))
        if mode.lower() in ("s", "p"):
            ctrl.set_mode(mode.lower())
        time.sleep(settle_s)
        sp = usb.acquire_spectrum()
        if sp is None:
            raise RuntimeError(f"Spectrometer failed during cycle on channel {ch}")
        ctrl.turn_off_channels()
    t1 = time.perf_counter()
    return (t1 - t0) * 1000.0


def main() -> None:
    ap = argparse.ArgumentParser(description="Measure acquisition timing for single-channel and A→D cycle")
    ap.add_argument("--integration-ms", type=float, default=50.0, help="Integration time in ms (default 50)")
    ap.add_argument("--mode", type=str, default="p", choices=["s", "p"], help="Polarizer mode")
    ap.add_argument("--channel", type=str, default="a", choices=CHANNELS, help="Channel for single-channel timing")
    ap.add_argument("--intensity", type=int, default=180, help="LED intensity for single-channel timing (0-255)")
    ap.add_argument("--repeats", type=int, default=5, help="Number of repeats to average timings")
    ap.add_argument("--settle-ms", type=float, default=30.0, help="Settle delay after LED/mode change (ms)")
    ap.add_argument("--cycle-intensity", type=int, default=180, help="LED intensity used for all channels in cycle")
    args = ap.parse_args()

    settle_s = max(0.0, args.settle_ms / 1000.0)

    # Initialize hardware
    usb = USB4000()
    devices = usb.discover_devices()
    if not devices:
        raise RuntimeError("No spectrometer found")
    usb.connect(devices[0])
    usb.set_integration_time(args.integration_ms / 1000.0)

    ctrl = PicoP4SPR()
    ctrl.turn_off_channels()

    print("\n=== Acquisition Timing Measurement ===")
    print(f"Integration: {args.integration_ms:.1f} ms, Mode: {args.mode.upper()}, Settle: {args.settle_ms:.0f} ms")

    # Spectrometer-only timing
    spec_times = _measure_spectrometer_only(usb, max(1, args.repeats))
    print("\nSpectrometer acquire_spectrum() timing:")
    print(f"  mean:   {statistics.mean(spec_times):6.2f} ms")
    print(f"  median: {statistics.median(spec_times):6.2f} ms")
    print(f"  min:    {min(spec_times):6.2f} ms  |  max: {max(spec_times):6.2f} ms")

    # Single-channel timing
    single_times: list[float] = []
    for _ in range(max(1, args.repeats)):
        t_ms = _measure_single_channel(usb, ctrl, args.channel.lower(), args.intensity, args.mode.lower(), settle_s)
        single_times.append(t_ms)
    print(f"\nSingle-channel acquisition timing (LED {args.channel.upper()}, intensity {args.intensity}):")
    print(f"  mean:   {statistics.mean(single_times):6.2f} ms")
    print(f"  median: {statistics.median(single_times):6.2f} ms")
    print(f"  min:    {min(single_times):6.2f} ms  |  max: {max(single_times):6.2f} ms")

    # Full cycle timing A→D
    intensities = {ch: int(args.cycle_intensity) for ch in CHANNELS}
    cycle_times: list[float] = []
    for _ in range(max(1, args.repeats)):
        t_ms = _measure_cycle(usb, ctrl, intensities, args.mode.lower(), settle_s)
        cycle_times.append(t_ms)
    print(f"\nFull cycle timing (A→D, intensity {args.cycle_intensity} for all channels):")
    print(f"  mean:   {statistics.mean(cycle_times):7.2f} ms")
    print(f"  median: {statistics.median(cycle_times):7.2f} ms")
    print(f"  min:    {min(cycle_times):7.2f} ms  |  max: {max(cycle_times):7.2f} ms")

    # Rough overhead estimate (beyond integration time)
    spec_overhead = statistics.mean(spec_times) - args.integration_ms
    single_overhead = statistics.mean(single_times) - args.integration_ms
    print("\nApprox. overhead (beyond integration time):")
    print(f"  spectrometer-only: {spec_overhead:6.2f} ms")
    print(f"  single-channel:    {single_overhead:6.2f} ms")

    # Cleanup
    ctrl.turn_off_channels()
    try:
        usb.disconnect()
    except Exception:
        pass


if __name__ == "__main__":
    main()
