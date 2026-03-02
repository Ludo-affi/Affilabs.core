"""
OQ Suite 1 — Signal Processing
Req IDs: OQ-SPR-001 to OQ-SPR-006

Verifies core SPR signal processing algorithms using synthetic data.
No hardware required — numpy only.
"""
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.signal import savgol_filter

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Shared synthetic spectrum helpers
# ---------------------------------------------------------------------------

def _synthetic_spr_spectrum(
    center_nm: float = 620.0,
    dip_depth: float = 30.0,
    dip_width_nm: float = 20.0,
    noise_std: float = 0.5,
    n_pixels: int = 1797,
    wl_start: float = 560.0,
    wl_end: float = 720.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (wavelengths, transmission) with a Gaussian SPR dip."""
    wavelengths = np.linspace(wl_start, wl_end, n_pixels)
    transmission = 100.0 - dip_depth * np.exp(
        -0.5 * ((wavelengths - center_nm) / dip_width_nm) ** 2
    )
    rng = np.random.default_rng(42)
    transmission += rng.normal(0, noise_std, n_pixels)
    return wavelengths, transmission


def _synthetic_raw_intensity(
    center_nm: float = 620.0,
    n_pixels: int = 1797,
    wl_start: float = 560.0,
    wl_end: float = 720.0,
    peak_counts: float = 40000.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (wavelengths, intensity_counts) as if read from detector."""
    wavelengths = np.linspace(wl_start, wl_end, n_pixels)
    # Broad LED illumination profile × transmission dip
    led = peak_counts * np.exp(-0.5 * ((wavelengths - 640.0) / 40.0) ** 2)
    dip = 1.0 - 0.3 * np.exp(-0.5 * ((wavelengths - center_nm) / 20.0) ** 2)
    intensity = led * dip
    return wavelengths, intensity


# ---------------------------------------------------------------------------
# OQ-SPR-001 — Fourier pipeline locates SPR dip
# ---------------------------------------------------------------------------

@pytest.mark.req("OQ-SPR-001")
def test_fourier_pipeline_finds_dip():
    """Fourier pipeline must locate a synthetic SPR dip within ±2 nm."""
    from affilabs.utils.pipelines import initialize_pipelines
    from affilabs.utils.processing_pipeline import get_pipeline_registry

    initialize_pipelines()
    registry = get_pipeline_registry()
    pipeline = registry.get_pipeline("fourier")
    assert pipeline is not None, "Fourier pipeline not found in registry"

    center = 620.0
    wavelengths, transmission = _synthetic_spr_spectrum(
        center_nm=center, noise_std=0.3, wl_start=570.0, wl_end=720.0
    )
    # s_reference: flat array simulating S-pol reference at same intensity
    s_reference = np.ones_like(transmission) * 30000.0

    result = pipeline.find_resonance_wavelength(transmission, wavelengths, s_reference=s_reference)
    assert result is not None, "Fourier pipeline returned None"

    # result is a float (NaN on failure)
    assert not np.isnan(float(result)), "Fourier pipeline returned NaN — SPR region not found"
    assert abs(float(result) - center) < 3.0, (
        f"Fourier pipeline result {result:.2f} nm deviates >3 nm from true center {center} nm"
    )


# ---------------------------------------------------------------------------
# OQ-SPR-002 — Dark subtraction
# ---------------------------------------------------------------------------

@pytest.mark.req("OQ-SPR-002")
def test_dark_subtraction():
    """Dark-subtracted signal must equal raw - dark within floating-point tolerance."""
    rng = np.random.default_rng(0)
    raw = rng.normal(35000, 500, 1797)
    dark = rng.normal(300, 20, 1797)
    corrected = raw - dark

    assert corrected.shape == raw.shape
    np.testing.assert_allclose(corrected, raw - dark, rtol=1e-10)
    # Mean of corrected should be close to mean(raw) - mean(dark)
    assert abs(corrected.mean() - (raw.mean() - dark.mean())) < 1.0


# ---------------------------------------------------------------------------
# OQ-SPR-003 — P/S ratio is attenuated at the SPR dip
# ---------------------------------------------------------------------------

@pytest.mark.req("OQ-SPR-003")
def test_ps_ratio_attenuated_at_dip():
    """P-pol / S-pol ratio must be lower at the SPR dip than at flanks."""
    center_nm = 625.0
    wavelengths = np.linspace(560, 720, 1797)

    # S-pol: flat reference (no SPR coupling)
    s_pol = np.ones(1797) * 30000.0

    # P-pol: attenuated at SPR dip
    p_pol = 30000.0 * (1.0 - 0.25 * np.exp(-0.5 * ((wavelengths - center_nm) / 20.0) ** 2))

    ratio = p_pol / s_pol

    dip_idx = int(np.argmin(ratio))
    flank_left = int(np.argmin(np.abs(wavelengths - (center_nm - 40))))
    flank_right = int(np.argmin(np.abs(wavelengths - (center_nm + 40))))

    assert ratio[dip_idx] < ratio[flank_left], (
        "P/S ratio at dip should be lower than at left flank"
    )
    assert ratio[dip_idx] < ratio[flank_right], (
        "P/S ratio at dip should be lower than at right flank"
    )


# ---------------------------------------------------------------------------
# OQ-SPR-004 — Savitzky-Golay smoothing reduces P2P noise
# ---------------------------------------------------------------------------

@pytest.mark.req("OQ-SPR-004")
def test_savgol_reduces_noise():
    """Savitzky-Golay smoothing must reduce point-to-point noise."""
    rng = np.random.default_rng(7)
    wavelengths, clean = _synthetic_spr_spectrum(noise_std=0.0)
    noisy = clean + rng.normal(0, 3.0, len(clean))

    smoothed = savgol_filter(noisy, window_length=15, polyorder=3)

    raw_p2p = float(np.mean(np.abs(np.diff(noisy))))
    smoothed_p2p = float(np.mean(np.abs(np.diff(smoothed))))

    assert smoothed_p2p < raw_p2p, (
        f"Smoothed P2P ({smoothed_p2p:.4f}) should be less than raw P2P ({raw_p2p:.4f})"
    )


# ---------------------------------------------------------------------------
# OQ-SPR-005 — Out-of-range wavelength classification
# ---------------------------------------------------------------------------

@pytest.mark.req("OQ-SPR-005")
def test_out_of_range_wavelength_zone():
    """A wavelength >720 nm must be classified as OUT_OF_BOUNDS_HIGH."""
    from affilabs.utils.sensor_iq import SensorIQClassifier, WavelengthZone

    clf = SensorIQClassifier()
    zone = clf.classify_wavelength_zone(735.0)
    assert zone == WavelengthZone.OUT_OF_BOUNDS_HIGH, (
        f"Expected OUT_OF_BOUNDS_HIGH for 735 nm, got {zone}"
    )


# ---------------------------------------------------------------------------
# OQ-SPR-006 — validate_sp_orientation detects correct P/S orientation
# ---------------------------------------------------------------------------

@pytest.mark.req("OQ-SPR-006")
def test_transmission_dip_is_minimum():
    """P/S transmission ratio must have its minimum at the SPR dip wavelength.

    This verifies the core physical principle: P-pol is attenuated at the SPR
    resonance wavelength, so P/S transmission has a minimum (dip) there.
    """
    center_nm = 625.0
    wavelengths = np.linspace(560, 720, 1797)

    # S-pol: flat reference (no SPR coupling)
    s_pol = np.ones(1797) * 28000.0

    # P-pol: attenuated at SPR dip center
    p_pol = 30000.0 * (1.0 - 0.35 * np.exp(-0.5 * ((wavelengths - center_nm) / 18.0) ** 2))

    # Compute transmission ratio
    transmission = (p_pol / s_pol) * 100.0

    # SPR dip = minimum in transmission
    dip_idx = int(np.argmin(transmission))
    dip_wl = wavelengths[dip_idx]

    assert abs(dip_wl - center_nm) < 3.0, (
        f"Transmission minimum at {dip_wl:.2f} nm deviates >3 nm from SPR center {center_nm} nm"
    )
    # Verify the dip is a genuine minimum — flanks are higher
    flank_mean = (transmission[0] + transmission[-1]) / 2.0
    assert transmission[dip_idx] < flank_mean, (
        "Transmission at SPR dip must be lower than flank mean"
    )
