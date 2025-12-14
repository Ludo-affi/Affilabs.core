# ⚠️ CRITICAL ARCHITECTURE RULE - SERVO POSITIONS ⚠️

## 🎯 TL;DR - THE ABSOLUTE RULE

**NEVER USE EEPROM FOR SERVO POSITIONS. ALWAYS USE device_config.json**

- ✅ Single source of truth: `device_config.json`
- ✅ Sync to EEPROM: **Only at startup**
- ❌ Never read from EEPROM at runtime
- ❌ Never write to EEPROM at runtime
- ❌ Never use servo_get/servo_set/flash (DELETED)

**WHY CALIBRATION FAILED:**
The controller firmware caches EEPROM values when it boots. After writing new positions to EEPROM, the firmware doesn't reload them. **You must power cycle the controller** to apply new positions.

## 🚫 ABSOLUTE RULE - NEVER TO BE VIOLATED

```
╔═════════════════════════════════════════════════════════════════════╗
║                                                                     ║
║  NEVER EVER USE EEPROM FOR SERVO POSITIONS                          ║
║  ALWAYS USE device_config.json AS SINGLE SOURCE OF TRUTH            ║
║                                                                     ║
║  This rule exists because:                                          ║
║  - EEPROM can drift from device_config causing inconsistency       ║
║  - Runtime EEPROM writes are DANGEROUS and can corrupt positions   ║
║  - Multiple sources of truth lead to inverted polarizer bugs       ║
║  - Device config is version controlled and auditable               ║
║                                                                     ║
╚═════════════════════════════════════════════════════════════════════╝
```

## ✅ CORRECT ARCHITECTURE

```
STARTUP FLOW (ONCE):
┌─────────────────────┐
│ device_config.json  │  ← Single source of truth
│   S: 89°            │  ← Factory calibrated positions
│   P: 179°           │  ← Never changed at runtime
└──────────┬──────────┘
           │
           │ (sync at startup)
           ↓
┌─────────────────────┐
│ Controller EEPROM   │  ← Written ONCE at startup
│   S: 89°            │  ← Matches device_config
│   P: 179°           │  ← Firmware reads from here
└──────────┬──────────┘
           │
           │ ('ss' or 'sp' command)
           ↓
┌─────────────────────┐
│ Servo Motor         │  ← Moves to EEPROM position
│   Position: 89°     │  ← No position calculation
└─────────────────────┘

RUNTIME FLOW:
- Application calls: ctrl.set_mode('s')
- Controller firmware executes: 'ss' command
- Firmware reads S position from EEPROM (89°)
- Servo moves to 89°
- NO POSITION VALUES SENT OR CALCULATED AT RUNTIME
```

## 🚫 FORBIDDEN OPERATIONS

These functions have been **DELETED** and must **NEVER** be recreated:

1. ❌ **servo_get()** - Reads positions from EEPROM
   - Why forbidden: Creates second source of truth
   - Violates: Single source of truth principle

2. ❌ **servo_set()** - Writes positions to EEPROM
   - Why forbidden: Runtime EEPROM writes can corrupt positions
   - Violates: Immutable position principle

3. ❌ **flash()** - Writes configuration to EEPROM
   - Why forbidden: Uncontrolled EEPROM writes during runtime
   - Violates: Startup-only sync principle

4. ❌ **ANY function that reads servo positions from EEPROM**
   - Always use: `device_config.get_servo_positions()`

5. ❌ **ANY function that writes servo positions to EEPROM at runtime**
   - Only allowed: Startup sync in `_load_device_settings()`

## ✅ ALLOWED OPERATIONS

### Runtime (Normal Operation)
```python
# ✅ CORRECT - Switch modes using device_config positions
ctrl.set_mode('s')  # Firmware uses EEPROM (loaded from device_config at startup)
ctrl.set_mode('p')  # Firmware uses EEPROM (loaded from device_config at startup)

# ✅ CORRECT - Validate positions before mode switch
device_config.get_servo_positions()  # Returns {'s': 89, 'p': 179}
_validate_polarizer_positions(device_config, 's', logger)
ctrl.set_mode('s')
```

### Startup (One-Time Sync)
```python
# ✅ CORRECT - Sync device_config → EEPROM (ONCE at startup)
def _load_device_settings(self):
    device_config_positions = device_config.get_servo_positions()
    eeprom_positions = ctrl.read_config_from_eeprom()

    if device_config_positions != eeprom_positions:
        logger.warning("⚠️ EEPROM mismatch - syncing from device_config")
        ctrl.write_config_to_eeprom(device_config_dict)
        logger.info("✅ EEPROM synced from device_config")
```

### Servo Calibration (Finding Positions)
```python
# ✅ CORRECT - Calibration finds positions, saves to device_config ONLY
def run_servo_calibration():
    # Scan angles to find optimal S and P positions
    best_s = find_optimal_s_position()  # e.g., 89°
    best_p = find_optimal_p_position()  # e.g., 179°

    # Save to device_config (NOT EEPROM)
    device_config.set_servo_positions(s=best_s, p=best_p)
    device_config.save()

    # Restart required - startup sync will write to EEPROM
    logger.info("🔄 Restart application to apply new positions")
```

## 🔍 VALIDATION CHECKS

Before every `set_mode()` call:
```python
def _validate_polarizer_positions(device_config, mode, logger):
    """Ensure positions come from device_config (single source of truth)."""
    positions = device_config.get_servo_positions()
    if not positions:
        raise ValueError("No servo positions in device_config")

    s_pos = positions.get('s')
    p_pos = positions.get('p')

    if s_pos is None or p_pos is None:
        raise ValueError("Invalid servo positions in device_config")

    target_pos = s_pos if mode == 's' else p_pos
    logger.info(f"✅ Validation: {mode.upper()}-mode target={target_pos}° (from device_config)")
    logger.info(f"   Controller will use this position from EEPROM (synced at startup)")
```

## 🐛 WHY DID CALIBRATION FAIL?

### Root Cause: Firmware Caches EEPROM at Boot

**THE REAL PROBLEM:**
1. Old EEPROM had positions: S=120°, P=60° (inverted)
2. Device config has correct positions: S=89°, P=179°
3. Application wrote device_config → EEPROM successfully ✅
4. **BUT** firmware cached old EEPROM values when it booted
5. Firmware did NOT reload new EEPROM values after write
6. When calibration calls `set_mode('s')`, firmware tries to use old cached value (120°)
7. Servo can't reach that position or hits limit → command fails

### Why Controller Returns False

The controller firmware:
- **Expected**: Move servo to S position from EEPROM (should be 89°)
- **Reality**: Tries to move servo to OLD cached position (120°)
- **Result**:
  - Servo movement fails or times out
  - Controller returns empty response or error
  - `set_mode()` returns False
  - Calibration fails with "controller did not confirm"

**This is NOT a code bug - it's a firmware limitation.**

### Solution: Power Cycle Required

After EEPROM write, firmware must be restarted to reload values:

```
BEFORE POWER CYCLE:
  device_config: S=89°, P=179°  ✅ Correct
  EEPROM flash:  S=89°, P=179°  ✅ Written
  Firmware RAM:  S=120°, P=60°  ❌ Cached old values at boot

AFTER POWER CYCLE:
  device_config: S=89°, P=179°  ✅ Correct
  EEPROM flash:  S=89°, P=179°  ✅ Written
  Firmware RAM:  S=89°, P=179°  ✅ Reloaded from EEPROM
```

**Required Steps:**
1. Close application
2. Unplug controller USB
3. Wait 5 seconds
4. Plug USB back in
5. Restart application
6. Run calibration (will work now)

## 📁 FILE LOCATIONS

### Source of Truth
- **Device Config**: `src/config/devices/FLMT09116/device_config.json`
  - `servo_s_position`: 89
  - `servo_p_position`: 179

### Implementation Files
- **Controller**: `src/utils/controller.py`
  - `set_mode()` - Runtime mode switching (EEPROM positions)
  - `servo_move_calibration_only()` - Calibration workflow ONLY
  - `write_config_to_eeprom()` - Startup sync (device_config → EEPROM)

- **Calibration**: `src/utils/calibration_6step.py`
  - `_validate_polarizer_positions()` - Pre-mode-switch validation
  - Calls `set_mode()` with validation

- **Main App**: `src/main_simplified.py`
  - `_load_device_settings()` - Startup EEPROM sync

- **Servo Calibration**: `src/utils/servo_calibration.py`
  - Finds optimal positions
  - Saves to device_config ONLY

## 🎯 QUICK REFERENCE

| Operation | Function | Source | Target | When |
|-----------|----------|--------|--------|------|
| **Mode Switch** | `set_mode('s')` | EEPROM | Servo | Runtime |
| **Get Position** | `device_config.get_servo_positions()` | device_config | Code | Runtime |
| **Validate** | `_validate_polarizer_positions()` | device_config | Validation | Before set_mode |
| **Sync EEPROM** | `write_config_to_eeprom()` | device_config | EEPROM | Startup ONLY |
| **Find Positions** | `run_servo_calibration()` | Scanning | device_config | Calibration |

## 🔒 IMMUTABILITY PRINCIPLE

```python
# Positions are IMMUTABLE at runtime:
# ✅ Read from device_config
# ✅ Written to EEPROM at startup
# ❌ NEVER changed during runtime
# ❌ NEVER read from EEPROM during runtime

# Application lifecycle:
Startup:  device_config → EEPROM  (sync once)
Runtime:  EEPROM → servo           (firmware handles)
Shutdown: (no position changes)
```

## 📊 AUDIT TRAIL

All operations logged:
```
Startup:
  ⚠️ Checking EEPROM positions...
  ⚠️ Device config: S=89°, P=179°
  ⚠️ EEPROM: S=120°, P=60° (MISMATCH!)
  ⚠️ Syncing device_config → EEPROM...
  ✅ EEPROM updated: S=89°, P=179°

Runtime:
  🔍 POLARIZER POSITION VALIDATION: S-MODE
     Device Config Source: VERIFIED ✅
     S-mode position: 89°
     P-mode position: 179°
     Validation: PASSED ✅

  📡 Controller response to set_mode('s'): b'1'
  ✅ Controller confirmed: S-mode servo moved to position from device_config
```

---

## 🚨 ENFORCEMENT

If anyone attempts to:
1. Read servo positions from EEPROM during runtime
2. Write servo positions to EEPROM during runtime
3. Create functions that bypass device_config
4. Use multiple sources of truth for positions

**→ REJECT THE CHANGE IMMEDIATELY**
**→ REFER TO THIS DOCUMENT**
**→ EXPLAIN THE ARCHITECTURE VIOLATION**

This rule exists because the inverted polarizer bug (P/S ratio > 1.15) was caused by:
- Old positions in EEPROM (S=120°, P=60°)
- New positions in device_config (S=89°, P=179°)
- No sync mechanism
- Runtime EEPROM operations causing drift

**NEVER AGAIN.**

---

*Document created: 2025-11-30*
*Last updated: 2025-11-30*
*Status: PERMANENT - DO NOT DELETE OR MODIFY*
