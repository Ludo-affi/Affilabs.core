# Sensorgram Display Investigation

## Issue Summary

**Reported Problems:**
1. Channel D (green) is visible in Spectroscopy tab but NOT in Sensorgram tab
2. Bottom graph (SOI) in Sensorgram tab displays nothing

## Investigation Results

### ✅ Visibility Initialization - WORKING CORRECTLY

**What we tested:**
- Added visibility initialization loop in `DataWindow.__init__()`
- Changed diagnostic logs from INFO → WARNING level (to be visible in console)
- Ran app and confirmed initialization

**Result:**
```
✅ Initialized channel a visibility: True
✅ Initialized channel b visibility: True
✅ Initialized channel c visibility: True
✅ Initialized channel d visibility: True
```

**Conclusion:** Visibility initialization IS working! All 4 channels are initialized with visibility=True. The issue must occur AFTER initialization, during live data updates.

---

### 🔍 Key Discovery: Spectroscopy vs Sensorgram Comparison

**Spectroscopy Tab (widgets/spectroscopy.py):**
- Does NOT have explicit visibility initialization loop
- Creates plots with `self.plots[ch] = self.plot.plot(...)`
- **Channel D works fine here!**

**Sensorgram Tab (widgets/datawindow.py):**
- HAS visibility initialization loop (we added it)
- Creates plots the same way
- **Channel D does NOT show here**

**Critical Insight:** Since Spectroscopy works WITHOUT visibility init, and Sensorgram has visibility init but channel D still doesn't show, the problem is NOT about visibility initialization. It's something else that happens during live data updates.

---

### 📊 Diagnostic Logging Added

We added logging at two critical points to capture what happens during live data updates:

#### 1. Top Graph Update (Full Sensorgram)
**Location:** `widgets/datawindow.py` line ~605

```python
# Log per-channel data counts and visibility before plotting
try:
    counts = {ch: len(y_data.get(ch, [])) for ch in CH_LIST}
    vis = {ch: self.full_segment_view.plots[ch].isVisible() for ch in CH_LIST}
    logger.warning(f"📊 Plot update: counts={counts}, visibility={vis}")
except Exception:
    logger.debug("Could not read plot visibility or data counts")
```

**What this will show:**
- How many data points each channel has during live updates
- Whether each plot is visible at the moment of rendering
- Whether channel D has empty arrays (count=0) or data (count>0)

**Expected outputs:**

**Scenario A - No data for channel D:**
```
📊 Plot update: counts={'a': 42, 'b': 42, 'c': 42, 'd': 0}, visibility={'a': True, 'b': True, 'c': True, 'd': True}
```
→ Channel D data is not being generated or filtered out

**Scenario B - Visibility changed to False:**
```
📊 Plot update: counts={'a': 42, 'b': 42, 'c': 42, 'd': 42}, visibility={'a': True, 'b': True, 'c': True, 'd': False}
```
→ Something is calling `setVisible(False)` after initialization

**Scenario C - Data exists but plot skipped:**
```
📊 Plot update: counts={'a': 42, 'b': 42, 'c': 42, 'd': 42}, visibility={'a': True, 'b': True, 'c': True, 'd': True}
```
→ Plot update logic is skipping channel D for another reason (maybe NaN data)

---

#### 2. Bottom Graph Update (SOI Segment)
**Location:** `widgets/datawindow.py` line ~695

```python
if self.current_segment.error is None:
    try:
        seg_counts = {ch: len(self.current_segment.seg_y.get(ch, [])) for ch in CH_LIST}
        soi_vis = {ch: self.SOI_view.plots[ch].isVisible() for ch in CH_LIST}
        logger.warning(f"📉 SOI update: seg_counts={seg_counts}, soi_visibility={soi_vis}")
    except Exception:
        logger.debug("Could not read SOI plot visibility or segment counts")
    self.SOI_view.update_display(self.current_segment)
```

**What this will show:**
- Whether segment data is being extracted at all
- How many segment points each channel has
- Whether SOI plots are visible

**Expected outputs:**

**Scenario A - No segment updates:**
```
(No "📉 SOI update" logs appear at all)
```
→ Segment extraction isn't triggering or is always hitting error condition

**Scenario B - Empty segment data:**
```
📉 SOI update: seg_counts={'a': 0, 'b': 0, 'c': 0, 'd': 0}, soi_visibility={'a': True, 'b': True, 'c': True, 'd': True}
```
→ Segment extraction is running but not finding any data to extract

**Scenario C - Data exists but not displayed:**
```
📉 SOI update: seg_counts={'a': 15, 'b': 15, 'c': 15, 'd': 15}, soi_visibility={'a': True, 'b': True, 'c': True, 'd': True}
```
→ Data is being extracted correctly, but `SegmentGraph.update_display()` isn't rendering it

---

## 🎯 Next Steps - CRITICAL

### Step 1: Run App to Live Mode (REQUIRED)

**Problem:** We interrupted the app during calibration both times, so we never captured the diagnostic logs during live data acquisition.

**Action Required:**
1. Start the app: `python run_app.py`
2. **Let calibration complete fully** (don't interrupt!)
3. Open the Sensorgram tab
4. **Wait for at least 5-10 data update cycles** (30-60 seconds of live data)
5. Look for the diagnostic logs in the terminal:
   - `📊 Plot update: counts={...}, visibility={...}`
   - `📉 SOI update: seg_counts={...}, soi_visibility={...}`
6. Take a screenshot or copy the log output

**These logs will tell us EXACTLY what's wrong:**
- If channel D has no data → Backend data generation issue
- If channel D visibility is False → Something is changing visibility after init
- If channel D has data and visibility=True but still doesn't show → Rendering issue

---

### Step 2: Based on Diagnostic Logs, Implement Fix

Once we see the diagnostic logs, we'll know which fix to apply:

#### Fix Path A: Channel D Has No Data (count=0)

**Where to look:**
- `utils/spr_data_acquisition.py` - Check if channel D is being filtered out
- Calibration completion - Verify all 4 channels complete calibration
- `_should_read_channel()` logic - Check if channel D is being excluded

**Possible fixes:**
- Enable channel D in data acquisition loop
- Fix calibration to include channel D
- Remove channel-specific filters that exclude D

---

#### Fix Path B: Visibility Becomes False After Init

**Where to look:**
- Search for `setVisible(False)` calls that might affect channel D
- Check if checkbox state changes during runtime
- Verify `display_channel_changed()` not being called with False

**Possible fixes:**
- Remove or fix code that sets visibility to False
- Fix checkbox state management
- Add defensive code to prevent visibility changes

---

#### Fix Path C: Data Exists But Plot Not Rendering

**Where to look:**
- Check if data contains all NaN values
- Review `SensorgramGraph.update()` logic for channel-specific filters
- Check if plot rendering has hardcoded channel exclusions

**Possible fixes:**
- Fix NaN handling in data processing
- Remove channel D exclusions from update logic
- Fix plot range or axis limits that might hide channel D

---

#### Fix Path D: SOI Bottom Graph Empty

**Where to look:**
- Check if segment updates are triggering at all (look for 📉 logs)
- Review `Segment.add_data()` extraction logic
- Check if current_segment is None or always has error

**Possible fixes:**
- Fix segment timing or trigger conditions
- Debug segment data extraction
- Fix error handling that prevents segment updates

---

## 📁 Modified Files

### 1. widgets/datawindow.py

**Lines 334-342: Visibility Initialization**
```python
# ✅ FIX: Initialize plot visibility to match checkbox state
for ch in CH_LIST:
    checkbox = getattr(self.ui, f"segment_{ch.upper()}")
    is_checked = checkbox.isChecked()
    self.full_segment_view.display_channel_changed(ch, is_checked)
    self.SOI_view.display_channel_changed(ch, is_checked)
    logger.warning(f"✅ Initialized channel {ch} visibility: {is_checked}")
```
Status: ✅ Working (confirmed via logs)

---

**Lines 603-611: Top Graph Diagnostic Logging**
```python
# Log per-channel data counts and visibility before plotting
try:
    counts = {ch: len(y_data.get(ch, [])) for ch in CH_LIST}
    vis = {ch: self.full_segment_view.plots[ch].isVisible() for ch in CH_LIST}
    logger.warning(f"📊 Plot update: counts={counts}, visibility={vis}")
except Exception:
    logger.debug("Could not read plot visibility or data counts")
```
Status: ⏸️ Added but not yet captured (app interrupted before live mode)

---

**Lines 693-701: Bottom Graph Diagnostic Logging**
```python
if self.current_segment.error is None:
    try:
        seg_counts = {ch: len(self.current_segment.seg_y.get(ch, [])) for ch in CH_LIST}
        soi_vis = {ch: self.SOI_view.plots[ch].isVisible() for ch in CH_LIST}
        logger.warning(f"📉 SOI update: seg_counts={seg_counts}, soi_visibility={soi_vis}")
    except Exception:
        logger.debug("Could not read SOI plot visibility or segment counts")
    self.SOI_view.update_display(self.current_segment)
```
Status: ⏸️ Added but not yet captured

---

### 2. widgets/graphs.py

**Line 3: Added numpy import**
```python
import numpy as np
```
For potential NaN detection in future debugging

---

## 🔬 Technical Details

### Data Flow Architecture

```
Backend: SPRDataAcquisition
  ↓ self.update_live_signal.emit(self.sensorgram_data())
  ↓
Frontend: DataWindow
  ↓ @Slot(dict) update_data(app_data)
  ↓ y_data = lambda_values (dict with keys: 'a', 'b', 'c', 'd')
  ↓ x_data = lambda_times (dict with keys: 'a', 'b', 'c', 'd')
  ↓ full_segment_view.update(y_data, x_data)  # Top graph
  ↓
SensorgramGraph.update()
  ↓ for ch in CH_LIST:
  ↓   if not self.plots[ch].isVisible(): continue  # Skip if not visible
  ↓   self.plots[ch].setData(y=y_data[ch], x=x_data[ch])  # Render
```

### Critical Question

**Why does channel D work in Spectroscopy but not Sensorgram?**

- Both use the same plot creation method
- Spectroscopy has NO visibility init → channel D works
- Sensorgram HAS visibility init (all True) → channel D doesn't work
- Therefore: Issue is NOT about visibility initialization
- **Must be something specific to sensorgram data flow or update logic**

---

## ⚠️ Important Notes

### Logging Configuration

**Console Log Level:** `WARNING` (from `settings/settings.py` line 277)
- Console only shows WARNING and above
- INFO and DEBUG logs only go to `logfile.txt`
- That's why we changed our diagnostic logs to `logger.warning()`

**To see INFO logs in console (optional):**
```python
# In settings/settings.py line 277:
CONSOLE_LOG_LEVEL = logging.INFO  # Change from logging.WARNING
```

### Why Diagnostic Logs Are Critical

The logs will answer these questions:
1. **Is channel D data being generated?** → counts={'d': ???}
2. **Is channel D visible at render time?** → visibility={'d': ???}
3. **Is segment data being extracted?** → seg_counts={'d': ???}
4. **Do all channels have same issue or just D?** → Compare all counts

Without these logs, we're just guessing. With them, we'll know the exact root cause.

---

## 📋 Quick Checklist

Before the next debugging session:

- [ ] Run app to completion (don't interrupt during calibration)
- [ ] Open Sensorgram tab
- [ ] Wait 30-60 seconds in live mode
- [ ] Capture terminal output with 📊 and 📉 logs
- [ ] Share the log output

Once we have the diagnostic logs, we'll know exactly what to fix!

---

## 🎓 What We Learned

1. **Visibility initialization IS working** - Confirmed via logs
2. **PyQtGraph plots default to visible** - No explicit setVisible() needed
3. **Issue occurs during live updates** - Not during initialization
4. **Spectroscopy and Sensorgram have different behavior** - Despite similar code
5. **Need runtime diagnostics** - Initialization diagnostics alone aren't enough

---

## 🚀 Expected Timeline

1. **Run app with diagnostics:** 2-3 minutes (including calibration)
2. **Analyze diagnostic output:** 1-2 minutes
3. **Implement fix:** 5-10 minutes (depends on root cause)
4. **Test fix:** 2-3 minutes
5. **Total:** ~15-20 minutes to resolution

The diagnostic logs are the KEY to solving this quickly!
