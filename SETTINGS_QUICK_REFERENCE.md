# Settings Quick Reference Card

**Location:** `settings/settings.py`  
**Purpose:** Global configuration constants for the SPR control system

---

## 📊 Calibration Settings (Most Important for Troubleshooting)

### **Dark Noise & Reference Measurements**
```python
DARK_NOISE_SCANS = 30      # Number of scans to average for dark noise
REF_SCANS = 20             # Number of scans to average for reference
```
**Troubleshooting:** If calibration is noisy, increase these values (e.g., 50 and 30)

### **Integration Time**
```python
MIN_INTEGRATION = 5        # Minimum detector integration time (ms)
MAX_INTEGRATION = 100      # Maximum detector integration time (ms)
```
**Troubleshooting:** If signal too weak, allow higher MAX_INTEGRATION (e.g., 150ms)

### **LED Intensity**
```python
S_LED_INT = int(0.66 * 255)  # ~168 - S-polarized LED intensity
P_LED_MAX = 255              # Maximum P-polarized LED intensity
S_LED_MIN = 20               # Minimum intensity for saturation check
```
**Troubleshooting:** If LEDs too bright/dim, adjust S_LED_INT (range: 100-255)

### **Target Intensity (Percentage-Based)**
```python
TARGET_INTENSITY_PERCENT = 80   # Target: 80% of detector max
MIN_INTENSITY_PERCENT = 60      # Min acceptable: 60%
MAX_INTENSITY_PERCENT = 90      # Max acceptable: 90%
DETECTOR_MAX_COUNTS = 65535     # 16-bit ADC max
```
**Calculation:**
- Target counts = 80% × 65535 = **52,428 counts**
- Min acceptable = 60% × 65535 = **39,321 counts**
- Max acceptable = 90% × 65535 = **58,982 counts**

**Troubleshooting:** If calibration fails intensity checks:
- Lower MIN_INTENSITY_PERCENT (e.g., 50%)
- Raise MAX_INTENSITY_PERCENT (e.g., 95%)

### **Target Wavelength Range**
```python
TARGET_WAVELENGTH_MIN = 580  # nm - Start of range
TARGET_WAVELENGTH_MAX = 610  # nm - End of range
```
**Troubleshooting:** If peak not in range, adjust (e.g., 560-630nm for wider range)

### **Saturation & Count Thresholds**
```python
S_COUNT_MAX = 64000           # Saturation limit (below 16-bit max)
P_COUNT_THRESHOLD = 3000      # Min P-polarized count for success
```
**Troubleshooting:** 
- If false saturation warnings, raise S_COUNT_MAX (e.g., 65000)
- If P-LED too sensitive, lower P_COUNT_THRESHOLD (e.g., 2000)

### **Development Mode**
```python
DEVELOPMENT_MODE = True       # Skip validation thresholds
```
**Usage:**
- `True` = Skip all validation checks (for testing/fixing)
- `False` = Enforce all thresholds (production mode)

**Troubleshooting:** Keep `True` while debugging, set `False` for production

---

## 🎯 Data Processing Settings

### **Wavelength Range**
```python
MIN_WAVELENGTH = 560   # Minimum wavelength for data
MAX_WAVELENGTH = 720   # Maximum wavelength for data
POL_WAVELENGTH = 620   # Index for auto polarization
```
**Troubleshooting:** Adjust if your sensor has different range

### **Filtering**
```python
FILTERING_ON = True       # Enable/disable filtering
MED_FILT_WIN = 5         # Median filter window size
```
**Troubleshooting:** 
- If data too noisy, increase MED_FILT_WIN (e.g., 7 or 9)
- If data too smooth (losing features), decrease to 3

### **Unit Conversion**
```python
UNIT = "RU"              # Measurement units (RU or nm)
UNIT_LIST = {"nm": 1, "RU": 355}
```
**Troubleshooting:** 
- `"nm"` = Wavelength shift
- `"RU"` = Refractive Units (1 RU = 1/355 nm)

---

## ⚡ Performance Settings

### **Graph Update Rate**
```python
GRAPH_REGION_UPDATE_GAP = 0.1   # 100ms between graph updates
```
**Troubleshooting:** If GUI laggy, increase to 0.2 or 0.3

### **Cycle Time**
```python
CYCLE_TIME = 1.3         # Cycle time for all 4 channels (seconds)
```
**Troubleshooting:** If data acquisition too fast/slow, adjust

### **Recording Interval**
```python
RECORDING_INTERVAL = 15  # Frequency to save data when recording
```
**Troubleshooting:** Adjust based on storage needs

---

## 🔧 Hardware Settings

### **USB4000 Spectrometer**
```python
CP210X_VID = 0x10C4
CP210X_PID = 0xEA60
BAUD_RATE = 115200
```

### **Raspberry Pi Pico Controller**
```python
PICO_VID = 0x2E8A
PICO_PID = 0x000A
```

### **LED Stabilization**
```python
LED_DELAY = 0.1          # LED stabilization delay (seconds)
```
**Troubleshooting:** If LED not stable, increase to 0.2s

### **Max Read Time**
```python
MAX_READ_TIME = 200      # Maximum total read time (ms)
```
**Troubleshooting:** If reads timing out, increase (e.g., 300ms)

---

## 🧪 Debug Settings

### **Debug Flags**
```python
DEBUG = False            # Enable debug mode
SHOW_PLOT = False        # Show test plotting for grab data
SHOW_AUTOSEGMENT = False # Show auto-segmentation plots
DEMO = False             # Demo mode (no hardware required)
```

**Usage:**
- `DEBUG = True` → Verbose logging
- `SHOW_PLOT = True` → See raw spectrometer data plots
- `DEMO = True` → Run without hardware (for GUI testing)

### **Static vs Dynamic Plotting**
```python
STATIC_PLOT = False      # Enable/disable static portion of plots
POP_OUT_SPEC = False     # Pop out spectroscopy window
```

---

## 🎯 Quick Adjustments for Common Issues

### **Issue: Calibration fails - signal too weak**
```python
MAX_INTEGRATION = 150        # Was: 100
S_LED_INT = 200             # Was: 168
MIN_INTENSITY_PERCENT = 50   # Was: 60
```

### **Issue: Calibration fails - signal too strong (saturation)**
```python
S_LED_INT = 120             # Was: 168
S_COUNT_MAX = 60000         # Was: 64000 (more sensitive)
```

### **Issue: Peak not in target range**
```python
TARGET_WAVELENGTH_MIN = 560  # Was: 580
TARGET_WAVELENGTH_MAX = 640  # Was: 610
```

### **Issue: Data too noisy**
```python
DARK_NOISE_SCANS = 50       # Was: 30
REF_SCANS = 30              # Was: 20
MED_FILT_WIN = 7            # Was: 5
```

### **Issue: P-LED calibration too sensitive**
```python
P_COUNT_THRESHOLD = 2000    # Was: 3000
P_MAX_INCREASE = 1.5        # Was: 1.33
```

### **Issue: GUI laggy during measurement**
```python
GRAPH_REGION_UPDATE_GAP = 0.2   # Was: 0.1
CYCLE_TIME = 1.5               # Was: 1.3
```

---

## 📋 Recommended Settings for Different Scenarios

### **Scenario: Initial Setup / Testing**
```python
DEVELOPMENT_MODE = True
DEBUG = True
SHOW_PLOT = True
MIN_INTENSITY_PERCENT = 50
P_COUNT_THRESHOLD = 2000
```

### **Scenario: Production / Reliable Operation**
```python
DEVELOPMENT_MODE = False
DEBUG = False
SHOW_PLOT = False
MIN_INTENSITY_PERCENT = 60
P_COUNT_THRESHOLD = 3000
```

### **Scenario: Low Signal Conditions**
```python
MAX_INTEGRATION = 150
S_LED_INT = 200
DARK_NOISE_SCANS = 50
MIN_INTENSITY_PERCENT = 50
```

### **Scenario: High Performance / Fast Measurements**
```python
DARK_NOISE_SCANS = 20
REF_SCANS = 10
GRAPH_REGION_UPDATE_GAP = 0.15
CYCLE_TIME = 1.0
```

---

## 🔍 Where to Look During Troubleshooting

### **Calibration Issues:** Lines 41-79
- Integration time
- LED intensity
- Target intensity percentages
- Wavelength range
- Thresholds

### **Data Processing Issues:** Lines 51-60, 80-94
- Wavelength range (MIN/MAX_WAVELENGTH)
- Filtering settings (MED_FILT_WIN)
- Unit conversion (UNIT, UNIT_LIST)

### **Performance Issues:** Lines 49-50, 61, 97-98
- GRAPH_REGION_UPDATE_GAP
- CYCLE_TIME
- RECORDING_INTERVAL

### **Hardware Issues:** Lines 41-47
- VID/PID values
- BAUD_RATE
- LED_DELAY

### **Debug Flags:** Lines 92-99
- DEBUG, SHOW_PLOT, DEMO
- STATIC_PLOT, POP_OUT_SPEC

---

## ✅ Current Settings Validation

**Your current settings (lines 41-60):**
```python
PICO_PID = 0x000A           ✅ Correct
PICO_VID = 0x2E8A           ✅ Correct
CP210X_VID = 0x10C4         ✅ Correct
CP210X_PID = 0xEA60         ✅ Correct
BAUD_RATE = 115200          ✅ Correct

GRAPH_REGION_UPDATE_GAP = 0.1    ✅ Good for real-time
UNIT = "RU"                      ✅ Standard
MIN_WAVELENGTH = 560             ✅ Good range
MAX_WAVELENGTH = 720             ✅ Good range
POL_WAVELENGTH = 620             ✅ Mid-range
DARK_NOISE_SCANS = 30            ✅ Good for accuracy
REF_SCANS = 20                   ✅ Good balance
CYCLE_TIME = 1.3                 ✅ Standard
```

**All settings look good for standard operation!** ✅

---

## 💡 Pro Tips

1. **Make changes incrementally** - Change one setting at a time
2. **Document changes** - Comment why you changed a value
3. **Test after each change** - Run full calibration cycle
4. **Keep backups** - Save working settings before experimenting
5. **Use git** - Commit working configurations

---

**Last Updated:** October 10, 2025  
**Reference:** `settings/settings.py`  
**Related Docs:** 
- `SIMPLIFIED_ARCHITECTURE_README.md`
- `POLARIZER_CALIBRATION_SYSTEM.md`
- `WORKSPACE_TROUBLESHOOTING_GUIDE.md`
