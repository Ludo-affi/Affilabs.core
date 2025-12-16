"""Comprehensive error boundary system for the SPR application."""

import functools
import logging
import sys
import traceback
from collections.abc import Callable
from enum import Enum
from typing import ParamSpec, TypeVar

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

# Type variables for proper typing
P = ParamSpec("P")
T = TypeVar("T")


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = "low"  # Warning, app continues
    MEDIUM = "medium"  # Error, feature disabled
    HIGH = "high"  # Critical error, safe shutdown
    CRITICAL = "critical"  # Immediate shutdown required


class ErrorCategory(Enum):
    """Error categories for better handling."""

    HARDWARE = "hardware"
    DATA_ACQUISITION = "data_acquisition"
    CALIBRATION = "calibration"
    UI = "ui"
    CONFIGURATION = "configuration"
    THREADING = "threading"
    MEMORY = "memory"
    VALIDATION = "validation"


class ErrorBoundary(QObject):
    """Centralized error boundary for the application."""

    # Signals for error communication
    error_occurred = Signal(str, str, str)  # severity, category, message
    recovery_attempted = Signal(str, bool)  # error_id, success
    shutdown_requested = Signal(str)  # reason

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.error_count = 0
        self.max_errors = 50  # Maximum errors before forced shutdown
        self.error_history = []

    def handle_error(
        self,
        error: Exception,
        category: ErrorCategory,
        severity: ErrorSeverity,
        context: str = "",
        recovery_fn: Callable | None = None,
        user_message: str | None = None,
    ) -> bool:
        """Handle an error with appropriate response based on severity.

        Returns True if error was handled and app can continue.
        """
        self.error_count += 1
        error_id = f"{category.value}_{self.error_count}"

        # Log the error
        self._log_error(error, category, severity, context, error_id)

        # Store in history
        self.error_history.append(
            {
                "id": error_id,
                "error": str(error),
                "category": category.value,
                "severity": severity.value,
                "context": context,
                "traceback": traceback.format_exc(),
            },
        )

        # Emit signal
        self.error_occurred.emit(severity.value, category.value, str(error))

        # Handle based on severity
        if severity == ErrorSeverity.CRITICAL:
            self._handle_critical_error(error, context, user_message)
            return False

        if severity == ErrorSeverity.HIGH:
            return self._handle_high_severity_error(
                error,
                context,
                recovery_fn,
                user_message,
            )

        if severity == ErrorSeverity.MEDIUM:
            return self._handle_medium_severity_error(
                error,
                context,
                recovery_fn,
                user_message,
            )

        # LOW severity
        return self._handle_low_severity_error(error, context, user_message)

    def _log_error(
        self,
        error: Exception,
        category: ErrorCategory,
        severity: ErrorSeverity,
        context: str,
        error_id: str,
    ):
        """Log error with appropriate level."""
        log_msg = f"[{error_id}] {category.value.upper()}: {error}"
        if context:
            log_msg += f" | Context: {context}"

        if severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_msg, exc_info=True)
        elif severity == ErrorSeverity.HIGH:
            self.logger.error(log_msg, exc_info=True)
        elif severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_msg, exc_info=True)
        else:
            self.logger.info(log_msg)

    def _handle_critical_error(
        self,
        error: Exception,
        context: str,
        user_message: str | None,
    ):
        """Handle critical errors that require immediate shutdown."""
        msg = user_message or f"Critical error occurred: {error}"
        self.logger.critical(f"CRITICAL ERROR - Initiating shutdown: {msg}")
        self.shutdown_requested.emit(f"Critical error: {error}")

        # Show user dialog
        try:
            QMessageBox.critical(
                None,
                "Critical Error",
                f"{msg}\n\nThe application will now close.",
            )
        except:
            print(f"CRITICAL ERROR: {msg}")
        sys.exit(1)

    def _handle_high_severity_error(
        self,
        error: Exception,
        context: str,
        recovery_fn: Callable | None,
        user_message: str | None,
    ) -> bool:
        """Handle high severity errors with recovery attempts."""
        if recovery_fn:
            try:
                recovery_fn()
                self.logger.info(f"Recovery successful for error: {error}")
                self.recovery_attempted.emit(f"high_{self.error_count}", True)
                return True
            except Exception as recovery_error:
                self.logger.error(f"Recovery failed: {recovery_error}")
                self.recovery_attempted.emit(f"high_{self.error_count}", False)

        # Show warning to user
        msg = user_message or f"Error in {context}: {error}"
        try:
            QMessageBox.warning(
                None,
                "Error",
                f"{msg}\n\nSome features may be disabled.",
            )
        except:
            print(f"ERROR: {msg}")
        return False

    def _handle_medium_severity_error(
        self,
        error: Exception,
        context: str,
        recovery_fn: Callable | None,
        user_message: str | None,
    ) -> bool:
        """Handle medium severity errors."""
        if recovery_fn:
            try:
                recovery_fn()
                self.recovery_attempted.emit(f"medium_{self.error_count}", True)
                return True
            except Exception:
                self.recovery_attempted.emit(f"medium_{self.error_count}", False)

        if user_message:
            try:
                QMessageBox.information(None, "Warning", user_message)
            except:
                print(f"WARNING: {user_message}")
        return True

    def _handle_low_severity_error(
        self,
        error: Exception,
        context: str,
        user_message: str | None,
    ) -> bool:
        """Handle low severity errors (warnings)."""
        if user_message:
            self.logger.info(f"User notification: {user_message}")
        return True


# Global error boundary instance
error_boundary = ErrorBoundary()


def with_error_boundary(
    category: ErrorCategory,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    recovery_fn: Callable | None = None,
    user_message: str | None = None,
    context: str = "",
):
    """Decorator to wrap functions with error boundary protection."""

    def decorator(func: Callable[P, T]) -> Callable[P, T | None]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                ctx = context or f"{func.__module__}.{func.__name__}"
                handled = error_boundary.handle_error(
                    error=e,
                    category=category,
                    severity=severity,
                    context=ctx,
                    recovery_fn=recovery_fn,
                    user_message=user_message,
                )
                if not handled and severity in [
                    ErrorSeverity.HIGH,
                    ErrorSeverity.CRITICAL,
                ]:
                    raise
                return None

        return wrapper

    return decorator


def hardware_error_boundary(
    recovery_fn: Callable | None = None,
    user_message: str | None = None,
):
    """Specific decorator for hardware operations."""
    return with_error_boundary(
        category=ErrorCategory.HARDWARE,
        severity=ErrorSeverity.HIGH,
        recovery_fn=recovery_fn,
        user_message=user_message,
    )


def data_acquisition_error_boundary(recovery_fn: Callable | None = None):
    """Specific decorator for data acquisition operations."""
    return with_error_boundary(
        category=ErrorCategory.DATA_ACQUISITION,
        severity=ErrorSeverity.MEDIUM,
        recovery_fn=recovery_fn,
        user_message="Data acquisition error occurred. Please try again.",
    )


def calibration_error_boundary(recovery_fn: Callable | None = None):
    """Specific decorator for calibration operations."""
    return with_error_boundary(
        category=ErrorCategory.CALIBRATION,
        severity=ErrorSeverity.MEDIUM,
        recovery_fn=recovery_fn,
        user_message="Calibration error occurred. Please check hardware and try again.",
    )


def ui_error_boundary():
    """Specific decorator for UI operations."""
    return with_error_boundary(
        category=ErrorCategory.UI,
        severity=ErrorSeverity.LOW,
        user_message="UI error occurred. Interface may need refresh.",
    )


def validation_error_boundary():
    """Specific decorator for validation operations."""
    return with_error_boundary(
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.MEDIUM,
        user_message="Validation error: Please check your inputs and try again.",
    )
