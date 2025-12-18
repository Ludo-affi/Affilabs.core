# LED Convergence Algorithm - Golden Reference Document

**Version:** 1.0  
**Date:** December 18, 2025  
**Status:** Production Reference - Foundation for Future Improvements

---

## 1. Overview

The LED convergence algorithm optimizes LED intensities and integration time to achieve target signal levels across all spectral channels while avoiding pixel saturation. This is the core calibration algorithm used in startup calibration (Steps 4 & 5) and forms the foundation of the SPR measurement system.

### Purpose
- Achieve **consistent signal levels** across channels A, B, C, D
- Target **80-85% of detector maximum** (optimal SNR with headroom)
- Maintain **zero pixel saturation** (any saturated pixel triggers correction)
- Respect **time budget constraints** (60ms max integration, 180ms per spectrum with 3 scans)

### Key Files
- **Algorithm:** `affilabs/utils/led_convergence_algorithm.py` (main convergence loop)
- **Core Functions:** `affilabs/utils/led_convergence_core.py` (measurement, convergence check)
- **Configuration:** `affilabs/convergence/config.py` (thresholds, limits)
- **Orchestration:** `affilabs/core/calibration_orchestrator.py` (Steps 4 & 5)

---

## 2. Signal Measurement Method

### ROI Signal Extraction
The algorithm measures signal using the **top 50 pixels method**:

```python
# From led_convergence_core.py line 300
signal = roi_signal_fn(spec, wave_min_index, wave_max_index, method="top_n_mean", top_n=50)
```

**Process:**
1. Extract ROI from spectrum (wave_min_index to wave_max_index)
2. Sort ROI pixels by intensity
3. Take the **50 highest-value pixels**
4. Return **average of those 50 pixels**

**Why Top 50?**
- Robust to noise (more stable than single max pixel)
- Sensitive to saturation (if 50+ pixels saturate, signal ~65535)
- Represents peak signal region (where SPR resonance occurs)
- Less sensitive to outliers than full ROI average

### Saturation Detection
```python
# From led_convergence_core.py
sat_pixels = count_saturated_pixels(spec, wave_min_index, wave_max_index, saturation_threshold)
```

**Saturation Threshold:** 65535 counts (100% of detector max)  
**Zero Tolerance:** Any pixel ≥ saturation_threshold triggers correction

---

## 3. Target Signal Levels

### S-Mode (Parallel Polarization)
- **Target:** 85% of max_counts = 55,700 counts
- **Tolerance:** ±5% = ±3,280 counts
- **Acceptance Window:** 52,420 to 59,000 counts (93.75% to 106.25% of target)
- **Near Window:** ±10% = 50,175 to 61,285 counts

### P-Mode (Perpendicular Polarization)
- **Target:** 80% of max_counts = 52,428 counts
- **Tolerance:** ±5% = ±2,621 counts
- **Acceptance Window:** 49,151 to 55,705 counts (93.75% to 106.25% of target)
- **Near Window:** ±10% = 47,185 to 57,671 counts

**Why Different Targets?**
- P-mode has **weaker signal** due to perpendicular polarization
- Lower target (80% vs 85%) provides more headroom to avoid saturation
- Ensures convergence success even with challenging optical conditions

---

## 4. Integration Time Management

### Time Budget Constraints
- **Max Integration per Scan:** 60 ms
- **Scans per Spectrum:** 3
- **Total Time Budget:** 180 ms per spectrum

**Configured in:** `affilabs/utils/calibration_helpers.py`
```python
max_int_ms = int(getattr(usb, "max_integration_ms", 60))  # Default 60ms
```

### Integration Time Adjustments

**Increase Integration When:**
1. **Maxed LED Below Threshold** (lines 455-490)
   - Any channel at LED=255 AND signal < acceptance threshold
   - Increase by 2× (capped at 60ms max)
   - Purpose: Extract more signal when LED power exhausted

2. **Saturation with Room to Grow** (adaptive logic)
   - Model predicts safe integration increase
   - Uses slope estimation to avoid overshooting

**Decrease Integration When:**
1. **Pixel Saturation Detected** (any channel has sat_pixels > 0)
   - Reduce by 0.7× multiplier
   - Purpose: Eliminate saturation immediately
   - Zero-tolerance policy on saturated pixels

### Integration Time Bounds
- **Minimum:** 5 ms (detector hardware limit)
- **Maximum:** 60 ms (time budget constraint)
- **Clamping:** Applied after every adjustment

---

## 5. LED Adjustment Strategy

### Channel Prioritization
Channels are classified each iteration:

1. **LOCKED** (5.0% tolerance & zero saturation)
   - Within acceptance window AND no saturated pixels
   - LED intensity frozen (not adjusted)
   - Represents converged channels

2. **PRIORITY** (saturating OR >10% away from target)
   - Has saturated pixels OR outside near window
   - Adjusted first with larger steps
   - Critical channels requiring immediate correction

3. **NEAR** (within 10% but outside tolerance, zero saturation)
   - Close to target but needs fine-tuning
   - Adjusted with smaller steps
   - Lower priority than PRIORITY channels

### LED Step Sizes
**Priority Channels:**
```python
step = 50  # Large steps for channels far from target or saturating
```

**Near Channels:**
```python
step = 10  # Fine-tuning steps for channels close to target
```

### LED Adjustment Direction
- **Signal Too Low:** Increase LED intensity
- **Signal Too High or Saturating:** Decrease LED intensity
- **Model-Based Prediction:** Uses calibrated slopes (counts/LED) to estimate required change

---

## 6. Convergence Criteria

### Success Conditions (ALL must be true)
1. **All channels in acceptance window**
   - signal ≥ min_signal (93.75% of target)
   - signal ≤ max_signal (106.25% of target)

2. **Zero pixel saturation across ALL channels**
   - sat_pixels == 0 for every channel
   - No tolerance for any saturated pixels

3. **Locked channels stable**
   - Channels marked LOCKED remain unchanged
   - No oscillation or instability

### Failure Conditions
- **Max iterations reached** (default: 15)
- **Measurement failure** (spectrum acquisition error)
- **Timeout** (stuck in saturation loop or oscillation)

---

## 7. Special Cases & Edge Handling

### Case 1: Maxed LED Detection
**Trigger:** Channel at LED=255 AND signal < acceptance threshold

**Action:**
1. Log warning: "Channels at max LED but below acceptance threshold"
2. Increase integration time by 2×
3. Clamp to max_integration_time (60ms)
4. If already at max integration → log warning, continue iterating

**Code:** `led_convergence_algorithm.py` lines 455-490

### Case 2: Saturation Trap
**Problem:** Integration too high → saturation, integration too low → weak signal

**Current Behavior:**
- Oscillates between saturation and low signal
- Eventually fails after max iterations
- **Known Issue:** Needs better escape strategy

**Future Improvement:** Implement LED-based saturation recovery (reduce LEDs instead of integration)

### Case 3: Weak Channel Dominance
**Problem:** Weakest channel limits all others (must increase integration, others saturate)

**Current Behavior:**
- Integration increases until weakest channel acceptable
- Strong channels may saturate during process
- Saturation triggers integration reduction
- Can lead to oscillation

**Future Improvement:** Lock weakest channel at LED=255, reduce other LEDs independently

### Case 4: High Sensitivity Device
**Problem:** Device saturates at low integration times (≤20ms)

**Current Mitigation:**
- Integration cap enforced (60ms max)
- Saturation detection triggers immediate reduction
- May still struggle with very sensitive devices

**Future Improvement:** Sensitivity classification with integration caps (HIGH devices capped at 20ms)

---

## 8. Algorithm Flow

### Initialization
```
1. Set initial integration time (from S-mode or model prediction)
2. Set initial LED intensities (from model or equal distribution)
3. Initialize convergence tracking (iteration counter, previous states)
```

### Main Loop (Iterations 1 to max_iterations)
```
FOR each iteration:
    
    STEP 1: Measure All Channels
        - Turn on LED for channel
        - Acquire spectrum at current integration time
        - Extract top-50 signal
        - Count saturated pixels
        - Turn off LED
    
    STEP 2: Check Early Saturation
        - If saturation detected → reduce integration by 0.7×
        - Restart iteration (skip to next iteration)
    
    STEP 3a: Check Convergence
        - All channels in acceptance window?
        - Zero saturation across all channels?
        - If YES → SUCCESS, exit loop
    
    STEP 3b: Classify Channels
        - LOCKED: in tolerance & no saturation
        - PRIORITY: saturating OR >10% from target
        - NEAR: within 10% but outside tolerance
    
    STEP 3c: Check Maxed LEDs Below Threshold
        - Any channel at LED=255 AND signal < acceptance?
        - If YES → increase integration by 2×
        - Restart iteration
    
    STEP 4: Adjust LEDs
        - For PRIORITY channels: ±50 LED step
        - For NEAR channels: ±10 LED step
        - Clamp LEDs to [0, 255]
        - Keep LOCKED channels unchanged
    
    STEP 5: Log Iteration Results
        - Current integration time
        - Channel signals and saturation status
        - Channel classifications (LOCKED/PRIORITY/NEAR)
        - LED adjustments
    
END LOOP

IF converged:
    RETURN (integration_time, final_signals, success=True)
ELSE:
    RETURN (integration_time, final_signals, success=False)
```

---

## 9. Model-Based Optimization

### LED Calibration Model
When available, the algorithm uses pre-calibrated **model slopes** to predict LED requirements:

```python
slope = counts_per_LED_at_10ms  # e.g., 56.4 for channel A
```

**Model Formula:**
```
signal = slope × LED × (integration_time / 10.0)
```

**Usage:**
1. **Initial LED Calculation:**
   ```python
   optimal_LED = target_signal / (slope × integration_time / 10.0)
   ```

2. **Integration Time Optimization:**
   - Calculate integration for weakest channel at LED=255
   - Ensures fastest convergence (weakest channel maxed)

3. **LED Adjustment Prediction:**
   - Predict required LED change based on signal deficit
   - Reduces trial-and-error iterations

### Model Files
- **Location:** `affilabs/config/devices/{SERIAL}/led_model.json`
- **Structure:**
  ```json
  {
    "s_mode": {"a": 56.4, "b": 128.1, "c": 151.2, "d": 45.8},
    "p_mode": {"a": 60.2, "b": 135.7, "c": 160.1, "d": 48.9}
  }
  ```

---

## 10. Configuration Parameters

### Core Settings (`led_convergence_core.py`)
```python
class DetectorParams:
    max_counts: float = 65535              # Detector ADC maximum
    saturation_threshold: float = 65535    # 100% of max (hard limit)
    min_integration_time: float = 5.0      # Hardware minimum (ms)
    max_integration_time: float = 60.0     # Time budget constraint (ms)
```

### Convergence Settings (`convergence/config.py`)
```python
# Tolerance
TOLERANCE_PERCENT = 0.05           # ±5% acceptance window

# LED Steps
LED_STEP_LARGE = 50                # Priority channel adjustments
LED_STEP_SMALL = 10                # Near channel fine-tuning

# Integration Adjustments
INTEGRATION_INCREASE_FACTOR = 2.0  # Multiply by 2× when maxed LED
INTEGRATION_DECREASE_FACTOR = 0.7  # Multiply by 0.7× when saturating

# Iteration Limits
MAX_ITERATIONS = 15                # Maximum convergence attempts
```

### Target Percentages (`calibration_orchestrator.py`)
```python
# S-Mode
s_target_percent = 0.85            # 85% of max_counts

# P-Mode  
p_target_percent = 0.80            # 80% of max_counts (lower for safety)
```

---

## 11. Logging & Diagnostics

### Iteration Logs
Each iteration logs:
```
--- Iteration 3/15 @ 47.7ms ---
  A: LED=225    45915 counts ( 87.6% of target) [SAT=357px]
  B: LED=127    51048 counts ( 97.4% of target) [SAT=984px]
  C: LED=115    35404 counts ( 67.5% of target) [SAT=538px]
  D: LED=255    26744 counts ( 51.0% of target) [SAT=467px]
  
  Acceptance window: 49151..55705 counts (93.75%..106.25% of target)
  Near window: 47185..57671 counts (10.0% of target)
  
  LOCKED (5.0% & no sat): [none]
  PRIORITY (sat or >10%): [A, B, C, D]
  NEAR (within 10% but outside tolerance): [none]
  SATURATING: [A, B, C, D]
  
  Reducing integration time: 95.4ms → 66.8ms (saturation: 2346px)
```

### Debug Information
- Channel-by-channel signal and saturation
- Acceptance/near window boundaries
- Channel classifications
- LED adjustment calculations
- Integration time changes with reasoning

---

## 12. Known Limitations & Future Work

### Current Limitations

1. **Saturation Trap**
   - Can oscillate between saturation and low signal
   - No sophisticated escape strategy
   - May fail after max iterations

2. **Weak Channel Bottleneck**
   - Weakest channel forces high integration
   - Strong channels saturate as consequence
   - No independent LED adjustment for strong channels

3. **Fixed Step Sizes**
   - 50/10 LED steps may overshoot or undershoot
   - No adaptive step sizing based on distance from target

4. **No Sensitivity Classification**
   - High-sensitivity devices (saturate ≤20ms) not detected
   - No automatic integration capping for high-sensitivity cases

### Planned Improvements

1. **Weakest Channel Protection** (HIGH PRIORITY)
   - When weakest channel locked at LED=255, reduce other LEDs instead of integration
   - Prevents saturation in strong channels
   - Enables convergence in mixed-sensitivity scenarios

2. **Sensitivity Detection** (MEDIUM PRIORITY)
   - Classify device as HIGH/BASELINE sensitivity in early iterations
   - Cap integration at 20ms for HIGH sensitivity devices
   - Documented in `CONVERGENCE_MIGRATION_PLAN.md`

3. **Adaptive Margin & Boundaries** (MEDIUM PRIORITY)
   - Near window margin adjusts based on tolerance
   - Prevents logical inconsistencies
   - Better handling of edge cases

4. **Model-Based Recovery** (LOW PRIORITY)
   - Use slopes to predict saturation-safe integration
   - Calculate optimal LED distribution before iteration
   - Reduce trial-and-error cycles

---

## 13. Testing & Validation

### Test Cases

**1. Normal Convergence**
- All channels reach acceptance window
- Zero saturation in final state
- Converges within 5-8 iterations

**2. Weak Channel (D) Maxed**
- Channel D at LED=255, signal below threshold
- Integration increases to compensate
- Other channels stay below saturation

**3. High Saturation**
- Multiple channels saturate at high integration
- Integration reduces progressively
- Eventually finds saturation-free state

**4. P-Mode Lower Target**
- P-mode converges to 80% target
- Avoids saturation better than 85% target
- Maintains consistency with S-mode approach

### Success Metrics
- **Convergence Rate:** >95% success in production devices
- **Iteration Count:** Average 6-8 iterations for S-mode, 8-10 for P-mode
- **Signal Consistency:** All channels within ±5% of target
- **Saturation Rate:** 0% saturated pixels in final state

---

## 14. Code References

### Main Entry Point
```python
# affilabs/utils/led_convergence_algorithm.py
def LEDconverge(
    usb, ctrl, ch_list,
    led_intensities: dict,
    acquire_raw_spectrum_fn,
    roi_signal_fn,
    initial_integration_ms: float,
    target_percent: float = 0.85,
    tolerance_percent: float = 0.05,
    detector_params: DetectorParams,
    wave_min_index: int,
    wave_max_index: int,
    max_iterations: int = 15,
    step_name: str = "",
    use_batch_command: bool = True,
    model_slopes: dict = None,
    polarization: str = "S",
    config: ConvergenceConfig = None,
    logger = None,
) -> Tuple[float, dict, bool]:
```

### Measurement Function
```python
# affilabs/utils/led_convergence_core.py
def measure_channel(
    usb, ctrl, channel: str,
    led_intensity: int,
    integration_ms: float,
    acquire_spectrum_fn,
    roi_signal_fn,
    wave_min_index: int,
    wave_max_index: int,
    saturation_threshold: float,
    use_batch: bool,
) -> Tuple[Optional[float], int, Optional[object]]:
```

### Convergence Check
```python
# affilabs/utils/led_convergence_core.py
def check_convergence(
    signals: Dict[str, float],
    sat_per_ch: Dict[str, int],
    target_signal: float,
    tolerance_signal: float,
    config: Optional[ConvergenceConfig] = None,
) -> Tuple[bool, List[str], List[str]]:
```

---

## 15. Production Configuration

### Device-Specific Settings
Each device has calibrated parameters in:
```
affilabs/config/devices/{SERIAL}/
├── device_config.json      # Hardware settings (servo positions, fiber, etc.)
├── led_model.json          # Model slopes for LED prediction
└── led_calibration.json    # Final calibrated LED intensities
```

### Global Settings
```python
# affilabs/convergence/config.py
TOLERANCE_PERCENT = 0.05           # ±5%
PARALLEL_MEASUREMENTS = False      # Sequential channel measurement
MAX_MEASURE_WORKERS = 1            # Single-threaded
MEASUREMENT_TIMEOUT_S = 30.0       # Per-channel timeout
```

---

## 16. Change Log

### Version 1.0 (December 18, 2025)
- **Fixed:** ROI signal method from median to top_n_mean (top 50 pixels)
- **Fixed:** Integration time cap set to 60ms (time budget constraint)
- **Fixed:** P-mode target set to 80% (was 75%, reverted to 80%)
- **Fixed:** Servo initialization order (device_config loaded before servo init)
- **Fixed:** Misleading PWM labels changed to degrees
- **Documented:** Golden reference for current convergence algorithm

---

## Appendix A: Glossary

- **ROI (Region of Interest):** Spectral range used for signal measurement
- **Top 50 Pixels:** Average of 50 highest-intensity pixels in ROI
- **Saturation:** Detector pixel at maximum counts (65535)
- **Acceptance Window:** ±5% tolerance around target signal
- **Near Window:** ±10% range around target (wider than acceptance)
- **LOCKED Channel:** In acceptance window with zero saturation
- **PRIORITY Channel:** Saturating or >10% away from target
- **NEAR Channel:** Within 10% but outside tolerance, no saturation
- **Integration Time:** Detector exposure time per scan (milliseconds)
- **LED Intensity:** PWM value 0-255 controlling LED brightness
- **Model Slope:** Calibrated counts/LED ratio at 10ms integration
- **Time Budget:** 180ms total per spectrum (60ms × 3 scans)

---

## Appendix B: Mathematical Formulas

### Signal Prediction
```
signal = slope × LED × (integration_time / 10.0)
```

### Optimal LED Calculation
```
LED_optimal = target_signal / (slope × integration_time / 10.0)
```

### Acceptance Window
```
min_signal = target_signal × (1 - tolerance_percent)  # 93.75% of target
max_signal = target_signal × (1 + tolerance_percent)  # 106.25% of target
```

### Near Window
```
near_lower = target_signal × 0.90  # 90% of target
near_upper = target_signal × 1.10  # 110% of target
```

### Integration Adjustments
```
# When saturating
new_integration = current_integration × 0.7

# When maxed LED below threshold
new_integration = current_integration × 2.0

# Always clamp
new_integration = clamp(new_integration, min_integration, max_integration)
```

---

**End of Document**

This reference document represents the current production state of the LED convergence algorithm as of December 18, 2025. All future improvements should reference this document as the baseline.
