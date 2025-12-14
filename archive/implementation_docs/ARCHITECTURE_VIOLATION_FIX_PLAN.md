# Architecture Violation Fix: LiveRtoT Functions

**Date:** November 27, 2025
**Status:** 🔴 VIOLATION IDENTIFIED
**Priority:** HIGH

---

## 🔴 Problem Summary

The `LiveRtoT_QC` and `LiveRtoT_batch` functions violate the 4-layer architecture by:
1. Implementing core business logic in `utils/` folder (wrong layer)
2. Duplicating transmission calculation code (DRY violation)
3. Bypassing architectural data flow (direct utils → widgets)

---

## 📐 Current 4-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ LAYER 4: UI/WIDGETS (widgets/, affilabs_core_ui.py)        │
│   - calibration_qc_dialog.py                                │
│   - sidebar.py                                              │
│   - Main window                                             │
└─────────────────────────────────────────────────────────────┘
                         ▲
                         │ Display data only
                         │
┌─────────────────────────────────────────────────────────────┐
│ LAYER 3: COORDINATORS (core/)                               │
│   - graph_coordinator.py                                    │
│   - cycle_coordinator.py                                    │
└─────────────────────────────────────────────────────────────┘
                         ▲
                         │ Processed data
                         │
┌─────────────────────────────────────────────────────────────┐
│ LAYER 2: CORE BUSINESS LOGIC (core/)                        │
│   - data_acquisition_manager.py ✅ CORRECT                  │
│   - calibration_service.py                                  │
│   - recording_manager.py                                    │
└─────────────────────────────────────────────────────────────┘
                         ▲
                         │ Raw data
                         │
┌─────────────────────────────────────────────────────────────┐
│ LAYER 1: HARDWARE (managers/)                               │
│   - hardware_manager.py                                     │
│   - Hardware abstraction layer (HAL)                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔴 Violations Found

### **Violation #1: Business Logic in Wrong Layer**

**Current:**
```python
# ❌ WRONG: In utils/calibration_6step.py (Line 2165-2272)
def run_full_6step_calibration():
    # ... calibration code ...

    def LiveRtoT_QC(...):  # ❌ Nested in utils!
        """Process ONE channel for QC display"""
        # Complex transmission calculation logic (100+ lines)
        pass

    def LiveRtoT_batch(...):  # ❌ Nested in utils!
        """Process ALL channels for live view"""
        # Complex transmission calculation logic (100+ lines)
        pass
```

**Should Be:**
```python
# ✅ CORRECT: In core/transmission_processor.py (NEW FILE)
class TransmissionProcessor:
    """Layer 2: Core business logic for transmission calculations.

    Single source of truth for P/S ratio processing used by:
    - Calibration QC display
    - Live data acquisition
    - Post-processing analysis
    """

    def process_single_channel(self, ...):
        """Process one channel (for QC display)"""
        pass

    def process_batch(self, ...):
        """Process all channels (for live view)"""
        pass
```

---

### **Violation #2: Code Duplication**

**Problem:**
Transmission calculation logic exists in **THREE** places:

1. `utils/calibration_6step.py::LiveRtoT_QC` (lines 2165-2270)
2. `utils/calibration_6step.py::LiveRtoT_batch` (lines 2272-2370)
3. `core/data_acquisition_manager.py::_process_spectrum` (lines 1345-1410)

**All implement:**
- Dark noise removal
- Afterglow correction
- P/S ratio calculation
- LED boost correction (P_LED / S_LED)
- 95th percentile baseline correction
- Savitzky-Golay filtering (window=11, poly=3)

**Risk:**
- Algorithms can diverge during maintenance
- Bug fixes must be applied 3 times
- No single source of truth

---

### **Violation #3: Data Flow Bypasses Architecture**

**Current Flow (VIOLATES 4-LAYER):**
```
utils/calibration_6step.py (Layer ?)
  └─ LiveRtoT_QC()
       └─ Calculates transmission ❌ WRONG LAYER
            └─ result.transmission = transmission_ch
                 └─ CalibrationData (Layer 2 model)
                      └─ CalibrationQCDialog (Layer 4 widget)
                           └─ Displays graphs
```

**Flow skips Layer 3 (Coordinators)!**

**Correct Flow (FOLLOWS 4-LAYER):**
```
Layer 2: CalibrationService
  └─ perform_full_led_calibration()
       └─ Returns RAW P-pol and S-pol data (NO processing)
            └─ CalibrationData (RAW data only)

Layer 2: TransmissionProcessor (NEW)
  └─ process_for_qc(CalibrationData) ✅ Core logic
       └─ Applies transmission calculation
            └─ Returns TransmissionQCData

Layer 3: GraphCoordinator
  └─ prepare_qc_display(TransmissionQCData) ✅ Formatting
       └─ Formats for PyQtGraph
            └─ Returns display-ready dicts

Layer 4: CalibrationQCDialog
  └─ show_qc_report(display_data) ✅ Display only
       └─ Plots graphs (NO calculations)
```

---

## ✅ Refactoring Plan

### **Step 1: Create TransmissionProcessor (Layer 2)**

**New File:** `src/core/transmission_processor.py`

```python
"""Transmission spectrum processor - Core business logic (Layer 2).

Single source of truth for P/S ratio calculations used throughout application.
"""

import numpy as np
from typing import Dict, Optional
from scipy.signal import savgol_filter

class TransmissionProcessor:
    """Process raw P-pol spectra into transmission spectra.

    This is the ONLY place where transmission calculation logic exists.
    Used by:
    - Calibration QC display (LiveRtoT_QC replacement)
    - Live data acquisition (already integrated)
    - Post-calibration analysis
    """

    @staticmethod
    def process_single_channel(
        p_pol_raw: np.ndarray,
        s_pol_ref: np.ndarray,
        dark_noise: np.ndarray,
        afterglow_correction = None,
        prev_led_intensity: int = 0,
        p_integration_time: float = 93.0,
        led_intensity_s: int = 200,
        led_intensity_p: int = 255,
        wavelengths: np.ndarray = None,
        apply_sg_filter: bool = True
    ) -> np.ndarray:
        """Process ONE channel (for QC display with logging).

        Pipeline:
        1. Remove dark noise
        2. Remove afterglow (if provided)
        3. Calculate P/S ratio
        4. Correct for LED boost (P_LED / S_LED)
        5. Apply baseline correction (95th percentile)
        6. Clip to 0-100% range
        7. Apply Savitzky-Golay filter

        Returns:
            transmission: Transmission spectrum (%)
        """
        # Step 1: Remove dark noise
        p_pol_clean = p_pol_raw - dark_noise

        # Step 2: Remove afterglow
        if afterglow_correction is not None and prev_led_intensity > 0:
            afterglow = afterglow_correction.predict_afterglow(
                prev_led_intensity, p_integration_time
            )
            p_pol_clean = p_pol_clean - afterglow

        # Step 3: Calculate transmission (P / S)
        s_pol_safe = np.where(s_pol_ref < 1, 1, s_pol_ref)
        raw_transmission = (p_pol_clean / s_pol_safe) * 100.0

        # Step 4: LED boost correction
        led_boost_factor = max(led_intensity_p, 1) / max(led_intensity_s, 1)
        transmission = raw_transmission / led_boost_factor

        # Step 5: Baseline correction
        baseline = np.percentile(transmission, 95)
        transmission = transmission - baseline + 100.0

        # Step 6: Clip to valid range
        transmission = np.clip(transmission, 0, 100)

        # Step 7: Savitzky-Golay filter
        if apply_sg_filter and len(transmission) >= 11:
            transmission = savgol_filter(transmission, window_length=11, polyorder=3)

        return transmission

    @staticmethod
    def process_batch(
        p_pol_raw_batch: Dict[str, np.ndarray],
        s_pol_ref_batch: Dict[str, np.ndarray],
        dark_noise: np.ndarray,
        afterglow_correction = None,
        p_integration_time: float = 93.0,
        led_intensities_s: Dict[str, int] = None,
        led_intensities_p: Dict[str, int] = None,
        wavelengths: np.ndarray = None,
        ch_list: list = ['a', 'b', 'c', 'd'],
        apply_sg_filter: bool = True
    ) -> Dict[str, np.ndarray]:
        """Process ALL channels (for live view - optimized).

        Same pipeline as process_single_channel, but:
        - Minimal logging (performance)
        - Batch processing
        - Returns dict of transmission spectra
        """
        transmission_batch = {}

        for i, ch in enumerate(ch_list):
            if ch not in p_pol_raw_batch:
                continue

            # Get previous channel LED for afterglow
            prev_led = 0
            if i > 0 and afterglow_correction is not None:
                prev_ch = ch_list[i - 1]
                prev_led = led_intensities_p.get(prev_ch, 0)

            # Process this channel
            transmission_batch[ch] = TransmissionProcessor.process_single_channel(
                p_pol_raw=p_pol_raw_batch[ch],
                s_pol_ref=s_pol_ref_batch[ch],
                dark_noise=dark_noise,
                afterglow_correction=afterglow_correction,
                prev_led_intensity=prev_led,
                p_integration_time=p_integration_time,
                led_intensity_s=led_intensities_s.get(ch, 200),
                led_intensity_p=led_intensities_p.get(ch, 255),
                wavelengths=wavelengths,
                apply_sg_filter=apply_sg_filter
            )

        return transmission_batch
```

---

### **Step 2: Update calibration_6step.py (Remove LiveRtoT)**

**File:** `src/utils/calibration_6step.py`

```python
# ✅ REMOVE nested LiveRtoT_QC and LiveRtoT_batch functions (Lines 2165-2370)

def run_full_6step_calibration(...):
    # ... calibration code ...

    # ❌ DELETE:
    # def LiveRtoT_QC(...):
    # def LiveRtoT_batch(...):

    # ✅ NEW: Use TransmissionProcessor (Layer 2)
    from core.transmission_processor import TransmissionProcessor

    # Process transmission for QC display
    for ch in ch_list:
        prev_ch_idx = ch_list.index(ch) - 1 if ch_list.index(ch) > 0 else -1
        prev_led_intensity = result.p_mode_intensity[ch_list[prev_ch_idx]] if prev_ch_idx >= 0 else 0

        transmission_ch = TransmissionProcessor.process_single_channel(
            p_pol_raw=result.p_raw_data[ch],
            s_pol_ref=s_pol_ref[ch],
            dark_noise=result.dark_noise,
            afterglow_correction=afterglow_correction,
            prev_led_intensity=prev_led_intensity,
            p_integration_time=result.p_integration_time,
            led_intensity_s=result.ref_intensity[ch],
            led_intensity_p=result.p_mode_intensity[ch],
            wavelengths=result.wave_data,
            apply_sg_filter=True
        )

        transmission_spectra[ch] = transmission_ch
```

---

### **Step 3: Update data_acquisition_manager.py (Use TransmissionProcessor)**

**File:** `src/core/data_acquisition_manager.py`

```python
# ✅ REPLACE duplicated transmission calculation (Lines 1345-1410)

def _process_spectrum(self, ...):
    # ... existing code ...

    # ❌ DELETE: Inline transmission calculation (Lines 1370-1405)

    # ✅ NEW: Use TransmissionProcessor (same as calibration)
    from core.transmission_processor import TransmissionProcessor

    if channel in self.calibration_data.s_pol_ref:
        transmission_spectrum = TransmissionProcessor.process_single_channel(
            p_pol_raw=raw_spectrum,  # Already dark-corrected in acquisition
            s_pol_ref=self.calibration_data.s_pol_ref[channel],
            dark_noise=np.zeros_like(raw_spectrum),  # Already subtracted
            afterglow_correction=None,  # Already corrected if enabled
            prev_led_intensity=0,
            p_integration_time=self.calibration_data.p_integration_time,
            led_intensity_s=self.calibration_data.s_mode_intensities.get(channel),
            led_intensity_p=self.calibration_data.p_mode_intensities.get(channel),
            wavelengths=self.calibration_data.wavelengths,
            apply_sg_filter=True
        )
```

---

### **Step 4: Benefits of Refactoring**

✅ **Single Source of Truth**
- One implementation of transmission calculation
- Bug fixes applied once, work everywhere
- Algorithm consistency guaranteed

✅ **Correct Architecture**
- Core logic in Layer 2 (core/)
- Utils folder is stateless helpers only
- Proper separation of concerns

✅ **Maintainability**
- Clear ownership: TransmissionProcessor owns the algorithm
- Easy to unit test
- Easy to optimize (profiling, caching, vectorization)

✅ **Reusability**
- QC display uses it
- Live acquisition uses it
- Post-processing can use it
- Analysis tools can use it

---

## 📋 Migration Checklist

- [ ] Create `src/core/transmission_processor.py`
- [ ] Implement `TransmissionProcessor.process_single_channel()`
- [ ] Implement `TransmissionProcessor.process_batch()`
- [ ] Update `calibration_6step.py` to use TransmissionProcessor
- [ ] Update `data_acquisition_manager.py` to use TransmissionProcessor
- [ ] Remove `LiveRtoT_QC` function (Lines 2165-2270)
- [ ] Remove `LiveRtoT_batch` function (Lines 2272-2370)
- [ ] Test calibration QC display
- [ ] Test live data acquisition
- [ ] Verify transmission spectra match exactly
- [ ] Update documentation

---

## 🎯 Summary

**Current State:** 🔴 ARCHITECTURE VIOLATION
- Business logic in utils/ folder (wrong layer)
- Code duplicated 3 times (DRY violation)
- Data flow bypasses coordinators

**Target State:** ✅ CORRECT 4-LAYER ARCHITECTURE
- Core logic in Layer 2 (core/transmission_processor.py)
- Single source of truth
- Proper data flow through all layers
- Clean separation of concerns

**Priority:** HIGH - Affects maintainability and consistency

**Effort:** Medium (2-3 hours)
- Create TransmissionProcessor class
- Update 2 call sites
- Test thoroughly

---

**Created:** November 27, 2025
**Author:** Architecture Audit
**Status:** VIOLATION IDENTIFIED - FIX REQUIRED
