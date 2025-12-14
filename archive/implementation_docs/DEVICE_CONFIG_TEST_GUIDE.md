# Device Config Load Priority - Quick Test Guide

## Overview
New device config workflow with improved load priority and automatic calibration.

---

## Load Priority Chain

```
1. JSON file exists?          YES → Load from JSON (no popup)
                               NO  → Go to step 2

2. EEPROM valid?               YES → Load from EEPROM, save to JSON (no popup)
                               NO  → Go to step 3

3. Neither exists?             YES → Create partial config → SHOW POPUP → AUTO CALIBRATE
```

---

## Quick Test Scenarios

### Test 1: Existing JSON (Normal Operation)
**Setup:**
```powershell
# Ensure JSON exists
Test-Path "config/devices/FLMT09116/device_config.json"  # Should be True
```

**Expected Behavior:**
- ✅ Load from JSON
- ❌ No popup shown
- ❌ No calibration triggered
- 📝 Log: "✓ Loaded existing configuration from JSON"

---

### Test 2: EEPROM Fallback
**Setup:**
```powershell
# Delete JSON file
Remove-Item "config/devices/FLMT09116/device_config.json" -Force

# Controller must have valid EEPROM config
# Check via: ctrl.is_config_valid_in_eeprom() → True
```

**Expected Behavior:**
- ✅ Load from EEPROM
- ✅ Auto-save to JSON
- ❌ No popup shown
- ❌ No calibration triggered
- 📝 Log: "✓ Valid configuration found in EEPROM"
- 📝 Log: "✓ Saved EEPROM config to JSON"

---

### Test 3: New Device Setup
**Setup:**
```powershell
# Delete JSON file
Remove-Item "config/devices/FLMT09116/device_config.json" -Force

# Erase EEPROM (in Python/application):
# hardware_mgr.ctrl.erase_config_from_eeprom()
```

**Expected Behavior:**
1. ✅ Create partial config with known info:
   - Device serial: FLMT09116 (from spectrometer)
   - Controller: PicoP4SPR (detected)
   - Polarizer: round (auto-set for PicoP4SPR)

2. ✅ **SHOW POPUP DIALOG**
   - Pre-filled: Device ID = FLMT09116
   - Pre-filled: Controller = PicoP4SPR
   - Pre-filled: Polarizer = circle
   - **USER INPUT:** LED Model (LCW/OWW)
   - **USER INPUT:** Fiber Diameter (A/B)

3. User clicks "Save Configuration"

4. ✅ **AUTO-START CALIBRATION WORKFLOW**
   - Message: "Starting servo calibration..."
   - Runs servo calibration (~1-2 min)
   - User accepts/declines results
   - Message: "Now starting LED calibration..."
   - Runs LED calibration (~30-60 sec)
   - Pulls intensities from data_mgr
   - Pushes complete config to EEPROM
   - Message: "✅ OEM Calibration Complete!"

5. ✅ Device ready for use

**Logs to Watch For:**
```
📋 NEW DEVICE CONFIGURATION - User Input Required
   Device Serial: FLMT09116
   Config created with known info (serial, controller)
   Missing fields: LED model, fiber diameter

Workflow:
   1. User fills device config dialog
   2. Trigger servo calibration (auto-detect S/P positions)
   3. Trigger LED calibration (calculate optimal intensities)
   4. Save complete config to JSON and EEPROM
```

---

## How to Force Each Test

### Force Test 1 (JSON Priority)
```powershell
# Make sure JSON exists and is valid
cd "config/devices/FLMT09116"
cat device_config.json  # Should show valid JSON
```

### Force Test 2 (EEPROM Fallback)
```python
# In Python console or add to test script:
import os
json_path = "config/devices/FLMT09116/device_config.json"
if os.path.exists(json_path):
    os.remove(json_path)
    print(f"✓ Deleted {json_path}")

# Verify EEPROM has config
if hardware_mgr.ctrl.is_config_valid_in_eeprom():
    print("✓ EEPROM config is valid")
else:
    print("❌ EEPROM config is invalid or empty")
```

### Force Test 3 (New Device Flow)
```python
# In Python console or add to test script:
import os
json_path = "config/devices/FLMT09116/device_config.json"
if os.path.exists(json_path):
    os.remove(json_path)
    print(f"✓ Deleted {json_path}")

# Erase EEPROM config
if hasattr(hardware_mgr.ctrl, 'erase_config_from_eeprom'):
    hardware_mgr.ctrl.erase_config_from_eeprom()
    print("✓ Erased EEPROM config")
else:
    print("⚠️ EEPROM erase method not available")
    print("   Manually clear EEPROM or use controller command")

# Now disconnect and reconnect hardware to trigger detection
```

---

## Verification Steps

### After Each Test
1. Check logs for expected messages
2. Verify device_config object:
   ```python
   print(f"created_from_scratch: {device_config.created_from_scratch}")
   print(f"loaded_from_eeprom: {device_config.loaded_from_eeprom}")
   print(f"Config source: {device_config.config_path}")
   ```

3. Check config contents:
   ```python
   hw = device_config.config['hardware']
   print(f"Serial: {hw['spectrometer_serial']}")
   print(f"Controller: {hw['controller_type']}")
   print(f"LED Model: {hw['led_pcb_model']}")
   print(f"Fiber: {hw['optical_fiber_diameter_um']} µm")
   print(f"Polarizer: {hw['polarizer_type']}")
   print(f"Servo Model: {hw['servo_model']}")
   print(f"Servo S: {hw['servo_s_position']} (0-255 range)")
   print(f"Servo P: {hw['servo_p_position']} (0-255 range)")

   cal = device_config.config['calibration']
   print(f"LED A: {cal['led_intensity_a']}")
   print(f"LED B: {cal['led_intensity_b']}")
   print(f"LED C: {cal['led_intensity_c']}")
   print(f"LED D: {cal['led_intensity_d']}")
   ```

---

## Expected Flag States

| Test Scenario | `created_from_scratch` | `loaded_from_eeprom` | Popup? | Calibration? |
|---------------|------------------------|----------------------|--------|--------------|
| Test 1 (JSON) | False                  | False                | No     | No           |
| Test 2 (EEPROM)| False                 | True                 | No     | No           |
| Test 3 (New)   | True                  | False                | Yes    | Yes          |

---

## Troubleshooting

### Popup Shows When It Shouldn't
**Symptom:** Popup appears even though JSON/EEPROM exists

**Check:**
```python
print(f"JSON exists: {device_config.config_path.exists()}")
print(f"EEPROM valid: {hardware_mgr.ctrl.is_config_valid_in_eeprom()}")
print(f"created_from_scratch: {device_config.created_from_scratch}")
```

**Fix:** Ensure JSON file is valid JSON or EEPROM has valid magic bytes

---

### Popup Doesn't Show When It Should
**Symptom:** No popup for new device

**Check:**
```python
print(f"JSON exists: {device_config.config_path.exists()}")
print(f"EEPROM valid: {hardware_mgr.ctrl.is_config_valid_in_eeprom()}")
print(f"created_from_scratch: {device_config.created_from_scratch}")
```

**Expected:** All False, except `created_from_scratch` should be True

---

### Calibration Doesn't Auto-Start
**Symptom:** Popup completes but no calibration triggered

**Check:**
```python
print(f"oem_config_just_completed: {main_window.oem_config_just_completed}")
print(f"Has _start_oem_calibration_workflow: {hasattr(main_window, '_start_oem_calibration_workflow')}")
print(f"Has _run_servo_auto_calibration: {hasattr(app, '_run_servo_auto_calibration')}")
```

**Look for log:**
```
🏭 Device Configuration Complete - Starting Calibration Workflow
```

---

## Success Criteria

✅ **Test 1 Success:**
- No popup shown
- Config loaded in < 1 second
- Log shows "Loaded from JSON"

✅ **Test 2 Success:**
- No popup shown
- Config loaded from EEPROM
- JSON file created automatically
- Log shows "Saved EEPROM config to JSON"

✅ **Test 3 Success:**
- Popup shown with pre-filled fields
- User enters LED model and fiber diameter
- Servo calibration starts automatically
- LED calibration starts after servo
- Complete config saved to JSON and EEPROM
- Success message shown

---

**READY TO TEST!**
