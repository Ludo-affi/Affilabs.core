# Method Manager Feature

## Overview
The Method Manager allows you to save and load cycle queue sequences as reusable methods. This is perfect for standardized protocols that you run repeatedly.

## Features

### 📁 Methods Button
- Located in the Method (Assay Builder) tab
- Next to "View All Cycles" button
- Opens the Method Manager dialog

### Method Manager Dialog

#### Save Current Queue
1. Build your cycle sequence using the Method tab
2. Click "📁 Methods" button
3. Click "💾 Save Current Queue"
4. Enter method name (e.g., "Standard Kinetics")
5. Optionally add description
6. Method is saved with:
   - Your username (from profile)
   - Creation timestamp
   - All cycle details

#### Load Saved Method
1. Click "📁 Methods" button
2. Select a method from the list
3. Preview shows:
   - Method name and description
   - Author and creation date
   - List of all cycles with durations
4. Double-click or click "📥 Load Method"
5. Confirms if queue is not empty
6. Loads cycles into queue

#### Delete Method
1. Select a method
2. Click "🗑 Delete"
3. Confirm deletion

## Storage

### Location
Methods are stored in: `methods/` directory

### File Format
- JSON files with `.json` extension
- Filename: sanitized method name
- Contains:
  - Method metadata (name, description, author, creation time)
  - All cycle data (type, duration, notes, concentrations)

### Example Method File
```json
{
  "name": "Standard Kinetics",
  "description": "3-concentration kinetics with baseline",
  "author": "John Doe",
  "created": 1738368000.0,
  "cycle_count": 5,
  "cycles": [
    {
      "type": "Baseline",
      "length_minutes": 5.0,
      "name": "",
      "note": "Initial baseline"
    },
    {
      "type": "Association",
      "length_minutes": 15.0,
      "concentration_value": 100.0,
      "concentration_units": "nM"
    }
  ]
}
```

## Use Cases

### Standard Protocols
Save your most common experimental protocols:
- "Daily Baseline Check"
- "Kinetics 3-Point"
- "Regeneration Cycle"

### Team Sharing
- Share method files with colleagues
- Ensure consistent protocols across team
- Copy `.json` files to share via email/network

### Batch Experiments
- Load method
- Run experiment
- Repeat with different samples

## Tips

- Use descriptive method names
- Add descriptions for complex protocols
- Review preview before loading
- Methods preserve all cycle details (durations, notes, concentrations)
- User profile automatically captured when saving

## Technical Details

### Architecture
- **MethodManager**: Service class handling file I/O
- **MethodManagerDialog**: PySide6 dialog UI
- **Cycle.to_dict/from_dict**: Serialization methods
- **Storage**: JSON files in `methods/` folder

### Files
- `affilabs/services/method_manager.py` - Backend logic
- `affilabs/widgets/method_manager_dialog.py` - Dialog UI
- `affilabs/domain/cycle.py` - Cycle serialization
- `affilabs/sidebar_tabs/AL_method_builder.py` - Button integration
