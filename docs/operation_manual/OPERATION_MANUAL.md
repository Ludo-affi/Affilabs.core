# AffiLabs.core v2.0 - Operation Manual

**Software Version:** 2.0
**Release Date:** January 30, 2026
**Status:** Release
**Device:** FLMT09788 (Flame-T Spectrometer)

---

## Table of Contents

1. [Quick Start Guide](#quick-start-guide)
2. [System Overview](#system-overview)
3. [Software Purpose & Scope](#software-purpose--scope)
4. [Getting to Auto-Read Section](#getting-to-auto-read-section)
4. [Creating a Method](#creating-a-method)
5. [Recording an Experiment](#recording-an-experiment)
6. [Editing & Analyzing Data](#editing--analyzing-data)
7. [Data Export Formats](#data-export-formats)
8. [Manual Operation](#manual-operation)
   - [Sensor Installation (P4PRO & P4SPR 2.0)](#sensor-installation-p4pro--p4spr-20)
   - [Channel Addressing & Volume Guidelines](#channel-addressing--volume-guidelines)
   - [Manual Pump Control](#manual-pump-control)
9. [User Management](#user-management)
   - [Creating User Profiles](#creating-user-profiles)
   - [User Progression System](#user-progression-system)
   - [Switching Between Users](#switching-between-users)
10. [Maintenance](#maintenance)
11. [Software Compatibility](#software-compatibility)

---

## ⚠️ CRITICAL SENSOR HANDLING DISCLAIMER

### Sensor Specifications & Liability

**Affinité Sensors:**
- **Surface**: Gold sensor layer (extremely delicate)
- **Windows**: Two glass windows on long end for optical access
- **Value**: High-cost precision component
- **Damage**: Irreversible if surface is contaminated or touched

### ⚠️ MANDATORY HANDLING PROTOCOL

**FAILURE TO FOLLOW THESE RULES WILL DAMAGE THE SENSOR:**

1. **ALWAYS wear nitrile gloves** when handling sensor
   - Never touch sensor with bare hands
   - Hand oils permanently damage gold surface
   - Damaged sensor cannot be recovered

2. **NEVER touch the sensor surface** with:
   - Fingers, hands, or bare skin
   - Tissues, wipes, or paper
   - Any cleaning materials (unless pre-approved by manufacturer)
   - Pipette tips or other instruments

3. **Golden surface care**:
   - Surface chemistry is delicate
   - Any contact = irreversible damage
   - Results in erratic signal, failed experiments, unusable sensor

4. **Glass window care**:
   - Handle by edges only
   - Never touch optical surfaces
   - Dust on windows causes signal degradation

### Sensor Cleaning (Dust/Debris Removal)

**For light dust contamination ONLY:**
- Use **nitrogen gas** (N₂) to blow away dust particles
- Hold sensor at safe distance (avoid pressure damage)
- Use in fume hood or clean area to prevent re-contamination
- **DO NOT use compressed air** (contains moisture/oil contaminants)
- **DO NOT use solvents** unless pre-approved by Affinité
- **DO NOT attempt to wipe or scrub** the sensor surface

**Chemical surface damage cannot be cleaned** - if surface chemistry is damaged, sensor is lost.

### Sensor Reuse & Storage

**Sensors CAN be reused** under strict conditions:

1. **Storage Requirements:**
   - **Must be refrigerated** (2-8°C) between uses
   - **Must be kept hydrated** - store in appropriate buffer solution
   - **Must be in sealed container** to prevent evaporation
   - Duration: Up to 1-2 weeks if stored properly

2. **Performance Degradation Notice:**
   - **Performance decreases with each use** - this is expected
   - First use = best performance
   - Second use = measurable performance reduction
   - Third+ use = significant signal loss likely
   - Surface chemistry degrades with repeated exposure

3. **Recommendations:**
   - **Always use NEW sensors for critical/important experiments**
   - Only reuse sensors for:
     - Preliminary/screening experiments
     - Method development
     - Non-critical measurements
   - Keep detailed records of sensor usage history

### Liability Statement - Sensor Reuse

**AffiLabs is NOT responsible for:**
- Sensor damage from hand contact
- Damage from improper cleaning or wiping
- Contamination from tissue contact
- Signal degradation from surface chemistry damage
- Loss of sensor functionality due to user mishandling
- **Performance loss after first use** (sensor reuse degradation is expected)
- **Poor results from reused sensors** (new sensors strongly recommended for critical experiments)
- Sensor degradation from improper storage during reuse
- Data quality issues due to using degraded reused sensors

**User assumes full responsibility** for:
- Proper sensor handling per this manual
- Understanding sensor reuse degrades performance
- Using new sensors for important experiments
- Proper refrigerated storage if choosing to reuse sensors
- Maintaining sensor hydration during storage

---

## Quick Start Guide

### First Time Setup

**⚠️ Power Requirements (CRITICAL)**

Before starting, ensure your system is properly powered:
- **P4SPR**: USB powered only - just connect to computer USB port
- **P4PRO**: Must have Affinité's 24V power bar connected (NOT generic supplies)
- **Affi Pump** (if equipped): Must have Affinité's 24V power bar connected
- Do NOT proceed if using incorrect power supply - contact Affinité if needed

**Steps:**

1. **Connect Power**
   - P4SPR: Connect USB 3.0+ cable to computer
   - P4PRO/Pump: Connect Affinité's 24V power bar (verify label shows "Affinité")
   - Allow 30 seconds for power stabilization

2. **Launch the application**
   - Double-click `AffiLabs.core v2.0`
   - Wait for hardware initialization (30-60 seconds)
   - Status indicator changes from "Searching..." to "Connected"

3. **Select User Profile**
   - Choose your name from the user dropdown in the Export tab
   - This tracks who ran each experiment

4. **Power On Device**
   - Click **Power On** button (top left)
   - LED indicators illuminate
   - Spectrometer initializes

4. **Create Your First Method**
   - Go to **Live tab** → Method Builder (sidebar)
   - Add baseline cycle → concentration cycles → regeneration
   - Click **Save Method**

5. **Start Recording**
   - Click **Start Run** button
   - Data streams in real-time on the graph
   - Cycles execute automatically

---

## System Overview

### Hardware Components

| Component | Model | Serial | Status |
|-----------|-------|--------|--------|
| Spectrometer | Flame-T | FLMT09788 | ✓ Ready |
| LED PCB | Luminus Cool White | — | ✓ Ready |
| Controller | Raspberry Pi Pico P4SPR | V2.4 | ✓ Ready |
| Servo Motor | HS-55MG | — | ✓ Ready |
| Optical Fiber | 200 μm diameter | — | ✓ Ready |

### Power Requirements

**⚠️ CRITICAL: Use only Affinité-provided power supplies. Incorrect power can damage the system.**

| Device | Power Source | Voltage | Notes |
|--------|--------------|---------|-------|
| **P4SPR** | USB Port | 5V (USB) | **No external power needed** - USB powered only from computer |
| **P4PRO** | External Power Supply | **24V DC** | **MUST use Affinité's provided 24V power bar** - Do NOT use alternative supplies |
| **Affi Pump** | External Power Supply | **24V DC** | **MUST use Affinité's provided 24V power bar** - Do NOT use alternative supplies |

**Safety Requirements:**
- **P4SPR**: Connect via USB 3.0+ port on computer - no additional power required
- **P4PRO & Affi Pump**: ALWAYS use Affinité's certified 24V power bars
- Do NOT use generic 24V supplies - they may have incorrect polarity or voltage regulation
- Check power bar connectors regularly for damage or corrosion
- Keep power cables away from water and heat sources
- If power supply shows signs of damage: STOP using it immediately and contact Affinité for replacement

### Environmental Operating Conditions

**Flame-T Spectrometer (Ocean Insight):**

| Condition | Specification | Notes |
|-----------|---------------|-------|
| **Operating Temperature** | -30°C to +70°C | Detector and electronics rated for this range |
| **Storage Temperature** | 0°C to +50°C | Long-term storage conditions |
| **Optimal Operating Range** | 15°C to 25°C | Best performance and stability |
| **Humidity** | 10% to 90% (non-condensing) | Avoid moisture condensation |

**Important:**
- Temperature fluctuations can affect baseline stability and signal quality
- Allow 30 minutes warm-up time if instrument is operated below 10°C
- Keep device away from direct sunlight and heat sources
- In cold environments (< 5°C), warm the device before operation
- In hot environments (> 45°C), ensure adequate ventilation to prevent overheating

### Software Architecture

**Two-Phase Workflow:**

| Phase | Tab | Function | Output |
|-------|-----|----------|--------|
| **Capture** | Live | Record raw sensor data in real-time | Raw Excel file |
| **Analysis** | Edit | Process, measure, validate, annotate | Analysis Excel file |

---

## Software Purpose & Scope

### What Affilabs.core Does

**Affilabs.core v2.0** is a specialized software for **high-quality data acquisition and annotation** on the P4SPR surface plasmon resonance system.

**Core Functions:**
1. **Acquire high-quality sensor data** - Real-time streaming from Flame-T spectrometer (4 independent channels: A, B, C, D)
2. **Execute experimental protocols** - Run predefined method sequences (baseline → concentration → regeneration → wash cycles)
3. **Annotate during acquisition** - Add flags, notes, and markers in real-time to document events
4. **Enable basic data editing** - Measure binding response (Δ-SPR), align cycles, validate quality
5. **Export publication-ready data** - Create Excel files compatible with external analysis software

### What Affilabs.core Does NOT Do

Affilabs.core intentionally focuses on data capture and annotation. Advanced analysis is delegated to specialized tools:

- ❌ **Curve fitting** (use Excel, Origin, Prism, TraceDrawer, or Affilabs.analysis)
- ❌ **Kinetic modeling** (use specialized kinetics software)
- ❌ **Statistical analysis** (use R, Python, Prism, or GraphPad)
- ❌ **Advanced image processing** (use external visualization tools)

### Design Philosophy: Separation of Concerns

Affilabs.core follows a **three-phase workflow**:

```
┌─────────────────────────────────────────────────────┐
│  PHASE 1: CAPTURE (Live Tab)                        │
│  ─ Acquire raw sensor data                          │
│  ─ Execute method queue                             │
│  ─ Real-time visualization & monitoring             │
│  ─ Add labels, flags, notes                         │
│  → OUTPUT: Raw_YYYYMMDD_HHMMSS.xlsx                 │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  PHASE 2: ANNOTATION (Edit Tab)                     │
│  ─ Load raw data or previous analysis               │
│  ─ Measure binding response (Δ-SPR) using cursors   │
│  ─ Align cycles for comparison                      │
│  ─ Validate data quality (QC pass/fail)             │
│  ─ Enrich with metadata                             │
│  → OUTPUT: Analysis_YYYYMMDD_HHMMSS.xlsx            │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  PHASE 3: ANALYSIS (External Software)              │
│  ─ Copy Δ-SPR values to Excel / Origin / Prism      │
│  ─ Perform curve fitting & Kd calculation           │
│  ─ Generate publication figures                     │
│  ─ Use Affilabs.analysis for advanced workflows     │
│  → OUTPUT: Final reports, publications              │
└─────────────────────────────────────────────────────┘
```

**Key Principle:** Raw data is **immutable** - once captured, it is never modified. All analysis is performed on copies, preserving data integrity for audit trails and reproducibility.

### Multi-Channel Operation

Affilabs.core manages **four independent channels** (A, B, C, D) on the P4SPR system:

- **Individual control**: Each channel can be injected independently via dedicated ports
- **Simultaneous measurement**: All channels sampled in parallel during experiments
- **Flexible addressing**: Inject into 1 channel, 2 channels, 3 channels, or all 4 simultaneously
- **Per-channel annotation**: Δ-SPR, flags, and notes tracked separately per channel
- **Reference channel capability**: Optionally subtract one channel from others for background correction

### Method-Based Workflow

Experiments are controlled through **Methods** - predefined sequences of cycles:

- **Method Builder** in Live tab: Create custom methods for your specific assays
- **Affinité templates**: Pre-built methods for common binding assays (affinity, kinetics, screening)
- **Save & reuse**: Methods persist across sessions - load once, run multiple times
- **Cycle types**: Baseline, Concentration, Regeneration, Wash (customizable)
- **Personalized parameters**: Set incubation times, volumes, analyte concentrations per cycle

### GLP/GMP Compliance Focus

Data is organized and tracked for regulatory environments:

- **Per-experiment folders**: One folder per measurement session with date, operator, device info
- **Hierarchical structure**: Raw_Data, Analysis, Figures, Methods, QC_Reports
- **Audit trail**: Every file creation, modification, and action timestamped
- **Metadata tracking**: Device ID, sensor type, software version, operator name, experimental parameters
- **Immutable raw data**: Source of truth cannot be altered after capture

### User & Team Organization

- **Per-user experiments**: Each user has separate data folders and method libraries
- **Operator tracking**: Every experiment records who ran it and when
- **Repeatable workflows**: Save methods once, reuse across experiments
- **Shared methods**: Affinité-provided templates available to all users
- **Data traceability**: Complete audit trail for compliance and troubleshooting

### Integration with Affilabs.analysis

For users needing advanced analysis capabilities:

- **Affilabs.analysis** is a separate, complementary software suite
- **Seamless import**: Load Affilabs.core Excel exports directly into analysis software
- **Extended kinetics**: Advanced curve fitting, Kd calculation, kinetic analysis
- **Statistical tools**: Batch processing, comparison across experiments, data visualization
- **Publication workflow**: Automated report generation with figures

### Scope Boundaries

| Task | Tool | Notes |
|------|------|-------|
| Acquire SPR data | **Affilabs.core** | Real-time sensor acquisition |
| Annotate cycles | **Affilabs.core** | Add flags, notes, Δ-SPR measurements |
| Basic export | **Affilabs.core** | Excel with all raw data + annotations |
| Curve fitting | External tool or **Affilabs.analysis** | Not included in core |
| Kinetic analysis | **Affilabs.analysis** | Advanced workflow for kinetics |
| Statistical tests | Excel, R, Prism, Python | Affilabs.core provides data only |
| Figure generation | Origin, Prism, Python, Matplotlib | Export data, create figures externally |

---

## Getting to Auto-Read Section

The **Auto-Read feature** allows automatic baseline acquisition without manual cycle entry.

### Steps to Access Auto-Read

1. **Navigate to Live Tab**
   - Click "Live" in the main tabs
   - Right sidebar shows "Method Builder"

2. **Auto-Read Controls** (in Method Builder)
   - Find "Auto-Read Baseline" section
   - Set **duration** (minutes): e.g., 5 minutes
   - Click **Add Auto-Read Cycle**

3. **Configuration Options**
   - **Duration**: Length of baseline acquisition
   - **Channels**: Select which channels to monitor (A, B, C, D)
   - **Reference Channel** (if enabled): Automatic subtraction

4. **Start Auto-Read**
   - Adjust sensor on chip surface
   - Click **Start Run**
   - Software automatically records baseline
   - Progress shown on timeline graph

### Auto-Read Typical Duration

- **Baseline Stabilization**: 3-5 minutes
- **Quality Check**: 2-3 minutes
- **Total**: 5-8 minutes before concentration injection

---

## Creating a Method

A **Method** is a predefined sequence of cycles (baseline → concentration → regeneration → wash).

### Method Builder Interface

**Location:** Live Tab → Right Sidebar → "Method Builder"

### Step-by-Step Method Creation

#### 1. Add a Baseline Cycle

```
Cycle Type:     Baseline
Duration (min): 5
Temperature:    25°C
```

- Click **Add Baseline**
- Adjust duration if needed
- Baseline stabilizes sensor before experiment

#### 2. Add Concentration Cycles

```
Cycle Type:        Concentration
Concentration:     100 nM (or custom)
Units:            nM / µM / mg/mL / %
Duration (min):    10
Volume (µL):       200
```

- Click **Add Concentration**
- Enter analyte concentration value
- Select units (nM, µM, mg/mL, %)
- **Duration**: Fixed incubation time (typically 5-10 minutes)
  - Longer duration = approach to equilibrium
  - Shorter duration = kinetic snapshot
- **Volume**: 150-300 µL per channel injection

**Add multiple concentrations for affinity mapping:**
- 1 nM (10 min incubation) → lowest affinity point
- 10 nM (10 min incubation) → mid-range
- 100 nM (10 min incubation) → high concentration
- 1000 nM (10 min incubation) → saturation

Each concentration measured at **same timepoint** (10 min) to estimate Kd (dissociation constant)

#### 3. Add Regeneration Cycle

```
Cycle Type:     Regeneration
Duration (min): 3-5
Regenerant:     0.1 M NaOH (or custom note)
```

- Click **Add Regeneration**
- Clears surface for next cycle
- Duration: 3-5 minutes

#### 4. Add Wash Cycle (Optional)

```
Cycle Type:     Wash
Duration (min): 2-3
Buffer:         Running Buffer
```

- Stabilizes sensor after regeneration
- Before next concentration cycle

### Complete Method Example - Affinity Measurement

This example measures binding affinity across a concentration range using fixed incubation time:

| Cycle # | Type | Duration | Concentration | Volume | Notes |
|---------|------|----------|---|---|---|
| 1 | Baseline | 5 min | — | — | Initial sensor stabilization |
| 2 | Concentration | 10 min | 1 nM | 200 µL | Low affinity point |
| 3 | Regeneration | 3 min | — | 500 µL | Surface cleaning |
| 4 | Wash | 2 min | — | — | Buffer stabilization |
| 5 | Concentration | 10 min | 10 nM | 200 µL | Mid-range affinity |
| 6 | Regeneration | 3 min | — | 500 µL | Surface cleaning |
| 7 | Wash | 2 min | — | — | Buffer stabilization |
| 8 | Concentration | 10 min | 100 nM | 200 µL | Higher affinity |
| 9 | Regeneration | 3 min | — | 500 µL | Surface cleaning |

**Result**: Three Δ-SPR measurements at same incubation time (10 min) across 3 concentrations → Kd estimation

### Save the Method

1. **Enter Method Name**
   - Click **Save Method**
   - Name: e.g., "Antibody_Binding_Assay"

2. **Method Location**
   - Automatically saved to: `Documents/Affilabs Methods/[YourName]/`
   - File format: `.json`

3. **Load Existing Method**
   - Click **Load Method**
   - Select from list of previously saved methods
   - Method queues automatically

---

## Recording an Experiment

### Pre-Recording Checklist

- [ ] **⚠️ SENSOR HANDLING: Gloves worn during any sensor contact**
- [ ] **⚠️ SENSOR SURFACE: Not touched, cleaned, or wiped (ever)**
- [ ] Device powered on (green status light)
- [ ] Method selected or created (with correct incubation times & concentrations)
- [ ] Sensor chip installed on instrument (by edges only, gloved hands)
- [ ] **Buffer flowing smoothly** (no air bubbles visible in tubing)
- [ ] **Baseline stable on graph** (drift < 0.5 nm/min)
- [ ] **⚠️ CRITICAL: Syringes primed and FREE of air bubbles** (major issue!)
- [ ] User profile selected (Export tab)
- [ ] Ports accessible for each channel (A, B, C, D) to be used
- [ ] Analyte solutions prepared at correct concentrations
- [ ] Wash solution (regenerant) available in reservoir
- [ ] Note: This is **affinity measurement** (fixed timepoint), not kinetic monitoring

### ⚠️ Critical: Air Bubble Prevention

**Air bubbles are the single biggest problem with the P4SPR system.** They cause:
- Data loss during critical measurements
- Sensor damage
- System blockages
- Failed experiments

**Prevention:**
1. **Before injection**: Inspect syringe visually - NO air bubbles allowed
2. **Prime the line**: Run buffer through pump at moderate speed to clear any trapped air
3. **During measurement**: Watch for air pocket formation in tubing
4. **If air enters**: Use **pulse injections** to force air out of the system
   - Small volume (50-100 µL) rapid injections
   - Repeat until air is cleared
   - Resume normal operation

### Starting a Recording

1. **Click "Start Run"** (top toolbar)
   - Queue begins executing
   - Green "Recording" indicator appears
   - Timeline graph shows data acquisition

2. **Real-Time Monitoring**
   - Watch sensorgram on "Live" graph
   - Four channels visible (A, B, C, D)
   - Red/green shift indicates binding events

3. **Add Flags** (Optional, During Run)
   - Right-click on graph at injection point
   - Select flag type: **▲ Injection**, **■ Wash**, **◆ Spike**
   - Timestamp automatically recorded

4. **Add Notes** (Optional, Per Cycle)
   - Enter text in "Cycle Notes" field
   - Saved with cycle metadata
   - Visible in Edit tab later

5. **Pause/Resume**
   - **Pause** button: Temporarily stop acquisition
   - **Resume** button: Continue from pause
   - Use for buffer exchanges or troubleshooting

### Stop Recording

1. **Click "Stop Run"** when experiment complete
2. **Data Automatically Saved** to Live tab cycle queue
3. **Ready to Export** raw data to Excel

---

## Editing & Analyzing Data

The **Edit Tab** is where you measure, validate, and prepare final results.

### Loading Data into Edit Tab

#### Option 1: Load Raw Data File

1. Go to **Edit Tab**
2. Click **Load Data**
3. Select raw Excel file from:
   - `Documents/Affilabs_Data/[ExperimentName]/Raw_Data/`
4. Cycles populate automatically in table

#### Option 2: From Live Tab Export

1. In Live tab, click **Save Raw Data**
2. Choose save location (defaults to experiment folder)
3. Switch to Edit tab
4. Click **Load Data** → select same file

### Cycle Analysis Table

**Columns:**
| Column | Description | Editable |
|--------|-------------|----------|
| Type | Cycle type (BL, CN, RG, WS) | No |
| Time | Start time & duration | No |
| Conc | Concentration value | No |
| ΔSPR | Delta SPR (A:val B:val...) | Yes (via cursors) |
| Flags | Event markers (▲■◆) | Yes |
| Notes | User annotations | Yes |

### Measuring Delta SPR (Δ-SPR)

**Δ-SPR** = Change in wavelength shift during incubation = **Binding Response at Fixed Timepoint**

**Important**: In P4SPR affinity measurement, you measure the binding response at a **fixed incubation time** (e.g., all at 10 minutes), not the binding kinetics over time.

#### Manual Measurement with Cursors

1. **Select a concentration cycle** in the table
2. **Place cursors** on sensorgram:
   - **Left cursor** (green): Start of incubation (injection point)
   - **Right cursor** (red): End of incubation (at fixed timepoint, typically 10 min)
3. **Value updates in real-time**:
   - Channel A, B, C, D Δ-SPR values calculated
   - Displayed in ΔSPR bar chart (colored bars)
   - **This is your binding affinity measurement at this concentration**
4. **Auto-saves** to selected cycle

#### Cursor Tips for Affinity Measurement

- Position left cursor at injection start (baseline level)
- Position right cursor at **same time offset for all concentration cycles** (e.g., always at 10 min)
- This ensures fair comparison across concentrations
- Bar chart shows delta for all 4 channels simultaneously
- Use consistent timepoint for all cycles → build affinity curve

#### Building an Affinity Curve

After measuring Δ-SPR for each concentration at same timepoint:
1. Extract Δ-SPR values: [1 nM: 25, 10 nM: 45, 100 nM: 65, 1000 nM: 75]
2. Plot concentration vs. Δ-SPR in external software (Prism, Origin)
3. Fit to binding curve (e.g., Langmuir isotherm) to estimate **Kd**

### Alignment & Time Shift

**Use when:** Cycles need time-axis adjustment for overlay comparison

1. **Select Alignment Tab**
2. **Drag slider** for time shift
   - Real-time updates to graph
   - No "Apply" button needed
3. **Adjustment saved** to cycle metadata

### Validation & QC

1. **Mark Cycles** as Pass/Fail/Review
   - Right-click cycle → QC Status
   - Filters visible cycles based on status

2. **Flag Low-Quality Data**
   - Noisy baseline
   - Incomplete binding
   - Sensor drift

3. **Add QC Notes**
   - Explain why marked as fail
   - Reference to raw data issues

### Data Enrichment

**Metadata Panel Shows:**
- **Date**: Experiment date & time
- **User**: Who ran the experiment
- **Device**: Hardware serial (FLMT09788)
- **Cycles**: Total count
- **Conc. Range**: Min-Max analyte concentration
- **Sensor**: Chip type (optional user entry)

---

## Data Export Formats

### Raw Data Export (from Live Tab)

**When to Use:** Preserve original sensor data for re-analysis
**Format:** Excel (.xlsx)
**Location:** `Documents/Affilabs_Data/[ExperimentName]/Raw_Data/`
**Filename:** `Raw_YYYYMMDD_HHMMSS.xlsx`

**Contains:**
- Sheet 1: Raw Data (long format) - Time, Channel, Value
- Sheet 2: Per-Channel Format - Time_A, A, Time_B, B, Time_C, C, Time_D, D
- Sheet 3: Cycle Table - Basic info (type, duration, conc, flags, notes)
- Sheet 4: Export Info - Metadata (date, software version, device)

**Use Cases:**
- Backup of original measurements
- Re-analysis with different reference channel
- Quality control audits
- External software analysis (Prism, Origin)

### Analysis Export (from Edit Tab)

**When to Use:** Final results with annotations & Δ-SPR measurements
**Format:** Excel (.xlsx)
**Location:** `Documents/Affilabs_Data/[ExperimentName]/Analysis/`
**Filename:** `Analysis_YYYYMMDD_HHMMSS.xlsx`

**Contains:**
- Sheet 1: Cycle Analysis - Full table with ΔSPR, flags, notes, QC status
- Sheet 2: Metadata - Experiment info, operator, device, sensor type
- Sheet 3: Settings - Analysis settings (ref channel, alignment, filters)

**Ready to Use:**
- Copy & paste ΔSPR values to external software
- Includes all annotations & validation status
- Re-loadable for further editing

### Export Info Sheet

Both exports include metadata:

```
Export Date:    2026-02-07 14:30:00
Software:       Affilabs-Core v2.0
Device:         FLMT09788
Total Cycles:   8
Data Points:    12,450
Channels:       A, B, C, D
```

---

## Manual Operation

### Sensor Installation (P4PRO & P4SPR 2.0)

**CRITICAL: Proper sensor installation is essential for accurate measurements. Follow steps precisely.**

#### Hardware Components for Installation

The sensor assembly has **three key mechanisms**:

| Component | Purpose | Description |
|-----------|---------|-------------|
| **Latch Mechanism** | Opens/closes prism/microfluidic system | Allows arm to move freely for sensor installation/removal |
| **Small Lock Knob** | Secures the prism/microfluidic arm | Locks arm in position once aligned (clockwise = locked) |
| **Large Pressure Knob** | Compresses microfluidic cell onto sensor | Presses sensor and microfluidic cell together for optical contact |

**Assembly Structure:**
- **Sensor** sits face UP in the sample holder (gold surface upward)
- **Prism/Microfluidic Cell** comes DOWN from the arm (facing the sensor)
- **Pressure Knob** compresses these together for optical coupling
- **Lock Knob** holds the assembly stable
- **Latch** allows opening/closing of the entire prism/microfluidic system

#### Step-by-Step Sensor Installation

**⚠️ IMPORTANT: Wear nitrile gloves during entire installation process. Never touch sensor surface with bare hands.**

**Before You Start:**
- [ ] Sensor removed from storage (if reused) and hydrated
- [ ] Gloves on (nitrile only, never bare hands)
- [ ] Sensor slot visually clear of debris
- [ ] Pressure knob fully released (all the way up)

**Installation Steps:**

**Step 1: Position the Sensor in the Sample Holder**
1. Hold sensor by **edges only** (never touch surface)
2. Orient sensor so **gold surface faces UP** in the sample holder
3. Glass windows should face upward toward the prism/microfluidic arm
4. Gently place sensor into the sample holder slot
5. Ensure sensor sits **flat and level** in the holder
6. Verify sensor is not tilted or askew

**Step 2: Open the Prism/Microfluidic Latch (if not already open)**
1. Locate the **latching mechanism** on the prism/microfluidic arm
2. Unlock/open the latch to allow the arm to move freely
3. Prism/microfluidic cell should be accessible above the sensor
4. Keep latch accessible for the next steps

**Step 3: Lower the Prism/Microfluidic Arm Toward Sensor**
1. Carefully lower the prism/microfluidic arm down toward the sensor
2. The microfluidic cell (facing downward) will approach the sensor gold surface
3. Lower slowly and steadily until arm is in contact position
4. Prism/microfluidic cell should be positioned directly above the sensor

**Step 4: Verify Pressure Knob Position (Critical)**
1. Check the **large pressure knob** (compression control)
2. Verify knob is **all the way UP** (fully clockwise position)
3. Knob should be at maximum height before compression
4. This ensures proper initial alignment before locking

**Step 5: Lock the Arm in Place**
1. Locate the **small lock knob** on the side
2. Turn lock knob **CLOCKWISE** to fully lock
3. Lock should be tight but not forced
4. Arm/prism is now secured in position
5. Latch mechanism helps hold the prism/microfluidic assembly in place

**Step 6: Compress the Sensor (Final Step)**
1. Now turn the **large pressure knob ANTI-CLOCKWISE** (counter-clockwise)
2. Turn slowly and steadily
3. Stop when knob reaches the DOWN position (fully counter-clockwise)
4. Knob will press the microfluidic cell onto the sensor gold surface
5. Sensor and microfluidic cell should be in firm contact
6. Do NOT over-tighten - sensor should be pressed, not crushed

**Step 7: Verify Installation**
1. Sensor should be **firmly held** in position with prism/microfluidic cell pressing down
2. **No visible gaps** between sensor and microfluidic cell contact surface
3. **No movement** when gently pressing on the arm
4. Gold surface should be **in firm contact** with the microfluidic cell
5. Glass windows should be **clear and unobstructed** and facing upward
6. Prism/microfluidic assembly should be locked and stable

#### Understanding the Compression Mechanism

**Why Compression Matters: Balancing Optical Contact and Microfluidic Integrity**

The **large pressure knob** (compression control) is critical for measurement quality. Proper compression ensures optical coupling between the sensor and microfluidic cell, but incorrect compression can cause serious issues:

**⚠️ COMPRESSION TOO LOOSE:**
- **Symptom**: Incomplete optical contact between sensor and microfluidic cell
- **Result**: **Leaks** - buffer escapes from the fluidic channels
- **Consequences**:
  - Loss of sample volume
  - Air entry into the system
  - Failed experiments
  - Water infiltration into optical apertures
  - Baseline instability

**⚠️ OVER-COMPRESSION:**
- **Symptom**: Excessive force pressing microfluidic cell onto sensor
- **Result**: **Microfluidic deformation** - the cell structure distorts under pressure
- **Consequences**:
  - Unreliable signal (distorted optical path)
  - Inconsistent baseline readings
  - Channel-to-channel variability
  - Reduced sensor lifespan
  - Permanent damage to microfluidic cell geometry

**The Compression Sweet Spot:**

The ideal compression provides:
- ✓ **Tight seal** - No leaks, complete fluidic containment
- ✓ **Optical coupling** - Full contact for accurate SPR measurement
- ✓ **Structural integrity** - No deformation of microfluidic channels
- ✓ **Stable baseline** - Minimal drift, consistent signal quality

**Compression Assistant Feature:**

Affilabs.core v2.0 includes a **Compression Training Assistant** to help you find the optimal compression:

1. **Access the Assistant:**
   - Settings → Device Status → "Train Compression"
   - Or ask Spark AI: "Help me optimize compression"

2. **What the Assistant Does:**
   - Guides you through incremental compression adjustments
   - Monitors baseline stability in real-time
   - Detects leak signatures (sudden drift, signal loss)
   - Identifies over-compression (noise increase, signal distortion)
   - Recommends optimal knob position for your specific sensor

3. **How It Works:**
   - Start with knob fully UP (no compression)
   - Turn knob counter-clockwise in small increments
   - Assistant monitors signal quality at each position
   - Stop when assistant indicates "optimal compression achieved"
   - Record the knob position for future reference

4. **Benefits:**
   - **Prevents leaks** by ensuring sufficient compression
   - **Prevents over-compression** by detecting signal degradation
   - **Consistent measurements** across experiments
   - **Extends sensor lifespan** by avoiding damage
   - **Faster setup** - no trial-and-error needed

**Compression Adjustment Guidelines:**

| Observation | Action | Explanation |
|-------------|--------|-------------|
| Visible liquid leaking from sensor area | Turn knob further COUNTER-CLOCKWISE (increase compression) | Seal is incomplete - more pressure needed |
| Baseline drift > 1 nm/min after installation | Turn knob slightly CLOCKWISE (reduce compression) | Possible over-compression causing microfluidic deformation |
| Signal very noisy or erratic | Turn knob slightly CLOCKWISE (reduce compression) | Over-compression distorting optical path |
| Baseline stable, no leaks | ✓ Optimal compression achieved | Current position is ideal - record for future use |

**Best Practice:**
- Use the **Compression Assistant** during initial setup or when switching sensors
- Document the optimal knob position for your specific sensor type
- Recheck compression if baseline becomes unstable during long experiments
- Always start with knob UP, then compress incrementally (never start compressed)

#### Verification Checklist

After installation, verify:

- [ ] Sensor is level and centered in sample holder (gold surface facing UP)
- [ ] Gold surface is in firm contact with microfluidic cell (facing DOWN from arm)
- [ ] Prism/microfluidic arm is locked (lock knob fully clockwise)
- [ ] Pressure knob is compressed (fully counter-clockwise)
- [ ] No visible gaps between sensor and microfluidic cell contact surface
- [ ] Sensor cannot be shifted or moved
- [ ] Glass windows are clean and unobstructed (facing upward)
- [ ] No fingerprints or contamination on sensor surfaces
- [ ] Latch mechanism is engaged and secure

#### Removing the Sensor

**When experiment is complete:**

**⚠️ IMPORTANT: Use proper technique to avoid damaging sensor or prism assembly**

1. Turn **pressure knob CLOCKWISE** (upward) to release compression from microfluidic cell
2. Unlock the **latch mechanism** to release the prism/microfluidic arm
3. **Use a pipette tip** to gently lift the **side of the prism** away from the sensor
   - Insert pipette tip under edge of prism/microfluidic cell
   - Gently lift to create separation between prism and sensor
   - Do NOT pull straight up - work gradually from the side
   - This prevents suction/adhesion from holding sensor in place
4. Once prism is lifted clear, unlock the **lock knob COUNTER-CLOCKWISE** to fully release the arm
5. Grasp sensor by **edges only** (gloved hands, NEVER bare hands)
6. Lift sensor straight up and out of the sample holder
7. **For reuse**: Immediately rinse with appropriate buffer and store in refrigerator with hydration
8. **For disposal**: Follow institutional waste protocols for contaminated lab materials

**Why this matters:**
- Optical contact between sensor gold surface and microfluidic cell can create slight adhesion
- Using pipette tip prevents direct force on sensor or prism surfaces
- Gentle side lifting breaks the optical contact safely
- Protects both sensor and prism from damage

#### Sensor Handling Tips & Best Practices

**Critical Techniques for Sensor Care:**

1. **During Installation:**
   - Always hold sensor by edges only (never touch surface or windows)
   - Lower prism/microfluidic arm slowly and steadily
   - Ensure full compression for optical contact
   - Never force any components

2. **During Removal:**
   - **Use pipette tip technique** to gently lift prism side (NOT straight up)
   - This prevents adhesion from breaking sensor or prism
   - Always work from the side - never pull straight up
   - Optical contact can create suction - pipette tip breakage is gentle

3. **Between Measurements:**
   - Never leave sensor exposed to air for extended periods
   - Keep sensor hydrated during breaks
   - Cover with buffer if pausing experiment > 5 minutes

4. **After Use:**
   - Rinse immediately with appropriate buffer
   - Do NOT allow sensor to dry
   - Store in refrigerator (2-8°C) in buffer solution
   - Label with date and usage count if reusing

#### Troubleshooting Installation Issues

| Problem | Solution |
|---------|----------|
| Sensor won't sit flat in holder | Remove and check holder slot for debris. Clean with nitrogen if needed. Sensor edges may have manufacturing residue - clean edge with nitrogen. Reinstall with sensor face UP. |
| Prism/microfluidic arm won't close | Verify latch mechanism is fully open. Sensor may be tilted. Remove, reposition flat (face UP), try again. Ensure microfluidic cell (facing DOWN) aligns with sensor. |
| Pressure knob stuck | Don't force. Verify lock knob is fully loosened first and latch is open. Try gentle pressure while turning. Contact support if stuck. |
| Sensor moves after installation | Lock knob not fully engaged. Remove sensor, reinstall, and turn lock knob more firmly clockwise. Verify latch is engaged. |
| Baseline very unstable after installation | Microfluidic cell not in full contact. Turn pressure knob further counter-clockwise for better compression. Verify sensor gold surface is facing UP. |
| Signal extremely noisy | Sensor contamination (most common). Verify no fingerprints on gold surface or windows. Use nitrogen to blow away dust. Check microfluidic cell for debris. Reinstall. |
| No optical contact | Sensor orientation incorrect (gold surface must face UP). Remove and reposition with gold face UP. Verify microfluidic cell comes DOWN from arm. |

---

### Channel Addressing & Volume Guidelines

**P4SPR System Features:**
- Each channel (A, B, C, D) can be addressed individually via dedicated port on system front
- All channels accessible simultaneously or sequentially

**Volume Specifications:**
| Operation | Volume | Notes |
|-----------|--------|-------|
| **Minimum per channel** | 150 µL | Sufficient for sensor incubation |
| **Standard concentration test** | 150-300 µL | Typical binding assay |
| **Washing** | 500 µL | Complete buffer exchange |
| **Maximum** | No limit | Limited by reservoir size |

**Flow Rate (Manual Injection):**
- **Standard rate**: ~100 µL/second
- **Slower rate** (optional): 50 µL/second for sensitive samples
- **Flow adjustment**: Via pump speed control in Pump Controls panel

### Manual Pump Control (If Equipped)

**Use for:** Single injections, buffer exchanges, troubleshooting

#### Manual Injection

1. **Go to Live Tab → Pump Controls** (if hardware connected)
2. **Select Channel**: A, B, C, or D (or multi-channel)
3. **Set Volume**: 150-500 µL depending on operation
   - Standard test: 200 µL
   - Washing: 500 µL
4. **Flow Rate**: ~100 µL/second (approximately 10 µL/min @ 0.167 mL/sec)
5. **Click "Inject"**
   - Pump dispenses specified volume
   - Graph updates in real-time
   - Flag automatically added to sensorgram
   - **Important**: Monitor binding response during incubation (fixed timepoint)

#### Manual Pressure Check

1. **Pump Controls → Pressure Monitor**
2. **Current Pressure** display shows PSI
3. **Acceptable Range**: 0.5-2.0 bar
   - Below 0.5: Check tubing, flow issues
   - Above 2.0: Blockage detected

#### Fixed-Time Incubation Workflow

The P4SPR uses **microfluidic incubation** for affinity measurement, not kinetic monitoring:

1. **Inject analyte** (150-300 µL) at standard flowrate
2. **Wait for binding** at fixed timepoint (typically 5-10 minutes)
3. **Measure maximum binding** (Δ-SPR) using cursors in Edit tab
4. **Wash channel** (500 µL buffer) to regenerate surface
5. **Repeat** with next concentration or sample

**Key difference from kinetics:**
- You're measuring **equilibrium binding** at a fixed time
- Not tracking binding kinetics over time
- Compare Δ-SPR values across multiple concentrations to build affinity curve
- Each injection is independent measurement at same timepoint

#### Air Bubble Pulse Clearing Technique

**If air bubbles enter the system during operation:**

1. **STOP the experiment immediately**
2. **Go to Live Tab → Pump Controls**
3. **Run Pulse Injections:**
   - Set Volume: 50-100 µL (small pulses)
   - Set Flow Rate: Maximum speed (force air out)
   - Click "Inject" repeatedly (3-5 times)
   - Watch tubing - air should be expelled from the system
4. **Verify System Clear:**
   - No more air bubbles visible in tubing
   - Baseline returns to stable (< 0.5 nm/min drift)
5. **Re-prime the line:**
   - Inject 100-200 µL buffer at normal speed
   - Verify smooth flow
6. **Resume experiment** or restart current cycle

### Servo Position (S-Mode / P-Mode)

**S-Mode (Shear):** Both surfaces parallel (higher SPR sensitivity)
**P-Mode (Parallel):** Surfaces at angle (lower drift)

**Current Configuration:**
- S-Position: 193° (servo angle)
- P-Position: 30° (servo angle)

**To Switch Modes (Advanced):**
- Settings → Device Configuration
- Adjust servo positions (requires recalibration)
- Factory defaults recommended for most users

---

## Maintenance

### Daily Maintenance (Before/After Use)

| Task | Frequency | Instructions |
|------|-----------|---|
| **⚠️ SENSOR INSPECTION** | **BEFORE EVERY RUN** | **GLOVED HANDS ONLY:** Visually inspect sensor - NO dust, debris, or contamination on surface or windows |
| **⚠️ Air Bubble Check** | **BEFORE EVERY RUN** | **CRITICAL:** Inspect all tubing visually for air pockets - NONE allowed |
| **Syringe Prime** | **BEFORE EVERY RUN** | Run buffer through pump (50-100 µL) to clear air from lines |
| **Flow Check** | Daily | Verify buffer flows smoothly through chip (2-3 mL/min) |
| **Visual Inspection** | Daily | Check for debris, discoloration in tubing |
| **Baseline Stability** | Daily | Baseline drift < 0.5 nm over 5 min = OK |
| **Sensor Position** | Weekly | Ensure chip properly seated in holder - HANDLE BY EDGES ONLY, GLOVED |

### Weekly Maintenance

1. **⚠️ Sensor Visual Check** (GLOVED HANDS ONLY)
   - Inspect sensor surface for dust, debris, fingerprints
   - Check glass windows for contamination
   - **If light dust only**: Use nitrogen gas (N₂) to blow away particles
     - Hold sensor by edges only
     - Use dry nitrogen at safe distance
     - Do NOT use compressed air (contains moisture/oils)
   - **If chemical contamination or fingerprints**: Contact manufacturer for cleaning protocol
   - **Never attempt to wipe or scrub sensor** (damage risk)

2. **Buffer Reservoir**
   - Check volume (should be > 50% full)
   - If low, refill with fresh running buffer
   - Replace if older than 2 weeks

3. **Tubing Inspection**
   - Look for cracks, discoloration, or blockages
   - Replace if compromised
   - Connection tightness: Hand-tight + ¼ turn

4. **Pump Lines**
   - Prime pump (push air out)
   - Verify no air bubbles in line
   - Flow rate consistent?

### Biweekly System Cleaning (CLN-KIT)

**Purpose:** Thoroughly clean and sanitize the fluidic system to reduce baseline noise and drift from accumulated residues.

**Recommended Frequency:** Every two weeks (or after critical experiments)

**Equipment Required:**
- Affinité Cleaning Kit (Product code: CLN-KIT)
- 1 mL syringes with slip tip or Luer tip
- Distilled Deionized (DDI) water
- Running buffer (e.g., PBS 1X pH 7.4 + 0.1% Tween 20)
- Unused or used Au sensor (dedicated for cleaning, NOT your experiment sensor)

**Kit Contents & Storage:**
| Component | Volume | Storage Condition |
|-----------|--------|-------------------|
| **0.5% SDS** | 60 mL | Room temperature |
| **Glycine-NaOH, 50mM pH 9.5** | 60 mL | 2°C to 8°C (refrigerator) |
| **ezSanitize solution** | 60 mL | 2°C to 8°C (refrigerator) |

**⚠️ IMPORTANT NOTES:**
- The cleaning process will damage any biomolecules on a sensor, so use an **unused Au sensor or a previously-used sensor** (NOT your active experiment sensor)
- Do NOT dock your experiment sensor - use a dedicated cleaning sensor only
- Refer to Safety Data Sheet for safe handling of cleaning solutions

#### Procedure: Regular Cleaning

**Step 1: Dock Cleaning Sensor**
1. Remove your active experiment sensor carefully (follow removal procedure)
2. Dock an unused Au sensor or a used/dedicated cleaning sensor
3. Ensure sensor is fully seated and locked in place

**Step 2: SDS Wash (3 cycles)**
1. Draw up 250 µL of **0.5% SDS** into syringe
2. Inject into all channels (A, B, C, D) sequentially
3. Repeat cycle 3 times total
4. Allow to sit for 1-2 minutes after final injection

**Step 3: Distilled Deionized Water Rinse (3 cycles)**
1. Draw up 1 mL of **Distilled Deionized (DDI) water**
2. Inject into all channels sequentially
3. Repeat cycle 3 times total
4. This removes SDS residue

**Step 4: Glycine-NaOH Wash (3 cycles)**
1. Draw up 250 µL of **Glycine-NaOH, 50mM pH 9.5** (from refrigerator)
2. Inject into all channels sequentially
3. Repeat cycle 3 times total
4. Allow to sit for 2-3 minutes after final injection

**Step 5: Final DDI Rinse (3 cycles)**
1. Draw up 1 mL of **Distilled Deionized water**
2. Inject into all channels sequentially
3. Repeat cycle 3 times total

**Step 6: Running Buffer Equilibration**
1. Draw up 1 mL of **Running Buffer** (same buffer used in experiments)
2. Inject into all channels sequentially
3. **Repeat until baseline is stable** (watch graph for < 0.1 nm/min drift)
4. Typically 2-4 injections needed

**Step 7: Resume Experiments**
1. Baseline should now be clean and stable
2. Remove cleaning sensor
3. Dock your experiment sensor
4. Run preliminary baseline check before resuming

#### Procedure: Sanitization (for biological samples)

**Use this additional step if system has contacted biological samples** (serum, urine, plasma, saliva)

After completing Regular Cleaning steps 1-5 above, add Sanitization:

**Step 1: ezSanitize Wash (3 cycles)**
1. Draw up 250 µL of **ezSanitize solution** (from refrigerator)
2. Inject into all channels sequentially
3. Repeat cycle 3 times total
4. Allow to sit for 2-3 minutes

**Step 2: Running Buffer Rinse (3 cycles)**
1. Draw up 1 mL of **Running Buffer**
2. Inject into all channels sequentially
3. Repeat cycle 3 times total

**Step 3: DDI Water Rinse (3 cycles)**
1. Draw up 1 mL of **Distilled Deionized water**
2. Inject into all channels sequentially
3. Repeat cycle 3 times total

**Step 4: Running Buffer Equilibration**
1. Draw up 1 mL of **Running Buffer**
2. Inject into all channels sequentially
3. **Repeat until baseline is stable** (< 0.1 nm/min drift)

**Step 5: Resume Experiments**
1. Remove cleaning sensor
2. Dock experiment sensor
3. Run baseline check

#### Cleaning Kit Maintenance Notes

**Kit Shelf Life & Storage:**
- Check expiration dates on kit bottles (typically 1-2 years from manufacture)
- Store at recommended temperatures (room temp for SDS, 2-8°C for others)
- Keep bottles sealed when not in use
- Discard if solutions appear discolored or cloudy
- Replace kit annually or when solutions are depleted

**Expected Kit Duration:**
- One CLN-KIT (60 mL per solution) is sufficient for ~12-15 cleaning cycles (2-3 months of biweekly cleaning)
- Monitor usage and order replacement kits before depleting

### Monthly Maintenance

1. **LED PCB Light Source Check**
   - **Spectral Range**: 500 nm - 680 nm (cool white LED)
   - **Check LED intensity**: Settings → Device Configuration
     - Current LED intensities:
       - Channel A: 115
       - Channel B: 119
       - Channel C: 92
       - Channel D: 119
     - **Warning signs of degradation:**
       - Variation > 10% between channels
       - Overall intensity loss (baseline signal decreasing)
       - Color profile shift (signal shifting toward red/infrared)
   - **If LED degradation detected:**
     - Document observed changes (date, intensity values, symptoms)
     - Order replacement LED PCB from Affinité (specify your device ID: FLMT09788)
     - Keep spare LED on hand for critical experiments
     - **DO NOT attempt to repair or adjust LED** - replacement is standard procedure

2. **Spectrometer Calibration Status**
   - Settings → Calibration
   - Check last calibration date
   - If > 3 months, recommend recalibration

3. **Polarizer Alignment**
   - Last calibrated: 2025-12-18
   - Status: OK
   - If seeing drift, perform polarizer recalibration

### Quarterly/Annual Maintenance

1. **⚠️ Microfluidic Cell Replacement** (ANNUAL - CRITICAL)
   - **Replace microfluidic cell once per year** - this is preventive maintenance
   - Even if no visible issues, the cell degrades with exposure to buffers and samples
   - Degraded cells can cause:
     - Reduced optical contact
     - Baseline drift
     - Inconsistent measurements
     - Leaks (water infiltration)
   - Order replacement cell from manufacturer before annual maintenance date
   - Keep spare cell on hand in case of damage or leak

2. **Microfluidic Cell Leak Diagnosis & Repair**
   - **If experiencing leaks during measurements:**
   - **First check**: Look for water stuck in the **apertures toward the polarizer** (opposite side from LED)
   - Water in these apertures causes:
     - Signal degradation
     - Baseline instability
     - Optical interference
   - **To clear water from apertures:**
     - Use compressed nitrogen (N₂) at moderate pressure
     - Direct airflow toward polarizer-side apertures
     - Allow to air dry completely (15-30 minutes)
     - Verify leak has stopped before resuming experiments
   - **If leak persists after water removal**: Replace microfluidic cell
   - **Do NOT attempt to disassemble or repair cell** - replacement is standard procedure

3. **Fluidic Components Inspection & Replacement**
   - **Components that can be replaced:**
     - Tubing (silicone, PTFE)
     - Pump seals and O-rings
     - Connectors and fittings
     - Syringe plungers
     - Check valves
     - Flow restrictors
   - **When to replace:**
     - Tubing cracks or discoloration
     - Visible leaks at connections
     - Pressure readings abnormal (< 0.3 bar or > 2.5 bar)
     - Flow rate decreasing
     - Visible blockages or crystallization
   - **For replacement:**
     - Contact Affinité with device ID (FLMT09788) and component description
     - Keep spare tubing sets on hand (easy to replace in the field)
     - Most other components require technician-level service
   - **DO NOT attempt to repair** - replacement is the standard procedure
   - Affinité can provide:
     - Replacement part kits
     - Installation instructions
     - Technical support for component swaps

4. **⚠️ Sensor Assessment** (GLOVED, HANDLE WITH CARE)
   - Inspect sensor under magnification if available
   - Look for:
     - Surface contamination or discoloration
     - Dust or particles on gold surface
     - Fingerprints or smudges on windows
     - Visible damage or scratches
   - **If any contamination found**: Contact Affinité for professional cleaning
   - **DO NOT attempt to clean sensor** (you will damage it permanently)

2. **Deep Cleaning** (Fluidics only, NOT sensor)
   - Run 70% ethanol through system (10 min)
   - Flush with distilled water (5 min)
   - Run fresh buffer (2 min)
   - **NOTE: This only cleans tubing/pump, NOT sensor**

3. **Full Sensor Calibration**
   - Settings → Calibration → Start Calibration
   - Runs dark calibration + S/P mode calibration
   - Takes ~15 minutes
   - Improves baseline accuracy

4. **Optical Fiber Inspection**
   - Visual inspection with magnifier
   - Look for dust, scratches at both ends
   - If dirty: Clean with lens tissue + solvent
   - **DO NOT point laser at eyes** during inspection

### Sensor Storage & Reuse Protocol

**If planning to REUSE a sensor after an experiment:**

1. **Immediately after use:**
   - Rinse sensor with appropriate buffer
   - Keep sensor hydrated (do not allow to dry)
   - Do NOT let surface dry out

2. **Short-term storage (1-2 weeks):**
   - Store in sealed container with buffer solution
   - Keep in refrigerator (2-8°C)
   - Label with date and usage count
   - Prevent evaporation (seal container tightly)

3. **Before reuse:**
   - Visually inspect for contamination
   - If dusty: Use nitrogen gas to clean
   - Rehydrate sensor by immersing in fresh buffer
   - Allow 15-30 minutes equilibration before use

4. **Performance expectations:**
   - **First use**: ~100% performance (baseline)
   - **Second use**: ~80-90% performance (expect some signal loss)
   - **Third+ use**: ~50-70% performance (significant degradation)
   - Degradation is **permanent and expected**

**⚠️ RECOMMENDATION:** Always use **fresh new sensors** for:
- Critical/important experiments
- Publication-quality data
- Regulatory/compliance experiments
- Kinetic analysis or precise Kd determination

### Maintenance Log

Record in lab notebook or digital system:

**Daily/Weekly Example:**
```
Date: 2026-02-07
Technician: Lucy
Task: Weekly maintenance
- Flow check: OK (2.5 mL/min)
- Tubing: Clean, no blockages
- Buffer changed: Yes
- LED check: All within range
- Sensor: Visually clear, no contamination
- Microfluidic cell: No leaks observed
- Next action: Quarterly calibration due 2026-05-07
```

**Annual Maintenance Tracking:**
```
Date: 2026-02-01
Technician: Lucy
Task: Annual maintenance & microfluidic cell replacement
- Microfluidic cell: REPLACED (old cell installed 2025-02-01, lifespan 1 year)
- Cell serial: MFC-2026-001
- Sensor: Full assessment, no visible contamination
- Calibration: Full recalibration performed
- Optical fiber: Cleaned and inspected
- Deep cleaning: Fluidic system flushed with ethanol + water
- Next scheduled maintenance: 2027-02-01
- Notes: Previous cell showed slight baseline drift near end of cycle - new cell installed as preventive measure
```

### Troubleshooting Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| **Erratic/noisy signal** | **Sensor surface contaminated (fingerprints, dust, tissue residue)** | **STOP immediately. This is IRREVERSIBLE damage. Sensor cannot be recovered. Contact Affinité. For future: ALWAYS wear gloves, NEVER touch surface, NEVER wipe with tissues.** |
| **Signal degradation over time** | **Sensor surface chemistry damaged from hand contact** | Sensor likely permanently damaged. Document incident. Contact Affinité for replacement. Liability note: User is responsible for proper handling. |
| **⚠️ Baseline drift > 1 nm/min** | **Air bubble in line (CRITICAL)** | **STOP immediately. Visual inspect all tubing. Use pulse injections (50-100 µL rapid) to force air out. Refill lines with buffer. DO NOT resume until air is cleared.** |
| **No data on graph** | Sensor not seated OR air in line | Reseat chip (gloved, by edges only), prime pump with 100 µL buffer, inspect for air bubbles |
| **Δ-SPR values erratic/missing** | Air bubble in measurement path OR sensor contamination | Use pulse injections to clear air, recalibrate baseline, remeasure. If persists: check sensor for contamination. |
| **LED intensities vary** | Dust on optics OR air affecting signal OR dirty sensor windows | Verify no air bubbles. If sensor has dust: Use nitrogen gas (N₂) to blow away particles (gloved hands). Then run calibration. |
| **Pressure high (> 2.5 bar)** | Blockage in line (could be air lock) | Check for air pockets, pulse to clear, flush with buffer |
| **Pressure low (< 0.3 bar)** | Tubing crack OR air leak | Inspect tubing for punctures, check connections, verify no air entry |
| **Experiment fails mid-run** | Air bubble OR sensor contamination | Prime syringe, inspect sensor surface (gloved), ensure NO bubbles, NO contamination |
| **⚠️ Leak visible during measurement** | **Water in polarizer-side apertures OR damaged microfluidic cell** | **STOP immediately.** Check apertures (opposite LED side) for water. Use nitrogen (N₂) to clear water from apertures. If leak persists: Replace microfluidic cell (annual maintenance item). |
| **Baseline unstable + water visible** | Water infiltration in microfluidic cell | Dry apertures with nitrogen. If unstable baseline persists after drying: Cell likely damaged - replace. Check that cell is properly seated and compressed. |
| **Poor signal after leak event** | Optical interference from residual water | Use nitrogen to fully dry all apertures and contact surfaces. Allow 15-30 min air dry time. Recalibrate baseline. If signal remains poor: Replace microfluidic cell. |
| **⚠️ LED intensity decreasing** | LED PCB aging/degradation (500-680 nm source) | Document current intensities. If variation > 10% or overall loss, order replacement LED PCB from Affinité (specify device ID). LED color profile may shift toward red/infrared. Keep spare on hand. |
| **Baseline signal very low** | Dim LED or sensor contamination | Check LED intensities (Settings → Device Config). If all intensities low: LED aging. If some channels low: Check sensor windows for dust/contamination. Replace LED if needed. |
| **Signal color shifted (red/infrared bias)** | LED PCB color profile degradation | LED approaching end of life. Order replacement LED PCB from Affinité. Continue experiments with caution - signal integrity may be compromised. |
| **⚠️ Pressure abnormal + no visible blockage** | Fluidic component degradation (tubing, seals, check valve) | Check for: tiny cracks in tubing, dried buffer in connectors, pump seal wear. Replace affected component. Contact Affinité for replacement kits - most fluidic components are replaceable. |
| **Slow/weak flow** | Fluidic restriction or blockage | Try pulse injections to clear. If flow remains weak: Replace tubing (easy field replacement). If issue persists: Check pump seals and check valves - may need replacement. Contact Affinité. |
| **Visible leak from tubing connection** | Loose fitting or cracked tubing | Tighten connection (hand-tight + ¼ turn). If leak persists: Replace tubing section. If multiple leaks: Entire fluidic system may need service - contact Affinité. |
| **Baseline unstable after power-on** | Cold start or thermal equilibration | Allow 30 minutes warm-up time. Device optimal at 15-25°C. If still unstable: Check room temperature - may be outside operating range (-30 to +70°C). |
| **Signal drifting after temperature change** | Thermal expansion/contraction in optics | Avoid rapid temperature changes (> 5°C/minute). Allow device to thermally stabilize. Recalibrate baseline after major temperature swings. |
| **High baseline noise in cold environment** | Low temperature affecting detector sensitivity | Cold operation normal (-30°C valid). If noise unacceptable: Warm device to 15-25°C for optimal performance. Check detector isn't below -30°C (out of spec). |
| **Detector not responding (cold weather)** | Temperature below -30°C (out of spec) | Device cannot operate below -30°C. Warm to -30°C or higher before use. Store only between 0-50°C. |
| **Overheating warnings (hot environment)** | Temperature above +70°C (out of spec) | Device cannot operate above +70°C. Move to cooler location or provide active cooling. Ensure ventilation - hot environment (> 45°C) needs airflow. |

---

## Software Compatibility

### System Requirements

| Requirement | Specification | Status |
|---|---|---|
| **OS** | Windows 10 / 11 (64-bit) **ONLY** | ✓ Supported |
| **Python** | 3.10+ | ✓ Included |
| **RAM** | 8 GB minimum | ✓ Recommended |
| **Storage** | 2 GB free space | ✓ For data |
| **USB** | 3.0+ recommended | ✓ For device |

**⚠️ IMPORTANT: Windows Only**
- Affilabs.core v2.0 is **Windows-only software**
- macOS and Linux are **NOT supported** at this time
- Ensure you are running Windows 10 (build 19041+) or Windows 11

### Environmental Operating Conditions (Hardware)

| Condition | Specification | Impact |
|---|---|---|
| **Temperature** | -30°C to +70°C (operational) | Flame-T spectrometer detector range |
| **Optimal Temperature** | 15°C to 25°C | Best baseline stability and signal quality |
| **Storage Temperature** | 0°C to +50°C | Long-term storage conditions |
| **Humidity** | 10-90% (non-condensing) | Prevents moisture damage to optics |
| **Ventilation** | Adequate airflow | Prevents thermal stress in hot environments |

**Operating Notes:**
- Allow 30-minute warm-up if operating below 10°C
- Keep away from direct sunlight and heat sources
- In cold environments (< 5°C), warm device before use to prevent condensation
- In hot environments (> 45°C), ensure cooling ventilation
- Temperature changes > 5°C/minute can affect baseline stability

### Current Software Version

```
Software Name:        Affilabs-Core
Version:             2.0
Release Date:        January 30, 2026
Status:              Production Release
Device Compatibility: FLMT09788 (Flame-T Spectrometer)
```

### Version History

| Version | Date | Changes | Status |
|---------|------|---------|--------|
| **2.0** | 2026-01-30 | Live/Edit two-phase workflow, GLP/GMP organization, auto-save Δ-SPR | Current |
| 1.06 | 2025-12-15 | Various bug fixes | Deprecated |
| 1.0 | 2025-10-01 | Initial release | End of Life |

### Backward Compatibility

- **Raw data files (v1.x)**: ✓ Loadable in Edit tab
- **Method files (v1.x)**: ✓ Loadable in Method Builder
- **Analysis files (v1.x)**: ⚠ Requires manual column mapping

### Known Limitations

- **Maximum concurrent cycles**: 100 per experiment
- **Maximum data points**: 500,000 (per session)
- **Supported channels**: 4 (A, B, C, D)
- **External software import**: Excel only (CSV via Pandas)

### Update Policy

**Check for updates:** Help → About → Check for Updates

- **Automatic**: Minor updates (security patches)
- **Manual**: Major updates (new features, breaking changes)
- **Notification**: Optional alert on startup

### Getting Help

- **In-app help**: Click **?** button (top right)
- **Documentation**: `docs/` folder in installation directory
- **Error logs**: Saved to `~/.affilabs/logs/`
- **Contact support**: [support contact info]

---

---

## User Management

### Overview

ezControl includes a built-in user management system to track who runs experiments and help users progress from novice to expert operators.

**Key Features:**
- Multiple user profiles for lab sharing
- Automatic experiment tracking per user
- Progression system with titles (Novice → Master)
- User attribution in exported data and metadata
- GLP/GMP compliance with user tracking

---

### Creating User Profiles

#### Adding Your First User

1. Open ezControl
2. Navigate to **Settings** tab in sidebar
3. Scroll down to **👥 User Management** section
4. Click **Expand** to show user management controls
5. Click **+ Add User** button
6. Enter user's name (e.g., "John Smith")
7. Click **OK**

**Tips:**
- Use full names for GLP/GMP compliance
- Names appear in exported data files and metadata
- Default user "Default User" is created automatically

#### Managing Multiple Users

**Adding More Users:**
- Click **+ Add User** for each lab member
- Users are sorted alphabetically
- No limit on number of users

**Deleting Users:**
1. Select user name from the list
2. Click **Delete Selected**
3. Confirm deletion
4. Cannot delete the last remaining user

---

### User Progression System

ezControl tracks how many experiments each user has run and awards progression titles based on experience.

#### Progression Titles

| Title | Experiments Required | Description |
|-------|---------------------|-------------|
| **Novice** | 0-4 experiments | New user, learning the basics |
| **Operator** | 5-19 experiments | Familiar with standard workflows |
| **Specialist** | 20-49 experiments | Experienced with advanced features |
| **Expert** | 50-99 experiments | Highly skilled, can troubleshoot |
| **Master** | 100+ experiments | Expert operator, training capability |

#### Viewing Your Progression

When you expand the **User Management** section:
- **Blue progression banner** shows your current title
- Displays total experiment count (XP)
- Shows progress to next title
  - Example: "Novice — 2 experiments (3 more to Operator)"

#### How Experiments Are Counted

**Experiments are counted when you:**
- Complete an acquisition in the **Live** tab
- Save experiment data to the GLP folder structure
- Export analysis results from the **Edits** tab

**Not counted:**
- Test runs that aren't saved
- Method building/editing
- Calibration procedures

#### User List Display

The user list shows all users with their titles:
```
John Smith — Master (127 experiments)
Jane Doe — Specialist (34 experiments)
Default User — Novice (0 experiments)
```

---

### Switching Between Users

#### Before Starting an Experiment

1. Click the **user dropdown** (top toolbar, near device status)
2. Select your name from the list
3. Your name appears in the toolbar
4. All subsequent experiments will be attributed to you

**Important:**
- Always switch to your name before running experiments
- User attribution is permanent in exported data
- Required for GLP/GMP audit trails

#### User Attribution in Files

When you run an experiment, your username appears in:

**Folder Names:**
```
2026-02-08_MyExperiment_JohnSmith/
```

**Metadata Files:**
```json
{
  "user": "John Smith",
  "timestamp": "2026-02-08T14:23:45",
  "user_title": "Specialist",
  "user_experiments": 34
}
```

**Excel Exports:**
- User column in data tables
- Operator field in metadata sheets

---

### User Management for Labs

#### Best Practices

**For Lab Managers:**
- Create profiles for all authorized users
- Use full names (not initials) for traceability
- Regularly review user list to remove former staff
- Monitor progression to identify training needs

**For Individual Users:**
- Always select your name before starting work
- Don't share accounts (creates audit trail issues)
- Progression titles reflect experience level
- Contact admin if your profile is missing

#### GLP/GMP Compliance

**Regulatory Requirements:**
- User attribution is mandatory for GLP/GMP
- All data files include operator information
- Timestamps track when users performed actions
- Audit trail shows who exported/modified data

**What's Tracked:**
- Username (full name)
- Experiment count (experience level)
- Timestamps for all actions
- File modifications and exports

---

### Troubleshooting User Management

#### Can't Add User

**Problem:** "+ Add User" button doesn't work
- Check if username already exists (case-sensitive)
- Don't use empty names or only whitespace
- Special characters are allowed

#### User Disappeared from List

**Solution:**
- Check `user_profiles.json` in config folder
- File location: `C:\Users\[YourName]\AppData\Local\Affilabs\user_profiles.json`
- Restore from backup if corrupted
- Contact support if data lost

#### Progression Not Updating

**Causes:**
- Experiment wasn't saved to GLP folder structure
- Data exported to wrong location
- Config file permissions issue

**Fix:**
- Ensure experiments are saved properly
- Check that exports use GLP folder structure
- Verify write permissions on config folder

#### Default User Can't Be Deleted

**By Design:**
- System requires at least one user
- Add your own profile first
- Then delete "Default User" if desired

---

## Appendix: Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| **Ctrl+P** | Power On/Off device |
| **Ctrl+R** | Start/Stop recording |
| **Ctrl+S** | Save method / Export data |
| **Ctrl+O** | Open/Load file |
| **Ctrl+E** | Export sensorgram as PNG |
| **Space** | Pause/Resume acquisition |
| **+/-** | Zoom in/out on graph |
| **Arrow Keys** | Move cursors (when focused) |

---

## Appendix: File Locations

### Windows Default Paths

```
C:\Users\[YourName]\Documents\
├── Affilabs_Data\              # Experiment folder hierarchy
│   └── [Date]_[Name]_[User]\
│       ├── Raw_Data\           # Live tab exports
│       ├── Analysis\           # Edit tab exports
│       ├── Figures\
│       ├── Method\
│       └── QC_Reports\
│
└── Affilabs Methods\           # Method library
    └── [YourName]\
        ├── method_1.json
        └── method_2.json
```

### Application Config

```
C:\Users\[YourName]\AppData\Local\Affilabs\
├── config\                    # Device configuration
├── logs\                       # Error/debug logs
└── user_profiles.json          # User management
```

---

---

## ⚠️ SAFETY & LIABILITY SUMMARY

### Critical Operating Rules (Non-Negotiable)

1. **Air Bubbles**: The single biggest system issue
   - Inspect syringe before EVERY injection
   - Prime lines before every run
   - Use pulse injections to clear if air enters
   - Stop immediately if baseline drift > 1 nm/min

2. **Sensor Handling**: Premium equipment requiring extreme care
   - **ALWAYS wear nitrile gloves** - bare hands damage permanently
   - **NEVER touch sensor surface** with anything
   - **NEVER wipe or clean** sensor surface yourself
   - Gold surface is delicate - one touch = signal degradation
   - Sensor damage is IRREVERSIBLE and user's responsibility

3. **System Maintenance**: Follow schedules strictly
   - Daily air bubble & baseline checks before every run
   - Weekly maintenance including sensor visual inspection
   - Quarterly deep cleaning & calibration
   - Contact manufacturer for sensor cleaning

### User Responsibility & Liability

**The user assumes full responsibility for:**
- Proper sensor handling per this manual
- Avoiding air bubbles during operation
- Regular maintenance schedule compliance
- Reporting any signal degradation immediately
- Not attempting unauthorized repairs or cleaning

**Affilabs is NOT responsible for:**
- Sensor damage from bare-hand contact
- Sensor damage from tissue wiping or cleaning
- Damage from improper storage or handling
- Signal degradation from surface contamination
- Air bubble damage to system components
- Damage from non-compliance with this manual

### Emergency Contacts

- **Sensor Damage**: Contact Affinité Instruments immediately
- **System Malfunction**: [Support contact]
- **Software Issues**: [Support contact]

---

**Last Updated:** 2026-02-07
**Manual Version:** 1.0
**Status:** PRODUCTION - CRITICAL SAFETY REQUIREMENTS
**For questions or corrections, contact:** [Development Team]

**⚠️ This manual contains critical safety information. All users MUST read and understand the sensor handling and air bubble prevention sections before operating the system.**

