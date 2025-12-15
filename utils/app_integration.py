"""Integration module for error boundaries, logging, and testing systems.

This module provides easy integration of the new systems into the main application.
"""

import atexit
import traceback
from typing import Any

# Import our new systems
from utils.error_boundary import (
    calibration_error_boundary,
    data_acquisition_error_boundary,
    error_boundary,
    hardware_error_boundary,
    ui_error_boundary,
)
from utils.logging_system import (
    get_logger,
    log_security_event,
    log_shutdown,
    log_startup,
    measure_performance,
)

# Version information
APP_VERSION = "3.2.9"


class ApplicationIntegration:
    """Integration manager for all new systems."""

    def __init__(self, app_name: str = "SPR_Control"):
        self.app_name = app_name
        self.logger = get_logger("integration")
        self.initialized = False

    def initialize(self, config: dict[str, Any]) -> bool:
        """Initialize all systems."""
        try:
            # Initialize logging first
            log_startup(APP_VERSION, config)
            self.logger.info("Initializing application systems...")

            # Connect error boundary signals
            self._setup_error_boundary()

            # Register shutdown handler
            atexit.register(self._shutdown_handler)

            self.initialized = True
            self.logger.info("All systems initialized successfully")
            return True

        except Exception as e:
            print(f"Failed to initialize systems: {e}")
            traceback.print_exc()
            return False

    def _setup_error_boundary(self):
        """Setup error boundary signal connections."""
        # Connect error signals to logging
        error_boundary.error_occurred.connect(self._on_error_occurred)
        error_boundary.recovery_attempted.connect(self._on_recovery_attempted)
        error_boundary.shutdown_requested.connect(self._on_shutdown_requested)

        self.logger.info("Error boundary signals connected")

    def _on_error_occurred(self, severity: str, category: str, message: str):
        """Handle error occurred signal."""
        self.logger.error(
            f"Error boundary triggered: {severity} | {category} | {message}",
        )

        # Log security event for certain error types
        if category in ["hardware", "configuration"]:
            log_security_event("access", resource=category, success=False)

    def _on_recovery_attempted(self, error_id: str, success: bool):
        """Handle recovery attempt signal."""
        if success:
            self.logger.info(f"Recovery successful for error: {error_id}")
        else:
            self.logger.warning(f"Recovery failed for error: {error_id}")

    def _on_shutdown_requested(self, reason: str):
        """Handle shutdown request signal."""
        self.logger.critical(f"Shutdown requested: {reason}")
        log_shutdown(reason)

    def _shutdown_handler(self):
        """Handle application shutdown."""
        if self.initialized:
            log_shutdown("Normal application exit")


# Global integration instance
app_integration = ApplicationIntegration()


# Decorator functions for easy use in existing code
def with_hardware_protection(recovery_fn: Optional[callable] = None):
    """Decorator for hardware operations with error protection."""
    return hardware_error_boundary(recovery_fn=recovery_fn)


def with_data_protection():
    """Decorator for data acquisition operations with error protection."""
    return data_acquisition_error_boundary()


def with_calibration_protection():
    """Decorator for calibration operations with error protection."""
    return calibration_error_boundary()


def with_performance_monitoring(operation_name: str):
    """Decorator for performance monitoring."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            with measure_performance(operation_name):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def log_hardware_command(device: str, command: str, parameters: dict[str, Any]):
    """Log hardware commands for security audit."""
    log_security_event(
        "hardware_command",
        device=device,
        command=command,
        parameters=parameters,
    )


def log_config_change(component: str, changes: dict[str, Any]):
    """Log configuration changes for security audit."""
    log_security_event("config_change", component=component, changes=changes)


# Example usage decorators that can be applied to existing methods
def safe_hardware_operation(func):
    """Decorator for safe hardware operations."""

    @hardware_error_boundary()
    def wrapper(*args, **kwargs):
        with measure_performance(f"hardware_{func.__name__}"):
            return func(*args, **kwargs)

    return wrapper


def safe_data_operation(func):
    """Decorator for safe data operations."""

    @data_acquisition_error_boundary()
    def wrapper(*args, **kwargs):
        with measure_performance(f"data_{func.__name__}"):
            return func(*args, **kwargs)

    return wrapper


def safe_calibration_operation(func):
    """Decorator for safe calibration operations."""

    @calibration_error_boundary()
    def wrapper(*args, **kwargs):
        with measure_performance(f"calibration_{func.__name__}"):
            return func(*args, **kwargs)

    return wrapper


def safe_ui_operation(func):
    """Decorator for safe UI operations."""

    @ui_error_boundary()
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


# Quick initialization function
def initialize_app_systems(config: dict[str, Any]) -> bool:
    """Quick initialization of all application systems."""
    return app_integration.initialize(config)


# Testing integration
def run_system_tests():
    """Run system tests if testing framework is available."""
    try:
        from tests.test_framework import run_all_tests

        return run_all_tests()
    except ImportError:
        print("Testing framework not available")
        return None
