"""Compression Training Module — Guided sensor installation for new users.

This module provides a state-machine-driven training flow that educates
first-time users through proper sensor chip compression.  It evaluates
live spectrometer signals in real time and provides step-by-step guidance.

The method was developed using the standalone labeller tool
(``standalone_tools/compression_labeller.py``) to study how the SPR signal
behaves under different compression states.  The thresholds and scoring
weights below encode what we learned from that research.

**Device / sensor agnostic** — works with any spectrometer and controller
combination.  All thresholds, channel counts, wavelength ranges, and
scoring parameters live in ``StageThresholds``.  Nothing is hardcoded.

Training stages:
    1. DRY_CONTACT — Place chip and hand-tighten (spectrum appears)
    2. INITIAL_COMPRESSION — Begin compressing (SPR dip forms)
    3. FINE_TUNING — Dial in optimal compression (dip sharpens, SNR climbs)
    4. LEAK_CHECK — Hold steady for N s to verify seal stability
    5. PASSED / FAILED — Final verdict with score

Integration points:
    - ``UserProfileManager.record_compression_training()`` — stores result
    - ``UserProfileManager.needs_compression_training()`` — gate check
    - ``SimpleAcquisitionManager.spectrum_ready`` — feed live spectra in

Threshold values below are **PLACEHOLDERS** (marked with 🏷️).
They will be calibrated from labelled data captured with the
compression labeller.

No Qt dependency — pure Python + numpy.  Can be tested headlessly.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# TRAINING STAGES
# ═══════════════════════════════════════════════════════════════════════════════


class CompressionStage(Enum):
    """State machine stages for compression training."""

    IDLE = auto()               # Not started — waiting for user to begin
    DRY_CONTACT = auto()        # Stage 1: chip placed, no compression yet
    INITIAL_COMPRESSION = auto()  # Stage 2: user begins pressing knob
    FINE_TUNING = auto()        # Stage 3: dialling in optimal compression
    LEAK_CHECK = auto()         # Stage 4: hold steady 10 s for leak test
    PASSED = auto()             # Training complete — sensor ready
    FAILED = auto()             # Training failed — user should retry


STAGE_INSTRUCTIONS: dict[CompressionStage, str] = {
    CompressionStage.IDLE: (
        "Place the sensor chip into the flow cell and close the lid.\n"
        "Press 'Start Training' when ready."
    ),
    CompressionStage.DRY_CONTACT: (
        "Good — a spectrum is visible.\n"
        "Now gently begin turning the compression knob clockwise.\n"
        "Watch the SPR dip form in the transmission spectrum."
    ),
    CompressionStage.INITIAL_COMPRESSION: (
        "SPR dip detected!\n"
        "Continue tightening slowly — quarter-turn at a time.\n"
        "The dip should sharpen and deepen.  Stop if it starts widening."
    ),
    CompressionStage.FINE_TUNING: (
        "Nearly there — fine-tune compression.\n"
        "Aim for the sharpest, deepest dip across all channels.\n"
        "Small adjustments only — 1/8 turn max."
    ),
    CompressionStage.LEAK_CHECK: (
        "Compression looks good!\n"
        "Hold steady for 10 seconds while the system checks for leaks.\n"
        "Do NOT touch the knob."
    ),
    CompressionStage.PASSED: (
        "✅ Compression training PASSED.\n"
        "The sensor is properly installed.  You may begin experiments."
    ),
    CompressionStage.FAILED: (
        "❌ Compression training FAILED.\n"
        "Remove the chip, inspect the o-ring, and try again."
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# SIGNAL SNAPSHOT  — one measurement from all channels at one instant
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class CompressionSignalSnapshot:
    """Signal quality metrics extracted from a single live spectrum.

    Created by ``CompressionTrainer.evaluate_spectrum()`` from each incoming
    spectrum_ready dict.
    """

    channel: str                    # 'a', 'b', 'c', 'd'
    timestamp: float                # time.time()

    # Raw spectrum stats
    mean_intensity: float           # mean counts (raw, before transmission)
    max_intensity: float            # peak count value
    min_intensity: float            # minimum count value
    saturation_fraction: float      # fraction of pixels near max counts

    # Transmission dip metrics (SPR-specific)
    has_dip: bool                   # True if a clear dip was found
    dip_wavelength: float | None    # nm — where the dip center is
    dip_depth: float | None         # fractional depth of the dip (0–1)
    dip_fwhm: float | None          # nm — full width at half max of dip
    dip_asymmetry: float | None     # ratio of left/right half-widths

    # Noise / stability
    snr: float                      # signal-to-noise ratio of the dip region
    baseline_std: float             # std of the transmission outside the dip
    baseline_mean: float            # mean transmission outside the dip

    # Overall quality score (0–100) for this single snapshot
    quality_score: float


@dataclass
class ChannelTrainingState:
    """Per-channel tracking during training."""

    snapshots: list[CompressionSignalSnapshot] = field(default_factory=list)
    best_snr: float = 0.0
    best_dip_depth: float = 0.0
    stage_passed: dict[str, bool] = field(default_factory=dict)
    first_dip_time: float | None = None


@dataclass
class TrainingResult:
    """Final result of compression training."""

    passed: bool
    overall_score: float            # 0–100
    per_channel_scores: dict[str, float]   # {'a': 85.2, 'b': 91.0, ...}
    per_channel_passed: dict[str, bool]    # {'a': True, ...}
    best_snr: float
    total_time_s: float
    num_snapshots: int
    stage_reached: CompressionStage
    failure_reasons: list[str]
    recommendations: list[str]


# ═══════════════════════════════════════════════════════════════════════════════
# THRESHOLD CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
#
# 🏷️  ALL VALUES BELOW ARE PLACEHOLDERS.
#     They will be replaced with empirically calibrated values once
#     labelled data (good/bad compression) is provided.
#


@dataclass
class StageThresholds:
    """Thresholds that define pass/fail for each training stage.

    Attributes marked 🏷️ need calibration from real data.
    """

    # ── Stage 1: DRY_CONTACT  (chip in, no pressure) ─────────────────────
    # We just need *any* reasonable spectrum  — signal above dark noise
    dry_contact_min_mean_intensity: float = 5000.0    # 🏷️ counts
    dry_contact_min_snr: float = 3.0                  # 🏷️ very loose

    # ── Stage 2: INITIAL_COMPRESSION  (SPR dip appears) ──────────────────
    initial_compression_min_dip_depth: float = 0.05   # 🏷️ fractional
    initial_compression_min_snr: float = 5.0          # 🏷️

    # ── Stage 3: FINE_TUNING  (dip is sharp, deep, symmetric) ────────────
    fine_tuning_min_dip_depth: float = 0.15           # 🏷️ fractional
    fine_tuning_max_fwhm: float = 50.0                # 🏷️ nm
    fine_tuning_min_snr: float = 10.0                 # 🏷️
    fine_tuning_max_asymmetry: float = 2.0            # 🏷️ ratio ≤ 2
    fine_tuning_min_baseline_mean: float = 0.40       # 🏷️ transmission

    # ── Stage 4: LEAK_CHECK  (stability over hold window) ────────────────
    leak_check_hold_time_s: float = 10.0              # seconds to hold
    leak_check_max_drift_nm: float = 1.0              # 🏷️ max peak shift
    leak_check_max_intensity_drop_frac: float = 0.15  # 🏷️ max drop in mean

    # ── Pass gate ─────────────────────────────────────────────────────────
    min_channels_passed: int = 0       # 🏷️ 0 = auto (total_channels − 1)
    overall_pass_score: float = 60.0   # 🏷️ minimum composite score (0–100)

    # ── Channel requirements per stage ────────────────────────────────────
    # How many channels must show signal / dip before advancing.
    # 0 = auto-compute as max(1, total_channels // 2).
    dry_contact_min_channels: int = 0
    initial_compression_min_channels: int = 0

    # ── Wavelength region of interest for dip search ─────────────────────
    dip_search_wl_min: float = 550.0   # 🏷️ nm — start of search window
    dip_search_wl_max: float = 700.0   # 🏷️ nm — end of search window

    # ── Detector parameters (set per spectrometer) ───────────────────────
    max_detector_counts: int = 65535   # Spectrometer ADC max (e.g. 16-bit)
    saturation_threshold: float = 0.95 # fraction of max = saturated

    # ── Quality scoring ranges ────────────────────────────────────────────
    # These define the ranges for the 0-100 quality score.  Each pair is
    # (start_scoring, full_marks).  All are 🏷️ placeholders.
    score_depth_range: tuple[float, float] = (0.05, 0.30)     # 🏷️ fractional
    score_fwhm_range: tuple[float, float] = (15.0, 60.0)      # 🏷️ nm (ideal, zero)
    score_snr_range: tuple[float, float] = (5.0, 30.0)        # 🏷️
    score_asymmetry_max: float = 3.0                           # 🏷️ ratio → 0 pts
    score_baseline_range: tuple[float, float] = (0.3, 0.7)    # 🏷️ transmission


# ═══════════════════════════════════════════════════════════════════════════════
# COMPRESSION TRAINER  — state machine + signal evaluator
# ═══════════════════════════════════════════════════════════════════════════════


class CompressionTrainer:
    """State machine that guides a user through sensor compression training.

    Usage (headless / non-Qt)::

        trainer = CompressionTrainer()
        trainer.start()

        # Feed spectra as they arrive:
        for spectrum_dict in acquisition_stream:
            snapshot = trainer.evaluate_spectrum(spectrum_dict)
            print(trainer.stage, trainer.get_instruction())
            if trainer.is_finished():
                result = trainer.get_result()
                break

    Integration with Qt (connect to SimpleAcquisitionManager)::

        trainer = CompressionTrainer()
        trainer.start()
        acq.spectrum_ready.connect(trainer.evaluate_spectrum)
        # poll trainer.stage in a QTimer or observe trainer callbacks

    """

    def __init__(
        self,
        thresholds: StageThresholds | None = None,
        channels: list[str] | None = None,
    ) -> None:
        self.thresholds = thresholds or StageThresholds()
        self.channels = channels or ["a", "b", "c", "d"]

        # State
        self.stage = CompressionStage.IDLE
        self._channel_state: dict[str, ChannelTrainingState] = {
            ch: ChannelTrainingState() for ch in self.channels
        }
        self._start_time: float | None = None
        self._leak_check_start: float | None = None
        self._leak_check_baselines: dict[str, float] = {}
        self._leak_check_dip_positions: dict[str, list[float]] = {}
        self._snapshot_count = 0
        self._failure_reasons: list[str] = []

        # Optional callbacks (no Qt dependency — plain callables)
        self.on_stage_change: Any = None     # callable(old_stage, new_stage)
        self.on_snapshot: Any = None         # callable(snapshot)
        self.on_feedback: Any = None         # callable(message: str, level: str)
        self.on_training_complete: Any = None  # callable(result: TrainingResult)

    # ─── Lifecycle ────────────────────────────────────────────────────────

    def start(self) -> None:
        """Begin training.  Moves from IDLE → DRY_CONTACT."""
        if self.stage != CompressionStage.IDLE:
            logger.warning("Training already started; call reset() first")
            return
        self._start_time = time.time()
        self._transition(CompressionStage.DRY_CONTACT)
        logger.info("🎓 Compression training STARTED")

    def reset(self) -> None:
        """Reset trainer to IDLE so it can be restarted."""
        self.stage = CompressionStage.IDLE
        self._channel_state = {
            ch: ChannelTrainingState() for ch in self.channels
        }
        self._start_time = None
        self._leak_check_start = None
        self._leak_check_baselines.clear()
        self._leak_check_dip_positions.clear()
        self._snapshot_count = 0
        self._failure_reasons.clear()
        logger.info("🔄 Compression trainer reset")

    def abort(self) -> TrainingResult:
        """Abort training early.  Returns a FAILED result."""
        self._failure_reasons.append("Training aborted by user")
        self._transition(CompressionStage.FAILED)
        return self.get_result()

    def is_finished(self) -> bool:
        return self.stage in (CompressionStage.PASSED, CompressionStage.FAILED)

    def get_instruction(self) -> str:
        """Get the human-readable instruction for the current stage."""
        return STAGE_INSTRUCTIONS.get(self.stage, "")

    def get_stage_name(self) -> str:
        return self.stage.name.replace("_", " ").title()

    def get_elapsed_time(self) -> float:
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    # ─── Stage transitions ────────────────────────────────────────────────

    def _transition(self, new_stage: CompressionStage) -> None:
        old = self.stage
        self.stage = new_stage
        logger.info(f"Stage transition: {old.name} → {new_stage.name}")
        if self.on_stage_change:
            try:
                self.on_stage_change(old, new_stage)
            except Exception as e:
                logger.error(f"on_stage_change callback error: {e}")

        if new_stage == CompressionStage.PASSED:
            self._complete(passed=True)
        elif new_stage == CompressionStage.FAILED:
            self._complete(passed=False)

    def _complete(self, passed: bool) -> None:
        result = self.get_result()
        logger.info(
            f"🎓 Training {'PASSED' if passed else 'FAILED'} "
            f"(score={result.overall_score:.1f}, "
            f"time={result.total_time_s:.1f}s)"
        )
        if self.on_training_complete:
            try:
                self.on_training_complete(result)
            except Exception as e:
                logger.error(f"on_training_complete callback error: {e}")

    def _emit_feedback(self, message: str, level: str = "info") -> None:
        """Send feedback to the UI (or log)."""
        log_fn = getattr(logger, level, logger.info)
        log_fn(f"[Training] {message}")
        if self.on_feedback:
            try:
                self.on_feedback(message, level)
            except Exception as e:
                logger.error(f"on_feedback callback error: {e}")

    # ─── Main entry point: evaluate an incoming spectrum ──────────────────

    def evaluate_spectrum(
        self,
        spectrum_data: dict,
    ) -> CompressionSignalSnapshot | None:
        """Evaluate one incoming spectrum and advance state machine.

        This is the method you connect to ``spectrum_ready`` signal::

            acq_manager.spectrum_ready.connect(trainer.evaluate_spectrum)

        Args:
            spectrum_data: Dict with keys:
                - ``channel`` (str): 'a'|'b'|'c'|'d'
                - ``wavelength`` (np.ndarray): wavelength axis
                - ``transmission`` (np.ndarray): transmission values
                - ``timestamp`` (float): time.time()

        Returns:
            CompressionSignalSnapshot or None if stage is IDLE/finished

        """
        if self.stage in (
            CompressionStage.IDLE,
            CompressionStage.PASSED,
            CompressionStage.FAILED,
        ):
            return None

        channel = spectrum_data.get("channel", "?")
        if channel not in self.channels:
            return None

        wavelengths = spectrum_data.get("wavelength")
        transmission = spectrum_data.get("transmission")
        timestamp = spectrum_data.get("timestamp", time.time())

        if wavelengths is None or transmission is None:
            return None

        wavelengths = np.asarray(wavelengths, dtype=np.float64)
        transmission = np.asarray(transmission, dtype=np.float64)

        if len(wavelengths) != len(transmission) or len(wavelengths) == 0:
            return None

        # ── Extract signal metrics ────────────────────────────────────────
        snapshot = self._extract_snapshot(channel, wavelengths, transmission, timestamp)

        # Store snapshot
        ch_state = self._channel_state[channel]
        ch_state.snapshots.append(snapshot)
        self._snapshot_count += 1

        # Track bests
        if snapshot.snr > ch_state.best_snr:
            ch_state.best_snr = snapshot.snr
        if snapshot.dip_depth is not None and snapshot.dip_depth > ch_state.best_dip_depth:
            ch_state.best_dip_depth = snapshot.dip_depth

        # Notify listener
        if self.on_snapshot:
            try:
                self.on_snapshot(snapshot)
            except Exception as e:
                logger.error(f"on_snapshot callback error: {e}")

        # ── Advance state machine ─────────────────────────────────────────
        self._advance(snapshot)

        return snapshot

    # ─── Signal feature extraction ────────────────────────────────────────

    def _extract_snapshot(
        self,
        channel: str,
        wavelengths: np.ndarray,
        transmission: np.ndarray,
        timestamp: float,
    ) -> CompressionSignalSnapshot:
        """Extract quality metrics from one transmission spectrum."""
        th = self.thresholds

        # Basic stats
        mean_int = float(np.mean(transmission))
        max_int = float(np.max(transmission))
        min_int = float(np.min(transmission))
        sat_frac = float(
            np.sum(transmission >= th.saturation_threshold) / len(transmission)
        )

        # ── Find SPR dip in region of interest ───────────────────────────
        roi_mask = (wavelengths >= th.dip_search_wl_min) & (
            wavelengths <= th.dip_search_wl_max
        )
        wl_roi = wavelengths[roi_mask]
        tr_roi = transmission[roi_mask]

        has_dip = False
        dip_wl: float | None = None
        dip_depth: float | None = None
        dip_fwhm: float | None = None
        dip_asym: float | None = None
        baseline_mean = float(np.mean(tr_roi)) if len(tr_roi) > 0 else 0.0
        baseline_std = float(np.std(tr_roi)) if len(tr_roi) > 0 else 0.0
        snr = 0.0

        if len(tr_roi) > 20:
            # Baseline = mean of upper 30% of transmission (outside dip)
            sorted_vals = np.sort(tr_roi)
            top_30 = sorted_vals[int(0.7 * len(sorted_vals)):]
            baseline_mean = float(np.mean(top_30))

            # Dip = minimum in ROI
            min_idx = int(np.argmin(tr_roi))
            dip_val = float(tr_roi[min_idx])
            dip_wl = float(wl_roi[min_idx])

            # Depth as fraction of baseline
            if baseline_mean > 0:
                dip_depth = float((baseline_mean - dip_val) / baseline_mean)
            else:
                dip_depth = 0.0

            # Is this a real dip?  Must be deeper than noise
            noise_outside_dip = self._estimate_noise(tr_roi, min_idx)
            baseline_std = noise_outside_dip

            if dip_depth is not None and noise_outside_dip > 0:
                snr = float((baseline_mean - dip_val) / noise_outside_dip)

            # Consider it a dip if SNR > 2 and depth > 2%
            if snr > 2.0 and (dip_depth or 0) > 0.02:
                has_dip = True

                # FWHM — find where transmission crosses half-depth
                half_level = dip_val + (baseline_mean - dip_val) * 0.5
                dip_fwhm = self._measure_fwhm(wl_roi, tr_roi, min_idx, half_level)

                # Asymmetry — ratio of left to right half-widths
                dip_asym = self._measure_asymmetry(
                    wl_roi, tr_roi, min_idx, half_level
                )

                # Record first-dip time
                ch_state = self._channel_state.get(channel)
                if ch_state and ch_state.first_dip_time is None:
                    ch_state.first_dip_time = time.time()

        # ── Composite quality score ───────────────────────────────────────
        quality = self._compute_quality_score(
            has_dip=has_dip,
            dip_depth=dip_depth,
            dip_fwhm=dip_fwhm,
            snr=snr,
            dip_asym=dip_asym,
            baseline_mean=baseline_mean,
        )

        return CompressionSignalSnapshot(
            channel=channel,
            timestamp=timestamp,
            mean_intensity=mean_int,
            max_intensity=max_int,
            min_intensity=min_int,
            saturation_fraction=sat_frac,
            has_dip=has_dip,
            dip_wavelength=dip_wl,
            dip_depth=dip_depth,
            dip_fwhm=dip_fwhm,
            dip_asymmetry=dip_asym,
            snr=snr,
            baseline_std=baseline_std,
            baseline_mean=baseline_mean,
            quality_score=quality,
        )

    @staticmethod
    def _estimate_noise(tr_roi: np.ndarray, dip_idx: int) -> float:
        """Estimate noise from transmission values *away* from the dip.

        Takes the std of the outer 25% on each side of the ROI (avoiding
        the central dip region).
        """
        n = len(tr_roi)
        quarter = max(n // 4, 5)
        left_wing = tr_roi[:quarter]
        right_wing = tr_roi[-quarter:]
        wings = np.concatenate([left_wing, right_wing])
        return float(np.std(wings)) if len(wings) > 2 else 1e-6

    @staticmethod
    def _measure_fwhm(
        wl: np.ndarray,
        tr: np.ndarray,
        min_idx: int,
        half_level: float,
    ) -> float | None:
        """Measure FWHM of a dip at the given half-level."""
        n = len(wl)
        # Search left
        left_wl = None
        for i in range(min_idx, -1, -1):
            if tr[i] >= half_level:
                # Linear interpolate
                if i < min_idx:
                    frac = (half_level - tr[i + 1]) / (tr[i] - tr[i + 1] + 1e-12)
                    left_wl = wl[i + 1] + frac * (wl[i] - wl[i + 1])
                else:
                    left_wl = wl[i]
                break

        # Search right
        right_wl = None
        for i in range(min_idx, n):
            if tr[i] >= half_level:
                if i > min_idx:
                    frac = (half_level - tr[i - 1]) / (tr[i] - tr[i - 1] + 1e-12)
                    right_wl = wl[i - 1] + frac * (wl[i] - wl[i - 1])
                else:
                    right_wl = wl[i]
                break

        if left_wl is not None and right_wl is not None:
            return float(abs(right_wl - left_wl))
        return None

    @staticmethod
    def _measure_asymmetry(
        wl: np.ndarray,
        tr: np.ndarray,
        min_idx: int,
        half_level: float,
    ) -> float | None:
        """Measure left/right half-width ratio (1.0 = perfectly symmetric)."""
        n = len(wl)
        dip_wl = wl[min_idx]

        left_hw = None
        for i in range(min_idx, -1, -1):
            if tr[i] >= half_level:
                left_hw = abs(dip_wl - wl[i])
                break

        right_hw = None
        for i in range(min_idx, n):
            if tr[i] >= half_level:
                right_hw = abs(wl[i] - dip_wl)
                break

        if left_hw and right_hw and min(left_hw, right_hw) > 0:
            return float(max(left_hw, right_hw) / min(left_hw, right_hw))
        return None

    def _compute_quality_score(
        self,
        *,
        has_dip: bool,
        dip_depth: float | None,
        dip_fwhm: float | None,
        snr: float,
        dip_asym: float | None,
        baseline_mean: float,
    ) -> float:
        """Compute a 0-100 quality score from spectrum metrics.

        Scoring components (🏷️ weights are placeholders):
            - Dip presence:  20 pts
            - Dip depth:     25 pts  (deeper = better, up to threshold)
            - FWHM:          20 pts  (narrower = better)
            - SNR:           20 pts  (higher = better)
            - Symmetry:      10 pts  (closer to 1.0 = better)
            - Baseline:       5 pts  (reasonable transmission level)
        """
        score = 0.0
        th = self.thresholds

        # Dip presence (20 pts)
        if has_dip:
            score += 20.0

        # Dip depth (25 pts) — linear from 0 at min threshold to 25 at good depth
        if dip_depth is not None and dip_depth > 0:
            d_lo, d_hi = th.score_depth_range     # 🏷️
            depth_score = np.clip(
                (dip_depth - d_lo) / (d_hi - d_lo), 0.0, 1.0
            )
            score += float(depth_score) * 25.0

        # FWHM (20 pts) — narrower is better
        if dip_fwhm is not None and dip_fwhm > 0:
            f_ideal, f_zero = th.score_fwhm_range  # 🏷️
            fwhm_score = np.clip(
                1.0 - (dip_fwhm - f_ideal) / (f_zero - f_ideal), 0.0, 1.0
            )
            score += float(fwhm_score) * 20.0

        # SNR (20 pts)
        if snr > 0:
            s_lo, s_hi = th.score_snr_range        # 🏷️
            snr_score = np.clip((snr - s_lo) / (s_hi - s_lo), 0.0, 1.0)
            score += float(snr_score) * 20.0

        # Symmetry (10 pts) — asymmetry ratio close to 1.0
        if dip_asym is not None and dip_asym >= 1.0:
            asym_max = th.score_asymmetry_max      # 🏷️
            sym_score = np.clip(
                1.0 - (dip_asym - 1.0) / (asym_max - 1.0), 0.0, 1.0
            )
            score += float(sym_score) * 10.0

        # Baseline level (5 pts) — transmission not too low
        if baseline_mean > 0:
            bl_lo, bl_hi = th.score_baseline_range  # 🏷️
            bl_score = np.clip(
                (baseline_mean - bl_lo) / (bl_hi - bl_lo), 0.0, 1.0
            )
            score += float(bl_score) * 5.0

        return round(score, 1)

    # ─── State machine advancement ────────────────────────────────────────

    def _advance(self, snap: CompressionSignalSnapshot) -> None:
        """Advance the state machine based on the latest snapshot."""
        if self.stage == CompressionStage.DRY_CONTACT:
            self._check_dry_contact(snap)
        elif self.stage == CompressionStage.INITIAL_COMPRESSION:
            self._check_initial_compression(snap)
        elif self.stage == CompressionStage.FINE_TUNING:
            self._check_fine_tuning(snap)
        elif self.stage == CompressionStage.LEAK_CHECK:
            self._check_leak(snap)

    def _check_dry_contact(self, snap: CompressionSignalSnapshot) -> None:
        """Stage 1: Verify we have *any* reasonable spectrum."""
        th = self.thresholds

        # If we already see a dip, skip straight to INITIAL_COMPRESSION
        if snap.has_dip:
            self._emit_feedback(
                f"Ch {snap.channel}: SPR dip already visible — good contact!",
                "info",
            )
            self._transition(CompressionStage.INITIAL_COMPRESSION)
            return

        # Otherwise, check basic signal presence
        if snap.mean_intensity >= th.dry_contact_min_mean_intensity:
            # Count how many channels have signal
            channels_with_signal = sum(
                1
                for ch in self.channels
                if self._channel_state[ch].snapshots
                and self._channel_state[ch].snapshots[-1].mean_intensity
                >= th.dry_contact_min_mean_intensity
            )
            min_ch = (
                th.dry_contact_min_channels
                or max(1, len(self.channels) // 2)
            )
            if channels_with_signal >= min_ch:
                self._emit_feedback(
                    f"{channels_with_signal} channels have signal — begin compressing.",
                    "info",
                )
                self._transition(CompressionStage.INITIAL_COMPRESSION)

    def _check_initial_compression(self, snap: CompressionSignalSnapshot) -> None:
        """Stage 2: Look for SPR dip to appear."""
        th = self.thresholds

        if not snap.has_dip:
            return

        if (snap.dip_depth or 0) < th.initial_compression_min_dip_depth:
            return

        if snap.snr < th.initial_compression_min_snr:
            return

        # Count channels with a valid dip
        channels_with_dip = sum(
            1
            for ch in self.channels
            if self._channel_state[ch].snapshots
            and self._channel_state[ch].snapshots[-1].has_dip
        )

        min_ch = (
            th.initial_compression_min_channels
            or max(1, len(self.channels) // 2)
        )
        if channels_with_dip >= min_ch:
            self._emit_feedback(
                f"SPR dip detected on {channels_with_dip} channels! "
                f"Continue tightening slowly.",
                "info",
            )
            self._transition(CompressionStage.FINE_TUNING)

    def _check_fine_tuning(self, snap: CompressionSignalSnapshot) -> None:
        """Stage 3: Check that the dip is sharp, deep, and the SNR is high."""
        th = self.thresholds

        if not snap.has_dip:
            return

        # Check individual thresholds
        depth_ok = (snap.dip_depth or 0) >= th.fine_tuning_min_dip_depth
        fwhm_ok = (
            snap.dip_fwhm is not None and snap.dip_fwhm <= th.fine_tuning_max_fwhm
        )
        snr_ok = snap.snr >= th.fine_tuning_min_snr
        asym_ok = (
            snap.dip_asymmetry is None
            or snap.dip_asymmetry <= th.fine_tuning_max_asymmetry
        )
        baseline_ok = snap.baseline_mean >= th.fine_tuning_min_baseline_mean

        # Mark channel as passed if all criteria met
        ch_state = self._channel_state[snap.channel]
        if depth_ok and fwhm_ok and snr_ok and asym_ok and baseline_ok:
            ch_state.stage_passed["fine_tuning"] = True
            self._emit_feedback(
                f"Ch {snap.channel}: ✅ compression quality GOOD "
                f"(depth={snap.dip_depth:.2f}, FWHM={snap.dip_fwhm:.1f}nm, "
                f"SNR={snap.snr:.1f})",
                "info",
            )
        else:
            # Provide specific guidance
            hints = []
            if not depth_ok:
                hints.append(f"dip too shallow ({snap.dip_depth:.2f})")
            if not fwhm_ok and snap.dip_fwhm is not None:
                hints.append(f"dip too wide ({snap.dip_fwhm:.0f}nm)")
            if not snr_ok:
                hints.append(f"SNR low ({snap.snr:.1f})")
            if not asym_ok and snap.dip_asymmetry is not None:
                hints.append(f"asymmetric ({snap.dip_asymmetry:.1f})")
            if not baseline_ok:
                hints.append(f"baseline low ({snap.baseline_mean:.2f})")

            if hints and self._snapshot_count % 10 == 0:
                self._emit_feedback(
                    f"Ch {snap.channel}: needs adjustment — "
                    + ", ".join(hints),
                    "warning",
                )

        # Check if enough channels have passed fine-tuning
        passed_channels = sum(
            1
            for ch in self.channels
            if self._channel_state[ch].stage_passed.get("fine_tuning", False)
        )

        min_ch = th.min_channels_passed or max(1, len(self.channels) - 1)
        if passed_channels >= min_ch:
            self._emit_feedback(
                f"{passed_channels}/{len(self.channels)} channels passed! "
                f"Starting leak check — hold steady.",
                "info",
            )
            self._begin_leak_check()
            self._transition(CompressionStage.LEAK_CHECK)

    def _begin_leak_check(self) -> None:
        """Initialize leak check baselines."""
        self._leak_check_start = time.time()
        self._leak_check_baselines.clear()
        self._leak_check_dip_positions.clear()

        for ch in self.channels:
            snaps = self._channel_state[ch].snapshots
            if snaps:
                last = snaps[-1]
                self._leak_check_baselines[ch] = last.mean_intensity
                if last.dip_wavelength is not None:
                    self._leak_check_dip_positions[ch] = [last.dip_wavelength]

    def _check_leak(self, snap: CompressionSignalSnapshot) -> None:
        """Stage 4: Monitor stability for hold_time seconds."""
        th = self.thresholds
        now = time.time()
        elapsed = now - (self._leak_check_start or now)
        ch = snap.channel

        # Track dip position drift
        if snap.dip_wavelength is not None:
            if ch not in self._leak_check_dip_positions:
                self._leak_check_dip_positions[ch] = []
            self._leak_check_dip_positions[ch].append(snap.dip_wavelength)

        # Track intensity drop
        baseline = self._leak_check_baselines.get(ch)
        if baseline and baseline > 0 and snap.mean_intensity > 0:
            drop_frac = (baseline - snap.mean_intensity) / baseline
            if drop_frac > th.leak_check_max_intensity_drop_frac:
                self._failure_reasons.append(
                    f"Ch {ch}: intensity dropped {drop_frac:.0%} during leak check"
                )
                self._emit_feedback(
                    f"⚠️ Ch {ch}: intensity dropping — possible leak!",
                    "warning",
                )
                self._transition(CompressionStage.FAILED)
                return

        # Check dip position drift
        if ch in self._leak_check_dip_positions:
            positions = self._leak_check_dip_positions[ch]
            if len(positions) >= 3:
                drift = abs(positions[-1] - positions[0])
                if drift > th.leak_check_max_drift_nm:
                    self._failure_reasons.append(
                        f"Ch {ch}: dip drifted {drift:.2f}nm during leak check"
                    )
                    self._emit_feedback(
                        f"⚠️ Ch {ch}: dip position unstable — "
                        f"re-adjust compression.",
                        "warning",
                    )
                    # Don't fail immediately — go back to fine-tuning
                    self._leak_check_start = None
                    self._transition(CompressionStage.FINE_TUNING)
                    return

        # Have we held long enough?
        if elapsed >= th.leak_check_hold_time_s:
            self._emit_feedback(
                f"Leak check passed after {elapsed:.0f}s — sensor stable!",
                "info",
            )
            self._transition(CompressionStage.PASSED)

        elif self._snapshot_count % 20 == 0:
            remaining = th.leak_check_hold_time_s - elapsed
            self._emit_feedback(
                f"Hold steady… {remaining:.0f}s remaining",
                "info",
            )

    # ─── Results ──────────────────────────────────────────────────────────

    def get_result(self) -> TrainingResult:
        """Build the final training result object."""
        th = self.thresholds
        elapsed = self.get_elapsed_time()

        per_channel_scores: dict[str, float] = {}
        per_channel_passed: dict[str, bool] = {}
        best_snr = 0.0

        for ch in self.channels:
            ch_state = self._channel_state[ch]
            if ch_state.snapshots:
                # Score = best quality score seen during training
                best_q = max(s.quality_score for s in ch_state.snapshots)
                per_channel_scores[ch] = best_q

                # Channel passes if it achieved fine-tuning
                per_channel_passed[ch] = ch_state.stage_passed.get(
                    "fine_tuning", False
                )

                if ch_state.best_snr > best_snr:
                    best_snr = ch_state.best_snr
            else:
                per_channel_scores[ch] = 0.0
                per_channel_passed[ch] = False

        # Overall score = weighted average of channel scores
        if per_channel_scores:
            overall_score = sum(per_channel_scores.values()) / len(per_channel_scores)
        else:
            overall_score = 0.0

        passed_count = sum(per_channel_passed.values())
        min_ch_pass = (
            th.min_channels_passed
            or max(1, len(self.channels) - 1)
        )
        passed = (
            self.stage == CompressionStage.PASSED
            and passed_count >= min_ch_pass
            and overall_score >= th.overall_pass_score
        )

        recommendations = self._generate_recommendations(
            per_channel_scores, per_channel_passed
        )

        return TrainingResult(
            passed=passed,
            overall_score=round(overall_score, 1),
            per_channel_scores=per_channel_scores,
            per_channel_passed=per_channel_passed,
            best_snr=round(best_snr, 2),
            total_time_s=round(elapsed, 1),
            num_snapshots=self._snapshot_count,
            stage_reached=self.stage,
            failure_reasons=self._failure_reasons.copy(),
            recommendations=recommendations,
        )

    def _generate_recommendations(
        self,
        scores: dict[str, float],
        passed: dict[str, bool],
    ) -> list[str]:
        """Generate user-friendly recommendations based on per-channel data."""
        recs: list[str] = []

        failed_chs = [ch for ch, p in passed.items() if not p]
        if failed_chs:
            recs.append(
                f"Channels {', '.join(ch.upper() for ch in failed_chs)} "
                f"did not reach target compression."
            )

        # Check for asymmetric compression across channels
        if scores:
            score_vals = list(scores.values())
            spread = max(score_vals) - min(score_vals)
            if spread > 30:
                recs.append(
                    "Large quality spread between channels — check that "
                    "the chip is seated evenly and the o-ring is centered."
                )

        # Check for over-compression hints
        for ch in self.channels:
            ch_state = self._channel_state[ch]
            snaps = ch_state.snapshots
            if len(snaps) > 10:
                # If quality was going up then started going down
                recent = [s.quality_score for s in snaps[-10:]]
                older = [s.quality_score for s in snaps[-20:-10]] if len(snaps) > 20 else []
                if older and np.mean(recent) < np.mean(older) * 0.8:
                    recs.append(
                        f"Ch {ch.upper()}: quality decreased recently — "
                        f"you may have over-compressed.  Back off slightly."
                    )

        if not recs:
            recs.append("Compression looks good across all channels.")

        return recs

    # ─── Channel summary (for UI display) ─────────────────────────────────

    def get_channel_summary(self, channel: str) -> dict:
        """Get summary dict for one channel (useful for UI cards).

        Returns:
            Dict with keys: channel, num_snapshots, best_snr, best_dip_depth,
            latest_quality, has_dip, fine_tuning_passed, dip_wavelength,
            dip_fwhm, dip_depth, snr, quality_score
        """
        ch_state = self._channel_state.get(channel)
        if not ch_state or not ch_state.snapshots:
            return {
                "channel": channel,
                "num_snapshots": 0,
                "best_snr": 0.0,
                "best_dip_depth": 0.0,
                "latest_quality": 0.0,
                "has_dip": False,
                "fine_tuning_passed": False,
                "dip_wavelength": None,
                "dip_fwhm": None,
                "dip_depth": None,
                "snr": 0.0,
                "quality_score": 0.0,
            }

        latest = ch_state.snapshots[-1]
        return {
            "channel": channel,
            "num_snapshots": len(ch_state.snapshots),
            "best_snr": round(ch_state.best_snr, 2),
            "best_dip_depth": round(ch_state.best_dip_depth, 3),
            "latest_quality": round(latest.quality_score, 1),
            "has_dip": latest.has_dip,
            "fine_tuning_passed": ch_state.stage_passed.get("fine_tuning", False),
            "dip_wavelength": (
                round(latest.dip_wavelength, 1) if latest.dip_wavelength else None
            ),
            "dip_fwhm": round(latest.dip_fwhm, 1) if latest.dip_fwhm else None,
            "dip_depth": round(latest.dip_depth, 3) if latest.dip_depth else None,
            "snr": round(latest.snr, 1),
            "quality_score": round(latest.quality_score, 1),
        }

    def get_all_channels_summary(self) -> dict[str, dict]:
        """Get summary for all channels."""
        return {ch: self.get_channel_summary(ch) for ch in self.channels}

    # ─── Diagnostic dump (for logging / debugging) ─────────────────────────

    def dump_training_log(self) -> str:
        """Generate a detailed text log of the entire training session.

        Useful for post-training review or debugging threshold issues.
        """
        lines = [
            "=" * 72,
            "COMPRESSION TRAINING LOG",
            "=" * 72,
            f"Stage reached: {self.stage.name}",
            f"Elapsed time:  {self.get_elapsed_time():.1f}s",
            f"Total spectra: {self._snapshot_count}",
            "",
        ]

        for ch in self.channels:
            ch_state = self._channel_state[ch]
            lines.append(f"── Channel {ch.upper()} ──")
            lines.append(f"  Snapshots:      {len(ch_state.snapshots)}")
            lines.append(f"  Best SNR:       {ch_state.best_snr:.2f}")
            lines.append(f"  Best dip depth: {ch_state.best_dip_depth:.3f}")
            lines.append(
                f"  Fine-tuning:    "
                f"{'PASSED' if ch_state.stage_passed.get('fine_tuning') else 'not passed'}"
            )

            if ch_state.snapshots:
                latest = ch_state.snapshots[-1]
                lines.append(f"  Latest quality: {latest.quality_score:.1f}/100")
                if latest.dip_wavelength:
                    lines.append(
                        f"  Dip position:   {latest.dip_wavelength:.1f}nm"
                    )
                if latest.dip_fwhm:
                    lines.append(f"  Dip FWHM:       {latest.dip_fwhm:.1f}nm")
            lines.append("")

        result = self.get_result()
        lines.append(f"Overall score: {result.overall_score:.1f}/100")
        lines.append(f"Result:        {'PASSED' if result.passed else 'FAILED'}")

        if result.failure_reasons:
            lines.append("\nFailure reasons:")
            for reason in result.failure_reasons:
                lines.append(f"  - {reason}")

        if result.recommendations:
            lines.append("\nRecommendations:")
            for rec in result.recommendations:
                lines.append(f"  - {rec}")

        lines.append("=" * 72)
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# STANDALONE DEMO  — run with:  python -m affilabs.services.compression_training
#                    or:         python affilabs/services/compression_training.py
# ═══════════════════════════════════════════════════════════════════════════════


def _demo() -> None:
    """Simulate a full compression training session with synthetic SPR data.

    Walks through every stage of the state machine so you can see the
    feedback messages, quality scores, and final training report.
    """
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
    )

    print("=" * 72)
    print("  COMPRESSION TRAINING DEMO  (synthetic data)")
    print("=" * 72)
    print()

    wl = np.linspace(500, 750, 500)
    trainer = CompressionTrainer()

    # Attach a simple feedback printer
    def _on_feedback(msg: str, level: str) -> None:
        icon = {"info": "  ℹ️ ", "warning": "  ⚠️ ", "error": "  ❌ "}.get(level, "  ")
        print(f"{icon}{msg}")

    def _on_stage(old: CompressionStage, new: CompressionStage) -> None:
        print(f"\n{'─'*50}")
        print(f"  STAGE: {old.name}  →  {new.name}")
        print(f"  {trainer.get_instruction().split(chr(10))[0]}")
        print(f"{'─'*50}")

    trainer.on_feedback = _on_feedback
    trainer.on_stage_change = _on_stage

    # ── Start ─────────────────────────────────────────────────────────────
    trainer.start()

    # ── Stage 1 → 2: Flat spectra (chip placed, no compression) ──────────
    print("\n📌 Sending flat spectra (chip placed, no dip yet)...")
    for ch in "abcd":
        flat = np.ones_like(wl) * 0.85 + np.random.normal(0, 0.01, len(wl))
        trainer.evaluate_spectrum({
            "channel": ch, "wavelength": wl,
            "transmission": flat, "timestamp": time.time(),
        })

    # ── Stage 2 → 3: Shallow dip appears ─────────────────────────────────
    print("\n📌 Sending spectra with shallow SPR dip (initial compression)...")
    for _ in range(3):
        for ch in "abcd":
            tr = np.ones_like(wl) * 0.80
            tr -= 0.20 * np.exp(-((wl - 615) ** 2) / (2 * 15**2))
            tr += np.random.normal(0, 0.005, len(wl))
            trainer.evaluate_spectrum({
                "channel": ch, "wavelength": wl,
                "transmission": tr, "timestamp": time.time(),
            })

    # ── Stage 3 → 4: Sharp, deep dip (good compression) ──────────────────
    print("\n📌 Sending spectra with sharp, deep dip (fine-tuned)...")
    for _ in range(5):
        for ch in "abcd":
            tr = np.ones_like(wl) * 0.75
            tr -= 0.38 * np.exp(-((wl - 610) ** 2) / (2 * 8**2))
            tr += np.random.normal(0, 0.003, len(wl))
            trainer.evaluate_spectrum({
                "channel": ch, "wavelength": wl,
                "transmission": tr, "timestamp": time.time(),
            })

    # ── Print channel cards ───────────────────────────────────────────────
    print("\n📊 Channel Status:")
    for ch in "abcd":
        s = trainer.get_channel_summary(ch)
        status = "✅" if s["fine_tuning_passed"] else "⬜"
        print(
            f"  {status} Ch {ch.upper()}: "
            f"quality={s['quality_score']}/100, "
            f"SNR={s['snr']}, "
            f"dip={s['dip_depth']}, "
            f"FWHM={s['dip_fwhm']}nm"
        )

    # ── Stage 4 → PASSED: Simulate stable 10 s hold ──────────────────────
    if trainer.stage == CompressionStage.LEAK_CHECK:
        print("\n📌 Simulating 10 s stable hold (leak check)...")
        # Fast-forward the timer
        trainer._leak_check_start = time.time() - 11
        tr = np.ones_like(wl) * 0.75
        tr -= 0.38 * np.exp(-((wl - 610) ** 2) / (2 * 8**2))
        tr += np.random.normal(0, 0.003, len(wl))
        trainer.evaluate_spectrum({
            "channel": "a", "wavelength": wl,
            "transmission": tr, "timestamp": time.time(),
        })
    elif trainer.stage == CompressionStage.FINE_TUNING:
        # Might still be in fine-tuning if leak check bounced back
        print("\n📌 Still in FINE_TUNING — sending more good spectra...")
        for _ in range(3):
            for ch in "abcd":
                tr = np.ones_like(wl) * 0.75
                tr -= 0.38 * np.exp(-((wl - 610) ** 2) / (2 * 8**2))
                tr += np.random.normal(0, 0.003, len(wl))
                trainer.evaluate_spectrum({
                    "channel": ch, "wavelength": wl,
                    "transmission": tr, "timestamp": time.time(),
                })
        if trainer.stage == CompressionStage.LEAK_CHECK:
            trainer._leak_check_start = time.time() - 11
            tr = np.ones_like(wl) * 0.75
            tr -= 0.38 * np.exp(-((wl - 610) ** 2) / (2 * 8**2))
            tr += np.random.normal(0, 0.003, len(wl))
            trainer.evaluate_spectrum({
                "channel": "a", "wavelength": wl,
                "transmission": tr, "timestamp": time.time(),
            })

    # ── Final report ──────────────────────────────────────────────────────
    result = trainer.get_result()
    print()
    print(trainer.dump_training_log())

    # ── Summary ───────────────────────────────────────────────────────────
    print()
    if result.passed:
        print("🎉 TRAINING PASSED — sensor ready for experiments!")
        print(f"   Score: {result.overall_score}/100")
        print(f"   Best SNR: {result.best_snr}")
    else:
        print("🔧 TRAINING DID NOT PASS (this is expected with synthetic data)")
        print(f"   Score: {result.overall_score}/100")
        print(f"   Stage reached: {result.stage_reached.name}")
        if result.failure_reasons:
            for r in result.failure_reasons:
                print(f"   • {r}")


if __name__ == "__main__":
    _demo()
