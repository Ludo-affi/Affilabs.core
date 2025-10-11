# Device Configuration Quick Reference

**Last Updated**: October 11, 2025
**Version**: 1.0

## Quick Start

### First Time Setup
```bash
python setup_device.py
```

### Modify Configuration
```bash
python -m utils.config_cli
```

---

## Optical Fiber Diameter

### Valid Options
- **100 µm**: Higher resolution, lower signal
- **200 µm**: Higher signal, most common (recommended)

### Set via CLI
```
Main Menu → 3. Modify Configuration → 2. Optical Fiber Diameter
```

### Set Programmatically
```python
from utils.device_configuration import DeviceConfiguration

config = DeviceConfiguration()
config.set_optical_fiber_diameter(200)  # or 100
config.save()
```

### Get Current Value
```python
diameter = config.get_optical_fiber_diameter()
print(f"Current fiber diameter: {diameter} µm")
```

---

## LED PCB Model

### Valid Options
- **luminus_cool_white**: Most common
- **osram_warm_white**: Alternative model

### Set via CLI
```
Main Menu → 3. Modify Configuration → 1. LED PCB Model
```

### Set Programmatically
```python
config.set_led_pcb_model('luminus_cool_white')
config.save()
```

---

## Timing Parameters

### Minimum Integration Time

**Range**: 1.0 to 1000.0 ms
**Default**: 5.0 ms

```python
# Get
min_time = config.get_min_integration_time()

# Set
config.set_min_integration_time(5.0)
config.save()
```

### LED Delays

**Range**: 0.0 to 1000.0 ms per channel
**Default**: 20 ms for all channels

```python
# Get
delays = config.get_led_delays()
# Returns: {'a': 20, 'b': 20, 'c': 20, 'd': 20}

# Set
config.set_led_delays({
    'a': 20,
    'b': 20,
    'c': 20,
    'd': 20
})
config.save()
```

---

## Frequency Limits

### Get Limits

```python
# 4-LED mode limits
limits_4 = config.get_frequency_limits(num_leds=4)
# Returns: {'max_hz': 5.0, 'recommended_hz': 2.0}

# 2-LED mode limits
limits_2 = config.get_frequency_limits(num_leds=2)
# Returns: {'max_hz': 10.0, 'recommended_hz': 5.0}
```

### Default Values

| Mode | Max Frequency | Recommended |
|------|---------------|-------------|
| 4-LED | 5.0 Hz | 2.0 Hz |
| 2-LED | 10.0 Hz | 5.0 Hz |

---

## Hardware Detection

### Auto-Detect Hardware

```bash
# Via CLI
Main Menu → 2. Hardware Detection

# Via setup wizard
python setup_device.py
```

### Programmatic Detection

```python
from utils.hardware_detection import HardwareDetector

detector = HardwareDetector()

# Detect all hardware
detected = detector.detect_all_hardware()

# Print results
detector.print_detected_hardware()

# Generate configuration
config_dict = detector.generate_device_config(
    led_pcb_model='luminus_cool_white',
    fiber_diameter_um=200
)
```

### Supported Devices

**Spectrometers**:
- Ocean Optics USB4000 (VID:PID 2457:101E)
- Ocean Optics FLAME-S (VID:PID 2457:1022)

**Controllers**:
- Raspberry Pi Pico (VID:PID 2E8A:000A)

---

## Configuration Validation

### Via CLI
```
Main Menu → 5. Validate Configuration
```

### Programmatically
```python
is_valid, errors = config.validate()

if not is_valid:
    print("Configuration errors:")
    for error in errors:
        print(f"  - {error}")
else:
    print("Configuration is valid!")
```

---

## Import/Export

### Export Configuration

```bash
# Via CLI
Main Menu → 4. Import/Export → 1. Export

# Programmatically
config.export_config('backup.json')
```

### Import Configuration

```bash
# Via CLI
Main Menu → 4. Import/Export → 2. Import

# Programmatically
config.import_config('backup.json')
```

---

## Calibration Status

### Check Status

```python
# Factory calibration
is_factory_cal = config.is_factory_calibrated()

# User calibration
is_user_cal = config.is_user_calibrated()

# Last calibration date
last_cal = config.get_last_calibration_date()
```

### Update Status

```python
# Mark factory calibrated
config.set_factory_calibrated(True)

# Mark user calibrated
from datetime import datetime
config.set_user_calibrated(True, datetime.now())

config.save()
```

---

## Maintenance Tracking

### Get Metrics

```python
# Total measurement cycles
cycles = config.get_total_cycles()

# LED on-time hours
hours = config.get_led_hours()
```

### Update Metrics

```python
# Increment cycle count
config.increment_cycle_count()

# Add LED hours
config.add_led_hours(0.5)  # 0.5 hours

config.save()
```

---

## Reset to Defaults

### Via CLI
```
Main Menu → 6. Reset to Defaults
Type 'RESET' to confirm
```

### Programmatically
```python
config.reset_to_defaults()
config.save()
```

---

## Configuration File Location

**Default Path**: `config/device_config.json`

### Custom Location

```python
from pathlib import Path

config = DeviceConfiguration(
    config_file=Path('custom/path/config.json')
)
```

---

## Error Handling

### Common Errors

**Invalid Fiber Diameter**:
```python
try:
    config.set_optical_fiber_diameter(150)  # Invalid!
except ValueError as e:
    print(f"Error: {e}")
    # Error: Optical fiber diameter must be 100 or 200 micrometers
```

**Invalid LED PCB Model**:
```python
try:
    config.set_led_pcb_model('invalid_model')
except ValueError as e:
    print(f"Error: {e}")
    # Error: LED PCB model must be one of: ...
```

**Invalid Integration Time**:
```python
try:
    config.set_min_integration_time(2000)  # Out of range!
except ValueError as e:
    print(f"Error: {e}")
    # Error: Minimum integration time must be between 1.0 and 1000.0 ms
```

---

## Integration Examples

### With AdaptiveBatchProcessor

```python
from utils.adaptive_batch_processor import AdaptiveBatchProcessor
from utils.device_configuration import DeviceConfiguration

# Load configuration
config = DeviceConfiguration()

# Create processor with config
processor = AdaptiveBatchProcessor(device_config=config)

# Processor automatically uses timing and frequency settings
batch_config = processor.calculate_batch_config(
    frequency_hz=2.0,
    num_leds=4
)
```

### With Main Application

```python
from utils.device_configuration import DeviceConfiguration

# Load and validate config
config = DeviceConfiguration()
is_valid, errors = config.validate()

if not is_valid:
    raise RuntimeError(f"Invalid configuration: {errors}")

# Use throughout application
fiber_diameter = config.get_optical_fiber_diameter()
min_integration = config.get_min_integration_time()
frequency_limits = config.get_frequency_limits(num_leds=4)
```

---

## CLI Menu Structure

```
Main Menu
├── 1. View Current Configuration
├── 2. Hardware Detection
├── 3. Modify Configuration
│   ├── 1. LED PCB Model
│   ├── 2. Optical Fiber Diameter
│   ├── 3. Spectrometer Serial Number
│   ├── 4. Minimum Integration Time
│   └── 5. LED Delays
├── 4. Import/Export Configuration
│   ├── 1. Export Configuration
│   └── 2. Import Configuration
├── 5. Validate Configuration
├── 6. Reset to Defaults
└── 0. Exit
```

---

## Troubleshooting

### Configuration Not Saving

```python
# Check file permissions
config_file = config.config_file
print(f"Config file: {config_file}")
print(f"Exists: {config_file.exists()}")
print(f"Writable: {os.access(config_file, os.W_OK)}")
```

### Hardware Not Detected

1. Ensure devices are connected via USB
2. Check device drivers are installed
3. Try different USB port
4. Verify VID:PID in Device Manager (Windows)

```python
# List all serial ports
import serial.tools.list_ports
ports = serial.tools.list_ports.comports()
for port in ports:
    print(f"{port.device}: {port.description}")
    print(f"  VID:PID = {port.vid:04X}:{port.pid:04X}")
```

### Configuration Validation Failing

```python
# Get detailed error list
is_valid, errors = config.validate()
for error in errors:
    print(f"Error: {error}")
```

---

## API Reference

### DeviceConfiguration Methods

| Method | Description |
|--------|-------------|
| `set_optical_fiber_diameter(um)` | Set fiber diameter (100 or 200) |
| `get_optical_fiber_diameter()` | Get current fiber diameter |
| `set_led_pcb_model(model)` | Set LED PCB model |
| `get_led_pcb_model()` | Get current LED PCB model |
| `set_spectrometer_serial(serial)` | Set spectrometer serial number |
| `get_spectrometer_serial()` | Get spectrometer serial number |
| `set_min_integration_time(ms)` | Set minimum integration time |
| `get_min_integration_time()` | Get minimum integration time |
| `set_led_delays(delays)` | Set LED delays for all channels |
| `get_led_delays()` | Get LED delays |
| `get_frequency_limits(num_leds)` | Get frequency limits for mode |
| `validate()` | Validate configuration |
| `save()` | Save to file |
| `import_config(path)` | Import from file |
| `export_config(path)` | Export to file |
| `reset_to_defaults()` | Reset all settings |

### HardwareDetector Methods

| Method | Description |
|--------|-------------|
| `scan_ports()` | List all serial ports |
| `detect_spectrometer()` | Find spectrometer |
| `detect_controller()` | Find controller |
| `detect_all_hardware()` | Scan all devices |
| `generate_device_config()` | Create config from hardware |
| `print_detected_hardware()` | Display detection results |

---

## Support

For issues or questions:
1. Check this guide
2. Review `PHASE_2_COMPLETION.md`
3. Run validation: `python -m utils.config_cli` → Menu 5
4. Check logs in `logs/` directory

---

*End of Quick Reference*
