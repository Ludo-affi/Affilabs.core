# Demo Mode Plan

## Purpose
Two independent demo datasets for training and promotional screenshots.
Both triggered via keyboard shortcuts — no hardware required.

---

## Two Modes

### Mode 1 — Kinetics (existing, `Ctrl+Shift+D`)
**Use case:** Show full SPR kinetics experiment — association + dissociation curves, dose-response series, binding affinity analysis.

**What it loads:**
- 15-min sensorgram, 4 channels, distinct on/off profiles (A: fast on/slow off, D: slow on/fast off)
- Full cycle queue: Baseline → Activation → Immobilization → Blocking → Baseline → 5× Binding (hIgG 10–1000 nM)
- Edits table: 5 binding cycles with concentrations + ΔSPR values pre-filled (Langmuir KD=150 nM)
- Delta SPR bar chart pre-populated at 500 nM response
- Binding tab: dose-response plot auto-generates when user selects all 5 rows
- Transmission spectra: 4 channels, SPR dip visible, shifted by binding
- Sparq message: analysis blurb about hIgG dose-response

**Tab showcase:** Live → Edits (sensorgram overlay, ΔSPR bar, binding plot) → Spectroscopy

---

### Mode 2 — Manual Injection / Contact Monitoring (`Ctrl+Shift+M`)
**Use case:** Show P4SPR manual syringe injection workflow — user pipettes sample, on-rate only (no wash/dissociation), contact time monitoring.

**What it loads:**

**Sensorgram (30 min):**
- 4 channels, each with a different analyte
- Shape: flat baseline → sharp step-up at injection → slow linear association (on-rate only, no dissociation phase)
- No wash cycle — signal stays elevated (contact monitoring mode)
- Each channel injected manually with ~10–15 s stagger (realistic P4SPR pipetting delay)
- Channels: A (fast binder), B (moderate), C (slow), D (very slow / near-baseline)

**Cycle queue:**
- Baseline (2 min) → 4× Contact (one per channel, 20 min each, all "running" or staggered start)
- OR: single "Contact Monitoring" cycle type spanning all 4 channels

**Contact time counter / timer display:**
- If app has a contact timer widget, pre-set it to show elapsed contact time for each channel
- e.g. "Ch A: 8:32 contact | Ch B: 8:17 | Ch C: 8:02 | Ch D: 7:47"

**Edits table:**
- 4 rows — one per channel — type "Contact", with on-rate (association slope, RU/min) instead of ΔSPR
- No concentration column (not applicable for contact monitoring)
- Or: show 4 analytes at a single concentration (e.g. 100 nM each, different kobs)

**Sparq message:**
- "Manual injection mode — 4 analytes injected sequentially by pipette. Contact monitoring active. Channels show on-rate only; wash not yet applied."

---

## Implementation Notes

### File: `affilabs/utils/demo_data_generator.py`
- Add `generate_demo_contact_sensorgrams()` — 30-min, association-only curves with staggered injection starts
- Add `load_contact_demo_into_app(app)` — same architecture as `load_demo_data_into_app()`
- Keep both functions independent (separate seed, separate profiles)

### File: `main.py`
- Add `Ctrl+Shift+M` shortcut → `self._load_contact_demo_data()`
- Add `_load_contact_demo_data()` method (mirrors `_load_demo_data()`)
- The `Ctrl+Shift+D` shortcut stays on kinetics mode

### Association-only curve shape
```
signal = baseline + Rmax * (1 - exp(-ka * t))    # association phase only
# No dissociation phase — signal held at plateau
# After 20 min contact: signal ≈ 85–95% of Rmax
```

### Staggered injection (P4SPR realism)
```python
_INJECT_OFFSETS_S = {"a": 0, "b": 12, "c": 24, "d": 36}  # ~12 s per pipette
```

### Edits table format for contact monitoring
```python
{
    "type": "Contact",
    "name": "Anti-CD3 100 nM",
    "duration_minutes": 20.0,
    "concentration_value": "100",
    "delta_ch1": None,   # no ΔSPR — not applicable
    "on_rate_ru_per_min": 142.0,   # slope during association
    "delta_measured": False,
}
```
(Note: edits table may need a new column or use the ΔSPR column as on-rate display — decide at implementation time.)

---

## Status
- [ ] Mode 1 (kinetics): **complete** — all features implemented
- [ ] Mode 2 (contact/manual injection): **planned** — implement next
