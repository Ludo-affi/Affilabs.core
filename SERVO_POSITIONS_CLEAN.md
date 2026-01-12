# Servo Position Architecture - Clean & Simple

## Single Source of Truth
**device_config.json** → **DeviceConfiguration.get_servo_positions()** 

All servo positions read from here. No exceptions.

## Flow (Clean, No Duplication)

```
1. CALIBRATION
   calibrate_polarizer.py finds optimal positions
   ↓
   Saves to device_config.json: s_position, p_position
   
2. STARTUP (settings_helpers.py)
   Read: device_config.get_servo_positions()
   ↓
   Write to firmware flash:
     • PicoP4SPR V2.4.1+: controller.servo_flash(s, p)  ← NEW, CLEAN
     • OLD P4PRO: controller.set_servo_positions(s, p) 
     • PicoEZSPR: positions sent dynamically (no flash)
   
3. RUNTIME
   Python: controller.set_mode("s") or set_mode("p")
   ↓
   Firmware: reads curr_s/curr_p from flash, moves servo
```

## Files & Responsibilities

### SINGLE SOURCE
- **device_config.json** - Stores S/P positions (PWM values)
- **DeviceConfiguration.get_servo_positions()** - Read positions (returns dict)

### CALIBRATION
- **calibrate_polarizer.py** - Finds positions, saves to device_config

### INITIALIZATION  
- **settings_helpers.py** - Loads positions, syncs to firmware at startup

### HARDWARE LAYER
- **controller.servo_flash(s, p)** - PicoP4SPR V2.4.1+ flash write
- **controller.set_servo_positions(s, p)** - OLD P4PRO flash write
- **controller.set_mode("s"/"p")** - Move servo to cached position

### REMOVED DUPLICATES
- ❌ Deleted hardware_manager.get_servo_positions() duplicate logic
- ❌ Removed misleading HAL set_servo_positions() stubs  
- ❌ Simplified controller implementations

## Bug Fixed
**Problem**: Double-swap in led_calibration_result.py was inverting data labels  
**Solution**: Disabled auto-swap since calibration already handles it correctly

## Rules
1. ✓ device_config.json → DeviceConfiguration is ONLY source
2. ✓ Positions written to firmware flash ONCE at startup
3. ✓ No runtime position changes
4. ✓ No reading from firmware (device_config is source)
5. ✓ No duplicate getter methods
6. ✓ Clear controller-specific flash methods

## Controllers
- **PicoP4SPR V2.4.1+**: Uses `servo_flash(s, p)` → `flash:S,P` command
- **OLD P4PRO (Arduino)**: Uses `set_servo_positions(s, p)` → `sv` command
- **PicoEZSPR**: No flash, positions sent with each `set_mode()` call

## Clean!
