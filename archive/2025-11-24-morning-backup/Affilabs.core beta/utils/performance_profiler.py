"""Performance profiler for identifying bottlenecks in SPR acquisition system.

This module provides timing measurements for critical paths to identify
actual bottlenecks vs theoretical optimizations.

Usage:
    from utils.performance_profiler import PerformanceProfiler

    profiler = PerformanceProfiler()

    with profiler.measure('operation_name'):
        # ... code to measure ...
        pass

    profiler.print_stats()
"""

import time
import threading
from collections import defaultdict
from contextlib import contextmanager
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import numpy as np
from utils.logger import logger


@dataclass
class TimingStats:
    """Statistics for a timed operation."""
    name: str
    count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    times: List[float] = field(default_factory=list)

    def add_measurement(self, duration: float):
        """Add a timing measurement."""
        self.count += 1
        self.total_time += duration
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.times.append(duration)

        # Keep only last 1000 measurements to prevent memory growth
        if len(self.times) > 1000:
            self.times = self.times[-1000:]

    @property
    def mean_time(self) -> float:
        """Average time per call."""
        return self.total_time / self.count if self.count > 0 else 0.0

    @property
    def std_time(self) -> float:
        """Standard deviation of call times."""
        if len(self.times) < 2:
            return 0.0
        return float(np.std(self.times))

    @property
    def median_time(self) -> float:
        """Median call time."""
        if not self.times:
            return 0.0
        return float(np.median(self.times))

    @property
    def p95_time(self) -> float:
        """95th percentile call time."""
        if not self.times:
            return 0.0
        return float(np.percentile(self.times, 95))

    @property
    def p99_time(self) -> float:
        """99th percentile call time."""
        if not self.times:
            return 0.0
        return float(np.percentile(self.times, 99))


class PerformanceProfiler:
    """Thread-safe performance profiler for timing measurements."""

    def __init__(self, enabled: bool = True):
        """Initialize profiler.

        Args:
            enabled: If False, measurements are no-ops (zero overhead)
        """
        self.enabled = enabled
        self.stats: Dict[str, TimingStats] = defaultdict(lambda: TimingStats(name=""))
        self._lock = threading.Lock()
        self._active_timers: Dict[int, tuple] = {}  # thread_id -> (name, start_time)

    @contextmanager
    def measure(self, name: str):
        """Context manager for measuring execution time.

        Args:
            name: Name of the operation being measured

        Example:
            with profiler.measure('spectrum_processing'):
                process_spectrum(data)
        """
        if not self.enabled:
            yield
            return

        start_time = time.perf_counter()
        thread_id = threading.get_ident()

        # Store active timer for this thread
        with self._lock:
            self._active_timers[thread_id] = (name, start_time)

        try:
            yield
        finally:
            end_time = time.perf_counter()
            duration = end_time - start_time

            # Remove active timer and record measurement
            with self._lock:
                self._active_timers.pop(thread_id, None)
                if name not in self.stats:
                    self.stats[name] = TimingStats(name=name)
                self.stats[name].add_measurement(duration)

    def measure_func(self, name: str):
        """Decorator for measuring function execution time.

        Args:
            name: Name of the operation being measured

        Example:
            @profiler.measure_func('spectrum_processing')
            def process_spectrum(data):
                ...
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                with self.measure(name):
                    return func(*args, **kwargs)
            return wrapper
        return decorator

    def get_stats(self, name: str) -> Optional[TimingStats]:
        """Get statistics for a specific operation.

        Args:
            name: Operation name

        Returns:
            TimingStats object or None if not found
        """
        with self._lock:
            return self.stats.get(name)

    def get_all_stats(self) -> Dict[str, TimingStats]:
        """Get all timing statistics.

        Returns:
            Dictionary of operation name -> TimingStats
        """
        with self._lock:
            return dict(self.stats)

    def reset(self):
        """Reset all statistics."""
        with self._lock:
            self.stats.clear()
            self._active_timers.clear()

    def print_stats(self, sort_by: str = 'total', min_calls: int = 10):
        """Print formatted statistics table.

        Args:
            sort_by: Sort key ('total', 'mean', 'count', 'max')
            min_calls: Minimum number of calls to include in output
        """
        with self._lock:
            stats_list = list(self.stats.values())

        # Filter by minimum calls
        stats_list = [s for s in stats_list if s.count >= min_calls]

        if not stats_list:
            logger.info("No profiling data available")
            return

        # Sort
        if sort_by == 'total':
            stats_list.sort(key=lambda s: s.total_time, reverse=True)
        elif sort_by == 'mean':
            stats_list.sort(key=lambda s: s.mean_time, reverse=True)
        elif sort_by == 'count':
            stats_list.sort(key=lambda s: s.count, reverse=True)
        elif sort_by == 'max':
            stats_list.sort(key=lambda s: s.max_time, reverse=True)

        # Print header
        logger.info("=" * 120)
        logger.info("PERFORMANCE PROFILING RESULTS")
        logger.info("=" * 120)
        logger.info(f"{'Operation':<40} {'Count':>8} {'Total(s)':>10} {'Mean(ms)':>10} {'Median(ms)':>10} {'P95(ms)':>10} {'P99(ms)':>10} {'Max(ms)':>10}")
        logger.info("-" * 120)

        # Print rows
        for stat in stats_list:
            logger.info(
                f"{stat.name:<40} {stat.count:>8} "
                f"{stat.total_time:>10.3f} "
                f"{stat.mean_time*1000:>10.2f} "
                f"{stat.median_time*1000:>10.2f} "
                f"{stat.p95_time*1000:>10.2f} "
                f"{stat.p99_time*1000:>10.2f} "
                f"{stat.max_time*1000:>10.2f}"
            )

        logger.info("=" * 120)

        # Calculate totals
        total_time = sum(s.total_time for s in stats_list)
        total_calls = sum(s.count for s in stats_list)
        logger.info(f"Total tracked time: {total_time:.3f}s across {total_calls} operations")
        logger.info("")

    def print_hotspots(self, top_n: int = 10):
        """Print top N hotspots by total time.

        Args:
            top_n: Number of top operations to show
        """
        with self._lock:
            stats_list = list(self.stats.values())

        if not stats_list:
            logger.info("No profiling data available")
            return

        # Sort by total time
        stats_list.sort(key=lambda s: s.total_time, reverse=True)
        stats_list = stats_list[:top_n]

        logger.info("=" * 80)
        logger.info(f"TOP {top_n} HOTSPOTS (by total time)")
        logger.info("=" * 80)

        total_time = sum(s.total_time for s in self.stats.values())

        for i, stat in enumerate(stats_list, 1):
            pct = (stat.total_time / total_time * 100) if total_time > 0 else 0
            logger.info(
                f"{i:2d}. {stat.name:<40} "
                f"{stat.total_time:>8.3f}s ({pct:>5.1f}%) "
                f"[{stat.count} calls, {stat.mean_time*1000:.2f}ms avg]"
            )

        logger.info("=" * 80)
        logger.info("")

    def export_to_file(self, filepath: str):
        """Export timing data to CSV file.

        Args:
            filepath: Output CSV file path
        """
        import csv

        with self._lock:
            stats_list = sorted(self.stats.values(), key=lambda s: s.total_time, reverse=True)

        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Operation', 'Count', 'Total(s)', 'Mean(ms)', 'Std(ms)',
                'Median(ms)', 'P95(ms)', 'P99(ms)', 'Min(ms)', 'Max(ms)'
            ])

            for stat in stats_list:
                writer.writerow([
                    stat.name,
                    stat.count,
                    f"{stat.total_time:.3f}",
                    f"{stat.mean_time*1000:.2f}",
                    f"{stat.std_time*1000:.2f}",
                    f"{stat.median_time*1000:.2f}",
                    f"{stat.p95_time*1000:.2f}",
                    f"{stat.p99_time*1000:.2f}",
                    f"{stat.min_time*1000:.2f}",
                    f"{stat.max_time*1000:.2f}"
                ])

        logger.info(f"Profiling data exported to: {filepath}")


# Global profiler instance
_global_profiler: Optional[PerformanceProfiler] = None


def get_profiler() -> PerformanceProfiler:
    """Get global profiler instance (creates if needed).

    Returns:
        Global PerformanceProfiler instance
    """
    global _global_profiler
    if _global_profiler is None:
        # Check if profiling is enabled via environment variable or settings
        import os
        enabled = os.environ.get('SPR_PROFILING_ENABLED', '0') == '1'

        try:
            from settings import PROFILING_ENABLED
            enabled = PROFILING_ENABLED
        except (ImportError, AttributeError):
            pass

        _global_profiler = PerformanceProfiler(enabled=enabled)

        if enabled:
            logger.info("⏱️ Performance profiling ENABLED - timing measurements active")
        else:
            logger.debug("Performance profiling DISABLED - set PROFILING_ENABLED=True in settings.py to enable")

    return _global_profiler


def enable_profiling():
    """Enable global profiling."""
    global _global_profiler
    profiler = get_profiler()
    profiler.enabled = True
    logger.info("⏱️ Performance profiling ENABLED")


def disable_profiling():
    """Disable global profiling."""
    global _global_profiler
    profiler = get_profiler()
    profiler.enabled = False
    logger.info("Performance profiling DISABLED")


# Convenience functions for global profiler
def measure(name: str):
    """Measure execution time using global profiler."""
    return get_profiler().measure(name)


def print_profile():
    """Print profiling statistics."""
    get_profiler().print_stats()


def print_hotspots(top_n: int = 10):
    """Print top N hotspots."""
    get_profiler().print_hotspots(top_n)


def reset_profiler():
    """Reset profiling statistics."""
    get_profiler().reset()
