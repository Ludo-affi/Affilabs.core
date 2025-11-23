# Servo Calibration Test Script

## Overview

I've created `test_servo_calibration.py` - a comprehensive test script to nail down the servo position calibration sequence before porting it to the main application.

## What It Does

This script implements the **complete servo calibration workflow**:

1. **Hardware Connection**
   - Connects to USB4000/FLAME-T spectrometer via pyseabreeze
   - Connects to PicoP4SPR controller
   - Verifies both devices are functional

2. **Fast Validation Mode** (2 seconds)
   - Reads current EEPROM positions
   - Checks if separation is reasonable (65-95°)
   - Measures actual S and P intensities
   - Validates S/P ratio ≥ 1.3× (ideal ≥ 1.5×)
   - **If valid**: Uses stored positions (skip full sweep)
   - **If invalid**: Triggers full calibration

3. **Full Calibration Mode** (~60 seconds)
   - Sweeps servo from 10° to 170° in 5° steps
   - Measures intensity at each position for both S and P modes
   - Collects ~33 data points across full range

4. **Peak Detection & Analysis**
   - Uses scipy to find peaks in intensity data
   - Identifies the 2 most prominent peaks
   - Calculates peak widths and edge positions
   - Determines optimal S and P servo positions

5. **5-Layer Validation**
   - ✅ **Layer 1**: Peak count ≥ 2
   - ✅ **Layer 2**: Prominent peaks ≥ 2
   - ✅ **Layer 3**: Peak separation 65-95° (expected ~80°)
   - ✅ **Layer 4**: S intensity > P intensity (physical verification)
   - ✅ **Layer 5**: S/P ratio ≥ 1.3× (minimum), ≥ 1.5× (ideal)

6. **Retry Logic**
   - Maximum 3 attempts if validation fails
   - Detailed diagnostics after each failed attempt
   - Shows which validation layer failed and why

7. **Position Application**
   - Sets servo positions on hardware
   - Verifies positions with readback
   - Optionally saves to EEPROM for persistence

## Usage

```bash
# Basic run (tries fast validation first, then full sweep if needed)
python test_servo_calibration.py

# Force full calibration (skip fast validation)
python test_servo_calibration.py --force

# Save positions to EEPROM after success
python test_servo_calibration.py --save

# Force full calibration AND save to EEPROM
python test_servo_calibration.py --force --save
```

## Output Format

The script provides **detailed diagnostic output** at every step:

```
================================================================================
SERVO CALIBRATION TEST
================================================================================
   Force full calibration: False
   Save to EEPROM: False

================================================================================
HARDWARE INITIALIZATION
================================================================================

1. Connecting to spectrometer...
   ✓ Connected: USB4000/FLAME-T
   ✓ Serial: FLMT09788
   ✓ Wavelength range: 441.1 - 786.7 nm
   ✓ Pixels: 3840

2. Connecting to controller...
   ✓ Connected: PicoP4SPR V1.0
   ✓ Current servo positions: S=55, P=145

================================================================================
FAST VALIDATION (EEPROM POSITIONS)
================================================================================
   Current EEPROM positions: S=55, P=145
   Position separation: 90°

   Measuring intensities at stored positions...
   S-mode intensity: 45000 counts
   P-mode intensity: 28000 counts
   S/P ratio: 1.61×
   ✅ VALID - Stored positions are good

✅ CALIBRATION COMPLETE
```

If fast validation fails, it proceeds to full sweep with detailed progress:

```
================================================================================
SERVO POSITION SWEEP
================================================================================

   Sweep range: 10° - 170°
   Step size: 5°
   Total steps: 33
   Estimated time: ~13 seconds
   Integration time: 100.0ms

   Starting sweep at center position (90°)...
   Center position: 42000 counts

   Sweeping positions...
      Step 5/16: S=38000, P=22000
      Step 10/16: S=45000, P=28000
      Step 15/16: S=42000, P=25000

   ✅ Sweep complete
   Intensity range: 15000 - 48000 counts

================================================================================
PEAK ANALYSIS
================================================================================

1. Peak Detection:
   Found 4 peaks
   ✓ PASS: 4 peaks detected

2. Peak Properties:
   Peak 1: Position=55°, Intensity=45000
   Peak 2: Position=145°, Intensity=28000

3. Peak Separation:
   Measured: 90°
   Expected: 65-95°
   ✓ PASS: Separation is valid

4. Intensity Verification:
   S-mode intensity: 45000
   P-mode intensity: 28000
   ✓ PASS: S is higher than P

5. S/P Ratio:
   Measured: 1.61×
   Minimum: 1.30×
   Ideal: 1.50×
   ✓ PASS: Ratio is ideal

================================================================================
✅ ALL VALIDATIONS PASSED
================================================================================
   S position: 55°
   P position: 145°
   S/P ratio: 1.61×
```

## Configuration

All parameters can be adjusted at the top of the script:

```python
# Sweep parameters
MIN_ANGLE = 10          # Start of servo sweep
MAX_ANGLE = 170         # End of servo sweep
ANGLE_STEP = 5          # Step size for sweep

# LED settings
LED_CHANNEL = "a"       # LED channel to use
LED_INTENSITY = 255     # Full intensity for sweep

# Timing
SETTLING_TIME = 0.2     # Servo settling time (seconds)
MODE_SWITCH_TIME = 0.1  # Mode switch delay (seconds)

# Validation thresholds
MIN_PEAKS = 2                      # Minimum number of peaks required
MIN_SEPARATION = 65                # Minimum peak separation (degrees)
MAX_SEPARATION = 95                # Maximum peak separation (degrees)
MIN_SP_RATIO = 1.3                 # Minimum S/P ratio
IDEAL_SP_RATIO = 1.5               # Ideal S/P ratio
MAX_RETRIES = 3                    # Maximum calibration attempts

# Fast validation
FAST_VALIDATION_RATIO = 1.3        # Minimum ratio for fast validation
```

## Return Values

The `calibrate_servo_positions()` function returns a dictionary with results:

```python
{
    "success": True,           # True if calibration succeeded
    "method": "fast_validation",  # "fast_validation" or "full_sweep"
    "s_pos": 55,              # S-mode servo position (degrees)
    "p_pos": 145,             # P-mode servo position (degrees)
    "sp_ratio": 1.61,         # Measured S/P intensity ratio
    "attempts": 0,            # Number of attempts (0 if fast validation worked)
    "validation": [           # List of validation results
        ("Peak count", True, "4 >= 2"),
        ("Peak separation", True, "90° in [65, 95]"),
        ...
    ]
}
```

Returns `None` if all attempts fail.

## Next Steps

Once you've tested this script and are satisfied with the behavior:

1. **Test the script** with your hardware:
   ```bash
   python test_servo_calibration.py
   ```

2. **Verify the positions** are reasonable (should be ~80° apart)

3. **Test saving to EEPROM**:
   ```bash
   python test_servo_calibration.py --save
   ```

4. **Port to main.py**: The key functions to copy are:
   - `fast_validation()` → replaces current validation logic
   - `perform_sweep()` → replaces current sweep code
   - `analyze_peaks()` → replaces current peak analysis
   - `apply_positions()` → adds EEPROM save capability
   - `calibrate_servo_positions()` → master function with retry logic

## Key Improvements Over Current main.py

1. **Fast Path**: 2-second validation vs 60-second sweep (when EEPROM positions are good)
2. **Better Validation**: 5 layers instead of 2
3. **Retry Logic**: 3 attempts with diagnostics
4. **EEPROM Persistence**: Positions survive power cycles
5. **Detailed Logging**: Clear diagnostics at every step
6. **Error Recovery**: Handles edge cases gracefully

## Integration Strategy

To integrate into `main.py`:

1. Copy helper functions (`fast_validation`, `perform_sweep`, `analyze_peaks`)
2. Replace `auto_polarization()` method with new implementation
3. Add `--save-servo` flag to calibration menu
4. Update calibration flow to try fast validation first
5. Add EEPROM save after successful auto-polarization

The test script is **standalone** - you can experiment, modify parameters, and perfect the sequence before touching main.py.
