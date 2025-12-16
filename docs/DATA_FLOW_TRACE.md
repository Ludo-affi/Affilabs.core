# Data Flow Trace: Acquisition → Sidebar Graphs

## Complete Path from Data Acquisition Manager to Setting Sidebar Graphs

### 1. **DATA EMISSION** (Worker Thread)
**Location:** `affilabs/core/data_acquisition_manager.py`

**Line 1177** - Batch Mode Emission:
```python
result = {
    "channel": ch,
    "wavelength": processed["wavelength"],      # Peak wavelength (nm)
    "intensity": processed["intensity"],        # Peak intensity
    "raw_spectrum": raw,                        # Raw intensity array
    "transmission_spectrum": trans,             # Transmission % array
    "wavelengths": self.calibration_data.wavelengths,  # Wavelength array for plotting
    "timestamp": timestamp,
    "is_preview": False,
    "batch_processed": False,
    "integration_time": self.calibration_data.integration_time,
    "num_scans": self.calibration_data.num_scans,
    "led_intensity": self.calibration_data.p_mode_intensities.get(ch, 0),
}

self.spectrum_acquired.emit(result)  # Qt Signal (thread-safe)
```

**Line 1322** - Rank Mode Emission:
```python
spectrum_data = {
    "channel": channel,
    "raw_spectrum": raw_spectrum,               # Raw intensity array
    "wavelengths": self.calibration_data.wavelengths,  # Array for plotting
    "wavelength": peak_wavelength,              # Scalar peak (nm)
    "intensity": peak_intensity,                # Peak intensity
    "timestamp": time.time(),
    "integration_time": self.calibration_data.integration_time,
    "num_scans": self.calibration_data.num_scans,
    "led_intensity": led_intensities.get(channel, 0),
    # Calibration references for processing
    "s_pol_ref": self.calibration_data.s_pol_ref.get(channel),
    "dark_s": self.calibration_data.dark_s.get(channel),
    "wave_min_index": self.calibration_data.wave_min_index,
    "wave_max_index": self.calibration_data.wave_max_index,
}

self.spectrum_acquired.emit(spectrum_data)  # Qt Signal (thread-safe)
```

---

### 2. **SIGNAL CONNECTION** (Main Thread)
**Location:** `main-simplified.py` line 1090

```python
self.data_mgr.spectrum_acquired.connect(
    self._on_spectrum_acquired,
    Qt.QueuedConnection,  # Thread-safe queued connection
)
```

---

### 3. **ACQUISITION CALLBACK** (Main Thread)
**Location:** `main-simplified.py` line 1769

```python
def _on_spectrum_acquired(self, data: dict):
    """Acquisition callback - queues data for processing."""
    # Add elapsed time
    data["elapsed_time"] = data["timestamp"] - self.experiment_start_time

    # Queue for processing thread (non-blocking)
    self._spectrum_queue.put_nowait(data)
```

---

### 4. **SPECTRUM PROCESSING** (Worker Thread)
**Location:** `affilabs/utils/spectrum_helpers.py` line 28

```python
@staticmethod
def process_spectrum_data(app: Application, data: dict) -> None:
    """Process spectrum data in worker thread."""
    channel = data["channel"]
    has_raw_data = data.get("raw_spectrum") is not None
    has_transmission = data.get("transmission_spectrum") is not None

    # Always update sidebar if we have ANY data
    if has_raw_data or has_transmission:
        SpectrumHelpers.queue_transmission_update(app, channel, data)
```

---

### 5. **TRANSMISSION UPDATE QUEUEING** (Worker Thread)
**Location:** `affilabs/utils/spectrum_helpers.py` line 134

```python
def queue_transmission_update(app: Application, channel: str, data: dict) -> None:
    """Queue transmission update for batch processing."""
    transmission = data.get("transmission_spectrum")
    raw_spectrum = data.get("raw_spectrum")

    # Calculate transmission if not provided
    if transmission is None and raw_spectrum is not None:
        ref_spectrum = app.data_mgr.calibration_data.s_pol_ref[channel]
        p_led = app.data_mgr.calibration_data.p_mode_intensities.get(channel)
        s_led = app.data_mgr.calibration_data.s_mode_intensities.get(channel)

        transmission = app.transmission_calc.calculate(
            p_spectrum=raw_spectrum,
            s_reference=ref_spectrum,
            p_led_intensity=p_led,
            s_led_intensity=s_led,
        )

        # Apply baseline correction
        transmission = app.baseline_corrector.correct(transmission)

    # Get wavelengths from calibration
    wavelengths = app.data_mgr.wave_data

    # Queue for batch processing
    app.ui_updates.queue_transmission_update(
        channel, wavelengths, transmission, raw_spectrum
    )
```

---

### 6. **UI UPDATE COORDINATOR QUEUEING** (Worker Thread → Main Thread)
**Location:** `affilabs/coordinators/ui_update_coordinator.py` line 74

```python
def queue_transmission_update(
    self,
    channel: str,
    wavelengths: np.ndarray,
    transmission: np.ndarray,
    raw_spectrum: np.ndarray | None = None,
):
    """Queue transmission curve update for batch processing."""
    self._pending_transmission_updates[channel] = {
        "wavelengths": wavelengths,      # Wavelength array (nm)
        "transmission": transmission,    # Transmission % array
        "raw_spectrum": raw_spectrum,    # Raw intensity array
    }
```

**Processing Queue** (Called by UI Timer ~100ms):
**Location:** Line 119

```python
def _update_transmission_curves(self):
    """Update transmission spectrum curves from pending queue."""
    for channel, update_data in self._pending_transmission_updates.items():
        if update_data is None:
            continue

        wavelengths = update_data["wavelengths"]
        transmission = update_data["transmission"]
        raw_spectrum = update_data.get("raw_spectrum")

        # Update via presenter
        if self._transmission_updates_enabled:
            self.spectroscopy_presenter.update_transmission(
                channel, wavelengths, transmission
            )

        if self._raw_spectrum_updates_enabled and raw_spectrum is not None:
            self.spectroscopy_presenter.update_raw_spectrum(
                channel, wavelengths, raw_spectrum
            )
```

---

### 7. **SPECTROSCOPY PRESENTER** (Main Thread)
**Location:** `affilabs/presenters/spectroscopy_presenter.py`

**Transmission Update** (Line 86):
```python
def update_transmission(
    self,
    channel: str,
    wavelengths: np.ndarray,
    transmission: np.ndarray,
):
    """Update transmission spectrum for a channel."""
    channel_idx = self._channel_to_idx[channel]  # a=0, b=1, c=2, d=3

    # Direct update to PyQtGraph curve
    if hasattr(self.main_window, "transmission_curves"):
        self.main_window.transmission_curves[channel_idx].setData(
            wavelengths,    # X-axis: wavelengths (nm)
            transmission,   # Y-axis: transmission (%)
        )
    # Fallback to sidebar API
    elif hasattr(self.main_window.sidebar, "update_transmission_plot"):
        self.main_window.sidebar.update_transmission_plot(
            channel, wavelengths, transmission
        )
```

**Raw Spectrum Update** (Line 141):
```python
def update_raw_spectrum(
    self,
    channel: str,
    wavelengths: np.ndarray,
    raw_spectrum: np.ndarray,
):
    """Update raw intensity spectrum for a channel."""
    channel_idx = self._channel_to_idx[channel]

    # Direct update to PyQtGraph curve
    if hasattr(self.main_window, "raw_data_curves"):
        self.main_window.raw_data_curves[channel_idx].setData(
            wavelengths,   # X-axis: wavelengths (nm)
            raw_spectrum,  # Y-axis: intensity (counts)
        )
    # Fallback to sidebar API
    elif hasattr(self.main_window.sidebar, "update_raw_plot"):
        self.main_window.sidebar.update_raw_plot(
            channel, wavelengths, raw_spectrum
        )
```

---

### 8. **SIDEBAR GRAPHS** (PyQtGraph Widgets)
**Location:** `affilabs/affilabs_sidebar.py`

**Transmission Plot Setup** (Line 640):
```python
self.transmission_curves = add_channel_curves(self.transmission_plot)
# Creates 4 curves: [curve_a, curve_b, curve_c, curve_d]
```

**Raw Data Plot Setup** (Line 666):
```python
self.raw_data_curves = add_channel_curves(self.raw_data_plot)
# Creates 4 curves: [curve_a, curve_b, curve_c, curve_d]
```

**Main Window Forwarding** (Line 1357-1370 in `affilabs_core_ui.py`):
```python
# Forward sidebar curves to main_window for direct access
self.transmission_curves = self.sidebar.transmission_curves
self.raw_data_curves = self.sidebar.raw_data_curves
```

**Direct Update** (Line 867):
```python
def update_transmission_plot(self, channel: str, wavelength, transmission_spectrum):
    """Update transmission plot for a channel."""
    idx = {"a": 0, "b": 1, "c": 2, "d": 3}.get(channel)

    if idx is not None and idx < len(self.transmission_curves):
        self.transmission_curves[idx].setData(wavelength, transmission_spectrum)
```

---

## Data Properties at Each Stage

### Required Properties for Graph Update:

**Transmission Graph:**
- `wavelengths`: NumPy array of wavelength values (nm) - X-axis
- `transmission`: NumPy array of transmission % (0-100) - Y-axis
- Both arrays must have same length

**Raw Data Graph:**
- `wavelengths`: NumPy array of wavelength values (nm) - X-axis
- `raw_spectrum`: NumPy array of intensity counts - Y-axis
- Both arrays must have same length

### Validation Checklist:

✅ **Data Acquisition Manager emits:**
- ✓ `raw_spectrum`: NumPy array from detector
- ✓ `transmission_spectrum`: NumPy array (if processed)
- ✓ `wavelengths`: NumPy array from calibration_data

✅ **Spectrum Helpers ensures:**
- ✓ Transmission calculated if missing
- ✓ Baseline correction applied
- ✓ Wavelengths from `app.data_mgr.wave_data`

✅ **UI Coordinator queues:**
- ✓ All arrays validated before queueing
- ✓ Batch updates every ~100ms

✅ **Presenter updates:**
- ✓ Direct setData() call to PyQtGraph curves
- ✓ Arrays must be NumPy types (not lists)

---

## Common Issues & Solutions

### Issue 1: "No data on graphs"
**Check:**
1. Is `calibration_data.wavelengths` set? (Required for X-axis)
2. Is `raw_spectrum` valid NumPy array?
3. Is transmission calculated or provided?

**Debug:**
```python
# In spectrum_helpers.py line ~215
print(f"[DEBUG] Channel {channel}: wavelengths={len(wavelengths)}, transmission={len(transmission)}")
```

### Issue 2: "Graphs not updating"
**Check:**
1. Is `spectroscopy_enabled` checkbox checked?
2. Is UI update timer running?
3. Are curves created in sidebar?

**Debug:**
```python
# In spectroscopy_presenter.py line ~105
print(f"[DEBUG] Updating {channel}: curves={hasattr(self.main_window, 'transmission_curves')}")
```

### Issue 3: "Array length mismatch"
**Check:**
1. `len(wavelengths) == len(transmission)`?
2. ROI indices match calibration?

**Debug:**
```python
# In data_acquisition_manager.py line ~1164
print(f"[DEBUG] Spectrum: {len(raw)}, Wavelengths: {len(self.calibration_data.wavelengths)}")
```

---

## Performance Notes

- **Thread Safety:** All cross-thread communication uses Qt signals (QueuedConnection)
- **Batch Updates:** UI updates batched every ~100ms to prevent overload
- **Queue Depth:** Processing queue prevents blocking acquisition thread
- **Direct Access:** PyQtGraph curves updated directly via `setData()` for speed

---

## Summary: Data Must Have

**At Emission (data_acquisition_manager.py):**
```python
{
    "channel": "a",                              # Required
    "wavelengths": np.ndarray,                   # Required for X-axis
    "raw_spectrum": np.ndarray,                  # Required for raw graph
    "transmission_spectrum": np.ndarray or None, # Calculated if None
}
```

**At Graph Update (spectroscopy_presenter.py):**
```python
# Transmission:
main_window.transmission_curves[idx].setData(
    wavelengths,   # NumPy array, X-axis (nm)
    transmission,  # NumPy array, Y-axis (%)
)

# Raw:
main_window.raw_data_curves[idx].setData(
    wavelengths,   # NumPy array, X-axis (nm)
    raw_spectrum,  # NumPy array, Y-axis (counts)
)
```

Both arrays **must** be NumPy arrays of equal length!
