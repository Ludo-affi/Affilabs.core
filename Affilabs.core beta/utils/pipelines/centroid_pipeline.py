"""Centroid-based SPR Processing Pipeline

Alternative pipeline that uses centroid calculation to find resonance wavelength.
This method finds the center of mass of the inverted transmission dip.
"""

import numpy as np
from scipy.ndimage import gaussian_filter1d

from utils.processing_pipeline import ProcessingPipeline, PipelineMetadata
from utils.logger import logger


class CentroidPipeline(ProcessingPipeline):
    """Pipeline using centroid method for peak detection
    
    This method finds the resonance wavelength by calculating the centroid
    (center of mass) of the inverted transmission spectrum around the dip region.
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        
        # Default parameters
        self.smoothing_sigma = self.config.get('smoothing_sigma', 2.0)
        self.search_window = self.config.get('search_window', 100)  # pixels around minimum
        self.min_dip_depth = self.config.get('min_dip_depth', 5.0)  # % transmission drop
    
    def get_metadata(self) -> PipelineMetadata:
        return PipelineMetadata(
            name="Centroid Method",
            description="Finds resonance via center of mass of transmission dip",
            version="1.0",
            author="ezControl Team",
            parameters={
                'smoothing_sigma': self.smoothing_sigma,
                'search_window': self.search_window,
                'min_dip_depth': self.min_dip_depth,
                'method': 'Centroid (Center of Mass)'
            }
        )
    
    def calculate_transmission(
        self,
        intensity: np.ndarray,
        reference: np.ndarray
    ) -> np.ndarray:
        """Standard transmission calculation
        
        Transmission = (Intensity / Reference) * 100
        """
        if intensity.shape != reference.shape:
            raise ValueError(f"Shape mismatch: intensity {intensity.shape} vs reference {reference.shape}")
        
        # Avoid division by zero
        with np.errstate(divide='ignore', invalid='ignore'):
            transmission = (intensity / reference) * 100
            transmission = np.where(reference == 0, 0, transmission)
        
        return transmission
    
    def find_resonance_wavelength(
        self,
        transmission: np.ndarray,
        wavelengths: np.ndarray,
        **kwargs
    ) -> float:
        """Find resonance using centroid method
        
        Algorithm:
        1. Apply Gaussian smoothing to reduce noise
        2. Find global minimum in transmission (resonance dip)
        3. Extract window around minimum
        4. Invert spectrum to make dip a peak
        5. Calculate centroid (weighted average) of inverted region
        
        Args:
            transmission: Transmission spectrum
            wavelengths: Wavelength array
            **kwargs: Additional parameters (smoothing_sigma, search_window override)
        """
        try:
            # Allow parameter overrides
            smoothing_sigma = kwargs.get('smoothing_sigma', self.smoothing_sigma)
            search_window = kwargs.get('search_window', self.search_window)
            min_dip_depth = kwargs.get('min_dip_depth', self.min_dip_depth)
            
            # Step 1: Apply Gaussian smoothing
            smoothed = gaussian_filter1d(transmission, sigma=smoothing_sigma)
            
            # Step 2: Find global minimum (deepest part of dip)
            min_idx = np.argmin(smoothed)
            min_value = smoothed[min_idx]
            
            # Step 3: Define search window around minimum
            start_idx = max(0, min_idx - search_window)
            end_idx = min(len(smoothed), min_idx + search_window)
            
            # Extract window
            window_spectrum = smoothed[start_idx:end_idx]
            window_wavelengths = wavelengths[start_idx:end_idx]
            
            # Step 4: Check if dip is significant enough
            baseline = np.median(transmission)
            dip_depth = baseline - min_value
            
            if dip_depth < min_dip_depth:
                logger.debug(f"Dip too shallow ({dip_depth:.1f}% < {min_dip_depth}%), using minimum")
                return float(wavelengths[min_idx])
            
            # Step 5: Invert spectrum (make dip into peak for centroid calculation)
            # Normalize so minimum becomes maximum
            inverted = np.max(window_spectrum) - window_spectrum
            
            # Ensure non-negative weights
            inverted = np.maximum(inverted, 0)
            
            # Step 6: Calculate centroid (weighted average)
            if np.sum(inverted) > 0:
                centroid_wavelength = np.sum(window_wavelengths * inverted) / np.sum(inverted)
            else:
                # Fallback to minimum position
                centroid_wavelength = wavelengths[min_idx]
            
            return float(centroid_wavelength)
            
        except Exception as e:
            logger.debug(f"Centroid pipeline error: {e}")
            return np.nan
