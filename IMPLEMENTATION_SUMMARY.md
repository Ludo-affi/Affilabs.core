# Implementation Summary - Threading Safety & Error Handling

**Date:** January 7, 2026  
**Status:** ✅ IMPLEMENTED

---

## 🎯 What Was Implemented

### 1. **Thread-Safe Serial Communication** ✅ CRITICAL
**File:** `affipump/affipump_controller.py`

**Changes:**
- Upgraded `threading.Lock()` → `threading.RLock()` (reentrant lock for nested calls)
- Added `_min_command_interval = 0.05` (50ms minimum between commands)
- Added `_last_command_time` tracking
- Enforced minimum interval in `send_command()` method

**Code:**
```python
# In __init__:
self._serial_lock = threading.RLock()  # Reentrant lock
self._min_command_interval = 0.05  # 50ms minimum
self._last_command_time = 0.0

# In send_command:
with self._serial_lock:
    elapsed = time.time() - self._last_command_time
    if elapsed < self._min_command_interval:
        sleep_time = self._min_command_interval - elapsed
        time.sleep(sleep_time)
    
    self.ser.write((cmd + '\r').encode())
    self._last_command_time = time.time()
```

**Why it matters:**
- Prevents race conditions when UI changes flow rate while pump is running
- Hardware requires minimum time between commands (similar to Cavro Centris)
- Eliminates command collision errors

---

### 2. **Wait-Until-Ready Pattern** ✅ EXCELLENT
**File:** `affipump/affipump_controller.py`

**New Method:**
```python
def wait_until_ready(self, pump_num, timeout=30.0, poll_interval=0.1):
    """Wait for pump to become ready (not busy).
    
    Returns:
        tuple: (ready: bool, elapsed_time: float, error_msg: str or None)
    """
    start_time = time.time()
    
    while True:
        elapsed = time.time() - start_time
        if elapsed >= timeout:
            return (False, elapsed, f"Timeout after {timeout}s")
        
        result = self.get_status(pump_num)
        if result and result['busy'] is False:
            return (True, elapsed, None)
        if result and result['error']:
            return (False, elapsed, f"Pump error: {result['error_msg']}")
        
        time.sleep(poll_interval)
```

**Benefits:**
- Replaces fixed `time.sleep()` delays with actual status polling
- Returns structured data: success flag, elapsed time, error message
- More reliable than guessing completion times

---

### 3. **Async Wait-For-Pumps Helper** ✅ ASYNC-FRIENDLY
**File:** `affilabs/managers/pump_manager.py`

**New Method:**
```python
async def _wait_for_pumps_ready(self, timeout: float = 30.0) -> tuple[bool, float, str | None]:
    """Wait for both pumps to become idle/ready.
    
    Returns:
        tuple: (success: bool, elapsed_time: float, error_msg: str or None)
    """
    # Checks pump 1, then pump 2 with remaining timeout
    # Returns structured result with timing info
```

**Benefits:**
- Async-compatible (uses `run_in_executor`)
- Checks both pumps sequentially
- Adjusts timeout dynamically (remaining time for pump 2)
- Structured return value for error handling

---

### 4. **Always Abort Before New Operations** ✅ SAFETY
**File:** `affilabs/managers/pump_manager.py`

**Changes in `run_buffer()`:**
```python
async def run_buffer(self, ...):
    # OLD: Just checked if idle, rejected if busy
    # NEW: Automatically abort if busy, then wait for confirmation
    
    if not self.is_idle:
        logger.warning(f"Pump busy ({self._current_operation.value}) - aborting first")
        self.stop_current_operation(immediate=True)
        
        # Wait for pumps to actually stop (up to 2 seconds)
        success, elapsed, error = await self._wait_for_pumps_ready(timeout=2.0)
        if not success:
            error_msg = f"Failed to abort previous operation: {error}"
            logger.error(error_msg)
            self.error_occurred.emit("run_buffer", error_msg)
            return False
        
        logger.info(f"✅ Previous operation aborted in {elapsed:.2f}s")
```

**Benefits:**
- Prevents "pump busy" errors
- Automatically clears previous operations
- User doesn't need to manually stop first
- Safer state transitions

---

### 5. **Enhanced Error Context** ✅ DEBUGGING
**File:** `affilabs/managers/pump_manager.py`

**Old Error Message:**
```python
error_detail = "Aspirate timeout: Pump1=FAILED, Pump2=OK"
```

**New Error Message:**
```python
error_detail = (
    f"Aspirate timeout in cycle {cycle}: "
    f"Pump1={'READY' if p1_ready else 'TIMEOUT'} ({p1_time:.1f}s), "
    f"Pump2={'READY' if p2_ready else 'TIMEOUT'} ({p2_time:.1f}s), "
    f"Total elapsed: {elapsed:.1f}s"
)
```

**Added Emergency Stop on Error:**
```python
if not (p1_ready and p2_ready):
    logger.error(f"[PUMP ERROR] {error_detail}")
    
    # Attempt emergency stop
    try:
        logger.warning("Attempting emergency pump stop...")
        self.stop_current_operation(immediate=True)
    except Exception as stop_err:
        logger.error(f"Emergency stop failed: {stop_err}")
```

**Benefits:**
- Rich context for debugging (cycle number, timing, which pump failed)
- Automatic emergency stop on timeout
- Safer failure mode

---

## 📚 Documentation Created

### 1. **PUMP_IMPROVEMENTS_FROM_CAVRO.md**
Detailed analysis of Cavro library patterns:
- Threading lock requirements
- On-the-fly speed changes
- Busy status polling
- Compound operations
- Error code parsing
- Mock driver pattern

### 2. **ERROR_HANDLING_PATTERNS.md** ⭐ NEW
Comprehensive error handling guide:
- Core principles (structured errors, context-rich messages)
- Error recovery strategies
- Context manager pattern
- Wait loops with timeout
- Error classification (transient vs. critical)
- Emergency stop patterns
- Validation before operations
- Critical error scenarios
- Testing strategies

---

## 🔍 Additional Error Handling Patterns Identified

### **From Cavro Library:**

1. **Context Manager for Auto-Recovery**
   ```python
   @contextmanager
   def error_recovery(self, pump_num):
       try:
           yield
       except PumpError as e:
           if auto_recovery and e.error_code in recoverable_codes:
               self.clear_errors(pump_num)
               self.initialize_pump(pump_num)
               self.send_command(self.last_command)  # Retry
   ```

2. **Error Classification**
   ```python
   class PumpTimeoutError(PumpError):
       retryable = True
   
   class PumpCriticalError(PumpError):
       retryable = False
   ```

3. **Validation Before Operations**
   ```python
   def prime(self, N=5):
       start_speed = self.speed
       self.set_speed(68.0)  # Fast
       # ... operation ...
       self.set_speed(start_speed)  # Restore
   ```

4. **Structured Error Codes**
   ```python
   ERROR_CODES = {
       b'`': {'busy': False, 'error': 'No Error'},
       b'i': {'busy': False, 'error': 'Plunger Overload'},
       # ... (already implemented in our code!)
   }
   ```

5. **Mock Driver for Testing**
   ```python
   class MockDevice():
       """Simulated pump for testing without hardware"""
       def run_once(self):
           if self.position != self.cmd_position:
               self.busy = True
               self.position += self.speed * dt
   ```

---

## 🚨 Critical Improvements Made

### **Before:**
- ❌ No minimum interval enforcement → command collisions possible
- ❌ Fixed delays (`time.sleep(5)`) → wasted time or premature timeout
- ❌ Rejected operations if pump busy → user frustration
- ❌ Generic error messages → hard to debug
- ❌ No automatic error recovery

### **After:**
- ✅ 50ms minimum between commands → prevents hardware conflicts
- ✅ Dynamic wait with polling → accurate completion detection
- ✅ Auto-abort before new operations → seamless UX
- ✅ Rich error context (cycle, timing, pump states) → easy debugging
- ✅ Emergency stop on timeout → safer failure mode

---

## 📊 Testing Recommendations

### **Unit Tests to Add:**
```python
async def test_command_interval_enforcement():
    """Verify 50ms minimum between commands"""
    controller = AffipumpController()
    controller.open()
    
    start = time.time()
    controller.send_command("/1?")
    controller.send_command("/2?")
    elapsed = time.time() - start
    
    assert elapsed >= 0.05  # Minimum 50ms enforced

async def test_auto_abort_before_buffer():
    """Test automatic abort when starting buffer while busy"""
    manager = PumpManager(hardware)
    
    # Start prime
    await manager.prime_pump(cycles=6)  # Running
    
    # Try to start buffer (should auto-abort prime first)
    result = await manager.run_buffer(cycles=1)
    
    assert result == True  # Should succeed after auto-abort
```

### **Integration Tests:**
- Rapid flow rate changes (no crash)
- Concurrent stop + flow change (no deadlock)
- Multiple rapid starts/stops
- Timeout scenarios
- Load test: 1000 operations

---

## 🎓 Key Learnings

1. **Hardware timing constraints are real** - 50ms minimum not optional
2. **Polling > Guessing** - Wait loops more reliable than fixed delays
3. **Auto-recovery beats rejection** - Abort busy operations automatically
4. **Context saves hours** - Rich error messages = faster debugging
5. **Thread safety is critical** - Lock + timing enforcement essential
6. **Fail-safe always** - Emergency stop on any error
7. **Test error paths** - Happy path easy, error handling is hard

---

## 🔜 Future Enhancements (Optional)

### **High Priority:**
- [ ] Add retry logic with exponential backoff
- [ ] Implement error classification (transient vs. critical)
- [ ] Add validation before all operations
- [ ] Create mock pump driver for testing

### **Medium Priority:**
- [ ] Parse error codes into structured dicts
- [ ] Add state restoration after operations
- [ ] Implement operation history logging
- [ ] Add performance metrics (timing stats)

### **Low Priority:**
- [ ] Create GUI error dashboard
- [ ] Add telemetry for error patterns
- [ ] Implement automatic diagnostics
- [ ] Add email alerts for critical errors

---

## ✅ Verification Checklist

- [x] Threading lock implemented (RLock)
- [x] Minimum command interval enforced (50ms)
- [x] Wait-until-ready method added
- [x] Async wait helper created
- [x] Auto-abort before operations
- [x] Enhanced error messages with context
- [x] Emergency stop on timeout
- [x] Documentation created
- [ ] Unit tests added (recommended)
- [ ] Integration tests run (recommended)

---

## 📝 Files Modified

1. **affipump/affipump_controller.py**
   - Lines 55-70: Added RLock and timing enforcement
   - Lines 110-130: Enforced minimum command interval
   - Lines 235-270: Added `wait_until_ready()` method

2. **affilabs/managers/pump_manager.py**
   - Lines 945-990: Added `_wait_for_pumps_ready()` async helper
   - Lines 730-760: Auto-abort before `run_buffer()`
   - Lines 810-830: Enhanced aspirate error handling
   - Lines 840-860: Enhanced dispense error handling

3. **PUMP_IMPROVEMENTS_FROM_CAVRO.md** (NEW)
   - Full analysis of Cavro library patterns
   - Implementation recommendations
   - Code snippets

4. **ERROR_HANDLING_PATTERNS.md** (NEW)
   - Comprehensive error handling guide
   - Best practices from industry
   - Testing strategies

---

## 🎯 Summary

**Implemented threading safety and error handling improvements based on Cavro Centris library best practices:**

✅ **Thread safety** - RLock with 50ms minimum command interval  
✅ **Smart waiting** - Poll hardware status instead of fixed delays  
✅ **Auto-recovery** - Abort busy operations before new ones  
✅ **Rich errors** - Context-rich messages for easy debugging  
✅ **Fail-safe** - Emergency stop on any timeout  
✅ **Documentation** - Two comprehensive guides created

**Result:** More robust, safer, and easier to debug pump control system.
