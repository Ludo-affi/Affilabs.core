# Manual Injection Data Flow Map
**Complete workflow from Method Builder → Live Execution → Edits Tab**

---

## Overview

Manual injection is the most complex workflow in ezControl because it involves:
1. **User interaction** (placing flags, confirming injection)
2. **Real-time detection** (automatic injection peak finding)
3. **Timer coordination** (contact time countdown)
4. **Automatic wash flag placement** (NEW: no manual intervention)
5. **Comprehensive metadata capture** (all details saved for post-processing)

When data is well-organized during manual injection, edits become easy because:
- All injection times are captured per channel
- Detection confidence scores are saved
- Contact times are recorded
- Wash flags are placed automatically at the right time
- Cycle metadata includes all method settings

---

## 1. Method Builder: Cycle Definition

### Location
`affilabs/widgets/method_builder_dialog.py` (2289 lines)

### Components

#### A. Overview Tab (Main Table)
**Columns:** `Type | Duration | Notes`
- Shows high-level cycle structure
- User types cycle lines in note field
- Example: `Concentration 5min [A:100nM] contact 180s`

#### B. Details Tab (NEW - Injection-Specific Info)
**Columns:** `# | Channels | Concentration | Contact Time`
- `#`: Sequential number (30px fixed width)
- `Channels`: Which channels get injection, e.g., "A, B" (70px fixed)
- `Concentration`: Parse from note, e.g., "100 nM" (stretch to fill)
- `Contact Time`: How long sample stays, e.g., "180s" (resize to contents)

**Purpose:** Quick view of injection schedule without reading full notes

#### C. Settings Panel (Collapsible, Below Table)
**Toggle:** ⚙ Cog button below table
**Contents:**
- **Mode:** Manual | Semi-Automated | Automated
- **Device Type:** Manual (syringe) | Pump (AffiPump)
- **Detection Priority:** Baseline | Priority | Elevated | Off

**Sensitivity Factors:**
- Manual mode: 2.0 (conservative, avoids syringe handling noise)
- Pump mode: 0.75 (tight detection for clean pump injections)
- Priority mode: 1.0 (medium sensitivity)
- Off: 999 (disables auto-detection)

**Detection Algorithm:**
```python
threshold = 2.5 × std(baseline) × sensitivity_factor
baseline_points = 5  # Last 5 points
```

### Cycle Data Structure (`affilabs/domain/cycle.py`)

**Key Fields for Manual Injection:**
```python
class Cycle(BaseModel):
    type: str  # "Binding", "Kinetic", "Immobilization", etc.
    length_minutes: float
    note: str  # Full user-typed line
    
    # Injection settings
    injection_method: Optional[str]  # "simple" or "partial"
    injection_delay: float = 20.0  # Always 20s into cycle
    contact_time: Optional[float]  # Seconds, e.g., 180.0
    
    # Manual injection mode
    manual_injection_mode: Optional[str]  # "manual" or "automated"
    planned_concentrations: List[str]  # ["100 nM", "50 nM", "10 nM"]
    injection_count: int = 0  # How many injections completed so far
    
    # Detection settings
    method_mode: Optional[str]  # "manual", "semi-automated", "automated"
    detection_priority: str = "auto"  # or "priority", "off"
    detection_sensitivity: Optional[float]  # Multiplier for threshold
    target_channels: Optional[str]  # "ABCD" or "AC", etc.
    
    # Runtime metadata (populated during execution)
    injection_time_by_channel: Dict[str, float]  # {"a": 123.5, "b": 124.1}
    injection_confidence_by_channel: Dict[str, float]  # {"a": 0.95, "b": 0.87}
    injection_mislabel_flags: List[str]  # Channels with potential mislabeling
    
    # Flags (injection, wash)
    flags: List[dict]  # [{"type": "injection", "time": 123.5, "channel": "a"}]
```

### Example Cycle Creation

**User Types:**
```
Binding 5min [A:100nM, B:50nM] contact 180s
```

**Parsed Result:**
```python
Cycle(
    type="Binding",
    length_minutes=5.0,
    note="Binding 5min [A:100nM, B:50nM] contact 180s",
    
    # Auto-set by parser
    injection_method="simple",
    injection_delay=20.0,
    contact_time=180.0,
    
    # From method builder settings
    method_mode="manual",
    detection_priority="auto",
    target_channels="AB",
    
    # Multi-injection schedule
    planned_concentrations=["100 nM", "50 nM"],
    injection_count=0,
    
    # Concentrations dict for reference
    concentrations={"A": 100.0, "B": 50.0},
    units="nM",
    
    # Runtime fields (empty initially)
    injection_time_by_channel={},
    injection_confidence_by_channel={},
    flags=[],
)
```

---

## 2. Live Execution: Data Collection

### Injection Coordinator
`affilabs/coordinators/injection_coordinator.py` (771 lines)

**Entry Point:** `execute_injection(cycle, flow_rate, parent_widget)`

#### Workflow Steps

**1. Show Concentration Schedule (if multi-injection)**
```python
if cycle.planned_concentrations and cycle.injection_count == 0:
    dialog = ConcentrationScheduleDialog(cycle, parent_widget)
    if dialog.exec() != Accepted:
        return False  # User cancelled
```

**Dialog Contents:**
- Instruction card (6 steps)
- Planned injections list
- Contact time for each
- "Ready to Begin" button

**2. Wait for User Flag Placement**
User presses **Ctrl+Click** on live sensorgram → places injection flag

**3. Manual Injection Dialog Appears**
`affilabs/dialogs/manual_injection_dialog.py` (793 lines)

**Dialog Shows:**
- 60-second countdown timer
- Channel LED indicators (🔴 → 🟢 when detected)
- "Injection Complete" button
- Real-time sensitivity factor display

**Detection Logic:**
```python
# Running in background (200ms polling)
def _check_for_injection():
    for channel in active_channels:
        baseline = last_5_points(channel)
        threshold = 2.5 × std(baseline) × sensitivity_factor
        
        if current_value > baseline_mean + threshold:
            # Injection detected!
            mark_time = current_time
            confidence = (peak_height / threshold)
            
            # Update dialog LED
            set_channel_led(channel, green=True)
            
            # Save to cycle metadata
            cycle.injection_time_by_channel[channel] = mark_time
            cycle.injection_confidence_by_channel[channel] = confidence
```

**Auto-Close Triggers:**
- All channels detected ✅
- User clicks "Injection Complete" ✅
- 60-second timeout expires ⏱
- Grace period after all detections ✅

**4. Detection Results Saved**
```python
# Metadata captured automatically
cycle.injection_time_by_channel = {
    "a": 123.45,  # Detected at 123.45s
    "b": 124.12,  # Detected at 124.12s
}

cycle.injection_confidence_by_channel = {
    "a": 0.95,  # 95% confidence (strong signal)
    "b": 0.87,  # 87% confidence (good signal)
}

cycle.injection_count += 1  # Increment injection counter
```

**5. Contact Timer Starts**
`main.py` → `_start_contact_countdown(contact_duration)`

**Timer Infrastructure:**
```python
def _start_contact_countdown(contact_duration: float):
    # Build timer label
    label = "Contact Time — 100 nM (1/2)"  # If multi-injection
    
    # Start countdown
    self._manual_timer.start(contact_duration * 1000)  # Convert to ms
    self._manual_timer_label = label
    self._manual_timer_next_action = "Perform wash"
    
    # Show unified bar in CONTACT state
    unified_bar.set_contact_state(label, contact_duration)
    
    # Create orange deadline marker on graph
    wash_time = injection_time + contact_duration
    create_deadline_marker(wash_time, color="orange")
```

**6. Timer Expiration → Automatic Wash Flags**
`affilabs/affilabs_core_ui.py` → `_on_manual_timer_tick()`

**When Timer Hits Zero:**
```python
def _on_manual_timer_tick(self, seconds_remaining):
    if seconds_remaining <= 0:
        # Timer completed!
        self._manual_timer.stop()
        
        # Show WASH NOW alert
        self.timer_button.show_wash_alert()  # Yellow state
        
        # **NEW: Place automatic wash flags**
        self._place_automatic_wash_flags()
        
        # Start alarm loop
        if self._manual_timer_sound:
            self._start_alarm_loop()
```

**Automatic Wash Flag Placement:**
```python
def _place_automatic_wash_flags(self):
    # Get current sensorgram time (when timer expired)
    wash_time = timeline.stop_cursor.value()
    
    # Find all channels with injection flags
    injection_flags = {
        f['channel']: f 
        for f in coordinator._flag_markers 
        if f['type'] == 'injection'
    }
    
    # Place wash flag on each channel
    for channel, inj_flag in injection_flags.items():
        # Get SPR value at wash time
        spr_val = get_spr_at_time(channel, wash_time)
        
        # Create wash flag marker
        coordinator._add_flag_marker(channel, wash_time, spr_val, 'wash')
        
        logger.info(f"✓ Automatic wash flag placed on channel {channel.upper()}")
```

**Result:** Wash flags appear automatically, user just performs the wash action

### Flag Data Structure
```python
# Injection flag (placed by user Ctrl+Click)
{
    "type": "injection",
    "channel": "a",
    "time": 123.45,  # Sensorgram time
    "spr": 1250.3,   # SPR value at flag position
}

# Wash flag (placed automatically when contact timer expires)
{
    "type": "wash",
    "channel": "a",
    "time": 303.45,  # injection_time + contact_time
    "spr": 1180.7,   # SPR value at wash time
}
```

---

## 3. Cycle Completion: Export to Edits

### When Cycle Ends
`main.py` → `_on_cycle_complete()`

**Data Export:**
```python
def _on_cycle_complete(self):
    # Convert cycle to export dictionary
    cycle_export_data = self._current_cycle.to_export_dict(clock=self.clock)
    
    # Add to Edits table (live view during run)
    if hasattr(self.main_window, 'edits_tab'):
        self.main_window.edits_tab.add_cycle(cycle_export_data)
        logger.info("✓ Cycle saved to Edits table")
    
    # Export to recording manager (if recording)
    if self.recording_manager and self.recording_manager.is_recording():
        self.recording_manager.add_cycle(cycle_export_data)
```

### Export Dictionary Structure
```python
cycle.to_export_dict() returns:
{
    # Basic info
    "cycle_id": "abc123",
    "cycle_num": 1,
    "type": "Binding",
    "name": "100 nM",
    "note": "Binding 5min [A:100nM] contact 180s",
    
    # Timing (converted to sensorgram time)
    "start_time_sensorgram": 0.0,
    "stop_time_sensorgram": 300.0,
    "duration_minutes": 5.0,
    
    # Injection metadata
    "injection_method": "simple",
    "injection_delay": 20.0,
    "contact_time": 180.0,
    "manual_injection_mode": "manual",
    
    # Multi-injection schedule
    "planned_concentrations": ["100 nM", "50 nM"],
    "injection_count": 1,
    
    # **CRITICAL: Per-channel detection results**
    "injection_time_by_channel": {
        "a": 123.45,
        "b": 124.12
    },
    "injection_confidence_by_channel": {
        "a": 0.95,
        "b": 0.87
    },
    
    # Flags (injection + automatic wash)
    "flags": [
        {"type": "injection", "channel": "a", "time": 123.45, "spr": 1250.3},
        {"type": "injection", "channel": "b", "time": 124.12, "spr": 1248.9},
        {"type": "wash", "channel": "a", "time": 303.45, "spr": 1180.7},
        {"type": "wash", "channel": "b", "time": 304.12, "spr": 1182.1},
    ],
    
    # Method settings
    "method_mode": "manual",
    "detection_priority": "auto",
    "detection_sensitivity": 2.0,
    "target_channels": "AB",
    
    # Concentrations
    "concentrations": {"A": 100.0, "B": 50.0},
    "units": "nM",
    
    # Flow settings
    "flow_rate": 50.0,
    "pump_type": "P4SPR",
    "channels": "AB",
}
```

---

## 4. Edits Tab: Post-Processing

### Location
`affilabs/tabs/edits_tab.py` (5034 lines)

### Load Excel File

**User Action:** Click "📂 Load Excel" button

**File Structure Expected:**
- Sheet 1: **Raw Data** (time, channel_a, channel_b, channel_c, channel_d)
- Sheet 2: **Cycles** (all cycle metadata from `to_export_dict()`)
- Sheet 3: **Flags** (injection and wash flags)
- Sheet 4: **Metadata** (experiment info)

**Loading Process:**
```python
def _load_data_from_excel(self, file_path):
    # Read Excel sheets
    raw_df = pd.read_excel(file_path, sheet_name="Raw Data")
    cycles_df = pd.read_excel(file_path, sheet_name="Cycles")
    flags_df = pd.read_excel(file_path, sheet_name="Flags")
    metadata_df = pd.read_excel(file_path, sheet_name="Metadata")
    
    # Store metadata
    self._loaded_metadata = {
        "file_path": file_path,
        "experiment_name": metadata_df.get("experiment_name"),
        "user": metadata_df.get("user"),
        "device": metadata_df.get("device"),
    }
    
    # Populate cycle table
    for idx, row in cycles_df.iterrows():
        self.add_cycle(row.to_dict())
    
    # Draw cycle markers on timeline
    self.add_cycle_markers_to_timeline(cycles_df)
    
    # Load and reconstruct flags
    for idx, flag in flags_df.iterrows():
        self._edits_flags.append({
            "type": flag["type"],
            "channel": flag["channel"],
            "time": flag["time"],
            "spr": flag["spr"],
        })
```

### Cycle Table Display

**Columns:**
```
Type | Name | Start (s) | Stop (s) | Duration | Channels | Concentration | Contact | Status
```

**Example Row:**
```
Concentration | 100 nM | 0.0 | 300.0 | 5.0 min | A, B | 100 nM | 180s | Complete
```

**Color Coding:** Based on `CycleTypeStyle` (same as live view)
- Concentration: Blue
- Regeneration: Orange
- Baseline: Green
- Wash: Purple

### Cycle Details Panel (Master-Detail)

**Triggered by:** Click row in cycle table

**Panel Sections:**

#### A. Metadata Display
```
Cycle Type:     Binding
Name:           100 nM
Note:           Binding 5min [A:100nM] contact 180s
Status:         Complete
```

#### B. Timing Controls
```
Start Time:     [  0.00  ] s
Stop Time:      [300.00  ] s
Duration:       5.0 minutes
```
**Note:** Editable! User can adjust boundaries

#### C. Injection Details
```
Method:         Simple Injection
Delay:          20.0 s
Contact Time:   180 s
Mode:           Manual

Detected Injections:
  Channel A: 123.45s (confidence: 95%)
  Channel B: 124.12s (confidence: 87%)
```

#### D. Multi-Injection Schedule (if applicable)
```
Planned: ["100 nM", "50 nM"]
Completed: 1 of 2 injections
```

#### E. Flags List
```
Injection Flags:
  ▲ Ch A: 123.45s
  ▲ Ch B: 124.12s

Wash Flags (automatic):
  ■ Ch A: 303.45s
  ■ Ch B: 304.12s
```

#### F. Alignment Controls (Per-Channel Shift)
```
Channel A: [  0.00  ] s offset
Channel B: [ -0.67  ] s offset  (align to A)
Channel C: [  0.00  ] s offset
Channel D: [  0.00  ] s offset
```

### Editing Operations

#### 1. Adjust Cycle Boundaries
```python
def _update_cycle_boundaries(self):
    # User changed start/stop spinboxes
    new_start = self.start_time_spin.value()
    new_stop = self.stop_time_spin.value()
    
    # Update cycle data in table
    selected_row = self.cycle_data_table.currentRow()
    self.cycle_data_table.setItem(selected_row, 2, QTableWidgetItem(f"{new_start:.2f}"))
    self.cycle_data_table.setItem(selected_row, 3, QTableWidgetItem(f"{new_stop:.2f}"))
    
    # Update graph cursors
    self.edits_timeline_cursors['left'].setValue(new_start)
    self.edits_timeline_cursors['right'].setValue(new_stop)
    
    # Refresh active selection view
    self._update_selection_view()
```

#### 2. Align Channels
```python
def _apply_channel_alignment(self):
    # User adjusted channel offset spinboxes
    selected_row = self.cycle_data_table.currentRow()
    
    # Store alignment per cycle
    self._cycle_alignment[selected_row] = {
        "a": self.align_a_spin.value(),
        "b": self.align_b_spin.value(),
        "c": self.align_c_spin.value(),
        "d": self.align_d_spin.value(),
    }
    
    # Redraw with alignment
    self._update_selection_view()
```

#### 3. Manual Injection Correction
```python
def _manually_place_injection_flag(self, channel, time):
    # User dragged injection marker to correct position
    selected_row = self.cycle_data_table.currentRow()
    
    # Update injection metadata
    self._injection_points[selected_row] = {
        "time": time,
        "auto": False,  # Manual override
        "confidence": 1.0,  # User confirmed
    }
    
    # Update flag in edits flags
    for flag in self._edits_flags:
        if flag["type"] == "injection" and flag["channel"] == channel:
            flag["time"] = time
            break
```

#### 4. Add Custom Flags
```python
def _add_custom_flag(self, event):
    # User Ctrl+Clicked on edits graph
    time_val = event.xdata
    
    # Show flag type menu (Injection only, wash is automatic)
    # Note: Wash and Spike were deprecated - only Injection remains
    self._add_flag_marker("a", time_val, spr_val, "injection")
```

### Validation & QC

**Auto-Detection Review:**
- Highlight low-confidence injections (<70%) in yellow
- Show warning if injection times differ >5s between channels
- Flag missing wash flags (shouldn't happen with automatic system)

**Baseline Quality:**
- Check if baseline stable before injection
- Verify post-wash return to baseline
- Calculate drift rate

**Contact Time Verification:**
```python
def _verify_contact_time(self):
    # For each cycle with injection and wash flags
    for channel in ["a", "b", "c", "d"]:
        inj_flag = find_flag(channel, "injection")
        wash_flag = find_flag(channel, "wash")
        
        if inj_flag and wash_flag:
            actual_contact = wash_flag["time"] - inj_flag["time"]
            expected_contact = cycle["contact_time"]
            
            delta = abs(actual_contact - expected_contact)
            
            if delta > 5.0:  # More than 5s off
                logger.warning(f"Contact time mismatch: {delta:.1f}s")
```

---

## 5. Export from Edits

### Export Format Options

**1. Excel (.xlsx) - PRIMARY**
- Raw Data sheet (time-series)
- Cycles sheet (all metadata)
- Flags sheet (injection + wash)
- Analysis sheet (computed metrics)
- Metadata sheet (experiment info)

**2. CSV (cycle table only)**
- Flattened cycle metadata
- Good for quick imports to R/Python

**3. AnIML (standardized XML)**
- For regulatory compliance
- Full audit trail
- FAIR data principles

### What Gets Saved

**From Manual Injection Workflow:**
✅ Original cycle definition (type, duration, note)  
✅ Method mode and detection settings  
✅ Planned concentrations list  
✅ Per-channel injection times  
✅ Per-channel detection confidence scores  
✅ Injection flags (user-placed)  
✅ Wash flags (automatic)  
✅ Contact time (planned vs actual)  
✅ Alignment offsets (if user adjusted)  
✅ Manual corrections (if any)  
✅ QC warnings (low confidence, misalignment)

**Export Preserves:**
- All timing in sensorgram time (continuous)
- All original metadata
- User edits and adjustments
- Flag positions
- Comments/notes

---

## 6. Key Advantages of Well-Organized Data

### For Manual Injection

**During Live Run:**
1. **No missed data**
   - All injection times captured automatically
   - Confidence scores saved for QC
   - Wash flags placed exactly when timer expires
   
2. **No manual bookkeeping**
   - User doesn't need to note times
   - Multi-injection schedule tracked automatically
   - Contact timer ensures consistent timing

3. **Immediate feedback**
   - LED indicators show detection in real-time
   - Low confidence warnings appear immediately
   - Timer shows countdown with visual alerts

**In Edits Tab:**
1. **Complete reconstruction**
   - Load Excel → all flags, timings, metadata restored
   - Click cycle row → see all injection details
   - No need to remember what happened

2. **Easy corrections**
   - Drag injection marker to correct position
   - Adjust cycle boundaries with spinboxes
   - Align channels if timing was off
   - Add missing flags (rare, but possible)

3. **Quality validation**
   - Confidence scores highlight uncertain detections
   - Contact time verification catches errors
   - Baseline stability checks prevent bad data

4. **Export flexibility**
   - Excel: human-readable, editable
   - CSV: machine-readable, analysis-ready
   - AnIML: regulatory-compliant, auditable

---

## 7. Comparison: Manual vs Pump Injection Data

### Manual Injection (Complex)
```python
{
    "manual_injection_mode": "manual",
    "method_mode": "manual",
    "detection_sensitivity": 2.0,  # Conservative
    
    # User interaction required
    "injection_time_by_channel": {
        "a": 123.45,  # Detection varied by channel
        "b": 124.12,  # Due to manual syringe timing
    },
    "injection_confidence_by_channel": {
        "a": 0.95,  # Good signal
        "b": 0.87,  # Lower (syringe noise?)
    },
    
    # Multiple injections possible
    "planned_concentrations": ["100 nM", "50 nM", "10 nM"],
    "injection_count": 1,
    
    # Flags placed at different times
    "flags": [
        {"type": "injection", "channel": "a", "time": 123.45},  # User Ctrl+Click
        {"type": "injection", "channel": "b", "time": 124.12},
        {"type": "wash", "channel": "a", "time": 303.45},  # Automatic
        {"type": "wash", "channel": "b", "time": 304.12},
    ],
}
```

### Pump Injection (Simple)
```python
{
    "manual_injection_mode": "automated",
    "method_mode": "semi-automated",
    "detection_sensitivity": 0.75,  # Tight
    
    # Automatic valve control
    "injection_time_by_channel": {
        "a": 20.0,  # Synchronized
        "b": 20.0,  # All channels same time
    },
    "injection_confidence_by_channel": {
        "a": 0.99,  # Clean pump signal
        "b": 0.99,
    },
    
    # Single injection
    "planned_concentrations": [],  # Not used for pump
    "injection_count": 0,
    
    # Flags synchronized
    "flags": [
        {"type": "injection", "channel": "a", "time": 20.0},  # Auto-placed
        {"type": "injection", "channel": "b", "time": 20.0},
        {"type": "wash", "channel": "a", "time": 200.0},  # Automatic
        {"type": "wash", "channel": "b", "time": 200.0},
    ],
}
```

**Why Manual is More Complex:**
- User timing variance → different injection times per channel
- Syringe handling noise → lower detection confidence
- Multi-injection schedule → state tracking required
- Manual flag placement → user interaction in workflow
- Contact timer → must track and alert user
- Automatic wash flags → triggered by timer expiration

**But With Good Data Organization:**
- All metadata captured automatically
- No manual record-keeping needed
- Easy to review and validate in Edits
- Complete audit trail preserved

---

## 8. Summary: Why This Matters

### For Users
✅ **Less work during run** - System handles timing, detection, flags  
✅ **Better data quality** - No missed injections or forgotten notes  
✅ **Easier troubleshooting** - Confidence scores show which injections need review  
✅ **Faster analysis** - Load Excel → all data organized and ready  

### For Developers
✅ **Clean separation** - Method Builder → Live → Edits workflow is clear  
✅ **Consistent metadata** - Same structure from planning to export  
✅ **Easy debugging** - All detection results logged and saved  
✅ **Future-proof** - Adding new fields is straightforward  

### For Data Integrity
✅ **Audit trail** - Complete record of what happened when  
✅ **Reproducibility** - All settings and results preserved  
✅ **Validation** - Confidence scores enable QC  
✅ **Compliance** - AnIML export for regulatory needs  

---

## 9. Files Reference

### Method Builder
- `affilabs/widgets/method_builder_dialog.py` - Main dialog UI
- `affilabs/domain/cycle.py` - Cycle data model

### Live Execution
- `affilabs/coordinators/injection_coordinator.py` - Injection workflow
- `affilabs/dialogs/manual_injection_dialog.py` - 60s detection window
- `affilabs/dialogs/concentration_schedule_dialog.py` - Multi-injection schedule
- `main.py` - Contact timer and automatic wash flags
- `affilabs/affilabs_core_ui.py` - Timer tick handler

### Edits Tab
- `affilabs/tabs/edits_tab.py` - Full edits interface
- `affilabs/domain/cycle.py` - `to_export_dict()` method

### Detection
- `affilabs/spr_signal_processing.py` - `auto_detect_injection_point()`

### Export
- `affilabs/utils/export_helpers.py` - Excel/CSV/image export
- `affilabs/services/animl_exporter.py` - AnIML format

---

**Last Updated:** February 15, 2026  
**Version:** ezControl 2.0 with automatic wash flags
