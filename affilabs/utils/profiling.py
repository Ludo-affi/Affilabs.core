"""Profiling utilities for performance measurement.

Simple context manager for optional performance profiling.
"""

from contextlib import contextmanager


@contextmanager
def measure(operation_name: str):
    """Context manager for measuring operation performance.

    This is a no-op stub. When PROFILING_ENABLED is True in settings,
    this could be enhanced to collect actual metrics.

    Args:
        operation_name: Name of the operation being measured

    Yields:
        None
    """
    yield
