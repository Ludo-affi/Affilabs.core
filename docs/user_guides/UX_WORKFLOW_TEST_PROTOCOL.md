# Affilabs.core — Experiment Workflow Test Protocol
**Version**: 1.0  
**Last Updated**: 2026-02-20  
**Purpose**: Formal UX readiness assessment across the 6-stage experiment workflow. Results feed into Sparq IQ scoring and UX_USER_JOURNEY.md improvements.

---

## How to Use This Protocol

**Tester**: Run through each test item in order. No skipping — sequence matters.  
**Scoring**: Score each item 1–4 using this rubric:

| Score | Label | Meaning |
|-------|-------|---------|
| **4** | ✅ Clear | Completed immediately, no hesitation |
| **3** | 🟡 Managed | Completed but required a pause or re-read |
| **2** | 🟠 Struggled | Completed but confused, needed trial and error |
| **1** | ❌ Failed | Could not complete, or completed incorrectly |

**Sparq IQ** = (total score / max score) × 100 — target ≥ 80.  
After scoring, paste your results back using the **Result Report Template** at the bottom.

---

## Stage 1 — CONNECT (Max: 20)

> Goal: Instrument recognized and software ready. No prior knowledge assumed.

| # | Test Item | What to Observe | Score |
|---|-----------|----------------|-------|
| 1.1 | Launch the app | Is it immediately clear what you should do first? | |
| 1.2 | Locate the connect/power button | Without instructions, find and identify the button | |
| 1.3 | Click connect with no instrument plugged in | Does the app communicate clearly that nothing was found? | |
| 1.4 | Plug in instrument and connect | Does the SEARCHING state feel responsive (not frozen)? | |
| 1.5 | Wait for CONNECTED | Is the success state unmissable? | |

**Stage 1 Subtotal**: __ / 20  
**Notes**:

---

## Stage 2 — CALIBRATE (Max: 24)

> Goal: Clean S-pol baseline captured. User understands why calibration is needed.

| # | Test Item | What to Observe | Score |
|---|-----------|----------------|-------|
| 2.1 | Find the Calibrate button after connecting | Is the next-step clear without reading a manual? | |
| 2.2 | Open the pre-calibration dialog | Does the water-in-device warning register clearly? | |
| 2.3 | Understand what calibration does | Without asking, can the user articulate what it does? | |
| 2.4 | Observe calibration progress | Does the progress display tell you WHAT is happening (not just %)? | |
| 2.5 | Calibration completes successfully | Is the success state clearly communicated? | |
| 2.6 | Understand what to do next after calibration | Is the next step (acquire) visually indicated? | |

**Stage 2 Subtotal**: __ / 24  
**Notes**:

---

## Stage 3 — ACQUIRE (Max: 20)

> Goal: Live signal visible, user can judge signal quality.

| # | Test Item | What to Observe | Score |
|---|-----------|----------------|-------|
| 3.1 | Find the live sensorgram | Does the main display show a live signal without extra steps? | |
| 3.2 | Understand what the signal means | Does the user understand they are seeing wavelength vs time? | |
| 3.3 | Assess signal quality (IQ dots) | Without guidance, locate and understand the per-channel IQ indicator | |
| 3.4 | Distinguish "good signal" from "bad signal" | Can the user tell if their signal is usable? | |
| 3.5 | Spot a flat baseline | Can the user tell when baseline is stable enough to inject? | |

**Stage 3 Subtotal**: __ / 20  
**Notes**:

---

## Stage 4 — INJECT (Max: 24)

> Goal: Sample delivered, injection event registered, signal response observed.

| # | Test Item | What to Observe | Score |
|---|-----------|----------------|-------|
| 4.1 | Know when to inject (stability cue) | Does the stability badge guide the injection decision? | |
| 4.2 | Locate injection controls (P4SPR: Mark Injection button) | Without instructions, find how to log an injection | |
| 4.3 | Place an injection flag | Flag appears on the sensorgram — is it noticeable? | |
| 4.4 | Observe signal response | User notices the wavelength change after injection | |
| 4.5 | Understand blue-shift direction (signal drops) | Does the user know a drop = positive binding? | |
| 4.6 | *[P4PRO/PROPLUS only]* Operate method / pump controls | Locate, configure, and start a semi-automated injection | |

**Stage 4 Subtotal**: __ / 24 (or __ / 20 if P4SPR only)  
**Notes**:

---

## Method Builder (Supplement — score separately)

> Run this block whenever testing method creation. Max: 16. Not included in Sparq IQ total until the redesign (see [METHOD_BUILDER_REDESIGN_FRS.md](../features/METHOD_BUILDER_REDESIGN_FRS.md)) is implemented.

| # | Test Item | What to Observe | Score |
|---|-----------|----------------|-------|
| MB.1 | Open Method Builder — start from a template in <30 seconds | Can the user pick a starting point without reading any help text? | |
| MB.2 | Add a Binding step using the structured controls | No typing required — all fields accessible via dropdowns/spinboxes | |
| MB.3 | Ask Sparq "add kinetics" in the method builder | Does the result appear in the step list automatically? | |
| MB.4 | Push the method to queue and find it in the cycle list | Is the Push action clearly labelled and the result visible? | |

**Method Builder Subtotal**: __ / 16  
**Notes**:

---

## Stage 5 — RECORD (Max: 20)

> Goal: Experiment data captured to file. User confident data is saved.

| # | Test Item | What to Observe | Score |
|---|-----------|----------------|-------|
| 5.1 | Find the Record button | Without instructions, locate and identify it | |
| 5.2 | Start recording | Is the recording state unmissable (pulsing dot, file path shown)? | |
| 5.3 | Know WHERE data is being saved | File path visible without opening a dialog | |
| 5.4 | Stop recording | Does stopping feel safe (not like data loss)? | |
| 5.5 | Locate the saved file after stopping | Can the user find the file from the post-stop notification? | |

**Stage 5 Subtotal**: __ / 20  
**Notes**:

---

## Stage 6 — EXPORT & ANALYZE (Max: 20)

> Goal: Recorded data reviewed, Excel/file exported.

| # | Test Item | What to Observe | Score |
|---|-----------|----------------|-------|
| 6.1 | Navigate to Edits tab after recording | Is the transition from Live → Edits prompted or discoverable? | |
| 6.2 | Understand what a "cycle" is | First-time: does the in-context explanation appear? | |
| 6.3 | Find recorded cycles in the table | Are cycles listed, labeled, and navigable? | |
| 6.4 | Locate the Export function | Is Export discoverable without reading a manual? | |
| 6.5 | Export to Excel | File is generated and user can find it | |

**Stage 6 Subtotal**: __ / 20  
**Notes**:

---

## Sparq IQ Scorecard

Fill in after completing all stages.

| Stage | Score | Max | % |
|-------|-------|-----|---|
| 1 — Connect | | 20 | |
| 2 — Calibrate | | 24 | |
| 3 — Acquire | | 20 | |
| 4 — Inject | | 24 | |
| 5 — Record | | 20 | |
| 6 — Export | | 20 | |
| **TOTAL** | | **128** | |

**Sparq IQ = (Total / 128) × 100 = ____**

| Score Range | Rating |
|-------------|--------|
| 90–100 | 🟢 Excellent — no major friction points |
| 80–89 | 🟡 Good — minor polish items |
| 65–79 | 🟠 Needs Work — multiple confusing moments |
| < 65 | 🔴 Poor — significant UX barriers |

---

## Result Report Template

Paste this back after testing:

```
SPARQ IQ RESULT — [Tester name] — [Date] — [Hardware model tested: P4SPR / P4PRO / P4PROPLUS / No hardware]

SCORES:
Stage 1 (Connect):   __ / 20
Stage 2 (Calibrate): __ / 24
Stage 3 (Acquire):   __ / 20
Stage 4 (Inject):    __ / 24
Stage 5 (Record):    __ / 20
Stage 6 (Export):    __ / 20
TOTAL:               __ / 128  →  IQ = __

FAILED ITEMS (score 1 or 2):
- [#]: [what happened]

OBSERVATIONS:
- [Any freeform notes per stage]

SPARQ GAPS (things Sparq could have answered but didn't):
- [Question the user had that Sparq couldn't answer]
```

---

## How Results Update the Codebase

| Finding type | Action |
|-------------|--------|
| Item scored ≤ 2 | Open `REQ:` and fix; update `UX_USER_JOURNEY.md` `⬜ → ✅` when done |
| Item scored 3 consistently | Add polish note to relevant `⬜` entry in journey doc |
| "Sparq gap" identified | Add Q&A pattern to `affilabs/services/spark/patterns.py` |
| New test item needed | Add row to this doc and re-number |

---

## Related Docs

- [UX_USER_JOURNEY.md](../ui/UX_USER_JOURNEY.md) — Stage-by-stage intent and `✅/⬜` implementation status
- [UI_STATE_MACHINE.md](../ui/UI_STATE_MACHINE.md) — App states that correspond to stages 1–3
- [SPARQ_PRD.md](../../product_requirements/SPARQ_PRD.md) — Sparq feature roadmap
