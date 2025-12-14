"""Baseline Data Recorder - Records transmission spectra for noise optimization analysis.

This module records raw transmission spectra during stable baseline acquisition
for offline analysis of signal processing parameters (SG filter, Fourier alpha, etc.)
"""

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from PySide6.QtCore import QObject, Signal, QTimer
from utils.logger import logger


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
    recording_progress = Signal(dict)  # {'elapsed': float, 'remaining': float, 'count': int}
    recording_complete = Signal(str)  # filepath
    recording_error = Signal(str)

    def __init__(self, data_acquisition_mgr, parent=None):
        super().__init__(parent)

        self.data_mgr = data_acquisition_mgr
        self.recording = False
        self.duration_seconds = 300  # 5 minutes default

        # Data storage
        self.transmission_data = {'a': [], 'b': [], 'c': [], 'd': []}  # Raw transmission spectra
        self.wavelength_data = {'a': [], 'b': [], 'c': [], 'd': []}  # Processed peak wavelengths
        self.timestamps = {'a': [], 'b': [], 'c': [], 'd': []}
        self.wavelength_axis = None  # Wavelength axis (same for all spectra)

        # Metadata
        self.metadata = {}
        self.start_time = None

        # Timer for progress updates
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self._update_progress)

    def start_recording(self, duration_minutes: float = 5.0):
        """Start recording baseline data.

        Args:
            duration_minutes: Recording duration in minutes (default: 5.0)
        """
        if self.recording:
            logger.warning("Recording already in progress")
            return

        if not self.data_mgr.calibrated:
            self.recording_error.emit("System not calibrated. Please calibrate before recording.")
            return

        if not self.data_mgr._acquiring:
            self.recording_error.emit("Acquisition not running. Please start live mode first.")
            return

        logger.info("=" * 80)
        logger.info("🔴 STARTING BASELINE DATA RECORDING")
        logger.info("=" * 80)
        logger.info(f"Duration: {duration_minutes:.1f} minutes ({duration_minutes * 60:.0f} seconds)")
        logger.info("Purpose: Offline optimization of signal processing parameters")
        logger.info("Ensure stable baseline (no sample injections) during recording")
        logger.info("=" * 80)

        # Initialize recording
        self.duration_seconds = duration_minutes * 60
        self.recording = True
        self.start_time = datetime.now()

        # Clear previous data
        for ch in ['a', 'b', 'c', 'd']:
            self.transmission_data[ch].clear()
            self.wavelength_data[ch].clear()
            self.timestamps[ch].clear()

        # Capture wavelength axis
        self.wavelength_axis = self.data_mgr.wave_data.copy() if self.data_mgr.wave_data is not None else None

        # Capture metadata
        self.metadata = {
            'recording_start': self.start_time.isoformat(),
            'duration_seconds': self.duration_seconds,
            'integration_time_ms': self.data_mgr.integration_time,
            'num_scans': self.data_mgr.num_scans,
            'p_led_intensities': dict(self.data_mgr.leds_calibrated),
            's_led_intensities': dict(self.data_mgr.ref_intensity),
            'wavelength_min': float(self.wavelength_axis[0]) if self.wavelength_axis is not None else None,
            'wavelength_max': float(self.wavelength_axis[-1]) if self.wavelength_axis is not None else None,
            'wavelength_points': len(self.wavelength_axis) if self.wavelength_axis is not None else 0,
        }

        # Start progress timer (update every second)
        self.progress_timer.start(1000)

        # Connect to data acquisition signals
        self.data_mgr.spectrum_acquired.connect(self._on_spectrum_acquired)

        self.recording_started.emit()
        logger.info("✅ Recording started - collecting data...")

    def _on_spectrum_acquired(self, data: Dict):
        """Handle new spectrum data from acquisition manager."""
        if not self.recording:
            return

        channel = data.get('channel')
        if channel not in ['a', 'b', 'c', 'd']:
            return

        # Store transmission spectrum
        transmission = data.get('transmission_spectrum')
        if transmission is not None:
            self.transmission_data[channel].append(transmission.copy())

        # Store processed wavelength
        wavelength = data.get('wavelength')
        if wavelength is not None:
            self.wavelength_data[channel].append(wavelength)

        # Store timestamp
        timestamp = data.get('timestamp')
        if timestamp is not None:
            self.timestamps[channel].append(timestamp)

    def _update_progress(self):
        """Update recording progress."""
        if not self.recording or self.start_time is None:
            return

        elapsed = (datetime.now() - self.start_time).total_seconds()
        remaining = max(0, self.duration_seconds - elapsed)

        # Count total spectra collected
        total_count = sum(len(self.transmission_data[ch]) for ch in ['a', 'b', 'c', 'd'])

        progress_info = {
            'elapsed': elapsed,
            'remaining': remaining,
            'count': total_count,
            'percent': min(100, (elapsed / self.duration_seconds) * 100)
        }

        self.recording_progress.emit(progress_info)

        # Check if recording is complete
        if elapsed >= self.duration_seconds:
            self.stop_recording()

    def stop_recording(self):
        """Stop recording and save data."""
        if not self.recording:
            return

        logger.info("⏹️ Stopping baseline data recording...")

        # Stop timer and disconnect signals
        self.progress_timer.stop()
        try:
            self.data_mgr.spectrum_acquired.disconnect(self._on_spectrum_acquired)
        except:
            pass  # Already disconnected

        self.recording = False

        # Save data to file
        try:
            filepath = self._save_data()
            logger.info(f"✅ Baseline data saved: {filepath}")
            self.recording_complete.emit(str(filepath))
        except Exception as e:
            error_msg = f"Failed to save baseline data: {e}"
            logger.error(error_msg)
            self.recording_error.emit(error_msg)

    def _save_data(self) -> Path:
        """Save recorded data to CSV file.

        Returns:
            Path to saved file
        """
        # Create output directory
        output_dir = Path("baseline_data")
        output_dir.mkdir(exist_ok=True)

        timestamp_str = self.start_time.strftime("%Y%m%d_%H%M%S")

        # Save transmission spectra (one file per channel)
        for ch in ['a', 'b', 'c', 'd']:
            if not self.transmission_data[ch]:
                continue

            # Create DataFrame with wavelength axis as index
            df = pd.DataFrame(
                np.array(self.transmission_data[ch]).T,
                index=self.wavelength_axis,
                columns=[f"t_{i:04d}" for i in range(len(self.transmission_data[ch]))]
            )
            df.index.name = 'wavelength_nm'

            filepath = output_dir / f"baseline_transmission_ch{ch}_{timestamp_str}.csv"
            df.to_csv(filepath)
            logger.info(f"  Channel {ch}: {len(self.transmission_data[ch])} spectra -> {filepath.name}")

        # Save wavelength traces (all channels in one file)
        # Channels may have different lengths, so pad with NaN to make them equal
        max_length = max(
            len(self.wavelength_data['a']),
            len(self.wavelength_data['b']),
            len(self.wavelength_data['c']),
            len(self.wavelength_data['d'])
        )

        # Pad each channel's data to max_length
        wavelength_dict = {}
        for ch in ['a', 'b', 'c', 'd']:
            wl_data = self.wavelength_data[ch]
            ts_data = self.timestamps[ch]

            # Pad with NaN if needed
            if len(wl_data) < max_length:
                wl_data = wl_data + [np.nan] * (max_length - len(wl_data))
                ts_data = ts_data + [np.nan] * (max_length - len(ts_data))

            wavelength_dict[f'channel_{ch}'] = wl_data
            wavelength_dict[f'timestamp_{ch}'] = ts_data

        wavelength_df = pd.DataFrame(wavelength_dict)
        wavelength_filepath = output_dir / f"baseline_wavelengths_{timestamp_str}.csv"
        wavelength_df.to_csv(wavelength_filepath, index=False)
        logger.info(f"  Wavelength traces: {wavelength_filepath.name}")

        # Save metadata
        metadata_df = pd.DataFrame([self.metadata])
        metadata_filepath = output_dir / f"baseline_metadata_{timestamp_str}.csv"
        metadata_df.to_csv(metadata_filepath, index=False)
        logger.info(f"  Metadata: {metadata_filepath.name}")

        logger.info("")
        logger.info("📊 RECORDING SUMMARY:")
        logger.info(f"  Duration: {self.duration_seconds / 60:.1f} minutes")
        for ch in ['a', 'b', 'c', 'd']:
            logger.info(f"  Channel {ch}: {len(self.transmission_data[ch])} spectra collected")
        logger.info(f"  Output directory: {output_dir.absolute()}")

        return wavelength_filepath

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.recording
