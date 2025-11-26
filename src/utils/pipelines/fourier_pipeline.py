"""Default SPR Processing Pipeline

This is the current/default processing pipeline that uses:
- Standard transmission calculation (intensity/reference * 100)
- Fourier transform method for resonance wavelength detection

This pipeline serves as the baseline for comparison with other methods.
"""

import numpy as np
from scipy.fftpack import dst, idct
from scipy.stats import linregress

from utils.processing_pipeline import ProcessingPipeline, PipelineMetadata
from utils.logger import logger


class FourierPipeline(ProcessingPipeline):
    """Default pipeline using Fourier transform for peak detection
    
    This is the established method that has been used in the application.
    It uses DST/IDCT to find the derivative zero-crossing point.
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        
        # Default parameters
        self.window_size = self.config.get('window_size', 165)
        self.alpha = self.config.get('alpha', 2e3)  # Fourier weight parameter
        self.baseline_correction = self.config.get('baseline_correction', False)  # Flatten spectral tilt
        self.baseline_degree = self.config.get('baseline_degree', 2)  # Polynomial degree for baseline
    
    def get_metadata(self) -> PipelineMetadata:
        return PipelineMetadata(
            name="Fourier Transform (Default)",
            description="Uses DST/IDCT to find resonance dip via derivative zero-crossing",
            version="1.0",
            author="ezControl Team",
            parameters={
                'window_size': self.window_size,
                'alpha': self.alpha,
                'baseline_correction': self.baseline_correction,
                'baseline_degree': self.baseline_degree,
                'method': 'Discrete Sine Transform + Zero-crossing'
            }
        )
    
    def calculate_transmission(
        self,
        intensity: np.ndarray,
        reference: np.ndarray
    ) -> np.ndarray:
        """Standard transmission calculation with optional baseline correction
        
        Transmission = (Intensity / Reference) * 100
        
        Optional baseline correction removes spectral tilt caused by:
        - LED wavelength-dependent intensity
        - Detector wavelength-dependent sensitivity
        - Optical path wavelength-dependent losses
        """
        if intensity.shape != reference.shape:
            raise ValueError(f"Shape mismatch: intensity {intensity.shape} vs reference {reference.shape}")
        
        # Avoid division by zero
        with np.errstate(divide='ignore', invalid='ignore'):
            transmission = (intensity / reference) * 100
            transmission = np.where(reference == 0, 0, transmission)
        
        # Apply baseline correction if enabled
        if self.baseline_correction:
            logger.info("Applying baseline correction to transmission spectrum")
            transmission = self._apply_baseline_correction(transmission)
        
        return transmission
    
    def _apply_baseline_correction(self, transmission: np.ndarray) -> np.ndarray:
        """Apply polynomial baseline correction to flatten spectral tilt
        
        This removes the systematic wavelength-dependent variation in transmission
        that comes from LED/detector spectral response, making the spectrum flatter.
        
        Method:
        1. Fit polynomial to transmission spectrum
        2. Divide transmission by fitted baseline
        3. Re-scale to maintain similar transmission range
        
        Args:
            transmission: Raw transmission spectrum (may have tilt)
            
        Returns:
            Corrected transmission with flattened baseline
        """
        try:
            # Create x-axis for polynomial fit (normalized 0-1)
            x = np.linspace(0, 1, len(transmission))
            
            # Fit polynomial to transmission
            # Use degree 2 (quadratic) by default - captures most spectral tilts
            coeffs = np.polyfit(x, transmission, self.baseline_degree)
            baseline = np.polyval(coeffs, x)
            
            # Avoid division by very small baseline values
            baseline = np.where(baseline < 1.0, 1.0, baseline)
            
            # Divide transmission by baseline to remove tilt
            corrected = transmission / baseline
            
            # Re-scale to maintain similar transmission range
            # Target mean around original mean for consistency
            original_mean = np.nanmean(transmission)
            corrected_mean = np.nanmean(corrected)
            if corrected_mean > 0:
                corrected = corrected * (original_mean / corrected_mean)
            
            logger.debug(f"Baseline correction: mean {original_mean:.1f}% → {np.nanmean(corrected):.1f}%")
            
            return corrected
            
        except Exception as e:
            logger.warning(f"Baseline correction failed: {e}, using raw transmission")
            return transmission
    
    def find_resonance_wavelength(
        self,
        transmission: np.ndarray,
        wavelengths: np.ndarray,
        fourier_weights: np.ndarray = None,
        **kwargs
    ) -> float:
        """Find resonance using Fourier transform method
        
        Algorithm:
        1. Compute Fourier coefficients using DST
        2. Calculate derivative using IDCT
        3. Find zero-crossing of derivative
        4. Refine position using linear regression
        
        Args:
            transmission: Transmission spectrum
            wavelengths: Wavelength array
            fourier_weights: Pre-calculated Fourier weights
            **kwargs: Additional parameters (window_size override)
        """
        try:
            # Allow window_size override
            window_size = kwargs.get('window_size', self.window_size)
            
            # Calculate Fourier weights if not provided
            if fourier_weights is None:
                fourier_weights = self._calculate_fourier_weights(len(transmission))
            elif len(fourier_weights) != len(transmission) - 1:
                # Recalculate if wrong size
                fourier_weights = self._calculate_fourier_weights(len(transmission))
            
            spectrum = transmission
            
            # Calculate Fourier coefficients with denoising
            fourier_coeff = np.zeros_like(spectrum)
            fourier_coeff[0] = 2 * (spectrum[-1] - spectrum[0])
            
            # Apply DST with linear detrending and Fourier weights
            fourier_coeff[1:-1] = fourier_weights * dst(
                spectrum[1:-1] - np.linspace(spectrum[0], spectrum[-1], len(spectrum))[1:-1],
                1,
            )
            
            # Calculate derivative using IDCT
            derivative = idct(fourier_coeff, 1)
            
            # Find zero-crossing (resonance minimum)
            zero = derivative.searchsorted(0)
            
            # Define window around zero-crossing
            start = max(zero - window_size, 0)
            end = min(zero + window_size, len(spectrum) - 1)
            
            # Refine position using linear regression
            line = linregress(wavelengths[start:end], derivative[start:end])
            
            # Calculate resonance wavelength from line intercept
            fit_lambda = -line.intercept / line.slope
            
            return float(fit_lambda)
            
        except Exception as e:
            logger.debug(f"Fourier pipeline error: {e}")
            return np.nan
    
    def _calculate_fourier_weights(self, n: int) -> np.ndarray:
        """Calculate Fourier weights for denoising
        
        Args:
            n: Length of spectrum
            
        Returns:
            Weight array for Fourier coefficients
        """
        n_inner = n - 1
        phi = np.pi / n_inner * np.arange(1, n_inner)
        phi2 = phi**2
        weights = phi / (1 + self.alpha * phi2 * (1 + phi2))
        return weights
