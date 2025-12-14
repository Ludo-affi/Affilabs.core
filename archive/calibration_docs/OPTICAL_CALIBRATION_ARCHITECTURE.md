# Optical System Calibration - Architecture & Usage

**Status**: ✅ Design Confirmed
**Date**: October 11, 2025
**Architecture**: Separate OEM Tool (Not integrated with main calibration)

---

## Architecture Decision: Separate Tool ✅

### The Two Calibration Systems

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SPR SYSTEM CALIBRATION                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────────────────┐  ┌─────────────────────────┐  │
│  │   MAIN CALIBRATION (9 Steps)    │  │ OPTICAL CALIBRATION     │  │
│  │                                  │  │ (Separate OEM Tool)     │  │
│  ├─────────────────────────────────┤  ├─────────────────────────┤  │
│  │ Frequency: FREQUENT              │  │ Frequency: RARE         │  │
│  │   • Every startup                │  │   • Once per 1000 hrs   │  │
│  │   • Hardware changes             │  │   • LED aging detected  │  │
│  │   • Daily operation              │  │   • Hardware replaced   │  │
│  ├─────────────────────────────────┤  ├─────────────────────────┤  │
│  │ Duration: ~1.5 minutes           │  │ Duration: ~2-3 minutes  │  │
│  ├─────────────────────────────────┤  ├─────────────────────────┤  │
│  │ Purpose:                         │  │ Purpose:                │  │
│  │   • Dark noise baseline          │  │   • LED phosphor decay  │  │
│  │   • Integration time opt         │  │   • τ characterization  │  │
│  │   • LED intensity setting        │  │   • Afterglow modeling  │  │
│  │   • Reference signals            │  │                         │  │
│  │   • Wavelength range             │  │                         │  │
│  ├─────────────────────────────────┤  ├─────────────────────────┤  │
│  │ Outputs:                         │  │ Outputs:                │  │
│  │   • LED intensities              │  │   • τ(int_time) tables  │  │
│  │   • Integration time             │  │   • Decay parameters    │  │
│  │   • Dark noise arrays            │  │   • System signature    │  │
│  │   • Reference spectra            │  │                         │  │
│  ├─────────────────────────────────┤  ├─────────────────────────┤  │
│  │ Storage:                         │  │ Storage:                │  │
│  │   calibration_profiles/          │  │   optical_calibration/  │  │
│  │   auto_save_TIMESTAMP.json       │  │   system_SN_DATE.json   │  │
│  ├─────────────────────────────────┤  ├─────────────────────────┤  │
│  │ User: AUTOMATIC                  │  │ User: OEM ONLY          │  │
│  └─────────────────────────────────┘  └─────────────────────────┘  │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Why Separate?

### 1. **Different Timescales**

| Aspect | Main Calibration | Optical Calibration |
|--------|-----------------|---------------------|
| **Frequency** | Daily / Every startup | Once per 1000 hours |
| **Trigger** | Hardware connection, settings change | LED aging, hardware replacement |
| **Duration** | 1.5 minutes | 2-3 minutes |
| **User** | Automatic (all users) | Manual (OEM only) |

### 2. **Different Purposes**

**Main Calibration**:
- Establishes measurement baselines
- Optimizes acquisition parameters
- Changes frequently with conditions
- System-dependent but short-lived

**Optical Calibration**:
- Characterizes hardware physics
- Models phosphor decay behavior
- Changes only with hardware aging
- System-dependent and long-lived

### 3. **Different Data Usage**

**Main Calibration Data**:
```python
# Used for every measurement
dark_noise      # Baseline subtraction
ref_signals     # Transmittance calculation
integration_ms  # Acquisition settings
led_intensities # Signal optimization
```

**Optical Calibration Data**:
```python
# Used for correction algorithm
tau_tables[channel][integration_time]  # Decay time constants
amplitude_tables[channel]              # Afterglow magnitude
baseline_tables[channel]               # Reference levels
```

### 4. **Independence**

```
Main Calibration ──────┐
                       ├──> SPR Measurement
Optical Calibration ───┘

Main calibration DOES NOT depend on optical calibration
Optical calibration DOES NOT depend on main calibration
Both can run independently, in any order
```

---

## Usage Workflows

### Workflow 1: New System Setup (First Time)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Hardware Assembly                                         │
│    ├── Install LED PCB                                       │
│    ├── Connect optical fiber (e.g., 200µm)                  │
│    ├── Mount spectrometer (e.g., Flame-T S/N FLMT09788)     │
│    └── Connect controller (PicoP4SPR)                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Run Optical System Calibration (OEM Tool)                │
│    $ python optical_system_calibration.py                   │
│                                                              │
│    ✓ Tests 4 channels × 5 integration times = 20 tests      │
│    ✓ 5 cycles per test for statistics                       │
│    ✓ Runtime: ~2.2 minutes (actual from testing)            │
│    ✓ Generates: optical_calibration/system_FLMT09788_...json│
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Link to Device Config                                    │
│    Edit device_config.json:                                 │
│    {                                                         │
│      "optical_calibration_file": "optical_calibration/      │
│                                   system_FLMT09788_...json" │
│    }                                                         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. System Ready for Use                                     │
│    • Main calibration runs automatically on startup          │
│    • Measurements use optical correction automatically       │
│    • No user intervention needed                            │
└─────────────────────────────────────────────────────────────┘
```

### Workflow 2: Daily Operation (Routine Use)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Start Application                                         │
│    $ python run_app.py                                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Automatic Main Calibration (9 Steps, ~1.5 min)           │
│    ├── Load optical calibration file (if exists)            │
│    ├── Run 9-step calibration                               │
│    └── Ready for measurements                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. SPR Measurements                                          │
│    • Optical correction applied automatically               │
│    • Uses τ tables from optical calibration file            │
│    • No re-calibration needed                               │
└─────────────────────────────────────────────────────────────┘
```

### Workflow 3: Maintenance Re-Calibration (After 1000 Hours)

```
┌─────────────────────────────────────────────────────────────┐
│ Trigger: LED aging detected or 1000 hours operation         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 1. Run Optical Calibration Again (OEM Tool)                 │
│    $ python optical_system_calibration.py                   │
│                                                              │
│    ✓ Generates NEW τ tables with current LED characteristics│
│    ✓ Runtime: ~2.2 minutes                                  │
│    ✓ New file: optical_calibration/system_FLMT09788_...json│
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Update Device Config (Point to New File)                 │
│    Edit device_config.json:                                 │
│    {                                                         │
│      "optical_calibration_file": "optical_calibration/      │
│                                   system_FLMT09788_NEW.json"│
│    }                                                         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Resume Normal Operation                                  │
│    • Main calibration still runs daily                      │
│    • Measurements now use updated optical correction        │
│    • System continues operating                             │
└─────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
control-3.2.9/
├── optical_system_calibration.py        # OEM tool (standalone)
├── afterglow_correction.py              # Correction module (loads τ tables)
├── test_optical_calibration.py          # Validation/quick-check tool
│
├── config/
│   ├── device_config.json               # Links to optical calibration
│   │   {
│   │     "spectrometer_serial": "FLMT09788",
│   │     "optical_fiber_diameter_um": 200,
│   │     "led_pcb_model": "luminus_cool_white",
│   │     "optical_calibration_file": "optical_calibration/system_FLMT09788_20251011.json"
│   │   }
│   │
│   ├── optical_calibration/             # τ tables storage
│   │   ├── system_FLMT09788_20251011_210859.json  # Generated calibration
│   │   ├── system_FLMT09788_20251015_143022.json  # Re-calibration
│   │   └── ...
│   │
│   └── calibration_profiles/            # Main calibration storage
│       ├── auto_save_20251011_220530.json
│       └── ...
│
└── utils/
    └── spr_data_acquisition.py          # Uses afterglow correction
```

---

## Implementation Components

### 1. Optical Calibration Script (OEM Tool)

**File**: `optical_system_calibration.py`

```python
"""Optical System Calibration - OEM Maintenance Tool

Characterizes LED phosphor afterglow across integration times.
Run once per ~1000 hours or after hardware changes.

Usage:
    python optical_system_calibration.py

Runtime: ~2-3 minutes
Output: config/optical_calibration/system_SERIAL_TIMESTAMP.json
"""

def main():
    # Initialize hardware
    ctrl = PicoP4SPRHAL()
    spec = get_spectrometer()

    # Test all channels × integration times
    channels = [ChannelID.A, ChannelID.B, ChannelID.C, ChannelID.D]
    integration_times = [5, 10, 20, 50, 100]  # ms

    results = {}
    for channel in channels:
        results[channel] = {}
        for int_time in integration_times:
            # Characterize at this integration time
            tau, amplitude, baseline, r_squared = characterize_at_integration_time(
                ctrl, spec, channel, int_time, n_cycles=5
            )
            results[channel][int_time] = {
                'tau_ms': tau,
                'amplitude': amplitude,
                'baseline': baseline,
                'r_squared': r_squared
            }

    # Save to file
    save_optical_calibration(results, spec.serial_number)

    return results
```

### 2. Correction Module (Production Code)

**File**: `afterglow_correction.py`

```python
"""Afterglow Correction Module

Loads optical calibration and applies correction during measurements.
Used by SPR data acquisition automatically.
"""

from scipy.interpolate import CubicSpline
import numpy as np

class AfterglowCorrection:
    """Apply afterglow correction using optical calibration data."""

    def __init__(self, calibration_file: str):
        """Load optical calibration τ tables."""
        self.calibration = load_json(calibration_file)
        self._build_interpolators()

    def _build_interpolators(self):
        """Build cubic spline interpolators for τ(integration_time)."""
        self.tau_interpolators = {}
        for channel, data in self.calibration['channel_data'].items():
            int_times = [d['integration_time_ms'] for d in data['integration_time_data']]
            taus = [d['tau_ms'] for d in data['integration_time_data']]

            # Cubic spline for smooth interpolation
            self.tau_interpolators[channel] = CubicSpline(int_times, taus)

    def calculate_correction(
        self,
        previous_channel: ChannelID,
        integration_time_ms: float,
        delay_ms: float
    ) -> float:
        """Calculate expected afterglow signal.

        Returns correction value to subtract from measurement.
        """
        # Interpolate τ for this integration time
        tau = self.tau_interpolators[previous_channel.value](integration_time_ms)

        # Get amplitude from calibration (could interpolate if needed)
        amplitude = self._get_amplitude(previous_channel, integration_time_ms)
        baseline = self._get_baseline(previous_channel)

        # Exponential decay: signal(t) = baseline + A * exp(-t/τ)
        correction = baseline + amplitude * np.exp(-delay_ms / tau)

        return correction

    def apply_correction(
        self,
        measured_signal: np.ndarray,
        previous_channel: ChannelID,
        integration_time_ms: float,
        delay_ms: float = 5.0
    ) -> np.ndarray:
        """Apply afterglow correction to measurement.

        Returns corrected signal array.
        """
        correction = self.calculate_correction(
            previous_channel, integration_time_ms, delay_ms
        )

        # Subtract afterglow contribution
        corrected_signal = measured_signal - correction

        return corrected_signal
```

### 3. Integration with Data Acquisition

**File**: `utils/spr_data_acquisition.py`

```python
class SPRDataAcquisition:
    def __init__(self, ...):
        # Load optical calibration if available
        self.afterglow_correction = None
        if device_config.get('optical_calibration_file'):
            try:
                self.afterglow_correction = AfterglowCorrection(
                    device_config['optical_calibration_file']
                )
                logger.info("✅ Optical correction loaded and enabled")
            except Exception as e:
                logger.warning(f"⚠️ Optical correction not available: {e}")

    def acquire_multi_channel(self, channels, integration_time_ms):
        """Acquire multiple channels with optional afterglow correction."""
        results = {}
        previous_channel = None

        for channel in channels:
            # Activate LED and measure
            signal = self._measure_channel(channel, integration_time_ms)

            # Apply optical correction if available
            if self.afterglow_correction and previous_channel:
                signal_corrected = self.afterglow_correction.apply_correction(
                    signal, previous_channel, integration_time_ms, delay_ms=5
                )
            else:
                signal_corrected = signal

            results[channel] = {
                'raw': signal,
                'corrected': signal_corrected
            }

            previous_channel = channel

        return results
```

---

## Key Points

### ✅ **What This Architecture Provides**

1. **Separation of concerns**:
   - Main calibration handles daily operations
   - Optical calibration handles hardware characterization

2. **Correct timescales**:
   - Frequent re-calibration where needed (main)
   - Infrequent characterization where stable (optical)

3. **OEM control**:
   - Optical calibration is maintenance procedure
   - Not exposed to end users
   - Controlled re-calibration schedule

4. **Passive correction**:
   - Once τ tables exist, just load and apply
   - No need to re-run characterization
   - Fast correction during measurements

5. **Independent workflows**:
   - Can run either calibration without the other
   - Can develop/test independently
   - Can deploy separately

### ❌ **What This Architecture Avoids**

1. **No forced coupling**: Main calibration doesn't wait for optical calibration
2. **No runtime bloat**: 1.5 min calibration doesn't become 3.5 min
3. **No daily overhead**: Don't characterize phosphor decay every day
4. **No user confusion**: Optical calibration hidden in OEM tools

---

## Next Steps

1. ✅ **Architecture decided**: Separate tool confirmed
2. ⏳ **Implement correction module**: `afterglow_correction.py` with interpolation
3. ⏳ **Integrate with acquisition**: Add to `spr_data_acquisition.py`
4. ⏳ **Create validation suite**: `test_optical_calibration.py`
5. ⏳ **Document OEM procedure**: Complete guide for field use

---

**Last Updated**: October 11, 2025
**Status**: Architecture finalized, ready for implementation
