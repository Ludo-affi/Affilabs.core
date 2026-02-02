# Hardware Communication Layer Documentation

**Last Updated**: February 2, 2026
**Author**: AffiLabs Team
**Related Docs**: [Device Database](DEVICE_DATABASE_REGISTRATION.md), [Pump & Valve System](PUMP_VALVE_SYSTEM.md)

---

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Serial Communication Protocol](#serial-communication-protocol)
4. [Hardware Abstraction Layer (HAL)](#hardware-abstraction-layer-hal)
5. [Device Types](#device-types)
6. [Connection Management](#connection-management)
7. [Command & Response Patterns](#command--response-patterns)
8. [Error Handling & Recovery](#error-handling--recovery)
9. [Threading & Concurrency](#threading--concurrency)
10. [API Reference](#api-reference)
11. [Troubleshooting](#troubleshooting)

---

## Overview

### Purpose

The Hardware Communication Layer provides a unified interface for all hardware devices in the ezControl system:

- **SPR Controllers** (PicoP4PRO, PicoP4SPR, PicoEZSPR)
- **Kinetic Controllers** (PicoKNX2, KineticController)
- **Spectrometers** (Ocean Optics USB4000/Flame-T, Phase Photonics ST Series)
- **Pumps** (AffiPump dual syringe, internal KNX pumps)

### Key Features

- **Unified HAL**: Consistent API across all hardware types
- **Automatic Discovery**: Scans USB ports to detect connected devices
- **Connection Resilience**: Auto-reconnect, timeout recovery, port caching
- **Thread-Safe**: Lock protection for concurrent serial access
- **Device-Agnostic**: Applications code to HAL, not specific hardware

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYER                       │
│  (main.py, affilabs_core_ui.py, managers/)                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│               HARDWARE MANAGER (Coordinator)                │
│  ├─ Device Scanning & Discovery                             │
│  ├─ Connection Lifecycle Management                        │
│  ├─ Hardware Status Signals                                │
│  └─ HAL Instance Factory                                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
    ┌──────────────────┼──────────────────┬─────────────────┐
    │                  │                  │                 │
┌───▼────┐      ┌──────▼──────┐   ┌──────▼──────┐   ┌─────▼──────┐
│ Ctrl   │      │ Detector    │   │ Pump        │   │ Kinetic    │
│ HAL    │      │ HAL         │   │ HAL         │   │ Controller │
└───┬────┘      └──────┬──────┘   └──────┬──────┘   └─────┬──────┘
    │                  │                  │                 │
┌───▼─────────────────────────────────────────────────────────────┐
│            SERIAL COMMUNICATION LAYER                           │
│  ├─ PySerial (USB Virtual COM Ports)                            │
│  ├─ PyUSB (Direct USB for Ocean Optics)                         │
│  ├─ Command Timing (minimum 50ms intervals)                     │
│  ├─ Buffer Management (flush input/output)                      │
│  └─ Timeout Handling (0.1-2.0 seconds)                          │
└─────────────────────────────────────────────────────────────────┘
    │                  │                  │                 │
┌───▼────┐      ┌──────▼──────┐   ┌──────▼──────┐   ┌─────▼──────┐
│ Pico   │      │ Ocean Optics│   │ FTDI Serial │   │ CP210x     │
│ USB    │      │ USB Driver  │   │ (Cavro Pump)│   │ USB-Serial │
└────────┘      └─────────────┘   └─────────────┘   └────────────┘
```

---

## Serial Communication Protocol

### Communication Fundamentals

#### Baud Rates

| Device Type | Baud Rate | Data Bits | Parity | Stop Bits |
|-------------|-----------|-----------|--------|-----------|
| **Pico Controllers** | 115200 | 8 | None | 1 |
| **Arduino Controllers** | 115200 | 8 | None | 1 |
| **AffiPump (Cavro)** | 38400 | 8 | None | 1 |
| **KNX Controllers** | 9600 | 8 | None | 1 |

#### Timeout Strategy

```python
# Connection establishment: Longer timeout for initial handshake
CONNECTION_TIMEOUT = 2.0  # seconds

# Command execution: Short timeout for fast detection of dead devices
COMMAND_TIMEOUT = 0.1  # seconds (controller responses < 50ms)

# Write timeout: Prevent blocking on buffer full
WRITE_TIMEOUT = 2.0  # seconds
```

---

### USB Device Identification

**Controllers** (Pico-based):
```python
VID = 0x2E8A  # Raspberry Pi
PID = 0x000A  # Pico
```

**Pumps** (FTDI adapter):
```python
VID = 0x0403  # FTDI
PID = 0x6001  # FT232R USB-Serial
```

**Spectrometers** (Ocean Optics):
- USB4000: Detected via SeaBreeze library
- Flame-T: Detected via SeaBreeze library
- Phase Photonics: Custom USB integration

---

## Hardware Abstraction Layer (HAL)

### Controller HAL

**File**: `affilabs/utils/hal/controller_hal.py`

Unified interface for all controller types:

```python
class ControllerHAL(Protocol):
    """Unified controller interface."""

    # LED Control
    def set_led_intensity(ch: str, intensity: int) -> bool
    def set_batch_intensities(a: int, b: int, c: int, d: int) -> bool

    # Polarizer Control
    def set_mode(mode: str) -> bool  # 's' or 'p'
    def get_mode() -> str

    # Servo Control (P4PRO only)
    def set_servo_position(servo_id: str, angle: int) -> bool
    def get_servo_position(servo_id: str) -> int | None

    # Valve Control (KNX, P4PRO with pumps)
    def knx_six(ch: int, state: int, timeout_seconds: int | None) -> bool
    def knx_six_both(state: int, timeout_seconds: int | None) -> bool
    def knx_three(ch: int, state: int) -> bool
    def knx_three_both(state: int) -> bool

    # Pump Control (Internal pumps on KNX)
    def knx_start(rate: int, ch: int) -> bool
    def knx_stop(ch: int) -> bool

    # EEPROM Configuration
    def read_config_from_eeprom() -> dict
    def write_config_to_eeprom(config: dict) -> bool

    # Connection
    def open() -> bool
    def close() -> None
```

**Adapters**:
- `PicoP4PROAdapter`: P4PRO with polarizer servos, 6-port/3-way valves
- `PicoP4SPRAdapter`: P4SPR with polarizer servos
- `PicoEZSPRAdapter`: EZSPR/AFFINITE (no servos)

---

### Detector HAL

**File**: `affilabs/utils/hal/detector_hal.py`

```python
class DetectorHAL(Protocol):
    """Unified spectrometer interface."""

    def set_integration_time(time_ms: int) -> bool
    def get_spectrum() -> np.ndarray
    def get_wavelengths() -> np.ndarray
    def get_serial() -> str
    def close() -> None
```

**Adapters**:
- `OceanOpticsAdapter`: USB4000, Flame-T via SeaBreeze
- `PhasePhotonicsAdapter`: ST Series spectrometers

---

### Pump HAL

**File**: `affilabs/utils/hal/pump_hal.py`

```python
class PumpHAL(Protocol):
    """Unified pump interface."""

    # Low-level
    def send_command(address: int, command: bytes) -> bytes
    def is_available() -> bool

    # High-level
    def initialize_pumps() -> bool
    def aspirate(pump_address: int, volume_ul: float, rate_ul_min: float) -> bool
    def dispense(pump_address: int, volume_ul: float, rate_ul_min: float) -> bool
    def set_valve_position(pump_address: int, port: int) -> bool
    def get_syringe_position(pump_address: int) -> int | None
    def wait_until_idle(pump_address: int, timeout_s: float) -> bool

    # Connection
    def close() -> None
```

**Adapters**:
- `AffipumpAdapter`: Tecan Cavro Centris dual syringe pumps

---

## Device Types

### 1. Pico Controllers (P4PRO, P4SPR, EZSPR)

**Hardware**: Raspberry Pi Pico microcontroller, USB CDC serial

**Command Format**: ASCII text, newline-terminated

**Example Commands**:
```python
# LED control (batch command)
ctrl.send_command("L1,2,3,4\n")  # Set A=1, B=2, C=3, D=4 (fast)

# Polarizer mode
ctrl.send_command("s\n")  # S-pol mode
ctrl.send_command("p\n")  # P-pol mode

# Servo positioning (P4PRO only)
ctrl.send_command("S100\n")  # S-pol servo to 100°
ctrl.send_command("P110\n")  # P-pol servo to 110°

# Valve control (6-port inject)
ctrl.send_command("v611\n")  # Channel 1 inject

# Firmware version
response = ctrl.send_command("V\n")  # Returns "P4PRO-v2.3.1"
```

**Response Format**:
- Success: `b'1'`, `b'\x01'`, `b'b'`, or empty `b''`
- Error: `b'0'` or `b'\x00'`

---

### 2. Ocean Optics Spectrometers

**Communication**: PyUSB via SeaBreeze library (no serial port)

**Integration Time**: 1-65,535 milliseconds

**Acquisition**:
```python
import seabreeze.spectrometers as sb

devices = sb.list_devices()
spec = sb.Spectrometer(devices[0])

spec.integration_time_micros(100000)  # 100ms
wavelengths = spec.wavelengths()
intensities = spec.intensities()

spec.close()
```

**Serial Number Extraction**:
```python
serial_number = spec.serial_number
# Example: "FLMT09788" (Flame-T) or "USB4C00123" (USB4000)
```

---

### 3. AffiPump (Dual Syringe Pumps)

**Hardware**: 2x Tecan Cavro Centris pumps connected via FTDI USB-serial

**Communication**: Custom binary protocol, 38400 baud

**Command Structure**:
```
Format: /<ADDRESS><COMMAND><PARAMETERS>\r
Example: /1A1000R    # Pump 1, Absolute move to 1000 steps
```

**Common Commands**:

| Command | Description | Example |
|---------|-------------|---------|
| `ZR` | Initialize pump (home plunger) | `/1ZR` |
| `A<pos>R` | Absolute move to position | `/1A1000R` |
| `P<vol>R` | Pick up (aspirate) volume | `/1P500R` |
| `D<vol>R` | Dispense volume | `/1D500R` |
| `I<port>R` | Set valve to input port | `/1IIR` |
| `O<port>R` | Set valve to output port | `/1OOR` |
| `?` | Query status | `/1?` |
| `T` | Terminate (emergency stop) | `/1TR` |

**Response Parsing**:
```python
response = pump.send_command("/1?")  # Query pump 1 status

status_byte = response[0]
STATUS_MAP = {
    b'/': {'busy': False, 'error': None},              # Idle
    b'`': {'busy': True, 'error': None},               # Busy
    b'?': {'busy': False, 'error': 'Initialization'},  # Not initialized
    b'@': {'busy': True, 'error': 'Initialization'},
    b'o': {'busy': False, 'error': 'Buffer Overflow'},
}
```

---

### 4. Kinetic Controllers (Internal Pumps)

**Hardware**: Arduino or Pico with stepper motor drivers

**Valve Commands**:
```python
# 6-port valve (load/inject)
ctrl.knx_six(state=1, ch=1)  # Channel 1 inject
ctrl.knx_six(state=0, ch=1)  # Channel 1 load

# 3-way valve (waste/load)
ctrl.knx_three(state=1, ch=1)  # Channel 1 to load
ctrl.knx_three(state=0, ch=1)  # Channel 1 to waste
```

**Pump Commands**:
```python
# Start internal pump
rate = 50  # µL/min
ctrl.knx_start(rate=rate, ch=1)

# Stop pump
ctrl.knx_stop(ch=1)
```

---

## Connection Management

### HardwareManager Workflow

**File**: `affilabs/core/hardware_manager.py`

```
┌─────────────────────────────────────────────────────────────┐
│ 1. HARDWARE SCANNING (Priority Order)                      │
├─────────────────────────────────────────────────────────────┤
│    a) Controller (PicoP4PRO → PicoP4SPR → PicoEZSPR)       │
│       └─ Stop at first found                               │
│    b) Detector (USB4000/Ocean Optics → Phase Photonics)    │
│    c) Pump (AffiPump first, then KNX if no AffiPump)      │
│    d) Kinetic (Only if no AffiPump)                        │
└─────────────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. DEVICE IDENTIFICATION                                    │
├─────────────────────────────────────────────────────────────┤
│    - Extract serial numbers                                │
│    - Query firmware versions                               │
│    - Read EEPROM configuration (if supported)              │
└─────────────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. DATABASE LOOKUP                                          │
├─────────────────────────────────────────────────────────────┤
│    Check: affilabs/config/devices/{SERIAL}/device_config.json│
│    If exists: Load device profile                          │
│    If missing: Create registration dialog                  │
└─────────────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. HAL WRAPPING                                             │
├─────────────────────────────────────────────────────────────┤
│    Wrap hardware instances with HAL adapters               │
│    Store both HAL (ctrl) and raw (_ctrl_raw) references   │
└─────────────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. SIGNAL EMISSION                                          │
├─────────────────────────────────────────────────────────────┤
│    hardware_connected.emit({                               │
│        'ctrl_type': 'PicoP4PRO',                            │
│        'pump_connected': True,                             │
│        'spectrometer': 'USB4000'                           │
│    })                                                      │
└─────────────────────────────────────────────────────────────┘
```

### Connection Resilience

**Port Caching**:
```python
class HardwareManager:
    def __init__(self):
        # Cache successful connection details
        self._ctrl_port = None      # COM port for controller
        self._ctrl_type = None      # Controller type that worked
        self._spec_serial = None    # Spectrometer serial that worked
        self._connection_lock = threading.RLock()
```

**Auto-Reconnect**:
```python
def reconnect_controller(self):
    """Attempt to reconnect using cached port."""
    if not self._ctrl_port or not self._ctrl_type:
        logger.warning("No cached connection info - run full scan")
        return False

    try:
        # Try exact port first
        ctrl_class = _get_controller_classes()[self._ctrl_type]
        ctrl = ctrl_class()
        if ctrl.open(port=self._ctrl_port):
            self.ctrl = create_controller_hal(ctrl)
            self._ctrl_raw = ctrl
            logger.info(f"✓ Reconnected to {self._ctrl_type} on {self._ctrl_port}")
            return True
    except Exception as e:
        logger.error(f"Reconnection failed: {e}")

    return False
```

---

## Command & Response Patterns

### Command Timing

**Critical Rule**: Minimum 50ms between commands

```python
class AffipumpController:
    def __init__(self):
        self._serial_lock = threading.Lock()
        self._min_command_interval = 0.05  # 50ms
        self._last_command_time = 0.0

    def send_command(self, cmd):
        with self._serial_lock:
            # Enforce minimum interval
            elapsed = time.time() - self._last_command_time
            if elapsed < self._min_command_interval:
                time.sleep(self._min_command_interval - elapsed)

            self.ser.write((cmd + '\r').encode())
            self._last_command_time = time.time()

            # Read response
            response = self.ser.read(256)
            return response
```

**Why 50ms?** Hardware UART buffers can overflow if commands arrive too quickly, causing dropped responses and communication errors.

---

### Command Queueing

For concurrent operations (e.g., UI + automation):

```python
import queue

class CommandQueue:
    def __init__(self, controller):
        self.controller = controller
        self.queue = queue.Queue()
        self.worker = threading.Thread(target=self._process_queue, daemon=True)
        self.worker.start()

    def send(self, command):
        """Thread-safe command submission."""
        future = queue.Queue()
        self.queue.put((command, future))
        return future.get(timeout=5.0)  # Block until response

    def _process_queue(self):
        """Worker thread processes commands sequentially."""
        while True:
            command, result_queue = self.queue.get()
            try:
                response = self.controller.send_command(command)
                result_queue.put(response)
            except Exception as e:
                result_queue.put(e)
```

---

### Response Validation

```python
def send_command_with_retry(ctrl, command, expected_response, max_retries=3):
    """Send command with validation and retry logic."""
    for attempt in range(max_retries):
        try:
            ctrl.ser.reset_input_buffer()  # Clear stale data
            response = ctrl.send_command(command)

            if response == expected_response:
                return True

            logger.warning(f"Unexpected response: {response!r} (expected {expected_response!r})")

        except serial.SerialTimeoutException:
            logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}")
            time.sleep(0.5)  # Wait before retry

    return False
```

---

## Error Handling & Recovery

### Common Errors

#### 1. Serial Timeout

**Cause**: Device not responding within timeout period

**Recovery**:
```python
try:
    response = ctrl.send_command("V\n")
except serial.SerialTimeoutException:
    logger.error("Controller not responding")

    # Attempt recovery
    ctrl.ser.reset_input_buffer()
    ctrl.ser.reset_output_buffer()
    time.sleep(0.5)

    # Retry once
    response = ctrl.send_command("V\n")
```

#### 2. Port Disconnected

**Cause**: USB cable unplugged, device powered off

**Detection**:
```python
if not ctrl.ser or not ctrl.ser.is_open:
    logger.error("Serial port closed")

    # Trigger reconnection
    hardware_mgr.reconnect_controller()
```

#### 3. Buffer Overflow

**Cause**: Commands sent too quickly

**Prevention**:
```python
# Always enforce minimum command interval
# Always flush buffers before sending
ctrl.ser.reset_input_buffer()
ctrl.ser.write(command.encode())
```

---

### Emergency Recovery

**Pump Emergency Stop**:
```python
def emergency_stop_pumps(pump):
    """Terminate all pump operations immediately."""
    pump.send_command("/1TR")  # Terminate pump 1
    pump.send_command("/2TR")  # Terminate pump 2
    logger.warning("⚠️ Pumps terminated")
```

**Controller Reset**:
```python
def reset_controller(ctrl):
    """Reset controller to safe state."""
    ctrl.turn_off_channels()  # All LEDs off
    ctrl.set_mode("s")        # S-pol mode
    ctrl.close()
    time.sleep(1.0)
    ctrl.open()
```

---

## Threading & Concurrency

### Thread Safety

**Serial Lock Pattern**:
```python
class ThreadSafeController:
    def __init__(self):
        self._lock = threading.Lock()
        self._ser = None

    def send_command(self, cmd):
        with self._lock:
            self._ser.write(cmd.encode())
            return self._ser.read(256)
```

**Why Locks?** Prevents race conditions when:
- Acquisition thread reads detector
- UI thread changes LED intensity
- Automation sends valve commands

---

### Acquisition Thread

**Pattern**: Dedicated non-daemon thread for hardware polling

```python
def _acquisition_worker(self):
    """Background thread for continuous data acquisition."""
    try:
        while not self._stop_flag.is_set():
            # Acquire spectrum (thread-safe via HAL locks)
            spectrum = self.detector.get_spectrum()

            # Queue for processing (lock-free queue)
            self._data_queue.put({
                'timestamp': time.time(),
                'spectrum': spectrum
            })

            time.sleep(1.0)  # 1 Hz acquisition
    finally:
        logger.info("Acquisition worker stopped")
```

---

## API Reference

### HardwareManager

**Connection**:
```python
from affilabs.core.hardware_manager import HardwareManager

hw_mgr = HardwareManager()

# Connect to hardware (async in background thread)
hw_mgr.scan_and_connect()

# Check connection status
status = hw_mgr.get_hardware_status()
# Returns: {
#     'controller': 'PicoP4PRO',
#     'spectrometer': 'USB4000',
#     'pump': 'AffiPump',
#     'connected': True
# }
```

**Signals**:
```python
# Listen for connection events
hw_mgr.hardware_connected.connect(on_connected)
hw_mgr.hardware_disconnected.connect(on_disconnected)
hw_mgr.error_occurred.connect(on_error)

def on_connected(status_dict):
    print(f"Connected: {status_dict}")

def on_disconnected():
    print("Hardware disconnected")
```

---

### Controller HAL

**LED Control**:
```python
# Single channel
ctrl.set_led_intensity('a', 50)  # Channel A to 50/255

# Batch (15x faster)
ctrl.set_batch_intensities(a=50, b=60, c=70, d=80)
```

**Polarizer Control**:
```python
# Mode switching
ctrl.set_mode('s')  # S-polarization
ctrl.set_mode('p')  # P-polarization

# Get current mode
mode = ctrl.get_mode()  # Returns 's' or 'p'
```

**Valve Control**:
```python
# 6-port valve (with safety timeout)
ctrl.knx_six(ch=1, state=1, timeout_seconds=300)  # Inject with 5-min timeout
ctrl.knx_six(ch=1, state=0)  # Load (no timeout for automated sequences)

# Both channels simultaneously
ctrl.knx_six_both(state=1, timeout_seconds=300)
```

---

### Detector HAL

**Spectrum Acquisition**:
```python
# Set integration time
detector.set_integration_time(100)  # 100ms

# Get spectrum
wavelengths = detector.get_wavelengths()  # [200.0, 200.5, ..., 1100.0]
intensities = detector.get_spectrum()     # [1024, 1256, ..., 45678]

# Device info
serial = detector.get_serial()  # "FLMT09788"
```

---

### Pump HAL

**Priming**:
```python
pump.initialize_pumps()  # Home both plungers

# Aspirate 500µL at 1000µL/min
pump.aspirate(pump_address=1, volume_ul=500, rate_ul_min=1000)

# Wait for completion
pump.wait_until_idle(pump_address=1, timeout_s=60)
```

**Injection**:
```python
# Set valve to inject port
pump.set_valve_position(pump_address=1, port='I')

# Dispense 100µL at 100µL/min
pump.dispense(pump_address=1, volume_ul=100, rate_ul_min=100)
```

---

## Troubleshooting

### No Devices Found

**Symptoms**: `scan_and_connect()` finds no hardware

**Checks**:
1. USB cables connected?
2. Device powered on?
3. Correct drivers installed?

**Windows Driver Check**:
```powershell
# Check COM ports
Get-WmiObject Win32_SerialPort | Select-Object Name, DeviceID, Description

# Expected:
# Name                      DeviceID  Description
# USB Serial Device (COM3)  COM3      USB-SERIAL CH340
# USB Serial Device (COM8)  COM8      USB Serial Device
```

**Test Script**:
```python
import serial.tools.list_ports

ports = list(serial.tools.list_ports.comports())
for port in ports:
    print(f"{port.device}: {port.description}")
    print(f"  VID={port.vid:04x} PID={port.pid:04x}")
```

---

### Communication Timeout

**Symptoms**: Commands never return, serial timeout exceptions

**Causes**:
1. Baud rate mismatch
2. Device busy (pump running)
3. Buffer overflow (commands too fast)

**Diagnostics**:
```python
# Verify port settings
print(f"Baud: {ser.baudrate}")
print(f"Timeout: {ser.timeout}")
print(f"Write Timeout: {ser.write_timeout}")

# Test with simple command
ser.reset_input_buffer()
ser.write(b"V\n")
response = ser.read(20)
print(f"Response: {response!r}")
```

---

### Intermittent Errors

**Symptoms**: Commands work sometimes, fail randomly

**Common Cause**: No serial lock (concurrent access)

**Fix**:
```python
# Before (BAD):
ser.write(b"cmd1\n")
response1 = ser.read(10)

# Another thread writes simultaneously → corruption!

# After (GOOD):
with serial_lock:
    ser.write(b"cmd1\n")
    response1 = ser.read(10)
```

---

### Pump Blockage Detection

**Symptoms**: Pump takes much longer than expected

**Detection**:
```python
start = time.time()
pump.dispense(pump_address=1, volume_ul=100, rate_ul_min=100)
elapsed = time.time() - start

expected = (100 / 100) * 60  # volume / rate * 60 = 60 seconds
if elapsed > expected * 1.5:
    logger.error(f"Possible blockage: {elapsed:.1f}s vs {expected:.1f}s expected")
```

---

### EEPROM Corruption

**Symptoms**: Invalid values in device configuration

**Check**:
```python
config = ctrl.read_config_from_eeprom()

if config is None or config.get('led_pcb_model') not in ['luminus_cool_white', 'osram_warm_white']:
    logger.error("EEPROM corrupted or uninitialized")

    # Write default config
    default_config = {
        'led_pcb_model': 'luminus_cool_white',
        'controller_type': 'pico_p4pro',
        'fiber_diameter_um': 200,
        'polarizer_type': 'barrel',
        'servo_s_position': 90,
        'servo_p_position': 110,
        'led_intensity_a': 50,
        'led_intensity_b': 50,
        'led_intensity_c': 50,
        'led_intensity_d': 50,
        'integration_time_ms': 100,
        'num_scans': 1
    }
    ctrl.write_config_to_eeprom(default_config)
```

---

## Performance Optimization

### Batch Commands

**Problem**: Sending 4 separate LED commands takes 200ms (4 × 50ms minimum interval)

**Solution**: Batch command sends all 4 in one transaction (50ms total)

```python
# Before (SLOW): 200ms
ctrl.set_led_intensity('a', 50)  # 50ms
ctrl.set_led_intensity('b', 60)  # 50ms
ctrl.set_led_intensity('c', 70)  # 50ms
ctrl.set_led_intensity('d', 80)  # 50ms

# After (FAST): 50ms
ctrl.set_batch_intensities(a=50, b=60, c=70, d=80)
```

**Result**: 4x speedup, critical for live data acquisition

---

### Buffer Flushing

**Always flush before critical commands**:

```python
# Clear stale data from previous operations
ser.reset_input_buffer()
ser.reset_output_buffer()

# Send command
ser.write(b"CRITICAL_CMD\n")
response = ser.read(256)
```

---

### Connection Caching

**Avoid repeated device scans**:

```python
# First connection: Full scan (slow)
hw_mgr.scan_and_connect()  # ~5 seconds

# Disconnection detected → use cached port info
hw_mgr.reconnect_controller()  # ~500ms (10x faster)
```

---

## Debugging Tools

### Serial Monitor Script

**File**: `emergency-pump-reset.py`

```python
import serial
import time

def monitor_serial(port='COM8', baudrate=38400):
    """Monitor all serial traffic."""
    ser = serial.Serial(port, baudrate, timeout=1)

    print(f"Monitoring {port} at {baudrate} baud...")
    print("Press Ctrl+C to stop\n")

    while True:
        # Echo all incoming data
        if ser.in_waiting:
            data = ser.read(ser.in_waiting)
            print(f"← {data!r}")

        time.sleep(0.1)

if __name__ == "__main__":
    monitor_serial()
```

---

### Hardware Diagnostics

**File**: `diagnose_usb.py`

Lists all USB devices with VID/PID:

```python
import usb.core

devices = usb.core.find(find_all=True)
for dev in devices:
    print(f"VID={dev.idVendor:04x} PID={dev.idProduct:04x}")
    print(f"  Manufacturer: {usb.util.get_string(dev, dev.iManufacturer)}")
    print(f"  Product: {usb.util.get_string(dev, dev.iProduct)}")
```

---

### Controller Info Script

```python
def get_controller_info(ctrl):
    """Query all controller properties."""
    info = {}

    try:
        # Firmware version
        version = ctrl.send_command("V\n")
        info['firmware'] = version.decode().strip()

        # Current mode
        mode = ctrl.get_mode()
        info['polarizer_mode'] = mode

        # EEPROM config
        config = ctrl.read_config_from_eeprom()
        info['eeprom_config'] = config

    except Exception as e:
        info['error'] = str(e)

    return info
```

---

## Best Practices

### 1. Always Use HAL

❌ **BAD** (couples code to specific hardware):
```python
from affilabs.utils.controller import PicoP4PRO

ctrl = PicoP4PRO()
ctrl.open()
ctrl.send_command("L50,60,70,80\n")  # Direct serial command
```

✅ **GOOD** (works with any controller):
```python
ctrl = hardware_mgr.ctrl  # HAL instance
ctrl.set_batch_intensities(a=50, b=60, c=70, d=80)
```

---

### 2. Handle Disconnections Gracefully

```python
def acquire_spectrum():
    try:
        spectrum = detector.get_spectrum()
        return spectrum
    except Exception as e:
        logger.error(f"Acquisition failed: {e}")

        # Notify user
        ui.show_error("Detector disconnected - check USB cable")

        # Attempt reconnection
        hardware_mgr.reconnect_detector()
        return None
```

---

### 3. Use Timeouts Appropriately

```python
# Connection: Long timeout
ser = serial.Serial(port, baudrate, timeout=2.0)

# Commands: Short timeout (fail fast)
ser.timeout = 0.1
response = ser.read(256)

if not response:
    # Device not responding → reconnect
    reconnect()
```

---

### 4. Enforce Minimum Command Intervals

```python
# Store last command time
self._last_cmd_time = 0.0

def send_command(self, cmd):
    # Wait if needed
    elapsed = time.time() - self._last_cmd_time
    if elapsed < 0.05:  # 50ms minimum
        time.sleep(0.05 - elapsed)

    # Send command
    self.ser.write(cmd.encode())
    self._last_cmd_time = time.time()

    return self.ser.read(256)
```

---

## Related Documentation

- [Device Database Registration](DEVICE_DATABASE_REGISTRATION.md) - Device configuration and EEPROM
- [Pump & Valve System](PUMP_VALVE_SYSTEM.md) - AffiPump and KNX pump details
- [Optical Convergence Engine](OPTICAL_CONVERGENCE_ENGINE.md) - LED calibration workflow
- [Data Processing Pipeline](DATA_PROCESSING_PIPELINE.md) - Detector integration with acquisition

---

**End of Hardware Communication Layer Documentation**
