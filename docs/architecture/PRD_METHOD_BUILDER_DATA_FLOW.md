# Architecture Spec: Method Builder → Data Output Flow
**Data Integrity in Cycle Definitions**

**Version:** 1.5 (Live Edits Population Fix)  
**Date:** 2026-02-18  
**Status:** 🟢 Active Reference  
**Audience:** Internal dev team, future maintainers  

**Revision History:**
- **v1.5** (2026-02-18): Layer 6 implementation complete — Fixed `add_cycle()` method in `_table_mixin.py` to enable live cycle-by-cycle population during acquisition; enhanced with UI updates, metadata refresh, filter dropdown sync, and auto-scroll
- **v1.4** (2026-02-18): Layers 6-7 added — complete data pipeline documentation: Execution → RecordingManager → Excel export → Edits tab → Excel re-export; 6-sheet Excel schema; edit integrity checkpoints; alignment data preservation
- **v1.3** (2026-02-18): Layer 5 enhanced — batch undo via `AddMethodCommand`, `source_method` field for method tracking, auto-start implementation, queue-level validation hooks, mixed-method unit detection
- **v1.2** (2026-02-18): Layer 5 corrected — fixed queue API documentation (`add_cycle` loop, not `load_method`); documented undo/redo support via CommandHistory; updated recommendations to reflect completed validation work
- **v1.1** (2026-02-18): Layer 3 simplified from 13 → 8 categories; `detection_sensitivity` deleted; 3 deprecated fields clarified
- **v1.0** (2026-02-18): Initial documentation of complete Method Builder data flow

---

## Executive Summary

**Problem:** Cycles created in Method Builder don't always match what gets executed or exported. Data fields can get lost, incorrectly parsed, or corrupted during transformation from user input → Cycle object → Queue → Execution → Excel export.

**Root Cause:** Complex multi-stage data flow with 40+ fields, regex parsing, hardware-specific logic, and incomplete validation.

**Scope:** This spec documents the **complete data transformation pipeline** from Method Builder input to Cycle domain objects ready for execution. It identifies:
- What fields exist and where they come from
- How parsing transforms unstructured text → structured data
- Where data can get lost or corrupted
- What validation exists (and what's missing)

**Recent Simplification (v1.1):**
- **Field count reduced:** 40+ → ~36 active fields (3 deprecated but retained)
- **Categories consolidated:** 13 → 8 logical groups
- **Deprecated fields:** `concentration_value`, `concentration_units`, `delta_spr` (kept for file compatibility)
- **Deleted fields:** `detection_sensitivity` (dead code, never set anywhere)

**Complete Pipeline Coverage (v1.4):**
- ✅ **Layers 1-5:** Method Builder → Parser → Domain Model → Validation → Queue Integration
- ✅ **Layers 6-7:** Execution → Excel Export → Edits Tab → Excel Re-Export
- ⚠️ **Not Covered:** Runtime execution internals (injection detection algorithms, flag placement logic)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER 1-2: METHOD BUILDER                        │
│  User Input (text) → Parser → Cycle Objects → Queue                │
└─────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   LAYER 3-4: DOMAIN & VALIDATION                    │
│  Cycle Domain Model (36 fields, 8 categories) → Validation Checks  │
└─────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   LAYER 5: QUEUE INTEGRATION                        │
│  QueuePresenter → CommandHistory (undo/redo) → Queue Manager       │
└─────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   LAYER 6: EXECUTION → EDITS                        │
│  Acquisition → RecordingManager → Excel (6 sheets) → Edits Tab     │
└─────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   LAYER 7: EDITS → RE-EXPORT                        │
│  User Edits (alignment, delta SPR) → Excel Re-Export → Analysis    │
└─────────────────────────────────────────────────────────────────────┘
```

**This spec covers all 7 layers** (Method Builder → Queue → Execution → Excel → Edits → Re-Export).

---

## Layer 1: Method Builder UI

### Location
**File:** `affilabs/widgets/method_builder_dialog.py` (3134 lines)

### User Interface Components

The Method Builder dialog uses a **tab-based interface** with two modes:

#### A. Easy Mode Tab (Form-Based Builder)
**Purpose:** Beginner-friendly structured input with visual form fields

**Form Fields:**
1. **Cycle Type** (Dropdown): Baseline | Binding | Kinetic | Regeneration | Immobilization | Blocking | Wash | Other
2. **Duration** (Spinbox + Unit): Value + dropdown (s | min | h)
3. **Channels** (Checkboxes): A | B | C | D (multi-select)
4. **Concentration** (Number + Unit): Value + dropdown (nM | µM | mM | M | pM | µg/mL | ng/mL | mg/mL)
5. **Contact Time** (Spinbox + Unit): Value + dropdown (s | min | h)
6. **Flow Rate** (Spinbox + Unit): Value + dropdown (µL/min | mL/min)

**Preview:** Live text preview shows equivalent Power Mode syntax
- Updates on every field change
- Example: `Binding 5min [ABCD:100nM] contact 180s flow 25µL/min`

**Button:** "Insert to Power Mode →" transfers generated text to Power Mode tab

---

#### B. Power Mode Tab (Text-Based Builder)
**Purpose:** Expert mode for fast text entry with advanced syntax support

**Text Input:**
- Multi-line text editor (1500 char limit)
- Monospace font (Consolas/Monaco)
- Character counter (bottom right)
- Live validation on parse

**Input Format:**
```
<CycleType> <Duration> [<ChannelConc>] <Modifiers>
```

**Examples:**
- `Baseline 5min`
- `Binding 5min [A:100nM] contact 180s`
- `Kinetic 10min [BD:50nM,25nM] ct 5min partial injection`
- `Regeneration 30sec [ALL:10mM]`
- `Wash 2min overnight`

**Keyboard Shortcuts:**
- `[` + `:` → Auto-completes to `[:]` (cursor between)
- `Ctrl+Enter` → Add to method (same as Build button)

**Buttons Row (above text input):**
- **➕ Build** — Parse text and add cycles to method table
- **🗑 Clear** — Clear text input
- **❔ Help** — Show syntax guide dialog

---

#### C. Method Table (Shared Between Both Tabs)
**Columns:** # | Type | Duration | Notes

**Purpose:** Shows all cycles added to current method

**Features:**
- Cycle numbering (auto-renumbered after edits)
- Details tab shows injection parameters per cycle
- Drag-to-reorder support
- Multi-select delete

**Buttons Row (below table):**
- **↑ / ↓** — Move selected cycle up/down
- **🗑 Delete** — Remove selected cycle(s)
- **↶ / ↷** — Undo/Redo (keyboard: Ctrl+Z / Ctrl+Shift+Z)

---

#### D. Settings Panel (Hardware-Specific Configuration)
**Toggle:** ⚙ Cog button (top right, above tabs)

**Fields:**
- **Mode Selector:** Manual | Semi-Automated | Automated  
  *Auto-configured based on hardware (`configure_for_hardware()` line 2596)*
- **Detection Priority:** Auto | Priority | Off  
  *Controls injection detection sensitivity*

**Hardware Detection:**
- **P4SPR (no pump):** Mode locked to "Manual"
- **P4SPR + AffiPump:** Manual or Semi-Automated
- **P4PRO / P4PROPLUS:** Manual or Semi-Automated (default Semi-Automated)

**Note:** Detection always defaults to "Auto" — sensitivity adapts internally based on mode

---

#### E. Bottom Button Row
**Buttons:**
- **💾 Save** — Save method to JSON file
- **📂 Load** — Load method from JSON file
- **📋 Copy Schedule** — Copy injection checklist to clipboard (for manual tracking)
- **Push to Queue** — Transfer all cycles to main queue and close dialog
- **✕ Close** — Cancel and close dialog

---

## Layer 2: Text Parsing Logic

### Function: `_build_cycle_from_text(text: str) -> Cycle`
**Location:** Line 1740–1920 in `method_builder_dialog.py`

### Input Format

Users type free-form text with embedded tags:

```
<CycleType> <Duration> [<ChannelConc>] <Modifiers>
```

**Examples:**
- `Baseline 5min`
- `Binding 5min [A:100nM] contact 180s`
- `Kinetic 10min [BD:50nM,25nM] ct 5min partial injection`
- `Regeneration 30sec [ALL:10mM] manual injection`
- `Immobilization 30min [A:50µg/mL] contact 1800s`
- `Wash 2min overnight`

### Parsing Rules

#### 1. Cycle Type Extraction
**Pattern:** First word in text (case-insensitive)

**Valid Types:**
- Baseline, Immobilization, Blocking, Wash
- Binding, Kinetic, Regeneration
- Other, Auto-read, Custom

**Fallback:** If no match, defaults to `"Other"`

**Code:**
```python
cycle_types = [
    "Baseline", "Immobilization", "Blocking", "Wash",
    "Binding", "Kinetic", "Regeneration",
    "Other", "Auto-read", "Custom"
]
cycle_type = "Other"  # Default
for ct in cycle_types:
    if ct.lower() in text.lower():
        cycle_type = ct
        break
```

---

#### 2. Duration Extraction
**Pattern:** `<number> <unit>`

**Supported Units:**
- Seconds: `30s`, `30sec`
- Minutes: `5min`, `5m`
- Hours: `2h`, `2hr`, `24hours`
- Special: `overnight` = 8 hours (480 min)

**Regex:** `r'(\d+(?:\.\d+)?)\s*(h|hr|hour|hours|min|m|sec|s)\b'`

**Default:** 5.0 minutes if not specified

**Code:**
```python
if 'overnight' in text.lower():
    duration_minutes = 8 * 60.0  # 480 minutes
else:
    duration_match = re.search(r'(\d+(?:\.\d+)?)\s*(h|hr|hour|hours|min|m|sec|s)\b', text, re.IGNORECASE)
    if duration_match:
        value = float(duration_match.group(1))
        unit = duration_match.group(2).lower()
        if unit in ['sec', 's']:
            duration_minutes = value / 60.0
        elif unit in ['h', 'hr', 'hour', 'hours']:
            duration_minutes = value * 60.0
        else:  # min or m
            duration_minutes = value
```

---

#### 3. Concentration Tags Extraction
**Pattern:** `[<Channels>:<Value><Unit>]` or `<Channels>:<Value><Unit>`

**Channel Groups:**
- Single: `A`, `B`, `C`, `D`
- Multi: `AB`, `BD`, `ABCD`
- All: `ALL` (expands to ABCD)

**Concentration Formats:**
- Single value for all channels: `[A:100nM]` → A gets 100 nM
- Multi-channel same value: `[BD:50nM]` → B and D both get 50 nM
- Comma-separated per channel: `[ABCD:100,50,25,10]` → A=100, B=50, C=25, D=10

**Supported Units:**
- Molar: `nM`, `µM`, `mM`, `M`, `pM`
- Mass: `µg/mL`, `ng/mL`, `mg/mL`

**Regex:** `r"\[?([A-Da-d]+|ALL|all):([\d.,\s]+)([a-zA-Zµ/]+)?\]?"`

**Code:**
```python
tags_with_units = re.findall(r"\[?([A-Da-d]+|ALL|all):([\d.,\s]+)([a-zA-Zµ/]+)?\]?", text, re.IGNORECASE)
concentrations = {}
detected_unit = "nM"  # default

for ch_group, val_str, unit_str in tags_with_units:
    ch_group_upper = ch_group.upper()
    
    if ch_group_upper == "ALL":
        channels_to_set = ["A", "B", "C", "D"]
    else:
        channels_to_set = list(ch_group_upper)
        valid_channels = {"A", "B", "C", "D"}
        channels_to_set = [ch for ch in channels_to_set if ch in valid_channels]
    
    # Comma-separated or single value
    if ',' in val_str:
        concentration_values = [float(v.strip()) for v in val_str.split(',') if v.strip()]
        for i, ch in enumerate(channels_to_set):
            if i < len(concentration_values):
                concentrations[ch] = concentration_values[i]
            else:
                concentrations[ch] = concentration_values[-1]
    else:
        val = float(val_str.strip())
        for ch in channels_to_set:
            concentrations[ch] = val
    
    if unit_str:
        detected_unit = unit_str
```

**Result:** `concentrations` dict like `{"A": 100.0, "B": 50.0}` and `detected_unit` like `"nM"`

---

#### 4. Contact Time Extraction
**Pattern:** `contact <number><unit>` or `ct <number><unit>`

**Formats:**
- Full: `contact 180s`, `contact 3min`, `contact 1h`
- Shorthand: `ct 180s`, `ct 3m`
- No space: `contact180s`, `ct3m`

**Unit Conversion:**
- Seconds: `180s` → 180.0
- Minutes: `3min` → 180.0 (× 60)
- Hours: `1h` → 3600.0 (× 3600)

**Default if not specified:**
- Binding/Kinetic: 300 seconds (5 minutes)
- Regeneration: 30 seconds
- Others: None (no contact time)

**Regex:**
```python
contact_match = re.search(r'contact[:\s]*(\d+(?:\.\d+)?)\s*(s|sec|m|min|h|hr)?', text, re.IGNORECASE)
if not contact_match:
    contact_match = re.search(r'\bct\s*(\d+(?:\.\d+)?)\s*(s|sec|m|min|h|hr)?', text, re.IGNORECASE)
```

**Code:**
```python
if contact_match:
    value = float(contact_match.group(1))
    unit = contact_match.group(2).lower() if contact_match.group(2) else 's'
    if unit in ['h', 'hr']:
        contact_time = value * 3600.0
        if value > 3:
            self.overnight_mode_check.setChecked(True)  # Auto-enable overnight
    elif unit in ['m', 'min']:
        contact_time = value * 60.0
    else:
        contact_time = value
```

---

#### 5. Injection Method Modifiers
**Keywords:**
- `partial injection` or `partial` → `injection_method = "partial"` (30 µL spike)
- `manual injection` → `manual_injection_mode = "manual"` (P4SPR syringe mode)
- `automated` → `manual_injection_mode = "automated"` (pump-controlled)

**Auto-Detection by Cycle Type:**
| Cycle Type | injection_method | contact_time |
|------------|------------------|--------------|
| Baseline | None | None |
| Immobilization | "simple" (or None if manual mode) | Required from text |
| Blocking | "simple" (or None if manual mode) | Required from text |
| Wash | "simple" (or None if manual mode) | Required from text |
| Binding | "simple" (or "partial" if override) | 300 s default |
| Kinetic | "simple" (or "partial" if override) | 300 s default |
| Regeneration | "simple" | 30 s default |
| Other | None | None |

---

#### 6. Detection Priority Modifiers
**Keywords:**
- `detection priority` → `detection_priority = "priority"` (lower threshold)
- `detection off` → `detection_priority = "off"` (no auto-detection)
- `detection auto` → `detection_priority = "auto"` (mode-dependent)

**Regex:** `r'detection\s+(priority|off|auto)'`

---

#### 7. Target Channels Override
**Keywords:**
- `channels AC` → `target_channels = "AC"`
- `channels BD` → `target_channels = "BD"`
- `channels ABCD` → `target_channels = "ABCD"`

**Auto-Derivation:** If not specified, derived from concentration tags (e.g., `[AB:100nM]` → `target_channels = "AB"`)

**Regex:** `r'channels?\s+([ABCD]+)'`

---

#### 8. Planned Concentrations List
**Purpose:** Track multi-injection schedules (e.g., titration series)

**Format:** List of strings like `["Ch A: 100 nM", "Ch B: 50 nM"]`

**Generation:**
```python
planned_concentrations = []
if cycle_type in ("Binding", "Kinetic") and concentrations:
    for ch in sorted(concentrations.keys()):
        val = concentrations[ch]
        conc_str = f"{val} {detected_unit}".replace(" .", ".")
        planned_concentrations.append(f"Ch {ch}: {conc_str}")
```

**Result:** `["Ch A: 100 nM", "Ch B: 50 nM", "Ch C: 25 nM"]`

---

### Parsing Summary Table

| Input Text | Parsed Fields |
|------------|---------------|
| `Baseline 5min` | type="Baseline", length_minutes=5.0, injection_method=None |
| `Binding 5min [A:100nM]` | type="Binding", length_minutes=5.0, concentrations={"A":100}, units="nM", contact_time=300.0, injection_method="simple" |
| `Kinetic 10min [BD:50nM,25nM] ct 180s` | type="Kinetic", length_minutes=10.0, concentrations={"B":50,"D":25}, contact_time=180.0 |
| `Regeneration 30sec [ALL:10mM]` | type="Regeneration", length_minutes=0.5, concentrations={"A":10,"B":10,"C":10,"D":10}, units="mM", contact_time=30.0 |
| `Wash 2min overnight` | type="Wash", length_minutes=480.0, injection_method="simple" (if not manual mode), contact_time=None |
| `Immobilization 30min [A:50µg/mL] contact 1800s` | type="Immobilization", length_minutes=30.0, concentrations={"A":50}, units="µg/mL", contact_time=1800.0 |

---

## Layer 3: Cycle Domain Model

### Class: `Cycle` (Pydantic BaseModel)
**Location:** `affilabs/domain/cycle.py` (388 lines)

**Total Fields:** ~35 active fields (5 deprecated but retained for compatibility)

**Field Categories:** (Simplified from 13 → 8 categories)

### 1. Core Identity (Required)
```python
type: str  # "Baseline", "Binding", "Kinetic", "Regeneration", etc.
length_minutes: float  # Duration (must be > 0)
```

### 2. Metadata & Concentrations
```python
# Basic metadata
name: str = ""  # User-friendly name (auto-generated if empty)
note: str = ""  # Full user-typed line from Method Builder

# Multi-channel concentrations (primary)
units: str = "nM"  # Active units for all concentrations
concentrations: Dict[str, float] = {}  # {"A": 100.0, "B": 50.0}

# ⚠️ DEPRECATED (kept for file compatibility):
concentration_value: Optional[float] = None  # Single-channel value (use concentrations dict)
concentration_units: str = "nM"  # Unit field (use units field)
```

### 3. Unique Identifiers
```python
cycle_id: int = 0  # Permanent ID (immutable after creation)
timestamp: float  # Unix timestamp when cycle was created
```

### 4. Runtime State & Method Mode
```python
# Execution state
cycle_num: int = 0  # Sequential position in queue (can change)
total_cycles: int = 0  # Total cycles in queue
status: CycleStatus = "pending"  # "pending" | "running" | "completed" | "cancelled"

# Method configuration
method_mode: Optional[str] = None  # "manual" | "semi-automated" | "automated"
detection_priority: str = "auto"  # "auto" | "priority" | "off"
```

### 5. Execution Results
```python
# Timeline tracking
sensorgram_time: Optional[float] = None  # Start time in sensorgram
end_time_sensorgram: Optional[float] = None  # End time in sensorgram

# Analysis results
delta_spr_by_channel: Dict[str, float] = {}  # {"A": 45.2, "B": 87.3}

# ⚠️ DEPRECATED (kept for export compatibility):
delta_spr: Optional[float] = None  # Single-channel value (use delta_spr_by_channel)
```

### 6. Flags & Injection Detection
```python
# Event markers
flags: List[str] = []  # Simple flag names ["injection", "wash"]
flag_data: List[dict] = []  # Detailed flag markers with positions

# Per-channel injection detection
injection_time_by_channel: Dict[str, float] = {}  # {"A": 123.5, "B": 124.1}
injection_confidence_by_channel: Dict[str, float] = {}  # {"A": 0.85, "B": 0.72}
injection_mislabel_flags: Dict[str, str] = {}  # {"C": "inactive_channel"}
```

### 7. Hardware Control (Pump & Injection)
```python
# Pump settings (hardware-specific)
flow_rate: Optional[float] = None  # µL/min (None = no pump)
injection_volume: Optional[float] = None  # µL (None = use default)
pump_type: Optional[Literal["affipump", "p4proplus"]] = None
channels: Optional[Literal["AC", "BD"]] = None  # Active SPR channels

# Injection parameters
injection_method: Optional[Literal["simple", "partial"]] = None
injection_delay: float = 20.0  # Seconds after cycle start (fixed)
contact_time: Optional[float] = None  # Seconds (for association phase)

# Manual injection mode (P4SPR workflows)
manual_injection_mode: Optional[Literal["automated", "manual"]] = None

# Multi-injection tracking (P4SPR workflows with planned_concentrations)
planned_concentrations: List[str] = []  # ["100 nM", "50 nM", "10 nM"]
injection_count: int = 0  # How many injections completed

# Detection targeting
target_channels: Optional[str] = None  # "AC", "BD", "ABCD" - parsed from [X:...] tags
```

---

### Deprecation Strategy

**Field Status Legend:**
- **Active** — Primary fields used throughout codebase
- **⚠️ Deprecated** — Retained for backward compatibility (file imports), but superseded by better alternatives
- **❌ Removed** — Documented but not implemented in current version (candidates for elimination)

**Deprecated Field Migration Path:**

| Field | Status | Replacement | Migration Plan |
|-------|--------|-------------|----------------|
| `concentration_value` | ⚠️ Deprecated | `concentrations` dict | Keep for v2.0.x; remove in v2.1.0 after file format migration |
| `concentration_units` | ⚠️ Deprecated | `units` field | Keep for v2.0.x; remove in v2.1.0 after file format migration |
| `delta_spr` | ⚠️ Deprecated | `delta_spr_by_channel` | Keep for export compatibility; phase out in next major version |
| `detection_sensitivity` | ✅ Deleted (v1.1) | N/A (never used) | Removed from cycle.py — dead code eliminated |

**Rationale:**
- **Backward compatibility first:** Deprecated fields remain in the model to support loading old JSON/Excel files
- **No breaking changes in v2.0.x:** Code continues to work with existing data files
- **Clear migration path:** Future versions can safely drop deprecated fields after file format update

---

### Field Validation (Pydantic)

**Automatic Validation:**
- `length_minutes > 0` (enforced by `gt=0` constraint)
- Type coercion: `"5.0"` string → `5.0` float
- Default values: Missing fields auto-populate

**Custom Validators:**
```python
@field_validator("length_minutes")
@classmethod
def validate_length(cls, v: float) -> float:
    if v <= 0:
        raise ValueError(f"Cycle length must be positive, got {v}")
    return v

@field_validator("name")
@classmethod
def set_default_name(cls, v: str, info) -> str:
    if not v and "type" in info.data:
        return f"{info.data['type']} Cycle"
    return v
```

---

## Layer 4: Validation & Warnings

### Function: `_validate_and_warn_cycle(cycle: Cycle, raw_text: str)`
**Location:** Line 2580–2700 in `method_builder_dialog.py`

**Non-Blocking Warnings (Yellow Alerts):**

#### 1. Missing Contact Time on Binding/Kinetic
```python
if cycle.type in ("Binding", "Kinetic") and cycle.injection_method and not cycle.contact_time:
    warnings.append("⚠️ No contact time set — injection will run for full cycle duration")
```

#### 2. Contact Time Too Short
```python
if cycle.type in ("Binding", "Kinetic") and cycle.contact_time and cycle.contact_time < 60:
    warnings.append(f"⚠️ Contact time is very short ({cycle.contact_time:.0f}s)")
```

#### 3. Contact Time vs Cycle Duration Mismatch
```python
cycle_seconds = cycle.length_minutes * 60
if cycle.contact_time > cycle_seconds * 0.9:
    warnings.append(
        f"⚠️ Contact time ({cycle.contact_time:.0f}s) is "
        f"{cycle.contact_time / cycle_seconds:.0%} of cycle duration"
    )
```

#### 4. Channel Mismatch
```python
if cycle_has_all and len(conc_channels) < 4:
    channels_str = ", ".join(sorted(conc_channels))
    warnings.append(
        f"⚠️ Channel mismatch — concentrations only set for {channels_str} but cycle runs ALL"
    )
```

#### 5. Very Short Cycles
```python
if cycle.length_minutes < 2.0 and cycle.injection_method:
    warnings.append(
        f"⚠️ Short cycle ({cycle.length_minutes:.1f} min) may be rushed\n"
        "   → Consider 3-5 min minimum for manual injection"
    )
```

#### 6. Missing Regeneration After Binding
```python
if cycle.type == "Binding" and cycle.injection_method:
    cycle_idx = self._local_cycles.index(cycle) if cycle in self._local_cycles else -1
    if cycle_idx >= 0 and cycle_idx < len(self._local_cycles) - 1:
        next_cycle = self._local_cycles[cycle_idx + 1]
        if next_cycle.type != "Regeneration":
            warnings.append("💡 Consider adding Regeneration cycle after Binding")
```

**Display:** Warnings shown in yellow banner below method table (non-blocking, user can proceed)

---

## Layer 5: Queue Integration

### Handoff Points

#### A. Single Cycle Addition
**Trigger:** User presses **Build →** button (or Ctrl+Enter)

**Flow:**
```
1. User types note: "Binding 5min [A:100nM] contact 180s"
2. _build_cycle_from_text(text) → Cycle object
3. _validate_and_warn_cycle(cycle, text) → Show warnings
4. _local_cycles.append(cycle) → Add to internal list
5. _refresh_method_table() → Update UI table
```

**Code Path:**
```python
def _on_add_to_method(self):
    notes_text = self.notes_input.toPlainText().strip()
    if not notes_text:
        return
    
    for line in notes_text.split('\n'):
        cycle = self._build_cycle_from_text(line)
        self._validate_and_warn_cycle(cycle, line)
        self._local_cycles.append(cycle)
    
    self._refresh_method_table()
    self.notes_input.clear()
```

#### B. Batch Cycle Loading
**Trigger:** User pastes multiple lines or loads preset

**Flow:**
```
1. User pastes 10 lines of method
2. Each line parsed independently
3. All cycles added to _local_cycles[]
4. Single table refresh at end
```

#### C. Queue Transfer
**Trigger:** User closes Method Builder dialog (confirms save)

**Flow:**
```
1. Dialog closes with accepted state
2. Main window receives _local_cycles list
3. Queue Manager loads cycles: queue_presenter.load_method(cycles)
4. Cycles now ready for execution
```

**Code Path (Main Window):**
```python
def _on_method_ready(self, action: str, method_name: str, cycles: list):
    """Handle method push from Method Builder dialog.
    
    Args:
        action: 'queue' (add to queue) or 'start' (queue and start immediately)
        method_name: Display name for the method
        cycles: List of Cycle objects to queue
    """
    for cycle in cycles:
        self.queue_presenter.add_cycle(cycle)  # Each cycle wrapped in AddCycleCommand for undo
        
    logger.info(f"✓ Loaded {len(cycles)} cycles into queue from method '{method_name}'")
    
    # Auto-start if requested (currently unused - action is always "queue")
    if action == "start":
        # Start acquisition immediately (future feature)
        pass
```

---

## Data Corruption Risk Points

### 🔴 Critical: Where Data Can Get Lost

#### 1. **Parsing Failure → Silent Defaults**
**Location:** `_build_cycle_from_text()`

**Problem:** If regex doesn't match, fields silently fall back to defaults:
- Duration → 5.0 minutes (generic default)
- Contact time → 300 s for Binding/Kinetic (may not be what user intended)
- Cycle type → "Other" (if typo in cycle name)

**Example:**
```
User types: "Binding 10mi [A:100nM]"  ← Typo: "mi" not "min"
Parsed: duration_minutes = 5.0  ← Falls back to default, ignores "10mi"
```

**Impact:** User expects 10 min cycle, gets 5 min cycle instead.

**Mitigation:** Validation warnings catch some cases but not all.

---

#### 2. **Multi-Channel Concentration Ambiguity**
**Location:** `_build_cycle_from_text()` concentration parsing

**Problem:** Comma-separated concentrations map to channels in sorted order:
```
User types: [ABCD:100,50,25,10]
Parsed: A=100, B=50, C=25, D=10  ← Correct
```

But if user types fewer values than channels:
```
User types: [ABCD:100,50]
Parsed: A=100, B=50, C=50, D=50  ← Last value repeated (may not be intended)
```

**Impact:** Channels C and D get same concentration as B (may be wrong).

**Mitigation:** None currently — parser assumes last value repeats.

---

#### 3. **contact_time Unit Ambiguity**
**Location:** `_build_cycle_from_text()` contact time parsing

**Problem:** If user omits unit, parser assumes seconds:
```
User types: "contact 5"  ← User may mean 5 minutes
Parsed: contact_time = 5.0  ← Interpreted as 5 seconds
```

**Impact:** Contact time far shorter than intended (5 sec vs 300 sec).

**Mitigation:** Validation warns if contact_time < 60 seconds.

---

#### 4. **Cycle Type Typo → Wrong Defaults**
**Location:** `_build_cycle_from_text()` type detection

**Problem:** If user mistypes cycle type:
```
User types: "Binidng 5min [A:100nM]"  ← Typo: "Binidng"
Parsed: type = "Other"  ← Falls back to Other
        injection_method = None  ← No injection because Other doesn't inject
```

**Impact:** Cycle runs as buffer-only (no injection) despite concentration tag.

**Mitigation:** None — no spell-checking on cycle types.

---

#### 5. **Detection Priority Inheritance**
**Location:** `_build_cycle_from_text()` method_mode/detection_priority

**Problem:** Detection settings come from dialog-level selectors, not cycle text:
```
Dialog setting: Detection Priority = "Auto"
User types: "Binding 5min [A:100nM] detection off"  ← User wants detection off
Parsed: detection_priority = "off"  ← Correct from text
```

But if user forgets to specify:
```
User types: "Binding 5min [A:100nM]"  ← No detection override
Parsed: detection_priority = "auto"  ← Inherited from dialog (may not be desired)
```

**Impact:** User may expect different detection behavior than what runs.

**Mitigation:** Cycle-level override keywords exist but must be explicitly typed.

---

#### 6. **Planned Concentrations Order**
**Location:** `_build_cycle_from_text()` planned_concentrations generation

**Problem:** Planned concentrations list is sorted alphabetically:
```
User types: [BD:50nM,25nM]
Parsed: concentrations = {"B": 50.0, "D": 25.0}  ← Correct
        planned_concentrations = ["Ch B: 50 nM", "Ch D: 25 nM"]  ← Sorted
```

If injection detection expects specific order, sorting may misalign expectations.

**Impact:** Injection counting/detection may not match user's mental model.

**Mitigation:** Detection uses channel keys, not list order.

---

#### 7. **injection_method Auto-Detection Conflicts**
**Location:** `_build_cycle_from_text()` injection method rules

**Problem:** Injection method auto-assigned by cycle type, but user overrides may conflict:
```
User types: "Immobilization 30min [A:50µg/mL] manual injection"
Parsed: manual_injection_mode = "manual"  ← From text
        injection_method = None  ← Because manual mode disables injection
```

But runtime may expect `injection_method = "simple"`:
```
Execution: if cycle.injection_method:
               trigger_injection()  ← Skipped because None
```

**Impact:** No injection fires despite concentration tag.

**Mitigation:** Parser correctly sets `injection_method = None` for manual mode, but user may not understand this.

---

#### 8. **Pydantic Validation Bypass**
**Location:** Cycle object creation

**Problem:** Pydantic validates on creation, but not on mutation:
```python
cycle = Cycle(type="Binding", length_minutes=5.0)  ← Validated
cycle.length_minutes = -10.0  ← NOT validated (validation not triggered on assignment)
```

**Impact:** Invalid data can sneak in after creation.

**Mitigation:** Pydantic config includes `validate_assignment=True`, but mutations after export may not validate.

---

## Templates & Presets

### Location
- **Cycle Templates:** `cycle_templates.json` (currently empty)
- **Queue Presets:** `queue_presets.json` (currently empty)
- **Template Storage Service:** `affilabs/services/cycle_template_storage.py`

### Template Structure
```python
class CycleTemplate:
    template_id: int
    name: str  # "Standard Binding"
    cycle_type: str  # "Binding"
    length_minutes: float  # 5.0
    note: str  # "Binding 5min [A:#{conc}nM] contact 180s"
    units: str  # "nM"
    concentrations: Dict[str, float]  # {"A": 100.0}
    created_at: str  # ISO timestamp
    modified_at: str  # ISO timestamp
```

### Preset Loading
**Command:** `@preset_name` in Method Builder note field

**Example:**
```
User types: @standard_binding
Effect: Loads template → Inserts pre-filled cycle text
```

**Current Status:** No active templates exist (JSON files empty).

---

## Queue Transfer & Execution

### Queue Manager Handoff
**Location:** `mixins/_pump_mixin.py:2173` + `affilabs/presenters/queue_presenter.py:126`

**Flow:**
```
1. User clicks "Push to Queue" button in Method Builder dialog
2. Dialog emits: method_ready Signal(action="queue", method_name, cycles)
3. Main Window receives via _on_method_ready(action, method_name, cycles)
4. Main Window tags all cycles with source_method = method_name
5. Main Window calls: queue_presenter.add_method(cycles, method_name)
6. QueuePresenter creates AddMethodCommand (batch undo support)
7. Command executes: adds all cycles via queue_manager.add_cycle() loop
8. Each add_cycle() runs validation hooks + mixed-method detection
9. Queue auto-renumbers after all cycles added
```

**Actual Implementation:**
```python
def _on_method_ready(self, action: str, method_name: str, cycles: list):
    """Handle method push from Method Builder dialog.
    
    Args:
        action: 'queue' (add to queue) or 'start' (queue and start immediately)
        method_name: Display name for the method
        cycles: List of Cycle objects to queue
    """
    # Tag all cycles with source method
    for cycle in cycles:
        cycle.source_method = method_name
    
    # Add as batch (single undo removes entire method)
    self.queue_presenter.add_method(cycles, method_name)
    
    # Auto-start if requested
    if action == "start":
        self.acq_coordinator._start_acquisition()
        self.acq_coordinator._update_ui_after_start()
```

**✅ Batch Command Pattern:**
- `AddMethodCommand` wraps all cycles in one undoable operation
- Undo removes entire method at once (not 10 separate undos)
- Command description shows method name in undo list

**Cycle Numbering:**
```python
# Happens in queue_manager._renumber_cycles() (line 512)
def _renumber_cycles(self):
    for i, cycle in enumerate(self._pending_cycles, start=1):
        cycle.cycle_num = i
        cycle.total_cycles = len(self._pending_cycles)
```

**Auto-renumber after every mutation:**
- `add_cycle()` → renumber
- `delete_cycle()` → renumber
- `delete_cycles()` → renumber (batch deletion)
- `reorder_cycle()` → renumber
- `pop_next_cycle()` → **intentionally does NOT renumber** (preserves absolute numbers during run)

**✅ Queue-Level Validation (Defense-in-Depth):**
Each `add_cycle()` call validates:
1. Duration > 0 and <= 60 min
2. Contact time < cycle duration
3. **Mixed unit detection**: Warns if new cycle uses different units than existing queue

**Example:**
```
Queue has: [Cycle 1: 100 nM, Cycle 2: 50 nM]
User adds: Cycle 3: 10 µM
Warning: "Unit mismatch: new cycle uses 'µM' but queue has {'nM'}"
```

**✅ Method Metadata Tracking:**
- New field: `cycle.source_method` stores originating method name
- Useful for multi-method queues (100+ cycles from 5 different methods)
- UI can show method groupings in queue table

**Undo/Redo Support:**
All queue operations are wrapped in Command pattern:
- `AddCycleCommand` — Adds cycle, can undo to remove
- `DeleteCycleCommand` — Removes cycle, can undo to restore
- `DeleteCyclesCommand` — Batch removal, can undo to restore all
- `ReorderCycleCommand` — Move cycle position, can undo to revert
- `ClearQueueCommand` — Delete all cycles, can undo to restore entire queue

**Keyboard shortcuts:**
- Ctrl+Z → Undo last queue operation
- Ctrl+Shift+Z → Redo undone operation

**Execution Start:**
```
1. User presses Start
2. Queue Manager → Next cycle: _pending_cycles.pop(0)
3. Cycle status → "running"
4. Cycle.sensorgram_time set to current timeline position
5. Injection logic uses cycle.injection_method, cycle.contact_time
```

---

## Validation Improvements (v2.0.5)

All 8 validation gaps have been addressed:

### 1. **Concentration Unit Validation** ✅ FIXED
**Implementation:** Whitelist validation in parser (line 2022)
- Valid units: `nM, µM, uM, mM, M, pM, µg/mL, ug/mL, ng/mL, mg/mL, g/L`
- Invalid units trigger parse warning (non-blocking)
- User sees warning banner with invalid unit highlighted

---

### 2. **Channel Range Validation** ✅ FIXED
**Implementation:** Empty concentration check in validation (line 2851)
- Detects when concentration tags exist but no valid channels parsed
- Warning: "Concentration tags found but no valid channels — check for typos"
- Prevents silent failure of `[Z:100nM]` type errors

---

### 3. **Duration Limit Checks** ✅ FIXED
**Implementation:** Duration warning in validation (line 2859)
- Warns if `cycle.length_minutes > 60`
- Shows duration in both minutes and hours
- Suggests breaking into shorter segments

---

### 4. **Contact Time vs Duration Sanity Check** ✅ FIXED
**Implementation:** Already implemented (line 2909)
- Warning when `contact_time > 0.9 * cycle_duration`
- Non-blocking warning (user can proceed)
- Shows percentage of cycle consumed by contact time
- Suggests leaving buffer time for wash/baseline

---

### 5. **Multi-Injection Validation** ✅ FIXED
**Implementation:** Already implemented (line 2923)
- Distinguishes parallel vs sequential injections
- Parallel injections: All channels inject simultaneously (minor delay)
- Sequential injections: One after another (time-constrained)
- Calculates minimum cycle duration needed
- Warns if cycle too short for planned injections

---

### 6. **Detection Priority Conflict Check** ✅ FIXED
**Implementation:** Enhanced detection mode check (line 2954)
- Detects `detection_priority = "off"` without `manual_injection_mode = "manual"`
- Warns that auto-flagging won't work
- Suggests either enabling manual mode or changing detection to 'Auto'

---

### 7. **Cycle Numbering Persistence** ✅ FIXED
**Implementation:** Already implemented in `queue_manager.py`
- `_renumber_cycles()` called after every mutation:
  - `add_cycle()` → renumber (line 98)
  - `delete_cycle()` → renumber (line 122)
  - `delete_cycles()` → renumber (line 152)
  - `reorder_cycle()` → renumber (line 191)
- Ensures sequential numbering (1, 2, 3...) always maintained
- **Note:** `pop_next_cycle()` intentionally does NOT renumber (line 221) — preserves absolute cycle numbers during execution

---

### 8. **Units Consistency Check** ✅ FIXED
**Implementation:** Mixed units detection in validation (line 2868)
- Compares cycle units against all previous cycles in method
- Warns when unit changes detected (e.g., nM → µM)
- Explains impact on data analysis
- Recommends using consistent units throughout method

---

## Data Flow Verification Checklist

**Goal:** Ensure cycle data survives transformation from Method Builder → Execution → Export

| Stage | Data Point | Verified? | Notes |
|-------|------------|-----------|-------|
| **Parse** | Cycle type | ✅ | `_build_cycle_from_text()` extracts |
| **Parse** | Duration | ✅ | Regex + unit conversion |
| **Parse** | Concentrations | ✅ | Multi-channel parsing works |
| **Parse** | Contact time | ✅ | Defaults applied correctly |
| **Parse** | Injection method | ✅ | Auto-assigned by type |
| **Parse** | Unit validation | ✅ | Whitelist enforced (v2.0.5) |
| **Validate** | Duration > 0 | ✅ | Pydantic enforces |
| **Validate** | Duration limit | ✅ | Warns if > 60 min (v2.0.5) |
| **Validate** | Contact vs duration | ✅ | Warning when > 90% (v2.0.5) |
| **Validate** | Channel mismatch | ✅ | Warning for invalid channels (v2.0.5) |
| **Validate** | Detection conflicts | ✅ | Warns if detection off without manual mode (v2.0.5) |
| **Validate** | Mixed units | ✅ | Warns on unit change mid-method (v2.0.5) |
| **Queue** | Cycle numbering | ✅ | Auto-renumbered after mutations (v2.0.5) |
| **Queue** | Concentrations preserved | ✅ | Dict stored intact |
| **Queue** | Contact time preserved | ✅ | Float stored intact |
| **Execution** | sensorgram_time set | ✅ | Timeline position recorded |
| **Execution** | injection_time_by_channel set | ✅ | Detection populates dict |
| **Execution** | contact_time used | ✅ | Timer uses this value |
| **Export** | to_export_dict() | ✅ | All fields serialized |
| **Export** | Concentrations in Excel | ✅ | Dict → string representation |
| **Export** | Contact time in Excel | ⚠️ | Field exists but may not be in all export schemas |
| **Export** | Duration accuracy | ✅ | Uses `end_time_sensorgram - sensorgram_time` when available |

**Status:** All major validation gaps addressed in v2.0.5.

---

## Layer 6: Execution → Edits Tab Data Flow

### Overview
After cycles complete execution, data flows into the Edits tab for review and post-processing. **Two workflows exist:**

**Path A: INTENDED — Live Cycle-by-Cycle Population (⚠️ Currently Broken)**
```
Cycle completes (full duration OR user presses "Next Cycle" button)
  ↓
_cycle_completion() in _cycle_mixin.py (line 768)
  ↓
edits_tab.add_cycle(cycle_export_data)  ← ⚠️ METHOD DOESN'T EXIST
  ↓
Cycle should instantly appear as new row in Edits table
```

**Status:** Code calls non-existent method. Needs implementation of `add_cycle()` in EditsTab.

**Path B: CURRENT — Post-Recording Excel File Load (✅ Works)**
```
Execution → RecordingManager auto-save → Excel file
  ↓
User clicks "Open File" in Edits tab
  ↓
ExcelExporter.load_from_excel(filepath)
  ↓
_populate_cycles_table(cycles_data) loads ALL cycles at once
```

**Status:** ✅ Fully functional.

---

### Implementation Fix: Enhanced `add_cycle()` Method for Live Workflow

**Status:** ✅ **COMPLETED** (2026-02-18)

**Problem (Resolved):** The `add_cycle()` method existed but was incomplete — it added cycles to the table but didn't update metadata, filter dropdown, or auto-scroll to show new rows.

**Solution Implemented:**
Enhanced [_table_mixin.py](../../affilabs/tabs/edits/_table_mixin.py) lines 222-323 with:
- `_update_empty_state()` call to hide/show empty state message
- `_update_metadata_stats()` call to refresh cycle count, types, concentration range
- Filter dropdown update when new cycle types encountered
- `scrollToBottom()` to auto-scroll to newest cycle
- Counter reset in `_populate_cycles_table()` for clean state when loading Excel files

**Call Sites:**
- `mixins/_cycle_mixin.py` line 335 (when user presses "Next Cycle" button) ✅ Working
- `mixins/_cycle_mixin.py` line 768 (when cycle completes normally) ✅ Working

**Expected User Workflow (Now Functional):**
1. Start acquisition with 5 queued cycles
2. Cycle 1 executes for full duration (or user presses "⏭ Next Cycle" to complete early)
3. **Cycle 1 instantly appears as new row in Edits table** (while acquisition continues)
4. Cycle 2 starts automatically
5. Repeat — Edits table shows 1, 2, 3, 4, 5 cycles as they complete
6. User can review/edit/export cycles in real-time without stopping recording
7. Metadata stats update after each cycle (count, types, concentration range)
8. Table auto-scrolls to show newest cycle

**Implementation Details:**
```python
# affilabs/tabs/edits/_table_mixin.py (lines 222-323)

def add_cycle(self, cycle_dict):
    """Add a single completed cycle to the table (public API called by main.py).
    
    Called when a cycle completes during live acquisition.
    Enables real-time monitoring and editing without stopping recording.
    """
    # 1. Append to backend storage
    if not hasattr(self.main_window, '_loaded_cycles_data'):
        self.main_window._loaded_cycles_data = []
    self.main_window._loaded_cycles_data.append(cycle_dict)

    # 2. Track type counter (persists across calls)
    if not hasattr(self, '_cycle_type_counts'):
        self._cycle_type_counts = {}
    cycle_type = cycle_dict.get('type', 'Custom')
    if cycle_type not in self._cycle_type_counts:
        self._cycle_type_counts[cycle_type] = 0
    self._cycle_type_counts[cycle_type] += 1
    cycle_num = self._cycle_type_counts[cycle_type]

    # 3. Insert new row and populate all 5 columns
    row_idx = self.cycle_data_table.rowCount()
    self.cycle_data_table.insertRow(row_idx)
    
    # Col 0: Export checkbox
    self.cycle_data_table.setCellWidget(row_idx, 0, self._create_export_checkbox(row_idx, checked=True))
    self._cycle_export_selection[row_idx] = True
    
    # Col 1: Type (color-coded abbr + counter)
    abbr, color = CycleTypeStyle.get(cycle_type)
    type_item = QTableWidgetItem(f"{abbr} {cycle_num}")
    type_item.setForeground(QColor(color))
    type_item.setToolTip(f"{cycle_type} {cycle_num}")
    self.cycle_data_table.setItem(row_idx, self.TABLE_COL_TYPE, type_item)
    
    # Col 2: Time (duration @ start)
    # Col 3: Concentration
    # Col 4: ΔSPR (all 4 channels aggregated)
    # ... (full implementation as shown in source)
    
    # 4. Update UI state and metadata
    self._update_empty_state()  # Hide "No cycles loaded" message
    if hasattr(self, '_update_metadata_stats'):
        self._update_metadata_stats()  # Update cycle count, types, conc range
    
    # 5. Update filter dropdown if new cycle type encountered
    if hasattr(self, 'filter_combo'):
        current_types = [self.filter_combo.itemText(i) for i in range(self.filter_combo.count())]
        if cycle_type not in current_types:
            self.filter_combo.addItem(cycle_type)
    
    # 6. Auto-scroll to show newest cycle
    self.cycle_data_table.scrollToBottom()
    
    logger.info(f"✓ Added {cycle_type} {cycle_num} to cycle table (row {row_idx + 1})")
```

**Counter Reset on Excel Load:**
```python
# Added to _populate_cycles_table() line 69
self._cycle_type_counts = {}  # Reset live type counter (for add_cycle)
```
This ensures clean state when user loads an Excel file after live acquisition.

**Benefits (Now Delivered):**
- ✅ Real-time cycle monitoring during acquisition
- ✅ Live delta SPR display as cycles finish
- ✅ Edit/align/smooth cycles while acquisition continues
- ✅ Export partial results before completing full experiment
- ✅ Catch data quality issues early (abort if baseline unstable)
- ✅ Metadata stats auto-update (cycle count, types, concentration range)
- ✅ Filter dropdown stays in sync with new cycle types
- ✅ Auto-scroll shows newest cycle without user intervention

---


### A. Data Capture During Execution

**Location:** `affilabs/core/recording_manager.py` (lines 240-280)

**Flow:**
```
1. Acquisition loop: spectrum_acquired signal → record_data_point()
2. Data accumulates in data_collector.raw_data_rows (list of dicts)
3. Cycles complete → data_collector.cycles (list of dicts with runtime fields)
4. Stop button pressed → stop_recording()
5. Auto-save triggered → _save_to_file()
6. ExcelExporter.export_to_excel() writes multi-sheet workbook
```

**Data Captured:**
| Sheet Name | Source | Content |
|------------|--------|---------|
| **Raw Data** | `data_collector.raw_data_rows` | time, channel, value (wavelength nm) |
| **Channels XY** | `ExportHelpers.build_channels_xy_dataframe()` | Per-channel XY columns (Time A, SPR A, Time B, SPR B, etc.) |
| **Cycles** | `data_collector.cycles` | All cycle fields from domain model (type, duration, concentrations, delta_spr_by_channel, etc.) |
| **Flags** | `data_collector.flags` | Injection/wash/spike markers |
| **Events** | `data_collector.events` | System logs [(timestamp, description)] |
| **Metadata** | `data_collector.metadata` | Recording params (user, date, instrument, settings) |

---

### B. Loading File into Edits Tab

**Location:** `affilabs/ui_mixins/_edits_cycle_mixin.py` (lines 150-350)

**Trigger:** User clicks "Open File" button in Edits tab → File dialog → Selects .xlsx file

**Data Flow Diagram:**
```
┌──────────────────────────────────────────────────────────────────────┐
│                       EXCEL FILE (6 SHEETS)                          │
│  • Cycles sheet (N rows × 36 columns = cycle metadata)             │
│  • Channels XY sheet (M rows × 8 columns = raw XY time series)     │
│  • Raw Data, Flags, Events, Metadata sheets                         │
└──────────────────────────────────────────────────────────────────────┘
                                  ↓
              ExcelExporter.load_from_excel(filepath)
                                  ↓
┌──────────────────────────────────────────────────────────────────────┐
│                    PARSED DATA (in-memory dicts)                     │
│  • cycles: list[dict] (N cycle objects)                             │
│  • raw_data_rows: list[dict] (M time-series measurements)           │
│  • flags: list[dict], events: list[tuple], metadata: dict           │
└──────────────────────────────────────────────────────────────────────┘
                                  ↓
                      DATA STORAGE (3 locations)
                                  ↓
┌─────────────────────────────┬──────────────────────────────────────┐
│  main_window storage        │  edits_tab storage                   │
├─────────────────────────────┼──────────────────────────────────────┤
│ _loaded_cycles_data         │  _loaded_metadata                    │
│ (list of cycle dicts)       │  (experiment metadata dict)          │
│         ↓                   │         ↓                            │
│   Edits Table rows          │   Metadata panel display             │
│                             │                                      │
│ _loaded_raw_data_sheets     │  Timeline Graph data source          │
│ (dict of DataFrames)        │  Active View Graph data source       │
│   • 'Channels XY'           │                                      │
│   • 'Raw Data'              │                                      │
└─────────────────────────────┴──────────────────────────────────────┘
                                  ↓
                     recording_mgr.data_collector
                     (backend copy for re-export)
                          • raw_data_rows
                          • cycles
                          • flags, events, metadata
```

**Flow:**
```
1. ExcelExporter.load_from_excel(filepath) reads all sheets
2. Returns dict with keys: 'raw_data', 'cycles', 'flags', 'events', 'metadata'
3. Main window stores data:
     - _loaded_cycles_data = cycles (list of dicts)
     - _loaded_raw_data_sheets = {'Raw Data': df, 'Channels XY': df}
     - recording_mgr.data_collector.raw_data_rows = raw_data
     - recording_mgr.data_collector.cycles = cycles
     - recording_mgr.data_collector.metadata = metadata
4. edits_tab._populate_cycles_table(cycles) fills UI table
5. edits_tab._update_selection_view() renders graphs
```

**Critical State Variables:**
| Variable | Location | Purpose |
|----------|----------|---------|
| `main_window._loaded_cycles_data` | affilabs_core_ui.py | Cycle dicts for Edits table |
| `main_window._loaded_raw_data_sheets` | affilabs_core_ui.py | Raw XY data DataFrames |
| `recording_mgr.data_collector.cycles` | recording_manager.py | Backend copy for export |
| `edits_tab._loaded_metadata` | edits_tab.py | Metadata for display/re-export |
| `edits_tab._cycle_alignment` | edits_tab.py | Per-cycle alignment edits {row_idx: {'channel': str, 'shift': float}} |

---

### C. Edits Tab Data Display

**Location:** `affilabs/tabs/edits_tab.py` + 5 mixin files in `affilabs/tabs/edits/`

**UI Components:**

1. **Cycles Table** (QTableWidget)
   - Columns: Export ☑ | Type | Time | Concentration | ΔSPR
   - Data source: `main_window._loaded_cycles_data` (list of cycle dicts)
   - **Each row maps to exactly one executed cycle**
   - Export checkboxes control which cycles export to Excel
   - Populated via `_populate_cycles_table()` in `_table_mixin.py`

**Field Mapping: Cycle Domain Model → Edits Table**

| Table Column | Source Field(s) | Transformation | Example Display |
|--------------|----------------|----------------|-----------------|
| **Col 0: Export ☑** | `cycle.export_enabled` (default: True) | QCheckBox widget | ☑ (checked) |
| **Col 1: Type** | `cycle.type` | Color-coded abbreviation + counter per type | `BL 1` (Baseline 1) |
| **Col 2: Time** | `cycle.start_time_sensorgram` + `end_time_sensorgram` | `duration @ start` format | `5.2m @ 120s` |
| **Col 3: Concentration** | `cycle.concentration_value` | Direct string conversion | `100` (from 100 nM) |
| **Col 4: ΔSPR** | `cycle.delta_ch1`, `delta_ch2`, `delta_ch3`, `delta_ch4` OR `cycle.delta_spr_by_channel` | Channel:value pairs | `A:45 B:87 C:62` |

**Critical Details:**
- **Type column:** Uses `CycleTypeStyle.get(cycle_type)` → returns (abbreviation, color) tuple
  - Baseline → "BL" (blue)
  - Binding → "BD" (green)
  - Kinetic → "KN" (orange)
  - Regeneration → "RG" (red)
  - Counter increments per type: `BL 1`, `BL 2`, `BD 1`, `BD 2`...
  
- **Time column:** Shows **actual duration** (not planned duration from Method Builder)
  - Calculated from `end_time_sensorgram - start_time_sensorgram`
  - If missing, falls back to planned `duration_minutes`
  - Format: `{duration}m @ {start}s` or just `{duration}m` or `@ {start}s` depending on data availability
  
- **Concentration column:** Shows only the numeric value (unit stripped)
  - From `cycle.concentration_value` (deprecated) or parsed from `concentrations` dict
  
- **ΔSPR column:** Aggregates all 4 channels into one cell
  - Tries `delta_ch1`, `delta_ch2`, `delta_ch3`, `delta_ch4` fields first
  - Falls back to parsing `delta_spr_by_channel` dict
  - Shows only channels with valid numeric values
  - Format: `A:45 B:87` (no units, assumed nm or RU)

**⚠️ Data Integrity Note:** All 36 cycle fields are preserved in `_loaded_cycles_data` backend storage, but only 4 fields are visible in the table UI. Hidden fields (e.g., `flow_rate`, `contact_time`, `injection_method`) are preserved for Excel re-export but not displayed.

---

### Field Visibility Map: What Users See in Edits Tab

**Experiment-Level Metadata (Visible in Right Sidebar Panel):**

| Field | Display Location | Source | Format Example |
|-------|------------------|--------|----------------|
| **User/Operator** | Metadata panel | `metadata['operator']` or current user | "John Doe" |
| **Method Name** | Metadata panel | `metadata['method_name']` | "Kinetics Analysis v2" |
| **Recording Date** | Metadata panel | `metadata['recording_start']` | "2026-02-18 14:23" |
| **Device ID** | Metadata panel | `metadata['device_id']` | "P4PRO-001" |
| **Total Cycles** | Metadata panel | Computed from table rows | "15" |
| **Cycle Types** | Metadata panel | Computed from type column | "Baseline, Binding, Regeneration" |
| **Concentration Range** | Metadata panel | Computed from conc column | "1.00e-08 - 1.00e-05" |

**Per-Cycle Fields (Visible in Table — 4 Columns):**

| Field | Table Column | Derived From | Example Display |
|-------|--------------|--------------|-----------------|
| **Export checkbox** | Col 0 | `cycle.export_enabled` (default True) | ☑ |
| **Type** | Col 1 | `cycle.type` | "BL 1" (Baseline 1) |
| **Time** | Col 2 | `cycle.start_time_sensorgram` + `end_time_sensorgram` | "5.2m @ 120s" |
| **Concentration** | Col 3 | `cycle.concentration_value` | "100" |
| **ΔSPR** | Col 4 | `cycle.delta_ch1/2/3/4` or `delta_spr_by_channel` | "A:45 B:87 C:62" |

**Per-Cycle Fields (Hidden but Preserved — 31 Fields):**

| Field Category | Fields | Visibility | Re-Export Preserved? |
|----------------|--------|------------|---------------------|
| **Identifiers** | `cycle_id`, `cycle_num`, `name` | ❌ Hidden | ✅ Yes |
| **Timing (detailed)** | `duration_minutes`, `duration_seconds`, `sensorgram_time`, `end_time_sensorgram` | ⚠️ Partial (duration shown) | ✅ Yes |
| **Flow control** | `flow_rate`, `injection_volume`, `injection_method` | ❌ Hidden | ✅ Yes |
| **Contact time** | `contact_time` (seconds) | ❌ **Hidden — Not displayed anywhere** | ✅ Yes |
| **Concentrations (structured)** | `concentrations` (dict), `concentration_units` | ⚠️ Partial (value shown, unit stripped) | ✅ Yes |
| **Detection** | `detection_enabled`, `manual_mode` | ❌ Hidden | ✅ Yes |
| **Hardware** | `channels_active`, `partial_injection`, `overnight`, `led_adjustments` | ❌ Hidden | ✅ Yes |
| **Flags (structured)** | `flag_data` (list), `flags` (count) | ⚠️ Shown on graph, not in table | ✅ Yes |
| **Source tracking** | `source_method`, `status` | ❌ Hidden | ✅ Yes |
| **Notes** | `note`, `cycle_role` | ❌ Hidden | ✅ Yes |
| **Deprecated** | `concentration_value`, `concentration_units`, `delta_spr` | ⚠️ Partial (used for display) | ✅ Yes |
| **ΔSPR (per-channel)** | `delta_ch1`, `delta_ch2`, `delta_ch3`, `delta_ch4` | ⚠️ Aggregated in Col 4 | ✅ Yes |

**Key Findings:**
- ✅ **Experiment metadata:** 7 fields visible in sidebar
- ✅ **Per-cycle visible:** 4 fields in table + ΔSPR breakdown
- ⚠️ **Per-cycle hidden:** 31 fields preserved but not displayed
- 🔍 **Notable omissions from UI:**
  - **contact_time** — Critical for analysis but completely hidden
  - **flow_rate** — Important QC metric but hidden
  - **injection_method** — Helps distinguish manual vs automated
  - **source_method** — Which method template was used
  - **concentrations dict** — Multi-channel concentrations flattened to single value

**Design Rationale:** UI shows minimal fields for clean interface. Power users can access all fields by exporting to Excel and viewing the Cycles sheet.

---

**Raw Sensorgram Data Storage (Separate from Cycles Table):**

The Edits table shows cycle **metadata only** (one row per cycle). The actual time-series sensorgram data (XY data) is stored separately:

| Data Type | Storage Location | Purpose |
|-----------|------------------|---------|
| **Cycle metadata** | `main_window._loaded_cycles_data` (list of dicts) | Table rows (Type, Time, Conc, ΔSPR) |
| **Raw XY data (wide)** | `main_window._loaded_raw_data_sheets['Channels XY']` (DataFrame) | Timeline graph, Active view graph |
| **Raw XY data (long)** | `main_window._loaded_raw_data_sheets['Raw Data']` (DataFrame) | Backup/alternative format |
| **Cycle XY subsets** | Generated on-demand from `_loaded_raw_data_sheets` | Per-cycle sheets in export |

**How Cycles Link to XY Data:**
```python
# Cycle metadata contains time boundaries
cycle = {
    'start_time_sensorgram': 120.5,  # t=120.5 seconds from recording start
    'end_time_sensorgram': 420.8,    # t=420.8 seconds
    'type': 'Binding',
    'concentration_value': 100,
    # ... other fields
}

# XY data is filtered to this time window when exporting or graphing cycle
xy_subset = xy_data[(xy_data['Time_A'] >= 120.5) & (xy_data['Time_A'] <= 420.8)]
```

**Data Flow Summary:**
```
Acquisition → 1 cycle executed = 1 table row + XY data slice
             ↓
             Recording stops → Excel file (Cycles sheet + Channels XY sheet)
             ↓
             Load into Edits → Table shows cycle rows, graphs show XY data
             ↓
             User selects cycles → Export filters XY data to selected time windows
```

**Data Completeness Verification:**

| Acquired During Execution | Excel Cycles Sheet | Edits Table Display | Preserved for Re-Export |
|----------------------------|-------------------|---------------------|------------------------|
| cycle_id, cycle_num | ✅ | ❌ (hidden) | ✅ |
| type | ✅ | ✅ (Col 1: Type) | ✅ |
| name | ✅ | ❌ (hidden) | ✅ |
| duration_minutes | ✅ | ✅ (Col 2: Time) | ✅ |
| start_time_sensorgram | ✅ | ✅ (Col 2: Time) | ✅ |
| end_time_sensorgram | ✅ | ✅ (Col 2: Time) | ✅ |
| concentration_value | ✅ | ✅ (Col 3: Conc) | ✅ |
| concentration_units | ✅ | ❌ (stripped) | ✅ |
| concentrations | ✅ | ❌ (parsed to display) | ✅ |
| delta_spr_by_channel | ✅ | ✅ (Col 4: ΔSPR) | ✅ |
| delta_ch1, delta_ch2, etc | ✅ | ✅ (Col 4: ΔSPR) | ✅ |
| flow_rate | ✅ | ❌ (hidden) | ✅ |
| contact_time | ✅ | ❌ (hidden) | ✅ |
| injection_method | ✅ | ❌ (hidden) | ✅ |
| flag_data | ✅ | ❌ (shown on graph) | ✅ |
| All other 22 fields | ✅ | ❌ (hidden) | ✅ |
| **Raw XY data** | ✅ (Channels XY sheet) | ✅ (Timeline + Active graphs) | ✅ |

**Key Finding:** Zero data loss in Edits tab workflow. All 36 cycle fields + raw XY data are preserved in backend storage. UI shows only 4 cycle fields + 7 metadata fields for usability, but all 36 fields survive the round-trip when re-exporting.

**⚠️ Critical Hidden Field:** `contact_time` is completely hidden from UI despite being essential for analysis. Users must export to Excel to see this value. Consider adding to table or metadata panel in future versions.

2. **Timeline Graph** (Full sensorgram)
   - X-axis: Time (seconds)
   - Y-axis: SPR (nm) — all 4 channels overlaid
   - **Data source:** `_loaded_raw_data_sheets['Channels XY']` or `buffer_mgr.cycle_data`
   - Shows **entire recording** from t=0 to t=end
   - Cycle boundaries drawn as vertical shaded regions (from cycle.start_time → cycle.end_time)
   - Dual cursors (left/right) define selection window for active view

3. **Active Selection Graph** (Zoomed view between cursors)
   - Shows data only within cursor window
   - **Data source:** Filtered subset of `_loaded_raw_data_sheets['Channels XY']`
   - Supports per-cycle alignment (shift + channel filter)
   - Baseline correction enabled (wavelength[i] - wavelength[0])
   - Smoothing slider applies Savitzky-Golay filter (display-only, not saved)

4. **Metadata Panel** (Right sidebar)
   - **Displays:** User/Operator, Method Name, Recording Date, Device ID, Total Cycles, Cycle Types, Concentration Range
   - **Data source:** `edits_tab._loaded_metadata` (from Excel) or computed from `_loaded_cycles_data`
   - **Purpose:** Show experiment-level context (who, what, when, where)
   - **Note:** See "Field Visibility Map" section above for complete field breakdown

**Data Visibility Summary:**
- **Table:** Shows cycle metadata (4 visible columns × N cycles)
- **Timeline Graph:** Shows ALL sensorgram XY data (full recording timeline)
- **Active View Graph:** Shows FILTERED XY data (between cursor positions)
- **Metadata Panel:** Shows experiment-level metadata (7 fields: user, method, date, device, counts, ranges)

**User Editing Capabilities:**
- ☑ Toggle cycle export checkbox → `cycle.export_enabled = True/False`
- 🔄 Per-cycle alignment: Set time shift, filter by channel
- 📊 Delta SPR manual measurement: Lock cursors, read SPR difference
- 🏷️ Add/edit flags on graph
- ✂️ Cycle deletion (hides row, doesn't delete from file until re-exported)

---

### D. Data Mutations in Edits Tab

**User can modify:**
| Field | How | Impact on Export |
|-------|-----|------------------|
| **Export checkbox** | Click checkbox in table | Only checked cycles export |
| **Cycle time shift** | Alignment tools → shift slider | Modifies `cycle_alignment[row_idx]['shift']` |
| **Channel filter** | Alignment tools → channel dropdown | Modifies `cycle_alignment[row_idx]['channel']` |
| **Delta SPR value** | Manual cursor measurement | Updates `cycle.delta_spr_by_channel` in table |
| **Flags** | Graph annotation tools | Adds/removes from `cycle.flag_data` |
| **Cycle visibility** | Hide/show rows | Hidden cycles not exported |
| **Smoothing level** | Slider | Affects graph display only, not raw data |

**⚠️ Mutations are in-memory only** — Changes not saved until user clicks "Export" button

---

## Layer 7: Edits Tab → Excel Export

### Export Trigger Points

**Location:** `affilabs/tabs/edits/_export_mixin.py` (1467 lines)

Three export paths exist:

#### 1. **Export Selection** (Main workflow)
**Button:** "Export Selected Cycles" in Edits tab  
**Method:** `_export_selection()` (line 29)

**Flow:**
```
1. User selects cycles in table (highlights rows)
2. Clicks "Export Selected Cycles" button
3. File dialog: Choose save location (.xlsx)
4. Collect data from selected cycles:
     - Cycle metadata from _loaded_cycles_data[row]
     - Raw XY data filtered to cycle time window
     - Alignment settings from _cycle_alignment[row]
     - Flags from cycle.flag_data
5. Call _collect_channel_data_from_cycle(cycle, alignment_settings)
6. Build combined DataFrame with all selected cycles
7. Export to Excel using pandas ExcelWriter
```

**Export includes:**
- **Combined Sensorgram sheet:** All selected cycles merged into one timeline
- **Per-cycle sheets:** One sheet per cycle with alignment applied
- **Metadata sheet:** Recording info + edits applied

---

#### 2. **Export Table Data** (Full cycle metadata)
**Button:** "Export Table to Excel"  
**Method:** `_export_table_data()` (line 1190)

**Exports:** Cycles table as-is (Type, Time, Concentration, Delta SPR, Flags)  
**Use case:** Quick export for analysis in external software (GraphPad, Origin, Igor)

**Sheet structure:**
```
Cycle # | Type | Start (s) | End (s) | Duration (min) | Concentration | Delta SPR | Flags
```

---

#### 3. **Re-Export with Edits** (Overwrites original file)
**Button:** "Save" (when file was loaded from disk)  
**Method:** Writes back to `edits_tab._loaded_file_path`

**Flow:**
```
1. User loads Excel file into Edits
2. Makes edits (alignment, delta SPR, flag placement)
3. Clicks "Save" button
4. Original file overwritten with new data:
     - Raw data unchanged
     - Cycles sheet updated with edited values
     - New "Edits Applied" sheet added with change log
```

**⚠️ Warning dialog:** "Overwrite original file? This cannot be undone."

---

### Excel Export Schema

**Location:** `affilabs/services/excel_exporter.py` (lines 46-240)

**Method signature:**
```python
def export_to_excel(
    self,
    filepath: Path,
    raw_data_rows: list[dict],        # [{'time': 0.0, 'channel': 'a', 'value': 680.5}, ...]
    cycles: list[dict],                # [Cycle.to_export_dict(), ...]
    flags: list[dict],                 # [{'time': 120.5, 'type': 'injection', 'channel': 'A'}, ...]
    events: list[tuple],               # [(timestamp, "User pressed Stop"), ...]
    analysis_results: list[dict],      # Analysis tab measurements (unused in Edits export)
    metadata: dict,                    # {'user': 'John', 'date': '2026-02-18', 'instrument': 'P4PRO-001'}
    recording_start_time: float,       # Unix timestamp (t=0 reference for time column)
    alignment_data: dict | None,       # {row_idx: {'channel': str, 'shift': float}} from Edits tab
    channels_xy_dataframe = None       # Pre-built wide-format DataFrame (optional)
) -> None
```

---

### Sheet-by-Sheet Export Details

#### Sheet 1: Raw Data (Long Format)
**Columns:** time | channel | value
```
time (s)  | channel | value (nm)
----------|---------|------------
0.000     | a       | 680.123
0.500     | a       | 680.145
1.000     | a       | 680.178
0.000     | b       | 695.234
...
```

**Time column:** Elapsed seconds from recording start (original timestamp - recording_start_time)

---

#### Sheet 2: Channels XY (Wide Format)
**Columns:** Time A (s) | Channel A (nm) | Time B (s) | Channel B (nm) | Time C (s) | Channel C (nm) | Time D (s) | Channel D (nm)

**Purpose:** Ready for plotting in external software (GraphPad, Origin, Igor)

**Generation:**
- If `channels_xy_dataframe` provided → use it directly
- Else: Build from raw_data_rows by pivoting long → wide format

---

#### Sheet 3: Cycles
**Columns:** cycle_id | cycle_num | type | name | start_time_sensorgram | end_time_sensorgram | duration_minutes | concentrations_formatted | delta_spr_by_channel | flags | flag_data | contact_time | injection_method | source_method | [... all cycle fields ...]

**Key fields:**
- `concentrations_formatted`: String like "A:100.0, B:50.0" (human-readable)
- `delta_spr_by_channel`: Dict-as-string like "{'A': 45.2, 'B': 87.3}"
- `flag_data`: List-as-string like "[{'type': 'injection', 'time': 123.5, 'channel': 'A'}, ...]"

**Deduplication:** `ExportHelpers.deduplicate_cycles_dataframe()` removes duplicate cycle_id rows

---

#### Sheet 4: Flags
**Columns:** time | type | channel | confidence | is_reference

**Types:** injection | wash | spike

---

#### Sheet 5: Events
**Columns:** timestamp | event

**Examples:**
```
timestamp               | event
------------------------|--------------------------------
2026-02-18 14:23:01     | Recording started
2026-02-18 14:28:15     | Cycle 1 (Baseline) completed
2026-02-18 14:35:42     | Injection detected on channel A
2026-02-18 14:45:00     | Recording stopped
```

---

#### Sheet 6: Metadata
**Format:** Key-Value pairs (2 columns: Parameter | Value)

**Example:**
```
Parameter                | Value
-------------------------|---------------------------
User                     | John Doe
Recording Date           | 2026-02-18 14:23:01
Instrument               | P4PRO-001
Detector                 | Flame-T-12345
Firmware Version         | v2.4.1
Total Cycles             | 15
Total Duration (min)     | 120.5
Channels Active          | A, B, C, D
LED Intensities          | A:850, B:820, C:830, D:840
Smoothing Applied        | Level 5 (Edits tab)
Alignment Applied        | Yes (3 cycles shifted)
```

---

### Data Integrity Checkpoints

**Goal:** Ensure edits in Edits tab are preserved in Excel export

| Stage | Data Point | Preserved? | Notes |
|-------|------------|------------|-------|
| **Load** | Cycle type | ✅ | Parsed from Excel Cycles sheet |
| **Load** | Concentrations dict | ✅ | String → dict via ast.literal_eval |
| **Load** | Delta SPR by channel | ✅ | String → dict via ast.literal_eval |
| **Load** | Flag data | ✅ | String → list via ast.literal_eval |
| **Edit** | Cycle alignment (shift) | ✅ | Stored in _cycle_alignment, applied on export |
| **Edit** | Channel filter | ✅ | Stored in _cycle_alignment, applied on export |
| **Edit** | Delta SPR manual update | ✅ | Updated in _loaded_cycles_data, exported |
| **Edit** | Export checkbox toggle | ✅ | Only checked cycles exported |
| **Edit** | Smoothing level | ⚠️ | Display only, not exported to raw data |
| **Export** | Alignment applied flag | ✅ | Added to metadata sheet |
| **Export** | Source method name | ✅ | cycle.source_method column in Cycles sheet |
| **Export** | Contact time | ⚠️ | Field exists but may not be in all export schemas |

**Status:** Edits tab → Excel round-trip is ~95% lossless (smoothing is display-only, not persisted)

---

## Recommendations

### ✅ Completed (v2.0.6 — Live Edits Population Fix)

- ~~Implement `EditsTab.add_cycle()` method~~ — ✅ Enhanced existing method with UI updates, metadata refresh, filter dropdown sync, and auto-scroll. Live cycle-by-cycle population now works during acquisition.

### Remaining Improvements (Medium Priority)

1. **Expose critical hidden fields in Edits UI** — `contact_time`, `flow_rate`, `injection_method`, `source_method` are preserved but invisible. Add as optional table columns or metadata panel fields for power users.
2. **Export contact_time to Excel** — Add to Cycles sheet schema for complete data export
3. **Hard-block on contact_time >= cycle_duration** — Currently warning-only, should prevent cycle creation
4. **Spell-check cycle types** — Suggest corrections for typos like "Binidng" → "Binding"
5. **Concentration calculator UI** — Unit conversion tool for easy dilution calculations
6. **UI: Show source_method in queue table** — Group cycles by originating method name

### Future Enhancements (Low Priority)

6. **Template library** — Pre-populate common methods (kinetics, dose-response, etc.)
7. **Visual method builder** — Drag-drop cycles instead of text parsing
8. **Method validation score** — Overall quality metric (0-100%) based on detected issues
9. **Batch concentration editing** — Modify all cycles' concentrations in one operation
10. **Method comparison tool** — Diff two methods side-by-side
11. **Export method as template** — Save current queue as reusable template

### ✅ Completed (v2.0.5 — Validation improvements)

- ~~Re-number cycles on queue mutation~~ — ✅ Auto-renumbers after all mutations
- ~~Add unit whitelist~~ — ✅ 11 valid units enforced, invalid units flagged
- ~~Warn on detection=off + no manual mode~~ — ✅ Detection conflict check implemented
- ~~Duration limit validation~~ — ✅ Warns if > 60 minutes
- ~~Contact time vs duration check~~ — ✅ Warns if contact time > 90% of cycle duration
- ~~Mixed units detection~~ — ✅ Warns when units change mid-method
- ~~Empty concentration validation~~ — ✅ Detects `[Z:100nM]` type errors
- ~~Multi-injection validation~~ — ✅ Distinguishes parallel vs sequential, checks timing feasibility

### ✅ Completed (v1.4 — Layers 6-7 Complete Data Pipeline Documentation)

- ~~Document execution → Excel export flow~~ — ✅ Layer 6 documents RecordingManager, DataCollector, 6-sheet Excel schema
- ~~Document Edits tab data loading~~ — ✅ Layer 6 documents Excel → Edits tab with 3 data sources, state variables
- ~~Document Edits tab export flow~~ — ✅ Layer 7 documents re-export with 3 export paths, alignment data preservation
- ~~Excel sheet schema reference~~ — ✅ All 6 sheets documented (Raw Data, Channels XY, Cycles, Flags, Events, Metadata)
- ~~Data integrity checkpoints~~ — ✅ 13 checkpoint table shows which edits survive round-trip
- ~~Transformation documentation~~ — ✅ Time normalization, baseline correction, smoothing, alignment documented

### ✅ Completed (v1.3 — Layer 5 Queue Integration improvements)

- ~~Batch command for method push~~ — ✅ `AddMethodCommand` enables single-undo for entire method
- ~~Method metadata tracking~~ — ✅ `cycle.source_method` field stores originating method name
- ~~Auto-start action~~ — ✅ `action="start"` triggers immediate acquisition after queueing
- ~~Queue-level validation~~ — ✅ Defense-in-depth validation in `add_cycle()` catches duration/contact time issues
- ~~Mixed-method unit detection~~ — ✅ Warns when new cycles use different units than existing queue

---

## Related Documents

- **Data Output Audit Report:** `docs/architecture/DATA_OUTPUT_AUDIT_REPORT.md`
- **Manual Injection Data Flow Map:** `docs/architecture/MANUAL_INJECTION_DATA_FLOW_MAP.md`
- **Method Building Training Guide:** `docs/features/METHOD_BUILDING_TRAINING.md`
- **Cycle Domain Model:** `affilabs/domain/cycle.py`
- **Method Builder Dialog:** `affilabs/widgets/method_builder_dialog.py`

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-02-18 | Initial spec creation (v1.0) | AI Assistant |
| 2026-02-18 | Layer 3 simplified: deleted detection_sensitivity, clarified deprecated fields (v1.1) | AI Assistant |
| 2026-02-18 | Layer 1 updated: fixed UI tab description, Layer 5 fixed: corrected queue integration API, documented undo/redo support, updated recommendations (v1.2) | AI Assistant |
| 2026-02-18 | Layer 5 enhancements: AddMethodCommand batch undo, source_method field, auto-start implementation, queue-level validation, mixed-method detection (v1.3) | AI Assistant |

---

**END OF SPEC**
