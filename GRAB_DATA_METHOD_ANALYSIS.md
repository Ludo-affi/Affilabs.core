# _grab_data() Method - Detailed Analysis

## Overview
The `_grab_data()` method is the **core data acquisition loop** for the SPR system. It runs continuously in a background thread, reading optical intensity data, processing it into wavelength measurements, and updating the UI.

**Location**: `main/main.py`, lines 1110-1285  
**Size**: 175 lines  
**Complexity**: Very High  
**Thread**: Runs in `self._tr` daemon thread (started in `__init__`)

---

## Method Structure

### **1. Initialization** (Lines 1110-1116)
```python
def _grab_data(self: Any) -> None:
    # transmission segment of interest
    # transmission segment wavelengths

    first_run = True

    while not self._b_kill.is_set():
```
- Infinite loop controlled by `self._b_kill` event
- `first_run` flag to set experiment start time

### **2. Loop Control** (Lines 1117-1127)
```python
ch = CH_LIST[0]
time.sleep(0.01)
try:
    if self._b_stop.is_set() or self.device_config["ctrl"] not in DEVICES:
        time.sleep(0.2)
        continue

    if first_run:
        self.exp_start = time.time()
        first_run = False
```
- 10ms sleep between iterations
- Skip if stopped or no device connected
- Set experiment start time on first run

### **3. Buffer Synchronization** (Lines 1128-1133)
```python
if not (
    len(self.buffered_times["a"])
    == len(self.buffered_times["b"])
    == len(self.buffered_times["c"])
    == len(self.buffered_times["d"])
):
    self.pad_values()
```
- Ensure all 4 channels have same buffer length
- Call `pad_values()` to add NaN if mismatched

### **4. Channel Selection** (Lines 1135-1140)
```python
ch_list = CH_LIST
if self.single_mode:
    ch_list = [self.single_ch]
elif self.device_config["ctrl"] in ["PicoEZSPR"]:  # EZSPR disabled (obsolete)
    ch_list = EZ_CH_LIST
```
- **Normal mode**: All 4 channels (A, B, C, D)
- **Single mode**: Only selected channel
- **PicoEZSPR mode**: Only 2 channels (A, B)

### **5. Main Channel Loop** (Lines 1141-1257)
**For each channel in CH_LIST:**

#### **5a. Hardware Control & Data Acquisition** (Lines 1141-1173)
```python
for ch in CH_LIST:
    fit_lambda = np.nan
    if self._b_stop.is_set():
        break
    if (
        ch in ch_list
        and not self._b_no_read.is_set()
        and self.calibrated
        and self.ctrl is not None
    ):
        int_data_sum = None
        self.ctrl.turn_on_channel(ch=ch)  # Turn on LED for this channel
        if self.led_delay > 0:
            time.sleep(self.led_delay)  # Wait for LED stabilization
        
        for _scan in range(self.num_scans):  # Average multiple scans
            if self._b_stop.is_set():
                break
            reading = self.usb.read_intensity()  # Read from spectrometer
            if reading is None:
                self.raise_error.emit("spec")
                self._b_stop.set()
                break
            int_data_single = reading[
                self.wave_min_index : self.wave_max_index
            ]
            if int_data_sum is None:
                int_data_sum = int_data_single
            else:
                int_data_sum = np.add(int_data_sum, int_data_single)
```

**What happens here**:
1. ✅ Check if channel should be read (in active channel list, not stopped, calibrated)
2. ✅ Turn on LED for this channel
3. ✅ Wait for LED stabilization (led_delay, typically 5ms)
4. ✅ Read intensity from spectrometer `num_scans` times (for averaging)
5. ✅ Extract valid wavelength range (wave_min_index to wave_max_index)
6. ✅ Accumulate intensity readings

#### **5b. Data Processing** (Lines 1174-1193)
```python
if int_data_sum is not None:
    # Average scans and subtract dark noise
    averaged_intensity = int_data_sum / self.num_scans
    self.int_data[ch] = averaged_intensity - self.dark_noise
    
    if self.ref_sig[ch] is not None and self.data_processor is not None:
        # Calculate transmission using data processor ✅ REFACTORED
        try:
            self.trans_data[ch] = self.data_processor.calculate_transmission(
                p_pol_intensity=averaged_intensity,
                s_ref_intensity=self.ref_sig[ch],
                dark_noise=self.dark_noise,
            )
        except Exception as e:
            logger.exception(f"Failed to get trans data: {e}")

if self.device_config["ctrl"] in DEVICES:
    self.ctrl.turn_off_channels()  # Turn off all LEDs
```

**What happens here**:
1. ✅ Average multiple scans
2. ✅ Subtract dark noise (background)
3. ✅ Store intensity data in `self.int_data[ch]`
4. ✅ Calculate transmission spectrum using **data_processor** (REFACTORED ✅)
5. ✅ Turn off LEDs

#### **5c. Resonance Wavelength Detection** (Lines 1195-1209)
```python
if not (self._b_stop.is_set() or self.trans_data[ch] is None):
    # Use data processor to find resonance wavelength ✅ REFACTORED
    if self.data_processor is not None:
        spectrum = self.trans_data[ch]
        fit_lambda = self.data_processor.find_resonance_wavelength(
            spectrum=spectrum,
            window=DERIVATIVE_WINDOW,  # 165
        )
    else:
        # Fallback if processor not initialized
        fit_lambda = np.nan
else:
    fit_lambda = np.nan
    time.sleep(0.1)
```

**What happens here**:
1. ✅ Extract transmission spectrum
2. ✅ Find resonance wavelength using **data_processor** (REFACTORED ✅)
3. ✅ Uses derivative method with window size 165
4. ✅ Result is the SPR wavelength shift (the key measurement!)

#### **5d. Data Storage** (Lines 1211-1218)
```python
# update lambda values
self.lambda_values[ch] = np.append(
    self.lambda_values[ch],
    fit_lambda,
)
self.lambda_times[ch] = np.append(
    self.lambda_times[ch],
    round(time.time() - self.exp_start, 3),
)
```

**What happens here**:
1. ✅ Append new wavelength measurement to time series
2. ✅ Append timestamp (relative to experiment start)

#### **5e. Median Filtering** (Lines 1220-1244)
```python
if ch in ch_list:
    # Use data processor for median filtering ✅ REFACTORED
    if len(self.lambda_values[ch]) > self.filt_buffer_index:
        if self.data_processor is not None:
            filtered_value = self.data_processor.apply_causal_median_filter(
                data=self.lambda_values[ch],
                buffer_index=self.filt_buffer_index,
                window=self.med_filt_win,
            )
        else:
            # Fallback if processor not initialized
            filtered_value = fit_lambda
    else:
        filtered_value = fit_lambda

    self.filtered_lambda[ch] = np.append(
        self.filtered_lambda[ch],
        filtered_value,
    )
    self.buffered_lambda[ch] = np.append(
        self.buffered_lambda[ch],
        self.lambda_values[ch][self.filt_buffer_index],
    )
```

**What happens here**:
1. ✅ Apply median filter to reduce noise (using **data_processor** - REFACTORED ✅)
2. ✅ Uses causal filter (only past data, no future data)
3. ✅ Store filtered value
4. ✅ Store buffered value (from buffer_index position)

#### **5f. Inactive Channel Handling** (Lines 1245-1253)
```python
else:
    self.filtered_lambda[ch] = np.append(
        self.filtered_lambda[ch],
        np.nan,
    )
    self.buffered_lambda[ch] = np.append(
        self.buffered_lambda[ch],
        np.nan,
    )
```
- Fill inactive channels with NaN to maintain buffer synchronization

#### **5g. Time Buffering** (Lines 1254-1257)
```python
self.buffered_times[ch] = np.append(
    self.buffered_times[ch],
    self.lambda_times[ch][self.filt_buffer_index],
)

if ch == CH_LIST[-1]:
    self.filt_buffer_index += 1
```
- Store timestamp for buffered data
- Increment buffer index after last channel

### **6. UI Updates** (Lines 1259-1267)
```python
if not self._b_stop.is_set():
    self.update_live_signal.emit(self.sensorgram_data())
    self.update_spec_signal.emit(self.spectroscopy_data())

if self.device_config["ctrl"] == "PicoP4SPR" and isinstance(
    self.ctrl,
    PicoP4SPR,
):
    self.temp_sig.emit(self.ctrl.get_temp())
```
- Emit Qt signals to update sensorgram plot
- Emit Qt signals to update spectroscopy plot
- Emit temperature signal (P4SPR only)

### **7. Error Handling** (Lines 1268-1285)
```python
except Exception as e:
    logger.exception(
        f"Error while grabbing data:{type(e)}:{e}:channel {ch}",
    )
    self.pad_values()
    self._b_stop.set()
    self.main_window.ui.status.setText("Error while reading SPR data")
    if e is IndexError:
        show_message(
            msg_type="Warning",
            msg="Data Error: the program has encountered an error, "
            "stopped data acquisition",
        )
    else:
        self.raise_error.emit("ctrl")
```
- Log exception details
- Pad buffer values to prevent crashes
- Stop acquisition
- Update UI status
- Show error message to user

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────┐
│          _grab_data() Infinite Loop                 │
└─────────────────────────────────────────────────────┘
                      │
                      ▼
    ┌─────────────────────────────────────┐
    │  For Each Channel (A, B, C, D)      │
    └─────────────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│ Turn ON LED      │    │ Skip if inactive │
│ Wait for stable  │    │ (fill with NaN)  │
└──────────────────┘    └──────────────────┘
          │
          ▼
┌──────────────────────────────────┐
│ Read Spectrometer (num_scans)    │
│ - usb.read_intensity()            │
│ - Average multiple readings       │
│ - Extract wavelength range        │
└──────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────┐
│ Process Intensity Data            │
│ - Subtract dark noise             │
│ - Store in self.int_data[ch]      │
└──────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────┐
│ Calculate Transmission Spectrum        │
│ ✅ data_processor.calculate_transmission│
│    (p_pol, s_ref, dark_noise)          │
│ - Store in self.trans_data[ch]         │
└────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────┐
│ Find Resonance Wavelength              │
│ ✅ data_processor.find_resonance_wavelength│
│    (spectrum, window=165)              │
│ - Result: fit_lambda (SPR shift)       │
└────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────┐
│ Store Wavelength & Time                │
│ - self.lambda_values[ch].append()      │
│ - self.lambda_times[ch].append()       │
└────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────┐
│ Apply Median Filter                    │
│ ✅ data_processor.apply_causal_median_filter│
│    (data, buffer_index, window=11)     │
│ - Store filtered value                 │
└────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────┐
│ Update Buffers                         │
│ - self.filtered_lambda[ch].append()    │
│ - self.buffered_lambda[ch].append()    │
│ - self.buffered_times[ch].append()     │
└────────────────────────────────────────┘
          │
          ▼
    (Repeat for next channel)
          │
          ▼
┌────────────────────────────────────────┐
│ Emit UI Update Signals                 │
│ - update_live_signal.emit()            │
│ - update_spec_signal.emit()            │
│ - temp_sig.emit() (P4SPR only)         │
└────────────────────────────────────────┘
          │
          ▼
    (Loop continues)
```

---

## Key Data Structures

### **Input Data (Per Channel)**
```python
# From hardware
reading = self.usb.read_intensity()  # np.ndarray, full spectrum (2048 pixels)

# Calibration data
self.wave_min_index: int              # Start of valid range (e.g., 200)
self.wave_max_index: int              # End of valid range (e.g., 1800)
self.dark_noise: np.ndarray           # Background spectrum
self.ref_sig[ch]: np.ndarray          # Reference signal (S-polarized)
```

### **Intermediate Data (Per Channel)**
```python
self.int_data[ch]: np.ndarray         # Intensity data (dark noise subtracted)
self.trans_data[ch]: np.ndarray       # Transmission spectrum T(λ) = P/S
```

### **Output Data (Per Channel)**
```python
self.lambda_values[ch]: np.ndarray    # Raw resonance wavelengths (nm)
self.lambda_times[ch]: np.ndarray     # Timestamps (seconds)
self.filtered_lambda[ch]: np.ndarray  # Median-filtered wavelengths
self.buffered_lambda[ch]: np.ndarray  # Buffered wavelengths (delayed)
self.buffered_times[ch]: np.ndarray   # Buffered timestamps
```

### **Buffer Management**
```python
self.filt_buffer_index: int           # Current position in filter buffer
self.med_filt_win: int                # Median filter window size (default 11)
```

---

## What Has Been Refactored ✅

### **Data Processing Methods** (Phase 1)
- ✅ **Transmission calculation**: `data_processor.calculate_transmission()`
- ✅ **Resonance finding**: `data_processor.find_resonance_wavelength()`
- ✅ **Median filtering**: `data_processor.apply_causal_median_filter()`

**Before**: ~150 lines of inline processing logic  
**After**: Clean delegation to data_processor module

---

## What Remains (Cannot Be Easily Refactored)

### **1. Hardware Control** (~40 lines)
```python
self.ctrl.turn_on_channel(ch=ch)
time.sleep(self.led_delay)
reading = self.usb.read_intensity()
self.ctrl.turn_off_channels()
```
**Why it stays**: 
- Direct hardware communication
- Timing-critical (LED stability)
- Channel-specific control
- Must be in main thread context

### **2. Buffer Management** (~60 lines)
```python
self.lambda_values[ch] = np.append(...)
self.lambda_times[ch] = np.append(...)
self.filtered_lambda[ch] = np.append(...)
self.buffered_lambda[ch] = np.append(...)
self.buffered_times[ch] = np.append(...)
self.filt_buffer_index += 1
```
**Why it stays**:
- Application-level state management
- Multiple buffers synchronized
- Used by UI and recording
- Part of data model

### **3. Loop Control** (~30 lines)
```python
while not self._b_kill.is_set():
    if self._b_stop.is_set():
        continue
    if first_run:
        self.exp_start = time.time()
```
**Why it stays**:
- Application lifecycle control
- Thread coordination
- Experiment timing

### **4. UI Signal Emission** (~10 lines)
```python
self.update_live_signal.emit(self.sensorgram_data())
self.update_spec_signal.emit(self.spectroscopy_data())
self.temp_sig.emit(self.ctrl.get_temp())
```
**Why it stays**:
- Qt signal/slot mechanism
- Must emit from QApplication
- UI coupling required

### **5. Error Handling** (~20 lines)
```python
except Exception as e:
    logger.exception(...)
    self.pad_values()
    self._b_stop.set()
    self.main_window.ui.status.setText(...)
    show_message(...)
```
**Why it stays**:
- Application-level error recovery
- UI error messaging
- State management

---

## Potential Further Refactoring

### **Option 1: Extract Channel Acquisition Logic** (~50 lines)
Create a helper method:
```python
def _acquire_channel_data(self, ch: str) -> float:
    """Acquire and process data for a single channel."""
    # Turn on LED
    # Read intensity
    # Average scans
    # Process with data_processor
    # Return resonance wavelength
    return fit_lambda
```

**Benefits**: 
- ✅ Reduces main loop complexity
- ✅ Easier to test channel logic
- ✅ Better code organization

**Tradeoff**: 
- ❌ Adds method overhead
- ❌ Breaks up sequential flow

### **Option 2: Create Data Acquisition Manager** (~100 lines)
Move to `utils/spr_data_acquisition.py`:
```python
class SPRDataAcquisition:
    def __init__(self, ctrl, usb, data_processor, calibration_data):
        self.ctrl = ctrl
        self.usb = usb
        self.processor = data_processor
        # ... calibration parameters
    
    def acquire_channel(self, channel: str) -> ChannelReading:
        """Acquire raw data for one channel."""
        # LED control + spectrometer reading
        return ChannelReading(intensity=..., timestamp=...)
    
    def process_channel(self, reading: ChannelReading) -> float:
        """Process raw reading to wavelength."""
        # Transmission + resonance finding
        return wavelength
```

**Benefits**:
- ✅ Testable in isolation
- ✅ Clearer separation of concerns
- ✅ Can be reused for other acquisition modes

**Tradeoffs**:
- ❌ More complex architecture
- ❌ Need to pass many parameters
- ❌ Buffer management still in main
- ❌ Medium refactoring effort

---

## Performance Characteristics

### **Timing Analysis**
```
LED turn on:        < 1 ms
LED stabilization:  5 ms (configurable via led_delay)
Spectrometer read:  ~10-50 ms (depends on integration time)
Data processing:    ~5 ms (transmission + resonance finding)
Median filter:      ~1 ms
Buffer operations:  ~1 ms
UI signal emit:     ~1 ms

Total per channel:  ~23-73 ms (mostly waiting for spectrometer)
Total per cycle:    ~92-292 ms (4 channels)

Acquisition rate:   ~3-11 Hz (3-11 readings per second)
```

### **Memory Usage**
```
Per channel buffers:
- lambda_values:    ~8 bytes/reading × N readings
- lambda_times:     ~8 bytes/reading × N readings
- filtered_lambda:  ~8 bytes/reading × N readings
- buffered_lambda:  ~8 bytes/reading × N readings
- buffered_times:   ~8 bytes/reading × N readings

Total per channel:  ~40 bytes/reading
Total (4 channels): ~160 bytes/reading

For 1 hour at 5 Hz:
18,000 readings × 160 bytes = ~2.88 MB
```

---

## Thread Safety

### **Thread Context**
- Runs in `self._tr` daemon thread
- Started in `__init__()` on line 241
- Stopped by setting `self._b_kill` event

### **Shared Data**
- **Read**: `self.calibrated`, `self.device_config`, calibration data
- **Write**: `self.lambda_values`, `self.int_data`, `self.trans_data`, buffers
- **Signals**: Qt signals (thread-safe via Qt event loop)

### **Synchronization**
- `self._b_kill` - Thread termination
- `self._b_stop` - Pause acquisition
- `self._b_no_read` - Skip reading (used during calibration)
- Qt signals automatically queued to main thread

---

## Summary

### **What This Method Does**
The `_grab_data()` method is the **heart of the SPR measurement system**. It:
1. ✅ Controls multi-channel LED switching
2. ✅ Reads optical intensity from spectrometer
3. ✅ Processes intensity into transmission spectra
4. ✅ Detects resonance wavelength shifts (the SPR signal!)
5. ✅ Applies noise filtering
6. ✅ Manages time-series data buffers
7. ✅ Updates UI in real-time

### **Refactoring Status**
- ✅ **Data processing**: COMPLETE (delegates to data_processor)
- ⚙️ **Acquisition logic**: Could be extracted (~50-100 lines)
- ❌ **Hardware control**: Must stay in main
- ❌ **Buffer management**: Must stay in main
- ❌ **UI updates**: Must stay in main
- ❌ **Loop control**: Must stay in main

### **Current State**
- **185 lines** total
- **~60 lines** could potentially be extracted to a helper/manager
- **~125 lines** must remain in main.py (hardware, state, UI, threading)

### **Recommendation**
The method is **already well-optimized** after Phase 1 refactoring. Further extraction would provide **marginal benefit** (~60 lines saved) at the cost of **increased complexity**. 

**Verdict**: ✅ **Leave as-is** - focus refactoring efforts on higher-value targets (calibration profiles, kinetic operations, widget I/O).
