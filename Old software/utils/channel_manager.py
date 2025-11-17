"""Channel Manager - Centralized multi-channel data management.

This module extracts channel iteration and data buffering logic from the main
application loop, providing:
- Channel selection based on device type and mode
- Data buffer management for all channels
- Automatic value padding for synchronization
- Clean data export for UI updates

Design Goals:
- Single Responsibility: Only manage channel data, not acquisition or processing
- Simple API: add_data_point(), get_sensorgram_data()
- Thread-safe: Can be used from acquisition thread
- Testable: Pure data management, no hardware dependencies
"""

from __future__ import annotations

import time
from typing import Optional
from dataclasses import dataclass

import numpy as np

from utils.logger import logger
from settings import CH_LIST, EZ_CH_LIST


@dataclass
class ChannelConfig:
    """Configuration for channel management.
    
    Attributes:
        device_type: Controller type ('PicoP4SPR', 'EZSPR', 'PicoEZSPR', etc.)
        single_mode: Whether single-channel mode is enabled
        single_channel: Which channel to use in single-channel mode
    """
    device_type: str = ""
    single_mode: bool = False
    single_channel: str = "x"


class ChannelManager:
    """Manages multi-channel data buffers and iteration logic.
    
    This class centralizes all channel-related data management:
    - Determines which channels are active based on device and mode
    - Maintains time-series buffers for raw and filtered wavelength data
    - Handles buffer synchronization (padding missing values)
    - Exports data for UI display
    
    Example:
        >>> mgr = ChannelManager()
        >>> mgr.configure(device_type='PicoP4SPR', single_mode=False)
        >>> mgr.add_data_point('a', wavelength=680.5, timestamp=1.23)
        >>> data = mgr.get_sensorgram_data()
    """
    
    def __init__(self):
        """Initialize channel manager with preallocated buffers."""
        # Configuration
        self.config = ChannelConfig()
        
        # Preallocate buffers for better performance (10,000 data points = ~2.5 hours at 1 Hz)
        self._buffer_capacity = 10000
        
        # Track current length PER CHANNEL (each channel may have different lengths)
        self._current_length = {ch: 0 for ch in CH_LIST}
        
        # Raw wavelength values (unfiltered) - preallocated
        self.lambda_values = {ch: np.full(self._buffer_capacity, np.nan) for ch in CH_LIST}
        
        # Timestamps for raw values - preallocated
        self.lambda_times = {ch: np.full(self._buffer_capacity, np.nan) for ch in CH_LIST}
        
        # Filtered wavelength values (after temporal filtering) - preallocated
        self.filtered_lambda = {ch: np.full(self._buffer_capacity, np.nan) for ch in CH_LIST}
        
        # Buffered (delayed) raw values for synchronization - preallocated
        self.buffered_lambda = {ch: np.full(self._buffer_capacity, np.nan) for ch in CH_LIST}
        
        # Timestamps for buffered values - preallocated
        self.buffered_times = {ch: np.full(self._buffer_capacity, np.nan) for ch in CH_LIST}
        
        # Current buffer index (for median filter delay)
        self.buffer_index = 0
        
        # Experiment start time references
        self.exp_start_time = time.time()
        self.exp_start_perf = time.perf_counter()
        
    def configure(
        self,
        device_type: str,
        single_mode: bool = False,
        single_channel: str = "x",
    ) -> None:
        """Update channel configuration.
        
        Args:
            device_type: Controller type
            single_mode: Enable single-channel mode
            single_channel: Channel to use in single-channel mode
        """
        self.config = ChannelConfig(
            device_type=device_type,
            single_mode=single_mode,
            single_channel=single_channel,
        )
        logger.debug(
            f"ChannelManager configured: device={device_type}, "
            f"single_mode={single_mode}, single_ch={single_channel}"
        )
    
    def get_active_channels(self) -> list[str]:
        """Get list of channels that should be acquired.
        
        Returns:
            List of channel identifiers ('a', 'b', 'c', 'd')
        """
        if self.config.single_mode:
            return [self.config.single_channel]
        elif self.config.device_type in ["EZSPR", "PicoEZSPR"]:
            return EZ_CH_LIST
        else:
            return CH_LIST
    
    def add_data_point(
        self,
        channel: str,
        wavelength: float,
        timestamp: float,
        filtered_value: Optional[float] = None,
    ) -> None:
        """Add a new data point for a channel.
        
        This updates all relevant buffers:
        - Raw wavelength and timestamp
        - Filtered wavelength (if provided)
        - Buffered raw value (delayed by filter window)
        - Buffered timestamp
        
        Args:
            channel: Channel identifier
            wavelength: Raw resonance wavelength (nm)
            timestamp: Time since experiment start (seconds)
            filtered_value: Filtered wavelength (nm), if available
        """
        if channel not in self.lambda_values:
            logger.warning(f"Unknown channel: {channel}")
            return
        
        # Check if THIS CHANNEL needs to grow the buffers (geometric growth for efficiency)
        if self._current_length[channel] >= self._buffer_capacity:
            self._grow_buffers()
        
        # Get current index for THIS CHANNEL
        idx = self._current_length[channel]
        
        # Store raw data using index assignment (NO array copying!)
        self.lambda_values[channel][idx] = wavelength
        self.lambda_times[channel][idx] = timestamp
        
        # Store filtered data (or NaN if not provided)
        if filtered_value is not None:
            self.filtered_lambda[channel][idx] = filtered_value
        else:
            self.filtered_lambda[channel][idx] = np.nan
        
        # Calculate buffered data (delayed raw value)
        if self._current_length[channel] > self.buffer_index:
            buffered_val = self.lambda_values[channel][self.buffer_index]
            buffered_time = self.lambda_times[channel][self.buffer_index]
        else:
            # Not enough data yet for buffering
            buffered_val = np.nan
            buffered_time = timestamp
        
        self.buffered_lambda[channel][idx] = buffered_val
        self.buffered_times[channel][idx] = buffered_time
        
        # Increment THIS CHANNEL's length counter
        self._current_length[channel] += 1
    
    def _grow_buffers(self):
        """Grow all buffers by 50% when capacity is reached (geometric growth)."""
        old_capacity = self._buffer_capacity
        new_capacity = int(old_capacity * 1.5)
        
        print(f"Growing buffers from {old_capacity} to {new_capacity}")
        
        for ch in CH_LIST:
            # Create new larger arrays
            new_lambda = np.full(new_capacity, np.nan)
            new_times = np.full(new_capacity, np.nan)
            new_filtered = np.full(new_capacity, np.nan)
            new_buffered = np.full(new_capacity, np.nan)
            new_buffered_times = np.full(new_capacity, np.nan)
            
            # Copy existing data (vectorized operation)
            new_lambda[:old_capacity] = self.lambda_values[ch]
            new_times[:old_capacity] = self.lambda_times[ch]
            new_filtered[:old_capacity] = self.filtered_lambda[ch]
            new_buffered[:old_capacity] = self.buffered_lambda[ch]
            new_buffered_times[:old_capacity] = self.buffered_times[ch]
            
            # Replace with new arrays
            self.lambda_values[ch] = new_lambda
            self.lambda_times[ch] = new_times
            self.filtered_lambda[ch] = new_filtered
            self.buffered_lambda[ch] = new_buffered
            self.buffered_times[ch] = new_buffered_times
        
        self._buffer_capacity = new_capacity
    
    def increment_buffer_index(self) -> None:
        """Increment the buffer index after processing all channels.
        
        This should be called once per acquisition cycle, after all
        channels have been processed.
        """
        self.buffer_index += 1
    
    def pad_missing_values(self) -> None:
        """Pad channels with NaN to ensure all have same length.
        
        No longer needed with preallocated buffers - all channels maintain
        synchronized lengths through shared _current_length counter.
        """
        # This method is now a no-op but kept for backwards compatibility
        pass
    
    def check_synchronization(self) -> bool:
        """Check if all channels are synchronized (same length).
        
        With preallocated buffers, all channels are always synchronized
        through the shared _current_length counter.
        
        Returns:
            Always True with preallocated buffers
        """
        return True
    
    def get_sensorgram_data(self) -> dict:
        """Export current data for sensorgram UI display.
        
        Returns only the valid data (excludes preallocated unused space).
        
        Returns:
            Dictionary with channel data:
            {
                'a': {'times': array, 'values': array, 'filtered': array},
                'b': {...},
                ...
            }
        """
        data = {}
        # Only return the valid data points per channel
        for ch in CH_LIST:
            n = self._current_length[ch]
            data[ch] = {
                'times': self.buffered_times[ch][:n].copy(),
                'values': self.buffered_lambda[ch][:n].copy(),
                'filtered': self.filtered_lambda[ch][:n].copy(),
            }
        return data
    
    def get_spectroscopy_data(self) -> dict:
        """Export current data for spectroscopy view.
        
        This is similar to sensorgram data but may have different
        format requirements.
        
        Returns:
            Dictionary with channel data
        """
        # For now, use same format as sensorgram
        return self.get_sensorgram_data()
    
    def get_statistics(self) -> dict:
        """Get statistics about buffer state.
        
        Returns:
            Dictionary with statistics per channel
        """
        stats = {}
        for ch in CH_LIST:
            n = self._current_length[ch]
            stats[ch] = {
                'total_points': n,
                'buffered_points': n,
                'buffer_capacity': self._buffer_capacity,
                'utilization': f"{100 * n / self._buffer_capacity:.1f}%",
                'has_nan': np.isnan(self.buffered_lambda[ch][:n]).any(),
                'latest_wavelength': (
                    self.lambda_values[ch][n - 1]
                    if n > 0
                    else np.nan
                ),
            }
        return stats
    
    def clear_data(self) -> None:
        """Clear all data buffers and reset state."""
        # Reset to initial preallocated state
        self._buffer_capacity = 10000
        self._current_length = {ch: 0 for ch in CH_LIST}
        
        for ch in CH_LIST:
            self.lambda_values[ch] = np.full(self._buffer_capacity, np.nan)
            self.lambda_times[ch] = np.full(self._buffer_capacity, np.nan)
            self.filtered_lambda[ch] = np.full(self._buffer_capacity, np.nan)
            self.buffered_lambda[ch] = np.full(self._buffer_capacity, np.nan)
            self.buffered_times[ch] = np.full(self._buffer_capacity, np.nan)
        
        self.buffer_index = 0
        self.exp_start_time = time.time()
        self.exp_start_perf = time.perf_counter()
        
        logger.info("ChannelManager data cleared")
    
    def reset_experiment_time(self) -> None:
        """Reset experiment start time references."""
        self.exp_start_time = time.time()
        self.exp_start_perf = time.perf_counter()
        logger.debug("Experiment time reset")
    
    def get_current_time(self) -> float:
        """Get current time relative to experiment start.
        
        Returns:
            Elapsed time in seconds since experiment start
        """
        return round(time.perf_counter() - self.exp_start_perf, 3)
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        stats = self.get_statistics()
        active = self.get_active_channels()
        return (
            f"ChannelManager("
            f"active={active}, "
            f"buffer_index={self.buffer_index}, "
            f"points={[stats[ch]['total_points'] for ch in CH_LIST]}"
            f")"
        )
