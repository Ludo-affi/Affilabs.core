# Hardware Detection Fix - SeaBreeze Support

**Date**: October 11, 2025
**Issue**: Spectrometer not detected in GUI
**Status**: ✅ FIXED

---

## Problem

The hardware detection GUI could not find the Ocean Optics spectrometer, even though it was connected and working in the main application.

**Symptoms**:
- Pico controller detected ✅
- Spectrometer not detected ❌

---

## Root Cause

The spectrometer uses **SeaBreeze** (Ocean Optics native USB protocol), **not a serial port**. The original hardware detector only scanned serial ports (VID:PID).

**Key Differences**:

| Device | Connection Method |
|--------|-------------------|
| **Pico Controller** | Serial port (COM4) - VID:PID 2E8A:000A |
| **Spectrometer** | SeaBreeze USB (direct) - No serial port! |

---

## Solution

Updated `utils/hardware_detection.py` to use **SeaBreeze** for spectrometer detection:

### Change 1: Added SeaBreeze Detection

```python
# Try SeaBreeze detection first (Ocean Optics native USB)
try:
    import seabreeze
    # Use cseabreeze (C backend) - more reliable than pyseabreeze
    seabreeze.use('cseabreeze')
    from seabreeze.spectrometers import list_devices, Spectrometer

    devices = list_devices()

    if devices:
        device = devices[0]
        spec = Spectrometer(device)

        spec_info = {
            'device': 'SeaBreeze',
            'name': spec.model,
            'description': f"Ocean Optics {spec.model}",
            'serial_number': spec.serial_number,
            'manufacturer': 'Ocean Optics',
            'product': spec.model,
            'connection_type': 'USB (SeaBreeze)',
        }

        spec.close()
        return spec_info

except Exception as e:
    logger.debug(f"SeaBreeze detection failed: {e}")

# Fallback to serial port detection (CP210x)
# ... existing code ...
```

### Change 2: Use cseabreeze Backend

**Critical**: Must use `cseabreeze` (C backend), not `pyseabreeze`:
- ✅ `seabreeze.use('cseabreeze')` - Works!
- ❌ `seabreeze.use('pyseabreeze')` - "No pyusb backend found"

---

## Testing Results

### Before Fix:
```
Spectrometer: ❌ Not found
Controller:   ✅ Detected
```

### After Fix:
```
✅ Spectrometer FOUND on SeaBreeze
   Model: USB4000
   Serial: FLMT09788

✅ Controller FOUND on COM4
   VID:PID = 2E8A:000A
```

---

## Detected Hardware

Your system configuration:

| Component | Details |
|-----------|---------|
| **Spectrometer** | Ocean Optics USB4000 (actually Flame-T) |
| **Serial Number** | FLMT09788 |
| **Connection** | USB (SeaBreeze native protocol) |
| **Backend** | cseabreeze (C library) |
| | |
| **Controller** | Raspberry Pi Pico P4SPR |
| **Serial Number** | E6614864D3147C21 |
| **Port** | COM4 |
| **VID:PID** | 2E8A:000A |

---

## GUI Usage

Now the "Detect Hardware" button in the Device Configuration GUI will:

1. ✅ Detect spectrometer via SeaBreeze
2. ✅ Detect Pico controller via serial port scan
3. ✅ Extract serial numbers automatically
4. ✅ Update configuration with detected hardware

**To test**:
```bash
python -m widgets.device_settings
```

Click "🔍 Detect Hardware" button → Both devices now detected!

---

## Technical Notes

### Why SeaBreeze?

Ocean Optics spectrometers use proprietary USB protocol, not standard serial communication:

- **USB4000/Flame-T**: Direct USB via SeaBreeze library
- **QE Pro**: Direct USB via SeaBreeze library
- **Some older models**: CP210x USB-to-Serial chip (VID:PID 10C4:EA60)

Your USB4000 (Flame-T) uses **direct USB**, so it never appears as a COM port.

### Backend Choice

SeaBreeze supports two backends:

1. **cseabreeze** (C library):
   - ✅ Faster
   - ✅ More stable
   - ✅ Works on your system
   - Requires compiled C library

2. **pyseabreeze** (Pure Python):
   - ✅ Pure Python (easier to install)
   - ❌ Requires pyusb backend (libusb/WinUSB)
   - ❌ Not working on your system ("No pyusb backend found")

**Solution**: Always use `cseabreeze` for reliability.

---

## Files Modified

| File | Changes |
|------|---------|
| `utils/hardware_detection.py` | Added SeaBreeze detection before serial port scan |
| `test_hardware_detection.py` | Created test script for debugging |

---

## Verification

Run test script to verify detection:
```bash
python test_hardware_detection.py
```

Expected output:
```
✅ Spectrometer FOUND on SeaBreeze
   Model: USB4000
   Serial: FLMT09788

✅ Controller FOUND on COM4
   VID:PID = 2E8A:000A
```

---

## Summary

**Problem**: Hardware detector couldn't find spectrometer
**Cause**: Spectrometer uses SeaBreeze USB (not serial port)
**Fix**: Added SeaBreeze detection with cseabreeze backend
**Result**: Both devices now detected correctly ✅

**GUI now working**: Device Configuration tab can detect all hardware!

---

*Issue resolved October 11, 2025*
