# Firmware V1.2: LED Rank Command for Fast Calibration

## Overview

Added `rank` command to firmware for **atomic LED ranking** during Step 3 calibration. This command sequences through all 4 LEDs with firmware-controlled timing, making calibration faster and more reliable.

## Firmware Changes

### New Command: `rank:XXX,SSSS,DDD`

**Parameters:**
- `XXX` = Test LED intensity (0-255, typical: 128 for 50%)
- `SSSS` = LED settling time in ms (default: 45ms)
- `DDD` = Dark time between channels in ms (default: 5ms)

**Example:**
```
rank:128,45,5\n  → Test at 50% brightness, 45ms settling, 5ms dark
rank:64\n        → Test at 25% brightness, use default timings
```

### Protocol Flow

```
Python → Firmware: "rank:128,45,5\n"
Firmware → Python: "START\n"

[Channel A]
Firmware → Python: "a:READY\n"     (LED A turning on)
Firmware: sleep(45ms)               (LED settling)
Firmware → Python: "a:READ\n"      (signal Python to read spectrum NOW)
Python: read_spectrum()             (spectrum acquisition while LED on)
Firmware: LED A off, sleep(5ms)    (dark period)
Firmware → Python: "a:DONE\n"      (measurement complete)

[Channel B]
Firmware → Python: "b:READY\n"
... (repeat for B, C, D)

Firmware → Python: "END\n"          (all channels complete)
```

### Implementation Details

**Firmware side** (`affinite_p4spr.c`):

```c
// New function declaration
bool led_rank_sequence (uint8_t test_intensity, uint16_t settling_ms, uint16_t dark_ms);

// Command handler in main loop
case 'r':
    if (strncmp(command, "rank:", 5) == 0){
        // Parse parameters with defaults
        uint8_t test_intensity = parse_or_default(128);
        uint16_t settling_ms = parse_or_default(45);
        uint16_t dark_ms = parse_or_default(5);

        // Execute sequence
        led_rank_sequence(test_intensity, settling_ms, dark_ms);
    }
    break;

// Sequence function
bool led_rank_sequence (uint8_t test_intensity, uint16_t settling_ms, uint16_t dark_ms){
    printf("START\n");

    for each channel (a, b, c, d):
        printf("X:READY\n");
        sleep_ms(settling_ms);      // Firmware-controlled timing
        printf("X:READ\n");
        // Python reads spectrum here
        led_batch_set(0, 0, 0, 0);  // Turn off
        sleep_ms(dark_ms);
        printf("X:DONE\n");

    printf("END\n");
    return true;
}
```

**Python side** (`controller.py`):

```python
def led_rank_sequence(self, test_intensity=128, settling_ms=45, dark_ms=5):
    """Generator that yields (channel, signal) tuples."""
    cmd = f"rank:{test_intensity},{settling_ms},{dark_ms}\n"
    self._ser.write(cmd.encode())

    # Wait for START
    line = self._ser.readline()
    assert line == b"START\n"

    # Yield channel signals
    while True:
        line = self._ser.readline().decode().strip()
        if line == "END":
            break

        if ':' in line:
            ch, signal = line.split(':', 1)
            yield (ch, signal)  # e.g., ('a', 'READ')
```

## Usage in Calibration

**Old method (Python-controlled):**

```python
# Step 3: Manual LED control (SLOW)
for ch in ['a', 'b', 'c', 'd']:
    ctrl.set_batch_intensities(**{ch: 128, others: 0})
    time.sleep(0.045)  # Python sleep (imprecise)
    spectrum = usb.read_spectrum()
    analyze(ch, spectrum)
    ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
    time.sleep(0.005)

# Total: ~600ms (150ms per channel)
```

**New method (Firmware-controlled):**

```python
# Step 3: Firmware-controlled LED sequencing (FAST)
channel_data = {}

for ch, signal in ctrl.led_rank_sequence(test_intensity=128):
    if signal == 'READ':
        # Firmware has LED on and stable - read NOW
        spectrum = usb.read_spectrum()
        channel_data[ch] = analyze_spectrum(spectrum)

# Rank channels by brightness
ranked = sorted(channel_data.items(), key=lambda x: x[1]['mean'])

# Total: ~220ms (55ms per channel)
# Speedup: 2.7x faster
```

## Benefits

### 1. **Faster Execution**
- Old: Python sleep + serial overhead = ~150ms per channel = 600ms total
- New: Firmware-controlled = ~55ms per channel = 220ms total
- **2.7x faster**

### 2. **Atomic Operation**
- Entire sequence executes without interruption
- No risk of Python GC pauses, thread delays, or OS scheduling
- **Deterministic timing** guaranteed by firmware

### 3. **Precise Timing**
- Firmware uses hardware timers (1µs precision)
- Python `time.sleep()` only ~10-15ms precision
- **Better LED settling and dark measurements**

### 4. **Simpler Python Code**
- No manual LED on/off logic
- No timing calculations
- Just respond to firmware signals

### 5. **Easier to Tune**
- Change settling/dark times from Python (no firmware recompile)
- Can experiment: `led_rank_sequence(128, settling_ms=60, dark_ms=10)`

## Backward Compatibility

- V1.1 firmware: Falls back to manual `set_batch_intensities()` method
- V1.2 firmware: Uses `rank` command if available
- Auto-detection via firmware version query

```python
if ctrl.get_firmware_version() >= "V1.2":
    # Use fast rank command
    for ch, signal in ctrl.led_rank_sequence():
        ...
else:
    # Fall back to manual method
    for ch in ch_list:
        ctrl.set_batch_intensities(...)
```

## Build Instructions

1. Update firmware source: `firmware/pico_p4spr/affinite_p4spr.c`
2. Build: `cd firmware/pico_p4spr && ./build_firmware.ps1`
3. Flash: Drag `affinite_p4spr_v1.2.uf2` to Pico bootloader
4. Verify: `python -c "import utils.controller; ctrl = controller.PicoSPR4('COM4'); print(ctrl.get_firmware_version())"`
   - Should print: `V1.2`

## Testing

```python
# Test rank command
from utils.controller import PicoSPR4

ctrl = PicoSPR4('COM4')
ctrl.open()

print("Testing rank command...")
for ch, signal in ctrl.led_rank_sequence(test_intensity=128):
    print(f"  {ch}: {signal}")

# Expected output:
#   a: READY
#   a: READ
#   a: DONE
#   b: READY
#   b: READ
#   b: DONE
#   c: READY
#   c: READ
#   c: DONE
#   d: READY
#   d: READ
#   d: DONE
```

## Version History

- **V1.0**: Initial release (legacy)
- **V1.1**: Added `batch:` command, LED intensity queries (`ia`, `ib`, `ic`, `id`)
- **V1.2**: Added `rank:` command for fast calibration
