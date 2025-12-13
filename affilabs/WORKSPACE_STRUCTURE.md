# AffiLabs.core Workspace Structure

## 📁 Production Code (What Actually Runs)

### Main Application
- **`main_simplified.py`** - Application entry point and coordinator
  - Creates `Application` class
  - Initializes hardware, data, recording, kinetic managers
  - Creates `EventBus` for centralized signal routing
  - Creates production UI (`AffilabsMainWindow`)

### Production UI
- **`affilabs_core_ui.py`** - Production main window
  - Class: `AffilabsMainWindow` (not "Prototype")
  - Handles main window, graphs, navigation, status bars
  - Uses `AffilabsSidebar` from `sidebar.py`

- **`sidebar.py`** - Production sidebar (3,732 lines)
  - Class: `AffilabsSidebar` (not "Prototype")
  - 6 tabs: Device Status, Graphic Control, Static, Flow, Export, Settings
  - EventBus integrated
  - **TODO**: Extract tab builders to reduce from 3,732 → ~600 lines

### Core Components
- **`core/`**
  - `event_bus.py` - Centralized signal routing (227 lines)
  - `hardware_manager.py` - Hardware communication
  - `data_acquisition_manager.py` - Data collection
  - `recording_manager.py` - Recording control
  - `kinetic_manager.py` - Pump/valve control
  - `calibration_coordinator.py` - Calibration workflows
  - `graph_coordinator.py` - Graph management
  - `cycle_coordinator.py` - Cycle management

### UI Helpers
- **`sections.py`** - CollapsibleSection widget
- **`plot_helpers.py`** - PyQtGraph plotting utilities
- **`diagnostics_dialog.py`** - System diagnostics
- **`ui_adapter.py`** - Clean interface between App and UI
- **`ui_styles.py`** - Consistent styling (Colors, Fonts, Dimensions)

---

## 🗂️ Prototype/Testing Code (Not Production)

### Prototype UIs (Reference Only)
- **`LL_UI_v1_0.py`** - Original prototype UI
  - Contains `MainWindowPrototype` (actual prototype)
  - Contains `SidebarPrototype` (actual prototype)
  - **NOT USED** in production
  - Kept for reference

- **`LL_UI_v1_0_GIT_VERSION.py`** - Git version of prototype
- **`ui_prototype.py`**, **`ui_prototype_rev1.py`** - Early prototypes

### Old/Unused Widgets
- **`widgets/`** directory
  - `mainwindow.py` - Old MainWindow (not used)
  - `sidebar.py` - Refactored modular sidebar (not used in production)
  - `sidebar_modern.py` - Old sidebar version (not used)
  - `tabs/` - Modular tab classes (not used in production)

These were created during refactoring but are **NOT** used by production code.

---

## 📋 Clear Naming Convention

### Production Code (What Runs)
- `AffilabsMainWindow` (in `affilabs_core_ui.py`)
- `AffilabsSidebar` (in `sidebar.py`)
- Both have EventBus integration
- Both are used by `main_simplified.py`

### Prototype Code (Reference Only)
- `MainWindowPrototype` (in `LL_UI_v1_0.py`) ← Actual prototype
- `SidebarPrototype` (in `LL_UI_v1_0.py`) ← Actual prototype
- Kept for design reference, not executed

### Rule
- **Remove "Prototype" from production code**
- **Keep "Prototype" only for actual prototypes**
- **Clear separation**: production in root, old code in `widgets/` or with "Prototype" suffix

---

## 🎯 Current Refactoring Status

### ✅ Completed
1. Extracted coordinators from main_simplified.py
   - CalibrationCoordinator (558 lines)
   - GraphCoordinator (433 lines)
   - CycleCoordinator (271 lines)
   - **Result**: main_simplified.py reduced from 3,576 → 2,386 lines (33%)

2. Created centralized EventBus
   - core/event_bus.py (227 lines)
   - 44+ signals organized by category
   - Debug mode for event tracing
   - Integrated into production chain

3. Renamed production classes
   - `MainWindowPrototype` → `AffilabsMainWindow`
   - `SidebarPrototype` → `AffilabsSidebar`
   - Clear separation from actual prototypes

### 🔄 In Progress
4. Extract sidebar tab builders
   - Device Status: ~246 lines → `sidebar_tabs/device_status_builder.py`
   - Graphic Control: ~521 lines → `sidebar_tabs/graphic_control_builder.py`
   - Static: ~654 lines → `sidebar_tabs/static_builder.py`
   - Flow: ~607 lines → `sidebar_tabs/flow_builder.py`
   - Export: ~442 lines → `sidebar_tabs/export_builder.py`
   - Settings: ~1,091 lines → `sidebar_tabs/settings_builder.py`
   - **Goal**: Reduce sidebar.py from 3,732 → ~600 lines

---

## 📝 Quick Reference

### To Run Production App
```bash
cd "Affilabs.core beta"
python main_simplified.py
```

### Production UI Chain
```
main_simplified.py
  └─ Application.__init__()
      ├─ EventBus (centralized signals)
      ├─ HardwareManager, DataAcquisitionManager, etc.
      ├─ AffilabsMainWindow (from affilabs_core_ui.py)
      │   └─ AffilabsSidebar (from sidebar.py)
      └─ CalibrationCoordinator, GraphCoordinator, CycleCoordinator
```

### To Find Production Code
- Look for: `Affilabs` prefix (e.g., `AffilabsMainWindow`, `AffilabsSidebar`)
- Look in: Root directory of `Affilabs.core beta/`
- **Avoid**: `widgets/` directory (old code), `LL_UI_v1_0.py` (prototype)

---

*Last Updated: November 23, 2025*
