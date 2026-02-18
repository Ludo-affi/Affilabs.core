# Product Requirements Documentation

This folder contains Product Requirements Documents (PRDs) for Affilabs.core features and technologies.

---

## 📋 PRD Index

| PRD | Status | Owner | Last Updated | Phase |
|-----|--------|-------|--------------|-------|
| [SPARQ_PRD.md](SPARQ_PRD.md) | 🟢 Active | Affinite | Feb 18, 2026 | Phase 1 Complete ✅, Phase 2 Planned |
| [LENSLESS_SPR_PRD.md](LENSLESS_SPR_PRD.md) | ✅ Complete | Affinite | Feb 18, 2026 | Retroactive Documentation (v2.0.5) |

---

## 🎯 PRD Status Guide

| Status | Meaning |
|--------|---------|
| 🟢 Active | Implementation in progress, PRD is current |
| 🟡 Draft | PRD being written, not yet finalized |
| 🔵 Planning | Future PRD, requirements gathering phase |
| ✅ Complete | Feature shipped, PRD archived as reference |
| 🔴 Blocked | Waiting on dependencies or decisions |

---

## 📝 PRD Template Structure

All PRDs follow this structure:

1. **Vision** — What problem does this solve?
2. **Product Scope** — Features and boundaries
3. **User Personas** — Who uses this?
4. **Requirements** — Functional + non-functional
5. **Technical Architecture** — How it's built
6. **Success Criteria** — How we measure success
7. **Out of Scope** — What we explicitly won't do
8. **Implementation Plan** — Phases and milestones

---

## 🔄 Task Tracking

### Sparq (Phase 1 ✅ Complete)

**Completed Tasks:**
- T1: Route Method Builder popup through SparkAnswerEngine ✅
- T2: Add 5 P4SPR KB articles ✅
- T3: Add 9 P4SPR patterns ✅
- T4: Add user_manager param to SparkHelpWidget ✅
- T5: Per-user Q&A history (JSON persistence) ✅
- T6: Method parameter validator enhancements ✅
- T7: Fix KB article accuracy ✅
- T8: Preset save suggestion ✅

**Next Phase (Phase 2 — Calibration Intelligence):**
- T9: Author 7 calibration KB articles (from docs/calibration/*.md)
- T10: Expand calibration patterns (3 → 15+)
- T11: Calibration wizard (interactive flow)
- T12: Real-time QC interpretation
- T13: Proactive recalibration reminders

---

## 📂 Related Documentation

- Technical specs: `docs/architecture/`
- Calibration docs: `docs/calibration/`
- User guides: `docs/user_guides/`
- Feature docs: `docs/features/`

---

## 🤝 How to Contribute

When creating a new PRD:

1. Create `{FEATURE_NAME}_PRD.md` in this folder
2. Add entry to PRD Index table above
3. Follow the PRD template structure
4. Link to related technical docs
5. Update task tracking if implementation starts

---

## 📧 Contact

- PRD questions: Lucia (OEM)
- Implementation status: Check git commits + CLAUDE.md
