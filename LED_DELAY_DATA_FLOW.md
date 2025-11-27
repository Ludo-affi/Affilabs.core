# LED Delay Data Flow Analysis

## Current Status: ⚠️ LED DELAYS ARE NOT STORED IN DEVICE CONFIG

**Date**: November 27, 2025
**Finding**: LED delays are **hard-coded defaults** and **NOT part of the device config → calibration → live view data flow**

---

## The Problem

You expected this flow:
```
device_config.json → calibration → live view
     (stored)          (uses)      (applies)
```

But the **actual flow** is:
```
Hard-coded defaults (45ms PRE, 5ms POST)
           ↓
    Advanced Settings UI (optional manual override)
           ↓
    Live View Acquisition (applied immediately)
```

**LED delays are NEVER stored in `device_config.json`** ❌

---

## Current Implementation

### 1. Device Configuration (device_configuration.py)
**Location**: `src/utils/device_configuration.py`

```python
DEFAULT_CONFIG = {
    'timing_parameters': {
        'led_a_delay_ms': 0,  # Per-channel timing offsets (NOT PRE/POST delays!)
        'led_b_delay_ms': 0,
        'led_c_delay_ms': 0,
        'led_d_delay_ms': 0,
        'min_integration_time_ms': 50,
        'led_rise_fall_time_ms': 5,
    },
}
```

**Issue**: These are **per-channel timing offsets**, NOT the PRE/POST LED delays!
- `led_a_delay_ms`: Fine-tuning offset for channel A timing (currently unused)
- NOT the same as `pre_led_delay_ms` (45ms stabilization time)

**Methods**:
```python
def get_led_delays(self) -> Dict[str, float]:
    """Returns per-channel offsets {'a': 0, 'b': 0, 'c': 0, 'd': 0}"""
    # NOT the PRE/POST delays used in acquisition!

def set_led_delays(self, delays: Dict[str, float]):
    """Sets per-channel offsets (NOT PRE/POST delays)"""
```

---

### 2. LED Calibration (led_calibration.py)
**Location**: `Affilabs.core beta/utils/led_calibration.py`

```python
def perform_full_led_calibration(
    usb,
    ctrl: ControllerBase,
    device_type: str,
    # ...
    pre_led_delay_ms: float = 45.0,  # ✅ HARD-CODED DEFAULT
    post_led_delay_ms: float = 5.0,  # ✅ HARD-CODED DEFAULT
) -> LEDCalibrationResult:
```

**Usage in calibration**:
```python
# Line 650
time.sleep(pre_led_delay_ms / 1000.0)  # Wait for LED stabilization
int_array = usb.read_intensity()
time.sleep(post_led_delay_ms / 1000.0)  # Wait for afterglow decay
```

**Issue**: Calibration uses these delays but **NEVER saves them to device_config.json** ❌

---

### 3. Live View Acquisition (data_acquisition_manager.py)
**Location**: `src/core/data_acquisition_manager.py`

```python
def __init__(self, hardware_mgr, ...):
    # Line 153
    self._pre_led_delay_ms = 45.0   # ✅ HARD-CODED DEFAULT
    self._post_led_delay_ms = 5.0   # ✅ HARD-CODED DEFAULT
```

**Usage in acquisition**:
```python
# Line 762 - LED ON
time.sleep(self._pre_led_delay_ms / 1000.0)  # Wait before reading

# Line 833 - LED OFF
time.sleep(self._post_led_delay_ms / 1000.0)  # Wait after reading
```

**Setter method**:
```python
# Line 919
def set_led_delays(self, pre_delay_ms: float, post_delay_ms: float) -> None:
    """Update LED timing delays (can be called during runtime)."""
    self._pre_led_delay_ms = max(0.0, min(200.0, pre_delay_ms))
    self._post_led_delay_ms = max(0.0, min(200.0, post_delay_ms))
    logger.info(f"LED delays updated: PRE={self._pre_led_delay_ms:.1f}ms, POST={self._post_led_delay_ms:.1f}ms")
```

**Called from**: `main_simplified.py` line 3284 when user applies settings in Advanced Settings UI

---

### 4. Main Window (main_simplified.py)
**Location**: `src/main_simplified.py`

```python
def _on_apply_settings(self):
    """Apply polarizer positions, LED intensities, and LED delays to hardware."""

    # Line 3253-3257: Get LED delays from Advanced Settings UI
    pre_led_delay = 45  # ✅ HARD-CODED DEFAULT
    post_led_delay = 5  # ✅ HARD-CODED DEFAULT
    if hasattr(self.main_window, 'advanced_menu') and self.main_window.advanced_menu:
        if hasattr(self.main_window.advanced_menu, 'led_delay_input'):
            pre_led_delay = self.main_window.advanced_menu.led_delay_input.value()
        if hasattr(self.main_window.advanced_menu, 'post_led_delay_input'):
            post_led_delay = self.main_window.advanced_menu.post_led_delay_input.value()

    # Line 3284: Apply to acquisition manager
    if self.data_mgr:
        self.data_mgr.set_led_delays(pre_led_delay, post_led_delay)
        logger.info(f"Applied LED delays: PRE={pre_led_delay}ms, POST={post_led_delay}ms")

    # Line 3293: Save OTHER settings to device config (but NOT LED delays!)
    if self.main_window.device_config:
        self.main_window.device_config.set_servo_positions(s_pos, p_pos)
        self.main_window.device_config.set_led_intensities(led_a, led_b, led_c, led_d)
        self.main_window.device_config.save()
        # ❌ LED delays are NOT saved here!
```

---

## The Missing Link

### What's Missing
1. **No storage in device_config.json**: PRE/POST LED delays are never persisted
2. **No loading on startup**: Acquisition manager always uses hard-coded 45ms/5ms
3. **No calibration-to-live-view transfer**: Calibration delays don't propagate
4. **Manual UI override only**: User must manually set delays in Advanced Settings every session

### Current Per-Channel Delays (in device_config)
```json
"timing_parameters": {
    "led_a_delay_ms": 0,  // Fine-tuning offset (NOT PRE/POST delay)
    "led_b_delay_ms": 0,
    "led_c_delay_ms": 0,
    "led_d_delay_ms": 0
}
```

These are **timing offsets** for staggering channel acquisition, NOT the PRE/POST stabilization delays.

---

## Correct Data Flow (What You Expected)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DEVICE CONFIGURATION                            │
│                    (config/device_config.json)                       │
│                                                                       │
│  "timing_parameters": {                                              │
│      "pre_led_delay_ms": 45.0,    ← SHOULD BE HERE (missing!)      │
│      "post_led_delay_delay_ms": 5.0, ← SHOULD BE HERE (missing!)   │
│      "led_rise_fall_time_ms": 5    ← Already exists                │
│  }                                                                   │
└────────────┬────────────────────────────────────────────────────────┘
             │
             │ ① Load on startup
             ↓
┌─────────────────────────────────────────────────────────────────────┐
│                     LED CALIBRATION                                  │
│              (utils/led_calibration.py)                              │
│                                                                       │
│  def perform_full_led_calibration(                                   │
│      pre_led_delay_ms = device_config.get('pre_led_delay_ms', 45.0) │
│      post_led_delay_ms = device_config.get('post_led_delay_ms', 5.0)│
│  ):                                                                  │
│      # Use loaded delays during calibration                          │
│      time.sleep(pre_led_delay_ms / 1000.0)                          │
│      ...                                                             │
│      # Save back to device_config if user changes them              │
│      device_config.set_led_timing(pre_led_delay_ms, post_led_delay_ms)│
└────────────┬────────────────────────────────────────────────────────┘
             │
             │ ② Transfer after calibration
             ↓
┌─────────────────────────────────────────────────────────────────────┐
│                  LIVE VIEW ACQUISITION                               │
│           (core/data_acquisition_manager.py)                         │
│                                                                       │
│  def __init__(self, hardware_mgr, ...):                              │
│      # Load from device config (not hard-coded!)                     │
│      config = device_config or DeviceConfiguration()                │
│      self._pre_led_delay_ms = config.get('pre_led_delay_ms', 45.0) │
│      self._post_led_delay_ms = config.get('post_led_delay_ms', 5.0)│
│                                                                       │
│  def _acquire_channel_spectrum(...):                                 │
│      time.sleep(self._pre_led_delay_ms / 1000.0)  # Use loaded value│
│      ...                                                             │
│      time.sleep(self._post_led_delay_ms / 1000.0) # Use loaded value│
└─────────────────────────────────────────────────────────────────────┘
```

---

## Actual Data Flow (Current Implementation)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DEVICE CONFIGURATION                            │
│                    (config/device_config.json)                       │
│                                                                       │
│  ❌ PRE/POST LED delays NOT stored here                             │
│  ✅ Only per-channel timing offsets (unused):                       │
│     "led_a_delay_ms": 0                                             │
│     "led_b_delay_ms": 0                                             │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     LED CALIBRATION                                  │
│              (utils/led_calibration.py)                              │
│                                                                       │
│  def perform_full_led_calibration(                                   │
│      pre_led_delay_ms: float = 45.0,  ← HARD-CODED DEFAULT          │
│      post_led_delay_ms: float = 5.0,  ← HARD-CODED DEFAULT          │
│  ):                                                                  │
│      # Uses hard-coded defaults                                      │
│      # NEVER saves to device_config                                 │
└─────────────────────────────────────────────────────────────────────┘

             ❌ NO DATA TRANSFER

┌─────────────────────────────────────────────────────────────────────┐
│                  LIVE VIEW ACQUISITION                               │
│           (core/data_acquisition_manager.py)                         │
│                                                                       │
│  def __init__(self, hardware_mgr, ...):                              │
│      self._pre_led_delay_ms = 45.0   ← HARD-CODED DEFAULT           │
│      self._post_led_delay_ms = 5.0   ← HARD-CODED DEFAULT           │
│                                                                       │
│  ⚠️ Only updated via manual UI override (Advanced Settings)         │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    ADVANCED SETTINGS UI                              │
│                  (main_simplified.py)                                │
│                                                                       │
│  User manually sets LED delays in UI                                 │
│           ↓                                                          │
│  Calls: data_mgr.set_led_delays(pre_delay, post_delay)             │
│  ❌ Does NOT save to device_config.json                             │
│  ❌ Reset to 45ms/5ms on next startup                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Impact

### Current Behavior
1. **Every session** starts with 45ms PRE / 5ms POST delays (hard-coded)
2. **Calibration** uses these defaults (may not be optimal for all hardware)
3. **Live view** uses these defaults unless user manually overrides
4. **Manual changes** in Advanced Settings are **lost on restart**

### Why This Matters
- **Hardware variations**: Different LED PCBs may need different settling times
  - Luminus Cool White: May need 30-40ms
  - Osram Warm White: May need 50-60ms
  - Current: Everyone gets 45ms (one-size-fits-all)

- **Afterglow characteristics**: Different LEDs have different phosphor decay
  - Some LEDs: 5ms POST delay sufficient
  - Others: May need 10-15ms
  - Current: Everyone gets 5ms

- **User tuning**: If user experimentally finds 35ms PRE / 8ms POST works better:
  - Must manually set it EVERY SESSION
  - Settings don't persist
  - Calibration won't use the optimized values

---

## Solution: Implement Proper Data Flow

### Step 1: Add LED Delays to Device Config Schema
**File**: `src/utils/device_configuration.py`

```python
DEFAULT_CONFIG = {
    'timing_parameters': {
        # ADD THESE:
        'pre_led_delay_ms': 45.0,    # LED stabilization time before acquisition
        'post_led_delay_ms': 5.0,    # Afterglow decay time after acquisition

        # KEEP EXISTING:
        'led_a_delay_ms': 0,         # Per-channel timing offsets
        'led_b_delay_ms': 0,
        'led_c_delay_ms': 0,
        'led_d_delay_ms': 0,
        'min_integration_time_ms': 50,
        'led_rise_fall_time_ms': 5,
    },
}

# ADD THESE METHODS:
def get_pre_led_delay_ms(self) -> float:
    """Get PRE LED delay (stabilization time)."""
    return self.config['timing_parameters'].get('pre_led_delay_ms', 45.0)

def get_post_led_delay_ms(self) -> float:
    """Get POST LED delay (afterglow decay time)."""
    return self.config['timing_parameters'].get('post_led_delay_ms', 5.0)

def set_pre_post_led_delays(self, pre_ms: float, post_ms: float):
    """Set PRE/POST LED delays and save to config."""
    self.config['timing_parameters']['pre_led_delay_ms'] = pre_ms
    self.config['timing_parameters']['post_led_delay_ms'] = post_ms
    self.save()
    logger.info(f"LED timing delays saved: PRE={pre_ms}ms, POST={post_ms}ms")
```

---

### Step 2: Load LED Delays in Acquisition Manager
**File**: `src/core/data_acquisition_manager.py`

```python
def __init__(self, hardware_mgr, ...):
    # REPLACE hard-coded defaults with device config loading:

    # OLD (current):
    # self._pre_led_delay_ms = 45.0
    # self._post_led_delay_ms = 5.0

    # NEW:
    from utils.device_configuration import DeviceConfiguration
    device_serial = getattr(hardware_mgr.usb, 'serial_number', None) if hardware_mgr.usb else None
    device_config = DeviceConfiguration(device_serial=device_serial)

    self._pre_led_delay_ms = device_config.get_pre_led_delay_ms()
    self._post_led_delay_ms = device_config.get_post_led_delay_ms()

    logger.info(f"Loaded LED timing delays from device config: PRE={self._pre_led_delay_ms}ms, POST={self._post_led_delay_ms}ms")
```

---

### Step 3: Load LED Delays in Calibration
**File**: `Affilabs.core beta/utils/led_calibration.py`

```python
def perform_full_led_calibration(
    usb,
    ctrl: ControllerBase,
    device_type: str,
    # ...
    device_config=None,
    pre_led_delay_ms: float = None,   # Make optional (default to config value)
    post_led_delay_ms: float = None,  # Make optional (default to config value)
) -> LEDCalibrationResult:

    # Load from device config if not explicitly provided
    if device_config is None:
        from utils.device_configuration import DeviceConfiguration
        device_serial = getattr(usb, 'serial_number', None)
        device_config = DeviceConfiguration(device_serial=device_serial)

    if pre_led_delay_ms is None:
        pre_led_delay_ms = device_config.get_pre_led_delay_ms()
    if post_led_delay_ms is None:
        post_led_delay_ms = device_config.get_post_led_delay_ms()

    logger.info(f"Using LED timing delays: PRE={pre_led_delay_ms}ms, POST={post_led_delay_ms}ms")

    # ... rest of calibration ...
```

---

### Step 4: Save LED Delays When User Changes Them
**File**: `src/main_simplified.py`

```python
def _on_apply_settings(self):
    """Apply polarizer positions, LED intensities, and LED delays to hardware."""

    # Get LED delays from UI
    pre_led_delay = 45
    post_led_delay = 5
    if hasattr(self.main_window, 'advanced_menu') and self.main_window.advanced_menu:
        if hasattr(self.main_window.advanced_menu, 'led_delay_input'):
            pre_led_delay = self.main_window.advanced_menu.led_delay_input.value()
        if hasattr(self.main_window.advanced_menu, 'post_led_delay_input'):
            post_led_delay = self.main_window.advanced_menu.post_led_delay_input.value()

    # Apply to acquisition manager (existing code)
    if self.data_mgr:
        self.data_mgr.set_led_delays(pre_led_delay, post_led_delay)
        logger.info(f"Applied LED delays: PRE={pre_led_delay}ms, POST={post_led_delay}ms")

    # ADD THIS: Save to device config
    if self.main_window.device_config:
        self.main_window.device_config.set_pre_post_led_delays(pre_led_delay, post_led_delay)
        logger.info("✅ LED timing delays saved to device config")
```

---

## Testing Checklist

After implementing the fix:

1. **Device Config Persistence**
   - [ ] Set LED delays to 30ms PRE / 10ms POST in Advanced Settings
   - [ ] Click Apply Settings
   - [ ] Check `device_config.json` contains:
     ```json
     "timing_parameters": {
         "pre_led_delay_ms": 30.0,
         "post_led_delay_ms": 10.0
     }
     ```
   - [ ] Restart application
   - [ ] Verify delays are still 30ms/10ms (not reset to 45ms/5ms)

2. **Calibration Uses Config Values**
   - [ ] Set LED delays to non-default values (e.g., 35ms/8ms)
   - [ ] Run LED calibration
   - [ ] Verify calibration log shows "Using LED timing delays: PRE=35ms, POST=8ms"

3. **Live View Uses Config Values**
   - [ ] Set LED delays to 40ms PRE / 7ms POST
   - [ ] Save and restart
   - [ ] Start live view
   - [ ] Verify acquisition log shows loaded delays (not 45ms/5ms defaults)

4. **Backward Compatibility**
   - [ ] Test with OLD device_config.json (missing PRE/POST delay fields)
   - [ ] Verify falls back to 45ms/5ms defaults
   - [ ] Verify user can set and save new values

---

## Summary

**Current State**: LED delays are hard-coded 45ms/5ms everywhere, with no persistence
**Expected State**: LED delays stored in device_config.json, loaded by calibration and live view
**Root Cause**: `timing_parameters` in device_config only has per-channel offsets, not PRE/POST delays
**Solution**: Add `pre_led_delay_ms` and `post_led_delay_ms` to device config schema and load them on startup

**Impact**: User-optimized LED timing will persist across sessions, calibration will use correct values, hardware-specific timing can be stored per device.
