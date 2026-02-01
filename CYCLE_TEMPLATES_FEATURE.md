# Cycle Templates Feature

## Overview
Users can now save and reuse common cycle configurations as templates. This saves time and ensures consistency when creating repetitive cycle types.

## Features Implemented

### 1. Template Storage (`affilabs/services/cycle_template_storage.py`)
- **TinyDB Backend**: Persistent storage in `cycle_templates.json`
- **CycleTemplate Model**: Stores all cycle configuration
  - Name, type, duration, concentrations, notes, timestamps
- **CRUD Operations**:
  - `save_template(name, cycle)` - Save or update template
  - `load_template(template_id)` - Load by ID
  - `delete_template(template_id)` - Delete with confirmation
  - `get_all_templates()` - List all (sorted alphabetically)
  - `search_templates(query)` - Filter by name/type
  - `get_templates_by_type(cycle_type)` - Filter by type
- **Import/Export**:
  - `export_template(template_id, path)` - Export to JSON file
  - `import_template(path)` - Import from JSON file

### 2. Template Browser Dialog (`affilabs/widgets/cycle_template_dialog.py`)
- **Search Bar**: Live filtering by name or type
- **Template List**: Alphabetically sorted, shows name and type
- **Preview Pane**: Shows full details:
  - Cycle type and duration
  - Concentration channels
  - Notes
  - Created/modified timestamps
- **Actions**:
  - Load: Select template and populate form
  - Delete: Remove template (with confirmation)
  - Import: Load template from JSON file
  - Export: Save template to JSON file
- **Styling**: Matches application design (white, rounded, SF Pro font)

### 3. UI Integration
- **Save Template Button** (💾): Below "Add to Queue" button
  - Reads current form values
  - Prompts for template name
  - Saves to storage
  - Shows success message

- **Load Template Button** (📋): Next to Save button
  - Opens template browser dialog
  - Populates form with selected template
  - Logs template loaded

## Usage

### Saving a Template
1. Configure cycle in the cycle builder form (type, duration, notes, concentrations)
2. Click "💾 Save as Template" button
3. Enter a descriptive name (e.g., "Standard Baseline 10min")
4. Click OK
5. Template is saved to `cycle_templates.json`

### Loading a Template
1. Click "📋 Load Template" button
2. Browse available templates (use search if needed)
3. Click on template to preview details
4. Click "Load" button
5. Form is populated with template values
6. Modify as needed and add to queue

### Managing Templates
1. Click "📋 Load Template" to open browser
2. Select template to manage
3. Actions available:
   - **Delete**: Remove template permanently (with confirmation)
   - **Export**: Save template to JSON file for sharing
   - **Import**: Load template from JSON file shared by others

## Benefits
- **Time Savings**: No need to re-enter common configurations
- **Consistency**: Ensures identical parameters across experiments
- **Sharing**: Export/import allows sharing templates between users
- **Organization**: Search and filter large template libraries
- **Audit Trail**: Created/modified timestamps for tracking

## Technical Details

### Storage Location
- Templates: `cycle_templates.json` (TinyDB database)
- Format: JSON array of template objects
- Auto-created on first use

### Template Data Structure
```python
{
    "template_id": 1,
    "name": "Standard Baseline 10min",
    "cycle_type": "Baseline",
    "length_minutes": 10.0,
    "note": "Standard baseline scan",
    "units": "nM",
    "concentrations": {"A": 100.0, "B": 50.0},
    "created_at": "2026-01-31 17:30:00",
    "modified_at": "2026-01-31 17:30:00"
}
```

### Signal Flow
```
Button Click → Handler Method → Dialog/Storage → Form/Database
```

**Save Flow**:
1. `save_template_btn.clicked` signal
2. `_on_save_template()` handler
3. Read form values → Create Cycle
4. Prompt for name (QInputDialog)
5. `template_storage.save_template()`
6. Write to TinyDB
7. Show success message

**Load Flow**:
1. `load_template_btn.clicked` signal
2. `_on_load_template()` handler
3. Show CycleTemplateDialog
4. User selects template
5. `template_selected` signal
6. `populate_form()` callback
7. Update all form widgets

## Future Enhancements (Not Implemented)
- Template categories/tags for better organization
- Template versioning (track changes over time)
- Duplicate template detection
- Batch operations (delete multiple, export all)
- Template usage statistics
- Cloud sync for team sharing

## Files Modified
- `main.py`: Added storage initialization, signal connections, handler methods
- `affilabs/sidebar_tabs/AL_method_builder.py`: Added Save/Load buttons

## Files Created
- `affilabs/services/cycle_template_storage.py` (383 lines)
- `affilabs/widgets/cycle_template_dialog.py` (445 lines)
- `cycle_templates.json` (auto-created on first save)

## Testing Checklist
- [x] Application starts without errors
- [x] Storage initialized successfully
- [x] Buttons visible in UI
- [ ] Save template creates entry in database
- [ ] Load template populates form correctly
- [ ] Delete removes template from database
- [ ] Export creates valid JSON file
- [ ] Import loads template from JSON file
- [ ] Search filters templates correctly
- [ ] Templates persist across app restarts
