"""
Data Buffer Manager for SPR System

Consolidates all data storage arrays and provides clean interfaces for buffer operations.
Manages memory efficiently and provides unified data access patterns.
"""

from __future__ import annotations

import time
from typing import Any, Dict

import numpy as np

from settings import CH_LIST
from utils.logger import logger
from widgets.datawindow import DataDict


class DataBufferManager:
    """
    Centralized manager for all SPR data buffers and arrays.
    
    Consolidates scattered numpy arrays into a single, well-organized interface
    with proper memory management and buffer size limits.
    """
    
    def __init__(self, channels: list[str] | None = None) -> None:
        """
        Initialize data buffer manager.
        
        Args:
            channels: List of channel names (defaults to CH_LIST)
        """
        self.channels = channels or CH_LIST
        
        # Core sensorgram data buffers
        self.lambda_values: Dict[str, np.ndarray] = {ch: np.array([]) for ch in self.channels}
        self.lambda_times: Dict[str, np.ndarray] = {ch: np.array([]) for ch in self.channels}
        
        # Filtered data buffers
        self.filtered_lambda: Dict[str, np.ndarray] = {ch: np.array([]) for ch in self.channels}
        
        # Buffered data for processing
        self.buffered_lambda: Dict[str, np.ndarray] = {ch: np.array([]) for ch in self.channels}
        self.buffered_times: Dict[str, np.ndarray] = {ch: np.array([]) for ch in self.channels}
        
        # Spectroscopy data buffers
        self.int_data: Dict[str, np.ndarray] = {ch: np.array([]) for ch in self.channels}
        self.trans_data: Dict[str, np.ndarray | None] = {ch: None for ch in self.channels}
        
        # Buffer configuration
        self.max_buffer_size = 100000  # Maximum points per buffer
        self.buffer_trim_size = 80000  # Trim to this size when max reached
        
        # Filter buffer management
        self.filt_buffer_index = 0
        
        logger.debug(f"DataBufferManager initialized for channels: {self.channels}")
    
    def clear_all_buffers(self) -> None:
        """Clear all data buffers for all channels."""
        try:
            for ch in self.channels:
                self.lambda_values[ch] = np.array([])
                self.lambda_times[ch] = np.array([])
                self.filtered_lambda[ch] = np.array([])
                self.buffered_lambda[ch] = np.array([])
                self.buffered_times[ch] = np.array([])
                self.int_data[ch] = np.array([])
                self.trans_data[ch] = None
            
            self.filt_buffer_index = 0
            logger.debug("All data buffers cleared")
            
        except Exception as e:
            logger.exception(f"Error clearing buffers: {e}")
    
    def clear_channel_buffers(self, channel: str) -> None:
        """
        Clear all buffers for a specific channel.
        
        Args:
            channel: Channel name to clear
        """
        if channel not in self.channels:
            logger.warning(f"Invalid channel: {channel}")
            return
            
        try:
            self.lambda_values[channel] = np.array([])
            self.lambda_times[channel] = np.array([])
            self.filtered_lambda[channel] = np.array([])
            self.buffered_lambda[channel] = np.array([])
            self.buffered_times[channel] = np.array([])
            self.int_data[channel] = np.array([])
            self.trans_data[channel] = None
            
            logger.debug(f"Cleared buffers for channel {channel}")
            
        except Exception as e:
            logger.exception(f"Error clearing buffers for channel {channel}: {e}")
    
    def add_sensorgram_point(self, channel: str, value: float, timestamp: float) -> None:
        """
        Add a data point to sensorgram buffers.
        
        Args:
            channel: Channel name
            value: Lambda value
            timestamp: Time value
        """
        if channel not in self.channels:
            logger.warning(f"Invalid channel: {channel}")
            return
            
        try:
            # Add to main buffers
            self.lambda_values[channel] = np.append(self.lambda_values[channel], value)
            self.lambda_times[channel] = np.append(self.lambda_times[channel], timestamp)
            
            # Manage buffer size
            self._trim_buffers_if_needed(channel)
            
        except Exception as e:
            logger.exception(f"Error adding sensorgram point for {channel}: {e}")
    
    def add_filtered_point(self, channel: str, value: float) -> None:
        """
        Add a filtered data point.
        
        Args:
            channel: Channel name
            value: Filtered lambda value
        """
        if channel not in self.channels:
            logger.warning(f"Invalid channel: {channel}")
            return
            
        try:
            self.filtered_lambda[channel] = np.append(self.filtered_lambda[channel], value)
            
        except Exception as e:
            logger.exception(f"Error adding filtered point for {channel}: {e}")
    
    def add_buffered_point(self, channel: str, value: float, timestamp: float) -> None:
        """
        Add a point to buffered data arrays.
        
        Args:
            channel: Channel name
            value: Lambda value
            timestamp: Time value
        """
        if channel not in self.channels:
            logger.warning(f"Invalid channel: {channel}")
            return
            
        try:
            self.buffered_lambda[channel] = np.append(self.buffered_lambda[channel], value)
            self.buffered_times[channel] = np.append(self.buffered_times[channel], timestamp)
            
        except Exception as e:
            logger.exception(f"Error adding buffered point for {channel}: {e}")
    
    def set_intensity_data(self, channel: str, data: np.ndarray) -> None:
        """
        Set intensity data for a channel.
        
        Args:
            channel: Channel name
            data: Intensity data array
        """
        if channel not in self.channels:
            logger.warning(f"Invalid channel: {channel}")
            return
            
        try:
            self.int_data[channel] = data.copy() if data is not None else np.array([])
            
        except Exception as e:
            logger.exception(f"Error setting intensity data for {channel}: {e}")
    
    def set_transmittance_data(self, channel: str, data: np.ndarray | None) -> None:
        """
        Set transmittance data for a channel.
        
        Args:
            channel: Channel name
            data: Transmittance data array or None
        """
        if channel not in self.channels:
            logger.warning(f"Invalid channel: {channel}")
            return
            
        try:
            self.trans_data[channel] = data.copy() if data is not None else None
            
        except Exception as e:
            logger.exception(f"Error setting transmittance data for {channel}: {e}")
    
    def get_sensorgram_data(self, filtered: bool = False) -> Dict[str, Any]:
        """
        Get sensorgram data in standard format.
        
        Args:
            filtered: Whether to include filtered data
            
        Returns:
            Dictionary with sensorgram data
        """
        try:
            data = {
                "lambda_values": self.lambda_values.copy(),
                "lambda_times": self.lambda_times.copy(),
                "buffered_lambda_values": self.buffered_lambda.copy(),
                "buffered_lambda_times": self.buffered_times.copy(),
            }
            
            if filtered:
                data["filtered_lambda_values"] = self.filtered_lambda.copy()
                
            return data
            
        except Exception as e:
            logger.exception(f"Error getting sensorgram data: {e}")
            # Return empty data structure
            return {
                "lambda_values": {ch: np.array([]) for ch in self.channels},
                "lambda_times": {ch: np.array([]) for ch in self.channels},
                "buffered_lambda_values": {ch: np.array([]) for ch in self.channels},
                "buffered_lambda_times": {ch: np.array([]) for ch in self.channels},
            }
    
    def get_spectroscopy_data(self) -> Dict[str, Any]:
        """
        Get spectroscopy data.
        
        Returns:
            Dictionary with spectroscopy data
        """
        try:
            return {
                "int_data": self.int_data.copy(),
                "trans_data": self.trans_data.copy(),
            }
            
        except Exception as e:
            logger.exception(f"Error getting spectroscopy data: {e}")
            return {
                "int_data": {ch: np.array([]) for ch in self.channels},
                "trans_data": {ch: None for ch in self.channels},
            }
    
    def get_channel_data_count(self, channel: str) -> int:
        """
        Get number of data points for a channel.
        
        Args:
            channel: Channel name
            
        Returns:
            Number of data points
        """
        if channel not in self.channels:
            return 0
            
        try:
            return len(self.lambda_values[channel])
        except Exception:
            return 0
    
    def get_total_data_count(self) -> Dict[str, int]:
        """
        Get data point counts for all channels.
        
        Returns:
            Dictionary mapping channel names to data counts
        """
        return {ch: self.get_channel_data_count(ch) for ch in self.channels}
    
    def get_latest_value(self, channel: str) -> float | None:
        """
        Get the latest lambda value for a channel.
        
        Args:
            channel: Channel name
            
        Returns:
            Latest value or None if no data
        """
        if channel not in self.channels:
            return None
            
        try:
            if len(self.lambda_values[channel]) > 0:
                return float(self.lambda_values[channel][-1])
            return None
            
        except Exception as e:
            logger.exception(f"Error getting latest value for {channel}: {e}")
            return None
    
    def get_latest_timestamp(self, channel: str) -> float | None:
        """
        Get the latest timestamp for a channel.
        
        Args:
            channel: Channel name
            
        Returns:
            Latest timestamp or None if no data
        """
        if channel not in self.channels:
            return None
            
        try:
            if len(self.lambda_times[channel]) > 0:
                return float(self.lambda_times[channel][-1])
            return None
            
        except Exception as e:
            logger.exception(f"Error getting latest timestamp for {channel}: {e}")
            return None
    
    def pad_values(self) -> None:
        """Pad values to synchronize buffer lengths across channels."""
        try:
            # Find the maximum length across all channels
            max_len = max(len(self.lambda_values[ch]) for ch in self.channels)
            
            if max_len == 0:
                return  # No data to pad
            
            for ch in self.channels:
                current_len = len(self.lambda_values[ch])
                if current_len < max_len:
                    # Pad with the last value or zero
                    pad_count = max_len - current_len
                    
                    if current_len > 0:
                        # Pad with last value
                        last_value = self.lambda_values[ch][-1]
                        last_time = self.lambda_times[ch][-1]
                    else:
                        # No data yet, pad with zero
                        last_value = 0.0
                        last_time = time.time()
                    
                    # Add padding
                    pad_values = np.full(pad_count, last_value)
                    pad_times = np.linspace(last_time, last_time + pad_count * 0.1, pad_count)
                    
                    self.lambda_values[ch] = np.concatenate([self.lambda_values[ch], pad_values])
                    self.lambda_times[ch] = np.concatenate([self.lambda_times[ch], pad_times])
            
            logger.debug(f"Padded values to length {max_len}")
            
        except Exception as e:
            logger.exception(f"Error padding values: {e}")
    
    def shift_time_reference(self, time_diff: float) -> None:
        """
        Shift all time references by a given amount.
        
        Args:
            time_diff: Time difference to subtract from all timestamps
        """
        try:
            for ch in self.channels:
                if len(self.lambda_times[ch]) > 0:
                    self.lambda_times[ch] -= time_diff
                if len(self.buffered_times[ch]) > 0:
                    self.buffered_times[ch] -= time_diff
            
            logger.debug(f"Shifted time reference by {time_diff:.2f}s")
            
        except Exception as e:
            logger.exception(f"Error shifting time reference: {e}")
    
    def get_memory_usage(self) -> Dict[str, int]:
        """
        Get approximate memory usage for all buffers.
        
        Returns:
            Dictionary with memory usage in bytes
        """
        try:
            usage = {}
            total = 0
            
            for ch in self.channels:
                ch_usage = 0
                ch_usage += self.lambda_values[ch].nbytes
                ch_usage += self.lambda_times[ch].nbytes
                ch_usage += self.filtered_lambda[ch].nbytes
                ch_usage += self.buffered_lambda[ch].nbytes
                ch_usage += self.buffered_times[ch].nbytes
                ch_usage += self.int_data[ch].nbytes
                if self.trans_data[ch] is not None:
                    ch_usage += self.trans_data[ch].nbytes  # type: ignore
                
                usage[ch] = ch_usage
                total += ch_usage
            
            usage["total"] = total
            return usage
            
        except Exception as e:
            logger.exception(f"Error calculating memory usage: {e}")
            return {"total": 0}
    
    def _trim_buffers_if_needed(self, channel: str) -> None:
        """
        Trim buffers if they exceed maximum size.
        
        Args:
            channel: Channel to check and trim
        """
        try:
            if len(self.lambda_values[channel]) > self.max_buffer_size:
                # Trim to buffer_trim_size, keeping the most recent data
                trim_start = len(self.lambda_values[channel]) - self.buffer_trim_size
                
                self.lambda_values[channel] = self.lambda_values[channel][trim_start:]
                self.lambda_times[channel] = self.lambda_times[channel][trim_start:]
                
                # Also trim other buffers for this channel
                if len(self.filtered_lambda[channel]) > self.max_buffer_size:
                    self.filtered_lambda[channel] = self.filtered_lambda[channel][trim_start:]
                
                if len(self.buffered_lambda[channel]) > self.max_buffer_size:
                    trim_buffered = len(self.buffered_lambda[channel]) - self.buffer_trim_size
                    self.buffered_lambda[channel] = self.buffered_lambda[channel][trim_buffered:]
                    self.buffered_times[channel] = self.buffered_times[channel][trim_buffered:]
                
                logger.debug(f"Trimmed buffers for channel {channel} to {self.buffer_trim_size} points")
                
        except Exception as e:
            logger.exception(f"Error trimming buffers for {channel}: {e}")
    
    def get_buffer_info(self) -> Dict[str, Any]:
        """
        Get information about buffer states.
        
        Returns:
            Dictionary with buffer information
        """
        try:
            info = {
                "channels": self.channels,
                "max_buffer_size": self.max_buffer_size,
                "buffer_trim_size": self.buffer_trim_size,
                "data_counts": self.get_total_data_count(),
                "memory_usage": self.get_memory_usage(),
            }
            
            return info
            
        except Exception as e:
            logger.exception(f"Error getting buffer info: {e}")
            return {"error": str(e)}
