"""ML-Enhanced QC Intelligence System for SPR Calibration Monitoring.

This module provides machine learning-based predictive analytics for:
- Calibration quality prediction
- LED health monitoring
- Sensor coating degradation tracking
- Optical alignment monitoring (non-interfering with real SPR data)

All models are designed to enhance QC without interfering with actual SPR measurements.
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, List, TYPE_CHECKING
from pathlib import Path
import json
import logging

if TYPE_CHECKING:
    from core.calibration_data import CalibrationData

logger = logging.getLogger(__name__)


@dataclass
class CalibrationPrediction:
    """Prediction results for next calibration quality."""
    failure_probability: float  # 0-1
    predicted_fwhm: Dict[str, float]  # Channel -> FWHM (nm)
    confidence: float  # 0-1
    warnings: List[str]
    recommendations: List[str]
    risk_level: str  # 'low', 'medium', 'high'


@dataclass
class LEDHealthStatus:
    """LED health monitoring results."""
    channel: str
    current_intensity: int
    intensity_trend: float  # Change per calibration
    days_until_replacement: Optional[int]
    health_score: float  # 0-1 (1=excellent, 0=needs replacement)
    status: str  # 'excellent', 'good', 'degrading', 'critical'
    replacement_recommended: bool


@dataclass
class SensorCoatingStatus:
    """Sensor coating degradation tracking."""
    current_fwhm_avg: float  # nm
    fwhm_trend: float  # nm per session
    estimated_experiments_remaining: Optional[int]
    coating_quality: str  # 'excellent', 'good', 'acceptable', 'poor'
    replacement_warning: bool
    confidence: float


@dataclass
class OpticalAlignmentStatus:
    """Optical alignment monitoring (baseline-based, not real-time SPR)."""
    ps_ratio_baseline: float  # Expected P/S ratio from calibration
    ps_ratio_deviation: float  # Deviation from baseline
    orientation_confidence: float  # 0-1
    alignment_drift_detected: bool
    maintenance_recommended: bool
    warning_message: Optional[str]


class MLQCIntelligence:
    """ML-based QC intelligence for predictive calibration monitoring.

    This system learns from calibration history to predict:
    1. Calibration failure probability
    2. LED degradation timeline
    3. Sensor coating lifespan
    4. Optical alignment drift (baseline comparison only)

    IMPORTANT: Model 4 (optical alignment) uses BASELINE comparison from
    calibration QC data, NOT real-time SPR measurements, to avoid interfering
    with dynamic SPR responses during experiments.
    """

    def __init__(self, device_serial: str, data_dir: Optional[Path] = None):
        """Initialize ML QC intelligence system.

        Args:
            device_serial: Device serial number for history tracking
            data_dir: Directory for storing ML models and history
        """
        self.device_serial = device_serial
        self.data_dir = data_dir or Path(f"data/devices/{device_serial}/ml_qc")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # History files
        self.calibration_history_file = self.data_dir / "calibration_history.json"
        self.led_health_file = self.data_dir / "led_health.json"
        self.sensor_coating_file = self.data_dir / "sensor_coating.json"
        self.alignment_baseline_file = self.data_dir / "alignment_baseline.json"

        # Load existing history
        self.calibration_history = self._load_calibration_history()
        self.led_health_history = self._load_led_health()
        self.sensor_coating_history = self._load_sensor_coating()
        self.alignment_baseline = self._load_alignment_baseline()

        logger.info(f"🤖 ML QC Intelligence initialized for device {device_serial}")
        logger.info(f"   History: {len(self.calibration_history)} calibrations tracked")

    # =========================================================================
    # MODEL 1: CALIBRATION QUALITY PREDICTOR
    # =========================================================================

    def predict_next_calibration(self) -> CalibrationPrediction:
        """Predict the quality of the next calibration based on history.

        Uses last 10 calibrations to predict failure probability and FWHM.

        Returns:
            CalibrationPrediction with failure probability and recommendations
        """
        if len(self.calibration_history) < 3:
            return CalibrationPrediction(
                failure_probability=0.1,
                predicted_fwhm={'a': 25.0, 'b': 25.0, 'c': 25.0, 'd': 25.0},
                confidence=0.3,
                warnings=["Insufficient calibration history for prediction"],
                recommendations=["Continue calibrating to build prediction baseline"],
                risk_level='low'
            )

        # Extract features from last 10 calibrations
        recent = self.calibration_history[-10:]

        # Calculate failure rate
        failures = sum(1 for cal in recent if cal.get('failed', False))
        failure_rate = failures / len(recent)

        # Calculate FWHM trends per channel
        fwhm_trends = {}
        predicted_fwhm = {}

        for ch in ['a', 'b', 'c', 'd']:
            fwhm_history = []
            for cal in recent:
                fwhm = cal.get('transmission_qc', {}).get(ch, {}).get('fwhm')
                if fwhm is not None:
                    fwhm_history.append(fwhm)

            if len(fwhm_history) >= 2:
                # Linear regression for trend
                x = np.arange(len(fwhm_history))
                coeffs = np.polyfit(x, fwhm_history, 1)
                trend = coeffs[0]
                fwhm_trends[ch] = trend

                # Predict next FWHM
                predicted_fwhm[ch] = float(coeffs[0] * len(fwhm_history) + coeffs[1])
            else:
                fwhm_trends[ch] = 0.0
                predicted_fwhm[ch] = fwhm_history[-1] if fwhm_history else 25.0

        # Calculate failure probability using multiple factors
        failure_prob = 0.0
        warnings = []
        recommendations = []

        # Factor 1: Recent failure rate (40% weight)
        failure_prob += failure_rate * 0.4

        # Factor 2: FWHM degradation trend (40% weight)
        avg_trend = np.mean([abs(t) for t in fwhm_trends.values()])
        if avg_trend > 2.0:  # >2nm per calibration is concerning
            failure_prob += 0.4
            warnings.append(f"FWHM increasing rapidly ({avg_trend:.1f}nm per calibration)")
            recommendations.append("Inspect sensor chip for coating degradation or contamination")
        elif avg_trend > 1.0:
            failure_prob += 0.2
            warnings.append(f"FWHM trending upward ({avg_trend:.1f}nm per calibration)")

        # Factor 3: LED intensity degradation (20% weight)
        led_status = self.predict_led_health()
        critical_leds = [led for led in led_status if led.status == 'critical']
        if critical_leds:
            failure_prob += 0.2
            warnings.append(f"{len(critical_leds)} LED(s) in critical state")
            recommendations.append(f"Replace LEDs: {', '.join([led.channel.upper() for led in critical_leds])}")

        # Determine risk level
        if failure_prob > 0.7:
            risk_level = 'high'
            recommendations.append("🚨 HIGH RISK: Perform maintenance before next calibration")
        elif failure_prob > 0.4:
            risk_level = 'medium'
            recommendations.append("⚠️ MEDIUM RISK: Schedule maintenance soon")
        else:
            risk_level = 'low'

        # Confidence based on data quantity
        confidence = min(1.0, len(recent) / 10.0)

        return CalibrationPrediction(
            failure_probability=float(failure_prob),
            predicted_fwhm=predicted_fwhm,
            confidence=confidence,
            warnings=warnings,
            recommendations=recommendations if recommendations else ["System healthy - no action needed"],
            risk_level=risk_level
        )

    # =========================================================================
    # MODEL 2: LED HEALTH MONITOR
    # =========================================================================

    def predict_led_health(self) -> List[LEDHealthStatus]:
        """Predict LED health and days until replacement needed.

        Tracks LED intensity trends to predict when replacement is needed.

        Returns:
            List of LEDHealthStatus for each channel
        """
        led_statuses = []

        for ch in ['a', 'b', 'c', 'd']:
            # Extract LED intensity history
            intensities = []
            timestamps = []

            for cal in self.calibration_history:
                intensity = cal.get('p_mode_intensity', {}).get(ch)
                if intensity is not None:
                    intensities.append(intensity)
                    timestamps.append(cal.get('timestamp', datetime.now().isoformat()))

            if len(intensities) < 2:
                # Insufficient data
                led_statuses.append(LEDHealthStatus(
                    channel=ch,
                    current_intensity=intensities[-1] if intensities else 0,
                    intensity_trend=0.0,
                    days_until_replacement=None,
                    health_score=1.0,
                    status='excellent',
                    replacement_recommended=False
                ))
                continue

            # Calculate intensity trend (change per calibration)
            x = np.arange(len(intensities))
            coeffs = np.polyfit(x, intensities, 1)
            intensity_trend = coeffs[0]
            current_intensity = intensities[-1]

            # Calculate days until replacement
            # Assume LED=255 means maxed out, need replacement soon
            # Typical LED degrades 5-10 points per calibration
            days_until_replacement = None
            if intensity_trend > 0.5:  # Increasing (degrading)
                remaining_headroom = 255 - current_intensity
                if remaining_headroom > 0:
                    calibrations_remaining = remaining_headroom / intensity_trend
                    # Assume 1 calibration per day on average
                    days_until_replacement = int(calibrations_remaining)

            # Health score (1.0 = excellent, 0.0 = needs replacement)
            health_score = 1.0 - (current_intensity / 255.0) ** 2

            # Status determination
            if current_intensity >= 250:
                status = 'critical'
                replacement_recommended = True
            elif current_intensity >= 230:
                status = 'degrading'
                replacement_recommended = False
            elif current_intensity >= 200:
                status = 'good'
                replacement_recommended = False
            else:
                status = 'excellent'
                replacement_recommended = False

            led_statuses.append(LEDHealthStatus(
                channel=ch,
                current_intensity=current_intensity,
                intensity_trend=float(intensity_trend),
                days_until_replacement=days_until_replacement,
                health_score=float(health_score),
                status=status,
                replacement_recommended=replacement_recommended
            ))

        return led_statuses

    # =========================================================================
    # MODEL 3: SENSOR COATING DEGRADATION
    # =========================================================================

    def predict_sensor_coating_life(self) -> SensorCoatingStatus:
        """Predict sensor coating lifespan based on FWHM degradation.

        Tracks FWHM trends to estimate remaining sensor chip life.
        FWHM > 60nm typically indicates coating degradation.

        Returns:
            SensorCoatingStatus with lifespan prediction
        """
        if len(self.calibration_history) < 3:
            return SensorCoatingStatus(
                current_fwhm_avg=25.0,
                fwhm_trend=0.0,
                estimated_experiments_remaining=None,
                coating_quality='excellent',
                replacement_warning=False,
                confidence=0.3
            )

        # Extract FWHM history (average across all channels)
        fwhm_history = []
        for cal in self.calibration_history:
            fwhm_values = []
            for ch in ['a', 'b', 'c', 'd']:
                fwhm = cal.get('transmission_qc', {}).get(ch, {}).get('fwhm')
                if fwhm is not None:
                    fwhm_values.append(fwhm)
            if fwhm_values:
                fwhm_history.append(np.mean(fwhm_values))

        if len(fwhm_history) < 2:
            current_fwhm = fwhm_history[-1] if fwhm_history else 25.0
            return SensorCoatingStatus(
                current_fwhm_avg=current_fwhm,
                fwhm_trend=0.0,
                estimated_experiments_remaining=None,
                coating_quality='excellent' if current_fwhm < 30 else 'good',
                replacement_warning=False,
                confidence=0.5
            )

        # Calculate FWHM trend
        x = np.arange(len(fwhm_history))
        coeffs = np.polyfit(x, fwhm_history, 1)
        fwhm_trend = coeffs[0]
        current_fwhm = fwhm_history[-1]

        # Estimate experiments remaining until FWHM > 60nm
        estimated_experiments = None
        if fwhm_trend > 0.1:  # Degrading
            fwhm_remaining = 60.0 - current_fwhm
            if fwhm_remaining > 0:
                # Assume 1 experiment = 1 calibration cycle
                estimated_experiments = int(fwhm_remaining / fwhm_trend)

        # Coating quality assessment
        if current_fwhm < 30:
            coating_quality = 'excellent'
        elif current_fwhm < 45:
            coating_quality = 'good'
        elif current_fwhm < 60:
            coating_quality = 'acceptable'
        else:
            coating_quality = 'poor'

        # Replacement warning
        replacement_warning = (
            current_fwhm > 55 or
            (estimated_experiments is not None and estimated_experiments < 10)
        )

        # Confidence based on data quantity
        confidence = min(1.0, len(fwhm_history) / 20.0)

        return SensorCoatingStatus(
            current_fwhm_avg=float(current_fwhm),
            fwhm_trend=float(fwhm_trend),
            estimated_experiments_remaining=estimated_experiments,
            coating_quality=coating_quality,
            replacement_warning=replacement_warning,
            confidence=confidence
        )

    # =========================================================================
    # MODEL 4: OPTICAL ALIGNMENT MONITOR (BASELINE-BASED, NON-INTERFERING)
    # =========================================================================

    def check_optical_alignment(self, calibration_data: CalibrationData) -> OpticalAlignmentStatus:
        """Check optical alignment using CALIBRATION BASELINE comparison.

        IMPORTANT: This does NOT analyze real-time SPR data during experiments.
        It only compares CALIBRATION P/S ratios to historical baseline to detect
        hardware drift (polarizer misalignment, fiber movement, etc.).

        Real SPR measurements are NEVER analyzed by this function to avoid
        interfering with dynamic biological responses.

        Args:
            calibration_data: Calibration QC data (baseline measurements only)

        Returns:
            OpticalAlignmentStatus with drift detection
        """
        # Extract P/S ratios from calibration QC (baseline measurements)
        ps_ratios = []
        for ch in ['a', 'b', 'c', 'd']:
            qc = calibration_data.transmission_validation.get(ch, {})
            ratio = qc.get('ratio')
            if ratio is not None:
                ps_ratios.append(ratio)

        if not ps_ratios:
            return OpticalAlignmentStatus(
                ps_ratio_baseline=0.0,
                ps_ratio_deviation=0.0,
                orientation_confidence=0.5,
                alignment_drift_detected=False,
                maintenance_recommended=False,
                warning_message="Insufficient calibration QC data"
            )

        current_ps_avg = float(np.mean(ps_ratios))

        # Load historical baseline (average P/S ratio from calibrations)
        if not self.alignment_baseline or len(self.alignment_baseline) < 3:
            # Insufficient history - establish baseline
            self._update_alignment_baseline(current_ps_avg)

            return OpticalAlignmentStatus(
                ps_ratio_baseline=current_ps_avg,
                ps_ratio_deviation=0.0,
                orientation_confidence=0.5,
                alignment_drift_detected=False,
                maintenance_recommended=False,
                warning_message="Building alignment baseline (need 3+ calibrations)"
            )

        # Calculate baseline from history
        baseline_ps = np.mean(self.alignment_baseline)
        baseline_std = np.std(self.alignment_baseline)

        # Calculate deviation
        deviation = abs(current_ps_avg - baseline_ps)

        # Drift detection (3-sigma rule for calibration baseline)
        # Note: We use 3-sigma because calibration should be highly reproducible
        # Real SPR data during experiments will have much larger natural variation
        drift_detected = deviation > (3 * baseline_std)

        # Orientation confidence (1.0 = well aligned, 0.0 = misaligned)
        orientation_confidence = max(0.0, 1.0 - (deviation / 0.3))

        # Maintenance recommendation
        maintenance_recommended = drift_detected or deviation > 0.2

        # Warning message
        warning_message = None
        if drift_detected:
            warning_message = (
                f"⚠️ Calibration P/S ratio drifted {deviation:.2f} from baseline "
                f"({baseline_ps:.2f}±{baseline_std:.2f}) - polarizer alignment may have shifted"
            )
        elif maintenance_recommended:
            warning_message = (
                f"⚠️ Calibration P/S ratio deviation {deviation:.2f} - monitor alignment"
            )

        # Update baseline with current value
        self._update_alignment_baseline(current_ps_avg)

        return OpticalAlignmentStatus(
            ps_ratio_baseline=float(baseline_ps),
            ps_ratio_deviation=float(deviation),
            orientation_confidence=float(orientation_confidence),
            alignment_drift_detected=drift_detected,
            maintenance_recommended=maintenance_recommended,
            warning_message=warning_message
        )

    # =========================================================================
    # DATA MANAGEMENT
    # =========================================================================

    def update_from_calibration(self, calibration_data: CalibrationData) -> None:
        """Update ML intelligence with new calibration data.

        Args:
            calibration_data: Latest calibration QC results
        """
        # Create calibration record
        cal_record = {
            'timestamp': datetime.now().isoformat(),
            'device_type': calibration_data.device_type,
            'detector_serial': calibration_data.detector_serial,
            'firmware_version': calibration_data.firmware_version,
            's_integration_time': calibration_data.s_integration_time,
            'p_integration_time': calibration_data.p_integration_time,
            's_mode_intensity': calibration_data.s_mode_intensity,
            'p_mode_intensity': calibration_data.p_mode_intensity,
            'transmission_qc': calibration_data.transmission_validation,
            'failed': any(
                qc.get('status') == '❌ FAIL'
                for qc in calibration_data.transmission_validation.values()
            )
        }

        # Append to history
        self.calibration_history.append(cal_record)

        # Keep last 100 calibrations
        if len(self.calibration_history) > 100:
            self.calibration_history = self.calibration_history[-100:]

        # Save to disk
        self._save_calibration_history()

        logger.info(f"🤖 ML QC updated with calibration #{len(self.calibration_history)}")

    def _load_calibration_history(self) -> List[Dict]:
        """Load calibration history from disk."""
        if not self.calibration_history_file.exists():
            return []

        try:
            with open(self.calibration_history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load calibration history: {e}")
            return []

    def _save_calibration_history(self) -> None:
        """Save calibration history to disk."""
        try:
            with open(self.calibration_history_file, 'w', encoding='utf-8') as f:
                json.dump(self.calibration_history, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save calibration history: {e}")

    def _load_led_health(self) -> Dict:
        """Load LED health history."""
        if not self.led_health_file.exists():
            return {}

        try:
            with open(self.led_health_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _load_sensor_coating(self) -> Dict:
        """Load sensor coating history."""
        if not self.sensor_coating_file.exists():
            return {}

        try:
            with open(self.sensor_coating_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _load_alignment_baseline(self) -> List[float]:
        """Load optical alignment baseline."""
        if not self.alignment_baseline_file.exists():
            return []

        try:
            with open(self.alignment_baseline_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('ps_ratio_history', [])
        except Exception:
            return []

    def _update_alignment_baseline(self, ps_ratio: float) -> None:
        """Update alignment baseline with new calibration P/S ratio."""
        self.alignment_baseline.append(ps_ratio)

        # Keep last 50 calibration baselines
        if len(self.alignment_baseline) > 50:
            self.alignment_baseline = self.alignment_baseline[-50:]

        # Save to disk
        try:
            with open(self.alignment_baseline_file, 'w', encoding='utf-8') as f:
                json.dump({'ps_ratio_history': self.alignment_baseline}, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save alignment baseline: {e}")

    def generate_intelligence_report(self) -> str:
        """Generate comprehensive ML intelligence report.

        Returns:
            Formatted report string with all 4 model predictions
        """
        lines = ["=" * 80]
        lines.append("🤖 ML QC INTELLIGENCE REPORT")
        lines.append(f"Device: {self.device_serial}")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Calibration History: {len(self.calibration_history)} records")
        lines.append("=" * 80)

        # Model 1: Calibration Quality Prediction
        lines.append("\n📊 MODEL 1: NEXT CALIBRATION PREDICTION")
        lines.append("-" * 80)
        cal_pred = self.predict_next_calibration()
        lines.append(f"  Failure Probability: {cal_pred.failure_probability*100:.1f}%")
        lines.append(f"  Risk Level: {cal_pred.risk_level.upper()}")
        lines.append(f"  Confidence: {cal_pred.confidence*100:.0f}%")
        lines.append(f"\n  Predicted FWHM:")
        for ch, fwhm in cal_pred.predicted_fwhm.items():
            lines.append(f"    Ch {ch.upper()}: {fwhm:.1f} nm")
        if cal_pred.warnings:
            lines.append(f"\n  ⚠️ Warnings:")
            for w in cal_pred.warnings:
                lines.append(f"    • {w}")
        lines.append(f"\n  💡 Recommendations:")
        for r in cal_pred.recommendations:
            lines.append(f"    • {r}")

        # Model 2: LED Health
        lines.append("\n💡 MODEL 2: LED HEALTH STATUS")
        lines.append("-" * 80)
        led_statuses = self.predict_led_health()
        for led in led_statuses:
            status_emoji = {
                'excellent': '✅',
                'good': '✅',
                'degrading': '⚠️',
                'critical': '🚨'
            }.get(led.status, '❓')

            lines.append(f"  {status_emoji} Channel {led.channel.upper()}: {led.status.upper()}")
            lines.append(f"     Intensity: {led.current_intensity}/255 (trend: {led.intensity_trend:+.1f}/cal)")
            lines.append(f"     Health Score: {led.health_score*100:.0f}%")
            if led.days_until_replacement:
                lines.append(f"     Estimated Lifespan: {led.days_until_replacement} days")
            if led.replacement_recommended:
                lines.append(f"     🚨 REPLACEMENT RECOMMENDED")

        # Model 3: Sensor Coating
        lines.append("\n🔬 MODEL 3: SENSOR COATING STATUS")
        lines.append("-" * 80)
        coating = self.predict_sensor_coating_life()
        quality_emoji = {
            'excellent': '✅',
            'good': '✅',
            'acceptable': '⚠️',
            'poor': '❌'
        }.get(coating.coating_quality, '❓')

        lines.append(f"  {quality_emoji} Quality: {coating.coating_quality.upper()}")
        lines.append(f"  Current FWHM (avg): {coating.current_fwhm_avg:.1f} nm")
        lines.append(f"  FWHM Trend: {coating.fwhm_trend:+.2f} nm/calibration")
        if coating.estimated_experiments_remaining:
            lines.append(f"  Estimated Lifespan: {coating.estimated_experiments_remaining} experiments")
        lines.append(f"  Confidence: {coating.confidence*100:.0f}%")
        if coating.replacement_warning:
            lines.append(f"  ⚠️ REPLACEMENT WARNING: Sensor chip approaching end of life")

        # Model 4: Optical Alignment (Baseline-based)
        lines.append("\n🔧 MODEL 4: OPTICAL ALIGNMENT (BASELINE MONITOR)")
        lines.append("-" * 80)
        lines.append("  Note: This checks CALIBRATION baseline only, not real-time SPR data")
        if len(self.alignment_baseline) >= 3:
            lines.append(f"  Baseline P/S Ratio: {np.mean(self.alignment_baseline):.3f} ± {np.std(self.alignment_baseline):.3f}")
            lines.append(f"  Baseline History: {len(self.alignment_baseline)} calibrations")
            lines.append(f"  Status: ✅ Baseline established")
        else:
            lines.append(f"  Baseline: Building... ({len(self.alignment_baseline)}/3 calibrations)")
            lines.append(f"  Status: ⏳ Need more calibration data")

        lines.append("\n" + "=" * 80)

        return "\n".join(lines)
