# Useful Patterns from Cavro Syringe Pump Library

## Repository
https://github.com/vstadnytskyi/syringe-pump

**Note:** This is for **Cavro Centris** pumps (different hardware than our KC pumps), but the software architecture patterns are excellent.

---

## 🎯 Improvements We Should Adopt

### 1. **Threading Lock for Serial Communication** ✅ CRITICAL
**Problem in our code:** No lock protection for concurrent pump commands  
**Their solution:**
```python
class Driver(object):
    def __init__(self):
        self.lock = Lock()  # Threading lock
        self.serial_communication_dt = 0.1  # Min 100ms between commands
        
    def query(self, command, port=None):
        timeout = self.serial_communication_dt
        with self.lock:
            port.flushInput()
            port.flushOutput()
            self.write(command=command, port=port)
            reply = self.read(port=port)
        # Ensure minimum time between commands
        dt = self.serial_communication_dt - (time() - t1)
        if dt > 0:
            sleep(dt)
```

**Why it matters:**
- Prevents race conditions when UI changes flow rate while pump is running
- Hardware requires minimum time between commands (100ms for Cavro)
- Our KC pumps likely have similar timing requirements

---

### 2. **Separate "On-The-Fly" vs "Full Stop" Speed Changes** ✅ IMPLEMENTED
**Their implementation:**
```python
def set_speed(self, speed, on_the_fly=True):
    """Set speed - can change during movement if on_the_fly=True"""
    if on_the_fly:
        # Use 'F' suffix for on-the-fly changes (no stop required)
        reply = self.query(f"/1V{speed},1F\r")
    else:
        # Use 'R' suffix - requires pump to stop first
        self.abort()
        reply = self.query(f"/1V{speed},1R\r")
```

**We already have this!** Our `set_speed_on_the_fly()` uses 'F' suffix correctly.

---

### 3. **Busy Status Checking with Wait Loop** ✅ USEFUL
**Their pattern:**
```python
def wait(self, dt=0.34):
    """Wait for pump to finish current task"""
    busy = self.get_busy()
    while self.busy:
        sleep(dt)
    busy = self.get_busy()
```

**Application for us:**
- After terminate commands, wait for pumps to actually stop
- More reliable than fixed `time.sleep()` delays

---

### 4. **Compound Operations with Safety Checks** ✅ EXCELLENT PATTERN
**Their implementation:**
```python
def prime(self, N=5):
    """Prime pump with N fill/empty cycles"""
    start_speed = self.speed
    self.set_speed(68.0)  # Fast speed for priming
    self.set_valve('i')   # Input valve
    self.wait()           # Wait for valve
    
    for i in range(N):
        self.set_cmd_position(0.0)   # Empty
        self.wait()
        self.set_cmd_position(250.0)  # Fill
        self.wait()
    
    self.set_speed(start_speed)  # Restore original speed
    self.set_valve('o')  # Output valve

def flow(self, position=0, speed=0.1):
    """Safe flow operation"""
    self.abort()  # Stop any current operation
    if self.valve != 'o':
        self.set_valve('o')
    if speed <= self.flow_speed_high_limit:
        self.move_abs(position=position, speed=speed)
    else:
        warning(f'Speed {speed} exceeds limit {self.flow_speed_high_limit}')
```

**Benefits:**
- Always abort() before new operations
- Restore previous state after operations
- Validate parameters before execution
- Clear error messages

---

### 5. **Error Code Parsing** ✅ VERY USEFUL
**Their implementation:**
```python
def query(self, command, port=None):
    reply = self.read(port=port)
    if reply is not None:
        # Parse: '\xff/0`0.000\x03\r\n'
        error_code = reply.split(b'\x03\r\n')[0].split(b'\xff/0')[1][0:1]
        value = reply.split(b'\x03\r\n')[0].split(b'\xff/0')[1][1:]
        
        return {
            'value': value,
            'error_code': error_code,
            'busy': self.check_busy(error_code),
            'error': self.convert_error_code(error_code)
        }
```

**Why it's good:**
- Structured error handling instead of raw strings
- Automatic busy detection from error codes
- Human-readable error messages

---

### 6. **Position/Speed Properties** ✅ CLEAN INTERFACE
```python
# Internal state tracking
self._position = 0.0
self._cmd_position = 0.0
self._speed = 25.0

# Properties for clean access
position = property(_get_position, _set_position)
speed = property(get_speed, set_speed)
```

---

### 7. **Mock Driver for Testing** ✅ EXCELLENT IDEA
```python
class MockDevice():
    """Simulated pump for testing without hardware"""
    def __init__(self):
        self.position = 0.0
        self.cmd_position = 0.0
        self.speed = 0.001
        self.busy = False
    
    def run_once(self):
        if self.position != self.cmd_position:
            self.busy = True
            sign = (self.cmd_position - self.position) / abs(...)
            step = sign * self.speed * self.time_step
            self.position += step
        else:
            self.busy = False
```

**Application:**
- Test UI without hardware
- Regression testing
- Demo mode

---

## 📋 Recommended Implementation Plan

### **HIGH PRIORITY** (Do Now)

#### 1. Add Threading Lock to Pump Commands ⚠️ CRITICAL
```python
# In affipump_controller.py
class AffipumpController:
    def __init__(self):
        from threading import RLock
        self.lock = RLock()
        self.min_command_interval = 0.05  # 50ms minimum
        self.last_command_time = 0
        
    def send_command(self, command):
        with self.lock:
            # Enforce minimum interval
            elapsed = time.time() - self.last_command_time
            if elapsed < self.min_command_interval:
                time.sleep(self.min_command_interval - elapsed)
            
            result = self._serial_send(command)
            self.last_command_time = time.time()
            return result
```

#### 2. Add Wait-Until-Ready Function
```python
def wait_for_pumps_idle(self, timeout=30.0):
    """Wait until both pumps are idle"""
    start = time.time()
    while time.time() - start < timeout:
        status = self.get_status_both()
        if not status['pump1_busy'] and not status['pump2_busy']:
            return True
        time.sleep(0.1)
    return False
```

#### 3. Always Abort Before New Operations
```python
# In pump_manager.py run_buffer()
async def run_buffer(self, ...):
    # Add this at start
    if not self.is_idle:
        logger.warning("Pump busy - aborting current operation first")
        self.stop_current_operation(immediate=True)
        await asyncio.sleep(0.5)  # Wait for abort to complete
```

### **MEDIUM PRIORITY** (Next Week)

#### 4. Structured Error Handling
- Parse pump responses into structured dicts
- Map error codes to human messages
- Log all errors consistently

#### 5. State Restoration
- Save pump state before operations
- Restore state after operations
- Handle interruptions gracefully

### **LOW PRIORITY** (Future)

#### 6. Mock Pump Driver
- Create simulated pump for testing
- Add to test suite
- Enable demo mode

#### 7. Compound Operations
- `prime_both_pumps(cycles=6)`
- `flush_lines(volume=300)`
- `emergency_drain()`

---

## 🔧 Code Snippets to Add

### Thread-Safe Command Wrapper
```python
# Add to affipump_controller.py

from threading import RLock
import time

class AffipumpController:
    def __init__(self):
        self.command_lock = RLock()
        self.min_command_dt = 0.05  # 50ms between commands
        self._last_command_time = 0
        
    def _send_with_lock(self, command):
        """Thread-safe command sending with timing enforcement"""
        with self.command_lock:
            # Enforce minimum time between commands
            elapsed = time.time() - self._last_command_time
            if elapsed < self.min_command_dt:
                time.sleep(self.min_command_dt - elapsed)
            
            # Send command
            result = self.pump.write(command.encode())
            self._last_command_time = time.time()
            
            return result
```

### Wait for Completion Helper
```python
# Add to pump_manager.py

async def _wait_for_pumps_ready(self, timeout=30.0):
    """Async wait for both pumps to become idle"""
    start_time = asyncio.get_event_loop().time()
    
    while True:
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > timeout:
            logger.error(f"Timeout waiting for pumps (>{timeout}s)")
            return False
            
        # Check if pumps are ready
        try:
            pump = self.hardware_manager.pump
            status = pump._pump.pump.get_status_both()
            
            if not status.get('pump1_busy') and not status.get('pump2_busy'):
                return True
                
        except Exception as e:
            logger.warning(f"Error checking pump status: {e}")
            
        await asyncio.sleep(0.1)
```

---

## ⚠️ Critical Differences - Be Aware!

| Feature | Cavro Centris | Our KC Pumps |
|---------|---------------|--------------|
| **Command format** | `/1V25.0,1R\r` | Different syntax |
| **Valve types** | 3-position: i/o/b | 6-port + 3-way |
| **Speed units** | µL/s | µL/s (same) |
| **On-the-fly** | 'F' suffix | 'F' suffix (same!) |
| **Termination** | `/1TR\r` | `/1TR\r` (same!) |
| **Max speed** | 68.8 µL/s | Unknown - test! |

---

## 📊 Testing Checklist

After implementing improvements:

- [ ] Test rapid flow rate changes (no crash)
- [ ] Test concurrent stop + flow change (no deadlock)
- [ ] Measure actual min command interval (oscilloscope?)
- [ ] Test multiple rapid starts/stops
- [ ] Verify state restoration after abort
- [ ] Test timeout scenarios
- [ ] Load test: 1000 operations

---

## 🎓 Key Learnings

1. **Threading protection is ESSENTIAL** - we're missing this!
2. **Timing between commands matters** - hardware limitation
3. **Always abort before new operations** - prevents conflicts
4. **Wait loops better than fixed delays** - more reliable
5. **Structured errors better than strings** - easier debugging
6. **Mock drivers enable testing** - worth the investment

---

## Summary

**Must implement now:**
- ✅ Threading lock for serial commands
- ✅ Minimum command interval enforcement  
- ✅ Wait-for-ready helper functions
- ✅ Abort before new operations

**Nice to have:**
- Error code parsing
- State restoration
- Mock driver for testing

The Cavro library shows **professional-grade pump control** - we should adopt their best practices!
