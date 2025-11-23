# Performance Profiling Guide

## Overview

The SPR system now includes comprehensive performance profiling to identify actual bottlenecks and measure the impact of optimizations.

## Enabling Profiling

### Method 1: Settings File (Recommended)
Edit `settings/settings.py`:
```python
PROFILING_ENABLED = True  # Enable profiling
PROFILING_REPORT_INTERVAL = 60  # Print stats every 60 seconds (0 = disable periodic reports)
```

### Method 2: Environment Variable
```powershell
$env:SPR_PROFILING_ENABLED = "1"
python main_simplified.py
```

## What Gets Measured

The profiler tracks execution time for these critical operations:

### Acquisition Path (Hot Path - 40 Hz)
- **`spectrum_processing.total`** - Complete spectrum processing pipeline
- **`intensity_monitoring`** - Leak detection calculations
- **`transmission_queueing`** - Transmission spectrum preparation
- **`buffer_append`** - Data buffer operations

### UI Update Path (10 Hz)
- **`ui_update_timer`** - Overall UI update cycle
- **`filtering.online_smoothing`** - Median filter application
- **`graph_update.setData`** - PyQtGraph curve updates
- **`transmission_batch_process`** - Transmission plot updates

### User-Initiated Operations
- **`cycle_graph_update.total`** - Cycle of interest graph refresh

## Reading Profiling Output

### Periodic Reports (every 60s by default)
```
⏱️ PERIODIC PROFILING SNAPSHOT:
================================================================================
Operation                                  Count   Total(s)   Mean(ms)  Median(ms)    P95(ms)    P99(ms)    Max(ms)
--------------------------------------------------------------------------------
spectrum_processing.total                  2400      4.320       1.80       1.75       2.50       3.20       8.50
ui_update_timer                             600      1.250       2.08       2.00       2.80       3.50       6.20
filtering.online_smoothing                 2400      0.850       0.35       0.30       0.50       0.80       2.10
graph_update.setData                       2400      0.620       0.26       0.25       0.35       0.45       1.50
================================================================================
```

### Understanding the Metrics

| Metric | Meaning |
|--------|---------|
| **Count** | Number of times operation was called |
| **Total(s)** | Total cumulative time spent (seconds) |
| **Mean(ms)** | Average time per call (milliseconds) |
| **Median(ms)** | Middle value (50th percentile) |
| **P95(ms)** | 95th percentile - worst 5% of calls |
| **P99(ms)** | 99th percentile - worst 1% of calls |
| **Max(ms)** | Longest single call |

### Identifying Bottlenecks

1. **High Total Time** = Operation consuming most CPU time overall
2. **High Mean/Median** = Each call is slow (needs optimization)
3. **High P95/P99** = Inconsistent performance (needs investigation)
4. **High Max** = Occasional spikes (may indicate GC, blocking I/O, etc.)

## Example Analysis

### Scenario: Acquisition Running at 40 Hz (4 channels × 10 Hz each)

**Expected Measurements (60 second window):**
- `spectrum_processing.total`: ~2400 calls (40/sec × 60s)
- Each call should be < 2ms for smooth operation
- `ui_update_timer`: ~600 calls (10/sec × 60s)
- Each call should be < 10ms to maintain 10 FPS

**Red Flags:**
```
spectrum_processing.total    2400    12.000      5.00    <- TOO SLOW! Should be ~2ms
```
→ **Acquisition bottleneck**: Processing takes 5ms per spectrum, limiting frequency

```
graph_update.setData         2400     8.400      3.50    <- BLOCKING UI!
```
→ **UI bottleneck**: Graph updates taking 3.5ms each, causing visible lag

### Vectorization Impact Measurement

**Before Median Filter Vectorization:**
```
filtering.online_smoothing    2400    23.040      9.60    <- Manual loop implementation
```

**After scipy.ndimage.median_filter:**
```
filtering.online_smoothing    2400     0.150      0.06    <- Vectorized (160x faster!)
```

## Advanced Usage

### Export Data to CSV
```python
from utils.performance_profiler import get_profiler

profiler = get_profiler()
profiler.export_to_file("profiling_results.csv")
```

### Manual Timing
```python
from utils.performance_profiler import measure

# In any function
with measure('custom_operation'):
    expensive_function()
```

### Programmatic Access
```python
profiler = get_profiler()
stats = profiler.get_stats('spectrum_processing.total')
print(f"Mean time: {stats.mean_time * 1000:.2f}ms")
print(f"P95 time: {stats.p95_time * 1000:.2f}ms")
```

## Performance Targets

### Real-Time Acquisition (40 Hz total, 10 Hz per channel)

| Operation | Target | Critical? |
|-----------|--------|-----------|
| Spectrum processing | < 2ms | ✅ YES - blocks acquisition |
| Intensity monitoring | < 0.5ms | ✅ YES - in acquisition path |
| Buffer append | < 0.1ms | ✅ YES - in acquisition path |
| UI update timer | < 10ms | ⚠️ IMPORTANT - affects responsiveness |
| Graph setData | < 1ms | ⚠️ IMPORTANT - cumulative impact |
| Filtering | < 0.5ms | ⚠️ IMPORTANT - called per spectrum |

### Non-Critical Operations (User-Initiated)
- Cycle graph update: < 50ms (acceptable lag)
- CSV export: < 500ms (one-time operation)
- Image export: < 1000ms (one-time operation)

## Troubleshooting

### Profiling Has No Effect
- Check `PROFILING_ENABLED = True` in settings
- Restart application after changing settings
- Check logs for "⏱️ Performance profiling ENABLED"

### High Overhead from Profiling
- Profiling adds ~0.01-0.05ms per `with measure()` block
- Negligible for operations > 1ms
- Disable periodic reports: `PROFILING_REPORT_INTERVAL = 0`

### Missing Expected Operations
- Operation may not have been called yet (check Count)
- `min_calls` filter may be hiding low-frequency operations
- Try: `profiler.print_stats(min_calls=1)`

## Optimization Workflow

1. **Enable profiling** and run system normally for 5-10 minutes
2. **Review hotspots** - what operations consume most total time?
3. **Check mean times** - are individual calls slow?
4. **Investigate high P95/P99** - what causes outliers?
5. **Optimize** the slowest bottleneck first
6. **Re-measure** to verify improvement
7. **Repeat** until performance targets met

## Example: Finding a Bottleneck

```
TOP 10 HOTSPOTS (by total time)
================================================================================
 1. spectrum_processing.total              18.240s (45.6%) [4800 calls, 3.80ms avg]
 2. graph_update.setData                   12.100s (30.3%) [4800 calls, 2.52ms avg]
 3. filtering.online_smoothing              5.120s (12.8%) [4800 calls, 1.07ms avg]
 4. ui_update_timer                         3.200s  (8.0%) [1200 calls, 2.67ms avg]
================================================================================
```

**Interpretation:**
- **45% of time** in spectrum processing → Check what's inside
- **30% of time** in graph updates → PyQtGraph performance issue?
- **12% of time** filtering → Already optimized (1ms is good for this)
- **8% of time** UI timer → Acceptable overhead

**Action:** Investigate `graph_update.setData` - 2.5ms per call is high for simple curve update.

## Integration with Existing Optimizations

This profiler complements the multi-phase optimization work:

- **Phase 1** (Mappings): Eliminated dictionary allocations → measure with `buffer_append`
- **Phase 2** (Batch Updates): Reduced UI blocking → measure with `transmission_batch_process`
- **Phase 3** (Threading): Separated acquisition/processing → measure queue stats separately
- **Vectorization**: Faster filtering → measure with `filtering.online_smoothing`

Now you can **quantify** the impact of each optimization!
