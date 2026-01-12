# Error Handling Patterns - Best Practices

## Overview
This document outlines error handling patterns learned from the Cavro syringe pump library and applied to our AffiPump system.

---

## 🎯 Core Principles

### 1. **Structured Error Information**
Always return structured error data, never just strings.

**❌ Bad:**
```python
def get_status(pump_num):
    return "Error: timeout"  # Unstructured string
```

**✅ Good:**
```python
def get_status(pump_num):
    return {
        'success': False,
        'error_code': 'TIMEOUT',
        'error_msg': 'Pump did not respond within 5s',
        'pump_num': pump_num,
        'timestamp': time.time(),
        'context': {'timeout': 5.0, 'bytes_received': 0}
    }
```

### 2. **Context-Rich Error Messages**
Include all relevant debugging information in error messages.

**❌ Bad:**
```python
logger.error("Pump failed")
```

**✅ Good:**
```python
logger.error(
    f"Pump {pump_num} timeout during {operation}: "
    f"Expected completion in {expected_time:.1f}s, "
    f"actual elapsed: {elapsed:.1f}s, "
    f"last_position: {last_pos}\u00b5L, "
    f"target_position: {target_pos}\u00b5L"
)
```

### 3. **Error Recovery Strategies**
Define clear recovery paths for each error type.

```python
ERROR_RECOVERY = {
    'TIMEOUT': {
        'action': 'abort_and_retry',
        'max_retries': 2,
        'delay': 0.5
    },
    'OVERLOAD': {
        'action': 'clear_error_and_reinit',
        'max_retries': 1,
        'delay': 1.0
    },
    'NOT_INITIALIZED': {
        'action': 'initialize',
        'max_retries': 1,
        'delay': 2.0
    },
    'SERIAL_ERROR': {
        'action': 'reconnect',
        'max_retries': 3,
        'delay': 1.0
    }
}
```

### 4. **Fail-Safe Defaults**
Always fail to a safe state, never leave hardware in unknown state.

```python
try:
    pump.start_dispense()
except Exception as e:
    logger.error(f"Dispense failed: {e}")
    # CRITICAL: Always clean up
    try:
        pump.abort()  # Stop movement
        pump.close_valves()  # Safe valve state
        pump.mark_idle()  # Clear operation flag
    except Exception as cleanup_error:
        logger.critical(f"Cleanup failed: {cleanup_error}")
        # Escalate to UI
        raise CriticalPumpError("Hardware in unknown state - manual intervention required")
```

---

## 📋 Error Handling Patterns from Cavro Library

### Pattern 1: **Context Manager for Auto-Recovery**

From Cavro library:
```python
@contextmanager
def error_recovery(self, pump_num):
    """Context manager for automatic error recovery"""
    try:
        yield
    except self.PumpError as e:
        if self.auto_recovery and e.error_code in ['i', 'I', 'g', 'G']:
            print(f"Auto-recovery triggered for: {e.error_msg}")
            self.clear_errors(pump_num)
            time.sleep(0.5)
            if e.error_code in ['g', 'G', 'i', 'I']:
                self.initialize_pump(pump_num)
                time.sleep(2)
            if self.last_command:
                self.send_command(self.last_command)  # Retry
        else:
            raise
```

**Application in our code:**
```python
class PumpManager:
    async def safe_operation(self, operation_func, *args, **kwargs):
        """Execute pump operation with automatic recovery"""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                return await operation_func(*args, **kwargs)
            except PumpTimeoutError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Attempt {attempt+1} failed: {e} - retrying...")
                    self.stop_current_operation(immediate=True)
                    await asyncio.sleep(0.5)
                else:
                    raise
            except PumpOverloadError as e:
                logger.error(f"Overload detected: {e}")
                await self._recover_from_overload()
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.0)
                else:
                    raise
```

### Pattern 2: **Structured Error Codes**

From Cavro library:
```python
ERROR_CODES = {
    b'`': {'busy': False, 'error': 'No Error'},
    b'i': {'busy': False, 'error': 'Plunger Overload'},
    b'I': {'busy': True, 'error': 'Plunger Overload'},
    b'g': {'busy': False, 'error': 'Device Not Initialized'},
    # ... more codes
}

def parse_response(self, response):
    status_char = match.group(1)
    error_info = self.ERROR_CODES.get(
        status_char,
        {'busy': None, 'error': f'Unknown: {status_char}'}
    )
    return {
        'status_char': status_char,
        'busy': error_info['busy'],
        'error_msg': error_info['error'],
        'data': data
    }
```

**Our implementation:**
```python
# Already implemented in affipump_controller.py!
# ERROR_CODES dictionary with structured error info
```

### Pattern 3: **Wait Loops with Timeout**

From Cavro library:
```python
def wait(self, dt=0.34):
    """Wait for pump to finish current task"""
    busy = self.get_busy()
    while busy:
        sleep(dt)
        busy = self.get_busy()
```

**Our improved implementation (just added):**
```python
def wait_until_ready(self, pump_num, timeout=30.0, poll_interval=0.1):
    """Wait for pump to become ready with timeout protection"""
    start_time = time.time()
    
    while True:
        elapsed = time.time() - start_time
        if elapsed >= timeout:
            return (False, elapsed, f"Timeout after {timeout}s")
        
        result = self.get_status(pump_num)
        if result and result['busy'] is False:
            return (True, elapsed, None)
        
        time.sleep(poll_interval)
```

### Pattern 4: **Always Abort Before New Operations**

From Cavro library:
```python
def flow(self, position=0, speed=0.1):
    """Safe flow - always abort first"""
    self.abort()  # Stop any current operation
    if self.valve != 'o':
        self.set_valve('o')
    if speed <= self.flow_speed_high_limit:
        self.move_abs(position=position, speed=speed)
    else:
        warning(f'Speed {speed} exceeds limit')
```

**Our implementation (just added):**
```python
async def run_buffer(self, ...):
    # CRITICAL: Always abort before new operations
    if not self.is_idle:
        logger.warning("Pump busy - aborting before buffer start")
        self.stop_current_operation(immediate=True)
        success, elapsed, error = await self._wait_for_pumps_ready(timeout=2.0)
        if not success:
            logger.error(f"Failed to abort: {error}")
            return False
```

---

## 🔧 Recommended Error Handling Patterns for Our Code

### 1. **Operation Wrapper with Retry Logic**

```python
async def _retry_operation(
    self,
    operation_name: str,
    operation_func,
    max_retries: int = 2,
    retry_delay: float = 0.5,
    *args,
    **kwargs
):
    """Execute operation with automatic retry on transient errors"""
    for attempt in range(max_retries):
        try:
            return await operation_func(*args, **kwargs)
        except PumpTimeoutError as e:
            if attempt < max_retries - 1:
                logger.warning(
                    f"{operation_name} attempt {attempt+1}/{max_retries} failed: {e}"
                )
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"{operation_name} failed after {max_retries} attempts")
                raise
        except PumpCriticalError:
            # Don't retry critical errors
            raise
```

### 2. **Error Classification**

```python
class PumpError(Exception):
    """Base pump error"""
    severity = 'ERROR'

class PumpTimeoutError(PumpError):
    """Transient timeout - retry"""
    severity = 'WARNING'
    retryable = True

class PumpOverloadError(PumpError):
    """Overload - needs recovery"""
    severity = 'ERROR'
    retryable = True

class PumpCriticalError(PumpError):
    """Critical hardware failure - don't retry"""
    severity = 'CRITICAL'
    retryable = False

class PumpNotInitializedError(PumpError):
    """Needs initialization"""
    severity = 'WARNING'
    retryable = True
```

### 3. **Logging Best Practices**

```python
# ❌ Bad: No context
logger.error("Operation failed")

# ✅ Good: Rich context
logger.error(
    f"[{operation_name}] Operation failed in cycle {cycle}/{total_cycles}: "
    f"error={error_type}, pump1_state={p1_state}, pump2_state={p2_state}, "
    f"elapsed={elapsed:.1f}s, expected={expected:.1f}s",
    extra={
        'operation': operation_name,
        'cycle': cycle,
        'total_cycles': total_cycles,
        'error_type': error_type,
        'pump_states': {'pump1': p1_state, 'pump2': p2_state},
        'timing': {'elapsed': elapsed, 'expected': expected}
    }
)
```

### 4. **Emergency Stop Pattern**

```python
async def _emergency_stop_with_feedback(self, context: str = ""):
    """Emergency stop with comprehensive feedback"""
    logger.critical(f"🚨 EMERGENCY STOP triggered: {context}")
    
    errors = []
    
    # Stop hardware
    try:
        self.stop_current_operation(immediate=True)
    except Exception as e:
        errors.append(f"Stop failed: {e}")
    
    # Wait for stop confirmation
    try:
        success, elapsed, error = await self._wait_for_pumps_ready(timeout=5.0)
        if not success:
            errors.append(f"Stop verification failed: {error}")
    except Exception as e:
        errors.append(f"Wait failed: {e}")
    
    # Close valves to safe state
    try:
        if self.hardware_manager._ctrl_raw:
            self.hardware_manager._ctrl_raw.knx_six_both(0)
            self.hardware_manager._ctrl_raw.knx_three_both(0)
    except Exception as e:
        errors.append(f"Valve close failed: {e}")
    
    # Reset state
    self._current_operation = PumpOperation.EMERGENCY_STOP
    self._shutdown_requested = True
    
    if errors:
        error_msg = f"Emergency stop completed with errors: {'; '.join(errors)}"
        logger.error(error_msg)
        return False, error_msg
    else:
        logger.info("✅ Emergency stop completed successfully")
        return True, None
```

### 5. **Validation Before Operations**

```python
def _validate_operation_preconditions(
    self,
    operation_name: str,
    required_hardware: list[str] = None,
    required_state: PumpOperation = PumpOperation.IDLE,
    volume_ul: float = None,
    flow_rate: float = None
) -> tuple[bool, str | None]:
    """Validate all preconditions before operation"""
    
    # Check hardware availability
    if not self.is_available:
        return False, f"{operation_name}: Pump hardware not available"
    
    if required_hardware:
        for hw in required_hardware:
            if not hasattr(self.hardware_manager, hw):
                return False, f"{operation_name}: Required hardware '{hw}' not found"
    
    # Check state
    if self._current_operation != required_state:
        return False, (
            f"{operation_name}: Invalid state. "
            f"Expected {required_state.value}, got {self._current_operation.value}"
        )
    
    # Validate parameters
    if volume_ul is not None:
        if not (0 < volume_ul <= 1000.0):
            return False, f"{operation_name}: Invalid volume {volume_ul}\u00b5L (must be 0-1000)"
    
    if flow_rate is not None:
        if not (1.0 <= flow_rate <= 10000.0):
            return False, f"{operation_name}: Invalid flow rate {flow_rate}\u00b5L/min (must be 1-10000)"
    
    return True, None

# Usage:
async def prime_pump(self, cycles=6, volume_ul=1000.0, ...):
    valid, error = self._validate_operation_preconditions(
        "prime",
        required_hardware=['pump', '_ctrl_raw'],
        required_state=PumpOperation.IDLE,
        volume_ul=volume_ul
    )
    if not valid:
        self.error_occurred.emit("prime", error)
        return False
    
    # Proceed with operation...
```

---

## 🚨 Critical Error Scenarios

### Scenario 1: **Serial Communication Failure**

**Detection:**
- Write timeout
- Read timeout
- Malformed response

**Response:**
```python
try:
    response = pump.send_command(cmd)
except serial.SerialTimeoutException:
    logger.error("Serial timeout - attempting recovery")
    # 1. Reset buffers
    self.ser.reset_input_buffer()
    self.ser.reset_output_buffer()
    time.sleep(0.5)
    
    # 2. Reopen port
    self.ser.close()
    time.sleep(1.0)
    self.ser.open()
    
    # 3. Retry command ONCE
    try:
        response = pump.send_command(cmd)
    except:
        # Recovery failed - escalate
        raise CriticalPumpError("Serial communication failed after recovery")
```

### Scenario 2: **Pump Doesn't Respond to Stop**

**Detection:**
- Terminate command sent but pump still busy after 5s

**Response:**
```python
# Send terminate
pump.send_command("/1TR")
pump.send_command("/2TR")

# Wait with timeout
start = time.time()
while time.time() - start < 5.0:
    status1 = pump.get_status(1)
    status2 = pump.get_status(2)
    if not status1['busy'] and not status2['busy']:
        logger.info("Pumps stopped successfully")
        return True
    time.sleep(0.1)

# Still busy - CRITICAL
logger.critical("Pumps did not respond to terminate command!")
# 1. Try broadcast terminate
pump.send_command("/0TR")
time.sleep(1.0)

# 2. Try power cycle (if relay available)
if hasattr(hardware_manager, 'pump_relay'):
    hardware_manager.pump_relay.power_cycle()

# 3. Alert user
raise CriticalPumpError(
    "Pumps unresponsive to stop commands. "
    "Manual intervention required: "
    "1) Press emergency stop button, "
    "2) Power cycle pumps, "
    "3) Check serial connection"
)
```

### Scenario 3: **Blockage Detection**

**Detection:**
- One pump takes significantly longer than expected
- Timeout during wait_until_both_ready

**Response:**
```python
p1_ready, p2_ready, elapsed, p1_time, p2_time = wait_until_both_ready(timeout=120)

if not (p1_ready and p2_ready):
    # Identify which pump timed out
    failed_pump = []
    if not p1_ready:
        failed_pump.append("KC1 (Pump 1)")
    if not p2_ready:
        failed_pump.append("KC2 (Pump 2)")
    
    error_msg = (
        f"Blockage suspected in {', '.join(failed_pump)}: "
        f"Pump1={p1_time:.1f}s, Pump2={p2_time:.1f}s, "
        f"Timeout={timeout}s"
    )
    logger.error(error_msg)
    
    # Stop pumps
    self.stop_current_operation(immediate=True)
    
    # Suggest corrective action
    self.error_occurred.emit(
        "blockage",
        f"{error_msg}\n\n"
        "Recommended actions:\n"
        "1. Check for air bubbles in lines\n"
        "2. Check valve positions\n"
        "3. Inspect for physical blockages\n"
        "4. Verify buffer supply"
    )
    return False
```

---

## 📊 Error Logging Levels

| Severity | When to Use | Example |
|----------|-------------|---------|
| **DEBUG** | Normal operation details | `logger.debug("Pump 1 ready in 2.3s")` |
| **INFO** | Operation milestones | `logger.info("Buffer flow started: 50\u00b5L/min")` |
| **WARNING** | Recoverable issues | `logger.warning("Retry attempt 1/3 after timeout")` |
| **ERROR** | Operation failures | `logger.error("Pump timeout - operation aborted")` |
| **CRITICAL** | System failures | `logger.critical("Pump hardware unresponsive")` |

---

## ✅ Testing Error Handling

### Unit Tests
```python
async def test_pump_timeout_recovery():
    """Test automatic recovery from pump timeout"""
    manager = PumpManager(mock_hardware)
    
    # Simulate timeout on first attempt
    mock_hardware.pump.fail_next_command(PumpTimeoutError("Simulated timeout"))
    
    # Should retry and succeed
    result = await manager.run_buffer(cycles=1)
    assert result == True
    assert mock_hardware.pump.command_count == 2  # Initial + retry

async def test_critical_error_no_retry():
    """Test that critical errors don't retry"""
    manager = PumpManager(mock_hardware)
    
    # Simulate critical error
    mock_hardware.pump.fail_next_command(PumpCriticalError("Hardware fault"))
    
    # Should fail immediately without retry
    with pytest.raises(PumpCriticalError):
        await manager.run_buffer(cycles=1)
    
    assert mock_hardware.pump.command_count == 1  # No retry
```

---

## 🎓 Key Takeaways

1. **Threading Protection**: Use locks with timing enforcement (50ms minimum)
2. **Structured Errors**: Return dicts/objects, not strings
3. **Context-Rich Logging**: Include all diagnostic info in error messages
4. **Always Abort First**: Clear previous operations before starting new ones
5. **Wait Loops > Fixed Delays**: Poll hardware status instead of guessing
6. **Classify Errors**: Distinguish transient vs. critical errors
7. **Auto-Recovery**: Implement retry logic for transient errors
8. **Fail-Safe**: Always leave hardware in known safe state
9. **Emergency Stops**: Multiple layers of safety (commands + state + valves)
10. **Test Error Paths**: Unit test recovery logic, not just happy path

---

## 📚 References

- [Cavro Centris Library](https://github.com/vstadnytskyi/syringe-pump)
- [PUMP_IMPROVEMENTS_FROM_CAVRO.md](PUMP_IMPROVEMENTS_FROM_CAVRO.md)
- [PUMP_CONTROL_ARCHITECTURE.md](PUMP_CONTROL_ARCHITECTURE.md)
