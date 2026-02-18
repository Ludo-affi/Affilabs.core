# Pico P4SPR V2.2 FINAL Firmware - Golden Version

**Branch**: `firmware-v2.2-golden`
**Tag**: `v2.2-golden`
**Date**: December 13, 2025
**Status**: ✅ VERIFIED WORKING

---

## What Changed

### V2.2 Firmware Features
- **Hardware Timer LED Sequencing**: LEDs controlled by hardware timer instead of software delays
- **Improved Timing Precision**: Jitter-free LED switching
- **USB CDC Protocol**: Same serial commands as V1.9, different handshake requirements

### Critical Fixes Applied

#### 1. Serial Communication (DTR/RTS Handshake)
**File**: `affilabs/utils/controller.py`

```python
# BEFORE (V1.9 worked fine)
self._ser = serial.Serial(port=dev.device, baudrate=115200, timeout=0.30)

# AFTER (V2.2 requirement)
self._ser = serial.Serial(
    port=dev.device, baudrate=115200, timeout=1.0,
    dsrdtr=True, rtscts=False,
)
# Explicitly set control lines
self._ser.dtr = True
self._ser.rts = True
time.sleep(0.1)  # 100ms settle time

# Increased response timeout
time.sleep(0.5)  # Was 0.2s, now 0.5s
```

**Why**: Pico V2.2 USB CDC requires DTR/RTS assertion before accepting commands.

#### 2. Spectrometer Detection (libusb)
**File**: `affilabs/utils/libusb_init.py`

Added search path for user site-packages:
```python
import site
user_site = site.getusersitepackages()
search_paths.append(os.path.join(user_site, "libusb_package", "libusb-1.0.dll"))
```

**Dependencies**:
```bash
pip install pyusb libusb-package
```

#### 3. UI Compatibility
**File**: `affilabs/ui/ui_message.py`

Fixed QMessageBox parent type checking for PySide6.

---

## Verification Steps

### 1. Firmware Test (Manual)
```powershell
$port = New-Object System.IO.Ports.SerialPort COM5,115200,None,8,One
$port.DtrEnable = $true
$port.RtsEnable = $true
$port.Open()
Start-Sleep -Milliseconds 100
$port.WriteLine("id")
Start-Sleep -Milliseconds 500
$response = $port.ReadExisting()
$port.Close()
Write-Host "Response: '$response'"
```

**Expected**: `P4SPR V2.2`

### 2. Application Test
1. Launch application: `python main-simplified.py`
2. Click Power button
3. Verify logs show:
   - `Pico P4SPR ID reply: 'P4SPR'`
   - `[OK] Controller connected: PicoP4SPR`
   - `Spectrometer: Flame-T (S/N: FLMT09116)` (if detector present)

### 3. Calibration Test
- LED calibration should complete successfully
- Hardware timer ensures precise timing
- No "device already opened" errors

---

## Files Modified

| File | Changes |
|------|---------|
| `affilabs/utils/controller.py` | DTR/RTS handshake, timeout adjustments (4 locations) |
| `affilabs/core/hardware_manager.py` | Removed debug logs, kept test mode |
| `affilabs/utils/libusb_init.py` | Added user site-packages search |
| `affilabs/ui/ui_message.py` | Fixed QMessageBox parent handling |

---

## Controller Detection Logic

```
1. VID/PID Scan (0x2E8A:0x000A)
   ├─ Found COM5 → Open port
   ├─ Set DTR=True, RTS=True
   ├─ Wait 100ms (settle)
   ├─ Flush buffers
   ├─ Send "id\n"
   ├─ Wait 500ms (V2.2 requirement)
   └─ Read response → "P4SPR V2.2\r\n"

2. Version Query
   ├─ Send "iv\n"
   ├─ Wait 200ms
   └─ Read version → "V2.2"

3. Validation
   ├─ Controller: P4SPR ✓
   ├─ Detector: FLAME-T (if present) ✓
   └─ Combined: Valid SPR device ✓
```

---

## Known Issues (Non-blocking)

1. **Test Mode Active**: `hardware_manager.py` line 668 allows controller without detector
   - Remove for production: `ctrl_type = None` instead of adding to valid_hardware

2. **libusb Warning**: `seabreeze.use has to be called before instantiating` on first run
   - Harmless, pyseabreeze backend loads correctly

---

## Migration from V1.9

**No changes needed** - V2.2 is backward compatible with V1.9 software after applying these fixes.

Existing installations:
1. Flash V2.2 firmware to Pico
2. Pull `firmware-v2.2-golden` branch
3. Install dependencies: `pip install pyusb libusb-package`
4. Test connection

---

## Production Checklist

Before deployment:
- [ ] Remove test mode in `hardware_manager.py` (line 668)
- [ ] Verify DTR/RTS flags in all 4 controller classes
- [ ] Test with multiple detector types (USB4000, FLAME-T, FLAME-S)
- [ ] Validate timing with hardware timer (scope measurement)
- [ ] Update firmware in production units

---

## Contact

Issues with V2.2 firmware or hardware detection:
- Check COM port enumeration: Device Manager → Ports
- Verify VID/PID: `0x2E8A:0x000A` (Raspberry Pi Pico)
- Test serial manually with PowerShell script above
- Check logs for "DTR/RTS set to True" message

**Golden Version Commit**: `9a7b619`
