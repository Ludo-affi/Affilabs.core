# UI Adapter Usage Examples

The `UIAdapter` class provides a clean, stable API for interacting with the UI from the Application layer.

## Basic Setup

```python
from ui_adapter import UIAdapter
from affilabs_core_ui import MainWindowPrototype

# In Application.__init__():
self.main_window = MainWindowPrototype()
self.ui = UIAdapter(self.main_window)
```

## Common Usage Patterns

### Power & Connection Control

```python
# When searching for hardware
self.ui.set_power_state('searching')

# When connected
self.ui.set_power_state('connected')
self.ui.update_device_status('spectrometer', True, {'info': 'Ready'})
self.ui.update_device_status('led', True)

# When disconnected
self.ui.set_power_state('disconnected')
```

### Recording Control

```python
# After calibration completes
self.ui.enable_recording_controls()

# When recording starts
self.ui.set_recording_state(True)

# When recording stops
self.ui.set_recording_state(False)
```

### Calibration Progress

```python
# Show calibration dialog
dialog = self.ui.show_calibration_dialog(
    title="Full Calibration",
    message="Initializing hardware..."
)

# Update progress (in dialog object)
dialog.update_progress(50, "Calibrating LEDs...")
dialog.update_progress(100, "Calibration complete!")
dialog.mark_complete()
```

### Graph Data Updates

```python
# Update timeline graph for channel A (index 0)
self.ui.update_timeline_graph_data(0, time_array, signal_array)

# Update all channels
for ch_idx, (times, signals) in enumerate(channel_data):
    self.ui.update_timeline_graph_data(ch_idx, times, signals)

# Update transmission plot
self.ui.update_transmission_plot(0, wavelengths, transmission_percent)
```

### Reading Settings from UI

```python
# Get filter settings
if self.ui.get_filter_enabled():
    strength = self.ui.get_filter_strength()  # 0.0 - 1.0
    # Apply filtering...

# Get reference channel for subtraction
ref_channel = self.ui.get_reference_channel()  # 'a', 'b', 'c', 'd', or None

# Get Y-axis settings
if self.ui.get_y_axis_mode() == 'manual':
    min_val, max_val = self.ui.get_y_axis_range()
    # Apply manual scaling...

# Get LED intensities
led_values = self.ui.get_led_intensities()
# Returns: {'a': 255, 'b': 200, 'c': 180, 'd': 220}
```

### Setting LED Values

```python
# Set individual channel
self.ui.set_led_intensity('a', 255)

# Set all channels from calibration
calibrated_values = {'a': 255, 'b': 198, 'c': 175, 'd': 210}
for channel, intensity in calibrated_values.items():
    self.ui.set_led_intensity(channel, intensity)
```

### Channel Visibility

```python
# Hide channel C (index 2)
self.ui.set_channel_visibility(2, False)

# Show all channels
for i in range(4):
    self.ui.set_channel_visibility(i, True)
```

### Status Messages

```python
# Show temporary message (5 seconds)
self.ui.show_status_message("Calibration complete!")

# Show message for 10 seconds
self.ui.show_status_message("Processing data...", duration=10000)

# Show permanent message
self.ui.show_status_message("Recording in progress", duration=0)

# Clear message
self.ui.clear_status_message()
```

### Device Status Updates

```python
# Update spectrometer status
self.ui.update_device_status('spectrometer', True, {
    'temperature': 25.5,
    'integration_time': 10.0
})

# Update LED status with details
self.ui.update_device_status('led', True, {
    'total_hours': 150.5,
    'maintenance_due': False
})

# Mark component as not ready
self.ui.update_device_status('pump', False, {
    'error': 'Not connected'
})
```

### Afterglow Status

```python
# Update afterglow correction value
self.ui.update_afterglow_status(2.5)  # 2.5 seconds
```

## Benefits of Using UIAdapter

✅ **Decoupling**: Business logic doesn't know UI implementation details
✅ **Stability**: UI changes don't break application code
✅ **Type Safety**: Clear method signatures with type hints
✅ **Discoverability**: IDE autocomplete shows all available methods
✅ **Maintainability**: Single place to update if UI API changes
✅ **Testing**: Easy to mock for unit tests

## Migration from Direct UI Access

**Before (tightly coupled):**
```python
self.main_window._set_power_button_state('connected')
self.main_window._update_power_button_style()
self.main_window.full_timeline_graph.curves[0].setData(x, y)
```

**After (loosely coupled via adapter):**
```python
self.ui.set_power_state('connected')
self.ui.update_timeline_graph_data(0, x, y)
```

## When to Add New Methods

Add methods to `UIAdapter` when you need to:
1. Update UI state from application logic
2. Read user settings/selections from UI
3. Show/hide UI elements based on app state
4. Update graphs or displays with new data

Keep methods **focused** and **semantic** - each method should do one clear thing.
