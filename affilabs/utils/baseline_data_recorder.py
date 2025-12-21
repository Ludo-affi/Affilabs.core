"""Baseline Data Recorder - Records transmission spectra for noise optimization analysis.

This module records raw transmission spectra during stable baseline acquisition
for offline analysis of signal processing parameters (SG filter, Fourier alpha, etc.)
"""

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, QTimer, Signal

from affilabs.utils.logger import logger


class BaselineDataRecorder(QObject):
    """Records transmission spectra for baseline noise optimization.

    Collects:
    - Raw transmission spectra (wavelength vs transmission %)
    - Processed wavelength values (resonance peaks)
    - Timestamps
    - Metadata (integration time, LED intensities, calibration parameters)

    Signals:
        recording_started: Emitted when recording begins
        recording_progress: Emitted periodically with progress info (elapsed, remaining, count)
        recording_complete: Emitted when recording finishes with filepath
        recording_error: Emitted if recording fails with error message
    """

    recording_started = Signal()
    recording_progress = Signal(
        dict,
    )  # {'elapsed': float, 'remaining': float, 'count': int}
    recording_complete = Signal(str)  # filepath
    recording_error = Signal(str)

    def __init__(self, data_acquisition_mgr, spectrum_viewmodels=None, parent=None) -> None:
        super().__init__(parent)

        self.data_mgr = data_acquisition_mgr
        self.spectrum_viewmodels = spectrum_viewmodels  # Dict of SpectrumViewModel (one per channel)
        self.recording = False
        self.duration_seconds = 300  # 5 minutes default

        # Data storage
        self.transmission_data = {
            "a": [],
            "b": [],
            "c": [],
            "d": [],
        }  # Raw transmission spectra
        self.wavelength_data = {
            "a": [],
            "b": [],
            "c": [],
            "d": [],
        }  # Processed peak wavelengths
        self.timestamps = {"a": [], "b": [], "c": [], "d": []}
        self.wavelength_axis = None  # Wavelength axis (same for all spectra)

        # Metadata
        self.metadata = {}
        self.start_time = None

        # Timer for progress updates
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self._update_progress)

    def start_recording(self, duration_minutes: float = 5.0) -> None:
        """Start recording baseline data.

        Args:
            duration_minutes: Recording duration in minutes (default: 5.0)

        """
        if self.recording:
            logger.warning("Recording already in progress")
            return

        if not self.data_mgr.calibrated:
            self.recording_error.emit(
                "System not calibrated. Please calibrate before recording.",
            )
            return

        if not self.data_mgr._acquiring:
            self.recording_error.emit(
                "Acquisition not running. Please start live mode first.",
            )
            return

        logger.info("=" * 80)
        logger.info("🔴 STARTING BASELINE DATA RECORDING")
        logger.info("=" * 80)
        logger.info(
            f"Duration: {duration_minutes:.1f} minutes ({duration_minutes * 60:.0f} seconds)",
        )
        logger.info("Purpose: Offline optimization of signal processing parameters")
        logger.info("Ensure stable baseline (no sample injections) during recording")
        logger.info("=" * 80)

        # Initialize recording
        self.duration_seconds = duration_minutes * 60
        self.recording = True
        self.start_time = datetime.now()

        # Clear previous data
        for ch in ["a", "b", "c", "d"]:
            self.transmission_data[ch].clear()
            self.wavelength_data[ch].clear()
            self.timestamps[ch].clear()

        # Capture wavelength axis from calibration data
        calib_data = self.data_mgr.calibration_data
        self.wavelength_axis = (
            calib_data.wavelengths.copy()
            if calib_data and calib_data.wavelengths is not None
            else None
        )

        # Capture metadata
        self.metadata = {
            "recording_start": self.start_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "integration_time_ms": calib_data.integration_time if calib_data else None,
            "num_scans": calib_data.num_scans if calib_data else None,
            "p_led_intensities": dict(calib_data.p_mode_intensities)
            if calib_data
            else {},
            "s_led_intensities": dict(calib_data.s_mode_intensities)
            if calib_data
            else {},
            "wavelength_min": float(self.wavelength_axis[0])
            if self.wavelength_axis is not None
            else None,
            "wavelength_max": float(self.wavelength_axis[-1])
            if self.wavelength_axis is not None
            else None,
            "wavelength_points": len(self.wavelength_axis)
            if self.wavelength_axis is not None
            else 0,
        }

        # Start progress timer (update every second)
        self.progress_timer.start(1000)

        # Connect to spectrum_updated and peak_updated signals (transmission + wavelength data)
        # If spectrum_viewmodels dict is available, connect to all 4 channels
        if self.spectrum_viewmodels and isinstance(self.spectrum_viewmodels, dict):
            logger.info("[OK] Connecting to spectrum_viewmodels signals...")
            for channel, vm in self.spectrum_viewmodels.items():
                if channel in ["a", "b", "c", "d"]:
                    try:
                        vm.spectrum_updated.disconnect(self._on_transmission_spectrum)
                    except:
                        pass  # Not connected yet, that's fine
                    vm.spectrum_updated.connect(self._on_transmission_spectrum)

                    try:
                        vm.peak_updated.disconnect(self._on_peak_updated)
                    except:
                        pass  # Not connected yet, that's fine
                    vm.peak_updated.connect(self._on_peak_updated)

                    logger.info(f"  ✓ Channel {channel.upper()}: Connected to spectrum_updated + peak_updated")
        else:
            # Fallback: connect to raw data acquisition signal
            try:
                self.data_mgr.spectrum_acquired.disconnect(self._on_spectrum_acquired)
            except:
                pass  # Not connected yet, that's fine
            self.data_mgr.spectrum_acquired.connect(self._on_spectrum_acquired)
            logger.warning("[FALLBACK] Connected to data_mgr.spectrum_acquired (transmission may not be available)")

        self.recording_started.emit()
        logger.info("[OK] Recording started - collecting data...")

    def _on_transmission_spectrum(self, channel: str, wavelengths: np.ndarray, transmission: np.ndarray) -> None:
        """Handle processed transmission spectrum from SpectrumViewModel.

        This is the preferred signal - transmission is already calculated.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            wavelengths: Wavelength axis (nm)
            transmission: Transmission spectrum (%)
        """
        try:
            if not self.recording:
                return

            if channel not in ["a", "b", "c", "d"]:
                return

            # Store wavelength axis (first time only)
            if self.wavelength_axis is None and wavelengths is not None and len(wavelengths) > 0:
                self.wavelength_axis = wavelengths.copy()
                logger.info(f"✓ Wavelength axis captured: {len(self.wavelength_axis)} points ({wavelengths[0]:.1f}-{wavelengths[-1]:.1f} nm)")

            # Store transmission spectrum (full array)
            if transmission is not None and isinstance(transmission, (np.ndarray, list)) and len(transmission) > 0:
                if isinstance(transmission, list):
                    transmission = np.ndarray(transmission)
                self.transmission_data[channel].append(transmission.copy())

                # Store timestamp
                import time
                self.timestamps[channel].append(time.time())
            else:
                # Log once per channel if transmission data is missing
                if not hasattr(self, '_logged_missing_transmission'):
                    self._logged_missing_transmission = set()
                if channel not in self._logged_missing_transmission:
                    logger.warning(f"Channel {channel}: transmission spectrum is empty or invalid")
                    self._logged_missing_transmission.add(channel)

        except Exception as e:
            logger.error(f"Baseline recorder error processing transmission spectrum: {e}")
            import traceback
            traceback.print_exc()

    def _on_peak_updated(self, channel: str, peak_wavelength: float, metadata: dict) -> None:
        """Handle peak_updated signal from SpectrumViewModel.

        Captures the processed wavelength peak for each spectrum.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            peak_wavelength: Detected peak wavelength (nm)
            metadata: Additional peak detection metadata
        """
        try:
            if not self.recording:
                return

            if channel not in ["a", "b", "c", "d"]:
                return

            # Store processed wavelength (single value - peak position)
            if peak_wavelength is not None:
                self.wavelength_data[channel].append(peak_wavelength)

        except Exception as e:
            logger.error(f"Baseline recorder error processing peak wavelength: {e}")
            import traceback
            traceback.print_exc()

    def _on_spectrum_acquired(self, data: dict) -> None:
        """Handle new spectrum data from acquisition manager (FALLBACK - raw data only).

        This is a fallback when SpectrumViewModel is not available.
        Transmission may not be present in raw data.
        """
        try:
            if not self.recording:
                return

            channel = data.get("channel")
            if channel not in ["a", "b", "c", "d"]:
                return

            # Store wavelength axis (first time only)
            wavelengths = data.get("wavelengths")
            if self.wavelength_axis is None and wavelengths is not None and len(wavelengths) > 0:
                self.wavelength_axis = wavelengths.copy()
                logger.info(f"✓ Wavelength axis captured: {len(self.wavelength_axis)} points")

            # Store transmission spectrum (full array) - may not be available in raw data
            transmission = data.get("transmission_spectrum")
            if transmission is not None and isinstance(transmission, (np.ndarray, list)) and len(transmission) > 0:
                # Convert to numpy array if it's a list
                if isinstance(transmission, list):
                    transmission = np.array(transmission)
                self.transmission_data[channel].append(transmission.copy())

                # Also store timestamp when we successfully capture transmission
                timestamp = data.get("timestamp")
                if timestamp is not None:
                    self.timestamps[channel].append(timestamp)
            else:
                # Log once per channel if transmission data is missing
                if not hasattr(self, '_logged_missing_transmission'):
                    self._logged_missing_transmission = set()
                if channel not in self._logged_missing_transmission:
                    logger.warning(f"Channel {channel}: transmission_spectrum not available in raw data dict (expected with fallback mode)")
                    self._logged_missing_transmission.add(channel)

            # Store processed wavelength (single value - peak position)
            wavelength = data.get("wavelength")
            if wavelength is not None:
                self.wavelength_data[channel].append(wavelength)
        except Exception as e:
            # Don't let baseline recorder crash the main acquisition thread
            logger.error(f"Baseline recorder error processing spectrum: {e}")
            import traceback
            traceback.print_exc()

    def _update_progress(self) -> None:
        """Update recording progress."""
        if not self.recording or self.start_time is None:
            return

        elapsed = (datetime.now() - self.start_time).total_seconds()
        remaining = max(0, self.duration_seconds - elapsed)

        # Count total spectra collected
        total_count = sum(
            len(self.transmission_data[ch]) for ch in ["a", "b", "c", "d"]
        )

        progress_info = {
            "elapsed": elapsed,
            "remaining": remaining,
            "count": total_count,
            "percent": min(100, (elapsed / self.duration_seconds) * 100),
        }

        self.recording_progress.emit(progress_info)

        # Log progress every 30 seconds
        if not hasattr(self, "_last_log_time") or elapsed - self._last_log_time >= 30:
            self._last_log_time = elapsed
            logger.info(
                f"📊 Baseline recording: {elapsed:.0f}s elapsed, {remaining:.0f}s remaining, {total_count} spectra collected",
            )

        # Check if recording is complete
        if elapsed >= self.duration_seconds:
            self.stop_recording()

    def stop_recording(self) -> None:
        """Stop recording and save data."""
        if not self.recording:
            return

        logger.info("⏹ Stopping baseline data recording...")

        # Stop timer and disconnect signals
        self.progress_timer.stop()

        # Disconnect from spectrum viewmodels if connected
        if self.spectrum_viewmodels and isinstance(self.spectrum_viewmodels, dict):
            for channel, vm in self.spectrum_viewmodels.items():
                if channel in ["a", "b", "c", "d"]:
                    try:
                        vm.spectrum_updated.disconnect(self._on_transmission_spectrum)
                    except:
                        pass  # Already disconnected
                    try:
                        vm.peak_updated.disconnect(self._on_peak_updated)
                    except:
                        pass  # Already disconnected
        else:
            # Disconnect from fallback signal
            try:
                self.data_mgr.spectrum_acquired.disconnect(self._on_spectrum_acquired)
            except:
                pass  # Already disconnected

        self.recording = False

        # Save data to file
        try:
            filepath = self._save_data()
            logger.info(f"[OK] Baseline data saved: {filepath}")
            self.recording_complete.emit(str(filepath))
        except Exception as e:
            error_msg = f"Failed to save baseline data: {e}"
            logger.error(error_msg)
            self.recording_error.emit(error_msg)

    def _save_data(self) -> Path:
        """Save recorded data to single Excel file with multiple tabs.

        Returns:
            Path to saved file

        """
        try:
            # Create output directory
            output_dir = Path("baseline_data")
            output_dir.mkdir(exist_ok=True)

            timestamp_str = self.start_time.strftime("%Y%m%d_%H%M%S")
            filepath = output_dir / f"baseline_recording_{timestamp_str}.xlsx"

            logger.info(f"💾 Saving baseline data to: {filepath}")

            # Check if we have any data to save
            total_transmission_count = sum(len(self.transmission_data[ch]) for ch in ["a", "b", "c", "d"])
            if total_transmission_count == 0:
                raise ValueError("No transmission data collected during recording. Check that transmission_spectrum is available in data stream.")

            logger.info(f"Total transmission spectra collected: {total_transmission_count}")
        except Exception as e:
            logger.error(f"Failed to initialize save operation: {e}")
            raise

        # Create Excel writer
        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            # Tab 1-4: Transmission spectra (one tab per channel)
            for ch in ["a", "b", "c", "d"]:
                if not self.transmission_data[ch] or len(self.transmission_data[ch]) == 0:
                    logger.warning(f"  Channel {ch}: No transmission data collected, skipping")
                    continue

                try:
                    # Create DataFrame with wavelength axis as index
                    df = pd.DataFrame(
                        np.array(self.transmission_data[ch]).T,
                        index=self.wavelength_axis,
                        columns=[
                            f"t_{i:04d}" for i in range(len(self.transmission_data[ch]))
                        ],
                    )
                    df.index.name = "wavelength_nm"

                    df.to_excel(writer, sheet_name=f"Channel_{ch.upper()}")
                    logger.info(
                        f"  Channel {ch}: {len(self.transmission_data[ch])} spectra -> Tab 'Channel_{ch.upper()}'",
                    )
                except Exception as e:
                    logger.error(f"  Channel {ch}: Failed to save transmission data - {e}")
                    # Continue with other channels even if one fails
                    continue

            # Tab 5: Wavelength traces (all channels)
            max_length = max(
                len(self.wavelength_data["a"]),
                len(self.wavelength_data["b"]),
                len(self.wavelength_data["c"]),
                len(self.wavelength_data["d"]),
            )

            # Pad each channel's data to max_length
            wavelength_dict = {}
            for ch in ["a", "b", "c", "d"]:
                wl_data = self.wavelength_data[ch]
                ts_data = self.timestamps[ch]

                # Pad with NaN if needed
                if len(wl_data) < max_length:
                    wl_data = wl_data + [np.nan] * (max_length - len(wl_data))
                    ts_data = ts_data + [np.nan] * (max_length - len(ts_data))

                wavelength_dict[f"channel_{ch}"] = wl_data
                wavelength_dict[f"timestamp_{ch}"] = ts_data

            wavelength_df = pd.DataFrame(wavelength_dict)
            wavelength_df.to_excel(writer, sheet_name="Wavelengths", index=False)
            logger.info("  Wavelength traces -> Tab 'Wavelengths'")

            # Tab 6: Metadata
            metadata_df = pd.DataFrame([self.metadata])
            metadata_df.to_excel(writer, sheet_name="Metadata", index=False)
            logger.info("  Metadata -> Tab 'Metadata'")

        logger.info("")
        logger.info("📊 RECORDING SUMMARY:")
        logger.info(f"  Duration: {self.duration_seconds / 60:.1f} minutes")
        for ch in ["a", "b", "c", "d"]:
            logger.info(
                f"  Channel {ch}: {len(self.transmission_data[ch])} spectra collected",
            )
        logger.info(f"  Output file: {filepath.absolute()}")

        return filepath

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.recording
