# Ocean Optics NI-VISA Communication Disabled

## Summary
NI-VISA USB communication path has been explicitly disabled for Ocean Optics spectrometers in favor of the modern Ocean Direct API over WinUSB.

## Decision Rationale

### **NI-VISA USB Communication (❌ DISABLED - Legacy)**
- **Legacy approach** from older Ocean Optics software
- **Additional driver complexity** requiring NI-VISA runtime
- **Slower performance** due to VISA abstraction layer
- **Limited features** compared to native Ocean Direct API
- **Compatibility issues** with newer Ocean Optics firmware
- **Unnecessary overhead** for direct USB communication

### **Ocean Direct API over WinUSB (✅ ENABLED - Modern)**
- **Native Ocean Optics protocol** designed specifically for their hardware
- **Direct WinUSB communication** without VISA abstraction
- **Better performance** with lower latency
- **Full feature access** to all spectrometer capabilities
- **Official support** from Ocean Optics
- **Future-proof** architecture

## Implementation Changes

### **USB4000 HAL (`utils/hal/usb4000_hal.py`)**
```python
# Ocean Direct API communication (WinUSB)
COMMUNICATION_METHOD = "Ocean Direct API over WinUSB"
VISA_DISABLED = True  # NI-VISA communication explicitly disabled

def connect(self, device_id: Optional[int] = None, **connection_params: Any) -> bool:
    # Validate that we're not trying to use VISA
    if 'visa' in str(connection_params).lower():
        raise HALConnectionError(
            "NI-VISA communication is disabled for Ocean Optics devices. Use Ocean Direct API."
        )
```

### **USB4000 Test HAL (`utils/hal/usb4000_test_hal.py`)**
```python
COMMUNICATION_METHOD = "Simulated Ocean Direct API"
VISA_DISABLED = True  # NI-VISA communication explicitly disabled
```

### **Logging Updates**
- **Initialization:** `"Ocean Direct/WinUSB only - VISA disabled"`
- **Connection:** `"Connecting via Ocean Direct API (VISA disabled)"`
- **Validation:** `"NI-VISA communication disabled - using Ocean Direct API"`

## Hardware Detection Changes

### **Device Manager Location**
| Communication Method | Device Manager Location | Status |
|---------------------|-------------------------|---------|
| **Ocean Direct/WinUSB** | "Universal Serial Bus devices" | ✅ Enabled |
| **NI-VISA USB** | "VISA USB Devices" or similar | ❌ Disabled |

### **Driver Requirements**
| Communication Method | Required Drivers | Status |
|---------------------|------------------|---------|
| **Ocean Direct API** | WinUSB (built into Windows) | ✅ Enabled |
| **NI-VISA** | NI-VISA Runtime + drivers | ❌ Disabled |

## Code Examples

### **Correct Usage (Ocean Direct API):**
```python
from utils.hal import HALFactory

# This works - uses Ocean Direct API
spec = HALFactory.create_spectrometer("USB4000")
wavelengths, intensities = spec.capture_spectrum()
```

### **Disabled Usage (VISA - will raise error):**
```python
# This will raise HALConnectionError
spec = HALFactory.create_spectrometer("USB4000")
spec.connect(visa_resource="USB0::0x2457::0x1022::INSTR")  # ❌ Error!
```

## Error Handling

### **VISA Attempt Detection:**
```python
HALConnectionError: NI-VISA communication is disabled for Ocean Optics devices. Use Ocean Direct API.
Device Info: {
    "model": "USB4000",
    "supported_api": "Ocean Direct",
    "disabled_api": "NI-VISA"
}
```

## Migration Benefits

### **Performance Improvements:**
- **Faster device detection** via native WinUSB enumeration
- **Lower latency** spectrum acquisition
- **Reduced driver overhead** without VISA abstraction
- **Better integration** with Windows USB subsystem

### **Simplified Dependencies:**
- **No NI-VISA runtime** requirement
- **Smaller installation footprint**
- **Built-in WinUSB drivers** (no additional downloads)
- **Ocean Direct package only** (`pip install oceandirect`)

### **Enhanced Compatibility:**
- **Newer Ocean Optics firmware** fully supported
- **Windows 10/11 optimized** WinUSB implementation
- **USB 3.0/3.1 performance** benefits
- **Future spectrometer models** supported

## Future Spectrometer Support

### **Ocean Direct API Compatible (✅ Enabled):**
- USB4000, USB2000, QE65000
- Flame, Maya, Torus series
- NIR series, HR series
- Future Ocean Optics models

### **VISA-Only Legacy Models (❌ Not Supported):**
- Very old Ocean Optics models that only support VISA
- Third-party spectrometers requiring VISA
- Custom instruments using VISA protocol

**Note:** For VISA-only instruments, separate HAL implementations would be needed with explicit VISA support, but Ocean Optics devices should use Ocean Direct API.

## Testing Results

### **VISA Disabling Validation:**
```
✅ Ocean Direct API connection successful
✅ VISA connection attempts properly rejected
✅ Error messages provide clear guidance
✅ Device detection via WinUSB working
✅ Performance improved vs VISA approach
```

## Installation Notes

### **Required for Production:**
```bash
pip install oceandirect>=0.1.0
```

### **NOT Required (Legacy):**
```bash
# These are NOT needed for Ocean Optics devices:
# - NI-VISA Runtime
# - Additional USB drivers
# - VISA libraries or tools
```

## Date
**October 8, 2025** - NI-VISA communication explicitly disabled for Ocean Optics USB devices in favor of Ocean Direct API over WinUSB.