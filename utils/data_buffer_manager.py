"""Data Buffer Manager for SPR System

Consolidates all data storage arrays and provides clean interfaces for buffer operations.
Manages memory efficiently and provides unified data access patterns.

Now uses pandas-backed TimeSeriesBuffer for 10-100× performance improvement over
repeated np.append() operations.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from numpy import ndarray

from settings import CH_LIST
from utils.logger import logger
from utils.time_series_buffer import TimeSeriesBuffer


class DataBufferManager:
    """Centralized manager for all SPR data buffers and arrays.

    Consolidates scattered numpy arrays into a single, well-organized interface
    with proper memory management and buffer size limits.
    """

    def __init__(self, channels: list[str] | None = None) -> None:
        """Initialize data buffer manager.

        Args:
            channels: List of channel names (defaults to CH_LIST)

        """
        self.channels = channels or CH_LIST

        # Core sensorgram data buffers - now using pandas-backed TimeSeriesBuffer
        # Maintains NumPy array interface via properties for backwards compatibility
        self._time_series_buffers: dict[str, TimeSeriesBuffer] = {
            ch: TimeSeriesBuffer(channel=ch, batch_size=100) for ch in self.channels
        }

        # Backwards-compatible properties (delegate to TimeSeriesBuffer)
        # These return NumPy arrays to maintain existing API
        self.lambda_values: dict[str, np.ndarray] = {
            ch: self._time_series_buffers[ch].lambda_values for ch in self.channels
        }
        self.lambda_times: dict[str, np.ndarray] = {
            ch: self._time_series_buffers[ch].lambda_times for ch in self.channels
        }
        self.filtered_lambda: dict[str, np.ndarray] = {
            ch: self._time_series_buffers[ch].filtered_lambda for ch in self.channels
        }
        self.buffered_lambda: dict[str, np.ndarray] = {
            ch: self._time_series_buffers[ch].buffered_lambda for ch in self.channels
        }
        self.buffered_times: dict[str, np.ndarray] = {
            ch: self._time_series_buffers[ch].buffered_times for ch in self.channels
        }

        # Spectroscopy data buffers (keep as numpy for now)
        self.int_data: dict[str, np.ndarray] = {
            ch: np.array([]) for ch in self.channels
        }
        self.trans_data: dict[str, np.Optional[ndarray]] = dict.fromkeys(self.channels)

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
                # Clear TimeSeriesBuffer instances
                self._time_series_buffers[ch].clear()

                # Clear spectroscopy buffers
                self.int_data[ch] = np.array([])
                self.trans_data[ch] = None

                # Update property references
                self._update_property_references(ch)

            self.filt_buffer_index = 0
            logger.debug("All data buffers cleared")

        except Exception as e:
            logger.exception(f"Error clearing buffers: {e}")

    def clear_channel_buffers(self, channel: str) -> None:
        """Clear all buffers for a specific channel.

        Args:
            channel: Channel name to clear

        """
        if channel not in self.channels:
            logger.warning(f"Invalid channel: {channel}")
            return

        try:
            # Clear TimeSeriesBuffer
            self._time_series_buffers[channel].clear()

            # Clear spectroscopy buffers
            self.int_data[channel] = np.array([])
            self.trans_data[channel] = None

            # Update property references
            self._update_property_references(channel)

            logger.debug(f"Cleared buffers for channel {channel}")

        except Exception as e:
            logger.exception(f"Error clearing buffers for channel {channel}: {e}")

    def add_sensorgram_point(
        self,
        channel: str,
        value: float,
        timestamp: float,
    ) -> None:
        """Add a data point to sensorgram buffers.

        Args:
            channel: Channel name
            value: Lambda value
            timestamp: Time value

        """
        if channel not in self.channels:
            logger.warning(f"Invalid channel: {channel}")
            return

        try:
            # Add to TimeSeriesBuffer (batched operation for performance)
            self._time_series_buffers[channel].append(
                timestamp=timestamp,
                lambda_val=value,
            )

            # Update property references to point to new array views
            self._update_property_references(channel)

            # Manage buffer size
            self._trim_buffers_if_needed(channel)

        except Exception as e:
            logger.exception(f"Error adding sensorgram point for {channel}: {e}")

    def add_filtered_point(self, channel: str, value: float) -> None:
        """Add a filtered data point.

        Args:
            channel: Channel name
            value: Filtered lambda value

        """
        if channel not in self.channels:
            logger.warning(f"Invalid channel: {channel}")
            return

        try:
            # Add to TimeSeriesBuffer (batched operation)
            # Use last timestamp or current time
            buffer = self._time_series_buffers[channel]
            last_time = buffer.lambda_times[-1] if len(buffer) > 0 else 0.0

            buffer.append(
                timestamp=last_time,
                lambda_val=buffer.lambda_values[-1] if len(buffer) > 0 else value,
                filtered=value,
            )

            # Update property reference
            self._update_property_references(channel)

        except Exception as e:
            logger.exception(f"Error adding filtered point for {channel}: {e}")

    def add_buffered_point(self, channel: str, value: float, timestamp: float) -> None:
        """Add a point to buffered data arrays.

        Args:
            channel: Channel name
            value: Lambda value
            timestamp: Time value

        """
        if channel not in self.channels:
            logger.warning(f"Invalid channel: {channel}")
            return

        try:
            # Add to TimeSeriesBuffer (batched operation)
            buffer = self._time_series_buffers[channel]

            buffer.append(
                timestamp=buffer.lambda_times[-1] if len(buffer) > 0 else timestamp,
                lambda_val=buffer.lambda_values[-1] if len(buffer) > 0 else value,
                buffered=value,
                buffered_time=timestamp,
            )

            # Update property references
            self._update_property_references(channel)

        except Exception as e:
            logger.exception(f"Error adding buffered point for {channel}: {e}")

    def set_intensity_data(self, channel: str, data: np.ndarray) -> None:
        """Set intensity data for a channel.

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

    def set_transmittance_data(self, channel: str, data: np.Optional[ndarray]) -> None:
        """Set transmittance data for a channel.

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

    def get_sensorgram_data(self, filtered: bool = False) -> dict[str, Any]:
        """Get sensorgram data in standard format.

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

    def get_spectroscopy_data(self) -> dict[str, Any]:
        """Get spectroscopy data.

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
                "trans_data": dict.fromkeys(self.channels),
            }

    def get_channel_data_count(self, channel: str) -> int:
        """Get number of data points for a channel.

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

    def get_total_data_count(self) -> dict[str, int]:
        """Get data point counts for all channels.

        Returns:
            Dictionary mapping channel names to data counts

        """
        return {ch: self.get_channel_data_count(ch) for ch in self.channels}

    def get_latest_value(self, channel: str) -> float | None:
        """Get the latest lambda value for a channel.

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
        """Get the latest timestamp for a channel.

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
            max_len = max(len(self._time_series_buffers[ch]) for ch in self.channels)

            if max_len == 0:
                return  # No data to pad

            for ch in self.channels:
                buffer = self._time_series_buffers[ch]
                current_len = len(buffer)

                if current_len < max_len:
                    # Pad with the last value or zero
                    pad_count = max_len - current_len

                    if current_len > 0:
                        # Pad with last value
                        last_value = buffer.lambda_values[-1]
                        last_time = buffer.lambda_times[-1]
                    else:
                        # No data yet, pad with zero
                        last_value = 0.0
                        last_time = time.time()

                    # Add padding points
                    for i in range(pad_count):
                        buffer.append(
                            lambda_value=last_value,
                            lambda_time=last_time + i * 0.1,
                        )

                    # Update property references
                    self._update_property_references(ch)

            logger.debug(f"Padded values to length {max_len}")

        except Exception as e:
            logger.exception(f"Error padding values: {e}")

    def shift_time_reference(self, time_diff: float) -> None:
        """Shift all time references by a given amount.

        Args:
            time_diff: Time difference to subtract from all timestamps

        """
        try:
            for ch in self.channels:
                buffer = self._time_series_buffers[ch]
                buffer.shift_time_reference(time_diff)

                # Update property references
                self._update_property_references(ch)

            logger.debug(f"Shifted time reference by {time_diff:.2f}s")

        except Exception as e:
            logger.exception(f"Error shifting time reference: {e}")

    def get_memory_usage(self) -> dict[str, int]:
        """Get approximate memory usage for all buffers.

        Returns:
            Dictionary with memory usage in bytes

        """
        try:
            usage = {}
            total = 0

            for ch in self.channels:
                ch_usage = 0

                # TimeSeriesBuffer memory
                buffer = self._time_series_buffers[ch]
                ch_usage += buffer.get_memory_usage()

                # Spectroscopy data
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
        """Trim buffers if they exceed maximum size.

        Args:
            channel: Channel to check and trim

        """
        try:
            buffer = self._time_series_buffers[channel]
            current_size = len(buffer)

            if current_size > self.max_buffer_size:
                # Trim to buffer_trim_size, keeping the most recent data
                trim_start = current_size - self.buffer_trim_size
                buffer.trim(trim_start)

                # Update property references
                self._update_property_references(channel)

                logger.debug(
                    f"Trimmed buffers for channel {channel} to {self.buffer_trim_size} points",
                )

        except Exception as e:
            logger.exception(f"Error trimming buffers for {channel}: {e}")

    def get_buffer_info(self) -> dict[str, Any]:
        """Get information about buffer states.

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

    def _update_property_references(self, channel: str) -> None:
        """Update property dict references after TimeSeriesBuffer changes.

        Since property dicts point to NumPy arrays, we need to update references
        after buffer operations to maintain backwards compatibility.

        Args:
            channel: Channel to update

        """
        self.lambda_values[channel] = self._time_series_buffers[channel].lambda_values
        self.lambda_times[channel] = self._time_series_buffers[channel].lambda_times
        self.filtered_lambda[channel] = self._time_series_buffers[
            channel
        ].filtered_lambda
        self.buffered_lambda[channel] = self._time_series_buffers[
            channel
        ].buffered_lambda
        self.buffered_times[channel] = self._time_series_buffers[channel].buffered_times
