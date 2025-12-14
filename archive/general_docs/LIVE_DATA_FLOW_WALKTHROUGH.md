# Live Data Flow: Raw P-Pol to Transmission Output
**Complete Technical Walkthrough** | AffiLabs.core v4.0-beta

## Overview: The Complete Journey

This document traces a single P-pol spectrum from hardware acquisition through to final transmission display.

---

## 🔄 The Complete Data Pipeline

```
STEP 1: Hardware Acquisition (USB read)
    ↓ Raw P-pol spectrum (counts)

STEP 2: Dark Noise Subtraction
    ↓ Dark-corrected P-pol (counts)

STEP 3: Transmission Calculation (P/S with LED correction)
    ↓ Raw transmission spectrum (%)

STEP 3b: Savitzky-Golay Denoising (STANDARD PREPROCESSING)
    ↓ SG-filtered transmission (% - ready for ANY peak finder)

STEP 4: Peak Finding (choose from multiple algorithms)
    ↓ SPR wavelength (nm)

STEP 5-7: Queue → Main Thread → UI Display
```

**KEY INSIGHT:** Steps 1-3b create a **standard prepared transmission spectrum** that is fed to ALL peak tracking models. Each model may apply additional method-specific processing, but the SG-filtered transmission is the universal input.

---

## Step 1: Hardware Acquisition (Worker Thread)
**File:** `core/data_acquisition_manager.py:910-990`
**Thread:** Acquisition Worker (Background)
**Function:** `_acquire_channel_spectrum(channel)`

### What Happens:
```python
# 1. Set polarizer to P-mode (done once at start_acquisition)
ctrl.set_mode('p')  # Servo moves to P-polarization position

# 2. Turn on LED for this channel with calibrated intensity
led_intensity = self.leds_calibrated[channel]  # e.g., 180 for channel 'a'
ctrl.set_intensity(ch=channel, raw_val=led_intensity)

# 3. Wait for LED to stabilize (70ms ON delay)
time.sleep(0.070)  # LED_DELAY_MS

# 4. Set spectrometer integration time
usb.set_integration(self.integration_time)  # e.g., 40ms

# 5. Acquire raw spectrum from USB spectrometer
raw_spectrum = usb.read_intensity()  # Returns np.array[2048] of counts

# 6. Trim to calibrated wavelength range (e.g., 400-900nm)
raw_spectrum = raw_spectrum[wave_min_index:wave_max_index]
```

### Output:
```python
{
    'wavelength': np.array([400.0, 400.3, ..., 899.7]),  # 2048 points
    'intensity': np.array([15234, 16891, ..., 14532])    # Raw counts
}
```

**Key Point:** This is **RAW P-polarization intensity** - uncorrected, with dark noise, LED profile, etc.

---

## Step 2: Dark Noise Subtraction (Worker Thread)
**File:** `core/data_acquisition_manager.py:1000-1010`
**Function:** `_process_spectrum(channel, spectrum_data)`

### What Happens:
```python
# Get raw intensity from Step 1
intensity = spectrum_data['intensity']  # Raw counts

# Subtract dark noise (measured during calibration with LEDs off)
if self.dark_noise is not None:
    intensity = intensity - self.dark_noise
    # Now contains only LED signal, no detector background
```

### Output:
```python
raw_spectrum = intensity.copy()  # Dark-corrected P-pol spectrum
# Example: [12450, 13920, 14100, ..., 11780] counts
```

**Key Point:** Still has LED spectral profile (some wavelengths brighter than others).

---

## Step 3: Transmission Calculation (Worker Thread)
**File:** `core/data_acquisition_manager.py:1013-1040`
**Function:** `_process_spectrum()` → calls `calculate_transmission()`

### What Happens:
```python
# Get S-mode reference spectrum (LED profile in S-pol, from calibration)
ref_spectrum = self.ref_sig[channel]
# Example: [38200, 42100, 40900, ..., 35600] counts (S-mode at LED=80)

# Get LED intensities for correction
p_led = self.leds_calibrated[channel]  # P-mode LED (e.g., 220)
s_led = self.ref_intensity[channel]    # S-mode LED (e.g., 80)

# Calculate transmission percentage with LED boost correction
from utils.spr_signal_processing import calculate_transmission
transmission_spectrum = calculate_transmission(
    raw_spectrum, ref_spectrum,
    p_led_intensity=p_led,
    s_led_intensity=s_led
)
```

### The Math (CRITICAL - LED Boost Correction):
```python
def calculate_transmission(intensity, reference, p_led_intensity, s_led_intensity):
    """
    WRONG (without LED correction):
    Transmission = (P_counts / S_counts) × 100
    Problem: If P-mode LED=220 and S-mode LED=80, this inflates by 2.75x!

    CORRECT (with LED correction):
    Transmission = (P_counts / P_LED) / (S_counts / S_LED) × 100
                 = (P_counts × S_LED) / (S_counts × P_LED) × 100

    Example:
    - P_counts = 45000, P_LED = 220
    - S_counts = 40000, S_LED = 80
    - Raw ratio: 45000/40000 = 1.125 = 112.5% [WRONG - too high!]
    - Corrected: (45000 × 80) / (40000 × 220) = 3.6M / 8.8M = 0.409 = 40.9% [CORRECT]

    Why this works:
    - S_counts ∝ LED_S × Detector × S_transmission
    - P_counts ∝ LED_P × Detector × P_transmission
    - Division cancels Detector AND normalizes LED boost!
    """
    transmission = (intensity / reference) * 100

    if p_led_intensity and s_led_intensity:
        led_correction = s_led_intensity / p_led_intensity  # e.g., 80/220 = 0.364
        transmission = transmission * led_correction

    return transmission
```

### Output:
```python
transmission_spectrum = np.array([32.6, 33.1, 34.5, ..., 28.2, ..., 33.0])  # Percentages
# Typical range: 10-70% depending on SPR dip depth
# SPR resonance appears as a DIP (minimum value, e.g., 28.2%)
```

**Key Point:** LED boost correction is **ESSENTIAL** - without it, transmission values would be artificially high by the LED boost factor (e.g., 2-3x)!

---

## Step 3b: Savitzky-Golay Denoising (Worker Thread)
**File:** `core/data_acquisition_manager.py:1048-1050`
**Function:** `_process_spectrum()` → applies SG filter

### What Happens:
```python
from scipy.signal import savgol_filter

# Apply Savitzky-Golay filter to denoise transmission spectrum
# THIS IS STANDARD PREPROCESSING - applied before ANY peak finding method
if transmission_spectrum is not None and len(transmission_spectrum) >= 21:
    transmission_spectrum = savgol_filter(transmission_spectrum, 21, 3)
```

### The Math:
```python
def savgol_filter(data, window_length, polyorder):
    """
    Savitzky-Golay filter: Local polynomial smoothing

    - Fits polynomial to sliding window
    - Window=21 points → ~2nm smoothing @ 0.1nm/pixel
    - Polynomial order=3 (cubic) → preserves peak curvature
    - Removes high-frequency noise while preserving peak position
    """
```

### Effect:
```python
# Before SG: [32.1, 33.5, 31.8, 34.2, 28.4, 27.9, ...]  ← Noisy (P/S amplifies noise)
# After SG:  [32.3, 32.8, 32.1, 31.5, 28.2, 27.8, ...]  ← Smooth (~10× noise reduction)
```

**Why This is Critical:**
- Transmission = P/S ratio **amplifies noise** (division operation)
- SG filter removes high-frequency noise before peak finding
- Window size preserves SPR dip (typically 10-30nm FWHM)
- **Applied ONCE in pipeline** - ALL peak finding methods use this same filtered data

**This is the "prepared transmission spectrum" that goes to ALL peak tracking models.**

---

## Step 4: Peak Finding (Worker Thread)
**File:** `core/data_acquisition_manager.py:1053-1060`
**Function:** `_process_spectrum()` - Simple min-finding (default)

### What Happens:
```python
# Find SPR resonance peak (actually a dip - minimum transmission)
# Input: SG-filtered transmission spectrum (already denoised)
peak_input = transmission_spectrum

# Simple approach: Find minimum value
min_idx = np.argmin(peak_input)
peak_wavelength = wavelength[min_idx]

# Example result: 652.3 nm (the SPR resonance wavelength)
```

### Advanced Peak Finding Methods (Optional):
**File:** `core/data_acquisition_manager.py:1084-1121`
**Function:** `_find_resonance_peak()` - Multiple algorithms available

Each peak finding method receives the **same SG-filtered transmission spectrum** and may apply additional method-specific processing:

#### **Method 1: Fourier Transform (DST/IDCT)**
```python
from utils.spr_signal_processing import find_resonance_wavelength_fourier

peak_wavelength = find_resonance_wavelength_fourier(
    transmission_spectrum=transmission_spectrum,  # ← Already SG-filtered!
    wavelengths=wavelength,
    fourier_weights=self.fourier_weights[channel],  # SNR-aware weights
    window_size=165,
    apply_sg_filter=False  # ← No additional filtering (already done in pipeline)
)
)
```

**Algorithm (Fourier Method):**
1. **Input:** SG-filtered transmission spectrum (already denoised in Step 3b)
2. **Linear Detrending:** Remove baseline slope from spectrum
3. **DST (Discrete Sine Transform):** Transform to frequency domain with SNR-aware weights
4. **IDCT (Inverse DCT):** Calculate smoothed derivative in spatial domain
5. **Zero-crossing:** Find where derivative = 0 (peak minimum)
6. **Linear Regression:** Refine position in 165-point window around zero-crossing

**Note:** The Fourier method can optionally apply additional SG filtering by setting `apply_sg_filter=True`, but this is redundant since the transmission is already SG-filtered in the main pipeline.

#### **Method 2-5: Other Peak Tracking Models**
The system supports multiple peak tracking algorithms (centroid-based, Gaussian fit, multi-parametric, etc.). All methods receive the **same SG-filtered transmission spectrum** from Step 3b.

### Output:
```python
{
    'wavelength': 652.3,  # Peak wavelength (nm)
    'intensity': 12450,   # Intensity at peak
    'full_spectrum': raw_spectrum,  # Full dark-corrected P-pol data
    'raw_spectrum': raw_spectrum,   # Same (for compatibility)
    'transmission_spectrum': transmission_spectrum,  # P/S ratio (%)
    'fwhm': None  # Full-width half-max (optional)
}
```

---

## Step 5: Queue to Main Thread (Worker → Main)
**File:** `core/data_acquisition_manager.py:630-660`
**Function:** `_acquisition_worker()` loop

### What Happens:
```python
# Process spectrum in worker thread (Steps 1-4)
processed = self._process_spectrum(channel, spectrum_data)

# Build data packet for main thread
data = {
    'channel': channel,  # 'a', 'b', 'c', or 'd'
    'wavelength': processed['wavelength'],  # 652.3 nm
    'intensity': processed['intensity'],    # Peak intensity
    'timestamp': time.time(),
    'raw_spectrum': processed['raw_spectrum'],  # Full dark-corrected data
    'full_spectrum': processed['full_spectrum'],
    'transmission_spectrum': processed['transmission_spectrum'],  # P/S ratio
    'is_preview': False
}

# Put in thread-safe queue (non-blocking)
try:
    self._spectrum_queue.put_nowait(data)
except queue.Full:
    # Queue full - drop frame (prevents blocking worker)
    pass
```

---

## Step 6: Queue Processing (Main Thread via Timer)
**File:** `core/data_acquisition_manager.py:533-556`
**Function:** `_process_spectrum_queue()` - Called by QTimer

### What Happens:
```python
# QTimer calls this every ~50ms in main thread
def _process_spectrum_queue(self):
    max_items = 20  # Process up to 20 items per tick

    while items_processed < max_items:
        try:
            data = self._spectrum_queue.get_nowait()

            # Emit Qt signal (thread-safe) to application
            self.spectrum_acquired.emit(data)

        except queue.Empty:
            break  # No more data
```

---

## Step 7: Application Processing (Main Thread)
**File:** `main_simplified.py:1424-1453`
**Function:** `_on_spectrum_acquired(data)` - Acquisition callback

### What Happens:
```python
# Calculate elapsed time since experiment start
data['elapsed_time'] = data['timestamp'] - self.experiment_start_time

# Queue for processing thread (another queue!)
self._spectrum_queue.put_nowait(data)
```

**Why another queue?** Performance optimization - keeps acquisition callback FAST.

---

## Step 8: Spectrum Data Processing (Processing Thread)
**File:** `main_simplified.py:1456-1610`
**Function:** `_process_spectrum_data(data)` - Worker thread

### What Happens:
```python
# 1. Extract data
channel = data['channel']
wavelength = data['wavelength']  # Peak: 652.3 nm
elapsed_time = data['elapsed_time']  # Time since start
transmission = data.get('transmission_spectrum')  # Full P/S array
raw_spectrum = data.get('raw_spectrum')  # Full P-pol array

# 2. Append to timeline buffer (for sensorgram)
self.buffer_mgr.append_timeline_point(channel, elapsed_time, wavelength)

# 3. Queue transmission spectrum update (THROTTLED - every 1 sec)
time_since_last = timestamp - self._last_transmission_update[channel]
if time_since_last >= 1.0:  # TRANSMISSION_UPDATE_INTERVAL
    self._queue_transmission_update(channel, data)
    self._last_transmission_update[channel] = timestamp

# 4. Queue sensorgram graph update (DOWNSAMPLED - every 2nd point)
self._sensorgram_update_counter += 1
if self._sensorgram_update_counter % 2 == 0:  # SENSORGRAM_DOWNSAMPLE_FACTOR
    self._pending_graph_updates[channel] = {
        'elapsed_time': elapsed_time,
        'channel': channel
    }
```

---

## Step 9: Transmission Display Update (Main Thread)
**File:** `main_simplified.py:1658-1705`
**Function:** `_queue_transmission_update(channel, data)`

### What Happens:
```python
# Skip if disabled (performance optimization)
if not self._transmission_updates_enabled:
    return

# Get transmission spectrum
transmission = data.get('transmission_spectrum')  # P/S ratio array
raw_spectrum = data.get('raw_spectrum')  # Dark-corrected P-pol array
wavelengths = data.get('wavelengths', self.data_mgr.wave_data)

# Update live data dialog if open
if self._live_data_dialog is not None:
    # Update transmission plot (P/S ratio %)
    self._live_data_dialog.update_transmission_plot(
        channel, wavelengths, transmission
    )

    # Update raw data plot (dark-corrected P-pol counts)
    if self._raw_spectrum_updates_enabled:
        self._live_data_dialog.update_raw_data_plot(
            channel, wavelengths, raw_spectrum
        )
```

---

## Step 10: Graph Rendering (PyQtGraph)
**File:** `widgets/live_data_dialog.py` (if exists)

### What Happens:
```python
def update_transmission_plot(self, channel, wavelengths, transmission):
    # Get plot curve for this channel
    curve = self.transmission_plots[channel]

    # Update plot data
    curve.setData(wavelengths, transmission)
    # PyQtGraph handles efficient rendering with downsampling
```

---

## 📊 Data at Each Stage

### Stage 1: Raw P-Pol (After USB Read)
```
Wavelength (nm): [400.0, 400.3, ..., 899.7]
Intensity (counts): [15234, 16891, 17123, ..., 14532]
↓ Contains: LED profile + P-pol signal + dark noise
```

### Stage 2: Dark-Corrected P-Pol
```
Wavelength (nm): [400.0, 400.3, ..., 899.7]
Intensity (counts): [12450, 13920, 14100, ..., 11780]
↓ Contains: LED profile + P-pol signal
```

### Stage 3: Transmission (P/S Ratio)
```
Wavelength (nm): [400.0, 400.3, ..., 899.7]
Transmission (%): [32.6, 33.1, 34.5, 28.2 (DIP), ..., 33.0]
↓ Contains: Pure SPR signal (LED profile canceled)
```

### Stage 4: Peak Detection
```
Peak Wavelength: 652.3 nm (location of minimum transmission)
Peak Intensity: 12450 counts (at 652.3 nm)
```

### Stage 5: Timeline Point (for Sensorgram)
```
Time: 15.3 seconds (since experiment start)
Wavelength: 652.3 nm
Channel: 'a'
↓ Plotted on sensorgram as (time, wavelength) point
```

---

## 🔍 Key Optimizations

### 1. Throttling (TRANSMISSION_UPDATE_INTERVAL = 1.0s)
- **Before:** 40+ spectrum updates per second → UI freeze
- **After:** 1 update per second → Smooth UI
- **Impact:** 40x reduction in plot updates

### 2. Downsampling (SENSORGRAM_DOWNSAMPLE_FACTOR = 2)
- **Before:** Every data point plotted → Excessive redraws
- **After:** Every 2nd point plotted → 50% fewer redraws
- **Note:** Full data still recorded!

### 3. Debug Log Throttling (DEBUG_LOG_THROTTLE_FACTOR = 10)
- **Before:** 50+ log messages per spectrum
- **After:** Log every 10th spectrum
- **Impact:** 90% reduction in I/O overhead

---

## 🎯 Understanding Transmission

### Why Calculate Transmission?

**Problem:** Raw P-pol intensity varies with LED brightness across wavelengths
```
Channel A LED: Strong at 650nm, weak at 700nm
Channel B LED: Weak at 650nm, strong at 700nm
```

**Solution:** Divide by S-pol reference (LED profile)
```
Transmission = P-pol / S-pol * 100

Channel A: P=15000 / S=40000 = 37.5%
Channel B: P=12000 / S=35000 = 34.3%
```

Now both channels are normalized despite different LED profiles!

### SPR Signal in Transmission

- **High transmission (>50%):** Light passes through (no SPR)
- **Low transmission (<30%):** Light absorbed by SPR resonance
- **SPR dip:** Minimum transmission point = resonance wavelength

Example:
```
Wavelength:     640nm  650nm  652.3nm  655nm  660nm
Transmission:   35%    32%    28% ←DIP 31%    34%
                               ↑
                         SPR resonance
```

---

## 🛠️ Troubleshooting Guide

### Issue: No Transmission Data
**Check:**
1. `data_mgr.ref_sig[channel]` exists (S-mode calibration done?)
2. Array shapes match: `len(raw) == len(ref_sig)`
3. No division by zero in reference spectrum

### Issue: Noisy Transmission
**Check:**
1. Dark noise properly subtracted
2. LED intensities stable
3. Fourier weights computed during calibration

### Issue: Wrong Peak Detection
**Check:**
1. Using transmission (not raw) for peak finding
2. Wavelength range appropriate (640-690nm for typical SPR)
3. Fourier weights appropriate for channel

### Issue: UI Freezing
**Solution:** Increase throttling intervals in `config.py`
```python
TRANSMISSION_UPDATE_INTERVAL = 2.0  # Update every 2 seconds
SENSORGRAM_DOWNSAMPLE_FACTOR = 4    # Show 25% of points
```

---

## 📈 Performance Metrics

**Typical Pipeline Timing:**
```
USB Read:              5-10ms   (hardware speed)
Dark Subtraction:      <1ms     (numpy subtraction)
Transmission Calc:     <1ms     (numpy division)
Peak Finding:          1-3ms    (Fourier method)
Queue Operations:      <0.1ms   (lock-free queue)
UI Update (throttled): 50-100ms (PyQtGraph rendering)
────────────────────────────────
Total per spectrum:    ~10-15ms (67-100 Hz capability)
```

**With Optimizations:**
- Actual UI update rate: 1 Hz (throttled)
- Sensorgram update: 20 Hz (downsampled 2x from 40 Hz)
- Log output: 4 Hz (throttled 10x from 40 Hz)

---

## 🎓 Summary: The Journey

1. **Hardware** reads raw P-pol light intensity (2048 wavelengths)
2. **Dark noise** subtracted → Clean LED signal
3. **Transmission** calculated → P/S ratio normalizes LED profile
4. **Peak finding** extracts SPR resonance wavelength
5. **Queue** transfers data from worker → main thread (thread-safe)
6. **Processing** thread handles heavy computation
7. **UI updates** throttled to prevent freezing
8. **Graphs** display both transmission spectrum and timeline

**The Result:** Smooth, real-time SPR monitoring with minimal CPU overhead! 🚀
