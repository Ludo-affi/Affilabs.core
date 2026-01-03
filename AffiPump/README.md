# AffiPump Development

Python-based control software for Tecan Cavro Centris syringe pumps via FTDI USB-Serial interface.

## Hardware Configuration

- **Interface**: FTDI FT232 USB-to-Serial (VID:0x0403, PID:0x6001)
- **Serial Number**: AP9XLF0GA
- **COM Port**: COM8 (may vary)
- **Baud Rate**: 38400
- **Protocol**: 8N1, no flow control
- **VCP Setting**: Load VCP must be **ON** (enabled in FTDI driver settings)

## Connected Pumps

- **Pump 1**: Tecan Cavro Centris (Address: `/1`)
- **Pump 2**: Tecan Cavro Centris (Address: `/2`)
- **Broadcast**: Both pumps (Address: `/A`)

## Quick Start

```python
from affipump_controller import AffipumpController

# Connect
pump = AffipumpController(port='COM8', baudrate=38400)
pump.open()

# Initialize both pumps
pump.initialize_pumps()

# Aspirate 500µL into pump 1 at 100µL/s
pump.aspirate(pump_num=1, volume_ul=500, speed_ul_s=100)

# Dispense from pump 1 at 50µL/s
pump.dispense(pump_num=1, speed_ul_s=50)

pump.close()
```

## Available Commands

See [COMMANDS.md](COMMANDS.md) for full command reference.

### Basic Operations
- `initialize_pumps()` - Initialize both pumps (required first step)
- `get_status(pump_num)` - Query status and position
- `aspirate(pump_num, volume_ul, speed_ul_s)` - Fill from input (left)
- `dispense(pump_num, speed_ul_s)` - Empty to output (right)
- `set_valve_input(pump_num)` - Set valve to input port
- `set_valve_output(pump_num)` - Set valve to output port
- `move_to_position(pump_num, position_ul, speed_ul_s)` - Move to absolute position

## Files

- **affipump_controller.py** - Main controller class (production code)
- **test_affipump_38400.py** - Hardware validation test
- **test_affipump_extended.py** - Extended response analysis
- **test_affipump_direct.py** - Direct serial communication test
- **test_putty_settings.py** - Serial configuration testing

## Development Notes

### Baud Rate Discovery
Initially tested at 9600 baud (incorrect) - pumps only echoed commands without executing. Engineer notes confirmed correct baud rate is **38400**.

### Response Format
Commands return: Echo + Status data
```
/1?\r → /1?\r\x00\xff/0`1600\x03\r\n\x00
         [echo] [sep] [status:0x60] [position:1600µL]
```

### Integration with ezControl
The VCP driver setting must remain **ON** for Python serial communication. Previous note about toggling VCP was for legacy configuration - current approach keeps VCP enabled for all software.

## Python Version
Requires **Python 3.12** (uses modern type hint syntax: `list[int] | None`)

Run scripts with: `py -3.12 script_name.py`

## References

- [Tecan Cavro Centris Operating Manual](../Affilabs.core/ezcontrol-AI/affipump/docs/)
- [Engineer's PuTTY Setup Notes](../Engineering%20Notes/)
- [Original affipump package](../Affilabs.core/ezcontrol-AI/affipump/)
