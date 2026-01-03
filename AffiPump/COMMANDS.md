# Cavro Centris Pump Command Reference

Complete command set for Tecan Cavro Centris syringe pumps (38400 baud, 8N1).

## Command Format

```
/<address><command(s)>R<CR>
```

- **Address**: `1` (Pump 1), `2` (Pump 2), `A` (Both pumps)
- **Commands**: One or more commands chained together
- **R**: Execute command (required)
- **<CR>**: Carriage return `\r` (required)

## Basic Control Commands

| Command | Description | Example |
|---------|-------------|---------|
| `Z` | Initialize pump (home syringe) | `/AZR` - Initialize both pumps |
| `z` | Soft reset | `/1zR` - Reset pump 1 |
| `T` | Terminate (emergency stop) | `/1TR` - Stop pump 1 immediately |
| `I` | Set valve to Input (left port) | `/1IR` - Pump 1 valve to input |
| `O` | Set valve to Output (right port) | `/2OR` - Pump 2 valve to output |
| `B` | Set valve to Bypass (if equipped) | `/1BR` |
| `E` | Set valve to Extra port (if equipped) | `/1ER` |

## Movement Commands

| Command | Parameter | Description | Example |
|---------|-----------|-------------|---------|
| `A[n],1` | Position (µL) | Move plunger to absolute position | `/1A500,1R` - Move to 500µL |
| `P[n],1` | Volume (µL) | Pull/aspirate (relative move up) | `/1P200,1R` - Aspirate 200µL |
| `D[n],1` | Volume (µL) | Dispense (relative move down) | `/1D100,1R` - Dispense 100µL |
| `V[n],1` | Speed (µL/s) | Set plunger velocity | `/1V200,1R` - Set to 200µL/s |

**Note**: The `,1` suffix is required for volume/position parameters.

## Query Commands

| Command | Description | Response Format |
|---------|-------------|-----------------|
| `?` | Query status and position | Status byte + position in µL |
| `?1` | Query start velocity | Velocity in steps/sec |
| `?2` | Query top velocity | Velocity in steps/sec |
| `?3` | Query cutoff velocity | Velocity in steps/sec |
| `?4` | Query plunger position | Position in steps |
| `?6` | Query valve position | Port number (1=I, 2=O, etc.) |
| `?10` | Query backlash steps | Backlash compensation value |
| `?21000` | Query syringe volume | Maximum volume in µL |

## Status Byte Decoding

Returned by `?` command (second byte after separator):

```
Bit 0 (0x01): Initialization error
Bit 1 (0x02): Invalid command
Bit 2 (0x04): Invalid operand  
Bit 3 (0x08): EEPROM error
Bit 4 (0x10): Initialized
Bit 5 (0x20): Idle (ready)
Bit 6 (0x40): Busy (moving)
Bit 7 (0x80): Reserved
```

**Common Values:**
- `0x60` (96) = Ready (Initialized + Idle)
- `0x40` (64) = Busy (moving)
- `0x30` (48) = Initialized but not idle
- `0x01` (1) = Initialization error

## Configuration Commands

| Command | Parameter | Description |
|---------|-----------|-------------|
| `h[n]` | Mode bits | Set control mode/options |
| `S[n]` | Steps | Set start velocity |
| `P[n]` | Steps | Set top (peak) velocity |
| `c[n]` | Steps | Set cutoff (stop) velocity |
| `k[n]` | Steps | Set backlash compensation |
| `e[n]` | Enable bits | Enable/disable pump features |

## Command Chaining Examples

Multiple commands can be executed in sequence:

**Fill pump from input:**
```
/1IV200,1A1000,1R
```
- `I` - Set valve to input
- `V200,1` - Set speed to 200µL/s
- `A1000,1` - Move to 1000µL (aspirate)
- `R` - Execute

**Empty pump to output:**
```
/2OV2,1A0,1R
```
- `O` - Set valve to output
- `V2,1` - Set speed to 2µL/s
- `A0,1` - Move to 0µL (dispense)
- `R` - Execute

**Load and inject loop (from engineer notes):**
```
/2IV200,1,A1000,12OV5,1,A0,1R
```
- `I` - Valve to input
- `V200,1` - Speed 200µL/s
- `A1000,1` - Aspirate to 1000µL
- `2` - (parameter separator)
- `O` - Valve to output
- `V5,1` - Speed 5µL/s
- `A0,1` - Dispense to 0µL
- `R` - Execute

## Common Workflows

### Initialization Sequence
```python
pump.send_command("/1zR")      # Reset pump 1
pump.send_command("/1ZR")      # Initialize pump 1
time.sleep(5)                   # Wait for homing
status = pump.get_status(1)     # Verify ready (0x60)
```

### Aspirate-Dispense Cycle
```python
# Fill from input
pump.send_command("/1IV200,1A1000,1R")  # 1000µL at 200µL/s
time.sleep(5.5)  # Wait: 1000µL / 200µL/s + 0.5s

# Dispense to output
pump.send_command("/1OV50,1A0,1R")      # Empty at 50µL/s
time.sleep(20.5)  # Wait: 1000µL / 50µL/s + 0.5s
```

### Position Verification
```python
response = pump.send_command("/1?")
result = pump.parse_response(response)
print(f"Status: 0x{result['status']:02X}")
print(f"Position: {result['data']}µL")
```

## Timing Considerations

- **Initialization**: 2-5 seconds after `Z` command
- **Movement**: Calculate wait time as `volume / speed + 0.5s` buffer
- **Query response**: 0.1-0.3 seconds typical
- **Command processing**: ~50ms overhead per command

## Error Handling

Check status byte after operations:
- If bit 0 set (0x01): Re-initialize pump
- If bit 1 set (0x02): Invalid command syntax
- If bit 2 set (0x04): Parameter out of range
- If bit 6 set (0x40): Pump still busy, wait longer

## Protocol Notes

1. **Echo Response**: All commands are echoed back, followed by status data
2. **Null Terminators**: Responses end with `\x00`
3. **Separator**: Status data starts after `\xff` byte
4. **Checksum**: `\x03` marks end of data section
5. **Line Ending**: `\r\n` follows checksum

Example response breakdown:
```
/1?\r\x00\xff/0`1600\x03\r\n\x00
[cmd] [sep][status][data][end]
```

## Safety Notes

- Always initialize pumps after power-on (`/AZR`)
- Use reasonable speeds (2-200µL/s typical)
- Don't exceed syringe volume (query with `?21000`)
- Stop pump before changing valve positions for safety
- Use `T` command for emergency stop if needed

## References

- Tecan Cavro Centris Operating Manual - Section 3.4-3.5
- Original affipump package: `../Affilabs.core/ezcontrol-AI/affipump/`
- Engineer PuTTY setup notes
