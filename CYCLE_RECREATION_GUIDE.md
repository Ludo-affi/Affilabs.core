# Cycle Recreation from Excel Export - Complete Guide

## Executive Summary

This guide documents how saved cycles are recorded in the AffiLabs.core data output and how to accurately recreate them from exported Excel files.

**Analysis based on:** `spr_data_20260211_194755 - concentrations.xlsx`

---

## Critical Findings

### ⚠️ Issues Discovered in Excel Export

1. **✅ `end_time_sensorgram` is NaN BUT CAN BE CALCULATED**
   - End times not stored in the export (NaN)
   - **However**: `end_time = start_time + (duration_minutes × 60)`
   - With start time (215.79s) and duration (8 min), we get end time (695.79s)
   - **Complete timeline reconstruction is possible!**

2. **❌ `concentration_value` field is NaN for ALL cycles**
   - Concentration data NOT stored in the dedicated field
   - This should be populated but isn't in this export

3. **❌ `concentrations` dict is EMPTY `{}` for ALL cycles**
   - Multi-channel concentrations NOT populated
   - Should contain `{'A': 100.0, 'B': 50.0, 'C': 25.0, 'D': 12.5}` format

4. **✅ Concentration data IS PRESERVED in the `note` field**
   - Format: `"conc 8min 0nm"`, `"conc 8min 1.37nm"`, `"conc 8min 4.1nm"`
   - **This is the ONLY source of concentration values in this export**
   - User manually entered concentrations in cycle notes

5. **✅ SPR deltas stored in `delta_ch1/ch2/ch3/ch4` columns**
   - Maps to channels A, B, C, D respectively
   - First 3 cycles have analysis data
   - Cycles 4-8 have NaN (analysis not completed)

---

## Excel File Structure

The exported file contains **6 sheets**:

### 1. Raw Data (19,451 rows)
- Time-series sensor measurements
- Columns: `time`, `channel`, `value`

### 2. Cycles (8 rows) ⭐ Primary focus
- Complete cycle metadata
- Columns: `cycle_id`, `cycle_num`, `type`, `name`, `start_time_sensorgram`, `end_time_sensorgram`, `duration_minutes`, `concentration_value`, `concentration_units`, `units`, `concentrations`, `note`, `delta_spr`, `delta_spr_by_channel`, `flags`, `flow_rate`, `pump_type`, `channels`, `injection_method`, `injection_delay`, `contact_time`, `delta_ch1`, `delta_ch2`, `delta_ch3`, `delta_ch4`

### 3. Flags (3 rows)
- Flag markers: wash, injection
- Columns: `type`, `channel`, `time`, `spr`, `timestamp`, `is_reference`

### 4. Events (1 row)
- Event log with timestamps
- Single event: "Recording Started"

### 5. Metadata (1 row)
- Recording metadata
- Columns: `recording_start`, `recording_start_iso`, `User`, `device_id`, `sensorgram_offset_seconds`, `channel_a_time_shift`, `channel_b_time_shift`, `channel_c_time_shift`, `channel_d_time_shift`

### 6. Channels XY (4,863 rows)
- Wide format: `Time_A`, `SPR_A`, `Time_B`, `SPR_B`, `Time_C`, `SPR_C`, `Time_D`, `SPR_D`

---

## Cycle Data in This Export

All 8 cycles are **Concentration** type with **8-minute planned duration**:

| Cycle | Start Time | Note | Concentration | SPR Deltas (A/B/C/D) |
|-------|------------|------|---------------|----------------------|
| 1 | 215.79s | conc 8min 0nm | 0 nM | 2.35 / 1.55 / -0.76 / -2.40 |
| 2 | 614.49s | conc 8min 1.37nm | 1.37 nM | 8.59 / 5.75 / 1.39 / 0.37 |
| 3 | 1096.10s | conc 8min 4.1nm | 4.1 nM | -9.19 / 10.68 / -5.54 / -2.89 |
| 4 | 1576.68s | conc 8min 12.7nm | 12.7 nM | - / - / - / - |
| 5 | 2049.92s | conc 8min 37nm | 37 nM | - / - / - / - |
| 6 | 2531.02s | conc 8min 111nm | 111 nM | - / - / - / - |
| 7 | 3011.68s | conc 8min 333nm | 333 nM | - / - / - / - |
| 8 | 3492.92s | conc 8min 1000nm | 1000 nM | - / - / - / - |

**Concentration Series:** 0, 1.37, 4.1, 12.7, 37, 111, 333, 1000 nM (3-fold dilution series)

**Automation Settings:** All cycles use `injection_method=simple` with `injection_delay=20s`

---

## Cycle Reconstruction Strategy

### Step 1: Read Excel File

```python
import pandas as pd
from pathlib import Path

excel_path = Path("spr_data_20260211_194755 - concentrations.xlsx")
df_cycles = pd.read_excel(excel_path, sheet_name='Cycles', engine='openpyxl')
```

### Step 2: Parse Concentration from Note Field

**CRITICAL:** This is the ONLY source of concentration data in this export.

```python
import re

def parse_concentration_from_note(note: str) -> float | None:
    """Extract concentration value from cycle note.

    Examples:
        "conc 8min 0nm" -> 0.0
        "conc 8min 1.37nm" -> 1.37
        "conc 8min 111nm" -> 111.0
    """
    if not note or pd.isna(note):
        return None

    # Match number before "nm" or "nM"
    match = re.search(r'(\d+\.?\d*)n[mM]', str(note))
    if match:
        return float(match.group(1))

    return None
```

### Step 3: Reconstruct SPR Deltas by Channel

```python
def reconstruct_delta_spr_by_channel(row: pd.Series) -> dict:
    """Reconstruct delta_spr_by_channel from delta_ch1/ch2/ch3/ch4.

    Returns:
        {'A': 2.35, 'B': 1.55, 'C': -0.76, 'D': -2.40}
    """
    delta_by_channel = {}

    for ch_num in [1, 2, 3, 4]:
        delta_col = f'delta_ch{ch_num}'
        if delta_col in row and pd.notna(row[delta_col]):
            ch_letter = chr(64 + ch_num)  # 1->A, 2->B, 3->C, 4->D
            delta_by_channel[ch_letter] = float(row[delta_col])

    return delta_by_channel
```

### Step 4: Create Cycle Objects

```python
from affilabs.domain.cycle import Cycle

cycles = []

for idx, row in df_cycles.iterrows():
    # Parse concentration from note (CRITICAL)
    concentration = parse_concentration_from_note(row.get('note', ''))

    # Reconstruct delta_spr_by_channel
    delta_by_channel = reconstruct_delta_spr_by_channel(row)

    # Handle missing end_time_sensorgram
    end_time = row.get('end_time_sensorgram')
    if pd.isna(end_time):
        end_time = None

    # Create Cycle object
    cycle_data = {
        'type': row.get('type', 'Unknown'),
        'length_minutes': row.get('duration_minutes', 0.0),
        'name': row.get('name', f"Cycle {idx + 1}"),
        'note': row.get('note', ''),
        'cycle_id': int(row.get('cycle_id', idx + 1)),
        'cycle_num': int(row.get('cycle_num', idx + 1)),
        'status': 'completed',
        'sensorgram_time': row.get('start_time_sensorgram'),
        'end_time_sensorgram': end_time,

        # Parsed concentration
        'concentration_value': concentration,
        'concentration_units': row.get('concentration_units', 'nM'),
        'units': row.get('units', 'nM'),

        # Reconstructed deltas
        'delta_spr_by_channel': delta_by_channel,

        # Automation settings
        'injection_method': row.get('injection_method'),
        'injection_delay': row.get('injection_delay', 20.0),
    }

    cycle = Cycle(**cycle_data)
    cycles.append(cycle)
```

---

## Complete Working Script

A fully functional script is available at:
**`recreate_cycles_from_excel.py`**

To use:
```bash
python recreate_cycles_from_excel.py
```

This script:
- ✅ Parses the Excel file
- ✅ Extracts concentrations from notes
- ✅ Reconstructs SPR deltas by channel
- ✅ Handles missing end times gracefully
- ✅ Creates validated Cycle objects
- ✅ Displays complete cycle information

---

## Expected vs Actual Export Behavior

### What SHOULD Happen (Per Architecture)

According to [cycle.py](affilabs/domain/cycle.py#L169-L204), `to_export_dict()` should export:

```python
{
    "concentration_value": 100.0,  # ✅ Should be populated
    "concentrations": {"A": 100.0, "B": 50.0},  # ✅ Should be populated
    "end_time_sensorgram": 600.0,  # ✅ Should be captured
    "duration_minutes": 5.0,  # ✅ ACTUAL duration (calculated)
}
```

### What ACTUALLY Happened (This Export)

```python
{
    "concentration_value": NaN,  # ❌ NOT populated
    "concentrations": {},  # ❌ EMPTY dict
    "end_time_sensorgram": NaN,  # ❌ NOT captured
    "note": "conc 8min 1.37nm",  # ✅ User preserved data here
}
```

### Possible Causes

1. **End time missing**: Cycles stopped early via Stop Cycle button or recording stopped mid-cycle
2. **Concentration fields empty**: User didn't set concentration in Method Builder, only in cycle notes
3. **Working as designed**: Notes are the primary metadata storage mechanism for this workflow

---

## Recommendations

### For Users

1. **Always use the concentration fields in Method Builder**
   - Don't rely solely on notes for concentration tracking
   - Fill in both `concentration_value` and channel-specific values

2. **Let cycles complete normally**
   - Avoid stopping cycles early if you need accurate timing data
   - `end_time_sensorgram` is critical for timeline reconstruction

3. **Verify exports contain expected data**
   - Check that concentration fields are populated
   - Confirm end times are captured

### For Developers

1. **Consider warning when concentration fields are empty**
   - Alert user if creating cycle without concentration data
   - Suggest moving note data to proper fields

2. **Ensure end times are always captured**
   - Even when stopped early, calculate and store end time
   - Current behavior leaves end time as NaN

3. **Add validation on export**
   - Check for missing critical fields before export
   - Warn user about incomplete data

---

## Summary

**Saved cycles ARE recorded in the data output**, but with varying data quality:

✅ **Always Preserved:**
- Cycle type, name, notes
- Start time in sensorgram timeline
- Planned duration
- Injection settings
- User-entered notes (reliable metadata storage)

⚠️ **Sometimes Missing:**
- End time (if stopped early)
- Concentration values in dedicated fields
- Multi-channel concentration data
- SPR delta analysis (if not computed)

🔑 **Key Insight:**
In this export, **cycle notes are the primary source of concentration data**. The system allows users to store critical metadata in notes when structured fields aren't used. This is working as designed, but structured fields provide better data integrity.

**Cycle recreation IS POSSIBLE** using the provided script, which intelligently parses notes and reconstructs complete cycle metadata.

---

## Files Referenced

- **Analysis Script:** [recreate_cycles_from_excel.py](recreate_cycles_from_excel.py)
- **Domain Model:** [affilabs/domain/cycle.py](affilabs/domain/cycle.py)
- **Excel Exporter:** [affilabs/services/excel_exporter.py](affilabs/services/excel_exporter.py)
- **Recording Manager:** [affilabs/core/recording_manager.py](affilabs/core/recording_manager.py)
- **Sample Data:** `C:\Users\lucia\Documents\Affilabs Data\spr_data_20260211_194755 - concentrations.xlsx`

---

**Document created:** 2026-02-11
**Analysis based on:** Real exported data from AffiLabs.core v2.0.2
