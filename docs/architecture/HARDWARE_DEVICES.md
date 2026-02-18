# Affilabs.core Hardware Devices Reference

**Document Version:** 1.0
**Last Updated:** February 4, 2026
**Software:** Affilabs.core (SPR Control System)

---

## Overview

Affilabs.core supports multiple SPR hardware configurations with different capabilities. This document describes all supported devices, their specifications, and how the system detects and manages them.

---

## Device Architecture

### Hardware Component Types

Affilabs.core manages four main hardware subsystems:

1. **SPR Controller** - Main microcontroller (Pico or Arduino-based)
2. **Detector** - Optical spectrometer (Ocean Optics USB4000/Flame-T)
3. **Pump System** - Fluidics control (AffiPump or Internal Pumps)
4. **Kinetic Controller** - Optional valve/pump control (KNX/KNX2)

### Detection Priority

Hardware scanning follows this order:
1. **Controller**: PicoP4SPR → PicoP4PRO → PicoEZSPR (stops at first found)
2. **Detector**: USB4000/Flame-T via SeaBreeze
3. **Pump**: AffiPump (FTDI) first, then check for internal pumps
4. **Kinetic**: KNX/KNX2 (only if no AffiPump found)

---

## Supported SPR Controllers

### 1. P4SPR (PicoP4SPR)

**Hardware:** Raspberry Pi Pico-based controller
**Firmware ID:** `affinite_P4SPR`
**Product Name:** P4SPR

#### Specifications
- **LED Channels:** 4 (quad-channel SPR)
- **Polarizer:** Round/circular polarizer (servo-controlled, 0-180°)
- **Servo Command:** `servo:<s_pos>,<p_pos>` format
- **Detector:** External spectrometer (USB4000/Flame-T)
- **Fluidics:** No built-in pump (use external AffiPump or manual injection)
- **USB Interface:** Native USB (Pico RP2040)

#### Device Variants
| Configuration | Kinetic Controller | Device Name Display |
|---------------|-------------------|---------------------|
| PicoP4SPR alone | None | **P4SPR** |
| PicoP4SPR + KNX | RPi KNX2 | **P4SPR+KNX** |
| PicoP4SPR + KNX (specific serials) | RPi KNX2 | **ezSPR** |

#### Use Cases
- Basic 4-channel SPR experiments
- Research-grade SPR with manual fluidics
- Paired with AffiPump for automated fluidics
- Paired with KNX for kinetic experiments

---

### 2. P4PRO (PicoP4PRO)

**Hardware:** Raspberry Pi Pico-based controller
**Firmware ID:** `affinite_P4PRO`
**Product Name:** P4PRO

#### Specifications
- **LED Channels:** 4 (quad-channel SPR)
- **Polarizer:** Barrel polarizer (servo-controlled, dual-axis)
- **Servo Command:** `sv <s_pos> <p_pos>` format (different from P4SPR)
- **Valves:** 6-port and 3-way valve control (KC1/KC2)
- **Detector:** External spectrometer (USB4000/Flame-T)
- **Fluidics:** External AffiPump (Tecan Cavro dual syringe pumps)
- **USB Interface:** Native USB (Pico RP2040)

#### Valve System
- **6-Port Valve:** Sample loop (LOAD/INJECT positions)
  - LOAD: KC1=LOW, KC2=HIGH
  - INJECT: KC1=HIGH, KC2=LOW
- **3-Way Valve:** Channel routing (CLOSED/OPEN positions)
  - CLOSED: KC1→A, KC2→C (waste routing)
  - OPEN: KC1→B, KC2→D (sample routing)

#### Use Cases
- Advanced SPR with automated fluidics
- Sample injection experiments (loop-based)
- Multi-channel binding assays
- Kinetic experiments with valve control

#### Typical Configuration
```
P4PRO Controller (Pico)
    ├── USB4000 Spectrometer (optical detection)
    ├── AffiPump (dual syringe pumps via FTDI)
    ├── 6-Port Valve (sample loop)
    └── 3-Way Valve (channel routing)
```

---

### 3. P4PRO+ (PicoP4PROPLUS)

**Hardware:** Raspberry Pi Pico-based controller (V2.3+)
**Firmware ID:** `affinite_P4PROPLUS` or `affinite_P4PRO` with internal pump detection
**Product Name:** P4PRO+ or P4PROPLUS

#### Specifications
- **LED Channels:** 4 (quad-channel SPR)
- **Polarizer:** Barrel polarizer (servo-controlled, dual-axis)
- **Servo Command:** `sv <s_pos> <p_pos>` format
- **Valves:** 6-port and 3-way valve control (KC1/KC2)
- **Detector:** External spectrometer (USB4000/Flame-T)
- **Fluidics:** **Built-in peristaltic pumps** (2× independent channels)
- **USB Interface:** Native USB (Pico RP2040)

#### Internal Pump System
- **Pump 1:** RPM control (10-500 RPM)
- **Pump 2:** RPM control (10-500 RPM)
- **Sync Mode:** Both pumps run at same RPM
- **Individual Mode:** Independent RPM control
- **Correction Factors:** 0.8-1.2× (calibrate flow rates)

#### Detection Method
The system identifies P4PRO+ by:
1. Firmware ID contains "p4proplus", OR
2. Controller has `has_internal_pumps()` method that returns `True`

#### Differences from P4PRO
| Feature | P4PRO | P4PRO+ |
|---------|-------|--------|
| Pumps | External AffiPump | Built-in peristaltic |
| Pump Type | Syringe (Tecan Cavro) | Peristaltic |
| Pump Control | Serial (FTDI) | Firmware commands |
| Flow Rates | Precise (µL/min) | RPM-based (calibrated) |
| Hardware Cost | Higher (external pump) | Lower (integrated) |

#### Use Cases
- Cost-effective automated SPR
- Educational/training systems
- Field deployment (fewer components)
- Portable SPR experiments

---

### 4. ezSPR (PicoEZSPR)

**Hardware:** Raspberry Pi Pico-based controller
**Firmware ID:** `EZSPR` or `AFFINITE`
**Product Name:** ezSPR or AFFINITE

#### Specifications
- **LED Channels:** 2 (dual-channel SPR, red + NIR)
- **Polarizer:** Barrel polarizer (2 fixed windows - S and P)
- **Servo:** None (fixed polarization)
- **Pump Control:** Commands for pump operations
- **Detector:** External spectrometer (USB4000/Flame-T)
- **USB Interface:** Native USB (Pico RP2040)

#### Firmware Variants
| Firmware ID | Product | Pump Support | Channels |
|-------------|---------|--------------|----------|
| EZSPR | ezSPR | Yes | 2 (Red + NIR) |
| AFFINITE | Affinite | Yes | 2 (Red + NIR) |

#### Use Cases
- Simplified SPR experiments (2 channels)
- Integrated pump control
- Educational systems
- Rapid screening applications

**Note:** P4PRO hardware (4 LEDs + servo) is now handled by the separate `PicoP4PRO` class, NOT by `PicoEZSPR`.

---

### 5. P4SPR (Arduino) - LEGACY

**Hardware:** Arduino-based controller (obsolete)
**Firmware ID:** `p4spr`
**Product Name:** P4SPR (Arduino)
**Status:** ⚠️ Legacy hardware - Pico-based controllers preferred

#### Specifications
- **LED Channels:** 4
- **Polarizer:** Round/circular (servo-controlled)
- **USB Interface:** Arduino USB serial
- **Scanning:** Disabled by default (`ENABLE_ARDUINO_SCAN = False`)

**Note:** Most systems now use PicoP4SPR instead. Arduino scanning is disabled to improve connection speed.

---

## Detector Systems

### Ocean Optics USB4000 / Flame-T

**Interface:** USB (SeaBreeze driver)
**Wavelength Range:** ~350-1000 nm (model-dependent)
**Integration Time:** 3-8000 ms (configurable)
**Pixels:** 2048-3648 (model-dependent)

#### Detection Method
- **Library:** SeaBreeze (cross-platform spectrometer driver)
- **Warm-up:** 10 ms dummy read on connection
- **ROI Support:** Hardware Abstraction Layer (HAL) provides `read_roi()` method

#### Typical ROI Settings
| Device | Start Pixel | End Pixel | Wavelength Range |
|--------|-------------|-----------|------------------|
| P4SPR | 1800 | 2200 | ~600-650 nm (red) |
| P4PRO | 1800 | 2200 | ~600-650 nm (red) |
| ezSPR | 1500 | 2500 | Dual-wavelength |

---

## Pump Systems

### AffiPump (External Syringe Pumps)

**Hardware:** Tecan Cavro Centris dual syringe pumps
**Interface:** FTDI serial (USB-to-serial adapter)
**Product Name:** AffiPump

#### Specifications
- **Pump Count:** 2 (dual pump system)
- **Pump Type:** Syringe pumps
- **Syringe Volume:** 1000 µL (1 mL)
- **Flow Rates:** 1-5000 µL/min (precise control)
- **Valves:** 2-position (INPUT/OUTPUT)
- **Communication:** Cavro protocol over serial

#### Operations
- **Prime:** Fill pumps and tubing with buffer (6 cycles × 1000 µL)
- **Cleanup:** Flush system (alternating aspirate/dispense)
- **Simple Injection:** Full loop injection (100 µL sample)
- **Partial Injection:** 30 µL spike injection
- **Continuous Flow:** Run buffer at set flow rate

#### Detection Method
1. Scan for FTDI device via `PumpController.from_first_available()`
2. If found, create `CavroPumpManager` wrapper
3. Wrap with `PumpHAL` for unified interface

#### Typical Configuration
```
AffiPump System
    ├── Pump 1 (address 0x41, 1 mL syringe)
    │   ├── Valve: INPUT (port 1) / OUTPUT (port 2)
    │   └── Operations: Aspirate, Dispense, Home
    └── Pump 2 (address 0x42, 1 mL syringe)
        ├── Valve: INPUT (port 1) / OUTPUT (port 2)
        └── Operations: Aspirate, Dispense, Home
```

---

### P4PRO+ Internal Pumps

**Hardware:** Built-in peristaltic pumps (P4PROPLUS firmware)
**Interface:** Firmware commands (no external serial)
**Product Name:** P4PRO+ Internal Pumps

#### Specifications
- **Pump Count:** 2 (dual pump system)
- **Pump Type:** Peristaltic pumps
- **Control:** RPM-based (10-500 RPM)
- **Flow Rates:** Calibrated via correction factors
- **Sync Mode:** Yes (both pumps at same RPM)
- **Communication:** Firmware commands over USB

#### Operations
- **Start Pump:** Set RPM and direction
- **Stop Pump:** Halt pump operation
- **Sync Mode:** Toggle synchronized operation
- **Correction Factor:** Adjust flow rate (0.8-1.2×)

#### Detection Method
- Controller firmware ID contains "p4proplus", OR
- Controller has `has_internal_pumps()` method returning `True`

#### Flow Rate Calibration
```python
# Example: Pump 1 at 100 RPM with 0.95 correction
actual_rpm = 100 * 0.95 = 95 RPM
# Correction compensates for tubing differences
```

---

## Kinetic Controllers

### KNX / KNX2 (Raspberry Pi-based)

**Hardware:** Raspberry Pi with valve/pump control
**Interface:** USB serial
**Product Name:** KNX or KNX2
**Status:** Only scanned if specific detector serial numbers detected

#### Specifications
- **Valve Control:** Multi-port valve switching
- **Pump Control:** Basic pump operations
- **Communication:** Serial commands over USB
- **Conditional Scanning:** Only if detector serial matches `KNX_SERIAL_PREFIXES`

#### Serial Number Filter
```python
KNX_SERIAL_PREFIXES = ["FLMT09116", "KNX"]
# Only scan for KNX if detector serial starts with these
```

**Note:** KNX scanning is conditional to avoid unnecessary hardware probing on systems without kinetic controllers.

---

## Hardware Abstraction Layer (HAL)

### Controller HAL

**Purpose:** Unified interface for all controller types
**File:** `affilabs/utils/hal/controller_hal.py`

#### Supported Controllers
- `PicoP4SPRAdapter` - Wraps PicoP4SPR
- `PicoP4PROAdapter` - Wraps PicoP4PRO (servo + valves)
- `PicoEZSPRAdapter` - Wraps PicoEZSPR (2 LEDs, pump)

#### Key Features
- Type-safe capability queries (`has_servo()`, `has_valves()`, etc.)
- Consistent API across controller types
- Servo position management via `DeviceConfiguration`
- Automatic device type detection

#### Usage Example
```python
from affilabs.utils.hal.controller_hal import create_controller_hal

# Wrap any controller with HAL
hal_ctrl = create_controller_hal(pico_controller, device_config)

# Query capabilities
if hal_ctrl.has_servo():
    hal_ctrl.servo_set(s=45, p=135)

if hal_ctrl.has_valves():
    hal_ctrl.valve_set_6port_load()
```

---

### Pump HAL

**Purpose:** Unified interface for pump systems
**File:** `affilabs/utils/hal/pump_hal.py`

#### Supported Pumps
- `AffipumpAdapter` - Wraps CavroPumpManager (syringe pumps)

#### Key Features
- Volume operations (aspirate/dispense in µL)
- Valve position control (INPUT/OUTPUT)
- Status queries (position, ready state)
- Consistent API regardless of pump type

#### Usage Example
```python
from affilabs.utils.hal.pump_hal import create_pump_hal

# Wrap pump manager with HAL
pump = create_pump_hal(pump_manager)

# Operations
pump.initialize_pumps()  # Home both pumps
pump.aspirate(1, 500, 1000)  # Pump 1: 500 µL @ 1000 µL/min
pump.dispense(1, 500, 500)   # Pump 1: 500 µL @ 500 µL/min
```

---

### Detector HAL

**Purpose:** ROI reading support for all detectors
**File:** `affilabs/utils/hal/adapters.py`

#### Supported Detectors
- `OceanSpectrometerAdapter` - Wraps USB4000/Flame-T

#### Key Features
- `read_roi(start, end)` - Read specific pixel range
- Fallback to full read if ROI not supported
- Consistent interface across detector types

---

## Hardware Configuration Matrix

### Complete System Configurations

| Device Name | Controller | Detector | Pump | Kinetic | Channels | Polarizer |
|-------------|-----------|----------|------|---------|----------|-----------|
| **P4SPR** | PicoP4SPR | USB4000 | Manual/AffiPump | None | 4 | Round (servo) |
| **P4SPR+KNX** | PicoP4SPR | USB4000 | AffiPump | KNX2 | 4 | Round (servo) |
| **ezSPR** | PicoP4SPR | USB4000 | AffiPump | KNX2 | 4 | Round (servo) |
| **P4PRO** | PicoP4PRO | USB4000 | AffiPump | None | 4 | Barrel (servo) |
| **P4PRO+** | PicoP4PROPLUS | USB4000 | Internal | None | 4 | Barrel (servo) |
| **ezSPR** | PicoEZSPR | USB4000 | Internal | None | 2 | Barrel (fixed) |
| **AFFINITE** | PicoEZSPR | USB4000 | Internal | None | 2 | Barrel (fixed) |

---

## Device Detection Logic

### Controller Scan Order
```
1. Try PicoP4SPR (affinite_P4SPR firmware)
   ├─ Success → Device = "P4SPR" or "P4SPR+KNX" (check for KNX)
   └─ Fail → Continue

2. Try PicoP4PRO (affinite_P4PRO firmware)
   ├─ Success → Check for internal pumps
   │   ├─ Has pumps → Device = "P4PROPLUS"
   │   └─ No pumps → Device = "P4PRO"
   └─ Fail → Continue

3. Try PicoEZSPR (EZSPR/AFFINITE firmware)
   ├─ Success → Device = "ezSPR" or "AFFINITE"
   └─ Fail → No controller found
```

### Pump Detection Logic
```
1. Scan for AffiPump (FTDI serial)
   ├─ Found → Use AffiPump (external syringe pumps)
   └─ Not found → Continue

2. Check controller for internal pumps
   ├─ has_internal_pumps() → True → Use internal pumps
   └─ has_internal_pumps() → False → No pump available
```

### Kinetic Detection Logic
```
IF detector serial in KNX_SERIAL_PREFIXES:
    Scan for KNX controller
ELSE:
    Skip KNX scan (not needed)
```

---

## Firmware ID Reference

| Firmware ID | Controller Class | Product Name | LED Count | Pump | Polarizer |
|-------------|-----------------|--------------|-----------|------|-----------|
| `affinite_P4SPR` | PicoP4SPR | P4SPR | 4 | None | Round (servo) |
| `affinite_P4PRO` | PicoP4PRO | P4PRO | 4 | External | Barrel (servo) |
| `affinite_P4PROPLUS` | PicoP4PRO | P4PRO+ | 4 | Internal | Barrel (servo) |
| `EZSPR` | PicoEZSPR | ezSPR | 2 | Internal | Barrel (fixed) |
| `AFFINITE` | PicoEZSPR | AFFINITE | 2 | Internal | Barrel (fixed) |
| `p4spr` | Arduino | P4SPR (legacy) | 4 | None | Round (servo) |

---

## USB Connection Specifications

### VID/PID Configuration

| Device | VID | PID | Interface |
|--------|-----|-----|-----------|
| Pico Controllers | 0x2E8A | 0x0005 | Native USB |
| FTDI (AffiPump) | 0x0403 | 0x6001 | USB-to-Serial |
| USB4000 | Varies | Varies | SeaBreeze |

### Connection Timeout Settings
```python
CONNECTION_TIMEOUT = 2.0  # Reduced from 8s for faster scans
CONNECTION_RETRY_COUNT = 1  # Single attempt (no retries)
```

---

## Debugging and Troubleshooting

### Enable Hardware Debug Logging
```python
# In affilabs/core/hardware_manager.py
HARDWARE_DEBUG = True  # Verbose logging for troubleshooting
```

### Common Issues

#### No Controller Found
**Symptoms:** Power button stays gray, no hardware detected
**Causes:**
- USB cable disconnected
- Pico not powered
- Driver issues (WinUSB)
- Wrong firmware flashed

**Solutions:**
1. Check USB cable connection
2. Verify Pico power LED is on
3. Check Device Manager (Windows) for COM ports
4. Reflash correct firmware

#### No Detector Found
**Symptoms:** Controller connects, but no spectrometer
**Causes:**
- SeaBreeze driver not installed
- USB bandwidth issues
- Spectrometer not powered

**Solutions:**
1. Install SeaBreeze driver
2. Try different USB port (avoid hubs)
3. Check spectrometer power

#### Pump Not Detected
**Symptoms:** Controller works, but no pump found
**Causes:**
- FTDI driver missing (AffiPump)
- Wrong pump firmware (P4PRO+)
- Serial port conflict

**Solutions:**
1. Install FTDI driver (for AffiPump)
2. Check `has_internal_pumps()` returns True (for P4PRO+)
3. Close other apps using serial ports

---

## Hardware Manager API

### Key Methods

#### `scan_and_connect()`
Non-blocking hardware scan and connection.

#### `disconnect_all()`
Safely disconnect all hardware.

#### `get_controller_type() -> str`
Returns product name: "P4SPR", "P4PRO", "P4PROPLUS", "ezSPR", "AFFINITE"

#### Signals
- `hardware_connected` - Emitted when hardware successfully connects
- `hardware_connection_failed` - Emitted if connection fails

---

## Configuration Files

### Device Configuration
**File:** `device_config.json` (user data directory)

Stores:
- Controller type and model
- Polarizer type (round/barrel)
- Servo calibration positions (S-mode, P-mode)
- ROI settings (start/end pixels)
- Device serial numbers

#### Auto-sync with Hardware
The system automatically updates configuration when new hardware is detected:
- Controller type → Updates `controller_type` field
- Polarizer type → Auto-set based on controller (P4SPR=round, P4PRO=barrel)
- Serial numbers → Cached for fast reconnection

---

## Version History

### Current Hardware Generations

| Generation | Year | Products | Key Features |
|------------|------|----------|--------------|
| Gen 1 | 2018-2020 | Arduino P4SPR | Legacy, 4 LEDs |
| Gen 2 | 2021-2023 | PicoP4SPR, PicoEZSPR | Pico-based, faster USB |
| Gen 3 | 2024-2025 | PicoP4PRO | Standalone P4PRO class |
| Gen 4 | 2025-2026 | P4PROPLUS | Integrated pumps |

---

## Related Documentation

- [PUMP_VALVE_SYSTEM.md](PUMP_VALVE_SYSTEM.md) - Detailed pump and valve documentation
- [CALIBRATION_GUIDE.md](../CALIBRATION_GUIDE.md) - Calibration procedures for all devices
- [HARDWARE_CONNECTION_LOGIC_FIX.md](HARDWARE_CONNECTION_LOGIC_FIX.md) - Connection logic fixes
- [REFACTOR_P4PRO_STANDALONE.md](../REFACTOR_P4PRO_STANDALONE.md) - P4PRO refactoring details
- [P4PROPLUS_IMPLEMENTATION.md](../P4PROPLUS_IMPLEMENTATION.md) - P4PRO+ implementation
- [INTERNAL_PUMP_ARCHITECTURE.md](../INTERNAL_PUMP_ARCHITECTURE.md) - Internal pump architecture

---

## Support Information

For hardware support:
- Check device configuration: Settings → Device Configuration
- View connection logs: Check console output with `HARDWARE_DEBUG = True`
- Verify firmware version: Check controller firmware ID
- Contact: support@affilabs.com

---

**End of Document**
