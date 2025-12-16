# Demo Data System - Quick Reference

## 🎯 Purpose
Generate realistic SPR binding curves for promotional images and screenshots.

## ⚡ Quick Commands (Choose One)

### 🌟 **EASIEST: Load Demo Data in Running App**
**Press: `Ctrl+Shift+D`** while application is running

### 🚀 **Launch with Pre-loaded Data**
```powershell
python load_demo_ui.py
```

### 📊 **Preview Data (Optional - requires matplotlib)**
```powershell
# First install matplotlib if you want preview:
pip install matplotlib

# Then run preview:
python preview_demo_data.py
```
**Note:** Preview is optional - you can use the demo data without matplotlib!

## 📊 What You Get

**3 cycles** of realistic SPR kinetics:
- Cycle 1: 20 RU (low concentration)
- Cycle 2: 40 RU (medium concentration)
- Cycle 3: 65 RU (high concentration)

Each cycle shows:
- Baseline (0-60s)
- Association/binding (60-300s)
- Dissociation/washout (300-600s)

**4 channels** with realistic variation:
- Channel A: Red (100% response)
- Channel B: Green (87% response)
- Channel C: Blue (95% response)
- Channel D: Orange (82% response)

## 📁 Files Added

1. **`utils/demo_data_generator.py`** - Core generator
2. **`preview_demo_data.py`** - Visual preview (optional)
3. **`load_demo_ui.py`** - Launch with data
4. **`DEMO_DATA_README.md`** - Full documentation
5. **`DEMO_QUICK_START.md`** - This file

## 🚀 Recommended Workflow

1. Run your application normally: `python main_simplified.py`
2. Get to a good UI state (adjust windows, etc.)
3. Press **Ctrl+Shift+D** to load demo data
4. Take your promotional screenshots!

## 💡 Best Views for Screenshots

- **Full Sensorgram**: Shows all 3 cycles, professional overview
- **Cycle 2 Zoom**: Best kinetics detail, clear phases
- **Multi-Channel**: All 4 channels visible, shows comparison

## ✨ Features

✅ Realistic binding kinetics (Langmuir model)
✅ Proper noise characteristics (~0.5 RU)
✅ Channel variation (biological realism)
✅ Baseline drift simulation
✅ Easy keyboard shortcut (Ctrl+Shift+D)
✅ Instant loading (no file I/O)

## 🔧 Customization

Edit `utils/demo_data_generator.py` line 155+ to change:
- Number of cycles
- Response levels
- Cycle duration
- Noise levels
- Kinetic constants

---

**Need help?** See `DEMO_DATA_README.md` for full documentation.
