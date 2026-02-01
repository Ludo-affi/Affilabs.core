"""FMEA (Failure Mode and Effects Analysis) Tracking System

Cohesive monitoring of quality, correlation, and failure scenarios across:
1. Calibration (LED, dark noise, afterglow)
2. Afterglow correction (validation, LED timing)
3. Live data processing (signal quality, pump interactions)

Provides:
- Real-time failure detection and mitigation
- Historical trend analysis
- Correlation between calibration/afterglow/live data
- Automated scenario classification
- Mitigation strategy tracking

Usage:
    fmea = FMEATracker()

    # During calibration
    fmea.log_calibration_event('led_calibration', 'a', passed=True, metrics={...})

    # During afterglow validation
    fmea.log_afterglow_event('tau_validation', 'a', passed=True, metrics={...})

    # During live data
    fmea.log_live_data_event('signal_quality', 'a', passed=True, metrics={...})

    # Get current system health
    health = fmea.get_system_health()

    # Query for specific scenarios
    scenarios = fmea.get_active_scenarios()
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from utils.logger import logger


class FailureMode(Enum):
    """Categorized failure modes across the system."""

    # Calibration failures
    LED_SATURATION = "led_saturation"
    LED_DRIFT = "led_drift"
    LED_TIMING_ISSUE = "led_timing_issue"
    DARK_NOISE_HIGH = "dark_noise_high"
    DARK_NOISE_UNSTABLE = "dark_noise_unstable"
    SPECTRAL_CORRECTION_FAIL = "spectral_correction_fail"

    # Afterglow failures
    AFTERGLOW_TAU_OUT_OF_RANGE = "afterglow_tau_out_of_range"
    AFTERGLOW_AMPLITUDE_HIGH = "afterglow_amplitude_high"
    AFTERGLOW_FIT_POOR = "afterglow_fit_poor"
    AFTERGLOW_BASELINE_HIGH = "afterglow_baseline_high"
    AFTERGLOW_TREND_ABNORMAL = "afterglow_trend_abnormal"

    # Live data failures
    SIGNAL_LOSS = "signal_loss"
    SIGNAL_DRIFT = "signal_drift"
    PEAK_QUALITY_DEGRADED = "peak_quality_degraded"
    FWHM_DEGRADATION = "fwhm_degradation"
    PUMP_INTERFERENCE = "pump_interference"
    FLOW_INSTABILITY = "flow_instability"

    # Hardware failures
    USB_DISCONNECT = "usb_disconnect"
    CONTROLLER_ERROR = "controller_error"
    PUMP_ERROR = "pump_error"
    OPTICS_LEAK = "optics_leak"

    # Correlation failures
    CALIBRATION_AFTERGLOW_MISMATCH = "calibration_afterglow_mismatch"
    LIVE_DATA_DEGRADATION_POST_CALIBRATION = "live_data_degradation_post_calibration"


class Severity(Enum):
    """Impact severity levels."""

    INFO = 1  # Informational, no impact
    LOW = 2  # Minor impact, experiment can continue
    MEDIUM = 3  # Moderate impact, reduced data quality
    HIGH = 4  # Significant impact, may need intervention
    CRITICAL = 5  # Experiment should stop


@dataclass
class FMEAEvent:
    """Single FMEA event record."""

    timestamp: datetime
    phase: str  # 'calibration', 'afterglow', 'live_data'
    event_type: str  # Event name
    channel: str | None  # Channel ID ('a', 'b', 'c', 'd') or None for system-wide
    passed: bool  # True if check passed, False if failed
    failure_mode: FailureMode | None = None
    severity: Severity = Severity.INFO
    metrics: dict[str, Any] = field(default_factory=dict)
    mitigation_applied: str | None = None
    notes: str = ""


@dataclass
class ScenarioDefinition:
    """Defines a specific failure scenario and its mitigation."""

    name: str
    description: str
    detection_logic: str  # Description of how to detect this scenario
    required_events: list[str]  # Event types that must be present
    mitigation_strategy: str
    severity: Severity
    correlation_check: str | None = None  # Cross-phase correlation to check


class FMEATracker:
    """Tracks failures, mitigations, and correlations across the system."""

    def __init__(self, session_id: str | None = None):
        """Initialize FMEA tracker.

        Args:
            session_id: Unique identifier for this session (auto-generated if None)

        """
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.events: list[FMEAEvent] = []
        self.active_failures: dict[str, FMEAEvent] = {}  # failure_mode -> latest event

        # Phase completion tracking
        self.calibration_completed = False
        self.afterglow_validation_completed = False

        # Scenario definitions
        self.scenarios = self._define_scenarios()

        # Historical data
        self.session_start = datetime.now()

        logger.info(f"FMEA Tracker initialized: session_id={self.session_id}")

    def _define_scenarios(self) -> dict[str, ScenarioDefinition]:
        """Define failure scenarios and their mitigations."""
        return {
            "led_timing_causes_high_afterglow": ScenarioDefinition(
                name="LED Timing → High Afterglow",
                description="LED turn-off timing too fast causes elevated afterglow amplitude",
                detection_logic="Afterglow amplitude > 10,000 counts AND LED calibration passed",
                required_events=["led_calibration", "afterglow_amplitude_check"],
                mitigation_strategy="Increase LED settle delay from 45ms to 75ms",
                severity=Severity.MEDIUM,
                correlation_check="Compare LED intensity vs afterglow amplitude",
            ),
            "poor_calibration_invalidates_afterglow": ScenarioDefinition(
                name="Poor Calibration → Invalid Afterglow",
                description="LED calibration drift/saturation invalidates afterglow model",
                detection_logic="LED saturation OR drift >10% AND afterglow tau out of range",
                required_events=["led_calibration", "afterglow_tau_validation"],
                mitigation_strategy="Re-run full optical calibration with lower LED intensities",
                severity=Severity.HIGH,
                correlation_check="LED stability correlates with tau consistency",
            ),
            "afterglow_correction_insufficient": ScenarioDefinition(
                name="Afterglow Correction Insufficient",
                description="Afterglow correction applied but live data shows baseline drift",
                detection_logic="Afterglow correction enabled AND live dark noise increasing >5 counts/min",
                required_events=["afterglow_validation", "live_dark_noise_trend"],
                mitigation_strategy="Check for optical leak, increase LED delay, or recalibrate afterglow",
                severity=Severity.MEDIUM,
                correlation_check="Compare afterglow-corrected dark noise vs live dark noise",
            ),
            "pump_pulse_artifacts": ScenarioDefinition(
                name="Pump Pulse Artifacts",
                description="Pump flow changes cause transient signal spikes",
                detection_logic="Pump flow change event within 2s of signal spike >100 RU",
                required_events=["pump_flow_change", "signal_spike"],
                mitigation_strategy="Apply temporal filtering (moving average), flag affected regions",
                severity=Severity.LOW,
                correlation_check="Temporal correlation: pump events precede signal changes by 0.5-2s",
            ),
            "fwhm_degradation_post_calibration": ScenarioDefinition(
                name="FWHM Degradation Post-Calibration",
                description="Peak quality degrades during experiment despite good calibration",
                detection_logic="Calibration FWHM <40nm AND live FWHM increasing >0.5nm/min",
                required_events=["calibration_fwhm", "live_fwhm_trend"],
                mitigation_strategy="Check sensor temperature, verify optical alignment, consider recalibration",
                severity=Severity.MEDIUM,
                correlation_check="Calibration FWHM vs Live FWHM trend",
            ),
            "dark_noise_jump_after_led_change": ScenarioDefinition(
                name="Dark Noise Jump After LED Changes",
                description="Dark noise increases after LED intensity adjustments",
                detection_logic="LED intensity change >50 units AND dark noise increases >20 counts",
                required_events=["led_intensity_change", "dark_noise_measurement"],
                mitigation_strategy="Wait 500ms settle time after LED changes, verify afterglow correction",
                severity=Severity.LOW,
                correlation_check="LED change magnitude vs dark noise delta",
            ),
            "channel_cross_contamination": ScenarioDefinition(
                name="Channel Cross-Contamination",
                description="Signal from previous channel bleeds into current measurement",
                detection_logic="Channel switch AND signal baseline >expected by 2σ",
                required_events=["channel_switch", "baseline_measurement"],
                mitigation_strategy="Increase inter-channel delay, verify afterglow correction active",
                severity=Severity.MEDIUM,
                correlation_check="Previous channel intensity vs current baseline elevation",
            ),
            "usb_communication_degradation": ScenarioDefinition(
                name="USB Communication Degradation",
                description="USB read errors or timeouts increasing over time",
                detection_logic="USB read failures >5% within 10-minute window",
                required_events=["usb_read_attempt", "usb_read_failure"],
                mitigation_strategy="Reduce acquisition rate, check USB cable, restart spectrometer",
                severity=Severity.HIGH,
                correlation_check="USB error rate vs time since session start",
            ),
        }

    def log_calibration_event(
        self,
        event_type: str,
        channel: str | None,
        passed: bool,
        metrics: dict[str, Any] | None = None,
        failure_mode: FailureMode | None = None,
        severity: Severity = Severity.INFO,
        mitigation: str | None = None,
        notes: str = "",
    ) -> None:
        """Log a calibration-related event.

        Args:
            event_type: Type of calibration event (e.g., 'led_calibration', 'dark_noise_measurement')
            channel: Channel ID or None for system-wide
            passed: Whether the check passed
            metrics: Measurement values and QC metrics
            failure_mode: Classified failure mode if applicable
            severity: Impact severity
            mitigation: Mitigation strategy applied
            notes: Additional context

        """
        event = FMEAEvent(
            timestamp=datetime.now(),
            phase="calibration",
            event_type=event_type,
            channel=channel,
            passed=passed,
            failure_mode=failure_mode,
            severity=severity,
            metrics=metrics or {},
            mitigation_applied=mitigation,
            notes=notes,
        )

        self._add_event(event)

    def log_afterglow_event(
        self,
        event_type: str,
        channel: str | None,
        passed: bool,
        metrics: dict[str, Any] | None = None,
        failure_mode: FailureMode | None = None,
        severity: Severity = Severity.INFO,
        mitigation: str | None = None,
        notes: str = "",
    ) -> None:
        """Log an afterglow validation event."""
        event = FMEAEvent(
            timestamp=datetime.now(),
            phase="afterglow",
            event_type=event_type,
            channel=channel,
            passed=passed,
            failure_mode=failure_mode,
            severity=severity,
            metrics=metrics or {},
            mitigation_applied=mitigation,
            notes=notes,
        )

        self._add_event(event)

    def log_live_data_event(
        self,
        event_type: str,
        channel: str | None,
        passed: bool,
        metrics: dict[str, Any] | None = None,
        failure_mode: FailureMode | None = None,
        severity: Severity = Severity.INFO,
        mitigation: str | None = None,
        notes: str = "",
    ) -> None:
        """Log a live data processing event."""
        event = FMEAEvent(
            timestamp=datetime.now(),
            phase="live_data",
            event_type=event_type,
            channel=channel,
            passed=passed,
            failure_mode=failure_mode,
            severity=severity,
            metrics=metrics or {},
            mitigation_applied=mitigation,
            notes=notes,
        )

        self._add_event(event)

    def _add_event(self, event: FMEAEvent) -> None:
        """Add event to tracking and update active failures."""
        self.events.append(event)

        # Update active failures
        if event.failure_mode and not event.passed:
            key = f"{event.failure_mode.value}_{event.channel or 'system'}"
            self.active_failures[key] = event
            logger.warning(
                f"🔴 FMEA: Active failure - {event.failure_mode.value} "
                f"(ch={event.channel}, severity={event.severity.name})",
            )
        elif event.passed and event.failure_mode:
            # Clear failure if now passing
            key = f"{event.failure_mode.value}_{event.channel or 'system'}"
            if key in self.active_failures:
                del self.active_failures[key]
                logger.info(
                    f"🟢 FMEA: Resolved - {event.failure_mode.value} (ch={event.channel})",
                )

        # Check for scenario matches
        self._check_scenarios(event)

    def _check_scenarios(self, latest_event: FMEAEvent) -> None:
        """Check if recent events match any defined scenarios."""
        # Look at events in last 5 minutes
        recent_window = datetime.now() - timedelta(minutes=5)
        recent_events = [e for e in self.events if e.timestamp >= recent_window]

        for scenario_key, scenario in self.scenarios.items():
            # Check if all required event types are present
            event_types_present = {e.event_type for e in recent_events}
            if all(req in event_types_present for req in scenario.required_events):
                # Scenario potentially active - log it
                logger.warning(
                    f"⚠️ FMEA Scenario Detected: {scenario.name}\n"
                    f"   Description: {scenario.description}\n"
                    f"   Mitigation: {scenario.mitigation_strategy}\n"
                    f"   Severity: {scenario.severity.name}",
                )

    def get_system_health(self) -> dict[str, Any]:
        """Get current system health summary.

        Returns:
            Dictionary with health metrics:
                - overall_health: 'healthy', 'degraded', 'critical'
                - active_failures: Count and list of active failures
                - active_scenarios: List of detected scenarios
                - phase_status: Completion status of each phase
                - correlation_score: 0-100 score of calibration→afterglow→live correlation

        """
        # Count failures by severity
        severity_counts = dict.fromkeys(Severity, 0)
        for failure in self.active_failures.values():
            severity_counts[failure.severity] += 1

        # Determine overall health
        if severity_counts[Severity.CRITICAL] > 0:
            overall = "critical"
        elif severity_counts[Severity.HIGH] > 0 or len(self.active_failures) >= 3:
            overall = "degraded"
        else:
            overall = "healthy"

        # Calculate correlation score (placeholder - would implement full logic)
        correlation_score = self._calculate_correlation_score()

        return {
            "overall_health": overall,
            "session_id": self.session_id,
            "session_duration_minutes": (
                datetime.now() - self.session_start
            ).total_seconds()
            / 60,
            "active_failures": {
                "count": len(self.active_failures),
                "failures": [
                    {
                        "mode": f.failure_mode.value if f.failure_mode else "unknown",
                        "channel": f.channel,
                        "severity": f.severity.name,
                        "since": (datetime.now() - f.timestamp).total_seconds(),
                    }
                    for f in self.active_failures.values()
                ],
            },
            "severity_distribution": {
                s.name: count for s, count in severity_counts.items()
            },
            "phase_status": {
                "calibration_completed": self.calibration_completed,
                "afterglow_validated": self.afterglow_validation_completed,
                "live_data_active": any(
                    e.phase == "live_data" for e in self.events[-10:]
                ),
            },
            "correlation_score": correlation_score,
            "total_events": len(self.events),
        }

    def _calculate_correlation_score(self) -> float:
        """Calculate correlation quality between phases (0-100)."""
        score = 100.0

        # Deduct points for cross-phase inconsistencies
        # Example: if calibration passed but afterglow validation failed
        cal_events = [e for e in self.events if e.phase == "calibration"]
        afterglow_events = [e for e in self.events if e.phase == "afterglow"]
        live_events = [e for e in self.events if e.phase == "live_data"]

        # Check calibration → afterglow correlation
        if cal_events and afterglow_events:
            cal_passed_rate = sum(e.passed for e in cal_events) / len(cal_events)
            afterglow_passed_rate = sum(e.passed for e in afterglow_events) / len(
                afterglow_events,
            )

            # If calibration passed but afterglow failed, deduct points
            if cal_passed_rate > 0.8 and afterglow_passed_rate < 0.5:
                score -= 30

        # Check afterglow → live data correlation
        if afterglow_events and live_events:
            afterglow_passed_rate = sum(e.passed for e in afterglow_events) / len(
                afterglow_events,
            )
            live_passed_rate = sum(e.passed for e in live_events[-20:]) / min(
                20,
                len(live_events),
            )

            # If afterglow passed but live data degrading, deduct points
            if afterglow_passed_rate > 0.8 and live_passed_rate < 0.5:
                score -= 25

        return max(0.0, min(100.0, score))

    def get_active_scenarios(self) -> list[dict[str, Any]]:
        """Get list of currently active failure scenarios.

        Returns:
            List of scenario descriptions with detection details

        """
        active = []
        recent_window = datetime.now() - timedelta(minutes=5)
        recent_events = [e for e in self.events if e.timestamp >= recent_window]

        for scenario_key, scenario in self.scenarios.items():
            event_types_present = {e.event_type for e in recent_events}
            if all(req in event_types_present for req in scenario.required_events):
                active.append(
                    {
                        "name": scenario.name,
                        "description": scenario.description,
                        "detection_logic": scenario.detection_logic,
                        "mitigation": scenario.mitigation_strategy,
                        "severity": scenario.severity.name,
                        "correlation_check": scenario.correlation_check,
                    },
                )

        return active

    def export_session_report(self, output_path: Path | None = None) -> Path:
        """Export FMEA session report to JSON file.

        Args:
            output_path: Where to save report (auto-generated if None)

        Returns:
            Path to saved report file

        """
        if output_path is None:
            output_path = Path(f"fmea_reports/session_{self.session_id}.json")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        report = {
            "session_id": self.session_id,
            "session_start": self.session_start.isoformat(),
            "session_end": datetime.now().isoformat(),
            "system_health": self.get_system_health(),
            "active_scenarios": self.get_active_scenarios(),
            "all_events": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "phase": e.phase,
                    "event_type": e.event_type,
                    "channel": e.channel,
                    "passed": e.passed,
                    "failure_mode": e.failure_mode.value if e.failure_mode else None,
                    "severity": e.severity.name,
                    "metrics": e.metrics,
                    "mitigation": e.mitigation_applied,
                    "notes": e.notes,
                }
                for e in self.events
            ],
        }

        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"📊 FMEA report exported: {output_path}")
        return output_path

    def mark_calibration_complete(self):
        """Mark calibration phase as complete."""
        self.calibration_completed = True
        logger.info("✅ FMEA: Calibration phase marked complete")

    def mark_afterglow_validation_complete(self):
        """Mark afterglow validation as complete."""
        self.afterglow_validation_completed = True
        logger.info("✅ FMEA: Afterglow validation marked complete")

    def query_events(
        self,
        phase: str | None = None,
        channel: str | None = None,
        event_type: str | None = None,
        passed: bool | None = None,
        time_window_minutes: int | None = None,
    ) -> list[FMEAEvent]:
        """Query events with filters.

        Args:
            phase: Filter by phase ('calibration', 'afterglow', 'live_data')
            channel: Filter by channel
            event_type: Filter by event type
            passed: Filter by passed status
            time_window_minutes: Only include events in last N minutes

        Returns:
            Filtered list of events

        """
        results = self.events

        if phase:
            results = [e for e in results if e.phase == phase]

        if channel:
            results = [e for e in results if e.channel == channel]

        if event_type:
            results = [e for e in results if e.event_type == event_type]

        if passed is not None:
            results = [e for e in results if e.passed == passed]

        if time_window_minutes:
            cutoff = datetime.now() - timedelta(minutes=time_window_minutes)
            results = [e for e in results if e.timestamp >= cutoff]

        return results
