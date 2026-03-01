# Data Acquisition Manager — Functional Requirements Specification

**Source:** `affilabs/core/data_acquisition_manager.py` (2166 lines)
**Version:** 2.0.5.1 | **Date:** 2026-03-01

---

## 1. Purpose

`DataAcquisitionManager` is the core engine that reads raw spectra from the Affi Detector in a background thread. It emits raw spectrum data via Qt signals — all processing is delegated to downstream subscribers (SpectrumProcessor → pipelines).

---

## 2. Class

**`DataAcquisitionManager(QObject)`**

### 2.1 Qt Signals

| Signal | Payload | Purpose |
|--------|---------|---------|
| `spectrum_acquired` | `dict` | Raw spectrum + calibration context per channel |
| `acquisition_error` | `str` | Error message |
| `acquisition_started` | — | Lifecycle: worker thread running |
| `acquisition_stopped` | — | Lifecycle: worker thread exited |

### 2.2 Module-Level Constants

| Constant | Default | Purpose |
|----------|---------|---------|
| `USE_CYCLE_SYNC` | `True` | V2.4 firmware CYCLE_SYNC mode vs EVENT_RANK fallback |
| `ENABLE_WATCHDOG` | `True` | Firmware watchdog safety keepalive |
| `WATCHDOG_KEEPALIVE_INTERVAL` | `60.0` s | Keepalive interval |

---

## 3. Lifecycle

```
apply_calibration(CalibrationData)   ← Must be called before start
  → Validates & stores calibration params, sets calibrated=True

start_acquisition()                  ← Non-blocking
  → Validates calibration
  → Sets polarizer to P-mode
  → Detects firmware capabilities (batch / rankbatch)
  → Deferred launch via QTimer.singleShot(50ms) → _launch_worker()

stop_acquisition()
  → Sends firmware stop + emergency_shutdown
  → Joins thread (3s timeout)
  → Emits acquisition_stopped

pause_acquisition() / resume_acquisition()
  → Sets/clears _pause_acquisition event
  → Tracks cumulative paused duration
```

---

## 4. Acquisition Worker — 3-Tier Fallback

The background thread (`_acquisition_worker`) tries three methods in priority order:

| Priority | Method | Firmware Req | Description |
|----------|--------|-------------|-------------|
| 1 | **RANKBATCH** | V2.4+ | Firmware-controlled LED timing — `set_rankbatch_intensities()`, reads at calculated offsets |
| 2 | **BATCH** | Any | Software-timed — `set_batch_intensities()` once, then sequential channel reads |
| 3 | **SEQUENTIAL** | Any | Individual `_acquire_raw_spectrum()` per channel (slowest, most compatible) |

### 4.1 Batch Acquisition (Default Path)

```
_acquire_all_channels_batch(channels, led_intensities, integration_time_ms, num_scans):
  1. set_batch_intensities(led_intensities)    ← one firmware call
  2. For each channel:
     a. Wait LED_ON_TIME_MS
     b. Read raw spectrum from detector
     c. Wait DETECTOR_WAIT_MS
  3. Return dict of {channel: raw_spectrum}
```

### 4.2 Raw Spectrum Read (Layer 3)

```
_acquire_raw_spectrum(channel, led_intensity, integration_time_ms, ...):
  1. Set LED via batch command
  2. Wait pre_led_delay_ms
  3. detector.read_spectrum()  → numpy array
  4. Wait post_led_delay_ms
  5. Return raw numpy array (or None on error)
```

### 4.3 Emission

```
_emit_raw_spectrum(channel, raw_spectrum, led_intensities):
  → Packages: raw spectrum + calibration references (S-pol, dark) + LED context
  → spectrum_acquired.emit(dict)
```

---

## 5. Threading Model

| Component | Type | Detail |
|-----------|------|--------|
| Worker thread | `threading.Thread(daemon=True, name="AcquisitionWorker")` | Single background thread |
| GC | `gc.disable()` at module level | Prevents GC pauses during acquisition |
| Stop signal | `threading.Event` (`_stop_acquisition`) | Clean shutdown |
| Pause signal | `threading.Event` (`_pause_acquisition`) | Pause/resume |
| Emission queue | `queue.Queue(maxsize=100)` | `_emission_queue` |
| Cross-thread | Qt `Signal` | `spectrum_acquired.emit()` is thread-safe |
| Launch delay | `QTimer.singleShot(50ms)` | Avoids blocking UI on start |

---

## 6. Timing Architecture

All timing constants from `settings.py`:

| Constant | Default | Purpose |
|----------|---------|---------|
| `LED_ON_TIME_MS` | 225.0 | LED warm-up before read |
| `DETECTOR_WAIT_MS` | 45.0 | Post-read cooldown |
| `MAX_INTEGRATION_PER_SCAN_MS` | 62.5 | Max integration per scan |
| `NUM_SCANS` | 3 | Scans averaged per read |
| `SAFETY_BUFFER_MS` | 10.0 | Safety margin |
| `CYCLE_TIME` | 1.0 s | Target time per full 4-channel cycle |

**Detector-aware calculations:**
- Phase Photonics uses 1.93× timing multiplier
- USB4000 uses simple division

---

## 7. Error Recovery

| Condition | Response |
|-----------|----------|
| 5 consecutive failures | Stop acquisition + emit `hardware_disconnected` |
| 20 consecutive per-channel errors | Channel disabled for remainder of run |
| Hardware check failure | `_check_hardware()` validates ctrl + USB present before each cycle |

---

## 8. Key Methods

| Method | Purpose |
|--------|---------|
| `apply_calibration(CalibrationData)` | Single entry point — validates & stores calibration |
| `start_acquisition()` | Validates, detects firmware caps, launches worker |
| `stop_acquisition()` | Firmware stop + join thread |
| `pause_acquisition()` / `resume_acquisition()` | Event-based pause |
| `set_queue_size(int)` | Channel count for sequential acquisition |
| `set_led_delays(pre_ms, post_ms)` | Update LED timing |
| `clear_buffers()` | Clear all channel data buffers |

---

## 9. Configuration Modes

| Mode | Flag | Behavior |
|------|------|----------|
| CYCLE_SYNC | `USE_CYCLE_SYNC=True` | V2.4 firmware-synced timing (default) |
| EVENT_RANK | `USE_CYCLE_SYNC=False` | Legacy fallback |
| Overnight | `OVERNIGHT_MODE=True` | Configurable inter-cycle delay (`OVERNIGHT_DELAY_SECONDS`) |
| Pre-arm | auto-detected | Integration time set once before loop (saves ~7ms/channel) |
