# CONTROLLER_HAL_FRS.md

**Feature Requirement Specification: Controller Hardware Abstraction Layer**  
Document Status: ✅ Code-verified  
Last Updated: February 19, 2026  
Source File: `affilabs/utils/hal/controller_hal.py` (1223 lines)

---

## §1. Purpose & Context

**What This Is:**  
The Controller HAL provides a unified `ControllerHAL` interface for all supported SPR instrument controller types (P4SPR and legacy EZSPR). It eliminates string-based device type checks throughout the codebase by replacing `if ctrl_type == 'PicoP4SPR'` guards with type-safe capability properties (`ctrl.supports_polarizer`, `ctrl.supports_batch_leds`, etc.).

**Why It Exists:**
- Abstracts PicoP4SPR vs PicoEZSPR hardware differences
- Single API surface for LED control, polarizer control, temperature, capability queries
- Additive layer — does NOT modify existing controller implementations (PicoP4SPR/PicoEZSPR remain unchanged)

**Hardware Supported:**
- **PicoP4SPR** (P4SPR, P4PRO models) — 4 LED channels, polarizer/servo, batch LED, firmware rank sequence
- **PicoEZSPR** (legacy EZSPR/AFFINITE) — 2 LED channels, no polarizer, pump corrections, KNX valve control

---

## §2. Architecture

```
Physical Hardware:
  PicoP4SPR controller ← USB/Serial → PicoP4SPR (affinite package)
  PicoEZSPR controller ← USB/Serial → PicoEZSPR (affinite package)

affilabs/utils/hal/controller_hal.py:
  ControllerHAL (Protocol) ← Interface definition
  ├─ PicoP4SPRAdapter ← Wraps PicoP4SPR
  │   └─ Uses sv+ss/sp servo commands (verified working format)
  └─ PicoEZSPRAdapter ← Wraps PicoEZSPR/AFFINITE
      └─ Falls back to sequential LED commands (no batch support)

Factory function:
  create_controller_hal(controller, device_config) → ControllerHAL

Business logic (DataAcquisitionManager, CalibrationService, etc.):
  ctrl = create_controller_hal(raw_controller, device_config)
  ctrl.turn_on_channel('a')       ← uniform API
  ctrl.set_mode('p')              ← uniform (False if no polarizer)
  ctrl.supports_polarizer         ← type-safe capability check
```

**Related files:**
- `affilabs/utils/hal/interfaces.py` — Hardware interface definitions
- `affilabs/utils/hal/adapters.py` — Additional adapter utilities
- `affilabs/utils/hal/pump_hal.py` — AffiPump HAL (separate, same pattern)

---

## §3. ControllerHAL Protocol

**Type:** Python `Protocol` (structural subtyping — duck-typed, no inheritance required)

### 3.1 LED Control

**turn_on_channel(ch: str) → bool**
- Turn on a single LED channel
- `ch`: `'a'`, `'b'`, `'c'`, `'d'`
- Returns `True` if command succeeded

**turn_off_channels() → bool**
- Turn off all LED channels
- Returns `True` if command succeeded

**set_intensity(ch: str, raw_val: int) → bool**
- Set LED channel intensity
- `raw_val`: 0-255
- Returns `True` if command succeeded

**set_batch_intensities(a=0, b=0, c=0, d=0) → bool**
- Set all 4 LED intensities in one command (if supported)
- Falls back to sequential calls for controllers without batch support (EZSPR)
- Returns `True` if all succeeded

**led_rank_sequence(test_intensity, settling_ms, dark_ms, timeout_s) → Generator | None**
- Execute firmware-side LED ranking sequence (V2.4+ firmware, P4SPR only)
- Firmware sequences through all 4 LEDs with precise timing, Python reads spectra when signaled
- Yields `(channel, signal)` tuples where signal is `'READY'`, `'READ'`, or `'DONE'`
- Returns `None` if not supported (EZSPR)

### 3.2 Polarizer Control

**set_mode(mode: str) → bool**
- Set servo polarizer to S or P mode
- `mode`: `'s'` or `'p'`
- Returns `False` if polarizer not supported
- **P4SPRAdapter:** Uses `sv{s_deg}{p_deg}\n` + `ss\n`/`sp\n` commands (verified format)

**get_polarizer_position() → dict[str, Any]**
- Returns `{'s': int, 'p': int}` or empty dict if not supported
- **CRITICAL:** Returns positions from `device_config` only — legacy EEPROM reading removed

**servo_move_calibration_only(s, p) → bool**
- Move servo without firmware lock (calibration workflows)
- Returns `False` if not supported

**servo_move_raw_pwm(pwm: int) → bool**
- Move servo to arbitrary PWM position (calibration sweeps only)
- `pwm`: 0-255
- **P4SPRAdapter:** Uses `sv{deg}{deg}\n + sp\n` format (only working format per testing)
- Returns `False` if not supported

**servo_set(s, p) → bool**
- Set and lock servo positions in firmware RAM
- Returns `False` if not supported

### 3.3 LED Query

**get_all_led_intensities() → dict[str, int] | None**
- Query current LED intensities from device (requires firmware V1.1+)
- Returns `{'a': int, 'b': int, 'c': int, 'd': int}` or `None`

### 3.4 Device Info

**get_device_type() → str**
- Returns device type string: `'PicoP4SPR'`, `'PicoEZSPR'`, `'PicoAFFINITE'`

**get_firmware_version() → str**
- Returns firmware version (e.g., `'V1.4'`) or empty string

**get_temperature() → float**
- Returns temperature in °C, or `-1.0` if not supported

### 3.5 Capability Properties (Type-Safe)

| Property | P4SPR | EZSPR/AFFINITE | Description |
|----------|-------|---------------|-------------|
| `supports_polarizer` | `True` | `False` | Has servo/polarizer |
| `supports_batch_leds` | `True` | `False` | Batch LED intensity command |
| `supports_rank_sequence` | `True` | `False` | Firmware LED rank sequence (V2.4+) |
| `supports_pump` | `False` | `True` | Built-in pump corrections |
| `supports_firmware_update` | `False` | `True` | OTA firmware update |
| `channel_count` | `4` | `2` | Number of LED channels |

**Usage pattern:**
```python
# Before HAL:
if ctrl_type == 'PicoP4SPR':
    ctrl.set_mode('p')

# After HAL:
if ctrl.supports_polarizer:
    ctrl.set_mode('p')
```

### 3.6 Pump Control (EZSPR Only)

**get_pump_corrections() → tuple[float, float] | None**
- Returns `(pump_1_correction, pump_2_correction)` for EZSPR
- Returns `None` for P4SPR

**set_pump_corrections(pump_1_correction, pump_2_correction) → bool**
- Set EZSPR pump correction factors
- Returns `False` for P4SPR

### 3.7 KNX Valve & Internal Pump Control (EZSPR Only)

**knx_six(ch, state, timeout_seconds=None) → bool**
- Control 6-port rotary valve for single channel
- `ch`: 1 (KC1) or 2 (KC2)
- `state`: 0 = LOAD (buffer), 1 = TO SENSOR (inject sample)
- `timeout_seconds=None`: NO timeout — valve stays open (use for calculated contact times)
- `timeout_seconds=300`: Safety fallback timeout for manual operations
- Returns `False` for P4SPR

**knx_six_both(state, timeout_seconds=None) → bool**
- Control both 6-port valves simultaneously
- Same `state` semantics as `knx_six()`

**knx_three_both(state) → bool**
- Control both 3-way valves (AC vs BD channel selection)
- `state`: 0 = A/C channels, 1 = B/D channels

**knx_start(rate, ch) → bool**
- Start internal peristaltic pump (P4PROPLUS, accessed via EZSPR controller)
- `rate`: 50, 100, 200, or 500 µL/min (only 4 presets)
- `ch`: 1 (KC1) or 2 (KC2)
- Returns `False` for P4SPR

**knx_stop(ch) → bool**
- Stop internal peristaltic pump
- `ch`: 1 or 2

### 3.8 Connection Management

**open() → bool** — Open serial connection  
**close() → None** — Close serial connection  
**is_connected() → bool** — Check if connected and operational

---

## §4. PicoP4SPRAdapter

**Class:** `PicoP4SPRAdapter`  
**Hardware:** P4SPR, P4PRO instruments (PicoP4SPR firmware)

### 4.1 Constructor

```python
def __init__(self, controller, device_config=None):
    self._ctrl = controller          # PicoP4SPR instance
    self._device_type = "PicoP4SPR"
    self._device_config = device_config
    self._servo_s_pos = None         # Cached PWM for S position
    self._servo_p_pos = None         # Cached PWM for P position
    
    # Load servo positions from device_config immediately
    if device_config:
        positions = device_config.get_servo_positions()
        if positions:
            self._servo_s_pos = positions["s"]
            self._servo_p_pos = positions["p"]
```

**Servo position source:** `device_config.get_servo_positions()` (NOT EEPROM)  
**Critical design:** EEPROM reading for servo positions has been deleted. All positions come from device_config.json.

### 4.2 set_mode() — Servo Position Command (Verified Working Format)

```
If cached positions available (standard path):
    1. Convert PWM→degrees: degrees = int(5 + (pwm/255.0)*170.0)
    2. Clear serial buffers (reset_input_buffer, reset_output_buffer)
    3. Send 'id\n' and verify controller responds (not '66')
    4. Send 'sv{s_deg:03d}{p_deg:03d}\n'  (set both positions)
    5. Wait 0.2s
    6. Send 'ss\n' (mode='s') or 'sp\n' (mode='p')
    7. Wait 0.5s for servo settle
    
If no cached positions (fallback):
    Call self._ctrl.set_mode(mode)  (uses EEPROM positions via firmware)
```

**Why this format:** Testing confirmed `sv{s}{p}\n + ss\n/sp\n` is the ONLY working servo command format for current firmware. Alternative formats tried during testing (old-style `sv{pos}\n` single-arg) did not work.

**Controller health check:** Before sending servo command, sends `id\n` probe command. If controller returns `'66'` (or no response), logs error and returns `False`. This prevents silent failures when controller needs power cycle.

### 4.3 servo_move_raw_pwm() — Calibration Sweep

Used during servo calibration workflows to scan arbitrary PWM positions:
```python
degrees = int(5 + (pwm/255.0)*170.0)
degrees = max(5, min(175, degrees))  # Clamp to safe range
self._ser.write(f"sv{degrees:03d}{degrees:03d}\n".encode())
time.sleep(0.1)
self._ser.write(b"sp\n")
time.sleep(0.5)  # Wait for physical movement
```

**PWM→Degrees:** `5 + (pwm/255) * 170` = range 5°-175°

### 4.4 set_servo_positions() — Cache Update

Called after successful calibration to update cached PWM values:
```python
def set_servo_positions(self, s: int, p: int) -> None:
    self._servo_s_pos = int(s)
    self._servo_p_pos = int(p)
```

This updates the in-memory cache. CalibrationService writes to `device_config.json` separately.

### 4.5 LED Batch Command

P4SPR supports batch command — delegates directly:
```python
def set_batch_intensities(self, a=0, b=0, c=0, d=0) -> bool:
    return self._ctrl.set_batch_intensities(a=a, b=b, c=c, d=d)
```

### 4.6 P4SPR Capability Summary

```python
supports_polarizer = True      # Has servo motor
supports_batch_leds = True     # Firmware batch LED command
supports_rank_sequence = True  # V2.4+ firmware rank command
supports_pump = False          # No built-in pump
supports_firmware_update = False
channel_count = 4
```

---

## §5. PicoEZSPRAdapter

**Class:** `PicoEZSPRAdapter`  
**Hardware:** Legacy EZSPR and AFFINITE instruments (2-LED, older firmware)

### 5.1 Constructor

```python
def __init__(self, controller):
    self._ctrl = controller
    # Device type from firmware_id
    if hasattr(controller, 'firmware_id') and controller.firmware_id:
        fw_id = controller.firmware_id.upper()
        if 'AFFINITE' in fw_id:
            self._device_type = "PicoAFFINITE"
        else:
            self._device_type = "PicoEZSPR"
    else:
        self._device_type = "PicoEZSPR"
```

### 5.2 LED Batch — Sequential Fallback

EZSPR does NOT have batch LED command → falls back to sequential:
```python
def set_batch_intensities(self, a=0, b=0, c=0, d=0) -> bool:
    success = True
    if a > 0: success &= self.set_intensity("a", a)
    if b > 0: success &= self.set_intensity("b", b)
    if c > 0: success &= self.set_intensity("c", c)
    if d > 0: success &= self.set_intensity("d", d)
    return success
```

### 5.3 Polarizer — Not Supported

All servo/polarizer methods return `False` immediately:
```python
def set_mode(self, mode: str) -> bool:
    return False  # EZSPR has no polarizer
```

### 5.4 KNX Valve Implementation

The EZSPR adapter implements KNX methods by delegating with argument reordering:
```python
def knx_six(self, ch: int, state: int, timeout_seconds=None) -> bool:
    # HAL:  knx_six(ch=1, state=0)
    # CTRL: knx_six(state=0, ch=1)   ← arg order differs!
    if hasattr(self._ctrl, "knx_six"):
        return self._ctrl.knx_six(state, ch, timeout_seconds=timeout_seconds)
    return False
```

**Argument order reversal** between HAL (ch, state) and underlying controller (state, ch) — this is an adapter concern, hidden from callers.

### 5.5 EZSPR Capability Summary

```python
supports_polarizer = False     # No servo
supports_batch_leds = False    # No batch command (sequential fallback)
supports_rank_sequence = False # No firmware rank sequence
supports_pump = True           # Has pump correction factors
supports_firmware_update = True
channel_count = 2              # Only 2 LED channels (unlike P4SPR's 4)
```

---

## §6. Factory Function

**Function:** `create_controller_hal(controller, device_config=None) → ControllerHAL`

```python
from affilabs.utils.hal.controller_hal import create_controller_hal

# At hardware initialization time:
raw_ctrl = PicoP4SPR(port=port)   # From affinite package
ctrl = create_controller_hal(raw_ctrl, device_config=self._device_config)

# Uniform usage:
ctrl.turn_on_channel('a')
ctrl.set_intensity('a', 200)
if ctrl.supports_polarizer:
    ctrl.set_mode('p')
```

**Type dispatch:**
- If `isinstance(controller, PicoP4SPR)` → returns `PicoP4SPRAdapter`
- If `isinstance(controller, PicoEZSPR)` → returns `PicoEZSPRAdapter`
- Raises `TypeError` for unknown controller types

---

## §7. Capability Query Pattern

**Before HAL (old pattern — scattered device type checks):**
```python
if ctrl_type == 'PicoP4SPR':
    result = ctrl.set_batch_intensities(a=200, b=200, c=200, d=200)
else:
    for ch in ['a', 'b', 'c', 'd']:
        ctrl.set_intensity(ch, 200)
```

**After HAL (new pattern — single call, adapter handles difference):**
```python
ctrl.set_batch_intensities(a=200, b=200, c=200, d=200)
# P4SPRAdapter: single batch command
# EZSPRAdapter: 4 sequential commands (transparent to caller)
```

**Capability guard pattern:**
```python
if ctrl.supports_rank_sequence:
    # Use fast firmware-controlled LED sequencing
    for channel, signal in ctrl.led_rank_sequence(test_intensity=150):
        if signal == 'READ':
            spectrum = spectrometer.read()
else:
    # Fall back to manual Python-controlled sequencing
    for ch in ['a', 'b', 'c', 'd']:
        ctrl.turn_on_channel(ch)
        time.sleep(0.045)  # Settling time
        spectrum = spectrometer.read()
        ctrl.turn_off_channels()
```

---

## §8. Servo Command Format (P4SPR — Critical Knowledge)

**Working format (verified in testing):**
```
sv{s_degrees:03d}{p_degrees:03d}\n   ← Sets both S and P degree positions
ss\n                                  ← Moves to S position
sp\n                                  ← Moves to P position
```

**Not-working formats (tested, rejected):**
- `sv{single_pos}\n` (single argument) — firmware does not recognize
- Direct EEPROM write + `ss`/`sp` — removed; stale EEPROM caused incorrect positions post-calibration

**PWM ↔ Degrees conversion:**
```python
degrees = int(5 + (pwm / 255.0) * 170.0)
# PWM=0   → 5°   (minimum)
# PWM=128 → 90°  (mid-point)
# PWM=255 → 175° (maximum)
```

**Clamping:** `max(5, min(175, degrees))` — prevents servo from hitting mechanical stops

---

## §9. Integration Points

### 9.1 DataAcquisitionManager

Primary user of LED control methods:
```python
ctrl.turn_on_channel(channel)
ctrl.set_intensity(channel, intensity)
ctrl.set_mode(polarization)  # 's' or 'p'
ctrl.turn_off_channels()
```

### 9.2 CalibrationService

Uses polarizer and servo methods during calibration:
```python
ctrl.set_mode('s')            # Take S reference
ctrl.set_mode('p')            # Take P signal
ctrl.servo_move_raw_pwm(pwm)  # Scan servo positions
ctrl.servo_move_calibration_only(s=s_pos, p=p_pos)
ctrl.set_servo_positions(s, p)  # Update cache after calibration
```

### 9.3 LED Convergence Engine

Uses batch LED and rank sequence:
```python
if ctrl.supports_rank_sequence:
    for ch, sig in ctrl.led_rank_sequence(test_intensity=128):
        ...
else:
    ctrl.set_batch_intensities(a=a_int, b=b_int, c=c_int, d=d_int)
```

### 9.4 Injection Coordinator / Cycle Coordinator

KNX valve control for P4PRO/P4PROPLUS automated injection:
```python
ctrl.knx_six(ch=1, state=1, timeout_seconds=None)  # Inject (no timeout = calculated contact time)
# ... wait for contact time ...
ctrl.knx_six(ch=1, state=0)                         # Back to buffer
```

---

## §10. Known Issues

1. **PicoP4PROAdapter mentioned in comments but missing** — Code comments in `PicoEZSPRAdapter` docstring say "P4PRO uses the separate PicoP4PRO class" but no `PicoP4PROAdapter` class exists in `controller_hal.py`. P4PRO currently uses `PicoP4SPRAdapter` since firmware reports as `PicoP4SPR`.

2. **Controller health check sends `'id\n'` but response check is fragile** — Checks `if '66' in response` as failure indicator, but a valid response containing '66' (e.g., firmware version) would false-positive as failure. Should use proper response parsing.

3. **servo_move_raw_pwm() sets both S and P to same degrees** — `sv{degrees}{degrees}` sets both S and P equal to the scan position. This overwrites any previously saved P position during a sweep that only intended to scan S positions.

4. **PicoEZSPRAdapter.get_temperature() hardcoded to -1** — Always returns `-1.0` even if EZSPR hardware has a temperature sensor. No query implemented.

5. **knx_six() arg order mismatch between HAL and controller** — HAL is `(ch, state)`, underlying controller is `(state, ch)`. This is handled correctly in the adapter but is a recurring confusion source for developers reading the code.

---

## §11. Method Inventory (Adapter Classes)

### PicoP4SPRAdapter Methods

| Method | Lines | Purpose |
|--------|-------|---------|
| `__init__()` | ~22 | Store controller + load servo positions from device_config |
| `_ser` (property) | 2 | Expose serial port for calibration operations |
| `turn_on_channel()` | 1 | Delegate to controller |
| `turn_off_channels()` | 1 | Delegate to controller |
| `set_intensity()` | 1 | Delegate to controller |
| `set_batch_intensities()` | 2 | Delegate to controller (batch supported) |
| `led_rank_sequence()` | 5 | Delegate to controller (V2.4+ firmware) |
| `set_mode()` | ~65 | sv+ss/sp servo command chain; health check; fallback |
| `get_polarizer_position()` | ~8 | Returns empty dict (use device_config instead) |
| `servo_move_calibration_only()` | 1 | Delegate to controller |
| `servo_move_raw_pwm()` | ~18 | PWM→degrees, sv+sp command, settle 0.5s |
| `servo_set()` | 1 | Delegate (P4SPR: same as calibration move) |
| `set_servo_positions()` | ~5 | Cache S/P PWM values |
| `get_all_led_intensities()` | ~3 | Delegate if supported |
| `get_device_type()` | 1 | Return "PicoP4SPR" |
| `get_firmware_version()` | 1 | Return controller.version |
| `get_temperature()` | ~3 | controller.get_temp() |
| `supports_polarizer` | 1 | True |
| `supports_batch_leds` | 1 | True |
| `supports_rank_sequence` | 1 | True |
| `supports_pump` | 1 | False |
| `supports_firmware_update` | 1 | False |
| `channel_count` | 1 | 4 |
| `get_pump_corrections()` | 1 | None |
| `set_pump_corrections()` | 1 | False |
| `knx_six()` | 1 | False (P4SPR) |
| `knx_six_both()` | 1 | False (P4SPR) |
| `knx_three_both()` | 1 | False (P4SPR) |
| `knx_start()` | 1 | False (P4SPR) |
| `knx_stop()` | 1 | False (P4SPR) |
| `open()` | 1 | Delegate |
| `close()` | 1 | Delegate |
| `is_connected()` | 1 | Check `_ser is not None and _ser.is_open` |

### PicoEZSPRAdapter Methods

Similar structure but:
- All servo methods return `False`
- `set_batch_intensities()` → sequential fallback (~8 lines)
- `get_pump_corrections()` → delegates
- `set_pump_corrections()` → delegates
- `knx_six()`, `knx_six_both()`, `knx_three_both()` → delegate with arg reorder
- `knx_start()`, `knx_stop()` → delegate
- `channel_count` → 2

---

## §12. Document Metadata

**Created:** February 19, 2026  
**Codebase Version:** Affilabs.core v2.0.5 beta  
**Lines Reviewed:** 900 of 1223 (controller_hal.py; remaining ~320 lines are factory function + imports)  
**Next Review:** When PicoP4PROAdapter is added, or when servo command format changes
