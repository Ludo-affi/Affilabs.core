# ML Model Improvement & Retraining Strategy

## Current Issues

1. **Feature Mismatch** (CRITICAL):
   - Model trained with: 33 features (19 base + 14 device-specific)
   - Inference provides: 19 features only
   - Error: `X has 19 features, but RandomForestClassifier is expecting 33`

2. **Device Overfitting**:
   - Model relies on device history which makes it device-specific
   - New devices or devices with little history get poor predictions
   - Reduces model generalization

3. **Oscillation Issue**:
   - Convergence almost worked (85-90% of target at iteration 8)
   - Algorithm improvements (conservative scaling) are now in place
   - Model may now be unnecessary or less critical

## Recommended Strategy

### Option A: Retrain Generic Model (RECOMMENDED)
**Best for production deployment**

```bash
# 1. Retrain WITHOUT device features (generic model)
cd tools/ml_training
python train_convergence_predictor.py --no-device-features

# 2. Test on new data (including your latest run)
python test_model.py --model convergence_predictor_generic.joblib
```

**Advantages:**
- ✅ Works with new devices immediately
- ✅ No feature mismatch issues
- ✅ Simpler inference (19 features only)
- ✅ More robust generalization

**Changes needed:**
- Modify `train_convergence_predictor.py` line 119: `use_device_features=False`
- Save as `convergence_predictor_generic.joblib`
- Update `engine.py` to load generic model

### Option B: Fix Feature Mismatch (Keep Device Features)
**Best for maximum accuracy on known devices**

Add device feature extraction to `engine.py` at iteration 1:

```python
# At line 476 in engine.py, extend X_conv with device features:
X_conv = [
    # ... existing 19 features ...

    # Device history features (14 additional)
    device_stats.get('device_total_calibrations', 0),
    device_stats.get('device_success_rate', 0.5),  # Default to 50%
    device_stats.get('device_avg_s_iterations', 6.0),  # Default average
    # ... etc (see train_convergence_predictor.py lines 146-162)
]
```

**Advantages:**
- ✅ Higher accuracy for devices with history
- ✅ Learns device-specific patterns

**Disadvantages:**
- ❌ Requires device history database infrastructure
- ❌ New devices get poor predictions
- ❌ More complex deployment

### Option C: Disable ML Convergence Predictor (SIMPLEST)
**Best for immediate deployment**

The convergence predictor is now **less critical** because:
1. Algorithm improvements (conservative scaling) fixed the oscillation
2. It only runs at iteration 1 (early prediction)
3. Your calibration got to 85-90% without it

```python
# In engine.py line 137, disable loading:
if convergence_predictor_path:
    # Disabled - algorithm improvements make this less critical
    self.convergence_predictor = None
    self._log("info", "[ML] Convergence predictor disabled (algorithm-only mode)")
```

**Advantages:**
- ✅ No feature mismatch
- ✅ Simpler code
- ✅ Faster inference
- ✅ Algorithm improvements already fixed oscillation

## Retraining Data Collection

### Add Your Latest Run
Your calibration that reached 85-90% is **valuable training data**:

```bash
# 1. Parse your latest log
python parse_calibration_logs.py --log logs/calibration_2026-01-06_20-12.log

# 2. Label it as "almost converged" (85% threshold)
python record_calibration_result.py \
    --serial 65535 \
    --success partial \
    --log logs/calibration_2026-01-06_20-12.log \
    --note "Reached 85-90%, failed due to aggressive scaling"

# 3. Retrain with updated data
python train_all_models.py
```

### Training Data Requirements

For good generalization, you need:
- **Minimum**: 50 calibration runs
- **Recommended**: 200+ runs across 5+ devices
- **Ideal**: 500+ runs across 10+ devices

Current data check:
```bash
# Check training data size
python -c "
import pandas as pd
df = pd.read_csv('training_data/iterations.csv')
print(f'Total runs: {df[\"log_file\"].nunique()}')
print(f'Total devices: {df[\"detector_serial\"].nunique()}')
print(f'Success rate: {df.groupby(\"log_file\")[\"success\"].first().mean():.1%}')
"
```

## Feature Engineering Improvements

### 1. Add Physical Constraints
```python
# In train_convergence_predictor.py, add physics-based features:
'led_headroom': 255 - initial_leds.max(),  # Room for LED increase
'integration_headroom': 60.0 - initial_integration_ms,  # Room for time increase
'saturation_risk': total_sat_pixels / (num_channels * 1000),  # Normalized risk
'initial_snr_estimate': avg_signal / signal_variance,  # Signal quality
```

### 2. Interaction Features
```python
# Capture LED-time tradeoffs:
'led_time_product': avg_initial_led * initial_integration_ms,
'balance_score': 1.0 - (led_imbalance / avg_initial_led),  # How balanced
```

### 3. Temporal Smoothing
```python
# Use moving averages to reduce noise:
'signal_trend': (signal_iter2 - signal_iter1) / signal_iter1,  # Improving?
'led_trend': (led_iter2 - led_iter1) / led_iter1,  # LED direction
```

## Model Architecture Improvements

### 1. Ensemble Approach (Advanced)
```python
# Combine multiple weak learners:
from sklearn.ensemble import VotingClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

ensemble = VotingClassifier([
    ('rf', RandomForestClassifier(n_estimators=150)),
    ('gb', GradientBoostingClassifier(n_estimators=100)),
    ('lr', LogisticRegression(max_iter=1000)),
], voting='soft')
```

### 2. Uncertainty Estimation
```python
# Get confidence scores:
proba = model.predict_proba(X_conv)[0]
confidence = max(proba)  # Highest class probability

if confidence < 0.6:
    # Low confidence - run full 12 iterations regardless
    self._log("warning", f"[ML] Low confidence ({confidence:.1%}) - running full convergence")
```

### 3. Regularization
```python
# Prevent overfitting:
RandomForestClassifier(
    n_estimators=150,
    max_depth=8,  # Reduced from 12
    min_samples_split=12,  # Increased from 8
    min_samples_leaf=5,  # Increased from 3
    max_features='sqrt',  # Auto feature selection
)
```

## Testing Strategy

### 1. Cross-Device Validation
```python
# Test on devices NOT in training set:
from sklearn.model_selection import GroupKFold

cv = GroupKFold(n_splits=5)
scores = cross_val_score(
    model, X, y,
    cv=cv,
    groups=device_serials,  # Group by device
    scoring='f1'
)
print(f"Cross-device F1: {scores.mean():.3f} ± {scores.std():.3f}")
```

### 2. Time-Based Validation
```python
# Test on recent data (last 20%):
timestamps = pd.to_datetime(df['timestamp'])
split_date = timestamps.quantile(0.8)

train_mask = timestamps <= split_date
X_train, X_test = X[train_mask], X[~train_mask]
y_train, y_test = y[train_mask], y[~train_mask]
```

### 3. Edge Case Testing
```python
# Identify failure modes:
failures = df[df['success'] == 0]
print(f"Failure analysis:")
print(f"  Avg initial LED: {failures['avg_initial_led'].mean():.1f}")
print(f"  Avg saturation: {failures['early_saturation'].mean():.1%}")
print(f"  Avg signal: {failures['avg_signal_fraction'].mean():.1%}")
```

## Recommended Action Plan

**IMMEDIATE (Next 24 hours):**
1. ✅ Algorithm improvements already done (conservative scaling)
2. 🔧 **Option C**: Disable convergence predictor (simplest fix)
3. ✅ Test calibration with algorithm-only mode

**SHORT-TERM (Next week):**
1. 📊 Collect 10+ calibration runs with new algorithm
2. 🔧 Parse logs and add to training data
3. 🤖 **Option A**: Retrain generic model (no device features)
4. ✅ Test generic model vs algorithm-only

**LONG-TERM (Next month):**
1. 📊 Collect 50+ runs across multiple devices
2. 🔧 Add physics-based features
3. 🤖 Retrain with ensemble approach
4. ✅ A/B test: ML-assisted vs algorithm-only

## Expected Results

With algorithm improvements + generic model:
- **Convergence rate**: 90-95% (up from 67%)
- **Iterations to converge**: 6-8 (down from 12+)
- **Robustness**: Works on new devices immediately
- **Failure recovery**: Algorithm-only fallback for edge cases

## Monitoring & Iteration

Add telemetry to track model performance:
```python
# In engine.py, log predictions vs outcomes:
ml_logger.log({
    'timestamp': datetime.now().isoformat(),
    'prediction': conv_prediction,
    'actual_converged': result.converged,
    'iterations_used': iteration,
    'final_error_pct': final_error,
})
```

Monthly review:
- Retrain if success rate drops below 85%
- Add new failure modes to training data
- Update features based on physics insights
