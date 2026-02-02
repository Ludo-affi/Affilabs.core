# UI Architecture Documentation

**Last Updated**: February 2, 2026
**Author**: AffiLabs Team
**Related Docs**: [Acquisition System](ACQUISITION_SYSTEM.md), [Method & Cycle System](METHOD_CYCLE_SYSTEM.md)

---

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Main Window Structure](#main-window-structure)
4. [Sidebar Architecture](#sidebar-architecture)
5. [Dialog System](#dialog-system)
6. [Signal & Slot Architecture](#signal--slot-architecture)
7. [Widget Hierarchy](#widget-hierarchy)
8. [Navigation System](#navigation-system)
9. [Graph Components](#graph-components)
10. [API Reference](#api-reference)
11. [Troubleshooting](#troubleshooting)

---

## Overview

### Purpose

The UI Architecture provides a clean separation between presentation (UI) and business logic (managers/services). Built with PySide6 (Qt for Python), the system emphasizes:

- **Modularity**: Independent components with clear interfaces
- **Signal-Based Communication**: Loose coupling between layers
- **Lazy Loading**: Deferred widget creation for fast startup
- **Responsive Design**: Non-blocking operations, smooth animations

### Key Features

- **Multi-Page Navigation**: Sensorgram, Edits, Analysis tabs
- **Modular Sidebar**: 6 tabs (Device Status, Graphic Control, Method, Flow, Export, Spark)
- **Lazy-Loaded Dialogs**: On-demand creation of complex windows
- **Theme System**: Consistent colors, fonts, spacing
- **Real-Time Updates**: Live data graphs at 10 Hz

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                        │
│  (main.py - Application class extends QApplication)        │
│  ├─ Managers (HardwareManager, DataAcquisitionManager)     │
│  ├─ Services (CalibrationService, ExportManager)           │
│  ├─ Coordinators (AcquisitionEventCoordinator)             │
│  └─ Signal Connections (UI ← → Business Logic)             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Creates and configures
                       │
┌──────────────────────▼──────────────────────────────────────┐
│               MAIN WINDOW (AffilabsMainWindow)              │
│  QMainWindow - Top-level window container                  │
│  ├─ Menu Bar (File, View, Tools, Help)                     │
│  ├─ Toolbar (Power, Record, Pause buttons)                 │
│  ├─ Status Bar (Connection, acquisition status)            │
│  └─ Central Widget (QSplitter with content + sidebar)      │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
┌───────▼──────────┐         ┌────────▼─────────┐
│  CONTENT AREA    │         │  SIDEBAR         │
│  (QStackedWidget)│         │  (AffilabsSidebar)│
└───────┬──────────┘         └────────┬─────────┘
        │                             │
┌───────▼─────────────────────────────▼────────────────────┐
│  PAGES (Lazy-Loaded)    │   TABS (6 sections)            │
├──────────────────────────┼────────────────────────────────┤
│  0. Sensorgram          │   0. Device Status             │
│     ├─ Full Timeline    │   1. Graphic Control           │
│     └─ Cycle Detail     │   2. Method (Static)           │
│  1. Edits               │   3. Flow (Pumps)              │
│     └─ Post-processing  │   4. Export                    │
│  2. Analysis            │   5. Spark AI Help             │
│     └─ Multi-cycle      │                                │
└─────────────────────────┴────────────────────────────────┘
                       │
                       │ On-Demand Creation
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                    DIALOG MANAGER                           │
│  ├─ LiveDataDialog (transmission + raw plots)              │
│  ├─ TransmissionSpectrumDialog (spectroscopy view)         │
│  ├─ MethodBuilderDialog (Spark-powered cycle creation)     │
│  ├─ CycleTemplateDialog (template library)                 │
│  ├─ QueuePresetDialog (preset workflow manager)            │
│  └─ AdvancedSettingsDialog (system configuration)          │
└─────────────────────────────────────────────────────────────┘
```

---

## Main Window Structure

### AffilabsMainWindow

**File**: `affilabs/affilabs_core_ui.py`

**Class Hierarchy**:
```
QMainWindow (Qt base class)
    └─ AffilabsMainWindow
```

**Components**:

```python
class AffilabsMainWindow(QMainWindow):
    # === SIGNALS (UI → Application) ===
    power_on_requested = Signal()
    power_off_requested = Signal()
    recording_start_requested = Signal()
    recording_stop_requested = Signal()
    acquisition_pause_requested = Signal(bool)  # True=pause, False=resume
    export_requested = Signal(dict)
    send_to_edits_requested = Signal()

    def __init__(self):
        # === WINDOW SETUP ===
        self.setWindowTitle("ezControl 2.0")
        self.setMinimumSize(1400, 800)

        # === CENTRAL WIDGET (Splitter) ===
        self.splitter = QSplitter(Qt.Horizontal)

        # Left: Content area (main graphs/tabs)
        self.content_stack = QStackedWidget()

        # Right: Sidebar (controls)
        self.sidebar = AffilabsSidebar()

        self.splitter.addWidget(self.content_stack)
        self.splitter.addWidget(self.sidebar)
        self.setCentralWidget(self.splitter)

        # === TOOLBAR ===
        self.power_btn = QPushButton("⚡ Power")
        self.record_btn = QPushButton("⏺ Record")
        self.pause_btn = QPushButton("⏸ Pause")

        # === PAGES (Lazy-Loaded) ===
        self._sensorgram_page = None  # Created on first access
        self._edits_tab = None
        self._analysis_tab = None
```

---

### Toolbar Buttons

**Power Button**:
```python
self.power_btn = QPushButton("⚡ Power")
self.power_btn.setCheckable(True)  # Toggle state
self.power_btn.setProperty("powerState", "disconnected")

# Visual states: 'disconnected', 'searching', 'connected'
# Styled via CSS property selector
```

**Record Button**:
```python
self.record_btn = QPushButton("⏺ Record")
self.record_btn.setCheckable(True)
self.record_btn.setEnabled(False)  # Disabled until calibration

# When clicked → recording_start_requested.emit()
```

**Pause Button**:
```python
self.pause_btn = QPushButton("⏸ Pause")
self.pause_btn.setCheckable(True)
self.pause_btn.setEnabled(False)  # Disabled until acquisition

# When toggled → acquisition_pause_requested.emit(checked)
```

---

### Status Bar

**Connection Status**:
```python
self.connection_status = QLabel("Disconnected")
self.connection_status.setStyleSheet("color: #E74C3C;")  # Red

# Updated via _set_power_button_state():
# - 'disconnected' → Red
# - 'searching' → Orange + animated ellipsis
# - 'connected' → Green
```

**Acquisition Status**:
```python
self.acquisition_status = QLabel("⚫ Idle")

# States:
# - "⚫ Idle" (no acquisition)
# - "🔴 Acquiring..." (active)
# - "⏸️ Paused" (paused)
```

---

## Sidebar Architecture

### AffilabsSidebar

**File**: `affilabs/affilabs_sidebar.py`

**Structure**:
```python
class AffilabsSidebar(QWidget):
    def __init__(self):
        # === TAB WIDGET ===
        self.tabs = QTabWidget()

        # === TAB BUILDERS (Modular Construction) ===
        self._build_device_status_tab()   # Tab 0
        self._build_graphic_control_tab() # Tab 1
        self._build_method_tab()          # Tab 2
        self._build_flow_tab()            # Tab 3
        self._build_export_tab()          # Tab 4
        self._build_spark_tab()           # Tab 5
```

---

### Tab 0: Device Status

**Purpose**: Display hardware connection status

**Components**:
- **Controller Status**: Firmware, COM port, LED control
- **Detector Status**: Model, serial, integration time
- **Pump Status**: Type, connection, valve state
- **Subunit Health**: Sensor IQ, Optics, Fluidics (✅/❌)

**Builder**: `DeviceStatusTabBuilder` (affilabs/sidebar_tabs/AL_device_status_builder.py)

---

### Tab 1: Graphic Control

**Purpose**: Graph display and filtering controls

**Components**:
- **Plots**: Transmission, Raw Data (spectroscopy diagnostics)
- **Axis Controls**: Auto/Manual scaling, min/max inputs
- **Filter Controls**: EMA smoothing (None/Light/Medium/Heavy)
- **Accessibility**: Colorblind mode, grid toggle

**Builder**: `GraphicControlTabBuilder` (affilabs/sidebar_tabs/AL_graphic_control_builder.py)

---

### Tab 2: Method (Static Experiments)

**Purpose**: Build and execute static SPR experiments

**Components**:
- **Cycle Builder**: Duration, comment, buffer/sample selection
- **Queue Summary**: ResizeToContents table with Type, Duration, Comment
- **Spark Integration**: AI-powered method creation
- **Templates**: Saved cycle configurations

**Builder**: `MethodTabBuilder` (affilabs/sidebar_tabs/AL_method_builder.py)

**Key Widget**: `QueueSummaryWidget` (drag-and-drop reordering)

---

### Tab 3: Flow (Pump Experiments)

**Purpose**: Pump-controlled flow experiments

**Components**:
- **Pump Controls**: Flow rate, volume, priming
- **Valve Controls**: 6-port (load/inject), 3-way (waste/load)
- **Cycle Queue**: Same QueueSummaryWidget as Method tab
- **Flow Profiles**: Constant, gradient, pulse

**Builder**: `FlowTabBuilder` (affilabs/sidebar_tabs/AL_flow_builder.py)

---

### Tab 4: Export

**Purpose**: Data export configuration

**Components**:
- **Format Selection**: Excel, CSV, JSON
- **Channel Selection**: A, B, C, D checkboxes
- **Destination**: Directory picker
- **User Profile**: Experiment metadata (user, experiment name)
- **File Size Estimate**: Real-time calculation

**Builder**: `ExportTabBuilder` (affilabs/sidebar_tabs/AL_export_builder.py)

---

### Tab 5: Spark AI Help

**Purpose**: Natural language Q&A assistant

**Components**:
- **Conversation View**: Question/answer bubbles
- **Input Field**: Text entry with Enter-to-send
- **Knowledge Base**: TinyDB + pattern matching + website lookup
- **Feedback**: Thumbs up/down for response quality

**Builder**: Built inline in `_build_spark_tab()`

**Widget**: `SparkHelpWidget` (affilabs/widgets/spark_help_widget.py)

---

## Dialog System

### DialogManager (Lazy Loading)

**File**: `affilabs/coordinators/dialog_manager.py`

**Purpose**: Create dialogs only when first accessed

```python
class DialogManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self._dialogs = {}  # Cache created dialogs

    def get_live_data_dialog(self):
        """Get or create LiveDataDialog."""
        if "live_data" not in self._dialogs:
            from affilabs.dialogs.live_data_dialog import LiveDataDialog
            self._dialogs["live_data"] = LiveDataDialog(self.main_window)
        return self._dialogs["live_data"]

    def get_transmission_dialog(self):
        """Get or create TransmissionSpectrumDialog."""
        if "transmission" not in self._dialogs:
            from transmission_spectrum_dialog import TransmissionSpectrumDialog
            self._dialogs["transmission"] = TransmissionSpectrumDialog(self.main_window)
        return self._dialogs["transmission"]
```

**Benefits**:
- Faster startup (dialogs created on-demand)
- Lower memory (unused dialogs not created)
- Single instance (dialog reused across sessions)

---

### LiveDataDialog

**File**: `affilabs/dialogs/live_data_dialog.py`

**Purpose**: Real-time transmission and raw spectrum plots

**Layout**:
```
┌─────────────────────────────────────────────────────┐
│  LiveDataDialog                                     │
├─────────────────────────────────────────────────────┤
│  Channel Selection: [A] [B] [C] [D]                 │
├─────────────────────────────────────────────────────┤
│                                                     │
│   Transmission Plot (P/S %)                         │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━                      │
│                                                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│   Raw Data Plot (Counts)                            │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━                      │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Update Method**:
```python
def update_transmission_plot(self, channel, wavelengths, transmission):
    """Update transmission plot for channel."""
    curve = self.transmission_curves[channel]
    curve.setData(wavelengths, transmission)
```

---

### MethodBuilderDialog (Spark Integration)

**File**: `affilabs/widgets/method_builder_dialog.py`

**Purpose**: AI-powered cycle creation

**Features**:
- **Natural Language Input**: "30 second baseline, then 5 minute association with sample A"
- **Spark Parsing**: Converts text → cycle parameters
- **Preview**: Shows generated cycles before adding
- **Templates**: Quick access to saved configurations

**Example Interaction**:
```
User: "3 minute baseline, 10 minute association, 5 minute dissociation"

Spark: I'll create 3 cycles:
       1. Baseline - 180s (Buffer)
       2. Association - 600s (Sample)
       3. Dissociation - 300s (Buffer)

[Preview] [Add to Queue] [Cancel]
```

---

### Advanced Settings Dialog

**File**: `affilabs/dialogs/advanced_settings_dialog.py`

**Categories**:

1. **Hardware**:
   - Polarizer settle time
   - Detector wait time
   - Pump flow rate limits

2. **Calibration**:
   - Target intensity ranges
   - Convergence thresholds
   - LED intensity limits

3. **Display**:
   - Units (RU/nm/degrees)
   - Graph colors
   - Update rates

4. **Export**:
   - Default formats
   - Filename templates
   - Auto-export on completion

---

## Signal & Slot Architecture

### Signal Flow Patterns

#### Pattern 1: User Action → Application

```
┌─────────────────┐
│  Power Button   │  (UI Component)
│  clicked()      │
└────────┬────────┘
         │
         │ Qt Signal
         │
┌────────▼────────┐
│ power_on_       │  (MainWindow Signal)
│ requested.emit()│
└────────┬────────┘
         │
         │ Connected in Application.__init__
         │
┌────────▼────────┐
│ _on_power_on()  │  (Application Method)
│ → HardwareManager.scan_and_connect()
└─────────────────┘
```

---

#### Pattern 2: Manager → UI Update

```
┌─────────────────┐
│ HardwareManager │
│ hardware_       │
│ connected.emit()│
└────────┬────────┘
         │
         │ Qt Signal
         │
┌────────▼────────┐
│ _on_hardware_   │  (Application Method)
│ connected()     │
└────────┬────────┘
         │
         │ Direct call
         │
┌────────▼────────────┐
│ main_window.        │  (MainWindow Method)
│ _set_power_button_  │
│ state('connected')  │
└─────────────────────┘
```

---

#### Pattern 3: Acquisition → Graph Update

```
┌─────────────────────┐
│ DataAcquisitionMgr  │
│ spectrum_acquired.  │
│ emit(data)          │
└────────┬────────────┘
         │
         │ Qt Signal (QueuedConnection)
         │
┌────────▼────────────┐
│ _on_spectrum_       │  (Application Method)
│ acquired(data)      │
└────────┬────────────┘
         │
         │ Queue data
         │
┌────────▼────────────┐
│ _spectrum_queue.    │  (Lock-Free Queue)
│ put(data)           │
└────────┬────────────┘
         │
         │ Processing Thread
         │
┌────────▼────────────┐
│ _processing_worker()│
│ → Update graphs     │
└─────────────────────┘
```

---

### Connection Types

**Direct Connection** (same thread):
```python
button.clicked.connect(self._on_button_clicked)  # Immediate call
```

**Queued Connection** (cross-thread):
```python
data_mgr.spectrum_acquired.connect(
    self._on_spectrum_acquired,
    Qt.QueuedConnection  # Thread-safe via event loop
)
```

**Auto Connection** (Qt decides):
```python
button.clicked.connect(self._handler)  # Direct if same thread, queued otherwise
```

---

## Widget Hierarchy

### Main Window Tree

```
AffilabsMainWindow (QMainWindow)
├─ Central Widget (QWidget)
│  └─ Splitter (QSplitter)
│     ├─ Content Area (QStackedWidget)
│     │  ├─ Page 0: Sensorgram (QWidget)
│     │  │  ├─ Full Timeline Graph (PlotWidget)
│     │  │  └─ Cycle Detail Graph (PlotWidget)
│     │  ├─ Page 1: Edits Tab (EditsTab)
│     │  │  └─ Post-processing controls
│     │  └─ Page 2: Analysis Tab (AnalysisTab)
│     │     └─ Multi-cycle overlay
│     └─ Sidebar (AffilabsSidebar)
│        └─ Tab Widget (QTabWidget)
│           ├─ Tab 0: Device Status (QWidget)
│           ├─ Tab 1: Graphic Control (QWidget)
│           ├─ Tab 2: Method (QWidget)
│           │  └─ Queue Summary (QueueSummaryWidget)
│           ├─ Tab 3: Flow (QWidget)
│           │  └─ Queue Summary (QueueSummaryWidget)
│           ├─ Tab 4: Export (QWidget)
│           └─ Tab 5: Spark Help (SparkHelpWidget)
├─ Toolbar (QToolBar)
│  ├─ Power Button (QPushButton)
│  ├─ Record Button (QPushButton)
│  └─ Pause Button (QPushButton)
└─ Status Bar (QStatusBar)
   ├─ Connection Status (QLabel)
   └─ Acquisition Status (QLabel)
```

---

### Widget Access Patterns

**Direct Reference** (forwarded from sidebar):
```python
# In AffilabsMainWindow._setup_ui():
self.channel_a_input = self.sidebar.channel_a_input
self.filter_slider = self.sidebar.filter_slider
self.ref_combo = self.sidebar.ref_combo
```

**Property Access** (via main window):
```python
# In Application class:
integration_time = self.main_window.sidebar.integration_time_input.value()
```

**Signal-Based Access** (loose coupling):
```python
# Sidebar emits signal → Application handles
self.main_window.sidebar.calibration_requested.connect(
    self._start_calibration
)
```

---

## Navigation System

### Page Switching

**QStackedWidget**:
```python
self.content_stack = QStackedWidget()

# Add pages
self.content_stack.addWidget(sensorgram_page)  # Index 0
self.content_stack.addWidget(edits_tab)        # Index 1
self.content_stack.addWidget(analysis_tab)     # Index 2

# Switch page
self.content_stack.setCurrentIndex(1)  # Show Edits tab
```

**Navigation Bar** (custom implementation):
```python
nav_buttons = [
    QPushButton("Sensorgram"),
    QPushButton("Edits"),
    QPushButton("Analysis")
]

for i, btn in enumerate(nav_buttons):
    btn.clicked.connect(lambda checked, idx=i: self.content_stack.setCurrentIndex(idx))
```

---

### Lazy Page Loading

**Deferred Creation**:
```python
def _load_sensorgram_page(self):
    """Create Sensorgram page on first access."""
    if self._sensorgram_page is None:
        self._sensorgram_page = QWidget()

        # Create graphs
        self.full_timeline_graph = create_time_plot("Full Sensorgram")
        self.cycle_detail_graph = create_time_plot("Active Cycle")

        # Layout
        layout = QVBoxLayout(self._sensorgram_page)
        layout.addWidget(self.full_timeline_graph)
        layout.addWidget(self.cycle_detail_graph)

        # Add to stack
        self.content_stack.addWidget(self._sensorgram_page)

    return self._sensorgram_page
```

**Trigger**:
```python
# Called on first show or when user navigates
self._load_sensorgram_page()
self.content_stack.setCurrentWidget(self._sensorgram_page)
```

---

## Graph Components

### PyQtGraph Integration

**Plot Creation**:
```python
import pyqtgraph as pg

def create_time_plot(title):
    """Create a time-series plot."""
    plot = pg.PlotWidget(title=title)

    # Styling
    plot.setBackground('w')  # White background
    plot.showGrid(x=True, y=True, alpha=0.3)

    # Axes
    plot.setLabel('left', 'SPR Signal', units='RU')
    plot.setLabel('bottom', 'Time', units='s')

    return plot
```

---

### Multi-Channel Curves

**Add Channel Curves**:
```python
def add_channel_curves(plot):
    """Add curves for channels A, B, C, D."""
    colors = {
        'a': '#E74C3C',  # Red
        'b': '#3498DB',  # Blue
        'c': '#2ECC71',  # Green
        'd': '#F39C12'   # Orange
    }

    curves = {}
    for ch, color in colors.items():
        curve = plot.plot([], [], pen=pg.mkPen(color, width=2), name=f"Ch {ch.upper()}")
        curves[ch] = curve

    return curves
```

---

### Real-Time Updates

**Update Pattern** (throttled to 10 Hz):
```python
class Application(QApplication):
    def __init__(self):
        # Update timer (100ms = 10 Hz)
        self._ui_update_timer = QTimer()
        self._ui_update_timer.timeout.connect(self._process_pending_ui_updates)
        self._ui_update_timer.start(100)

        self._pending_updates = {'a': None, 'b': None, 'c': None, 'd': None}

    def _queue_graph_update(self, channel, time_data, spr_data):
        """Queue update (overwrites pending)."""
        self._pending_updates[channel] = (time_data, spr_data)

    def _process_pending_ui_updates(self):
        """Apply queued updates (called at 10 Hz)."""
        for ch, data in self._pending_updates.items():
            if data is not None:
                time_data, spr_data = data
                curve = self.main_window.full_timeline_graph.curves[ch]
                curve.setData(time_data, spr_data)
                self._pending_updates[ch] = None  # Clear
```

**Why Throttle?** Prevents UI freezing - acquisition at 1 Hz, processing faster → throttle display to 10 Hz max.

---

## API Reference

### MainWindow

**Power Button Control**:
```python
# Set visual state
main_window._set_power_button_state('disconnected')  # Red
main_window._set_power_button_state('searching')    # Orange + animation
main_window._set_power_button_state('connected')    # Green
```

**Recording State**:
```python
main_window.update_recording_state(is_recording=True)   # Show "⏺ Recording"
main_window.update_recording_state(is_recording=False)  # Show "⏺ Record"
```

**Enable Controls**:
```python
main_window.enable_controls()  # Enable record/pause after calibration
```

---

### Sidebar

**Get Widget References**:
```python
# LED intensity inputs
a_input = main_window.sidebar.channel_a_input
b_input = main_window.sidebar.channel_b_input

# Settings
integration_time = main_window.sidebar.integration_time_input.value()
num_scans = main_window.sidebar.num_scans_input.value()
```

**Set Polarizer Mode**:
```python
main_window.sidebar.set_polarizer_mode('s')  # S-pol
main_window.sidebar.set_polarizer_mode('p')  # P-pol
```

**Set Operation Mode**:
```python
main_window.sidebar.set_operation_mode('method')  # Enable Method tab
main_window.sidebar.set_operation_mode('flow')    # Enable Flow tab
```

---

### DialogManager

**Show Live Data Dialog**:
```python
dialog = app.dialog_manager.get_live_data_dialog()
dialog.show()
```

**Update Live Data**:
```python
dialog.update_transmission_plot('a', wavelengths, transmission)
dialog.update_raw_data_plot('a', wavelengths, raw_spectrum)
```

---

### Graphs

**Update Timeline Graph**:
```python
# Get curve for channel A
curve_a = main_window.full_timeline_graph.curves['a']

# Update data
curve_a.setData(time_array, spr_array)
```

**Update Cycle Detail Graph**:
```python
curve_b = main_window.cycle_detail_graph.curves['b']
curve_b.setData(cycle_time, cycle_spr)
```

---

## Troubleshooting

### UI Freezing

**Symptoms**: Application unresponsive during long operations

**Cause**: Blocking operation in main thread

**Fix**: Move to background thread
```python
# BAD (blocks UI):
def calibrate():
    for i in range(100):
        do_work()  # 100ms each = 10 seconds total (UI frozen)

# GOOD (non-blocking):
def calibrate():
    def worker():
        for i in range(100):
            do_work()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
```

---

### Signal Not Firing

**Symptoms**: Signal emitted but slot never called

**Check Connection**:
```python
# Verify connection
result = button.clicked.connect(handler)
if not result:
    print("Connection failed!")

# Check if signal exists
if not hasattr(button, 'clicked'):
    print("Signal doesn't exist!")
```

**Debug Signal**:
```python
def handler(*args, **kwargs):
    print(f"Signal received: args={args}, kwargs={kwargs}")

button.clicked.connect(handler)
```

---

### Widget Not Visible

**Symptoms**: Widget created but not showing

**Checks**:
1. **Added to layout?**
   ```python
   layout.addWidget(widget)  # Must be in layout
   ```

2. **Parent set?**
   ```python
   widget = QWidget(parent=main_window)  # Parent determines visibility
   ```

3. **Show called?**
   ```python
   widget.show()  # Some widgets need explicit show()
   ```

4. **Size too small?**
   ```python
   widget.setMinimumSize(100, 50)  # Ensure visible size
   ```

---

### Graph Not Updating

**Symptoms**: `curve.setData()` called but graph doesn't change

**Force Repaint**:
```python
curve.setData(x, y)
plot.update()  # Force redraw
```

**Check Data**:
```python
print(f"Data length: {len(x)}, {len(y)}")
print(f"Data range: x=[{min(x)}, {max(x)}], y=[{min(y)}, {max(y)}]")
```

**Auto-Range**:
```python
plot.enableAutoRange()  # Reset view to fit data
```

---

### Memory Leak

**Symptoms**: Memory usage grows over time

**Causes**:
1. **Curves not cleared**: Old data accumulates
2. **Dialogs not reused**: New dialog every time
3. **Signals not disconnected**: Handlers keep references

**Fix**:
```python
# Limit curve data
MAX_POINTS = 10000
if len(time_data) > MAX_POINTS:
    time_data = time_data[-MAX_POINTS:]
    spr_data = spr_data[-MAX_POINTS:]

# Reuse dialogs
dialog = dialog_manager.get_live_data_dialog()  # Returns cached instance

# Disconnect signals when done
button.clicked.disconnect(handler)
```

---

## Best Practices

### 1. Use Signals for UI-Business Logic Communication

❌ **BAD** (tight coupling):
```python
# In UI code:
def on_button_clicked(self):
    hardware_mgr.connect()  # UI directly calls manager
```

✅ **GOOD** (loose coupling):
```python
# In UI code:
button_clicked = Signal()

def on_button_clicked(self):
    self.button_clicked.emit()  # Just emit signal

# In Application:
main_window.button_clicked.connect(hardware_mgr.connect)
```

---

### 2. Lazy-Load Heavy Widgets

❌ **BAD** (slow startup):
```python
def __init__(self):
    self.dialog = ComplexDialog()  # Created immediately (slow)
```

✅ **GOOD** (fast startup):
```python
def __init__(self):
    self._dialog = None  # Created on first use

def get_dialog(self):
    if self._dialog is None:
        self._dialog = ComplexDialog()
    return self._dialog
```

---

### 3. Throttle UI Updates

❌ **BAD** (UI freezes):
```python
# Update graph 100 times per second
for data in data_stream:
    curve.setData(data)  # Too frequent!
```

✅ **GOOD** (smooth):
```python
# Queue updates, apply at 10 Hz
self._pending_update = data

# Timer (10 Hz)
def update_ui(self):
    if self._pending_update:
        curve.setData(self._pending_update)
        self._pending_update = None
```

---

### 4. Clean Up Resources

```python
def closeEvent(self, event):
    """Called when window closes."""
    # Stop timers
    self._update_timer.stop()

    # Disconnect signals
    self.hardware_mgr.hardware_connected.disconnect()

    # Close dialogs
    for dialog in self._dialogs.values():
        dialog.close()

    event.accept()
```

---

## Related Documentation

- [Acquisition System](ACQUISITION_SYSTEM.md) - Backend integration with UI
- [Method & Cycle System](METHOD_CYCLE_SYSTEM.md) - Queue widgets and workflow
- [Spark AI Assistant](SPARK_AI_ASSISTANT.md) - Spark Help tab integration

---

**End of UI Architecture Documentation**
