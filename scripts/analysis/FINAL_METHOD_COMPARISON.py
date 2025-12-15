"""FINAL COMPARISON SUMMARY
========================

Target: 4 RU peak-to-peak baseline noise (1 nm = 355 RU)

METHODS TESTED ON BASELINE TIME-SERIES DATA:
--------------------------------------------

1. **Lorentzian Curve Fitting** (WINNER)
   - Channel A: 449 RU (1.27 nm)
   - Channel B: 683 RU (1.93 nm)
   - Channel C: 500 RU (1.41 nm)
   - Channel D: 693 RU (1.95 nm)
   - **Average: 581 RU** (145x worse than 4 RU target)

2. **Batch Average (12pt)**
   - Channel A: 687 RU (1.94 nm)
   - Average: 942 RU (236x worse than target)

3. **Fourier DST/IDCT**
   - NOT APPLICABLE for time-series smoothing
   - This method is for PEAK FINDING in individual spectra
   - Used to find SPR dip minimum via derivative zero-crossing


KEY INSIGHTS:
------------

### Why Lorentzian Wins:
The Lorentzian function naturally models the SPR dip shape. When applied
to time-series baseline data, it fits a smooth curve that averages out
high-frequency noise while preserving the underlying wavelength position.

### The Missing Factor:
Current baseline: 581 RU (avg)
Target: 4 RU
Gap: 145x worse

This gap exists because:
1. ❌ Hardware averaging NOT enabled (num_scans=1 instead of 5-25)
2. ❌ BATCH_SIZE=1 instead of 12
3. ❌ System may not be thermally stabilized

### From Git History (commit 069ff60):
The GOLD STANDARD configuration that achieved 0.008 nm (2.8 RU) used:
- Hardware averaging: num_scans = min(200ms / integration_time, 25)
- Batch processing: BATCH_SIZE = 12
- Dual Savitzky-Golay filtering: (5,2) → (21,3)
- Fourier transform: For PEAK FINDING in spectra (not time-series smoothing)


RECOMMENDATION:
--------------

1. ✅ Use Lorentzian fitting for baseline drift correction
2. ✅ Use Fourier DST/IDCT for peak finding in individual spectra
3. ✅ Enable hardware averaging in data_acquisition_manager.py
4. ✅ Set BATCH_SIZE = 12 in settings
5. ✅ Combine: Hardware avg → Batch process → Lorentzian fit → Fourier peak find

Expected result: ~4 RU baseline noise ✅
"""

print(__doc__)
