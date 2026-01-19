# P4PROPLUS Pump Control Quick Reference

## Detection
```python
from affilabs.utils.controller import PicoP4PRO

ctrl = PicoP4PRO()
ctrl.open()

# Check if device has pumps
if ctrl.has_pumps():
    print("P4PROPLUS detected")
    # firmware_id will be "P4PROPLUS"
else:
    print("Standard P4PRO")
    # firmware_id will be "P4PRO"
```

## Basic Operations

### Run Pumps
```python
# Run individual pump
ctrl.pump_run(1, 50)  # Pump 1 at 50 RPM
ctrl.pump_run(2, 100) # Pump 2 at 100 RPM

# Run both pumps at same speed
ctrl.pump_run(3, 75)  # Both pumps at 75 RPM
```

### Stop Pumps
```python
ctrl.pump_stop(1)  # Stop pump 1
ctrl.pump_stop(2)  # Stop pump 2
ctrl.pump_stop(3)  # Stop both pumps
```

### Emergency Stop All
```python
ctrl.stop_kinetic()  # Stops pumps + valves
```

## Monitoring

### Read Calibration
```python
cal = ctrl.pump_read_calibration()
if cal:
    pump1_pct, pump2_pct = cal
    print(f"Pump 1: {pump1_pct}% duty cycle")
    print(f"Pump 2: {pump2_pct}% duty cycle")
```

### Read Cycle Counts
```python
counts = ctrl.pump_read_cycle_counts()
if counts:
    count1, count2 = counts
    print(f"Pump 1: {count1} cycles")
    print(f"Pump 2: {count2} cycles")
```

## Calibration (Advanced)

### Flash New Calibration
**WARNING: Writes to EEPROM - use sparingly!**

```python
# Set Pump 1 to 60%, Pump 2 to 65%
ctrl.pump_flash_calibration(60, 65)
```

## Through HAL

```python
from affilabs.core.hardware_manager import HardwareManager

hm = HardwareManager()
hm.initialize()

# Access through HAL
hal = hm.ctrl

# Check pump support
if hal.has_internal_pumps:
    # Run pumps
    hal.pump_run(1, 50)
    
    # Read status
    cal = hal.pump_read_calibration()
    counts = hal.pump_read_cycle_counts()
    
    # Stop pumps
    hal.pump_stop(1)
```

## Speed Limits
- **Minimum**: 5 RPM
- **Maximum**: 220 RPM
- **Auto-clamping**: Values outside range are automatically adjusted

## Calibration Range
- **Default**: 100 (100% duty cycle)
- **Minimum**: 50 (50% duty cycle)
- **Maximum**: 150 (150% duty cycle)

## Example: Typical Flow Injection
```python
# Connect
ctrl = PicoP4PRO()
ctrl.open()

if not ctrl.has_pumps():
    print("Error: P4PROPLUS required")
    exit(1)

# Set flow rate
flow_rate_rpm = 30  # 30 RPM

# Start injection
ctrl.pump_run(1, flow_rate_rpm)

# Wait for injection to complete
import time
time.sleep(60)  # 60 seconds

# Stop pump
ctrl.pump_stop(1)

# Check usage
counts = ctrl.pump_read_cycle_counts()
if counts:
    print(f"Total pump 1 cycles: {counts[0]}")

ctrl.close()
```

## Firmware Commands (Low-Level)

Direct serial commands (if needed):
```python
# Via serial port (for testing/debugging only)
ser.write(b"pr1050\n")  # Run pump 1 at 50 RPM
ser.write(b"ps1\n")     # Stop pump 1
ser.write(b"pc\n")      # Read calibration
response = ser.read(2)   # Returns 2 bytes: pump1%, pump2%
```

## Notes
1. Call `id` command during initialization (handled automatically by `open()`)
2. Pump commands only work on P4PROPLUS firmware V2.3+
3. Regular P4PRO will log warnings if pump commands are attempted
4. Calibration flash has limited write cycles - avoid frequent writes
5. Always stop pumps before disconnecting: `ctrl.pump_stop(3)`
