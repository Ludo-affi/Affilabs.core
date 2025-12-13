"""System Intelligence - ML-Driven Operational Guidance and Troubleshooting.

This module provides a centralized ML system that has a complete view of the
instrument's operational state and guides operation through:

1. **Operational Pattern Recognition** - Learn normal vs abnormal behavior
2. **Predictive Maintenance** - Forecast component degradation
3. **Automated Troubleshooting** - Diagnose issues and suggest fixes
4. **Calibration Quality Assessment** - Validate calibration effectiveness
5. **Experiment Quality Monitoring** - Real-time data quality assessment

Architecture:
- System-wide observability (all subsystems report to intelligence layer)
- Pattern learning from operational history
- Rule-based + ML hybrid approach
- Actionable guidance with confidence scores

Author: AI Assistant
Date: November 21, 2025
Version: 1.0
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

from affilabs.utils.logger import logger


class SystemState(Enum):
    """Overall system operational state."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    WARNING = "warning"
    ERROR = "error"
    UNKNOWN = "unknown"


class IssueCategory(Enum):
    """Categories of system issues."""

    OPTICAL = "optical"  # LED, fiber, polarizer
    DETECTOR = "detector"  # Spectrometer issues
    CALIBRATION = "calibration"  # Calibration quality
    THERMAL = "thermal"  # Temperature effects
    FLUIDICS = "fluidics"  # Flow, bubbles, etc
    DATA_QUALITY = "data_quality"  # Signal quality
    SOFTWARE = "software"  # Software bugs


class IssueSeverity(Enum):
    """Severity levels for issues."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class SystemIssue:
    """Detected system issue with diagnostic information."""

    category: IssueCategory
    severity: IssueSeverity
    title: str
    description: str
    symptoms: list[str]
    probable_causes: list[str]
    recommended_actions: list[str]
    confidence: float  # 0.0-1.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "symptoms": self.symptoms,
            "probable_causes": self.probable_causes,
            "recommended_actions": self.recommended_actions,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "metrics": self.metrics,
        }


@dataclass
class OperationalMetrics:
    """Metrics tracked for system intelligence."""

    # Calibration metrics
    calibration_success_rate: float = 0.0
    calibration_attempts: int = 0
    last_calibration_time: str | None = None
    calibration_drift_rate: float = 0.0  # nm/hour

    # Signal quality metrics
    avg_snr: float = 0.0
    peak_tracking_stability: float = 0.0  # std dev of wavelength
    transmission_quality: float = 0.0

    # LED health metrics
    led_intensity_degradation: dict[str, float] = field(default_factory=dict)
    led_failure_count: dict[str, int] = field(default_factory=dict)

    # Detector health
    dark_noise_level: float = 0.0
    saturation_events: int = 0

    # Thermal stability
    temperature_stability: float = 0.0

    # Operational stats
    uptime_hours: float = 0.0
    total_experiments: int = 0
    error_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)


class SystemIntelligence:
    """ML-driven system intelligence for operational guidance and troubleshooting.

    This class maintains a comprehensive view of the instrument's state and
    provides intelligent guidance for operation, maintenance, and troubleshooting.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        """Initialize system intelligence.

        Args:
            data_dir: Directory for storing intelligence data and models

        """
        self.data_dir = data_dir or Path("generated-files/system_intelligence")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # System state
        self.system_state = SystemState.UNKNOWN
        self.metrics = OperationalMetrics()
        self.active_issues: list[SystemIssue] = []

        # Historical data
        self.metrics_history: list[dict] = []
        self.issue_history: list[SystemIssue] = []

        # Session tracking
        self.session_start_time = datetime.now()
        self.last_update_time = datetime.now()

        # Load historical data
        self._load_history()

        logger.info("🧠 System Intelligence initialized")

    def update_calibration_metrics(
        self,
        success: bool,
        quality_scores: dict[str, float],
        failed_channels: list[str] | None = None,
    ) -> None:
        """Update calibration-related metrics.

        Args:
            success: Whether calibration succeeded
            quality_scores: Per-channel quality scores (0-1)
            failed_channels: List of failed channel IDs

        """
        self.metrics.calibration_attempts += 1
        if success:
            self.metrics.calibration_success_rate = (
                self.metrics.calibration_success_rate
                * (self.metrics.calibration_attempts - 1)
                + 1.0
            ) / self.metrics.calibration_attempts
            self.metrics.last_calibration_time = datetime.now().isoformat()
        else:
            self.metrics.calibration_success_rate = (
                self.metrics.calibration_success_rate
                * (self.metrics.calibration_attempts - 1)
            ) / self.metrics.calibration_attempts

        # Analyze calibration quality
        if success:
            avg_quality = np.mean(list(quality_scores.values()))
            if avg_quality < 0.7:
                self._report_issue(
                    SystemIssue(
                        category=IssueCategory.CALIBRATION,
                        severity=IssueSeverity.WARNING,
                        title="Low Calibration Quality",
                        description=f"Calibration succeeded but quality is below target (avg: {avg_quality:.2f})",
                        symptoms=[
                            "Low S-ref signal",
                            "Weak SPR dip in P-mode",
                            "Unstable wavelength readings",
                        ],
                        probable_causes=[
                            "Dirty optical fiber",
                            "LED intensity degradation",
                            "Misaligned polarizer",
                            "Detector saturation/noise",
                        ],
                        recommended_actions=[
                            "Clean fiber optic connections",
                            "Check LED PCB connections",
                            "Verify polarizer alignment",
                            "Run optics diagnostic",
                        ],
                        confidence=0.8,
                        metrics={"quality_scores": quality_scores},
                    ),
                )

        if failed_channels:
            self._analyze_calibration_failures(failed_channels, quality_scores)

        self._update_system_state()

    def update_signal_quality(
        self,
        channel: str,
        snr: float,
        peak_wavelength: float,
        transmission_quality: float,
    ) -> None:
        """Update real-time signal quality metrics.

        Args:
            channel: Channel ID
            snr: Signal-to-noise ratio
            peak_wavelength: Detected resonance wavelength
            transmission_quality: Quality of transmission spectrum (0-1)

        """
        # Update rolling averages
        alpha = 0.1  # Exponential moving average factor
        self.metrics.avg_snr = alpha * snr + (1 - alpha) * self.metrics.avg_snr
        self.metrics.transmission_quality = (
            alpha * transmission_quality
            + (1 - alpha) * self.metrics.transmission_quality
        )

        # Check for degraded signal quality
        if snr < 10.0:
            self._report_issue(
                SystemIssue(
                    category=IssueCategory.DATA_QUALITY,
                    severity=IssueSeverity.WARNING
                    if snr > 5.0
                    else IssueSeverity.ERROR,
                    title=f"Low SNR on Channel {channel.upper()}",
                    description=f"Signal-to-noise ratio ({snr:.1f}dB) is below threshold",
                    symptoms=[
                        "Noisy baseline",
                        "Poor peak resolution",
                        "Unstable readings",
                    ],
                    probable_causes=[
                        "Low LED intensity",
                        "Optical path contamination",
                        "Excessive ambient light",
                        "Detector noise",
                    ],
                    recommended_actions=[
                        "Recalibrate LED intensities",
                        "Check for light leaks",
                        "Clean optical components",
                        "Verify dark noise levels",
                    ],
                    confidence=0.9,
                    metrics={"snr": snr, "channel": channel},
                ),
            )

    def update_led_health(self, channel: str, intensity: float, target: float) -> None:
        """Update LED health tracking.

        Args:
            channel: Channel ID
            intensity: Current intensity reading
            target: Target intensity

        """
        # Calculate degradation
        degradation = max(0, 1.0 - intensity / target)

        if channel not in self.metrics.led_intensity_degradation:
            self.metrics.led_intensity_degradation[channel] = 0.0

        # Exponential moving average
        alpha = 0.05
        self.metrics.led_intensity_degradation[channel] = (
            alpha * degradation
            + (1 - alpha) * self.metrics.led_intensity_degradation[channel]
        )

        # Check for LED failure
        if degradation > 0.2:
            self._report_issue(
                SystemIssue(
                    category=IssueCategory.OPTICAL,
                    severity=IssueSeverity.WARNING
                    if degradation < 0.3
                    else IssueSeverity.ERROR,
                    title=f"LED Degradation on Channel {channel.upper()}",
                    description=f"LED intensity {intensity:.0f} is {degradation * 100:.1f}% below target {target:.0f}",
                    symptoms=["Weak signal", "Failed calibration", "Low transmission"],
                    probable_causes=[
                        "LED aging/burnout",
                        "Loose PCB connection",
                        "Power supply issue",
                        "Thermal damage",
                    ],
                    recommended_actions=[
                        "Check LED PCB connections",
                        "Measure LED drive current",
                        "Replace LED PCB if necessary",
                        "Contact technical support",
                    ],
                    confidence=0.85,
                    metrics={
                        "intensity": intensity,
                        "target": target,
                        "degradation": degradation,
                    },
                ),
            )

    def update_channel_characteristics(
        self,
        channel: str,
        max_signal: float,
        utilization_pct: float,
        boost_ratio: float,
        optical_limit_reached: bool,
        hit_saturation: bool,
    ) -> None:
        """Update per-channel optical characteristics for ML guidance.

        These metrics inform peak tracking sensitivity and noise models:
        - High utilization (>90%) → channel can deliver strong signal, use tighter tracking
        - Low utilization (<70%) → channel limited, use looser tracking tolerances
        - High boost ratio (>2x) → strong P-mode response, good SPR sensitivity
        - Optical limit reached → cannot improve further, this is channel's maximum
        - Hit saturation → channel pushed to absolute limit

        Args:
            channel: Channel ID
            max_signal: Maximum signal counts achieved in P-mode
            utilization_pct: Percentage of detector capacity utilized (0-100)
            boost_ratio: P-mode / S-mode intensity ratio
            optical_limit_reached: Whether channel hit optical coupling limit
            hit_saturation: Whether channel approached detector saturation

        """
        # Store in metrics for later use
        if not hasattr(self.metrics, "channel_characteristics"):
            self.metrics.channel_characteristics = {}

        self.metrics.channel_characteristics[channel] = {
            "max_signal": max_signal,
            "utilization_pct": utilization_pct,
            "boost_ratio": boost_ratio,
            "optical_limit_reached": optical_limit_reached,
            "hit_saturation": hit_saturation,
            "timestamp": datetime.now().isoformat(),
        }

        # Provide guidance based on channel characteristics
        if utilization_pct < 60:
            logger.info(
                f"📊 Ch {channel.upper()}: Low utilization ({utilization_pct:.1f}%) - "
                f"limited optical coupling or weak LED. Use relaxed peak tracking.",
            )
        elif utilization_pct > 90:
            logger.info(
                f"📊 Ch {channel.upper()}: High utilization ({utilization_pct:.1f}%) - "
                f"excellent signal strength. Use tight peak tracking.",
            )

        if boost_ratio < 1.5:
            logger.warning(
                f"[WARN] Ch {channel.upper()}: Low P/S boost ratio ({boost_ratio:.2f}x) - "
                f"weak SPR response or polarizer issue.",
            )

        if optical_limit_reached:
            logger.info(
                f"📊 Ch {channel.upper()}: Optical limit reached - "
                f"this is maximum achievable signal for this channel.",
            )

    def diagnose_system(self) -> tuple[SystemState, list[SystemIssue]]:
        """Run comprehensive system diagnosis.

        Returns:
            Tuple of (system_state, active_issues)

        """
        self._update_system_state()

        # Sort issues by severity
        self.active_issues.sort(
            key=lambda x: [
                IssueSeverity.CRITICAL,
                IssueSeverity.ERROR,
                IssueSeverity.WARNING,
                IssueSeverity.INFO,
            ].index(x.severity),
        )

        return self.system_state, self.active_issues

    def get_maintenance_recommendations(self) -> list[dict[str, Any]]:
        """Get predictive maintenance recommendations based on metrics.

        Returns:
            List of maintenance recommendations with priority and urgency

        """
        recommendations = []

        # Check calibration drift
        if self.metrics.calibration_drift_rate > 0.5:  # > 0.5 nm/hour
            recommendations.append(
                {
                    "priority": "high",
                    "category": "calibration",
                    "title": "Calibration Drift Detected",
                    "description": f"System drifting at {self.metrics.calibration_drift_rate:.2f} nm/hour",
                    "action": "Recalibrate system or check thermal stability",
                    "urgency_hours": 2,
                },
            )

        # Check LED health
        for channel, degradation in self.metrics.led_intensity_degradation.items():
            if degradation > 0.15:
                recommendations.append(
                    {
                        "priority": "medium",
                        "category": "optical",
                        "title": f"LED Maintenance Required - Channel {channel.upper()}",
                        "description": f"LED showing {degradation * 100:.0f}% degradation",
                        "action": "Inspect LED PCB, check connections, consider replacement",
                        "urgency_hours": 24,
                    },
                )

        # Check dark noise
        if self.metrics.dark_noise_level > 1000:  # Arbitrary threshold
            recommendations.append(
                {
                    "priority": "medium",
                    "category": "detector",
                    "title": "Elevated Dark Noise",
                    "description": f"Dark noise at {self.metrics.dark_noise_level:.0f} counts",
                    "action": "Check detector cooling, clean detector window, verify shielding",
                    "urgency_hours": 48,
                },
            )

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: priority_order.get(x["priority"], 3))

        return recommendations

    def _analyze_calibration_failures(
        self, failed_channels: list[str], quality_scores: dict,
    ) -> None:
        """Analyze patterns in calibration failures to diagnose root cause."""
        if len(failed_channels) == 4:
            # All channels failed - systemic issue
            self._report_issue(
                SystemIssue(
                    category=IssueCategory.OPTICAL,
                    severity=IssueSeverity.CRITICAL,
                    title="Complete Calibration Failure - All Channels",
                    description="All 4 channels failed calibration indicating systemic issue",
                    symptoms=[
                        "No channels pass calibration",
                        "Very low signal across all LEDs",
                    ],
                    probable_causes=[
                        "Detector not connected",
                        "Major optical path blockage",
                        "Power supply failure to LED PCB",
                        "Controller communication failure",
                    ],
                    recommended_actions=[
                        "Verify detector connection (USB)",
                        "Check LED PCB power connection",
                        "Inspect fiber optic cable",
                        "Restart hardware and software",
                    ],
                    confidence=0.95,
                ),
            )
        elif len(failed_channels) >= 2:
            # Multiple failures - possible PCB or thermal issue
            self._report_issue(
                SystemIssue(
                    category=IssueCategory.OPTICAL,
                    severity=IssueSeverity.ERROR,
                    title=f"Multiple Channel Failures: {', '.join([ch.upper() for ch in failed_channels])}",
                    description="Multiple channels failed - possible LED PCB or thermal issue",
                    symptoms=[
                        "Some channels calibrate, others fail",
                        "Inconsistent LED performance",
                    ],
                    probable_causes=[
                        "LED PCB partial failure",
                        "Thermal stress on LEDs",
                        "Loose PCB connections",
                        "LED driver circuit issue",
                    ],
                    recommended_actions=[
                        "Inspect LED PCB for physical damage",
                        "Check LED PCB mounting/connections",
                        "Verify LED driver circuit",
                        "Consider LED PCB replacement",
                    ],
                    confidence=0.8,
                ),
            )

    def _report_issue(self, issue: SystemIssue) -> None:
        """Register a new issue if not already active."""
        # Check if similar issue already exists
        for active_issue in self.active_issues:
            if (
                active_issue.category == issue.category
                and active_issue.title == issue.title
            ):
                # Update existing issue
                active_issue.metrics.update(issue.metrics)
                active_issue.timestamp = issue.timestamp
                return

        # Add new issue
        self.active_issues.append(issue)
        self.issue_history.append(issue)
        logger.warning(f"🚨 {issue.severity.value.upper()}: {issue.title}")

    def _update_system_state(self) -> None:
        """Update overall system state based on active issues."""
        if not self.active_issues:
            self.system_state = SystemState.HEALTHY
            return

        # Check severity of active issues
        has_critical = any(
            i.severity == IssueSeverity.CRITICAL for i in self.active_issues
        )
        has_error = any(i.severity == IssueSeverity.ERROR for i in self.active_issues)
        has_warning = any(
            i.severity == IssueSeverity.WARNING for i in self.active_issues
        )

        if has_critical:
            self.system_state = SystemState.ERROR
        elif has_error:
            self.system_state = SystemState.WARNING
        elif has_warning:
            self.system_state = SystemState.DEGRADED
        else:
            self.system_state = SystemState.HEALTHY

    def clear_issue(self, issue_index: int) -> None:
        """Clear a resolved issue."""
        if 0 <= issue_index < len(self.active_issues):
            resolved = self.active_issues.pop(issue_index)
            logger.info(f"[OK] Resolved: {resolved.title}")
            self._update_system_state()

    def clear_all_issues(self) -> None:
        """Clear all active issues (after manual verification)."""
        self.active_issues.clear()
        self.system_state = SystemState.HEALTHY
        logger.info("[OK] All issues cleared")

    def save_session_report(self, filename: str | None = None):
        """Save session diagnostics report."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"system_intelligence_report_{timestamp}.json"

        report_path = self.data_dir / filename

        report = {
            "session_info": {
                "start_time": self.session_start_time.isoformat(),
                "duration_hours": (
                    datetime.now() - self.session_start_time
                ).total_seconds()
                / 3600,
                "system_state": self.system_state.value,
            },
            "metrics": self.metrics.to_dict(),
            "active_issues": [issue.to_dict() for issue in self.active_issues],
            "issue_history": [
                issue.to_dict() for issue in self.issue_history[-100:]
            ],  # Last 100
            "maintenance_recommendations": self.get_maintenance_recommendations(),
        }

        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"📊 Session report saved: {report_path}")
        return report_path

    def _load_history(self) -> None:
        """Load historical metrics and issues from previous sessions."""
        # TODO: Implement persistent storage and learning from history

    def _save_history(self) -> None:
        """Save current session data to history."""
        # TODO: Implement periodic history saves


# Singleton instance for global access
_system_intelligence_instance: SystemIntelligence | None = None


def get_system_intelligence() -> SystemIntelligence:
    """Get or create the global system intelligence instance."""
    global _system_intelligence_instance
    if _system_intelligence_instance is None:
        _system_intelligence_instance = SystemIntelligence()
    return _system_intelligence_instance
