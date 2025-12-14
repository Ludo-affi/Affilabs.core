# KNX Kinetic System Hardware Reference

## Overview

The KNX Kinetic System is the valve control subsystem for the SPR (Surface Plasmon Resonance) spectrometer. It manages sample injection, flow routing, and temperature monitoring for dual-channel operation.

## Quick Reference Table

| Component | Manufacturer | Model | Voltage | Product Link |
|-----------|--------------|-------|---------|--------------|
| **Six-Port Valve** | Takasago Electric | Low Pressure 2-Position 6-Port Valve | [TBD] | [Link](https://www.takasago-fluidics.com/products/2position-6port-valve?variant=37040799285414) |
| **Three-Way Valve** | The Lee Company | XOVER 2/3-Way Isolation Solenoid Valve | 24V DC | [Link](https://www.theleeco.com/product/xover-2-3-way-isolation-solenoid-valve/) |
| **Temperature Sensors** | Integrated in KNX | - | - | - |
| **KNX Controller** | [TBD] | KNX / KNX2 | [TBD] | - |

## Hardware Components

### 1. Six-Port Valve (Takasago Electric)

**Manufacturer:** Takasago Electric  
**Model:** Low Pressure 2-Position 6-Port Valve  
**Product Page:** https://www.takasago-fluidics.com/products/2position-6port-valve?variant=37040799285414

#### Specifications
- **Positions:** 2 (Load / Inject)
- **Ports:** 6
- **Pressure Rating:** Low pressure
- **Application:** Sample injection switching

#### Port Configuration
```
Position 0 (LOAD):
  - Sample loop is connected to inlet
  - Sample is loaded into loop
  - Flow cell receives buffer flow

Position 1 (INJECT):
  - Sample loop is connected to flow cell
  - Sample is injected from loop
  - Flow cell receives sample
```

#### Control
- **Method:** `kinetic_manager.set_six_port_valve(channel, position)`
- **Channel:** "CH1" or "CH2"
- **Position Values:**
  - `0` = LOAD position (filling sample loop)
  - `1` = INJECT position (injecting sample to flow cell)

#### Usage Example
```python
# Load sample into loop
kinetic_manager.set_six_port_valve("CH1", 0)  # LOAD

# Inject sample to flow cell
kinetic_manager.set_six_port_valve("CH1", 1)  # INJECT
```

#### Maintenance Notes
- Check for leaks at port connections
- Verify smooth switching between positions
- Typical lifetime: [Add based on manufacturer specs]
- Replacement part number: [Add when known]

---

### 2. Three-Way Valve (The Lee Company)

**Manufacturer:** The Lee Company  
**Model:** XOVER 2/3-Way Isolation Solenoid Valve  
**Voltage:** 24V  
**Product Page:** https://www.theleeco.com/product/xover-2-3-way-isolation-solenoid-valve/

#### Specifications
- **Type:** Solenoid-actuated isolation valve
- **Positions:** 2 (Waste / Load)
- **Voltage:** 24V DC
- **Function:** Flow direction control
- **Application:** Directing flow to waste or sample loading

#### Operation
```
Position 0 (WASTE):
  - Flow is directed to waste
  - Used for priming, flushing, and disposal
  - De-energized state (solenoid OFF)

Position 1 (LOAD):
  - Flow is directed to sample loop
  - Used for sample loading and injection
  - Energized state (solenoid ON)
```

#### Control
- **Method:** `kinetic_manager.set_three_way_valve(channel, position)`
- **Channel:** "CH1" or "CH2"
- **Position Values:**
  - `0` = WASTE position (flow to waste, solenoid OFF)
  - `1` = LOAD position (flow to sample loop, solenoid ON)

#### Usage Example
```python
# Send flow to waste
kinetic_manager.set_three_way_valve("CH1", 0)  # WASTE

# Direct flow to sample loop
kinetic_manager.set_three_way_valve("CH1", 1)  # LOAD
```

#### Maintenance Notes
- Verify 24V power supply is stable
- Check solenoid actuation (audible click when switching)
- Test for leaks at all ports
- Clean valve body periodically to prevent particle buildup
- Typical lifetime: [Add based on manufacturer specs or operational experience]
- Replacement part number: [Add specific Lee Company part number]

---

### 3. Combined Valve States

The KNX system coordinates both valves to create four distinct operational states:

#### WASTE (Default/Safe State)
- **3-way:** Position 0 (Waste)
- **6-port:** Position 0 (Load)
- **Flow Path:** Pump → Waste
- **Purpose:** Priming, flushing, cleaning

#### LOAD (Sample Loading)
- **3-way:** Position 1 (Load)
- **6-port:** Position 0 (Load)
- **Flow Path:** Pump → Sample Loop → Flow Cell
- **Purpose:** Loading sample into injection loop

#### INJECT (Sample Injection)
- **3-way:** Position 1 (Load)
- **6-port:** Position 1 (Inject)
- **Flow Path:** Pump → Flow Cell (with sample from loop)
- **Purpose:** Injecting sample into flow cell

#### DISPOSE (Unusual State)
- **3-way:** Position 0 (Waste)
- **6-port:** Position 1 (Inject)
- **Flow Path:** Mixed state (typically avoided)
- **Purpose:** Transition state only

#### State Diagram
```
       WASTE                    LOAD
    (3:0, 6:0)  ←─────────→  (3:1, 6:0)
         ↕                        ↕
    DISPOSE                   INJECT
    (3:0, 6:1)  ←─────────→  (3:1, 6:1)
    
Legend: (3:X, 6:Y) = 3-way position X, 6-port position Y
```

---

### 4. Temperature Sensors

**Integration:** Built into KNX controller hardware  
**Type:** Likely thermistor or RTD-based

#### Specifications
- **Channels:** 2 (CH1 and CH2)
- **Range:** Validated between 5°C and 75°C
- **Accuracy:** [Add based on calibration data]
- **Sampling Rate:** Configurable (default: every 10 seconds)

#### Monitored Temperatures
1. **Channel Temperature (CH1/CH2)**
   - Location: Sample flow cell
   - Purpose: Monitor sample temperature during experiment
   - Critical for: Temperature-dependent binding kinetics

2. **Device Temperature**
   - Location: KNX controller hardware
   - Purpose: Hardware thermal monitoring
   - Critical for: Detecting overheating, ensuring stable operation

#### Control
```python
# Read temperature for a channel
reading = kinetic_manager.read_sensor("CH1")
if reading and reading.is_valid():
    temperature = reading.temperature  # °C

# Get averaged reading (rolling average of last 10 readings)
avg_temp = kinetic_manager.get_averaged_sensor_reading("CH1")

# Read device temperature
device_temp = kinetic_manager.read_device_temperature()
```

---

## KNX Controller Hardware

### Supported Controllers

1. **KineticController (KNX)**
   - Standard KNX controller
   - Supports single channel operation
   
2. **KNX2**
   - Dual-channel KNX controller
   - Supports independent CH1 and CH2 operation
   
3. **PicoKNX2** (Obsolete)
   - Legacy Raspberry Pi Pico-based controller
   - No longer supported in KineticManager
   - Use KNX or KNX2 for new installations

### Control Protocol

The KNX controller uses serial communication with the following commands:

#### Command Reference

```python
# Three-way valve control
knx.knx_three(position, channel)
# position: 0 (waste) or 1 (load)
# channel: 1 (CH1), 2 (CH2), or 3 (both when synced)

# Six-port valve control
knx.knx_six(position, channel)
# position: 0 (load) or 1 (inject)
# channel: 1 (CH1), 2 (CH2), or 3 (both when synced)

# Status query (temperature and valve positions)
status = knx.knx_status(channel)
# Returns: dict with 'temp' key (and possibly valve positions)
# channel: 1 (CH1) or 2 (CH2)
```

---

## Dual-Channel Operation

### Independent Mode (Default)
- CH1 and CH2 operate independently
- Commands sent individually to each channel
- Allows different samples on each channel

### Synchronized Mode
- CH1 controls both channels simultaneously
- Commands to CH1 are mirrored to CH2
- Useful for: Duplicate experiments, reference/sample comparison

```python
# Enable sync mode
kinetic_manager.enable_sync()

# Now CH1 commands affect both channels
kinetic_manager.set_six_port_valve("CH1", 1)
# Both CH1 and CH2 switch to INJECT

# Disable sync mode
kinetic_manager.disable_sync()
```

---

## Injection Sequence

### Typical Injection Protocol

```python
# 1. Start with LOAD position
kinetic_manager.set_three_way_valve("CH1", 1)  # Load
kinetic_manager.set_six_port_valve("CH1", 0)   # Load
# State: LOAD - Sample is loaded into loop

# 2. Start injection
kinetic_manager.start_injection("CH1", flow_rate=0.02, auto_timeout=True)
# Automatically switches to INJECT
# Calculates timeout: (100 seconds / 0.02 ml/min) + 2 min = 83.3 min
# State: INJECT - Sample flows from loop to flow cell

# 3. Wait for injection to complete (manual or auto)
# Manual:
kinetic_manager.end_injection("CH1")
# State returns to LOAD

# Auto timeout will call end_injection automatically
```

### Injection Timing

The injection timeout is calculated as:
```
timeout = (BASE_TIME / flow_rate) + SAFETY_MARGIN
where:
  BASE_TIME = 100 seconds
  SAFETY_MARGIN = 2 minutes
  flow_rate = ml/min
```

Example:
- Flow rate = 0.02 ml/min
- Timeout = (100s / 60s/min / 0.02) + 2 = 83.3 + 2 = 85.3 minutes

---

## Safety Features

### 1. Sensor Pause During Valve Movement
- Sensor reading is automatically paused when valves are moving
- Prevents invalid readings during transitions
- Automatically resumes after valve command completes

### 2. Valve Position Verification
```python
# Verify valve reached expected position within timeout
success = kinetic_manager.verify_valve_position(
    channel="CH1",
    expected_3way=1,
    expected_6port=1,
    timeout=5.0  # seconds
)
```

### 3. Graceful Shutdown
```python
# Safe shutdown procedure
kinetic_manager.shutdown()
# - Stops all injection timers
# - Returns all valves to safe LOAD position (3-way:1, 6-port:0)
# - Clears all buffers
```

### 4. Error Handling
- All valve commands wrapped in try-except blocks
- Errors logged and emitted via Qt signals
- Failed commands return False (no exception raised)

---

## Wiring and Connections

### Physical Connections

```
[Pump] → [3-Way Valve] → [6-Port Valve] → [Flow Cell] → [Waste]
                ↓              ↓
            [Waste]      [Sample Loop]

Channel 1:
- 3-way valve CH1
- 6-port valve CH1
- Temperature sensor CH1
- Flow cell CH1

Channel 2 (if present):
- 3-way valve CH2
- 6-port valve CH2
- Temperature sensor CH2
- Flow cell CH2
```

### Electrical Connections
- **Valve control:** Via KNX controller serial interface
- **Temperature sensors:** Integrated into KNX hardware
- **Power Requirements:**
  - Three-Way Valve (Lee XOVER): 24V DC
  - Six-Port Valve (Takasago): [Add voltage/current specifications]
  - KNX Controller: [Add voltage/current specifications]
  - Total power budget: [Calculate based on all components]

---

## Troubleshooting

### Valve Not Responding
1. Check KNX controller connection
2. Verify `kinetic_manager.is_available()` returns True
3. Check device type with `kinetic_manager.get_device_type()`
4. Review error logs for exceptions
5. Test manual valve control via controller interface

### Temperature Reading Issues
1. Verify sensor reading is not paused (`is_sensor_paused()`)
2. Check temperature is within valid range (5-75°C)
3. Clear buffers and restart: `kinetic_manager.clear_sensor_buffers()`
4. Check hardware connections to temperature sensors

### Injection Not Completing
1. Verify valve reached INJECT position
2. Check flow rate setting (affects timeout calculation)
3. Review injection timer status
4. Check pump operation (separate from KineticManager)
5. Manually end injection if needed: `end_injection(channel)`

### Sync Mode Issues
1. Verify sync is enabled: `kinetic_manager.is_synced()`
2. Check both channels have hardware available
3. Review channel states: `kinetic_manager.get_all_states()`
4. Manually sync states: `kinetic_manager.sync_channel_states()`

---

## Maintenance Schedule

### Daily
- Visual inspection of valve connections
- Check for leaks at ports
- Verify temperature readings are reasonable

### Weekly
- Flush all channels with cleaning solution
- Cycle all valves through full range
- Check event logs for errors

### Monthly
- Clean flow cells
- Inspect valve seals
- Calibrate temperature sensors (if needed)
- Review and archive event logs

### Annually
- Professional service of valves
- Replace worn seals and O-rings
- Full system calibration
- Update firmware (if available)

---

## Replacement Parts

### Six-Port Valve (Takasago)
- **Order from:** Takasago Electric website
- **Product link:** https://www.takasago-fluidics.com/products/2position-6port-valve?variant=37040799285414
- **Lead time:** [Add based on vendor]
- **Cost:** [Add when known]

### Three-Way Valve (Lee XOVER)
- **Manufacturer:** The Lee Company
- **Model:** XOVER 2/3-Way Isolation Solenoid Valve (24V)
- **Order from:** The Lee Company website
- **Product link:** https://www.theleeco.com/product/xover-2-3-way-isolation-solenoid-valve/
- **Voltage:** 24V DC
- **Part number:** [Add specific part number from Lee Company]
- **Lead time:** [Add based on vendor]
- **Cost:** [Add when known]

### Temperature Sensors
- **Type:** [Add]
- **Part number:** [Add]
- **Order from:** [Add]

### KNX Controller
- **Contact:** [Add supplier information]
- **Compatibility:** Ensure firmware supports KNX or KNX2 protocol

---

## Software Integration

### KineticManager API
All hardware control is abstracted through the `KineticManager` class.

**Location:** `utils/kinetic_manager.py`

**Key Methods:**
```python
# Valve control
set_three_way_valve(channel, position)
set_six_port_valve(channel, position)
toggle_three_way_valve(channel)
toggle_six_port_valve(channel)

# State queries
get_valve_position(channel) -> ValvePosition
get_valve_position_name(channel) -> str
get_channel_state(channel) -> ChannelState

# Temperature
read_sensor(channel) -> SensorReading | None
get_averaged_sensor_reading(channel) -> str
read_device_temperature() -> float | None

# Injection
start_injection(channel, flow_rate, auto_timeout=True)
end_injection(channel)
get_injection_time(channel) -> float

# Sync
enable_sync()
disable_sync()
is_synced() -> bool

# Logging
log_event(channel, event, temp="-", dev="-")
get_log(channel) -> KineticLog
clear_log(channel)
```

### Qt Signals
```python
valve_state_changed = Signal(str, str)    # channel, position_name
sensor_reading = Signal(dict)              # {"temp1": str, "temp2": str}
device_temp_updated = Signal(str, str)    # temperature, source
injection_started = Signal(str, float)    # channel, exp_time
injection_ended = Signal(str)             # channel
error_occurred = Signal(str, str)         # channel, error_message
```

---

## Version History

### v1.0 (Current)
- Flow rate monitoring removed (obsolete)
- Temperature-only sensor reading
- Dual-channel operation (KNX2)
- Synchronized mode
- Auto-timeout injection
- Comprehensive event logging

### v0.x (Legacy)
- Flow rate and temperature monitoring
- PicoKNX2 support (now removed)
- Basic valve control

---

## References

1. **Takasago Electric - Six-Port Valve:**  
   https://www.takasago-fluidics.com/products/2position-6port-valve?variant=37040799285414

2. **The Lee Company - Three-Way Valve (XOVER):**  
   https://www.theleeco.com/product/xover-2-3-way-isolation-solenoid-valve/

3. **KineticManager Documentation:**  
   See `KINETIC_MANAGER_IMPLEMENTATION.md`

4. **Hardware Setup Guide:**  
   [Add link to setup/installation documentation]

5. **Calibration Procedures:**  
   [Add link to calibration documentation]

---

## Contact Information

**Hardware Support:**  
[Add contact information for hardware vendor]

**Software Support:**  
[Add contact information for software maintenance]

**Emergency Contact:**  
[Add emergency support contact]

---

**Document Version:** 1.0  
**Last Updated:** October 7, 2025  
**Author:** [Your name/team]  
**Next Review Date:** [Schedule regular reviews]
