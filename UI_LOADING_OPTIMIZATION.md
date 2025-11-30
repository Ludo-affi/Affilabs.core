# UI Loading Optimization Guide

## Current Issue
All UI elements load synchronously before the window appears, causing a delay between app launch and visible window.

## Solution: Progressive UI Loading

### Strategy 1: Deferred Heavy Widgets (RECOMMENDED)
Load essential UI first, defer expensive components until after window is visible.

#### What to defer:
1. **Spectroscopy plots** (transmission_plot, raw_data_plot) - heavy PyQtGraph initialization
2. **Bottom graph** (cycle_of_interest_graph) - second large plot widget
3. **Advanced settings panels** - rarely used on startup
4. **Device status widgets** - not needed until hardware connects
5. **Diagnostics panels** - developer/debug tools

#### Implementation:
```python
# In Application.__init__():
# Show window FIRST with minimal UI
self.main_window.show()
self.main_window.raise_()
self.main_window.activateWindow()
logger.info("✅ Window visible (minimal UI)")

# Process events to update display
QApplication.processEvents()

# THEN load heavy widgets in background
QTimer.singleShot(100, self._load_deferred_widgets)

def _load_deferred_widgets(self):
    """Load expensive UI components after window is visible."""
    # Load spectroscopy plots
    if hasattr(self.main_window, '_init_spectroscopy_plots'):
        self.main_window._init_spectroscopy_plots()

    # Load bottom graph
    if hasattr(self.main_window, '_init_cycle_graph'):
        self.main_window._init_cycle_graph()

    # Load advanced panels
    if hasattr(self.main_window.sidebar, '_init_advanced_panels'):
        self.main_window.sidebar._init_advanced_panels()

    logger.info("✅ Deferred widgets loaded")
```

### Strategy 2: Lazy Initialization
Create widgets only when user first accesses them.

#### Example - Transmission Dialog:
```python
@property
def transmission_dialog(self):
    """Lazy-load transmission dialog on first access."""
    if self._transmission_dialog is None:
        from transmission_spectrum_dialog import TransmissionSpectrumDialog
        self._transmission_dialog = TransmissionSpectrumDialog(self.main_window)
    return self._transmission_dialog
```

### Strategy 3: Splash Screen
Show a branded splash screen while UI loads.

```python
from PySide6.QtWidgets import QSplashScreen
from PySide6.QtGui import QPixmap

# Before QApplication.exec()
splash_pix = QPixmap("ui/img/splash.png")
splash = QSplashScreen(splash_pix)
splash.show()
app.processEvents()

# After UI ready
splash.finish(main_window)
```

### Strategy 4: Stub Widgets
Create placeholder widgets initially, replace with real implementations later.

```python
# Initial (fast):
self.transmission_plot = QLabel("Loading spectroscopy plots...")

# Later (after window shown):
def _upgrade_to_real_plot(self):
    self.transmission_plot.deleteLater()
    self.transmission_plot = create_spectroscopy_plot("Transmission")
    self.layout.replaceWidget(old, self.transmission_plot)
```

## Recommended Implementation Order

### Phase 1: Minimal Essential UI (< 100ms)
- Window frame
- Top navigation bar
- Power button
- Empty graph placeholders

### Phase 2: Core Controls (show window, then load these)
- Top timeline graph
- Sidebar tabs structure
- Recording controls

### Phase 3: Advanced Features (load on-demand)
- Bottom cycle graph
- Spectroscopy plots
- Diagnostics panels
- Settings sections

## Code Changes Needed

### 1. Split AffilabsMainWindow._setup_ui()
```python
def _setup_ui(self):
    """Setup minimal essential UI only."""
    self._setup_minimal_ui()  # Frame, navigation, power button

def _setup_deferred_ui(self):
    """Load heavy widgets after window is visible."""
    self._setup_graphs()
    self._setup_spectroscopy()
    self._setup_diagnostics()
```

### 2. Add deferred loading to Application.__init__()
```python
# Show window FIRST
self.main_window.show()
QApplication.processEvents()

# Load deferred UI
QTimer.singleShot(100, self.main_window._setup_deferred_ui)
```

### 3. Add loading indicators
```python
# While loading:
self.status_bar.showMessage("Loading UI components...")

# After loaded:
self.status_bar.showMessage("Ready")
```

## Performance Targets

| Phase | Target Time | User Experience |
|-------|-------------|-----------------|
| Window visible | < 200ms | User sees window immediately |
| Core controls | < 500ms | Can start interacting |
| Full UI loaded | < 1000ms | All features available |

## Testing
1. Time each phase with `logger.info` timestamps
2. Monitor with Task Manager (CPU/memory spikes)
3. Test on slower hardware
4. Measure with Qt profiling tools

## Maintenance Notes
- Keep minimal UI truly minimal - resist adding "just one more thing"
- Document which widgets are deferred
- Test that deferred widgets work correctly when lazy-loaded
- Consider user's typical workflow (what do they need first?)
