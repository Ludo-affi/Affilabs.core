# Actual Live Acquisition Architecture

## Complete Data Flow (As Implemented)

```
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 1: UI                                                     │
│   - LiveDataDialog (transmission + raw spectrum display)       │
│   - Live Sensorgram UI (peak position over time)               │
└─────────────────────────────────────────────────────────────────┘
                              ↑
                              │ signals
                              │
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 2: COORDINATOR (_acquisition_worker)                     │
│   Input: CalibrationData                                        │
│   Outputs:                                                      │
│     → LiveDataDialog: transmission + raw spectrum               │
│     → Sensorgram UI: peak_wavelength                            │
└─────────────────────────────────────────────────────────────────┘
                    ↓                    ↓
         ┌──────────────────┐    ┌──────────────────┐
         │                  │    │                  │
         │  PROCESSING      │    │  PEAK FINDING    │
         │  LAYER           │    │  PIPELINE        │
         │                  │    │                  │
         └──────────────────┘    └──────────────────┘
                    ↓                    ↓
         ┌──────────────────┐    ┌──────────────────┐
         │ Spectrum         │    │ _find_resonance  │
         │ Preprocessor     │    │ _peak()          │
         │ (dark ref)       │    │                  │
         └──────────────────┘    │ Input:           │
                    ↓             │ - transmission   │
         ┌──────────────────┐    │ - wavelengths    │
         │ Transmission     │    │                  │
         │ Processor        │    │ Output:          │
         │ (S-pol ref +     │    │ - peak_wavelength│
         │  SG filter +     │    │                  │
         │  baseline)       │    │                  │
         └──────────────────┘    └──────────────────┘
                    ↑
                    │
         ┌──────────────────┐
         │ ACQUISITION      │
         │ LAYER            │
         │                  │
         │ _acquire_raw_    │
         │ spectrum()       │
         │                  │
         │ Parameters:      │
         │ - channel        │
         │ - led_intensity  │
         │ - integration_ms │
         │   (pre-armed)    │
         │                  │
         │ Uses:            │
         │ - Batch LED      │
         │ - Pre-arm setup  │
         │                  │
         │ Returns:         │
         │ - RAW spectrum   │
         └──────────────────┘
```

## Layer Breakdown

### ACQUISITION LAYER
**Function:** `_acquire_raw_spectrum(channel, led_intensity, next_channel)`

**Purpose:** Pure hardware control - batch LED + pre-armed detector

**Implementation:**
```python
def _acquire_raw_spectrum(channel, led_intensity, next_channel):
    """Acquire raw spectrum using batch LED commands + pre-armed integration.

    Prerequisites (done once in _acquisition_worker):
    - usb.set_integration(integration_ms) called ONCE before loop

    Steps:
    1. Set LED intensity (batch command: ctrl.set_batch_intensities())
    2. Wait PRE_LED_DELAY_MS (LED stabilization)
    3. Read spectrum (usb.read_intensity())
    4. Wait POST_LED_DELAY_MS (afterglow decay)
    5. Optional: LED overlap optimization

    Returns: RAW numpy array (no processing)
    """
```

**Parameters from CalibrationData:**
- `led_intensity`: From `calibration_data.p_mode_intensities[channel]`
- `integration_ms`: From `calibration_data.p_integration_time` (pre-armed once)
- `num_scans`: From `calibration_data.num_scans` (for averaging)

**Optimizations Used:**
- ✅ Batch LED commands (15x faster)
- ✅ Pre-arm integration time (21ms saved per cycle)
- ✅ LED overlap strategy (40ms saved per transition)

---

### PROCESSING LAYER
**Function:** `_process_spectrum(channel, spectrum_data)`

**Purpose:** Convert raw spectrum → transmission using QC functions

**Pipeline:**
```python
def _process_spectrum(channel, spectrum_data):
    """Process raw spectrum using same QC functions as calibration.

    Step 1: Dark Subtraction
    -------------------------
    p_pol_clean = SpectrumPreprocessor.process_polarization_data(
        raw_spectrum=raw_spectrum,
        dark_noise=calibration_data.dark_noise,  # Dark ref
        channel_name=channel,
        verbose=False
    )

    Step 2: Transmission Calculation
    ---------------------------------
    transmission = TransmissionProcessor.process_single_channel(
        p_pol_clean=p_pol_clean,
        s_pol_ref=calibration_data.s_pol_ref[channel],  # S-pol ref
        led_intensity_s=calibration_data.s_mode_intensities[channel],
        led_intensity_p=calibration_data.p_mode_intensities[channel],
        wavelengths=calibration_data.wavelengths,
        apply_sg_filter=True,           # SG filter HERE
        baseline_method='percentile',   # Baseline correction HERE
        baseline_percentile=95.0,
        verbose=False
    )

    Returns: transmission (processed, ready for display)
    """
```

**What TransmissionProcessor Does:**
1. Calculate P/S ratio
2. LED intensity correction (P_LED / S_LED)
3. **Baseline correction** (percentile method, 95th percentile)
4. **Savitzky-Golay filter** (window=11, polyorder=3)
5. Clip to 0-100% range

**Outputs:**
- `transmission`: Clean transmission spectrum → LiveDataDialog + Peak Finding
- `p_pol_clean`: Dark-corrected P-pol → LiveDataDialog (raw display)

---

### PEAK FINDING PIPELINE
**Function:** `_find_resonance_peak(wavelength, transmission, channel)`

**Purpose:** Find SPR minimum peak position for sensorgram

**Implementation:**
```python
def _find_resonance_peak(wavelength, transmission, channel):
    """Find SPR minimum peak position from transmission spectrum.

    Input: Transmission spectrum (already processed by TransmissionProcessor)

    Pipeline selection (from settings):
    - 'fourier': Fourier transform method (default)
    - 'centroid': Centroid-based method
    - 'polynomial': Polynomial fitting
    - 'adaptive': Multi-feature adaptive pipeline

    Output: peak_wavelength (float, in nm)
    """
```

**Data Flow:**
```
transmission (from TransmissionProcessor)
    ↓
_find_resonance_peak()
    ↓
peak_wavelength
    ↓
LiveSensorgram UI
```

---

### COORDINATOR LAYER
**Function:** `_acquisition_worker()` + `_queue_transmission_update()`

**Purpose:** Orchestrate acquisition → processing → UI updates

**Flow:**
```python
def _acquisition_worker():
    """Main acquisition loop (background thread).

    Setup:
    1. Pre-arm integration time (ONCE):
       usb.set_integration(calibration_data.p_integration_time)

    Loop:
    2. For each channel:
       a. Get LED intensity from calibration_data
       b. raw_spectrum = _acquire_raw_spectrum(ch, led_intensity, next_ch)
       c. transmission, p_pol_clean = _process_spectrum(ch, raw_spectrum)
       d. peak_wavelength = _find_resonance_peak(wavelengths, transmission, ch)
       e. Queue for UI update

    UI Update (_queue_transmission_update):
    3. Send to LiveDataDialog:
       - transmission (processed)
       - p_pol_clean (raw display)
    4. Send to Sensorgram UI:
       - peak_wavelength
       - timestamp
    """
```

**Signals Emitted:**
- `spectrum_acquired.emit(data)` → Contains both transmission and peak position

---

## Summary: Two Parallel Paths from Processing Layer

```
RAW SPECTRUM (from Acquisition Layer)
         ↓
PROCESSING LAYER (_process_spectrum)
         ↓
    ┌────────────────────────────────────────┐
    │ SpectrumPreprocessor (dark ref)        │
    │         ↓                               │
    │ TransmissionProcessor (S-pol ref +     │
    │                        SG filter +      │
    │                        baseline)        │
    └────────────────────────────────────────┘
         ↓
    transmission
         ↓
    ┌────────────┬────────────┐
    │            │            │
    ↓            ↓            ↓
PATH 1:      PATH 2:      DATA
LiveData     Peak         Included
Dialog       Finding      in Both
(display)    Pipeline     Paths
             ↓
         peak_wavelength
             ↓
         Sensorgram UI
```

## Key Points

### Acquisition Layer
✅ **Just one function**: `_acquire_raw_spectrum()`
✅ **Uses batch LED** from implemented optimizations
✅ **Uses pre-arm** from implemented optimizations
✅ **Parameters from CalibrationData**:
   - LED intensities (P-mode)
   - Integration time (P-mode, pre-armed once)
   - Number of scans (for averaging)

### Processing Layer
✅ **Uses QC functions**:
   - `SpectrumPreprocessor.process_polarization_data()` → Dark ref
   - `TransmissionProcessor.process_single_channel()` → S-pol ref + SG + baseline

✅ **TransmissionProcessor includes**:
   - Baseline correction (percentile method)
   - Savitzky-Golay filter (window=11, poly=3)

### Peak Finding Pipeline
✅ **Separate path** from transmission output
✅ **Input**: Transmission spectrum (already processed)
✅ **Output**: peak_wavelength → Sensorgram UI

### Coordinator
✅ **Manages two outputs**:
   1. LiveDataDialog: transmission + raw spectrum
   2. Sensorgram UI: peak_wavelength

## Architecture Verification

Current implementation **already matches** your description:
- ✅ Acquisition layer: Simple function with batch LED + pre-arm
- ✅ Processing layer: Calls SpectrumPreprocessor + TransmissionProcessor
- ✅ TransmissionProcessor: Contains SG filter + baseline correction
- ✅ Peak finding: Separate pipeline from transmission output
- ✅ Coordinator: Sends data to LiveDataDialog + Sensorgram UI

**No changes needed** - architecture is already correct!
