# EEPROM Device Configuration Specification

## Overview
Store device configuration in controller EEPROM as a portable backup. This allows:
- Device to work on any computer without JSON file
- Recovery from JSON corruption/deletion
- Factory pre-configuration that travels with hardware
- Simplified first-time setup on new systems

## Memory Layout

### EEPROM Structure (Version 1.0)
Total storage: 20 bytes (fits easily in 1KB Arduino EEPROM)

```
Byte  | Field                    | Type    | Values/Range
------|-------------------------|---------|------------------
0     | Config Version          | uint8   | 1 (for v1.0)
1     | LED PCB Model           | uint8   | 0=LCW, 1=OWW
2     | Controller Type         | uint8   | 0=Arduino, 1=PicoP4SPR, 2=PicoEZSPR, 3=qSPR
3     | Fiber Diameter          | uint8   | 100 or 200 (µm)
4     | Polarizer Type          | uint8   | 0=barrel, 1=round
5-6   | Servo S Position        | uint16  | 0-180 degrees (little-endian)
7-8   | Servo P Position        | uint16  | 0-180 degrees (little-endian)
9     | LED A Intensity         | uint8   | 0-255
10    | LED B Intensity         | uint8   | 0-255
11    | LED C Intensity         | uint8   | 0-255
12    | LED D Intensity         | uint8   | 0-255
13-14 | Integration Time        | uint16  | milliseconds (little-endian)
15    | Num Scans               | uint8   | 1-255
16    | Checksum                | uint8   | XOR of bytes 0-15
17-19 | Reserved                | uint8   | 0x00 (future use)
```

### Enumerations

**LED PCB Model (byte 1):**
- `0` = Luminus Cool White (LCW)
- `1` = Osram Warm White (OWW)
- `255` = Unconfigured

**Controller Type (byte 2):**
- `0` = Arduino (legacy)
- `1` = PicoP4SPR (standard 4-channel)
- `2` = PicoEZSPR (2-channel simplified)
- `3` = qSPR (legacy)
- `255` = Unconfigured

**Polarizer Type (byte 4):**
- `0` = Barrel (2 fixed windows - PicoEZSPR only)
- `1` = Round (continuous rotation - Arduino/PicoP4SPR)
- `255` = Unconfigured

## Serial Protocol

### Commands

#### Write Device Config to EEPROM
**Command:** `wc<20_bytes>\n`
- `wc` = write config
- Followed by 20 bytes of binary data (layout above)
- Returns: `1` on success, `0` on failure

**Example:**
```python
config_bytes = bytes([
    1,      # version
    0,      # LCW
    1,      # PicoP4SPR
    200,    # 200µm fiber
    1,      # round polarizer
    10, 0,  # S position = 10 (little-endian)
    100, 0, # P position = 100
    128,    # LED A intensity
    128,    # LED B
    128,    # LED C
    128,    # LED D
    100, 0, # integration time = 100ms
    3,      # num scans = 3
    0xXX,   # checksum (XOR of bytes 0-15)
    0, 0, 0 # reserved
])
controller.write(b'wc' + config_bytes + b'\n')
```

#### Read Device Config from EEPROM
**Command:** `rc\n`
- `rc` = read config
- Returns: 20 bytes of binary data

**Example:**
```python
controller.write(b'rc\n')
time.sleep(0.1)
config_bytes = controller.read(20)
```

#### Check if Config Valid
**Command:** `cv\n`
- `cv` = config valid
- Returns: `1` if valid config exists, `0` if unconfigured/corrupted

### Checksum Calculation
```python
def calculate_checksum(config_bytes: bytes) -> int:
    """XOR checksum of first 16 bytes."""
    checksum = 0
    for byte in config_bytes[0:16]:
        checksum ^= byte
    return checksum
```

## Firmware Requirements

### Arduino (.ino)
- Use `EEPROM.h` library
- Implement `wc`, `rc`, `cv` commands
- Validate checksum on read
- Flash existing `f` command continues to work (now writes both servo+LED+config)

### Pico RP2040 (C/C++)
- Use hardware flash sector for EEPROM emulation
- Reserve 256 bytes at known flash address
- Implement same protocol as Arduino
- Flash command `sf\n` extended to include config

## Python Implementation

### controller.py Changes

```python
class ControllerBase:
    def read_config_from_eeprom(self) -> Optional[Dict[str, Any]]:
        """Read device configuration from controller EEPROM."""
        pass

    def write_config_to_eeprom(self, config: Dict[str, Any]) -> bool:
        """Write device configuration to controller EEPROM."""
        pass

    def is_config_valid_in_eeprom(self) -> bool:
        """Check if valid configuration exists in EEPROM."""
        pass
```

### device_configuration.py Changes

```python
def __init__(self, config_path=None, device_serial=None, controller=None):
    """
    Initialize device configuration.

    Load priority:
    1. JSON file (if exists)
    2. EEPROM (if JSON missing and controller connected)
    3. Prompt user for configuration (if both missing)
    """

def sync_to_eeprom(self, controller) -> bool:
    """
    Push current configuration to controller EEPROM.
    Called on major config changes (LED model, fiber, etc.)
    """
```

## UI Changes

### Device Config Dialog
- Add checkbox: ☐ **Sync to EEPROM** (checked by default)
- Add button: **Push to EEPROM** (manual sync)
- Status indicator: "Config source: JSON" or "Config source: EEPROM (no JSON found)"

### Main Window
- Show EEPROM status in connection panel
- Warn if JSON and EEPROM are out of sync
- Auto-sync EEPROM on calibration completion

## Workflow Examples

### Scenario 1: New Device on Existing Computer
1. Connect device (has EEPROM config from factory)
2. Software checks for JSON → not found
3. Software reads EEPROM → valid config found
4. Software creates JSON from EEPROM data
5. User can start measurements immediately

### Scenario 2: Existing Device on New Computer
1. Connect device (EEPROM has previous config)
2. Software checks for JSON → not found
3. Software reads EEPROM → valid config found
4. Software creates JSON from EEPROM data
5. No recalibration needed

### Scenario 3: Config Update (New Fiber)
1. User changes fiber from 200µm → 100µm in dialog
2. Dialog saves to JSON
3. Dialog auto-syncs to EEPROM
4. Both storage locations now consistent

### Scenario 4: Factory Calibration
1. Factory calibrates device
2. Saves JSON and EEPROM
3. Ships device to customer
4. Customer plugs in → works immediately

## Migration Strategy

### Phase 1: Firmware Update (Required)
- Update Arduino firmware to support `wc`, `rc`, `cv` commands
- Update Pico firmware with same protocol
- Maintain backward compatibility (existing `f` command still works)

### Phase 2: Python Backend (Optional - graceful degradation)
- Add EEPROM methods to controller classes
- Modify DeviceConfiguration to check EEPROM
- If firmware doesn't support new commands, fall back to JSON-only

### Phase 3: UI Integration (Optional)
- Add EEPROM controls to device config dialog
- Add status indicators
- Add manual sync button

## Backward Compatibility

- Old firmware: Software uses JSON-only mode (current behavior)
- New firmware, old software: EEPROM config stored but unused
- New firmware, new software: Full EEPROM backup/restore capability

## Security Considerations

- EEPROM config is read-only from user perspective (no direct editing)
- Changes must go through validated UI dialog
- Checksum prevents corruption detection
- Factory lock option (future): Prevent field modifications

## Testing Checklist

- [ ] Write config to EEPROM with all valid values
- [ ] Read config from EEPROM and verify all fields
- [ ] Test checksum validation (corrupt byte 5, verify detection)
- [ ] Delete JSON, verify load from EEPROM
- [ ] Change LED model in UI, verify EEPROM auto-sync
- [ ] Move device between computers, verify portable config
- [ ] Test with old firmware (verify graceful degradation)
- [ ] Test factory calibration workflow

## Future Enhancements (v2.0)

- Store spectrometer serial number (16 bytes ASCII)
- Store last calibration timestamp (4 bytes UNIX epoch)
- Store factory lock bit (prevent field modifications)
- Store maintenance counters (cycle count, LED hours)
- Expand to 64 bytes for richer metadata
