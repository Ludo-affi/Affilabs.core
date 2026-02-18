# Sparq AI Assistant — PRD

**Product**: Sparq (formerly "Spark") — embedded AI assistant in Affilabs.core
**Status**: In Progress
**Owner**: Lucia / Software Team
**Last Updated**: 2026-02-18

---

## Vision

Sparq is an intelligent, in-app AI assistant that helps users operate the SPR instrument, build methods, troubleshoot hardware, and interpret results — without leaving the application.

---

## Goals

1. Reduce time-to-first-experiment for new users
2. Surface contextual guidance at the right moment (during calibration, method building, etc.)
3. Enable voice interaction for hands-free lab operation
4. Grow into an active AI co-pilot (proactive alerts, pattern detection)

---

## Current State (v2.0.5)

- Pattern-based Q&A (regex matching against `patterns.py`)
- Categories: startup, calibration, method, pump, export, hardware, p4spr, analysis, general
- TinyLM integration for free-text answers beyond patterns
- Knowledge base stored in `data/spark/knowledge_base.json`
- Voice output via Piper TTS (optional, off by default)
- Voice toggle button in sidebar
- Lazy-loaded sidebar panel (no startup cost)
- Troubleshooting flow for weak-channel LED diagnosis

---

## Requirements

### Core

| # | Requirement | Priority | Status |
|---|-------------|----------|--------|
| 1 | Pattern-based Q&A for all instrument operations | High | Done |
| 2 | Free-text fallback (TinyLM / Claude API) | High | Done |
| 3 | Voice output (Piper TTS), off by default | Medium | Done |
| 4 | Sidebar UI, lazy-loaded | High | Done |
| 5 | Guided troubleshooting flows | Medium | Done |

### Near-Term (v2.0.6)

| # | Requirement | Priority | Status |
|---|-------------|----------|--------|
| 6 | Context-aware suggestions (knows current cycle, current state) | High | [ ] |
| 7 | Proactive alerts (e.g., "baseline drifting — run calibration?") | Medium | [ ] |
| 8 | `@spark` method template generation in Method Builder | High | [~] |
| 9 | Session memory (remember user preferences within session) | Low | [ ] |
| 10 | Persistent knowledge base updates (user-confirmed facts) | Low | [ ] |

### Future (v2.1+)

| # | Requirement | Priority | Status |
|---|-------------|----------|--------|
| 11 | Cloud AI tier (Claude API for premium users) | Medium | [ ] |
| 12 | Experiment analysis AI (summarize results, suggest next steps) | High | [ ] |
| 13 | Voice input (speech-to-text) | Low | [ ] |
| 14 | Multi-turn conversation memory | Medium | [ ] |
| 15 | Integration with Affilabs.data output for auto-reporting | High | [ ] |

---

## Architecture

```
User Input (text or voice)
    ↓
PatternMatcher (regex, patterns.py)
    ↓ (if no match)
KnowledgeBase lookup (knowledge_base.json)
    ↓ (if no match)
TinyLM / Claude API (free-text generation)
    ↓
Answer rendered in sidebar
    ↓ (optional)
Piper TTS (voice output)
```

**Key Files**:
- [affilabs/services/spark/patterns.py](../affilabs/services/spark/patterns.py) — All regex Q&A patterns
- [affilabs/services/spark/answer_engine.py](../affilabs/services/spark/answer_engine.py) — Answer generation
- [affilabs/services/spark/knowledge_base.py](../affilabs/services/spark/knowledge_base.py) — Knowledge retrieval
- [affilabs/services/spark/tinylm.py](../affilabs/services/spark/tinylm.py) — LM integration
- [affilabs/widgets/spark_help_widget.py](../affilabs/widgets/spark_help_widget.py) — UI widget
- [affilabs/widgets/spark_sidebar.py](../affilabs/widgets/spark_sidebar.py) — Sidebar shell

---

## Tasks

### Active
- [ ] Add context awareness: pass current app state into Sparq answer engine
- [ ] `@spark` templates: expand built-in protocol templates (amine coupling, kinetics, etc.)
- [ ] Proactive alert hook: connect to acquisition event coordinator

### Backlog
- [ ] Cloud AI tier design (auth, billing, API key management)
- [ ] Voice input (speech-to-text via faster-whisper or similar)
- [ ] Auto-generate analysis summary from experiment results
- [ ] Session memory model (what did the user ask this session)

---

## Success Metrics

- % of user questions answered without escalating to support
- Time from power-on to first recording (target: <5 min for new users)
- Voice usage rate (if enabled)
- User satisfaction score (NPS from in-app survey)
