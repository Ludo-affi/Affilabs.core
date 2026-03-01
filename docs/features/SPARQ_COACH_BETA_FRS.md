# Sparq Coach Beta — FRS

**Document Status:** 🟡 Implementation Ready  
**Last Updated:** February 28, 2026  
**Related FRS:** `SPARQ_ACCOUNT_FRS.md` (account registration, Nutshell CRM baseline)

**Client-side source files (this repo):**
- `affilabs/services/sparq_coach_service.py` — ✅ Implemented (Phase 1, v2.0.5) — HTTP client: bug submit, Coach Beta chat
- `affilabs/services/bug_reporter.py` — `send_bug_report_auto()` planned for Phase 1.6
- `affilabs/widgets/spark_help_widget.py` — ✅ Exists — "Ask Sparq Coach" button wiring pending (Phase 1.6)

**Backend (Cloudflare Worker — separate repo, not in this codebase):**
- `POST /sparq/bug` — receive bug report, notify engineering, log to Nutshell
- `POST /sparq/coach/beta/chat` — proxy to Anthropic Claude Haiku, enforce rate limit

---

## 1. Purpose

Two features share one backend and one auth model:

| Feature | Problem it solves |
|---|---|
| **Auto bug reporting** | Users currently get a wall of text to copy and email manually — nobody does it. Bugs go unreported. |
| **Sparq Coach Beta chat** | Local Sparq engine (pattern matching + TinyLM) fails on complex, novel, or multi-step questions. Customers hit a dead end with "I don't know how to answer that." |

Both features are **free for registered beta devices** and **rate-limited per device serial** via Cloudflare KV so costs stay controlled while the user base is small.

---

## 2. Architecture Overview

```
In-app Sparq sidebar
        │
        │  HTTPS (JSON)
        ▼
Cloudflare Worker  ← free tier: 100k req/day, zero cold start latency
        │
        ├── /sparq/bug ────────────► Discord webhook (instant engineer ping)
        │                         ► Nutshell Activity on Contact
        │
        └── /sparq/coach/beta/chat ► Cloudflare KV (rate limit check: daily count per serial)
                                   ► Anthropic API (Claude 3 Haiku)
                                   ► Nutshell Activity on Contact ("Asked Sparq Coach: …")
```

**No app server.** The Cloudflare Worker IS the backend. No hosting cost for beta volume. The Anthropic + Nutshell API keys live only in Cloudflare Worker environment secrets — never in the app or in this repo.

---

## 3. Authentication

Reuses the `device_serial` + `api_key` pair from `SPARQ_ACCOUNT_FRS.md §2`.

- All requests include `Authorization: Bearer <api_key>` header and `X-Device-Serial: <serial>` header
- Worker validates the pair against a Cloudflare KV store populated at registration time
- Unregistered devices get HTTP 401; app gracefully degrades (see §8)

**No new registration dialog.** Sparq Coach Beta activates automatically for any device that has a valid `config/sparq_account.json`.

---

## 4. Bug Reporting — Auto-Submit

### 4.1 Current flow (bad)

`🐛` button → user types description → `send_bug_report()` generates a 200-line email draft → user copies text → opens email client → attaches screenshot manually → sends.

This has ~0% completion rate.

### 4.2 Target flow

`bug icon` button → user types description → **Submit** → confirmation in chat. Screenshot auto-attached. Logs auto-included. User does nothing else. Engineering gets pinged in Discord within seconds.

### 4.3 Bug button — SVG replacement

Replace the `"🐛"` emoji button with a proper SVG icon:

```xml
<!-- affilabs/ui/img/bug_icon.svg — 24×24 viewBox -->
<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <!-- Body -->
  <ellipse cx="12" cy="14" rx="5" ry="6" stroke="#7D5A00" stroke-width="1.5" fill="none"/>
  <!-- Head -->
  <circle cx="12" cy="7" r="3" stroke="#7D5A00" stroke-width="1.5" fill="none"/>
  <!-- Antennae -->
  <line x1="10" y1="5" x2="8" y2="3" stroke="#7D5A00" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="14" y1="5" x2="16" y2="3" stroke="#7D5A00" stroke-width="1.5" stroke-linecap="round"/>
  <!-- Legs left -->
  <line x1="7" y1="12" x2="4" y2="11" stroke="#7D5A00" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="7" y1="14" x2="4" y2="14" stroke="#7D5A00" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="7" y1="16" x2="4" y2="17" stroke="#7D5A00" stroke-width="1.5" stroke-linecap="round"/>
  <!-- Legs right -->
  <line x1="17" y1="12" x2="20" y2="11" stroke="#7D5A00" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="17" y1="14" x2="20" y2="14" stroke="#7D5A00" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="17" y1="16" x2="20" y2="17" stroke="#7D5A00" stroke-width="1.5" stroke-linecap="round"/>
</svg>
```

Rendered at 16×16 inside the 36×36 button, same `get_affilabs_resource()` + `QSvgRenderer` pattern used throughout.

### 4.4 Bug submission dialog flow (in-chat)

```
User clicks bug button
  └─ Sparq chat: "What happened? Describe the bug — I'll capture everything else automatically.
                  (or drag a screenshot here)"

User types description [+ optional dragged image], clicks Submit
  └─ Sparq chat: "Sending… ⏳"
  └─ [background thread]
        ├─ capture screenshot (existing _take_screenshot())
        ├─ read last 150 lines from most recent log
        ├─ collect system info + device serial + version
        └─ POST /sparq/bug (see §4.5)

On success (HTTP 200):
  └─ Sparq chat: "✅ Report submitted — we'll follow up at [email on file]."
  └─ Local: append to data/spark/bug_history.json

On failure (no internet / 5xx):
  └─ Sparq chat: "Couldn't reach server. Here's the report text to email manually:"
  └─ [fall back to existing generate_bug_report_draft() copy-paste flow]
```

No modal dialog. Entirely within the Sparq chat panel. The fallback ensures the feature degrades gracefully without a Sparq account or internet.

### 4.5 `POST /sparq/bug` payload

```json
{
  "device_serial": "FLMT09788",
  "instrument_model": "P4SPR",
  "app_version": "2.0.5",
  "user_name": "lucia",
  "description": "Calibration dialog hangs after LED pass…",
  "log_tail": "…last 150 lines…",
  "system_info": {
    "os": "Windows-11-10.0.26100",
    "python": "3.12.4",
    "machine": "AMD64"
  },
  "screenshot_b64": "<base64-encoded PNG, max 1MB>",
  "additional_images_b64": [],
  "submitted_at": "2026-02-28T14:32:00Z"
}
```

Screenshot is base64-encoded inline (not a separate upload). Cap at **1 MB** after encoding — if larger, send without screenshot and note it in the report.

### 4.6 What the Worker does on receiving `/sparq/bug`

1. **Validate** `Authorization` + `X-Device-Serial` headers against KV
2. **Discord webhook POST** — rich embed:
   ```
   🐛 Bug Report — FLMT09788 (P4SPR) v2.0.5
   lucia @ 2026-02-28 14:32
   ─────────────────────────────────
   Calibration dialog hangs after LED pass…
   ─────────────────────────────────
   OS: Windows-11 | Python 3.12.4
   [View log tail] [Screenshot attached]
   ```
3. **Nutshell Activity** on the Contact linked to this device serial:
   ```
   Type:  "Bug Report"
   Note:  "v2.0.5 — Calibration dialog hangs after LED pass…"
   ```
4. **Return HTTP 200** `{ "status": "received", "ticket_id": "<uuid>" }`

Rate limit on `/sparq/bug`: **10 bug reports per device per day** (KV counter). Prevents spam. Returns HTTP 429 with `{ "error": "report_limit_reached" }` — app falls back to draft mode.

---

## 5. Sparq Coach Beta Chat

### 5.1 When it activates

The local `SparkAnswerEngine` already classifies questions as matched/unmatched. An unmatched question (or a question the user explicitly escalates) can be routed to Sparq Coach Beta.

**Trigger options (both wired):**
1. **Auto-escalate**: if local engine returns a "miss" (no match confidence), automatically offer Coach Beta
2. **Manual**: user clicks "Ask Sparq Coach ✨" button that appears below any answer

```
User asks: "Why is my sensorgram baseline drifting between cycles?"
  └─ Local engine: no high-confidence match
  └─ Sparq chat: "[local best answer…]
                  ─────────────────────────────────────
                  Not sure? Ask Sparq Coach for a deeper answer.
                  [Ask Sparq Coach ✨]  (3 of 20 daily uses remaining)"
```

### 5.2 Rate limiting display

The remaining-uses count is fetched from the Worker on Sparq sidebar open (cached for 60 seconds). Displayed as a soft counter below the Coach button — not a hard blocker. When quota is exhausted:
- Coach button becomes greyed, tooltip: "Daily limit reached — resets at midnight UTC"
- Local engine and bug reporting continue to work normally

### 5.3 `POST /sparq/coach/beta/chat` payload

```json
{
  "device_serial": "FLMT09788",
  "instrument_model": "P4SPR",
  "app_version": "2.0.5",
  "question": "Why is my sensorgram baseline drifting between cycles?",
  "local_answer": "…what local engine returned, if any…",
  "context": {
    "active_tab": "live",
    "is_recording": false,
    "last_calibration_age_min": 15
  }
}
```

The `context` block is cheap runtime state — helps Claude give relevant answers without the user needing to explain their situation.

### 5.4 Worker: Claude Haiku system prompt

```
You are Sparq, the built-in AI assistant for Affilabs.core — an SPR (Surface Plasmon Resonance) instrument control application.

You help users of the SimplexSPR, SimplexFlow, and SimplexPro instruments operated with this software. You are intelligent, concise, and technically accurate. You understand SPR binding kinetics, fluidics, sensor chip chemistry, and instrument troubleshooting.

Device context: {instrument_model}, software v{app_version}.
The local Sparq assistant attempted to answer but was not confident.
Local answer provided (for reference): {local_answer}

Answer the user's question directly. If the local answer was partially correct, confirm and extend it. If it was wrong, correct it politely. Keep answers under 250 words. Use **bold** for key terms. Use `code` formatting for settings, file names, or exact values.

Do NOT hallucinate product names, specifications, or procedures. If you are not certain, say so and recommend the user contact support at info@affiniteinstruments.com.
```

**Model:** `claude-3-haiku-20240307`  
**Max tokens:** 600 output  
**Temperature:** 0.3 (factual, low creativity)  
**Cost per question:** ~$0.0002–0.0008 depending on question length

### 5.5 Rate limit strategy

| Quota type | Limit | Reset | Storage |
|---|---|---|---|
| Coach Beta chat per device | **20 requests / day** | Midnight UTC | Cloudflare KV: `quota:{serial}:chat:{YYYYMMDD}` |
| Bug reports per device | **10 reports / day** | Midnight UTC | Cloudflare KV: `quota:{serial}:bug:{YYYYMMDD}` |
| Global (all devices) | **500 chat req / day** | Midnight UTC | Cloudflare KV: `quota:global:chat:{YYYYMMDD}` |

The global cap protects against unexpected device volume. If hit, return HTTP 503 with a friendly message (not 429 — the user hasn't done anything wrong).

**Worst-case cost estimate:** 20 beta devices × 20 questions/day × $0.0008/question = **$0.32/day**. All 20 devices going full throttle simultaneously. Actual cost will be a fraction of this.

### 5.6 Nutshell Activity on Chat

Each successful Coach Beta query logs a Nutshell Activity on the device's Contact:

```
Type:  "Sparq Coach Beta"
Note:  "Asked: 'Why is my baseline drifting?' — answered by Claude Haiku, v2.0.5"
```

This gives the sales/support team visibility into what customers are struggling with, without any PII from the answer content.

---

## 6. `sparq_coach_service.py` — Client Interface

```python
# affilabs/services/sparq_coach_service.py

class SparqCoachService:
    """HTTP client for Sparq Coach Beta — bug reporting + Claude chat."""

    BASE_URL = "https://sparq.affiniteinstruments.com"  # Cloudflare Worker URL

    def submit_bug_report(
        self,
        description: str,
        user_name: str = "",
        screenshot_bytes: bytes | None = None,
        additional_images: list[str] = None,
    ) -> tuple[bool, str]:
        """
        Auto-submit a bug report to the backend.

        Returns:
            (True, ticket_id) on success.
            (False, error_message) on failure — caller falls back to draft mode.
        """
        ...

    def ask_coach(
        self,
        question: str,
        local_answer: str = "",
        context: dict | None = None,
    ) -> tuple[bool, str, int]:
        """
        Send a question to Sparq Coach Beta (Claude Haiku).

        Returns:
            (True, answer_text, remaining_quota) on success.
            (False, error_message, 0) on failure.
        """
        ...

    def get_quota(self) -> dict:
        """
        Fetch current rate limit status for this device.
        Returns: { "chat_remaining": int, "bug_remaining": int, "resets_at": str }
        Cached for 60 seconds. Returns defaults on network failure (graceful).
        """
        ...

    def is_available(self) -> bool:
        """True if device has a registered Sparq account (api_key in config)."""
        ...
```

The service reads `config/sparq_account.json` for `device_serial` and `api_key`. If the file does not exist or has no `api_key`, `is_available()` returns `False` and all methods return graceful failure tuples without making network calls.

**Timeout:** 8 seconds for chat (Claude latency), 5 seconds for bug reports, 3 seconds for quota fetch.

---

## 7. `bug_reporter.py` — Changes Required

Add `send_bug_report_auto()` that tries `SparqCoachService.submit_bug_report()` first and falls back to `generate_bug_report_draft()` on failure:

```python
def send_bug_report_auto(
    description: str,
    user_name: str = "",
    include_screenshot: bool = True,
    additional_images: list[str] = None,
) -> tuple[bool, str, str]:
    """
    Try to auto-submit via Sparq Coach backend; fall back to draft mode.

    Returns:
        (auto_submitted: bool, result_text: str, ticket_id_or_draft: str)
    """
```

`SparkHelpWidget._submit_bug_report()` is updated to call `send_bug_report_auto()` instead of `send_bug_report()`.

---

## 8. Graceful Degradation

| Condition | Behavior |
|---|---|
| No Sparq account registered | Bug flow falls back to copy-paste draft. Coach Beta button hidden. |
| No internet | Bug auto-submit fails → fallback draft shown. Coach Beta button greyed with "Offline". |
| Claude API down (5xx from Worker) | "Sparq Coach is temporarily unavailable. Your local Sparq is still here." Local engine continues. |
| Daily quota exhausted (chat) | Coach button disabled. Bug reporting unaffected. |
| Daily quota exhausted (bug) | Bug button still shows, submit shows "Daily limit reached — email info@affiniteinstruments.com directly." |
| HTTP 401 (invalid api_key) | "Sparq account needs reconnection. Go to Settings → Sparq." Both features disabled. |
| Screenshot larger than 1 MB encoded | Send report without screenshot, note "screenshot omitted (too large)" in report body. |

---

## 9. Notification Delivery to Engineering

Bug reports must reach the engineering team with zero friction. Two notification channels, both configured as Worker environment secrets:

### 9.1 Discord webhook (primary)

Worker POSTs a rich embed to a dedicated `#sparq-bugs` Discord channel:

```
🐛 Bug Report — FLMT09788 (P4SPR)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
lucia | v2.0.5 | 2026-02-28 14:32 UTC

DESCRIPTION
Calibration dialog hangs after LED pass…

SYSTEM
Windows-11-10.0.26100 | Python 3.12.4

[Ticket: abc-123]
```

Screenshot (if included) posted as attachment in the same message. Engineers see everything without opening Nutshell.

### 9.2 Nutshell Activity (secondary)

Logged to the Contact record so the support/sales team has full history. Engineering reads Discord; sales reads Nutshell. Both get the same data automatically.

---

## 10. Cloudflare Worker — Endpoint Summary

| Endpoint | Method | Auth | Rate limit |
|---|---|---|---|
| `/sparq/bug` | POST | api_key required | 10/device/day |
| `/sparq/coach/beta/chat` | POST | api_key required | 20/device/day + 500/global/day |
| `/sparq/coach/beta/quota` | GET | api_key required | 60s cached, no KV write |

Worker environment secrets (set in Cloudflare dashboard, never in this repo):
- `ANTHROPIC_API_KEY`
- `NUTSHELL_API_KEY`
- `NUTSHELL_API_USER`
- `DISCORD_WEBHOOK_URL_BUGS`
- `SPARQ_ACCOUNT_KV` (KV namespace binding)

---

## 11. UI Changes in `spark_help_widget.py`

### 11.1 Bug button

Replace `"🐛"` emoji with `bug_icon.svg`:
- Load via `get_affilabs_resource("ui/img/bug_icon.svg")` → `QSvgRenderer` → `QPixmap(16, 16)`
- Button stays 36×36, amber style unchanged
- Tooltip updated: `"Report a Bug — submitted automatically with logs + screenshot"`

### 11.2 Sparq Coach Beta button

Appears below each AI answer bubble when `SparqCoachService.is_available()` is True and local answer was a miss:

```
┌─────────────────────────────────────────────────┐
│  [local answer text]                            │
│                                                 │
│  ─────────────────────────────────────────────  │
│  Ask Sparq Coach ✨  (17 of 20 uses remaining)  │
└─────────────────────────────────────────────────┘
```

Button style: secondary, no border, `#007AFF` text, right-aligned below answer bubble. 32px height.

The remaining-uses count is rendered by the `SparkHelpWidget` from `SparqCoachService.get_quota()` result. If quota fetch fails, the count is omitted and the button still shows.

### 11.3 Coach Beta answer rendering

Coach Beta answers display identically to local answers (same `MessageBubble`, is_user=False) but with a subtle "✨ Sparq Coach" label in the timestamp row instead of the clock time:

```
[answer text]
✨ Sparq Coach  👍 👎
```

This distinguishes AI-generated answers from local pattern matches without creating visual noise.

---

## 12. `data/spark/bug_history.json` — Local Record

Every submitted (or attempted) bug report is appended to a local history file:

```json
[
  {
    "ticket_id": "abc-123",
    "submitted_at": "2026-02-28T14:32:00Z",
    "description": "Calibration dialog hangs…",
    "auto_submitted": true,
    "screenshot_included": true,
    "status": "received"
  }
]
```

`auto_submitted: false` means the user got the draft copy-paste fallback. This lets you see how often the network path is failing in field devices.

---

## 13. Implementation Order

| Step | What | File(s) | Notes |
|---|---|---|---|
| 1 | Create `bug_icon.svg` | `affilabs/ui/img/bug_icon.svg` | SVG per §4.3 |
| 2 | Replace emoji bug button with SVG | `spark_help_widget.py` | Use cached `QSvgRenderer` pattern |
| 3 | Implement `SparqCoachService` | `affilabs/services/sparq_coach_service.py` | `submit_bug_report`, `ask_coach`, `get_quota`, `is_available` |
| 4 | Update `send_bug_report_auto()` in bug_reporter | `affilabs/services/bug_reporter.py` | Calls service; fallback to draft on failure |
| 5 | Wire `_submit_bug_report()` to use `send_bug_report_auto()` | `spark_help_widget.py` | |
| 6 | Deploy Cloudflare Worker with `/sparq/bug` endpoint | CF Worker repo | Discord webhook + Nutshell Activity |
| 7 | Test end-to-end: bug submit → Discord ping → Nutshell activity | — | Gate for step 8 |
| 8 | Add `/sparq/coach/beta/chat` to Worker | CF Worker repo | Claude Haiku + KV rate limit |
| 9 | Wire `ask_coach()` + Coach Beta button in widget | `spark_help_widget.py` | Show on local engine miss only |
| 10 | Add `/sparq/coach/beta/quota` endpoint | CF Worker repo | |
| 11 | Wire `get_quota()` → remaining-uses display | `spark_help_widget.py` | |

Steps 1–7 can ship as "Sparq Coach Beta — Bug Reporting" before chat is live. Steps 8–11 are independent and can follow.

---

## 14. Out of Scope (Beta)

- Conversation history (multi-turn Claude sessions) — each question is stateless
- Email notifications to users after bug is triaged
- Public bug tracker / status page
- Claude response streaming (streamed SSE in sidebar) — deferred, adds complexity
- Sparq Coach Beta for unregistered devices — registration gate is intentional
- Per-user quotas within a lab — quota is per device serial, not per named user
