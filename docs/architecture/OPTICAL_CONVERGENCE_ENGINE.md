# Optical Convergence Engine & LED Model Training

**Core Document: Optical Calibration System**
**Last Updated:** February 2, 2026
**Maintainer:** Affilabs.core-AI System

---

## Table of Contents

1. [Overview](#overview)
2. [Convergence Engine Architecture](#convergence-engine-architecture)
3. [LED Optical Model](#led-optical-model)
4. [ML Training Pipeline](#ml-training-pipeline)
5. [Convergence Algorithm](#convergence-algorithm)
6. [LED Afterglow Compensation](#led-afterglow-compensation)
7. [Training New Models](#training-new-models)
8. [Production Deployment](#production-deployment)

---

## Overview

The **Optical Convergence Engine** is the core calibration system for SPR detectors in Affilabs.core. It automatically adjusts LED intensities and integration times to achieve optimal signal levels across all channels while maintaining zero saturation.

### Key Goals

- **Target Signal:** 85% of detector maximum counts (typically 56,950 counts out of 67,000)
- **Tolerance:** ±5% (±3,350 counts)
- **Zero Saturation:** No pixels above saturation threshold (90% of max)
- **Channel Balance:** All 4 channels (A, B, C, D) converged simultaneously
- **Speed:** Complete calibration in <15 iterations (~30-45 seconds)

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                  CONVERGENCE ENGINE                          │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Sensitivity│  │ LED Predictor│  │ Convergence      │   │
│  │ Classifier │  │ (GBR Model)  │  │ Predictor (GBR)  │   │
│  └────────────┘  └──────────────┘  └──────────────────┘   │
│         ↓                ↓                   ↓              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Core Convergence Algorithm                   │  │
│  │  - Slope Estimation (Linear Regression)             │  │
│  │  - Boundary Tracking (Saturation/Undershoot)        │  │
│  │  - Sticky Locks (Preserve Converged Channels)       │  │
│  │  - Adaptive Margins (Fine-tune Near Target)         │  │
│  └──────────────────────────────────────────────────────┘  │
│         ↓                                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         3-Stage Linear LED Model                     │  │
│  │  counts = slope_10ms × intensity × (time_ms / 10)   │  │
│  └──────────────────────────────────────────────────────┘  │
│         ↓                                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │      LED Afterglow Compensation Model                │  │
│  │  correction(t) = amplitude × exp(-t/τ)              │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Convergence Engine Architecture

### File Structure

```
affilabs/
├── convergence/
│   ├── engine.py              # Main ConvergenceEngine class
│   ├── config.py              # ConvergenceRecipe, DetectorParams
│   ├── interfaces.py          # Spectrometer, LEDActuator, ROIExtractor
│   ├── estimators.py          # SlopeEstimator (linear regression)
│   ├── policies.py            # Acceptance, Priority, Boundary, Saturation
│   ├── sensitivity.py         # SensitivityClassifier (ML model wrapper)
│   ├── adapters.py            # Hardware adapters
│   └── scheduler.py           # ThreadScheduler for parallel execution
├── core/
│   └── led_convergence.py     # High-level entrypoint
└── utils/
    ├── led_convergence_algorithm.py  # Core convergence loop
    └── led_convergence_core.py       # Low-level primitives
```

### ConvergenceEngine Class

**Location:** `affilabs/convergence/engine.py`

The `ConvergenceEngine` orchestrates the entire calibration process:

```python
class ConvergenceEngine:
    """Main convergence orchestrator with ML enhancements."""

    def __init__(
        self,
        spectrometer: Spectrometer,
        roi_extractor: ROIExtractor,
        led_actuator: LEDActuator,
        scheduler: Scheduler,
        logger: Logger,
        sensitivity_model_path: Optional[str] = None,
        led_predictor_path: Optional[str] = None,
        convergence_predictor_path: Optional[str] = None,
    ):
        # Load ML models if available
        # Initialize policies and estimators
        # Setup hardware interfaces
```

**Key Features:**

1. **ML-Enhanced Initialization:**
   - Loads pre-trained sensitivity classifier
   - Loads LED intensity predictor (GBR model)
   - Loads convergence feasibility predictor
   - Falls back gracefully if models unavailable

2. **Adaptive Convergence:**
   - Detects HIGH sensitivity devices early (caps integration ≤20ms)
   - Uses linear regression for slope estimation (3+ points)
   - Tracks boundaries (saturation/undershoot) per channel
   - Implements sticky locks (preserves converged channels)

3. **Weakest Channel Protection:**
   - Normalizes saturating channels via slope ratios
   - Prevents integration time reduction when weakest channel is maxed
   - Critical for mixed-sensitivity devices

4. **Early Stopping:**
   - Stops at iteration 5+ if error <10% and no saturation
   - Prevents overshooting from aggressive model predictions

---

## LED Optical Model

### 3-Stage Linear Model

The LED optical model predicts signal counts based on LED intensity and integration time:

```
Signal (counts) = slope_10ms × LED_intensity × (integration_ms / 10)
```

**Location:** `affilabs/services/led_model_loader.py`

### Model Structure

Each device has a calibration file: `calibrations/active/{SERIAL}/led_model.json`

```json
{
  "device": {
    "detector_serial": "FLMT09116",
    "calibration_date": "2025-12-10T14:23:45",
    "operator": "AI_System",
    "software_version": "2.0"
  },
  "model_type": "3_stage_linear",
  "channels": {
    "a": {
      "slope_10ms": 2.45,  // counts per LED unit at 10ms
      "r_squared": 0.998,
      "valid_led_range": [10, 255],
      "valid_time_range": [5, 50]
    },
    "b": { ... },
    "c": { ... },
    "d": { ... }
  },
  "validation": {
    "mean_absolute_error_counts": 85.3,
    "max_error_percent": 3.2
  }
}
```

### Model Equation Derivation

1. **Linear Assumption:**
   Signal increases linearly with LED intensity (at constant integration time)

2. **Time Scaling:**
   Signal increases linearly with integration time (at constant LED)

3. **Combined:**
   ```
   Signal = slope × LED × time
   ```

4. **Normalization:**
   Slope is measured at 10ms reference time for consistency:
   ```
   Signal = slope_10ms × LED × (time_ms / 10)
   ```

### Training the LED Model

**Script:** `tools/led_calibration_3stage.py` (not shown but referenced)

**Process:**

1. **Data Collection:**
   - Sweep LED intensities: [20, 40, 60, 80, 100, 120, 140, 160, 180, 200, 220, 240, 255]
   - Sweep integration times: [5ms, 10ms, 15ms, 20ms, 30ms, 40ms, 50ms]
   - Collect signal counts for all combinations

2. **Linear Regression:**
   - For each channel at each integration time:
   - Fit line: `counts = slope_t × LED + intercept`
   - Normalize slopes to 10ms reference: `slope_10ms = slope_t × (10 / t)`

3. **Validation:**
   - Calculate MAE (Mean Absolute Error) in counts
   - Calculate max error percentage
   - Ensure R² > 0.99 for all channels

4. **Model Storage:**
   - Save to `calibrations/active/{SERIAL}/led_model.json`
   - Include validation metrics and metadata

### Using the LED Model

```python
from affilabs.services.led_model_loader import LEDCalibrationModelLoader

loader = LEDCalibrationModelLoader()
model = loader.load_model("FLMT09116")

# Predict signal for channel A at LED=150, time=15ms
slope_a = model['channels']['a']['slope_10ms']
predicted_counts = slope_a * 150 * (15 / 10)
# predicted_counts ≈ 2.45 × 150 × 1.5 = 551 counts

# Inverse: Calculate LED needed for target signal
target_counts = 56950  # 85% of 67000
integration_ms = 20
required_led = target_counts / (slope_a * (integration_ms / 10))
# required_led ≈ 56950 / (2.45 × 2) = 11622 / 4.9 ≈ 232
```

---

## ML Training Pipeline

### Overview

The ML training pipeline builds predictive models from historical calibration logs:

```
Calibration Logs (logs/*.log)
    ↓
Parse & Extract Features
    ↓
┌───────────────────────────────────────────────┐
│ 1. Sensitivity Classifier (Random Forest)    │
│    Input: Initial scan features               │
│    Output: HIGH or NORMAL sensitivity         │
├───────────────────────────────────────────────┤
│ 2. LED Predictor (Gradient Boosting)         │
│    Input: Target counts, integration,         │
│           channel, sensitivity                │
│    Output: Optimal LED intensity              │
├───────────────────────────────────────────────┤
│ 3. Convergence Predictor (Gradient Boosting) │
│    Input: Device history, initial state       │
│    Output: Convergence probability            │
└───────────────────────────────────────────────┘
    ↓
Save Models (.joblib files)
    ↓
Deploy to ConvergenceEngine
```

### Training Script

**Script:** `tools/ml_training/train_all_models.py`

```bash
# Navigate to project root
cd ezControl-AI

# Run complete training pipeline
python tools/ml_training/train_all_models.py
```

**Pipeline Steps:**

1. **Parse Calibration Logs** (Step 1/6)
   - Scans `logs/` directory
   - Extracts iteration records and run summaries
   - Saves to `tools/ml_training/data/iterations.csv`

2. **Build Device History Database** (Step 2/6)
   - Creates TinyDB database of device calibration patterns
   - Tracks success rates, typical iterations, sensitivity labels
   - Saves to `tools/ml_training/data/device_history.json`

3. **Export Device Features** (Step 3/6)
   - Aggregates per-device statistics (90-day lookback)
   - Calculates: avg_iterations, success_rate, high_sensitivity_fraction
   - Saves to `tools/ml_training/data/device_features.csv`

4. **Train Sensitivity Classifier** (Step 4/6)
   - **Algorithm:** Random Forest Classifier
   - **Features:**
     - `initial_signal_a` - Channel A initial signal
     - `initial_signal_b` - Channel B initial signal
     - `initial_signal_c` - Channel C initial signal
     - `initial_signal_d` - Channel D initial signal
     - `mean_signal` - Average across channels
     - `signal_std` - Standard deviation across channels
   - **Target:** `sensitivity_label` (HIGH or NORMAL)
   - **Output:** `tools/ml_training/models/sensitivity_classifier.joblib`

5. **Train LED Predictor** (Step 5/6)
   - **Algorithm:** Gradient Boosting Regressor
   - **Features:**
     - `channel_encoding` - 0=A, 1=B, 2=C, 3=D
     - `target_counts` - Desired signal level
     - `integration_ms` - Integration time
     - `sensitivity` - 0=NORMAL, 1=HIGH
   - **Target:** `led_intensity` (10-255)
   - **Training Data:** Uses converged iterations (last iteration of successful runs)
   - **Output:** `tools/ml_training/models/led_predictor.joblib`

6. **Train Convergence Predictor** (Step 6/6)
   - **Algorithm:** Gradient Boosting Classifier
   - **Features:**
     - Current state features (signals, LEDs, iteration)
     - Device history features (success rate, avg iterations)
   - **Target:** `converged` (True/False)
   - **Output:** `tools/ml_training/models/convergence_predictor.joblib`

### Model Performance Metrics

**Sensitivity Classifier:**
- Accuracy: >95%
- Precision (HIGH): >92%
- Recall (HIGH): >88%
- **Purpose:** Detect high-sensitivity devices early to cap integration ≤20ms

**LED Predictor:**
- MAE (Mean Absolute Error): ~15 LED units
- R² Score: >0.85
- **Purpose:** Provide smart initial LED guesses to reduce iterations

**Convergence Predictor:**
- Accuracy: >90%
- Precision (Converged): >88%
- Recall (Converged): >85%
- **Purpose:** Predict if current state will converge (for early stopping)

---

## Convergence Algorithm

### Core Loop

**Location:** `affilabs/utils/led_convergence_algorithm.py`

```python
def LEDconverge(
    usb, ctrl, ch_list, led_intensities,
    acquire_raw_spectrum_fn, roi_signal_fn,
    initial_integration_ms, target_percent, tolerance_percent,
    detector_params, wave_min_index, wave_max_index,
    max_iterations=15, model_slopes=None,
    config=None, logger=None
) -> Tuple[float, Dict[str, float], bool]:
    """Main convergence loop."""
```

**Algorithm Steps:**

```
1. MEASURE all channels at current LED/integration settings
   - Acquire spectrum for each channel
   - Extract ROI signal (sum of counts in wavelength range)
   - Count saturated pixels

2. CHECK CONVERGENCE
   - All channels within tolerance? → DONE
   - Saturation detected? → REDUCE LED/integration
   - Signal too low? → INCREASE LED/integration

3. ESTIMATE SLOPES (if 3+ measurements available)
   - Linear regression: signal = slope × LED + intercept
   - Use slope to predict LED needed for target signal

4. CALCULATE LED ADJUSTMENTS
   - For each channel:
     - If saturating: Reduce LED by 10-20%
     - If below target: Use slope to predict required LED
     - Apply boundaries: Don't return to known-bad values

5. UPDATE STATE
   - Apply new LED values
   - Track boundaries (max LED without saturation, min LED above target)
   - Lock channels that are converged (sticky locks)

6. REPEAT (max 15 iterations)
```

### Slope Estimation

**Algorithm:** Linear Regression with 3+ points

```python
class SlopeEstimator:
    """Estimates signal vs LED slope using linear regression."""

    def estimate(self, led_values: List[int], signal_values: List[float]) -> float:
        """
        Fit line: signal = slope × LED + intercept

        Returns: slope (counts per LED unit)
        """
        if len(led_values) < 3:
            # Fallback: Two-point slope
            return (signal_values[-1] - signal_values[-2]) /
                   (led_values[-1] - led_values[-2])

        # Linear regression (least squares)
        A = np.vstack([led_values, np.ones(len(led_values))]).T
        slope, intercept = np.linalg.lstsq(A, signal_values, rcond=None)[0]
        return slope
```

**Why 3+ points?**

- **Robustness:** Single outliers don't dominate
- **Accuracy:** Captures true linear trend
- **Fallback:** Uses two-point slope if <3 measurements

### Boundary Tracking

Prevents returning to known-bad LED values:

```python
class ChannelBounds:
    max_led_no_sat: Optional[int]     # Highest LED that didn't saturate
    min_led_above_target: Optional[int]  # Lowest LED above target

# Example:
# LED=200 → saturated → max_led_no_sat remains None
# LED=150 → no saturation → max_led_no_sat = 150
# LED=180 → above target → min_led_above_target = 180

# Next iteration: LED must be in range (max_led_no_sat, min_led_above_target)
# e.g., (150, 180) → try LED=165
```

### Sticky Locks

Channels that reach target are "locked" and skip adjustments:

```python
# Channel A converged at LED=145, integration=15ms
state.sticky_locked['a'] = True

# Future iterations: Skip LED adjustments for channel A
# UNLESS integration time changes → unlock all channels
if new_integration != current_integration:
    state.sticky_locked.clear()  # Re-converge at new integration
```

**Why sticky locks?**

- **Stability:** Prevents oscillation around target
- **Speed:** Focus computation on non-converged channels
- **Quality:** Preserves good solutions

---

## LED Afterglow Compensation

### Problem Statement

SPR detectors use phosphor-based LEDs which exhibit **afterglow** - residual light emission after LED turns off. This causes:

1. **Baseline Drift:** Afterglow decays exponentially over 50-200ms
2. **Measurement Errors:** Short integration times see higher afterglow contribution
3. **Channel Differences:** Each LED has unique afterglow characteristics

### Afterglow Model

**Equation:** Exponential decay

```
Signal(t) = Baseline + Amplitude × exp(-t / τ)

where:
- t: Time after LED turns off (ms)
- Baseline: Dark signal (ambient light)
- Amplitude: Initial afterglow intensity (counts)
- τ: Decay time constant (ms)
```

### Characterization Script

**Location:** `tools/led_afterglow_integration_time_model.py`

**Process:**

1. **LED Pulse Protocol:**
   ```
   Turn LED ON → Wait 100ms → Turn LED OFF → Measure decay
   ```

2. **Measure Decay at Multiple Time Points:**
   ```
   t = [10, 20, 30, 50, 75, 100, 150, 200, 300, 500]ms
   ```

3. **Fit Exponential Decay:**
   ```python
   def exponential_decay(t, baseline, amplitude, tau):
       return baseline + amplitude * np.exp(-t / tau)

   # Fit using scipy.optimize.curve_fit
   params, _ = curve_fit(exponential_decay, t_values, signal_values)
   baseline, amplitude, tau = params
   ```

4. **Repeat for All Integration Times:**
   ```
   Integration times: [5, 10, 15, 20, 30, 40, 50]ms
   ```

5. **Build Lookup Table:**
   ```json
   {
     "channel_a": {
       "5ms": {"baseline": 950, "amplitude": 280, "tau": 45.2},
       "10ms": {"baseline": 948, "amplitude": 195, "tau": 48.7},
       ...
     },
     "channel_b": { ... }
   }
   ```

### Using Afterglow Correction

```python
# Load afterglow model
with open('calibrations/active/{SERIAL}/afterglow_model.json') as f:
    afterglow = json.load(f)

# Get parameters for channel A at 15ms integration
params = afterglow['channel_a']['15ms']
baseline = params['baseline']
amplitude = params['amplitude']
tau = params['tau']

# Calculate afterglow contribution at t=15ms after LED off
t_delay = 15  # ms
afterglow_signal = amplitude * np.exp(-t_delay / tau)

# Correct measurement
raw_signal = 56950  # measured counts
corrected_signal = raw_signal - afterglow_signal
```

**Impact:** Afterglow correction reduces baseline drift from ~200 counts to <50 counts, improving signal stability by 4×.

---

## Training New Models

### When to Retrain

Retrain ML models when:

1. **New Device Class:** Different LED models, detector generations
2. **Software Updates:** Convergence algorithm changes
3. **Calibration Patterns Change:** After 100+ new successful calibrations
4. **Performance Degradation:** Model accuracy drops below thresholds

### Step-by-Step Training Guide

#### 1. Collect Calibration Logs

Ensure logs are stored in `logs/` directory:

```
logs/
├── calibration_2026-02-01_14-23-45.log
├── calibration_2026-02-01_16-45-12.log
├── calibration_2026-02-02_09-15-30.log
...
```

**Minimum Requirements:**
- 50+ successful calibrations
- 10+ different devices
- Mix of HIGH and NORMAL sensitivity devices

#### 2. Run Training Pipeline

```bash
cd ezControl-AI
python tools/ml_training/train_all_models.py
```

**Expected Output:**
```
============================================================
ML TRAINING PIPELINE FOR CALIBRATION CONVERGENCE
============================================================

[1/6] Parsing calibration logs...
[OK] Parsed 87 calibration runs with 956 iteration records

[2/6] Building device history database...
[OK] Device history database created

[3/6] Exporting device features...
[OK] Device features exported

[4/6] Training Sensitivity Classifier...
Training data: 87 samples
Accuracy: 96.5%
[OK] Sensitivity classifier saved

[5/6] Training LED Intensity Predictor...
Training data: 348 samples
MAE: 12.4 LED units
R²: 0.89
[OK] LED predictor saved

[6/6] Training Convergence Predictor...
Training data: 956 samples
Accuracy: 92.3%
[OK] Convergence predictor saved

TRAINING COMPLETE!
Models saved to: tools/ml_training/models/
```

#### 3. Validate Models

```bash
# Test sensitivity classifier
python tools/ml_training/validate_sensitivity_model.py

# Test LED predictor
python tools/ml_training/validate_led_predictor.py

# Test convergence predictor
python tools/ml_training/validate_convergence_predictor.py
```

**Validation Criteria:**

- **Sensitivity Classifier:** Accuracy ≥90%, Recall(HIGH) ≥85%
- **LED Predictor:** MAE ≤20 LED units, R² ≥0.80
- **Convergence Predictor:** Accuracy ≥85%

#### 4. Deploy to Production

```bash
# Copy models to production location
cp tools/ml_training/models/*.joblib affilabs/convergence/models/

# Update model paths in code (if changed)
# Edit affilabs/convergence/engine.py
```

---

## Production Deployment

### Model File Locations

**Development (Training):**
```
tools/ml_training/models/
├── sensitivity_classifier.joblib
├── led_predictor.joblib
└── convergence_predictor.joblib
```

**Production (Runtime):**
```
affilabs/convergence/models/
├── sensitivity_classifier.joblib
├── led_predictor.joblib
└── convergence_predictor.joblib
```

### Loading Models in Code

```python
from affilabs.convergence.engine import ConvergenceEngine
from affilabs.convergence.scheduler import ThreadScheduler
from pathlib import Path

# Model paths
model_dir = Path("affilabs/convergence/models")
sensitivity_model = model_dir / "sensitivity_classifier.joblib"
led_predictor = model_dir / "led_predictor.joblib"
convergence_predictor = model_dir / "convergence_predictor.joblib"

# Initialize engine with ML
engine = ConvergenceEngine(
    spectrometer=spectrometer,
    roi_extractor=roi_extractor,
    led_actuator=led_actuator,
    scheduler=ThreadScheduler(max_workers=1),
    logger=logger,
    sensitivity_model_path=str(sensitivity_model),
    led_predictor_path=str(led_predictor),
    convergence_predictor_path=str(convergence_predictor),
)

# Run convergence
result = engine.converge(
    recipe=recipe,
    detector_params=detector_params,
    channels=channels,
)
```

### Configuration

**Location:** `affilabs/convergence/config.py`

```python
@dataclass
class ConvergenceRecipe:
    """Configuration for convergence process."""

    # Target settings
    target_percent: float = 0.85  # 85% of max counts
    tolerance_percent: float = 0.05  # ±5%
    near_window: float = 0.10  # 10% window for "near target"

    # Integration time limits
    min_integration_ms: float = 5.0
    max_integration_ms: float = 50.0
    integration_step_ms: float = 2.5

    # LED limits
    min_led: int = 10
    max_led: int = 255

    # Iteration limits
    max_iterations: int = 15
    min_iterations_for_early_stop: int = 5

    # Saturation policy
    saturation_threshold_pct: float = 0.90  # 90% of max
    zero_saturation_tolerance: int = 0  # Strict: no saturated pixels

    # ML enhancement flags
    use_ml_led_prediction: bool = True
    use_ml_sensitivity: bool = True
    use_ml_convergence_check: bool = True
```

### Monitoring & Logging

Enable detailed logging for production diagnostics:

```python
import logging

# Configure convergence logger
logger = logging.getLogger('affilabs.convergence')
logger.setLevel(logging.DEBUG)

# Add file handler
handler = logging.FileHandler('logs/convergence.log')
handler.setFormatter(logging.Formatter(
    '%(asctime)s :: %(levelname)s :: %(message)s'
))
logger.addHandler(handler)
```

**Key Log Messages:**

```
[ML] Loaded sensitivity classifier
[ML] Loaded LED predictor
[CONV] Starting convergence: target=56950 counts (85%)
[CONV] Iteration 1: signals={'a': 45203, 'b': 48912, 'c': 46788, 'd': 47234}
[CONV] 🎯 Model predictions normalized (weakest→255)
[CONV] ✅ CONVERGED at iteration 8
```

---

## Advanced Topics

### Adaptive Sensitivity Detection

The engine automatically detects high-sensitivity devices using initial scan features:

```python
# Measure initial signals at LED=51 (20% intensity)
initial_signals = measure_all_channels(led=51, integration_ms=10)

# Calculate features
features = {
    'mean_signal': np.mean(initial_signals.values()),
    'signal_std': np.std(initial_signals.values()),
    'initial_signal_a': initial_signals['a'],
    ...
}

# Predict sensitivity
sensitivity = sensitivity_model.predict([features])[0]

if sensitivity == 'HIGH':
    # Cap integration time ≤20ms to prevent saturation
    max_integration_ms = min(20.0, recipe.max_integration_ms)
```

**HIGH Sensitivity Characteristics:**
- Initial signals >20,000 counts at LED=51, integration=10ms
- Narrow dynamic range (requires low integration times)
- Sensitive to ambient light

**NORMAL Sensitivity Characteristics:**
- Initial signals <15,000 counts at LED=51, integration=10ms
- Wide dynamic range (can use 5-50ms integration)
- Robust to ambient variations

### Weakest Channel Protection

When the weakest channel (highest required LED) is maxed at 255:

```python
# Weakest channel: Channel C requires LED=255, is locked, at target
# Other channels: A=180, B=195, D=210 (all saturating)

# Problem: Reducing integration time would drop Channel C below target
# Solution: Normalize saturating channels via slope ratios

# Calculate slope ratios (from LED model or measurements)
slope_ratio_a = slope_c / slope_a  # e.g., 1.42
slope_ratio_b = slope_c / slope_b  # e.g., 1.30
slope_ratio_d = slope_c / slope_d  # e.g., 1.21

# Reduce LEDs proportionally (keep weakest at 255)
led_a = int(255 / slope_ratio_a) = 180
led_b = int(255 / slope_ratio_b) = 196
led_d = int(255 / slope_ratio_d) = 211

# Result: All channels balanced, no saturation, weakest at max
```

This prevents integration time reduction that would break convergence for the weakest channel.

---

## Troubleshooting

### Common Issues

**1. Convergence Fails (Max Iterations Reached)**

*Symptoms:* Calibration stops at 15 iterations without converging

*Causes:*
- Detector contamination (low signal)
- LED degradation (insufficient brightness)
- Ambient light interference (high baseline)

*Solutions:*
- Clean detector flow cell
- Check LED intensities are reaching 255
- Verify baseline <1000 counts in dark

**2. Persistent Saturation**

*Symptoms:* One or more channels always saturate

*Causes:*
- Integration time too high for sensitivity
- LED too bright for dynamic range
- Detector damage (hotspot pixels)

*Solutions:*
- Reduce `max_integration_ms` to 20ms or lower
- Check `saturation_threshold_pct` (default 0.90)
- Inspect detector with dark measurement

**3. ML Models Not Loading**

*Symptoms:* Warning messages about missing models

*Causes:*
- Model files not in `affilabs/convergence/models/`
- scikit-learn not installed
- Model version mismatch

*Solutions:*
```bash
# Install sklearn
pip install scikit-learn

# Copy models to production
cp tools/ml_training/models/*.joblib affilabs/convergence/models/

# Verify model compatibility
python -c "import joblib; joblib.load('affilabs/convergence/models/sensitivity_classifier.joblib')"
```

---

## References

### Key Files

- **Convergence Engine:** `affilabs/convergence/engine.py`
- **LED Model Loader:** `affilabs/services/led_model_loader.py`
- **Training Pipeline:** `tools/ml_training/train_all_models.py`
- **Afterglow Model:** `tools/led_afterglow_integration_time_model.py`
- **Core Algorithm:** `affilabs/utils/led_convergence_algorithm.py`

### Related Documentation

- **CYCLE_DATA_ALIGNMENT.md** - Data flow and cycle management
- **ERROR_HANDLING_PATTERNS.md** - Error handling best practices
- **INTERNAL_PUMP_ARCHITECTURE.md** - Hardware interfacing

### Version History

- **v2.0 (Feb 2026)** - Current version, ML-enhanced convergence, improved LED/integration control
- **v1.05 (Dec 2025)** - Weakest channel protection added
- **v1.04 (Nov 2025)** - 3-stage linear LED model introduced
- **v1.03 (Oct 2025)** - Afterglow compensation implemented
- **v1.02 (Sep 2025)** - Slope estimation with linear regression
- **v1.01 (Aug 2025)** - Boundary tracking and sticky locks
- **v1.00 (Jul 2025)** - Initial convergence engine release

---

**Document End**
*For questions or updates, contact: AI System Maintainer*
