# 21 CFR Part 11 Compliance — Gap Analysis

**Assessed:** Feb 24 2026  
**Assessor:** GitHub Copilot (Claude Sonnet 4.6)  
**Current compliance level:** ~15–20%

21 CFR Part 11 governs electronic records and electronic signatures in FDA-regulated environments.
Affilabs.core targets biopharma/CRO customers who may be subject to this regulation.

---

## What Is Already In Place (Partial Credit)

| Requirement | Current State | Gap |
|-------------|--------------|-----|
| Unique user IDs | `user_profiles.json` — per-user identity exists | No authentication (no password, no lockout) |
| Record retention | Excel files saved to disk per recording session | Files are editable outside the app — not tamper-evident |
| Timestamps | Events timestamped via `flag_manager` + `timeline` | No verified/synchronized time source (NTP); clock can be changed |
| Operational event log | `event_logged` signal + `RecordingManager` | This is telemetry, not a compliance audit trail |
| Data traceability | `ExperimentIndex` links recordings to calibrations | Not cryptographically protected |

---

## What Is Missing (Hard Gaps)

### §11.10(a) — Validation
- **Gap:** No IQ/OQ/PQ documentation exists as structured protocols
- **Effort:** High (process, not code)
- **Action:** Write Installation Qualification, Operational Qualification, Performance Qualification protocols; run them on each release build
- **Plan:** See [IQOQ_PLAN.md](IQOQ_PLAN.md) — full IQ check list (10 checks) and OQ test suite plan (5 suites, 28 req IDs) documented

### §11.10(b) — Record Integrity (legible, accurate copies)
- **Gap:** Excel files can be opened and overwritten by any user outside the app
- **Effort:** Medium
- **Action:** SHA-256 hash each exported Excel at creation time; store hash in `ExperimentIndex`; verify on load; warn/block if hash mismatches

### §11.10(c) — Record Retention & Protection
- **Gap:** No automated backup; no write-once-equivalent
- **Effort:** Medium
- **Action:** Auto-copy completed recordings to a designated archive folder on recording stop; mark archived files read-only (Windows ACL); log archive event

### §11.10(d) — System Access (Authentication)
- **Gap:** `user_profiles.json` has names but no passwords, no session timeout, no account lockout
- **Effort:** Medium
- **Action:** Add bcrypt-hashed passwords to user profiles; enforce login on app start; lock account after N failed attempts; auto-logout after idle timeout

### §11.10(e) — Audit Trail
- **Gap:** No tamper-evident, attribute-level audit trail exists anywhere
- **Effort:** High — this is the largest single gap
- **Action:** Create `affilabs/services/audit_log.py` — append-only SQLite DB with rows: `(id, timestamp_utc, user_id, action, record_id, field, old_value, new_value, row_hash)`. Each row's `row_hash = SHA256(prev_hash + row_data)` — chained hashing makes retroactive tampering detectable. Cover: record creation, notes edits, rating changes, tag changes, delta SPR cursor placement, export events, login/logout

### §11.10(f) — Operational System Checks
- **Gap:** No sequence enforcement (e.g. operator must complete step before reviewer can sign)
- **Effort:** Medium
- **Action:** Role-based workflow states on `ExperimentIndex` entries: `draft → submitted → reviewed → approved`

### §11.10(g) — Authority Checks (Role-Based Access Control)
- **Gap:** All users have equal access to all functions; no operator/supervisor/admin distinction
- **Effort:** High
- **Action:** Add `role` field to user profiles (`operator` / `reviewer` / `admin`); gate destructive actions (delete, overwrite, export) behind role checks; gate approval workflow behind `reviewer`+

### §11.10(h) — Device Checks
- **Gap:** No check that the instrument serial matches the user's assigned instrument
- **Effort:** Low
- **Action:** Record `instrument_serial` in user profile; warn if connected instrument doesn't match assigned instrument

### §11.10(i) — Training
- **Gap:** No training records in the system
- **Effort:** Low (mostly process)
- **Action:** `user_profiles.json` training completion field + date; blocked from recording until flagged trained by admin

### §11.50 / §11.70 — Electronic Signatures
- **Gap:** No e-signature capability anywhere
- **Effort:** High
- **Action:** E-signature = user re-enters password + selects meaning (`"I approve this record"`) + timestamp; binding recorded in audit trail linked to specific `entry_id`; signed records show signature panel in Edits metadata and Notes preview

---

## Recommended Implementation Order

> Do these in order — each builds on the previous.

1. **Password authentication** (`user_profiles.py` → bcrypt, login dialog, session)
2. **Audit trail service** (`audit_log.py` — append-only SQLite, chained SHA-256)
3. **Record integrity hashing** (SHA-256 on Excel at export; verify on load)
4. **Reason-for-change capture** (modal on any record edit in Notes/Edits)
5. **Role definitions + access gating** (`role` in profiles; decorator-based guards)
6. **Record archive / write-protect** (auto-copy on recording stop; read-only flag)
7. **Electronic signatures** (re-auth dialog; binding in audit trail)
8. **Audit trail review UI** (filterable table: who/what/when; export to PDF)
9. **Validation protocols** (IQ/OQ/PQ documents — process work, not code)

---

## Architectural Notes

- **Audit trail must be separate from `ExperimentIndex`** — different file, different writer, never modified after write
- **Chained hashing pattern:** `row_hash[n] = SHA256(row_hash[n-1] + canonical_json(row[n]))` — verifiable without a signing key
- **Platform:** SQLite for the audit DB (same as `device_history.db`); `audit_log.db` in a protected system folder, not the user's data folder
- **Import constraint:** `audit_log.py` must be importable without Qt (same rule as `experiment_index.py`)
- **Do not use the existing `event_logged` / `flag_manager` infrastructure for compliance audit** — those are operational telemetry and are mutable. The compliance audit trail must be a separate, append-only store

---

## Files That Will Be Created/Modified

| File | Action |
|------|--------|
| `affilabs/services/audit_log.py` | New — append-only SQLite audit trail |
| `affilabs/services/auth_service.py` | New — bcrypt password auth, session management |
| `affilabs/dialogs/login_dialog.py` | New — login UI |
| `affilabs/dialogs/esignature_dialog.py` | New — e-signature re-auth + meaning selection |
| `affilabs/dialogs/audit_viewer_dialog.py` | New — filterable audit trail table |
| `user_profiles.json` | Modify — add `role`, `password_hash`, `training_complete`, `instrument_serial` |
| `affilabs/services/experiment_index.py` | Modify — emit audit events on all mutations |
| `affilabs/services/excel_exporter.py` | Modify — compute + store SHA-256 hash on export |
| `settings/settings.py` | Modify — add compliance feature flags (`CFR11_MODE = False` default) |

---

## Feature Flag Strategy

All Part 11 features should be gated behind `CFR11_MODE = True` in `settings.py`.
When `False` (default for research/non-regulated customers), the app behaves exactly as today.
When `True`, authentication, audit trail, and signature requirements are enforced.
This avoids breaking the existing user experience for non-regulated customers.
