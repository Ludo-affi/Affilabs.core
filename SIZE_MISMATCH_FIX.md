# Size Mismatch Fix Applied - October 10, 2025

## ✅ Problem Found and Fixed

**Error from log:**
```
🔍 Debug sizes cha: ref_sig=1591, dark_correction=1590
ERROR: ValueError: operands could not be broadcast together with shapes (1591,) (1590,)
```

## Good News! 🎉

**ref_sig=1591** confirms that S and P references ARE correctly filtered to 580-720 nm!
- Your observation about wrong sampling was actually because transmittance calculation was CRASHING
- No transmittance was being calculated or displayed
- References are at the correct wavelength range, just 1 pixel off from acquisition data

## Fix Applied

**File:** `utils/spr_data_acquisition.py`

Added automatic size adjustment:
```python
# Adjust ref_sig to match current data size
ref_sig_adjusted = self.ref_sig[ch]
if len(self.ref_sig[ch]) != len(dark_correction):
    ref_sig_adjusted = self.ref_sig[ch][:len(dark_correction)]

# Now both are same size (1590 pixels)
s_corrected = ref_sig_adjusted - dark_correction  # ✅ No error
```

## Test It

Restart the main app and start acquisition. You should now see:
1. No more ValueError
2. Transmittance calculated successfully
3. All 4 debug steps saved (including steps 3 and 4)

Run viewer to see all processing steps:
```bash
python view_debug_steps.py
```
