# AffiPump Controller - Function Reference

## ✅ Implemented Functions (Complete)

### Basic Operations
- `open()` - Connect to pump
- `close()` - Disconnect
- `initialize_pumps()` - Zero both pumps (broadcast)
- `initialize_pump(pump_num)` - Zero specific pump
- `get_position(pump_num)` - Get current volume in µL
- `aspirate(pump_num, volume_ul, speed_ul_s)` - Draw liquid in
- `dispense(pump_num, volume_ul, speed_ul_s)` - Push liquid out
- `move_to_position(pump_num, position_ul, speed_ul_s)` - Absolute positioning

### Dual Pump Control
- `aspirate_both(volume_ul, speed_ul_s)` - Synchronized aspirate
- `dispense_both(volume_ul, speed_ul_s)` - Synchronized dispense
- `get_both_positions()` - Get both pump positions

### Valve Control
- `set_valve_input(pump_num)` - I position
- `set_valve_output(pump_num)` - O position
- `set_valve_bypass(pump_num)` - B position
- `get_valve_position(pump_num)` - Query current valve position

### Status & Errors
- `get_status(pump_num)` - Full status with error decoding
- `get_error_code(pump_num)` - Last error with message
- `clear_errors(pump_num)` - Reset error state
- `is_busy(pump_num)` - Check if pump is moving
- `wait_until_ready(pump_num, timeout)` - Block until ready
- `terminate_move(pump_num)` - Stop current command (T)
- `abort(pump_num)` - Alias for terminate_move

### Configuration Queries
- `get_syringe_volume(pump_num)` - Query ?17
- `get_backlash(pump_num)` - Query ?26
- `get_firmware_version(pump_num)` - Query ?23
- `get_plunger_position_raw(pump_num)` - Position in steps
- `get_start_speed(pump_num)` - Query ?1
- `get_top_speed(pump_num)` - Query ?2
- `get_cutoff_speed(pump_num)` - Query ?3

### Speed Control
- `set_speed(pump_num, speed_ul_s)` - Set speed in µL/s (with ,1)
- `set_start_speed(pump_num, pulses_per_sec)` - v command (50-1000)
- `set_top_speed(pump_num, pulses_per_sec)` - V command (5-6000)
- `set_cutoff_speed(pump_num, pulses_per_sec)` - c command (50-2700)
- `set_slope(pump_num, slope_code)` - L command (1-20)
- `set_backlash(pump_num, steps)` - K command

### Pressure Monitoring
- `get_pressure(pump_num)` - Query ?24 (0 if no sensor)
- `get_pressure_limit(pump_num)` - Query ?25
- `get_back_pressure(pump_num)` - Alias for get_pressure
- `dispense_with_pressure_monitoring()` - Incremental dispense with pressure checks

### Volume Calculations
- `get_current_volume(pump_num)` - Alias for get_position
- `get_remaining_volume(pump_num)` - Space left for aspiration
- `check_volume_available(pump_num, volume_ul)` - Check before dispense
- `validate_position(position_ul)` - Check if position valid

### Advanced Operations (Priority 2)
- `extract_to_waste(pump_num, volume_ul, waste_port, input_port, speed_ul_s)`
  - Aspirate from input → switch valve → dispense to waste
  - Common pattern for sample extraction
  
- `transfer(from_pump, to_pump, volume_ul, speed_ul_s)`
  - Transfer liquid between pump 1 and pump 2
  - Validates volume availability
  - Synchronized operation
  
- `prime_lines(pump_num, cycles, volume_ul, speed_ul_s)`
  - Repeated fill/empty for priming
  - Default: 3 cycles of full syringe volume
  
- `flush(pump_num, cycles, speed_ul_s)`
  - Fast flush (5 cycles at high speed)
  - Maintenance operation

### Dilution/Mixing (Priority 3)
- `dilute(pump_num, diluent_volume_ul, sample_volume_ul, ports...)`
  - Aspirate diluent from one port
  - Aspirate sample from another port
  - Dispense mixed solution to output
  - Automatic ratio calculation

### Diagnostics
- `get_all_diagnostics(pump_num)` - Returns complete dict with:
  - Status (busy, error, initialized)
  - Position (µL and steps)
  - Valve position
  - Configuration (volume, backlash, firmware)
  - Speed settings
  - Pressure info
  - Error info
  
- `print_diagnostics(pump_num)` - Formatted diagnostic report

## Usage Examples

### Basic Operation
```python
pump = AffipumpController()
pump.open()

# Initialize
pump.initialize_pump(1)
time.sleep(5)

# Aspirate 100µL
pump.set_valve_input(1)
pump.aspirate(1, 100, speed_ul_s=200)

# Dispense 50µL
pump.set_valve_output(1)
pump.dispense(1, 50, speed_ul_s=100)

pump.close()
```

### Extract to Waste
```python
# Aspirate 200µL from input, dispense to output (waste)
pump.extract_to_waste(1, 200, waste_port='O', input_port='I')
```

### Transfer Between Pumps
```python
# Transfer 100µL from pump 1 to pump 2
pump.transfer(from_pump=1, to_pump=2, volume_ul=100)
```

### Dilution
```python
# Mix 80µL diluent with 20µL sample (4:1 ratio)
pump.dilute(1, 
           diluent_volume_ul=80, 
           sample_volume_ul=20,
           diluent_port='I',
           sample_port='O',
           output_port='B')
```

### Prime/Flush
```python
# Prime lines with 3 cycles of 100µL
pump.prime_lines(1, cycles=3, volume_ul=100)

# Fast flush with 5 cycles
pump.flush(1, cycles=5, speed_ul_s=500)
```

### Diagnostics
```python
# Full diagnostic report
pump.print_diagnostics(1)

# Or get raw data
diag = pump.get_all_diagnostics(1)
print(f"Firmware: {diag['firmware_version']}")
print(f"Position: {diag['position_ul']}µL")
```

### Speed Optimization
```python
# Fine-tune acceleration
pump.set_start_speed(1, 100)      # Gentle start
pump.set_top_speed(1, 5000)       # Fast movement
pump.set_cutoff_speed(1, 500)     # Controlled stop
pump.set_slope(1, 10)              # Medium acceleration
```

### Error Recovery
```python
# Auto-recovery enabled by default
pump = AffipumpController(auto_recovery=True)

try:
    pump.dispense(1, 100)
except pump.PumpError as e:
    print(f"Error: {e.error_msg}")
    # Auto-recovery already attempted
```

### Volume Safety
```python
# Check before operations
if pump.check_volume_available(1, 100):
    pump.dispense(1, 100)
else:
    print("Not enough volume!")

remaining = pump.get_remaining_volume(1)
print(f"Can still aspirate {remaining}µL")
```

## Key Features

### ✅ Accurate Conversion
- 181.49 steps/µL for 1000µL syringe
- 1600 step offset for zero position
- Automatic step↔µL conversion

### ✅ Error Handling
- ASCII error code dictionary (i=Plunger Overload, g=Not Initialized, etc.)
- Auto-recovery on overload errors
- Custom PumpError exception

### ✅ Dual Pump Support
- Individual control (/1, /2)
- Synchronized broadcast (/A)
- Pump-to-pump transfer

### ✅ No Pressure Sensor
- Hardware not installed (query ?24 returns 0)
- Motor current sensing provides overload protection
- Incremental dispense workaround for pseudo-monitoring

## Test Results

**All systems operational:**
- Firmware: 30048042 Rev -E
- Syringe: 1000µL
- Backlash: 28 steps
- Configuration queries: ✓
- Speed controls: ✓
- Volume calculations: ✓
- Error handling: ✓
- Advanced operations: ✓ (defined, tested individually)

## Next: Phase 2 HAL Adapter
Controller ready for Affilabs.core integration!
