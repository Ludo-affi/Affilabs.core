"""Signal Event Classifier — FRS §3 (readiness) + §4 (bubble detection).

Two outputs only:
  1. Pre-inject readiness verdict: READY / WAIT / CHECK  (Stage 1)
  2. Bubble detected flag: POSSIBLE_BUBBLE              (Stage 2)

Called per-frame from spectrum_helpers.py (for telemetry) and per-poll
from _InjectionMonitor._check_bubbles() (for live alerts).

All thresholds live in settings.py — no magic numbers here.

See docs/features/SIGNAL_EVENT_CLASSIFIER_FRS.md for full spec.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ReadinessVerdict = Literal["READY", "WAIT", "CHECK", "NONE"]


# ---------------------------------------------------------------------------
# Stage 1 — Pre-inject readiness
# ---------------------------------------------------------------------------

@dataclass
class ReadinessResult:
    verdict: ReadinessVerdict = "NONE"
    message: str = ""
    reason:  str = ""   # which criterion triggered WAIT or CHECK


def check_readiness(
    *,
    slope_5s_ru:       float,
    p2p_5frame_ru:     float,
    control_slope_ru:  float | None = None,
    regen_delta_ru:    float | None = None,
    iq_level:          str          = "",
    is_first_cycle:    bool         = False,
) -> ReadinessResult:
    """Evaluate pre-inject readiness per FRS §3.2.

    All inputs in RU. Returns a ReadinessResult with verdict + plain-English message.

    Args:
        slope_5s_ru:      Linear regression slope of last 5 frames (RU/s, signed).
        p2p_5frame_ru:    Peak-to-peak of last 5 frames (RU).
        control_slope_ru: Slope of control channel (RU/s). None → criterion skipped.
        regen_delta_ru:   Post-regen baseline − pre-injection baseline (RU, ≥0).
                          None → criterion skipped (first cycle or no prior cycle).
        iq_level:         SensorIQ level string ('GOOD', 'FAIR', 'POOR', 'CRITICAL').
        is_first_cycle:   Loosen baseline criterion for equilibrating chips.
    """
    try:
        from settings import (
            READINESS_SLOPE_READY, READINESS_SLOPE_WAIT,
            READINESS_NOISE_READY, READINESS_NOISE_WAIT,
            READINESS_CTRL_READY,  READINESS_CTRL_WAIT,
            READINESS_REGEN_READY, READINESS_REGEN_WAIT,
        )
    except ImportError:
        READINESS_SLOPE_READY = 7.0;  READINESS_SLOPE_WAIT = 35.0
        READINESS_NOISE_READY = 12.0; READINESS_NOISE_WAIT = 35.0
        READINESS_CTRL_READY  = 7.0;  READINESS_CTRL_WAIT  = 18.0
        READINESS_REGEN_READY = 18.0; READINESS_REGEN_WAIT = 53.0

    abs_slope = abs(slope_5s_ru)

    # Loosen baseline threshold on first cycle (chip still equilibrating)
    slope_wait_thresh  = READINESS_SLOPE_WAIT  * (2.0 if is_first_cycle else 1.0)
    slope_check_thresh = slope_wait_thresh

    # --- CHECK conditions (override WAIT) ---

    if abs_slope >= slope_check_thresh:
        return ReadinessResult("CHECK", "Check baseline — unstable", "baseline")

    if p2p_5frame_ru >= READINESS_NOISE_WAIT:
        return ReadinessResult("CHECK", "Check — persistent noise", "noise")

    if control_slope_ru is not None and abs(control_slope_ru) >= READINESS_CTRL_WAIT:
        return ReadinessResult("CHECK", "Check — buffer matching", "bulk")

    if regen_delta_ru is not None and regen_delta_ru >= READINESS_REGEN_WAIT:
        return ReadinessResult("CHECK", "Check — residual signal from last cycle", "regen")

    if iq_level in ("POOR", "CRITICAL"):
        return ReadinessResult("CHECK", "Check — signal quality low", "iq")

    # --- WAIT conditions ---

    if abs_slope >= READINESS_SLOPE_READY:
        return ReadinessResult("WAIT", "Wait — stabilising", "baseline")

    if p2p_5frame_ru >= READINESS_NOISE_READY:
        return ReadinessResult("WAIT", "Wait — noisy signal", "noise")

    if control_slope_ru is not None and abs(control_slope_ru) >= READINESS_CTRL_READY:
        return ReadinessResult("WAIT", "Wait — reference settling", "control")

    if regen_delta_ru is not None and regen_delta_ru >= READINESS_REGEN_READY:
        return ReadinessResult("WAIT", "Wait — regen incomplete", "regen")

    if iq_level == "FAIR":
        return ReadinessResult("WAIT", "Wait — signal quality marginal", "iq")

    return ReadinessResult("READY", "Ready", "")


# ---------------------------------------------------------------------------
# Stage 2 — Bubble detection
# ---------------------------------------------------------------------------

def check_bubble(
    *,
    p2p_ru:        float,
    dip_depth:     float | None,
    fwhm_nm:       float | None,
    dip_depth_ref: float | None,
    fwhm_ref:      float | None,
) -> str | None:
    """Evaluate bubble criterion per FRS §4.3.

    Returns 'POSSIBLE_BUBBLE' if all three criteria fire simultaneously, else None.

    Args:
        p2p_ru:        Rolling P2P of last 5 frames in RU (std × 355).
        dip_depth:     Current dip depth (fractional, e.g. 0.77).
        fwhm_nm:       Current FWHM in nm.
        dip_depth_ref: Reference dip depth (mean of last 10 clean frames). None → skip.
        fwhm_ref:      Reference FWHM in nm. None → skip.
    """
    try:
        from settings import (
            BUBBLE_P2P_THRESHOLD,
            BUBBLE_DEPTH_THRESHOLD,
            BUBBLE_FWHM_THRESHOLD,
        )
    except ImportError:
        BUBBLE_P2P_THRESHOLD   = 20.0
        BUBBLE_DEPTH_THRESHOLD = 0.05
        BUBBLE_FWHM_THRESHOLD  = 3.0

    # Criterion 1: P2P elevated (supporting)
    p2p_criterion = p2p_ru > BUBBLE_P2P_THRESHOLD

    # Criterion 2: dip depth dropped ≥5% (primary)
    depth_criterion = False
    if dip_depth is not None and dip_depth_ref is not None and dip_depth_ref > 0:
        depth_drop = (dip_depth_ref - dip_depth) / dip_depth_ref
        depth_criterion = depth_drop > BUBBLE_DEPTH_THRESHOLD

    # Criterion 3: FWHM broadened (directional — bubble never narrows)
    fwhm_criterion = False
    if fwhm_nm is not None and fwhm_ref is not None:
        fwhm_criterion = (fwhm_nm - fwhm_ref) > BUBBLE_FWHM_THRESHOLD

    if p2p_criterion and depth_criterion and fwhm_criterion:
        return "POSSIBLE_BUBBLE"
    return None


# ---------------------------------------------------------------------------
# Stage 3 — Pre/post event triage
# ---------------------------------------------------------------------------

# Each entry in a snapshot is (wavelength_nm, transmittance_pct, fwhm_nm, raw_peak)
_OpticalFrame = tuple[float | None, float | None, float | None, float | None]

# Triage outcomes — ordered by priority (highest first)
TriageOutcome = Literal["LEAK", "BUBBLE", "CHIP_DEGRADED", "INJECTION"]


def _mean_field(frames: list[_OpticalFrame], idx: int) -> float | None:
    """Mean of field[idx] across frames, ignoring None values."""
    vals = [f[idx] for f in frames if f[idx] is not None]
    return sum(vals) / len(vals) if vals else None


def check_event_triage(
    pre: list[_OpticalFrame],
    post: list[_OpticalFrame],
) -> TriageOutcome:
    """Classify a confirmed P2P spike using 5-point pre/post optical windows.

    Triage cascade (highest priority first):
      1. LEAK        — raw_peak collapses ≥75% from pre to post
      2. BUBBLE      — %T drops ≥10pp AND FWHM broadens ≥30% from pre to post
      3. CHIP_DEGRADED — FWHM broadens ≥30% AND %T did not rise (not a filling artifact)
      4. INJECTION   — none of the above → sustained binding event

    Note on %T rise after injection: if %T increases post-event (dip shallows,
    e.g. 70%→80%), this means air pockets in the flow cell were displaced by
    liquid. This is a normal filling artifact — not a bubble, not chip degradation.
    tx_drop will be negative, so checks 2 and 3 are both suppressed correctly.

    Args:
        pre:  Last 5 optical frames before the spike (pre-event window).
        post: First 5 optical frames after the spike (post-event window).

    Returns:
        TriageOutcome string.
    """
    if not pre or not post:
        return "INJECTION"  # insufficient data — default to injection

    # Field indices: 0=wavelength, 1=transmittance_pct, 2=fwhm_nm, 3=raw_peak
    pre_peak  = _mean_field(pre,  3)
    post_peak = _mean_field(post, 3)
    pre_tx    = _mean_field(pre,  1)
    post_tx   = _mean_field(post, 1)
    pre_fwhm  = _mean_field(pre,  2)
    post_fwhm = _mean_field(post, 2)

    # 1. Leak — raw intensity collapses ≥75%
    if pre_peak is not None and post_peak is not None and pre_peak > 0:
        if (pre_peak - post_peak) / pre_peak >= 0.75:
            return "LEAK"

    # 2. Bubble — %T drops ≥10pp AND FWHM broadens ≥30%
    tx_drop   = (pre_tx   - post_tx)   if (pre_tx is not None   and post_tx is not None)   else None
    fwhm_rel  = ((post_fwhm - pre_fwhm) / pre_fwhm) if (pre_fwhm is not None and post_fwhm is not None and pre_fwhm > 0) else None

    if tx_drop is not None and fwhm_rel is not None:
        if tx_drop >= 10.0 and fwhm_rel >= 0.30:
            return "BUBBLE"

    # 3. Chip degraded — FWHM broadens ≥30% without %T drop
    # Exception: if %T increased post-injection (tx_drop < 0), this is a filling
    # artifact — air pockets displaced by liquid causing dip to shallow temporarily.
    # Do not flag as chip degradation; fall through to INJECTION.
    tx_rose = tx_drop is not None and tx_drop < 0
    if fwhm_rel is not None and fwhm_rel >= 0.30 and not tx_rose:
        return "CHIP_DEGRADED"

    # 4. Injection — sustained binding event (includes filling artifact with %T rise)
    return "INJECTION"


# ---------------------------------------------------------------------------
# Convenience class — wraps both stages as static methods for easy import
# ---------------------------------------------------------------------------

class SignalEventClassifier:
    """Stateless classifier. All methods are static — no instance needed."""

    check_readiness   = staticmethod(check_readiness)
    check_bubble      = staticmethod(check_bubble)
    check_event_triage = staticmethod(check_event_triage)
