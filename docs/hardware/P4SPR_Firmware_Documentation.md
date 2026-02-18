# P4SPR Firmware Documentation

## Device Information
- **Device**: P4SPR
- **Current Version**: V2.4
- **Hardware Platform**: Raspberry Pi Pico (RP2040)
- **License**: BSD-3-Clause

## Version History

### V2.4 - CYCLE_SYNC
- **Major Improvement**: Cycle synchronization - ONE `CYCLE_START` event per cycle instead of 4 READY events
- **Benefit**: 75% reduction in USB traffic compared to V2.3
- **Event Model**: ISR-to-main communication with cycle-level synchronization

### V2.3 - Ring Buffer Fix
- Ring buffer for READY events to prevent loss when printf blocks
- Improved event handling reliability

### V2.2
- Hardware timer-based LED sequencer (1kHz ISR)
- Autonomous LED cycling with precise timing
- Watchdog timer support

## Hardware Configuration

### Pin Assignments (GPIO)

#### SPR Core I/O
- `SERVO_PIN`: GPIO 0 - Polarizer servo control
- `LED_A_CTRL`: GPIO 28 - LED A PWM control
- `LED_B_CTRL`: GPIO 27 - LED B PWM control
- `LED_C_CTRL`: GPIO 22 - LED C PWM control (CRITICAL: Must be GPIO 22, not 26)
- `LED_D_CTRL`: GPIO 21 - LED D PWM control

#### Device I/O
- `DEV_OK`: GPIO 19 - Device status indicator
- `BOARD_LED`: GPIO 25 - Onboard Pico LED

#### I2C Bus 0
- `I2C0_SDA`: GPIO 12
- `I2C0_SCL`: GPIO 13
- **Connected Devices**:
  - Temperature sensor (0x48)
  - I/O Expander (0x20)

#### Spare/Future Pins
- `PICO_SPARE_1`: GPIO 26 (now available - LED_C moved to GPIO 22)
- `PICO_SPARE_2`: GPIO 18
- `POWER_BTN`: GPIO 17
- `PICO_SPARE_4`: GPIO 16

### PWM Configuration

#### Servo (Polarizer)
- **Frequency**: 50 Hz
- **PWM Divider**: 50
- **Slice**: 0, Channel: 0
- **Angle Range**: 5° - 175°
- **Default Speed**: 500ms
- **Speed Range**: 200ms - 2000ms

#### LED PWM
- **Frequency**: 400 Hz
- **PWM Divider**: 10
- **Wrap Value**: 65535 (maximum 16-bit for best resolution)
- **Brightness Range**: 0-255

| LED | GPIO | Slice | Channel |
|-----|------|-------|---------|
| A   | 28   | 6     | 0       |
| B   | 27   | 5     | 1       |
| C   | 22   | 3     | 0       |
| D   | 21   | 2     | 1       |

**Note**: PWM slice numbers work as-is despite seeming incorrect. Do NOT change them - `gpio_set_function()` handles the GPIO→slice mapping internally.

## Firmware Architecture

### Timer System

#### Timer 0: LED Sequencer (1kHz)
- **Callback**: `led_sequencer_callback()`
- **Purpose**: Autonomous LED cycling with precise timing
- **States**: LED_ON → SETTLE → READY_SENT → DARK
- **Event Generation**: `CYCLE_START` event at beginning of each cycle

#### Timer 1: Watchdog (1Hz)
- **Callback**: `watchdog_timer_callback()`
- **Timeout**: 120 seconds (default)
- **Purpose**: Prevent runaway firmware, auto-stop rankbatch if no keepalive

### Event System (V2.4)

The firmware uses ISR-to-main event queue for safe communication:

```c
volatile struct {
    bool cycle_start;        // Set by ISR when new cycle begins (LED_A turns on)
    uint32_t cycle_number;   // Current cycle number for verification
    bool batch_complete;     // Set when batch finishes
} isr_events;
```

**Event Flow**:
1. ISR sets `cycle_start` flag when LED_A turns on
2. Main loop detects flag and prints `CYCLE_START:N`
3. Flag is cleared
4. One event per complete ABCD cycle (75% less traffic than V2.3)

### Flash Memory Storage

- **Offset**: `PICO_FLASH_SIZE_BYTES - FLASH_SECTOR_SIZE`
- **Contents**:
  - Byte 0: S position (servo)
  - Byte 1: P position (servo)
  - Byte 2-5: Reserved/padding

## Command Reference

### Format
- Commands are newline-terminated ASCII strings
- Responses: `ACK` (6) or `NAK` (1)
- Case-sensitive for LED identifiers (a, b, c, d)

### Information Commands

#### `id` - Device Identification
```
Command: id
Response: P4SPR V2.4
```
Powers on device and returns device name and version.

#### `iv` - Version Only
```
Command: iv
Response: V2.4
```
Returns firmware version string.

#### `it` - Temperature Reading
```
Command: it
Response: 25.38
```
Reads and returns temperature from I2C sensor (0x48) in Celsius.

#### `ib` - Reboot to Bootloader
```
Command: ib
Response: 6 (ACK)
```
Reboots device into BOOTSEL mode for firmware updates. Device appears as mass storage device.

#### `ix` - Debug: ISR Status
```
Command: ix
Response: 6 (ACK)
         CYCLE:42 ACTIVE:1
```
Returns cycle counter and sequencer status (debug feature).

### Device Control

#### `do` - Device Off
```
Command: do
Response: 6 (ACK)
```
Turns off device power and stops all fluidic operations.

#### `du` - Direct USB Boot
```
Command: du
Response: (none - immediate reboot)
```
Immediate reboot to BOOTSEL mode.

### LED Commands

#### `l[a|b|c|d]` - Single LED On
```
Command: la
Response: 6 (ACK)
```
Turns on specified LED at current brightness level. LEDs: a, b, c, d.

#### `lx` - All LEDs Off
```
Command: lx
Response: 6 (ACK)
```
Fast turn-off for all LEDs (disables PWM).

#### `lm:LED1,LED2,...` - Multi-LED On
```
Command: lm:a,c,d
Response: 6 (ACK)
```
Turns on multiple LEDs simultaneously. Accepts comma-separated list.

#### `b[a|b|c|d]NNN` - Set LED Brightness
```
Command: ba128
Response: 6 (ACK)
```
Sets brightness for specified LED (0-255). Format: `b` + LED + 3-digit brightness.

Examples:
- `ba255` - LED A full brightness
- `bc000` - LED C off
- `bd128` - LED D half brightness

#### `batch:AAA,BBB,CCC,DDD` - Atomic Multi-LED Brightness
```
Command: batch:255,128,064,000
Response: 6 (ACK)
```
Sets all four LED brightness values atomically. Each value is 0-255.

**Optimization**: If all values are zero, uses fast turn-off path.

### Advanced LED Sequencing

#### `rankbatch:A,B,C,D,SETTLE,DARK,CYCLES` - Batch LED Cycling
```
Command: rankbatch:255,200,180,150,245,5,100
Response: 6 (ACK)
```

Autonomous LED cycling with hardware timer. Cycles through LEDs A→B→C→D repeatedly.

**Parameters**:
- `A, B, C, D`: LED intensities (0-255)
- `SETTLE`: Settling time in ms (10-1000, default 245)
- `DARK`: Dark period between LEDs in ms (0-100, default 5)
- `CYCLES`: Number of complete ABCD cycles (1-10000)

**Event Stream** (V2.4):
```
CYCLE_START:1
CYCLE_START:2
CYCLE_START:3
...
CYCLE_START:100
BATCH_COMPLETE
```

**Timing per LED**:
1. LED turns on at specified intensity
2. Settle period (default 245ms)
3. `CYCLE_START` event sent (only for LED A)
4. Dark period (default 5ms)
5. Next LED

**V2.4 Improvement**: Only ONE `CYCLE_START` event per complete cycle (when LED A turns on), not 4 READY events. This reduces USB traffic by 75%.

#### `rank:INTENSITY,SETTLE,DARK` - Legacy Single-Intensity Sequence
```
Command: rank:255,245,5
Response: 6 (ACK)
```
Backward-compatible rank command. All LEDs use same intensity.

#### `stop` - Stop Rankbatch
```
Command: stop
Response: 6 (ACK)
```
Immediately halts ongoing rankbatch sequence and turns off all LEDs.

### Servo Commands

#### `ss` - Move to S Position
```
Command: ss
Response: 6 (ACK)
```
Moves servo to stored S position.

#### `sp` - Move to P Position
```
Command: sp
Response: 6 (ACK)
```
Moves servo to stored P position.

#### `servo_speed:####` - Set Servo Speed
```
Command: servo_speed:1000
Response: 6 (ACK)
```
Sets servo pulse duration in milliseconds (200-2000ms). Default: 500ms.

**Examples**:
- `servo_speed:200` - Fast movement (200ms)
- `servo_speed:500` - Default speed
- `servo_speed:2000` - Slow movement (2s)

#### `svSSSppp` - Set S and P Positions
```
Command: sv030120
Response: 6 (ACK)
```
Sets S position (degrees 0-179) and P position (degrees 0-179). Format: `sv` + 3-digit S + 3-digit P.

Example: `sv030120` sets S=30°, P=120°

#### `sf` - Flash Servo Settings
```
Command: sf
Response: 6 (ACK)
```
Writes current S and P positions to flash memory for persistence.

#### `sr` - Read Servo Settings
```
Command: sr
Response: S:30 P:120
```
Reads and displays current S and P positions from flash.

### Watchdog Commands (V2.4.1)

#### `ka` - Keepalive
```
Command: ka
Response: 6 (ACK)
```
Resets watchdog timer. Must be sent within 120 seconds during rankbatch operations to prevent auto-stop.

**Use Case**: Long rankbatch sequences where host software needs to maintain control.

## Function Reference

### Setup Functions

#### `void affinite_setup(void)`
Initializes all GPIO pins, I2C buses, PWM channels, and peripherals.

#### `bool check_flash(void)`
Verifies flash memory contains valid servo calibration data. Returns `true` if valid.

### LED Functions

#### `void led_setup(void)`
Configures LED PWM channels and initializes hardware.

#### `bool led_on(char ch_led)`
Turns on specified LED (a, b, c, d, or x for all off). Returns `true` on success.

#### `bool led_multi_on(const char* leds, uint8_t count)`
Turns on multiple LEDs from comma-separated string. Returns `true` on success.

#### `uint8_t led_brightness(char ch_led, uint8_t brightness)`
Sets LED brightness (0-255). Returns the brightness value set.

#### `bool led_rank_sequence(uint8_t intensity, uint16_t settling_ms, uint16_t dark_ms)`
Legacy rank sequence with single intensity. Returns `true` on success.

#### `bool led_rank_batch_cycles(uint8_t int_a, uint8_t int_b, uint8_t int_c, uint8_t int_d, uint16_t settling_ms, uint16_t dark_ms, uint16_t num_cycles)`
Initiates batch cycling with individual LED intensities. Returns `true` on success.

### Timer-Based Rankbatch Functions (V2.2+)

#### `bool led_sequencer_callback(struct repeating_timer *t)`
1kHz ISR callback for LED sequencer. Manages LED state machine and timing.

**State Machine**:
- Phase 0: LED_ON - Turn on current LED
- Phase 1: SETTLE - Wait for settling time
- Phase 2: READY_SENT - Event sent, continue settling
- Phase 3: DARK - Dark period before next LED

#### `void rankbatch_start(uint8_t ia, uint8_t ib, uint8_t ic, uint8_t id, uint16_t settle_ms, uint16_t dark_ms, uint16_t n_cycles)`
Starts timer-based rankbatch sequence. Non-blocking - runs in ISR.

#### `void rankbatch_stop(void)`
Immediately stops rankbatch sequence and disables all LEDs.

### Watchdog Functions (V2.4.1)

#### `bool watchdog_timer_callback(struct repeating_timer *t)`
1Hz ISR callback for watchdog timer. Checks for timeout and auto-stops rankbatch if needed.

**Behavior**:
- If watchdog enabled and timeout exceeded, automatically calls `rankbatch_stop()`
- Timeout reset by `ka` (keepalive) command

### Servo Functions

#### `void pwm_servo_setup(void)`
Initializes servo PWM at 50Hz.

#### `void move_servo(double duty)`
Moves servo to specified duty cycle (0.0-1.0).

#### `double get_servo_duty(uint8_t deg)`
Converts angle (5-175°) to PWM duty cycle.

**Calibration Formula**:
```c
duty = (angle * (p - s) + (s * 180 - 5 * p)) / (175 * 180)
```
Where `s` and `p` are calibration points stored in flash.

#### `bool servo_flash(uint8_t s, uint8_t p)`
Writes servo calibration to flash. Returns `true` on success.

#### `void servo_read(void)`
Reads and prints servo calibration from flash.

### Device Functions

#### `void device_setup(void)`
Initializes device power control GPIO.

#### `void device_on(void)`
Enables device power.

#### `void device_off(void)`
Disables device power and shuts down fluidics.

## Important Notes

### LED_C GPIO Critical Configuration
**LED_C MUST use GPIO 22 (Slice 3), NOT GPIO 26 (Slice 5)**

- GPIO 26 on Slice 5 conflicts with LED_B on GPIO 27
- This was a critical bug fix in earlier versions
- GPIO 26 is now available as spare pin

### PWM Slice Mapping
The slice numbers in the firmware work correctly despite appearing incorrect:
```c
const uint LED_A_SLICE = 6;  // GPIO 28
const uint LED_B_SLICE = 5;  // GPIO 27
const uint LED_C_SLICE = 3;  // GPIO 22
const uint LED_D_SLICE = 2;  // GPIO 21
```
**Do not modify these values** - the SDK handles GPIO-to-slice mapping internally.

### Event Queue Timing (V2.4)
- ISR sets flags, main loop prints messages
- Prevents printf() blocking in ISR context
- One `CYCLE_START` event per complete ABCD cycle
- Dramatically reduces USB bandwidth usage

### Flash Memory Persistence
- Servo positions persist across reboots
- First boot after fresh firmware: defaults written (S=30, P=120)
- Board LED flashes differently on first boot vs. subsequent boots

### Watchdog Behavior
- Disabled by default
- Enabled automatically during rankbatch
- 120-second timeout
- Host must send `ka` command to prevent auto-stop

## Typical Usage Patterns

### Basic LED Control
```
Command: la          # Turn on LED A
Command: ba255       # Set LED A to full brightness
Command: lx          # Turn all LEDs off
```

### Multi-LED Simultaneous Control
```
Command: batch:255,200,150,100   # Set all 4 LEDs at once
Command: lm:a,b,c                # Turn on LEDs A, B, C
```

### Automated Measurement Sequence
```
Command: rankbatch:255,200,180,150,245,5,100
# Wait for CYCLE_START events
# After 100 cycles: BATCH_COMPLETE
```

### Servo Calibration
```
Command: sv030120    # Set S=30°, P=120°
Command: sf          # Save to flash
Command: sr          # Verify: S:30 P:120
Command: ss          # Move to S position
Command: sp          # Move to P position
```

### Long-Running Measurement with Keepalive
```
Command: rankbatch:255,255,255,255,245,5,5000  # 5000 cycles
# Host sends 'ka' every 60 seconds to prevent timeout
# Firmware continues until completion or timeout
```

## Debugging

### Enable Debug Output
Debug output is controlled by compile-time constant:
```c
const bool debug = false;
```
Set to `true` and recompile for verbose diagnostic output.

### ISR Debug Command
```
Command: ix
Response: 6
         CYCLE:42 ACTIVE:1
```
Shows current cycle number and sequencer active state.

### Temperature Monitoring
```
Command: it
Response: 25.38
```
Monitor device temperature during operation.

## Error Handling

### Response Codes
- `ACK` (6): Command successful
- `NAK` (1): Command failed or invalid

### Common Error Scenarios
1. **Command parse error**: Invalid format → NAK
2. **Parameter out of range**: Values clamped to valid range, ACK returned
3. **Flash write failure**: NAK returned from `sf` command
4. **I2C timeout**: Temperature read may fail silently
5. **Watchdog timeout**: Rankbatch auto-stops after 120s without keepalive

### Recovery Procedures
- **Hung state**: Send `stop` command to halt rankbatch
- **Unknown state**: Send `do` (device off) then `id` (device on)
- **Flash corruption**: Send `sv030120` and `sf` to restore defaults
- **Firmware crash**: Power cycle device or send `ib` (bootloader reboot)

## Performance Characteristics

### Event Generation Rate (V2.4)
- **V2.3 and earlier**: 4 READY events per cycle (one per LED)
- **V2.4**: 1 CYCLE_START event per cycle
- **Improvement**: 75% reduction in USB traffic

### Timing Precision
- **LED sequencer**: ±1ms (1kHz ISR)
- **Watchdog**: ±1s (1Hz ISR)
- **Settling time range**: 10-1000ms
- **Dark period range**: 0-100ms

### Maximum Throughput
- **Fastest cycle**: ~20ms (4 LEDs × 5ms dark, no settling)
- **Typical cycle**: ~1000ms (4 LEDs × 245ms settle + 5ms dark)
- **Maximum batch**: 10000 cycles (configurable limit)

## Compatibility Notes

### P4PRO Compatibility
P4SPR firmware is designed for SPR devices. For P4PRO devices with fluidic control (pumps, valves), use P4PRO firmware (separate documentation).

### Software Integration
- Communicates via USB CDC (virtual serial port)
- Baud rate: Auto-detected by Pico USB stack
- Line termination: `\n` (LF)
- Character encoding: ASCII
- Buffer size: 64 bytes

### Firmware Update Procedure
1. Send `ib` command (or power on while holding BOOTSEL button)
2. Device appears as USB mass storage "RPI-RP2"
3. Copy `.uf2` firmware file to device
4. Device automatically reboots with new firmware

---

**Document Version**: 1.0  
**Last Updated**: February 2, 2026  
**Firmware Version**: V2.4  
**Author**: Lucia Iannantuono  
**Copyright**: © 2022 Affinite Instruments
