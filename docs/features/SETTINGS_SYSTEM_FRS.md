# Settings System — Functional Requirements Specification

**Source:** `settings/settings.py` (653 lines), `affilabs/app_config.py` (~87 lines)
**Version:** 2.0.5.1 | **Date:** 2026-03-01

---

## 1. Purpose

Two-tier configuration system: **`settings.py`** holds physics/algorithm constants imported via `from settings import *`; **`app_config.py`** holds runtime operational limits imported individually.

---

## 2. Import Pattern

```python
# settings.py — star import puts 100+ constants into caller namespace
from settings import *

# app_config.py — explicit imports
from affilabs.app_config import GRAPH_SUBSAMPLE_THRESHOLD, TIMELINE_MAX_DISPLAY_POINTS
```

`settings/__init__.py` does `from .settings import *` — bare `from settings import X` works because root is on `sys.path`.

---

## 3. settings.py — Constant Categories (22 groups)

### 3.1 Application Identity
`DEV`, `SW_APP_NAME`, `SW_VERSION`, `TARGET`

### 3.2 Root Directory
`ROOT_DIR` — computed from frozen/source context, creates `generated-files/`

### 3.3 Channel & Unit System
| Constant | Value | Purpose |
|----------|-------|---------|
| `CH_LIST` | `["a", "b", "c", "d"]` | All channels |
| `EZ_CH_LIST` | `["a", "b"]` | EzSPR 2-channel subset |
| `UNIT_LIST` | `{"nm": 1, "RU": 355}` | Unit conversion map |
| `UNIT` | `"RU"` | Default display unit |
| `GRAPH_COLORS` | black/red/blue/green | Standard palette |
| `GRAPH_COLORS_COLORBLIND` | PuOr divergent | Colorblind palette |
| `ACTIVE_GRAPH_COLORS` | — | Live palette (mutable at runtime) |
| `CYCLE_MARKER_STYLE` | `"cursors"` | Marker rendering style |

### 3.4 Hardware USB IDs
`ARDUINO_VID/PID`, `ADAFRUIT_VID`, `PICO_VID/PID`, `CP210X_VID/PID`, `BAUD_RATE = 115200`

### 3.5 Transmittance Display
`INVERT_TRANSMISSION_VISUAL = False`

### 3.6 Detector Parameters (DEPRECATED — use detector profiles)
`MIN_WAVELENGTH = 560`, `MAX_WAVELENGTH = 720`, `POL_WAVELENGTH = 620`

### 3.7 Wavelength Cache
`WAVELENGTH_CACHE_ENABLED = True`, `WAVELENGTH_CACHE_MAX_AGE_DAYS = 7.0`

### 3.8 Timing Architecture
| Constant | Default | Purpose |
|----------|---------|---------|
| `LED_ON_TIME_MS` | 225.0 | LED warm-up before read |
| `DETECTOR_WAIT_MS` | 45.0 | Post-read cooldown |
| `MAX_INTEGRATION_PER_SCAN_MS` | 62.5 | Max integration per scan |
| `NUM_SCANS` | 3 | Scans averaged per read |
| `SAFETY_BUFFER_MS` | 10.0 | Safety margin |
| `OVERNIGHT_MODE` | `False` | Slow acquisition mode |
| `OVERNIGHT_DELAY_SECONDS` | 15.0 | Inter-cycle delay |

### 3.9 Reference Signal
`DARK_NOISE_SCANS = 25`, `REF_SCANS = NUM_SCANS`

### 3.10 Legacy LED Parameters
`S_LED_INT`, `S_LED_MIN`, `P_LED_MAX`, `P_MAX_INCREASE`, `S_COUNT_MAX`, `P_COUNT_THRESHOLD`, `MIN_INTEGRATION`, `CYCLE_TIME = 1.0`, `MAX_INTEGRATION`

### 3.11 Calibration Targets
| Constant | Default | Purpose |
|----------|---------|---------|
| `TARGET_INTENSITY_PERCENT` | 50 | Target signal level |
| `MIN_INTENSITY_PERCENT` | 40 | Min acceptable |
| `MAX_INTENSITY_PERCENT` | 70 | Max acceptable |
| `WEAKEST_TARGET_PERCENT` | 70 | Weak channel target |
| `STRONGEST_MAX_PERCENT` | 95 | Strong channel max |

### 3.12 Transmission Baseline Correction
| Constant | Default | Purpose |
|----------|---------|---------|
| `TRANSMISSION_BASELINE_METHOD` | `"percentile"` | Correction method |
| `TRANSMISSION_BASELINE_PERCENTILE` | 95.0 | Percentile value |
| `TRANSMISSION_BASELINE_POLYNOMIAL_DEGREE` | 2 | Poly degree |
| `TRANSMISSION_OFF_SPR_WAVELENGTH_RANGE` | — | Off-SPR range for correction |

### 3.13 Smoothing Master Switch
| Constant | Default | Purpose |
|----------|---------|---------|
| `FILTERING_ON` | `True` | Master smoothing toggle |
| `MED_FILT_WIN` | 5 | Median filter window |
| `DENOISE_WINDOW` | 11 | SG denoising window |
| `DENOISE_POLYORDER` | 3 | SG polynomial order |
| `DYNAMIC_SG_ENABLED` | `True` | Dynamic SG filter |
| `KALMAN_FILTER_ENABLED` | — | Kalman filter toggle |

### 3.14 Peak Tracking
| Constant | Default | Purpose |
|----------|---------|---------|
| `PEAK_TRACKING_METHOD` | `"numerical_derivative"` | Tracking algorithm |
| `WIDTH_BIAS_CORRECTION_ENABLED` | `True` | Bias correction |
| `WIDTH_BIAS_K` | 0.5 | Correction coefficient |
| `CENTROID_WINDOW_NM` | 100.0 | Centroid window |
| `FOURIER_ALPHA` | 3430 | Fourier weighting |

### 3.15 Session Quality Monitoring
`ENABLE_SESSION_QUALITY_MONITORING = False`, FWHM thresholds, QC wavelength range, degradation alert

### 3.16 Consensus Peak Tracking
`CONSENSUS_SAVGOL_WINDOW = 7`, `CONSENSUS_TARGET_PIXELS = 20`, centroid/parabolic weights

### 3.17 Acquisition Speed
`INTEGRATION_TIME_MS = 100.0`, `NUM_SCANS_PER_ACQUISITION = 2`, `TEMPORAL_WINDOW_SIZE = 5`

### 3.18 GUI Rendering
`ENABLE_ANTIALIASING_LIVE_MODE = False`, `ENABLE_ANTIALIASING_STATIC = True`, `GUI_UPDATE_EVERY_N_CYCLES = 1`

### 3.19 Live Mode Smart Boost
`LIVE_MODE_MAX_INTEGRATION_MS`, `LIVE_MODE_TARGET_INTENSITY_PERCENT = 90`, boost factor range

### 3.20 Signal Telemetry & Event Classifier
`SIGNAL_TELEMETRY_ENABLED = True`, injection detection thresholds, readiness thresholds, bubble detection constants

### 3.21 Miscellaneous
`DEBUG`, `SHOW_PLOT`, `RECORDING_INTERVAL = 15`, `FLUSH_RATE = 220`, `DEMO = False`, `FORCE_FULL_CALIBRATION = True`, `CONSOLE_LOG_LEVEL`, `PROFILING_ENABLED`

### 3.22 Default Config
`DEFAULT_CONFIG` dict → written to `CONFIG_FILE` (JSON). `from local_settings import *` at bottom (optional override).

---

## 4. app_config.py — Runtime Categories

| Category | Key Constants |
|----------|---------------|
| **Data Acquisition** | `LEAK_DETECTION_WINDOW = 5.0`, `LEAK_THRESHOLD_RATIO = 1.5` |
| **Signal Processing** | `WAVELENGTH_TO_RU_CONVERSION = 355.0` |
| **Filtering** | `DEFAULT_FILTER_ENABLED = False`, `DEFAULT_FILTER_STRENGTH = 3` |
| **Graph Display** | `GRAPH_SUBSAMPLE_THRESHOLD = 10000`, `GRAPH_SUBSAMPLE_TARGET = 5000` |
| **Memory** | `TIMELINE_MAX_DISPLAY_POINTS = 20000`, `TIMELINE_MAX_MEMORY_POINTS = 100000`, `TIMELINE_TRIM_TO_POINTS = 80000`, `CYCLE_MAX_POINTS = 3600`, `ENABLE_MEMORY_TRIMMING = False` |
| **Quality** | `FWHM_WARNING_THRESHOLD = 2.0`, `FWHM_CRITICAL_THRESHOLD = 5.0` |
| **Optics** | `OPTICS_LEAK_DETECTION_TIME = 3.0`, `OPTICS_LEAK_THRESHOLD = 0.10`, `OPTICS_MAX_DETECTOR_COUNTS = 65535` |
| **Timing** | `ACQUISITION_INTERVAL_MS = 100`, `CALIBRATION_TIMEOUT_S = 60` |
| **Export** | `DEFAULT_EXPORT_DIRECTORY = "Documents"`, `DEFAULT_FILE_PREFIX` |
| **Hardware** | `HARDWARE_SCAN_TIMEOUT_S = 10`, `CONTROLLER_RETRY_ATTEMPTS = 3` |
| **UI Updates** | `STATUS_UPDATE_INTERVAL_MS = 100`, `CYCLE_OF_INTEREST_UPDATE_INTERVAL_MS = 33` |
| **Live Performance** | `DEBUG_LOG_THROTTLE_FACTOR = 10`, `TRANSMISSION_UPDATE_INTERVAL = 0.05` |
| **Feature Flags** | `ENABLE_TRANSMISSION_UPDATES_DEFAULT = True`, `ENABLE_RAW_SPECTRUM_UPDATES_DEFAULT = True` |

---

## 5. Override Mechanism

`settings.py` ends with `from local_settings import *` — if `settings/local_settings.py` exists, its values override any constant. This enables per-developer or per-deployment overrides without modifying the committed file.

---

## 6. Relationship to Detector Profiles

The deprecated detector constants in §3.6 (`MIN_WAVELENGTH`, `MAX_WAVELENGTH`, etc.) are overridden at runtime by values from `detector_profiles/*.json` via `get_current_detector_profile()`. New code should read from detector profiles, not from these constants.
