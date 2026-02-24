# IQ / OQ Implementation Plan

**Document status:** Planning  
**Created:** Feb 24 2026  
**Related:** [21CFR_PART11_GAP_ANALYSIS.md](21CFR_PART11_GAP_ANALYSIS.md)

No hardware required for either IQ or OQ.  
PQ (Performance Qualification, real hardware + real biology) is a separate effort documented elsewhere.

> **Implementation trigger:** Do NOT start implementing IQ/OQ scripts or OQ test suites until after a version freeze. The OQ report is only valid evidence against a specific, tagged release. Decision made Feb 24 2026 — freeze first, then implement.
>
> **Sequence:** feature complete → `git tag v2.x.x` → implement IQ/OQ against that tag → generate reports → ship to regulated customer.

---

## IQ — Installation Qualification

### Purpose
Verify that Affilabs.core was installed completely and correctly on a given machine.
Produces a signed, timestamped JSON report that can be archived as evidence.

### What It Checks

| Check ID | Description | Pass Criterion |
|----------|-------------|----------------|
| IQ-001 | Python version | `>= 3.12`, `< 3.13` |
| IQ-002 | All required packages installed | Each entry in `pyproject.toml [dependencies]` importable at the pinned version |
| IQ-003 | Critical source modules importable | `affilabs.core`, `affilabs.services`, `affilabs.hardware`, `AffiPump` — no import errors |
| IQ-004 | `VERSION` file present and parseable | File exists, content matches `^\d+\.\d+\.\d+` |
| IQ-005 | Required config files present | `settings/settings.py`, `detector_profiles/*.json` (≥1), `user_profiles.json` |
| IQ-006 | Detector profile schema valid | Each `.json` in `detector_profiles/` contains required keys: `pixel_count`, `wavelength_range`, `integration_limits` |
| IQ-007 | `user_profiles.json` schema valid | Parses as JSON, contains `"profiles"` key, ≥1 entry |
| IQ-008 | No conflicting Qt installations | Only one Qt binding importable (`PySide6`; `PyQt5`/`PyQt6` must be absent) |
| IQ-009 | File integrity manifest | SHA-256 of each file in `affilabs/` matches `_build/file_manifest.json` (generated at build time) |
| IQ-010 | OS and architecture | Windows 10/11, x86-64 |

### Output

```
_data/validation/IQ_report_SERIAL_DATE_TIME.json
```

```json
{
  "report_type": "IQ",
  "software_version": "2.0.5 beta",
  "instrument_serial": "FLMT09788",
  "machine_hostname": "LAB-PC-01",
  "os": "Windows-11-10.0.22631",
  "python_version": "3.12.3",
  "timestamp_utc": "2026-02-24T14:32:00Z",
  "operator": "Lucia Noe",
  "checks": [
    {"id": "IQ-001", "description": "Python version", "result": "PASS", "detail": "3.12.3"},
    ...
  ],
  "overall": "PASS",
  "signature": null
}
```

`"signature"` field is null until e-signatures are implemented (Phase 11 of 21CFR work).
Overall is `"PASS"` only if all checks pass; any `FAIL` → `"FAIL"`.

### Implementation

**File:** `scripts/validation/iq_check.py`  
**Runner:** CLI — `python scripts/validation/iq_check.py --serial FLMT09788 --operator "Lucia Noe"`  
**Also triggered by:** NSIS installer post-install step (silent mode, auto-saves report)

**No Qt, no hardware, no display server required.** Must run headlessly.

---

## OQ — Operational Qualification

### Purpose
Verify that the software performs its designed functions correctly, using simulated data.
No hardware connection required. Builds on and extends the existing `tests/` pytest suite.

### Architecture

**Two layers:**

1. **Existing pytest tests** — tagged with requirement IDs using a custom `@req()` marker
2. **OQ runner** (`scripts/validation/oq_runner.py`) — runs pytest programmatically, collects results, generates a signed HTML + JSON report

### Requirement Tag System

```python
# conftest.py addition
import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "req(id): link test to OQ requirement ID")
```

```python
# Usage in any test file
@pytest.mark.req("OQ-SPR-001")
def test_centroid_pipeline_dip_position():
    ...
```

### OQ Test Suites

#### Suite 1 — Signal Processing (OQ-SPR-*)
*Covers: SpectrumProcessor, SpectrumPreprocessor, all 5 pipelines*

| Req ID | Test | Pass Criterion |
|--------|------|----------------|
| OQ-SPR-001 | Centroid pipeline: known dip at 620 nm in synthetic spectrum | Returned wavelength within ±1.0 nm |
| OQ-SPR-002 | Fourier pipeline: same input | Within ±1.0 nm |
| OQ-SPR-003 | Polynomial pipeline: same input | Within ±1.0 nm |
| OQ-SPR-004 | Hybrid pipeline: same input | Within ±0.5 nm |
| OQ-SPR-005 | Consensus pipeline: same input | Within ±0.5 nm |
| OQ-SPR-006 | Dark subtraction: dark spectrum subtracted before processing | Output < input at each pixel |
| OQ-SPR-007 | P/S ratio: S-pol reference divides into P-pol | Transmission values 0–200% |
| OQ-SPR-008 | Baseline correction (percentile): flat spectrum → ~100% transmission | Median within ±2% of 100 |
| OQ-SPR-009 | Savitzky-Golay smoothing: noisy spectrum smoothed | Std dev of output < std dev of input |
| OQ-SPR-010 | Out-of-range wavelength rejected | `ValueError` or graceful skip, no crash |

*Synthetic data:* `create_synthetic_spr_spectrum(center_nm, noise_level)` — already partially in `test_pipelines.py`, expand it.

#### Suite 2 — Data Recording (OQ-REC-*)
*Covers: RecordingManager, ExperimentIndex, Excel export*

| Req ID | Test | Pass Criterion |
|--------|------|----------------|
| OQ-REC-001 | `start_recording(filename=None)` — memory mode | No exception; `is_recording == True` |
| OQ-REC-002 | `start_recording(filename=path)` — file mode | File created on disk |
| OQ-REC-003 | `stop_recording()` — file mode | File exists, is valid Excel, contains `Sensorgram` sheet |
| OQ-REC-004 | `ExperimentIndex.append_entry()` — entry written | `experiment_index.json` contains new entry with correct `id` |
| OQ-REC-005 | `ExperimentIndex.search(keyword="test")` — returns matching entries | Result list length ≥ 1 |
| OQ-REC-006 | `ExperimentIndex.set_rating()` — rating persisted | Re-read entry has correct rating |
| OQ-REC-007 | `ExperimentIndex.add_tag()` + `remove_tag()` | Tag appears then disappears |
| OQ-REC-008 | Excel export: cycle table sheet columns present | `Cycle_Type`, `Start_Time_s`, `Delta_SPR_nm` present |
| OQ-REC-009 | Concurrent start/start raises or guards correctly | No data corruption |

#### Suite 3 — Calibration Logic (OQ-CAL-*)
*Covers: CalibrationService, SpectrumPreprocessor, servo position math*  
*Uses simulated spectra — no hardware*

| Req ID | Test | Pass Criterion |
|--------|------|----------------|
| OQ-CAL-001 | Servo position stored and retrieved correctly | Read-back == write value ±1 PWM unit |
| OQ-CAL-002 | S-pol reference capture: stored wavelength array length correct | Length == pixel count from detector profile |
| OQ-CAL-003 | LED boost correction applied: output != raw input | At least 1 pixel differs |
| OQ-CAL-004 | IQ score computed for a known synthetic transmission | Score in 0–100 range |
| OQ-CAL-005 | Calibration with mismatched array lengths raises, not crashes | `ValueError` or graceful failure logged |

#### Suite 4 — Timeline & Flags (OQ-TML-*)
*Covers: TimelineEventStream, CycleMarker, FlagManager*

| Req ID | Test | Pass Criterion |
|--------|------|----------------|
| OQ-TML-001 | `TimelineEventStream.append()` — event retrievable | `len(stream) == 1` |
| OQ-TML-002 | `CycleMarker` serialises to dict and back | Round-trip equality |
| OQ-TML-003 | `RecordingManager` creates `TimelineContext` on start | `_timeline_context is not None` |
| OQ-TML-004 | Injection flag emitted at correct timestamp | Flag `t` within ±0.1s of injection command time |

#### Suite 5 — User & Configuration (OQ-CFG-*)

| Req ID | Test | Pass Criterion |
|--------|------|----------------|
| OQ-CFG-001 | `user_profiles.json` loads without error | List of profiles returned |
| OQ-CFG-002 | Detector profile loaded for `Flame-T` | `pixel_count == 2048` |
| OQ-CFG-003 | Detector profile loaded for `USB4000` | `pixel_count == 3648` |
| OQ-CFG-004 | `settings.py` constants importable | `from settings import *` — no `ImportError` |
| OQ-CFG-005 | `VERSION` parses as semver | `re.match(r"\d+\.\d+\.\d+", version)` |

### OQ Report Output

```
_data/validation/OQ_report_DATE_TIME.html   ← human-readable, printable
_data/validation/OQ_report_DATE_TIME.json   ← machine-readable, archivable
```

HTML report sections:
- Header: software version, date, operator, overall PASS/FAIL
- Summary table: suite name, pass count, fail count, skip count
- Detail table: each test — req ID, description, result, duration, failure message if any
- Footer: `"This report was generated automatically by Affilabs.core OQ Runner v{version}"`

### Implementation Files

| File | Purpose |
|------|---------|
| `scripts/validation/iq_check.py` | IQ runner — headless, CLI |
| `scripts/validation/oq_runner.py` | OQ runner — invokes pytest, collects results, generates report |
| `scripts/validation/report_generator.py` | Shared HTML + JSON report builder |
| `scripts/validation/_manifest_builder.py` | Build-time: walks `affilabs/`, computes SHA-256 per file, writes `_build/file_manifest.json` |
| `tests/conftest.py` | Add `@req()` marker + `--oq-report` pytest option |
| `tests/oq/test_signal_processing.py` | Suite 1 (SPR-*) — new file |
| `tests/oq/test_data_recording.py` | Suite 2 (REC-*) — new file |
| `tests/oq/test_calibration_logic.py` | Suite 3 (CAL-*) — new file |
| `tests/oq/test_timeline_flags.py` | Suite 4 (TML-*) — extends existing `test_recording_manager_timeline.py` |
| `tests/oq/test_configuration.py` | Suite 5 (CFG-*) — new file |

---

## Build-Time Step: File Manifest

The IQ file integrity check (IQ-009) requires a manifest generated at build time:

```python
# scripts/validation/_manifest_builder.py
# Run as part of PyInstaller build — generates _build/file_manifest.json
# { "affilabs/core/recording_manager.py": "sha256:abcd1234...", ... }
```

Add to `_build/Affilabs-Core.spec` as a pre-build hook.

---

## Implementation Order

1. `conftest.py` — add `@req()` marker (30 min)
2. `tests/oq/test_configuration.py` — Suite 5, all easy (1 hr)
3. `tests/oq/test_signal_processing.py` — Suite 1, expand existing `test_pipelines.py` (2 hr)
4. `tests/oq/test_data_recording.py` — Suite 2, temp dir fixtures (2 hr)
5. `tests/oq/test_timeline_flags.py` — Suite 4, extend existing tests (1 hr)
6. `tests/oq/test_calibration_logic.py` — Suite 3, needs synthetic data helpers (2 hr)
7. `scripts/validation/report_generator.py` — HTML + JSON builder (2 hr)
8. `scripts/validation/oq_runner.py` — pytest invoker + report wiring (1 hr)
9. `scripts/validation/iq_check.py` — all IQ checks + report output (2 hr)
10. `scripts/validation/_manifest_builder.py` — build-time manifest (1 hr)

**Estimated total:** ~14 hrs of focused implementation

---

## Key Constraints

- **IQ and OQ must run with no hardware connected** — any test touching real serial/USB ports is PQ, not OQ
- **No Qt event loop in OQ tests** — test business logic only; widget tests are integration tests, separate
- **OQ tests must be deterministic** — no random seeds, no time-dependent assertions without mocking
- **Temp directories** — all file-writing tests use `tmp_path` (pytest fixture); never write to the real `_data/` folder during OQ
- **IQ manifest** — `_build/file_manifest.json` must be regenerated on every release build; stale manifest = IQ-009 FAIL
