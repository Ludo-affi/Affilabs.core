"""
OQ Suite 6 — Optical Fault Detection
Req IDs: OQ-FLT-001 to OQ-FLT-005

Verifies AirBubbleDetector singleton/state and injection event scorer.
Qt-free — monkey-patches _fire_alert to capture emissions without Qt signals.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# OQ-FLT-001 — AirBubbleDetector singleton
# ---------------------------------------------------------------------------

@pytest.mark.req("OQ-FLT-001")
def test_air_bubble_detector_singleton():
    """get_instance() must return the same object on repeated calls."""
    from affilabs.services.air_bubble_detector import AirBubbleDetector

    inst1 = AirBubbleDetector.get_instance()
    inst2 = AirBubbleDetector.get_instance()
    assert inst1 is inst2, "AirBubbleDetector must be a singleton"


# ---------------------------------------------------------------------------
# OQ-FLT-002 — Detection fires after high-variance + %T-drop sequence
# ---------------------------------------------------------------------------

@pytest.mark.req("OQ-FLT-002")
def test_air_bubble_detector_fires_on_spike():
    """
    After feeding stable wavelengths (high %T baseline) followed by a
    high-variance + low-%T spike sequence, _fire_alert must be called.

    The two-stage algorithm requires:
      Stage 1: rolling std(wavelength, 30-frame window) > 0.056 nm
      Stage 2: mean_%T drops >10 pp from the baseline seen in the window
    """
    from affilabs.services.air_bubble_detector import AirBubbleDetector

    detector = AirBubbleDetector.get_instance()
    detector.reset_session()
    # Reset cooldown so the test can fire immediately
    detector._last_alert_ts = {}

    rng = np.random.default_rng(42)
    channel = "A"

    # Monkey-patch _fire_alert to capture calls without needing Qt signal
    fired: list[tuple] = []
    original_fire = detector._fire_alert

    def _mock_fire(ch, std_nm, t_drop_pp):
        fired.append((ch, std_nm, t_drop_pp))

    detector._fire_alert = _mock_fire

    try:
        # Feed 35 stable points to fill the 30-frame std window and %T history
        for i in range(35):
            detector.feed(
                channel=channel,
                wavelength_nm=620.0 + rng.normal(0, 0.005),  # very stable
                mean_transmittance=85.0,                       # high %T baseline
                timestamp=float(i),
            )

        # Feed 5 spike frames: large std (>0.056 nm) AND dropped %T (>10 pp)
        for i in range(5):
            spike_wl = 620.0 + rng.normal(0, 5.0)  # std ≈ 5 nm >> 0.056 nm threshold
            detector.feed(
                channel=channel,
                wavelength_nm=spike_wl,
                mean_transmittance=60.0,  # dropped 25 pp from 85% → triggers stage 2
                timestamp=float(35 + i),
            )
    finally:
        detector._fire_alert = original_fire

    assert len(fired) > 0, (
        "AirBubbleDetector._fire_alert was not called for high-std + low-%T sequence. "
        "Check _STD_THRESHOLD_NM and _T_DROP_THRESHOLD_PP thresholds."
    )


# ---------------------------------------------------------------------------
# OQ-FLT-003 — reset_session clears history
# ---------------------------------------------------------------------------

@pytest.mark.req("OQ-FLT-003")
def test_air_bubble_detector_reset_clears_state():
    """reset_session() must clear all wavelength and %T history."""
    from affilabs.services.air_bubble_detector import AirBubbleDetector

    detector = AirBubbleDetector.get_instance()

    # Add some history by feeding a few points
    detector.feed(channel="B", wavelength_nm=620.0, mean_transmittance=85.0, timestamp=0.0)
    detector.feed(channel="B", wavelength_nm=621.0, mean_transmittance=84.0, timestamp=1.0)

    detector.reset_session()

    # After reset, wavelength and %T history deques must be empty
    wl_hist = getattr(detector, "_wl_history", {})
    t_hist = getattr(detector, "_t_history", {})

    assert len(wl_hist) == 0, f"_wl_history must be empty after reset, got {wl_hist}"
    assert len(t_hist) == 0, f"_t_history must be empty after reset, got {t_hist}"


# ---------------------------------------------------------------------------
# OQ-FLT-004 — Injection scorer detects rising signal
# ---------------------------------------------------------------------------

@pytest.mark.req("OQ-FLT-004")
def test_injection_scorer_detects_injection():
    """score_injection_event() with a rising wavelength profile must return score > 0.3."""
    from affilabs.utils.spr_signal_processing import score_injection_event

    # 120 seconds total; injection at t=30 s
    times = np.linspace(0, 120, 480)
    # Flat baseline for first 30 s, then rising step (injection)
    wavelengths = np.where(
        times < 30.0,
        620.0 + np.random.default_rng(1).normal(0, 0.15, len(times)),
        620.0 + (times - 30.0) * 0.08 + np.random.default_rng(2).normal(0, 0.15, len(times)),
    )
    p2p = np.ones(len(times)) * 0.3
    transmittance = np.ones(len(times)) * 80.0

    result = score_injection_event(
        times=times,
        wavelengths=wavelengths,
        p2p_values=p2p,
        transmittance=transmittance,
        baseline_window_s=25.0,
        recovery_window_s=10.0,
    )

    assert isinstance(result, dict), "score_injection_event must return a dict"
    score = result.get("score", result.get("confidence", 0.0))
    assert float(score) > 0.3, (
        f"Injection scorer returned low score {score:.3f} for a rising signal"
    )


# ---------------------------------------------------------------------------
# OQ-FLT-005 — Injection scorer does not fire on flat baseline
# ---------------------------------------------------------------------------

@pytest.mark.req("OQ-FLT-005")
def test_injection_scorer_no_false_positive():
    """score_injection_event() with a flat baseline must return score < 0.6."""
    from affilabs.utils.spr_signal_processing import score_injection_event

    rng = np.random.default_rng(99)
    times = np.linspace(0, 120, 480)
    wavelengths = 620.0 + rng.normal(0, 0.2, len(times))  # pure noise, no trend
    p2p = np.ones(len(times)) * 0.3
    transmittance = np.ones(len(times)) * 80.0

    result = score_injection_event(
        times=times,
        wavelengths=wavelengths,
        p2p_values=p2p,
        transmittance=transmittance,
        baseline_window_s=25.0,
        recovery_window_s=10.0,
    )

    score = result.get("score", result.get("confidence", 1.0))
    assert float(score) < 0.6, (
        f"Injection scorer returned high score {score:.3f} for flat baseline (false positive)"
    )
