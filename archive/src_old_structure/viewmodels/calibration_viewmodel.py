"""Calibration View Model

Manages calibration workflow state and coordinates validation.
Bridges CalibrationValidator service with Qt UI.
"""

from PySide6.QtCore import QObject, Signal
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class CalibrationViewModel(QObject):
    """View model for calibration workflow.

    Responsibilities:
    - Manage calibration state (idle, running, complete, failed)
    - Coordinate validation via CalibrationValidator service
    - Emit signals for UI updates
    - Track validation results

    Signals emitted:
    - calibration_started: When calibration begins
    - calibration_progress: Progress updates (percent, message)
    - calibration_complete: When calibration succeeds (data)
    - calibration_failed: When calibration fails (error_message)
    - validation_complete: When validation finishes (passed, results)
    """

    # Signals
    calibration_started = Signal()
    calibration_progress = Signal(int, str)  # percent, message
    calibration_complete = Signal(dict)  # calibration_data
    calibration_failed = Signal(str)  # error_message
    validation_complete = Signal(bool, list)  # passed, results

    def __init__(self):
        super().__init__()
        self._state = 'idle'  # idle, running, complete, failed
        self._validation_results = []
        self._calibration_data = None

        # Will be set by dependency injection
        self._validator = None

    def set_validator(self, validator):
        """Inject CalibrationValidator service dependency."""
        from services import CalibrationValidator
        if not isinstance(validator, CalibrationValidator):
            raise TypeError(f"Expected CalibrationValidator, got {type(validator)}")
        self._validator = validator
        logger.debug("CalibrationValidator injected")

    @property
    def state(self) -> str:
        """Current calibration state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Check if calibration is currently running."""
        return self._state == 'running'

    @property
    def is_complete(self) -> bool:
        """Check if calibration completed successfully."""
        return self._state == 'complete'

    @property
    def validation_results(self) -> List:
        """Get latest validation results."""
        return self._validation_results.copy()

    def start_calibration(self):
        """Start calibration workflow."""
        if self._state == 'running':
            logger.warning("Calibration already running")
            return

        self._state = 'running'
        self._validation_results = []
        self._calibration_data = None
        self.calibration_started.emit()
        logger.info("Calibration started")

    def update_progress(self, percent: int, message: str):
        """Update calibration progress.

        Args:
            percent: Progress percentage (0-100)
            message: Status message
        """
        if self._state != 'running':
            logger.warning(f"Progress update ignored - state is {self._state}")
            return

        self.calibration_progress.emit(percent, message)
        logger.debug(f"Calibration progress: {percent}% - {message}")

    def complete_calibration(self, calibration_data: dict):
        """Mark calibration as complete.

        Args:
            calibration_data: Calibration data dictionary
        """
        self._state = 'complete'
        self._calibration_data = calibration_data
        self.calibration_complete.emit(calibration_data)
        logger.info("Calibration completed successfully")

    def fail_calibration(self, error_message: str):
        """Mark calibration as failed.

        Args:
            error_message: Error description
        """
        self._state = 'failed'
        self.calibration_failed.emit(error_message)
        logger.error(f"Calibration failed: {error_message}")

    def reset(self):
        """Reset to idle state."""
        self._state = 'idle'
        self._validation_results = []
        self._calibration_data = None
        logger.debug("Calibration viewmodel reset")

    def validate_spectrum(self, spectrum, channel: str):
        """Validate a single spectrum using service.

        Args:
            spectrum: Spectrum intensities (numpy array)
            channel: Channel identifier

        Returns:
            List of ValidationResult objects
        """
        if self._validator is None:
            logger.error("CalibrationValidator not injected")
            return []

        try:
            results = self._validator.validate_spectrum(spectrum, channel)
            logger.debug(f"Validated spectrum for channel {channel}: {len(results)} checks")
            return results
        except Exception as e:
            logger.exception(f"Spectrum validation failed: {e}")
            return []

    def validate_calibration_set(
        self,
        s_pol_ref: Dict,
        wavelengths,
        p_mode_intensities: Dict,
        s_mode_intensities: Dict,
        integration_time_s: float,
        integration_time_p: float
    ):
        """Validate complete calibration dataset using service.

        Emits validation_complete signal with results.

        Args:
            s_pol_ref: S-pol reference spectra per channel
            wavelengths: Wavelength array
            p_mode_intensities: P-mode LED intensities
            s_mode_intensities: S-mode LED intensities
            integration_time_s: S-mode integration time
            integration_time_p: P-mode integration time
        """
        if self._validator is None:
            logger.error("CalibrationValidator not injected")
            self.validation_complete.emit(False, [])
            return

        try:
            passed, results = self._validator.validate_calibration_set(
                s_pol_ref=s_pol_ref,
                wavelengths=wavelengths,
                p_mode_intensities=p_mode_intensities,
                s_mode_intensities=s_mode_intensities,
                integration_time_s=integration_time_s,
                integration_time_p=integration_time_p
            )

            self._validation_results = results
            self.validation_complete.emit(passed, results)

            logger.info(f"Calibration validation: {'PASSED' if passed else 'FAILED'} "
                       f"({len([r for r in results if r.severity == 'error'])} errors, "
                       f"{len([r for r in results if r.severity == 'warning'])} warnings)")

        except Exception as e:
            logger.exception(f"Calibration validation failed: {e}")
            self.validation_complete.emit(False, [])

    def get_validation_report(self) -> str:
        """Get formatted validation report.

        Returns:
            Formatted text report
        """
        if self._validator is None or not self._validation_results:
            return "No validation results available"

        try:
            return self._validator.format_validation_report(self._validation_results)
        except Exception as e:
            logger.exception(f"Failed to format validation report: {e}")
            return f"Error formatting report: {e}"

    def get_error_count(self) -> int:
        """Get number of validation errors."""
        return len([r for r in self._validation_results if r.severity == 'error'])

    def get_warning_count(self) -> int:
        """Get number of validation warnings."""
        return len([r for r in self._validation_results if r.severity == 'warning'])
