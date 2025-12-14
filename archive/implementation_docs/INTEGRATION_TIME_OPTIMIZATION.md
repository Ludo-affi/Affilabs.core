# Integration Time Optimization Guide

## Overview

The integration time optimizer finds the **minimum integration time** that maintains your signal quality requirements (<2 RU sensorgram noise) while maximizing acquisition speed.

## Why This Matters

**Current bottleneck breakdown** (per channel):
```
LED activation:       ~50-60ms  (optimized via Phase 1)
Integration time:     ~100ms    ← THIS IS THE TARGET
USB transfer:         ~50ms     (hardware limited)
────────────────────────────────
Total:                ~200-210ms per channel
```

**Opportunity**: Integration time is often **over-specified**. You might be using 100ms when 40ms would give the same quality!

## Physics Background

### Signal-to-Noise Relationship

- **Signal** (S) scales linearly: `S ∝ t_int`
- **Shot noise** (N) scales with √signal: `N ∝ √t_int`
- **SNR** scales as: `SNR ∝ t_int / √t_int = √t_int`

**Key insight**: Halving integration time reduces SNR by only **√2 ≈ 1.41×**, not 2×!

### Example

If you're at 100ms with 10 RU noise:
- 50ms → ~14 RU noise (1.41× worse)
- 25ms → ~20 RU noise (2× worse)

You have **headroom** to trade!

## How The Optimizer Works

### 1. Test Multiple Integration Times

Tests 7 integration times: **20, 30, 40, 50, 60, 80, 100 ms**

For each:
- Takes **100 repeated measurements**
- Measures signal level (mean counts)
- Calculates signal noise (std dev)
- Tracks SPR peak wavelength stability
- Converts to estimated RU noise

### 2. Find Optimal Balance

Selects the **shortest integration time** that keeps RU noise **< 2.0 RU**

### 3. Calculate Speed Gain

Compares:
- **Current setup**: Your existing integration time
- **Optimized setup**: Recommended integration time
- **Speedup factor**: How much faster acquisition will be

## Running The Optimizer

### Prerequisites

1. **Stable SPR conditions**:
   - Equilibrated temperature
   - Stable buffer flow
   - No binding events during test
   - All channels calibrated

2. **Time required**:
   - ~10-15 minutes per channel
   - Test one channel first (usually Channel A)

### Usage

```bash
cd tools
python optimize_integration_time.py
```

### What Happens

1. **Hardware connection**: Connects to controller and spectrometer
2. **Channel testing**: For each integration time:
   - Sets integration time
   - Calculates optimal LED delay (Phase 1)
   - Takes 100 measurements
   - Analyzes signal quality
3. **Analysis**: Finds minimum integration time meeting <2 RU target
4. **Visualization**: Creates plots showing:
   - RU noise vs integration time
   - SNR vs integration time
   - Signal level vs integration time
   - Acquisition rate comparison (current vs optimized)
5. **Results**: Saves to `integration_time_optimization.json`

## Understanding The Results

### Output Files

1. **`integration_time_ch{X}.png`**: Visualization plots
2. **`integration_time_optimization.json`**: Detailed numeric results

### Key Metrics

**For each integration time tested**:
```json
{
  "integration_time_ms": 40.0,
  "led_delay_s": 0.052,
  "mean_signal_counts": 25000.0,
  "std_signal_counts": 45.3,
  "snr": 551.8,
  "mean_peak_nm": 632.456,
  "std_peak_nm": 0.0018,
  "estimated_ru_noise": 1.8
}
```

**What to look for**:
- ✅ `estimated_ru_noise < 2.0` → Meets target
- ✅ `snr > 200` → Good signal quality
- ✅ `mean_signal_counts > 10000` → Not too dim

**RU Conversion Factor**:
The tool uses the system-specific calibration: **1 nm = 355 RU**. This conversion factor is specific to this SPR sensor and has been calibrated for accurate noise estimation.

### Example Results

```
Channel A:
  Optimal integration time: 40.0ms
  Expected RU noise: 1.8 RU
  SNR: 551
  LED delay: 52.0ms

  Speedup: 2.0× FASTER
```

## Applying The Results

### Option 1: Manual Application (Simple)

Edit `settings/settings.py`:

```python
MIN_INTEGRATION = 40  # Was 100ms, now 40ms
```

Then re-run calibration to store this value.

### Option 2: Automatic Application (Advanced - TODO)

Future enhancement: Optimizer could write optimal values directly to device config.

## Per-Channel Optimization

Different channels may have **different optimal integration times**:

- **Bright channels** (high transmission) → Can use shorter times
- **Dim channels** (low transmission) → Need longer times

### Testing Multiple Channels

Modify `tools/optimize_integration_time.py`:

```python
channels_to_test = ['a', 'b', 'c', 'd']  # Test all channels
```

### Storing Per-Channel Times

Future enhancement: Device config could store:

```json
{
  "integration_times_ms": {
    "a": 40,
    "b": 50,
    "c": 45,
    "d": 40
  }
}
```

## Expected Speed Gains

### Conservative Estimate (100ms → 50ms)

**Before** (per 4-channel cycle):
```
4 × (100ms int + 60ms LED + 50ms USB) = 840ms
Rate: 1.19 Hz
```

**After**:
```
4 × (50ms int + 52ms LED + 50ms USB) = 608ms
Rate: 1.64 Hz
Speedup: 1.38× FASTER
```

### Aggressive Estimate (100ms → 40ms)

**Before**: 840ms → 1.19 Hz

**After**:
```
4 × (40ms int + 52ms LED + 50ms USB) = 568ms
Rate: 1.76 Hz
Speedup: 1.48× FASTER
```

### Best Case (100ms → 30ms, if SNR allows)

**Before**: 840ms → 1.19 Hz

**After**:
```
4 × (30ms int + 52ms LED + 50ms USB) = 528ms
Rate: 1.89 Hz
Speedup: 1.59× FASTER (~2× with Phase 1+2)
```

## Troubleshooting

### Issue: No integration time meets <2 RU target

**Possible causes**:
- Unstable conditions during test (temperature drift, bubbles, etc.)
- Poor calibration quality
- Detector noise floor too high

**Solutions**:
- Re-run test under more stable conditions
- Re-calibrate system
- Relax target to <3 RU

### Issue: Signal saturation at shorter times

**Symptom**: Signal doesn't scale linearly with integration time

**Solution**:
- Reduce LED intensity during test
- Optimizer uses calibrated intensity by default

### Issue: Results vary between runs

**Cause**: Intrinsic measurement variability

**Solution**:
- Ensure thermal equilibrium
- Run optimizer twice and average
- Use 200 measurements instead of 100

## Advanced: RU Conversion Factor

The optimizer uses **1 nm ≈ 1000 RU** as a rough estimate. This is:
- ✅ Conservative (safe margin)
- ⚠️ Sensor-dependent (varies by SPR chip)

To calibrate your specific conversion:
1. Run binding assay with known ΔRU
2. Measure actual Δλ (nm)
3. Calculate: `RU/nm = ΔRU / Δλ`

## Integration with Phase 1

Phase 1 (afterglow-based LED delay) and Phase 2 (optimized integration time) work together:

**Phase 1**: LED delay → 50-60ms (was 100ms)
**Phase 2**: Integration time → 30-50ms (was 100ms)
**Combined**: **~100-150ms saved per channel** → **~2× faster acquisition!**

## Next Steps

1. **Run optimizer on Channel A** (most commonly used)
2. **Review plots** - verify RU noise meets target
3. **Apply recommended integration time** to settings
4. **Re-calibrate** to store new parameters
5. **Test in live mode** - verify sensorgram quality
6. **Optimize other channels** if using multi-channel

## Questions?

Check the generated plots:
- **Top-left**: RU noise vs integration time (main decision plot)
- **Top-right**: SNR vs integration time (quality metric)
- **Bottom-left**: Signal level vs integration time (linearity check)
- **Bottom-right**: Acquisition rate comparison (speedup)

The plots tell you everything you need to know! 📊
