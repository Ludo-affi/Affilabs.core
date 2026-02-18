# Hardware Connection & Scan Behavior - REFERENCE DOCUMENT

**Location:** `Affilabs.core beta/README_HARDWARE_BEHAVIOR.md`
**Date:** November 22, 2025
**Purpose:** Central reference for hardware connection logic - READ THIS FIRST

---

## 🔌 Power Button Behavior

### States:
- **GRAY (disconnected)**: No hardware connected
- **YELLOW (searching)**: Scanning for hardware
- **GREEN (connected)**: Hardware connected and ready

### Click Actions:
```
GRAY → Click → YELLOW (start scan)
YELLOW → Click → GRAY (cancel scan)
GREEN → Click → Confirm dialog → GRAY (disconnect)
```

### Important Rules:
1. ✅ Clicking while YELLOW **cancels** the scan immediately
2. ✅ Backend returns to GRAY automatically if no hardware found
3. ✅ Button only turns GREEN when hardware is **actually connected**
4. ✅ No infinite cycling - user has full control

**File:** `affilabs_core_ui.py` → `_handle_power_click()`

---

## 🔍 Scan for Hardware Button (Device Status Widget)

### Purpose:
Re-scan USB devices and update Device Status display without disconnecting current hardware.

### Important Rule:
**⚠️ IF HARDWARE IS ALREADY CONNECTED, SCANNING AGAIN WILL NOT DISCONNECT IT**

This is handled in `core/hardware_manager.py`:

```python
def scan_and_connect(self):
    """Scan for and connect to all available hardware (non-blocking)."""
    if self._connecting:
        logger.warning("Connection already in progress")
        return

    # Check if hardware is already connected
    if any([self.ctrl, self.knx, self.pump, self.usb]):
        logger.info("Hardware already connected - reporting current status without re-scanning")
        # Just report current status without disconnecting
        status = {
            'ctrl_type': self._get_controller_type(),
            'knx_type': self._get_kinetic_type(),
            'pump_connected': self.pump is not None,
            'spectrometer': self.usb is not None,
            'sensor_ready': self._sensor_verified,
            'optics_ready': self._optics_verified,
            'fluidics_ready': self.pump is not None
        }
        self.hardware_connected.emit(status)
        return  # EXIT - no re-scan needed

    # Only scan if no hardware is currently connected
    self._connecting = True
    self.connection_progress.emit("Scanning for hardware...")
    # ... scanning logic ...
```

### Behavior:
```
IF hardware already connected:
    → Report current status
    → Do NOT disconnect
    → Do NOT re-scan USB
    → EXIT immediately

IF no hardware connected:
    → Scan USB devices
    → Try to connect
    → Update status
```

**File:** `core/hardware_manager.py` → `scan_and_connect()`

---

## 📋 Device Type Identification Logic

### Detection Rules:

```python
# ONLY what is physically plugged in determines device type

If Arduino OR PicoP4SPR detected alone:
    → Device = "P4SPR"

If PicoP4SPR + RPi (kinetic controller) detected:
    → Device = "P4SPR+KNX" or "ezSPR" (check serial number list)

If PicoEZSPR detected:
    → Device = "P4PRO"

If NOTHING detected:
    → Device = "" (empty)
    → Power button returns to GRAY
    → NO green button
    → NO hardware status displayed
```

### Controller Name Mapping:
- `name = 'p4spr'` → Arduino-based P4SPR
- `name = 'pico_p4spr'` → Pico-based P4SPR
- `name = 'pico_ezspr'` → Pico-based ezSPR (P4PRO)

**File:** `core/hardware_manager.py` → `_get_controller_type()`

---

## 🔧 Connection Workflow

### Step-by-Step:

1. **User clicks Power Button (gray)**
   - UI: Button turns YELLOW
   - UI: Emits `power_on_requested` signal
   - Backend: Receives signal, calls `hardware_manager.scan_and_connect()`

2. **Backend scans USB devices**
   - Checks if already connected → skip scan, report status
   - If not connected → scan for:
     - Spectrometer (Ocean Optics)
     - Controller (Arduino, PicoP4SPR, PicoEZSPR)
     - Kinetic controller (KNX2, PicoKNX2)
     - Pump (CAVRO via FTDI)

3. **Backend emits `hardware_connected` signal**
   - Always emits, even if nothing found
   - Status dict includes: ctrl_type, knx_type, pump_connected, spectrometer, etc.

4. **Frontend receives status**
   - If ANY hardware found → Button turns GREEN
   - If NO hardware found → Button returns to GRAY
   - Updates Device Status UI with connected hardware

5. **Device Status Updated**
   - Shows controller type (P4SPR, P4SPR+KNX, P4PRO)
   - Shows kinetic system (KNX2, etc.)
   - Shows pump status
   - Shows spectrometer status

**Files:**
- UI: `affilabs_core_ui.py` → `_handle_power_click()`
- Backend: `main_simplified.py` → `_on_power_on_requested()`, `_on_hardware_connected()`
- Hardware: `core/hardware_manager.py` → `scan_and_connect()`, `_connection_worker()`

---

## ⚠️ What NOT to Do

### ❌ DON'T:
1. Re-scan hardware when already connected (it will just report current status)
2. Assume power button can cycle indefinitely (it can be cancelled)
3. Check for hardware using names other than those in controllers
4. Create new "scan" behaviors without reading this doc first

### ✅ DO:
1. Use `scan_and_connect()` for new hardware detection
2. Let backend handle device type identification
3. Trust the power button state machine
4. Check this doc before modifying connection logic

---

## 📁 Related Files

| File | Purpose |
|------|---------|
| `affilabs_core_ui.py` | Main UI window, power button logic |
| `main_simplified.py` | Application layer, signal handlers |
| `core/hardware_manager.py` | Hardware detection and connection |
| `utils/controller.py` | Controller implementations (Arduino, Pico, etc.) |
| `widgets/sidebar_modern.py` | Device Status widget with Scan button |

---

## 🐛 Troubleshooting

### Power button stuck in YELLOW:
- Click it to cancel
- Check backend logs for connection errors
- Verify `hardware_connected` signal is being emitted

### Device shows "P4SPR" instead of "P4SPR+KNX":
- Check if kinetic controller is connected
- Verify `self.knx` is not None in hardware_manager
- Check `_get_controller_type()` logic

### Scan button doesn't find hardware:
- Check USB connections
- Check if hardware is already connected (won't re-scan)
- Check driver installation (Ocean Optics, FTDI)

### "No hardware found" even though devices are plugged in:
- Check VID:PID values in `utils/controller.py`
- Verify USB devices with: `python -c "import usb.core; [print(f'{hex(d.idVendor)}:{hex(d.idProduct)}') for d in usb.core.find(find_all=True)]"`
- Check serial port access (may need admin rights)

---

## 📝 Quick Reference

### Adding New Controller Type:
1. Add controller class to `utils/controller.py`
2. Add detection logic to `hardware_manager._connect_controller()`
3. Add device type mapping to `hardware_manager._get_controller_type()`
4. Update Device Status display in `widgets/sidebar_modern.py`

### Modifying Connection Behavior:
1. **READ THIS DOC FIRST**
2. Update `hardware_manager.scan_and_connect()` if changing scan logic
3. Update `affilabs_core_ui._handle_power_click()` if changing button behavior
4. Update `main_simplified._on_hardware_connected()` if changing status handling
5. **UPDATE THIS DOC** with your changes

---

## 🎯 Key Takeaway

**Hardware connection is SAFE and PREDICTABLE:**
- Scanning while connected does NOT disconnect
- Power button can be cancelled at any time
- Device type is determined by what's plugged in
- No ghost hardware displayed when nothing connected

**If you modify this logic, UPDATE THIS DOCUMENT.**
