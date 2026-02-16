# Pump & Valve System Documentation

## Overview

The Affilabs.core SPR system uses a combination of **precision syringe pumps** and **electronically-controlled valves** to deliver precise fluid flow to the sensor surface. The system supports two pump configurations: external dual syringe pumps (AffiPump) and internal peristaltic pumps (P4PROPLUS).

**Key Features:**
- **Dual-channel flow**: Independent control of KC1 and KC2 kinetic channels
- **Multi-valve routing**: 6-port and 3-way valves for complex fluid paths
- **Volume-based injection**: Precise aspirate/dispense with microfluidic control
- **Contact time injection**: 30-second timed injection sequences
- **Channel routing**: A/B/C/D channel selection via valve switching

---

## System Architecture

### Two Pump Configurations

```
┌─────────────────────────────────────────────────────────┐
│           CONFIGURATION 1: AffiPump (External)          │
│  • Hardware: 2× Tecan Cavro Centris syringe pumps       │
│  • Connection: FTDI USB-to-Serial (COM8)                │
│  • Volume: 1000 µL per syringe (5000 µL optional)       │
│  • Protocol: Cavro XP3000 command set (38400 baud)      │
│  • Valves: Each pump has 6-port valve for routing       │
└─────────────────────────────────────────────────────────┘
                           OR
┌─────────────────────────────────────────────────────────┐
│        CONFIGURATION 2: P4PROPLUS (Internal)            │
│  • Hardware: 3× peristaltic pumps (firmware V2.3+)      │
│  • Connection: Integrated via P4PROPLUS controller      │
│  • Flow: Continuous flow at 5-220 RPM                   │
│  • Channels: Pump 1, Pump 2, or Both synced             │
│  • Valves: 6-port valves for KC1/KC2 injection          │
└─────────────────────────────────────────────────────────┘
```

### Valve Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     VALVE SYSTEM                         │
│                                                          │
│  ┌─────────────────┐          ┌─────────────────┐      │
│  │   6-PORT VALVE  │          │   3-WAY VALVE    │      │
│  │    (KC1 & KC2)  │          │   (KC1 & KC2)    │      │
│  └─────────────────┘          └─────────────────┘      │
│                                                          │
│  • LOAD/INJECT     • OPEN/CLOSED                        │
│  • Sample loop     • Channel routing                    │
│  • Position 0/1    • A ↔ B, C ↔ D                       │
└─────────────────────────────────────────────────────────┘
```

---

## Pump Types

### 1. AffiPump (Tecan Cavro Centris Syringe Pumps)

#### Hardware Specifications

- **Manufacturer**: Tecan (Cavro brand)
- **Model**: Centris™ Syringe Pump
- **Quantity**: 2 pumps (KC1, KC2)
- **Syringe Volume**: 1000 µL standard (5000 µL configurable)
- **Resolution**: 48,000 steps per syringe (0.021 µL/step @ 1000µL)
- **Flow Rate Range**: 0.001 - 24,000 µL/min
- **Accuracy**: ±1% of programmed volume
- **Precision**: ±0.5% CV (coefficient of variation)

#### Communication Interface

- **Protocol**: Cavro XP3000 command set
- **Interface**: FTDI FT232 USB-to-Serial adapter
- **Serial Number**: AP9XLF0GA
- **COM Port**: COM8 (Windows), `/dev/ttyUSB0` (Linux)
- **Baud Rate**: 38400
- **Data Format**: 8N1 (8 data bits, no parity, 1 stop bit)
- **Flow Control**: None
- **VCP Mode**: Required (Load VCP enabled in FTDI driver)

#### Pump Addresses

- **Pump 1 (KC1)**: `/1` (address byte: `0x42`)
- **Pump 2 (KC2)**: `/2` (address byte: `0x43`)
- **Broadcast**: `/A` (address byte: `0x41`) - both pumps simultaneously

#### Command Examples

```python
# Initialize pumps (home syringes to zero position)
pump.send_command("/1ZR")  # Initialize KC1
pump.send_command("/2ZR")  # Initialize KC2
pump.send_command("/AZR")  # Initialize both (broadcast)

# Aspirate 500 µL at 1000 µL/min
# P = Absolute position (in steps)
# S = Speed (in steps/sec)
pump.send_command("/1A24000R")  # Move to 500µL position (24000 steps)
pump.send_command("/1V1000R")   # Set speed to 1000 µL/min

# Dispense to waste
pump.send_command("/1A0R")      # Return to zero position (dispense)

# Set valve to INJECT position
pump.send_command("/1OR")       # Output port (INJECT)
pump.send_command("/1IR")       # Input port (LOAD)
```

#### Valve Configuration

Each Cavro pump includes an integrated 6-port distribution valve:

| Port | Function | Position Code |
|------|----------|---------------|
| I | INPUT (aspirate from sample) | `I` |
| O | OUTPUT (dispense to sensor) | `O` |
| B | BYPASS (optional waste) | `B` |
| E | EXTRA (optional buffer) | `E` |

**Typical Workflow:**
1. Valve → INPUT (load sample)
2. Aspirate sample from vial
3. Valve → OUTPUT (inject to sensor)
4. Dispense sample through flow cell

#### File References

- **Controller**: `AffiPump/affipump_controller.py` (500+ lines)
- **Manager**: `AffiPump/__init__.py` → `CavroPumpManager`
- **HAL**: `affilabs/utils/hal/pump_hal.py` → `AffipumpAdapter`
- **Commands**: `AffiPump/COMMANDS.md` (Cavro protocol reference)

---

### 2. P4PROPLUS Internal Pumps (Peristaltic)

#### Hardware Specifications

- **Type**: Peristaltic pumps
- **Quantity**: 3 channels (Pump 1, Pump 2, Both synced)
- **RPM Range**: 5 - 220 RPM (firmware enforced)
- **Flow Type**: Continuous (not volume-based)
- **Tubing**: Standard peristaltic tubing (size TBD)
- **Firmware Requirement**: V2.3+ (P4PROPLUS)

#### Control Channels

| Channel | Description | Use Case |
|---------|-------------|----------|
| **1** | Pump 1 only | Independent KC1 control |
| **2** | Pump 2 only | Independent KC2 control |
| **3** | Both pumps synchronized | Dual-channel experiments |

#### Serial Commands

**Start Pump:**
```
Format: pr{channel}{rpm:04d}\n

Examples:
  pr10050\n  → Pump 1 at 50 RPM
  pr20100\n  → Pump 2 at 100 RPM
  pr30075\n  → Both pumps at 75 RPM (synced)

Response: None (no ACK from firmware)
Delay: 150ms required between commands
```

**Stop Pump:**
```
Format: ps{channel}\n

Examples:
  ps1\n  → Stop pump 1
  ps2\n  → Stop pump 2
  ps3\n  → Stop both pumps

Response: None
Delay: 150ms
```

#### RPM Correction Factor

The UI includes a correction factor spinbox to compensate for tubing wear or calibration drift:

```python
actual_rpm = base_rpm * correction_factor

# Example:
# Base RPM: 100
# Correction: 1.05
# Actual RPM sent to hardware: 105
```

#### Live RPM Updates

Pumps support changing speed while running (no need to stop/restart):

```python
# User changes RPM spinbox while pump running
if pump_running:
    new_rpm = spinbox.value() * correction_factor
    ctrl.pump_start(rate_ul_min=new_rpm, ch=channel)
    # Pump smoothly transitions to new speed
```

#### File References

- **Architecture**: `INTERNAL_PUMP_ARCHITECTURE.md`
- **Controller API**: `affilabs/utils/controller.py` → `pump_start()`, `pump_stop()`
- **UI Builder**: `affilabs/sidebar_tabs/AL_flow_builder.py` → internal pump controls
- **Manager**: `affilabs/managers/pump_manager.py` (1620 lines)

---

## Valve System

### 6-Port Valves (KC1 & KC2)

#### Purpose

Control sample injection from external loop to sensor flow cell.

#### Hardware

- **Type**: 6-port 2-position valve
- **Actuation**: Electronic (solenoid or motor)
- **Channels**: 2 valves (one for KC1, one for KC2)
- **Response Time**: ~100-200ms

#### Positions

| State | Position | Flow Path | Use Case |
|-------|----------|-----------|----------|
| **0** | LOAD | Sample loop isolated | Loading sample, priming |
| **1** | INJECT | Sample loop in-line | Injection to sensor |

#### Control Commands

```python
# Individual valve control
ctrl.knx_six(state=0, ch=1)  # KC1 → LOAD
ctrl.knx_six(state=1, ch=1)  # KC1 → INJECT

ctrl.knx_six(state=0, ch=2)  # KC2 → LOAD
ctrl.knx_six(state=1, ch=2)  # KC2 → INJECT

# Both valves simultaneously
ctrl.knx_six_both(state=0)   # Both → LOAD
ctrl.knx_six_both(state=1)   # Both → INJECT
```

**Command Format:**
```
Format: v6{channel}{state}\n

Examples:
  v611\n  → KC1 valve to INJECT
  v610\n  → KC1 valve to LOAD
  v621\n  → KC2 valve to INJECT
  v620\n  → KC2 valve to LOAD

Response: b"1" on success
```

#### Timeout Feature

Valves can auto-return to LOAD position after a timeout (safety feature):

```python
# Open valve for 30 seconds, then auto-close
ctrl.knx_six(state=1, ch=1, timeout_seconds=30.0)

# Valve opens (INJECT)
# ... 30 seconds pass ...
# Valve automatically closes (LOAD)
```

#### Typical Injection Sequence

```python
# 30-second contact time injection
1. Start pump at desired flow rate
2. Open 6-port valve → INJECT position
   ctrl.knx_six(state=1, ch=1)
3. Wait 30 seconds (contact time)
4. Close 6-port valve → LOAD position
   ctrl.knx_six(state=0, ch=1)
5. Pump continues running (for buffer flow)
```

### 3-Way Valves (KC1 & KC2)

#### Purpose

Route flow between sensor channels (A/B for KC1, C/D for KC2).

#### Hardware

- **Type**: 3-way solenoid valve
- **Channels**: 2 valves (one for KC1, one for KC2)
- **Switch Time**: ~50-100ms

#### Positions

| State | KC1 Routing | KC2 Routing | Description |
|-------|-------------|-------------|-------------|
| **0** | KC1 → A | KC2 → C | CLOSED (default channels) |
| **1** | KC1 → B | KC2 → D | OPEN (alternate channels) |

**Naming Convention:**
- **CLOSED** = Default channels (A, C)
- **OPEN** = Alternate channels (B, D)

#### Control Commands

```python
# Individual 3-way valve control
ctrl.knx_three(state=0, ch=1)  # KC1 → Channel A (CLOSED)
ctrl.knx_three(state=1, ch=1)  # KC1 → Channel B (OPEN)

ctrl.knx_three(state=0, ch=2)  # KC2 → Channel C (CLOSED)
ctrl.knx_three(state=1, ch=2)  # KC2 → Channel D (OPEN)

# Both 3-way valves simultaneously
ctrl.knx_three_both(state=0)   # KC1→A, KC2→C (CLOSED)
ctrl.knx_three_both(state=1)   # KC1→B, KC2→D (OPEN)
```

**Command Format:**
```
Format: v3{channel}{state}\n

Examples:
  v310\n  → KC1 to Channel A (CLOSED)
  v311\n  → KC1 to Channel B (OPEN)
  v320\n  → KC2 to Channel C (CLOSED)
  v321\n  → KC2 to Channel D (OPEN)

  v3B0\n  → Both valves CLOSED (broadcast)
  v3B1\n  → Both valves OPEN (broadcast)

Response: b"1" on success
```

#### Multi-Channel Experiments

3-way valves enable parallel experiments across 4 sensor channels:

```
┌─────────────────────────────────────────────────────┐
│         KC1 (Pump 1)        KC2 (Pump 2)            │
│         ┌────────────┐      ┌────────────┐          │
│         │  3-Way     │      │  3-Way     │          │
│         │  Valve     │      │  Valve     │          │
│         └─┬────┬─────┘      └─┬────┬─────┘          │
│           │    │              │    │                │
│     State=0  State=1    State=0  State=1           │
│           │    │              │    │                │
│           ▼    ▼              ▼    ▼                │
│       Channel A  B         Channel C  D             │
│         (Ref)  (Sample)      (Ref)  (Sample)        │
└─────────────────────────────────────────────────────┘
```

**Typical Configuration:**
- **Channel A**: Reference (buffer only)
- **Channel B**: Sample 1 (KC1 analyte)
- **Channel C**: Reference (buffer only)
- **Channel D**: Sample 2 (KC2 analyte)

---

## Fluid Routing Architecture

### Complete Flow Path (AffiPump Configuration)

```
Sample Vial
     ↓
 [6-Port Valve LOAD]
     ↓
Syringe Pump (aspirate)
     ↓
 [6-Port Valve INJECT]
     ↓
 [3-Way Valve]
    ↙    ↘
Channel A  Channel B  (KC1 paths)
Channel C  Channel D  (KC2 paths)
     ↓
  Sensor
     ↓
  Waste
```

### Pump Priming Sequence (AffiPump)

The `prime_pump()` operation prepares the system by cycling pumps with progressive valve opening:

```
Cycles 1-2: Standard priming
  • 6-port valves: LOAD (closed)
  • 3-way valves: CLOSED (A, C)
  • Action: Aspirate + Dispense buffer through pump

Cycle 3-4: Load valve priming
  • 6-port valves: INJECT (opened)  ← NEW
  • 3-way valves: CLOSED (A, C)
  • Action: Prime sample loop pathway

Cycle 5-6: Full path priming
  • 6-port valves: INJECT
  • 3-way valves: OPEN (B, D)  ← NEW
  • Action: Prime alternate channel routes

Final: Return to safe state
  • 6-port valves: LOAD
  • 3-way valves: CLOSED
```

**Implementation:**
```python
async def prime_pump(cycles=6, volume_ul=1000, ...):
    for cycle in range(1, cycles + 1):
        # Open 6-port valves at cycle 3
        if cycle == 3:
            ctrl.knx_six_both(state=1)  # INJECT

        # Open 3-way valves at cycle 5
        if cycle == 5:
            ctrl.knx_three_both(state=1)  # KC1→B, KC2→D

        # Aspirate-dispense cycle
        pump.aspirate_both(volume_ul, speed)
        await wait_for_completion()

        pump.dispense_both(volume_ul, speed)
        await wait_for_completion()

    # Return to safe position
    ctrl.knx_six_both(state=0)    # LOAD
    ctrl.knx_three_both(state=0)  # CLOSED
```

---

## Pump Operations

### AffiPump Operations

#### Prime Pump

**Purpose**: Fill pumps and tubing with buffer

**Parameters:**
- `cycles`: Number of aspirate-dispense cycles (default: 6)
- `volume_ul`: Volume per cycle (default: 1000 µL)
- `aspirate_speed`: Aspiration rate (default: 24,000 µL/min)
- `dispense_speed`: Dispense rate (default: 5,000 µL/min)

**Workflow:**
1. Initialize pumps to zero position
2. Aspirate buffer from reservoir
3. Dispense buffer to waste
4. Repeat for N cycles
5. Open valves progressively (see priming sequence)
6. Return all valves to safe positions

**Blockage Detection:**
- Monitors completion times for both pumps
- If time difference > 1.5 seconds → blockage detected
- Reports which pump (KC1 or KC2) is blocked
- Automatically homes plungers and aborts

**Example:**
```python
success = await pump_mgr.prime_pump(
    cycles=6,
    volume_ul=1000,
    aspirate_speed=24000,
    dispense_speed=5000
)
```

#### Cleanup Pump

**Purpose**: Remove air bubbles and contaminants

**Phases:**
1. **Pulse Phase**: 10 rapid cycles (200 µL at 24,000 µL/min)
   - Dislodges bubbles
2. **Prime Phase**: 6 standard cycles (1000 µL at 5,000 µL/min)
   - Flushes system

**Example:**
```python
success = await pump_mgr.cleanup_pump(
    pulse_cycles=10,
    prime_cycles=6,
    speed=5000
)
```

#### Run Buffer

**Purpose**: Continuous buffer flow during experiment

**Parameters:**
- `duration_seconds`: How long to run (default: 60)
- `flow_rate_ul_min`: Flow rate (default: 100 µL/min)
- `channel`: Which pump (1, 2, or both)

**Workflow:**
1. Set flow rate
2. Start continuous dispense
3. Run for specified duration
4. Stop pumps

**Example:**
```python
success = await pump_mgr.run_buffer(
    duration_seconds=60,
    flow_rate_ul_min=100
)
```

#### Aspirate/Dispense

**Purpose**: Precise volume-based liquid handling

**Parameters:**
- `pump_address`: 1 (KC1) or 2 (KC2)
- `volume_ul`: Volume in microliters
- `rate_ul_min`: Flow rate in µL/min

**Example:**
```python
# Aspirate 500 µL from sample vial
pump.aspirate(pump_address=1, volume_ul=500, rate_ul_min=1000)

# Wait for completion
pump.wait_until_idle(pump_address=1, timeout_s=60)

# Dispense to sensor
pump.dispense(pump_address=1, volume_ul=500, rate_ul_min=500)
```

### P4PROPLUS Operations

#### Start/Stop Pump

**Individual Pump:**
```python
# Start pump 1 at 100 RPM (with 1.05 correction factor)
rpm_corrected = 100 * 1.05  # = 105 RPM
ctrl.pump_start(rate_ul_min=rpm_corrected, ch=1)

# Stop pump 1
ctrl.pump_stop(ch=1)
```

**Synced Pumps:**
```python
# Start both pumps at same speed
ctrl.pump_start(rate_ul_min=75, ch=3)

# Stop both pumps
ctrl.pump_stop(ch=3)
```

#### 30-Second Injection

**Purpose**: Timed sample injection with contact time

**Workflow:**
```python
# 1. Start pumps
ctrl.pump_start(rate_ul_min=100, ch=1)

# 2. Open valve (begin injection)
ctrl.knx_six(state=1, ch=1)

# 3. Wait 30 seconds (contact time)
await asyncio.sleep(30)

# 4. Close valve (end injection, buffer continues)
ctrl.knx_six(state=0, ch=1)

# 5. User stops pump manually when ready
```

**Valve Sync Mode:**
- **Sync OFF**: Only KC1 valve opens
- **Sync ON**: Both KC1 and KC2 valves open

---

## Hardware Abstraction Layer (HAL)

### PumpHAL Protocol

**File**: `affilabs/utils/hal/pump_hal.py`

Unified interface for both pump types:

```python
class PumpHAL(Protocol):
    # Low-level
    def send_command(address: int, command: bytes) -> bytes
    def is_available() -> bool

    # High-level
    def initialize_pumps() -> bool
    def aspirate(pump_address, volume_ul, rate_ul_min) -> bool
    def dispense(pump_address, volume_ul, rate_ul_min) -> bool
    def set_valve_position(pump_address, port) -> bool
    def get_syringe_position(pump_address) -> int | None
    def wait_until_idle(pump_address, timeout_s) -> bool

    # Connection
    def close() -> None
```

### AffipumpAdapter

Wraps `CavroPumpManager` to provide consistent HAL interface:

```python
from affilabs.utils.hal.pump_hal import create_pump_hal
from affipump import CavroPumpManager, PumpController

# Connect to hardware
controller = PumpController.from_first_available()
manager = CavroPumpManager(controller)

# Wrap with HAL
pump = create_pump_hal(manager)

# Use unified interface
pump.initialize_pumps()
pump.aspirate(1, 100.0, 500.0)
```

---

## Device Detection & Configuration

### Hardware Manager Detection

**File**: `affilabs/core/hardware_manager.py`

#### AffiPump Detection

```python
def _connect_pump():
    # Scan for FTDI serial interface
    controller = PumpController.from_first_available()

    if controller:
        # FTDI found (VID:0x0403, PID:0x6001, SN:AP9XLF0GA)
        manager = CavroPumpManager(controller)
        pump = create_pump_hal(manager)
        logger.info("✅ AffiPump connected - 2x Tecan Cavro Centris")
    else:
        pump = None
        logger.info("❌ No FTDI pump controller found")
```

#### Internal Pumps Detection

```python
def _get_controller_type():
    firmware_id = ctrl.get_firmware_id()

    if 'p4proplus' in firmware_id.lower():
        return "P4PROPLUS"  # Has internal pumps
    else:
        return "P4PRO"      # No internal pumps
```

### Device Status Display

**File**: `affilabs/widgets/device_status.py`

```python
# Hardware list
if controller_type == "P4PROPLUS":
    hardware_items.append("• P4PROPLUS (with internal pumps)")
elif pump_connected and not has_internal_pumps:
    hardware_items.append("• AffiPump (external)")

# Flow mode indicator
FLOW_CONTROLLERS = ["PicoKNX2", "PicoEZSPR", "EZSPR", "P4PROPLUS"]
if controller_type in FLOW_CONTROLLERS:
    flow_indicator = "🟢 Flow Mode"
```

---

## UI Controls

### AffiPump Controls (Flow Tab)

**File**: `affilabs/sidebar_tabs/AL_flow_builder.py`

#### Pump Control Section

- **Prime Pump Button**: Triggers `prime_pump(cycles=6)`
- **Cleanup Pump Button**: Triggers `cleanup_pump()`
- **Run Buffer Button**: Starts continuous flow
- **Progress Bar**: Shows operation progress (0-100%)
- **Status Label**: Displays current operation and errors

#### Valve Control Section

- **Loop Valve (6-Port)**: Toggle buttons for KC1/KC2
  - LOAD button → `knx_six(state=0)`
  - INJECT button → `knx_six(state=1)`

- **Channel Valve (3-Way)**: Toggle buttons for KC1/KC2
  - CLOSED button → `knx_three(state=0)` (KC1→A, KC2→C)
  - OPEN button → `knx_three(state=1)` (KC1→B, KC2→D)

### P4PROPLUS Controls (Flow Tab)

#### Pump 1 Controls

- **Toggle Button**: Start/Stop pump 1 (channel 1)
- **RPM Spinbox**: Set base RPM (5-220)
- **Correction Spinbox**: Calibration factor (0.8-1.2)
- **Live Update**: Changes RPM while running

#### Pump 2 Controls

- **Toggle Button**: Start/Stop pump 2 (channel 2)
- **RPM Spinbox**: Set base RPM (5-220)
- **Correction Spinbox**: Calibration factor (0.8-1.2)
- **Live Update**: Changes RPM while running

#### Synced Controls

- **Sync Toggle Button**: Enable/disable pump synchronization
- **Synced Toggle Button**: Start/Stop both pumps (channel 3)
- **RPM Spinbox**: Set synchronized RPM
- **Correction Spinbox**: Global correction factor

#### Injection Button

- **30s Inject Button**: Timed injection sequence
  - Starts pumps
  - Opens valve(s)
  - Waits 30 seconds
  - Closes valve(s)
  - Pumps continue running

---

## Calibration & Maintenance

### AffiPump Calibration

#### Pump Timing Calibration

**Purpose**: Verify actual flow rates match programmed rates

**File**: `affilabs/ui/pump_timing_calibration_dialog.py`

**Procedure:**
1. Place known volume in graduated cylinder
2. Run pump at test flow rate
3. Measure actual time to dispense volume
4. Calculate correction factor:
   ```
   correction = programmed_time / actual_time
   ```
5. Store correction in EEPROM or config file

**Example:**
```python
# Program 1000 µL at 1000 µL/min (should take 60 seconds)
programmed_time = 60.0
actual_time = 62.3  # Measured with stopwatch

correction = 60.0 / 62.3 = 0.963

# Apply correction
corrected_rate = 1000 * 0.963 = 963 µL/min
```

#### Pump Volume Calibration

**Purpose**: Calibrate syringe volume and step conversion

**File**: `affilabs/ui/pump_calibration_dialog.py`

**Procedure:**
1. Dispense known number of steps
2. Measure actual volume delivered
3. Calculate µL per step:
   ```
   ul_per_step = measured_volume / steps
   ```
4. Update syringe size setting

### P4PROPLUS Calibration

#### RPM Correction Factor

**Purpose**: Compensate for tubing wear or age

**Procedure:**
1. Run pump at 100 RPM
2. Measure actual flow rate (mL/min)
3. Calculate correction:
   ```
   correction = target_flow / measured_flow
   ```
4. Set correction in UI spinbox

**Example:**
```python
# Target: 100 RPM should deliver 5.0 mL/min
# Measured: Actually delivers 4.8 mL/min

correction = 5.0 / 4.8 = 1.042

# New setting: 100 RPM × 1.042 = 104.2 RPM sent to hardware
```

### Valve Testing

**Purpose**: Verify valve switching and positioning

**File**: `test_valves.py`

**Procedure:**
```python
# Test 6-port valves
ctrl.knx_six(0, 1)  # KC1 → LOAD
time.sleep(1)
ctrl.knx_six(1, 1)  # KC1 → INJECT
time.sleep(1)
ctrl.knx_six(0, 1)  # KC1 → LOAD (return)

# Test 3-way valves
ctrl.knx_three(0, 1)  # KC1 → Channel A
time.sleep(1)
ctrl.knx_three(1, 1)  # KC1 → Channel B
time.sleep(1)
ctrl.knx_three(0, 1)  # KC1 → Channel A (return)
```

---

## Error Handling

### AffiPump Errors

#### Blockage Detection

```python
# During aspirate/dispense, monitor completion times
p1_time = 5.2  # Pump 1 took 5.2 seconds
p2_time = 7.8  # Pump 2 took 7.8 seconds

time_diff = abs(p1_time - p2_time)  # 2.6 seconds

if time_diff > 1.5:  # Threshold for blockage
    blocked_pump = "KC2" if p1_time > p2_time else "KC1"
    logger.error(f"Blockage detected in {blocked_pump}")
    await home_plungers()  # Emergency recovery
```

#### Communication Timeouts

```python
try:
    response = pump.send_command("/1ZR")
    if not response:
        raise TimeoutError("Pump did not respond")
except serial.SerialTimeoutException:
    logger.error("Serial communication timeout")
    logger.info("Check: USB cable, pump power, COM port")
```

#### Initialization Failures

```python
success = pump.initialize_pumps()
if not success:
    logger.warning("Pump initialization failed")
    logger.info("Common causes:")
    logger.info("  - Pump already initialized")
    logger.info("  - Mechanical obstruction")
    logger.info("  - Syringe not seated properly")
```

### P4PROPLUS Errors

#### No Acknowledgment

P4PROPLUS firmware does not send ACK for pump commands:

```python
# Pump commands return True even without ACK
ctrl.pump_start(rate_ul_min=100, ch=1)  # Always returns True
ctrl.pump_stop(ch=1)                    # Always returns True

# Valve commands DO return ACK
response = ctrl.knx_six(state=1, ch=1)  # Returns True if b"1" received
if not response:
    logger.error("Valve command failed - no ACK")
```

#### RPM Out of Range

```python
rpm = 250  # Too high (max is 220)

if rpm < 5 or rpm > 220:
    logger.error(f"RPM {rpm} out of range (5-220)")
    rpm = max(5, min(220, rpm))  # Clamp to valid range
```

#### Signal Loop Prevention

```python
# WRONG: Creates infinite loop
btn.setChecked(False)  # Triggers toggled signal → calls handler again

# CORRECT: Block signals during programmatic changes
btn.blockSignals(True)
btn.setChecked(False)
btn.blockSignals(False)
```

---

## Threading & Async

### Background Threading (P4PROPLUS)

**Problem**: Serial commands (150ms delay) block UI

**Solution**: QRunnable background tasks

```python
class PumpStartTask(QRunnable):
    def __init__(self, ctrl, rpm, ch, callback):
        self.ctrl = ctrl
        self.rpm = rpm
        self.ch = ch
        self.callback = callback

    def run(self):
        success = self.ctrl.pump_start(rate_ul_min=self.rpm, ch=self.ch)
        self.callback(success)

# Usage
task = PumpStartTask(ctrl, rpm=100, ch=1, callback=on_complete)
QThreadPool.globalInstance().start(task)

# UI remains responsive during 150ms serial command
```

### Async Operations (AffiPump)

**Prime/Cleanup Operations:**

```python
async def prime_pump(self, cycles=6, volume_ul=1000, ...):
    for cycle in range(1, cycles + 1):
        # Aspirate (blocking call in executor)
        pump.aspirate_both(volume_ul, speed)

        # Wait for completion (async)
        ready = await asyncio.get_event_loop().run_in_executor(
            None,
            pump.wait_until_both_ready,
            60.0  # timeout
        )

        if not ready:
            logger.error("Timeout waiting for pumps")
            return False

    return True
```

**Calling from UI:**

```python
# In main.py signal handlers
async def _on_prime_pump_clicked(self):
    success = await self.pump_mgr.prime_pump(cycles=6)
    if success:
        logger.info("✅ Prime completed")
    else:
        logger.error("❌ Prime failed")

# Connect button to async handler
prime_btn.clicked.connect(lambda: asyncio.create_task(_on_prime_pump_clicked()))
```

---

## Signal Architecture

### Pump Manager Signals

**File**: `affilabs/managers/pump_manager.py`

```python
class PumpManager(QObject):
    # Progress tracking
    operation_started = Signal(str)              # operation_name
    operation_progress = Signal(str, int, str)   # operation, percent, message
    operation_completed = Signal(str, bool)      # operation_name, success

    # Status updates
    status_updated = Signal(str, float, float, float, float)
    # status, flow_rate, plunger_pos, contact_time_current, contact_time_expected

    # Errors
    error_occurred = Signal(str, str)  # operation_name, error_message
```

**Example Connection:**

```python
# In Flow Tab UI builder
pump_mgr.operation_started.connect(self._on_pump_operation_started)
pump_mgr.operation_progress.connect(self._update_progress_bar)
pump_mgr.operation_completed.connect(self._on_pump_operation_complete)
pump_mgr.error_occurred.connect(self._show_pump_error)

def _update_progress_bar(operation, percent, message):
    self.progress_bar.setValue(percent)
    self.status_label.setText(f"{operation}: {message}")
```

---

## Testing & Diagnostics

### Standalone Test Scripts

#### Pump Control Test

**File**: `test_pump_control.py`

Interactive pump control for manual testing:

```bash
python test_pump_control.py

> Commands:
  a1 500 1000  → Aspirate 500µL on Pump 1 at 1000µL/min
  d2 500 500   → Dispense 500µL on Pump 2 at 500µL/min
  ab 1000 1000 → Aspirate both pumps
  db 1000 500  → Dispense both pumps
  i1           → Initialize Pump 1
  v1 input     → Set Pump 1 valve to INPUT
  s            → Show status
  q            → Quit
```

#### Valve Test

**File**: `test_valves.py`

Automated valve testing:

```bash
python test_valves.py

Testing 6-port valves...
  KC1 → LOAD: ✓
  KC1 → INJECT: ✓
  KC1 → LOAD: ✓

  KC2 → LOAD: ✓
  KC2 → INJECT: ✓
  KC2 → LOAD: ✓

Testing 3-way valves...
  KC1 → Channel A: ✓
  KC1 → Channel B: ✓
  KC1 → Channel A: ✓

  KC2 → Channel C: ✓
  KC2 → Channel D: ✓
  KC2 → Channel C: ✓
```

#### Valve Control UI

**File**: `valve-control-ui.py`

Simple Tkinter GUI for valve testing:

```bash
python valve-control-ui.py

# Shows:
  [KC1 - 6-Port Valve]
    [INJECT (Open)]  [LOAD (Close)]
    State: LOAD

  [KC2 - 6-Port Valve]
    [INJECT (Open)]  [LOAD (Close)]
    State: LOAD
```

### Diagnostic Commands

#### AffiPump Status Check

```python
# Check pump positions
pos1 = pump.get_syringe_position(pump_address=1)
pos2 = pump.get_syringe_position(pump_address=2)

logger.info(f"KC1: {pos1} steps ({pos1 * 0.021:.1f} µL)")
logger.info(f"KC2: {pos2} steps ({pos2 * 0.021:.1f} µL)")

# Check valve positions
valve1 = pump.get_valve_position(pump_address=1)
valve2 = pump.get_valve_position(pump_address=2)

logger.info(f"KC1 valve: {valve1}")  # 'I', 'O', 'B', 'E'
logger.info(f"KC2 valve: {valve2}")
```

#### P4PROPLUS Status Check

```python
# Check if internal pumps available
has_pumps = ctrl.has_internal_pumps()
logger.info(f"Internal pumps: {has_pumps}")

# Check firmware
firmware_id = ctrl.get_firmware_id()
logger.info(f"Firmware: {firmware_id}")  # "P4PROPLUS V2.3"

# Query valve states
kc1_state = ctrl.knx_six_state(ch=1)  # 0 or 1
kc2_state = ctrl.knx_six_state(ch=2)

logger.info(f"KC1 6-port valve: {'INJECT' if kc1_state else 'LOAD'}")
logger.info(f"KC2 6-port valve: {'INJECT' if kc2_state else 'LOAD'}")
```

---

## Troubleshooting

### AffiPump Issues

#### Pump Not Detected

**Symptoms:**
- "No FTDI pump controller found" error
- COM8 not appearing in Device Manager

**Solutions:**
1. **Check FTDI driver:**
   ```bash
   # Windows Device Manager → Ports (COM & LPT)
   # Should see: "USB Serial Port (COM8)"
   ```

2. **Enable VCP mode:**
   - Download FT_Prog from FTDI website
   - Scan for devices
   - Select device (SN: AP9XLF0GA)
   - Enable "Load VCP"
   - Program device
   - Disconnect/reconnect USB

3. **Verify hardware:**
   - Check USB cable connection
   - Verify pump power supply (24V)
   - Try different USB port

#### Aspirate/Dispense Failure

**Symptoms:**
- Pump timeout errors
- Blockage detection triggered
- Inconsistent volumes

**Solutions:**
1. **Check for air bubbles:**
   ```bash
   python test_pump_control.py
   > cleanup  # Run cleanup sequence
   ```

2. **Verify valve positions:**
   - INPUT for aspirate
   - OUTPUT for dispense

3. **Check tubing:**
   - Kinks or pinches
   - Disconnected fittings
   - Clogged filters

4. **Re-initialize pumps:**
   ```python
   pump.initialize_pumps()  # Home to zero position
   ```

#### Serial Communication Errors

**Symptoms:**
- Timeout exceptions
- Garbled responses
- Intermittent connection loss

**Solutions:**
1. **Check baud rate:** Must be 38400
2. **Verify cable:** Replace if damaged
3. **Close other programs:** Only one app can use COM8
4. **Reset controller:**
   ```python
   ctrl.close()
   time.sleep(1)
   ctrl = PumpController.from_first_available()
   ```

### P4PROPLUS Issues

#### Pumps Not Starting

**Symptoms:**
- Toggle button clicks but pump doesn't run
- No error messages

**Solutions:**
1. **Check RPM range:**
   - Must be 5-220 RPM
   - UI clamps to valid range

2. **Verify channel:**
   - Pump 1 = channel 1
   - Pump 2 = channel 2
   - Both = channel 3 (not for individual buttons!)

3. **Check controller connection:**
   ```python
   if not ctrl:
       logger.error("Controller not connected")
   ```

#### Toggle Buttons Stuck

**Symptoms:**
- Button shows "Stop" but pump not running
- Can't click button again

**Solutions:**
1. **Signal blocking issue:**
   - Check for `blockSignals(True)` before `setChecked()`
2. **UI state reset:**
   ```python
   btn.blockSignals(True)
   btn.setChecked(False)
   btn.setText("▶ Start")
   btn.blockSignals(False)
   ```

#### Valve Not Switching

**Symptoms:**
- Valve command returns success but no physical switch
- Injection not working

**Solutions:**
1. **Check valve feedback:**
   ```python
   response = ctrl.knx_six(state=1, ch=1)
   if response != b"1":
       logger.error("Valve command not acknowledged")
   ```

2. **Test with standalone script:**
   ```bash
   python valve-kc2-open.py --pump 1 --state open
   ```

3. **Check firmware version:**
   - Requires V2.3+ for valve support

---

## Best Practices

### Pump Operation

1. **Always prime before use:**
   ```python
   await pump_mgr.prime_pump(cycles=6)
   ```

2. **Run cleanup after experiments:**
   ```python
   await pump_mgr.cleanup_pump()
   ```

3. **Monitor for blockages:**
   - Check pump timing differences
   - Listen for unusual sounds
   - Inspect tubing regularly

4. **Use appropriate flow rates:**
   - Too fast: Air bubbles, pressure spikes
   - Too slow: Inefficient, long experiments
   - Recommended: 100-500 µL/min for most applications

### Valve Operation

1. **Return to safe positions:**
   ```python
   # Always close valves after use
   ctrl.knx_six(state=0, ch=1)    # LOAD
   ctrl.knx_six(state=0, ch=2)    # LOAD
   ctrl.knx_three(state=0, ch=1)  # Channel A
   ctrl.knx_three(state=0, ch=2)  # Channel C
   ```

2. **Use timeouts for safety:**
   ```python
   # Auto-close after 30 seconds
   ctrl.knx_six(state=1, ch=1, timeout_seconds=30)
   ```

3. **Verify switching:**
   - Audible click from valve
   - Visual confirmation in UI
   - Check valve state queries

### Code Patterns

1. **Block signals during programmatic changes:**
   ```python
   btn.blockSignals(True)
   btn.setChecked(new_state)
   btn.blockSignals(False)
   ```

2. **Use background threads for hardware:**
   ```python
   task = HardwareTask(callback=on_complete)
   QThreadPool.globalInstance().start(task)
   ```

3. **Handle errors gracefully:**
   ```python
   try:
       success = await pump_operation()
   except Exception as e:
       logger.exception(f"Operation failed: {e}")
       self.error_occurred.emit("operation", str(e))
   finally:
       self._current_operation = PumpOperation.IDLE
   ```

---

## API Reference

### PumpManager

```python
from affilabs.managers.pump_manager import PumpManager

mgr = PumpManager(hardware_manager)

# Operations
await mgr.prime_pump(cycles=6, volume_ul=1000,
                     aspirate_speed=24000, dispense_speed=5000)
await mgr.cleanup_pump(pulse_cycles=10, prime_cycles=6, speed=5000)
await mgr.run_buffer(duration_seconds=60, flow_rate_ul_min=100)

# Properties
mgr.is_available        # bool: Hardware present
mgr.is_idle            # bool: No operation running
mgr.current_operation  # PumpOperation enum

# Signals
mgr.operation_started.connect(callback)      # (str: operation_name)
mgr.operation_progress.connect(callback)     # (str, int, str)
mgr.operation_completed.connect(callback)    # (str, bool)
mgr.error_occurred.connect(callback)         # (str, str)
mgr.status_updated.connect(callback)         # (str, float, float, float, float)
```

### Controller (Valve Commands)

```python
from affilabs.utils.controller import PicoP4PRO

ctrl = PicoP4PRO()

# 6-Port Valves
ctrl.knx_six(state=0, ch=1)                    # KC1 → LOAD
ctrl.knx_six(state=1, ch=1)                    # KC1 → INJECT
ctrl.knx_six(state=1, ch=1, timeout_seconds=30) # Auto-close after 30s
ctrl.knx_six_both(state=1)                     # Both → INJECT

# 3-Way Valves
ctrl.knx_three(state=0, ch=1)                  # KC1 → Channel A
ctrl.knx_three(state=1, ch=1)                  # KC1 → Channel B
ctrl.knx_three_both(state=1)                   # KC1→B, KC2→D

# Internal Pumps (P4PROPLUS only)
ctrl.pump_start(rate_ul_min=100, ch=1)         # Start pump 1 at 100 RPM
ctrl.pump_stop(ch=1)                           # Stop pump 1
ctrl.has_internal_pumps()                      # bool: P4PROPLUS detected

# Valve State Query
state = ctrl.knx_six_state(ch=1)               # 0 or 1
```

### PumpHAL (AffiPump)

```python
from affilabs.utils.hal.pump_hal import create_pump_hal

pump = create_pump_hal(pump_manager)

# Initialization
pump.initialize_pumps()                        # Home both pumps
pump.is_available()                            # Check connection

# Volume Operations
pump.aspirate(pump_address=1, volume_ul=500, rate_ul_min=1000)
pump.dispense(pump_address=1, volume_ul=500, rate_ul_min=500)

# Valve Control
pump.set_valve_position(pump_address=1, port=1)  # Port 1 (INPUT)
pump.set_valve_position(pump_address=1, port=2)  # Port 2 (OUTPUT)

# Status
position = pump.get_syringe_position(pump_address=1)  # Steps
pump.wait_until_idle(pump_address=1, timeout_s=60)    # Block until ready

# Cleanup
pump.close()                                   # Disconnect
```

---

## Related Documentation

- [DEVICE_DATABASE_REGISTRATION.md](./DEVICE_DATABASE_REGISTRATION.md) - Device configuration and EEPROM
- [METHOD_CYCLE_SYSTEM.md](./METHOD_CYCLE_SYSTEM.md) - Experimental workflows and cycle queue
- [OPTICAL_CONVERGENCE_ENGINE.md](./OPTICAL_CONVERGENCE_ENGINE.md) - Detector calibration
- [INTERNAL_PUMP_ARCHITECTURE.md](../INTERNAL_PUMP_ARCHITECTURE.md) - P4PROPLUS detailed architecture

---

## Glossary

- **AffiPump**: External dual syringe pump system (Tecan Cavro Centris)
- **Aspirate**: Draw fluid into syringe (negative displacement)
- **Broadcast**: Send command to both pumps simultaneously (`/A`)
- **Cavro**: Brand name for Tecan's syringe pump product line
- **Dispense**: Push fluid out of syringe (positive displacement)
- **FTDI**: USB-to-Serial interface chip (FT232)
- **HAL**: Hardware Abstraction Layer (unified pump interface)
- **KC1/KC2**: Kinetic Channel 1 and 2 (independent flow paths)
- **LOAD**: 6-port valve position for sample loading
- **INJECT**: 6-port valve position for injection to sensor
- **P4PROPLUS**: Controller with integrated peristaltic pumps
- **Peristaltic**: Pump type using rollers and flexible tubing
- **RPM**: Revolutions Per Minute (peristaltic pump speed)
- **Syringe Pump**: Precision pump using piston in glass/plastic barrel
- **3-Way Valve**: Valve routing flow between 2 paths (A↔B, C↔D)
- **6-Port Valve**: Sample loop valve with LOAD/INJECT positions
- **VCP**: Virtual COM Port (FTDI driver mode)

---

**Document Version:** 1.0
**Last Updated:** February 2026
**Maintained By:** Affinité Instruments Development Team

