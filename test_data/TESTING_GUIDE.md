# Testing Guide for Edits Interface

## Test Data Generated
**File:** `test_data/test_spr_data_20251223_101055.xlsx`

### Data Characteristics:
- **10 cycles** with realistic SPR binding curves
- **4 channels** (A, B, C, D) with distinct wavelengths
- **Concentrations:** 0, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000 nM
- **Cycle types:** Baseline, Association, Dissociation
- **Duration:** 5 minutes per cycle
- **Signal features:**
  - Exponential association curves
  - Exponential dissociation curves
  - Realistic noise and drift
  - Different binding responses (strong/medium/weak)

## Color Scheme (Now Matching Main Window)
- **Channel A:** Black (0, 0, 0)
- **Channel B:** Red (255, 0, 0)
- **Channel C:** Blue (0, 0, 255)
- **Channel D:** Green (0, 170, 0)

## Testing Steps

### 1. Load Data
1. Run the application: `python main.py`
2. Navigate to **Edits** tab
3. Click **"Load Data"** button (top-right)
4. Select: `test_data/test_spr_data_20251223_101055.xlsx`
5. Verify cycle table populates with 10 cycles

### 2. Single Cycle Selection
1. Click on **Cycle 1** in the table
2. Verify graph shows all 4 channels with correct colors
3. Verify baseline cursors appear (green and blue dashed lines)
4. Try dragging the cursors

### 3. Multi-Cycle Selection
1. Hold **Ctrl** and click multiple cycles (e.g., cycles 2, 3, 4)
2. Verify all selected cycles overlay on the graph
3. Verify channel source dropdowns update with cycle numbers
4. Verify cursors disappear (only shown for single selection)

### 4. Channel Source Selection
1. Select multiple cycles (e.g., cycles 5-8)
2. Click **"▶ Advanced Controls"** to expand
3. For each channel dropdown (A, B, C, D):
   - Select different source cycles
   - Verify the graph updates to show the selected combination

### 5. Create Segment
1. Select cycles you want to blend (e.g., cycles 2, 4, 6)
2. Use channel sources to create your desired combination
3. Click **"Create Segment"** button
4. Enter a name (e.g., "Multi-Cycle Blend Test")
5. Verify segment appears in the "📊 Saved segments..." dropdown

### 6. Reference Graphs
1. Select a cycle in the table (e.g., Cycle 1)
2. **Drag** the cycle row to one of the 3 reference graph panels at the bottom
3. Verify the cycle loads in the mini-graph
4. Repeat for other reference panels
5. Click **"Clear All"** to reset reference graphs

### 7. Editing Controls (Advanced)
1. Expand **"▶ Advanced Controls"**
2. Adjust **Smoothing slider** (1-21, Savitzky-Golay)
   - Watch the graph smooth in real-time
3. Adjust **Baseline Offset slider** (-10 to +10 nm)
   - Watch the graph shift vertically

### 8. Export Segment
1. Select a saved segment from the dropdown
2. Click the **"⋯"** menu button
3. Choose **"Export to TraceDrawer CSV"**
   - Select save location
   - Verify CSV file contains time and channel data
4. Choose **"Export to JSON"**
   - Verify JSON contains metadata and channel arrays

### 9. Delete Segment
1. Select a segment from the dropdown
2. Click **"⋯"** menu → **"Delete segment"**
3. Confirm deletion
4. Verify segment removed from dropdown

## Expected Results

### Visual Verification
- ✅ All 4 channels display with correct colors (Black/Red/Blue/Green)
- ✅ Primary graph shows clear overlay of selected cycles
- ✅ Reference graphs show mini-previews with same color scheme
- ✅ Baseline cursors (green/blue) appear only for single selection
- ✅ Advanced controls are hidden by default

### Functional Verification
- ✅ Multi-cycle selection overlays all cycles
- ✅ Channel source selection creates custom blends
- ✅ Segment creation saves the configuration
- ✅ Export generates valid CSV/JSON files
- ✅ Drag-to-reference works smoothly
- ✅ Smoothing slider updates graph in real-time
- ✅ UI is less cluttered with collapsible sections

## Known Limitations
- Drag-and-drop to reference graphs (framework ready, may need drag handler)
- Smoothing and baseline offset are visual only (not saved to segments yet)

## Troubleshooting

### "No Valid Cycles" Warning
- Ensure the Excel file has both "Raw Data" and "Cycles" sheets
- Check that cycles have `start_time_sensorgram` or `sensorgram_time` fields
- Verify timestamps are numeric (seconds from start)

### Cycles Not Displaying
- Ensure raw data has `elapsed` or `time` field
- Check that `wavelength_a`, `wavelength_b`, `wavelength_c`, `wavelength_d` columns exist
- Verify data covers the cycle time ranges

### Colors Look Wrong
- The colors now match the main Sensorgram window
- Channel A: Pure black (not gray)
- Channel B: Pure red (not orange-red)
- Channel C: Pure blue (not sky blue)
- Channel D: Forest green (RGB: 0, 170, 0)
