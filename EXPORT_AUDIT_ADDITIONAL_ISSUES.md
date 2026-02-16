# Export Audit - Additional Issues Found

**Review Date**: February 16, 2026  
**Reviewer**: Analysis of previous quick wins implementation  
**Status**: 🔴 Additional issues identified

---

## Summary of Review

### ✅ What Was Fixed (Quick Win #1)
- Centralized cycle deduplication
- Eliminated 45+ lines of duplicated code
- Added dedup tracking to DataCollector
- All 3 export paths now use shared utility

### 🔴 Additional Issues Found

---

## Issue #2: Channels XY Sheet Generation Duplicated 3 Times

**Severity**: HIGH  
**Impact**: ~120 lines of duplicated code  
**Complexity**: MEDIUM (2-3 hours to fix)

### Current State

**Duplication locations:**
1. `recording_manager.py` lines 195-237 (~42 lines)
2. `export_helpers.py` lines 513-547 (~34 lines)  
3. `export_helpers.py` lines 580-607 (~27 lines)

**All three do the same thing:**
```python
# Pattern (repeated 3x):
1. Find max length across all channels
2. Iterate through channels
3. Get time and SPR arrays from buffer_mgr.cycle_data[ch]
4. Pad arrays to max_len with np.nan
5. Build sheet_data dict with Time_A, SPR_A, Time_B, SPR_B, etc.
6. Create DataFrame and write to Excel
```

### Recommended Fix

Create shared utility method:

```python
# In export_helpers.py
@staticmethod
def build_channels_xy_dataframe(buffer_mgr, channels: list[str] = None) -> pd.DataFrame:
    """Build Channels XY DataFrame for Excel export.
    
    Creates wide-format DataFrame with Time_A, SPR_A, Time_B, SPR_B columns.
    All arrays padded to same length with NaN.
    
    Args:
        buffer_mgr: DataBufferManager instance
        channels: List of channel letters (default: ['a', 'b', 'c', 'd'])
        
    Returns:
        DataFrame with Channels XY data
    """
    if channels is None:
        channels = ['a', 'b', 'c', 'd']
    
    # Find max length across all channels
    max_len = 0
    for ch in channels:
        if hasattr(buffer_mgr.cycle_data[ch], 'time'):
            max_len = max(max_len, len(buffer_mgr.cycle_data[ch].time))
    
    if max_len == 0:
        return pd.DataFrame()  # Empty DataFrame
    
    # Build sheet data
    sheet_data = {}
    for ch in channels:
        ch_upper = ch.upper()
        
        # Get time and SPR data for this channel
        if hasattr(buffer_mgr.cycle_data[ch], 'time'):
            ch_time = np.array(buffer_mgr.cycle_data[ch].time)
            ch_spr = np.array(buffer_mgr.cycle_data[ch].spr)
            
            # Pad to max length if needed
            if len(ch_time) < max_len:
                ch_time = np.pad(ch_time, (0, max_len - len(ch_time)), constant_values=np.nan)
            if len(ch_spr) < max_len:
                ch_spr = np.pad(ch_spr, (0, max_len - len(ch_spr)), constant_values=np.nan)
        else:
            # Channel has no data - fill with NaN
            ch_time = np.full((max_len,), np.nan)
            ch_spr = np.full((max_len,), np.nan)
        
        sheet_data[f"Time_{ch_upper}"] = ch_time
        sheet_data[f"SPR_{ch_upper}"] = ch_spr
    
    return pd.DataFrame(sheet_data)
```

**Then replace all 3 duplications with:**
```python
# recording_manager.py
df_xy = ExportHelpers.build_channels_xy_dataframe(self.buffer_mgr)
df_xy.to_excel(writer, sheet_name='Channels XY', index=False)

# export_helpers.py (2 places)
df_xy = ExportHelpers.build_channels_xy_dataframe(app.buffer_mgr, channels)
df_xy.to_excel(writer, sheet_name='Channels XY', index=False)
```

**Impact**: Reduce 120 lines to ~60 lines (shared utility + 3 short calls)

---

## Issue #3: Auto-Save Inefficiency

**Severity**: MEDIUM  
**Impact**: Unnecessary I/O every 60 seconds  
**Complexity**: MEDIUM (3-4 hours including testing)

### Current State

**Location**: `recording_manager.py`
- Line 58: `self.auto_save_interval = 60  # seconds`
- Line 294: Timer check inside `record_data_point()` triggers full Excel write

**Problem**:
```python
# In record_data_point():
if self.current_file:
    current_time = time.time()
    if current_time - self.last_save_time >= self.auto_save_interval:
        self._save_to_file()  # Full Excel write every 60 seconds!
        self.last_save_time = current_time
```

**Issues**:
1. Writes entire Excel workbook every 60 seconds (expensive)
2. Blocks if file is locked
3. Fixed interval regardless of data volume
4. No user control

### Recommended Fix

Replace timer-based with event-based saves:

```python
class RecordingManager:
    def __init__(self, ...):
        # Replace fixed interval with configurable options
        self.auto_save_enabled = True
        self.auto_save_on_cycle = True  # Save when cycle completes
        self.auto_save_on_event = True  # Save on injection/flag markers
        self.auto_save_interval = None  # Disable timer-based (or make optional)
    
    def on_cycle_completed(self, cycle_data: dict):
        """Called when a cycle completes - event-driven save."""
        if self.auto_save_enabled and self.auto_save_on_cycle:
            self._save_to_file()
    
    def on_event_logged(self, event: str):
        """Called when important event occurs."""
        if self.auto_save_enabled and self.auto_save_on_event:
            if event in ['injection', 'regeneration']:  # Important events
                self._save_to_file()
```

**Impact**: 
- Eliminates periodic I/O
- Saves on meaningful events (cycle completion, injections)
- User can configure auto-save behavior
- Reduces file lock conflicts

---

## Issue #4: Data Source Inconsistency

**Severity**: MEDIUM  
**Impact**: Export/Record paths use different data sources  
**Complexity**: LOW (1-2 hours)

### Current State

**Data flow inconsistency:**

```
Export Button Path:
  → Reads buffer_mgr.cycle_data[ch].time directly
  → Bypasses DataCollector entirely!

Record Button Path:
  → Uses data_collector.raw_data_rows for raw data
  → BUT still reads buffer_mgr.cycle_data for Channels XY sheet
  → Mixed data sources
```

**Problem**: Export and Record access raw buffer manager differently:
- Export: `app.buffer_mgr.cycle_data[ch].time` (direct)
- Record: `self.buffer_mgr.cycle_data[ch].time` (same, but through self reference)
- Both bypass data_collector for channel data

### Recommended Fix

Option 1: **Make buffer_mgr the single source** (simplest)
- Document that buffer_mgr is canonical for real-time channel data
- DataCollector is for accumulated point data only
- Keep current behavior but add comments explaining architecture

Option 2: **Add wrapper method** (better encapsulation)
```python
# In RecordingManager or DataCollector
def get_channel_export_data(self, channel: str) -> dict:
    """Get export-ready channel data.
    
    Returns:
        dict with 'time' and 'spr' arrays
    """
    return {
        'time': self.buffer_mgr.cycle_data[channel].time,
        'spr': self.buffer_mgr.cycle_data[channel].spr
    }
```

Then both export paths call this method instead of direct buffer access.

**Impact**: 
- Clearer separation of concerns
- Single accessor method
- Easier to refactor later if needed

---

## Issue #5: Directory Structure Inconsistency

**Severity**: LOW  
**Impact**: User confusion about where files are saved  
**Complexity**: LOW (30 minutes)

### Current State

| Export Path | Default Directory |
|-------------|------------------|
| Export Button | `~/Documents/Affilabs Data/<user>/SPR_data/` |
| Record Button | `~/Documents/Affilabs Data/` (parent folder) |
| Quick CSV | `~/Documents/Affilabs Data/<user>/SPR_data/` |
| Autosave | `data/cycles/YYYYMMDD/` OR session folder |
| Edits Save | Original file location (in-place) |

**Problem**: Inconsistent defaults make it hard to find files

### Recommended Fix

Standardize all paths:
```python
# Create path utility
class ExportPaths:
    @staticmethod
    def get_default_export_dir(username: str = None) -> Path:
        """Get standardized export directory."""
        base = Path.home() / "Documents" / "Affilabs Data"
        if username:
            return base / username / "exports"
        return base / "exports"
    
    @staticmethod
    def get_recording_dir(username: str = None) -> Path:
        """Get recording directory."""
        base = Path.home() / "Documents" / "Affilabs Data"
        if username:
            return base / username / "recordings"
        return base / "recordings"
    
    @staticmethod
    def get_autosave_dir(username: str = None) -> Path:
        """Get autosave directory."""
        base = Path.home() / "Documents" / "Affilabs Data"
        if username:
            return base / username / "autosave"
        return base / "autosave"
```

All export paths use these utilities for consistent folder structure.

---

## Issue #6: ExcelExporter Service Unused

**Severity**: HIGH  
**Impact**: Dead code, missed opportunities for consolidation  
**Complexity**: MEDIUM (4-5 hours including testing)

### Current State

**Location**: `affilabs/services/excel_exporter.py` (362 lines)

**Status**: ❌ COMPLETELY UNUSED

```python
# RecordingManager instantiates it but never calls it:
class RecordingManager:
    def __init__(self, ...):
        self.excel_exporter = ExcelExporter()  # Created
        # But _save_to_file() has inline Excel logic instead!
```

**Problem**:
- ExcelExporter.export_to_excel() exists with full implementation
- recording_manager._save_to_file() reimplements Excel export inline (~100 lines)
- export_helpers.export_requested() also reimplements Excel export inline (~150 lines)
- Total duplication: ~250 lines that could use the 1 service

### Recommended Fix

**Replace inline implementations with ExcelExporter calls:**

```python
# In recording_manager._save_to_file():
if filepath.suffix == ".xlsx":
    # BEFORE: 100 lines of inline Excel logic
    # AFTER:
    self.excel_exporter.export_to_excel(
        filepath=filepath,
        raw_data_rows=self.data_collector.raw_data_rows,
        cycles=self.data_collector.cycles,
        flags=self.data_collector.flags,
        events=self.data_collector.events,
        analysis_results=self.data_collector.analysis_results,
        metadata=self.data_collector.metadata,
        recording_start_time=self.data_collector.recording_start_time,
        alignment_data=None
    )

# In export_helpers.export_requested():
if format_type == 'excel':
    # BEFORE: 150 lines of inline Excel logic
    # AFTER:
    from affilabs.services.excel_exporter import ExcelExporter
    exporter = ExcelExporter()
    exporter.export_to_excel(
        filepath=full_path,
        raw_data_rows=raw_data_rows,
        cycles=cycles_data,
        flags=app.recording_mgr.data_collector.flags if hasattr(...) else [],
        events=app.recording_mgr.data_collector.events if hasattr(...) else [],
        analysis_results=[],
        metadata=app.recording_mgr.data_collector.metadata if hasattr(...) else {},
        recording_start_time=app.recording_mgr.data_collector.recording_start_time if hasattr(...) else time.time(),
        alignment_data=None
    )
```

**Impact**:
- Eliminate ~250 lines of duplicated Excel logic
- Use already-written, well-tested service
- Single source of truth for Excel export
- Easier to add features (all export paths benefit)

---

## Priority Ranking

| Priority | Issue | Effort | Impact | Quick Win? |
|----------|-------|--------|--------|------------|
| 🔴 1 | #6: Use ExcelExporter service | 4-5h | Eliminates 250 lines | YES (medium) |
| 🔴 2 | #2: Consolidate Channels XY | 2-3h | Eliminates 120 lines | YES (easy) |
| 🟡 3 | #3: Event-based auto-save | 3-4h | Better performance | NO (complex) |
| 🟡 4 | #4: Data source wrapper | 1-2h | Better architecture | YES (easy) |
| 🟢 5 | #5: Standardize directories | 30m | Better UX | YES (trivial) |

---

## Recommended Next Steps

### Immediate (can do now):
1. ✅ **Fix #2: Consolidate Channels XY generation** - 2-3 hours
   - Create `ExportHelpers.build_channels_xy_dataframe()`
   - Replace 3 duplications
   - Test all export paths

2. ✅ **Fix #5: Standardize directories** - 30 minutes
   - Create path utility class
   - Update all export paths to use it

### Short-term (next session):
3. **Fix #6: Use ExcelExporter service** - 4-5 hours
   - Refactor recording_manager to call ExcelExporter
   - Refactor export_helpers to call ExcelExporter
   - Add Channels XY logic to ExcelExporter if missing
   - Comprehensive testing

4. **Fix #4: Data source wrapper** - 1-2 hours
   - Create buffer access wrapper
   - Update both paths to use it

### Long-term (future planning):
5. **Fix #3: Event-based auto-save** - 3-4 hours
   - Design event system
   - Integration with cycle coordinator
   - User settings for auto-save preferences

---

## Code Quality Metrics

### Before Additional Fixes:
- Duplicated code: ~370 lines
  - Channels XY: 120 lines
  - Excel export: 250 lines
- Export paths: 6 different implementations
- Data sources: Mixed (buffer_mgr + data_collector)
- Auto-save: Timer-based (inefficient)

### After All Fixes:
- Duplicated code: ~50 lines (remaining)
- Export paths: 2 unified (ExcelExporter + CSV utility)
- Data sources: Consistent wrapper
- Auto-save: Event-driven
- **Total reduction: ~320 lines eliminated**

---

## Testing Requirements

Before merging any fixes:
- [ ] Test Export button creates valid Excel
- [ ] Test Record button stops and saves correctly
- [ ] Test Quick CSV export works
- [ ] Test Autosave creates files
- [ ] Test Edits tab save preserves data
- [ ] Test all 4 channels export correctly
- [ ] Test empty channels handled (NaN padding)
- [ ] Test no duplicate cycles in output
- [ ] Compare output files from all paths (should be identical)
- [ ] Performance test: auto-save doesn't block UI

---

## Conclusion

The initial quick win successfully eliminated cycle deduplication duplication. However, **5 additional issues remain** that follow the same pattern of code duplication and inconsistency.

**Most valuable next fixes (ranked by ROI):**
1. Consolidate Channels XY generation (120 lines saved, 2-3h effort)
2. Use ExcelExporter service (250 lines saved, 4-5h effort)
3. Standardize directory paths (better UX, 30m effort)

Implementing these 3 would eliminate **~370 additional lines of duplication** and significantly improve export consistency.
