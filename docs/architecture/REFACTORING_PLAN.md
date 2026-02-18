# Performance Refactoring Plan for AffiLabs.core v4.0

## Immediate Wins (High Impact, Low Risk)

### 1. **Split `_on_spectrum_acquired()` into Specialized Handlers** ⭐⭐⭐
**Impact:** Reduce hot path execution time by 30-40%
**Risk:** Low (clear separation of concerns)

Split the 167-line monster method into:
```python
def _on_spectrum_acquired(self, data):
    """Main dispatcher - minimal logic."""
    channel = data['channel']
    timestamp = data['timestamp']
    is_preview = data.get('is_preview', False)

    # Initialize timing
    if self.experiment_start_time is None:
        self.experiment_start_time = timestamp
    elapsed_time = timestamp - self.experiment_start_time

    # Dispatch to specialized handlers (only what's needed)
    if not is_preview:
        self._handle_intensity_monitoring(channel, data, timestamp)
        self._queue_transmission_update(channel, data)

    self._update_timeline_buffer(channel, elapsed_time, data['wavelength'])
    self._queue_graph_update(channel, elapsed_time)

    if self.main_window.live_data_enabled:
        self._update_cursor_tracking(elapsed_time)

    if self.recording_mgr.is_recording:
        self._record_data_point(channel)

def _handle_intensity_monitoring(self, channel, data, timestamp):
    """Isolated intensity/leak detection logic."""
    intensity = data.get('intensity', 0)
    self.buffer_mgr.append_intensity_point(channel, timestamp, intensity)

    if self.hardware_mgr._calibration_passed:
        self.hardware_mgr.update_led_intensity(channel, intensity, timestamp)

    # Trim old data
    cutoff_time = timestamp - LEAK_DETECTION_WINDOW
    self.buffer_mgr.trim_intensity_buffer(channel, cutoff_time)

    # Check leak threshold
    if self.buffer_mgr.get_intensity_timespan(channel) >= LEAK_DETECTION_WINDOW:
        self._check_intensity_leak(channel)

def _queue_transmission_update(self, channel, data):
    """Queue transmission plot updates (deferred rendering)."""
    # Check if feature is enabled FIRST (skip if hidden)
    if not self._should_update_transmission():
        return

    transmission = data.get('transmission_spectrum')
    if transmission is not None and len(transmission) > 0:
        # Queue for batch update (like timeline graphs)
        self._pending_transmission_updates[channel] = {
            'transmission': transmission,
            'raw_spectrum': data.get('raw_spectrum')
        }
```

**Benefits:**
- Easier to profile individual handlers
- Can skip disabled features early
- Better code organization
- Easier testing and debugging

---

### 2. **Pre-compute Channel Mappings** ⭐⭐⭐
**Impact:** Eliminate ~500 dictionary lookups per second
**Risk:** None (pure optimization)

```python
# In __init__:
self._channel_to_idx = {'a': 0, 'b': 1, 'c': 2, 'd': 3}
self._idx_to_channel = ['a', 'b', 'c', 'd']
self._channel_pairs = [('a', 0), ('b', 1), ('c', 2), ('d', 3)]

# Use everywhere:
channel_idx = self._channel_to_idx[channel]  # Direct lookup, no computation
```

---

### 3. **Lazy Feature Evaluation** ⭐⭐
**Impact:** Skip 20-30% of processing when features are disabled
**Risk:** Very low (add early returns)

```python
def _should_update_transmission(self):
    """Check if transmission updates are needed."""
    if not hasattr(self.main_window, 'spectroscopy_enabled'):
        return False
    if not self.main_window.spectroscopy_enabled.isChecked():
        return False
    if not hasattr(self.data_mgr, 'ref_sig') or not self.data_mgr.ref_sig:
        return False
    return True

# Usage:
if not self._should_update_transmission():
    return  # Skip entire transmission block
```

**Add similar guards for:**
- Intensity leak detection (only if enabled)
- Cursor auto-follow (only if not being dragged)
- FWHM tracking (only if quality monitor active)

---

### 4. **Batch Transmission Updates Like Timeline** ⭐⭐⭐
**Impact:** Remove blocking UI calls from acquisition thread
**Risk:** Low (proven pattern already in use)

Currently transmission plots update immediately in `_on_spectrum_acquired()`:
```python
# CURRENT (BLOCKING):
self.main_window.transmission_curves[channel_idx].setData(wavelengths, transmission)
```

Should be queued like timeline graphs:
```python
# IMPROVED (QUEUED):
self._pending_transmission_updates[channel] = {'transmission': transmission, 'raw': raw_spectrum}

# Then in _process_pending_ui_updates():
for channel, update_data in self._pending_transmission_updates.items():
    if update_data is None:
        continue
    # ... update transmission plots in batch
```

---

### 5. **Reduce Redundant `len()` Calls** ⭐
**Impact:** Small but measurable (hundreds per second)
**Risk:** None

```python
# BEFORE:
if transmission is not None and len(transmission) > 0:
    if hasattr(self.main_window, 'transmission_curves'):
        channel_idx = {'a': 0, 'b': 1, 'c': 2, 'd': 3}[channel]
        wavelengths = self.data_mgr.wave_data
        if len(wavelengths) > 0:
            # ... use wavelengths

# AFTER:
if transmission is not None:
    transmission_len = len(transmission)
    if transmission_len == 0:
        return

    wavelengths = self.data_mgr.wave_data
    if wavelengths is None or len(wavelengths) != transmission_len:
        return

    # Now we know both arrays are valid and same length
```

---

### 6. **Move Complex Logging Out of Hot Path** ⭐⭐
**Impact:** Reduce string formatting overhead
**Risk:** None (logging only)

```python
# BEFORE (EVERY SPECTRUM):
if channel not in self._transmission_update_logged:
    logger.info(f"✅ Ch {channel.upper()}: Transmission plot updated! ({len(wavelengths)} points, range {np.min(transmission):.1f}-{np.max(transmission):.1f}%)")
    logger.info(f"🔍 Plot visible: {self.main_window.transmission_plot.isVisible()}, parent: {self.main_window.transmission_plot.parent()}")
    logger.info(f"🔍 Plot size: {self.main_window.transmission_plot.width()}x{self.main_window.transmission_plot.height()}")

# AFTER:
if channel not in self._transmission_update_logged:
    logger.info(f"✅ Ch {channel.upper()}: Transmission plot updated ({len(wavelengths)} points)")
    self._transmission_update_logged.add(channel)
```

Move detailed diagnostics to debug level or separate debug mode.

---

## Medium-Term Improvements (Higher Impact, More Work)

### 7. **Use NumPy Views Instead of Copies** ⭐⭐
**Impact:** Reduce memory allocations by 50%
**Risk:** Medium (need to understand data ownership)

```python
# BEFORE (COPIES):
if len(raw_time) > MAX_PLOT_POINTS:
    step = len(raw_time) // MAX_PLOT_POINTS
    display_time = raw_time[::step]  # Creates new array
    display_wavelength = display_wavelength[::step]  # Creates new array

# AFTER (VIEWS where possible):
if len(raw_time) > MAX_PLOT_POINTS:
    indices = np.linspace(0, len(raw_time)-1, MAX_PLOT_POINTS, dtype=int)
    display_time = raw_time[indices]  # Still creates new, but more efficient
    display_wavelength = display_wavelength[indices]
```

Better: Use LTTB downsampling (already in buffer manager!) for better visual quality.

---

### 8. **Implement Object Pooling for Data Dictionaries** ⭐
**Impact:** Reduce GC pressure from 160 allocations/sec
**Risk:** Medium (need careful lifecycle management)

```python
class DataPointPool:
    """Reusable data point dictionaries to reduce allocations."""
    def __init__(self, pool_size=50):
        self._pool = [self._create_data_point() for _ in range(pool_size)]
        self._available = self._pool.copy()

    def acquire(self):
        if self._available:
            return self._available.pop()
        return self._create_data_point()

    def release(self, data_point):
        # Clear data but keep structure
        for key in data_point:
            data_point[key] = None
        self._available.append(data_point)
```

---

### 9. **Separate Acquisition Thread from Processing** ⭐⭐⭐
**Impact:** Prevent acquisition jitter from processing overhead
**Risk:** High (significant architectural change)

Currently acquisition and processing happen in same thread. Better:

```
[Hardware Thread] → [Lock-free Queue] → [Processing Thread] → [UI Thread]
       ↓                                         ↓
  Raw spectra                            Feature extraction
  ~40 Hz                                 Graph queuing
                                         Buffer management
```

This prevents slow processing from delaying next acquisition.

---

### 10. **Profile-Guided Optimization** ⭐⭐⭐
**Impact:** Find actual bottlenecks (not guesses)
**Risk:** None (measurement only)

Add profiling hooks:
```python
import cProfile
import pstats
from contextlib import contextmanager

@contextmanager
def profile_section(name):
    """Profile a code section."""
    if not self._profiling_enabled:
        yield
        return

    profiler = cProfile.Profile()
    profiler.enable()
    try:
        yield
    finally:
        profiler.disable()
        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        logger.debug(f"Profile [{name}]:\n{stats}")

# Usage:
with profile_section("spectrum_processing"):
    self._on_spectrum_acquired(data)
```

---

## Implementation Priority

### Phase 1 (This Week) - **Quick Wins**
1. ✅ Add `_skip_graph_updates` for tab switching (DONE)
2. Pre-compute channel mappings (5 min)
3. Split `_on_spectrum_acquired()` into handlers (1 hour)
4. Add lazy feature evaluation guards (30 min)

**Expected improvement: 30-40% faster hot path**

### Phase 2 (Next Week) - **Threading Improvements**
5. Batch transmission updates like timeline (1 hour)
6. Move complex logging to debug level (15 min)
7. Reduce redundant len() calls (30 min)

**Expected improvement: Additional 15-20% reduction in UI blocking**

### Phase 3 (Future) - **Advanced Optimizations**
8. Implement object pooling for high-frequency allocations
9. Separate acquisition from processing threads
10. Add profiling infrastructure for ongoing optimization

---

## Measurement Strategy

Before each phase, measure:
1. **Spectrum processing time** (avg/max/p99)
2. **UI frame rate during acquisition** (should be 60 FPS)
3. **Memory growth rate** (MB/hour)
4. **Tab switch response time** (should be <100ms)

Use these metrics to validate improvements.

---

## Risk Mitigation

1. **Keep old code commented** during refactor
2. **Add unit tests** for extracted methods
3. **Test with real hardware** before merging
4. **Profile before/after** each change
5. **Use feature flags** to enable/disable new code paths

---

## Architecture Principles Going Forward

1. **Separate concerns**: Acquisition → Processing → Rendering
2. **Fail fast**: Check preconditions early, skip unnecessary work
3. **Lazy evaluation**: Don't compute what won't be displayed
4. **Batch operations**: Group UI updates, minimize setData() calls
5. **Profile-driven**: Measure, don't guess

---

## Questions to Answer

1. What's the target acquisition rate? (Currently ~10 Hz per channel)
2. Are all 4 channels always active? (Affects optimization priorities)
3. How long are typical experiments? (Affects buffer strategy)
4. Is offline post-processing a priority? (Affects data retention)
5. What's minimum acceptable UI responsiveness? (60 FPS? 30 FPS?)

---

## Tools Needed

- **cProfile**: Built-in Python profiler
- **memory_profiler**: Track memory growth
- **py-spy**: Sample running process (no code changes)
- **line_profiler**: Line-by-line performance
- **pytest-benchmark**: Regression testing for performance

---

## Success Metrics

After all refactoring:
- ✅ UI stays at 60 FPS during acquisition
- ✅ Tab switching <50ms response time
- ✅ Spectrum processing <5ms average
- ✅ Memory growth <100 MB/hour
- ✅ No acquisition jitter (consistent 10 Hz)
- ✅ CPU usage <40% on modern hardware
