# Sparq AI Upgrade Plan — RAG + Claude Haiku

**Status:** Future work
**Priority:** Medium
**Estimated effort:** 2–4 weeks (exe) + 1 week (relay server)
**Target version:** v2.1.0

---

## Background

Sparq currently runs a 2-layer hybrid system:
1. **Pattern matching** (`patterns.py`) — regex, ~1ms, deterministic
2. **Knowledge base search** (`knowledge_base.py`) — TinyDB full-text, ~50ms
3. **Keyword fallback** — always returns something, never crashes

TinyLM (local transformer) was removed in v2.0.5 due to 30+ second UI freezes on CPU with no GPU.

This plan upgrades Sparq to a 3-layer system adding **Claude Haiku via a hosted relay** as the final layer, only firing when layers 1 and 2 don't match with confidence.

---

## Architecture

```
User question
      │
      ▼
Layer 1: Pattern Matcher (~1ms)
  patterns.py — regex on 108KB of curated SPR patterns
  → if matched with high confidence: return immediately
      │
      ▼ (no confident match)
Layer 2: Knowledge Base Search (~50ms)
  knowledge_base.py — TinyDB vector/text search
  RAG: ChromaDB embeddings over curated SPR docs + FRS docs
  → if score > threshold: return grounded answer
      │
      ▼ (score below threshold)
Layer 3: AffiNite Relay → Claude Haiku (~500ms)
  Exe posts question + KB chunks to api.affiniteinstruments.com
  Relay validates license key, calls Anthropic with org key
  → returns generated answer, grounded in your docs
      │
      ▼
Response shown in Sparq sidebar
```

**Key principle:** Haiku only fires for genuinely novel questions. Common questions (calibration, acquisition, flow) are answered by layers 1–2 with zero relay cost.

---

## Phase 1 — SPR Knowledge Base (Week 1)

Build the curated content that powers both KB search and Haiku context injection.

### 1a — SPR Glossary (~200 terms)

Curate definitions for three term categories:

**Physics / Signal**
- Surface Plasmon Resonance, Kretschmann configuration, evanescent field
- Resonance wavelength, SPR dip, FWHM, transmission spectrum
- P-polarization, S-polarization, P/S ratio
- Baseline drift, refractive index unit (RIU), response unit (RU)
- Bulk refractive index effect, mass transport limitation, rebinding

**Kinetics / Binding**
- Association phase, dissociation phase
- kₐ (on-rate, M⁻¹s⁻¹), k_d (off-rate, s⁻¹), K_D (equilibrium dissociation constant)
- Rmax, kobs = ka×C + kd, Langmuir 1:1 binding model
- Heterogeneous ligand, avidity, cooperativity
- Equilibrium dissociation constant vs kinetic KD

**Experiment Workflow**
- Chip activation (EDC/NHS chemistry)
- Ligand immobilization, surface density
- Blocking (ethanolamine), reference channel subtraction, double referencing
- Running buffer, contact time, flow rate, injection volume
- Priming, equilibration, regeneration, stability test

**Hardware (Affilabs.core specific)**
- LED channel A/B/C/D, integration time, dark spectrum
- S-mode / P-mode calibration, servo polarizer, convergence
- Startup calibration, LED model, fiber optic
- Ocean Optics Flame-T / USB4000 spectrometer
- AffiPump, 6-port valve, KC1/KC2, P4SPR / P4PRO / P4PROPLUS

**Software (Affilabs.core specific)**
- Cycle, method, recording, Edits tab
- Sensorgram, binding plot, Langmuir fit, kinetics fit
- Demo mode (Ctrl+Shift+D), SensorIQ, ΔSPR, RU conversion (1nm = 355 RU)
- Simple LED calibration, startup calibration dialog, Sparq troubleshooting flow

### 1b — Q&A Pairs (~500 pairs)

Curated question → answer pairs organized by topic:

| Topic | Target pairs |
|-------|-------------|
| Calibration (startup, simple LED, polarizer) | 80 |
| Acquisition settings (integration time, LED intensity) | 60 |
| Binding analysis (Langmuir fit, kinetics, KD) | 80 |
| Hardware troubleshooting (timeout, saturation, weak channel) | 80 |
| Flow / pump control (AffiPump, valve, injection) | 60 |
| Export / recording | 40 |
| SPR physics (what is SPR, blue shift, P/S ratio) | 60 |
| Software navigation (tabs, buttons, shortcuts) | 40 |

**Format:** JSON, stored in `affilabs/data/sparq/knowledge/`

```json
{
  "id": "cal_001",
  "question": "Why did startup calibration fail?",
  "answer": "Common causes: water not filling the flow cell (check for air bubbles), LED intensity too low (run Simple LED Calibration first), servo not reaching S-position (check servo calibration). See the Sparq troubleshooting flow for guided diagnosis.",
  "tags": ["calibration", "startup", "troubleshooting"],
  "source": "frs:CALIBRATION_ORCHESTRATOR_FRS"
}
```

---

## Phase 2 — ChromaDB RAG Layer (Week 2)

Replace TinyDB full-text search in `knowledge_base.py` with semantic vector search.

### Dependencies to add to `pyproject.toml`

```toml
"chromadb>=0.4.0",
"requests>=2.31.0",
```

### Implementation: `knowledge_base.py` upgrade

```python
# affilabs/services/spark/knowledge_base.py

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

class SparkKnowledgeBase:
    def __init__(self):
        self._client = chromadb.PersistentClient(path=str(KB_PATH))
        self._ef = SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"   # 80MB, runs on CPU, no GPU needed
        )
        self._collection = self._client.get_or_create_collection(
            name="sparq_kb",
            embedding_function=self._ef,
        )

    def search(self, query: str, n_results: int = 3) -> list[dict]:
        results = self._collection.query(
            query_texts=[query],
            n_results=n_results,
        )
        return results["documents"][0]   # top-N chunks
```

**Embedding model:** `all-MiniLM-L6-v2` — 80MB, Apache 2.0 license, runs in ~20ms on CPU. No GPU required. Included via `sentence-transformers` package.

### Indexing the knowledge base

One-time indexing script (`scripts/build_sparq_kb.py`):
- Reads all Q&A JSON files from `affilabs/data/sparq/knowledge/`
- Reads all FRS docs from `docs/features/` and `docs/calibration/`
- Chunks into 200-token segments with 20-token overlap
- Embeds and stores in ChromaDB persistent store
- Re-run whenever knowledge base content changes

---

## Phase 3 — Claude Haiku via Hosted Relay (Week 3)

### Approach: AffiNite Relay Server

The Anthropic API key never ships in the exe. All Layer 3 queries go through AffiNite's own backend, which holds the key centrally.

```
Affilabs.core (exe)
    │
    │  HTTPS POST /sparq/ask
    │  { question, kb_chunks, device_serial }
    │  Header: X-License-Key: <customer license>
    ▼
api.affiniteinstruments.com  (AffiNite relay)
    │  validates license key
    │  calls Anthropic with AffiNite org key
    ▼
Anthropic API  (one org account, one key, full visibility)
    │
    ▼
Answer → back to exe → shown in Sparq sidebar
```

**Advantages over bundling a key in the exe:**

| | Bundled key | Hosted relay |
|--|---|---|
| Key exposure | In exe (extractable) | Never leaves AffiNite server |
| Revoke a customer | Can't | Block license key instantly |
| Update system prompt | Rebuild + redeploy exe | Edit server, live for all users |
| Usage analytics | None | Per-serial, per-question logs |
| Cost control | Per-exe spend cap | One account, one cap, full visibility |

**Relay server:** FastAPI, ~50 lines. Deploy on Railway / Render / Fly.io — $0–5/month at current fleet size.

**Org account:** Create at console.anthropic.com under AffiNite Instruments. Set hard monthly spend limit.

**License key:** Already shipped per customer. Sent as `X-License-Key` request header — relay validates before forwarding to Anthropic.

### Implementation: `answer_engine.py` — Layer 3

```python
# affilabs/services/spark/answer_engine.py

import requests

SPARQ_RELAY_URL = "https://api.affiniteinstruments.com/sparq/ask"

class SparkAnswerEngine:

    def _query_haiku(self, question: str, kb_chunks: list[str]) -> tuple[str, bool]:
        """Layer 3: relay to AffiNite backend → Claude Haiku."""
        if not SPARQ_RELAY_URL or not CUSTOMER_LICENSE_KEY:
            return "", False
        try:
            response = requests.post(
                SPARQ_RELAY_URL,
                headers={"X-License-Key": CUSTOMER_LICENSE_KEY},
                json={
                    "question": question,
                    "context_chunks": kb_chunks,
                    "device_serial": self._device_serial,
                },
                timeout=5.0,
            )
            if response.status_code == 200:
                answer = response.json().get("answer", "")
                return answer, bool(answer)
            return "", False
        except Exception:
            return "", False

    def generate_answer(self, question: str) -> tuple[str, bool]:
        # Layer 1: patterns
        answer, matched = self.pattern_matcher.match(question)
        if matched:
            return answer, True

        # Layer 2: KB search
        chunks = self.kb.search(question, n_results=3)
        answer, matched = self._kb_answer(question, chunks)
        if matched:
            return answer, True

        # Layer 3: relay → Haiku
        return self._query_haiku(question, chunks)
```

### Relay Server (separate repo, new microservice)

```python
# relay/main.py — FastAPI

@app.post("/sparq/ask")
async def sparq_ask(req: SparqRequest, x_license_key: str = Header(...)):
    if not license_db.is_valid(x_license_key):
        raise HTTPException(403, "Invalid license")

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)  # server env var only
    context = "\n\n".join(req.context_chunks) if req.context_chunks else ""
    user_msg = f"{req.question}\n\nRelevant context:\n{context}" if context else req.question

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=SPARQ_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return {"answer": message.content[0].text.strip()}
```

### Graceful Degradation

- Relay unreachable (offline / server down) → layers 1+2 only, no error shown to user
- HTTP timeout (>5s) → return KB fallback answer silently
- 403 invalid license → log silently, return pattern fallback
- Layers 1+2 always work fully offline — relay is additive only

---

## Phase 4 — Settings UI (Week 4)

Add to Settings → Sparq tab:

- **AI Mode** toggle: `Pattern + KB only` / `Full AI (Claude Haiku)`
- **Connection status**: "Sparq AI: connected" / "offline — using local KB"
- **Usage indicator**: "Sparq AI: X queries this session"

No API key field — key management is server-side only.

---

## File Changes Summary

### Exe (Affilabs.core)

| File | Change |
|------|--------|
| `affilabs/services/spark/answer_engine.py` | Add `_query_haiku()` via relay, upgrade `generate_answer()` |
| `affilabs/services/spark/knowledge_base.py` | Replace TinyDB with ChromaDB + sentence-transformers |
| `affilabs/data/sparq/knowledge/` | New directory — JSON Q&A pairs (500+ entries) |
| `settings/settings.py` | Add `SPARQ_RELAY_URL` + `CUSTOMER_LICENSE_KEY` constants |
| `affilabs/sidebar_tabs/AL_settings_builder.py` | Add Sparq AI settings section |
| `scripts/build_sparq_kb.py` | New — one-time KB indexing script |
| `pyproject.toml` | Add `chromadb`, `requests`, `sentence-transformers` |
| `_build/Affilabs-Core.spec` | Add ChromaDB data files to bundle |

### Relay Server (new repo)

| File | Purpose |
|------|---------|
| `relay/main.py` | FastAPI app — license validation + Anthropic call |
| `relay/license_db.py` | License key lookup (flat file or simple DB) |
| `relay/Dockerfile` | Container for Railway/Render/Fly.io deploy |

---

## Cost Model

| Scenario | Queries/month | Haiku calls | Cost/month |
|----------|--------------|-------------|------------|
| 1 unit in field | ~200 | ~60 (30% novel) | $0.06 |
| 10 units in field | ~2,000 | ~600 | $0.60 |
| 50 units in field | ~10,000 | ~3,000 | $3.00 |

Layers 1+2 handle ~70% of queries without any relay call. Cost is negligible at any realistic fleet size.

---

## What This Is NOT

- Not a fine-tuned model — no GPU training, no model weights to ship
- Not a general-purpose chatbot — Sparq stays instrument-focused
- Not always-on — Haiku only fires when pattern+KB don't have a confident answer
- Not a dependency on Anthropic uptime — instrument works fully offline without Haiku

---

## Success Criteria

- [ ] Sparq answers 95%+ of calibration questions correctly
- [ ] Sparq answers 90%+ of kinetics/binding questions correctly
- [ ] Layer 3 fires for <30% of queries (layers 1+2 handle the rest)
- [ ] No UI freeze — relay call is always async, response shown when ready
- [ ] Graceful offline operation — zero errors when no internet
- [ ] Monthly API cost <$10 at 50-unit fleet scale
- [ ] Relay: invalid license key returns 403, no Anthropic call made
