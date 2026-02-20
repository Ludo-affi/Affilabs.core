# Hardware Discovery & Connection — Functional Requirements Specification (FRS)

**Type:** Functional Requirements Specification  
**Status:** 🟢 Active — Retroactive Documentation  
**Owner:** Affinite Instruments  
**Last Updated:** February 19, 2026  
**Implementation:** `affilabs/core/hardware_manager.py` · `affilabs/coordinators/hardware_event_coordinator.py`

---

## Table of Contents

1. [Overview](#1-overview)
2. [Trigger & Entry Points](#2-trigger--entry-points)
3. [Scan Sequence](#3-scan-sequence)
4. [Device Discovery Detail](#4-device-discovery-detail)
5. [HAL Wrapping](#5-hal-wrapping)
6. [Model Identification](#6-model-identification)
7. [DeviceConfiguration Loading](#7-deviceconfiguration-loading)
8. [Status Emission & UI Response](#8-status-emission--ui-response)
9. [Locking & Re-scan Behavior](#9-locking--re-scan-behavior)
10. [Fast Reconnect Path](#10-fast-reconnect-path)
11. [Error Handling](#11-error-handling)
12. [Timing Constants](#12-timing-constants)
13. [Component Map](#13-component-map)

---

## 1. Overview

Hardware discovery is the process by which the software finds and connects to all physical devices attached to the PC: the SPR controller (Pico microcontroller), the optical detector (spectrometer), and optional peripherals (AffiPump, KNX kinetic controller).

**Design goals:**
- Non-blocking — all scanning runs in a background thread; the UI remains responsive
- Priority-ordered — controller is found first, then detector, then pump, then kinetics
- Locking — once the main unit (controller + detector) is found, it cannot change without an explicit disconnect
- Safe — USB/FTDI library initialization is performed on the main thread before handing off to the background thread
- HAL-wrapped — all connected devices are returned through hardware abstraction layer adapters; no caller touches raw driver objects

---

## 2. Trigger & Entry Points

### 2.1 User-Initiated Scan

The user clicks the **Scan** button in the Device Status panel of the sidebar.

```
User clicks "Scan"
  → HardwareEventCoordinator.on_scan_requested()
  → HardwareManager.scan_and_connect()
```

**Guard:** If a scan is already in progress (`_connecting = True`), the duplicate call is silently ignored.

### 2.2 Auto-Scan at Startup

Called once during Phase 5 of the 9-phase application initialization in `main.py`:

```python
self.hardware_mgr.scan_and_connect()
```

### 2.3 Peripheral-Only Re-Scan

If the main unit (controller + detector) is already locked, `scan_and_connect()` skips controller and detector steps and runs `_peripheral_scan_worker()` instead — searching only for pump and kinetic controller.

### 2.4 Disconnect and Rescan

The user can force a full rescan by clicking **Disconnect** (which calls `disconnect_all()`), then clicking **Scan** again. `disconnect_all()` clears all device references, resets all locks, and clears cached port/serial data.

---

## 3. Scan Sequence

```
scan_and_connect() called
  │
  ├── [Guard] Already scanning? → return (no-op)
  ├── [Guard] Main unit locked?
  │     ├── Peripherals also locked? → return (no-op)
  │     └── Peripherals unlocked? → run _peripheral_scan_worker() (background) → return
  │
  ├── emit connection_progress("Scanning for hardware...")
  │
  ├── _preinit_hardware()  [MAIN THREAD — USB library constraint]
  │     ├── reset_usb_spectrometers()   ← software reset, clears stuck "already opened" state
  │     ├── load config/device_config.json
  │     └── create_detector(config)     ← instantiates USB spectrometer object (NOT opened yet)
  │
  ├── QCoreApplication.processEvents()  ← let UI update before blocking hand-off
  │
  └── _connection_worker()  [BACKGROUND THREAD — daemon, name="HardwareScanner"]
        │
        ├── Step 1: _connect_controller()      — SPR controller via serial VID/PID
        ├── Step 2: Detector hand-off           — use pre-initialized detector from main thread
        ├── Step 3: _connect_pump()            — AffiPump via FTDI
        ├── Step 4: _connect_kinetic()         — KNX (conditional; only if no pump AND serial matches)
        │
        ├── Build status dict
        ├── Validate: ctrl_type requires both controller + detector to be non-None
        ├── Lock main unit if controller + detector both connected
        └── emit hardware_connected(status)   ← or hardware_disconnected() on failure
```

---

## 4. Device Discovery Detail

### 4.1 Controller (Step 1)

**Method:** `_connect_controller()`  
**Transport:** USB serial (pyserial + `serial.tools.list_ports`)  
**VID/PID:** `PICO_VID = 0x2E8A`, `PICO_PID = 0x000A` (Raspberry Pi Pico USB)

The method enumerates all serial ports via `serial.tools.list_ports.comports()`, then attempts to open each controller class in priority order. **Stops at the first success.**

| Priority | Class | Product |
|----------|-------|---------|
| 1 (highest) | `PicoP4SPR` | P4SPR instrument controller |
| 2 | `PicoP4PRO` | P4PRO / P4PROPLUS instrument controller |
| 3 (lowest) | `PicoEZSPR` | EzSPR instrument controller (legacy) |

> **Note:** Arduino controllers (`ARDUINO_VID = 0x2341`, `ARDUINO_PID = 0x0043`) are no longer scanned. `ENABLE_ARDUINO_SCAN = False`. Arduino support is fully deprecated.

**Fast reconnect path:** If a COM port and controller type were cached from a previous successful connection, those are tried first before the full serial scan. See §10.

**Result stored in:** `self.ctrl` (HAL-wrapped), `self._ctrl_raw` (raw object), `self._ctrl_type` (string), `self._ctrl_port` (COM port string)

---

### 4.2 Detector (Step 2)

**Method:** Pre-initialized on main thread (`_preinit_hardware()`), then consumed in `_connection_worker()`  
**Transport:** USB (OceanDirect API / oceandirect library)  
**Driver constraint:** The Ocean Optics USB driver and FTDI DLL are not thread-safe. The detector object **must be created on the main thread** — the background thread only hands off the pre-created object.

**Sequence:**
1. `reset_usb_spectrometers()` — software-resets all USB spectrometers to clear "already opened" errors without physical disconnect
2. `create_detector(config)` via `affilabs/utils/detector_factory.py` — instantiates the correct spectrometer class based on config (Flame-T / USB4000 / Phase Photonics). Config is read from `config/device_config.json`.
3. In `_connection_worker()`, the pre-initialized detector is wrapped with `OceanSpectrometerAdapter` (HAL)
4. `serial_number` is read from the detector for `DeviceConfiguration` lookup

**Result stored in:** `self.usb` (HAL-wrapped `OceanSpectrometerAdapter`), `self._spec_serial` (serial number string)

---

### 4.3 Pump (Step 3)

**Method:** `_connect_pump()`  
**Transport:** FTDI USB serial (`AffiPump` library)  
**Hardware:** Tecan Cavro Centris dual syringe pumps

**Sequence:**
1. `PumpController.from_first_available()` — scans for any FTDI device and opens the first found
2. `CavroPumpManager(controller)` — creates dual-pump manager
3. Pump is **connected but not initialized** — auto-prime is intentionally disabled (would eject buffer unexpectedly on every connect)
4. Wrapped with `create_pump_hal(pump_manager)` (HAL)

> **Mutual exclusion:** AffiPump and KNX are mutually exclusive. If `self.pump` is set, the KNX scan (Step 4) is skipped entirely.

**Result stored in:** `self.pump` (HAL-wrapped)

---

### 4.4 Kinetic Controller (Step 4)

**Method:** `_connect_kinetic()`  
**Transport:** USB serial  
**Conditional:** Only scanned if:
1. No AffiPump was found in Step 3
2. `_should_scan_kinetic()` returns `True` — the detector serial number must start with a prefix in `KNX_SERIAL_PREFIXES` (e.g., `"FLMT09116"`, `"KNX"`)

This prefix gate prevents spurious KNX scan time on systems that have never had a KNX attached.

**Sequence (if scan proceeds):**
1. Try `KineticController()` — legacy KNX2 (Arduino-based)
2. Try `PicoKNX2()` — modern Pico-based KNX

**Result stored in:** `self.knx`

---

## 5. HAL Wrapping

All discovered devices are wrapped in hardware abstraction layer adapters before being stored. No upstream code touches raw driver objects.

| Device | Raw class | HAL wrapper | HAL method |
|--------|-----------|-------------|------------|
| Controller | `PicoP4SPR` / `PicoP4PRO` / `PicoEZSPR` | `ControllerHAL` | `create_controller_hal()` |
| Detector | `USB4000` / `FlameT` / `PhasePhotonicsWrapper` | `OceanSpectrometerAdapter` | direct wrapping |
| Pump | `CavroPumpManager` | `PumpHAL` | `create_pump_hal()` |
| Kinetic | `KineticController` / `PicoKNX2` | none (raw) | — |

The raw controller is additionally stored in `self._ctrl_raw` because some hardware-specific operations (e.g., reading `firmware_id`, `has_internal_pumps()`) are not exposed through the HAL interface and must access the raw object directly.

---

## 6. Model Identification

The instrument model is determined after both controller and detector are connected, via `_get_controller_type()`:

| `self.ctrl.get_device_type()` | firmware check | `ctrl_type` returned |
|-------------------------------|---------------|---------------------|
| `"PicoP4SPR"` | — | `"P4SPR"` |
| `"PicoP4PRO"` | `firmware_id` contains `"p4proplus"` | `"P4PROPLUS"` |
| `"PicoP4PRO"` | `has_internal_pumps()` returns `True` | `"P4PROPLUS"` |
| `"PicoP4PRO"` | neither above | `"P4PRO"` |
| `"PicoEZSPR"` | — | `"ezSPR"` |
| `None` (no controller) | — | `""` (empty string) |

`ctrl_type` is also used downstream to:
- Enable/disable the Manual Injection workflow
- Show/hide internal pump UI (P4PROPLUS-specific)
- Configure pump mode combo in Method Builder dialog

---

## 7. DeviceConfiguration Loading

After the detector serial number is known, `DeviceConfiguration` is instantiated for that serial:

```python
self.device_config = DeviceConfiguration(
    device_serial=self._spec_serial,
    controller=self._ctrl_raw,
    silent_load=True,
)
```

`DeviceConfiguration` loads a per-device JSON config file that stores:
- Servo P and S positions (PWM degrees)
- Controller model (for change detection — triggers a warning if controller model changes between sessions)
- Spectrometer serial (for cross-verification)
- Any other persistent per-unit calibration metadata

If the stored controller model in the config doesn't match the detected controller, the config is updated and saved automatically.

**Servo initialization is NOT triggered during hardware scan.** The polarizer is moved only during the calibration workflow, not on every connect. This avoids unnecessary mechanical movement and ensures the servo is in a known state only when the system is ready to calibrate.

---

## 8. Status Emission & UI Response

### 8.1 Status Dict

On scan completion, `HardwareManager` emits `hardware_connected(status)` with:

| Key | Type | Value |
|-----|------|-------|
| `ctrl_type` | `str` or `""` | `"P4SPR"`, `"P4PRO"`, `"P4PROPLUS"`, `"ezSPR"`, or `""` — only set if both controller AND detector connected |
| `knx_type` | `str` or `None` | KNX variant name, or `None` |
| `pump_connected` | `bool` | `True` if AffiPump found |
| `spectrometer` | `bool` | `True` if detector connected |
| `spectrometer_serial` | `str` or `None` | Detector serial number |
| `valid_hardware` | `list[str]` | All connected device type strings (e.g., `["P4SPR", "AffiPump"]`) |
| `fluidics_ready` | `bool` | `True` if pump connected |
| `scan_successful` | `bool` | `True` if any single device found |
| `sensor_ready` | `bool` | Always `False` at scan time — set `True` only after successful calibration |
| `optics_ready` | `bool` | Always `False` at scan time — same |

### 8.2 Validation Rule

A `ctrl_type` is only placed in `valid_hardware` if **both** controller and detector are present. Controller alone → `ctrl_type` is still computed but does not go into `valid_hardware`, and the power button stays yellow (not green).

Pump and KNX can go into `valid_hardware` standalone.

### 8.3 UI Response

`HardwareEventCoordinator.on_hardware_connected(status)` handles the signal:

1. De-duplicates rapid-fire signals (< 500 ms apart are suppressed)
2. Resets the Scan button state
3. Validates hardware combinations
4. Sets power button: green (connected) or yellow/red (partial/missing)
5. Initializes `DeviceConfiguration` for new device serials (first-time OEM setup path)
6. Updates Device Status panel (model name, serial, readiness indicators)
7. Starts LED status monitoring timer
8. Loads device-specific settings
9. Checks for bilinear model (required for SPR processing)
10. Triggers initial calibration flow on first connection

If `scan_successful = False`, `hardware_disconnected` is emitted instead.

---

## 9. Locking & Re-scan Behavior

### 9.1 Main Unit Lock

Once both controller and detector are connected, `_hardware_locked = True`. Any subsequent `scan_and_connect()` call:
- Skips Steps 1 and 2 (controller and detector)
- Only runs `_peripheral_scan_worker()` to look for pump/kinetic

This prevents a new controller or detector being substituted mid-session without an explicit disconnect.

### 9.2 Peripheral Lock

Once peripherals are also locked (`_peripherals_locked = True`), subsequent scans return immediately without any scanning. Only `disconnect_all()` can reset this state.

### 9.3 Clearing Locks

`disconnect_all()` clears:
- All device object references (`ctrl`, `usb`, `pump`, `knx`)
- All lock flags (`_hardware_locked`, `_peripherals_locked`)
- Cached port and serial (`_ctrl_port`, `_ctrl_type`, `_spec_serial`)
- Emits `hardware_disconnected()`

---

## 10. Fast Reconnect Path

When the application hot-reloads or the user reconnects quickly after a disconnect, the software tries a **fast path** before doing a full serial port scan:

**Controller fast path (`_try_reconnect_controller`):**
- If `_ctrl_port` and `_ctrl_type` are populated (from a prior connection), open that specific port directly
- Skip the full `list_ports` enumeration and priority-order scan
- Falls back to full scan if fast path fails

**Detector fast path (`_try_reconnect_spectrometer`):**
- If `_spec_serial` is populated, open the first available spectrometer and verify the serial matches
- Falls back to full scan if mismatch or failure

Full scan is always the fallback if the fast path doesn't succeed within `CONNECTION_TIMEOUT = 2.0s`.

---

## 11. Error Handling

| Failure | Behavior |
|---------|----------|
| No controller found | `self.ctrl = None`; warning logged; scan continues to detector |
| No detector found | `self.usb = None`; `ctrl_type` is suppressed from `valid_hardware` |
| Detector "already opened" | Software reset via `reset_usb_spectrometers()` before scan; non-fatal if reset fails |
| Pump module not installed | `ImportError` caught; `self.pump = None`; debug logged (not an error) |
| Pump found but FTDI fails | `self.pump = None`; `connection_progress` not updated for this device |
| KNX not found | `self.knx = None`; debug logged; non-fatal |
| Any unhandled exception | Caught per-device; device set to `None`; scan continues for remaining devices |
| No valid hardware at all | `hardware_disconnected()` emitted; power button set to red/disconnected |
| Duplicate scan call | Second call returns immediately if `_connecting = True` |

Errors are emitted via:
- `logger.error()` / `logger.warning()` for dev diagnostics
- `error_occurred` signal for UI display (connection errors the user should see)
- `connection_progress` signal for status panel progress messages

---

## 12. Timing Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `CONNECTION_TIMEOUT` | 2.0 s | Per-device connection attempt timeout |
| `CONNECTION_RETRY_COUNT` | 1 | Number of retry passes (no retry by default — prevents error cascade) |
| `HARDWARE_DEBUG` | `True` | Enables verbose per-step timing logs |
| `KNX_SERIAL_PREFIXES` | `["FLMT09116", "KNX"]` | Detector serials that warrant KNX scan |
| Dedup window (coordinator) | 500 ms | `hardware_connected` callbacks closer than this are dropped |

Typical total scan time: **3–6 seconds** (dominated by USB spectrometer open time and serial port enumeration). Controller scan: ~0.5–1 s. Detector: ~2–3 s. Pump: ~0.5 s. KNX (if scanned): ~0.5 s.

---

## 13. Component Map

```
User clicks Scan
    │
    ▼
HardwareEventCoordinator.on_scan_requested()
    │  affilabs/coordinators/hardware_event_coordinator.py
    │
    ▼
HardwareManager.scan_and_connect()
    │  affilabs/core/hardware_manager.py
    │
    ├── _preinit_hardware() [main thread]
    │     └── create_detector()
    │           affilabs/utils/detector_factory.py
    │
    └── _connection_worker() [background thread: "HardwareScanner"]
          │
          ├── _connect_controller()
          │     ├── serial.tools.list_ports  (pyserial)
          │     ├── PicoP4SPR / PicoP4PRO / PicoEZSPR
          │     │     affilabs/utils/controller.py
          │     └── create_controller_hal()
          │           affilabs/utils/hal/controller_hal.py
          │
          ├── OceanSpectrometerAdapter(pre_init_detector)
          │     affilabs/utils/hal/adapters.py
          │
          ├── DeviceConfiguration(serial)
          │     affilabs/utils/device_configuration.py
          │
          ├── _connect_pump()
          │     ├── PumpController.from_first_available()
          │     │     AffiPump library (external)
          │     └── create_pump_hal()
          │           affilabs/utils/hal/pump_hal.py
          │
          ├── _connect_kinetic() [conditional]
          │     ├── KineticController
          │     └── PicoKNX2
          │           affilabs/utils/controller.py
          │
          └── hardware_connected.emit(status)  [Qt signal → main thread]
                │
                ▼
          HardwareEventCoordinator.on_hardware_connected(status)
                affilabs/coordinators/hardware_event_coordinator.py
```
