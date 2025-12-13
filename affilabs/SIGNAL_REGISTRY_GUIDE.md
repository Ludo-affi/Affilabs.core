# Signal Registry Pattern - Implementation Guide

The signal registry pattern organizes all Qt signal connections in a centralized, maintainable structure.

## Implementation

All signal connections are registered in `main_simplified.py` via the `_connect_signals()` method, which delegates to specialized connection methods:

```python
def _connect_signals(self):
    """Connect all signals in organized registry."""
    self._connect_hardware_signals()
    self._connect_data_acquisition_signals()
    self._connect_recording_signals()
    self._connect_kinetic_signals()
    self._connect_ui_control_signals()
    self._connect_ui_request_signals()
```

## Organization

### 1. Hardware Manager Signals
Connections from `hardware_mgr` to application handlers:
- `hardware_connected` → `_on_hardware_connected`
- `hardware_disconnected` → `_on_hardware_disconnected`
- `connection_progress` → `_on_connection_progress`
- `error_occurred` → `_on_hardware_error`

### 2. Data Acquisition Signals
Connections from `data_mgr` to application handlers:
- Spectrum data: `spectrum_acquired`
- Calibration lifecycle: `calibration_started`, `calibration_complete`, `calibration_failed`, `calibration_progress`
- Acquisition lifecycle: `acquisition_started`, `acquisition_stopped`, `acquisition_error`

### 3. Recording Signals
Connections from `recording_mgr`:
- `recording_started`, `recording_stopped`, `recording_error`, `event_logged`

### 4. Kinetic Signals
Connections from `kinetic_mgr`:
- `pump_initialized`, `pump_error`, `pump_state_changed`, `valve_switched`

### 5. UI Control Signals
Connections from UI controls (buttons, sliders, checkboxes) to application:
- **Graph Controls**: grid, autoscale, manual scale, axis selection, cursor movements
- **Visual Accessibility**: colorblind mode
- **Export Controls**: CSV, image export
- **Data Processing**: reference channel, filtering
- **Hardware Settings**: polarizer, LED intensities, units
- **Calibration**: simple, full, OEM calibration buttons
- **Cycle Control**: start cycle button

### 6. UI Request Signals
High-level requests from UI to application:
- **Power Control**: `power_on_requested`, `power_off_requested`
- **Recording Control**: `recording_start_requested`, `recording_stop_requested`
- **Acquisition Control**: `acquisition_pause_requested`

## Benefits

### ✅ **Easy Debugging**
All connections in one place - quickly see what's connected:
```python
# Instead of searching through 2000+ lines of code,
# just look at the 6 registry methods
```

### ✅ **Clear Documentation**
Each registry method is self-documenting:
```python
def _connect_hardware_signals(self):
    """Register hardware manager signal connections."""
    hw = self.hardware_mgr
    hw.hardware_connected.connect(self._on_hardware_connected)
    # All hardware signals in one place
```

### ✅ **Easy to Maintain**
Adding/removing connections is straightforward:
```python
# Need a new signal? Add it to the appropriate registry method
def _connect_recording_signals(self):
    rec = self.recording_mgr
    rec.recording_started.connect(self._on_recording_started)
    rec.recording_paused.connect(self._on_recording_paused)  # NEW!
```

### ✅ **Prevents Duplication**
Clear organization prevents accidentally connecting the same signal twice.

### ✅ **Better Testing**
Each category can be tested independently:
```python
def test_hardware_signals():
    app = Application()
    # Test only hardware signal connections
    assert app.hardware_mgr.hardware_connected.receivers(...)
```

### ✅ **Follows Qt Best Practices**
Organized signal/slot connections as recommended by Qt documentation.

## Usage Examples

### Adding a New Signal Connection

**Step 1**: Identify the category
```python
# Is it from a manager or from the UI?
# Is it a control signal or a request signal?
```

**Step 2**: Add to appropriate registry method
```python
def _connect_ui_control_signals(self):
    ui = self.main_window
    # ... existing connections ...

    # Add new connection
    ui.new_button.clicked.connect(self._on_new_button_clicked)
```

**Step 3**: Implement handler
```python
def _on_new_button_clicked(self):
    """Handle new button click."""
    logger.info("New button clicked")
    # Implementation...
```

### Debugging a Signal Connection

**Problem**: "My button click doesn't do anything"

**Solution**: Check the registry
```python
# 1. Find which registry method should have it
def _connect_ui_control_signals(self):
    # Look for your button here

# 2. Verify the connection exists
ui.my_button.clicked.connect(self._on_my_button_clicked)

# 3. Verify the handler exists
def _on_my_button_clicked(self):
    # Implementation should be here
```

### Temporarily Disabling a Connection

```python
def _connect_hardware_signals(self):
    hw = self.hardware_mgr
    hw.hardware_connected.connect(self._on_hardware_connected)
    # hw.hardware_disconnected.connect(self._on_hardware_disconnected)  # Commented out for testing
```

## Migration from Old Pattern

**Before (scattered connections):**
```python
# Line 150:
self.hardware_mgr.hardware_connected.connect(self._on_hardware_connected)

# Line 890:
self.main_window.power_on_requested.connect(self._on_power_on_requested)

# Line 1205:
self.data_mgr.spectrum_acquired.connect(self._on_spectrum_acquired)

# Line 1876:
self.recording_mgr.recording_started.connect(self._on_recording_started)
```

**After (centralized registry):**
```python
def _connect_signals(self):
    """All connections organized by category."""
    self._connect_hardware_signals()      # Line 150 moved here
    self._connect_data_acquisition_signals()  # Line 1205 moved here
    self._connect_recording_signals()     # Line 1876 moved here
    self._connect_ui_request_signals()    # Line 890 moved here
```

## Best Practices

1. **Keep registry methods focused**: One category per method
2. **Use local variables**: `ui = self.main_window` for readability
3. **Comment complex connections**: Explain why, not what
4. **Group related signals**: Keep lifecycle signals together
5. **Add new signals to existing methods**: Don't create new registry methods unnecessarily

## Debugging Checklist

When a signal/slot connection isn't working:

- [ ] Connection exists in registry
- [ ] Handler method exists and is spelled correctly
- [ ] Signal signature matches slot signature
- [ ] Object emitting signal still exists (not deleted)
- [ ] Connection made before signal is emitted
- [ ] No exceptions in handler (check logs)

## Future Enhancements

Potential improvements to the pattern:

1. **Signal Spy**: Log all signal emissions for debugging
2. **Connection Validator**: Verify all connections at startup
3. **Auto-documentation**: Generate connection diagram from registry
4. **Connection Groups**: Enable/disable groups of connections dynamically

## Integration Status

✅ **Fully Implemented** in `main_simplified.py`
✅ **All 50+ connections** organized into 6 categories
✅ **Tested and working** with full application
✅ **Backward compatible** with existing code

Last Updated: November 22, 2025
