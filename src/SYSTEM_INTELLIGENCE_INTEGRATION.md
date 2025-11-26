# System Intelligence Integration Guide

## Overview

The System Intelligence module provides ML-driven operational guidance and troubleshooting. It monitors the entire instrument and provides actionable recommendations.

## Architecture

```
System Intelligence (core/system_intelligence.py)
    ↓
Observes all subsystems:
├─ Calibration Manager → Quality scores, failures
├─ Data Acquisition Manager → Signal quality, SNR
├─ Hardware Manager → LED health, detector status
├─ Buffer Manager → Data flow, processing delays
└─ Main Controller → User actions, errors
    ↓
Analyzes patterns:
├─ Rule-based diagnostics (immediate)
└─ ML pattern learning (future enhancement)
    ↓
Provides guidance:
├─ Real-time issue detection
├─ Troubleshooting recommendations
├─ Predictive maintenance alerts
└─ Session diagnostic reports
```

## Key Features

### 1. Operational Pattern Recognition
- **Normal vs Abnormal Behavior**: Learns baseline metrics
- **Drift Detection**: Tracks calibration drift over time
- **Quality Trends**: Monitors signal quality degradation

### 2. Automated Troubleshooting
- **Issue Classification**: Optical, detector, calibration, thermal, fluidics, data quality
- **Severity Levels**: Info, Warning, Error, Critical
- **Root Cause Analysis**: Symptoms → Probable causes → Actions

### 3. Predictive Maintenance
- **LED Degradation Tracking**: Per-channel intensity monitoring
- **Calibration Drift Forecasting**: Predict when recalibration needed
- **Component Health**: Dark noise, saturation, thermal stability

### 4. Calibration Quality Assessment
- **Per-channel quality scores**: Validates calibration effectiveness
- **Failure pattern analysis**: All-channel vs single-channel failures
- **Success rate tracking**: Historical calibration performance

## Integration Points

### Calibration Manager Integration

**In `calibration_manager.py` after calibration:**

```python
from core.system_intelligence import get_system_intelligence

# After calibration completes
si = get_system_intelligence()
si.update_calibration_metrics(
    success=all_passed,
    quality_scores={ch: score for ch, score in quality_scores.items()},
    failed_channels=failed_channels if not all_passed else None
)
```

### Data Acquisition Manager Integration

**In `data_acquisition_manager.py` during spectrum processing:**

```python
from core.system_intelligence import get_system_intelligence

# After processing each spectrum
si = get_system_intelligence()
si.update_signal_quality(
    channel=channel,
    snr=calculated_snr,
    peak_wavelength=resonance_wavelength,
    transmission_quality=transmission_spectrum_quality
)

# After LED intensity measurement
si.update_led_health(
    channel=channel,
    intensity=measured_intensity,
    target=target_intensity
)
```

### Main Application Integration

**In `main_simplified.py` or main controller:**

```python
from core.system_intelligence import get_system_intelligence

class MainApplication:
    def __init__(self):
        self.system_intelligence = get_system_intelligence()

        # Periodic health check (every 30 seconds)
        self.health_check_timer = QTimer()
        self.health_check_timer.timeout.connect(self._check_system_health)
        self.health_check_timer.start(30000)  # 30 sec

    def _check_system_health(self):
        """Periodic system health check."""
        state, issues = self.system_intelligence.diagnose_system()

        # Update UI status indicator
        self._update_status_indicator(state)

        # Show critical issues as notifications
        critical_issues = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
        for issue in critical_issues:
            self._show_notification(issue.title, issue.description)

    def _on_session_end(self):
        """Generate diagnostic report at session end."""
        report_path = self.system_intelligence.save_session_report()
        logger.info(f"Session report saved: {report_path}")
```

## UI Integration Recommendations

### Status Indicator Widget
```
┌─────────────────────────┐
│ System Status: ●        │
│ ○ Healthy               │
│ ○ Degraded (1 warning)  │
│ ○ Error (2 issues)      │
└─────────────────────────┘
```

### Troubleshooting Panel
```
┌──────────────────────────────────────────┐
│ Active Issues (2)                        │
├──────────────────────────────────────────┤
│ ⚠️ Low SNR on Channel A                  │
│   Confidence: 90%                        │
│   Symptoms:                              │
│   • Noisy baseline                       │
│   • Poor peak resolution                 │
│   Recommended Actions:                   │
│   1. Recalibrate LED intensities         │
│   2. Check for light leaks               │
│   [Details] [Resolve]                    │
├──────────────────────────────────────────┤
│ ⚠️ LED Degradation - Channel B           │
│   ...                                    │
└──────────────────────────────────────────┘
```

### Maintenance Dashboard
```
┌──────────────────────────────────────────┐
│ Maintenance Recommendations              │
├──────────────────────────────────────────┤
│ 🔴 High Priority (< 2 hours)             │
│   • Calibration drift detected           │
│     Action: Recalibrate system           │
│                                          │
│ 🟡 Medium Priority (< 24 hours)          │
│   • LED maintenance - Channel B          │
│     Action: Inspect LED PCB              │
│                                          │
│ 📊 System Uptime: 24.5 hours             │
│ 📈 Calibration Success Rate: 95%         │
└──────────────────────────────────────────┘
```

## Example Usage Flow

### 1. System Startup
```python
si = get_system_intelligence()
# Intelligence layer initialized
```

### 2. During Calibration
```python
# Calibration runs...
si.update_calibration_metrics(
    success=True,
    quality_scores={'a': 0.92, 'b': 0.88, 'c': 0.65, 'd': 0.91},
    failed_channels=None
)
# → Intelligence detects Channel C low quality
# → Creates WARNING: "Low Calibration Quality"
# → Recommends: Clean fiber, check LED
```

### 3. During Live Acquisition
```python
# Each spectrum processed...
si.update_signal_quality('a', snr=12.5, peak=637.2, quality=0.85)
si.update_led_health('a', intensity=28500, target=30000)
# → Intelligence monitors trends
# → Detects LED degradation if intensity drops
```

### 4. User Requests Diagnosis
```python
state, issues = si.diagnose_system()
# Returns: (SystemState.DEGRADED, [issue1, issue2, ...])
```

### 5. Session End
```python
report_path = si.save_session_report()
# Saves JSON report with:
# - Session metrics
# - Issue history
# - Maintenance recommendations
```

## Future Enhancements

### ML Pattern Learning (Phase 2)
- **Training Data Collection**: Store operational metrics and outcomes
- **Anomaly Detection**: Learn normal patterns, flag deviations
- **Predictive Models**: Forecast component failures before they occur
- **Adaptive Thresholds**: Learn site-specific normal ranges

### Integration Points for ML:
```python
class SystemIntelligence:
    def _train_anomaly_detector(self, metrics_history):
        """Train unsupervised anomaly detection model."""
        # Isolation Forest or Autoencoder
        pass

    def _predict_failure(self, component: str) -> Tuple[float, int]:
        """Predict probability and time-to-failure."""
        # Survival analysis or LSTM time series
        pass

    def _learn_from_feedback(self, issue_id: str, was_helpful: bool):
        """Update confidence scores based on user feedback."""
        # Reinforcement learning
        pass
```

### Operational Scenario Classification (Phase 2)
```python
class OperationalScenario(Enum):
    NORMAL = "normal"
    BINDING_EVENT = "binding_event"
    DRIFT = "drift"
    OPTICAL_LEAK = "optical_leak"
    BUBBLE = "bubble"
    HARDWARE_FAILURE = "hardware_failure"

def classify_scenario(metrics: Dict) -> Tuple[OperationalScenario, float]:
    """Classify current operational scenario."""
    # Decision tree or neural network
    pass
```

## Configuration

Add to `config.py`:
```python
# System Intelligence
SYSTEM_INTELLIGENCE_ENABLED = True
HEALTH_CHECK_INTERVAL_SEC = 30
ISSUE_CONFIDENCE_THRESHOLD = 0.7  # Only report issues above 70% confidence
AUTO_SAVE_REPORTS = True
REPORT_SAVE_INTERVAL_MIN = 60
```

## Testing

### Unit Tests
```python
def test_calibration_failure_detection():
    si = SystemIntelligence()
    si.update_calibration_metrics(
        success=False,
        quality_scores={},
        failed_channels=['a', 'b', 'c', 'd']
    )
    state, issues = si.diagnose_system()
    assert state == SystemState.ERROR
    assert any('All Channels' in i.title for i in issues)
```

### Integration Tests
```python
def test_full_session_workflow():
    si = SystemIntelligence()
    # Simulate session with various issues
    # Verify recommendations generated
    # Check report generation
```

## Deployment Checklist

- [ ] Add `system_intelligence.py` to `core/` directory
- [ ] Integrate with `calibration_manager.py` (update_calibration_metrics)
- [ ] Integrate with `data_acquisition_manager.py` (update_signal_quality, update_led_health)
- [ ] Add UI status indicator in main window
- [ ] Add troubleshooting panel (optional, Phase 2)
- [ ] Add health check timer in main application
- [ ] Add configuration parameters to `config.py`
- [ ] Test with real hardware session
- [ ] Generate and review first diagnostic report
- [ ] Document for users

## Benefits

1. **Proactive Issue Detection**: Catch problems before they cause experiment failure
2. **Guided Troubleshooting**: Reduce debug time with actionable recommendations
3. **Predictive Maintenance**: Schedule maintenance before component failure
4. **Operational Learning**: System gets smarter with usage
5. **Quality Assurance**: Automatic validation of calibration and data quality
6. **Audit Trail**: Complete session history for troubleshooting and compliance

## Support

For questions or feature requests related to System Intelligence:
- Review diagnostic reports in `generated-files/system_intelligence/`
- Check logger output for intelligence warnings
- Examine issue metrics for quantitative diagnostics
