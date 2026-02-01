"""Parse calibration logs to extract ML training data.

Extracts iteration-by-iteration data from convergence logs for:
- Sensitivity classification
- LED prediction
- Convergence outcome prediction
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import pandas as pd


@dataclass
class IterationData:
    """Single iteration measurement."""
    log_file: str
    timestamp: str
    polarization: str  # 's' or 'p'
    iteration: int
    max_iterations: int
    integration_ms: float

    # Per-channel data
    channel: str
    led: int
    counts: int
    target_counts: float
    fraction_of_target: float
    saturated: bool
    saturation_pixels: int

    # Convergence state
    phase: str  # PHASE-1, PHASE-2, PHASE-3
    locked: bool
    error_counts: float
    num_channels_locked: int
    total_channels: int

    # NEW: Enhanced ML features
    total_error: Optional[float] = None  # Iteration-level total error
    avg_error_pct: Optional[float] = None  # Average error percentage
    led_decision_reason: Optional[str] = None  # Why LED was changed
    led_decision_confidence: Optional[str] = None  # Decision confidence
    model_expected_counts: Optional[float] = None  # Model prediction
    model_error: Optional[float] = None  # Prediction error


@dataclass
class CalibrationRun:
    """Complete calibration run summary."""
    log_file: str
    timestamp: str
    success: bool

    # Device identity
    detector_serial: int

    # Initial conditions
    initial_leds: Dict[str, int]
    initial_integration_ms: float
    target_percent: float

    # Final results
    final_leds_s: Dict[str, int]
    final_leds_p: Dict[str, int]
    final_integration_s: float
    final_integration_p: float

    # Final quality metrics (from calibration_results JSONs)
    final_fwhm_avg: Optional[float] = None
    final_fwhm_std: Optional[float] = None
    final_snr_avg: Optional[float] = None
    final_dip_depth_avg: Optional[float] = None
    num_warnings: int = 0
    overall_quality: Optional[str] = None  # 'excellent', 'good', 'poor'

    # Temporal convergence features
    led_convergence_rate_s: Optional[float] = None  # LED change per iteration
    led_convergence_rate_p: Optional[float] = None
    signal_stability_s: Optional[float] = None  # Variance in target fraction
    signal_stability_p: Optional[float] = None
    oscillation_detected_s: bool = False  # LED bouncing pattern
    oscillation_detected_p: bool = False
    phase1_iterations: int = 0
    phase2_iterations: int = 0
    phase3_iterations: int = 0

    # Convergence metrics
    total_iterations_s: int = 0
    total_iterations_p: int = 0
    converged_s: bool = False
    converged_p: bool = False

    # Device characteristics (if available)
    model_slopes: Dict[str, float] = None
    sensitivity_label: str = "BASELINE"  # 'HIGH', 'BASELINE'


class CalibrationLogParser:
    """Parse calibration log files to extract training data."""

    # Regex patterns
    ITERATION_PATTERN = r'--- Iteration (\d+)/(\d+) @ ([\d.]+)ms ---'
    CHANNEL_PATTERN = r'([A-D]): LED=\s*(\d+)\s+(\d+) counts \(\s*([\d.]+)% of target\)'
    SATURATION_PATTERN = r'\[SAT=(\d+)px\]'
    PHASE_PATTERN = r'PHASE-([123]):'
    LOCKED_PATTERN = r'Locked channels.*?: ([A-D@, ]+)'
    TIMESTAMP_PATTERN = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'
    POLARIZATION_PATTERN = r'Step \d/\d: ([SP])-mode'

    # NEW PATTERNS for enhanced ML training
    DEVICE_SERIAL_PATTERN = r'DEVICE_SERIAL:\s*(\d+)'
    ITERATION_METRICS_PATTERN = r'ITERATION_METRICS: total_error=([\d.]+), avg_error_pct=([\d.]+)%, locked=(\d+)/(\d+)'
    LED_DECISION_PATTERN = r'LED_DECISION: ([A-D]) (\d+)→(\d+) \(reason=([^,]+), .*confidence=(\w+)\)'
    MODEL_PRED_PATTERN = r'MODEL_PRED: ([A-D]) expected_counts=([\d.]+), current=([\d.]+), target=([\d.]+)'
    PHASE_CHANGE_PATTERN = r'PHASE_CHANGE: (PHASE-\d+)→(PHASE-\d+) \(reason=([^,]+), locked=(\d+)/(\d+)\)'

    def __init__(self, logs_dir: Path):
        self.logs_dir = Path(logs_dir)

    def parse_all_logs(self, max_logs: int = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Parse calibration logs quickly (optimized).
        
        Args:
            max_logs: Max recent logs to parse (None = all). Recommended: 100
        
        Returns:
            Tuple of (iteration_data, calibration_runs) DataFrames
        """
        import time

        all_logs = list(self.logs_dir.glob("calibration_*.log"))
        log_files = sorted(all_logs, key=lambda f: f.stat().st_mtime, reverse=True)

        if max_logs and len(log_files) > max_logs:
            log_files = log_files[:max_logs]
            print(f"Processing {max_logs} most recent logs (out of {len(all_logs)} total)")
        else:
            print(f"Found {len(log_files)} calibration log files")

        # Quick filter - skip large files
        valid_files = []
        for log_file in log_files:
            file_size_mb = log_file.stat().st_size / (1024 * 1024)
            if file_size_mb <= 0.5:  # Skip files > 0.5MB
                valid_files.append(log_file)

        print(f"Parsing {len(valid_files)} valid files (skipped {len(log_files) - len(valid_files)} large files)...")

        start_time = time.time()
        iteration_records = []
        run_records = []

        for i, log_file in enumerate(valid_files, 1):
            file_start = time.time()
            print(f"  [{i}/{len(valid_files)}] {log_file.name}...", end='', flush=True)

            try:
                import threading
                result = [None]
                error = [None]

                def parse_with_timeout():
                    try:
                        result[0] = self.parse_log(log_file)
                    except Exception as e:
                        error[0] = e

                thread = threading.Thread(target=parse_with_timeout)
                thread.daemon = True
                thread.start()
                thread.join(timeout=10.0)  # 10 second timeout

                if thread.is_alive():
                    print(" TIMEOUT (>10s) - SKIPPED")
                    continue

                if error[0]:
                    print(f" ERROR: {error[0]}")
                    continue

                if result[0]:
                    iterations, run_summary = result[0]
                    iteration_records.extend(iterations)
                    if run_summary:
                        run_records.append(run_summary)

                file_time = time.time() - file_start
                if file_time > 2:
                    print(f" {file_time:.1f}s (SLOW)")
                else:
                    print(f" {file_time:.2f}s")
            except Exception as e:
                print(f" ERROR: {e}")
                continue

        elapsed = time.time() - start_time
        print(f"Extracted {len(iteration_records)} iteration records from {len(run_records)} runs in {elapsed:.1f}s")

        # Convert to DataFrames
        iterations_df = pd.DataFrame([asdict(r) for r in iteration_records])
        runs_df = pd.DataFrame([asdict(r) for r in run_records])

        return iterations_df, runs_df

    def parse_log(self, log_file: Path) -> Tuple[List[IterationData], Optional[CalibrationRun]]:
        """Parse a single calibration log file (optimized).
        
        Returns:
            Tuple of (iteration_records, run_summary)
        """
        # Read with line limit to avoid huge files
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = []
            for i, line in enumerate(f):
                if i > 2000:  # Cap at 2000 lines to prevent slow parsing
                    break
                lines.append(line.rstrip('\n'))

        # Extract basic info
        timestamp = self._extract_timestamp(lines)

        # Parse iterations
        iterations = self._parse_iterations(log_file.name, timestamp, lines)

        # Create run summary
        run_summary = self._create_run_summary(log_file.name, timestamp, lines, iterations)

        return iterations, run_summary

    def _extract_timestamp(self, lines: List[str]) -> str:
        """Extract timestamp from log."""
        for line in lines[:10]:
            match = re.search(self.TIMESTAMP_PATTERN, line)
            if match:
                return match.group(1)
        return ""

    def _calculate_temporal_features(self, iterations: List[IterationData]) -> Tuple[Optional[float], Optional[float], bool, Dict[str, int]]:
        """Calculate temporal convergence features from iteration sequence.
        
        Returns:
            (led_convergence_rate, signal_stability, oscillation_detected, phase_counts)
        """
        if not iterations:
            return None, None, False, {}

        # Group by channel
        channels = {}
        for it in iterations:
            if it.channel not in channels:
                channels[it.channel] = []
            channels[it.channel].append(it)

        # Calculate LED convergence rate (mean absolute change per iteration)
        led_changes = []
        oscillations = []
        for ch, iters in channels.items():
            iters = sorted(iters, key=lambda x: x.iteration)
            for i in range(1, len(iters)):
                led_change = abs(iters[i].led - iters[i-1].led)
                led_changes.append(led_change)

                # Detect oscillation (direction reversal)
                if i >= 2:
                    prev_change = iters[i-1].led - iters[i-2].led
                    curr_change = iters[i].led - iters[i-1].led
                    if prev_change * curr_change < 0:  # Sign change
                        oscillations.append(True)

        led_conv_rate = sum(led_changes) / len(led_changes) if led_changes else None
        oscillation_detected = len(oscillations) >= 2  # Multiple direction changes

        # Calculate signal stability (variance in fraction_of_target)
        fractions = [it.fraction_of_target for it in iterations]
        if len(fractions) > 1:
            mean_frac = sum(fractions) / len(fractions)
            variance = sum((f - mean_frac) ** 2 for f in fractions) / len(fractions)
            signal_stability = variance ** 0.5  # Std dev
        else:
            signal_stability = None

        # Count iterations per phase
        phase_counts = {}
        for it in iterations:
            phase_counts[it.phase] = phase_counts.get(it.phase, 0) + 1

        return led_conv_rate, signal_stability, oscillation_detected, phase_counts

    def _load_quality_metrics(self, timestamp: str) -> Dict:
        """Load quality metrics from calibration_results JSON."""
        # Convert log timestamp to calibration result filename
        # timestamp format: 2025-12-19 23:19:55
        try:
            # Try multiple filename patterns
            json_dir = Path("calibration_results")
            if not json_dir.exists():
                return {}

            # Find matching JSON by timestamp
            ts_parts = timestamp.split()[0].replace('-', '') + '_' + timestamp.split()[1].replace(':', '')[:6]

            matching_files = list(json_dir.glob(f"calibration_*{ts_parts[:8]}*.json"))
            if not matching_files:
                return {}

            # Find closest match by time
            target_time = timestamp.split()[1].replace(':', '')[:6]
            best_match = None
            min_diff = float('inf')

            for f in matching_files:
                # Extract time from filename: calibration_YYYYMMDD_HHMMSS.json
                fname_time = f.stem.split('_')[-1][:6]
                try:
                    time_diff = abs(int(fname_time) - int(target_time))
                    if time_diff < min_diff:
                        min_diff = time_diff
                        best_match = f
                except:
                    continue

            if not best_match:
                return {}

            # Load and parse JSON
            with open(best_match, 'r') as f:
                data = json.load(f)

            # Extract quality metrics
            metrics = {
                'detector_serial': data.get('calibration_metadata', {}).get('detector_serial', 65535)
            }

            qc_results = data.get('qc_results', {})
            if qc_results:
                fwhms = [ch.get('fwhm', 0) for ch in qc_results.values() if isinstance(ch, dict)]
                snrs = [ch.get('snr', 0) for ch in qc_results.values() if isinstance(ch, dict)]
                dip_depths = [ch.get('dip_depth', 0) for ch in qc_results.values() if isinstance(ch, dict)]

                if fwhms:
                    metrics['fwhm_avg'] = sum(fwhms) / len(fwhms)
                    metrics['fwhm_std'] = (sum((f - metrics['fwhm_avg']) ** 2 for f in fwhms) / len(fwhms)) ** 0.5
                if snrs:
                    metrics['snr_avg'] = sum(snrs) / len(snrs)
                if dip_depths:
                    metrics['dip_depth_avg'] = sum(dip_depths) / len(dip_depths)

                # Count warnings
                total_warnings = 0
                quality_labels = []
                for ch_data in qc_results.values():
                    if isinstance(ch_data, dict):
                        warnings = ch_data.get('warnings', [])
                        total_warnings += len(warnings)
                        quality_labels.append(ch_data.get('fwhm_quality', 'unknown'))

                metrics['num_warnings'] = total_warnings

                # Overall quality (worst of all channels)
                if 'poor' in quality_labels:
                    metrics['quality'] = 'poor'
                elif 'good' in quality_labels:
                    metrics['quality'] = 'good'
                elif 'excellent' in quality_labels:
                    metrics['quality'] = 'excellent'

            return metrics

        except Exception:
            # Silently fail - quality metrics optional
            return {}

    def _parse_iterations(self, log_file: str, timestamp: str, lines: List[str]) -> List[IterationData]:
        """Parse iteration data from log lines."""
        iterations = []

        current_polarization = None
        current_iteration = None
        max_iterations = None
        current_integration = None
        current_phase = "PHASE-1"
        locked_channels = set()

        i = 0
        while i < len(lines):
            line = lines[i]

            # Skip very long lines immediately (they're usually debug output)
            if len(line) > 500:
                i += 1
                continue

            # Detect polarization mode - SIMPLE STRING MATCHING (no regex)
            if 'S-mode' in line or 's-mode' in line:
                current_polarization = 's'
            elif 'P-mode' in line or 'p-mode' in line:
                current_polarization = 'p'

            # Detect iteration header - SIMPLE PARSING (no regex, faster!)
            # Pattern: "--- Iteration 5/30 @ 10.0ms ---"
            iter_match = None
            if '--- Iteration' in line and '@' in line and 'ms ---' in line:
                try:
                    parts = line.split('Iteration')[1].split('@')
                    iter_part = parts[0].strip().split('/')
                    ms_part = parts[1].split('ms')[0].strip()
                    current_iteration = int(iter_part[0])
                    max_iterations = int(iter_part[1])
                    current_integration = float(ms_part)
                    iter_match = True
                except:
                    iter_match = False

            if iter_match:
                # Parse channel data in next lines
                i += 1
                while i < len(lines):
                    ch_line = lines[i]

                    # Skip very long lines
                    if len(ch_line) > 500:
                        i += 1
                        continue

                    # Check for phase change - SIMPLE STRING MATCHING
                    if 'PHASE-1:' in ch_line:
                        current_phase = 'PHASE-1'
                    elif 'PHASE-2:' in ch_line:
                        current_phase = 'PHASE-2'
                    elif 'PHASE-3:' in ch_line:
                        current_phase = 'PHASE-3'

                    # Check for locked channels - SIMPLE STRING PARSING
                    if 'Locked channels' in ch_line and ':' in ch_line:
                        try:
                            locked_str = ch_line.split(':')[-1]
                            locked_channels = set(ch.strip().lower() for ch in locked_str.split(',') if '@' in ch)
                        except:
                            pass

                    # Parse channel measurement - USE REGEX (THIS IS THE CRITICAL ONE)
                    # Pattern: "A: LED= 128  45000 counts ( 90.5% of target)"
                    ch_match = None
                    if ': LED=' in ch_line and 'counts' in ch_line:
                        try:
                            ch_match = re.search(self.CHANNEL_PATTERN, ch_line)
                        except:
                            ch_match = None

                    if ch_match:
                        channel = ch_match.group(1).lower()
                        led = int(ch_match.group(2))
                        counts = int(ch_match.group(3))
                        fraction = float(ch_match.group(4)) / 100.0

                        # Check for saturation - SIMPLE REGEX WITH PRE-CHECK
                        saturated = False
                        sat_pixels = 0
                        if '[SAT=' in ch_line:
                            try:
                                sat_match = re.search(self.SATURATION_PATTERN, ch_line)
                                if sat_match:
                                    saturated = True
                                    sat_pixels = int(sat_match.group(1))
                            except:
                                pass

                        # Estimate target counts (counts / fraction)
                        target_counts = counts / fraction if fraction > 0 else 50000
                        error_counts = abs(counts - target_counts)

                        iterations.append(IterationData(
                            log_file=log_file,
                            timestamp=timestamp,
                            polarization=current_polarization or 's',
                            iteration=current_iteration,
                            max_iterations=max_iterations,
                            integration_ms=current_integration,
                            channel=channel,
                            led=led,
                            counts=counts,
                            target_counts=target_counts,
                            fraction_of_target=fraction,
                            saturated=saturated,
                            saturation_pixels=sat_pixels,
                            phase=current_phase,
                            locked=(channel in locked_channels),
                            error_counts=error_counts,
                            num_channels_locked=len(locked_channels),
                            total_channels=4,
                        ))

                    # Stop at next iteration or end of section - SIMPLE STRING CHECK
                    if '--- Iteration' in ch_line or '===' in ch_line:
                        i -= 1  # Back up to reprocess
                        break

                    i += 1
                continue

            i += 1

        return iterations

    def _create_run_summary(self, log_file: str, timestamp: str,
                           lines: List[str], iterations: List[IterationData]) -> Optional[CalibrationRun]:
        """Create calibration run summary."""
        if not iterations:
            return None

        # Separate S and P mode iterations
        s_iters = [it for it in iterations if it.polarization == 's']
        p_iters = [it for it in iterations if it.polarization == 'p']

        # Extract initial and final LEDs
        initial_leds = {}
        final_leds_s = {}
        final_leds_p = {}

        if s_iters:
            # Initial from first S-mode iteration
            for it in s_iters:
                if it.iteration == 1:
                    initial_leds[it.channel] = it.led

            # Final from last S-mode iteration
            last_s_iter = max(it.iteration for it in s_iters)
            for it in s_iters:
                if it.iteration == last_s_iter:
                    final_leds_s[it.channel] = it.led

        if p_iters:
            last_p_iter = max(it.iteration for it in p_iters)
            for it in p_iters:
                if it.iteration == last_p_iter:
                    final_leds_p[it.channel] = it.led

        # Determine convergence
        converged_s = False
        converged_p = False

        if s_iters:
            last_s_fracs = [it.fraction_of_target for it in s_iters if it.iteration == max(it.iteration for it in s_iters)]
            converged_s = all(0.95 <= f <= 1.05 for f in last_s_fracs)

        if p_iters:
            last_p_fracs = [it.fraction_of_target for it in p_iters if it.iteration == max(it.iteration for it in p_iters)]
            converged_p = all(0.95 <= f <= 1.05 for f in last_p_fracs)

        # Calculate temporal features
        led_conv_rate_s, signal_stab_s, osc_s, phase_counts = self._calculate_temporal_features(s_iters)
        led_conv_rate_p, signal_stab_p, osc_p, _ = self._calculate_temporal_features(p_iters)

        # Load quality metrics from JSON
        quality_metrics = self._load_quality_metrics(timestamp)

        # Detect sensitivity (high if saturation occurred in early iterations)
        early_saturation = any(it.saturated for it in iterations if it.iteration <= 3)
        sensitivity_label = "HIGH" if early_saturation else "BASELINE"

        return CalibrationRun(
            log_file=log_file,
            timestamp=timestamp,
            success=converged_s and (converged_p or len(p_iters) == 0),
            detector_serial=quality_metrics.get('detector_serial', 65535),
            initial_leds=initial_leds,
            initial_integration_ms=s_iters[0].integration_ms if s_iters else 0.0,
            target_percent=0.85,  # Assumed default
            final_leds_s=final_leds_s,
            final_leds_p=final_leds_p,
            final_integration_s=s_iters[-1].integration_ms if s_iters else 0.0,
            final_integration_p=p_iters[-1].integration_ms if p_iters else 0.0,
            # Quality metrics
            final_fwhm_avg=quality_metrics.get('fwhm_avg'),
            final_fwhm_std=quality_metrics.get('fwhm_std'),
            final_snr_avg=quality_metrics.get('snr_avg'),
            final_dip_depth_avg=quality_metrics.get('dip_depth_avg'),
            num_warnings=quality_metrics.get('num_warnings', 0),
            overall_quality=quality_metrics.get('quality'),
            # Temporal features
            led_convergence_rate_s=led_conv_rate_s,
            led_convergence_rate_p=led_conv_rate_p,
            signal_stability_s=signal_stab_s,
            signal_stability_p=signal_stab_p,
            oscillation_detected_s=osc_s,
            oscillation_detected_p=osc_p,
            phase1_iterations=phase_counts.get('PHASE-1', 0),
            phase2_iterations=phase_counts.get('PHASE-2', 0),
            phase3_iterations=phase_counts.get('PHASE-3', 0),
            # Legacy fields
            total_iterations_s=max((it.iteration for it in s_iters), default=0),
            total_iterations_p=max((it.iteration for it in p_iters), default=0),
            converged_s=converged_s,
            converged_p=converged_p,
            model_slopes={},
            sensitivity_label=sensitivity_label,
        )


def main():
    """Test log parsing."""
    import sys

    logs_dir = Path("logs")
    if not logs_dir.exists():
        print(f"Error: {logs_dir} not found")
        sys.exit(1)

    parser = CalibrationLogParser(logs_dir)
    iterations_df, runs_df = parser.parse_all_logs()

    print("\n=== Iteration Data ===")
    print(f"Shape: {iterations_df.shape}")
    print(iterations_df.head(10))

    print("\n=== Calibration Runs ===")
    print(f"Shape: {runs_df.shape}")
    print(runs_df.head(5))

    # Save to CSV
    output_dir = Path("tools/ml_training/data")
    output_dir.mkdir(parents=True, exist_ok=True)

    iterations_df.to_csv(output_dir / "iterations.csv", index=False)
    runs_df.to_csv(output_dir / "calibration_runs.csv", index=False)

    print(f"\nSaved to {output_dir}/")
    print(f"  iterations.csv: {len(iterations_df)} rows")
    print(f"  calibration_runs.csv: {len(runs_df)} rows")


if __name__ == "__main__":
    main()
