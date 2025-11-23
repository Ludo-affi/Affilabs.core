# Device Configuration System Status

## ✅ CURRENT IMPLEMENTATION (LL_UI_v1_0.py)

### 1. **Auto-Popup Dialog for Missing Config**
**Status**: ✅ **FULLY IMPLEMENTED** in `LL_UI_v1_0.py`

#### When It Appears:
- **Automatically** when device connects for the first time
- **Only if** critical fields are missing: LED model, controller, fiber diameter, polarizer
- Called from: `_init_device_config()` → `_check_missing_config_fields()` → `_prompt_device_config()`

#### What It Asks For:
1. **LED Model**: LCW (Luminus Cool White) or OWW (Osram Warm White)
2. **Controller**: Arduino, PicoP4SPR, or PicoEZSPR
3. **Fiber Diameter**: A (100 µm) or B (200 µm)
4. **Polarizer Type**: circle or barrel (auto-set based on controller)
5. **Device ID**: Optional detector serial number

#### Smart Features:
- ✅ **Auto-detects** controller type from hardware
- ✅ **Pre-fills** existing values if any
- ✅ **Auto-sets** polarizer based on controller (Arduino/PicoP4SPR → circle, PicoEZSPR → barrel)
- ✅ **Validates** all fields before saving
- ✅ **Confirms** save with popup showing what was saved
- ✅ **Re-checks** after save to ensure no fields still missing

### 2. **Where Config is Stored**

#### ❌ NOT in Controller EEPROM:
```
Device config JSON file ≠ Controller EEPROM
```

**What IS in EEPROM** (controller flash memory):
- ✅ Servo positions (S and P)
- ✅ LED intensities (A, B, C, D)
- ⚠️ Stored via `flash()` command in `utils/controller.py`
- ⚠️ Read/write takes 5-10ms on AVR/RP2040

**What IS in device_config.json** (persistent file):
```json
config/devices/{SERIAL}/device_config.json
├── device_info
│   ├── device_id: "FLMT09116"
│   ├── created_date
│   └── last_modified
├── hardware
│   ├── led_pcb_model: "luminus_cool_white"
│   ├── led_type_code: "LCW"
│   ├── controller_model: "Raspberry Pi Pico P4SPR"
│   ├── controller_type: "PicoP4SPR"
│   ├── optical_fiber_diameter_um: 200
│   ├── polarizer_type: "circular"
│   ├── servo_s_position: 10
│   └── servo_p_position: 100
├── calibration
│   ├── integration_time_ms: 88
│   ├── num_scans: 2
│   ├── led_intensity_a: 168
│   ├── led_intensity_b: 76
│   ├── led_intensity_c: 70
│   └── led_intensity_d: 160
└── maintenance
    ├── led_on_hours: 24.5
    └── last_power_on: "2025-11-23T00:00:00"
```

#### 💡 Why Separate?
- **EEPROM**: Small, limited write cycles (100k), hardware-level settings
- **JSON File**: Large, unlimited writes, device metadata & calibration history
- **Best Practice**: Use EEPROM for runtime settings, JSON for configuration & tracking

### 3. **Flow Diagram**

```
Device Connects
      ↓
initialize_device_on_connection(usb)
      ↓
_init_device_config(device_serial)
      ↓
DeviceConfiguration.__init__(device_serial)
      ├─→ Check if config/devices/{SERIAL}/ exists
      │   NO → Create directory + device_config.json from template
      │   YES → Load existing device_config.json
      ↓
_check_missing_config_fields()
      ├─→ Check LED model
      ├─→ Check controller type
      ├─→ Check fiber diameter
      └─→ Check polarizer type
      ↓
Missing fields? ──YES──→ _prompt_device_config(serial)
      │                         ↓
      │                   DeviceConfigDialog.exec()
      │                         ↓
      │                   User fills form → Save
      │                         ↓
      │                   Update device_config.json
      │                         ↓
      │                   Verify fields complete
      │                         ↓
      │                   Show confirmation popup
      ↓
     NO
      ↓
Continue with calibration
```

---

## ⚠️ NOT YET IN affilabs_core_ui.py

### Current Status:
- ❌ `DeviceConfigDialog` class not copied to `affilabs_core_ui.py`
- ❌ `_init_device_config()` method not in `MainWindowPrototype`
- ❌ `_check_missing_config_fields()` not implemented
- ❌ `_prompt_device_config()` not implemented

### Impact:
- ✅ Old UI (LL_UI_v1_0.py): **Prompts for missing config** ✅
- ❌ New UI (affilabs_core_ui.py): **Skips config dialog** ❌
- ⚠️ If using new UI with a new device: **Config will have default values**

### Workaround:
1. Run old UI once to fill config
2. OR manually edit `config/devices/{SERIAL}/device_config.json`
3. OR new UI will use defaults (works but suboptimal)

---

## 🔧 TO-DO: Port to affilabs_core_ui.py

### Required Steps:

1. **Copy DeviceConfigDialog class** (lines 458-719 from LL_UI_v1_0.py)
   ```python
   # Add to affilabs_core_ui.py before MainWindowPrototype class
   class DeviceConfigDialog(QDialog):
       # ... full dialog implementation ...
   ```

2. **Add _init_device_config() method** to MainWindowPrototype
   ```python
   def _init_device_config(self, device_serial: Optional[str] = None):
       """Initialize device configuration and prompt if fields missing."""
       from utils.device_configuration import DeviceConfiguration
       self.device_config = DeviceConfiguration(device_serial=device_serial)

       if device_serial:
           missing = self._check_missing_config_fields()
           if missing:
               self._prompt_device_config(device_serial)
   ```

3. **Add _check_missing_config_fields()** method
   ```python
   def _check_missing_config_fields(self):
       """Return list of missing critical config fields."""
       if not self.device_config:
           return []
       missing = []
       hw = self.device_config.config.get('hardware', {})
       if not hw.get('led_pcb_model'):
           missing.append('LED Model')
       if not hw.get('controller_type'):
           missing.append('Controller')
       # ... check other fields ...
       return missing
   ```

4. **Add _prompt_device_config()** method
   ```python
   def _prompt_device_config(self, device_serial: str):
       """Show DeviceConfigDialog and save results."""
       dialog = DeviceConfigDialog(self, device_serial, controller_type)
       if dialog.exec() == QDialog.DialogCode.Accepted:
           config_data = dialog.get_config_data()
           # Update device_config.config dict
           # Save to file
   ```

5. **Call from main_simplified.py** (already done! line 445)
   ```python
   # In _on_hardware_connected():
   self.main_window._init_device_config(device_serial=device_serial)
   ```

---

## 📊 Summary Table

| Feature | LL_UI_v1_0.py | affilabs_core_ui.py | EEPROM | device_config.json |
|---------|---------------|---------------------|--------|-------------------|
| Auto-popup for missing fields | ✅ Yes | ❌ No | N/A | ✅ Saved here |
| LED model config | ✅ Yes | ❌ No | ❌ No | ✅ Yes |
| Controller type config | ✅ Yes | ❌ No | ❌ No | ✅ Yes |
| Fiber diameter config | ✅ Yes | ❌ No | ❌ No | ✅ Yes |
| Polarizer type config | ✅ Yes | ❌ No | ❌ No | ✅ Yes |
| Servo positions (S/P) | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes (backup) |
| LED intensities (A/B/C/D) | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes (backup) |
| Calibration history | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes |
| Maintenance tracking | ✅ Yes | ⚠️ Partial | ❌ No | ✅ Yes |

---

## 🎯 Immediate Action Required

### For FLMT09116 (Your Device):
✅ **No Action Needed** - Config already complete:
```json
{
  "hardware": {
    "led_pcb_model": "luminus_cool_white",  ✅
    "controller_model": "Raspberry Pi Pico P4SPR",  ✅
    "optical_fiber_diameter_um": 200,  ✅
    "polarizer_type": "circular",  ✅
    "servo_s_position": 10,  ✅
    "servo_p_position": 100  ✅
  }
}
```

### For New Devices:
⚠️ **Port DeviceConfigDialog to affilabs_core_ui.py** or **Use LL_UI_v1_0.py first-time setup**

---

## 💡 Related Files

- **Dialog Class**: `LL_UI_v1_0.py:458-719` (`DeviceConfigDialog`)
- **Init Method**: `LL_UI_v1_0.py:4514-4547` (`_init_device_config`)
- **Check Method**: `LL_UI_v1_0.py:4549-4577` (`_check_missing_config_fields`)
- **Prompt Method**: `LL_UI_v1_0.py:4615-4727` (`_prompt_device_config`)
- **Config Class**: `utils/device_configuration.py:31` (`DeviceConfiguration`)
- **Controller Flash**: `utils/controller.py:197, 824` (`flash()` method)
- **Main Call**: `main_simplified.py:445` (calls `_init_device_config`)
