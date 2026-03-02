"""
OQ Suite 3 — Calibration & Signal Quality
Req IDs: OQ-CAL-001 to OQ-CAL-011

Verifies CalibrationMetrics thresholds, CalibrationData construction,
SensorIQClassifier zone boundaries, and TimelineContext time math.
No hardware required — domain model + numpy only.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from affilabs.domain.calibration_data import CalibrationData, CalibrationMetrics
from affilabs.domain.timeline import EventContext, TimelineContext
from affilabs.utils.sensor_iq import SensorIQClassifier, WavelengthZone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _good_metrics() -> CalibrationMetrics:
    return CalibrationMetrics(
        snr=500.0,
        peak_intensity=40000.0,
        mean_intensity=35000.0,
        std_dev=200.0,
        dynamic_range=39700.0,
        saturation_percent=0.5,
    )


def _make_calibration_data() -> CalibrationData:
    wavelengths = np.linspace(560, 720, 1797)
    ref = np.ones(1797) * 32000.0
    channels = {"a": ref.copy(), "b": ref.copy(), "c": ref.copy(), "d": ref.copy()}
    return CalibrationData(
        s_pol_ref=channels,
        wavelengths=wavelengths,
        p_mode_intensities={"a": 128, "b": 128, "c": 128, "d": 128},
        s_mode_intensities={"a": 96, "b": 96, "c": 96, "d": 96},
    )


# ---------------------------------------------------------------------------
# CalibrationMetrics threshold tests
# ---------------------------------------------------------------------------

@pytest.mark.req("OQ-CAL-001")
def test_metrics_is_saturated_true():
    """saturation_percent=10.0 must trigger is_saturated() == True."""
    m = CalibrationMetrics(
        snr=500.0, peak_intensity=40000.0, mean_intensity=35000.0,
        std_dev=200.0, dynamic_range=39700.0, saturation_percent=10.0,
    )
    assert m.is_saturated() is True


@pytest.mark.req("OQ-CAL-002")
def test_metrics_is_saturated_false():
    """saturation_percent=1.0 must NOT trigger is_saturated()."""
    m = CalibrationMetrics(
        snr=500.0, peak_intensity=40000.0, mean_intensity=35000.0,
        std_dev=200.0, dynamic_range=39700.0, saturation_percent=1.0,
    )
    assert m.is_saturated() is False


@pytest.mark.req("OQ-CAL-003")
def test_metrics_not_low_signal():
    """High SNR + high peak must NOT trigger is_low_signal()."""
    m = _good_metrics()
    assert m.is_low_signal() is False


@pytest.mark.req("OQ-CAL-004")
def test_metrics_is_acceptable():
    """Metrics with good SNR, high peak, low saturation must be acceptable."""
    m = _good_metrics()
    assert m.is_acceptable() is True


# ---------------------------------------------------------------------------
# CalibrationData construction
# ---------------------------------------------------------------------------

@pytest.mark.req("OQ-CAL-005")
def test_calibration_data_channel_keys():
    """CalibrationData with 4-channel refs must have a/b/c/d in s_pol_ref."""
    cal = _make_calibration_data()
    for ch in ("a", "b", "c", "d"):
        assert ch in cal.s_pol_ref, f"Missing channel '{ch}' in s_pol_ref"


@pytest.mark.req("OQ-CAL-006")
def test_calibration_data_roi_defaults():
    """CalibrationData must default roi_start=560.0 and roi_end=720.0."""
    cal = _make_calibration_data()
    assert cal.roi_start == 560.0
    assert cal.roi_end == 720.0


# ---------------------------------------------------------------------------
# SensorIQClassifier zone tests
# ---------------------------------------------------------------------------

@pytest.mark.req("OQ-CAL-007")
def test_zone_good():
    """640 nm must classify as GOOD zone."""
    clf = SensorIQClassifier()
    assert clf.classify_wavelength_zone(640.0) == WavelengthZone.GOOD


@pytest.mark.req("OQ-CAL-008")
def test_zone_out_of_bounds_low():
    """550 nm must classify as OUT_OF_BOUNDS_LOW."""
    clf = SensorIQClassifier()
    assert clf.classify_wavelength_zone(550.0) == WavelengthZone.OUT_OF_BOUNDS_LOW


@pytest.mark.req("OQ-CAL-009")
def test_zone_questionable_high():
    """700 nm must classify as QUESTIONABLE_HIGH."""
    clf = SensorIQClassifier()
    assert clf.classify_wavelength_zone(700.0) == WavelengthZone.QUESTIONABLE_HIGH


# ---------------------------------------------------------------------------
# TimelineContext time math
# ---------------------------------------------------------------------------

@pytest.mark.req("OQ-CAL-010")
def test_timeline_context_normalize_time():
    """normalize_time() must return absolute_time - recording_start_offset."""
    ctx = TimelineContext(recording_start_time=1000.0, recording_start_offset=5.0)
    # normalize converts an absolute (elapsed) time to recording-relative time
    result = ctx.normalize_time(15.0)
    # Expected: 15.0 - 5.0 = 10.0
    assert abs(result - 10.0) < 1e-9, f"Expected 10.0, got {result}"


@pytest.mark.req("OQ-CAL-011")
def test_timeline_context_round_trip():
    """denormalize_time(normalize_time(t)) must equal t."""
    ctx = TimelineContext(recording_start_time=2000.0, recording_start_offset=7.3)
    for t in (0.0, 5.0, 100.0, 999.9):
        normalized = ctx.normalize_time(t)
        restored = ctx.denormalize_time(normalized)
        assert abs(restored - t) < 1e-9, (
            f"Round-trip failed for t={t}: got {restored}"
        )
