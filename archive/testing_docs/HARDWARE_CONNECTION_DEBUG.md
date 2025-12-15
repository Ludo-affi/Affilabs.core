# Hardware Connection Debug Guide

## Quick Troubleshooting

### Debug Flags (in `core/hardware_manager.py`)

```python
HARDWARE_DEBUG = False      # Set to True for detailed output
CONNECTION_TIMEOUT = 2.0    # USB scan timeout in seconds (2s fast, 5s safe)
```

### Connection Speed Optimization

**Default Mode** (HARDWARE_DEBUG = False, CONNECTION_TIMEOUT = 2.0):
- Target: < 2 seconds total scan time
- Minimal logging (only critical events)
- 2-second USB device discovery timeout

**Debug Mode** (HARDWARE_DEBUG = True):
- Detailed timing for each device scan step
- Full serial port enumeration
- Device identification details
- Full exception tracebacks

### Quick Diagnosis

**If connection takes > 5 seconds:**
1. Check `HARDWARE_DEBUG = True` and run again to see timing breakdown
2. Look for which device scan is slow:
   - `[SCAN] Spectrometer scan: X.XXs`
   - `[SCAN] Controller scan: X.XXs`
   - `[SCAN] Kinetic scan: X.XXs`
   - `[SCAN] Pump scan: X.XXs`

**If no hardware detected:**
1. Enable debug mode: `HARDWARE_DEBUG = True`
2. Check serial ports list in log output
3. Verify VID/PID matches expected values
4. Check Device Manager for driver issues

**If connection unreliable:**
1. Increase timeout: `CONNECTION_TIMEOUT = 5.0`
2. Enable debug mode to see USB scan details
3. Check for "already opened" errors (device stuck)

## Connection Flow

```
Power Button Click
  → AffilabsMainWindow._handle_power_click()
  → Application._on_power_on_requested()
  → HardwareManager.scan_and_connect()
  → Background thread: _connection_worker()
      ├─ _connect_spectrometer() [~2s with timeout]
      ├─ _connect_controller()   [~0.1s typical]
      ├─ _connect_kinetic()      [~0.1s typical]
      └─ _connect_pump()         [~0.1s typical]
  → hardware_connected signal emitted
```

## Log Output Examples

### Normal Mode (HARDWARE_DEBUG = False)
```
[SCAN] Starting hardware scan...
Connecting to spectrometer...
Spectrometer connected: USB4D07000
Controller connected: pico_p4spr
No kinetic controller found
Pump connected
============================================================
HARDWARE SCAN COMPLETE (2.34s)
  • Controller: pico_p4spr
  • Kinetic:    NOT FOUND
  • Pump:       CONNECTED
  • Spectro:    CONNECTED
  → Device Type: P4SPR
============================================================
```

### Debug Mode (HARDWARE_DEBUG = True)
```
[SCAN] Starting hardware scan...
============================================================
SCANNING FOR SPECTROMETER...
============================================================
Connecting to spectrometer...
Scanning for Ocean Optics devices (2.0s timeout)...
SeaBreeze found 1 device(s)
Spectrometer connected: USB4D07000
   Model: USB4000
   Device config: c:\Users\...\USB4D07000
[SCAN] Spectrometer scan: 2.01s
============================================================
SCANNING FOR CONTROLLERS...
============================================================
Serial ports: 4
  COM3: VID=0x2E8A PID=0x0005 - USB Serial Device
  COM4: VID=0x2341 PID=0x0043 - Arduino Uno
  COM5: VID=0x1A86 PID=0x7523 - USB-SERIAL CH340
  COM6: VID=0x10C4 PID=0xEA60 - CP2102 USB to UART
Trying PicoP4SPR (VID:PID = 0x2e8a:0x5)...
Controller connected: pico_p4spr
[SCAN] Controller scan: 0.12s
[SCAN] Kinetic scan: 0.08s
Pump connected
[SCAN] Pump scan: 0.11s
============================================================
HARDWARE SCAN COMPLETE (2.32s)
  • Controller: pico_p4spr
  • Kinetic:    NOT FOUND
  • Pump:       CONNECTED
  • Spectro:    CONNECTED
  → Device Type: P4SPR
============================================================
```

## Timing Targets

| Component     | Typical Time | Max Acceptable |
|---------------|--------------|----------------|
| Spectrometer  | 1.5-2.0s     | 2.0s (timeout) |
| Controller    | 0.05-0.2s    | 0.5s           |
| Kinetic       | 0.05-0.2s    | 0.5s           |
| Pump          | 0.05-0.2s    | 0.5s           |
| **TOTAL**     | **1.7-2.6s** | **3.0s**       |

## Common Issues

### Spectrometer timeout taking full 2-5s
- **Cause**: No spectrometer connected or USB driver issue
- **Fix**: Check USB cable, drivers, power; device should respond in <1s if healthy

### Controller scan slow (>0.5s)
- **Cause**: Serial port enumeration slow or multiple devices
- **Fix**: Unplug unused USB serial devices; check driver installation

### "Already opened" errors
- **Cause**: Previous connection not cleaned up
- **Fix**: Restart application; check for duplicate instances

### No devices found but hardware is connected
- **Cause**: Driver issue, wrong VID/PID, or permission problem
- **Fix**: Check Device Manager, reinstall drivers, try different USB port

## Performance Tuning

**For fastest connection (may be less reliable):**
```python
HARDWARE_DEBUG = False
CONNECTION_TIMEOUT = 1.5  # Aggressive but may fail on slow USB hubs
```

**For most reliable connection (slower):**
```python
HARDWARE_DEBUG = False
CONNECTION_TIMEOUT = 5.0  # Safe for slow USB hubs/older hardware
```

**For troubleshooting:**
```python
HARDWARE_DEBUG = True
CONNECTION_TIMEOUT = 5.0  # See everything, wait longer
```
