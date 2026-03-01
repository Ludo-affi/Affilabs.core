# Sparq Coach Beta — Full Setup Guide

**Audience:** Lucia (founder) + dev team  
**Goal:** Ship end-to-end bug reporting + Claude chat support in the shortest path  
**Last Updated:** February 28, 2026  
**Reference FRS:** [SPARQ_COACH_BETA_FRS.md](../features/SPARQ_COACH_BETA_FRS.md)

---

## Glossary

| Term | Meaning |
|---|---|
| **Sparq** | Local AI assistant built into the sidebar (pattern matching + TinyLM, works offline) |
| **Sparq Coach Beta** | Cloud extension of Sparq — bug auto-submit + Claude Haiku live chat |
| **Cloudflare Worker** | Serverless function that acts as the backend proxy (free tier ~100k req/day) |
| **Cloudflare KV** | Key-value store used to track per-device rate limits (also free tier) |
| **Claude Haiku** | Anthropic's cheapest/fastest model. ~$0.0008/question. Used for Sparq Coach chat answers |
| **Nutshell** | Your CRM. Every registered device = a Contact. Bug reports and chat usage = Activities on that Contact |
| **Discord webhook** | One URL you paste into the Worker — all bug reports appear as a rich message in a `#sparq-bugs` channel |
| **api_key** | A secret string issued to each registered device. Ties the device to its Nutshell Contact. Stored in `config/sparq_account.json` on the customer's machine |
| **device_serial** | Hardware serial (e.g. `FLMT09788`). Primary key across all systems |
| **Sparq registration** | One-time in-app flow where the user enters their email — creates the Contact in Nutshell and issues the api_key |

---

## Phase 1 — Software (client-side) ← Start here

Estimated time: **2–3 days** of coding. No backend needed yet — bug reports fall back to draft mode until Phase 2 is deployed.

### Step 1.1 — Create `bug_icon.svg`

Create `affilabs/ui/img/bug_icon.svg` with the SVG from FRS §4.3. Replace the `"🐛"` emoji button in `spark_help_widget.py` with the SVG loaded via `QSvgRenderer` (same pattern as all other icon buttons).

### Step 1.2 — Implement `SparqCoachService`

Create `affilabs/services/sparq_coach_service.py` per FRS §6. The class needs:

```python
class SparqCoachService:
    BASE_URL = "https://sparq.affiniteinstruments.com"

    def is_available(self) -> bool:       # checks config/sparq_account.json exists + has api_key
    def submit_bug_report(...) -> tuple   # POST /sparq/bug
    def ask_coach(...) -> tuple           # POST /sparq/coach/beta/chat
    def get_quota(...) -> dict            # GET /sparq/coach/beta/quota
```

The service always reads `config/sparq_account.json` for `device_serial` and `api_key`. If that file doesn't exist or has no key, `is_available()` → False, all methods return graceful failures without any network call.

Add `requests` to `pyproject.toml` dependencies if not already present (it may be there via other code). Timeout: 8s chat, 5s bug, 3s quota.

### Step 1.3 — Update `bug_reporter.py`

Add `send_bug_report_auto()` that:
1. Tries `SparqCoachService().submit_bug_report(...)` first
2. On success → returns `(True, "auto_submitted", ticket_id)`
3. On failure (no internet, no account, 5xx) → falls back to existing `generate_bug_report_draft()` → returns `(False, "draft", draft_text)`

Keep `send_bug_report()` (the old one) intact so nothing else breaks.

### Step 1.4 — Wire `spark_help_widget.py`

Update `_submit_bug_report()` in `SparkHelpWidget` to call `send_bug_report_auto()` and show the right confirmation message:
- Auto-submitted: `"✅ Report submitted — we'll follow up at [email on file]."`
- Draft fallback: `"Couldn't reach server — copy the text below and email info@affiniteinstruments.com"`

Append every attempt (auto or draft) to `data/spark/bug_history.json` (create if not exists).

### Step 1.5 — Sparq registration flow (prerequisite for auth)

Without a registered account, `is_available()` is False and features gracefully degrade — so Steps 1.1–1.4 can be built and tested before registration is implemented. BUT to actually use the cloud features, the device needs an `api_key`.

For the very first beta test: **manually create `config/sparq_account.json`** on the test device with a hardcoded api_key you define. You're provisioning it by hand until the registration dialog is built.

```json
{
  "device_serial": "AFFI09792",
  "instrument_model": "P4SPR",
  "sparq_account_id": "test-001",
  "api_key": "beta-test-key-001",
  "owner_email": "info@affiniteinstruments.com",
  "institution": "Affinite Instruments",
  "registered_at": "2026-03-01T00:00:00Z"
}
```

The Worker validates this key against a KV entry you insert manually for the first test. Full registration dialog (SPARQ_ACCOUNT_FRS.md §3) comes after beta validation.

### Step 1.6 — Coach Beta chat button

After the Worker is live (Phase 2), add the "Ask Sparq Coach ✨" button below each local-engine miss. Per FRS §11.2 — a subtle secondary button with remaining-count from `get_quota()`.

**Do not block on this.** Steps 1.1–1.5 can ship first. Chat button is additive.

---

## Phase 2 — Cloudflare Worker (backend)

Estimated time: **half a day** to deploy the first endpoint. No server to manage — Cloudflare runs it.

### Step 2.1 — Create a Cloudflare account

Go to [cloudflare.com](https://cloudflare.com). Free plan is enough for beta volume. You need a credit card on file (Workers free tier is ~$0/month at beta scale).

### Step 2.2 — Create a KV namespace

In the Cloudflare dashboard: **Workers & Pages → KV → Create namespace**. Name it `SPARQ_KV`. This stores:
- Rate limit counters: `quota:AFFI09792:bug:20260301` → `"3"` (reads: device 09792 has submitted 3 bugs today)
- Device API keys for validation: `apikey:beta-test-key-001` → `"AFFI09792"` (reads: this key belongs to serial 09792)

Insert your first test key manually: click "Add entry", Key = `apikey:beta-test-key-001`, Value = `AFFI09792`.

> **Serial prefix:** All shipped devices use the `AFFI` prefix (e.g. `AFFI09792`). Legacy `FLMT` serials are retired — do not use in new provisioning.

### Step 2.3 — Create the Worker

In the dashboard: **Workers & Pages → Create Application → Worker**. Name it `sparq-worker`. Use the Quick Edit (online editor) for the first deployment:

```javascript
// sparq-worker/index.js  (Cloudflare Workers — runs at edge, zero cold start)

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "POST" && url.pathname === "/sparq/bug") {
      return handleBugReport(request, env);
    }
    if (request.method === "POST" && url.pathname === "/sparq/coach/beta/chat") {
      return handleCoachChat(request, env);
    }
    if (request.method === "GET" && url.pathname === "/sparq/coach/beta/quota") {
      return handleQuota(request, env);
    }

    return new Response("Not found", { status: 404 });
  }
};

// ── Auth helper ───────────────────────────────────────────────────────────────

async function validateAuth(request, env) {
  const apiKey = request.headers.get("Authorization")?.replace("Bearer ", "");
  const serial = request.headers.get("X-Device-Serial");
  if (!apiKey || !serial) return null;

  const storedSerial = await env.SPARQ_KV.get(`apikey:${apiKey}`);
  if (storedSerial !== serial) return null;
  return serial;  // returns serial on success, null on failure
}

// ── /sparq/bug ────────────────────────────────────────────────────────────────

async function handleBugReport(request, env) {
  const serial = await validateAuth(request, env);
  if (!serial) return new Response(JSON.stringify({ error: "unauthorized" }), { status: 401 });

  // Rate limit: 10 bug reports per device per day
  const today = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const countKey = `quota:${serial}:bug:${today}`;
  const count = parseInt(await env.SPARQ_KV.get(countKey) || "0");
  if (count >= 10) {
    return new Response(JSON.stringify({ error: "report_limit_reached" }), { status: 429 });
  }

  const body = await request.json();
  const ticketId = crypto.randomUUID().slice(0, 8);

  // 1. Discord notification
  await notifyDiscord(env, body, serial, ticketId);

  // 2. Nutshell Activity
  await logNutshellActivity(env, serial, "Bug Report",
    `v${body.app_version} — ${body.description?.slice(0, 200)}`);

  // 3. Increment rate limit counter (expire after 24h)
  await env.SPARQ_KV.put(countKey, String(count + 1), { expirationTtl: 86400 });

  return new Response(JSON.stringify({ status: "received", ticket_id: ticketId }), {
    status: 200, headers: { "Content-Type": "application/json" }
  });
}

// ── /sparq/coach/beta/chat ────────────────────────────────────────────────────

async function handleCoachChat(request, env) {
  const serial = await validateAuth(request, env);
  if (!serial) return new Response(JSON.stringify({ error: "unauthorized" }), { status: 401 });

  const today = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const deviceKey = `quota:${serial}:chat:${today}`;
  const globalKey = `quota:global:chat:${today}`;

  const [deviceCount, globalCount] = await Promise.all([
    env.SPARQ_KV.get(deviceKey).then(v => parseInt(v || "0")),
    env.SPARQ_KV.get(globalKey).then(v => parseInt(v || "0")),
  ]);

  if (deviceCount >= 20) {
    return new Response(JSON.stringify({ error: "device_quota_exhausted", remaining: 0 }), { status: 429 });
  }
  if (globalCount >= 500) {
    return new Response(JSON.stringify({ error: "service_busy" }), { status: 503 });
  }

  const body = await request.json();

  // Call Anthropic Claude Haiku
  const systemPrompt = buildSystemPrompt(body);
  const anthropicResp = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": env.ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: "claude-3-haiku-20240307",
      max_tokens: 600,
      temperature: 0.3,
      system: systemPrompt,
      messages: [{ role: "user", content: body.question }],
    }),
  });

  if (!anthropicResp.ok) {
    return new Response(JSON.stringify({ error: "ai_unavailable" }), { status: 503 });
  }

  const aiData = await anthropicResp.json();
  const answer = aiData.content?.[0]?.text || "Sorry, I couldn't generate an answer.";

  // Increment counters
  await Promise.all([
    env.SPARQ_KV.put(deviceKey, String(deviceCount + 1), { expirationTtl: 86400 }),
    env.SPARQ_KV.put(globalKey, String(globalCount + 1), { expirationTtl: 86400 }),
  ]);

  // Log to Nutshell (fire-and-forget)
  logNutshellActivity(env, serial, "Sparq Coach Beta",
    `Asked: "${body.question?.slice(0, 100)}" — v${body.app_version}`);

  const remaining = 20 - deviceCount - 1;
  return new Response(JSON.stringify({ answer, remaining }), {
    status: 200, headers: { "Content-Type": "application/json" }
  });
}

// ── /sparq/coach/beta/quota ───────────────────────────────────────────────────

async function handleQuota(request, env) {
  const serial = await validateAuth(request, env);
  if (!serial) return new Response(JSON.stringify({ error: "unauthorized" }), { status: 401 });

  const today = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const [chatUsed, bugUsed] = await Promise.all([
    env.SPARQ_KV.get(`quota:${serial}:chat:${today}`).then(v => parseInt(v || "0")),
    env.SPARQ_KV.get(`quota:${serial}:bug:${today}`).then(v => parseInt(v || "0")),
  ]);

  return new Response(JSON.stringify({
    chat_remaining: Math.max(0, 20 - chatUsed),
    bug_remaining: Math.max(0, 10 - bugUsed),
    resets_at: "00:00 UTC",
  }), { status: 200, headers: { "Content-Type": "application/json" } });
}

// ── Discord notification ──────────────────────────────────────────────────────

async function notifyDiscord(env, body, serial, ticketId) {
  const embed = {
    title: `🐛 Bug Report — ${serial} (${body.instrument_model || "?"})`,
    color: 0xF0C040,
    fields: [
      { name: "Reporter", value: body.user_name || "anonymous", inline: true },
      { name: "Version", value: body.app_version || "?", inline: true },
      { name: "Ticket", value: ticketId, inline: true },
      { name: "OS", value: body.system_info?.os || "?", inline: true },
      { name: "Description", value: body.description?.slice(0, 1000) || "—", inline: false },
    ],
    timestamp: new Date().toISOString(),
  };

  const payload = { embeds: [embed] };

  // Attach screenshot if present (as a separate message with image)
  await fetch(env.DISCORD_WEBHOOK_URL_BUGS, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// ── Nutshell Activity ─────────────────────────────────────────────────────────

async function logNutshellActivity(env, serial, activityType, note) {
  // Nutshell API v1 — find contact by tag sparq:serial:<serial>, create activity
  // This is a best-effort fire-and-forget — errors are silent (not critical path)
  try {
    // Step 1: find contact ID by custom field or tag
    const searchResp = await fetch("https://app.nutshell.com/api/v1/json", {
      method: "POST",
      headers: {
        "Authorization": "Basic " + btoa(`${env.NUTSHELL_API_USER}:${env.NUTSHELL_API_KEY}`),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        method: "searchContacts",
        params: { query: { tag: `sparq:${serial}` }, limit: 1 },
        id: "1",
      }),
    });
    const searchData = await searchResp.json();
    const contactId = searchData?.result?.[0]?.id;
    if (!contactId) return;  // contact not found — silent fail

    // Step 2: create activity
    await fetch("https://app.nutshell.com/api/v1/json", {
      method: "POST",
      headers: {
        "Authorization": "Basic " + btoa(`${env.NUTSHELL_API_USER}:${env.NUTSHELL_API_KEY}`),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        method: "newActivity",
        params: {
          activity: {
            note: `[${activityType}] ${note}`,
            contacts: [{ id: contactId }],
          }
        },
        id: "2",
      }),
    });
  } catch (_) { /* fire and forget */ }
}

// ── System prompt builder ─────────────────────────────────────────────────────

function buildSystemPrompt(body) {
  return `You are Sparq, the built-in AI assistant for Affilabs.core — an SPR (Surface Plasmon Resonance) instrument control application.

You help users of the SimplexSPR, SimplexFlow, and SimplexPro instruments. You are intelligent, concise, and technically accurate. You understand SPR binding kinetics, fluidics, sensor chip chemistry, and instrument troubleshooting.

Device: ${body.instrument_model || "SimplexSPR"}, software v${body.app_version || "?"}.
Context: active_tab=${body.context?.active_tab || "?"}, is_recording=${body.context?.is_recording || false}.
${body.local_answer ? `\nThe local Sparq assistant attempted to answer but was not confident:\n"${body.local_answer}"\nIf the local answer was partially correct, confirm and extend it. If it was wrong, correct it politely.` : ""}

Answer the user's question directly. Keep answers under 250 words. Use **bold** for key terms. Use \`code\` formatting for settings, file names, or exact values.

Do NOT hallucinate product specs or procedures. If uncertain, say so and recommend: info@affiniteinstruments.com.`;
}
```

### Step 2.4 — Bind KV namespace to Worker

In the Worker settings: **Settings → Bindings → Add → KV namespace**. Variable name: `SPARQ_KV`. Select the namespace from Step 2.2.

### Step 2.5 — Set environment secrets

In the Worker settings: **Settings → Variables → Add secret** (one at a time):

| Secret name | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) → API keys |
| `NUTSHELL_API_KEY` | Nutshell → Settings → API keys |
| `NUTSHELL_API_USER` | Your Nutshell login email |
| `DISCORD_WEBHOOK_URL_BUGS` | Discord channel → Edit channel → Integrations → Webhooks → New webhook → Copy URL |

### Step 2.6 — Add a custom domain (optional but clean)

In Cloudflare: add `sparq.affiniteinstruments.com` as a route to the Worker. Already required by `SparqCoachService.BASE_URL`. If you don't have the domain on Cloudflare yet, either move DNS to Cloudflare (free) or use the default `*.workers.dev` URL and update `BASE_URL` in the code.

### Step 2.7 — Test end-to-end

```powershell
# From any machine — test bug endpoint directly
$body = @{
  device_serial = "AFFI09792"
  instrument_model = "P4SPR"
  app_version = "2.0.5"
  user_name = "lucia"
  description = "Test bug report — ignore"
  system_info = @{ os = "Windows-11"; python = "3.12.4" }
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "https://sparq-worker.jolly-pond-da61.workers.dev/sparq/bug" `
  -Method POST `
  -Headers @{ Authorization = "Bearer beta-test-key-001"; "X-Device-Serial" = "AFFI09792" } `
  -Body $body `
  -ContentType "application/json"
```

Expected: Discord message appears in `#sparq-bugs`, Nutshell Activity logged, response `{ "status": "received", "ticket_id": "..." }`.

---

## Phase 3 — Wix Website Integration

The Wix site is a **marketing + account portal**. It does NOT need to process payments or store data — Nutshell and the Worker handle that. What Wix needs to do:

### 3.1 Pages to set up

| Page | Purpose |
|---|---|
| `/sparq` | Landing page describing Sparq Coach Beta. "Sign up for beta" form → creates Nutshell Lead |
| `/privacy` | Required by the in-app registration flow (SPARQ_ACCOUNT_FRS §3). Documents what Affilabs stores |
| `/shop/kit-degas-01` etc. | Product pages for upsell links from Sparq Coach (UTM tracked → Nutshell) |
| `/sparq/account` | (Future) Self-serve account page — not needed for beta |

### 3.2 "Sign up for beta" form → Nutshell

Add a Wix Form on `/sparq`. Use **Wix Zapier integration** or **Wix Automations → Webhooks** to send form submissions to Nutshell:

**Option A — Zapier (easiest, free tier works):**
1. Wix Automations → When form is submitted → Send webhook to Zapier
2. Zapier: Catch webhook → Create or Update Contact in Nutshell (map email, name, company)
3. Zapier: Add tag `sparq-beta-waitlist` to that Contact

**Option B — Wix Velo (no third-party):**
Write a Velo backend function that calls Nutshell API directly on form submit. More control, no Zapier subscription needed. The Nutshell API key lives in Wix Secrets Manager.

**Recommended:** Option A for now (15-minute setup). Switch to Velo when you want custom logic.

### 3.3 UTM → Nutshell click tracking

Sparq in-app product links use: `affiniteinstruments.com/shop/kit-degas-01?ref=sparq&device=FLMT09792`

Set up UTM tracking in Wix Analytics. Then use Wix Automations: "When a visitor lands from UTM source `sparq`" → Send webhook to Zapier → Log Nutshell Activity: "Clicked Sparq product link — {device}" on the Contact matching that device serial.

This is a nice-to-have — product click visibility. Not required for beta launch.

---

## Phase 4 — Ticket Handling Workflow

When a bug report arrives in Discord and may need engineering action, here is the full loop:

### 4.1 Triage (same day, Lucia)

When a bug appears in `#sparq-bugs` Discord:

```
1. Read the description + log tail in the Discord embed
2. Classify:
   ├─ "User error / misunderstanding"  → Reply in Sparq chat (see §4.3)
   ├─ "Config / firmware issue"        → Remote assist (see §4.4)
   └─ "Real software bug"              → Create GitHub issue (see §4.2)
```

The ticket_id in the Discord embed is the reference number for all follow-up.

### 4.2 Real bugs → GitHub issue

Create a GitHub issue with:
- **Title:** `[Sparq Coach] {ticket_id} — {one-line summary}`
- **Body:** paste the full discord embed content (description + log tail + system info)
- **Labels:** `bug`, `sparq-coach-beta`, and severity: `p1-crash` / `p2-wrong-behavior` / `p3-cosmetic`
- **Milestone:** next planned release (e.g. `v2.0.6`)

When the fix is merged, the issue closes automatically via commit message `Fixes #{issue_number}`.

### 4.3 Responding to users

The user submitted their email at registration → it's on their Nutshell Contact.

**Standard response email (copy-paste template):**

```
Subject: Re: Your Sparq bug report [{ticket_id}]

Hi {user_name},

Thanks for reporting this — we received your report and are investigating.

[If user error:]
This is actually expected behavior: [explanation]. Here's how to [fix]:
[steps]

[If bug, fix is queued:]
We've confirmed this is a bug. It will be fixed in the next update (v2.0.x),
which we'll send to you directly.

[If bug, fix ships NOW:]
We've just released a fix. Please download the updated installer here:
[link] or simply replace Affilabs-Core.exe with the attached file.

Let me know if you run into anything else.

Lucia
Affinite Instruments
```

Send from your personal email or create a shared `support@affiniteinstruments.com` alias. Copy into Nutshell as an Activity on the Contact (log it for sales visibility).

### 4.4 Hotfix delivery

When the fix is ready:

1. Build a new `Affilabs-Core.exe` via PyInstaller
2. Attach directly to the support email (drop-in exe — no reinstall needed per SOFTWARE_UPDATE_DELIVERY_FRS.md)
3. Send to the specific customer email from Nutshell Contact

For multiple affected users: post in a `#beta-updates` Discord channel where all beta users are members, with a download link (Wix file or GitHub release).

### 4.5 Proactive outreach via Nutshell

Nutshell will accumulate Activities from every bug report and Coach Beta query. Review the Contact record when:
- A user has submitted 3+ bug reports (tag: `frequent-reporter` — add manually when you see it)
- A user has 0 Coach Beta queries after 2 weeks (may not know it exists)
- A user has the `struggling-user` tag (3 bad runs — per SPARQ_ACCOUNT_FRS §4.3)

In all cases: reach out proactively via the email on the Contact record. Sales team can see everything on the Contact without any extra briefing — the Activities tell the whole story.

---

## Summary Timeline

| Day | Deliverable |
|---|---|
| **Day 1** | SVG bug button, `SparqCoachService` skeleton, `send_bug_report_auto()` fallback path |
| **Day 2** | Wire bug flow in `spark_help_widget.py`, test fallback (draft mode, no Worker yet) |
| **Day 3** | Deploy Cloudflare Worker with `/sparq/bug`, set secrets, insert test key in KV |
| **Day 3** | End-to-end test: submit bug from app → Discord ping appears |
| **Day 4** | Nutshell Activity wiring in Worker, confirm activity logged on Contact |
| **Day 4** | Wix `/privacy` page (required before any beta user registers) |
| **Day 5** | Worker `/sparq/coach/beta/chat`, wire `ask_coach()` in widget, test Claude response |
| **Day 6** | Coach Beta button in sidebar, quota display |
| **Day 7** | Wix beta sign-up form → Nutshell via Zapier |
| **Day 7** | Internal test with one real device (`FLMT09792`) — full flow |
| **Week 2** | Ship to first beta customer |

The critical path is **Days 1–3**. Bug reporting works without the Claude chat. Chat is additive.

---

## Costs at Beta Scale (20 devices)

| Item | Cost |
|---|---|
| Cloudflare Worker + KV | **$0** (free tier) |
| Anthropic Claude Haiku | ~$0.05–0.30/day worst case if all devices use quota daily |
| Nutshell | Your existing plan |
| Discord | Free |
| Zapier (Wix → Nutshell) | Free tier (100 tasks/month) — enough for beta signups |

Total cloud cost: **under $10/month** for the first 20 beta devices.
