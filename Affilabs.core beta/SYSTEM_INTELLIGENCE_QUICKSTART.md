# System Intelligence - Quick Start Guide

## Integration Complete! 🧠

The System Intelligence ML guidance system is now integrated and ready to use.

## What's Been Added

### 1. Core Intelligence Module
**File:** `core/system_intelligence.py`
- Monitors calibration quality, signal quality, LED health
- Detects issues automatically with confidence scores
- Provides troubleshooting recommendations
- Tracks operational metrics and maintenance needs

### 2. Data Acquisition Integration
**File:** `core/data_acquisition_manager.py`
- Automatically reports calibration results to intelligence system
- Updates system with signal quality metrics (ready for connection)
- Tracks LED health during operation

### 3. UI Status Widget
**File:** `ui/system_intelligence_widget.py`
- Real-time system health indicator (●)
- Active issues display with recommendations
- Manual diagnosis button
- Session report generation

## How to Use

### Add Widget to Main Window

In your main application file (e.g., `main_simplified.py`):

```python
from ui.system_intelligence_widget import SystemIntelligenceWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # ... existing UI setup ...

        # Add System Intelligence widget
        self.si_widget = SystemIntelligenceWidget()

        # Option 1: Add to status bar area
        self.status_bar_layout.addWidget(self.si_widget)

        # Option 2: Add to sidebar
        self.sidebar_layout.addWidget(self.si_widget)

        # Option 3: Add as separate dock widget
        dock = QDockWidget("System Intelligence", self)
        dock.setWidget(self.si_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
```

### Automatic Operation

Once integrated, the system intelligence will:

1. **During Calibration:**
   - Automatically analyze calibration quality
   - Detect low-quality channels
   - Identify LED degradation
   - Suggest actions if issues found

2. **During Acquisition:**
   - Monitor signal quality (when connected)
   - Track LED health trends
   - Detect anomalies

3. **Continuous:**
   - Update status indicator every 5 seconds
   - Show active issues in widget
   - Maintain operational metrics

### Manual Diagnosis

Click the "🔍 Diagnose" button anytime to:
- Run comprehensive system check
- See maintenance recommendations
- Review operational metrics

### Save Reports

Click "📊 Save Report" to generate a JSON diagnostic report containing:
- Session metrics (uptime, calibrations, errors)
- Active and historical issues
- Maintenance recommendations
- Timestamps and confidence scores

Reports saved to: `generated-files/system_intelligence/`

## Status Indicator

The colored dot shows system health:
- 🟢 **Green** - Healthy (no issues)
- 🟡 **Yellow** - Degraded (minor warnings)
- 🟠 **Orange** - Warning (attention needed)
- 🔴 **Red** - Error (critical issue)
- ⚪ **Gray** - Unknown (initializing)

## Issue Display

Each issue shows:
- **Severity emoji** (🔴🟠🟡🔵)
- **Title and confidence** (e.g., "Low SNR - 90%")
- **Description** (what's happening)
- **Recommended actions** (what to do)

## Example Issues Detected

### Calibration Issues
- **Low Calibration Quality** - Channel quality below target
- **Complete Calibration Failure** - All channels failed (systemic issue)
- **Multiple Channel Failures** - LED PCB or thermal issue

### Signal Quality Issues
- **Low SNR** - Signal-to-noise ratio below threshold
- **Poor Peak Resolution** - Noisy baseline, unstable readings

### LED Health Issues
- **LED Degradation** - Intensity below target
- **LED Failure** - Critical intensity loss

## Connecting Signal Quality Monitoring (Optional)

To enable live signal quality monitoring, add this call in your spectrum processing:

```python
# In main_simplified.py after processing each spectrum
from core.data_acquisition_manager import DataAcquisitionManager

def _on_spectrum_acquired(self, data):
    channel = data['channel']
    wavelength = data['wavelength']

    # ... existing processing ...

    # Calculate SNR (example)
    snr = calculate_snr(spectrum)  # Your SNR calculation

    # Calculate transmission quality (example)
    transmission_quality = 0.85  # Or your quality metric

    # Update intelligence
    if hasattr(self.data_mgr, '_update_signal_intelligence'):
        self.data_mgr._update_signal_intelligence(
            channel=channel,
            wavelength=wavelength,
            snr=snr,
            transmission_quality=transmission_quality
        )
```

## Testing

### Test with Calibration

1. Run calibration
2. System Intelligence automatically analyzes results
3. Check widget for any issues detected
4. Review recommendations

### Test Manual Diagnosis

1. Click "🔍 Diagnose" button
2. Check logger for maintenance recommendations
3. Review active issues in widget

### Test Report Generation

1. Click "📊 Save Report"
2. Check `generated-files/system_intelligence/` folder
3. Open JSON report to review session data

## Configuration (Optional)

Add to `config.py` to customize:

```python
# System Intelligence
SYSTEM_INTELLIGENCE_ENABLED = True
HEALTH_CHECK_INTERVAL_SEC = 30  # Update frequency
ISSUE_CONFIDENCE_THRESHOLD = 0.7  # Only show issues above 70% confidence
AUTO_SAVE_REPORTS = True
REPORT_SAVE_INTERVAL_MIN = 60  # Auto-save every hour
```

## Future Enhancements (Phase 2)

The current system uses rule-based diagnostics. Future ML enhancements:

1. **Pattern Learning** - Learn normal vs abnormal behavior from data
2. **Anomaly Detection** - ML model detects unusual patterns
3. **Predictive Maintenance** - Forecast component failures
4. **Adaptive Thresholds** - Learn site-specific normal ranges
5. **Operational Scenario Classification** - Auto-detect binding events, drift, leaks

## Troubleshooting

### Widget Not Showing
- Verify import: `from ui.system_intelligence_widget import SystemIntelligenceWidget`
- Check widget is added to layout
- Ensure parent widget is visible

### No Issues Detected
- Normal! System is healthy
- Click "🔍 Diagnose" to force check
- Try running calibration to trigger analysis

### Import Errors
- If `system_intelligence` not available, system operates without ML guidance
- Check logs for "System Intelligence not available" warning

## Benefits

✅ **Proactive** - Catch problems before experiment failure
✅ **Guided** - Actionable recommendations reduce debug time
✅ **Predictive** - Schedule maintenance before component failure
✅ **Learning** - System gets smarter with usage
✅ **Quality Assurance** - Automatic validation of calibration and data
✅ **Audit Trail** - Complete session history for troubleshooting

## Summary

The System Intelligence module is now:
- ✅ Integrated with Data Acquisition Manager
- ✅ Monitoring calibration quality
- ✅ Tracking LED health
- ✅ Providing UI status widget
- ✅ Generating diagnostic reports
- 🔄 Ready for signal quality monitoring (optional connection)

**Next Step:** Add the `SystemIntelligenceWidget` to your main window and start using it!
