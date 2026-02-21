# Compression Assistant — FRS

**Document Status:** ✅ Code-verified  
**Last Updated:** February 21, 2026  
**Source File:** `standalone_tools/compression_trainer_ui.py` (1800 lines)  
**Service:** `affilabs/services/compression_training.py`  
**User profile hook:** `affilabs/services/user_profile_manager.py` → `compression_training` key

---

## 1. Purpose

The Compression Assistant walks a first-time user through the mechanical process of seating and compressing a sensor chip onto the prism.  Correct compression is critical: too loose → no SPR coupling (flat spectrum); too tight → over-coupling (signal wraps back up).

This tool is **device and sensor agnostic** — it auto-calibrates to the specific instrument by capturing two spectral baselines before guiding live compression.

---

## 2. Launch Paths

| Path | Trigger | Hardware state |
|------|---------|---------------|
| **Standalone** | `python standalone_tools/compression_trainer_ui.py` | Opens its own serial + spectrometer connections |
| **From app (P4SPR)** | Startup calibration → "Sensor Chip" button | Hardware already connected; adapter used |
| **From app (P4PRO)** | Priming wizard / calibration orchestrator | Pre-baseline may be pre-captured from S-pol flow |

When launched from the main app, `HardwareMgrAdapter` wraps the existing `hardware_mgr` — it does **not** disconnect hardware on close (it restores integration time only).

---

## 3. Hardware Adapters

| Class | Use |
|-------|-----|
| `HardwareLink` | Standalone — opens own seabreeze + serial connections |
| `HardwareMgrAdapter` | In-app — wraps `hardware_mgr.usb` (spectrometer) + `hardware_mgr.ctrl` (controller) |

Both expose the same interface: `.connect()`, `.leds_on()`, `.leds_off()`, `.read()`, `.disconnect()`.

---

## 4. Detection Algorithm

### Signal: Mid/Low Band Ratio

The tracker uses a **self-normalizing spectral shape metric** — no absolute calibration needed:

```
ratio = mean(intensity[600–650 nm]) / mean(intensity[560–600 nm])
```

| Band | Range | Role |
|------|-------|------|
| Mid band | 600–650 nm | Numerator — SPR dip region |
| Low band | 560–600 nm | Denominator — reference |

### Why This Works

- As compression improves SPR coupling, the dip deepens in the mid band → ratio **drops**
- S-pol not used here (single-pass ratio metric is sufficient for compression guidance)
- Normalised to `chip_water_ratio = 1.0` before display — removes system-to-system variation

### Sweet Spot

Default range is 94–96% of the uncompressed (chip + water) baseline ratio:

```
sweet_lo = chip_water_ratio × 0.94
sweet_hi = chip_water_ratio × 0.96
```

User can override via the "Advanced Settings" collapsible panel in Step 2.

---

## 5. Stages / Flow

```
STAGE_CONNECT (0)         — standalone only; skipped when launched from app
    ↓
STAGE_NO_CHIP (1)         — Step 1: dry sensor baseline
    ↓
STAGE_CHIP_WATER (2)      — Step 2: chip + water, uncompressed baseline
    ↓
STAGE_COMPRESS (3)        — Step 3: live gauge feedback during knob turn
    ↓
STAGE_QC_LEAK_CHECK (4)   — inject liquid; 30-second intensity stability monitor
    ↓
STAGE_DONE (5)            — compression locked; user returns to experiment
```

### Stage Details

#### STAGE_NO_CHIP
- Shows live raw intensity spectrum (`live_plot`, 540–720 nm)
- On "Capture DRY SENSOR baseline": averages `capture_avg_frames` (default 10) frames → stores `_no_chip_ratio` + `_no_chip_spectrum`

#### STAGE_CHIP_WATER
- Shows live **transmission** = `raw / _no_chip_spectrum` (if reference available)
- Displays "Advanced Settings" toggle for sweet spot adjustment (spinboxes: 85–150, integer %)
- On capture: computes `_chip_water_ratio`; calculates sweet spot; calibrates `CompressionGauge`; saves `.npz` calibration file

#### STAGE_COMPRESS
- `live_plot` hidden; `evo_plot` + `CompressionGauge` visible
- Every spectrum update: `ratio = current_mid_low / chip_water_ratio`
- Gauge + feedback label updated every frame
- Calibration is persisted (`compression_trainer_cal.npz`) so subsequent sessions skip to this stage

#### STAGE_QC_LEAK_CHECK
- `evo_plot` shows relative intensity (normalised to first sample = 1.0)
- 30-second monitoring window (600 samples at ~20 Hz)
- Pass criterion: total intensity does not drop >10% from first-third baseline to last-third
- If `pump` reference is provided (P4PRO + AffiPump): `_PumpFlushWorker` runs a gentle 1 mL aspirate-dispense cycle concurrently
- User can skip via "Skip Leak Check" button (shown only when monitoring not active)

---

## 6. CompressionGauge Widget

Vertical colour-coded bar rendered via `paintEvent` (pure `QPainter`, no Qt widgets):

| Zone colour | Condition | Label |
|-------------|-----------|-------|
| Yellow (top) | ratio > sweet_hi | "Loose" |
| Green (middle) | sweet_lo ≤ ratio ≤ sweet_hi | "SWEET SPOT" |
| Red (bottom) | ratio < sweet_lo | "Over-tight" |

Triangle marker moves vertically to show current position.  Text value drawn left of the bar.

### Hysteresis (over-compression detection)

If the ratio drops **below** sweet_lo (`_has_been_below = True`) and then rises back above sweet_hi (wrap-around), the zone is set to `"backoff"` (red) instead of `"tighten"` (orange).  This prevents the user from continuing to tighten after going too far.

---

## 7. UI Structure

```
QMainWindow (860×640 min, 1060×720 default)
  └─ central QWidget  (background: #F2F2F7)
       └─ root QVBoxLayout (margins 24/16/24/12, spacing 10)
            ├─ Header row (title + status label)
            ├─ StepProgressBar (3 steps: No Chip / Chip+Water / Compress)
            └─ content QHBoxLayout
                 ├─ Left column (stretch=3)
                 │    ├─ instr_card  (QFrame#affi_card, white, border-radius 14px)
                 │    │    ├─ step_badge  (pill label, min-width 100px, max 140px)
                 │    │    ├─ instruction  (14px, word-wrap, min-height 108px)
                 │    │    └─ sweet_spot_container (hidden except Step 2)
                 │    │         ├─ settings_toggle_btn (▸/▾ Advanced Settings)
                 │    │         └─ settings_panel (lower/upper spinboxes + Reset)
                 │    ├─ action_btn (50px tall, primary action, full-width)
                 │    ├─ skip_btn (hidden except STAGE_QC_LEAK_CHECK not monitoring)
                 │    ├─ feedback (36px bold label, fixed 56px height)
                 │    ├─ live_plot (pg.PlotWidget, 140px, visible Steps 1-2)
                 │    └─ evo_plot  (pg.PlotWidget, 140px, visible Steps 3-QC)
                 └─ Right column (stretch=1)
                      ├─ "Compression" label
                      └─ CompressionGauge (visible Step 3 only)
```

### StepProgressBar

Custom `QWidget` rendered via `paintEvent`:
- 3 numbered circles connected by lines
- Circle states: done (green ✓), current (purple filled), pending (gray)
- `set_step(n)`: marks 0..n-1 as done, n as current
- `mark_all_done()`: all green — called in STAGE_DONE

---

## 8. Configuration (`TrainerConfig`)

All tuneable parameters — no magic numbers in the UI:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `integration_time_ms` | 5 ms | Spectrometer integration time |
| `led_brightness` | 25 | LED intensity (0-255) |
| `band_low` | 560–600 nm | Reference band for ratio |
| `band_mid` | 600–650 nm | Signal band for ratio |
| `band_high` | 650–695 nm | (Reserved) |
| `sweet_spot_low` | 0.94 | Lower green zone boundary (normalised) |
| `sweet_spot_high` | 0.96 | Upper green zone boundary (normalised) |
| `capture_avg_frames` | 10 | Frames averaged per baseline capture |
| `trend_window` | 30 | Derivative smoothing window |
| `evo_buffer_size` | 500 | Evolution plot history length |

---

## 9. Calibration Persistence

File: `standalone_tools/compression_trainer_cal.npz`  
Saved after Step 2 capture; auto-loaded on next launch.

| Key | Type | Content |
|-----|------|---------|
| `no_chip_ratio` | float | Mid/low ratio from dry sensor baseline |
| `chip_water_ratio` | float | Mid/low ratio from chip+water baseline |
| `target_ratio` | float | Centre of sweet spot |

If `chip_water_ratio > 0 and target_ratio > 0`, the app skips directly to STAGE_COMPRESS on next launch.

---

## 10. User Profile Integration

Training result recorded in `user_profiles.json` under each user:

```json
"compression_training": {
  "completed": true,
  "score": 0.95,
  "date": "2026-02-21T10:30:00Z"
}
```

- `UserProfileManager.needs_compression_training(username)` returns `True` if not yet completed
- The priming widget (`affilabs/widgets/priming.py`) checks this and warns the user before priming if training is incomplete

---

## 11. Colour Palette

| Token | Value | Use |
|-------|-------|-----|
| `COL_BG` | `#F2F2F7` | Window background |
| `COL_CARD` | `#FFFFFF` | Card backgrounds |
| `COL_TEXT` | `#1D1D1F` | Primary text |
| `COL_SUBTLE` | `#8E8E93` | Secondary text, disabled |
| `COL_BLUE` | `#007AFF` | Info / primary action |
| `COL_PURPLE` | `#5856D6` | Step badge (in progress) |
| `COL_GREEN` | `#34C759` | Sweet spot, done, pass |
| `COL_ORANGE` | `#FF9500` | Warning, "keep tightening" |
| `COL_RED` | `#FF3B30` | Over-tight, leak, error |
| `COL_BORDER` | `#E5E5EA` | Input borders, gauge border |

These match the main app iOS system color palette (same tokens, different names).

---

## 12. Key Gotchas

1. **`HardwareMgrAdapter` does not disconnect** — the main app owns the hardware; the adapter only restores the integration time on close.
2. **Standalone path uses `seabreeze`** — the main app uses `oceandirect` (via `OceanSpectrometerAdapter`). Different backends, same read interface.
3. **`_has_been_below` hysteresis flag** — must be reset explicitly on `set_calibration()` call; otherwise persists across recalibrations.
4. **P4PRO pump flush is best-effort** — valve + dispense errors are silently swallowed; leak check continues with spectral monitoring only.
5. **`launch_modal()` blocks with `QEventLoop`** — caller blocks until the window is destroyed. Do not call from background threads.
6. **Skip-to-step launch** — `start_stage` param in `launch_modal()` lets the calibration orchestrator skip Step 1 if a pre-baseline is already available from the S-pol reference capture.
