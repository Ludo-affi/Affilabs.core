# Active Calibrations - Single Source of Truth

This folder contains the **active calibration data** for all devices in the OEM network.

## Structure

```
calibrations/
  active/
    {DEVICE_SERIAL}/
      led_model.json          # 3-stage linear LED calibration model
      device_profile.json     # Polarizer positions, afterglow, device metadata
      startup_config.json     # Current LED intensities & integration times
  archive/
    {DEVICE_SERIAL}/
      {TIMESTAMP}/            # Historical calibrations
```

## Files in Each Device Folder

### 1. `led_model.json`
**Purpose:** Pre-computed 3-stage linear LED model for instant intensity calculations  
**Model:** `counts = slope_10ms × intensity × (time_ms / 10)`  
**Source:** OEM factory calibration (from `led_calibration_official/spr_calibration/data/`)  
**Updated:** When new OEM calibration is performed

### 2. `device_profile.json`
**Purpose:** Device-specific system calibration data  
**Contains:**
- Polarizer S/P servo positions
- S/P intensity ratio
- Afterglow correction data
- Device metadata (serial, type, LED type)  
**Source:** Polarizer calibration, afterglow calibration  
**Updated:** When polarizer or afterglow calibration is performed

### 3. `startup_config.json`
**Purpose:** Current active LED settings for device startup  
**Contains:**
- S-mode LED intensities (a, b, c, d)
- P-mode LED intensities (a, b, c, d)
- S-mode integration time
- P-mode integration time  
**Source:** Latest full system calibration or simple LED calibration  
**Updated:** Every time LED calibration runs

## Usage

All calibration loaders check `calibrations/active/{SERIAL}/` **first** before falling back to legacy locations:
- `LEDCalibrationModelLoader` → checks `led_model.json`
- Device profile loaders → check `device_profile.json`
- Startup configuration → checks `startup_config.json`

## Migration

Run `tools/consolidate_active_calibrations.py` to populate this folder with current active calibrations from legacy locations.

---

**Version:** 1.0  
**Date:** December 19, 2025  
**Author:** ezControl OEM System
