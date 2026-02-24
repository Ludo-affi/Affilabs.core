# Customer Data Review Service Plan

**Status:** Future work — validate demand before building
**Priority:** Low
**Target version:** Independent of Affilabs.core versioning
**Estimated effort:** 0 code (Phase A) → 4–6 weeks (Phase B if validated)

---

## Overview

A paid service where AffiNite Instruments customers submit their SPR data for expert review, quality assessment, and recommendations. Structured as three phases — start with zero infrastructure, only build if demand is proven.

---

## Phase A — Manual Review Service (Start Here)

**No code. No portal. Validate demand first.**

### How It Works

1. Customer exports their data from Affilabs.core (Excel or JSON)
2. Customer emails the file + a brief description of their experiment
3. You open it locally in Affilabs.core, review it, annotate cycles
4. You email back a PDF report with findings and recommendations
5. Customer pays before or after via Stripe payment link

### What You Review

- **Signal quality** — SensorIQ scores per channel, flag weak or noisy channels
- **Calibration quality** — FWHM, SNR, convergence iterations from calibration JSON
- **Cycle quality** — identify bad cycles, baseline drift, injection artifacts
- **Kinetics** — check KD fit quality, flag mass transport or rebinding artifacts
- **Recommendations** — surface cleaning, regeneration optimization, chip upgrade, flow rate adjustment, method changes

### Payment

- Stripe payment link on your website (no code — create in Stripe dashboard in 5 minutes)
- Suggested pricing: $150–300 per dataset review (1–2 hours of your time)
- Or: annual support subscription (~$500/year) that includes N reviews

### Infrastructure Needed

| Item | Action |
|------|--------|
| Stripe account | Create at stripe.com, add payment link to website |
| Email | Existing business email |
| Affilabs.core | Already installed — open their file locally |
| PDF report | Word/Google Docs template, export as PDF |

**Total setup time: 1–2 hours. Total cost: $0.**

---

## Go / No-Go Criteria for Phase B

Build Phase B (automated portal) only if:

- [ ] 5+ paying customers use Phase A within 3 months
- [ ] Manual review time exceeds 10 hours/month (worth automating)
- [ ] Customers ask for self-serve access or faster turnaround

If criteria are not met within 6 months, Phase B is not justified.

---

## Phase B — Automated Upload + Report Portal (If Validated)

### Stack

| Component | Tool | Cost/month |
|-----------|------|-----------|
| Portal UI | Streamlit (Python) | Free |
| Hosting | Railway | ~$5 |
| Auth | License key in localStorage | Free |
| Payments | Stripe (same account as Phase A) | 2.9% + $0.30/tx |
| Storage | Railway volume or S3 | ~$2 |
| DB | PostgreSQL on Railway | Free tier |

### What It Does

**Customer side:**
1. Logs in with license key at `portal.affiniteinstruments.com`
2. Uploads Affilabs.core Excel export
3. Sees automated quality report immediately (SensorIQ scores, flagged cycles, calibration summary)
4. Receives notification when manual review + recommendations are added
5. Downloads annotated report

**Your side (admin view):**
1. Email/Slack notification on new upload
2. Streamlit admin page — see customer data, automated flags, add manual annotations
3. Run re-analysis with different parameters if needed (same Python pipeline)
4. Mark as reviewed → customer notified

### Analysis Pipeline (Reuses Existing Code)

The Streamlit app imports directly from `affilabs/`:

```python
# portal/analysis.py
from affilabs.utils.sensor_iq import compute_sensor_iq
from affilabs.services.excel_exporter import parse_exported_excel
from affilabs.utils.export_helpers import load_calibration_json

def analyze_upload(file_path: str) -> dict:
    data = parse_exported_excel(file_path)
    iq_scores = {ch: compute_sensor_iq(data[ch]) for ch in data}
    return {
        "iq_scores": iq_scores,
        "flagged_cycles": find_bad_cycles(data),
        "calibration_summary": load_calibration_json(file_path),
    }
```

No duplication — the same analysis code that runs in the desktop app runs on the server.

### What "Execute Operations" Means in Phase B

You cannot remote-control their instrument — it's in their lab. But server-side you can:

| Operation | How |
|-----------|-----|
| Re-analyze with different baseline correction | Re-run pipeline with new params |
| Re-fit kinetics with corrected cycle selection | Pass updated cycle mask to fit function |
| Generate cleaned Excel report | Run `excel_exporter.py` server-side → customer downloads |
| Flag and annotate specific cycles | Store annotations in DB, render in report |

---

## Phase C — Full SaaS Portal (Only If Phase B Gets Traction)

Per-customer accounts, subscription billing, data history, async job queue, team access. Full engineering project — 4–6 months. Do not plan this until Phase B is running and revenue justifies it.

---

## Files Needed

### Phase A (no code)
- Stripe payment link (created in Stripe dashboard)
- PDF report template (Word/Google Docs)

### Phase B
| File | Purpose |
|------|---------|
| `portal/app.py` | Streamlit customer-facing upload + report view |
| `portal/admin.py` | Streamlit admin view for your review workflow |
| `portal/analysis.py` | Wrapper around existing affilabs/ analysis code |
| `portal/auth.py` | License key validation |
| `portal/Dockerfile` | Railway deploy |
| `portal/requirements.txt` | Streamlit + affilabs dependencies |

---

## Success Criteria

### Phase A
- [ ] Stripe payment link live on website
- [ ] First paying customer submits data and receives report
- [ ] 5 paying customers within 3 months → proceed to Phase B

### Phase B
- [ ] Customer can upload Excel export and receive automated quality report
- [ ] Admin can annotate and return recommendations without leaving the portal
- [ ] Payment gated — unauthenticated uploads rejected
- [ ] Re-analysis runs server-side using existing affilabs/ pipeline code
