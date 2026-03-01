# Website — Software Page Plan
**Platform:** Wix
**Created:** Mar 1 2026
**Status:** Planning

---

## Strategy

### Download model — Phase 1 (now, v2.0.5)
- **Gated download** — "Request Access" form, not a public download link
- Form captures: name, institution, instrument serial number, email
- Affinite manually sends installer + IQ/OQ protocol doc by email
- No license key required (enforcement disabled in code — see `affilabs/services/license_service.py:112`)
- Wix → Power Automate → SharePoint intake already plumbed (`SHAREPOINT_WIX_INTEGRATION_GUIDE.md`)

### IQ/OQ documents — on request only
- `IQ_OQ_PROTOCOL_v2.0.5.html` is the customer-facing document (safe to share)
- `IQ_OQ_PLAN_v2.0.5.html` is internal only — do not post or attach to emails
- Response: attach PDF export of the protocol when a customer asks

### Download model — Phase 2 (v2.1, post-stabilisation)
- Sparq account / device registration gates the download (see `SPARQ_ACCOUNT_FRS.md`)
- License enforcement enabled — flip 4-line bypass in `license_service._load()`, generate real HMAC secret
- Self-service key delivery via Sparq account portal

---

## Newsletter source (Feb 2026)
URL: https://growth.affiniteinstruments.com/n/ed/321327/IfoTcO
Edition: "Feb Newsletter_changes 02262026" (247-emEditions in Nutshell)

Key lines to reuse verbatim or near-verbatim:
- **Hero:** *"Your instrument. Fully unleashed."*
- **Positioning:** *"The software your P4SPR was always waiting for — built for scientists who can't afford to waste a run."*
- **Workflow promise:** *"Load sample → acquire organized data → see clean results right after your run."*
- **Stats:** 16 interactions / 20 reagents / 1 day · 500× MW range (1 kDa–500 kDa) · 2 days saved per experiment
- **Sparq:** *"Meet SPARQ"* — coming soon framing, *"Accelerated biosensor development"*
- **Upgrade hook:** *"P4SPR Gen 2 — 10× SNR improvement, full Affilabs.core included"*
- **CTA labels used:** "Explore P4SPR 2.0 →" · "Meet SPARQ Coach →" · "Stay in the loop →"

---

## Page Structure (Wix)

### Hero
**Headline:** `Your instrument. Fully unleashed.`
**Subheadline:** `Affilabs.core — the SPR software your P4SPR was always waiting for.`
**Sub-sub:** `Built for scientists who can't afford to waste a run.`
**CTA button:** `Request Access →` (links to form)
**Secondary link:** `Still on ezControl? See the upgrade →` (anchors to legacy callout)

---

### Workflow promise block (3 steps)
Visual: 3-column icon strip
1. **Load sample** — set up your run in minutes with guided method templates
2. **Acquire organised data** — real-time signal quality tells you when your signal is ready
3. **See clean results right after your run** — binding curves, kinetics, and export without leaving the software

---

### Stats bar (from newsletter)
- **16 interactions** screened across 20 reagents in one day
- **500× molecular weight range** — 1 kDa to 500 kDa
- **2 days saved** per experiment

---

### Feature sections

#### "Know before you inject" — Signal monitoring
*Headline copy:* "Always-On Signal Monitoring"
- Detects bubbles, leaks, or drift before wasted runs occur
- Per-channel quality score — green means go
- Contact Monitor tracks binding time, wash detection, and ΔSPR live

#### "From acquisition to insight" — Analysis
*Headline copy:* "From Run to Results — all in one session"
- Binding curves and kinetics (ka / kd / KD) calculated automatically
- Edits tab: cycle alignment, reference subtraction, concentration series
- Excel export with sensorgram, cycle table, and kinetics — one click

#### "Your experiment history" — Data management
- Searchable experiment log with star ratings and tags
- Built-in ELN (Notes tab) — link observations to runs
- Selective export — choose exactly which cycles go into the report

#### "Calibration & Traceability"
- Self-verifies optical alignment and LED health on every startup
- Traceable calibration logs — IQ/OQ documentation available on request

#### Meet SPARQ *(coming soon framing)*
*Headline copy:* "Meet SPARQ — your built-in SPR assistant"
- Guides you through setup, troubleshooting, and method optimisation
- Works offline — no data leaves your instrument
- SPARQ Coach: accelerated biosensor development (coming in v2.1)

---

### Legacy callout block
> **Still on ezControl (v1.x)?**
> Affilabs.core 2.0 is a full upgrade — new interface, real-time signal quality, built-in AI assistant, and structured data export. Available now for existing P4SPR customers.
> [Request upgrade →]

---

### "Coming Next" section (from newsletter)
*Headline copy:* "Coming Next — A New Era"
- **SimplexFlow (P4PRO)** — automated injection, AffiPump support — coming soon
- **P4SPR Gen 2** — 10× SNR improvement, full Affilabs.core included from day one
- CTA: "Stay in the loop →" (email capture or LinkedIn follow)

---

### Compatibility table

| Model | Status | Notes |
|-------|--------|-------|
| SimplexSPR (P4SPR) | ✅ Available now | Request access below |
| SimplexFlow (P4PRO) | Coming soon | Automated injection support |
| SimplexPro (P4PROPLUS) | Coming soon | — |
| ezControl (legacy v1.x) | Legacy | No new features — upgrade available |

---

### Request Access form
Fields:
- Full name (required)
- Institution / company (required)
- Instrument serial number (required — format FLMT##### or P4SPR-#####)
- Email (required)
- How are you currently using your instrument? (optional, free text)

On submit → Power Automate → SharePoint intake folder (existing flow)
Response email sent manually by Affinite within 1–2 business days, includes:
- Installer download link (time-limited or password-protected)
- `IQ_OQ_PROTOCOL_v2.0.5.html` as PDF attachment
- Installation guide link

---

### Footer note
`Affilabs.core is currently available to existing SimplexSPR customers.`
`General availability planned for Q3 2026.`

---

## Content tone notes
- Talk about what the **scientist** experiences, not software architecture
- "Know your signal is ready before you inject" — not "SensorIQ 5-level scoring"
- "Your experiment history, searchable" — not "Experiment Index with schema v2"
- Keep legacy framing neutral — don't disparage old software, just call it legacy and offer upgrade
- Sparq = "your built-in SPR assistant" — not "AI" or "LLM"

---

### Release Notes page (separate Wix page)
Linked from footer: "Release Notes" or "What's New"
- One section per version: version number, date, 3–5 bullet points (user-facing language, not dev jargon)
- Source: `CHANGELOG.md` in the repo — copy and translate before publishing
- Bugs fixed go here too: "Fixed: software could freeze after calibration on some systems"
- Keep legacy ezControl notes at the bottom under a "Legacy Software" heading

**Internal source of truth:** `CHANGELOG.md` (already maintained)
**Customer-facing translation:** this Wix page (manually updated per release)

---

## Open items
- [ ] Screenshot or screen recording of Affilabs.core UI for hero section
- [ ] Decide on installer delivery method (email attachment vs time-limited OneDrive link)
- [ ] PDF export of `IQ_OQ_PROTOCOL_v2.0.5.html` for email attachment
- [ ] SimplexFlow compatibility target date for website
- [ ] Legacy software URL to link to
- [ ] Add "Latest version: v2.0.5 — released Feb 24 2026" banner to download page
- [ ] Build Release Notes Wix page from CHANGELOG.md v2.0.5 entry (user-facing translation)
