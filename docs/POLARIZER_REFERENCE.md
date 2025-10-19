# Polarizer System Reference Guide

**Consolidated reference for Affilabs 0.1.0 polarizer management**

This document consolidates all polarizer-related information from:
- `POLARIZER_QUICK_REFERENCE.md`
- `POLARIZER_HARDWARE_VARIANTS.md`
- `POLARIZER_POSITION_FIX_COMPLETE.md` (summary)

---

## Quick Reference

### SPR Physics (Correct Understanding)

For Surface Plasmon Resonance measurements:

**S-mode (Perpendicular Polarization)**:
- **Function**: Reference signal
- **Signal Level**: HIGH transmission (flat spectrum)
- **Usage**: Denominator in transmittance calculation
- **Window**: Uses the window with HIGHER signal

**P-mode (Parallel Polarization)**:
- **Function**: Measurement signal
- **Signal Level**: LOWER transmission (shows resonance dip)
- **Usage**: Numerator in transmittance calculation
- **Window**: Uses the window with LOWER signal

**Transmittance Calculation**:
```
Transmittance = P / S × 100%
```
- Results in resonance **DIP** (not peak)
- P signal is lower than S at resonance wavelength
- Typical S/P ratio: 3-15× (S is 3-15 times higher than P)

### Position Format

**Servo Position Scale**: 0-255 (raw servo units, NOT degrees)
- 0 = Minimum position
- 255 = Maximum position
- Typical working range: 10-240

**Example Configuration**:
```json
{
  "oem_calibration": {
    "polarizer_s_position": 165,  // HIGH transmission window
    "polarizer_p_position": 50,   // LOWER transmission window
    "polarizer_sp_ratio": 15.89   // S is 15.89× higher than P
  }
}
```

---

## Hardware Variants

### Barrel Polarizer (Recommended)

**Type**: Fixed dual-window polarizer
**Configuration**: Two orthogonal polarization windows at fixed angular positions
**Advantages**:
- No moving parts (very reliable)
- Instant switching between S and P modes (servo moves between two fixed positions)
- Consistent polarization state
- Low maintenance

**OEM Calibration Required**: YES
- Must empirically determine which window gives HIGH vs LOW signal
- Positions stored in `device_config.json` under `oem_calibration`
- Use `utils/oem_calibration_tool.py` to characterize

**Typical Positions**:
- Window 1: ~50-80 (either S or P depending on hardware)
- Window 2: ~165-180 (the other polarization)
- Gap between windows: ~90-115 servo units

### Rotating Polarizer (Legacy)

**Type**: Continuously rotating polarizer
**Configuration**: Single polarizing element rotated to desired angle
**Advantages**:
- Can access any polarization angle
- Flexible for non-standard measurements

**Disadvantages**:
- Moving parts (wear over time)
- Slower switching between modes
- Requires precise angle calibration
- More complex setup

**Support Status**: Legacy, not recommended for new installations

---

## OEM Calibration Process

### When to Run OEM Calibration

**Required for**:
- New hardware installation
- Replacing polarizer hardware
- After significant mechanical adjustments
- If polarizer validation fails during calibration

**Not required if**:
- Positions already configured in `device_config.json`
- System previously calibrated and working correctly

### Running OEM Calibration Tool

```powershell
# Activate environment
.\.venv\Scripts\Activate.ps1

# Run OEM calibration tool
python utils/oem_calibration_tool.py --serial YOUR_DEVICE_SERIAL

# Tool will:
# 1. Scan both polarizer windows
# 2. Measure signal intensity at each position
# 3. Determine which window is S (HIGH) vs P (LOWER)
# 4. Calculate S/P ratio
# 5. Save results to device_config.json
```

### Expected S/P Ratios

- **Good**: 3-15× (S is 3-15 times higher than P)
- **Acceptable**: 2-20× (still usable)
- **Poor**: <2× or >20× (check hardware alignment)

**If ratio is too low (<2×)**:
- Check fiber coupling alignment
- Verify LED intensity
- Inspect polarizer for damage
- Ensure clean optical path

**If ratio is too high (>20×)**:
- P-mode may be too close to extinction angle
- Consider adjusting mechanical setup
- System may still work but with reduced P-mode signal

---

## Validation During Calibration

### Step 2B: Polarizer Position Validation

**Automatic validation during calibration**:
1. Positions loaded from `device_config.json` → `oem_calibration` section
2. Servo moves to S position
3. Signal measured (expect HIGH intensity)
4. Servo moves to P position
5. Signal measured (expect LOWER intensity)
6. S/P ratio calculated and validated

**Validation Criteria**:
```python
S/P ratio > 2.0  # Minimum acceptable
S/P ratio 3-15   # Optimal range
```

**If validation fails**:
- Error: "Polarizer positions invalid - run auto-polarization from Settings"
- Action: Run OEM calibration tool to reconfigure positions

### Manual Validation (Settings Tab)

Can also validate from application Settings tab:
1. Open Settings → Polarizer Configuration
2. Click "Validate Positions"
3. System will test S and P positions
4. Results displayed with S/P ratio

---

## Troubleshooting

### Problem: Servo barely moves during calibration

**Symptom**: Servo only moves a few units (e.g., 50→80 instead of 50→165)

**Causes**:
1. Positions not loaded from config
2. Positions swapped (using wrong values)
3. Config not saved after OEM calibration

**Solution**:
1. Check `device_config.json` has `oem_calibration` section
2. Run OEM calibration tool if missing
3. Restart application to reload config

### Problem: Transmittance shows peak instead of dip

**Symptom**: SPR curve inverted (peak at resonance wavelength instead of dip)

**Cause**: S and P positions swapped (P using HIGH window, S using LOWER window)

**Solution**:
1. Run OEM calibration tool - it will determine correct positions
2. Alternatively, manually swap positions in `device_config.json`:
   ```json
   // If you have:
   "polarizer_s_position": 50,
   "polarizer_p_position": 165,

   // Try swapping to:
   "polarizer_s_position": 165,
   "polarizer_p_position": 50,
   ```
3. Restart application and recalibrate

### Problem: P-mode saturating detector

**Symptom**: P-mode intensity readings at or near detector max (65535 counts)

**Cause**: P-mode using HIGH transmission window (should use LOWER window)

**Solution**: Same as above - positions are swapped, run OEM calibration

### Problem: S/P ratio validation fails

**Symptom**: Calibration stops at Step 2B with "Invalid polarizer positions"

**Causes**:
1. S/P ratio < 2.0 (insufficient polarization contrast)
2. Hardware misalignment
3. Wrong positions configured

**Solutions**:
1. Run OEM calibration tool for fresh characterization
2. Check fiber coupling and LED intensity
3. Inspect polarizer hardware for damage
4. Verify optical path is clean and unobstructed

---

## Configuration File Format

### Location
`config/device_config.json`

### Structure
```json
{
  "hardware": {
    "device_type": "PicoP4SPR",
    "serial_port": "COM4",
    // ... other hardware config
  },

  "oem_calibration": {
    "polarizer_s_position": 165,
    "polarizer_p_position": 50,
    "polarizer_sp_ratio": 15.89,
    "calibration_method": "window_verification_corrected",
    "calibrated_at": "2025-10-19T03:05:00-04:00",
    "calibrated_by": "OEM barrel polarizer characterization"
  }
}
```

### Important Notes

**Single Source of Truth**:
- `oem_calibration` section is the **only** authoritative source for positions
- Do not hardcode positions elsewhere in code
- Always load from device_config.json

**Validation Required**:
- Positions must be present before calibration
- System will not use default values
- Missing positions will cause calibration failure

**Manual Editing** (Not Recommended):
- Only edit if you know exact positions from hardware testing
- OEM tool is preferred method
- After editing, test with validation before full calibration

---

## API Reference

### Loading Positions from Config

```python
from utils.device_configuration import get_device_config

# Load device configuration
config = get_device_config()
config_dict = config.to_dict()

# Access OEM calibration data
oem_cal = config_dict.get('oem_calibration', {})
s_pos = oem_cal.get('polarizer_s_position')
p_pos = oem_cal.get('polarizer_p_position')
sp_ratio = oem_cal.get('polarizer_sp_ratio')
```

### Applying Positions to Hardware

```python
# In calibration, positions stored in state
self.state.polarizer_s_position = s_pos
self.state.polarizer_p_position = p_pos

# Applied to hardware during mode switching
self.ctrl.set_mode(mode="s")  # Servo moves to S position
self.ctrl.set_mode(mode="p")  # Servo moves to P position
```

### Validation Method

```python
# In SPRCalibrator
def validate_polarizer_positions(self) -> bool:
    """Validate polarizer positions by measuring S/P ratio.

    Returns:
        True if positions valid (S/P ratio > 2.0), False otherwise
    """
    # Measure S-mode intensity
    s_signal = measure_at_s_position()

    # Measure P-mode intensity
    p_signal = measure_at_p_position()

    # Calculate ratio (S should be higher than P)
    ratio = s_signal / p_signal

    # Validate
    if ratio < 2.0:
        logger.error("Polarizer validation failed: S/P ratio too low")
        return False

    # Store in state
    self.state.polarizer_sp_ratio = ratio
    return True
```

---

## Best Practices

### 1. Always Use OEM Calibration Tool
- **Don't** guess positions or use values from other systems
- **Do** run empirical characterization for each hardware unit
- Positions vary between devices even with identical hardware

### 2. Document Your Configuration
- Save OEM tool output
- Note calibration date and conditions
- Record S/P ratio for future reference
- Keep backup of working `device_config.json`

### 3. Verify After Changes
- Run validation after any hardware adjustment
- Recalibrate fully after changing positions
- Check that transmittance shows dip (not peak)

### 4. Monitor S/P Ratio Over Time
- Ratio should remain stable (±10%)
- Significant drift indicates hardware issue
- Recalibrate if ratio changes >20%

### 5. Handle Errors Gracefully
- System will fail calibration if positions invalid
- User gets clear message to run OEM tool
- Never use default/fallback positions for polarizer

---

## Version History

**Affilabs 0.1.0** (2025-10-19):
- Implemented single source of truth in device_config.json
- Created OEM calibration tool for empirical characterization
- Fixed S/P position swap bug (major fix)
- Added validation during calibration Step 2B
- Corrected SPR physics documentation throughout codebase

**Future Enhancements**:
- GUI-based OEM calibration wizard
- Automatic position optimization
- Historical S/P ratio tracking
- Multi-device position profiles

---

## Related Documentation

- **OEM_CALIBRATION_TOOL_GUIDE.md** - Detailed tool usage guide
- **SETTINGS_QUICK_REFERENCE.md** - Settings tab configuration
- **POLARIZER_POSITION_FIX_COMPLETE.md** - Historical fix documentation (archive)
- **SIMPLIFIED_ARCHITECTURE_README.md** - System architecture overview

---

**Document Version**: 1.0
**Last Updated**: October 19, 2025
**Affilabs Version**: 0.1.0
