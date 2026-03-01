# Polarizer Shield Position FRS
## Barrel Polarizer Back-Position as Optical Shutter

**Version:** 1.0
**Date:** 2026-02-28
**Subsystem:** Optical Fault Protection / Servo Polarizer
**Depends on:** OPTICAL_FAULT_DETECTION_FRS.md, CALIBRATION_ORCHESTRATOR_FRS.md
**Source files (to implement):**
- `calibrations/servo_polarizer/calibrate_polarizer.py` — shield position detection
- `affilabs/utils/device_configuration.py` — store `servo_shield_position`
- `affilabs/utils/hal/controller_hal.py` — `move_to_shield()` method
- `mixins/_acquisition_mixin.py` — invoke shield on confirmed leak

---

## 1. Concept

A barrel polarizer has **two transmission windows** separated by opaque barrel walls.
Between and behind the windows, the barrel material blocks light — extinction is close to dark current.

```
Barrel cross-section (viewed from fiber end):

       PWM 0 ─────────────────────────── PWM 255
       ────────────────────────────────────────
        DARK  [  S-window  ]  DARK  [  P-window  ]  DARK
              ↑            ↑        ↑             ↑
            s_stable    s_stable  p_stable    p_stable
              min          max     min           max
```

The **shield position** is the point on the barrel **furthest from both windows** — i.e., the back of the barrel, where the opaque material is thickest and transmission is at a minimum. This position acts as a physical optical shutter.

**Use case:** When a liquid leak is confirmed (water on optical path), rotating to the shield position:
1. Blocks light at source — no photons reach the sensor
2. Prevents water from degrading the SPR measurement during the fault
3. Protects the optical interface from repeated strong illumination during a wet event
4. Signals clearly to the system (and user) that the instrument is in protective mode

---

## 2. Geometry: Finding the Shield Position

### 2.1 Barrel layout on the PWM axis

After servo calibration, we have:
- `s_stable_range = (s_min, s_max)` — S-window stable region
- `p_stable_range = (p_min, p_max)` — P-window stable region
- `s_pwm` — optimal S position (center of S stable range)
- `p_pwm` — optimal P position (center of P stable range)

Both windows are on the **same half** of the barrel (0–255 PWM range wraps at 256 ≡ 0). The two dark regions are:
1. **Between-window gap** — the dark region between S and P (smaller gap, ~30–90 PWM wide)
2. **Back region** — the dark region behind both windows (larger gap, the "far side")

### 2.2 Finding the between-window gap center

```python
gap_center = (min(s_pwm, p_pwm) + max(s_pwm, p_pwm)) / 2
```

This is **not** the shield position — it is between the windows and corresponds to partial transmission.

### 2.3 Finding the shield (back) position

The back of the barrel is the point on the PWM axis that is **furthest from both windows**, i.e., maximises `min(distance_to_S, distance_to_P)` on the circular (mod 256) axis.

```python
def find_shield_position(s_pwm: int, p_pwm: int) -> int:
    """Return PWM position at the back of the barrel.

    The back is the point on the circular [0, 255] axis that maximises
    the minimum circular distance to both S and P windows.
    That point is diametrically opposite the midpoint of the two windows.
    """
    mid = (s_pwm + p_pwm) / 2.0
    shield = (mid + 128) % 256   # 128 PWM ≈ 90° (half rotation)
    return int(round(shield))
```

**Visual example** (FLMT09792: S=65, P=231):
```
S=65, P=231 → mid = 148 → shield = (148 + 128) % 256 = 20

PWM axis (circular):
  0    65    128   148   231   256(=0)
  |--S--|     |--gap--|---P---|--shield--|
  ↑                              ↑
 S=65                         shield≈20 (= 276%256)
```

> **Edge case:** if `shield` lands within 20 PWM of either window, shift it by ±30 PWM away from the nearest window. This shouldn't happen for correctly calibrated barrel devices (S/P are ≥60 PWM apart, so back region is ≥60 PWM wide), but add the guard for robustness.

### 2.4 Verification at calibration time

After computing the shield position, measure it optically during servo cal to confirm it is at or near dark current:

```python
expected_dark = dark_current    # From stage1 measurement
shield_signal = measure_signal(shield_pwm)
shield_is_dark = (shield_signal < dark_current * 4.0)  # ≤4× dark = valid shutter
```

If `shield_is_dark` is False (shield position transmits too much light), log a warning and **do not use** the shield feature — the barrel geometry is unusual. The device still calibrates normally; shield protection is silently disabled.

---

## 3. Data Storage

### 3.1 device_config.json — new field

Add to the `hardware` section:

```json
"hardware": {
    "servo_s_position": 65,
    "servo_p_position": 231,
    "servo_shield_position": 20,      ← NEW
    "servo_shield_verified": true,    ← NEW: confirmed dark at calibration time
    ...
}
```

`servo_shield_position: null` means shield is not available for this device (non-barrel, or barrel with unusual geometry).

### 3.2 DeviceConfiguration

- `get_servo_shield_position() -> int | None` — returns `hardware.servo_shield_position`, or `None`
- `set_servo_shield_position(pwm: int, verified: bool)` — writes both fields + updates `last_modified`

---

## 4. Controller HAL — new command

Add to `ControllerHAL` protocol and all adapters (`P4SPRAdapter`, `PicoEZSPRAdapter`, `PicoP4PROAdapter`):

```python
def move_to_shield(self) -> bool:
    """Move servo to shield (back-of-barrel) position.

    Only valid for barrel polarizers with a verified shield position.
    Moves servo to stored shield PWM using direct servo_move_raw_pwm().
    Returns True if the move command was sent; False if no shield position available.
    """
```

Implementation in `P4SPRAdapter`:
```python
def move_to_shield(self) -> bool:
    shield_pwm = self._device_config and self._device_config.get_servo_shield_position()
    if shield_pwm is None:
        logger.warning("move_to_shield: no shield position for this device")
        return False
    logger.info(f"Moving servo to shield position: PWM {shield_pwm}")
    return self.servo_move_raw_pwm(shield_pwm)
```

---

## 5. Leak Protection Flow

### 5.1 State machine integration

Extends the existing leak state machine in `_acquisition_mixin.py`:

```
NORMAL
  ↓ (raw_peak drops < 25% baseline for ≥3s)
LEAK_CONFIRMED
  → emit spark alert ("Leak detected — shielding optical path")
  → ctrl.move_to_shield()           ← NEW
  → pause acquisition
  → set _shielded = True
  ↓ (user resolves leak, raw_peak ≥ 50% baseline not possible while shielded)
  ↓ (user clicks "Resume" / Sparq sends resume command)
RECOVERING
  → ctrl.set_mode("s")              (move back to S position)
  → run quick LED recal
  → resume acquisition
  → _shielded = False
NORMAL
```

### 5.2 Recovery trigger (user-initiated)

While shielded, the detector is blocked — automatic recovery detection cannot work (signal will always be dark). Recovery is **user-initiated**:

1. Sparq bubble shows: *"Optical path protected (servo shielded). Once the leak is resolved and the flow cell is dry, click 'Resume' to re-open the shutter and recalibrate."*
2. User clicks **Resume** button (same button as used for pause/resume, or a dedicated "Unshield" button in the Sparq bubble action bar).
3. App calls `ctrl.set_mode("s")` → runs quick LED recal → resumes acquisition.

> **Do not** attempt automatic unshielding based on signal level — signal will always read dark current while shielded, making it impossible to detect recovery automatically.

### 5.3 Guard: shield only on confirmed leaks

Shield moves are **only triggered** when ALL of:
- `_leak_alerted[ch]` is True (confirmed leak, not just a transient dip)
- `device_config.get_servo_shield_position()` is not None
- `hardware.servo_shield_verified` is True
- Acquisition is currently running (not already stopped/paused by user)

Do not shield during air bubble events — air bubbles are transient (typically <5s). Shield is reserved for liquid leaks which require user intervention.

---

## 6. Servo Calibration Integration

### 6.1 When to compute shield position

At the end of `run_servo_calibration_from_hardware_mgr()`, after S/P positions are validated and saved:

```python
# Compute shield position
shield_pwm = find_shield_position(s_pwm=refinement["s_pwm"], p_pwm=refinement["p_pwm"])

# Verify optically
shield_signal = measure_signal(ctrl, usb, shield_pwm, integration_ms=5.0, led_intensity=led_intensity)
shield_verified = (shield_signal < dark_current * 4.0)

if shield_verified:
    print(f"✅ Shield position: PWM {shield_pwm} — signal {shield_signal:.0f} counts (dark ✓)")
else:
    print(f"⚠️  Shield position PWM {shield_pwm} transmits too much ({shield_signal:.0f} counts) — disabled")
    shield_pwm = None

# Save alongside S/P
profile_mgr.update_device_config({
    **polarizer_results,
    "shield_position": shield_pwm,
    "shield_verified": shield_verified,
}, serial_number=serial_number)
```

Only barrel polarizers compute shield position. For CIRCULAR polarizers, there is no dark region → `shield_pwm = None`, `shield_verified = False`.

### 6.2 update_device_config extension

`DeviceProfileManager.update_device_config()` must also write `servo_shield_position` and `servo_shield_verified` when present in `polarizer_results`.

---

## 7. OEM Calibration Output (device_config.json — populated example)

```json
"hardware": {
    "servo_s_position": 65,
    "servo_p_position": 231,
    "servo_shield_position": 20,
    "servo_shield_verified": true,
    "polarizer_type": "barrel"
}
```

```json
"polarizer": {
    "s_position": 65,
    "p_position": 231,
    "shield_position": 20,
    "shield_verified": true,
    "sp_ratio": 2.111,
    "shield_signal_counts": 2180,
    "dark_current_counts": 2100,
    ...
}
```

---

## 8. Non-Goals

- **No autonomous unshielding** — shield removal is always user-triggered.
- **No shield for circular polarizers** — they have no dark region; all positions transmit.
- **No shield for P4PRO / P4PROPLUS** — those systems are flow-controlled; leak response is pump-stop not servo-park.
- **No change to injection detection** — shield has no effect on the injection auto-detection algorithm.

---

## 9. Implementation Order

1. `find_shield_position()` utility function + `verify_shield_position()` — standalone, testable
2. `device_configuration.py` — `get/set_servo_shield_position()`
3. `oem_calibration_tool.py` — extend `update_device_config()` to accept shield fields
4. `calibrate_polarizer.py` — call shield detection at end of barrel cal
5. `controller_hal.py` — `move_to_shield()` on all adapters
6. `_acquisition_mixin.py` — invoke shield on confirmed leak, add `_shielded` flag, adapt recovery flow
7. `spark_bubble.py` / `spark_help_widget.py` — "Resume" action for shielded state Sparq message

---

## 10. Open Questions

| # | Question | Impact |
|---|----------|--------|
| 1 | Should the Resume button appear inline in the Sparq message or as a persistent badge in the transport bar? | UX only |
| 2 | Should shielding be skippable via a settings flag (e.g., for devices where servo is unreliable)? | Settings.py constant |
| 3 | Is it worth adding a separate `shield` LED command to the firmware (to signal to the controller that we're in protective mode)? | Firmware scope |
