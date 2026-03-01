# IQ / OQ Implementation Plan

**Document status:** Planning — tests not yet implemented
**Created:** Feb 24 2026
**Updated:** Mar 1 2026 — binary deployment model added; customer protocol doc created
**Related:** [21CFR_PART11_GAP_ANALYSIS.md](21CFR_PART11_GAP_ANALYSIS.md)

## Published Documents

| File | Audience | Status |
|------|----------|--------|
| `docs/validation/IQ_OQ_PLAN_v2.0.5.html` | Internal (Affinite) — developer reference, implementation order, internal notes | ✅ Created Mar 1 2026 — **not for distribution** |
| `docs/validation/IQ_OQ_PROTOCOL_v2.0.5.html` | External — distributors, customers, auditors | ✅ Created Mar 1 2026 — **safe to share on request** |

> **Difference:** The internal plan includes implementation order, time estimates, and developer notes. The customer protocol is clean: test descriptions, pass criteria, signature blocks, and copyright footer only.

No hardware required for either IQ or OQ.
PQ (Performance Qualification, real hardware + real biology) is a separate effort documented elsewhere.

> **Implementation trigger:** Do NOT start implementing IQ/OQ scripts or OQ test suites until after a version freeze. The OQ report is only valid evidence against a specific, tagged release. Decision made Feb 24 2026 — freeze first, then implement.
>
> **Sequence:** feature complete → `git tag v2.x.x` → implement IQ/OQ against that tag → generate reports → ship to regulated customer.

---

## Binary Deployment Model (Academic / Field Customers)

When Affilabs.core is shipped as a **compiled Windows exe** (PyInstaller), the customer has no Python interpreter, no pytest, and no source tree. The OQ model changes as follows:

### Who runs OQ

| Scenario | Who runs OQ | How |
|----------|-------------|-----|
| Source install (internal / regulated site) | Affilabs or site IT | `python scripts/validation/oq_runner.py` against tagged source |
| Binary exe (academic researcher, demo unit) | **Affilabs only**, before shipping | Same runner, against the source that produced the exe |

**The end user never runs OQ.** They receive a pre-generated `OQ_report_v2.x.x.html` bundled with the installer as documentary evidence.

### What ships to the customer

```
Affilabs-Core-Setup-v2.x.x.exe      ← installer
OQ_report_v2.x.x.html               ← pre-generated OQ evidence (email / docs folder)
IQ_report_SERIAL_DATE.json          ← generated on first run by the exe itself (see below)
```

### IQ for binary installs

The full source-based IQ checks (IQ-001 to IQ-009) are replaced by a **slim embedded IQ** that runs automatically at first launch:

| Check ID | Description | Pass Criterion |
|----------|-------------|----------------|
| IQ-B-001 | Exe version string readable | `version.py` or `VERSION` frozen inside exe returns parseable semver |
| IQ-B-002 | Detector profiles present | ≥1 `.json` in `detector_profiles/` (bundled inside exe data) |
| IQ-B-003 | `user_profiles.json` present and valid | Parses as JSON, contains `"profiles"` key |
| IQ-B-004 | `settings/settings.py` importable | No `ImportError` from frozen bytecode |
| IQ-B-005 | OS check | Windows 10/11, x86-64 |

Output: `_data/validation/IQ_report_SERIAL_DATE.json` — written on first run, same schema as the source IQ report. Customer can email this to Affilabs for support triage.

### OQ evidence chain for a binary deployment

```
1. git tag v2.x.x
2. Run oq_runner.py on source → generates OQ_report_v2.x.x.html  (Affilabs)
3. Build exe from same tag    → Affilabs-Core-Setup-v2.x.x.exe
4. Ship exe + OQ report to researcher
5. Researcher runs exe → IQ_report auto-generated on first launch
6. Researcher archives: OQ_report (software tested) + IQ_report (installed correctly)
```

This gives a two-document evidence package for any academic or light-regulated use case, without requiring the researcher to run any scripts.

---

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
*Covers: FourierPipeline (production pipeline), dark subtraction, P/S ratio, Savitzky-Golay smoothing*
*Note: Only the Fourier pipeline is active in production. Centroid, polynomial, hybrid, consensus exist in code but are not used.*

| Req ID | Test | Pass Criterion |
|--------|------|----------------|
| OQ-SPR-001 | Fourier pipeline: known dip at 620 nm in synthetic spectrum | Returned wavelength within ±1.0 nm |
| OQ-SPR-002 | Fourier pipeline: dip at 640 nm (upper range) | Within ±1.0 nm |
| OQ-SPR-003 | Dark subtraction: dark spectrum subtracted before processing | Output < input at each pixel |
| OQ-SPR-004 | P/S ratio: S-pol reference divides into P-pol | Transmission values 0–200% |
| OQ-SPR-005 | Savitzky-Golay smoothing: noisy spectrum smoothed | Std dev of output < std dev of input |
| OQ-SPR-006 | Out-of-range wavelength returns graceful result, no crash | No unhandled exception |

*Synthetic data:* `create_synthetic_spr_spectrum(center_nm, noise_level)` — generates a numpy array with a Gaussian dip at `center_nm` over the 560–720 nm SPR window, sampled at USB4000 pixel spacing.

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

#### Suite 3 — Calibration & Signal Quality (OQ-CAL-*)
*Covers: CalibrationData domain model, baseline corrector, IQ score, ExperimentClock time conversions*
*Uses simulated spectra — no hardware*

| Req ID | Test | Pass Criterion |
|--------|------|----------------|
| OQ-CAL-001 | Servo position stored and retrieved correctly | Read-back == write value ±1 PWM unit |
| OQ-CAL-002 | S-pol reference capture: stored wavelength array length correct | Length == pixel count from detector profile |
| OQ-CAL-003 | `CalibrationData.__post_init__` rejects mismatched array lengths | `ValueError` raised |
| OQ-CAL-004 | `CalibrationData.__post_init__` rejects all-zero reference spectrum | `ValueError` raised |
| OQ-CAL-005 | Baseline correction (percentile): flat spectrum → transmission ≈ 100% | Median within ±2% of 100 |
| OQ-CAL-006 | Baseline correction (off_spr): non-SPR region used as reference | Output differs from uncorrected input |
| OQ-CAL-007 | IQ score: clean transmission (deep dip, low noise) → score ≥ 70 | Score in 70–100 |
| OQ-CAL-008 | IQ score: flat/noisy transmission (no dip) → score ≤ 30 | Score in 0–30 |
| OQ-CAL-009 | `ExperimentClock.convert(RAW → DISPLAY)` correct | `display = raw - display_offset` to within float precision |
| OQ-CAL-010 | `ExperimentClock.convert(RAW → RECORDING)` correct | `recording = raw - recording_offset` to within float precision |
| OQ-CAL-011 | `ExperimentClock` round-trip: RAW → DISPLAY → RAW | Returns original value ±1e-9 |

#### Suite 4 — Timeline, Flags & Injection Detection (OQ-TML-*)
*Covers: TimelineEventStream, CycleMarker, FlagManager*

| Req ID | Test | Pass Criterion |
|--------|------|----------------|
| OQ-TML-001 | `TimelineEventStream.append()` — event retrievable | `len(stream) == 1` |
| OQ-TML-002 | `CycleMarker` serialises to dict and back | Round-trip equality |
| OQ-TML-003 | `RecordingManager` creates `TimelineContext` on start | `_timeline_context is not None` |
| OQ-TML-004 | Injection flag emitted at correct timestamp | Flag `t` within ±0.1s of injection command time |
| OQ-TML-005 | Injection autodetection: synthetic step-change (rising 0.3 nm in 3 s) triggers detection | `injection_detected == True` within 5 s of step onset |
| OQ-TML-006 | Injection autodetection: slow drift (0.05 nm/s) does not trigger | `injection_detected == False` over 30 s |
| OQ-TML-007 | Delta SPR calculation: ΔSPR = peak − baseline cursor value | Result within ±0.001 nm of expected |
| OQ-TML-008 | Cycle dataclass serialises to dict and back | Round-trip equality on all fields |

#### Suite 5 — User & Configuration (OQ-CFG-*)

| Req ID | Test | Pass Criterion |
|--------|------|----------------|
| OQ-CFG-001 | `user_profiles.json` loads without error | List of profiles returned |
| OQ-CFG-002 | Detector profile loaded for `USB4000` | `pixel_count == 3648` |
| OQ-CFG-003 | `settings.py` constants importable | `from settings import *` — no `ImportError` |
| OQ-CFG-004 | `VERSION` parses as semver | `re.match(r"\d+\.\d+\.\d+", version)` |

*Note: Flame-T profile (`ocean_optics_flame_t.json`) exists on disk but Flame-T devices connect via the USB4000 driver — only the USB4000 profile is active at runtime. OQ-CFG-002 covers the only profile that matters.*

#### Suite 6 — Optical Fault Detection Algorithms (OQ-FLT-*)
*Covers: leak detector, air bubble detector — algorithm correctness with synthetic intensity/wavelength data*
*Hardware-free: inject synthetic data streams, verify the detection logic fires or stays silent correctly.*

| Req ID | Test | Pass Criterion |
|--------|------|----------------|
| OQ-FLT-001 | Leak detector: sustained intensity drop ≥ threshold triggers alert | `leak_detected == True` within N samples |
| OQ-FLT-002 | Leak detector: transient drop below threshold does not trigger | `leak_detected == False` (noise immunity) |
| OQ-FLT-003 | Leak detector: recovery after drop ≥ 50% baseline → `leak_resolved` | `leak_resolved == True` |
| OQ-FLT-004 | Air bubble detector: wavelength spike + transmittance dip triggers alert | `bubble_detected == True` |
| OQ-FLT-005 | Air bubble detector: normal wavelength variance does not trigger | `bubble_detected == False` |

*These test the algorithms (`affilabs/services/air_bubble_detector.py`, leak logic in `mixins/_acquisition_mixin.py`) against fabricated sensor data — no serial port, no Qt.*

---

## PQ — Performance Qualification (Hardware Required)

> **PQ is separate from IQ/OQ and requires a physically connected, primed device with fluid running.**
> PQ is not implemented in software — it is a documented manual procedure run by a lab technician.

### Fluidic PQ checks (manual procedure)

These checks require real hardware and cannot be simulated:

| Check ID | Description | Pass Criterion | How to run |
|----------|-------------|----------------|------------|
| PQ-FLD-001 | No baseline leak | Stable intensity for 5 min with PBS running | Observe Live tab — no leak alert, <5% intensity drift |
| PQ-FLD-002 | Squarewave injection response | Load the **"Squarewave QC" preset** in Method Builder and run it | Sensorgram shows clean step-up on inject, step-down on wash, for each of 3 cycles |
| PQ-FLD-003 | Contact time accuracy | Squarewave preset: 60 s contact time per cycle | Measured contact time (from injection flag to wash flag) within ±3 s of 60 s |
| PQ-FLD-004 | SPR baseline drift | 30-min PBS baseline | Drift < 50 RU over 30 min (≈ < 0.14 nm) |
| PQ-FLD-005 | Noise floor | Same 30-min window | Noise std < 10 RU (≈ < 0.028 nm) |

**Squarewave QC preset** — to be added to `affilabs/services/cycle_template_storage.py`: 3 identical cycles of `inject 60 s / wash 60 s / baseline 60 s` with PBS buffer, no analyte. Used to verify fluidic repeatability and timing accuracy.

The PQ procedure and acceptance report template will be documented in `docs/calibration/PQ_PROCEDURE.md` (to be created before first regulated shipment).

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
| `tests/oq/test_calibration_logic.py` | Suite 3 (CAL-*) — calibration domain model, baseline corrector, IQ score, ExperimentClock |
| `tests/oq/test_timeline_flags.py` | Suite 4 (TML-*) — timeline, flags, injection autodetection, ΔSPR math, Cycle serialisation |
| `tests/oq/test_configuration.py` | Suite 5 (CFG-*) — new file |
| `tests/oq/test_fault_detection.py` | Suite 6 (FLT-*) — leak + bubble detector algorithm tests |

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
3. `tests/oq/test_signal_processing.py` — Suite 1, Fourier pipeline only + dark/P/S/SG tests (1.5 hr)
4. `tests/oq/test_data_recording.py` — Suite 2, temp dir fixtures (2 hr)
5. `tests/oq/test_timeline_flags.py` — Suite 4, extend existing tests (1 hr)
6. `tests/oq/test_calibration_logic.py` — Suite 3, baseline corrector + IQ score + ExperimentClock (2.5 hr)
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
