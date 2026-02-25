# Sparq Account — FRS

**Document Status:** 🔵 Design (not yet implemented)
**Last Updated:** February 25, 2026
**Planned source files:**
- `affilabs/services/sparq_account_service.py` — registration, API key storage, account state
- `affilabs/dialogs/sparq_registration_dialog.py` — in-app one-time setup dialog
- `affilabs/services/sparq_coach_service.py` — run summary upload, Tier 1/2 payload, response handling (see also SIGNAL_EVENT_CLASSIFIER_FRS.md §9)

**Backend (server-side — not in this repo):**
- `POST /sparq/register` — device registration, Nutshell contact creation
- `POST /sparq/coach/v1` — run upload, Haiku coaching, Nutshell activity log, upsell trigger

---

## 1. Purpose

The Sparq account ties a physical instrument to a cloud identity. It is the entry point for:

1. **Sparq Coach** — LLM-powered post-run debrief (see SIGNAL_EVENT_CLASSIFIER_FRS.md §9)
2. **CRM** — every registered device becomes a qualified contact in Nutshell with known usage patterns
3. **Upsell pipeline** — failure patterns detected in run data trigger targeted product recommendations and sales tasks
4. **Platform retention** — coaching history accumulates on the device; switching instruments means starting over

The account is **device-bound**, not user-bound. One lab instrument = one Sparq account. Everyone in the lab shares the coaching history on that device.

---

## 2. Account Identity Model

| Field | Source | Notes |
|---|---|---|
| `device_serial` | Hardware — read at connect time | Primary key. e.g. `FLMT09788`. Never changes. |
| `instrument_model` | `ctrl_type` from hardware manager | `P4SPR` / `P4PRO` / `P4PROPLUS` |
| `owner_email` | User-entered at registration | Used for account recovery and coaching summary emails |
| `institution` | User-entered at registration (optional) | Lab name, university, company |
| `api_key` | Issued by backend at registration | Stored in `config/sparq_account.json`. Never sent to Haiku. |
| `registered_at` | Server timestamp | |
| `sparq_account_id` | UUID issued by backend | Internal — not shown to user |

No username. No password. The device serial + API key is the auth pair for all subsequent API calls. The email is for account management only.

---

## 3. Registration Flow

### 3.1 Trigger

First time the user clicks **"Send to Sparq Coach"** in the Edits tab and no `config/sparq_account.json` exists (or it exists but has no valid `api_key`).

Also accessible via **Settings → Sparq → "Connect Sparq account"**.

### 3.2 In-app registration dialog

```
┌──────────────────────────────────────────────────────────┐
│  Connect your instrument to Sparq                        │
│                                                          │
│  Get AI-powered coaching after every run, product        │
│  recommendations based on your data, and access to       │
│  the Sparq knowledge base.                               │
│                                                          │
│  Device:  FLMT09788  (P4SPR)           ← auto-detected  │
│                                                          │
│  Email:   [_______________________________]              │
│  Lab:     [_______________________________]  (optional)  │
│                                                          │
│  By connecting, you agree to the Affilabs Privacy        │
│  Policy. Your run summaries are used to generate         │
│  coaching advice and improve Sparq.                      │
│  affilabs.com/privacy                                    │
│                                                          │
│        [Cancel]          [Connect →]                     │
└──────────────────────────────────────────────────────────┘
```

### 3.3 Registration sequence

```
App                          Backend                    Nutshell
 │                               │                          │
 ├─ POST /sparq/register ────────►│                          │
 │  { device_serial,             │                          │
 │    instrument_model,          │                          │
 │    owner_email,               │                          │
 │    institution,               │                          │
 │    app_version }              │                          │
 │                               ├─ create/update Contact ──►│
 │                               │  create Account          │
 │                               │  log Activity:           │
 │                               │  "Sparq registered"      │
 │                               │                          │
 │◄─ { api_key, account_id } ────┤                          │
 │                               │                          │
 ├─ write config/sparq_account.json                         │
 ├─ show success in dialog                                  │
 └─ proceed to Sparq Coach send                             │
```

`config/sparq_account.json` schema:

```json
{
  "device_serial": "FLMT09788",
  "instrument_model": "P4SPR",
  "sparq_account_id": "<uuid>",
  "api_key": "<key>",
  "owner_email": "user@lab.com",
  "institution": "McGill University",
  "registered_at": "2026-02-25T14:32:00Z"
}
```

If the device serial changes (detector replaced), the old account is orphaned. User must re-register. The backend links the new serial to the same email, preserving coaching history.

---

## 4. Nutshell CRM Integration

All Nutshell writes happen **server-side only** — the Nutshell API key never leaves the backend. The app has no direct Nutshell access.

### 4.1 Objects created at registration

| Nutshell object | Fields populated |
|---|---|
| **Contact** | Name (from email prefix or institution), email, tag: `sparq-user` |
| **Account** (Company) | Name: institution (or "Unknown Lab"), tag: `sparq-device` |
| **Note** on Contact | "Sparq registered — Device: FLMT09788 (P4SPR), App: v2.0.5" |

If a Contact with the same email already exists (device previously registered, or sales already has this contact), the existing record is updated — not duplicated.

### 4.2 Activity logged on every Sparq Coach send

Each `POST /sparq/coach/v1` call logs an Activity on the Contact:

```
Activity type:  "Sparq Coach run submitted"
Note:           "Run: ⭐⭐⭐ Medium | Cycles: 7/8 completed
                 Issues: 1 bubble cycle, 1 drifting baseline
                 Tier 2 (Excel): No"
```

This gives the sales team a live feed of how actively each lab is using the instrument and what problems they are hitting — without the sales rep having to do anything.

### 4.3 Failure pattern tags

After each run upload, the backend evaluates the aggregate failure patterns and applies tags to the Nutshell Contact:

| Failure pattern | Tag applied | Retention |
|---|---|---|
| ≥ 2 bubble cycles in one run | `issue-bubbles` | Until 3 clean runs in a row |
| ≥ 2 regen-incomplete cycles | `issue-regen` | Until regen score improves |
| Missed injection ≥ 2 cycles | `issue-injection-detection` | Until resolved |
| Run star rating ≤ 2 for 3 consecutive runs | `struggling-user` | Until 2 good runs |
| First Pro-tier run completed | `pro-user` | Permanent |
| 10+ runs submitted total | `active-user` | Permanent |
| Run star rating ⭐⭐⭐⭐⭐ × 3 consecutive | `power-user` | Permanent |

Tags are additive — a contact can have multiple. They drive the upsell pipeline (§5) and help the sales team prioritise outreach.

### 4.4 Automated Tasks

When high-priority tags are applied, the backend creates a Task in Nutshell assigned to the account owner:

| Trigger | Task created |
|---|---|
| `struggling-user` tag applied | "Check in with [lab] — 3 consecutive low-scoring runs" |
| New registration from a known institution (email domain match) | "New Sparq registration at [institution] — introduce yourself" |
| `pro-user` first occurrence | "Pro user milestone at [lab] — consider upsell to P4PRO" |

---

## 5. Upsell Pipeline

### 5.1 Product catalogue

A static catalogue of Affilabs products with associated failure-pattern triggers. Maintained server-side — updated without app release.

| Product | SKU | Trigger pattern |
|---|---|---|
| Running buffer degassing kit | `KIT-DEGAS-01` | `issue-bubbles` × 2+ runs |
| Regeneration scouting kit (pH gradient + glycine panel) | `KIT-REGEN-SCOUT-01` | `issue-regen` × 2+ runs |
| Amine coupling optimisation kit | `KIT-AMINECOUPLING-01` | Low signal score × 2+ runs |
| Sensor chip bundle (×5) | `CHIP-BUNDLE-05` | 10+ runs on same chip (inferred from run count) |
| Advanced kinetics training (1hr online session) | `SVC-TRAINING-KINETICS` | First Pro-tier run |
| P4PRO upgrade consultation | `SVC-UPGRADE-P4PRO` | `pro-user` + model = `P4SPR` |
| Service contract renewal | `SVC-CONTRACT-ANNUAL` | Account age > 11 months |

### 5.2 In-app product recommendation

At the end of the Sparq Coach debrief in the Sparq sidebar, Haiku appends a product recommendation if a trigger pattern is active. The recommendation is part of the Haiku system prompt — the backend passes the triggered SKU(s) and product descriptions to Haiku, which weaves them into the coaching response naturally:

> "You've had air bubble events in your last two runs. A few things to try: degas your running buffer under vacuum for 10 minutes before each session, and prime your lines twice before starting acquisition. If bubbles persist, a proper degassing setup makes a real difference — [Affilabs Degassing Kit →](https://affilabs.com/shop/kit-degas-01)"

The link is a tracked URL (`affilabs.com/shop/kit-degas-01?ref=sparq&device=FLMT09788`) so click-through is logged to the Nutshell Contact automatically via UTM → CRM integration.

At most **one product recommendation per debrief** — the highest-priority triggered SKU only. No multi-product dump.

### 5.3 Nutshell lead creation

When a product recommendation is shown in-app, the backend also creates or updates a **Lead** in Nutshell:

```
Lead name:    "FLMT09788 — Degassing Kit"
Contact:      [linked to existing contact]
Account:      [linked to existing account]
Status:       New
Note:         "Auto-triggered by Sparq Coach — 3 bubble runs. Recommendation shown in-app on 2026-02-25."
Product:      KIT-DEGAS-01
```

The sales team sees a qualified lead with full context — no manual data entry, no cold outreach. They know exactly what problem the lab is having and what was already recommended.

---

## 6. Account State in the App

### 6.1 Settings → Sparq panel

```
┌──────────────────────────────────────────────────────────┐
│  Sparq Account                                           │
│                                                          │
│  Device:       FLMT09788  (P4SPR)                        │
│  Account:      user@lab.com                              │
│  Institution:  McGill University                         │
│  Status:       ✅ Connected                              │
│                                                          │
│  Sparq Coach                                             │
│  ○ Send run summaries automatically after each session   │
│  ● Ask me before each send              ← default        │
│                                                          │
│  Data sharing                                            │
│  ☐ Allow Affilabs to use my run data to improve Sparq    │
│    (Tier 2 Excel uploads — unchecked by default)         │
│                                                          │
│  [Disconnect account]    [affilabs.com/privacy]          │
└──────────────────────────────────────────────────────────┘
```

### 6.2 Account states

| State | What it means | UI indicator |
|---|---|---|
| `unregistered` | No `sparq_account.json` | "Connect Sparq" prompt in Edits header |
| `registered` | Valid API key, last ping OK | ✅ green dot in Settings |
| `api_key_invalid` | Key rejected by backend | ⚠ "Reconnect Sparq" in Settings |
| `offline` | No internet | Sparq Coach button greyed out |

---

## 7. Coaching History (Local)

Coaching history is stored locally in `data/spark/coach_history.json`. The backend is stateless — it does not store run summaries or coaching responses.

```json
[
  {
    "run_id": "<uuid>",
    "session_file": "2026-02-25_14-32_recording.csv",
    "sent_at": "2026-02-25T15:44:00Z",
    "stars": 3,
    "tier": "medium",
    "tier2_included": false,
    "coaching_response": "Your baseline was drifting on 2 cycles...",
    "product_recommendation": "KIT-DEGAS-01"
  }
]
```

When Haiku has access to prior coaching history (future Phase 10+), the last 5 entries are included in the system prompt so Haiku can track improvement: "Your bubble rate has dropped since your last run — whatever you changed is working."

---

## 8. Privacy and Data Governance

### 8.1 What Affilabs stores server-side

| Data | Stored? | Notes |
|---|---|---|
| Device serial | ✅ | Primary key for account |
| Owner email | ✅ | Account management only |
| Institution | ✅ | CRM context |
| Run summary (Tier 1) | ✅ | Anonymised — no ligand/analyte names, no PII |
| Excel export (Tier 2) | ✅ if opted in | Stored for model training, not resold |
| Raw sensorgram data beyond Excel | ❌ | Never collected |
| Individual user identity within a lab | ❌ | Device-bound, not person-bound |

### 8.2 User rights

- **View:** `data/spark/coach_history.json` contains everything sent from this device
- **Delete:** "Withdraw consent and delete my data" in Settings → Sparq sends `DELETE /sparq/account/{device_serial}` — removes all server-side data for this serial within 30 days
- **Export:** `GET /sparq/account/{device_serial}/export` — returns full data dump (future)

### 8.3 Consent checkpoints

| Action | Consent required |
|---|---|
| Registration | Email + privacy policy acknowledgement |
| Tier 1 send | None beyond initial registration |
| Tier 2 send | Explicit checkbox on every send |
| Product recommendation display | Covered by registration privacy policy |
| Nutshell CRM entry | Covered by registration privacy policy |

---

## 9. Implementation Phases

| Phase | Deliverable | Gate |
|---|---|---|
| **1** | Backend: `/sparq/register` endpoint + Nutshell contact/account creation | Test with one real device serial. Verify Nutshell record created correctly. |
| **2** | In-app: `SparqRegistrationDialog` + `SparqAccountService` + `config/sparq_account.json` write | End-to-end registration from app → backend → Nutshell. |
| **3** | Backend: `/sparq/coach/v1` — Tier 1 upload + Haiku coaching + Nutshell activity log | First real coaching debrief. Validate Haiku system prompt produces useful advice. |
| **4** | Failure pattern tags + automated Tasks in Nutshell | Verify tags apply/remove correctly across run sequences. |
| **5** | Product catalogue + upsell recommendation in Sparq Coach debrief | Validate recommendation relevance. Confirm tracked link click-through → Nutshell. |
| **6** | Nutshell Lead creation on recommendation trigger | Sales team review — are auto-leads useful or noisy? |
| **7** | Tier 2 opt-in (Excel upload) — checkbox in confirmation dialog, multipart upload | Privacy review. Confirm Excel parsing produces better Haiku advice. |
| **8** | Multi-run coaching history in Haiku context ("your bubble rate has dropped...") | Requires ≥ 5 runs of history. Validate improvement tracking is accurate. |

---

## 10. Out of Scope

- Server-side coaching history storage — local only (`coach_history.json`)
- Multi-user accounts within a lab — device-bound only
- Subscription / paywall for Sparq Coach — free for registered devices, v1
- In-app store / cart — product links go to `affilabs.com/shop`
- Peer benchmarking ("top 20% of P4SPR users") — deferred, requires sufficient user base
- Push notifications / coaching summary emails — deferred
