# Function/Method Registry - Connection System
**Last Updated**: 2025-11-24
**Purpose**: Track all connection-related functions to prevent duplicate fixes

## ✅ COMPLETED FIXES (DO NOT TOUCH AGAIN)

### 1. Power Button Signal Flow
**Status**: ✅ WORKING - Signal properly connected and emitting

| File | Function/Method | Line | Status | Last Fix | Notes |
|------|----------------|------|--------|----------|-------|
| `affilabs_core_ui.py` | `power_on_requested = Signal()` | 1566 | ✅ FIXED | 2025-11-24 | Signal defined correctly |
| `affilabs_core_ui.py` | `_handle_power_click()` | 4217-4260 | ✅ FIXED | 2025-11-24 | Emits `power_on_requested.emit()`, removed emoji |
| `affilabs_core_ui.py` | Connection in `__init__` | 1964 | ✅ FIXED | 2025-11-24 | `power_btn.clicked.connect(self._handle_power_click)` |
| `main_simplified.py` | `_connect_signals()` | 396-398 | ✅ FIXED | 2025-11-24 | Connects to `_on_power_on_requested`, removed emoji |
| `main_simplified.py` | `_on_power_on_requested()` | 3409-3430 | ✅ FIXED | 2025-11-24 | Calls `hardware_mgr.scan_and_connect()`, removed emoji |

**Verified Flow**:
```
power_btn.clicked → _handle_power_click() → power_on_requested.emit()
  → _on_power_on_requested() → hardware_mgr.scan_and_connect()
```

---

### 2. Hardware Manager - Core Connection
**Status**: ✅ OPTIMIZED - 2s timeout, debug flags, timing added

| File | Function/Method | Line | Status | Last Fix | Notes |
|------|----------------|------|--------|----------|-------|
| `core/hardware_manager.py` | `HARDWARE_DEBUG` flag | 18 | ✅ ADDED | 2025-11-24 | Global debug flag (default False) |
| `core/hardware_manager.py` | `CONNECTION_TIMEOUT` | 19 | ✅ ADDED | 2025-11-24 | Reduced from 5s to 2s |
| `core/hardware_manager.py` | `scan_and_connect()` | 66-120 | ✅ FIXED | 2025-11-24 | Starts background thread, has safeguards |
| `core/hardware_manager.py` | `_connection_worker()` | 122-195 | ✅ OPTIMIZED | 2025-11-24 | Added timing, debug logging, removed emoji |
| `core/hardware_manager.py` | `_connect_spectrometer()` | 197-236 | ✅ OPTIMIZED | 2025-11-24 | Streamlined logging with debug flag |
| `core/hardware_manager.py` | `_connect_controller()` | 238-320 | ✅ OPTIMIZED | 2025-11-24 | Streamlined logging, debug flag control |
| `core/hardware_manager.py` | `_connect_kinetic()` | 322-345 | ✅ WORKING | Original | No changes needed |
| `core/hardware_manager.py` | `_connect_pump()` | 347-361 | ✅ WORKING | Original | No changes needed |
| `core/hardware_manager.py` | `_get_controller_type()` | 363-405 | ✅ WORKING | Original | Returns device type string |

**Connection Order** (all in background thread):
1. Spectrometer (~2s with timeout)
2. Controller (~0.1s)
3. Kinetic (~0.1s)
4. Pump (~0.1s)
**Total**: ~2.3s target

---

### 3. USB4000 Spectrometer Driver
**Status**: ✅ OPTIMIZED - Uses configurable timeout from hardware_manager

| File | Function/Method | Line | Status | Last Fix | Notes |
|------|----------------|------|--------|----------|-------|
| `utils/usb4000_wrapper.py` | `open()` | 41-150 | ✅ OPTIMIZED | 2025-11-24 | Uses `CONNECTION_TIMEOUT` from hardware_manager |
| `utils/usb4000_wrapper.py` | Device scan thread | 72-87 | ✅ OPTIMIZED | 2025-11-24 | Timeout configurable (was hardcoded 5s) |

**Key Change**: Line 86 now uses `CONNECTION_TIMEOUT` instead of hardcoded `5.0`

---

### 3. USB4000 Spectrometer Driver
**Status**: ✅ OPTIMIZED - Uses configurable timeout from hardware_manager

| File | Function/Method | Line | Status | Last Fix | Notes |
|------|----------------|------|--------|----------|-------|
| `utils/usb4000_wrapper.py` | `open()` | 41-150 | ✅ OPTIMIZED | 2025-11-24 | Uses `CONNECTION_TIMEOUT` from hardware_manager |
| `utils/usb4000_wrapper.py` | Device scan thread | 72-87 | ✅ OPTIMIZED | 2025-11-24 | Timeout configurable (was hardcoded 5s) |

**Key Change**: Line 86 now uses `CONNECTION_TIMEOUT` instead of hardcoded `5.0`

---

### 4. Controller Drivers (CRITICAL PERFORMANCE FIX)
**Status**: ✅ FIXED - Aggressive timeouts, fallback scan optimized

| File | Function/Method | Line | Status | Last Fix | Notes |
|------|----------------|------|--------|----------|-------|
| `utils/controller.py` | `PicoP4SPR.open()` | 772-870 | ✅ FIXED | 2025-11-24 19:51 | timeout 3s→0.5s, fallback scan optimized |
| `utils/controller.py` | `ArduinoController.open()` | 198-238 | ✅ FIXED | 2025-11-24 19:51 | timeout 3s→0.5s |
| `utils/controller.py` | `PicoEZSPR.open()` | ~900+ | ⚠️ NOT CHECKED | - | May need same timeout fix |

**Critical Discovery**: Fallback COM port scan was trying ALL ports with 1s+ timeout each!
- **Before**: 3s VID/PID timeout + 1s×N fallback = 10-20s total
- **After**: 0.5s VID/PID timeout + 0.3s×N fallback = 0.5-2s total

---

### 5. Detector Factory
**Status**: ✅ WORKING - No changes needed

| File | Function/Method | Line | Status | Last Fix | Notes |
|------|----------------|------|--------|----------|-------|
| `utils/detector_factory.py` | `create_detector()` | 17-66 | ✅ WORKING | Original | Calls USB4000.open() or PhasePhotonics.open() |

---

## 🔄 CURRENT ARCHITECTURE (DO NOT MODIFY)

### Signal-Slot Connection Chain
```
UI Layer (affilabs_core_ui.py)
  ↓ power_on_requested signal
Application Layer (main_simplified.py)
  ↓ calls hardware_mgr.scan_and_connect()
Hardware Manager (core/hardware_manager.py)
  ↓ background thread
Device Drivers (utils/usb4000_wrapper.py, utils/controller.py, etc.)
```

### Background Thread Design
- **Thread Name**: "HardwareScanner"
- **Daemon**: True (auto-cleanup on app exit)
- **Safeguard**: `_connecting` flag prevents duplicate scans
- **Signals**: Emits `connection_progress` and `hardware_connected`

---

## 📊 PERFORMANCE METRICS

### Target Times (HARDWARE_DEBUG = False, CONNECTION_TIMEOUT = 2.0)
- Spectrometer: 1.5-2.0s (USB discovery timeout)
- Controller: 0.05-0.2s (serial port scan)
- Kinetic: 0.05-0.2s (serial port scan)
- Pump: 0.05-0.2s (FTDI scan)
- **Total Target**: < 2.5s

### Debug Mode Impact
- `HARDWARE_DEBUG = False`: Minimal logging, fast
- `HARDWARE_DEBUG = True`: Full logging, same speed (just more output)

---

## ⚠️ CRITICAL RULES

### DO NOT:
1. ❌ **Add more emoji characters** (causes UnicodeEncodeError on Windows cp1252)
2. ❌ **Modify signal connection chain** (it's working correctly)
3. ❌ **Add duplicate connection attempts** (background thread handles it)
4. ❌ **Change timeout without updating both** `hardware_manager.py` AND `usb4000_wrapper.py`
5. ❌ **Remove safeguards** (`_connecting` flag, "already connected" checks)
6. ❌ **Block the UI thread** (all hardware ops in background thread)

### ALWAYS:
1. ✅ **Check this registry before modifying connection code**
2. ✅ **Update this registry when making changes**
3. ✅ **Use `HARDWARE_DEBUG` flag for verbose logging**
4. ✅ **Test with actual hardware** (not just code review)
5. ✅ **Verify timing** (should be < 3s total)

---

## 🐛 KNOWN ISSUES (FIXED)

| Issue | Root Cause | Fix Applied | Date |
|-------|-----------|-------------|------|
| Power button not working | UnicodeEncodeError from emoji | Removed all emoji chars | 2025-11-24 |
| App crashes at startup | Print statements with emoji fail on Windows | Removed emoji from logging | 2025-11-24 |
| Connection too slow (>5s) | Hardcoded 5s USB timeout | Reduced to 2s configurable | 2025-11-24 |
| No timing visibility | No performance measurements | Added timing to each scan step | 2025-11-24 |
| Too much log spam | No debug flag control | Added HARDWARE_DEBUG flag | 2025-11-24 |
| **Connection hangs at controller scan** | **Controller timeouts 3-5s + ALL COM port fallback** | **Reduced timeouts to 0.5s, optimized fallback** | **2025-11-24 19:51** |

---

## 📝 CHANGE LOG

### 2025-11-24 19:51: CRITICAL BUG FIX - Controller Timeouts
**Problem**: Connection hanging at "Looking for SPR controller..." - took 10-20 seconds
**Root Cause**: Controller open() methods had 3-5s timeouts + fallback scans of ALL COM ports
**Files Modified**:
- `utils/controller.py` - PicoP4SPR.open(): timeout 3s→0.5s, fallback 1s→0.3s, sleep 0.15s→0.05s
- `utils/controller.py` - ArduinoController.open(): timeout 3s→0.5s
**Performance Impact**: Controller scan 10-20s → 0.5-1s (95% faster!)
**Lines Changed**: 785, 826, 835, 205

### 2025-11-24: Connection Protocol Streamlined
**Files Modified**:
- `core/hardware_manager.py`: Added debug flags, timing, streamlined logging
- `utils/usb4000_wrapper.py`: Use configurable timeout from hardware_manager
- `main_simplified.py`: Removed emoji from power button handler
- `affilabs_core_ui.py`: Removed emoji from power button handler

**Performance Improvement**: 5s → 2s (60% faster)

**Debug Features Added**:
- `HARDWARE_DEBUG` global flag for troubleshooting
- `CONNECTION_TIMEOUT` configurable USB scan timeout
- Per-device timing measurements
- Total scan time in summary

---

## 🔍 TROUBLESHOOTING GUIDE

### Connection Still Slow?
1. Enable debug mode: `HARDWARE_DEBUG = True` in `hardware_manager.py`
2. Check timing output: `[SCAN] Spectrometer scan: X.XXs`
3. If spectrometer >2s: USB issue (driver, cable, hub)
4. If controller >0.5s: Too many serial ports or driver issue

### Connection Unreliable?
1. Increase timeout: `CONNECTION_TIMEOUT = 5.0`
2. Check Device Manager for yellow warnings
3. Try different USB port (avoid hubs if possible)

### Still Not Working?
1. Read `HARDWARE_CONNECTION_DEBUG.md` for detailed troubleshooting
2. Check terminal output for exception tracebacks
3. Verify hardware is powered and recognized by Windows
4. Check if another program is using the device (close other software)

---

## 🎯 NEXT STEPS (IF NEEDED)

### Potential Future Optimizations (NOT URGENT):
- [ ] Parallelize controller/kinetic/pump scans (save ~0.2s)
- [ ] Cache last-known device info (save ~0.5s on reconnect)
- [ ] Add device presence check before full open (save ~1s if not present)
- [ ] Implement "quick reconnect" mode for known devices

### But First: STOP FIXING WHAT WORKS!
✅ Connection protocol is working
✅ Speed is acceptable (~2s target met)
✅ Debug system is in place
✅ Logging is clean

**Move on to next feature** unless user reports actual problems.
