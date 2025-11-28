# Firmware Changelog

## V1.2 (November 2025)

### New Features
- **LED Ranking Command**: Added `rank:XXX,SSSS,DDD` command for fast LED calibration
  - Sequences through all 4 LEDs (A→B→C→D) with firmware-controlled timing
  - **Parameters**:
    - `XXX` = Test LED intensity (0-255, typical: 128)
    - `SSSS` = LED settling time in ms (default: 45ms)
    - `DDD` = Dark time between channels in ms (default: 5ms)
  - **Protocol**: Sends `X:READY` → `X:READ` → `X:DONE` for each channel
  - **Benefit**: Eliminates timing jitter from Python serial communication
  - **Use case**: Step 3 calibration (LED brightness ranking)
  - **Speedup**: ~2x faster and more reliable than Python-side sequencing

### Implementation Details
- New function: `led_rank_sequence(test_intensity, settling_ms, dark_ms)`
- Command parser handles optional parameters with sensible defaults
- Full atomic sequence: Python sends one command, firmware handles all timing
- See `FIRMWARE_V1.2_RANK_COMMAND.md` for protocol details and examples

---

## V1.1 (November 2025)

### Critical Fixes
- **Fixed batch command bug**: The `batch:A,B,C,D` command now properly turns off LEDs with 0 intensity
  - Root cause: Old code only set PWM levels but didn't disable PWM channels
  - Fix: Turn off all LEDs first, then enable only channels with non-zero intensity
  - Impact: Prevents "sticky LED" bug where LEDs stayed on when they shouldn't

### New Features
- **Automatic firmware update support**: Added `iB\n` command to reboot into bootloader
  - **No physical BOOTSEL button needed!**
  - Software can automatically update firmware over USB
  - Uses Pico SDK's `reset_usb_boot()` function
  - Enables seamless firmware updates for users

- **LED state tracking**: Added boolean flags to track which LEDs are enabled
  - Prevents brightness changes on disabled LEDs
  - More predictable behavior during batch operations

- **Working LED intensity queries**: Fixed `ia`, `ib`, `ic`, `id` commands
  - Now properly return current intensity (0-255)
  - Old code had buffer overrun issues

- **Emergency shutdown**: Added `i0\n` command
  - Immediately turns off all LEDs
  - Useful for safety/error recovery

### Improvements
- **Better command parsing**: Increased buffer from 10 to 20 characters to handle batch commands
- **Brightness range fix**: Allow 0 intensity (was incorrectly clamped to minimum 1)
- **Code cleanup**: Better comments and function organization
- **Null termination**: Added proper string null terminators for atoi() calls

### Testing Results
- ✅ Individual LED commands work (la, lb, lc, ld)
- ✅ Individual brightness commands work (baXXX, bbXXX, bcXXX, bdXXX)
- ✅ Batch command now works correctly (batch:A,B,C,D)
- ✅ All 4 LEDs can be controlled independently
- ✅ LEDs properly turn off when set to 0 intensity
- ✅ Query commands return correct values

### Software Alignment
This firmware update aligns with ezControl-AI software changes:
- Software currently uses individual commands (reliable baseline)
- Batch command now available for future optimization
- Query commands work for validation/debugging
- Emergency shutdown for error handling

## V1.0 (2022)

### Initial Release
- Basic LED control (on/off, brightness)
- Servo control (S/P positions)
- Temperature sensor reading
- Flash storage for servo positions
- I2C communication
- USB serial interface

### Known Issues (Fixed in V1.1)
- Batch command doesn't turn off LEDs properly
- LED query commands return incorrect values
- Minimum brightness incorrectly clamped to 1 instead of 0
- Command buffer too small for batch commands
