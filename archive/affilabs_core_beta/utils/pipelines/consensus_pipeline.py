"""Consensus SPR Analysis Pipeline.

This pipeline combines multiple peak-finding methods to achieve robust detection:
- Centroid method (weighted center-of-mass)
- Parabolic interpolation (3-point fit)
- Fourier derivative (zero-crossing)

The consensus approach yields a single point by weighted combination of all methods,
reducing systematic bias and improving robustness to peak shape variations.

Key Features:
- Multi-method validation (3 independent methods)
- Weighted averaging (60% centroid, 30% parabolic, 10% fourier)
- Outlier detection and replacement
- Confidence scoring based on method agreement

Author: AI Assistant
Date: November 24, 2025
"""

import numpy as np
from typing import Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class ConsensusPipeline:
    """Pipeline combining multiple peak-finding methods for robust detection."""

    def __init__(self, config=None):
        """Initialize the consensus pipeline.

        Args:
            config: Optional configuration dict (for compatibility with pipeline registry)
        """
        self.name = "Consensus"
        self.description = "Combines 3 methods (centroid, parabolic, fourier) for robust peak detection"
        self.config = config or {}

        # Import the consensus functions
        try:
            from utils.peak_consensus import find_peak_consensus
            self.find_peak_consensus = find_peak_consensus
        except ImportError:
            logger.warning("peak_consensus module not found, using fallback")
            self.find_peak_consensus = None

    def get_metadata(self) -> Dict:
        """Return pipeline metadata."""
        return {
            'name': self.name,
            'description': self.description,
            'version': '1.0',
            'features': ['multi_method', 'weighted_consensus', 'outlier_detection'],
        }

    def find_resonance_wavelength(
        self,
        transmission: np.ndarray,
        wavelengths: np.ndarray,
        timestamp: Optional[float] = None,
    ) -> Tuple[float, Dict]:
        """Find resonance wavelength using consensus of multiple methods.

        Args:
            transmission: Transmission spectrum (%)
            wavelengths: Wavelength array (nm)
            timestamp: Optional timestamp (unused, for compatibility)

        Returns:
            Tuple of (resonance_wavelength, metadata_dict)
        """
        if transmission is None or wavelengths is None:
            raise ValueError("Invalid input data")
        if len(transmission) != len(wavelengths):
            raise ValueError("Data length mismatch")

        # Use consensus method if available
        if self.find_peak_consensus is not None:
            try:
                # Get consensus peak with diagnostics
                peak_wavelength, diagnostics = self.find_peak_consensus(
                    spectrum=transmission,
                    wavelengths=wavelengths,
                    search_range=(600, 720),
                    method='weighted_average'  # 60% centroid + 40% parabolic by default
                )

                # Add pipeline metadata
                metadata = {
                    'method': 'consensus',
                    'peak_wavelength': float(peak_wavelength),
                    **diagnostics
                }

                return peak_wavelength, metadata

            except Exception as e:
                logger.error(f"Consensus method failed: {e}, using fallback")

        # Fallback: simple minimum
        logger.warning("Using fallback minimum method")
        mask = (wavelengths >= 600) & (wavelengths <= 720)
        wl_region = wavelengths[mask]
        spec_region = transmission[mask]

        if len(wl_region) > 0:
            min_idx = np.argmin(spec_region)
            peak_wavelength = wl_region[min_idx]
        else:
            peak_wavelength = wavelengths[np.argmin(transmission)]

        metadata = {
            'method': 'fallback_minimum',
            'peak_wavelength': float(peak_wavelength)
        }

        return peak_wavelength, metadata

    def reset_temporal_state(self):
        """Reset any temporal state (for compatibility with other pipelines)."""
        pass  # Consensus pipeline is stateless
