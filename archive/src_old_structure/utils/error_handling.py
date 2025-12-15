"""Error handling utilities for SPR application.

Provides decorator-based error boundaries and safe execution wrappers
to prevent crashes and ensure graceful degradation.
"""

import functools
import traceback
from collections.abc import Callable
from typing import Any, TypeVar

from utils.logger import logger

T = TypeVar("T")


def safe_execute(
    default_return: Any | None = None,
    log_errors: bool = True,
    error_message: str = "Operation failed",
):
    """Decorator to safely execute functions with error handling.

    Wraps a function to catch exceptions and return a default value instead
    of crashing. Useful for non-critical operations that should degrade gracefully.

    Args:
        default_return: Value to return if function raises exception
        log_errors: Whether to log exceptions (default: True)
        error_message: Custom error message prefix

    Returns:
        Decorated function that catches all exceptions

    Example:
        @safe_execute(default_return=0.0, error_message="Failed to calculate")
        def calculate_something(x, y):
            return risky_operation(x, y)

    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(f"{error_message}: {func.__name__} - {e}")
                    logger.debug(f"Traceback: {traceback.format_exc()}")
                return default_return

        return wrapper

    return decorator


def safe_property(default_value: Any = None):
    """Decorator for class properties that should never raise exceptions.

    Useful for properties that might fail due to uninitialized state
    but should return a sensible default instead of crashing.

    Args:
        default_value: Value to return if property access fails

    Example:
        @safe_property(default_value=0)
        @property
        def temperature(self):
            return self.sensor.read_temperature()

    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.debug(f"Property access failed: {func.__name__} - {e}")
                return default_value

        return wrapper

    return decorator


def with_timeout_recovery(
    timeout_value: Any,
    timeout_message: str = "Operation timed out",
):
    """Decorator to handle timeout exceptions gracefully.

    Specifically catches timeout-related exceptions and returns a fallback value.

    Args:
        timeout_value: Value to return on timeout
        timeout_message: Log message for timeout events

    Example:
        @with_timeout_recovery(timeout_value=None, timeout_message="Serial read timed out")
        def read_serial_data(self):
            return self.serial.read()

    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except (TimeoutError, ConnectionError, OSError) as e:
                logger.warning(f"{timeout_message}: {func.__name__} - {e}")
                return timeout_value

        return wrapper

    return decorator


def log_exceptions(
    log_level: str = "error",
    reraise: bool = False,
):
    """Decorator to log exceptions with optional re-raising.

    Useful for debugging and monitoring without changing error propagation behavior.

    Args:
        log_level: Logging level ('debug', 'info', 'warning', 'error')
        reraise: Whether to re-raise the exception after logging

    Example:
        @log_exceptions(log_level="warning", reraise=True)
        def critical_operation(self):
            # Exception will be logged and then propagated
            return important_calculation()

    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_func = getattr(logger, log_level, logger.error)
                log_func(f"Exception in {func.__name__}: {e}")
                log_func(f"Traceback:\n{traceback.format_exc()}")

                if reraise:
                    raise
                return None

        return wrapper

    return decorator


class ErrorContext:
    """Context manager for safe code execution blocks.

    Provides a cleaner alternative to try/except for code blocks that
    should handle errors gracefully.

    Example:
        with ErrorContext("Reading sensor data", default_return=0.0) as ctx:
            value = sensor.read()
            ctx.result = value

        # ctx.result contains either the value or default_return
        print(f"Sensor value: {ctx.result}")

    """

    def __init__(
        self,
        operation_name: str,
        default_return: Any = None,
        log_errors: bool = True,
    ):
        """Initialize error context.

        Args:
            operation_name: Description of the operation for logging
            default_return: Value to use if operation fails
            log_errors: Whether to log exceptions

        """
        self.operation_name = operation_name
        self.default_return = default_return
        self.log_errors = log_errors
        self.result = default_return
        self.error = None

    def __enter__(self):
        """Enter context."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and handle any exceptions."""
        if exc_type is not None:
            self.error = exc_val
            if self.log_errors:
                logger.error(f"{self.operation_name} failed: {exc_val}")
                logger.debug(f"Traceback:\n{traceback.format_exc()}")
            # Suppress the exception
            return True
        return False
