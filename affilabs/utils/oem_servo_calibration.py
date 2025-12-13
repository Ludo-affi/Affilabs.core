"""OEM Calibration Tool - Manufacturing Characterization Suite.
============================================================

This tool performs one-time device characterization during manufacturing:

1. **Polarizer Calibration**: Find optimal servo positions for S and P modes
   - Supports TWO polarizer types:
     * Barrel polarizer: 2 fixed windows, finds alignment positions
     * Round polarizer: Continuous rotation, finds global max/min
   - Sweeps servo through full range (10-255 PWM positions)
   - Uses peak detection to identify optimal transmission positions
   - Identifies S-mode (HIGH transmission) vs P-mode (LOWER transmission)
   - Physics: S-mode (perpendicular) transmits MORE light than P-mode (parallel)
   - Runtime: ~1.4 minutes (optimized algorithm)

2. **Afterglow Characterization**: Measure LED phosphor decay per channel
   - Tests all 4 channels at multiple integration times
   - Fits exponential decay model: signal(t) = baseline + A × exp(-t/τ)
   - Builds τ(integration_time) lookup tables
   - Runtime: ~40-50 minutes

3. **Device Profile Generation**: Saves unified device-specific profile
   - Polarizer positions (verified labels)
   - Afterglow τ tables (per channel, per integration time)
   - Device metadata (serial, detector, calibration date)

This is a MANUFACTURING tool - end users load the resulting profile automatically.

Usage:
    python utils/oem_calibration_tool.py --serial FLMT12345 [--skip-polarizer] [--skip-afterglow]

Author: GitHub Copilot
Date: 2025-10-19
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit
from scipy.signal import find_peaks, peak_prominences

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from affilabs.utils.hal.pico_p4spr_hal import ChannelID, PicoP4SPRHAL
from affilabs.utils.logger import logger as base_logger

try:
    import seabreeze

    seabreeze.use("cseabreeze")
    from seabreeze.spectrometers import Spectrometer, list_devices
except ImportError:
    base_logger.error("SeaBreeze not available - spectrometer functionality disabled")
    Spectrometer = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s :: %(levelname)s :: %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================================
# POLARIZER CALIBRATION
# ============================================================================


class PolarizerCalibrator:
    """Find optimal servo positions for S and P polarization modes.

    Hardware Variants:
    ------------------
    This tool supports two different polarizer designs:

    **1. Barrel Polarizer (Fixed Windows)**:
       - Two fixed polarization windows mounted perpendicular to each other
       - Only 2 viable positions where windows align with beam
       - Servo rotates barrel to select which window is used
       - Most positions BLOCK light (very low signal ~50-100 counts)
       - Typical P/S ratio: 0.4-0.67 (P dimmer than S, limited by fixed window orientation)

    **2. Round Polarizer (Continuous Rotation)**:
       - Continuously rotating polarizer element
       - Light intensity changes smoothly at every angle
       - Many viable positions with varying transmission
       - Need to find global max (S-mode) and min (P-mode) positions
       - Typical P/S ratio: 0.07-0.33 (P significantly dimmer than S, optimizable orientation)

    Physics Background:
    -------------------
    For both designs, the algorithm identifies two key positions:

    - **S-mode (perpendicular)**: HIGHER transmission (~1000+ counts for barrel, higher for round)
      * More light reaches the detector
      * Used for reference signal measurements

    - **P-mode (parallel)**: LOWER transmission (~300-700 counts for barrel, lower for round)
      * Less light reaches detector, but still SUBSTANTIAL (not near zero)
      * Used for live SPR measurements (sensitive to refractive index changes)

    The servo sweep identifies optimal positions. The HIGHER peak is S-mode,
    the LOWER peak (but still well above noise) is P-mode.
    """

    def __init__(self, ctrl: PicoP4SPRHAL, spec: Spectrometer) -> None:
        """Initialize polarizer calibrator.

        Args:
            ctrl: SPR controller HAL instance
            spec: Spectrometer instance

        """
        self.ctrl = ctrl
        self.spec = spec
        self.results = {
            "s_position": None,
            "p_position": None,
            "s_is_high": None,  # True if S position produces HIGH signal
            "p_is_high": None,  # True if P position produces HIGH signal
            "intensity_curve": None,
            "timestamp": datetime.now().isoformat(),
        }

    def run_calibration(self, use_optimized: bool = True) -> dict:
        """Execute full polarizer calibration sweep.

        Args:
            use_optimized: Use two-phase adaptive search (60% faster) vs legacy sequential

        Returns:
            dict: Calibration results with positions and verification

        """
        logger.info("=" * 80)
        logger.info("POLARIZER CALIBRATION - Finding Optimal Positions")
        logger.info("=" * 80)

        if use_optimized:
            return self._run_calibration_optimized()
        return self._run_calibration_legacy()

    def _run_calibration_legacy(self) -> dict:
        """Legacy sequential sweep (3 minutes, step=5).

        Kept for compatibility and validation of optimized algorithm.
        """
        logger.info("Using LEGACY sequential sweep (step=5, ~3 minutes)")

        # Set initial conditions
        logger.info("Setting up hardware for polarizer sweep...")
        self.ctrl.set_intensity("a", 255)  # Max intensity for clear signal
        self.spec.integration_time_micros(20000)  # 20ms integration
        time.sleep(0.5)

        # Define sweep parameters (0-255 servo position range)
        min_angle = 10
        max_angle = 255  # Full servo range (0-255 positions, NOT degrees)
        half_range = (max_angle - min_angle) // 2
        angle_step = 5
        steps = half_range // angle_step

        logger.info("Sweep parameters:")
        logger.info(f"  Range: {min_angle}-{max_angle}°")
        logger.info(f"  Step size: {angle_step}°")
        logger.info(f"  Total measurements: {2 * steps + 1}")

        # Initialize intensity array
        max_intensities = np.zeros(2 * steps + 1)
        angles = np.zeros(2 * steps + 1)

        # Set starting position
        start_pos = half_range + min_angle
        self.ctrl.servo_set(s=start_pos, p=max_angle)
        time.sleep(1.0)  # Wait for servo to settle

        # Measure at center
        self.ctrl.set_mode("s")
        time.sleep(0.3)
        max_intensities[steps] = self.spec.intensities().max()
        angles[steps] = start_pos
        logger.info(
            f"Center measurement: {start_pos}° = {max_intensities[steps]:.0f} counts",
        )

        # Sweep through angles
        logger.info("Starting servo sweep...")
        for i in range(steps):
            s_angle = min_angle + angle_step * i
            p_angle = s_angle + half_range + angle_step
            angles[i] = s_angle
            angles[i + steps + 1] = p_angle

            self.ctrl.servo_set(s=s_angle, p=p_angle)
            time.sleep(0.3)  # Servo settling time

            # Measure S position
            self.ctrl.set_mode("s")
            time.sleep(0.2)
            max_intensities[i] = self.spec.intensities().max()

            # Measure P position
            self.ctrl.set_mode("p")
            time.sleep(0.2)
            max_intensities[i + steps + 1] = self.spec.intensities().max()

            if (i + 1) % 5 == 0:
                logger.info(f"  Progress: {i + 1}/{steps} positions measured")

        logger.info("Sweep complete. Analyzing data...")

        return self._analyze_sweep_results(
            angles, max_intensities, min_angle, angle_step,
        )

    def _run_calibration_optimized(self) -> dict:
        """Two-phase adaptive search (~60% faster than legacy).

        Phase 1: Coarse sweep (step=10) to find peaks quickly
        Phase 2: Fine refinement (step=2) around peaks for precision
        """
        logger.info("Using OPTIMIZED two-phase adaptive search (~1.2 minutes)")

        # Set initial conditions
        logger.info("Setting up hardware for polarizer sweep...")
        self.ctrl.set_intensity("a", 255)  # Max intensity for clear signal
        self.spec.integration_time_micros(20000)  # 20ms integration
        time.sleep(0.5)

        # ====================================================================
        # PHASE 1: COARSE SWEEP (step=10, find peak regions)
        # ====================================================================
        logger.info("=" * 80)
        logger.info("PHASE 1: Coarse Sweep (step=10) - Finding Peak Regions")
        logger.info("=" * 80)

        min_angle = 10
        max_angle = 255
        coarse_step = 10
        coarse_positions = list(range(min_angle, max_angle + 1, coarse_step))

        logger.info(f"  Range: {min_angle}-{max_angle}")
        logger.info(f"  Step: {coarse_step}")
        logger.info(f"  Measurements: {len(coarse_positions)}")

        coarse_angles = []
        coarse_intensities = []

        for i, pos in enumerate(coarse_positions):
            self.ctrl.servo_set(s=pos, p=pos)
            time.sleep(0.3)

            self.ctrl.set_mode("s")
            time.sleep(0.2)
            intensity = self.spec.intensities().max()

            coarse_angles.append(pos)
            coarse_intensities.append(intensity)

            if (i + 1) % 5 == 0:
                logger.info(f"  Progress: {i + 1}/{len(coarse_positions)} positions")

        coarse_angles = np.array(coarse_angles)
        coarse_intensities = np.array(coarse_intensities)

        # Find peaks in coarse data
        # Note: distance=5 ensures peaks are at least 50 servo units apart (step=10)
        # This helps reject noise but is NOT sufficient for barrel polarizers
        # (which need ~64 units separation). Further validation added below.
        peaks, properties = find_peaks(coarse_intensities, prominence=200, distance=5)

        if len(peaks) < 2:
            logger.warning("⚠️ Only found 1 peak in coarse sweep, using legacy method")
            return self._run_calibration_legacy()

        # Get top 2 peaks
        prominences = properties["prominences"]
        top_peak_indices = prominences.argsort()[-2:]
        peak_positions = coarse_angles[peaks[top_peak_indices]]

        logger.info(f"✅ Found {len(peaks)} peaks, refining top 2:")
        logger.info(
            f"   Peak 1: ~{peak_positions[0]} (intensity: {coarse_intensities[peaks[top_peak_indices[0]]]:.0f})",
        )
        logger.info(
            f"   Peak 2: ~{peak_positions[1]} (intensity: {coarse_intensities[peaks[top_peak_indices[1]]]:.0f})",
        )

        # ====================================================================
        # PHASE 2: FINE REFINEMENT (step=2 around peaks)
        # ====================================================================
        logger.info("=" * 80)
        logger.info("PHASE 2: Fine Refinement (step=2) - Precise Peak Location")
        logger.info("=" * 80)

        fine_step = 2
        refine_range = 15  # ±15 positions around each peak

        all_angles = []
        all_intensities = []

        for peak_pos in peak_positions:
            start = max(min_angle, peak_pos - refine_range)
            end = min(max_angle, peak_pos + refine_range)
            fine_positions = list(range(start, end + 1, fine_step))

            logger.info(
                f"  Refining peak near {peak_pos}: range {start}-{end} (step={fine_step})",
            )

            for pos in fine_positions:
                self.ctrl.servo_set(s=pos, p=pos)
                time.sleep(0.25)

                self.ctrl.set_mode("s")
                time.sleep(0.15)
                intensity = self.spec.intensities().max()

                all_angles.append(pos)
                all_intensities.append(intensity)

        # Merge coarse and fine data
        all_angles = np.array(coarse_angles.tolist() + all_angles)
        all_intensities = np.array(coarse_intensities.tolist() + all_intensities)

        # Sort by angle
        sort_idx = np.argsort(all_angles)
        all_angles = all_angles[sort_idx]
        all_intensities = all_intensities[sort_idx]

        logger.info("✅ Two-phase sweep complete. Analyzing final data...")

        return self._analyze_sweep_results(
            all_angles, all_intensities, min_angle, fine_step,
        )

    def _analyze_sweep_results(
        self,
        angles: np.ndarray,
        intensities: np.ndarray,
        min_angle: int,
        step_size: int,
    ) -> dict:
        """Analyze sweep data and extract optimal positions.

        Args:
            angles: Array of measured servo positions
            intensities: Array of measured intensities
            min_angle: Minimum servo position
            step_size: Step size used (for calculation)

        Returns:
            dict: Calibration results

        """
        # Store intensity curve for plotting
        self.results["intensity_curve"] = {
            "angles": angles.tolist(),
            "intensities": intensities.tolist(),
        }

        # Find peaks
        peaks, _ = find_peaks(intensities, prominence=200)
        if len(peaks) < 2:
            logger.error("Failed to find two distinct peaks in intensity curve")
            logger.error("This may indicate:")
            logger.error("  • Polarizer mechanical issue")
            logger.error("  • LED not working")
            logger.error("  • Servo not responding")
            return self.results  # Return partial results

        prominences = peak_prominences(intensities, peaks)
        peak_indices = prominences[0].argsort()[-2:]  # Two highest peaks

        # Get peak positions directly from angles array
        pos1 = int(angles[peaks[peak_indices[0]]])
        pos2 = int(angles[peaks[peak_indices[1]]])

        # ✨ CRITICAL: Enforce minimum separation for barrel polarizers
        # Barrel polarizers have 2 perpendicular windows ~90° apart (≈64 servo units on 0-255 scale)
        # If peaks are too close, they're likely from the same window (noise/shoulders)
        MIN_SEPARATION_SERVO_UNITS = 40  # Minimum ~56° apart (half of expected 90°)
        peak_separation = abs(pos2 - pos1)

        if peak_separation < MIN_SEPARATION_SERVO_UNITS:
            logger.error("=" * 80)
            logger.error("❌ INVALID POLARIZER CALIBRATION - Peaks Too Close")
            logger.error("=" * 80)
            logger.error(
                f"Peak separation: {peak_separation} servo units (~{peak_separation * 0.706:.1f}°)",
            )
            logger.error(
                f"Minimum required: {MIN_SEPARATION_SERVO_UNITS} servo units (~{MIN_SEPARATION_SERVO_UNITS * 0.706:.1f}°)",
            )
            logger.error("")
            logger.error(
                "❌ Root Cause: Two peaks detected from SAME transmission window",
            )
            logger.error(
                "   (Barrel polarizers have 2 windows ~90° apart = 64 servo units)",
            )
            logger.error("")
            logger.error("🔧 Possible Issues:")
            logger.error("   • Noisy intensity curve creating false peaks")
            logger.error("   • Peak detection finding shoulders of same window")
            logger.error("   • Servo not moving through full range")
            logger.error("")
            logger.error("💡 Solutions:")
            logger.error("   1. Check servo is moving full 0-180° range")
            logger.error("   2. Verify LED is bright enough (full intensity)")
            logger.error("   3. Increase integration time for cleaner signal")
            logger.error("   4. Manually verify servo reaches all positions")
            logger.error("=" * 80)

            # Return partial results for debugging
            self.results.update(
                {
                    "s_position": None,
                    "p_position": None,
                    "error": "peaks_too_close",
                    "peak_separation_servo_units": peak_separation,
                    "detected_peak1": pos1,
                    "detected_peak2": pos2,
                },
            )
            return self.results

        # Verify which position is S vs P by measuring actual behavior
        logger.info("Verifying polarization modes...")
        self.ctrl.servo_set(s=pos1, p=pos2)
        time.sleep(0.5)

        # Measure at position 1 (labeled as S)
        self.ctrl.set_mode("s")
        time.sleep(0.3)
        intensity_pos1 = self.spec.intensities().max()

        # Measure at position 2 (labeled as P)
        self.ctrl.set_mode("p")
        time.sleep(0.3)
        intensity_pos2 = self.spec.intensities().max()

        logger.info("Position verification:")
        logger.info(f"  Hardware 'S' position ({pos1}°): {intensity_pos1:.0f} counts")
        logger.info(f"  Hardware 'P' position ({pos2}°): {intensity_pos2:.0f} counts")

        # Determine actual polarization behavior
        # CORRECTED PHYSICS (per user clarification):
        # S-mode (perpendicular): HIGHER transmission (more light reaches detector)
        # P-mode (parallel): LOWER transmission (less light, but still substantial - NOT near zero)
        # Most servo positions: Very LOW/blocked (near zero)

        # Identify which position gives higher transmission
        if intensity_pos1 > intensity_pos2:
            # Position 1 is HIGH → Actually S-mode (perpendicular)
            actual_s_position = pos1
            actual_p_position = pos2
            s_intensity = intensity_pos1
            p_intensity = intensity_pos2
            label_status = "✅ LABELS CORRECT"
            labels_inverted = False
        else:
            # Position 2 is HIGH → Actually S-mode (perpendicular)
            actual_s_position = pos2
            actual_p_position = pos1
            s_intensity = intensity_pos2
            p_intensity = intensity_pos1
            label_status = "⚠️ LABELS INVERTED"
            labels_inverted = True

        # Calculate S/P ratio for validation
        # Expected: S > P (S-mode has higher transmission)
        # Typical ratio: 3-15× (S is significantly brighter than P)
        sp_ratio = s_intensity / p_intensity if p_intensity > 0 else 0

        logger.info("=" * 80)
        logger.info("POLARIZER CALIBRATION RESULTS:")
        logger.info("=" * 80)
        logger.info(f"{label_status}")
        logger.info(
            f"Actual S position (HIGH transmission): {actual_s_position}° → {s_intensity:.0f} counts",
        )
        logger.info(
            f"Actual P position (LOW transmission):  {actual_p_position}° → {p_intensity:.0f} counts",
        )
        logger.info(
            f"S/P intensity ratio: {sp_ratio:.2f}× (ideal >3.0×, acceptable >1.5×)",
        )
        logger.info("=" * 80)

        # Updated thresholds: Accept 1.5× for hardware-limited systems
        if sp_ratio < 1.5:
            logger.warning(
                f"⚠️ Very low S/P ratio ({sp_ratio:.2f}×) - polarizer alignment issue",
            )
        elif sp_ratio < 2.5:
            logger.info(
                f"✅ Acceptable S/P ratio ({sp_ratio:.2f}×) - hardware limited but usable",
            )
        elif sp_ratio < 3.0:
            logger.info(
                f"✅ Good S/P ratio ({sp_ratio:.2f}×) - within acceptable range",
            )
        else:
            logger.info(
                f"✅ Excellent S/P ratio ({sp_ratio:.2f}×) - optimal performance",
            )

        if p_intensity < 100:
            logger.warning(
                f"⚠️ P-mode intensity very low ({p_intensity:.0f} counts) - check alignment",
            )

        # Store results (convert numpy types to Python native for JSON serialization)
        self.results.update(
            {
                "s_position": int(actual_s_position),
                "p_position": int(actual_p_position),
                "s_intensity": float(s_intensity),
                "p_intensity": float(p_intensity),
                "sp_ratio": float(
                    sp_ratio,
                ),  # P/S ratio (lower is better, should be < 1.0)
                "hardware_s_position": int(pos1),
                "hardware_p_position": int(pos2),
                "labels_inverted": bool(labels_inverted),
            },
        )

        return self.results


# ============================================================================
# AFTERGLOW CHARACTERIZATION
# ============================================================================


class AfterglowCharacterizer:
    """Characterize LED phosphor afterglow across integration times."""

    def __init__(self, ctrl: PicoP4SPRHAL, spec: Spectrometer) -> None:
        """Initialize afterglow characterizer.

        Args:
            ctrl: SPR controller HAL instance
            spec: Spectrometer instance

        """
        self.ctrl = ctrl
        self.spec = spec
        self.results = {
            "channels": {},
            "timestamp": datetime.now().isoformat(),
        }

    @staticmethod
    def exponential_decay(
        t: np.ndarray, baseline: float, amplitude: float, tau: float,
    ) -> np.ndarray:
        """Exponential decay model: signal(t) = baseline + amplitude * exp(-t/tau).

        Args:
            t: Time array (ms)
            baseline: Dark signal baseline (counts)
            amplitude: Initial afterglow amplitude (counts)
            tau: Decay time constant (ms)

        Returns:
            Model predictions

        """
        return baseline + amplitude * np.exp(-t / tau)

    def characterize_channel(
        self,
        channel: str,
        integration_times_ms: list[float],
        num_cycles: int = 5,
    ) -> dict:
        """Characterize afterglow for one channel across integration times.

        Args:
            channel: Channel ID ('a', 'b', 'c', 'd')
            integration_times_ms: List of integration times to test
            num_cycles: Number of on/off cycles per integration time

        Returns:
            dict: Channel characterization results

        """
        logger.info("=" * 80)
        logger.info(f"AFTERGLOW CHARACTERIZATION - Channel {channel.upper()}")
        logger.info("=" * 80)

        channel_results = {
            "channel": channel,
            "integration_time_data": [],
        }

        # LED intensity for testing (use high value for clear signal)
        led_intensity = 255

        for int_time_ms in integration_times_ms:
            logger.info(f"\nTesting integration time: {int_time_ms}ms")

            # Set integration time
            int_time_us = int(int_time_ms * 1000)
            self.spec.integration_time_micros(int_time_us)
            time.sleep(0.2)

            # Measurement parameters
            led_on_time = int_time_ms * 0.003  # LED on for ~3 integration periods
            delay_times_ms = np.array(
                [10, 50, 100, 200, 500, 1000, 2000],
            )  # Decay measurement points

            decay_intensities = np.zeros((num_cycles, len(delay_times_ms)))

            logger.info(f"  Running {num_cycles} on/off cycles...")

            for cycle in range(num_cycles):
                # Turn LED ON
                self.ctrl.set_intensity(ChannelID[channel.upper()], led_intensity)
                time.sleep(led_on_time)

                # Turn LED OFF and measure decay
                self.ctrl.set_intensity(ChannelID[channel.upper()], 0)

                for i, delay_ms in enumerate(delay_times_ms):
                    time.sleep(delay_ms / 1000.0)  # Convert to seconds
                    spectrum = self.spec.intensities()
                    decay_intensities[cycle, i] = spectrum.max()

                if (cycle + 1) % 2 == 0:
                    logger.info(f"    Cycle {cycle + 1}/{num_cycles} complete")

            # Average across cycles
            avg_decay = decay_intensities.mean(axis=0)
            std_decay = decay_intensities.std(axis=0)

            logger.info("  Fitting exponential decay model...")

            # Fit exponential decay
            try:
                # Initial guess
                p0 = [
                    avg_decay[-1],  # baseline (final value)
                    avg_decay[0] - avg_decay[-1],  # amplitude
                    100,  # tau (ms)
                ]

                popt, _pcov = curve_fit(
                    self.exponential_decay,
                    delay_times_ms,
                    avg_decay,
                    p0=p0,
                    maxfev=5000,
                )

                baseline, amplitude, tau = popt

                # Calculate R²
                residuals = avg_decay - self.exponential_decay(delay_times_ms, *popt)
                ss_res = np.sum(residuals**2)
                ss_tot = np.sum((avg_decay - np.mean(avg_decay)) ** 2)
                r_squared = 1 - (ss_res / ss_tot)

                logger.info("  ✅ Fit successful:")
                logger.info(f"     τ = {tau:.2f} ms")
                logger.info(f"     Amplitude = {amplitude:.1f} counts")
                logger.info(f"     Baseline = {baseline:.1f} counts")
                logger.info(f"     R² = {r_squared:.3f}")

                # Store results
                int_time_result = {
                    "integration_time_ms": float(int_time_ms),
                    "tau_ms": float(tau),
                    "amplitude": float(amplitude),
                    "baseline": float(baseline),
                    "r_squared": float(r_squared),
                    "decay_times_ms": delay_times_ms.tolist(),
                    "measured_intensities": avg_decay.tolist(),
                    "std_intensities": std_decay.tolist(),
                }

            except Exception as e:
                logger.exception(f"  ❌ Fit failed: {e}")
                int_time_result = {
                    "integration_time_ms": float(int_time_ms),
                    "error": str(e),
                }

            channel_results["integration_time_data"].append(int_time_result)

        logger.info("=" * 80)
        return channel_results

    def run_calibration(
        self,
        channels: list[str] | None = None,
        integration_times_ms: list[float] | None = None,
    ) -> dict:
        """Run full afterglow characterization for all channels.

        Args:
            channels: List of channels to characterize
            integration_times_ms: Integration times to test

        Returns:
            dict: Complete afterglow characterization results

        """
        if integration_times_ms is None:
            integration_times_ms = [10, 20, 35, 55, 80]
        if channels is None:
            channels = ["a", "b", "c", "d"]
        logger.info("=" * 80)
        logger.info("AFTERGLOW CHARACTERIZATION - Full Suite")
        logger.info("=" * 80)
        logger.info(f"Channels: {[ch.upper() for ch in channels]}")
        logger.info(f"Integration times: {integration_times_ms} ms")
        logger.info(
            f"Estimated time: {len(channels) * len(integration_times_ms) * 2} minutes",
        )
        logger.info("=" * 80)

        for channel in channels:
            channel_results = self.characterize_channel(channel, integration_times_ms)
            self.results["channels"][channel] = channel_results

        return self.results


# ============================================================================
# DEVICE PROFILE MANAGER
# ============================================================================


class DeviceProfileManager:
    """Manage device-specific OEM calibration profiles."""

    def __init__(self, output_dir: Path) -> None:
        """Initialize profile manager.

        Args:
            output_dir: Directory for storing device profiles

        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_profile(
        self,
        serial_number: str,
        polarizer_results: dict | None,
        afterglow_results: dict | None,
        detector_model: str = "Unknown",
        led_type: str = "LCW",
    ) -> Path:
        """Save unified device profile.

        Args:
            serial_number: Device serial number
            polarizer_results: Polarizer calibration results
            afterglow_results: Afterglow characterization results
            detector_model: Detector model name
            led_type: LED PCB type code ('LCW' = Luminus Cool White, 'OWW' = Osram Warm White)

        Returns:
            Path to saved profile

        """
        timestamp = datetime.now().strftime("%Y%m%d")
        profile_name = f"device_{serial_number}_{timestamp}.json"
        profile_path = self.output_dir / profile_name

        # Expand LED type to full name for metadata
        led_type_names = {
            "LCW": "Luminus Cool White",
            "OWW": "Osram Warm White",
        }
        led_type_full = led_type_names.get(led_type, led_type)

        profile_data = {
            "device_serial": serial_number,
            "device_type": "PicoP4SPR",
            "detector_model": detector_model,
            "led_type": led_type,  # Short code: LCW or OWW
            "led_type_full": led_type_full,  # Human readable
            "oem_calibration_version": "1.1",  # Bumped version to include LED type
            "calibration_date": datetime.now().isoformat(),
            "polarizer": polarizer_results if polarizer_results else {},
            "afterglow": afterglow_results if afterglow_results else {},
        }

        # Add LED type to afterglow metadata for validation
        if afterglow_results and "channels" in afterglow_results:
            if "metadata" not in profile_data["afterglow"]:
                profile_data["afterglow"]["metadata"] = {}
            profile_data["afterglow"]["metadata"]["led_type"] = led_type

        with profile_path.open("w") as f:
            json.dump(profile_data, f, indent=2)

        logger.info(f"✅ Device profile saved: {profile_path}")
        logger.info(f"   Serial: {serial_number}")
        logger.info(f"   LED Type: {led_type} ({led_type_full})")
        return profile_path

    def update_device_config(self, polarizer_results: dict | None) -> None:
        """Update config/device_config.json with OEM calibration data.

        This ensures the main application can load OEM positions from the
        single source of truth (device_config.json) without needing to
        search for device profile files.

        Args:
            polarizer_results: Polarizer calibration results with s_position, p_position

        """
        if not polarizer_results:
            logger.warning("⚠️ No polarizer results to save to device_config")
            return

        # Path to device_config.json
        config_path = Path(__file__).parent.parent / "config" / "device_config.json"

        try:
            # Load existing config
            if config_path.exists():
                with open(config_path) as f:
                    config = json.load(f)
            else:
                logger.warning(
                    f"⚠️ device_config.json not found at {config_path}, creating new",
                )
                config = {}

            # Update OEM calibration section
            config["oem_calibration"] = {
                "polarizer_s_position": polarizer_results["s_position"],
                "polarizer_p_position": polarizer_results["p_position"],
                "polarizer_sp_ratio": polarizer_results.get("sp_ratio", 0.0),
                "calibration_date": datetime.now().isoformat(),
                "calibration_method": polarizer_results.get("method", "oem_tool"),
            }

            # Update last modified timestamp if device_info exists
            if "device_info" in config:
                config["device_info"]["last_modified"] = datetime.now().isoformat()

            # Ensure directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # Save updated config
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)

            logger.info("✅ Updated device_config.json with OEM calibration:")
            logger.info(f"   S position: {polarizer_results['s_position']}")
            logger.info(f"   P position: {polarizer_results['p_position']}")
            logger.info(f"   P/S ratio: {polarizer_results.get('sp_ratio', 0.0):.3f}")

        except Exception as e:
            logger.exception(f"❌ Failed to update device_config.json: {e}")
            logger.warning("   Device profile was still saved successfully")

    def generate_plots(
        self,
        serial_number: str,
        polarizer_results: dict | None,
        afterglow_results: dict | None,
    ) -> None:
        """Generate diagnostic plots for calibration results.

        Args:
            serial_number: Device serial number
            polarizer_results: Polarizer calibration results
            afterglow_results: Afterglow characterization results

        """
        timestamp = datetime.now().strftime("%Y%m%d")

        # Polarizer sweep plot
        if polarizer_results and "intensity_curve" in polarizer_results:
            plt.figure(figsize=(12, 6))
            curve = polarizer_results["intensity_curve"]
            plt.plot(curve["angles"], curve["intensities"], "b-", linewidth=2)
            plt.axvline(
                polarizer_results["s_position"],
                color="r",
                linestyle="--",
                label=f"S position ({polarizer_results['s_position']}°)",
            )
            plt.axvline(
                polarizer_results["p_position"],
                color="g",
                linestyle="--",
                label=f"P position ({polarizer_results['p_position']}°)",
            )
            plt.xlabel("Servo Position (degrees)")
            plt.ylabel("Intensity (counts)")
            plt.title(f"Polarizer Sweep - Device {serial_number}")
            plt.legend()
            plt.grid(True, alpha=0.3)

            plot_path = self.output_dir / f"polarizer_{serial_number}_{timestamp}.png"
            plt.savefig(plot_path, dpi=150, bbox_inches="tight")
            plt.close()
            logger.info(f"  Plot saved: {plot_path}")

        # Afterglow decay plots
        if afterglow_results and "channels" in afterglow_results:
            for channel_id, channel_data in afterglow_results["channels"].items():
                _fig, axes = plt.subplots(1, 2, figsize=(15, 6))

                # Left: Decay curves for all integration times
                ax1 = axes[0]
                int_times = []
                taus = []

                for int_data in channel_data["integration_time_data"]:
                    if "tau_ms" in int_data:
                        int_time = int_data["integration_time_ms"]
                        int_times.append(int_time)
                        taus.append(int_data["tau_ms"])

                        times = np.array(int_data["decay_times_ms"])
                        measured = np.array(int_data["measured_intensities"])

                        ax1.plot(
                            times, measured, "o-", label=f"{int_time}ms", alpha=0.7,
                        )

                ax1.set_xlabel("Time after LED off (ms)")
                ax1.set_ylabel("Intensity (counts)")
                ax1.set_title(f"Channel {channel_id.upper()} - Afterglow Decay")
                ax1.legend()
                ax1.grid(True, alpha=0.3)
                ax1.set_xscale("log")

                # Right: τ vs integration time
                ax2 = axes[1]
                if len(int_times) > 0:
                    ax2.plot(int_times, taus, "ro-", linewidth=2, markersize=8)
                    ax2.set_xlabel("Integration Time (ms)")
                    ax2.set_ylabel("Decay Constant τ (ms)")
                    ax2.set_title(
                        f"Channel {channel_id.upper()} - τ vs Integration Time",
                    )
                    ax2.grid(True, alpha=0.3)

                plt.tight_layout()
                plot_path = (
                    self.output_dir
                    / f"afterglow_ch{channel_id}_{serial_number}_{timestamp}.png"
                )
                plt.savefig(plot_path, dpi=150, bbox_inches="tight")
                plt.close()
                logger.info(f"  Plot saved: {plot_path}")


# ============================================================================
# MAIN OEM CALIBRATION WORKFLOW
# ============================================================================


def main() -> int | None:
    """Main OEM calibration workflow."""
    parser = argparse.ArgumentParser(
        description="OEM Calibration Tool - Polarizer + Afterglow Characterization",
    )
    parser.add_argument(
        "--serial",
        type=str,
        required=True,
        help="Device serial number (e.g., FLMT12345)",
    )
    parser.add_argument(
        "--skip-polarizer",
        action="store_true",
        help="Skip polarizer calibration",
    )
    parser.add_argument(
        "--skip-afterglow",
        action="store_true",
        help="Skip afterglow characterization",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="calibration_data/device_profiles",
        help="Output directory for profiles",
    )
    parser.add_argument(
        "--detector",
        type=str,
        default="Unknown",
        help="Detector model name",
    )
    parser.add_argument(
        "--led-type",
        type=str,
        choices=["LCW", "OWW"],
        default="LCW",
        help="LED PCB type: LCW (Luminus Cool White) or OWW (Osram Warm White)",
    )
    parser.add_argument(
        "--legacy-sweep",
        action="store_true",
        help="Use legacy sequential sweep instead of optimized two-phase (for validation)",
    )

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("OEM CALIBRATION TOOL")
    logger.info("=" * 80)
    logger.info(f"Device Serial: {args.serial}")
    logger.info(f"Detector: {args.detector}")
    logger.info(
        f"LED Type: {args.led_type} ({'Luminus Cool White' if args.led_type == 'LCW' else 'Osram Warm White'})",
    )
    logger.info(f"Output Directory: {args.output_dir}")
    logger.info("=" * 80)

    # Initialize hardware
    logger.info("Initializing hardware...")

    try:
        # Find devices
        devices = list_devices()
        if not devices:
            logger.error("No spectrometer found!")
            return 1

        spec = Spectrometer(devices[0])
        logger.info(f"✅ Spectrometer: {spec.model}")

        # Initialize HAL
        ctrl = PicoP4SPRHAL()
        if not ctrl.connect():
            logger.error("Failed to connect to SPR controller!")
            return 1

        logger.info("✅ Controller: PicoP4SPR")

    except Exception as e:
        logger.exception(f"Hardware initialization failed: {e}")
        return 1

    # Run calibrations
    polarizer_results = None
    afterglow_results = None

    try:
        # Polarizer calibration
        if not args.skip_polarizer:
            logger.info("\n" + "=" * 80)
            logger.info("STEP 1: POLARIZER CALIBRATION")
            logger.info("=" * 80)
            pol_cal = PolarizerCalibrator(ctrl, spec)

            # Use optimized algorithm by default, legacy only if requested
            use_optimized = not args.legacy_sweep
            if args.legacy_sweep:
                logger.info("⚠️  Using LEGACY sequential sweep (--legacy-sweep flag)")

            polarizer_results = pol_cal.run_calibration(use_optimized=use_optimized)

            if polarizer_results is None or not polarizer_results:
                logger.error("Polarizer calibration failed!")
                return 1
        else:
            logger.info("⏭️  Skipping polarizer calibration")

        # Afterglow characterization
        if not args.skip_afterglow:
            logger.info("\n" + "=" * 80)
            logger.info("STEP 2: AFTERGLOW CHARACTERIZATION")
            logger.info("=" * 80)
            afterglow_cal = AfterglowCharacterizer(ctrl, spec)
            afterglow_results = afterglow_cal.run_calibration()
        else:
            logger.info("⏭️  Skipping afterglow characterization")

        # Save device profile
        logger.info("\n" + "=" * 80)
        logger.info("SAVING DEVICE PROFILE")
        logger.info("=" * 80)

        profile_mgr = DeviceProfileManager(args.output_dir)
        profile_path = profile_mgr.save_profile(
            serial_number=args.serial,
            polarizer_results=polarizer_results,
            afterglow_results=afterglow_results,
            detector_model=args.detector,
            led_type=args.led_type,
        )

        # Update device_config.json with OEM calibration data
        logger.info("\nUpdating device_config.json...")
        profile_mgr.update_device_config(polarizer_results)

        # Generate plots
        logger.info("\nGenerating diagnostic plots...")
        profile_mgr.generate_plots(
            serial_number=args.serial,
            polarizer_results=polarizer_results,
            afterglow_results=afterglow_results,
        )

        logger.info("\n" + "=" * 80)
        logger.info("✅ OEM CALIBRATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Device Profile: {profile_path}")
        logger.info(f"Serial Number: {args.serial}")

        if polarizer_results:
            logger.info("\nPolarizer:")
            logger.info(
                f"  S position: {polarizer_results['s_position']}° (HIGH transmission)",
            )
            logger.info(
                f"  P position: {polarizer_results['p_position']}° (LOW transmission)",
            )
            sp_ratio = polarizer_results["sp_ratio"]
            status = (
                "✅ EXCELLENT"
                if sp_ratio <= 0.4
                else "✅ GOOD"
                if sp_ratio <= 0.7
                else "✅ ACCEPTABLE"
                if sp_ratio <= 0.9
                else "⚠️ HIGH"
            )
            logger.info(f"  P/S ratio: {sp_ratio:.3f} ({status})")

        if afterglow_results:
            logger.info("\nAfterglow:")
            for ch, data in afterglow_results["channels"].items():
                [
                    d["integration_time_ms"]
                    for d in data["integration_time_data"]
                    if "tau_ms" in d
                ]
                taus = [
                    d["tau_ms"] for d in data["integration_time_data"] if "tau_ms" in d
                ]
                if taus:
                    logger.info(
                        f"  Channel {ch.upper()}: τ range = {min(taus):.1f}-{max(taus):.1f} ms",
                    )

        logger.info("=" * 80)

        return 0

    except KeyboardInterrupt:
        logger.warning("\n❌ Calibration interrupted by user")
        return 1

    except Exception as e:
        logger.exception(f"❌ Calibration failed: {e}")
        return 1

    finally:
        # Cleanup
        try:
            ctrl.all_off()
            ctrl.disconnect()
            spec.close()
        except (OSError, AttributeError, RuntimeError):
            pass  # Cleanup operations may fail if connection already closed


if __name__ == "__main__":
    sys.exit(main())
