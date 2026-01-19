# P4PROPLUS Internal Pump Implementation - CORRECT Commands

## CRITICAL: Command Format

P4PROPLUS internal pumps use **RPM (rotations per minute)**, NOT µL/min!

### Command Format (CORRECTED - verified against firmware source):
- **Start pump**: `pr{ch}{rpm:04d}\n`
  - Example: `pr10050\n` = Pump 1 at 50 RPM
  - Example: `pr20100\n` = Pump 2 at 100 RPM
  - Example: `pr30075\n` = Both pumps at 75 RPM
  - **NOTE**: Firmware parses command[3:6] directly, does NOT subtract offset!

- **Stop pump**: `ps{ch}\n`
  - Example: `ps1\n` = Stop pump 1
  - Example: `ps2\n` = Stop pump 2
  - Example: `ps3\n` = Stop both pumps

### Valid RPM Range:
- **Minimum**: 5 RPM
- **Maximum**: 220 RPM
- Firmware auto-clamps values outside this range

## Flow Rate Conversion (µL/min → RPM)

Since users want to specify flow rates in µL/min (1-300 range), we need conversion:

```python
def _ul_min_to_rpm(self, rate_ul_min: float) -> int:
    """Convert flow rate from µL/min to RPM.
    
    Calibration factor depends on peristaltic tubing specs:
    - Small bore: ~2.0 µL/revolution  
    - Standard bore: ~3.0 µL/revolution
    - Large bore: ~5.0 µL/revolution
    """
    UL_PER_REVOLUTION = 3.0  # Must be calibrated per installation
    
    rpm = rate_ul_min / UL_PER_REVOLUTION
    rpm = max(5, min(220, int(rpm)))  # Clamp to firmware limits
    
    return rpm
```

### Example Conversions (assuming 3 µL/rev):
- 15 µL/min → 5 RPM (firmware minimum)
- 50 µL/min → 17 RPM
- 100 µL/min → 33 RPM
- 150 µL/min → 50 RPM
- 300 µL/min → 100 RPM
- 660 µL/min → 220 RPM (firmware maximum)

## Implementation for PicoP4PRO Class

### 1. Add to PicoP4PRO class (controller.py):

```python
def has_internal_pumps(self) -> bool:
    """Check if this P4PRO has internal peristaltic pumps.
    
    Returns:
        True if firmware version >= V2.3 (P4PROPLUS)
    """
    if not self.version:
        return False
    
    try:
        version_float = float(self.version.replace('V', '').replace('v', ''))
        return version_float >= 2.3
    except (ValueError, AttributeError):
        return False

def get_pump_capabilities(self) -> dict:
    """Get capability flags for P4PROPLUS internal pumps."""
    if not self.has_internal_pumps():
        return {}
    
    return {
        "type": "peristaltic",
        "bidirectional": False,
        "has_homing": False,
        "has_position_tracking": False,
        "supports_partial_loop": False,
        "max_flow_rate_ul_min": 300,
        "min_flow_rate_ul_min": 1,
        "supports_flow_rate_change": True,
        "recommended_prime_cycles": 10,
        "requires_visual_verification": True,
        "ul_per_revolution": 3.0,  # Calibration factor
    }

def _ul_min_to_rpm(self, rate_ul_min: float) -> int:
    """Convert µL/min to RPM using calibrated conversion factor."""
    caps = self.get_pump_capabilities()
    if not caps:
        return 0
    
    ul_per_rev = caps["ul_per_revolution"]
    rpm = rate_ul_min / ul_per_rev
    return max(5, min(220, int(rpm)))

def pump_start(self, rate_ul_min: float, ch: int = 1) -> bool:
    """Start internal peristaltic pump.
    
    Args:
        rate_ul_min: Flow rate in µL/min (1-300)
        ch: Pump channel (1, 2, or 3 for both)
    """
    if not self.has_internal_pumps():
        logger.error("No internal pumps available")
        return False
    
    # Validate range
    caps = self.get_pump_capabilities()
    if rate_ul_min < caps["min_flow_rate_ul_min"] or rate_ul_min > caps["max_flow_rate_ul_min"]:
        logger.error(f"Flow rate {rate_ul_min} µL/min out of range")
        return False
    
    # Convert to RPM
    rpm = self._ul_min_to_rpm(rate_ul_min)
    
    # Format command: pr{ch}{rpm+1000:04d}\n
    cmd = f"pr{ch}{rpm + 1000:04d}\n"
    
    try:
        if self._ser is not None or self.open():
            self._ser.write(cmd.encode())
            response = self._ser.read()
            if response == b"6":
                logger.info(f"Pump {ch} started: {rate_ul_min} µL/min ({rpm} RPM)")
                return True
        return False
    except Exception as e:
        logger.error(f"Error starting pump: {e}")
        return False

def pump_stop(self, ch: int = 1) -> bool:
    """Stop internal peristaltic pump.
    
    Args:
        ch: Pump channel (1, 2, or 3 for both)
    """
    if not self.has_internal_pumps():
        logger.error("No internal pumps available")
        return False
    
    cmd = f"ps{ch}\n"
    
    try:
        if self._ser is not None or self.open():
            self._ser.write(cmd.encode())
            response = self._ser.read()
            if response == b"6":
                logger.info(f"Pump {ch} stopped")
                return True
        return False
    except Exception as e:
        logger.error(f"Error stopping pump: {e}")
        return False
```

## Summary of Correct Implementation

1. **Commands use RPM**, not µL/min directly
2. **Offset format**: `pr{ch}{rpm+1000:04d}\n`
   - `pr11050\n` = Pump 1, 50 RPM
   - `pr21100\n` = Pump 2, 100 RPM  
   - `pr31075\n` = Both pumps, 75 RPM
3. **Stop format**: `ps{ch}\n`
   - `ps1\n`, `ps2\n`, `ps3\n`
4. **Conversion factor** (µL/revolution) must be calibrated per installation
5. **Firmware response**: `b"6"` = success
6. **User specifies µL/min** (1-300 range), code converts to RPM (5-220 range)
