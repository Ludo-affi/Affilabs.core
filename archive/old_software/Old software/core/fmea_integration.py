"""FMEA Integration Guide and Helper Functions

This module provides integration helpers to connect the FMEA tracker to:
1. Calibration (LED, dark noise, spectral correction)
2. Afterglow validation
3. Live data processing

Each area has specific event types and metrics to track.
"""

from core.fmea_tracker import FailureMode, FMEATracker, Severity


class FMEAIntegrationHelper:
    """Helper functions for integrating FMEA tracking into existing code."""

    def __init__(self, fmea_tracker: FMEATracker):
        self.fmea = fmea_tracker

    # ========================================================================
    # CALIBRATION INTEGRATION
    # ========================================================================

    def check_led_calibration(
        self,
        channel: str,
        intensity: float,
        target_intensity: float,
        tolerance: float = 0.1,
        r_squared: float | None = None,
    ) -> None:
        """Check LED calibration result and log to FMEA.

        Args:
            channel: Channel ID ('a', 'b', 'c', 'd')
            intensity: Measured intensity
            target_intensity: Target intensity
            tolerance: Acceptable deviation (fraction, e.g., 0.1 = 10%)
            r_squared: LED response model R² if available

        """
        # Check for saturation
        if intensity > 60000:
            self.fmea.log_calibration_event(
                event_type="led_calibration",
                channel=channel,
                passed=False,
                metrics={
                    "intensity": intensity,
                    "target": target_intensity,
                    "saturation_threshold": 60000,
                },
                failure_mode=FailureMode.LED_SATURATION,
                severity=Severity.HIGH,
                mitigation="Reduce LED intensity and recalibrate",
                notes=f"Channel {channel.upper()} saturated at {intensity} counts",
            )
            return

        # Check if within tolerance
        deviation = abs(intensity - target_intensity) / target_intensity
        passed = deviation <= tolerance

        # Check for drift (if R² provided)
        failure_mode = None
        severity = Severity.INFO
        mitigation = None

        if not passed:
            failure_mode = FailureMode.LED_DRIFT
            severity = Severity.MEDIUM if deviation < 0.2 else Severity.HIGH
            mitigation = (
                "Recalibrate LED intensity"
                if deviation < 0.2
                else "Check LED PCB, may need replacement"
            )

        if r_squared is not None and r_squared < 0.95:
            if not failure_mode:
                failure_mode = FailureMode.LED_DRIFT
            severity = max(severity, Severity.MEDIUM)
            mitigation = f"{mitigation or 'Review'} - Poor LED response linearity (R²={r_squared:.3f})"

        self.fmea.log_calibration_event(
            event_type="led_calibration",
            channel=channel,
            passed=passed,
            metrics={
                "intensity": intensity,
                "target": target_intensity,
                "deviation_pct": deviation * 100,
                "r_squared": r_squared,
            },
            failure_mode=failure_mode,
            severity=severity,
            mitigation=mitigation,
            notes=f"LED cal: {intensity:.0f} counts (target: {target_intensity:.0f}, dev: {deviation*100:.1f}%)",
        )

    def check_dark_noise(
        self,
        channel: str | None,
        dark_mean: float,
        dark_std: float,
        expected_dark: float = 100.0,
        max_std: float = 50.0,
    ) -> None:
        """Check dark noise measurement quality.

        Args:
            channel: Channel ID or None for system dark
            dark_mean: Mean dark noise value
            dark_std: Standard deviation
            expected_dark: Expected dark noise level
            max_std: Maximum acceptable standard deviation

        """
        # Check if dark noise is abnormally high
        high_dark = dark_mean > (expected_dark + 100)
        unstable = dark_std > max_std

        passed = not (high_dark or unstable)
        failure_mode = None
        severity = Severity.INFO
        mitigation = None

        if high_dark:
            failure_mode = FailureMode.DARK_NOISE_HIGH
            severity = Severity.MEDIUM
            mitigation = "Check for light leaks, verify afterglow correction applied"

        if unstable:
            failure_mode = FailureMode.DARK_NOISE_UNSTABLE
            severity = Severity.HIGH if dark_std > 100 else Severity.MEDIUM
            mitigation = "Check detector stability, reduce integration time, verify USB connection"

        self.fmea.log_calibration_event(
            event_type="dark_noise_measurement",
            channel=channel,
            passed=passed,
            metrics={
                "dark_mean": dark_mean,
                "dark_std": dark_std,
                "expected": expected_dark,
                "snr": dark_mean / dark_std if dark_std > 0 else 0,
            },
            failure_mode=failure_mode,
            severity=severity,
            mitigation=mitigation,
            notes=f"Dark noise: {dark_mean:.1f} ± {dark_std:.1f} counts",
        )

    # ========================================================================
    # AFTERGLOW INTEGRATION
    # ========================================================================

    def check_afterglow_tau(
        self,
        channel: str,
        tau_ms: float,
        led_type: str,
        expected_range: tuple[float, float],
        warn_range: tuple[float, float],
    ) -> None:
        """Check afterglow tau value against expected range.

        Args:
            channel: Channel ID
            tau_ms: Measured tau value (milliseconds)
            led_type: LED type code ('LCW', 'OWW')
            expected_range: (min, max) expected tau range
            warn_range: (min, max) warning threshold range

        """
        in_expected = expected_range[0] <= tau_ms <= expected_range[1]
        in_warn = warn_range[0] <= tau_ms <= warn_range[1]

        passed = in_warn
        failure_mode = None
        severity = Severity.INFO
        mitigation = None

        if not in_expected:
            severity = Severity.LOW
            mitigation = "Tau outside expected range - monitor for pattern"

        if not in_warn:
            failure_mode = FailureMode.AFTERGLOW_TAU_OUT_OF_RANGE
            severity = Severity.MEDIUM
            mitigation = "Tau significantly out of range - check LED timing, verify LED type correct, consider re-characterization"

        self.fmea.log_afterglow_event(
            event_type="afterglow_tau_validation",
            channel=channel,
            passed=passed,
            metrics={
                "tau_ms": tau_ms,
                "led_type": led_type,
                "expected_range": expected_range,
                "warn_range": warn_range,
            },
            failure_mode=failure_mode,
            severity=severity,
            mitigation=mitigation,
            notes=f"Tau: {tau_ms:.2f}ms (expected: {expected_range[0]}-{expected_range[1]}ms)",
        )

    def check_afterglow_amplitude(
        self,
        channel: str,
        amplitude: float,
        integration_time_ms: float,
        max_amplitude: float = 10000.0,
    ) -> None:
        """Check afterglow amplitude for LED timing issues.

        Args:
            channel: Channel ID
            amplitude: Measured amplitude
            integration_time_ms: Integration time used
            max_amplitude: Maximum reasonable amplitude

        """
        passed = amplitude < max_amplitude
        failure_mode = None
        severity = Severity.INFO
        mitigation = None

        if not passed:
            failure_mode = FailureMode.AFTERGLOW_AMPLITUDE_HIGH
            severity = Severity.MEDIUM
            mitigation = "High amplitude suggests LED timing issue - increase settle delay from 45ms to 75ms"

        self.fmea.log_afterglow_event(
            event_type="afterglow_amplitude_check",
            channel=channel,
            passed=passed,
            metrics={
                "amplitude": amplitude,
                "integration_time_ms": integration_time_ms,
                "max_threshold": max_amplitude,
            },
            failure_mode=failure_mode,
            severity=severity,
            mitigation=mitigation,
            notes=f"Amplitude: {amplitude:.0f} counts @ {integration_time_ms:.1f}ms integration",
        )

    def check_afterglow_fit_quality(
        self,
        channel: str,
        r_squared: float,
        min_r_squared: float = 0.85,
        good_r_squared: float = 0.95,
    ) -> None:
        """Check afterglow exponential fit quality.

        Args:
            channel: Channel ID
            r_squared: Fit R² value
            min_r_squared: Minimum acceptable R²
            good_r_squared: Good quality threshold

        """
        passed = r_squared >= min_r_squared
        failure_mode = None
        severity = Severity.INFO
        mitigation = None

        if r_squared < good_r_squared:
            severity = Severity.LOW
            mitigation = "Fit quality below optimal - monitor for consistency"

        if not passed:
            failure_mode = FailureMode.AFTERGLOW_FIT_POOR
            severity = Severity.MEDIUM
            mitigation = "Poor fit quality - check LED stability, verify measurement timing, may need re-characterization"

        self.fmea.log_afterglow_event(
            event_type="afterglow_fit_quality",
            channel=channel,
            passed=passed,
            metrics={
                "r_squared": r_squared,
                "min_threshold": min_r_squared,
                "good_threshold": good_r_squared,
            },
            failure_mode=failure_mode,
            severity=severity,
            mitigation=mitigation,
            notes=f"Fit R²: {r_squared:.4f} ({'excellent' if r_squared >= good_r_squared else 'acceptable' if passed else 'poor'})",
        )

    # ========================================================================
    # LIVE DATA INTEGRATION
    # ========================================================================

    def check_signal_quality(
        self,
        channel: str,
        peak_intensity: float,
        fwhm_nm: float,
        snr: float,
        min_intensity: float = 1000.0,
        max_fwhm: float = 60.0,
        min_snr: float = 10.0,
    ) -> None:
        """Check live data signal quality.

        Args:
            channel: Channel ID
            peak_intensity: Peak intensity value
            fwhm_nm: Full-width at half-maximum
            snr: Signal-to-noise ratio
            min_intensity: Minimum acceptable intensity
            max_fwhm: Maximum acceptable FWHM
            min_snr: Minimum acceptable SNR

        """
        signal_weak = peak_intensity < min_intensity
        peak_degraded = fwhm_nm > max_fwhm
        noisy = snr < min_snr

        passed = not (signal_weak or peak_degraded or noisy)
        failure_mode = None
        severity = Severity.INFO
        mitigation = None

        if signal_weak:
            failure_mode = FailureMode.SIGNAL_LOSS
            severity = Severity.HIGH
            mitigation = "Check LED intensity, verify spectrometer connection, check for optical obstructions"
        elif peak_degraded:
            failure_mode = FailureMode.PEAK_QUALITY_DEGRADED
            severity = Severity.MEDIUM
            mitigation = (
                "FWHM degraded - check sensor temperature, verify optical alignment"
            )
        elif noisy:
            failure_mode = FailureMode.PEAK_QUALITY_DEGRADED
            severity = Severity.LOW
            mitigation = "Increase integration time or averaging to improve SNR"

        self.fmea.log_live_data_event(
            event_type="signal_quality_check",
            channel=channel,
            passed=passed,
            metrics={
                "peak_intensity": peak_intensity,
                "fwhm_nm": fwhm_nm,
                "snr": snr,
            },
            failure_mode=failure_mode,
            severity=severity,
            mitigation=mitigation,
            notes=f"Signal: {peak_intensity:.0f} counts, FWHM: {fwhm_nm:.1f}nm, SNR: {snr:.1f}",
        )

    def check_pump_correlation(
        self,
        channel: str,
        pump_flow_rate: float,
        signal_change: float,
        time_since_pump_change: float,
        expected_correlation: bool = True,
    ) -> None:
        """Check for pump-induced signal artifacts.

        Args:
            channel: Channel ID
            pump_flow_rate: Current pump flow rate
            signal_change: Signal change magnitude (RU or counts)
            time_since_pump_change: Time since last pump flow change (seconds)
            expected_correlation: Whether correlation is expected (e.g., during injection)

        """
        # Check for unexpected pump artifacts
        unexpected_artifact = (
            time_since_pump_change < 2.0  # Recent pump change
            and abs(signal_change) > 100  # Significant signal change
            and not expected_correlation  # Not during injection
        )

        passed = not unexpected_artifact
        failure_mode = None
        severity = Severity.INFO
        mitigation = None

        if unexpected_artifact:
            failure_mode = FailureMode.PUMP_INTERFERENCE
            severity = Severity.LOW
            mitigation = "Apply temporal filtering, flag affected data region, consider flow stabilization time"

        self.fmea.log_live_data_event(
            event_type="pump_correlation_check",
            channel=channel,
            passed=passed,
            metrics={
                "pump_flow_rate": pump_flow_rate,
                "signal_change": signal_change,
                "time_since_pump_change": time_since_pump_change,
                "expected_correlation": expected_correlation,
            },
            failure_mode=failure_mode,
            severity=severity,
            mitigation=mitigation,
            notes=f"Pump @ {pump_flow_rate:.0f} µL/min, signal Δ{signal_change:.1f}, Δt={time_since_pump_change:.1f}s",
        )

    def check_fwhm_trend(
        self,
        channel: str,
        current_fwhm: float,
        calibration_fwhm: float,
        fwhm_rate_nm_per_min: float,
        max_rate: float = 0.5,
    ) -> None:
        """Check for FWHM degradation over time.

        Args:
            channel: Channel ID
            current_fwhm: Current FWHM value
            calibration_fwhm: FWHM at calibration
            fwhm_rate_nm_per_min: Rate of FWHM increase
            max_rate: Maximum acceptable rate

        """
        degrading = fwhm_rate_nm_per_min > max_rate

        passed = not degrading
        failure_mode = None
        severity = Severity.INFO
        mitigation = None

        if degrading:
            failure_mode = FailureMode.FWHM_DEGRADATION
            severity = Severity.MEDIUM
            mitigation = "FWHM degrading - check sensor temperature, verify optical alignment, consider recalibration"

        self.fmea.log_live_data_event(
            event_type="fwhm_trend_check",
            channel=channel,
            passed=passed,
            metrics={
                "current_fwhm": current_fwhm,
                "calibration_fwhm": calibration_fwhm,
                "delta_fwhm": current_fwhm - calibration_fwhm,
                "rate_nm_per_min": fwhm_rate_nm_per_min,
            },
            failure_mode=failure_mode,
            severity=severity,
            mitigation=mitigation,
            notes=f"FWHM: {current_fwhm:.1f}nm (cal: {calibration_fwhm:.1f}nm, rate: {fwhm_rate_nm_per_min:.2f}nm/min)",
        )

    # ========================================================================
    # CROSS-PHASE CORRELATION CHECKS
    # ========================================================================

    def check_calibration_afterglow_correlation(self) -> None:
        """Check correlation between calibration results and afterglow validation.

        This should be called after both calibration and afterglow validation complete.
        """
        # Query recent events from both phases
        cal_events = self.fmea.query_events(phase="calibration", time_window_minutes=30)
        afterglow_events = self.fmea.query_events(
            phase="afterglow",
            time_window_minutes=30,
        )

        if not cal_events or not afterglow_events:
            return  # Not enough data yet

        # Check LED calibration pass rate
        led_events = [e for e in cal_events if e.event_type == "led_calibration"]
        if led_events:
            led_pass_rate = sum(e.passed for e in led_events) / len(led_events)

            # Check afterglow pass rate
            afterglow_pass_rate = sum(e.passed for e in afterglow_events) / len(
                afterglow_events,
            )

            # If LED calibration passed but afterglow failed, flag mismatch
            if led_pass_rate > 0.75 and afterglow_pass_rate < 0.5:
                self.fmea.log_calibration_event(
                    event_type="calibration_afterglow_correlation",
                    channel=None,
                    passed=False,
                    metrics={
                        "led_pass_rate": led_pass_rate,
                        "afterglow_pass_rate": afterglow_pass_rate,
                    },
                    failure_mode=FailureMode.CALIBRATION_AFTERGLOW_MISMATCH,
                    severity=Severity.MEDIUM,
                    mitigation="Review LED calibration quality - may have drift or timing issues affecting afterglow",
                    notes="Calibration passed but afterglow validation failed - possible LED timing issue",
                )

    def check_afterglow_live_correlation(self) -> None:
        """Check if afterglow correction is effective in live data.

        This should be called periodically during live data acquisition.
        """
        # Query recent afterglow and live events
        afterglow_events = self.fmea.query_events(
            phase="afterglow",
            time_window_minutes=60,
        )
        live_events = self.fmea.query_events(phase="live_data", time_window_minutes=10)

        if not afterglow_events or not live_events:
            return

        # Check if afterglow validation passed
        afterglow_passed = (
            sum(e.passed for e in afterglow_events) / len(afterglow_events) > 0.75
        )

        # Check live data quality
        live_passed = sum(e.passed for e in live_events) / len(live_events)

        # If afterglow passed but live data degrading, flag issue
        if afterglow_passed and live_passed < 0.5:
            self.fmea.log_live_data_event(
                event_type="afterglow_live_correlation",
                channel=None,
                passed=False,
                metrics={
                    "afterglow_validation_pass_rate": sum(
                        e.passed for e in afterglow_events
                    )
                    / len(afterglow_events),
                    "live_data_pass_rate": live_passed,
                },
                failure_mode=FailureMode.LIVE_DATA_DEGRADATION_POST_CALIBRATION,
                severity=Severity.MEDIUM,
                mitigation="Afterglow correction validated but live data degrading - check for optical leak, LED drift, or temperature effects",
                notes="Live data quality degrading despite good afterglow validation",
            )


# ============================================================================
# INTEGRATION EXAMPLES
# ============================================================================

"""
EXAMPLE 1: Integrate into LED Calibration
------------------------------------------

# In led_calibration.py or spr_calibrator.py:

from core.fmea_tracker import FMEATracker
from core.fmea_integration import FMEAIntegrationHelper

# Initialize FMEA (typically in main controller)
fmea = FMEATracker()
fmea_helper = FMEAIntegrationHelper(fmea)

# During LED calibration:
for channel in ['a', 'b', 'c', 'd']:
    intensity = measure_led_intensity(channel)

    # Check and log to FMEA
    fmea_helper.check_led_calibration(
        channel=channel,
        intensity=intensity,
        target_intensity=target,
        r_squared=led_model_r_squared
    )

# After calibration completes:
fmea.mark_calibration_complete()


EXAMPLE 2: Integrate into Afterglow Validation
-----------------------------------------------

# In afterglow_correction.py _validate_calibration_data():

from core.fmea_tracker import FMEATracker
from core.fmea_integration import FMEAIntegrationHelper

# Get FMEA tracker instance (passed from controller)
fmea_helper = FMEAIntegrationHelper(self.fmea_tracker)

for channel, data in channel_data.items():
    for entry in data['integration_time_data']:
        # Check tau range
        fmea_helper.check_afterglow_tau(
            channel=channel,
            tau_ms=entry['tau_ms'],
            led_type=self.led_type,
            expected_range=LED_SPECS[self.led_type]['tau_range_ms'],
            warn_range=LED_SPECS[self.led_type]['tau_warn_range_ms']
        )

        # Check amplitude
        fmea_helper.check_afterglow_amplitude(
            channel=channel,
            amplitude=entry['amplitude'],
            integration_time_ms=entry['integration_time_ms']
        )

        # Check fit quality
        fmea_helper.check_afterglow_fit_quality(
            channel=channel,
            r_squared=entry['r_squared']
        )

# After validation completes:
fmea.mark_afterglow_validation_complete()

# Check correlation with calibration:
fmea_helper.check_calibration_afterglow_correlation()


EXAMPLE 3: Integrate into Live Data Processing
-----------------------------------------------

# In data_acquisition_manager.py or spectrum_processor.py:

from core.fmea_tracker import FMEATracker
from core.fmea_integration import FMEAIntegrationHelper

# During live acquisition:
for channel in channels:
    spectrum = acquire_spectrum(channel)
    peak_info = find_peak(spectrum)

    # Check signal quality
    fmea_helper.check_signal_quality(
        channel=channel,
        peak_intensity=peak_info['intensity'],
        fwhm_nm=peak_info['fwhm'],
        snr=peak_info['snr']
    )

    # Check pump correlation (if pump active)
    if pump_active:
        fmea_helper.check_pump_correlation(
            channel=channel,
            pump_flow_rate=current_flow,
            signal_change=signal_delta,
            time_since_pump_change=time_delta
        )

    # Check FWHM trend periodically
    if should_check_trend:
        fmea_helper.check_fwhm_trend(
            channel=channel,
            current_fwhm=peak_info['fwhm'],
            calibration_fwhm=calibration_fwhm[channel],
            fwhm_rate_nm_per_min=fwhm_trend_rate
        )

# Periodically check correlation with afterglow:
if time_to_check_correlation:
    fmea_helper.check_afterglow_live_correlation()


EXAMPLE 4: Query FMEA for UI Display
-------------------------------------

# In main_simplified.py or UI controller:

# Get current system health
health = fmea.get_system_health()
print(f"System Health: {health['overall_health']}")
print(f"Active Failures: {health['active_failures']['count']}")

# Get active scenarios
scenarios = fmea.get_active_scenarios()
for scenario in scenarios:
    print(f"⚠️ {scenario['name']}: {scenario['mitigation']}")

# Query specific events
led_failures = fmea.query_events(
    phase='calibration',
    event_type='led_calibration',
    passed=False,
    time_window_minutes=60
)

# Export session report
report_path = fmea.export_session_report()
print(f"FMEA report saved: {report_path}")
"""
