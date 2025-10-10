# Workspace Organization for Optimal Troubleshooting

**Date:** October 10, 2025  
**Purpose:** Ensure best performance and efficiency when debugging the SPR control system

---

## ✅ Current Status (Already Done)

- ✅ Single Python 3.12 virtual environment (`.venv/`)
- ✅ Simplified architecture (shared CalibrationState)
- ✅ Cleaned workspace (removed old files)
- ✅ Optimized VS Code settings (tool count reduced)
- ✅ All changes pushed to GitHub

---

## 🎯 Additional Optimizations for Troubleshooting

### 1. **Create .gitignore Additions** ✅

Add these to ensure clean git status during debugging:

```gitignore
# Python cache
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Virtual environments
.venv/
venv/
ENV/

# IDE
.vscode/
.idea/

# Testing
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage
*.cover

# Logs
logs/*.log
logs/*.log.*
generated-files/logfile.txt*
generated-files/stderr.txt
generated-files/stdout.txt

# Generated files (keep structure, ignore content)
generated-files/*.json
!generated-files/config.json

# OS
.DS_Store
Thumbs.db
```

### 2. **Organize Debug Configurations**

Create `.vscode/launch.json` for debugging:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Main Application",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/run_app.py",
      "console": "integratedTerminal",
      "justMyCode": false,
      "env": {
        "PYTHONPATH": "${workspaceFolder}",
        "USE_STATE_MACHINE": "true"
      }
    },
    {
      "name": "Python: Current File",
      "type": "debugpy",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal",
      "justMyCode": true
    },
    {
      "name": "Python: Calibration Only",
      "type": "debugpy",
      "request": "launch",
      "module": "main",
      "console": "integratedTerminal",
      "justMyCode": false,
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      }
    }
  ]
}
```

### 3. **Structured Logging Configuration**

Ensure logs are organized for easy debugging:

```
logs/
├── spr_control_structured.jsonl  ✅ Keep (structured logs)
├── debug_session_YYYYMMDD.log    📝 Create per session
└── calibration_YYYYMMDD.log      📝 Specific feature logs
```

### 4. **Workspace Folder Structure** (Optimized)

```
control-3.2.9/
├── .venv/                      # Python 3.12 only
├── .vscode/                    # IDE settings (local, not in git)
│   ├── settings.json          ✅ Optimized
│   ├── extensions.json        ✅ Essential only
│   ├── launch.json            📝 Debug configs
│   └── tasks.json             📝 Build/run tasks
│
├── main/                       # Application entry points
│   ├── __main__.py            # Entry point
│   └── main.py                # State machine app
│
├── utils/                      # Core functionality
│   ├── spr_calibrator.py      ⭐ CalibrationState + calibration logic
│   ├── spr_state_machine.py   ⭐ Shared state + state machine
│   ├── spr_data_acquisition.py
│   ├── spr_data_processor.py
│   ├── hal/                   # Hardware abstraction
│   │   ├── pico_p4spr_hal.py
│   │   └── usb4000_oceandirect_hal.py
│   └── ...
│
├── widgets/                    # GUI components
│   └── mainwindow.py
│
├── settings/                   # Configuration
│   └── settings.py            # Global settings
│
├── ui/                        # UI definitions
│
├── tests/                     # Test framework
│   └── test_framework.py
│
├── generated-files/           # Runtime data (ignored in git)
│   ├── config.json           ✅ Keep
│   ├── calibration_profiles/
│   └── calibration_history/
│
├── logs/                      # Logs (ignored in git)
│   └── spr_control_structured.jsonl
│
├── firmware/                  # Firmware files
│   └── pi_pico_fw/
│
├── 📚 DOCUMENTATION           # All documentation files
│   ├── README.md                          # Main docs
│   ├── SIMPLIFIED_ARCHITECTURE_README.md  # Architecture guide
│   ├── WORKSPACE_CLEANUP.md               # Cleanup details
│   ├── GITHUB_PUSH_AND_CLEANUP_COMPLETE.md
│   ├── TOOL_COUNT_FIX_COMPLETE.md
│   ├── HARDWARE_*.md                      # Hardware docs
│   ├── PRODUCTION_SYSTEMS_README.md
│   └── SMART_PROCESSING_README.md
│
└── 🔧 BUILD FILES
    ├── pyproject.toml
    ├── main.spec, mac.spec, dev.spec
    └── requirements_backup.txt
```

---

## 🐛 Troubleshooting Workflow Setup

### **A. Pre-Debugging Checklist**

```bash
# 1. Ensure you're in the right venv
.venv\Scripts\activate

# 2. Verify Python version
python --version  # Should be 3.12.x

# 3. Check for uncommitted changes
git status

# 4. Clean Python cache
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

# 5. Start fresh logs
Remove-Item logs\*.log -ErrorAction SilentlyContinue
```

### **B. Quick Reference - Key Files for Debugging**

#### **Data Flow Issues:**
1. `utils/spr_calibrator.py` (line 104-195) - CalibrationState class
2. `utils/spr_state_machine.py` (line 525-540) - Shared state creation
3. `utils/spr_state_machine.py` (line 320-355) - sync_from_shared_state
4. `utils/spr_data_acquisition.py` (line 462-490) - sensorgram_data/spectroscopy_data

#### **Signal Flow Issues:**
1. `utils/spr_state_machine.py` (line 270-310) - emit_to_ui function
2. `utils/spr_data_acquisition.py` (line 350-351) - Signal emissions
3. `main/main.py` (line 62-74) - Signal connections

#### **Hardware Issues:**
1. `utils/hal/pico_p4spr_hal.py` - Controller HAL
2. `utils/usb4000_oceandirect.py` - Spectrometer interface
3. `utils/spr_calibrator.py` (line 550-800) - Calibration methods

#### **Configuration:**
1. `settings/settings.py` - All global settings
2. `generated-files/config.json` - Runtime config

### **C. Debugging Commands**

```bash
# Run with detailed logging
python run_app.py

# Run specific module for testing
python -m main

# Check imports
python -c "from utils.spr_calibrator import CalibrationState; print('OK')"

# Verify shared state
python -c "from utils.spr_state_machine import SPRStateMachine; print('OK')"
```

### **D. VS Code Debugging Setup**

**Breakpoint Hotspots** (where to set breakpoints):

1. **Calibration Phase:**
   - `utils/spr_calibrator.py:605` - Wavelength storage
   - `utils/spr_calibrator.py:1194` - Dark noise storage
   - `utils/spr_calibrator.py:1650` - LED calibration

2. **Data Transfer Phase:**
   - `utils/spr_state_machine.py:528` - Shared state creation
   - `utils/spr_state_machine.py:348` - sync_from_shared_state

3. **Data Acquisition Phase:**
   - `utils/spr_data_acquisition.py:350` - update_live_signal emit
   - `utils/spr_data_acquisition.py:351` - update_spec_signal emit

4. **UI Update Phase:**
   - `utils/spr_state_machine.py:283` - sensorgram.update_data
   - `utils/spr_state_machine.py:286` - spectroscopy.update_data

---

## 📊 Performance Monitoring

### **A. Key Metrics to Watch**

```python
# Add to utils/logger.py for performance tracking
import time
import psutil
import os

def log_performance(phase: str):
    """Log current performance metrics."""
    process = psutil.Process(os.getpid())
    logger.info(f"📊 Performance [{phase}]:")
    logger.info(f"  Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB")
    logger.info(f"  CPU: {process.cpu_percent(interval=0.1):.1f}%")
    logger.info(f"  Threads: {process.num_threads()}")
```

### **B. Monitor Points**

Add performance logging at these points:
1. After hardware connection
2. After calibration complete
3. After data acquisition start
4. During continuous measurement (every 10s)

---

## 🔍 Quick Diagnostic Commands

### **Check Shared State:**
```python
# Add to state machine for debugging
def debug_shared_state(self):
    """Print shared state status."""
    logger.info("🔍 Shared State Debug:")
    logger.info(f"  Valid: {self.calib_state.is_valid()}")
    logger.info(f"  Wavelengths: {len(self.calib_state.wavelengths) if self.calib_state.wavelengths is not None else 0}")
    logger.info(f"  Dark noise: {len(self.calib_state.dark_noise) if self.calib_state.dark_noise is not None else 0}")
    logger.info(f"  Ref sig channels: {[ch for ch, ref in self.calib_state.ref_sig.items() if ref is not None]}")
```

### **Verify Data Flow:**
```python
# Add to data acquisition for debugging
def verify_data_pipeline(self):
    """Verify data pipeline integrity."""
    logger.info("🔍 Data Pipeline Check:")
    logger.info(f"  wave_data: {len(self.wave_data)}")
    logger.info(f"  dark_noise: {len(self.dark_noise)}")
    logger.info(f"  ref_sig available: {[ch for ch, ref in self.ref_sig.items() if ref is not None]}")
    logger.info(f"  signals connected: {self.update_live_signal is not None and self.update_spec_signal is not None}")
```

---

## 🎯 Recommended VS Code Extensions for Debugging

**Essential:**
1. **Python** (ms-python.python) - Language support
2. **Pylance** (ms-python.vscode-pylance) - Type checking
3. **GitHub Copilot** - AI assistance

**Debugging:**
4. **Python Debugger** (ms-python.debugpy) - Built into Python extension
5. **Error Lens** (usernamehw.errorlens) - Inline error highlighting

**Optional:**
6. **Better Comments** - Comment highlighting
7. **Git Graph** - Visual git history

---

## 📋 Troubleshooting Checklist

### Before Starting Debugging Session:

- [ ] **Workspace clean:** No uncommitted changes
- [ ] **Correct venv:** Python 3.12 activated
- [ ] **Cache cleared:** No `__pycache__` directories
- [ ] **Logs fresh:** Old logs deleted
- [ ] **VS Code reloaded:** Tool count optimizations applied
- [ ] **Git synced:** Latest changes pulled from origin
- [ ] **Documentation reviewed:** Architecture docs read

### During Debugging:

- [ ] **Set breakpoints:** At key transition points
- [ ] **Watch variables:** Monitor shared state
- [ ] **Check logs:** Review structured logs for errors
- [ ] **Monitor performance:** CPU/memory usage acceptable
- [ ] **Verify data flow:** Arrays sizes match
- [ ] **Check signals:** Emitters connected properly

### After Fixing Issues:

- [ ] **Test fix:** Run calibration → measurement cycle
- [ ] **Verify logs:** No errors or warnings
- [ ] **Check performance:** No degradation
- [ ] **Update docs:** Document fix in relevant README
- [ ] **Commit changes:** Clear commit message
- [ ] **Push to GitHub:** Share with team

---

## 🚀 Quick Start for Debugging Session

```bash
# 1. Activate venv
.venv\Scripts\activate

# 2. Clean workspace
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

# 3. Clear old logs
Remove-Item logs\*.log -ErrorAction SilentlyContinue

# 4. Verify setup
python --version
git status

# 5. Run with debugging (option 1: command line)
python run_app.py

# OR (option 2: VS Code debugger)
# Press F5 → Select "Python: Main Application"
```

---

## 📚 Key Documentation References

**During troubleshooting, refer to:**

1. **Architecture:** `SIMPLIFIED_ARCHITECTURE_README.md`
   - Data flow (3 layers)
   - Shared state design
   - Thread safety

2. **Hardware:** `HARDWARE_DOCUMENTATION_SUMMARY.md`
   - Device commands
   - Communication protocols

3. **Calibration:** `POLARIZER_CALIBRATION_SYSTEM.md`
   - Percentage-based approach
   - Adaptive LED algorithm

4. **Data Processing:** `SMART_PROCESSING_README.md`
   - Signal processing
   - Data structures

---

## 💡 Pro Tips

### **1. Use Structured Logs**
```python
# Good: Structured logging
logger.info(f"✅ Calibration complete: {calib_state.is_valid()}")

# Better: With context
logger.info(f"✅ Calibration complete | valid={calib_state.is_valid()} | "
           f"wavelengths={len(calib_state.wavelengths)} | "
           f"channels={list(calib_state.leds_calibrated.keys())}")
```

### **2. Add Debug Assertions**
```python
# Add at critical points
assert self.calib_state is not None, "Shared state not initialized!"
assert len(self.wave_data) > 0, "Wave data empty after sync!"
assert len(self.wave_data) == len(self.dark_noise), "Array size mismatch!"
```

### **3. Use Emoji in Logs for Quick Scanning**
```python
logger.info("✅ Success")
logger.warning("⚠️ Warning")
logger.error("❌ Error")
logger.debug("🔍 Debug info")
logger.info("📊 Performance metric")
logger.info("🎯 Important milestone")
```

### **4. Track State Transitions**
```python
# Already implemented in state machine
logger.info(f"State transition: {old_state} → {new_state}")
```

### **5. Use Conditional Breakpoints**
```python
# In VS Code debugger, set condition:
# calib_state.is_valid() == False
# len(wavelengths) != 3648
```

---

## ✅ Final Checklist - Workspace Ready for Troubleshooting

- ✅ Single Python 3.12 venv
- ✅ Optimized VS Code settings (tool count reduced)
- ✅ Clean workspace (no old files)
- ✅ Simplified architecture (shared state)
- ✅ Documentation up to date
- ✅ Git synchronized
- ✅ Debug configurations ready
- ✅ Performance monitoring available
- ✅ Key files identified
- ✅ Troubleshooting workflow defined

---

**Status:** 🎉 **WORKSPACE OPTIMIZED FOR TROUBLESHOOTING!**

**Next Steps:**
1. Reload VS Code (Ctrl+Shift+P → "Reload Window")
2. Verify tool count reduced (~20-30)
3. Review key documentation
4. Start debugging with F5 or `python run_app.py`

**Happy Debugging!** 🐛🔍
