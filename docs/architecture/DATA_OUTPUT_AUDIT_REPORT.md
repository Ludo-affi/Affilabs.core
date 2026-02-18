# Data Output Audit Report - Cycle Time & Data Integrity

**Date:** 2026-02-12
**Status:** ⚠️ CRITICAL ISSUES FOUND

---

## Executive Summary

Audit of the cycle data export pipeline has identified **4 critical issues** affecting data integrity:

1. **Cycles are NOT being recorded during live execution** - No mechanism to track cycle timing
2. **Cycle duration_minutes may not reflect actual recorded time** - Uses fallback to planned duration
3. **Potential duplicate cycles in export** - Deduplication band-aid applied, not root cause fixed
4. **Ambiguous end_time_sensorgram values** - May be null or missing during export

---

## Issue 1: Cycles Not Recorded During Live Execution ⚠️ CRITICAL

### Location
- `recording_mgr.add_cycle()` exists at: `affilabs/core/recording_manager.py:382`
- `DataCollector.add_cycle()` exists at: `affilabs/services/data_collector.py:99`
- **BUT**: These methods are NEVER CALLED during cycle execution

### Current behavior
- Cycles are only added to data collector when **loading from Excel** (affilabs_core_ui.py:3412)
- Live experiments running through the queue have NO cycle tracking
- Completed cycle data is stored in `QueueManager._completed` list but never exported

### Impact
- **No cycle timing data** is recorded for live experiments
- Exported Excel files from live runs will have empty or incomplete Cycles sheet
- Users cannot verify which cycles ran and when

### Root Cause
The cycle execution pipeline (in queue execution) doesn't call `recording_mgr.add_cycle()`:
- `QueueManager.mark_completed()` only appends to a local list (queue_manager.py:240)
- No trigger to export completed cycle data to recording manager
- `cycle.complete(end_time_sensorgram: float)` method exists but is never called during execution

---

## Issue 2: Duration Calculation Can Use Stale Data ⚠️ HIGH PRIORITY

### Location
`affilabs/domain/cycle.py:169-189` (Cycle.to_export_dict method)

### Current Code
```python
def to_export_dict(self) -> dict:
    # Calculate actual duration if both start and end times are available
    # Otherwise use planned duration (length_minutes)
    actual_duration = self.length_minutes
    if self.sensorgram_time is not None and self.end_time_sensorgram is not None:
        actual_duration = (self.end_time_sensorgram - self.sensorgram_time) / 60.0

    return {
        "duration_minutes": actual_duration,
        "length_minutes": self.length_minutes,  # Keep planned duration for reference
        ...
    }
```

### Problem
- If `end_time_sensorgram` is **never set** (Issue #1), it defaults to `None`
- Fall back to `length_minutes` (the PLANNED duration)
- Users cannot distinguish between planned vs actual recorded time
- No indication that actual timing was not captured

### Impact
- Duration column in Excel may show planned time instead of actual recording time
- Users cannot audit if cycles ran for the correct duration
- Data integrity cannot be verified

### Example Scenario
```
Planned duration:  5.0 minutes
Actual recording:  4.3 minutes (due to manual stop)
Exported duration: 5.0 minutes ❌ (because end_time_sensorgram was None)
```

---

## Issue 3: Deduplication Indicates Upstream Problem ⚠️ MEDIUM PRIORITY

### Locations
- `affilabs/services/excel_exporter.py:123-133`
- `affilabs/utils/export_helpers.py:503-513`
- `affilabs/core/recording_manager.py:177-187`

### Current Code (Excel Exporter)
```python
# Deduplicate cycles to prevent duplicate rows
if 'cycle_id' in df_cycles.columns:
    original_count = len(df_cycles)
    df_cycles = df_cycles.drop_duplicates(subset=['cycle_id'], keep='first')
    if len(df_cycles) < original_count:
        logger.warning(f"Removed {original_count - len(df_cycles)} duplicate cycle rows during export")
```

### Problem
1. **This is a band-aid, not a fix** - it removes duplicates at export time
2. **Root cause is unknown** - why are duplicates being added in first place?
3. **No tracking of source** - where do duplicates originate?
4. **Silent failures** - deduplication masks upstream issues

### Scenarios That Could Create Duplicates
1. Cycles added multiple times to data collector
2. Cycles with same `cycle_id` but different timing/metadata
3. Import/export cycles creating duplicates
4. Queue re-execution without clearing completed cycles

### Impact
- Users may not realize their data had duplicates
- Loss of metadata when 'keep=first' discards actual recorded cycle
- Cannot audit which cycle record was kept vs discarded

---

## Issue 4: Ambiguous End Time Values ⚠️ MEDIUM PRIORITY

### Location
`affilabs/domain/cycle.py:95` and Excel export chain

### Current State
```python
end_time_sensorgram: Optional[float] = Field(
    default=None,
    description="End time in sensorgram timeline (seconds)"
)
```

### Problem
- `end_time_sensorgram` is optional and defaults to `None`
- When exporting to Excel, None values may:
  - Appear as blank cells
  - Be converted to "#N/A"
  - Cause formula errors in dependent columns
  - Create ambiguity (planned? actual? missing?)

### In Excel Export Chain
1. `Cycle.to_export_dict()` returns `"end_time_sensorgram": None`
2. Passed to pandas DataFrame
3. Rendered as blank or NaN in Excel
4. Downstream formulas fail or behave unexpectedly

### Impact
- Users cannot calculate actual cycle duration
- Excel analysis formulas break
- Difficult to navigate and verify data

---

## Data Flow Analysis

### Current (Broken) Flow for Live Recording:

```
Queue Execution
    ↓
Cycle.start() method called? ❌ NO
    ↓
Cycle runs...
    ↓
Cycle.complete() called? ❌ NO
    ↓
recording_mgr.add_cycle() called? ❌ NO
    ↓
Data Collector has cycles? ❌ NO (empty)
    ↓
Export to Excel
    ↓
Cycles sheet is empty or incomplete ❌
```

### How Load/Reload Works (Functional):

```
Excel file with Cycles sheet
    ↓
Parse cycles from Excel
    ↓
Direct assignment: data_collector.cycles = cycles_data (line 3412)
    ↓
Are duplicates removed? ✓ YES (lines 3328-3337)
    ↓
Export to Excel
    ↓
Cycles sheet populated ✓
```

---

## Cleanup Opportunities - Data Ambiguities

### 1. Naming Inconsistency
- Field: `sensorgram_time` (cycle start in timeline)
- Column: `start_time_sensorgram` (exported name)
- Should be unified

### 2. Missing Flag for Actual vs Planned
- Both `duration_minutes` (actual) and `length_minutes` (planned) exported
- No indicator which one was actually used

### 3. Null/None Values Not Standardized
- Some cells blank, some "N/A", some 0.0
- Should be consistent representation

### 4. Channel Field Inconsistency
- `concentrations` dict with channel keys (e.g., `{'A': 100.0}`)
- Also `concentration_value` (single channel)
- Both exported, can conflict

---

## Recommendations (Priority Order)

### CRITICAL - Fix Cycle Recording During Execution
1. **Implement cycle tracking into recording manager during queue execution**
   - Call `cycle.start(cycle_num, total_cycles, sensorgram_time)` when cycle begins
   - Call `cycle.complete(end_time_sensorgram)` when cycle completes
   - Call `recording_mgr.add_cycle(cycle.to_export_dict())` to record cycle
   - Location: Queue execution loop (find where cycles are actually run)

### HIGH - Ensure Real Timing is Always Available
1. **Guarantee `end_time_sensorgram` is set for all cycles**
   - Add validation in `Cycle.to_export_dict()` to warn if timing is missing
   - Fallback: Use actual recorded time if available
   - Never silently use planned duration

2. **Add indicator of actual vs planned duration**
   - New field: `duration_calculated` (boolean)
   - Or: New field: `duration_source` (("planned"|"recorded"))

### MEDIUM - Eliminate Duplicate Creation
1. **Remove deduplication band-aid** once root cause is fixed
2. **Add cycle_id uniqueness validation**
   - Assert each cycle_id appears only once before export
   - Log warnings if duplicates detected

### MEDIUM - Clean Up Data Ambiguities
1. **Unify naming**: `sensorgram_time` → `start_time_sensorgram` throughout
2. **Standardize null handling**: 0.0 for defaults, None for missing
3. **Consolidate concentration fields**: Use only multi-channel dict, not single-channel fallback
4. **Rename export fields for clarity**:
   - `start_time_sensorgram` → `start_time_s`
   - `end_time_sensorgram` → `end_time_s`
   - `duration_minutes` → `actual_duration_min`
   - `length_minutes` → `planned_duration_min`

---

## Files to Investigate Further

1. **Queue Execution Loop** - Where cycles are actually run (not found yet)
   - Search for: "while executing", "queue runner", "cycle runner"
   - This is where cycle.start() and cycle.complete() should be called

2. **Recording Manager Integration** - How to hook into queue execution
   - `affilabs/core/recording_manager.py`
   - `affilabs/managers/queue_manager.py`
   - `affilabs/presenters/queue_presenter.py`

3. **Cycle Export** - How cycles flow to Excel
   - `affilabs/domain/cycle.py` (source)
   - `affilabs/services/data_collector.py` (accumulation)
   - `affilabs/services/excel_exporter.py` (output)

---

## Data Audit Checklist

- [ ] Verify cycle.start() is called with correct sensorgram_time
- [ ] Verify cycle.complete() is called with measured end_time_sensorgram
- [ ] Verify recording_mgr.add_cycle() is called with complete cycle data
- [ ] Verify no duplicate cycles by cycle_id before export
- [ ] Verify duration_minutes matches actual recorded time
- [ ] Verify all required fields are non-null before export
- [ ] Test with multi-cycle experiment to verify all cycles recorded
- [ ] Test with stopped/cancelled cycles to verify proper cleanup

---

## Status

```
✅ Code inspection complete
⚠️  4 critical/high issues identified
❌ Root cause: Cycle execution pipeline not integrated with recording manager
🔧 Awaiting implementation of fixes
```
