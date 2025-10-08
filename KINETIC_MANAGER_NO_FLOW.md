# KineticManager - Flow Rate Removal

## Summary

Flow rate monitoring has been removed from the KineticManager as it is obsolete. The class now only handles **temperature sensing** from the KNX hardware.

## Changes Made

### 1. Data Classes Updated

**SensorReading** (Lines 88-95)
```python
# BEFORE:
@dataclass
class SensorReading:
    """Flow and temperature sensor reading."""
    flow_rate: float | None = None  # ml/min
    temperature: float | None = None  # °C
    timestamp: float = field(default_factory=time.time)
    exp_time: float = 0.0
    
    def is_valid(self) -> bool:
        return self.flow_rate is not None and self.temperature is not None

# AFTER:
@dataclass
class SensorReading:
    """Temperature sensor reading."""
    temperature: float | None = None  # °C
    timestamp: float = field(default_factory=time.time)
    exp_time: float = 0.0
    
    def is_valid(self) -> bool:
        return self.temperature is not None
```

**ChannelState** (Lines 98-106)
```python
# BEFORE:
@dataclass
class ChannelState:
    channel_name: str
    valve: ValveState = field(default_factory=ValveState)
    pump_running: bool = False
    pump_rate: float = 0.0
    current_flow: float | None = None  # REMOVED
    current_temp: float | None = None
    injection_timer_active: bool = False
    injection_timeout_sec: int = 0

# AFTER:
@dataclass
class ChannelState:
    channel_name: str
    valve: ValveState = field(default_factory=ValveState)
    pump_running: bool = False
    pump_rate: float = 0.0
    current_temp: float | None = None  # Temperature only
    injection_timer_active: bool = False
    injection_timeout_sec: int = 0
```

**KineticLog** (Lines 115-153)
```python
# BEFORE:
@dataclass
class KineticLog:
    timestamps: list[str] = field(default_factory=list)
    times: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    flow: list[str] = field(default_factory=list)  # REMOVED
    temp: list[str] = field(default_factory=list)
    dev: list[str] = field(default_factory=list)
    
    def append_event(self, event, exp_time, flow="-", temp="-", dev="-"):
        ...
        self.flow.append(flow)  # REMOVED
        ...
    
    def to_dict(self):
        return {
            "timestamps": self.timestamps,
            "times": self.times,
            "events": self.events,
            "flow": self.flow,  # REMOVED
            "temp": self.temp,
            "dev": self.dev,
        }

# AFTER:
@dataclass
class KineticLog:
    timestamps: list[str] = field(default_factory=list)
    times: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    temp: list[str] = field(default_factory=list)  # Temperature only
    dev: list[str] = field(default_factory=list)
    
    def append_event(self, event, exp_time, temp="-", dev="-"):
        ...
        # No flow parameter
        ...
    
    def to_dict(self):
        return {
            "timestamps": self.timestamps,
            "times": self.times,
            "events": self.events,
            "temp": self.temp,
            "dev": self.dev,
        }
```

### 2. Class Initialization Updated

**__init__ method** (Lines 183-233)
```python
# BEFORE:
self._flow_buf_1: list[float] = []  # REMOVED
self._temp_buf_1: list[float] = []
self._flow_buf_2: list[float] = []  # REMOVED
self._temp_buf_2: list[float] = []
self._device_temp_buf: list[float] = []

# AFTER:
self._temp_buf_1: list[float] = []  # Temperature only
self._temp_buf_2: list[float] = []
self._device_temp_buf: list[float] = []
```

### 3. Sensor Reading Methods Updated

**read_sensor()** (Lines 717-760)
```python
# BEFORE:
def read_sensor(self, channel: str) -> SensorReading | None:
    """Read flow and temperature sensor for a channel."""
    ...
    if isinstance(status, dict):
        flow_rate = status.get("flow")
        temperature = status.get("temp")
    ...
    reading = SensorReading(
        flow_rate=flow_rate,
        temperature=temperature,
        exp_time=exp_time
    )
    self.channels[channel].current_flow = flow_rate
    self.channels[channel].current_temp = temperature

# AFTER:
def read_sensor(self, channel: str) -> SensorReading | None:
    """Read temperature sensor for a channel."""
    ...
    if isinstance(status, dict):
        temperature = status.get("temp")
    elif isinstance(status, (list, tuple)) and len(status) >= 2:
        temperature = status[1]  # Temperature is typically second value
    ...
    reading = SensorReading(
        temperature=temperature,
        exp_time=exp_time
    )
    self.channels[channel].current_temp = temperature
```

**get_averaged_sensor_reading()** (Lines 765-785)
```python
# BEFORE:
def get_averaged_sensor_reading(self, channel: str) -> tuple[str, str]:
    """Get averaged sensor readings for display."""
    ...
    return (flow_text, temp_text)  # Tuple with flow and temp

# AFTER:
def get_averaged_sensor_reading(self, channel: str) -> str:
    """Get averaged temperature reading for display."""
    ...
    return temp_text  # Temperature only
```

**update_sensor_buffers()** (Lines 787-800)
```python
# BEFORE:
def update_sensor_buffers(self, channel: str, flow: float, temp: float) -> None:
    """Add new sensor reading to averaging buffer."""
    if channel == "CH1":
        self._flow_buf_1.append(flow)  # REMOVED
        self._temp_buf_1.append(temp)
    elif channel == "CH2":
        self._flow_buf_2.append(flow)  # REMOVED
        self._temp_buf_2.append(temp)

# AFTER:
def update_sensor_buffers(self, channel: str, temp: float) -> None:
    """Add new temperature reading to averaging buffer."""
    if channel == "CH1":
        self._temp_buf_1.append(temp)
    elif channel == "CH2":
        self._temp_buf_2.append(temp)
```

**clear_sensor_buffers()** (Lines 802-806)
```python
# BEFORE:
def clear_sensor_buffers(self) -> None:
    self._flow_buf_1.clear()  # REMOVED
    self._temp_buf_1.clear()
    self._flow_buf_2.clear()  # REMOVED
    self._temp_buf_2.clear()
    self._device_temp_buf.clear()

# AFTER:
def clear_sensor_buffers(self) -> None:
    self._temp_buf_1.clear()
    self._temp_buf_2.clear()
    self._device_temp_buf.clear()
```

### 4. Logging Methods Updated

**log_event()** (Lines 895-913)
```python
# BEFORE:
def log_event(self, channel, event, flow="-", temp="-", dev="-"):
    """Log a kinetic event."""
    self.logs[channel].append_event(event, exp_time, flow, temp, dev)

# AFTER:
def log_event(self, channel, event, temp="-", dev="-"):
    """Log a kinetic event."""
    self.logs[channel].append_event(event, exp_time, temp, dev)
```

**log_sensor_reading()** (Lines 915-923)
```python
# BEFORE:
def log_sensor_reading(self, channel: str, flow: str, temp: str) -> None:
    """Log a sensor reading event."""
    self.log_event(channel, "Sensor reading", flow=flow, temp=temp)

# AFTER:
def log_sensor_reading(self, channel: str, temp: str) -> None:
    """Log a sensor reading event."""
    self.log_event(channel, "Sensor reading", temp=temp)
```

### 5. Qt Signals Updated

**Class signals** (Lines 176-180)
```python
# BEFORE:
sensor_reading = Signal(dict)  # {"flow1": str, "temp1": str, "flow2": str, "temp2": str}

# AFTER:
sensor_reading = Signal(dict)  # {"temp1": str, "temp2": str}
```

## Integration Impact

### For main.py Integration

When integrating KineticManager into main.py, the sensor reading thread should now look like:

```python
def sensor_reading_thread(self):
    """Background thread for temperature sensor reading."""
    while self.dev.dev_connected:
        if self.kinetic_manager:
            # Read CH1
            reading_ch1 = self.kinetic_manager.read_sensor("CH1")
            if reading_ch1 and reading_ch1.is_valid():
                self.kinetic_manager.update_sensor_buffers("CH1", reading_ch1.temperature)
            
            # Read CH2
            reading_ch2 = self.kinetic_manager.read_sensor("CH2")
            if reading_ch2 and reading_ch2.is_valid():
                self.kinetic_manager.update_sensor_buffers("CH2", reading_ch2.temperature)
            
            # Get averaged readings (temperature only)
            temp1 = self.kinetic_manager.get_averaged_sensor_reading("CH1")
            temp2 = self.kinetic_manager.get_averaged_sensor_reading("CH2")
            
            # Emit signal for UI (no flow data)
            self.kinetic_manager.sensor_reading.emit({
                "temp1": temp1,
                "temp2": temp2
            })
        
        time.sleep(self.kinetic_manager.sensor_interval_sec)
```

### Signal Handler Changes

```python
def _on_sensor_reading(self, readings: dict):
    """Update UI with sensor readings (temperature only)."""
    # OLD: self.ui.label_flow_ch1.setText(readings["flow1"])  # REMOVED
    self.ui.label_temp_ch1.setText(readings["temp1"])
    # OLD: self.ui.label_flow_ch2.setText(readings["flow2"])  # REMOVED
    self.ui.label_temp_ch2.setText(readings["temp2"])
```

### Log Export Changes

When exporting logs, the structure now excludes flow data:

```python
log_dict = kinetic_manager.get_log_dict("CH1")
# log_dict = {
#     "timestamps": [...],
#     "times": [...],
#     "events": [...],
#     "temp": [...],      # Temperature only
#     "dev": [...]        # Device temperature
# }
# No "flow" key
```

## Benefits of This Change

1. **Cleaner Code**: Removed ~150 lines of flow-related code
2. **Simpler Data Structures**: Fewer fields to track and manage
3. **Reduced Memory**: Smaller buffers (2 instead of 4)
4. **Clearer Intent**: Class now clearly focused on temperature sensing
5. **Easier Maintenance**: Less obsolete code to work around

## Files Modified

- `utils/kinetic_manager.py` - Complete flow rate removal (1,092 lines)

## Testing Checklist

After this change:
- [ ] Verify temperature reading still works for CH1
- [ ] Verify temperature reading still works for CH2
- [ ] Check temperature averaging is functioning
- [ ] Verify logs only contain temperature (no flow columns)
- [ ] Test log export (no flow field in dict)
- [ ] Ensure UI updates correctly without flow display

## Backward Compatibility

⚠️ **Breaking Changes:**
- `SensorReading.flow_rate` attribute removed
- `ChannelState.current_flow` attribute removed
- `KineticLog.flow` list removed
- `get_averaged_sensor_reading()` now returns `str` instead of `tuple[str, str]`
- `update_sensor_buffers()` signature changed (removed `flow` parameter)
- `log_event()` signature changed (removed `flow` parameter)
- `log_sensor_reading()` signature changed (removed `flow` parameter)
- `sensor_reading` signal dict format changed (removed "flow1" and "flow2" keys)

Any code calling these methods or accessing these attributes will need to be updated.

## Summary

Flow rate monitoring has been **completely removed** from KineticManager. The class now focuses exclusively on:
- ✓ Temperature sensing (CH1 and CH2)
- ✓ Device temperature monitoring
- ✓ Valve control
- ✓ Injection timing
- ✓ Event logging (timestamps, temps, device temps only)

All flow-related buffers, parameters, and return values have been eliminated.
