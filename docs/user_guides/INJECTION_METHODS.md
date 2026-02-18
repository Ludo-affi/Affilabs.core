# Injection Methods Documentation

## Overview

Three injection methods are now available in the `PumpManager` class, each designed for different experimental requirements:

1. **Simple Injection** (`method="simple"`) - **DEFAULT RECOMMENDED**
2. **Partial Loop Injection** (`method="partial_loop"`) - **ADVANCED**
3. **Complex Injection** (`method="default"`) - **ORIGINAL WITH KC2 PRIMING**

---

## Method 1: Simple Injection (Recommended Default)

### Use Case
Standard injection for most experiments where you need straightforward sample introduction.

### Sequence
1. Aspirate both pumps to 1000 µL
2. Start dispensing at flow rate from setup (assay_flow_rate when in autoread)
3. Wait 30 seconds (configurable)
4. Open 6-port valves (contact time starts)
5. Calculate contact time = loop_volume / assay_flow_rate
6. After contact time, close valves
7. Continue dispensing until empty

### Advantages
- Simple, reliable operation
- Minimal valve switching
- Predictable timing
- Good for routine experiments

### Usage Example

```python
from affilabs.managers.pump_manager import PumpManager

# Get flow rate from UI
assay_flow = sidebar.pump_assay_spin.value()  # e.g., 15 µL/min

# Run simple injection
success = await pump_mgr.inject_with_valve_timing(
    assay_flow_rate=assay_flow,
    method="simple",                    # Use simple method
    valve_open_delay_s=30.0,            # Wait 30s before opening valves
    loop_volume_ul=100.0,               # 100 µL loop
)
```

### Parameters
- `assay_flow_rate`: Required - Flow rate from setup (µL/min)
- `valve_open_delay_s`: Optional - Default 30s
- `loop_volume_ul`: Optional - Default 100 µL
- `aspiration_flow_rate`: Optional - Default 24000 µL/min

---

## Method 2: Partial Loop Injection (Advanced)

### Use Case
Advanced technique for partial loop filling from pump output, useful for:
- Small sample volumes
- Precise sample introduction
- Minimizing sample waste
- Controlled mixing

### Sequence
1. Aspirate 900 µL into both pumps
2. Flip 3-way valve (open to D position)
3. Flip 6-port valve to inject position
4. Aspirate 100 µL from pump output (fills loop)
5. Close 6-port valve (load position)
6. Push 50 µL
7. Wait 10 seconds
8. Flip 6-port valve (inject position)
9. Push 40 µL
10. Flip 3-way valve (close)
11. Switch flowrate to setup flowrate (if different)
12. Push rest of volume using contact time calculation
13. Close valves after contact time

### Advantages
- Fills loop from pump output (not from sample source)
- Controlled introduction of sample
- Allows partial loop filling
- Better control over sample volume

### Usage Example

```python
# Run partial loop injection
success = await pump_mgr.inject_with_valve_timing(
    assay_flow_rate=15.0,               # µL/min
    method="partial_loop",              # Use partial loop method
    loop_volume_ul=100.0,               # Loop size
)
```

### Parameters
- `assay_flow_rate`: Required - Flow rate from setup (µL/min)
- `loop_volume_ul`: Optional - Default 100 µL
- `aspiration_flow_rate`: Optional - Default 24000 µL/min

### Notes
- Contact time calculation still applies for final push phase
- Valve timing is automatically managed
- Total volume used: 1000 µL (900 initial + 100 from output)

---

## Method 3: Complex Injection (Original Default)

### Use Case
Original method with KC2 priming and pulsing, for experiments requiring:
- KC2 channel priming before injection
- Pulsed delivery during injection
- Maximum control over both channels

### Sequence
1. Load both pumps to 1000 µL
2. KC1 starts dispensing at assay flow rate immediately
3. KC2 opens 3-way valve to D
4. KC2 pushes 100 µL (priming)
5. Wait 5 seconds
6. KC2 closes 3-way valve
7. KC2 pulls 100 µL (back-flush)
8. Wait 10 seconds
9. KC2 starts dispensing to join KC1 (both now dispensing)
10. Wait 30 seconds after KC2 dispense starts
11. Open both 6-port valves in sync
12. KC2 pulse sequence (spike to 900 µL/min for 2s)
13. Contact time = loop_volume / assay_flow_rate
14. KC2 pulse sequence after closing (spike to 900 µL/min for 2s)
15. Close both 6-port valves (back to load)
16. Continue dispensing until pumps empty

### Advantages
- KC2 priming ensures channel is ready
- Pulsing can help with mixing or preventing settling
- Most control over both channels

### Disadvantages
- More complex valve sequences
- Longer total time
- More potential failure points

### Usage Example

```python
# Run complex injection with KC2 priming
success = await pump_mgr.inject_with_valve_timing(
    assay_flow_rate=15.0,
    method="default",                   # Use original complex method
    pulse_rate=900.0,                   # KC2 spike rate
    valve_open_delay_s=30.0,
    loop_volume_ul=100.0,
)
```

### Parameters
- `assay_flow_rate`: Required - Flow rate from setup (µL/min)
- `pulse_rate`: Optional - Default 900 µL/min (KC2 spike rate)
- `valve_open_delay_s`: Optional - Default 30s
- `loop_volume_ul`: Optional - Default 100 µL
- `aspiration_flow_rate`: Optional - Default 24000 µL/min

---

## Comparison Table

| Feature | Simple | Partial Loop | Complex |
|---------|--------|--------------|---------|
| **Complexity** | Low | Medium | High |
| **Valve Switches** | 2 | 8 | 12 |
| **Total Time** | Shortest | Medium | Longest |
| **KC2 Priming** | No | No | Yes |
| **Pulsing** | No | No | Yes |
| **Sample Source** | Standard | Pump output | Standard |
| **Recommended For** | Routine work | Small volumes | Complex assays |

---

## Contact Time Calculation

All methods use the same contact time calculation:

```python
contact_time_seconds = (loop_volume_ul / assay_flow_rate_ul_per_min) * 60
```

### Examples

| Loop Volume | Flow Rate | Contact Time |
|-------------|-----------|--------------|
| 100 µL | 15 µL/min | 400 seconds (6.67 min) |
| 100 µL | 10 µL/min | 600 seconds (10 min) |
| 100 µL | 25 µL/min | 240 seconds (4 min) |
| 50 µL | 15 µL/min | 200 seconds (3.33 min) |

---

## Integration with UI

### From Flow Builder Tab

```python
# In affilabs/sidebar_tabs/AL_flow_builder.py

async def on_inject_button_clicked():
    """Handle inject button click."""
    # Get parameters from UI
    assay_flow = self.sidebar.pump_assay_spin.value()
    loop_volume = 100.0  # Or from settings
    
    # Choose method (can add dropdown in UI)
    method = "simple"  # Default recommended
    
    # Run injection
    success = await self.sidebar.hardware_manager.pump_manager.inject_with_valve_timing(
        assay_flow_rate=assay_flow,
        method=method,
        valve_open_delay_s=30.0,
        loop_volume_ul=loop_volume,
    )
    
    if success:
        logger.info("✅ Injection completed successfully")
    else:
        logger.error("❌ Injection failed")
```

### Adding Method Selection to UI

To allow users to select the injection method in the UI, add a dropdown:

```python
# In flow builder setup
self.injection_method_combo = QComboBox()
self.injection_method_combo.addItems([
    "Simple (Default)",
    "Partial Loop",
    "Complex (Original)"
])

# Then use:
method_map = {
    "Simple (Default)": "simple",
    "Partial Loop": "partial_loop",
    "Complex (Original)": "default"
}
selected_method = method_map[self.injection_method_combo.currentText()]
```

---

## Safety Features

All methods include:

1. **Automatic valve closure** on error
2. **Automatic valve closure** in finally block
3. **Progress signals** for UI updates
4. **Error signals** for failure notification
5. **State checking** (ensures pump is idle before starting)
6. **Hardware availability** checks

---

## Troubleshooting

### Injection Fails to Start
- Check that pumps are idle (`pump_manager.is_idle`)
- Verify hardware is available (`pump_manager.is_available`)
- Check valve controller connection

### Valves Don't Open/Close
- Check valve controller (`hardware_manager._ctrl_raw`)
- Verify valve command responses in logs
- Check for hardware communication errors

### Contact Time Too Short/Long
- Verify `assay_flow_rate` is correct
- Check `loop_volume_ul` setting
- Review contact time calculation in logs

### Pumps Don't Complete
- Check for blockages (time difference between pumps)
- Verify flow rate is achievable
- Check pump positions and syringe capacity

---

## Best Practices

1. **Use "simple" method** for routine experiments
2. **Use "partial_loop"** for small sample volumes
3. **Use "default"** only if KC2 priming is required
4. **Monitor logs** for valve timing and contact time
5. **Adjust valve_open_delay_s** based on system stabilization needs
6. **Verify contact time** matches experimental requirements

---

## See Also

- [INJECT_FUNCTION_README.md](INJECT_FUNCTION_README.md) - Original complex method documentation
- [PUMP_CONTROL_ARCHITECTURE.md](PUMP_CONTROL_ARCHITECTURE.md) - Overall pump architecture
- [affilabs/managers/pump_manager.py](affilabs/managers/pump_manager.py) - Implementation source code
