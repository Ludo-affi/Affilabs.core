# Queue Presets Feature

## Overview
Users can now save and load entire queue sequences as presets. This is different from cycle templates - templates save individual cycle configurations, while presets save complete queue workflows with multiple cycles in order.

## Features Implemented

### 1. Preset Storage (`affilabs/services/queue_preset_storage.py`)
- **TinyDB Backend**: Persistent storage in `queue_presets.json`
- **QueuePreset Model**: Stores complete queue configuration
  - Name, description, cycles list, total duration, cycle count, timestamps
  - `get_summary()` - Returns formatted summary (e.g., "2x Baseline, 3x Concentration")
- **CRUD Operations**:
  - `save_preset(name, cycles, description)` - Save or update preset
  - `load_preset(preset_id)` - Load by ID
  - `delete_preset(preset_id)` - Delete with confirmation
  - `get_all_presets()` - List all (sorted alphabetically)
  - `search_presets(query)` - Filter by name or description
  - `get_preset_count()` - Get total count
- **Import/Export**:
  - `export_preset(preset_id, path)` - Export to JSON file
  - `import_preset(path)` - Import from JSON file

### 2. Preset Browser Dialog (`affilabs/widgets/queue_preset_dialog.py`)
- **Search Bar**: Live filtering by name or description
- **Preset List**: Alphabetically sorted, shows name
- **Preview Pane**: Shows full details:
  - Name and description
  - Cycle count and total duration
  - Summary of cycle types
  - Detailed cycle sequence (type, duration, concentrations)
  - Created/modified timestamps
- **Actions**:
  - Load: Select preset and load into queue (replaces current queue)
  - Delete: Remove preset (with confirmation)
  - Import: Load preset from JSON file
  - Export: Save preset to JSON file
- **Styling**: Matches application design (white, rounded, SF Pro font)

### 3. UI Integration
- **Save Queue Preset Button** (💾): Below queue summary table
  - Checks if queue has cycles
  - Prompts for name and description
  - Saves entire queue to storage
  - Shows success message with cycle count and duration

- **Load Queue Preset Button** (📋): Next to Save button
  - Warns if current queue will be replaced
  - Opens preset browser dialog
  - Loads selected preset into queue
  - Updates UI and backup

## Usage

### Saving a Queue Preset
1. Build a complete queue with multiple cycles
2. Click "💾 Save Queue Preset" button
3. Enter a descriptive name (e.g., "Standard Screening Protocol")
4. Optionally enter a description (e.g., "1 baseline + 5 concentration steps")
5. Click OK
6. Preset is saved to `queue_presets.json`

### Loading a Queue Preset
1. Click "📋 Load Queue Preset" button
2. If queue is not empty, confirm replacement
3. Browse available presets (use search if needed)
4. Click on preset to preview cycle sequence
5. Click "✓ Load Preset" button
6. Queue is cleared and preset cycles are loaded
7. Undo/redo supported via QueuePresenter

### Managing Presets
1. Click "📋 Load Queue Preset" to open browser
2. Select preset to manage
3. Actions available:
   - **Delete**: Remove preset permanently (with confirmation)
   - **Export**: Save preset to JSON file for sharing
   - **Import**: Load preset from JSON file shared by others

## Benefits
- **Workflow Automation**: Save complex experimental protocols once, reuse many times
- **Consistency**: Ensures identical queue setup across multiple runs
- **Collaboration**: Export/import allows sharing protocols between users/labs
- **Time Savings**: No need to rebuild multi-step protocols manually
- **Audit Trail**: Created/modified timestamps for tracking
- **Search & Organization**: Easily find presets by name or description

## Use Cases
1. **Standard Screening**: Save baseline + concentration series
2. **Multi-Analyte Testing**: Save complete ligand panel workflow
3. **Quality Control**: Save calibration/validation protocols
4. **Method Transfer**: Export presets from one system, import on another
5. **Training**: Provide new users with validated protocols

## Technical Details

### Storage Location
- Presets: `queue_presets.json` (TinyDB database)
- Format: JSON array of preset objects with embedded cycle arrays
- Auto-created on first use

### Preset Data Structure
```python
{
    "preset_id": 1,
    "name": "Standard Screening Protocol",
    "description": "1 baseline + 5 concentration steps",
    "cycles": [
        {
            "type": "Baseline",
            "length_minutes": 10.0,
            "note": "Initial baseline",
            "units": "nM",
            "concentrations": {},
            ...
        },
        {
            "type": "Concentration",
            "length_minutes": 5.0,
            "note": "[A:100]",
            "units": "nM",
            "concentrations": {"A": 100.0},
            ...
        },
        ...
    ],
    "total_duration_minutes": 35.0,
    "cycle_count": 6,
    "created_at": "2026-01-31 18:30:00",
    "modified_at": "2026-01-31 18:30:00"
}
```

### Signal Flow

**Save Flow**:
1. `save_preset_btn.clicked` signal
2. `_on_save_preset()` handler
3. Check queue not empty
4. Prompt for name & description (QInputDialog)
5. `preset_storage.save_preset(name, cycles, description)`
6. Write to TinyDB
7. Show success message with summary

**Load Flow**:
1. `load_preset_btn.clicked` signal
2. `_on_load_preset()` handler
3. Confirm replacement if queue not empty
4. Show QueuePresetDialog
5. User selects preset
6. `preset_selected` signal
7. `load_queue()` callback:
   - Clear current queue via presenter (undo support)
   - Add all preset cycles via presenter
   - Sync backward compatibility list
   - Update UI and backup
8. Show success message

## Integration with Queue System
- **Undo/Redo Support**: Loading preset clears queue via `QueuePresenter.clear_queue()`, which is undoable
- **Drag & Drop**: Loaded cycles can be reordered via QueueSummaryWidget
- **Backup**: Auto-saves queue backup after loading preset
- **Validation**: All cycles validated through presenter's add_cycle() method

## Differences from Cycle Templates
| Feature | Cycle Templates | Queue Presets |
|---------|----------------|---------------|
| **Scope** | Single cycle configuration | Entire queue sequence |
| **Use Case** | Reuse common cycle types | Reuse complete workflows |
| **Storage** | `cycle_templates.json` | `queue_presets.json` |
| **Load Action** | Populate form (user adds to queue) | Replace entire queue |
| **Undo** | N/A (form only) | Full undo support |
| **Example** | "Standard Baseline 10min" | "Screening Protocol (1 baseline + 5 concentrations)" |

## Future Enhancements (Not Implemented)
- Preset categories/tags for better organization
- Preset versioning (track changes over time)
- Merge presets (append instead of replace)
- Preset scheduling (auto-run at specific times)
- Cloud sync for team sharing
- Preset usage statistics and history

## Files Modified
- `main.py`: Added storage initialization, signal connections, handler methods
- `affilabs/sidebar_tabs/AL_method_builder.py`: Added Save/Load preset buttons

## Files Created
- `affilabs/services/queue_preset_storage.py` (367 lines)
- `affilabs/widgets/queue_preset_dialog.py` (403 lines)
- `queue_presets.json` (auto-created on first save)

## Testing Checklist
- [x] Application starts without errors
- [x] Storage initialized successfully
- [x] Buttons visible in UI
- [ ] Save preset creates entry in database
- [ ] Load preset populates queue correctly
- [ ] Delete removes preset from database
- [ ] Export creates valid JSON file
- [ ] Import loads preset from JSON file
- [ ] Search filters presets correctly
- [ ] Presets persist across app restarts
- [ ] Undo/redo works with preset loading
- [ ] Warning shows when replacing non-empty queue
