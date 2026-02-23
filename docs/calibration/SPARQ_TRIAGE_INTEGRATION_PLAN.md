# Sparq + History-Triage Integration Plan
## Smarter Calibration Failure Guidance

*Status: Planned — not yet implemented*
*Last updated: 2026-02-22*

---

## Problem

Two calibration failure systems exist and don't talk to each other:

| System | Data source | Trigger | Output |
|--------|------------|---------|--------|
| **History triage** | `device_history.db` (`successful_calibrations` count) | Every failure, retry 0+ | Static text appended to error string: "N prior successes → likely water" or "never succeeded → contact support" |
| **Sparq guided flow** | `calibration_results/*.json` (recent signal counts vs historical avg) | Retry ≥ 2 AND `"D=19.2% (LED=255)"` pattern in error | Interactive: lights LED, asks "is paper wet?", then "is LED dimmer?", routes to water / LED degradation / fiber conclusions |

### Current gaps

1. **Sparq starts blind** — always runs the same `START → CHECK_WATER → CHECK_LED_BRIGHTNESS` path regardless of whether the device has 10 prior successes (almost certainly water) or has never calibrated (almost certainly hardware). The history triage already knows which branch is likely correct — but doesn't share it.

2. **Sparq only fires on retry ≥ 2 + weak-channel pattern** — if convergence fails for saturation, timeout, or any other reason, Sparq never opens, even though the history triage has a classification ready at retry 0.

3. **History triage fires early but guides nothing** — on retry 0 and 1, the user reads a text hint in the dialog and is then on their own. No interactive walkthrough.

4. **Wrong opening question on new devices** — Sparq always asks "is the paper wet?" as its first step. When `device_history.db` shows this device has zero successful calibrations, the water question is irrelevant — the issue is almost certainly hardware, fiber, or initial setup.

---

## Proposed Solution

Pass the history-triage classification into the `diagnosis` dict so Sparq can branch at `START` instead of always asking about water first.

### Three history tracks (from `_build_triage_message`)

| Track | Condition | Sparq opening |
|-------|-----------|--------------|
| **`known_good`** | `successful_calibrations ≥ 1` | Current flow unchanged: check water first, then LED brightness |
| **`never_calibrated`** | `total_calibrations == 0` (or no DB record) | Skip water. Open with hardware checklist: fiber, connections, power |
| **`consistently_failing`** | `total_calibrations ≥ 1`, `successful_calibrations == 0` | Skip water. Direct to support: offer to generate bug report with serial + error |

---

## Data Flow After Change

```
CalibrationService._on_calibration_failed_dialog()
  │
  ├── _check_weak_channel_diagnosis(error_message)
  │     → diagnosis dict  {channel, current_signal, current_led,
  │                        historical_avg, pct_of_historical}
  │
  ├── _query_calibration_history(self._triage_serial)   ← already called at emit time
  │     → DeviceStatistics | None
  │
  ├── _classify_history_track(history)                  ← NEW helper
  │     → 'known_good' | 'never_calibrated' | 'consistently_failing'
  │
  ├── diagnosis['history_track'] = track                ← NEW key injected
  ├── diagnosis['history_successes'] = N                ← NEW key (for message text)
  │
  └── _launch_spark_troubleshooting(diagnosis)
        └── spark_sidebar.push_troubleshooting(diagnosis, ctrl)
              └── spark_help_widget.start_troubleshooting_flow(diagnosis, ctrl)
                    └── __advance_troubleshooting_inner()
                          branches on diag.get('history_track', 'known_good')
```

---

## Files to Modify

| File | Change |
|------|--------|
| `affilabs/core/calibration_service.py` | Add `_classify_history_track(history)`; inject `history_track` + `history_successes` into diagnosis dict in `_on_calibration_failed_dialog` before calling `_launch_spark_troubleshooting` |
| `affilabs/widgets/spark_help_widget.py` | Branch `__advance_troubleshooting_inner` at `START` state on `history_track`; add two new state paths: `CHECK_HARDWARE` and `CONTACT_SUPPORT`; add handler methods |

No changes needed to: `spark_sidebar.py`, `spark_bubble.py`, `_launch_spark_troubleshooting`, `diagnose_weak_channel`, `_build_triage_message`.

---

## Implementation Detail

### Step 1 — `calibration_service.py`: `_classify_history_track()`

Add as a static method near `_build_triage_message`:

```python
@staticmethod
def _classify_history_track(history) -> str:
    """Classify device calibration history into a Sparq guidance track.

    Returns:
        'known_good'           — ≥1 prior success (water/optical path likely)
        'never_calibrated'     — no calibrations on record (setup/hardware)
        'consistently_failing' — calibrations attempted but none succeeded (OEM issue)
    """
    if history is None or history.total_calibrations == 0:
        return 'never_calibrated'
    if history.successful_calibrations == 0:
        return 'consistently_failing'
    return 'known_good'
```

### Step 2 — `calibration_service.py`: inject into diagnosis dict

In `_on_calibration_failed_dialog`, between `_check_weak_channel_diagnosis()` and `_launch_spark_troubleshooting()`:

```python
# Enrich diagnosis with history track for Sparq branching
history = self._query_calibration_history(getattr(self, '_triage_serial', None))
track = self._classify_history_track(history)
diagnosis['history_track'] = track
diagnosis['history_successes'] = (
    history.successful_calibrations if history else 0
)
```

### Step 3 — `spark_help_widget.py`: branch at `START`

Replace the unconditional `START` block in `__advance_troubleshooting_inner` with a three-way branch:

```python
if state == "START":
    track = diag.get('history_track', 'known_good')
    n_success = diag.get('history_successes', 0)

    if track == 'known_good':
        # Existing flow — water check is the right first step
        self.push_system_message(
            f"**Calibration failed — Channel {ch} signal is critically low.**\n\n"
            f"Channel {ch} at maximum LED brightness is producing only "
            f"**{diag['current_signal']:,.0f} counts** ({diag['pct_of_historical']:.0f}% of normal).\n\n"
            f"Historically this device calibrates successfully. "
            f"({n_success} prior successful calibration{'s' if n_success != 1 else ''} on record.)\n\n"
            f"Most likely cause: **water or debris in the optical path.**\n"
            f"I'm turning on LED {ch} at full brightness — check the paper test."
        )
        self._ts_state = "CHECK_WATER"
        # [LED on + QTimer.singleShot → _advance_troubleshooting as before]

    elif track == 'never_calibrated':
        self.push_system_message(
            f"**Calibration failed — Channel {ch} signal is critically low.**\n\n"
            f"This device has **no successful calibration history on record**. "
            f"This typically points to a setup or hardware issue rather than water.\n\n"
            f"Let's check the basics before anything else."
        )
        self._ts_state = "CHECK_HARDWARE"
        QTimer.singleShot(800, self._advance_troubleshooting)

    else:  # consistently_failing
        self.push_system_message(
            f"**Calibration failed — Channel {ch} signal is critically low.**\n\n"
            f"This device has attempted calibration before but has **never succeeded**. "
            f"This is unlikely to be water — it points to a persistent hardware issue.\n\n"
            f"I recommend contacting technical support. "
            f"I can generate a bug report with the full diagnostic details."
        )
        self._ts_state = "CONTACT_SUPPORT"
        QTimer.singleShot(800, self._advance_troubleshooting)
```

### Step 4 — `spark_help_widget.py`: new states

**`CHECK_HARDWARE` state** — interactive checklist for a never-calibrated device:

```python
elif state == "CHECK_HARDWARE":
    bubble = self.push_interactive_message(
        f"Check the following for Channel {ch}:\n\n"
        f"• Fiber cable seated at both ends\n"
        f"• LED connector firmly attached\n"
        f"• Detector USB connected and powered\n\n"
        f"**Have you checked all connections?**",
        ["Yes — all look good", "Found a loose connection"],
    )
    bubble.option_selected.connect(self._on_hardware_check_answer)
```

**`CONTACT_SUPPORT` state** — offer bug report for consistently-failing device:

```python
elif state == "CONTACT_SUPPORT":
    bubble = self.push_interactive_message(
        f"Would you like me to generate a support report?\n\n"
        f"It will include: device serial, error details, calibration history, "
        f"and a system log excerpt — ready to email to support.",
        ["Yes, generate report", "No thanks"],
    )
    bubble.option_selected.connect(self._on_contact_support_answer)
```

**Handler methods** (all lead to `DONE` or existing LED-check flow):

- `_on_hardware_check_answer(answer)`:
  - "Found a loose connection" → "Re-seat it and retry calibration. If still failing after reconnecting, contact support."  → `DONE`
  - "Yes — all look good" → transition to `CHECK_LED_BRIGHTNESS` (existing flow)

- `_on_contact_support_answer(answer)`:
  - "Yes, generate report" → call `self.start_bug_report_flow()` (already exists in `spark_help_widget.py`) → `DONE`
  - "No thanks" → "OK. Contact support at info@affiniteinstruments.com with your device serial if the issue persists." → `DONE`

---

## Backwards Compatibility

- `history_track` defaults to `'known_good'` via `diag.get('history_track', 'known_good')` — if the key is absent (DB unavailable, old code path) the flow is 100% identical to today.
- No changes to any external interface (`push_troubleshooting`, `start_troubleshooting_flow` signatures unchanged).
- `_query_calibration_history` is already wrapped in try/except — any DB failure degrades to `history=None` → `track='never_calibrated'` — an acceptable safe default (shows hardware checklist instead of water, which is conservative and correct for unknown devices).

---

## Validation

1. **Known-good device** (FLMT09788, which has successful calibrations): force a convergence failure → Sparq opens after retry 2 → opening message mentions prior successes and water → paper test question appears → flow continues as today ✅
2. **Never-calibrated device**: simulate by temporarily zeroing `successful_calibrations` in DB (or use a device serial not in DB) → Sparq opening skips water, shows hardware checklist → "found loose connection" → DONE ✅
3. **Consistently-failing device**: simulate by adding a DB record with `total=3, success=0` → Sparq opening goes straight to contact support offer → "Yes, generate report" → bug report flow activates ✅
4. **DB unavailable** (delete or rename `device_history.db`): `_query_calibration_history` returns None → track = `'never_calibrated'` → hardware checklist shown → no crash ✅
5. **Sparq fired without `history_track` key** (old code path): `diag.get('history_track', 'known_good')` → original water flow → no crash ✅

---

## What This Does Not Change

- The triage text in the error dialog (plain text "N prior successes → likely water") — remains as-is, still fires at retry 0
- The retry/max-retries logic — unchanged
- `diagnose_weak_channel` and `load_recent_successful_calibrations` — unchanged
- The Sparq flow for retry < 2 — Sparq still only opens at retry ≥ 2 (this is intentional — give the user a chance to self-resolve first)
- Bug report flow — reused, not duplicated

---

*Related doc: `STARTUP_CALIBRATION_TROUBLESHOOTING.md` §History-Based Failure Triage*
