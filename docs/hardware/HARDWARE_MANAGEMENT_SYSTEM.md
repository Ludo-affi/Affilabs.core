# Hardware Management System - Complete Architecture

## Overview
The hardware management system orchestrates **3 types of hardware** through a modular, signal-based architecture:

1. **SPR Controllers** - Optical measurement hardware (P4SPR, EZSPR)
2. **Kinetic Systems** - Flow/valve control (KNX, KNX2)
3. **Pump Systems** - Dual Cavro Centris syringe pumps

---

## Hardware Architecture

### **Hardware Components**

```
┌─────────────────────────────────────────────────────────┐
│                     AffiniteApp                         │
│                  (Main Orchestrator)                    │
└─────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  SPR System  │  │   Kinetic    │  │  Pump System │
│              │  │   System     │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
     │                   │                 │
     ▼                   ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ self.ctrl    │  │  self.knx    │  │  self.pump   │
│ (PicoP4SPR/  │  │ (Kinetic     │  │ (Pump        │
│  PicoEZSPR)  │  │  Controller) │  │  Controller) │
└──────────────┘  └──────────────┘  └──────────────┘
     │                   │                 │
     ▼                   ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ self.usb     │  │ Kinetic      │  │ Cavro Pump   │
│ (USB4000     │  │ Manager      │  │ Manager      │
│  Spectro-    │  │              │  │              │
│  meter)      │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
     │                   │                 │
     ▼                   ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ SPR          │  │ Valve/Flow   │  │ Dual Syringe │
│ Calibrator   │  │ Control      │  │ Pumps        │
│              │  │ Temperature  │  │ (CH1 + CH2)  │
└──────────────┘  └──────────────┘  └──────────────┘
```

---

## Device Configuration System

### **Configuration Dictionary**

```python
self.device_config: dict[str, str | None] = {
    "ctrl": "",    # SPR controller type: "PicoP4SPR", "PicoEZSPR", or ""
    "knx": "",     # Kinetic system: "KNX", "KNX2", or ""
    "pump": None   # Pump controller: PumpController object or None
}
```

### **Hardware Detection Process**

**1. Connection Thread (`connection_thread()`)**
- Runs in separate daemon thread
- Scans USB devices for hardware
- Calls `open_device()` after detection

**2. Device Discovery (`get_current_device_config()`)**
```python
def get_current_device_config(self) -> None:
    # Check SPR controller type
    if self.ctrl is not None:
        if hasattr(self.ctrl, 'name'):
            ctrl_name = self.ctrl.name
            if ctrl_name in ["pico_p4spr", "PicoP4SPR"]:
                self.device_config["ctrl"] = "PicoP4SPR"
            elif ctrl_name in ["pico_ezspr", "PicoEZSPR"]:
                self.device_config["ctrl"] = "PicoEZSPR"
    
    # Check kinetic system type
    if self.knx is not None:
        if hasattr(self.knx, 'name'):
            knx_name = self.knx.name
            if knx_name == "KNX":
                self.device_config["knx"] = "KNX"
            elif knx_name == "KNX2":
                self.device_config["knx"] = "KNX2"
    
    # Update UI display
    mods = []
    if self.device_config["ctrl"]:
        mods.append("SPR")
    if self.device_config["knx"]:
        mods.append("Kinetics")
    if self.pump:
        mods.append("Pumps")
    
    dev_str = " + ".join(mods) or "No Devices"
    # Result: "SPR + Kinetics + Pumps" or "SPR + Kinetics" or "No Devices"
```

---

## Hardware Initialization Flow

### **Complete Initialization Sequence**

```python
def open_device(self) -> None:
    """Open connection to devices."""
    # 1. Check connection status
    if self._con_tr.is_alive():
        # Handle connection errors
        
    # 2. Detect and configure devices
    self.get_current_device_config()
    
    # 3. Validate at least one controller exists
    if self.ctrl is None and self.knx is None:
        logger.debug("no device")
        self.stop()
        return
    
    # 4. Start application
    self.startup()
    
    # 5. Initialize Pump Manager (if pump hardware available)
    if self.pump:
        self.pump_manager = CavroPumpManager(self.pump)
        if self.pump_manager.initialize_pumps():
            # Configure syringe sizes (5 mL each)
            self.pump_manager.set_syringe_size(PumpAddress.PUMP_1, 5000)
            self.pump_manager.set_syringe_size(PumpAddress.PUMP_2, 5000)
            
            # Connect signals
            self.pump_manager.pump_state_changed.connect(self._on_pump_state_changed)
            self.pump_manager.error_occurred.connect(self._on_pump_error)
    
    # 6. Initialize Kinetic Manager (if KNX hardware available)
    if self.knx is not None:
        self.kinetic_manager = KineticManager(self.knx, self.exp_start)
        
        # Connect signals
        self.kinetic_manager.valve_state_changed.connect(self._on_valve_state_changed)
        self.kinetic_manager.sensor_reading.connect(self._on_sensor_reading)
        self.kinetic_manager.device_temp_updated.connect(self._on_device_temp_updated)
        self.kinetic_manager.injection_started.connect(self._on_injection_started)
        self.kinetic_manager.injection_ended.connect(self._on_injection_ended)
        self.kinetic_manager.error_occurred.connect(self._on_kinetic_error)
    
    # 7. Initialize SPR Calibrator (if SPR controller + spectrometer available)
    if self.ctrl is not None and self.usb is not None:
        device_type = self.device_config.get("ctrl", "") or ""
        self.calibrator = SPRCalibrator(
            ctrl=self.ctrl,
            usb=self.usb,
            device_type=device_type,
            stop_flag=self._c_stop,
        )
        self.calibrator.set_progress_callback(self.calibration_progress.emit)
    
    # 8. Setup UI components
    self.main_window.sidebar.device_widget.setup(
        self.device_config["ctrl"],
        self.device_config["knx"],
        self.pump,
    )
    self.main_window.sidebar.kinetic_widget.setup(
        self.device_config["ctrl"],
        self.device_config["knx"],
    )
```

---

## Hardware Managers

### **1. Pump Manager (`CavroPumpManager`)**

**Purpose**: High-level control of dual Tecan Cavro Centris syringe pumps

**Initialization**:
```python
if self.pump:
    self.pump_manager = CavroPumpManager(self.pump)
    if self.pump_manager.initialize_pumps():
        # Set syringe volumes (µL)
        self.pump_manager.set_syringe_size(PumpAddress.PUMP_1, 5000)  # 5 mL
        self.pump_manager.set_syringe_size(PumpAddress.PUMP_2, 5000)  # 5 mL
```

**Capabilities**:
- Volume-based aspirate/dispense (µL precision)
- Syringe position tracking (steps → volume)
- Valve control (9-port distribution valves)
- Flow rate management (ml/min)
- Error detection and recovery
- State monitoring and diagnostics

**Key Methods**:
```python
# Volume operations
pump_manager.aspirate(address, volume_ul, flow_rate)
pump_manager.dispense(address, volume_ul, flow_rate)

# Valve control
pump_manager.set_valve_position(address, port)
pump_manager.verify_valve_position(address, port, timeout)

# State queries
state = pump_manager.get_pump_state(address)
position = pump_manager.get_syringe_position(address)
port = pump_manager.get_valve_position(address)

# Flow control
pump_manager.start_flow(address, rate_ml_per_min)
pump_manager.stop()
pump_manager.pause()
```

**Signals Emitted**:
```python
pump_state_changed = Signal(int, str)      # (address, description)
valve_position_changed = Signal(int, int)  # (address, port)
error_occurred = Signal(int, str)          # (address, error_message)
operation_progress = Signal(str, int)      # (operation_name, progress_percent)
```

**Address Constants**:
```python
PumpAddress.PUMP_1 = 0x31      # Channel 1
PumpAddress.PUMP_2 = 0x32      # Channel 2
PumpAddress.BROADCAST = 0x41   # Both pumps
```

---

### **2. Kinetic Manager (`KineticManager`)**

**Purpose**: Manages flow control, valve operations, and sensor readings for kinetic experiments

**Initialization**:
```python
if self.knx is not None:
    self.kinetic_manager = KineticManager(self.knx, self.exp_start)
```

**Capabilities**:
- Valve position control (Sample/Waste/Regen)
- Flow rate management
- Temperature monitoring (sensor + device)
- Injection timing and logging
- Event tracking
- Kinetic log buffering

**Key Methods**:
```python
# Valve control
kinetic_manager.set_valve_position(channel, position)
# position: "Sample", "Waste", "Regen"

# Flow control  
kinetic_manager.set_flow_rate(rate)

# Event logging
kinetic_manager.log_event(channel, event_type, exp_time)
# event_type: "Injection", "Regeneration", "Flush", etc.

# State queries
valve_pos = kinetic_manager.get_valve_position(channel)
flow_rate = kinetic_manager.get_current_flow_rate()
temp = kinetic_manager.get_sensor_temperature()
```

**Signals Emitted**:
```python
valve_state_changed = Signal(str, str)        # (channel, position_name)
sensor_reading = Signal(dict)                 # sensor data dict
device_temp_updated = Signal(str, str)        # (temperature, source)
injection_started = Signal(str, float)        # (channel, exp_time)
injection_ended = Signal(str)                 # (channel)
error_occurred = Signal(str, str)             # (channel, error_message)
```

**Kinetic Log Structure**:
```python
{
    "timestamps": [],  # Absolute timestamps (strings)
    "times": [],       # Experiment time (floats, seconds)
    "events": [],      # Event descriptions (strings)
    "flow": [],        # Flow rates (floats, µL/min)
    "temp": [],        # Sensor temperatures (floats, °C)
    "dev": []          # Device temperatures (floats, °C)
}
```

---

### **3. SPR Calibrator (`SPRCalibrator`)**

**Purpose**: Performs 9-step SPR optical calibration

**Initialization**:
```python
if self.ctrl is not None and self.usb is not None:
    self.calibrator = SPRCalibrator(
        ctrl=self.ctrl,
        usb=self.usb,
        device_type=device_type,
        stop_flag=self._c_stop,
    )
    self.calibrator.set_progress_callback(self.calibration_progress.emit)
```

**Calibration Steps**:
1. Dark noise measurement
2. LED intensity optimization (per channel)
3. Reference intensity collection
4. Wavelength range detection
5. Fourier weight calculation
6. Signal validation
7. Error checking
8. Calibration data storage
9. Status reporting

**Key Methods**:
```python
# Full calibration
result = calibrator.run_full_calibration()

# Individual steps
calibrator.measure_dark_noise()
calibrator.optimize_led_intensity(channel)
calibrator.collect_reference_signal(channel)
calibrator.validate_calibration()

# Configuration
calibrator.set_integration_time(ms)
calibrator.set_num_scans(count)
calibrator.set_channel_mode(single_mode, channel)
```

**Calibration Data Output**:
```python
{
    "wave_data": np.ndarray,           # Wavelength axis (nm)
    "wave_min_index": int,             # Valid range start
    "wave_max_index": int,             # Valid range end
    "fourier_weights": np.ndarray,     # FFT filter coefficients
    "dark_noise": np.ndarray,          # Background spectrum
    "ref_sig": dict[str, np.ndarray],  # Reference signals per channel
    "leds_calibrated": dict[str, int], # Optimal LED intensities
    "integration": int,                # Integration time (ms)
    "num_scans": int,                  # Scans to average
    "calibrated": bool                 # Success flag
}
```

**Progress Callback**:
```python
# Emits (step_number: int, step_description: str)
calibration_progress.emit(3, "Optimizing LED intensity for CH1")
```

---

## Signal-Based Communication

### **Hardware → Application Signals**

The system uses Qt signals for **hardware-to-software** communication:

#### **Pump Manager Signals**
```python
# Signal handler registration
self.pump_manager.pump_state_changed.connect(self._on_pump_state_changed)
self.pump_manager.error_occurred.connect(self._on_pump_error)

# Handler implementation
def _on_pump_state_changed(self, address: int, description: str) -> None:
    """Handle pump state changes."""
    ch_name = "CH1" if address == PumpAddress.PUMP_1 else "CH2"
    
    # Update internal state
    if "Running" in description or "Flowing" in description:
        self.pump_states[ch_name] = "Running"
    elif "Stopped" in description:
        self.pump_states[ch_name] = "Off"
    else:
        self.pump_states[ch_name] = description
    
    # Update UI
    self.update_pump_display.emit(self.pump_states, self.synced)

def _on_pump_error(self, address: int, error: str) -> None:
    """Handle pump errors."""
    ch_name = "CH1" if address == PumpAddress.PUMP_1 else "CH2"
    logger.error(f"Pump {ch_name} error: {error}")
    show_message(f"Pump {ch_name} Error: {error}", msg_type="Warning")
```

#### **Kinetic Manager Signals**
```python
# Signal handler registration
self.kinetic_manager.valve_state_changed.connect(self._on_valve_state_changed)
self.kinetic_manager.sensor_reading.connect(self._on_sensor_reading)
self.kinetic_manager.device_temp_updated.connect(self._on_device_temp_updated)
self.kinetic_manager.injection_started.connect(self._on_injection_started)
self.kinetic_manager.injection_ended.connect(self._on_injection_ended)

# Handler implementations
def _on_valve_state_changed(self, channel: str, position_name: str) -> None:
    """Handle valve position changes."""
    self.valve_states[channel] = position_name
    logger.debug(f"Valve {channel} state: {position_name}")

def _on_sensor_reading(self, readings: dict) -> None:
    """Handle temperature/pressure sensor readings."""
    self.update_sensor_display.emit(readings)

def _on_device_temp_updated(self, temperature: str, source: str) -> None:
    """Handle device temperature updates."""
    try:
        temp_val = float(temperature)
        self.temp = temp_val
        self.update_temp_display.emit(temperature, source)
    except ValueError:
        logger.warning(f"Invalid temperature value: {temperature}")

def _on_injection_started(self, channel: str, exp_time: float) -> None:
    """Handle injection start events."""
    logger.info(f"Injection started on {channel} at {exp_time:.2f}s")
    # Update kinetic logs
    self.log_ch1 = self.kinetic_manager.get_kinetic_log("CH1")
    if self.device_config["knx"] in ["KNX2"]:
        self.log_ch2 = self.kinetic_manager.get_kinetic_log("CH2")

def _on_injection_ended(self, channel: str) -> None:
    """Handle injection end events."""
    logger.info(f"Injection ended on {channel}")
```

#### **Calibrator Signals**
```python
# Signal handler registration
self.calibration_started.connect(self._on_calibration_started)
self.calibration_status.connect(self._on_calibration_status)
self.calibration_progress.connect(self._on_calibration_progress)

# Progress updates from calibrator
def _on_calibration_progress(self, step: int, description: str) -> None:
    """Handle calibration progress updates."""
    logger.info(f"Calibration step {step}: {description}")
    self.main_window.update_calibration_status(step, description)
```

---

## Hardware State Management

### **State Variables**

```python
# Device instances
self.ctrl: PicoP4SPR | PicoEZSPR | None = None      # SPR controller
self.knx: KineticController | PicoEZSPR | None = None  # Kinetic system
self.pump: PumpController | None = None               # Pump hardware
self.usb: USB4000 | None = None                       # Spectrometer

# Manager instances
self.pump_manager: CavroPumpManager | None = None     # Pump operations
self.kinetic_manager: KineticManager | None = None    # Kinetic operations
self.calibrator: SPRCalibrator | None = None          # Calibration

# Device configuration
self.device_config: dict[str, str | None] = {
    "ctrl": "",    # "PicoP4SPR", "PicoEZSPR", or ""
    "knx": "",     # "KNX", "KNX2", or ""
    "pump": None   # PumpController or None
}

# Operational state
self.pump_states: dict[str, str] = {
    "CH1": "Off",      # "Off", "Running", "Error"
    "CH2": "Off"
}
self.valve_states: dict[str, str] = {
    "CH1": "Waste",    # "Sample", "Waste", "Regen"
    "CH2": "Waste"
}
self.calibrated = False           # SPR calibration status
self.synced = False               # Pump-flow synchronization
self.flow_rate = 0.0              # Current flow rate (µL/min)
```

### **State Query Methods**

```python
# Check what hardware is connected
def has_spr_controller(self) -> bool:
    return self.ctrl is not None

def has_kinetic_system(self) -> bool:
    return self.knx is not None

def has_pump_system(self) -> bool:
    return self.pump is not None

def is_calibrated(self) -> bool:
    return self.calibrated

# Get current configuration
def get_device_config(self) -> dict:
    return self.device_config.copy()

# Get operational state
def get_pump_states(self) -> dict:
    return self.pump_states.copy()

def get_valve_states(self) -> dict:
    return self.valve_states.copy()
```

---

## Error Handling

### **Hardware Error Types**

**1. Connection Errors**
```python
# Detected in connection_thread() and open_device()
if self.ctrl is None and self.knx is None:
    logger.debug("no device")
    self.main_window.ui.status.setText("No Connection")
    self.stop()
```

**2. Initialization Errors**
```python
# Pump manager initialization
try:
    self.pump_manager = CavroPumpManager(self.pump)
    if not self.pump_manager.initialize_pumps():
        logger.warning("Pump manager initialization failed")
        self.pump_manager = None
except Exception as e:
    logger.exception(f"Error initializing pump manager: {e}")
    self.pump_manager = None
```

**3. Runtime Errors**
```python
# Pump errors (via signal)
def _on_pump_error(self, address: int, error: str) -> None:
    ch_name = "CH1" if address == PumpAddress.PUMP_1 else "CH2"
    logger.error(f"Pump {ch_name} error: {error}")
    show_message(f"Pump {ch_name} Error: {error}", msg_type="Warning")

# Kinetic errors (via signal)
def _on_kinetic_error(self, channel: str, error: str) -> None:
    logger.error(f"Kinetic {channel} error: {error}")
    show_message(f"Kinetic Error ({channel}): {error}", msg_type="Warning")
```

**4. Calibration Errors**
```python
# Calibration status signal
def _on_calibration_status(self, success: bool, message: str) -> None:
    if success:
        self.calibrated = True
        logger.info(f"Calibration successful: {message}")
    else:
        self.calibrated = False
        logger.error(f"Calibration failed: {message}")
        show_message(f"Calibration Error: {message}", msg_type="Error")
```

---

## Hardware Lifecycle

### **Startup Sequence**

```
1. Application Launch
   └─→ __init__() - Initialize variables

2. Connection Thread
   └─→ connection_thread() - Scan for devices
       └─→ open_device()

3. Device Configuration
   └─→ get_current_device_config() - Identify hardware
       └─→ Update device_config dict

4. Manager Initialization
   ├─→ CavroPumpManager (if pump present)
   ├─→ KineticManager (if KNX present)
   └─→ SPRCalibrator (if ctrl + usb present)

5. Signal Connection
   └─→ Connect all hardware signals to handlers

6. UI Update
   └─→ Update device display and status

7. Calibration (if SPR controller present)
   └─→ Run 9-step calibration process

8. Ready for Operation
```

### **Shutdown Sequence**

```
1. Stop Recording
   └─→ Save any buffered data

2. Stop Hardware Operations
   ├─→ pump_manager.stop()
   ├─→ kinetic_manager.stop_flow()
   └─→ Set stop flags (_b_stop, _c_stop, _s_stop)

3. Save Logs
   ├─→ save_kinetic_log()
   ├─→ save_temp_log()
   └─→ save_rec_data()

4. Disconnect Hardware
   └─→ disconnect_dev()

5. Join Threads
   └─→ Wait for background threads to exit

6. Application Exit
```

---

## Configuration Options

### **Hardware-Specific Settings**

**SPR Controller**:
```python
# Integration time (spectrometer exposure)
self.integration = 10  # milliseconds (MIN: 3, MAX: 1000)

# Number of scans to average
self.num_scans = 1  # (1-100)

# Single channel mode
self.single_mode = False
self.single_ch = "x"  # "A", "B", "C", or "x" (all channels)

# LED delay (switching time)
self.led_delay = 0.005  # seconds
```

**Kinetic System**:
```python
# Flow rate (µL/min)
self.flow_rate = 60.0  # typical range: 10-200 µL/min

# Sensor reading interval
self.sensor_interval = 10  # seconds

# Temperature range validation
TEMP_CHECK_MIN = 5      # °C
TEMP_CHECK_MAX = 75     # °C
```

**Pump System**:
```python
# Syringe sizes (µL)
PUMP_1_VOLUME = 5000  # 5 mL
PUMP_2_VOLUME = 5000  # 5 mL

# Flow rates (ml/min)
DEFAULT_FLOW_RATE = 1.0
MAX_FLOW_RATE = 10.0
MIN_FLOW_RATE = 0.001

# Valve positions (1-9 ports)
PORT_SAMPLE = 1
PORT_WASTE = 2
PORT_REGEN = 3
```

---

## Hardware Compatibility Matrix

| Device Type | Controller | Kinetic System | Pump System | Channels |
|-------------|-----------|----------------|-------------|----------|
| **PicoP4SPR** | PicoP4SPR | None | Optional | 4 (A-D) |
| **PicoEZSPR** | PicoEZSPR | Integrated | Optional | 2 (A-B) |
| **KNX** | Any | KNX | Required | 1 (CH1) |
| **KNX2** | Any | KNX2 | Required | 2 (CH1+CH2) |

### **Valid Configurations**

✅ **Supported Combinations**:
1. `ctrl=PicoP4SPR, knx=None, pump=None` - Basic SPR (4 channels)
2. `ctrl=PicoP4SPR, knx=KNX, pump=Yes` - SPR + Single kinetics
3. `ctrl=PicoP4SPR, knx=KNX2, pump=Yes` - SPR + Dual kinetics
4. `ctrl=PicoEZSPR, knx=KNX, pump=Yes` - Integrated SPR+kinetics
5. `ctrl=None, knx=KNX, pump=Yes` - Kinetics only

❌ **Invalid Combinations**:
- `knx=KNX/KNX2, pump=None` - Kinetic system requires pumps
- `ctrl=PicoEZSPR, knx=None` - EZSPR has integrated kinetics
- `ctrl=None, knx=None, pump=Yes` - Pumps need kinetic controller

---

## Best Practices

### **Hardware Initialization**
1. ✅ Always check hardware presence before creating managers
2. ✅ Connect signals immediately after manager creation
3. ✅ Handle initialization failures gracefully
4. ✅ Log all hardware events for debugging
5. ✅ Validate configuration compatibility

### **Hardware Operations**
1. ✅ Use manager methods, not raw hardware commands
2. ✅ Check operation success via return values
3. ✅ Wait for operations to complete before next command
4. ✅ Handle errors via signal handlers
5. ✅ Monitor state changes via signals

### **Error Recovery**
1. ✅ Implement timeout-based recovery
2. ✅ Reset hardware state on errors
3. ✅ Retry operations with exponential backoff
4. ✅ Provide user feedback on failures
5. ✅ Log detailed error information

---

## Troubleshooting

### **Common Issues**

**1. "No Connection" Error**
- **Cause**: No hardware detected
- **Check**: USB cables, drivers, device power
- **Solution**: Reconnect hardware and restart application

**2. Pump Initialization Failed**
- **Cause**: Communication error or wrong syringe config
- **Check**: Pump power, USB connection, baud rate
- **Solution**: Power cycle pumps, verify PumpController setup

**3. Calibration Failed**
- **Cause**: LED intensity too low/high, no signal
- **Check**: LED connections, spectrometer connection, sample
- **Solution**: Check hardware, adjust integration time

**4. Kinetic Manager Not Created**
- **Cause**: KNX hardware not detected
- **Check**: USB connection, drivers, firmware
- **Solution**: Reconnect KNX, check device manager

**5. Temperature Readings Invalid**
- **Cause**: Sensor disconnected or out of range
- **Check**: Temperature sensor connections
- **Solution**: Reconnect sensor, verify TEMP_CHECK_MIN/MAX

---

## Summary

The hardware management system provides:

✅ **Modular Architecture** - Independent managers for each hardware type  
✅ **Signal-Based Communication** - Async, thread-safe event handling  
✅ **Automatic Configuration** - Detects and configures hardware automatically  
✅ **Robust Error Handling** - Graceful degradation on failures  
✅ **State Synchronization** - Consistent state across UI and hardware  
✅ **High-Level APIs** - Simplified control through manager classes  

**Key Design Principles**:
1. **Separation of Concerns** - Hardware, managers, and application logic separated
2. **Event-Driven** - Qt signals for async hardware communication
3. **Fault Tolerance** - Handles missing hardware gracefully
4. **Extensibility** - Easy to add new hardware types
5. **Testability** - Managers can be mocked for unit testing
