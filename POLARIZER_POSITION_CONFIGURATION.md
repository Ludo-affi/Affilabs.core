# Polarizer Position Configuration Guide

## 📍 How Polarizer Positions Are Set

### Default Positions (Hardcoded)

The polarizer has **TWO servo positions** that are controlled via the `servo_set()` method:

```python
def servo_set(self, s=10, p=100):
    """
    Set polarizer servo positions.

    Args:
        s: S-mode position (default: 10 degrees)
        p: P-mode position (default: 100 degrees)

    Valid range: 0-180 degrees for both positions
    """
```

**Default Values:**
- **S-mode position**: `10` degrees (perpendicular polarization)
- **P-mode position**: `100` degrees (parallel polarization)

### Command Format

The firmware command format is:
```
svSSSPPP\n

Where:
- SSS = 3-digit S-mode position (000-180)
- PPP = 3-digit P-mode position (000-180)

Example: "sv010100\n" sets S=10°, P=100°
```

---

## 🔧 Where Positions Are Used

### 1. Controller Classes

**File**: `utils/controller.py`

#### KineticController
```python
def servo_set(self, s=10, p=100):
    return self._send_command(f"servo_set({s},{p})")
```

#### PicoP4SPR
```python
def servo_set(self, s=10, p=100):
    try:
        if (s < 0) or (p < 0) or (s > 180) or (p > 180):
            raise ValueError(f"Invalid polarizer position given: {s}, {p}")
        cmd = f"sv{s:03d}{p:03d}\n"  # Format: sv010100
        if self.valid():
            if not self.safe_write(cmd):
                return False
            return self.safe_read() == b"1"
        logger.error("unable to update servo positions")
        return False
    except Exception as e:
        logger.debug(f"error setting servo position {e}")
        return False
```

#### PicoEZSPR
```python
def servo_set(self, s=10, p=100):
    try:
        if (s < 0) or (p < 0) or (s > 180) or (p > 180):
            raise ValueError(f"Invalid polarizer position given: {s}, {p}")
        cmd = f"sv{s:03d}{p:03d}\n"
        # ... (same as PicoP4SPR)
```

---

### 2. UI Configuration

**File**: `widgets/advanced.py`

The UI allows users to configure custom positions:

```python
# Settings displayed in UI
settings = [
    "s_pos",  # S-mode position input field
    "p_pos",  # P-mode position input field
]

def update_settings(self):
    """Update settings with current widget entries."""
    self.new_parameter_sig.emit({
        "s_pos": self.ui.s_pos.text(),
        "p_pos": self.ui.p_pos.text(),
        # ... other settings
    })
```

---

### 3. Mode Switching

**File**: `utils/controller.py`

The `set_mode()` method switches between the **PRE-CONFIGURED** positions:

```python
def set_mode(self, mode="s"):
    """Set polarizer to S-mode or P-mode.

    This moves the servo to the POSITION that was previously
    set with servo_set(s, p). It does NOT change the position
    values themselves.

    Commands:
        "ss\n" = Move to S-mode position (the 's' value from servo_set)
        "sp\n" = Move to P-mode position (the 'p' value from servo_set)
    """
    if mode == "s":
        cmd = "ss\n"  # ✅ FIXED: S-mode command
    else:
        cmd = "sp\n"  # ✅ FIXED: P-mode command
```

**IMPORTANT**:
- `set_mode("s")` moves servo to the **position** stored as S-position
- `set_mode("p")` moves servo to the **position** stored as P-position
- The actual degree values were set earlier with `servo_set(s, p)`

---

## 🎯 Auto-Polarization (Optional)

**File**: `utils/spr_calibrator.py` (Line 3731)

The system can automatically find optimal polarizer positions:

```python
def auto_polarize(self, ctrl, usb) -> tuple[int, int] | None:
    """Automatically find optimal polarizer positions for P and S modes.

    Uses peak detection to find the angles where maximum light transmission
    occurs for both polarization modes.

    Returns:
        Tuple of (s_pos, p_pos) if successful, None if failed
    """
    # Sweep parameters
    min_angle = 10
    max_angle = MAX_POLARIZER_ANGLE  # From settings
    half_range = (max_angle - min_angle) // 2
    angle_step = 5

    # Sweep through angles measuring light intensity
    for i in range(steps):
        x = min_angle + angle_step * i
        ctrl.servo_set(s=x, p=x + half_range + angle_step)
        ctrl.set_mode("s")
        max_intensities[i] = usb.read_intensity().max()
        ctrl.set_mode("p")
        max_intensities[i + steps + 1] = usb.read_intensity().max()

    # Find peaks and optimal positions
    p_pos, s_pos = (min_angle + angle_step * edges.mean(0)).astype(int)
    ctrl.servo_set(s_pos, p_pos)  # Set the discovered positions

    logger.info(f"Auto-polarization complete: s={s_pos}, p={p_pos}")
    return s_pos, p_pos
```

---

## 📊 Position Storage & Retrieval

### Getting Current Positions

**File**: `utils/controller.py`

```python
def servo_get(self):
    """Get current servo positions.

    Returns:
        dict: {"s": b"010", "p": b"100"} with 3-digit position values
    """
    cmd = "sr\n"
    curr_pos = {"s": b"000", "p": b"000"}

    if self.valid():
        self.safe_reset_input_buffer()
        if not self.safe_write(cmd):
            logger.error("Failed to write servo get command")
            return curr_pos

        # Read response (format: "010,100")
        line_str = self.safe_readline()
        if len(line_str) >= 7 and "," in line_str:
            s_pos = line_str[0:3]
            p_pos = line_str[4:7]
            result = {"s": s_pos.encode(), "p": p_pos.encode()}
            logger.debug(f"Servo s, p: {result}")
            return result

    return curr_pos
```

### Saving to EEPROM

**File**: `utils/controller.py`

```python
def flash(self):
    """Save current servo positions to EEPROM.

    This makes the positions persistent across power cycles.
    """
    flash_cmd = "sf\n"
    if self.valid():
        if not self.safe_write(flash_cmd):
            return False
        return self.safe_read() == b"1"
    return False
```

---

## 🔍 How It Works: Complete Flow

### Initialization (System Startup)

1. **Default positions** are sent to firmware:
   ```python
   ctrl.servo_set(s=10, p=100)  # Set default positions
   ```

2. **Positions stored in firmware** (in RAM, not EEPROM yet)

### During Calibration (S-mode)

1. **Switch to S-mode**:
   ```python
   ctrl.set_mode("s")  # Sends "ss\n" → moves to position 10°
   ```

2. **Calibration runs** with servo at S-position (10°)

### After Calibration (P-mode)

1. **Switch to P-mode**:
   ```python
   ctrl.set_mode("p")  # Sends "sp\n" → moves to position 100°
   ```

2. **Live measurements** run with servo at P-position (100°)

---

## 🛠️ Manual Position Configuration

### Method 1: Via UI

1. Open **Advanced Settings**
2. Edit **S Position** field (e.g., change 10 to 20)
3. Edit **P Position** field (e.g., change 100 to 110)
4. Click **Apply Settings**
5. New positions take effect on next servo command

### Method 2: Via Code

```python
from utils.controller import PicoP4SPR

ctrl = PicoP4SPR()
ctrl.connect("COM4")

# Set custom positions
ctrl.servo_set(s=20, p=110)  # S=20°, P=110°

# Switch to S-mode (moves to 20°)
ctrl.set_mode("s")

# Switch to P-mode (moves to 110°)
ctrl.set_mode("p")

# Save to EEPROM (persistent across power cycles)
ctrl.flash()
```

### Method 3: Auto-Polarization

```python
from utils.spr_calibrator import SPRCalibrator

calibrator = SPRCalibrator(ctrl, usb)
s_pos, p_pos = calibrator.auto_polarize(ctrl, usb)

if s_pos and p_pos:
    print(f"Optimal positions found: S={s_pos}°, P={p_pos}°")
    ctrl.servo_set(s_pos, p_pos)
    ctrl.flash()  # Save permanently
```

---

## 📋 Position Constraints

**Valid Range**: 0° - 180° for both S and P positions

**Validation**:
```python
if (s < 0) or (p < 0) or (s > 180) or (p > 180):
    raise ValueError(f"Invalid polarizer position given: {s}, {p}")
```

**Typical Values**:
- S-mode: 10-30° (perpendicular polarization)
- P-mode: 90-120° (parallel polarization)
- Difference: Usually 80-90° (perpendicular relationship)

---

## 🎯 Why These Values Matter

### S-Mode (Calibration, ~10°)
- **Purpose**: Reference baseline measurement
- **Orientation**: Light polarized perpendicular to binding surface
- **Signal**: Lower sensitivity to binding events
- **Use**: Calibration and normalization

### P-Mode (Measurement, ~100°)
- **Purpose**: SPR detection
- **Orientation**: Light polarized parallel to binding surface
- **Signal**: High sensitivity to binding events (SPR resonance)
- **Use**: Live measurements and sensorgram generation

### Perpendicular Relationship
- S and P positions should be ~90° apart
- This ensures perpendicular polarization states
- Default: 100° - 10° = 90° separation ✅

---

## 🐛 Common Issues

### Issue 1: Wrong Mode After Calibration
**Symptom**: Polarizer doesn't move to P-mode after calibration
**Cause**: Commands reversed in `set_mode()` (NOW FIXED!)
**Solution**: Fixed in `POLARIZER_COMMAND_BUG_FIX.md`

### Issue 2: Servo Not Moving
**Possible Causes**:
1. **Positions not set**: Call `servo_set(s, p)` before `set_mode()`
2. **Power issue**: Servo needs sufficient power supply
3. **Mechanical jam**: Check for physical obstructions
4. **Wrong COM port**: Verify device connection

### Issue 3: Suboptimal Signal
**Symptom**: Weak SPR signal or poor peak contrast
**Solution**: Run auto-polarization to find optimal positions:
```python
s_pos, p_pos = calibrator.auto_polarize(ctrl, usb)
ctrl.servo_set(s_pos, p_pos)
ctrl.flash()  # Save permanently
```

---

## 📝 Summary

| Aspect | S-Mode | P-Mode |
|--------|---------|---------|
| **Default Position** | 10° | 100° |
| **Command** | `"ss\n"` | `"sp\n"` |
| **Firmware Cmd** | `"sv010100\n"` (sets both) | (same) |
| **Purpose** | Calibration/Reference | SPR Detection |
| **Sensitivity** | Low | High |
| **When Used** | Step 7 (Reference) | Live Measurements |
| **Orientation** | Perpendicular | Parallel |

**Key Point**:
- `servo_set(s, p)` **defines** the positions (10°, 100°)
- `set_mode("s")` or `set_mode("p")` **moves** to those positions
- Positions can be customized via UI, code, or auto-polarization

---

**Document Created**: 2024-10-19
**Related Fixes**: `POLARIZER_COMMAND_BUG_FIX.md`
**Status**: Complete ✅
