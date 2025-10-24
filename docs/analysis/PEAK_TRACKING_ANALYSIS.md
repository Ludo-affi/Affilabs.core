# SPR Peak Tracking Analysis

## Current Implementation (Zero-Crossing Method)

### Algorithm:
1. Calculate derivative of transmittance spectrum: `dT/dλ`
2. Find zero-crossing where derivative changes sign
3. Fit linear regression around zero-crossing
4. Interpolate exact wavelength

### Issues Identified:

**Problem 1: Noise Sensitivity**
- Zero-crossing detection is sensitive to noise in the derivative
- Can find false zero-crossings from spectral features, not the SPR dip
- Many "out of range" warnings in logs (754nm, 729nm, 733nm, etc.)

**Problem 2: Wrong Minima**
- The method finds ANY local minimum, not necessarily the SPR resonance dip
- Without proper spectral features, it picks up noise or other artifacts
- Adaptive range (600-720nm) helps but doesn't solve the core issue

**Problem 3: Derivative Amplifies Noise**
- Even with Savitzky-Golay filtering, derivative calculation amplifies high-frequency noise
- Small spectral artifacts become large derivative spikes
- Zero-crossing becomes ambiguous

## Better Approaches

### Option 1: Direct Minimum Finding (RECOMMENDED)
Find the actual minimum transmission value directly:

```python
def find_resonance_wavelength_direct(
    self,
    spectrum: np.ndarray,
    search_range: tuple[float, float] = (600, 720),
) -> float:
    """Find SPR resonance by locating minimum transmission.

    Simpler and more robust than zero-crossing derivative method.
    Directly finds the wavelength with lowest transmission.
    """
    # Find indices for search range
    start_idx = np.searchsorted(self.wave_data, search_range[0])
    end_idx = np.searchsorted(self.wave_data, search_range[1])

    # Extract search region
    search_spectrum = spectrum[start_idx:end_idx]
    search_wavelengths = self.wave_data[start_idx:end_idx]

    # Find minimum in search region
    min_idx = np.argmin(search_spectrum)

    # Parabolic interpolation for sub-pixel accuracy
    if 0 < min_idx < len(search_spectrum) - 1:
        # Fit parabola through 3 points around minimum
        y = search_spectrum[min_idx-1:min_idx+2]
        x = search_wavelengths[min_idx-1:min_idx+2]

        # Parabolic fit: y = ax² + bx + c
        # Minimum at: x = -b/(2a)
        A = np.vstack([x**2, x, np.ones_like(x)]).T
        coeffs = np.linalg.lstsq(A, y, rcond=None)[0]
        a, b, c = coeffs

        if a > 0:  # Valid parabola (opens upward)
            resonance = -b / (2 * a)
            return resonance

    # Fallback: return wavelength at minimum index
    return search_wavelengths[min_idx]
```

**Advantages:**
- ✅ Directly finds what we care about (minimum transmission)
- ✅ No derivative calculation (no noise amplification)
- ✅ Parabolic interpolation gives sub-pixel accuracy
- ✅ Much simpler and more intuitive
- ✅ Faster (no linear regression, smaller search space)

**Disadvantages:**
- Requires good SNR to avoid noise spikes
- May need pre-smoothing (but we already do Savitzky-Golay filtering)

### Option 2: Gaussian Fitting
Fit a Gaussian (or inverted Gaussian) to the SPR dip:

```python
from scipy.optimize import curve_fit

def gaussian_dip(x, amplitude, center, width, offset):
    """Inverted Gaussian for SPR dip."""
    return offset - amplitude * np.exp(-((x - center) ** 2) / (2 * width ** 2))

def find_resonance_gaussian(self, spectrum, search_range=(600, 720)):
    """Fit Gaussian to SPR dip for robust peak tracking."""
    start_idx = np.searchsorted(self.wave_data, search_range[0])
    end_idx = np.searchsorted(self.wave_data, search_range[1])

    x = self.wave_data[start_idx:end_idx]
    y = spectrum[start_idx:end_idx]

    # Initial guess
    min_idx = np.argmin(y)
    p0 = [
        np.max(y) - np.min(y),  # amplitude
        x[min_idx],              # center
        10.0,                    # width (nm)
        np.max(y),               # offset
    ]

    try:
        popt, _ = curve_fit(gaussian_dip, x, y, p0=p0, maxfev=1000)
        return popt[1]  # center wavelength
    except:
        return x[min_idx]  # fallback
```

**Advantages:**
- ✅ Very robust to noise
- ✅ Physical model of SPR resonance
- ✅ Can extract width and depth information
- ✅ Handles asymmetric peaks well

**Disadvantages:**
- ❌ Slower (iterative fitting)
- ❌ May fail to converge for poor data
- ❌ Requires good initial guess

### Option 3: Hybrid Approach
Combine minimum finding with validation:

1. Find coarse minimum in search range
2. Verify it's a valid SPR dip (check depth, width)
3. Apply parabolic interpolation for precision
4. If validation fails, fall back to zero-crossing method

## Recommendation

**Implement Option 1 (Direct Minimum Finding) first:**

1. **Replace** zero-crossing method with direct minimum finding
2. **Keep** Savitzky-Golay denoising for spectroscopy view
3. **Skip** denoising for sensorgram (O2 optimization still applies)
4. **Use** parabolic interpolation for sub-pixel accuracy
5. **Add** validation checks (depth, width, position)

**Expected Improvements:**
- 🎯 More accurate peak tracking (fewer "out of range" warnings)
- ⚡ Faster (~2-3ms saved by avoiding derivative + linear regression)
- 🛡️ More robust to noise and artifacts
- 📊 Cleaner sensorgram data

## Implementation Priority

**Phase 1 (Immediate):**
- ✅ Implement direct minimum finding with parabolic interpolation
- ✅ Add validation checks
- ✅ Test with real data

**Phase 2 (Optional):**
- Add Gaussian fitting as alternative for noisy data
- Compare accuracy of both methods
- Make method selectable via settings

**Phase 3 (Future):**
- Implement predictive tracking (Kalman filter on peak position)
- Add outlier rejection (remove bad peaks from sensorgram)
- Machine learning approach for difficult samples
