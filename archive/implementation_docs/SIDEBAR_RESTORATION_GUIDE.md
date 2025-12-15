# Sidebar Content Restoration Guide

## COMPLETE MISSING CONTENT ANALYSIS

---

## TAB COMPARISON SUMMARY

| Tab | Lines in Original | Current Status | Missing Major Sections |
|-----|------------------|----------------|------------------------|
| Device Status | ~550 lines | Partial (~150 lines) | Operation Modes, Maintenance, Software Version |
| Graphic Control | ~850 lines | Partial (~200 lines) | Data Pipeline section, Channel/Marker selector, accessibility info text |
| Settings | ~400 lines | COMPLETELY MISSING | Entire tab (Spectroscopy graphs, Polarizer/LED settings) |
| Static | ~150 lines | Present (~100 lines) | Minor differences only |
| Flow | ~200 lines | Present (~150 lines) | Minor differences only |
| Export | ~50 lines | Present (~50 lines) | Debug button moved from Device Status |

**Total Original: ~2,200 lines | Current: ~650 lines | Missing: ~1,550 lines (70%)**

---

## DEVICE STATUS TAB - DETAILED RESTORATION

### ✅ Currently Present:
- Hardware Connected section (3 device labels)
- Scan button with emoji
- Subunit Status section (wrong names)

### ❌ COMPLETELY MISSING:

#### 1. **Operation Modes Section** (after Subunit Status)
```python
# "OPERATION MODES" header
operation_modes_section = QLabel("OPERATION MODES")
# Card with rgba(0,0,0,0.03) background
# Two modes: Static & Flow
self.operation_modes = {
    'static': {
        'indicator': QLabel("●"),  # circle
        'label': QLabel("Static"),
        'status_label': QLabel("Disabled")
    },
    'flow': {
        'indicator': QLabel("●"),
        'label': QLabel("Flow"),
        'status_label': QLabel("Disabled")
    }
}
```

#### 2. **Maintenance Section** (after Operation Modes)
```python
# "Maintenance" title (15px, 600 weight)
# Divider line (1px, rgba(0,0,0,0.1))
# Stats card:
self.hours_value = QLabel("1,247 hrs")
self.last_op_value = QLabel("Nov 19, 2025")
self.next_maintenance_value = QLabel("November 2025")  # Orange #FF9500
```

#### 3. **Debug Log Button Container** (after Maintenance)
- Needs card wrapper with rgba background
- Currently in Export tab, should be in Device Status

#### 4. **Software Version Label** (at bottom)
```python
version_label = QLabel("AffiLabs.core Beta")
# 11px, 600 weight, #86868B, centered
```

### 🔧 FIXES NEEDED:

#### Subunit Names (Line ~120 in sidebar.py)
**Current:**
```python
subunits = ['spectrometer', 'led_controller', 'polarizer', 'pump']
```
**Should be:**
```python
subunits = ['Sensor', 'Optics', 'Fluidics']
```

#### Missing Separators
Between each subunit item, add:
```python
separator = QFrame()
separator.setFrameShape(QFrame.HLine)
separator.setStyleSheet("background: rgba(0, 0, 0, 0.06); border: none;")
```

---

## GRAPHIC CONTROL TAB - DETAILED RESTORATION

### ✅ Currently Present:
- transmission_plot & raw_data_plot (pyqtgraph)
- Grid checkbox
- Auto/Manual radio buttons with min/max inputs
- Filter slider with method radios
- Reference combo
- Colorblind checkbox

### ❌ MISSING:

#### 1. **Data Pipeline Section** (after Data Filtering)
```python
# "Data Pipeline" header with divider
# Pipeline Selection Card (white background)
self.pipeline_method_group = QButtonGroup()
self.pipeline1_radio = QRadioButton("Pipeline 1")  # Checked
self.pipeline2_radio = QRadioButton("Pipeline 2")
# Connected to: self.on_pipeline_changed
```

#### 2. **Trace Style Options** (in Graphic Display card)
```python
# Channel selector combo
channel_combo = QComboBox()
channel_combo.addItems(["All", "A", "B", "C", "D"])

# Markers combo
marker_combo = QComboBox()
marker_combo.addItems(["Circle", "Triangle", "Square", "Star"])
```

#### 3. **Accessibility Info Text**
```python
colorblind_info = QLabel("Uses optimized colors for deuteranopia and protanopia")
# 11px, #86868B, italic, below colorblind checkbox
```

#### 4. **"Applied to cycle of interest" Note**
```python
display_note = QLabel("Applied to cycle of interest")
# 11px, #86868B, italic, under "Graphic Display" header
```

---

## SETTINGS TAB - COMPLETELY MISSING!!

### ❌ ENTIRE TAB NEEDS RESTORATION:

This tab is **NOT** the same as "Graphic Control". The Settings tab contains:

#### Section 1: Spectroscopy
- Toggle buttons: Transmission / Raw Data (segmented control)
- **transmission_plot** (PlotWidget with 4 channel curves)
- **raw_data_plot** (PlotWidget, hidden by default)
- Switch visibility with: `self._on_spectroscopy_toggle`

#### Section 2: Polarizer and LED Settings
```python
# Polarizer Positions
self.s_position_input = QLineEdit()  # S: 0-255
self.p_position_input = QLineEdit()  # P: 0-255
self.polarizer_toggle_btn = QPushButton("Position: S")  # 100px wide, 28px tall

# LED Channel Intensity (A, B, C, D)
self.channel_a_input = QLineEdit()  # 0-4095
self.channel_b_input = QLineEdit()
self.channel_c_input = QLineEdit()
self.channel_d_input = QLineEdit()

# Apply Settings button
self.apply_settings_btn = QPushButton("Apply Settings")  # Green #34C759

# Calibration buttons
self.simple_calibration_btn = QPushButton("Simple Calibration")
self.full_calibration_btn = QPushButton("Full Calibration")
self.oem_calibration_btn = QPushButton("OEM Calibration")
```

**NOTE:** Current sidebar.py has some of this in "Flow" tab, but original had dedicated "Settings" tab.

---

## TAB STYLING RESTORATION

### Current (WRONG):
```python
QTabBar::tab {
    min-height: 95px;
    min-width: 140px;
    border-right: 3px solid #007AFF;  # Wrong - too thick
}
```

### Original (CORRECT):
```python
QTabBar::tab {
    background: transparent;
    color: #86868B;
    border: none;
    padding: 8px 20px;
    margin: 2px 0;
    font-size: 13px;
    font-weight: 500;
    min-height: 32px;  # Much more compact!
    border-radius: 6px;
}
QTabBar::tab:selected {
    background: #FFFFFF;
    color: #1D1D1F;
}
```

---

## RESTORATION PRIORITY

### Phase 1: CRITICAL (Device Status fixes) ✅ COMPLETE
1. ✅ Fix tab styling (32px height, proper selected state) - DONE
2. ✅ Fix subunit names (Sensor/Optics/Fluidics) - DONE
3. ✅ Add Operation Modes section - DONE
4. ✅ Add Maintenance section with stats - DONE
5. ✅ Add Software Version label - DONE
6. ✅ Move Debug Log button from Export to Device Status with card wrapper - DONE

**Phase 1 Results:**
- Tab styling restored to compact 32px design with rounded corners
- Device Status tab now complete with all 4 major sections
- Subunit indicators use correct domain names (Sensor/Optics/Fluidics)
- Separators added between subunit items
- Operation Modes section tracks Static/Flow availability
- Maintenance section displays operation hours, last operation, maintenance due date
- Debug Log button moved to Device Status in styled card container
- Software version label added at bottom
- sidebar.py increased from 442 → 550 lines

### Phase 2: IMPORTANT (Graphic Control additions) ✅ COMPLETE
1. ✅ Add Data Pipeline section with Pipeline 1/2 radios - DONE
2. ✅ Add Channel/Marker selector combos - DONE
3. ✅ Add accessibility info text - DONE
4. ✅ Add "Applied to cycle of interest" note - DONE
5. ✅ Reorganize Reference section with proper info text - DONE

**Phase 2 Results:**
- Data Pipeline section added with Pipeline 1/2 radio selection
- Graphic Display section now has Channel (All/A/B/C/D) selector
- Graphic Display section now has Marker (Circle/Triangle/Square/Star) selector
- "Applied to cycle of interest" note added below section header
- Visual Accessibility section properly structured with colorblind checkbox
- Accessibility info text: "Uses optimized colors for deuteranopia and protanopia"
- Reference section properly formatted with combo and info text
- sidebar.py increased from 550 → 678 lines

### Phase 3: MAJOR (Settings tab restoration) - SKIPPED FOR NOW
**Note:** Original Settings tab had:
1. Spectroscopy section (Transmission/Raw Data plot toggle)
2. Polarizer and LED Settings section

**Current structure:**
- Settings tab: Minimal auto/manual radios + min/max inputs
- Flow tab: Has polarizer/LED settings (different from original)

**Decision:** Keep current structure for now. Flow tab serves the same purpose as original Settings tab's polarizer section. Settings tab can be enhanced later if needed.

### Phase 3: MAJOR (Settings tab restoration)
1. ✅ Create complete Settings tab with Spectroscopy section
2. ✅ Add Polarizer/LED settings section
3. ✅ Wire up all signal connections

### Phase 4: POLISH
1. Review Static/Flow tabs for minor differences
2. Apply SF Pro font specifications throughout
3. Verify all rgba color codes match original

---

## ESTIMATED EFFORT

- Phase 1: ~200 lines to add
- Phase 2: ~150 lines to add
- Phase 3: ~400 lines to add (entire tab)
- Phase 4: ~50 lines of refinements

**Total: ~800 lines to restore (from current 650 → target 1,450)**
