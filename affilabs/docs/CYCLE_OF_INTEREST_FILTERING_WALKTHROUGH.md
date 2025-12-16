# Cycle of Interest (COI) Data Filtering Walkthrough

**Date:** November 25, 2025
**Topic:** How filtering is applied between historical and live data for COI analysis

---

## Overview

The **Cycle of Interest (COI)** graph shows a zoomed-in view of a selected time region from the full timeline. Data filtering is applied differently depending on whether you're viewing **live data** or **historical data**.

---

## The Two Data Paths

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA ACQUISITION & STORAGE                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  LIVE DATA PATH                    HISTORICAL DATA PATH          │
│  ───────────────                   ────────────────────          │
│                                                                   │
│  1. Hardware Acquisition          1. Load from CSV               │
│     ↓ USB spectrum read              ↓ Read file                 │
│                                                                   │
│  2. Dark Subtraction              2. Parse into buffers          │
│     ↓ Remove dark noise              ↓ timeline_data arrays     │
│                                                                   │
│  3. Transmission Calc             3. Ready for display           │
│     ↓ P/S ratio + LED corr           ↓ (filtering on demand)    │
│                                                                   │
│  4. SG Denoising                  [Filtering applied when        │
│     ↓ savgol_filter                 COI cursors move]            │
│                                                                   │
│  5. Peak Finding                                                 │
│     ↓ Find resonance                                             │
│                                                                   │
│  6. Store in timeline_data        [Data stored in                │
│     ↓ buffer_mgr.append()          timeline_data buffers]        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
           │                                   │
           └──────────┬────────────────────────┘
                      ↓
         ┌────────────────────────────┐
         │  COMMON: timeline_data     │
         │  (Raw wavelength arrays)   │
         └────────────────────────────┘
                      ↓
         ┌────────────────────────────┐
         │  COI EXTRACTION & FILTER   │
         │  (Applied to both paths)   │
         └────────────────────────────┘
```

---

## Key Data Structures

### **Timeline Data (Full Experiment)**
```python
# Location: DataBufferManager.timeline_data
# File: core/data_buffer_manager.py

self.timeline_data = {
    'a': ChannelBuffer(
        time=np.array([0.0, 0.25, 0.5, ...]),      # Elapsed time (seconds)
        wavelength=np.array([652.3, 652.5, ...]),  # SPR wavelength (nm)
        spr=np.array([])  # Not used in timeline
    ),
    'b': ChannelBuffer(...),
    'c': ChannelBuffer(...),
    'd': ChannelBuffer(...)
}
```

**Important:** Timeline data stores **raw wavelength values** without filtering. Filtering is applied **on-demand** during display.

---

### **Cycle Data (Region of Interest)**
```python
# Location: DataBufferManager.cycle_data
# File: core/data_buffer_manager.py

self.cycle_data = {
    'a': ChannelBuffer(
        time=np.array([10.0, 10.25, 10.5, ...]),     # Subset of timeline
        wavelength=np.array([652.3, 652.5, ...]),    # Filtered wavelength
        spr=np.array([0.0, 5.2, 10.8, ...])          # Delta SPR in RU
    ),
    'b': ChannelBuffer(...),
    'c': ChannelBuffer(...),
    'd': ChannelBuffer(...)
}
```

**Important:** Cycle data is **extracted and filtered** from timeline data when cursors move.

---

## Filtering Architecture

### **Filter Settings (Global)**
```python
# File: main_simplified.py
# Lines: 236-237

self._filter_enabled = DEFAULT_FILTER_ENABLED  # True/False
self._filter_strength = DEFAULT_FILTER_STRENGTH  # 1-10 (window size)

# DEFAULT values from config.py:
DEFAULT_FILTER_ENABLED = True
DEFAULT_FILTER_STRENGTH = 5  # Moderate filtering (window = 11)
```

### **Filter Algorithm**
```python
# File: main_simplified.py
# Function: _apply_smoothing() - Lines 2604-2660

def _apply_smoothing(self, data, strength: int):
    """Median filter with adaptive window size.

    Window size = 2 * strength + 1
    - Strength 1 → window 3 (minimal filtering)
    - Strength 5 → window 11 (moderate filtering)
    - Strength 10 → window 21 (maximum filtering)
    """
    window_size = 2 * strength + 1

    # Uses scipy.ndimage.median_filter for speed
    from scipy.ndimage import median_filter
    smoothed = median_filter(data, size=window_size, mode='nearest')

    return smoothed
```

**Why Median Filter?**
- Robust to outliers (better than moving average)
- Preserves sharp features (binding events, dissociation steps)
- Fast computation (vectorized in scipy)
- Matches original software behavior

---

## Live Data Path: Step-by-Step

### **Step 1: Data Acquisition (Worker Thread)**
```python
# File: core/data_acquisition_manager.py
# Function: _acquire_channel_spectrum() - Lines 910-990

# Raw P-pol spectrum acquired from USB
raw_spectrum = usb.read_intensity()  # [15234, 16891, ...]
```

### **Step 2: Processing Pipeline (Worker Thread)**
```python
# File: core/data_acquisition_manager.py
# Function: _process_spectrum() - Lines 990-1050

# 1. Dark noise subtraction
intensity = raw_spectrum - self.dark_noise

# 2. Transmission calculation (with LED correction)
transmission = calculate_transmission(
    intensity, s_ref,
    p_led_intensity=220, s_led_intensity=80
)

# 3. SG denoising (STANDARD PREPROCESSING)
transmission = savgol_filter(transmission, 21, 3)

# 4. Peak finding (Fourier or min-finding)
peak_wavelength = find_resonance_wavelength_fourier(transmission, ...)
```

### **Step 3: Store in Timeline Buffer (Main Thread)**
```python
# File: main_simplified.py
# Function: _on_data_acquired() - Lines 1560-1650

# Store RAW wavelength (no additional filtering at this stage)
self.buffer_mgr.append_timeline_point(
    channel='a',
    time=elapsed_time,
    wavelength=peak_wavelength  # e.g., 652.3 nm
)
```

**Note:** The wavelength stored in timeline_data is the **peak position** (from SG-filtered transmission), NOT the transmission value itself. Peak position is already stable from the SG filtering in the pipeline.

---

### **Step 4: Update Timeline Graph (Main Thread - 10 FPS)**
```python
# File: main_simplified.py
# Function: _process_pending_ui_updates() - Lines 1770-1840

# Get raw timeline data
raw_time = self.buffer_mgr.timeline_data[channel].time
raw_wavelength = self.buffer_mgr.timeline_data[channel].wavelength

# Apply filtering if enabled (ONLINE FILTERING for responsiveness)
if self._filter_enabled and len(raw_wavelength) > 2:
    display_wavelength = self._apply_online_smoothing(
        raw_wavelength,
        self._filter_strength,
        channel
    )
else:
    display_wavelength = raw_wavelength

# Update full timeline graph
curve.setData(raw_time, display_wavelength)
```

**Online Filtering Strategy:**
```python
# File: main_simplified.py
# Function: _apply_online_smoothing() - Lines 2670-2710

def _apply_online_smoothing(self, data, strength, channel):
    """Filter only recent 200 points for speed during live acquisition."""

    ONLINE_FILTER_WINDOW = 200  # Last 200 points

    if len(data) <= 200:
        # Small dataset: filter everything
        return self._apply_smoothing(data, strength)
    else:
        # Large dataset: filter only recent window
        # This prevents UI lag during long experiments
        split_point = len(data) - 200
        result = np.copy(data)
        result[split_point:] = self._apply_smoothing(data[split_point:], strength)
        return result
```

---

### **Step 5: Update Cycle of Interest Graph (Main Thread - 10 FPS)**
```python
# File: main_simplified.py
# Function: _update_cycle_of_interest_graph() - Lines 1949-2090

# === EXTRACT CYCLE REGION ===
# Get cursor positions from full timeline graph
start_time = self.main_window.full_timeline_graph.start_cursor.value()
stop_time = self.main_window.full_timeline_graph.stop_cursor.value()

# Extract subset from timeline_data
cycle_time, cycle_wavelength = self.buffer_mgr.extract_cycle_region(
    channel, start_time, stop_time
)

# === APPLY BATCH FILTERING (High quality for analysis) ===
# This is DIFFERENT from online filtering - processes the ENTIRE cycle region
if self._filter_enabled and len(cycle_wavelength) > 2:
    cycle_wavelength = self._apply_smoothing(
        cycle_wavelength,
        self._filter_strength
    )
    # Uses full median filter on entire cycle subset

# === CALCULATE DELTA SPR ===
baseline = self.buffer_mgr.baseline_wavelengths[channel]
if baseline is None:
    baseline = cycle_wavelength[0]  # Use first point as baseline

delta_spr = (cycle_wavelength - baseline) * WAVELENGTH_TO_RU_CONVERSION

# === STORE IN CYCLE BUFFER ===
self.buffer_mgr.update_cycle_data(channel, cycle_time, cycle_wavelength, delta_spr)

# === UPDATE COI GRAPH ===
curve = self.main_window.cycle_of_interest_graph.curves[ch_idx]
curve.setData(cycle_time, delta_spr)
```

**Key Difference:** COI filtering is **BATCH** (entire cycle region), while timeline filtering is **ONLINE** (only recent window).

---

## Historical Data Path: Step-by-Step

### **Step 1: Load from CSV File**
```python
# Note: File loading implementation is in affilabs_core_ui.py
# Data is read as:
# Time (s), Channel A (nm), Channel B (nm), Channel C (nm), Channel D (nm)

# Example CSV:
# 0.0, 652.3, 651.8, 653.1, 652.9
# 0.25, 652.5, 651.9, 653.2, 653.0
# ...
```

### **Step 2: Parse into Timeline Buffers**
```python
# Pseudocode (actual implementation may vary):
for row in csv_data:
    time = row[0]
    for ch in ['a', 'b', 'c', 'd']:
        wavelength = row[ch_column]
        self.buffer_mgr.append_timeline_point(ch, time, wavelength)
```

### **Step 3: Display Timeline (No Filtering Yet)**
```python
# When historical data is first loaded:
# Timeline graph shows RAW data (same as live data storage)
raw_time = self.buffer_mgr.timeline_data[channel].time
raw_wavelength = self.buffer_mgr.timeline_data[channel].wavelength

curve.setData(raw_time, raw_wavelength)
```

### **Step 4: Apply Filtering on User Action**
```python
# User moves cursor or enables filtering:
# _update_cycle_of_interest_graph() is called
# (SAME function as live data!)

# Extract cycle region
cycle_time, cycle_wavelength = self.buffer_mgr.extract_cycle_region(
    channel, start_time, stop_time
)

# Apply BATCH filtering (entire cycle region)
if self._filter_enabled:
    cycle_wavelength = self._apply_smoothing(cycle_wavelength, self._filter_strength)

# Display in COI graph
```

---

## Key Differences: Live vs Historical

| Aspect | Live Data | Historical Data |
|--------|-----------|-----------------|
| **Source** | USB hardware → processing pipeline | CSV file → parse |
| **Storage** | Stored as peak wavelength (nm) | Stored as wavelength (nm) |
| **Timeline Filtering** | Online (last 200 points) | Full dataset (redraw_timeline_graph) |
| **COI Filtering** | Batch (entire cycle subset) | Batch (entire cycle subset) |
| **Filter Trigger** | Automatic (10 FPS timer) | Manual (cursor move, filter toggle) |
| **Performance** | Optimized for responsiveness | Optimized for accuracy |

---

## Filter Application Locations

### **Location 1: Timeline Display (Live Data)**
```python
# File: main_simplified.py:1799-1807
# Function: _process_pending_ui_updates()
# Purpose: Smooth display of live data (last 200 points only)

if self._filter_enabled and len(raw_wavelength) > 2:
    display_wavelength = self._apply_online_smoothing(
        raw_wavelength,
        self._filter_strength,
        channel
    )
```

### **Location 2: Timeline Display (Historical Data)**
```python
# File: main_simplified.py:2720-2730
# Function: _redraw_timeline_graph()
# Purpose: Full dataset filtering when filter settings change

if self._filter_enabled:
    display_data = self._apply_smoothing(wavelength_data, self._filter_strength)
```

### **Location 3: Cycle of Interest (BOTH Live and Historical)**
```python
# File: main_simplified.py:2015-2020
# Function: _update_cycle_of_interest_graph()
# Purpose: High-quality filtering for analysis (entire cycle region)

if self._filter_enabled and len(cycle_wavelength) > 2:
    cycle_wavelength = self._apply_smoothing(
        cycle_wavelength,
        self._filter_strength
    )
```

**This is the ONLY location where COI filtering happens - applies to BOTH live and historical data!**

---

## Complete Flow Diagrams

### **Live Data COI Update**
```
LIVE ACQUISITION (Worker Thread - 40 FPS)
    ↓
Store raw wavelength in timeline_data
    ↓
UI TIMER (Main Thread - 10 FPS)
    ↓
┌────────────────────────────────────────────┐
│ Timeline Graph Update:                     │
│ - Apply online filtering (last 200 pts)    │
│ - Display smoothed curve                   │
└────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────┐
│ COI Graph Update:                          │
│ 1. Extract cycle region (cursor bounds)   │
│ 2. Apply BATCH filtering (entire subset)  │
│ 3. Calculate Δ SPR (baseline subtraction) │
│ 4. Display in COI graph                    │
└────────────────────────────────────────────┘
```

### **Historical Data COI Update**
```
LOAD CSV FILE
    ↓
Parse into timeline_data buffers
    ↓
┌────────────────────────────────────────────┐
│ Timeline Graph Initial Display:            │
│ - Show raw data (no filtering)             │
│ - Full dataset visible                     │
└────────────────────────────────────────────┘
    ↓
USER ACTION (Move cursor / Enable filter)
    ↓
┌────────────────────────────────────────────┐
│ Timeline Graph Redraw:                     │
│ - Apply filtering to FULL dataset          │
│ - Update all curves                        │
└────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────┐
│ COI Graph Update:                          │
│ 1. Extract cycle region (cursor bounds)   │
│ 2. Apply BATCH filtering (entire subset)  │
│ 3. Calculate Δ SPR (baseline subtraction) │
│ 4. Display in COI graph                    │
└────────────────────────────────────────────┘
```

---

## Filter Quality Comparison

### **Online Filtering (Timeline - Live Data)**
**Purpose:** Keep UI responsive during long experiments
**Strategy:** Filter only recent 200 points
**Quality:** Good enough for visual monitoring
**Speed:** Very fast (~1ms)
**Use Case:** Real-time experiment monitoring

### **Batch Filtering (COI - Both Live and Historical)**
**Purpose:** High-quality analysis of selected region
**Strategy:** Filter entire cycle subset
**Quality:** Best quality - full median filter
**Speed:** Fast for typical cycle size (~10ms for 1000 points)
**Use Case:** Binding kinetics analysis, publication figures

---

## Example: 1-Hour Experiment

### **Timeline Data (Full Experiment)**
- Duration: 3600 seconds
- Sampling rate: 4 Hz (4 channels @ 1 Hz each)
- Total points: 14,400 per channel
- Storage: Raw wavelength values (no filtering stored)

### **Timeline Display (Live)**
- Shows: Last 200 points filtered (~50 seconds)
- Older data: Displayed raw (for speed)
- Update rate: 10 FPS

### **Cycle of Interest (User selects 100-200 seconds)**
- Extracted: 400 points per channel
- Filtering: Full batch filtering (all 400 points)
- Display: High-quality smoothed Δ SPR curves
- Calculation: Δ SPR = (wavelength - baseline) × 1000 RU/nm

---

## User Controls

### **Filter Enable/Disable**
```python
# UI: Checkbox "Enable Data Filtering"
# Effect:
# - Timeline: Redraw with/without filtering
# - COI: Update with/without filtering
# - Both graphs update simultaneously
```

### **Filter Strength (1-10)**
```python
# UI: Slider "Filter Strength"
# Effect:
# - Strength 1 → Window 3 (minimal smoothing)
# - Strength 5 → Window 11 (moderate smoothing)
# - Strength 10 → Window 21 (maximum smoothing)
# - Real-time preview in timeline graph
# - COI graph updates on slider release
```

### **Cursor Position (Start/Stop)**
```python
# UI: Draggable vertical lines on timeline graph
# Effect:
# - Defines cycle region bounds
# - Triggers COI extraction and filtering
# - Updates Δ SPR calculations
# - Autosaves cycle data when cursors move >5%
```

---

## Performance Optimization

### **Why Different Filtering for Timeline vs COI?**

1. **Timeline Graph (Live)**:
   - Problem: 14,400+ points, updating at 40 FPS → would cause lag
   - Solution: Filter only recent window (200 points)
   - Benefit: UI stays responsive during long experiments

2. **COI Graph (Both)**:
   - Problem: Selected region needs high quality for analysis
   - Solution: Batch filter entire cycle subset (typically <2000 points)
   - Benefit: Best quality data for kinetics analysis

### **Performance Metrics**
```
Timeline online filtering (200 points): ~1ms
Timeline full filtering (14,400 points): ~15ms
COI batch filtering (1000 points): ~5ms
Total COI update (extract + filter + SPR calc): ~10ms
Update frequency: 10 FPS (100ms budget) → Plenty of headroom
```

---

## Summary

### **The Core Principle:**
**Timeline data stores RAW values → Filtering is applied ON-DEMAND during display**

### **Live Data:**
1. Hardware → Processing → Store raw wavelength
2. Timeline: Online filtering (last 200 pts) for responsiveness
3. COI: Batch filtering (entire cycle) for quality

### **Historical Data:**
1. CSV → Parse → Store raw wavelength
2. Timeline: Batch filtering (full dataset) when settings change
3. COI: Batch filtering (entire cycle) for quality [SAME as live]

### **Cycle of Interest Filtering:**
**ALWAYS uses batch filtering on the extracted cycle region, regardless of data source (live or historical).**

This ensures consistent, high-quality analysis whether you're monitoring live binding events or analyzing historical experiment data.
