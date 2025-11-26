"""Polynomial Fitting SPR Processing Pipeline

Alternative pipeline that uses polynomial curve fitting to find resonance wavelength.
Fits a polynomial around the transmission dip and finds its minimum analytically.
"""

import numpy as np
from scipy.optimize import curve_fit

from utils.processing_pipeline import ProcessingPipeline, PipelineMetadata
from utils.logger import logger


class PolynomialPipeline(ProcessingPipeline):
    """Pipeline using polynomial fitting for peak detection
    
    This method fits a polynomial to the transmission dip region and
    finds the minimum analytically by taking the derivative.
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        
        # Default parameters
        self.poly_degree = self.config.get('poly_degree', 4)  # 4th degree polynomial
        self.fit_window = self.config.get('fit_window', 80)  # pixels around minimum
        self.use_weighted = self.config.get('use_weighted', True)  # Weight points near minimum
    
    def get_metadata(self) -> PipelineMetadata:
        return PipelineMetadata(
            name="Polynomial Fitting",
            description="Fits polynomial to dip and finds minimum analytically",
            version="1.0",
            author="ezControl Team",
            parameters={
                'poly_degree': self.poly_degree,
                'fit_window': self.fit_window,
                'use_weighted': self.use_weighted,
                'method': f'Polynomial (degree {self.poly_degree})'
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
        """Find resonance using polynomial fitting
        
        Algorithm:
        1. Find approximate minimum in transmission
        2. Extract window around minimum
        3. Fit polynomial to window data
        4. Find polynomial minimum analytically (derivative = 0)
        
        Args:
            transmission: Transmission spectrum
            wavelengths: Wavelength array
            **kwargs: Additional parameters (poly_degree, fit_window override)
        """
        try:
            # Allow parameter overrides
            poly_degree = kwargs.get('poly_degree', self.poly_degree)
            fit_window = kwargs.get('fit_window', self.fit_window)
            use_weighted = kwargs.get('use_weighted', self.use_weighted)
            
            # Step 1: Find approximate minimum
            min_idx = np.argmin(transmission)
            
            # Step 2: Define fitting window
            start_idx = max(0, min_idx - fit_window)
            end_idx = min(len(transmission), min_idx + fit_window)
            
            # Extract window
            window_wavelengths = wavelengths[start_idx:end_idx]
            window_transmission = transmission[start_idx:end_idx]
            
            # Check if window is large enough
            if len(window_wavelengths) < poly_degree + 2:
                logger.debug(f"Window too small for poly fit (degree {poly_degree})")
                return float(wavelengths[min_idx])
            
            # Step 3: Fit polynomial
            if use_weighted:
                # Weight points closer to minimum more heavily
                center_wl = wavelengths[min_idx]
                distances = np.abs(window_wavelengths - center_wl)
                weights = np.exp(-distances**2 / (2 * (fit_window / 4)**2))
            else:
                weights = np.ones_like(window_wavelengths)
            
            # Fit polynomial with weights
            poly_coeffs = np.polyfit(
                window_wavelengths,
                window_transmission,
                poly_degree,
                w=weights
            )
            
            # Step 4: Find minimum analytically
            # Take derivative of polynomial
            derivative_coeffs = np.polyder(poly_coeffs)
            
            # Find roots of derivative (critical points)
            critical_points = np.roots(derivative_coeffs)
            
            # Filter for real roots within window
            real_critical = critical_points[np.isreal(critical_points)].real
            valid_critical = real_critical[
                (real_critical >= window_wavelengths[0]) &
                (real_critical <= window_wavelengths[-1])
            ]
            
            if len(valid_critical) == 0:
                # No valid critical point found, use approximate minimum
                logger.debug("No critical point in window, using argmin")
                return float(wavelengths[min_idx])
            
            # Evaluate polynomial at critical points to find minimum
            poly_func = np.poly1d(poly_coeffs)
            values_at_critical = poly_func(valid_critical)
            min_critical_idx = np.argmin(values_at_critical)
            resonance_wavelength = valid_critical[min_critical_idx]
            
            return float(resonance_wavelength)
            
        except Exception as e:
            logger.debug(f"Polynomial pipeline error: {e}")
            return np.nan
