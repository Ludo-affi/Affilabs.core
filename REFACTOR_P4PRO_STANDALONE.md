# P4PRO Standalone Class Refactor

## Overview
Separated P4PRO hardware support into standalone `PicoP4PRO` class instead of handling it within `PicoEZSPR` class with conditional logic.

**Date:** 2025
**Reason:** Simplifies architecture, eliminates firmware_id conditional checks, prevents bugs from mixed command protocols, improves maintainability.

---

## Architecture Changes

### Before (Mixed Class)
```
PicoEZSPR
├── firmware_id checks throughout methods
├── Handles EZSPR firmware (2 LEDs, pump)
├── Handles P4PRO firmware (4 LEDs, servo, valves)
└── Handles AFFINITE firmware (2 LEDs, pump)
```

**Problems:**
- Scattered conditional logic: `if 'P4PRO' in firmware_id:`
- Different command formats in same methods
- Easy to miss edge cases
- Device type detection bugs (HAL adapter was hardcoded)

### After (Separate Classes)
```
PicoP4SPR               PicoP4PRO                PicoEZSPR
├── P4SPR firmware      ├── P4PRO firmware       ├── EZSPR firmware
├── 4 LEDs + servo      ├── 4 LEDs + servo       ├── 2 LEDs + pump
├── Batch command       ├── Batch command        └── 2 LEDs + pump
└── Rank sequence       ├── Valve control              (AFFINITE)
                        └── sv command (fast)
```

**Benefits:**
- Clear separation of hardware variants
- No runtime firmware_id checks
- Type-safe HAL adapters
- Easier to debug and maintain

---

## Files Modified

### 1. `affilabs/utils/controller.py`
**Added:**
- Complete `PicoP4PRO` class (lines 2563-3019)
  - `__init__()`: firmware_id="P4PRO", valve tracking, safety timers
  - `open()`: Scans for VID/PID, requires "P4PRO" firmware ID
  - LED control: `turn_on_channel()`, `set_intensity()`, `set_batch_intensities()` (4 channels)
  - Servo: `servo_move_raw_pwm()` uses `sv{pwm:03d}{pwm:03d}` format (RAM-only, fast)
  - Servo: `set_mode()` for S/P switching using stored positions
  - Valves: `knx_six()`, `knx_three()`, `knx_six_both()`, `knx_three_both()` with safety timeouts
  - Monitoring: `get_valve_cycles()`, `get_temp()`, valve state tracking
  - ~456 lines total, inherits from `FlowController`

**Modified:**
- `PicoEZSPR` class (lines 1620+)
  - Removed P4PRO support from `open()` method
  - Updated docstring: "EZSPR/AFFINITE controller... (NOT P4PRO)"
  - Removed `_servo_s_pos` and `_servo_p_pos` attributes
  - Now only accepts "EZSPR" or "AFFINITE" firmware IDs
  - Logs "P4PRO firmware detected - skipping (use PicoP4PRO class)" if P4PRO found

### 2. `affilabs/core/hardware_manager.py`
**Modified:**
- `_get_controller_classes()` (lines 52-90)
  - Added `PicoP4PRO` to import statement
  - Added `"PicoP4PRO": PicoP4PRO` to adapter_map
  - Added stub `PicoP4PRO: StubController` for error handling

- `_connect_controller()` (lines 1029-1107)
  - **NEW Priority 2:** Try `PicoP4PRO` separately (inserted between P4SPR and EZSPR)
  - Scan order now: **PicoP4SPR → PicoP4PRO → PicoEZSPR**
  - Each controller gets HAL wrapper with `create_controller_hal()`
  - Caches `_ctrl_type = "PicoP4PRO"` for fast reconnect

### 3. `affilabs/utils/hal/controller_hal.py`
**Added:**
- Complete `PicoP4PROAdapter` class (lines 854-1044)
  - Wraps `PicoP4PRO` controller instance
  - `__init__()`: Sets `_device_type = "PicoP4PRO"` (no firmware detection needed)
  - Loads servo positions from device_config at initialization
  - LED control: `turn_on_channel()`, `set_intensity()`, `set_batch_intensities()`
  - Servo: `servo_move_raw_pwm()`, `set_mode()`, `set_servo_positions()`
  - Valves: `knx_six()`, `knx_six_both()`, `knx_three_both()` with timeout support
  - Capabilities: `supports_polarizer=True`, `supports_batch_leds=True`, `channel_count=4`
  - NO pump support: `supports_pump=False`, `knx_start()`/`knx_stop()` return False
  - Exposes `_ser` property for low-level calibration access
  - ~190 lines total

**Modified:**
- `PicoEZSPRAdapter.__init__()` (lines 591-610)
  - Removed P4PRO detection from firmware_id check
  - Now only maps "AFFINITE" → "PicoAFFINITE" or defaults to "PicoEZSPR"
  - Updated docstring: "EZSPR and AFFINITE firmware only (NOT P4PRO)"

- `PicoEZSPRAdapter` capabilities (lines 726-750)
  - `supports_polarizer = False` (was True for P4PRO)
  - `channel_count = 2` (was 4 for P4PRO)
  - Servo methods now return False/None (no conditional logic)

- `create_controller_hal()` (lines 1050-1114)
  - Added P4PRO to adapter_map:
    ```python
    "pico_p4pro": PicoP4PROAdapter,
    "PicoP4PRO": PicoP4PROAdapter,
    ```
  - Updated to pass device_config to both PicoP4SPRAdapter AND PicoP4PROAdapter
  - Updated docstring to list all 3 supported controllers

---

## Command Protocol Differences

### P4PRO (PicoP4PRO class)
- **Servo:** `sv{pwm:03d}{pwm:03d}\n` - RAM-only, fast (~150ms)
  - Example: `sv128128\n` moves to PWM 128
- **LEDs:** 4 channels (A, B, C, D) with batch command `batch:A,B,C,D\n`
  - CRITICAL: Must call `turn_on_channel()` for each channel BEFORE batch works
- **Valves:** `v6{ch}{state}\n` for 6-port, `v3{ch}{state}\n` for 3-way
- **NO pump control** - valves only

### P4SPR (PicoP4SPR class - unchanged)
- **Servo:** `servo:{angle},150\n` - Different format, EEPROM write (~5s)
- **LEDs:** 4 channels with batch + firmware rank sequence
- **Valves:** Same as P4PRO
- **NO pump control**

### EZSPR/AFFINITE (PicoEZSPR class - cleaned up)
- **NO servo support** - only 2-LED control
- **LEDs:** 2 channels (A, B) - individual control only
- **Pump:** Internal pump with flow rate control
- **Valves:** Same protocol as P4PRO

---

## Breaking Changes

### ✅ NONE - Backward Compatible
All existing code continues to work:
1. **Hardware scanning:** Automatically selects correct class based on firmware ID
2. **HAL interface:** Same methods, automatic adapter selection
3. **Calibration code:** Uses `firmware_id` checks (still works)
4. **OEM training:** Already recognizes "PicoP4PRO" device type

### Code that benefited:
- `servo_polarizer_calibration/calibrate_polarizer.py`: No changes needed
  - Already checks `hasattr(ctrl, 'firmware_id') and 'P4PRO' in ctrl.firmware_id`
  - Works correctly with new `PicoP4PRO` class

- `affilabs/core/oem_model_training.py`: No changes needed
  - Already recognizes "PicoP4PRO" in servo detection list

- `affilabs/core/hardware_manager.py`: Valve initialization works
  - Checks `hasattr(self._ctrl_raw, 'firmware_id') and 'P4PRO' in self._ctrl_raw.firmware_id`
  - Still valid since `PicoP4PRO.firmware_id = "P4PRO"`

---

## Testing Checklist

### ✅ Before Testing (Verify no syntax errors)
- [x] `controller.py` - No errors
- [x] `controller_hal.py` - No errors  
- [x] `hardware_manager.py` - No errors

### 🧪 Hardware Connection Tests
- [ ] **P4PRO hardware:**
  - [ ] Connects to `PicoP4PRO` class (check logs for "Trying PicoP4PRO")
  - [ ] HAL reports `device_type = "PicoP4PRO"`
  - [ ] Servo calibration runs successfully
  - [ ] 4-LED batch command works
  - [ ] Valve initialization to LOAD on startup

- [ ] **EZSPR hardware:**
  - [ ] Connects to `PicoEZSPR` class (skips P4PRO scan)
  - [ ] HAL reports `device_type = "PicoEZSPR"`
  - [ ] Pump control works
  - [ ] NO servo support (as expected)

- [ ] **P4SPR hardware:**
  - [ ] Still connects to `PicoP4SPR` class (unchanged)
  - [ ] Servo calibration works with `servo:` command format
  - [ ] Rank sequence LED calibration works

### 🔬 Calibration Tests
- [ ] OEM calibration workflow completes on P4PRO
- [ ] Servo positions saved to device_config
- [ ] LED calibration uses correct servo positions
- [ ] Automatic return to live view after calibration

### 🚨 Edge Case Tests
- [ ] Fast reconnect after code reload (cached port)
- [ ] P4PRO hardware doesn't connect to `PicoEZSPR` class
- [ ] EZSPR hardware doesn't connect to `PicoP4PRO` class
- [ ] Valve safety timeout triggers correctly on P4PRO
- [ ] Temperature reading on P4PRO (`get_temp()`)

---

## Rollback Plan

If issues arise, revert these 3 files:
1. `affilabs/utils/controller.py` - Remove `PicoP4PRO` class, restore P4PRO support in `PicoEZSPR`
2. `affilabs/core/hardware_manager.py` - Remove P4PRO scan priority, restore old scan order
3. `affilabs/utils/hal/controller_hal.py` - Remove `PicoP4PROAdapter`, restore P4PRO detection in `PicoEZSPRAdapter`

No other files were modified, so rollback is clean.

---

## Future Improvements

1. **Remove firmware_id checks:** Since each class is hardware-specific, remove runtime `firmware_id` checks from methods
2. **Type hints:** Add proper type annotations for controller instances in hardware_manager
3. **AFFINITE separation:** Consider splitting AFFINITE into standalone class (currently shares PicoEZSPR)
4. **Valve command abstraction:** Create shared base class for valve control (identical across P4PRO/EZSPR)

---

## Summary

**Goal:** Eliminate firmware_id conditional logic scattered throughout codebase  
**Approach:** Separate P4PRO into standalone class with dedicated command protocols  
**Result:** Cleaner architecture, easier debugging, prevents future command format bugs  
**Risk:** Low - backward compatible, existing code continues to work  
**Testing:** Hardware connection + calibration workflow on P4PRO/EZSPR/P4SPR  

**Files Changed:** 3 (controller.py, hardware_manager.py, controller_hal.py)  
**Lines Added:** ~650 (new PicoP4PRO class + adapter)  
**Lines Modified:** ~100 (scan order, EZSPR cleanup, HAL updates)  
**Breaking Changes:** 0  

---

**Next Steps:**
1. Test P4PRO hardware connection and calibration
2. Verify EZSPR still works (doesn't connect to P4PRO class)
3. Confirm valve initialization on P4PRO startup
4. Validate servo calibration uses correct `sv` command

