# Firmware V2.1 Implementation Guide

## Quick Start

1. **Apply modifications** to V2.0 firmware using `affinite_p4spr_v2.1_modifications.c`
2. **Compile** using Pico SDK toolchain
3. **Flash** UF2 file to Pico in bootloader mode
4. **Test** with provided Python test script

## What's New in V2.1

### Enhanced Rank Command: `rankbatch`
- **Batch intensities**: Individual intensity per LED (A, B, C, D)
- **Cycle counting**: Execute N complete cycles autonomously
- **Configurable timing**: Respect settle/dark times per cycle
- **Performance**: 18% faster than sequential batch commands

### Command Format
```
rankbatch:A,B,C,D,SETTLE,DARK,CYCLES\n
```

Example:
```
rankbatch:225,94,97,233,15,5,1\n
```

### Protocol Signals
- `BATCH_START` - Sequence begins
- `CYCLE:N` - Cycle N starts
- `X:READY` - LED X on, settling
- `X:READ` - Acquire spectrum now
- `X:DONE` - LED X off
- `X:SKIP` - LED X skipped (intensity=0)
- `CYCLE_END:N` - Cycle N complete
- `BATCH_END` - All cycles complete

## Files in This Directory

| File | Description |
|------|-------------|
| `affinite_p4spr_v2.1_modifications.c` | Code changes to apply to V2.0 firmware |
| `RANKBATCH_COMMAND_IMPLEMENTATION.md` | Complete specification and usage guide |
| `README_V2.1.md` | This file - quick reference |
| `test_rankbatch.py` | Python test script for validation |

## Implementation Checklist

### Step 1: Prepare Development Environment
- [ ] Pico SDK installed and configured
- [ ] Toolchain (gcc-arm-none-eabi) available
- [ ] V2.0 firmware source code accessible
- [ ] USB cable for flashing Pico

### Step 2: Apply Code Changes
- [ ] Update VERSION to "V2.1"
- [ ] Add `led_rank_batch_cycles()` function declaration
- [ ] Add `rankbatch:` command handler in main loop
- [ ] Implement `led_rank_batch_cycles()` function
- [ ] Keep existing `rank:` handler (backward compatibility)

### Step 3: Build Firmware
```bash
cd pico-p4spr-firmware
mkdir build && cd build
cmake ..
make
```
- [ ] Compilation successful
- [ ] `affinite_p4spr_v2.1.uf2` generated

### Step 4: Flash Firmware
- [ ] Hold BOOTSEL button on Pico
- [ ] Connect USB (Pico appears as mass storage)
- [ ] Copy UF2 file to Pico drive
- [ ] Pico automatically reboots with new firmware

### Step 5: Verify Installation
- [ ] Open serial terminal (115200 baud)
- [ ] Send `iv\n` command
- [ ] Verify response contains "2.1"
- [ ] Test backward compatibility: `rank:128,35,5\n`
- [ ] Test new command: `rankbatch:128,128,128,128,35,5,1\n`

### Step 6: Performance Testing
- [ ] Measure single cycle time (~675ms expected)
- [ ] Test multi-cycle execution (10 cycles)
- [ ] Verify batch intensities work correctly
- [ ] Test selective channels (zero intensity)
- [ ] Validate timing parameters respected

## Code Changes Summary

### 1. Version Update (Line ~33)
```c
const char* VERSION = "V2.1";
```

### 2. Function Declaration (Line ~143)
```c
bool led_rank_batch_cycles(uint8_t int_a, uint8_t int_b, uint8_t int_c, uint8_t int_d,
                           uint16_t settling_ms, uint16_t dark_ms, uint16_t num_cycles);
```

### 3. Command Handler (Line ~350)
```c
case 'r':
    if (command[1] == 'a' && command[2] == 'n' && command[3] == 'k' &&
        command[4] == 'b' && ... command[9] == ':'){
        // Parse 7 parameters
        // Call led_rank_batch_cycles()
    }
    else if (command[1] == 'a' && ... command[4] == ':'){
        // Existing rank: handler (V2.0 compatibility)
    }
    break;
```

### 4. Function Implementation (After led_rank_sequence)
```c
bool led_rank_batch_cycles(...){
    // Set individual LED intensities
    // Signal BATCH_START
    // Loop N cycles:
    //   Signal CYCLE:N
    //   Loop 4 channels:
    //     Turn on LED, signal READY
    //     Wait settle time
    //     Signal READ, wait for ACK
    //     Signal DONE
    //     Dark time
    //   Signal CYCLE_END:N
    // Signal BATCH_END
    // Return success
}
```

## Testing with Python

### Basic Test
```python
import serial
import time

ser = serial.Serial('COM5', 115200, timeout=1)
time.sleep(2)

# Check version
ser.write(b'iv\n')
print(f"Version: {ser.readline().decode().strip()}")

# Test rankbatch
cmd = "rankbatch:225,94,97,233,15,5,1\n"
ser.write(cmd.encode())

while True:
    line = ser.readline().decode().strip()
    print(line)

    if line.endswith(":READ"):
        # Simulate detector read
        time.sleep(0.15)
        ser.write(b'1\n')

    elif line == "BATCH_END":
        break

ser.close()
```

### Expected Output
```
Version: 2.1
BATCH_START
CYCLE:1
a:READY
a:READ
a:DONE
b:READY
b:READ
b:DONE
c:READY
c:READ
c:DONE
d:READY
d:READ
d:DONE
CYCLE_END:1
BATCH_END
1
```

## Performance Comparison

### V2.0 Sequential Mode
```python
# 4 separate batch commands
for ch in ['a', 'b', 'c', 'd']:
    ctrl.set_batch_intensities({ch: intensity})  # ~30ms
    spectrum = detector.acquire()                # ~150ms
    time.sleep(0.015)                           # ~15ms
# Total: ~820ms per cycle
```

### V2.1 Rankbatch Mode
```python
# Single rankbatch command
ctrl.led_rank_batch_cycles(
    intensities={'a': 225, 'b': 94, 'c': 97, 'd': 233},
    settling_ms=15,
    dark_ms=5,
    num_cycles=1
)
# Total: ~675ms per cycle (18% faster)
```

## Troubleshooting

### Issue: Firmware doesn't respond
- **Check**: USB connection stable
- **Check**: Serial port correct (COM5, /dev/ttyACM0, etc.)
- **Check**: Baud rate 115200
- **Fix**: Reset Pico, reconnect USB

### Issue: Version shows V2.0 not V2.1
- **Check**: UF2 file copied successfully
- **Check**: Pico rebooted after flashing
- **Fix**: Re-flash firmware in bootloader mode

### Issue: rankbatch command not recognized
- **Check**: Command format exactly `rankbatch:A,B,C,D,SETTLE,DARK,CYCLES\n`
- **Check**: No extra spaces or characters
- **Fix**: Test with simple example: `rankbatch:128,128,128,128,35,5,1\n`

### Issue: Timeouts during acquisition
- **Check**: Python sends ACK after each READ signal
- **Check**: Detector integration time < 10 seconds
- **Fix**: Send any character (`1\n`) after detector read

### Issue: LEDs don't turn off
- **Check**: Firmware receives ACK from Python
- **Check**: BATCH_END signal received
- **Fix**: Send `lx\n` command to force all LEDs off

## Next Steps

### Python Integration
1. Create wrapper function `led_rank_batch_cycles()` in controller.py
2. Update data_acquisition_manager.py to use rankbatch
3. Add firmware version detection
4. Test with live acquisition

### Performance Optimization
1. Measure actual cycle time in live mode
2. Compare with sequential mode baseline
3. Tune settle/dark times if needed
4. Validate timing consistency

### Production Deployment
1. Document firmware version in device config
2. Add version compatibility check in Python
3. Create firmware update procedure
4. Train users on new command

## Support

For issues or questions:
1. Check `RANKBATCH_COMMAND_IMPLEMENTATION.md` for detailed specification
2. Review test script `test_rankbatch.py` for examples
3. Verify V2.0 rank command still works (backward compatibility)
4. Check Pico SDK documentation for low-level debugging

## Version History

- **V2.1** (2025-12-12): Added rankbatch command with batch intensities and cycle counting
- **V2.0**: Added rank command for firmware-controlled LED sequencing
- **V1.9**: Added multi-LED command (lm:A,B,C,D)
- **V1.8**: Base firmware with individual LED control

## License

Same as base firmware repository: https://github.com/Ludo-affi/pico-p4spr-firmware
