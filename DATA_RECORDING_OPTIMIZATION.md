# Data Recording Optimization for Long Experiments

## Problem Statement

For long experiments (4+ hours at 1 Hz sampling rate across 4 channels):
- **Data volume**: 14,400 points/channel × 4 channels = **57,600 total data points**
- **Old approach**: Write every single point immediately to CSV
- **Issues**:
  - 57,600 individual write operations
  - I/O overhead accumulates over time
  - 60-second flush intervals = potential data loss window
  - Not optimal for sustained high-frequency data collection

## New Batch Buffering Strategy

### Core Improvements

#### 1. **Batch Buffering (100x Reduction in Write Operations)**
```python
BUFFER_SIZE = 100  # Write every 100 data points
```

**Old system**: 57,600 writes
**New system**: ~576 writes (100x fewer!)

- Data points accumulate in memory buffer
- Buffer flushes when reaching 100 points
- At 1 Hz × 4 channels: Flush every ~25 seconds

#### 2. **Reduced Flush Interval (Better Safety)**
```python
FLUSH_INTERVAL = 10  # Force flush every 10 seconds
```

**Old system**: 60 seconds = potential data loss
**New system**: 10 seconds = minimal risk

- Safety net for variable acquisition rates
- Ensures data reaches disk regularly
- Maximum data loss: ~40 points (10 sec × 4 channels)

#### 3. **Event-Triggered Flush (Critical Timestamp Preservation)**

Immediate flush when logging events:
- Injections
- Valve switches
- Protocol changes
- User markers

**Benefit**: Critical timestamps guaranteed on disk before continuing

### Performance Metrics

| Metric | Old System | New System | Improvement |
|--------|-----------|------------|-------------|
| Write Operations (4 hrs) | 57,600 | ~576 | **100x fewer** |
| Flush Interval | 60 sec | 10 sec | **6x safer** |
| Max Data Loss | ~240 points | ~40 points | **6x less risk** |
| I/O Overhead | High | Minimal | **Significant** |
| Event Safety | Delayed | Immediate | **Critical fix** |

## Implementation Details

### Buffer Management

```python
# core/recording_manager.py

class RecordingManager:
    BUFFER_SIZE = 100      # Points before flush
    FLUSH_INTERVAL = 10    # Seconds between forced flush

    def __init__(self):
        self.write_buffer = []        # In-memory buffer
        self.points_written = 0       # Statistics tracking
        self.last_flush_count = 0     # Logging throttle
```

### Write Flow

```
Data Point Arrives
      ↓
Add to Buffer (write_buffer.append)
      ↓
Check Conditions:
  - Buffer size ≥ 100? → Flush
  - Time > 10 sec?     → Flush
  - Event logged?      → Flush
      ↓
Flush: writerows() → file.flush()
      ↓
Update Statistics
```

### Automatic Flush Triggers

1. **Size-based**: `len(write_buffer) >= BUFFER_SIZE`
2. **Time-based**: `elapsed_time >= FLUSH_INTERVAL`
3. **Event-based**: `log_event()` called
4. **Stop-based**: `stop_recording()` called

## Configuration

### Tuning for Different Scenarios

**Fast acquisition (>5 Hz per channel)**:
```python
BUFFER_SIZE = 200      # Larger buffer (less frequent writes)
FLUSH_INTERVAL = 5     # More frequent safety flushes
```

**Slow acquisition (<0.5 Hz per channel)**:
```python
BUFFER_SIZE = 50       # Smaller buffer (faster to disk)
FLUSH_INTERVAL = 30    # Less frequent flushes (lower overhead)
```

**Critical experiments (maximum safety)**:
```python
BUFFER_SIZE = 50       # Small buffer
FLUSH_INTERVAL = 5     # Frequent flushes
```

**Ultra-long experiments (days, not hours)**:
```python
BUFFER_SIZE = 500      # Larger buffer
FLUSH_INTERVAL = 15    # Balance performance and safety
```

## Monitoring and Diagnostics

### Recording Statistics

```python
info = recording_manager.get_recording_info()
# Returns:
{
    'recording': True,
    'filename': 'AffiLabs_data_20251121_143022.csv',
    'elapsed_time': 3847.2,          # seconds
    'event_count': 12,                # logged events
    'points_written': 15234,          # total points written to disk
    'buffered_points': 47,            # currently in buffer (not flushed)
    'avg_rate': 3.96                  # points/sec average
}
```

### Log Messages

**Initialization**:
```
RecordingManager initialized with batch buffering (buffer_size=100, flush_interval=10s)
```

**Periodic flush logging** (every 1000 points):
```
💾 Flushed 100 points to disk (1000 total)
💾 Flushed 100 points to disk (2000 total)
...
```

**Final statistics** (on stop):
```
📊 Recording stats: 57600 points written in 14400.5s (4.00 points/sec)
```

## Comparison with Old Software

### Old Software Approach
- ✅ Immediate write = data always saved
- ❌ 57,600 individual writes = high I/O overhead
- ❌ No optimization for long experiments
- ❌ Potential performance degradation over time

### New Approach
- ✅ Batch writes = 100x fewer I/O operations
- ✅ Configurable safety/performance trade-off
- ✅ Event-triggered flush = critical timestamps preserved
- ✅ Statistics tracking for monitoring
- ✅ Optimized for multi-hour experiments
- ✅ 10-second flush = better safety than old 60-second

## Data Integrity Guarantees

1. **Buffer never lost**: Exception handling preserves buffer on write errors
2. **Events force flush**: Critical timestamps always saved before continuing
3. **Stop flushes all**: `stop_recording()` guarantees all buffered data written
4. **10-second maximum lag**: Time-based flush ensures data reaches disk regularly
5. **Chronological order**: Flush before events maintains timeline consistency

## Future Enhancements

### Potential Improvements

1. **Adaptive buffer sizing**: Adjust BUFFER_SIZE based on acquisition rate
2. **Compression**: Use gzip for large files (`.csv.gz`)
3. **Binary format**: Switch to HDF5 or Parquet for huge datasets
4. **Real-time export**: Stream to multiple formats simultaneously
5. **Cloud sync**: Auto-upload to cloud storage during acquisition
6. **Checkpointing**: Save metadata periodically for recovery

### Binary Format Comparison

| Format | Size (4 hrs) | Read Speed | Write Speed | Compression |
|--------|-------------|------------|-------------|-------------|
| CSV | ~15 MB | Slow | Medium | None |
| CSV.GZ | ~3 MB | Medium | Medium | High |
| HDF5 | ~8 MB | Very Fast | Fast | Medium |
| Parquet | ~2 MB | Very Fast | Fast | High |

**Recommendation**: CSV for compatibility, consider HDF5/Parquet for very long experiments (days).

## Testing Recommendations

### Validation Tests

1. **Normal operation**: Record 1000 points, verify all written
2. **Event logging**: Add events, verify flush occurs
3. **Crash recovery**: Kill process mid-recording, check data integrity
4. **Long experiment**: 4-hour test at 1 Hz, monitor performance
5. **Buffer edge cases**: Fill buffer exactly, verify flush
6. **Timing verification**: Confirm 10-second flushes under slow acquisition

### Performance Benchmarks

Expected results for 4-hour experiment:
- Total points: 57,600
- Write operations: ~576 (100x reduction)
- Average flush time: <50 ms
- Total I/O time: <30 seconds (over 4 hours)
- Max latency: 10 seconds

## Migration Notes

### Compatibility

- ✅ CSV format unchanged (backward compatible)
- ✅ Header and footer structure preserved
- ✅ Event log format identical
- ✅ File naming convention maintained
- ✅ Works with existing analysis tools

### Breaking Changes

None - this is a pure performance optimization with no API changes.

## Summary

The batch buffering system provides:
- **100x reduction** in write operations
- **6x better safety** (10 sec vs 60 sec flush)
- **Event-triggered flush** for critical timestamps
- **Configurable trade-offs** for different scenarios
- **Full backward compatibility** with existing data format

For 4-hour experiments, this transforms data recording from a potential bottleneck into a negligible overhead operation.
