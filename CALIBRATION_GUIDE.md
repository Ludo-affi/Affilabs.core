# Affilabs.core Calibration Guide

**Last Updated:** February 4, 2026
**Purpose:** Complete reference for all calibration types in Affilabs.core 2.0 SPR system

---

## Table of Contents

1. [Overview](#overview)
2. [Calibration Types](#calibration-types)
3. [Simple LED Calibration](#1-simple-led-calibration)
4. [Full System Calibration](#2-full-system-calibration)
5. [Polarizer Calibration](#3-polarizer-calibration)
6. [OEM LED Calibration](#4-oem-led-calibration)
7. [LED Model Training](#5-led-model-training)
8. [Startup Calibration](#startup-calibration)
9. [Troubleshooting](#troubleshooting)
10. [Best Practices](#best-practices)

---

## Overview

Calibration ensures optimal performance of your SPR system by:
- **Adjusting LED intensities** for consistent signal levels
- **Finding optimal polarizer positions** for S and P modes
- **Capturing reference spectra** for baseline corrections
- **Validating system performance** through quality control checks

### When to Calibrate

| Situation | Recommended Calibration |
|-----------|-------------------------|
| **First-time setup** | OEM LED Calibration (full) |
| **Sensor swap (same type)** | Simple LED Calibration |
| **Sensor swap (different type)** | Full System Calibration |
| **Optical model missing** | LED Model Training |
| **Polarizer drift** | Polarizer Calibration |
| **Daily startup** | Automatic startup calibration |
| **After maintenance** | Full System Calibration |

---

## Calibration Types

Affilabs.core 2.0 offers **5 calibration types**, each designed for specific use cases:

| Calibration Type | Duration | When to Use | Complexity |
|------------------|----------|-------------|------------|
| **Simple LED** | 10-20 sec | Quick sensor swap (same type) | ⭐ Easy |
| **Full System** | 3-5 min | Complete calibration with QC | ⭐⭐ Moderate |
| **Polarizer** | 2-5 min | Servo position optimization | ⭐⭐ Moderate |
| **OEM LED** | 10-15 min | Factory-level calibration | ⭐⭐⭐ Advanced |
| **LED Model Training** | 2-5 min | Rebuild optical model only | ⭐⭐ Moderate |

**All calibrations follow a uniform pattern:**
1. ✅ Stop live data acquisition
2. ✅ Run calibration procedure
3. ✅ Clear graphs (restart sensorgram at t=0)
4. ✅ Restart live data acquisition

---

## 1. Simple LED Calibration

### Quick Reference
- **Location:** Settings Tab → Calibration Controls → "Run Simple Calibration"
- **Duration:** 10-20 seconds
- **Purpose:** Fast LED intensity adjustment for sensor swaps
- **Requirements:** LED calibration model must already exist

### What It Does

Simple LED calibration performs a **quick convergence** to match LED intensities to your current sensor:
- Uses the existing LED calibration model (from previous OEM/Full calibration)
- Adjusts intensities for both S-mode and P-mode
- Updates device configuration
- **Does NOT** recalibrate polarizer positions or rebuild optical model

### Step-by-Step Procedure

1. **Prepare System:**
   - Install prism/sensor with buffer (no air bubbles)
   - Ensure hardware is connected (check Device Status tab)
   - Stable baseline preferred (30-60 min warmup ideal)

2. **Run Calibration:**
   - Go to **Settings** tab in sidebar
   - Scroll to **Calibration Controls** section
   - Click **"Run Simple Calibration"** button
   - Dialog appears with progress bar (auto-starts)

3. **Monitor Progress:**
   - S-mode convergence: 3-5 iterations
   - P-mode convergence: 3-5 iterations
   - Total time: 10-20 seconds

4. **Completion:**
   - ✅ "Simple calibration complete!" message
   - Graphs cleared and sensorgram restarted at t=0
   - Live data acquisition automatically resumed
   - Dialog auto-closes after 2 seconds

### When to Use

✅ **Use Simple LED when:**
- Swapping between sensors of the same type
- LED intensities seem off but polarizer positions are good
- You need a quick recalibration (minutes, not hours)
- LED model already exists in system

❌ **Don't use Simple LED when:**
- LED calibration model is missing (run OEM calibration first)
- Polarizer positions need adjustment (use Polarizer Calibration)
- First-time setup (use OEM LED Calibration)
- Sensor type has changed significantly

### Troubleshooting

**Problem:** "LED model not found" error
**Solution:** Run OEM LED Calibration first to create the optical model

**Problem:** Calibration completes but signal is too low/high
**Solution:** Run Full System Calibration for complete recalibration

**Problem:** Calibration freezes or hangs
**Solution:** Check logs for hardware errors, restart software if needed

---

## 2. Full System Calibration

### Quick Reference
- **Location:** Settings Tab → Calibration Controls → "Run Full Calibration"
- **Duration:** 3-5 minutes
- **Purpose:** Complete 6-step system calibration with quality control
- **Shows:** Startup Calibration Dialog with "Start" button

### What It Does

Full calibration performs a **complete 6-step calibration** with convergence and QC validation:

**6 Steps:**
1. **Dark Reference** - Capture detector dark signal (LEDs off)
2. **S-Mode Convergence** - Optimize LED intensities for S polarization
3. **S-Mode Reference** - Capture S-mode reference spectrum
4. **P-Mode Convergence** - Optimize LED intensities for P polarization
5. **P-Mode Reference** - Capture P-mode reference spectrum
6. **QC Validation** - Validate calibration quality

### Step-by-Step Procedure

1. **Prepare System:**
   - Install prism with buffer (critical: no air bubbles!)
   - Hardware connected and stable
   - Allow 30-60 min warmup for best results

2. **Start Calibration:**
   - Go to **Settings** tab → **Calibration Controls**
   - Click **"Run Full Calibration"** button
   - Startup Calibration Dialog appears

3. **Pre-Calibration Checklist:**
   - ✅ Prism installed with buffer
   - ✅ No air bubbles in flow cell
   - ✅ Detector connected
   - ✅ System warmed up
   - Click **"Start"** button

4. **Monitor Progress (3-5 minutes):**
   - Step 1: Dark reference (~10 sec)
   - Step 2: S-mode convergence (~60 sec)
   - Step 3: S-mode reference (~20 sec)
   - Step 4: P-mode convergence (~60 sec)
   - Step 5: P-mode reference (~20 sec)
   - Step 6: QC validation (~30 sec)

5. **Review QC Report:**
   - Dialog shows "✅ Calibration Successful!"
   - Review QC graphs:
     - ✅ Signal strength adequate
     - ✅ Baseline stability good
     - ✅ LED convergence successful
   - If warnings appear, review logs for details

6. **Start Live Data:**
   - Click **"Start"** button (enabled after calibration)
   - Graphs cleared, sensorgram restarted at t=0
   - Live data acquisition begins
   - Dialog auto-closes

### When to Use

✅ **Use Full Calibration when:**
- Sensor type has changed significantly
- After system maintenance
- First use after installation
- Monthly routine calibration
- QC validation required

### QC Validation Criteria

Full calibration validates:
- ✅ Signal strength above minimum threshold
- ✅ LED convergence successful (both S and P)
- ✅ Baseline stability within tolerance
- ✅ Reference spectra quality good
- ✅ No detector saturation

### Troubleshooting

**Problem:** Calibration fails at convergence step
**Solution:**
- Check for air bubbles in flow cell
- Ensure LEDs are functioning (check Device Status)
- Verify detector connection

**Problem:** QC warnings about baseline drift
**Solution:**
- Allow longer warmup time (60+ minutes)
- Check temperature stability
- Ensure flow is stable

**Problem:** "Start" button doesn't appear after calibration
**Solution:** Check logs for calibration errors, may need to restart

---

## 3. Polarizer Calibration

### Quick Reference
- **Location:** Settings Tab → Calibration Controls → "Calibrate Polarizer"
- **Duration:** 2-5 minutes
- **Purpose:** Find optimal servo positions for S and P modes
- **Algorithm:** Sweeps 180° to find positions ~90° apart with best signal

### What It Does

Polarizer calibration automatically finds the **optimal servo positions** for maximum signal in S and P modes:
- Sweeps servo motor across 180° range (0-255 PWM)
- Measures signal at each position
- Identifies peaks for S-mode and P-mode
- Verifies positions are ~90° apart
- Saves positions to device configuration

### Step-by-Step Procedure

1. **Prepare System:**
   - Prism installed with buffer
   - Hardware connected
   - Stable baseline (warmup recommended)

2. **Start Calibration:**
   - Go to **Settings** tab → **Calibration Controls**
   - Click **"Calibrate Polarizer"** button
   - Progress dialog appears

3. **Monitor Progress (2-5 minutes):**
   - "🔄 Sweeping servo positions..."
   - "📊 Analyzing signal peaks..."
   - "✅ Optimal positions found"

4. **Results:**
   - S position: PWM value (e.g., 128)
   - P position: PWM value (e.g., 45)
   - Positions saved to device_config.json
   - Servo moves to P position
   - Graphs cleared, sensorgram restarted
   - Live data resumed

5. **Completion:**
   - Dialog: "Polarizer calibration completed successfully!"
   - System ready for use

### When to Use

✅ **Use Polarizer Calibration when:**
- Signal strength drops over time
- After servo motor replacement
- Polarizer positions seem incorrect
- Manual servo adjustment needed
- OEM calibration polarizer step needed

❌ **Don't use when:**
- Hardware not connected
- Servo motor malfunctioning
- During active acquisition (will auto-stop)

### Technical Details

**Servo Positions:**
- Range: 0-255 (PWM values, not degrees)
- S and P positions should be ~90° apart
- Typical values: S=128, P=45 (device-specific)

**Storage Location:**
- File: `affilabs/config/devices/{serial}/device_config.json`
- Section: `hardware.servo_s_position`, `hardware.servo_p_position`

### Troubleshooting

**Problem:** "Servo not responding" error
**Solution:**
- Check hardware connections
- Restart software
- Verify servo motor functionality

**Problem:** Positions found are not ~90° apart
**Solution:**
- Check for mechanical obstruction
- Verify polarizer is properly installed
- Contact technical support if persistent

**Problem:** Calibration completes but signal still low
**Solution:**
- Run Full System Calibration (includes LED adjustment)
- Check detector calibration
- Verify prism/sensor quality

---

## 4. OEM LED Calibration

### Quick Reference
- **Location:** Settings Tab → Calibration Controls → "Run OEM Calibration"
- **Duration:** 10-15 minutes
- **Purpose:** Factory-level complete calibration (servo + LED + full system)
- **Complexity:** Advanced users only

### What It Does

OEM calibration is the **most complete calibration workflow**:

**3-Phase Process:**
1. **Servo Polarizer Calibration** (2-5 min)
   - Finds optimal S and P positions
   - Saves to device configuration

2. **LED Model Training** (2-5 min)
   - Measures LED response at 10-60ms integration times
   - Creates 3-stage linear calibration model
   - Saves optical_calibration.json

3. **Full 6-Step Calibration** (3-5 min)
   - Runs complete system calibration (see Full Calibration section)
   - Uses newly trained LED model

**Total Time:** 10-15 minutes

### Step-by-Step Procedure

1. **Prepare System:**
   - ⚠️ **CRITICAL:** Fresh, clean prism with buffer
   - ⚠️ **CRITICAL:** No air bubbles
   - Hardware connected
   - 60+ minute warmup strongly recommended

2. **Start OEM Calibration:**
   - Go to **Settings** tab → **Calibration Controls**
   - Click **"Run OEM Calibration"** button
   - Dialog shows 3-phase process overview
   - Click **"Start"**

3. **Phase 1: Servo Polarizer (2-5 min)**
   - Progress: "🔄 Calibrating servo positions..."
   - Sweeps servo range
   - Finds optimal S and P positions
   - Saves to device configuration

4. **Phase 2: LED Model Training (2-5 min)**
   - Progress: "🔄 Training LED calibration model..."
   - Tests integration times: 10ms, 20ms, 30ms, 40ms, 50ms, 60ms
   - Measures responses for all LED channels (A, B, C, D)
   - Creates 3-stage linear model
   - Saves optical_calibration.json

5. **Phase 3: Full System Calibration (3-5 min)**
   - Progress: "🔄 Running 6-step calibration..."
   - Runs complete calibration (see Full Calibration)
   - Uses newly trained LED model
   - Captures references and validates QC

6. **Review Results:**
   - Dialog: "✅ OEM Calibration Successful!"
   - Review QC graphs
   - Click **"Start"** to begin live data

7. **Completion:**
   - Graphs cleared, sensorgram restarted
   - Live data acquisition resumed
   - System fully calibrated and ready

### When to Use

✅ **Use OEM Calibration when:**
- First-time system setup
- LED model missing or corrupted
- Complete factory reset needed
- After major hardware changes
- Sensor type completely different from previous

❌ **Don't use OEM when:**
- Simple sensor swap (use Simple LED instead)
- Time-limited (use Quick LED or Full Calibration)
- LED model exists and works well

### Output Files

**1. device_config.json** (servo positions)
```json
{
  "hardware": {
    "servo_s_position": 128,
    "servo_p_position": 45
  }
}
```

**2. optical_calibration.json** (LED model)
```json
{
  "led_model": {
    "channel_A": { "stage1": {...}, "stage2": {...}, "stage3": {...} },
    "channel_B": { ... },
    "channel_C": { ... },
    "channel_D": { ... }
  },
  "calibration_date": "2026-02-04T15:30:00"
}
```

**3. Calibration results** (full system calibration)
- S-mode reference spectrum
- P-mode reference spectrum
- QC validation results

### Troubleshooting

**Problem:** "Optical calibration failed" during Phase 2
**Solution:**
- Ensure prism is clean and bubble-free
- Check detector connection
- Verify LEDs are functioning
- Allow longer warmup time

**Problem:** OEM calibration takes too long (>20 minutes)
**Solution:**
- Normal for first-time calibration
- Check logs for stalled steps
- Verify hardware not overheating

**Problem:** Phase 3 fails after successful Phase 1 and 2
**Solution:**
- LED model was created successfully
- Run Full Calibration separately to retry Phase 3
- Check for hardware issues (bubbles, flow problems)

---

## 5. LED Model Training

### Quick Reference
- **Location:** Settings Tab → Calibration Controls → "Train LED Model"
- **Duration:** 2-5 minutes
- **Purpose:** Rebuild optical model without full calibration
- **Output:** Creates/updates optical_calibration.json

### What It Does

LED Model Training performs **Phase 2 of OEM Calibration only**:
- Measures LED response at multiple integration times (10-60ms)
- Creates 3-stage linear calibration model
- Saves optical_calibration.json
- **Does NOT** run servo calibration or full system calibration

### Step-by-Step Procedure

1. **Prepare System:**
   - Prism installed with buffer
   - Hardware connected
   - Stable baseline recommended

2. **Start Training:**
   - Go to **Settings** tab → **Calibration Controls**
   - Click **"Train LED Model"** button
   - Dialog appears with overview
   - Click **"Start"**

3. **Monitor Progress (2-5 min):**
   - "Testing 10ms integration time..."
   - "Testing 20ms integration time..."
   - "Testing 30ms integration time..."
   - "Testing 40ms integration time..."
   - "Testing 50ms integration time..."
   - "Testing 60ms integration time..."
   - "Creating 3-stage linear model..."

4. **Completion:**
   - "✅ LED calibration model created successfully!"
   - optical_calibration.json updated
   - Graphs cleared, sensorgram restarted
   - Live data resumed
   - Dialog auto-closes

### When to Use

✅ **Use LED Model Training when:**
- optical_calibration.json is missing
- LED model seems incorrect
- LED hardware has changed
- Want to update model without full OEM calibration

❌ **Don't use when:**
- Full OEM calibration is needed (includes model training)
- Servo positions also need calibration (use OEM instead)

### Technical Details

**3-Stage Linear Model:**
- **Stage 1:** 10-20ms (low integration times)
- **Stage 2:** 20-40ms (medium integration times)
- **Stage 3:** 40-60ms (high integration times)

Each stage has linear regression coefficients for converting target intensity to actual LED PWM values.

**Model File:** `affilabs/config/devices/{serial}/optical_calibration.json`

### Troubleshooting

**Problem:** "Model training failed" error
**Solution:**
- Check detector connection
- Verify all LED channels functioning
- Ensure stable baseline
- Run OEM calibration for full reset

**Problem:** Model created but intensities still wrong
**Solution:**
- Run Full System Calibration to test new model
- Check if servo positions are correct (run Polarizer Calibration)

---

## Startup Calibration

### Automatic Daily Calibration

Every time you click **"Power On"**, Affilabs.core runs an **automatic startup calibration**:

**Purpose:**
- Quick daily system check and optimization
- Ensures consistent performance
- Takes 1-2 minutes

**What It Does:**
1. Checks hardware connection
2. Runs quick LED adjustment (similar to Simple LED)
3. Validates signal quality
4. Shows QC Report

**Dialog Flow:**
1. Click **"Power On"** button
2. "Hardware connected" message
3. Startup Calibration Dialog appears
4. Click **"Start"**
5. Progress bar (1-2 minutes)
6. QC Report displayed
7. Review results, click **"Start"** to begin live data

### Startup Calibration Failure Recovery

**New Feature (Feb 2026):** Manual retry with up to 3 attempts

If startup calibration fails:
1. Dialog shows: "❌ Calibration Failed"
2. **Two options appear:**
   - **Retry** - Try calibration again (up to 3 total attempts)
   - **Continue Anyway** - Skip calibration and manually troubleshoot

**Retry Button:**
- Restarts calibration from beginning
- Attempt counter shown (e.g., "Attempt 2/3")
- After 3 failed attempts, Retry button disabled
- Use when: temporary issue like bubbles, brief connection loss

**Continue Anyway Button:**
- Closes dialog without retrying
- Allows manual troubleshooting
- Live data can still be started
- Use when: need to diagnose hardware, change settings, or run different calibration

**Example Workflow:**
```
Attempt 1: Failed (air bubble)
→ Remove bubble, click Retry

Attempt 2: Failed (still stabilizing)
→ Wait 30 seconds, click Retry

Attempt 3: Success!
→ Review QC, click Start
```

### Troubleshooting Startup Calibration

**Problem:** Startup calibration fails repeatedly
**Solution:**
1. Click **"Continue Anyway"**
2. Check Device Status tab for hardware issues
3. Go to Settings → Calibration Controls
4. Run Full System Calibration manually
5. If persistent, contact technical support

**Problem:** "Hardware not found" during startup
**Solution:**
- Check USB connections
- Verify power supply
- Try different USB port
- Restart software

**Problem:** QC Report shows warnings
**Solution:**
- Check for air bubbles
- Verify baseline stability
- Allow more warmup time
- Run Full System Calibration if warnings persist

---

## Troubleshooting

### Common Issues and Solutions

#### 1. "LED model not found"

**Symptoms:**
- Simple LED Calibration fails
- Error: "optical_calibration.json not found"

**Solution:**
- Run **OEM LED Calibration** to create LED model
- OR run **LED Model Training** to create model without full OEM

#### 2. Calibration Freezes or Hangs

**Symptoms:**
- Progress bar stops moving
- Dialog becomes unresponsive

**Solution:**
- Check logs for Qt threading errors
- If frozen >5 minutes, restart software
- Run calibration again
- Report to technical support if persistent

#### 3. Signal Too Low After Calibration

**Symptoms:**
- Calibration completes successfully
- But signal strength is still low

**Possible Causes:**
- Air bubbles in flow cell
- Dirty or damaged prism
- LED hardware issue
- Detector issue

**Solution:**
1. Check for air bubbles, purge system
2. Clean/replace prism
3. Run **Polarizer Calibration** to check servo positions
4. Run **Full System Calibration**
5. Check Device Status for hardware errors

#### 4. Baseline Drift After Calibration

**Symptoms:**
- Calibration successful
- But baseline drifts during acquisition

**Solution:**
- Allow 60+ minute warmup before calibration
- Check temperature stability
- Ensure flow rate is stable
- Use baseline correction in Analysis tab

#### 5. "Calibration Failed" - No Specific Error

**Symptoms:**
- Generic "calibration failed" message
- No specific error details

**Solution:**
1. Check logs for detailed error message
2. Verify all hardware connected (Device Status tab)
3. Ensure prism installed with buffer (no bubbles)
4. Allow warmup time (30-60 min)
5. Try **Full System Calibration** instead
6. Contact support with log file if persistent

#### 6. Servo Positions Not Saving

**Symptoms:**
- Polarizer calibration completes
- But positions revert to old values

**Solution:**
- Check write permissions on config folder
- Verify device_config.json exists
- Run calibration as administrator
- Check logs for file write errors

#### 7. QC Report Shows Warnings

**Symptoms:**
- Calibration completes
- QC Report has yellow/red warnings

**Common Warnings:**
- ⚠️ "Signal strength below optimal"
- ⚠️ "Baseline drift detected"
- ⚠️ "LED convergence slow"

**Solution:**
- For signal strength: Check prism, LEDs, detector
- For baseline drift: Allow more warmup, check temperature
- For slow convergence: Check LED model, may need retraining
- Click **Retry** if during startup calibration
- Run **Full System Calibration** if warnings persist

---

## Best Practices

### Daily Routine

**Every Day:**
1. ✅ Click "Power On"
2. ✅ Run automatic startup calibration (1-2 min)
3. ✅ Review QC Report
4. ✅ If successful, start live data
5. ✅ If failed, use Retry button (up to 3 attempts)

**Weekly:**
- Run **Full System Calibration** for QC validation
- Check QC trends in logs

**Monthly:**
- Run **OEM LED Calibration** for complete system refresh
- Document calibration results for compliance

### Sensor Swap Workflow

**Same Sensor Type:**
1. Install new sensor with buffer
2. Run **Simple LED Calibration** (10-20 sec)
3. Start acquisition

**Different Sensor Type:**
1. Install new sensor with buffer
2. Run **Full System Calibration** (3-5 min)
3. Review QC Report
4. Start acquisition

**Major Sensor Change:**
1. Install new sensor
2. Run **OEM LED Calibration** (10-15 min)
3. Thoroughly review QC Report
4. Validate with test samples

### Maintenance Workflow

**After Routine Maintenance:**
- Run **Full System Calibration**
- Document results

**After Servo Replacement:**
- Run **Polarizer Calibration** first
- Then run **Full System Calibration**

**After LED/Detector Replacement:**
- Run **OEM LED Calibration** (complete reset)
- Validate with known samples

### Quality Control

**QC Validation Schedule:**
- Daily: Startup calibration QC
- Weekly: Full calibration QC
- Monthly: OEM calibration QC
- After maintenance: Full calibration QC

**QC Documentation:**
- Save QC reports to file
- Track calibration trends over time
- Note any warnings or failures
- Document corrective actions

### Calibration Hygiene

**Before Every Calibration:**
- ✅ Clean prism/sensor
- ✅ Fresh buffer (no bubbles)
- ✅ Allow warmup time (30-60 min ideal)
- ✅ Check hardware connections (Device Status)
- ✅ Verify stable baseline

**During Calibration:**
- ❌ Don't disturb the system
- ❌ Don't change settings
- ❌ Don't run other operations
- ✅ Monitor progress dialog

**After Calibration:**
- ✅ Review QC Report
- ✅ Verify sensorgram looks good
- ✅ Document any issues
- ✅ Save calibration results

---

## Quick Reference Tables

### Calibration Comparison

| Feature | Simple LED | Full System | Polarizer | OEM LED | LED Training |
|---------|-----------|-------------|-----------|---------|--------------|
| **Duration** | 10-20 sec | 3-5 min | 2-5 min | 10-15 min | 2-5 min |
| **LED Adjustment** | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes | ❌ No |
| **Servo Calibration** | ❌ No | ❌ No | ✅ Yes | ✅ Yes | ❌ No |
| **LED Model Training** | ❌ No | ❌ No | ❌ No | ✅ Yes | ✅ Yes |
| **Reference Capture** | ❌ No | ✅ Yes | ❌ No | ✅ Yes | ❌ No |
| **QC Validation** | ❌ No | ✅ Yes | ❌ No | ✅ Yes | ❌ No |
| **Requires LED Model** | ✅ Yes | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **Stops Live Data** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Clears Graphs** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Restarts Live Data** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |

### When to Use What

| Scenario | Recommended Calibration | Duration |
|----------|-------------------------|----------|
| First-time setup | OEM LED Calibration | 10-15 min |
| Daily startup | Automatic Startup | 1-2 min |
| Quick sensor swap (same type) | Simple LED Calibration | 10-20 sec |
| Sensor swap (different type) | Full System Calibration | 3-5 min |
| LED model missing | LED Model Training or OEM | 2-15 min |
| Polarizer drift | Polarizer Calibration | 2-5 min |
| After maintenance | Full System Calibration | 3-5 min |
| Monthly QC | OEM LED Calibration | 10-15 min |
| Troubleshooting low signal | Full System Calibration | 3-5 min |

### Files Modified by Each Calibration

| Calibration | device_config.json | optical_calibration.json | References |
|-------------|-------------------|-------------------------|------------|
| Simple LED | ✅ Yes (LED intensities) | ❌ No | ❌ No |
| Full System | ✅ Yes (LED intensities) | ❌ No | ✅ Yes (S/P refs) |
| Polarizer | ✅ Yes (servo positions) | ❌ No | ❌ No |
| OEM LED | ✅ Yes (servo + LED) | ✅ Yes (model) | ✅ Yes (S/P refs) |
| LED Training | ❌ No | ✅ Yes (model) | ❌ No |

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| None | Calibrations must be started from UI |

*Note: Calibration cannot be started via keyboard shortcuts for safety reasons.*

---

## Technical Support

If calibration issues persist after troubleshooting:

1. **Collect Information:**
   - Full error message
   - Log file (from logs/ directory)
   - Calibration type attempted
   - Steps already tried

2. **Contact Support:**
   - Email: support@affinitylabs.com
   - Include log file attachment
   - Describe issue and troubleshooting steps

3. **Emergency Workarounds:**
   - Use **"Continue Anyway"** button to skip failed startup calibration
   - Manually run **Full System Calibration** from Settings tab
   - Check Device Status for hardware issues

---

## Appendix: Calibration File Locations

### Configuration Files

```
affilabs/config/
├── device_config.json                    # Default (no serial number)
└── devices/
    └── {serial_number}/
        ├── device_config.json            # Device-specific config
        └── optical_calibration.json      # LED calibration model
```

### Calibration Results

```
calibration_results/
├── latest_calibration.json               # Most recent full calibration
└── calibration_YYYYMMDD_HHMMSS.json     # Timestamped backups
```

### Log Files

```
logs/
├── affilabs_YYYYMMDD.log                # Main application log
└── calibration_YYYYMMDD.log             # Calibration-specific log
```

---

## Changelog

**February 4, 2026:**
- ✅ All 5 calibrations now uniformized (stop → run → clear → restart)
- ✅ Added manual retry functionality for startup calibration (max 3 attempts)
- ✅ Fixed QTimer threading issues in Simple LED, Polarizer, and LED Training
- ✅ Documented all calibration workflows
- ✅ Added troubleshooting section
- ✅ Added best practices guide

---

**End of Calibration Guide**

For the latest documentation, see:
- [CALIBRATION_ENTRY_EXIT_FLOWS.md](CALIBRATION_ENTRY_EXIT_FLOWS.md) - Technical implementation details
- [SPARK_TRAINING_GUIDE.md](SPARK_TRAINING_GUIDE.md) - How to train Spark AI with this guide

