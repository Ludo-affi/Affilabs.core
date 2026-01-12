# Threading Architecture Analysis

## Summary
Threading architecture review completed. System uses consistent patterns throughout with proper memory management.

## ✅ Threading Patterns

### 1. **Pump Operations** (Consistent & Safe)
**Location:** [main.py](main.py#L3544-L3560)
**Pattern:** `_run_pump_operation_async()` helper method

```python
def _run_pump_operation_async(self, operation_name: str, operation_coro, *args, **kwargs):
    """Helper to run async pump operations in background thread."""
    def run_operation():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(operation_coro(*args, **kwargs))
        finally:
            loop.close()
    
    threading.Thread(target=run_operation, daemon=True).start()
```

**Usage:** All pump operations use this consistent pattern:
- ✅ `_on_pump_prime_clicked()` → line 3571
- ✅ `_on_pump_cleanup_clicked()` → line 3582
- ✅ `_on_pump_stop_clicked()` → line 3652 (emergency stop)
- ✅ `_on_pump_flush_clicked()` → line 3679
- ✅ `_on_pump_home_clicked()` → lines 3700, 3705
- ✅ `_on_pump_inject_clicked()` → line 3753
- ✅ `data_acquisition_manager.start_pump_buffer()` → line 461

**Status:** ✅ SAFE - Consistent pattern, daemon threads, proper cleanup

---

### 2. **Data Acquisition** (Dedicated Thread)
**Location:** [data_acquisition_manager.py](affilabs/core/data_acquisition_manager.py#L744)
**Pattern:** Long-running acquisition thread with proper stop signals

```python
self._acquisition_thread = threading.Thread(
    target=self._acquisition_worker,
    name="DataAcquisition",
    daemon=False,  # NOT daemon - we need graceful shutdown
)
```

**Characteristics:**
- ✅ Non-daemon for graceful shutdown
- ✅ Event-based stop signals (`_stop_acquisition`)
- ✅ Proper cleanup in `stop_acquisition()`

**Status:** ✅ SAFE - Proper lifecycle management

---

### 3. **Processing Thread** (Spectrum Analysis)
**Location:** [main.py](main.py#L2968-L2975)
**Pattern:** Dedicated processing thread separates acquisition from analysis

```python
self._processing_thread = threading.Thread(
    target=self._processing_worker,
    name="SpectrumProcessing",
    daemon=True,
)
```

**Status:** ✅ SAFE - Prevents acquisition jitter, queue-based communication

---

### 4. **Calibration Operations** (Background Tasks)
**Location:** [main.py](main.py#L5358)
**Pattern:** Daemon threads for long-running calibration/training

```python
thread = threading.Thread(
    target=run_calibration, 
    daemon=True, 
    name="SimpleCalibration"
)
```

**Examples:**
- ✅ Simple LED calibration (line 5358)
- ✅ LED model training (line 5638)
- ✅ Polarizer calibration (uses similar pattern)

**Status:** ✅ SAFE - Daemon threads with progress dialogs, can be interrupted

---

### 5. **Shutdown Sequence** (Synchronous Cleanup)
**Location:** [main.py](main.py#L5767)
**Pattern:** New event loop for emergency cleanup

```python
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    loop.run_until_complete(emergency_stop())
    loop.run_until_complete(self._home_plungers(pump))
finally:
    loop.close()
```

**Status:** ✅ ACCEPTABLE - Necessary for synchronous shutdown from Qt event loop

---

## ✅ Memory Management

### Timing Data Buffers
**Location:** [data_acquisition_manager.py](affilabs/core/data_acquisition_manager.py#L277-L283)

**Pattern:** Bounded buffers with automatic cleanup

1. **Timing instrumentation** (`_timing_data`):
   - ✅ Reset at acquisition start (line 715)
   - ✅ Bounded to one acquisition session
   - ✅ Prevents unbounded growth

2. **Jitter statistics** (`_timing_jitter_stats`):
   - ✅ Fixed-size rolling window (100 samples per channel)
   - ✅ Auto-prune with `pop(0)` when full (line 2156)
   - ✅ No memory leak

**Status:** ✅ SAFE - Proper bounds, automatic cleanup

---

## Improvements Made This Session

### Fixed Issues:
1. ✅ **Flow Sidebar Home Button** - Removed dangerous inline threading
   - Was: Creating new event loop in button click handler
   - Now: Uses proper Qt signal → `_run_pump_operation_async()`
   
2. ✅ **data_acquisition_manager.start_pump_buffer()** - Fixed threading pattern
   - Was: Creating new event loop directly in data acquisition manager
   - Now: Delegates to `app._run_pump_operation_async()`

3. ✅ **run_buffer() timeout calculation** - Fixed for slow flow rates
   - Was: Fixed 2x multiplier broke 5-10 µL/min flow rates
   - Now: Adaptive timeout (<10: +600s, 10-50: 2x, >50: 1.5x)

4. ✅ **run_buffer() volume validation** - Added safety limits
   - Was: No validation, could overflow pump
   - Now: Clamps to 10-1000 µL range with logging

5. ✅ **run_buffer() jam detection** - Enabled position monitoring
   - Was: No position change checking during buffer flow
   - Now: `check_position_change=True` for jam detection

---

## Architecture Assessment

### Pattern Consistency: ✅ GOOD
- All pump operations use `_run_pump_operation_async()`
- No ad-hoc event loop creation in business logic
- Centralized async wrapper ensures consistent behavior

### Thread Safety: ✅ GOOD
- Qt signals for cross-thread communication
- Proper event-based synchronization
- No shared mutable state without protection

### Resource Management: ✅ GOOD
- Event loops properly closed
- Timing buffers bounded
- Graceful shutdown sequences

### Potential Improvements (Low Priority):
1. **Single Persistent Event Loop** (optional optimization)
   - Current: Create/destroy event loop per pump operation
   - Alternative: Single background event loop + queue
   - Tradeoff: More complex, minimal performance gain
   - Verdict: Current approach is simpler and sufficient

2. **Thread Pool for Operations** (optional)
   - Current: New thread per operation
   - Alternative: QThreadPool with QRunnable
   - Tradeoff: More Qt-idiomatic, but current works fine
   - Verdict: Not worth refactoring

---

## Conclusion

**Status: ✅ PRODUCTION READY**

The threading architecture is:
- ✅ Consistent across all pump operations
- ✅ Safe with proper cleanup and daemon settings
- ✅ Memory-safe with bounded buffers
- ✅ Well-organized with clear separation of concerns

**No critical issues found.**

Minor optimization opportunities exist but are NOT recommended due to:
- Working system in production
- Added complexity not justified by marginal gains
- Risk of introducing bugs during refactoring

---

*Document created: 2025-01-XX*
*Review scope: Threading patterns, memory management, pump operations*
*Files analyzed: main.py, data_acquisition_manager.py, pump_manager.py, AL_flow_builder.py*
