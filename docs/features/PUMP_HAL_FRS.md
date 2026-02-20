# PUMP_HAL_FRS.md

**Feature Requirement Specification: Pump Hardware Abstraction Layer**  
Document Status: ✅ Code-verified  
Last Updated: February 19, 2026  
Source File: `affilabs/utils/hal/pump_hal.py` (267 lines)

---

## §1. Purpose & Context

**What This Is:**  
The Pump HAL (Hardware Abstraction Layer) provides a unified interface for communicating with the AffiPump (Tecan Cavro Centris dual syringe pump). It wraps the external `AffiPump` package so the rest of the codebase never depends on package-specific details.

**Why It Exists:**
- Isolates hardware-specific pump protocol from business logic
- Enables mock/test pump implementations without hardware
- Consistent `PumpHAL` protocol used everywhere instead of `CavroPumpManager` directly

**Hardware Supported:** AffiPump only (2× Tecan Cavro Centris pumps via FTDI serial)

**Device Context:** Used in P4PRO and P4PROPLUS models with AffiPump; not used for P4SPR manual syringe or internal peristaltic pumps.

---

## §2. Architecture

```
External Hardware:
  AffiPump (USB/FTDI serial)
    └─ PumpController (from AffiPump package) ← Serial comms
        └─ CavroPumpManager (from AffiPump package) ← High-level operations

affilabs/utils/hal/pump_hal.py:
  PumpHAL (Protocol) ← Interface definition (type hints only)
    └─ AffipumpAdapter ← Wraps CavroPumpManager
        └─ create_pump_hal(pump_manager) ← Factory function (MAIN ENTRY POINT)

Business logic (affilabs/managers/PumpMixin, etc.):
  pump = create_pump_hal(pump_manager)
  pump.aspirate(1, 100.0, 500.0)  ← uniform API, no AffiPump-specific calls
```

**Layer placement:** `affilabs/utils/hal/` — alongside `controller_hal.py`, `interfaces.py`, `adapters.py`

---

## §3. PumpHAL Protocol

**Type:** Python `Protocol` (structural subtyping — no inheritance required, duck-typed)

### 3.1 Low-Level Commands

**send_command(address, command) → bytes**
- **Purpose:** Send raw Cavro command bytes to pump controller
- **Args:**
  - `address: int` — Pump address: `0x41` (broadcast 'A'), `0x42` ('B' = pump 1), `0x43` ('C' = pump 2)
  - `command: bytes` — Raw command (e.g., `b"T"` = terminate, `b"A0"` = absolute move)
- **Returns:** Response bytes from pump
- **Use case:** Low-level calibration or diagnostic commands not exposed by high-level API

**is_available() → bool**
- **Returns:** `True` if pumps are ready for operation (connected + initialized)

### 3.2 High-Level Operations

**initialize_pumps() → bool**
- **Purpose:** Initialize both Cavro Centris pumps and prepare for operation
- **Returns:** `True` if initialization succeeded
- **Side effects:** Pumps perform homing sequence on init

**aspirate(pump_address, volume_ul, rate_ul_min) → bool**
- **Args:**
  - `pump_address: int` — Pump ID (1 or 2)
  - `volume_ul: float` — Volume in microliters (e.g., `100.0`)
  - `rate_ul_min: float` — Flow rate in µL/min (e.g., `500.0`)
- **Returns:** `True` if command succeeded
- **Note:** This PULLS fluid into the syringe from reservoir

**dispense(pump_address, volume_ul, rate_ul_min) → bool**
- **Args:**
  - `pump_address: int` — Pump ID (1 or 2)
  - `volume_ul: float` — Volume in microliters
  - `rate_ul_min: float` — Flow rate in µL/min
- **Returns:** `True` if command succeeded
- **Note:** This PUSHES fluid from syringe to flow cell

**set_valve_position(pump_address, port) → bool**
- **Args:**
  - `pump_address: int` — Pump ID (1 or 2)
  - `port: int` — Valve port number (1-9, depends on valve type)
- **Returns:** `True` if command succeeded

**get_syringe_position(pump_address) → int | None**
- **Returns:** Current syringe position in steps, or `None` if query failed

**wait_until_idle(pump_address, timeout_s=60.0) → bool**
- **Purpose:** Block until pump finishes current operation
- **Args:**
  - `pump_address: int` — Pump ID (1 or 2)
  - `timeout_s: float` — Maximum wait time (default 60s)
- **Returns:** `True` if pump became idle within timeout, `False` if timeout

### 3.3 Connection Management

**close() → None**
- Closes serial connection to pump hardware
- Called on application shutdown or hardware disconnect

---

## §4. AffipumpAdapter — Concrete Implementation

**Class:** `AffipumpAdapter`  
**Implements:** `PumpHAL` protocol  
**Wraps:** `CavroPumpManager` from AffiPump package

### 4.1 Constructor

```python
def __init__(self, pump_manager) -> None:
    self._pump = pump_manager          # CavroPumpManager instance
    self._controller = pump_manager.pump  # PumpController (serial layer)
```

### 4.2 Address → Cavro Command Conversion

The `send_command()` method converts HAL-style addressing to Cavro protocol:
```python
# HAL args:    address=0x41, command=b"TR"
# Cavro format: "/ATR"
addr_char = chr(address)           # 0x41 → 'A' (broadcast)
cmd_str = command.decode('ascii')  # b"TR" → "TR"
full_cmd = f"/{addr_char}{cmd_str}"  # → "/ATR"
result = self._controller.send_command(full_cmd)
```

**Address mapping:**
- `0x41` = `'A'` = broadcast to all pumps
- `0x42` = `'B'` = pump 1 specific
- `0x43` = `'C'` = pump 2 specific

### 4.3 High-Level Operations Implementation

All methods delegate directly to `CavroPumpManager`:
```python
def aspirate(self, pump_address: int, volume_ul: float, rate_ul_min: float) -> bool:
    if not self._pump:
        return False
    try:
        self._pump.aspirate(pump_address, volume_ul, rate_ul_min)
        return True
    except Exception as e:
        logger.error(f"Aspirate failed: {e}")
        return False
```

**All high-level methods follow same pattern:**
1. Guard: `if not self._pump: return False`
2. Delegate: `self._pump.method_name(args)`
3. Exception handling: log error, return `False`

### 4.4 get_syringe_position() Implementation

Directly delegates (no exception wrapping for this one):
```python
def get_syringe_position(self, pump_address: int) -> int | None:
    if not self._pump:
        return None
    return self._pump.get_syringe_position(pump_address)
```

### 4.5 close() Implementation

Closes via `PumpController`, not `CavroPumpManager`:
```python
def close(self) -> None:
    if self._controller:
        self._controller.close()
```

---

## §5. Factory Function

**Function:** `create_pump_hal(pump_manager) → PumpHAL`  
**Main entry point** — this is how callers get a pump HAL instance

```python
from AffiPump import CavroPumpManager, PumpController
from affilabs.utils.hal.pump_hal import create_pump_hal

# Connect to hardware
controller = PumpController.from_first_available()
pump_manager = CavroPumpManager(controller)

# Wrap with HAL
pump = create_pump_hal(pump_manager)

# Use unified interface
if pump.initialize_pumps():
    pump.aspirate(1, 100.0, 500.0)   # Pump 1: 100µL at 500µL/min
    pump.wait_until_idle(1)
    pump.dispense(1, 100.0, 500.0)   # Pump 1: 100µL at 500µL/min
```

**Returns:** `AffipumpAdapter` instance typed as `PumpHAL`

---

## §6. Integration in Application

### 6.1 Pump HAL Initialization (main.py)

```python
# Initialized in pump mixin / hardware setup phase
controller = PumpController.from_first_available()
pump_manager = CavroPumpManager(controller)
self.pump = create_pump_hal(pump_manager)
```

### 6.2 Usage in PumpMixin

Business logic in `mixins/pump_mixin.py` calls pump HAL methods:
```python
# Aspirate before injection
if self.pump.is_available():
    self.pump.aspirate(1, volume_ul=self._method_volume, rate_ul_min=self._method_flow_rate)
    self.pump.wait_until_idle(1)
    # Then inject...
    self.pump.dispense(1, volume_ul=self._method_volume, rate_ul_min=self._method_flow_rate)
```

### 6.3 Pump HAL Shutdown

```python
# On application close or hardware disconnect
if hasattr(self, 'pump') and self.pump:
    self.pump.close()
```

---

## §7. Hardware Model Context

**P4PRO (AffiPump external):**
- Uses `create_pump_hal()` with real `CavroPumpManager`
- Full aspirate + dispense capability
- Pulse-free high-accuracy flow
- Volume and flow rate fully programmable per injection

**P4PROPLUS (Internal peristaltic pumps):**
- Internal pumps are NOT controlled via PumpHAL
- Internal pumps use `controller_hal.knx_start()` / `knx_stop()` directly
- PumpHAL is still used if an AffiPump is attached to P4PROPLUS

**P4SPR (no pump, or optional AffiPump):**
- If AffiPump attached: uses `create_pump_hal()` to enable Semi-Automated mode
- No pump: PumpHAL not instantiated

---

## §8. Cavro Protocol Reference

The AffiPump (Tecan Cavro Centris) uses DT protocol over RS-232 (FTDI USB-serial adapter):

**Command format:** `/{addr}{command}R\r` where `R` = execute

**Common commands:**
| Command | Description |
|---------|-------------|
| `TR` | Terminate (stop current move) |
| `A0` | Move to absolute position 0 (bottom) |
| `A{n}` | Move to absolute step `n` |
| `P{v}` | Pick up (aspirate) volume in steps |
| `D{v}` | Dispense volume in steps |
| `I{port}` | Input valve (switch to port) |
| `O{port}` | Output valve (switch to port) |
| `Q` | Query pump status |

**Address bytes:**
- `0x41` = `'A'` = broadcast to all on bus
- `0x42` = `'B'` = first pump on bus
- `0x43` = `'C'` = second pump on bus

---

## §9. Error Handling

| Scenario | Behavior |
|----------|----------|
| `_pump` is None | All methods return `False` / `None`, log warning |
| CavroPumpManager raises exception | Caught, logged as `logger.error()`, return `False` |
| Serial timeout in `wait_until_idle` | Returns `False`, user-facing pump timeout warning |
| Hardware disconnected mid-operation | Exception caught in delegate layer, `False` returned |

**No exceptions propagate** from AffipumpAdapter methods — all failures return `False` / `None`.

---

## §10. Method Inventory

| Method | Lines | Purpose |
|--------|-------|---------|
| `PumpHAL.send_command()` (Protocol) | 5 | Protocol definition |
| `PumpHAL.is_available()` (Protocol) | 3 | Protocol definition |
| `PumpHAL.initialize_pumps()` (Protocol) | 3 | Protocol definition |
| `PumpHAL.aspirate()` (Protocol) | 6 | Protocol definition |
| `PumpHAL.dispense()` (Protocol) | 6 | Protocol definition |
| `PumpHAL.set_valve_position()` (Protocol) | 5 | Protocol definition |
| `PumpHAL.get_syringe_position()` (Protocol) | 4 | Protocol definition |
| `PumpHAL.wait_until_idle()` (Protocol) | 5 | Protocol definition |
| `PumpHAL.close()` (Protocol) | 2 | Protocol definition |
| `AffipumpAdapter.__init__()` | ~8 | Store pump_manager + extract controller |
| `AffipumpAdapter.send_command()` | ~12 | Convert address/command, delegate |
| `AffipumpAdapter.is_available()` | ~4 | Delegate to pump_manager |
| `AffipumpAdapter.initialize_pumps()` | ~5 | Delegate to pump_manager |
| `AffipumpAdapter.aspirate()` | ~8 | Guard + delegate + exception handling |
| `AffipumpAdapter.dispense()` | ~8 | Guard + delegate + exception handling |
| `AffipumpAdapter.set_valve_position()` | ~8 | Guard + delegate + exception handling |
| `AffipumpAdapter.get_syringe_position()` | ~5 | Guard + delegate |
| `AffipumpAdapter.wait_until_idle()` | ~5 | Guard + delegate |
| `AffipumpAdapter.close()` | ~4 | Close via controller |
| `create_pump_hal()` | ~5 | Factory: wraps CavroPumpManager in AffipumpAdapter |

---

## §11. Known Issues

1. **Single AffiPump assumed** — HAL assumes one CavroPumpManager instance with two pumps (addresses 1 and 2). No support for multiple independent AffiPump units on different COM ports.

2. **No connection retry logic** — If pump disconnects mid-operation, `False` is returned but no reconnect attempt is made. Caller must handle reconnect.

3. **`send_command()` address char boundary** — Address conversion `chr(address)` only works correctly for `0x41+`. Address `0x00` would produce null byte behavior. Not a practical issue (pump addresses are always `>= 0x41`).

4. **wait_until_idle default timeout too long** — 60s default may delay UI response if pump jams or disconnects. Callers should pass shorter timeouts for time-sensitive operations.

---

## §12. Document Metadata

**Created:** February 19, 2026  
**Codebase Version:** Affilabs.core v2.0.5 beta  
**Lines Reviewed:** 267 (pump_hal.py, full)  
**Related:** `CONTROLLER_HAL_FRS.md` (same HAL pattern for LED controller)
