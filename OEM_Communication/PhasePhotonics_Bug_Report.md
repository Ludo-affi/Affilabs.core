# PhasePhotonics Detector - EEPROM Operations & Bug Report

## Overview

This document accompanies the example Python code (`example_eeprom_write.py`) that demonstrates:
1. Reading wavelength calibration from EEPROM
2. Writing wavelength calibration to EEPROM
3. A critical bug with hardware averaging functionality

---

## EEPROM Structure

### Configuration Area
- **Total size**: 4096 bytes
- **Area number**: 0 (used for calibration data)
- **Wavelength calibration offset**: 3072 bytes

### Wavelength Calibration Format
The wavelength calibration consists of 4 polynomial coefficients stored as **big-endian double-precision floats** (8 bytes each):

```
Offset 3072: c0 (constant term, nm)
Offset 3080: c1 (linear term)
Offset 3088: c2 (quadratic term)
Offset 3096: c3 (cubic term)
```

**Polynomial formula:**
```
wavelength(pixel) = c0 + c1*pixel + c2*pixel² + c3*pixel³
```

For 1848 pixels (indexed 0-1847), this produces the wavelength array.

---

## EEPROM Operations

### Reading Calibration

```python
# Read EEPROM config area 0
ret, cc = detector.api.usb_read_config(detector.spec, area_number=0)

# Extract coefficients from offset 3072
coeffs = np.frombuffer(
    cc.data,
    dtype=">f8",  # Big-endian float64
    count=4,       # 4 coefficients
    offset=3072
)
```

### Writing Calibration

```python
# Read current EEPROM
ret, cc = detector.api.usb_read_config(detector.spec, area_number=0)

# Convert new coefficients to big-endian bytes
coeff_bytes = struct.pack('>dddd', c0, c1, c2, c3)

# Modify config data
data_array = bytearray(cc.data)
data_array[3072:3104] = coeff_bytes  # 4 × 8 bytes = 32 bytes

# Copy back to structure
for i, byte in enumerate(data_array):
    cc.data[i] = byte

# Write to EEPROM
ret = detector.api.usb_write_config(detector.spec, cc, area_number=0)
```

---

## CRITICAL BUG: Hardware Averaging Ignores Integration Time

### Expected Behavior

When using hardware averaging:
1. `usb_set_interval(integration_us)` sets the integration time per scan
2. `usb_set_averaging(num_scans)` tells the detector to average N scans internally
3. Each scan should use the configured integration time
4. **Total acquisition time = (num_scans × integration_time) + USB_overhead**

### Actual Behavior (BUG)

The detector performs N scans but **IGNORES the integration time** set by `usb_set_interval()`:
- Uses approximately **1ms per scan** regardless of configured integration time
- Total time is nearly constant (~16ms) for any number of scans or integration time setting
- This makes hardware averaging unusable for our application

### Empirical Evidence

**Test configuration:**
- Integration time: 10ms
- Hardware averaging: 10 scans

**Expected timing:**
```
10 scans × 10ms = 100ms minimum (plus USB overhead)
```

**Actual timing:**
```
Total time: ~16ms
Effective integration time per scan: ~0.8ms
```

**This is physically impossible** if the detector is respecting the integration time setting.

### Test Results

Running the example code shows:

```
Setting integration time to 10.0ms
Integration time verified: 10.0ms

Testing single scan (no averaging):
  Time for 1 scan: ~18ms
  Expected: ~18ms (10ms integration + 8ms USB)
  ✓ CORRECT

Testing 10 scans with hardware averaging:
  Time for 10 scans: ~16ms
  Expected: ~108ms minimum (10 × 10ms + USB)
  ✗ BUG CONFIRMED - detector is ignoring integration time!
```

---

## Impact on Our Application

We require:
- Integration time: 7.908ms per scan
- Time budget: 185ms (detector window)
- Target: 12 scans for √12 = 3.46× SNR improvement

**With working hardware averaging:**
```
12 scans × 7.908ms = 94.9ms ✓ (fits in 185ms window)
```

**Current workaround (software averaging):**
```
12 scans × (7.908ms × 1.93) = 183ms ✓ (barely fits)
```

Software averaging works but is **1.93× slower** due to USB overhead per scan.

---

## Questions for PhasePhotonics

1. **Is this a known bug or intended behavior?**
   - If intended, what is the purpose of hardware averaging if it doesn't use the configured integration time?

2. **Is there a different API call needed?**
   - Should we use a different function to set integration time when using averaging?
   - Is there a combined function that sets both parameters atomically?

3. **Can this be fixed in firmware?**
   - Is a firmware update possible to make `usb_set_averaging()` respect the integration time from `usb_set_interval()`?
   - What is the timeline for a potential fix?

4. **Workaround documentation?**
   - If this is intended behavior, can you provide documentation on the correct way to use hardware averaging?
   - What integration time is actually being used when hardware averaging is enabled?

---

## How to Run the Example Code

### Prerequisites
```bash
pip install numpy
```

### Execution
```bash
python example_eeprom_write.py
```

### Output
The script will:
1. Connect to the detector
2. Read and display current EEPROM calibration coefficients
3. Demonstrate the hardware averaging bug with timing measurements
4. Print a summary report

### Safety Note
The EEPROM write function is **commented out by default** to prevent accidental modification. Only enable it with valid calibration data.

---

## Our API Usage Pattern

```python
# Initialize detector
detector = PhasePhotonics()
detector.open()

# Set integration time (expects MILLISECONDS in our wrapper)
integration_ms = 7.908
detector.set_integration(integration_ms)

# Set hardware averaging (BROKEN - ignores integration time)
detector.set_averaging(num_scans=10)

# Read spectrum
spectrum = detector.read_intensity()  # Returns 1848 uint16 values
```

**Internal wrapper calls:**
```python
def set_integration(self, integration_ms: float) -> bool:
    integration_us = int(integration_ms * 1000)
    ret = self.api.usb_set_interval(self.spec, integration_us)
    if ret == 0:
        self._integration_time = integration_ms / 1000.0  # Store in seconds
    return ret == 0

def set_averaging(self, num_scans: int) -> None:
    self.api.usb_set_averaging(self.spec, num_scans)
```

---

## Contact Information

**Company**: Affilabs
**Application**: Multi-channel optical biosensor system
**Detector Model**: PhasePhotonics spectrometer (1848 pixels, 13-bit ADC)
**Firmware Version**: [Please check your records for our detector serial numbers]

We appreciate your assistance in resolving this issue. Hardware averaging would significantly improve our system performance and reduce USB traffic.
