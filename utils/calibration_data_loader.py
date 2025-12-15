"""Utility functions for loading saved calibration data for longitudinal processing.

This module provides functions to load dark noise, S-mode reference signals,
and wavelength arrays that were saved during calibration.
"""

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def get_calibration_data_dir() -> Path:
    """Get the calibration data directory path."""
    from settings import ROOT_DIR

    return Path(ROOT_DIR) / "calibration_data"


def load_latest_dark_noise() -> np.ndarray | None:
    """Load the most recent dark noise array.

    Returns:
        Dark noise array, or None if not found

    """
    try:
        calib_dir = get_calibration_data_dir()
        dark_file = calib_dir / "dark_noise_latest.npy"

        if not dark_file.exists():
            logger.warning(f"Dark noise file not found: {dark_file}")
            return None

        dark_noise = np.load(dark_file)
        logger.info(
            f"✅ Loaded dark noise: {len(dark_noise)} pixels, mean={dark_noise.mean():.1f} counts",
        )
        return dark_noise

    except Exception as e:
        logger.exception(f"Error loading dark noise: {e}")
        return None


def load_dark_noise_by_timestamp(timestamp: str) -> np.ndarray | None:
    """Load dark noise array from a specific calibration run.

    Args:
        timestamp: Timestamp string in format "YYYYMMDD_HHMMSS"

    Returns:
        Dark noise array, or None if not found

    """
    try:
        calib_dir = get_calibration_data_dir()
        dark_file = calib_dir / f"dark_noise_{timestamp}.npy"

        if not dark_file.exists():
            logger.warning(f"Dark noise file not found: {dark_file}")
            return None

        dark_noise = np.load(dark_file)
        logger.info(f"✅ Loaded dark noise from {timestamp}: {len(dark_noise)} pixels")
        return dark_noise

    except Exception as e:
        logger.exception(f"Error loading dark noise: {e}")
        return None


def load_latest_s_references() -> dict[str, np.ndarray] | None:
    """Load the most recent S-mode reference signals for all channels.

    Returns:
        Dictionary mapping channel ('a', 'b', 'c', 'd') to reference array,
        or None if not found

    """
    try:
        calib_dir = get_calibration_data_dir()
        s_refs = {}

        for ch in ["a", "b", "c", "d"]:
            s_ref_file = calib_dir / f"s_ref_{ch}_latest.npy"

            if not s_ref_file.exists():
                logger.warning(f"S-ref file not found: {s_ref_file}")
                continue

            s_refs[ch] = np.load(s_ref_file)
            logger.info(
                f"✅ Loaded S-ref[{ch}]: {len(s_refs[ch])} pixels, max={s_refs[ch].max():.1f} counts",
            )

        if not s_refs:
            logger.warning("No S-mode reference files found")
            return None

        return s_refs

    except Exception as e:
        logger.exception(f"Error loading S-mode references: {e}")
        return None


def load_s_references_by_timestamp(timestamp: str) -> dict[str, np.ndarray] | None:
    """Load S-mode reference signals from a specific calibration run.

    Args:
        timestamp: Timestamp string in format "YYYYMMDD_HHMMSS"

    Returns:
        Dictionary mapping channel to reference array, or None if not found

    """
    try:
        calib_dir = get_calibration_data_dir()
        s_refs = {}

        for ch in ["a", "b", "c", "d"]:
            s_ref_file = calib_dir / f"s_ref_{ch}_{timestamp}.npy"

            if not s_ref_file.exists():
                logger.warning(f"S-ref file not found: {s_ref_file}")
                continue

            s_refs[ch] = np.load(s_ref_file)
            logger.info(
                f"✅ Loaded S-ref[{ch}] from {timestamp}: {len(s_refs[ch])} pixels",
            )

        if not s_refs:
            logger.warning(f"No S-mode reference files found for {timestamp}")
            return None

        return s_refs

    except Exception as e:
        logger.exception(f"Error loading S-mode references: {e}")
        return None


def load_latest_wavelengths() -> np.ndarray | None:
    """Load the most recent wavelength array.

    Returns:
        Wavelength array in nm, or None if not found

    """
    try:
        calib_dir = get_calibration_data_dir()
        wave_file = calib_dir / "wavelengths_latest.npy"

        if not wave_file.exists():
            logger.warning(f"Wavelength file not found: {wave_file}")
            return None

        wavelengths = np.load(wave_file)
        logger.info(
            f"✅ Loaded wavelengths: {len(wavelengths)} pixels, "
            f"range={wavelengths[0]:.1f}-{wavelengths[-1]:.1f} nm",
        )
        return wavelengths

    except Exception as e:
        logger.exception(f"Error loading wavelengths: {e}")
        return None


def load_wavelengths_by_timestamp(timestamp: str) -> np.ndarray | None:
    """Load wavelength array from a specific calibration run.

    Args:
        timestamp: Timestamp string in format "YYYYMMDD_HHMMSS"

    Returns:
        Wavelength array, or None if not found

    """
    try:
        calib_dir = get_calibration_data_dir()
        wave_file = calib_dir / f"wavelengths_{timestamp}.npy"

        if not wave_file.exists():
            logger.warning(f"Wavelength file not found: {wave_file}")
            return None

        wavelengths = np.load(wave_file)
        logger.info(
            f"✅ Loaded wavelengths from {timestamp}: {len(wavelengths)} pixels",
        )
        return wavelengths

    except Exception as e:
        logger.exception(f"Error loading wavelengths: {e}")
        return None


def load_complete_calibration_set(
    timestamp: str | None = None,
) -> tuple[np.ndarray, dict[str, np.ndarray], np.ndarray] | None:
    """Load a complete calibration data set (wavelengths, S-refs, dark noise).

    Args:
        timestamp: Optional timestamp string. If None, loads latest calibration.

    Returns:
        Tuple of (wavelengths, s_refs, dark_noise), or None if incomplete

    """
    try:
        if timestamp:
            wavelengths = load_wavelengths_by_timestamp(timestamp)
            s_refs = load_s_references_by_timestamp(timestamp)
            dark_noise = load_dark_noise_by_timestamp(timestamp)
        else:
            wavelengths = load_latest_wavelengths()
            s_refs = load_latest_s_references()
            dark_noise = load_latest_dark_noise()

        if wavelengths is None or s_refs is None or dark_noise is None:
            logger.error("Incomplete calibration data set")
            return None

        # Validate sizes match
        expected_size = len(wavelengths)
        if len(dark_noise) != expected_size:
            logger.error(
                f"Size mismatch: wavelengths={expected_size}, dark={len(dark_noise)}",
            )
            return None

        for ch, s_ref in s_refs.items():
            if len(s_ref) != expected_size:
                logger.error(
                    f"Size mismatch: wavelengths={expected_size}, s_ref[{ch}]={len(s_ref)}",
                )
                return None

        logger.info("✅ Complete calibration set loaded and validated")
        return wavelengths, s_refs, dark_noise

    except Exception as e:
        logger.exception(f"Error loading calibration set: {e}")
        return None


def list_available_calibrations() -> list[str]:
    """List all available calibration timestamps.

    Returns:
        List of timestamp strings

    """
    try:
        calib_dir = get_calibration_data_dir()

        if not calib_dir.exists():
            logger.warning(f"Calibration directory not found: {calib_dir}")
            return []

        # Find all dark noise files (they're saved for every calibration)
        dark_files = list(calib_dir.glob("dark_noise_*.npy"))

        # Extract timestamps (exclude "latest")
        timestamps = []
        for f in dark_files:
            if "latest" not in f.name:
                # Extract timestamp from "dark_noise_YYYYMMDD_HHMMSS.npy"
                timestamp = f.stem.replace("dark_noise_", "")
                timestamps.append(timestamp)

        timestamps.sort(reverse=True)  # Most recent first
        logger.info(f"Found {len(timestamps)} calibration sets")

        return timestamps

    except Exception as e:
        logger.exception(f"Error listing calibrations: {e}")
        return []


# Example usage for longitudinal data processing:
"""
# Load most recent calibration
wavelengths, s_refs, dark_noise = load_complete_calibration_set()

# Or load specific calibration by timestamp
wavelengths, s_refs, dark_noise = load_complete_calibration_set("20251011_123456")

# Process your P-mode measurement data
p_raw = measure_p_mode_spectrum()
p_corrected = p_raw - dark_noise

# Calculate transmittance for each channel
for ch in ['a', 'b', 'c', 'd']:
    transmittance = (p_corrected / s_refs[ch]) * 100.0
    plot_transmittance(wavelengths, transmittance, ch)

# List all available calibrations
timestamps = list_available_calibrations()
print(f"Available calibrations: {timestamps}")
"""
