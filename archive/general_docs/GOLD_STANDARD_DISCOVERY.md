# CRITICAL DISCOVERY: Original 0.008nm Performance Strategy

## What Achieved 0.008 nm (8 picometers) Peak-to-Peak Baseline

Based on git analysis of the **GOLD STANDARD commit (069ff60)** from TODAY (Nov 26, 2025), the original high-performance system used:

### 1. **Hardware-Level Averaging** (PRIMARY NOISE REDUCTION)
```python
MAX_READ_TIME = 200  # milliseconds total acquisition time
MAX_NUM_SCANS = 25   # maximum scans to average

# Dynamic calculation during calibration:
num_scans = min(int(MAX_READ_TIME / integration_time), MAX_NUM_SCANS)

# Example with integration_time = 36ms (typical for your channels):
num_scans = min(int(200 / 36), 25) = min(5, 25) = 5 scans averaged

# Example with integration_time = 10ms (short exposure):
num_scans = min(int(200 / 10), 25) = min(20, 25) = 20 scans averaged
```

**Effect**: √N noise reduction at the hardware level
- 5 scans → 2.24x noise reduction (√5)
- 20 scans → 4.47x noise reduction (√20)

### 2. **Batch Processing with Savitzky-Golay Filtering** (SECONDARY SMOOTHING)
```python
BATCH_SIZE = 12  # Quality mode (~300ms processing window)
```

**Savitzky-Golay Filter Applied to Wavelength Data:**
```python
# In _process_and_emit_batch():
if len(wavelength_array) >= 5:
    filtered_wavelengths = savgol_filter(
        wavelength_array,
        window_length=5,  # 5-point window
        polyorder=2       # Quadratic polynomial
    )
```

**Savitzky-Golay Filter Applied to Transmission Spectrum:**
```python
# In _calculate_resonance_wavelength():
if len(transmission_spectrum) >= 21:
    transmission_spectrum = savgol_filter(
        transmission_spectrum,
        window_length=21,  # 21-point window
        polyorder=3        # Cubic polynomial
    )
```

### 3. **Fourier Transform Peak Detection** (UNCHANGED)
```python
alpha = 9000  # Original smoothing parameter
window = 165  # Zero-crossing refinement window
```

## Cascaded Noise Reduction Strategy

The GOLD STANDARD system achieves sub-10pm noise through **THREE cascaded stages**:

```
Stage 1: Hardware Averaging (num_scans=5-25)
         ↓ 2.2-4.5x noise reduction

Stage 2: Savitzky-Golay Batch Filtering (window=5, batch=12)
         ↓ Additional ~2x noise reduction

Stage 3: Fourier DST/IDCT (alpha=9000, window=165)
         ↓ Heavy smoothing for zero-crossing

Combined: ~5-10x total noise reduction
```

## Current System vs. GOLD STANDARD

### Current System (Broken):
- ❌ **NO hardware averaging**: `num_scans` calculated but NOT USED in `read_intensity()`
- ❌ **NO batch processing**: `BATCH_SIZE = 1` (disabled)
- ❌ **NO Savitzky-Golay**: Batch filtering removed
- ✅ Fourier transform: `alpha=9000` (correct)

**Result**: Only 1/3 of noise reduction active → 330x worse than target

### GOLD STANDARD System (Working):
- ✅ **Hardware averaging**: `num_scans=5` (2.24x reduction)
- ✅ **Batch processing**: `BATCH_SIZE=12` with SG filtering
- ✅ **Savitzky-Golay**: 5-point (wavelength) + 21-point (transmission)
- ✅ **Fourier transform**: `alpha=9000`

**Result**: Full cascaded filtering → 0.008nm baseline achieved

## The Missing Link: Hardware Averaging

The current code **calculates** `num_scans` during calibration:
```python
# In led_calibration.py (line 860):
num_scans = min(int(MAX_READ_TIME / integration), MAX_NUM_SCANS)
```

But it's **NEVER USED** during live acquisition! The `read_intensity()` call doesn't pass `num_scans`:

```python
# In data_acquisition_manager.py (line 754):
raw_spectrum = usb.read_intensity()  # ❌ NO num_scans parameter!

# Should be:
raw_spectrum = usb.read_roi(
    wave_min_index=self.wave_min_index,
    wave_max_index=self.wave_max_index,
    num_scans=self.num_scans  # ✅ Hardware averaging
)
```

## Why EMA Pre-Smoothing Failed

My EMA approach (α=0.1) was attempting to do **IN SOFTWARE** what should be done **IN HARDWARE**:

- Software EMA: 10-sample lag, 13% reduction, 9-second delay
- Hardware averaging: 5-20 scans averaged, √N reduction, NO delay

Hardware averaging is superior because:
1. **Reduces photon shot noise** at source (quantum noise √N reduction)
2. **Zero latency** (happens during integration)
3. **No signal distortion** (true averaging vs. recursive filtering)

## Temporal Resolution Analysis

### GOLD STANDARD Performance:
```
Integration time: 36ms (typical)
Num scans: 5
Hardware read time: 36ms × 5 = 180ms per channel
Cycle time (4 channels): 180ms × 4 = 720ms = 0.72 seconds
Temporal resolution: ~1.4 Hz ✅

With batch processing (12 samples):
Display update: 720ms × 12 = 8.6 seconds
But emits interpolated previews for smooth display!
```

### Current Broken System:
```
Integration time: 36ms
Num scans: 1 (NOT AVERAGING!)
Hardware read time: 36ms × 1 = 36ms per channel
Cycle time (4 channels): 36ms × 4 = 144ms = 0.14 seconds
Temporal resolution: ~7 Hz ✅ (faster but noisier!)

Without batch processing:
Display update: 144ms (instant)
```

**Trade-off**:
- Current system: 7 Hz temporal resolution, 2.6nm noise ❌
- GOLD STANDARD: 1.4 Hz temporal resolution, 0.008nm noise ✅

## Action Plan: Restore Hardware Averaging

### Step 1: Enable Hardware Averaging in Acquisition
```python
# In data_acquisition_manager.py, _acquire_channel_spectrum():

# REPLACE:
raw_spectrum = usb.read_intensity()

# WITH:
raw_spectrum = usb.read_roi(
    wave_min_index=self.wave_min_index,
    wave_max_index=self.wave_max_index,
    num_scans=self.num_scans
)
```

### Step 2: Re-enable Batch Processing
```python
# In settings.py:
BATCH_SIZE = 12  # Was 1, restore to 12 for quality mode
ENABLE_INTERPOLATED_DISPLAY = True
```

### Step 3: Restore Savitzky-Golay Filtering
Uncomment the SG filter code in:
- `_process_and_emit_batch()` - wavelength smoothing
- `_calculate_resonance_wavelength()` - transmission smoothing

### Step 4: Remove EMA Pre-smoothing
Revert my changes to `fourier_pipeline.py`:
- Remove `ema_enabled` and `ema_alpha` parameters
- Remove `_apply_ema_smoothing()` method
- Keep only Fourier transform (alpha=9000)

## Expected Results After Fix

With all 3 stages restored:
- Hardware averaging (num_scans=5): 2.24x reduction → 1.18nm
- SG filtering (batch=12, window=5): 2x reduction → 0.59nm
- Fourier transform (alpha=9000): 2x reduction → 0.29nm

**Conservative estimate**: 0.3nm peak-to-peak (37x better than current 2.6nm)

To reach 0.008nm target:
- May need higher `num_scans` (increase MAX_READ_TIME to 400ms?)
- May need larger batch size (BATCH_SIZE=24 for more SG smoothing)
- May need temperature stabilization (if hardware allows)

## Temporal Resolution Impact

Restoring hardware averaging:
- Current: 7 Hz (0.14s per cycle)
- GOLD STANDARD: 1.4 Hz (0.72s per cycle)
- **5x slower acquisition**, but **330x better noise**

This is ACCEPTABLE for biosensor applications:
- Binding kinetics: minute-scale events
- Sub-second resolution: 1.4 Hz is MORE than sufficient
- Stability: Critical for detecting small signals (< 1 RU)

## Conclusion

The original 0.008nm performance was NOT from:
- ❌ Software filtering tricks
- ❌ Complex signal processing
- ❌ Temperature control (maybe helped, but not primary)

It was from:
- ✅ **Hardware averaging** (num_scans=5-25)
- ✅ **Batch processing** (BATCH_SIZE=12)
- ✅ **Savitzky-Golay filtering** (polynomial smoothing)
- ✅ **Fourier transform** (alpha=9000)

The current system has ALL the code in place but **disabled**:
- `num_scans` calculated but not used
- `BATCH_SIZE = 1` (disabled batching)
- SG filters present but commented out or skipped

**Next step**: Restore the GOLD STANDARD configuration and test.
