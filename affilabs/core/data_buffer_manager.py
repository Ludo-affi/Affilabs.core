from __future__ import annotations

"""Data buffer management for SPR signal processing."""

from dataclasses import dataclass, field

import numpy as np


@dataclass
class ChannelBuffer:
    """Buffer for a single channel's data."""

    time: np.ndarray = field(
        default_factory=lambda: np.array([]),
    )  # Elapsed time (seconds)
    timestamp: np.ndarray = field(
        default_factory=lambda: np.array([]),
    )  # Absolute timestamp (seconds since epoch)
    wavelength: np.ndarray = field(default_factory=lambda: np.array([]))
    spr: np.ndarray = field(default_factory=lambda: np.array([]))  # Delta SPR in RU


@dataclass
class IntensityBuffer:
    """Buffer for intensity leak detection."""

    times: list[float] = field(default_factory=list)
    intensities: list[float] = field(default_factory=list)


class DataBufferManager:
    """Manages all data buffers for the application.

    Handles:
    - Timeline data (full experiment for each channel)
    - Cycle data (selected region for each channel)
    - Baseline wavelengths (reference points)
    - Intensity buffers (for leak detection)
    - Smart memory management for long experiments

    Memory Strategy:
    - Live Sensorgram: Navigation tool, aggressively downsampled for display
    - Full data saved to CSV as it arrives (no loss)
    - Old data trimmed from memory when limit reached
    - Cycle of Interest: Full resolution (≤1 hour @ 4 Hz = 14,400 points)
    """

    def __init__(self) -> None:
        """Initialize all data buffers."""
        # Timeline data for full experiment view
        self.timeline_data: dict[str, ChannelBuffer] = {
            "a": ChannelBuffer(),
            "b": ChannelBuffer(),
            "c": ChannelBuffer(),
            "d": ChannelBuffer(),
        }

        # Cycle data for region of interest view
        self.cycle_data: dict[str, ChannelBuffer] = {
            "a": ChannelBuffer(),
            "b": ChannelBuffer(),
            "c": ChannelBuffer(),
            "d": ChannelBuffer(),
        }

        # Baseline wavelengths for each channel (for delta SPR calculation)
        self.baseline_wavelengths: dict[str, float | None] = {
            "a": None,
            "b": None,
            "c": None,
            "d": None,
        }

        # Intensity buffers for leak detection (5-second sliding window)
        self.intensity_buffers: dict[str, IntensityBuffer] = {
            "a": IntensityBuffer(),
            "b": IntensityBuffer(),
            "c": IntensityBuffer(),
            "d": IntensityBuffer(),
        }

    def append_timeline_point(
        self,
        channel: str,
        time: float,
        wavelength: float,
        timestamp: float | None = None,
        ema_state: dict | None = None,
        ema_alpha: float = 0.0,
    ) -> float:
        """Append a data point to the timeline buffer with optional EMA filtering.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            time: Elapsed time in seconds
            wavelength: Wavelength in nanometers (raw, unfiltered)
            timestamp: Absolute timestamp (seconds since epoch), optional
            ema_state: Dictionary containing previous EMA values per channel
            ema_alpha: EMA smoothing factor (0=no filtering, higher=less smoothing)

        Returns:
            Filtered wavelength value (or raw if ema_alpha=0)

        """
        buffer = self.timeline_data[channel]

        # Apply EMA filtering if enabled
        display_wavelength = wavelength
        if ema_alpha > 0 and ema_state is not None:
            if ema_state.get(channel) is None:
                # First point - no previous state
                display_wavelength = wavelength
            else:
                # EMA formula: y[i] = α * x[i] + (1 - α) * y[i-1]
                display_wavelength = ema_alpha * wavelength + (1 - ema_alpha) * ema_state[channel]
            # Update EMA state for next point
            ema_state[channel] = display_wavelength

        # Check if new point is out of order (due to threading/async arrival)
        if len(buffer.time) > 0 and time < buffer.time[-1]:
            # Point arrived late - insert in sorted position to maintain monotonic time
            insert_idx = np.searchsorted(buffer.time, time)
            buffer.time = np.insert(buffer.time, insert_idx, time)
            buffer.wavelength = np.insert(buffer.wavelength, insert_idx, display_wavelength)
            if timestamp is not None and len(buffer.timestamp) > 0:
                buffer.timestamp = np.insert(buffer.timestamp, insert_idx, timestamp)
        else:
            # Normal case - append to end
            buffer.time = np.append(buffer.time, time)
            buffer.wavelength = np.append(buffer.wavelength, display_wavelength)
            if timestamp is not None:
                buffer.timestamp = np.append(buffer.timestamp, timestamp)

        return display_wavelength

    def append_intensity_point(
        self,
        channel: str,
        timestamp: float,
        intensity: float,
    ) -> None:
        """Append an intensity measurement for leak detection.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            timestamp: Absolute timestamp
            intensity: Raw intensity value

        """
        buffer = self.intensity_buffers[channel]
        buffer.times.append(timestamp)
        buffer.intensities.append(intensity)

    def trim_intensity_buffer(self, channel: str, cutoff_time: float) -> None:
        """Remove intensity data older than cutoff time.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            cutoff_time: Remove all data before this timestamp

        """
        buffer = self.intensity_buffers[channel]
        while len(buffer.times) > 0 and buffer.times[0] < cutoff_time:
            buffer.times.pop(0)
            buffer.intensities.pop(0)

    def get_intensity_average(self, channel: str) -> float | None:
        """Get average intensity over the buffer window.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')

        Returns:
            Average intensity or None if buffer is empty

        """
        buffer = self.intensity_buffers[channel]
        if len(buffer.intensities) == 0:
            return None
        return np.mean(buffer.intensities)

    def get_intensity_timespan(self, channel: str) -> float | None:
        """Get time span covered by intensity buffer.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')

        Returns:
            Time span in seconds or None if insufficient data

        """
        buffer = self.intensity_buffers[channel]
        if len(buffer.times) < 2:
            return None
        return buffer.times[-1] - buffer.times[0]

    def update_cycle_data(
        self,
        channel: str,
        cycle_time: np.ndarray,
        cycle_wavelength: np.ndarray,
        delta_spr: np.ndarray,
        cycle_timestamp: np.ndarray = None,
    ) -> None:
        """Update cycle data for a channel.

        NOTE: This REPLACES the buffer data (used for fixed/cursor mode).
        For moving window mode that accumulates, use append_cycle_data instead.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            cycle_time: Time array for cycle (elapsed time)
            cycle_wavelength: Wavelength array for cycle
            delta_spr: Delta SPR array in RU
            cycle_timestamp: Absolute timestamp array (optional)

        """
        buffer = self.cycle_data[channel]
        buffer.time = cycle_time
        buffer.wavelength = cycle_wavelength
        buffer.spr = delta_spr
        # Ensure timestamp array matches length of data arrays
        if cycle_timestamp is not None and len(cycle_timestamp) == len(cycle_time):
            buffer.timestamp = cycle_timestamp
        else:
            # Initialize empty timestamp array if not provided or length mismatch
            buffer.timestamp = np.array([])

    def append_cycle_data(
        self,
        channel: str,
        new_time: list,
        new_wavelength: list,
        new_delta_spr: list,
        new_timestamp: list | None = None,
        max_window_seconds: float = 600,  # Default 10 minutes
    ) -> None:
        """Append new data to cycle buffer (for moving window mode).

        Accumulates new points and removes old points outside the time window.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            new_time: New time points to append
            new_wavelength: New wavelength points to append
            new_delta_spr: New delta SPR points to append
            new_timestamp: New timestamp points to append (optional)
            max_window_seconds: Maximum time window to keep (removes older data)

        """
        if len(new_time) == 0:
            return

        buffer = self.cycle_data[channel]

        # Convert lists to arrays
        new_time_arr = np.array(new_time)
        new_wavelength_arr = np.array(new_wavelength)
        new_delta_spr_arr = np.array(new_delta_spr)

        # DEBUG: (disabled) heavy console printing can cause serious lag during live acquisition
        # To re-enable, switch to logger.debug and throttle frequency.
        # logger.debug(
        #     f"[BUFFER-DEBUG] Ch {channel}: Appending {len(new_delta_spr_arr)} points"
        # )
        # logger.debug(
        #     f"[BUFFER-DEBUG] Ch {channel}: delta_spr input range=[{new_delta_spr_arr.min():.2f}, {new_delta_spr_arr.max():.2f}] RU"
        # )
        # logger.debug(
        #     f"[BUFFER-DEBUG] Ch {channel}: delta_spr first 5 values: {new_delta_spr_arr[:5]}"
        # )

        # Append new data
        buffer.time = np.concatenate([buffer.time, new_time_arr])
        buffer.wavelength = np.concatenate([buffer.wavelength, new_wavelength_arr])
        buffer.spr = np.concatenate([buffer.spr, new_delta_spr_arr])

        # DEBUG: (disabled) heavy console printing can cause serious lag during live acquisition
        # logger.debug(
        #     f"[BUFFER-DEBUG] Ch {channel}: After append, buffer.spr has {len(buffer.spr)} points"
        # )
        # logger.debug(
        #     f"[BUFFER-DEBUG] Ch {channel}: After append, buffer.spr range=[{buffer.spr.min():.2f}, {buffer.spr.max():.2f}] RU"
        # )

        if new_timestamp is not None:
            new_timestamp_arr = np.array(new_timestamp)
            if len(buffer.timestamp) > 0:
                buffer.timestamp = np.concatenate([buffer.timestamp, new_timestamp_arr])
            else:
                buffer.timestamp = new_timestamp_arr

        # Remove old data outside the window
        if len(buffer.time) > 0:
            current_time = buffer.time[-1]
            cutoff_time = current_time - max_window_seconds

            # Keep only points within the window
            mask = buffer.time >= cutoff_time
            buffer.time = buffer.time[mask]
            buffer.wavelength = buffer.wavelength[mask]
            buffer.spr = buffer.spr[mask]
            if len(buffer.timestamp) > 0:
                buffer.timestamp = buffer.timestamp[mask]

    def set_baseline(self, channel: str, wavelength: float) -> None:
        """Set baseline wavelength for a channel.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            wavelength: Baseline wavelength in nm

        """
        self.baseline_wavelengths[channel] = wavelength

    def clear_baseline(self, channel: str) -> None:
        """Clear baseline for a channel.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')

        """
        self.baseline_wavelengths[channel] = None

    def clear_all_baselines(self) -> None:
        """Clear baselines for all channels."""
        for channel in self.baseline_wavelengths:
            self.baseline_wavelengths[channel] = None

    def get_timeline_length(self, channel: str) -> int:
        """Get number of points in timeline buffer.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')

        Returns:
            Number of data points

        """
        return len(self.timeline_data[channel].time)

    def get_cycle_length(self, channel: str) -> int:
        """Get number of points in cycle buffer.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')

        Returns:
            Number of data points

        """
        return len(self.cycle_data[channel].time)

    def extract_cycle_region(
        self,
        channel: str,
        start_time: float,
        stop_time: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Extract data within time range from timeline buffer.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            start_time: Start time in seconds (elapsed)
            stop_time: Stop time in seconds (elapsed)

        Returns:
            Tuple of (time_array, wavelength_array, timestamp_array) within range

        """
        buffer = self.timeline_data[channel]
        if len(buffer.time) == 0:
            return np.array([]), np.array([]), np.array([])

        mask = (buffer.time >= start_time) & (buffer.time <= stop_time)
        timestamps = buffer.timestamp[mask] if len(buffer.timestamp) > 0 else np.array([])
        return buffer.time[mask], buffer.wavelength[mask], timestamps

    def clear_all(self) -> None:
        """Clear all buffers (for new experiment)."""
        for channel in ["a", "b", "c", "d"]:
            self.timeline_data[channel] = ChannelBuffer()
            self.cycle_data[channel] = ChannelBuffer()
            self.baseline_wavelengths[channel] = None
            self.intensity_buffers[channel] = IntensityBuffer()

    def get_latest_value(self, channel: str) -> float | None:
        """Get most recent wavelength value for a channel.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')

        Returns:
            Latest wavelength or None if no data

        """
        buffer = self.timeline_data[channel]
        if len(buffer.wavelength) == 0:
            return None
        return buffer.wavelength[-1]

    def get_latest_time(self, channel: str) -> float | None:
        """Get most recent elapsed time for a channel.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')

        Returns:
            Latest elapsed time or None if no data

        """
        buffer = self.timeline_data[channel]
        if len(buffer.time) == 0:
            return None
        return buffer.time[-1]

    def trim_timeline_memory(self, channel: str, max_points: int, trim_to: int) -> int:
        """Trim old data from timeline buffer when memory limit reached.

        This is safe because all data is saved to CSV as it arrives.
        Keeps most recent data for current viewing.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            max_points: Trim if buffer exceeds this size
            trim_to: Keep this many most recent points after trimming

        Returns:
            Number of points removed (0 if no trimming needed)

        """
        buffer = self.timeline_data[channel]
        current_size = len(buffer.time)

        if current_size <= max_points:
            return 0  # No trimming needed

        # Keep the most recent trim_to points
        points_to_remove = current_size - trim_to

        # Trim old data (keep recent data)
        buffer.time = buffer.time[-trim_to:]
        buffer.wavelength = buffer.wavelength[-trim_to:]
        if len(buffer.timestamp) > 0:
            buffer.timestamp = buffer.timestamp[-trim_to:]

        return points_to_remove

    def get_downsampled_timeline(
        self,
        channel: str,
        target_points: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Get downsampled timeline data for efficient display.

        Uses intelligent downsampling to preserve signal features while
        reducing point count for smooth rendering.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            target_points: Target number of points for display

        Returns:
            Tuple of (time_array, wavelength_array) downsampled to ~target_points

        """
        buffer = self.timeline_data[channel]

        if len(buffer.time) <= target_points:
            # No downsampling needed
            return buffer.time, buffer.wavelength

        # Calculate downsampling factor
        downsample_factor = max(1, len(buffer.time) // target_points)

        # Simple decimation (every Nth point)
        # For navigation view, this is sufficient - full data in CSV
        time_ds = buffer.time[::downsample_factor]
        wavelength_ds = buffer.wavelength[::downsample_factor]

        # Always include the last point (most recent data)
        if time_ds[-1] != buffer.time[-1]:
            time_ds = np.append(time_ds, buffer.time[-1])
            wavelength_ds = np.append(wavelength_ds, buffer.wavelength[-1])

        return time_ds, wavelength_ds

    def get_memory_stats(self) -> dict[str, dict[str, int]]:
        """Get memory usage statistics for all buffers.

        Returns:
            Dict with memory stats per channel

        """
        stats = {}
        for ch in ["a", "b", "c", "d"]:
            timeline_points = len(self.timeline_data[ch].time)
            cycle_points = len(self.cycle_data[ch].time)

            # Rough memory estimate (bytes)
            # Each point has time (8) + wavelength (8) + timestamp (8) = 24 bytes
            timeline_bytes = timeline_points * 24 * 3  # time, wavelength, timestamp
            cycle_bytes = cycle_points * 24 * 4  # time, wavelength, spr, timestamp

            stats[ch] = {
                "timeline_points": timeline_points,
                "cycle_points": cycle_points,
                "timeline_kb": timeline_bytes // 1024,
                "cycle_kb": cycle_bytes // 1024,
            }

        return stats
