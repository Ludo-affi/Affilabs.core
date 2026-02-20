# Notion Import Guide — Affilabs.core PRD Tracking

**Instructions:** Copy the sections below into Notion to set up your PRD workspace.

---

## 📋 SECTION 1: Create Main PRD Page (Copy This)

Paste this into a new Notion page called **"Affilabs.core — Product Requirements"**:

```markdown
# Affilabs.core — Product Requirements & Task Tracking

**Owner:** Lucia (OEM)  
**Last Updated:** February 18, 2026  
**Workspace:** ezControl-AI  
**Version:** v2.0.5 beta

---

## 🎯 Active PRDs

### 1. Sparq AI Assistant
**Status:** 🟢 Active Development  
**Phase:** Phase 1 Complete ✅ | Phase 2 Planned  
**Goal:** Definitive AI companion for Affinite SPR — guides researchers from concept to report

**Key Features:**
- Method Builder intelligence (P4SPR-first)
- Calibration troubleshooting (Universal: all models)
- Real-time Q&A with contextual awareness
- Per-user learning and history

**[View Full PRD →]** *(link to separate Sparq PRD page you'll create below)*

---

### 2. Lensless Spectral SPR Technology
**Status:** ✅ Complete (Retroactive Doc)  
**Phase:** Production (v2.0.5)  
**Goal:** Document wavelength interrogation SPR technology that powers all Affinite instruments

**Key Features:**
- Kretschmann configuration with lensless optics
- 9 peak-finding pipelines for broad spectral dip
- 4-channel time-multiplexed acquisition
- P/S ratio transmission calculation

**[View Full PRD →]** *(link to separate Lensless SPR page you'll create below)*

---

## 📊 Quick Stats

| Metric | Value |
|--------|-------|
| **Total PRDs** | 2 active |
| **Completed Tasks (This Week)** | 8 (Sparq Phase 1) |
| **Next Milestone** | Sparq Phase 2: Calibration Intelligence |
| **Modified Files (This Week)** | 4 Python source files |
| **Lines of Code Changed** | ~500 (net addition) |

---

## 🚀 Current Sprint: Sparq Phase 2

**Focus:** Calibration Intelligence (Universal — all models)

**Planned Tasks:**
- [ ] T9: Author 7 calibration KB articles (from 5000+ lines of existing docs)
- [ ] T10: Expand calibration patterns (3 → 15+)
- [ ] T11: Calibration wizard (interactive flow)
- [ ] T12: Real-time QC interpretation
- [ ] T13: Proactive recalibration reminders

**Why Phase 2:** Calibration is the #1 barrier to successful instrument use. Users cannot acquire data without completing calibration first.

---

## 📂 Source Locations

**PRD Documents (Local):**
- `docs/product_requirements/SPARQ_PRD.md`
- `docs/product_requirements/LENSLESS_SPECTRAL_SPR_SYSTEM_REQUIREMENTS.md`
- `docs/product_requirements/README.md`

**Modified Source Files (Phase 1):**
- `affilabs/services/spark/knowledge_base.py` (added 5 P4SPR articles)
- `affilabs/services/spark/patterns.py` (added 9 P4SPR patterns)
- `affilabs/widgets/method_builder_dialog.py` (refactored routing + validation)
- `affilabs/widgets/spark_help_widget.py` (user context + history)

---

## 🔗 Related Documentation

- **Technical Specs:** `docs/architecture/`
- **Calibration Docs:** `docs/calibration/` (3939 lines in CALIBRATION_MASTER.md)
- **User Guides:** `docs/user_guides/`
- **Implementation Notes:** `CLAUDE.md` (Active Context section)
```

---

## 📋 SECTION 2: Create Sparq Task Database

**Instructions:**
1. In Notion, create a new **Database - Table** page under your main PRD page
2. Name it: **"Sparq Task Tracker"**
3. Click the "⋮" menu → **Import** → **CSV**
4. Copy the CSV below and save as `sparq_tasks.csv`, then import

**CSV to Import:**

```csv
Task ID,Task Name,Phase,Status,Priority,Date Completed,Files Modified,Notes,Lines Changed
T1,Route Method Builder popup through SparkAnswerEngine,Phase 1,✅ Complete,High,2026-02-18,"method_builder_dialog.py",Refactored _detect_and_respond_to_question() to use single source of truth,~100 removed
T2,Add 5 P4SPR KB articles,Phase 1,✅ Complete,High,2026-02-18,"knowledge_base.py","Added: Channel Assignment, Injection Timing, Concentration Recommendations, Workflow, vs P4PRO comparison",~400
T3,Add 9 P4SPR patterns,Phase 1,✅ Complete,High,2026-02-18,"patterns.py","New p4spr category: 4-channels, manual injection, concentration, immobilization, workflow, regen, baseline, conflicts",~150
T4,Add user_manager param to SparkHelpWidget,Phase 1,✅ Complete,Medium,2026-02-18,"spark_help_widget.py",Personalized greeting with active username,~15
T5,Per-user Q&A history (JSON persistence),Phase 1,✅ Complete,Medium,2026-02-18,"spark_help_widget.py","Implemented _save_qa_entry(), saves to spark_qa_history_{username}.json, 50-entry limit",~70
T6,Method parameter validator enhancements,Phase 1,✅ Complete,High,2026-02-18,"method_builder_dialog.py","3 new P4SPR warnings: no contact time, short contact time, channel mismatch",~50
T7,Fix KB article accuracy,Phase 1,✅ Complete,Medium,2026-02-18,"knowledge_base.py",Clarified Presets article location; added P4SPR vs P4PRO comparison,~30
T8,Preset save suggestion,Phase 1,✅ Complete,Low,2026-02-18,"method_builder_dialog.py","Auto-suggests saving ≥3-cycle methods as presets, extends tooltip to 4000ms",~30
T9,Author 7 calibration KB articles,Phase 2,📋 Planned,High,,"knowledge_base.py","Distill from docs/calibration/*.md (5000+ lines): What is Cal, Types, When to Recal, QC interpretation, Failure troubleshooting, Step-by-step, Data persistence",~800
T10,Expand calibration patterns (3 → 15+),Phase 2,📋 Planned,High,,"patterns.py","Add: how to calibrate, cal failed, QC interpretation, LED saturation, servo error, when to recal, missing channel D, simple vs full, first-time setup, cal takes long, SNR low, P vs S polarity, afterglow",~200
T11,Calibration wizard (interactive flow),Phase 2,📋 Planned,Medium,,"spark_help_widget.py, method_builder_dialog.py","Multi-turn conversation: first-time vs routine → step-by-step prompts → QC validation → targeted fixes if failure",~300
T12,Real-time QC interpretation,Phase 2,📋 Planned,High,,"spark_help_widget.py, calibration_qc_dialog.py","Parse QC metrics (SNR, LED error, P/S ratio) → plain-language explanation → flag issues",~150
T13,Proactive recalibration reminders,Phase 2,📋 Planned,Low,,"spark_help_widget.py, calibration_service.py","Track last cal date per user+hardware → remind if >14 days → user can dismiss/snooze",~100
```

**After importing:**
1. Notion will convert this to a database
2. Add views:
   - **By Phase** (group by Phase column)
   - **By Status** (filter: Status = "📋 Planned" or "🔄 In Progress")
   - **Completed This Week** (filter: Date Completed = This Week)

---

## 📄 SECTION 3: Create Sparq PRD Detail Page

**Instructions:**
1. Create a new page under main PRD page
2. Name it: **"Sparq PRD — AI Assistant for SPR"**
3. Paste this content:

```markdown
# Sparq — AI Assistant for Affinite SPR

**Status:** 🟢 Active Development  
**Version:** v0.1 (Phase 1 shipped Feb 2026)  
**Owner:** Affinite Instruments  
**Next Milestone:** Phase 2 — Calibration Intelligence

---

## 🎯 Vision

Sparq is the definitive AI companion for Affinite-based SPR technology — guiding researchers from first experimental concept to final report, adapting to every skill level, learning individual workflows, and always proposing Affinite Instruments-native solutions.

---

## 🧑‍🔬 User Personas

### Persona A — The Novice
*Grad student or new lab tech, first 3 months with SPR*
- Does not know what a cycle is, what P-pol means, or why baseline matters
- Needs definitions, validation, and reassurance
- Questions are vague: "what do I do next?" / "is this normal?"

**Sparq Goal:** Walk them through every step. Detect novice vocabulary. Offer wizard-style flows. Flag mistakes before they happen.

### Persona B — The Regular User
*Experienced lab member, runs standard assays weekly*
- Knows the workflow but gets stuck on non-standard scenarios
- Wants fast, precise answers — no hand-holding
- Questions are specific: "what regeneration conditions work for antibody–antigen?"

**Sparq Goal:** Be a fast reference, troubleshooter, and method optimizer. Respect their time.

### Persona C — The Expert / Lab Manager
*Senior scientist or PI, runs multiple experiments, reviews others' data*
- Understands SPR deeply, wants advanced AI analysis
- Wants Sparq to compare runs, flag quality issues, suggest kinetics fitting
- May want to customize Sparq behavior for their team

**Sparq Goal:** Provide analytical intelligence, cross-experiment insights, report-ready outputs. Be a co-investigator.

---

## 🏗️ Architecture

### Answer Engine (4 Layers)

```
User Question
  ↓
Layer 0: USER CONTEXT INJECTION (< 1ms)
  → Active user, hardware model, app state
  ↓
Layer 1: PATTERN MATCHER (< 1ms)
  → Pre-compiled regex, ~50+ patterns
  → Instant answers for high-frequency questions
  ↓ (no match)
Layer 2: KNOWLEDGE BASE (< 200ms) ← PRIMARY INTELLIGENCE
  → Curated Affinite-authored articles
  → TinyLM parses intent → KB search
  → Relevance scoring, source cited
  ↓ (score < threshold)
Layer 3: AFFINITE CLOUD ESCALATION [future]
  → Pre-filled support ticket or live chat
```

**Knowledge-First Philosophy:** Sparq's primary content is human-written SPR guidelines, not AI-generated text. AI parsing supports retrieval; it doesn't replace expert content.

---

## 📦 Phase 1: Method Builder Mastery ✅ COMPLETE

**Goal:** Make Sparq the best guide for building SPR experiments (P4SPR-first)

### Shipped Features (Feb 2026)

✅ SparkHelpWidget in sidebar (Tab 4)  
✅ SparkMethodPopup in MethodBuilderDialog (inline ⚡ Spark button)  
✅ Pattern matching for @spark commands (titration, kinetics, amine coupling, build N)  
✅ TinyLlama local AI (lazy-loaded, background thread)  
✅ Per-user Q&A history (JSON files: `spark_qa_history_{username}.json`)  
✅ User-aware personalization (greeting, history)  
✅ P4SPR-specific KB (5 articles: channels, injection, concentration, workflow, vs P4PRO)  
✅ P4SPR-specific patterns (9 patterns covering manual injection, 4-channel system)  
✅ Method validation warnings (contact time, channel mismatch, missing regen)  
✅ Preset save suggestion (auto for ≥3-cycle methods)  
✅ Zero-crash guarantee (all layers wrapped in try/except)

### Implementation Details

**8 Tasks Completed:**
- T1-T8 (see Task Tracker for full list)

**Files Modified:**
- `affilabs/services/spark/knowledge_base.py` (+~430 lines)
- `affilabs/services/spark/patterns.py` (+~150 lines)
- `affilabs/widgets/method_builder_dialog.py` (~100 lines refactored, +80 new)
- `affilabs/widgets/spark_help_widget.py` (+~85 lines)

**Validation:** All files compile (py_compile verified)

---

## 📦 Phase 2: Calibration Intelligence 📋 PLANNED

**Goal:** Sparq as the definitive guide to instrument calibration — the critical gate before any experiment

**Why Phase 2:** Calibration is the #1 barrier to instrument use. Users cannot acquire data without successful calibration. It's **universal** — P4SPR, P4PRO, P4PROPLUS all use identical calibration procedures.

### Planned Features

📋 7 calibration KB articles (distilled from 5000+ lines of docs)  
📋 15+ calibration patterns (fast-path answers)  
📋 Calibration wizard (interactive multi-turn flow)  
📋 Real-time QC interpretation (plain-language explanations)  
📋 Proactive recalibration reminders (14-day cycle)

### Tasks

- T9: Author 7 calibration KB articles
- T10: Expand calibration patterns (3 → 15+)
- T11: Calibration wizard (interactive flow)
- T12: Real-time QC interpretation
- T13: Proactive recalibration reminders

**Estimated Completion:** 3-4 weeks (depends on content authoring time)

---

## 🔗 Source Files

**Sparq Implementation:**
- `affilabs/widgets/spark_help_widget.py` — Main UI, Q&A chat
- `affilabs/services/spark/answer_engine.py` — Layer coordinator
- `affilabs/services/spark/pattern_matcher.py` — Layer 1 regex
- `affilabs/services/spark/knowledge_base.py` — Layer 2 curated content
- `affilabs/services/spark/tinylm.py` — Layer 3 TinyLlama parser

**Method Builder Integration:**
- `affilabs/widgets/method_builder_dialog.py` — Inline Spark popup

**Data Storage:**
- `spark_qa_history_{username}.json` — Per-user Q&A history (root directory)
- `spark_knowledge_base.json` — KB content cache (root directory)

---

## 📊 Success Criteria

### Phase 1 Metrics (Achieved)

✅ Zero crashes (100% error handling)  
✅ < 200ms response time for KB queries  
✅ User personalization (active user name in greeting)  
✅ History persistence (50-entry limit per user)  
✅ P4SPR coverage (9 patterns + 5 articles)

### Phase 2 Metrics (Target)

🎯 < 1ms response for calibration patterns  
🎯 QC interpretation accuracy > 90% (user validation)  
🎯 Calibration wizard completion rate > 80%  
🎯 Support ticket reduction: 30% fewer cal-related tickets after rollout

---

## 🚫 Out of Scope (All Phases)

- Generic SPR advice not specific to Affinite instruments
- Third-party hardware integration suggestions
- AI-generated scientific content (KB is human-authored only)
- Cloud AI features without offline fallback (offline-first principle)

---

## 📅 Roadmap

**Phase 1:** Method Builder Mastery (P4SPR) — ✅ Complete (Feb 2026)  
**Phase 2:** Calibration Intelligence (Universal) — 📋 Planned (Mar 2026)  
**Phase 3:** Acquisition Troubleshooting (P4SPR) — 🔵 Future  
**Phase 4:** Affinite Product Proposals — 🔵 Future  
**Phase 5:** Flow Integration — 🔵 Future  
**Phase 6:** User Memory & Data Retrieval — 🔵 Future  
**Phase 7:** Paid Tier (Reporting, Interpretation) — 🔵 Future

---

**Full PRD Location:** `docs/product_requirements/SPARQ_PRD.md` (local file)
```

---

## 📄 SECTION 4: Create Lensless SPR PRD Detail Page

**Instructions:**
1. Create another new page under main PRD page
2. Name it: **"Lensless SPR Technology — Technical Specification"**
3. Paste this content:

```markdown
# Lensless Spectral SPR — Technology Specification

**Status:** ✅ Production (Retroactive Documentation)  
**Version:** v2.0.5 beta  
**Product Line:** P4SPR, P4PRO, P4PROPLUS  
**Owner:** Affinite Instruments

---

## 🔬 Technology Overview

Affinite's SPR is based on **wavelength interrogation** in a **Kretschmann prism configuration** using **lensless optics**. This is fundamentally different from conventional angular SPR (e.g., Biacore).

### Affinite vs. Angular SPR

| Property | Affinite (This System) | Angular SPR (Biacore) |
|----------|----------------------|----------------------|
| **Interrogation** | Wavelength (spectral) | Angle |
| **Light source** | White LED (broadband) | Laser (monochrome) |
| **Optics** | **Lensless** (no focusing) | Lens-based |
| **Configuration** | Kretschmann prism | Kretschmann prism |
| **Signal unit** | **nm** (wavelength) | RU (resonance units) |
| **SPR feature** | **Broad dip** (20-40 nm FWHM) | Narrow angular peak |
| **Acquisition rate** | 2-5 Hz (4 channels) | 1-10 Hz |

---

## ⚙️ System Architecture

### Optical Path

```
4× White LEDs (A, B, C, D) — SEQUENTIAL firing
  ↓
Servo polarizer (P-pol / S-pol)
  ↓
Prism + Gold-coated sensor chip (50 nm Au)
  ↓
SPR coupling at Au/buffer interface
  ↓
Optical fiber (600 µm, multimode)
  ↓
Spectrometer (Ocean Optics Flame-T or USB4000)
```

**Key Physics:**
- **Blue shift on binding** — Resonance wavelength DECREASES when analyte binds (opposite of angular SPR convention)
- **P/S ratio** — S-pol is reference (no SPR); P/S ratio cancels LED drift
- **Time-multiplexed** — 4 LEDs fire one at a time, never simultaneously
- **Full cycle time** — ~1-2 seconds for 4 channels × 2 polarizations = 8 spectra

---

## 📊 Signal Processing Chain

```
Raw Spectrum (P-pol, S-pol per channel)
  ↓
[1] Dark Subtraction
  ↓
[2] Transmission = P / S × 100%
  ↓
[3] Baseline Correction (percentile/polynomial)
  ↓
[4] Savitzky-Golay Smoothing
  ↓
[5] Peak Finding (9 pipelines available)
  ↓
[6] Temporal Filtering (Kalman/median)
  ↓
Resonance Wavelength (nm) → Sensorgram Y-axis
```

---

## 🎯 Performance Specifications

| Metric | Target | Typical Achieved |
|--------|--------|-----------------|
| **Baseline noise (RMS)** | < 2.0 RU | 0.5-1.5 RU |
| **Resolution** | < 0.01 nm | 0.002-0.005 nm |
| **SNR** | > 60:1 | 80:1-120:1 |
| **Acquisition rate** | 2-5 Hz | 2-3 Hz (4ch) |

**Conversion:** 1 nm ≈ 355 RU (system-specific)

---

## 🧮 Peak Finding Algorithms (9 Pipelines)

| Pipeline | Speed | Robustness | Best For |
|----------|-------|-----------|----------|
| **Direct Argmin** | < 0.1 ms | Medium | Clean signals, fast |
| **Centroid** | 0.5 ms | High | Broad dips |
| **Fourier** | 2 ms | Very High | Noisy signals, SNR-aware |
| **Polynomial** | 5 ms | Medium | Symmetric dips |
| **Hybrid** | 1 ms | High | Balanced (default) |
| **Consensus** | 10 ms | Very High | Ultra-stable |
| **Adaptive MultiFeature** | 3 ms | Very High | Research |
| **Batch Savgol** | 0.5 ms | Medium-High | Offline |
| **Hybrid Original** | 1 ms | High | Legacy |

**Active Pipeline:** Hybrid (set in `processing_pipeline.py`)

**Fourier is Gold Standard** for noisy signals — uses DST + SNR-aware weighting for sub-pixel precision.

---

## 🔧 Hardware Requirements

### Spectrometer

| Spec | Flame-T | USB4000 |
|------|---------|---------|
| Pixels | 2048 | 3648 |
| Wavelength range | 200-1000 nm | 200-850 nm |
| SPR ROI | 560-720 nm | 560-720 nm |
| Integration time | 10-100 ms | 10-100 ms |

### LED Controller

- **4 channels** (A, B, C, D) — identical white LEDs
- **Intensity:** 0-255 (8-bit PWM)
- **Typical:** 150-200 (calibrated)
- **Settling time:** 50 ms

### Servo Polarizer

- **Types:** Barrel (simple) or Circular (complex)
- **P-pol / S-pol positions:** Device-specific, calibrated
- **Settling time:** 100 ms

---

## 📐 Calibration Requirements

### 5 Calibration Types

1. **Startup** (auto, 1-2 min) — Runs on Power On, QC validation
2. **Simple LED** (10-20 sec) — Same-sensor swap, adjust intensities
3. **Full LED** (5-10 min) — New sensor, rebuild LED model
4. **Servo Position** (1.4-13 min) — First-time, find P/S angles
5. **OEM Optical** (10-15 min) — Factory-only, afterglow characterization

**Must pass QC before acquisition:**
- SNR > 40:1
- LED convergence error < 5%
- P/S ratio 50-150%
- Dark noise < 8000 counts

**Storage:**
- `device_config.json` — Servo positions, LED model
- `optical_calibration.json` — Afterglow time constants
- `calibration_checkpoint.pkl` — Fast reload

---

## ✅ Implementation Status

**100% Complete Features:**
- ✅ Lensless optical path (hardware design)
- ✅ 4-channel time-multiplexing
- ✅ P/S ratio transmission calculation
- ✅ 9 peak-finding pipelines
- ✅ Baseline correction (4 methods)
- ✅ Temporal filtering (Kalman, median)
- ✅ Calibration system (5 types)
- ✅ QC validation
- ✅ Detector profiles (Flame-T, USB4000)
- ✅ SNR-aware Fourier weighting
- ✅ Blue shift detection (injection)
- ✅ Servo calibration (barrel + circular)

---

## ⚠️ Known Limitations

| Limitation | Impact | Workaround |
|-----------|--------|-----------|
| Single spectrometer | Sequential channel readout (1-2 sec) | Not fixable (hardware) |
| Broad spectral dip | Lower resolution than angular SPR | Fourier/Consensus pipelines |
| Lensless = large spot | ~1 mm spot, no spatial imaging | Multi-channel compensates |
| Manual injection (P4SPR) | ±15 sec inter-channel skew | P4PRO/PLUS solve |

---

## 📚 Documentation References

**Architecture:**
- `docs/architecture/LIVE_DATA_FLOW_WALKTHROUGH.md`
- `docs/architecture/DATA_PROCESSING_PIPELINE.md`

**Calibration:**
- `docs/calibration/CALIBRATION_MASTER.md` (3939 lines)

**Source Code:**
- `affilabs/core/spectrum_processor.py` — Main processor
- `affilabs/utils/pipelines/*.py` — 9 peak-finding pipelines
- `affilabs/services/calibration_service.py` — Calibration orchestrator

---

**Full PRD Location:** `docs/product_requirements/LENSLESS_SPECTRAL_SPR_SYSTEM_REQUIREMENTS.md` (local file)
```

---

## ✅ DONE! Copy-Paste Checklist

1. ✅ Copy **SECTION 1** → Create main page "Affilabs.core — Product Requirements"
2. ✅ Copy **CSV in SECTION 2** → Save as `sparq_tasks.csv` → Import to Notion database "Sparq Task Tracker"
3. ✅ Copy **SECTION 3** → Create child page "Sparq PRD — AI Assistant for SPR"
4. ✅ Copy **SECTION 4** → Create child page "Lensless SPR Technology — Technical Specification"
5. ✅ Link child pages to main page (use @ mention)

---

**Result:** You'll have a complete Notion workspace with:
- 📄 Main PRD dashboard
- 📊 Task database (8 complete, 5 planned)
- 📄 2 detailed PRD pages (Sparq + Lensless SPR)
- 🔗 Quick stats and source file references

**Time to set up:** ~5-10 minutes
