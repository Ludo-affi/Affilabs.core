# Optical Calibration Workflow Optimization

**Date**: 2025-11-23
**Status**: ✅ Implemented
**Impact**: Saves ~30 minutes in OEM calibration workflow

---

## Problem Statement

When running OEM calibration (LED + optical calibration), the original workflow was:

1. **Run LED calibration** (30 min)
2. **Run optical calibration** (5-10 min)
3. **Re-run LED calibration** to use the new optical correction (30 min)

**Total time**: ~65-70 minutes with redundant LED calibration

---

## Solution: Check and Optimize Workflow Order

### Smart Detection
Before starting OEM calibration, check if `optical_calibration.json` exists:

```python
from utils.device_integration import get_device_optical_calibration_path
optical_cal_path = get_device_optical_calibration_path()

if not optical_cal_path or not optical_cal_path.exists():
    # File missing - offer optimized workflow
```

### User Dialog
If optical calibration is missing, show optimization dialog:

```
┌─────────────────────────────────────────────┐
│  Optimize Calibration Order?                │
├─────────────────────────────────────────────┤
│  Optical calibration file not found.        │
│                                              │
│  RECOMMENDED: Run optical calibration       │
│  FIRST (5-10 min), then LED calibration     │
│  can use it immediately.                    │
│                                              │
│  Alternative: Run LED calibration now,      │
│  then optical calibration separately        │
│  (requires re-calibration later).           │
│                                              │
│  Run optical calibration first?             │
│                                              │
│  [ Yes (Recommended) ]  [ No ]              │
└─────────────────────────────────────────────┘
```

### Optimized Workflow
If user selects "Yes":

1. **Run optical calibration first** (5-10 min)
2. **Automatically trigger LED calibration** (30 min)
   → LED calibration immediately uses the new optical correction

**Total time**: ~35-40 minutes (saves 30 minutes!)

---

## Implementation Details

### File Modified
`main_simplified.py`

### New Method
```python
def _run_afterglow_then_led_calibration(self):
    """Run afterglow measurement first, then automatically trigger LED calibration.

    This is the optimized workflow when optical calibration is missing.
    Running afterglow first (5-10 min) means LED calibration can immediately
    use the correction data, avoiding the need to re-run LED calibration later.
    """
```

### Workflow Steps

1. **Check for optical calibration file**:
   ```python
   optical_cal_path = get_device_optical_calibration_path()
   if not optical_cal_path or not optical_cal_path.exists():
       # Offer optimized workflow
   ```

2. **Show optimization dialog** with recommendation

3. **If user chooses optimized path**:
   - Run `measure_afterglow()` in background thread
   - Show progress dialog (non-blocking)
   - On completion, automatically trigger `data_mgr.start_calibration()`

4. **If user declines**:
   - Continue with standard LED calibration only
   - User can run optical calibration later (but will need to re-calibrate LEDs)

---

## Benefits

### Time Savings
- **Old workflow**: 65-70 minutes (with redundant LED calibration)
- **New workflow**: 35-40 minutes (optimized order)
- **Savings**: ~30 minutes per OEM calibration session

### User Experience
- **Intelligent guidance**: System recommends optimal workflow
- **Transparency**: User understands the time tradeoff
- **Flexibility**: User can still choose to skip if desired

### Technical
- **No code duplication**: Reuses existing `measure_afterglow()` function
- **Clean integration**: Fits naturally into calibration coordinator flow
- **Backwards compatible**: If file exists, no dialog shown

---

## Usage Scenarios

### Scenario 1: New Device (No Optical Calibration)
**User**: Clicks "Run Optical Calibration..." in Advanced Settings

**System**:
1. Detects missing optical calibration file
2. Shows optimization dialog
3. Recommends running optical calibration first
4. User accepts → runs optimized workflow (35-40 min)

**Result**: Device fully calibrated in one session

---

### Scenario 2: Existing Device (Has Optical Calibration)
**User**: Clicks "Run Optical Calibration..." in Advanced Settings

**System**:
1. Detects existing optical calibration file
2. No dialog shown
3. Proceeds directly with LED calibration
4. LED calibration uses existing optical correction

**Result**: Standard workflow, no interruption

---

### Scenario 3: User Declines Optimization
**User**: Clicks "Run Optical Calibration..." → Declines optimized workflow

**System**:
1. Runs LED calibration only (30 min)
2. User can manually run optical calibration later
3. System logs: "ℹ️ User chose to skip optical calibration for now"

**Result**: User has flexibility, but may need re-calibration later

---

## Code Flow

```
┌──────────────────────────────────────────┐
│ User clicks "Run Optical Calibration"   │
└───────────────┬──────────────────────────┘
                │
                ▼
        ┌───────────────────┐
        │ Hardware ready?   │
        └────┬──────────┬───┘
             │          │
            No         Yes
             │          │
             ▼          ▼
        [Error]  ┌─────────────────────────┐
                 │ Optical cal file exists?│
                 └─────┬──────────┬────────┘
                       │          │
                      No         Yes
                       │          │
                       ▼          ▼
            ┌──────────────┐  [Skip dialog]
            │ Show dialog  │       │
            └──────┬───────┘       │
                   │               │
          ┌────────┴────────┐      │
          │                 │      │
         Yes               No      │
          │                 │      │
          ▼                 ▼      ▼
  ┌──────────────┐   ┌───────────────────┐
  │Run afterglow │   │ Run LED calibration│
  │   (5-10 min) │   │     (30 min)       │
  └──────┬───────┘   └────────────────────┘
         │
         ▼
  ┌──────────────────┐
  │ Auto-trigger LED │
  │  calibration     │
  │   (30 min)       │
  └──────────────────┘
```

---

## Future Enhancements

### Potential Improvements

1. **Progress Callback Integration**
   - Show real-time progress for afterglow measurement
   - Update dialog with current channel being measured

2. **Cancellation Support**
   - Allow user to cancel afterglow measurement
   - Clean up partial results on cancel

3. **Smart Re-calibration Detection**
   - If optical calibration changes significantly, prompt to re-run LED calibration
   - Compare old vs new optical calibration checksums

4. **Batch Processing**
   - Support multiple devices in sequence
   - Generate calibration reports for QA tracking

---

## Testing

### Test Cases

1. **New Device**:
   - Delete optical calibration file
   - Run OEM calibration
   - Verify dialog appears
   - Accept optimization
   - Verify afterglow runs first, then LED calibration

2. **Existing Device**:
   - Ensure optical calibration file exists
   - Run OEM calibration
   - Verify no dialog (direct LED calibration)

3. **User Decline**:
   - Delete optical calibration file
   - Run OEM calibration
   - Decline optimization
   - Verify LED calibration runs without afterglow

4. **Error Handling**:
   - Simulate afterglow import error
   - Verify graceful error message
   - Verify system remains stable

---

## Related Files

- `main_simplified.py`: Dialog and workflow logic
- `afterglow_measurement.py`: Optical calibration measurement
- `data_acquisition_manager.py`: LED calibration
- `utils/device_integration.py`: File path utilities

---

## Deployment Notes

### User-Facing Changes
- **Visible**: New optimization dialog for OEM users
- **Hidden**: Improved workflow efficiency
- **Impact**: Positive (saves time, improves UX)

### Rollout Strategy
- **Target**: OEM/factory users only (DEV=False hides feature from end-users)
- **Training**: Update OEM calibration guide with new workflow
- **Support**: Emphasize time savings in release notes

---

## Success Metrics

- **Time reduction**: ~30 minutes per OEM calibration
- **User adoption**: % of users accepting optimized workflow
- **Error rate**: Track any workflow-related issues
- **Feedback**: Collect OEM user satisfaction data

---

## Conclusion

This optimization provides significant time savings for OEM calibration workflows while maintaining flexibility and backwards compatibility. The intelligent detection and user-friendly dialog ensure a smooth transition with minimal training required.

**Key Benefit**: What used to take 70 minutes now takes 40 minutes, with better data quality from the start.
