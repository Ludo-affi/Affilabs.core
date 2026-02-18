# Spark AI — Method Building Master Training Guide

**Date:** February 2026
**Training Type:** Pattern Matching + Knowledge Base (Fast Path + Deep Retrieval)
**Knowledge Domain:** Method Building, Cycle Syntax, Experiment Design, Injection Control

---

## Overview

This is the definitive guide for building SPR experiment methods in Affilabs ezControl. It covers every cycle type, every syntax keyword, every modifier, every shortcut, every template, and every common workflow. Spark should use this document as the authoritative source when answering any question about creating methods.

### What is a Method?

A **Method** is an ordered sequence of **Cycles** that defines an entire SPR experiment. Each cycle is a timed segment with a specific purpose (stabilize baseline, inject analyte, regenerate surface, etc.). Methods are built in the **Method Builder** dialog, queued, and then executed automatically.

```
Method = "Anti-IgG Titration"
├── Cycle 1: Baseline (5 min)          ← Stabilize signal
├── Cycle 2: Binding A:10nM (5 min)    ← Inject lowest concentration
├── Cycle 3: Regeneration (30 sec)     ← Strip analyte
├── Cycle 4: Baseline (2 min)          ← Re-stabilize
├── Cycle 5: Binding A:50nM (5 min)    ← Next concentration
├── Cycle 6: Regeneration (30 sec)
├── Cycle 7: Baseline (2 min)
├── ...                                ← Repeat for each concentration
└── Auto-Read (2 hours)                ← Automatic monitoring after last cycle
```

---

## How to Open the Method Builder

1. Click **+ Build Method** in the left sidebar (Method tab)
2. The Method Builder dialog opens with:
   - **Note field** (top) — where you type cycle lines and Spark commands
   - **Method table** (middle) — shows queued cycles with type, duration, notes
   - **Details tab** — shows injection settings (channels, concentration, contact time)
   - **Controls** (bottom) — Add to Method, Push to Queue, Save, Load

---

## Cycle Types — Complete Reference

There are **8 cycle types** in ezControl. Each has specific behaviors for injection, contact time, and detection.

| Type | Abbreviation | Injection | Default Contact Time | Purpose |
|------|-------------|-----------|---------------------|---------|
| **Baseline** | BL | None | — | Running buffer only — establish stable signal before/after injection cycles |
| **Binding** | BN | Simple (or partial) | 300 s (5 min) | Manual injection — incubate analyte for a set contact time. No flow-based dissociation. Best for P4SPR manual syringe workflows |
| **Kinetic** | KN | Simple (or partial) | 300 s (5 min) | Flow injection — association + dissociation phases. Requires flow rate. Best for pump-driven experiments |
| **Regeneration** | RG | Simple | 30 s | Strip bound analyte from sensor surface, restore baseline. Short contact with regeneration buffer |
| **Immobilization** | IM | Simple | User-specified | Attach ligand to sensor surface (EDC/NHS coupling, biotin-streptavidin, etc.) |
| **Blocking** | BK | Simple | User-specified | Block unreacted surface sites after immobilization (ethanolamine, BSA, etc.) |
| **Wash** | WS | Simple | User-specified | Rinse flow path between steps (removes carryover, air bubbles) |
| **Other** | OT | None | — | Custom step (activation, equilibration, incubation, any non-standard step) |

### Cycle Type Details

**Baseline (BL)**
- No injection happens. Buffer flows continuously.
- Use at the start of every method to establish a stable reference signal.
- Use between injection cycles to re-stabilize before the next sample.
- Typical duration: 2–5 min for inter-cycle, 5–15 min for initial stabilization.
- `overnight` keyword sets 8-hour baseline for stability testing.

**Binding (BN)**
- For **manual injection** workflows (P4SPR syringe injection).
- User physically injects sample; the system detects the injection and starts a contact timer.
- Contact time counts down from injection detection; when it expires, a wash flag is placed automatically.
- Default 300 s (5 min) contact if not specified. Override with `contact Ns`.
- Use `partial` modifier for 30 µL spike instead of full loop.
- Alias keywords recognized: `binding`, `bn`, `cn`, `concentration`, `conc`, `association`, `inject`.

**Kinetic (KN)**
- For **pump-driven** experiments (P4PRO, P4PRO+, AffiPump).
- Pump delivers analyte at a set flow rate for association phase.
- After contact time expires, buffer resumes for dissociation phase within the same cycle.
- Requires flow rate (`fr N` or `flow N`).
- Default 300 s contact if not specified.
- Alias keywords: `kinetic`, `kinetics`, `kn`.

**Regeneration (RG)**
- Short, aggressive contact to strip bound analyte.
- Default 30 s contact time.
- Typically uses harsh buffer: 10 mM Glycine pH 2.0, 50 mM NaOH, etc.
- Alias keywords: `regeneration`, `regen`, `rg`, `clean`.

**Immobilization (IM)**
- Attaches capture ligand to the sensor surface.
- Contact time **must be specified** by the user (no default).
- Part of surface preparation workflow (amine coupling, biotin-streptavidin, etc.).
- Alias keywords: `immobilization`, `immobilize`, `immob`, `im`.

**Blocking (BK)**
- Blocks unreacted binding sites after immobilization.
- Contact time must be specified.
- Common blocking agents: 1 M ethanolamine, BSA, casein.
- Alias keywords: `blocking`, `block`, `bk`.

**Wash (WS)**
- Rinses flow path to remove residual sample or regeneration buffer.
- Contact time must be specified.
- Alias keywords: `wash`, `ws` (matched as standalone word only).

**Other (OT)**
- No injection. Used for any custom step: EDC/NHS activation, equilibration, custom incubation.
- No contact time assigned.
- Alias keywords: `other`, `custom`, `ot`.

---

## Cycle Syntax — The Line Format

Each cycle is defined as **one line** of text in the Note field. The format is:

```
Type Duration [ChannelTags] contact Ns [modifiers]
```

### Parts of a Cycle Line

| Part | Required? | Description | Examples |
|------|-----------|-------------|---------|
| **Type** | Yes | Cycle type name or abbreviation | `Baseline`, `BN`, `KN`, `RG`, `IM` |
| **Duration** | Yes | How long the cycle runs | `5min`, `30sec`, `2h`, `overnight` |
| **[Channel Tags]** | No | Channel + optional concentration | `A:100nM`, `B:50µM`, `ALL:25pM` |
| **contact Ns** | No | Injection contact time | `contact 180s`, `contact 3min`, `ct 5h` |
| **partial** | No | Use partial injection (30 µL spike) | `partial` or `partial injection` |
| **manual / automated** | No | Override injection mode | `manual`, `automated` |
| **detection priority/off** | No | Override injection detection | `detection priority`, `detection off` |
| **channels XX** | No | Restrict to specific channels | `channels AC`, `channels BD` |
| **fr N** | No | Flow rate in µL/min | `fr 50`, `flow 100` |
| **iv N** | No | Injection volume in µL | `iv 25` |

### Multiple Cycles at Once

Type **one cycle per line** in the Note field. All lines are parsed when you click **Add to Method**:

```
Baseline 5min
Binding 5min A:100nM contact 180s
Regeneration 30sec ALL:50mM
Baseline 2min
```

This adds 4 cycles to the method table in one click.

---

## Duration Shortcuts

All duration formats recognized by the parser:

| Format | Meaning | Example |
|--------|---------|---------|
| `Ns` or `Nsec` | N seconds | `30s`, `30sec` |
| `Nm` or `Nmin` | N minutes | `5m`, `5min` |
| `Nh` or `Nhr` or `Nhour` | N hours | `2h`, `2hr`, `24hour` |
| `overnight` | 8 hours (auto) | `Baseline overnight` |
| *(none)* | Default 5 min | `Baseline` → 5 min |

**Important:** Durations > 3 hours auto-enable **Overnight Mode** to prevent accidental long runs.

---

## Contact Time Syntax

Contact time controls how long the analyte stays in contact with the sensor after injection before the wash flag is placed.

| Format | Meaning | Example |
|--------|---------|---------|
| `contact Ns` | N seconds | `contact 180s` |
| `contact Nm` or `contact Nmin` | N minutes | `contact 3min` |
| `contact Nh` or `contact Nhr` | N hours | `contact 5h` |
| `ct Ns` | Shorthand for contact | `ct 180s` |
| `ct Nm` | Shorthand minutes | `ct 3min` |
| *(none on Binding/Kinetic)* | Default 300 s (5 min) | `Binding 5min A:100nM` → 300s contact |
| *(none on Regeneration)* | Default 30 s | `Regeneration 30sec` → 30s contact |

**Auto-Overnight:** Contact time > 3 hours automatically enables Overnight Mode.

### Default Contact Times by Cycle Type

| Cycle Type | Default Contact (if not specified) |
|---|---|
| Binding | 300 s (5 min) |
| Kinetic | 300 s (5 min) |
| Regeneration | 30 s |
| Immobilization | Must be specified by user |
| Blocking | Must be specified by user |
| Wash | Must be specified by user |
| Baseline | N/A (no injection) |
| Other | N/A (no injection) |

---

## Concentration & Channel Tags

Tags document which channel gets which concentration. They are embedded in the cycle line.

### Tag Format

```
Channel:ValueUnit
```
or with optional brackets:
```
[Channel:ValueUnit]
```

### Channels

- `A`, `B`, `C`, `D` — Individual SPR channels
- `ALL` — All four channels
- Lowercase also accepted: `a`, `b`, `c`, `d`

### Supported Concentration Units

| Unit | Meaning |
|------|---------|
| `nM` | Nanomolar |
| `µM` | Micromolar |
| `pM` | Picomolar |
| `mM` | Millimolar |
| `M` | Molar |
| `mg/mL` | Milligrams per milliliter |
| `µg/mL` | Micrograms per milliliter |
| `ng/mL` | Nanograms per milliliter |

### Tag Examples

| Syntax | Meaning |
|--------|---------|
| `A:100nM` | Channel A at 100 nM |
| `B:50µM` | Channel B at 50 µM |
| `ALL:25pM` | All channels at 25 pM |
| `A:100nM B:50nM` | Channel A at 100 nM, Channel B at 50 nM |
| `[A:100nM]` | Same as `A:100nM` (brackets optional) |
| `A:1mg/mL` | Channel A at 1 mg/mL (mass concentration) |

**Note:** Tags are for documentation/tracking. They don't control the physical injection volume — they record what concentration the user injected.

---

## Injection Modifiers

### Injection Method

| Modifier | Effect |
|----------|--------|
| *(default)* | Simple injection — full sample loop via valve switching |
| `partial` or `partial injection` | Partial injection — 30 µL spike (less reagent, quick test) |

### Injection Mode Override

| Modifier | Effect |
|----------|--------|
| `manual` or `manual injection` | Force manual syringe injection for this cycle |
| `automated` or `automated mode` | Force pump-driven injection for this cycle |

### Detection Override

| Modifier | Effect |
|----------|--------|
| `detection priority` | High-sensitivity injection detection |
| `detection off` | Disable auto-detection (must place flags manually) |
| `detection auto` | Default mode-dependent detection |

### Channel Override

| Modifier | Effect |
|----------|--------|
| `channels A` | Restrict to channel A only |
| `channels BD` | Restrict to channels B and D |
| `channels AC` | Restrict to channels A and C |
| `channels ALL` | All channels (default) |

---

## Flow Rate & Injection Volume Shorthand

| Shorthand | Long Form | Example |
|-----------|-----------|---------|
| `fr N` | `flow N` | `fr 50` = flow rate 50 µL/min |
| `iv N` | | `iv 25` = injection volume 25 µL |

### Recommended Flow Rates

| Purpose | Flow Rate |
|---------|-----------|
| Binding / Association | 25–100 µL/min |
| Dissociation | 25–100 µL/min |
| Regeneration | 100–200 µL/min |
| Wash / Rinse | 200–500 µL/min |
| Priming | 500–1000 µL/min |

---

## Cycle Type Abbreviations — Complete List

Use these anywhere a cycle type is expected:

| Abbreviation | Full Name | Parser Regex |
|---|---|---|
| `BL` | Baseline | `\bbl\b` or `baseline` |
| `BN` | Binding | `\bbn\b` or `binding` |
| `CN` | Concentration (→ Binding) | `\bcn\b` or `concentration` |
| `AS` | Association (→ Binding) | `association` |
| `KN` | Kinetic | `\bkn\b` or `kinetic` |
| `RG` | Regeneration | `\brg\b` or `regeneration` or `regen` or `clean` |
| `IM` | Immobilization | `\bim\b` or `immobilization` or `immob` |
| `BK` | Blocking | `\bbk\b` or `blocking` or `block` |
| `WS` | Wash | `\bws\b` or `wash` |
| `OT` | Other | `\bot\b` or `other` or `custom` |

**Parsing priority:** The parser checks types in this order: Baseline → Immobilization → Blocking → Wash → Kinetic → Binding → Regeneration → Other. First match wins.

---

## In-Place Modifiers — `#N` Commands

Edit cycles that are already in the method table without removing them. Type `#N <modifier>` in the Note field and click **Add to Method**.

### Targeting

| Selector | Targets |
|----------|---------|
| `#3` | Cycle 3 only (1-indexed) |
| `#2-5` | Cycles 2 through 5 |
| `#all` | All cycles in the table |

### Modifier Commands

| Command | Effect | Example |
|---------|--------|---------|
| `contact Ns` | Set contact time | `#3 contact 120s` |
| `ct Ns` | Shorthand contact time | `#3 ct 120s` |
| `channels XX` | Set target channels | `#3 channels BD` |
| `detection priority/off/auto` | Set detection mode | `#all detection off` |
| `injection manual/simple/partial/automated` | Set injection mode | `#3 injection partial` |
| `flow N` or `fr N` | Set flow rate (µL/min) | `#3 flow 50` |
| `iv N` | Set injection volume (µL) | `#3 iv 25` |
| `conc A:NnM B:NnM` | Set per-channel concentrations | `#3 conc A:100nM B:50nM` |
| `duration Nmin` or `time Ns` | Change cycle duration | `#3 duration 10min` |

### Compound Modifiers

Multiple modifiers on one line:

```
#3 contact 120s channels BD detection priority
```

This sets contact time, channels, and detection mode on cycle 3 in a single command.

---

## Presets — Save & Reuse Methods

### Save a Preset

1. Build your method (add cycles to the table)
2. Type `!save my_protocol_name` in the Note field
3. Click **Add to Method**
4. Preset saved to `cycle_templates.json`

### Load a Preset

1. Type `@my_protocol_name` in the Note field
2. Click **Add to Method**
3. All cycles from the preset are loaded into the table

### Save Method to File

Click the **💾 Save** button to save the method as a `.json` file in `Documents/Affilabs Methods/`.

### Load Method from File

Click the **📂 Load** button to browse and load a previously saved `.json` method file.

---

## Spark AI Templates — `@spark` Commands

Type these in the Note field and press Enter or click the ⚡ Spark button:

| Command | What It Generates |
|---------|-------------------|
| `@spark titration` | Dose-response series: Baseline → 4 Binding cycles (10nM, 50nM, 100nM, 500nM) → Regeneration |
| `@spark kinetics` | Association + long dissociation: Baseline → Kinetic → Baseline 10min (dissociation) → Regen |
| `@spark amine coupling` | Full amine coupling workflow — asks how many binding cycles, then generates: Baseline → Activation → Wash → Immobilization → Wash → Blocking → Wash → Baseline → N × (Binding + Regen + Baseline) |
| `@spark binding` | Multi-concentration binding examples (100nM, 200nM, 500nM) |
| `@spark regeneration` | Single regeneration cycle (30sec ALL:50mM) |
| `@spark immobilization` | Single immobilization cycle (10min contact 180s) |
| `@spark baseline` | Single baseline cycle (5min) |
| `@spark full cycle` | Complete cycle: Baseline → Binding → Regeneration |
| `build N` | Auto-generate N × (Binding 15min + Regeneration 2min + Baseline 2min) |

### Spark Interaction Flow

1. You type a template command (e.g., `@spark titration`)
2. Spark generates cycle lines and shows them as a suggestion
3. Click **✅ Accept** to add all suggested cycles to the method
4. Click **✏ Edit** to modify the suggestion before adding
5. Click **❌ Reject** to discard

For multi-step templates (like amine coupling), Spark asks follow-up questions:
1. You type `@spark amine coupling`
2. Spark asks: "How many binding cycles?"
3. You type a number (e.g., `5`) and press Enter
4. Spark generates the full method

---

## Complete Workflow — Step by Step

### 1. Open Method Builder
Click **+ Build Method** in the sidebar.

### 2. Type Cycle Lines
Enter one cycle per line in the Note field:
```
Baseline 5min
Binding 5min A:100nM contact 180s
Regeneration 30sec ALL:50mM
Baseline 2min
```

### 3. Add to Method
Click **➕ Add to Method**. Cycles appear in the table below.

### 4. Review & Edit
- **Overview tab** — see type, duration, notes for each cycle
- **Details tab** — see injection settings (channels, concentration, contact time)
- Use **↑/↓** to reorder, **🗑 Delete** to remove, **↶ Undo / ↷ Redo** for history
- Use `#N` modifiers to edit cycles in-place

### 5. Push to Queue
Click **📋 Push to Queue** to send all cycles to the main Cycle Queue.

### 6. Copy Schedule (Optional)
Click **📋 Copy Schedule** to copy a print-friendly injection checklist to clipboard. Shows all injections with checkboxes, concentrations, contact times, and estimated runtime.

### 7. Start the Run
Press **▶ Start Run** in the sidebar. Cycles execute in order with auto-advance.

### 8. During Execution
- Cycles auto-advance when the timer expires
- Press **⏭ Next Cycle** to skip to the next cycle early (data preserved)
- The intelligence bar shows countdown and previews the next cycle in the last 10 seconds
- Injection detection auto-places flags when it detects a sample injection
- Contact timer counts down after injection; wash flag placed when it expires

### 9. After the Last Cycle
The system enters **Auto-Read** mode — 2 hours of continuous monitoring.

---

## Hardware Modes & Detection

### Method Modes

The Method Builder auto-configures based on detected hardware:

| Hardware | Default Mode | Available Modes | Notes |
|----------|-------------|-----------------|-------|
| P4SPR (no pump) | Manual | Manual only | Syringe injection only |
| P4SPR + AffiPump | Semi-Automated | Manual, Semi-Automated | External syringe pump |
| P4PRO | Semi-Automated | Manual, Semi-Automated | Built-in peristaltic pump |
| P4PRO+ | Semi-Automated | Manual, Semi-Automated | Built-in peristaltic pump |

### Detection Priority

| Mode | Sensitivity Factor | Best For |
|------|-------------------|----------|
| Auto | Mode-dependent | Default — adapts to hardware |
| Priority | 1.0 (medium) | Balanced sensitivity |
| Off | Disabled | Manual flag placement only |

**Manual mode** uses factor 2.0 (conservative, avoids false positives from syringe handling).
**Pump mode** uses factor 0.75 (tight detection for clean pump injections).

---

## Injection Timing Rules

All injection cycles follow these rules:

1. **Injection delay**: Always **20 seconds** after cycle start (fixed). This allows baseline to stabilize before injection.
2. **Contact timer**: Starts when injection is detected (not when cycle starts).
3. **Wash flag**: Automatically placed when contact timer expires.
4. **Cycle continues**: Data collection continues for the full cycle duration even after wash flag.

---

## Validation Warnings

The Method Builder warns you about potential issues when adding cycles:

| Warning | Condition | Recommendation |
|---------|-----------|----------------|
| Contact time vs duration | Contact > 90% of cycle duration | Extend cycle duration or reduce contact time |
| Short cycle with injection | < 2 min with injection enabled | Use 3–5 min minimum for reliable injection detection |
| Tight multi-injection | Multiple injections per cycle, not enough time | Increase cycle duration |
| Detection off | Detection disabled on an injection cycle | Enable Auto detection for assisted flag placement |
| High sensitivity in manual | Manual mode + Priority detection | May miss weak injections (factor 2.0) |

---

## Common Method Examples

### Example 1: Simple Binding Assay (Manual Injection)

```
Baseline 5min
Binding 5min A:100nM contact 180s
Regeneration 30sec ALL:50mM
Baseline 2min
```

### Example 2: Dose-Response Titration

```
Baseline 5min
Binding 5min A:10nM contact 180s
Regeneration 30sec ALL:50mM
Baseline 2min
Binding 5min A:50nM contact 180s
Regeneration 30sec ALL:50mM
Baseline 2min
Binding 5min A:100nM contact 180s
Regeneration 30sec ALL:50mM
Baseline 2min
Binding 5min A:500nM contact 180s
Regeneration 30sec ALL:50mM
Baseline 2min
Binding 5min A:1000nM contact 180s
Regeneration 30sec ALL:50mM
Baseline 5min
```

### Example 3: Kinetics Study (Pump-Driven)

```
Baseline 2min
Kinetic 5min A:100nM contact 120s fr 50
Baseline 10min                            # Dissociation phase
Regeneration 30sec ALL:50mM
Baseline 2min
```

### Example 4: Amine Coupling + Analyte Titration

```
Baseline 30sec
Other 4min                                 # EDC/NHS activation
Wash 30sec contact 30s
Immobilization 4min A:50µg/mL contact 180s
Wash 30sec contact 30s
Other 4min                                 # Ethanolamine blocking
Wash 30sec contact 30s
Baseline 15min
Binding 15min A:10nM contact 180s
Regeneration 2min ALL:50mM
Baseline 2min
Binding 15min A:50nM contact 180s
Regeneration 2min ALL:50mM
Baseline 2min
Binding 15min A:100nM contact 180s
Regeneration 2min ALL:50mM
Baseline 5min
```

### Example 5: Overnight Stability Test

```
Baseline overnight
```
(= 8 hours of continuous buffer flow)

```
Baseline 12h
```
(= 12-hour extended stability)

```
Baseline 24hr
```
(= 24-hour full-day stability)

### Example 6: Partial Injection (Reagent Conservation)

```
Binding 5min A:100nM contact 120s partial
```

(Uses 30 µL spike instead of full sample loop — saves expensive analyte for screening)

### Example 7: Multi-Channel Different Concentrations

```
Binding 5min A:100nM B:50nM contact 180s
```

(Channel A gets 100 nM, Channel B gets 50 nM — documented per-channel)

### Example 8: Channel-Restricted Experiment

```
Binding 5min A:100nM channels AC contact 180s
```

(Only channels A and C are active for this cycle)

### Example 9: Build Quick Series

```
build 5
```

Generates:
```
Binding 15min [A]  # Binding 1
Regeneration 2min [ALL]
Baseline 2min [ALL]
Binding 15min [A]  # Binding 2
Regeneration 2min [ALL]
Baseline 2min [ALL]
... (×5)
```

### Example 10: In-Place Edits After Building

```
# After adding a Titration preset, modify specific cycles:
#2 contact 120s                    # Change cycle 2 contact to 120s
#4 contact 120s                    # Change cycle 4 contact to 120s
#all channels AC                   # Restrict all cycles to channels A & C
#3 conc A:100nM B:50nM            # Set concentrations on cycle 3
```

---

## Choosing Between Binding and Kinetic

This is the most common question users have.

| Question | Choose **Binding** | Choose **Kinetic** |
|----------|-------------------|--------------------|
| How do you inject? | Manual syringe | Automated pump |
| Do you have a pump? | No (P4SPR) | Yes (P4PRO/P4PRO+/AffiPump) |
| What phases? | Association only (incubation) | Association + Dissociation |
| Flow during contact? | Static / very slow | Continuous at set rate |
| Typical use case | Endpoint binding, screening, teaching | Full kinetics (ka, kd, KD) |

**Rule of thumb:**
- **No pump → Binding** (manual injection, contact timer, wash)
- **Have pump → Kinetic** (pump injection, association, dissociation, wash)

---

## Tips & Best Practices

### Method Design

1. **Always start with a Baseline** — at least 2–5 min to establish a stable reference signal.
2. **Always end with a Baseline** — confirms regeneration worked and surface is reusable.
3. **Use descriptive names** — include concentration in the cycle name: `Binding 5min A:100nM` not just `Binding 5min`.
4. **Order concentrations low → high** — minimizes carryover effects in titration experiments.
5. **Include regeneration between binding cycles** — strips bound analyte so each cycle starts fresh.
6. **Set contact time explicitly** — don't rely on defaults unless you're sure 300 s or 30 s is correct for your experiment.

### Injection Best Practices

7. **Allow 3–5 min minimum** for cycles with manual injection — gives enough time for injection detection.
8. **Use partial injection** when screening expensive analytes — 30 µL is enough for detection.
9. **Manual mode on P4SPR** — injection detection uses factor 2.0 (conservative) to avoid false positives from syringe handling noise.
10. **Keep injection delay at 20 s** (automatic) — this ensures stable baseline before injection.

### Surface Preparation

11. **Amine coupling order:** Activation → Immobilization → Blocking → Baseline → Binding
12. **Set contact time on immobilization** — typically 180–300 s (3–5 min) for EDC/NHS.
13. **Wash between each prep step** — prevents carryover from activation to immobilization.

### Overnight Experiments

14. **Use `overnight` keyword** for 8-hour baselines.
15. **Contact time > 3 h auto-enables Overnight Mode** — prevents accidental timeout.
16. **Monitor stability** — long baselines reveal drift, bubble artifacts, and temperature effects.

---

## Spark AI Q&A — Example Questions & Answers

### Getting Started

**Q: How do I build a method?**
A: Click **+ Build Method** in the sidebar. Type one cycle per line in the Note field (e.g., `Baseline 5min`), then click **➕ Add to Method**. When ready, click **📋 Push to Queue** → **▶ Start Run**.

**Q: What cycle types are available?**
A: Eight types: Baseline, Binding, Kinetic, Regeneration, Immobilization, Blocking, Wash, Other. Use full names or abbreviations (BL, BN, KN, RG, IM, BK, WS, OT).

**Q: What's the difference between Binding and Kinetic?**
A: **Binding** is for manual injection (syringe, no pump) — sample incubates for a set contact time. **Kinetic** is for pump injection — includes association + dissociation phases at a set flow rate.

### Syntax

**Q: How do I set contact time?**
A: Add `contact Ns` to your cycle line. Example: `Binding 5min A:100nM contact 180s`. Shorthand: `ct 180s`. Supports seconds (s), minutes (m/min), hours (h/hr).

**Q: How do I set flow rate?**
A: Add `fr N` or `flow N` to the cycle line. Example: `Kinetic 5min A:100nM fr 50` (50 µL/min).

**Q: What are the cycle abbreviations?**
A: BL=Baseline, BN=Binding, KN=Kinetic, RG=Regeneration, IM=Immobilization, BK=Blocking, WS=Wash, OT=Other. Also: CN=Concentration (→Binding), AS=Association (→Binding).

**Q: How do I set injection volume?**
A: Add `iv N` to the cycle line. Example: `Binding 5min A:100nM iv 25` (25 µL injection).

**Q: How do I specify channels?**
A: Add `channels XX` (e.g., `channels AC`) or use per-channel tags (`A:100nM B:50nM`). Channels auto-derived from tags if not explicitly set.

**Q: How do I do partial injection?**
A: Add `partial` to the cycle line. Example: `Binding 5min A:100nM contact 120s partial`. Uses 30 µL spike instead of full loop.

**Q: What units are supported for concentration tags?**
A: nM, µM, pM, mM, M, mg/mL, µg/mL, ng/mL. Format: `Channel:ValueUnit` (e.g., `A:100nM`).

### Templates & Presets

**Q: How do I use Spark templates?**
A: Type `@spark` followed by a template name: `@spark titration`, `@spark kinetics`, `@spark amine coupling`, `@spark binding`, `@spark regeneration`, `@spark baseline`, `@spark full cycle`.

**Q: How do I save my method as a preset?**
A: Build your method, then type `!save my_method_name` and click Add to Method. Load later with `@my_method_name`.

**Q: How do I auto-generate binding cycles?**
A: Type `build N` (e.g., `build 5`) to generate N × (Binding 15min + Regeneration 2min + Baseline 2min).

**Q: What does @spark amine coupling generate?**
A: A full amine coupling workflow: Baseline → Activation (Other 4min) → Wash → Immobilization → Wash → Blocking (Other 4min) → Wash → Baseline 15min → N × (Binding + Regen + Baseline). Spark asks how many binding cycles to include.

### Editing

**Q: How do I edit a cycle after adding it?**
A: Use `#N` modifiers. Example: `#3 contact 120s` changes cycle 3 contact time. `#all detection off` disables detection on all cycles. `#2-5 channels AC` restricts cycles 2–5 to channels A and C. Multiple modifiers: `#3 contact 120s channels BD detection priority`.

**Q: How do I reorder cycles?**
A: Select a cycle in the table, then use **↑** (move up) or **↓** (move down) buttons.

**Q: How do I delete a cycle?**
A: Select the cycle, click **🗑 Delete**. Use **↶ Undo (Ctrl+Z)** to restore.

### Execution

**Q: What happens when a cycle ends?**
A: The next cycle starts automatically. After the last cycle, the system enters **Auto-Read** mode (2 hours of continuous monitoring).

**Q: Can I skip a cycle?**
A: Yes, press **⏭ Next Cycle** to end the current cycle early and advance. Data from the shortened cycle is still saved.

**Q: When does injection happen in a cycle?**
A: All injections start **20 seconds** after cycle begins (fixed delay for baseline stabilization).

**Q: What is the wash flag?**
A: When contact time expires during an injection cycle, the system automatically places a **wash flag** on the sensorgram to mark the transition from contact to wash/dissociation phase.

**Q: What is overnight mode?**
A: Overnight Mode is auto-enabled when duration > 3 hours or contact time > 3 hours. It prevents accidental cycle timeouts during long experiments.

### Troubleshooting

**Q: My contact time defaulted to 300s — why?**
A: Binding and Kinetic cycles default to 300 s (5 min) if you don't specify a contact time. Add `contact Ns` to override (e.g., `contact 180s`).

**Q: My regeneration cycle is too long.**
A: Regeneration defaults to 30 s contact. You can reduce it with `contact 15s` or increase with `contact 60s`.

**Q: Injection wasn't detected. What happened?**
A: Check detection mode — Manual mode is conservative (factor 2.0). Try `detection priority` for medium sensitivity. Ensure injection volume is > 10 µL. Verify you completed the injection before the detection window closed.

**Q: Can I mix Binding and Kinetic cycles in one method?**
A: Yes. Binding cycles use manual injection (syringe), Kinetic cycles use pump injection. The system handles both — just make sure the appropriate hardware is connected for Kinetic cycles.

**Q: How do I do a concentration series?**
A: Build individual Binding cycles at increasing concentrations with regeneration between each:
```
Baseline 5min
Binding 5min A:10nM contact 180s
Regen 30sec ALL:50mM
Baseline 2min
Binding 5min A:50nM contact 180s
Regen 30sec ALL:50mM
Baseline 2min
```
Or use `@spark titration` for an auto-generated template.

---

## Cycle Domain Model — Technical Reference

For developers and advanced users, each cycle is a Pydantic model with these fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | str | *(required)* | Cycle type |
| `length_minutes` | float | *(required, > 0)* | Duration in minutes |
| `name` | str | `""` | User-friendly name |
| `note` | str | `""` | Original text from Note field |
| `units` | str | `"nM"` | Concentration unit type |
| `concentrations` | Dict[str, float] | `{}` | Channel→value map |
| `injection_method` | "simple" or "partial" or None | `None` | Injection method |
| `injection_delay` | float | `20.0` | Seconds before injection (always 20) |
| `contact_time` | float or None | `None` | Contact time in seconds |
| `pump_type` | "affipump" or "p4proplus" or None | `None` | Auto-detected |
| `manual_injection_mode` | "automated" or "manual" or None | `None` | Override injection mode |
| `flow_rate` | float or None | `None` | µL/min |
| `injection_volume` | float or None | `None` | µL |
| `method_mode` | str or None | `None` | "manual", "semi-automated", "automated" |
| `detection_priority` | str | `"auto"` | "auto", "priority", "off" |
| `target_channels` | str or None | `None` | e.g., "AC", "BD", "ABCD" |
| `planned_concentrations` | List[str] | `[]` | e.g., ["100 nM", "50 nM"] |

---

## Quick Cheat Sheet

```
CYCLE TYPES:   BL BN KN RG IM BK WS OT
DURATIONS:     5s 5min 2h overnight
CONTACT:       contact 180s | ct 3min | ct 5h
FLOW:          fr 50 | flow 100
VOLUME:        iv 25
CHANNELS:      channels AC | A:100nM B:50nM
INJECTION:     partial | manual | automated
DETECTION:     detection priority | detection off
IN-PLACE:      #3 contact 120s | #all detection off | #2-5 channels BD
PRESETS:        !save name | @name
SPARK:          @spark titration | @spark kinetics | @spark amine coupling
BUILD:          build 5 | build 10
```

---

*Document generated for Spark AI Knowledge Base training. Run `python tools/spark/train_from_markdown.py` to ingest into the knowledge base.*
