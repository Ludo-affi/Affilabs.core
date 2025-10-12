# Optical System Calibration - Implementation Plan

**Status**: Design & Validation Phase
**Date**: October 11, 2025
**Current**: Running comprehensive characterization (measurement 14/20)

---

## Overview

**Optical System Calibration** is a **separate, infrequent maintenance procedure** that characterizes LED phosphor afterglow behavior across multiple integration times. This is NOT part of the main 9-step calibration - it's a standalone OEM tool.

### Key Architecture Decisions ✅

**DECISION: Separate OEM Tool (Not Step 10)**

1. **Separation from main calibration**:
   - Main calibration (9 steps): Runs frequently (~daily, ~1.5 min)
   - Optical calibration: Runs rarely (~1000 hours operation, ~2-3 min)
   - Independent procedures with different purposes

2. **Correction model persistence**:
   - Optical calibration generates τ(integration_time) lookup tables **once**
   - Tables stored in `config/optical_calibration/system_SERIAL_DATE.json`
   - Correction loads existing model during measurements
   - **No need to re-run calibration** - just use existing τ tables

3. **Usage pattern**:
   - **Calibration**: Infrequent characterization (once per ~1000 hours)
   - **Correction**: Always active (loads τ tables, applies during measurements)
   - **Re-calibration**: Only when LED aging detected or hardware changed

### Why "Optical System Calibration"?

The name accurately reflects that we're calibrating the **complete optical path**:
- LED phosphor emission characteristics
- Optical fiber light collection
- Spectrometer detector response
- Integration time effects

This is NOT just "LED calibration" - it's the entire optical system's dynamic response.

---

## Files & Naming Convention

### Core Scripts

1. **`optical_system_calibration.py`** (rename from `led_afterglow_integration_time_model.py`)
   - Main calibration procedure
   - OEM-accessible, CLI-based
   - Generates system-specific correction models
   - Runtime: ~45 minutes
   - Output: `optical_system_calibration_TIMESTAMP.json`

2. **`afterglow_correction.py`**
   - Production correction module
   - Loads calibration data
   - Applies real-time correction during measurements
   - Interpolates τ for arbitrary integration times

3. **`test_optical_calibration.py`**
   - Validation suite
   - Quick-check script (~2 minutes)
   - Verifies calibration accuracy
   - Compares current system to stored calibration

### Documentation

1. **`OPTICAL_SYSTEM_CALIBRATION_GUIDE.md`**
   - Complete theory and procedure
   - OEM setup instructions
   - When to calibrate/re-calibrate
   - Troubleshooting guide

2. **`OPTICAL_CALIBRATION_IMPLEMENTATION_PLAN.md`** (this file)
   - Design decisions
   - GUI integration ideas
   - Storage strategy
   - API design

---

## OEM Workflow

### Initial System Setup (Factory/Integration)

```
1. Assemble optical system:
   ├── LED PCB installed
   ├── Optical fiber connected
   ├── Spectrometer mounted
   └── Controller connected

2. Run optical system calibration:
   $ python optical_system_calibration.py

   ✓ Tests all 4 channels (A, B, C, D)
   ✓ Tests 5 integration times (5, 10, 20, 50, 100 ms)
   ✓ 5 measurement cycles per test
   ✓ Generates calibration file

3. Store calibration data:
   ├── Save to: config/optical_calibration/
   ├── Filename: optical_cal_[SPECTROMETER_SN]_[DATE].json
   └── Link in device_config.json

4. Validation:
   $ python test_optical_calibration.py

   ✓ Quick 2-minute verification
   ✓ Confirms correction accuracy
   ✓ Generates calibration certificate
```

### Re-Calibration Triggers

**REQUIRED** (must re-calibrate):
- LED PCB replacement
- Optical fiber change
- Spectrometer replacement
- >20% deviation in quick-check test

**RECOMMENDED** (good practice):
- Annual maintenance
- After 1000+ hours operation
- Visible LED degradation
- Cross-talk artifacts in data

---

## Storage Strategy

### Directory Structure

```
control-3.2.9/
├── config/
│   ├── device_config.json                    # Main config
│   └── optical_calibration/                  # Calibration data
│       ├── optical_cal_FLMT09788_20251011.json
│       ├── optical_cal_FLMT09788_20251115.json  # After re-cal
│       └── README.md                         # Calibration log
│
├── optical_system_calibration.py             # Main calibration script
├── afterglow_correction.py                   # Correction module
├── test_optical_calibration.py               # Quick validation
│
└── docs/
    └── OPTICAL_SYSTEM_CALIBRATION_GUIDE.md   # Full documentation
```

### Device Config Integration

**Current `device_config.json`**:
```json
{
  "device_info": {
    "config_version": "1.0",
    "device_id": "SPR-001"
  },
  "hardware": {
    "led_pcb_model": "luminus_cool_white",
    "led_pcb_serial": null,
    "spectrometer_serial": "FLMT09788",
    "optical_fiber_diameter_um": 200
  }
}
```

**Enhanced with Optical Calibration**:
```json
{
  "device_info": {
    "config_version": "1.1",
    "device_id": "SPR-001"
  },
  "hardware": {
    "led_pcb_model": "luminus_cool_white",
    "led_pcb_serial": "LED-20251001-001",
    "spectrometer_serial": "FLMT09788",
    "optical_fiber_diameter_um": 200
  },
  "optical_calibration": {
    "enabled": true,
    "calibration_file": "config/optical_calibration/optical_cal_FLMT09788_20251011.json",
    "calibration_date": "2025-10-11T21:06:48",
    "calibration_valid_until": "2026-10-11T21:06:48",  // 1 year expiry
    "calibrated_for_hardware": {
      "led_pcb_serial": "LED-20251001-001",
      "led_pcb_model": "luminus_cool_white",
      "spectrometer_serial": "FLMT09788",
      "fiber_diameter_um": 200
    },
    "quick_check_interval_days": 90,  // Run validation every 3 months
    "last_quick_check": "2025-10-11T21:06:48",
    "quick_check_status": "passed"  // passed, warning, failed
  }
}
```

---

## GUI Integration Ideas (Future Implementation)

### Phase 1: Simple CLI Access via GUI Button

**Location**: Settings → Advanced → OEM Tools
**Feature**: "Run Optical System Calibration"

```
[Settings Window]
├── General
├── Hardware
├── Calibration (User-facing: Dark, Reference, etc.)
└── Advanced
    └── OEM Tools (password/unlock required)
        ├── [Button] Run Optical System Calibration (~45 min)
        ├── [Button] Quick Calibration Check (~2 min)
        ├── [Display] Calibration Status: Valid until 2026-10-11
        ├── [Display] Last Check: 2025-10-11 (Passed ✓)
        └── [Button] View Calibration Report
```

**Implementation**:
```python
# In OEM settings panel
def on_run_optical_calibration(self):
    """Launch optical system calibration as subprocess."""
    # Show warning dialog
    response = show_warning_dialog(
        title="Optical System Calibration",
        message="This will take approximately 45 minutes.\n"
                "Please ensure:\n"
                " • System is warmed up (20 min)\n"
                " • No other measurements running\n"
                " • Hardware is stable\n\n"
                "Continue?",
        buttons=["Start Calibration", "Cancel"]
    )

    if response == "Start Calibration":
        # Launch subprocess with progress display
        process = subprocess.Popen(
            [sys.executable, "optical_system_calibration.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Show progress window with live output
        progress_window = CalibrationProgressWindow(process)
        progress_window.show()
```

### Phase 2: Integrated Progress Display

**Features**:
- Live progress bar (measurement X/20)
- Current channel and integration time display
- Real-time τ values and R² fits
- Estimated time remaining
- Abort capability (safe LED shutdown)

**UI Mockup**:
```
┌─────────────────────────────────────────────────────┐
│  Optical System Calibration                    [X]  │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Progress: [████████████░░░░░░░░░░] 14/20 (70%)    │
│                                                      │
│  Current: Channel C @ 50ms integration              │
│  Estimated time remaining: 18 minutes               │
│                                                      │
│  ┌────────────────────────────────────────────┐    │
│  │ Results Summary                             │    │
│  │ ✓ Channel A: τ range 1.02-6.36ms (5 tests) │    │
│  │ ✓ Channel B: τ range 1.03-6.52ms (5 tests) │    │
│  │ ⏳ Channel C: Testing... (2/5 complete)     │    │
│  │ ⏸ Channel D: Pending                        │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
│  [View Detailed Log]  [Abort Calibration]          │
└─────────────────────────────────────────────────────┘
```

### Phase 3: Auto-Scheduling & Reminders

**Features**:
- Automatic quick-check every 90 days
- Dashboard warning if calibration expired
- Reminder before calibration expires (30 days)
- Hardware change detection (triggers re-cal alert)

**Dashboard Integration**:
```
┌─────────────────────────────────────────────┐
│  System Status                               │
├─────────────────────────────────────────────┤
│  ✓ Hardware: Connected                       │
│  ✓ Calibration: Valid (expires 2026-10-11)  │
│  ⚠ Optical Cal: Last check 45 days ago      │
│     [Run Quick Check Now]                    │
└─────────────────────────────────────────────┘
```

### Phase 4: Calibration History & Comparison

**Features**:
- Store all calibration runs
- Compare current vs previous (detect LED aging)
- Plot τ drift over time
- Export calibration certificate (PDF)

**Calibration History View**:
```
┌─────────────────────────────────────────────────────────┐
│  Optical Calibration History                            │
├─────────────────────────────────────────────────────────┤
│  Date         Status  LED Serial    τ Drift  R² Quality │
│  2025-10-11   Active  LED-20251001  --       0.97 ✓     │
│  2025-07-15   Old     LED-20251001  +8%      0.96 ✓     │
│  2025-04-10   Old     LED-20250330  +12%     0.94 ⚠     │
│                                                          │
│  [Compare Calibrations]  [Export Certificate]           │
└─────────────────────────────────────────────────────────┘
```

---

## API Design for Correction Module

### Core Functions

```python
# afterglow_correction.py

class OpticalSystemCorrection:
    """Manages optical system afterglow correction."""

    def __init__(self, calibration_file: Path):
        """Load calibration data from JSON file."""
        self.models = self._load_calibration(calibration_file)
        self.interpolators = self._build_interpolators()

    def _load_calibration(self, file: Path) -> dict:
        """Load and validate calibration data."""
        with open(file) as f:
            data = json.load(f)

        # Validate format and completeness
        self._validate_calibration(data)
        return data

    def _build_interpolators(self) -> dict:
        """Build cubic spline interpolators for each channel."""
        from scipy.interpolate import CubicSpline

        interpolators = {}
        for channel in ['A', 'B', 'C', 'D']:
            channel_data = self.models['channel_data'][channel]

            # Extract successful measurements
            int_times = []
            tau_values = []
            amplitudes = []
            baselines = []

            for measurement in channel_data['integration_time_data']:
                if measurement.get('fit_success', False):
                    int_times.append(measurement['integration_time_ms'])
                    tau_values.append(measurement['tau_ms'])
                    amplitudes.append(measurement['amplitude'])
                    baselines.append(measurement['baseline'])

            interpolators[channel] = {
                'tau': CubicSpline(int_times, tau_values),
                'amplitude': CubicSpline(int_times, amplitudes),
                'baseline': CubicSpline(int_times, baselines),
                'int_time_range': (min(int_times), max(int_times))
            }

        return interpolators

    def get_correction_parameters(
        self,
        channel: ChannelID,
        integration_time_ms: float
    ) -> tuple[float, float, float]:
        """
        Get interpolated correction parameters for given integration time.

        Args:
            channel: LED channel (A, B, C, D)
            integration_time_ms: Current integration time

        Returns:
            (tau_ms, amplitude, baseline)
        """
        ch_name = channel.name
        interp = self.interpolators[ch_name]

        # Clamp to calibrated range
        int_time = np.clip(
            integration_time_ms,
            interp['int_time_range'][0],
            interp['int_time_range'][1]
        )

        tau = float(interp['tau'](int_time))
        amplitude = float(interp['amplitude'](int_time))
        baseline = float(interp['baseline'](int_time))

        return tau, amplitude, baseline

    def calculate_afterglow_signal(
        self,
        channel: ChannelID,
        integration_time_ms: float,
        delay_after_led_off_ms: float
    ) -> float:
        """
        Calculate expected afterglow signal at given delay.

        Args:
            channel: LED channel
            integration_time_ms: Current integration time
            delay_after_led_off_ms: Time since LED turned off

        Returns:
            Expected afterglow signal (counts)
        """
        tau, amplitude, baseline = self.get_correction_parameters(
            channel, integration_time_ms
        )

        # Exponential decay model
        afterglow = amplitude * np.exp(-delay_after_led_off_ms / tau)

        return baseline + afterglow

    def apply_correction(
        self,
        spectrum: np.ndarray,
        previous_channel: ChannelID,
        integration_time_ms: float,
        inter_channel_delay_ms: float
    ) -> np.ndarray:
        """
        Apply afterglow correction to measured spectrum.

        Args:
            spectrum: Measured spectrum (raw counts)
            previous_channel: Channel that was active before current
            integration_time_ms: Current integration time
            inter_channel_delay_ms: Delay between channel switch and measurement

        Returns:
            Corrected spectrum (afterglow subtracted)
        """
        # Calculate expected afterglow from previous channel
        expected_afterglow = self.calculate_afterglow_signal(
            previous_channel,
            integration_time_ms,
            inter_channel_delay_ms
        )

        # Subtract afterglow (uniform correction across spectrum)
        corrected = spectrum - expected_afterglow

        return corrected

    def get_correction_info(self) -> dict:
        """Get calibration metadata for logging/display."""
        return {
            'calibration_date': self.models['metadata']['timestamp'],
            'channels_calibrated': self.models['metadata']['channels_tested'],
            'integration_times_tested': self.models['metadata']['integration_times_ms'],
            'total_measurements': self.models['metadata']['total_measurements']
        }


# Usage example in data acquisition
def measure_multi_channel_with_correction(
    ctrl: PicoP4SPRHAL,
    spec: Spectrometer,
    channels: list[ChannelID],
    integration_time_ms: float,
    correction: OpticalSystemCorrection
) -> dict[str, np.ndarray]:
    """
    Measure all channels with afterglow correction.
    """
    results = {}
    previous_channel = None
    inter_channel_delay = 5.0  # ms

    for channel in channels:
        # Activate channel
        ctrl.activate_channel(channel)
        time.sleep(0.020)  # LED stabilization

        # Measure spectrum
        raw_spectrum = spec.intensities()

        # Apply correction if not first channel
        if previous_channel is not None:
            corrected_spectrum = correction.apply_correction(
                raw_spectrum,
                previous_channel,
                integration_time_ms,
                inter_channel_delay
            )
        else:
            corrected_spectrum = raw_spectrum

        results[channel.name] = corrected_spectrum
        previous_channel = channel

        # Wait before next channel
        time.sleep(inter_channel_delay / 1000.0)

    return results
```

---

## Validation Plan (Before Full Implementation)

### Current Status
✅ Characterization script created
⏳ Running comprehensive data collection (14/20 complete)
⏳ Awaiting full calibration dataset

### Validation Steps (After Characterization Completes)

#### 1. Data Quality Check (5 minutes)
```python
# Verify calibration data quality
- All 20 measurements successful
- R² > 0.95 for all fits
- Smooth τ curves (no anomalies)
- Physically reasonable values (0.5-10ms range)
```

#### 2. Interpolation Accuracy Test (10 minutes)
```python
# Test cubic spline interpolation
- Test at calibrated points (5, 10, 20, 50, 100ms)
- Test at mid-points (7.5, 15, 35, 75ms)
- Verify smooth curves, no oscillations
- Check extrapolation behavior at boundaries
```

#### 3. Correction Module Unit Tests (15 minutes)
```python
# test_optical_calibration.py
- Load calibration file successfully
- Interpolate τ for arbitrary integration times
- Calculate afterglow signal correctly
- Apply correction without errors
- Handle edge cases (missing data, invalid inputs)
```

#### 4. Real-World Accuracy Test (20 minutes)
```python
# Measure actual afterglow and compare to prediction
- Activate Channel A, measure peak
- Turn off, wait 5ms, measure residual
- Compare to predicted afterglow
- Repeat for different integration times
- Target: <5% prediction error
```

#### 5. Multi-Channel Cycling Test (10 minutes)
```python
# Worst-case scenario: rapid A→B→C→D loops
- Run 20 cycles with 5ms inter-channel delay
- Apply correction to each measurement
- Verify no cumulative error buildup
- Check baseline stability
- Target: <2% drift over 20 cycles
```

### Success Criteria

Before proceeding to GUI integration:
- ✅ All validation tests pass
- ✅ Correction error < 5% (ideally <2%)
- ✅ No cumulative buildup detected
- ✅ Interpolation smooth across full range
- ✅ Code well-documented and robust

---

## Implementation Timeline (Proposed)

### Week 1: Validation & Core Module
- [x] Day 1: Complete characterization (current, in progress)
- [ ] Day 2: Validate calibration data quality
- [ ] Day 3: Build `afterglow_correction.py` module
- [ ] Day 4: Create `test_optical_calibration.py` suite
- [ ] Day 5: Run comprehensive validation tests

### Week 2: Integration & Documentation
- [ ] Day 1: Integrate correction into data acquisition
- [ ] Day 2: Add enable/disable flag to device_config
- [ ] Day 3: Test with real SPR measurements
- [ ] Day 4: Write `OPTICAL_SYSTEM_CALIBRATION_GUIDE.md`
- [ ] Day 5: Create OEM quick-start guide

### Week 3: GUI Planning (Design Only, No Implementation Yet)
- [ ] Day 1: Design GUI mockups (see above)
- [ ] Day 2: Define user workflows (OEM vs end-user)
- [ ] Day 3: Plan integration points in existing GUI
- [ ] Day 4: Security model (OEM unlock mechanism)
- [ ] Day 5: Write GUI implementation specification

### Week 4+: GUI Implementation (After Full Validation)
- Only proceed after 3+ weeks of successful CLI usage
- Start with simple button → CLI script
- Gradually add progress display
- Final: integrated scheduling & history

---

## Risk Mitigation

### Technical Risks

**Risk**: Interpolation fails at integration times outside calibrated range
**Mitigation**: Clamp to [5ms, 100ms] range, log warning if extrapolating

**Risk**: Calibration file corrupted or missing
**Mitigation**: Validate on load, fall back to no correction (log error)

**Risk**: Hardware change invalidates calibration
**Mitigation**: Quick-check detects drift >20%, prompts re-calibration

**Risk**: Correction introduces artifacts
**Mitigation**: Always store both raw and corrected data, allow disable

### User Experience Risks

**Risk**: 45-minute calibration too long for users
**Mitigation**: Clearly set expectations, show progress, allow abort

**Risk**: Users forget to re-calibrate after hardware changes
**Mitigation**: Automatic detection + warning dialog

**Risk**: Calibration fails mid-process
**Mitigation**: Resume capability, save partial results, safe LED shutdown

---

## Future Enhancements (Post-V1)

### Advanced Features
- Adaptive inter-channel delays (optimize based on τ)
- Real-time correction quality monitoring
- Automatic re-calibration scheduling
- Cloud backup of calibration data
- Multi-device calibration comparison (QC tool)

### Research Features
- Temperature-dependent correction (measure at multiple temps)
- Aging prediction model (predict when re-cal needed)
- Wavelength-dependent afterglow (full spectrum correction)
- Machine learning optimization of correction parameters

---

## Questions for User/Team

1. **OEM Access Control**: How should we restrict access to calibration tool?
   - Password protection?
   - Hardware key?
   - Config file flag?

2. **Calibration Certificate**: Should we generate PDF reports for QC/compliance?

3. **Remote Support**: Should calibration data be uploadable for remote diagnostics?

4. **Batch Production**: How to streamline calibration for multiple units?

5. **End-User Access**: Should end-users ever run calibration, or OEM-only?

---

## Current Action Items

1. ⏳ **Wait for characterization to complete** (~25 minutes remaining)
2. ⏳ **Analyze calibration data quality** (after completion)
3. ⏳ **Run validation tests** (before any implementation)
4. 📝 **Document findings** (update this file with results)
5. 🚀 **Proceed to correction module** (only after successful validation)

---

**Last Updated**: October 11, 2025, 21:15
**Status**: Awaiting characterization completion
**Next Review**: After validation tests complete
