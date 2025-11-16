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
        """Initialize channel manager with empty buffers."""
        # Configuration
        self.config = ChannelConfig()
        
        # Raw wavelength values (unfiltered)
        self.lambda_values = {ch: np.array([]) for ch in CH_LIST}
        
        # Timestamps for raw values
        self.lambda_times = {ch: np.array([]) for ch in CH_LIST}
        
        # Filtered wavelength values (after temporal filtering)
        self.filtered_lambda = {ch: np.array([]) for ch in CH_LIST}
        
        # Buffered (delayed) raw values for synchronization
        self.buffered_lambda = {ch: np.array([]) for ch in CH_LIST}
        
        # Timestamps for buffered values
        self.buffered_times = {ch: np.array([]) for ch in CH_LIST}
        
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
        
        # Add raw data
        self.lambda_values[channel] = np.append(
            self.lambda_values[channel],
            wavelength,
        )
        self.lambda_times[channel] = np.append(
            self.lambda_times[channel],
            timestamp,
        )
        
        # Add filtered data (or NaN if not provided)
        if filtered_value is not None:
            self.filtered_lambda[channel] = np.append(
                self.filtered_lambda[channel],
                filtered_value,
            )
        else:
            self.filtered_lambda[channel] = np.append(
                self.filtered_lambda[channel],
                np.nan,
            )
        
        # Add buffered data (delayed raw value)
        if len(self.lambda_values[channel]) > self.buffer_index:
            buffered_val = self.lambda_values[channel][self.buffer_index]
            buffered_time = self.lambda_times[channel][self.buffer_index]
        else:
            # Not enough data yet for buffering
            buffered_val = np.nan
            buffered_time = timestamp
            
        self.buffered_lambda[channel] = np.append(
            self.buffered_lambda[channel],
            buffered_val,
        )
        self.buffered_times[channel] = np.append(
            self.buffered_times[channel],
            buffered_time,
        )
    
    def increment_buffer_index(self) -> None:
        """Increment the buffer index after processing all channels.
        
        This should be called once per acquisition cycle, after all
        channels have been processed.
        """
        self.buffer_index += 1
    
    def pad_missing_values(self) -> None:
        """Pad channels with NaN to ensure all have same length.
        
        This ensures all channels have the same number of buffered points,
        which is required for proper UI display and synchronization.
        """
        # Find the maximum length
        max_len = max(len(self.buffered_times[ch]) for ch in CH_LIST)
        
        # Pad each channel to max length
        for ch in CH_LIST:
            current_len = len(self.buffered_times[ch])
            if current_len < max_len:
                padding_size = max_len - current_len
                
                self.buffered_lambda[ch] = np.append(
                    self.buffered_lambda[ch],
                    np.full(padding_size, np.nan),
                )
                self.buffered_times[ch] = np.append(
                    self.buffered_times[ch],
                    np.full(padding_size, np.nan),
                )
                self.filtered_lambda[ch] = np.append(
                    self.filtered_lambda[ch],
                    np.full(padding_size, np.nan),
                )
                
                logger.debug(f"Padded channel {ch} with {padding_size} NaN values")
    
    def check_synchronization(self) -> bool:
        """Check if all channels are synchronized (same length).
        
        Returns:
            True if all channels have same number of buffered points
        """
        lengths = [len(self.buffered_times[ch]) for ch in CH_LIST]
        return len(set(lengths)) == 1
    
    def get_sensorgram_data(self) -> dict:
        """Export current data for sensorgram UI display.
        
        Returns:
            Dictionary with channel data:
            {
                'a': {'times': array, 'values': array, 'filtered': array},
                'b': {...},
                ...
            }
        """
        data = {}
        for ch in CH_LIST:
            data[ch] = {
                'times': self.buffered_times[ch].copy(),
                'values': self.buffered_lambda[ch].copy(),
                'filtered': self.filtered_lambda[ch].copy(),
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
            stats[ch] = {
                'total_points': len(self.lambda_values[ch]),
                'buffered_points': len(self.buffered_lambda[ch]),
                'has_nan': np.isnan(self.buffered_lambda[ch]).any(),
                'latest_wavelength': (
                    self.lambda_values[ch][-1]
                    if len(self.lambda_values[ch]) > 0
                    else np.nan
                ),
            }
        return stats
    
    def clear_data(self) -> None:
        """Clear all data buffers and reset state."""
        for ch in CH_LIST:
            self.lambda_values[ch] = np.array([])
            self.lambda_times[ch] = np.array([])
            self.filtered_lambda[ch] = np.array([])
            self.buffered_lambda[ch] = np.array([])
            self.buffered_times[ch] = np.array([])
        
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
