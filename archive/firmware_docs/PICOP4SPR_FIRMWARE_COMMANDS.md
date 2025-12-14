# PicoP4SPR Firmware Command Reference

**CRITICAL REFERENCE - DO NOT DELETE**
**Date Created: October 8, 2025**
**Source: Extracted from utils/controller.py and main/main.py**

## Overview
This document contains the exact serial commands that the PicoP4SPR firmware understands. These commands were extracted from the working codebase and are the authoritative reference for hardware communication.

## Connection Settings
- **Port**: COM4 (typically)
- **Baud Rate**: 115200
- **Timeout**: 1 second
- **Line Ending**: Most commands use `\n`, system commands use `\r\n`

## LED Commands

### Basic LED Control
```
lx\n        - Turn off ALL LEDs (emergency shutdown)
la\n        - Turn on LED channel A only
lb\n        - Turn on LED channel B only
lc\n        - Turn on LED channel C only
ld\n        - Turn on LED channel D only
```

### LED Intensity Control (000-255)
```
baXXX\n     - Set LED A intensity (e.g., ba050\n for 50/255)
bbXXX\n     - Set LED B intensity (e.g., bb100\n for 100/255)
bcXXX\n     - Set LED C intensity (e.g., bc200\n for 200/255)
bdXXX\n     - Set LED D intensity (e.g., bd025\n for 25/255)
```

**Important**:
- Intensity values must be 3-digit zero-padded (ba001\n, not ba1\n)
- Range is 000-255
- After setting intensity, you must send the corresponding `lx\n` command to turn the LED on

## Polarizer/Servo Commands

### Polarizer Mode Control
```
ss\n        - Set polarizer to S mode (perpendicular)
sp\n        - Set polarizer to P mode (parallel)
```

### Servo Position Control
```
sr\n        - Get current servo positions (returns "sss,ppp" format)
svSSSPPP\n  - Set servo positions (e.g., sv010100\n = S=10°, P=100°)
```

**Important**:
- Servo positions must be 3-digit zero-padded
- Range is 000-180 degrees
- Format: svSSSPPP where SSS=S-servo, PPP=P-servo

## System Commands

### Device Information
```
id\r\n      - Get device ID (returns "P4SPR" if connected)
iv\r\n      - Get firmware version (returns version string)
it\n        - Get temperature reading (returns float value)
```

### Utility Commands
```
i0\n        - Set LED intensity to 0 (backup LED shutdown)
sf\n        - Flash/save settings to firmware
```

## Response Protocol
- **Success Response**: All commands return `"1"` for success
- **Error Response**: Commands return other values or no response for errors
- **Read Timeout**: 1 second maximum wait for response

## Usage Examples

### Sequential LED Test (A→B→C→D)
```python
import serial
import time

with serial.Serial("COM4", 115200, timeout=1) as ser:
    # Turn off all first
    ser.write(b"lx\n")
    time.sleep(0.1)

    # Set intensity and turn on each LED
    for ch in ['a', 'b', 'c', 'd']:
        ser.write(f"b{ch}050\n".encode())  # Set intensity to 50
        time.sleep(0.1)
        ser.write(f"l{ch}\n".encode())     # Turn on LED
        time.sleep(0.5)                    # Wait 500ms
        ser.write(b"lx\n")                 # Turn off
        time.sleep(0.1)
```

### Polarizer Movement Test
```python
import serial
import time

with serial.Serial("COM4", 115200, timeout=1) as ser:
    # Move to S mode
    ser.write(b"ss\n")
    time.sleep(1)

    # Move to P mode
    ser.write(b"sp\n")
    time.sleep(1)

    # Get current position
    ser.write(b"sr\n")
    response = ser.readline().decode().strip()
    print(f"Servo positions: {response}")  # Should be "sss,ppp"
```

## Emergency LED Shutdown
```python
import serial

try:
    with serial.Serial("COM4", 115200, timeout=1) as ser:
        ser.write(b"lx\n")  # Turn off all LEDs
        ser.write(b"i0\n")  # Set intensity to 0 as backup
except Exception as e:
    print(f"Emergency shutdown failed: {e}")
```

## Channel Mapping Reference
- **Channel A** = LED position 1 (leftmost)
- **Channel B** = LED position 2
- **Channel C** = LED position 3
- **Channel D** = LED position 4 (rightmost)

## Firmware Version History
- **V1.3**: Basic LED and servo control
- **V1.4**: Added pump correction support
- **V1.5**: Enhanced pump correction multiplier

## Common Mistakes to Avoid
1. ❌ Using wrong line endings (`\r\n` vs `\n`)
2. ❌ Not zero-padding intensity values (`b50` instead of `b050`)
3. ❌ Forgetting to turn on LED after setting intensity
4. ❌ Using uppercase channel letters (`LA` instead of `la`)
5. ❌ Not checking for "1" response after commands

## Files Containing These Commands
- `utils/controller.py` - Main implementation
- `main/main.py` - Emergency shutdown (lines 2479, 2484)
- This document - Permanent reference

---
**KEEP THIS FILE FOREVER - IT'S YOUR HARDWARE BIBLE!**