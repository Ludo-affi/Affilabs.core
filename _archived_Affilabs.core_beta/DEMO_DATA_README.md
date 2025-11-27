# Demo Data Generator for Promotional Images

This system generates realistic SPR binding curves for creating promotional screenshots and marketing materials.

## Quick Start

### Option 1: Preview the Data First (Recommended)
```powershell
cd "c:\Users\ludol\ezControl-AI\Affilabs.core beta"
python preview_demo_data.py
```
This will show you what the demo data looks like before loading it into the UI.

### Option 2: Load Demo Data in Running Application
1. Launch the application normally:
   ```powershell
   python main_simplified.py
   ```
2. Press **Ctrl+Shift+D** to load demo data instantly

### Option 3: Launch with Pre-loaded Demo Data
```powershell
python load_demo_ui.py
```
The UI will open with demo data already displayed.

## What Does the Demo Data Include?

### Data Structure
- **3 cycles** of SPR binding kinetics
- **600 seconds** per cycle (10 minutes each)
- **2 Hz sampling rate** (2 data points per second)
- **4 channels** (A, B, C, D) with realistic variation

### Kinetic Phases (per cycle)
- **0-60s**: Baseline stabilization
- **60-300s**: Association phase (analyte binding)
- **300-600s**: Dissociation phase (analyte washout)

### Concentration Series
- **Cycle 1**: 20 RU maximum response (low concentration)
- **Cycle 2**: 40 RU maximum response (medium concentration)
- **Cycle 3**: 65 RU maximum response (high concentration)

### Realistic Features
- ✅ Exponential association kinetics (ka = 1×10⁵ M⁻¹s⁻¹)
- ✅ Exponential dissociation kinetics (kd = 1×10⁻³ s⁻¹)
- ✅ Channel-to-channel variation (~80-100% relative response)
- ✅ Realistic noise (~0.5 RU standard deviation)
- ✅ Baseline drift (0.5 RU over full experiment)
- ✅ Low-frequency noise oscillations

## Files Created

| File | Purpose |
|------|---------|
| `utils/demo_data_generator.py` | Core data generation engine |
| `preview_demo_data.py` | Matplotlib visualization preview |
| `load_demo_ui.py` | Launch UI with pre-loaded data |
| `DEMO_DATA_README.md` | This documentation |

## Usage Examples

### For Marketing Screenshots
1. Run `python load_demo_ui.py`
2. Navigate to desired view (Sensorgram, Cycle of Interest, etc.)
3. Take screenshots showing:
   - Full timeline with 3 cycles
   - Zoomed cycle showing binding curves
   - Multi-channel overlay
   - Any UI features you want to highlight

### For Training Materials
1. Load demo data (any method above)
2. Use "Cycle of Interest" view to zoom into specific cycles
3. Demonstrate:
   - Channel selection/deselection
   - Zoom controls
   - Export functionality
   - Analysis tools

### For Presentations
The preview script (`preview_demo_data.py`) generates high-quality matplotlib plots suitable for:
- PowerPoint presentations
- Scientific posters
- Documentation
- Website graphics

## Customizing Demo Data

Edit `utils/demo_data_generator.py` to adjust:

```python
# In generate_demo_cycle_data() function:
responses = [20, 40, 65]  # Change max responses
cycle_duration = 600      # Change cycle length (seconds)
num_cycles = 3           # Change number of cycles
sampling_rate = 2.0      # Change sampling frequency (Hz)
noise_level = 0.5        # Change noise magnitude (RU)
ka = 1e5                 # Change association rate
kd = 1e-3                # Change dissociation rate
```

## Technical Details

### Kinetic Model
The demo data uses a **Langmuir binding model**:

**Association**: R(t) = R_max × (1 - exp(-k_obs×t))
- where k_obs = k_a×C + k_d

**Dissociation**: R(t) = R_0 × exp(-k_d×t)

### Noise Model
- **White noise**: Gaussian (σ = 0.5 RU)
- **Low-frequency drift**: Sinusoidal (0.01 Hz, 0.2 RU amplitude)
- **Baseline drift**: Linear (0.5 RU over experiment)

### Channel Variation
Channels show realistic biological variation:
- Channel A: 100% of specified response
- Channel B: 87% (slightly lower binding)
- Channel C: 95% (near-optimal binding)
- Channel D: 82% (lowest binding)

## Tips for Best Screenshots

1. **Full Timeline View**
   - Shows all 3 cycles
   - Demonstrates experiment overview
   - Good for showing navigation features

2. **Cycle of Interest (Zoomed)**
   - Focus on Cycle 2 (middle, medium response)
   - Shows clear association/dissociation phases
   - Best for demonstrating kinetic analysis

3. **Multi-Channel Overlay**
   - Keep all 4 channels visible
   - Shows channel comparison capability
   - Demonstrates color-coding system

4. **Clean Interface**
   - Consider hiding debug panels
   - Maximize graph area
   - Use high-contrast settings for clarity

## Troubleshooting

### "Module not found" error
Make sure you're in the correct directory:
```powershell
cd "c:\Users\ludol\ezControl-AI\Affilabs.core beta"
```

### Data doesn't appear in graphs
1. Check that `_update_plots()` method exists in UI
2. Verify time_buffer and wavelength_buffer_* attributes exist
3. Try closing and reopening the application

### Matplotlib plot doesn't show
Install matplotlib if missing:
```powershell
pip install matplotlib
```

## Contact

For questions or issues with demo data generation, contact the development team.

---

**Last Updated**: November 24, 2025
**Version**: 1.0
**Author**: AI Assistant
