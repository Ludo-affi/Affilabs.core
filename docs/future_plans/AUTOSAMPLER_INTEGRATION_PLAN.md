# Autosampler Integration Plan — Knauer Azura AS 6.1L

**Status:** Future work
**Priority:** Medium
**Target hardware:** Knauer Azura AS 6.1L autosampler
**Target instrument config:** P4PRO + AffiPump + Azura AS 6.1L
**Estimated effort:** 4–6 weeks
**Target version:** v2.2.0

---

## Overview

Add support for the Knauer Azura AS 6.1L autosampler connected to a P4PRO system.
The autosampler replaces manual injection, enabling fully unattended multi-sample SPR runs.

**Workflow enabled:**
1. User loads sample plate (96-well or vials) into autosampler
2. Affilabs.core sends injection commands per cycle
3. Autosampler draws sample from well, injects into 6-port valve loop
4. AffiPump delivers sample through KC1/KC2 to flow cells
5. Next cycle: autosampler advances to next well automatically
6. Full concentration series (e.g. 8 concentrations × 3 replicates) runs overnight, unattended

---

## Hardware Context

### Knauer Azura AS 6.1L

| Property | Value |
|----------|-------|
| Type | Autosampler (loop injection) |
| Communication | **LAN (TCP/IP)** — primary; RS-232 optional |
| Protocol | ASCII command set over TCP, port 10001 |
| Control | Firmware Wizard for IP config; command-driven for runtime |
| Injection volume | 0.1 – 900 µL (configurable) |
| Sample capacity | 96-well plate or vial tray |
| Needle wash | Programmable (internal + external wash) |
| Trigger I/O | TTL in/out for synchronization with external instruments |
| Flow rate | Pump-controlled (AffiPump drives flow, autosampler controls needle) |

### Connection to existing system

```
Knauer Azura AS 6.1L
  ↓ LAN (TCP/IP, port 10001)
  ↓ ASCII commands (inject, wash, status query)
PC running Affilabs.core
  ↓ AffiPump (Cavro syringe pumps)
  ↓ P4PRO controller (6-port valve, LEDs, servo)
  ↓ Ocean Optics detector (USB)
```

The autosampler does **not** drive flow — AffiPump controls all fluid delivery.
The autosampler only:
- Picks up sample from a well/vial
- Loads it into the injection loop
- Triggers "ready" when loop is filled

---

## Architecture

### New HAL: `autosampler_hal.py`

Following the same pattern as `pump_hal.py` — a Protocol interface + concrete adapter.

**Location:** `affilabs/utils/hal/autosampler_hal.py`

```
AutosamplerHAL (Protocol)          ← interface, 8 methods
    └── KnauerAzuraAdapter         ← concrete Knauer TCP implementation
            └── KnauerTCPClient    ← low-level TCP ASCII socket layer
```

Factory function: `create_autosampler_hal(host, port) → AutosamplerHAL`

### HAL Interface — `AutosamplerHAL` Protocol

```python
class AutosamplerHAL(Protocol):

    def connect(self) -> bool:
        """Open TCP connection to autosampler. Returns True if successful."""

    def is_connected(self) -> bool:
        """Return True if TCP connection is active and device responds."""

    def inject(self, well: str, volume_ul: float, wash: bool = True) -> bool:
        """
        Draw volume_ul from well (e.g. 'A1', 'B3') and load into injection loop.
        Optionally wash needle before pickup (default True).
        Returns True when loop is loaded and ready.
        """

    def wash_needle(self, cycles: int = 2) -> bool:
        """Run needle wash sequence (internal + external wash station)."""

    def get_status(self) -> dict:
        """
        Return device status dict:
          {
            'ready': bool,
            'busy': bool,
            'error': str | None,
            'current_well': str | None,
            'tray_type': str,
          }
        """

    def set_tray(self, tray_type: str) -> bool:
        """
        Configure tray type: '96_well_plate', 'vials_1_5ml', 'vials_2ml'.
        Must match physically loaded tray.
        """

    def abort(self) -> bool:
        """Immediately abort current operation, retract needle, return to home."""

    def close(self) -> None:
        """Close TCP connection cleanly."""
```

### TCP Client Layer — `KnauerTCPClient`

```python
class KnauerTCPClient:
    """Low-level TCP ASCII client for Knauer Azura devices."""

    DEFAULT_PORT = 10001       # Knauer standard port for all AZURA devices
    TIMEOUT_S    = 5.0         # Socket timeout
    ENCODING     = "ascii"

    def __init__(self, host: str, port: int = DEFAULT_PORT): ...

    def send_command(self, cmd: str) -> str:
        """Send ASCII command, return response string. Thread-safe."""

    def query(self, cmd: str) -> str:
        """send_command + return stripped response."""

    def connect(self) -> bool: ...
    def close(self) -> None: ...
    def is_connected(self) -> bool: ...
```

**ASCII command format** (Knauer AZURA standard):
```
Command:  {COMMAND_NAME}:{value}\r\n
Response: {STATUS}:{value}\r\n

Examples:
  INJECT:A1,100\r\n      → inject 100µL from well A1
  WASH:2\r\n             → wash needle 2 cycles
  STATUS\r\n             → query device status
  TRAY:96WELL\r\n        → set tray type
  ABORT\r\n              → emergency stop
```

> **Note:** Exact command syntax must be verified against the Knauer Azura AS 6.1L
> firmware documentation (request from Knauer support: "remote control ASCII command reference").
> The above is representative of the Knauer AZURA ASCII protocol family.

---

## Integration Points

### 1. Hardware Manager — `hardware_manager.py`

Add autosampler scanning alongside AffiPump detection:

```python
# affilabs/core/hardware_manager.py

class HardwareManager:
    autosampler: AutosamplerHAL | None = None

    def _scan_autosampler(self) -> None:
        """Try to connect to Knauer Azura autosampler at configured IP."""
        host = self._get_autosampler_host()   # from device config or settings
        if not host:
            return
        hal = create_autosampler_hal(host)
        if hal.connect():
            self.autosampler = hal
            logger.info(f"[OK] Knauer Azura autosampler connected at {host}")
        else:
            logger.warning(f"Autosampler not found at {host}")
```

### 2. Injection Coordinator — `injection_coordinator.py`

Extend `execute_injection()` to use autosampler when available:

```python
# affilabs/coordinators/injection_coordinator.py

def execute_injection(self, cycle, flow_rate, well=None, volume_ul=None, ...):
    has_autosampler = (
        self._hardware_mgr.autosampler is not None
        and self._hardware_mgr.autosampler.is_connected()
    )

    if has_autosampler and well:
        self._execute_autosampler_injection(cycle, well, volume_ul, flow_rate)
    elif has_affipump:
        self._execute_affipump_injection(cycle, flow_rate)
    else:
        self._execute_manual_injection(cycle)
```

New method `_execute_autosampler_injection()`:
1. Wash needle (if enabled in settings)
2. `autosampler.inject(well, volume_ul)` — loads loop
3. Wait for autosampler "ready" status
4. Trigger AffiPump to deliver (same as existing automated injection)
5. Wait for dissociation phase
6. `autosampler.wash_needle()` — clean between samples

### 3. Method Builder — `method_builder_dialog.py`

Add per-cycle well assignment when autosampler is configured:

- New column in cycle table: **Well** (e.g. "A1", "B3", "—")
- Dropdown: **Tray type** (96-well plate / 1.5mL vials / 2mL vials)
- Volume field: **Injection volume (µL)** per cycle (default: loop volume)
- Auto-fill: **Concentration series** wizard populates well assignments from plate map

### 4. Settings — Autosampler Configuration

Add to Settings → Hardware tab:

```
Autosampler
  ☑ Enable Knauer Azura autosampler
  IP Address: [192.168.1.xxx      ]
  Port:       [10001              ]
  Tray type:  [96-well plate  ▼  ]
  Needle wash: ☑ Before each injection
               Wash cycles: [2]
  [Test Connection]   [Detect IP]
```

IP stored in `affilabs/config/devices/{SERIAL}/device_config.json`:
```json
{
  "autosampler": {
    "enabled": true,
    "host": "192.168.1.50",
    "port": 10001,
    "tray_type": "96_well_plate",
    "needle_wash_enabled": true,
    "needle_wash_cycles": 2
  }
}
```

---

## Synchronization Strategy

The Azura signals "loop loaded and ready" — Affilabs.core must detect this before triggering AffiPump delivery. Two approaches, in order of preference:

### Option 1: TTL Trigger (Recommended)

```
Azura trigger OUT ──────────────────► P4PRO digital input pin
                   BNC/GPIO cable
                   ~$5, <1ms latency
```

- Azura asserts TTL HIGH when injection loop is full
- P4PRO firmware detects rising edge → raises an event → `injection_coordinator` starts AffiPump
- No network dependency, hardware-level timing, zero polling overhead
- **Requires:** exposed digital input on P4PRO controller board + firmware event handler (confirm with firmware team)

### Option 2: TCP Status Polling (Fallback)

- After sending `INJECT` command, poll `STATUS` every 200ms over the existing TCP socket
- When response transitions from `BUSY` → `READY`, AffiPump starts delivery
- Pure software — no hardware changes, no firmware changes
- Latency: 0–200ms (acceptable for SPR injection timing)
- **Use this if** TTL wiring is not feasible (rack layout, no exposed P4PRO input pin)

### HAL Design for Both

`inject()` blocks until ready regardless of mechanism — the coordinator always sees the same interface:

```python
# injection_coordinator.py
autosampler.inject(well, volume_ul)   # blocks until loop loaded + ready
affipump.start_delivery(flow_rate)    # fires immediately after
```

Internally, `KnauerAzuraAdapter` uses whichever sync method is configured (TTL callback forwarded from controller, or TCP poll loop). The coordinator is unaware of which path was taken.

### Sync Method Config

```json
{
  "autosampler": {
    "sync_method": "ttl",        // "ttl" or "tcp_poll"
    "tcp_poll_interval_ms": 200  // used only when sync_method = "tcp_poll"
  }
}
```

---

## UI Design

### Where Autosampler UI Appears

Autosampler UI is **hidden entirely** when no autosampler is configured. It surfaces in three places only:

#### 1. Method Builder — Well Assignment (Setup)

Add two columns to the existing cycle table, visible only when autosampler is enabled:

| Type | Duration | Flow Rate | ... | **Well** | **Vol (µL)** |
|------|----------|-----------|-----|----------|--------------|
| Inject | 120s | 25 µL/min | ... | A1 | 100 |
| Inject | 120s | 25 µL/min | ... | B1 | 100 |
| Baseline | 60s | 25 µL/min | ... | — | — |

- **Well** field: free-text entry (e.g. `A1`, `H12`) or `—` for no autosampler action
- **Vol (µL)** field: per-cycle injection volume, defaults to loop volume from settings
- **Auto-fill wizard**: "Fill concentration series" button → user enters concentrations + starting well → wizard populates Well column in order

No full 96-well plate map visual — the column is enough for v1.

#### 2. Active Cycle Overlay — Current Well (During Run)

Extend the existing `CycleStatusOverlay` (top-right of sensorgram) with one additional line when autosampler is active:

```
Injecting          [A1] → 100 nM
■■■■■□□□□□  00:42 remaining
Next: Dissociation
```

- Well ID + concentration label pulled from the method's plate map
- Only shown during injection cycles — hidden during baseline/wash cycles
- No separate panel or widget needed

#### 3. Error State — Inline Banner (Mid-Run Failure)

If autosampler goes offline or fails to load a well, **do not block with a modal dialog** — the user may need to physically interact with the autosampler while responding:

```
⚠  Autosampler timeout on well B2
[Inject manually]   [Retry]   [Abort run]
```

- Inline banner appears below the cycle overlay
- Run pauses, timer stops
- **Inject manually** → proceeds without autosampler for this cycle, flags it in metadata
- **Retry** → re-sends inject command, resumes poll/wait
- **Abort run** → stops acquisition, logs which cycles completed

---

## Injection Sequence (Full Unattended Run)

```
Method: 8-concentration kinetics (10, 30, 100, 300, 1000 nM × 3 replicates)

Plate map:
  A1: 10 nM    B1: 30 nM    C1: 100 nM    D1: 300 nM
  A2: 10 nM    B2: 30 nM    C2: 100 nM    D2: 300 nM
  A3: 10 nM    B3: 30 nM    C3: 100 nM    D3: 300 nM
  E1: 1000 nM  F1: 1000 nM  G1: 1000 nM  (remaining wells)

Per cycle:
  1. Baseline (PBS, no autosampler action)
  2. Autosampler: wash needle → pick up A1 (10 nM) → load loop
  3. AffiPump: inject at 25 µL/min × 120s contact time
  4. AffiPump: buffer rinse (dissociation) × 180s
  5. Regeneration (separate well with regeneration buffer)
  6. Baseline (stabilization)
  7. → next cycle, next well
```

---

## New Files

| File | Purpose |
|------|---------|
| `affilabs/utils/hal/autosampler_hal.py` | HAL Protocol + KnauerAzuraAdapter + KnauerTCPClient |
| `affilabs/utils/autosampler_config.py` | Config dataclass for autosampler settings |
| `docs/hardware/AUTOSAMPLER_SETUP_GUIDE.md` | User-facing setup and plate map guide |

## Modified Files

| File | Change |
|------|--------|
| `affilabs/core/hardware_manager.py` | Add `autosampler` property + `_scan_autosampler()` |
| `affilabs/coordinators/injection_coordinator.py` | Add autosampler injection path + sync wait logic |
| `affilabs/widgets/method_builder_dialog.py` | Add Well + Vol columns, auto-fill wizard |
| `affilabs/widgets/cycle_status_overlay.py` | Add current well + concentration label line |
| `affilabs/sidebar_tabs/AL_settings_builder.py` | Add autosampler settings section + sync method toggle |
| `affilabs/config/devices/*/device_config.json` | Add `autosampler` config block |
| `_build/Affilabs-Core.spec` | No changes needed (pure Python TCP, no new binaries) |

---

## Compatibility

| Config | Behavior |
|--------|----------|
| P4PRO + AffiPump + Azura | Full autosampler injection (this feature) |
| P4PRO + AffiPump, no Azura | Existing automated injection unchanged |
| P4SPR + AffiPump + Azura | Autosampler loads loop; AffiPump delivers (same flow) |
| P4SPR, no pump | Manual injection — autosampler ignored |
| Autosampler offline mid-run | Error dialog + pause; user can switch to manual |

---

## Pre-Implementation Requirements

Nothing can be implemented until the following are resolved. Grouped by source.

### From Knauer Support

| Item | Request wording | Blocking? |
|------|----------------|-----------|
| **ASCII command reference** | "Remote control ASCII command reference for Azura AS 6.1L" | ✅ Yes — cannot write HAL without exact syntax |
| **Firmware version for remote control** | "Minimum firmware version required for LAN ASCII remote control" | ✅ Yes — some units require paid firmware upgrade |
| **TCP port confirmation** | "Confirm TCP port for ASCII remote control on AS 6.1L" (expected: 10001) | Minor |
| **Needle outlet fitting spec** | "Fitting type and thread spec for needle outlet tubing connection" | ✅ Yes — needed for fluidic adapter design |
| **TTL trigger spec** | "Trigger output connector type, voltage level, and polarity for AS 6.1L" | Only if going TTL route |

Command reference must confirm exact syntax for: `inject` (well address format, volume parameter), `wash`, `status` (response states + error codes), `abort`, tray configuration.

### From Firmware Team (Internal)

| Item | Question | Blocking? |
|------|----------|-----------|
| **P4PRO digital input pin** | Is there an exposed TTL input on the controller board? | Only if going TTL route |
| **Voltage tolerance** | Does the input accept 3.3V or 5V TTL? (Azura output level TBD) | Only if going TTL route |
| **Firmware trigger event** | Is there existing firmware support for an external start-injection trigger, or does it need to be added? | Only if going TTL route |

If no digital input is available on P4PRO, fall back to TCP polling — no firmware changes needed.

### Fluidics (Internal)

| Item | Action |
|------|--------|
| **Needle → 6-port valve adapter** | Confirm needle outlet OD/fitting matches P4PRO injection loop inlet. Design custom PEEK adapter if needed. |
| **Tubing dead volume** | Measure dead volume in adapter + tubing run from needle to valve. Add to injection volume to ensure full loop loading. |

---

## Integration Paths — Decision Guide

Two independent approaches. They solve different problems and can be combined.

| Approach | What it does | Effort | When to use |
|----------|-------------|--------|-------------|
| **TTL hardware trigger** | Autosampler tells P4PRO exactly when it injects (hardware wire) | ~1 week (firmware + software) | When you need precise injection timestamps with zero latency. Works with ANY autosampler brand. |
| **SiLA 2 software wrapper** | Software on PC orchestrates both instruments via gRPC over LAN | ~1 week (software only) | When customer has a lab scheduler that speaks SiLA 2, or you want full remote control of the P4PRO from external software. |
| **TCP polling (current plan)** | Affilabs.core asks Knauer "are you done?" repeatedly | Already in plan above | Simplest. Sufficient for most use cases. ~2s latency on injection timestamp. |

**Recommended for v2.2:** TCP polling (already designed) + TTL trigger as an optional add-on.
**Recommended for v2.3:** SiLA 2 wrapper (see `ANIML_SILA_IMPLEMENTATION_PLAN.md`).

---

## TTL Hardware Trigger — Specification

### What it does

The Knauer Azura AS 6.1L has a **relay contact output** (TTL OUT) that changes state at the moment the injection loop is loaded and sample starts flowing. Connecting this to a GPIO input on the P4PRO controller lets the firmware timestamp the injection to within one acquisition frame (~100 ms) — far more precise than polling.

```
Knauer AS 6.1L injects sample
    → Relay contact output fires (TTL OUT, 3.3V or 5V, momentary pulse ~100ms)
    → Physical wire to P4PRO GPIO input pin
    → Firmware detects rising edge
    → Firmware sends serial event: "TRIGGER:INJECT\n"
    → controller_hal reads event, emits Python signal
    → InjectionCoordinator.on_external_trigger() called
    → Injection flag placed on sensorgram at current elapsed_time
    → User sees auto-placed marker with channel label
```

### Hardware requirements

| Item | Spec | Source |
|------|------|--------|
| Knauer TTL output | 3.3V or 5V, momentary pulse on injection | Knauer user manual §Trigger I/O |
| P4PRO GPIO input | Must confirm: is there an exposed input pin on controller board? | → **Firmware team to confirm** |
| Voltage matching | If Azura outputs 5V and P4PRO expects 3.3V: add voltage divider (2× resistors, 5 min) | → Resolve once both voltages confirmed |
| Cable | 2-wire (signal + GND), any length ≤ 3m, standard BNC or bare wire to header | Customer-supplied or bundled |

**Key open question:** Does the P4PRO controller board have an exposed digital input GPIO pin? If not, this requires a hardware revision or a cheap USB GPIO board (e.g. FT232H breakout — Python-accessible, no firmware changes needed).

### Firmware changes (if using P4PRO GPIO)

1. Poll GPIO input pin in acquisition loop (already running ~10 Hz)
2. On rising edge detected: send `TRIGGER:INJECT\n` over serial to PC
3. Timestamp = firmware clock at detection moment (same clock as LED cycle timestamps)

Effort: ~1 day firmware, straightforward.

### Software changes (Affilabs.core side)

**New method in `ControllerHAL`:**
```python
def get_pending_trigger_events(self) -> list[str]:
    """Poll for any external trigger events received since last call.
    Returns list of event strings, e.g. ['TRIGGER:INJECT'].
    Called from acquisition loop worker thread.
    """
```

**New handler in `InjectionCoordinator`:**
```python
def on_external_injection_trigger(self, elapsed_time: float) -> None:
    """Called when TTL trigger received from external instrument.
    Places injection flag at elapsed_time — same path as manual flag placement.
    Also starts contact timer in InjectionActionBar if a cycle is running.
    """
```

**Integration point:** `_acquisition_mixin._on_spectrum_acquired()` — after each frame, call `ctrl.get_pending_trigger_events()` and route any `TRIGGER:INJECT` events to the coordinator. Fast, non-blocking.

**Settings flag to add:**
```python
# settings/settings.py
EXTERNAL_TRIGGER_ENABLED: bool = False  # Set True when TTL wire connected
EXTERNAL_TRIGGER_DEBOUNCE_S: float = 2.0  # Minimum seconds between triggers
```

### What the user sees

- Injection flag appears automatically at the exact moment Knauer injects — no button press required
- Flag label: `"Auto: [well_id]"` if well ID is known from TCP sequence, else `"Auto: External"`
- If TCP integration also active: cross-check TCP timestamp vs TTL timestamp; log discrepancy if > 3s

### Effort estimate for TTL path

| Task | Where | Effort |
|------|-------|--------|
| Confirm P4PRO GPIO pin + voltage | Firmware team | 0.5 day |
| Firmware: edge detection → serial event | Controller firmware | 1 day |
| `ControllerHAL.get_pending_trigger_events()` | `controller_hal.py` | 0.5 day |
| `InjectionCoordinator.on_external_injection_trigger()` | `injection_coordinator.py` | 0.5 day |
| Wire into acquisition loop | `_acquisition_mixin.py` | 0.5 day |
| Settings flag + debounce | `settings.py` | 0.5 day |
| Testing (bench) | — | 1 day |
| **Total** | | **~4–5 days** |

---

## Success Criteria

- [ ] Autosampler connects via LAN and responds to status queries
- [ ] Single injection: autosampler loads well, AffiPump delivers, sensorgram records binding
- [ ] Multi-cycle unattended run: 8 concentrations complete without user intervention
- [ ] Needle wash between samples: no cross-contamination (verified by blank injection)
- [ ] Graceful error handling: autosampler offline → fallback to manual injection dialog
- [ ] Well assignment visible in cycle table and recorded in experiment metadata
- [ ] Concentration auto-populated in Edits tab Binding plot from well map

Sources:
- [Knauer Azura AS 6.1L User Manual](https://www.knauer.net/Dokumente/autosamplers/AZURA/V6821_Autosampler_AS_6.1L_User-Manual_EN.pdf)
- [Knauer Autosamplers Library](https://www.knauer.net/en/Support/Library/Autosamplers)
