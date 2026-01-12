# Inject Function Documentation

## Overview

A new inject function has been added to the `PumpManager` class that implements a precise injection sequence with automated valve timing control.

## Location

**File:** [affilabs/managers/pump_manager.py](affilabs/managers/pump_manager.py#L997-L1226)

**Method:** `inject_with_valve_timing()`

## Function Signature

```python
async def inject_with_valve_timing(
    self,
    assay_flow_rate: float,
    aspiration_flow_rate: float = 24000.0,
    loop_volume_ul: float = 100.0,
    valve_open_delay_s: float = 30.0,
    pulse_rate: float = 1200.0,
) -> bool:
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `assay_flow_rate` | float | **Required** | Dispense flow rate from assay settings (µL/min) - typically from sidebar flow control |
| `aspiration_flow_rate` | float | 24000.0 | Aspiration speed for loading the pump (µL/min) |
| `loop_volume_ul` | float | 100.0 | Sample loop volume in microliters |
| `valve_open_delay_s` | float | 30.0 | Delay after dispense starts before opening valves (seconds) |
| `pulse_rate` | float | 1200.0 | KC2 spike flow rate during pulse sequences (µL/min) - configurable in advanced settings |

## Sequence of Operations

The function performs the following sequence:

1. **Load Pump** (Aspiration Phase)
   - Both pumps aspirate 1000 µL at the default aspiration flowrate (24000 µL/min)
   - Simultaneous operation using broadcast commands
   - Blockage detection via timing comparison

2. **Start Dispense** (Dispense Phase Begin)
   - Both pumps start dispensing at the assay flow rate (from sidebar)
   - Continues in background while executing timing sequence

3. **Valve Open Delay** (15 seconds default)
   - Waits specified time after dispense starts
   - Allows system to stabilize before sample injection

4. **Open 6-Port Valves** (Inject Position)
   - Both 6-port valves open synchronously
   - Valves switch to "inject" position (state = 1)
   - Sample begins flowing through the loop

5. **Contact Time** (Calculated)
   - Duration calculated as: `contact_time = loop_volume / assay_flow_rate`
   - For example: 100 µL loop at 15 µL/min = 400 seconds contact time
   - Sample flows through loop for this duration

6. **Close 6-Port Valves** (Load Position)
   - Both valves close synchronously after contact time
   - Valves return to "load" position (state = 0)
   - Sample injection complete

7. **Empty Pumps** (Continue Dispensing)
   - Pumps continue dispensing until fully empty
   - Single cycle operation - no refill
   - Monitors for completion and blockages

## Usage Example

### From Application Code

```python
from affilabs.managers.pump_manager import PumpManager

# Assuming you have a hardware_manager instance
pump_mgr = PumpManager(hardware_manager)

# Get assay flow rate from sidebar (e.g., 15 µL/min)
assay_flow = sidebar.pump_assay_spin.value()

# Get pulse rate from advanced settings (default: 1200 µL/min)
pulse_rate = getattr(sidebar, 'pump_inject_pulse_rate', 1200.0)

# Run inject sequence
success = await pump_mgr.inject_with_valve_timing(
    assay_flow_rate=assay_flow,
    aspiration_flow_rate=24000.0,  # Default fast load
    loop_volume_ul=100.0,           # Standard 100 µL loop
    valve_open_delay_s=30.0,        # 30 second delay
    pulse_rate=pulse_rate,          # KC2 spike rate from settings
)

if success:
    print("✓ Injection completed successfully")
else:
    print("✗ Injection failed")
```

### Standalone Test Script

Run the included test script:

```bash
python test_inject_function.py
```

This will:
- Initialize hardware
- Run inject sequence with default parameters
- Show detailed logging of each step
- Report success/failure

## Contact Time Calculation

The contact time is automatically calculated based on the loop volume and flow rate:

```python
contact_time_seconds = (loop_volume_ul / assay_flow_rate_ul_per_min) * 60
```

**Examples:**

| Loop Volume | Flow Rate | Contact Time |
|-------------|-----------|--------------|
| 100 µL | 15 µL/min | 400 seconds (6.67 min) |
| 100 µL | 10 µL/min | 600 seconds (10 min) |
| 100 µL | 25 µL/min | 240 seconds (4 min) |
| 50 µL | 15 µL/min | 200 seconds (3.33 min) |

## Safety Features

1. **Automatic Valve Closure**
   - Valves automatically close after contact time
   - `finally` block ensures closure even on errors
   - Safety timeout prevents valve from staying open

2. **Blockage Detection**
   - Monitors timing difference between KC1 and KC2 pumps
   - Alerts if one pump significantly lags (>1.5s aspiration, >2.0s dispense)
   - Prevents damage from blocked lines

3. **Error Handling**
   - All exceptions caught and logged
   - Valves closed on any error
   - Clear error messages via signals

4. **Hardware Checks**
   - Verifies pump availability before starting
   - Checks for valve controller presence
   - Validates pump is idle before beginning

## Signals Emitted

The function emits progress signals throughout execution:

```python
# Operation lifecycle
operation_started.emit("inject")
operation_progress.emit("inject", percent, message)
operation_completed.emit("inject", success)

# Errors
error_occurred.emit("inject", error_message)
```

### Progress Updates

| Progress % | Message | Description |
|------------|---------|-------------|
| 10% | "Loading pumps..." | Aspiration phase |
| 30% | "Dispensing..." | Dispense started |
| 40% | "Waiting 15s..." | Pre-valve delay |
| 50% | "Valves OPEN - sample flowing" | Valves opened |
| 60% | "Contact time X.Xs..." | Sample in loop |
| 70% | "Valves CLOSED - returning to load" | Valves closed |
| 80% | "Emptying pumps..." | Final dispense |
| 100% | "Complete" | Sequence done |

## Hardware Requirements

1. **AffiPump System**
   - 2x Tecan Cavro Centris syringe pumps
   - Connected via FTDI USB interface
   - Initialized and ready

2. **KNX Valve Controller**
   - 2x 6-port valves (KC1 and KC2)
   - Connected and responsive
   - Required for inject sequence

3. **Sample Loop**
   - Configured loop volume (default 100 µL)
   - Connected to 6-port valves

## Integration with UI

To integrate with the sidebar flow controls:

```python
# In your UI event handler (e.g., inject button clicked)
async def on_inject_clicked(self):
    # Get flow rate from sidebar assay setting
    assay_flow = self.sidebar.pump_assay_spin.value()

    # Get pulse rate from advanced settings (if configured)
    pulse_rate = getattr(self.sidebar, 'pump_inject_pulse_rate', 1200.0)

    # Run inject with UI settings
    success = await self.pump_mgr.inject_with_valve_timing(
        assay_flow_rate=assay_flow,
        pulse_rate=pulse_rate,
    )

    if success:
        self.show_message("Injection complete")
    else:
        self.show_error("Injection failed")
```

## Configuration

### Advanced Settings Dialog

The inject pulse flow rate can be configured in the **Flow Advanced Settings** dialog:

1. Open the Flow tab in the sidebar
2. Click the **⚙️ Advanced** button in the AffiPump Control section
3. Adjust the **Inject Pulse** field (default: 1200 µL/min)
   - Range: 100 - 5000 µL/min
   - Controls the KC2 spike flow rate during the inject sequence
   - Two 2-second pulses are performed (after valve open and valve close)
4. Click **Save** to apply the new setting

The pulse rate is used during the inject sequence to spike KC2 at a higher flow rate for 2 seconds, helping to push sample through the loop efficiently.

## Troubleshooting

### "No pump hardware available"
- Check pump power
- Verify USB connection
- Ensure FTDI drivers installed

### "No valve controller available"
- Check KNX controller connection
- Verify controller initialization
- Check valve power supply

### "Blockage detected"
- Check for kinked tubing
- Verify sample line is clear
- Check valve operation
- Inspect pump plungers

### Valves don't open/close
- Check KNX controller logs
- Verify valve power (24V)
- Test valves manually
- Check valve cycle count

## Notes

- **Single Cycle Only:** Function does not refill - runs one complete cycle
- **Simultaneous Operation:** Both pumps (KC1 & KC2) operate in sync
- **No Manual Intervention:** Fully automated timing - no user interaction needed
- **Precise Timing:** Contact time calculated automatically from loop volume and flow rate

## See Also

- [pump_manager.py](affilabs/managers/pump_manager.py) - Full source code
- [test_inject_function.py](test_inject_function.py) - Test script
- AffiPump controller documentation
- KNX valve controller reference
