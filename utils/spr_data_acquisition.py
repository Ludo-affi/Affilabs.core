from __future__ import annotations

import time
import threading
from copy import deepcopy
from typing import Any, Callable, cast, Protocol
import numpy as np

from utils.logger import logger
from widgets.message import show_message
from settings import DEVICES, CH_LIST, EZ_CH_LIST
from widgets.datawindow import DataDict

# Constants
DERIVATIVE_WINDOW = 165  # Window size for derivative calculation


class SignalEmitter(Protocol):
    """Protocol for Qt signal emitters."""
    def emit(self, *args: Any) -> None: ...


class SPRDataAcquisition:
    """
    Manages SPR data acquisition, sensor reading, and real-time data processing.
    
    Handles the main data acquisition loop, spectrum reading, transmission calculation,
    wavelength fitting, and filtering operations with minimal UI coupling via callbacks.
    """
    
    def __init__(
        self,
        *,
        # Hardware references
        ctrl: Any | None,
        usb: Any | None,
        data_processor: Any | None,
        # Data storage references (managed by main app)
        lambda_values: dict[str, np.ndarray],
        lambda_times: dict[str, np.ndarray],
        filtered_lambda: dict[str, np.ndarray],
        buffered_lambda: dict[str, np.ndarray],
        buffered_times: dict[str, np.ndarray],
        int_data: dict[str, np.ndarray],
        trans_data: dict[str, np.ndarray | None],
        ref_sig: dict[str, np.ndarray | None],
        wave_data: np.ndarray,
        # Configuration
        device_config: dict[str, Any],
        wave_min_index: int,
        wave_max_index: int,
        num_scans: int,
        led_delay: float,
        med_filt_win: int,
        dark_noise: np.ndarray,
        # State management
        _b_kill: threading.Event,
        _b_stop: threading.Event,
        _b_no_read: threading.Event,
        # UI callbacks
        update_live_signal: SignalEmitter,
        update_spec_signal: SignalEmitter,
        temp_sig: SignalEmitter,
        raise_error: SignalEmitter,
        set_status_text: Callable[[str], None],
    ) -> None:
        # Hardware references
        self.ctrl = ctrl
        self.usb = usb
        self.data_processor = data_processor
        
        # Data storage (references to main app data)
        self.lambda_values = lambda_values
        self.lambda_times = lambda_times
        self.filtered_lambda = filtered_lambda
        self.buffered_lambda = buffered_lambda
        self.buffered_times = buffered_times
        self.int_data = int_data
        self.trans_data = trans_data
        self.ref_sig = ref_sig
        self.wave_data = wave_data
        
        # Configuration
        self.device_config = device_config
        self.wave_min_index = wave_min_index
        self.wave_max_index = wave_max_index
        self.num_scans = num_scans
        self.led_delay = led_delay
        self.med_filt_win = med_filt_win
        self.dark_noise = dark_noise
        
        # State management
        self._b_kill = _b_kill
        self._b_stop = _b_stop
        self._b_no_read = _b_no_read
        
        # UI callbacks
        self.update_live_signal = update_live_signal
        self.update_spec_signal = update_spec_signal
        self.temp_sig = temp_sig
        self.raise_error = raise_error
        self.set_status_text = set_status_text
        
        # Internal state
        self.exp_start: float = 0.0
        self.filt_buffer_index: int = 0
        self.single_mode: bool = False
        self.single_ch: str = "a"
        self.calibrated: bool = False
        self.filt_on: bool = True
        self.recording: bool = False

    def grab_data(self) -> None:
        """Main data acquisition loop."""
        first_run = True

        while not self._b_kill.is_set():
            ch = CH_LIST[0]
            time.sleep(0.01)
            try:
                if self._b_stop.is_set() or self.device_config["ctrl"] not in DEVICES:
                    time.sleep(0.2)
                    continue

                if first_run:
                    self.exp_start = time.time()
                    first_run = False

                if not self._check_buffer_lengths():
                    self.pad_values()

                ch_list = self._get_active_channels()
                
                for ch in CH_LIST:
                    fit_lambda = np.nan
                    if self._b_stop.is_set():
                        break
                        
                    if self._should_read_channel(ch, ch_list):
                        fit_lambda = self._read_channel_data(ch)
                    else:
                        time.sleep(0.1)

                    self._update_lambda_data(ch, fit_lambda)
                    self._apply_filtering(ch, ch_list, fit_lambda)

                    if ch == CH_LIST[-1]:
                        self.filt_buffer_index += 1

                if not self._b_stop.is_set():
                    self._emit_data_updates()
                    self._emit_temperature_update()

            except Exception as e:
                self._handle_acquisition_error(e, ch)

    def _check_buffer_lengths(self) -> bool:
        """Check if all buffer lengths are synchronized."""
        lengths = [len(self.buffered_times[ch]) for ch in ["a", "b", "c", "d"]]
        return len(set(lengths)) == 1

    def _get_active_channels(self) -> list[str]:
        """Get list of active channels based on current mode."""
        if self.single_mode:
            return [self.single_ch]
        elif self.device_config["ctrl"] in ["PicoEZSPR"]:  # EZSPR disabled (obsolete)
            return EZ_CH_LIST
        else:
            return CH_LIST

    def _should_read_channel(self, ch: str, ch_list: list[str]) -> bool:
        """Check if we should read data from this channel."""
        return (
            ch in ch_list
            and not self._b_no_read.is_set()
            and self.calibrated
            and self.ctrl is not None
        )

    def _read_channel_data(self, ch: str) -> float:
        """Read and process data from a specific channel."""
        try:
            int_data_sum: np.ndarray | None = None
            self.ctrl.turn_on_channel(ch=ch)
            
            if self.led_delay > 0:
                time.sleep(self.led_delay)
                
            # Multiple scans for averaging
            for _scan in range(self.num_scans):
                if self._b_stop.is_set():
                    break
                    
                reading = self.usb.read_intensity()
                if reading is None:
                    self.raise_error.emit("spec")
                    self._b_stop.set()
                    break
                    
                int_data_single = reading[self.wave_min_index:self.wave_max_index]
                if int_data_sum is None:
                    int_data_sum = int_data_single
                else:
                    int_data_sum = np.add(int_data_sum, int_data_single)

            if int_data_sum is not None:
                # Average scans and subtract dark noise
                averaged_intensity = int_data_sum / self.num_scans
                self.int_data[ch] = averaged_intensity - self.dark_noise
                
                # Calculate transmission
                if self.ref_sig[ch] is not None and self.data_processor is not None:
                    try:
                        self.trans_data[ch] = self.data_processor.calculate_transmission(
                            p_pol_intensity=averaged_intensity,
                            s_ref_intensity=self.ref_sig[ch],
                            dark_noise=self.dark_noise,
                        )
                    except Exception as e:
                        logger.exception(f"Failed to get trans data: {e}")
                        
            # Turn off channels after reading
            if self.device_config["ctrl"] in DEVICES:
                self.ctrl.turn_off_channels()

            # Find resonance wavelength
            if not (self._b_stop.is_set() or self.trans_data[ch] is None):
                if self.data_processor is not None:
                    spectrum = self.trans_data[ch]
                    return self.data_processor.find_resonance_wavelength(
                        spectrum=spectrum,
                        window=DERIVATIVE_WINDOW,  # 165
                    )
                    
        except Exception as e:
            logger.exception(f"Error reading channel {ch}: {e}")
            
        return np.nan

    def _update_lambda_data(self, ch: str, fit_lambda: float) -> None:
        """Update lambda values and times for a channel."""
        self.lambda_values[ch] = np.append(self.lambda_values[ch], fit_lambda)
        self.lambda_times[ch] = np.append(
            self.lambda_times[ch],
            round(time.time() - self.exp_start, 3),
        )

    def _apply_filtering(self, ch: str, ch_list: list[str], fit_lambda: float) -> None:
        """Apply filtering to lambda data."""
        if ch in ch_list:
            # Use data processor for median filtering
            if len(self.lambda_values[ch]) > self.filt_buffer_index:
                if self.data_processor is not None:
                    filtered_value = self.data_processor.apply_causal_median_filter(
                        data=self.lambda_values[ch],
                        buffer_index=self.filt_buffer_index,
                        window=self.med_filt_win,
                    )
                else:
                    # Fallback if processor not initialized
                    filtered_value = fit_lambda
            else:
                filtered_value = fit_lambda

            self.filtered_lambda[ch] = np.append(self.filtered_lambda[ch], filtered_value)
            self.buffered_lambda[ch] = np.append(
                self.buffered_lambda[ch],
                self.lambda_values[ch][self.filt_buffer_index],
            )
        else:
            self.filtered_lambda[ch] = np.append(self.filtered_lambda[ch], np.nan)
            self.buffered_lambda[ch] = np.append(self.buffered_lambda[ch], np.nan)

        self.buffered_times[ch] = np.append(
            self.buffered_times[ch],
            self.lambda_times[ch][self.filt_buffer_index],
        )

    def _emit_data_updates(self) -> None:
        """Emit data updates to UI."""
        self.update_live_signal.emit(self.sensorgram_data())
        self.update_spec_signal.emit(self.spectroscopy_data())

    def _emit_temperature_update(self) -> None:
        """Emit temperature update if applicable."""
        if (self.device_config["ctrl"] == "PicoP4SPR" 
            and self.ctrl is not None
            and hasattr(self.ctrl, 'get_temp')):
            try:
                self.temp_sig.emit(self.ctrl.get_temp())
            except Exception as e:
                logger.debug(f"Error getting temperature: {e}")

    def _handle_acquisition_error(self, error: Exception, ch: str) -> None:
        """Handle errors during data acquisition."""
        logger.exception(f"Error while grabbing data:{type(error)}:{error}:channel {ch}")
        self.pad_values()
        self._b_stop.set()
        self.set_status_text("Error while reading SPR data")
        
        if error is IndexError:
            show_message(
                msg_type="Warning",
                msg="Data Error: the program has encountered an error, "
                "stopped data acquisition",
            )
        else:
            self.raise_error.emit("ctrl")

    def pad_values(self) -> None:
        """Pad values to synchronize buffer lengths."""
        try:
            max_raw_len = 0
            max_filt_len = 0
            for ch in CH_LIST:
                if len(self.lambda_times[ch]) > max_raw_len:
                    max_raw_len = len(self.lambda_times[ch])
                if len(self.buffered_times[ch]) > max_filt_len:
                    max_filt_len = len(self.buffered_times[ch])
                    
            for ch in CH_LIST:
                if len(self.lambda_times[ch]) < max_raw_len:
                    self.lambda_values[ch] = np.append(self.lambda_values[ch], np.nan)
                    self.lambda_times[ch] = np.append(
                        self.lambda_times[ch],
                        round(time.time() - self.exp_start, 3),
                    )
                if len(self.buffered_times[ch]) < max_filt_len:
                    self.filtered_lambda[ch] = np.append(self.filtered_lambda[ch], np.nan)
                    self.buffered_lambda[ch] = np.append(self.buffered_lambda[ch], np.nan)
                    self.buffered_times[ch] = np.append(self.buffered_times[ch], np.nan)
                    
            self.filt_buffer_index += 1
        except Exception as e:
            logger.exception(f"Error while padding missing values: {e}")

    def update_filtered_lambda(self) -> None:
        """Recompute filtered data with new filter window size."""
        try:
            new_filtered_lambda = {ch: np.array([]) for ch in CH_LIST}
            for ch in CH_LIST:
                if (
                    len(self.lambda_values[ch]) > 0
                    and len(self.lambda_times[ch]) > 0
                    and len(self.buffered_times[ch]) > 0
                ):
                    first_filt_index = self.med_filt_win
                    last_filt_index = len(self.lambda_values[ch]) - 1
                    
                    # Filter beginning values
                    for i in range(first_filt_index):
                        filt_val = np.nanmean(self.lambda_values[ch][0:i])
                        new_filtered_lambda[ch] = np.append(new_filtered_lambda[ch], filt_val)
                        
                    # Filter middle values with full window
                    for i in range(first_filt_index, last_filt_index):
                        filt_val = np.nanmean(
                            self.lambda_values[ch][(i - self.med_filt_win):i]
                        )
                        new_filtered_lambda[ch] = np.append(new_filtered_lambda[ch], filt_val)
                        
                    # Filter end values
                    for i in range(last_filt_index, len(self.lambda_values[ch])):
                        filt_val = np.nanmean(
                            self.lambda_values[ch][(i - self.med_filt_win):i]
                        )
                        new_filtered_lambda[ch] = np.append(new_filtered_lambda[ch], filt_val)
                        
                    # Align with buffered times
                    offset = 0
                    while self.lambda_times[ch][offset] != self.buffered_times[ch][0]:
                        offset += 1
                    self.filtered_lambda[ch] = deepcopy(new_filtered_lambda[ch][offset:])
                    
        except Exception as e:
            logger.exception(f"error updating the filter win size: {e}")
            show_message("Filter window could not be updated", msg_type="Warning")

    def sensorgram_data(self) -> DataDict:
        """Return sensorgram data for UI updates."""
        sens_data = {
            "lambda_values": self.lambda_values,
            "lambda_times": self.lambda_times,
            "buffered_lambda_values": self.buffered_lambda,
            "filtered_lambda_values": self.filtered_lambda,
            "buffered_lambda_times": self.buffered_times,
            "filt": self.filt_on,
            "start": self.exp_start,
            "rec": self.recording,
        }
        return cast(DataDict, deepcopy(sens_data))

    def spectroscopy_data(self) -> dict[str, object]:
        """Return spectroscopy data for UI updates."""
        return {
            "wave_data": self.wave_data,
            "int_data": self.int_data,
            "trans_data": self.trans_data,
        }

    def set_configuration(
        self,
        *,
        single_mode: bool = False,
        single_ch: str = "a",
        calibrated: bool = False,
        filt_on: bool = True,
        recording: bool = False,
        med_filt_win: int | None = None,
    ) -> None:
        """Update acquisition configuration."""
        self.single_mode = single_mode
        self.single_ch = single_ch
        self.calibrated = calibrated
        self.filt_on = filt_on
        self.recording = recording
        if med_filt_win is not None:
            self.med_filt_win = med_filt_win