# Sparq — Product Requirements Document

**Product Name:** Sparq  
**Branding:** Sparq⚡ — the lettermark uses a stylized SPR sensorgram dip curve as a ligature between the tail of the **p** and the **q** (see branding notes below)  
**Owner:** Affinite Instruments  
**Status:** Active — v0.1 foundation shipped (Feb 2026), full vision in progress  
**Last Updated:** February 18, 2026

---

## Table of Contents

1. [Vision](#1-vision)
2. [Problem Statement](#2-problem-statement)
3. [User Personas](#3-user-personas)
4. [Product Scope — End-to-End Coverage](#4-product-scope--end-to-end-coverage)
5. [User-Specific Intelligence](#5-user-specific-intelligence)
6. [Answer Engine Architecture](#6-answer-engine-architecture)
7. [Feature Roadmap](#7-feature-roadmap)
   - Phase 1: Method Builder Mastery (P4SPR) ✅
   - Phase 2: Calibration Intelligence (Universal)
   - Phase 3: Acquisition Troubleshooting (P4SPR)
   - Phase 4: Affinite Product Proposals
   - Phase 5: Flow Integration
   - Phase 6: User Memory & Data Retrieval
   - Phase 7: Paid Tier — Reporting, Interpretation, Historical Comparison
8. [Technical Architecture](#8-technical-architecture)
9. [Data & Storage Schema](#9-data--storage-schema)
10. [Cloud AI Premium Tier](#10-cloud-ai-premium-tier)
11. [Performance Targets](#11-performance-targets)
12. [Privacy & Compliance](#12-privacy--compliance)
13. [Branding & UX Direction](#13-branding--ux-direction)
14. [Success Criteria](#14-success-criteria)
15. [Out of Scope](#15-out-of-scope)
16. [Implementation Notes — Current State](#16-implementation-notes--current-state)

---

## 1. Vision

> **Sparq is the definitive AI companion for Affinite-based SPR technology — guiding researchers from first experimental concept to final report, adapting to every skill level, learning individual workflows, and always proposing Affinite Instruments-native solutions.**

Sparq is not a generic chatbot embedded in a software product. It is a domain-expert AI that understands the full surface plasmon resonance workflow — the physics, the instrumentation (P4SPR, P4PRO, P4PROPLUS), the data, the common failure modes — and it knows the *user* operating it. It meets novices where they are and accelerates experts where they want to go.

### Guiding Principles

| Principle | What It Means |
|-----------|--------------|
| **End-to-end** | Sparq is useful before the experiment, during acquisition, during analysis, and at reporting. No gaps. |
| **User-aware** | Sparq knows who is logged in, their role, their history, and their habits. |
| **Affinite-native** | Sparq never suggests third-party workflows or instruments. All guidance is grounded in Affinite hardware and Affilabs.core features. |
| **Offline-first** | Core intelligence works with no internet, on any lab PC, even air-gapped. Cloud tiers are additive, never required. |
| **No jargon walls** | Novice users get plain-language guidance. Expert users get precision. Sparq detects the difference. |
| **Knowledge-first** | Sparq's primary intelligence is a curated, human-written knowledge base of SPR guidelines, examples, and workflows — not generated AI text. AI parsing supports retrieval; it does not replace expert content. |
| **P4SPR as the foundation** | All Sparq development starts with the P4SPR. Its technology — lensless spectral SPR, 4 independent channels, manual injection — is the baseline across every Affinite product. Solving for P4SPR solves for the product family. |

### Why P4SPR First

The P4SPR is the most widely deployed Affinite instrument and the technological core from which all other models (P4PRO, P4PROPLUS) derive. Key reasons it is the development anchor for Sparq:

- **Broadest user base** — more P4SPR units in the field than all other models combined
- **Most complex manual workflow** — P4SPR uses manual syringe injection per channel, requiring significantly more user guidance than automated platforms
- **4 fully independent channels** — users can run up to 4 different samples in a single experiment, creating richer experimental design complexity that Sparq must handle
- **No automation safety net** — on P4PRO/PLUS, the pump enforces timing. On P4SPR, the user is the pump. Mistakes are unrecoverable mid-run without Sparq guidance.
- **Cross-product applicability** — every workflow concept, cycle type, and SPR principle solved for P4SPR applies directly to P4PRO and P4PROPLUS, making P4SPR work automatically extend to the full product line

---

## 2. Problem Statement

SPR is a powerful but technically demanding technique. Researchers — especially new ones — face steep learning curves:

- **Experiment design:** What cycle type? What flow rate? What regeneration buffer? How many replicates?
- **Instrument operation:** Calibration is not intuitive. Connection, pump priming, channel selection — all friction-heavy.
- **Data interpretation:** Is this noise or a real binding event? Why is the baseline drifting? What does the dip position mean?
- **Reporting:** How do I export this for a paper? What units are correct? What controls do I need to describe?

Today, users rely on emailing Affinite support or consulting PDFs. Sparq eliminates that friction — giving every user immediate, contextual, instrument-specific guidance at every step.

---

## 3. User Personas

### Persona A — The Novice
*Grad student or new lab tech, first 3 months with SPR*

- Does not know what a cycle is, what P-pol means, or why baseline matters
- Will break the experiment if not guided step by step
- Needs definitions, validation, and reassurance
- Questions are vague: "what do I do next?" / "is this normal?"

**Sparq goal:** Walk them through every step. Detect their novice vocabulary. Offer wizard-style flows. Flag mistakes before they happen.

### Persona B — The Regular User
*Experienced lab member, runs standard assays weekly*

- Knows the workflow but gets stuck on non-standard scenarios (new analyte, different chip, changing flow rates)
- Wants fast, precise answers — no hand-holding
- Uses method builder, exports regularly, cares about data quality
- Questions are specific: "what regeneration conditions work for antibody–antigen?"

**Sparq goal:** Be a fast reference, a troubleshooter, and a method optimizer. Respect their time.

### Persona C — The Expert / Lab Manager
*Senior scientist or PI, runs multiple experiments, reviewes others' data*

- Understands SPR deeply, wants advanced AI analysis
- Wants Sparq to compare runs, flag quality issues across sessions, suggest kinetics fitting strategies
- Wants AI-generated QC summaries for their lab reports
- May want to customize Sparq behavior for their team

**Sparq goal:** Provide analytical intelligence, cross-experiment insights, and report-ready outputs. Be a co-investigator.

---

## 4. Product Scope — End-to-End Coverage

Sparq covers the full SPR research lifecycle. Each phase maps to specific Sparq capabilities:

### Phase 1: Experimental Design
*Before the instrument is even turned on*

- Guide the user through assay design: what to immobilize, what analyte concentrations to use, what regeneration strategy fits their biomolecule class
- Recommend cycle templates for their experimental goal (kinetics, screening, titration, competition)
- Validate method parameters: warn if contact time is too short, flow rate is incompatible with chip type, or selected channels are misconfigured for the hardware model
- Suggest Affinite-specific chip types and buffers based on analyte class

### Phase 2: Instrument Setup & Calibration
*Hardware connection through calibration complete*

- Step-by-step connection guide tailored to detected hardware (P4SPR vs P4PRO vs P4PROPLUS)
- Priming guidance, pump check, valve position confirmation
- Calibration wizard — explain what each calibration step does and what good vs. bad results look like
- Proactive warnings: "Your last calibration was 14 days ago — consider recalibrating before this run"

### Phase 3: Acquisition
*Live — experiment is running*

- Real-time context: detect current phase (baseline, association, dissociation) and offer that phase's guidance
- Flag anomalies as they appear: baseline drift, noise spikes, unexpected dip shift direction
- Answer mid-run questions without disrupting acquisition
- Injection timing guidance for P4SPR manual injection users

### Phase 4: Data Analysis
*Post-acquisition, in Affilabs.core*

- Interpret the sensorgram: explain what the curve shape means in plain language
- Identify artifacts: air bubbles, pressure spikes, incomplete regeneration
- Suggest analysis pipeline settings (which baseline correction, which peak-finding method)
- Guide kinetics fitting: what constraints to apply, what a good fit looks like, what parameters are physically meaningful

### Phase 5: Reporting & Export
*Preparing data for papers, reports, or colleagues*

- Guide export: which format (CSV, Excel, ANIML) for which purpose
- Help write figure legends or results-section text for SPR data
- QC checklist before export: are all controls present? Is the baseline stable? Are replicates consistent?
- For Expert/Lab Manager persona: generate AI-written summary of experiment quality

---

## 5. User-Specific Intelligence

Sparq has access to the Affilabs.core **UserProfileManager** and uses it to deliver personalized, adaptive assistance.

### What Sparq Knows About the User

| Data | Source | How Sparq Uses It |
|------|--------|------------------|
| Active user name | `UserProfileManager.get_active_user()` | Personalizes greetings, references previous work |
| User created date | `UserProfile.created_date` | Detects novice (new user) vs. experienced |
| Last active date | `UserProfile.last_used` | Adjusts guidance verbosity — long absence → more detail |
| Sparq Q&A history | `spark_qa_history.json` per-user | Avoids repeating answers, learns vocabulary |
| Experiment pattern | `spark_workflow_log.json` per-user | Infers preferred cycles, method templates, common flows |

### Workflow Learning

Sparq passively observes (with user consent) what the user does in the app:
- Which tabs they visit most
- Which cycle types they use
- How often they run calibration
- What export format they prefer
- Where they get stuck (repeated questions on same topic → Sparq proactively offers help)

Over time, Sparq builds a per-user **workflow profile** that enables:
- **Proactive suggestions:** "Based on your usual method, you might want to add a dissociation cycle here"
- **Shortcut answers:** "Last time you ran a titration, you used 25 µL/min — use the same?"
- **Risk alerts:** "You usually calibrate before this type of run. Would you like to run calibration now?"

### User Skill Level Detection

Sparq infers skill level from:
1. `created_date` (new user = lean toward novice guidance)
2. Vocabulary in questions (technical terms = expert mode)
3. Pattern of questions (repeated basic questions = novice; advanced analytical questions = expert)
4. Number of Q&A interactions (>50 = experienced Sparq user)

The inferred level determines:
- Response verbosity (step-by-step vs. concise)
- Jargon usage (plain language vs. technical terms)
- Proactive warnings (more for novice, fewer for expert)
- Feature suggestions (basics for novice, advanced pipelines for expert)

---

## 6. Answer Engine Architecture

### Design Philosophy

Sparq's intelligence is **knowledge-driven, not generation-driven**. The primary content that answers user questions is a curated library of well-written SPR guidelines, worked examples, and Affinite-specific procedures — authored by Affinite's team. AI components serve specific support roles, not the lead role:

| Component | Role | What It Is NOT |
|-----------|------|----------------|
| **Curated Knowledge Base** | Primary answer source — the expert | Not generated text; authored by Affinite |
| **Pattern Matcher** | Fast path for exact-match questions | Not learning; static, human-written |
| **TinyLM (TinyLlama-1.1B)** | Parsing assistant — interprets user phrasing and extracts intent to query the KB | Not the main brain; does not generate scientific answers |
| **Affinite Cloud Connection** | Human escalation path — connects user to Affinite support when KB is insufficient | Not a generic LLM chat; routes to real human expertise |

This architecture ensures every answer Sparq gives is traceable back to Affinite-authored content. There is no hallucinated SPR advice.

### Layer Stack

```
User Question
    ↓
Layer 0: USER CONTEXT INJECTION (always, < 1ms)
    ├── Active user profile (name, skill level, hardware model)
    ├── Current app state (acquisition phase, active channels)
    └── Question enriched before routing to any layer
    ↓
Layer 1: PATTERN MATCHER (< 1ms)
    ├── Pre-compiled regex for ~50+ exact-match question types
    ├── Instant answers for high-frequency, well-defined questions
    └── Returns immediately if matched — KB not consulted
    ↓ (no exact match)
Layer 2: KNOWLEDGE BASE — PRIMARY INTELLIGENCE (< 200ms)
    ├── Curated Affinite-authored articles, worked examples, and guidelines
    ├── Sections: experimental design · method builder · instrument setup ·
    │             troubleshooting · calibration · reporting
    ├── TinyLM parses the user's question → extracts intent + keywords
    ├── KB is searched using extracted intent (semantic-guided keyword search)
    ├── Relevance scoring: keyword hit (+3.0), title match (+2.0), content match (+1.0)
    └── Returns best matching article section(s); source always cited
    ↓ (KB score < threshold or question requires human judgment)
Layer 3: AFFINITE CLOUD ESCALATION (optional, user-initiated or auto-suggested)
    ├── Sparq surfaces: "I don't have a confident answer — would you like to ask Affinite?"
    ├── Packages question + context + hardware info into support ticket or live chat
    ├── Free tier: opens pre-filled email to support team
    └── Pro/Enterprise tier: real-time chat with Affinite application scientists
```

### The Role of TinyLM

TinyLlama-1.1B is **not** the answer engine. It serves as an intent parser — transforming the user's natural-language phrasing into a structured query that can efficiently search the curated KB:

```
User: "my baseline keeps moving up before I inject anything"
    ↓ TinyLM parses intent
Extracted: { topic: "troubleshooting", symptom: "baseline drift", phase: "pre-injection" }
    ↓ KB search with extracted intent
KB returns: "P4SPR Troubleshooting — Baseline Stability" article section
    ↓ Sparq presents the curated answer
```

TinyLM is lazy-loaded (first use per session, 10–30s). For pattern-matched questions, TinyLM is never invoked.

### Component Map

```
Sparq UI
└── SparkHelpWidget (affilabs/widgets/spark_help_widget.py)
    ├── AnswerGeneratorThread        — background thread, UI never blocked
    └── SparkAnswerEngine (affilabs/widgets/spark_answer_engine.py)
        ├── UserContextBuilder       — user profile + app state injection
        ├── SparkPatternMatcher      — Layer 1 fast path
        ├── SparkKnowledgeBase       — Layer 2 curated content store
        ├── SparkTinyLM              — Layer 2 intent parser (supports KB search)
        └── SparkCloudEscalation     — Layer 3 Affinite support routing [future]
```

### Knowledge Base — Content Architecture

The KB is organized into **domains**, each built out for P4SPR first:

| Domain | Content Type | P4SPR Priority |
|--------|-------------|----------------|
| **Method Builder** | Cycle syntax reference, worked examples (titration, kinetics, amine coupling), channel tagging guide, `@spark` command catalog | ⭐ First to build — new language users must learn |
| **Experimental Design** | Assay design decision trees, concentration selection, chip/buffer pairing, regeneration chemistry | ⭐ Critical for novice persona |
| **Instrument Setup** | P4SPR startup sequence, syringe connection, manual injection technique, timing for multi-channel | High |
| **Troubleshooting** | Symptom → cause → fix tables for P4SPR (Phase 2 focus — see roadmap) | High |
| **Calibration** | Step-by-step calibration, what good vs. bad results look like | Medium |
| **Data & Export** | Export formats, analysis pipeline selection, results interpretation | Medium |
| **SPR Concepts** | Physics primer: what is SPR, what the dip means, blue shift on binding, P vs S polarization | Reference — all levels |

**Content format:** Each entry is a **plain-text article** with: `title`, `summary` (2 sentences), `full_text` (step-by-step or explanation), `keywords[]`, `hardware_tags[]` (e.g., `["p4spr", "all"]`), `persona_level` (`novice` / `any` / `expert`), and optional `example_code` (cycle syntax snippets).

---

## 7. Feature Roadmap

The roadmap follows a logical user journey: **design the method → calibrate the instrument → run the experiment → troubleshoot issues → optimize workflows**. Phase 1 (Method Builder) is P4SPR-first. Phase 2 (Calibration) is **universal** — all Affinite models share identical calibration systems. Phase 3+ return to P4SPR-first development.

---

### Phase 1 — Method Builder Mastery (P4SPR) ✅ SHIPPED
*Goal: make Sparq the best possible guide for building SPR experiments, centered on the Method Builder and its cycle language.*

Method Builder is the newest and most important feature in Affilabs.core. It introduces a **new syntax language** that users must learn (cycle types, duration, channel tags, concentration notation, contact time). Sparq must be fluent in this language and guide users — especially P4SPR users with 4 independent manual channels — through designing meaningful, scientifically sound experiments.

#### v0.1 — Foundation ✅ SHIPPED (Feb 2026)
- [x] `SparkHelpWidget` in sidebar Help tab
- [x] `SparkMethodPopup` in MethodBuilderDialog — inline `@spark` method generation
- [x] Pattern matching for `@spark` commands: titration, kinetics, amine coupling, build N, regeneration, baseline, full cycle
- [x] Multi-turn conversation in method popup (ask → answer → generate)
- [x] TinyLlama local AI — lazy-loaded, background thread, used as fallback parser
- [x] Q&A history persistence (per-user JSON files)
- [x] Helpful / Not Helpful feedback buttons
- [x] Zero-crash guarantee (all layers wrapped in try/except)
- [x] User-aware personalization (greeting, per-user history)
- [x] P4SPR-specific KB articles (5 articles: channels, injection, concentration, workflow, vs P4PRO)
- [x] P4SPR-specific patterns (9 patterns covering manual injection, 4-channel system)
- [x] Method validation warnings (contact time, channel mismatch, missing regen)
- [x] Preset save suggestion (auto-triggered for ≥3-cycle methods)

#### v0.2 — Knowledge Base Foundation (P4SPR Method Builder KB)
*Build the curated content that is Sparq's primary intelligence.*

- [ ] Author and load **Method Builder KB articles** for P4SPR:
  - [ ] Cycle syntax reference (all types, all duration formats, all channel tag variants)
  - [ ] Worked example: 5-point titration for P4SPR — which channels to use, why
  - [ ] Worked example: kinetics with dissociation phase — timing guidance for P4SPR manual injection
  - [ ] Worked example: amine coupling full workflow — immobilization, blocking, binding series
  - [ ] Channel tagging guide — `[A:100nM]` vs `[ALL]` vs `[A:100nM][B:50nM]` — when and why
  - [ ] Concentration selection primer — how to choose a titration series starting point
  - [ ] Regeneration chemistry guide — which buffer for which biomolecule class
  - [ ] Contact time guidance by cycle type — P4SPR-specific (manual injection timing)
  - [ ] `@spark` command catalog — every command, what it generates, how to modify the output
- [ ] Enable KB Layer 2 in `SparkAnswerEngine` (currently commented out)
- [ ] Wire TinyLM as intent parser feeding KB search (not standalone answer generator)
- [ ] Connect `UserProfileManager` — load active user; per-user Q&A history
- [ ] Novice vs. expert detection — response verbosity adapts per persona
- [ ] Expand pattern matcher to 100+ Method Builder-specific patterns

#### v0.3 — Smart Method Design for P4SPR
*Sparq actively helps design the experiment, not just generate syntax.*

- [ ] **Experimental goal wizard**: conversational flow — "What are you trying to measure?" → recommended cycle sequence with explanation
- [ ] **P4SPR channel assignment assistant**: "You have 4 channels — here's how to assign sample, reference, and replicates for your assay type"
- [ ] **Method parameter validator** — inline warnings in MethodBuilderDialog:
  - Contact time too short for the injection volume at current flow rate
  - Dissociation phase missing after association (warn on kinetics intent without dissociation)
  - Regeneration missing between binding cycles
  - Channel conflict: same channel assigned multiple concentrations in same cycle
- [ ] **Concentration series generator** — ask analyte Kd estimate (or "unknown") → suggest starting concentration and dilution fold
- [ ] **Preset suggestion** — after building a method, Sparq suggests saving it: "This looks like a standard titration — save as preset?"
- [ ] **`!save` and `@preset` guidance** — KB articles explaining the preset system with examples

---

### Phase 2 — Calibration Intelligence (Universal: All Models)
*Goal: Sparq as the definitive guide to instrument calibration — the critical gate before any experiment can run.*

**Why Phase 2:** Calibration is the #1 barrier to successful instrument use. Users cannot acquire data, build methods, or troubleshoot anything without completing calibration first. It is the **prerequisite for all downstream workflows**. Unlike Method Builder (P4SPR-first), calibration is **universal** — P4SPR, P4PRO, and P4PROPLUS all use identical calibration procedures. Solving calibration for one model solves it for all.

**User pain:** Calibration fails cryptically. QC reports show red flags without explanation. Users don't know when to recalibrate, which calibration type to run, or how to interpret results. This is the highest-volume Affinite support request category.

#### v0.4 — Calibration Knowledge Base (Universal)
*Author the expert-level calibration content that all users need.*

- [ ] Author **Calibration KB Articles** (distilled from `docs/calibration/*.md` — 5000+ lines of existing documentation):
  - [ ] **What is Calibration?** — Why it's required, what it measures, when it runs (first use, after hardware changes, daily/weekly, on QC failure)
  - [ ] **Calibration Types Explained** — 5 calibration types with decision tree:
    - Startup calibration (auto, 1-2 min, runs on Power On)
    - Simple LED calibration (10-20 sec, for same-type sensor swaps)
    - Full LED calibration (5-10 min, after new sensor or hardware changes)
    - Servo position calibration (barrel: 1.4 min, circular: ~13 measurements, first-time setup only)
    - OEM Optical calibration (10-15 min, factory-only, afterglow characterization)
  - [ ] **When to Recalibrate** — Decision guide: daily best practice, mandatory after hardware changes, recommended if QC warnings appear, before critical experiments
  - [ ] **Interpreting QC Reports** — What each QC metric means (SNR, LED convergence, P/S ratio range), what thresholds are acceptable, what red flags require action
  - [ ] **Calibration Failure Troubleshooting** — Symptom → cause → fix for common failures:
    - Startup calibration fails → check flow path obstructions, USB connection, detector power
    - LED convergence fails → check LED saturation, integration time limits, fiber alignment
    - "LED model not found" error → run OEM calibration first to populate LED response curve
    - Servo position calibration fails → for barrel polarizer: check prism alignment; for circular: ensure water on sensor for SPR detection
    - QC score below threshold → cleaning protocol, recalibration steps
  - [ ] **Step-by-Step Calibration** — Walkthrough for each calibration type with screenshots and expected progress messages
  - [ ] **Calibration Data Persistence** — Where calibration data is stored (`device_config.json`, `optical_calibration.json`), what gets saved, how it's reused across sessions

- [ ] All calibration articles structured as: **What → When → Why → How → What Good Looks Like → Troubleshooting**
- [ ] Universal content — same procedures for P4SPR, P4PRO, P4PROPLUS (only servo hardware differs, covered in separate article)

#### v0.5 — Calibration Patterns (Universal)
*Fast-path answers for high-frequency calibration questions.*

- [ ] Expand **calibration pattern category** in `patterns.py` from 3 patterns to 15+:
  - [ ] "how do I calibrate" / "run calibration" / "start calibration" → startup vs. full decision guide
  - [ ] "calibration failed" / "calibration error" → triage question: which calibration type? what error message?
  - [ ] "QC report" / "what does this QC mean" / "QC score" → link to QC interpretation KB
  - [ ] "LED saturation" / "LED too bright" → reduce integration time, check for fiber misalignment
  - [ ] "servo error" / "polarizer calibration failed" → barrel vs. circular troubleshooting
  - [ ] "when to recalibrate" / "how often calibrate" → daily best practice answer
  - [ ] "missing channel D" / "optical calibration incomplete" → OEM feature, DEV=True required
  - [ ] "simple vs full calibration" / "which calibration should I run" → decision tree
  - [ ] "first time setup" / "new instrument calibration" → full calibration sequence guide
  - [ ] "calibration takes too long" → expected times per calibration type
  - [ ] "SNR too low" / "signal quality" → QC metric explanation, recalibration guide
  - [ ] "P vs S polarization" / "wrong polarity" → servo validation, recalibration if inverted
  - [ ] "afterglow correction" / "optical calibration" → OEM-only feature explanation

#### v0.6 — Calibration Wizard (Interactive)
*Sparq guides users through calibration step-by-step with real-time validation.*

- [ ] **Calibration wizard flow** — multi-turn conversation:
  - Sparq asks: "Is this your first time calibrating this instrument, or have you calibrated before?"
  - Based on answer: routes to "first-time full calibration" vs. "routine recalibration"
  - Step-by-step prompts: "Click Settings → Power On" → wait for startup calibration → "Did the QC report pass?"
  - If QC fails: Sparq asks for specific error, provides targeted fix
  - If QC passes: "You're ready to start acquiring data. Go to the Flow tab and build your method."
- [ ] **Real-time QC interpretation** — when user shares QC results (screenshot or typed metrics), Sparq parses and explains in plain language:
  - "Your SNR is 85:1 across all channels — excellent signal quality."
  - "Channel B's LED convergence was marginal (3.2% error) — acceptable, but watch for drift. Consider recalibrating if baseline looks noisy."
  - "P/S ratio is inverted on Channel A — your servo position may need recalibration."
- [ ] **Proactive recalibration reminders** — Sparq tracks last calibration date per user and hardware:
  - "It's been 14 days since your last full calibration. I recommend recalibrating before starting this kinetics experiment."
  - User can dismiss or snooze reminder

---

### Phase 3 — Acquisition Troubleshooting (P4SPR)
*Goal: Sparq as the first line of support when something goes wrong during live acquisition — before the user emails Affinite.*

Troubleshooting is the highest-volume support request for P4SPR users after calibration issues. The instrument has no automated diagnostics — all failure modes manifest as sensorgram anomalies that the user must interpret. Sparq should recognize symptoms and guide resolution step by step.

#### v0.7 — P4SPR Acquisition Troubleshooting Knowledge Base
*Author the troubleshooting content — symptom → cause → fix.*

- [ ] Author **P4SPR Acquisition Troubleshooting KB** covering all common failure modes:

  | Symptom | Likely Causes | Sparq Guides To |
  |---------|--------------|----------------|
  | Baseline drifting upward | Incomplete priming, air in flow cell, thermal drift, chip not equilibrated | Priming protocol, equilibration wait |
  | Baseline drifting downward | Ligand dissociating, chip degradation, buffer mismatch | Chip condition check, buffer pH verification |
  | Spiky noise in signal | Air bubbles, loose fiber connection, flow obstruction | Degassing, connector check, flow path inspection |
  | No binding response | Wrong channel active, ligand not immobilized, analyte inactive, wrong polarization | Channel verification, calibration check |
  | Asymmetric channels (A≠C when same sample) | Air bubble in one flow cell, different chip surface quality, different immobilization | Individual channel priming |
  | Regeneration incomplete | Regeneration buffer too weak, too short contact time, surface saturation | Regeneration optimization guidance |
  | Signal lost mid-experiment | Fiber disconnected, LED failure, USB disconnect | Connection checklist, recovery steps |
  | Baseline won't stabilize before injection | Insufficient baseline time, flow rate instability, thermal issue | Timing guidance, environment checklist |
  | Injection detection failed | P4SPR inter-channel timing skew, weak analyte signal, detection sensitivity too low | Detection settings guide, manual flag placement |
  | Blue shift not detected | Analyte not binding, wrong sensorgram polarity, detection threshold too high | Binding validation checklist, sensitivity adjustment |

- [ ] All troubleshooting articles structured as: **Symptom → When it happens → Step-by-step diagnosis → Fix → Prevention**
- [ ] P4SPR-specific procedures: manual syringe technique, injection timing, inter-channel delay tolerance

#### v0.8 — Active Acquisition Troubleshooting Assistant
*Sparq moves from reference to interactive diagnostic guide.*

- [ ] **Symptom intake flow**: "Describe what you're seeing" → Sparq asks clarifying questions (which channel? when did it start? did you recently change anything?) → narrows to likely cause
- [ ] **Phase-aware troubleshooting**: Sparq knows acquisition is running and what phase — adjusts advice accordingly ("Since you're in dissociation, avoid stopping flow — try...") 
- [ ] **Affinite escalation**: if KB doesn't resolve the issue after 2–3 exchanges, Sparq offers: "Would you like me to package this for Affinite support?" — pre-fills a support request with the symptom, hardware model, and conversation history
- [ ] **Recovery procedure library**: step-by-step recovery scripts for the most common P4SPR recovery scenarios

---

### Phase 4 — Affinite Product Proposals for Specific Experiments
*Goal: Sparq becomes a trusted advisor that recommends the right Affinite instrument, chip, and accessory for a user's experimental objective — not a generic list of products, but a specific, justified recommendation grounded in what the user is trying to measure.*

This phase positions Sparq as a pre-sales and upgrade advisor embedded in the instrument software. When a user describes an experiment that is difficult or impossible on their current setup, Sparq recognizes the gap and proposes the Affinite solution — with a clear rationale.

#### v0.9 — Experimental Goal → Product Fit KB
*Author the content that maps experimental needs to Affinite solutions.*

- [ ] Author **Product Proposal KB**: for each experiment type, document which Affinite configuration is optimal and why:

  | Experimental Goal | Current P4SPR Limitation | Sparq Proposes |
  |-------------------|--------------------------|----------------|
  | Kinetics with automated injection timing | Manual injection introduces ±15s inter-channel skew | AffiPump upgrade → P4PRO configuration |
  | Running 2 different samples simultaneously with precise timing | P4SPR manual injection cannot guarantee simultaneous delivery | P4PRO with 6-port valve: AC and BD pairs |
  | High-throughput screening (>20 analytes/day) | Manual injection limits throughput | P4PROPLUS with internal pumps for continuous automated flow |
  | Very low Kd (<1 nM) — needs long, stable dissociation | Manual injection quality limits long stable runs | AffiPump + P4PRO: pulse-free, programmable |
  | Multi-ligand chip (different ligand per channel) | Already native to P4SPR — 4 independent channels | P4SPR is the right tool — Sparq confirms |

- [ ] Proposals always include: **why this experiment is hard on the current setup**, **what the upgrade adds**, and **what stays the same** (Sparq never oversells — if P4SPR is the right tool, Sparq says so)
- [ ] Proposals link to Affinite website product pages (for in-app display)
- [ ] Trigger conditions: Sparq detects proposal opportunity when user asks about experiment types that strain the current hardware model

#### v1.0 — Context-Triggered Proposal Engine
*Sparq surfaces relevant product suggestions at the right moment, not as ads.*

- [ ] **Method Builder trigger**: if user builds a method with simultaneous multi-channel injection intent on P4SPR, Sparq flags the manual injection limitation and explains the P4PRO option inline
- [ ] **Troubleshooting trigger**: if user repeatedly hits the same P4SPR limitation (e.g., injection timing issues across multiple sessions), Sparq proactively surfaces the upgrade path
- [ ] **Chip and consumable recommendations**: for detected analyte classes, Sparq recommends appropriate Affinite sensor chip type and surface chemistry
- [ ] User can dismiss proposals permanently ("Don't suggest this again") — stored in user profile

---

### Phase 5 — Flow Integration
*Goal: Sparq is aware of and interactive with live fluidics — pump state, valve position, flow rate, and flow events — making it a real-time flow advisor during experiment setup and execution.*

This phase bridges Sparq from a knowledge assistant to an active participant in the fluidic workflow. For P4SPR, flow is manual — Sparq guides injection timing. For P4PRO/PROPLUS, flow is programmable — Sparq helps configure it.

#### v1.1 — P4SPR Manual Flow Guidance
*Making the most of manual injection — the hardest part of P4SPR for new users.*

- [ ] **Injection readiness check**: before each association cycle, Sparq confirms prerequisites — baseline is stable, correct cycle is active, syringe is loaded — and prompts the user when ready to inject
- [ ] **Per-channel injection sequencing**: "Start with Channel A → wait 3–5 seconds → Channel B → Channel C → Channel D. Your inter-channel delay should be under 15 seconds total."
- [ ] **Contact time countdown**: Sparq displays a countdown from cycle start and alerts when to stop injection and allow dissociation to begin
- [ ] **KB: Manual injection technique guide** — step-by-step for P4SPR: how to load syringe, purge air, inject at correct flow rate by feel, timing tips for reproducible inter-channel delivery

#### v1.2 — P4PRO / P4PROPLUS Automated Flow Integration
*Sparq understands pump programming and helps users configure it correctly.*

- [ ] Sparq reads current pump state from `PumpMixin` / `pump_hal.py` and incorporates it into context
- [ ] **Flow rate advisor**: validates user's intended flow rate against cycle type and chip requirements
- [ ] **P4PRO pump programming guide**: volume, flow rate, speed profile per injection — KB articles for each parameter
- [ ] **P4PROPLUS constraint enforcement**: minimum contact time warnings (180s at 25 µL/min), on/off-only pump limitations — Sparq explains why these constraints exist and what to do
- [ ] **Valve state awareness**: Sparq knows 6-port valve position (load vs. inject) and can explain what position is expected at each method step

---

### Phase 6 — User Memory and Data Retrieval
*Goal: Sparq remembers what each user has done and asked before, and can find their raw data using natural-language descriptions of what they remember about an experiment.*

This phase transforms Sparq from a session-scoped assistant to a persistent lab memory. Combined with Affilabs.core's existing file export system, Sparq can retrieve specific past datasets when a user describes them in natural language — even years later.

#### v1.3 — Q&A Memory and Conversational Continuity
*Sparq remembers what you've asked and learned.*

- [ ] **Per-user persistent Q&A memory**: every question and answer stored per user (already partially built in `spark_qa_history_{user}.json`), now actively used:
  - "You asked about regeneration chemistry 3 weeks ago — the answer was glycine-HCl pH 2.0 for antibody–antigen. Still relevant?"
  - Sparq skips re-explaining things the user has already learned and marked helpful
- [ ] **Topic repetition detection**: if a user asks the same topic ≥3 times, Sparq surfaces a deeper KB article or offers to escalate to Affinite ("This keeps coming up — want me to connect you with support?")
- [ ] **Cross-session experiment continuity**: "Last time you ran this method, you noted the baseline was unstable. Did that resolve?"
- [ ] **User-defined memory items**: user can tell Sparq to remember things — "Remember: I'm using PBS pH 7.4 as running buffer for all antibody experiments" — stored in user profile and injected into relevant answers

#### v1.4 — Raw Data Retrieval by Metadata
*Find past experiments by describing what you remember, not by knowing the file name.*

The exported data files from Affilabs.core contain rich metadata — experiment date, cycle types, channel concentrations, duration, delta SPR values. Sparq indexes this metadata and lets users retrieve files by describing the experiment.

- [ ] **Metadata index**: at export or session end, Sparq indexes the session's metadata into a per-user local store:
  - Date/time, hardware model, cycle types used, concentration values, number of channels active, overall experiment duration, delta SPR per channel
- [ ] **Natural-language retrieval queries**: user asks Sparq to find data:
  - "Find my titration run from last month with antibody at 100–500 nM on Channel A"
  - "Show me the run where I had the highest binding on Channel C"
  - "Find all kinetics experiments from Q4 2025"
  - "What was my regeneration time in the run where Channel B had no signal?"
- [ ] **Result presentation**: Sparq returns a list of matching sessions with key metadata summary and the file path to open or re-export
- [ ] File path integration: clicking a result opens the folder or re-loads the session data into the analysis view

---

### Phase 7 — Paid Tier: Reporting, Interpretation, and Historical Comparison
*Goal: premium Sparq capabilities that directly accelerate publication and institutional decision-making — the features that justify a subscription.*

> ⚠️ **Pricing strategy for this phase requires a separate business decision** (tier structure, price points, free vs. paid boundary). The features below are confirmed in scope; the commercial model is to be determined.

#### Candidate Features (Scope Confirmed, Tier TBD)

**Report Generation**
- Sparq generates a structured experiment summary report: method overview, binding responses per channel, key observations, data quality flags
- Export as PDF or Word — ready to share with PI or include in lab notebook
- For amine coupling experiments: generates immobilization report (ligand density, surface quality assessment)
- For kinetics: includes curve shape description and flags potential fitting concerns

**Sensorgram Interpretation**
- User shares a sensorgram (screenshot or live data reference) → Sparq describes what it sees in plain language
- Identifies curve features: fast-on/slow-off, mass transport limitation signs, regeneration completeness, reference channel subtraction quality
- Flags anomalies with plain-language explanations: "The sharp downward spike at 12 minutes is consistent with an air bubble"
- For novice persona: "This looks like a good binding event — here's what each part of the curve means..."

**Next Experiment Suggestions**
- After reviewing a completed run, Sparq suggests logical next experiments:
  - "Your Kd appears to be in the 50–200 nM range based on this titration. I'd suggest running kinetics at 3 concentrations bracketing 100 nM."
  - "Regeneration at 50mM glycine pH 2.5 was incomplete — try pH 2.0 or 10mM NaOH next."
  - "Channel B had no signal — consider checking immobilization before re-running"
- Suggestions are KB-grounded (not generated) and always actionable

**Historical Comparison**
- Compare two or more past experiments by metadata and delta SPR:
  - "Compare my last 3 titrations of antibody X — is binding improving after regeneration optimization?"
  - "Did my Kd change between Chip Lot A and Chip Lot B?"
- Generates a side-by-side summary table of key metrics
- Flags statistically meaningful differences vs. run-to-run noise

**Affinite Application Scientist Integration (Pro/Enterprise)**
- Pro tier: async question submission to Affinite application team (48h response SLA)
- Enterprise tier: real-time chat/video session booking with Affinite scientists
- Auto-packages context: hardware model, session metadata, conversation history, sensorgram screenshot
- Sparq drafts the support question for the user — they review and send

---

## 8. Technical Architecture

### Source File Locations

```
affilabs/widgets/
├── spark_help_widget.py         # Main UI, AnswerGeneratorThread, feedback
├── spark_answer_engine.py       # Answer coordinator, layer routing
├── spark_pattern_matcher.py     # Layer 1: pre-compiled regex patterns
├── spark_knowledge_base.py      # Layer 2: TinyDB knowledge base search
├── spark_tinylm.py              # Layer 3: TinyLlama integration
└── spark_cloud_client.py        # Layer 4: Cloud API client [future]

Runtime data (auto-created at root):
├── spark_qa_history_{user}.json   # Per-user Q&A history [v0.2+]
├── spark_knowledge_base.json      # Local knowledge base content
└── spark_workflow_log_{user}.json # Per-user workflow events [v0.3+]
```

### Threading

All answer generation runs in `AnswerGeneratorThread` (daemon `threading.Thread`). The UI is never blocked. The model loading uses `threading.Lock()` with double-check pattern to prevent concurrent load races.

### User Context Injection

At question submission, before routing to any layer, Sparq assembles a context dict:

```python
context = {
    "user": user_profile_manager.get_active_user(),
    "user_age_days": (today - user.created_date).days,
    "hardware": hardware_mgr.get_status()["ctrl_type"],
    "has_affipump": hardware_mgr.has_affipump(),
    "active_channels": acquisition_mgr.get_active_channels(),
    "acquisition_phase": current_phase,   # baseline/association/etc.
    "last_sparq_topics": recent_topics_from_history,
}
```

This context is passed to all layers. Pattern responses can be templated with it. The TinyLlama system prompt is built from it.

### Pattern Matcher Implementation

```python
# Pre-compiled at init — never re-compile on each question
self._compiled_patterns = [
    (re.compile(regex, re.IGNORECASE | re.DOTALL), answer_template)
    for regex, answer_template in PATTERNS.items()
]

def match_question(self, question: str, context: dict) -> str | None:
    for compiled, template in self._compiled_patterns:
        if compiled.search(question):
            return template.format(**context)   # context-aware answer
    return None
```

### TinyLlama System Prompt (Layer 3)

```
You are Sparq, the AI assistant built into Affilabs.core — software for surface
plasmon resonance (SPR) instruments made by Affinite Instruments.

You are helping: {user_name} ({skill_level} user, using {hardware_model}).
Current phase: {acquisition_phase}.

You help with: experimental design, instrument operation, data analysis, and
reporting for SPR experiments in the Kretschmann configuration using spectral
interrogation (wavelength-based, not angular).

Rules:
- Only recommend Affinite Instruments products and Affilabs.core features.
- Keep answers under 150 words unless the question requires more.
- Use plain language for novice users, technical precision for experts.
- The SPR resonance dip is a MINIMUM in transmission (not a peak).
- Binding causes a BLUE SHIFT (wavelength decreases), not a red shift.
- Answer in the active user's context.
```

---

## 9. Data & Storage Schema

### Q&A History (per user)

**File:** `spark_qa_history_{username}.json`

```json
{
  "questions_answers": {
    "1": {
      "timestamp": "2026-02-18T10:30:00.000000",
      "question": "how do I start an acquisition?",
      "answer": "To start an acquisition: ...",
      "layer_used": "pattern",
      "hardware_context": "PicoP4SPR",
      "phase_context": "idle",
      "feedback": "helpful"
    }
  }
}
```

**Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `timestamp` | ISO datetime | History ordering |
| `question` | string | Original user input |
| `answer` | string | Sparq response |
| `layer_used` | `pattern` / `kb` / `tinylm` / `cloud` | Which layer answered |
| `hardware_context` | string | Hardware at time of question |
| `phase_context` | string | Acquisition phase at time |
| `feedback` | `null` / `helpful` / `not_helpful` | User rating |

### Knowledge Base

**File:** `spark_knowledge_base.json`

```json
{
  "articles": {
    "1": {
      "title": "Multi-Channel Detection Setup",
      "content": "...",
      "category": "tutorials",
      "keywords": ["channels", "multi-channel", "A", "B", "C", "D"],
      "url": "https://www.affiniteinstruments.com/docs/channels",
      "last_updated": "2026-02-18T10:00:00"
    }
  }
}
```

**Content Categories:**

- `getting-started` — First-time user flows
- `calibration` — Calibration procedures and QC
- `troubleshooting` — Error states, noise, drift
- `tutorials` — Step-by-step workflows
- `product-features` — Affilabs.core feature guides
- `faqs` — Frequently asked questions
- `experimental-design` — Assay setup guidance

### Relevance Scoring Algorithm

```python
score = 0
if any(kw in question_lower for kw in article["keywords"]):
    score += 3.0   # keyword hit
if search_term in article["title"].lower():
    score += 2.0   # title hit
if search_term in article["content"].lower():
    score += 1.0   # content hit
# Return if score > 2.0
```

### Workflow Log (v0.3+, opt-in)

**File:** `spark_workflow_log_{username}.json`

```json
{
  "events": [
    {
      "timestamp": "2026-02-18T09:00:00",
      "event": "cycle_added",
      "detail": {"cycle_type": "association", "duration_s": 120}
    },
    {
      "timestamp": "2026-02-18T09:15:00",
      "event": "calibration_run",
      "detail": {"result": "passed"}
    }
  ]
}
```

---

## 10. Cloud AI Premium Tier

### Tier Structure

| Tier | Price | AI Source | Analyses | Vision |
|------|-------|-----------|----------|--------|
| **Free** | Included | TinyLlama local | Unlimited text | No |
| **Pro** | $39/month | GPT-4o or Claude 3.5 Sonnet | 100/month | Yes |
| **Enterprise** | $199+/month | Any, custom | Unlimited | Yes + batch |

### Cloud Architecture

```
Affilabs.core Desktop
    │  HTTPS (TLS 1.3)
    ▼
Affinite Backend API (FastAPI + PostgreSQL + Redis)
    ├── Auth: JWT tokens (30-day expiry)
    ├── Rate limiting: token bucket per user
    ├── Usage metering: track analyses per billing cycle
    └── LLM routing: OpenAI SDK / Anthropic SDK
    ▼
LLM Provider
    └── Response streamed via Server-Sent Events (SSE) → live typing in UI
```

### Premium Feature Set (Pro+)

- **Vision analysis:** User captures sensorgram screenshot → AI describes quality, flags issues, estimates binding behavior
- **Kinetics interpretation:** Upload processed sensorgram data → AI explains ka, kd, KD in plain language, flags unphysical fits
- **Cross-run comparison:** "Why does run 3 look different from run 1?"
- **QC Report generation:** AI writes a structured quality summary for the full session
- **Custom context upload:** Lab can upload their own SOPs, and Sparq references them

### Economics

- GPT-4o text: ~$0.005–0.02 per analysis
- GPT-4 Vision: ~$0.02–0.05 per sensorgram
- Pro tier: $39/month, 100 analyses → ~91% gross margin

### Fallback Strategy

Cloud is always optional. If the API is unavailable:
1. Sparq transparently falls back to Layer 3 (TinyLlama)
2. User sees: "Cloud features unavailable — using local AI"
3. No interruption to core functionality

---

## 11. Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Context injection (Layer 0) | **< 1 ms** | Dict assembly from in-memory objects |
| Pattern match (Layer 1) | **< 1 ms** | Pre-compiled regex, measured ~0.5 ms |
| KB intent parse via TinyLM | **< 3 s** | TinyLM extracts keywords/intent to query KB; lazy-loaded first use |
| KB search + article retrieval (Layer 2) | **< 200 ms** | TinyDB with RLock after intent is extracted |
| Total Layer 2 response (first use) | **< 35 s** | TinyLM load (30s) + parse + KB search |
| Total Layer 2 response (warm) | **< 5 s** | TinyLM already loaded — parse + KB search only |
| Affinite cloud escalation (Layer 3) | **User-initiated** | Opens support email or live chat; not a timed operation |
| UI responsiveness during any call | **0 ms block** | All layers run in background thread — UI never freezes |

---

## 12. Privacy & Compliance

### Local-First Data Handling

All Q&A data is stored locally in `spark_qa_history_{user}.json` in the app directory. No data leaves the machine unless the user opts into cloud features.

**What Sparq stores:**
- Questions and answers
- Feedback ratings
- Timestamp and hardware context
- Workflow events (opt-in only)

**What Sparq never stores:**
- Sample names or experimental data values
- File contents or measurement arrays
- Personal information beyond the username already in UserProfileManager
- System passwords or license keys

### Cloud Data Handling (Pro/Enterprise)

- Questions and sensorgram screenshots are sent to Affinite backend, then forwarded to the LLM provider
- Sample-identifying strings are stripped from questions before transmission (best-effort anonymization)
- No persistent storage of sensorgram images at the backend (pass-through only)
- All API traffic: HTTPS TLS 1.3

### Regulatory

| Standard | Applicability | Approach |
|----------|--------------|---------|
| GDPR | EU users | Opt-in consent for cloud, data deletion on request |
| HIPAA | Healthcare Enterprise customers | BAA, no persistent PHI storage |
| 21 CFR Part 11 | Pharma Enterprise | Audit trail export, timestamped Q&A log |

---

## 13. Branding & UX Direction

### Name: Sparq

The product is named **Sparq** — representing both the spark of insight an AI assistant provides and a phonetic nod to **SPR** (Surface Plasmon Resonance).

### Logotype Concept

The lettermark `Sparq` uses a **custom ligature** between the descending tail of the **p** and the ascending curve of the **q**: a stylized SPR sensorgram dip curve — a smooth arc that dips down (representing the resonance minimum) and rises back up, connecting the two letters organically.

```
  S p────┐ r q
         └──╯
      (sensorgram dip)
```

This should be designed as an SVG logotype for use in:
- App sidebar header (replaces current "Spark ⚡" text)
- Splash screen
- About dialog
- Marketing materials

### UX Voice

- **Novice user tone:** Warm, encouraging, step-by-step. "Here's how to do that — step by step..."
- **Expert user tone:** Direct, precise, no hand-holding. "Use percentile baseline with SG window 15, then centroid pipeline."
- **Error states:** Never blame the user. "That didn't work as expected — here's what to try."

### UI Location

Sparq lives in the **Help sidebar tab** (Tab 5) as `SparkHelpWidget`. It is also accessible inline from:
- `MethodBuilderDialog` — via `@spark` prompt for natural-language cycle creation
- Anomaly/warning toasts — "Ask Sparq about this" button on flagged events [v0.4+]
- Pre-export QC panel — "Ask Sparq to review" [v0.5+]

---

## 14. Success Criteria

### Phase 1 — Method Builder Mastery
- Sparq can generate correct, runnable cycle syntax for 100% of the 9 core P4SPR Method Builder scenarios (tested manually with each persona)
- Novice user can build a complete 5-point titration method on P4SPR using only Sparq guidance, without reading any documentation
- Parameter validator catches the 4 defined method mistakes (missing dissociation, missing regeneration, short contact time, channel conflict) with zero false positives
- KB Layer 2 enabled and contributing answers (layer_used = `kb` in >50% of non-pattern-matched questions)

### Phase 2 — Troubleshooting Intelligence (P4SPR)
- All 9 symptom categories in the troubleshooting table have authored KB articles
- Symptom intake flow correctly narrows to the right cause category in ≥80% of test scenarios
- Affinite escalation package is generated correctly (symptom + hardware + conversation) for 100% of escalation requests
- Users report "resolved my issue without contacting Affinite" for ≥60% of troubleshooting sessions (user survey)

### Phase 3 — Product Proposals
- Sparq surfaces a relevant product proposal in ≥90% of test scenarios where hardware limitation is the actual barrier
- Zero proposals surfaced when P4SPR is the correct tool for the job (no false upsell)
- Proposals include a clear rationale in plain language (validated by non-technical user reading)

### Phase 4 — Flow Integration
- P4SPR injection readiness check prevents premature injection in test scenarios
- Per-channel injection sequencing guide validated by P4SPR users as accurate and useful
- P4PROPLUS constraint warnings trigger correctly for contact times below 180s at 25 µL/min

### Phase 5 — User Memory & Data Retrieval
- Metadata retrieval returns correct file(s) for ≥85% of natural-language queries tested against a sample data library
- Q&A memory correctly surfaces a relevant prior answer when the same topic is re-asked
- Per-user data is fully isolated (no cross-user data visible)

### Phase 6 — Paid Tier (Success Criteria to be defined at business model review)
- Subscription conversion rate, report quality rating, and interpretation accuracy to be validated with pilot users before setting targets
- Pricing strategy and tier boundaries require a dedicated business review session before implementation begins

---

## 15. Out of Scope

The following are explicitly **not** in scope for Sparq:

- **Generic scientific literature search** — Sparq is Affinite-specific, not a PubMed interface
- **Instrument firmware control** — Sparq advises; it does not actuate hardware
- **Third-party instrument support** — Biacore, Sierra, etc. are not referenced positively
- **Custom ML model training for labs** — deferred to Enterprise roadmap only
- **Voice interface** — TTS/STT features removed from roadmap (sounddevice dependency dropped); text-only
- **Mobile app** — Windows desktop only, consistent with Affilabs.core platform

---

## 16. Implementation Notes — Current State (Feb 2026)

### What Is Actually Shipped and Working

| Component | Status | Notes |
|-----------|--------|-------|
| `SparkHelpWidget` | ✅ Working | Sidebar Tab 5, text chat, feedback buttons |
| `SparkPatternMatcher` | ✅ Working | ~50 patterns, pre-compiled regex |
| `SparkTinyLM` | ✅ Working | TinyLlama, lazy-loaded, background thread |
| `SparkAnswerEngine` | ✅ Working | Pattern → TinyLlama routing |
| `SparkKnowledgeBase` | ⚠️ Partial | File exists, search disabled in answer engine (KB Layer 2 commented out) |
| User context injection | ❌ Not started | No UserProfileManager connection yet |
| Per-user Q&A history | ❌ Not started | Single shared `spark_qa_history.json` |
| Workflow logging | ❌ Not started | No event capture |
| Cloud client | ❌ Not started | Concept only |

### Immediate Next Steps (v0.2 — P4SPR Method Builder KB)

1. **Author the KB content** — this is the highest-leverage work. Start with the 9 Method Builder articles listed in Section 6. Plain text, structured as: title / summary / full_text / keywords[] / hardware_tags[] / persona_level. Store in `spark_knowledge_base.json`.
2. **Enable KB Layer 2** — uncomment `kb_answer` block in `spark_answer_engine.py`. Wire TinyLM as the intent parser that queries the KB (extract keywords from question → search KB), not as a standalone answer generator.
3. **Connect UserProfileManager** — `SparkHelpWidget.__init__` should accept `user_profile_manager`; load active user on init and refresh on user-switch signal.
4. **Per-user history** — rename storage to `spark_qa_history_{username}.json`; load correct file on user switch.
5. **Skill level detection** — `_estimate_skill_level(user_profile, qa_history)` in `SparkAnswerEngine` → adjusts KB article verbosity returned.

### Known Gotchas

- `SPARK_PERFORMANCE_IMPROVEMENTS.md` in repo root references `affilabs/services/spark/` paths that do not exist (the actual files are in `affilabs/widgets/`) — that doc is stale, delete it
- `spark_help_widget.py` has `# from affilabs.services.spark import SparkAnswerEngine` commented out at line 20 — this is a leftover from a planned refactor; the actual import path is local/relative
- `sounddevice` / TTS dependency was planned but removed; keep it out of `pyproject.toml` and the main requirements
- TinyLlama auto-downloads to `~/.cache/huggingface/` on first AI use if not pre-bundled; consider bundling in installer to guarantee offline capability

---

*This document supersedes: `docs/user_guides/SPARK_DEVELOPER.md`, `docs/user_guides/SPARK_GUIDE.md`, `docs/future_plans/CLOUD_AI_PREMIUM_TIER.md`, and `SPARK_PERFORMANCE_IMPROVEMENTS.md` (root).*
