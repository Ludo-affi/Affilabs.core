# Device-Specific Afterglow Calibration System

## Overview

Each device (identified by detector serial number like FLMT09116, FLMT09788) gets its own configuration directory with device-specific settings and optical calibration data. The system automatically handles:

1. **Device detection** - Identifies detector serial number on connection
2. **Auto-calibration** - Runs optical calibration if missing
3. **Per-device storage** - Each device has its own afterglow correction model
4. **Manual recalibration** - Users/technicians can rerun calibration from settings

## Directory Structure

```
config/
└── devices/
    ├── FLMT09116/
    │   ├── device_config.json          # Device-specific configuration
    │   └── optical_calibration.json    # Afterglow τ tables for this detector
    ├── FLMT09788/
    │   ├── device_config.json
    │   └── optical_calibration.json
    └── [serial_number]/
        ├── device_config.json
        └── optical_calibration.json
```

## Key Components

### 1. DeviceManager (`utils/device_manager.py`)

Core module that manages device-specific configurations:

```python
from utils.device_manager import get_device_manager

device_manager = get_device_manager()

# Set current device (creates directory if needed)
device_dir = device_manager.set_device("FLMT09116")

# Check if optical calibration exists
if device_manager.needs_optical_calibration():
    # Run optical calibration
    pass

# Get path to optical calibration file
optical_cal_path = device_manager.get_optical_calibration_path()
```

**Key Methods:**
- `set_device(serial_number)` - Initialize device configuration
- `needs_optical_calibration()` - Check if calibration missing
- `get_optical_calibration_path()` - Get path to calibration file
- `set_optical_calibration_path(path)` - Update after calibration completes
- `get_device_config()` - Get device-specific configuration dict

### 2. Device Integration (`utils/device_integration.py`)

High-level integration functions for use in application code:

```python
from utils.device_integration import (
    initialize_device_on_connection,
    check_and_request_optical_calibration,
    get_device_optical_calibration_path,
    save_optical_calibration_result
)
```

**Helper Functions:**
- `initialize_device_on_connection(usb_device)` - Call after spectrometer connects
- `check_and_request_optical_calibration()` - Check if calibration needed
- `get_device_optical_calibration_path()` - Get calibration file path
- `save_optical_calibration_result(path)` - Update config after calibration

## Integration Workflow

### Step 1: Hardware Connection

**Location:** `main/main.py` or `utils/spr_state_machine.py`

After spectrometer successfully connects:

```python
from utils.device_integration import initialize_device_on_connection

# After successful spectrometer connection
if self.usb is not None:
    device_dir = initialize_device_on_connection(self.usb)
    if device_dir:
        logger.info(f"✅ Device initialized: {device_dir.name}")
```

This creates/loads the device-specific configuration directory.

### Step 2: Calibration Check

**Location:** `utils/spr_calibrator.py` (after LED calibration completes)

Before starting measurements, check if optical calibration exists:

```python
from utils.device_integration import check_and_request_optical_calibration

# After LED calibration completes
if check_and_request_optical_calibration():
    logger.info("🔬 Optical calibration missing - running automatically...")
    self.run_optical_calibration()  # Run optical calibration workflow
```

### Step 3: Optical Calibration Execution

**Location:** Optical calibration tool (e.g., `utils/afterglow_calibration.py`)

When optical calibration completes:

```python
from utils.device_integration import (
    get_device_manager,
    save_optical_calibration_result
)

# Perform optical calibration as normal
calibration_data = {
    "metadata": {...},
    "channel_data": {...}
}

# Save to device-specific directory
device_manager = get_device_manager()
device_dir = device_manager.current_device_dir
calibration_path = device_dir / "optical_calibration.json"

with open(calibration_path, 'w') as f:
    json.dump(calibration_data, f, indent=2)

# Update device configuration
save_optical_calibration_result(calibration_path)
```

### Step 4: Data Acquisition Initialization

**Location:** `utils/spr_data_acquisition.py` (`__init__` method)

Load device-specific afterglow correction:

```python
from utils.device_integration import get_device_optical_calibration_path

# Load device-specific optical calibration
optical_cal_path = get_device_optical_calibration_path()

if optical_cal_path and optical_cal_path.exists():
    from afterglow_correction import AfterglowCorrection
    
    self.afterglow_correction = AfterglowCorrection(optical_cal_path)
    self.afterglow_correction_enabled = True
    
    logger.info(f"✅ Afterglow correction enabled for device")
    logger.info(f"   Calibration file: {optical_cal_path.name}")
else:
    logger.warning("⚠️ No optical calibration - afterglow correction disabled")
    self.afterglow_correction_enabled = False
```

### Step 5: Manual Recalibration (Settings Menu)

**Location:** `widgets/settings.py` or `widgets/channelmenu.py`

Add button for manual recalibration:

```python
from PySide6.QtWidgets import QPushButton, QMessageBox
from utils.device_integration import get_device_manager

# In UI setup
self.recalibrate_afterglow_btn = QPushButton("Recalibrate Afterglow")
self.recalibrate_afterglow_btn.clicked.connect(self.on_recalibrate_afterglow)

def on_recalibrate_afterglow(self):
    """Handle manual afterglow recalibration request."""
    device_manager = get_device_manager()
    
    if device_manager.current_device_serial is None:
        QMessageBox.warning(self, "Error", "No device connected")
        return
    
    reply = QMessageBox.question(
        self,
        "Recalibrate Afterglow",
        f"Recalibrate afterglow correction for device "
        f"{device_manager.current_device_serial}?\n\n"
        f"This process takes ~5-10 minutes.\n\nContinue?",
        QMessageBox.Yes | QMessageBox.No
    )
    
    if reply == QMessageBox.Yes:
        # Trigger optical calibration
        # This will overwrite existing optical_calibration.json
        self.main_window.run_optical_calibration()
```

## Migration from Old System

### Old System (Global Configuration)
```
config/
├── device_config.json
└── optical_calibration/
    └── system_FLMT09788_20251011.json
```

### New System (Per-Device Configuration)
```
config/
├── device_config.json (legacy/template)
└── devices/
    ├── FLMT09116/
    │   ├── device_config.json
    │   └── optical_calibration.json
    └── FLMT09788/
        ├── device_config.json
        └── optical_calibration.json
```

### Migration Strategy

1. **First connection** - Device gets auto-initialized, creates device directory
2. **Missing calibration** - System detects and runs optical calibration automatically
3. **Existing global config** - Can be used as template for first device
4. **Multiple devices** - Each gets independent configuration, no conflicts

## Benefits

### ✅ Multi-Device Support
- Plug in any device, system automatically handles it
- Each detector gets optimal afterglow correction
- No manual configuration file editing

### ✅ Automatic Calibration
- Missing calibration detected automatically
- Optical calibration runs once per device
- Future connections use existing calibration

### ✅ Easy Recalibration
- One button in settings to recalibrate
- Overwrites existing calibration file
- No file path management needed

### ✅ Clean Organization
- All device data in one place: `config/devices/{serial}/`
- Easy to backup per-device configs
- Can delete device configs without affecting others

## Testing Checklist

- [ ] Connect device → device directory created
- [ ] First connection → optical calibration runs automatically
- [ ] Optical calibration saves to device directory
- [ ] Data acquisition loads device-specific calibration
- [ ] Afterglow correction uses device-specific τ tables
- [ ] Disconnect and reconnect → uses existing calibration
- [ ] Manual recalibration → overwrites calibration file
- [ ] Connect second device → gets separate configuration
- [ ] Switch between devices → correct calibration loaded

## Files Modified/Created

### New Files
- `utils/device_manager.py` - Core device management
- `utils/device_integration.py` - Integration helper functions
- `DEVICE_SPECIFIC_AFTERGLOW_SYSTEM.md` - This documentation

### Files to Modify
- `main/main.py` - Add `initialize_device_on_connection()` call
- `utils/spr_calibrator.py` - Add optical calibration check/trigger
- `utils/spr_data_acquisition.py` - Load device-specific calibration
- `utils/afterglow_calibration.py` - Save to device directory
- `widgets/settings.py` or `widgets/channelmenu.py` - Add recalibration button

## Example: Complete Flow

```
1. User plugs in device FLMT09116
   ↓
2. Software detects serial number
   ↓
3. DeviceManager creates config/devices/FLMT09116/
   ↓
4. System checks for optical_calibration.json → NOT FOUND
   ↓
5. "Running automatic optical calibration for FLMT09116..."
   ↓
6. Optical calibration completes, saves to:
   config/devices/FLMT09116/optical_calibration.json
   ↓
7. Data acquisition loads device-specific calibration
   ↓
8. Afterglow correction uses FLMT09116 τ tables
   ↓
9. User disconnects and reconnects device
   ↓
10. System loads existing calibration → NO RECALIBRATION NEEDED
```

## Next Steps

1. **Integration** - Add function calls at integration points
2. **Testing** - Test with multiple devices
3. **UI** - Add recalibration button to settings
4. **Documentation** - Update user manual with new workflow
5. **Migration** - Plan for migrating existing installations
