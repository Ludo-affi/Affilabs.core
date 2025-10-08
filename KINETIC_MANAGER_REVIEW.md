# Kinetic Manager - Class Structure Review

## Overview
This document outlines the proposed `KineticManager` class structure for managing KNX kinetic system operations. **All methods are defined but not yet implemented** - this is for architectural review before implementation.

---

## Architecture Summary

### **Design Philosophy**
- **Separation of concerns**: Valve control, sensor reading, logging separated into logical groups
- **State encapsulation**: All kinetic state managed within the class
- **Qt integration**: Signals for UI updates without tight coupling
- **Sync mode support**: CH1 controls both channels when synchronized
- **Error resilience**: Validation, retry logic, graceful degradation

---

## Data Classes

### **1. `ValvePosition` (Enum)**
Represents combined 3-way + 6-port valve states:
- `WASTE` - 3-way=0, 6-port=0
- `LOAD` - 3-way=1, 6-port=0
- `INJECT` - 3-way=1, 6-port=1
- `DISPOSE` - 3-way=0, 6-port=1

### **2. `Channel` (Enum)**
Channel identifiers:
- `CH1`, `CH2`, `BOTH` (for synced operations)

### **3. `ValveState` (Dataclass)**
Tracks valve positions for one channel:
- `three_way_position: int` - Current 3-way position (0 or 1)
- `six_port_position: int` - Current 6-port position (0 or 1)
- `last_injection_time: float` - When injection started (exp time)
- `last_injection_timestamp: str` - Human-readable timestamp
- **Properties:**
  - `position` → Combined `ValvePosition` enum
  - `position_name` → "Waste", "Load", etc.

### **4. `SensorReading` (Dataclass)**
Single sensor measurement:
- `flow_rate: float | None` - Flow in ml/min
- `temperature: float | None` - Temp in °C
- `timestamp: float` - When reading was taken
- `exp_time: float` - Experiment time
- **Method:** `is_valid()` → Check if data present

### **5. `ChannelState` (Dataclass)**
Complete state of one channel:
- `channel_name: str` - "CH1" or "CH2"
- `valve: ValveState` - Valve positions
- `pump_running: bool` - Is pump active
- `pump_rate: float` - Pump rate in ml/min
- `current_flow: float | None` - Latest sensor flow reading
- `current_temp: float | None` - Latest sensor temp reading
- `injection_timer_active: bool` - Is auto-timeout running
- `injection_timeout_sec: int` - Timeout duration

### **6. `KineticLog` (Dataclass)**
Event log for one channel:
- `timestamps: list[str]` - "HH:MM:SS" format
- `times: list[str]` - Experiment times
- `events: list[str]` - Event descriptions
- `flow: list[str]` - Flow readings (or "-")
- `temp: list[str]` - Temp readings (or "-")
- `dev: list[str]` - Device temps (or "-")
- **Methods:**
  - `append_event()` → Add log entry
  - `to_dict()` → Export as dict
  - `clear()` → Empty log

---

## Method Categories

### **1. Hardware Availability** (2 methods)
```python
is_available() -> bool
  # Check if KNX hardware is connected

get_device_type() -> str
  # Return "KNX", "KNX2", "PicoKNX2", etc.
```

---

### **2. Three-Way Valve Control** (3 methods)
```python
set_three_way_valve(channel: str, position: int) -> bool
  # Set valve to 0 (waste) or 1 (load)
  # Handles sync mode, pauses sensors, emits signals

get_three_way_position(channel: str) -> int
  # Query current position

toggle_three_way_valve(channel: str) -> bool
  # Flip between waste and load
```

**Implementation Notes:**
- Must pause sensor reading during valve movement
- Map channel to hardware channel (1, 2, or 3 for synced)
- Call `self.knx.knx_three(state, hw_channel)`
- Update internal state
- Emit `valve_state_changed` signal

---

### **3. Six-Port Valve Control** (3 methods)
```python
set_six_port_valve(channel: str, position: int) -> bool
  # Set valve to 0 (load) or 1 (inject)
  # Handles sync mode, pauses sensors, emits signals

get_six_port_position(channel: str) -> int
  # Query current position

toggle_six_port_valve(channel: str) -> bool
  # Flip between load and inject
```

**Implementation Notes:**
- Similar to 3-way but uses `self.knx.knx_six(state, hw_channel)`
- More complex due to injection timing

---

### **4. Valve State Management** (4 methods)
```python
get_valve_position(channel: str) -> ValvePosition
  # Get combined position (WASTE/LOAD/INJECT/DISPOSE)

get_valve_position_name(channel: str) -> str
  # Get position as string ("Waste", "Load", etc.)

verify_valve_position(channel, expected_3way, expected_6port, timeout) -> bool
  # Query hardware and confirm valve reached target
  # Wait and retry if needed

update_valve_state_from_hardware(channel: str) -> bool
  # Query hardware via knx.knx_status(hw_channel)
  # Update internal state
  # Emit signal if changed
```

**Implementation Notes:**
- `verify_valve_position` should poll hardware every 100ms up to timeout
- `update_valve_state_from_hardware` called by sensor thread

---

### **5. Injection Management** (4 methods)
```python
start_injection(channel: str, flow_rate: float, auto_timeout: bool) -> bool
  # Set six-port to inject
  # Calculate timeout: (100 / flow_rate) + 2 minutes
  # Start QTimer for auto-shutoff
  # Log injection event
  # Emit injection_started signal

end_injection(channel: str) -> bool
  # Set six-port to load
  # Stop QTimer
  # Emit injection_ended signal

_auto_end_injection(channel: str) -> None
  # Called by QTimer timeout
  # Log auto-shutoff
  # Call end_injection()

get_injection_time(channel: str) -> float
  # Return when last injection started (exp time)
```

**Implementation Notes:**
- Timeout formula: `(INJECTION_BASE_TIME_SEC / flow_rate) + INJECTION_SAFETY_MARGIN_MIN * 60`
- `_auto_end_injection` connected to QTimer.timeout signals
- Must handle sync mode (both channels injected together)

---

### **6. Synchronization** (4 methods)
```python
enable_sync() -> None
  # Set self.synced = True
  # Copy CH1 states to CH2
  # Emit signals

disable_sync() -> None
  # Set self.synced = False
  # Emit signals

is_synced() -> bool
  # Return sync status

sync_channel_states() -> None
  # Force CH2 to match CH1
```

**Implementation Notes:**
- When synced, CH1 commands affect both channels
- Hardware channel 3 controls both valves simultaneously
- Valve position changes should update both channels

---

### **7. Sensor Reading** (6 methods)
```python
read_sensor(channel: str) -> SensorReading | None
  # Call self.knx.knx_status(hw_channel)
  # Extract flow and temp from response dict
  # Return SensorReading object

get_averaged_sensor_reading(channel: str) -> tuple[str, str]
  # Average last N readings from buffer
  # Return (flow_text, temp_text) as formatted strings

update_sensor_buffers(channel, flow, temp) -> None
  # Append to _flow_buf_1/_flow_buf_2 and _temp_buf_1/_temp_buf_2
  # Keep buffer size reasonable (last 100 readings)

clear_sensor_buffers() -> None
  # Empty all buffers

pause_sensor_reading() -> None
  # Set _sensor_paused flag (used during valve movement)

resume_sensor_reading() -> None
  # Clear _sensor_paused flag

is_sensor_paused() -> bool
  # Check flag
```

**Implementation Notes:**
- `knx.knx_status(hw_channel)` returns dict: `{"flow": float, "temp": float, "3W": int, "6P": int}`
- Averaging window: `self.sensor_avg_window` (default 10 readings)
- Format: `f"{value:.2f}"` for flow/temp
- Sensor reading should be paused during valve movements (takes ~0.3s)

---

### **8. Device Temperature** (2 methods)
```python
read_device_temperature() -> float | None
  # Call self.knx.get_status() (method varies by device type)
  # Extract temperature
  # Validate range (5°C to 75°C)
  # Add to averaging buffer
  # Return averaged value

get_averaged_device_temperature() -> str
  # Average last N readings from buffer
  # Return formatted string with 1 decimal place
```

**Implementation Notes:**
- Device type matters:
  - `knx.version == "1.1"`: `status = knx.get_status()`, `temp = status['Temperature']`
  - `PicoKNX2` or `PicoEZSPR`: `temp = knx.get_status()` (returns float directly)
- Average over `DEVICE_TEMP_AVG_WINDOW` (5 readings)

---

### **9. Event Logging** (6 methods)
```python
log_event(channel, event, flow="-", temp="-", dev="-") -> None
  # Add entry to kinetic log
  # Calculate exp_time = time.time() - self.exp_start
  # Call log.append_event()
  # Handle sync mode (log to both if synced)

log_sensor_reading(channel, flow, temp) -> None
  # Convenience: log_event with "Sensor reading"

log_device_reading(temp) -> None
  # Log to both CH1 and CH2
  # Event: "Device reading"

get_log(channel: str) -> KineticLog
  # Return log object

get_log_dict(channel: str) -> dict[str, list]
  # Return log as dict for export/CSV

clear_log(channel: str) -> None
  # Empty log for one channel

clear_all_logs() -> None
  # Empty both logs
```

**Implementation Notes:**
- Every sensor reading creates a log entry (can be hundreds per minute)
- Consider adding `log_sampling_rate` to reduce log spam
- Device readings go to both channels

---

### **10. State Queries** (3 methods)
```python
get_channel_state(channel: str) -> ChannelState
  # Return complete state object

get_all_states() -> dict[str, ChannelState]
  # Return {"CH1": state1, "CH2": state2}

get_valve_states_dict() -> dict[str, str]
  # Return {"CH1": "Waste", "CH2": "Load"}
  # For UI compatibility with existing code
```

---

### **11. Experiment Time Management** (3 methods)
```python
set_experiment_start_time(start_time: float) -> None
  # Set self.exp_start

get_experiment_time() -> float
  # Return time.time() - self.exp_start

reset_experiment_time() -> None
  # Set new exp_start = time.time()
  # Adjust all logged times by time_diff
```

**Implementation Notes:**
- `reset_experiment_time` must update all existing log entries
- Subtract time difference from logged times

---

### **12. Shutdown** (1 method)
```python
shutdown() -> None
  # Stop injection timers
  # Set all valves to safe positions (load)
  # Clear buffers and logs
  # Close hardware connection
```

---

### **13. Utility Methods** (2 methods)
```python
_hardware_channel_number(channel: str) -> int
  # Map "CH1"/"CH2" to 1, 2, or 3 (synced)

_validate_channel(channel: str) -> bool
  # Check channel name is valid
```

---

## Qt Signals

```python
valve_state_changed = Signal(str, str)  # channel, position_name
  # Emitted when any valve changes position

sensor_reading = Signal(dict)  # {"flow1": str, "temp1": str, "flow2": str, "temp2": str}
  # Emitted after sensor read with all channels

device_temp_updated = Signal(str, str)  # temperature, source ("ctrl" or "knx")
  # Emitted when device temp changes

injection_started = Signal(str, float)  # channel, exp_time
  # Emitted when injection begins

injection_ended = Signal(str)  # channel
  # Emitted when injection ends

error_occurred = Signal(str, str)  # channel, error_message
  # Emitted on any error
```

---

## Constants

```python
# Sensor
DEFAULT_SENSOR_AVG_WINDOW = 10  # readings to average
DEFAULT_SENSOR_INTERVAL_SEC = 10  # seconds between reads
DEVICE_TEMP_MIN = 5.0  # °C
DEVICE_TEMP_MAX = 75.0  # °C
DEVICE_TEMP_AVG_WINDOW = 5  # readings

# Injection
INJECTION_BASE_TIME_SEC = 100  # base injection time
INJECTION_SAFETY_MARGIN_MIN = 2  # extra timeout minutes
```

---

## Usage Example (Main App Integration)

```python
# Initialize
self.kinetic_manager = KineticManager(
    kinetic_controller=self.knx,
    experiment_start_time=self.exp_start
)

# Connect signals
self.kinetic_manager.valve_state_changed.connect(self._on_valve_changed)
self.kinetic_manager.sensor_reading.connect(self._update_sensor_display)
self.kinetic_manager.injection_started.connect(self._on_injection_start)

# Three-way valve toggle (user clicks button)
self.kinetic_manager.toggle_three_way_valve("CH1")

# Six-port valve toggle with injection
if self.kinetic_manager.get_valve_position("CH1") == ValvePosition.LOAD:
    # Start injection
    flow_rate = float(self.ui.run_rate_ch1.currentText())
    self.kinetic_manager.start_injection("CH1", flow_rate, auto_timeout=True)
else:
    # End injection
    self.kinetic_manager.end_injection("CH1")

# Sensor reading (in background thread)
while not stopped:
    if not self.kinetic_manager.is_sensor_paused():
        reading = self.kinetic_manager.read_sensor("CH1")
        if reading and reading.is_valid():
            self.kinetic_manager.update_sensor_buffers("CH1", reading.flow_rate, reading.temperature)
            flow, temp = self.kinetic_manager.get_averaged_sensor_reading("CH1")
            self.kinetic_manager.log_sensor_reading("CH1", flow, temp)
    time.sleep(10)

# Get log for export
log_dict = self.kinetic_manager.get_log_dict("CH1")
save_to_csv(log_dict)
```

---

## Questions for Review

### **1. Data Structure**
- Is the separation into `ValveState`, `ChannelState`, `KineticLog` clear?
- Should `SensorReading` include valve positions too?
- Is `ValvePosition` enum covering all cases?

### **2. Method Organization**
- Are methods grouped logically?
- Missing any key operations?
- Any methods that should be combined or split?

### **3. Sensor Reading**
- Should sensor reading be entirely managed by KineticManager (with its own thread)?
- Or just provide methods for the existing sensor thread to call?
- Current design: methods for existing thread to call

### **4. Logging**
- Every sensor reading creates a log entry - is this too verbose?
- Should we add sampling (log every Nth reading)?
- Or leave it to the caller to decide when to log?

### **5. Synchronization**
- Is the sync model clear (CH1 controls both, hardware channel 3)?
- Should there be a "sync_mode" parameter on each method instead of global flag?

### **6. Error Handling**
- Should methods return bool (success/fail) or raise exceptions?
- Current design: return bool, emit error signals
- Add retry logic?

### **7. Thread Safety**
- QTimer runs in main thread, sensor reading in background thread
- Need locks for state access?
- Or assume all valve commands run in main thread?

### **8. Injection Timeout**
- Current formula: `(100 / flow_rate) + 2` minutes
- Where does "100" come from? Should it be configurable?
- Is auto-timeout mandatory or optional?

### **9. Missing Features**
- Pump control (run/stop/flush) - should this be in KineticManager or separate PumpManager?
- Current design: assumes separate PumpManager (already created)

### **10. Backward Compatibility**
- `get_valve_states_dict()` returns dict for old UI code
- Keep this or update all UI code to use `get_channel_state()`?

---

## Recommendations Before Implementation

1. **Confirm sensor thread integration** - Should KineticManager own the sensor thread or just provide methods?

2. **Clarify sync mode behavior** - When CH1 changes, should CH2 update immediately or on next command?

3. **Define error handling strategy** - Exceptions vs return codes vs signals only?

4. **Decide on thread safety** - Add locks or document thread usage rules?

5. **Review injection timeout formula** - Magic numbers should be constants or configurable?

6. **Consider log sampling** - Too many log entries may cause performance issues?

---

## Next Steps

Once you've reviewed and approved this structure:
1. I'll implement each method category one at a time
2. We can test each group before moving to the next
3. Then integrate into main.py
4. Finally refactor sensor thread to use the new manager

**Please review and let me know:**
- Which methods look good as-is?
- Which need changes to signature or behavior?
- Any missing functionality?
- Any concerns about the approach?
