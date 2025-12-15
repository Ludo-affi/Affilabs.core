"""Spectrum Preprocessing - Single source of truth for dark noise removal.

This module provides unified spectrum preprocessing across the application:
- Dark noise removal (baseline subtraction)

Used by:
- calibration_6step.py (finalcalQC - preparing S-pol/P-pol references)
- transmission_processor.py (process_single_channel - preprocessing before transmission calc)
- data_acquisition_manager.py (live acquisition - preprocessing raw spectra)

Architecture:
- Layer 2 (Core Business Logic)
- Utils should call this, not implement their own preprocessing
"""

import numpy as np

from utils.logger import logger


class SpectrumPreprocessor:
    """Single source of truth for spectrum preprocessing.

    This class handles dark noise removal (baseline subtraction).

    All spectrum processing in the application should use these methods
    to ensure consistency and maintainability.
    """

    @staticmethod
    def process_polarization_data(
        raw_spectrum: np.ndarray,
        dark_noise: np.ndarray | None = None,
        channel_name: str = "",
        verbose: bool = False,
    ) -> np.ndarray:
        """Remove dark noise from raw spectrum.

        This is the primary preprocessing method used before any analysis
        (transmission calculation, display, peak finding, etc.).

        Args:
            raw_spectrum: Raw spectrum counts from spectrometer (ROI-only: wavelength-adapted range)
            dark_noise: Dark reference spectrum (must match raw_spectrum length; use ROI-sliced dark)
            channel_name: Channel identifier for logging (e.g., "a", "b", "c", "d")
            verbose: Enable detailed logging

        Returns:
            Clean spectrum with dark noise removed

        Processing steps:
            1. Copy raw spectrum (preserve original)
            2. Subtract dark noise if provided
            3. Return clean spectrum

        Example:
            >>> clean = SpectrumPreprocessor.process_polarization_data(
            ...     raw_spectrum=raw_counts,
            ...     dark_noise=dark_ref,
            ...     channel_name="b",
            ...     verbose=True
            ... )

        """
        # Start with copy (preserve original)
        clean_spectrum = raw_spectrum.copy()

        if verbose and channel_name:
            logger.info(f"[Preprocessor] Channel {channel_name.upper()}:")
            logger.info(
                f"   Raw spectrum: mean={np.mean(clean_spectrum):.1f}, max={np.max(clean_spectrum):.1f}",
            )

        # Dark noise removal
        if dark_noise is not None:
            if len(dark_noise) != len(clean_spectrum):
                raise ValueError(
                    "Dark noise length mismatch. Downstream expects ROI-sliced dark "
                    f"(got {len(dark_noise)} vs spectrum {len(clean_spectrum)}). "
                    "Ensure dark uses the wavelength-adapted spectral range (same ROI).",
                )

            dark_mean = np.mean(dark_noise)
            clean_spectrum = clean_spectrum - dark_noise

            if verbose:
                logger.info(f"   Dark removed: mean={dark_mean:.1f} counts")
                logger.info(
                    f"   After dark removal: mean={np.mean(clean_spectrum):.1f}",
                )

        if verbose and channel_name:
            logger.info(
                f"   Final clean spectrum: mean={np.mean(clean_spectrum):.1f}, max={np.max(clean_spectrum):.1f}",
            )

        return clean_spectrum

    @staticmethod
    def process_batch_channels(
        raw_spectra: dict[str, np.ndarray],
        dark_noise: np.ndarray | None,
        ch_list: list[str],
        verbose: bool = False,
    ) -> dict[str, np.ndarray]:
        """Process multiple channels with dark noise removal.

        Args:
            raw_spectra: Dict of {channel: raw_spectrum}
            dark_noise: Common dark reference for all channels
            ch_list: Ordered list of channels (e.g., ['a', 'b', 'c', 'd'])
            verbose: Enable detailed logging

        Returns:
            Dict of {channel: clean_spectrum}

        Example:
            >>> clean_spectra = SpectrumPreprocessor.process_batch_channels(
            ...     raw_spectra={'a': s_a, 'b': s_b, 'c': s_c, 'd': s_d},
            ...     dark_noise=dark_ref,
            ...     ch_list=['a', 'b', 'c', 'd'],
            ...     verbose=True
            ... )

        """
        if verbose:
            logger.info("=" * 80)
            logger.info("SpectrumPreprocessor: Processing Batch Channels")
            logger.info("=" * 80)

        clean_spectra = {}

        for ch in ch_list:
            # Process this channel
            clean_spectra[ch] = SpectrumPreprocessor.process_polarization_data(
                raw_spectrum=raw_spectra[ch],
                dark_noise=dark_noise,
                channel_name=ch,
                verbose=verbose,
            )

        if verbose:
            logger.info("=" * 80)
            logger.info("✅ Batch preprocessing complete")
            logger.info("=" * 80)

        return clean_spectra
