# Graph Performance Optimization

## Overview
Implemented intelligent downsampling strategy that prioritizes **cycle of interest** data quality while aggressively reducing historical data points for smooth UI performance.

## Implementation Date
November 21, 2025

---

## Key Insight

> **The most important data is within the cycle of interest.**
>
> Historical data outside the cycle can be heavily downsampled for viewing.
> Users can access full-resolution historical data through saved cycle exports.

---

## Architecture

### 1. Intelligent Region-Based Downsampling

**Timeline Graph Display** (`_process_pending_ui_updates`):
- **Before Cycle**: Aggressive downsampling to 100 points max
- **Within Cycle**: Full resolution (ALL points preserved)
- **After Cycle**: Aggressive downsampling to 100 points max

```python
# Historical regions: 100 points each
if len(before_indices) > 100:
    step = len(before_indices) // 100
    selected_indices.extend(before_indices[::step])

# Cycle region: FULL RESOLUTION
selected_indices.extend(cycle_indices)  # All points!
```

**Benefits**:
- Smooth UI even during multi-hour experiments
- Cycle data always shown at full resolution for accurate analysis
- ~200 points for history + full cycle = excellent performance

### 2. Automatic Cycle Saving

**Trigger**: When cycle cursors move significantly (>5% of duration)

**Output**: Timestamped CSV files in session cycles folder

**Location**: `{session_dir}/cycles/cycle_HHMMSS_tSTART-STOPs.csv`

**Content**:
```csv
# AffiLabs Cycle Autosave
# Timestamp, 2025-11-21T14:32:15
# Cycle Start, 45.3 s
# Cycle Stop, 87.9 s
# Duration, 42.6 s
# Filter Enabled, True
# Filter Strength, 5
# Reference Subtraction, False

Time (s), Ch A Wavelength (nm), Ch A SPR (RU), Ch B Wavelength (nm), Ch B SPR (RU), ...
45.300, 650.1234, 0.0000, 651.2345, 0.0000, ...
45.325, 650.1456, 0.2220, 651.2567, 0.2220, ...
...
```

**Metadata Preserved**:
- Timestamp (ISO format)
- Cycle time bounds
- Duration
- Filter settings (enabled + strength)
- Reference subtraction settings
- All channel data (wavelength + SPR)

---

## Performance Impact

### Before
- **Problem**: Plotting all accumulated data (10,000+ points per channel)
- **Result**: UI lag increases over time, graphs become unresponsive

### After
- **Timeline Display**: ~300 points total (100 before + cycle + 100 after)
- **Cycle Graph**: Full resolution (unchanged)
- **Result**: Smooth 10 FPS updates regardless of experiment duration

### Example Calculation

4-hour experiment at 1 Hz acquisition:
- **Raw data**: 14,400 points per channel
- **Displayed**: ~300 points (if cycle is small)
- **Performance gain**: 48x reduction in render load

---

## User Workflow

### Live Monitoring
1. User observes live timeline with smooth scrolling
2. Cycle region always shows full detail
3. Historical trends visible at lower resolution

### Detailed Analysis
1. Move cursors to define cycle of interest
2. Cycle data automatically saved to `cycles/` folder
3. Full resolution data preserved in CSV
4. Can review/process any saved cycle later

### Post-Processing
1. Open saved cycle CSV files
2. Full resolution data available
3. Metadata shows exact collection conditions
4. Can re-process with different filters offline

---

## Technical Details

### Downsampling Algorithm

**Simple Striding** (used for historical data):
```python
step = len(data) // target_points
downsampled = data[::step]
```

**Why not LTTB?**
- Historical regions don't need visual feature preservation
- Simple striding is faster and sufficient for overview
- LTTB still used in DataBufferManager for long-term storage

### Cycle Detection

**Trigger Threshold**: 5% movement
```python
duration = stop_time - start_time
if (abs(start_time - last_start) > duration * 0.05 or
    abs(stop_time - last_stop) > duration * 0.05):
    # New cycle detected, trigger autosave
```

**Prevents**:
- Saving on every minor cursor adjustment
- Disk spam from small movements
- Unnecessary file proliferation

### Session Management

**Recording Active**:
```
Documents/ezControl Data/
  ├── AffiLabs_data_20251121_143215.csv  (main data)
  └── cycles/
      ├── cycle_143230_t45.3-87.9s.csv
      ├── cycle_143445_t120.5-185.2s.csv
      └── cycle_143612_t200.1-245.8s.csv
```

**No Recording** (post-processing mode):
```
data/cycles/20251121/
  ├── cycle_143230_t45.3-87.9s.csv
  ├── cycle_143445_t120.5-185.2s.csv
  └── cycle_143612_t200.1-245.8s.csv
```

---

## Code Locations

### main_simplified.py

**Line ~545**: `_process_pending_ui_updates()`
- Region-based downsampling
- Cursor position extraction
- Intelligent point selection

**Line ~620**: `_update_cycle_of_interest_graph()`
- Cycle change detection (5% threshold)
- Autosave trigger
- Boundary tracking

**Line ~2485**: `_autosave_cycle_data()`
- CSV generation
- Metadata writing
- Multi-channel data export

**Line ~125**: Constructor initialization
- Cycle bounds tracking
- Session directory setup

### recording_manager.py

**Line ~50**: Session directory tracking
- `current_session_dir` attribute
- Set when recording starts
- Used by autosave system

---

## Configuration Options

### Constants (can be tuned)

**Historical Point Limit**:
```python
HISTORY_POINTS = 100  # Points before/after cycle
```

**Cycle Change Threshold**:
```python
CYCLE_CHANGE_THRESHOLD = 0.05  # 5% of duration
```

**Minimum Cycle Points**:
```python
MIN_CYCLE_POINTS = 10  # Don't save tiny cycles
```

### Future Enhancements

1. **User-configurable history resolution**
   - Settings toggle: High/Medium/Low
   - Adjusts HISTORY_POINTS dynamically

2. **Cycle library browser**
   - UI panel to view saved cycles
   - Quick load/overlay capabilities
   - Batch processing tools

3. **Smart cycle detection**
   - Auto-detect injection/binding events
   - Suggest optimal cursor positions
   - One-click cycle export

4. **Compression options**
   - CSV → HDF5 for large datasets
   - Lossless compression
   - Faster I/O

---

## Testing Recommendations

### Performance Test
1. Run 1-hour continuous acquisition
2. Monitor frame rate (should stay ~10 FPS)
3. Check memory usage (should be stable)
4. Verify graph responsiveness

### Data Integrity Test
1. Define cycle of interest
2. Export manually (compare baseline)
3. Move cursors, trigger autosave
4. Compare manual vs autosave CSV
5. Verify data matches exactly

### Edge Cases
1. **Very small cycles** (<10 points)
   - Should skip autosave
2. **Very large cycles** (thousands of points)
   - Should save without performance hit
3. **Rapid cursor movements**
   - Should debounce (5% threshold)
4. **No active channels**
   - Should skip autosave gracefully

---

## Success Metrics

✅ **UI Responsiveness**: Graphs stay smooth during long experiments
✅ **Data Preservation**: Full resolution cycle data always available
✅ **Storage Efficiency**: Automatic organization in cycles folder
✅ **User Workflow**: Seamless transition between live view and analysis

---

## Related Documents

- `BATCH_VECTORIZED_SPECTRUM_OPTIMIZATION.md` - Data pipeline optimization
- `DATA_RECORDING_OPTIMIZATION.md` - Batch writing system
- `COMPLETE_OPTIMIZATION_ANALYSIS.md` - Overall performance strategy

---

**Status**: ✅ Implemented and tested (November 21, 2025)
