# Affilabs.core v2.0.5.1 - Operation Manual

**Software Version:** 2.0.5.1
**Release Date:** March 1, 2026
**Status:** Release
**Supported Detectors:** Affi Detector

---

## Table of Contents

1. [Quick Start Guide](#quick-start-guide)
   - [Startup Calibration Failures](#startup-calibration-failures)
2. [System Overview](#system-overview)
3. [Software Purpose & Scope](#software-purpose--scope)
4. [Creating a Method](#creating-a-method)
5. [Recording an Experiment](#recording-an-experiment)
6. [Editing & Analyzing Data](#editing--analyzing-data)
7. [Notes Tab — Electronic Lab Notebook](#notes-tab--electronic-lab-notebook)
8. [Data Export Formats](#data-export-formats)
9. [Accessibility & Display Settings](#accessibility--display-settings)
10. [Manual Operation](#manual-operation)
    - [Sensor Installation (P4PRO & P4SPR 2.0)](#sensor-installation-p4pro--p4spr-20)
    - [Channel Addressing & Volume Guidelines](#channel-addressing--volume-guidelines)
    - [Manual Pump Control](#manual-pump-control)
11. [User Management](#user-management)
    - [Creating User Profiles](#creating-user-profiles)
    - [User Progression System](#user-progression-system)
    - [Switching Between Users](#switching-between-users)
12. [Maintenance](#maintenance)
13. [Software Compatibility](#software-compatibility)

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
   - Double-click the **Affilabs-Core** shortcut on your desktop (or Start Menu → Affilabs-Core)
   - The main window loads within a few seconds
   - The Power button (top-right Transport Bar) starts **red** (disconnected)

3. **Power On — Connect Hardware**
   - Click the **Power** button (⏻) in the Transport Bar (top-right area)
   - The button turns **yellow** while scanning for the detector and controller
   - Once hardware is found, startup calibration begins automatically
   - A calibration dialog shows LED convergence progress and S-pol reference capture (~30–60 s)
   - **If calibration passes:** the QC dialog shows pass/fail per channel (FWHM, SNR, convergence iterations) → click **Continue** → Power button turns **green**
   - **If calibration fails:** see [Startup Calibration Failures](#startup-calibration-failures) below

4. **Select User Profile**
   - Click the **User** icon on the Icon Rail (left sidebar)
   - Choose your name from the Lab Users panel
   - This tracks who ran each experiment in exports and logs

5. **Create Your First Method**
   - Go to **Live tab** → Method Builder (sidebar)
   - Add baseline cycle → binding cycles → regeneration
   - Click **Save Method**

6. **Start Recording**
   - Click **Start Run** button
   - Data streams in real-time on the graph
   - Cycles execute automatically

---

### Startup Calibration Failures

If the calibration dialog shows a failure, the software diagnoses the likely root cause based on your device's history.

#### QC pass/fail criteria

| Check | Good | Warning | Fail |
|-------|------|---------|------|
| FWHM (nm) | < 60 | 60–100 | > 100 |
| SNR | > 20 | 10–20 | < 10 |
| Convergence | < 10 iterations | 10–20 | > 20 or timeout |
| Signal level | ≥ 7500 counts | 5000–7500 | < 5000 |

Warnings are non-blocking (calibration accepted). Failures block acceptance.

#### Failure triage

The failure message includes a suggested action based on your device's history:

| Scenario | Likely cause | Action |
|----------|-------------|--------|
| Device has calibrated successfully before | Water or debris in optical path | Dry or flush the flow cell, then click **Retry** |
| Device has never calibrated successfully | Hardware issue (fiber, LED, detector) | Contact Affinité Support |
| Only one channel fails | That LED or flow cell channel | Check the specific channel; flush and retry |

**Most common cause:** Water droplets in the microfluidic cell or on the prism face during calibration. Dry the cell with a flush of dry buffer, wait 10 s, then click **Retry**.

#### Buttons in the failure dialog

| Button | What it does |
|--------|-------------|
| **Retry** | Re-runs the full calibration sequence |
| **Continue Anyway** | Bypasses the failed calibration — instrument enters bypass mode; acquisition is allowed but results may be unreliable |

> **Continue Anyway** is intended for emergency runs only. Acquisition in bypass mode uses default LED intensities and no S-pol reference — ΔSPR values will be inaccurate.

---

## System Overview

### Hardware Components

| Component | Model | Notes |
|-----------|-------|-------|
| Detector | Affi Detector | Auto-detected on Power On |
| LED PCB | Luminus Cool White (4 channels) | Time-multiplexed A → B → C → D |
| Controller | Raspberry Pi Pico (P4SPR / P4PRO) | V2.4 firmware (CYCLE_SYNC mode) |
| Servo Motor | HS-55MG | Rotates between P-pol and S-pol |
| Optical Fiber | 200 μm diameter | Connects prism to detector |

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

**Affi Detector:**

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

### Hardware Models

Affilabs.core supports three instrument models. The software auto-detects which model is connected.

| Feature | **SimplexSPR (P4SPR)** | **SimplexFlow (P4PRO)** | **SimplexPro (P4PROPLUS)** |
|---------|------------------------|-------------------------|---------------------------|
| Injection | **Manual syringe** (user pipettes) | **Semi-automated** — 6-port valve + AffiPump | **Semi-automated** — 6-port valve + internal pumps |
| Fluidic channels | **4 independent** — inject different samples into A, B, C, D simultaneously | **2 per cycle** — valve routes to AC pair or BD pair | **2 per cycle** — same as P4PRO |
| Power | USB only (5V) | 24V Affinité power bar required | 24V Affinité power bar required |
| Pump | None (or optional AffiPump) | AffiPump (external syringe pump — pulse-free) | Built-in peristaltic pumps |
| Mode in software | Manual (locked) | Semi-Automated (default) | Semi-Automated (default) |
| Flow tab | Hidden | Visible | Visible |

**P4SPR note:** Manual injection means the user physically pipettes sample into each inlet port. Channels A, B, C, D are fully independent — you can inject four different samples in one experiment. Sequential pipetting can introduce up to ~15 s of inter-channel timing offset; the Interactive SPR Legend nudge feature corrects for this in post-analysis.

**P4PRO/PROPLUS note:** The 6-port valve routes sample to one pair of channels at a time (AC or BD). To screen four samples, run two sequential injection cycles. The Flow tab (left sidebar) controls valve routing and pump parameters.

Sections of this manual that are hardware-specific are labelled **(P4SPR)** or **(P4PRO/PROPLUS)** where relevant.

### Software Architecture

**Three-Tab Workflow:**

| Tab | When | Purpose |
|-----|------|---------|
| **Live** | During acquisition | Real-time sensorgram, hardware controls, method queue, injection monitoring |
| **Edits** | After recording | Load, align, fit, measure Δ-SPR, export |
| **Notes** | Before / during / after | Plan experiments, search history, tag and rate runs, build ELN entries |

---

## Software Purpose & Scope

### What Affilabs.core Does

**Affilabs.core v2.0** is a specialized software for **high-quality data acquisition and annotation** on the P4SPR surface plasmon resonance system.

**Core Functions:**
1. **Acquire high-quality sensor data** - Real-time streaming from the Affi Detector (4 independent channels: A, B, C, D)
2. **Execute experimental protocols** - Run predefined method sequences (baseline → concentration → regeneration → wash cycles)
3. **Annotate during acquisition** - Add flags, notes, and markers in real-time to document events
4. **Enable basic data editing** - Measure binding response (Δ-SPR), align cycles, validate quality
5. **Export publication-ready data** - Create Excel files compatible with external analysis software

### What Affilabs.core Does NOT Do

Some advanced workflows are out of scope or delegated to external tools:

- ❌ **Statistical analysis across experiments** (use R, Python, Prism, or GraphPad)
- ❌ **Publication figure generation** (use Origin, Prism, Python/Matplotlib)
- ❌ **AnIML / SiLA 2 / LIMS integration** (planned for future versions)

> **Note:** Basic kinetic fitting (ka, kd, KD from association phases) and Langmuir binding curve fitting are available directly in the Edits tab Binding Plot. For complex multi-cycle global fitting, use Prism with the exported Excel data (TraceDrawer compatibility coming soon).

### Design Philosophy: Separation of Concerns

Affilabs.core follows a **three-phase workflow**:

```
┌─────────────────────────────────────────────────────┐
│  PHASE 1: CAPTURE (Live Tab)                        │
│  ─ Acquire raw sensor data                          │
│  ─ Execute method queue                             │
│  ─ Real-time signal quality monitoring (Sensor IQ)  │
│  ─ Automatic injection & wash detection             │
│  ─ Optical fault alerts (leak, bubble)              │
│  → OUTPUT: Auto-saved .xlsx every 60 s              │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  PHASE 2: ANALYSIS (Edits Tab)                      │
│  ─ Load raw data                                    │
│  ─ Measure Δ-SPR with cursors                       │
│  ─ Fit binding curves (Langmuir / Kinetics)         │
│  ─ Align cycles, subtract reference channel        │
│  ─ Validate data quality, annotate                  │
│  → OUTPUT: Analysis_YYYYMMDD_HHMMSS.xlsx            │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  PHASE 3: RECORD & PLAN (Notes Tab)                 │
│  ─ Tag and rate completed experiments               │
│  ─ Search experiment history                        │
│  ─ Plan future runs, attach methods                 │
│  ─ Build ELN entries                                │
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
| Kinetic analysis (Kd, kon, koff) | **Prism**, Affilabs.analysis | Import the Excel export directly; TraceDrawer compatibility coming soon |
| SPR data visualisation & fitting | **Prism**, TraceDrawer *(coming soon)* | TraceDrawer compatibility under validation |
| Statistical tests | Excel, R, Prism, Python | Affilabs.core provides data only |
| Figure generation | Origin, Prism, Python, Matplotlib | Export data, create figures externally |

---


## Creating a Method

A **Method** is a predefined sequence of cycles (baseline → binding → regeneration).

### Method Builder Interface

**Open:** Click **Build Method** in the Transport Bar (top), or via the Live tab sidebar.

The Method Builder has three zones:

| Zone | Purpose |
|------|---------|
| **Template Gallery** | Start from a built-in template or browse all presets |
| **Step List** | Edit the cycle sequence — one row per step |
| **Sparq Bar** | Natural-language method building ("add 5 kinetic cycles") |

### Starting from a Template

Four built-in templates are available:

| Template | Use case |
|----------|---------|
| **Binding** | Basic affinity screening — baseline → N×binding |
| **Kinetics** | Association + dissociation per cycle (P4PRO/PROPLUS) |
| **Amine Coupling** | Immobilization workflow — activation → ligand → blocking → baseline → binding |
| **Custom** | Blank canvas |

Click a template to load it into the Step List, then edit individual cycles as needed.

### Editing the Step List

Each row in the Step List is one cycle. Click any cell to edit.

**[+ Add step ▾]** dropdown adds a new cycle of the chosen type at the bottom:
- **Baseline** — sensor equilibration (typical: 5 min)
- **Binding** — analyte contact (typical: 8–10 min; sets contact timer, enables injection detection)
- **Regeneration** — surface clean (typical: 3 min)
- **Wash** — buffer flush (typical: 2 min)
- **Custom** — any duration/label

**Cycle parameters:**
```
Cycle Type:     Binding
Concentration:  100 nM
Units:          nM / µM / pM / mg/mL / %
Duration (min): 10
Volume (µL):    200
Notes:          (optional label shown on sensorgram)
```

> **P4SPR note:** Keep binding cycles to 8–10 min. Longer cycles work but the sensorgram window becomes hard to read while you are also pipetting. Post-run cursor placement and Δ-SPR measurement happen in the Edits tab regardless of cycle length.

### Using the Sparq Bar

Type a natural-language request in the Sparq bar at the bottom of the dialog:

- `"add 5 binding cycles at 1, 3, 10, 30, 100 nM"`
- `"amine coupling workflow"`
- `"kinetics titration"`

Sparq translates the request into step-list rows. Review and edit before pushing to queue.

### Complete Method Example — Affinity Measurement (P4SPR)

| Cycle # | Type | Duration | Concentration | Notes |
|---------|------|----------|---------------|-------|
| 1 | Baseline | 10 min | — | Sensor equilibration |
| 2 | Binding | 8.5 min | 1 nM | Lowest concentration |
| 3 | Binding | 8.5 min | 10 nM | — |
| 4 | Binding | 8.5 min | 100 nM | — |
| 5 | Binding | 8.5 min | 1000 nM | Saturation |

Regeneration between binding cycles is done manually by the user (pipette regenerant, wait, pipette buffer) during the binding incubation window — it does not need its own queue entry for P4SPR. Alignment and baseline subtraction are handled in the Edits tab.

### Save and Load Methods

- **Save:** Enter a method name → click **Save Method** → saved as `.json` in `Documents/Affilabs Methods/[YourName]/`
- **Load:** Click **Load Method** → select from list → method loads into the Step List
- **Push to Queue:** Click **Add to Queue** — method cycles appear in the queue panel on the Live tab

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

1. **Click Record** (⏺) in the Transport Bar
   - Queue begins executing; green "Recording" indicator appears
   - Timeline graph shows data acquisition
   - Auto-save runs every 60 s to `Documents/Affilabs Data/`

2. **Pause/Resume**
   - **Pause** (⏸) in Transport Bar: temporarily stops acquisition
   - **Resume**: continue from pause point
   - Pause/resume markers appear on the timeline graph

3. **Click Stop** (⏹) when the experiment is complete
   - Recording stops; final auto-save runs
   - Data ready to load in the Edits tab

---

### Sensor IQ — Real-Time Signal Quality

Affilabs.core classifies signal quality continuously during acquisition. The result is shown as colour-coded dots in the Active Cycle legend.

| Colour | IQ Level | Meaning |
|--------|----------|---------|
| Green | Excellent / Good | Signal in optimal zone — proceed normally |
| Yellow | Questionable | Borderline — monitor; investigate if sustained |
| Red | Poor / Critical | Action needed — see troubleshooting below |

**What sets the IQ level:**

| Metric | Good range | Concern |
|--------|-----------|---------|
| Resonance wavelength | 590–690 nm | Edge zones 560–590 / 690–720 nm: acceptable but monitor |
| FWHM (dip width) | < 60 nm | 60–100 nm: questionable; > 100 nm: critical |

**FWHM > 100 nm typically means:** air bubble in the optical path, sensor running dry, or heavy contamination. Stop the run, purge air, recheck compression.

**FWHM 60–100 nm typically means:** sensor chip ageing or partial contamination. The run can continue; flag affected cycles for review in Edits tab.

---

### Contact Monitor — Live Injection Tracking (Binding cycles)

When a Binding cycle is running, the **Contact Monitor panel** appears at the bottom of the queue area. No setup needed — it activates automatically.

**What it shows:**

```
  A  ◉  +42 RU   3:12       B  ·○  approaching...
  C  ○  inactive            D  ○   inactive
```

| Symbol | State | Meaning |
|--------|-------|---------|
| ◉ | CONTACT | Injection detected; binding accumulating; timer counting down |
| ·○ | APPROACHING | Signal rising; injection not yet confirmed |
| ○· | WASH | Wash step detected; surface regenerating |
| ○ | INACTIVE | Channel not injected this cycle |

**ΔSPR value** (e.g., `+42 RU`) shows cumulative binding since injection — live, updating every frame.

**Countdown timer** (e.g., `3:12`) counts down from the cycle's contact time. Channels are independent — each timer starts when that channel's injection is detected. **(P4SPR)** This handles the natural 5–15 s lag between pipetting channel A and then B, C, D.

**Wash detection is automatic.** After injection, the monitor watches for a second step-change (buffer returning to baseline). When detected, the channel transitions to WASH state and a wash flag is placed automatically. No button to click.

---

### Optical Fault Alerts

Affilabs.core monitors the raw optical signal for two fault types during live acquisition:

#### Leak detection

**Trigger:** Raw intensity drops to ≤ 25% of calibration baseline and stays there for ≥ 3 s.

**What happens:**
1. Sparq chat panel opens automatically with an alert message and remediation steps
2. Spectrum Bubble (top toolbar) turns red and shows the raw intensity collapse
3. Recording continues — data is preserved

**When the signal recovers (≥ 50% of baseline):**
1. A quick LED recalibration runs automatically (acquisition pauses ~5 s, then resumes)
2. Sparq shows a "signal recovered" message and suggests reviewing the affected cycle in Edits tab
3. Recording is never interrupted — only a brief acquisition pause during recal

**Remediation:** Check for loose microfluidic cell compression, disconnected tubing, or air introduction. See [Sensor Installation](#sensor-installation-p4pro--p4spr-20) for compression guidance.

#### Air bubble detection

**Trigger:** Simultaneous wavelength noise spike AND transmission drop within a short time window.

**What happens:** Sparq chat opens with a bubble alert. The affected data region is marked; the run continues.

**Remediation:** Purge with 3–5 pulse injections (50–100 µL) at high flow rate until bubble is cleared and baseline returns. See [Air Bubble Pulse Clearing Technique](#air-bubble-pulse-clearing-technique).

---

### Flags & Markers

Flags are placed on the sensorgram timeline to mark injection events, wash steps, and anomalies.

**Automatic flags (software-placed):**

| Flag | When placed |
|------|------------|
| ▲ Injection | Injection detection confirms analyte contact |
| ■ Wash | Contact timer expires OR wash step detected by monitor |

You do not need to manually flag injections or washes — the software places them based on signal detection and the Contact Monitor.

**Manual flags (user-placed during acquisition or in Edits tab):**

| Flag | When to use |
|------|------------|
| ◆ Spike | Anomaly — air bubble, noise burst, accidental bump. Marks the region for exclusion in analysis. |

To add a spike flag during a run: right-click on the sensorgram at the anomaly → **Add Spike Flag**.

**AutoMarkers (dashed lines):** The software draws predicted timelines (expected wash deadline, expected injection deadline) as dashed reference lines. These are read-only — they update as the cycle progresses.

**Editing flags in the Edits tab:** Flag positions can be nudged with arrow keys and snap to the nearest data point. See [Editing & Analyzing Data](#editing--analyzing-data).

---

## Editing & Analyzing Data

The **Edits Tab** is where you measure, validate, fit, and prepare final results.

### Loading Data

#### Option 1: Load file directly
1. Go to **Edits Tab**
2. Click **Load Data**
3. Select an auto-saved `.xlsx` from `Documents/Affilabs Data/`
4. Cycles populate the table

#### Option 2: From Notes tab history
1. Go to **Notes Tab** → find the experiment in the list
2. Double-click the row → file loads directly into Edits tab (no file picker)

### Cycle Table

| Column | Description | Editable |
|--------|-------------|----------|
| Type | BL / BN / RG / WS / Custom | No |
| Time | Start time & duration | No |
| Conc | Concentration value | Yes |
| ΔSPR | Per-channel binding response | Set via cursors |
| Flags | ▲ ■ ◆ event markers | Yes (nudge with arrow keys) |
| Notes | Free text per cycle | Yes |

**Keyboard navigation:** ↑ / ↓ arrows move through the table without clicking; the sensorgram updates to the selected cycle.

### Measuring Δ-SPR with Cursors

1. **Select a binding cycle** in the table
2. **Place cursors** on the sensorgram:
   - **Left cursor** (green): injection start (baseline)
   - **Right cursor** (red): end of incubation (fixed timepoint, e.g. 10 min)
3. Δ-SPR values for all four channels update live in the ΔSPR bar chart
4. Values auto-save to the selected cycle

**Lock cursors:** Check the **Lock** checkbox to fix the cursor distance to `contact_time × 1.1`. Both cursors then move together — useful for stepping through cycles at the same timepoint.

**Reference channel subtraction:** Ctrl+click a channel button (A / B / C / D) to set it as the reference. Its signal is subtracted from all other channels. The reference channel button shows a dotted border. Ctrl+click again to clear.

**Tip (P4SPR):** Use the Interactive SPR Legend to correct inter-channel injection timing before measuring (see below).

### Interactive SPR Legend — Channel Selection & Nudge

The **Active Cycle graph** has a floating legend in the top-right corner showing the current Δ-SPR per channel as integers (e.g., `+12`, `−3`).

**Click a channel row** in the legend to select it:
- That channel's curve thickens (4 px)
- Other channels dim

**Nudge the selected channel's X-axis:**
- `←` / `→` arrow keys: ±1 s shift
- `Shift + ←` / `Shift + →`: ±5 s shift

**When to use nudge (P4SPR):** When you pipette channels A → B → C → D sequentially, each injection is 3–5 s later than the previous one. Nudging shifts each channel's curve so all response onsets align — making the Δ-SPR comparison fair.

### Binding Plot & Kd Fitting

Switch to the **Binding** subtab in the Edits tab to open the binding plot and fit controls.

**The binding plot shows:** concentration (X) vs. Δ-SPR (Y) for all cycles with a concentration value assigned.

**Fitting models:**

| Model | Use case | Output |
|-------|---------|--------|
| **Linear** | Low-concentration / screening | Slope (RU/nM) |
| **Langmuir 1:1** | Equilibrium affinity | KD, Rmax |
| **Kinetics** | Association + dissociation phases | ka, kd, KD |

**Rmax calculator:** Enter the Δ-SPR from your immobilization cycle → the calculator estimates surface activity % (measured Rmax / theoretical Rmax).

**Concentration units:** Toggle nM / µM / pM from the unit selector — the X-axis rescales automatically.

To use fitted KD values for publication: export to Excel (the fitted parameters are included in the analysis sheet) or copy to clipboard.

### Alignment & Time Shift

1. Switch to the **Alignment** subtab
2. Select the channel to shift
3. Drag the slider or type an offset (seconds)
4. Graph updates in real time — no Apply button needed
5. Shift is saved to the cycle

### Validation & QC

- **Right-click a cycle** → set QC status: Pass / Fail / Review
- Filter the table by QC status using the filter buttons above the table
- Add notes per cycle to explain exclusions

### Adjusting Flag Positions

1. Click a flag marker on the sensorgram to select it
2. Use **← / →** arrow keys to nudge position (snaps to nearest data point)
3. Shift+arrow for larger steps

---

## Notes Tab — Electronic Lab Notebook

The **Notes Tab** (`Ctrl+3`) is the third main tab — always accessible, even without hardware connected or a file loaded.

```
Live      →   Edits      →   Notes
Acquire       Analyse        Document / Plan / Search
```

Use it to rate experiments, write notes, track what to repeat, plan future runs, and search your full experiment history.

### Three-Panel Layout

| Panel | What's here |
|-------|------------|
| **Left (filter bar)** | Smart filters (All / Needs Repeat / Planned / Unrated) with live counts; tag browser |
| **Centre (list / Kanban)** | All experiments as rows; toggle to Kanban for workflow view |
| **Right (preview + ELN)** | Sensorgram thumbnail, metadata, star rating, tags, notes editor |

### Experiment List

Each row shows: date · description (first line of notes) · star rating · tags · status badge.

- **Single-click** → preview in right panel
- **Double-click** → load directly into Edits tab (no file picker)
- **Right-click** → Load · Open Excel · Reveal in Explorer · Edit tags · Delete from index

### Kanban View

Toggle with the `[# Kanban]` button. Four columns:

| Column | What appears here |
|--------|-----------------|
| **Planned** | Future experiments you've sketched out |
| **Running** | Current live recording (auto-populated) |
| **Done** | Completed experiments, rating ≥ 3 (or unrated) |
| **Needs Repeat** | Rating 1–2 — runs to redo |

Drag cards between columns to update status. The **Running** column is read-only.

### Rating & Tagging

**Star rating (1–5):** Click the stars in the right panel.
- Rating 1 or 2 → entry automatically moves to **Needs Repeat** column and gets `#needs-repeat` tag
- Raising rating above 2 → removes `#needs-repeat` tag

**Tags:** Pill chips in the right panel. Click `[+ Add tag]` to add; tags autocomplete from your full tag history. Click `×` to remove.

**Notes:** Free-text editor (4 visible lines). Auto-saves on focus-out. Supports any plain text — protocol changes, observations, troubleshooting notes.

### Smart Filters

| Filter | Shows |
|--------|-------|
| All Experiments | Everything in the index |
| Needs Repeat | Rating 1–2 |
| Planned | Entries you've planned but not yet run |
| Unrated | No rating set yet |

Click any filter label to apply. Counts update live as you rate and tag.

### Search

Type in the search bar at the top of the centre panel. Full-text search across: notes, tags, chip serial, filename, user name, and date range. All filters and tags are applied on top of the search query.

### Planning a Future Run

Select any Done or Needs Repeat entry → click **Plan Next Run** in the right panel.

Fill in:
- **Description** — what you intend to try
- **Based on** — reference to a past experiment
- **Method** — pre-saved cycle template from the Method Builder
- **Target date** — optional scheduling note

The planned entry appears in the Kanban **Planned** column and in the filtered list.

### Loading Data from Notes

The fastest way to load a past recording into Edits tab:

1. Go to **Notes Tab**
2. Find the experiment (search or scroll)
3. **Double-click** → loads directly into Edits tab

---

## Data Export Formats

> **Design philosophy:** Acquire high-quality data, analyse it in the Edits tab, then export one Excel file with all results and embedded charts. Publication-ready output without touching any other software for routine experiments.

### Workflow: Acquire → Edit → Export

```
Live tab (Acquire)
    │  Record sensorgram data in real-time
    │
    ▼
Edits tab (Analyse)
    │  Align cycles, set cursors, measure Δ-SPR per cycle
    │  Add concentrations, flag outliers, annotate notes
    │
    ▼
Export (one click from Edits tab)
    │  Single Excel file: data + charts
    └─ Ready to share, present, or archive
```

### Raw Data Export (from Live Tab)

**When to use:** Backup or re-analysis from raw signal.
**Format:** Excel (.xlsx)

**Contains:**
- Sheet 1: Raw Data (long format) — Time, Channel, Value
- Sheet 2: Per-Channel — Time_A, A, Time_B, B, Time_C, C, Time_D, D
- Sheet 3: Cycle Table — type, duration, concentration, flags, notes
- Sheet 4: Export Info — date, software version, device serial

### Analysis Export (from Edits Tab)

**When to use:** Primary export — use it at the end of every experiment.
**Format:** Single Excel (.xlsx) with embedded charts.

**Contains:**
- **Cycle analysis sheet** — full table with Δ-SPR per cycle, per channel, flags, QC status, notes, concentration
- **Sensorgram chart** — time-series plot of all channels, aligned and annotated
- **Δ-SPR bar chart** — per-cycle binding response
- **Binding fit results** (if Kd fitting was run) — KD, ka, kd, Rmax
- **Metadata sheet** — experiment info, operator, device, sensor type, analysis settings

Charts are generated automatically — no manual Excel work required.

### Graph Image Export

Right-click any graph in the Edits tab (sensorgram or Δ-SPR bar chart) to export:

| Format | Use case |
|--------|---------|
| **Copy to clipboard** | Paste directly into PowerPoint, Word, or email |
| **Save as PNG** | Presentations, quick sharing |
| **Save as SVG** | Vector — publication-quality, fully scalable |

### Save as Method

In the Edits tab → right-click a cycle row → **Save as Method**. Saves the cycle's step timings, concentrations, and type as a reusable cycle template in the Method Builder.

### External Software Compatibility

The Analysis Export Excel file can be imported into third-party platforms:

| Platform | What it supports |
|---------|----------------|
| **TraceDrawer** *(coming soon)* | Kinetic fitting (kon, koff, Kd) from sensorgram data — recommended for multi-analyte global fitting |
| **GraphPad Prism** | Statistical analysis, dose-response curves from the Δ-SPR table |
| **Origin** | Custom curve fitting, publication charts |

> **TraceDrawer export is coming soon** — direct compatibility is under validation and not yet officially released. In the meantime, import the Analysis Export Excel file manually if needed.

**When to use external fitting:** For global kinetic fits (simultaneous fit of multiple analyte concentrations), use TraceDrawer or similar. Affilabs.core's in-app Kinetics model fits single curves; TraceDrawer fits all concentrations simultaneously.

### Export Info Sheet

Both exports include a metadata block:

```
Export Date:    2026-02-07 14:30:00
Software:       Affilabs-Core v2.0.5
Device:         AFFI09792
Total Cycles:   8
Data Points:    12,450
Channels:       A, B, C, D
```

---

## Accessibility & Display Settings

Open the **Accessibility Panel** by clicking the eye (👁) button in the vertical icon rail on the left edge of the main window. The panel slides in at 380 px wide and collapses the sidebar automatically.

All changes propagate to graphs in real time (except Large Text, which requires restart).

### Colour Palettes

Seven palettes available. All four channels update immediately across all live graphs and the Edits tab.

| Palette | Notes |
|---------|-------|
| **Default** | High-contrast dark/red/blue/green — standard |
| **PuOr (CB-safe)** | Purple–orange — deuteranopia and protanopia safe |
| **Wong (CB-safe)** | Widely used in scientific publications |
| **Tol Bright (CB-safe)** | Paul Tol bright — safe for all colorblindness types |
| **Okabe-Ito (CB-safe)** | Commonly recommended by journals |
| **IBM (CB-safe)** | IBM Design Language palette |
| **Pastel** | Low-saturation — reduces eye strain on bright displays |

Click any palette card to apply. The selected palette shows a blue border.

### Line Styles

Three options: **Solid** / **Dashed** / **Dotted**. Click a card to apply. Affects all live sensorgrams and the Active Cycle graph.

### Active Cycle Dark Mode

Pill toggle in the **Appearance** row. When enabled:
- Active Cycle graph background → near-black (`#0D0D0D`)
- Channel curves → neon colours (matrix green, neon red, electric cyan, neon yellow)
- Useful on dark ambient displays or for screencast presentations

Toggling dark mode off restores the current palette and line style.

### Large Text

Pill toggle below Dark Mode. Scales all key UI text by **1.2×** (e.g. 13 px → 16 px, 21 px → 25 px).

> **Requires restart.** After toggling, a Sparq message appears confirming the change. Restart Affilabs.core to apply.

The setting persists in `config/app_prefs.json` — it survives software updates.

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

**Compression Assistant** *(BETA)*

Affilabs.core includes a built-in **Compression Assistant** that teaches you how to compress the sensor correctly and confirms whether you have a leak — in real time, without guesswork.

> **This is the recommended way to learn compression.** Even experienced operators use it when installing a new sensor type or after a microfluidic cell replacement, because small differences in knob position have a large effect on signal quality and leak risk.

**Access:** Settings → Device Status → "Train Compression"

**What it does:**
- Walks you through compression step by step with on-screen instructions
- Monitors baseline stability live as you turn the knob
- **Detects leak signatures** — sudden drift or signal loss indicates the seal is incomplete
- **Detects over-compression** — noise increase or signal distortion means too much pressure
- Confirms when the compression is in the optimal zone

**Leak check:** The assistant monitors for the optical and fluidic signatures of a leak during compression. If the seal is not properly seated, it will flag this before you start an experiment — avoiding data loss and potential damage to the polarizer optics from water infiltration.

> **BETA notice:** Guidance values (optimal knob position, threshold targets) are estimates based on typical hardware. Always verify the result visually (no visible liquid, stable baseline < 0.5 nm/min) and with a trained operator during first use.

**How to use it:**
1. Start with the knob fully UP (no compression applied)
2. Launch the assistant — it will prompt each adjustment
3. Turn the knob counter-clockwise in small increments as instructed
4. The assistant monitors signal quality at each step
5. Stop when the assistant indicates the optimal zone is reached
6. Note the knob position — use it as your reference for this sensor type

**Best practice:**
- Run the assistant on every new sensor installation and after every microfluidic cell replacement
- Recheck compression if baseline becomes unstable mid-experiment (could indicate the knob shifted)
- Never start an experiment without confirming no leak in the assistant's leak-check step

**Manual compression adjustment (without assistant):**

| Observation | Action | Explanation |
|-------------|--------|-------------|
| Visible liquid leaking from sensor area | Turn knob further COUNTER-CLOCKWISE (increase compression) | Seal is incomplete — more pressure needed |
| Baseline drift > 1 nm/min after installation | Turn knob slightly CLOCKWISE (reduce compression) | Possible over-compression causing microfluidic deformation |
| Signal very noisy or erratic | Turn knob slightly CLOCKWISE (reduce compression) | Over-compression distorting optical path |
| Baseline stable, no leaks | ✓ Optimal compression achieved | Record this knob position for future reference |

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

> **Cleaning kit reminder:** Run the Affinité CLN-KIT maintenance procedure once per week to prevent residue build-up in the fluidic cell. See [Biweekly System Cleaning](#biweekly-system-cleaning-cln-kit) for the full procedure — weekly use is recommended over biweekly if sample throughput is high.

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
   - **Expected lifespan**: ~1 000 hours of cumulative on-time. After this threshold, brightness can decrease noticeably and the spectral balance may shift toward red/infrared, degrading signal quality.
   - **Check LED intensity**: Settings → Device Configuration
     - Current LED intensities:
       - Channel A: 115
       - Channel B: 119
       - Channel C: 92
       - Channel D: 119
     - **Warning signs of degradation:**
       - Variation > 10% between channels
       - Overall intensity loss (baseline signal decreasing over weeks)
       - Color profile shift (signal shifting toward red/infrared)
   - **If LED degradation detected:**
     - Document observed changes (date, intensity values, symptoms)
     - Order replacement LED PCB from Affinité (include your device serial number)
     - Keep a spare LED PCB on hand for critical experiments — lead times can be several weeks
     - **DO NOT attempt to repair or adjust LED** — replacement is the standard procedure

2. **Detector Calibration Status**
   - Settings → Calibration
   - Check last calibration date
   - If > 3 months, recommend recalibration

3. **Polarizer Alignment**
   - Last calibrated: 2025-12-18
   - Status: OK
   - If seeing drift, perform polarizer recalibration

### Quarterly/Annual Maintenance

1. **⚠️ Microfluidic Cell Replacement** (ANNUAL - CRITICAL)
   - **Replace microfluidic cell once per year** — preventive maintenance regardless of visible symptoms
   - The cell undergoes mechanical stress and chemical exposure with each use; cracks and slow leaks develop progressively over time and are not always visible until the leak is significant
   - **Do not wait for a leak to appear** — a cracked cell contaminates the optics and requires urgent unscheduled service
   - Degraded cells cause: reduced optical contact, baseline drift, inconsistent measurements, and leaks (water infiltration into the polarizer apertures)
   - Order a replacement cell from Affinité before your annual maintenance date; keep one spare on hand at all times

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

3. **Fluidic Tubing & Luer Connector Replacement** (ANNUAL)
   - **Replace all luer tubing and connectors once per year** under normal usage; replace sooner if usage is high (> 3 experiments/week) or if any visual degradation is observed
   - **Components that can be replaced in the field:**
     - Silicone and PTFE tubing
     - Luer connectors and fittings
     - Pump seals and O-rings
     - Syringe plungers
     - Check valves
     - Flow restrictors
   - **When to replace early:**
     - Tubing cracks, kinks, or discoloration
     - Visible leaks at connections
     - Pressure readings abnormal (< 0.3 bar or > 2.5 bar)
     - Flow rate decreasing or inconsistent
     - Visible blockages or salt crystallization at joints
   - **For replacement:**
     - Contact Affinité with your device serial number and component description
     - Keep a spare tubing set on hand — tubing is the most frequently replaced component and is easy to swap in the field
     - Pump seals and check valves require technician-level service — contact Affinité
   - **DO NOT attempt to repair** — replacement is the standard procedure

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

## SPR Measurement Tips

### Physical Principles

**SPR signal = refractive index change at the sensor surface.**
Anything that changes the refractive index of the medium near the gold surface will shift the resonance wavelength — not just specific binding. Understanding this is essential for designing reliable experiments.

| Effect | Impact on signal | Mitigation |
|--------|-----------------|------------|
| Temperature increase | Baseline drifts (refractive index of water is temperature-dependent) | Allow 30 min thermal equilibration; keep lab temperature stable |
| Pressure spike (e.g. bubble clearing, pump pulsation) | Transient spike or step jump in all channels simultaneously | Use pulse injections carefully; inspect for air before starting |
| Bulk refractive index mismatch (sample buffer ≠ running buffer) | Large rectangular artifact at injection start and end | Match sample to running buffer; use reference channel subtraction |
| Non-specific binding | Slow creep across all channels | Always use a reference channel; subtract it from analyte channels |

### Always Use a Reference Channel

A reference channel is a flow cell with no immobilised ligand (or a control surface) that experiences the same bulk effects — temperature, pressure, and non-specific adsorption — as your analyte channel.

- Subtract the reference sensorgram from the analyte sensorgram to isolate specific binding signal
- Without reference subtraction, temperature drift and bulk shifts are indistinguishable from real binding events
- **Rule:** never report Kd values from a single channel without reference correction

### Sensitivity and Target Size

SPR signal amplitude scales with the mass of analyte accumulating on the surface. Small molecules produce inherently weaker signals.

| Analyte size | Expected signal | Notes |
|-------------|----------------|-------|
| > 50 kDa | Strong — easily detectable at low nM | Standard kinetic experiments straightforward |
| 1–50 kDa | Moderate — detectable at high nM range | Optimise surface density; use good reference |
| < 1 kDa | Weak — difficult to detect reliably | Consider fragment screening protocols; maximise ligand density |

**Practical threshold:** Expect reliable, reproducible signal with targets above **1 kDa** at concentrations in the **high nM range**. Below this size, signal-to-noise requires careful optimisation.

### Weak Binders and Dissociation During Wash

For interactions with fast off-rates (high k_off, high K_D), dissociation begins as soon as the sample injection ends and buffer wash starts. On a sensorgram this appears as:

- A rapid drop during the wash phase that mirrors the association slope
- The signal may return to near-baseline before the wash cycle ends
- **Do not mistake this for a failed experiment** — it is the dissociation phase of a weak binder

To capture dissociation kinetics for weak binders:
- Use a shorter wash injection (or no wash) and measure at end-of-injection
- Increase association concentration to drive more signal before dissociation competes
- Consider equilibrium (steady-state) analysis rather than full kinetic fitting if dissociation is too fast to measure accurately

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
| **Temperature** | -30°C to +70°C (operational) | Affi Detector operational range |
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
Software Name:        Affilabs.core
Version:             2.0.5
Release Date:        February 24, 2026
Status:              Production Release
Device Compatibility: Affi Detector
```

### Version History

| Version | Date | Changes | Status |
|---------|------|---------|--------|
| **2.0.5** | 2026-02-24 | Notes tab, accessibility panel, binding plot enhancements, Sparq AI tips, experiment index, timeline events, transport bar, icon rail | **Current** |
| 2.0 | 2026-01-30 | Live/Edit two-phase workflow, GLP/GMP organization, auto-save Δ-SPR | Superseded |
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

**Check current version:** Settings → About Affilabs.core

- Updates are distributed as new installer packages
- Contact Affinite Instruments for update availability: info@affiniteinstruments.com

### Getting Help

- **In-app assistant**: Open the Sparq AI sidebar tab for contextual help
- **Documentation**: `docs/` folder in installation directory
- **Known issues**: See [KNOWN_ISSUES.md](KNOWN_ISSUES.md)
- **Hardware compatibility**: See [HARDWARE_COMPATIBILITY.md](HARDWARE_COMPATIBILITY.md)
- **Contact support**: info@affiniteinstruments.com

---

---

## User Management

### Overview

Affilabs.core includes a built-in user management system to track who runs experiments and help users progress from novice to expert operators.

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
- **System Malfunction**: info@affiniteinstruments.com
- **Software Issues**: info@affiniteinstruments.com

---

## Affinité Resources

### Surface Chemistry & Sensors

Affinité offers a broad range of sensor surface chemistries designed for both small and large molecule applications — from fragment screening to antibody characterisation. Whether you are working with proteins, peptides, lipids, nucleic acids, or small drug-like molecules, there is a surface chemistry suited to your assay.

Contact Affinité to discuss which surface is right for your target: **info@affiniteinstruments.com**

### Assay Development Support

Setting up an SPR assay for the first time — or struggling with a difficult target? Affinité's application scientists can help with:

- Surface chemistry selection and immobilisation strategy
- Buffer and regeneration scouting
- Concentration series design for Kd determination
- Troubleshooting baseline drift, non-specific binding, or weak signal

**Contact us:** info@affiniteinstruments.com

### Feedback

Think we can do better? We want to hear from you.

Affilabs.core is continuously improved based on user feedback. If something is confusing, missing, or could work better — tell us. Every report is read by the development team.

**Share your feedback:** info@affiniteinstruments.com

---

**Last Updated:** 2026-03-01
**Manual Version:** 2.0.5.1
**Status:** PRODUCTION - CRITICAL SAFETY REQUIREMENTS
**For questions or corrections, contact:** info@affiniteinstruments.com

**⚠️ This manual contains critical safety information. All users MUST read and understand the sensor handling and air bubble prevention sections before operating the system.**

