"""
Pump Timing Synchronization Calibration
=======================================

Injection-based calibration to synchronize pump timing between channel pairs.

Principle:
----------
- Inject sample with different refractive index than buffer
- Monitor sensorgram for refractive index shift
- Measure transit time from injection start to signal change
- Compare pump 1 (A+C) vs pump 2 (B+D) arrival times
- Find correction factors that sync the arrival times

Output:
-------
- CSV with transit times per channel (+ corrected values if provided)
- Recommended correction factor to sync pump pairs
"""

import time
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import contextlib

from affilabs.utils.logger import logger
from affilabs.utils.controller import PicoP4PRO
from affilabs.utils.usb4000_wrapper import USB4000
from affilabs.utils.hal.adapters import OceanSpectrometerAdapter


class PumpTimingCalibration:
    """Automated pump timing calibration for P4PROPLUS internal pumps.

    Architecture alignment:
    - Uses HAL `OceanSpectrometerAdapter` for detector to match app interfaces
    - Supports dependency injection for `ctrl` and `detector` to ease integration
    """

    def __init__(self, ctrl: Optional[PicoP4PRO] = None, detector: Optional[object] = None):
        self.ctrl: Optional[PicoP4PRO] = ctrl
        self.detector: Optional[OceanSpectrometerAdapter] = None
        if detector is not None:
            self.detector = detector if isinstance(detector, OceanSpectrometerAdapter) else OceanSpectrometerAdapter(detector)
        self.results: List[Dict] = []
        self.output_dir = Path("calibration_results")
        self.output_dir.mkdir(exist_ok=True)

    def connect_hardware(self) -> bool:
        """Connect to P4PROPLUS controller and detector."""
        print("\n" + "=" * 60)
        print("  PUMP TIMING CALIBRATION")
        print("=" * 60)
        print("\n[1/4] Connecting to hardware...")

        # Controller
        try:
            if self.ctrl is None:
                self.ctrl = PicoP4PRO()
            if not self.ctrl.valid():
                print("❌ Controller not connected")
                return False
            version = getattr(self.ctrl, "version", "unknown")
            has_pumps = True
            if hasattr(self.ctrl, "has_internal_pumps"):
                with contextlib.suppress(Exception):
                    has_pumps = bool(self.ctrl.has_internal_pumps())
            if not has_pumps:
                print(f"❌ No internal pumps (version: {version})")
                print("   P4PROPLUS V2.3+ required")
                return False
            print(f"✓ Controller: {version}")
        except Exception as e:
            print(f"❌ Controller connection failed: {e}")
            return False

        # Detector via HAL adapter
        try:
            if self.detector is None:
                usb = USB4000()
                if not usb.open():
                    print("❌ Detector not connected")
                    return False
                self.detector = OceanSpectrometerAdapter(usb)
            serial = getattr(self.detector, "serial_number", None)
            print(f"✓ Detector: {serial or 'Connected'}")
            if hasattr(self.detector, "set_integration") and self.detector.set_integration(60) is False:
                print("❌ Failed to set detector integration time")
                return False
            print("✓ Integration time: 60ms")
        except Exception as e:
            print(f"❌ Detector connection failed: {e}")
            return False

        print("\n✓ Hardware ready\n")
        return True

    def _extract_channel_signals(self, spectrum: np.ndarray) -> Dict[str, float]:
        """Extract average signal for each channel from spectrum (simple pixel windows)."""
        pixel_ranges = {
            "a": (900, 1100),
            "b": (1100, 1300),
            "c": (1300, 1500),
            "d": (1500, 1700),
        }
        signals: Dict[str, float] = {}
        for ch, (start_px, end_px) in pixel_ranges.items():
            signals[ch] = float(np.mean(spectrum[start_px:end_px]))
        return signals

    def measure_baseline(self, duration: float = 10.0, channels: List[str] = ["a", "b", "c", "d"]) -> Dict[str, float]:
        print(f"      Measuring baseline ({duration:.0f}s)...")
        vals = {ch: [] for ch in channels}
        t0 = time.time()
        while (time.time() - t0) < duration:
            try:
                spec = self.detector.read_intensity()
                sig = self._extract_channel_signals(spec)
                for ch in channels:
                    vals[ch].append(sig[ch])
                time.sleep(0.2)
            except Exception as e:
                logger.warning(f"Error reading spectrum: {e}")
                time.sleep(0.2)
        baselines = {ch: float(np.mean(v)) if v else 0.0 for ch, v in vals.items()}
        print(
            f"      Baseline: A={baselines.get('a', 0):.1f}, B={baselines.get('b', 0):.1f}, C={baselines.get('c', 0):.1f}, D={baselines.get('d', 0):.1f} counts"
        )
        return baselines

    def detect_sample_arrival(
        self,
        baseline_signals: Dict[str, float],
        detection_threshold_pct: float = 5.0,
        timeout: float = 300.0,
        channels: List[str] = ["a", "b", "c", "d"],
        start_epoch: Optional[float] = None,
    ) -> Dict[str, Optional[float]]:
        """Detect arrival time per channel using baseline deviation with hysteresis."""
        start_time = start_epoch if start_epoch is not None else time.time()
        arrival_times = {ch: None for ch in channels}
        detected = {ch: False for ch in channels}
        thresholds = {ch: abs(baseline_signals[ch]) * (detection_threshold_pct / 100.0) for ch in channels}
        consecutive = {ch: 0 for ch in channels}
        required_hits = 10

        print(f"      Monitoring for sample arrival (timeout: {int(timeout)}s)...")
        print(
            f"      Baselines: A={baseline_signals.get('a', 0):.1f}, B={baseline_signals.get('b', 0):.1f}, C={baseline_signals.get('c', 0):.1f}, D={baseline_signals.get('d', 0):.1f}"
        )

        while (time.time() - start_time) < timeout:
            if all(detected.values()):
                break
            try:
                spec = self.detector.read_intensity()
                sig = self._extract_channel_signals(spec)
                now = time.time()
                elapsed = now - start_time
                for ch in channels:
                    if detected[ch]:
                        continue
                    change = abs(sig[ch] - baseline_signals[ch])
                    if change > thresholds[ch]:
                        consecutive[ch] += 1
                        if consecutive[ch] >= required_hits:
                            detected[ch] = True
                            arrival_times[ch] = elapsed
                            pct = (change / (abs(baseline_signals[ch]) or 1.0)) * 100.0
                            print(f"      ✓ {ch.upper()}: detected at {elapsed:.1f}s ({pct:.1f}% from baseline)")
                    else:
                        consecutive[ch] = 0
                if int(elapsed) % 10 == 0 and int(elapsed) > 0:
                    undet = [c for c, d in detected.items() if not d]
                    if undet:
                        print(f"      ... {int(elapsed)}s elapsed, waiting for: {', '.join([u.upper() for u in undet])}")
                time.sleep(0.2)
            except Exception as e:
                logger.warning(f"Error reading spectrum: {e}")
                time.sleep(0.2)

        for ch in channels:
            if not detected[ch]:
                print(f"      ⚠️ {ch.upper()}: Timeout - no arrival within {int(timeout)}s")
        return arrival_times

    def _confirm_or_correct_arrivals(self, arrivals: Dict[str, Optional[float]], channels: List[str]) -> Dict[str, Optional[float]]:
        print("\n      Review auto-detected arrival times:")
        for ch in channels:
            current = arrivals.get(ch)
            if current is None:
                print(f"        {ch.upper()}: not detected")
                override = input(f"        → Enter arrival time for {ch.upper()} (s) or ENTER to skip: ").strip()
                if override:
                    try:
                        arrivals[ch] = float(override)
                        print(f"        ✓ {ch.upper()} set to {arrivals[ch]:.1f}s")
                    except ValueError:
                        print("        ⚠️ Invalid number, keeping as not detected")
            else:
                print(f"        {ch.upper()}: {current:.1f}s")
                override = input(f"        → Override {ch.upper()}? Enter seconds or ENTER to accept: ").strip()
                if override:
                    try:
                        arrivals[ch] = float(override)
                        print(f"        ✓ {ch.upper()} updated to {arrivals[ch]:.1f}s")
                    except ValueError:
                        print("        ⚠️ Invalid number, keeping autodetect")
        return arrivals

    def run_injection_test(
        self,
        pump_ch: int,
        rpm: float,
        correction: float,
        contact_time: float,
        test_num: int,
        total_tests: int,
    ) -> Dict:
        pump_name = f"Pump {pump_ch}"
        channels = ["a", "b", "c", "d"]  # Monitor ALL channels
        print(f"\n  [{test_num}/{total_tests}] {pump_name}: {rpm} RPM × {correction} correction")
        print(f"  Monitoring: ALL channels (A+B+C+D)")
        print("  " + "-" * 56)

        # Baseline
        baseline_signals = self.measure_baseline(duration=10.0, channels=channels)

        # Prepare loop and start pump (valves closed/LOAD)
        print("      Preparing loop: BOTH valves → LOAD (closed), starting purge...")
        with contextlib.suppress(Exception):
            self.ctrl.knx_six_both(state=0)
        
        # Step 1: High-speed purge to clean KC1 path (2 min @ 250 RPM)
        purge_rate = 250.0
        try:
            if not self.ctrl.pump_start(rate_ul_min=purge_rate, ch=pump_ch):
                print("      ❌ Failed to start pump for purge")
                return {
                    "pump": pump_ch,
                    "rpm_target": rpm,
                    "correction": correction,
                    "rpm_actual": 0,
                    "contact_time": contact_time,
                    "success": False,
                    "error": "Pump start failed (purge)",
                }
            print(f"      ✓ Purging KC1 path at {purge_rate:.0f} RPM for 2 min...")
            time.sleep(120.0)  # 2 minute purge
            print(f"      ✓ Purge complete")
        except Exception as e:
            print(f"      ❌ Purge error: {e}")
            return {
                "pump": pump_ch,
                "rpm_target": rpm,
                "correction": correction,
                "rpm_actual": 0,
                "contact_time": contact_time,
                "success": False,
                "error": f"Purge failed: {e}",
            }
        
        # Step 2: Slow to test rate for loop filling
        flow_rate_ul_min = rpm * correction
        try:
            if not self.ctrl.pump_start(rate_ul_min=flow_rate_ul_min, ch=pump_ch):
                print("      ❌ Failed to adjust pump to test rate")
                return {
                    "pump": pump_ch,
                    "rpm_target": rpm,
                    "correction": correction,
                    "rpm_actual": flow_rate_ul_min,
                    "contact_time": contact_time,
                    "success": False,
                    "error": "Pump rate adjust failed",
                }
            print(f"      ✓ Pump {pump_ch} at test rate {flow_rate_ul_min:.1f} RPM (loop filling)")
        except Exception as e:
            print(f"      ❌ Pump adjust error: {e}")
            return {
                "pump": pump_ch,
                "rpm_target": rpm,
                "correction": correction,
                "rpm_actual": flow_rate_ul_min,
                "contact_time": contact_time,
                "success": False,
                "error": str(e),
            }

        # Auto-load: wait for loop to fill while pump runs
        print("\n      ⏸️  Valve CLOSED (LOAD) - Filling loop with sample (pump stays ON)")
        print("      → Waiting 15 seconds for loop to fill...")
        time.sleep(15.0)

        # Open BOTH valves to INJECT to push loop content to sensor
        print("\n      Opening BOTH valves → INJECT (sample flows to all channels)")
        with contextlib.suppress(Exception):
            opened = self.ctrl.knx_six_both(state=1)
            if not opened:
                print("      ⚠️ Valve command rejected - continuing anyway")
        injection_start_time = time.time()
        print("      ✓ Injection start flagged at valve open")

        # Detect arrival
        arrival_times = self.detect_sample_arrival(
            baseline_signals=baseline_signals,
            detection_threshold_pct=5.0,
            timeout=300.0,
            channels=channels,
            start_epoch=injection_start_time,
        )

        # Close BOTH valves after contact time
        print(f"      Contact time {contact_time:.0f}s → Closing BOTH valves to LOAD")
        time.sleep(contact_time)
        with contextlib.suppress(Exception):
            self.ctrl.knx_six_both(state=0)

        # Final purge with valves OPEN to clean sensor path
        print(f"\n      Final purge: opening valves, running pump at 250 RPM for 2 min...")
        with contextlib.suppress(Exception):
            self.ctrl.knx_six_both(state=1)  # Open valves
        with contextlib.suppress(Exception):
            self.ctrl.pump_start(rate_ul_min=250.0, ch=pump_ch)
        time.sleep(120.0)  # 2 minute purge
        with contextlib.suppress(Exception):
            self.ctrl.knx_six_both(state=0)  # Close valves
        with contextlib.suppress(Exception):
            self.ctrl.pump_stop(ch=pump_ch)

        # Record result
        result = {
            "timestamp": datetime.now().isoformat(),
            "pump": pump_ch,
            "rpm_target": rpm,
            "correction": correction,
            "rpm_actual": flow_rate_ul_min,
            "contact_time": contact_time,
            "baseline_a": baseline_signals.get("a"),
            "baseline_b": baseline_signals.get("b"),
            "baseline_c": baseline_signals.get("c"),
            "baseline_d": baseline_signals.get("d"),
            "arrival_a": arrival_times.get("a"),
            "arrival_b": arrival_times.get("b"),
            "arrival_c": arrival_times.get("c"),
            "arrival_d": arrival_times.get("d"),
            "arrival_a_corrected": arrival_times.get("a"),
            "arrival_b_corrected": arrival_times.get("b"),
            "arrival_c_corrected": arrival_times.get("c"),
            "arrival_d_corrected": arrival_times.get("d"),
            "success": all(arrival_times.get(ch) is not None for ch in channels),
        }

        self.results.append(result)
        print("      ✓ Test complete\n" if result["success"] else "      ⚠️ Test complete - some channels not detected\n")

        # Wait for baseline recovery
        print("      Waiting 2 min for baseline recovery...")
        time.sleep(120.0)
        return result

    def run_calibration(self):
        print("\n[2/4] Starting calibration sequence...")
        print("      This will take approximately 20-25 minutes\n")

        rpm = 150
        correction_factors = [0.5, 1.0, 1.5]
        pumps = [1, 2]
        contact_time = 10.0  # 10 seconds per injection (single loop content)

        total_tests = len(correction_factors) * len(pumps)
        test_num = 0
        for correction in correction_factors:
            for pump in pumps:
                test_num += 1
                self.run_injection_test(
                    pump_ch=pump,
                    rpm=rpm,
                    correction=correction,
                    contact_time=contact_time,
                    test_num=test_num,
                    total_tests=total_tests,
                )

        print("\n✓ Calibration sequence complete\n")

    def analyze_results(self):
        print("\n[3/4] Analyzing results...")
        if not self.results:
            print("❌ No results to analyze")
            return

        successful = [r for r in self.results if r.get("success")]
        if not successful:
            print("❌ No successful tests")
            return

        print(f"\n  Successful tests: {len(successful)}/{len(self.results)}")
        print(f"\n  PUMP SYNCHRONIZATION ANALYSIS:")
        print("  " + "-" * 56)

        for correction in [0.5, 1.0, 1.5]:
            p1 = next((r for r in successful if r["correction"] == correction and r["pump"] == 1), None)
            p2 = next((r for r in successful if r["correction"] == correction and r["pump"] == 2), None)
            if not (p1 and p2):
                continue
            a_time = p1.get("arrival_a_corrected") or p1.get("arrival_a")
            c_time = p1.get("arrival_c_corrected") or p1.get("arrival_c")
            b_time = p2.get("arrival_b_corrected") or p2.get("arrival_b")
            d_time = p2.get("arrival_d_corrected") or p2.get("arrival_d")
            print(f"\n  Correction Factor: {correction}")
            print("    Pump 1 (A+C):")
            if a_time is not None and c_time is not None:
                avg1 = (a_time + c_time) / 2
                print(f"      A: {a_time:.1f}s, C: {c_time:.1f}s")
                print(f"      Average: {avg1:.1f}s (Δ{abs(a_time - c_time):.1f}s between A-C)")
            else:
                avg1 = None
                print(f"      A: {a_time or 'N/A'}, C: {c_time or 'N/A'}")
            print("    Pump 2 (B+D):")
            if b_time is not None and d_time is not None:
                avg2 = (b_time + d_time) / 2
                print(f"      B: {b_time:.1f}s, D: {d_time:.1f}s")
                print(f"      Average: {avg2:.1f}s (Δ{abs(b_time - d_time):.1f}s between B-D)")
            else:
                avg2 = None
                print(f"      B: {b_time or 'N/A'}, D: {d_time or 'N/A'}")
            if avg1 is not None and avg2 is not None:
                delta = abs(avg1 - avg2)
                faster = "Pump 1" if avg1 < avg2 else "Pump 2"
                print(f"\n    → Sync Delta: {delta:.1f}s ({faster} arrives first)")
                if delta < 5.0:
                    print("    ✓ GOOD SYNC (< 5s difference)")
                elif delta < 15.0:
                    print("    → MODERATE SYNC (5-15s difference)")
                else:
                    print("    ⚠️ POOR SYNC (> 15s difference)")

        # Overall recommendation
        print(f"\n  RECOMMENDATIONS:")
        print("  " + "-" * 56)
        best_sync = None
        best_delta = float("inf")
        for correction in [0.5, 1.0, 1.5]:
            p1 = next((r for r in successful if r["correction"] == correction and r["pump"] == 1), None)
            p2 = next((r for r in successful if r["correction"] == correction and r["pump"] == 2), None)
            if not (p1 and p2):
                continue
            a_time = p1.get("arrival_a_corrected") or p1.get("arrival_a")
            c_time = p1.get("arrival_c_corrected") or p1.get("arrival_c")
            b_time = p2.get("arrival_b_corrected") or p2.get("arrival_b")
            d_time = p2.get("arrival_d_corrected") or p2.get("arrival_d")
            if all(v is not None for v in [a_time, c_time, b_time, d_time]):
                avg1 = (a_time + c_time) / 2
                avg2 = (b_time + d_time) / 2
                delta = abs(avg1 - avg2)
                if delta < best_delta:
                    best_delta = delta
                    best_sync = correction
        if best_sync is not None:
            print(f"\n  ✓ Best synchronization with correction factor: {best_sync}")
            print(f"    Pump timing delta: {best_delta:.1f}s")
        else:
            print(f"\n  ⚠️ No clear recommendation - review individual results")

    def save_results(self):
        print("\n[4/4] Saving results...")
        if not self.results:
            print("❌ No results to save")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = self.output_dir / f"pump_calibration_{timestamp}.csv"
        fieldnames = [
            "timestamp",
            "pump",
            "rpm_target",
            "correction",
            "rpm_actual",
            "contact_time",
            "baseline_a",
            "baseline_b",
            "baseline_c",
            "baseline_d",
            "arrival_a",
            "arrival_b",
            "arrival_c",
            "arrival_d",
            "arrival_a_corrected",
            "arrival_b_corrected",
            "arrival_c_corrected",
            "arrival_d_corrected",
            "success",
        ]
        with open(csv_file, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(self.results)
        print(f"✓ Results saved to: {csv_file}")

        report_file = self.output_dir / f"pump_calibration_report_{timestamp}.txt"
        with open(report_file, "w") as f:
            f.write("PUMP TIMING CALIBRATION REPORT\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total tests: {len(self.results)}\n")
            f.write(f"Successful: {sum(1 for r in self.results if r.get('success'))}\n\n")
            for pump in [1, 2]:
                channels = "A+C" if pump == 1 else "B+D"
                f.write(f"\nPUMP {pump} ({channels}) RESULTS:\n")
                f.write("-" * 60 + "\n")
                pump_results = [r for r in self.results if r["pump"] == pump]
                for correction in [0.5, 1.0, 1.5]:
                    corr_results = [r for r in pump_results if r["correction"] == correction]
                    if corr_results:
                        f.write(f"\nCorrection {correction}:\n")
                        for r in corr_results:
                            if pump == 1:
                                a_time = r.get("arrival_a_corrected") or r.get("arrival_a")
                                c_time = r.get("arrival_c_corrected") or r.get("arrival_c")
                                f.write(f"  A: {a_time}s, C: {c_time}s\n")
                            else:
                                b_time = r.get("arrival_b_corrected") or r.get("arrival_b")
                                d_time = r.get("arrival_d_corrected") or r.get("arrival_d")
                                f.write(f"  B: {b_time}s, D: {d_time}s\n")
        print(f"✓ Report saved to: {report_file}")

    def cleanup(self):
        print("\n" + "=" * 60)
        print("Cleaning up...")
        if self.ctrl:
            with contextlib.suppress(Exception):
                self.ctrl.pump_stop(ch=1)
            with contextlib.suppress(Exception):
                self.ctrl.pump_stop(ch=2)
            print("✓ Pumps stopped")
        print("✓ Cleanup complete")

    def run(self):
        try:
            if not self.connect_hardware():
                print("\n❌ Hardware connection failed. Exiting.")
                return
            print("\nThis calibration will:")
            print("  • Test 2 pumps: Pump 1 (A+C), Pump 2 (B+D)")
            print("  • Test 3 correction factors: 0.5, 1.0, 1.5")
            print("  • RPM: 150 (typical flow rate)")
            print("  • Total: 6 tests with 2 min waits between injections")
            print("\nSequence per correction factor:")
            print("  1. Valve closed, you load sample while pump runs")
            print("  2. Open valve → sample flows to sensor (10s contact)")
            print("  3. Arrival auto-detect + manual correction option")
            print("  4. 2 min wait for baseline recovery")
            resp = input("\nReady to start? (yes/no): ").strip().lower()
            if resp not in ["yes", "y"]:
                print("Calibration cancelled.")
                return
            self.run_calibration()
            self.analyze_results()
            self.save_results()
            print("\n" + "=" * 60)
            print("  CALIBRATION COMPLETE")
            print("=" * 60)
            print("\nCheck the calibration_results folder for detailed data.")
        except KeyboardInterrupt:
            print("\n\n⚠️ Calibration interrupted by user")
        except Exception as e:
            logger.error(f"Calibration error: {e}", exc_info=True)
            print(f"\n❌ Error: {e}")
        finally:
            self.cleanup()


def main():
    calibration = PumpTimingCalibration()
    calibration.run()


if __name__ == "__main__":
    main()
