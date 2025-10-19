# Diagnostic Scripts Archive

This directory contains temporary diagnostic and research scripts used during development of Affilabs 0.1.0. These scripts are **not required for production use** but are preserved for reference and future development.

## Script Inventory

### Polarizer Diagnostic Tools

**`scan_polarizer_positions.py`**
- Purpose: Scan all servo positions to identify blocking vs. transmitting windows
- Usage: `python scan_polarizer_positions.py`
- Output: Full 0-255 servo sweep showing signal strength at each position
- When used: Initial polarizer hardware characterization

**`verify_polarizer_windows.py`**
- Purpose: Test two discovered transmission windows to determine S vs P assignment
- Usage: `python verify_polarizer_windows.py`
- Output: Signal measurements for both configurations with S/P ratio analysis
- When used: Validating polarizer window assignments after sweep

**`test_sp_modes.py`**
- Purpose: Quick test of S-mode vs P-mode at specific positions
- Usage: Edit positions in script, then run
- Output: Signal levels in both modes for troubleshooting
- When used: Debugging polarizer mode switching

**`analyze_polarizer_intensities.py`**
- Purpose: Analyze polarizer sweep data in 600-630nm SPR range
- Usage: `python analyze_polarizer_intensities.py`
- Output: Spectral analysis of polarizer positions
- When used: Detailed spectral characterization

### Calibration Diagnostic Tools

**`check_calib.py`**
- Purpose: Quick review of calibration history
- Usage: `python check_calib.py`
- Output: Last 3 calibrations with integration time, LED intensities, weakest channel
- When used: Debugging calibration sequence issues

**`check_saturation.py`**
- Purpose: Comprehensive saturation diagnostic for all channels
- Usage: `python check_saturation.py`
- Output: Signal levels at different LED intensities and integration times
- When used: Diagnosing saturation during calibration

**`check_s_refs.py`**
- Purpose: Quick saturation check of S-mode reference signals
- Usage: `python check_s_refs.py`
- Output: Max/mean values with 62k saturation threshold check
- When used: Verifying S-ref calibration data quality

### LED Afterglow Research Scripts

**`led_afterglow_model.py`**
- Purpose: Characterize LED phosphor afterglow decay and fit exponential model
- Usage: `python led_afterglow_model.py`
- Output: Decay constants, correction algorithms, plots
- Runtime: ~10-15 minutes per channel
- When used: Initial afterglow characterization research

**`led_afterglow_integration_time_model.py`**
- Purpose: Build integration-time-dependent afterglow correction models
- Usage: `python led_afterglow_integration_time_model.py`
- Output: τ(integration_time) lookup tables for all channels
- Runtime: ~40-50 minutes (4 channels × 5 integration times)
- When used: Comprehensive afterglow modeling across parameter space

## Production Tools vs Research Scripts

**Production tools** (in `utils/` directory):
- `oem_calibration_tool.py` - OEM-facing polarizer calibration (PRODUCTION USE)
- `spr_calibrator.py` - Full 8-step calibration sequence (PRODUCTION USE)
- `device_configuration.py` - Device profile management (PRODUCTION USE)

**Research scripts** (this directory):
- For development, debugging, and research only
- Not required for normal operation
- May have hardcoded paths or require manual editing
- Useful for troubleshooting edge cases

## Usage Notes

### When to Use These Scripts

1. **Hardware Issues**: If polarizer behaves unexpectedly, use scan/verify scripts
2. **Calibration Debugging**: If calibration fails, use check_* scripts to diagnose
3. **Research**: To characterize new hardware or develop new features

### How to Run

All scripts assume they're run from the project root:

```powershell
# From: C:\Users\lucia\OneDrive\Desktop\control-3.2.9\

# Example: Scan polarizer positions
python tools/diagnostic_scripts/scan_polarizer_positions.py

# Example: Check calibration history
python tools/diagnostic_scripts/check_calib.py
```

### Important Warnings

⚠️ **Hardware Access**: Many scripts directly control hardware (LEDs, servo, spectrometer)
- Close main application before running
- Scripts may not include safety checks (rapid LED switching, etc.)
- Use at your own risk for development/debug only

⚠️ **Hardcoded Paths**: Some scripts have hardcoded paths for test data
- Edit paths as needed for your environment
- Output directories may not exist (scripts may fail)

⚠️ **Development Quality**: These are research/debug tools, not production code
- Minimal error handling
- May require code modification to adapt to your use case
- Not regularly tested or maintained

## Maintenance

**Status**: Archived as of Affilabs 0.1.0 (2025-10-19)

**Future Updates**:
- Scripts frozen at v0.1.0 state
- May be updated for future research/development
- Not part of regular maintenance cycle

**Deletion Policy**:
- Scripts preserved indefinitely for reference
- Safe to delete if disk space needed (all logic integrated into production code)

## Related Documentation

- **Production Guide**: See `README.md` for normal operation
- **OEM Calibration**: See `OEM_CALIBRATION_TOOL_GUIDE.md` for polarizer setup
- **Polarizer Reference**: See `docs/POLARIZER_REFERENCE.md` for comprehensive polarizer documentation
- **Architecture**: See `SIMPLIFIED_ARCHITECTURE_README.md` for system design

---

**Affilabs 0.1.0 "The Core"**
Diagnostic Scripts Archive - October 2025
