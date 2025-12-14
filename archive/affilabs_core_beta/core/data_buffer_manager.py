"""Data buffer management for SPR signal processing."""

import numpy as np
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field


@dataclass
class ChannelBuffer:
    """Buffer for a single channel's data."""
    time: np.ndarray = field(default_factory=lambda: np.array([]))  # Elapsed time (seconds)
    timestamp: np.ndarray = field(default_factory=lambda: np.array([]))  # Absolute timestamp (seconds since epoch)
    wavelength: np.ndarray = field(default_factory=lambda: np.array([]))
    spr: np.ndarray = field(default_factory=lambda: np.array([]))  # Delta SPR in RU


@dataclass
class IntensityBuffer:
    """Buffer for intensity leak detection."""
    times: List[float] = field(default_factory=list)
    intensities: List[float] = field(default_factory=list)


class DataBufferManager:
    """Manages all data buffers for the application.

    Handles:
    - Timeline data (full experiment for each channel)
    - Cycle data (selected region for each channel)
    - Baseline wavelengths (reference points)
    - Intensity buffers (for leak detection)
    """

    def __init__(self):
        """Initialize all data buffers."""
        # Timeline data for full experiment view
        self.timeline_data: Dict[str, ChannelBuffer] = {
            'a': ChannelBuffer(),
            'b': ChannelBuffer(),
            'c': ChannelBuffer(),
            'd': ChannelBuffer()
        }

        # Cycle data for region of interest view
        self.cycle_data: Dict[str, ChannelBuffer] = {
            'a': ChannelBuffer(),
            'b': ChannelBuffer(),
            'c': ChannelBuffer(),
            'd': ChannelBuffer()
        }

        # Baseline wavelengths for each channel (for delta SPR calculation)
        self.baseline_wavelengths: Dict[str, Optional[float]] = {
            'a': None,
            'b': None,
            'c': None,
            'd': None
        }

        # Intensity buffers for leak detection (5-second sliding window)
        self.intensity_buffers: Dict[str, IntensityBuffer] = {
            'a': IntensityBuffer(),
            'b': IntensityBuffer(),
            'c': IntensityBuffer(),
            'd': IntensityBuffer()
        }

    def append_timeline_point(self, channel: str, time: float, wavelength: float, timestamp: float = None) -> None:
        """Append a data point to the timeline buffer.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            time: Elapsed time in seconds
            wavelength: Wavelength in nanometers
            timestamp: Absolute timestamp (seconds since epoch), optional
        """
        buffer = self.timeline_data[channel]

        # Check if new point is out of order (due to threading/async arrival)
        if len(buffer.time) > 0 and time < buffer.time[-1]:
            # Point arrived late - insert in sorted position to maintain monotonic time
            insert_idx = np.searchsorted(buffer.time, time)
            buffer.time = np.insert(buffer.time, insert_idx, time)
            buffer.wavelength = np.insert(buffer.wavelength, insert_idx, wavelength)
            if timestamp is not None and len(buffer.timestamp) > 0:
                buffer.timestamp = np.insert(buffer.timestamp, insert_idx, timestamp)
        else:
            # Normal case - append to end
            buffer.time = np.append(buffer.time, time)
            buffer.wavelength = np.append(buffer.wavelength, wavelength)
            if timestamp is not None:
                buffer.timestamp = np.append(buffer.timestamp, timestamp)

    def append_intensity_point(self, channel: str, timestamp: float, intensity: float) -> None:
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

    def get_intensity_average(self, channel: str) -> Optional[float]:
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

    def get_intensity_timespan(self, channel: str) -> Optional[float]:
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
        cycle_timestamp: np.ndarray = None
    ) -> None:
        """Update cycle data for a channel.

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
        stop_time: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
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
        for channel in ['a', 'b', 'c', 'd']:
            self.timeline_data[channel] = ChannelBuffer()
            self.cycle_data[channel] = ChannelBuffer()
            self.baseline_wavelengths[channel] = None
            self.intensity_buffers[channel] = IntensityBuffer()

    def get_latest_value(self, channel: str) -> Optional[float]:
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
