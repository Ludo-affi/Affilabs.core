# Standalone Tools

This folder contains standalone applications that can be run independently from the main Affilabs.core application.

## Tools

### 1. Data Replay (`data_replay.py`)
**Purpose**: Video-style playback of recorded SPR experiments
**Usage**: `python data_replay.py`
**Features**:
- Load Excel files with SPR data (live acquisition format or export format)
- Animated playback of experimental data cycle-by-cycle
- 4-channel simultaneous display with toggle controls
- Playback speed controls (1x, 2x, 5x, 10x)
- Timeline scrubber for seeking
- Cycle navigation (previous/next)
- Export to GIF or PNG (planned)

**Dependencies**: `data_replay_builder.py` (included)

---

### 2. Experiment Planner (`experiment_planner.py`)
**Purpose**: Interactive SPR experiment design and planning tool
**Usage**: `python experiment_planner.py`
**Features**:
- Plan immobilization levels
- Estimate expected responses
- Design concentration ranges for kinetics
- UniProt protein lookup integration
- Response calculation for different SPR surface chemistries
- Save/load experiment plans
- Export planning reports

**Dependencies**: `protein_utils.py` (included)

---

### 3. Data Analysis (`data_analysis.py`)
**Purpose**: Prototype for Affilabs.analyze - data analysis and visualization
**Usage**: `python data_analysis.py`
**Features**:
- Multi-experiment data loading
- Peak detection and analysis
- Kinetic analysis (ka, kd, KD calculations)
- Batch processing
- Statistical analysis
- Report generation
- Interactive data visualization

---

## Requirements

All tools require:
- Python 3.10+
- PySide6
- pandas
- numpy
- pyqtgraph (for data replay and analysis)

Some tools have additional requirements:
- `experiment_planner.py`: requests (for UniProt API)
- `data_analysis.py`: matplotlib, scipy (for advanced analysis)

## Running from this folder

Make sure you're in the project root directory when running these tools, as they need access to the `affilabs` package:

```bash
cd "ezControl-AI"
python standalone_tools/data_replay.py
python standalone_tools/experiment_planner.py
python standalone_tools/data_analysis.py
```

## Notes

- These tools are designed to work independently but share the same UI design system as the main application
- They can be distributed separately for specific use cases
- Data files are typically located in `test_data/` and `simulated_data/` folders
