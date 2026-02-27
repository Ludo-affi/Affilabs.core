from __future__ import annotations

"""Injection and SPR signal utilities — live acquisition path.

Live callers:
- score_injection_event         ← _InjectionMonitor confirmation layer
- measure_delta_spr             ← cycle result reporting
- validate_sp_orientation       ← calibration orchestrator
- apply_centered_median_filter  ← sensorgram smoothing utility
"""

import numpy as np

from affilabs.utils.logger import logger


def apply_centered_median_filter(
    values: np.ndarray,
    current_index: int,
    window_size: int,
) -> float:
    """Apply centered median filter at a specific index.

    Uses a centered window around the current point for better temporal accuracy.
    For points near the beginning where a full centered window isn't available,
    uses all available data up to that point.

    Args:
        values: Array of values to filter (may contain NaN)
        current_index: Index of point to filter
        window_size: Median filter window size (should be odd)

    Returns:
        float: Filtered value (median of window), or np.nan if input is NaN

    """
    # If current value is NaN, return NaN
    if current_index >= len(values):
        return np.nan

    if np.isnan(values[current_index]):
        return np.nan

    # Not enough data for filtering yet
    if len(values) <= window_size:
        # Use all available data for initial values
        return float(np.nanmedian(values[: current_index + 1]))

    # Center the window on current point
    half_win = window_size // 2
    start_idx = max(0, current_index - half_win)
    end_idx = min(len(values), current_index + half_win + 1)

    window_data = values[start_idx:end_idx]

    return float(np.nanmedian(window_data))



def validate_sp_orientation(
    p_spectrum: np.ndarray,
    s_spectrum: np.ndarray,
    wavelengths: np.ndarray,
    window_px: int = 200,
) -> dict:
    """Validate S/P polarizer orientation by analyzing transmission spectrum ONLY.

    IMPORTANT: This function analyzes the TRANSMISSION SPECTRUM (P/S ratio) to detect
    polarizer orientation. Raw P vs S intensity comparison is NOT used here - that's
    only done during servo/polarizer calibration to find optimal positions.

    DETECTION METHOD:
    Analyze transmission spectrum (P/S ratio) for:
    - Peak shape (dip vs hill)
    - Peak depth (transmission reduction at SPR wavelength)
    - Peak width (FWHM characteristics)
    - Triangulation (peak vs edges comparison)

    For correct orientation:
    - Transmission shows a DIP (valley, minimum) due to SPR absorption
    - Peak value is LOWER than surrounding edge baselines
    - Dip depth indicates SPR coupling strength

    For inverted orientation (swapped S/P positions):
    - Transmission shows a PEAK (hill, maximum) instead of dip
    - Peak value is HIGHER than surrounding edge baselines
    - No SPR absorption visible (high transmission at resonance wavelength)

    Key insight: With weak SPR coupling (marginal water contact), the dip may be
    very shallow or barely visible. We need to distinguish between:
    - Shallow dip (correct orientation, weak coupling)
    - Actual peak/hill (inverted orientation)

    Method:
    1. Calculate transmission = P/S ratio
    2. Find local min/max in SPR region (600-750nm)
    3. Compare peak vs edge baselines
    4. Determine if structure is dip (correct) or peak (inverted)

    Args:
        p_spectrum: P-mode intensity spectrum
        s_spectrum: S-mode reference spectrum
        wavelengths: Wavelength array
        window_px: Number of pixels to sample on each side of peak (default 200)

    Returns:
        dict with:
            - 'orientation_correct': bool - True if dip detected (correct), False if peak (inverted)
            - 'peak_idx': int - Index of peak/dip
            - 'peak_wl': float - Wavelength of peak/dip
            - 'peak_value': float - Transmission value at peak
            - 'left_value': float - Mean transmission left of peak
            - 'right_value': float - Mean transmission right of peak
            - 'is_flat': bool - True if spectrum is flat (saturation or dark)
            - 'confidence': float - Confidence score (0-1) based on peak prominence

    """
    # Calculate transmission
    transmission = calculate_transmission(p_spectrum, s_spectrum)

    # Find peak (could be min or max depending on orientation)
    min_idx = np.argmin(transmission)
    max_idx = np.argmax(transmission)

    min_val = transmission[min_idx]

    # Determine which is more prominent
    spectrum_range = np.ptp(transmission)  # peak-to-peak amplitude

    # Check if flat (saturation or dark signal)
    is_flat = spectrum_range < 5.0  # Less than 5% variation = flat

    if is_flat:
        logger.warning(
            f"[WARN] S/P validation: Flat transmission spectrum (range={spectrum_range:.2f}%) - possible saturation or dark signal",
        )
        return {
            "orientation_correct": None,  # Cannot determine
            "peak_idx": min_idx,
            "peak_wl": wavelengths[min_idx],
            "peak_value": min_val,
            "left_value": 0,
            "right_value": 0,
            "is_flat": True,
            "confidence": 0.0,
        }

    # NEW APPROACH: Check for local structure in SPR region (600-750nm) first
    # This is more robust than global min/max for weak coupling cases
    spr_region_start = np.searchsorted(wavelengths, 600)
    spr_region_end = np.searchsorted(wavelengths, 750)

    # Initialize edge values (will be overwritten if SPR region is valid)
    left_edge_mean = transmission[0] if len(transmission) > 0 else 0
    right_edge_mean = transmission[-1] if len(transmission) > 0 else 0

    # Initialize confidence (will be calculated based on structure prominence)
    confidence = 0.5  # Default moderate confidence

    if spr_region_end > spr_region_start:
        spr_transmission = transmission[spr_region_start:spr_region_end]
        spr_wavelengths = wavelengths[spr_region_start:spr_region_end]

        # Find local minimum in SPR region
        local_min_idx = np.argmin(spr_transmission)
        local_max_idx = np.argmax(spr_transmission)

        local_min_val = spr_transmission[local_min_idx]
        local_max_val = spr_transmission[local_max_idx]

        # Check structure: compare center vs edges of SPR region
        edge_width = min(50, len(spr_transmission) // 4)
        left_edge_mean = np.mean(spr_transmission[:edge_width])
        right_edge_mean = np.mean(spr_transmission[-edge_width:])
        edge_mean = (left_edge_mean + right_edge_mean) / 2

        # Calculate how much the min and max differ from edges
        min_deviation = local_min_val - edge_mean
        max_deviation = local_max_val - edge_mean

        logger.debug("   S/P validation in 600-750nm region:")
        logger.debug(
            f"     Min at {spr_wavelengths[local_min_idx]:.1f}nm: {local_min_val:.1f}% (deviation: {min_deviation:+.1f}%)",
        )
        logger.debug(
            f"     Max at {spr_wavelengths[local_max_idx]:.1f}nm: {local_max_val:.1f}% (deviation: {max_deviation:+.1f}%)",
        )
        logger.debug(
            f"     Edges: left={left_edge_mean:.1f}%, right={right_edge_mean:.1f}%",
        )

        # Decision logic:
        # - If min is BELOW edges: correct orientation (has a dip)
        # - If max is ABOVE edges MORE than min is below: inverted (has a peak instead)
        # - Allow some tolerance for weak coupling (±5% is acceptable noise)

        if min_deviation < -5:  # Clear dip present
            orientation_correct = True
            peak_idx = spr_region_start + local_min_idx
            peak_val = local_min_val
            confidence = min(
                1.0,
                abs(min_deviation) / 30.0,
            )  # Scale: 30% deviation = 100% confidence
            logger.debug(
                f"   ✓ SPR DIP detected: {min_deviation:.1f}% below edges - CORRECT orientation",
            )
        elif max_deviation > 10:  # Clear peak present (inverted)
            orientation_correct = False
            peak_idx = spr_region_start + local_max_idx
            peak_val = local_max_val
            confidence = min(1.0, max_deviation / 30.0)
            logger.debug(
                f"   ✗ SPR PEAK detected: {max_deviation:+.1f}% above edges - INVERTED orientation",
            )
        elif abs(min_deviation) > abs(
            max_deviation,
        ):  # Subtle dip more prominent than peak
            orientation_correct = True
            peak_idx = spr_region_start + local_min_idx
            peak_val = local_min_val
            confidence = min(
                0.7,
                abs(min_deviation) / 30.0,
            )  # Lower confidence for weak signal
            logger.debug(
                f"   ✓ Subtle SPR dip detected (weak coupling): {min_deviation:.1f}% - CORRECT orientation",
            )
        else:  # Weak structure, cannot reliably determine orientation
            logger.warning(
                "   [WARN] Weak SPR structure in 600-750nm - cannot determine orientation",
            )
            # Return None (indeterminate) rather than guessing
            orientation_correct = None  # Cannot determine with confidence
            peak_idx = min_idx
            peak_val = min_val
            confidence = 0.1  # Very low confidence for indeterminate
    else:
        # No valid SPR region - cannot determine orientation
        logger.warning("   [WARN] Invalid wavelength range for SPR analysis")
        orientation_correct = None  # Cannot determine without valid SPR region
        peak_idx = min_idx
        peak_val = min_val
        confidence = 0.0  # Zero confidence for invalid range

    return {
        "orientation_correct": orientation_correct,
        "peak_idx": peak_idx,
        "peak_wl": wavelengths[peak_idx],
        "peak_value": peak_val,
        "left_value": left_edge_mean,
        "right_value": right_edge_mean,
        "is_flat": False,
        "confidence": confidence,
    }


# ─────────────────────────────────────────────────────────────────────────────
# User-facing display labels for event flags.
# Internal flag strings (keys) are used throughout the codebase for
# programmatic checks.  UI components that display flags to users must go
# through this mapping so the copy is consistent and can be updated in one
# place without touching logic code.
#
# Rule: if a flag is not in this dict, fall back to flag.replace('_', ' ').title()
# ─────────────────────────────────────────────────────────────────────────────
FLAG_USER_LABELS: dict[str, str] = {
    # Detection outcomes
    'INJECTION_DETECTED': 'Injection',
    'POSSIBLE_BUBBLE':    'Bubble trouble',
    'POSSIBLE_LEAK':      'Check for leak',
    'BASELINE_DRIFT':     'Baseline drift',
    # Spike classifier (internal — not normally shown, included for completeness)
    'SINGLE_SPIKE':       'Spike',
}


def flag_display_label(flag: str) -> str:
    """Return the user-facing label for an internal flag string."""
    return FLAG_USER_LABELS.get(flag, flag.replace('_', ' ').title())


# ─────────────────────────────────────────────────────────────────────────────
# Injection event classifiers (v3 two-stage architecture)
#
# Stage 1 — _classify_spike:  What shape is the disturbance?
#   NONE              No exceedance above 3σ at all (matched-buffer injection or drift)
#   SINGLE_SPIKE      1–2 points above 3σ, returns within 3 s, no trend change
#   INJECTION_TRANSIENT  Larger spike, signal decays over 5–30 s, P2P normalises after
#   BUBBLE            Spike sustained >20 s OR P2P stays elevated / signal noisier after
#   STEP_ONLY         No spike, but a clear level shift between pre and post halves
#
# Stage 2 — _classify_trend:  What did the sensorgram do after the transient settled?
#   BINDING_UP        Post mean > pre mean + 1σ, detrended σ similar to before
#   BINDING_DOWN      Post mean < pre mean − 1σ (e.g. regen, bulk RI artefact)
#   DRIFT_UP/DOWN     Slow monotonic drift, no spike, detrended σ unchanged
#   NOISY             Post detrended σ > 2.5× pre σ — signal degraded
#   FLAT              No detectable change
#
# Combined outcome (spike → trend):
#   SINGLE_SPIKE               → ignore
#   BUBBLE                     → POSSIBLE_BUBBLE  (skip trend)
#   INJECTION_TRANSIENT/NONE/STEP_ONLY:
#     BINDING_UP               → INJECTION_DETECTED
#     BINDING_DOWN             → BASELINE_DRIFT  (false positive, signal went negative)
#     DRIFT_UP / DRIFT_DOWN    → BASELINE_DRIFT
#     NOISY                    → POSSIBLE_BUBBLE
#     FLAT                     → (no event)
#   Independent %T leak check  → POSSIBLE_LEAK  (any path, large sustained %T drop)
# ─────────────────────────────────────────────────────────────────────────────

def _classify_spike(
    times: np.ndarray,
    wavelengths: np.ndarray,
    p2p_arr: np.ndarray,
    pre_mean: float,
    pre_std: float,
    event_start_idx: int,
) -> tuple[str, dict]:
    """Stage 1 — classify the shape of the disturbance in the event region.

    Args:
        times, wavelengths, p2p_arr: full arrays (nm)
        pre_mean / pre_std: baseline detrended statistics
        event_start_idx: index where the baseline ends and the event region begins

    Returns:
        (spike_class, metrics_dict)
    """
    n = len(times)
    event_wl  = wavelengths[event_start_idx:]
    event_t   = times[event_start_idx:]
    event_p2p = p2p_arr[event_start_idx:]
    thresh    = 3.0 * max(pre_std, 0.01)   # 3σ exceedance threshold (nm)

    _empty_metrics: dict = {
        'peak_sigma': 0.0, 'frames_above': 0, 'return_time_s': float('inf'),
        'returned_to_baseline': True, 'p2p_sustained': False,
        'p2p_ratio_tail': 1.0, 'noise_ratio': 1.0,
    }

    if len(event_wl) < 2:
        return 'NONE', _empty_metrics

    deviations = np.abs(event_wl - pre_mean)
    peak_dev   = float(np.max(deviations))
    peak_sigma = peak_dev / max(pre_std, 0.01)

    # No exceedance — step-only or no event
    if peak_sigma < 3.0:
        return 'STEP_ONLY', {**_empty_metrics, 'peak_sigma': peak_sigma}

    peak_idx_local = int(np.argmax(deviations))
    frames_above   = int(np.sum(deviations > thresh))

    # Time for signal to return within 1.5σ of baseline after the peak
    return_time_s = float('inf')
    for i in range(peak_idx_local + 1, len(event_wl)):
        if abs(event_wl[i] - pre_mean) < 1.5 * max(pre_std, 0.01):
            return_time_s = float(event_t[i] - event_t[peak_idx_local])
            break

    # Tail window: last third of the event region (min 3 pts)
    lookback = max(3, len(event_wl) // 3)
    tail_wl  = event_wl[-lookback:]
    tail_t   = event_t[-lookback:]

    # P2P in the tail vs baseline P2P
    baseline_p2p = float(np.median(p2p_arr[:event_start_idx])) if event_start_idx > 3 else float(np.median(p2p_arr))
    tail_p2p     = float(np.mean(event_p2p[-lookback:]))
    p2p_ratio_tail = tail_p2p / max(baseline_p2p, 1e-6)
    p2p_sustained  = p2p_ratio_tail > 2.0

    # Detrended σ of the tail — is signal noisier than before?
    try:
        t_norm           = tail_t - tail_t[0]
        residuals        = tail_wl - np.polyval(np.polyfit(t_norm, tail_wl, 1), t_norm)
        post_detrended_std = float(np.std(residuals))
    except Exception:
        post_detrended_std = float(np.std(tail_wl))
    noise_ratio = post_detrended_std / max(pre_std, 0.01)

    returned_to_baseline = abs(float(np.mean(tail_wl)) - pre_mean) < 1.5 * max(pre_std, 0.01)

    metrics = {
        'peak_sigma':          peak_sigma,
        'frames_above':        frames_above,
        'return_time_s':       return_time_s,
        'returned_to_baseline': returned_to_baseline,
        'p2p_sustained':       p2p_sustained,
        'p2p_ratio_tail':      p2p_ratio_tail,
        'noise_ratio':         noise_ratio,
    }

    # ── Decision rules ────────────────────────────────────────────────────────
    # 1. Single noise spike: ≤ 2 frames, returns within 3 s, P2P normalises
    if frames_above <= 2 and return_time_s < 3.0 and not p2p_sustained:
        return 'SINGLE_SPIKE', metrics

    # 2. Bubble / degraded signal: P2P stays elevated OR signal stays noisy
    if p2p_sustained or noise_ratio > 2.5:
        return 'BUBBLE', metrics

    # 3. Everything else: a real transient (injection or artefact — let trend decide)
    return 'INJECTION_TRANSIENT', metrics


def _classify_trend(
    times: np.ndarray,
    wavelengths: np.ndarray,
    pre_mean: float,
    pre_std: float,
    event_start_idx: int,
    settle_pts: int = 10,
) -> tuple[str, dict]:
    """Stage 2 — classify the sensorgram trend AFTER the transient has settled.

    Args:
        times, wavelengths: full arrays (nm)
        pre_mean / pre_std: baseline statistics
        event_start_idx: index where the baseline ends
        settle_pts: number of points to skip after event_start_idx to let the
                    transient die down before measuring the post-event trend

    Returns:
        (trend_class, metrics_dict)
    """
    n          = len(times)
    post_start = min(event_start_idx + settle_pts, n - 1)
    if n - post_start < 3:
        post_start = event_start_idx

    post_wl = wavelengths[post_start:]
    post_t  = times[post_start:]

    _empty_metrics: dict = {
        'post_mean': pre_mean, 'level_shift': 0.0, 'level_shift_sigma': 0.0,
        'post_slope': 0.0, 'post_detrended_std': pre_std, 'noise_ratio': 1.0,
    }

    if len(post_wl) < 3:
        return 'FLAT', _empty_metrics

    post_mean    = float(np.mean(post_wl))
    level_shift  = post_mean - pre_mean          # signed: + = up, − = down
    level_shift_sigma = level_shift / max(pre_std, 0.01)

    # Detrended σ of post window (removes any residual drift before measuring noise)
    try:
        t_norm      = post_t - post_t[0]
        post_fit    = np.polyfit(t_norm, post_wl, 1)
        post_slope  = float(post_fit[0])          # nm/s
        residuals   = post_wl - np.polyval(post_fit, t_norm)
        post_detrended_std = float(np.std(residuals))
    except Exception:
        post_slope         = 0.0
        post_detrended_std = float(np.std(post_wl))

    noise_ratio = post_detrended_std / max(pre_std, 0.01)

    metrics = {
        'post_mean':           post_mean,
        'level_shift':         level_shift,
        'level_shift_sigma':   level_shift_sigma,
        'post_slope':          post_slope,
        'post_detrended_std':  post_detrended_std,
        'noise_ratio':         noise_ratio,
    }

    # ── Decision rules ────────────────────────────────────────────────────────
    # Still noisy after the transient settled → ongoing bubble / bad coupling
    if noise_ratio > 2.5:
        return 'NOISY', metrics

    # Clear upward level shift — analyte bound
    if level_shift_sigma > 1.0:
        return 'BINDING_UP', metrics

    # Downward level shift — unphysical for binding (regen, bulk RI artefact)
    if level_shift_sigma < -1.0:
        return 'BINDING_DOWN', metrics

    # Monotonic drift without level shift
    if abs(post_slope) > 0.02:   # nm/s
        return ('DRIFT_UP' if post_slope > 0 else 'DRIFT_DOWN'), metrics

    return 'FLAT', metrics


def score_injection_event(
    times: np.ndarray,
    wavelengths: np.ndarray,
    p2p_values: np.ndarray | None,
    transmittance: np.ndarray | None,
    baseline_window_s: float = 30.0,
    recovery_window_s: float = 20.0,
) -> dict:
    """Two-stage injection event scorer (v3).

    Stage 1 (_classify_spike):  what shape is the disturbance?
    Stage 2 (_classify_trend):  what did the sensorgram do after it settled?
    Combined output produces flags and confidence.

    Public interface is unchanged — all callers pass the same arguments.

    Args:
        times:             Time array (seconds).
        wavelengths:       Resonance wavelength array (nm).
        p2p_values:        Peak-to-peak variation array (nm). None → rolling-std proxy.
        transmittance:     Mean % transmittance (0–100). None → skip %T leak check.
        baseline_window_s: History used for rolling baselines (default 30 s).
        recovery_window_s: Lookback for %T recovery (default 20 s).

    Returns:
        dict with keys: score, feature_count, injection_time, confidence, flags, features
    """
    _empty = {
        'score': 0.0, 'feature_count': 0, 'injection_time': None,
        'confidence': 0.0, 'flags': [], 'features': {},
    }
    try:
        n = len(times)
        if n < 10 or len(wavelengths) != n:
            return _empty

        now_t = times[-1]

        # ── Baseline window ───────────────────────────────────────────────────
        bl_mask = times >= (now_t - baseline_window_s)
        bl_idx  = int(np.argmax(bl_mask)) if bl_mask.any() else 0
        if (n - bl_idx) < 5:
            bl_idx = max(0, n - max(5, n // 3))

        # Split window in half: pre = baseline, post = event region
        half_idx = bl_idx + max(1, (n - bl_idx) // 2)

        # Baseline statistics: detrended σ so a drifting baseline isn't penalised
        pre_wl = wavelengths[bl_idx:half_idx]
        pre_t  = times[bl_idx:half_idx]
        pre_mean = float(np.mean(pre_wl))
        try:
            t_norm       = pre_t - pre_t[0]
            pre_residuals = pre_wl - np.polyval(np.polyfit(t_norm, pre_wl, 1), t_norm)
            pre_std      = max(float(np.std(pre_residuals)), 0.01)
        except Exception:
            pre_std = max(float(np.std(pre_wl)), 0.01)

        # ── P2P proxy ─────────────────────────────────────────────────────────
        if p2p_values is not None and len(p2p_values) == n:
            p2p_arr = np.asarray(p2p_values, dtype=float)
        else:
            p2p_arr = np.array([
                np.std(wavelengths[max(0, i - 4): i + 1])
                for i in range(n)
            ])

        # ── Stage 1: Spike classifier ─────────────────────────────────────────
        spike_class, spike_m = _classify_spike(
            times, wavelengths, p2p_arr, pre_mean, pre_std, half_idx,
        )

        # ── Stage 2: Trend classifier ─────────────────────────────────────────
        # settle_pts: skip ~10 s of transient before measuring post-event level
        trend_class, trend_m = _classify_trend(
            times, wavelengths, pre_mean, pre_std, half_idx, settle_pts=10,
        )

        # ── Combine → flags ───────────────────────────────────────────────────
        flags:         list[str] = []
        score:         float     = 0.0
        feature_count: int       = 0
        injection_time: float | None = None

        if spike_class == 'SINGLE_SPIKE':
            # Noise transient — nothing to report
            pass

        elif spike_class == 'BUBBLE':
            # Cross-check trend: a drifting baseline can produce an artificially
            # low pre_std (briefly flat window), making p2p_ratio_tail > 2.0 and
            # triggering a false BUBBLE.  Use trend + absolute level-shift to
            # decide whether this is really a bubble or a baseline artifact.
            level_shift_nm = abs(trend_m.get('level_shift', 0.0))
            if trend_class in ('DRIFT_UP', 'DRIFT_DOWN'):
                # Ongoing drift — not a bubble
                flags.append('BASELINE_DRIFT')
            elif trend_class == 'BINDING_UP' and level_shift_nm < 0.5:
                # level_shift_sigma > 1.0 but actual shift < 0.5 nm → pre_std was
                # artificially deflated; suppress the false POSSIBLE_BUBBLE.
                flags.append('BASELINE_DRIFT')
            else:
                flags.append('POSSIBLE_BUBBLE')

        else:
            # INJECTION_TRANSIENT, NONE, or STEP_ONLY — trend decides outcome
            if trend_class == 'BINDING_UP':
                flags.append('INJECTION_DETECTED')
                # Base score from level-shift magnitude (capped at 1.0)
                lss   = abs(trend_m.get('level_shift_sigma', 1.0))
                score = float(np.clip(0.70 + 0.10 * min(lss, 3.0), 0.70, 1.0))
                feature_count = 2 if spike_class == 'INJECTION_TRANSIENT' else 1

                # %T recovery adds evidence (up to +0.10)
                if transmittance is not None and len(transmittance) == n:
                    t_arr    = np.asarray(transmittance, dtype=float)
                    bl_t     = float(np.mean(t_arr[bl_idx:half_idx]))
                    min_t    = float(np.min(t_arr[half_idx:]))
                    cur_t    = float(np.mean(t_arr[-3:]))
                    t_drop   = max(0.0, bl_t - min_t)
                    t_rec    = float(np.clip((cur_t - min_t) / max(t_drop, 1e-6), 0.0, 1.0))
                    if t_drop > 0.5 and t_rec > 0.55:
                        score = min(1.0, score + 0.10)
                        feature_count += 1

                # Injection timestamp: first point where wavelength crosses 2σ above pre_mean
                for i in range(half_idx, n):
                    if wavelengths[i] - pre_mean > 2.0 * pre_std:
                        injection_time = float(times[i])
                        break
                if injection_time is None:
                    injection_time = float(times[half_idx])

            elif trend_class == 'BINDING_DOWN':
                # Signal went downward after spike — not a binding injection.
                # Treat as baseline disturbance (e.g. temperature, bulk RI artefact).
                flags.append('BASELINE_DRIFT')

            elif trend_class in ('DRIFT_UP', 'DRIFT_DOWN'):
                flags.append('BASELINE_DRIFT')

            elif trend_class == 'NOISY':
                # Transient didn't fully settle and signal stayed noisy → bubble
                flags.append('POSSIBLE_BUBBLE')

            # FLAT: no detectable event — leave flags empty

        # ── Independent %T leak check ─────────────────────────────────────────
        # Large, sustained %T drop that didn't recover → possible flow cell leak.
        # Checked on every path (bubble or not) because a leak can present without
        # a visible λ spike if the channel was already blocked.
        if 'POSSIBLE_LEAK' not in flags and transmittance is not None and len(transmittance) == n:
            t_arr    = np.asarray(transmittance, dtype=float)
            bl_t     = float(np.mean(t_arr[bl_idx:half_idx]))
            min_t    = float(np.min(t_arr[half_idx:]))
            cur_t    = float(np.mean(t_arr[-3:]))
            t_drop   = max(0.0, bl_t - min_t)
            t_rec    = float(np.clip((cur_t - min_t) / max(t_drop, 1e-6), 0.0, 1.0))
            sustained = (now_t - times[half_idx]) > 30.0
            if t_drop > 2.0 and t_rec < 0.20 and sustained:
                flags.append('POSSIBLE_LEAK')

        confidence = float(np.clip(score / 0.65, 0.0, 1.0)) if 'INJECTION_DETECTED' in flags else 0.0

        logger.debug(
            f"score_injection_event v3: spike={spike_class} trend={trend_class} "
            f"pre_std={pre_std:.3f}nm level_shift={trend_m.get('level_shift_sigma', 0):.2f}σ "
            f"noise_ratio={trend_m.get('noise_ratio', 0):.2f} score={score:.2f} flags={flags}"
        )

        return {
            'score':          score,
            'feature_count':  feature_count,
            'injection_time': injection_time,
            'confidence':     confidence,
            'flags':          flags,
            'features': {
                'spike_class':  spike_class,
                'trend_class':  trend_class,
                **spike_m,
                **{f'trend_{k}': v for k, v in trend_m.items()},
            },
        }

    except Exception as e:
        logger.debug(f"score_injection_event failed: {e}")
        return _empty
