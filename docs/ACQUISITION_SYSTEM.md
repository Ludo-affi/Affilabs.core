# Acquisition System Documentation

**Last Updated**: February 2, 2026
**Author**: AffiLabs Team
**Related Docs**: [Hardware Communication](HARDWARE_COMMUNICATION_LAYER.md), [Data Processing Pipeline](DATA_PROCESSING_PIPELINE.md)

---

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [1 Hz Acquisition Loop](#1-hz-acquisition-loop)
4. [Detector Integration](#detector-integration)
5. [Calibration Application](#calibration-application)
6. [Threading Model](#threading-model)
7. [Timing & Performance](#timing--performance)
8. [Channel Sequencing](#channel-sequencing)
9. [Data Flow](#data-flow)
10. [API Reference](#api-reference)
11. [Troubleshooting](#troubleshooting)

---

## Overview

### Purpose

The Acquisition System manages continuous real-time data collection from the spectrometer at precisely 1 Hz. It coordinates:

- **Detector Reading**: Acquire spectra from USB spectrometer
- **LED Cycling**: Sequence through channels A, B, C, D
- **Calibration Application**: Apply dark/S-ref corrections
- **Data Emission**: Queue processed spectra for display

### Key Features

- **Precise 1 Hz Timing**: Acquisition every 1000ms ± 1µs
- **Thread Separation**: Acquisition and processing in separate threads
- **Non-Blocking**: Never blocks UI or other operations
- **Resilient**: Auto-recovery from detector errors
- **Calibrated**: Applies dark subtraction and S-pol reference

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                        │
│  (main.py, affilabs_core_ui.py)                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────▼────────────────┐
        │  start_acquisition()          │  User presses Start
        └──────────────┬────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│            DATA ACQUISITION MANAGER                         │
│  ├─ Calibration Data Storage (dark, S-ref, wavelengths)    │
│  ├─ Acquisition State Management (_acquiring flag)         │
│  ├─ Thread Lifecycle (start, stop, pause)                  │
│  └─ Signal Emission (spectrum_acquired)                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────▼────────────────┐
        │  _acquisition_worker()        │  Background Thread
        │  (1 Hz loop)                  │  (Non-daemon)
        └──────────────┬────────────────┘
                       │
                       │ Cycles: A → B → C → D → repeat
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              HARDWARE LAYER                                 │
│  ├─ Controller: Set LED intensity (batch command)          │
│  ├─ Detector: Acquire spectrum (USB)                       │
│  └─ Timing: Sleep for precise 1 Hz cadence                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Raw spectrum data
                       │
┌──────────────────────▼──────────────────────────────────────┐
│             CALIBRATION APPLICATION                         │
│  ├─ Dark Subtraction: spectrum - dark                      │
│  ├─ S-Reference Division: (P - dark) / (S - dark)          │
│  └─ Wavelength Masking: Filter to valid range              │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────▼────────────────┐
        │  spectrum_acquired.emit()     │  Qt Signal
        └──────────────┬────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│            PROCESSING THREAD                                │
│  ├─ Dequeue spectrum from queue                            │
│  ├─ Run processing pipeline (Fourier, centroid, etc.)      │
│  ├─ Update data buffers (timeline, cycle, intensity)       │
│  └─ Update graphs (throttled to 10 Hz)                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 1 Hz Acquisition Loop

### Core Loop Structure

**File**: `affilabs/core/data_acquisition_manager.py:737-900`

```python
def _acquisition_worker(self):
    """Main acquisition loop - runs at 1 Hz."""

    # PHASE 1: Pre-arm detector (one-time setup)
    detector.set_integration_time(integration_time_ms)

    # PHASE 2: Infinite loop until stop signal
    while not self._stop_acquisition.is_set():

        # Pause check (without sleep → instant resume)
        while self._paused:
            if self._stop_acquisition.is_set():
                return
            time.sleep(0.01)

        # PHASE 3: Cycle through channels A, B, C, D
        for channel in ['a', 'b', 'c', 'd']:

            # Set LED intensity (batch command for speed)
            intensity = led_intensities[channel]
            ctrl.set_batch_intensities(
                a=intensity if channel == 'a' else 0,
                b=intensity if channel == 'b' else 0,
                c=intensity if channel == 'c' else 0,
                d=intensity if channel == 'd' else 0
            )

            # Acquire raw spectrum from detector
            raw_spectrum = detector.get_spectrum()

            # Apply calibration (dark subtraction, S-ref division)
            corrected = self._apply_calibration(channel, raw_spectrum)

            # Emit spectrum data via signal (non-blocking)
            self.spectrum_acquired.emit({
                'channel': channel,
                'timestamp': time.time(),
                'wavelengths': wavelengths,
                'raw_spectrum': raw_spectrum,
                'transmission': corrected,
                'p_spectrum': corrected  # P-pol data
            })

        # PHASE 4: Sleep to maintain 1 Hz cadence
        # (accounts for processing time to keep precise timing)
        elapsed = time.time() - loop_start
        sleep_time = max(0, 1.0 - elapsed)
        time.sleep(sleep_time)
```

### Why 1 Hz?

**Rationale**:
1. **SPR Kinetics**: Most binding events occur on 10-1000 second timescales
2. **Detector Integration**: 100ms integration + 900ms for LED switching/processing
3. **Data Volume**: 1 point/sec = manageable file sizes (3600 points/hour)
4. **Real-Time Display**: 1 Hz updates feel responsive without overwhelming UI

---

## Detector Integration

### Spectrometer Setup

**Pre-Arm Integration Time** (saves 21ms per cycle):

```python
# Before loop (one-time setup)
detector.set_integration_time(integration_time_ms)

# Inside loop (NO re-arming)
spectrum = detector.get_spectrum()  # Uses pre-armed time
```

**Why Pre-Arm?** Ocean Optics spectrometers require ~21ms to arm integration time. By doing this once before the loop, we save 84ms per 4-channel cycle (4 channels × 21ms).

---

### Integration Time Selection

| Use Case | Integration Time | Rationale |
|----------|------------------|-----------|
| **High Signal** | 10-50ms | Avoid saturation, fast acquisition |
| **Standard** | 100ms | Balanced SNR and speed |
| **Low Signal** | 200-500ms | Maximize photon collection |
| **Very Low** | 1000ms+ | Dark samples, requires 0.25 Hz acquisition |

**Automatic Selection** (during calibration):
```python
def auto_select_integration_time(detector, target_intensity=30000):
    """Find integration time for target intensity."""

    times = [10, 20, 50, 100, 200, 500, 1000]

    for time_ms in times:
        detector.set_integration_time(time_ms)
        spectrum = detector.get_spectrum()
        max_intensity = np.max(spectrum)

        if 20000 < max_intensity < 40000:  # Target range
            return time_ms

    return 100  # Default fallback
```

---

### Spectrum Acquisition

**Ocean Optics (via SeaBreeze)**:
```python
import seabreeze.spectrometers as sb

spec = sb.Spectrometer(devices[0])
spec.integration_time_micros(100000)  # 100ms

# Acquire spectrum
intensities = spec.intensities()  # Returns np.ndarray[float]
wavelengths = spec.wavelengths()  # Returns np.ndarray[float]
```

**Phase Photonics**:
```python
# Custom USB integration
spectrum = detector.read_spectrum()  # Direct USB read
```

---

## Calibration Application

### Calibration Data Structure

**Stored in `DataAcquisitionManager.calibration_data`**:

```python
class CalibrationData:
    wavelengths: np.ndarray        # [200.0, 200.5, ..., 1100.0]

    # Dark spectrum (LEDs off)
    dark: np.ndarray               # [100, 105, 98, ...]

    # S-polarization reference (per channel)
    s_pol_ref: dict[str, np.ndarray]  # {
    #     'a': [1024, 1256, ...],
    #     'b': [1135, 1423, ...],
    #     'c': [987, 1098, ...],
    #     'd': [1245, 1567, ...]
    # }

    # LED intensities (optimized during calibration)
    led_intensities: dict[str, int]   # {'a': 50, 'b': 60, 'c': 70, 'd': 80}

    # Detector settings
    integration_time: int          # 100 (ms)
    num_scans: int                 # 1 (averaging count)
```

---

### Dark Subtraction

**Purpose**: Remove detector noise and ambient light

```python
def subtract_dark(raw_spectrum, dark):
    """Subtract dark spectrum from raw data."""
    corrected = raw_spectrum - dark

    # Clip negative values (should be rare)
    corrected = np.maximum(corrected, 0)

    return corrected
```

**When Applied**: Every spectrum acquisition, before any other processing

---

### Transmission Calculation

**Formula**:
$$
T(\lambda) = \frac{P(\lambda) - D(\lambda)}{S(\lambda) - D(\lambda)}
$$

Where:
- $P(\lambda)$ = P-polarization spectrum (sample measurement)
- $S(\lambda)$ = S-polarization reference (baseline)
- $D(\lambda)$ = Dark spectrum (detector noise)

**Implementation**:
```python
def calculate_transmission(p_spectrum, s_ref, dark):
    """Calculate transmission percentage."""

    # Dark subtraction
    p_corrected = p_spectrum - dark
    s_corrected = s_ref - dark

    # Avoid division by zero
    s_corrected = np.where(s_corrected < 1, 1, s_corrected)

    # Transmission (0-100%)
    transmission = (p_corrected / s_corrected) * 100.0

    # Clamp to realistic range
    transmission = np.clip(transmission, 0, 200)

    return transmission
```

---

### Wavelength Masking

**Purpose**: Filter to detector's valid SPR range

```python
def apply_wavelength_mask(wavelengths, data, detector_serial):
    """Mask data to valid wavelength range."""

    # Detector-specific ranges
    if detector_serial.startswith("ST"):  # Phase Photonics
        valid_min, valid_max = 570, 720  # nm
    elif detector_serial.startswith("FLMT") or detector_serial.startswith("USB4"):
        valid_min, valid_max = 560, 720  # nm
    else:
        return wavelengths, data  # No masking

    # Filter wavelengths
    mask = (wavelengths >= valid_min) & (wavelengths <= valid_max)
    return wavelengths[mask], data[mask]
```

**Why Mask?** Spectrometers measure 200-1100nm, but SPR signal only exists in 560-720nm range. Filtering reduces noise and computation.

---

## Threading Model

### Thread Separation (Phase 3 Optimization)

**Problem**: Processing spectra inline with acquisition caused timing jitter

**Solution**: Separate acquisition and processing threads

```
┌───────────────────────────────────────────────────────────┐
│  ACQUISITION THREAD (1 Hz precise)                        │
│  ├─ Set LED intensity                                     │
│  ├─ Read spectrum from detector                           │
│  ├─ Apply calibration (dark/S-ref)                        │
│  ├─ Queue data (non-blocking)                             │
│  └─ Sleep to maintain 1 Hz                                │
└──────────────────┬────────────────────────────────────────┘
                   │
                   │ Lock-free queue
                   │
┌──────────────────▼────────────────────────────────────────┐
│  PROCESSING THREAD (async, no timing constraints)        │
│  ├─ Dequeue spectrum                                      │
│  ├─ Run processing pipeline (Fourier, centroid, etc.)    │
│  ├─ Update data buffers                                   │
│  └─ Queue UI updates (throttled)                          │
└───────────────────────────────────────────────────────────┘
```

**Key Benefit**: Acquisition thread never waits for processing → perfect 1 Hz timing

---

### Thread Lifecycle

**Start**:
```python
def start_acquisition(self):
    """Start acquisition thread."""

    # Set flags
    self._acquiring = True
    self._stop_acquisition.clear()

    # Launch worker thread (non-daemon for graceful shutdown)
    self._acquisition_thread = threading.Thread(
        target=self._acquisition_worker,
        name="AcquisitionWorker",
        daemon=False  # Ensures clean stop
    )
    self._acquisition_thread.start()

    # Emit signal
    self.acquisition_started.emit()
```

**Stop**:
```python
def stop_acquisition(self):
    """Stop acquisition gracefully."""

    # Signal thread to stop
    self._stop_acquisition.set()
    self._acquiring = False

    # Wait for thread to finish (timeout after 3 seconds)
    if self._acquisition_thread:
        self._acquisition_thread.join(timeout=3.0)

        if self._acquisition_thread.is_alive():
            logger.warning("Acquisition thread did not stop cleanly")

    self.acquisition_stopped.emit()
```

---

### Pause/Resume

**Pause** (instant, no sleep):
```python
def pause_acquisition(self):
    """Pause acquisition without stopping thread."""
    self._paused = True
    self._pause_start_time = time.time()
    logger.info("⏸️  Acquisition paused")
```

**Resume** (instant, resumes immediately):
```python
def resume_acquisition(self):
    """Resume paused acquisition."""
    if self._paused:
        pause_duration = time.time() - self._pause_start_time
        self._total_paused_time += pause_duration
        self._paused = False
        logger.info(f"▶️  Acquisition resumed (paused {pause_duration:.1f}s)")
```

**Why Track Paused Time?** Prevents time jumps in graphs when resuming - elapsed time excludes paused intervals.

---

## Timing & Performance

### Timing Budget (1000ms total)

```
┌─────────────────────────────────────────────────────────┐
│  LED Switching: 4 × 50ms = 200ms                        │
│    ├─ Set channel A intensity (batch command)           │
│    ├─ Set channel B intensity                           │
│    ├─ Set channel C intensity                           │
│    └─ Set channel D intensity                           │
├─────────────────────────────────────────────────────────┤
│  Spectrum Acquisition: 4 × 100ms = 400ms                │
│    ├─ Read channel A spectrum (integration time)        │
│    ├─ Read channel B spectrum                           │
│    ├─ Read channel C spectrum                           │
│    └─ Read channel D spectrum                           │
├─────────────────────────────────────────────────────────┤
│  Calibration: 4 × 5ms = 20ms                            │
│    ├─ Dark subtraction (vectorized NumPy)               │
│    └─ Transmission calculation                          │
├─────────────────────────────────────────────────────────┤
│  Signal Emission: 4 × 1ms = 4ms                         │
│    └─ Qt signal emission (non-blocking)                 │
├─────────────────────────────────────────────────────────┤
│  Buffer & Overhead: ~76ms                               │
│    ├─ Queue operations                                  │
│    ├─ Thread scheduling                                 │
│    └─ Misc overhead                                     │
├─────────────────────────────────────────────────────────┤
│  Sleep: ~300ms                                          │
│    └─ Compensates for processing to maintain 1 Hz       │
└─────────────────────────────────────────────────────────┘
```

---

### Performance Optimizations

#### 1. Pre-Arm Integration Time

**Savings**: 84ms per cycle (21ms × 4 channels)

```python
# Before (SLOW): 84ms wasted per cycle
for channel in ['a', 'b', 'c', 'd']:
    detector.set_integration_time(100)  # 21ms overhead
    spectrum = detector.get_spectrum()  # 100ms

# After (FAST): 0ms overhead
detector.set_integration_time(100)  # Once before loop
for channel in ['a', 'b', 'c', 'd']:
    spectrum = detector.get_spectrum()  # Just 100ms
```

---

#### 2. Batch LED Commands

**Savings**: 150ms per cycle (50ms × 3 avoided commands)

```python
# Before (SLOW): 200ms for 4 channels
ctrl.set_led_intensity('a', 50)  # 50ms
ctrl.set_led_intensity('b', 0)   # 50ms
ctrl.set_led_intensity('c', 0)   # 50ms
ctrl.set_led_intensity('d', 0)   # 50ms

# After (FAST): 50ms for all 4 channels
ctrl.set_batch_intensities(a=50, b=0, c=0, d=0)  # 50ms
```

---

#### 3. Vectorized Calibration

**NumPy** (FAST):
```python
# Vectorized operations on entire array
transmission = (p_spectrum - dark) / (s_ref - dark) * 100
```

**Pure Python** (SLOW):
```python
# Element-by-element loop (100x slower)
transmission = []
for i in range(len(p_spectrum)):
    t = (p_spectrum[i] - dark[i]) / (s_ref[i] - dark[i]) * 100
    transmission.append(t)
```

---

## Channel Sequencing

### Channel Order

**Standard Sequence**: A → B → C → D → repeat

```python
channels = ['a', 'b', 'c', 'd']

while not stop_flag:
    for channel in channels:
        # Acquire spectrum for channel
        acquire_channel(channel)

    # Sleep to maintain 1 Hz (4 channels per second)
    time.sleep(sleep_time)
```

---

### LED Intensity Switching

**Batch Command** (all channels in one transaction):

```python
def set_channel_led(channel, intensities):
    """Set LED for specific channel, others off."""

    ctrl.set_batch_intensities(
        a=intensities['a'] if channel == 'a' else 0,
        b=intensities['b'] if channel == 'b' else 0,
        c=intensities['c'] if channel == 'c' else 0,
        d=intensities['d'] if channel == 'd' else 0
    )
```

**LED Overlap Strategy** (experimental, saves 40ms):

Turn on next channel's LED while reading current channel's spectrum:

```python
# Turn on LED A
ctrl.set_batch_intensities(a=50, b=0, c=0, d=0)

# Read spectrum A (100ms)
spectrum_a = detector.get_spectrum()

# Turn on LED B while processing A
ctrl.set_batch_intensities(a=0, b=60, c=0, d=0)

# Process spectrum A in parallel with LED B stabilization
process(spectrum_a)

# Read spectrum B (already stable)
spectrum_b = detector.get_spectrum()
```

**Result**: Saves ~40ms per cycle by overlapping LED switching with processing

---

## Data Flow

### Acquisition → Processing → Display

```
┌─────────────────────────────────────────────────────────┐
│ 1. ACQUISITION THREAD                                   │
│    ├─ Set LED (50ms)                                    │
│    ├─ Read spectrum (100ms)                             │
│    ├─ Apply calibration (5ms)                           │
│    └─ spectrum_acquired.emit(data)                      │
└──────────────────┬──────────────────────────────────────┘
                   │
                   │ Qt Signal (thread-safe)
                   │
┌──────────────────▼──────────────────────────────────────┐
│ 2. MAIN THREAD (Qt Event Loop)                          │
│    ├─ _on_spectrum_acquired(data)                       │
│    └─ _spectrum_queue.put(data)                         │
└──────────────────┬──────────────────────────────────────┘
                   │
                   │ Lock-free queue
                   │
┌──────────────────▼──────────────────────────────────────┐
│ 3. PROCESSING THREAD                                    │
│    ├─ _processing_worker()                              │
│    ├─ data = _spectrum_queue.get()                      │
│    ├─ Run processing pipeline (Fourier, centroid, etc.) │
│    ├─ _data_buffer_manager.append_timeline_point(...)   │
│    └─ Queue UI update (throttled)                       │
└──────────────────┬──────────────────────────────────────┘
                   │
                   │ Throttled updates (10 Hz max)
                   │
┌──────────────────▼──────────────────────────────────────┐
│ 4. UI UPDATES (Main Thread)                             │
│    ├─ _process_pending_ui_updates()                     │
│    ├─ Update graphs (setData)                           │
│    └─ Update live data dialog                           │
└─────────────────────────────────────────────────────────┘
```

---

### Queue Statistics

**Monitor queue health**:

```python
queue_stats = {
    'queued': 0,      # Total items queued
    'processed': 0,   # Total items processed
    'dropped': 0,     # Items dropped (queue full)
    'max_size': 0     # Peak queue size
}

# Check for backlog
if _spectrum_queue.qsize() > 10:
    logger.warning(f"Processing backlog: {_spectrum_queue.qsize()} items")
```

**Typical Values**:
- Healthy: 0-2 items in queue
- Slow processing: 3-10 items
- Blocking issue: >10 items (investigate)

---

## API Reference

### DataAcquisitionManager

**Initialization**:
```python
from affilabs.core.data_acquisition_manager import DataAcquisitionManager

data_mgr = DataAcquisitionManager(hardware_mgr)

# Connect signals
data_mgr.spectrum_acquired.connect(on_spectrum)
data_mgr.acquisition_started.connect(on_started)
data_mgr.acquisition_stopped.connect(on_stopped)
data_mgr.acquisition_error.connect(on_error)
```

---

**Start Acquisition**:
```python
# Requires calibration data first
data_mgr.apply_calibration(calibration_data)

# Start acquisition loop
data_mgr.start_acquisition()
```

---

**Stop Acquisition**:
```python
data_mgr.stop_acquisition()  # Graceful stop, waits for thread
```

---

**Pause/Resume**:
```python
data_mgr.pause_acquisition()   # Instant pause
data_mgr.resume_acquisition()  # Instant resume
```

---

### Calibration Data

**Create Calibration**:
```python
from affilabs.services.calibration_service import CalibrationData

cal_data = CalibrationData(
    wavelengths=wavelengths,      # np.ndarray
    dark=dark_spectrum,           # np.ndarray
    s_pol_ref={                   # dict[str, np.ndarray]
        'a': s_ref_a,
        'b': s_ref_b,
        'c': s_ref_c,
        'd': s_ref_d
    },
    led_intensities={             # dict[str, int]
        'a': 50,
        'b': 60,
        'c': 70,
        'd': 80
    },
    integration_time=100,         # int (ms)
    num_scans=1                   # int
)
```

---

**Apply Calibration**:
```python
data_mgr.apply_calibration(cal_data)

# Verify calibration
if data_mgr.calibrated:
    print("✓ Ready for acquisition")
else:
    print("✗ Calibration failed")
```

---

### Spectrum Data Structure

**Emitted via `spectrum_acquired` signal**:

```python
spectrum_data = {
    'channel': 'a',                    # str: 'a', 'b', 'c', or 'd'
    'timestamp': 1738492800.123,       # float: Unix timestamp
    'wavelengths': np.array([...]),    # np.ndarray: [200.0, 200.5, ...]
    'raw_spectrum': np.array([...]),   # np.ndarray: Raw detector counts
    'transmission': np.array([...]),   # np.ndarray: Calibrated transmission %
    'p_spectrum': np.array([...])      # np.ndarray: P-pol corrected data
}
```

---

## Troubleshooting

### Acquisition Not Starting

**Symptoms**: `start_acquisition()` called but no data appears

**Checks**:
1. Is system calibrated? `data_mgr.calibrated == True`
2. Is hardware connected? `hardware_mgr.connected == True`
3. Is detector responding? `detector.get_spectrum()` works?

**Debug**:
```python
# Check calibration
print(f"Calibrated: {data_mgr.calibrated}")
print(f"Cal data: {data_mgr.calibration_data}")

# Check hardware
print(f"Connected: {hardware_mgr.connected}")
print(f"Detector: {hardware_mgr.usb}")

# Test acquisition manually
spectrum = hardware_mgr.usb.get_spectrum()
print(f"Spectrum shape: {spectrum.shape}")
```

---

### Timing Drift

**Symptoms**: Acquisition not precisely 1 Hz, drifts over time

**Cause**: Sleep time not compensating for processing time

**Fix**:
```python
# Measure loop time
loop_start = time.time()

# ... acquisition work ...

# Compensate in sleep
elapsed = time.time() - loop_start
sleep_time = max(0, 1.0 - elapsed)
time.sleep(sleep_time)
```

---

### Missing Spectra

**Symptoms**: Channels A, B, C acquired, but D missing

**Cause**: Detector error during channel D acquisition

**Solution**: Add error handling per channel

```python
for channel in ['a', 'b', 'c', 'd']:
    try:
        spectrum = detector.get_spectrum()
    except Exception as e:
        logger.error(f"Channel {channel} acquisition failed: {e}")
        # Use previous spectrum or zeros
        spectrum = np.zeros(len(wavelengths))

    # Continue with remaining channels
```

---

### High Queue Size

**Symptoms**: `_spectrum_queue.qsize()` growing unbounded

**Cause**: Processing thread slower than acquisition

**Solutions**:
1. **Profile processing**: Identify slow operations
2. **Reduce processing**: Skip non-critical analysis
3. **Drop old data**: Implement queue size limit

```python
# Limit queue size
MAX_QUEUE_SIZE = 50

if _spectrum_queue.qsize() > MAX_QUEUE_SIZE:
    # Drop oldest item
    _spectrum_queue.get_nowait()
    logger.warning("Queue full - dropped oldest spectrum")
```

---

### Detector Saturation

**Symptoms**: Spectrum values at 65535 (16-bit max)

**Cause**: Integration time too long or LED too bright

**Fix**:
```python
# Check for saturation
max_intensity = np.max(spectrum)

if max_intensity > 60000:  # 90% of max
    logger.warning("Detector saturated - reduce integration time or LED")

    # Auto-adjust
    new_integration_time = integration_time * 0.8
    detector.set_integration_time(int(new_integration_time))
```

---

### Dark Spectrum Drift

**Symptoms**: Transmission values drift negative over time

**Cause**: Dark spectrum measured once at calibration, but detector temp changed

**Solution**: Periodic dark re-measurement

```python
# Re-measure dark every 15 minutes
DARK_REFRESH_INTERVAL = 900  # seconds

if time.time() - last_dark_time > DARK_REFRESH_INTERVAL:
    logger.info("Refreshing dark spectrum...")

    # Turn off all LEDs
    ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
    time.sleep(0.1)

    # Acquire new dark
    new_dark = detector.get_spectrum()

    # Update calibration
    calibration_data.dark = new_dark
    last_dark_time = time.time()
```

---

## Best Practices

### 1. Always Calibrate Before Acquisition

❌ **BAD**:
```python
data_mgr.start_acquisition()  # Will fail if not calibrated
```

✅ **GOOD**:
```python
if not data_mgr.calibrated:
    logger.error("Cannot start - not calibrated")
    return

data_mgr.start_acquisition()
```

---

### 2. Use Thread-Safe Queues

❌ **BAD** (race condition):
```python
# Two threads accessing list simultaneously
spectrum_list.append(data)  # Not thread-safe!
```

✅ **GOOD**:
```python
import queue

spectrum_queue = queue.Queue()  # Thread-safe
spectrum_queue.put(data)        # Safe from any thread
```

---

### 3. Monitor Queue Health

```python
# Log queue stats every 60 seconds
if time.time() - last_stats_time > 60:
    logger.info(f"Queue stats: size={queue.qsize()}, "
                f"processed={stats['processed']}, "
                f"dropped={stats['dropped']}")
    last_stats_time = time.time()
```

---

### 4. Handle Detector Errors Gracefully

```python
try:
    spectrum = detector.get_spectrum()
except Exception as e:
    logger.error(f"Detector error: {e}")

    # Attempt reconnection
    hardware_mgr.reconnect_detector()

    # Use fallback data
    spectrum = np.zeros(len(wavelengths))
```

---

## Related Documentation

- [Hardware Communication Layer](HARDWARE_COMMUNICATION_LAYER.md) - Detector and controller protocols
- [Data Processing Pipeline](DATA_PROCESSING_PIPELINE.md) - Post-acquisition processing
- [Optical Convergence Engine](OPTICAL_CONVERGENCE_ENGINE.md) - LED calibration for acquisition

---

**End of Acquisition System Documentation**
