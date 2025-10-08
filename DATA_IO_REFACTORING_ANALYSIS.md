# Data I/O Module - Refactoring Candidate

## What is "Data I/O"?

**Data I/O (Input/Output)** refers to all operations that read from or write to files - essentially how the application saves experimental data, logs, and analysis results to disk, and loads them back.

## Current Data I/O Operations in the Codebase

### 📁 In `main/main.py` (~150 lines)

#### 1. **Recording & Export Operations**
- `save_rec_data()` - Main recording save coordinator (lines 1071-1084)
  - Delegates to sensorgram widget for SPR data
  - Calls `save_temp_log()` for temperature data
  - Calls `save_kinetic_log()` for kinetic logs
  
- `manual_export_raw_data()` - User-triggered manual export (lines 1086-1103)
  - Opens directory picker dialog
  - Exports all current data
  - Shows success notification

#### 2. **Temperature Log Saving** (~30 lines)
- `save_temp_log()` - Temperature data export (lines 1730-1754)
  - Format: Tab-delimited text file
  - Columns: Timestamp, Experiment Time, Device Temp
  - Filename: `{rec_dir} Temperature Log.txt`
  - Uses CSV writer with excel-tab dialect

#### 3. **Kinetic Log Saving** (~120 lines)
- `save_kinetic_log()` - Kinetic system logs (lines 1757-1877)
  - **Two channel files**:
    * `{rec_dir} Kinetic Log Ch A.txt`
    * `{rec_dir} Kinetic Log Ch B.txt` (if dual-channel device)
  - **Version-specific formats**:
    * Version 1.1: Timestamp, Exp Time, Event, Flow, Sensor Temp, Device Temp
    * Other: Timestamp, Exp Time, Event, Flow, Temperature
  - Uses CSV writer with excel-tab dialect
  - Handles both KNX and EZSPR devices

### 📁 In `widgets/datawindow.py` (~400 lines)

#### 1. **Main Data Saving** (~200 lines)
- `save_data()` - Primary SPR data export (lines 1998+)
  - Creates directory structure
  - Saves raw sensorgram data
  - Saves processed data
  - Saves segment metadata

#### 2. **Data Loading** (~100 lines)
- Multiple load methods for:
  - Loading previous experiment data
  - Importing calibration parameters
  - Loading reference signals

#### 3. **Export Formats** (~100 lines)
- **Tab-delimited text files** (`.txt`)
  - Raw wavelength vs time data
  - Processed data with filtering
  - Segment tables
- **CSV files** (`.csv`)
  - Analyzed data tables
  - Summary statistics
- **JSON files** (`.json`)
  - Complete experiment metadata
  - Analysis results

### 📁 In `widgets/analysis.py` (~150 lines)

#### 1. **Analysis Data Loading**
- `load_data()` - Load saved analysis results
- JSON parsing for analysis configurations

#### 2. **Analysis Export**
- Segment tables
- Kinetic parameters (ka, kd, KD)
- Binding curves
- Raw analysis data

## Data File Types Created

### 1. **SPR Data Files**
```
{directory}/
├── Raw Data Ch A.txt         # Raw wavelength data, channel A
├── Raw Data Ch B.txt         # Raw wavelength data, channel B
├── Raw Data Ch C.txt         # Raw wavelength data, channel C
├── Raw Data Ch D.txt         # Raw wavelength data, channel D
├── Processed Data.txt        # Filtered/processed wavelengths
├── Segment Table.txt         # Experiment segments metadata
└── experiment_metadata.json  # Complete configuration
```

### 2. **Temperature Logs**
```
{directory} Temperature Log.txt
Columns: Timestamp | Experiment Time | Device Temp
Format: Tab-delimited text
```

### 3. **Kinetic Logs**
```
{directory} Kinetic Log Ch A.txt
{directory} Kinetic Log Ch B.txt
Columns: Timestamp | Experiment Time | Event Type | Flow Rate | Temperature(s)
Format: Tab-delimited text
```

### 4. **Analysis Files**
```
{directory}/
├── Analysis-Segments-Table.txt      # Analyzed segment data
├── Analysis-Kinetics-Ch{X}.txt      # ka, kd, KD values per channel
├── Analysis-Binding-Curves.txt      # Dose-response curves
└── AnalysisRawData.json             # Complete analysis data
```

## Why Refactor Data I/O?

### Current Issues:

1. **Scattered Logic** (~400+ lines across multiple files)
   - Hard to maintain consistent file formats
   - Duplicate code for similar operations
   - No centralized error handling

2. **Mixed Concerns**
   - UI widgets handling file I/O directly
   - Main app orchestrating saves
   - No separation of data formatting vs file writing

3. **Format Inconsistency**
   - Some files use CSV writer
   - Some use manual formatting
   - Different encoding strategies

4. **No Abstraction**
   - Direct file path manipulation
   - Hardcoded file extensions
   - No data validation before save

### Proposed Refactoring:

Create `utils/data_io_manager.py` with:

```python
class DataIOManager:
    """Centralized data I/O operations."""
    
    # SPR Data
    def save_spr_data(self, directory: str, data: dict, channels: list) -> bool
    def load_spr_data(self, directory: str) -> dict
    
    # Temperature Logs
    def save_temperature_log(self, directory: str, temp_log: dict) -> bool
    def load_temperature_log(self, file_path: str) -> dict
    
    # Kinetic Logs
    def save_kinetic_log(self, directory: str, log_data: dict, channel: str, version: str) -> bool
    def load_kinetic_log(self, file_path: str) -> dict
    
    # Analysis Data
    def save_analysis_results(self, directory: str, analysis_data: dict) -> bool
    def load_analysis_results(self, directory: str) -> dict
    
    # Utility Methods
    def create_export_directory(self, base_path: str, timestamp: str) -> Path
    def validate_data_structure(self, data: dict, data_type: str) -> bool
    def get_file_info(self, file_path: str) -> dict
```

## Benefits of Refactoring:

### 1. **Maintainability** ✅
- Single place to update file formats
- Consistent error handling
- Easy to add new export formats

### 2. **Testability** ✅
- Mock file operations
- Test data validation
- Unit test each save/load operation

### 3. **Extensibility** ✅
- Easy to add new file formats (HDF5, Parquet, etc.)
- Plugin system for custom exporters
- Configurable export options

### 4. **Error Handling** ✅
- Centralized validation
- Consistent error messages
- Automatic backup on failed writes

### 5. **Performance** ✅
- Batch operations
- Async file writes (optional)
- Progress reporting for large files

## Estimated Refactoring Impact

### Lines to Extract:
- **main.py**: ~150 lines (save operations)
- **datawindow.py**: ~400 lines (SPR data I/O)
- **analysis.py**: ~150 lines (analysis I/O)
- **Total**: ~700 lines → Dedicated module

### Complexity: **Medium**
- Well-defined interfaces
- Mostly independent code
- Clear data structures
- Low risk to existing functionality

### Priority: **Medium-High**
- Improves code organization significantly
- Enables better error handling
- Facilitates future format changes
- Foundation for data pipeline improvements

## Example Usage After Refactoring:

```python
# In main.py
from utils.data_io_manager import DataIOManager

class AffiniteApp(QApplication):
    def __init__(self):
        # ...
        self.data_io = DataIOManager()
    
    def save_rec_data(self):
        """Save recorded data using IO manager."""
        try:
            # SPR data
            spr_data = self.collect_spr_data()
            self.data_io.save_spr_data(self.rec_dir, spr_data, CH_LIST)
            
            # Temperature log
            if self.device_config["ctrl"] == "PicoP4SPR":
                self.data_io.save_temperature_log(self.rec_dir, self.temp_log)
            
            # Kinetic logs
            if self.device_config["knx"]:
                version = self.knx.version if self.knx else "1.0"
                self.data_io.save_kinetic_log(self.rec_dir, self.log_ch1, "A", version)
                
            logger.info("✓ All data saved successfully")
            
        except Exception as e:
            logger.exception(f"Error saving data: {e}")
            show_message(f"Save failed: {e}", msg_type="Error")
```

## Next Steps if Proceeding:

1. Create `utils/data_io_manager.py`
2. Define data structures (TypedDict for validation)
3. Implement save methods with error handling
4. Implement load methods with validation
5. Update main.py to use DataIOManager
6. Update datawindow.py to use DataIOManager
7. Update analysis.py to use DataIOManager
8. Test with existing data files
9. Add comprehensive error handling
10. Document file formats

---

**Recommendation**: This is a **good second refactoring** after calibration. It's well-scoped, provides immediate benefits, and sets the foundation for better data management throughout the application.
