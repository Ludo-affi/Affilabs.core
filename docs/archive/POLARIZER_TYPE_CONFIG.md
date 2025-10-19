# Polarizer Type Configuration

**Date**: October 19, 2025
**Status**: ✅ Implemented in Device Configuration System

---

## Overview

The device configuration system now includes a `polarizer_type` field to document which type of polarizer hardware is installed in each SPR device. This information is stored alongside other hardware specifications like optical fiber diameter and LED PCB model.

---

## Polarizer Types

### **1. Barrel Polarizer** (`'barrel'`)

**Hardware Description**:
- Two **fixed perpendicular polarization windows** mounted in a rotating barrel
- Servo rotates barrel to align each window with the optical beam
- Polarization angles are **hardware-fixed** and cannot be adjusted

**Characteristics**:
- Only **2 viable servo positions** (alignment with fixed windows)
- S/P intensity ratio: **1.5-2.5×** (hardware-limited)
- OEM calibration finds optimal alignment positions
- Example positions: S=141, P=55 (0-255 PWM scale)

**Expected S/P Ratio**: ✅ **1.5-2.5× is ACCEPTABLE** (hardware limitation)

---

### **2. Round Polarizer** (`'round'`)

**Hardware Description**:
- Single **continuously rotating** polarization element
- Smooth intensity variation at all angles
- Polarization angle adjustable through servo position

**Characteristics**:
- **Many viable positions** with varying transmission
- S/P intensity ratio: **3.0-15.0×** (optimizable)
- OEM calibration finds global maximum and minimum
- Broader range of optimal positions

**Expected S/P Ratio**: ✅ **>3.0× is EXCELLENT** (optimized positioning)

---

## Configuration Structure

### File Location
```
config/device_config.json
```

### JSON Schema
```json
{
  "hardware": {
    "led_pcb_model": "luminus_cool_white",
    "optical_fiber_diameter_um": 200,
    "polarizer_type": "barrel",  // 👈 NEW FIELD
    "spectrometer_model": "Flame-T",
    "spectrometer_serial": "FLMT12345",
    "controller_model": "Raspberry Pi Pico P4SPR"
  }
}
```

### Valid Values
- `"barrel"` - Barrel polarizer with 2 fixed perpendicular windows (default)
- `"round"` - Round polarizer with continuous rotation

---

## API Usage

### **Import Configuration**
```python
from utils.device_configuration import DeviceConfiguration

config = DeviceConfiguration()
```

### **Get Polarizer Type**
```python
polarizer_type = config.get_polarizer_type()
# Returns: "barrel" or "round"
```

### **Set Polarizer Type**
```python
# Set to barrel polarizer
config.set_polarizer_type("barrel")

# Set to round polarizer
config.set_polarizer_type("round")

# Save changes to disk
config.save()
```

### **Validation**
```python
# Validation happens automatically
config.set_polarizer_type("invalid")  # ❌ Raises ValueError

# Valid options:
valid_types = config.VALID_POLARIZER_TYPES  # ['barrel', 'round']
```

---

## Integration with OEM Calibration

The polarizer type determines expected S/P ratio validation thresholds during OEM calibration:

```python
# In utils/oem_calibration_tool.py
from utils.device_configuration import DeviceConfiguration

config = DeviceConfiguration()
polarizer_type = config.get_polarizer_type()

if polarizer_type == "barrel":
    # Expect 1.5-2.5× ratio (hardware limited)
    min_ratio = 1.5
    warn_ratio = 2.5
elif polarizer_type == "round":
    # Expect >3.0× ratio (optimizable)
    min_ratio = 3.0
    warn_ratio = 5.0
```

### Validation Thresholds

| Polarizer Type | Min Acceptable | Good Range | Excellent |
|----------------|---------------|------------|-----------|
| **Barrel**     | 1.5×          | 1.5-2.5×   | 2.5-3.0×  |
| **Round**      | 3.0×          | 3.0-5.0×   | >5.0×     |

---

## Configuration Summary Display

When loading device configuration, the polarizer type is displayed:

```
============================================================
DEVICE CONFIGURATION SUMMARY
============================================================
  LED PCB Model: luminus_cool_white
  Optical Fiber: 200 µm
  Polarizer Type: barrel (2 fixed windows)
  Spectrometer: Flame-T (S/N: FLMT12345)
  Controller: Raspberry Pi Pico P4SPR
  Factory Calibrated: Yes
  User Calibrated: Yes
============================================================
```

---

## Backward Compatibility

**Default Value**: `"barrel"`

- Existing configuration files without `polarizer_type` field default to `"barrel"`
- `get_polarizer_type()` returns `"barrel"` if field is missing
- No breaking changes to existing devices

---

## Factory Provisioning

During factory setup, operators should:

1. **Physically inspect** the polarizer hardware
2. **Set polarizer type** in device configuration:
   ```python
   config.set_polarizer_type("barrel")  # or "round"
   config.save()
   ```
3. **Run OEM calibration** to find optimal S/P positions
4. **Validate S/P ratio** matches expected range for hardware type

---

## Documentation Reference

- **Hardware Comparison**: `POLARIZER_HARDWARE_VARIANTS.md`
- **Single Source of Truth**: `POLARIZER_SINGLE_SOURCE_OF_TRUTH.md`
- **Configuration Guide**: `CONFIG_QUICK_REFERENCE.md`
- **OEM Calibration**: `utils/oem_calibration_tool.py`

---

## Quick Reference

| Action | Code |
|--------|------|
| Get polarizer type | `config.get_polarizer_type()` |
| Set to barrel | `config.set_polarizer_type("barrel")` |
| Set to round | `config.set_polarizer_type("round")` |
| Valid options | `config.VALID_POLARIZER_TYPES` |
| Save changes | `config.save()` |

---

## Benefits

✅ **Hardware Documentation**: Clear record of which polarizer variant is installed
✅ **Calibration Validation**: Set appropriate S/P ratio thresholds per hardware type
✅ **Troubleshooting**: Quickly identify if S/P ratio is within expected range
✅ **Manufacturing**: Track hardware variants across deployed devices
✅ **Single Source of Truth**: Device configuration is authoritative for all hardware specs

---

## Example: Complete Device Setup

```python
from utils.device_configuration import DeviceConfiguration

# Create configuration
config = DeviceConfiguration()

# Set hardware specifications
config.set_led_pcb_model("luminus_cool_white")
config.set_optical_fiber_diameter(200)
config.set_polarizer_type("barrel")  # 👈 Document polarizer hardware
config.set_spectrometer_serial("FLMT12345")

# Save to disk
config.save()

# Verify
print(f"Fiber: {config.get_optical_fiber_diameter()} µm")
print(f"Polarizer: {config.get_polarizer_type()}")
# Output:
# Fiber: 200 µm
# Polarizer: barrel
```

---

## Status

✅ **IMPLEMENTED**: Polarizer type field added to device configuration system
✅ **VALIDATED**: Configuration validation includes polarizer type
✅ **DOCUMENTED**: Added to configuration summary logging
✅ **BACKWARD COMPATIBLE**: Defaults to "barrel" for existing configs

---

## Next Steps (Optional)

1. **Update OEM Tool**: Use polarizer type to set S/P ratio validation thresholds
2. **Update Factory Script**: Prompt operator to select polarizer type during provisioning
3. **Update UI**: Add polarizer type selection to Device Settings widget
4. **Analytics**: Track S/P ratio statistics by polarizer type

---

**For more details, see:**
- `utils/device_configuration.py` - Implementation
- `POLARIZER_HARDWARE_VARIANTS.md` - Hardware comparison
- `POLARIZER_SINGLE_SOURCE_OF_TRUTH.md` - Architecture overview
