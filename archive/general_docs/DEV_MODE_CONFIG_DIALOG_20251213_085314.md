# Developer Mode Configuration Dialog

## Overview

When running in developer mode, the application will automatically detect missing device configuration information and prompt you to fill it in via a modern dialog interface.

## How to Enable Dev Mode

### Option 1: Use the Launch Scripts
```bash
# Windows Command Prompt
run_dev_mode.bat

# PowerShell
.\run_dev_mode.ps1
```

### Option 2: Set Environment Variable Manually
```bash
# Windows Command Prompt
set AFFILABS_DEV=1
python main_simplified.py

# PowerShell
$env:AFFILABS_DEV = "1"
python main_simplified.py

# Linux/Mac
export AFFILABS_DEV=1
python main_simplified.py
```

## What Information Is Collected

When a new device is connected (or configuration is missing), the dialog will prompt for:

1. **LED PCB Model** - Choose between:
   - `luminus_cool_white` (LCW)
   - `osram_warm_white` (OWW)

2. **LED PCB Serial** - Serial number of the LED PCB board
   - Example: `LED-12345`

3. **Controller Serial** - Serial number of the controller board
   - Example: `CTRL-12345`

4. **Optical Fiber Diameter** - Choose between:
   - `200 µm` (standard)
   - `100 µm` (high sensitivity)

5. **Polarizer Type** - Choose between:
   - `barrel` - 2 fixed windows (S and P positions)
   - `round` - Continuous rotation (circular polarizer)
   - **Hardware Rule**: Arduino and PicoP4SPR controllers **always** use `round` polarizer
   - This field will be auto-selected and locked when Arduino or PicoP4SPR is detected

6. **Device ID** (Optional) - User-friendly name for the device
   - Example: `Lab Device #1` or `Production Unit A`

## Configuration Storage

Device configurations are stored in device-specific directories:

```
config/
└── devices/
    └── <spectrometer_serial>/
        └── device_config.json
```

Each device gets its own configuration file based on its spectrometer serial number.

## When Is the Dialog Shown?

The configuration dialog appears when:

1. ✅ Dev mode is enabled (`AFFILABS_DEV=1`)
2. ✅ A device with a serial number connects
3. ✅ Critical configuration fields are missing:
   - LED PCB Serial
   - Controller Serial

If all critical fields are already filled, the dialog will not appear.

## Normal (Production) Mode

In normal mode (dev mode not enabled):
- No configuration prompts are shown
- Missing fields are logged as warnings
- Application uses default values
- Configuration can be manually edited in the JSON file

## Workflow

### OEM/Factory Setup
1. Enable dev mode
2. Connect device
3. Fill in configuration dialog
4. Configuration saved to device-specific file
5. Export configuration to EEPROM (for transfer to customer)

### Customer/End User
1. Receive device with EEPROM containing configuration
2. Transfer configuration file to computer
3. Place in correct directory: `config/devices/<serial>/`
4. No manual configuration needed

## Testing

To test the configuration dialog:

1. Enable dev mode
2. Connect a device
3. Delete the device's configuration file (or LED/Controller serial fields)
4. Reconnect hardware or restart application
5. Dialog should appear automatically

## Troubleshooting

**Dialog doesn't appear:**
- Check that `AFFILABS_DEV=1` is set in environment
- Verify device has a valid serial number
- Check logs for "Dev Mode: Missing device configuration fields"

**Configuration not saving:**
- Check file permissions on `config/devices/` directory
- Check logs for save errors
- Verify device serial number is valid (no special characters)

**Wrong information entered:**
- Edit the JSON file directly: `config/devices/<serial>/device_config.json`
- Or delete the file and reconnect in dev mode to re-enter

## See Also

- `LED_INTENSITY_PERSISTENCE_COMPLETE.md` - Complete configuration system documentation
- `device_configuration.py` - Configuration class implementation
- `LIVE_DATA_CONDITIONS.md` - Hardware connection flow
