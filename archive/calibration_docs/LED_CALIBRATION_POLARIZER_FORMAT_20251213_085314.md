# LED Calibration - Polarizer Position Format

**Question**: Why isn't the polarizer position value passed to LED calibration? If it is, how is it written - is it the three-digit format?

**Answer**: ✅ **YES, polarizer positions ARE passed to LED calibration, and YES, they use THREE-DIGIT FORMAT (000-255)**

---

## 🔍 How Polarizer Positions Are Used in LED Calibration

### **Step-by-Step Flow**:

1. **Calibration Start** → Load OEM positions from `device_config.json`
2. **Step 2B** → Validate polarizer positions are correct
3. **Step 3** → **Set to S-mode** for LED brightness ranking
4. **Step 3 continues** → Measure all LEDs in S-polarization mode
5. **Step 4** → Continue LED optimization in S-mode

---

## 📝 Code Evidence

### **1. LED Calibration ALWAYS Uses S-Mode**

**File**: `utils/spr_calibrator.py` (Line ~2043)

```python
def step_3_identify_weakest_channel(self, ch_list: list[str]):
    """STEP 3: Rank all LED channels by brightness"""

    # Set to S-mode and turn off all channels
    self.ctrl.set_mode(mode="s")  # ← Sets polarizer to S-mode position
    time.sleep(0.5)
    self.ctrl.turn_off_channels()
    time.sleep(0.2)

    # ... LED brightness testing continues in S-mode
```

**Key Point**: `set_mode("s")` automatically moves the polarizer to the S-position loaded from config.

---

### **2. set_mode() Implementation**

**File**: `utils/spr_calibrator.py` (Line ~1033)

```python
def set_mode(self, mode):
    """Set mode: 's' for single channel, 'p' for polarized measurement."""
    logger.info(f"Setting controller mode to: {mode}")
    self._current_mode = mode

    try:
        if mode == "s":
            cmd = b"sp\n"  # S-polarization mode ← Sends command to hardware
        else:
            cmd = b"ss\n"  # P-polarization mode

        # Use HAL's serial connection directly
        if hasattr(self._hal, "_ser") and self._hal._ser:
            self._hal._ser.write(cmd)
            response = self._hal._ser.read(10)
            success = b"1" in response
```

**What happens**:
- `set_mode("s")` sends `sp\n` command to PicoP4SPR controller
- Controller firmware reads the S and P positions from memory
- Firmware moves servo to S-position automatically

---

### **3. Positions Are Set During Calibration Init**

**File**: `utils/spr_calibrator.py` (Line ~1850)

```python
def validate_polarizer_positions(self) -> bool:
    """Validate that polarizer positions are correctly configured."""

    logger.info("STEP 2B: Polarizer Position Validation")

    # Get OEM positions from state
    s_pos, p_pos, sp_ratio = self._get_oem_positions()

    # ✅ SET POSITIONS TO HARDWARE
    success = self.ctrl.servo_set(s=s_pos, p=p_pos)

    if not success:
        raise ValueError("Failed to set polarizer positions to hardware")

    logger.info(f"   ✅ Polarizer positions applied to hardware")
    logger.info(f"      S-position: {s_pos}")
    logger.info(f"      P-position: {p_pos}")
```

---

### **4. servo_set() Uses THREE-DIGIT FORMAT**

**File**: `utils/spr_calibrator.py` (Line ~1065)

```python
def servo_set(self, s=10, p=100):
    """Set servo polarizer positions (0-255 raw values)."""
    logger.info(f"Setting servo positions: s={s}, p={p}")

    try:
        if (s < 0) or (p < 0) or (s > 255) or (p > 255):
            raise ValueError(f"Invalid polarizer position given: {s}, {p}")

        # ✅ THREE-DIGIT FORMAT: sv{SSS}{PPP}\n
        cmd = f"sv{s:03d}{p:03d}\n".encode()  # ← Format as 3 digits each

        self._hal._ser.write(cmd)
        response = self._hal._ser.read(10)
        success = b"1" in response
```

**Example**:
- If S=165, P=50 (from your config)
- Command sent: `sv165050\n`
- Format: `sv` + `165` (3 digits) + `050` (3 digits) + `\n`

---

## 🔄 Complete Calibration Flow with Polarizer

```
Calibration Start
    ↓
Step 0: Load device_config.json
    → Reads: polarizer_s_position = 165
    → Reads: polarizer_p_position = 50
    ↓
Step 1: Dark noise measurement
    → LEDs OFF, polarizer position irrelevant
    ↓
Step 2B: Polarizer Position Validation
    → servo_set(s=165, p=50)  ← THREE-DIGIT FORMAT: sv165050\n
    → Hardware stores: S=165, P=50 in memory
    ↓
Step 3: LED Brightness Ranking
    → set_mode("s")  ← Sends: sp\n
    → Hardware moves servo to position 165 (S-mode)
    → Measures all 4 LEDs at 50% intensity
    → Ranks LEDs weakest → strongest
    ↓
Step 4: LED Intensity Optimization
    → STILL in S-mode (polarizer at position 165)
    → Optimizes LED intensities to match weakest channel
    → Final LED values: {a: 255, b: 180, c: 220, d: 190} (example)
    ↓
Step 5: Save Calibration
    → Saves LED intensities to profile
    → Polarizer positions already stored in device_config.json
```

---

## 📊 Protocol Format Details

### **Servo Set Command**:
```
sv{SSS}{PPP}\n

Where:
  sv     = Command prefix (servo set)
  {SSS}  = S-position (3 digits, 000-255)
  {PPP}  = P-position (3 digits, 000-255)
  \n     = Newline terminator
```

### **Examples**:
```python
# Your current config: S=165, P=50
servo_set(s=165, p=50) → "sv165050\n"

# If positions were swapped: S=50, P=165
servo_set(s=50, p=165) → "sv050165\n"

# Maximum range: S=255, P=10
servo_set(s=255, p=10) → "sv255010\n"

# Minimum range: S=10, P=0
servo_set(s=10, p=0) → "sv010000\n"
```

---

## ❓ Why You Might Think It's Not Passed

### **Common Confusion**:

1. **Positions set ONCE, used MANY times**:
   - Positions are set in Step 2B (`servo_set()`)
   - Then `set_mode("s")` or `set_mode("p")` just switches between them
   - You don't see the actual position values in Step 3/4 logs

2. **Implicit vs Explicit**:
   - `set_mode("s")` doesn't show "moving to position 165"
   - It just says "Setting controller mode to: s"
   - But hardware **internally** moves to position 165

3. **Firmware handles the mapping**:
   - `sp\n` command → Firmware reads S-position from memory → Moves servo
   - `ss\n` command → Firmware reads P-position from memory → Moves servo
   - Application doesn't repeat position values

---

## 🔍 How to Verify Positions Are Being Used

### **Check Calibration Logs**:

```
2025-10-20 20:04:22,550 :: WARNING ::    ⚠️ Hardware mismatch: Expected S=165 P=50, got S=30 P=120
2025-10-20 20:04:22,562 :: WARNING ::    Re-applying positions to hardware...
```

**Analysis**:
- Code tried to set S=165, P=50 (from config)
- Hardware reported back S=30, P=120 (actual servo positions)
- **This proves positions ARE being sent!**
- Mismatch suggests:
  - Previous run set different positions
  - Or servo didn't move correctly
  - Or positions need re-verification

---

## ✅ Summary: Answers to Your Questions

### **Q1: Why isn't the polarizer position value passed to LED calibration?**

**A1**: ✅ **IT IS PASSED!**
- Positions loaded from `device_config.json` → `oem_calibration` section
- Set to hardware in Step 2B via `servo_set(s=165, p=50)`
- Used implicitly via `set_mode("s")` in Step 3 and Step 4

### **Q2: Is it written in three-digit format?**

**A2**: ✅ **YES, EXACTLY THREE DIGITS!**
- Format: `sv{SSS}{PPP}\n`
- Example: S=165, P=50 → `sv165050\n`
- Leading zeros for positions < 100 (e.g., P=50 → `050`)

### **Q3: Where can I see this in the code?**

**A3**: Line 1074 in `utils/spr_calibrator.py`:
```python
cmd = f"sv{s:03d}{p:03d}\n".encode()
```
- `{s:03d}` = Format S as 3-digit integer (e.g., 165 → "165", 50 → "050")
- `{p:03d}` = Format P as 3-digit integer

---

## 🔧 Your Current Issue

**Your log shows**:
```
Expected S=165 P=50, got S=30 P=120
```

**Possible causes**:
1. **Servo didn't move** after `servo_set()` command
2. **Positions were overwritten** by previous calibration run
3. **Hardware swap detection** failed (positions might be reversed)

**Solution**:
Run Auto-Polarization from Settings to re-measure and re-set positions with verification.
