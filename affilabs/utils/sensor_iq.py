"""Sensor IQ (Intelligence Quotient) - SPR Data Quality Classification System.

This module provides real-time quality assessment for SPR sensorgram data based on
wavelength ranges and FWHM characteristics. It correlates peak tracking position
with expected sensor performance quality.

Quality Classification System (4 complementary checks, worst result wins):

1. Wavelength zone — static per-point check:
   - GOOD (590-690 nm): Expected operating range, high confidence
   - QUESTIONABLE (560-590 nm, 690-720 nm): Edge zones, acceptable but monitor
   - OUT_OF_BOUNDS (<560 nm, >720 nm): Invalid measurements, sensor issues

2. FWHM — dip sharpness (when available from adaptive pipeline):
   - Narrow FWHM (<30 nm) = Excellent coupling
   - Broad FWHM (>60 nm) = Warning: sensor degradation

3. Dip depth / transmission intensity (when available):
   - Measures how deep the SPR transmission dip is relative to baseline
   - Shallow dip (<0.05, i.e. <5%) → QUESTIONABLE: weak SPR coupling
   - Very shallow dip (<0.02) → POOR: insufficient coupling, check water contact
   - Only downgrades; never overrides a worse zone/FWHM result

4. Baseline noise — rolling 10-point temporal check:
   - Computes std and peak-to-peak of last 10 wavelength readings (~10 s)
   - If peak-to-peak > 3×std → QUESTIONABLE (noisy baseline)
   - If peak-to-peak > 6×std → POOR (severely noisy, do not inject)
   - Only downgrades; never overrides a worse zone or FWHM result
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from affilabs.utils.logger import logger

# =============================================================================
# DISPLAY CONSTANTS FOR UI INTEGRATION
# =============================================================================

# Sensor IQ Level Icons (for UI display)
SENSOR_IQ_ICONS = {
    "excellent": "🌟",
    "good": "[OK]",
    "questionable": "[WARN]",
    "poor": "🔶",
    "critical": "⛔",
}

# Sensor IQ Level Colors (hex codes for UI styling)
SENSOR_IQ_COLORS = {
    "excellent": "#34C759",  # Green
    "good": "#30D158",  # Light green
    "questionable": "#FF9500",  # Orange
    "poor": "#FF9F0A",  # Amber
    "critical": "#FF3B30",  # Red
}

# Zone boundaries display string (for static UI labels)
ZONE_BOUNDARIES_DISPLAY = (
    "Good: 590-690nm | Edge: 560-590, 690-720nm | Out: <560, >720nm"
)

# FWHM thresholds display string (for static UI labels)
FWHM_THRESHOLDS_DISPLAY = (
    "Excellent: <30nm | Good: 30-60nm | Poor: 60-80nm | Critical: >80nm"
)


class SensorIQLevel(Enum):
    """Sensor Intelligence Quotient levels for SPR data quality."""

    EXCELLENT = "excellent"  # 590-690nm + FWHM <30nm
    GOOD = "good"  # 590-690nm + FWHM 30-60nm
    QUESTIONABLE = "questionable"  # Edge zones or moderate FWHM
    POOR = "poor"  # Out of bounds or high FWHM
    CRITICAL = "critical"  # Severely out of bounds or FWHM >80nm


class WavelengthZone(Enum):
    """SPR wavelength zones for quality assessment."""

    GOOD = "good"  # 590-690 nm - Expected operating range
    QUESTIONABLE_LOW = "questionable_low"  # 560-590 nm - Lower edge
    QUESTIONABLE_HIGH = "questionable_high"  # 690-720 nm - Upper edge
    OUT_OF_BOUNDS_LOW = "out_of_bounds_low"  # <560 nm - Below valid range
    OUT_OF_BOUNDS_HIGH = "out_of_bounds_high"  # >720 nm - Above valid range


@dataclass
class SensorIQMetrics:
    """Container for sensor IQ quality metrics."""

    wavelength: float
    fwhm: float | None
    dip_depth: float | None  # SPR transmission dip depth (0.0–1.0); None if unavailable
    zone: WavelengthZone
    iq_level: SensorIQLevel
    quality_score: float  # 0.0-1.0
    warning_message: str | None
    recommendation: str | None


class SensorIQClassifier:
    """Classify SPR data quality based on wavelength and FWHM."""

    # Wavelength zone boundaries (nm)
    ZONE_BOUNDARIES = {
        "out_of_bounds_low": (0, 560),
        "questionable_low": (560, 590),
        "good": (590, 690),
        "questionable_high": (690, 720),
        "out_of_bounds_high": (720, 1000),
    }

    # FWHM quality thresholds (nm)
    FWHM_EXCELLENT = 30.0  # <30nm = Excellent sensor coupling
    FWHM_GOOD = 60.0  # 30-60nm = Good coupling
    FWHM_POOR = 80.0  # 60-80nm = Poor coupling (warning)
    # >80nm = Critical coupling issues

    def __init__(self) -> None:
        """Initialize the sensor IQ classifier."""
        self._history = {}  # Track per-channel history for trend analysis

    def classify_wavelength_zone(self, wavelength: float) -> WavelengthZone:
        """Classify wavelength into quality zone.

        Args:
            wavelength: SPR peak wavelength (nm)

        Returns:
            WavelengthZone classification

        """
        if wavelength < self.ZONE_BOUNDARIES["out_of_bounds_low"][1]:
            return WavelengthZone.OUT_OF_BOUNDS_LOW
        if wavelength < self.ZONE_BOUNDARIES["questionable_low"][1]:
            return WavelengthZone.QUESTIONABLE_LOW
        if wavelength < self.ZONE_BOUNDARIES["good"][1]:
            return WavelengthZone.GOOD
        if wavelength < self.ZONE_BOUNDARIES["questionable_high"][1]:
            return WavelengthZone.QUESTIONABLE_HIGH
        return WavelengthZone.OUT_OF_BOUNDS_HIGH

    def classify_fwhm_quality(self, fwhm: float | None) -> tuple[str, float]:
        """Classify FWHM into quality category.

        Args:
            fwhm: Full width at half maximum (nm), or None if not available

        Returns:
            Tuple of (quality_category, quality_score)
            - quality_category: 'excellent', 'good', 'poor', 'critical', or 'unknown'
            - quality_score: 0.0-1.0

        """
        if fwhm is None:
            return "unknown", 0.5

        if fwhm < self.FWHM_EXCELLENT:
            # Excellent: Sharp, well-defined peak
            score = 1.0 - (fwhm / self.FWHM_EXCELLENT) * 0.1  # 0.9-1.0
            return "excellent", max(0.9, score)
        if fwhm < self.FWHM_GOOD:
            # Good: Normal operating range
            score = (
                0.9
                - (
                    (fwhm - self.FWHM_EXCELLENT)
                    / (self.FWHM_GOOD - self.FWHM_EXCELLENT)
                )
                * 0.3
            )
            return "good", max(0.6, score)
        if fwhm < self.FWHM_POOR:
            # Poor: Degraded coupling, monitor closely
            score = (
                0.6
                - ((fwhm - self.FWHM_GOOD) / (self.FWHM_POOR - self.FWHM_GOOD)) * 0.3
            )
            return "poor", max(0.3, score)
        # Critical: Severe coupling issues
        score = max(0.1, 0.3 - (fwhm - self.FWHM_POOR) / 100.0)
        return "critical", score

    # Dip depth thresholds (transmission fraction: 0.0 = no signal, 1.0 = full transmission)
    # SPR dip depth is the fraction of transmission removed at the resonance minimum
    DIP_DEPTH_GOOD = 0.05       # ≥5% dip = acceptable coupling
    DIP_DEPTH_QUESTIONABLE = 0.02  # 2-5% = weak, monitor

    def compute_sensor_iq(
        self,
        wavelength: float,
        fwhm: float | None = None,
        dip_depth: float | None = None,
        channel: str | None = None,
    ) -> SensorIQMetrics:
        """Compute comprehensive sensor IQ metrics.

        Args:
            wavelength: SPR peak wavelength (nm)
            fwhm: Full width at half maximum (nm), optional
            dip_depth: SPR dip depth as transmission fraction (0.0–1.0), optional
            channel: Channel identifier for history tracking, optional

        Returns:
            SensorIQMetrics with complete quality assessment

        """
        _level_order = [
            SensorIQLevel.EXCELLENT,
            SensorIQLevel.GOOD,
            SensorIQLevel.QUESTIONABLE,
            SensorIQLevel.POOR,
            SensorIQLevel.CRITICAL,
        ]

        # Classify wavelength zone
        zone = self.classify_wavelength_zone(wavelength)

        # Classify FWHM quality
        fwhm_category, fwhm_score = self.classify_fwhm_quality(fwhm)

        # Combine wavelength zone and FWHM to determine overall IQ level
        iq_level, quality_score, warning, recommendation = self._determine_iq_level(
            zone,
            wavelength,
            fwhm_category,
            fwhm_score,
            fwhm,
        )

        # Dip depth check — transmission intensity / SPR coupling strength
        # Applied after zone/FWHM; can only downgrade
        if dip_depth is not None:
            if dip_depth < self.DIP_DEPTH_QUESTIONABLE:
                # Very shallow dip → POOR: SPR coupling almost absent
                depth_level = SensorIQLevel.POOR
                depth_score = min(quality_score, 0.3)
                depth_warning = f"Very shallow SPR dip ({dip_depth*100:.1f}%) — weak coupling"
                depth_rec = "Check water contact, flow cell, sensor chip surface"
            elif dip_depth < self.DIP_DEPTH_GOOD:
                # Shallow dip → QUESTIONABLE: coupling present but weak
                depth_level = SensorIQLevel.QUESTIONABLE
                depth_score = min(quality_score, 0.55)
                depth_warning = f"Shallow SPR dip ({dip_depth*100:.1f}%) — coupling is weak"
                depth_rec = "Monitor; ensure good water contact before injecting"
            else:
                depth_level = None  # Dip depth is acceptable — no downgrade

            if depth_level is not None and _level_order.index(depth_level) > _level_order.index(iq_level):
                iq_level = depth_level
                quality_score = depth_score
                warning = depth_warning if not warning else f"{warning}; {depth_warning}"
                recommendation = depth_rec if not recommendation else recommendation

        # Baseline noise check — peak-to-peak vs std over last 10 points
        # Requires BOTH a statistically significant ratio AND a clinically meaningful
        # absolute magnitude — prevents flagging sub-0.3nm noise as "poor quality".
        # Thresholds: QUESTIONABLE at p2p>0.3nm AND p2p>5×std; POOR at p2p>0.8nm AND p2p>8×std
        if channel and channel in self._history and len(self._history[channel]) >= 10:
            recent_wl = [m["wavelength"] for m in self._history[channel][-10:]]
            std = float(np.std(recent_wl))
            p2p = float(np.max(recent_wl) - np.min(recent_wl))

            if std > 0 and p2p > 5.0 * std and p2p > 0.3:
                noise_warning = f"Noisy baseline: peak-to-peak={p2p:.2f}nm, std={std:.2f}nm"
                noise_rec = "Wait for baseline to stabilise before injecting"

                if p2p > 8.0 * std and p2p > 0.8:
                    # Severe noise → at least POOR
                    noise_level = SensorIQLevel.POOR
                    noise_score = min(quality_score, 0.3)
                else:
                    # Moderate noise → at least QUESTIONABLE
                    noise_level = SensorIQLevel.QUESTIONABLE
                    noise_score = min(quality_score, 0.55)

                # Only downgrade
                if _level_order.index(noise_level) > _level_order.index(iq_level):
                    iq_level = noise_level
                    quality_score = noise_score
                    warning = noise_warning if not warning else f"{warning}; {noise_warning}"
                    recommendation = noise_rec if not recommendation else recommendation

        # Track history for trend analysis
        if channel:
            if channel not in self._history:
                self._history[channel] = []
            self._history[channel].append(
                {
                    "wavelength": wavelength,
                    "fwhm": fwhm,
                    "dip_depth": dip_depth,
                    "iq_level": iq_level,
                    "quality_score": quality_score,
                },
            )
            # Keep only last 100 measurements
            if len(self._history[channel]) > 100:
                self._history[channel].pop(0)

        return SensorIQMetrics(
            wavelength=wavelength,
            fwhm=fwhm,
            dip_depth=dip_depth,
            zone=zone,
            iq_level=iq_level,
            quality_score=quality_score,
            warning_message=warning,
            recommendation=recommendation,
        )

    def _determine_iq_level(
        self,
        zone: WavelengthZone,
        wavelength: float,
        fwhm_category: str,
        fwhm_score: float,
        fwhm: float | None,
    ) -> tuple[SensorIQLevel, float, str | None, str | None]:
        """Determine overall IQ level from zone and FWHM classifications.

        Returns:
            Tuple of (iq_level, quality_score, warning_message, recommendation)

        """
        warning = None
        recommendation = None

        # CRITICAL: Out of bounds zones
        if zone in [
            WavelengthZone.OUT_OF_BOUNDS_LOW,
            WavelengthZone.OUT_OF_BOUNDS_HIGH,
        ]:
            iq_level = SensorIQLevel.CRITICAL
            quality_score = 0.1

            if zone == WavelengthZone.OUT_OF_BOUNDS_LOW:
                warning = f"⛔ CRITICAL: Wavelength {wavelength:.1f}nm is below valid range (<560nm)"
                recommendation = "Check sensor surface, ensure proper water contact, inspect for air bubbles"
            else:
                warning = f"⛔ CRITICAL: Wavelength {wavelength:.1f}nm is above valid range (>720nm)"
                recommendation = "Verify sensor coupling, check for contamination or surface degradation"

            return iq_level, quality_score, warning, recommendation

        # GOOD ZONE: 590-690nm
        if zone == WavelengthZone.GOOD:
            if fwhm_category == "excellent":
                iq_level = SensorIQLevel.EXCELLENT
                quality_score = min(
                    1.0,
                    fwhm_score * 1.1,
                )  # Bonus for excellent in good zone
            elif fwhm_category == "good":
                iq_level = SensorIQLevel.GOOD
                quality_score = fwhm_score
            elif fwhm_category == "poor":
                iq_level = SensorIQLevel.QUESTIONABLE
                quality_score = fwhm_score
                if fwhm is not None:
                    warning = (
                        f"[WARN]  FWHM {fwhm:.1f}nm is high - Monitor sensor coupling"
                    )
                    recommendation = (
                        "Check for air bubbles, verify water contact quality"
                    )
            elif fwhm_category == "critical":  # critical FWHM
                iq_level = SensorIQLevel.POOR
                quality_score = fwhm_score
                if fwhm is not None:
                    warning = f"[WARN]  FWHM {fwhm:.1f}nm is very high - Sensor degradation suspected"
                    recommendation = (
                        "Clean sensor surface, check for contamination or damage"
                    )
            else:  # unknown (no FWHM data)
                iq_level = SensorIQLevel.GOOD
                quality_score = 0.7  # Moderate score without FWHM confirmation

            return iq_level, quality_score, warning, recommendation

        # QUESTIONABLE ZONES: 560-590nm or 690-720nm
        if zone in [WavelengthZone.QUESTIONABLE_LOW, WavelengthZone.QUESTIONABLE_HIGH]:
            # Wavelength in edge zone - downgrade quality
            if fwhm_category in ["excellent", "good"]:
                iq_level = SensorIQLevel.QUESTIONABLE
                quality_score = fwhm_score * 0.8  # 20% penalty for edge zone
                warning = f"[WARN]  Wavelength {wavelength:.1f}nm in edge zone"
                recommendation = "Monitor closely - may indicate binding event or drift"
            else:  # poor or critical FWHM
                iq_level = SensorIQLevel.POOR
                quality_score = fwhm_score * 0.7  # 30% penalty
                if fwhm is not None:
                    warning = f"[WARN]  Wavelength {wavelength:.1f}nm in edge zone with poor FWHM {fwhm:.1f}nm"
                else:
                    warning = f"[WARN]  Wavelength {wavelength:.1f}nm in edge zone with unknown FWHM quality"
                recommendation = "Check sensor surface quality and water contact"

            return iq_level, quality_score, warning, recommendation

        # Fallback (should not reach here)
        return SensorIQLevel.QUESTIONABLE, 0.5, None, None

    def get_channel_trend(self, channel: str, window: int = 10) -> dict | None:
        """Analyze recent IQ trend for a channel.

        Args:
            channel: Channel identifier
            window: Number of recent measurements to analyze

        Returns:
            Dictionary with trend statistics, or None if insufficient data

        """
        if channel not in self._history or len(self._history[channel]) < 2:
            return None

        recent = self._history[channel][-window:]

        wavelengths = [m["wavelength"] for m in recent]
        fwhms = [m["fwhm"] for m in recent if m["fwhm"] is not None]
        scores = [m["quality_score"] for m in recent]

        trend = {
            "wavelength_mean": np.mean(wavelengths),
            "wavelength_std": np.std(wavelengths),
            "wavelength_drift": wavelengths[-1] - wavelengths[0]
            if len(wavelengths) > 1
            else 0,
            "quality_score_mean": np.mean(scores),
            "quality_score_trend": "improving"
            if scores[-1] > scores[0]
            else "degrading",
            "measurements": len(recent),
        }

        if fwhms:
            trend["fwhm_mean"] = np.mean(fwhms)
            trend["fwhm_std"] = np.std(fwhms)

        return trend


# Global singleton instance
_global_classifier: SensorIQClassifier | None = None


def get_sensor_iq_classifier() -> SensorIQClassifier:
    """Get global sensor IQ classifier instance."""
    global _global_classifier
    if _global_classifier is None:
        _global_classifier = SensorIQClassifier()
    return _global_classifier


def classify_spr_quality(
    wavelength: float,
    fwhm: float | None = None,
    dip_depth: float | None = None,
    channel: str | None = None,
) -> SensorIQMetrics:
    """Convenience function to classify SPR data quality.

    Args:
        wavelength: SPR peak wavelength (nm)
        fwhm: Full width at half maximum (nm), optional
        dip_depth: SPR dip depth as transmission fraction (0.0–1.0), optional
        channel: Channel identifier, optional

    Returns:
        SensorIQMetrics with complete quality assessment

    """
    classifier = get_sensor_iq_classifier()
    return classifier.compute_sensor_iq(wavelength, fwhm, dip_depth, channel)


def log_sensor_iq(metrics: SensorIQMetrics, channel: str) -> None:
    """Log sensor IQ metrics with appropriate severity level.

    Args:
        metrics: SensorIQMetrics to log
        channel: Channel identifier

    """
    prefix = f"[Ch {channel.upper()}] Sensor IQ"

    if metrics.iq_level == SensorIQLevel.CRITICAL:
        logger.error(f"{prefix} CRITICAL: {metrics.warning_message}")
        if metrics.recommendation:
            logger.error(f"   → {metrics.recommendation}")
    elif metrics.iq_level == SensorIQLevel.POOR:
        fwhm_str = f"{metrics.fwhm:.1f}nm" if metrics.fwhm else "N/A"
        logger.warning(f"{prefix} POOR: λ={metrics.wavelength:.1f}nm, FWHM={fwhm_str}")
        if metrics.warning_message:
            logger.warning(f"   {metrics.warning_message}")
    elif metrics.iq_level == SensorIQLevel.QUESTIONABLE:
        logger.info(
            f"{prefix} QUESTIONABLE: λ={metrics.wavelength:.1f}nm "
            f"(Zone: {metrics.zone.value})",
        )
        if metrics.warning_message:
            logger.info(f"   {metrics.warning_message}")
    elif metrics.iq_level == SensorIQLevel.EXCELLENT:
        logger.debug(
            f"{prefix} EXCELLENT: λ={metrics.wavelength:.1f}nm, FWHM={metrics.fwhm:.1f}nm, Score={metrics.quality_score:.2f}",
        )
    else:  # GOOD
        logger.debug(
            f"{prefix} GOOD: λ={metrics.wavelength:.1f}nm, Score={metrics.quality_score:.2f}",
        )
