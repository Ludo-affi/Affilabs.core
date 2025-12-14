# Hardware Display Logic - Power Button & Device Status

## Valid Hardware Types

**ONLY 5 hardware types should be displayed:**

1. **P4SPR** - Basic 4-channel SPR controller (most popular)
2. **P4PRO** - Advanced SPR controller (often paired with AffiPump)
3. **ezSPR** - Easy-to-use SPR controller
4. **KNX** - Kinetic flow controller (often paired with P4SPR)
5. **AffiPump** - Dual syringe pump system (often paired with P4PRO)

**Common Pairings:**
- **P4SPR alone** (most popular)
- **P4SPR + KNX**
- **P4PRO + AffiPump** (often together)

## Hardware Display Rules

### Display Format
Hardware is displayed in the **"Hardware Connected"** section of the Device Status tab (sidebar).

**Format**: Each hardware type on its own line
```
P4SPR
KNX
AffiPump
```

**NOT like this:**
```
Device: PicoP4SPR          ❌ NO - don't show internal names
Kinetic Controller: KNX2    ❌ NO - don't show technical prefixes
Pump: Connected             ❌ NO - show actual product name
```

### Common Hardware Combinations

#### Configuration 1: P4SPR Standalone (Most Popular)
```
P4SPR
```
- Basic SPR only
- Most common configuration

#### Configuration 2: P4SPR + KNX
```
P4SPR
KNX
```
- Basic SPR with kinetic flow control

#### Configuration 3: P4PRO + AffiPump (Often Together)
```
P4PRO
AffiPump
```
- Advanced SPR with pump system
- Common pairing

#### Configuration 4: P4PRO Standalone
```
P4PRO
```
- Advanced SPR only

#### Configuration 5: ezSPR Standalone
```
ezSPR
```
- Easy-to-use SPR only

#### Configuration 6: AffiPump Standalone
```
AffiPump
```
- Pump system only

## Implementation Details

### Hardware Detection Flow

```
1. Hardware Scan (core/hardware_manager.py)
   ├─→ _connect_controller()
   │   └─→ Returns: P4SPR, P4PRO, or ezSPR
   ├─→ _connect_kinetic()
   │   └─→ Returns: KNX (if present)
   └─→ _connect_pump()
       └─→ Returns: True/False

2. Type Detection (_get_controller_type, _get_kinetic_type)
   └─→ Maps internal names to display names

3. Status Emission (hardware_connected signal)
   └─→ Sends: ctrl_type, knx_type, pump_connected

4. UI Update (affilabs_core_ui.py::update_hardware_status)
   └─→ Displays only valid hardware names
```

### Name Mapping System

#### Controller Names
**Internal HAL Names** → **Display Names**
```python
CONTROLLER_DISPLAY_NAMES = {
    'PicoP4SPR': 'P4SPR',      # Pico-based P4SPR
    'P4SPR': 'P4SPR',          # Arduino-based P4SPR
    'PicoP4PRO': 'P4PRO',      # Pico-based P4PRO
    'P4PRO': 'P4PRO',          # P4PRO controller
    'PicoEZSPR': 'P4PRO',      # PicoEZSPR hardware = P4PRO product
    'EZSPR': 'ezSPR',          # ezSPR alternative name
    'ezSPR': 'ezSPR'           # ezSPR canonical name
}
```

**Important**: `PicoEZSPR` hardware → `P4PRO` product (this is the controller that pairs with AffiPump)

#### Kinetic Controller Names
**Internal HAL Names** → **Display Names**
```python
KNX_DISPLAY_NAMES = {
    'KNX': 'KNX',              # Standard KNX
    'KNX2': 'KNX',             # Dual KNX (display as KNX)
    'PicoKNX2': 'KNX'          # Pico-based KNX
}
```

#### Pump Names
**Detection** → **Display Name**
```python
if pump_connected:
    display_name = "AffiPump"  # Always show as "AffiPump"
```

### Hardware Detection Logic

#### Controller Type Detection
Located in: `core/hardware_manager.py::_get_controller_type()`

```python
# Arduino P4SPR
if name == 'p4spr':
    return 'P4SPR'

# Pico P4SPR
elif name == 'pico_p4spr':
    return 'P4SPR'

# Pico EZSPR hardware = P4PRO product
elif name == 'pico_ezspr':
    return 'P4PRO'
```

**Key Mapping**: `pico_ezspr` (hardware) → `P4PRO` (product name)

P4PRO is often paired with AffiPump. P4SPR is often paired with KNX.

#### Kinetic Type Detection
Located in: `core/hardware_manager.py::_get_kinetic_type()`

```python
# All kinetic controllers map to "KNX"
if 'KNX' in name.upper() or 'KINETIC' in name.upper():
    return 'KNX'
```

### UI Display Logic

Located in: `affilabs_core_ui.py::update_hardware_status()`

```python
devices = []

# Add controller (P4SPR, P4PRO, ezSPR)
if ctrl_type:
    display_name = CONTROLLER_DISPLAY_NAMES.get(ctrl_type, None)
    if display_name:
        devices.append(display_name)
    else:
        logger.warning(f"Unknown controller '{ctrl_type}' - not displayed")

# Add kinetic (KNX)
if knx_type:
    display_name = KNX_DISPLAY_NAMES.get(knx_type, None)
    if display_name:
        devices.append(display_name)
    else:
        logger.warning(f"Unknown kinetic '{knx_type}' - not displayed")

# Add pump (AffiPump)
if pump_connected:
    devices.append("AffiPump")
```

**Key Features:**
- ✅ Only displays mapped hardware names
- ✅ Unknown hardware types logged but NOT displayed
- ✅ Prevents ghost/generic hardware from showing
- ✅ Maintains clean, product-focused UI

## Power Button Logic

### Connection States

#### Disconnected (Gray)
```
● Gray power button
No hardware detected
"No devices found" message shown
```

#### Connected (Green)
```
● Green power button
At least 1 hardware detected
Hardware list populated
```

### Hardware Detection Criteria

**ANY of the following keeps power button green:**
- Controller detected (P4SPR, P4PRO, ezSPR)
- Kinetic detected (KNX)
- Pump detected (AffiPump)
- Spectrometer detected

**Power button logic** (`main_simplified.py::_on_hardware_connected()`):
```python
hardware_detected = any([
    status.get('ctrl_type'),
    status.get('knx_type'),
    status.get('pump_connected'),
    status.get('spectrometer')
])

if hardware_detected:
    set_power_state("connected")  # Green
else:
    set_power_state("disconnected")  # Gray
```

## Unknown Hardware Handling

### What Happens to Unknown Hardware?

**Scenario**: Hardware detected but not in mapping tables

**Behavior**:
1. Warning logged to console:
   ```
   ⚠️ Unknown controller type 'XYZ123' - not displayed in Hardware Connected
   ```
2. Hardware **NOT shown** in Device Status UI
3. Power button **stays gray** (no valid hardware)
4. User sees "No devices found" message

**Rationale**: Prevents confusing/technical hardware names from appearing in production UI.

## Validation & Testing

### Test Cases

#### Test 1: P4SPR Standalone
**Expected**:
```
✅ Hardware Connected:
   • P4SPR
```

#### Test 2: P4SPR + KNX (Often Together)
**Expected**:
```
✅ Hardware Connected:
   • P4SPR
   • KNX
```

#### Test 3: P4PRO + AffiPump (Often Together)
**Expected**:
```
✅ Hardware Connected:
   • P4PRO
   • AffiPump
```

#### Test 4: P4PRO Standalone
**Expected**:
```
✅ Hardware Connected:
   • P4PRO
```

#### Test 5: ezSPR Standalone
**Expected**:
```
✅ Hardware Connected:
   • ezSPR
```

#### Test 6: No Hardware
**Expected**:
```
⚠️ No hardware detected
○ Gray power button
```

### Debug Logging

When hardware is detected, you should see:
```
[INFO] HARDWARE SCAN COMPLETE (2.34s)
  • Controller: pico_p4spr
  • Kinetic:    NOT FOUND
  • Pump:       NOT FOUND
  • Spectro:    CONNECTED
  → Device Type: P4SPR
```

Then in UI update:
```
[INFO] Updating Device Status UI...
  Controller: P4SPR
  Spectrometer: Connected
  Kinetic: None
  Pump: Not connected
```

## Troubleshooting

### Issue: Hardware detected but not shown

**Check**:
1. Is the hardware type in the mapping tables?
2. Look for warning: `Unknown controller type 'XXX'`
3. Add mapping to `CONTROLLER_DISPLAY_NAMES` or `KNX_DISPLAY_NAMES`

### Issue: Wrong hardware name displayed

**Check**:
1. What does `_get_controller_type()` return?
2. Is mapping table correct?
3. Update display name in mapping table

### Issue: Hardware shown with prefix/suffix

**Check**:
1. Mapping should return clean name: "P4SPR" not "Device: P4SPR"
2. UI should use name directly, not add "Device:" prefix

## Files Modified

### Hardware Detection
- `core/hardware_manager.py`
  - `_get_controller_type()` - Returns standardized names
  - `_get_kinetic_type()` - Returns standardized names
  - Lines 366-420

### UI Display
- `affilabs_core_ui.py`
  - `update_hardware_status()` - Maps and displays hardware
  - Lines 4417-4470

### UI Components
- `sidebar_tabs/device_status_builder.py`
  - Builds "Hardware Connected" section
  - Lines 40-90

## Design Philosophy

**Product-Focused**: Show customer-facing product names, not internal technical identifiers.

**Clean & Simple**: Each hardware type on one line, no prefixes/suffixes.

**Maintainable**: Centralized mapping tables make it easy to add new hardware.

**Defensive**: Unknown hardware logged but not displayed, prevents UI confusion.

**Truthful**: Only shows physically connected hardware, no placeholders or mock data.

---

**Last Updated**: November 25, 2025
**Status**: ✅ Complete - Hardware display logic standardized
**Related**: Power button logic, device status UI, HAL factory
