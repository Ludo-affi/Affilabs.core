"""Sensor IQ (Intelligence Quotient) - SPR Data Quality Classification System.

This module provides real-time quality assessment for SPR sensorgram data based on
wavelength ranges and FWHM characteristics. It correlates peak tracking position
with expected sensor performance quality.

Quality Classification System:
- GOOD (590-690 nm): Expected operating range, high confidence
- QUESTIONABLE (560-590 nm, 690-720 nm): Edge zones, acceptable but monitor
- OUT_OF_BOUNDS (<560 nm, >720 nm): Invalid measurements, sensor issues

FWHM Correlation:
- Narrow FWHM (15-30 nm) + Good range = Excellent sensor IQ
- Broad FWHM (>60 nm) + Questionable range = Warning: sensor degradation
- Out of bounds = Critical: check sensor surface, water contact, bubbles
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

    def compute_sensor_iq(
        self,
        wavelength: float,
        fwhm: float | None = None,
        channel: str | None = None,
    ) -> SensorIQMetrics:
        """Compute comprehensive sensor IQ metrics.

        Args:
            wavelength: SPR peak wavelength (nm)
            fwhm: Full width at half maximum (nm), optional
            channel: Channel identifier for history tracking, optional

        Returns:
            SensorIQMetrics with complete quality assessment

        """
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

        # Track history for trend analysis
        if channel:
            if channel not in self._history:
                self._history[channel] = []
            self._history[channel].append(
                {
                    "wavelength": wavelength,
                    "fwhm": fwhm,
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
                    1.0, fwhm_score * 1.1,
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
    channel: str | None = None,
) -> SensorIQMetrics:
    """Convenience function to classify SPR data quality.

    Args:
        wavelength: SPR peak wavelength (nm)
        fwhm: Full width at half maximum (nm), optional
        channel: Channel identifier, optional

    Returns:
        SensorIQMetrics with complete quality assessment

    """
    classifier = get_sensor_iq_classifier()
    return classifier.compute_sensor_iq(wavelength, fwhm, channel)


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
            f"{prefix} QUESTIONABLE: λ={metrics.wavelength:.1f}nm (Zone: {metrics.zone.value})",
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
