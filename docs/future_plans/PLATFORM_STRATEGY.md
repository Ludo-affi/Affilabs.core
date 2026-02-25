# Affilabs Platform Strategy

**Document Status:** 🟡 Living document — update as strategy evolves
**Last Updated:** February 25, 2026

---

## Instrument Family

| Old name | **New name** | Tier | Differentiator |
|----------|-------------|------|----------------|
| P4SPR | **SimplexSPR** | Entry | Manual syringe, 4-channel, lensless spectral SPR |
| P4PRO | **SimplexFlow** | Mid | AffiPump + 6-port valve, automated microfluidics, precise sample delivery |
| P4PROPLUS | **SimplexPro** | Top | Built-in pumps, full walk-away automation, integrated fluidics |

**Brand rationale:** "Simplex" encodes simplicity + multiplexing + the lensless (no extra optics) design philosophy. No existing SPR instrument uses this name (verified Feb 2026). File trademark before launch — see §13.

---

## 1. The Play

Affilabs sells SPR instruments. The instrument is the entry point, not the product. The product is the platform that wraps the instrument — software, data, coaching, consumables, services — built around a data flywheel that gets more valuable with every run a customer submits.

**Core loop:**
```
User runs experiment
  → Software scores the run (cycle quality, star rating)
  → Sparq Coach delivers debrief (Haiku, device-bound account)
  → Run data uploaded to Affilabs backend
  → Failure patterns detected → consumable/service upsell
  → CRM (Nutshell) captures lead, logs activity, assigns sales task
  → Better data → better Sparq → more reason to stay
```

Every layer increases switching cost. The instrument alone is replaceable. The instrument + 2 years of run history + compliance validation + published kinetics reports is not.

---

## 2. What We've Built (or Specced)

### 2.1 In-app quality layer (v2.0.5+)
- **Per-cycle quality score** (0–100) — baseline stability, injection detection, bubble events, wash detection, regen effectiveness. Live queue dot during acquisition.
- **Run star rating** (1–5) — signal quality roll-up (4★) + run completion (1★) + complexity tier badge (Easy / Medium / Pro).
- **Sparq Coach** — "Send to Sparq Coach" button in Edits. Structured run summary (Tier 1, anonymised) or full Excel (Tier 2, opt-in) sent to Haiku. Coaching debrief in Sparq sidebar. One concrete fix per issue. Product recommendation at end of debrief.
- **Sparq account** — device-bound (serial + email). In-app registration. API key issued at registration.

*FRS refs: [SIGNAL_EVENT_CLASSIFIER_FRS.md](../features/SIGNAL_EVENT_CLASSIFIER_FRS.md), [SPARQ_ACCOUNT_FRS.md](../features/SPARQ_ACCOUNT_FRS.md)*

### 2.2 CRM pipeline (server-side, Nutshell)
- Registration → Contact + Account created in Nutshell
- Every run upload → Activity logged (star rating, tier, failure summary)
- Failure pattern tags auto-applied (`issue-bubbles`, `issue-regen`, `struggling-user`, `pro-user`, etc.)
- High-priority tags → Tasks auto-created for sales team
- Product recommendation shown in-app → Lead created in Nutshell with full context

*FRS ref: [SPARQ_ACCOUNT_FRS.md](../features/SPARQ_ACCOUNT_FRS.md) §4–5*

### 2.3 Data flywheel
- Tier 1 uploads: anonymised run summaries → aggregate failure pattern intelligence
- Tier 2 uploads (opt-in): raw sensorgram data → labelled training data for Sparq model improvement
- Run data from real experiments = the most valuable SPR dataset in existence for training domain-specific models

---

## 3. Retention Layers

Ordered from weakest to strongest switching cost:

| Layer | What it is | Switching cost |
|---|---|---|
| **Good software** | Best-in-class instrument control, Edits tab, method builder | Low — a competitor can match features |
| **Coaching history** | Run-over-run improvement tracking in Sparq Coach | Medium — lose your coaching history if you leave |
| **Cloud graphing** | Cross-session analysis, collaboration, publication figures | Medium-high — rebuild your analysis environment |
| **Kinetics fitting reports** | Published papers citing Affilabs platform analysis | High — published data is linked to your software |
| **21 CFR Part 11 compliance** | Audit trail, e-signatures, FDA-submission-ready reports | Very high — re-validation costs $10k–$50k |
| **Chip lot QC tracking** | Lot-to-lot variation history, failure prediction | Very high — chip history only exists on our platform |

---

## 4. Revenue Streams

### 4.1 Hardware (existing)
- Instrument sales: SimplexSPR, SimplexFlow, SimplexPro
- Sensor chips, consumables

### 4.2 Consumables upsell (new — driven by Sparq Coach)
Failure patterns from run data trigger targeted recommendations. Products matched to observed issues:

| Observed failure | Product recommended | SKU |
|---|---|---|
| ≥ 2 bubble cycles | Running buffer degassing kit | `KIT-DEGAS-01` |
| Regen incomplete | Regeneration scouting kit (pH gradient + glycine panel) | `KIT-REGEN-SCOUT-01` |
| Low signal / poor immobilisation | Amine coupling optimisation kit | `KIT-AMINECOUPLING-01` |
| 10+ runs on same chip | Sensor chip bundle (×5) | `CHIP-BUNDLE-05` |
| First Pro-tier run | Advanced kinetics training (1hr online) | `SVC-TRAINING-KINETICS` |
| Pro user on SimplexSPR | SimplexFlow upgrade consultation | `SVC-UPGRADE-SIMPLEXFLOW` |
| Account age > 11 months | Service contract renewal | `SVC-CONTRACT-ANNUAL` |

### 4.3 Sparq subscription (planned)

| Tier | Price | Included |
|---|---|---|
| **Free** | $0 | Sparq Coach Tier 1, basic coaching debrief, 1 product recommendation per run |
| **Pro** | $X/mo per device | Tier 2 (Excel upload), multi-run coaching history, curve-aware advice, cloud graphing platform |
| **Lab** | $X/mo per institution | All Pro features, multi-device dashboard, team collaboration, priority support |

Recurring revenue on top of hardware margins. Instrument is sold once; subscription compounds.

### 4.4 Cloud platform services (planned)
- **Kinetics fitting as a service** — global fitting, heterogeneous binding models, mass transport correction, model selection (BIC/AIC), PDF report. Per-analysis fee or included in Pro.
- **Publication-ready figure export** — SVG, 300 DPI, journal-formatted. Included in Pro.
- **Shareable experiment links** — send a sensorgram to a collaborator or PI without exporting. Included in Pro.

### 4.5 Compliance tier (planned)
- 21 CFR Part 11 audit trail, electronic signatures, data integrity locks, FDA-submission-ready reports
- Premium tier — pharma and regulated biotech only
- Once a lab is validated on our platform, switching cost is a full re-validation exercise ($10k–$50k)

*Gap analysis: [21CFR_PART11_GAP_ANALYSIS.md](21CFR_PART11_GAP_ANALYSIS.md)*

---

## 5. Platform Extensions (Planned)

### 5.1 Cloud graphing platform
SPR data analysis today is Excel + manual cursor placement. The cloud platform replaces this:
- Upload any session (from any Affilabs instrument) — no local software required
- Overlay multiple runs: compare chip-to-chip, batch-to-batch, lab-to-lab
- Automated Kd fitting with confidence intervals
- Concentration series overlay with 1:1 Langmuir fit
- Shareable links for collaborators and PIs
- Publication-ready figure export

This is not a replacement for the local Edits tab — it is for cross-session analysis, collaboration, and publication. The local app is the instrument controller; the cloud platform is the analysis environment.

### 5.2 Advanced kinetics fitting (cloud)
Local fitting (already in app) is basic 1:1 Langmuir. Cloud offers:
- Global fitting across full concentration series
- Two-site / heterogeneous binding models
- Conformational change models
- Mass transport correction
- Automated model selection (BIC/AIC comparison)
- Downloadable PDF report with constants, confidence intervals, fit quality, residuals

### 5.3 Chip lot QC and batch tracking
Only possible because we have telemetry data. No competitor can offer this:
- Track baseline noise, FWHM, dip depth per chip lot number across all runs on that lot
- Flag lot-to-lot variation ("this chip lot has 15% higher background than your previous lot")
- Predict chip replacement before failure mid-experiment
- Lab-level chip inventory management

### 5.4 Experiment templates marketplace
Labs solve the same problems repeatedly (amine coupling, kinetics, epitope binning). Let power users publish method presets to a shared library:
- Affilabs curates and validates top templates
- New users download a "validated antibody-antigen kinetics protocol" and run it immediately
- Templates include expected signal ranges, recommended concentrations, regen conditions
- Network effect: more users → better templates → more reason to use Affilabs over a competitor

### 5.5 Lab notebook / ELN integration
Notes tab is already a lightweight ELN. Extend it:
- Export experiment entries to Benchling, Notion, or any ELN via API
- Auto-populate records with run metadata (date, chip lot, ligand, star rating, Kd)
- Makes Affilabs software the hub of the lab workflow, not just the instrument controller
- Reduces manual transcription errors — run data flows directly into the lab record

### 5.6 21 CFR Part 11 compliance tier
Pharma and regulated biotech must use compliant software. This is a premium add-on:
- Audit trail: who opened, modified, exported each record and when
- Electronic signatures on experiment records and reports
- Data integrity locks (records cannot be modified post-signature)
- FDA-submission-ready PDF reports
- IQ/OQ/PQ validation package

Once a lab is compliant on our platform, switching requires a full re-validation exercise. This is the highest switching cost available.

*Implementation plan: [IQOQ_PLAN.md](IQOQ_PLAN.md), [21CFR_PART11_GAP_ANALYSIS.md](21CFR_PART11_GAP_ANALYSIS.md)*

---

## 6. Data Strategy

### 6.1 What we collect

| Data source | Tier | Value |
|---|---|---|
| Run summary (scores, cycle notes, failure patterns) | Tier 1 — anonymised, default | Aggregate failure intelligence, upsell targeting |
| Full Excel export (sensorgrams, delta-SPR, concentration series) | Tier 2 — opt-in | Labelled SPR training data for model improvement |
| Chip lot + run count correlation | Derived from Tier 1 | Chip QC / batch tracking product |
| Coaching interaction (what advice was given, was product clicked) | Logged locally + Nutshell | Upsell conversion tracking |

### 6.2 The flywheel

```
More users submit runs
  → More labelled SPR data (Tier 2)
    → Better Sparq coaching models
      → More accurate advice
        → More trust in platform
          → More users submit runs
```

This is a moat. A competitor starting today has no labelled real-world SPR data. We accumulate it with every run.

### 6.3 Privacy boundary

- Tier 1 is always anonymised — fresh UUID per send, no device serial, no PII, no ligand names
- Tier 2 is explicit opt-in per send — user sees exactly what is included before confirming
- Users can withdraw consent and delete all server-side data at any time
- Nutshell CRM data covered by registration privacy policy

---

## 7. Competitive Positioning

| What Affilabs offers | What Biacore / competitors offer |
|---|---|
| Open instrument platform (Ocean Optics detector, standard serial) | Proprietary locked hardware |
| Cloud coaching tied to real run data | No post-run intelligence |
| Targeted consumable recommendations from failure patterns | Generic sales outreach |
| Cross-run analysis and publication tools | Export to Excel, analyse yourself |
| Community templates marketplace | No sharing |
| 21 CFR Part 11 tier (planned) | Available but expensive and rigid |

The instrument competes on price and openness. The platform competes on intelligence and stickiness. Over time, the platform is worth more than the instrument.

---

## 8. Academic Market Focus (Launch Priority)

### 8.1 Why academia first

- Existing installed base is primarily academic labs and core facilities
- Fastest path to revenue: convert existing customers, not new ones
- Academic word-of-mouth is powerful — one core facility manager influences 20+ PIs
- No 21 CFR Part 11 requirements → lower compliance burden, faster iteration
- Grant budgets are real money — a PI with an active NIH/NSERC/ERC grant will spend on tools that make experiments work

### 8.2 What academics will pay for

| Revenue stream | Academic fit | Notes |
|---|---|---|
| Perpetual Pro license | ✅ Best | One PO, capitalised as equipment. No recurring admin friction. |
| Annual maintenance (optional) | ✅ Good | 20–30% of perpetual price. Covers Sparq Coach access, updates, support. Opt-in renewal. |
| Pay-per-analysis (kinetics reports) | ✅ Good | No commitment. Grant-expensable as a service. $X per PDF report. |
| Consumables (chips, kits) | ✅ Good | Triggered by Sparq Coach failure patterns. Impulse-buyable on a grant. |
| Monthly SaaS | ❌ Bad | Procurement friction, grant cycle mismatch, feels like a trap. Avoid. |
| Core facility tier | ✅ High volume | One facility = 10–30 PIs sharing one instrument. Per-instrument-year pricing. |

### 8.3 Academic pricing model

```
Base software (free, bundled with instrument)
─────────────────────────────────────────────
  Live acquisition + sensorgram display
  Edits tab — full local analysis, Kd fitting, delta-SPR
  Local Sparq Q&A (knowledge base, tips, hardware guidance)
  Basic cycle quality dot (score shown, no breakdown)
  Notes tab — visible but locked (grayed out, upgrade prompt on click)
  Sparq Coach button — visible but locked (upgrade prompt on click)

Sparq Pro (perpetual license, one-time purchase)
─────────────────────────────────────────────────
  Notes tab — full ELN, experiment log, Kanban, tags, star ratings
  Sparq Coach — "Send to Sparq Coach" + full coaching debrief
  Cycle score breakdown (component detail, auto-notes)
  Run star rating detail + complexity tier
  Cloud graphing + cross-run analysis
  Annual maintenance option (optional renewal for updates + new features)

Pay-per-use (no license required)
──────────────────────────────────
  Kinetics fitting report (PDF) — $X per analysis
  Publication figure export — $X per figure set
```

**Pricing anchor:** Sparq Pro perpetual = 10–15% of instrument purchase price. At an instrument price of $X, the Pro license is an easy yes on the same grant. It feels like a software add-on to capital equipment, not a subscription.

**Annual maintenance** is optional, not mandatory. Labs that don't renew keep their Pro features — they just stop receiving new Sparq features and updates. This removes the "hostage" feeling academics hate while still generating recurring revenue from labs that value staying current.

### 8.4 Fastest path to revenue at launch

1. **Convert existing customers first** — every device in the field is a Pro license opportunity. Email list from `device_registry.json`. Offer a launch discount for first 90 days.
2. **Bundle Pro with new instrument purchases** — include Pro license in the instrument price or offer it as a low-friction add-on at checkout. First-run experience is better, reduces support burden.
3. **Core facilities as high-value targets** — one conversion = many users. Offer a "Core Facility" tier with multi-user Notes tab and per-run reporting for facility managers.
4. **Pay-per-analysis for non-Pro users** — gives free users a path to spend without a license commitment. Kinetics report at $X is reachable on any grant.

---

## 9. Freemium Feature Gate

The free version is genuinely useful — a researcher can run a full experiment, analyse the data, and export results without paying. The gate is designed to frustrate power users (those getting the most value) rather than new users (who need to learn the software first).

### 9.1 Feature gate table

| Feature | Free | Pro |
|---|---|---|
| Live acquisition + sensorgram | ✅ | ✅ |
| Edits tab — full analysis | ✅ | ✅ |
| Edits tab — Kd fitting (local) | ✅ | ✅ |
| Edits tab — delta-SPR, alignment | ✅ | ✅ |
| Excel export | ✅ | ✅ |
| Local Sparq Q&A (knowledge base) | ✅ | ✅ |
| Basic cycle quality dot | ✅ | ✅ |
| Cycle score breakdown + auto-notes | ❌ locked | ✅ |
| Run star rating detail | ❌ locked | ✅ |
| Notes tab (ELN, experiment log) | 👁 visible, locked | ✅ |
| Sparq Coach (cloud debrief) | 👁 visible, locked | ✅ |
| Cloud graphing / cross-run analysis | ❌ | ✅ |
| Kinetics fitting PDF report | ❌ pay-per-use | ✅ included |
| Annual maintenance / updates | ❌ | ✅ optional |

**Design rule:** Locked features are **visible** in the UI — grayed out with a small lock icon and "Upgrade to Pro" tooltip on hover. This creates desire without blocking core workflows. The user sees what they're missing every session; they don't discover Pro exists from a marketing email.

### 9.2 Upgrade prompt tone

Never aggressive. No popups. No countdown timers. The lock icon is the only signal.

On click of a locked feature:

```
┌────────────────────────────────────────────────────┐
│  Notes tab is a Sparq Pro feature                  │
│                                                    │
│  Keep a full experiment log, track your runs,      │
│  rate experiments, and plan your next session —    │
│  all in one place.                                 │
│                                                    │
│  [Learn more]        [Upgrade to Pro →]            │
└────────────────────────────────────────────────────┘
```

"Learn more" opens `affilabs.com/sparq-pro`. "Upgrade to Pro" opens the Sparq account registration / purchase flow.

---

## 10. Licensing Model

### 10.1 Approach: device-serial-bound license file

The simplest robust enforcement for a small installed base. The device serial is already the identity of every unit — tie the Pro license to it.

- At Pro purchase, the backend generates a signed `.lic` file for the device serial
- Delivered automatically via Sparq account registration flow, or emailed as a file attachment
- User places it in `config/sparq_pro.lic` (or the app handles it automatically post-purchase)
- App validates the signature locally on startup — **no internet required after activation**
- If the file is copied to a different device, the serial mismatch fails validation silently — Pro features stay locked, no error message to the user (avoids antagonising honest users who accidentally tried)

### 10.2 License file schema

```json
{
  "device_serial": "FLMT09788",
  "license_tier": "pro",
  "issued_at": "2026-02-25",
  "maintenance_expires": "2027-02-25",
  "signature": "<HMAC-SHA256 of serial+tier+issued_at, signed with Affilabs private key>"
}
```

`maintenance_expires` controls whether the user receives new features and updates — not whether existing Pro features work. After expiry, Pro features continue to work; new features added after expiry require maintenance renewal to unlock.

### 10.3 Validation logic (client-side)

```python
def validate_license(serial: str, lic_path: Path) -> LicenseState:
    if not lic_path.exists():
        return LicenseState.FREE
    data = json.loads(lic_path.read_text())
    if data["device_serial"] != serial:
        return LicenseState.FREE          # silent mismatch — no error shown
    if not verify_signature(data, AFFILABS_PUBLIC_KEY):
        return LicenseState.FREE          # tampered file — silent
    maintenance_active = date.fromisoformat(data["maintenance_expires"]) >= date.today()
    return LicenseState.PRO_MAINTENANCE if maintenance_active else LicenseState.PRO
```

Three states:
- `FREE` — no license or invalid
- `PRO` — valid license, maintenance expired (all Pro features work, no new updates)
- `PRO_MAINTENANCE` — valid license, maintenance active (all Pro features + latest updates)

### 10.4 Why this works for academia

- **Works offline** — no phone-home, no annual activation. A lab in a basement with no internet still gets full Pro features.
- **One PO, done** — no recurring billing to manage. The `.lic` file is the receipt.
- **Not trivially bypassable** — HMAC signature with a private key means the file cannot be forged without Affilabs' private key. Good enough for academic honesty norms.
- **Not draconian** — if a serial mismatch happens (detector replaced), the user contacts Affilabs, gets a new `.lic` for the new serial. No punitive behaviour.
- **Low admin overhead** — for a small installed base, license generation can be done manually. As volume grows, the Sparq account backend automates delivery.

### 10.5 Device replacement policy

If a detector is replaced (warranty swap, upgrade):
- User contacts Affilabs with old serial + new serial + proof of purchase
- Backend generates new `.lic` for new serial
- Old `.lic` is invalidated server-side (flagged in `device_registry.json`)
- No charge for replacement — the license follows the customer, not the hardware unit

---

## 11. Implementation Priority (Revised)

| Initiative | Effort | Revenue impact | Retention impact | Priority |
|---|---|---|---|---|
| License file validation + feature gate | Low | High (enables all paid tiers) | Medium | **1st** |
| Sparq account registration + CRM pipeline | Medium (backend) | High (upsell leads) | High | **1st** |
| Sparq Coach Tier 1 + consumables catalogue | Low | High | Medium | **1st** |
| Pro license purchase flow (website + delivery) | Low | High (direct revenue) | Low | **1st** |
| Convert existing installed base (launch email) | Zero dev | High (immediate) | Low | **1st** |
| Pay-per-analysis kinetics report | Medium | Medium | Medium | **2nd** |
| Core facility tier | Low (pricing + Notes tab) | High (volume) | High | **2nd** |
| Cloud graphing platform | High (new product) | High | Very high | **3rd** |
| Annual maintenance renewal flow | Low | Medium (recurring) | Low | **3rd** |
| Templates marketplace | Medium | Low direct | High | **4th** |
| ELN integration | Medium | Low | High | **4th** |
| Chip lot QC tracking | Low (telemetry-derived) | Medium (chip sales) | High | **4th** |
| 21 CFR Part 11 compliance | Very high | Very high (pharma) | Highest | **Long term** |

---

## 12. Competitive Defence

### 12.1 What you can't protect

- The general idea of "SPR software with AI coaching" — not patentable
- UI layouts, feature lists, workflow steps — copyable in 6 months by a funded competitor
- The LLM integration pattern — anyone can call an API

### 12.2 Real moats (ordered by strength)

| Moat | Why it holds |
|---|---|
| **Data moat** | The labelled SPR dataset from Tier 2 uploads is not reproducible. A competitor starting today has no real-world run data. By the time they have enough users, you have 2–3 years of head start and a model that actually works. |
| **Coaching history** | A lab's run history, failure patterns, and improvement trajectory lives in your platform. Switching means starting over. The longer they use Sparq Coach, the more it knows about their specific setup. |
| **Network effects** | Templates marketplace and community knowledge compound with users. More users → better templates → more reason to use Affilabs over a competitor. |
| **Nutshell CRM relationships** | You know every customer, their usage patterns, failure history, and grant cycle. A competitor is cold-calling. Your sales team can be proactive by design. |
| **Incumbency + distribution** | You're already in the labs. The software ships with the instrument. A competitor has to convince labs to install a second piece of software on a machine already running yours. |
| **Copyright** | Automatic on all code. Direct copying is legally actionable. Raises the cost of clean-room reimplementation. |
| **Trade secrets** | Coaching logic, upsell thresholds, Haiku system prompts, scoring weights — all server-side. The client is inspectable; the backend is not. |
| **Trademark** | Register **Sparq** and **Affilabs** immediately if not done. A competitor can copy the concept but cannot call it Sparq. Brand recognition in a small academic niche is durable. |
| **21 CFR Part 11 (long term)** | Once a pharma lab is validated on your platform, switching costs $10k–$50k in re-validation. The highest lock-in available. |

### 12.3 Threat assessment

**Well-funded incumbent (Cytiva / Biacore):**
- Can build the same features in 12–18 months
- Cannot copy your data, customer relationships, or pricing agility
- Their software is notoriously bad and locked to their hardware — "open platform that works with any detector" is a structural differentiator they cannot match without abandoning their hardware business model

**Startup copycat:**
- Can clone UI and workflow in 6 months
- Has no installed base, no data, no customer relationships, no hardware to bundle with
- Would be selling software to labs that already own your instrument — you have incumbent advantage and a head start on coaching history

**The honest answer:** No software workflow is truly defensible long-term. The defence is speed + data + relationships. A copycat who launches 18 months after you, into a market where your customers already have 18 months of coaching history and a Pro license, is not a serious threat to existing customers — only to new ones.

### 12.4 What to do now (time-sensitive)

1. **File SimplexSPR + Sparq + Affilabs trademarks** — costs ~$500–1000 per mark, filing date is what matters legally. Do this before launch. SimplexSPR confirmed clear in the SPR/biosensor field (Feb 2026).
2. **Get Tier 2 opt-in moving as fast as possible** — data accumulation is the primary moat. Every run uploaded is a point of lead.
3. **Lock in existing customers with the launch discount** — a customer with a Pro license and 6 months of coaching history is not going to switch for a copycat with no history.
4. **Move fast on the backend** — the app-side work is straightforward. The backend (API, Haiku, Nutshell, `.lic` delivery, Stripe) is the critical path. Options if no dedicated backend developer available:
   - **n8n** (self-hosted workflow automation) + **Supabase** (Postgres + edge functions) — low-code, fast to deploy, handles webhooks, Stripe, Nutshell API calls, `.lic` generation
   - **Zapier / Make** for Nutshell CRM writes — no-code, operational in hours
   - Haiku API call can be a simple Python Flask endpoint on a $5 VPS — doesn't need to be complex for v1

---

## 13. Launch Sprint Plan

Speed is the primary weapon. First-mover advantage + installed base + clear roadmap = a window that closes the moment a competitor notices what you're building.

### 13.1 What must exist on launch day

| Must-have | Why it can't wait |
|---|---|
| License validation + feature gate (client-side) | Everything else is free without it |
| Pro purchase flow (website, Stripe, `.lic` delivery) | Can't make money without it |
| Sparq account registration (in-app dialog) | Seeds CRM pipeline from day one |
| Sparq Coach Tier 1 (send button → Haiku → Sparq sidebar) | The headline feature — what gets demoed and talked about |
| Launch email to existing installed base | First 90-day discount window — converts warm leads before they hear about a competitor |

Everything else ships post-launch.

### 13.5 Sparq Coach Waitlist — Pre-launch demand capture

**Status:** UI placeholder live (✦ Sparq Coach button in Edits tab, dashed border, opens waitlist URL)
**Backend:** Not yet built — implement after core launch sprint is complete.

**What to build (self-hosted, no Zapier):**

```
Wix form submit (name, email, institution, instrument model)
  → Wix Automation: "When form submitted → Send webhook" (built-in, free)
  → POST → Flask endpoint on $5 VPS  (scripts/backend/sparq_waitlist_webhook.py)
  → Nutshell API: newContact + tag "sparq-waitlist" + note with instrument model
```

**Wix form fields:**
- Name
- Email
- Institution / lab name
- Instrument model (dropdown: SimplexSPR / SimplexFlow / SimplexPro / Other)

**Nutshell outcome:** every signup appears as a Contact tagged `sparq-waitlist`, segmented by instrument tier — ready for targeted early-access outreach.

**TODO before going live:**
1. Create Wix waitlist landing page
2. Set up Wix Automation → webhook on form submit
3. Deploy `scripts/backend/sparq_waitlist_webhook.py` (placeholder file — see below)
4. Replace `_SPARQ_WAITLIST_URL` in `affilabs/tabs/edits/_ui_builders.py` with live Wix URL
5. Test end-to-end: submit → Nutshell contact created with `sparq-waitlist` tag

**Placeholder backend:** `scripts/backend/sparq_waitlist_webhook.py` — stub file with TODO comments, ready to implement.

### 13.2 What can wait (post-launch v2.1)

- Cycle score breakdown detail + run star rating UI
- "Repeat cycle" button
- Tier 2 Excel upload
- Notes tab (visible + locked is enough for launch — full unlock post-launch)
- Annual maintenance renewal flow
- Pay-per-analysis kinetics report

### 13.3 Sprint sequence (6–7 weeks to launch)

```
Week 1–2   Client-side license validation (LicenseState enum, .lic file reader, HMAC verify)
           Feature gate UI — lock icons, grayed tabs, upgrade prompt dialogs
           Sparq Coach send button + confirmation dialog (UI complete, backend stub)
           Sparq account registration dialog (UI complete, backend stub)

Week 3–4   Backend: POST /sparq/register → Nutshell contact/account creation + API key issue
           Backend: POST /sparq/coach/v1 → Haiku call → coaching response + Nutshell activity log
           .lic file generation on purchase → email delivery

Week 5–6   Stripe payment integration → purchase → .lic delivery → in-app activation
           Sparq account settings panel (connected state, disconnect, privacy link)
           End-to-end test: register → purchase → activate → send run → receive debrief

Week 7     Trademark filing (Sparq + Affilabs)
           Launch email to installed base (device_registry.json email list)
           Launch discount code active (90-day window)
           Software v2.0.5 release with feature gate live
```

### 13.4 Critical path item: the backend

The app-side work (Qt dialogs, license validation, send button) is all standard Python/Qt — low risk, fast to build. The backend is the single biggest variable.

**If no dedicated backend developer:**

| Tool | Use | Time to operational |
|---|---|---|
| **n8n** (self-hosted) | Webhook handler, Nutshell API writes, `.lic` generation, email delivery | 1–2 days |
| **Supabase edge functions** | `/sparq/register` and `/sparq/coach/v1` endpoints, Postgres for account storage | 2–3 days |
| **Stripe** | Payment processing, webhook → `.lic` delivery trigger | 1 day |
| **Simple Flask app on VPS** | Haiku API proxy (receives run summary, calls Anthropic, returns coaching text) | 1 day |

Total backend: **5–7 days** with no prior setup, using low-code tools. Not a blocker if started in Week 3.

---

## 14. SimplexSPR Market Positioning — Active Concentration Assay

### 14.1 The angle

> **"The SPR instrument that tells you how much active protein you actually have — before you waste it on kinetics."**

This repositions SimplexSPR not as a cheaper Biacore but as a **protein QC instrument**. Every lab producing recombinant protein needs active concentration data. Current options are ELISA (slow, indirect) or BCA/A280 (measures total protein, not active fraction). SPR active concentration is faster and direct — but only accessible if you have an SPR instrument.

SimplexSPR makes active concentration assay routine and affordable for labs that can't justify a Biacore.

### 14.2 Why SimplexSPR is structurally well-suited

| Factor | Advantage |
|--------|-----------|
| 4 independent fluidic channels | Channel D = permanent reference surface. Every run has a built-in calibration channel if the user wants one. No reconfiguration needed. |
| Lensless spectral — no moving parts | Concentration assay needs a stable baseline. No mechanical angular scanning = less drift = tighter calibration curves. |
| Open detector (Ocean Optics) | Raw spectral data accessible. Custom calibration models possible — not locked to a vendor assay module. |
| Manual syringe (P4SPR) | Lower dead volume than automated systems. Better for small-volume samples where exact injected amount matters. |
| Price point | Labs that cannot afford a Biacore can now run active concentration assays. This is a new market, not a Biacore replacement market. |

### 14.3 Who buys on this angle

- **Protein production labs** — CROs, academic expression labs, core facilities. Need to know if their protein folds correctly before sending to kinetics.
- **Small biotech** — no Biacore budget; need fast active concentration QC on lead candidates.
- **Labs that already have a Biacore** — use SimplexSPR as the pre-screen instrument upstream of the expensive Biacore runs. Saves Biacore chip consumption and instrument time.
- **Core facilities** — one SimplexSPR as a shared QC station used by 10–20 PIs across the department.

### 14.4 Honest positioning boundary

Spectral SPR has broader dips (~20–40 nm FWHM) than angular SPR. Absolute concentration precision is lower than a Biacore calibration module. The pitch is **fast routine QC screening**, not "replace your Biacore calibration module."

- ✅ "Is my protein active? What fraction is functional?" — SimplexSPR answers this in 15 minutes
- ✅ "Screen 8 batches for active concentration before sending the best to kinetics" — ideal use case
- ❌ "Absolute concentration to 3 significant figures for regulatory submission" — use Biacore

This is an honest market position and it's a real gap. Biacore users frequently skip active concentration because it requires a second surface and extra chip real estate. SimplexSPR users can dedicate a channel to it permanently.

### 14.5 What the software needs (mostly already there)

| Feature | Status |
|---------|--------|
| Dedicated "Concentration Assay" method preset | Not yet — add to method presets library |
| Reference surface setup guide (in-app) | Guidance coordinator — Phase B |
| Calibration curve builder in Edits (concentration vs ΔSPR) | Binding plot already plots conc series — extend with linear fit + unknown readout |
| Active concentration readout from unknown injection | New — one value output from the calibration curve fit |
| Sparq Coach prompts for concentration assay troubleshooting | Haiku system prompt extension — add assay-specific failure patterns |

---

## 15. Comparable Companies

These companies run the same fundamental playbook: hardware as the entry point, software/data/services as the margin.

| Company | What they do | What Affilabs borrows |
|---|---|---|
| **Illumina** | DNA sequencers at accessible price points; consumables (reagents, flow cells) are the real business. Instrument margins are thin; reagent margins are 70%+. | Razor/blade model — SimplexSPR is the razor, chips + kits are the blades. Sparq Coach drives consumable reorders by name. |
| **Nikon / Zeiss (microscopy)** | Sell the instrument once; perpetual software licenses for analysis modules (NIS-Elements, ZEN) add 20–40% to instrument revenue. Device-serial-bound, works offline. | Perpetual Pro license tied to device serial. One PO. Academic-friendly. No monthly SaaS friction. |
| **Strava** | Free GPS running app; Premium unlocks training analysis, coaching plans, route leaderboards. The free tier builds habit and social graph; Premium converts power users. Data from users improves AI coaching. | Free tier is genuinely useful (live acquisition, Edits, local Sparq Q&A). Pro converts power users. Coaching history accumulates — leaving means losing your training data. |
| **Benchling** | Free for academics (ELN, registry, sequence editor); enterprise tier for pharma/biotech. Academic use drives word-of-mouth and trains the next generation of industry scientists who bring Benchling with them. | Notes tab + Sparq Coach free for academics → when lab members move to industry, they know the platform. Academic install base is the sales pipeline for future pharma upsell. |
| **Roper Technologies / IDEX** | Acquires niche scientific instrument companies (fluid handling, imaging, spectroscopy). Instruments serve captive markets with high switching costs; recurring revenue from service contracts and consumables. | The Affilabs endgame: build platform stickiness until the installed base + data moat makes it an acquisition target for a strategic buyer in the life science tools space. |
| **Peloton** | Hardware (bike) at accessible price; monthly coaching subscription is the recurring revenue. Coaching content + leaderboards create social switching cost. | SimplexSPR at accessible price + Sparq Coach subscription. The instrument gets you in the door; coaching keeps you. The lab that has 2 years of run history and improvement tracking is not switching to a competitor. |

**The common thread:** none of these companies primarily sell what they appear to sell. Illumina sells reagents. Nikon sells software modules. Strava sells coaching data. Benchling sells pharma contracts. Affilabs sells a platform that happens to start with an instrument.
