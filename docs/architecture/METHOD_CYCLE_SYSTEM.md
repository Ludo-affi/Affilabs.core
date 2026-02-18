# Method & Cycle System Documentation

## Overview

The Method & Cycle System is the core workflow engine for designing and executing SPR (Surface Plasmon Resonance) experiments in Affilabs.core. It enables users to build multi-step experimental protocols through an intuitive interface with AI assistance, queue management, and preset storage.

**Key Features:**
- **Cycle-based workflow**: Experiments composed of discrete time-bound cycles
- **Spark AI integration**: Natural language method generation (@spark commands)
- **Queue management**: Visual queue with drag-drop reordering, execution control
- **Preset system**: Save and reuse common methods (@preset, !save)
- **Multi-channel support**: Per-channel concentration control ([A:10nM], [B:50nM])
- **Real-time validation**: Intelligence Bar shows method status and suggestions
- **Template library**: Pre-built methods for kinetics, titration, screening

---

## System Architecture

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    UI LAYER                              │
│  • Method Tab Sidebar (AL_method_builder.py)            │
│  • Method Builder Dialog (method_builder_dialog.py)     │
│  • Queue Summary Widget (queue_summary_widget.py)       │
│  • Intelligence Bar (real-time status)                  │
└─────────────────────────────────────────────────────────┘
                           ↕
┌─────────────────────────────────────────────────────────┐
│                  DOMAIN LAYER                            │
│  • Cycle (Pydantic model with validation)               │
│  • QueueManager (state management & operations)         │
│  • QueuePresenter (MVP coordination)                    │
└─────────────────────────────────────────────────────────┘
                           ↕
┌─────────────────────────────────────────────────────────┐
│                 SERVICES LAYER                           │
│  • MethodTemplates (predefined templates)               │
│  • MethodStorage (persistence)                          │
│  • QueuePresetStorage (saved presets)                   │
│  • CycleTemplateStorage (reusable cycles)               │
└─────────────────────────────────────────────────────────┘
```

---

## Cycle Domain Model

### Cycle Class (Pydantic-based)

**File:** `affilabs/domain/cycle.py` (233 lines)

The `Cycle` class is a Pydantic-validated domain model representing a single experimental phase.

#### Core Fields

```python
class Cycle:
    # Identity
    cycle_id: int                      # Unique permanent ID (assigned by QueueManager)
    cycle_num: int                     # Sequential display number (1, 2, 3...)

    # Type & Configuration
    type: str                          # Baseline, Association, Dissociation, Regeneration, Custom
    length_minutes: float              # Duration in minutes (must be positive)
    name: str                          # Display name (e.g., "Baseline 1", "Concentration 5")
    note: str = ""                     # User annotation/comments

    # Concentration (single-channel legacy)
    concentration_value: Optional[float] = None
    concentration_units: str = "nM"

    # Multi-channel concentration
    concentrations: Dict[str, float] = {}  # {"a": 100.0, "b": 50.0}

    # Status & Timeline
    status: str = "pending"           # pending, running, completed, cancelled
    sensorgram_time: float = 0.0      # Start time in sensorgram (seconds)

    # SPR Data (post-execution)
    delta_spr_by_channel: Dict[str, float] = {}  # {"a": 145.2, "b": 87.3}
    delta_spr: Optional[float] = None  # Legacy single-channel value
```

#### Validation Rules

1. **Positive Length**: `length_minutes` must be > 0
2. **Type Coercion**: All fields automatically coerced to correct type
3. **Default Name**: Auto-generated if not provided (e.g., "Baseline 1")

#### Methods

```python
# Lifecycle
cycle.start()                    # Mark as running
cycle.complete()                 # Mark as completed
cycle.is_running() -> bool       # Check if currently running

# Serialization
cycle.to_dict() -> dict          # Full state (includes internal fields)
cycle.to_export_dict() -> dict   # Export-safe (excludes internal IDs)
cycle.from_dict(data) -> Cycle   # Deserialize from dict

# Display
str(cycle)                       # Human-readable representation
```

#### Cycle Types

| Type | Description | Typical Duration | Use Case |
|------|-------------|------------------|----------|
| **Baseline** | Buffer flow, no analyte | 2-10 min | Stabilization, dissociation phase |
| **Association** | Analyte injection (binding phase) | 2-5 min | Binding kinetics measurement |
| **Dissociation** | Buffer flow after association | 5-15 min | Off-rate measurement |
| **Regeneration** | Regeneration solution flow | 30 sec - 2 min | Surface cleaning between cycles |
| **Custom** | User-defined purpose | Variable | Special protocols (activation, blocking) |

#### Example Usage

```python
from affilabs.domain.cycle import Cycle

# Create baseline cycle
baseline = Cycle(
    type="Baseline",
    length_minutes=5.0,
    name="Initial Baseline",
    note="Stabilization before titration"
)

# Create multi-channel binding cycle
assoc = Cycle(
    type="Association",
    length_minutes=3.0,
    name="Concentration 1",
    concentrations={"a": 100.0, "b": 50.0},  # Channel A: 100nM, Channel B: 50nM
    concentration_units="nM"
)

# Lifecycle
assoc.start()          # status = "running"
assoc.complete()       # status = "completed"
```

---

## Queue Manager

### QueueManager Class

**File:** `affilabs/managers/queue_manager.py` (439 lines)

Centralized state management for the cycle queue with signal-based notifications.

#### Key Responsibilities

1. **State Management**: Single source of truth for queue state
2. **ID Assignment**: Automatic unique ID generation for cycles
3. **Renumbering**: Sequential `cycle_num` for display (1, 2, 3...)
4. **Queue Locking**: Prevent modifications during execution
5. **Signal Emission**: Notify listeners of state changes

#### Core Operations

```python
queue_mgr = QueueManager()

# Add cycles
queue_mgr.add_cycle(cycle)                    # Returns True if successful
queue_mgr.add_cycle(cycle)                    # Returns False if locked

# Delete cycles
deleted = queue_mgr.delete_cycle(index=2)     # Returns deleted Cycle
deleted_list = queue_mgr.delete_cycles([0, 2, 5])  # Batch delete

# Reorder cycles
queue_mgr.reorder_cycle(from_idx=0, to_idx=3) # Move cycle

# Queue access
cycles = queue_mgr.get_queue_snapshot()       # Immutable copy
next_cycle = queue_mgr.peek_next_cycle()      # Get next without removing
size = queue_mgr.get_queue_size()             # Current count

# Execution flow
next_cycle = queue_mgr.pop_next_cycle()       # Remove & return first cycle
queue_mgr.mark_completed(cycle)               # Add to completed history

# Queue control
queue_mgr.lock()                              # Prevent modifications
queue_mgr.unlock()                            # Allow modifications
queue_mgr.clear_queue()                       # Remove all cycles
```

#### Signals

```python
# Connect to signals
queue_mgr.queue_changed.connect(update_ui)
queue_mgr.cycle_added.connect(on_cycle_added)
queue_mgr.cycle_deleted.connect(on_cycle_deleted)
queue_mgr.cycle_reordered.connect(on_reorder)
queue_mgr.queue_locked.connect(gray_out_ui)
queue_mgr.queue_unlocked.connect(enable_ui)
```

#### ID Management

- **Permanent ID** (`cycle_id`): Unique across session, never reused
- **Display Number** (`cycle_num`): Sequential 1, 2, 3... (renumbered on changes)

Example:
```
Add 3 cycles:      cycle_id: [1, 2, 3]    cycle_num: [1, 2, 3]
Delete cycle 2:    cycle_id: [1, 3]       cycle_num: [1, 2]  ← Renumbered!
Add new cycle:     cycle_id: [1, 3, 4]    cycle_num: [1, 2, 3]
```

---

## Method Builder UI

### Method Tab Sidebar

**File:** `affilabs/sidebar_tabs/AL_method_builder.py` (561 lines)

The sidebar tab in the main application window for queue management.

#### Components

1. **Intelligence Bar**
   - Real-time status display
   - Shows validation messages (✓ Good, ⚠ Warning, ✗ Error)
   - Guidance text (e.g., "→ Ready for injection")

2. **Build Method Button**
   - Opens popup dialog for cycle creation
   - Keyboard shortcut: `Ctrl+M`

3. **Queue Summary Section**
   - Collapsible section with queue table
   - Columns: #, Type, Name, Duration, Status
   - Drag-drop reordering support
   - Right-click context menu (edit, delete, duplicate)

4. **Syntax Highlighting**
   - Channel tags: `[A:10]`, `[B:50]`, `[ALL:20]`
   - Concentration tags highlighted in green
   - Plain channel tags in dark color

#### Example

```
╔════════════════════════════════════════════════════╗
║ METHOD BUILDER                                     ║
╟────────────────────────────────────────────────────╢
║ ✓ Good - Method ready for execution               ║ ← Intelligence Bar
╟────────────────────────────────────────────────────╢
║ [Build Method] Button                              ║
╟────────────────────────────────────────────────────╢
║ ▼ Cycle Queue (5 cycles)                           ║
║ ┌──┬──────────┬──────────────┬─────────┬─────────┐ ║
║ │# │Type      │Name          │Duration │Status   │ ║
║ ├──┼──────────┼──────────────┼─────────┼─────────┤ ║
║ │1 │Baseline  │Initial       │5 min    │pending  │ ║
║ │2 │Assoc     │Conc 100nM    │3 min    │pending  │ ║
║ │3 │Dissoc    │Dissoc 1      │10 min   │pending  │ ║
║ │4 │Regen     │Regen 1       │1 min    │pending  │ ║
║ │5 │Baseline  │Final         │2 min    │pending  │ ║
║ └──┴──────────┴──────────────┴─────────┴─────────┘ ║
╚════════════════════════════════════════════════════╝
```

---

### Method Builder Dialog

**File:** `affilabs/widgets/method_builder_dialog.py` (1034 lines)

Modal popup dialog for building cycle sequences with Spark AI integration.

#### Features

1. **NotesTextEdit Input**
   - Multi-line text editor
   - Up/Down arrow navigation (command history)
   - Syntax highlighting for channel tags

2. **Spark AI Integration**
   - Trigger: `@spark <question>` or click Spark button
   - Pattern matching for common questions
   - Multi-turn conversations (ask → answer → generate)

3. **Preset System**
   - Search: `@<preset_name>` (e.g., `@kinetics`)
   - Save: `!save my_preset` after building method
   - Auto-complete suggestions

4. **Cycle Parsing**
   - Natural language syntax: `Baseline 5min [ALL]`
   - Multi-line methods (one cycle per line)
   - Comment support: `# This is a comment`

#### Spark AI Patterns

| Question Pattern | Example | Generated Output |
|-----------------|---------|------------------|
| Titration | `@spark how do I run a titration?` | Baseline + multiple Binding cycles |
| Kinetics | `@spark show me kinetics` | Kinetic + Dissociation + Regeneration |
| Amine coupling | `@spark build amine coupling` | Asks "How many binding cycles?" → Full protocol |
| Regeneration | `@spark how do I regenerate?` | Regeneration cycle |
| Full cycle | `@spark complete cycle?` | Baseline + Binding + Regeneration |

#### Multi-Turn Conversation Example

```
User:   @spark build amine coupling
Spark:  ⚡ How many concentrations? (e.g., type '5' and press Enter)

User:   5
Spark:  ⚡ Spark suggestion! Edit as needed.

        Baseline 30sec [ALL]
        Other 4min  # Activation
        Other 30sec  # Wash
        Immobilization 4min [A]
        Other 30sec  # Wash
        Other 4min  # Blocking
        Other 30sec  # Wash
        Baseline 15min [ALL]

        # Concentration series
        Concentration 15min [A]  # Concentration 1
        Regeneration 2min [ALL]
        Baseline 2min [ALL]
        Concentration 15min [A]  # Concentration 2
        Regeneration 2min [ALL]
        Baseline 2min [ALL]
        ... (3 more cycles)
```

#### Cycle Syntax

```
<Type> <Duration> [<Channels>] [<Note>]

Examples:
Baseline 5min [ALL]
Concentration 2min [A:100nM]
Concentration 3min [A:100nM] [B:50nM]  # Multi-channel
Dissociation 10min [ALL]
Regeneration 30sec [ALL:50mM]
Custom 5min [A]  # Special protocol
```

**Channel Tags:**
- `[A]` - Channel A only
- `[A:100]` - Channel A with 100nM concentration
- `[A:100nM] [B:50µM]` - Multi-channel with concentrations
- `[ALL]` - All channels (A, B, C, D)
- `[ALL:50mM]` - All channels with 50mM concentration

---

## Queue Summary Widget

**File:** `affilabs/widgets/queue_summary_widget.py`

Visual representation of the cycle queue with interactive controls.

#### Features

1. **Table Display**
   - Columns: #, Type, Name, Duration, Status
   - Type column: ResizeToContents (fits longest type name)
   - Color-coded status (pending: gray, running: blue, completed: green)

2. **Drag-Drop Reordering**
   - Click and drag rows to reorder
   - Visual feedback during drag
   - Automatically renumbers cycles

3. **Context Menu**
   - Edit cycle
   - Delete cycle
   - Duplicate cycle
   - Insert baseline before/after

4. **Queue Controls**
   - Start Run button
   - Pause button
   - Clear Queue button
   - Skip Current Cycle button

5. **Execution State**
   - Queue locks during execution (grayed out)
   - Current cycle highlighted
   - Progress bar shows % complete

---

## Cycle Execution Flow

### Execution Lifecycle

```
┌─────────────────────────────────────────────────────────┐
│ 1. USER BUILDS METHOD (Method Builder Dialog)          │
│    • Type cycles in natural language                    │
│    • Use @spark for AI assistance                       │
│    • Preview in dialog before adding to queue           │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ 2. ADD TO QUEUE (QueueManager)                          │
│    • Assign unique cycle_id                             │
│    • Set cycle_num for display                          │
│    • Set status = "pending"                             │
│    • Emit queue_changed signal                          │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ 3. START RUN (Application)                              │
│    • Lock queue (prevent modifications)                 │
│    • Pop first cycle from queue                         │
│    • Set cycle status = "running"                       │
│    • Configure pump controllers                         │
│    • Start data acquisition                             │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ 4. CYCLE EXECUTION (CycleCoordinator)                   │
│    • Monitor elapsed time                               │
│    • Update progress bar                                │
│    • Collect SPR data                                   │
│    • Detect cycle boundaries (start/stop cursors)       │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ 5. CYCLE COMPLETION                                     │
│    • Set cycle status = "completed"                     │
│    • Store delta_spr_by_channel                         │
│    • Mark as completed in QueueManager                  │
│    • Autosave cycle data to CSV                         │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ 6. NEXT CYCLE OR FINISH                                 │
│    • If queue not empty: goto step 3                    │
│    • If queue empty: unlock queue, show summary         │
└─────────────────────────────────────────────────────────┘
```

### CycleCoordinator

**File:** `affilabs/core/cycle_coordinator.py` (300 lines)

Manages cycle tracking, extraction, and autosave operations.

#### Responsibilities

1. **Boundary Detection**: Track cycle start/stop cursor positions
2. **Autosave**: Save cycle data to CSV when boundaries change
3. **Flagging System**: Mark interesting regions with annotations
4. **Data Extraction**: Extract time-series data for each cycle

#### Methods

```python
coordinator = CycleCoordinator(app)

# Cycle tracking
changed = coordinator.check_cycle_changed(start_time, stop_time)
coordinator.autosave_cycle_data(start_time, stop_time)
bounds = coordinator.get_cycle_bounds()  # Returns (start, stop) or None
coordinator.reset_cycle_tracking()

# Flagging
coordinator.add_flag(channel=0, time=45.2, annotation="Peak here")
flags = coordinator.get_flags_for_channel(channel=0)
coordinator.export_flags_to_csv(filename)
coordinator.clear_flags()
```

---

## Preset System

### Saving Presets

```python
# In Method Builder Dialog:
# 1. Build your method
Baseline 5min [ALL]
Concentration 2min [A:100nM]
Dissociation 10min [ALL]
Regeneration 30sec [ALL:50mM]

# 2. Save with command
!save my_kinetics_preset

# Saved to: queue_presets.json
```

### Loading Presets

```python
# Search for preset
@my_kinetics_preset

# Or use auto-complete
@kin<TAB>  # Shows matching presets
```

### QueuePresetStorage

**File:** `affilabs/services/queue_preset_storage.py`

Persistent storage for reusable cycle sequences.

```python
from affilabs.services.queue_preset_storage import QueuePresetStorage

storage = QueuePresetStorage()

# Save cycles as preset
storage.save_preset("titration_5pt", cycles=[
    Cycle(type="Baseline", length_minutes=5),
    Cycle(type="Association", length_minutes=2, concentration_value=10),
    # ... more cycles
])

# Load preset
cycles = storage.load_preset("titration_5pt")

# List all presets
names = storage.list_presets()  # Returns ["titration_5pt", "kinetics_standard", ...]

# Delete preset
storage.delete_preset("old_preset")
```

---

## Method Templates

### MethodTemplates Service

**File:** `affilabs/services/method_templates.py` (441 lines)

Pre-built method templates for common SPR workflows (Pro/Enterprise tier feature).

#### Available Templates

| Template ID | Name | Description | Tier |
|------------|------|-------------|------|
| `kinetics_analysis` | Kinetics Analysis | Multi-concentration kinetics with baseline/regeneration | Pro |
| `affinity_screening` | Affinity Screening | High-throughput concentration series | Pro |
| `single_cycle_kinetics` | Single-Cycle Kinetics | Rapid kinetics with sequential injections | Pro |
| `regeneration_screening` | Regeneration Screening | Test different regeneration conditions | Pro |
| `binding_analysis` | Binding Analysis | Simple association/dissociation analysis | Free |

#### Usage

```python
from affilabs.services.method_templates import MethodTemplates

templates = MethodTemplates()

# Get available templates
template_list = templates.get_templates_list()
# Returns: [{'id': 'kinetics_analysis', 'name': 'Kinetics Analysis', ...}, ...]

# Apply template
cycles = templates.apply_template(
    template_id="kinetics_analysis",
    concentrations=[100, 50, 25, 12.5, 6.25],
    baseline_minutes=5.0,
    association_minutes=3.0,
    dissociation_minutes=5.0,
    regeneration_minutes=1.0,
    concentration_units="nM"
)

# Returns list of Cycle objects ready to add to queue
```

#### Kinetics Analysis Template Example

```python
cycles = templates.apply_template(
    "kinetics_analysis",
    concentrations=[100, 50, 25],
    baseline_minutes=5,
    association_minutes=3,
    dissociation_minutes=5,
    regeneration_minutes=1
)

# Generates:
# 1. Baseline 5min - Initial Baseline
# 2. Association 3min [100nM] - Association 1
# 3. Dissociation 5min - Dissociation 1
# 4. Regeneration 1min - Regeneration 1
# 5. Baseline 2.5min - Baseline 2
# 6. Association 3min [50nM] - Association 2
# 7. Dissociation 5min - Dissociation 2
# 8. Regeneration 1min - Regeneration 2
# 9. Baseline 2.5min - Baseline 3
# 10. Association 3min [25nM] - Association 3
# 11. Dissociation 5min - Dissociation 3
# 12. Regeneration 1min - Regeneration 3
# 13. Baseline 5min - Final Baseline
```

---

## Best Practices

### Method Design

1. **Always Start with Baseline**
   - 2-10 minutes for instrument stabilization
   - Establishes zero reference for binding

2. **Include Regeneration Cycles**
   - After each binding cycle
   - Prevents surface saturation
   - Typical: 30 sec - 2 min with 50mM NaOH or glycine-HCl

3. **Plan Dissociation Phases**
   - 5-15 minutes for off-rate measurement
   - Use Dissociation type OR extend Baseline

4. **Use Multi-Channel Wisely**
   - Reference channel: buffer only
   - Active channels: different concentrations
   - Example: `[A:100nM] [B:50nM] [C:0]` (C is reference)

5. **Add Notes for Clarity**
   - Document unusual parameters
   - Note sample IDs or buffer compositions
   - Example: `Concentration 5min [A:100nM]  # Sample: mAb-542`

### Channel Tagging

```
# Single channel
Concentration 2min [A:100nM]

# Multi-channel (different concentrations)
Concentration 2min [A:100nM] [B:50nM] [C:0]  # C is reference

# All channels (same concentration)
Baseline 5min [ALL]
Regeneration 30sec [ALL:50mM]

# Multiple tags (concentration + buffer info)
Regeneration 1min [ALL:50mM]  # Glycine-HCl pH 2.5
```

### Queue Organization

1. **Group by Experiment**
   - Use clear naming: "Titration 1", "Kinetics Screen"
   - Add blank cycles (0 duration) as separators with notes

2. **Save Common Methods**
   - Build once, reuse with `!save` command
   - Example: `!save standard_kinetics`

3. **Use Templates for Standardization**
   - Ensures consistency across experiments
   - Reduces setup errors

4. **Preview Before Running**
   - Check total duration
   - Verify concentration series
   - Ensure regeneration between cycles

---

## Troubleshooting

### Common Issues

#### Queue Won't Accept Cycles

**Problem:** Cannot add cycles to queue

**Solutions:**
1. Check if queue is locked (during execution)
2. Wait for current run to complete OR pause run
3. Verify cycle has valid `length_minutes` (> 0)

#### Cycle Parsing Failed

**Problem:** Text doesn't convert to cycles

**Solutions:**
1. Check syntax: `<Type> <Duration> [<Channels>]`
2. Valid types: Baseline, Binding, Kinetic, Regeneration, Immobilization, Custom
3. Valid durations: `5min`, `30sec`, `2.5min`
4. Valid channels: `[A]`, `[A:100nM]`, `[ALL]`

#### Spark Doesn't Understand Question

**Problem:** @spark returns "I didn't understand"

**Solutions:**
1. Try simpler keywords: "titration", "kinetics", "regeneration"
2. Use pattern matching: "@spark how do I..." questions
3. Check for saved presets: `@preset_name`
4. Use template library for complex methods

#### Cycles Execute Out of Order

**Problem:** Queue doesn't execute in expected sequence

**Solutions:**
1. Check `cycle_num` in queue summary (should be 1, 2, 3...)
2. Use drag-drop to reorder before starting run
3. Verify no duplicate `cycle_id` values (QueueManager should prevent this)

#### Autosave Not Working

**Problem:** Cycle data not saved to CSV

**Solutions:**
1. Check that `DATA_DIR/cycles` directory exists
2. Verify at least 10 data points collected
3. Check cycle boundaries changed significantly (>5% duration)
4. Look for error messages in console

---

## API Reference

### Cycle

```python
from affilabs.domain.cycle import Cycle

# Constructor
cycle = Cycle(
    type: str,                          # Required: Baseline, Association, etc.
    length_minutes: float,              # Required: Duration in minutes
    name: str = "",                     # Optional: Auto-generated if empty
    note: str = "",                     # Optional: User annotation
    concentration_value: float = None,  # Optional: Legacy single-channel
    concentration_units: str = "nM",    # Optional: Units for concentration
    concentrations: dict = {},          # Optional: Multi-channel {channel: value}
    status: str = "pending",            # Optional: pending, running, completed
)

# Methods
cycle.start() -> None                   # Mark as running
cycle.complete() -> None                # Mark as completed
cycle.is_running() -> bool              # Check if running
cycle.to_dict() -> dict                 # Serialize to dict
cycle.to_export_dict() -> dict          # Export-safe serialization
Cycle.from_dict(data: dict) -> Cycle    # Deserialize from dict
```

### QueueManager

```python
from affilabs.managers.queue_manager import QueueManager

# Constructor
mgr = QueueManager()

# Operations
mgr.add_cycle(cycle: Cycle) -> bool
mgr.delete_cycle(index: int) -> Optional[Cycle]
mgr.delete_cycles(indices: List[int]) -> List[Cycle]
mgr.reorder_cycle(from_idx: int, to_idx: int) -> bool
mgr.clear_queue() -> int
mgr.pop_next_cycle() -> Optional[Cycle]

# Access
mgr.get_queue_snapshot() -> List[Cycle]
mgr.get_cycle_at(index: int) -> Optional[Cycle]
mgr.peek_next_cycle() -> Optional[Cycle]
mgr.get_queue_size() -> int
mgr.get_completed_count() -> int
mgr.get_completed_cycles() -> List[Cycle]

# State
mgr.lock() -> None
mgr.unlock() -> None
mgr.is_locked() -> bool
mgr.mark_completed(cycle: Cycle) -> None
mgr.clear_completed() -> int

# Signals
mgr.queue_changed.connect(callback)
mgr.cycle_added.connect(callback)        # callback(cycle)
mgr.cycle_deleted.connect(callback)      # callback(index, cycle)
mgr.cycle_reordered.connect(callback)    # callback(from_idx, to_idx)
mgr.queue_locked.connect(callback)
mgr.queue_unlocked.connect(callback)
```

### MethodTemplates

```python
from affilabs.services.method_templates import MethodTemplates

# Constructor
templates = MethodTemplates()

# Methods
templates.get_templates_list() -> List[Dict[str, str]]
templates.apply_template(
    template_id: str,
    **params
) -> List[Cycle]

# Template-specific parameters
# kinetics_analysis:
templates.apply_template(
    "kinetics_analysis",
    concentrations=[100, 50, 25],
    baseline_minutes=5.0,
    association_minutes=3.0,
    dissociation_minutes=5.0,
    regeneration_minutes=1.0,
    concentration_units="nM"
)
```

### QueuePresetStorage

```python
from affilabs.services.queue_preset_storage import QueuePresetStorage

# Constructor
storage = QueuePresetStorage()

# Methods
storage.save_preset(name: str, cycles: List[Cycle]) -> bool
storage.load_preset(name: str) -> List[Cycle]
storage.list_presets() -> List[str]
storage.delete_preset(name: str) -> bool
storage.search_presets(query: str) -> List[str]
```

---

## Future Enhancements

### Planned Features

1. **Visual Method Designer**
   - Drag-drop cycle blocks
   - Timeline visualization
   - Gantt chart for queue execution

2. **Method Validation**
   - Pre-flight checks for common errors
   - Concentration range warnings
   - Duration optimization suggestions

3. **Advanced Templates**
   - Epitope binning protocols
   - Sandwich assay workflows
   - Competition binding experiments

4. **Method Sharing**
   - Export methods as JSON
   - Import from collaborators
   - Community template library

5. **Execution Analytics**
   - Estimated completion time
   - Resource usage (sample volume, buffer)
   - Cost estimation

6. **Smart Scheduling**
   - Multi-method queue (run overnight)
   - Auto-restart after errors
   - Email notifications on completion

---

## Related Documentation

- [OPTICAL_CONVERGENCE_ENGINE.md](./OPTICAL_CONVERGENCE_ENGINE.md) - LED convergence and ML training
- [DEVICE_DATABASE_REGISTRATION.md](./DEVICE_DATABASE_REGISTRATION.md) - Device configuration and EEPROM sync
- [SPARK_AI_ASSISTANT.md](./SPARK_AI_ASSISTANT.md) - Spark AI architecture and training
- QUEUE_ARCHITECTURE.md - Detailed queue refactoring (see REFACTORING_COMPLETE_SUMMARY.md)

---

## Glossary

- **Cycle**: A discrete experimental phase with defined duration and purpose
- **Method**: A sequence of cycles forming a complete experimental protocol
- **Queue**: Ordered list of cycles waiting to be executed
- **Baseline**: Buffer-only flow phase for stabilization or dissociation
- **Association**: Analyte injection phase (binding)
- **Dissociation**: Buffer flow after association (off-rate measurement)
- **Regeneration**: Surface cleaning phase (removes bound analyte)
- **Sensorgram**: Time-series plot of SPR signal (RU or response units)
- **Delta SPR**: Change in SPR signal during cycle (binding response)
- **Multi-channel**: Independent flow paths for parallel experiments (A, B, C, D)
- **Preset**: Saved method sequence for reuse
- **Template**: Pre-built method pattern with configurable parameters
- **Channel Tag**: Syntax for specifying channel and concentration (e.g., `[A:100nM]`)

---

**Document Version:** 1.0
**Last Updated:** 2024
**Maintained By:** Affinité Instruments Development Team

