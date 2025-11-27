# DATA FLOW DIAGRAM - Raw & Transmission Spectra

## 🎯 Visual Trace: From Detector → Graph Display

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     PHASE 1: ACQUISITION THREAD                          │
│                 (data_acquisition_manager.py)                            │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ Line 641-642: Build data dict
                                  ▼
                    ┌──────────────────────────────┐
                    │  data = {                    │
                    │    'channel': 'a',           │
                    │    'wavelength': 665.2,      │
                    │    'intensity': 45000,       │
                    │    'raw_spectrum': [3648],   │◄── ✅ RAW DATA
                    │    'transmission_spectrum':  │◄── ✅ TRANSMISSION
                    │    'wavelengths': [3648],    │◄── ✅ CALIBRATED λ
                    │    'timestamp': 1234.5       │
                    │  }                           │
                    └──────────────────────────────┘
                                  │
                                  │ Line 354: spectrum_acquired.emit(data)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     PHASE 2: SIGNAL CONNECTION                           │
│                      (Qt Signal/Slot Bridge)                             │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ Line 395: Qt.QueuedConnection
                                  │ (thread-safe cross-thread signal)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   PHASE 3: ACQUISITION CALLBACK                          │
│              (main_simplified.py::_on_spectrum_acquired)                 │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ Line 1510: Queue for worker thread
                                  ▼
                    ┌──────────────────────────────┐
                    │  self._spectrum_queue.put()  │
                    │                              │
                    │  Queue contains:             │
                    │    - raw_spectrum            │◄── ✅ PRESERVED
                    │    - transmission_spectrum   │◄── ✅ PRESERVED
                    │    - wavelengths             │◄── ✅ PRESERVED
                    └──────────────────────────────┘
                                  │
                                  │ Worker thread pulls from queue
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    PHASE 4: WORKER THREAD PROCESSING                     │
│             (main_simplified.py::_process_spectrum_data)                 │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ Line 1578-1582: Throttle check
                                  │ (Only update every N seconds)
                                  ▼
                    ┌──────────────────────────────┐
                    │  if should_update:           │
                    │    _queue_transmission_      │
                    │    update(channel, data)     │
                    └──────────────────────────────┘
                                  │
                                  │ Line 1747: Stage in pending updates
                                  ▼
                    ┌──────────────────────────────┐
                    │  _pending_transmission_      │
                    │  updates[channel] = {        │
                    │    'transmission': [3648],   │◄── ✅ STAGED
                    │    'raw_spectrum': [3648],   │◄── ✅ STAGED
                    │    'wavelengths': [3648]     │◄── ✅ STAGED
                    │  }                           │
                    └──────────────────────────────┘
                                  │
                                  │ Wait for UI timer (10 FPS)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  PHASE 5: BATCH GRAPH UPDATE (10 FPS)                    │
│           (main_simplified.py::_process_transmission_updates)            │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ Line 308: Timer fires (100ms interval)
                                  │ Line 1929: Calls _process_transmission_updates()
                                  ▼
                    ┌──────────────────────────────┐
                    │  for channel in pending:     │
                    │    data = pending[channel]   │
                    │                              │
                    │    # Update transmission     │
                    │    transmission_curves[]     │
                    │      .setData(λ, trans)      │◄── ✅ GRAPH 1
                    │                              │
                    │    # Update raw data         │
                    │    raw_data_curves[]         │
                    │      .setData(λ, raw)        │◄── ✅ GRAPH 2
                    └──────────────────────────────┘
                                  │
                                  │ PyQtGraph renders curves
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      PHASE 6: UI DISPLAY (PyQtGraph)                     │
│                        (User sees graphs update)                         │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                        ┌─────────┴─────────┐
                        │                   │
                        ▼                   ▼
          ┌─────────────────────┐ ┌─────────────────────┐
          │ TRANSMISSION GRAPH  │ │   RAW DATA GRAPH    │
          │                     │ │                     │
          │  X: Wavelength      │ │  X: Wavelength      │
          │  Y: Transmission %  │ │  Y: Raw Intensity   │
          │                     │ │                     │
          │  640-690 nm         │ │  640-690 nm         │
          │  0-100%             │ │  0-65535            │
          │                     │ │                     │
          │  ✅ DISPLAYS        │ │  ✅ DISPLAYS        │
          └─────────────────────┘ └─────────────────────┘
```

---

## 📊 Data Preservation Table

| **Stage**                  | **raw_spectrum** | **transmission_spectrum** | **wavelengths** |
|----------------------------|------------------|---------------------------|-----------------|
| Acquisition (emit)         | ✅ Included      | ✅ Included               | ✅ Included     |
| Queue (put_nowait)         | ✅ Preserved     | ✅ Preserved              | ✅ Preserved    |
| Worker (stage)             | ✅ Extracted     | ✅ Extracted              | ✅ Extracted    |
| Batch Update (setData)     | ✅ Displayed     | ✅ Displayed              | ✅ Axis         |
| UI Curves                  | ✅ Rendered      | ✅ Rendered               | ✅ X-axis       |

---

## 🔄 Update Timing

```
Acquisition Rate:   40+ Hz (detector scan rate)
                    │
                    │ Throttle via time check
                    ▼
Queue Rate:         1-2 Hz per channel (TRANSMISSION_UPDATE_INTERVAL)
                    │
                    │ Batch processing
                    ▼
Graph Update:       1 Hz (UI timer, 1000ms interval)
                    │
                    │ PyQtGraph render
                    ▼
Display:            Smooth visual update
```

---

## 🎨 Channel Color Mapping

```
Channel A (Index 0) → Red Curve
Channel B (Index 1) → Green Curve
Channel C (Index 2) → Blue Curve
Channel D (Index 3) → Yellow Curve
```

---

## 🧵 Thread Context

```
ACQUISITION THREAD
│ data_acquisition_manager.py
│ ├─ _process_spectrum() [Line 900-965]
│ ├─ calculate_transmission() [Called internally]
│ └─ spectrum_acquired.emit(data) [Line 354]
│
├─ Qt Signal Queue (thread-safe)
│
MAIN THREAD
│ main_simplified.py
│ ├─ _on_spectrum_acquired() [Line 1483]
│ └─ _spectrum_queue.put_nowait() [Line 1510]
│
WORKER THREAD
│ main_simplified.py
│ ├─ _process_spectrum_data() [Line 1517]
│ └─ _queue_transmission_update() [Line 1706]
│
MAIN THREAD (UI Timer)
│ main_simplified.py
│ ├─ _process_pending_ui_updates() [Line 308 connect]
│ ├─ _process_transmission_updates() [Line 1941]
│ └─ transmission_curves[].setData() [Line 1967, 1983]
```

---

## 🔍 Debug Verification Points

### 1. Check Data Emission
```python
# In data_acquisition_manager.py, line 641-642
print(f"Emitting: raw={len(data['raw_spectrum'])}, trans={len(data['transmission_spectrum'])}")
```

### 2. Check Queue Receipt
```python
# In main_simplified.py, line 1510
print(f"Queued: raw={len(data['raw_spectrum'])}, trans={len(data['transmission_spectrum'])}")
```

### 3. Check Staging
```python
# In main_simplified.py, line 1747
print(f"Staged for {channel}: raw={len(raw_spectrum)}, trans={len(transmission)}")
```

### 4. Check Graph Update
```python
# In main_simplified.py, line 1967, 1983
print(f"setData called: {channel} - {len(wavelengths)} points")
```

### 5. Check Log Output
```bash
# Expected log messages
✅ Ch A: Transmission plot updated (3648 points)
✅ Ch A: Raw data plot updated
```

---

## 🚀 Performance Characteristics

| **Metric**                | **Value**           | **Purpose**                |
|---------------------------|---------------------|----------------------------|
| Acquisition Rate          | 40+ Hz              | Detector scan speed        |
| Queue Size                | 100 items           | Buffer overflow protection |
| Throttle Interval         | 1-2 seconds/channel | Prevent graph thrashing    |
| UI Update Rate            | 1 Hz (1000ms)       | Smooth visual refresh      |
| Points per Spectrum       | 3648                | Full detector pixel array  |
| Downsampling (Timeline)   | 2000 points max     | Maintain rendering speed   |

---

## ✅ VERIFICATION CHECKLIST

- [x] Data emitted with both spectra
- [x] Signal connection active (QueuedConnection)
- [x] Queue preserves data structure
- [x] Worker thread extracts both spectra
- [x] Batch processor calls setData() for both graphs
- [x] UI curves exist and are initialized
- [x] First update logs confirmation message
- [x] Auto-scale enabled on first update
- [x] Subsequent updates render smoothly

**Result**: Complete data flow verified end-to-end. Both raw and transmission spectra display correctly.

---

**Created**: 2025-01-18
**Git Tag**: v1.0-gold-standard
**Status**: ✅ PRODUCTION READY
