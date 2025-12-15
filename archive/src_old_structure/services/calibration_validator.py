"""Calibration Validation Service

Pure business logic for validating calibration data quality.
NO Qt dependencies - fully testable.
"""

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""

    passed: bool
    message: str
    severity: str  # 'info', 'warning', 'error'
    value: float | None = None
    threshold: float | None = None


class CalibrationValidator:
    """Validates calibration data quality and completeness.

    This service checks:
    - Signal strength (not too low, not saturated)
    - Signal-to-noise ratio (SNR)
    - Spectral consistency
    - LED intensity validity
    - Integration time validity
    """

    def __init__(
        self,
        min_signal: float = 5000.0,
        max_counts: int = 65535,
        saturation_threshold: float = 0.95,
        min_snr: float = 10.0,
    ):
        """Initialize calibration validator.

        Args:
            min_signal: Minimum acceptable mean signal (counts)
            max_counts: Maximum detector counts (saturation level)
            saturation_threshold: Saturation threshold (fraction of max_counts)
            min_snr: Minimum acceptable SNR

        """
        self.min_signal = min_signal
        self.max_counts = max_counts
        self.saturation_threshold = saturation_threshold
        self.saturation_counts = int(max_counts * saturation_threshold)
        self.min_snr = min_snr

    def validate_spectrum(
        self,
        spectrum: np.ndarray,
        channel: str = "unknown",
    ) -> list[ValidationResult]:
        """Validate a single spectrum.

        Args:
            spectrum: Spectrum intensities (counts)
            channel: Channel identifier for error messages

        Returns:
            List of validation results

        """
        results = []

        # Check if spectrum is empty
        if len(spectrum) == 0:
            results.append(
                ValidationResult(
                    passed=False,
                    message=f"Channel {channel}: Empty spectrum",
                    severity="error",
                ),
            )
            return results

        # Check for non-finite values
        if not np.isfinite(spectrum).all():
            results.append(
                ValidationResult(
                    passed=False,
                    message=f"Channel {channel}: Contains NaN or Inf values",
                    severity="error",
                ),
            )
            return results

        # Check signal strength
        mean_signal = float(np.mean(spectrum))
        results.append(self._check_signal_strength(mean_signal, channel))

        # Check saturation
        results.append(self._check_saturation(spectrum, channel))

        # Check SNR
        snr = self._calculate_snr(spectrum)
        results.append(self._check_snr(snr, channel))

        # Check for all zeros
        if np.count_nonzero(spectrum) == 0:
            results.append(
                ValidationResult(
                    passed=False,
                    message=f"Channel {channel}: All zeros (no signal)",
                    severity="error",
                ),
            )

        return results

    def validate_calibration_set(
        self,
        s_pol_ref: dict[str, np.ndarray],
        wavelengths: np.ndarray,
        p_mode_intensities: dict[str, int],
        s_mode_intensities: dict[str, int],
        integration_time_s: float,
        integration_time_p: float,
    ) -> tuple[bool, list[ValidationResult]]:
        """Validate complete calibration dataset.

        Args:
            s_pol_ref: S-pol reference spectra per channel
            wavelengths: Wavelength array
            p_mode_intensities: P-mode LED intensities
            s_mode_intensities: S-mode LED intensities
            integration_time_s: S-mode integration time (ms)
            integration_time_p: P-mode integration time (ms)

        Returns:
            Tuple of (all_passed, list of validation results)

        """
        results = []

        # Validate channel consistency
        expected_channels = {"a", "b", "c", "d"}
        ref_channels = set(s_pol_ref.keys())
        p_led_channels = set(p_mode_intensities.keys())
        s_led_channels = set(s_mode_intensities.keys())

        if ref_channels != expected_channels:
            results.append(
                ValidationResult(
                    passed=False,
                    message=f"Missing reference channels: {expected_channels - ref_channels}",
                    severity="error",
                ),
            )

        if p_led_channels != expected_channels:
            results.append(
                ValidationResult(
                    passed=False,
                    message=f"Missing P-mode LED values: {expected_channels - p_led_channels}",
                    severity="error",
                ),
            )

        if s_led_channels != expected_channels:
            results.append(
                ValidationResult(
                    passed=False,
                    message=f"Missing S-mode LED values: {expected_channels - s_led_channels}",
                    severity="error",
                ),
            )

        # Validate wavelengths
        if len(wavelengths) == 0:
            results.append(
                ValidationResult(
                    passed=False,
                    message="Empty wavelength array",
                    severity="error",
                ),
            )

        # Validate each spectrum
        for channel, spectrum in s_pol_ref.items():
            # Check length consistency
            if len(spectrum) != len(wavelengths):
                results.append(
                    ValidationResult(
                        passed=False,
                        message=f"Channel {channel}: Length mismatch ({len(spectrum)} vs {len(wavelengths)} wavelengths)",
                        severity="error",
                    ),
                )

            # Validate spectrum quality
            results.extend(self.validate_spectrum(spectrum, channel))

        # Validate LED intensities
        for channel in expected_channels:
            if channel in p_mode_intensities:
                results.append(
                    self._check_led_intensity(
                        p_mode_intensities[channel],
                        channel,
                        "P-mode",
                    ),
                )
            if channel in s_mode_intensities:
                results.append(
                    self._check_led_intensity(
                        s_mode_intensities[channel],
                        channel,
                        "S-mode",
                    ),
                )

        # Validate integration times
        results.extend(
            self._check_integration_times(integration_time_s, integration_time_p),
        )

        # Overall pass/fail
        all_passed = all(r.passed or r.severity == "warning" for r in results)

        return all_passed, results

    def _check_signal_strength(
        self,
        mean_signal: float,
        channel: str,
    ) -> ValidationResult:
        """Check if signal strength is adequate."""
        if mean_signal < self.min_signal:
            return ValidationResult(
                passed=False,
                message=f"Channel {channel}: Signal too low ({mean_signal:.0f} < {self.min_signal:.0f} counts)",
                severity="error",
                value=mean_signal,
                threshold=self.min_signal,
            )
        if mean_signal < self.min_signal * 1.5:
            return ValidationResult(
                passed=True,
                message=f"Channel {channel}: Signal marginal ({mean_signal:.0f} counts)",
                severity="warning",
                value=mean_signal,
                threshold=self.min_signal,
            )
        return ValidationResult(
            passed=True,
            message=f"Channel {channel}: Signal strength good ({mean_signal:.0f} counts)",
            severity="info",
            value=mean_signal,
        )

    def _check_saturation(self, spectrum: np.ndarray, channel: str) -> ValidationResult:
        """Check for saturation."""
        saturated_pixels = np.sum(spectrum >= self.saturation_counts)
        saturation_percent = 100.0 * saturated_pixels / len(spectrum)

        if saturation_percent > 5.0:
            return ValidationResult(
                passed=False,
                message=f"Channel {channel}: Saturated ({saturation_percent:.1f}% of pixels)",
                severity="error",
                value=saturation_percent,
                threshold=5.0,
            )
        if saturation_percent > 1.0:
            return ValidationResult(
                passed=True,
                message=f"Channel {channel}: Slight saturation ({saturation_percent:.1f}% of pixels)",
                severity="warning",
                value=saturation_percent,
                threshold=1.0,
            )
        return ValidationResult(
            passed=True,
            message=f"Channel {channel}: No saturation",
            severity="info",
            value=saturation_percent,
        )

    def _check_snr(self, snr: float, channel: str) -> ValidationResult:
        """Check signal-to-noise ratio."""
        if snr < self.min_snr:
            return ValidationResult(
                passed=False,
                message=f"Channel {channel}: SNR too low ({snr:.1f} < {self.min_snr:.1f})",
                severity="error",
                value=snr,
                threshold=self.min_snr,
            )
        if snr < self.min_snr * 2:
            return ValidationResult(
                passed=True,
                message=f"Channel {channel}: SNR marginal ({snr:.1f})",
                severity="warning",
                value=snr,
                threshold=self.min_snr,
            )
        return ValidationResult(
            passed=True,
            message=f"Channel {channel}: SNR good ({snr:.1f})",
            severity="info",
            value=snr,
        )

    def _check_led_intensity(
        self,
        intensity: int,
        channel: str,
        mode: str,
    ) -> ValidationResult:
        """Check LED intensity validity."""
        if not (0 <= intensity <= 255):
            return ValidationResult(
                passed=False,
                message=f"Channel {channel} {mode}: Invalid LED intensity ({intensity})",
                severity="error",
                value=float(intensity),
                threshold=255.0,
            )
        if intensity == 0:
            return ValidationResult(
                passed=False,
                message=f"Channel {channel} {mode}: LED off",
                severity="error",
                value=float(intensity),
            )
        if intensity < 20:
            return ValidationResult(
                passed=True,
                message=f"Channel {channel} {mode}: LED very dim ({intensity}/255)",
                severity="warning",
                value=float(intensity),
            )
        return ValidationResult(
            passed=True,
            message=f"Channel {channel} {mode}: LED intensity OK ({intensity}/255)",
            severity="info",
            value=float(intensity),
        )

    def _check_integration_times(
        self,
        integration_time_s: float,
        integration_time_p: float,
    ) -> list[ValidationResult]:
        """Check integration time validity."""
        results = []

        # Valid range: 3ms to 10,000ms
        min_time = 3.0
        max_time = 10000.0

        for time, mode in [
            (integration_time_s, "S-mode"),
            (integration_time_p, "P-mode"),
        ]:
            if not (min_time <= time <= max_time):
                results.append(
                    ValidationResult(
                        passed=False,
                        message=f"{mode}: Integration time out of range ({time:.1f}ms)",
                        severity="error",
                        value=time,
                        threshold=max_time,
                    ),
                )
            elif time < 10.0:
                results.append(
                    ValidationResult(
                        passed=True,
                        message=f"{mode}: Integration time very short ({time:.1f}ms)",
                        severity="warning",
                        value=time,
                    ),
                )
            else:
                results.append(
                    ValidationResult(
                        passed=True,
                        message=f"{mode}: Integration time OK ({time:.1f}ms)",
                        severity="info",
                        value=time,
                    ),
                )

        return results

    def _calculate_snr(self, spectrum: np.ndarray) -> float:
        """Calculate signal-to-noise ratio.

        SNR = mean / std_dev
        """
        mean = np.mean(spectrum)
        std = np.std(spectrum)

        if std == 0:
            return float("inf")

        return float(mean / std)

    def format_validation_report(self, results: list[ValidationResult]) -> str:
        """Format validation results as a text report.

        Args:
            results: List of validation results

        Returns:
            Formatted text report

        """
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("CALIBRATION VALIDATION REPORT")
        report_lines.append("=" * 80)

        # Group by severity
        errors = [r for r in results if r.severity == "error"]
        warnings = [r for r in results if r.severity == "warning"]
        info = [r for r in results if r.severity == "info"]

        if errors:
            report_lines.append("\n❌ ERRORS:")
            for r in errors:
                report_lines.append(f"  - {r.message}")

        if warnings:
            report_lines.append("\n⚠️  WARNINGS:")
            for r in warnings:
                report_lines.append(f"  - {r.message}")

        if info:
            report_lines.append("\n✅ INFO:")
            for r in info:
                report_lines.append(f"  - {r.message}")

        # Summary
        report_lines.append("\n" + "=" * 80)
        passed = len(errors) == 0
        status = "✅ PASSED" if passed else "❌ FAILED"
        report_lines.append(f"VALIDATION: {status}")
        report_lines.append(
            f"  Errors: {len(errors)}, Warnings: {len(warnings)}, Info: {len(info)}",
        )
        report_lines.append("=" * 80)

        return "\n".join(report_lines)
