# Affinité Kinetic Method Definitions

## Three Operating Modes

### Mode 1: Individual Cycles (No method header)

**Each cycle runs independently, as written. Manual control.**

```
Baseline
Concentration 50 nM
Regeneration
Baseline
```

Each line = one cycle. Flow panel behavior. Independent aspirate/dispense per action.

---

### Mode 2: Stacking Kinetics (Biacore equivalent: Multi-Cycle Kinetics)

**One concentration per syringe. Surface regenerated between each.**

Method header: `Stacking Kinetics`

Each `Concentration` line auto-expands to:

| Phase | Duration | Volume (@ 40 µL/min) |
|---|---|---|
| Baseline 1 | 30s | 20 µL |
| Pre-inject delay | 15s | 10 µL |
| Injection (contact) | 2 min | 80 µL |
| Dissociation (buffer) | 10 min | 400 µL |
| Regen pre-inject delay | 15s | 10 µL |
| Regeneration (contact) | 1 min | 40 µL |
| Baseline 2 | remainder | 440 µL |
| **Total** | **~25 min** | **1000 µL** |

After each concentration: **Home → Refill → Next concentration**

Example method:
```
Stacking Kinetics
contact_time 2 min
channels AC
Concentration 50 nM
Concentration 100 nM
Concentration 200 nM
Concentration 400 nM
Concentration 800 nM
```

5 concentrations = 5 syringes = ~125 min + refill pauses.

---

### Mode 3: Cascade Kinetics (Biacore equivalent: Single-Cycle Kinetics) — PLACEHOLDER

**All concentrations in ONE syringe. No regeneration between injections. Analyte accumulates on the surface.**

Method header: `Cascade Kinetics`

**Key difference from Stacking:** Between each concentration, flow **stops** while the user loads the next sample into the loop. Single syringe, no refills, no regen.

#### Sequence:

```
FLOW RUNNING (buffer) ──→ INJECT (50 µL @ 100 µL/min, 30s) ──→ STOP FLOW ──→ LOAD PAUSE (user loads next sample, ~10s) ──→ FLOW RUNNING ──→ INJECT next ──→ ...
```

#### Volume budget (5 concentrations @ 100 µL/min):

| Phase | Duration | Volume |
|---|---|---|
| Baseline | 30s | 50 µL |
| Inject Conc 1 (50 nM) | 30s | 50 µL |
| **Load pause** (flow stopped) | ~10s | 0 µL |
| Inject Conc 2 (100 nM) | 30s | 50 µL |
| **Load pause** (flow stopped) | ~10s | 0 µL |
| Inject Conc 3 (200 nM) | 30s | 50 µL |
| **Load pause** (flow stopped) | ~10s | 0 µL |
| Inject Conc 4 (400 nM) | 30s | 50 µL |
| **Load pause** (flow stopped) | ~10s | 0 µL |
| Inject Conc 5 (800 nM) | 30s | 50 µL |
| Dissociation (buffer) | remainder | 650 µL |
| **Total** | **~14 min** | **1000 µL** |

Example method:
```
Cascade Kinetics
contact_time 30s
Concentration 50 nM
Concentration 100 nM
Concentration 200 nM
Concentration 400 nM
Concentration 800 nM
```

#### Load pause mechanics:

1. After injection contact time ends → **stop pump dispense**
2. Switch 6-port valve to LOAD position
3. Signal user to load next sample (UI prompt / buzzer / timer)
4. Wait for user confirmation OR auto-timeout (~10s)
5. Switch 6-port valve to INJECT position
6. **Resume pump dispense** → next injection begins

> **⚠️ PLACEHOLDER:** Requires a new pump method (`inject_cascade`?) and experiment type. The load-pause with flow-stop is fundamentally different from `inject_simple` (continuous flow). Implementation TBD.

#### Open questions:

- [ ] Does the pump literally stop (plunger holds position) or does it home during load pause?
- [ ] How does the user signal "sample loaded"? Button click? Auto-timeout?
- [ ] Should there be a brief buffer rinse after resuming flow before the next injection hits the sensor?
- [ ] Contact time per injection — fixed 30s or configurable per concentration?
- [ ] 50 µL injection volume — is this always the target, or does it vary?

---

### Mode 4: Amine Coupling Functionalization (Fixed Protocol)

**Surface preparation before kinetics. Always the same sequence. Single syringe.**

Method header: `Amine Coupling`

This is a predefined protocol — the user doesn't configure individual steps, they just run it.

#### Fixed sequence (3 injections + washes):

| Phase | Type | Duration | Volume (@ 20 µL/min) | Cumulative |
|---|---|---|---|---|
| Baseline | Buffer | 2 min | 40 µL | 40 µL |
| Pre-inject delay | Buffer | 15s | 5 µL | 45 µL |
| **Activation** (EDC/NHS) | Inject | 4 min | 80 µL | 125 µL |
| Wash 1 | Buffer | 2 min | 40 µL | 165 µL |
| Pre-inject delay | Buffer | 15s | 5 µL | 170 µL |
| **Immobilization** (Ligand) | Inject | 4 min | 80 µL | 250 µL |
| Wash 2 | Buffer | 2 min | 40 µL | 290 µL |
| Pre-inject delay | Buffer | 15s | 5 µL | 295 µL |
| **Blocking** (Ethanolamine) | Inject | 4 min | 80 µL | 375 µL |
| Wash 3 | Buffer | 10 min | 200 µL | 575 µL |
| **Total** | | **~28.75 min** | **575 µL** | |

Flow rate: 20 µL/min (derived from 4 min contact time)
Single syringe: 575 µL used, 425 µL headroom.

#### Load pause between injections:

Same as Cascade Kinetics — flow stops, user loads next reagent:
1. Activation → stop flow → user loads ligand → resume
2. Immobilization → stop flow → user loads ethanolamine → resume
3. Blocking → long wash → done

Example method (user just writes):
```
Amine Coupling
```

No parameters needed — everything is predefined. The system prompts the user to load each reagent at the right time.

#### Reagent order (user loads):
1. **EDC/NHS mix** → Activation
2. **Ligand (protein)** → Immobilization
3. **Ethanolamine** → Blocking

> **⚠️ PLACEHOLDER:** Shares load-pause mechanics with Cascade Kinetics. Implementation TBD alongside `inject_cascade`.

---

### Mode 5: Streptavidin Functionalization — PLACEHOLDER

**Pre-coated streptavidin surface. User captures biotinylated ligand.**

Method header: `Streptavidin`

> Protocol TBD. Streptavidin chips are pre-functionalized — no activation/blocking needed. Sequence is likely: Baseline → Inject biotinylated ligand → Wash → Ready for kinetics.

---

### Mode 6: Protein A Functionalization — PLACEHOLDER

**Protein A surface for antibody capture.**

Method header: `Protein A`

> Protocol TBD. Protein A binds Fc region of antibodies. Typically: Baseline → Inject antibody → Wash → Ready for kinetics. Regeneration with low pH (Glycine pH 1.5–2.5).

---

### Mode 7: Ni-NTA Functionalization — PLACEHOLDER

**Ni-NTA surface for His-tagged protein capture.**

Method header: `Ni-NTA`

> Protocol TBD. Ni-NTA chelates His-tags. Typical sequence: Baseline → NiCl₂ loading → Wash → Inject His-tagged ligand → Wash → Ready for kinetics. Regeneration with imidazole or EDTA.

---

### Mode 8: RAM-Fc Functionalization — PLACEHOLDER

**Rabbit Anti-Mouse Fc (RAM-Fc) surface for mouse antibody capture.**

Method header: `RAM-Fc`

> Protocol TBD. RAM-Fc captures mouse IgG via Fc region. Typical sequence: Baseline → Inject mouse antibody → Wash → Ready for kinetics. Regeneration with low pH.

---

## User Interface

From the user's perspective, the method header determines orchestration:

| What they write | What happens |
|---|---|
| No header + individual cycles | Each cycle runs as written |
| `Stacking Kinetics` + concentrations | Auto-expand: BL1→Inject→Dissoc→Regen→BL2→Refill per conc |
| `Cascade Kinetics` + concentrations | All in one syringe with load pauses (PLACEHOLDER) |

---

## Flow Rate ↔ Contact Time

Either can be specified; the other is derived:

$$\text{flow\_rate} = \frac{80}{\text{contact\_time\_s}} \times 60$$

| Contact Time | Flow Rate |
|---|---|
| 30s | 160 µL/min |
| 1 min | 80 µL/min |
| 2 min | 40 µL/min |
| 3 min | 26.7 µL/min |
| 5 min | 16 µL/min |

If both specified, contact_time takes priority.

---

## Default Parameters

| Parameter | Default | Applies to |
|---|---|---|
| Contact time | 2 min | Stacking Kinetics |
| Contact time | 30s | Cascade Kinetics |
| Baseline 1 | 30s | Both |
| Dissociation | 10 min | Stacking Kinetics |
| Regen wash volume | 40 µL | Stacking Kinetics |
| Channels | AC | Both |
| Loop volume | 100 µL (80 µL usable) | Both |

---

## Key Differences

| | Stacking Kinetics | Cascade Kinetics |
|---|---|---|
| Syringes | 1 per concentration | 1 total |
| Regeneration | Between each concentration | After all (optional) |
| Surface state | Reset each time | Accumulates |
| Refills | Yes, between each | None |
| Flow between injections | Continuous | Stops for load pause |
| Pump method | `inject_simple` | `inject_cascade` (TBD) |
| Implementation | Ready | PLACEHOLDER |
| Best for | Accurate ka/kd per conc | Low sample, screening |
