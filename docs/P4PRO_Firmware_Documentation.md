# P4PRO Firmware Documentation

## Device Information
- **Device**: P4PRO
- **Current Version**: V2.3
- **Hardware Platform**: Raspberry Pi Pico (RP2040)
- **License**: BSD-3-Clause

## Version History

### V2.3 - Latest
- GPIO verification for six-port valve operations
- Enhanced valve state confirmation
- Improved reliability for critical fluidic operations

### V2.2
- Added `leds:A:X,B:Y,C:Z,D:W` command for atomic multi-LED brightness control
- Enhanced LED control API for simultaneous multi-LED operations
- Improved LED hardware configuration structure

### V2.1
- Added `servo:ANGLE,DURATION` command for polarizer calibration
- Servo speed control (200-2000ms duration)
- Compatible with P4SPR v2.4.1 servo calibration tools

### V2.0 - Major Modernization
- Hardware timer-based LED sequencer (1kHz ISR)
- Rankbatch command with autonomous ISR-driven LED cycling
- Watchdog timer with 120s timeout and keepalive support
- Valve and pump cycle tracking for maintenance prediction
- Six-port valve rate limiting protection (0.5 Hz max per manufacturer spec)
- Three-way valve rate limiting (1 Hz max to prevent overheating)
- Thermal protection with shutdown at 70°C
- I2C timeout protection to prevent firmware lockup
- Flow sensor support removed (obsolete)

## Hardware Configuration

### Pin Assignments (GPIO)

#### SPR Core I/O
- `SERVO_PIN`: GPIO 0 - Polarizer servo control
- `LED_A_CTRL`: GPIO 28 - LED A PWM control
- `LED_B_CTRL`: GPIO 27 - LED B PWM control
- `LED_C_CTRL`: GPIO 26 - LED C PWM control
- `LED_D_CTRL`: GPIO 21 - LED D PWM control

#### Kinetic I/O (Fluidic Control)
- `THREE_WAY_1`: GPIO 3 - Three-way valve 1 control
- `SIX_PORT_1`: GPIO 4 - Six-port valve 1 control
- `THREE_WAY_2`: GPIO 6 - Three-way valve 2 control
- `SIX_PORT_2`: GPIO 5 - Six-port valve 2 control
- `PUMP_STBY`: GPIO 7 - Pump standby control
- `PUMP_EN_1`: GPIO 8 - Pump 1 enable
- `PUMP_STCK_1`: GPIO 9 - Pump 1 step clock
- `PUMP_EN_2`: GPIO 14 - Pump 2 enable
- `PUMP_STCK_2`: GPIO 15 - Pump 2 step clock

#### Device I/O
- `PWR_SENSE`: GPIO 1 - Power sensing
- `PWR_ENABLE`: GPIO 2 - Power enable control
- `FAN_EN`: GPIO 20 - Cooling fan enable
- `DEV_OK`: GPIO 19 - Device status indicator
- `BOARD_LED`: GPIO 25 - Onboard Pico LED

#### I2C Bus 0
- `I2C0_SDA`: GPIO 12
- `I2C0_SCL`: GPIO 13
- **Connected Devices**:
  - Temperature sensor (0x48)
  - I/O Expander (0x20)

#### I2C Bus 1
- `I2C1_SDA`: GPIO 10
- `I2C1_SCL`: GPIO 11

#### Spare/Future Pins
- `PICO_SPARE_1`: GPIO 19 (may be reassigned)
- `PICO_SPARE_2`: GPIO 18
- `POWER_BTN`: GPIO 17 - Physical power button
- `MAGLOCK`: GPIO 16 - Magnetic lock control

### PWM Configuration

#### Servo (Polarizer)
- **Frequency**: 50 Hz
- **PWM Divider**: 50
- **Slice**: 0, Channel: 0
- **Angle Range**: 5° - 175°
- **Default Speed**: 500ms
- **Speed Range**: 200ms - 2000ms (V2.1+)

#### LED PWM
- **Frequency**: 400 Hz
- **PWM Divider**: 10
- **Wrap Value**: 65535 (**CRITICAL** - use maximum 16-bit value for proper resolution)
- **Brightness Range**: 0-255

| LED | GPIO | Slice | Channel |
|-----|------|-------|---------|
| A   | 28   | 6     | 0       |
| B   | 27   | 5     | 1       |
| C   | 26   | 3     | 0       |
| D   | 21   | 2     | 1       |

#### Three-Way Valves
- **Frequency**: 20 kHz
- **Duty Cycle**: 35%
- **Pulse Duration**: 800ms (configurable via `THREE_WAY_DELAY`)
- **Rate Limiting**: 1 second minimum between operations (prevents overheating)

| Valve | GPIO | Slice | Channel |
|-------|------|-------|---------|
| 1     | 3    | 1     | 1       |
| 2     | 6    | 3     | 0       |

#### Pumps (Stepper Motors)
- **PWM Divider**: 100
- **Duty Cycle**: 50%
- **Rate Range**: 220 Hz (default for both pumps)
- **Maximum Frequency**: 1000 Hz

| Pump | Enable GPIO | Clock GPIO | Slice | Channel |
|------|-------------|------------|-------|---------|
| 1    | 8           | 9          | 4     | 1       |
| 2    | 14          | 15         | 7     | 1       |

## Firmware Architecture

### Timer System

#### Timer 0: LED Sequencer (1kHz)
- **Callback**: `led_sequencer_callback()`
- **Purpose**: Autonomous LED cycling with precise timing
- **States**: LED_ON → SETTLE → DARK
- **Event Generation**: READY events for each LED during settling phase

#### Timer 1: Watchdog (1Hz)
- **Callback**: `watchdog_timer_callback()`
- **Timeout**: 120 seconds (default)
- **Purpose**: Auto-stop rankbatch if no keepalive received

### Event System

```c
volatile struct {
    uint8_t ready_led;       // 0-3 for a-d, 255 = no event
    uint16_t cycle_num;      // For CYCLE events
    bool batch_complete;     // Batch completion flag
    uint32_t ready_count;    // Debug: event counter
} isr_events;
```

**Event Flow**:
1. ISR sets `ready_led` during LED settling phase
2. Main loop detects and prints `READY:X`
3. Flag is cleared to 255
4. Process repeats for each LED in sequence

### Flash Memory Storage

- **Offset**: `PICO_FLASH_SIZE_BYTES - FLASH_SECTOR_SIZE`
- **Contents**:
  - Byte 0: S position (servo)
  - Byte 1: P position (servo)
  - Byte 2: Pump mode flag
  - Byte 3: Pump 1 correction factor
  - Byte 4: Pump 2 correction factor
  - Byte 5: CRC checksum

### Rate Limiting System

#### Six-Port Valves (V2.0+)
- **Minimum Interval**: 2000ms (0.5 Hz max)
- **Reason**: Manufacturer specification to prevent mechanical damage
- **Implementation**: Timestamp tracking with enforcement

```c
const uint32_t SIX_PORT_MIN_INTERVAL = 2000;  // 2 seconds
uint32_t six_1_last_op = 0;
uint32_t six_2_last_op = 0;
```

#### Three-Way Valves (V2.0+)
- **Minimum Interval**: 1000ms (1 Hz max)
- **Reason**: Prevent coil overheating
- **Implementation**: Timestamp tracking with enforcement

```c
const uint32_t THREE_WAY_MIN_INTERVAL = 1000;  // 1 second
uint32_t thr_1_last_op = 0;
uint32_t thr_2_last_op = 0;
```

### Cycle Tracking System (V2.0+)

Track component usage for maintenance prediction:

```c
uint32_t thr_1_cycles = 0;      // Three-way valve 1
uint32_t thr_2_cycles = 0;      // Three-way valve 2
uint32_t six_1_cycles = 0;      // Six-port valve 1
uint32_t six_2_cycles = 0;      // Six-port valve 2
uint32_t pump_1_cycles = 0;     // Pump 1
uint32_t pump_2_cycles = 0;     // Pump 2
```

**Overflow Warning**: Alert generated when any counter exceeds 4,000,000,000 (93% of uint32_t max).

### Thermal Protection (V2.0+)

```c
const float THERMAL_SHUTDOWN_TEMP = 70.0;   // Emergency shutdown
const float THERMAL_WARNING_TEMP = 60.0;    // Warning threshold
```

**Behavior**:
- **60°C**: Warning message printed
- **70°C**: Emergency shutdown - all systems disabled
- **Recovery**: Allowed when temperature drops 5°C below warning threshold

## Command Reference

### Format
- Commands are newline-terminated ASCII strings
- Responses: `ACK` (1) or `NAK` (0)
- Note: P4PRO uses different ACK/NAK values than P4SPR

### Information Commands

#### `id` - Device Identification
```
Command: id
Response: P4PRO V2.3
```
Powers on device and returns device name and version.

#### `iv` - Version Only
```
Command: iv
Response: V2.3
```
Returns firmware version string.

#### `it` - Temperature Reading
```
Command: it
Response: 25.38
```
Reads temperature from I2C sensor with timeout protection.

#### `ib` - Reboot to Bootloader
```
Command: ib
Response: 1 (ACK)
```
Reboots device into BOOTSEL mode for firmware updates.

#### `dbg` - Toggle Debug Mode
```
Command: dbg
Response: 1 (ACK)
```
Runtime toggle for debug output. Default: disabled.

### Device Control

#### `do` - Device Off
```
Command: do
Response: 1 (ACK)
```
Emergency shutdown - stops all fluidic operations, disables pumps, closes valves, turns off LEDs.

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
Response: 1 (ACK)
```
Turns on specified LED at current brightness level.

#### `lx` - All LEDs Off
```
Command: lx
Response: 1 (ACK)
```
Turns off all LEDs immediately.

#### `l[a|b|c|d]:NNN` - LED with Brightness (V2.2+)
```
Command: la:255
Command: lb:128
Response: 1 (ACK)
```
Turn on LED with specified brightness (0-255) in single command.

#### `leds:A:X,B:Y,C:Z,D:W` - Atomic Multi-LED Control (V2.2+)
```
Command: leds:A:255,B:200,C:150,D:100
Response: 1 (ACK)
```
Set multiple LEDs with individual brightness values atomically. Format: `leds:LED1:VAL1,LED2:VAL2,...`

**Features**:
- Specify any combination of LEDs (1-4)
- Order doesn't matter
- Case insensitive LED identifiers
- Each LED: brightness 0-255

**Examples**:
```
leds:A:255,D:128           # Only A and D
leds:B:200,C:200,D:200     # B, C, D at same brightness
leds:A:255,B:255,C:255,D:255  # All LEDs full brightness
```

#### `lm:LED1,LED2,...` - Multi-LED On
```
Command: lm:a,c,d
Response: 1 (ACK)
```
Turns on multiple LEDs at current brightness. Comma-separated list.

#### `b[a|b|c|d]NNN` - Set LED Brightness
```
Command: ba255
Response: 1 (ACK)
```
Sets brightness for specified LED (0-255). Format: `b` + LED + 3-digit brightness.

### Advanced LED Sequencing

#### `rankbatch:A,B,C,D,SETTLE,DARK,CYCLES` - Batch LED Cycling
```
Command: rankbatch:255,200,180,150,245,5,100
Response: 1 (ACK)
```

Autonomous timer-based LED cycling. Same as P4SPR but with P4PRO-specific event format.

**Parameters**:
- `A, B, C, D`: LED intensities (0-255)
- `SETTLE`: Settling time in ms (10-1000)
- `DARK`: Dark period in ms (0-100)
- `CYCLES`: Number of ABCD cycles (1-10000)

**Event Stream**:
```
READY:a
READY:b
READY:c
READY:d
READY:a
READY:b
...
BATCH_COMPLETE
```

#### `stop` - Stop Rankbatch
```
Command: stop
Response: 1 (ACK)
```
Immediately halts rankbatch sequence.

### Servo Commands

#### `servo:ANGLE,DURATION` - Calibrated Servo Move (V2.1+)
```
Command: servo:90,500
Response: 1 (ACK)
```
Move servo to specified angle with specified speed.

**Parameters**:
- `ANGLE`: Target angle (5-175°)
- `DURATION`: Movement duration in ms (200-2000)

**Examples**:
```
servo:30,500    # Move to 30° in 500ms
servo:120,1000  # Move to 120° in 1 second
servo:90,200    # Fast move to 90°
```

**Behavior**: Command blocks for `DURATION` ms to allow servo to reach position.

#### `ss` - Move to S Position
```
Command: ss
Response: 1 (ACK)
```
Moves servo to stored S position.

#### `sp` - Move to P Position
```
Command: sp
Response: 1 (ACK)
```
Moves servo to stored P position.

#### `svSSSppp` - Set S and P Positions
```
Command: sv030120
Response: 1 (ACK)
```
Sets S and P calibration positions. Format: `sv` + 3-digit S + 3-digit P.

#### `sf` - Flash Servo Settings
```
Command: sf
Response: 1 (ACK)
```
Writes servo calibration and pump corrections to flash.

#### `sr` - Read Servo Settings
```
Command: sr
Response: S:30 P:120
```
Displays current servo calibration from flash.

### Valve Commands

#### `v3XY` - Three-Way Valve Control
```
Command: v310
Command: v321
Response: 1 (ACK)
```
Control three-way valves with rate limiting.

**Format**: `v3` + valve_number + state
- `X`: Valve number (1, 2, or 3 for both)
- `Y`: State (0 = off, 1 = on)

**Examples**:
```
v310   # Three-way valve 1 off
v311   # Three-way valve 1 on
v320   # Three-way valve 2 off
v330   # Both valves off
```

**Rate Limiting**: Minimum 1 second between operations to prevent overheating.

#### `v6XY` - Six-Port Valve Control (V2.3: GPIO Verified)
```
Command: v611
Command: v620
Response: 1 (ACK) or 0 (NAK if GPIO verification fails)
```
Control six-port valves with rate limiting and GPIO verification.

**Format**: `v6` + valve_number + state
- `X`: Valve number (1, 2, or 3 for both)
- `Y`: State (0 = position A, 1 = position B)

**Examples**:
```
v610   # Six-port valve 1 to position A
v611   # Six-port valve 1 to position B
v620   # Six-port valve 2 to position A
v630   # Both valves to position A
```

**Rate Limiting**: Minimum 2 seconds between operations (manufacturer spec).

**V2.3 Enhancement**: GPIO verification after state change. NAK returned if verification fails.

#### `vc` - Read Valve Cycle Counts
```
Command: vc
Response: 1234,5678,9012,3456
```
Returns cycle counts: `thr_1,thr_2,six_1,six_2`

Use for maintenance prediction and component lifecycle tracking.

### Pump Commands

#### `prXNNN` - Run Pump
```
Command: pr1220
Command: pr2220
Response: 1 (ACK)
```
Start pump at specified rate.

**Format**: `pr` + pump_number + 3-digit rate
- `X`: Pump number (1, 2, or 3 for both)
- `NNN`: Rate in Hz (220 typical, 1000 max)

**Examples**:
```
pr1220   # Pump 1 at 220 Hz
pr2220   # Pump 2 at 220 Hz
pr3220   # Both pumps at 220 Hz
pr1500   # Pump 1 at 500 Hz (faster)
```

**Behavior**: 
- Pump enabled and PWM started
- Cycle counter incremented
- Pump runs until `ps` command received

#### `psX` - Stop Pump
```
Command: ps1
Command: ps2
Response: 1 (ACK)
```
Stop specified pump.

**Format**: `ps` + pump_number
- `X`: Pump number (1, 2, or 3 for both)

**Examples**:
```
ps1   # Stop pump 1
ps2   # Stop pump 2
ps3   # Stop both pumps
```

#### `pcc` - Read Pump Cycle Counts
```
Command: pcc
Response: 12345,67890
```
Returns cycle counts: `pump_1,pump_2`

#### `pc` - Read Pump Corrections
```
Command: pc
Response: AB
```
Returns pump correction factors from flash (bytes 3-4).

#### `pfXY` - Flash Pump Corrections
```
Command: pf12
Response: (none)
```
Writes pump correction factors to flash.

**Format**: `pf` + correction_pump1 + correction_pump2

## Function Reference

### Setup Functions

#### `void affinite_setup(void)`
Initializes all GPIO pins, I2C buses, PWM channels, kinetic systems, and peripherals.

#### `bool check_flash(void)`
Verifies flash contains valid data using CRC checksum. Returns `true` if valid.

### LED Functions

#### `void led_setup(void)`
Configures LED PWM and hardware structure.

**LED Hardware Structure** (V2.2+):
```c
typedef struct {
    uint gpio_pin;
    uint pwm_slice;
    uint pwm_channel;
    uint16_t* level_ptr;
} led_hw_t;

static led_hw_t led_hw[4];  // Initialized for all 4 LEDs
```

#### `bool led_on(char ch_led)`
Turns on LED (a/b/c/d) or all off (x). Returns `true` on success.

#### `bool led_multi_on(const char* leds, uint8_t count)`
Turns on multiple LEDs from string. Returns `true` on success.

#### `void led_all_off(void)`
Immediately disables all LED PWM channels.

#### `uint8_t led_brightness(char ch_led, uint8_t brightness)`
Sets LED brightness (0-255). Returns brightness value.

#### `static int get_led_idx(char ch)`
Internal helper: Converts LED character (a/b/c/d) to array index (0-3).

### Timer-Based Rankbatch Functions

#### `bool led_sequencer_callback(struct repeating_timer *t)`
1kHz ISR for LED sequencer state machine.

**State Machine**:
- Phase 0: LED_ON - Turn on current LED at specified intensity
- Phase 1: SETTLE - Wait for settling time, send READY event
- Phase 2: DARK - Dark period before next LED

**Cycle Management**:
- Increments `current_led` (0→1→2→3→0)
- Increments `current_cycle` when returning to LED A
- Sets `batch_complete` flag when all cycles done

#### `bool watchdog_timer_callback(struct repeating_timer *t)`
1Hz ISR for watchdog.

**Logic**:
- If inactive: Do nothing
- If active: Increment `seconds_since_keepalive`
- If timeout exceeded: Stop rankbatch, disable watchdog

#### `void rankbatch_start(uint8_t ia, uint8_t ib, uint8_t ic, uint8_t id, uint16_t settle_ms, uint16_t dark_ms, uint16_t n_cycles)`
Initializes sequencer state and activates timer.

**Side Effects**:
- Enables LED sequencer
- Enables watchdog timer
- Resets cycle counters

#### `void rankbatch_stop(void)`
Emergency stop for rankbatch.

**Actions**:
- Disables sequencer
- Disables watchdog
- Turns off all LEDs
- Resets state machine

### Servo Functions

#### `void pwm_servo_setup(void)`
Initializes servo PWM at 50Hz.

#### `void move_servo(double duty)`
Moves servo to duty cycle (0.0-1.0).

#### `double get_servo_duty(uint8_t deg)`
Converts angle to duty cycle using flash calibration.

#### `bool flash(uint8_t s, uint8_t p, uint8_t is_pump, uint8_t pump_1_correction, uint8_t pump_2_correction)`
Writes all calibration data to flash with CRC. Returns `true` on success.

**Flash Layout**:
```
Byte 0: S position
Byte 1: P position
Byte 2: Pump mode flag
Byte 3: Pump 1 correction
Byte 4: Pump 2 correction
Byte 5: CRC-8 checksum
```

#### `void servo_read(void)`
Reads and prints servo calibration.

### Device Functions

#### `void device_setup(void)`
Initializes power control, fan, and device I/O.

#### `void device_on(void)`
Enables device power and cooling fan.

#### `void device_off(void)`
**Emergency Shutdown**:
- Stops all pumps
- Closes all valves
- Turns off all LEDs
- Disables power
- Stops fan

### Kinetic Functions

#### `void kinetic_setup(void)`
Initializes all fluidic control hardware (valves and pumps).

#### `bool six_port(char ch, char state)`
Controls six-port valves with rate limiting and GPIO verification.

**Parameters**:
- `ch`: Valve channel ('1', '2', or '3' for both)
- `state`: '0' (position A) or '1' (position B)

**Returns**: `true` if GPIO verification successful (V2.3+), `false` otherwise.

**Rate Limiting**: Enforces 2-second minimum interval.

**V2.3 GPIO Verification**:
1. Set GPIO state
2. Wait 50ms for valve to respond
3. Read back GPIO state
4. Compare with expected state
5. Return verification result

#### `void three_way(char ch, char state)`
Controls three-way valves with rate limiting.

**Parameters**:
- `ch`: Valve channel ('1', '2', or '3' for both)
- `state`: '0' (off) or '1' (on)

**Implementation**:
- Sets PWM at 20kHz, 35% duty for 800ms
- Uses hardware timer callback for auto-shutoff
- Prevents overheating with rate limiting

#### `int64_t three_way_callback_1(alarm_id_t id, void* user_data)`
Timer callback to turn off three-way valve 1 after pulse duration.

#### `int64_t three_way_callback_2(alarm_id_t id, void* user_data)`
Timer callback to turn off three-way valve 2 after pulse duration.

#### `bool run_pump(char ch, int rate)`
Starts pump at specified frequency.

**Parameters**:
- `ch`: Pump channel ('1', '2', or '3' for both)
- `rate`: PWM frequency in Hz (220 typical, 1000 max)

**Returns**: `true` on success.

**Actions**:
- Enables pump
- Sets PWM frequency
- Increments cycle counter
- Disables standby mode

#### `bool stop_pump(char ch)`
Stops pump and disables PWM.

**Parameters**:
- `ch`: Pump channel ('1', '2', or '3' for both)

**Returns**: `true` on success.

### Utility Functions

#### `int i2c_read_timeout_safe(i2c_inst_t *i2c, uint8_t addr, uint8_t *dst, size_t len, bool nostop)`
I2C read with 50ms timeout protection. Returns bytes read or -1 on timeout.

**Purpose**: Prevents firmware lockup if I2C device hangs.

#### `int i2c_write_timeout_safe(i2c_inst_t *i2c, uint8_t addr, const uint8_t *src, size_t len, bool nostop)`
I2C write with 50ms timeout protection. Returns bytes written or -1 on timeout.

#### `uint8_t calculate_flash_crc(void)`
Calculates CRC-8 checksum over first 5 flash bytes for integrity verification.

**Polynomial**: 0x31 (CRC-8)

#### `void check_thermal_limits(void)`
Monitors temperature and triggers thermal protection.

**Thresholds**:
- **≥70°C**: Emergency shutdown, print `!THERMAL_SHUTDOWN:XX.XX`
- **≥60°C**: Warning, print `!THERMAL_WARNING:XX.XX`
- **<55°C** (after shutdown): Allow recovery, print `!THERMAL_RECOVERY:XX.XX`

#### `void check_cycle_overflow(void)`
Checks all cycle counters and warns if approaching uint32_t overflow.

**Threshold**: 4,000,000,000 (93% of max)

**Output**: `!CYCLE_OVERFLOW_WARNING`

## Important Notes

### LED_WRAP Critical Value
**LED_WRAP MUST be 65535** (maximum 16-bit value)

```c
const uint16_t LED_WRAP = 65535;  // DO NOT use calculated value
```

Using calculated wrap value causes LED control issues. Always use maximum 16-bit value for proper PWM resolution.

### Six-Port Valve Rate Limiting
**CRITICAL**: Six-port valves limited to 0.5 Hz (one operation per 2 seconds) per manufacturer specification. Exceeding this rate can cause mechanical damage.

Firmware enforces this automatically - requests within the interval are still processed but timing is tracked.

### Three-Way Valve Thermal Protection
Three-way valves use 20kHz PWM at 35% duty for 800ms. Rate limiting (1 Hz max) prevents coil overheating.

### I2C Timeout Protection
All I2C operations use timeout-safe wrappers to prevent firmware lockup if sensors hang or disconnect.

```c
i2c_read_timeout_safe()   // 50ms timeout
i2c_write_timeout_safe()  // 50ms timeout
```

### Thermal Monitoring
Continuous temperature monitoring with automatic emergency shutdown at 70°C. All fluidic operations cease during thermal shutdown.

**Recovery**: Automatic when temperature drops to 55°C.

### Cycle Counter Maintenance
Monitor cycle counts for predictive maintenance:
- Valves: Typical lifetime ~1,000,000 cycles
- Pumps: Depends on usage and fluid type

Warning generated at 4 billion cycles (approaching counter overflow).

### Flash Memory CRC
Flash data integrity verified on boot using CRC-8. Invalid CRC triggers rewrite of default values.

### Debug Mode
Debug output controlled at runtime via `dbg` command. Useful for troubleshooting without recompiling firmware.

## Typical Usage Patterns

### Basic Fluidic Operation
```
Command: v310        # Open three-way valve 1
Command: pr1220      # Start pump 1 at 220 Hz
(wait for operation)
Command: ps1         # Stop pump 1
Command: v300        # Close three-way valve 1
```

### Six-Port Valve Switching
```
Command: v610        # Six-port valve 1 to position A
(wait 2+ seconds - rate limiting)
Command: v611        # Six-port valve 1 to position B
Response: 1 (ACK if GPIO verified)
```

### LED Measurement Sequence with Fluidics
```
Command: v611                                    # Route sample
Command: pr1220                                  # Pump sample
Command: rankbatch:255,200,180,150,245,5,100    # Measure
(wait for BATCH_COMPLETE)
Command: ps1                                     # Stop pump
```

### Multi-LED Control (V2.2+)
```
Command: leds:A:255,B:200,C:150,D:100    # Set all LEDs at once
(perform measurement)
Command: lx                              # All LEDs off
```

### Servo Calibration (V2.1+)
```
Command: servo:30,500      # Move to 30° in 500ms
(verify position)
Command: servo:120,500     # Move to 120° in 500ms
(verify position)
Command: sv030120          # Save calibration
Command: sf                # Flash to memory
```

### Maintenance Check
```
Command: vc                # Check valve cycles
Response: 12345,23456,34567,45678
Command: pcc               # Check pump cycles
Response: 123456,234567
```

### Thermal Monitoring
```
Command: it
Response: 58.25
(if temperature rises above 60°C, firmware prints warning)
(if temperature reaches 70°C, emergency shutdown occurs)
```

## Error Handling

### Response Codes
- `ACK` (1): Command successful
- `NAK` (0): Command failed

### Automatic Error Conditions

#### Thermal Shutdown (70°C)
- **Trigger**: Temperature ≥70°C
- **Action**: Emergency shutdown - all systems disabled
- **Output**: `!THERMAL_SHUTDOWN:XX.XX`
- **Recovery**: Automatic when temperature drops to 55°C

#### Thermal Warning (60°C)
- **Trigger**: Temperature ≥60°C but <70°C
- **Action**: Warning message only
- **Output**: `!THERMAL_WARNING:XX.XX`

#### Cycle Overflow Warning
- **Trigger**: Any cycle counter >4,000,000,000
- **Action**: Warning message
- **Output**: `!CYCLE_OVERFLOW_WARNING`
- **Recommendation**: Reset counters or plan component replacement

#### I2C Timeout
- **Trigger**: I2C device doesn't respond within 50ms
- **Action**: Command fails, NAK returned
- **Debug Output**: `I2C read/write timeout at addr 0xXX`

#### GPIO Verification Failure (V2.3+)
- **Trigger**: Six-port valve GPIO doesn't match expected state
- **Action**: Command returns NAK
- **Debug Output**: `v6 GPIO verification failed`
- **Possible Causes**: Valve mechanical failure, GPIO malfunction

### Common Error Scenarios

1. **Rate limit violation**: Command accepted but valve/pump state unchanged if within rate limit window
2. **Invalid parameter**: Values clamped to safe ranges, ACK still returned
3. **Flash write failure**: NAK returned from `sf` command
4. **Watchdog timeout**: Rankbatch auto-stops after 120s, no error message
5. **Pump overcurrent**: No firmware detection - external monitoring required

### Recovery Procedures

- **System hung**: Send `do` (emergency shutdown), then `id` (power on)
- **Rankbatch stuck**: Send `stop` command
- **Valve position unknown**: Cycle valve to known position (e.g., `v610` then verify)
- **Thermal shutdown**: Wait for cool-down, check `it` command, system recovers automatically
- **Flash corruption**: Send `sv030120` and `sf` to restore defaults
- **Firmware crash**: Power cycle or send `ib` (bootloader reboot)

## Performance Characteristics

### Timing Precision
- **LED sequencer**: ±1ms (1kHz ISR)
- **Watchdog**: ±1s (1Hz ISR)
- **Valve pulse**: ±1ms (hardware timer callback)
- **Pump frequency**: Accurate to PWM clock division

### Maximum Throughput
- **LED cycling**: Same as P4SPR (~20ms to ~1000ms per cycle)
- **Valve switching**: Limited by rate limiting (0.5-1 Hz)
- **Pump speed**: Up to 1000 Hz

### Cycle Counter Limits
- **Maximum before overflow**: ~4.3 billion (uint32_t)
- **Warning threshold**: 4 billion
- **Typical valve lifetime**: ~1 million cycles
- **Recommendation**: Monitor and reset counters periodically

## Safety Features

### Mechanical Protection
- **Six-port valves**: 2-second minimum interval (0.5 Hz max)
- **Three-way valves**: 1-second minimum interval (1 Hz max)
- **GPIO verification**: Confirms six-port valve state changes (V2.3+)

### Thermal Protection
- **60°C**: Warning threshold
- **70°C**: Emergency shutdown threshold
- **55°C**: Recovery threshold (after shutdown)

### Electrical Protection
- **Pump overcurrent**: External monitoring required (not in firmware)
- **PWM duty limiting**: Three-way valves limited to 35% duty
- **Valve pulse duration**: 800ms maximum for three-way valves

### Software Protection
- **Watchdog timer**: 120-second timeout for rankbatch
- **I2C timeout**: 50ms timeout prevents firmware lockup
- **Parameter clamping**: All input values validated and clamped
- **Flash CRC**: Data integrity verification

## Compatibility Notes

### P4SPR Compatibility
P4PRO includes all P4SPR LED and servo functionality plus fluidic control. Commands are mostly compatible but:
- **ACK/NAK values differ**: P4PRO uses 1/0, P4SPR uses 6/1
- **P4PRO-specific commands**: Valve (`v`), pump (`p`), cycle count commands
- **LED command enhancements**: `leds:` command only in P4PRO V2.2+

### Software Integration
- **USB CDC**: Virtual serial port
- **Baud rate**: Auto-detected
- **Line termination**: `\n` (LF)
- **Encoding**: ASCII
- **Buffer size**: 64 bytes

### Firmware Update Procedure
1. Send `ib` command (or hold BOOTSEL during power-on)
2. Device appears as "RPI-RP2" mass storage
3. Copy `.uf2` firmware file to device
4. Automatic reboot with new firmware

---

**Document Version**: 1.0  
**Last Updated**: February 2, 2026  
**Firmware Version**: V2.3  
**Author**: Lucia Iannantuono  
**Copyright**: © 2022 Affinite Instruments
