# Device Database & Registration System

**Core Document: Device Management & Configuration**
**Last Updated:** February 2, 2026
**Maintainer:** Affilabs.core-AI System

---

## Table of Contents

1. [Overview](#overview)
2. [Device Database Structure](#device-database-structure)
3. [Device Registration Process](#device-registration-process)
4. [Configuration Storage](#configuration-storage)
5. [EEPROM Integration](#eeprom-integration)
6. [Detector Database](#detector-database)
7. [Adding New Devices](#adding-new-devices)
8. [Calibration Files](#calibration-files)
9. [Best Practices](#best-practices)

---

## Overview

The **Device Database System** manages all hardware components in Affilabs.core, tracking their unique identifiers, calibration data, and operational settings. When a new device is connected, it must be properly registered in the database to enable full functionality.

### Key Components

1. **Device Configuration System** - Per-device JSON configuration files
2. **Detector Database** - Detector characteristics and wavelength ranges
3. **Calibration Storage** - Device-specific calibration data (LED models, startup configs, profiles)
4. **EEPROM Sync** - Persistent storage in controller hardware
5. **Device Manager** - Runtime device lifecycle management

### Supported Device Types

- **Spectrometers/Detectors:**
  - Ocean Optics Flame-T (Serial: `FLMT*****`)
  - Ocean Optics USB4000 (Serial: `USB4*****`)
  - Phase Photonics ST Series (Serial: `ST*****`)

- **Controllers:**
  - Arduino P4SPR
  - Raspberry Pi Pico P4SPR
  - Raspberry Pi Pico P4PRO
  - Raspberry Pi Pico P4PROPLUS (with internal pumps)
  - Raspberry Pi Pico EZSPR

- **Servos:**
  - Hitec HS-55MG (default)
  - Alternate servo models

---

## Device Database Structure

### File Organization

```
ezControl-AI/
├── affilabs/
│   └── config/
│       ├── devices/
│       │   ├── FLMT09788/          # Device-specific configs
│       │   │   └── device_config.json
│       │   ├── ST00012/
│       │   │   └── device_config.json
│       │   └── USB4H14526/
│       │       └── device_config.json
│       └── device_config.json      # Default fallback config
│
├── calibrations/
│   └── active/
│       ├── FLMT09788/              # Calibration data storage
│       │   ├── device_profile.json
│       │   ├── startup_config.json
│       │   ├── led_model.json
│       │   └── afterglow_model.json
│       ├── ST00012/
│       │   ├── startup_config.json
│       │   └── led_model.json
│       └── FLMT09116/
│           ├── device_profile.json
│           ├── startup_config.json
│           └── led_model.json
│
└── tools/
    └── ml_training/
        └── data/
            └── device_history.json  # ML training device history database
```

---

## Device Registration Process

### Automatic Registration Flow

When a new device is connected, Affilabs.core follows this auto-detection sequence:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. HARDWARE CONNECTION                                       │
│    - USB detection                                           │
│    - Serial port enumeration                                 │
│    - Device type identification                              │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. SERIAL NUMBER EXTRACTION                                  │
│    - Spectrometer: Query detector serial via USB command    │
│    - Controller: Read firmware ID and device name           │
│    - Verify serial format (e.g., FLMT09788, ST00012)        │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. CONFIGURATION LOOKUP (Priority Order)                    │
│    a) Check: affilabs/config/devices/{SERIAL}/device_config.json │
│    b) Check: Controller EEPROM (if JSON missing)            │
│    c) Create: New config with known info (triggers UI prompt)│
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. HARDWARE SYNC                                             │
│    - Match controller type (Arduino, PicoP4SPR, P4PRO, etc.)│
│    - Auto-detect polarizer type (barrel/round)              │
│    - Validate firmware compatibility                         │
│    - Update config if hardware changed                       │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. CALIBRATION CHECK                                         │
│    - Verify servo positions (S/P)                            │
│    - Check LED intensities (A/B/C/D)                         │
│    - Validate SPR model path                                 │
│    - If missing → trigger OEM calibration workflow          │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. DEVICE READY                                              │
│    - Register with DeviceManager                             │
│    - Load operational settings                               │
│    - Enable UI controls                                      │
└─────────────────────────────────────────────────────────────┘
```

### Configuration Load Priority

1. **JSON File** (Highest Priority)
   - `affilabs/config/devices/{SERIAL}/device_config.json`
   - Device-specific, human-editable
   - Survives power cycles and firmware updates

2. **EEPROM Fallback**
   - Read from controller hardware EEPROM
   - Auto-saved to JSON on first load
   - Used when JSON file is missing

3. **Create New** (Lowest Priority)
   - Partial config with auto-detected info
   - Flags `created_from_scratch = True`
   - Triggers UI prompt for missing fields

---

## Configuration Storage

### Device Configuration File Structure

**Location:** `affilabs/config/devices/{SERIAL}/device_config.json`

```json
{
  "device_info": {
    "config_version": "1.0",
    "created_date": "2025-12-10T14:23:45",
    "last_modified": "2026-01-30T11:44:01",
    "device_id": "FLMT09788"
  },
  "hardware": {
    "led_pcb_model": "luminus_cool_white",
    "led_type_code": "LCW",
    "led_pcb_serial": null,
    "spectrometer_model": "Flame-T",
    "spectrometer_serial": "FLMT09788",
    "controller_model": "Raspberry Pi Pico P4SPR",
    "controller_type": "PicoP4SPR",
    "controller_serial": null,
    "optical_fiber_diameter_um": 200,
    "polarizer_type": "round",
    "servo_model": "HS-55MG",
    "servo_s_position": 133,
    "servo_p_position": 35
  },
  "timing_parameters": {
    "led_off_period_ms": 5.0,
    "detector_wait_before_ms": 35.0,
    "detector_window_ms": 210.0,
    "detector_wait_after_ms": 5.0,
    "min_integration_time_ms": 50,
    "led_rise_fall_time_ms": 5,
    "led_a_delay_ms": 0,
    "led_b_delay_ms": 0,
    "led_c_delay_ms": 0,
    "led_d_delay_ms": 0
  },
  "frequency_limits": {
    "4_led_target_hz": 1.0
  },
  "calibration": {
    "dark_calibration_date": "2025-12-18T00:15:23",
    "s_mode_calibration_date": "2025-12-18T00:20:37",
    "p_mode_calibration_date": "2025-12-18T00:20:37",
    "polarizer_calibration_date": "2025-12-18T00:20:37",
    "polarizer_extinction_ratio_percent": 58.12,
    "factory_calibrated": true,
    "user_calibrated": true,
    "preferred_calibration_mode": "global",
    "integration_time_ms": 30.0,
    "num_scans": 3,
    "led_intensity_a": 128,
    "led_intensity_b": 128,
    "led_intensity_c": 128,
    "led_intensity_d": 128,
    "spr_model_path": "OpticalSystem_QC/FLMT09788/spr_calibration/led_calibration_spr_processed_latest.json",
    "spr_model_calibration_date": "2025-12-18T00:25:10"
  },
  "maintenance": {
    "last_maintenance_date": null,
    "total_measurement_cycles": 1247,
    "led_on_hours": 3.5,
    "next_maintenance_due": "2026-11-01"
  }
}
```

### Field Descriptions

#### Device Info Section

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `config_version` | string | Yes | Configuration schema version |
| `created_date` | ISO datetime | Yes | When config was first created |
| `last_modified` | ISO datetime | Yes | Last modification timestamp |
| `device_id` | string | Yes | Unique device identifier (usually serial) |

#### Hardware Section

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `led_pcb_model` | string | Yes | `luminus_cool_white` or `osram_warm_white` |
| `led_type_code` | string | Yes | `LCW` or `OWW` (short code) |
| `spectrometer_serial` | string | Yes | Detector serial number |
| `spectrometer_model` | string | Yes | `Flame-T`, `USB4000`, or `Phase Photonics ST` |
| `controller_model` | string | Yes | Full controller model name |
| `controller_type` | string | Yes | `Arduino`, `PicoP4SPR`, `PicoP4PRO`, `PicoP4PROPLUS`, `PicoEZSPR` |
| `optical_fiber_diameter_um` | int | Yes | `100` or `200` micrometers |
| `polarizer_type` | string | Yes | `barrel` (2 fixed windows) or `round` (continuous rotation) |
| `servo_s_position` | int | **Required after calibration** | S-mode servo position (PWM units: 1-255) |
| `servo_p_position` | int | **Required after calibration** | P-mode servo position (PWM units: 1-255) |

**CRITICAL:** Servo positions are in **PWM units (1-255)**, NOT degrees. Firmware uses PWM directly.

#### Calibration Section

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `factory_calibrated` | bool | Yes | Factory OEM calibration completed |
| `polarizer_extinction_ratio_percent` | float | After servo cal | (S-P)/S ratio in best bucket (%) |
| `led_intensity_{a,b,c,d}` | int | After LED cal | LED intensities (0-255) |
| `integration_time_ms` | float | After LED cal | Calibrated integration time |
| `spr_model_path` | string | After LED cal | Path to bilinear SPR model JSON |
| `spr_model_calibration_date` | ISO datetime | After LED cal | When SPR model was created |

---

## EEPROM Integration

### Controller EEPROM Storage

Controllers store essential calibration data in EEPROM for fast boot and offline operation:

**EEPROM Fields:**
- `servo_s_position` (int 1-255)
- `servo_p_position` (int 1-255)
- `led_intensity_a` (int 0-255)
- `led_intensity_b` (int 0-255)
- `led_intensity_c` (int 0-255)
- `led_intensity_d` (int 0-255)
- `integration_time_ms` (float)
- `num_scans` (int)
- `led_pcb_model` (string)
- `fiber_diameter_um` (int)
- `polarizer_type` (string)

### Sync Workflow

```python
# Read from EEPROM
if controller.is_config_valid_in_eeprom():
    eeprom_config = controller.read_config_from_eeprom()
    # Convert to full device_config structure
    # Auto-save to JSON for future use

# Write to EEPROM (after calibration)
device_config.save(auto_sync_eeprom=True)
# OR manually:
device_config.sync_to_eeprom(controller)
```

**Tool:** `write_controller_eeprom_from_config.py`

```bash
# Sync device_config.json → EEPROM
python write_controller_eeprom_from_config.py
```

### EEPROM vs JSON Priority

- **JSON is authoritative** (single source of truth)
- EEPROM is **cache/backup** for fast boot
- On first load: EEPROM → JSON (auto-save)
- After calibration: JSON → EEPROM (manual sync)

---

## Detector Database

### Detector Characteristics Database

**Location:** `affilabs/utils/detector_config.py`

```python
DETECTOR_DATABASE = {
    "PhasePhotonics": DetectorCharacteristics(
        name="Phase Photonics ST Series",
        serial_prefix="ST",
        wavelength_min=570.0,  # Valid data starts at 570nm
        wavelength_max=720.0,
        spr_wavelength_min=570.0,
        spr_wavelength_max=720.0,
        max_counts=8191,  # 13-bit ADC (measured saturation ~8K)
        pixels=1848,
    ),
    "USB4000": DetectorCharacteristics(
        name="Ocean Optics USB4000",
        serial_prefix="USB4",
        wavelength_min=560.0,
        wavelength_max=720.0,
        spr_wavelength_min=560.0,
        spr_wavelength_max=720.0,
        max_counts=65535,  # 16-bit ADC
        pixels=3648,
    ),
    "FlameT": DetectorCharacteristics(
        name="Ocean Optics Flame-T",
        serial_prefix="FLMT",
        wavelength_min=560.0,
        wavelength_max=720.0,
        spr_wavelength_min=560.0,
        spr_wavelength_max=720.0,
        max_counts=65535,  # 16-bit ADC
        pixels=2048,
    ),
}
```

### Auto-Detection Logic

```python
from affilabs.utils.detector_config import get_detector_characteristics

# Detect by serial number
detector = get_detector_characteristics(serial_number="ST00012")
# → Returns PhasePhotonics characteristics

# Use detector-specific parameters
wavelength_range = (detector.wavelength_min, detector.wavelength_max)
saturation_threshold = detector.max_counts * 0.90
```

---

## Adding New Devices

### Step-by-Step: Register a New Spectrometer

#### 1. Physical Connection

```
1. Connect spectrometer via USB
2. Connect controller via USB
3. Connect servo to controller (if applicable)
4. Power on system
```

#### 2. Verify USB Detection

```bash
# Windows PowerShell
Get-PnpDevice -Class "Ports" | Where-Object {$_.Status -eq "OK"}

# Look for:
# - Ocean Optics spectrometer (USB serial port)
# - Arduino/Pico controller (COM port)
```

#### 3. Extract Serial Number

**For Ocean Optics (Flame-T, USB4000):**
```python
import seabreeze.spectrometers as sb

devices = sb.list_devices()
print(f"Found: {devices[0].serial_number}")
# Example: FLMT09788
```

**For Phase Photonics:**
```python
from affilabs.hardware.spectrometer_phase import PhasePhotonicsSpectrometer

spec = PhasePhotonicsSpectrometer()
spec.connect()
print(f"Serial: {spec.serial_number}")
# Example: ST00012
```

#### 4. Create Device Directory

```bash
# Create device-specific config folder
mkdir -p affilabs/config/devices/FLMT09788
mkdir -p calibrations/active/FLMT09788
```

#### 5. Launch ezControl (First Boot)

```bash
python main.py
```

**What Happens:**
1. System detects new serial: `FLMT09788`
2. No JSON config found → tries EEPROM
3. EEPROM empty/invalid → creates partial config
4. Sets `created_from_scratch = True`
5. **UI dialog appears** prompting for:
   - LED Model (LCW or OWW)
   - Fiber Diameter (100µm or 200µm)
   - Polarizer Type (barrel or round) - **auto-set if controller detected**

#### 6. User Input Dialog

```
╔═══════════════════════════════════════════════════════╗
║          NEW DEVICE CONFIGURATION                     ║
╠═══════════════════════════════════════════════════════╣
║                                                       ║
║  Device Serial: FLMT09788                            ║
║  Controller: PicoP4SPR (auto-detected)               ║
║                                                       ║
║  Missing Configuration Fields:                        ║
║                                                       ║
║  ⚙ LED Model:                                        ║
║     ○ Luminus Cool White (LCW)                       ║
║     ○ Osram Warm White (OWW)                         ║
║                                                       ║
║  ⚙ Optical Fiber Diameter:                           ║
║     ○ 100 µm                                         ║
║     ○ 200 µm                                         ║
║                                                       ║
║  ✓ Polarizer Type: round (auto-set for PicoP4SPR)   ║
║                                                       ║
║  [ Save & Continue ]  [ Cancel ]                     ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝
```

#### 7. Automatic OEM Calibration

After user input, system automatically runs:

**Step 7a: Servo Calibration**
```
[OEM] 📋 Starting Servo Calibration...
[OEM] 🔍 Scanning positions 1-255 (barrel detection mode)
[OEM] ✓ S-mode detected at position 133 (intensity: 22,513 counts)
[OEM] ✓ P-mode detected at position 35 (intensity: 9,449 counts)
[OEM] 📊 Extinction ratio: 58.12% (good polarization quality)
[OEM] 💾 Saved to device_profile.json
```

**Step 7b: LED Convergence Calibration**
```
[OEM] 📋 Starting LED Calibration...
[OEM] 🎯 Target: 85% of max counts (56,950 counts)
[OEM] 🔧 Using ML-enhanced convergence engine
[OEM] Iteration 1: signals={a: 45203, b: 48912, c: 46788, d: 47234}
[OEM] Iteration 2: signals={a: 54102, b: 55890, c: 53456, d: 54789}
[OEM] ...
[OEM] ✅ CONVERGED at iteration 8
[OEM] 💾 LED intensities: A=128, B=128, C=128, D=128
[OEM] 💾 Integration time: 30ms
[OEM] 💾 Saved to startup_config.json
```

**Step 7c: SPR Model Generation**
```
[OEM] 📋 Building 3-stage linear LED model...
[OEM] 🧪 Sweeping LED intensities: 20-255 (13 points)
[OEM] 🧪 Integration times: 5ms, 10ms, 15ms, 20ms, 30ms, 40ms, 50ms
[OEM] 📊 Channel A: slope_10ms=2.45, R²=0.998
[OEM] 📊 Channel B: slope_10ms=2.38, R²=0.997
[OEM] 📊 Channel C: slope_10ms=2.51, R²=0.999
[OEM] 📊 Channel D: slope_10ms=2.42, R²=0.998
[OEM] ✅ LED model validated (MAE: 85.3 counts, max error: 3.2%)
[OEM] 💾 Saved to led_model.json
```

#### 8. Final Config Save

```
[CONFIG] 💾 Saving complete device configuration...
[CONFIG] ✓ affilabs/config/devices/FLMT09788/device_config.json
[CONFIG] ✓ Syncing to controller EEPROM...
[CONFIG] ✅ Device FLMT09788 fully registered and calibrated
```

#### 9. Verification

```bash
# Check files created
ls -l affilabs/config/devices/FLMT09788/
# → device_config.json

ls -l calibrations/active/FLMT09788/
# → device_profile.json
# → startup_config.json
# → led_model.json
```

---

## Calibration Files

### Device Profile

**Location:** `calibrations/active/{SERIAL}/device_profile.json`

```json
{
  "device_serial": "FLMT09788",
  "device_type": "PicoP4SPR",
  "detector_model": "USB4000",
  "led_type": "LCW",
  "led_type_full": "Luminus Cool White",
  "oem_calibration_version": "1.1",
  "calibration_date": "2025-12-18T00:20:37",
  "polarizer": {
    "s_position": 133,
    "p_position": 35,
    "sp_ratio": 2.38,
    "polarizer_type": "BARREL",
    "method": "servo_calibration_barrel_detection",
    "led_intensity_used": "5%",
    "s_intensity": 22512.76,
    "p_intensity": 9449.27,
    "s_stable_range": [128, 138],
    "p_stable_range": [28, 42]
  },
  "afterglow": {}
}
```

**Purpose:** OEM calibration results from servo calibration workflow.

### Startup Config

**Location:** `calibrations/active/{SERIAL}/startup_config.json`

```json
{
  "device_serial": "FLMT09788",
  "last_updated": "2026-01-30T11:44:01",
  "source": "device_config.json",
  "led_intensities": {
    "s_mode": {
      "a": 128,
      "b": 128,
      "c": 128,
      "d": 128
    },
    "p_mode": {
      "a": 128,
      "b": 128,
      "c": 128,
      "d": 128
    }
  },
  "integration_times": {
    "s_mode_ms": 30.0,
    "p_mode_ms": 30.0
  }
}
```

**Purpose:** Fast boot configuration (loaded on startup before device_config.json).

### LED Model

**Location:** `calibrations/active/{SERIAL}/led_model.json`

```json
{
  "device": {
    "detector_serial": "FLMT09788",
    "calibration_date": "2025-12-10T14:23:45",
    "operator": "AI_System",
    "software_version": "1.06"
  },
  "model_type": "3_stage_linear",
  "channels": {
    "a": {
      "slope_10ms": 2.45,
      "r_squared": 0.998,
      "valid_led_range": [10, 255],
      "valid_time_range": [5, 50]
    },
    "b": { "slope_10ms": 2.38, "r_squared": 0.997 },
    "c": { "slope_10ms": 2.51, "r_squared": 0.999 },
    "d": { "slope_10ms": 2.42, "r_squared": 0.998 }
  },
  "validation": {
    "mean_absolute_error_counts": 85.3,
    "max_error_percent": 3.2
  }
}
```

**Purpose:** Optical model for LED intensity prediction (used by convergence engine).

---

## Best Practices

### New Device Checklist

- [ ] **Physical Setup:**
  - [ ] Connect all USB cables
  - [ ] Verify power supply
  - [ ] Check cable quality (use shielded USB)

- [ ] **Initial Detection:**
  - [ ] Confirm USB enumeration
  - [ ] Extract serial number
  - [ ] Verify firmware compatibility

- [ ] **Configuration:**
  - [ ] Create device folders (`config/devices/{SERIAL}`, `calibrations/active/{SERIAL}`)
  - [ ] Launch ezControl for first boot
  - [ ] Fill user prompt (LED model, fiber diameter)

- [ ] **Calibration:**
  - [ ] Servo calibration completes (S/P positions valid)
  - [ ] LED convergence calibration succeeds (intensities set)
  - [ ] SPR model generated (R² > 0.99)

- [ ] **Verification:**
  - [ ] `device_config.json` created with all fields
  - [ ] EEPROM synced successfully
  - [ ] `device_profile.json`, `startup_config.json`, `led_model.json` present
  - [ ] Test acquisition (S-mode and P-mode)

### Controller Type Detection Rules

**Hardware Rules (Auto-Set):**

| Controller | Polarizer Type | Notes |
|------------|----------------|-------|
| Arduino P4SPR | `round` | Fixed rule |
| PicoP4SPR | `round` | Fixed rule |
| PicoP4PRO | `barrel` | Fixed rule |
| PicoP4PROPLUS | `barrel` | Has internal pumps |
| PicoEZSPR | `barrel` | Typical config |

**CRITICAL:** Never manually override polarizer type if it conflicts with hardware rules.

### Naming Conventions

**Serial Numbers:**
- Ocean Optics Flame-T: `FLMT#####` (5 digits)
- Ocean Optics USB4000: `USB4H#####` (5 digits after H)
- Phase Photonics: `ST#####` (5 digits)

**File Naming:**
- Config: `device_config.json` (always this exact name)
- Profile: `device_profile.json` (OEM calibration results)
- Startup: `startup_config.json` (fast boot settings)
- LED Model: `led_model.json` (optical model)

### Maintenance Schedule

**Recommended:**
- Servo calibration: Every 6 months or 10,000 cycles
- LED calibration: Every 12 months or 50,000 cycles
- Dark calibration: Weekly or before critical experiments
- EEPROM sync: After every calibration update

---

## Adding New Detector Types

### Step 1: Add to Detector Database

Edit `affilabs/utils/detector_config.py`:

```python
DETECTOR_DATABASE = {
    # ... existing entries ...

    "NewDetector": DetectorCharacteristics(
        name="New Detector Model XYZ",
        serial_prefix="XYZ",  # First 3 chars of serial number
        wavelength_min=550.0,  # nm - Valid data start
        wavelength_max=750.0,  # nm - Valid data end
        spr_wavelength_min=560.0,  # nm - SPR search start
        spr_wavelength_max=720.0,  # nm - SPR search end
        max_counts=16383,  # Maximum ADC counts (14-bit example)
        pixels=2048,  # Number of detector pixels
    ),
}
```

### Step 2: Update Spectrometer Factory

Edit `affilabs/hardware/spectrometer_factory.py`:

```python
def create_spectrometer(serial_number: str = None):
    """Create appropriate spectrometer based on serial."""

    if serial_number.startswith("XYZ"):
        from affilabs.hardware.spectrometer_xyz import XYZSpectrometer
        return XYZSpectrometer()
    elif serial_number.startswith("ST"):
        # ... existing logic
```

### Step 3: Implement Spectrometer Driver

Create `affilabs/hardware/spectrometer_xyz.py`:

```python
from .spectrometer_interface import ISpectrometer

class XYZSpectrometer(ISpectrometer):
    """Driver for XYZ detector."""

    def connect(self) -> bool:
        # USB connection logic
        pass

    def set_integration_time(self, time_ms: float) -> None:
        # Set integration time
        pass

    def acquire_spectrum(self) -> np.ndarray:
        # Capture spectrum
        pass

    # ... implement all ISpectrometer methods
```

### Step 4: Test New Detector

```bash
# Connect detector and run detection test
python test_detector_config.py

# Expected output:
# ✓ Detected: XYZ12345
# ✓ Characteristics: New Detector Model XYZ
# ✓ Wavelength range: 550-750 nm
# ✓ Max counts: 16383
```

### Step 5: Add Default Config Template

Create `affilabs/config/devices/XYZ_TEMPLATE/device_config.json`:

```json
{
  "hardware": {
    "spectrometer_model": "XYZ Detector",
    "spectrometer_serial": "XYZ#####",
    ...
  }
}
```

---

## Troubleshooting

### Common Issues

**1. Device Not Detected**

*Symptoms:* "No devices found" error on startup

*Causes:*
- USB cable disconnected
- Driver not installed
- Wrong COM port selected

*Solutions:*
```bash
# Windows: Check USB devices
Get-PnpDevice -Class "Ports"

# Install drivers
python fix_usb_drivers_clean.ps1

# Verify connection
python diagnose_usb.py
```

**2. Serial Number Mismatch**

*Symptoms:* Config loaded for wrong device

*Causes:*
- Multiple devices with same serial prefix
- Serial number changed after calibration

*Solutions:*
```python
# Verify current serial
from affilabs.hardware.device_manager import DeviceManager
dm = DeviceManager()
dm.register_spectrometer(spectrometer)
print(f"Serial: {spectrometer.get_serial()}")

# Rename config folder if needed
mv config/devices/OLD_SERIAL config/devices/NEW_SERIAL
```

**3. EEPROM Sync Failed**

*Symptoms:* "EEPROM write did not confirm" warning

*Causes:*
- Firmware version doesn't support EEPROM write ACK (V2.4)
- Controller disconnected during write

*Solutions:*
```bash
# Verify EEPROM content (readback)
python check_controller_eeprom.py

# Manual re-sync
python write_controller_eeprom_from_config.py
```

**4. Missing Calibration Data**

*Symptoms:* `servo_s_position = None` or `led_intensity_a = 0`

*Causes:*
- OEM calibration workflow interrupted
- Config created before calibration

*Solutions:*
```python
# Check calibration status
device_config = DeviceConfiguration(device_serial="FLMT09788")
servo_pos = device_config.get_servo_positions()

if servo_pos is None:
    print("⚠️ Servo calibration required")
    # Run servo calibration workflow
```

---

## Related Documentation

- **[OPTICAL_CONVERGENCE_ENGINE.md](OPTICAL_CONVERGENCE_ENGINE.md)** - LED calibration and ML training
- **DETECTOR_AGNOSTIC_IMPLEMENTATION.md** - Detector database architecture
- **INTERNAL_PUMP_ARCHITECTURE.md** - Controller hardware interfaces
- **ERROR_HANDLING_PATTERNS.md** - Exception handling best practices

---

## Version History

- **v1.1 (Feb 2026)** - Added detector database, auto-detection, EEPROM sync
- **v1.0 (Dec 2025)** - Initial device configuration system
- **v0.9 (Nov 2025)** - OEM calibration workflow integrated
- **v0.8 (Oct 2025)** - Device-specific config folders introduced

---

**Document End**
*For questions or updates, contact: AI System Maintainer*
