# Data Flow: Live Recording → Excel → Edits Tab

## ✅ VERIFIED: The data IS properly linked!

## 1. Data Recording (Live Tab)

### When a cycle completes:
**File:** `main.py` → `_on_cycle_completed()` (line 1700)

```python
cycle_export_data = self._current_cycle.to_export_dict()
self.recording_mgr.add_cycle(cycle_export_data)
```

### Cycle Export Format:
**File:** `affilabs/domain/cycle.py` → `to_export_dict()` (line 106)

```python
{
    'cycle_num': 1,
    'type': 'Baseline',
    'name': 'Baseline 1',
    'start_time_sensorgram': 30.5,      # ✅ KEY FIELD for Edits
    'end_time_sensorgram': 330.5,        # ✅ KEY FIELD for Edits
    'duration_minutes': 5.0,             # ✅ KEY FIELD for Edits
    'concentration_value': 100.0,
    'concentration_units': 'nM',
    'note': 'Test cycle'
}
```

### Raw Data Points:
**File:** `affilabs/services/data_collector.py`

Each data point contains:
```python
{
    'elapsed': 45.2,              # ✅ Used to filter cycle time range
    'time': 45.2,                 # Alias for elapsed
    'timestamp': '2025-12-23T...',
    'wavelength_a': 650.1234,     # ✅ Plotted on graph
    'wavelength_b': 655.5678,     # ✅ Plotted on graph
    'wavelength_c': 660.9012,     # ✅ Plotted on graph
    'wavelength_d': 665.3456      # ✅ Plotted on graph
}
```

---

## 2. Excel Export

### When recording stops:
**File:** `affilabs/services/excel_exporter.py` → `export_to_excel()` (line 40)

Creates Excel file with **6 sheets**:
1. **Raw Data** - All wavelength_a/b/c/d data points with elapsed time
2. **Cycles** - Cycle metadata with start_time_sensorgram, end_time_sensorgram
3. **Flags** - User-placed markers
4. **Events** - Recording events
5. **Analysis** - Analysis results
6. **Metadata** - Session info

---

## 3. Excel Import (Edits Tab)

### When user clicks "Load Data":
**File:** `affilabs/affilabs_core_ui.py` → `_load_previous_data()` (line 6377)

```python
# Read Excel
loaded_data = self.app.recording_mgr.load_from_excel(file_path)

# ✅ Store raw data for graph display
self.app.recording_mgr.data_collector.raw_data_rows = loaded_data.get('raw_data', [])

# ✅ Populate cycle table
self._populate_cycle_table_from_loaded_data(loaded_data.get('cycles', []))
```

**File:** `affilabs/affilabs_core_ui.py` → `_populate_cycle_table_from_loaded_data()` (line 6498)

```python
# Display cycles in table
for row_idx, cycle in enumerate(cycles_data):
    # ... populate table columns ...

# ✅ CRITICAL: Store cycles for selection
self._loaded_cycles_data = cycles_data
```

---

## 4. Cycle Selection & Graph Display

### When user selects a cycle in table:
**File:** `affilabs/affilabs_core_ui.py` → `_on_cycle_selected_in_table()` (line 6571)

```python
# Get cycle time range
cycle = self._loaded_cycles_data[row]
start_time = cycle.get('start_time_sensorgram')  # ✅ From Excel
end_time = cycle.get('end_time_sensorgram')      # ✅ From Excel

# Get raw data
raw_data = self.app.recording_mgr.data_collector.raw_data_rows  # ✅ From Excel

# Filter data for cycle time range
for row_data in raw_data:
    time = row_data.get('elapsed')
    if start_time <= time <= end_time:
        # Collect wavelength_a, wavelength_b, wavelength_c, wavelength_d
        all_cycle_data[ch]['time'].append(time)
        all_cycle_data[ch]['wavelength'].append(wavelength)

# Plot on graph
for i, ch in enumerate(['a', 'b', 'c', 'd']):
    self.edits_graph_curves[i].setData(time_data, wavelength_data)
```

---

## Field Mapping: Live → Excel → Edits

| Live Recording | Excel Column | Edits Tab Usage |
|----------------|--------------|-----------------|
| `sensorgram_time` | `start_time_sensorgram` | Filter start for raw data |
| `end_time_sensorgram` | `end_time_sensorgram` | Filter end for raw data |
| `length_minutes` | `duration_minutes` | Fallback if end_time missing |
| `elapsed` | `elapsed` | X-axis (time) |
| `wavelength_a/b/c/d` | `wavelength_a/b/c/d` | Y-axis (channels A/B/C/D) |
| `type` | `type` | Cycle type display |
| `concentration_value` | `concentration_value` | Table display |
| `note` | `note` | Table display |

---

## ✅ Verification Checklist

### For data to work in Edits tab, Excel must have:

**Cycles sheet MUST contain:**
- ✅ `start_time_sensorgram` (or `sensorgram_time` as alias)
- ✅ `end_time_sensorgram` (or can be calculated from duration_minutes)
- ✅ `duration_minutes` (fallback if end_time missing)

**Raw Data sheet MUST contain:**
- ✅ `elapsed` (or `time` as alias)
- ✅ `wavelength_a`
- ✅ `wavelength_b`
- ✅ `wavelength_c`
- ✅ `wavelength_d`

**Current test data has all required fields! ✅**

---

## Known Issues & Fixes

### Issue 1: NaN handling ✅ FIXED
- **Problem**: pandas converts missing values to NaN (not None)
- **Fix**: Added `math.isnan()` check with try-except
- **Location**: `_on_cycle_selected_in_table()` line 6623

### Issue 2: Raw data not loaded ✅ FIXED
- **Problem**: Excel data read but not stored in data_collector
- **Fix**: Added `data_collector.raw_data_rows = loaded_data['raw_data']`
- **Location**: `_load_previous_data()` line 6473

### Issue 3: Graph not plotting ✅ FIXED
- **Problem**: Data collected but never plotted
- **Fix**: Added `self.edits_graph_curves[i].setData()` calls
- **Location**: `_on_cycle_selected_in_table()` line 6682

### Issue 4: Segment creation expects Cycle objects ✅ FIXED
- **Problem**: Code called `Cycle.from_dict()` but data_collector has dicts
- **Fix**: Changed to work directly with dictionaries
- **Location**: `_create_segment_from_selection()` line 6803

---

## Summary

**YES, the data is fully linked!**

1. ✅ Live recording saves cycles with `start_time_sensorgram` and `end_time_sensorgram`
2. ✅ Excel export preserves all required fields
3. ✅ Excel import loads both cycles and raw data
4. ✅ Edits tab can filter raw data by cycle time range
5. ✅ Graph displays the filtered data for selected cycles

**The system is designed correctly - any issues are just bugs in the implementation, not architectural problems.**
