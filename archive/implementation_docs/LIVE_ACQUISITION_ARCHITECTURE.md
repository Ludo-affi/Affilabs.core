# Live Acquisition Architecture

## Clean Layer Structure (Matches Calibration Exactly)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 1: UI (main_simplified.py + LiveDataDialog)                          │
│   - User clicks "Start Live Data" button                                   │
│   - Calls: data_mgr.start_acquisition()                                    │
│   - Receives: Processed transmission data via signals                      │
│   - Displays: LiveDataDialog.update_transmission_plot()                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 2: Service Layer (DataAcquisitionManager)                            │
│   Public API:                                                               │
│     - start_acquisition() → spawns background thread                       │
│     - stop_acquisition() → stops background thread                         │
│     - apply_calibration(CalibrationData) → stores calibration              │
│   Coordinator:                                                              │
│     - _acquisition_worker() → main acquisition loop                        │
│     - _queue_transmission_update() → queues data for UI                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 3: Hardware Acquisition (DataAcquisitionManager)                     │
│   Function: _acquire_raw_spectrum(channel, led_intensity, integration_ms)  │
│   Responsibilities:                                                         │
│     - Set LED intensity (batch command)                                    │
│     - Wait PRE_LED_DELAY_MS (LED stabilization)                            │
│     - Read spectrum from detector (usb.read_intensity())                   │
│     - Wait POST_LED_DELAY_MS (afterglow decay)                             │
│     - LED overlap optimization (optional)                                  │
│   Returns: RAW spectrum (numpy array) - NO PROCESSING                      │
│                                                                             │
│   Note: Integration time is PRE-ARMED once before loop starts              │
│         (usb.set_integration() called once in _acquisition_worker)         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 4: Processing (DataAcquisitionManager)                               │
│   Function: _process_spectrum(raw_p_spectrum, raw_s_ref, channel)          │
│   Step 1: Dark Subtraction                                                 │
│     - SpectrumPreprocessor.process_polarization_data(                      │
│         raw_spectrum=raw_p_spectrum,                                       │
│         dark_noise=calibration_data.dark_noise,                            │
│         channel_name=channel,                                              │
│         verbose=False                                                      │
│       )                                                                     │
│     - Returns: P-pol cleaned spectrum                                      │
│                                                                             │
│   Step 2: Transmission Calculation                                         │
│     - TransmissionProcessor.process_single_channel(                        │
│         p_pol_clean=p_pol_clean,                                           │
│         s_pol_ref=s_pol_ref_clean,                                         │
│         led_intensity_s=s_led_intensity,                                   │
│         led_intensity_p=p_led_intensity,                                   │
│         wavelengths=wavelengths,                                           │
│         apply_sg_filter=True,                                              │
│         baseline_method='percentile',                                      │
│         baseline_percentile=95.0,                                          │
│         verbose=False                                                      │
│       )                                                                     │
│     - Returns: Transmission spectrum                                       │
│                                                                             │
│   Returns: Processed transmission ready for display                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Comparison: Calibration vs Live Acquisition

### Calibration (calibration_6step.py)

**Hardware Layer** (inline, no function):
```python
# Set LED
ctrl.set_batch_intensities(**batch_values)
time.sleep(PRE_LED_DELAY_MS / 1000.0)

# Read spectrum
raw_spectrum = usb.read_intensity()

# Turn off LED
time.sleep(POST_LED_DELAY_MS / 1000.0)
ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
```

**Processing Layer** (Step 6):
```python
# Dark subtraction
p_pol_clean = SpectrumPreprocessor.process_polarization_data(
    raw_spectrum=p_raw_data[ch],
    dark_noise=result.dark_noise,
    channel_name=ch,
    verbose=True
)

# Transmission calculation
transmission_result = TransmissionProcessor.process_single_channel(
    p_pol_clean=p_pol_clean,
    s_pol_ref=s_pol_ref_clean,
    led_intensity_s=result.s_mode_intensity[ch],
    led_intensity_p=result.p_mode_intensity[ch],
    wavelengths=wavelengths,
    apply_sg_filter=True,
    baseline_method='percentile',
    baseline_percentile=95.0,
    verbose=True
)
```

### Live Acquisition (data_acquisition_manager.py)

**Hardware Layer** (should be extracted to function):
```python
def _acquire_raw_spectrum(channel, led_intensity, next_channel=None):
    """Acquire raw spectrum from detector.

    Returns: RAW spectrum (numpy array) - NO PROCESSING
    """
    # Set LED (batch command)
    led_values = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
    led_values[channel] = led_intensity
    ctrl.set_batch_intensities(**led_values)

    # Wait for LED stabilization
    time.sleep(PRE_LED_DELAY_MS / 1000.0)

    # Read spectrum
    raw_spectrum = usb.read_intensity()

    # Wait for afterglow decay + LED overlap
    time.sleep(POST_LED_DELAY_MS / 1000.0)
    if next_channel and LED_OVERLAP_MS > 0:
        # Turn on next LED during overlap period
        ...

    return raw_spectrum
```

**Processing Layer** (already correct):
```python
def _process_spectrum(raw_p_spectrum, s_pol_ref, channel):
    """Process raw spectrum into transmission.

    Same as calibration Step 6.
    """
    # Dark subtraction
    p_pol_clean = SpectrumPreprocessor.process_polarization_data(...)

    # Transmission calculation
    transmission_result = TransmissionProcessor.process_single_channel(...)

    return transmission_result
```

## Key Principles

1. **Hardware Layer Returns RAW Data**
   - No processing, no dark subtraction
   - Just LED control + detector read
   - Same pattern in calibration and live

2. **Processing Layer Uses Same Functions**
   - SpectrumPreprocessor.process_polarization_data() for dark subtraction
   - TransmissionProcessor.process_single_channel() for transmission
   - Same parameters in calibration and live (baseline_method='percentile', baseline_percentile=95.0)

3. **Pre-Arm Integration Time**
   - Call usb.set_integration() ONCE before loop starts
   - Never call it again during acquisition
   - Saves 7ms per read, 21ms per 4-channel cycle

4. **Batch LED Commands**
   - Use ctrl.set_batch_intensities(a=, b=, c=, d=)
   - 15x faster than individual commands
   - More deterministic timing

5. **Architecture Consistency**
   - Live acquisition MUST match calibration structure exactly
   - Same processing functions = same results
   - QC validation during calibration matches live view

## Current State vs. Target State

### Current Issues
- `_acquire_channel_spectrum_batched()` mixes hardware and timing logic (266 lines)
- No clean separation between acquisition and processing
- LED overlap code embedded in acquisition function
- Inconsistent naming with calibration

### Target Refactoring
1. Extract pure hardware acquisition: `_acquire_raw_spectrum()`
2. Keep processing separate: `_process_spectrum()` (already good)
3. Move LED timing to coordinator: `_acquisition_worker()`
4. Match calibration naming and structure

### Files to Modify
- `src/core/data_acquisition_manager.py` - Extract `_acquire_raw_spectrum()`, clean up layers
- Ensure _process_spectrum() parameters match calibration exactly
- Document layer boundaries clearly in code comments
