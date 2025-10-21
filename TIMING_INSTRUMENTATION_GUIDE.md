# Timing Instrumentation Guide

## 🎯 Purpose

Comprehensive performance profiling added to identify and quantify overhead sources in the SPR data acquisition pipeline. This replaces speculation with empirical data to guide optimization priorities.

## ⏱️ What's Being Measured

### Per-Channel Timing (logged for each channel a,b,c,d)

```
⏱️ TIMING ch=a: LED_on=2ms, LED_settle=50ms, scan=210ms, dark=15ms, trans=8ms, peak=3ms, TOTAL=288ms
```

**Breakdown:**
1. **LED_on** (1-5ms): Time to activate LED via serial command
   - Includes: Serial communication, command parsing
   - Expected: <5ms (batch control), 10-20ms (sequential)

2. **LED_settle** (0-100ms): Stabilization delay after LED activation
   - Value from settings: `LED_DELAY` (default 50ms)
   - Expected: 50ms (new software), 100ms (old software)

3. **scan** (100-300ms): Spectrum acquisition and averaging
   - Includes: N scans × integration time + USB transfer overhead
   - Expected: ~200ms for 4×50ms or 2×100ms scans
   - Critical bottleneck if >250ms

4. **dark** (5-30ms): Dark noise correction and interpolation
   - Includes: Array operations, scipy interpolation if size mismatch
   - Expected: <20ms
   - Can be high (30ms) if scipy interpolation needed

5. **trans** (5-15ms): Transmittance calculation (P/S ratio)
   - Includes: Array division, denoising (if enabled)
   - Expected: <10ms with denoising disabled

6. **peak** (1-15ms): Resonance wavelength detection
   - Centroid method: 1-2ms
   - Enhanced method: 10-15ms
   - Parabolic method: 0.5-1ms

### Per-Cycle Timing (logged after all 4 channels)

```
⏱️ CYCLE #5: total=1520ms, emit=45ms, acq=1475ms
```

**Breakdown:**
1. **total**: Complete cycle time (all 4 channels + GUI emission)
   - Target: <1200ms to match old software
   - Current: ~1600ms

2. **emit**: Time to emit data to GUI (Qt signals)
   - Sensorgram data: lightweight (~5-10ms)
   - Spectroscopy data: heavy arrays (~40-80ms)
   - Optimization: Throttle spectroscopy to every 3rd cycle

3. **acq**: Pure acquisition time (total - emit)
   - Expected: 4 channels × ~300ms = ~1200ms
   - If >1400ms, indicates channel-level bottleneck

### Statistical Summary (every 10 cycles)

```
📊 TIMING STATS (last 10 cycles): avg=1520ms, min=1480ms, max=1650ms, rate=0.66 Hz
```

**Metrics:**
- **avg**: Average cycle time (target <1200ms)
- **min/max**: Variability indicates jitter sources
- **rate**: Update frequency (target >0.9 Hz to match old software)

## 🔧 Configuration

### Enable/Disable Timing Logs

```python
# In utils/spr_data_acquisition.py __init__
self.enable_timing_logs = True   # Set to False to disable
```

### Timing Data Storage

```python
self.timing_samples = []  # All cycle times (ms) for analysis
self.cycle_count = 0      # Total cycles completed
```

### Access Timing Data Programmatically

```python
# Get last 100 cycle times
recent_times = acquisition.timing_samples[-100:]

# Calculate statistics
avg_time = np.mean(recent_times)
std_time = np.std(recent_times)
p95_time = np.percentile(recent_times, 95)

# Estimate achievable rate
target_rate = 1000 / avg_time  # Hz
```

## 📊 Interpretation Guide

### Identifying Bottlenecks

#### 1. LED Activation Too Slow (>10ms)
```
LED_on=25ms  ❌  Slow serial communication
```
**Possible causes:**
- Sequential LED control (not using batch commands)
- USB-serial latency
- Serial buffer full

**Solutions:**
- Use batch LED control: `set_batch_intensities()`
- Check USB cable quality
- Increase serial baud rate

#### 2. LED Settle Time Excessive (>60ms)
```
LED_settle=100ms  ⚠️  Could be reduced
```
**Analysis:**
- Old software: 100ms (conservative)
- New software default: 50ms
- With afterglow correction: Could be 20-30ms

**Solutions:**
- Enable afterglow correction (if optical calibration available)
- Test lower values (30ms, 20ms) and check noise
- Set to 0ms if using first-integration overlap method

#### 3. Scan Time Too High (>250ms)
```
scan=310ms  ❌  70ms overhead per channel!
```
**Possible causes:**
- USB wrapper overhead (Python layers)
- Spectrometer USB transfer delays
- Too many scans

**Expected times:**
```
4 scans × 50ms = 200ms integration
+ 10-30ms USB overhead
= 210-230ms target

2 scans × 100ms = 200ms integration
+ 5-15ms USB overhead
= 205-215ms target (BETTER - less loop overhead)
```

**Solutions:**
- Implement fast-path USB read (bypass Python wrappers)
- Use detector-level averaging if hardware supports it
- Optimize `_acquire_averaged_spectrum()` method

#### 4. Dark Correction Slow (>25ms)
```
dark=35ms  ⚠️  Interpolation overhead
```
**Possible causes:**
- Size mismatch requiring scipy interpolation
- Multiple array copies
- Complex reshaping logic

**Solutions:**
- Pre-resample dark noise during calibration
- Use simple broadcasting instead of interpolation
- Cache interpolated dark noise

#### 5. GUI Emission Excessive (>50ms)
```
emit=85ms  ❌  Heavy data transfer to GUI
```
**Possible causes:**
- Emitting full spectra every cycle (1024+ points × 4 channels)
- Qt signal overhead with large arrays
- GUI thread processing backlog

**Solutions:**
- Throttle spectroscopy emissions (every 3rd cycle)
- Emit only sensorgram data (wavelength values) most cycles
- Use Qt queued connections to batch emissions

### Target Timing Profiles

#### Current (Baseline - 1.6s cycle)
```
Per channel: LED_on=3ms, LED_settle=50ms, scan=220ms, dark=20ms, trans=10ms, peak=2ms = 305ms
4 channels: 1220ms
GUI emit: 80ms (full spectra every cycle)
Total: 1300ms
Unexplained: 300ms ❌
```

#### Optimized (Target - 1.1s cycle)
```
Per channel: LED_on=2ms, LED_settle=50ms, scan=205ms, dark=10ms, trans=8ms, peak=2ms = 277ms
4 channels: 1108ms
GUI emit: 25ms (throttled, every 3rd cycle avg)
Total: 1133ms
Rate: 0.88 Hz ✅
```

#### Aggressive (Stretch - 0.9s cycle)
```
Per channel: LED_on=2ms, LED_settle=20ms, scan=180ms, dark=8ms, trans=8ms, peak=1ms = 219ms
4 channels: 876ms
GUI emit: 20ms
Total: 896ms
Rate: 1.12 Hz 🚀
```

## 🎯 Using Timing Data for Optimization

### Step 1: Run Application and Collect Data

```bash
# Start application with timing enabled (default)
python run_app.py

# Let it run for 60-120 seconds (40-80 cycles)
# Timing logs will appear in console
```

### Step 2: Analyze Bottlenecks

Look for patterns in the logs:

```
⏱️ TIMING ch=a: LED_on=3ms, LED_settle=50ms, scan=250ms, dark=18ms, trans=9ms, peak=2ms, TOTAL=332ms
⏱️ TIMING ch=b: LED_on=2ms, LED_settle=50ms, scan=245ms, dark=17ms, trans=8ms, peak=2ms, TOTAL=324ms
⏱️ TIMING ch=c: LED_on=3ms, LED_settle=50ms, scan=255ms, dark=19ms, trans=9ms, peak=2ms, TOTAL=338ms
⏱️ TIMING ch=d: LED_on=2ms, LED_settle=50ms, scan=248ms, dark=18ms, trans=8ms, peak=2ms, TOTAL=328ms
⏱️ CYCLE #1: total=1580ms, emit=75ms, acq=1505ms
```

**Analysis:**
- Scan time is 45-55ms above target (250ms vs 205ms) ❌
  - 50ms × 4 channels = 200ms extra per cycle
  - **PRIMARY BOTTLENECK**

- Emit time is 75ms (should be <50ms) ⚠️
  - 25ms × 4 channels (if throttled) = 100ms saved
  - **SECONDARY OPTIMIZATION**

- LED settle is 50ms (conservative, could reduce) ⏸️
  - 30ms reduction × 4 channels = 120ms potential savings
  - **TERTIARY OPTIMIZATION** (requires validation)

**Total potential savings: 200 + 25 + 120 = 345ms**
**New cycle time: 1580 - 345 = 1235ms (close to 1.1s target!) ✅**

### Step 3: Prioritize Optimizations

Based on timing data, implement in order:

1. **Optimize scan time** (200ms savings) ⭐⭐⭐⭐⭐
   - Implement fast-path USB read
   - Add `acquire_averaged_spectrum()` to HAL

2. **Throttle GUI emissions** (100ms savings) ⭐⭐⭐⭐
   - Emit spectroscopy data every 3rd cycle only

3. **Reduce LED settle** (120ms savings) ⭐⭐⭐
   - Test 30ms delay (requires noise validation)
   - Enable afterglow correction

### Step 4: Measure Improvement

After each optimization:

```python
# Before: avg=1580ms
# After optimization 1: avg=1380ms (200ms improvement ✅)
# After optimization 2: avg=1280ms (100ms improvement ✅)
# After optimization 3: avg=1160ms (120ms improvement ✅)
```

## 📁 Log File Analysis

### Export Timing Data for Analysis

```python
# After running for several minutes
import json
from datetime import datetime

# Save timing samples
timing_data = {
    'timestamp': datetime.now().isoformat(),
    'cycle_count': acquisition.cycle_count,
    'samples_ms': acquisition.timing_samples,
    'settings': {
        'integration_time_ms': 50.0,
        'num_scans': 4,
        'led_delay': 0.05,
        'peak_method': 'centroid'
    }
}

with open('timing_analysis.json', 'w') as f:
    json.dump(timing_data, f, indent=2)
```

### Visualize Timing Distribution

```python
import matplotlib.pyplot as plt
import numpy as np

times = np.array(acquisition.timing_samples)

plt.figure(figsize=(12, 6))

# Histogram
plt.subplot(1, 2, 1)
plt.hist(times, bins=50, edgecolor='black')
plt.axvline(times.mean(), color='red', linestyle='--', label=f'Mean: {times.mean():.1f}ms')
plt.axvline(1100, color='green', linestyle='--', label='Target: 1100ms')
plt.xlabel('Cycle Time (ms)')
plt.ylabel('Frequency')
plt.title('Cycle Time Distribution')
plt.legend()

# Time series
plt.subplot(1, 2, 2)
plt.plot(times)
plt.axhline(times.mean(), color='red', linestyle='--', label=f'Mean: {times.mean():.1f}ms')
plt.axhline(1100, color='green', linestyle='--', label='Target: 1100ms')
plt.xlabel('Cycle Number')
plt.ylabel('Cycle Time (ms)')
plt.title('Cycle Time Over Time')
plt.legend()

plt.tight_layout()
plt.savefig('timing_analysis.png', dpi=150)
plt.show()
```

## 🚀 Quick Start

### 1. Enable Timing (Already Default)

Timing is enabled by default. Check `utils/spr_data_acquisition.py` line ~203:

```python
self.enable_timing_logs = True  # ✅ Already enabled
```

### 2. Run Application

```bash
python run_app.py
```

### 3. Observe Console Output

You'll see detailed timing for each channel and cycle:

```
⏱️ TIMING ch=a: LED_on=3ms, LED_settle=50ms, scan=215ms, dark=12ms, trans=8ms, peak=2ms, TOTAL=290ms
⏱️ TIMING ch=b: LED_on=2ms, LED_settle=50ms, scan=218ms, dark=13ms, trans=7ms, peak=2ms, TOTAL=292ms
⏱️ TIMING ch=c: LED_on=3ms, LED_settle=50ms, scan=220ms, dark=12ms, trans=8ms, peak=2ms, TOTAL=295ms
⏱️ TIMING ch=d: LED_on=2ms, LED_settle=50ms, scan=216ms, dark=13ms, trans=8ms, peak=2ms, TOTAL=291ms
⏱️ CYCLE #1: total=1450ms, emit=62ms, acq=1388ms
```

### 4. Wait for Statistics (Every 10 Cycles)

```
📊 TIMING STATS (last 10 cycles): avg=1455ms, min=1420ms, max=1510ms, rate=0.69 Hz
```

### 5. Identify Bottleneck

Compare your numbers to expected values in this guide.

## 📝 Implementation Details

### Code Locations

**Timing setup:**
- File: `utils/spr_data_acquisition.py`
- Lines: ~3 (import perf_counter), ~203-206 (init variables)

**Per-channel timing:**
- File: `utils/spr_data_acquisition.py`
- Method: `_read_channel_data()`
- Lines: ~425-705 (complete method with timing points)

**Per-cycle timing:**
- File: `utils/spr_data_acquisition.py`
- Method: `grab_data()` main loop
- Lines: ~360-410 (cycle loop with timing)

### Timing Precision

Uses `time.perf_counter()`:
- **Resolution**: ~100 nanoseconds on Windows
- **Monotonic**: Not affected by system clock changes
- **Overhead**: <1 microsecond per call (negligible)

### Performance Impact

Timing instrumentation adds minimal overhead:
- Per-channel: ~7 perf_counter() calls = ~7µs
- Per-cycle: ~3 perf_counter() calls = ~3µs
- Logging: ~2ms per log statement (only when enabled)
- **Total impact**: <10ms per cycle (<1% overhead)

Can be disabled by setting `self.enable_timing_logs = False`

## 🎯 Success Criteria

After optimization guided by timing data:

✅ **Cycle time**: <1200ms (matching old software)
✅ **Update rate**: >0.83 Hz (1200ms = 0.83 Hz)
✅ **Variability**: <100ms std deviation (consistent performance)
✅ **GUI responsiveness**: emit time <30ms average

Stretch goals:
🎯 **Cycle time**: <1000ms (beating old software!)
🎯 **Update rate**: >1.0 Hz
🎯 **Variability**: <50ms std deviation

---

**Status**: Timing instrumentation implemented and ready for use
**Next Step**: Run application, collect data, analyze bottlenecks, implement optimizations
**Expected outcome**: Identify 300-400ms of overhead for optimization
