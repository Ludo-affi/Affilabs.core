# Hardware Model UI Requirements — Affilabs.core v2.0.5

> **Purpose**: Every UI difference between hardware models in one place. Use this before touching any hardware-conditional code to avoid regressions.
> **Priority order**: P4SPR (1st) → P4PRO (2nd) → P4PROPLUS (3rd) → ezSPR / KNX2 (legacy, lowest)
> **Source files**: [`affilabs/ui_mixins/_device_status_mixin.py`](../../affilabs/ui_mixins/_device_status_mixin.py), [`affilabs/widgets/method_builder_dialog.py`](../../affilabs/widgets/method_builder_dialog.py), [`affilabs/sidebar_tabs/AL_flow_builder.py`](../../affilabs/sidebar_tabs/AL_flow_builder.py)

---

## Model Detection at Runtime

Hardware model is determined from the `status` dict returned by `HardwareManager` after connection. The key field is `ctrl_type`.

### `ctrl_type` values → Display names

```python
CONTROLLER_DISPLAY_NAMES = {
    "PicoP4SPR":    "P4SPR",
    "P4SPR":        "P4SPR",
    "PicoP4PRO":    "P4PRO",
    "P4PRO":        "P4PRO",
    "P4PROPLUS":    "P4PRO+",
    "PicoP4PROPLUS":"P4PRO+",
    "PicoEZSPR":    "P4PRO",   # PicoEZSPR hardware = P4PRO product
    "EZSPR":        "ezSPR",
    "ezSPR":        "ezSPR",
}
```

### Detection guards used in code

| Model | Code guard |
|-------|-----------|
| P4PROPLUS | `ctrl_type in ["P4PROPLUS", "PicoP4PROPLUS"]` |
| P4PRO | `ctrl_type in ["P4PRO", "PicoP4PRO", "PicoEZSPR"]` |
| P4SPR | `ctrl_type in ["P4SPR", "PicoP4SPR"]` |
| Has AffiPump | `status.get("pump_connected") and not is_p4proplus_internal` |

### AffiPump detection

`pump_connected = True` in the status dict means an external AffiPump is connected (P4SPR+AffiPump or P4PRO+AffiPump). For P4PROPLUS, `pump_connected` may be `True` for internal pumps — but `is_p4proplus_internal` guard prevents showing "AffiPump" label in that case.

---

## Model Comparison Matrix

| Feature | P4SPR | P4SPR + AffiPump | P4PRO | P4PROPLUS |
|---------|-------|-----------------|-------|-----------|
| Method mode | Manual only (locked) | Manual or Semi-Auto | Manual or Semi-Auto | Manual or Semi-Auto |
| 6-port valve | ❌ | ✅ (via AffiPump controller) | ✅ (controller-actuated) | ✅ (controller-actuated) |
| Pump controls | ❌ | AffiPump controls | AffiPump controls | Internal pump controls |
| Fluidics subunit | Hidden | Visible | Visible | Visible |
| "AffiPump" device label | ❌ | ✅ | ✅ | ❌ (internal pumps, not shown) |
| Flow mode availability | ❌ | ✅ post-calibration | ✅ post-calibration | ✅ post-calibration |
| Internal pump UI | ❌ | ❌ | ❌ | ✅ |
| Injection pairs | A, B, C, D (independent) | AC or BD (paired) | AC or BD (paired) | AC or BD (paired) |
| Channel layout | 4 independent fluidic | 2 fluidic (AC/BD) | 2 fluidic (AC/BD) | 2 fluidic (AC/BD) |

---

## Device Status Tab — Per Model

### Subunit rows

| Subunit row | P4SPR | P4PRO | P4PROPLUS |
|-------------|-------|-------|-----------|
| Sensor | ✅ visible | ✅ visible | ✅ visible |
| Optics | ✅ visible | ✅ visible | ✅ visible |
| Fluidics | ❌ hidden | ✅ visible | ✅ visible |

**Implementation**: `_set_subunit_visibility("Fluidics", visible)` called from `_update_subunit_readiness_from_status()`. Fluidics row shown only when `"fluidics_ready"` key is present in the status dict — P4SPR never sends this key.

### Device labels shown

| Config | Labels |
|--------|--------|
| P4SPR only | `● P4SPR` |
| P4SPR + AffiPump | `● P4SPR`, `● AffiPump` |
| P4PRO | `● P4PRO` |
| P4PRO + AffiPump | `● P4PRO`, `● AffiPump` |
| P4PROPLUS | `● P4PRO+` (no AffiPump shown) |
| P4SPR + KNX2 | `● P4SPR`, `● KNX` |

### "Add Hardware" button

Visible only when `ctrl_type` is known (i.e., controller is connected). Hidden when disconnected. Allows adding peripherals (AffiPump) after core controller connects.

---

## Method Tab — Per Model

### `mode_combo` (Manual / Semi-Automated)

Configured by `MethodBuilderDialog.configure_for_hardware(hw_name, has_affipump)`:

| Model | AffiPump | mode_combo options | Default | Enabled? |
|-------|----------|-------------------|---------|---------|
| P4SPR | No | `["Manual"]` | Manual | **Disabled** (locked) |
| P4SPR | Yes | `["Manual", "Semi-Automated"]` | Semi-Automated | Enabled |
| P4PRO | No | `["Manual", "Semi-Automated"]` | Semi-Automated | Enabled |
| P4PRO | Yes | `["Manual", "Semi-Automated"]` | Semi-Automated | Enabled |
| P4PROPLUS | — | `["Manual", "Semi-Automated"]` | Semi-Automated | Enabled |

**Label** (`hw_label` in dialog):
- P4SPR (no pump): `"P4SPR"`
- P4SPR + AffiPump: `"P4SPR + AffiPump"`
- P4PRO: `"P4PRO"` or `"P4PRO + AffiPump"` if pump present
- P4PROPLUS: `"P4PRO+"`

### Detection combo

Always defaults to `"Auto"` regardless of model. Not model-gated.

### Cycle type availability

All cycle types available on all models. Method mode (Manual vs Semi-Automated) controls what happens during execution, not what can be queued.

### Advanced settings frame

Shown/hidden via checkbox in MethodBuilderDialog — not model-gated.

---

## Flow Tab — Per Model

### Pump control section

| Control | P4SPR | P4PRO | P4PROPLUS |
|---------|-------|-------|-----------|
| Flow rate input | Hidden | Visible (AffiPump) | Hidden (preset only) |
| Volume input | Hidden | Visible (AffiPump) | Hidden |
| Prime button | Hidden | Visible | Visible (internal pump) |
| Start/Stop pump | Hidden | Visible | Visible |
| Internal pump preset | Hidden | Hidden | **Visible** |
| Synced pump container | Hidden | Hidden | Visible when synced checked |
| Individual pumps container | Hidden | Hidden | Visible when synced unchecked |

### Valve section

| Control | P4SPR | P4PRO | P4PROPLUS |
|---------|-------|-------|-----------|
| 6-port valve (Load/Inject) | Hidden | Visible | Visible |
| 3-way valve (Waste/Load) | Hidden | Visible | Visible |

### Internal pump controls (P4PROPLUS only)

Toggled by `_update_internal_pump_visibility()`:
- `synced_pump_container.setVisible(checked)` — synced mode: one flow rate for both pumps
- `individual_pumps_container.setVisible(not checked)` — independent control per pump

**P4PROPLUS constraints enforced in UI**:
- Minimum contact time: 180s at 25 µL/min — warn before starting if below this
- Flow rate: preset options only (not freely programmable)
- Direction: dispense only — no aspiration controls shown

---

## Operation Mode Availability

After connection, `_update_operation_modes(status)` determines which modes the sidebar shows as available:

```python
static_available = sensor_ready AND optics_ready   # True immediately after connection + verification
flow_available = status.get("flow_calibrated", False)  # True only after calibration completes
```

This calls `sidebar.set_operation_mode_availability(static_available, flow_available)`.

| State | Static indicator | Flow indicator |
|-------|-----------------|----------------|
| Disconnected | Unavailable (gray) | Unavailable (gray) |
| Connected, not calibrated | Available (if subunits ready) | Unavailable |
| Calibrated, no pump | Available | Unavailable |
| Calibrated, pump present | Available | Available |

---

## Injection Channel Pairing

This is a physical constraint of the fluidics, not a software choice:

### P4SPR

- 4 **independent** fluidic channels: A, B, C, D each have their own inlet
- User can inject different samples into each channel simultaneously (by hand, sequentially)
- Injection detection must tolerate **up to 15 seconds** of inter-channel timing skew (pipetting A→D takes time)
- Unused channels stay in buffer — no pairing required

### P4PRO / P4PROPLUS

- 4 optical channels but only **2 fluidic channels** addressable per injection
- Standard pairs: **AC** (channels A and C share one fluidic path) and **BD** (B and D share one)
- The 6-port valve routes sample to one pair at a time
- To inject different samples into AC vs BD: run two sequential injection cycles
- Non-standard pairs (AD, CB) possible but uncommon
- Injection detection per optical channel still works independently (each channel processes its own SPR data)

**UI implication**: When showing injection results or flags, P4PRO/PROPLUS users expect A and C to behave similarly (they received the same sample). Showing them grouped may be useful; treating them as 4 independent lines may be confusing.

---

## Rules for Hardware-Conditional Code

1. **Always use `ctrl_type` from the status dict** — never infer model from firmware version string alone.

2. **P4PROPLUS guard**: `ctrl_type in ["P4PROPLUS", "PicoP4PROPLUS"]` — both strings must be checked.

3. **AffiPump guard**: `status.get("pump_connected") and ctrl_type not in ["P4PROPLUS", "PicoP4PROPLUS"]` — P4PROPLUS has internal pumps that set `pump_connected=True` but must not show "AffiPump".

4. **Fluidics subunit**: Show only when `"fluidics_ready"` key is present in status dict — not based on `ctrl_type` directly. This makes it automatically correct when a new flow-capable model is added.

5. **Mode combo**: Call `configure_for_hardware(hw_name, has_affipump)` on MethodBuilderDialog when dialog opens — never hardcode mode options inside the dialog constructor.

6. **Injection timing tolerance**: Any injection detection algorithm must handle 0–15s inter-channel skew for P4SPR, and expect near-simultaneous triggers for P4PRO/PROPLUS AC/BD pairs.

7. **Internal pump minimum contact time**: 180s minimum at 25 µL/min for P4PROPLUS. Warn in the UI (not block) before starting. The firmware enforces it as a hard block — a user-facing warning before they hit the firmware error is better UX.

8. **Testing across models**: When changing any pump, valve, or flow control UI, verify behavior assumptions against all three models. P4SPR assumptions (no pump) will break P4PRO, and vice versa.

---

## Adding Support for a New Hardware Model

1. Add `ctrl_type` string(s) to `CONTROLLER_DISPLAY_NAMES` in `_device_status_mixin.py`
2. Add model-specific flow/pump visibility logic in `AL_flow_builder.py`
3. Add model entry to `configure_for_hardware()` in `method_builder_dialog.py`
4. Determine if Fluidics subunit should be visible (send `fluidics_ready` key in status dict)
5. Document the new model in this file under all relevant sections
6. Update the Model Comparison Matrix table at the top
