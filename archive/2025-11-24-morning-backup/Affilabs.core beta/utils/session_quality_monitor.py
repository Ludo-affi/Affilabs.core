"""Session-based peak quality monitoring with RGB feedback.

Tracks FWHM and quality metrics within a single experimental session.
Provides RGB status indicators and end-of-session QC reports.

Feature can be enabled/disabled via ENABLE_SESSION_QUALITY_MONITORING flag.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from utils.peak_characterization import PeakCharacteristics

logger = logging.getLogger(__name__)


@dataclass
class SessionQualityMetrics:
    """Quality metrics for current session."""

    # FWHM statistics
    fwhm_mean: float
    fwhm_std: float
    fwhm_min: float
    fwhm_max: float
    fwhm_trend: float  # nm/minute (positive = degrading)

    # Asymmetry statistics
    asymmetry_mean: float
    asymmetry_std: float

    # SNR statistics
    snr_mean: float
    snr_min: float

    # Temporal info
    data_points: int
    session_duration_minutes: float

    # Quality assessment
    overall_grade: str  # "excellent", "good", "poor"
    rgb_status: tuple[int, int, int]  # RGB values for device LED


class SessionQualityMonitor:
    """Monitor peak quality within experimental session with RGB feedback.

    Tracks FWHM over time to detect:
    - Film quality issues (wide peaks)
    - Film degradation (increasing FWHM over time)
    - Sensor variations (compare to historical baseline)

    Quality Grades (for peaks within wavelength QC range):
    - Excellent (Green): FWHM < 30 nm
    - Good (Yellow): 30 nm ≤ FWHM < 60 nm
    - Poor (Red): FWHM ≥ 60 nm or degrading rapidly
    """

    def __init__(
        self,
        device_serial: str,
        session_id: str | None = None,
        sensor_id: str | None = None,
        fwhm_excellent: float = 30.0,  # nm - Green threshold
        fwhm_good: float = 60.0,  # nm - Yellow threshold
        wavelength_range: tuple[float, float] = (580.0, 630.0),  # nm - QC window
    ):
        """Initialize session quality monitor.

        Args:
            device_serial: Device serial number
            session_id: Optional session identifier
            sensor_id: Optional sensor chip identifier
            fwhm_excellent: Threshold for excellent quality (Green)
            fwhm_good: Threshold for good quality (Yellow)
            wavelength_range: Wavelength range for FWHM validation (min, max) in nm

        """
        self.device_serial = device_serial
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.sensor_id = sensor_id or "unknown"

        # Quality thresholds
        self.FWHM_EXCELLENT = fwhm_excellent
        self.FWHM_GOOD = fwhm_good
        self.WAVELENGTH_MIN, self.WAVELENGTH_MAX = wavelength_range

        # Degradation alert threshold (nm/minute)
        self.DEGRADATION_ALERT = 0.5

        # Session data - per channel tracking
        self.fwhm_history: dict[str, list[float]] = {
            ch: [] for ch in ["a", "b", "c", "d"]
        }
        self.peak_wavelength_history: dict[str, list[float]] = {
            ch: [] for ch in ["a", "b", "c", "d"]
        }
        self.asymmetry_history: dict[str, list[float]] = {
            ch: [] for ch in ["a", "b", "c", "d"]
        }
        self.snr_history: dict[str, list[float]] = {
            ch: [] for ch in ["a", "b", "c", "d"]
        }
        self.timestamps: dict[str, list[float]] = {
            ch: [] for ch in ["a", "b", "c", "d"]
        }

        # Session start time
        self.session_start = datetime.now().timestamp()

        logger.info("📊 Session Quality Monitor initialized")
        logger.info(f"   Device: {device_serial}")
        logger.info(f"   Session: {self.session_id}")
        logger.info(f"   Sensor ID: {self.sensor_id}")
        logger.info(
            f"   FWHM Thresholds: <{self.FWHM_EXCELLENT}nm (Green), "
            f"{self.FWHM_EXCELLENT}-{self.FWHM_GOOD}nm (Yellow), ≥{self.FWHM_GOOD}nm (Red)",
        )
        logger.info(
            f"   Wavelength QC Range: {self.WAVELENGTH_MIN}-{self.WAVELENGTH_MAX} nm",
        )

    def add_measurement(
        self,
        channel: str,
        peak_chars: PeakCharacteristics,
        timestamp: float | None = None,
    ) -> None:
        """Add peak quality measurement for current session.

        Only accepts measurements where peak wavelength is within QC range.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            peak_chars: PeakCharacteristics from spectrum processing
            timestamp: Optional timestamp (defaults to now)

        """
        if timestamp is None:
            timestamp = datetime.now().timestamp()

        # Validate wavelength is within QC range
        if not (
            self.WAVELENGTH_MIN <= peak_chars.peak_wavelength <= self.WAVELENGTH_MAX
        ):
            logger.debug(
                f"Ch {channel}: Peak at {peak_chars.peak_wavelength:.1f}nm outside QC range "
                f"({self.WAVELENGTH_MIN}-{self.WAVELENGTH_MAX}nm) - skipping",
            )
            return

        self.fwhm_history[channel].append(peak_chars.fwhm)
        self.peak_wavelength_history[channel].append(peak_chars.peak_wavelength)
        self.asymmetry_history[channel].append(peak_chars.asymmetry_ratio)
        self.snr_history[channel].append(peak_chars.snr)
        self.timestamps[channel].append(timestamp)

    def get_session_metrics(self, channel: str) -> SessionQualityMetrics | None:
        """Calculate session quality metrics for a channel.

        Args:
            channel: Channel to analyze

        Returns:
            SessionQualityMetrics or None if insufficient data

        """
        if len(self.fwhm_history[channel]) < 10:
            return None

        fwhm_data = np.array(self.fwhm_history[channel])
        asym_data = np.array(self.asymmetry_history[channel])
        snr_data = np.array(self.snr_history[channel])
        times = np.array(self.timestamps[channel])

        # Calculate FWHM statistics
        fwhm_mean = float(np.mean(fwhm_data))
        fwhm_std = float(np.std(fwhm_data))
        fwhm_min = float(np.min(fwhm_data))
        fwhm_max = float(np.max(fwhm_data))

        # Calculate FWHM trend (nm/minute)
        if len(times) > 1:
            time_minutes = (times - times[0]) / 60.0
            slope, _ = np.polyfit(time_minutes, fwhm_data, 1)
            fwhm_trend = float(slope)
        else:
            fwhm_trend = 0.0

        # Asymmetry statistics
        asym_mean = float(np.mean(asym_data))
        asym_std = float(np.std(asym_data))

        # SNR statistics
        snr_mean = float(np.mean(snr_data))
        snr_min = float(np.min(snr_data))

        # Session duration
        duration_minutes = (times[-1] - times[0]) / 60.0

        # Overall grade and RGB
        overall_grade = self._calculate_grade(fwhm_mean, fwhm_trend, snr_mean)
        rgb_status = self._calculate_rgb_status(fwhm_mean, fwhm_trend)

        return SessionQualityMetrics(
            fwhm_mean=fwhm_mean,
            fwhm_std=fwhm_std,
            fwhm_min=fwhm_min,
            fwhm_max=fwhm_max,
            fwhm_trend=fwhm_trend,
            asymmetry_mean=asym_mean,
            asymmetry_std=asym_std,
            snr_mean=snr_mean,
            snr_min=snr_min,
            data_points=len(fwhm_data),
            session_duration_minutes=duration_minutes,
            overall_grade=overall_grade,
            rgb_status=rgb_status,
        )

    def _calculate_grade(
        self,
        fwhm_mean: float,
        fwhm_trend: float,
        snr_mean: float,
    ) -> str:
        """Calculate overall quality grade based on FWHM thresholds."""
        # Degrading rapidly = poor
        if fwhm_trend > self.DEGRADATION_ALERT:
            return "poor"

        # FWHM-based grading with user-defined thresholds
        if fwhm_mean < self.FWHM_EXCELLENT and snr_mean > 15:
            return "excellent"
        if fwhm_mean < self.FWHM_GOOD and snr_mean > 10:
            return "good"
        return "poor"

    def _calculate_rgb_status(
        self,
        fwhm_mean: float,
        fwhm_trend: float,
    ) -> tuple[int, int, int]:
        """Calculate RGB LED color based on FWHM.

        Color coding:
        - GREEN: FWHM < 30nm (Excellent)
        - YELLOW: 30nm ≤ FWHM < 60nm (Good)
        - RED: FWHM ≥ 60nm or degrading rapidly (Poor)
        """
        # Check for rapid degradation first (overrides FWHM)
        if fwhm_trend > self.DEGRADATION_ALERT:
            return (255, 0, 0)  # RED - degrading

        # FWHM-based color with user-defined thresholds
        if fwhm_mean < self.FWHM_EXCELLENT:
            return (0, 255, 0)  # GREEN - excellent (<30nm)
        if fwhm_mean < self.FWHM_GOOD:
            return (255, 255, 0)  # YELLOW - good (30-60nm)
        return (255, 0, 0)  # RED - poor (≥60nm)

    def get_active_channels_status(self) -> dict[str, tuple[int, int, int]]:
        """Get RGB status for all active channels.

        Returns:
            Dictionary mapping channel -> RGB tuple

        """
        status = {}
        for ch in ["a", "b", "c", "d"]:
            metrics = self.get_session_metrics(ch)
            if metrics is not None:
                status[ch] = metrics.rgb_status
        return status

    def generate_session_report(self) -> str:
        """Generate end-of-session QC report.

        Returns:
            Formatted report string

        """
        report = ["=" * 70]
        report.append("SESSION QUALITY REPORT")
        report.append(f"Device: {self.device_serial}")
        report.append(f"Session: {self.session_id}")
        report.append(f"Sensor ID: {self.sensor_id}")
        report.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(
            f"QC Wavelength Range: {self.WAVELENGTH_MIN}-{self.WAVELENGTH_MAX} nm",
        )
        report.append("=" * 70)

        for ch in ["a", "b", "c", "d"]:
            metrics = self.get_session_metrics(ch)
            if metrics is None:
                continue

            report.append(f"\n📊 CHANNEL {ch.upper()}")
            report.append("-" * 70)

            # Grade emoji
            grade_emoji = {
                "excellent": "✅",
                "good": "⚠️",
                "poor": "❌",
            }.get(metrics.overall_grade, "❓")

            report.append(
                f"  Overall Grade:  {grade_emoji} {metrics.overall_grade.upper()}",
            )
            report.append(
                f"\n  FWHM Statistics (within {self.WAVELENGTH_MIN}-{self.WAVELENGTH_MAX}nm):",
            )
            report.append(f"    Mean:         {metrics.fwhm_mean:.1f} nm")
            report.append(f"    Std Dev:      {metrics.fwhm_std:.1f} nm")
            report.append(
                f"    Range:        {metrics.fwhm_min:.1f} - {metrics.fwhm_max:.1f} nm",
            )

            # Trend with status
            if abs(metrics.fwhm_trend) > 0.01:
                trend_dir = "↑" if metrics.fwhm_trend > 0 else "↓"
                trend_status = (
                    "⚠️" if metrics.fwhm_trend > self.DEGRADATION_ALERT else ""
                )
                report.append(
                    f"    Trend:        {trend_dir} {abs(metrics.fwhm_trend):.3f} nm/min {trend_status}",
                )

            # Quality interpretation
            report.append("\n  Quality Assessment:")
            if metrics.fwhm_mean < self.FWHM_EXCELLENT:
                report.append(
                    f"    ✅ Excellent film quality (FWHM < {self.FWHM_EXCELLENT}nm)",
                )
            elif metrics.fwhm_mean < self.FWHM_GOOD:
                report.append(
                    f"    ⚠️  Acceptable film quality ({self.FWHM_EXCELLENT}-{self.FWHM_GOOD}nm)",
                )
            else:
                report.append(f"    ❌ Poor film quality (FWHM ≥ {self.FWHM_GOOD}nm)")
                report.append(
                    "       → Check sensor coating, optical alignment, or replace chip",
                )

            # Asymmetry
            asym_status = "✅" if 0.7 < metrics.asymmetry_mean < 1.3 else "⚠️"
            report.append(
                f"\n  Asymmetry:      {asym_status} {metrics.asymmetry_mean:.2f}",
            )

            # SNR
            snr_status = (
                "✅"
                if metrics.snr_mean > 20
                else "⚠️"
                if metrics.snr_mean > 10
                else "❌"
            )
            report.append(
                f"  SNR:            {snr_status} {metrics.snr_mean:.1f} (min: {metrics.snr_min:.1f})",
            )

            # Session info
            report.append(f"\n  Data Points:    {metrics.data_points}")
            report.append(
                f"  Duration:       {metrics.session_duration_minutes:.1f} minutes",
            )

            # RGB status
            r, g, b = metrics.rgb_status
            color_name = {
                (0, 255, 0): "GREEN (Excellent)",
                (255, 255, 0): "YELLOW (Good)",
                (255, 0, 0): "RED (Poor)",
            }.get((r, g, b), f"RGB({r},{g},{b})")
            report.append(f"  RGB Status:     {color_name}")

        report.append("\n" + "=" * 70)

        # Add historical comparison if available
        try:
            comparison = self._compare_to_historical()
            if comparison:
                report.append("\n📈 HISTORICAL COMPARISON (Last 10 Sessions)")
                report.append("-" * 70)
                report.extend(comparison)
        except Exception as e:
            logger.debug(f"Historical comparison unavailable: {e}")

        return "\n".join(report)

    def _compare_to_historical(self) -> list[str]:
        """Compare session to historical baseline."""
        from utils.device_integration import get_device_dir

        device_dir = get_device_dir(self.device_serial)
        history_file = device_dir / "session_history.json"

        if not history_file.exists():
            return ["  No historical data available (first session)"]

        import json

        try:
            with open(history_file, encoding="utf-8") as f:
                history = json.load(f)

            recent_sessions = history.get("sessions", [])[-10:]
            if not recent_sessions:
                return ["  No historical data available"]

            comparison = []
            for ch in ["a", "b", "c", "d"]:
                current = self.get_session_metrics(ch)
                if current is None:
                    continue

                # Calculate historical mean FWHM
                hist_fwhm = [
                    s.get("channels", {}).get(ch, {}).get("fwhm_mean")
                    for s in recent_sessions
                ]
                hist_fwhm = [x for x in hist_fwhm if x is not None]

                if not hist_fwhm:
                    continue

                hist_mean = np.mean(hist_fwhm)
                hist_std = np.std(hist_fwhm)
                diff = current.fwhm_mean - hist_mean
                sigma = diff / hist_std if hist_std > 0 else 0

                if abs(sigma) < 1:
                    status = "✅ Within normal range"
                elif abs(sigma) < 2:
                    status = "⚠️ Slightly different from baseline"
                else:
                    status = "❌ Significantly different from baseline"

                comparison.append(
                    f"  Ch {ch.upper()}: Current={current.fwhm_mean:.1f}nm, "
                    f"Baseline={hist_mean:.1f}±{hist_std:.1f}nm ({diff:+.1f}nm) {status}",
                )

            return comparison

        except Exception as e:
            logger.debug(f"Error comparing to historical: {e}")
            return ["  Historical comparison unavailable"]

    def save_session_summary(self) -> None:
        """Save session summary to device history."""
        from utils.device_integration import get_device_dir

        device_dir = get_device_dir(self.device_serial)
        history_file = device_dir / "session_history.json"

        import json

        # Load existing history
        if history_file.exists():
            with open(history_file, encoding="utf-8") as f:
                history = json.load(f)
        else:
            history = {"sessions": []}

        # Add current session
        session_data = {
            "session_id": self.session_id,
            "sensor_id": self.sensor_id,
            "timestamp": datetime.now().isoformat(),
            "wavelength_range": [self.WAVELENGTH_MIN, self.WAVELENGTH_MAX],
            "thresholds": {
                "excellent": self.FWHM_EXCELLENT,
                "good": self.FWHM_GOOD,
            },
            "channels": {},
        }

        for ch in ["a", "b", "c", "d"]:
            metrics = self.get_session_metrics(ch)
            if metrics is not None:
                session_data["channels"][ch] = {
                    "fwhm_mean": metrics.fwhm_mean,
                    "fwhm_std": metrics.fwhm_std,
                    "fwhm_trend": metrics.fwhm_trend,
                    "asymmetry_mean": metrics.asymmetry_mean,
                    "snr_mean": metrics.snr_mean,
                    "overall_grade": metrics.overall_grade,
                    "data_points": metrics.data_points,
                }

        history["sessions"].append(session_data)

        # Keep last 50 sessions
        history["sessions"] = history["sessions"][-50:]

        # Save
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

        logger.info(f"Session summary saved to {history_file}")
