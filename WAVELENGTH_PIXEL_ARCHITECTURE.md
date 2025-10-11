# Clean Wavelength/Pixel Architecture

## The Problem We Solved

### Before (Confusing!)
```python
# What does wave_min_index mean?
wave_min_index = 0          # Index into... filtered array? Full array?
wave_max_index = 1590       # Same confusion!

# Using indices - semantic confusion
int_data = reading[wave_min_index:wave_max_index]  # Wrong if full spectrum!
```

**Issues:**
- ❌ `wave_min_index=0` could mean:
  - Index 0 of filtered array (580nm)?
  - Index 0 of full array (441nm)?
  - Something else?
- ❌ Fallback used wrong indices on full spectrum
- ❌ Mixing "index" and "wavelength" concepts

### After (Clean!)
```python
# Crystal clear - always use actual wavelength values
MIN_WAVELENGTH = 580  # nm
MAX_WAVELENGTH = 720  # nm

# Create mask based on wavelengths - always correct!
mask = (wavelengths >= MIN_WAVELENGTH) & (wavelengths <= MAX_WAVELENGTH)
filtered_data = full_spectrum[mask]
```

**Benefits:**
- ✅ Always uses actual wavelength values (no ambiguity)
- ✅ Works regardless of spectrum size (3647 or 3648 pixels)
- ✅ No confusion about which "index 0" we mean
- ✅ Self-documenting code

## Architecture Changes

### 1. Calibration State (utils/spr_calibrator.py)

**Old (Confusing):**
```python
self.state.wave_min_index = 0          # Index into filtered array
self.state.wave_max_index = 1590       # Last index of filtered array
```

**New (Clear):**
```python
# Store actual wavelength boundaries
self.state.wavelength_min = 580.0  # nm (clear!)
self.state.wavelength_max = 720.0  # nm (clear!)

# Store filtered wavelength array
self.state.wave_data = filtered_wavelengths  # 580-720nm

# Store full detector wavelengths for mask creation
self.state.full_wavelengths = full_wavelengths  # 441-773nm
```

**Deprecated (kept for compatibility):**
```python
# These are always 0 and len-1 for filtered data - not useful!
self.state.wave_min_index = 0
self.state.wave_max_index = len(filtered_data) - 1
```

### 2. Data Acquisition (utils/spr_data_acquisition.py)

**Old (Dangerous Fallback):**
```python
try:
    mask = create_mask(...)
    data = reading[mask]
except:
    # WRONG! Uses indices meant for filtered array on full array
    data = reading[self.wave_min_index:self.wave_max_index]
```

**New (Fail Explicitly):**
```python
try:
    # Get current wavelengths from detector
    wavelengths = self.usb.get_wavelengths()

    # Create mask using actual wavelength boundaries
    mask = (wavelengths >= MIN_WAVELENGTH) & (wavelengths <= MAX_WAVELENGTH)
    data = reading[mask]

except:
    # Don't fall back to wrong behavior - fail explicitly!
    logger.error("Cannot get wavelengths - spectral filtering impossible")
    raise RuntimeError("Wavelength data required for correct operation")
```

### 3. Helper Module (utils/wavelength_manager.py)

New clean API for wavelength/pixel management:

```python
from utils.wavelength_manager import SpectralFilter

# Initialize filter
filter = SpectralFilter(min_wavelength=580, max_wavelength=720)

# Calibrate with full detector wavelengths
spr_range = filter.calibrate(full_detector_wavelengths)

# Filter any spectrum
filtered_wl, filtered_data = filter.filter(full_spectrum)

# Validate alignment
filter.validate_alignment(s_reference, p_mode, "S-ref", "P-mode")
```

## Benefits of Clean Architecture

### 1. No Semantic Confusion
```python
# OLD: What does this mean?
data = reading[0:1590]  # Index 0 of what? Filtered? Full?

# NEW: Crystal clear
mask = (wavelengths >= 580) & (wavelengths <= 720)  # Obvious!
data = reading[mask]
```

### 2. Size-Independent
```python
# Works automatically for 3647 OR 3648 pixels
wavelengths = detector.get_wavelengths()  # Could be any size
mask = (wavelengths >= 580) & (wavelengths <= 720)  # Still correct!
```

### 3. Self-Documenting
```python
# OLD: Need to look up what indices mean
reading[wave_min_index:wave_max_index]

# NEW: Code explains itself
reading[(wavelengths >= 580) & (wavelengths <= 720)]
```

### 4. Fail-Safe
```python
# OLD: Falls back to wrong behavior
try:
    # Try correct method
except:
    # Use wrong indices - silently corrupts data!
    data = reading[0:1590]

# NEW: Fails explicitly if something is wrong
try:
    # Correct method
except:
    # Fail loudly - don't corrupt data silently!
    raise RuntimeError("Cannot proceed without wavelengths")
```

## Usage Examples

### Example 1: Calibration
```python
from utils.wavelength_manager import SpectralFilter

# Get full detector wavelengths
full_wavelengths = usb.get_wavelengths()  # 3648 points, 441-773nm

# Create filter
filter = SpectralFilter(min_wavelength=580, max_wavelength=720)
spr_range = filter.calibrate(full_wavelengths)

print(spr_range)
# Output: WavelengthRange(580.0-720.0 nm, 1591 pixels, 0.088 nm/px)

# Store for use during acquisition
state.spr_range = spr_range
```

### Example 2: Filtering During Acquisition
```python
# Read full spectrum from detector
full_spectrum = usb.read_intensity()  # 3648 points
full_wavelengths = usb.get_wavelengths()  # 3648 points

# Filter to SPR range
filtered_wl, filtered_data = filter.filter(full_spectrum, full_wavelengths)

# Now filtered_wl starts at 580nm, filtered_data has ~1591 points
print(f"Filtered: {filtered_wl[0]:.1f} - {filtered_wl[-1]:.1f} nm")
# Output: Filtered: 580.1 - 720.0 nm
```

### Example 3: Validation
```python
# Measure S-mode reference
s_ref_wl, s_ref_data = filter.filter(s_spectrum, s_wavelengths)

# Measure P-mode
p_mode_wl, p_mode_data = filter.filter(p_spectrum, p_wavelengths)

# Validate they're aligned
if filter.validate_alignment(s_ref_data, p_mode_data, "S-ref", "P-mode"):
    # Safe to calculate transmittance
    transmittance = p_mode_data / s_ref_data
else:
    # Misalignment detected!
    logger.error("Cannot calculate transmittance - data misaligned")
```

## Migration Guide

### For Existing Code

If you see this pattern:
```python
# OLD
data = reading[self.wave_min_index:self.wave_max_index]
```

Replace with:
```python
# NEW
wavelengths = self.usb.get_wavelengths()[:len(reading)]
mask = (wavelengths >= MIN_WAVELENGTH) & (wavelengths <= MAX_WAVELENGTH)
data = reading[mask]
```

### For Calibration State

Old attributes (deprecated but kept):
- `state.wave_min_index` → Always 0 (useless)
- `state.wave_max_index` → Always len-1 (useless)

New attributes (use these):
- `state.wavelength_min` → 580.0 (clear!)
- `state.wavelength_max` → 720.0 (clear!)
- `state.wave_data` → Filtered wavelength array
- `state.full_wavelengths` → Full detector wavelengths

## Summary

### Old Way: Index-Based (Confusing) ❌
- Stored indices (0, 1590)
- Ambiguous meaning
- Broke when used on wrong array
- Hard to debug

### New Way: Wavelength-Based (Clear) ✅
- Stores actual wavelengths (580nm, 720nm)
- Unambiguous meaning
- Always works correctly
- Self-documenting

**Result**: Code is clearer, safer, and more maintainable!

---

**Files Modified:**
- `utils/spr_calibrator.py` - Store wavelength boundaries instead of indices
- `utils/spr_data_acquisition.py` - Remove dangerous index fallback
- `utils/wavelength_manager.py` - New clean API (NEW FILE)
- `WAVELENGTH_PIXEL_ARCHITECTURE.md` - This documentation (NEW FILE)
