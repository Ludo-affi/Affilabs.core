"""
Quick timing test for acquisition:
- Spectrometer-only read time
- Single-channel time (LED on → settle → read → off)
- Full cycle time (A→D)

Defaults: 50 ms integration, P-mode, 5 repeats, 30 ms settle.
Run:
    python test.py --integration-ms 50 --mode p --repeats 5 --settle-ms 30
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

# Ensure project root on sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.controller import PicoP4SPR  # type: ignore
from utils.usb4000_oceandirect import USB4000OceanDirect as USB4000  # type: ignore

CHANNELS = ["a", "b", "c", "d"]


def spectrometer_only(usb: USB4000, repeats: int) -> list[float]:
    times: list[float] = []
    for _ in range(max(1, repeats)):
        t0 = time.perf_counter()
        sp = usb.acquire_spectrum()
        t1 = time.perf_counter()
        if sp is None:
            raise RuntimeError("Spectrometer failed to acquire spectrum")
        times.append((t1 - t0) * 1000.0)
    return times


def single_channel(usb: USB4000, ctrl: PicoP4SPR, ch: str, intensity: int, mode: str, settle_s: float) -> float:
    ctrl.set_intensity(ch=ch, raw_val=intensity)
    if mode in ("s", "p"):
        ctrl.set_mode(mode)
    time.sleep(settle_s)
    t0 = time.perf_counter()
    sp = usb.acquire_spectrum()
    t1 = time.perf_counter()
    ctrl.turn_off_channels()
    if sp is None:
        raise RuntimeError(f"Spectrometer failed (channel {ch})")
    return (t1 - t0) * 1000.0


def cycle_ad(usb: USB4000, ctrl: PicoP4SPR, intensity: int, mode: str, settle_s: float) -> float:
    t0 = time.perf_counter()
    for ch in CHANNELS:
        ctrl.set_intensity(ch=ch, raw_val=intensity)
        if mode in ("s", "p"):
            ctrl.set_mode(mode)
        time.sleep(settle_s)
        sp = usb.acquire_spectrum()
        if sp is None:
            raise RuntimeError(f"Spectrometer failed during cycle on {ch}")
        ctrl.turn_off_channels()
    t1 = time.perf_counter()
    return (t1 - t0) * 1000.0


def main() -> None:
    ap = argparse.ArgumentParser(description="Measure acquisition timing (single channel and A→D cycle)")
    ap.add_argument("--integration-ms", type=float, default=50.0, help="Integration time in ms (default 50)")
    ap.add_argument("--mode", type=str, default="p", choices=["s", "p"], help="Polarizer mode")
    ap.add_argument("--channel", type=str, default="a", choices=CHANNELS, help="Channel for single timing")
    ap.add_argument("--intensity", type=int, default=180, help="LED intensity (0-255) for single timing")
    ap.add_argument("--cycle-intensity", type=int, default=180, help="LED intensity for all channels in cycle")
    ap.add_argument("--repeats", type=int, default=5, help="Number of repeats for averaging")
    ap.add_argument("--settle-ms", type=float, default=30.0, help="Settle delay after LED/mode change (ms)")
    args = ap.parse_args()

    settle_s = max(0.0, args.settle_ms / 1000.0)

    # Hardware init
    usb = USB4000()
    devices = usb.discover_devices()
    if not devices:
        raise RuntimeError("No spectrometer found")
    usb.connect(devices[0])
    ok = usb.set_integration_time(args.integration_ms / 1000.0)
    if not ok:
        raise RuntimeError("Failed to set integration time")

    ctrl = PicoP4SPR()
    ctrl.turn_off_channels()

    print("\n=== Acquisition Timing ===")
    print(f"Integration: {args.integration_ms:.1f} ms  Mode: {args.mode.upper()}  Settle: {args.settle_ms:.0f} ms  Repeats: {args.repeats}")

    # Spectrometer-only
    spec_times = spectrometer_only(usb, args.repeats)
    print("\nSpectrometer acquire_spectrum():")
    print(f"  mean:   {statistics.mean(spec_times):6.2f} ms")
    print(f"  median: {statistics.median(spec_times):6.2f} ms   min: {min(spec_times):6.2f}  max: {max(spec_times):6.2f}")

    # Single-channel
    single_times: list[float] = []
    for _ in range(max(1, args.repeats)):
        t = single_channel(usb, ctrl, args.channel.lower(), args.intensity, args.mode.lower(), settle_s)
        single_times.append(t)
    print(f"\nSingle-channel ({args.channel.upper()}, intensity {args.intensity}):")
    print(f"  mean:   {statistics.mean(single_times):6.2f} ms")
    print(f"  median: {statistics.median(single_times):6.2f} ms   min: {min(single_times):6.2f}  max: {max(single_times):6.2f}")

    # Full cycle A→D
    cycle_times: list[float] = []
    for _ in range(max(1, args.repeats)):
        t = cycle_ad(usb, ctrl, args.cycle_intensity, args.mode.lower(), settle_s)
        cycle_times.append(t)
    print(f"\nFull cycle (A→D, intensity {args.cycle_intensity}):")
    print(f"  mean:   {statistics.mean(cycle_times):7.2f} ms")
    print(f"  median: {statistics.median(cycle_times):7.2f} ms   min: {min(cycle_times):7.2f}  max: {max(cycle_times):7.2f}")

    # Overheads
    spec_overhead = statistics.mean(spec_times) - args.integration_ms
    single_overhead = statistics.mean(single_times) - args.integration_ms
    print("\nApprox. overhead (beyond integration time):")
    print(f"  spectrometer-only: {spec_overhead:6.2f} ms")
    print(f"  single-channel:    {single_overhead:6.2f} ms")

    ctrl.turn_off_channels()
    try:
        usb.disconnect()
    except Exception:
        pass


if __name__ == "__main__":
    main()
